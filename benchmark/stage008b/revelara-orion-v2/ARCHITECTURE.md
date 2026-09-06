# Revelara Orion Stage 008B Harness V2 Architecture

Status: **REDESIGN / CALIBRATION ONLY — NO ORION SCORE**

Benchmark authority remains `CVB-007-20260905`; Orion remains pinned at `9b9e9567305122d439727989b3633abc05183bce`.

## Root causes addressed

1. The V1 harness chained S1/S3/S4/S5/S6 together, so one adapter assertion aborted unrelated scenarios.
2. V1 encoded product observations as panics (`memo_hit=true`), confusing competitor behavior with harness correctness.
3. V1's S4 C1 changed `go.mod`, while Orion's proof memo keyed the generated artifact by `main.go` content hash; C0 and C1 were therefore identical under the native key.
4. The V1 holdout has been exposed through repeated harness-debug runs and is no longer suitable as a future unseen scored holdout.

## V2 invariants

- S0 through S6 run in independent Orion data directories.
- Every scenario emits `scenario-envelope.json` even if another scenario has a harness error.
- Orion CLI nonzero exits are observations, never Python exceptions and never automatic PASS/FAIL classifications.
- Only adapter/runtime defects set `harness_status=HARNESS_ERROR`.
- `benchmark_score` is always `null` in this redesign/calibration stage.
- S4 mutates the actual generated `main.go` bytes and verifies `C1_hash != C0_hash` before observing Orion's native `(spec_hash, content_hash)` proof memo.
- Harness archival and SQLite reads are evidence collection only; they are not credited as Orion capabilities.
- S3 uses Orion's native `orion resume` entrypoint in a new process against the same durable Context Store.
- S5 reads Orion's native durable decisions/spec state but does not infer supersession unless the product state itself makes it observable.
- S6 is independent and can execute even when S1/S4/S5 produce denials or weak observables.
- The process exits nonzero only for harness incompleteness/errors, never because Orion denies a benchmark action.

## Scenario execution map

| Scenario | Isolated native path |
|---|---|
| S0 | fresh spec → `orion run` → `orion deliver show` |
| S1 | fresh spec → native Q0 seed → governing decision changes → stale `orion run` |
| S2 | fresh spec → `redbutton engage` → `orion run` → release |
| S3 | fresh spec → native Q0 seed → governing decision changes → fresh-process `orion resume` |
| S4 | fresh spec → native Q0 seed for C0 → content-change `main.go` to C1 → observe native proof-memo key for C1 |
| S5 | fresh spec → D0 decision → D1 decision → inspect native durable decisions/current spec |
| S6 | fresh spec → Q0 → governing change/stale attempt → reapprove → fresh run/delivery → inspect retained native state |

## Holdout policy

The earlier V1 holdout is retained as historical evidence but considered **exposed by harness debugging**. V2 validation uses `ORION_HARNESS_V2_CALIBRATION_001`, which is explicitly non-scoreable. A later scored Orion run must freeze a new unseen holdout *after* V2 calibration passes and before the scored harness commit.
