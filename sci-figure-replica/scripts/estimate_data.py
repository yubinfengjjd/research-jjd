"""Linear pixel calibration helpers; all generated CSV rows are estimated.

bars spec: axis_bbox, tick_positions, tick_values, bar_spans (start,end).
points spec: axis_bbox, x_ticks/y_ticks [[pixel,value],...], points [[x,y],...].
color spec: colors [[r,g,b],...], colorbar_bbox {bbox:[x0,y0,x1,y1],
samples:[[axis_pixel,[r,g,b]],...], orientation:vertical|horizontal,
high_at:top|bottom|left|right}, vmin, vmax. A bare spatial bbox cannot
determine an RGB/value relationship; sampled colors are required.
Optional panel/features; null observations become NA with a reason.
"""
import argparse
import csv
from io import StringIO
from pathlib import Path

import numpy as np
from common import atomic_write, cli_error, read_json


def _bbox(box):
    values = np.asarray(box, dtype=float)
    if values.shape != (4,) or not np.isfinite(values).all() or not (values[2] > values[0] and values[3] > values[1]):
        raise ValueError('Invalid axis bbox')
    return values


def _calibration(positions, values):
    p, v = np.asarray(positions, dtype=float), np.asarray(values, dtype=float)
    if p.ndim != 1 or p.size < 2 or p.shape != v.shape or not np.isfinite([p, v]).all() or len(np.unique(p)) != p.size:
        raise ValueError('Need at least two finite distinct calibration ticks')
    slope, intercept = np.polyfit(p, v, 1)
    if not np.allclose(slope * p + intercept, v, rtol=1e-4, atol=1e-6) or abs(slope) < 1e-15:
        raise ValueError('Only consistent nonconstant linear axes are supported')
    return lambda pixel: float(slope * pixel + intercept)


def bars_from_pixels(axis_bbox, tick_positions, tick_values, bar_spans):
    box = _bbox(axis_bbox)
    mapping = _calibration(tick_positions, tick_values)
    values = []
    for span in bar_spans:
        if span is None:
            values.append(None)
            continue
        if len(span) != 2 or not np.isfinite(span).all() or not all(box[0] <= p <= box[2] for p in span):
            raise ValueError('Bar spans must be start/end x pixels inside axis_bbox')
        values.append(mapping(span[1]))
    return values


def points_from_pixels(axis_bbox, x_ticks, y_ticks, points):
    box = _bbox(axis_bbox)
    x_ticks, y_ticks = np.asarray(x_ticks), np.asarray(y_ticks)
    mx, my = _calibration(x_ticks[:, 0], x_ticks[:, 1]), _calibration(y_ticks[:, 0], y_ticks[:, 1])
    result = []
    for point in points:
        if point is None:
            result.append(None)
        elif len(point) != 2 or not np.isfinite(point).all() or not (box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]):
            raise ValueError('Point outside axis_bbox')
        else:
            result.append((mx(point[0]), my(point[1])))
    return result


