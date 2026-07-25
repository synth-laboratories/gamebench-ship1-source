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


def rust_resume(checkpoint: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "gold_rust" / "Cargo.toml"), "--bin", "towermind_replay", "--", "--checkpoint-replay-stdin"],
        input=json.dumps({"checkpoint": checkpoint, "actions": actions}),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def verify_mid_episode_checkpoint() -> str | None:
    document = json.loads((ROOT / "defaults" / "scenarios" / "l1_build_collect.json").read_text())
    actions = document["actions"]
    cut = 4
    source = TowerMindEnv()
    source.reset(document["level"], seed=document["seed"])
    for action in actions[:cut]:
        source.step(action)
    if source.state is None or source.state["terminated"]:
        return "checkpoint cut unexpectedly terminal"
    checkpoint = source.checkpoint()
    resumed_python = TowerMindEnv()
    resumed_python.restore(checkpoint)
    for action in actions[cut:]:
        if resumed_python.state is not None and resumed_python.state["terminated"]:
            break
        resumed_python.step(action)
    expected = {"projection": resumed_python.projection(), "checkpoint": resumed_python.checkpoint()}
    difference = first_difference(expected, rust_resume(checkpoint, actions[cut:]))
    return None if difference is None else f"mid-episode Python->Rust restore/replay: {difference}"


def verify_leak_contract(result: dict[str, Any]) -> str | None:
    state = result["projection"]["state"]
    leaks = [event for event in result["projection"]["events"] if event["kind"] == "enemy_leaked"]
    if len(leaks) != 3:
        return f"expected 3 enemy_leaked events, found {len(leaks)}"
    if any(event["payload"].get("reward_delta") != -1.0 for event in leaks):
        return "enemy_leaked events must each carry reward_delta -1.0"
    if state["base_hp"] != 0 or state["termination_reason"] != "base_destroyed" or state["total_reward"] != -3.0:
        return f"base-destruction state mismatch: {state}"
    return None


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
        if document["id"] == "l1_base_destruction":
            difference = verify_leak_contract(python)
            if difference:
                failures.append(f"{path.name} leak contract: {difference}")
    difference = verify_mid_episode_checkpoint()
    if difference:
        failures.append(difference)
    if failures:
        raise SystemExit("TowerMind Python/Rust parity FAILED\n" + "\n".join(failures))
    print(json.dumps({"status": "pass", "scenarios": completed, "checkpoint_bridge": "python_to_rust_mid_episode_replay_pass", "leak_contract": "base_destroyed_pass"}, sort_keys=True))


if __name__ == "__main__":
    main()
