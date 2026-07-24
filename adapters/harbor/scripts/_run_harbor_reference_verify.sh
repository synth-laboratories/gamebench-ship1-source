#!/usr/bin/env bash
# Generic Harbor verify for registry-backed bundle families (code policy, cybernetic, puzzle).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

FAMILY="$1"
TASK_ID="$2"
shift 2 || true

PUZZLE_ID="${PUZZLE_ID:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --puzzle-id) PUZZLE_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

REG_FAMILY="$(registry_family "$FAMILY")"
load_task_env "$TASK_ID"
BUNDLE="$(eval_registry harbor-bundle "$REG_FAMILY" "$TASK_ID")"
TASK_ROOT="$(bundle_root "$BUNDLE")"
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-${BUNDLE}:latest}"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-${BUNDLE}-verify}"

mkdir -p "$OUT_DIR/logs/verifier"

BUILD_ARGS=(--build-arg "GAMEBENCH_TASK=$TASK_ID")
if [[ "$REG_FAMILY" == code_policy_opt || "$REG_FAMILY" == cybernetic_opt ]]; then
  BUILD_ARGS+=(--build-arg "CANDIDATE_SUBDIR=${CANDIDATE_SUBDIR:-}")
fi
if [[ "$REG_FAMILY" == code_policy_puzzles ]]; then
  BUILD_ARGS+=(--build-arg "PUZZLE_ID=${PUZZLE_ID:-puzzle_center_blind_v1}")
fi

docker build -t "$IMAGE" -f "$TASK_ROOT/environment/Dockerfile" "${BUILD_ARGS[@]}" "$GAMEBENCH_ROOT"

CONTAINER="$(
  docker run -d --rm \
    -e HARBOR_LOG_DIR=/logs/verifier \
    -e GAMEBENCH_WORKSPACE_ROOT=/workspace \
    -e GAMEBENCH_TASK="$TASK_ID" \
    -e GAMEBENCH_POLICY_SUITE="/workspace/gamebench/tasks/$TASK_ID/${GAMEBENCH_REGISTRY_policy_suite}" \
    -e GAMEBENCH_POLICY_BASELINE="/workspace/gamebench/tasks/$TASK_ID/${GAMEBENCH_REGISTRY_policy_baseline}" \
    -e GAMEBENCH_HILLCLIMB_EXTRA_ARGS="${GAMEBENCH_HILLCLIMB_EXTRA_ARGS:-}" \
    -e CANDIDATE_SUBDIR="${CANDIDATE_SUBDIR:-}" \
    -e GAMEBENCH_CYBERNETICS_MOCK="${GAMEBENCH_CYBERNETICS_MOCK:-1}" \
    "$IMAGE" \
    sleep infinity
)"
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT

docker exec "$CONTAINER" bash /task/solution/solve.sh
docker exec "$CONTAINER" bash /task/tests/test.sh

mkdir -p "$OUT_DIR/logs/verifier"
docker cp "$CONTAINER:/logs/verifier/." "$OUT_DIR/logs/verifier/"

echo ""
echo "reward: $(cat "$OUT_DIR/logs/verifier/reward.txt")"
echo "result: $OUT_DIR/logs/verifier/result.json"
