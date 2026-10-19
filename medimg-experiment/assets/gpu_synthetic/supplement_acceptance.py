"""Bounded acceptance continuation, not a controller or training entry point.

Parent must run this whole process with a <=90-second external timeout. Sharing
one torch import avoids repeating Windows DLL/CUDA startup for tiny operations.
All existing sources are read only; reused results undergo actual re-evaluation.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    began = time.monotonic()
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    source, out = a.source.resolve(), a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    asset = Path(__file__).resolve().parent
    provenance = json.loads((source / "source-before-validator-correction.json").read_text())
    unchanged = ("model.py", "train.py", "synth_data.py", "sampler.py", "torch_runtime.py", "audit_split.py", "evaluate_test.py")
    for name in unchanged:
        if provenance["sha256"][name] != sha(asset / name):
            raise RuntimeError(f"cannot reuse changed training/evaluation source: {name}")
    import audit_split
    import train
    import validate_resume
    import verify_run
    current_source_hashes = {p.name: sha(p) for p in asset.glob("*.py")}
    operations = []

    def record(value):
        operations.append(value)
        (out / "operations.json").write_text(json.dumps(operations, indent=2), encoding="utf-8")

    def call(module, args, run, contract, extra=None, log_dir=None):
        if time.monotonic() - began >= 85:
            raise RuntimeError("supplement internal85-second budget exhausted")
        old_argv, old_env = sys.argv, os.environ.copy()
        target = log_dir or run
        target.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        try:
            os.environ.update(ME_RUN_ID=run.name, ME_PHASE="matrix", ME_OUTPUT_DIR=str(run),
                              ME_DEVICE="cuda", ME_CONTRACT_PATH=str(contract), PYTHONDONTWRITEBYTECODE="1")
            os.environ.pop("ME_RESUME_PATH", None)
            os.environ.pop("ME_FIXTURE_INTERRUPT_AFTER_EPOCH", None)
            if extra:
                os.environ.update(extra)
            sys.argv = [module.__file__, *map(str, args)]
            with (target / (Path(module.__file__).stem + ".log")).open("w", encoding="utf-8") as log:
                with redirect_stdout(log), redirect_stderr(log):
                    module.main()
        finally:
            sys.argv = old_argv
            os.environ.clear()
            os.environ.update(old_env)
        record({"operation": Path(module.__file__).name, "argv": list(map(str, args)),
                "run": str(run), "wall_seconds": time.monotonic() - start})

    contracts = {}
    for selection in ("last", "best"):
        contracts[selection] = out / f"contract-{selection}.json"
        contracts[selection].write_text(json.dumps({"primary_metric": {"selection": selection}}), encoding="utf-8")
    commands = json.loads((source / "commands.json").read_text())
    matrix = []
    for task in ("classification", "segmentation"):
        for dimension in (2, 3):
            prefix = f"{task}-{dimension}d"
            audit_dir = out / f"{prefix}-audit"
            call(audit_split, ["--task", task, "--dimension", dimension, "--output", audit_dir / "audit.json"],
                 audit_dir, contracts["last"])
            audit_path = audit_dir / "audit.json"
            runs = {}
            values = []

            def obtain(seed, selection):
                name = f"{prefix}-seed{seed}" if selection == "last" else f"{prefix}-best-seed{seed}"
                prior = source / name
                expected = {"task": task, "dimension": dimension, "seed": seed, "epochs": 4,
                            "width": 4, "learning_rate": 0.03, "selection": selection}
                reused = False
                if (prior / "result.json").is_file() and (prior / "training-proof.json").is_file():
                    proof = json.loads((prior / "training-proof.json").read_text())
                    if proof["config"] == expected:
                        run = prior
                        reused = True
                if not reused:
                    run = out / name
                    call(train, ["--task", task, "--dimension", dimension, "--seed", seed, "--epochs", 4], run, contracts[selection])
                actual_weights = train.torch.load(run / "weights.pt", map_location="cpu", weights_only=True)
                if actual_weights["config"] != expected:
                    raise RuntimeError("actual weight configuration differs from reused/requested run")
                evidence = out / f"{name}-revalidation"
                old_test = source / f"{name}-test"
                test = old_test if (old_test / "result.json").is_file() else out / f"{name}-test"
                args = ["--run-dir", run, "--test-dir", test, "--audit", audit_path, "--evidence-dir", evidence]
                if not (test / "result.json").is_file():
                    args.append("--evaluate-test")
                call(verify_run, args, run, contracts[selection], log_dir=evidence)
                record({"disposition": "reused_after_actual_weight_prediction_metric_verification" if reused else "new_real_training",
                        "run": str(run), "config": expected, "weights_sha256": sha(run / "weights.pt"),
                        "checkpoint_sha256": sha(run / "checkpoint.pt"), "verification": str(evidence / "verification.json")})
                return run

            for seed in (11, 22, 33):
                runs[(seed, "last")] = obtain(seed, "last")
                result = json.loads((runs[(seed, "last")] / "result.json").read_text())
                values.append(next(iter(result["metrics"].values())))
            for selection in ("last", "best"):
                fresh = runs[(11, "last")] if selection == "last" else obtain(11, "best")
                interrupted = source / f"{prefix}-{selection}-interrupted"
                recorded_exit = any(c.get("exit_code") == 75 and c.get("output") == str(interrupted) for c in commands)
                if not recorded_exit:
                    interrupted = out / f"{prefix}-{selection}-interrupted"
                    interrupted.mkdir()
                    env = os.environ.copy()
                    env.update(ME_RUN_ID=interrupted.name, ME_PHASE="matrix", ME_OUTPUT_DIR=str(interrupted), ME_DEVICE="cuda",
                               ME_CONTRACT_PATH=str(contracts[selection]), ME_FIXTURE_INTERRUPT_AFTER_EPOCH="2", PYTHONDONTWRITEBYTECODE="1")
                    env.pop("ME_RESUME_PATH", None)
                    remaining = 85 - (time.monotonic() - began)
                    if remaining <= 5:
                        raise RuntimeError("supplement budget insufficient for an owned interruption")
                    start = time.monotonic()
                    cp = subprocess.run([sys.executable, "-X", "utf8", str(asset / "train.py"), "--task", task,
                                         "--dimension", str(dimension), "--seed", "11", "--epochs", "4"],
                                        env=env, capture_output=True, text=True, timeout=min(30, remaining - 5))
                    (interrupted / "interruption.log").write_text(cp.stdout + cp.stderr, encoding="utf-8")
                    record({"operation": "actual_owned_process_interruption", "exit_code": cp.returncode,
                            "run": str(interrupted), "wall_seconds": time.monotonic() - start})
                    if cp.returncode != 75:
                        raise RuntimeError("expected owned interrupted process exit75")
                validation = validate_resume.validate(interrupted / "checkpoint.pt")
                if validation["seed"] != 11 or validation["source_run_id"] != interrupted.name:
                    raise RuntimeError("source checkpoint identity mismatch")
                report = out / f"{prefix}-{selection}-validation.json"
                report.write_text(json.dumps(validation, indent=2), encoding="utf-8")
                resumed = source / f"{prefix}-{selection}-resumed"
                reused = (resumed / "result.json").is_file()
                if not reused:
                    resumed = out / f"{prefix}-{selection}-resumed"
                    call(train, ["--task", task, "--dimension", dimension, "--seed", 11, "--epochs", 4], resumed,
                         contracts[selection], {"ME_RESUME_PATH": str(interrupted / "checkpoint.pt")})
                evidence = out / f"{prefix}-{selection}-recovery-revalidation"
                call(verify_run, ["--run-dir", resumed, "--compare-run", fresh, "--resume-source", interrupted / "checkpoint.pt",
                                 "--audit", audit_path, "--evidence-dir", evidence], resumed, contracts[selection], log_dir=evidence)
                record({"disposition": "reused_after_complete_state_and_actual_prediction_verification" if reused else "new_real_resume",
                        "run": str(resumed), "source_checkpoint": str(interrupted / "checkpoint.pt"),
                        "checkpoint_sha256": sha(interrupted / "checkpoint.pt"), "verification": str(evidence / "verification.json")})
            matrix.append({"cell": prefix, "seeds": [11, 22, 33], "values": values,
                           "mean": statistics.mean(values), "sample_std": statistics.stdev(values)})
    summary = {"passed": True, "device": "cuda", "formal_seeds": [11, 22, 33], "cells": 4,
        "recovery_selections": ["last", "best"], "matrix": matrix, "source": str(source),
        "unchanged_source_hashes": {name: sha(asset / name) for name in unchanged},
        "validator_before_sha256": provenance["sha256"]["validate_resume.py"],
        "validator_after_sha256": sha(asset / "validate_resume.py"),
        "validator_change": "finite exact Adam step equality; no prediction/metric/training change",
        "elapsed_seconds": time.monotonic() - began,
        "scope": "actual synthetic CUDA executable/recovery behavior only; no scientific or clinical validity"}
    if current_source_hashes != {p.name: sha(p) for p in asset.glob("*.py")}:
        raise RuntimeError("acceptance sources changed during bounded continuation")
    (out / "acceptance.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
