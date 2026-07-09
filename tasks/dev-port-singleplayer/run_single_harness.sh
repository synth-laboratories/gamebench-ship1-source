#!/usr/bin/env bash
# GameBench dev-port, SINGLE-HARNESS arm: the same port task as run_sandboxed.sh
# but with NO jesterky workflow — one bare `codex exec` session in a seeded dir.
# Same files, same porter prompt, same wall-clock cap; scored the same way.
# Measures what the workflow substrate adds/costs vs a raw agent harness.
#
#   SOURCE_TASK=sokoban-singleplayer MODEL=gpt-5.5 ./run_single_harness.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_TASK="${SOURCE_TASK:-sokoban-singleplayer}"
MODEL="${MODEL:-gpt-5.5}"
TRAIN="${TRAIN:-4}"
TIMEOUT="${TIMEOUT:-600}"
ATTEMPT="${ATTEMPT:-sh1}"

MSLUG="$(echo "$MODEL" | tr '/' '_')"
JOB="$HERE/job.single.$MSLUG.$SOURCE_TASK.json"
SCORE="$HERE/score.single.$MSLUG.$SOURCE_TASK.r$ATTEMPT.json"
META="$HERE/meta.single.$MSLUG.$SOURCE_TASK.r$ATTEMPT.json"
WS="$(mktemp -d "${TMPDIR:-/tmp}/devport-single-$MSLUG-XXXXXX")"

echo "== bundling $SOURCE_TASK (train=$TRAIN) and seeding $WS =="
python3 "$HERE/bundle_sandbox_job.py" --source-task "$SOURCE_TASK" --train "$TRAIN" --out "$JOB"
python3 - "$JOB" "$WS" <<'PY'
import json, sys, pathlib
job = json.load(open(sys.argv[1]))["job"]
root = pathlib.Path(sys.argv[2])
for f in job["files"]:
    p = root / f["path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f["content"])
print(f"seeded {len(job['files'])} files")
PY

PROMPT="$(cat "$HERE/single_harness_prompt.txt")"

# Proxy models route through the same jesterky proxy the workflow uses, so the
# harness is identical across models; only the orchestration layer differs.
PROXY_PID=""
CODEX_ARGS=(-m "$MODEL")
if [[ "$MODEL" == */* ]]; then
  PORT=$((49500 + RANDOM % 1000))
  jesterky-proxy --listen "127.0.0.1:$PORT" >/dev/null 2>&1 &
  PROXY_PID=$!
  sleep 1
  CODEX_ARGS=(-m "$MODEL" -c "model_providers.jesterky.base_url=http://127.0.0.1:$PORT/v1" -c "model_providers.jesterky.name=jesterky" -c "model_providers.jesterky.wire_api=responses" -c "model_provider=jesterky")
fi

echo "== single-harness port ($MODEL, ${TIMEOUT}s cap) =="
T0=$(date +%s)
codex exec "${CODEX_ARGS[@]}" --sandbox workspace-write --skip-git-repo-check \
  -C "$WS" -o "$WS/.final_msg.txt" "$PROMPT" >"$WS/.codex_out.log" 2>&1 &
CPID=$!
( sleep "$TIMEOUT"; kill -9 "$CPID" 2>/dev/null ) & WDOG=$!
wait "$CPID"; RC=$?
kill "$WDOG" 2>/dev/null; wait "$WDOG" 2>/dev/null
T1=$(date +%s)
[ -n "$PROXY_PID" ] && kill "$PROXY_PID" 2>/dev/null
[ "$RC" -ge 128 ] && echo "!! capped at ${TIMEOUT}s — scoring partial crate"

echo "== scoring =="
python3 "$HERE/score_port.py" --candidate "$WS" --source-task "$SOURCE_TASK" --out "$SCORE" || true

# usage: sum token_count events from the codex session this run created
TOKENS=$(python3 - "$WS/.codex_out.log" <<'PY'
import re, sys
txt = open(sys.argv[1], errors="ignore").read()
m = re.findall(r"tokens used[:\s]+([\d,]+)", txt)
print(m[-1].replace(",", "") if m else "")
PY
)
python3 - "$SCORE" "$META" "$((T1-T0))" "$TOKENS" "$MODEL" "$SOURCE_TASK" "$RC" <<'PY'
import json, sys
score_path, meta_path, secs, tokens, model, task, rc = sys.argv[1:8]
try:
    s = json.load(open(score_path))
except Exception:
    s = {}
json.dump({
    "arm": "single_harness", "model": model, "source_task": task,
    "wall_seconds": int(secs), "tokens": int(tokens) if tokens else None,
    "capped": int(rc) >= 128,
    "passed": s.get("passed"), "total": s.get("total"),
}, open(meta_path, "w"), indent=2)
print(open(meta_path).read())
PY
echo "workspace kept at $WS (delete after review)"
