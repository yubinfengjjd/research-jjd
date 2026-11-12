"""Crop margins and separated bottom caption bands without changing the source.

--bbox uses original-image coordinates (exclusive right/bottom).
--spec writes/updates the analysis JSON; existing caption_bbox/quality_flags
are accepted as human overrides. Caption detection is a geometric heuristic,
not OCR; inspect crop.json and use --bottom-crop for ambiguous cases.
Content uses a sensitive mask plus 8 px padding. When a separated caption is
removed, keep the full canvas width to preserve composite-figure side margins.
"""
import argparse
from pathlib import Path
import re

import numpy as np
from PIL import Image
from common import cli_error, json_bytes, read_json, write_batch
from make_compare import open_rgb, png_bytes


def background_rgb(array):
    h, w = array.shape[:2]
    size = max(1, min(8, h // 10, w // 10))
    corners = np.concatenate([array[:size, :size].reshape(-1, 3), array[:size, -size:].reshape(-1, 3),
                              array[-size:, :size].reshape(-1, 3), array[-size:, -size:].reshape(-1, 3)])
    return np.median(corners, axis=0).round().astype('uint8')


def validate_bbox(bbox, width, height):
    if len(bbox) != 4 or any(int(x) != x for x in bbox):
        raise ValueError('bbox must contain four integer pixel coordinates')
    x0, y0, x1, y1 = map(int, bbox)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError('bbox outside original image or empty')
    return [x0, y0, x1, y1]


def caption_band(array, mask):
    """Detect a wide, achromatic text band below a substantial white gap."""
    h, w = mask.shape
    rows = np.flatnonzero(mask.any(axis=1))
    if not len(rows):
        return None
    groups = np.split(rows, np.where(np.diff(rows) > 1)[0] + 1)
    previous = -1
    for group in groups:
        start = int(group[0])
        if start > .72 * h and start - previous > max(8, .018 * h) and h - start < .27 * h:
            band = mask[start:]
            widths = band[:int(rows[-1]) - start + 1].sum(axis=1)
            color = np.ptp(array[start:].astype(float), axis=2) > 35
            if (widths.max() >= .6 * w and (widths > .4 * w).sum() >= 3
                    and widths.std() > .15 * widths.mean()
                    and color[band].mean() < .015):
                xs = np.flatnonzero(band.any(axis=0))
                return [int(xs[0]), start, int(xs[-1]) + 1, int(rows[-1]) + 1]
        previous = int(group[-1])
    return None


def crop_image(image, *, bottom_crop=0, overrides=None):
    array = np.asarray(image)
    h, w = array.shape[:2]
    if min(h, w) < 32:
        raise ValueError('Image too small: minimum side is 32 px')
    background = background_rgb(array)
    contrast_from_background = np.max(abs(array.astype(float) - background), axis=2)
    mask = contrast_from_background > 10
    if not mask.any():
        raise ValueError('All-background image has no figure content')
    if not 0 <= bottom_crop < h:
        raise ValueError('bottom-crop must be >=0 and smaller than image height')
    overrides = overrides or {}
    caption = overrides.get('caption_bbox')
    method = 'manual_spec' if caption else 'geometric_text_band'
    if bottom_crop:
        caption = [0, h - bottom_crop, w, h]
        method = 'explicit_bottom_crop'
    elif 'caption_bbox' not in overrides:
        # Caption geometry must not depend on the sensitive content mask:
        # pale plot elements must not bridge the whitespace before the caption.
        caption = caption_band(array, contrast_from_background > 25)
    if caption:
        caption = validate_bbox(caption, w, h)
        mask[caption[1]:] = False
    ys, xs = np.where(mask)
    if not len(xs):
        raise ValueError('Crop removes all figure content')
    margin = 8
    bottom_limit = caption[1] if caption else h
    bbox = [max(0, int(xs.min()) - margin), max(0, int(ys.min()) - margin),
            min(w, int(xs.max()) + 1 + margin), min(bottom_limit, int(ys.max()) + 1 + margin)]
    if caption:
        # Captioned multi-panel figures can have broad side margins. Retaining
        # their original horizontal canvas is safer than trimming to dark ink;
        # this rule uses no source-specific coordinates.
        bbox[0], bbox[2] = 0, w
    flags = list(overrides.get('quality_flags', []))
    if min(w, h) < 200:
        flags.append('low_resolution')
    if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
        flags.append('possible_truncation_at_image_edge')
    # Very weak edge contrast is a warning only, never a claim of readable text.
    gray = array.mean(axis=2)
    contrast = float(np.percentile(np.abs(np.diff(gray, axis=1)), 99))
    if contrast < 8:
        flags.append('possible_blur_or_low_contrast')
    meta = {**overrides, 'original_size': [w, h], 'background': background.tolist(),
            'crop_bbox': bbox, 'caption_bbox': caption, 'caption_detection': method if caption else None,
            'quality_flags': sorted(set(flags)),
            'quality_assessment': {'blur': 'heuristic_only', 'watermark': 'manual_review_required',
                                   'truncation': 'edge_contact_heuristic'}}
    meta['needs_clearer_source'] = overrides.get('key_elements_readable') is False
    if meta['needs_clearer_source']:
        meta['stop_reason'] = 'Key axes, legend or values are unreadable. Stop replication and request a clearer original image; do not invent missing values.'
    return image.crop(bbox), meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--bottom-crop', type=int, default=0)
    parser.add_argument('--panel')
    parser.add_argument('--bbox', help='x0,y0,x1,y1 in original-image pixels')
    args = parser.parse_args(argv)
    try:
        if bool(args.panel) != bool(args.bbox):
            raise ValueError('--panel and --bbox must be supplied together')
        if args.panel and not re.fullmatch(r'[A-Za-z0-9_-]+', args.panel):
            raise ValueError('Invalid panel id')
        image = open_rgb(args.image)
        cropped, meta = crop_image(image, bottom_crop=args.bottom_crop,
                                   overrides=read_json(args.spec) if args.spec and args.spec.exists() else None)
        outputs = {args.out / 'original_figure.png': png_bytes(cropped), args.out / 'crop.json': json_bytes(meta)}
        if args.panel:
            bbox = validate_bbox([int(n) for n in args.bbox.split(',')], *image.size)
            outputs[args.out / f'panel_{args.panel}.png'] = png_bytes(image.crop(bbox))
            meta['panels'] = [{'id': args.panel, 'bbox_px': bbox}]
            outputs[args.out / 'crop.json'] = json_bytes(meta)
        if args.spec:
            outputs[args.spec] = json_bytes(meta)
        if any(p.resolve() == args.image.resolve() for p in outputs):
            raise ValueError('Output must not overwrite source image')
        write_batch(outputs)
        print(f'crop_bbox={meta["crop_bbox"]}; caption_bbox={meta["caption_bbox"]}; quality_flags={meta["quality_flags"]} -> {args.out}')
        if meta['needs_clearer_source']:
            print(meta['stop_reason'])
            return 2
        return 0
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
