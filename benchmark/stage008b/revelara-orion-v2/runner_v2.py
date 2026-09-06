#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import traceback
from pathlib import Path
from typing import Any, Callable

SCENARIOS = [f"S{i}" for i in range(7)]
CALIBRATION_MODE = "CALIBRATION_ARCHITECTURE"


@dataclasses.dataclass
class ScenarioContext:
    scenario_id: str
    out_dir: Path
    data_dir: Path
    orion: str
    probe: str
    fixture: dict[str, Any]
    env: dict[str, str]


def run_command(argv: list[str], *, env: dict[str, str] | None = None,
                input_text: str | None = None, cwd: str | None = None,
                timeout: int = 900) -> dict[str, Any]:
    cp = subprocess.run(
        argv,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
        cwd=cwd,
        timeout=timeout,
    )
    return {
        "argv": argv,
        "rc": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
    }


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record_command(ctx: ScenarioContext, name: str, argv: list[str], *,
                   input_text: str | None = None, timeout: int = 900) -> dict[str, Any]:
    result = run_command(argv, env=ctx.env, input_text=input_text, timeout=timeout)
    stem = ctx.out_dir / "commands" / name
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".stdout").write_text(result["stdout"], encoding="utf-8")
    stem.with_suffix(".stderr").write_text(result["stderr"], encoding="utf-8")
    _write_json(stem.with_suffix(".json"), {k: v for k, v in result.items() if k not in {"stdout", "stderr"}})
    return result


def mutate_candidate_main_go(path: Path, token: str) -> str:
    data = path.read_bytes()
    marker = f"\n// stage008b-v2 candidate mutation {token}\n".encode("utf-8")
    path.write_bytes(data + marker)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sqlite_rows(db: Path, sql: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql, args).fetchall()]
    finally:
        con.close()


def seed_spec(ctx: ScenarioContext, intent: str) -> dict[str, Any]:
    if ctx.data_dir.exists():
        shutil.rmtree(ctx.data_dir)
    ctx.data_dir.mkdir(parents=True, exist_ok=True)
    ctx.env["ORION_DATA_DIR"] = str(ctx.data_dir)
    commands: list[dict[str, Any]] = []
    commands.append(record_command(ctx, "submit", [ctx.orion, "submit", "--non-interactive"], input_text=intent + "\n"))
    for key, value in (("response_format", "json"), ("timezone", "UTC"), ("port", "8080"), ("route", "/time")):
        commands.append(record_command(ctx, f"answer-{key}", [ctx.orion, "answer", "--key", key, "--value", value]))
    commands.append(record_command(ctx, "spec-show-preapprove", [ctx.orion, "spec", "show"]))
    commands.append(record_command(ctx, "spec-approve-assumptions", [ctx.orion, "spec", "approve-assumptions"]))
    commands.append(record_command(ctx, "spec-approve", [ctx.orion, "spec", "approve"]))
    commands.append(record_command(ctx, "plan-initial", [ctx.orion, "plan", "show", "--json"]))
    return {
        "commands": commands,
        "precondition_established": all(c["rc"] == 0 for c in commands),
    }


def seed_proof(ctx: ScenarioContext, qtoken: str, ctoken: str) -> dict[str, Any]:
    out = ctx.out_dir / "native" / "q0-seed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = record_command(ctx, "probe-seed-proof", [ctx.probe, "seed-proof", str(ctx.data_dir), str(out), qtoken, ctoken])
    if result["rc"] != 0 or not out.exists():
        raise RuntimeError(f"adapter probe failed to seed proof rc={result['rc']}")
    return json.loads(out.read_text(encoding="utf-8"))


def dump_native_state(ctx: ScenarioContext, name: str) -> dict[str, Any]:
    db = ctx.data_dir / "orion.db"
    if not db.exists():
        return {"db_present": False}
    payload = {
        "db_present": True,
        "projects": sqlite_rows(db, "SELECT id,name,status,created_at,updated_at FROM projects ORDER BY created_at,id"),
        "specs": sqlite_rows(db, "SELECT id,project_id,status,version,parent_spec_id,spec_hash,created_at,updated_at FROM specs ORDER BY created_at,id"),
        "decisions": sqlite_rows(db, "SELECT id,project_id,spec_id,key,value,value_kind,created_at FROM decisions ORDER BY created_at,id"),
        "tasks": sqlite_rows(db, "SELECT id,title,status,proof_id,reproof_required,created_at,updated_at FROM tasks ORDER BY created_at,id"),
        "proofs": sqlite_rows(db, "SELECT id,task_id,mode,verdict,detail,created_at FROM proofs ORDER BY created_at,id"),
        "artifacts": sqlite_rows(db, "SELECT id,task_id,artifact_type,storage_path,content_hash,created_at FROM artifacts ORDER BY created_at,id"),
        "deliveries": sqlite_rows(db, "SELECT id,epic_id,created_at FROM deliveries ORDER BY created_at,id"),
        "run_events": sqlite_rows(db, "SELECT id,project_id,run_id,task_id,phase,status,detail,created_at FROM run_events ORDER BY id"),
    }
    _write_json(ctx.out_dir / "native" / f"{name}.json", payload)
    return payload


