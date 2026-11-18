# Source-bound structural review, schema 1

Use explicit `--edit-mode structural --review-json REVIEW`; the default strict mode retains its existing contract. Structural mode permits merging, deduplication and reordering inside the same file and heading scope. It requires retained unique facts, numerical results and confidence intervals, units, adverse findings, qualifiers, scope and provenance. It has no universal minimum word count or ±10% limit. Word counts never substitute for information coverage.

The checker validates deterministic constraints and records actual review passes. It cannot establish arbitrary prose equivalence, scientific truth, translation accuracy, completeness of a human-created fact inventory, independence of reviewers or author acceptance. The editor must identify **all** unique scientific facts, including verbal facts without numbers. Do not create a reviewer identity or scientific approval that did not occur. One actual person may perform multiple recorded passes.

## Inputs and file boundary

`before` and `after` are full manuscript directories with the same regular-file inventory. All existing `*_EN.md` files are managed, together with their corresponding existing `*_ZH.md` and `*_EN_ZH.md`. Other author files normally remain byte-identical and are never overwritten or archived unless an existing author decision file (`作者决定.md` or `*_作者决定.md`) is explicitly listed in optional `"append_only_author_files"` with strictly append-only non-empty UTF-8 additions (never rewritten or truncated). Unchanged managed files are still inventoried. New files and file removal are rejected. If an EN file lacks an existing ZH counterpart, the report explicitly warns that bilingual synchronization cannot be verified; no counterpart is fabricated. Existing counterparts require demonstrated span and fact coverage for affected claims.

Use UTF-8 without a BOM for JSON. Duplicate object keys, unknown schema keys, incorrect container types, booleans in integer fields, stale/malformed hashes, nonfinite JSON values, unsafe relative paths, symlinks and Windows reparse points fail closed. Hashes are lowercase SHA-256 of exact file **bytes**. Span offsets are zero-based Python Unicode character offsets into `bytes.decode('utf-8')`, with an exclusive end. CRLF characters count separately; do not calculate offsets from newline-normalized text.

Every `Span` is exactly:

```json
{"file":"Results/Results_EN.md","start":12,"end":20,"text":"cohort A"}
```

The text must equal the indicated slice. Paths use `/`, remain relative to the manuscript root, and contain no empty component, `.`, `..`, backslash or drive prefix. Every span refers to an inventoried managed file. `Span[]` below means a nonempty list of exact spans. An `AnchorPair` is exactly `{"source": Span, "candidate": Span}` with identical literal source/candidate text. Its spans must be inside their claim's enclosing spans.

## Exact review structure

Top-level optional keys are `author_limits`, `heading_edits`, `append_only_author_files`, `scope_declarations`, and `review_status`. Existing schema-1 records without the new fields retain mechanical comparison support with actual recorded identities. Generated reviewer placeholders are rejected even if `review_status` is removed. Apply additionally requires explicit reviewed verbal-fact inventory attestation before any archive or manuscript write. New scaffolds always include `review_status`; removing it does not constitute a review. Required lists may be empty only where explicitly described below.

```text
{
  "schema_version": 1,
  "reviewers": {"editor": string, "scientific": string, "bilingual": string},
  "inventory": {
    "relative/file_EN.md": {"source_sha256": SHA256, "candidate_sha256": SHA256},
    ... every managed EN/ZH/existing EN_ZH file exactly once ...
  },
  "claims": [Claim, ...],
  "unknowns": [Unknown, ...],
  "heading_edits": [HeadingEdit, ...],
  "append_only_author_files": ["作者决定.md"],
  "narrative": Narrative,
  "author_limits": {"relative/file_EN.md": {"min_words": positive_integer,
                                             "max_words": positive_integer}}
}
```

Each limit object has one or both keys; a maximum cannot be smaller than a minimum. Review limits are whole-file EN budgets (Abstract excludes Keywords/Highlights). They supplement, and cannot replace, declared project limits.

