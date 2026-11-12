"""Rebuild local transcriptions, deterministic ESTIMATED points, and verbatim archives.

Run explicitly; replica.py only reads these inputs. Never trains a model.
"""
import csv
import hashlib
import json
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FEATURES = [
    ['Complexity_per_MW', 'Chi3v', 'SMR_VSA10', 'MR_per_MW', 'AromaticRing_Ratio',
     'Ketone', 'Kappa3', 'MinPartialCharge', 'Charge_Span', 'MolLogP', 'SlogP_VSA2',
     'BalabanJ', 'TPSA_x_LogP', 'MinAbsPartialCharge', 'FractionCSP3'],
    ['Complexity_per_MW', 'BertzCT', 'Ipc', 'Chi4v', 'Kappa_Anisotropy',
     'NumValenceElectrons', 'Chi3v', 'HallKierAlpha', 'MolWt', 'SlogP_VSA5',
     'BalabanJ', 'TPSA_x_LogP', 'LogP_TPSA', 'HalogenRatio', 'SMR_VSA7']]
VALUES = [[.1534, .1178, .1171, .0835, .0811, .0767, .0735, .0729, .0589,
           .0507, .0501, .0492, .0471, .0403, .0402],
          [.0965, .0908, .0682, .0628, .0442, .0406, .0388, .0284, .0279,
           .0241, .0199, .0174, .0173, .0169, .0161]]
# Separate visual transcription candidates, not normalized/recomputed bar values.
# Low-resolution ring labels remain uncertain (including apparent A/C rounding).
PERCENTS = [[13.8, 10.6, 10.5, 7.5, 7.3, 6.9, 6.6, 6.6, 5.3, 4.6, 4.5, 4.4, 4.2, 3.6, 3.6],
            [15.8, 14.9, 11.2, 10.3, 7.2, 6.7, 6.4, 4.7, 4.6, 4.0, 3.3, 2.9, 2.8, 2.8, 2.6]]

# Each row: (SHAP centre, spread, mixture weight, feature-value centre).
# These clusters describe visible positions/directions, never recovered observations.
CLUSTERS = [
    [[(-.07,.025,.70,.85),(.38,.07,.30,.05)], [(-.55,.07,.13,.03),(.05,.025,.87,.4)],
     [(-.30,.035,.20,.02),(.055,.020,.80,.85)], [(-.06,.035,.55,.9),(.17,.08,.45,.05)],
     [(-.07,.015,.55,.95),(.09,.045,.45,.05)], [(-.035,.015,.75,.12),(.22,.05,.25,.96)],
     [(-.035,.04,.65,.12),(.09,.05,.35,.24)], [(-.03,.03,.90,.08),(.07,.035,.10,.6)],
     [(-.13,.08,.13,.95),(.005,.03,.87,.5)], [(-.13,.015,.18,.15),(.045,.025,.82,.7)],
     [(-.12,.01,.10,.9),(.025,.025,.90,.24)], [(-.095,.02,.38,.12),(.025,.02,.62,.65)],
     [(-.055,.015,.18,.12),(.025,.025,.82,.75)], [(-.045,.025,.65,.75),(.008,.015,.35,.35)],
     [(-.07,.015,.35,.95),(.02,.007,.65,.1)]],
    [[(-.14,.015,.30,.95),(-.04,.025,.20,.7),(.085,.025,.50,.12)],
     [(-.055,.025,.55,.55),(.07,.04,.15,.2),(.165,.02,.30,.08)],
     [(-.055,.025,.65,.2),(.09,.04,.35,.03)], [(-.03,.03,.4,.55),(.075,.025,.6,.05)],
     [(-.04,.02,.85,.85),(.06,.01,.15,.2)], [(-.04,.015,.60,.8),(.06,.04,.40,.1)],
     [(-.035,.02,.55,.75),(.055,.04,.45,.15)], [(-.055,.025,.65,.12),(.025,.007,.35,.7)],
     [(-.01,.02,.35,.25),(.04,.015,.65,.9)], [(-.11,.035,.08,.95),(.012,.004,.92,.12)],
     [(-.02,.012,.35,.85),(.035,.012,.65,.15)], [(-.005,.005,.45,.65),(.018,.012,.55,.12)],
     [(-.007,.007,.30,.4),(.025,.013,.70,.15)], [(-.02,.01,.65,.15),(.018,.006,.35,.85)],
     [(-.02,.015,.65,.8),(.012,.005,.35,.12)]]]


def main():
    with (HERE / 'estimated_data.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['panel', 'feature', 'shap', 'percent', 'provenance', 'uncertain_reason'])
        for row, (bar, radial) in enumerate([('A', 'C'), ('D', 'F')]):
            for panel in (bar, radial):
                for i, (name, value, percent) in enumerate(zip(FEATURES[row], VALUES[row], PERCENTS[row])):
                    reason = 'ring percentage candidate from enlarged image; low-resolution digits/rounding need author confirmation'
                    if row == 0 and i == 1:
                        reason += '; A Chi3v candidate 0.1178 (0.1179 also plausible)'
                    if row == 1 and i == 0:
                        reason += '; D first label candidate 0.0965; F first percent candidate 15.8 (16.3 also plausible)'
                    writer.writerow([panel, name, f'{value:.4f}', f'{percent:.1f}', 'uncertain', reason])
    rng = np.random.default_rng(20261020)
    with (HERE / 'estimated_beeswarm.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['panel', 'feature', 'shap', 'feature_value', 'provenance'])
        for row, panel in enumerate('BE'):
            for feature, clusters in zip(FEATURES[row], CLUSTERS[row]):
                weights = np.array([c[2] for c in clusters])
                choices = rng.choice(len(clusters), size=180, p=weights / weights.sum())
                for idx in choices:
                    center, spread, _, feature_value = clusters[idx]
                    x = np.clip(rng.normal(center, spread / 2), *([-.64, .55] if row == 0 else [-.17, .205]))
                    color = np.clip(rng.normal(feature_value, .06), 0, 1)
                    writer.writerow([panel, feature, f'{x:.7f}', f'{color:.7f}', 'estimated'])
    source = ROOT / 'samples/post01/source/source.md'
    blocks = re.findall(rb'^```([^\r\n]*)\r?\n(.*?)^```', source.read_bytes(), flags=re.M | re.S)
    assert len(blocks) == 4
    folder = HERE / 'original_code'
    folder.mkdir(exist_ok=True)
    records = []
    for i, (language, body) in enumerate(blocks, 1):
        path = folder / f'code_block_{i:02}.{"py" if i == 1 else "txt"}'
        path.write_bytes(body)
        records.append({'file': path.name, 'fence_language': language.decode(),
                        'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body),
                        'original_code_provenance': 'example_not_target', 'execution': 'archived_only'})
    (folder / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print('prepared 60 uncertain transcription rows, 5400 estimated points; archived 4 verbatim blocks (not executed)')


if __name__ == '__main__':
    main()
