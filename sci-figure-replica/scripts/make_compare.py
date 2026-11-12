"""Create equal-height comparisons and optional 50% overlays, never a visual verdict."""
import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from common import cli_error, write_batch


def open_rgb(path):
    with Image.open(path) as image:
        image.load()
        rgba = image.convert('RGBA')
        white = Image.new('RGBA', image.size, 'white')
        return Image.alpha_composite(white, rgba).convert('RGB')


def png_bytes(image):
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--replica', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--overlay', type=Path)
    parser.add_argument('--labels', nargs=2, default=['Original', 'Replica'])
    parser.add_argument('--footer', help='Optional figure id/date, reserves 24 px below images')
    args = parser.parse_args(argv)
    try:
        outputs = [args.out] + ([args.overlay] if args.overlay else [])
        if len({p.resolve() for p in outputs}) != len(outputs):
            raise ValueError('Comparison and overlay paths must differ')
        if any(p.resolve() in (args.original.resolve(), args.replica.resolve()) for p in outputs):
            raise ValueError('Output must not overwrite input image')
        original, replica = open_rgb(args.original), open_rgb(args.replica)
        height = max(original.height, replica.height)
        left = original.resize((max(1, round(original.width * height / original.height)), height), Image.Resampling.LANCZOS)
        right = replica.resize((max(1, round(replica.width * height / replica.height)), height), Image.Resampling.LANCZOS)
        top, gap = 36, 24
        canvas = Image.new('RGB', (left.width + gap + right.width, height + top + (24 if args.footer else 0)), 'white')
        canvas.paste(left, (0, top))
        canvas.paste(right, (left.width + gap, top))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 10), args.labels[0], fill='black')
        draw.text((left.width + gap + 8, 10), args.labels[1], fill='black')
        if args.footer:
            draw.text((8, height + top + 5), args.footer, fill='black')
        data = {args.out: png_bytes(canvas)}
        if args.overlay:
            overlay = Image.blend(original, replica.resize(original.size, Image.Resampling.LANCZOS), 0.5)
            data[args.overlay] = png_bytes(overlay)
        write_batch(data)
        print(f'comparison {canvas.width}x{canvas.height}; content_height={height}; gap=24 -> {args.out}')
        if args.overlay:
            print(f'overlay {original.width}x{original.height} alpha=0.5 -> {args.overlay}')
        return 0
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
