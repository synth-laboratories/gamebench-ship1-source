#!/usr/bin/env python3
"""Compare independent Python and Rust TowerMind authorities on pinned tapes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_python.engine import TowerMindEnv, run_scenario
from scenario_fixtures import first_difference, load_scenarios


def rust_scenario(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "gold_rust" / "Cargo.toml"), "--bin", "towermind_replay", "--", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def rust_restore(checkpoint: str) -> dict[str, Any]:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "gold_rust" / "Cargo.toml"), "--bin", "towermind_replay", "--", "--checkpoint-stdin"],
        input=checkpoint,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    paths = sorted((ROOT / "defaults" / "scenarios").glob("*.json"))
    failures: list[str] = []
    completed: list[str] = []
    for path in paths:
        document = json.loads(path.read_text())
        python = run_scenario(document)
        rust = rust_scenario(path)
        difference = first_difference(python, rust)
        if difference:
            failures.append(f"{path.name}: {difference}")
            continue
        completed.append(document["id"])
        if document["level"] in {"L1", "L2"}:
            restored = rust_restore(python["checkpoint"])
            expected = {"projection": python["projection"], "checkpoint": python["checkpoint"]}
            difference = first_difference(expected, restored)
            if difference:
                failures.append(f"{path.name} python->rust checkpoint: {difference}")
    if failures:
        raise SystemExit("TowerMind Python/Rust parity FAILED\n" + "\n".join(failures))
    print(json.dumps({"status": "pass", "scenarios": completed, "checkpoint_bridge": "python_to_rust_pass"}, sort_keys=True))


if __name__ == "__main__":
    main()
