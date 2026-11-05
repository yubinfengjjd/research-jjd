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


BOUNDARY = ('Exact spans, token checks and recorded review do not prove arbitrary language '
            'equivalence, scientific truth, translation accuracy or author acceptance.')
HASH = re.compile(r'[0-9a-f]{64}')
NUMBER = r'(?<![A-Za-z0-9_.])[+−-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?'
UNIT = r'(?:µm/px|μm/px|mmHg|mmol/L|mol/L|mg/dL|g/L|kg|mg|µg|μg|ng|pg|mL|ml|µL|μL|dL|mm|cm|µm|μm|nm|px|pixels?|scans?|eyes|subjects?|patients?|cohorts?|clusters?|seeds?|runs?|epochs?|seconds?|ms|Hz|GB|MB|%)'
TOKENS = [re.compile(NUMBER), re.compile(NUMBER+r'\s*'+UNIT+r'(?!\w)'),
          re.compile(r'\b(?:PMID|DOI|arXiv|URL):\s*[^\s)\];,]+', re.I),
          re.compile(r'\b(?:Fig(?:ure)?s?\.?|Tables?)\s+S?\d+[a-z]?(?:[–-][a-z])?', re.I),
          re.compile(r'(?<!\w)'+UNIT+r'(?!\w)|%'),
          re.compile(r'<=|>=|≤|≥|<|>|≠|(?<![A-Za-z])=(?!=)'),
          re.compile(r'\b(?:not|no|never|without|failed|inconclusive|unresolved|unestablished|'
                     r'exploratory|descriptive|retrospective|paired|subset|single[- ]run|'
                     r'single[- ]seed|one[- ]sided|two[- ]sided|cluster[- ]bootstrap|'
                     r'not estimable|not executed|cross(?:ing|ed|es)? zero|confidence intervals?|CI)\b', re.I),
          re.compile(r'\$\$[\s\S]*?\$\$|(?<!\$)\$(?!\$)[^$\n]+\$|`[^`\n]+`|https?://[^\s)]+'),
          re.compile(r'(?:\d+(?:\.\d+)?%\s*)?\b(?:CI|confidence intervals?)\s*[:=]?\s*'
                     r'[\[(]?\s*'+NUMBER+r'\s*(?:,|\bto\b|[–—])\s*'+NUMBER+r'\s*[\])]?', re.I)]


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


def _section(text, offset):
    stack = []
    for match in re.finditer(r'^([ \t]*#{1,6})[ \t]+([^\r\n]+)', text, re.M):
        if match.start() > offset:
            break
        level = match[1].count('#')
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, match[2].strip()))
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
        _require(a['text'] == b['text'], label+': immutable anchor changed')
    return pairs


def _named_scopes(text):
    """Conservative explicit owner-label detection, not general semantic inference."""
    result = {}
    pattern = r'(?<![\w\-‐‑‒–—−])((?i:cohort|group|population|subset|endpoint|outcome|seed|run))\s+([A-Z][A-Za-z0-9_-]*|\d+)(?![A-Za-z0-9_])'
    for match in re.finditer(pattern, text):
        axis = {'group': 'population', 'outcome': 'endpoint', 'seed': 'run'}.get(match[1].casefold(), match[1].casefold())
        result.setdefault(axis, set()).add(match[0].casefold())
    for match in re.finditer(r'(队列|亚组|组|终点|种子|运行)\s*([A-Z][A-Za-z0-9_-]*|\d+)(?![A-Za-z0-9_])', text):
        axis = {'队列': 'cohort', '亚组': 'subset', '组': 'population', '终点': 'endpoint', '种子': 'run', '运行': 'run'}[match[1]]
        result.setdefault(axis, set()).add(match[0].casefold())
    return result


def _ownership(source, candidate, scope):
    declared = {x['axis']: x for x in scope}
    for spans, side in [(source, 'source'), (candidate, 'candidate')]:
        for axis, labels in _named_scopes(_content(spans)).items():
            _require(len(labels) == 1 and axis in declared and
                     labels <= _named_scopes(declared[axis][side]['text']).get(axis, set()),
                     'Ambiguous/unmapped scientific scope ownership; split or preserve affected unit: '+axis)


