#!/usr/bin/env python3
"""Compare Python and Rust owned-gold projections on every pinned fixture."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scenario_fixtures import load_scenarios

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))
from gold_python.engine import SettlersEnv


def compact(scenario: dict) -> dict:
    env = SettlersEnv(max_turns=scenario.get("max_turns", 240)); env.reset(scenario["seed"])
    for action in scenario["actions"]:
        env.step(action)
    checkpoint = env.checkpoint(); restored = SettlersEnv(); restored.restore(checkpoint)
    state = env._require_state()
    projection = {
        "turn": state.turn,
        "current_agent": env.current_agent() if not state.terminated else None,
        "robber_tile": state.robber_tile,
        "robber_pending": state.robber_pending,
        "pending_trade": state.pending_trade,
        "longest_road_owner": state.longest_road_owner,
        "largest_army_owner": state.largest_army_owner,
        "terminated": state.terminated,
        "winner": state.winner,
        "termination_reason": state.termination_reason,
        "players": [{"agent_id": player.agent_id, "resources": player.resources, "settlements": sorted(player.settlements), "cities": sorted(player.cities), "roads": sorted(player.roads), "dev_cards": player.dev_cards, "played_knights": player.played_knights, "victory_points": env.victory_points(player.agent_id)} for player in state.players],
        "event_kinds": [event["kind"] for event in state.nev],
    }
    return {"projection": projection, "checkpoint_equivalent": restored.state_dict() == env.state_dict()}


def first_difference(left: object, right: object, path: str = "$") -> str:
    if type(left) is not type(right): return f"{path}: Python {type(left).__name__}, Rust {type(right).__name__}"
    if isinstance(left, dict):
        if left.keys() != right.keys(): return f"{path}: keys differ Python={sorted(left)} Rust={sorted(right)}"
        for key in left:
            if left[key] != right[key]: return first_difference(left[key], right[key], f"{path}.{key}")
    elif isinstance(left, list):
        if len(left) != len(right): return f"{path}: lengths differ Python={len(left)} Rust={len(right)}"
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            if a != b: return first_difference(a, b, f"{path}[{index}]")
    return f"{path}: Python={left!r} Rust={right!r}"


def main() -> None:
    python = {scenario["scenario_id"]: compact(scenario) for scenario in load_scenarios()}
    rust_run = subprocess.run(["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--example", "parity_scenarios"], check=True, text=True, capture_output=True)
    rust = json.loads(rust_run.stdout)
    if python != rust:
        raise SystemExit("Settlers Python/Rust parity mismatch: " + first_difference(python, rust))
    print(f"Settlers Python/Rust parity OK ({len(python)} fixtures, owned checkpoints restore in both lanes)")

if __name__ == "__main__":
    main()
