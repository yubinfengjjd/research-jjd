"""Reload real weights, reproduce every group metric, and check full resume state."""
import argparse
import json
import os
import sys
from pathlib import Path
import model
import synth_data

torch = model.torch


def same(left, right):
    if isinstance(left, torch.Tensor):
        return isinstance(right, torch.Tensor) and torch.equal(left.cpu(), right.cpu())
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if isinstance(left, (tuple, list)):
        return len(left) == len(right) and all(same(x, y) for x, y in zip(left, right))
    if hasattr(left, "shape"):
        return bool((left == right).all())
    return left == right


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--test-dir", type=Path)
    p.add_argument("--audit", type=Path)
    p.add_argument("--compare-run", type=Path)
    p.add_argument("--resume-source", type=Path)
    p.add_argument("--evaluate-test", action="store_true")
    p.add_argument("--evidence-dir", type=Path)
    a = p.parse_args()
    run = a.run_dir
    evidence = a.evidence_dir or run
    evidence.mkdir(parents=True, exist_ok=True)
    checkpoint = torch.load(run / "checkpoint.pt", map_location="cpu", weights_only=False)
    weights = torch.load(run / "weights.pt", map_location="cpu", weights_only=True)
    config = weights["config"]
    task, dimension = config["task"], config["dimension"]
    metric = "accuracy" if task == "classification" else "dice"
    if a.evaluate_test:
        if a.test_dir is None:
            raise ValueError("--evaluate-test requires --test-dir")
        import evaluate_test
        prior_argv = sys.argv
        try:
            sys.argv = ["evaluate_test.py", "--task", task, "--dimension", str(dimension),
                        "--run-dir", str(run), "--output", str(a.test_dir)]
            evaluate_test.main()
        finally:
            sys.argv = prior_argv
    proof = json.loads((run / "training-proof.json").read_text())
    if os.environ.get("ME_TORCH_SITE"):
        assert Path(proof["torch_path"]).resolve() == (Path(os.environ["ME_TORCH_SITE"]) / "torch/__init__.py").resolve()
    if not proof["device"].startswith(os.environ["ME_DEVICE"]):
        raise AssertionError("claimed device differs from requested")
    network = model.build(task, dimension, config["width"]).to(os.environ["ME_DEVICE"])
    network.load_state_dict(weights["state_dict"])
    changes = sum(not torch.equal(checkpoint["initial_model"][k], checkpoint["model"][k]) for k in checkpoint["model"])
    assert changes == proof["changed_tensors"] > 0
    assert proof["optimizer_steps"] == 3 * config["epochs"] == checkpoint["optimizer_steps"]
    assert all(int(v["step"]) == checkpoint["optimizer_steps"] for v in checkpoint["optimizer"]["state"].values())
    assert checkpoint["scheduler"]["last_epoch"] == config["epochs"]
    assert same(weights["state_dict"], checkpoint["selected_model"])
    selected_index = checkpoint["selection"]["selected_epoch"] - 1
    selected_metric = checkpoint["events"][selected_index]["value"]
    assert json.loads((run / "result.json").read_text())["metrics"][metric] == selected_metric
    required = ("rng_python", "rng_numpy", "rng_torch", "rng_cuda", "config", "optimizer", "scheduler")
    assert all(k in checkpoint for k in required)
    audit = json.loads(a.audit.read_text()) if a.audit else None
    recomputed = {}
    for split, directory in (("val", run), ("test", a.test_dir)):
        if directory is None:
            continue
        part = synth_data.build_split(task, dimension, split)
        prediction = model.predict(network, torch.tensor(part["images"].copy(), device=os.environ["ME_DEVICE"]), task)
        metrics, actual = synth_data.evaluate(task, prediction, part["targets"], part["ids"])
        cases = [json.loads(line) for line in (directory / "cases.jsonl").read_text().splitlines()]
        result = json.loads((directory / "result.json").read_text())
        assert actual == cases, "saved predictions differ from reloaded model"
        assert synth_data.recompute_cases(task, cases) == result["metrics"][metric] == metrics[metric]
        if audit:
            assert {c["case_id"] for c in cases} == set(audit["splits"][split]["group_ids"])
        recomputed[split] = metrics
    recovery = None
    if a.compare_run:
        other = torch.load(a.compare_run / "checkpoint.pt", map_location="cpu", weights_only=False)
        other_weights = torch.load(a.compare_run / "weights.pt", map_location="cpu", weights_only=True)
        assert same(other_weights["state_dict"], other["selected_model"]), "fresh selected weights mismatch"
        assert (run / "cases.jsonl").read_text() == (a.compare_run / "cases.jsonl").read_text(), "fresh/resumed predictions differ"
        assert json.loads((run / "result.json").read_text())["metrics"] == json.loads((a.compare_run / "result.json").read_text())["metrics"]
        compared_keys = ("model", "selected_model", "initial_model", "selection", "sampler", "progress", "optimizer", "scheduler", "rng_python", "rng_numpy", "rng_torch", "rng_cuda", "config", "optimizer_steps", "epoch", "best", "device_type")
        for key in compared_keys:
            assert same(checkpoint[key], other[key]), f"recovery mismatch: {key}"
        normalize = lambda events: [{k: v for k, v in event.items() if k not in ("run_id", "phase", "time", "source_run_id")} for event in events]
        assert normalize(checkpoint["events"]) == normalize(other["events"]), "recovery mismatch: normalized events"
        assert checkpoint["resume_source"]["epoch"] == 2
        recovery = {"matches_fresh": str(a.compare_run), "fields": [*compared_keys, "events_normalized"]}
    if a.resume_source:
        import validate_resume
        valid = validate_resume.validate(a.resume_source)
        assert valid["compatible"] and valid["complete_state"]
        rejected = []
        for fault in ("missing-rng", "missing-adam-betas", "negative-adam-second-moment", "wrong-selected-model", "fractional-adam-step"):
            broken = torch.load(a.resume_source, map_location="cpu", weights_only=False)
            if fault == "missing-rng":
                del broken["rng_cuda"]
            elif fault == "missing-adam-betas":
                del broken["optimizer"]["param_groups"][0]["betas"]
            elif fault == "negative-adam-second-moment":
                next(iter(broken["optimizer"]["state"].values()))["exp_avg_sq"].fill_(-1)
            elif fault == "fractional-adam-step":
                next(iter(broken["optimizer"]["state"].values()))["step"].add_(0.5)
            else:
                broken["selected_model"] = broken["initial_model"]
            broken_path = evidence / f"checkpoint-{fault}.pt"
            torch.save(broken, broken_path)
            try:
                validate_resume.validate(broken_path)
            except (KeyError, ValueError) as error:
                rejected.append({"compatible": False, "reason": str(error), "fault": fault, "artifact": str(broken_path)})
            else:
                raise AssertionError(f"corrupt checkpoint was wrongly accepted: {fault}")
        (evidence / "invalid-checkpoint-validation.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    report = {"passed": True, "reloaded": True, "changed_tensors": changes,
              "optimizer_steps": proof["optimizer_steps"], "metrics": recomputed, "recovery": recovery,
              "frozen_test_invoked_in_process": a.evaluate_test}
    (evidence / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
