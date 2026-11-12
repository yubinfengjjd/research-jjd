"""Quantize image colors, separating colored data from ink and background.

Diverging stops are only inferred if both blue and red are observed; they
are a sampled visual approximation, not a recovered plotting colormap.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from common import atomic_write, cli_error, json_bytes, read_json
from crop_figure import background_rgb
from make_compare import open_rgb


def hex_rgb(rgb):
    return '#' + ''.join(f'{int(x):02x}' for x in rgb)


def sample_palette(image, k=8, probes=None):
    if not 2 <= k <= 256:
        raise ValueError('k must be between 2 and 256')
    array = np.asarray(image)
    background = background_rgb(array)
    total = image.width * image.height
    dominant = []
    # Separate roles before quantization: otherwise the huge white/black text
    # population consumes the palette budget and blends ink into data colors.
    bg_mask = np.linalg.norm(array.astype(float) - background.astype(float), axis=2) < 25
    ink_mask = (np.ptp(array.astype(float), axis=2) < 15) & ~bg_mask
    data_mask = ~(bg_mask | ink_mask)
    for role, mask in [('background', bg_mask), ('ink', ink_mask)]:
        count = int(mask.sum())
        if count:
            rgb = np.median(array[mask], axis=0).round().astype(int).tolist()
            dominant.append({'rgb': rgb, 'hex': hex_rgb(rgb), 'proportion': count / total, 'role': role})
    data_pixels = array[data_mask]
    if len(data_pixels):
        # Reserve at least one bin for each observed side of a diverging scale.
        # A dominant long red bar would otherwise merge the rare blue tail
        # into a pale averaged bin even after background/ink exclusion.
        cool = data_pixels[:, 2].astype(int) - data_pixels[:, 0].astype(int) > 15
        if cool.any() and (~cool).any():
            cool_k = max(1, min(k - 1, round(k * cool.mean())))
            groups = [(data_pixels[cool], cool_k), (data_pixels[~cool], k - cool_k)]
        else:
            groups = [(data_pixels, k)]
        for pixels, bins in groups:
            quantized = Image.fromarray(pixels.reshape(-1, 1, 3)).quantize(colors=bins, method=Image.Quantize.MEDIANCUT)
            palette = quantized.getpalette()
            for count, idx in quantized.getcolors():
                rgb = palette[idx * 3:idx * 3 + 3]
                dominant.append({'rgb': rgb, 'hex': hex_rgb(rgb), 'proportion': count / total, 'role': 'data'})
    dominant.sort(key=lambda p: p['proportion'], reverse=True)
    sampled = []
    for probe in probes or []:
        x, y = probe['x'], probe['y']
        if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x < image.width and 0 <= y < image.height):
            raise ValueError(f'Probe outside image: {probe}')
        rgb = array[y, x].tolist()
        sampled.append({**probe, 'rgb': rgb, 'hex': hex_rgb(rgb)})
    # Use actual saturated pixels, rather than quantized averages, for endpoints.
    pixels = array.reshape(-1, 3).astype(float)
    blue_score = pixels[:, 2] - pixels[:, 0]
    red_score = pixels[:, 0] - pixels[:, 2]
    stops = None
    if blue_score.max() > 40 and red_score.max() > 40:
        blue = pixels[np.argmax(blue_score)].astype(int)
        red = pixels[np.argmax(red_score)].astype(int)
        stops = [hex_rgb(blue), '#ffffff', hex_rgb(red)]
    return {'dominant': dominant, 'probes': sampled,
            'background': {'rgb': background.tolist(), 'hex': hex_rgb(background)},
            'diverging_stops': stops, 'diverging_note': 'sampled endpoints; intermediate colors require visual review'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--probes', type=Path)
    parser.add_argument('--k', type=int, default=8)
    args = parser.parse_args(argv)
    try:
        if args.out.resolve() in {args.image.resolve(), args.probes.resolve() if args.probes else None}:
            raise ValueError('Output must not overwrite input')
        meta = sample_palette(open_rgb(args.image), args.k, read_json(args.probes) if args.probes else None)
        atomic_write(args.out, json_bytes(meta))
        print(f'background={meta["background"]["hex"]}; data_colors={[x["hex"] for x in meta["dominant"] if x["role"] == "data"]}; diverging_stops={meta["diverging_stops"]} -> {args.out}')
        return 0
    except (OSError, ValueError, KeyError, Image.DecompressionBombError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
