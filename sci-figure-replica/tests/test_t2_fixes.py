"""Catch the T2 standalone B colorbar/layout and synthetic-density regressions."""
import subprocess
import sys

import pytest
from conftest import SKILL, read_json


def test_beeswarm_none_bounds_omits_colorbar_and_preserves_default_option():
    sys.path.insert(0, str(SKILL / 'templates'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd
    from beeswarm import draw_beeswarm
    from python_style import shap_cmap
    df = pd.DataFrame({'feature': ['one'], 'shap': [1.0], 'feature_value': [.5]})
    fig, axes = plt.subplots(1, 2)
    try:
        standalone = draw_beeswarm(axes[0], df, feature_order=['one'], cmap=shap_cmap(),
                                   xlim=(-25, 45), cbar_bounds=None)
        composed = draw_beeswarm(axes[1], df, feature_order=['one'], cmap=shap_cmap(), xlim=(-25, 45))
        fig.canvas.draw()
        assert standalone['colorbar'] is None and not axes[0].child_axes
        assert composed['colorbar'] is not None and len(axes[1].child_axes) == 1
    finally:
        plt.close(fig)


def test_standalone_beeswarm_exports_wide_plot_without_extra_colorbar(tmp_path):
    folder = SKILL / 'examples/single-panel/beeswarm'
    result = subprocess.run([sys.executable, '-X', 'utf8', str(folder / 'replica.py'), '--out', str(tmp_path)],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    spec = read_json(tmp_path / 'figure_spec.json')
    assert spec['insets'] == {}
    x, _, width, _ = spec['axes_bounds']
    assert x < .015 and width >= .96 and x + width > .98
    svg = (tmp_path / 'output/replica.svg').read_text(encoding='utf-8')
    assert 'Feature value' not in svg


def test_beeswarm_density_remains_explicitly_estimated():
    import pandas as pd
    df = pd.read_csv(SKILL / 'examples/single-panel/beeswarm/estimated_data.csv')
    counts = df.groupby('feature').size()
    assert len(counts) == 13 and counts.between(150, 200).all()
    assert set(df['provenance']) == {'estimated'}
    assert df['uncertain_reason'].str.contains('synthetic visual approximation').all()
    assert df['feature_value'].between(0, 1).all()
