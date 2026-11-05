# Structural writing revision: validation record

Date: 2026-11-05. Scope: the writing rules, explicit structural-edit CLI/transaction, project word limits, compatibility and selective installation. No formal manuscript was automatically rewritten.

## Executed checks

Windows, Python3.12.7, existing environment; no new dependencies installed.

| Check | Observed result |
|---|---|
| Repository pytest (`python -X utf8 -m pytest -q -p no:cacheprovider`) | 951 passed;8 warnings |
| Final affected skill, structural/CLI, word-policy and legacy-Finalize checks | 183 passed |
| Independent final structural/CLI and word-policy review run | 38 passed; no remaining substantive findings |
| Skill quick validation | All8 affected skills valid |
| Installer regression | 20 passed, including selective install/verify/uninstall and preservation of unrelated directories |
| Whitespace/diff check | Clean |

Warnings concern existing environment deprecation and the gallery layout engine; none is treated as evidence of scientific validation. The targeted final run covers the scoped fixes reviewed after the broad run began. Tests use synthetic files; private manuscript text and process records are excluded from the public fixtures.

The regression work observed failures before implementing: removed generic minima, explicit author-limit enforcement, lexical diagnostic severity, missing structural CLI, selective installation, fabricated assembly decisions, assembly word minima, natural Chinese measurements, and scope-owner association. Independent review reproduced a fresh-record mixed-cohort reassignment, which now fails while actual same-run conjunction merging passes. Single-run AUROC/CI does not falsely become a named run owner.

## Boundaries

Exact spans, hashes, scope axes, fact contexts, lexical-owner checks and review manifests are useful integrity checks. They do not prove arbitrary scientific meaning, exhaustive verbal-fact coverage or translation correctness. Contextual scientific/bilingual/narrative review and author acceptance remain distinct. Owner recognition is deliberately conservative and covers explicit labelled owners, not arbitrary medical terminology.

Transaction tests cover whole affected-language-group archival, stale records, path/reparse rejection and injected in-process write failure. They do not establish crash consistency across multi-file power/process failure or hostile concurrent mutation. Existing strict-call compatibility, Word/table/math/citation behavior and historical licence/source text are preserved.
