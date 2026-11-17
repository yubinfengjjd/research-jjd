"""Build a fail-closed structural review bundle for check_finalize.py --edit-mode structural.

Maps changed headings and paragraph/sentence hunks between baseline and staged
04_manuscript trees (including EN, ZH, and EN_ZH pairs), computes exact UTF-8
decoded character offsets and SHA256 hashes, extracts explicit evidence facts
and translation anchors using evidence_edit primitives, and verifies via
evidence_edit.compare_paths when --verify is given. Never fabricates or weakens
failed evidence checks: mismatched numbers, units, citations, qualifiers, or
ambiguous multi-owner sentences fail loudly with actionable diagnostics.
"""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import re
import sys

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import evidence_edit as edit

_CJK_RE = re.compile(r'[\u4e00-\u9fff]')
_ABBREV_RE = re.compile(
    r'\b(?:Fig|Figs|Eq|Eqs|Table|Tables|Dr|Mr|Ms|Prof|vs|al|No|e\.g|i\.e)\.$', re.I
)
_EN_TERM_RE = re.compile(r'[A-Za-z]')


def _is_zh_dominant(text: str) -> bool:
    cjk = len(_CJK_RE.findall(text))
    if cjk == 0:
        return False
    # Any block/sentence with Chinese sentence punctuation or meaningful CJK chars is Chinese.
    if re.search(r'[。！？，、；：]', text) or cjk >= 2:
        return True
    lat = len(_EN_TERM_RE.findall(text))
    return cjk >= lat * 0.25


def _span(texts: dict[str, str], key: str, start: int, end: int) -> dict:
    return {'file': key, 'start': start, 'end': end, 'text': texts[key][start:end]}


def resolve_exact_span(texts: dict[str, str], selector: dict) -> dict:
    """Official selector helper: unique exact text, or an explicit zero-based occurrence.

    Existing exact offset spans are accepted and validated without re-anchoring.
    The generated review always stores exact offsets; selectors are input only.
    """
    if set(selector) == {'file', 'start', 'end', 'text'}:
        return edit._span(selector, texts, 'supplied exact span')
    edit._object(selector, ('file', 'text'), 'exact selector', ('occurrence',))
    key, needle = selector['file'], edit._string(selector['text'], 'selector text')
    edit._require(key in texts, 'Selector outside manuscript inventory')
    hits = [m.start() for m in re.finditer(re.escape(needle), texts[key])]
    occurrence = selector.get('occurrence')
    if occurrence is None:
        edit._require(len(hits) == 1, 'Selector must match uniquely; supply explicit occurrence: '+key+' '+needle[:50])
        occurrence = 0
    edit._require(type(occurrence) is int and 0 <= occurrence < len(hits), 'Invalid selector occurrence')
    return _span(texts, key, hits[occurrence], hits[occurrence] + len(needle))


def _materialize_declarations(rationales, old, new):
    declarations = json.loads(json.dumps(rationales.get('scope_declarations', [])))
    for request in rationales.get('scope_declaration_requests', []):
        edit._object(request, ('id', 'reviewed_by', 'rationale', 'declaration', 'bindings'), 'scope declaration request')
        declaration = {k: request[k] for k in ('id', 'reviewed_by', 'rationale')}
        declaration.update(source=resolve_exact_span(old, request['declaration']), candidate=resolve_exact_span(new, request['declaration']), bindings=[])
        for binding in request['bindings']:
            edit._object(binding, ('language', 'source', 'candidate', 'removed', 'guards'), 'scope binding request', ('claim',))
            record = dict(binding, claim=binding.get('claim', 'AUTO'))
            for side, texts in [('source', old), ('candidate', new), ('removed', old)]:
                record[side] = [resolve_exact_span(texts, x) for x in binding[side]]
            declaration['bindings'].append(record)
        declarations.append(declaration)
    return declarations


def _bind_inheritance(declarations, cid, source, candidate, translations):
    inherited = {}
    for language, left, right in [('EN', source, candidate)] + [(lang, ls, rs) for lang, ls, rs, _ in translations]:
        for declaration in declarations:
            for binding in declaration['bindings']:
                if binding['language'] == language and binding['source'] == left and binding['candidate'] == right:
                    edit._require(binding['claim'] in ('AUTO', cid), 'Scope declaration claim id disagrees with exact governed spans')
                    binding['claim'] = cid
                    edit._require((cid, language) not in inherited, 'Duplicate inherited scope binding')
                    removed = binding['removed']
                    edit._require(all(edit._inside(x, left) and edit._tokens(x['text']) == {(6, 'single-seed')} for x in removed),
                                  'Only exact source single-seed qualifier slots may inherit')
                    inherited[(cid, language)] = removed
    return inherited


def _trim_span(texts: dict[str, str], key: str, start: int, end: int) -> tuple[int, int]:
    s = texts[key]
    while start < end and s[start].isspace():
        start += 1
    while end > start and s[end - 1].isspace():
        end -= 1
    return start, end


def _longest_shared_slice(a_text: str, b_text: str) -> tuple[int, int, int, int] | None:
    """Find a nonempty trimmed substring appearing verbatim in both texts."""
    m = difflib.SequenceMatcher(None, a_text, b_text, autojunk=False).find_longest_match(
        0, len(a_text), 0, len(b_text)
    )
    if m.size > 0:
        sa, ea = m.a, m.a + m.size
        sb, eb = m.b, m.b + m.size
        while sa < ea and a_text[sa].isspace():
            sa += 1
            sb += 1
        while ea > sa and a_text[ea - 1].isspace():
            ea -= 1
            eb -= 1
        if ea > sa:
            return sa, ea, sb, eb
    for ch in a_text:
        if not ch.isspace():
            pos_b = b_text.find(ch)
            if pos_b != -1:
                pos_a = a_text.find(ch)
                return pos_a, pos_a + 1, pos_b, pos_b + 1
    return None


def _tokenless_shared_slice(a_text: str, b_text: str) -> tuple[int, int, int, int] | None:
    """Find a nonempty shared substring whose edit._tokens set is empty."""
    sm = difflib.SequenceMatcher(None, a_text, b_text, autojunk=False)
    for blk in sorted(sm.get_matching_blocks(), key=lambda x: -x.size):
        if blk.size <= 0:
            continue
        sub = a_text[blk.a:blk.a + blk.size]
        if sub.strip() and not edit._tokens(sub):
            sa, ea, sb, eb = blk.a, blk.a + blk.size, blk.b, blk.b + blk.size
            while sa < ea and a_text[sa].isspace():
                sa += 1; sb += 1
            while ea > sa and a_text[ea - 1].isspace():
                ea -= 1; eb -= 1
            if ea > sa:
                return sa, ea, sb, eb
        # Carve out contiguous non-token spans inside the matching block
        occ = _token_occurrences(sub)
        masked = [(h[1], h[2]) for h in occ]
        cuts = [0] + [p for a, b in masked for p in (a, b)] + [len(sub)]
        best = None
        pos = 0
        # Build uncovered intervals from masked token intervals
        sorted_m = sorted(masked)
        cur = 0
        intervals = []
        for ms, me in sorted_m:
            if ms > cur:
                intervals.append((cur, ms))
            cur = max(cur, me)
        if cur < len(sub):
            intervals.append((cur, len(sub)))
        for ia, ib in sorted(intervals, key=lambda x: -(x[1] - x[0])):
            seg = sub[ia:ib]
            if seg.strip() and not edit._tokens(seg):
                sa, ea = blk.a + ia, blk.a + ib
                sb, eb = blk.b + ia, blk.b + ib
                while sa < ea and a_text[sa].isspace():
                    sa += 1; sb += 1
                while ea > sa and a_text[ea - 1].isspace():
                    ea -= 1; eb -= 1
                if ea > sa:
                    best = (sa, ea, sb, eb)
                    break
        if best:
            return best
    for m in re.finditer(r'[^\s\d%()\[\].]+', a_text):
        w = m[0]
        if not edit._tokens(w):
            pb = b_text.find(w)
            if pb != -1:
                return m.start(), m.end(), pb, pb + len(w)
    for ch in a_text:
        if not ch.isspace() and not ch.isdigit() and not edit._tokens(ch):
            pb = b_text.find(ch)
            if pb != -1:
                pa = a_text.find(ch)
                return pa, pa + 1, pb, pb + 1
    return None


def _sentence_spans(text: str, base_offset: int, is_zh: bool = False) -> list[tuple[int, int, str]]:
    """Split text into sentence offsets preserving decimals, Fig., and brackets."""
    if not text.strip():
        return []
    cuts, depth, start = [], 0, 0
    endings = '.!?。！？' if is_zh else '.!?'
    closers = '*_"\'”’)]）】'
    for i, ch in enumerate(text):
        if ch in '([（【':
            depth += 1
        elif ch in ')]）】':
            depth = max(0, depth - 1)
        if ch not in endings or depth:
            continue
        j = i + 1
        while j < len(text) and text[j] in closers:
            j += 1
        if ch in '.!?' and j < len(text) and not (text[j].isspace() or text[j] in '。！？'):
            continue
        if ch == '.' and _ABBREV_RE.search(text[:i + 1]):
            continue
        seg = text[start:j]
        if seg.strip():
            ls = len(seg) - len(seg.lstrip())
            rs = len(seg) - len(seg.rstrip())
            cuts.append((base_offset + start + ls, base_offset + j - rs, seg.strip()))
        start = j
    tail = text[start:]
    if tail.strip():
        ls = len(tail) - len(tail.lstrip())
        rs = len(tail) - len(tail.rstrip())
        cuts.append((base_offset + start + ls, base_offset + len(text) - rs, tail.strip()))
    return cuts or [(base_offset, base_offset + len(text), text)]


