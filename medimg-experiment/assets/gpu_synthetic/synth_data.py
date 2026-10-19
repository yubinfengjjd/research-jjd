"""FROZEN synthetic groups and accuracy/Dice definitions. No patient data or I/O."""
import numpy as np


def build_split(task, dimension, split):
    if task not in ("classification", "segmentation") or dimension not in (2, 3):
        raise ValueError("unsupported task/dimension")
    offset, count = {"train": (0, 12), "val": (100, 4), "test": (200, 4)}[split]
    shape = (8,) * dimension
    images, targets, ids = [], [], []
    coordinates = np.indices(shape)
    for i in range(count):
        group = offset + i
        rng = np.random.default_rng(91000 + group + dimension * 1000)
        label = i % 2
        if task == "classification":
            target = label
            image = np.full(shape, 0.8 if label else -0.8) + rng.normal(0, 0.1, shape)
        else:
            center = np.array([3 + (group % 2)] * dimension)
            radius_squared = sum((coordinates[k] - center[k]) ** 2 for k in range(dimension))
            target = (radius_squared <= (2 + label * 0.3) ** 2).astype(np.float32)
            image = target * 1.6 - 0.8 + rng.normal(0, 0.1, shape)
            target = target[None]
        images.append(image[None])
        targets.append(target)
        ids.append(f"synthetic-{split}-{i:03d}")
    images = np.asarray(images, dtype=np.float32)
    targets = np.asarray(targets, dtype=np.int64 if task == "classification" else np.float32)
    images.flags.writeable = False
    targets.flags.writeable = False
    return {"images": images, "targets": targets, "ids": ids}


def evaluate(task, prediction, targets, ids):
    cases = []
    for case_id, pred, target in zip(ids, prediction, targets):
        if task == "classification":
            predicted = int(np.asarray(pred).item())
            truth = int(np.asarray(target).item())
            case = {"case_id": case_id, "label": truth, "prediction": predicted,
                    "value": float(predicted == truth)}
        else:
            predicted = np.asarray(pred, dtype=np.uint8).reshape(-1)
            truth = np.asarray(target, dtype=np.uint8).reshape(-1)
            denominator = int(predicted.sum()) + int(truth.sum())
            value = 2 * int((predicted * truth).sum()) / denominator if denominator else 1.0
            case = {"case_id": case_id, "shape": list(target.shape), "label": truth.tolist(),
                    "prediction": predicted.tolist(), "value": value}
        cases.append(case)
    metric = "accuracy" if task == "classification" else "dice"
    return {metric: float(np.mean([c["value"] for c in cases]))}, cases


def recompute_cases(task, cases):
    values = []
    for c in cases:
        if task == "classification":
            value = float(c["label"] == c["prediction"])
        else:
            prediction = np.asarray(c["prediction"], dtype=np.uint8)
            label = np.asarray(c["label"], dtype=np.uint8)
            denominator = int(prediction.sum()) + int(label.sum())
            value = 2 * int((prediction * label).sum()) / denominator if denominator else 1.0
        if abs(value - c["value"]) > 1e-12:
            raise ValueError("case metric does not match predictions")
        values.append(value)
    return float(np.mean(values))
