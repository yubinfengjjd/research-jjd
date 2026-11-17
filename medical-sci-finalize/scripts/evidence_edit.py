"""Source-bound structural editing checks; no claim of semantic proof.

All offsets address exact decoded UTF-8 text (no newline normalization).
Only explicitly inventoried EN/ZH/existing EN_ZH groups may be edited.
"""
from __future__ import annotations

from datetime import date
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from collections import Counter


BOUNDARY = ('Exact spans, token checks and recorded review do not prove arbitrary language '
            'equivalence, scientific truth, translation accuracy or author acceptance.')
HASH = re.compile(r'[0-9a-f]{64}')
NUMBER = r'(?<![A-Za-z0-9_.])(?<![A-Za-z]-)[+−-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?'
UNIT = r'(?:µm/px|μm/px|mmHg|mmol/L|mol/L|mg/dL|g/L|kg|mg|µg|μg|ng|pg|mL|ml|µL|μL|dL|mm|cm|µm|μm|nm|px|pixels?|scans?|eyes|subjects?|patients?|cohorts?|clusters?|seeds?|runs?|epochs?|seconds?|ms|Hz|GB|MB|%)'
STANDALONE_UNIT = r'(?:µm/px|μm/px|mmHg|mmol/L|mol/L|mg/dL|g/L|kg|mg|µg|μg|ng|pg|mL|ml|µL|μL|dL|mm|cm|µm|μm|nm|px|pixels?|seconds?|ms|Hz|GB|MB|%)'
TOKENS = [re.compile(NUMBER), re.compile(NUMBER+r'\s*(?:µm/像素|μm/像素|'+UNIT+r'(?![A-Za-z0-9_])|像素)'),
          re.compile(r'\b(?:PMID|DOI|arXiv|URL):\s*[^\s)\];,）】，；：！？、“”‘’《》「」『』]+', re.I),
          re.compile(r'(?:\b(?:Supplementary\s+)?(Fig(?:ure)?s?\.?|Tables?)\s+|(?<![A-Za-z0-9_])((?:补充|附)?[图表])\s*)(S?\d+)'
                     r'([a-z](?:[–-][a-z])?(?:(?:\s*[,、]\s*(?:and\s+)?|\s*[与和及]\s*)(?:S?\d+[a-z](?:[–-][a-z])?|[a-z](?:[–-][a-z])?)|\s+and\s+(?:S?\d+[a-z](?:[–-][a-z])?|[b-z](?:[–-][a-z])?))*)?(?![A-Za-z])', re.I),
          re.compile(r'(?<!\w)(?:µm/像素|μm/像素|'+STANDALONE_UNIT+r'(?![A-Za-z0-9_]))|(?<![\u4e00-\u9fffA-Za-z_])像素|%'),
          re.compile(r'<=|>=|≤|≥|<|>|≠|(?<![A-Za-z])=(?!=)'),
          re.compile(r'\b(?:not estimable|not executed|cross(?:ing|ed|es)? zero|confidence intervals?|'
                     r'not established|cannot establish|(?:did|do|does) not establish|no established|'
                     r'(?:(?:did|do|does) not (?:(?:use|have|report|perform|apply|conduct|include|present|provide|make|show|give|employ|adopt|set|define|impose|require) ){0,3}(?:a |an |any )?(?:prespecified )?inferential (?:threshold|ranking|tests?|testing|comparisons?)|(?:without|no) (?:a |an |any )?(?:prespecified )?inferential (?:threshold|ranking|tests?|testing|comparisons?))|non[- ]inferential|'
                     r'not|no|never|without|failed|inconclusive|unresolved|unestablished|'
                     r'exploratory|descriptive|retrospective|paired|subset|'
                     r'(?:single(?:[- ]evaluated)?|one[- ]evaluated)[- ](?:seed|run)|'
                     r'(?:single[- ]evaluated|one[- ]evaluated)[- ](?:split|fold|reader|rater)|'
                     r'point[- ]estimates?|one[- ]sided|two[- ]sided|cluster[- ]bootstrap|CI)\b|点估计|单随机种子|单个(?:已)?评估种子|单次评估种子|单种子|一个评估种子|唯一接受评价的?种子|单次评估运行|单次运行|一次评估运行|单个评估折|单次评估折|单个评估读者|一名评估读者|单个评估阅片者', re.I),
          re.compile(r'\$\$[\s\S]*?\$\$|(?<!\$)\$(?!\$)[^$\n]+\$|`[^`\n]+`|https?://[^\s)）】，；：！？、“”‘’《》「」『』]+'),
          re.compile(r'(?:\d+(?:\.\d+)?%\s*)?\b(?:CI|confidence intervals?)\s*[:=]?\s*'
                     r'[\[(]?\s*'+NUMBER+r'\s*(?:,|\bto\b|[–—])\s*'+NUMBER+r'\s*[\])]?', re.I),
          re.compile(r'\b(?:first|1st)\b', re.I)]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _object(value, keys, label, optional=()):
    _require(type(value) is dict and set(keys) <= set(value) <= set(keys) | set(optional),
             label+': invalid object keys/type')
    return value


def _list(value, label, nonempty=False):
    _require(type(value) is list and (value or not nonempty), label+': expected '+('nonempty ' if nonempty else '')+'list')
    return value


def _string(value, label):
    _require(type(value) is str and value.strip() and '\x00' not in value, label+': expected nonempty string')
    return value


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _no_links(path):
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        if part.exists() or part.is_symlink():
            st = part.lstat()
            _require(not part.is_symlink() and not getattr(st, 'st_file_attributes', 0) & 0x400,
                     'Symlink/reparse paths are not allowed: '+str(part))
    return path


def _key(value):
    _string(value, 'relative file')
    p = PurePosixPath(value)
    _require(not p.is_absolute() and not any(x in ('', '.', '..') for x in value.split('/'))
             and '\\' not in value and ':' not in value, 'Unsafe relative file: '+value)
    return value


def _json(path):
    path = _no_links(path)
    _require(path.is_file(), 'Missing JSON manifest: '+str(path))
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'Duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(path.read_bytes().decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant: '+value)))


def _tree(path):
    path = _no_links(path)
    _require(path.is_dir(), 'Expected manuscript directory: '+str(path))
    result = {}
    for entry in path.rglob('*'):
        _no_links(entry)
        if entry.is_file():
            result[entry.relative_to(path).as_posix()] = entry.read_bytes()
        else:
            _require(entry.is_dir(), 'Nonregular manuscript entry: '+str(entry))
    return result


def _group(key):
    for suffix in ('_EN_ZH.md', '_EN.md', '_ZH.md'):
        if key.endswith(suffix):
            return key[:-len(suffix)]
    return None


def _section(text, offset, aliases=None):
    stack = []
    for match in re.finditer(r'^([ \t]*#{1,6})[ \t]+([^\r\n]+)', text, re.M):
        if match.start() > offset:
            break
        level = match[1].count('#')
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, (aliases or {}).get(match.start(), match[2].strip())))
    return tuple(stack)


def _span(value, texts, label):
    _object(value, ('file', 'start', 'end', 'text'), label)
    key = _key(value['file'])
    _require(key in texts, label+': file outside managed inventory')
    a, b = value['start'], value['end']
    _require(type(a) is int and type(b) is int and 0 <= a < b <= len(texts[key]), label+': invalid offsets')
    _string(value['text'], label+' text')
    _require(texts[key][a:b] == value['text'], label+': exact span mismatch')
    return value


def _spans(values, texts, label):
    return [_span(x, texts, label) for x in _list(values, label, True)]


def _inside(inner, outer):
    return any(inner['file'] == x['file'] and x['start'] <= inner['start'] < inner['end'] <= x['end'] for x in outer)


