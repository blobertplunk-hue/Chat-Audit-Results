# MetaBlooms Improvement Notes — Commercial Validation

Date: 2026-09-06
Scope: CVB-007 competitor Stage008B execution and continuity/recovery observations.
Status: living notes; findings are implementation candidates, not yet changes to canonical MetaBlooms OS.

## MB-CV-001 — Separate boot health from continuity freshness
- Observation: turn-boot normalized PASS while the GitHub continuity guard reported `SYNC_REQUIRED` / `SNAPSHOT_STALE_AT_FETCH`.
- Risk: an operator can read "PASS" as meaning remote durable authority is current when only local boot invariants passed.
- Improvement: emit distinct top-level states such as `BOOT_HEALTH=PASS` and `CONTINUITY_FRESHNESS=STALE|FRESH`; automatically refresh before any stage that depends on remote authority, or fail closed for writes.

## MB-CV-002 — Provider-read durable stage authority before executing handoff next-actions
- Observation: the local continuation said AgentAction had not been scored, while the evidence repository already contained the scored workflow and terminal result.
- Risk: duplicate benchmark runs, conflicting receipts, and accidental history overwrite.
- Improvement: every stage resume should reconcile the referenced evidence repository branch/result pointer before trusting a local `next_action` field.

## MB-CV-003 — Harden live-root restoration against partial MetaBlooms roots
- Observation: `/mnt/data/Metablooms_OS` was previously present but missing boot-critical `scripts/mpp/mpp.sh`, requiring canonical-baseline restoration.
- Risk: a path can look like the live root while being operationally incomplete.
- Improvement: live-root persistence guard should validate a required-path manifest and atomic root identity before accepting/restoring a root; quarantine partial roots automatically.

## MB-CV-004 — Validate continuation bundles for referenced-but-missing execution artifacts
- Observation: Stage008 authority references `adapters/provenrail.json`, but that adapter is not present in the continuation ZIP.
- Risk: next-chat execution depends on artifacts named by authority but omitted from the handoff.
- Improvement: export validation should resolve every authority path needed by `next_action` and fail/warn on missing adapters, fixtures, schemas, holdouts, or receipt pointers.

## MB-CV-005 — Pre-provision competitor holdouts at Stage008 freeze
- Observation: AgentAction lacked a competitor-specific holdout in the continuation packet and required a post-calibration, pre-score freeze.
- Risk: avoidable ambiguity about whether a scored fixture was exposed to tuning.
- Improvement: Stage008 should deterministically generate, hash, and bundle one untouched holdout per selected competitor before any Stage008B execution starts.

## MB-CV-006 — Publish immutable stage-completion pointers into continuation state
- Observation: AgentAction completion existed remotely but the local continuation remained stale.
- Risk: new chats resume from obsolete stage state.
- Improvement: terminal stage receipts should update an immutable remote `LATEST`/completion pointer and continuation bootstrap should reconcile against it before execution.

## MB-CV-007 — Distinguish narrow valid control layers from full-system failure
- Observation: Provenrail is frozen N/A for five of seven scenarios by scope, despite strong evidence-integrity/guardrail claims in its applicable layer.
- Risk: `FAIL` language can conflate "not an end-to-end promotion system" with "bad at its claimed layer."
- Improvement: tracker/result UI should prominently render `NOT_END_TO_END` as a scope classification and keep per-scenario quality separate.

## MB-CV-008 — Make benchmark applicability self-check against scenario applicability contract
- Observation: frozen Provenrail S5 is APPLICABLE, while the benchmark text says S5 applies to systems that preserve decision history *and also influence current promotion authority*. Provenrail influences current tool-call authorization rather than repository promotion.
- Risk: applicability decisions can silently broaden scenario semantics across competitors.
- Improvement: Stage008 applicability freeze should include an explicit `claimed_authority_boundary` and machine-check that each scenario's applicability predicate is satisfied at that boundary.

## MB-CV-009 — Treat approval capability and session authorization as separate evidence objects
- Observation: Provenrail's approval link is single-use/expiring, while approved oversight is then represented in session policy state; these are distinct lifetimes.
- Risk: a benchmark can incorrectly infer that single-use approval-link semantics guarantee single-use action authorization.
- Improvement: MetaBlooms benchmark adapters should separately capture `approval_capability_lifetime`, `authorization_effect_lifetime`, `revocation_event`, and `current-authority check`.

## MB-CV-010 — Evidence manifests must verify from the manifest's own directory
- Observation: the first Provenrail calibration workflow generated `SHA256SUMS.txt` inside `raw/calibration` using relative `./...` paths, then ran `sha256sum -c raw/calibration/SHA256SUMS.txt` from repository root. All substantive tests/probes passed, but packaging failed because verification resolved paths against the wrong working directory.
- Risk: false-red evidence jobs after successful benchmark execution, plus skipped artifact upload.
- Improvement: standardize an artifact-manifest helper that both generates and verifies inside the artifact root (for example `(cd "$ARTIFACT_ROOT" && sha256sum -c SHA256SUMS.txt)`) and unit-test it as an OS primitive.

## MB-CV-011 — Governance should model revocation propagation, not only decision retention
- Observation: pinned Provenrail calibration showed D0 approval remains `approved` and native `SessionState.oversight_rules` continues to allow the rule after a later same-scope D1 denial exists in the approval store.
- Risk: an audit trail can accurately retain a newer denial while the execution-side authorization cache remains permissive.
- Improvement: MetaBlooms authority objects should carry explicit generation/epoch or supersession IDs into the enforcement cache, and a later denial/revocation must invalidate any prior cached authorization before current execution.

## MB-CV-012 — Refresh the active tracker after durable stage transitions
- Observation: the turn-level `ACTIVE_TRACKER_PREVIEW.txt` still names the original AgentAction task even after provider reconciliation showed AgentAction complete and the same governed turn closed Provenrail Stage008B.
- Risk: the operator-facing tracker can become semantically stale inside a long turn even while receipts, GitHub evidence, and continuation state are correct.
- Improvement: every terminal stage receipt or authoritative `LATEST` pointer publication should trigger tracker regeneration from durable state, with a `tracker_as_of_stage` / source receipt hash so stale UI state is detectable.
