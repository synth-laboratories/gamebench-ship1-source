#!/usr/bin/env bash
# run_gelo_local.sh — local GELO on GameBench Rogue rust gold (DeepSeek v4 flash).
#
# Brings up:
#   1. Rogue rust gold HTTP (:8101)
#   2. ReAct container proxying rust gold (:8102)
# Then runs optimizers-beta `run-goex` against the committed smoke config.
#
# Usage:
#   DEEPSEEK_API_KEY=... scripts/run_gelo_local.sh [RUN_ID] [CONFIG_PATH]
#
# Local GELO artifacts default to /tmp/reports/goex_runs (Codex proposers break under
# ~/Documents). Override with GOEX_ARTIFACTS_DIR.
set -euo pipefail

TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_DIR"

RUN_ID="${1:-rogue_goex_local_$(date +%Y%m%d_%H%M%S)}"
CONFIG_PATH="${2:-configs/goex_rogue_gamebench_deepseek_smoke.json}"
CONFIG_ABS="$(cd "$(dirname "$CONFIG_PATH")" && pwd)/$(basename "$CONFIG_PATH")"
GOLD_PORT="${GOLD_PORT:-8101}"
PORT="${PORT:-8102}"
OPTIMIZERS_BETA="${OPTIMIZERS_BETA:-$HOME/Documents/GitHub/optimizers-beta}"
GOEX_ARTIFACTS_DIR="${GOEX_ARTIFACTS_DIR:-/tmp/reports/goex_runs}"
mkdir -p "$GOEX_ARTIFACTS_DIR"

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "ERROR: DEEPSEEK_API_KEY is required (policy + proposers use deepseek-v4-flash)." >&2
  exit 1
fi

python3.11 -m pip install -q -r "$TASK_DIR/containers/react/requirements.txt" 2>/dev/null || true

GOEX_BIN="${GOEX_BIN:-}"
if [[ -z "$GOEX_BIN" ]]; then
  for cand in "$OPTIMIZERS_BETA/target/release/optimizers-beta" "$OPTIMIZERS_BETA/target/debug/optimizers-beta"; do
    if [[ -x "$cand" ]]; then GOEX_BIN="$cand"; break; fi
  done
fi
run_goex() {
  if [[ -n "$GOEX_BIN" ]]; then
    "$GOEX_BIN" run-goex "$@"
  else
    ( cd "$OPTIMIZERS_BETA" && cargo run --quiet -- run-goex "$@" )
  fi
}

GOLD_PID=""
CONTAINER_PID=""
cleanup() {
  if [[ -n "$CONTAINER_PID" && "${KEEP_CONTAINER:-0}" != "1" ]]; then
    kill "$CONTAINER_PID" 2>/dev/null || true
  fi
  if [[ -n "$GOLD_PID" && "${KEEP_GOLD:-0}" != "1" ]]; then
    kill "$GOLD_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if curl -s --max-time 3 "http://127.0.0.1:${GOLD_PORT}/health" >/dev/null 2>&1; then
  echo "Rust gold already healthy on :${GOLD_PORT}." >&2
else
  echo "Starting Rogue rust gold on :${GOLD_PORT}..." >&2
  python3 scripts/run_service.py --lane rust --host 127.0.0.1 --port "$GOLD_PORT" \
    > "/tmp/rogue_gold_${GOLD_PORT}.log" 2>&1 &
  GOLD_PID=$!
  for _ in $(seq 1 60); do
    if curl -s --max-time 2 "http://127.0.0.1:${GOLD_PORT}/health" >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
  if ! curl -s --max-time 3 "http://127.0.0.1:${GOLD_PORT}/health" >/dev/null 2>&1; then
    echo "ERROR: rust gold failed health on :${GOLD_PORT}" >&2
    tail -20 "/tmp/rogue_gold_${GOLD_PORT}.log" >&2 || true
    exit 1
  fi
fi

export ROGUE_GOLD_URL="http://127.0.0.1:${GOLD_PORT}"
if curl -s --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "ReAct container already healthy on :${PORT}." >&2
else
  echo "Starting Rogue ReAct container on :${PORT} (gold=${ROGUE_GOLD_URL})..." >&2
  PYTHONPATH=".:gold_python:shared" PORT="$PORT" ROGUE_GOLD_URL="$ROGUE_GOLD_URL" \
    python3.11 -m containers.react.rogue_singleplayer_container \
    > "/tmp/rogue_react_${PORT}.log" 2>&1 &
  CONTAINER_PID=$!
  for _ in $(seq 1 40); do
    if curl -s --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
  if ! curl -s --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "ERROR: ReAct container failed health on :${PORT}" >&2
    tail -20 "/tmp/rogue_react_${PORT}.log" >&2 || true
    exit 1
  fi
fi

echo "Running GELO: run_id=${RUN_ID} config=${CONFIG_ABS} artifacts_dir=${GOEX_ARTIFACTS_DIR}" >&2
GOEX_EXIT=0
run_goex --config "$CONFIG_ABS" --run-id "$RUN_ID" --artifacts-dir "$GOEX_ARTIFACTS_DIR" || GOEX_EXIT=$?

ART_DIR="${GOEX_ARTIFACTS_DIR}/${RUN_ID}/artifacts"
RUN_ROOT="${GOEX_ARTIFACTS_DIR}/${RUN_ID}"
echo ""
if [[ "$GOEX_EXIT" -ne 0 ]]; then
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" >&2
  echo "!! GELO RUN FAILED (exit=${GOEX_EXIT}) run_id=${RUN_ID}" >&2
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" >&2
fi
echo "===== GELO run summary (${RUN_ID}) ====="
if [[ -f ../crafter-singleplayer/scripts/summarize_goex_run.py ]]; then
  python3.11 ../crafter-singleplayer/scripts/summarize_goex_run.py "$ART_DIR" || true
fi
if [[ "$GOEX_EXIT" -ne 0 ]]; then
  if [[ -f "${ART_DIR}/goex_failure_report.json" ]]; then
    echo "Failure report: ${ART_DIR}/goex_failure_report.json" >&2
  elif [[ -f "${RUN_ROOT}/state/tick_state.json" ]]; then
    echo "Tick state (stop_reason): ${RUN_ROOT}/state/tick_state.json" >&2
  fi
  exit "$GOEX_EXIT"
fi
echo "Artifacts: $ART_DIR"