def _canonical_scope_anchor(text):
    return re.sub(r'(?i)\b(seed|run)[-\s]+(\d+)\b', lambda m: m[1].casefold()+' '+m[2], text)


def _pairs(values, old, new, source, candidate, label, nonempty=True, scoped=False):
    pairs = _list(values, label, nonempty)
    axes = set()
    for pair in pairs:
        _object(pair, ('axis', 'source', 'candidate') if scoped else ('source', 'candidate'), label)
        if scoped:
            axis = pair['axis']
            _require(type(axis) is str and axis in {'cohort', 'population', 'endpoint', 'analysis', 'run', 'subset', 'ci_owner', 'timepoint', 'unit'}
                     and axis not in axes, 'Each claim requires one unique scientific unit per scope axis')
            axes.add(axis)
        a, b = _span(pair['source'], old, label), _span(pair['candidate'], new, label)
        _require(_inside(a, source) and _inside(b, candidate), label+': anchor outside claim')
        same = _canonical_scope_anchor(a['text']) == _canonical_scope_anchor(b['text']) if scoped else a['text'] == b['text']
        _require(same, label+': immutable anchor changed')
    return pairs


def _owner_occurrences(text):
    """Return ordered (start, end, axis, canonical_label) owner hits."""
    hits = []
    pattern = (r'(?<![\w\-‐‑‒–—−])((?i:analysis|cohort|group|population|subset|endpoint|outcome|seed|run))'
               r'(?:[ \t]+([A-Z][A-Za-z0-9_-]*|\d+)|[-‐‑‒–—−](\d+))(?![A-Za-z0-9_])'
               r'|(分析|队列|亚组|(?<![\u4e00-\u9fff])组|终点|种子|运行)[ \t]*([A-Z][A-Za-z0-9_-]*|\d+)(?![A-Za-z0-9_])')
    for match in re.finditer(pattern, text):
        if match[1]:
            raw_axis = match[1].casefold()
            raw_id = match[2] if match[2] is not None else match[3]
            if raw_axis in ('seed', 'run') and not re.fullmatch(r'[A-Z]\d*|\d+', raw_id):
                continue
            axis = {'group': 'population', 'outcome': 'endpoint', 'seed': 'run'}.get(raw_axis, raw_axis)
            canon = raw_axis + ' ' + raw_id.casefold()
        else:
            axis_cn, raw_id = match[4], match[5]
            if axis_cn in ('种子', '运行') and not re.fullmatch(r'[A-Z]\d*|\d+', raw_id):
                continue
            axis = {'分析': 'analysis', '队列': 'cohort', '亚组': 'subset', '组': 'population', '终点': 'endpoint', '种子': 'run', '运行': 'run'}[axis_cn]
            canon_prefix = {'分析': 'analysis', '队列': 'cohort', '亚组': 'subset', '组': 'group', '终点': 'endpoint', '种子': 'seed', '运行': 'run'}[axis_cn]
            canon = canon_prefix + ' ' + raw_id.casefold()
        hits.append((match.start(), match.end(), axis, canon))
    return hits


def _named_scopes(text):
    """Conservative explicit owner-label detection, not general semantic inference."""
    result = {}
    for _, _, axis, canon in _owner_occurrences(text):
        result.setdefault(axis, set()).add(canon)
    return result


def _multi_owner_segments_preserved(before_text, after_text):
    """Allow edits inside multi-owner spans iff owner order and per-segment evidence hold."""
    hb = _owner_occurrences(before_text)
    ha = _owner_occurrences(after_text)
    if [(ax, lbl) for _, _, ax, lbl in hb] != [(ax, lbl) for _, _, ax, lbl in ha] or not hb:
        return False
    def segs(txt, hits):
        bounds = [0] + [pos for s, e, _, _ in hits for pos in (s, e)] + [len(txt)]
        return [txt[bounds[2 * i]:bounds[2 * i + 1]] for i in range(len(hits) + 1)]
    b_segs = segs(before_text, hb)
    a_segs = segs(after_text, ha)
    b_tok_list = [_tokens(s) for s in b_segs]
    a_tok_list = [_tokens(s) for s in a_segs]
    for bt, at in zip(b_tok_list, a_tok_list):
        if not _evidence_equal({t for t in bt if t[0] != 3}, {t for t in at if t[0] != 3}):
            return False
    b_cits = [{t for t in bt if t[0] == 3} for bt in b_tok_list]
    a_cits = [{t for t in at if t[0] == 3} for at in a_tok_list]
    all_b, all_a = set().union(*b_cits), set().union(*a_cits)
    if all_b != all_a:
        return False
    for i, (bc, ac) in enumerate(zip(b_cits, a_cits)):
        if any(added not in all_b for added in (ac - bc)):
            return False
        for removed in (bc - ac):
            if not any(removed in b_cits[j] for j in range(len(b_cits)) if j != i):
                return False
    return True


def _ownership(source, candidate, scope):
    declared = {x['axis']: x for x in scope}
    src_txt, dst_txt = _content(source), _content(candidate)
    multi_safe = _named_scopes(src_txt) == _named_scopes(dst_txt) and _multi_owner_segments_preserved(src_txt, dst_txt)
    for spans, side in [(source, 'source'), (candidate, 'candidate')]:
        for axis, labels in _named_scopes(_content(spans)).items():
            decl_labels = _named_scopes(declared[axis][side]['text']).get(axis, set()) if axis in declared else set()
            if len(labels) == 1:
                _require(axis in declared and labels <= decl_labels,
                         'Ambiguous/unmapped scientific scope ownership; split or preserve affected unit: '+axis)
            else:
                _require(multi_safe and axis in declared and decl_labels <= labels,
                         'Ambiguous/unmapped scientific scope ownership; split or preserve affected unit: '+axis)


def _contexts(values, old, new, source, candidate, fact_source, fact_candidate, scopes, headings=(), removed=()):
    left, right, seen = [], [], set()
    for record in _list(values, 'fact context', True):
        _object(record, ('source', 'candidate', 'scope'), 'fact context')
        a, b = _span(record['source'], old, 'context source'), _span(record['candidate'], new, 'context candidate')
        _require(_inside(a, source) and _inside(b, candidate), 'Fact context outside claim')
        indices = _list(record['scope'], 'context scope indices', True)
        _require(all(type(i) is int and 0 <= i < len(scopes) for i in indices) and len(set(indices)) == len(indices),
                 'Invalid context scope references')
        for i in indices:
            sc_s, sc_d = scopes[i]['source']['text'], scopes[i]['candidate']['text']
            direct = sc_s in a['text'] and sc_d in b['text']
            _require(direct or (_canonical_scope_anchor(sc_s) in _canonical_scope_anchor(a['text']) and
                     _canonical_scope_anchor(sc_d) in _canonical_scope_anchor(b['text'])),
                     'Fact context does not retain owning scientific scope')
        owned_before, owned_after = _named_scopes(a['text']), _named_scopes(b['text'])
        single_ok = all(len(labels) == 1 for labels in owned_before.values())
        multi_ok = any(len(labels) > 1 for labels in owned_before.values()) and _multi_owner_segments_preserved(a['text'], b['text'])
        _require(owned_before == owned_after and (single_ok or multi_ok),
                 'Ambiguous/changed owner labels in fact context; preserve or split affected unit')
        ctx_src = _tokens(_body_content(_without_removed([a], removed), headings, 'source'))
        ctx_dst = _tokens(_body_content([b], headings, 'candidate'))
        ctx_src = _ignore_contradicted_noninferential(ctx_src, ctx_dst, a['text'], b['text'])
        _require(_evidence_equal(ctx_src, ctx_dst),
                 'Fact context lost numeric/citation/qualifier evidence')
        seen.update(indices)
        left.append(a)
        right.append(b)
    _require(seen == set(range(len(scopes))), 'Fact context omits declared scientific scope axes')
    _require(all(_inside(x, left) for x in fact_source) and all(_inside(x, right) for x in fact_candidate),
             'Fact lacks local scope-bound context')


