#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
TASK_ROOT="$GAMEBENCH_ROOT/tasks/dungeongrid-multiplayer"
LOG_DIR="${HARBOR_LOG_DIR:-/tmp/gamebench-dungeongrid-harbor}"

mkdir -p "$LOG_DIR"
DUNGEONGRID_TASK_ROOT="$TASK_ROOT" HARBOR_LOG_DIR="$LOG_DIR" \
  bash "$HARBOR_BUNDLE_ROOT/dungeongrid_multiplayer_gold/tests/test.sh"

echo "result=$LOG_DIR/result.json"
echo "reward=$(cat "$LOG_DIR/reward.txt")"
