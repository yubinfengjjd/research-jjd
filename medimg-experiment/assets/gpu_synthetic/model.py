"""Tiny real Conv2D/Conv3D networks; no pretrained models."""
from torch_runtime import load_torch

torch = load_torch()


def build(task, dimension, width=4):
    conv = torch.nn.Conv2d if dimension == 2 else torch.nn.Conv3d
    if task == "classification":
        pool = torch.nn.AdaptiveAvgPool2d if dimension == 2 else torch.nn.AdaptiveAvgPool3d
        return torch.nn.Sequential(conv(1, width, 3, padding=1), torch.nn.ReLU(),
                                   pool(1), torch.nn.Flatten(), torch.nn.Linear(width, 2))
    return torch.nn.Sequential(conv(1, width, 3, padding=1), torch.nn.ReLU(), conv(width, 1, 1))


def predict(network, images, task):
    network.eval()
    with torch.no_grad():
        logits = network(images)
        result = logits.argmax(1) if task == "classification" else (logits >= 0).to(torch.uint8)
    return result.cpu().numpy()
