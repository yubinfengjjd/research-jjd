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

## Historical continuation record (2026-11-14)

The earlier local continuation record reported `1019 passed, 8 warnings` in Windows Python 3.12, alongside independent-review runs of 85 structural/finalize tests, 255 root/finalize tests and 244 installer/skill/outline/pipeline tests. It also reported 8 selective-install tests for Methods/Legends and a clean diff check apart from Git's LF-to-CRLF notice. These are historical results from that revision, not fresh review or acceptance of the later changes.

## Verified source publication (2026-11-16)

Implementation commit: `527269f9f2ae60c2e912717d140c86e3279d91f1`, published on GitHub `main`. Its scope includes structural-review scaffolding, localized evidence anchors, owner-binding checks, writing diagnostics and regression tests. Private manuscripts and process artifacts are not included.

| Check | Observed result |
|---|---|
| Worktree repository pytest (`D:\anaconda\python.exe -X utf8 -m pytest -q -p no:cacheprovider`) | 1047 passed; 8 warnings; 671.10 seconds |
| Core checks after fast-forward merge (evidence edits, headings, scaffolding, writing policy and language contracts) | 79 passed; 6.50 seconds |
| Merged tree comparison | `main` and the tested feature commit had identical Git tree hashes |
| GitHub `tests` and `Windows experiment controller` workflows | Both succeeded for the implementation commit on `main` and the feature branch |
| Local skill installation | Not repeated or re-verified during this publication closeout |

The eight local warnings comprise one Jupyter path-deprecation warning and seven gallery layout warnings. Test results and publication do not establish scientific validity, translation equivalence, Word/Zotero acceptance or a fresh independent manuscript review. The historical validation results above remain separate from this verified source revision.

## Installation verification closeout (2026-11-17)

The publication closeout re-ran local installation verification after the source tree advanced to `8a1b32e`:

| Check | Observed result |
|---|---|
| `D:\anaconda\python.exe -X utf8 install.py --update` | Updated the stale `anti-defensive-writing` and `medical-sci-finalize` trees in both `.claude\skills` and `.codex\skills`; four backups were created under `C:\Users\86186\skill_backups\medfig_20261117_000144` |
| `D:\anaconda\python.exe -X utf8 install.py --verify` | 23/23 skills `ok` in both target roots |
| `D:\anaconda\python.exe -X utf8 -m pytest tests/test_install.py -q -p no:cacheprovider` | 31 passed in 465.63 seconds |

This closes the previously recorded local-installation verification gap. It does not change the separate manuscript boundaries: Word/Zotero author acceptance and scientific validation remain distinct.
