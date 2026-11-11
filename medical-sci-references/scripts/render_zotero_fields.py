"""Populate native Zotero field caches from a source-bound CSL plan; no UI/network.

This is offline CSL rendering, not evidence that Word's Zotero Refresh ran.
The legacy checker still verifies the unrendered native-field stage. This module
additionally requires visible numbered citations and a complete bibliography.
"""
from __future__ import annotations
import argparse
import copy
import json
import re
import zipfile
from pathlib import Path
from lxml import etree as E, html
from extract_citations import q, sha, load, save, package, fields, xml_bytes, c14n, visible_text


def plain(value):
    node = html.fragment_fromstring(value, create_parent='div')
    def text(element):
        value = element.text or ''
        for child in element:
            block = child.tag in ('div','p','br')
            value += (' ' if block else '') + text(child) + (' ' if block else '') + (child.tail or '')
        return value
    return re.sub(r'\s+', ' ', text(node)).strip()


def cache_text(field):
    return ''.join((n.text or '') if n.tag == q('t') else '\t'
                   for r in field['result_runs'] for n in r
                   if n.tag in (q('t'), q('tab')))


def wrapper(field):
    result = []
    for run in field['runs']:
        if run in field['result_runs']:
            continue
        node = copy.deepcopy(run)
        for instruction in node.iter(q('instrText')):
            instruction.text = ''
        result.append(c14n(node))
    return result


def prepare(source, plan):
    if plan.get('schema') != 1 or plan.get('source_sha256') != sha(source):
        raise ValueError('Stale CSL plan or unsupported schema')
    parts = package(source)
    root = E.fromstring(parts['word/document.xml'])
    fs = fields(root)
    citations = [f for f in fs if f['kind'] == 'citation']
    bibs = [f for f in fs if f['kind'] == 'bibliography']
    if len(bibs) != 1 or len(citations) != len(plan['citations']):
        raise ValueError('Citation/bibliography field count differs from CSL plan')
    item_ids = {str(i['id']) for f in citations for i in f['data']['citationItems']}
    identities = {}
    for f in citations:
        for item in f['data']['citationItems']:
            iid = item.get('id')
            value = (item.get('uris'), item.get('itemData'))
            if type(iid) is not int or item.get('itemData',{}).get('id') != iid:
                raise ValueError('Invalid native item identity')
            if iid in identities and identities[iid] != value:
                raise ValueError('Conflicting payloads for the same native item identity')
            identities[iid] = value
    entries = plan['bibliography']
    ordered = [i for entry in entries for i in entry['item_ids']]
    if len(entries) != len(item_ids) or len(ordered) != len(set(ordered)) or set(ordered) != item_ids:
        raise ValueError('Incomplete, duplicate or unrelated bibliography items')
    numbers = {item: n for n, entry in enumerate(entries, 1) for item in entry['item_ids']}
    data = {str(i['id']):i['itemData'] for f in citations for i in f['data']['citationItems']}
    resources = plan.get('resources')
    if resources is not None:
        for resource in resources.values():
            if sha(resource['path']) != resource['sha256']:
                raise ValueError('CSL input/processor/style/locale changed after rendering')
        input_data = load(resources['input']['path'])
        if input_data['items'] != data or input_data['citations'] != [f['data'] for f in citations]:
            raise ValueError('CSL input does not match actual native citation metadata')
        props = E.fromstring(parts['docProps/custom.xml'])
        pref = ''.join(n[0].text or '' for n in sorted(props,key=lambda n:n.get('name',''))
                       if n.get('name','').startswith('ZOTERO_PREF_'))
        selected = E.fromstring(pref.encode()).find('style').get('id')
        style = E.fromstring(Path(resources['style']['path']).read_bytes())
        actual_style = style.find('{http://purl.org/net/xbiblio/csl}info/{http://purl.org/net/xbiblio/csl}id')
        if actual_style is None or actual_style.text != selected:
            raise ValueError('CSL style differs from the native Zotero document preference')
    for n, entry in enumerate(entries, 1):
        if len(entry['item_ids']) != 1 or not plain(entry['html']).startswith(f'[{n}]'):
            raise ValueError('This renderer requires sequential bracketed numeric bibliography entries')
        normalize_title = lambda text: re.sub(r'[^\w]', '', text).casefold()
        title = normalize_title(data[entry['item_ids'][0]].get('title',''))
        if not title or title not in normalize_title(plain(entry['html'])):
            raise ValueError('Bibliography title does not match its cited item')
    for field, rendered in zip(citations, plan['citations']):
        data = field['data']
        ids = [str(x['id']) for x in data['citationItems']]
        if data['citationID'] != rendered['citationID'] or ids != rendered['item_ids']:
            raise ValueError('CSL plan citation identities/order changed')
        text = plain(rendered['html'])
        if not re.fullmatch(r'\[[\d, \u2013\-]+\]', text):
            raise ValueError('Citation cache is not numeric')
        actual = []
        for token in text[1:-1].split(','):
            ends = re.split(r'[\u2013-]', token.strip())
            if len(ends) == 1:
                actual.append(int(ends[0]))
            elif len(ends) == 2 and int(ends[0]) <= int(ends[1]):
                actual.extend(range(int(ends[0]), int(ends[1])+1))
            else:
                raise ValueError('Invalid citation range')
        if sorted(set(actual)) != sorted({numbers[i] for i in ids}):
            raise ValueError('Citation numbers do not identify their bibliography items')
    return parts, root, citations, bibs[0]


