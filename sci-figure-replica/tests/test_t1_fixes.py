"""Regression coverage for the four T1 review blockers."""
import subprocess
import sys

import pytest
from conftest import SKILL, SOURCE, read_json


def test_pytest_uses_default_temporary_root():
    config = (SKILL / 'pytest.ini').read_text(encoding='utf-8')
    assert '--basetemp' not in config
    assert 'test-gallery' not in config


def test_draft_index_has_only_existing_links(entry, cli):
    gallery = entry.parents[2]
    assert cli('build_index', '--gallery', gallery).returncode == 0
    item = read_json(gallery / 'index.json')[0]
    assert item['links'] == {'readme': 'post01/figures/fig01/README.md'}
    assert item['pending'] == [
        {'key': 'replica', 'label': '复刻 PNG'},
        {'key': 'compare', 'label': '并排对比'},
    ]
    page = (gallery / 'index.html').read_text(encoding='utf-8')
    assert '待生成' in page and '.pending{color:#8a6d3b}' in page
    assert 'output/replica.png' not in page and 'compare/side_by_side.png' not in page
    for filename in ('output/replica.png', 'compare/side_by_side.png'):
        (entry / filename).write_bytes((SOURCE / 'fig01.png').read_bytes())
    assert cli('build_index', '--gallery', gallery).returncode == 0
    item = read_json(gallery / 'index.json')[0]
    assert item['pending'] == []
    for filename in ('output/replica.png', 'compare/side_by_side.png'):
        assert f'post01/figures/fig01/{filename}' in item['links'].values()
        assert filename in (gallery / 'index.html').read_text(encoding='utf-8')
    (entry / 'README.md').unlink()
    assert cli('build_index', '--gallery', gallery).returncode == 0
    item = read_json(gallery / 'index.json')[0]
    assert 'readme' not in item['links']
    assert item['pending'] == [{'key': 'readme', 'label': 'README'}]


def test_init_known_fields(cli, tmp_path):
    gallery = tmp_path / 'gallery'
    result = cli('init_entry', '--gallery', gallery, '--post-slug', 'post01',
                 '--fig-id', 'fig01', '--source', SOURCE / 'fig01.png',
                 '--language', 'python', '--label', 'Fig. 4', '--caption', '已知图注',
                 '--panel', 'A', '--panel', 'B', '--chart-type', 'bar',
                 '--chart-type', 'beeswarm', '--scenario', 'model-explanation-shap',
                 '--scenario', 'chem-informatics-qsar',
                 '--secondary-scenario', 'experimental-statistics',
                 '--secondary-scenario', 'experimental-statistics',
                 '--free-tag', ' SHAP ', '--free-tag', 'SHAP', '--free-tag', 'LightGBM',
                 '--data-provenance', 'mixed', '--code-provenance', 'adapted',
                 '--original-code-provenance', 'example_not_target')
    assert result.returncode == 0, result.stderr
    entry = gallery / 'post01/figures/fig01'
    meta = read_json(entry / 'meta.json')
    assert meta['figure']['label'] == 'Fig. 4'
    assert meta['figure']['caption'] == '已知图注'
    assert meta['figure']['panels'] == ['A', 'B']
    assert meta['figure']['chart_types'] == ['bar', 'beeswarm']
    assert meta['language'] == 'python'
    assert meta['data_provenance'] == 'mixed' and meta['code_provenance'] == 'adapted'
    assert meta['original_code_provenance'] == 'example_not_target'
    assert meta['scenarios'] == {
        'primary': ['model-explanation-shap', 'chem-informatics-qsar'],
        'secondary': ['experimental-statistics'], 'free': ['SHAP', 'LightGBM']}
    readme = (entry / 'README.md').read_text(encoding='utf-8')
    assert all(value in readme for value in ('Fig. 4', 'A, B', 'python'))


@pytest.mark.parametrize('options, message', [
    (['--language', 'julia'], 'invalid choice'),
    (['--data-provenance', 'invented'], 'invalid choice'),
    (['--code-provenance', 'invented'], 'invalid choice'),
    (['--original-code-provenance', 'invented'], 'invalid choice'),
    (['--scenario', 'invalid'], '--scenario'),
    (['--secondary-scenario', 'invalid'], '--secondary-scenario'),
    (['--scenario', 'other', '--scenario', 'other'], '--scenario'),
    (['--scenario', 'other', '--scenario', 'single-cell', '--scenario', 'multi-omics'], '--scenario'),
    (['--free-tag', '   '], '--free-tag'),
])
def test_init_invalid_fields_leave_no_partial_entry(cli, tmp_path, options, message):
    gallery = tmp_path / 'gallery'
    result = cli('init_entry', '--gallery', gallery, '--post-slug', 'post01',
                 '--fig-id', 'fig01', '--source', SOURCE / 'fig01.png', *options)
    assert result.returncode != 0 and message in result.stderr
    assert not gallery.exists()


