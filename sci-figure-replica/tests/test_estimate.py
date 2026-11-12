import csv
import json

import pytest


def test_bar_linear_and_reversed_axis():
    from estimate_data import bars_from_pixels
    assert bars_from_pixels([0, 0, 100, 100], [0, 100], [0, 20], [[0, 25], [0, 75]]) == pytest.approx([5, 15])
    assert bars_from_pixels([0, 0, 100, 100], [0, 100], [20, 0], [[100, 25], [100, 75]]) == pytest.approx([15, 5])


def test_points_and_invalid_calibration():
    from estimate_data import points_from_pixels, bars_from_pixels
    result = points_from_pixels([10, 20, 110, 220], [[10, 0], [110, 10]], [[20, 50], [220, 0]], [[60, 120]])
    assert result[0] == pytest.approx((5, 25))
    with pytest.raises(ValueError):
        bars_from_pixels([0, 0, 100, 100], [0, 0], [0, 20], [[0, 25]])


def test_bar_values_keep_signed_and_nonzero_baseline_endpoints():
    from estimate_data import bars_from_pixels
    assert bars_from_pixels([0, 0, 100, 100], [0, 100], [-10, 10], [[50, 25]]) == pytest.approx([-5])
    assert bars_from_pixels([0, 0, 100, 100], [0, 100], [10, 30], [[0, 25]]) == pytest.approx([15])


def test_colorbar_axis_orientation_and_interpolation():
    from estimate_data import color_to_value
    vertical = {'bbox': [10, 0, 20, 100], 'samples': [[0, [255, 0, 0]], [100, [0, 0, 255]]], 'orientation': 'vertical', 'high_at': 'top'}
    assert color_to_value([255, 0, 0], vertical, 0, 20) == pytest.approx(20)
    assert color_to_value([128, 0, 127], vertical, 0, 20) == pytest.approx(10, abs=.05)
    horizontal = {'bbox': [0, 10, 100, 20], 'samples': [[0, [0, 0, 255]], [100, [255, 0, 0]]], 'orientation': 'horizontal', 'high_at': 'right'}
    assert color_to_value([0, 0, 255], horizontal, 0, 20) == pytest.approx(0)
    with pytest.raises(ValueError):
        color_to_value([0, 0, 0], [0, 0, 10, 100], 0, 20)


def test_color_mapping_rejects_unrelated_invalid_and_ambiguous_colors():
    from estimate_data import color_to_value
    spec = {'bbox': [0, 0, 10, 100], 'samples': [[0, [255, 0, 0]], [100, [0, 0, 255]]]}
    with pytest.raises(ValueError, match='match'):
        color_to_value([0, 255, 0], spec, 0, 20)
    with pytest.raises(ValueError):
        color_to_value([255, 0, 0], {**spec, 'samples': [[0, [500, 0, 0]], [100, [0, 0, 255]]]}, 0, 20)
    with pytest.raises(ValueError, match='ambiguous'):
        color_to_value([255, 0, 0], {**spec, 'samples': [[0, [255, 0, 0]], [50, [0, 0, 255]], [100, [255, 0, 0]]]}, 0, 20)


def test_csv_provenance_and_unreadable_values(cli, tmp_path):
    spec = tmp_path / 'axis.json'
    spec.write_text(json.dumps({'axis_bbox': [0, 0, 100, 100], 'tick_positions': [0, 100], 'tick_values': [20, 0],
                                'bar_spans': [[100, 25], None], 'features': ['one', 'unreadable'], 'panel': 'A'}))
    out = tmp_path / 'data.csv'
    result = cli('estimate_data', '--mode', 'bars', '--spec', spec, '--out', out)
    assert result.returncode == 0, result.stderr
    rows = list(csv.DictReader(out.open(encoding='utf-8')))
    assert float(rows[0]['value']) == pytest.approx(15)
    assert rows[0]['provenance'] == 'estimated' and rows[0]['panel'] == 'A'
    assert rows[1]['value'] == 'NA' and rows[1]['uncertain_reason']


@pytest.mark.parametrize('mode', ['points', 'color'])
def test_points_and_color_cli_provenance(cli, tmp_path, mode):
    spec = tmp_path / 'spec.json'
    if mode == 'points':
        content = {'axis_bbox': [0, 0, 100, 100], 'x_ticks': [[0, 0], [100, 10]], 'y_ticks': [[0, 10], [100, 0]], 'points': [[50, 25], None]}
    else:
        content = {'colors': [[255, 0, 0], [0, 255, 0]], 'vmin': 0, 'vmax': 20,
                   'colorbar_bbox': {'bbox': [0, 0, 10, 100], 'samples': [[0, [255, 0, 0]], [100, [0, 0, 255]]]}}
    spec.write_text(json.dumps(content))
    out = tmp_path / 'data.csv'
    result = cli('estimate_data', '--mode', mode, '--spec', spec, '--out', out)
    assert result.returncode == 0, result.stderr
    rows = list(csv.DictReader(out.open(encoding='utf-8')))
    assert all(r['provenance'] == 'estimated' for r in rows)
    assert rows[1]['value'] == 'NA' and rows[1]['uncertain_reason']
    assert float(rows[0]['value']) == pytest.approx(5 if mode == 'points' else 20)
