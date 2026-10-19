# Medical SCI submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add an evidence-grounded journal-adaptation skill and integrate it as pipeline stage 13, with an independent standalone entry.

**Architecture:** The agent reads current official journal rules and performs the author interview and document adaptation. Focused instructions and references define decisions; small deterministic helpers protect DOCX field identity and honest handoff/status. Reuse existing writing/reference skills and installer code rather than creating parallel systems.

**Tech Stack:** Markdown/YAML, Python 3.10+ stdlib and the suite's existing DOCX/lxml dependencies where appropriate, pytest. Use the real configured Python interpreter in this Windows environment.

**Spec:** `docs/superpowers/specs/2026-10-19-medical-sci-submission-design.md` (binding author-approved contract).

## Global constraints

- Implement only in the assigned isolated repository, never in installed skills or the source checkout.
- Source manuscripts and clinical inputs are immutable; only synthetic fixtures are used.
- The controller performs review, blind testing, source integration and three-root deployment. Worker must not install or push.
- New skill name: `medical-sci-submission`; stage: 13; clean deliverables: `06_submission/<journal>/<version>/`; process: `_process/Submission/`.
- Do not require preceding research stages for standalone manuscripts; no invented PROJECT or clinical facts.
- Ordinary formatting may proceed; substantive edits require concrete author approval.
- Missing required evidence means draft/pending, never automatically confirmed or ready.
- Current official sources with provenance; no fixed-journal assumptions.
- Preserve complex Zotero fields/identities and real source data; a generic marker-only validator is not final-field validation.
- No remote publication or real Zotero library writes in development/tests.

## Task 1: Integrated skill addition

**Files:**
- Create `medical-sci-submission/SKILL.md`, `agents/openai.yaml`, and only supporting `references/`, `scripts/`, templates justified by the spec.
- Modify `medpaper-pipeline/SKILL.md`, `references/project-layout.md` and relevant routing/status guidance.
- Modify `install.py`, `README.md`, `tests/test_skills.py` and focused new tests; adjust CI documentation only when needed.
- Existing reference/finalization implementations are not rewritten. If a necessary interface conflict is found, report it to the controller with the smallest proposed change.

**Interfaces:**
- Consumes original DOCX, evidence-backed metadata, current journal/article-type requirements with URLs/dates, explicit author decisions and optional PROJECT state.
- Produces new-version submission artifacts and requirements/preservation/pending evidence, plus a stage-13 `待确认` handoff.
- Reusable Python checks expose documented CLI `--help`, deterministic machine-readable reports and nonzero failure codes for detected violations. Worker chooses minimal arguments/functions and documents actual interfaces, not speculative placeholders.

- [ ] Read the spec, skill-creator and applicable local instructions; inventory existing suite conventions.
- [ ] Write focused failing behavioral tests first for any reusable Python code. Required observable cases: source bytes unchanged, split fields recognized, citation key/URI replacement detected, harmless numeric-cache/layout changes accepted, bibliography identity/count damage detected, unresolved requirements cannot be ready, filtered submission packaging excludes private process inputs, old PROJECT stage 13 initialized and downstream invalidation bounded correctly.
- [ ] Run each focused test and retain a red result showing the intended missing behavior (not an unrelated import/setup failure).
- [ ] Implement concise skill/reference instructions and minimal helpers so the test cases pass; do not encode patient or institution examples from the real task.
- [ ] Add author/funding/declaration provenance and confirmation workflow, conditional article-type checklist handling, official-access-failure behavior, copy-based DOCX editing and visual/Refresh acceptance requirements.
- [ ] Integrate stage 13, clean directory conventions, installer inventory and suite documentation/tests. No global settings edits.
- [ ] Run new helper `--help`, skill-creator validator and focused tests. Review own diff for hidden assumptions, source mutation, blanket readiness and data leakage.
- [ ] Run the existing suite once after focused tests pass; report exact results and genuine platform limitations. Do not repeatedly run the full suite while iterating minor changes.
- [ ] Commit only task-related changes in the isolated feature branch, leaving all clinical materials and private logs outside commits; provide actual file list, tests and limitations to the controller. Do not dispatch reviewers or child agents.

## Task 2: Controller acceptance and deployment

- [ ] Controller reviews implementation against every spec section and actual output; dispatch an independent review of the complete change.
- [ ] Return actionable findings to implementer. Fixes receive focused re-review; retain review/test records without calling them clinical validation.
- [ ] Prepare four minimal synthetic user scenarios with independent source snapshots: original observational research, case report, systematic review and narrative review. Use new context-free agents for each, with neutral prompts and no expected answers.
- [ ] Inspect generated files, paths, status, source hashes, field identities and pending actions. Run an additional fresh test after any behavioral fix; never reuse a failed tester as a fresh blind session.
- [ ] Run final validators/regressions and source/private-data checks.
- [ ] Integrate only reviewed changes into the canonical local suite checkout after confirming it has not drifted.
- [ ] Back up and SHA-256 verify only new/changed installed skill directories in Codex, Agents and Claude. Existing installer routines may be reused for selected directories; avoid replacing unrelated installed skills.
- [ ] Report source/install locations, local automated and behavioral results, limitations, and no remote publication.

## Self review

The author approved the entire contract and execution method before this plan. Task 1 implements the coherent new capability and its integration; Task 2 accepts and deploys it. Both share only the reviewed repository output. No implementation worker sees prior patient data or the controller's hidden blind-test expectations. The contractor can choose focused helper structure, but may not expand into a portal, journal database or second writing/reference engine.