`Claim` is exactly:

```text
{
  "id": string,
  "reviewed_by": scientific_reviewer_identity,
  "source": Span[],
  "candidate": Span[],
  "scope": [{"axis": scope_axis, "source": Span, "candidate": Span}, ...],
  "facts": [Fact, ...],
  "provenance": [AnchorPair, ...],
  "translations": [Translation, ...]
}
```

The source and candidate spans must all belong to one EN file and one identical heading scope (matched by position and Markdown heading level). Section heading counts, hierarchy levels, and section order remain unchanged; wording calibration of existing titles or bilingual subtitles is permitted only via explicit `"heading_edits"` records (each mapped 1-to-1 by `section_id`, with corresponding ZH and EN_ZH coverage, retaining scientific owner labels and non-weakened numeric/qualifier evidence). Optional `"bilingual_sync_only": true` inside a heading edit allows fixing stale ZH/EN_ZH titles or subtitles while keeping the EN title identical. Split claims when sections, populations, endpoints, cohorts, analysis level or other scientific scope differ; do not use a whole-file claim to hide a scope swap. `scope_axis` is exactly one of `cohort`, `population`, `endpoint`, `analysis`, `run`, `subset`, `ci_owner`, `timepoint`, `unit`. Each axis occurs at most once per primary claim and its source/candidate anchor text is identical (except hyphenated numeric labels such as `seed-0` may canonicalize to `seed 0`). The anchors name the actual population/endpoint/analysis restrictions. `provenance` anchors preserve the manuscript's attribution, figure/table reference, citation or data-source wording. Both arrays are nonempty. Review the underlying scientific source independently; a literal anchor is not evidence that the source supports the claim.

`Fact` is exactly:

```text
{"id": string, "kind": "result|measurement|ci|unit|qualifier|citation|scope|method",
 "source": Span[], "candidate": Span[], "context": [FactContext, ...]}
```

`kind` is one of the displayed alternatives. Fact IDs are unique within a claim. The source/candidate sets of literal fact anchors must match (ignoring case shifts such as sentence-initial `Paired` ↔ `paired`), allowing repeated instances of the same fact to merge. When generating `review.json` after sentence reordering or citation movement/consolidation, use decimal- and abbreviation-safe sentence segmentation (never split `0.781` or `Fig.` on bare `.`) and emit **atomic** `facts` / `provenance` anchor pairs for every retained number, CI, qualifier, and moved/localized citation rather than relying only on contiguous diff blocks. Choose sufficiently informative anchors to preserve values **and** bindings, such as `AUC 0.82`, `95% CI [0.75, 0.89]`, `12 scans` or `no benefit`; isolated numbers alone cannot demonstrate which endpoint they describe. All known lexical numeric (with `seed-0` / `run-1` normalized identically to `seed 0` / `run 1`), counted-unit (`NUMBER + UNIT`), physical unit, citation (stopping at Chinese delimiters such as `）`/`。`/`，`), figure/table (normalizing EN `Fig./Table` and ZH `图/表/附图/附表/补充图/补充表`, and expanding single-letter panel ranges such as `Fig. 4c–e` / `附图 S8C、D`), operator, CI, inline math/code and URL evidence must match as unique sets across each claim; selected negative/qualifier tokens (`not`/`no`/`without`, `retrospective`, `exploratory`, `descriptive`, etc.) cannot be silently dropped from a claim or study-design bullet (the bounded existing `unresolved` to `not established` mapping remains, but `descriptive` to `not established` is rejected). Canonical qualifier sets must match: adding negation, exploratory status or a single-seed restriction is also rejected. Repetition counts are diagnostic, not scientific invariants; repeated same-state tokens may increase or shrink while unique scientific states and named seed ownership remain protected. This token list is deliberately conservative and is not an exhaustive scientific semantic parser.

