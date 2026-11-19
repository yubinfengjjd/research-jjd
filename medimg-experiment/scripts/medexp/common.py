"""Core utilities: path safety, atomic JSON/text IO, locking, and state persistence."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid


class GateError(ValueError):
    """Raised when a scientific guardrail or controller precondition is violated."""


def require(condition, message: str) -> None:
    if not condition:
        raise GateError(message)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str) -> datetime:
    require(isinstance(value, str) and value.strip(), '截止时间必须为含时区的 ISO8601 字符串')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, '截止时间必须包含时区（例如 +08:00 或 Z）')
    return dt.astimezone(timezone.utc)


def _blocked_roots() -> list[str]:
    raw = os.environ.get('MEDEXP_BLOCKED_ROOTS', '')
    roots = []
    for item in raw.split(os.pathsep):
        value = item.strip()
        if value:
            q = Path(value).expanduser().absolute()
            roots.extend((str(q).replace('\\', '/').lower(),
                          str(q.resolve()).replace('\\', '/').lower()))
    return roots


def safe_path(value) -> Path:
    p = Path(value).expanduser().absolute()
    blocked = _blocked_roots()
    for q in (p, p.resolve()):
        norm = str(q).replace('\\', '/').lower()
        require(not any(norm == r or norm.startswith(r + '/') for r in blocked),
                '禁止访问已登记的隔离根目录')
    return p.resolve()


def inside(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), '必须使用相对路径')
    p = safe_path(root / relative)
    r = root.resolve()
    require(p.is_relative_to(r) and p != r, '路径越出受管目录')
    return p


def is_windows_store_python(path: Path) -> bool:
    norm = str(path).replace('\\', '/').lower()
    return '/windowsapps/python' in norm


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with safe_path(path).open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def digest_json(data) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
    return sha256_bytes(raw)


def read_json(path: Path):
    return json.loads(safe_path(path).read_text(encoding='utf-8-sig'))


def _atomic_replace(tmp: Path, target: Path) -> None:
    deadline = time.monotonic() + 2.0
    delay = 0.01
    while True:
        try:
            os.replace(tmp, target)
            return
        except PermissionError as exc:
            if getattr(exc, 'winerror', None) not in (5, 32, 33):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(delay, remaining))
            delay = min(0.2, delay * 2)


def write_json(path: Path, data) -> None:
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, allow_nan=False, indent=2)
        fh.write('\n')
        fh.flush()
        os.fsync(fh.fileno())
    _atomic_replace(tmp, target)


def atomic_text(path: Path, body: str) -> None:
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    _atomic_replace(tmp, target)


def number(value, label: str, positive: bool = False) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
            f'{label}必须是有限数值')
    require(not positive or value > 0, f'{label}必须大于 0')
    return float(value)


@contextmanager
def locked(root: Path):
    path = safe_path(root) / '.control.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as fh:
        if path.stat().st_size == 0:
            fh.write(b'0')
            fh.flush()
        if os.name == 'nt':
            import msvcrt
            deadline = time.monotonic() + 10.0
            while True:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    require(time.monotonic() < deadline, '控制状态锁超时；请勿并发修改同一课题状态')
                    time.sleep(0.05)
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def load_state(root: Path) -> dict:
    return read_json(root / 'state.json')


def save_state(root: Path, state: dict, event: str) -> None:
    state['updated_at'] = timestamp()
    write_json(root / 'state.json', state)
    with (root / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps({
            'time': timestamp(),
            'event': event,
            'route_revision': state.get('route_revision', 1),
            'status': state.get('status'),
        }, ensure_ascii=False) + '\n')
        fh.flush()
        os.fsync(fh.fileno())
