"""Explicit author/journal word limits; citation quotas are never word limits."""
import json
from pathlib import Path

SECTIONS = {'abstract', 'methods', 'results', 'introduction', 'discussion', 'legends'}


def load_limits(en_path, config=None):
    path = Path(config) if config is not None else None
    if path is None:
        for folder in Path(en_path).resolve().parents:
            if (folder / 'PROJECT.md').is_file():
                candidate = folder / 'writing-limits.json'
                path = candidate if candidate.is_file() else None
                break
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or set(data) - SECTIONS:
        raise ValueError('Word limits must map lowercase section names to min/max objects')
    for section, limits in data.items():
        if not isinstance(limits, dict) or not limits or set(limits) - {'min', 'max'}:
            raise ValueError('Invalid word limits for '+section)
        if any(type(n) is not int or n < 1 for n in limits.values()):
            raise ValueError('Word limits must be positive integers: '+section)
        if limits.get('min', 0) > limits.get('max', float('inf')):
            raise ValueError('Word limit minimum exceeds maximum: '+section)
    return data