`FactContext` is exactly `{"source": Span, "candidate": Span, "scope": [0, ...]}`. The nonempty `scope` list contains unique zero-based indices into this claim's `scope` array. Its contexts collectively cover every declared scope axis for that fact, and enclose all source/candidate fact occurrences. Each context contains its referenced owning scope text on the respective side. Context wording **may differ**: separate source contexts `Single-run analysis showed A.` and `Single-run analysis showed B.` can map to the shared candidate context `Single-run analysis showed A and B.` while atomic facts `A`, `B` and scope `Single-run` remain attributable. Source-context lexical evidence must remain in its candidate context; candidate contexts may include the other merged facts.

Explicit owner labels such as `Analysis A`, `分析A`, `cohort A`, `group B`, `endpoint X`, `seed 0` (including hyphenated numeric forms like `seed-0`), `队列A` and `终点B` receive conservative lexical checks. An EN claim cannot contain multiple owners on one recognized axis or leave a recognized owner unmapped. Local fact contexts cannot swap recognized labels or contain several conflicting owners on one axis. An ambiguous comparator passage can therefore require retaining the original or splitting the affected scientific unit while unrelated edits proceed. This detector recognizes a limited set of explicit labels; it does not infer arbitrary cohort names, ownership, comparator semantics or scientific scope from natural language. The review must still check those meanings. Contexts cannot be substituted with disconnected bags of unchanged numbers and scope labels.

`Translation` is exactly:

```text
{
  "language": "ZH|EN_ZH",
  "source": Span[], "candidate": Span[],
  "facts": [{"fact": corresponding_fact_id, "source": Span[], "candidate": Span[],
             "context": [FactContext, ...]}, ...],
  "scope": [AnchorPair, ...],
  "reviewed_by": bilingual_reviewer_identity,
  "rationale": string
}
```

There is exactly one translation record for each existing corresponding ZH and EN_ZH file, and no record for a nonexistent counterpart. Source and candidate spans stay in that corresponding file and heading scope. When editing a single section or long caption that mixes multiple scientific owners (e.g., `seed 0`, `seed 1`, and `seed 2` across different sentences of one table note), emit **paragraph- or sentence-level claims** covering only the edited sentence(s) rather than spanning the entire multi-owner section—never group separate `seed 0` / `seed 1` / `seed 2` sentences into a single `Claim`. When building `translation.facts`, emit exact matching anchors for **every** evidence token in both `translation.source` and `translation.candidate` (including tokens localized within Chinese files such as `Fig. 6A` ↔ `图 6A`, `Table 1` ↔ `表 1`, `seed-0` ↔ `种子0`, and `0.5 px` ↔ `0.5 像素`), and **never** overwrite mismatched spans with the bare section heading prefix. When a dense paragraph is split into multiple paragraphs (or merged), both the EN `Claim` and every `Translation` record for `ZH`/`EN_ZH` must include **all** resulting split blocks in `candidate` (`[para_1, ..., para_k]`) matching the full original `source` paragraph—never map split manuscripts by naive 1-to-1 paragraph index zip, which drops trailing split paragraphs and loses citations/numbers. Similarly, do not inject new Arabic numerals into spans that lacked them; the bounded prose ordinal `first`/`1st` equivalence is normalized separately and never masks endpoint values. Use a verified paragraph or analysis-group scope declaration when one applies, and mark only genuine scope transitions or exceptions; a repeated fixed qualifier is not a substitute for scope mapping. Each fact ID is covered exactly once. Its translated anchors remain literally unchanged within that language (or canonically equivalent under localized `Fig.`/`图`, `Table`/`表`, `seed`/`种子`, and `px`/`像素` formatting); numeric/citation/operator anchors also retain their language-independent values. Translation `scope` uses ordinary `AnchorPair` records without `axis`; its fact-context indices refer to this translation's scope array. Combined files use separate EN and ZH contexts referencing their respective language scope anchors, collectively covering all scope records and both language versions of each fact. Ordinary translations such as `12 scans` ↔ `12张扫描` are supported: translated unit/negative meaning must be checked by the recorded reviewer and explained in `rationale`. A boolean such as `bilingual_verified: true` is not a mapping. Existing combined files require coverage of both their EN and ZH text, rather than a link to just the Chinese half.