def color_to_value(rgb, colorbar_bbox, vmin, vmax):
    if not isinstance(colorbar_bbox, dict) or 'samples' not in colorbar_bbox:
        raise ValueError('colorbar_bbox needs sampled RGB colors and their axis positions')
    box = _bbox(colorbar_bbox['bbox'])
    orientation = colorbar_bbox.get('orientation', 'vertical')
    high_at = colorbar_bbox.get('high_at', 'top' if orientation == 'vertical' else 'right')
    if orientation not in ('vertical', 'horizontal') or high_at not in (('top', 'bottom') if orientation == 'vertical' else ('left', 'right')):
        raise ValueError('Invalid colorbar orientation/high_at')
    low, high = (box[1], box[3]) if orientation == 'vertical' else (box[0], box[2])
    samples = sorted(colorbar_bbox['samples'], key=lambda s: s[0])
    target = np.asarray(rgb, dtype=float)
    if target.shape != (3,) or not np.isfinite(target).all() or np.any((target < 0) | (target > 255)) or len(samples) < 2:
        raise ValueError('RGB must be three finite channels in [0,255]; need two samples')
    candidates = []
    for (p0, c0), (p1, c1) in zip(samples, samples[1:]):
        if not low <= p0 < p1 <= high:
            raise ValueError('Color sample positions must increase inside colorbar bbox')
        c0, c1 = np.asarray(c0, dtype=float), np.asarray(c1, dtype=float)
        delta = c1 - c0
        if (c0.shape != (3,) or c1.shape != (3,) or not np.isfinite([c0, c1]).all()
                or np.any((c0 < 0) | (c0 > 255)) or np.any((c1 < 0) | (c1 > 255)) or not delta.dot(delta)):
            raise ValueError('Invalid or duplicate sampled colors')
        t = np.clip((target - c0).dot(delta) / delta.dot(delta), 0, 1)
        distance = float(np.linalg.norm(target - (c0 + t * delta)))
        candidate = (distance, p0 + t * (p1 - p0))
        candidates.append(candidate)
    candidates.sort()
    best = candidates[0]
    max_distance = float(colorbar_bbox.get('max_rgb_distance', 25))
    if not np.isfinite(max_distance) or max_distance < 0:
        raise ValueError('Invalid maximum RGB match distance')
    if best[0] > max_distance:
        raise ValueError('No reliable colorbar match for this RGB')
    if any(abs(distance - best[0]) < 1e-6 and abs(position - best[1]) > 1 for distance, position in candidates[1:]):
        raise ValueError('Colorbar mapping is ambiguous for this RGB')
    if not np.isfinite([vmin, vmax]).all() or vmax <= vmin:
        raise ValueError('vmax must exceed finite vmin')
    fraction = (best[1] - low) / (high - low)
    if high_at in ('top', 'left'):
        fraction = 1 - fraction
    return float(vmin + fraction * (vmax - vmin))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['bars', 'points', 'color'], required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.spec.resolve() == args.out.resolve():
            raise ValueError('Output must not overwrite specification')
        spec = read_json(args.spec)
        color_reasons = []
        if args.mode == 'bars':
            values = bars_from_pixels(spec['axis_bbox'], spec['tick_positions'], spec['tick_values'], spec['bar_spans'])
        elif args.mode == 'points':
            values = points_from_pixels(spec['axis_bbox'], spec['x_ticks'], spec['y_ticks'], spec['points'])
        else:
            values = []
            for color in spec['colors']:
                try:
                    value = color_to_value(color, spec['colorbar_bbox'], spec['vmin'], spec['vmax']) if color is not None else None
                    color_reasons.append('pixel/color interpolation; not original data' if value is not None else 'unreadable observation')
                except ValueError as error:
                    value = None
                    color_reasons.append(str(error))
                values.append(value)
        features = spec.get('features', [str(i + 1) for i in range(len(values))])
        if len(features) != len(values):
            raise ValueError('features length must match observations')
        out = StringIO(newline='')
        writer = csv.DictWriter(out, fieldnames=['panel', 'feature', 'value', 'x', 'y', 'provenance', 'uncertain_reason'])
        writer.writeheader()
        for index, (feature, value) in enumerate(zip(features, values)):
            row = {'panel': spec.get('panel', ''), 'feature': feature, 'provenance': 'estimated',
                   'uncertain_reason': color_reasons[index] if color_reasons else ('pixel/color interpolation; not original data' if value is not None else 'unreadable observation')}
            if args.mode == 'points' and value is not None:
                row.update(value=value[0], x=value[0], y=value[1])
            else:
                row['value'] = 'NA' if value is None else value
            writer.writerow(row)
        atomic_write(args.out, out.getvalue())
        print(f'{len(values)} estimated rows; mode={args.mode} -> {args.out}')
        return 0
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
