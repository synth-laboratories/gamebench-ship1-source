#!/usr/bin/env bash
# GameBench dev-port, SANDBOXED: the porter runs in a seeded workspace-write
# workspace — it reads gold_python/, writes a Rust crate, runs `python check.py`
# to diff against the train oracle, and iterates. The crate is CAPTURED from the
# workspace; scoring grades ALL scenarios (train + held-out) against the oracle.
#
# Works with a codex-NATIVE model (gpt-5.5, real Responses API) OR a proxy model
# (deepseek/gemini): the jesterky proxy now translates agentic tool calls
# (Responses function_call ⇄ chat tool_calls), serves codex's /v1/models catalog,
# and round-trips Gemini's thought_signature — so proxy models drive the env too.
#
#   ./run_sandboxed.sh
#   SOURCE_TASK=frogs-singleplayer MODEL=gpt-5.5 ./run_sandboxed.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC="$HERE/dev_port_to_rust.sandboxed.json"
SOURCE_TASK="${SOURCE_TASK:-tictactoe-singleplayer}"
MODEL="${MODEL:-gpt-5.5}"
TRAIN="${TRAIN:-4}"
# Wall-clock cap per run (seconds). Slow proxy models (DeepSeek) get killed at the
# cap and scored on whatever crate they built so far — no run blocks indefinitely.
TIMEOUT="${TIMEOUT:-600}"
WS_BASE="$HOME/.cache/jesterky/workspaces"

echo "== bundling $SOURCE_TASK → sandbox workspace job (train=$TRAIN) =="
JOB="$HERE/job.sandbox.$SOURCE_TASK.json"
python3 "$HERE/bundle_sandbox_job.py" --source-task "$SOURCE_TASK" --train "$TRAIN" --out "$JOB"

MSLUG="$(echo "$MODEL" | tr '/' '_')"
MANIFEST="$HERE/port.sandbox.$MSLUG.$SOURCE_TASK.json"
SCORE="$HERE/score.sandbox.$MSLUG.$SOURCE_TASK.json"
echo "== porting in a workspace-write sandbox ($MODEL runs the env, ${TIMEOUT}s cap) =="
jesterky run "$SPEC" --actor codex --model "$MODEL" \
  --args-file "$JOB" --out "$MANIFEST" --run-id "dev-port-sbx-$SOURCE_TASK" &
JPID=$!
( sleep "$TIMEOUT"; kill -9 "$JPID" 2>/dev/null; pkill -9 -f "codex exec -m $MODEL" 2>/dev/null ) &
WDOG=$!
wait "$JPID"; RC=$?
kill "$WDOG" 2>/dev/null; wait "$WDOG" 2>/dev/null
[ "$RC" -ge 128 ] && echo "!! run capped at ${TIMEOUT}s (rc=$RC) — scoring partial workspace crate"

echo "== scoring the crate against the full NEV oracle =="
# Prefer the captured manifest; if the run was capped before capture, score the
# partial crate straight from its workspace dir (--candidate).
if python3 -c "import json,sys; d=json.load(open('$MANIFEST')); rec=d.get('recorded',[]); ok=bool(d.get('files')) or any(isinstance(r,dict) and r.get('outputs',{}).get('files') for r in rec); sys.exit(0 if ok else 1)" 2>/dev/null; then
  python3 "$HERE/score_port.py" --from-manifest "$MANIFEST" --source-task "$SOURCE_TASK" --out "$SCORE" || true
else
  # Workspace dirs embed the jesterky pid (sbx-<pid>-<n>) — scope the fallback to
  # THIS run so concurrent lanes never cross-score a partial crate.
  WS=$(ls -dt "$WS_BASE"/sbx-"$JPID"-* 2>/dev/null | head -1)
  echo "scoring partial workspace crate: $WS"
  python3 "$HERE/score_port.py" --candidate "$WS" --source-task "$SOURCE_TASK" --out "$SCORE" || true
fi