def _token_occurrences(text: str) -> list[tuple[int, int, int, str, set]]:
    """Return all non-redundant TOKENS hits in text as (kind_idx, start, end, raw_text, norm_tokens)."""
    masked = [(m.start(), m.end()) for idx in (2, 3, 9) for m in edit.TOKENS[idx].finditer(text)]
    meas_masked = [(m.start(), m.end()) for m in edit.TOKENS[1].finditer(text)]
    hits = []
    for idx, pattern in enumerate(edit.TOKENS):
        for match in pattern.finditer(text):
            st, en = match.start(), match.end()
            if idx in (0, 1) and any(a <= st and en <= b for a, b in masked):
                continue
            if idx in (0, 4) and any(a <= st and en <= b for a, b in meas_masked):
                continue
            raw = match[0]
            hits.append((idx, st, en, raw, edit._tokens(raw)))
    hits.sort(key=lambda x: (x[1], -x[2], x[0]))
    return hits


def _fact_kind(tok_idx: int, raw: str, surrounding: str) -> str:
    if tok_idx in (1, 4):
        return 'unit'
    if tok_idx == 2:
        return 'citation'
    if tok_idx == 6:
        if raw.lower() == 'ci' or 'confidence interval' in raw.lower():
            return 'ci'
        return 'qualifier'
    if 'ci' in surrounding.lower():
        return 'ci'
    return 'result' if tok_idx in (0, 3, 5) else 'measurement'


def _build_heading_edits(
    old: dict[str, str],
    new: dict[str, str],
    managed: set[str],
    rationales: dict,
    reviewers: dict,
) -> tuple[list[dict], dict[str, dict[int, str]], dict[str, set[tuple[int, int]]]]:
    """Build heading_edits covering all changed EN/ZH/EN_ZH headings & bold subtitles."""
    layouts = {}
    for key in sorted(managed):
        a, sa = edit._heading_slots(old[key])
        b, sb = edit._heading_slots(new[key])
        if len(a) != len(b) or [lv for _, lv in a] != [lv for _, lv in b]:
            raise ValueError(f'{key}: section heading count/levels changed ({len(a)} -> {len(b)})')
        layouts[key] = (a, b, sa, sb)

    def slots_by_ordinal(slots_dict: dict) -> dict[int, list[tuple[int, int, tuple]]]:
        grouped: dict[int, list[tuple[int, int, tuple]]] = {}
        for (st, en), meta in sorted(slots_dict.items(), key=lambda kv: kv[0][0]):
            grouped.setdefault(meta[0], []).append((st, en, meta))
        return grouped

    edits, aliases, covered_slots = [], {}, {k: set() for k in managed}
    r_headings = rationales.get('headings', {})
    seq = 0
    for en_key in sorted(k for k in managed if k.endswith('_EN.md')):
        group = edit._group(en_key)
        zh_key = group + '_ZH.md' if group + '_ZH.md' in managed else None
        enzh_key = group + '_EN_ZH.md' if group + '_EN_ZH.md' in managed else None
        keys = [k for k in (en_key, zh_key, enzh_key) if k]
        by_key = {
            k: (slots_by_ordinal(layouts[k][2]), slots_by_ordinal(layouts[k][3]))
            for k in keys
        }
        for idx in sorted(by_key[en_key][0]):
            changed_any = False
            for k in keys:
                so_list = by_key[k][0].get(idx, [])
                sn_list = by_key[k][1].get(idx, [])
                if [meta for _, _, meta in so_list] != [meta for _, _, meta in sn_list]:
                    raise ValueError(f'{k}: heading/subtitle slot structure changed at heading #{idx}')
                for (sa, ea, _), (sb, eb, _) in zip(so_list, sn_list):
                    if old[k][sa:ea] != new[k][sb:eb]:
                        changed_any = True
            if not changed_any:
                continue
            seq += 1
            section_id = f'{en_key}#heading-{idx}'
            eo_st, eo_en, _ = by_key[en_key][0][idx][0]
            en_st, en_en, _ = by_key[en_key][1][idx][0]
            en_changed = old[en_key][eo_st:eo_en] != new[en_key][en_st:en_en]
            h_meta = r_headings.get(section_id, {})
            h_rat = h_meta.get('rationale') if isinstance(h_meta, dict) else None
            if not h_rat:
                h_rat = (
                    f'Revised section heading for {section_id}.'
                    if en_changed
                    else f'Synchronized bilingual section heading/subtitle for {section_id}.'
                )
            covered_slots[en_key].add((eo_st, eo_en))
            aliases.setdefault(en_key, {})[en_st] = re.sub(
                r'^#{1,6}[ \t]*', '', old[en_key][eo_st:eo_en]
            ).strip()
            translations = []
            for lang, tkey in (('ZH', zh_key), ('EN_ZH', enzh_key)):
                if not tkey:
                    continue
                so_list = by_key[tkey][0].get(idx, [])
                sn_list = by_key[tkey][1].get(idx, [])
                src_spans = [_span(old, tkey, s, e) for s, e, _ in so_list]
                dst_spans = [_span(new, tkey, s, e) for s, e, _ in sn_list]
                for (s, e, meta), (sb, eb, _) in zip(so_list, sn_list):
                    covered_slots[tkey].add((s, e))
                    if meta[1] == 'heading':
                        aliases.setdefault(tkey, {})[sb] = re.sub(
                            r'^#{1,6}[ \t]*', '', old[tkey][s:e]
                        ).strip()
                t_rat = (
                    h_meta.get('translations', {}).get(lang)
                    if isinstance(h_meta, dict)
                    else None
                ) or f'Synchronized {lang} heading/subtitle for {section_id}.'
                translations.append({
                    'language': lang,
                    'source': src_spans,
                    'candidate': dst_spans,
                    'reviewed_by': reviewers['bilingual'],
                    'rationale': t_rat,
                })
            rec = {
                'id': f'H{seq}',
                'section_id': section_id,
                'source': _span(old, en_key, eo_st, eo_en),
                'candidate': _span(new, en_key, en_st, en_en),
                'reviewed_by': reviewers['scientific'],
                'rationale': h_rat,
                'translations': translations,
            }
            if not en_changed:
                rec['bilingual_sync_only'] = True
            edits.append(rec)
    return edits, aliases, covered_slots


_CAPTION_LINE_RE = re.compile(
    r'^(?:\*\*)?(?:Supplementary\s+)?(?:Figure|Table|[附补充]*[图表])\s+S?\d+\.',
    re.M,
)


def _section_blocks(
    text: str, covered_heading_slots: set[tuple[int, int]]
) -> dict[int, list[tuple[int, int, str]]]:
    """Group non-heading blocks by section ordinal and split single-newline caption lines."""
    heading_starts = [m.start() for m in re.finditer(r'^#{1,6}[^\r\n]*', text, re.M)]
    _, all_slots = edit._heading_slots(text)

    def sec_ordinal(pos: int) -> int:
        ord_num = 0
        for h_pos in heading_starts:
            if h_pos <= pos:
                ord_num += 1
            else:
                break
        return ord_num

    # Trim ALL heading & adjacent bold-subtitle slots from block prefixes.
    by_sec: dict[int, list[tuple[int, int, str]]] = {}
    for b_start, b_end, _ in edit._blocks(text):
        cur_start = b_start
        slot_hit = True
        while slot_hit and cur_start < b_end:
            slot_hit = False
            for s_start, s_end in sorted(all_slots):
                if s_start == cur_start and s_end <= b_end:
                    nxt = s_end
                    while nxt < b_end and text[nxt] in ' \t\r\n':
                        nxt += 1
                    cur_start = nxt
                    slot_hit = True
                    break
        if cur_start >= b_end or not text[cur_start:b_end].strip():
            continue
        ce = b_end
        while ce > cur_start and text[ce - 1] in ' \t\r\n':
            ce -= 1
        if ce <= cur_start:
            continue
        body_slice = text[cur_start:ce]
        cap_hits = list(_CAPTION_LINE_RE.finditer(body_slice))
        if len(cap_hits) >= 2 and cap_hits[0].start() == 0:
            for idx_c, ch in enumerate(cap_hits):
                sub_s = cur_start + ch.start()
                sub_e = cur_start + (cap_hits[idx_c + 1].start() if idx_c + 1 < len(cap_hits) else len(body_slice))
                while sub_e > sub_s and text[sub_e - 1] in ' \t\r\n':
                    sub_e -= 1
                if sub_e > sub_s:
                    by_sec.setdefault(sec_ordinal(sub_s), []).append(
                        (sub_s, sub_e, text[sub_s:sub_e])
                    )
        else:
            by_sec.setdefault(sec_ordinal(cur_start), []).append(
                (cur_start, ce, text[cur_start:ce])
            )
    return by_sec


def _overlaps_any(blk: tuple[int, int, str], ranges: set[tuple[int, int]]) -> bool:
    return any(blk[0] < r_end and r_start < blk[1] for r_start, r_end in ranges)