def _contexts(values, old, new, source, candidate, fact_source, fact_candidate, scopes):
    left, right, seen = [], [], set()
    for record in _list(values, 'fact context', True):
        _object(record, ('source', 'candidate', 'scope'), 'fact context')
        a, b = _span(record['source'], old, 'context source'), _span(record['candidate'], new, 'context candidate')
        _require(_inside(a, source) and _inside(b, candidate), 'Fact context outside claim')
        indices = _list(record['scope'], 'context scope indices', True)
        _require(all(type(i) is int and 0 <= i < len(scopes) for i in indices) and len(set(indices)) == len(indices),
                 'Invalid context scope references')
        for i in indices:
            _require(scopes[i]['source']['text'] in a['text'] and scopes[i]['candidate']['text'] in b['text'],
                     'Fact context does not retain owning scientific scope')
        owned_before, owned_after = _named_scopes(a['text']), _named_scopes(b['text'])
        _require(owned_before == owned_after and all(len(labels) == 1 for labels in owned_before.values()),
                 'Ambiguous/changed owner labels in fact context; preserve or split affected unit')
        _require(_tokens(a['text']) <= _tokens(b['text']), 'Fact context lost numeric/citation/qualifier evidence')
        seen.update(indices)
        left.append(a)
        right.append(b)
    _require(seen == set(range(len(scopes))), 'Fact context omits declared scientific scope axes')
    _require(all(_inside(x, left) for x in fact_source) and all(_inside(x, right) for x in fact_candidate),
             'Fact lacks local scope-bound context')


def _tokens(text):
    return {(i, re.sub(r'\s+', ' ', m[0]).casefold()) for i, pattern in enumerate(TOKENS) for m in pattern.finditer(text)}


def _content(spans):
    return '\n'.join(x['text'] for x in spans)


def _scope(source, candidate, old, new):
    def scopes(spans, texts):
        result = set()
        for x in spans:
            result.add((x['file'], _section(texts[x['file']], x['start'])))
            result.add((x['file'], _section(texts[x['file']], x['end']-1)))
            for match in re.finditer(r'^#{1,6}\s+', texts[x['file']][x['start']:x['end']], re.M):
                result.add((x['file'], _section(texts[x['file']], x['start']+match.start())))
        return result
    a, b = scopes(source, old), scopes(candidate, new)
    _require(len(a) == len(b) == 1 and a == b, 'Claim may not cross files/sections or move scope')


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


