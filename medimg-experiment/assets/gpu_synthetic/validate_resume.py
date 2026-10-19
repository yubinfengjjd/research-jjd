"""FROZEN: validate trusted local full checkpoint; positional checkpoint output.

No optimization occurs. Pickle checkpoints must be from this local fixture.
Validation checks actual states rather than trusting a list of claimed fields.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parameter_digest(state):
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        h.update(key.encode())
        h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def validate(path):
    import numpy as np
    import model
    import sampler
    import synth_data
    torch = model.torch
    c = torch.load(path, map_location="cpu", weights_only=False)
    fields = []
    config = c["config"]
    require(isinstance(config["seed"], int) and config["task"] in ("classification", "segmentation")
            and config["dimension"] in (2, 3), "invalid configuration")
    require(isinstance(config["epochs"], int) and 1 <= config["epochs"] <= 32
            and isinstance(config["width"], int) and 1 <= config["width"] <= 16
            and config["selection"] in ("last", "best")
            and math.isfinite(config["learning_rate"]) and config["learning_rate"] > 0, "invalid training configuration")
    require(isinstance(c["run_id"], str) and bool(c["run_id"]), "missing source run ID")
    network = model.build(config["task"], config["dimension"], config["width"])
    network.load_state_dict(c["model"], strict=True)
    expected = network.state_dict()
    for name in ("model", "initial_model", "selected_model"):
        require(set(c[name]) == set(expected), f"{name} key mismatch")
        for key, tensor in c[name].items():
            require(isinstance(tensor, torch.Tensor) and tensor.shape == expected[key].shape and tensor.dtype == expected[key].dtype
                    and bool(torch.isfinite(tensor).all()), f"invalid {name} tensor")
    require(any(not torch.equal(c["model"][k], c["initial_model"][k]) for k in expected), "no optimized parameters")
    fields.append("model")
    epoch, steps = c["epoch"], c["optimizer_steps"]
    require(isinstance(epoch, int) and 0 < epoch < config["epochs"], "checkpoint must be incomplete at a positive epoch boundary")
    examples = len(synth_data.build_split(config["task"], config["dimension"], "train")["ids"])
    require(steps == epoch * ((examples + 3) // 4), "optimizer/progress mismatch")
    optimizer = c["optimizer"]
    reference_optimizer = torch.optim.Adam(network.parameters(), lr=config["learning_rate"])
    reference_scheduler = torch.optim.lr_scheduler.StepLR(reference_optimizer, step_size=2, gamma=0.8)
    expected_groups = reference_optimizer.state_dict()["param_groups"]
    for group in expected_groups:
        for _ in range(epoch // 2):
            group["lr"] *= 0.8
    require(optimizer["param_groups"] == expected_groups, "Adam param_groups/configuration mismatch")
    ids = [pid for group in optimizer["param_groups"] for pid in group["params"]]
    parameters = list(network.parameters())
    require(len(ids) == len(parameters) == len(optimizer["state"]), "incomplete optimizer state")
    for pid, param in zip(ids, parameters):
        state = optimizer["state"][pid]
        require(set(state) == {"step", "exp_avg", "exp_avg_sq"}, "Adam state fields mismatch")
        require(isinstance(state["step"], torch.Tensor) and state["step"].ndim == 0
                and state["step"].dtype == torch.float32 and bool(torch.isfinite(state["step"]))
                and state["step"].item() == steps, "Adam step mismatch")
        for key in ("exp_avg", "exp_avg_sq"):
            require(state[key].shape == param.shape and state[key].dtype == param.dtype
                    and bool(torch.isfinite(state[key]).all()), "invalid Adam moments")
        require(bool((state["exp_avg_sq"] >= 0).all()), "negative Adam second moment")
    fields.append("optimizer")
    sched = c["scheduler"]
    expected_scheduler = reference_scheduler.state_dict()
    expected_scheduler.update(last_epoch=epoch, _step_count=epoch + 1,
                              _last_lr=[group["lr"] for group in expected_groups])
    require(sched == expected_scheduler, "scheduler state/configuration mismatch")
    require(sched["last_epoch"] == epoch and sched["step_size"] == 2 and sched["gamma"] == 0.8, "invalid scheduler progress/config")
    require(sched["_last_lr"] == [g["lr"] for g in optimizer["param_groups"]], "scheduler/optimizer LR mismatch")
    fields.append("scheduler")
    random.Random().setstate(c["rng_python"])
    fields.append("rng_python")
    np.random.RandomState().set_state(c["rng_numpy"])
    fields.append("rng_numpy")
    torch.Generator(device="cpu").set_state(c["rng_torch"])
    fields.append("rng_torch")
    require(c["device_type"] in ("cpu", "cuda"), "unknown checkpoint device")
    if c["device_type"] == "cuda":
        require(torch.cuda.is_available() and len(c["rng_cuda"]) == torch.cuda.device_count(), "incomplete CUDA RNG")
        for device, state in enumerate(c["rng_cuda"]):
            torch.Generator(device=f"cuda:{device}").set_state(state)
    else:
        require(c["rng_cuda"] == [], "unexpected CUDA RNG")
    fields.append("rng_cuda")
    require(c["sampler"] == sampler.state(epoch, examples), "frozen sampler implementation/boundary mismatch")
    fields.append("sampler")
    require(c["progress"] == {"completed_epochs": epoch, "optimizer_steps": steps}, "progress state mismatch")
    fields.append("progress")
    events = c["events"]
    require(len(events) == epoch and [e["step"] for e in events] == list(range(epoch)), "incomplete metric history")
    values = [e["value"] for e in events]
    require(all(math.isfinite(v) and 0 <= v <= 1 for v in values), "invalid metric history values")
    selected_epoch = c["selection"]["selected_epoch"]
    expected_epoch = epoch if config["selection"] == "last" else values.index(max(values)) + 1
    require(c["selection"] == {"strategy": config["selection"], "best_value": max(values), "selected_epoch": expected_epoch}
            and selected_epoch == expected_epoch and c["best"] == max(values), "checkpoint selection mismatch")
    require(parameter_digest(c["selected_model"]) == events[selected_epoch - 1]["checkpoint_sha256"], "selected model differs from selected epoch parameters")
    require(parameter_digest(c["model"]) == events[-1]["checkpoint_sha256"], "current model differs from latest epoch parameters")
    if config["selection"] == "last":
        require(parameter_digest(c["selected_model"]) == parameter_digest(c["model"]), "last-selected model mismatch")
    fields.append("selection")
    fields.append("configuration")
    return {"compatible": True, "complete_state": True, "source_run_id": c["run_id"], "seed": config["seed"],
            "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "reason": "validated real parameter/Adam/scheduler/RNG states; frozen sampler resumes at completed epoch boundary",
            "fields": fields}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    try:
        result = validate(a.checkpoint)
    except Exception as error:
        result = {"compatible": False, "complete_state": False, "reason": str(error), "fields": []}
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
