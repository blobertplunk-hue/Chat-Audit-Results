#!/usr/bin/env bash
set -euo pipefail

CASP_SRC="${1:?usage: run-casp.sh /path/to/casp-src}"
PIN="592a253cc16f346edf8537f4c40e4a90dceadc91"
CLI="$CASP_SRC/dist/cli.js"
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
OUT="$ROOT/benchmark-output/casp"
WORK="$ROOT/.benchmark-work/casp"

rm -rf "$OUT" "$WORK"
mkdir -p "$OUT" "$WORK"

actual_pin="$(git -C "$CASP_SRC" rev-parse HEAD)"
printf '%s\n' "$actual_pin" > "$OUT/source-pin.txt"
if [[ "$actual_pin" != "$PIN" ]]; then
  echo "PIN MISMATCH: expected $PIN got $actual_pin" >&2
  exit 97
fi
node "$CLI" --version > "$OUT/version.txt"

run_check() {
  local scenario="$1"
  local repo="$2"
  local stdout_file="$OUT/${scenario}.stdout.json"
  local stderr_file="$OUT/${scenario}.stderr.txt"
  local rc_file="$OUT/${scenario}.exit_code.txt"
  set +e
  (cd "$repo" && NO_COLOR=1 node "$CLI" check --json > "$stdout_file" 2> "$stderr_file")
  local rc=$?
  set -e
  printf '%s\n' "$rc" > "$rc_file"
}

write_state() {
  local repo="$1"
  local last_commit="$2"
  mkdir -p "$repo/casp"
  cat > "$repo/casp/state.json" <<JSON
{
  "casp_version": "0.17.0",
  "updated_at": "2026-09-05",
  "last_session_id": "pending",
  "last_commit": "$last_commit",
  "current_phase": "benchmark",
  "next_phase": null,
  "next_prompt": null,
  "phases_shipped": [],
  "phases_queued": [],
  "phases_backlog": []
}
JSON
}

# S0 — clean current state. CASP state points to the base commit; the only
# commit after it is the state-bump commit, which CASP explicitly accepts.
REPO="$WORK/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" config user.email benchmark@example.invalid
git -C "$REPO" config user.name "Stage008B Benchmark"
printf 'baseline\n' > "$REPO/app.txt"
git -C "$REPO" add app.txt
git -C "$REPO" commit -q -m "baseline"
BASE="$(git -C "$REPO" rev-parse --short HEAD)"
write_state "$REPO" "$BASE"
git -C "$REPO" add casp/state.json
git -C "$REPO" commit -q -m "record current CASP state"
STATE_BUMP="$(git -C "$REPO" rev-parse HEAD)"
printf '%s\n' "$BASE" > "$OUT/s0.recorded_base.txt"
printf '%s\n' "$STATE_BUMP" > "$OUT/s0.head.txt"
run_check S0 "$REPO"

# S1 — a legitimate code commit changes the trusted repository revision while
# the recorded CASP state remains unchanged.
printf 'changed-after-recorded-state\n' >> "$REPO/app.txt"
git -C "$REPO" add app.txt
git -C "$REPO" commit -q -m "out-of-band repository change"
CHANGED_HEAD="$(git -C "$REPO" rev-parse HEAD)"
printf '%s\n' "$CHANGED_HEAD" > "$OUT/s1.changed_head.txt"
run_check S1 "$REPO"

# S3 — cold re-entry: clone the stale repository into a fresh working tree and
# invoke a fresh CASP process without carrying process/session state.
FRESH="$WORK/fresh-reentry"
git clone -q "$REPO" "$FRESH"
run_check S3 "$FRESH"

# S6 — after the stale-state run, record the current code commit as the new
# trusted state and create the state-only bump commit. Then re-check.
CURRENT_CODE="$(git -C "$REPO" rev-parse --short HEAD)"
write_state "$REPO" "$CURRENT_CODE"
git -C "$REPO" add casp/state.json
git -C "$REPO" commit -q -m "refresh CASP state after repository change"
FRESH_STATE_HEAD="$(git -C "$REPO" rev-parse HEAD)"
printf '%s\n' "$CURRENT_CODE" > "$OUT/s6.recorded_base.txt"
printf '%s\n' "$FRESH_STATE_HEAD" > "$OUT/s6.head.txt"
run_check S6 "$REPO"

python3 - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
summary = {
    "schema": "metablooms-stage008b-casp-raw/v1",
    "competitor": "CASP",
    "repository": "ThalesGnimavo/casp",
    "pin": "592a253cc16f346edf8537f4c40e4a90dceadc91",
    "executed_scenarios": {},
    "not_executed": {
        "S2": "predeclared REQUIRES_PROBE; no native task-authorization/revocation primitive established",
        "S4": "predeclared NOT_APPLICABLE; CASP does not perform independent candidate qualification",
        "S5": "predeclared LIKELY_APPLICABLE; no native durable promotion-decision authority primitive established in the pinned probe"
    }
}
for sid in ("S0", "S1", "S3", "S6"):
    raw = json.loads((out / f"{sid}.stdout.json").read_text())
    rc = int((out / f"{sid}.exit_code.txt").read_text().strip())
    summary["executed_scenarios"][sid] = {
        "exit_code": rc,
        "verdict": raw.get("verdict"),
        "summary": raw.get("summary"),
        "findings": raw.get("findings", []),
    }
(out / "raw-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
PY

# Generate relocatable checksums: record basenames, not ephemeral runner paths.
(
  cd "$OUT"
  find . -maxdepth 1 -type f ! -name 'SHA256SUMS.txt' -printf '%f\n' \
    | sort \
    | xargs -r sha256sum > SHA256SUMS.txt
)
cat "$OUT/raw-summary.json"