def _tokens(text):
    text = re.sub(r'(?i)(?<![/\w.-])(seed|run)-(\d+)\b', r'\1 \2', text)
    result = EvidenceTokens()
    masked = [(m.start(), m.end()) for idx in (2, 3, 9) for m in TOKENS[idx].finditer(text)]
    for i, pattern in enumerate(TOKENS):
        for match in pattern.finditer(text):
            if i in (0, 1) and any(a <= match.start() and match.end() <= b for a, b in masked):
                continue
            if i == 3:
                raw_kind = (match[1] or match[2]).casefold()
                kind = 'table' if ('table' in raw_kind or '表' in raw_kind) else 'fig'
                num = match[3].casefold()
                tail = match[4]
                if not tail:
                    result.add((3, f'{kind} {num}'))
                else:
                    for part in re.finditer(r'(?:(s?\d+)([a-z])|([a-z])[–-]([a-z])|([a-z]))', tail.casefold()):
                        if part[1]:
                            result.add((3, f'{kind} {part[1]}{part[2]}'))
                        elif part[3]:
                            lo, hi = ord(part[3]), ord(part[4])
                            if lo <= hi <= lo + 10:
                                for code in range(lo, hi + 1):
                                    result.add((3, f'{kind} {num}{chr(code)}'))
                            else:
                                result.add((3, f'{kind} {num}{part[3]}–{part[4]}'))
                        else:
                            result.add((3, f'{kind} {num}{part[5]}'))
            elif i == 6:
                val = re.sub(r'\s+', ' ', match[0]).casefold()
                if val in ('not established', 'cannot establish', 'did not establish', 'do not establish',
                           'does not establish', 'no established'):
                    result.add_qualifier('neg')
                    result.add_qualifier('unestablished')
                    continue
                if val in ('non-inferential', 'non inferential'):
                    result.add_qualifier('non-inferential')
                    continue
                if re.match(r'(?:without|no|(?:did|do|does) not)\b', val) and 'inferential' in val:
                    prefix = 'no-prespecified-' if 'prespecified' in val else 'no-'
                    noun = ('testing' if re.search(r'\b(?:tests?|testing)$', val) else
                            'comparison' if re.search(r'\bcomparisons?$', val) else
                            'threshold' if val.endswith('threshold') else 'ranking')
                    state = prefix + 'inferential-' + noun
                    result.add_qualifier(state)
                    continue
                if val in ('not', 'no', 'without'):
                    val = 'neg'
                elif re.fullmatch(r'(?:single(?:[- ]evaluated)?|one[- ]evaluated)[- ](?:seed|run)|(?:single[- ]evaluated|one[- ]evaluated)[- ](?:split|fold|reader|rater)|单随机种子|单个(?:已)?评估种子|单次评估种子|单种子|一个评估种子|唯一接受评价的?种子|单次评估运行|单次运行|一次评估运行|单个评估折|单次评估折|单个评估读者|一名评估读者|单个评估阅片者', val, re.I):
                    val = 'single-run'
                elif re.fullmatch(r'point[- ]estimates?|点估计', val):
                    val = 'point-estimate'
                result.add_qualifier(val)
            elif i == 9:
                result.add((9, 'first'))
            else:
                tok_text = re.sub(r'\s+', ' ', match[0]).casefold()
                if i in (1, 4):
                    tok_text = tok_text.replace('μ', 'µ').replace('/像素', '/px')
                    tok_text = re.sub(r'(\d)\s*像素', r'\1 px', tok_text)
                    tok_text = tok_text.replace('像素', 'px')
                result.add((i, tok_text))
    return result


class EvidenceTokens(set):
    """Set-compatible tokens; repetition counts are diagnostic, not scientific state."""

    def __init__(self):
        super().__init__()
        self.qualifier_counts = Counter()

    def add_qualifier(self, value):
        self.add((6, value))
        self.qualifier_counts[value] += 1


def _evidence_equal(before, after):
    before_q = {t for t in before if t[0] == 6}
    after_q = {t for t in after if t[0] == 6}
    if (6, 'unresolved') in before_q and (6, 'unestablished') in after_q:
        before_q = (before_q - {(6, 'unresolved')}) | {(6, 'neg'), (6, 'unestablished')}
    return ({t for t in before if t[0] != 6} == {t for t in after if t[0] != 6} and before_q == after_q)


_REPORTED_TEST = re.compile(r'\b(?:permutation|sign-flip|P\s*[=<>≤≥])', re.I)


def _ignore_contradicted_noninferential(before, after, source_text, candidate_text):
    """Drop a non-inferential label only when the same span still reports the test."""
    if (6, 'non-inferential') not in set(before) or (6, 'non-inferential') in set(after):
        return before
    if not _REPORTED_TEST.search(source_text) or not _REPORTED_TEST.search(candidate_text):
        return before
    added = {t for t in after if t[0] == 6} - {t for t in before if t[0] == 6}
    if added:
        return before
    return {t for t in before if t != (6, 'non-inferential')}


def _content(spans):
    return '\n'.join(x['text'] for x in spans)


def _without_removed(spans, removed):
    """Mask only exact, independently validated inherited qualifier slots."""
    result = []
    for value in spans:
        chars = list(value['text'])
        for slot in removed:
            if slot['file'] == value['file']:
                lo, hi = max(slot['start'], value['start']), min(slot['end'], value['end'])
                if hi > lo:
                    chars[lo-value['start']:hi-value['start']] = ' ' * (hi-lo)
        result.append(dict(value, text=''.join(chars)))
    return result


