#!/usr/bin/env bash
# Generic Harbor Codex run for dev (per-env gold) bundles.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

TASK_ID="$1"
BUNDLE="$(eval_registry harbor-bundle dev "$TASK_ID")"
TASK_ROOT="$(bundle_root "$BUNDLE")"
WORKSPACE="$TASK_ROOT/workspace"
MODEL="${GAMEBENCH_HARBOR_MODEL:-openai/gpt-5.4-mini}"
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-${BUNDLE}:latest}"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-${BUNDLE}-codex}"

mkdir -p "$WORKSPACE" "$OUT_DIR/logs/verifier" "$WORKSPACE/spec" "$WORKSPACE/candidate"
if [[ -d "$TASK_ROOT/spec" ]]; then
  cp -a "$TASK_ROOT/spec/." "$WORKSPACE/spec/"
fi

if [[ ! -f "$CODEX_RUNNER" ]]; then
  echo "Missing codex runner: $CODEX_RUNNER" >&2
  exit 1
fi

docker build -t "$IMAGE" -f "$TASK_ROOT/environment/Dockerfile" "$GAMEBENCH_ROOT"

ROLLOUT_JSON="$OUT_DIR/rollout.json"
RESULT_JSON="$OUT_DIR/rollout_result.json"

python3 - "$ROLLOUT_JSON" "$WORKSPACE" "$MODEL" "$BUNDLE" <<'PY'
import json
import sys
from pathlib import Path

workspace = Path(sys.argv[2])
model = sys.argv[3]
bundle = sys.argv[4]
payload = {
    "trace_correlation_id": f"gamebench-harbor-{bundle}",
    "deployment_name": f"gamebench_{bundle}",
    "harbor_agent": {
        "name": "codex",
        "model_name": model,
        "kwargs": {"reasoning_effort": "medium"},
    },
    "task_metadata": {"workspace_dir": str(workspace.resolve())},
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

echo "Running Codex Harbor dev task=$TASK_ID bundle=$BUNDLE model=$MODEL"
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