def bibliography_bounds(root, field):
    body = root.find(q('body'))
    start = field['begin'].getparent()
    end = field['end'].getparent()
    if start.getparent() is not body or end.getparent() is not body or start is end:
        raise ValueError('Unsupported bibliography container')
    a, b = body.index(start), body.index(end)
    if b <= a or any(n.tag != q('p') for n in list(body)[a+1:b]):
        raise ValueError('Unsupported bibliography result structure')
    return body, a, b


def render(source, output, plan):
    output = Path(output)
    if output.exists() or output.resolve() == Path(source).resolve():
        raise ValueError('Refuse to overwrite source or existing output')
    parts, root, citations, bib = prepare(source, plan)
    for f, cached in zip(citations, plan['citations']):
        parent = f['begin'].getparent()
        if any(r.getparent() is not parent for r in f['runs']):
            raise ValueError('Citation crosses containers')
        if any(n.tag not in (q('rPr'), q('t')) for r in f['result_runs'] for n in r):
            raise ValueError('Non-text citation results require a separately validated conversion')
        first = f['result_runs'][0] if f['result_runs'] else None
        result = E.Element(q('r'))
        if first is not None and first.find(q('rPr')) is not None:
            result.append(copy.deepcopy(first.find(q('rPr'))))
        E.SubElement(result, q('t')).text = plain(cached['html'])
        at = parent.index(first) if first is not None else parent.index(f['end'])
        for r in f['result_runs']:
            parent.remove(r)
        parent.insert(at, result)
        data = copy.deepcopy(f['data'])
        data['properties']['formattedCitation'] = cached['html']
        data['properties']['plainCitation'] = plain(cached['html'])
        instruction = ' ADDIN ZOTERO_ITEM CSL_CITATION ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ' '
        nodes = [n for r in f['runs'] for n in r if n.tag == q('instrText')]
        nodes[0].text = instruction
        for n in nodes[1:]:
            n.text = ''
    body, a, b = bibliography_bounds(root, bib)
    if any(visible_text(n).strip() for n in list(body)[a+1:b]) or cache_text(bib):
        raise ValueError('Source bibliography already has visible content; use the unrendered native stage')
    for n in list(body)[a+1:b]:
        body.remove(n)
    for index, entry in enumerate(plan['bibliography']):
        paragraph = E.Element(q('p'))
        pr = E.SubElement(paragraph, q('pPr'))
        E.SubElement(pr, q('spacing'), {q('before'):'0', q('after'):'0', q('line'):'240', q('lineRule'):'auto'})
        E.SubElement(pr, q('ind'), {q('left'):'480', q('hanging'):'480'})
        run = E.SubElement(paragraph, q('r'))
        rp = E.SubElement(run, q('rPr'))
        E.SubElement(rp, q('rFonts'), {q('ascii'):'Arial', q('hAnsi'):'Arial'})
        E.SubElement(rp, q('sz'), {q('val'):'24'})
        E.SubElement(run, q('t')).text = plain(entry['html'])
        body.insert(a+1+index, paragraph)
    parts['word/document.xml'] = xml_bytes(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, value in parts.items():
            z.writestr(name, value)
    return check(source, output, plan)


def check(source, candidate, plan):
    errors = []
    try:
        srcpack, src, scit, sbib = prepare(source, plan)
        dstpack = package(candidate)
        dst = E.fromstring(dstpack['word/document.xml'])
        fs = fields(dst)
        dcit = [f for f in fs if f['kind'] == 'citation']
        dbib = [f for f in fs if f['kind'] == 'bibliography']
        if len(dcit) != len(scit) or len(dbib) != 1:
            raise ValueError('Native field count changed')
        original_body, original_a, _ = bibliography_bounds(dst, dbib[0])
        before_bibliography = ' '.join(visible_text(n) for n in list(original_body)[:original_a])
        if re.search(r'\b(?:PMID|DOI|URL|arXiv):', before_bibliography, re.I):
            raise ValueError('Unresolved visible citation markers remain before References')
        for old, new, cached in zip(scit, dcit, plan['citations']):
            expected = copy.deepcopy(old['data'])
            expected['properties']['formattedCitation'] = cached['html']
            expected['properties']['plainCitation'] = plain(cached['html'])
            if new['data'] != expected or cache_text(new) != plain(cached['html']):
                raise ValueError('Citation payload/cache differs from source-bound CSL plan')
            if wrapper(old) != wrapper(new):
                raise ValueError('Native citation wrapper or field-lock attributes changed')
            if any(n.tag not in (q('rPr'), q('t')) for r in new['result_runs'] for n in r):
                raise ValueError('Unexpected content in citation result')
            old_style = old['result_runs'][0].find(q('rPr')) if old['result_runs'] else None
            if any(c14n(r.find(q('rPr'))) != c14n(old_style) for r in new['result_runs']):
                raise ValueError('Citation result style differs from its source formatting')
            parent = new['begin'].getparent()
            if any(r.getparent() is not parent for r in new['runs']):
                raise ValueError('Citation crosses containers')
            at = parent.index(new['begin'])
            for run in new['runs']:
                parent.remove(run)
            for i, run in enumerate(old['runs']):
                parent.insert(at+i, copy.deepcopy(run))
        body, a, b = bibliography_bounds(dst, dbib[0])
        actual = list(body)[a+1:b]
        if len(actual) != len(plan['bibliography']):
            raise ValueError('Visible bibliography entry count differs from cited-item count')
        for paragraph, entry in zip(actual, plan['bibliography']):
            if visible_text(paragraph) != plain(entry['html']):
                raise ValueError('Bibliography text/order differs from CSL output')
            if paragraph.find('.//'+q('drawing')) is not None or paragraph.find('.//'+q('tbl')) is not None:
                raise ValueError('Unexpected nontext bibliography content')
        for paragraph in actual:
            body.remove(paragraph)
        if c14n(src) != c14n(dst):
            raise ValueError('Noncitation text, source formatting, field wrappers, or layout changed')
        changed = [n for n in set(srcpack)|set(dstpack) if n != 'word/document.xml' and srcpack.get(n) != dstpack.get(n)]
        if changed:
            raise ValueError('Non-document package parts changed: '+str(changed))
    except (ValueError, KeyError, TypeError, IndexError, E.XMLSyntaxError) as e:
        errors.append(str(e))
    return {'errors':errors, 'source_sha256':sha(source), 'candidate_sha256':sha(candidate),
            'citation_fields':len(plan.get('citations',[])), 'bibliography_entries':len(plan.get('bibliography',[])),
            'status':'rendered CSL caches verified' if not errors else 'blocked',
            'delivery_ready':not errors, 'word_refresh_tested':False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['render','check'])
    ap.add_argument('source', type=Path)
    ap.add_argument('candidate', type=Path)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    plan = load(args.plan)
    result = render(args.source,args.candidate,plan) if args.mode == 'render' else check(args.source,args.candidate,plan)
    result['plan_sha256'] = sha(args.plan)
    save(args.report,result)
    print(json.dumps(result,ensure_ascii=False))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
