"""FROZEN locked test. Load selected real weights; never optimize."""
import argparse
import json
from pathlib import Path
import os
import model
import synth_data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("classification", "segmentation"))
    p.add_argument("--dimension", type=int, required=True, choices=(2, 3))
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    torch = model.torch
    device = torch.device(os.environ["ME_DEVICE"])
    weights = torch.load(a.run_dir / "weights.pt", map_location=device, weights_only=True)
    config = weights["config"]
    if config["task"] != a.task or config["dimension"] != a.dimension:
        raise ValueError("weights task/dimension mismatch")
    network = model.build(a.task, a.dimension, config["width"]).to(device)
    network.load_state_dict(weights["state_dict"])
    part = synth_data.build_split(a.task, a.dimension, "test")
    prediction = model.predict(network, torch.tensor(part["images"].copy(), device=device), a.task)
    metrics, cases = synth_data.evaluate(a.task, prediction, part["targets"], part["ids"])
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / "cases.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    (a.output / "result.json").write_text(json.dumps({"completed": True, "metrics": metrics}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
