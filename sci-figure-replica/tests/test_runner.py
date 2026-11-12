import json
import pytest
from conftest import read_json


@pytest.mark.parametrize('exit_code', [0, 7])
def test_runner_preserves_output_and_exit_code(cli, tmp_path, exit_code):
    code = tmp_path / 'space 测试.py'
    code.write_text(f'import sys; print("hello"); print("problem",file=sys.stderr); sys.exit({exit_code})')
    result = cli('run_code', '--language', 'python', '--code', code, '--cwd', tmp_path)
    assert result.returncode == exit_code, result.stderr
    log = read_json(tmp_path / 'run.log')
    assert log['exit_code'] == exit_code and log['version']
    assert 'hello' in log['stdout_tail'] and 'problem' in log['stderr_tail']
    assert log['command'][-1] == str(code)
    assert (tmp_path / 'stdout.txt').read_text().strip() == 'hello'


def test_runner_timeout_retains_log(cli, tmp_path):
    code = tmp_path / 'sleep.py'
    code.write_text('import time; print("started",flush=True); time.sleep(60)')
    result = cli('run_code', '--language', 'python', '--code', code, '--cwd', tmp_path, '--timeout', '1')
    assert result.returncode != 0
    log = read_json(tmp_path / 'run.log')
    assert log['timed_out'] and 'started' in log['stdout_tail']


def test_runner_preflight_failure_retains_log(cli, tmp_path):
    code = tmp_path / 'ok.py'
    code.write_text('print("hello")')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'python_exe': str(tmp_path / 'missing.exe')}))
    result = cli('run_code', '--language', 'python', '--code', code, '--cwd', tmp_path, '--config', config)
    assert result.returncode != 0
    log = read_json(tmp_path / 'run.log')
    assert log['exit_code'] != 0 and log['launch_error']
