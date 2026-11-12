import csv
import subprocess
import sys

import pytest
from PIL import Image
from conftest import SKILL, SOURCE


@pytest.mark.parametrize('name,number', [('bar_inset', '06'), ('beeswarm', '07'), ('radial', '08')])
def test_example_exports_and_comparison(name, number, tmp_path):
    example = SKILL / 'examples/single-panel' / name
    result = subprocess.run([sys.executable, '-X', 'utf8', str(example / 'replica.py'), '--out', str(tmp_path)], capture_output=True, text=True, encoding='utf-8', timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    for ext in ('png', 'pdf', 'svg'):
        path = tmp_path / f'output/replica.{ext}'
        assert path.stat().st_size > 100
    with Image.open(tmp_path / 'output/replica.png') as replica, Image.open(SOURCE / f'article_images/img{number}.png') as original, Image.open(tmp_path / 'compare/side_by_side.png') as compare:
        assert abs((replica.width / replica.height) / (original.width / original.height) - 1) <= .02
        assert max(replica.size) >= 2000
        height = max(replica.height, original.height)
        assert compare.size == (round(original.width * height / original.height) + replica.width + 24, height + 60)
    assert '<text' in (tmp_path / 'output/replica.svg').read_text(encoding='utf-8')
    rows = list(csv.DictReader((example / 'estimated_data.csv').open(encoding='utf-8')))
    assert all(r['provenance'] == 'estimated' for r in rows)
    if name == 'beeswarm':
        counts = {}
        for row in rows:
            counts[row['feature']] = counts.get(row['feature'], 0) + 1
        assert len(counts) == 13 and all(150 <= n <= 200 for n in counts.values())
    else:
        assert len(rows) == 13
        assert rows[0]['shap'] == ('17.4089' if name == 'bar_inset' else '17.409')