def _scope_declarations(review, old, new, managed, remember, identity):
    """Bounded reviewed single-run inheritance, never general prose inference.

    Legacy records have no declarations and keep their original local semantics.
    Every allowance is an exact source qualifier -> unchanged declaration mapping.
    """
    claims = {c['id']: c for c in _list(review['claims'], 'claims')}
    result = {}
    slots = set()
    for declaration in _list(review.get('scope_declarations', []), 'scope declarations'):
        _object(declaration, ('id', 'reviewed_by', 'rationale', 'source', 'candidate', 'bindings'), 'scope declaration')
        remember(declaration['id'])
        identity(declaration['reviewed_by'], 'scientific')
        _string(declaration['rationale'], 'scope declaration rationale')
        ds, dc = _span(declaration['source'], old, 'declaration source'), _span(declaration['candidate'], new, 'declaration candidate')
        _require(ds['file'] == dc['file'] and ds['text'] == dc['text'], 'Governing declaration must remain exact and in its original file')
        declaration_tokens = _tokens(ds['text'])
        _require(not ({(6, 'neg'), (6, 'never'), (6, 'not executed'), (6, 'not estimable'),
                       (6, 'failed'), (6, 'inconclusive'), (6, 'unresolved'), (6, 'unestablished')} & declaration_tokens)
                 and not re.search(r'\b(?:except|excluded?|excluding|neither|nor|never|not|no|without|cannot)\b|'
                                   r"\b(?:ca|could|did|does|do|is|are|was|were|has|have|had|wo|would|should|must|need|sha)n['’]t\b|"
                                   r'rather than|instead of|other than|[不未无非没否]|排除|除外|以外|之外', ds['text'], re.I),
                 'Governing declaration must affirm its seed/run scope; negated or exclusionary declarations cannot govern removal')
        declared_runs = _named_scopes(ds['text']).get('run', set())
        _require(len(declared_runs) <= 1 and not re.search(
            r'\b(?:seeds|runs)\b|\b(?:seed|run)[ -]+\d+\s*(?:[,/–—-]|and\b|to\b)|种子\s*\d+\s*[、,，–—-]', ds['text'], re.I),
            'Declaration may not cover multiple/ranged seed or run identities')
        _require((6, 'single-run') in declaration_tokens or (len(declared_runs) == 1 and re.search(
            r'\b(?:used?|using|evaluat\w*|performed|executed|trained|model|generated|computed|derived|calculated|estimated|fitted|with)\b|使用|采用|评估|评价|执行|模型|计算|构建|生成|基于|训练|完成', ds['text'], re.I)),
                 'Declaration must state one evaluated run or exactly one explicit named run')
        for binding in _list(declaration['bindings'], 'declaration bindings', True):
            _object(binding, ('claim', 'language', 'source', 'candidate', 'removed', 'guards'), 'declaration binding')
            cid, language = binding['claim'], binding['language']
            _require(type(cid) is str and cid in claims and language in ('EN', 'ZH', 'EN_ZH'), 'Invalid declaration claim/language binding')
            claim = claims[cid]
            target = claim if language == 'EN' else next((x for x in claim['translations'] if x['language'] == language), None)
            _require(target is not None and binding['source'] == target['source'] and binding['candidate'] == target['candidate'],
                     'Declaration governed spans must exactly match the bound claim/language')
            source, candidate = _spans(binding['source'], old, 'governed source'), _spans(binding['candidate'], new, 'governed candidate')
            key = source[0]['file']
            _require(all(x['file'] == key for x in source+candidate) and key.endswith('_'+language+'.md') and ds['file'].endswith('_'+language+'.md'),
                     'Declaration language/file binding mismatch')
            same_section = (ds['file'] == key and ds['end'] <= min(x['start'] for x in source) and dc['end'] <= min(x['start'] for x in candidate)
                            and _section(old[key], ds['start']) == _section(old[key], source[0]['start'])
                            and _section(new[key], dc['start']) == _section(new[key], candidate[0]['start']))
            cross = (Path(ds['file']).name.casefold() == ('methods_'+language+'.md').casefold()
                     and Path(key).name.casefold() == ('results_'+language+'.md').casefold())
            _require(same_section or cross, 'Declaration inheritance limited to earlier same-heading text or Methods to Results')
            guards = _list(binding['guards'], 'declaration guards', True)
            axes = set()
            combined = [_content(source), _content(candidate), ds['text'], dc['text']]
            for guard in guards:
                _object(guard, ('axis', 'text'), 'declaration guard', ('location',))
                axis, text = guard['axis'], _string(guard['text'], 'guard text')
                _require(axis in {'analysis', 'cohort', 'population', 'subset', 'endpoint', 'run', 'timepoint', 'unit', 'ci_owner'}, 'Invalid declaration guard axis')
                axes.add(axis)
                location = guard.get('location', 'all')
                _require(location == 'all' or (location == 'declaration' and axis == 'run'), 'Only an explicit run guard may bind declaration-only scope')
                _require(all(text in paragraph for paragraph in (combined[2:] if location == 'declaration' else combined)),
                         'Declaration owner/endpoint/unit guard absent or changed: '+text)
            _require(bool(axes & {'analysis', 'cohort', 'population'}) and 'endpoint' in axes,
                     'Declaration requires explicit owning analysis/cohort and endpoint guards')
            for text in combined[:2]:
                for axis, labels in _named_scopes(text).items():
                    _require(len(labels) == 1 and axis in axes and any(labels <= _named_scopes(g['text']).get(axis, set()) for g in guards if g['axis'] == axis),
                             'Declaration has mixed/unmapped owner, endpoint or seed')
                for token in _tokens(text):
                    if token[0] == 4:
                        _require(any(g['axis'] == 'unit' and token in _tokens(g['text']) for g in guards), 'Declaration omits unit guard')
            removed_input = _list(binding['removed'], 'inherited source qualifier')
            removed = _spans(removed_input, old, 'inherited source qualifier') if removed_input else []
            _require(not declared_runs or any(g['axis'] == 'run' and declared_runs <= _named_scopes(g['text']).get('run', set()) for g in guards),
                     'Explicit named seed/run declaration needs its exact run guard')
            for slot in removed:
                marker = (slot['file'], slot['start'], slot['end'])
                _require(marker not in slots and _inside(slot, source) and _tokens(slot['text']) == {(6, 'single-run')},
                         'Only unique exact single-run qualifier spans may inherit')
                slots.add(marker)
            pair = (cid, language)
            _require(pair not in result, 'Duplicate declaration for governed claim/language')
            result[pair] = removed
    for cid, language in list(result):
        if language == 'EN':
            expected = {'EN'} | {x['language'] for x in claims[cid]['translations']}
            _require({lang for name, lang in result if name == cid} == expected,
                     'Inherited scope missing bilingual/combined declaration binding')
        else:
            _require((cid, 'EN') in result, 'Translated inheritance needs its English declaration binding')
    return result


def _review_status(review, old, new, identity):
    """Machine scaffolds cannot certify identities or a human verbal fact inventory."""
    placeholders = {'scientific editor', 'scientific reviewer', 'bilingual reviewer', 'draft - reviewer required'}
    _require(all(name.strip().casefold() not in placeholders and not name.strip().casefold().startswith('draft') for name in review['reviewers'].values()),
             'Supply actual reviewer identities; generated placeholders cannot certify review')
    if 'review_status' not in review:
        return  # Existing schema-1 review records retain their original semantics.
    status = _object(review['review_status'], ('state', 'reviewed_by', 'rationale', 'facts'), 'review status')
    _require(status['state'] == 'reviewed', 'Draft scaffold requires genuine reviewer identities, rationale and unique verbal fact inventory review')
    identity(status['reviewed_by'], 'scientific')
    _string(status['rationale'], 'verbal inventory review rationale')
    seen = set()
    claims = {c['id']: c for c in review['claims']}
    for fact in _list(status['facts'], 'reviewed unique verbal facts'):
        _object(fact, ('claim', 'source', 'candidate', 'reason'), 'reviewed verbal fact')
        _require(fact['claim'] in claims, 'Verbal inventory references unknown claim')
        claim = claims[fact['claim']]
        left, right = _spans(fact['source'], old, 'verbal source'), _spans(fact['candidate'], new, 'verbal candidate')
        _require(all(_inside(x, claim['source']) for x in left) and all(_inside(x, claim['candidate']) for x in right), 'Verbal inventory outside governed claim')
        _string(fact['reason'], 'unique verbal fact rationale')
        seen.add(fact['claim'])
    _require(seen == claims.keys(), 'Review must explicitly inventory unique verbal facts for every changed claim')


def _body_content(spans, headings, side):
    """Exclude only independently audited exact heading slots, never prose tokens."""
    result = []
    for value in spans:
        cursor = value['start']
        parts = []
        for heading in sorted((h[side] for h in headings if h[side]['file'] == value['file']), key=lambda h: h['start']):
            a, b = max(value['start'], heading['start']), min(value['end'], heading['end'])
            if b > a:
                parts.append(value['text'][cursor-value['start']:a-value['start']])
                cursor = b
        parts.append(value['text'][cursor-value['start']:])
        result.append(' '.join(parts))
    return '\n'.join(result)


def _scope(source, candidate, old, new, aliases=None):
    def scopes(spans, texts, aliases=None):
        result = set()
        for x in spans:
            names = (aliases or {}).get(x['file'])
            result.add((x['file'], _section(texts[x['file']], x['start'], names)))
            result.add((x['file'], _section(texts[x['file']], x['end']-1, names)))
            for match in re.finditer(r'^#{1,6}\s+', texts[x['file']][x['start']:x['end']], re.M):
                result.add((x['file'], _section(texts[x['file']], x['start']+match.start(), names)))
        return result
    a, b = scopes(source, old), scopes(candidate, new, aliases)
    _require(len(a) == len(b) == 1 and a == b, 'Claim may not cross files/sections or move scope')


