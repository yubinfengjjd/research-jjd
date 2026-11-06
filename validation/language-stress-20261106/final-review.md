# Evidence-first language regression review

Baseline: 65ba5ac8. Claude Code used configured deepseek-flash backend; after its balance failure, local Devin ACP used swe-2-max. First-round semantic self-assessment was rejected; later rounds corrected scope loss, invented material, incomplete cleanup, stale assembled output and stale checking snapshots. Final manuscript remained unchanged through two independent review passes; a final rule-only pass found no remaining conflicting paragraph-ending requirements.

Evidence locally retained: 17 case re-evaluations, four positive/negative variant pairs (small-count translation, seed index vs sample count, CI envelope vs pooled CI, stale assembled output), final-source/output SHA bindings, section checks and 8-case regression tests. These bounded checks do not establish general semantic equivalence or scientific validity. The real manuscript and private excerpts are not included in this public repository.

Remaining diagnostic warnings are recorded locally. New policy tests check contradictions only, not prose quality. Previous 171 and 104 test runs were distinct suite runs; do not present their sum as a deduplicated semantic acceptance score.

Final repository suite: `D:/anaconda/python.exe -X utf8 -m pytest tests -q -p no:cacheprovider` returned exit 0: 175 passed in 142.06s.
