# Orion Stage 008B Harness V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chained Orion benchmark harness with isolated, observation-first scenario execution that can emit S0–S6 without confusing adapter failures with Orion outcomes.

**Architecture:** A Python orchestration layer owns scenario isolation, command capture, result envelopes, SQLite evidence snapshots, and calibration-only gating. A minimal Go adapter seeds an independent native Orion proof precondition. A GitHub Actions calibration workflow builds the exact Orion pin and executes all seven scenarios using a non-scoreable fixture.

**Tech Stack:** Python 3 stdlib, Go 1.26.5, GitHub Actions, Orion pinned source, SQLite.

**Spec:** `ARCHITECTURE.md`

## Global Constraints

- CVB-007 scenario semantics remain unchanged.
- Orion source pin remains `9b9e9567305122d439727989b3633abc05183bce`.
- No PASS/PARTIAL/FAIL classification is produced during redesign/calibration.
- Orion CLI nonzero exits are observations, not harness exceptions.
- The exposed V1 holdout is not reused for a future scored run.

### Task 1: Scenario-isolation runner

**Files:** `runner_v2.py`, `test_runner_v2.py`

- [x] Write failing tests for nonzero product exits, scenario exception isolation, true candidate mutation, exact seven-scenario summary, and command capture.
- [x] Verify RED because `runner_v2` does not exist.
- [x] Implement the minimal runner interfaces.
- [x] Verify all five tests pass.

### Task 2: Minimal native proof adapter

**Files:** `probe_main.go`

- [x] Keep only mechanical native Q0 precondition creation.
- [x] Remove product-outcome assertions such as S4 memo-hit panic.
- [ ] Build inside the exact pinned Orion module and verify compilation.

### Task 3: Calibration-only workflow

**Files:** `calibration_fixture.json`, `.github/workflows/stage008b-revelara-orion-harness-v2-calibration.yml`

- [x] Create a fresh branch from repository `main` with no V1 holdout dependency.
- [ ] Commit runner, tests, probe, architecture, and calibration fixture.
- [ ] Add workflow last so intermediate file commits cannot trigger partial runs.
- [ ] Run unit tests, build exact Orion pin, execute S0–S6, upload raw evidence.
- [ ] Require seven envelopes and zero `HARNESS_ERROR`; do not evaluate product scores.

### Task 4: Governed preservation

- [ ] Preserve architecture, implementation plan, calibration summary/evidence, exact GitHub commit/run IDs, and hashes under MetaBlooms via ExecutionManager.
- [ ] Record next action as freeze-new-Orion-holdout then perform scored run; Stage 009 remains blocked until competitor cohort progression allows it.