def _heading_slots(text):
    """Complete ATX lines and their immediately adjacent bold bilingual subtitle."""
    headings, slots = [], {}
    for index, match in enumerate(re.finditer(r'^#{1,6}[^\r\n]*', text, re.M), 1):
        level = len(match[0])-len(match[0].lstrip('#'))
        headings.append((match, level))
        slots[(match.start(), match.end())] = (index, 'heading', level)
        following = re.match(r'\r?\n(\*\*[^\r\n]+\*\*)[ \t]*(?=\r?$)', text[match.end():], re.M)
        if following:
            slots[(match.end()+following.start(1), match.end()+following.end(1))] = (index, 'subtitle', level)
    return headings, slots


def _heading_edits(review, old, new, managed, remember, identity):
    """Fail-closed additive schema: one-to-one title slots; body safeguards remain separate."""
    pairs, aliases, covered = [], {}, set()
    layouts = {}
    for key in managed:
        a, sa = _heading_slots(old[key])
        b, sb = _heading_slots(new[key])
        _require(len(a) == len(b) and [level for _, level in a] == [level for _, level in b],
                 key+': section heading count/levels changed')
        layouts[key] = (a, b, sa, sb)

    def title_pair(source, candidate, key, primary=False):
        a = _span(source, old, 'heading source')
        b = _span(candidate, new, 'heading candidate')
        _require(a['file'] == b['file'] == key, 'Heading pair must stay in the same corresponding file')
        left, right, sa, sb = layouts[key]
        x, y = sa.get((a['start'], a['end'])), sb.get((b['start'], b['end']))
        _require(x is not None and x == y and (not primary or x[1] == 'heading'),
                 'Heading edit must map complete same-ordinal/same-level title slots')
        slot = (key, x)
        _require(slot not in covered, 'Duplicate heading slot mapping')
        covered.add(slot)
        before, after = _tokens(a['text']), _tokens(b['text'])
        _require(_evidence_equal(before, after),
                 'Heading numeric/citation/unit/negative/CI evidence changed')
        _require(_named_scopes(a['text']) == _named_scopes(b['text']), 'Heading scientific owner labels changed')
        if x[1] == 'heading':
            # Only candidate title labels are normalized; position, hierarchy and prose remain intact.
            aliases.setdefault(key, {})[b['start']] = re.sub(r'^#{1,6}[ \t]*', '', a['text']).strip()
        pairs.append(dict(source=a, candidate=b))
        return x

    for item in _list(review.get('heading_edits', []), 'heading_edits'):
        _object(item, ('id', 'section_id', 'source', 'candidate', 'reviewed_by', 'rationale', 'translations'),
                'heading edit', ('bilingual_sync_only',))
        remember(item['id'])
        identity(item['reviewed_by'], 'scientific')
        _string(item['rationale'], 'heading rationale')
        key = _key(item['source']['file'])
        _require(key in managed and key.endswith('_EN.md'), 'Primary heading edit must name inventoried EN file')
        slot = title_pair(item['source'], item['candidate'], key, True)
        _require(item['section_id'] == key+'#heading-'+str(slot[0]), 'Heading stable section_id mismatch')
        sync_only = item.get('bilingual_sync_only', False)
        _require(type(sync_only) is bool, 'bilingual_sync_only must be boolean')
        if sync_only:
            _require(item['source']['text'] == item['candidate']['text'],
                     'bilingual_sync_only heading edit must keep EN title identical')
        else:
            _require(item['source']['text'] != item['candidate']['text'], 'Primary heading edit must change title wording')
        group = _group(key)
        required = {lang: group+suffix for lang, suffix in [('ZH', '_ZH.md'), ('EN_ZH', '_EN_ZH.md')] if group+suffix in managed}
        seen = set()
        translation_changed = False
        for record in _list(item['translations'], 'heading translations', sync_only):
            _object(record, ('language', 'source', 'candidate', 'reviewed_by', 'rationale'), 'heading translation')
            lang = record['language']
            _require(type(lang) is str and lang in required and lang not in seen, 'Unexpected/duplicate heading translation')
            seen.add(lang)
            identity(record['reviewed_by'], 'bilingual')
            _string(record['rationale'], 'heading bilingual rationale')
            left, right = _list(record['source'], 'heading translation source', True), _list(record['candidate'], 'heading translation candidate', True)
            _require(len(left) == len(right), 'Heading translation mapping count changed')
            mapped = [title_pair(a, b, required[lang]) for a, b in zip(left, right)]
            translation_changed = translation_changed or any(a['text'] != b['text'] for a, b in zip(left, right))
            _require(any(x[1] == 'heading' for x in mapped), 'Heading translation requires corresponding heading slot')
            if lang == 'EN_ZH':
                _require(any(a['text'] == item['source']['text'] and b['text'] == item['candidate']['text'] for a, b in zip(left, right)),
                         'Combined heading must cover its English title')
                # Every adjacent bilingual subtitle of the mapped heading is reviewed, even if retained.
                sa, sb = layouts[required[lang]][2:]
                for x in mapped:
                    if x[1] == 'heading':
                        subtitles = {(required[lang], y) for y in sa.values() if y[0] == x[0] and y[1] == 'subtitle'}
                        _require(subtitles <= covered and {y for y in sa.values() if y[0] == x[0]} ==
                                 {y for y in sb.values() if y[0] == x[0]}, 'Combined bilingual subtitle coverage/structure missing')
        _require(seen == required.keys(), 'Heading edit missing bilingual/combined coverage')
        if sync_only:
            _require(translation_changed, 'bilingual_sync_only heading edit must change at least one translation title')
    for key, (left, right, sa, sb) in layouts.items():
        for index, ((a, _), (b, _)) in enumerate(zip(left, right), 1):
            _require(a[0] == b[0] or (key, (index, 'heading', left[index-1][1])) in covered,
                     key+': section headings changed/reordered without heading_edits')
    return pairs, aliases


def _covered(text, start, end, spans, key):
    ranges = sorted((max(start, x['start']), min(end, x['end'])) for x in spans if x['file'] == key)
    cursor = start
    for a, b in ranges:
        if b <= cursor:
            continue
        if a > cursor and text[cursor:a].strip():
            return False
        cursor = max(cursor, b)
    return not text[cursor:end].strip()


def _blocks(text):
    return [(m.start(), m.end(), m[0]) for m in re.finditer(r'\S[^\r\n]*(?:\r?\n(?![ \t]*\r?\n)[^\r\n]+)*', text)]


def _changed_blocks(old, new):
    a, b = _blocks(old), _blocks(new)
    matcher = difflib.SequenceMatcher(a=[x[2] for x in a], b=[x[2] for x in b], autojunk=False)
    return [(a[i:ie], b[j:je]) for op, i, ie, j, je in matcher.get_opcodes() if op != 'equal']


def _word_count(text):
    """Match check_finalize.word_count without importing its Word dependencies."""
    text = re.sub(r'^#{1,6}[^\n]*', '', text, flags=re.M)
    text = re.sub(r'\([^()]*\b(?:PMID|DOI|URL|arXiv):[^()]*\)', '', text, flags=re.I)
    text = re.sub(r'\((?:Supplementary\s+)?(?:Fig\.?|Figure|Table)[^()]*\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\n]+?\)', r'\1', text).replace('**', '').replace('`', '').strip()
    text = re.sub(r'(?<!\w)(?:\([a-h](?:[–-][a-h])?\)|（[a-h](?:[–-][a-h])?）)(?!\w)[,，;；:：.。]?', ' ', text)
    return len(text.split())


