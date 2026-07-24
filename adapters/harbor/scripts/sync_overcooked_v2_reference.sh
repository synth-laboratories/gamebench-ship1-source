#!/usr/bin/env bash
# Populate harbor/overcooked_v2_multiplayer_gold reference + verifier fixtures from the task lane.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
HARBOR="$HARBOR_BUNDLE_ROOT/overcooked_v2_multiplayer_gold"
LANE="$GAMEBENCH_ROOT/tasks/overcooked-v2-multiplayer"

mkdir -p "$HARBOR/reference/gold_python" "$HARBOR/reference/shared" "$HARBOR/reference/scripts" "$HARBOR/reference/policies"
mkdir -p "$HARBOR/tests/fixtures/gold/scenarios" "$HARBOR/tests/fixtures/gold/eventlogs"
mkdir -p "$HARBOR/spec"

rsync -a --delete "$LANE/gold_python/" "$HARBOR/reference/gold_python/"
rsync -a --delete "$LANE/shared/" "$HARBOR/reference/shared/"
rsync -a "$LANE/policies/" "$HARBOR/reference/policies/"
cp "$LANE/scripts/run_service.py" "$HARBOR/reference/scripts/run_service.py"
cp "$LANE/scripts/spectrum_eval.py" "$HARBOR/tests/spectrum_eval.py"
cp "$LANE/fixtures/gold/scenarios/scenarios.json" "$HARBOR/tests/fixtures/gold/scenarios/scenarios.json"
cp "$LANE/fixtures/gold/eventlogs/eventlogs.json" "$HARBOR/tests/fixtures/gold/eventlogs/eventlogs.json"
cp "$ROOT/spec/spectrum_correctness.md" "$HARBOR/spec/spectrum_correctness.md"
cp "$ROOT/spec/nev_log.md" "$HARBOR/spec/nev_log.md"
cp "$ROOT/spec/checkpoint.md" "$HARBOR/spec/checkpoint.md"
cp "$ROOT/spec/deterministic_tasks.md" "$HARBOR/spec/deterministic_tasks.md"
cp "$ROOT/spec/marl_env_standards.md" "$HARBOR/spec/marl_env_standards.md"

echo "synced overcooked v2 harbor reference from $LANE"
