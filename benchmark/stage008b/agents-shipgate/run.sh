#!/usr/bin/env bash
set -euo pipefail

SRC="${1:?usage: run.sh /path/to/source /path/to/venv}"
VENV="${2:?usage: run.sh /path/to/source /path/to/venv}"
PIN="c41571f2d11eb5864b487f0ace40a84dfa8f385b"
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
OUT="$ROOT/benchmark-output/agents-shipgate"
WORK="$ROOT/.benchmark-work/agents-shipgate"
FIXTURE="$ROOT/benchmark/holdouts/agents-shipgate-stage008b-v1.json"
SIGNER="$ROOT/benchmark/stage008b/agents-shipgate/sign_grant.py"
CLI="$VENV/bin/agents-shipgate"
PY="$VENV/bin/python"
HOST="/tmp/agents-shipgate-stage008b-host"
HOST_HOME="$HOST/home"
POLICY="$HOST_HOME/.config/agents-shipgate/human-authorization-trust-policy.json"
KEY="$HOST/reviewer-key.pem"
REPO_URL="https://github.com/blobertplunk-hue/Chat-Audit-Results.git"
S4_REF="refs/heads/benchmark/stage008b-agents-shipgate-target-s4-20260905"

rm -rf "$OUT" "$WORK" "$HOST"
mkdir -p "$OUT" "$WORK" "$HOST_HOME"
export HOME="$HOST_HOME"
export NO_COLOR=1

actual_pin="$(git -C "$SRC" rev-parse HEAD)"
printf '%s\n' "$actual_pin" > "$OUT/source-pin.txt"
[[ "$actual_pin" == "$PIN" ]] || { echo "PIN MISMATCH" >&2; exit 97; }
"$CLI" --version > "$OUT/version.txt"
cp "$FIXTURE" "$OUT/holdout-fixture.json"
VARIANT_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["variant_id"])' "$FIXTURE")"
TARGET_REF="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["target_ref"])' "$FIXTURE")"
printf '%s\n' "$VARIANT_ID" > "$OUT/variant-id.txt"

# Capture the checkout's scoped GitHub credential without printing or persisting it in evidence.
HEADER="$(git -C "$ROOT" config --get http.https://github.com/.extraheader || true)"
if [[ -z "$HEADER" ]]; then
  echo "GitHub checkout did not expose a scoped HTTPS extraheader" >&2
  exit 96
fi

run_capture() {
  local label="$1"; shift
  set +e
  "$@" >"$OUT/${label}.stdout.txt" 2>"$OUT/${label}.stderr.txt"
  local rc=$?
  set -e
  printf '%s\n' "$rc" >"$OUT/${label}.exit_code.txt"
  return 0
}

json_field() {
  local path="$1" expr="$2"
  python3 - "$path" "$expr" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1]))
cur=obj
for part in sys.argv[2].split('.'):
    if isinstance(cur,dict): cur=cur.get(part)
    else: cur=None; break
print('' if cur is None else (json.dumps(cur,sort_keys=True) if isinstance(cur,(dict,list)) else cur))
PY
}

remote_oid() {
  git -C "$WORK/repo" ls-remote origin "$1" | awk 'NR==1{print $1}'
}

copy_reports() {
  local sid="$1"
  rm -rf "$OUT/${sid}.reports"
  if [[ -d "$WORK/repo/agents-shipgate-reports" ]]; then
    cp -a "$WORK/repo/agents-shipgate-reports" "$OUT/${sid}.reports"
  fi
}

verify_current() {
  local label="$1"; shift
  rm -rf "$WORK/repo/agents-shipgate-reports"
  run_capture "$label" bash -lc "cd '$WORK/repo' && HOME='$HOST_HOME' NO_COLOR=1 '$CLI' verify --workspace . --config shipgate.yaml --base HEAD~1 --head HEAD --out agents-shipgate-reports --ci-mode advisory --no-plugins --json $*"
}

request_auth() {
  local label="$1" dest_ref="$2" lease="$3" out_request="$4"
  run_capture "$label" bash -lc "cd '$WORK/repo' && HOME='$HOST_HOME' NO_COLOR=1 '$CLI' authorization request --receipt agents-shipgate-reports/verification-receipt.json --artifacts-root agents-shipgate-reports --remote origin --destination-ref '$dest_ref' --expected-lease-oid '$lease' --out '$out_request' --json"
}

sign_grant() {
  local label="$1" request="$2" grant="$3" mode="$4"
  run_capture "$label" "$PY" "$SIGNER" --request "$request" --grant "$grant" --policy "$POLICY" --key "$KEY" --mode "$mode"
}

