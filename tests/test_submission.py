"""Synthetic offline behavioral checks; no Word, network or real Zotero library."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load("submission_guard", "medical-sci-submission/scripts/submission_guard.py")
state = load("submission_state", "medpaper-pipeline/scripts/submission_state.py")


def field(instruction, display, split=True):
    bits = [instruction[:22], instruction[22:]] if split else [instruction]
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>' + ''.join(
        f'<w:r><w:instrText xml:space="preserve">{escape(b)}</w:instrText></w:r>' for b in bits)
        + '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        + f'<w:r><w:t>{escape(display)}</w:t></w:r>'
        + '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def doc(path, key="ITEMA", uri=None, display="1", bib=True, bib_text="1. Synthetic reference.", split=True):
    item = {"id": key, "uris": [uri or "https://example.org/items/" + key]}
    instruction = ' ADDIN ZOTERO_ITEM CSL_CITATION ' + json.dumps({"citationID": "C1", "citationItems": [item]})
    body = field(instruction, display, split)
    if bib:
        body += field(' ADDIN ZOTERO_BIBL {"uncited":[],"omitted":[],"custom":[]} CSL_BIBLIOGRAPHY ', bib_text, split)
    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p>' + body + '</w:p></w:body></w:document>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)
    return path


def test_split_fields_numeric_cache_layout_and_source_immutable(tmp_path):
    source = doc(tmp_path / "source.docx")
    original = source.read_bytes()
    snap = guard.snapshot(source)
    candidate = doc(tmp_path / "candidate.docx", display="[1]", split=False)
    assert snap["parts"]["word/document.xml"]["citations"][0]["items"][0]["id"] == "ITEMA"
    assert guard.compare(snap, source, candidate)["ok"]
    assert source.read_bytes() == original


@pytest.mark.parametrize("change", [{"key": "ITEMB"}, {"uri": "https://example.org/items/OTHER"}, {"bib": False}, {"bib_text": ""}])
def test_identity_and_bibliography_damage_detected(tmp_path, change):
    source = doc(tmp_path / "source.docx")
    assert not guard.compare(guard.snapshot(source), source, doc(tmp_path / "candidate.docx", **change))["ok"]


def test_changed_source_detected(tmp_path):
    source = doc(tmp_path / "source.docx")
    snap = guard.snapshot(source)
    candidate = doc(tmp_path / "candidate.docx")
    doc(source, key="CHANGED")
    assert "source_hash_changed" in guard.compare(snap, source, candidate)["errors"]


def test_partial_field_support_fails_honestly(tmp_path):
    source = doc(tmp_path / "source.docx")
    with zipfile.ZipFile(source, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:fldSimple w:instr=" ADDIN ZOTERO_ITEM unknown"/></w:document>')
    with pytest.raises(ValueError, match="unsupported"):
        guard.snapshot(source)


def complete_record():
    return {"facts": [{"name": "ethics", "required": True, "value": "waived", "source": "supplied letter paragraph 2", "confirmation": {"by": "author", "evidence": "author response 2"}}],
            "requirements": [{"name": "article rules", "url": "https://example.org/authors", "access_date": "2026-10-19", "provenance": "official", "verification": "current", "resolved": True}],
            "conflicts": [], "checks": {"preservation": "pass", "visual": "pass", "word_refresh": "not_applicable"}}


@pytest.mark.parametrize("problem", ["missing_ethics", "fabricated_confirmation", "offline", "conflict", "preservation"])
def test_missing_or_fabricated_evidence_cannot_clear_gaps(problem):
    record = complete_record()
    if problem == "missing_ethics":
        record["facts"][0]["value"] = ""
    elif problem == "fabricated_confirmation":
        record["facts"][0]["confirmation"] = True
    elif problem == "offline":
        record["requirements"][0]["verification"] = "unavailable"
    elif problem == "conflict":
        record["conflicts"] = ["two incompatible counts"]
    else:
        record["checks"]["preservation"] = "fail"
    assert guard.assess(record)["status"] == "draft"
    assert guard.assess(record)["gaps"]


def test_mechanical_success_never_infers_author_approval():
    assert guard.assess(complete_record())["status"] == "pending_author"
    assert guard.assess({})["status"] == "draft"


@pytest.mark.parametrize("value", [False, 0, "no conflicts declared"])
def test_confirmed_absence_is_valid_with_provenance(value):
    record = complete_record()
    record["facts"][0]["value"] = value
    assert guard.assess(record)["status"] == "pending_author"
    record["facts"][0]["source"] = ""
    assert guard.assess(record)["status"] == "draft"


def rewrite(path, transform):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode()
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", transform(xml))


def test_real_paragraph_run_splitting_and_numeric_display_record(tmp_path):
    source = doc(tmp_path / "source.docx")
    baseline = guard.snapshot(source)
    assert baseline["citation_displays"] == {"word/document.xml": ["1"]}
    candidate = doc(tmp_path / "candidate.docx", display="[1]")
    rewrite(candidate, lambda xml: xml.replace('</w:r><w:r>', '</w:r></w:p><w:p><w:r>').replace('Synthetic reference.', 'Synthetic </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>reference.'))
    assert guard.compare(baseline, source, candidate)["ok"]


def test_citation_sequence_and_bibliography_count(tmp_path):
    source = doc(tmp_path / "source.docx")
    second = field(' ADDIN ZOTERO_ITEM CSL_CITATION ' + json.dumps({"citationID": "C2", "citationItems": [{"id": "ITEMB", "uris": ["https://example.org/items/ITEMB"]}]}), "2")
    rewrite(source, lambda xml: xml.replace('</w:body>', '<w:p>' + second + '</w:p></w:body>'))
    baseline = guard.snapshot(source)
    candidate = tmp_path / "candidate.docx"
    candidate.write_bytes(source.read_bytes())
    rewrite(candidate, lambda xml: xml.replace('<w:body>', '<w:body><w:p>' + second + '</w:p>').replace('<w:p>' + second + '</w:p></w:body>', '</w:body>'))
    assert not guard.compare(baseline, source, candidate)["ok"]
    candidate.write_bytes(source.read_bytes())
    rewrite(candidate, lambda xml: xml.replace('</w:body>', '<w:p>' + field(' ADDIN ZOTERO_BIBL {"uncited":[],"omitted":[],"custom":[]} CSL_BIBLIOGRAPHY ', '1. Synthetic reference.') + '</w:p></w:body>'))
    assert not guard.compare(baseline, source, candidate)["ok"]


@pytest.mark.parametrize("replacement", [
    lambda xml: xml.replace('ZOTERO_ITEM CSL_CITATION', 'ZOTERO_UNKNOWN CSL_CITATION'),
    lambda xml: xml.replace('w:fldCharType="end"', 'w:fldCharType="unknown"'),
    lambda xml: xml.replace('"ITEMA"', '"ITEMB"', 1),
])
def test_bad_or_changed_fields_never_pass(tmp_path, replacement):
    source = doc(tmp_path / "source.docx")
    candidate = doc(tmp_path / "candidate.docx", split=False)
    rewrite(candidate, replacement)
    try:
        result = guard.compare(guard.snapshot(source), source, candidate)
    except ValueError:
        return
    assert not result["ok"]


def test_requirement_provenance_is_required_even_when_resolved():
    for change in [{"provenance": "third_party"}, {"access_date": ""}, {"url": ""}, {"resolved": False}]:
        record = complete_record()
        record["requirements"][0].update(change)
        assert guard.assess(record)["status"] == "draft"


def test_cli_json_failure_and_read_only_snapshot(tmp_path):
    source = doc(tmp_path / "source.docx")
    original = source.read_bytes()
    script = ROOT / "medical-sci-submission/scripts/submission_guard.py"
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(script), "snapshot", str(source)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0
    baseline = tmp_path / "baseline.json"
    baseline.write_text(result.stdout, encoding="utf-8")
    candidate = doc(tmp_path / "candidate.docx", key="OTHER")
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(script), "compare", str(baseline), str(source), str(candidate)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 1 and json.loads(result.stdout)["ok"] is False
    assert source.read_bytes() == original


def test_allowlist_packaging_and_privacy(tmp_path):
    root = tmp_path / "delivery"
    root.mkdir()
    (root / "adapted.docx").write_bytes(b"synthetic")
    (root / "private.txt").write_text("private")
    output = tmp_path / "package.zip"
    entries = [{"path": "adapted.docx", "kind": "manuscript"}]
    assert guard.package(root, entries, output) == ["adapted.docx"]
    with zipfile.ZipFile(output) as z:
        assert z.namelist() == ["adapted.docx"]
    for bad in [{"path": "private.txt", "kind": "consent"}, {"path": "../private.txt", "kind": "attachment"}]:
        with pytest.raises(ValueError):
            guard.package(root, [bad], tmp_path / "bad.zip")


def project():
    return '| # | 阶段 | 技能 | 状态 | 当前产物 | 版本 | 确认日期 | 备注 |\n|---|---|---|---|---|---|---|---|\n' + ''.join(
        f'| {i} | stage | skill | 已确认 | artifact | v1 | date | |\n' for i in range(11, 13))


def test_old_project_migration_idempotent_and_bounded_invalidation():
    migrated = state.update(project())
    assert '| 13 |' in migrated and '| 未开始 | 06_submission/' in migrated
    assert state.update(migrated) == migrated
    accepted = migrated.replace('| 未开始 | 06_submission/', '| 已确认 | 06_submission/')
    invalidated = state.update(accepted, changed_stage=11)
    rows = {line.split('|')[1].strip(): line for line in invalidated.splitlines() if line.startswith('| ')}
    assert '需返工' in rows['12'] and '需返工' in rows['13']
    assert '已确认' in rows['11']
    assert state.update(accepted, changed_stage=13) == accepted
    assert state.update(accepted, changed_stage=7, affects_main=False) == accepted
    assert '需返工' in state.update(accepted, changed_stage=12).splitlines()[-1]


def test_stage_migration_does_not_rewrite_unrelated_numbered_table():
    unrelated = '\n## Other\n| 12 | unrelated | skill | 已确认 | keep | v1 | date | |\n'
    result = state.update(project() + unrelated, changed_stage=11)
    assert result.endswith(unrelated)
    assert result.count('| 13 |') == 1


def test_package_refuses_overwrite_and_process_inputs(tmp_path):
    root = tmp_path / "delivery"
    root.mkdir()
    (root / "_process").mkdir()
    (root / "_process/notes.md").write_text("private evidence")
    (root / "adapted.docx").write_bytes(b"synthetic")
    output = tmp_path / "existing.zip"
    output.write_bytes(b"keep")
    with pytest.raises(ValueError, match="overwrite"):
        guard.package(root, [{"path": "adapted.docx", "kind": "manuscript"}], output)
    assert output.read_bytes() == b"keep"
    with pytest.raises(ValueError):
        guard.package(root, [{"path": "_process/notes.md", "kind": "requirements"}], tmp_path / "new.zip")


@pytest.mark.parametrize("revision", ["del", "moveFrom"])
@pytest.mark.parametrize("delimiter", ["begin", "separate", "end"])
def test_tracked_revision_of_zotero_delimiter_rejected(tmp_path, revision, delimiter):
    source = doc(tmp_path / "source.docx")
    candidate = doc(tmp_path / "candidate.docx")
    run = f'<w:r><w:fldChar w:fldCharType="{delimiter}"/></w:r>'
    rewrite(candidate, lambda xml: xml.replace(run, f'<w:{revision} w:id="1" w:author="Synthetic">{run}</w:{revision}>', 1))
    with pytest.raises(ValueError, match="unsupported.*revision"):
        guard.compare(guard.snapshot(source), source, candidate)


@pytest.mark.parametrize("revision", ["del", "moveFrom"])
def test_tracked_revision_of_split_instruction_without_zotero_token_rejected(tmp_path, revision):
    import re
    source = doc(tmp_path / "source.docx")
    candidate = doc(tmp_path / "candidate.docx")
    def change(xml):
        run = re.findall(r'<w:r><w:instrText[^>]*>.*?</w:instrText></w:r>', xml)[1]
        assert "ZOTERO" not in run
        return xml.replace(run, f'<w:{revision} w:id="1" w:author="Synthetic">{run}</w:{revision}>', 1)
    rewrite(candidate, change)
    with pytest.raises(ValueError, match="unsupported.*revision"):
        guard.compare(guard.snapshot(source), source, candidate)


@pytest.mark.parametrize("field", ["source", "by", "evidence"])
def test_whitespace_provenance_reports_specific_gap(field):
    record = complete_record()
    if field == "source":
        record["facts"][0][field] = " \t "
    else:
        record["facts"][0]["confirmation"][field] = " \t "
    report = guard.assess(record)
    assert report["status"] == "draft"
    assert "fact_unresolved:ethics:" + field in report["gaps"]


@pytest.mark.parametrize("url", ["https://", "http://", "https:///authors", "https://bad host/authors"])
def test_unusable_http_url_reports_specific_gap(url):
    record = complete_record()
    record["requirements"][0]["url"] = url
    report = guard.assess(record)
    assert report["status"] == "draft"
    assert "requirement_unresolved:article rules:url" in report["gaps"]
