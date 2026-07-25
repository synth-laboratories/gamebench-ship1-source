"""Scenario execution and canonical fixture projections for settlers rules."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import sys
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
SCENARIO_DIR = TASK_DIR / "defaults" / "scenarios"
sys.path.insert(0, str(TASK_DIR))
from gold_python.engine import AGENTS, SettlersEnv


def load_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        scenario = json.loads(path.read_text())
        if scenario.get("schema_version") != "gamebench.task.v1" or scenario.get("env_family") != "settlers-multiplayer":
            raise ValueError(f"{path}: invalid settlers scenario schema")
        if not isinstance(scenario.get("seed"), int) or not isinstance(scenario.get("actions"), list):
            raise ValueError(f"{path}: seed and actions are required")
        scenario["source_file"] = path.name
        scenarios.append(scenario)
    if len(scenarios) < 3:
        raise ValueError("settlers v0 requires at least three pinned scenarios")
    return scenarios


def public_projection(env: SettlersEnv) -> dict[str, Any]:
    state = env._require_state()
    return {
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
        "nev": state.nev,
        "legacy_nev": state.legacy_nev,
    }


def run_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    env = SettlersEnv(max_turns=scenario.get("max_turns", 240)); env.reset(scenario["seed"])
    checkpoint_equivalent = True
    steps = []
    for index, action in enumerate(scenario["actions"], start=1):
        _, rewards, dones, info = env.step(deepcopy(action))
        steps.append({"index": index, "actor": AGENTS[(env._require_state().current_player - 1) % 4] if not env._require_state().robber_pending else env.current_agent(), "action": action, "rewards": rewards, "dones": dones, "state_hash": info["state_hash"]})
        if scenario.get("checkpoint_after") == index:
            checkpoint = env.checkpoint(); restored = SettlersEnv(); restored.restore(deepcopy(checkpoint))
            checkpoint_equivalent = restored.state_dict() == env.state_dict() and restored.state_hash() == env.state_hash()
            env = restored
    return {"scenario_id": scenario["scenario_id"], "checkpoint_equivalent": checkpoint_equivalent, "state_hash": env.state_hash(), "steps": steps, "projection": public_projection(env)}


def fixture_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scenarios = load_scenarios(); outcomes = [run_scenario(scenario) for scenario in scenarios]
    return (
        {"schema_version": "gamebench.scenarios.v1", "env_family": "settlers-multiplayer", "scenarios": scenarios},
        {"schema_version": "gamebench.settlers.eventlogs.v1", "games": [{"scenario_id": outcome["scenario_id"], "structured": outcome["projection"]["nev"], "legacy": outcome["projection"]["legacy_nev"], "steps": outcome["steps"]} for outcome in outcomes]},
        {"schema_version": "gamebench.settlers.states.v1", "games": [{"scenario_id": outcome["scenario_id"], "checkpoint_equivalent": outcome["checkpoint_equivalent"], "state_hash": outcome["state_hash"], "state": outcome["projection"]} for outcome in outcomes]},
    )