execute_auth() {
  local label="$1"
  run_capture "$label" bash -lc "cd '$WORK/repo' && HOME='$HOST_HOME' NO_COLOR=1 '$CLI' authorization execute --workspace . --receipt agents-shipgate-reports/verification-receipt.json --artifacts-root agents-shipgate-reports --json"
}

# Build the deterministic review-required fixture used by Shipgate's own authorization integration tests.
mkdir -p "$WORK/repo"
cat > "$WORK/repo/shipgate.yaml" <<'YAML'
version: "0.1"
project:
  name: stage008b-authorization-integration
agent:
  name: empty-test-agent
  declared_purpose:
    - exercise verifier authorization integration
  instructions: []
environment:
  target: local
tool_sources:
  - id: docs_tools
    type: mcp
    path: tools.json
agent_bindings:
  declarations:
    - agent: root
      complete: true
      tools:
        - {tool: docs.lookup, source_id: docs_tools}
      handoffs: []
      reason: reviewed local integration-test binding
permissions:
  scopes:
    - docs:read
action_surface:
  actions:
    - tool: docs.lookup
      effect: read
      scopes: [docs:read]
      authority:
        mode: scoped
        auth_type: oauth2
        credential_mode: delegated
YAML
cat > "$WORK/repo/tools.json" <<'JSON'
{
  "tools": [
    {
      "name": "docs.lookup",
      "description": "Look up metadata for one existing documentation article.",
      "inputSchema": {
        "type": "object",
        "properties": {"article_id": {"type": "string"}},
        "required": ["article_id"],
        "additionalProperties": false
      },
      "annotations": {"readOnlyHint": true},
      "auth": {"type": "oauth2", "scopes": ["docs:read"]},
      "owner": "docs-platform"
    }
  ]
}
JSON
git -C "$WORK/repo" init -q -b main
git -C "$WORK/repo" config user.email benchmark@example.invalid
git -C "$WORK/repo" config user.name "Stage008B Benchmark"
git -C "$WORK/repo" remote add origin "$REPO_URL"
git -C "$WORK/repo" config http.https://github.com/.extraheader "$HEADER"
git -C "$WORK/repo" add shipgate.yaml tools.json
git -C "$WORK/repo" commit -q -m baseline
python3 - "$WORK/repo/tools.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['tools'][0]['description']='Too short.'
open(p,'w').write(json.dumps(d,indent=2)+"\n")
PY
git -C "$WORK/repo" add tools.json
git -C "$WORK/repo" commit -q -m "introduce review item"
C0="$(git -C "$WORK/repo" rev-parse HEAD)"
printf '%s\n' "$C0" > "$OUT/C0.txt"

# S0: current target + current verification + valid externally signed authorization => exact push.
LEASE0="$(remote_oid "$TARGET_REF")"
printf '%s\n' "$LEASE0" > "$OUT/S0.target_before.txt"
verify_current S0.verify.initial
cp "$WORK/repo/agents-shipgate-reports/verifier.json" "$OUT/S0.verifier.initial.json"
REQUEST0="$OUT/S0.authorization-request.json"
GRANT0="$HOST/S0.authorization.json"
request_auth S0.request "$TARGET_REF" "$LEASE0" "$REQUEST0"
sign_grant S0.sign "$REQUEST0" "$GRANT0" valid
verify_current S0.verify.authorized "--authorization '$GRANT0'"
cp "$WORK/repo/agents-shipgate-reports/verifier.json" "$OUT/S0.verifier.authorized.json"
cp "$WORK/repo/agents-shipgate-reports/verification-receipt.json" "$OUT/S0.receipt.json"
cp "$WORK/repo/agents-shipgate-reports/human-authorization.json" "$OUT/S0.grant.canonical.json"
execute_auth S0.execute
remote_oid "$TARGET_REF" > "$OUT/S0.target_after.txt"
copy_reports S0

# S1: issue a valid grant against the now-current lease, then move the destination ref out-of-band.
LEASE1="$(remote_oid "$TARGET_REF")"
printf '%s\n' "$LEASE1" > "$OUT/S1.lease_at_grant.txt"
verify_current S1.verify.initial
REQUEST1="$OUT/S1.authorization-request.json"
GRANT1="$HOST/S1.authorization.json"
request_auth S1.request "$TARGET_REF" "$LEASE1" "$REQUEST1"
sign_grant S1.sign "$REQUEST1" "$GRANT1" valid
verify_current S1.verify.authorized "--authorization '$GRANT1'"
cp "$WORK/repo/agents-shipgate-reports/verifier.json" "$OUT/S1.verifier.authorized.json"
cp "$WORK/repo/agents-shipgate-reports/verification-receipt.json" "$OUT/S1.receipt.json"
cp "$WORK/repo/agents-shipgate-reports/human-authorization.json" "$OUT/S1.grant.canonical.json"
# Holdout perturbation: remote state changes after the grant is issued.
HOLDOUT_PATH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["remote_movement"]["path"])' "$FIXTURE")"
HOLDOUT_CONTENT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["remote_movement"]["content"], end="")' "$FIXTURE")"
mkdir -p "$ROOT/$(dirname "$HOLDOUT_PATH")"
printf '%s' "$HOLDOUT_CONTENT" > "$ROOT/$HOLDOUT_PATH"
git -C "$ROOT" add "$HOLDOUT_PATH"
git -C "$ROOT" -c user.email=benchmark@example.invalid -c user.name='Stage008B Remote Actor' commit -q -m "advance Shipgate holdout destination"
REMOTE_ADVANCE="$(git -C "$ROOT" rev-parse HEAD)"
git -C "$ROOT" push -q origin "HEAD:$TARGET_REF" --force
printf '%s\n' "$REMOTE_ADVANCE" > "$OUT/S1.target_advanced_to.txt"
execute_auth S1.execute_stale_lease
remote_oid "$TARGET_REF" > "$OUT/S1.target_after_attempt.txt"
copy_reports S1

