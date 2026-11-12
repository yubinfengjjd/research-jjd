"""B-only deterministic visual demonstration data; never original SHAP samples.

T2 F2 doubles the previous mixture counts to 192 points per feature. Mixture
ranges/color intervals retain the T2 bounded approximation; only density changes.
This helper writes only its sibling CSV, never samples or the A/C examples.
"""
import csv
from pathlib import Path

import numpy as np

FEATURES = ['VSS/TSS', 'ana-time', 'infS', 'pH', 'MLSS', 'infP', 'salinity',
            'infC', 'MLVSS', 'infAc', 'infpro', 'T', 'volume']
# (base count, SHAP low, SHAP high, color low, color high); counts are
# constructed visual-density choices, not recovered sample sizes.
MIXTURES = [
    [(40,-22,-14,.88,1),(28,-3,8,.58,.73),(24,30,42,0,.22),(4,10,28,.1,.5)],
    [(20,-14,-12,0,.15),(24,-10,-1,.05,.35),(16,-1,3,.4,.7),(36,3,10,.8,1)],
    [(20,-7,-5,.25,.4),(30,-3,0,.2,.5),(34,2,5,.6,.8),(12,5,9,.7,.85)],
    [(28,-5,-3,.25,.4),(28,-1.1,-.6,.85,1),(32,1,4,0,.12),(8,4,7,0,.15)],
    [(30,-4,-1,.2,.4),(30,-1,1,.35,.55),(30,1,3,.75,1),(6,3,9,.6,.75)],
    [(28,-7,-1,.85,1),(42,-1,1,.2,.6),(20,1,8,.6,.76),(6,-11,-7,.75,1)],
    [(12,-10,-7,.85,1),(44,-1.8,0,.6,.7),(40,.5,2,.1,.3)],
    [(34,-2,0,.7,1),(26,-.5,3,.55,.7),(28,2,3,0,.2),(8,-5,-2,.1,.9)],
    [(14,-5,-3,0,.2),(46,-1,1,.25,.7),(28,0,2,.55,.75),(8,3,9,.8,1)],
    [(18,-4,-2,0,.2),(46,-1,1,.2,.6),(32,1,5,.8,1)],
    [(38,-2,0,0,.22),(30,-.5,.5,.15,.5),(28,.5,3,.55,.72)],
    [(58,-1,0,.85,1),(38,.5,1.5,0,.2)],
    [(68,-1,0,0,1),(28,0,.5,0,.2)],
]


def main():
    rng = np.random.default_rng(20261020)
    output = Path(__file__).resolve().with_name('estimated_data.csv')
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['panel', 'feature', 'sample', 'shap', 'feature_value', 'provenance', 'uncertain_reason'])
        for feature, mixture in zip(FEATURES, MIXTURES):
            sample = 0
            for base_count, low, high, cmin, cmax in mixture:
                count = 2 * base_count
                xs = low + (high - low) * rng.beta(2, 2, count)
                colors = rng.uniform(cmin, cmax, count)
                for x, color in zip(xs, colors):
                    sample += 1
                    writer.writerow(['B', feature, sample, f'{x:.5f}', f'{color:.5f}', 'estimated',
                                     'synthetic visual approximation; density and color not original samples'])
    print(f'B=13x192=2496 synthetic points; provenance=estimated -> {output}')


if __name__ == '__main__':
    main()
