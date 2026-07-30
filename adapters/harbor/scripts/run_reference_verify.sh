#!/usr/bin/env bash
# Verify reference gold scores 100% on spectrum eval (no Codex).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_LANE="$GAMEBENCH_ROOT/tasks/tictactoe-singleplayer"
OUT="$TASK_LANE/reports/spectrum_reference.json"
VENV_PY="$GAMEBENCH_ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  python3 -m venv "$GAMEBENCH_ROOT/.venv"
  "$GAMEBENCH_ROOT/.venv/bin/pip" install -q fastapi uvicorn httpx pydantic
fi

cd "$TASK_LANE"
export PYTHONPATH=.
export GAMEBENCH_ROOT="$GAMEBENCH_ROOT"
"$VENV_PY" scripts/spectrum_eval.py \
  --lane http \
  --candidate-root "$TASK_LANE" \
  --candidate-port 19081 \
  --output "$OUT"
