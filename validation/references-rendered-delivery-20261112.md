# Rendered reference delivery validation — 2026-11-12

The former native-field construction stage deliberately retained source markers and an empty bibliography. Its preservation checks did not establish visible delivery completeness. The skill now distinguishes that intermediate stage from complete CSL caches, actual Word plugin Refresh, and author acceptance.

The new helper invokes an explicitly supplied installed citeproc-js, selected CSL style, and locale. It binds the plan to the source DOCX and resource hashes. Rendering retains native Zotero fields and item identities, adds CSL-generated numeric results and a complete bibliography, and verifies citation-to-bibliography correspondence. Restoring the original caches must reproduce the source XML; other package parts must remain byte-identical. No manuscript-specific item counts are required by production code.

## Validation

- Repository pytest: **975 passed, 9 warnings in 315.42s** (`python -X utf8 -m pytest -q -p no:cacheprovider` with explicit temporary directory).
- Legacy standalone reference suite: **76 tests, 0 failures, 0 errors** after the report-status change. Its I1–I9/I7a assertions were retained.
- New visible-delivery suite: **12 tests** included in pytest. Negative controls include unrendered markers, 53 cited sources with only four visible entries, incomplete plans, wrong numbers, wrong bibliography/title, changed prose, field-lock changes, stale plans, changed resources, and HTML block spacing.
- A local document regression used the installed CSL engine and original style; positive output and deliberately truncated four-entry output were independently checked. Private source text, Zotero metadata, CSL plans, and manuscripts are excluded from this repository.

## Limits

The supported renderer is for bracketed numeric styles and explicitly checked container structures; unsupported output fails. Synthetic plans in unit fixtures test the document checks, not the installed citation processor. Local file/API validation and a background Word file export do **not** establish that the Zotero Word plugin Refresh ran successfully, nor scientific reference support, journal acceptance, or author sign-off. No UI automation is needed for the visible-delivery gate.
