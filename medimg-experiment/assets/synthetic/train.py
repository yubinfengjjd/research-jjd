"""Minimal-intrusion training script demo (writes result.json + checkpoint)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from synth_data import simulate_eval


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--epochs', type=int, default=10)
    p.add_argument('--output-dir', default=os.environ.get('ME_OUTPUT_DIR', '.'))
    p.add_argument('--fail', action='store_true')
    args = p.parse_args()

    if args.fail:
        print('Simulated OOM or training failure', flush=True)
        return 1

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = simulate_eval(args.model, 'val', args.seed)

    # Save a lightweight mock checkpoint so evaluate_test.py knows which model/seed ran
    ckpt = out_dir / 'model.json'
    ckpt.write_text(json.dumps({'model': args.model, 'seed': args.seed, 'epochs': args.epochs}) + '\n', encoding='utf-8')

    with (out_dir / 'cases.jsonl').open('w', encoding='utf-8', newline='\n') as fh:
        for row in res['cases']:
            fh.write(json.dumps(row) + '\n')

    payload = {
        'metrics': {'bacc': res['bacc'], 'macro_f1': res['macro_f1']},
        'artifacts': ['model.json', 'cases.jsonl'],
        'notes': f'model={args.model}, epochs={args.epochs}',
    }
    (out_dir / 'result.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