def _limits(review, before, new):
    budgets = []
    def validate(limits):
        for count in limits.values():
            _require(type(count) is int and count > 0, 'Author limits must be positive integers')
        _require(limits.get('min_words', 0) <= limits.get('max_words', float('inf')), 'Inverted author limits')
    def body(key):
        text = new[key]
        if Path(key).name.casefold() == 'abstract_en.md':
            text = re.split(r'^#{1,6}\s*(?:Keywords|Highlights)\s*#*\s*$', text, maxsplit=1, flags=re.M | re.I)[0]
        return text
    if 'author_limits' in review:
        _require(type(review['author_limits']) is dict, 'author_limits: expected object')
        for key, value in review['author_limits'].items():
            _key(key)
            _require(key in new and key.endswith('_EN.md'), 'Author limit must name inventoried EN file')
            _object(value, (), 'author limit', ('min_words', 'max_words'))
            _require(value, 'Empty author limit')
            validate(value)
            budgets.append((key, body(key), value))
    project_limits = Path(before).parent/'writing-limits.json'
    if Path(before).name == '04_manuscript' and project_limits.exists():
        raw = _json(project_limits)
        _require(type(raw) is dict, 'writing-limits.json: expected object')
        for section, value in raw.items():
            _require(type(section) is str and section in {'abstract', 'methods', 'results', 'introduction', 'discussion', 'legends'},
                     'Invalid author section key')
            _object(value, (), 'writing limit', ('min', 'max'))
            _require(value, 'Empty writing limit')
            limits = {x+'_words': y for x, y in value.items()}
            validate(limits)
            if section == 'legends':
                for key in new:
                    if not key.casefold().endswith('_legends_en.md'):
                        continue
                    text = new[key]
                    hits = list(re.finditer(r'^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:Supplementary\s+)?Figure\s+(S?\d+)\.', text, re.M | re.I))
                    _require(hits, 'Author legend limits: no figure captions found in '+key)
                    _require(len({h[1].upper() for h in hits}) == len(hits), 'Duplicate figure caption')
                    for index, hit in enumerate(hits):
                        caption = text[hit.start():hits[index+1].start() if index+1 < len(hits) else len(text)]
                        budgets.append((key+' Figure '+hit[1], caption, limits))
            else:
                for key in new:
                    if Path(key).name.casefold() == section+'_en.md':
                        budgets.append((key, body(key), limits))
    for key, text, limits in budgets:
        count = _word_count(text)
        _require(limits.get('min_words', 0) <= count <= limits.get('max_words', float('inf')),
                 'Author word limit violated: '+key+' ('+str(count)+')')


def _canonical_translated_anchor(text):
    value = re.sub(r'\s+', ' ', text.strip()).casefold().replace('μ', 'µ')
    value = re.sub(r'(?:补充|附)图\s*', 'supplementary fig ', value)
    value = re.sub(r'\bsupplementary\s+fig(?:ure)?s?\.?\s*', 'supplementary fig ', value)
    value = re.sub(r'图\s*', 'fig ', value)
    value = re.sub(r'\bfig(?:ure)?s?\.?\s*', 'fig ', value)
    value = re.sub(r'(?:补充|附)表\s*', 'supplementary table ', value)
    value = re.sub(r'\bsupplementary\s+tables?\s*', 'supplementary table ', value)
    value = re.sub(r'表\s*', 'table ', value)
    value = re.sub(r'\btables?\s*', 'table ', value)
    value = re.sub(r'(?:种子|seed)[-\s]*(\d+)', r'seed \1', value)
    value = re.sub(r'(?:运行|run)[-\s]*(\d+)', r'run \1', value)
    value = re.sub(r'\s*像素', ' px', value)
    value = re.sub(r'\bsupplementary\s+(?=fig\b|table\b)', '', value)
    return re.sub(r'\s+', ' ', value).strip()


