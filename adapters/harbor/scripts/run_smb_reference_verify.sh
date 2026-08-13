#!/usr/bin/env bash
# Verify the checked-in Rust engine and its HTTP/Harbor contract.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

TASK_LANE="$GAMEBENCH_ROOT/tasks/super-mario-bros-singleplayer"
BUNDLE="$HARBOR_BUNDLE_ROOT/super_mario_bros_singleplayer_gold"
OUT="$TASK_LANE/reports/protocol_reference.json"
mkdir -p "$(dirname "$OUT")"

cargo test --manifest-path "$TASK_LANE/gold_rust/Cargo.toml"
GAMEBENCH_CANDIDATE_ROOT="$TASK_LANE" \
GAMEBENCH_CANDIDATE_PORT="${GAMEBENCH_CANDIDATE_PORT:-19099}" \
HARBOR_LOG_DIR="${HARBOR_LOG_DIR:-/tmp/gamebench-smb-harbor}" \
bash "$BUNDLE/tests/test.sh"

mkdir -p "$(dirname "$OUT")"
python3 - "$OUT" <<'PY'
import json
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "task_id": "super-mario-bros-singleplayer",
    "levels": 32,
    "cargo_tests": "passed",
    "protocol_smoke": "passed",
    "rom_path_used": False,
}, indent=2) + "\n", encoding="utf-8")
PY
echo "SMB research-port reference verification passed"
