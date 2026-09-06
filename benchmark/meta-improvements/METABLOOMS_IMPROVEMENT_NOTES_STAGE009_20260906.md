# MetaBlooms Improvement Notes — Stage009 Self-Run

These are additive to MB-CV-001 through MB-CV-019 already preserved in the commercial-validation evidence history. They are implementation candidates, not canonical OS changes.

## MB-CV-020 — Make the integrated promotion chain a single native product surface
- Observation: Stage009 reproduced all CVB-007 controls only in `COMPOSITE` mode by orchestrating existing MetaBlooms components: CCCC session authority, candidate qualification binding, transactional host enforcement, deny-default capability logic, and CAS authority publication.
- Risk: a composite benchmark PASS can be misread as proof that ordinary production promotion paths invoke every required control in one enforced native sequence.
- Improvement: implement one native promotion controller/contract that consumes the frozen Stage006 authority inputs, invokes every load-bearing control, emits one PROMOTE/DENY receipt, and is the normal production promotion surface. Preserve `COMPOSITE` labeling until that path is independently demonstrated.

## MB-CV-021 — Disable derived Python bytecode in benchmark runners by default
- Observation: the first Stage009 calibration produced `__pycache__` files and tripped MetaBlooms' own no-derived-bytecode invariant even though the substantive tests were otherwise green.
- Risk: self-validation can create artifacts that make a clean system appear nonconformant, causing false-red benchmark runs.
- Improvement: standardize `PYTHONDONTWRITEBYTECODE=1` and `python -B` in benchmark/calibration runner primitives, and validate no derived bytecode exists before and after execution.

## MB-CV-022 — Long scored runs need a durable resumable runner
- Observation: two byte-identical Stage009 scored attempts were terminated by the foreground execution window before completion; the third completed unchanged when run through a launched process and synchronously polled.
- Risk: transport/runtime limits can interrupt evidence collection and tempt ad hoc reruns without durable scenario boundaries.
- Improvement: make Stage008/Stage009 runners checkpoint after each scenario, preserve interruption receipts automatically, resume only from verified immutable holdout/harness hashes, and separate benchmark execution state from the chat/tool foreground window.

## MB-CV-023 — Add a provider-faithful CAS acceptance surface
- Observation: Stage009 S5 exercised native MetaBlooms CAS generation/parent logic with deterministic isolated provider receipt/readback fixtures rather than mutating a live provider repository.
- Risk: local deterministic evidence proves lineage logic but leaves a gap between the CAS contract and real provider transport semantics.
- Improvement: provide an official provider emulator or dedicated test-tenant harness that exercises create/update/readback CAS semantics, including stale generations and parent mismatches, while retaining deterministic replay and hash-bound evidence.
