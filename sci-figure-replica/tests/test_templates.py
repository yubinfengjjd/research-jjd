import sys
import pytest
from conftest import SKILL


@pytest.mark.parametrize('kind', ['bar', 'beeswarm', 'radial'])
def test_templates_render_correct_direction_and_labels(kind):
    sys.path.insert(0, str(SKILL / 'templates'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd
    from python_style import apply_style, shap_cmap, panel_label
    from panel_layout import grid_figure, recorded_inset
    apply_style()
    df = pd.DataFrame({'feature': ['one', 'two'], 'shap': [17.4, 2.8], 'percent': [52.5, 8.4], 'feature_value': [0, 1]})
    if kind == 'radial':
        from radial_bar import draw_radial
        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})
        result = draw_radial(ax, df, value_col='shap', percent_col='percent', label_col='feature', cmap=shap_cmap())
        assert len(result['bars']) == 2
        assert result['colorbar'].norm.vmax == 17.4089
    else:
        fig, axes = grid_figure(1, 1, (5, 4))
        ax = axes[0, 0]
        if kind == 'bar':
            from shap_bar import draw_shap_bar
            result = draw_shap_bar(ax, df, feature_col='feature', value_col='shap', percent_col='percent', cmap=shap_cmap())
            assert ax.xaxis_inverted()
            assert [t.get_text() for t in ax.get_yticklabels()] == ['one', 'two']
            assert ax.yaxis.get_ticks_position() == 'right'
            assert len(result['inset'].patches) >= 2
        else:
            from beeswarm import draw_beeswarm
            result = draw_beeswarm(ax, df, feature_order=['one', 'two'], cmap=shap_cmap(), xlim=(-25, 45))
            assert [len(c.get_offsets()) for c in result['points']] == [1, 1]
            assert all(not t.get_visible() for t in ax.get_yticklabels())
            assert result['colorbar'].ax.get_ylabel() == 'Feature value'
    panel_label(fig, ax, 'A')
    fig.canvas.draw()
    plt.close(fig)


def test_bar_supports_continuous_value_color_calibration():
    sys.path.insert(0, str(SKILL / 'templates'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd
    from shap_bar import draw_shap_bar
    from python_style import shap_cmap
    fig, ax = plt.subplots()
    result = draw_shap_bar(ax, pd.DataFrame({'feature': ['one'], 'shap': [2.0]}),
                           feature_col='feature', value_col='shap', cmap=shap_cmap(),
                           value_color_positions=[[0, 0], [2, .75], [17.4089, 1]], inset=False, colorbar=False)
    assert result['norm'](1) == pytest.approx(.375)
    assert result['bars'][0].get_facecolor()[:3] == pytest.approx((.965, .686, .538), abs=.01)
    plt.close(fig)
