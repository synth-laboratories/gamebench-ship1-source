#!/usr/bin/env python3
"""Deterministic Craftax-Coop scenario and fixture projections."""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
SCENARIO_DIR = TASK_DIR / "defaults" / "scenarios"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import CraftaxCoopEnv


AGENT_IDS = ("agent_0", "agent_1", "agent_2")
ROLES = {"agent_0": "warrior", "agent_1": "forager", "agent_2": "miner"}


def load_scenarios(path: Path = SCENARIO_DIR) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for source in sorted(path.glob("*.json")):
        entry = json.loads(source.read_text())
        validate_scenario(entry, source)
        entry["source_file"] = source.name
        entries.append(entry)
    if not entries:
        raise ValueError(f"no scenario JSON files found under {path}")
    return entries


def validate_scenario(entry: dict[str, Any], source: Path | None = None) -> None:
    label = str(source or entry.get("scenario_id", "<unknown>"))
    if entry.get("schema_version") != "gamebench.task.v1":
        raise ValueError(f"{label}: unsupported schema_version")
    if entry.get("env_family") != "craftax-multiplayer":
        raise ValueError(f"{label}: env_family must be craftax-multiplayer")
    if tuple(entry.get("agents", ())) != AGENT_IDS:
        raise ValueError(f"{label}: agents must be {list(AGENT_IDS)}")
    if entry.get("roles") != ROLES:
        raise ValueError(f"{label}: roles must be {ROLES}")
    if not isinstance(entry.get("seed"), int) or not isinstance(entry.get("max_timesteps"), int):
        raise ValueError(f"{label}: seed and max_timesteps must be integers")
    for index, joint_action in enumerate(entry.get("joint_actions", ())):
        if set(joint_action) != set(AGENT_IDS):
            raise ValueError(f"{label}: joint action {index} must name every agent exactly once")


def run_scenario(entry: dict[str, Any]) -> dict[str, Any]:
    validate_scenario(entry)
    env = CraftaxCoopEnv(max_timesteps=entry["max_timesteps"])
    initial_observations, reset_info = env.reset(entry["seed"])
    initial_projection = observation_projection(initial_observations)
    checkpoint_after = entry.get("checkpoint_after")
    checkpoint_equivalent = checkpoint_after is None
    step_records: list[dict[str, Any]] = []

    for index, joint_action in enumerate(entry["joint_actions"]):
        observations, rewards, dones, info = env.step(deepcopy(joint_action))
        step_records.append(
            {
                "index": index,
                "joint_action": joint_action,
                "rewards": rewards,
                "dones": dones,
                "events": info["events"],
                "state_hash": info["state_hash"],
            }
        )
        if checkpoint_after == index + 1:
            checkpoint = env.checkpoint()
            restored = CraftaxCoopEnv()
            restored_observations = restored.restore(deepcopy(checkpoint))
            checkpoint_equivalent = (
                restored._require_state().to_dict() == env._require_state().to_dict()
                and observation_projection(restored_observations) == observation_projection(observations)
            )
            env = restored

    state = env._require_state()
    outcome = {
        "scenario_id": entry["scenario_id"],
        "initial_state_hash": reset_info["state_hash"],
        "final_state_hash": env.state_hash(),
        "checkpoint_equivalent": checkpoint_equivalent,
        "structured_nev": deepcopy(state.nev),
        "legacy_nev": list(state.legacy_nev),
        "steps": step_records,
        "initial_observations": initial_projection,
        "final_observations": observation_projection(env.observations()),
        "state": state_projection(env),
    }
    verify_expectations(entry, outcome)
    return outcome


