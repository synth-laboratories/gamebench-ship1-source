#!/usr/bin/env bash
# Run Harbor Codex agent on GameBench Crafter gold rebuild task.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_ROOT="$HARBOR_BUNDLE_ROOT/crafter_singleplayer_gold"
WORKSPACE="$TASK_ROOT/workspace"
EVALS_ROOT="${GAMEBENCH_EVALS_ROOT:-$HOME/Documents/GitHub/evals}"
CODEX_RUNNER="$EVALS_ROOT/core/harbor/runner/codex_harbor_runner.py"
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-crafter-gold:latest}"
MODEL="${GAMEBENCH_HARBOR_MODEL:-openai/gpt-5.4-mini}"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-crafter}"

mkdir -p "$WORKSPACE" "$OUT_DIR/logs/verifier" "$WORKSPACE/spec" "$WORKSPACE/candidate"
if [[ -d "$TASK_ROOT/spec" ]]; then
  cp -a "$TASK_ROOT/spec/." "$WORKSPACE/spec/"
fi

docker build -t "$IMAGE" -f "$TASK_ROOT/environment/Dockerfile" "$GAMEBENCH_ROOT"

ROLLOUT_JSON="$OUT_DIR/rollout.json"
RESULT_JSON="$OUT_DIR/rollout_result.json"

cat > "$ROLLOUT_JSON" <<EOF
{
  "trace_correlation_id": "gamebench-harbor-crafter-$(date +%s)",
  "deployment_name": "gamebench_crafter_singleplayer_gold",
  "harbor_agent": {
    "name": "codex",
    "model_name": "$MODEL",
    "kwargs": {
      "reasoning_effort": "medium"
    }
  },
  "task_metadata": {
    "workspace_dir": "$WORKSPACE"
  }
}
EOF

if [[ ! -f "$CODEX_RUNNER" ]]; then
  echo "Missing codex runner: $CODEX_RUNNER" >&2
  exit 1
fi

echo "Running Codex Harbor agent model=$MODEL"
python3 "$CODEX_RUNNER" \
  --input "$ROLLOUT_JSON" \
  --output "$RESULT_JSON" \
  --task-root "$TASK_ROOT"

echo ""
echo "=== Verifier (spectrum) ==="
export HARBOR_LOG_DIR="$OUT_DIR/logs/verifier"
export GAMEBENCH_CANDIDATE_ROOT="$WORKSPACE/candidate"
bash "$TASK_ROOT/tests/test.sh"

echo ""
echo "reward: $(cat "$OUT_DIR/logs/verifier/reward.txt")"
echo "result: $OUT_DIR/logs/verifier/result.json"
echo "rollout: $RESULT_JSON"
