import hashlib
import json

import pytest
from conftest import SOURCE, read_json


def test_init_and_duplicate(entry, cli):
    for name in ('source', 'original_code', 'code', 'data', 'output', 'compare', 'history'):
        assert (entry / name).is_dir()
    meta = read_json(entry / 'meta.json')
    assert meta['source_image_sha256'] == hashlib.sha256((SOURCE / 'fig01.png').read_bytes()).hexdigest()
    assert meta['figure']['canvas_px'] == [893, 579]
    assert meta['post']['account'] == 'Python机器学习AI'
    assert meta['status'] == 'draft' and meta['version'] == 1
    assert meta['scenarios']['primary'] == ['other']
    before = (entry / 'meta.json').read_bytes()
    result = cli('init_entry', '--gallery', entry.parents[2], '--post-slug', 'post01',
                 '--fig-id', 'fig01', '--source', SOURCE / 'fig01.png')
    assert result.returncode != 0 and 'dedupe' in result.stderr
    assert (entry / 'meta.json').read_bytes() == before


@pytest.mark.parametrize('slug', ['../escape', '中文', 'Upper', 'a/b', 'a_b', '-'])
def test_invalid_slug(cli, tmp_path, slug):
    result = cli('init_entry', '--gallery', tmp_path / 'g', '--post-slug', slug,
                 '--fig-id', 'fig01', '--source', SOURCE / 'fig01.png')
    assert result.returncode != 0 and not (tmp_path / 'g').exists()


def test_explicit_gallery_required(cli):
    for script in ('init_entry', 'build_index', 'dedupe'):
        result = cli(script)
        assert result.returncode == 2 and '--gallery' in result.stderr


def test_dedupe_dry_run_migration_and_index(entry, cli):
    gallery = entry.parents[2]
    for name in ('code/replica.py', 'data/estimated_data.csv', 'output/replica.png', 'compare/side_by_side.png'):
        (entry / name).write_text('old artifact', encoding='utf-8')
    before = {p.relative_to(entry).as_posix(): p.read_bytes() for p in entry.rglob('*') if p.is_file()}
    meta = read_json(entry / 'meta.json')
    args = ['--gallery', gallery, '--post-url', meta['post']['url'], '--image', SOURCE / 'fig01.png']
    result = cli('dedupe', *args, '--dry-run')
    assert result.returncode == 0 and 'match' in result.stdout
    assert before == {p.relative_to(entry).as_posix(): p.read_bytes() for p in entry.rglob('*') if p.is_file()}
    result = cli('dedupe', *args)
    assert result.returncode == 0, result.stderr
    current = read_json(entry / 'meta.json')
    assert current['version'] == 2 and current['status'] == 'draft'
    histories = list((entry / 'history').iterdir())
    assert len(histories) == 1
    assert read_json(histories[0] / 'meta.json')['version'] == 1
    for name in ('code', 'data', 'output', 'compare'):
        assert (histories[0] / name).is_dir() and (entry / name).is_dir()
        assert not list((entry / name).iterdir())
    assert (entry / 'source/fig01.png').read_bytes() == (SOURCE / 'fig01.png').read_bytes()
    result = cli('build_index', '--gallery', gallery)
    assert result.returncode == 0, result.stderr
    assert len(read_json(gallery / 'index.json')) == 1


def test_url_normalization_and_title_fallback():
    from dedupe import post_key
    assert post_key('HTTPS://Example.COM:443/a?b=2&a=1#x') == post_key('https://example.com/a?a=1&b=2')
    assert post_key(None, '标题', '公众号') == post_key('', '标题', '公众号')
    assert post_key(None, '标题', '公众号') != post_key(None, '标题2', '公众号')


def test_dedupe_new(entry, cli):
    result = cli('dedupe', '--gallery', entry.parents[2], '--post-url', 'https://example.org/new',
                 '--image', SOURCE / 'fig01.png', '--dry-run')
    assert result.returncode == 0 and 'new' in result.stdout


def test_dedupe_rollback(entry, monkeypatch):
    import dedupe
    (entry / 'code/old.py').write_text('old')
    before = (entry / 'meta.json').read_bytes()
    def fail(*args, **kwargs):
        raise OSError('simulated disk failure')
    monkeypatch.setattr(dedupe, 'atomic_write', fail)
    with pytest.raises(OSError, match='simulated'):
        dedupe.archive_entry(entry)
    assert (entry / 'meta.json').read_bytes() == before
    assert (entry / 'code/old.py').read_text() == 'old'
    assert not list((entry / 'history').iterdir())


def test_dedupe_first_move_failure_preserves_metadata(entry, monkeypatch):
    import dedupe
    before = (entry / 'meta.json').read_bytes()
    readme = (entry / 'README.md').read_bytes()
    def fail(*args):
        raise OSError('simulated first move failure')
    monkeypatch.setattr(dedupe.os, 'rename', fail)
    with pytest.raises(OSError, match='first move'):
        dedupe.archive_entry(entry)
    assert (entry / 'meta.json').read_bytes() == before
    assert (entry / 'README.md').read_bytes() == readme


def test_dedupe_ignores_unidentifiable_other_entry(entry, cli):
    other = entry.parents[2] / 'unknown/figures/fig01'
    other.mkdir(parents=True)
    meta = read_json(entry / 'meta.json')
    meta['post'] = dict.fromkeys(meta['post'])
    (other / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
    result = cli('dedupe', '--gallery', entry.parents[2], '--post-url', meta['post']['url'] or 'https://example.org/new',
                 '--image', SOURCE / 'fig01.png', '--dry-run')
    assert result.returncode == 0, result.stderr
    assert 'new' in result.stdout
