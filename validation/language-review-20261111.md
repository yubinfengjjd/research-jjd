# Version-bound language-review follow-up

An external review described an earlier repository commit and manuscript. Later reviewed candidates already addressed most quoted examples, but those candidates had not been promoted into the project's current source directory. A quoted defect must therefore be checked against the current source and candidate before another edit.

This patch adds a version-binding step to Finalize and aligns the Abstract checker's human-review guidance with the existing evidence-prioritization policy. The checker previously still instructed the editor to include every analysis family in the abstract. That instruction contradicted the active writing rules even though it was not an automatic error condition.

The editing and evidence-mapping engine is unchanged. The new policy regressions protect the entry-point link, review-version dispositions, and the Abstract checker's guidance. These tests verify rule consistency, not prose quality, scientific equivalence, or authorship.

The local manuscript review separately inspected redundant result summaries, citation roles, publication-boundary language, scope of adverse findings, and EN/ZH/combined correspondence. A second review identified important adverse findings that needed restoration to the abstract, plus ambiguity between binary abstention and three-class coverage. Those points were addressed in the final local candidate. Private manuscript text and data are not included in this repository.

Validation receipts and limits:

- Final repository suite: 182 passed in 128.00s; exit code 0. Earlier 181-test runs are superseded, not added to this count.
- The local candidate passed the section and abstract checks with explained style warnings. Text-quality judgments remain bounded editorial assessments.
- No claim is made that a source-bound structural-edit certificate was generated for the complete historical-to-current manuscript change. Prior stress-test records are historical evidence, not a substitute for such a certificate.
- Existing publication uncertainty, unresolved project decisions, and the need for author review are retained. Word files require rebuilding after source promotion.