def _compare(before, after, review_path, changes):
    a, b = _tree(before), _tree(after)
    _require(a.keys() == b.keys(), 'Manuscript file inventory changed')
    english = {k for k in a if k.endswith('_EN.md')}
    _require(english, 'No *_EN.md files found')
    managed = {k for k in a if _group(k) in {_group(x) for x in english}}
    _require(all(a[k] == b[k] for k in a.keys()-managed), 'Unrelated author files changed')
    old = {k: a[k].decode('utf-8') for k in managed}
    new = {k: b[k].decode('utf-8') for k in managed}
    review = _json(review_path)
    _object(review, ('schema_version', 'reviewers', 'inventory', 'claims', 'unknowns', 'narrative'),
            'review', ('author_limits',))
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
    for key in managed:
        _require(re.findall(r'^#{1,6}[^\r\n]*', old[key], re.M) == re.findall(r'^#{1,6}[^\r\n]*', new[key], re.M),
                 key+': section headings changed/reordered')
    source_coverage, candidate_coverage = [], []
    warnings, identifiers = [BOUNDARY], set()
    def identity(value, role):
        _require(value == reviewers[role], 'reviewed_by must match recorded '+role+' reviewer identity')
    def remember(value):
        _string(value, 'record id')
        _require(value not in identifiers, 'Duplicate record id: '+value)
        identifiers.add(value)
    for claim in _list(review['claims'], 'claims'):
        _object(claim, ('id', 'reviewed_by', 'source', 'candidate', 'scope', 'facts', 'provenance', 'translations'), 'claim')
        remember(claim['id'])
        identity(claim['reviewed_by'], 'scientific')
        source, candidate = _spans(claim['source'], old, 'claim source'), _spans(claim['candidate'], new, 'claim candidate')
        _require(all(x['file'].endswith('_EN.md') for x in source+candidate), 'Primary claims must map English source')
        _scope(source, candidate, old, new)
        scope_pairs = _pairs(claim['scope'], old, new, source, candidate, 'scope', scoped=True)
        _ownership(source, candidate, scope_pairs)
        provenance = _pairs(claim['provenance'], old, new, source, candidate, 'provenance')
        _require(_tokens(_content(source)) == _tokens(_content(candidate)), 'Claim numeric/citation/unit/negative/CI evidence changed: '+claim['id'])
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
            _require({x['text'] for x in left} == {x['text'] for x in right}, 'Unique fact anchor changed')
            _contexts(fact['context'], old, new, source, candidate, left, right, scope_pairs)
            facts[fact['id']] = (left, right)
            fact_source.extend(left)
            fact_candidate.extend(right)
        _require(_tokens(_content(source)) <= _tokens(_content(fact_source)) and
                 _tokens(_content(candidate)) <= _tokens(_content(fact_candidate)), 'Salient evidence missing from explicit fact map')
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
            identity(translation['reviewed_by'], 'bilingual')
            _string(translation['rationale'], 'translation rationale')
            left = _spans(translation['source'], old, 'translation source')
            right = _spans(translation['candidate'], new, 'translation candidate')
            _require(all(x['file'] == required[lang] for x in left+right), 'Translation must cover corresponding existing manuscript')
            _scope(left, right, old, new)
            translated_scope = _pairs(translation['scope'], old, new, left, right, 'translation scope')
            _require(_tokens(_content(left)) == _tokens(_content(right)), 'Translation numeric/citation/unit/negative evidence changed')
            linked = set()
            linked_source = [x['source'] for x in translated_scope]
            linked_candidate = [x['candidate'] for x in translated_scope]
            for link in _list(translation['facts'], 'translation facts', True):
                _object(link, ('fact', 'source', 'candidate', 'context'), 'translation fact')
                _require(type(link['fact']) is str and link['fact'] in facts and link['fact'] not in linked, 'Invalid translated fact id')
                linked.add(link['fact'])
                ls, rs = _spans(link['source'], old, 'translated fact source'), _spans(link['candidate'], new, 'translated fact candidate')
                _require(all(_inside(x, left) for x in ls) and all(_inside(x, right) for x in rs), 'Translated fact outside claim')
                _require({x['text'] for x in ls} == {x['text'] for x in rs}, 'Translated fact anchor changed')
                _contexts(link['context'], old, new, left, right, ls, rs, translated_scope)
                # Numbers/citation identifiers/operators are language-independent anchors.
                invariant = {t for t in _tokens(_content(facts[link['fact']][0])) if t[0] in (0, 2, 5)}
                _require(invariant <= _tokens(_content(ls)) and invariant <= _tokens(_content(rs)), 'Translated numeric/citation fact mismatch')
                linked_source.extend(ls)
                linked_candidate.extend(rs)
            _require(linked == facts.keys(), 'Translation missing fact coverage')
            # Combined files also contain English text, so check its entire evidence set.
            _require(_tokens(_content(left)) <= _tokens(_content(linked_source)) and
                     _tokens(_content(right)) <= _tokens(_content(linked_candidate)), 'Translation salient evidence missing from fact map')
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
        _scope([left], [right], old, new)
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
        _manifest(decisions, review, result['narrative_decisions'])
        changed = [key for key, value in result['files'].items() if value['changed']]
        groups = {_group(key) for key in changed}
        archived = [key for key in result['files'] if _group(key) in groups]
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
