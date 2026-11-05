"""Exercise structural and strict dispatch through the public CLI."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent))
from test_evidence_edit import fixture


def run_cli(*args):
    return subprocess.run([sys.executable, '-X', 'utf8',
                           str(Path(__file__).with_name('check_finalize.py')), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def test_structural_comparison_and_bilingual_apply(tmp_path):
    before, after, review, changes, decisions, _ = fixture(tmp_path)
    args = ['--before', before, '--after', after, '--edit-mode', 'structural',
            '--review-json', review, '--changes', changes]
    compared = run_cli(*args)
    assert compared.returncode == 0, compared.stdout + compared.stderr
    assert json.loads(compared.stdout)['errors'] == []
    applied = run_cli(*args, '--apply', '--project-root', before.parent,
                      '--decisions', decisions, '--date', '2026-11-05')
    assert applied.returncode == 0, applied.stdout + applied.stderr
    result = json.loads(applied.stdout)
    assert len(result['applied']) == 3
    assert (before / 'Results/Results_ZH.md').read_bytes() == (after / 'Results/Results_ZH.md').read_bytes()


def test_missing_review_does_not_fallback_to_strict(tmp_path):
    before, after, *_ = fixture(tmp_path)
    result = run_cli('--before', before, '--after', after, '--edit-mode', 'structural')
    assert result.returncode == 1
    assert json.loads(result.stdout)['errors']


def test_review_argument_without_explicit_mode_fails(tmp_path):
    before, after, review, *_ = fixture(tmp_path)
    result = run_cli('--before', before, '--after', after, '--review-json', review)
    assert result.returncode == 1
    assert json.loads(result.stdout)['errors']
