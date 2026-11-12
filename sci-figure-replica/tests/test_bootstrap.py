import json
import sys


def test_check_existing_env(cli):
    result = cli('bootstrap_env', '--python-exe', sys.executable)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Pillow' in result.stdout and 'pytest' in result.stdout


def test_missing_package_reports_command(monkeypatch):
    import bootstrap_env
    monkeypatch.setattr(bootstrap_env, 'REQUIRED', {'definitely_missing_t1_package': 'definitely_missing_t1_package'})
    result, missing = bootstrap_env.check_python(sys.executable)
    assert missing == ['definitely_missing_t1_package']
    assert 'pip install' in result


def test_r_probe_single_expression_and_stderr(monkeypatch, capsys):
    import bootstrap_env
    monkeypatch.setattr(bootstrap_env, 'check_python', lambda exe: ('fixture Python', []))
    def run(executable, expression, timeout):
        assert expression is None or '\n' not in expression  # Windows Rscript -e truncates multiline expressions.
        packages = 'ggplot2\npatchwork\nsvglite\nscales\nggbeeswarm'
        return 0, packages if 'installed.packages()' in expression else 'TRUE', 'locale warning', False
    monkeypatch.setattr(bootstrap_env, 'run_r', run)
    assert bootstrap_env.main(['--check-r']) == 0
    captured = capsys.readouterr()
    assert 'ggplot2' in captured.out and 'locale warning' in captured.err
