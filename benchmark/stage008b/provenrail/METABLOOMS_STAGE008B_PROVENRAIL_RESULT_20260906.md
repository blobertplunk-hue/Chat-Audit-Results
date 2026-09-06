# MetaBlooms Stage008B — Provenrail Result

**Benchmark:** CVB-007-20260905  
**Pinned system:** Provenrail 0.2.33 @ `b4b890699f859b2cbf607bb871daea0821679aaf`  
**Integrated verdict:** **NOT_END_TO_END**

## Scenario adjudication

| Scenario | Classification | Observed decision |
|---|---|---|
| S0 | NOT_APPLICABLE | NO_DECISION |
| S1 | NOT_APPLICABLE | NO_DECISION |
| S2 | PARTIAL | PROMOTE |
| S3 | NOT_APPLICABLE | NO_DECISION |
| S4 | NOT_APPLICABLE | NO_DECISION |
| S5 | FAIL | PROMOTE |
| S6 | NOT_APPLICABLE | NO_DECISION |

## Key findings

- **S2 — PARTIAL:** A0 and A1 are separately auditable and approval links are single-use, but the execution-side session authority is represented at rule granularity (`SessionState.oversight_rules`) rather than by approval-request identity. After A1 existed, the old A0 target was accepted without a fresh approval. Because there is no native reusable A0 credential to present directly, this is scored PARTIAL rather than a stronger stale-token FAIL.
- **S5 — FAIL:** D0 was approved and a later same-scope D1 was denied. The same action still passed afterward without a new approval because D0-derived rule state remained active. Provenrail's signed chain correctly detects record reordering, but that integrity guarantee does not revoke execution authority.
- **Scope:** S0/S1/S3/S4/S6 remain frozen NOT_APPLICABLE. Provenrail is therefore a narrow but testable guard/evidence layer, not an end-to-end candidate-promotion system in CVB-007.

## Evidence

- Holdout commit: `e0b0191920913efb4c97c8232fa64801eb47851d`
- Holdout SHA-256: `e888be10782334ed412652a7f9d56f4799c41da23735793bd2e304a8d62b31c2`
- Scored run: `34059179376`
- Scored head: `8fa26d9414f3ba629011d95ab18388f8cb0bf546`
- Artifact ID: `9996912336`
- Artifact SHA-256: `fb0e9cffe13ace25088dae30646881254b7454aa69cf8b65a7668aab1de327ec`
- Internal artifact manifest: **PASS_ZERO_MISMATCH**
- Native reference tests: **34 passed, 1 warning**

## Boundaries

MetaBlooms Stage009 and Stage010 were not performed. No superiority or uniqueness claim is authorized.

**Next frozen competitor:** Evidence Gate.
