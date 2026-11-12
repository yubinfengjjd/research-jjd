"""Deterministic density jitter for estimated SHAP points; no shap dependency."""
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from panel_layout import hide_y as hide_y_axis, recorded_inset


def draw_beeswarm(ax, df, *, feature_order, cmap, xlim, zero_line=True,
                  grid=True, hide_y=True, colorbar=True, feature_col='feature',
                  shap_col='shap', color_col='feature_value', seed=20261020,
                  point_size=8, jitter=.28, cbar_bounds=(1.025, .03, .018, .92)):
    """Set cbar_bounds=None (or colorbar=False) to omit the optional colorbar."""
    rng = np.random.default_rng(seed)
    norm = Normalize(0, 1)
    collections = []
    for row, feature in enumerate(feature_order):
        points = df.loc[df[feature_col] == feature]
        xs = points[shap_col].to_numpy(float)
        # Dense clusters get wider vertical spread; isolated points remain close
        # to their feature row. Jitter never changes SHAP or feature-value data.
        if len(xs):
            bins = np.floor(xs / max((xlim[1] - xlim[0]) / 180, .05)).astype(int)
            _, inverse, counts = np.unique(bins, return_inverse=True, return_counts=True)
            amplitude = np.minimum(1, np.sqrt(counts[inverse] / 7)) * jitter
            ys = row + rng.uniform(-1, 1, len(xs)) * amplitude
            collections.append(ax.scatter(xs, ys, c=points[color_col], cmap=cmap, norm=norm,
                                          s=point_size, linewidths=0, zorder=3))
    ax.set_xlim(xlim)
    ax.set_ylim(len(feature_order) - .0, -1)
    ax.set_yticks(range(len(feature_order)), feature_order)
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel('SHAP Value', fontsize=12, weight='bold')
    for label in ax.get_xticklabels():
        label.set_weight('bold')
    if zero_line:
        ax.axvline(0, color='#999999', linewidth=1, zorder=1)
    if grid:
        ax.grid(axis='y', color='#d5d5d5', linestyle=(0, (1, 4)), linewidth=.5, zorder=0)
    if hide_y:
        hide_y_axis(ax)
    cbar = None
    if colorbar and cbar_bounds is not None:
        cax = recorded_inset(ax, cbar_bounds, name='feature_value_colorbar')
        cbar = ax.figure.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax)
        cbar.set_ticks([0, 1], labels=['Low', 'High'])
        cbar.ax.tick_params(length=0, labelsize=6)
        cbar.set_label('Feature value', fontsize=7)
        cbar.outline.set_visible(False)
    return {'points': collections, 'colorbar': cbar, 'norm': norm}
