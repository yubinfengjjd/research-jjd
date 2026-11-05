# Source-bound structural review, schema 1

Use explicit `--edit-mode structural --review-json REVIEW`; the default strict mode retains its existing contract. Structural mode permits merging, deduplication and reordering inside the same file and heading scope. It requires retained unique facts, numerical results and confidence intervals, units, adverse findings, qualifiers, scope and provenance. It has no universal minimum word count or ±10% limit. Word counts never substitute for information coverage.

The checker validates deterministic constraints and records actual review passes. It cannot establish arbitrary prose equivalence, scientific truth, translation accuracy, completeness of a human-created fact inventory, independence of reviewers or author acceptance. The editor must identify **all** unique scientific facts, including verbal facts without numbers. Do not create a reviewer identity or scientific approval that did not occur. One actual person may perform multiple recorded passes.

## Inputs and file boundary

`before` and `after` are full manuscript directories with the same regular-file inventory. All existing `*_EN.md` files are managed, together with their corresponding existing `*_ZH.md` and `*_EN_ZH.md`. Other author files must remain byte-identical and are never overwritten or archived by this mode. Unchanged managed files are still inventoried. New files and file removal are rejected. If an EN file lacks an existing ZH counterpart, the report explicitly warns that bilingual synchronization cannot be verified; no counterpart is fabricated. Existing counterparts require demonstrated span and fact coverage for affected claims.

Use UTF-8 without a BOM for JSON. Duplicate object keys, unknown schema keys, incorrect container types, booleans in integer fields, stale/malformed hashes, nonfinite JSON values, unsafe relative paths, symlinks and Windows reparse points fail closed. Hashes are lowercase SHA-256 of exact file **bytes**. Span offsets are zero-based Python Unicode character offsets into `bytes.decode('utf-8')`, with an exclusive end. CRLF characters count separately; do not calculate offsets from newline-normalized text.

Every `Span` is exactly:

```json
{"file":"Results/Results_EN.md","start":12,"end":20,"text":"cohort A"}
```

The text must equal the indicated slice. Paths use `/`, remain relative to the manuscript root, and contain no empty component, `.`, `..`, backslash or drive prefix. Every span refers to an inventoried managed file. `Span[]` below means a nonempty list of exact spans. An `AnchorPair` is exactly `{"source": Span, "candidate": Span}` with identical literal source/candidate text. Its spans must be inside their claim's enclosing spans.

## Exact review structure

Only `author_limits` is optional at the top level. Required lists may be empty only where explicitly described below.

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

The source and candidate spans must all belong to one EN file and one identical heading scope. Section headings and their order remain unchanged. Split claims when sections, populations, endpoints, cohorts, analysis level or other scientific scope differ; do not use a whole-file claim to hide a scope swap. `scope_axis` is exactly one of `cohort`, `population`, `endpoint`, `analysis`, `run`, `subset`, `ci_owner`, `timepoint`, `unit`. Each axis occurs at most once per primary claim and its source/candidate anchor text is identical. The anchors name the actual population/endpoint/analysis restrictions. `provenance` anchors preserve the manuscript's attribution, figure/table reference, citation or data-source wording. Both arrays are nonempty. Review the underlying scientific source independently; a literal anchor is not evidence that the source supports the claim.

`Fact` is exactly:

```text
{"id": string, "kind": "result|measurement|ci|unit|qualifier|citation|scope|method",
 "source": Span[], "candidate": Span[], "context": [FactContext, ...]}
```

`kind` is one of the displayed alternatives. Fact IDs are unique within a claim. The source/candidate sets of literal fact anchors must match exactly, allowing repeated instances of the same fact to merge. Choose sufficiently informative anchors to preserve values **and** bindings, such as `AUC 0.82`, `95% CI [0.75, 0.89]`, `12 scans` or `no benefit`; isolated numbers alone cannot demonstrate which endpoint they describe. All known lexical numeric, measurement, unit, citation, figure/table, operator, CI, selected negative/qualifier, inline math/code and URL evidence must be retained within each claim and explicitly covered by fact, scope or provenance anchors. Repeated token counts may shrink; unique token sets may not. This token list is deliberately conservative and is not an exhaustive scientific semantic parser.

