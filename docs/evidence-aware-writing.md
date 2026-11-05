# Evidence-preserving structural editing (0.10)

## Writing behavior

Abstracts select the research question, primary endpoint, core support and decisive counterexamples; the internal evidence table accounts for every analysis family and records omissions. Results use the information needed by the evidence, without a mandatory four-part paragraph or generic minimum length. Citation counts remain soft targets and explicit project targets are retained. Necessary limitations stay attached to their analyses, not repeated as automatic disclaimers.

Finalize reads the complete manuscript, resolves substantive narrative issues, and permits same-section merging, deduplication and reordering. It synchronizes corresponding ZH and existing EN_ZH versions. Unclear local evidence stays verbatim while unrelated editing continues; unresolved central contradictions block affected delivery. Promised or conclusion-relevant unfinished analyses remain scientifically disclosed; approvals and version histories belong in process records.

## New and legacy commands

Use the current skill's [structural review contract](../medical-sci-finalize/references/structural-review.md) for exact keys, spans, scope associations, manifests and examples. Stage a full copy of the manuscript tree outside its original directory, retaining unrelated author files byte-for-byte. Store review/process records outside both manuscript inventories.

```text
python -X utf8 medical-sci-finalize/scripts/check_finalize.py --edit-mode structural --before PROJECT/04_manuscript --after STAGE --review-json REVIEW --changes CHANGES --report REPORT
```

This mode requires source/candidate hashes, explicit scientific-unit/fact mappings, whole-manuscript narrative dispositions and actual bilingual coverage. `changes.json` and `decisions.json` are hash-bound transaction manifests in this mode; detailed prose changes are in review spans and the readable editing record. Apply only after checks pass, adding `--apply --project-root PROJECT --decisions DECISIONS --date YYYY-MM-DD`. It archives the whole affected language group and restores originals on an in-process write failure. A power/process crash across multiple file replacements is outside that rollback guarantee; archives remain available.

Without `--edit-mode structural`, existing strict comparison APIs and protected.json keep their previous behavior, including EN-only apply and old paragraph changes schema. Old records are not silently reinterpreted. Structural requests without complete matching records fail instead of falling back to token counts. Existing historical author decisions are preserved; a real conflict is reported rather than overwritten with a new default.

Author/journal limits can be declared using [writing-limits.json](../medpaper-pipeline/references/writing-limits.md). More than10% shortening does not automatically fail structural review. The legacy strict word band remains for old callers.

## Validation and installation

Synthetic tests cover legitimate merging, scope/fact mismatches, stale records, missing adverse evidence, bilingual coverage, archive/rollback, author limits and CLI compatibility. Word/table/math/citation regressions remain in the suite. Contextual scientific and narrative review is separate from deterministic validation: a schema, token or source-hash PASS does not prove arbitrary semantic equivalence, translation accuracy, scientific validity or author acceptance.

Install only reviewed changed skills with repeatable`--skill`; use explicit`--target`paths when multiple runtimes use different roots. Preview, back up and verify. Preserve local additions by reconciling them into reviewed source before installation; do not overwrite a local customization just because the default installer targets a different copy. No new runtime dependencies are required for this revision.

New source edits require fresh dependent assembly/reference checks and author acceptance. Existing formal manuscripts and their Word/Zotero fields are not automatically rewritten by installing these skills. Private manuscript excerpts and review records must stay outside the public repository.