def state_projection(env: CraftaxCoopEnv) -> dict[str, Any]:
    state = env._require_state()
    return {
        "seed": state.seed,
        "timestep": state.timestep,
        "max_timesteps": state.max_timesteps,
        "terminated": state.terminated,
        "termination_reason": state.termination_reason,
        "boss_health": state.boss_health,
        "boss_progress": state.boss_progress,
        "trade_count": state.trade_count,
        "food_trade_count": state.food_trade_count,
        "drink_trade_count": state.drink_trade_count,
        "revives": state.revives,
        "friendly_fire_damage": state.ff_damage_dealt,
        "monster_count": len(state.monsters),
        "projectile_count": len(state.projectiles),
        "plant_count": len(state.plants),
        "monsters_killed": list(state.monsters_killed),
        "potion_mapping": list(state.potion_mapping),
        "achievements": sorted(name for name, earned in state.achievements.items() if earned),
        "players": [env._player_summary(player) | {"facing": player.facing} for player in state.players],
        "map_samples": {
            "overworld_spawn": [state.maps[0][3][x] for x in (3, 4, 5)],
            "overworld_fountain": state.maps[0][5][5],
            "fire_table": state.maps[6][10][10],
            "ice_table": state.maps[7][10][10],
            "boss": state.maps[8][24][24],
        },
    }


def observation_projection(observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for agent_id in AGENT_IDS:
        observation = observations[agent_id]
        projected[agent_id] = {
            "agent_id": observation["agent_id"],
            "agent_index": observation["agent_index"],
            "role": observation["role"],
            "legal_agent_ids": observation["legal_agent_ids"],
            "legal_action_count": len(observation["legal_actions"]),
            "self": observation["self"],
            "teammate_dashboard": observation["teammate_dashboard"],
            "level": observation["level"],
            "map_size": observation["map_size"],
            "num_levels": observation["num_levels"],
            "ascii": observation["ascii"],
            "local_view_digest": _digest(observation["local_view"]),
            "visible_monsters": observation["visible_monsters"],
            "shared": observation["shared"],
            "last_joint_event": observation["last_joint_event"],
        }
    return projected


def verify_expectations(entry: dict[str, Any], outcome: dict[str, Any]) -> None:
    expected = entry.get("expect", {})
    state = outcome["state"]
    for field in ("timestep", "terminated", "termination_reason", "trade_count"):
        if field in expected and state[field] != expected[field]:
            raise AssertionError(f"{entry['scenario_id']}: expected {field}={expected[field]!r}, got {state[field]!r}")
    players = state["players"]
    if "request_remaining" in expected:
        if any(player["request"]["remaining"] != expected["request_remaining"] for player in players):
            raise AssertionError(f"{entry['scenario_id']}: request duration mismatch")
    if expected.get("requests_expired"):
        if any(player["request"]["resource"] is not None or player["request"]["remaining"] != 0 for player in players):
            raise AssertionError(f"{entry['scenario_id']}: requests did not expire")
    for agent_id in AGENT_IDS:
        key = f"{agent_id}_wood"
        if key in expected:
            player = next(player for player in players if player["agent_id"] == agent_id)
            if player["inventory"]["wood"] != expected[key]:
                raise AssertionError(f"{entry['scenario_id']}: expected {key}={expected[key]}")
    if expected.get("checkpoint_equivalent") and not outcome["checkpoint_equivalent"]:
        raise AssertionError(f"{entry['scenario_id']}: checkpoint restore changed state or observations")


def fixture_documents(scenarios: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    outcomes = [run_scenario(entry) for entry in scenarios]
    scenario_document = {
        "schema_version": "gamebench.scenarios.v1",
        "env_family": "craftax-multiplayer",
        "scenarios": scenarios,
    }
    event_document = {
        "schema_version": "gamebench.craftax_coop.eventlogs.v1",
        "games": [
            {
                "scenario_id": outcome["scenario_id"],
                "structured": outcome["structured_nev"],
                "legacy": outcome["legacy_nev"],
                "steps": outcome["steps"],
            }
            for outcome in outcomes
        ],
    }
    state_document = {
        "schema_version": "gamebench.craftax_coop.states.v1",
        "games": [
            {
                "scenario_id": outcome["scenario_id"],
                "initial_state_hash": outcome["initial_state_hash"],
                "final_state_hash": outcome["final_state_hash"],
                "checkpoint_equivalent": outcome["checkpoint_equivalent"],
                "initial_observations": outcome["initial_observations"],
                "final_observations": outcome["final_observations"],
                "state": outcome["state"],
            }
            for outcome in outcomes
        ],
    }
    return scenario_document, event_document, state_document


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
