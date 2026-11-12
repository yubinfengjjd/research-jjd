import json

from conftest import SOURCE, read_json


def test_real_html_and_markdown(cli, tmp_path):
    expected = read_json(SOURCE / 'meta.json')
    for name in ('article_raw.html', 'source.md'):
        out = tmp_path / name
        result = cli('parse_post', '--input', SOURCE / name, '--out', out, '--url', expected['url'])
        assert result.returncode == 0, result.stderr
        meta = read_json(out / 'meta.json')
        for key in ('title', 'account', 'author', 'publish_time', 'url'):
            assert meta[key] == expected[key]
        assert len(meta['code_blocks']) == 4
        assert [b['lang'] for b in meta['code_blocks']] == expected['code_languages']
        if name.endswith('html'):
            assert len(meta['image_urls']) > 0
            assert all('#imgIndex=' not in u for u in meta['image_urls'])
            assert (out / 'article.html').read_bytes() == (SOURCE / name).read_bytes()
        else:
            assert (out / 'source.md').read_bytes() == (SOURCE / name).read_bytes()
    from parse_post import parse_html, parse_text
    html_meta, _ = parse_html((SOURCE / 'article_raw.html').read_text(encoding='utf-8'))
    md_meta, _ = parse_text((SOURCE / 'source.md').read_text(encoding='utf-8'))
    # The supplied Markdown archive strips trailing spaces on three code lines.
    # Preserve raw HTML code, compare content without silently changing either source.
    assert ['\n'.join(line.rstrip() for line in b['code'].splitlines()) for b in html_meta['code_blocks']] == [b['code'] for b in md_meta['code_blocks']]


def test_balanced_html_and_code_lines():
    from parse_post import parse_html
    meta, body = parse_html('''<h1 id="activity-name"><span>标题</span></h1>
    <div id="js_content"><div>内层</div><pre class="code-snippet__js" data-lang="python">
    <code>x = 1</code><code>&nbsp;&nbsp;print(&quot;&lt;div&gt;&quot;)</code></pre>
    <img data-src="https://x/a.png#imgIndex=2"></div><p>OUTSIDE</p>''')
    assert meta['code_blocks'] == [{'lang': 'python', 'code': 'x = 1\n  print("<div>")', 'index': 1}]
    assert '内层' in body and 'OUTSIDE' not in body
    assert meta['image_urls'] == ['https://x/a.png']
    assert meta['author'] is None


def test_plain_text_no_invented_code(cli, tmp_path):
    source = tmp_path / 'input.txt'
    text = '标题\nprint(1)\n  不要强拆代码\n'
    source.write_text(text, encoding='utf-8')
    result = cli('parse_post', '--input', source, '--out', tmp_path / 'out')
    assert result.returncode == 0, result.stderr
    meta = read_json(tmp_path / 'out/meta.json')
    assert meta['code_blocks'] == [] and meta['title'] is None
    assert (tmp_path / 'out/source.md').read_text(encoding='utf-8').endswith(text)


def test_blocked_and_bad_html(cli, tmp_path):
    for html in ('<html>环境异常 请完成验证</html>', '<div id="js_content">unclosed'):
        source = tmp_path / 'bad.html'
        source.write_text(html, encoding='utf-8')
        result = cli('parse_post', '--input', source, '--out', tmp_path / 'out')
        assert result.returncode != 0
        assert not (tmp_path / 'out').exists()
    from parse_post import VerificationPage, parse_html
    import pytest
    with pytest.raises(VerificationPage, match='请粘贴全文'):
        parse_html('<html>环境异常 验证</html>')


def test_url_headers_and_verification(monkeypatch, cli, tmp_path):
    import parse_post
    captured = {}
    class Response:
        headers = type('Headers', (), {'get_content_charset': lambda self: 'utf-8'})()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return '<html>环境异常 验证</html>'.encode()
    def open_url(request, timeout):
        captured.update(dict(request.header_items()))
        return Response()
    monkeypatch.setattr(parse_post, 'urlopen', open_url)
    assert parse_post.main(['--url', 'https://example.org/a', '--out', str(tmp_path / 'out')]) == 2
    assert 'Mozilla' in captured['User-agent']
    assert captured['Accept-language'].startswith('zh-CN')
    assert not (tmp_path / 'out').exists()
