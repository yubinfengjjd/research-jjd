"""Deterministic file checks plus an unfilled human visual-QA checklist."""
import argparse
from pathlib import Path

from PIL import Image
from common import atomic_write, cli_error, read_json, utc_now


def aspect_error(original, replica):
    return abs((replica[0] / replica[1]) / (original[0] / original[1]) - 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry', type=Path, required=True)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--replica', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        rows = []
        def record(name, ok, reason):
            rows.append((name, 'PASS' if ok else 'FAIL', reason))
        required = ['meta.json', 'README.md', 'data/figure_spec.json', 'data/estimated_data.csv',
                    'output/replica.png', 'output/replica.pdf', 'output/replica.svg',
                    'compare/side_by_side.png', 'thumb.png', 'run.log']
        for name in required:
            path = args.entry / name
            record(name, path.is_file() and path.stat().st_size > 0, '文件存在且非空；不等于格式或视觉验收')
        code = [args.entry / 'code/replica.py', args.entry / 'code/replica.R']
        record('复刻代码', any(p.is_file() and p.stat().st_size > 0 for p in code), '需要 replica.py 或 replica.R')
        source = args.entry / 'source'
        record('原图存档', any(source.glob('fig*.png')), 'source/figNN.png')
        sizes = {}
        for label, path in [('original', args.original), ('replica', args.replica), ('thumbnail', args.entry / 'thumb.png')]:
            try:
                with Image.open(path) as image:
                    image.load()
                    sizes[label] = image.size
                    record(f'{label} 可打开', True, f'{image.format} {image.width}×{image.height} px')
                    if label == 'replica':
                        record('PNG 格式', image.format == 'PNG', '要求 PNG')
            except (OSError, ValueError) as error:
                record(f'{label} 可打开', False, str(error))
        if 'original' in sizes and 'replica' in sizes:
            error = aspect_error(sizes['original'], sizes['replica'])
            record('宽高比', error <= 0.02 + 1e-12, f'相对误差 {error:.4%}，阈值 ≤2%')
        manual = ['画布/宽高比', 'panel 布局与面板标签', '颜色/发散方向', '字体/中文缺字', '坐标轴/刻度',
                  '图例/colorbar', '数据形状/estimated 不确定项', '注释', '导出/矢量文字可编辑']
        text = '# QA report\n\n' + utc_now() + '\n\n'
        text += '机械检查只核查文件、像素尺寸与宽高比；不判断视觉像不像，不代表作者签核。\n\n'
        text += '| 自动检查 | 状态 | 证据 |\n|---|---|---|\n'
        text += '\n'.join(f'| {n} | {s} | {r.replace(chr(10), " ").replace("|", "/")} |' for n, s, r in rows)
        text += '\n\n## 人工视觉 QA（未评定）\n\n| 项目 | PASS/WARN/FAIL（待填） | 理由（待填） |\n|---|---|---|\n'
        text += '\n'.join(f'| {name} | | |' for name in manual)
        text += '\n\n作者/签核日期/结论：________\n\n修图以满足检查；不得降低阈值以通过。\n'
        protected = [args.original.resolve(), args.replica.resolve(), *( (args.entry / p).resolve() for p in required)]
        if args.out.resolve() in protected:
            raise ValueError('QA report must not overwrite an artifact')
        atomic_write(args.out, text)
        fails = sum(s == 'FAIL' for _, s, _ in rows)
        print(f'QA mechanical_failures={fails}; visual=unassessed -> {args.out}')
        return 1 if fails else 0
    except (OSError, ValueError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