`FactContext` is exactly `{"source": Span, "candidate": Span, "scope": [0, ...]}`. The nonempty `scope` list contains unique zero-based indices into this claim's `scope` array. Its contexts collectively cover every declared scope axis for that fact, and enclose all source/candidate fact occurrences. Each context contains its referenced owning scope text on the respective side. Context wording **may differ**: separate source contexts `Single-run analysis showed A.` and `Single-run analysis showed B.` can map to the shared candidate context `Single-run analysis showed A and B.` while atomic facts `A`, `B` and scope `Single-run` remain attributable. Source-context lexical evidence must remain in its candidate context; candidate contexts may include the other merged facts.

Explicit owner labels such as `cohort A`, `group B`, `endpoint X`, `seed 0`, `队列A` and `终点B` receive conservative lexical checks. An EN claim cannot contain multiple owners on one recognized axis or leave a recognized owner unmapped. Local fact contexts cannot swap recognized labels or contain several conflicting owners on one axis. An ambiguous comparator passage can therefore require retaining the original or splitting the affected scientific unit while unrelated edits proceed. This detector recognizes a limited set of explicit labels; it does not infer arbitrary cohort names, ownership, comparator semantics or scientific scope from natural language. The review must still check those meanings. Contexts cannot be substituted with disconnected bags of unchanged numbers and scope labels.

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

There is exactly one translation record for each existing corresponding ZH and EN_ZH file, and no record for a nonexistent counterpart. Source and candidate spans stay in that corresponding file and heading scope. Each fact ID is covered exactly once. Its translated anchors remain literally unchanged within that language; numeric/citation/operator anchors also retain their language-independent values. Translation `scope` uses ordinary `AnchorPair` records without `axis`; its fact-context indices refer to this translation's scope array. Combined files use separate EN and ZH contexts referencing their respective language scope anchors, collectively covering all scope records and both language versions of each fact. Ordinary translations such as `12 scans` ↔ `12张扫描` are supported: translated unit/negative meaning must be checked by the recorded reviewer and explained in `rationale`. A boolean such as `bilingual_verified: true` is not a mapping. Existing combined files require coverage of both their EN and ZH text, rather than a link to just the Chinese half.

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

From the skill repository root in PowerShell, create a **new synthetic demo** using the public test fixture. The demo contains no actual manuscript data and does not assert a real scientific review:

```powershell
@'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('medical-sci-finalize/scripts').resolve()))
from test_evidence_edit import fixture
demo = Path(r'E:\StructuralReviewDemo')
demo.mkdir()  # fail if already present; do not overwrite prior work
fixture(demo)
'@ | & D:\anaconda\python.exe -X utf8 -

& D:\anaconda\python.exe -X utf8 medical-sci-finalize/scripts/check_finalize.py `
  --edit-mode structural --before E:\StructuralReviewDemo\project\04_manuscript `
  --after E:\StructuralReviewDemo\stage --review-json E:\StructuralReviewDemo\review.json `
  --changes E:\StructuralReviewDemo\changes.json --report E:\StructuralReviewDemo\comparison.json

& D:\anaconda\python.exe -X utf8 medical-sci-finalize/scripts/check_finalize.py `
  --edit-mode structural --apply --project-root E:\StructuralReviewDemo\project `
  --before E:\StructuralReviewDemo\project\04_manuscript --after E:\StructuralReviewDemo\stage `
  --review-json E:\StructuralReviewDemo\review.json --changes E:\StructuralReviewDemo\changes.json `
  --decisions E:\StructuralReviewDemo\decisions.json --date 2026-11-05 `
  --report E:\StructuralReviewDemo\applied.json
```

Apply requires `before = PROJECT/04_manuscript`, a nonoverlapping external stage, and a valid ISO archive day. Before replacement, it archives the **entire existing language group** for every changed group, including unchanged companions, under `PROJECT/_archive/DAY/04_manuscript/`. Archive collisions with differing content fail before manuscript writes. All replacement bytes are staged and verified before the first overwrite. Individual files use atomic replacement; an I/O failure restores replaced originals and reports rollback failures explicitly. Temporary replacements are removed. This is an in-process transaction, not a guarantee against a power/process crash across several files or hostile concurrent filesystem mutations. Inspect any reported rollback failure before proceeding.

Run the public regression tests from `medical-sci-finalize/scripts`:

```powershell
& D:\anaconda\python.exe -X utf8 -m unittest test_evidence_edit -v
```
