# Evidence-aware medical writing implementation plan

> Historical plan, archived in place. The local-installation gap below was closed for the earlier publication revision by `efa52a4`; its checkbox is retained as historical session state. Later rule and implementation changes require new verification. Current revision: see `docs/writing-scope-validation-20261117.md`.

> Execute the approved design task by task. Use inline execution for coupled integration and independent review before publication.

**Goal:** Permit evidence-preserving structural editing, synchronize bilingual manuscripts, and make narrative review actionable without replacing scientific validation with word counts.

**Architecture:** Keep existing skill routing and strict comparison APIs. Add an explicit structural comparison/apply mode backed by source-bound claim and review records. Separate deterministic checks from the editor's contextual review.

**Tech stack:** Existing Python standard library, python-docx, pytest and Markdown skills. No new dependencies.

## Constraints
- Default skill workflow permits same-section merging, deduplication and reordering; scientific facts, scope, adverse findings and citations remain attributable.
- Abstract selection prioritizes the research question, primary endpoint and decisive counterexamples; omitted secondary families are recorded internally.
- No universal minimum prose length. Author/journal limits govern; more than 10% shortening is reviewed for information coverage, not automatically rejected.
- Citation counts remain soft targets. Update ZH and existing EN_ZH after structural edits.
- Preserve unclear passages and proceed independently; unresolved central conflicts block affected delivery.
- Publicly disclose promised or conclusion-relevant unfinished analyses; retain internal approvals/version history in process records.
- Public tests use synthetic inputs. Existing formal manuscripts and analysis code are outside implementation scope.

## Task 1: Structural review and transaction
- [x] Add failing tests for valid qualifier merging, changed scope, stale source, missing adverse claim, malformed review, bilingual mismatch and rollback.
- [x] Implement `medical-sci-finalize/scripts/evidence_edit.py`, `compare_paths(before, after, review, changes=None)` and `apply_edit(before, after, review, changes, decisions, root, day)`.
- [x] Review records bind exact source/candidate content, claim identities and facts, source/candidate spans and explicit editorial decisions. Neither schema validation nor assertions of equivalence prove scientific truth.
- [x] Require actual bilingual coverage; preserve unchanged unknown passages. Validate every changed prose block and narrative issue disposition.
- [x] Retain old strict APIs; test unchanged behavior.

## Task 2: CLI and project-aware length integration
- [x] Test `check_finalize.py --edit-mode structural --review-json REVIEW` and legacy strict calls with real CLI processes.
- [x] Route structural mode to the new module only when explicitly selected; missing records are errors, never implicit fallback.
- [x] Test short evidence-complete Results without a universal minimum and explicit author limits.
- [x] Update `manuscript_check.py` length handling and pure lexical style diagnostics without weakening number/citation checks.

## Task 3: Skill instructions and examples
- [x] Update Abstract/Results/Introduction/Discussion/Legends/Methods shared contracts and Finalize instructions.
- [x] Remove competing whole-family, rigid paragraph, EN-only and ±10% default rules; preserve the old strict CLI as compatibility mode.
- [x] Document the exact review schema and executable commands; retain upstream licence/provenance.
- [x] Update pipeline state propagation and bilingual workflow; preserve local research-wiki integration.

## Task 4: Installation and validation
- [x] Test selective installation, backups and explicit targets; preserve existing default installer behavior.
- [x] Run affected tests, then repository regression including Word/table/math/reference tests.
- [x] Obtain independent spec and quality review; fix substantive findings and re-run affected tests.
- [x] Commit and synchronize the verified skill source to GitHub; do not publish private manuscript content. Implementation commit `527269f9f2ae60c2e912717d140c86e3279d91f1` is on `main`; full regression passed 1047 tests with 8 warnings, and the merged tree passed 79 core checks. See `docs/evidence-aware-writing-validation.md` for current and historical evidence.
- [ ] Separately verify synchronization of the corresponding installed skill directories and record their paths, backups and hashes. Earlier installation results are historical; this publication closeout did not repeat installation or verify current installed copies.
