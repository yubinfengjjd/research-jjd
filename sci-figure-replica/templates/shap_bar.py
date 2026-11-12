"""Horizontal SHAP importance bars, value color scale and radial inset."""
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import FuncNorm, Normalize
from panel_layout import recorded_inset, right_feature_labels
from python_style import SHAP_MAX


def draw_shap_bar(ax, df, *, feature_col, value_col, percent_col=None, cmap,
                  invert_x=True, label_values=True, colorbar=True, inset=True,
                  vmin=0, vmax=SHAP_MAX, xlim=(18.3, 0),
                  inset_bounds=(.065, .14, .32, .37), cbar_bounds=(-.16, .03, .022, .88),
                  label_format='.4f', value_color_positions=None):
    values = df[value_col].to_numpy(float)
    norm = Normalize(vmin, vmax)
    if value_color_positions is not None:
        anchors = np.asarray(value_color_positions, dtype=float)
        if (anchors.ndim != 2 or anchors.shape[1] != 2 or len(anchors) < 2
                or not np.isfinite(anchors).all() or not np.all(np.diff(anchors, axis=0) > 0)
                or not np.allclose(anchors[[0, -1]], [[vmin, 0], [vmax, 1]])):
            raise ValueError('Color calibration must strictly increase from [vmin,0] to [vmax,1]')
        norm = FuncNorm((lambda x: np.interp(x, anchors[:, 0], anchors[:, 1]),
                         lambda y: np.interp(y, anchors[:, 1], anchors[:, 0])), vmin=vmin, vmax=vmax)
    colors = cmap(norm(values))
    bars = ax.barh(np.arange(len(df)), values, color=colors, height=.67, edgecolor='none')
    ax.set_ylim(len(df) - .0, -1)
    ax.set_xlim(xlim if invert_x else tuple(sorted(xlim)))
    ax.set_xticks(np.arange(0, 18, 2.5))
    ax.set_xlabel('SHAP Value', weight='bold', fontsize=11)
    right_feature_labels(ax, df[feature_col].astype(str).tolist())
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(True)
    ax.spines['right'].set_linewidth(.8)
    ax.tick_params(axis='x', labelsize=8)
    for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        label.set_weight('bold')
    texts = []
    if label_values:
        for y, value in enumerate(values):
            texts.append(ax.annotate(format(value, label_format), (value, y), xytext=(-1, 0), textcoords='offset points',
                                     ha='right', va='center', weight='bold', fontsize=7.5,
                                     bbox={'boxstyle': 'square,pad=0', 'fc': 'white', 'ec': '#bcbcbc', 'lw': .25}))
    cbar = None
    if colorbar:
        cax = recorded_inset(ax, cbar_bounds, name='colorbar')
        cbar = ax.figure.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax)
        cbar.set_ticks([])
        cbar.outline.set_visible(False)
        cax.text(.5, 1.02, 'High', transform=cax.transAxes, ha='center', va='bottom', weight='bold', fontsize=9)
        cax.text(.5, -.025, 'Low', transform=cax.transAxes, ha='center', va='top', weight='bold', fontsize=9)
        cax.set_ylabel('SHAP Value', weight='bold', fontsize=10, labelpad=4)
        cax.yaxis.set_label_position('left')
    inset_ax = None
    if inset:
        inset_ax = recorded_inset(ax, inset_bounds, projection='polar', name='radial_inset')
        n = len(values)
        theta = np.arange(n) * (2 * np.pi / n)
        inset_ax.set_theta_zero_location('N')
        inset_ax.set_theta_direction(1)
        # Angular sectors are equally spaced as in the reference; the radial
        # cap reflects importance while the translucent inner wedge leaves air.
        height = 1 + 1.1 * np.sqrt(np.maximum(values, 0) / vmax)
        inset_ax.bar(theta, height, width=2 * np.pi / n * .88, bottom=.07, color=colors, edgecolor='white', linewidth=.2)
        inset_ax.bar(theta, height * .72, width=2 * np.pi / n * .88, bottom=.07, color='white', alpha=.85, linewidth=0)
        percents = df[percent_col].to_numpy(float) if percent_col else values / values.sum() * 100
        for angle, radius, percent in zip(theta, height, percents):
            inset_ax.text(angle, radius + .75, f'{percent:.1f}%', ha='center', va='center', fontsize=7, weight='bold')
        inset_ax.set_ylim(0, 3.15)
        inset_ax.set_axis_off()
    return {'bars': bars, 'labels': texts, 'colorbar': cbar, 'inset': inset_ax, 'norm': norm}
