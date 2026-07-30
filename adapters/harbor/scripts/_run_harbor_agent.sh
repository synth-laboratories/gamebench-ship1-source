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
ensure_policy_sandbox_image
BUNDLE="$(eval_registry harbor-bundle "$REG_FAMILY" "$TASK_ID")"
TASK_ROOT="$(bundle_root "$BUNDLE")"
MODEL="${GAMEBENCH_HARBOR_MODEL:-openai/gpt-5.4-mini}"
EFFORT="${GAMEBENCH_HARBOR_EFFORT:-low}"
# Tag images per task so SKIP_BUILD cannot reuse a sibling-task bake (e.g. rogue vs craftax).
IMAGE="${GAMEBENCH_HARBOR_IMAGE:-gamebench-harbor-${BUNDLE}-${TASK_ID}:latest}"
# Default OUT_DIR is minted fresh per run (panel-style UTC stamp + pid) so a
# direct run can never score against a prior run's result.json.
OUT_DIR="${GAMEBENCH_HARBOR_OUT:-/tmp/gamebench-harbor-${BUNDLE}-${AGENT}-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_STARTED_AT="$(date -u +%Y%m%dT%H%M%SZ)"
DEPLOYMENT="gamebench_${BUNDLE}"
TIMEOUT_SEC="${GAMEBENCH_HARBOR_TIMEOUT_SEC:-3600}"
# Per-lane workspace under OUT_DIR so parallel panel replicas do not race.
WORKSPACE="${GAMEBENCH_HARBOR_WORKSPACE:-$OUT_DIR/workspace}"

emit_standard_results() {
  local run_rc=$?
  trap - EXIT
  python3 "$SCRIPT_DIR/emit_standard_results.py" \
    --evals-root "$EVALS_ROOT" \
    --out-dir "$OUT_DIR" \
    --family "$REG_FAMILY" \
    --task "$TASK_ID" \
    --agent "$AGENT" \
    --model "$MODEL" \
    --effort "$EFFORT" \
    --exit-code "$run_rc" \
    --started-at "$RUN_STARTED_AT" || {
      local emit_rc=$?
      if [[ "$run_rc" -eq 0 ]]; then run_rc="$emit_rc"; fi
    }
  exit "$run_rc"
}
trap emit_standard_results EXIT

mkdir -p "$OUT_DIR/logs/verifier"
# Scoring integrity: purge any prior run's scoring artifacts so this run can
# only report a result it wrote itself (a reused GAMEBENCH_HARBOR_OUT must not
# seed result.json/reward.txt into the lane receipt).
rm -f "$OUT_DIR/logs/verifier/result.json" \
  "$OUT_DIR/logs/verifier/reward.txt" \
  "$OUT_DIR/lane-receipt.json" \
  "$OUT_DIR/rollout_result.json"
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
RUNNER_RC=0
VERIFY_RC=125
RESULT_JSON="$OUT_DIR/rollout_result.json"
EXECUTION_STATUS_JSON="$OUT_DIR/execution-status.json"
REWARD_PATH="$OUT_DIR/logs/verifier/reward.txt"

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
  AGENT_LOG_DIR="$OUT_DIR/logs/agent"
  mkdir -p "$AGENT_LOG_DIR"
  RUNNER_STDOUT="$AGENT_LOG_DIR/codex.runner.stdout.txt"
  RUNNER_STDERR="$AGENT_LOG_DIR/codex.runner.stderr.txt"
  set +e
  python3 "$CODEX_RUNNER" \
    --input "$ROLLOUT_JSON" \
    --output "$RESULT_JSON" \
    --task-root "$TASK_ROOT" \
    > >(tee "$RUNNER_STDOUT") \
    2> >(tee "$RUNNER_STDERR" >&2)
  RUNNER_RC=$?
  set -e
  if [[ -f "$WORKSPACE/logs/agent/codex_stdout.log" ]]; then
    cp "$WORKSPACE/logs/agent/codex_stdout.log" "$AGENT_LOG_DIR/codex.stdout.jsonl"
  else
    cp "$RUNNER_STDOUT" "$AGENT_LOG_DIR/codex.stdout.jsonl"
  fi
  if [[ -f "$WORKSPACE/logs/agent/codex_stderr.log" ]]; then
    cp "$WORKSPACE/logs/agent/codex_stderr.log" "$AGENT_LOG_DIR/codex.stderr.txt"
    if [[ -s "$RUNNER_STDERR" ]]; then
      printf '\n=== runner stderr ===\n' >> "$AGENT_LOG_DIR/codex.stderr.txt"
      sed -n '1,$p' "$RUNNER_STDERR" >> "$AGENT_LOG_DIR/codex.stderr.txt"
    fi
  else
    cp "$RUNNER_STDERR" "$AGENT_LOG_DIR/codex.stderr.txt"
  fi
  # The evals Codex runner already executes the verifier. Its process code is
  # aggregate; recover independent child codes from rollout-result metadata.
  read -r AGENT_RC VERIFY_RC < <(
    python3 "$SCRIPT_DIR/harbor_run_contract.py" inspect-codex \
      --result "$RESULT_JSON" \
      --runner-rc "$RUNNER_RC" \
      --reward "$WORKSPACE/logs/verifier/reward.txt" \
      --output "$EXECUTION_STATUS_JSON"
  )
  if [[ "$AGENT_RC" -ne 0 ]]; then
    python3 - "$EXECUTION_STATUS_JSON" <<'PY' >&2
import json
import sys
from pathlib import Path

status = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
message = status.get("agent_error") or "agent exited without an error message"
print(f"Codex Harbor agent failed: {message}")
PY
  fi
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
  RUNNER_RC=$AGENT_RC
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

if [[ "$AGENT" != "codex" ]]; then
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
  mkdir -p "$HARBOR_LOG_DIR"
  set +e
  bash "$TASK_ROOT/tests/test.sh"
  VERIFY_RC=$?
  set -e
  python3 "$SCRIPT_DIR/harbor_run_contract.py" record-host \
    --agent-rc "$AGENT_RC" \
    --verify-rc "$VERIFY_RC" \
    --reward "$REWARD_PATH" \
    --output "$EXECUTION_STATUS_JSON" >/dev/null
fi

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

# Persist a typed lane receipt for the panel and evals.
python3 "$SCRIPT_DIR/harbor_run_contract.py" write-receipt \
  --status "$EXECUTION_STATUS_JSON" \
  --receipt "$OUT_DIR/lane-receipt.json" \
  --task "$TASK_ID" \
  --agent "$AGENT" \
  --model "$MODEL" \
  --effort "$EFFORT" \
  --out-dir "$OUT_DIR"

# Fail the lane if verifier failed. Agent non-zero still continues to verify
# (candidates may exist), but overall exit is non-zero if either failed.
if [[ "$VERIFY_RC" -ne 0 ]]; then
  exit "$VERIFY_RC"
fi
if [[ "$AGENT_RC" -ne 0 ]]; then
  exit "$AGENT_RC"
fi
exit 0