def scenario_s0(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['r0']} {f['tokens']['a0']}")
    run = record_command(ctx, "run", [ctx.orion, "run", "--mode", "json"])
    deliver = record_command(ctx, "deliver-show", [ctx.orion, "deliver", "show", "--json"])
    return {"setup": setup, "run": run, "deliver": deliver, "native_state": dump_native_state(ctx, "state-after-s0")}


def scenario_s1(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['r0']} {f['tokens']['a0']}")
    q0 = seed_proof(ctx, f['tokens']['q0'], f['tokens']['c0'])
    change = record_command(ctx, "authority-change", [ctx.orion, "answer", "--key", "oncall_escalation", "--value", f"team-omega {f['tokens']['a1']}"])
    spec = record_command(ctx, "spec-after-change", [ctx.orion, "spec", "show"])
    stale = record_command(ctx, "stale-run", [ctx.orion, "run", "--mode", "json"])
    deliver = record_command(ctx, "deliver-after-stale", [ctx.orion, "deliver", "show", "--json"])
    return {"setup": setup, "q0": q0, "authority_change": change, "spec": spec, "stale_run": stale, "deliver": deliver, "native_state": dump_native_state(ctx, "state-after-s1")}


def scenario_s2(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['a0']}")
    engage = record_command(ctx, "redbutton-engage", [ctx.orion, "redbutton", "engage"])
    status = record_command(ctx, "redbutton-status", [ctx.orion, "redbutton", "status"])
    revoked = record_command(ctx, "revoked-run", [ctx.orion, "run", "--mode", "json"])
    deliver = record_command(ctx, "deliver-revoked", [ctx.orion, "deliver", "show", "--json"])
    release = record_command(ctx, "redbutton-release", [ctx.orion, "redbutton", "release"])
    return {"setup": setup, "engage": engage, "status": status, "revoked_run": revoked, "deliver": deliver, "release": release, "native_state": dump_native_state(ctx, "state-after-s2")}


def scenario_s3(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['r0']} {f['tokens']['a0']}")
    q0 = seed_proof(ctx, f['tokens']['q0'], f['tokens']['c0'])
    change = record_command(ctx, "authority-change", [ctx.orion, "answer", "--key", "oncall_escalation", "--value", f"team-recovery {f['tokens']['a1']}"])
    resume = record_command(ctx, "cold-resume", [ctx.orion, "resume", "--mode", "json"])
    deliver = record_command(ctx, "deliver-after-resume", [ctx.orion, "deliver", "show", "--json"])
    return {"setup": setup, "q0": q0, "authority_change": change, "resume": resume, "deliver": deliver, "native_state": dump_native_state(ctx, "state-after-s3")}


def scenario_s4(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['r0']} {f['tokens']['a0']}")
    q0 = seed_proof(ctx, f['tokens']['q0'], f['tokens']['c0'])
    main_go = ctx.data_dir / "stage008b-seed-candidate" / "main.go"
    if not main_go.exists():
        raise RuntimeError("seeded candidate main.go missing")
    c0_hash = hash_file(main_go)
    c1_hash = mutate_candidate_main_go(main_go, f['tokens']['c1'])
    if c0_hash == c1_hash:
        raise RuntimeError("candidate mutation did not change Orion main.go content hash")
    db = ctx.data_dir / "orion.db"
    memo_rows = sqlite_rows(db, "SELECT spec_hash,content_hash,created_at FROM proof_memo WHERE spec_hash=? AND content_hash=?", (q0["spec_hash"], c1_hash))
    old_rows = sqlite_rows(db, "SELECT spec_hash,content_hash,created_at FROM proof_memo WHERE spec_hash=? AND content_hash=?", (q0["spec_hash"], c0_hash))
    evidence = {
        "c0_hash": c0_hash,
        "c1_hash": c1_hash,
        "candidates_distinct": c0_hash != c1_hash,
        "q0_candidate_hash": q0.get("candidate_hash"),
        "c0_memo_present": bool(old_rows),
        "c1_memo_present_without_fresh_proof": bool(memo_rows),
        "c1_token": f['tokens']['c1'],
    }
    _write_json(ctx.out_dir / "native" / "candidate-binding.json", evidence)
    return {"setup": setup, "q0": q0, "candidate_binding": evidence, "native_state": dump_native_state(ctx, "state-after-s4")}


