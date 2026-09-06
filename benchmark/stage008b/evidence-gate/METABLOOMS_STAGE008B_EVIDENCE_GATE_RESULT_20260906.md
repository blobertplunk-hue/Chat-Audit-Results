# MetaBlooms Stage008B — Evidence Gate

- **Integrated verdict:** `FAIL_INTEGRATED`
- **Mode:** `FREE_LOCAL_PINNED`
- **Pin:** `3f478e1f3d3c5050725f15ecf9cdb4ff5eb9ea75`
- **Native tests:** 242 passed
- **Scored run:** 34060609494
- **Scored artifact SHA-256:** `9771fd7741386de85479ca07fca5461c0107a823f3a13865080ba6178854aeae`

## Scenario adjudication

| Scenario | Result |
|---|---|
| S0 | PASS |
| S1 | FAIL |
| S2 | NOT_APPLICABLE |
| S3 | NOT_APPLICABLE |
| S4 | FAIL |
| S5 | NOT_VERIFIED |
| S6 | PASS |

S1 failed because unchanged proof still passed after the externally current baseline changed. S4 failed because C0-bound proof still passed when C1 was the externally expected candidate. S5 remains NOT_VERIFIED for hosted decision-chain supersession because the executable Free/local evaluator is stateless and no hosted credential was available.
