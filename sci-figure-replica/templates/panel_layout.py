"""Reusable rectangular layout and explicitly recorded inset bounds."""
import numpy as np
import matplotlib.pyplot as plt


def grid_figure(rows, cols, figsize, width_ratios=None, height_ratios=None, wspace=.15, hspace=.2):
    fig = plt.figure(figsize=figsize)
    grid = fig.add_gridspec(rows, cols, width_ratios=width_ratios, height_ratios=height_ratios,
                           wspace=wspace, hspace=hspace)
    axes = np.array([[fig.add_subplot(grid[r, c]) for c in range(cols)] for r in range(rows)])
    return fig, axes


def right_feature_labels(ax, labels):
    ax.set_yticks(range(len(labels)), labels, weight='bold')
    ax.yaxis.tick_right()
    ax.tick_params(axis='y', length=0, pad=7)


def hide_y(ax):
    # Keep tick locations for horizontal grid rows.
    ax.tick_params(axis='y', left=False, right=False, labelleft=False, labelright=False)
    ax.spines['left'].set_visible(False)


def recorded_inset(ax, bounds, *, projection=None, name='inset'):
    child = ax.inset_axes(bounds, **({'projection': projection} if projection else {}))
    records = getattr(ax, 'inset_positions', {})
    records[name] = {'bounds': list(bounds), 'coordinate_system': 'axes_fraction', 'projection': projection}
    ax.inset_positions = records
    return child
