import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, copyFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = process.cwd();
const csm = process.argv[2];
const outDir = path.join(root, 'benchmark-output/csm-agentbook');
const workDir = path.join(root, '.benchmark-work/csm-agentbook');
const workspace = path.join(workDir, 'workspace');
const dbPath = path.join(workDir, 'agentbook.sqlite');
const holdoutPath = path.join(root, 'benchmark/holdouts/csm-agentbook-stage008b-v1.json');
const holdout = JSON.parse(readFileSync(holdoutPath, 'utf8'));
mkdirSync(outDir, { recursive: true });
mkdirSync(workspace, { recursive: true });

function sha256Bytes(bytes) { return createHash('sha256').update(bytes).digest('hex'); }
function sha256File(p) { return sha256Bytes(readFileSync(p)); }
function runPhase(name) {
  const env = {
    ...process.env,
    CSM_SRC: csm,
    CSM_DB: dbPath,
    CSM_WORKSPACE: workspace,
    CSM_PROJECT_ID: holdout.project_id,
    CSM_D0: holdout.historical_decisions.d0_summary,
    CSM_D1: holdout.historical_decisions.d1_summary,
  };
  const proc = spawnSync(process.execPath, [path.join(root, 'benchmark/stage008b/csm-agentbook/phase.mjs'), name], { env, encoding: 'utf8' });
  writeFileSync(path.join(outDir, `${name}.stdout.txt`), proc.stdout || '');
  writeFileSync(path.join(outDir, `${name}.stderr.txt`), proc.stderr || '');
  writeFileSync(path.join(outDir, `${name}.exit_code.txt`), String(proc.status ?? -1) + '\n');
  if (proc.status !== 0) throw new Error(`${name} failed rc=${proc.status}: ${proc.stderr}`);
  const parsed = JSON.parse(proc.stdout);
  writeFileSync(path.join(outDir, `${name}.json`), JSON.stringify(parsed, null, 2) + '\n');
  return parsed;
}

const current = path.join(workspace, 'current-state.txt');
writeFileSync(current, holdout.baseline.r0_content);
const r0Sha = sha256File(current);
const seed = runPhase('seed');
if (seed.r0 !== r0Sha) throw new Error('seed R0 hash mismatch');

// Frozen perturbation: external/current workspace reality changes after session A ends.
writeFileSync(current, holdout.baseline.r1_content);
const r1Sha = sha256File(current);
if (r1Sha === r0Sha) throw new Error('holdout R1 must differ from R0');
const reentry = runPhase('reentry');

// Later state transition and decision are recorded explicitly through AgentBook's native append API.
const supersede = runPhase('supersede');
if (supersede.r1 !== r1Sha) throw new Error('supersede R1 hash mismatch');
const lineage = runPhase('lineage');

copyFileSync(dbPath, path.join(outDir, 'agentbook.sqlite'));
copyFileSync(current, path.join(outDir, 'workspace-current-state.txt'));
copyFileSync(holdoutPath, path.join(outDir, 'frozen-holdout.json'));

const d0 = lineage.decisionEvents.find((e) => e.metadata?.decisionId === 'D0');
const d1 = lineage.decisionEvents.find((e) => e.metadata?.decisionId === 'D1');
const nativeReentryText = JSON.stringify({
  persistedState: reentry.persistedState,
  projectedState: reentry.projectedState,
  decisionEvents: reentry.decisionEvents,
  verificationEvents: reentry.verificationEvents,
  frontPage: reentry.frontPage,
});
const summary = {
  schema: 'metablooms-stage008b-csm-agentbook-raw/v1',
  benchmark_id: holdout.benchmark_id,
  variant_id: holdout.variant_id,
  run_mode: 'SCORED_HOLDOUT',
  competitor: 'CSM / AgentBook',
  repository: 'NovasPlace/CSM',
  pin: '4361d38de8672cffe06086e32b91ed41e73e100b',
  package: { name: 'opencode-cross-session-memory', version: '1.0.0' },
  process_boundaries: {
    seed_pid: seed.processPid,
    cold_reentry_pid: reentry.processPid,
    supersede_pid: supersede.processPid,
    lineage_read_pid: lineage.processPid,
    all_fresh: new Set([seed.processPid, reentry.processPid, supersede.processPid, lineage.processPid]).size === 4,
  },
  perturbation: {
    r0_sha256: r0Sha,
    r1_sha256: r1Sha,
    changed: r0Sha !== r1Sha,
    cold_reentry_harness_observed_sha256: reentry.workspaceSha256ObservedByHarnessPhase,
  },
  native_observables: {
    reentry_r1_token_present_in_native_agentbook_outputs: nativeReentryText.includes('f47e2b90'),
    reentry_r0_token_present_in_native_agentbook_outputs: nativeReentryText.includes('a1c58d77') || nativeReentryText.includes(r0Sha),
    reentry_projected_goal: reentry.projectedState?.activeGoal ?? null,
    reentry_event_count: reentry.projectedState?.eventCount ?? null,
    d0_present_after_d1: Boolean(d0),
    d1_present: Boolean(d1),
    d0_status_after_d1: d0?.status ?? null,
    d1_status: d1?.status ?? null,
    current_goal_after_d1: lineage.projectedState?.activeGoal ?? null,
    d1_is_after_d0_in_native_since_query: Boolean(d0 && lineage.sinceD0.some((e) => e.eventId === d1?.eventId)),
    current_state_has_current_decision_field: Object.prototype.hasOwnProperty.call(lineage.projectedState ?? {}, 'decision') || Object.prototype.hasOwnProperty.call(lineage.projectedState ?? {}, 'currentDecision'),
  },
  note: 'Harness-side workspace SHA observation is captured only as perturbation evidence. It is not credited as a CSM capability. Native classification must use AgentBook persisted/readback/frontpage/event behavior only.'
};
writeFileSync(path.join(outDir, 'raw-summary.json'), JSON.stringify(summary, null, 2) + '\n');

const files = ['raw-summary.json','seed.json','reentry.json','supersede.json','lineage.json','agentbook.sqlite','workspace-current-state.txt','frozen-holdout.json'];
const checksums = Object.fromEntries(files.map((f) => [f, sha256File(path.join(outDir, f))]));
writeFileSync(path.join(outDir, 'checksums.json'), JSON.stringify(checksums, null, 2) + '\n');
process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