`Unknown` is exactly:

```text
{"id": string, "source": Span, "candidate": Span, "reason": string}
```

Unknown passages must retain identical original text and heading/file scope. Record the local uncertainty and proceed with unrelated edits. Do not replace unclear facts with guessed resolutions.

`Narrative` is exactly:

```text
{
  "reviewed_by": editor_reviewer_identity,
  "source": Span[], "candidate": Span[],
  "summary": string,
  "issues": [{
    "id": string, "kind": string,
    "source": Span[], "candidate": Span[],
    "decision": "resolved|retained|blocked", "central": boolean,
    "reviewed_by": editor_reviewer_identity, "reason": string
  }, ...]
}
```

The narrative spans demonstrate review of **every existing EN file in full**, including unchanged sections. Identify real narrative problems, their locations and their dispositions: disconnected logic, ambiguous referents, repetition, overclaiming, unsupported emphasis or a reviewed passage deliberately retained. Each changed EN prose block needs a located issue disposition; every changed managed prose block also needs claim/unknown coverage. Issue/claim/unknown IDs are unique across the review. There is no language-score threshold. A local `blocked` issue requires identical source/candidate wording and produces a warning. A central `blocked` issue prevents delivery. Review summaries and reasons are nonempty accounts of the actual review, not machine-generated certifications.

`claims` and `unknowns` can be empty when there are no changes requiring them; `narrative.issues` can be empty only when there are no changed EN blocks requiring dispositions. Lists required by a claim, fact, translation, issue or whole-manuscript narrative coverage are nonempty, except that `translations` is empty if neither counterpart exists.

## Change and decision manifests

For apply, both `--changes` and `--decisions` are JSON files with exactly the same small schema. They bind the complete review and its concrete dispositions; they do not use the legacy strict paragraph-log format:

```json
{"schema_version":1,"review_sha256":"64 lowercase SHA-256 characters","decisions":["N1","N2"]}
```

`review_sha256` hashes exact review JSON bytes. `decisions` lists **every** narrative issue ID exactly once, without unknown IDs or duplicates. Comparison optionally validates `--changes`; apply requires and validates both files. Keeping change and decision files separate permits separate process records even when their current contents coincide.

## Author limits

When comparing `PROJECT/04_manuscript`, the checker also reads existing `PROJECT/writing-limits.json`. Allowed section keys are exactly `abstract`, `methods`, `results`, `introduction`, `discussion`, `legends`; values have `min` and/or `max` positive integers. All objects are validated, including known sections absent from a partial manuscript tree. Existing matching sections are enforced. Unknown section keys fail closed. `legends` applies to each main/supplementary Figure caption in `*_Legends_EN.md`, excluding tables. Abstract counts exclude Keywords/Highlights. Counts match the existing Finalize word-count convention, including citation/panel-label exclusions. There is no implicit author limit when this file is absent.

## Commands and synthetic walkthrough

From the repository root, run the structural checker against an external stage. The paths below are illustrative. Synthetic fixtures and regression modules stay in the local development archive; this product tree does not include them, and they are not installed with the skill. A synthetic tree contains no manuscript data and does not assert a real scientific review:

Use the real interpreter as `python -X utf8`. Do not use a Windows Store `python.exe` stub.

```powershell
python -X utf8 medical-sci-finalize/scripts/check_finalize.py `
  --edit-mode structural --before E:\StructuralReviewDemo\project\04_manuscript `
  --after E:\StructuralReviewDemo\stage --review-json E:\StructuralReviewDemo\review.json `
  --changes E:\StructuralReviewDemo\changes.json --report E:\StructuralReviewDemo\comparison.json