# S2: the same exact request signed with an already-expired authority must not expose executable command authority.
GRANT2="$HOST/S2.authorization.expired.json"
sign_grant S2.sign_expired "$REQUEST1" "$GRANT2" expired
verify_current S2.verify.expired "--authorization '$GRANT2'"
cp "$WORK/repo/agents-shipgate-reports/verifier.json" "$OUT/S2.verifier.json"
copy_reports S2

# S4: bind valid evidence to C0 for a separate destination, then change local HEAD to C1 before execution.
git -C "$ROOT" push -q origin "HEAD:$S4_REF" --force
S4_LEASE="$(remote_oid "$S4_REF")"
printf '%s\n' "$S4_LEASE" > "$OUT/S4.target_before.txt"
verify_current S4.verify.initial
REQUEST4="$OUT/S4.authorization-request.json"
GRANT4="$HOST/S4.authorization.json"
request_auth S4.request "$S4_REF" "$S4_LEASE" "$REQUEST4"
sign_grant S4.sign "$REQUEST4" "$GRANT4" valid
verify_current S4.verify.authorized "--authorization '$GRANT4'"
cp "$WORK/repo/agents-shipgate-reports/verifier.json" "$OUT/S4.verifier.authorized.json"
cp "$WORK/repo/agents-shipgate-reports/verification-receipt.json" "$OUT/S4.receipt.json"
WRONG_PATH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["wrong_candidate"]["path"])' "$FIXTURE")"
WRONG_CONTENT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["wrong_candidate"]["content"], end="")' "$FIXTURE")"
mkdir -p "$WORK/repo/$(dirname "$WRONG_PATH")"
printf '%s' "$WRONG_CONTENT" > "$WORK/repo/$WRONG_PATH"
git -C "$WORK/repo" add "$WRONG_PATH"
git -C "$WORK/repo" commit -q -m "create wrong candidate C1"
C1="$(git -C "$WORK/repo" rev-parse HEAD)"
printf '%s\n' "$C1" > "$OUT/C1.txt"
execute_auth S4.execute_with_local_head_C1
remote_oid "$S4_REF" > "$OUT/S4.target_after.txt"
printf '%s\n' "$(git -C "$WORK/repo" rev-parse HEAD)" > "$OUT/S4.local_head_after.txt"
copy_reports S4

# S5 probe: establish whether the native output tree preserves a superseded decision lineage.
D0="$(json_field "$OUT/S4.verifier.authorized.json" decision_id)"
printf '%s\n' "$D0" > "$OUT/S5.D0.txt"

# S6: fresh candidate C2, fresh verification, fresh authorization against the current moved target.
FRESH_PATH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fresh_candidate"]["path"])' "$FIXTURE")"
FRESH_CONTENT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fresh_candidate"]["content"], end="")' "$FIXTURE")"
mkdir -p "$WORK/repo/$(dirname "$FRESH_PATH")"
printf '%s' "$FRESH_CONTENT" > "$WORK/repo/$FRESH_PATH"
python3 - "$WORK/repo/tools.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['tools'][0]['description']='No.'
open(p,'w').write(json.dumps(d,indent=2)+"\n")
PY
git -C "$WORK/repo" add "$FRESH_PATH" tools.json
git -C "$WORK/repo" commit -q -m "fresh candidate C2 after stale denial"
C2="$(git -C "$WORK/repo" rev-parse HEAD)"
printf '%s\n' "$C2" > "$OUT/C2.txt"
LEASE6="$(remote_oid "$TARGET_REF")"
printf '%s\n' "$LEASE6" > "$OUT/S6.target_before.txt"
verify_current S6.verify.initial
REQUEST6="$OUT/S6.authorization-request.json"
GRANT6="$HOST/S6.authorization.json"
request_auth S6.request "$TARGET_REF" "$LEASE6" "$REQUEST6"
sign_grant S6.sign "$REQUEST6" "$GRANT6" valid
verify_current S6.verify.authorized "--authorization '$GRANT6'"
cp "$WORK/repo/agents-shipgate-reports/verifier.json" "$OUT/S6.verifier.authorized.json"
cp "$WORK/repo/agents-shipgate-reports/verification-receipt.json" "$OUT/S6.receipt.json"
execute_auth S6.execute
remote_oid "$TARGET_REF" > "$OUT/S6.target_after.txt"
D1="$(json_field "$OUT/S6.verifier.authorized.json" decision_id)"
printf '%s\n' "$D1" > "$OUT/S5.D1.txt"
# Probe whether old D0 remains in the current native artifact tree after D1 supersedes it.
if grep -R -F -q -- "$D0" "$WORK/repo/agents-shipgate-reports"; then
  printf 'true\n' > "$OUT/S5.old_decision_present_in_current_native_outputs.txt"
