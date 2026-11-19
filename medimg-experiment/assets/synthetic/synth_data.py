"""Minimal synthetic 3-class medical dataset for protocol verification (stdlib only)."""
from __future__ import annotations

import random

SPLITS = {
    'train': [f'P{i:03d}' for i in range(1, 61)],
    'val': [f'P{i:03d}' for i in range(61, 81)],
    'test': [f'P{i:03d}' for i in range(81, 101)],
}


def class_counts(split_name: str) -> dict[str, int]:
    ids = SPLITS[split_name]
    counts = {'class_0': 0, 'class_1': 0, 'class_2': 0}
    for idx, _ in enumerate(ids):
        counts[f'class_{idx % 3}'] += 1
    return counts


def simulate_eval(model: str, split: str, seed: int) -> dict:
    rng = random.Random(f'{model}:{split}:{seed}')
    base = {
        'baseline': 0.78,
        'proposed_v1': 0.75,   # Intentionally underperforms to exercise route revision
        'proposed_v2': 0.86,   # Improved route after revising plan
        'ablation_no_aux': 0.81,
    }.get(model, 0.76)
    jitter = rng.uniform(-0.012, 0.012)
    bacc = round(max(0.0, min(1.0, base + jitter)), 4)
    macro_f1 = round(max(0.0, min(1.0, bacc - 0.015 + rng.uniform(-0.005, 0.005))), 4)
    cases = []
    for idx, pid in enumerate(SPLITS[split]):
        # Per-case correctness indicator (optional cases.jsonl demo)
        correct = 1.0 if rng.random() < bacc else 0.0
        cases.append({'case_id': pid, 'label': idx % 3, 'value': correct})
    return {'bacc': bacc, 'macro_f1': macro_f1, 'cases': cases}
