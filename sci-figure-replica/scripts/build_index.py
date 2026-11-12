"""Build offline gallery indexes from current figure entries only."""
import argparse
import json
from pathlib import Path

from common import SKILL_ROOT, cli_error, entry_metadata, json_bytes, load_config, utc_now, write_batch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gallery', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args(argv)
    try:
        load_config(args.config)
        entries = []
        for path, meta in entry_metadata(args.gallery):
            entry = path.parent
            candidates = [entry / 'thumb.png', entry / 'output/replica.png']
            source = meta.get('files', {}).get('source_image')
            if source:
                candidates.append(entry / source)
            candidates.extend(sorted((entry / 'source').glob('fig*.png')))
            thumb = next((p for p in candidates if p.is_file()), None)
            if thumb is None:
                raise ValueError(f'No thumbnail/replica/source image for {entry}')
            gallery = args.gallery.absolute()
            thumb = thumb.absolute()
            # Metadata may not inject external paths or file URLs into the offline page.
            if not thumb.resolve().is_relative_to(gallery.resolve()):
                raise ValueError(f'Thumbnail escapes gallery: {thumb}')
            rel = entry.absolute().relative_to(gallery)
            links, pending = {}, []
            for name, file, label in (
                    ('replica', 'output/replica.png', '复刻 PNG'),
                    ('compare', 'compare/side_by_side.png', '并排对比'),
                    ('readme', 'README.md', 'README')):
                if (entry / file).is_file():
                    links[name] = (rel / file).as_posix()
                else:
                    pending.append({'key': name, 'label': label})
            entries.append({**meta, 'title': meta['post'].get('title'),
                            'thumbnail': thumb.relative_to(gallery).as_posix(),
                            'links': links, 'pending': pending})
        generated = utc_now()
        # Escape HTML delimiters in JSON script data; render values using textContent.
        payload = json.dumps(entries, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        payload = payload.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        template = (SKILL_ROOT / 'assets/gallery_template.html').read_text(encoding='utf-8')
        page = template.replace('{{ENTRIES_JSON}}', payload).replace('{{GENERATED_AT}}', generated)
        write_batch({args.gallery / 'index.json': json_bytes(entries), args.gallery / 'index.html': page})
        print(f'indexed {len(entries)} entries -> {args.gallery / "index.json"}, {args.gallery / "index.html"}')
        return 0
    except (OSError, ValueError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