else
  printf 'false\n' > "$OUT/S5.old_decision_present_in_current_native_outputs.txt"
fi
copy_reports S6

python3 - "$OUT" "$VARIANT_ID" "$TARGET_REF" "$S4_REF" <<'PY'
import json, pathlib, sys
out=pathlib.Path(sys.argv[1]); variant=sys.argv[2]

def text(name):
    p=out/name
    return p.read_text(errors='replace').strip() if p.exists() else None

def js(name):
    p=out/name
    if not p.exists(): return None
    try: return json.loads(p.read_text())
    except Exception: return None

def verifier(name):
    d=js(name) or {}
    auth=d.get('authorization') or {}
    control=d.get('control') or {}
    return {
      'decision_id': d.get('decision_id'),
      'decision': d.get('decision'),
      'merge_verdict': d.get('merge_verdict'),
      'authorization_status': auth.get('status'),
      'authorization_reason_codes': auth.get('reason_codes'),
      'authorization_command': bool(auth.get('command')),
      'control_state': control.get('state'),
      'control_must_stop': control.get('must_stop'),
      'allowed_next_commands_count': len(control.get('allowed_next_commands') or []),
    }
summary={
 'schema':'metablooms-stage008b-agents-shipgate-raw/v1',
 'run_mode':'SCORED_HOLDOUT',
 'benchmark_id':'CVB-007-20260905',
 'variant_id':variant,
 'competitor':'Agents Shipgate',
 'repository':'ThreeMoonsLab/agents-shipgate',
 'pin':'c41571f2d11eb5864b487f0ace40a84dfa8f385b',
 'version':text('version.txt'),
 'executed_scenarios':{
   'S0':{'verifier':verifier('S0.verifier.authorized.json'),'execute_rc':text('S0.execute.exit_code.txt'),'target_before':text('S0.target_before.txt'),'target_after':text('S0.target_after.txt'),'candidate':text('C0.txt')},
   'S1':{'verifier':verifier('S1.verifier.authorized.json'),'execute_rc':text('S1.execute_stale_lease.exit_code.txt'),'lease_at_grant':text('S1.lease_at_grant.txt'),'target_advanced_to':text('S1.target_advanced_to.txt'),'target_after_attempt':text('S1.target_after_attempt.txt'),'candidate':text('C0.txt')},
   'S2':{'verifier':verifier('S2.verifier.json'),'verify_rc':text('S2.verify.expired.exit_code.txt')},
   'S4':{'verifier':verifier('S4.verifier.authorized.json'),'execute_rc':text('S4.execute_with_local_head_C1.exit_code.txt'),'authorized_candidate':text('C0.txt'),'local_candidate_at_execute':text('C1.txt'),'target_before':text('S4.target_before.txt'),'target_after':text('S4.target_after.txt')},
   'S5':{'D0':text('S5.D0.txt'),'D1':text('S5.D1.txt'),'old_decision_present_in_current_native_outputs':text('S5.old_decision_present_in_current_native_outputs.txt')},
   'S6':{'verifier':verifier('S6.verifier.authorized.json'),'execute_rc':text('S6.execute.exit_code.txt'),'target_before':text('S6.target_before.txt'),'target_after':text('S6.target_after.txt'),'candidate':text('C2.txt')},
 },
 'not_executed':{'S3':'predeclared NOT_APPLICABLE: native Shipgate Git authorization gate is not a cross-session work-recovery system'},
 'destination_refs':{'primary':sys.argv[3],'s4':sys.argv[4]},
}
(out/'raw-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps(summary,indent=2,sort_keys=True))
PY

# Relocatable evidence checksums; exclude the checksum file itself.
(
  cd "$OUT"
  find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt
)
cat "$OUT/raw-summary.json"
