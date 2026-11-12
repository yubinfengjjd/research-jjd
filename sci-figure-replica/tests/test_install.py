import hashlib
from conftest import ROOT, read_json


def test_install_dry_run_manifest_and_extras(cli, tmp_path):
    source, target = tmp_path / 'src', tmp_path / 'target'
    source.mkdir()
    (source / 'SKILL.md').write_text('fixture')
    result = cli('install', '--source', source, '--target', target, '--dry-run')
    assert result.returncode == 0 and 'SKILL.md' in result.stdout
    assert not target.exists()
    target.mkdir()
    (target / 'extra.txt').write_text('keep')
    result = cli('install', '--source', source, '--target', target)
    assert result.returncode == 0, result.stderr
    assert (target / 'extra.txt').exists()
    manifest = read_json(target / 'installation-manifest.json')
    assert manifest['files'][0]['sha256'] == hashlib.sha256(b'fixture').hexdigest()
    assert manifest['source'] == str(source.resolve())
    result = cli('install', '--source', source, '--target', target, '--clean')
    assert result.returncode == 0 and not (target / 'extra.txt').exists()
