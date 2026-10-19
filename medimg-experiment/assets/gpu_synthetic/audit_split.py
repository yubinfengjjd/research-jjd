"""FROZEN grouped split audit, independent of torch/CUDA."""
import argparse
import json
from pathlib import Path
import synth_data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("classification", "segmentation"))
    p.add_argument("--dimension", required=True, type=int, choices=(2, 3))
    p.add_argument("--output", required=True)
    a = p.parse_args()
    splits = {}
    for split in ("train", "val", "test"):
        part = synth_data.build_split(a.task, a.dimension, split)
        splits[split] = {"group_ids": part["ids"], "class_counts":
                         {"0": len(part["ids"]) // 2, "1": len(part["ids"]) // 2}}
    Path(a.output).write_text(json.dumps({"group_unit": "patient", "splits": splits,
        "note": "generated synthetic groups, one image per group; no patient data"}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
