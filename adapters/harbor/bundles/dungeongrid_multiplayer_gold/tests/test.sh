#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

OUTPUT_JSON="$LOG_DIR/result.json"
REWARD_PATH="$LOG_DIR/reward.txt"
LANE_ROOT="${DUNGEONGRID_TASK_ROOT:-/task/reference/dungeongrid-multiplayer}"

if [[ ! -d "$LANE_ROOT" ]]; then
  echo '{"error":"missing DungeonGrid task root","harbor_reward":0.0}' > "$OUTPUT_JSON"
  echo 0 > "$REWARD_PATH"
  exit 1
fi

python3 - "$LANE_ROOT" "$OUTPUT_JSON" "$REWARD_PATH" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

lane_root = Path(sys.argv[1])
output_json = Path(sys.argv[2])
reward_path = Path(sys.argv[3])

checks = [
    ("scenario_suite", "scripts/run_scenario_suite.py"),
    ("lane_compare", "scripts/compare_gold_lanes.py"),
    ("rust_mechanics_probe", "scripts/run_rust_mechanics_probe.py"),
    ("mechanics_probe_parity", "scripts/compare_mechanics_probes.py"),
]


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


results = []
for check_id, script in checks:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=lane_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    results.append(
        {
            "id": check_id,
            "script": script,
            "returncode": completed.returncode,
            "passed": completed.returncode == 0,
            "summary": extract_json(completed.stdout),
            "stdout": completed.stdout,
        }
    )

passed_count = sum(1 for item in results if item["passed"])
all_passed = passed_count == len(results)
report = {
    "schema": "gamebench.harbor.dungeongrid_contract_result.v1",
    "harbor_reward": 1.0 if all_passed else 0.0,
    "resolved": all_passed,
    "check_count": len(results),
    "passed_check_count": passed_count,
    "checks": results,
}
output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
reward_path.write_text(str(report["harbor_reward"]), encoding="utf-8")
print(f"harbor_reward={report['harbor_reward']}")
raise SystemExit(0 if all_passed else 1)
PY
