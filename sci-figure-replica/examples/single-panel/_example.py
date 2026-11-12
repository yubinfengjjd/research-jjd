"""Shared local example export; imports only staged templates/scripts."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / 'templates'))
sys.path.insert(0, str(SKILL / 'scripts'))
from common import atomic_write, json_bytes, sha256, utc_now
from make_compare import main as compare
from python_style import apply_style, save_figure, shap_cmap, SHAP_MAX, SHAP_STOPS


def render(name, folder, argv=None):
    parser = argparse.ArgumentParser(description=f'Reconstructed {name}; data estimated, never original samples')
    parser.add_argument('--out', type=Path, default=folder, help='Output root, defaults to this example')
    args = parser.parse_args(argv)
    number = {'bar_inset': '06', 'beeswarm': '07', 'radial': '08'}[name]
    original = SKILL / f'samples/post01/source/article_images/img{number}.png'
    with Image.open(original) as image:
        width, height = image.size
    font = apply_style()
    df = pd.read_csv(folder / 'estimated_data.csv')
    # Preserve the visible spelling while keeping the canonical CSV feature key.
    df['display_feature'] = df['feature'].replace({'volume': 'volumn'})
    figwidth = 4.5 if name != 'radial' else 3.1
    figsize = (figwidth, figwidth * height / width)
    fig = plt.figure(figsize=figsize)
    if name == 'bar_inset':
        from shap_bar import draw_shap_bar
        calibration = json.loads((folder / 'color_calibration.json').read_text(encoding='utf-8'))
        ax = fig.add_axes([.166, .099, .689, .886])
        result = draw_shap_bar(ax, df, feature_col='display_feature', value_col='shap', percent_col='percent',
                               cmap=shap_cmap(), inset_bounds=(-.115, .025, .63, .57),
                               value_color_positions=calibration['value_color_positions'])
    elif name == 'beeswarm':
        from beeswarm import draw_beeswarm
        ax = fig.add_axes([.008, .095, .984, .893])
        result = draw_beeswarm(ax, df, feature_order=df['feature'].drop_duplicates().tolist(), cmap=shap_cmap(),
                               xlim=(-25.5, 43.5), point_size=5.5, jitter=.30,
                               cbar_bounds=None)
    else:
        from radial_bar import draw_radial
        ax = fig.add_axes([-.08, -.05, 1.16, .96], projection='polar')
        result = draw_radial(ax, df, value_col='shap', percent_col='percent', label_col='display_feature', cmap=shap_cmap())
    paths = save_figure(fig, args.out / 'output/replica')
    source_hash = sha256(original)
    spec = {'name': name, 'status': 'review', 'code_provenance': 'reconstructed', 'data_provenance': 'estimated',
            'source_image': str(original), 'source_image_sha256': source_hash,
            'canvas': {'source_px': [width, height], 'figsize_inches': list(figsize), 'dpi': 600},
            'rows': 1, 'cols': 1, 'feature_count': 13, 'font': font,
            'palette': SHAP_STOPS, 'color_domain': [0, SHAP_MAX] if name != 'beeswarm' else [0, 1],
            'normalization': 'sample-calibrated continuous monotonic interpolation' if name == 'bar_inset' else 'linear',
            'axes_bounds': list(ax.get_position().bounds), 'insets': getattr(ax, 'inset_positions', {}),
            'source_label_spelling': 'volumn displayed; CSV canonical key volume',
            'panel_label': 'none: standalone source images have no A/B/C letter'}
    atomic_write(args.out / 'figure_spec.json', json_bytes(spec))
    plt.close(fig)
    code = compare(['--original', str(original), '--replica', str(paths[0]),
                    '--out', str(args.out / 'compare/side_by_side.png'), '--footer', f'{name} | {utc_now()[:10]}'])
    if code:
        raise RuntimeError('Comparison export failed')
    record = {'timestamp': utc_now(), 'command': [sys.executable, *sys.argv], 'version': sys.version,
              'cwd': str(Path.cwd()), 'exit_code': 0, 'font': font,
              'packages': {n: importlib.metadata.version(n) for n in ('matplotlib', 'numpy', 'pandas', 'Pillow')},
              'outputs': [str(p) for p in paths], 'data_provenance': 'estimated', 'source_image_sha256': source_hash,
              'iterations': [{'round': 1, 'changes': 'initial templates; canvas, shared normalization, standalone labels'},
                             {'round': 2, 'changes': 'A inset anticlockwise and variable label radii; C scale/center and upright values; B colorbar margin',
                              'qa': 'source A and C appear differently normalized'},
                             {'round': 3, 'changes': 'A continuous sampled nonlinear value-to-color calibration; A/C retain same palette/domain/direction',
                              'qa': 'author visual review pending; no further automatic visual rounds'}]}
    if name == 'beeswarm':
        record['iterations'].append({'round': 'T2 F2 revision',
                                     'changes': 'match img07: no colorbar, axes width .984, 192 estimated points per row, jitter .30',
                                     'qa': 'synthetic distribution remains WARN; author visual review pending'})
    atomic_write(args.out / 'render.log', json_bytes(record))
    atomic_write(args.out / 'run.log', json_bytes(record))
    print(f'{name}: rows={len(df)}; provenance=estimated; font={font["actual"]}; PNG/PDF/SVG -> {args.out / "output"}')
    if name == 'beeswarm':
        with Image.open(paths[0]) as exported:
            print(f'PNG size={exported.size[0]}x{exported.size[1]}; compare={args.out / "compare/side_by_side.png"}')
    return 0
