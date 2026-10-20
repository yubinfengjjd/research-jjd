# Claude Experiment Backend Implementation Plan

> **For agentic workers:** Use subagent-driven-development with a fresh implementation worker, independent task review and final acceptance review. Existing user authorization requests implementation and acceptance; execute without re-requesting it.

**Goal:** Add native Claude Code autonomous proposal/review execution without requiring Codex for a Claude-selected study.

**Architecture:** A small backend protocol module selects/validates invocation and output identity; agent_runner retains lifecycle/prompt ownership, and adaptive/reconciliation consume backend-bound identities. Training/controller/scientific policy is shared unchanged.

**Tech Stack:** Existing Python stdlib Windows Job Objects, native Claude/Codex CLIs, unittest, actual authorized CUDA synthetic fixtures.

**Spec:** `docs/superpowers/specs/2026-10-20-claude-experiment-backend-design.md`.

## Global constraints

Use the host-confirmed real Python with UTF-8. No patient data, private paths, credentials or raw runs in public source. Preserve Codex legacy hashes and no automatic backend/model fallback. Both agent roles are read-only; returned code is applied only by existing controller gates. Do not reset scientific definitions, cumulative budgets or test isolation. Scope is backend support plus necessary instructions/tests/deployment, not unrelated refactoring.

## Task 1: Native backend and protocol tests

Files: create `medimg-experiment/scripts/medexp/agent_backends.py` and `medimg-experiment/tests/test_agent_backends.py`; modify `agent_runner.py`, `adaptive.py`, `review_adapter.py`, and package resource requirements if necessary.

Interfaces: existing `invoke(root, delegation, purpose, payload)` remains stable. Backend helper exposes selected provider/config, executable validation, argv/event verification and replay verification. Invocation records include backend and actual CLI session provenance. Existing records default to Codex without mutation.

- [x] Write failing tests using actual protocol-shaped event streams, observed fresh Claude output and owned-process stub where external CLI is necessarily isolated. Reject failed/ambiguous/mismatched sessions, malformed output and inappropriate CLI flags/config; validate Claude-only and legacy delegations. Run new tests and retain a meaningful red log.
- [x] Implement the smallest backend helper and dispatch/lifecycle integration; preserve Codex argv, schema and existing calls. Claude must use fresh restricted read-only tool sessions and actual structured terminal success.
- [x] Generalize review labels and completed-review replay to bind the selected CLI/provider and real session/events; test no cross-backend replay and no synthetic-ID acceptance. Keep original input/candidate/deadline/budget gates.
- [x] Run new tests plus existing fresh-review/reconcile tests, compile and package checks. Report owned files, exact tests and limitations. Worker does not install, publish or run patient/model experiments.

## Task 2: Documentation, real acceptance and deployment

Files: `medimg-experiment/SKILL.md`, `references/adaptive-execution.md`, template and metadata; minimal plan/pipeline handoff wording; `README.md` and `CHANGELOG.md`. Private probe/study scripts and evidence remain outside this repository.

- [x] Probe installed native Claude with bounded real calls; verify session/structured result and that actual source reads work with restrictive tools. Preserve each failed probe. Record installed version and configured-model provenance without secrets or model override.
- [x] Document backend selection/default, native executable, max turns, read-only tools versus OS sandbox, model service use, honest fallback/blocked behavior. Keep skill discovery and all scientific gates.
- [x] Run the genuine Claude CUDA synthetic source-revision loop in a new bounded study, inspect real code commits, reviews/session IDs, runs/seeds, plan/archive and freeze/test histories. A blocked call or negative result is not a passing acceptance.
- [x] Independent fresh reviewer inspects the whole source change and real evidence. Fix actionable issues with scoped tests/re-review; run existing full Windows controller regressions and relevant suite/package/installation tests once final source is stable.
- [ ] Back up and hash-check affected global files in three roots while preserving intentional host isolation. Integrate reviewed source and maintain public documentation/CI honestly; no private logs in Git. Report implemented, tested, accepted and remaining limitations separately.
