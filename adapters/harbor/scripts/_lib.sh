#!/usr/bin/env bash
# Shared Harbor adapter helpers.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
GAMEBENCH_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
HARBOR_ADAPTER_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HARBOR_BUNDLE_ROOT="$HARBOR_ADAPTER_ROOT/bundles"
HARBOR_SCRIPTS="$HARBOR_ADAPTER_ROOT/scripts"
EVALS_ROOT="${GAMEBENCH_EVALS_ROOT:-$HOME/Documents/GitHub/evals}"
CODEX_RUNNER="$EVALS_ROOT/core/harbor/runner/codex_harbor_runner.py"
EVAL_REGISTRY="$GAMEBENCH_ROOT/adapters/scripts/eval_registry.py"

bundle_root() {
  echo "$HARBOR_BUNDLE_ROOT/$1"
}

task_root() {
  echo "$GAMEBENCH_ROOT/tasks/$1"
}

eval_registry() {
  python3 "$EVAL_REGISTRY" "$@"
}

ensure_policy_sandbox_image() {
  local image="python:3.13-slim-bookworm@sha256:129f9f5d5729767916d79f0021ba4fe56ff113332b08ef1213ecf529a9da7ebb"
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker pull --platform linux/amd64 "$image"
  fi
}

normalize_family() {
  case "$1" in
    dev|engine|engine_rebuild) echo dev ;;
    code-policy|code_policy|code_policy_opt) echo code_policy_opt ;;
    puzzle|puzzles|code_policy_puzzles) echo code_policy_puzzles ;;
    cybernetic|cybernetic_opt|exotic) echo cybernetic_opt ;;
    *) echo "$1" ;;
  esac
}

registry_family() {
  local cli="$1"
  case "$cli" in
    dev) echo dev ;;
    code_policy_opt) echo code_policy_opt ;;
    code_policy_puzzles) echo code_policy_puzzles ;;
    cybernetic_opt) echo cybernetic_opt ;;
    *) return 1 ;;
  esac
}

load_task_env() {
  local task_id="$1"
  while IFS='=' read -r key value; do
    [[ -n "$key" ]] || continue
    export "GAMEBENCH_REGISTRY_${key}=${value}"
    case "$key" in
      policy_suite) export GAMEBENCH_POLICY_SUITE="$GAMEBENCH_ROOT/tasks/$task_id/$value" ;;
      policy_baseline) export GAMEBENCH_POLICY_BASELINE="$GAMEBENCH_ROOT/tasks/$task_id/$value" ;;
      cybernetic_suite) export GAMEBENCH_CYBERNETIC_SUITE="$GAMEBENCH_ROOT/tasks/$task_id/$value" ;;
      candidate_subdir) export CANDIDATE_SUBDIR="$value" ;;
      default_puzzle) export PUZZLE_ID="${PUZZLE_ID:-$value}" ;;
      hillclimb_extra_args)
        export GAMEBENCH_HILLCLIMB_EXTRA_ARGS="$(
          python3 -c "import ast; print(' '.join(ast.literal_eval('''$value''')))"
        )"
        ;;
    esac
  done < <(eval_registry task-config "$task_id")
  export GAMEBENCH_TASK="$task_id"
}

venv_python() {
  local py="$GAMEBENCH_ROOT/.venv/bin/python"
  if [[ ! -x "$py" ]]; then
    python3 -m venv "$GAMEBENCH_ROOT/.venv"
    "$GAMEBENCH_ROOT/.venv/bin/pip" install -q fastapi uvicorn httpx pydantic
  fi
  echo "$py"
}

append_codex_auth_to_rollout() {
  local rollout_json="$1"
  python3 - "$rollout_json" <<'PY'
import base64
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
rollout = json.loads(path.read_text(encoding="utf-8"))
agent = rollout.get("harbor_agent") or {}
model = str(agent.get("model_name") or "").strip()
if model.startswith("synth-cloud/") or model.startswith("synth_cloud/"):
    api_key = os.environ.get("SYNTH_API_KEY", "").strip()
    if not api_key:
        print(
            "Synth cloud auth unavailable: set SYNTH_API_KEY",
            file=sys.stderr,
        )
        sys.exit(1)
    base_url = (
        os.environ.get("SYNTH_RESPONSES_GATEWAY_OPENAI_BASE_URL", "").strip()
        or os.environ.get("OPENAI_BASE_URL", "").strip()
    )
    if not base_url:
        gateway_root = os.environ.get("SYNTH_RESPONSES_GATEWAY_URL", "").strip().rstrip(
            "/"
        )
        if gateway_root:
            base_url = f"{gateway_root}/api/v1"
    if not base_url:
        print(
            "Synth cloud base URL unavailable: set "
            "SYNTH_RESPONSES_GATEWAY_OPENAI_BASE_URL "
            "(or SYNTH_RESPONSES_GATEWAY_URL / OPENAI_BASE_URL)",
            file=sys.stderr,
        )
        sys.exit(1)
    rollout["codex_provider"] = {
        "provider_id": "synth_cloud",
        "auth_mode": "provider_api_key",
        "api_key_env": "SYNTH_API_KEY",
        "base_url": base_url.rstrip("/"),
        "wire_api": "responses",
    }
    rollout["codex_auth_source"] = "synth_cloud_api_key"
    path.write_text(json.dumps(rollout, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0)
auth_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
api_key = os.environ.get("OPENAI_API_KEY", "").strip()
if api_key:
    rollout["openai_api_key"] = api_key
    rollout["codex_auth_source"] = "openai_api_key"
elif auth_path.is_file():
    rollout["codex_auth_json_b64"] = base64.b64encode(auth_path.read_bytes()).decode("ascii")
    rollout["codex_auth_source"] = "host_codex_auth_json"
else:
    print("Codex auth unavailable: set OPENAI_API_KEY or run `codex login`", file=sys.stderr)
    sys.exit(1)
path.write_text(json.dumps(rollout, indent=2) + "\n", encoding="utf-8")
PY
}
