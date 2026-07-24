#!/usr/bin/env bash
# Harbor pipeline smoke — reference solution staged as candidate, no Codex required.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_ROOT="$HARBOR_BUNDLE_ROOT/crafter_singleplayer_gold"
WORKSPACE="$TASK_ROOT/workspace"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-crafter-smoke}"
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-crafter-gold:latest}"

mkdir -p "$WORKSPACE/candidate" "$WORKSPACE/spec" "$OUT_DIR/logs/verifier"
if [[ -d "$TASK_ROOT/spec" ]]; then
  cp -a "$TASK_ROOT/spec/." "$WORKSPACE/spec/"
fi

docker build -t "$IMAGE" -f "$TASK_ROOT/environment/Dockerfile" "$GAMEBENCH_ROOT"

echo "=== Stage reference solution into workspace/candidate ==="
docker run --rm \
  -v "$TASK_ROOT:/task:ro" \
  -v "$WORKSPACE:/workspace" \
  "$IMAGE" \
  bash /task/solution/solve.sh

echo ""
echo "=== Verifier (spectrum) ==="
export HARBOR_LOG_DIR="$OUT_DIR/logs/verifier"
export GAMEBENCH_CANDIDATE_ROOT="$WORKSPACE/candidate"
bash "$TASK_ROOT/tests/test.sh"

REWARD="$(cat "$OUT_DIR/logs/verifier/reward.txt")"
echo ""
echo "harbor_smoke_reward=$REWARD"
if [[ "$REWARD" != "1.0" && "$REWARD" != "1" ]]; then
  echo "expected reward 1.0" >&2
  exit 1
fi
