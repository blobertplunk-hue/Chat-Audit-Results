import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const action = process.argv[2];
const csm = process.env.CSM_SRC;
const dbPath = process.env.CSM_DB;
const workspace = process.env.CSM_WORKSPACE;
const projectId = process.env.CSM_PROJECT_ID;
const d0Summary = process.env.CSM_D0;
const d1Summary = process.env.CSM_D1;
if (!action || !csm || !dbPath || !workspace || !projectId) throw new Error('missing benchmark environment');

const { Database } = await import(pathToFileURL(path.join(csm, 'dist/database.js')).href);
const { AgentBookEventStore } = await import(pathToFileURL(path.join(csm, 'dist/agentbook-event-store.js')).href);
const { AgentBookStateProjector } = await import(pathToFileURL(path.join(csm, 'dist/agentbook-state-projector.js')).href);
const { AgentBookRulesStore } = await import(pathToFileURL(path.join(csm, 'dist/agentbook-rules-store.js')).href);
const { AgentBookSummaryGenerator } = await import(pathToFileURL(path.join(csm, 'dist/agentbook-summary-generator.js')).href);
const { generateFrontPage } = await import(pathToFileURL(path.join(csm, 'dist/agentbook-frontpage.js')).href);

const database = new Database({ databaseProvider: 'sqlite', sqlitePath: dbPath });
await database.connect();
const pool = database.getPool();
const events = new AgentBookEventStore(pool);
const projector = new AgentBookStateProjector(pool, events);
const rules = new AgentBookRulesStore(pool);
const summaries = new AgentBookSummaryGenerator(pool, events);

function sha256File(p) {
  return createHash('sha256').update(readFileSync(p)).digest('hex');
}
function currentPath() { return path.join(workspace, 'current-state.txt'); }
async function snapshot() {
  const persistedState = await projector.getState(projectId);
  const projectedState = await projector.project(projectId);
  const decisionEvents = await events.listEvents({ projectId, eventType: 'decision', limit: 100 });
  const verificationEvents = await events.listEvents({ projectId, eventType: 'verification_evidence', limit: 100 });
  const recentEvents = await events.getRecentEvents(projectId, 20);
  const latestSummary = await summaries.getLatestSummary(projectId);
  const activeRules = await rules.getActiveRules();
  const frontPage = generateFrontPage(projectedState, latestSummary, activeRules, recentEvents);
  return { persistedState, projectedState, decisionEvents, verificationEvents, recentEvents, frontPage };
}

let out;
if (action === 'seed') {
  const r0 = sha256File(currentPath());
  const session = await events.append({ projectId, sessionId: 'session-A', eventType: 'session_start', summary: 'Seed session A against R0', metadata: { baselineSha256: r0 } });
  const goal = await events.append({ projectId, sessionId: 'session-A', eventType: 'goal_set', summary: 'Continue work against baseline R0', metadata: { goal: 'Continue work against baseline R0', baselineSha256: r0, nextAction: 'Resume scoped work after interruption' } });
  const verification = await events.append({ projectId, sessionId: 'session-A', eventType: 'verification_evidence', summary: 'Q0 verification evidence for R0', evidenceRefs: [`sha256:${r0}`], files: ['current-state.txt'], metadata: { baselineSha256: r0, qualification: 'Q0' } });
  const decision = await events.append({ projectId, sessionId: 'session-A', eventType: 'decision', summary: d0Summary, evidenceRefs: [`sha256:${r0}`, verification.eventId], files: ['current-state.txt'], metadata: { baselineSha256: r0, decision: 'keep', decisionId: 'D0' } });
  const state = await projector.project(projectId);
  out = { action, processPid: process.pid, r0, sessionId: session.eventId, goalId: goal.eventId, verificationId: verification.eventId, d0EventId: decision.eventId, state };
} else if (action === 'reentry') {
  out = { action, processPid: process.pid, workspaceSha256ObservedByHarnessPhase: sha256File(currentPath()), ...(await snapshot()) };
} else if (action === 'supersede') {
  const r1 = sha256File(currentPath());
  const goal = await events.append({ projectId, sessionId: 'session-B', eventType: 'goal_set', summary: 'Continue work against baseline R1', metadata: { goal: 'Continue work against baseline R1', baselineSha256: r1, nextAction: 'Use current R1 state' } });
  const decision = await events.append({ projectId, sessionId: 'session-B', eventType: 'decision', summary: d1Summary, evidenceRefs: [`sha256:${r1}`], files: ['current-state.txt'], metadata: { baselineSha256: r1, decision: 'keep', decisionId: 'D1' } });
  const state = await projector.project(projectId);
  out = { action, processPid: process.pid, r1, d1EventId: decision.eventId, r1GoalId: goal.eventId, state };
} else if (action === 'lineage') {
  const snap = await snapshot();
  const newestFirst = snap.decisionEvents;
  const oldest = [...newestFirst].reverse()[0];
  const sinceD0 = oldest ? await events.getEventsSince(projectId, oldest.eventId) : [];
  out = { action, processPid: process.pid, workspaceSha256ObservedByHarnessPhase: sha256File(currentPath()), ...snap, sinceD0 };
} else {
  throw new Error(`unknown action ${action}`);
}
await database.close();
process.stdout.write(JSON.stringify(out, null, 2) + '\n');
