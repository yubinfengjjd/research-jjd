"""Check/create the dedicated venv; report missing dependencies without installing."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from common import cli_error, load_config

REQUIRED = {'matplotlib': 'matplotlib', 'numpy': 'numpy', 'pandas': 'pandas', 'seaborn': 'seaborn',
            'scipy': 'scipy', 'Pillow': 'PIL', 'fonttools': 'fontTools', 'pytest': 'pytest'}
R_REQUIRED = ('ggplot2', 'patchwork', 'scales')
R_OPTIONAL = ('svglite', 'ggbeeswarm')


def run_r(executable, expression, timeout):
    """Run one bounded R probe, using files so inherited pipes cannot block exit.

    expression=None selects the basic --version probe.
    """
    command = [str(executable), '--version'] if expression is None else [
        str(executable), '--vanilla', '-e', expression]
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        options = {} if os.name == 'nt' else {'start_new_session': True}
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr, **options)
        timed_out = False
        cleanup_error = ''
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                if os.name == 'nt':
                    killed = subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                                            capture_output=True, timeout=5)
                    if killed.returncode:
                        cleanup_error = '\nProcess-tree cleanup failed: ' + killed.stderr.decode('utf-8', errors='replace')
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, subprocess.SubprocessError) as error:
                cleanup_error = f'\nProcess-tree cleanup failed: {error}'
            try:
                proc.wait(timeout=5)
            except (OSError, subprocess.SubprocessError) as error:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except (OSError, subprocess.SubprocessError) as fallback_error:
                    cleanup_error += f'\nFallback cleanup failed: {fallback_error}; process may still be running.'
        stdout.seek(0)
        stderr.seek(0)
        return (proc.returncode if proc.returncode is not None else 1, stdout.read().decode('utf-8', errors='replace'),
                stderr.read().decode('utf-8', errors='replace') + cleanup_error, timed_out)


def check_r(executable):
    """Inventory installed packages once, without loading their namespaces."""
    probes = [('installed.packages', 'ip <- rownames(installed.packages()); cat(paste(ip, collapse="\\n"))', 30),
              ('cairo', 'cat(capabilities("cairo"))', 10)]
    failed = False
    for label, expression, timeout in probes:
        code, stdout, stderr, timed_out = run_r(executable, expression, timeout)
        if timed_out:
            failed = True
            print(f'{label}: TIMEOUT — R check timed out after {timeout}s; '
                  'process-tree cleanup requested. Check this component before retrying; no packages installed.')
            if label == 'installed.packages':
                for package in R_REQUIRED + R_OPTIONAL:
                    print(f'{package}: UNKNOWN (package inventory timed out)')
        elif code:
            failed = True
            print(f'{label}: ERROR (exit={code}, output={stdout.strip()!r}); '
                  'check R configuration/packages; no packages installed.')
            if label == 'installed.packages':
                for package in R_REQUIRED + R_OPTIONAL:
                    print(f'{package}: UNKNOWN (package inventory failed)')
        elif label == 'installed.packages':
            installed = set(stdout.splitlines())
            for package in R_REQUIRED + R_OPTIONAL:
                available = package in installed
                failed |= not available and package in R_REQUIRED
                optional = ' (optional)' if package in R_OPTIONAL else ''
                print(f'{package}{optional}: {"AVAILABLE" if available else "MISSING"}')
                if not available and package == 'svglite':
                    print('SVG fallback: grDevices::svg (cairo); glyphs may be paths, not editable text; record device and WARN.')
                if not available and package == 'ggbeeswarm':
                    print('Beeswarm fallback: explicitly labelled synthetic jitter only; not original point data.')
        elif stdout.strip() != 'TRUE':
            failed = True
            print(f'{label}: MISSING (exit={code}, output={stdout.strip()!r}); no packages installed.')
        else:
            print(f'{label}: AVAILABLE')
        if stderr:
            print(stderr, file=sys.stderr)
    return 1 if failed else 0


def check_python(executable):
    code = '''import importlib, importlib.metadata as m, json, sys
packages=json.loads(sys.argv[1]); versions={}; missing=[]
for package,module in packages.items():
    try:
        importlib.import_module(module)
        versions[package]=m.version(package)
    except (ImportError, m.PackageNotFoundError):
        missing.append(package)
print(json.dumps({'python':sys.version,'versions':versions,'missing':missing}))
'''
    result = subprocess.run([str(executable), '-X', 'utf8', '-c', code, json.dumps(REQUIRED)],
                            capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode:
        raise ValueError(result.stderr or 'Python dependency probe failed')
    meta = json.loads(result.stdout)
    text = json.dumps(meta, ensure_ascii=False, indent=2)
    if meta['missing']:
        text += '\n缺包；不自动安装。由环境维护者运行：\n& "' + str(executable) + '" -m pip install ' + ' '.join(meta['missing'])
    return text, meta['missing']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--python-exe', type=Path)
    parser.add_argument('--base-python', type=Path, help='Required only when creating a missing venv')
    parser.add_argument('--rscript-exe', type=Path)
    parser.add_argument('--check-r', action='store_true', help='Also inventory installed R packages and check cairo')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        executable = args.python_exe or Path(config['python_exe'])
        if not executable.is_file():
            if not args.base_python or not args.base_python.is_file():
                raise ValueError('Dedicated venv missing; supply an existing --base-python to create it; no packages will be installed')
            if executable.name.lower() != 'python.exe' or executable.parent.name.lower() != 'scripts':
                raise ValueError('Creation requires a Windows <venv>/Scripts/python.exe path')
            subprocess.run([str(args.base_python), '-X', 'utf8', '-m', 'venv', str(executable.parent.parent)], check=True, timeout=60)
        text, missing = check_python(executable)
        print(text)
        rscript = args.rscript_exe or Path(config['rscript_exe'])
        print(f'Rscript: {rscript}; exists={rscript.is_file()} (not required by Python-only T1)')
        if args.check_r:
            if not rscript.is_file():
                raise ValueError(f'Rscript: MISSING {rscript}; check --rscript-exe/config; no packages installed')
            if check_r(rscript):
                return 1
        return 1 if missing else 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return cli_error(error)


if __name__ == '__main__':
    raise SystemExit(main())
