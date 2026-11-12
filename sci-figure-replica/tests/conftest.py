"""Unit-test artifacts use a unique session temporary root.

test-gallery is reserved for explicitly requested integration entries.
"""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

import pytest

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL
SOURCE = ROOT / 'samples/post01/source'
sys.path.insert(0, str(SKILL / 'scripts'))


def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = Path(tempfile.gettempdir()) / f'sci-figure-replica-pytest-{uuid.uuid4().hex}'


@pytest.fixture
def cli(tmp_path):
    installer = tmp_path / "standalone-installer" / "install.py"
    installer.parent.mkdir()
    shutil.copyfile(SKILL / "install.py", installer)
    def run(script, *args):
        path = installer if script == 'install' else SKILL / 'scripts' / (script + '.py')
        return subprocess.run([sys.executable, '-X', 'utf8', str(path), *map(str, args)],
                              capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    return run


@pytest.fixture
def entry(tmp_path, cli):
    gallery = tmp_path / '画廊 space'
    result = cli('init_entry', '--gallery', gallery, '--post-slug', 'post01',
                 '--fig-id', 'fig01', '--source', SOURCE / 'fig01.png')
    assert result.returncode == 0, result.stderr
    return gallery / 'post01/figures/fig01'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))
