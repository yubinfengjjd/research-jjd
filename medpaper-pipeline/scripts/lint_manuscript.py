"""Read-only prose diagnostics for Markdown sources or an assembled DOCX.

Counts locate passages to review; they never establish scientific meaning,
authorship, readability, or a required downward trend. Exit 1 means invalid
input, not that a frequency exceeded a suggested review threshold.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from style_check import _blocks, _sentences

WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
FAMILIES = {
    'scope': re.compile(r'\b(?:single|seeds?)\b', re.I),
    'inference': re.compile(r'\b(?:inferential|descriptive|descriptively|without|unresolved)\b', re.I),
    'discourse': re.compile(r'\b(?:alongside|whereas|rather\s+than)\b', re.I),
}
FIGURE_GROUP = re.compile(r'\([^)]*\b(?:Fig(?:ure)?s?\.?|Tables?)\s+S?\d+[^)]*\)', re.I)


def _read_file(path):
    if path.suffix.casefold() == '.docx':
        with ZipFile(path) as package:
            root = ET.fromstring(package.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs = []
        for para in root.findall('w:body/w:p', ns):
            text = ''.join(x.text or '' for x in para.findall('.//w:t', ns))
            if text.strip().casefold() in ('references', 'bibliography'):
                break
            paragraphs.append(text)
        return '\n\n'.join(paragraphs)
    if path.suffix.casefold() not in ('.md', '.txt'):
        raise ValueError('Expected Markdown, text, DOCX, or a manuscript source directory')
    return path.read_text(encoding='utf-8-sig')


def load_input(path):
    """English sources only for directories; DOCX tables are deliberately excluded."""
    path = Path(path)
    if path.is_dir():
        paths = sorted(path.rglob('*_EN.md'))
        if not paths:
            raise ValueError('No *_EN.md sources in manuscript directory')
        return {p.relative_to(path).as_posix(): _read_file(p) for p in paths}
    # A v20.docx and v22.docx are the same comparison unit despite their names.
    return {'document': _read_file(path)}


def _measure(documents):
    grams, singles, families = Counter(), Counter(), Counter()
    sentences, paragraphs, files = [], [], {}
    for name, text in documents.items():
        local = []
        for block, offset, _ in _blocks(text, name):
            words = 0
            for sentence, local_offset in _sentences(block):
                if not WORD.search(sentence):
                    continue
                tokens = [m[0].casefold() for m in WORD.finditer(sentence)]
                singles.update(tokens)
                for n in (3, 4, 5):
                    grams.update(' '.join(tokens[i:i+n]) for i in range(len(tokens)-n+1))
                for family, pattern in FAMILIES.items():
                    families[family] += len(pattern.findall(sentence))
                count = len(sentence.split())
                words += count
                local.append({'file': name, 'line': text.count('\n', 0, offset+local_offset)+1,
                              'words': count, 'figure_table_parentheses': len(FIGURE_GROUP.findall(sentence))})
            if words:
                paragraphs.append({'file': name, 'line': text.count('\n', 0, offset)+1, 'words': words})
        sentences.extend(local)
        files[name] = {'sentences': len(local), 'words': sum(s['words'] for s in local),
                       'sha256': hashlib.sha256(text.encode('utf8')).hexdigest()}
    words = sum(s['words'] for s in sentences)
    metrics = {'words': words, 'sentences': len(sentences),
               'mean_sentence_words': words/len(sentences) if sentences else 0,
               'max_sentence_words': max((s['words'] for s in sentences), default=0),
               'max_paragraph_words': max((p['words'] for p in paragraphs), default=0),
               'figure_table_parentheses': sum(s['figure_table_parentheses'] for s in sentences),
               'families': {f: {'count': families[f], 'per_1000_words': 1000*families[f]/words if words else 0}
                            for f in FAMILIES}}
    return {'metrics': metrics, 'files': files, 'ngrams': grams, 'terms': singles,
            'sentence_metrics': sentences, 'paragraph_metrics': paragraphs}


def analyze(documents, previous=None, allow_terms=(), min_occurrences=9, top=30):
    if min_occurrences < 2 or top < 1:
        raise ValueError('Review frequency must be >=2 and top count must be positive')
    allowed = {' '.join(WORD.findall(t.casefold())) for t in allow_terms}
    current = _measure(documents)
    findings = []
    ranked = sorted(current['ngrams'].items(), key=lambda x: (-x[1], -len(x[0].split()), x[0]))
    ngrams = [{'phrase': p, 'count': c, 'term_allowlisted': p in allowed} for p, c in ranked[:top]]
    for phrase, count in ranked:
        if count >= min_occurrences and phrase not in allowed:
            findings.append({'level': 'INFO', 'rule': 'repeated-phrase', 'phrase': phrase, 'count': count,
                             'hint': 'Read its uses together; a technical term or necessary scope may legitimately repeat.'})
    comparison = None
    if previous is not None:
        shared = sorted(documents.keys() & previous.keys())
        comparison = {'added_files': sorted(documents.keys()-previous.keys()),
                      'removed_files': sorted(previous.keys()-documents.keys()), 'compared_files': shared}
        if comparison['added_files'] or comparison['removed_files']:
            findings.append({'level': 'INFO', 'rule': 'comparison-inventory',
                             'hint': 'Growth/density comparisons use matching files only; inspect inventory changes separately.'})
        before = _measure({k: previous[k] for k in shared})
        after = _measure({k: documents[k] for k in shared})
        growth = []
        for kind in ('terms', 'ngrams'):
            for phrase, count in after[kind].items():
                old = before[kind].get(phrase, 0)
                if count >= min_occurrences and count > 3*old and phrase not in allowed:
                    row = {'level': 'INFO', 'rule': 'phrase-growth', 'phrase': phrase,
                           'before': old, 'after': count, 'ratio': count/old if old else None,
                           'hint': 'Check new content, technical terminology and substituted boilerplate; growth is not a failure.'}
                    growth.append(row)
        growth.sort(key=lambda r: (-r['after'], r['phrase']))
        findings.extend(growth[:top])
        comparison['metrics_before'] = before['metrics']
        comparison['metrics_after'] = after['metrics']
        for family in FAMILIES:
            old = before['metrics']['families'][family]['per_1000_words']
            new = after['metrics']['families'][family]['per_1000_words']
            if shared and new > old:
                findings.append({'level': 'INFO', 'rule': 'family-density-change', 'family': family,
                                 'before': old, 'after': new,
                                 'hint': 'Inspect whether added scope is necessary. These lexical families are not equivalent hedges.'})
    return {'schema_version': 1, 'diagnostic_only': True,
            'method': 'Prose blocks, abbreviation-aware sentences, whitespace words; 3-5-word n-grams reset at sentence/file boundaries. DOCX top-level paragraphs exclude bibliography and tables. Family hits count words/phrases, not semantic qualifications.',
            'metrics': current['metrics'], 'files': current['files'], 'ngrams': ngrams,
            'sentence_metrics': current['sentence_metrics'], 'paragraph_metrics': current['paragraph_metrics'],
            'comparison': comparison, 'findings': findings,
            'boundary': 'No authorship, scientific-equivalence, editorial acceptance, or required decline in word density is inferred.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--allow-term', action='append', default=[])
    parser.add_argument('--min-occurrences', type=int, default=9)
    parser.add_argument('--top', type=int, default=30)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.report and (args.report.resolve() == args.input.resolve()
                            or (args.previous and args.report.resolve() == args.previous.resolve())
                            or (args.input.is_dir() and args.report.resolve().is_relative_to(args.input.resolve()))
                            or (args.previous and args.previous.is_dir() and args.report.resolve().is_relative_to(args.previous.resolve()))):
            raise ValueError('Diagnostic output must be outside both manuscript inputs')
        result = analyze(load_input(args.input), load_input(args.previous) if args.previous else None,
                         args.allow_term, args.min_occurrences, args.top)
        result['inputs'] = {'current': str(args.input), 'previous': str(args.previous) if args.previous else None}
        content = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(content, encoding='utf8')
        print(content)
        return 0
    except (OSError, ValueError, BadZipFile, ET.ParseError, KeyError) as exc:
        print(json.dumps({'errors': [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