python -X utf8 medical-sci-finalize/scripts/check_finalize.py `
  --edit-mode structural --apply --project-root E:\StructuralReviewDemo\project `
  --before E:\StructuralReviewDemo\project\04_manuscript --after E:\StructuralReviewDemo\stage `
  --review-json E:\StructuralReviewDemo\review.json --changes E:\StructuralReviewDemo\changes.json `
  --decisions E:\StructuralReviewDemo\decisions.json --date 2026-11-05 `
  --report E:\StructuralReviewDemo\applied.json
```

Apply requires `before = PROJECT/04_manuscript`, a nonoverlapping external stage, and a valid ISO archive day. Before replacement, it archives the **entire existing language group** for every changed group, including unchanged companions, under `PROJECT/_archive/DAY/04_manuscript/`. Archive collisions with differing content fail before manuscript writes. All replacement bytes are staged and verified before the first overwrite. Individual files use atomic replacement; an I/O failure restores replaced originals and reports rollback failures explicitly. Temporary replacements are removed. This is an in-process transaction, not a guarantee against a power/process crash across several files or hostile concurrent filesystem mutations. Inspect any reported rollback failure before proceeding.

Run `scripts/scaffold_structural_review.py` to generate exact UTF-8 character-offset `review.json`, `changes.json`, and `decisions.json` deterministically without hand-rolling ad-hoc offset builders:

```powershell
python -X utf8 medical-sci-finalize/scripts/scaffold_structural_review.py `
  --before <BEFORE_04_MANUSCRIPT> --after <AFTER_STAGE> `
  --review-json <REVIEW_JSON> --changes <CHANGES_JSON> --decisions <DECISIONS_JSON> `
  [--rationale-json <RATIONALE_JSON>] --verify
