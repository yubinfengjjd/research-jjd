"""Actual CUDA acceptance, with a 900-second total and 90-second child cap.

Use the confirmed interpreter with -X utf8 tests/run_gpu_acceptance.py.
Set ME_TORCH_SITE to an explicitly approved cp312 dependency directory first.
No fallback to CPU, downloaded weights, or fabricated review identities.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets/gpu_synthetic"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/gpu-acceptance")
    parser.add_argument("--budget-seconds", type=float, default=900)
    parser.add_argument("--cells", nargs="+", choices=("classification-2d", "classification-3d", "segmentation-2d", "segmentation-3d"),
                        default=["classification-2d", "classification-3d", "segmentation-2d", "segmentation-3d"])
    parser.add_argument("--supplement-from", type=Path)
    a = parser.parse_args()
    if not 1 <= a.budget_seconds <= 900:
        raise ValueError("acceptance budget must be within 1..900 seconds")
    dependency_site = Path(os.environ["ME_TORCH_SITE"]).resolve(strict=True)
    a.output = a.output.resolve()
    if a.supplement_from:
        start = time.monotonic()
        argv = [sys.executable, "-X", "utf8", str(ASSET / "supplement_acceptance.py"),
                "--source", str(a.supplement_from.resolve()), "--output", str(a.output)]
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            output, _ = process.communicate(timeout=min(90, a.budget_seconds))
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            else:
                process.kill()
            output, _ = process.communicate()
            a.output.parent.joinpath(a.output.name + ".log").write_text(output, encoding="utf-8")
            raise
        a.output.parent.joinpath(a.output.name + ".log").write_text(output, encoding="utf-8")
        launcher = {"argv": argv, "pid": process.pid, "exit_code": process.returncode,
                    "wall_seconds": time.monotonic() - start, "external_timeout_seconds": min(90, a.budget_seconds)}
        a.output.parent.joinpath(a.output.name + "-launcher.json").write_text(json.dumps(launcher, indent=2), encoding="utf-8")
        if process.returncode:
            raise RuntimeError("supplement failed: see preserved launcher log")
        print(a.output / "acceptance.json")
        return
    a.output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    contracts = {}
    for selection in ("last", "best"):
        contracts[selection] = a.output / f"fixture-contract-{selection}.json"
        contracts[selection].write_text(json.dumps({"primary_metric": {"selection": selection},
            "scope_note": "synthetic protocol acceptance only; not human review or scientific acceptance"}), encoding="utf-8")
    frozen = ("synth_data.py", "audit_split.py", "evaluate_test.py", "torch_runtime.py", "sampler.py", "validate_resume.py")
    hashes = {name: hashlib.sha256((ASSET / name).read_bytes()).hexdigest() for name in frozen}
    results = []

    def invoke(script, args, output, phase="matrix", resume=None, selection="last"):
        remaining = a.budget_seconds - (time.monotonic() - began)
        if remaining <= 0:
            raise RuntimeError("GPU acceptance budget exhausted")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("ME_FIXTURE_INTERRUPT_AFTER_EPOCH", None)
        env.update(ME_RUN_ID=output.name, ME_PHASE=phase, ME_OUTPUT_DIR=str(output), ME_DEVICE="cuda",
                   ME_CONTRACT_PATH=str(contracts[selection]))
        if resume:
            env["ME_RESUME_PATH"] = str(resume)
        else:
            env.pop("ME_RESUME_PATH", None)
        output.mkdir(parents=True, exist_ok=True)
        (output / "cache").mkdir(exist_ok=True)
        env.update(TMP=str(output), TEMP=str(output), TORCH_HOME=str(output / "cache"),
                   CUDA_CACHE_PATH=str(output / "cache"), WANDB_MODE="disabled")
        start = time.monotonic()
        cp = subprocess.run([sys.executable, "-X", "utf8", str(ASSET / script), *map(str, args)],
                            cwd=ASSET, env=env, text=True, capture_output=True, timeout=min(90, remaining))
        (output / (script + ".log")).write_text(cp.stdout + cp.stderr, encoding="utf-8")
        record = {"script": script, "argv": args, "exit_code": cp.returncode,
                  "wall_seconds": time.monotonic() - start, "output": str(output)}
        results.append(record)
        (a.output / "commands.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        if cp.returncode:
            raise RuntimeError(f"{script} failed: see {output}")

    for task in ("classification", "segmentation"):
        for dimension in (2, 3):
            prefix = f"{task}-{dimension}d"
            if prefix not in a.cells:
                continue
            audit_dir = a.output / (prefix + "-audit")
            invoke("audit_split.py", ["--task", task, "--dimension", dimension,
                    "--output", str(audit_dir / "audit.json")], audit_dir)
            for seed in (11, 22, 33):
                run = a.output / f"{prefix}-seed{seed}"
                invoke("train.py", ["--task", task, "--dimension", dimension, "--seed", seed, "--epochs", 4], run)
                test = a.output / f"{prefix}-seed{seed}-test"
                verify_args = ["--run-dir", str(run), "--test-dir", str(test), "--audit", str(audit_dir / "audit.json")]
                if task == "classification" and dimension == 2 and seed == 11:
                    invoke("evaluate_test.py", ["--task", task, "--dimension", dimension,
                            "--run-dir", str(run), "--output", str(test)], test, "test")
                else:
                    verify_args.append("--evaluate-test")
                invoke("verify_run.py", verify_args, run)
            for selection in ("last", "best"):
                fresh = a.output / f"{prefix}-seed11"
                if selection == "best":
                    fresh = a.output / f"{prefix}-best-seed11"
                    invoke("train.py", ["--task", task, "--dimension", dimension, "--seed", 11, "--epochs", 4],
                           fresh, selection=selection)
                interrupted = a.output / f"{prefix}-{selection}-interrupted"
                interrupted.mkdir()
                env = os.environ.copy()
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                env.pop("ME_RESUME_PATH", None)
                env.update(ME_RUN_ID=interrupted.name, ME_PHASE="matrix", ME_OUTPUT_DIR=str(interrupted),
                           ME_DEVICE="cuda", ME_FIXTURE_INTERRUPT_AFTER_EPOCH="2", ME_CONTRACT_PATH=str(contracts[selection]))
                (interrupted / "cache").mkdir()
                env.update(TMP=str(interrupted), TEMP=str(interrupted), TORCH_HOME=str(interrupted / "cache"),
                           CUDA_CACHE_PATH=str(interrupted / "cache"), WANDB_MODE="disabled")
                remaining = a.budget_seconds - (time.monotonic() - began)
                if remaining <= 0:
                    raise RuntimeError("GPU acceptance budget exhausted")
                interrupt_started = time.monotonic()
                cp = subprocess.run([sys.executable, "-X", "utf8", str(ASSET / "train.py"), "--task", task,
                                     "--dimension", str(dimension), "--seed", "11", "--epochs", "4"],
                                    cwd=ASSET, env=env, capture_output=True, text=True, timeout=min(90, remaining))
                (interrupted / "interruption.log").write_text(cp.stdout + cp.stderr, encoding="utf-8")
                results.append({"script": "train.py", "selection": selection, "fault_injection": "actual process exit after durable epoch2",
                                "exit_code": cp.returncode, "wall_seconds": time.monotonic() - interrupt_started, "output": str(interrupted)})
                (a.output / "commands.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                if cp.returncode != 75:
                    raise RuntimeError(f"expected actual interrupted exit 75, got {cp.returncode}")
                invoke("validate_resume.py", [str(interrupted / "checkpoint.pt"), str(interrupted / "resume-validation.json")], interrupted, selection=selection)
                validation = json.loads((interrupted / "resume-validation.json").read_text())
                if not validation["compatible"] or not validation["complete_state"]:
                    raise RuntimeError(f"actual interrupted checkpoint failed validation: {validation}")
                resumed = a.output / f"{prefix}-{selection}-resumed"
                invoke("train.py", ["--task", task, "--dimension", dimension, "--seed", 11, "--epochs", 4],
                       resumed, resume=interrupted / "checkpoint.pt", selection=selection)
                invoke("verify_run.py", ["--run-dir", str(resumed), "--compare-run", str(fresh),
                        "--resume-source", str(interrupted / "checkpoint.pt"), "--audit", str(audit_dir / "audit.json")], resumed, selection=selection)
    assert hashes == {name: hashlib.sha256((ASSET / name).read_bytes()).hexdigest() for name in frozen}
    (a.output / "acceptance.json").write_text(json.dumps({"passed": True, "device": "cuda", "formal_seeds": [11, 22, 33],
        "cells": len(a.cells), "requested_cells": a.cells, "budget_seconds": a.budget_seconds, "dependency_site": str(dependency_site), "recovery_selections": ["last", "best"], "frozen_sha256": hashes, "elapsed_seconds": time.monotonic() - began,
        "scope": "synthetic executable behavior only; no scientific or clinical validity"}, indent=2), encoding="utf-8")
    print(a.output / "acceptance.json")


if __name__ == "__main__":
    main()
