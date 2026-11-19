"""Dependency-free package check for medimg-experiment (v3)."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys


def check(root) -> dict:
    root = Path(root).resolve()
    text = (root / 'SKILL.md').read_text(encoding='utf-8')
    match = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not match:
        raise ValueError('Missing YAML frontmatter in SKILL.md')
    meta = {}
    for line in match[1].splitlines():
        key, sep, value = line.partition(':')
        if not sep or key not in ('name', 'description') or not value.strip():
            raise ValueError(f'Unsupported or empty frontmatter field: {line}')
        meta[key] = value.strip()
    if set(meta) != {'name', 'description'} or meta['name'] != 'medimg-experiment':
        raise ValueError('Skill identity mismatch')
    if len(meta['description']) > 1024 or '[TODO:' in text:
        raise ValueError('Invalid description or unfinished TODO')

    md_files = [root / 'SKILL.md', *(root / 'references').glob('*.md')]
    for md in md_files:
        for link in re.findall(r'\]\(([^)]+)\)', md.read_text(encoding='utf-8')):
            if '://' not in link and not link.startswith('#'):
                target = (md.parent / link.split('#')[0]).resolve()
                if not target.is_relative_to(root) or not target.exists():
                    raise ValueError(f'Broken local reference in {md.name}: {link}')

    yaml_text = (root / 'agents' / 'openai.yaml').read_text(encoding='utf-8')
    if '$medimg-experiment' not in yaml_text or 'allow_implicit_invocation: true' not in yaml_text:
        raise ValueError('agents/openai.yaml missing invocation metadata')

    cfg_tpl = json.loads((root / 'assets' / 'study-config-template.json').read_text(encoding='utf-8'))
    if cfg_tpl.get('schema_version') != 3:
        raise ValueError('study-config-template.json must use schema_version=3')

    required_scripts = [
        'controller.py',
        'check_package.py',
        'medexp/__init__.py',
        'medexp/common.py',
        'medexp/config.py',
        'medexp/process.py',
        'medexp/stats.py',
        'medexp/plan_sync.py',
        'medexp/study.py',
    ]
    for name in required_scripts:
        if not (root / 'scripts' / name).is_file():
            raise ValueError(f'Missing runtime file: scripts/{name}')

    for name in ('synth_data.py', 'audit_split.py', 'train.py', 'evaluate_test.py'):
        if not (root / 'assets' / 'synthetic' / name).is_file():
            raise ValueError(f'Missing synthetic demo file: assets/synthetic/{name}')

    return {
        'valid': True,
        'name': meta['name'],
        'schema_version': 3,
        'references_checked': len(md_files),
    }


if __name__ == '__main__':
    try:
        print(json.dumps(check(sys.argv[1]), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}, ensure_ascii=False))
        sys.exit(1)
