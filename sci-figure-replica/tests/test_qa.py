from PIL import Image
from conftest import SOURCE


def test_qa_missing_artifacts_is_fail(entry, cli):
    report = entry / 'qa_report.md'
    result = cli('qa_check', '--entry', entry, '--original', SOURCE / 'fig01.png',
                 '--replica', SOURCE / 'fig01.png', '--out', report)
    assert result.returncode == 1
    text = report.read_text(encoding='utf-8')
    assert 'FAIL' in text and '人工' in text and 'PASS/WARN/FAIL' in text


def test_qa_ratio_and_valid_exports(entry, cli):
    from qa_check import aspect_error
    assert aspect_error((100, 100), (102, 100)) <= 0.02 + 1e-12
    assert aspect_error((100, 100), (103, 100)) > 0.02
    for name in ('output/replica.png', 'thumb.png', 'compare/side_by_side.png'):
        Image.new('RGB', (893, 579), 'white').save(entry / name)
    (entry / 'output/replica.pdf').write_bytes(b'%PDF-1.4\nplaceholder')
    (entry / 'output/replica.svg').write_text('<svg/>')
    (entry / 'code/replica.py').write_text('# fixture only')
    (entry / 'data/figure_spec.json').write_text('{}')
    (entry / 'data/estimated_data.csv').write_text('value\n1')
    (entry / 'run.log').write_text('fixture')
    result = cli('qa_check', '--entry', entry, '--original', SOURCE / 'fig01.png',
                 '--replica', entry / 'output/replica.png', '--out', entry / 'qa_report.md')
    assert result.returncode == 0, result.stderr
    assert '视觉' in (entry / 'qa_report.md').read_text(encoding='utf-8')
