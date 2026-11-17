# Evidence scope and prose diagnostics

This revision responds to a complete audit of the medical writing chain. It separates scientific evidence ownership, editorial judgment and mechanical diagnostics. Publication of this code does not constitute manuscript, clinical or author acceptance.

## Intended behavior

- State a shared analysis scope where it governs the relevant claims, then label changes and exceptions. Abstracts and independently read figures/tables retain enough local context. A global statement must not silently cover a different endpoint, cohort, seed or inference.
- Preserve numerical and verbal findings, unfavorable results, estimation units and uncertainty. Word-frequency budgets never authorize deleting scientific information.
- Organize paragraphs around a supported finding; use literature according to its argumentative role. A concise direct negative finding is useful when accurate, while an inconclusive test must retain its uncertainty.
- Use word counts, sentence length, citation density and repeated phrases to find passages for review. There is no universal requirement to reduce the density, use one qualifier, cite a figure only at paragraph ends, or use a prescribed number of references per paragraph.
- Automatic evidence records are scaffolding. They cannot certify that a person reviewed all verbal facts or translations.

The structural checker implements a bounded single-seed inheritance contract, not a general semantic scope solver. It supports reviewed same-heading consolidation and explicit unchanged Methods-to-Results declarations, with exact spans, hashes, owning analysis/endpoint/unit guards and language bindings. Other scope changes require substantive review; a scientifically incorrect baseline requires a separately documented source correction, not a convenient token equivalence. Existing schema-1 comparisons remain readable, while promotion requires an actual reviewed verbal inventory. The detailed rationale selectors and contract are maintained in `medical-sci-finalize/references/structural-review.md`.

Inferential testing, prespecification, descriptive estimation and a test's conclusion are distinct states. Protected qualifiers may neither be added nor removed through an unreviewed paraphrase. Repeating the same state more often is a prose diagnostic, not a scientific pass/fail count.

## Read-only cross-version diagnostics

```text
python medpaper-pipeline/scripts/lint_manuscript.py CANDIDATE/04_manuscript --previous BEFORE/04_manuscript --report PROCESS/prose-comparison.json
python medpaper-pipeline/scripts/lint_manuscript.py manuscript_v23.docx --previous manuscript_v22.docx --allow-term "a genuine technical expression" --report PROCESS/docx-comparison.json
```

Directory input selects `*_EN.md` sources, excluding bilingual combined files and verification notes. DOCX input reads top-level visible paragraphs through the bibliography boundary; it excludes tables. Compare like inputs and distinguish embedded legends from Results prose. JSON records the extraction method, input identities, per-sentence/paragraph metrics, 3–5 word n-grams and lexical family densities. The families include discourse terms; their combined count is not a count of semantic hedges.

Default phrase review starts at nine occurrences. Growth greater than threefold is reported only with enough current occurrences to avoid zero-to-one noise. Technical expressions can be annotated with `--allow-term`. These are review prompts, never a linguistic acceptance score. Exit 0 includes diagnostics; exit 1 indicates unreadable/invalid input or an unsafe output location. Reports cannot overwrite or be written into either manuscript input tree.

## Verification record

Implementation, source tests, selective installation, installed-file checks, independent review and manuscript blind testing are separate evidence. Historical plans and results are not fresh evidence for this revision. Private manuscripts, model transcripts, Zotero snapshots and render plans remain outside the repository.

Local verification on 2026-11-17:

- Repository pytest suite: 1090 passed, 9 dependency/layout warnings (579.14 s). The last bounded lexical and message refinements landed during that run; the final affected engine/policy/language tests were rerun afterward (110 passed, then 62 passed after adding contraction cases). These counts overlap and must not be added.
- Independent final evidence/scaffold/heading/lint/policy/language review: 109 passed; the original and newly discovered adversarial cases reject unsafe scope/negation changes. Open P0/P1/P2 in the explicitly reviewed code scope: zero. This was a targeted independent acceptance review, not equal-depth review of every repository file.
- Separate managed-experiment regressions: 134 passed; package resource/link check valid. Separate portable replica checks: 47 passed. No real-data experiment or clinical validation is inferred.
- Ten related skill entrypoints passed skill-creator's metadata validation. This checks structure, not writing quality.

The published commit's CI, installed-file receipts, fresh manuscript blind edit, bilingual/source review, rendered Word inspection and author acceptance retain their own status. Code publication does not imply those manuscript gates have passed.
