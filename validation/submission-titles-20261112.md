# Submission title workflow validation — 2026-11-12

The submission stage previously covered title-page preparation without an explicit title-review and selection workflow. The updated skill first reviews an existing title and retains it when appropriate. Missing titles, substantive issues or an author request trigger a default of three English candidates with Chinese counterparts, evidence boundaries and recommendation reasons. Changed titles require actual author selection or explicit delegated selection before synchronization to new submission copies.

The workflow separates scientific meaning, currently applicable journal/reporting rules, candidate recommendation, author selection, and actual file synchronization. Unknown journal requirements remain unresolved; short titles are conditional. Source manuscripts remain unchanged. The new read-only `submission_guard.py titles` command reads explicit locations in the actual deliverable allowlist, checks declared limits and decision-record completeness, and reports artifact hashes. It never declares submission readiness or authenticates scientific judgments or author identity.

## Executed validation

- Repository pytest: **996 passed, 9 warnings in 291.75s**. The warnings concern existing plotting/runtime behavior.
- Title and existing submission suites: **63 passed**, including **21 new title cases**. Initial feature tests failed before implementation. A further real-whitespace counterexample failed, then passed after checking actual located fragments.
- Cases cover retained titles and source immutability, missing/placeholders, a title found in the wrong paragraph, an omitted cover letter, recommendation versus selection/delegation records, unavailable rules, full/short limits, absence of invented universal limits, real whitespace, visible versus metadata-only titles, unsafe paths, and CLI exit states.
- An independent agent received only the skill and three isolated synthetic requests, without the expected answers. Parent review confirmed that it retained a suitable title, provided three bilingual alternatives for unsupported clinical/generalization claims without selecting one, and flagged a locked randomized-trial title contradicting retrospective methods while leaving the author's locked title unchanged. It accurately distinguished unknown journal rules and excerpt-only review from full manuscript verification. This is a bounded forward-test, not proof of universal narrative quality.
- Both skill entrypoints passed skill-creator validation. Installed Codex CLI positive/negative artifact checks passed after synchronization; all three local host copies were backed up and hash-verified.

## Limits

Title meaning, actual source authority, current reporting-rule applicability, genuine author authorization and unlisted title occurrences still require review. The mechanical checker supports located DOCX/MD/TXT text and declared whitespace/codepoint counting; other formats or official counting methods need separate evidence. Existing field-preservation checks remain independent. No private manuscripts, author information, Zotero data or source evidence are included in this public validation note. No manuscript title was selected or changed in the real project during skill maintenance.
