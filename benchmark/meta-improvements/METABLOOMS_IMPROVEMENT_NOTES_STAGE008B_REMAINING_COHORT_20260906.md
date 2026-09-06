# MetaBlooms Improvement Notes — Remaining Stage008B Cohort

These findings supplement the existing commercial-validation improvement log.

## MB-CV-013 — Bind proof validity to current authority context
Evidence Gate free/local provenance validation accepted structurally valid C0 evidence after the external baseline changed and when C1 was externally expected. MetaBlooms should require separate proof-validity and context-binding checks inside the enforcement boundary.

## MB-CV-014 — Make evidence applicability a first-class verifier output
Adapters should emit `evidence_subject`, `expected_subject`, `subject_match`, `policy_generation`, and `baseline_generation`. A valid statement with the wrong subject must not become valid promotion proof.

## MB-CV-015 — Score product modes independently when capability tiers diverge
Evidence Gate Free mode was fully reproducible, while hosted Pro/Enterprise behavior was credential-gated. Stage008/Stage008B should identify the exact product mode and forbid inheritance of untested higher-tier claims.

## MB-CV-016 — Preflight hosted-provider access before cohort execution
Pushgate was frozen as HOSTED_EXTERNAL, but this lane had no Pushgate/TestifySec/CI-lock credential and no repository-specific Pushgate remote. Stage008 should require an executable provider-access preflight before a hosted system enters the scored cohort.

## MB-CV-017 — Hash hosted documentation snapshots, not only timestamps
Pushgate had no immutable public product version and was pinned by documentation timestamp. MetaBlooms should archive normalized page/API bytes with per-resource SHA-256 and a manifest hash so later documentation drift cannot silently change the frozen evidence basis.

## MB-CV-018 — Keep contract evidence distinct from provider-execution evidence
Pushgate public documentation specifies exact commit/repository/nonce/policy bindings, but no runtime transition could be reproduced. Result schemas should separate `claimed_contract`, `code_supported_behavior`, `provider_runtime_observation`, and `classification_basis`.

## MB-CV-019 — Make probes immune to their own labels and diagnostics
The first Pushgate credential probe falsely matched its own `PUSHGATE_` output header. The corrected probe inspected `os.environ` directly. MetaBlooms probes should inspect structured sources first, emit labels afterward, and include negative controls against self-referential evidence contamination.