def _align_hunks(
    old_blocks: list[tuple[int, int, str]],
    new_blocks: list[tuple[int, int, str]],
    old_changed_ranges: set[tuple[int, int]],
    new_changed_ranges: set[tuple[int, int]],
) -> list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]], bool]]:
    """Align blocks within one section, merging pure inserts/deletes into non-empty hunks."""
    matcher = difflib.SequenceMatcher(
        a=[b[2] for b in old_blocks], b=[b[2] for b in new_blocks], autojunk=False
    )
    raw = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            for oi, nj in zip(range(i1, i2), range(j1, j2)):
                ob, nb = old_blocks[oi], new_blocks[nj]
                raw.append(([ob], [nb], False))
        elif (
            op == 'replace'
            and (i2 - i1) == (j2 - j1) > 1
            and all(
                edit._evidence_equal(_inv_tokens(old_blocks[oi][2]), _inv_tokens(new_blocks[nj][2]))
                for oi, nj in zip(range(i1, i2), range(j1, j2))
            )
        ):
            for oi, nj in zip(range(i1, i2), range(j1, j2)):
                raw.append(([old_blocks[oi]], [new_blocks[nj]], True))
        else:
            raw.append((list(old_blocks[i1:i2]), list(new_blocks[j1:j2]), True))
    # Merge any empty-side insert/delete with an adjacent hunk in the same section.
    merged: list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]], bool]] = []
    idx = 0
    while idx < len(raw):
        o_list, n_list, chg = raw[idx]
        if (not o_list or not n_list) and merged:
            po, pn, pc = merged[-1]
            merged[-1] = (po + o_list, pn + n_list, pc or chg)
            idx += 1
        elif (not o_list or not n_list) and idx + 1 < len(raw):
            no, nn, nc = raw[idx + 1]
            raw[idx + 1] = (o_list + no, n_list + nn, chg or nc)
            idx += 1
        else:
            if not o_list or not n_list:
                raise ValueError('Unable to pair empty section addition/deletion cleanly within section')
            merged.append((o_list, n_list, chg))
            idx += 1
    return merged


def _split_multi_owner_en_hunk(
    old_blocks: list[tuple[int, int, str]],
    new_blocks: list[tuple[int, int, str]],
) -> list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]]]]:
    """Split a hunk at sentence boundaries when a block has multiple owners on one axis."""
    old_joined = ' '.join(b[2] for b in old_blocks)
    new_joined = ' '.join(b[2] for b in new_blocks)
    need_split = any(
        len(v) > 1
        for scopes in (edit._named_scopes(old_joined), edit._named_scopes(new_joined))
        for v in scopes.values()
    )
    if not need_split:
        return [(old_blocks, new_blocks)]
    old_sents = [s for b in old_blocks for s in _sentence_spans(b[2], b[0], is_zh=False)]
    new_sents = [s for b in new_blocks for s in _sentence_spans(b[2], b[0], is_zh=False)]
    hunks = _align_hunks(old_sents, new_sents, set(), set())

    # Coalesce adjacent single-sentence pairs only when doing so keeps <=1 owner per axis.
    def ok_single_owner(ol, nl):
        os = edit._named_scopes('\n'.join(x[2] for x in ol))
        ns = edit._named_scopes('\n'.join(x[2] for x in nl))
        return all(len(v) <= 1 for v in os.values()) and all(len(v) <= 1 for v in ns.values())

    atomic_hunks = []
    for ol, nl, _ in hunks:
        if ok_single_owner(ol, nl):
            atomic_hunks.append((ol, nl))
        elif len(ol) == len(nl) and len(ol) > 1:
            for oi, ni in zip(ol, nl):
                atomic_hunks.append(([oi], [ni]))
        else:
            # Partition ol and nl greedily along matching single-owner boundaries
            cur_o, cur_n = [], []
            oi, ni = 0, 0
            while oi < len(ol) or ni < len(nl):
                if oi < len(ol) and not cur_o:
                    cur_o.append(ol[oi]); oi += 1
                if ni < len(nl) and not cur_n:
                    cur_n.append(nl[ni]); ni += 1
                want_o = edit._named_scopes('\n'.join(x[2] for x in cur_o))
                while ni < len(nl) and (
                    edit._named_scopes('\n'.join(x[2] for x in cur_n)) != want_o or not cur_n
                ):
                    cand_n = edit._named_scopes('\n'.join(x[2] for x in cur_n + [nl[ni]]))
                    if any(len(v) > 1 for v in cand_n.values()):
                        break
                    cur_n.append(nl[ni]); ni += 1
                atomic_hunks.append((cur_o, cur_n))
                cur_o, cur_n = [], []

    chunks: list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]]]] = []
    for ol, nl in atomic_hunks:
        ol_txt = '\n'.join(x[2] for x in ol)
        nl_txt = '\n'.join(x[2] for x in nl)
        unchanged_multi = [x[2] for x in ol] == [x[2] for x in nl] and not ok_single_owner(ol, nl)
        segment_safe_multi = not ok_single_owner(ol, nl) and edit._multi_owner_segments_preserved(ol_txt, nl_txt)
        if not ok_single_owner(ol, nl) and not unchanged_multi and not segment_safe_multi:
            raise ValueError(
                'Single edited sentence/unit mixes multiple owners on one axis: '
                + (ol[0][2][:100] if ol else nl[0][2][:100])
            )
        if chunks and not unchanged_multi and not segment_safe_multi:
            po, pn = chunks[-1]
            if ok_single_owner(po, pn) and ok_single_owner(po + ol, pn + nl):
                po_scopes = edit._named_scopes('\n'.join(x[2] for x in po))
                ol_scopes = edit._named_scopes('\n'.join(x[2] for x in ol))
                if not (po_scopes and ol_scopes and po_scopes != ol_scopes):
                    chunks[-1] = (po + ol, pn + nl)
                    continue
        chunks.append((ol, nl))
    return chunks


_LANG_MARKER_RE = re.compile(r'^\*\*(?:English|中文对照|Chinese|中文)\*\*$')


def _inv_tokens(text: str) -> set:
    return {t for t in edit._tokens(text) if t[0] in (0, 2, 3, 5)}


def _monotone_dp_partition(
    groups_inv: list[set], side_blocks: list[tuple[int, int, str]]
) -> list[list[tuple[int, int, str]]]:
    """Partition side_blocks into len(groups_inv) contiguous slices maximizing invariant-token overlap."""
    k = len(groups_inv)
    n = len(side_blocks)
    if k == 0:
        return []
    if n == 0:
        return [[] for _ in range(k)]
    if n <= k:
        # Degenerate case: assign 1-by-1 and empty tail
        return [[side_blocks[i]] if i < n else [] for i in range(k)]
    blk_inv = [_inv_tokens(b[2]) for b in side_blocks]
    neg_inf = -10**9
    dp = [[neg_inf] * (n + 1) for _ in range(k + 1)]
    back = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0
    for gi in range(1, k + 1):
        want = groups_inv[gi - 1]
        for end in range(gi, n - (k - gi) + 1):
            for prev in range(gi - 1, end):
                if dp[gi - 1][prev] == neg_inf:
                    continue
                have = set().union(*blk_inv[prev:end])
                miss = len(want - have)
                extra = len(have - want)
                score = dp[gi - 1][prev] - (miss * 10 + extra * 5)
                if score > dp[gi][end]:
                    dp[gi][end] = score
                    back[gi][end] = prev
    cuts = [n]
    cur = n
    for gi in range(k, 0, -1):
        cur = back[gi][cur]
        cuts.append(cur)
    cuts.reverse()
    return [side_blocks[cuts[i]:cuts[i + 1]] for i in range(k)]


def _pair_enzh_section(
    en_blocks: list[tuple[int, int, str]], enzh_blocks: list[tuple[int, int, str]]
) -> list[list[tuple[int, int, str]]]:
    """Map each EN block index inside a section to matching EN + ZH blocks in EN_ZH."""
    if not en_blocks:
        return []
    if len(enzh_blocks) == len(en_blocks):
        return [[enzh_blocks[i]] for i in range(len(en_blocks))]

    # Attach '**English**' / '**中文对照**' markers to their following content block
    units = []
    pending = []
    for blk in enzh_blocks:
        if _LANG_MARKER_RE.fullmatch(blk[2].strip()):
            pending.append(blk)
        else:
            units.append((pending + [blk], _is_zh_dominant(blk[2])))
            pending = []
    if pending and units:
        units[-1][0].extend(pending)

    ez_en = [u for u, is_z in units if not is_z]
    ez_zh = [u for u, is_z in units if is_z]
    en_inv = [_inv_tokens(b[2]) for b in en_blocks]

    if len(ez_en) == len(en_blocks):
        en_parts = ez_en
    else:
        flat_en = [(u, _inv_tokens(' '.join(x[2] for x in u))) for u in ez_en]
        # DP over units
        en_raw = _monotone_dp_partition(
            en_inv, [(u[0][0], u[-1][1], '\n\n'.join(x[2] for x in u)) for u in ez_en]
        )
        en_parts = []
        # Map back to original uncollapsed blocks in order
        cursor = 0
        for slice_blks in en_raw:
            take = len(slice_blks)
            en_parts.append([blk for u in ez_en[cursor:cursor + take] for blk in u])
            cursor += take

    if len(ez_zh) == len(en_blocks):
        zh_parts = ez_zh
    elif not ez_zh:
        zh_parts = [[] for _ in en_blocks]
    else:
        zh_raw = _monotone_dp_partition(
            en_inv, [(u[0][0], u[-1][1], '\n\n'.join(x[2] for x in u)) for u in ez_zh]
        )
        zh_parts = []
        cursor = 0
        for slice_blks in zh_raw:
            take = len(slice_blks)
            zh_parts.append([blk for u in ez_zh[cursor:cursor + take] for blk in u])
            cursor += take

    return [sorted(ep + zp, key=lambda x: x[0]) for ep, zp in zip(en_parts, zh_parts)]


