"""Synthetic patient-level split audit demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synth_data import SPLITS, class_counts


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--inject-leak', action='store_true')
    args = p.parse_args()

    splits = {
        name: {'group_ids': list(ids), 'class_counts': class_counts(name)}
        for name, ids in SPLITS.items()
    }
    if args.inject_leak:
        splits['val']['group_ids'].append(splits['train']['group_ids'][0])

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'group_unit': 'patient_id', 'splits': splits}, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
