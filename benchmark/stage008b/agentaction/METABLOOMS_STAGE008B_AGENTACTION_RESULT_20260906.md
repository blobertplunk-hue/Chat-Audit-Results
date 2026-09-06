# MetaBlooms Stage008B — AgentAction formal result

- Benchmark: `CVB-007-20260905`
- Mode: `NATIVE`
- Frozen upstream pin: `4dd2fdf73b894f8326cc76a3fd13b705695d140e`
- Frozen holdout commit: `ecc55622eeaf9bd77a5d4505dfedbf2b15fb6185`
- Holdout SHA-256: `71e7754ef08e92132e52c4386fc73a1d69d157aa2cb2f2d13d7a1d51e8613161`
- Scored workflow run: `34055275809`
- Scored artifact SHA-256: `e34625b293f141bcbd4231276609a8fd6dc4abe5804190ecbedd3067b5ef8ad8`
- Integrated verdict: **FAIL_INTEGRATED**

## Scenario results

| Scenario | Classification | Observed decision |
|---|---|---|
| S0 | **PASS** | `PROMOTE` |
| S1 | **FAIL** | `PROMOTE` |
| S2 | **PASS** | `DENY_PROMOTION` |
| S3 | **NOT_APPLICABLE** | `NO_DECISION` |
| S4 | **PASS** | `DENY_PROMOTION` |
| S5 | **FAIL** | `PROMOTE` |
| S6 | **PASS** | `PROMOTE` |

## Adjudication

AgentAction passes S0, S2, S4, and S6; S3 is frozen NOT_APPLICABLE. S1 and S5 are applicable FAILs: stale G0 authority remained executable after G1 became current, and D0 remained executable after a later same-scope D1 denial. CVB-007 therefore requires **FAIL_INTEGRATED**.

### Decisive failures

- **S1:** a grant issued under frozen `G0-3cbfa3ea` remained executable after current policy changed to `G1-3cb57964`; dispatch returned 201 and reached the provider integration path.
- **S5:** after later same-scope D1 denial, older D0 still minted a grant and dispatched with status 201.

### Positive controls and denial controls

- **S0 PASS:** current C0 authority dispatched the exact frozen C0 commit.
- **S2 PASS:** expired A0 JIT authority was denied 403 with zero provider calls and A1 remained distinguishable.
- **S4 PASS:** C0 evidence presented for C1 was denied 403 for commit/request-digest mismatch with zero provider calls.
- **S6 PASS:** stale C0 authority was denied for C1, then fresh C1 authority dispatched the exact C1 commit while retaining separate histories.
- **S3 NOT_APPLICABLE:** frozen Stage008 applicability excludes cross-session Git-workstream recovery for AgentAction.

## Evidence limitations

The scored path executed AgentAction's native authorization/JIT/dispatch code, but the final GitHub provider HTTP call was deterministically mocked to return 204. S2 expiry was induced by moving the test grant's `expires_at` into the past rather than waiting for wall-clock TTL. These limitations are retained in the machine-readable result.

## Next governed action

Execute **Provenrail** Stage008B under the unchanged CVB-007 benchmark and its frozen Stage008 pin/applicability. MetaBlooms Stage009 remains prohibited until the frozen competitor cohort is sufficiently closed.