def _map_zh_indices_for_hunks(
    en_hunks: list[tuple[list, list, list[int], list[int]]],
    zh_old: list[tuple[int, int, str]],
    zh_new: list[tuple[int, int, str]],
    n_en_old: int,
    n_en_new: int,
) -> list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]], bool]]:
    """Map each EN hunk to its corresponding ZH block slices in one section."""
    if not zh_old and not zh_new:
        return [([], [], False) for _ in en_hunks]

    def map_side(
        hunk_blocks_list: list[list[tuple[int, int, str]]],
        indices_per_hunk: list[list[int]],
        n_en: int,
        zh_side: list[tuple[int, int, str]],
    ):
        if len(zh_side) == n_en:
            return [[zh_side[idx] for idx in idxs] for idxs in indices_per_hunk]
        groups_inv = [_inv_tokens(' '.join(b[2] for b in blks)) for blks in hunk_blocks_list]
        return _monotone_dp_partition(groups_inv, zh_side)

    old_mapped = map_side([h[0] for h in en_hunks], [h[2] for h in en_hunks], n_en_old, zh_old)
    new_mapped = map_side([h[1] for h in en_hunks], [h[3] for h in en_hunks], n_en_new, zh_new)
    return [
        (ol, nl, [x[2] for x in ol] != [x[2] for x in nl])
        for ol, nl in zip(old_mapped, new_mapped)
    ]


def _contiguous_or_list(
    spans_list: list[tuple[int, int, str]], full_text: str, key: str
) -> list[dict]:
    """Collapse only whitespace-adjacent spans within the same section into contiguous spans."""
    if not spans_list:
        return []
    groups: list[list[tuple[int, int]]] = [[(spans_list[0][0], spans_list[0][1])]]
    for s, e, _ in spans_list[1:]:
        prev_s, prev_e = groups[-1][-1]
        gap = full_text[prev_e:s]
        if prev_e <= s and not gap.strip() and not re.search(r'^#{1,6}[ \t]+', full_text[prev_s:e], re.M):
            groups[-1][-1] = (prev_s, e)
        else:
            groups.append([(s, e)])
    return [{'file': key, 'start': s, 'end': e, 'text': full_text[s:e]} for grp in groups for s, e in grp]


def _split_translation_for_subclaims(
    subclaims: list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]]]],
    zh_old: list[tuple[int, int, str]],
    zh_new: list[tuple[int, int, str]],
    is_enzh: bool = False,
) -> list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]]]]:
    """Partition multi-owner translation blocks across EN subclaims."""
    if len(subclaims) == 1:
        return [(zh_old, zh_new)]

    def split_side(blocks: list[tuple[int, int, str]], target_k: int) -> list[list[tuple[int, int, str]]]:
        tagged_sents = []
        for s, e, txt in blocks:
            blk_is_zh = _is_zh_dominant(txt)
            parts = _sentence_spans(txt, s, is_zh=blk_is_zh)
            if is_enzh and not blk_is_zh:
                tagged_sents.extend((False, p) for p in parts)
            else:
                # If a ZH sentence still bundles two owners separated by '；', split at '；'
                refined = []
                for ps, pe, ptxt in parts:
                    sc = edit._named_scopes(ptxt)
                    if any(len(v) > 1 for v in sc.values()) and '；' in ptxt:
                        for m in re.finditer(r'[^；]+(?:；|$)', ptxt):
                            seg = m[0]
                            if seg.strip():
                                ls = len(seg) - len(seg.lstrip())
                                rs = len(seg) - len(seg.rstrip())
                                refined.append((ps + m.start() + ls, ps + m.end() - rs, seg.strip()))
                    else:
                        refined.append((ps, pe, ptxt))
                tagged_sents.extend((True, p) for p in refined)
        if len(tagged_sents) < target_k:
            raise ValueError(f'Translation cannot be split into {target_k} owner-isolated subclaims')
        if is_enzh:
            en_sents = [p for zh, p in tagged_sents if not zh]
            zh_sents = [p for zh, p in tagged_sents if zh]
            en_chunks = _partition_sents_by_owners(subclaims, en_sents, side=0)
            zh_chunks = _partition_sents_by_owners(subclaims, zh_sents, side=0)
            return [a + b for a, b in zip(en_chunks, zh_chunks)]
        return _partition_sents_by_owners(subclaims, [p for _, p in tagged_sents], side=0)

    old_parts = split_side(zh_old, len(subclaims))
    new_parts = split_side(zh_new, len(subclaims))
    return list(zip(old_parts, new_parts))


def _partition_sents_by_owners(
    subclaims: list[tuple[list[tuple[int, int, str]], list[tuple[int, int, str]]]],
    sents: list[tuple[int, int, str]],
    side: int,
) -> list[list[tuple[int, int, str]]]:
    """Assign consecutive sentences greedily to subclaims matching owner labels & tokens."""
    k = len(subclaims)
    target_owners = [
        edit._named_scopes('\n'.join(x[2] for x in sc[side])) for sc in subclaims
    ]
    chunks: list[list[tuple[int, int, str]]] = [[] for _ in range(k)]
    cursor = 0
    for idx in range(k):
        need_last = k - 1 - idx
        if idx == k - 1:
            chunks[idx] = sents[cursor:]
            break
        want = target_owners[idx]
        picked = []
        while cursor < len(sents) - need_last:
            cand = sents[cursor]
            cand_owners = edit._named_scopes(cand[2])
            if picked:
                combined_owners = edit._named_scopes('\n'.join(x[2] for x in picked + [cand]))
                if any(len(v) > 1 for v in combined_owners.values()):
                    break
                if want and cand_owners and cand_owners != want:
                    break
                if target_owners[idx + 1] and cand_owners == target_owners[idx + 1]:
                    break
            picked.append(cand)
            cursor += 1
            if want and edit._named_scopes('\n'.join(x[2] for x in picked)) == want:
                # Advance only until next sentence has a different owner or triggers multi-owner
                while cursor < len(sents) - need_last:
                    nxt = sents[cursor]
                    nxt_o = edit._named_scopes(nxt[2])
                    comb = edit._named_scopes('\n'.join(x[2] for x in picked + [nxt]))
                    if any(len(v) > 1 for v in comb.values()) or (nxt_o and nxt_o != want):
                        break
                    if not nxt_o and not want:
                        break
                    picked.append(nxt)
                    cursor += 1
                break
        if not picked and cursor < len(sents) - need_last:
            picked.append(sents[cursor])
            cursor += 1
        chunks[idx] = picked
    return chunks


def _find_anchor_spans(
    spans: list[dict], texts: dict[str, str], target_text: str, matcher_fn=None
) -> dict | None:
    for sp in spans:
        txt = sp['text']
        if matcher_fn is None:
            pos = txt.find(target_text)
            if pos != -1:
                return _span(texts, sp['file'], sp['start'] + pos, sp['start'] + pos + len(target_text))
        else:
            hit = matcher_fn(txt)
            if hit is not None:
                return _span(texts, sp['file'], sp['start'] + hit[0], sp['start'] + hit[1])
    return None


