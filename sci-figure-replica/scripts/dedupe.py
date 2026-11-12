"""Match post+image provenance and archive a previous entry version."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from common import atomic_write, cli_error, entry_metadata, json_bytes, read_json, reject_links, sha256, utc_now


def post_key(url=None, title=None, account=None):
    if url:
        parts = urlsplit(url.strip())
        if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username:
            raise ValueError('Invalid post URL')
        scheme = parts.scheme.lower()
        port = parts.port
        host = parts.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if port and not (scheme == 'https' and port == 443 or scheme == 'http' and port == 80):
            host += f':{port}'
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in ('wxfrom', 'scene', 'from', 'isappinstalled')]
        canonical = urlunsplit((scheme, host, parts.path or '/', urlencode(sorted(query)), ''))
    else:
        if not title or not account:
            raise ValueError('Without URL provide both --post-title and --account')
        canonical = json.dumps([title.strip(), account.strip()], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]


def archive_entry(entry):
    entry = reject_links(entry)
    meta = read_json(entry / 'meta.json')
    history = entry / 'history'
    history.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    final = history / stamp
    stage = Path(tempfile.mkdtemp(prefix='.pending-', dir=history))
    moved, created, replaced = [], [], []
    names = ('meta.json', 'code', 'data', 'output', 'compare', 'README.md', 'thumb.png', 'qa_report.md', 'run.log')
    try:
        for name in names:
            source = reject_links(entry / name)
            if source.exists():
                os.rename(source, stage / name)
                moved.append(name)
        for name in ('code', 'data', 'output', 'compare'):
            (entry / name).mkdir()
            created.append(name)
        meta['version'] += 1
        meta['updated_at'] = utc_now()
        meta['status'] = 'draft'
        meta['files'] = {k: v for k, v in meta['files'].items() if isinstance(v, str) and v.startswith('source/')}
        replaced.append('README.md')
        atomic_write(entry / 'README.md', f'# {meta["id"]}\n\n版本 {meta["version"]}：待重新复刻、QA 与作者签核。\n\n'
                     f'旧版本： [history/{stamp}/README.md](history/{stamp}/README.md)\n'
                     'source/ 和 original_code/ 保留；数据、代码及成图待重新生成。\n')
        replaced.append('meta.json')
        atomic_write(entry / 'meta.json', json_bytes(meta))
        os.rename(stage, final)
        return final
    except Exception:
        for name in replaced:
            (entry / name).unlink(missing_ok=True)
        for name in created:
            (entry / name).rmdir()
        for name in reversed(moved):
            os.rename(stage / name, entry / name)
        stage.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gallery', type=Path, required=True)
    parser.add_argument('--post-url')
    parser.add_argument('--post-title')
    parser.add_argument('--account')
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        pkey = post_key(args.post_url, args.post_title, args.account)
        digest = sha256(args.image)
        matches = []
        for path, meta in entry_metadata(args.gallery):
            post = meta['post']
            if not post.get('url') and not (post.get('title') and post.get('account')):
                continue  # Unknown provenance is not evidence of the same post.
            if meta['source_image_sha256'] == digest and post_key(post.get('url'), post.get('title'), post.get('account')) == pkey:
                matches.append(path.parent)
        if len(matches) > 1:
            raise ValueError(f'Ambiguous duplicate entries: {matches}; resolve manually')
        result = {'decision': 'match' if matches else 'new', 'post_key': pkey,
                  'figure_key': digest[:12], 'dry_run': args.dry_run}
        if matches:
            result['entry'] = str(matches[0])
            if not args.dry_run:
                result['history'] = str(archive_entry(matches[0]))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
