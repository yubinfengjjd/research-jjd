"""Copy a staged skill with a SHA-256 installation manifest; dry-run never writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def reject_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError(f'Refusing symlink/junction: {part}')
    return path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files_under(root):
    for path in sorted(root.rglob('*')):
        reject_links(path)
        if path.is_file():
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--clean', action='store_true', help='Explicitly remove target-only files')
    args = parser.parse_args(argv)
    stage, backup = None, None
    try:
        source, target = reject_links(args.source).resolve(), reject_links(args.target).resolve()
        if not source.is_dir():
            raise ValueError(f'Missing source directory: {source}')
        if source == target or source.is_relative_to(target) or target.is_relative_to(source):
            raise ValueError('Source and target directories must be disjoint')
        if target.exists() and not target.is_dir():
            raise ValueError('Target is not a directory')
        source_files = [p for p in files_under(source) if not any(part in ('__pycache__', '.pytest_cache') for part in p.relative_to(source).parts)
                        and p.name != 'installation-manifest.json' and p.suffix != '.pyc']
        relatives = {p.relative_to(source) for p in source_files}
        extras = [p.relative_to(target) for p in files_under(target)] if target.exists() else []
        extras = [p for p in extras if p not in relatives and p.name != 'installation-manifest.json']
        for path in source_files:
            rel = path.relative_to(source)
            print(f'{"OVERWRITE" if (target / rel).exists() else "COPY"} {rel.as_posix()}')
        if args.clean:
            for rel in extras:
                print(f'REMOVE {rel.as_posix()}')
        print(f'{"DRY-RUN" if args.dry_run else "INSTALL"} files={len(source_files)} source={source} target={target} clean={args.clean}')
        if args.dry_run:
            return 0
        permanent_backup = None
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            permanent_backup = reject_links(Path(__file__).resolve().parent / 'global-backups' / stamp / target.name)
            permanent_backup.parent.mkdir(parents=True, exist_ok=False)
            shutil.copytree(target, permanent_backup)
            for old in files_under(target):
                if digest(old) != digest(permanent_backup / old.relative_to(target)):
                    raise ValueError(f'Backup hash mismatch: {old}')
            print(f'BACKUP {permanent_backup}')
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.' + target.name + '-stage-', dir=target.parent))
        if target.exists() and not args.clean:
            shutil.copytree(target, stage, dirs_exist_ok=True)
        entries = []
        for path in source_files:
            rel = path.relative_to(source)
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            sha = digest(path)
            if digest(dest) != sha:
                raise ValueError(f'Copy hash mismatch: {rel}')
            entries.append({'path': rel.as_posix(), 'source': str(path), 'target': str(target / rel), 'sha256': sha})
        manifest = {'source': str(source), 'target': str(target), 'installed_at': datetime.now(timezone.utc).isoformat(),
                    'previous_backup': str(permanent_backup) if permanent_backup else None, 'files': entries}
        (stage / 'installation-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix='.' + target.name + '-backup-', dir=target.parent))
            backup.rmdir()
            os.rename(target, backup)
        try:
            os.rename(stage, target)
            stage = None
        except Exception:
            if backup is not None:
                os.rename(backup, target)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        print(f'MANIFEST {target / "installation-manifest.json"}; files={len(entries)}')
        return 0
    except (OSError, ValueError) as error:
        import sys
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    finally:
        if stage is not None:
            shutil.rmtree(stage)


if __name__ == '__main__':
    raise SystemExit(main())