def _build_claim_record(
    cid: str,
    en_src_spans: list[dict],
    en_dst_spans: list[dict],
    trans_entries: list[tuple[str, list[dict], list[dict], str]],
    old: dict[str, str],
    new: dict[str, str],
    reviewers: dict,
    inherited: dict | None = None,
) -> dict:
    """Construct one validated claim with scope, provenance, atomic facts & translations."""
    src_join = '\n'.join(s['text'] for s in en_src_spans)
    dst_join = '\n'.join(s['text'] for s in en_dst_spans)
    inherited = inherited or {}
    removed = inherited.get((cid, 'EN'), ())
    b_tok = edit._tokens(edit._content(edit._without_removed(en_src_spans, removed)))
    a_tok = edit._tokens(dst_join)
    if not edit._evidence_equal(b_tok, a_tok):
        miss = sorted(b_tok - a_tok)
        add = sorted(a_tok - b_tok)
        raise ValueError(
            f'Evidence mismatch in {cid} ({en_src_spans[0]["file"]}): '
            f'missing={miss}, added={add} | src={src_join[:120]!r}'
        )

    def make_shared_pair(src_sps, dst_sps, avoid_empty=True):
        if len(src_sps) == 1 and len(dst_sps) == 1:
            sl = _longest_shared_slice(src_sps[0]['text'], dst_sps[0]['text'])
            if sl:
                sa, ea, sb, eb = sl
                return {
                    'source': _span(old, src_sps[0]['file'], src_sps[0]['start'] + sa, src_sps[0]['start'] + ea),
                    'candidate': _span(new, dst_sps[0]['file'], dst_sps[0]['start'] + sb, dst_sps[0]['start'] + eb),
                }
        for s_sp in src_sps:
            for d_sp in dst_sps:
                sl = _longest_shared_slice(s_sp['text'], d_sp['text'])
                if sl:
                    sa, ea, sb, eb = sl
                    return {
                        'source': _span(old, s_sp['file'], s_sp['start'] + sa, s_sp['start'] + ea),
                        'candidate': _span(new, d_sp['file'], d_sp['start'] + sb, d_sp['start'] + eb),
                    }
        if avoid_empty:
            raise ValueError(f'{cid}: no shared verbatim anchor between source and candidate spans')
        return None

    def make_tokenless_pair(src_sps, dst_sps):
        for s_sp in src_sps:
            for d_sp in dst_sps:
                sl = _tokenless_shared_slice(s_sp['text'], d_sp['text'])
                if sl:
                    sa, ea, sb, eb = sl
                    return {
                        'source': _span(old, s_sp['file'], s_sp['start'] + sa, s_sp['start'] + ea),
                        'candidate': _span(new, d_sp['file'], d_sp['start'] + sb, d_sp['start'] + eb),
                    }
        return make_shared_pair(src_sps, dst_sps)

    # 1. Scope anchors: include every named owner axis plus fallback 'analysis' if none
    scopes = []
    named_src = edit._named_scopes(src_join)
    named_dst = edit._named_scopes(dst_join)
    multi_owner = any(len(v) > 1 for v in named_src.values())
    if named_src != named_dst or (multi_owner and not edit._multi_owner_segments_preserved(src_join, dst_join)):
        raise ValueError(f'{cid}: ambiguous or changed scope owner labels: {named_src} vs {named_dst}')
    owner_pat = re.compile(
        r'(?<![\w\-‐‑‒–—−])((?i:analysis|cohort|group|population|subset|endpoint|outcome|seed|run))'
        r'(?:[ \t]+([A-Z][A-Za-z0-9_-]*|\d+)|[-‐‑‒–—−](\d+))(?![A-Za-z0-9_])'
        r'|(分析|队列|亚组|(?<![\u4e00-\u9fff])组|终点|种子|运行)[ \t]*([A-Z][A-Za-z0-9_-]*|\d+)(?![A-Za-z0-9_])'
    )

    def collect_owner_hits(spans, texts):
        hits = {}
        for sp in spans:
            for m in owner_pat.finditer(sp['text']):
                if m[1]:
                    ra = m[1].casefold()
                    ri = m[2] if m[2] is not None else m[3]
                    if ra in ('seed', 'run') and not re.fullmatch(r'[A-Z]\d*|\d+', ri):
                        continue
                    axis = {'group': 'population', 'outcome': 'endpoint', 'seed': 'run'}.get(ra, ra)
                else:
                    cn = m[4]
                    ri = m[5]
                    if cn in ('种子', '运行') and not re.fullmatch(r'[A-Z]\d*|\d+', ri):
                        continue
                    axis = {'分析': 'analysis', '队列': 'cohort', '亚组': 'subset', '组': 'population',
                            '终点': 'endpoint', '种子': 'run', '运行': 'run'}[cn]
                hits.setdefault(axis, _span(texts, sp['file'], sp['start'] + m.start(), sp['start'] + m.end()))
        return hits

    s_owners = collect_owner_hits(en_src_spans, old)
    d_owners = collect_owner_hits(en_dst_spans, new)
    for axis in sorted(named_src):
        if axis not in s_owners or axis not in d_owners:
            raise ValueError(f'{cid}: unable to locate anchor span for axis {axis}')
        scopes.append({'axis': axis, 'source': s_owners[axis], 'candidate': d_owners[axis]})
    shared_anchor = make_shared_pair(en_src_spans, en_dst_spans)
    if not scopes:
        scopes.append({'axis': 'analysis', **shared_anchor})

    # Provenance must be nonempty; prefer shared fig/table citation span if present
    prov_pair = None
    def source_occurrences(spans, removed):
        return [(sp, [h for h in _token_occurrences(sp['text']) if not any(
            slot['file'] == sp['file'] and slot['start'] <= sp['start'] + h[1] < sp['start'] + h[2] <= slot['end']
            for slot in removed)]) for sp in spans]
    src_toks = source_occurrences(en_src_spans, removed)
    dst_toks = [(sp, _token_occurrences(sp['text'])) for sp in en_dst_spans]
    for s_sp, shits in src_toks:
        for d_sp, dhits in dst_toks:
            for _, ss, se, sraw, _ in shits:
                for _, ds, de, draw, _ in dhits:
                    if sraw == draw:
                        prov_pair = {
                            'source': _span(old, s_sp['file'], s_sp['start'] + ss, s_sp['start'] + se),
                            'candidate': _span(new, d_sp['file'], d_sp['start'] + ds, d_sp['start'] + de),
                        }
                        break
                if prov_pair:
                    break
            if prov_pair:
                break
        if prov_pair:
            break
    provenance = [prov_pair or shared_anchor]

    # Pick enclosing context spans containing all scope anchors
    def find_ctx_for_spans(s_fact_spans, d_fact_spans, outer_src, outer_dst, sc_list):
        ctxs = []
        used_scopes = set()
        for sf, df in zip(s_fact_spans, d_fact_spans):
            s_box = next(x for x in outer_src if x['file'] == sf['file'] and x['start'] <= sf['start'] < sf['end'] <= x['end'])
            d_box = next(x for x in outer_dst if x['file'] == df['file'] and x['start'] <= df['start'] < df['end'] <= x['end'])
            matching_idx = [
                i for i, sc in enumerate(sc_list)
                if edit._canonical_scope_anchor(sc['source']['text']) in edit._canonical_scope_anchor(s_box['text'])
                and edit._canonical_scope_anchor(sc['candidate']['text']) in edit._canonical_scope_anchor(d_box['text'])
            ]
            if not matching_idx:
                raise ValueError(f'{cid}: cannot build context span retaining an owning scope anchor')
            used_scopes.update(matching_idx)
            rec = {'source': s_box, 'candidate': d_box, 'scope': matching_idx}
            if rec not in ctxs:
                ctxs.append(rec)
        return ctxs, used_scopes

    # 2. Extract atomic EN facts grouped by normalized surface token so duplicates don't exhaust
    flat_src = [(sp, h) for sp, hits in src_toks for h in hits]
    flat_dst = [(sp, h) for sp, hits in dst_toks for h in hits]

    facts_out = []
    used_src, used_dst = set(), set()
    for i_s, (s_sp, (idx_s, st_s, en_s, raw_s, toks_s)) in enumerate(flat_src):
        if i_s in used_src or idx_s == 6:
            continue
        key_s = (idx_s, raw_s.casefold())
        s_group = [
            i for i, (_, (idx, _, _, raw, _)) in enumerate(flat_src)
            if i not in used_src and (idx, raw.casefold()) == key_s
        ]
        d_group = [
            j for j, (_, (idx, _, _, raw, _)) in enumerate(flat_dst)
            if j not in used_dst and (idx, raw.casefold()) == key_s
        ]
        if not d_group and idx_s in (1, 4, 9):
            d_group = [
                j for j, (_, (idx, _, _, _, toks_d)) in enumerate(flat_dst)
                if j not in used_dst and idx == idx_s and toks_s == toks_d
            ]
        if d_group:
            used_src.update(s_group)
            used_dst.update(d_group)
            for j_d in d_group:
                if flat_dst[j_d][1][3].casefold() != raw_s.casefold() and idx_s != 9:
                    raise ValueError(
                        f'{cid}: non-qualifier token surface changed {raw_s!r} -> {flat_dst[j_d][1][3]!r}'
                    )
            sf_list = [_span(old, flat_src[i][0]['file'], flat_src[i][0]['start'] + flat_src[i][1][1],
                             flat_src[i][0]['start'] + flat_src[i][1][2]) for i in s_group]
            df_list = [_span(new, flat_dst[j][0]['file'], flat_dst[j][0]['start'] + flat_dst[j][1][1],
                             flat_dst[j][0]['start'] + flat_dst[j][1][2]) for j in d_group]
            kind = _fact_kind(idx_s, raw_s, s_sp['text'][max(0, st_s - 25):en_s + 25])
            if kind == 'scope' and not any(edit._inside(sf_list[0], [sc['source']]) for sc in scopes):
                kind = 'result'
            ctxs, _ = find_ctx_for_spans(sf_list, df_list, en_src_spans, en_dst_spans, scopes)
            facts_out.append({
                'id': f'{cid}_f{len(facts_out) + 1}',
                'kind': kind,
                'source': sf_list,
                'candidate': df_list,
                'context': ctxs,
            })

    # Exact qualifiers grouped by lowercased text
    for i_s, (s_sp, (idx_s, st_s, en_s, raw_s, _)) in enumerate(flat_src):
        if i_s in used_src or idx_s != 6:
            continue
        q_key = raw_s.casefold()
        s_group = [i for i, (_, (idx, _, _, raw, _)) in enumerate(flat_src) if i not in used_src and idx == 6 and raw.casefold() == q_key]
        d_group = [j for j, (_, (idx, _, _, raw, _)) in enumerate(flat_dst) if j not in used_dst and idx == 6 and raw.casefold() == q_key]
        if d_group:
            used_src.update(s_group)
            used_dst.update(d_group)
            sf_list = [_span(old, flat_src[i][0]['file'], flat_src[i][0]['start'] + flat_src[i][1][1],
                             flat_src[i][0]['start'] + flat_src[i][1][2]) for i in s_group]
            df_list = [_span(new, flat_dst[j][0]['file'], flat_dst[j][0]['start'] + flat_dst[j][1][1],
                             flat_dst[j][0]['start'] + flat_dst[j][1][2]) for j in d_group]
            ctxs, _ = find_ctx_for_spans(sf_list, df_list, en_src_spans, en_dst_spans, scopes)
            facts_out.append({
                'id': f'{cid}_f{len(facts_out) + 1}',
                'kind': 'qualifier',
                'source': sf_list,
                'candidate': df_list,
                'context': ctxs,
            })

    # Remaining qualifier changes must be explicitly paired; scope declarations
    # are not invented here and repeated fixed qualifiers are not auto-generated.
    rem_s = [flat_src[i] for i in range(len(flat_src)) if i not in used_src and flat_src[i][1][0] == 6]
    rem_d = [flat_dst[j] for j in range(len(flat_dst)) if j not in used_dst and flat_dst[j][1][0] == 6]
    if rem_s or rem_d:
        rs = [_span(new, sp['file'], sp['start'] + h[1], sp['start'] + h[2]) for sp, h in rem_d]
        rem_d_toks = {t for _, h in rem_d for t in h[4]}
        if rem_s and rem_d:
            ls = [_span(old, sp['file'], sp['start'] + h[1], sp['start'] + h[2]) for sp, h in rem_s]
        else:
            raise ValueError(f'{cid}: unmatched qualifier evidence src={rem_s} dst={rem_d}')
        ctxs, _ = find_ctx_for_spans([ls[0]], [rs[0]], en_src_spans, en_dst_spans, scopes)
        facts_out.append({
            'id': f'{cid}_f{len(facts_out) + 1}',
            'kind': 'qualifier',
            'source': ls,
            'candidate': rs,
            'context': ctxs,
        })

    if not facts_out:
        ctxs, _ = find_ctx_for_spans([shared_anchor['source']], [shared_anchor['candidate']], en_src_spans, en_dst_spans, scopes)
        facts_out.append({
            'id': f'{cid}_f1',
            'kind': 'method',
            'source': [shared_anchor['source']],
            'candidate': [shared_anchor['candidate']],
            'context': ctxs,
        })

    # 3. Map each translation language cleanly
    translations_out = []
    for lang, t_src_spans, t_dst_spans, t_rat in trans_entries:
        ts_join = '\n'.join(s['text'] for s in t_src_spans)
        td_join = '\n'.join(s['text'] for s in t_dst_spans)
        t_removed = inherited.get((cid, lang), ())
        tb_tok, ta_tok = edit._tokens(edit._content(edit._without_removed(t_src_spans, t_removed))), edit._tokens(td_join)
        if not edit._evidence_equal(tb_tok, ta_tok):
            raise ValueError(
                f'{cid} {lang} translation evidence mismatch: '
                f'missing={sorted(tb_tok - ta_tok)}, added={sorted(ta_tok - tb_tok)}'
            )
        # Build one shared scope anchor per paired span when possible so disjoint EN_ZH spans work
        t_scope = []
        if len(t_src_spans) == len(t_dst_spans) and len(t_src_spans) > 1:
            for s_sp, d_sp in zip(t_src_spans, t_dst_spans):
                sl = _longest_shared_slice(s_sp['text'], d_sp['text'])
                if sl:
                    sa, ea, sb, eb = sl
                    t_scope.append({
                        'source': _span(old, s_sp['file'], s_sp['start'] + sa, s_sp['start'] + ea),
                        'candidate': _span(new, d_sp['file'], d_sp['start'] + sb, d_sp['start'] + eb),
                    })
        if not t_scope:
            t_scope = [make_shared_pair(t_src_spans, t_dst_spans)]
        t_shared = t_scope[0]
        ts_occ = [(sp, h) for sp, hits in source_occurrences(t_src_spans, t_removed) for h in hits]
        td_occ = [(sp, h) for sp in t_dst_spans for h in _token_occurrences(sp['text'])]
        t_used_s, t_used_d = set(), set()

        def find_tr_match(fn_need_toks, fn_kind_ok):
            src_hits, dst_hits = [], []
            for is_idx, (sp, h) in enumerate(ts_occ):
                if is_idx in t_used_s or not fn_kind_ok(h[0]):
                    continue
                if h[4] & fn_need_toks:
                    cs = edit._canonical_translated_anchor(h[3])
                    jd = next(
                        (j for j, (_, hd) in enumerate(td_occ)
                         if j not in t_used_d and hd[0] == h[0]
                         and (h[3].casefold() == hd[3].casefold()
                              or ((cs == edit._canonical_translated_anchor(hd[3]) or h[0] == 9) and h[4] == hd[4]))),
                        None,
                    )
                    if jd is not None:
                        t_used_s.add(is_idx)
                        t_used_d.add(jd)
                        spd, hd = td_occ[jd]
                        src_hits.append(_span(old, sp['file'], sp['start'] + h[1], sp['start'] + h[2]))
                        dst_hits.append(_span(new, spd['file'], spd['start'] + hd[1], spd['start'] + hd[2]))
            return src_hits, dst_hits

        def tr_box_ctx(ls, rs):
            ctxs = []
            seen_idx = set()
            pairs = list(zip(ls, rs)) if len(ls) == len(rs) else [(ls[0], rs[0])]
            for sp_s, sp_d in pairs:
                s_box = next(x for x in t_src_spans if x['file'] == sp_s['file'] and x['start'] <= sp_s['start'] < sp_s['end'] <= x['end'])
                d_box = next(x for x in t_dst_spans if x['file'] == sp_d['file'] and x['start'] <= sp_d['start'] < sp_d['end'] <= x['end'])
                matching = [
                    i for i, sc in enumerate(t_scope)
                    if sc['source']['text'] in s_box['text'] and sc['candidate']['text'] in d_box['text']
                ]
                if not matching:
                    # Pair s_box with the candidate box carrying the same t_scope index
                    matching = [i for i, sc in enumerate(t_scope) if sc['source']['text'] in s_box['text']]
                    if matching:
                        d_box = next(
                            (x for x in t_dst_spans if t_scope[matching[0]]['candidate']['text'] in x['text']),
                            d_box,
                        )
                seen_idx.update(matching)
                rec = {'source': s_box, 'candidate': d_box, 'scope': matching}
                if rec not in ctxs:
                    ctxs.append(rec)
            if len(t_scope) > 1 and len(t_src_spans) == len(t_scope) == len(t_dst_spans):
                for i in range(len(t_scope)):
                    if i not in seen_idx:
                        s_box, d_box = t_src_spans[i], t_dst_spans[i]
                        if (
                            t_scope[i]['source']['text'] in s_box['text']
                            and t_scope[i]['candidate']['text'] in d_box['text']
                        ):
                            seen_idx.add(i)
                            rec = {'source': s_box, 'candidate': d_box, 'scope': [i]}
                            if rec not in ctxs:
                                ctxs.append(rec)
            return ctxs, seen_idx

        tr_facts = []
        used_t_scopes = set()
        for ef in facts_out:
            inv = {t for t in edit._tokens('\n'.join(x['text'] for x in ef['source'])) if t[0] in (0, 2, 5)}
            all_ef_toks = edit._tokens('\n'.join(x['text'] for x in ef['source']))
            ls, rs = find_tr_match(inv or all_ef_toks, lambda k: True if ef['kind'] != 'qualifier' else k == 6)
            if ef['kind'] == 'qualifier' and not ls:
                rem_qs = [i for i, (_, h) in enumerate(ts_occ) if i not in t_used_s and h[0] == 6]
                rem_qd = [j for j, (_, h) in enumerate(td_occ) if j not in t_used_d and h[0] == 6]
                if rem_qs and rem_qd:
                    for i in rem_qs:
                        t_used_s.add(i)
                        sp, h = ts_occ[i]
                        ls.append(_span(old, sp['file'], sp['start'] + h[1], sp['start'] + h[2]))
                    for j in rem_qd:
                        t_used_d.add(j)
                        sp, h = td_occ[j]
                        rs.append(_span(new, sp['file'], sp['start'] + h[1], sp['start'] + h[2]))
            if not ls or not rs:
                if not inv:
                    ls, rs = [t_shared['source']], [t_shared['candidate']]
                else:
                    raise ValueError(f'{cid} {lang}: unable to align translation spans for fact {ef["id"]} ({inv})')
            ctxs, s_used = tr_box_ctx(ls, rs)
            used_t_scopes.update(s_used)
            tr_facts.append({'fact': ef['id'], 'source': ls, 'candidate': rs, 'context': ctxs})

        # Cover any remaining tokens in translation (e.g. units or EN_ZH second span tokens)
        extra_s, extra_d = find_tr_match(tb_tok | ta_tok, lambda k: k != 6)
        if extra_s and extra_d:
            target_f = next((tf for tf, ef in zip(tr_facts, facts_out) if ef['kind'] != 'qualifier'), None)
            ctxs, s_used = tr_box_ctx(extra_s, extra_d)
            used_t_scopes.update(s_used)
            if target_f is None:
                c_en, _ = find_ctx_for_spans([shared_anchor['source']], [shared_anchor['candidate']], en_src_spans, en_dst_spans, scopes)
                facts_out.append({
                    'id': f'{cid}_f{len(facts_out) + 1}',
                    'kind': 'method',
                    'source': [shared_anchor['source']],
                    'candidate': [shared_anchor['candidate']],
                    'context': c_en,
                })
                tr_facts.append({'fact': facts_out[-1]['id'], 'source': extra_s, 'candidate': extra_d, 'context': ctxs})
            else:
                target_f['source'].extend(extra_s)
                target_f['candidate'].extend(extra_d)
                for ctx in ctxs:
                    if ctx not in target_f['context']:
                        target_f['context'].append(ctx)

        # Prune any t_scope anchor from an unused disjoint box so seen == set(range(len(t_scope)))
        if used_t_scopes != set(range(len(t_scope))):
            kept_idx = sorted(used_t_scopes)
            remap = {old_i: new_i for new_i, old_i in enumerate(kept_idx)}
            t_scope = [t_scope[i] for i in kept_idx]
            for tf in tr_facts:
                for ctx in tf['context']:
                    ctx['scope'] = [remap[i] for i in ctx['scope'] if i in remap]

        translations_out.append({
            'language': lang,
            'source': t_src_spans,
            'candidate': t_dst_spans,
            'facts': tr_facts,
            'scope': t_scope,
            'reviewed_by': reviewers['bilingual'],
            'rationale': t_rat,
        })

    return {
        'id': cid,
        'reviewed_by': reviewers['scientific'],
        'source': en_src_spans,
        'candidate': en_dst_spans,
        'scope': scopes,
        'provenance': provenance,
        'facts': facts_out,
        'translations': translations_out,
    }


