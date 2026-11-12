"""T3: verify actual artists, protected inputs, and the runnable six-panel example."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest
from PIL import Image
from conftest import ROOT, SKILL

EXAMPLE = SKILL / 'examples/post01-fig4'


def digest_tree(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


@pytest.fixture(scope='module')
def model():
    assert (EXAMPLE / 'replica.py').is_file(), 'T3 example has not been implemented'
    spec = importlib.util.spec_from_file_location('post01_fig4', EXAMPLE / 'replica.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fig, artists, metadata = module.build_figure()
    yield module, fig, artists, metadata
    module.plt.close(fig)


def test_real_artists_and_shared_feature_alignment(model):
    _, fig, artists, meta = model
    assert [t.get_text() for t in fig.texts] == list('ABCDEF')
    assert meta['status'] == 'review'
    rows = list(csv.DictReader((EXAMPLE / 'estimated_data.csv').open(encoding='utf-8')))
    for bar, swarm, radial in [('A', 'B', 'C'), ('D', 'E', 'F')]:
        data = [r for r in rows if r['panel'] == bar]
        ring = [r for r in rows if r['panel'] == radial]
        assert len(data) == len(ring) == 15
        assert [t.get_text() for t in artists[bar]['ax'].get_yticklabels()] == [r['feature'] for r in data]
        assert [b.get_width() for b in artists[bar]['bars']] == pytest.approx([float(r['shap']) for r in data])
        assert [t.get_text() for t in artists[radial]['labels']] == [f"{r['feature']}\n{float(r['percent']):.1f}%" for r in ring]
        assert [t.get_text() for t in artists[bar]['inset'].texts] == [f"{float(r['percent']):.1f}%" for r in data]
        assert {r['feature']: r['percent'] for r in data} == {r['feature']: r['percent'] for r in ring}
        assert not any(t.get_visible() for t in artists[swarm]['ax'].get_yticklabels())
        assert artists[bar]['ax'].get_ylim() == artists[swarm]['ax'].get_ylim()
        for a, b in zip(artists[bar]['ax'].transData.transform([(0, i) for i in range(15)]),
                        artists[swarm]['ax'].transData.transform([(0, i) for i in range(15)])):
            assert a[1] == pytest.approx(b[1])
        assert artists[swarm]['colorbar'].ax.get_ylabel() == 'Feature value'
        assert artists[radial]['colorbar'].ax.get_title() == '|SHAP Value|'
        assert artists[radial]['ax'].name == artists[bar]['inset'].name == 'polar'
        assert artists[bar]['ax'].xaxis_inverted()


def test_beeswarm_density_and_evidence(model):
    _, _, artists, meta = model
    rows = list(csv.DictReader((EXAMPLE / 'estimated_beeswarm.csv').open(encoding='utf-8')))
    assert {r['provenance'] for r in rows} == {'estimated'}
    for letter in 'BE':
        counts = [len(c.get_offsets()) for c in artists[letter]['points']]
        assert len(counts) == 15 and all(150 <= n <= 200 for n in counts)
    assert meta['original_code_provenance'] == 'example_not_target'
    assert any(r['provenance'] == 'uncertain' and r['uncertain_reason']
               for r in csv.DictReader((EXAMPLE / 'estimated_data.csv').open(encoding='utf-8')))


def test_archived_code_is_verbatim_not_executed():
    source = (ROOT / 'samples/post01/source/source.md').read_bytes()
    blocks = re.findall(rb'^```([^\r\n]*)\r?\n(.*?)^```', source, flags=re.M | re.S)
    assert len(blocks) == 4
    for i, (_, body) in enumerate(blocks, 1):
        ext = 'py' if i == 1 else 'txt'
        assert (EXAMPLE / f'original_code/code_block_{i:02}.{ext}').read_bytes() == body
    text = (EXAMPLE / 'original_code/README.md').read_text(encoding='utf-8')
    assert 'example_not_target' in text and 'archived_only' in text


def test_exports_source_integrity_and_write_scope(tmp_path):
    before = digest_tree(ROOT / 'samples')
    # Instrument this subprocess's file mutations: every target must stay in --out.
    # Samples, the real gallery, and the skill installation cannot be written.
    guard = tmp_path / 'guard'
    guard.mkdir()
    (guard / 'sitecustomize.py').write_text('''import os, sys
root = os.path.realpath(os.environ['T3_ALLOWED_WRITE'])
def check(path):
    if isinstance(path, (str, bytes, os.PathLike)):
        target = os.path.realpath(os.fsdecode(path))
        if os.path.commonpath([root, target]) != root:
            raise RuntimeError('T3 unexpected write: ' + target)
def audit(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            check(args[0])
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir'):
        check(args[0])
    elif event in ('os.rename', 'os.replace'):
        check(args[0]); check(args[1])
sys.addaudithook(audit)
''', encoding='utf-8')
    import os
    out = tmp_path / 'render'
    out.mkdir()
    cache = out / 'mpl-cache'
    cache.mkdir()
    result = subprocess.run([sys.executable, '-X', 'utf8', str(EXAMPLE / 'replica.py'), '--out', str(out)],
                            capture_output=True, text=True, encoding='utf-8', timeout=150,
                            env={**os.environ, 'PYTHONPATH': str(guard), 'PYTHONDONTWRITEBYTECODE': '1',
                                 'T3_ALLOWED_WRITE': str(out), 'MPLCONFIGDIR': str(cache), 'TEMP': str(out), 'TMP': str(out)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert before == digest_tree(ROOT / 'samples')
    for ext in ('png', 'pdf', 'svg'):
        assert (out / f'output/replica.{ext}').stat().st_size > 100
    with Image.open(out / 'output/replica.png') as im:
        im.load()
        assert im.size == (7200, 4104)
        assert abs((im.width / im.height) / (893 / 509) - 1) <= .02
    assert '<text' in (out / 'output/replica.svg').read_text(encoding='utf-8')
    assert (out / 'output/replica.pdf').read_bytes().startswith(b'%PDF-')
    meta = json.loads((out / 'figure_spec.json').read_text(encoding='utf-8'))
    assert set(meta['panels']) == set('ABCDEF')
    assert meta['text_outside_canvas'] == []
    assert meta['crop']['crop_bbox'] == [0, 0, 893, 509]
    assert (out / 'compare/side_by_side.png').is_file()
    assert 'WARN' in (out / 'qa_report.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('target', [ROOT / 'samples/post01/source', Path(json.loads((SKILL / 'config.json').read_text(encoding='utf-8'))['gallery_root']) / 'T3-forbidden'])
def test_reject_protected_output_without_writing(target):
    result = subprocess.run([sys.executable, '-X', 'utf8', str(EXAMPLE / 'replica.py'), '--out', str(target)],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 2
    assert 'Refusing output' in result.stderr
