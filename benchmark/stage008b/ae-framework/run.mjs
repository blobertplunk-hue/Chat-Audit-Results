import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { runCommand, parseJsonFile } from './runner-lib.mjs';

const aeRoot = path.resolve(process.argv[2] ?? '');
if (!aeRoot || !fs.existsSync(path.join(aeRoot, 'package.json'))) {
  throw new Error('Usage: node run.mjs /absolute/path/to/pinned/ae-framework');
}

const harnessRoot = process.cwd();
const holdoutPath = path.join(harnessRoot, 'benchmark/holdouts/ae-framework-stage008b-v1.json');
const holdout = parseJsonFile(holdoutPath);
const outputRoot = path.join(harnessRoot, 'benchmark-output/ae-framework');
fs.rmSync(outputRoot, { recursive: true, force: true });
fs.mkdirSync(outputRoot, { recursive: true });

function writeJson(rel, payload) {
  const target = path.join(outputRoot, rel);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`);
  return target;
}

function sha256File(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

const node = process.execPath;
const compareScript = path.join(aeRoot, 'scripts/agents/compare-github-work-state.mjs');
const handoffScript = path.join(aeRoot, 'scripts/agents/create-handoff.mjs');
const gateScript = path.join(aeRoot, 'scripts/actions/assurance-gate.mjs');
const fixture = (name) => path.join(aeRoot, name);
const expectedHead = holdout.expected_head_sha;

function runComparison(label, baseline, current, expected = expectedHead, outputOverride = null) {
  const reportPath = outputOverride ?? path.join(outputRoot, 'comparisons', `${label}.json`);
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  const result = runCommand(node, [
    compareScript,
    '--baseline', baseline,
    '--current', current,
    '--expected-head', expected,
    '--output', reportPath,
  ], { cwd: aeRoot });
  const report = fs.existsSync(reportPath) ? parseJsonFile(reportPath) : null;
  writeJson(`commands/${label}.json`, { ...result, reportPath, report });
  return { ...result, reportPath, report };
}

async function buildRevokedSnapshot() {
  const base = parseJsonFile(fixture(holdout.native_baseline_fixture));
  const revoked = structuredClone(base);
  revoked.generatedAt = '2026-09-06T03:15:00.000Z';
  revoked.issueState = holdout.authorization_revocation_mutation.issueState;
  revoked.issueStateReason = holdout.authorization_revocation_mutation.issueStateReason;
  const lib = await import(pathToFileURL(path.join(aeRoot, 'scripts/agents/github-work-state-lib.mjs')).href);
  revoked.snapshotDigest = lib.computeSnapshotDigest(revoked);
  const target = path.join(outputRoot, 'derived', 'revoked-authority.github-work-state.json');
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(revoked, null, 2)}\n`);
  return target;
}

function runGate(label, policyEvidence) {
  const workspace = path.join(aeRoot, '.benchmark-stage008b', label);
  fs.rmSync(workspace, { recursive: true, force: true });
  fs.mkdirSync(path.join(workspace, 'artifacts'), { recursive: true });
  fs.writeFileSync(path.join(workspace, 'artifacts', 'evidence.json'), `${JSON.stringify({
    evidence: [],
    policyEvidence,
    inputs: { benchmark: 'CVB-007-20260905', scenario: label },
  }, null, 2)}\n`);
  const result = runCommand(node, [
    gateScript,
    '--workspace', workspace,
    '--action-repo', aeRoot,
    '--profile', 'minimal',
    '--artifacts-dir', 'artifacts',
    '--output-dir', 'artifacts/assurance-gate',
    '--fail-on-block', 'true',
  ], { cwd: aeRoot });
  const gateResultPath = path.join(workspace, 'artifacts/assurance-gate/gate-result.json');
  const policyDecisionPath = path.join(workspace, 'artifacts/assurance-gate/policy-decision.json');
  const gateResult = fs.existsSync(gateResultPath) ? parseJsonFile(gateResultPath) : null;
  const policyDecision = fs.existsSync(policyDecisionPath) ? parseJsonFile(policyDecisionPath) : null;
  writeJson(`gates/${label}.json`, { ...result, gateResult, policyDecision });
  return { ...result, gateResult, policyDecision };
}

const s0Compare = runComparison('S0-current-authority', fixture(holdout.native_baseline_fixture), fixture(holdout.native_positive_fixture));
const s0Gate = runGate('S0-pass', ['postDeployVerify', 'qualityGates']);
const s1Compare = runComparison('S1-stale-head', fixture(holdout.native_baseline_fixture), fixture(holdout.native_stale_head_fixture));
const revokedSnapshot = await buildRevokedSnapshot();
const s2Compare = runComparison('S2-authorization-revoked', fixture(holdout.native_baseline_fixture), revokedSnapshot);

