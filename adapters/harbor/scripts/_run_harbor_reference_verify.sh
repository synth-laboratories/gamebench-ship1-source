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
ensure_policy_sandbox_image
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

if [[ "$REG_FAMILY" == code_policy_opt ]]; then
  WORKSPACE="$OUT_DIR/workspace"
  rm -rf "$WORKSPACE"
  mkdir -p "$WORKSPACE" "$OUT_DIR/logs/verifier"
  docker run --rm "$IMAGE" bash -lc 'tar -C /workspace -cf - .' | tar -C "$WORKSPACE" -xf -
  bash "$SCRIPT_DIR/prepare_code_policy_workspace.sh" \
    "$WORKSPACE" \
    "$TASK_ID" \
    "${CANDIDATE_SUBDIR:-}" \
    "$TASK_ROOT" \
    "${GAMEBENCH_REGISTRY_policy_baseline}"

  REFERENCE="$TASK_ROOT/solution/references/$TASK_ID/heuristic_policy.py"
  if [[ ! -f "$REFERENCE" && "$TASK_ID" == "tictactoe-singleplayer" ]]; then
    REFERENCE="$TASK_ROOT/solution/reference_heuristic_policy.py"
  fi
  if [[ ! -f "$REFERENCE" ]]; then
    echo "missing bundled reference policy for task $TASK_ID: $REFERENCE" >&2
    exit 1
  fi
  DEST="$WORKSPACE/candidates/${CANDIDATE_SUBDIR:-}/candidate_reference"
  mkdir -p "$DEST"
  cp "$REFERENCE" "$DEST/heuristic_policy.py"

  export HARBOR_LOG_DIR="$OUT_DIR/logs/verifier"
  export GAMEBENCH_WORKSPACE_ROOT="$WORKSPACE"
  export GAMEBENCH_ROOT="$WORKSPACE/gamebench"
  export GAMEBENCH_TASK="$TASK_ID"
  export GAMEBENCH_TASK_DIR="$WORKSPACE/gamebench/tasks/$TASK_ID"
  export GAMEBENCH_POLICY_SUITE="$GAMEBENCH_TASK_DIR/${GAMEBENCH_REGISTRY_policy_suite}"
  export GAMEBENCH_POLICY_BASELINE="$GAMEBENCH_TASK_DIR/${GAMEBENCH_REGISTRY_policy_baseline}"
  export CANDIDATE_SUBDIR="${CANDIDATE_SUBDIR:-}"
  bash "$TASK_ROOT/tests/test.sh"

  echo ""
  echo "reward: $(cat "$OUT_DIR/logs/verifier/reward.txt")"
  echo "result: $OUT_DIR/logs/verifier/result.json"
  exit 0
fi

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
