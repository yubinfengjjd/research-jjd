"""Behavioral diagnostics; no word-frequency threshold establishes prose quality."""
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import lint_manuscript as lint


def test_repetition_and_growth_remain_nonblocking():
    previous = {'Results_EN.md': 'The effect was small. ' * 2}
    current = {'Results_EN.md': 'In the single evaluated seed, the effect was small. ' * 10}
    report = lint.analyze(current, previous)
    assert report['diagnostic_only'] is True
    assert any(x['rule'] == 'phrase-growth' for x in report['findings'])
    assert all(x['level'] in ('INFO', 'WARN') for x in report['findings'])
    assert report['metrics']['families']['scope']['count'] == 20


def test_technical_allowlist_changes_phrase_alerts_not_scientific_counts():
    text = {'Results_EN.md': 'Tumor necrosis factor was measured. ' * 10}
    report = lint.analyze(text, allow_terms=['tumor necrosis factor'])
    assert not any(x.get('phrase') == 'tumor necrosis factor' for x in report['findings'])
    assert report['metrics']['words'] > 0


def test_ngrams_do_not_cross_sentences_or_files():
    report = lint.analyze({'A_EN.md': 'Alpha beta. Gamma delta.', 'B_EN.md': 'Epsilon zeta.'})
    phrases = {p['phrase'] for p in report['ngrams']}
    assert 'beta gamma delta' not in phrases
    assert 'delta epsilon zeta' not in phrases


def test_density_increase_is_a_review_prompt_not_failure():
    report = lint.analyze({'A_EN.md': 'Whereas the result differs, we found no benefit.'},
                          {'A_EN.md': 'We found no benefit.'})
    assert any(x['rule'] == 'family-density-change' for x in report['findings'])
    assert report['diagnostic_only']
    assert 'passed' not in report


def test_directory_selects_english_sources_and_excludes_combined_and_notes(tmp_path):
    (tmp_path / 'Results_EN.md').write_text('# Results\n\nEffect was small.', encoding='utf8')
    (tmp_path / 'Results_EN_ZH.md').write_text('Duplicate English effect.', encoding='utf8')
    (tmp_path / 'Results_核查说明.md').write_text('Internal evidence.', encoding='utf8')
    assert list(lint.load_input(tmp_path)) == ['Results_EN.md']


def test_docx_reads_visible_paragraphs_and_stops_before_bibliography(tmp_path):
    path = tmp_path / 'main.docx'
    with ZipFile(path, 'w') as package:
        package.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>We found an effect.</w:t></w:r></w:p><w:p><w:r><w:t>References</w:t></w:r></w:p><w:p><w:r><w:t>Bibliography is excluded.</w:t></w:r></w:p></w:body></w:document>')
    text = next(iter(lint.load_input(path).values()))
    assert 'We found an effect.' in text
    assert 'Bibliography' not in text


def test_missing_comparison_files_are_reported_without_false_growth():
    report = lint.analyze({'New_EN.md': 'A new analysis is reported.'},
                          {'Old_EN.md': 'An older analysis was reported.'})
    assert report['comparison']['added_files'] == ['New_EN.md']
    assert report['comparison']['removed_files'] == ['Old_EN.md']
    assert any(x['rule'] == 'comparison-inventory' for x in report['findings'])


def test_cli_returns_zero_for_diagnostics_and_never_rewrites_sources(tmp_path):
    source = tmp_path / 'Results_EN.md'
    source.write_text('In the single evaluated seed, the result was small. ' * 12, encoding='utf8')
    original = source.read_bytes()
    output = tmp_path / 'report.json'
    result = subprocess.run([sys.executable, '-B', str(Path(lint.__file__)), str(source),
                             '--report', str(output)], capture_output=True, text=True, encoding='utf8')
    assert result.returncode == 0
    assert json.loads(output.read_text(encoding='utf8'))['findings']
    assert source.read_bytes() == original


def test_versioned_file_names_share_a_comparison_unit(tmp_path):
    old = tmp_path / 'manuscript_v20.md'
    new = tmp_path / 'manuscript_v22.md'
    old.write_text('The effect was small.', encoding='utf8')
    new.write_text('The effect was small. ' * 10, encoding='utf8')
    report = lint.analyze(lint.load_input(new), lint.load_input(old))
    assert report['comparison']['compared_files'] == ['document']
    assert any(x['rule'] == 'phrase-growth' for x in report['findings'])


def test_cli_rejects_source_overwrite_and_invalid_docx(tmp_path):
    source = tmp_path / 'source.md'
    source.write_text('Original scientific text.', encoding='utf8')
    script = str(Path(lint.__file__))
    result = subprocess.run([sys.executable, '-B', script, str(source), '--report', str(source)],
                            capture_output=True, text=True, encoding='utf8')
    assert result.returncode == 1
    assert source.read_text(encoding='utf8') == 'Original scientific text.'
    invalid = tmp_path / 'broken.docx'
    invalid.write_text('Not a ZIP archive.', encoding='utf8')
    result = subprocess.run([sys.executable, '-B', script, str(invalid)],
                            capture_output=True, text=True, encoding='utf8')
    assert result.returncode == 1 and 'errors' in json.loads(result.stdout)