def test_init_empty_panel_defaults(entry):
    meta = read_json(entry / 'meta.json')
    assert meta['figure']['panels'] == [] and meta['figure']['chart_types'] == []
    assert meta['language'] == 'unknown' and meta['original_code_provenance'] is None


@pytest.mark.parametrize('unavailable', ['packages', 'cairo', None])
def test_r_check_timeout_is_bounded_and_continues(monkeypatch, capsys, unavailable):
    import bootstrap_env
    monkeypatch.setattr(bootstrap_env, 'check_python', lambda exe: ('fixture Python', []))
    calls = []
    def fake_r(executable, expression, timeout):
        calls.append((expression, timeout))
        match = (unavailable == 'packages' and 'installed.packages()' in expression) or (
            unavailable == 'cairo' and 'capabilities' in expression)
        packages = 'ggplot2\npatchwork\nsvglite\nscales\nggbeeswarm'
        return (1, '', '', True) if match else (0, packages if 'installed.packages()' in expression else 'TRUE', '', False)
    monkeypatch.setattr(bootstrap_env, 'run_r', fake_r)
    result = bootstrap_env.main(['--check-r'])
    output = capsys.readouterr().out
    assert result == (0 if unavailable is None else 1)
    assert ('TIMEOUT' in output) == (unavailable is not None)
    if unavailable is not None:
        assert 'R check timed out' in output
    assert len(calls) == 2
    assert 'installed.packages()' in calls[0][0] and calls[0][1] == 30
    assert all('requireNamespace' not in expression for expression, _ in calls)
    assert calls[-1] == ('cat(capabilities("cairo"))', 10)


def test_r_runner_uses_files_and_kills_process_tree(monkeypatch):
    import bootstrap_env
    calls = []
    class Process:
        pid = 12345
        returncode = None
        def __init__(self, command, **kwargs):
            calls.append(command)
            assert 'capture_output' not in kwargs
            kwargs['stdout'].write(b'partial output')
            kwargs['stderr'].write(b'partial error')
        def wait(self, timeout):
            if self.returncode is None:
                self.returncode = 1
                raise subprocess.TimeoutExpired(calls[0], timeout)
            return self.returncode
    def taskkill(command, **kwargs):
        assert command == ['taskkill', '/PID', '12345', '/T', '/F']
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, b'', b'')
    monkeypatch.setattr(bootstrap_env.subprocess, 'Popen', Process)
    monkeypatch.setattr(bootstrap_env.subprocess, 'run', taskkill)
    assert bootstrap_env.run_r('Rscript.exe', 'cat(TRUE)', 0.01) == (
        1, 'partial output', 'partial error', True)
    assert len(calls) == 2


def test_r_runner_real_timeout(monkeypatch):
    import bootstrap_env
    popen = subprocess.Popen
    def python_sleeper(command, **kwargs):
        return popen([sys.executable, '-c', 'import time; print("started", flush=True); time.sleep(30)'], **kwargs)
    monkeypatch.setattr(bootstrap_env.subprocess, 'Popen', python_sleeper)
    code, stdout, stderr, timed_out = bootstrap_env.run_r(
        'Rscript.exe', 'cat(TRUE)', 1)
    assert timed_out and code != 0
    assert 'started' in stdout


@pytest.mark.parametrize('package', ['svglite', 'ggbeeswarm'])
def test_r_optional_package_reports_fallback_and_checks_remaining(monkeypatch, capsys, package):
    import bootstrap_env
    monkeypatch.setattr(bootstrap_env, 'check_python', lambda exe: ('fixture Python', []))
    def fake_r(executable, expression, timeout):
        packages = '\n'.join(p for p in ['ggplot2', 'patchwork', 'svglite', 'scales', 'ggbeeswarm'] if p != package)
        return 0, packages if 'installed.packages()' in expression else 'TRUE', '', False
    monkeypatch.setattr(bootstrap_env, 'run_r', fake_r)
    assert bootstrap_env.main(['--check-r']) == 0
    output = capsys.readouterr().out
    assert f'{package}' in output and 'MISSING' in output
    assert 'cairo: AVAILABLE' in output

