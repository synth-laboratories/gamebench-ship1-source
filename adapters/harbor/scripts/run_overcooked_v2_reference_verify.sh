#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
bash "$HARBOR_BUNDLE_ROOT/sync_overcooked_v2_reference.sh"
LANE="$GAMEBENCH_ROOT/tasks/overcooked-v2-multiplayer"
export PYTHONPATH="$LANE:$LANE/gold_python:$LANE/shared"
python3 "$LANE/scripts/spectrum_eval.py" --lane local --reference-local --output "$HARBOR_BUNDLE_ROOT/overcooked_v2_multiplayer_gold/reports/spectrum_reference.json"
echo "overcooked v2 reference verify OK"
