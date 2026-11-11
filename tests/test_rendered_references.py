"""Visible-delivery regressions, including a 53-item bibliography truncated to four."""
import copy
import json
from pathlib import Path
import sys
import zipfile
from docx import Document
from lxml import etree as E
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/'medical-sci-references/scripts'
sys.path.insert(0, str(SCRIPTS))
from extract_citations import extract, fields, package, q, sha, xml_bytes
from inject_zotero_fields import candidate
from render_zotero_fields import render, check, bibliography_bounds, plain


def fixture(tmp_path, count=5):
    source = tmp_path/'source.docx'
    doc = Document()
    doc.add_paragraph('Introduction')
    for i in range(1, count+1):
        doc.add_paragraph(f'Synthetic claim {i} (PMID: {i}).')
    doc.add_paragraph('Repeated grouped claim (PMID: 1; PMID: 2).')
    doc.add_table(rows=1, cols=1).cell(0,0).text = 'Unchanged table'
    doc.add_paragraph('Discussion')
    doc.add_paragraph('Unchanged conclusion.')
    doc.save(source)
    manifest = extract(source)
    snapshot = {'items':[]}
    for i, ref in enumerate(manifest['references'],1):
        key = f'A{i:07d}'
        ref.update(status='既有',key=key,reason='')
        metadata = {'id':100+i,'type':'article-journal','title':f'Synthetic title {i}',
                    'author':[{'family':'Example','given':'A'}], 'issued':{'date-parts':[[2020]]}}
        snapshot['items'].append({'key':key,'raw':{'itemType':'journalArticle','title':metadata['title'], 'extra':f'PMID: {i}'},
          'citation_item':{'id':100+i,'uris':[f'http://zotero.org/users/999/items/{key}'],'itemData':metadata},
          'resolved_identifiers':[ref['id']]})
    native = tmp_path/'native.docx'
    candidate(source,manifest,snapshot,SCRIPTS.parent/'assets/baseline-sample.docx',native)
    fs = [f for f in fields(E.fromstring(package(native)['word/document.xml'])) if f['kind']=='citation']
    plan = {'schema':1,'source_sha256':sha(native),'citations':[], 'bibliography':[]}
    for f in fs:
        ids = [str(x['id']) for x in f['data']['citationItems']]
        plan['citations'].append({'citationID':f['data']['citationID'],'item_ids':ids,
                                 'html':'['+','.join(str(int(i)-100) for i in ids)+']'})
    for i in range(1,count+1):
        plan['bibliography'].append({'item_ids':[str(100+i)],'html':f'<div>[{i}] Example A. Synthetic title {i}. 2020.</div>'})
    output = tmp_path/'rendered.docx'
    assert render(native,output,plan)['errors']==[]
    return native, output, plan


def mutate(path, edit, member='word/document.xml'):
    parts = package(path)
    root = E.fromstring(parts[member])
    edit(root)
    parts[member] = xml_bytes(root)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in parts.items():
            z.writestr(name,data)


def test_complete_visible_delivery(tmp_path):
    native, output, plan = fixture(tmp_path)
    result = check(native,output,plan)
    assert not result['errors']
    assert result['bibliography_entries']==5
    assert result['delivery_ready'] is True
    assert result['word_refresh_tested'] is False


def test_unrendered_native_fields_are_not_final_delivery(tmp_path):
    native, _, plan = fixture(tmp_path)
    assert check(native,native,plan)['errors']
    assert check(native,native,plan)['delivery_ready'] is False


def test_53_cited_items_with_only_four_visible_entries_fails(tmp_path):
    native, output, plan = fixture(tmp_path,53)
    def truncate(root):
        bib = next(f for f in fields(root) if f['kind']=='bibliography')
        body,a,b = bibliography_bounds(root,bib)
        for paragraph in list(body)[a+5:b]:
            body.remove(paragraph)
    mutate(output,truncate)
    assert 'entry count' in ' '.join(check(native,output,plan)['errors'])


def test_incomplete_plan_fails_before_render(tmp_path):
    native, _, plan = fixture(tmp_path)
    plan['bibliography'].pop()
    with pytest.raises(ValueError,match='Incomplete'):
        render(native,tmp_path/'bad.docx',plan)


def test_wrong_citation_number_is_rejected(tmp_path):
    native, output, plan = fixture(tmp_path)
    mutate(output,lambda root:setattr(fields(root)[0]['result_runs'][0].find(q('t')),'text','[5]'))
    assert check(native,output,plan)['errors']


def test_wrong_bibliography_text_is_rejected(tmp_path):
    native, output, plan = fixture(tmp_path)
    def wrong(root):
        bib=next(f for f in fields(root) if f['kind']=='bibliography')
        bib['result_runs'][0].find(q('t')).text='[1] Unrelated paper'
    mutate(output,wrong)
    assert check(native,output,plan)['errors']


def test_wrong_title_in_plan_is_rejected(tmp_path):
    native, _, plan = fixture(tmp_path)
    plan['bibliography'][0]['html']='<div>[1] Wrong title. 2020.</div>'
    with pytest.raises(ValueError,match='title'):
        render(native,tmp_path/'bad.docx',plan)


def test_non_citation_prose_remains_protected(tmp_path):
    native, output, plan = fixture(tmp_path)
    mutate(output,lambda root:setattr(next(root.iter(q('t'))),'text','Changed introduction'))
    assert check(native,output,plan)['errors']


def test_field_lock_mutation_is_rejected(tmp_path):
    native, output, plan = fixture(tmp_path)
    mutate(output,lambda root:fields(root)[0]['begin'].find(q('fldChar')).set(q('fldLock'),'true'))
    assert check(native,output,plan)['errors']


def test_stale_plan_rejected(tmp_path):
    native, output, plan = fixture(tmp_path)
    plan['source_sha256']='0'*64
    assert check(native,output,plan)['errors']


def test_bibliography_block_boundaries_remain_readable():
    assert plain('<div><div>[1]</div><div>Example title.</div></div>') == '[1] Example title.'


def test_changed_csl_resource_rejected(tmp_path):
    native, output, plan = fixture(tmp_path)
    resource = tmp_path/'input.json'
    resource.write_text('{}',encoding='utf-8')
    plan['resources']={'input':{'path':str(resource),'sha256':'0'*64}}
    assert 'changed' in ' '.join(check(native,output,plan)['errors'])