def build_review_bundle(
    before_dir: Path,
    after_dir: Path,
    rationales: dict | None = None,
    editor: str = 'DRAFT - reviewer required',
    scientific: str = 'DRAFT - reviewer required',
    bilingual: str = 'DRAFT - reviewer required',
) -> tuple[dict, dict, dict]:
    """Build (review, changes_manifest, decisions_manifest) dicts for before -> after."""
    rationales = rationales or {}
    rev_in = rationales.get('reviewers', {})
    reviewers = {
        'editor': rev_in.get('editor', editor),
        'scientific': rev_in.get('scientific', scientific),
        'bilingual': rev_in.get('bilingual', bilingual),
    }

    a_bytes, b_bytes = edit._tree(before_dir), edit._tree(after_dir)
    if a_bytes.keys() != b_bytes.keys():
        raise ValueError('Manuscript file inventory changed between before and after')
    english = sorted(k for k in a_bytes if k.endswith('_EN.md'))
    if not english:
        raise ValueError('No *_EN.md files found')
    managed = {k for k in a_bytes if edit._group(k) in {edit._group(x) for x in english}}

    old = {k: a_bytes[k].decode('utf-8') for k in managed}
    new = {k: b_bytes[k].decode('utf-8') for k in managed}
    for key in managed:
        before_nl, after_nl = set(re.findall(r'\r?\n', old[key])), set(re.findall(r'\r?\n', new[key]))
        edit._require(not before_nl or not after_nl or before_nl == after_nl,
                      key+': line endings changed (LF/CRLF); preserve original newline bytes before scaffolding')
    declarations = _materialize_declarations(rationales, old, new)

    inventory = {
        k: {'source_sha256': edit._sha(a_bytes[k]), 'candidate_sha256': edit._sha(b_bytes[k])}
        for k in sorted(managed)
    }

    heading_edits, _, heading_covered = _build_heading_edits(old, new, managed, rationales, reviewers)

    changed_ranges = {}
    for k in managed:
        chgs = edit._changed_blocks(old[k], new[k])
        old_r = {(b[0], b[1]) for left, _ in chgs for b in left}
        new_r = {(b[0], b[1]) for _, right in chgs for b in right}
        changed_ranges[k] = (old_r, new_r)

    claims, issues = [], []
    unknowns = list(rationales.get('unknowns', []))
    r_issues = rationales.get('issues', {})
    r_trans = rationales.get('translations', {})
    default_issue = r_issues.get('default', {}) if isinstance(r_issues.get('default'), dict) else {}

    claim_seq = 0
    issue_seq = 0
    unk_seq = len(unknowns)
    for en_key in english:
        group = edit._group(en_key)
        zh_key = group + '_ZH.md' if group + '_ZH.md' in managed else None
        enzh_key = group + '_EN_ZH.md' if group + '_EN_ZH.md' in managed else None

        en_old_sec = _section_blocks(old[en_key], heading_covered[en_key])
        en_new_sec = _section_blocks(new[en_key], heading_covered[en_key])
        zh_old_sec = _section_blocks(old[zh_key], heading_covered[zh_key]) if zh_key else {}
        zh_new_sec = _section_blocks(new[zh_key], heading_covered[zh_key]) if zh_key else {}
        ez_old_sec = _section_blocks(old[enzh_key], heading_covered[enzh_key]) if enzh_key else {}
        ez_new_sec = _section_blocks(new[enzh_key], heading_covered[enzh_key]) if enzh_key else {}

        all_sec_ids = sorted(set(en_old_sec) | set(en_new_sec))
        for sec_id in all_sec_ids:
            eo_blks = en_old_sec.get(sec_id, [])
            en_blks = en_new_sec.get(sec_id, [])
            if not eo_blks and not en_blks:
                continue
            zo_blks = zh_old_sec.get(sec_id, [])
            zn_blks = zh_new_sec.get(sec_id, [])
            ezo_blks = ez_old_sec.get(sec_id, [])
            ezn_blks = ez_new_sec.get(sec_id, [])

            raw_hunks = _align_hunks(eo_blks, en_blks, changed_ranges[en_key][0], changed_ranges[en_key][1])
            # Draft proposal: include an unchanged preceding declaration in the
            # same heading rather than silently treating a changed hunk as local.
            # The resulting claim still needs explicit human inventory review.
            grouped = []
            for ol, nl, changed in raw_hunks:
                bt, at = edit._tokens('\n'.join(x[2] for x in ol)), edit._tokens('\n'.join(x[2] for x in nl))
                if changed and grouped and bt - at == {(6, 'single-seed')} and not (at - bt):
                    po, pn, pc = grouped[-1]
                    prev_text = '\n'.join(x[2] for x in po)
                    if (not pc and [x[2] for x in po] == [x[2] for x in pn]
                            and (6, 'single-seed') in edit._tokens(prev_text)
                            and edit._named_scopes(prev_text) == edit._named_scopes('\n'.join(x[2] for x in ol))):
                        grouped[-1] = (po + ol, pn + nl, True)
                        continue
                grouped.append((ol, nl, changed))
            raw_hunks = grouped
            idx_map_o = {b[:2]: i for i, b in enumerate(eo_blks)}
            idx_map_n = {b[:2]: i for i, b in enumerate(en_blks)}
            en_hunks = [
                (ol, nl, [idx_map_o[b[:2]] for b in ol], [idx_map_n[b[:2]] for b in nl], chg)
                for ol, nl, chg in raw_hunks
            ]

            zh_mapped = _map_zh_indices_for_hunks(
                [(ol, nl, io, jn) for ol, nl, io, jn, _ in en_hunks],
                zo_blks, zn_blks, len(eo_blks), len(en_blks),
            ) if zh_key else [([], [], False)] * len(en_hunks)

            ez_old_pairs = _pair_enzh_section(eo_blks, ezo_blks) if enzh_key else []
            ez_new_pairs = _pair_enzh_section(en_blks, ezn_blks) if enzh_key else []
            ez_mapped = []
            for ol, nl, io, jn, _ in en_hunks:
                ezo_slice = (
                    sorted({b[:2]: b for idx in io for b in ez_old_pairs[idx]}.values(), key=lambda x: x[0])
                    if enzh_key and ez_old_pairs else []
                )
                ezn_slice = (
                    sorted({b[:2]: b for idx in jn for b in ez_new_pairs[idx]}.values(), key=lambda x: x[0])
                    if enzh_key and ez_new_pairs else []
                )
                ez_chg = (
                    [x[2] for x in ezo_slice] != [x[2] for x in ezn_slice]
                    or any((x[0], x[1]) in changed_ranges[enzh_key][0] for x in ezo_slice)
                    or any((x[0], x[1]) in changed_ranges[enzh_key][1] for x in ezn_slice)
                )
                ez_mapped.append((ezo_slice, ezn_slice, ez_chg))

            for (ol, nl, _, _, en_chg), (zol, znl, zh_chg), (ezol, eznl, ez_chg) in zip(en_hunks, zh_mapped, ez_mapped):
                zh_hit = zh_key and (
                    zh_chg
                    or any((x[0], x[1]) in changed_ranges[zh_key][0] for x in zol)
                    or any((x[0], x[1]) in changed_ranges[zh_key][1] for x in znl)
                )
                if not (en_chg or zh_hit or ez_chg):
                    # Preserve unchanged sub-blocks (e.g. single-newline captions inside an edited multi-caption block)
                    # via unknowns so changed_blocks coverage stays complete without emitting spurious claims.
                    for ob, nb in zip(ol, nl):
                        if ob[2] == nb[2] and (_overlaps_any(ob, changed_ranges[en_key][0]) or _overlaps_any(nb, changed_ranges[en_key][1])):
                            unk_seq += 1
                            unknowns.append({
                                'id': f'U{unk_seq}',
                                'source': _span(old, en_key, ob[0], ob[1]),
                                'candidate': _span(new, en_key, nb[0], nb[1]),
                                'reason': f'Preserved unchanged caption/sub-block inside edited block in {en_key}.',
                            })
                    for tkey, tol, tnl in ((zh_key, zol, znl), (enzh_key, ezol, eznl)):
                        if not tkey:
                            continue
                        for tb, tn in zip(tol, tnl):
                            if tb[2] == tn[2] and (_overlaps_any(tb, changed_ranges[tkey][0]) or _overlaps_any(tn, changed_ranges[tkey][1])):
                                unk_seq += 1
                                unknowns.append({
                                    'id': f'U{unk_seq}',
                                    'source': _span(old, tkey, tb[0], tb[1]),
                                    'candidate': _span(new, tkey, tn[0], tn[1]),
                                    'reason': f'Preserved unchanged caption/sub-block inside edited block in {tkey}.',
                                })
                    continue
                subclaims = _split_multi_owner_en_hunk(ol, nl)
                zh_subs = _split_translation_for_subclaims(subclaims, zol, znl, False) if zh_key else None
                ez_subs = _split_translation_for_subclaims(subclaims, ezol, eznl, True) if enzh_key else None
                for sc_idx, (sc_ol, sc_nl) in enumerate(subclaims):
                    en_src_s = _contiguous_or_list(sc_ol, old[en_key], en_key)
                    en_dst_s = _contiguous_or_list(sc_nl, new[en_key], en_key)
                    sc_en_owners = edit._named_scopes('\n'.join(x['text'] for x in en_src_s))
                    all_verbatim_multi = False
                    if any(len(v) > 1 for v in sc_en_owners.values()):
                        en_same = [sp_o['text'] for sp_o in en_src_s] == [sp_d['text'] for sp_d in en_dst_s]
                        tr_same = True
                        for tkey, tsubs in ((zh_key, zh_subs), (enzh_key, ez_subs)):
                            if not tkey or not tsubs:
                                continue
                            ts_ol, ts_nl = tsubs[sc_idx]
                            if [sp['text'] for sp in _contiguous_or_list(ts_ol, old[tkey], tkey)] != [
                                sp['text'] for sp in _contiguous_or_list(ts_nl, new[tkey], tkey)
                            ]:
                                tr_same = False
                                break
                        all_verbatim_multi = en_same and tr_same
                    if all_verbatim_multi:
                        # Unchanged multi-owner sentence inside a polished block -> preserve verbatim via unknowns
                        for sp_o, sp_d in zip(en_src_s, en_dst_s):
                            unk_seq += 1
                            unknowns.append({
                                'id': f'U{unk_seq}',
                                'source': sp_o,
                                'candidate': sp_d,
                                'reason': 'Preserved verbatim multi-owner reference sentence inside edited paragraph.',
                            })
                        for tkey, tsubs in ((zh_key, zh_subs), (enzh_key, ez_subs)):
                            if not tkey or not tsubs:
                                continue
                            ts_ol, ts_nl = tsubs[sc_idx]
                            for sp_o, sp_d in zip(
                                _contiguous_or_list(ts_ol, old[tkey], tkey),
                                _contiguous_or_list(ts_nl, new[tkey], tkey),
                            ):
                                unk_seq += 1
                                unknowns.append({
                                    'id': f'U{unk_seq}',
                                    'source': sp_o,
                                    'candidate': sp_d,
                                    'reason': f'Preserved verbatim multi-owner sentence in {tkey} matching EN sentence.',
                                })
                        continue
                    claim_seq += 1
                    cid = f'C{claim_seq}'
                    trans_entries = []
                    if zh_key and zh_subs:
                        zs_ol, zs_nl = zh_subs[sc_idx]
                        trat = r_trans.get(zh_key) or r_trans.get('default') or (
                            f'Synchronized {zh_key} with polished English claim {cid}.'
                        )
                        trans_entries.append((
                            'ZH',
                            _contiguous_or_list(zs_ol, old[zh_key], zh_key),
                            _contiguous_or_list(zs_nl, new[zh_key], zh_key),
                            trat,
                        ))
                    if enzh_key and ez_subs:
                        es_ol, es_nl = ez_subs[sc_idx]
                        trat = r_trans.get(enzh_key) or r_trans.get('default') or (
                            f'Synchronized {enzh_key} with polished English claim {cid}.'
                        )
                        trans_entries.append((
                            'EN_ZH',
                            _contiguous_or_list(es_ol, old[enzh_key], enzh_key),
                            _contiguous_or_list(es_nl, new[enzh_key], enzh_key),
                            trat,
                        ))
                    inherited = _bind_inheritance(declarations, cid, en_src_s, en_dst_s, trans_entries)
                    claims.append(_build_claim_record(cid, en_src_s, en_dst_s, trans_entries, old, new, reviewers, inherited))

        # Cover every changed EN block (including heading-only blocks) under narrative.issues
        en_changed_blocks = edit._changed_blocks(old[en_key], new[en_key])
        for hunk_idx, (left_blks, right_blks) in enumerate(en_changed_blocks, 1):
            issue_seq += 1
            iid = f'N{issue_seq}'
            custom = r_issues.get(en_key, {}) if isinstance(r_issues.get(en_key), dict) else {}
            l_spans = [_span(old, en_key, b[0], b[1]) for b in left_blks]
            r_spans = [_span(new, en_key, b[0], b[1]) for b in right_blks]
            if not l_spans:
                l_spans = [_span(old, en_key, 0, len(old[en_key]))]
            if not r_spans:
                r_spans = [_span(new, en_key, 0, len(new[en_key]))]
            issues.append({
                'id': iid,
                'kind': custom.get('kind', default_issue.get('kind', 'narrative-clarity')),
                'source': l_spans,
                'candidate': r_spans,
                'decision': custom.get('decision', default_issue.get('decision', 'retained')),
                'central': custom.get('central', default_issue.get('central', True)),
                'reviewed_by': reviewers['editor'],
                'reason': custom.get('reason') or default_issue.get('reason') or (
                    f'DRAFT: reviewer disposition required for {en_key} (hunk {hunk_idx}).'
                ),
            })

    narrative = {
        'reviewed_by': reviewers['editor'],
        'source': [_span(old, k, 0, len(old[k])) for k in english if old[k]],
        'candidate': [_span(new, k, 0, len(new[k])) for k in english if new[k]],
        'summary': rationales.get('narrative_summary') or (
            'DRAFT machine scaffold. Unique verbal facts, scope, narrative and translations require actual review.'
        ),
        'issues': issues,
    }

    review = {
        'schema_version': 1,
        'reviewers': reviewers,
        'inventory': inventory,
        'heading_edits': heading_edits,
        'claims': claims,
        'unknowns': unknowns,
        'narrative': narrative,
    }
    if declarations:
        review['scope_declarations'] = declarations
    inventory_review = rationales.get('inventory_review')
    review['review_status'] = {'state': 'draft', 'reviewed_by': reviewers['scientific'], 'rationale': '', 'facts': []}
    if inventory_review is not None:
        edit._object(inventory_review, ('reviewed_by', 'rationale', 'facts'), 'inventory review')
        status = dict(inventory_review, state='reviewed', facts=[])
        for supplied in inventory_review['facts']:
            fact = dict(supplied)
            for side, texts in [('source', old), ('candidate', new)]:
                fact[side] = [resolve_exact_span(texts, x) for x in supplied[side]]
            if fact.get('claim', 'AUTO') == 'AUTO':
                matching = [c['id'] for c in claims if all(edit._inside(x, c['source']) for x in fact['source']) and all(edit._inside(x, c['candidate']) for x in fact['candidate'])]
                edit._require(len(matching) == 1, 'Verbal inventory must identify one exact governed claim')
                fact['claim'] = matching[0]
            status['facts'].append(fact)
        edit._require(bool(rationales.get('narrative_summary')), 'Reviewed scaffold needs supplied narrative rationale')
        edit._require(all(not i['reason'].startswith('DRAFT') for i in issues), 'Reviewed scaffold needs supplied narrative issue dispositions')
        review['review_status'] = status
    if 'author_limits' in rationales:
        review['author_limits'] = rationales['author_limits']

    append_only = [
        k for k in sorted(a_bytes.keys() - managed)
        if (Path(k).name == '作者决定.md' or Path(k).name.endswith('_作者决定.md'))
        and a_bytes[k] != b_bytes[k]
    ]
    if append_only:
        review['append_only_author_files'] = append_only

    return review, {'schema_version': 1, 'decisions': [x['id'] for x in issues]}, None


