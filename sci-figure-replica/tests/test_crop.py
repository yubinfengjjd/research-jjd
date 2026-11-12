import hashlib

import pytest
from PIL import Image, ImageDraw
from conftest import SOURCE, read_json


def test_crop_borders_caption_and_panel(cli, tmp_path):
    path = tmp_path / 'input.png'
    image = Image.new('RGB', (300, 240), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 20, 269, 169), fill='#c40035')
    for y in (205, 217, 229):
        draw.line((10, y, 289, y), fill='black', width=3)
    image.save(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    out = tmp_path / 'out'
    result = cli('crop_figure', '--image', path, '--out', out,
                 '--panel', 'A', '--bbox', '30,20,270,170')
    assert result.returncode == 0, result.stderr
    meta = read_json(out / 'crop.json')
    assert meta['original_size'] == [300, 240]
    assert meta['caption_bbox'][1] == 204  # PIL centers a 3-pixel line on y=205.
    # Captioned figures retain horizontal canvas; content gets 8 px padding.
    assert meta['crop_bbox'] == [0, 12, 300, 178]
    assert Image.open(out / 'panel_A.png').size == (240, 150)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('number', ['06', '07', '08'])
def test_real_single_panels_have_no_caption(cli, tmp_path, number):
    result = cli('crop_figure', '--image', SOURCE / f'article_images/img{number}.png', '--out', tmp_path)
    assert result.returncode == 0, result.stderr
    assert read_json(tmp_path / 'crop.json')['caption_bbox'] is None


def test_real_fig01_caption(cli, tmp_path):
    result = cli('crop_figure', '--image', SOURCE / 'fig01.png', '--out', tmp_path)
    assert result.returncode == 0, result.stderr
    meta = read_json(tmp_path / 'crop.json')
    assert 510 <= meta['caption_bbox'][1] <= 525
    assert meta['crop_bbox'][3] <= 510
    x0, _, x1, y1 = meta['crop_bbox']
    assert x0 <= 5 and x1 >= 888
    assert y1 <= meta['caption_bbox'][1]


@pytest.mark.parametrize('color', ['#f3f7fb', '#303030'])
def test_crop_preserves_light_and_dark_content_on_all_four_edges(cli, tmp_path, color):
    image = Image.new('RGB', (200, 180), 'white')
    draw = ImageDraw.Draw(image)
    boxes = [(2, 70, 9, 90), (190, 70, 197, 90),
             (80, 2, 100, 9), (80, 170, 100, 177)]
    for box in boxes:
        draw.rectangle(box, fill=color)
    path = tmp_path / 'edges.png'
    image.save(path)
    result = cli('crop_figure', '--image', path, '--out', tmp_path / 'out')
    assert result.returncode == 0, result.stderr
    x0, y0, x1, y1 = read_json(tmp_path / 'out/crop.json')['crop_bbox']
    assert x0 <= 2 and y0 <= 2 and x1 >= 198 and y1 >= 178
    with Image.open(tmp_path / 'out/original_figure.png') as cropped:
        for left, top, _, _ in boxes:
            assert cropped.getpixel((left - x0, top - y0)) == image.getpixel((left, top))


def test_bottom_crop_overrides_caption_detection_without_changing_source(cli, tmp_path):
    image = Image.new('RGB', (200, 180), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 179, 90), fill='red')
    draw.rectangle((10, 130, 189, 170), fill='blue')
    path = tmp_path / 'manual.png'
    image.save(path)
    before = path.read_bytes()
    result = cli('crop_figure', '--image', path, '--out', tmp_path / 'out', '--bottom-crop', 60)
    assert result.returncode == 0, result.stderr
    meta = read_json(tmp_path / 'out/crop.json')
    assert meta['caption_bbox'] == [0, 120, 200, 180]
    assert meta['caption_detection'] == 'explicit_bottom_crop'
    assert meta['crop_bbox'][3] <= 120
    assert path.read_bytes() == before


@pytest.mark.parametrize('kind', ['corrupt', 'white', 'tiny'])
def test_reject_unusable_images(cli, tmp_path, kind):
    path = tmp_path / 'input.png'
    if kind == 'corrupt':
        path.write_bytes(b'not a png')
    else:
        Image.new('RGB', (8, 8) if kind == 'tiny' else (100, 100), 'white').save(path)
    assert cli('crop_figure', '--image', path, '--out', tmp_path / 'out').returncode != 0


def test_crop_rejects_source_overwrite(cli, tmp_path):
    path = tmp_path / 'original_figure.png'
    image = Image.new('RGB', (100, 100), 'white')
    ImageDraw.Draw(image).rectangle((20, 20, 80, 80), fill='red')
    image.save(path)
    before = path.read_bytes()
    assert cli('crop_figure', '--image', path, '--out', tmp_path).returncode != 0
    assert path.read_bytes() == before


def test_separated_bottom_gray_plot_is_not_caption(cli, tmp_path):
    image = Image.new('RGB', (400, 300), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 380, 180), fill='red')
    draw.rectangle((20, 240, 380, 270), fill='gray')
    path = tmp_path / 'plot.png'
    image.save(path)
    result = cli('crop_figure', '--image', path, '--out', tmp_path / 'out')
    assert result.returncode == 0, result.stderr
    meta = read_json(tmp_path / 'out/crop.json')
    assert meta['caption_bbox'] is None
    assert meta['crop_bbox'][3] == 279  # 8 px content safety margin.