def scenario_s5(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['r0']} {f['tokens']['a0']}")
    d0 = record_command(ctx, "decision-d0", [ctx.orion, "answer", "--key", "oncall_escalation", "--value", f"team-d0 {f['tokens']['d0']}"])
    show0 = record_command(ctx, "spec-after-d0", [ctx.orion, "spec", "show"])
    d1 = record_command(ctx, "decision-d1", [ctx.orion, "answer", "--key", "oncall_escalation", "--value", f"team-d1 {f['tokens']['d1']}"])
    show1 = record_command(ctx, "spec-after-d1", [ctx.orion, "spec", "show"])
    state = dump_native_state(ctx, "decision-lineage")
    return {"setup": setup, "d0": d0, "show0": show0, "d1": d1, "show1": show1, "native_state": state}


def scenario_s6(ctx: ScenarioContext) -> dict[str, Any]:
    f = ctx.fixture
    setup = seed_spec(ctx, f"Build an HTTP service that returns the current time as JSON. {f['tokens']['r0']} {f['tokens']['a0']}")
    q0 = seed_proof(ctx, f['tokens']['q0'], f['tokens']['c0'])
    change = record_command(ctx, "authority-change", [ctx.orion, "answer", "--key", "oncall_escalation", "--value", f"team-fresh {f['tokens']['a1']}"])
    stale = record_command(ctx, "stale-run", [ctx.orion, "run", "--mode", "json"])
    reapprove = record_command(ctx, "spec-reapprove", [ctx.orion, "spec", "approve"])
    fresh = record_command(ctx, "fresh-run", [ctx.orion, "run", "--mode", "json"])
    deliver = record_command(ctx, "fresh-deliver", [ctx.orion, "deliver", "show", "--json"])
    return {"setup": setup, "q0": q0, "authority_change": change, "stale_run": stale, "reapprove": reapprove, "fresh_run": fresh, "deliver": deliver, "native_state": dump_native_state(ctx, "state-after-s6")}


SCENARIO_FUNCS: dict[str, Callable[[ScenarioContext], dict[str, Any]]] = {
    "S0": scenario_s0,
    "S1": scenario_s1,
    "S2": scenario_s2,
    "S3": scenario_s3,
    "S4": scenario_s4,
    "S5": scenario_s5,
    "S6": scenario_s6,
}


def run_scenarios(scenarios: list[str], factory: Callable[[str], Callable[[ScenarioContext], dict[str, Any]]], out_root: Path,
                  *, orion: str = "orion", probe: str = "orion-probe", fixture: dict[str, Any] | None = None,
                  base_env: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    fixture = fixture or {"tokens": {}}
    for sid in scenarios:
        sdir = out_root / sid
        sdir.mkdir(parents=True, exist_ok=True)
        env = dict(base_env or os.environ)
        ctx = ScenarioContext(sid, sdir, out_root / "data" / sid, orion, probe, fixture, env)
        try:
            observations = factory(sid)(ctx)
            envelope = {
                "scenario_id": sid,
                "harness_status": "COMPLETE",
                "benchmark_score": None,
                "observations": observations,
            }
        except Exception as exc:
            envelope = {
                "scenario_id": sid,
                "harness_status": "HARNESS_ERROR",
                "benchmark_score": None,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        _write_json(sdir / "scenario-envelope.json", envelope)
        results[sid] = envelope
    return results


def summarize(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    exact = set(results) == set(SCENARIOS)
    errors = [sid for sid, r in results.items() if r.get("harness_status") != "COMPLETE"]
    return {
        "scenario_count": len(results),
        "all_scenarios_emitted": exact,
        "harness_error_count": len(errors),
        "harness_error_scenarios": errors,
        "score_performed": False,
    }


def sha256_manifest(root: Path) -> None:
    lines = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name == "SHA256SUMS.txt":
            continue
        lines.append(f"{hash_file(p)}  {p.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orion", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", required=True)
    args = ap.parse_args()
    if args.mode != CALIBRATION_MODE:
        raise SystemExit("runner_v2 is calibration-only; scored holdout execution requires a later frozen stage")
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    if fixture.get("fixture_mode") != "CALIBRATION_ONLY_NOT_SCOREABLE":
        raise SystemExit("fixture is not marked calibration-only")
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = dict(os.environ)
    env.update({
        "ORION_AGENT": "fixture",
        "ORION_SANDBOX_ISOLATION": "none",
        "ORION_ALLOW_UNSAFE_GO_ARM": "1",
        "ORION_MEMORY_EMBEDDER": "off",
        "ORION_POLARIS_MCP_URL": "",
        "ORION_GIT_DELIVERY": "0",
    })
    results = run_scenarios(SCENARIOS, lambda sid: SCENARIO_FUNCS[sid], out, orion=args.orion, probe=args.probe, fixture=fixture, base_env=env)
    summary = summarize(results)
    summary.update({
        "schema": "metablooms.stage008b.orion_harness_v2.calibration_summary.v1",
        "benchmark_id": fixture.get("benchmark_id"),
        "fixture_id": fixture.get("fixture_id"),
        "mode": args.mode,
        "competitor_pin": fixture.get("competitor_pin"),
    })
    _write_json(out / "summary.json", summary)
    sha256_manifest(out)
    return 0 if summary["all_scenarios_emitted"] and summary["harness_error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
