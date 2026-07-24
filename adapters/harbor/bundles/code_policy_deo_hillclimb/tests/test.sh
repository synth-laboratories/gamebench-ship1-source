#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${GAMEBENCH_WORKSPACE_ROOT:-/workspace}"
LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR="${WORKSPACE}/logs/verifier"
  mkdir -p "$LOG_DIR"
fi

OUTPUT_JSON="$LOG_DIR/result.json"
REWARD_PATH="$LOG_DIR/reward.txt"

python3 "$SCRIPT_DIR/score_hillclimb.py" \
  --workspace "$WORKSPACE" \
  --task-dir "${GAMEBENCH_TASK_DIR:-$WORKSPACE/gamebench/tasks/$GAMEBENCH_TASK}" \
  --output "$OUTPUT_JSON" \
  --reward "$REWARD_PATH"
