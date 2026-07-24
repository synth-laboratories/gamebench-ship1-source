#!/usr/bin/env bash
# Generic Harbor agent run for registry-backed bundle families.
# Agents: codex (evals runner) | pi | cursor (host agents).
# Set GAMEBENCH_HARBOR_OUT per lane so parallel replicas do not clobber each other.
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

AGENT="${GAMEBENCH_HARBOR_AGENT:-codex}"
case "$AGENT" in
  codex|pi|cursor) ;;
  *)
    echo "Unsupported GAMEBENCH_HARBOR_AGENT=$AGENT (want codex|pi|cursor)" >&2
    exit 2
    ;;
esac

REG_FAMILY="$(registry_family "$FAMILY")"
load_task_env "$TASK_ID"
BUNDLE="$(eval_registry harbor-bundle "$REG_FAMILY" "$TASK_ID")"
TASK_ROOT="$(bundle_root "$BUNDLE")"
MODEL="${GAMEBENCH_HARBOR_MODEL:-openai/gpt-5.4-mini}"
EFFORT="${GAMEBENCH_HARBOR_EFFORT:-low}"
# Tag images per task so SKIP_BUILD cannot reuse a sibling-task bake (e.g. rogue vs craftax).
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-${BUNDLE}-${TASK_ID}:latest}"
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-${BUNDLE}-${AGENT}}"
DEPLOYMENT="gamebench_${BUNDLE}"
TIMEOUT_SEC="${GAMEBENCH_HARBOR_TIMEOUT_SEC:-3600}"
# Per-lane workspace under OUT_DIR so parallel panel replicas do not race.
WORKSPACE="${GAMEBENCH_HARBOR_WORKSPACE:-$OUT_DIR/workspace}"

mkdir -p "$OUT_DIR/logs/verifier"
rm -rf "$WORKSPACE"
mkdir -p "$WORKSPACE"

if [[ "$AGENT" == "codex" && ! -f "$CODEX_RUNNER" ]]; then
  echo "Missing codex runner: $CODEX_RUNNER" >&2
  exit 1
fi

BUILD_ARGS=(--build-arg "GAMEBENCH_TASK=$TASK_ID")
if [[ "$REG_FAMILY" == code_policy_opt || "$REG_FAMILY" == cybernetic_opt ]]; then
  BUILD_ARGS+=(--build-arg "CANDIDATE_SUBDIR=${CANDIDATE_SUBDIR:-}")
fi
if [[ "$REG_FAMILY" == code_policy_puzzles ]]; then
  BUILD_ARGS+=(--build-arg "PUZZLE_ID=${PUZZLE_ID:-puzzle_center_blind_v1}")
fi

echo "Building Harbor image=$IMAGE task=$TASK_ID agent=$AGENT"
if [[ "${GAMEBENCH_HARBOR_SKIP_BUILD:-0}" == "1" ]] && docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Skipping docker build (GAMEBENCH_HARBOR_SKIP_BUILD=1, image present)"
else
  docker build -t "$IMAGE" -f "$TASK_ROOT/environment/Dockerfile" "${BUILD_ARGS[@]}" "$GAMEBENCH_ROOT"
fi

docker run --rm "$IMAGE" bash -lc 'tar -C /workspace -cf - .' | tar -C "$WORKSPACE" -xf -

bash "$SCRIPT_DIR/prepare_code_policy_workspace.sh" \
  "$WORKSPACE" \
  "$TASK_ID" \
  "${CANDIDATE_SUBDIR:-}" \
  "$TASK_ROOT" \
  "${GAMEBENCH_REGISTRY_policy_baseline}"

# Prefer workspace-staged instruction (task-specific). Bundle instruction.md is
# only a fallback and must not override a craftax/rogue AGENTS.md mismatch.
if [[ -f "$WORKSPACE/instruction.md" ]]; then
  INSTRUCTION_PATH="$WORKSPACE/instruction.md"
elif [[ -f "$TASK_ROOT/instruction.md" ]]; then
  INSTRUCTION_PATH="$TASK_ROOT/instruction.md"
else
  INSTRUCTION_PATH="$WORKSPACE/AGENTS.md"
