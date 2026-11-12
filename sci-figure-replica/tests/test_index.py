from conftest import SOURCE, read_json


def test_two_entries_and_thumbnail_fallback(entry, cli):
    gallery = entry.parents[2]
    result = cli('init_entry', '--gallery', gallery, '--post-slug', 'post02', '--fig-id', 'fig02',
                 '--source', SOURCE / 'fig01.png', '--post-title', '中文 <script>alert(1)</script>',
                 '--scenario', 'diagnostic-roc')
    assert result.returncode == 0, result.stderr
    (entry / 'thumb.png').write_bytes((SOURCE / 'fig01.png').read_bytes())
    second = gallery / 'post02/figures/fig02'
    (second / 'output/replica.png').write_bytes((SOURCE / 'fig01.png').read_bytes())
    result = cli('build_index', '--gallery', gallery)
    assert result.returncode == 0, result.stderr
    entries = read_json(gallery / 'index.json')
    assert len(entries) == 2
    for item in entries:
        assert '\\' not in item['thumbnail']
        assert (gallery / item['thumbnail']).is_file()
    assert entries[0]['thumbnail'].endswith('thumb.png')
    assert entries[1]['thumbnail'].endswith('output/replica.png')
    page = (gallery / 'index.html').read_text(encoding='utf-8')
    for text in ('filter-scenario', 'filter-language', 'filter-status', '中文', 'Python机器学习AI'):
        assert text in page
    assert '<script>alert(1)</script>' not in page
    assert 'cdn.' not in page and '{{ENTRIES_JSON}}' not in page
