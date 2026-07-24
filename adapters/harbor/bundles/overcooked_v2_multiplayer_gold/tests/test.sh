#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

CANDIDATE_ROOT="${GAMEBENCH_CANDIDATE_ROOT:-/workspace/candidate}"
OUTPUT_JSON="$LOG_DIR/result.json"
REWARD_PATH="$LOG_DIR/reward.txt"
LANE_ROOT="/tmp/gamebench_overcooked_v2_lane"

if [[ ! -f "$CANDIDATE_ROOT/scripts/run_service.py" ]]; then
  echo '{"error":"missing candidate scripts/run_service.py","harbor_reward":0.0}' > "$OUTPUT_JSON"
  echo 0 > "$REWARD_PATH"
  exit 1
fi

rm -rf "$LANE_ROOT"
mkdir -p "$LANE_ROOT/scripts" "$LANE_ROOT/fixtures/gold"
cp /task/tests/spectrum_eval.py "$LANE_ROOT/scripts/spectrum_eval.py"
cp -a /task/tests/fixtures/gold/. "$LANE_ROOT/fixtures/gold/"
cp -a /task/reference/gold_python "$LANE_ROOT/gold_python"
cp -a /task/reference/shared "$LANE_ROOT/shared"

export PYTHONPATH="$LANE_ROOT"
export GAMEBENCH_ROOT="/task"
python3 "$LANE_ROOT/scripts/spectrum_eval.py" \
  --lane http \
  --service-lane python \
  --candidate-root "$CANDIDATE_ROOT" \
  --candidate-port "${GAMEBENCH_CANDIDATE_PORT:-19094}" \
  --output "$OUTPUT_JSON"

python3 - "$OUTPUT_JSON" "$REWARD_PATH" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
reward = float(report.get("harbor_reward", 0.0))
Path(sys.argv[2]).write_text(str(reward), encoding="utf-8")
print(f"harbor_reward={reward}")
PY
