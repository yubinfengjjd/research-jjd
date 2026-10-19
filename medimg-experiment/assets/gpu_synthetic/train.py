"""Real tiny grouped synthetic trainer implementing the ME execution protocol."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

import numpy as np
import model
import sampler
import synth_data

torch = model.torch


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def atomic_save(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temp)
    temp.replace(path)


def state_copy(network):
    return {k: v.detach().cpu().clone() for k, v in network.state_dict().items()}


def digest(state):
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        h.update(key.encode())
        h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("classification", "segmentation"))
    p.add_argument("--dimension", required=True, type=int, choices=(2, 3))
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--width", type=int, default=4)
    p.add_argument("--learning-rate", type=float, default=0.03)
    a = p.parse_args()
    if not 1 <= a.epochs <= 32 or not 1 <= a.width <= 16:
        raise ValueError("tiny fixture limits exceeded")
    out = Path(os.environ["ME_OUTPUT_DIR"])
    out.mkdir(parents=True, exist_ok=True)
    run_id, phase = os.environ["ME_RUN_ID"], os.environ["ME_PHASE"]
    device = torch.device(os.environ["ME_DEVICE"])
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("requested CUDA unavailable; CPU fallback forbidden")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    random.seed(a.seed)
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(a.seed)
        torch.cuda.reset_peak_memory_stats(device)
    config = vars(a).copy()
    contract_path = os.environ["ME_CONTRACT_PATH"]
    selection = "last"
    if contract_path:
        contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
        selection = contract.get("primary_metric", {}).get("selection", "last")
    if selection not in ("last", "best"):
        raise ValueError("unsupported checkpoint selection")
    config["selection"] = selection
    network = model.build(a.task, a.dimension, a.width).to(device)
    optimizer = torch.optim.Adam(network.parameters(), lr=a.learning_rate)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=2, gamma=0.8)
    initial = state_copy(network)
    selected = None
    selected_epoch = 0
    best = -1.0
    events, source = [], None
    start_epoch, steps = 0, 0
    resume_path = os.environ.get("ME_RESUME_PATH")
    if resume_path:
        resume = Path(resume_path)
        checkpoint = torch.load(resume, map_location=device, weights_only=False)
        if checkpoint["config"] != config:
            raise ValueError("resume configuration mismatch")
        if checkpoint["device_type"] != device.type:
            raise ValueError("resume device mismatch")
        network.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        initial, selected, best = checkpoint["initial_model"], checkpoint["selected_model"], checkpoint["best"]
        selected_epoch = checkpoint["selection"]["selected_epoch"]
        start_epoch, steps = checkpoint["epoch"], checkpoint["optimizer_steps"]
        if start_epoch >= a.epochs:
            raise ValueError("checkpoint already complete")
        random.setstate(checkpoint["rng_python"])
        np.random.set_state(checkpoint["rng_numpy"])
        torch.set_rng_state(checkpoint["rng_torch"].cpu())
        if device.type == "cuda":
            torch.cuda.set_rng_state_all([v.cpu() for v in checkpoint["rng_cuda"]])
        source = {"path": str(resume.resolve()), "sha256": hashlib.sha256(resume.read_bytes()).hexdigest(),
                  "run_id": checkpoint["run_id"], "epoch": start_epoch}
        events = [dict(event, run_id=run_id, phase=phase, source_run_id=checkpoint["run_id"])
                  for event in checkpoint["events"]]
    # Train/validation only. This script never constructs the locked test split.
    train = synth_data.build_split(a.task, a.dimension, "train")
    val = synth_data.build_split(a.task, a.dimension, "val")
    x = torch.tensor(train["images"].copy(), device=device)
    y = torch.tensor(train["targets"].copy(), device=device)
    vx = torch.tensor(val["images"].copy(), device=device)
    criterion = torch.nn.CrossEntropyLoss() if a.task == "classification" else torch.nn.BCEWithLogitsLoss()
    metric = "accuracy" if a.task == "classification" else "dice"
    started = time.monotonic()
    with (out / "metrics.jsonl").open("w", encoding="utf-8") as log:
        for event in events:
            log.write(json.dumps(event) + "\n")
        log.flush()
        for epoch in range(start_epoch, a.epochs):
            network.train()
            for batch in sampler.batches(len(x), device):
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(network(x[batch]), y[batch])
                loss.backward()
                optimizer.step()
                steps += 1
            scheduler.step()
            prediction = model.predict(network, vx, a.task)
            metrics, _ = synth_data.evaluate(a.task, prediction, val["targets"], val["ids"])
            event = {"run_id": run_id, "phase": phase, "step": epoch, "metric": metric,
                     "value": metrics[metric], "time": datetime.now(timezone.utc).isoformat(),
                     "checkpoint_sha256": digest(network.state_dict())}
            events.append(event)
            log.write(json.dumps(event) + "\n")
            log.flush()
            if selection == "last" or metrics[metric] > best:
                selected = state_copy(network)
                selected_epoch = epoch + 1
            best = max(best, metrics[metric])
            checkpoint = {"format": 1, "run_id": run_id, "config": config, "device_type": device.type,
                "epoch": epoch + 1, "optimizer_steps": steps, "model": state_copy(network),
                "initial_model": initial, "selected_model": selected, "best": best, "events": events,
                "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                "rng_python": random.getstate(), "rng_numpy": np.random.get_state(),
                "rng_torch": torch.get_rng_state(),
                "rng_cuda": torch.cuda.get_rng_state_all() if device.type == "cuda" else [], "resume_source": source}
            checkpoint["sampler"] = sampler.state(epoch + 1, len(x))
            checkpoint["progress"] = {"completed_epochs": epoch + 1, "optimizer_steps": steps}
            checkpoint["selection"] = {"strategy": selection, "best_value": best, "selected_epoch": selected_epoch}
            atomic_save(out / "checkpoint.pt", checkpoint)
            if int(os.environ.get("ME_FIXTURE_INTERRUPT_AFTER_EPOCH", "-1")) == epoch + 1:
                print(f"fixture process interruption after durable epoch {epoch + 1}", flush=True)
                os._exit(75)
    network.load_state_dict(selected)
    final_predictions = model.predict(network, vx, a.task)
    metrics, cases = synth_data.evaluate(a.task, final_predictions, val["targets"], val["ids"])
    atomic_save(out / "weights.pt", {"config": config, "state_dict": selected})
    (out / "cases.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    changed = sum(int(not torch.equal(initial[k].cpu(), checkpoint["model"][k].cpu())) for k in initial)
    if changed == 0 or steps == 0:
        raise RuntimeError("no real parameter optimization occurred")
    proof = {"device": str(next(network.parameters()).device), "torch": torch.__version__,
        "python": sys.version, "python_executable": sys.executable, "torch_path": torch.__file__,
        "numpy": np.__version__, "numpy_path": np.__file__,
        "cuda_runtime": torch.version.cuda, "gpu_name": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "parameters": sum(p.numel() for p in network.parameters()), "changed_tensors": changed,
        "optimizer_steps": steps, "initial_sha256": digest(initial), "final_sha256": digest(checkpoint["model"]),
        "selected_sha256": digest(selected), "train_seconds": time.monotonic() - started,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(device) if device.type == "cuda" else 0,
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(device) if device.type == "cuda" else 0,
        "resume_source": source, "config": config}
    atomic_json(out / "training-proof.json", proof)
    atomic_json(out / "result.json", {"run_id": run_id, "phase": phase, "completed": True,
        "metrics": metrics, "artifacts": ["weights.pt", "checkpoint.pt", "cases.jsonl", "training-proof.json"]})
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
