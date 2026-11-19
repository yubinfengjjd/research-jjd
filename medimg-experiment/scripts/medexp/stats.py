"""Metric aggregation and optional case-level paired bootstrap CI (stdlib only)."""
from __future__ import annotations

import json
import math
from pathlib import Path
import random
import statistics

from .common import number, require, safe_path


def aggregate(values: list[float], mode: str = 'mean', higher: bool = True) -> float:
    require(bool(values), '聚合值列表不能为空')
    if mode == 'mean':
        return statistics.fmean(values)
    if mode == 'median':
        return statistics.median(values)
    if mode == 'worst':
        return min(values) if higher else max(values)
    raise ValueError(f'unsupported aggregation mode: {mode}')


def seed_sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def read_cases(path: Path, statistic: str) -> dict:
    p = safe_path(path)
    require(p.is_file(), f'逐病例记录不存在: {p}')
    cases = {}
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cid = item.get('case_id')
        require(isinstance(cid, str) and cid, 'cases.jsonl 缺少 case_id')
        require(cid not in cases, f'cases.jsonl 存在重复 case_id: {cid}')
        if statistic == 'mean_per_case':
            cases[cid] = number(item.get('value'), '逐病例 value')
        else:
            require(item.get('label') in (0, 1), 'binary_auroc 逐病例 label 必须为 0/1')
            cases[cid] = (item['label'], number(item.get('score'), '逐病例 score'))
    require(bool(cases), 'cases.jsonl 为空')
    return cases


def auroc(pairs: list[tuple[int, float]]) -> float | None:
    ordered = sorted(pairs, key=lambda x: x[1])
    ranks = [0.0] * len(ordered)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    pos = sum(1 for label, _ in ordered if label == 1)
    neg = len(ordered) - pos
    if pos == 0 or neg == 0:
        return None
    rank_sum = sum(r for r, (label, _) in zip(ranks, ordered) if label == 1)
    return (rank_sum - pos * (pos + 1) / 2.0) / (pos * neg)


def compute(statistic: str, cases: dict, ids: list[str]) -> float | None:
    if statistic == 'mean_per_case':
        return statistics.fmean(cases[i] for i in ids)
    return auroc([cases[i] for i in ids])


def paired_bootstrap(statistic: str, runs_a: list[dict], runs_b: list[dict],
                     higher: bool, resamples: int = 1000, level: float = 0.95,
                     seed: int = 42, mode: str = 'mean') -> dict:
    ids = sorted(runs_a[0])
    for r in runs_a + runs_b:
        require(sorted(r) == ids, '配对比较要求所有运行包含完全一致的病例集合')
    if statistic == 'binary_auroc':
        for r in runs_a + runs_b:
            require(all(r[i][0] == runs_a[0][i][0] for i in ids), '配对比较的病例标签不一致')

    def effect(sample: list[str]) -> float | None:
        a_vals = [compute(statistic, r, sample) for r in runs_a]
        b_vals = [compute(statistic, r, sample) for r in runs_b]
        if any(v is None for v in a_vals + b_vals):
            return None
        a = aggregate(a_vals, mode=mode, higher=higher)
        b = aggregate(b_vals, mode=mode, higher=higher)
        return (a - b) if higher else (b - a)

    point = effect(ids)
    require(point is not None, '无法在完整病例集上计算配对效应')
    rng = random.Random(seed)
    draws, skipped = [], 0
    for _ in range(resamples):
        sample = [ids[rng.randrange(len(ids))] for _ in ids]
        e = effect(sample)
        if e is None:
            skipped += 1
        else:
            draws.append(e)
    require(skipped <= resamples * 0.1, 'bootstrap 重采样中单一类别过多，无法稳定估计区间')
    draws.sort()
    alpha = (1.0 - level) / 2.0
    lo = draws[max(0, math.floor(alpha * len(draws)))]
    hi = draws[min(len(draws) - 1, math.ceil((1.0 - alpha) * len(draws)) - 1)]
    return {
        'effect': point,
        'ci_low': lo,
        'ci_high': hi,
        'level': level,
        'cases': len(ids),
        'resamples': resamples,
        'skipped_resamples': skipped,
        'seeds_a': len(runs_a),
        'seeds_b': len(runs_b),
    }
