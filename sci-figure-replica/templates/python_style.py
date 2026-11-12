"""Standalone matplotlib style and lossless vector/text export helpers."""
from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

SHAP_MAX = 17.4089
SHAP_STOPS = ['#2f84b1', '#eaf6fb', '#ffffff', '#f6b08a', '#c40035']


def shap_cmap():
    return LinearSegmentedColormap.from_list('sampled_shap', SHAP_STOPS, N=256)


def apply_style():
    candidates = ['Arial', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    installed = {font.name for font in font_manager.fontManager.ttflist}
    available = [name for name in candidates if name in installed]
    mpl.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': available or ['DejaVu Sans'],
                         'font.size': 7.5, 'axes.linewidth': .8, 'axes.spines.top': False,
                         'axes.spines.right': False, 'xtick.direction': 'out', 'ytick.direction': 'out',
                         'pdf.fonttype': 42, 'svg.fonttype': 'none', 'savefig.dpi': 600,
                         'savefig.bbox': None})
    return {'requested': candidates, 'available': available, 'actual': font_manager.FontProperties(family=['sans-serif']).get_name()}


def save_figure(fig, stem):
    """Keep the canvas ratio; callers reserve margins explicitly. Errors propagate."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ('png', 'pdf', 'svg'):
        path = stem.with_suffix('.' + ext)
        fig.savefig(path, format=ext, dpi=600, bbox_inches=None, facecolor='white')
        paths.append(path)
    return paths


def register_cjk_font(text='示例图分组数值'):
    """Select an installed CJK face and verify its cmap; never silently use tofu."""
    from matplotlib.ft2font import FT2Font
    candidates = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'SimSun']
    for family in candidates:
        try:
            path = font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
        except ValueError:
            continue
        cmap = FT2Font(path).get_charmap()
        if all(ord(char) in cmap for char in text if not char.isspace()):
            mpl.rcParams['font.family'] = [family]
            return {'family': family, 'file': str(Path(path).resolve()), 'verified_text': text,
                    'fallback': family not in candidates[:2]}
    raise RuntimeError('No installed CJK font covers the labels. Supply Microsoft YaHei/SimHei or Noto Sans CJK SC locally; rendering stopped to avoid tofu.')


def panel_label(fig, ax, letter, x=-.04, y=1.02, fontsize=12, **kwargs):
    point = fig.transFigure.inverted().transform(ax.transAxes.transform((x, y)))
    return fig.text(*point, letter, weight='bold', fontsize=fontsize, va='bottom', ha='left', **kwargs)


apply_style()
