"""Parse untrusted post text/HTML as data. Never run extracted code."""
import argparse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from common import cli_error, json_bytes, read_json, write_batch


class VerificationPage(ValueError):
    pass


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
        self.closed = False

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children).replace('\xa0', ' ')


class Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node
        else:
            node.closed = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                node.closed = True
                self.current = node.parent
                break
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def base_meta():
    return dict.fromkeys(('title', 'account', 'author', 'publish_time', 'url', 'source_html')) | {
        'code_blocks': [], 'image_urls': []}


def parse_html(document):
    root = Document(document).root
    nodes = list(root.walk())
    content = next((n for n in nodes if n.attrs.get('id') == 'js_content'), None)
    if content is None and re.search(r'环境异常|访问过于频繁|请.*验证|captcha|verify', document, re.I):
        raise VerificationPage('检测到环境异常/验证页，请粘贴全文')
    if content is None:
        raise ValueError('Cannot identify #js_content; unsupported HTML structure, 请粘贴全文')
    if content.tag != 'div' or not content.closed:
        raise ValueError('#js_content is not a balanced, closed div; stop rather than guess')
    meta = base_meta()
    for key, element_id in {'title': 'activity-name', 'account': 'js_name',
                            'author': 'js_author_name_text', 'publish_time': 'publish_time'}.items():
        found = next((n for n in nodes if n.attrs.get('id') == element_id), None)
        meta[key] = found.text().strip() or None if found else None
    if not meta['publish_time']:
        match = re.search(r'\bvar\s+ct\s*=\s*[\'"]?(\d+)', document)
        if match:
            meta['publish_time'] = datetime.fromtimestamp(int(match[1]), timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')

    def render(node):
        if isinstance(node, str):
            return node.replace('\xa0', ' ')
        if node.tag in ('script', 'style'):
            return ''
        if node.tag == 'pre':
            lines = [n.text().strip('\n') for n in node.walk() if n.tag == 'code']
            code = '\n'.join(lines) if lines else node.text().strip('\n')
            lang = node.attrs.get('data-lang') or 'text'
            meta['code_blocks'].append({'lang': lang, 'code': code, 'index': len(meta['code_blocks']) + 1})
            fence = '`' * max(3, max((len(m[0]) + 1 for m in re.finditer(r'`+', code)), default=3))
            return f'\n\n{fence}{lang}\n{code}\n{fence}\n\n'
        if node.tag == 'img':
            url = node.attrs.get('data-src') or node.attrs.get('src')
            if url:
                url = re.sub(r'#imgIndex=.*$', '', url)
                if url not in meta['image_urls']:
                    meta['image_urls'].append(url)
                return f'\n![{node.attrs.get("alt", "image")}](<{url}>)\n'
            return ''
        if node.tag == 'br':
            return '\n'
        text = ''.join(render(c) for c in node.children)
        return text + ('\n' if node.tag in ('div', 'p', 'section', 'li', 'h1', 'h2', 'h3', 'tr', 'blockquote') else '')
    body = render(content).strip() + '\n'
    meta['figure_candidates'] = [{'index': i + 1, 'url': u, 'classification': 'unconfirmed'}
                                 for i, u in enumerate(meta['image_urls'])]
    return meta, body


def parse_text(text):
    meta = base_meta()
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    if match:
        for line in match[1].splitlines():
            key, sep, value = line.partition(':')
            if sep and key in meta:
                value = value.strip()
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
                meta[key] = value or None
    body = text[match.end():] if match else text
    opening, code = None, []
    for line in body.splitlines(keepends=True):
        if opening is None:
            found = re.match(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)[\r\n]*$', line)
            if found:
                opening = (found[1], found[2].strip().split()[0] if found[2].strip() else 'text')
                code = []
        elif re.fullmatch(r' {0,3}' + re.escape(opening[0][0]) + '{' + str(len(opening[0])) + r',}\s*', line):
            meta['code_blocks'].append({'lang': opening[1], 'code': ''.join(code).removesuffix('\n').removesuffix('\r'),
                                        'index': len(meta['code_blocks']) + 1})
            opening = None
        else:
            code.append(line)
    if opening is not None:
        raise ValueError('Unclosed fenced code; 请粘贴全文 with complete fences')
    meta['image_urls'] = re.findall(r'!\[[^\]]*\]\(<?(https?://[^\s)>]+)>?\)', body)
    meta['figure_candidates'] = [{'index': i + 1, 'url': u, 'classification': 'unconfirmed'}
                                 for i, u in enumerate(meta['image_urls'])]
    return meta, bool(match)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--url')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.input and not args.url:
        parser.error('provide --input or --url')
    try:
        if args.input:
            raw = args.input.read_bytes()
            is_html = args.input.suffix.lower() in ('.html', '.htm')
        else:
            if not re.match(r'^https?://', args.url, re.I):
                raise ValueError('URL must be HTTP(S)')
            request = Request(args.url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                                                'Accept-Language': 'zh-CN,zh;q=0.9'})
            with urlopen(request, timeout=30) as response:
                raw = response.read()
            is_html = True
        text = raw.decode('utf-8-sig')
        outputs = {}
        if is_html:
            meta, body = parse_html(text)
            meta['source_html'] = 'article.html'
            outputs[args.out / 'article.html'] = raw
            has_header = False
        else:
            meta, has_header = parse_text(text)
            body = text
        if args.url:
            meta['url'] = args.url
        meta['local_figures'] = sorted(p.name for p in args.input.parent.glob('fig[0-9]*.*')) if args.input else []
        meta['pairing_status'] = 'needs_author_confirmation'
        # Keep source Markdown byte-for-byte when it already carries frontmatter.
        header = '---\n' + '\n'.join(f'{k}: {json.dumps(meta[k], ensure_ascii=False)}' for k in
                                     ('title', 'account', 'author', 'publish_time', 'url', 'source_html')) + '\n---\n'
        outputs[args.out / 'source.md'] = raw if has_header else (header + body).encode('utf-8')
        outputs[args.out / 'meta.json'] = json_bytes(meta)
        if args.input and any(p.resolve() == args.input.resolve() for p in outputs):
            raise ValueError('Output would overwrite input source')
        write_batch(outputs)
        print(json.dumps({k: meta[k] for k in ('title', 'account', 'author', 'publish_time')}, ensure_ascii=False))
        print(f'code_blocks={len(meta["code_blocks"])} image_urls={len(meta["image_urls"])} pairing=needs_author_confirmation')
        return 0
    except VerificationPage as error:
        print(str(error))
        return 2
    except (OSError, ValueError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
