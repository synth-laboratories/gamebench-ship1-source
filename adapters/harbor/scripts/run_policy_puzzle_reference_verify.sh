#!/usr/bin/env bash
# Build + verify a GameBench policy-puzzle Harbor bundle (reference solution, no Codex).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_ROOT="$HARBOR_BUNDLE_ROOT/policy_puzzle_diagnosis"
GAMEBENCH_TASK="${GAMEBENCH_TASK:-tictactoe-singleplayer}"
PUZZLE_ID="${PUZZLE_ID:-puzzle_center_blind_v1}"
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-policy-puzzle:latest}"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-policy-puzzle}"

mkdir -p "$OUT_DIR/logs/verifier"

docker build \
  -t "$IMAGE" \
  -f "$TASK_ROOT/environment/Dockerfile" \
  --build-arg "GAMEBENCH_TASK=$GAMEBENCH_TASK" \
  --build-arg "PUZZLE_ID=$PUZZLE_ID" \
  "$GAMEBENCH_ROOT"

CONTAINER="$(
  docker run -d --rm \
    -e HARBOR_LOG_DIR=/logs/verifier \
    -e GAMEBENCH_WORKSPACE_ROOT=/workspace \
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
