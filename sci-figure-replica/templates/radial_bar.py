"""Polar importance sectors with tangential labels and central color scale."""
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from panel_layout import recorded_inset
from python_style import SHAP_MAX


def draw_radial(ax, df, *, value_col, percent_col, label_col, cmap,
                cbar_title='|SHAP Value|', vmin=0, vmax=SHAP_MAX,
                inner=2.1, base_height=.34, height_scale=1.12,
                label_size=7, value_size=5.3, cbar_bounds=(.475, .36, .05, .27)):
    if ax.name != 'polar':
        raise ValueError('draw_radial requires a polar axes')
    values = df[value_col].to_numpy(float)
    percentages = df[percent_col].to_numpy(float)
    n = len(values)
    theta = np.arange(n) * 2 * np.pi / n
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    norm = Normalize(vmin, vmax)
    heights = base_height + height_scale * values / vmax
    width = 2 * np.pi / n * .93
    bars = ax.bar(theta, heights, width=width, bottom=inner, color=cmap(norm(values)),
                  edgecolor='#777777', linewidth=.8)
    circle = np.linspace(0, 2 * np.pi, 400)
    ax.plot(circle, np.full_like(circle, inner - .09), color='#777777', linewidth=.9)
    labels, numbers = [], []
    for angle, height, label, percent, value in zip(theta, heights, df[label_col], percentages, values):
        degrees = np.degrees(angle)
        rotation = 90 - degrees
        if 180 < degrees < 360:
            rotation += 180
        labels.append(ax.text(angle, inner + height + .52, f'{label}\n{percent:.1f}%',
                              rotation=rotation, rotation_mode='anchor', ha='center', va='center',
                              fontsize=label_size, weight='bold', color='#262626', clip_on=False))
        text_rotation = (-degrees + 90) % 180 - 90
        numbers.append(ax.text(angle, inner + height / 2, f'{value:.3f}', color='white',
                               fontsize=value_size, weight='bold', ha='center', va='center', rotation=text_rotation))
    ax.set_ylim(0, inner + base_height + height_scale + .44)
    ax.set_axis_off()
    cax = recorded_inset(ax, cbar_bounds, name='central_colorbar')
    cbar = ax.figure.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax)
    cbar.set_ticks([5, 10, 15])
    cbar.ax.tick_params(labelsize=6, width=.5, length=2)
    cax.set_title(cbar_title, fontsize=7, weight='bold', pad=4)
    return {'bars': bars, 'labels': labels, 'values': numbers, 'colorbar': cbar, 'norm': norm}
