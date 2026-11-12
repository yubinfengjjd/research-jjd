"""Run authorized Python/R code with the configured dedicated interpreter.

This is a timeout/logging runner, not a security sandbox. Only execute code
already reviewed/authorized by the caller. No shell evaluation is performed.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

from common import atomic_write, cli_error, json_bytes, load_config, utc_now


def run_code(code, cwd, timeout=300, config=None, language='python'):
    if language not in ('python', 'r'):
        raise ValueError('language must be python or r')
    code, cwd = Path(code).resolve(), Path(cwd).resolve()
    if not code.is_file() or not cwd.is_dir():
        raise ValueError('Code file and working directory must exist')
    if not timeout > 0:
        raise ValueError('timeout must be positive')
    outputs = [cwd / name for name in ('run.log', 'stdout.txt', 'stderr.txt', 'sessionInfo.txt')]
    if code in outputs:
        raise ValueError('Log paths must not overwrite code')
    record = {'timestamp': utc_now(), 'language': language, 'executable': None,
              'version': None, 'command': [], 'cwd': str(cwd), 'timed_out': False,
              'packages': {}, 'cleanup_errors': []}
    try:
        executable = Path(load_config(config)['rscript_exe' if language == 'r' else 'python_exe'])
        command = [str(executable), *(['--vanilla'] if language == 'r' else ['-X', 'utf8']), str(code)]
        record.update(executable=str(executable), command=command)
        if language == 'r':
            from bootstrap_env import run_r
            rc, out, err, timed = run_r(executable, None, 10)
            record['version'] = out.strip()
            if rc or timed:
                raise ValueError(f'R version probe failed (timeout={timed}): {err}')
            expression = 'ip <- installed.packages(); for (p in intersect(c("ggplot2","patchwork","scales","svglite","ggbeeswarm"), rownames(ip))) cat("PACKAGE:", p, "=", ip[p,"Version"], "\\n", sep=""); print(sessionInfo())'
            rc, out, err, timed = run_r(executable, expression, 30)
            record.update(session_info=out, probe_stderr=err)
            atomic_write(cwd / 'sessionInfo.txt', out)
            if rc or timed:
                raise ValueError(f'R sessionInfo probe failed (timeout={timed}): {err}')
            record['packages'] = dict(line.removeprefix('PACKAGE:').split('=', 1)
                                      for line in out.splitlines() if line.startswith('PACKAGE:'))
        else:
            record['version'] = subprocess.run([str(executable), '--version'], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
            probe = subprocess.run([str(executable), '-X', 'utf8', '-c',
                'import importlib.metadata as m,json; print(json.dumps({n:m.version(n) for n in ("matplotlib","numpy","pandas","Pillow")}))'],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            if probe.returncode:
                raise ValueError('Dedicated environment probe failed: ' + probe.stderr)
            record['packages'] = json.loads(probe.stdout)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        message = str(error)
        if language == 'r':
            message += '; Check config.json rscript_exe / local R installation; no packages were installed.'
        record.update(exit_code=1, launch_error=message, stdout_tail='', stderr_tail=message)
        atomic_write(cwd / 'stdout.txt', '')
        atomic_write(cwd / 'stderr.txt', message)
        atomic_write(cwd / 'run.log', json_bytes(record))
        return record
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            proc = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                    **({} if os.name == 'nt' else {'start_new_session': True}))
            try:
                proc.wait(timeout=timeout)
                record['exit_code'] = proc.returncode
            except subprocess.TimeoutExpired:
                record.update(timed_out=True, exit_code=124)
                try:
                    if os.name == 'nt':
                        result = subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=5)
                        if result.returncode:
                            record['cleanup_errors'].append(result.stderr.decode('utf-8', errors='replace'))
                    else:
                        os.killpg(proc.pid, signal.SIGKILL)
                except (OSError, subprocess.SubprocessError) as error:
                    record['cleanup_errors'].append(str(error))
                try:
                    proc.wait(timeout=5)
                except (OSError, subprocess.SubprocessError):
                    try:
                        proc.kill()
                        proc.wait(timeout=5)
                    except (OSError, subprocess.SubprocessError) as error:
                        record['cleanup_errors'].append('Fallback cleanup failed: ' + str(error))
        except OSError as error:
            record.update(exit_code=1, launch_error=str(error))
        stdout.seek(0)
        stderr.seek(0)
        out, err = stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')
    record.update(stdout_tail=out[-12000:], stderr_tail=err[-12000:])
    if language == 'r' and record['exit_code'] and ('there is no package called' in err or '不存在叫' in err):
        record['action_required'] = 'Missing R package: inspect stderr; ask the author before installing into the user library. No automatic install.'
    atomic_write(cwd / 'stdout.txt', out)
    atomic_write(cwd / 'stderr.txt', err)
    atomic_write(cwd / 'run.log', json_bytes(record))
    return record


def run_python(code, cwd, timeout=300, config=None):
    return run_code(code, cwd, timeout, config, 'python')


def run_r(code, cwd, timeout=300, config=None):
    return run_code(code, cwd, timeout, config, 'r')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=['python', 'r'], required=True)
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_code(args.code, args.cwd, args.timeout, args.config, args.language)
        print(f'exit_code={result["exit_code"]}; timed_out={result["timed_out"]}; log={args.cwd / "run.log"}')
        if result['cleanup_errors']:
            print('Process-tree cleanup failed: ' + '; '.join(result['cleanup_errors']))
        if result.get('launch_error'):
            print(result['launch_error'])
        if result.get('action_required'):
            print(result['action_required'])
        return result['exit_code'] if 0 <= result['exit_code'] <= 255 else 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
