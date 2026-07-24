#!/usr/bin/env bash
# Verify reference gold scores 100% on spectrum eval (no Codex).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_LANE="$GAMEBENCH_ROOT/tasks/craftax-singleplayer"
OUT="$TASK_LANE/reports/spectrum_reference_harbor.json"
VENV_PY="$GAMEBENCH_ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  python3 -m venv "$GAMEBENCH_ROOT/.venv"
  "$GAMEBENCH_ROOT/.venv/bin/pip" install -q fastapi uvicorn httpx pydantic
fi

bash "$HARBOR_BUNDLE_ROOT/sync_craftax_reference.sh"

cd "$TASK_LANE"
export PYTHONPATH=.:gold_python:shared
export GAMEBENCH_ROOT="$GAMEBENCH_ROOT"
"$VENV_PY" scripts/spectrum_eval.py \
  --lane http \
  --service-lane python \
  --candidate-root "$TASK_LANE" \
  --candidate-port 19093 \
  --output "$OUT"