def write_review_bundle(
    before_dir: Path,
    after_dir: Path,
    review_path: Path,
    changes_path: Path,
    decisions_path: Path | None = None,
    rationales: dict | None = None,
    editor: str = 'DRAFT - reviewer required',
    scientific: str = 'DRAFT - reviewer required',
    bilingual: str = 'DRAFT - reviewer required',
    verify: bool = False,
) -> dict:
    """Build and write review.json, changes.json, and optional decisions.json."""
    review, base_manifest, _ = build_review_bundle(
        before_dir, after_dir, rationales, editor=editor, scientific=scientific, bilingual=bilingual
    )
    review_path.parent.mkdir(parents=True, exist_ok=True)
    changes_path.parent.mkdir(parents=True, exist_ok=True)
    review_bytes = (json.dumps(review, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    review_path.write_bytes(review_bytes)
    manifest = {
        'schema_version': 1,
        'review_sha256': edit._sha(review_bytes),
        'decisions': base_manifest['decisions'],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    changes_path.write_bytes(manifest_bytes)
    if decisions_path is not None:
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_bytes(manifest_bytes)
    summary = {
        'review_json': str(review_path),
        'changes': str(changes_path),
        'decisions': str(decisions_path) if decisions_path else None,
        'review_sha256': manifest['review_sha256'],
        'heading_edits': len(review['heading_edits']),
        'claims': len(review['claims']),
        'narrative_decisions': manifest['decisions'],
    }
    if verify:
        comp = edit.compare_paths(before_dir, after_dir, review_path, changes_path)
        summary['compare'] = comp
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', required=True, type=Path)
    p.add_argument('--after', required=True, type=Path)
    p.add_argument('--review-json', required=True, type=Path)
    p.add_argument('--changes', required=True, type=Path)
    p.add_argument('--decisions', type=Path)
    p.add_argument('--rationale-json', type=Path)
    p.add_argument('--editor', default='DRAFT - reviewer required')
    p.add_argument('--scientific', default='DRAFT - reviewer required')
    p.add_argument('--bilingual', default='DRAFT - reviewer required')
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    try:
        rationales = (
            json.loads(args.rationale_json.read_bytes().decode('utf-8'))
            if args.rationale_json
            else None
        )
        res = write_review_bundle(
            args.before, args.after, args.review_json, args.changes, args.decisions,
            rationales=rationales, editor=args.editor, scientific=args.scientific,
            bilingual=args.bilingual, verify=args.verify,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if args.verify and res.get('compare', {}).get('errors'):
            return 1
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'errors': [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
