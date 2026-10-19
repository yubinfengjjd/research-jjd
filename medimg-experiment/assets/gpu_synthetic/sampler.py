"""FROZEN epoch-boundary sampler: resume RNG is restored before this function."""
import hashlib
from pathlib import Path
from torch_runtime import load_torch


def batches(examples, device):
    torch = load_torch()
    yield from torch.randperm(examples, device=device).split(4)


def state(completed_epochs, examples):
    return {"scheme": "epoch-boundary-torch-randperm", "batch_size": 4, "examples": examples,
            "next_epoch": completed_epochs, "cursor": 0,
            "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