fi
if [[ ! -f "$INSTRUCTION_PATH" ]]; then
  echo "missing harbor instruction at $INSTRUCTION_PATH" >&2
  exit 1
fi
AGENT_RC=0
RESULT_JSON="$OUT_DIR/rollout_result.json"

if [[ "$AGENT" == "codex" ]]; then
  ROLLOUT_JSON="$OUT_DIR/rollout.json"
  python3 - "$ROLLOUT_JSON" "$WORKSPACE" "$MODEL" "$DEPLOYMENT" "$TASK_ID" "${CANDIDATE_SUBDIR:-}" "$EFFORT" "$TIMEOUT_SEC" <<'PY'
import json
import sys
from pathlib import Path

workspace = Path(sys.argv[2])
model = sys.argv[3]
deployment = sys.argv[4]
task_id = sys.argv[5]
candidate_subdir = (sys.argv[6] if len(sys.argv) > 6 else "").strip()
if not candidate_subdir:
    # craftax-singleplayer -> craftax (never silently default to tictactoe)
    candidate_subdir = task_id.removesuffix("-singleplayer").removesuffix("-multiplayer")
effort = sys.argv[7] if len(sys.argv) > 7 else "low"
timeout_sec = int(sys.argv[8]) if len(sys.argv) > 8 else 3600
payload = {
    "trace_correlation_id": f"{deployment}-{workspace.name}",
    "deployment_name": deployment,
    "codex_timeout_seconds": timeout_sec,
    "harbor_agent": {
        "name": "codex",
        "model_name": model,
        "kwargs": {
            "reasoning_effort": effort,
            "codex_timeout_seconds": timeout_sec,
        },
    },
    "task_metadata": {"workspace_dir": str(workspace.resolve())},
    "env": {
        "HARBOR_LOG_DIR": str((workspace / "logs" / "verifier").resolve()),
        "GAMEBENCH_WORKSPACE_ROOT": str(workspace.resolve()),
        "GAMEBENCH_ROOT": str((workspace / "gamebench").resolve()),
        "GAMEBENCH_TASK": task_id,
        "GAMEBENCH_TASK_DIR": str((workspace / "gamebench" / "tasks" / task_id).resolve()),
        "CANDIDATE_SUBDIR": candidate_subdir,
    },
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

  append_codex_auth_to_rollout "$ROLLOUT_JSON"

  echo "Running Codex Harbor family=$REG_FAMILY task=$TASK_ID model=$MODEL effort=$EFFORT"
  set +e
  python3 "$CODEX_RUNNER" \
    --input "$ROLLOUT_JSON" \
    --output "$RESULT_JSON" \
    --task-root "$TASK_ROOT"
  AGENT_RC=$?
  set -e
else
  echo "Running host $AGENT Harbor family=$REG_FAMILY task=$TASK_ID model=$MODEL effort=$EFFORT"
  set +e
  python3 "$SCRIPT_DIR/run_host_harbor_agent.py" \
    --agent "$AGENT" \
    --workspace "$WORKSPACE" \
    --out-dir "$OUT_DIR" \
    --instruction "$INSTRUCTION_PATH" \
    --model "$MODEL" \
    --effort "$EFFORT" \
    --timeout-sec "$TIMEOUT_SEC"
  AGENT_RC=$?
  set -e
  python3 - "$RESULT_JSON" "$AGENT" "$MODEL" "$EFFORT" "$AGENT_RC" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "success": int(sys.argv[5]) == 0,
            "metadata": {
                "agent_name": sys.argv[2],
                "model_name": sys.argv[3],
                "effort": sys.argv[4],
                "exit_code": int(sys.argv[5]),
            },
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY
fi

echo ""
echo "=== Verifier ($BUNDLE) agent_rc=$AGENT_RC ==="
export HARBOR_LOG_DIR="$OUT_DIR/logs/verifier"
export GAMEBENCH_WORKSPACE_ROOT="$WORKSPACE"
export GAMEBENCH_ROOT="$WORKSPACE/gamebench"
export GAMEBENCH_TASK="$TASK_ID"
export GAMEBENCH_TASK_DIR="$WORKSPACE/gamebench/tasks/$TASK_ID"
export GAMEBENCH_POLICY_SUITE="$GAMEBENCH_TASK_DIR/${GAMEBENCH_REGISTRY_policy_suite}"
export GAMEBENCH_POLICY_BASELINE="$GAMEBENCH_TASK_DIR/${GAMEBENCH_REGISTRY_policy_baseline}"
export CANDIDATE_SUBDIR="${CANDIDATE_SUBDIR:-}"
# Also point verifier at OUT_DIR logs (score_hillclimb writes via HARBOR_LOG_DIR).
mkdir -p "$HARBOR_LOG_DIR"
set +e
bash "$TASK_ROOT/tests/test.sh"
VERIFY_RC=$?
set -e

# Copy verifier outputs into OUT_DIR if the script wrote under workspace.
if [[ -f "$WORKSPACE/logs/verifier/result.json" && ! -f "$OUT_DIR/logs/verifier/result.json" ]]; then
  cp "$WORKSPACE/logs/verifier/result.json" "$OUT_DIR/logs/verifier/result.json"
fi
if [[ -f "$WORKSPACE/logs/verifier/reward.txt" && ! -f "$OUT_DIR/logs/verifier/reward.txt" ]]; then
  cp "$WORKSPACE/logs/verifier/reward.txt" "$OUT_DIR/logs/verifier/reward.txt"
fi

# Normalize HARBOR_LOG_DIR copies when test.sh used OUT_DIR already.
if [[ -f "$OUT_DIR/logs/verifier/reward.txt" ]]; then
  echo "reward: $(cat "$OUT_DIR/logs/verifier/reward.txt")"
else
  echo "reward: (missing)"
fi
echo "result: $OUT_DIR/logs/verifier/result.json"
echo "rollout: $RESULT_JSON"
echo "agent_rc=$AGENT_RC verify_rc=$VERIFY_RC"

# Persist a compact lane receipt for the panel.
python3 - "$OUT_DIR/lane-receipt.json" "$TASK_ID" "$AGENT" "$MODEL" "$EFFORT" "$AGENT_RC" "$VERIFY_RC" "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

receipt = Path(sys.argv[1])
out = Path(sys.argv[8])
result_path = out / "logs" / "verifier" / "result.json"
reward_path = out / "logs" / "verifier" / "reward.txt"
payload = {
    "schema_version": "gamebench.harbor.lane_receipt.v1",
    "task_id": sys.argv[2],
    "agent": sys.argv[3],
    "model": sys.argv[4],
    "effort": sys.argv[5],
    "agent_rc": int(sys.argv[6]),
    "verify_rc": int(sys.argv[7]),
    "out_dir": str(out),
}
if result_path.is_file():
    try:
        payload["verifier"] = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload["verifier_error"] = "invalid result.json"
if reward_path.is_file():
    raw = reward_path.read_text(encoding="utf-8").strip()
    try:
        payload["reward"] = float(raw)
    except ValueError:
        payload["reward_raw"] = raw
v = payload.get("verifier") or {}
payload["baseline_score"] = v.get("baseline_score")
payload["best_score"] = v.get("best_score")
payload["delta_vs_baseline"] = v.get("delta_vs_baseline")
payload["best_candidate_id"] = v.get("best_candidate_id")
payload["score_metric"] = v.get("score_metric")
payload["baseline_mean_scout_score"] = v.get("baseline_mean_scout_score")
payload["best_mean_scout_score"] = v.get("best_mean_scout_score")
payload["delta_mean_scout_score"] = v.get("delta_mean_scout_score")
payload["best_scout_candidate_id"] = v.get("best_scout_candidate_id")
if v.get("error"):
    payload["verifier_error"] = v.get("error")
receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"receipt: {receipt}")
PY

# Fail the lane if verifier failed. Agent non-zero still continues to verify
# (candidates may exist), but overall exit is non-zero if either failed.
if [[ "$VERIFY_RC" -ne 0 ]]; then
  exit "$VERIFY_RC"
fi
if [[ "$AGENT_RC" -ne 0 ]]; then
  exit "$AGENT_RC"
fi
exit 0
