"""Synthetic title checks, independent of journal access or author authentication."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'medical-sci-submission/scripts/submission_guard.py'
spec = importlib.util.spec_from_file_location('title_guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
TITLE = 'Retinal imaging in diabetes: a retrospective study'


def document(path, paragraphs):
    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    xml += ''.join('<w:p><w:r><w:t>'+escape(p)+'</w:t></w:r></w:p>' for p in paragraphs)
    xml += '</w:body></w:document>'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', xml)


def case(tmp_path):
    document(tmp_path/'manuscript.docx', [TITLE, 'Unchanged scientific body.'])
    document(tmp_path/'title-page.docx', [TITLE, 'Synthetic author'])
    (tmp_path/'letter.md').write_text('Dear Editor,\n\nWe submit “'+TITLE+'”.\n', encoding='utf-8')
    allowlist = [{'path':'manuscript.docx','kind':'manuscript'},
                 {'path':'title-page.docx','kind':'title_page'},
                 {'path':'letter.md','kind':'cover_letter'}]
    record = {'original_title':TITLE, 'full_title':TITLE,
              'decision':{'mode':'retain','reason':'The existing title matches the studied design and scope.'},
              'requirements':{'verification':'current','url':'https://example.org/author-guide',
                 'access_date':'2026-11-12','locator':'Synthetic title instructions, paragraph 2',
                 'full_limits':{'max_words':15,'max_characters':100}, 'short_required':False},
              'targets':[{'path':'manuscript.docx','paragraph':1,'role':'full'},
                         {'path':'title-page.docx','paragraph':1,'role':'full'},
                         {'path':'letter.md','paragraph':2,'role':'full','prefix':'We submit “','suffix':'”.'}]}
    return record, allowlist


def test_retained_title_counts_actual_files_and_never_implies_readiness(tmp_path):
    record, allowlist = case(tmp_path)
    before = {e['path']:(tmp_path/e['path']).read_bytes() for e in allowlist}
    report = guard.check_titles(record, tmp_path, allowlist)
    assert report['ok'] and report['status']=='pending_author'
    assert report['counts']['full']=={'words':7,'characters':len(TITLE)}
    assert len(report['artifacts'])==3
    assert all((tmp_path/p).read_bytes()==data for p,data in before.items())


@pytest.mark.parametrize('bad', ['', '[Manuscript title]', '[Title]', '论文标题待定'])
def test_missing_and_placeholder_titles_fail(tmp_path, bad):
    record, allowlist = case(tmp_path)
    record['full_title']=bad
    assert not guard.check_titles(record,tmp_path,allowlist)['ok']


def test_title_in_another_paragraph_does_not_hide_wrong_title(tmp_path):
    record, allowlist = case(tmp_path)
    document(tmp_path/'manuscript.docx', ['A stale title', TITLE])
    report=guard.check_titles(record,tmp_path,allowlist)
    assert 'title_mismatch:manuscript.docx:1' in report['gaps']


def test_omitted_cover_letter_cannot_pass_sync_check(tmp_path):
    record, allowlist=case(tmp_path)
    record['targets']=record['targets'][:2]
    assert 'title_target_missing:letter.md' in guard.check_titles(record,tmp_path,allowlist)['gaps']


def test_recommendation_is_not_selection_or_delegation(tmp_path):
    record, allowlist=case(tmp_path)
    record['decision']={'mode':'recommended','by':'agent','evidence':'candidate ranking'}
    assert 'title_decision_unresolved' in guard.check_titles(record,tmp_path,allowlist)['gaps']


@pytest.mark.parametrize('mode', ['author_selected','delegated'])
def test_changed_title_needs_documented_selection(tmp_path,mode):
    record, allowlist=case(tmp_path)
    record['original_title']='An older title'
    assert not guard.check_titles(record,tmp_path,allowlist)['ok']
    record['decision']={'mode':mode,'by':'Synthetic author','evidence':'Synthetic response selecting the exact title above'}
    assert guard.check_titles(record,tmp_path,allowlist)['ok']
    record['decision']['evidence']='  '
    assert not guard.check_titles(record,tmp_path,allowlist)['ok']


def test_unknown_official_rules_leave_draft_without_invented_limit(tmp_path):
    record, allowlist=case(tmp_path)
    record['requirements']={'verification':'unavailable','short_required':None}
    report=guard.check_titles(record,tmp_path,allowlist)
    assert not report['ok'] and report['status']=='draft'
    assert report['counts']['full']['words']==7
    assert 'title_rules_unresolved' in report['gaps']


def test_limits_use_actual_title_and_short_title(tmp_path):
    record, allowlist=case(tmp_path)
    record['requirements']['full_limits']['max_words']=6
    assert 'title_limit:full:words' in guard.check_titles(record,tmp_path,allowlist)['gaps']
    record['requirements']['full_limits']['max_words']=15
    record['requirements'].update(short_required=True,short_limits={'max_words':None,'max_characters':10})
    assert not guard.check_titles(record,tmp_path,allowlist)['ok']
    record['short_title']='Retinal diabetes'
    record['targets'].append({'path':'manuscript.docx','paragraph':3,'role':'short'})
    document(tmp_path/'manuscript.docx',[TITLE,'Body.','Retinal diabetes'])
    assert 'title_limit:short:characters' in guard.check_titles(record,tmp_path,allowlist)['gaps']


def test_no_universal_word_limit_is_invented(tmp_path):
    record, allowlist=case(tmp_path)
    long_title=' '.join(['Synthetic']*35)
    record['original_title']=record['full_title']=long_title
    record['requirements']['full_limits']={'max_words':None,'max_characters':None}
    document(tmp_path/'manuscript.docx',[long_title])
    document(tmp_path/'title-page.docx',[long_title])
    (tmp_path/'letter.md').write_text('Dear Editor,\n\nWe submit “'+long_title+'”.',encoding='utf-8')
    assert guard.check_titles(record,tmp_path,allowlist)['ok']


def test_actual_title_whitespace_cannot_hide_character_limit(tmp_path):
    record, allowlist=case(tmp_path)
    record['requirements']['full_limits']['max_characters']=len(TITLE)
    document(tmp_path/'title-page.docx',[TITLE.replace(' ', '   ')])
    report=guard.check_titles(record,tmp_path,allowlist)
    assert not report['ok']
    assert 'title_limit:full:characters:title-page.docx' in report['gaps']


def test_complete_required_short_title_is_checked_at_its_location(tmp_path):
    record, allowlist=case(tmp_path)
    record['short_title']='Retinal imaging'
    record['requirements'].update(short_required=True,short_limits={'max_words':3,'max_characters':30})
    document(tmp_path/'manuscript.docx',[TITLE,'Body.','Retinal imaging'])
    record['targets'].append({'path':'manuscript.docx','paragraph':3,'role':'short'})
    assert guard.check_titles(record,tmp_path,allowlist)['ok']


def test_empty_title_rules_cannot_clear_limits_or_selection(tmp_path):
    record, allowlist=case(tmp_path)
    record['requirements']['full_limits']={}
    assert 'title_limits_unresolved:full' in guard.check_titles(record,tmp_path,allowlist)['gaps']


def test_metadata_only_cannot_substitute_for_visible_title(tmp_path):
    record, allowlist=case(tmp_path)
    record['targets'][0].update(location='metadata_title')
    with zipfile.ZipFile(tmp_path/'manuscript.docx','a') as z:
        z.writestr('docProps/core.xml','<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>'+TITLE+'</dc:title></cp:coreProperties>')
    assert 'title_target_missing:manuscript.docx' in guard.check_titles(record,tmp_path,allowlist)['gaps']


@pytest.mark.parametrize('path', ['../outside.docx','C:/outside.docx','_process/private.docx'])
def test_unsafe_target_paths_are_rejected(tmp_path,path):
    record, allowlist=case(tmp_path)
    record['targets'][0]['path']=path
    with pytest.raises(ValueError):
        guard.check_titles(record,tmp_path,allowlist)


def test_cli_checks_real_artifacts_and_returns_draft_for_stale_title(tmp_path):
    record, allowlist=case(tmp_path)
    record_path=tmp_path/'review.json'; list_path=tmp_path/'allowlist.json'
    record_path.write_text(json.dumps(record),encoding='utf-8')
    list_path.write_text(json.dumps(allowlist),encoding='utf-8')
    result=subprocess.run([sys.executable,'-B',str(SCRIPT),'titles',str(record_path),str(tmp_path),str(list_path)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0 and json.loads(result.stdout)['ok']
    document(tmp_path/'title-page.docx',['A stale title'])
    result=subprocess.run([sys.executable,'-B',str(SCRIPT),'titles',str(record_path),str(tmp_path),str(list_path)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==1 and json.loads(result.stdout)['status']=='draft'