const authorityDir = path.join(aeRoot, '.benchmark-stage008b', 'S3-authority');
fs.rmSync(authorityDir, { recursive: true, force: true });
fs.mkdirSync(authorityDir, { recursive: true });
const s3Baseline = path.join(authorityDir, 'baseline.json');
const s3Current = path.join(authorityDir, 'current.json');
fs.copyFileSync(fixture(holdout.native_baseline_fixture), s3Baseline);
fs.copyFileSync(fixture(holdout.native_stale_head_fixture), s3Current);
const s3HandoffJson = path.join(aeRoot, '.benchmark-stage008b', 'S3-handoff', 'ae-handoff.json');
const s3HandoffMd = path.join(aeRoot, '.benchmark-stage008b', 'S3-handoff', 'ae-handoff.md');
fs.mkdirSync(path.dirname(s3HandoffJson), { recursive: true });
const s3Handoff = runCommand(node, [
  handoffScript,
  '--goal', 'Resume benchmark work only against current GitHub authority',
  '--current-status', 'Interrupted after prior verification; authority must be rechecked',
  '--authority-snapshot', path.relative(aeRoot, s3Baseline),
  '--output-json', path.relative(aeRoot, s3HandoffJson),
  '--output-md', path.relative(aeRoot, s3HandoffMd),
  '--generated-at', '2026-09-06T03:16:00.000Z',
  '--command-run', 'github-work-state:compare before continuation',
], { cwd: aeRoot });
const s3HandoffPayload = fs.existsSync(s3HandoffJson) ? parseJsonFile(s3HandoffJson) : null;
writeJson('handoff/S3-create.json', { ...s3Handoff, handoff: s3HandoffPayload });
const s3Compare = runComparison('S3-cold-reentry-stale', s3Baseline, s3Current);

const s4Compare = runComparison('S4-wrong-candidate-proof', fixture(holdout.native_baseline_fixture), fixture(holdout.native_wrong_candidate_fixture));

const s5Dir = path.join(aeRoot, '.benchmark-stage008b', 'S5-decision');
fs.rmSync(s5Dir, { recursive: true, force: true });
fs.mkdirSync(s5Dir, { recursive: true });
const s5CurrentDecisionPath = path.join(s5Dir, 'current-comparison.json');
const s5D0 = runComparison('S5-D0-stale', fixture(holdout.native_baseline_fixture), fixture(holdout.native_stale_head_fixture), expectedHead, s5CurrentDecisionPath);
const d0HashBefore = fs.existsSync(s5CurrentDecisionPath) ? sha256File(s5CurrentDecisionPath) : null;
const d0PayloadBefore = fs.existsSync(s5CurrentDecisionPath) ? parseJsonFile(s5CurrentDecisionPath) : null;
const s5D1 = runComparison('S5-D1-current', fixture(holdout.native_stale_head_fixture), fixture(holdout.native_stale_head_fixture), 'cccccccccccccccccccccccccccccccccccccccc', s5CurrentDecisionPath);
const d1HashAfter = fs.existsSync(s5CurrentDecisionPath) ? sha256File(s5CurrentDecisionPath) : null;
const d1PayloadAfter = fs.existsSync(s5CurrentDecisionPath) ? parseJsonFile(s5CurrentDecisionPath) : null;
const nativeDecisionFiles = fs.readdirSync(s5Dir).sort();
writeJson('lineage/S5-native-history-probe.json', {
  outputPath: s5CurrentDecisionPath,
  d0HashBefore,
  d0PayloadBefore,
  d1HashAfter,
  d1PayloadAfter,
  nativeDecisionFiles,
  priorDecisionStillPresentAsSeparateNativeArtifact: nativeDecisionFiles.length > 1,
});

const s6Compare = runComparison('S6-fresh-authority', fixture(holdout.native_stale_head_fixture), fixture(holdout.native_stale_head_fixture), 'cccccccccccccccccccccccccccccccccccccccc');
const s6Gate = runGate('S6-pass', ['postDeployVerify', 'qualityGates']);

const raw = {
  schema: 'metablooms-stage008b-ae-framework-raw/v1',
  benchmark_id: holdout.benchmark_id,
  variant_id: holdout.variant_id,
  run_mode: 'SCORED_HOLDOUT',
  competitor: holdout.competitor,
  pin: holdout.competitor_pin,
  process_model: 'Each compare/gate/handoff invocation executes as a separate Node process.',
  scenarios: {
    S0: { comparison: s0Compare, gate: s0Gate },
    S1: { comparison: s1Compare },
    S2: { comparison: s2Compare, revokedSnapshot },
    S3: { handoff: s3HandoffPayload, handoffCommandExit: s3Handoff.exitCode, comparison: s3Compare },
    S4: { comparison: s4Compare },
    S5: { d0: s5D0, d1: s5D1, nativeHistoryProbe: parseJsonFile(path.join(outputRoot, 'lineage/S5-native-history-probe.json')) },
    S6: { comparison: s6Compare, gate: s6Gate },
  },
};
writeJson('raw-summary.json', raw);

const checksums = [];
for (const rel of walk(outputRoot)) {
  if (rel === 'SHA256SUMS.txt') continue;
  checksums.push(`${sha256File(path.join(outputRoot, rel))}  ${rel}`);
}
fs.writeFileSync(path.join(outputRoot, 'SHA256SUMS.txt'), `${checksums.join('\n')}\n`);
console.log(JSON.stringify(raw, null, 2));

function walk(root, current = root) {
  const files = [];
  for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
    const full = path.join(current, entry.name);
    if (entry.isDirectory()) files.push(...walk(root, full));
    else if (entry.isFile()) files.push(path.relative(root, full).split(path.sep).join('/'));
  }
  return files.sort();
}
