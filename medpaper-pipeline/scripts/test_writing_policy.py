"""Author limits and lexical diagnostics must not force filler prose."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import manuscript_check as mc


@pytest.mark.parametrize('section', ['methods', 'results', 'discussion'])
def test_short_evidence_complete_section_has_no_generic_minimum(tmp_path, section):
    path = tmp_path / 'Manuscript_EN.md'
    path.write_text('The prespecified estimate was lower in the held-out cohort.', encoding='utf-8')
    assert not [f for f in mc.check(section, path) if f['rule'] == 'word-count']


def test_project_limit_is_enforced_without_confusing_citation_quota(tmp_path):
    (tmp_path / 'PROJECT.md').write_text('## 写作目标\n- Results：≥25\n', encoding='utf-8')
    (tmp_path / 'writing-limits.json').write_text(json.dumps({'results': {'max': 8}}), encoding='utf-8')
    folder = tmp_path / '04_manuscript' / 'Results'
    folder.mkdir(parents=True)
    path = folder / 'Results_EN.md'
    path.write_text('The prespecified estimate was lower in the held-out cohort.', encoding='utf-8')
    findings = mc.check('results', path)
    assert any(f['rule'] == 'word-count' and f['level'] == mc.E for f in findings)


def test_lexical_repetition_is_a_signal_and_not_an_error(tmp_path):
    path = tmp_path / 'Discussion_EN.md'
    path.write_text('This agrees with prior work. That agrees with the estimate. '
                    'The result agrees with this explanation.', encoding='utf-8')
    findings = mc.check('discussion', path)
    assert any(f['rule'] == 'agrees-with' and f['level'] == mc.W for f in findings)
    assert not [f for f in findings if f['rule'] == 'agrees-with' and f['level'] == mc.E]


def test_malformed_declared_limits_fail_explicitly_in_cli(tmp_path):
    (tmp_path / 'PROJECT.md').write_text('# Project', encoding='utf-8')
    (tmp_path / 'writing-limits.json').write_text('{"results":{"max":true}}', encoding='utf-8')
    path = tmp_path / 'Results_EN.md'
    path.write_text('A measured finding.', encoding='utf-8')
    result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(mc.__file__)),
                             'results', str(path), '--json'], capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 1
    findings = json.loads(result.stdout)
    assert any(f['rule'] == 'word-limits-config' and f['level'] == mc.E for f in findings)


def test_explicit_caption_minimum_is_per_caption(tmp_path):
    (tmp_path / 'PROJECT.md').write_text('# Project', encoding='utf-8')
    (tmp_path / 'writing-limits.json').write_text('{"legends":{"min":10}}', encoding='utf-8')
    path = tmp_path / 'Figure_Legends_EN.md'
    path.write_text('**Figure 1. Measurement.** A measured value.', encoding='utf-8')
    findings = mc.check('legends', path)
    assert any(f['rule'] == 'legend-length' and f['level'] == mc.E for f in findings)
