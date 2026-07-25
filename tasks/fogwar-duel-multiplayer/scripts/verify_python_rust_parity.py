#!/usr/bin/env python3
"""Compare independent Python and Rust Fog Duel Lite traces."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_python.engine import execute_tape
from gold_python.engine import FogDuelEnv
from gold_python.scenarios import load_all_scenarios


def compare(left: Any, right: Any) -> bool:
    return left == right


def resumed_python(scenario_id: str, checkpoint: dict[str, Any], tape: list[dict[str, Any]]) -> dict[str, Any]:
    env = FogDuelEnv()
    env.restore(checkpoint)
    checkpoints = [env.checkpoint()]
    for request in tape:
        env.step(request)
        checkpoints.append(env.checkpoint())
        if env.state_projection()["terminal"] is not None:
            break
    return {
        "scenario_id": scenario_id,
        "state": env.state_projection(),
        "events": env.events,
        "checkpoints": checkpoints,
        "observation": env.observe(),
    }


def run_rust(request: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "gold_rust/Cargo.toml")],
        input=json.dumps(request), text=True, capture_output=True, check=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    for scenario in load_all_scenarios():
        request = {"scenario_id": scenario["id"], "tape": scenario["fixture_tape"]}
        python = execute_tape(scenario["id"], scenario["fixture_tape"])
        rust = run_rust(request)
        if not compare(python, rust):
            print(json.dumps({"scenario": scenario["id"], "python": python, "rust": rust}, indent=2, sort_keys=True))
            raise SystemExit("Python/Rust parity mismatch")
    checkpoint_scenario = next(item for item in load_all_scenarios() if item["id"] == "fogwar_illegal_reliability_v0")
    source = FogDuelEnv()
    source.reset(checkpoint_scenario["id"])
    source.step(checkpoint_scenario["fixture_tape"][0])
    checkpoint = source.checkpoint()
    python = resumed_python(checkpoint_scenario["id"], checkpoint, checkpoint_scenario["fixture_tape"][1:])
    rust = run_rust({"scenario_id": checkpoint_scenario["id"], "checkpoint": checkpoint, "tape": checkpoint_scenario["fixture_tape"][1:]})
    if not compare(python, rust):
        print(json.dumps({"checkpoint": checkpoint, "python": python, "rust": rust}, indent=2, sort_keys=True))
        raise SystemExit("Python/Rust checkpoint replay mismatch")
    print("Fog Duel Lite Python/Rust parity OK (3 scenarios, full NEV, nonterminal checkpoint replay)")


if __name__ == "__main__":
    main()
