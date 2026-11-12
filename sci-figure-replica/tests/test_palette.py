from PIL import Image, ImageDraw
from conftest import read_json
from conftest import SOURCE


def test_palette_separates_ink_and_background_and_probes(cli, tmp_path):
    image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 10, 89, 89), fill='#c40035')
    draw.rectangle((100, 10, 169, 89), fill='#2f84b1')
    draw.line((10, 90, 190, 90), fill='black', width=2)
    path = tmp_path / 'source.png'
    image.save(path)
    probes = tmp_path / 'probes.json'
    probes.write_text('[{"name":"high","x":30,"y":30}]')
    out = tmp_path / 'palette.json'
    result = cli('sample_palette', '--image', path, '--out', out, '--probes', probes)
    assert result.returncode == 0, result.stderr
    meta = read_json(out)
    assert meta['background']['hex'] == '#ffffff'
    data = {p['hex'] for p in meta['dominant'] if p['role'] == 'data'}
    assert {'#c40035', '#2f84b1'} <= data
    assert meta['probes'][0]['rgb'] == [196, 0, 53]
    assert meta['diverging_stops'][0] == '#2f84b1'
    assert meta['diverging_stops'][-1] == '#c40035'
    assert abs(sum(p['proportion'] for p in meta['dominant']) - 1) < 1e-6


def test_real_palette_does_not_lose_blue_to_ink_quantization(cli, tmp_path):
    out = tmp_path / 'palette.json'
    result = cli('sample_palette', '--image', SOURCE / 'article_images/img06.png', '--out', out)
    assert result.returncode == 0, result.stderr
    data = [p['rgb'] for p in read_json(out)['dominant'] if p['role'] == 'data']
    assert any(b - r > 60 for r, g, b in data)
    assert any(r - b > 60 for r, g, b in data)