```

The scaffolder splits multi-owner paragraphs at sentence boundaries when possible, preserves unchanged multi-owner reference enumerations and unchanged single-newline captions verbatim via `unknowns`, maps `ZH`/`EN_ZH` facts (including `**English**`/`**中文对照**` markers and bold bilingual subtitles), and fails explicitly with exact token diffs if any numeric, unit, citation, qualifier, or scope invariant is broken. Supply actual per-section/per-heading reasons through `--rationale-json`; final verification requires the reviewed inventory inputs described below. With no review inputs, the output is a draft with placeholder identities and unresolved review work, and `--verify`/apply fail closed. When editing staged files programmatically on Windows, preserve original LF (`\n`) line endings (e.g., `newline='\n'` or binary UTF-8 writes) and existing heading/bold-subtitle adjacency so untouched headings are not flagged as changed blocks.

## Reviewed declarations and draft scaffolds

`non-inferential`, no inferential test/testing, no inferential comparison, no prespecified inferential threshold, `descriptive`, and `unestablished` remain distinct. A `non-inferential` label may be removed only when that same span still reports a permutation, sign-flip, or `P` comparison and no other inferential state is added. Removing the test, or replacing the label with a different state, still fails. Presence or absence of `prespecified` is preserved independently for inferential testing, comparison, ranking and threshold phrases. `did`/`do`/`does not` plus a short verb (`use`, `report`, `perform`, and the same closed list in the tokenizer) is the same state as `without`/`no` for that exact inferential phrase; it does not match `did not establish`, and it does not collapse different nouns. The spellings `non inferential`/`non-inferential` have bounded normalization. One evaluated run is a single state. Recognized spellings include `single evaluated seed`, `one evaluated run`, `single evaluated reader`, and the same pattern for a split, fold, or rater, together with 单种子 and 单次运行. A seed phrase is one spelling of that state. Prose `first`/`1st` have bounded normalization. `first` is an ordinal token, never an ignored number: changing `1st` to `2nd` or changing an endpoint value still fails. A standalone Chinese `组120` is an owner; `入组120只眼` is enrollment prose rather than a new group.

A same-heading claim may include an earlier governing paragraph whose candidate text still states the same single evaluated run (or states a single explicit named run such as `seed 0` when the following paragraph drops a repeated `in the same single evaluated seed` phrase). When one or more later hunks under the same heading lose that repeated single-run token (including when a hunk also drops a contradicted `non-inferential` label in a paragraph reporting its permutation/sign-flip/`P` test), keep compatible explicit owners, and do not add evidence, the scaffold folds those hunks into the governing paragraph across any intervening compatible paragraphs in that same heading. It stops at a conflicting owner (such as `Analysis B` vs `Analysis A` or `seed 1` vs `seed 0`). This is a **draft proposal**, not an inferred scientific certification. A repeated single-run occurrence inside one paragraph may be removed while another occurrence of that same state remains; it is not paired with a different qualifier such as `paired` or `CI`. Moving that phrase from the start of a sentence to after the subject does not remove it. Adding `Supplementary` before an existing `Fig.` or `Table` with the same number keeps that citation. A translation fact binds all occurrences of that fact's source state or candidate state (including a reviewed change such as `unresolved` to `not established`) without absorbing a different state such as `CI`. An unused extra source occurrence of the same state does not need its own fact. An unchanged qualifier that appears on both sides of a translation but not in the English facts, such as 单种子 beside “seed-specific”, is anchored on a non-qualifier fact so a spacing edit does not drop it. A newly consolidated Results declaration is supported when the source qualifiers and all governed values fit one explicit same-heading claim: for example, two source paragraphs beginning `In the single evaluated seed, Analysis A ...` can map to one new declaration followed by the two retained result paragraphs. The reviewer inventories that complete source/candidate claim. Different `Analysis A`/`Analysis B` owners cannot inherit one another's scope.

Cross-file inheritance uses optional `scope_declarations`. Each record has exactly `id`, `reviewed_by`, `rationale`, `source`, `candidate`, `bindings`. Its source/candidate declaration spans must be unchanged in one inventoried file. Each binding has exactly `claim`, `language`, `source`, `candidate`, `removed`, `guards`; governed source/candidate span lists must exactly equal the named claim or translation. `removed` contains only exact source spans of that single-run state. Each guard is `{axis, text}`; the literal text must occur in both declaration and governed text. Require an owning `analysis`/`cohort`/`population`, an endpoint, every local named owner/seed, and every relevant physical unit. A named run guard may additionally use `"location":"declaration"` when a local clause refers to the reviewed single evaluated run without repeating its identifier. Local conflicting identifiers still fail. No other guard can use that location.

Declarations must affirm the scope. Negated or exclusionary statements, including Chinese cues such as `未`/`不`/`无` and English `not only`, cannot govern removal; choose a shorter affirmative, source-supported span or retain the local qualifier. Declarations are limited to an earlier paragraph under the same heading or an inventoried `Methods_<LANG>.md` → `Results_<LANG>.md` mapping. They must explicitly state one evaluated run in any recognized spelling **or exactly one named run**, such as `seed 0`; multiple competing identities or seed ranges fail. A named-run declaration requires its exact run guard and reviewed source single-run qualifier mapping. A reference to `seed 0` is not globally normalized into the single-run state. Existing ZH and EN_ZH companions require their own exact declaration bindings, even if their declaration text is unchanged. All declaration and governed spans are bound to the inventory's source/candidate SHA-256 hashes. Only the explicitly mapped source qualifier slots participate in inheritance; numbers, CI, negation, units, endpoint and owner checks remain active. The declaration records themselves are the qualifier mapping; ordinary fact anchors remain inside their original claims.

The scaffold accepts selectors through `scope_declaration_requests` in the rationale file. The official `resolve_exact_span(texts, selector)` helper resolves `{file, text}` only when it matches uniquely, or `{file, text, occurrence}` with an explicit zero-based occurrence. Existing full `Span` objects are validated without re-anchoring. Requests become exact offset records in `review.json`, with `claim` automatically resolved from the exact governed spans. For example, this **synthetic** request maps the same source qualifier to an unchanged Methods seed declaration without manually computing offsets:

```json
{
  "scope_declaration_requests": [{
    "id": "D_EN", "reviewed_by": "Actual reviewer identity",
    "rationale": "Explain the source-supported owner, endpoint and seed binding.",
    "declaration": {"file":"Methods_EN.md", "text":"Analysis A used seed 0 once for MAE measured in px."},
    "bindings": [{
      "language":"EN",
      "source":[{"file":"Results_EN.md", "text":"In the single evaluated seed, Analysis A had MAE 0.72 px."}],
      "candidate":[{"file":"Results_EN.md", "text":"Analysis A had MAE 0.72 px."}],
      "removed":[{"file":"Results_EN.md", "text":"single evaluated seed"}],
      "guards":[{"axis":"analysis","text":"Analysis A"}, {"axis":"endpoint","text":"MAE"},
                {"axis":"unit","text":"px"}, {"axis":"run","text":"seed 0","location":"declaration"}]
    }]
  }]
}
```

For final verification, the rationale file also supplies actual `reviewers` for all three roles, `narrative_summary`, actual `issues` dispositions/reasons, and `inventory_review`:

```json
{
  "reviewers":{"editor":"structural editor","scientific":"structural editor","bilingual":"structural editor"},
  "narrative_summary":"Describe the actual whole-manuscript review and its limits.",
  "issues":{"default":{"decision":"resolved","reason":"Explain the edits actually reviewed."}},
  "inventory_review":{
    "reviewed_by":"structural editor",
    "rationale":"Explain the actual review of every unique verbal fact, including adverse findings.",
    "facts":[{"source":[{"file":"Results_EN.md","text":"Exact source verbal finding."}],
              "candidate":[{"file":"Results_EN.md","text":"Exact retained candidate verbal finding."}],
              "reason":"Explain why this unique fact is retained, or where a duplicate is retained."}]
  }
}
```

Use one or more fact mappings for every changed claim; optional `claim` IDs may be supplied, otherwise exact containment resolves the claim. Inventory the actual distinct verbal findings, rather than using numbers alone. New `review_status` records contain `state`, `reviewed_by`, `rationale`, `facts`; only `state:"reviewed"` with supplied nonplaceholder identities, rationale and explicit per-claim inventory passes. The checker rejects the placeholder names `DRAFT - reviewer required`, `scientific editor`, `scientific reviewer`, and `bilingual reviewer`. For this structural edit, name the editing pass in all three reviewer roles, then supply `inventory_review.facts` for every changed claim and rerun `--verify`. That record means the editor read and retained those sentences. It does not establish an independent referee, translation accuracy, scientific validity, or author acceptance. Do not run `--verify` before the candidate differs from the source. Zero claims on an unchanged tree means the edit has not started. Do not revert the candidate and stop when the first scaffold reports a placeholder identity.

If a source assertion is scientifically inaccurate—for example, calling an analysis `non-inferential` despite an actual inferential test—correcting it is a factual correction, not stylistic equivalence. Freeze a separate source-correction record with source evidence, exact before/after spans and hashes, and actual independent scientific review; then create a separately identified corrected baseline. Apply the style gate from that corrected baseline. Do not rewrite or relabel the original baseline, and do not claim scientific equivalence from the original assertion to the final text. No declaration record bypasses this distinction.

Preserve original LF/CRLF bytes while staging. A newline-convention change produces an early actionable error; regenerate the staged files with original newline bytes and then generate fresh exact span records. Offsets are never silently normalized.

Regression modules for this checker stay in the local development archive. They are not part of the product repository or the installed skill. An archive run does not replace manuscript review.
