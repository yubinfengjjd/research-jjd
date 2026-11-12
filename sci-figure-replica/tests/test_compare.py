from PIL import Image


def test_compare_equal_height_and_overlay(cli, tmp_path):
    original, replica = tmp_path / 'a.png', tmp_path / 'b.png'
    Image.new('RGB', (100, 50), 'red').save(original)
    Image.new('RGB', (60, 100), 'blue').save(replica)
    out, overlay = tmp_path / 'side.png', tmp_path / 'overlay.png'
    result = cli('make_compare', '--original', original, '--replica', replica,
                 '--out', out, '--overlay', overlay)
    assert result.returncode == 0, result.stderr
    with Image.open(out) as img:
        assert img.width == 200 + 24 + 60
        assert img.height > 100
        assert img.getpixel((200, img.height - 2)) == (255, 255, 255)
        assert img.getpixel((199, img.height - 2)) == (255, 0, 0)
        assert img.getpixel((224, img.height - 2)) == (0, 0, 255)
    with Image.open(overlay) as img:
        assert img.size == (100, 50) and img.getpixel((1, 1)) == (127, 0, 127)


def test_missing_and_corrupt_preserve_outputs(cli, tmp_path):
    good = tmp_path / 'good.png'
    Image.new('RGB', (20, 10), 'red').save(good)
    out = tmp_path / 'out.png'
    for bad in (tmp_path / 'missing.png', tmp_path / 'bad.png'):
        if bad.name == 'bad.png':
            bad.write_bytes(b'broken')
        result = cli('make_compare', '--original', good, '--replica', bad, '--out', out)
        assert result.returncode != 0 and not out.exists()
