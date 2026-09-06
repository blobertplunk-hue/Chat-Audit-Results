#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil
from pathlib import Path
from runner_v2 import SCENARIOS, SCENARIO_FUNCS, run_scenarios, summarize, _write_json, sha256_manifest

SCORED_MODE='SCORED_HOLDOUT_EXECUTION'
PIN='9b9e9567305122d439727989b3633abc05183bce'
BENCHMARK='CVB-007-20260905'

def validate_scored_fixture(fixture):
    if fixture.get('fixture_mode') != 'SCORED_HOLDOUT':
        raise ValueError('fixture is not a scored holdout')
    if fixture.get('benchmark_id') != BENCHMARK:
        raise ValueError('benchmark binding mismatch')
    if fixture.get('competitor_pin') != PIN:
        raise ValueError('competitor pin mismatch')
    tokens=fixture.get('tokens') or {}
    required={'r0','r1','a0','a1','c0','c1','q0','q1','d0','d1'}
    if set(tokens) != required or len(set(tokens.values())) != len(required):
        raise ValueError('scored holdout token set invalid')

def build_scored_summary(results, fixture):
    summary=summarize(results)
    summary.update({
        'schema':'metablooms.stage008b.orion_harness_v2.scored_execution_summary.v1',
        'benchmark_id':fixture.get('benchmark_id'),
        'fixture_id':fixture.get('fixture_id'),
        'mode':SCORED_MODE,
        'competitor_pin':fixture.get('competitor_pin'),
        'score_performed':False,
    })
    return summary

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--orion',required=True)
    ap.add_argument('--probe',required=True)
    ap.add_argument('--fixture',required=True)
    ap.add_argument('--out',required=True)
    args=ap.parse_args()
    fixture=json.loads(Path(args.fixture).read_text(encoding='utf-8'))
    validate_scored_fixture(fixture)
    out=Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env=dict(os.environ)
    env.update({
        'ORION_AGENT':'fixture',
        'ORION_SANDBOX_ISOLATION':'none',
        'ORION_ALLOW_UNSAFE_GO_ARM':'1',
        'ORION_MEMORY_EMBEDDER':'off',
        'ORION_POLARIS_MCP_URL':'',
        'ORION_GIT_DELIVERY':'0',
    })
    results=run_scenarios(SCENARIOS, lambda sid: SCENARIO_FUNCS[sid], out, orion=args.orion, probe=args.probe, fixture=fixture, base_env=env)
    summary=build_scored_summary(results,fixture)
    _write_json(out/'summary.json',summary)
    sha256_manifest(out)
    return 0 if summary['all_scenarios_emitted'] and summary['harness_error_count']==0 else 2

if __name__=='__main__':
    raise SystemExit(main())
