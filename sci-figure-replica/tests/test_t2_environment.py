"""Environment regressions requiring neither installed R packages nor ACL changes."""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile

import pytest

import conftest


def test_default_basetemp_is_unique_and_explicit_option_preserved():
    first = SimpleNamespace(option=SimpleNamespace(basetemp=None))
    second = SimpleNamespace(option=SimpleNamespace(basetemp=None))
    conftest.pytest_configure(first)
    conftest.pytest_configure(second)
    assert first.option.basetemp != second.option.basetemp
    assert Path(first.option.basetemp).parent == Path(tempfile.gettempdir())
    assert Path(first.option.basetemp).name.startswith('sci-figure-replica-pytest-')
    explicit = SimpleNamespace(option=SimpleNamespace(basetemp='provided-by-user'))
    conftest.pytest_configure(explicit)
    assert explicit.option.basetemp == 'provided-by-user'
    assert '-p no:cacheprovider' in (conftest.SKILL / 'pytest.ini').read_text()


@pytest.mark.parametrize('kill_error', [PermissionError('fallback denied'), subprocess.TimeoutExpired('kill', 5)])
@pytest.mark.parametrize('failure_stage', ['kill', 'wait'])
def test_timeout_cleanup_denied_still_returns(monkeypatch, kill_error, failure_stage):
    import bootstrap_env
    class Process:
        pid = 12345
        returncode = None
        def __init__(self, command, **kwargs):
            kwargs['stdout'].write(b'partial')
        def wait(self, timeout):
            raise subprocess.TimeoutExpired('Rscript', timeout)
        def kill(self):
            if failure_stage == 'kill':
                raise kill_error
    def deny(*args, **kwargs):
        raise PermissionError('tree cleanup denied')
    monkeypatch.setattr(bootstrap_env.subprocess, 'Popen', Process)
    monkeypatch.setattr(bootstrap_env.subprocess, 'run', deny)
    code, stdout, stderr, timed_out = bootstrap_env.run_r('Rscript', 'cat(TRUE)', 0.01)
    assert code != 0 and stdout == 'partial' and timed_out
    assert 'Process-tree cleanup failed' in stderr and 'fallback' in stderr.lower()
