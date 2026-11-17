"""Deterministic pre-delivery checks for medical-sci-* manuscript sections.

Usage:
  python -X utf8 manuscript_check.py <section> <EN.md> [--zh ZH.md] [--results Results_EN.md] [--json]
  section: methods | legends | results | introduction | discussion | abstract

Checks the countable rules written in each skill's writing-rules / journal-style: word count,
sentence length, banned words, template-phrase frequency, citation format, verified citation soft quotas, EN/ZH
PMID and number parity, numbers against Results, figure-panel letter case.
ERROR = explicit limits, citation/format or evidence consistency failure; WARN/INFO = contextual diagnostics, record review in the 核查说明. Bare lexical matches do not establish scientific overclaim.
Exit code 1 if any ERROR. Argument quality, citation support and factual correctness are not checked.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from style_check import analyze_style

E, W, I = "ERROR", "WARN", "INFO"

# (level, rule id, regex, reporting threshold, message); 0 reports any match.
# WARN thresholds locate passages for contextual review; they are not word budgets.
COMMON = [
    (E, "numeric-citation", r"\[\d+(?:\s*[,–-]\s*\d+)*\]", 0, "数字式引用；改为 (PMID: …)"),
    (W, "hype", r"\b(?:novel|unprecedented|breakthrough|groundbreaking|paradigm-shifting|for the first time)\b", 0,
     "宣传性或首次性用语"),
    (W, "british-spelling", r"\b(?:tumour|oedema|haemorrhage|modelling|centre|colour|analys(?:e|ed|ing)|randomised|"
     r"normalised|behaviour|labelled|optimise[sd]?|generalis\w+)\b", 0, "非美式拼写（专有名称、引用题名除外）"),
    (W, "engineering-term", r"\b(?:audit\w*|ledger|firewall|frozen endpoint|seed-0)\b", 0, "工程或内部词汇"),
    (W, "meta-jargon", r"\b(?:structured method|method carrier|evaluation vehicle|evaluation framework|interpretability carrier)\b", 0,
     "空洞过程元标签，改用具体模型或直接发现"),
]

PROFILES = {
    "abstract": dict(words=(None, 250, E), rules=[
        (W, "overclaim", r"\b(?:prove[sd]?|proven|clearly|undoubtedly|clinically deployable)\b", 0,
         "审读结论强度与实际证据是否相称；词语匹配本身不能证明过度主张"),
        (E, "abstract-reference", r"(?:PMID|DOI|URL|arXiv)\s*:|\b(?:Fig\.|Figure|Table)\s*S?\d|\[citation needed\]", 0,
         "摘要默认不带引用、图表号或引用占位"),
        (W, "generic-validation-closer", r"\brequiring (?:further |prospective )?validation\b|\b(?:safe|clinical)\s+(?:deployment|use)\s+requires\s+(?:further|prospective)\b", 0,
         "空泛验证收尾，改为具体适用条件或直接发现边界"),
    ]),
    "methods": dict(words=(None, 3000, W), rules=[]),
    "legends": dict(words=None, legend_words=150, rules=[
        (W, "comparison-word", r"\b(?:superior|outperform\w*|favou?r(?:s|ed)?|advantage)\b", 0,
         "审读比较方向、效应量及不确定性；有据的直接比较可保留"),
        (W, "disclaimer", r"\b(?:do(?:es)? not establish|not significant overall|not clinical)\b", 0, "通用免责句"),
    ]),
    "results": dict(words=(None, 4000, W), rules=[
        (W, "sentence-opener", r"(?:^|(?<=[.!?]\s))(?:First|Then|Next|Finally|"
         r"Notably|Interestingly|Importantly)\b", 0, "句首串联或强调词"),
        (W, "section-number", r"\bSection \d|\d\.\d+ ?节|上一节", 0, "正文出现节号"),
        (W, "therefore-family", r"\b(?:therefore|thus|consequently)\b", 6, "结论连接词重复：审读推论关系与节奏，不按次数删换"),
        (W, "coexisted", r"\bcoexist(?:ed|s)?\b", 3, "共现表述重复：审读是否准确且有用，不按次数删换"),
        (W, "accompanied", r"\baccompanied\b", 3, "伴随表述重复：审读实际关系，不按次数删换"),
        (W, "separating", r"\bseparating\b", 3, "区分表述重复：审读是否具体，不按次数删换"),
    ]),
    "introduction": dict(words=(None, 1200, W), rules=[
        (W, "to-our-knowledge", r"\bto our knowledge\b", 1, "首次性限定重复：核对检索支持与各处必要性，不设次数配额"),
        (W, "negative-gap", r"\b(?:do|does|did) not (?:establish|show|demonstrate|determine)\b|\bcannot\b|\bneither\b", 2,
         "否定式空白句重复：核对具体缺口及支持文献，保留必要的否定"),
        (W, "no-study-has", r"\bno (?:previous |prior )?stud(?:y|ies) ha(?:s|ve)\b", 0, "核对文献检索能否支持排他性空白主张"),
        (W, "scope-disclaimer", r"\bwithout implying\b|\b(?:outside|beyond) (?:the |this )?(?:study's |present )?scope\b", 1,
         "范围限定重复：核对共享声明与必要例外，不能删除真实边界"),
        (W, "roadmap", r"\b(?:rest|remainder) of this (?:paper|article)\b|\bis organized as follows\b", 0, "路标式结构说明"),
        (W, "result-verb", r"\bwe (?:show|demonstrate|reveal|confirm|establish)\b", 0, "核对贡献句是否准确且服务于研究问题；有据的主张句可保留"),
    ]),
    "discussion": dict(words=(None, 1500, W), rules=[
        (W, "overclaim", r"\b(?:prove[sd]?|proven|clearly|undoubtedly)\b", 0, "审读实际证据与结论强度；词语匹配本身不能证明过度主张"),
        (W, "confirm", r"\bconfirm(?:s|ed)? (?:that|our)\b", 0, "核对研究设计和证据是否支持确认性结论，不机械替换动词"),
        (W, "to-our-knowledge", r"\bto our knowledge\b", 1, "首次性限定重复：核对检索支持与各处必要性，不设次数配额"),
        (W, "agrees-with", r"\bagree(?:s|d)? with\b", 2, "文献对照表达重复：审读各处比较的实际作用，不按次数删换"),
        (W, "extends", r"\bextend(?:s|ed)?\b", 2, "扩展性表达重复：核对具体新增证据，不按次数删换"),
        (W, "consistent-with", r"\b(?:is|are|was|were) consistent with\b", 2, "一致性表达重复：核对证据关系，不按次数删换"),
        (W, "contrasts-with", r"\bcontrast(?:s|ed)? with\b", 2, "对照表达重复：核对真实差异及段落作用，不按次数删换"),
        (W, "would-test", r"\bwould (?:test|distinguish|address|clarify|determine|separate)\b", 3, "检验建议重复：审读是否具体且与未决问题相关，不设次数配额"),
        (W, "negative-boundary", r"\b(?:does|do|did) not (?:imply|establish|identify|mean|indicate|demonstrate|prove|"
         r"ensure|guarantee|represent)\b|\bcannot be (?:assumed|interpreted|attributed|extended|treated|inferred)\b|"
         r"\bpreclude[sd]?\b", 5, "否定式限定重复：审读必要边界与冗余，不能按次数删除不利结果"),
        (W, "empty-future", r"\bfurther (?:studies|research|work) (?:is|are) (?:needed|warranted|required)\b", 0,
         "空泛的未来方向"),
        (W, "generic-validation-closer", r"\brequiring (?:further |prospective )?validation\b|\b(?:safe|clinical)\s+(?:deployment|use)\s+requires\s+(?:further|prospective)\b", 0,
         "空泛验证收尾，改为具体适用条件或已交代局限后的直接结论"),
        (W, "defensive-hedging-cluster", r"\b(?:unresolved|unestablished|remain(?:s|ed|ing)?\s+(?:descriptive|empirical|unresolved|unclear|cohort-dependent)|(?:do|does|did)\s+not\s+establish)\b", 3,
         "Discussion 重复使用 unresolved / not establish / remain* 防御性套话，请直陈已发现边界与可操作局限"),
        (W, "section-mention", r"\b(?:the|our) (?:Introduction|Methods|Results)\b|\bin the (?:Methods|Results) section\b", 0,
         "正文提及其他章节"),
        (W, "we-found-opener", r"(?:^|(?<=[.!?]\s))(?:We found|Our (?:results|findings))\b", 4,
         "主张句开头重复：审读节奏与实际发现，有据的直接主张可保留"),
        (W, "citation-needed", r"\[citation needed\]", 0, "引用缺口，须列入核查说明第 1 部分"),
    ]),
}
CITE_IN_PARENS = re.compile(r"[(（][^()（）]*?(?:PMID|DOI|URL|arXiv)\s*:[^()（）]*[)）]")
FIG_REF = re.compile(r"[(（][^()（）]*?(?:Fig\.|Figure|Table|Supplementary|图\s*\d|表\s*\d|补充图)[^()（）]*[)）]")
PMID = re.compile(r"PMID:\s*(\d+)")
BAD_PMID = re.compile(r"PMID:\s*(?!\d{6,9}\b)\S+|PMID\s+\d|PMID：")
NUM = re.compile(r"(?<![A-Za-z0-9_.])[−-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
PANEL = re.compile(r"\b(?:Fig\.|Figure|Supplementary Fig\.)\s*S?\d+([A-Ha-h])\b")


def strip_md(text):
    """Body text only: drop headings, emphasis markers and table lines."""
    lines = [l for l in text.replace("\r\n", "\n").split("\n") if not l.lstrip().startswith(("#", "|"))]
    return re.sub(r"\*\*|__", "", "\n".join(lines))


def words_of(text):
    t = CITE_IN_PARENS.sub(" ", FIG_REF.sub(" ", text))
    t = re.sub(r"\((?:[a-h](?:[–-][a-h])?)\)", " ", t)  # 段落级/panel 标签不算词
    return len(t.split())


def sentences(text):
    out = []
    for para in [p for p in text.split("\n") if p.strip()]:
        p = CITE_IN_PARENS.sub("", FIG_REF.sub("", para))
        p = re.sub(r"\b(?:e\.g|i\.e|et al|vs|Fig|approx|Dr|No)\.", lambda m: m.group(0)[:-1], p)
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(“\"])", p) if s.strip()]
    return out


def numbers(text):
    t = CITE_IN_PARENS.sub(" ", FIG_REF.sub(" ", text))
    return [n.replace("−", "-").replace(",", "") for n in NUM.findall(t)]


def abstract_numbers(text):
    """Chinese prose may touch a signed number; ASCII identifiers may not."""
    t = CITE_IN_PARENS.sub(" ", FIG_REF.sub(" ", text))
    found = re.findall(r"(?<![A-Za-z0-9_.])[−-]?\d+(?:,\d{3})*(?:\.\d+)?%?", t)
    return [n.replace("−", "-").replace(",", "") for n in found]


def abstract_body(text):
    """Exclude ancillary sections from abstract length; keep them for claim checks."""
    return re.split(r"^#{1,6}\s*(?:Keywords|Highlights|关键词|研究亮点|亮点)\s*#*\s*$", text,
                    maxsplit=1, flags=re.M | re.I)[0]


def check(section, en_path, zh_path=None, results_path=None, abstract_limit=250, allow_abstract_references=False,
          limits_json=None):
    prof = PROFILES[section]
    raw = Path(en_path).read_text(encoding="utf-8-sig")
    body = strip_md(abstract_body(raw) if section == "abstract" else raw)
    claims = strip_md(raw) if section == "abstract" else body
    out = []

    def add(level, rule, msg, ctx=""):
        out.append({"level": level, "rule": rule, "msg": msg, "context": ctx[:160]})

    from writing_limits import load_limits
    try:
        declared = load_limits(en_path, limits_json).get(section)
    except (ValueError, OSError) as exc:
        add(E, 'word-limits-config', str(exc))
        declared = None
    # length
    if section == "legends":
        for leg in re.split(r"\n(?=\*\*(?:Supplementary )?(?:Figure|Table) )", raw.replace("\r\n", "\n")):
            m = re.match(r"\*\*((?:Supplementary )?(?:Figure|Table) S?\d+)", leg)
            lo = declared.get('min') if declared else None
            hi = declared.get('max') if declared else prof['legend_words']
            n = words_of(leg)
            if m and m.group(1).split()[-2] != "Table" and ((lo and n < lo) or (hi and n > hi)):
                add(E if declared else W, "legend-length", f"{m.group(1)} 英文 {n} 词，目标 {lo or '—'}–{hi or '—'}")
        if re.search(r"\n\s*\n\*\*(?:Supplementary )?(?:Figure|Table)", raw.replace("\r\n", "\n")):
            add(E, "legend-blank-line", "图注之间有空行")
    else:
        n = words_of(body)
        lo, hi, lvl = prof["words"]
        if section == "abstract":
            hi = abstract_limit
        if declared is not None:
            lo, hi, lvl = declared.get('min'), declared.get('max'), E
        if (lo and n < lo) or (hi and n > hi):
            add(lvl, "word-count", f"英文正文 {n} 词，目标 {lo or '—'}–{hi}")
    # Shared style policy replaces legacy per-section 45/50/55-word caps.
    # Use raw Markdown so headings/boundaries and source locations remain available.
    style_text = abstract_body(raw) if section == "abstract" else raw
    out.extend(analyze_style(style_text, section)["findings"])
    # heading checks (strip_md omits headings for word counts, so inspect headings explicitly)
    heading_lines = [
        re.sub(r"^#{1,6}\s+", "", line.lstrip()).strip()
        for line in style_text.replace("\r\n", "\n").split("\n")
        if line.lstrip().startswith("#")
    ]
    heading_rules = [r for r in COMMON + prof["rules"] if r[1] in ("overclaim", "hype", "meta-jargon", "engineering-term")]
    if heading_lines:
        headings_joined = "\n".join(heading_lines)
        for level, rule, pat, _, msg in heading_rules:
            hits = list(re.finditer(pat, headings_joined, re.I))
            if hits:
                add(level, rule, f"标题含{msg}（{len(hits)} 处）", headings_joined[max(0, hits[0].start() - 20):hits[0].end() + 40])
        if section == "results":
            vague_pat = re.compile(r"\b(?:holds?\s+(?:across|in)\s+most|descriptive(?:ly)?|varies across cohorts and declines)\b", re.I)
            for hline in heading_lines:
                if vague_pat.search(hline):
                    add(W, "heading-defensive-vague", "小节标题含模糊多数或被动防御标签，改写为精准边界陈述", hline)
    # phrase rules
    for level, rule, pat, mx, msg in COMMON + prof["rules"]:
        if section == "abstract" and rule == "abstract-reference" and allow_abstract_references:
            continue
        hits = [m for m in re.finditer(pat, claims, re.I if rule not in ("sentence-opener", "we-found-opener") else 0)]
        if len(hits) > mx:
            ctx = "; ".join(claims[max(0, h.start() - 30):h.end() + 30].replace("\n", " ") for h in hits[:3])
            add(level, rule, f"{msg}（{len(hits)} 处）", ctx)
    # paragraph density & repetition diagnostics
    paras = [p.strip() for p in re.split(r"\n\s*\n", body.replace("\r\n", "\n")) if p.strip()]
    if section == "results":
        cite_target = re.compile(r"\b((?:Supplementary\s+)?(?:Fig(?:ure)?\.?|Tables?)\s*S?\d+[A-Za-z]?)\b", re.I)
        cite_root = re.compile(r"\b((?:Supplementary\s+)?(?:Fig(?:ure)?\.?|Tables?)\s*S?\d+)[A-Za-z]?\b", re.I)
        for p in paras:
            targets = Counter(
                re.sub(r"\s+", " ", m.group(1).casefold()).replace("figure", "fig").replace("fig.", "fig").replace("tables", "table")
                for m in cite_target.finditer(p)
            )
            roots = Counter(
                re.sub(r"\s+", " ", m.group(1).casefold()).replace("figure", "fig").replace("fig.", "fig").replace("tables", "table")
                for m in cite_root.finditer(p)
            )
            repeated = [(k, v) for k, v in targets.items() if v >= 3]
            if repeated:
                summary = ", ".join(f"{k} ({v}次)" for k, v in repeated[:3])
                add(W, "citation-repeat", f"单段同一图表引用 ≥3 次：{summary}（连续同源句优先合并至单元/句末括号）", p)
            else:
                root_repeated = [(k, v) for k, v in roots.items() if v >= 4]
                if root_repeated:
                    summary = ", ".join(f"{k} ({v}次)" for k, v in root_repeated[:3])
                    add(W, "citation-repeat", f"单段同一主图表引用 ≥4 次：{summary}（合并连续同源或子图 panel 引用）", p)
        bp_hits = list(re.finditer(
            r"\b(?:complete|full)\s+[\w-]+\s+data\s+(?:are\s+|were\s+)?(?:supplied|provided|reported)\s+as\s+supplementary\s+data\b|"
            r"\bsupplied\s+as\s+supplementary\s+data\b|\bprediction-set\s+supplementary\s+data\b",
            body, re.I,
        ))
        if len(bp_hits) >= 3:
            add(W, "boilerplate-repeat", f"补充数据模板套话重复 {len(bp_hits)} 次，合并至统一表格/总述处", bp_hits[0].group(0))
        else:
            prose_clean = CITE_IN_PARENS.sub(" ", FIG_REF.sub(" ", body.lower()))
            words_seq = re.findall(r"[a-z]{3,}(?:-[a-z]{2,})*", prose_clean)
            metric_skip = ("confidence interval", "balanced accuracy", "receiver operating", "precision recall",
                           "calibration error", "decision curve", "concept bottleneck", "confusion matrix")
            ngrams = Counter(" ".join(words_seq[i:i + 7]) for i in range(max(0, len(words_seq) - 6)))
            dup_ngrams = [(g, c) for g, c in ngrams.items() if c >= 3 and not any(m in g for m in metric_skip)]
            if dup_ngrams:
                add(W, "boilerplate-repeat", f"长套话短语重复 ≥3 次：\"{dup_ngrams[0][0]}\"（{dup_ngrams[0][1]} 次）", dup_ngrams[0][0])
        subsumed = list(re.finditer(r"\(([^()]*\b(?:Supplementary\s+)?(?:Fig\.|Figure)\s*(S?\d+)\s*;[^()]*\b(?:Supplementary\s+)?(?:Fig\.|Figure)\s*\2[A-Za-z])", body, re.I))
        if subsumed:
            add(W, "citation-redundant-parent", f"同一括号同时列出总图与该图子 panel（{len(subsumed)} 处，改为更精确的子 panel 引用）", subsumed[0].group(0))
        adj_repeat = list(re.finditer(r"(\((?:Supplementary\s+)?(?:Fig\.|Figure|Table)\s*S?\d+[A-Za-z]?(?:[–-][A-Za-z])?\))\.\s+[^.\n]+\1\.", body, re.I))
        if adj_repeat:
            add(W, "citation-adjacent-repeat", f"相邻两句末尾重复挂载同一图表引用（{len(adj_repeat)} 处，合并至单元/句末共享括号）", adj_repeat[0].group(0))
    if section in ("introduction", "results", "discussion"):
        for p in paras:
            n_sents, n_words = len(sentences(p)), words_of(p)
            if n_sents > 8 or n_words > 200:
                add(W, "paragraph-dense", f"单段过密（{n_sents} 句 / {n_words} 词；建议拆分为单一论证单元 ≤8 句且 ≤200 词）", p)
    # citations
    for m in BAD_PMID.finditer(claims):
        add(E, "pmid-format", "PMID 格式应为 (PMID: 12345678)", claims[max(0, m.start() - 20):m.end() + 20])
    pmids = PMID.findall(claims)
    if section in ("introduction", "discussion"):
        from citation_stats import check_section_quota
        for finding in check_section_quota(section, en_path):
            add(W, finding["rule"], finding["msg"])
    dup = [p for p, c in Counter(pmids).items() if c > 1]
    if dup and section in ("introduction", "discussion"):
        contexts = []
        for pmid in dup:
            uses = [claims[max(0, m.start() - 65):m.end() + 35].replace('\n', ' ')
                    for m in re.finditer(r'PMID:\s*' + re.escape(pmid) + r'\b', claims)]
            contexts.append(pmid + ': ' + ' | '.join(uses))
        add(I, "pmid-repeat", f"同一来源用于多处论断：{', '.join(dup)}；按各处支持关系判断，重复本身不要求删除或换源",
            '; '.join(contexts))
    # panel letter case
    cases = Counter("upper" if c.isupper() else "lower" for c in PANEL.findall(body))
    if len(cases) > 1:
        add(W, "panel-case", f"图 panel 字母大小写混用：{dict(cases)}（应与 Results / 图面一致）")
    # EN/ZH parity
    if zh_path:
        zh_raw = Path(zh_path).read_text(encoding="utf-8-sig")
        zh = strip_md(zh_raw)
        a, b = Counter(pmids), Counter(PMID.findall(zh))
        if a != b:
            add(E, "zh-pmid", f"中英 PMID 不一致：仅英文 {sorted((a - b).elements())}，仅中文 {sorted((b - a).elements())}")
        extract_numbers = abstract_numbers if section == "abstract" else numbers
        ne = Counter(x for x in extract_numbers(claims) if re.search(r"[.%]|\d{3,}", x))
        nz = Counter(x for x in extract_numbers(zh) if re.search(r"[.%]|\d{3,}", x))
        if ne - nz:
            add(W, "zh-number", f"英文有、中文无的数字：{sorted((ne - nz).elements())[:12]}")
        if section == "abstract" and nz - ne:
            add(W, "en-number", f"中文有、英文无的数字：{sorted((nz - ne).elements())[:12]}")
        if re.search(r"\((?:PMID|DOI)", zh):
            add(E, "zh-paren", "中文稿引用应用全角括号（PMID: …）")
        zh_clean = re.sub(r"`[^`\n]+`", " ", CITE_IN_PARENS.sub("", zh_raw))
        seed_hits = list(re.finditer(r"\bseed\b", zh_clean, re.I))
        if seed_hits:
            h0 = seed_hits[0]
            add(W, "zh-unlocalized-seed", f"中文稿保留未本地化英文词 seed（{len(seed_hits)} 处，应写为“种子”）",
                zh_clean[max(0, h0.start() - 20):h0.end() + 20])
        figtable_hits = list(re.finditer(r"\b(?:Supplementary\s+)?(?:Fig(?:ure)?\.?|Tables?)\s*S?\d+[A-Za-z]?\b", zh_clean))
        if figtable_hits:
            h0 = figtable_hits[0]
            add(W, "zh-unlocalized-figtable", f"中文稿保留英文图表编号（{len(figtable_hits)} 处，应写为“图/表/附图/附表”）",
                zh_clean[max(0, h0.start() - 20):h0.end() + 20])
        zh_body_raw = "\n".join(
            l for l in zh_raw.replace("\r\n", "\n").split("\n") if not l.lstrip().startswith(("#", "|"))
        )
        zh_period_scan = re.sub(r"。(?:\*\*|__)[ \t]*", "。", zh_body_raw)
        period_spaces = list(re.finditer(r"。[ \t]+(?=\S)", zh_period_scan))
        if period_spaces:
            h0 = period_spaces[0]
            add(W, "zh-space-after-period", f"中文句号后有多余空格（{len(period_spaces)} 处）",
                zh_period_scan[max(0, h0.start() - 15):h0.end() + 25])
        seed_spaces = list(re.finditer(r"(?<!\*\*)(?<!__)(?<!\([a-h]\))(?<!\([A-H]\))(?<!（[a-h]）)(?<!（[A-H]）) 种子|种子 ", zh_clean))
        if seed_spaces:
            h0 = seed_spaces[0]
            add(W, "zh-seed-space", f"“种子”前后有多余英文空格（{len(seed_spaces)} 处）",
                zh_clean[max(0, h0.start() - 15):h0.end() + 20])
        punct_spaces = list(re.finditer(r"[ \t]+[。，；：、）】]", zh_clean))
        if punct_spaces:
            h0 = punct_spaces[0]
            add(W, "zh-space-before-punct", f"中文标点前有多余空格（{len(punct_spaces)} 处）",
                zh_clean[max(0, h0.start() - 15):h0.end() + 20])
        bold_artifacts = list(re.finditer(r"\*{4}|\*\*\([a-h](?:[–-][a-h])?\)", zh_clean))
        if bold_artifacts:
            h0 = bold_artifacts[0]
            add(W, "zh-bold-artifact", f"中文粗体格式残留（**** 或 ** 与 (a) 之间缺少空格，{len(bold_artifacts)} 处）",
                zh_clean[max(0, h0.start() - 15):h0.end() + 20])
        zh_no_math = re.sub(r"\\\(.*?\\\)|\$[^$\n]+\$", "_MATH_", zh_clean)
        zh_no_math_body = "\n".join(
            l for l in zh_no_math.replace("\r\n", "\n").split("\n") if not l.lstrip().startswith(("#", "|"))
        )
        cjk_spaces = list(re.finditer(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", zh_no_math_body))
        if cjk_spaces:
            h0 = cjk_spaces[0]
            add(W, "zh-cjk-space", f"中文词语间存在多余空格（{len(cjk_spaces)} 处）",
                zh_no_math_body[max(0, h0.start() - 15):h0.end() + 20])
        unlocalized_en = list(re.finditer(
            r"(?i:\bexternal\s+oracle\b|\boracle\s*=)|\b(?:Errors\s*/\s*n|min[–-]max|test-tuned|band\s+dropout|class-Mondrian|n\s+(?:target|calibration)|Pointing)\b|(?<![A-Za-z/])(?:px|alpha)(?![A-Za-z])|(?<![A-Za-z])(?:logits?|bootstrap|Count|True|False|energy)(?![A-Za-z])",
            zh_no_math,
        ))
        if unlocalized_en:
            h0 = unlocalized_en[0]
            add(W, "zh-unlocalized-english", f"中文稿保留未本地化英文词/表项（{len(unlocalized_en)} 处）",
                zh_clean[max(0, h0.start() - 15):h0.end() + 20])
    # numbers against Results
    if results_path and section in ("discussion", "introduction", "abstract"):
        extract_numbers = abstract_numbers if section == "abstract" else numbers
        res = set(extract_numbers(strip_md(Path(results_path).read_text(encoding="utf-8-sig"))))
        cand = [x for x in extract_numbers(claims) if re.search(r"[.%]", x)]
        miss = sorted({x for x in cand if x not in res and (section == "abstract" or x.lstrip("-") not in res)})
        if section == "introduction" and cand:
            add(W, "intro-number", f"引言出现小数或百分比，确认不是本研究结果：{cand[:10]}")
        elif miss:
            add(E, "number-not-in-results", f"Results 中找不到的数字：{miss}（他人文献数字须在核查说明注明出处）")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("section", choices=sorted(PROFILES))
    ap.add_argument("en")
    ap.add_argument("--zh")
    ap.add_argument("--results")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-words", type=int, default=250, help="Abstract body word limit (default 250)")
    ap.add_argument("--allow-abstract-references", action="store_true", help="Only when author/journal explicitly requires abstract references")
    ap.add_argument("--limits-json", type=Path, help="Explicit section min/max word limits; otherwise discover writing-limits.json beside PROJECT.md")
    a = ap.parse_args()
    if a.max_words < 1:
        ap.error("--max-words must be positive")
    res = check(a.section, a.en, a.zh, a.results, a.max_words, a.allow_abstract_references, a.limits_json)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for r in res:
            print(f"[{r['level']}] {r['rule']}: {r['msg']}" + (f"  …{r['context']}…" if r["context"] else ""))
        print(f"{sum(r['level'] == E for r in res)} error(s), {sum(r['level'] == W for r in res)} warning(s)")
    sys.exit(1 if any(r["level"] == E for r in res) else 0)


if __name__ == "__main__":
    main()
