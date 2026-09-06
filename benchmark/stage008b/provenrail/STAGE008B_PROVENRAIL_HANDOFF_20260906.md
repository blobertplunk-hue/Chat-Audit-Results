# Stage008B Provenrail Handoff — 2026-09-06

## Terminal state
Provenrail Stage008B is formally adjudicated under frozen benchmark `CVB-007-20260905` at pin `b4b890699f859b2cbf607bb871daea0821679aaf` (version `0.2.33`).

## Result
- S0: NOT_APPLICABLE
- S1: NOT_APPLICABLE
- S2: PARTIAL
- S3: NOT_APPLICABLE
- S4: NOT_APPLICABLE
- S5: FAIL
- S6: NOT_APPLICABLE
- Integrated: `NOT_END_TO_END`

S2 is PARTIAL because Provenrail makes approval capabilities single-use but represents action authorization at this boundary as rule-level `SessionState.oversight_rules`, without preserving approval-request identity as the current execution credential. S5 is FAIL because a later same-scope denial did not revoke the prior D0-derived execution-side rule authorization. Signed-chain integrity still detected reordered history, showing the distinction between provenance integrity and semantic authority revocation.

## Evidence
- Calibration v2 run: `34058999746` — success; 34 native tests passed.
- Calibration artifact: `9996858180`, SHA-256 `b2ca770006a1538a600333fda0586677527068162bb76aaffb340e5391ed9202`.
- Frozen holdout commit: `e0b0191920913efb4c97c8232fa64801eb47851d`.
- Frozen holdout SHA-256: `e888be10782334ed412652a7f9d56f4799c41da23735793bd2e304a8d62b31c2`.
- Scored run: `34059179376` — success.
- Scored artifact: `9996912336`, SHA-256 `fb0e9cffe13ace25088dae30646881254b7454aa69cf8b65a7668aab1de327ec`; internal manifest PASS with zero mismatches.

## MetaBlooms improvement lane
Continue appending evidence-backed observations to `METABLOOMS_IMPROVEMENT_NOTES_COMMERCIAL_VALIDATION_20260906.md`. Do not silently apply those notes to canonical OS while another lease/lane owns the canonical root.

## Next authorized competitor action
Execute **Evidence Gate Stage008B** under the unchanged frozen benchmark and Stage008 pin/applicability. Pushgate follows. MetaBlooms Stage009 and Stage010 remain unperformed.
