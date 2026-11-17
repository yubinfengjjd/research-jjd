"""Visible-delivery regressions, including a 53-item bibliography truncated to four."""
import copy
import json
import shutil
import subprocess
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
from render_zotero_fields import render as production_render, check as production_check, bibliography_bounds, plain


def render(source, output, plan, **kwargs):
    return production_render(source,output,plan,validation_mode='synthetic',**kwargs)


def check(source, output, plan, *, validation_mode='synthetic'):
    return production_check(source,output,plan,validation_mode=validation_mode)


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


def test_complete_synthetic_visible_cache_is_not_delivery(tmp_path):
    native, output, plan = fixture(tmp_path)
    result = check(native,output,plan)
    assert not result['errors']
    assert result['bibliography_entries']==5
    assert result['delivery_ready'] is False
    assert result['csl_provenance_verified'] is False
    assert result['word_refresh_tested'] is False


def test_missing_csl_resources_never_proves_production_delivery(tmp_path):
    native, output, plan = fixture(tmp_path)
    result = production_check(native,output,plan)
    assert result['delivery_ready'] is False
    assert result['errors'] and 'resource' in ' '.join(result['errors']).lower()


def test_explicit_synthetic_and_legacy_validation_remain_non_delivery(tmp_path):
    native, output, plan = fixture(tmp_path)
    for mode in ('synthetic','legacy'):
        result = check(native,output,plan,validation_mode=mode)
        assert result['errors'] == []
        assert result['delivery_ready'] is False
        assert result['validation_mode'] == mode


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
    plan['resources']={name:{'path':str(resource),'sha256':'0'*64}
                       for name in ('input','processor','style','locale')}
    assert 'changed' in ' '.join(check(native,output,plan)['errors'])


@pytest.mark.parametrize('missing',['input','processor','style','locale'])
def test_every_production_resource_is_required(tmp_path,missing):
    native, output, plan = fixture(tmp_path)
    resource=tmp_path/'resource';resource.write_text('synthetic',encoding='utf-8')
    plan['resources']={name:{'path':str(resource),'sha256':sha(resource)}
                       for name in ('input','processor','style','locale') if name != missing}
    result=production_check(native,output,plan)
    assert result['errors'] and not result['delivery_ready']


def test_production_render_rejects_resource_free_plan_before_creating_output(tmp_path):
    native, _, plan = fixture(tmp_path)
    destination=tmp_path/'must-not-exist.docx'
    with pytest.raises(ValueError,match='resources'):
        production_render(native,destination,plan)
    assert not destination.exists()


@pytest.mark.skipif(shutil.which('node') is None, reason='Local Node required; no runtime installation')
def test_production_proof_replays_bound_processor_and_rejects_handwritten_output(tmp_path):
    """Synthetic processor stand-in exercises replay contract, not real CSL or Word acceptance."""
    native, _, _ = fixture(tmp_path)
    parts=package(native)
    fs=[f for f in fields(E.fromstring(parts['word/document.xml'])) if f['kind']=='citation']
    data={'source_sha256':sha(native),
          'items':{str(i['id']):i['itemData'] for f in fs for i in f['data']['citationItems']},
          'citations':[f['data'] for f in fs]}
    input_path=tmp_path/'input.json';input_path.write_text(json.dumps(data),encoding='utf-8')
    props=E.fromstring(parts['docProps/custom.xml'])
    preferences=''.join(n[0].text or '' for n in sorted(props,key=lambda n:n.get('name',''))
                        if n.get('name','').startswith('ZOTERO_PREF_'))
    selected=E.fromstring(preferences.encode()).find('style').get('id')
    style_path=tmp_path/'style.csl'
    style_path.write_text('<style xmlns="http://purl.org/net/xbiblio/csl"><info><id>'+selected+'</id></info></style>',encoding='utf-8')
    locale_path=tmp_path/'locale.xml';locale_path.write_text('<locale/>',encoding='utf-8')
    processor_path=tmp_path/'synthetic-processor.js'
    processor_path.write_text('''
var CSL={PROCESSOR_VERSION:'synthetic-contract-fixture-1'};
CSL.Engine=function(sys) {
  const ids=[], rendered=[];
  this.setOutputFormat=function(){};
  this.processCitationCluster=function(citation) {
    for(const item of citation.citationItems) if(!ids.includes(String(item.id))) ids.push(String(item.id));
    rendered.push('['+citation.citationItems.map(x=>ids.indexOf(String(x.id))+1).join(',')+']');
    return [null,rendered.map((text,index)=>[index,text])];
  };
  this.makeBibliography=function() {
    return [{entry_ids:ids.map(id=>[id])},ids.map((id,i)=>'<div>['+(i+1)+'] '+sys.retrieveItem(id).title+'.</div>')];
  };
};
''',encoding='utf-8')
    plan_path=tmp_path/'provenance-plan.json'
    result=subprocess.run([shutil.which('node'),str(SCRIPTS/'make_csl_plan.cjs'),
                           str(input_path),str(processor_path),str(style_path),str(locale_path),str(plan_path)],
                          capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    output=tmp_path/'proven-caches.docx'
    verified=production_render(native,output,plan)
    assert verified['delivery_ready'] and verified['csl_provenance_verified']
    assert verified['word_refresh_tested'] is False
    plan['bibliography'][0]['html']='<div>[1] Synthetic title 1. Handwritten addition.</div>'
    rejected=production_check(native,output,plan)
    assert not rejected['delivery_ready']
    assert 'replay' in ' '.join(rejected['errors'])