def _compare(before, after, review_path, changes):
    a, b = _tree(before), _tree(after)
    _require(a.keys() == b.keys(), 'Manuscript file inventory changed')
    english = {k for k in a if k.endswith('_EN.md')}
    _require(english, 'No *_EN.md files found')
    managed = {k for k in a if _group(k) in {_group(x) for x in english}}
    review = _json(review_path)
    _object(review, ('schema_version', 'reviewers', 'inventory', 'claims', 'unknowns', 'narrative'),
            'review', ('author_limits', 'heading_edits', 'append_only_author_files', 'scope_declarations', 'review_status'))
    append_only = set()
    if 'append_only_author_files' in review:
        entries = _list(review['append_only_author_files'], 'append_only_author_files', True)
        for item in entries:
            key = _key(item)
            _require(key not in append_only, 'Duplicate append_only_author_files entry: '+key)
            _require(key in a and key not in managed and
                     (Path(key).name == '作者决定.md' or Path(key).name.endswith('_作者决定.md')),
                     'Only existing author decision files may be append-only: '+key)
            _require(b[key].startswith(a[key]) and len(b[key]) > len(a[key]) and
                     b[key][len(a[key]):].decode('utf-8').strip(),
                     'Author decision file must be strictly append-only and non-empty: '+key)
            append_only.add(key)
    _require(all(a[k] == b[k] for k in a.keys()-managed-append_only), 'Unrelated author files changed')
    old = {k: a[k].decode('utf-8') for k in managed}
    new = {k: b[k].decode('utf-8') for k in managed}
    for key in managed:
        left_nl, right_nl = set(re.findall(r'\r?\n', old[key])), set(re.findall(r'\r?\n', new[key]))
        _require(not left_nl or not right_nl or left_nl == right_nl,
                 key+': line endings changed (LF/CRLF); preserve original newline bytes and regenerate exact review spans')
    _require(type(review['schema_version']) is int and review['schema_version'] == 1, 'Unsupported review schema_version')
    reviewers = _object(review['reviewers'], ('editor', 'scientific', 'bilingual'), 'reviewers')
    for name in reviewers.values():
        _string(name, 'reviewer identity')
    inventory = review['inventory']
    _require(type(inventory) is dict and inventory.keys() == managed, 'Review inventory must cover managed files exactly')
    for key, record in inventory.items():
        _key(key)
        _object(record, ('source_sha256', 'candidate_sha256'), 'inventory entry')
        for field, data in [('source_sha256', a[key]), ('candidate_sha256', b[key])]:
            _require(type(record[field]) is str and HASH.fullmatch(record[field]) and record[field] == _sha(data),
                     key+': stale or malformed '+field)
    source_coverage, candidate_coverage = [], []
    warnings, identifiers = [BOUNDARY], set()
    def identity(value, role):
        _require(value == reviewers[role], 'reviewed_by must match recorded '+role+' reviewer identity')
    def remember(value):
        _string(value, 'record id')
        _require(value not in identifiers, 'Duplicate record id: '+value)
        identifiers.add(value)
    headings, aliases = _heading_edits(review, old, new, managed, remember, identity)
    _review_status(review, old, new, identity)
    inherited = _scope_declarations(review, old, new, managed, remember, identity)
    source_coverage.extend(x['source'] for x in headings)
    candidate_coverage.extend(x['candidate'] for x in headings)
    def evidence(spans, side, removed=()):
        return _tokens(_body_content(_without_removed(spans, removed) if side == 'source' else spans, headings, side))
    for claim in _list(review['claims'], 'claims'):
        _object(claim, ('id', 'reviewed_by', 'source', 'candidate', 'scope', 'facts', 'provenance', 'translations'), 'claim')
        remember(claim['id'])
        removed = inherited.get((claim['id'], 'EN'), ())
        identity(claim['reviewed_by'], 'scientific')
        source, candidate = _spans(claim['source'], old, 'claim source'), _spans(claim['candidate'], new, 'claim candidate')
        _require(all(x['file'].endswith('_EN.md') for x in source+candidate), 'Primary claims must map English source')
        _scope(source, candidate, old, new, aliases)
        scope_pairs = _pairs(claim['scope'], old, new, source, candidate, 'scope', scoped=True)
        _ownership(source, candidate, scope_pairs)
        provenance = _pairs(claim['provenance'], old, new, source, candidate, 'provenance')
        src_ev, dst_ev = evidence(source, 'source', removed), evidence(candidate, 'candidate')
        src_ev = _ignore_contradicted_noninferential(src_ev, dst_ev, _content(source), _content(candidate))
        _require(_evidence_equal(src_ev, dst_ev),
                 'Claim numeric/citation/unit/negative/CI evidence changed: '+claim['id'])
        fact_kinds = {}
        facts = {}
        fact_source = [x['source'] for x in scope_pairs+provenance]
        fact_candidate = [x['candidate'] for x in scope_pairs+provenance]
        for fact in _list(claim['facts'], 'facts', True):
            _object(fact, ('id', 'kind', 'source', 'candidate', 'context'), 'fact')
            _string(fact['id'], 'fact id')
            _require(fact['id'] not in facts, 'Duplicate fact id')
            _require(fact['kind'] in ('result', 'measurement', 'ci', 'unit', 'qualifier', 'citation', 'scope', 'method'), 'Unknown fact kind')
            left, right = _spans(fact['source'], old, 'fact source'), _spans(fact['candidate'], new, 'fact candidate')
            _require(all(_inside(x, source) for x in left) and all(_inside(x, candidate) for x in right), 'Fact outside claim')
            if {x['text'].casefold() for x in left} != {x['text'].casefold() for x in right}:
                if fact['kind'] == 'qualifier':
                    tl, tr = _tokens(_content(left)), _tokens(_content(right))
                    _require((tl or tr == {(6, 'single-run')}) and tr and all(t[0] == 6 for t in tl | tr) and _evidence_equal(tl, tr),
                             'Qualifier fact anchor weakened or changed non-qualifier tokens')
                elif fact['kind'] == 'scope':
                    _require({_canonical_scope_anchor(x['text']).casefold() for x in left} ==
                             {_canonical_scope_anchor(x['text']).casefold() for x in right},
                             'Unique fact anchor changed')
                elif _tokens(_content(left)) == _tokens(_content(right)) == {(9, 'first')}:
                    pass  # Bounded first/1st equivalence; other numeric evidence stays literal.
                else:
                    _require(_tokens(_content(left)) == _tokens(_content(right)) and
                             {_canonical_translated_anchor(x['text']) for x in left} ==
                             {_canonical_translated_anchor(x['text']) for x in right},
                             'Unique fact anchor changed')
            _contexts(fact['context'], old, new, source, candidate, left, right, scope_pairs, headings, removed)
            facts[fact['id']] = (left, right)
            fact_kinds[fact['id']] = fact['kind']
            fact_source.extend(left)
            fact_candidate.extend(right)
        src_ev = _ignore_contradicted_noninferential(evidence(source, 'source', removed), evidence(candidate, 'candidate'), _content(source), _content(candidate))
        fact_src_ev = _ignore_contradicted_noninferential(evidence(fact_source, 'source', removed), evidence(fact_candidate, 'candidate'), _content(source), _content(candidate))
        _require(src_ev <= fact_src_ev and
                 evidence(candidate, 'candidate') <= evidence(fact_candidate, 'candidate'), 'Salient evidence missing from explicit fact map')
        key = source[0]['file']
        group = _group(key)
        required = {lang: group+suffix for lang, suffix in [('ZH', '_ZH.md'), ('EN_ZH', '_EN_ZH.md')] if group+suffix in managed}
        if 'ZH' not in required:
            warnings.append(key+': corresponding ZH source absent; bilingual synchronization cannot be verified')
        seen = set()
        for translation in _list(claim['translations'], 'translations'):
            _object(translation, ('language', 'source', 'candidate', 'facts', 'scope', 'reviewed_by', 'rationale'), 'translation')
            lang = translation['language']
            _require(type(lang) is str and lang in required and lang not in seen, 'Unexpected/duplicate translation language')
            seen.add(lang)
            translated_removed = inherited.get((claim['id'], lang), ())
            identity(translation['reviewed_by'], 'bilingual')
            _string(translation['rationale'], 'translation rationale')
            left = _spans(translation['source'], old, 'translation source')
            right = _spans(translation['candidate'], new, 'translation candidate')
            _require(all(x['file'] == required[lang] for x in left+right), 'Translation must cover corresponding existing manuscript')
            _scope(left, right, old, new, aliases)
            translated_scope = _pairs(translation['scope'], old, new, left, right, 'translation scope')
            tr_src, tr_dst = evidence(left, 'source', translated_removed), evidence(right, 'candidate')
            tr_src = _ignore_contradicted_noninferential(tr_src, tr_dst, _content(left), _content(right))
            _require(_evidence_equal(tr_src, tr_dst),
                     'Translation numeric/citation/unit/negative evidence changed')
            linked = set()
            linked_source = [x['source'] for x in translated_scope]
            linked_candidate = [x['candidate'] for x in translated_scope]
            for link in _list(translation['facts'], 'translation facts', True):
                _object(link, ('fact', 'source', 'candidate', 'context'), 'translation fact')
                _require(type(link['fact']) is str and link['fact'] in facts and link['fact'] not in linked, 'Invalid translated fact id')
                linked.add(link['fact'])
                ls, rs = _spans(link['source'], old, 'translated fact source'), _spans(link['candidate'], new, 'translated fact candidate')
                _require(all(_inside(x, left) for x in ls) and all(_inside(x, right) for x in rs), 'Translated fact outside claim')
                if {x['text'].casefold() for x in ls} != {x['text'].casefold() for x in rs}:
                    tl, tr = _tokens(_content(ls)), _tokens(_content(rs))
                    if fact_kinds.get(link['fact']) == 'qualifier':
                        _require(all(t[0] == 6 for t in tl | tr) and _evidence_equal(tl, tr),
                                 'Translated qualifier fact weakened or changed non-qualifier tokens')
                    else:
                        _require((_tokens(_content(ls)) == _tokens(_content(rs)) == {(9, 'first')}) or
                                 ({_canonical_translated_anchor(x['text']) for x in ls} ==
                                 {_canonical_translated_anchor(x['text']) for x in rs} and tl == tr),
                                 'Translated fact anchor changed')
                _contexts(link['context'], old, new, left, right, ls, rs, translated_scope, headings, translated_removed)
                # Numbers/citation identifiers/operators are language-independent anchors.
                invariant = {t for t in _tokens(_content(facts[link['fact']][0])) if t[0] in (0, 2, 5)}
                _require(invariant <= _tokens(_content(ls)) and invariant <= _tokens(_content(rs)), 'Translated numeric/citation fact mismatch')
                linked_source.extend(ls)
                linked_candidate.extend(rs)
            _require(linked == facts.keys(), 'Translation missing fact coverage')
            # Combined files also contain English text, so check its entire evidence set.
            tr_all = _ignore_contradicted_noninferential(evidence(left, 'source', translated_removed), evidence(right, 'candidate'), _content(left), _content(right))
            linked_all = _ignore_contradicted_noninferential(evidence(linked_source, 'source', translated_removed), evidence(linked_candidate, 'candidate'), _content(left), _content(right))
            _require(tr_all <= linked_all and
                     evidence(right, 'candidate') <= evidence(linked_candidate, 'candidate'), 'Translation salient evidence missing from fact map')
            source_coverage.extend(left)
            candidate_coverage.extend(right)
        _require(seen == required.keys(), 'Affected claim missing bilingual/combined coverage')
        source_coverage.extend(source)
        candidate_coverage.extend(candidate)
    for unknown in _list(review['unknowns'], 'unknowns'):
        _object(unknown, ('id', 'source', 'candidate', 'reason'), 'unknown')
        remember(unknown['id'])
        _string(unknown['reason'], 'unknown reason')
        left, right = _span(unknown['source'], old, 'unknown source'), _span(unknown['candidate'], new, 'unknown candidate')
        _require(left['text'] == right['text'], 'Unknown passage must retain exact original text')
        _scope([left], [right], old, new, aliases)
        source_coverage.append(left)
        candidate_coverage.append(right)
    narrative = _object(review['narrative'], ('reviewed_by', 'source', 'candidate', 'summary', 'issues'), 'narrative')
    identity(narrative['reviewed_by'], 'editor')
    _string(narrative['summary'], 'whole manuscript narrative summary')
    ns, nc = _spans(narrative['source'], old, 'narrative source'), _spans(narrative['candidate'], new, 'narrative candidate')
    for key in english:
        _require(_covered(old[key], 0, len(old[key]), ns, key) and _covered(new[key], 0, len(new[key]), nc, key),
                 'Narrative review must cover whole English manuscript: '+key)
    issue_source, issue_candidate, issue_ids = [], [], []
    for issue in _list(narrative['issues'], 'narrative issues'):
        _object(issue, ('id', 'kind', 'source', 'candidate', 'decision', 'central', 'reviewed_by', 'reason'), 'narrative issue')
        remember(issue['id'])
        issue_ids.append(issue['id'])
        identity(issue['reviewed_by'], 'editor')
        _string(issue['kind'], 'narrative issue kind')
        _string(issue['reason'], 'narrative issue disposition')
        _require(type(issue['central']) is bool and issue['decision'] in ('resolved', 'retained', 'blocked'), 'Invalid narrative disposition')
        left, right = _spans(issue['source'], old, 'issue source'), _spans(issue['candidate'], new, 'issue candidate')
        if issue['decision'] == 'blocked':
            _require(not issue['central'], 'Central unresolved narrative conflict blocks affected delivery')
            _require([x['text'] for x in left] == [x['text'] for x in right], 'Unresolved local issue must retain exact original')
            warnings.append(issue['id']+': local unresolved issue retained: '+issue['reason'])
        issue_source.extend(left)
        issue_candidate.extend(right)
    files = {}
    for key in sorted(managed):
        changed = a[key] != b[key]
        changeset = _changed_blocks(old[key], new[key])
        for left, right in changeset:
            for blocks, text, coverage in [(left, old[key], source_coverage), (right, new[key], candidate_coverage)]:
                for start, end, _ in blocks:
                    _require(_covered(text, start, end, coverage, key), key+': changed block lacks claim/unknown coverage')
            if key in english:
                for blocks, text, coverage in [(left, old[key], issue_source), (right, new[key], issue_candidate)]:
                    for start, end, _ in blocks:
                        _require(_covered(text, start, end, coverage, key), key+': changed block lacks narrative issue disposition')
        files[key] = dict(changed=changed, source_sha256=_sha(a[key]), candidate_sha256=_sha(b[key]), errors=[], warnings=[])
    for key in sorted(append_only):
        files[key] = dict(changed=True, source_sha256=_sha(a[key]), candidate_sha256=_sha(b[key]), errors=[], warnings=[])
    _limits(review, before, new)
    if changes is not None:
        _manifest(changes, review_path, issue_ids)
    return dict(errors=[], warnings=warnings, files=files, review_sha256=_sha(Path(review_path).read_bytes()),
                narrative_decisions=issue_ids, boundary=BOUNDARY)


