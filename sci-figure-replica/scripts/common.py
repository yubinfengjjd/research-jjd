"""Shared local I/O; no implicit gallery writes or external code execution."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SKILL_ROOT = Path(__file__).resolve().parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_config(path=None):
    return read_json(Path(path) if path else SKILL_ROOT / 'config.json')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reject_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError(f'Refusing symlink/junction path: {part}')
    return path


def atomic_write(path, data):
    path = reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode('utf-8')
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_batch(outputs):
    """Stage every file before replacement; restore prior bytes on Python exceptions.

    This is not a power-loss-safe multi-file transaction. Single-writer use only.
    """
    previous, staged, committed = {}, {}, []
    try:
        for raw, data in outputs.items():
            path = reject_links(raw)
            previous[path] = path.read_bytes() if path.exists() else None
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
            staged[path] = Path(name)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data.encode('utf-8') if isinstance(data, str) else data)
                stream.flush()
                os.fsync(stream.fileno())
        for path, temp in staged.items():
            os.replace(temp, path)
            committed.append(path)
    except Exception:
        for path in reversed(committed):
            if previous[path] is None:
                path.unlink()
            else:
                atomic_write(path, previous[path])
        raise
    finally:
        for temp in staged.values():
            temp.unlink(missing_ok=True)


def slug(value):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value):
        raise ValueError(f'Invalid slug {value!r}; use lowercase [a-z0-9-] segments')
    return value


def entry_metadata(gallery):
    gallery = reject_links(gallery)
    if not gallery.is_dir():
        return
    for path in sorted(gallery.rglob('meta.json')):
        rel = path.relative_to(gallery)
        # A post-level parser meta and archived versions are not gallery entries.
        if len(rel.parts) != 4 or rel.parts[1] != 'figures':
            continue
        reject_links(path)
        meta = read_json(path)
        if 'id' not in meta or 'figure' not in meta:
            raise ValueError(f'Invalid figure metadata: {path}')
        yield path, meta


def cli_error(error):
    import sys
    print(f'ERROR: {error}', file=sys.stderr)
    return 1
