"""Frozen locked-test evaluation script demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synth_data import simulate_eval


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()

    ckpt = json.loads((Path(args.run_dir) / 'model.json').read_text(encoding='utf-8'))
    res = simulate_eval(ckpt['model'], 'test', int(ckpt['seed']))

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / 'cases.jsonl').open('w', encoding='utf-8', newline='\n') as fh:
        for row in res['cases']:
            fh.write(json.dumps(row) + '\n')

    payload = {
        'metrics': {'bacc': res['bacc'], 'macro_f1': res['macro_f1']},
        'notes': f'locked test for model={ckpt["model"]}, seed={ckpt["seed"]}',
    }
    (out_dir / 'result.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
