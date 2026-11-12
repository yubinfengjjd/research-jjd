"""T4 live runtime and boundary contracts. No downloads or real gallery writes."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import warnings

import pytest
from PIL import Image, ImageDraw, ImageFilter
from conftest import SKILL, SOURCE, read_json

sys.path.insert(0, str(SKILL / 'templates'))


def test_r_example_live(cli, tmp_path):
    example = tmp_path / 'examples/r-simple'
    shutil.copytree(SKILL / 'examples/r-simple', example,
                    ignore=shutil.ignore_patterns('output', 'compare', 'run.log', 'stdout.txt', 'stderr.txt', 'sessionInfo.txt'))
    (tmp_path / 'templates').mkdir()
    shutil.copyfile(SKILL / 'templates/r_style.R', tmp_path / 'templates/r_style.R')
    result = cli('run_code', '--language', 'r', '--code', example / 'replica.R', '--cwd', example)
    assert result.returncode == 0, result.stdout + result.stderr
    record = read_json(example / 'run.log')
    assert record['language'] == 'r' and '4.5.0' in record['version']
    assert record['command'][1] == '--vanilla' and record['packages']['ggplot2']
    assert 'R version' in record['session_info']
    assert 'ggplot2' in (example / 'sessionInfo.txt').read_text()
    for ext in ('png', 'pdf', 'svg'):
        assert (example / f'output/replica.{ext}').stat().st_size > 100
    with Image.open(example / 'output/replica.png') as image:
        assert image.size == (2400, 1800)
    assert 'SVG:' in (example / 'output/replica-devices.txt').read_text()


def test_r_missing_executable(cli, tmp_path):
    code = tmp_path / 'ok.R'
    code.write_text('cat("hello")')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'rscript_exe': str(tmp_path / 'missing.exe')}))
    result = cli('run_code', '--language', 'r', '--code', code, '--cwd', tmp_path, '--config', config)
    record = read_json(tmp_path / 'run.log')
    assert result.returncode != 0 and 'rscript_exe' in record['launch_error']
    assert 'no packages' in record['launch_error']


def test_r_timeout_mock(monkeypatch, tmp_path):
    import bootstrap_env
    import run_code
    code = tmp_path / 'sleep.R'
    code.write_text('Sys.sleep(300)')
    monkeypatch.setattr(bootstrap_env, 'run_r', lambda *args: (0, 'R version fixture\n', '', False))
    class Process:
        pid = 12345
        returncode = None
        calls = 0
        def wait(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired('mock R', timeout)
            self.returncode = -9
        def kill(self):
            self.returncode = -9
    process = Process()
    monkeypatch.setattr(run_code.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr(run_code.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    record = run_code.run_r(code, tmp_path, timeout=0.01)
    assert record['timed_out'] and record['exit_code'] == 124
    assert process.returncode == -9 and not record['cleanup_errors']


def test_r_missing_package_action(cli, tmp_path):
    code = tmp_path / 'missing.R'
    code.write_text('library(definitely_missing_t4_package)')
    result = cli('run_code', '--language', 'r', '--code', code, '--cwd', tmp_path)
    record = read_json(tmp_path / 'run.log')
    assert result.returncode != 0 and 'definitely_missing_t4_package' in record['stderr_tail']
    assert 'author' in record['action_required']


def test_dedupe_real_cli_archives_all_and_index(cli, entry):
    gallery = entry.parents[2]
    meta = read_json(entry / 'meta.json')
    meta['post']['url'] = 'https://example.org/post01'
    (entry / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
    for name in ('code', 'data', 'output', 'compare'):
        (entry / name / 'sentinel.txt').write_text(name)
    before = {str(p.relative_to(entry / 'source')): p.read_bytes() for p in (entry / 'source').rglob('*') if p.is_file()}
    result = cli('dedupe', '--gallery', gallery, '--post-url', meta['post']['url'], '--image', SOURCE / 'fig01.png')
    assert result.returncode == 0, result.stderr
    history = Path(json.loads(result.stdout)['history'])
    assert read_json(history / 'meta.json')['version'] == 1
    assert read_json(entry / 'meta.json')['version'] == 2
    assert (history / 'README.md').is_file()
    for name in ('code', 'data', 'output', 'compare'):
        assert (history / name / 'sentinel.txt').read_text() == name
        assert not list((entry / name).iterdir())
    assert before == {str(p.relative_to(entry / 'source')): p.read_bytes() for p in (entry / 'source').rglob('*') if p.is_file()}
    result = cli('build_index', '--gallery', gallery)
    assert result.returncode == 0, result.stderr
    assert len(read_json(gallery / 'index.json')) == 1


def make_low_quality(path):
    image = Image.new('RGB', (240, 160), '#eeeeee')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 65, 180, 95), fill='#b8b8b8')
    draw.text((60, 30), 'WATERMARK', fill='#cecece')
    image.filter(ImageFilter.GaussianBlur(5)).save(path)


def test_low_quality_stops_and_records(cli, tmp_path):
    image = tmp_path / 'low.png'
    make_low_quality(image)
    original = image.read_bytes()
    spec = tmp_path / 'figure_spec.json'
    spec.write_text(json.dumps({'quality_flags': ['watermark'], 'key_elements_readable': False,
                                'uncertain_items': ['axis ticks', 'values']}))
    result = cli('crop_figure', '--image', image, '--out', tmp_path / 'crop', '--spec', spec)
    assert result.returncode == 2 and 'clearer original image' in result.stdout
    meta = read_json(spec)
    assert {'watermark', 'possible_blur_or_low_contrast', 'possible_truncation_at_image_edge'} <= set(meta['quality_flags'])
    assert meta['needs_clearer_source'] and meta['uncertain_items']
    assert image.read_bytes() == original


def test_cjk_font_and_render(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from python_style import register_cjk_font
    with matplotlib.rc_context(), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        info = register_cjk_font('示例图分组数值')
        assert Path(info['file']).is_file()
        fig, ax = plt.subplots(figsize=(3, 2))
        ax.bar([1, 2], [2, 3]); ax.set(title='示例图', xlabel='分组', ylabel='数值')
        fig.savefig(tmp_path / 'cjk.png', dpi=150)
        plt.close(fig)
    assert not [w for w in caught if 'Glyph' in str(w.message) and 'missing' in str(w.message)]
    with Image.open(tmp_path / 'cjk.png') as image:
        assert min(image.convert('L').getextrema()) < 100


def test_cjk_missing_font_stops(monkeypatch):
    import python_style
    monkeypatch.setattr(python_style.font_manager, 'findfont', lambda *a, **k: (_ for _ in ()).throw(ValueError('missing')))
    with pytest.raises(RuntimeError, match='avoid tofu'):
        python_style.register_cjk_font()


def test_installer_keeps_backup(cli, tmp_path):
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir(); target.mkdir()
    (source / 'SKILL.md').write_text('new')
    (target / 'SKILL.md').write_text('old')
    (target / 'extra.txt').write_text('keep')
    result = cli('install', '--source', source, '--target', target)
    assert result.returncode == 0, result.stderr
    backup = Path(read_json(target / 'installation-manifest.json')['previous_backup'])
    assert (backup / 'SKILL.md').read_text() == 'old'
    assert (target / 'extra.txt').read_text() == 'keep'
