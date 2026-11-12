"""Fig. 4 A–F reconstruction. CSV transcriptions are uncertain; beeswarms estimated.

Only staged T2 templates are imported. The archived post snippets are never run.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import importlib.metadata
from io import StringIO
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import AutoMinorLocator, FormatStrFormatter
import numpy as np
import pandas as pd
from PIL import Image

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
ROOT = SKILL
sys.path.insert(0, str(SKILL / 'templates'))
sys.path.insert(0, str(SKILL / 'scripts'))
from python_style import apply_style, save_figure
from shap_bar import draw_shap_bar
from beeswarm import draw_beeswarm
from radial_bar import draw_radial
from crop_figure import main as crop_main
from make_compare import main as compare_main
from common import atomic_write, json_bytes, sha256, utc_now

SOURCE = ROOT / 'samples/post01/source/fig01.png'
ROW_BOUNDS = [(0.564, .405), (.069, .405)]


def sampled_bar_palette(values, row):
    """Local calibration at bar interiors; not an independent color-QA holdout."""
    with Image.open(SOURCE) as image:
        image = np.asarray(image.convert('RGB'))
    ys = np.linspace(29 if row == 0 else 281, 209 if row == 0 else 461, 15).round().astype(int)
    samples = np.array([np.median(image[y-1:y+2, 319:335], axis=(0, 1)) / 255 for y in ys])
    vmin, vmax = float(min(values)), float(max(values))
    stops = sorted(zip((np.asarray(values) - vmin) / (vmax - vmin), samples), key=lambda x: x[0])
    return LinearSegmentedColormap.from_list(f'printed_bars_{row}', stops, N=4096), samples, [vmin, vmax]


def build_figure():
    font = apply_style()
    font['file'] = font_manager.findfont(font_manager.FontProperties(family=font['actual']))
    data = pd.read_csv(HERE / 'estimated_data.csv', keep_default_na=False)
    swarm = pd.read_csv(HERE / 'estimated_beeswarm.csv')
    fig = plt.figure(figsize=(12, 6.84))
    artists, panels = {}, {}
    # Radial / feature-value scale matches the visible blue-white-red source.
    radial_cmap = matplotlib.colormaps['RdBu_r']
    for row, (bar, bee, ring) in enumerate([('A', 'B', 'C'), ('D', 'E', 'F')]):
        y, h = ROW_BOUNDS[row]
        df = data[data.panel == bar]
        rdf = data[data.panel == ring]
        order = df.feature.tolist()
        if len(df) != 15 or len(rdf) != 15 or set(order) != set(rdf.feature):
            raise ValueError('Expected 15 matching bar/radial features per row')
        b_ax = fig.add_axes([.123, y, .259, h])
        cmap, samples, domain = sampled_bar_palette(df.shap, row)
        result = draw_shap_bar(b_ax, df, feature_col='feature', value_col='shap', percent_col='percent',
                               cmap=cmap, vmin=domain[0], vmax=domain[1], xlim=(.16 if row == 0 else .10, 0),
                               inset_bounds=(-.01, .11, .36, .40), cbar_bounds=(-.055, 0, .020, 1))
        result['ax'] = b_ax
        b_ax.set_ylim(14.95, -1.05)
        b_ax.set_xticks(np.arange(0, .161 if row == 0 else .101, .02))
        b_ax.set_xlim(.16 if row == 0 else .10, 0)
        b_ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        b_ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        b_ax.tick_params(axis='x', which='both', direction='in', length=2, labelsize=7.5, pad=2)
        b_ax.tick_params(axis='x', which='minor', length=1.4)
        b_ax.tick_params(axis='y', labelsize=10, pad=7)
        b_ax.set_xlabel('SHAP Value', fontsize=12, labelpad=1, weight='bold')
        for text in result['labels']:
            text.set_fontsize(4.8)
        cbar = result['colorbar']
        cbar.ax.set_ylabel('SHAP Value', fontsize=11, weight='bold', labelpad=8)
        for t in cbar.ax.texts:
            t.set_fontsize(10)
            t.set_x(-.7)
            t.set_ha('right')
            t.set_y(1 if t.get_text() == 'High' else 0)
        # T2 inset uses the same bar rows and explicit C/F percentages.
        inset = result['inset']
        # Fig.4's inset is an open radial fan: low bars extend farther out.
        # Adapt the T2 artists rather than duplicating its polar drawing code.
        angles = np.deg2rad(45 + np.arange(15) * 21)
        heights = np.linspace(1.0, 2.1, 15)
        inset.set_theta_direction(-1)
        for i, patch in enumerate(inset.patches):
            idx = i % 15
            patch.set_x(angles[idx] - np.deg2rad(18) / 2)
            patch.set_width(np.deg2rad(18))
            patch.set_height(heights[idx] * (.72 if i >= 15 else 1))
        for i, t in enumerate(inset.texts):
            t.set_position((angles[i], heights[i] + .49))
        inset.set_ylim(0, 3.15)
        for t in inset.texts:
            t.set_fontsize(3.9)
        artists[bar] = result
        panels[bar] = {'kind': 'bar_inset', 'axes_bounds': list(b_ax.get_position().bounds),
                       'features': order, 'shap': df.shap.tolist(), 'percent': df.percent.tolist(),
                       'insets': b_ax.inset_positions, 'color_domain': domain,
                       'palette_samples_rgb': samples.tolist(),
                       'normalization': 'piecewise source-interior color calibration; not holdout validation'}
        s_ax = fig.add_axes([.527, y, .138, h])
        bdf = swarm[swarm.panel == bee]
        xlim = (-.64, .55) if row == 0 else (-.17, .21)
        result = draw_beeswarm(s_ax, bdf, feature_order=order, cmap=radial_cmap, xlim=xlim,
                               cbar_bounds=(1.067, 0, .014, 1), point_size=4.5, jitter=.24)
        result['ax'] = s_ax
        s_ax.set_ylim(b_ax.get_ylim())
        s_ax.set_xticks([-.5, 0, .5] if row == 0 else [-.1, 0, .1, .2])
        s_ax.set_xlim(xlim)
        s_ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        s_ax.tick_params(axis='x', which='both', direction='in', labelsize=7, pad=2, length=2)
        s_ax.tick_params(axis='x', which='minor', length=1.4)
        s_ax.set_xlabel('SHAP Value', fontsize=12, weight='bold', labelpad=1)
        result['colorbar'].ax.tick_params(labelsize=5, pad=1)
        result['colorbar'].set_label('Feature value', fontsize=6, labelpad=-7)
        artists[bee] = result
        panels[bee] = {'kind': 'beeswarm', 'axes_bounds': list(s_ax.get_position().bounds),
                       'features_shared_with': bar, 'features': order, 'xlim': list(xlim),
                       'point_counts': [len(c.get_offsets()) for c in result['points']],
                       'data_provenance': 'estimated', 'color_domain': [0, 1],
                       'insets': s_ax.inset_positions}
        r_ax = fig.add_axes([.714, y - .073, .19, h + .026], projection='polar')
        result = draw_radial(r_ax, rdf, value_col='shap', percent_col='percent', label_col='feature',
                             cmap=radial_cmap, vmin=.035 if row == 0 else .015,
                             vmax=.155 if row == 0 else .10, inner=2.1, base_height=.08,
                             height_scale=1.5, label_size=5.7, value_size=3.8,
                             cbar_bounds=(.47, .38, .028, .24 if row == 0 else .12))
        result['ax'] = r_ax
        r_ax.set_theta_offset(np.pi / 2 - np.pi / 15)
        for t in result['labels']:
            theta, radius = t.get_position()
            # Extend names radially from the sector edge, with readable orientation.
            degrees = np.degrees(theta) + 12
            rotation = 90 - degrees
            left = degrees > 180
            if left:
                rotation += 180
            t.set_position((theta, radius - .29))
            t.set_rotation(rotation)
            t.set_ha('right' if left else 'left')
        cbar = result['colorbar']
        ticks = [.05, .075, .10, .125, .15] if row == 0 else [.025, .05, .075]
        cbar.set_ticks(ticks)
        cbar.ax.set_ylim(cbar.norm.vmin, cbar.norm.vmax)
        cbar.ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        cbar.ax.tick_params(labelsize=4.5, length=1, pad=1)
        cbar.ax.set_title('|SHAP Value|', fontsize=4.3, pad=3, weight='bold')
        artists[ring] = result
        panels[ring] = {'kind': 'radial_bar', 'axes_bounds': list(r_ax.get_position().bounds),
                        'features': rdf.feature.tolist(), 'shap': rdf.shap.tolist(), 'percent': rdf.percent.tolist(),
                        'color_domain': [cbar.norm.vmin, cbar.norm.vmax], 'color_ticks': ticks,
                        'theta_direction': 'clockwise', 'theta_offset_degrees': 78,
                        'insets': r_ax.inset_positions}
    # Preserve reading order in figure-level letters and metadata.
    for letter in 'ABCDEF':
        row = 0 if letter < 'D' else 1
        x = {'A': .057, 'B': .524, 'C': .711, 'D': .057, 'E': .524, 'F': .711}[letter]
        y = .968 if row == 0 else .472
        fig.text(x, y, letter, weight='bold', fontsize=14, va='bottom')
        panels[letter]['label'] = {'text': letter, 'figure_xy': [x, y], 'fontsize_pt': 14}
        panels[letter]['bbox_figure'] = ([.05, ROW_BOUNDS[row][0]-.065, .475, .49] if letter in 'AD'
                                        else [.523, ROW_BOUNDS[row][0]-.065, .176, .49] if letter in 'BE'
                                        else [.70, ROW_BOUNDS[row][0]-.065, .29, .49])
    meta = {'status': 'review', 'name': 'post01-fig4', 'code_provenance': 'reconstructed',
            'original_code_provenance': 'example_not_target', 'archive_execution': 'archived_only',
            'data_provenance': {'bars_and_rings': 'uncertain visual transcription', 'beeswarms': 'estimated'},
            'source_image': str(SOURCE), 'source_image_sha256': sha256(SOURCE),
            'data_files_sha256': {name: sha256(HERE / name) for name in ['estimated_data.csv', 'estimated_beeswarm.csv']},
            'canvas': {'source_px': [893, 509], 'figsize_inches': [12, 6.84], 'dpi': 600},
            'rows': 2, 'cols': 3, 'font': font, 'panels': {k: panels[k] for k in 'ABCDEF'},
            'radial_and_beeswarm_palette': 'matplotlib RdBu_r; blue low / red high',
            'data_sources': ['fig01.png', 'provided panel_A_4x.png through panel_F_4x.png'],
            'scientific_scope': 'visual reconstruction only; no original observations or fitted model'}
    return fig, artists, meta


def render(out):
    out.mkdir(parents=True, exist_ok=True)
    crop_code = crop_main(['--image', str(SOURCE), '--out', str(out / 'source_crop')])
    if crop_code:
        raise RuntimeError(f'crop failed: exit={crop_code}')
    fig, artists, meta = build_figure()
    paths = save_figure(fig, out / 'output/replica')
    from skimage.color import rgb2lab, deltaE_ciede2000
    colors = {'threshold_median_deltaE00': 10, 'status': 'WARN',
              'scope': 'bar source-interior calibration fit only; not independent palette/distribution validation',
              'radial_and_beeswarm': 'visual comparison only; not independently measured', 'panels': {}}
    for letter in 'AD':
        source_rgb = np.asarray(meta['panels'][letter]['palette_samples_rgb'])
        replica_rgb = np.asarray([p.get_facecolor()[:3] for p in artists[letter]['bars']])
        delta = deltaE_ciede2000(rgb2lab(source_rgb), rgb2lab(replica_rgb))
        colors['panels'][letter] = {'source_rgb': source_rgb.tolist(), 'replica_rgb': replica_rgb.tolist(),
                                    'deltaE00': delta.tolist(), 'median_deltaE00': float(np.median(delta)),
                                    'within_10_in_sample': bool(np.median(delta) <= 10)}
    atomic_write(out / 'color_audit.json', json_bytes(colors))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # Record actual text extents after drawing for reviewable clipping evidence.
    texts = [*fig.texts]
    for value in artists.values():
        texts.extend(value.get('labels', []))
    outside = []
    for text in texts:
        if not hasattr(text, 'get_window_extent'):
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < 0 or box.y0 < 0 or box.x1 > fig.bbox.width or box.y1 > fig.bbox.height:
            outside.append(text.get_text())
    plt.close(fig)
    meta['text_outside_canvas'] = outside
    meta['crop'] = json.loads((out / 'source_crop/crop.json').read_text(encoding='utf-8'))
    atomic_write(out / 'figure_spec.json', json_bytes(meta))
    code = compare_main(['--original', str(out / 'source_crop/original_figure.png'), '--replica', str(paths[0]),
                         '--out', str(out / 'compare/side_by_side.png'), '--footer', f'post01 Fig.4 | {utc_now()[:10]} | review'])
    if code:
        raise RuntimeError(f'comparison failed: exit={code}')
    with Image.open(paths[0]) as im:
        size = list(im.size)
        aspect_error = abs((im.width / im.height) / (893 / 509) - 1)
    qa = f'''# post01 Fig.4 QA

状态：review；作者未签核。阈值保持宽高比≤2%、颜色ΔE00中位数≤10。

| 项目 | 结论 | 证据与限制 |
|---|---|---|
| 画布/宽高比 | {'PASS' if aspect_error <= .02 else 'FAIL'} | PNG {size[0]}×{size[1]}；相对误差 {aspect_error:.6%} ≤2%。 |
| panel 布局 | WARN | 2×3，A/B、D/E共享标签；行间对齐有artist测试；并排图待作者签核。 |
| 面板标签 | PASS | A–F粗体；figure_spec记录位置，测试检查实际文本。 |
| 颜色 | WARN | 蓝低红高；A/D色彩按原图条内部校准，非独立验证；未宣称ΔE00通过，见color_audit.json。 |
| 字体 | WARN | 实际 {meta['font']['actual']}；文件 {meta['font']['file']}；源字体文件未知。 |
| 坐标轴/刻度 | PASS | A 0.16→0、D 0.10→0；B −0.64～0.55、E −0.17～0.21；覆盖源图可见范围。 |
| 图例/colorbar | PASS | A/D左侧High/Low；B/E右侧Feature value；C/F中心SHAP绝对值尺度与ticks已记录。 |
| 数据形状 | WARN | A/D印刷值逐条候选转录；C/F低分辨率百分比uncertain；B/E各15×180合成点，非原始样本。 |
| 注释 | WARN | 数值、环形百分比齐全；uncertain_reason逐项保存。画布外文字：{outside}。 |
| 导出 | WARN | PNG/PDF/SVG已生成；SVG文字可编辑；PDF页级独立查看器视觉保留待T4。 |

未执行帖子示例训练；未写真实画廊、samples或全局安装。作者/日期/结论：待填。
'''
    atomic_write(out / 'qa_report.md', qa)
    record = {'timestamp': utc_now(), 'command': [sys.executable, *sys.argv], 'executable': sys.executable,
              'cwd': str(Path.cwd()), 'python': sys.version, 'exit_code': 0,
              'packages': {n: importlib.metadata.version(n) for n in ['matplotlib', 'numpy', 'pandas', 'Pillow']},
              'font': meta['font'], 'source_image_sha256': meta['source_image_sha256'],
              'data_files_sha256': meta['data_files_sha256'], 'outputs': [str(p) for p in paths],
              'text_outside_canvas': outside,
              'iterations': [{'round': 1, 'changes': 'T2 templates composed at source-normalized axes; shared labels, paired insets, four outer and two central scales',
                              'qa': 'one C label exceeded canvas; radial diagrams too high and large; inset fan differs'},
                             {'round': 2, 'changes': 'lower and reduce C/F polar axes; reshape existing T2 inset artists into source open fan',
                              'qa': 'estimated swarm / uncertain transcription / source font / PDF page review remain WARN'}]}
    atomic_write(out / 'render.log', json_bytes(record))
    with (out / 'run.log').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    print('post01-fig4: A-F; 2x3; shared labels A/B,D/E; A/D radial insets; B/E Feature value scales; C/F polar scales')
    print(f'data: bars/rings=uncertain transcription; B=2700 E=2700 points (estimated); font={meta["font"]["actual"]}')
    print(f'PNG={size[0]}x{size[1]}; aspect_error={aspect_error:.6%}; text_outside_canvas={len(outside)}; status=review')
    print(f'PNG/PDF/SVG -> {out / "output"}; compare -> {out / "compare/side_by_side.png"}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE)
    args = parser.parse_args(argv)
    protected = [ROOT / 'samples', Path(json.loads((SKILL / 'config.json').read_text(encoding='utf-8'))['gallery_root'])]
    target = args.out.resolve()
    if any(target == p.resolve() or p.resolve() in target.parents for p in protected):
        print('Refusing output in protected samples or real gallery', file=sys.stderr)
        return 2
    # Capture the actual streams, also forwarding them to the caller.
    stdout, stderr = StringIO(), StringIO()
    code = 1
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = render(args.out)
    except Exception:
        import traceback
        traceback.print_exc(file=stderr)
    finally:
        atomic_write(args.out / 'stdout.txt', stdout.getvalue())
        atomic_write(args.out / 'stderr.txt', stderr.getvalue())
        atomic_write(args.out / 'exit_code.txt', f'{code}\n')
        sys.stdout.write(stdout.getvalue())
        sys.stderr.write(stderr.getvalue())
    return code


if __name__ == '__main__':
    raise SystemExit(main())