def _manifest(path, review_path, issue_ids):
    manifest = _object(_json(path), ('schema_version', 'review_sha256', 'decisions'), 'transaction manifest')
    _require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1, 'Invalid transaction schema_version')
    _require(type(manifest['review_sha256']) is str and manifest['review_sha256'] == _sha(Path(review_path).read_bytes()),
             'Stale or malformed transaction review_sha256')
    ids = _list(manifest['decisions'], 'transaction decisions')
    _require(all(type(x) is str for x in ids) and len(set(ids)) == len(ids) and set(ids) == set(issue_ids),
             'Transaction decisions must cover narrative dispositions exactly')


def compare_paths(before, after, review, changes=None):
    """Fail closed for invalid inputs; return errors/warnings/files in every case."""
    try:
        return _compare(before, after, review, changes)
    except (ValueError, OSError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        return dict(errors=[str(exc)], warnings=[], files={}, boundary=BOUNDARY)


def apply_edit(before, after, review, changes, decisions, root, day):
    """Archive full changed language groups; replace atomically per file and roll back I/O failures.

    A process/power crash across multiple files is outside this in-process rollback guarantee.
    No project files are modified until every archive and staged replacement is verified.
    """
    result = dict(errors=[], warnings=[], files={}, boundary=BOUNDARY)
    temporary, originals = [], {}
    try:
        root, before, after = _no_links(root), _no_links(before), _no_links(after)
        _require(before == root/'04_manuscript', 'Apply requires before = PROJECT/04_manuscript')
        _require(type(day) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) and date.fromisoformat(day).isoformat() == day,
                 'Invalid archive date')
        _require(after != before and not after.is_relative_to(before) and not before.is_relative_to(after),
                 'Stage must be outside the manuscript tree without overlap')
        result = compare_paths(before, after, review, changes)
        if result['errors']:
            return result
        _require('review_status' in _json(review),
                 'Apply requires an explicit reviewed verbal fact inventory; legacy comparison alone is not promotion approval')
        _manifest(decisions, review, result['narrative_decisions'])
        changed = [key for key, value in result['files'].items() if value['changed']]
        groups = {_group(key) for key in changed if _group(key) is not None}
        archived = [key for key in result['files'] if (_group(key) in groups and _group(key) is not None) or key in changed]
        candidates = {key: (after/key).read_bytes() for key in changed}
        originals = {key: (before/key).read_bytes() for key in archived}
        for key in archived:
            _require(_sha(originals[key]) == result['files'][key]['source_sha256'], 'Source changed during transaction')
        for key in changed:
            _require(_sha(candidates[key]) == result['files'][key]['candidate_sha256'], 'Candidate changed during transaction')
        archive = _no_links(root/'_archive'/day/'04_manuscript')
        for key in archived:
            target = _no_links(archive/key)
            _require(not target.exists() or (target.is_file() and target.read_bytes() == originals[key]),
                     'Archive collision: '+key)
        for key in archived:
            target = archive/key
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                with target.open('xb') as stream:
                    stream.write(originals[key])
            _require(target.read_bytes() == originals[key], 'Archive verification failed: '+key)
        staged = {}
        for key in changed:
            descriptor, name = tempfile.mkstemp(prefix='.structural-', suffix='.tmp', dir=(before/key).parent)
            temporary.append(Path(name))
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(candidates[key])
                stream.flush()
                os.fsync(stream.fileno())
            _require(Path(name).read_bytes() == candidates[key], 'Staged replacement verification failed')
            staged[key] = name
        # Recheck the live source after archival, immediately before the first replacement.
        for key, data in originals.items():
            _require((before/key).read_bytes() == data, 'Source changed during archival')
        replaced = []
        try:
            for key in changed:
                os.replace(staged[key], before/key)
                replaced.append(key)
                _require((before/key).read_bytes() == candidates[key], 'Applied replacement verification failed')
        except (OSError, ValueError) as exc:
            rollback_errors = []
            for key in replaced:
                try:
                    (before/key).write_bytes(originals[key])
                    _require((before/key).read_bytes() == originals[key], 'Rollback verification failed: '+key)
                except (OSError, ValueError) as rollback:
                    rollback_errors.append(str(rollback))
            raise ValueError('Transaction failed; '+('rollback FAILED: '+ '; '.join(rollback_errors) if rollback_errors else 'originals restored')+': '+str(exc)) from exc
        result.update(applied=changed, archived=archived, archive=str(archive))
        return result
    except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
        result['errors'].append(str(exc))
        return result
    finally:
        for path in temporary:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                result['warnings'].append('Could not remove transaction temporary file: '+str(path))
