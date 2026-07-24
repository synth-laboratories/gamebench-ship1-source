#!/usr/bin/env bash
# Run Harbor Codex agent on a GameBench policy-puzzle diagnosis task.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_ROOT="$HARBOR_BUNDLE_ROOT/policy_puzzle_diagnosis"
WORKSPACE="$TASK_ROOT/workspace"
EVALS_ROOT="${GAMEBENCH_EVALS_ROOT:-$HOME/Documents/GitHub/evals}"
CODEX_RUNNER="$EVALS_ROOT/containers/harbor/codex_harbor_runner.py"
GAMEBENCH_TASK="${GAMEBENCH_TASK:-tictactoe-singleplayer}"
PUZZLE_ID="${PUZZLE_ID:-puzzle_center_blind_v1}"
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-policy-puzzle:latest}"
MODEL="${GAMEBENCH_HARBOR_MODEL:-openai/gpt-5.4-mini}"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-policy-puzzle-codex}"

mkdir -p "$WORKSPACE" "$OUT_DIR/logs/verifier" "$WORKSPACE/traces"

docker build \
  -t "$IMAGE" \
  -f "$TASK_ROOT/environment/Dockerfile" \
  --build-arg "GAMEBENCH_TASK=$GAMEBENCH_TASK" \
  --build-arg "PUZZLE_ID=$PUZZLE_ID" \
  "$GAMEBENCH_ROOT"

# Seed agent-visible puzzle assets into the host workspace (mirrors container /workspace).
docker run --rm \
  "$IMAGE" \
  bash -lc 'tar -C /workspace -cf - .' | tar -C "$WORKSPACE" -xf -

ROLLOUT_JSON="$OUT_DIR/rollout.json"
RESULT_JSON="$OUT_DIR/rollout_result.json"

python3 - "$ROLLOUT_JSON" "$WORKSPACE" "$MODEL" <<'PY'
import json
import sys
from pathlib import Path

workspace = Path(sys.argv[2])
model = sys.argv[3]
payload = {
    "trace_correlation_id": f"gamebench-harbor-policy-puzzle-{workspace.name}",
    "deployment_name": "gamebench_policy_puzzle_diagnosis",
    "harbor_agent": {
        "name": "codex",
        "model_name": model,
        "kwargs": {"reasoning_effort": "medium"},
    },
    "task_metadata": {"workspace_dir": str(workspace.resolve())},
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

if [[ ! -f "$CODEX_RUNNER" ]]; then
  echo "Missing codex runner: $CODEX_RUNNER" >&2
  exit 1
fi

echo "Running Codex Harbor agent model=$MODEL task=$GAMEBENCH_TASK puzzle=$PUZZLE_ID"
python3 "$CODEX_RUNNER" \
  --input "$ROLLOUT_JSON" \
  --output "$RESULT_JSON" \
  --task-root "$TASK_ROOT"

echo ""
echo "=== Verifier (policy puzzle diagnosis) ==="
export HARBOR_LOG_DIR="$OUT_DIR/logs/verifier"
export GAMEBENCH_WORKSPACE_ROOT="$WORKSPACE"
bash "$TASK_ROOT/tests/test.sh"

echo ""
echo "reward: $(cat "$OUT_DIR/logs/verifier/reward.txt")"
echo "result: $OUT_DIR/logs/verifier/result.json"
echo "rollout: $RESULT_JSON"
