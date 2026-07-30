"""Compact state -> action traces for Crafter policy puzzle rollouts."""

from __future__ import annotations

from typing import Any

TRACE_SCHEMA = "gamebench.crafter.policy_puzzle.state_action_trace.v1"
SURVIVAL_INVENTORY_KEYS = frozenset({"health", "food", "drink", "energy"})


def state_snapshot(readout: dict[str, Any]) -> dict[str, Any]:
    """Project a policy-sleuthing view from a symbolic readout (pre-action)."""
    observation = readout.get("observation") if isinstance(readout.get("observation"), dict) else {}
    player = observation.get("player") if isinstance(observation.get("player"), dict) else {}
    inventory_raw = player.get("inventory") if isinstance(player.get("inventory"), dict) else {}
    achievements_raw = observation.get("achievements") if isinstance(observation.get("achievements"), dict) else {}
    front_tile = readout.get("front_tile")
    if not isinstance(front_tile, dict):
        front_tile = None
    return {
        "step": int(observation.get("step", readout.get("private", {}).get("step_index", 0)) or 0),
        "pos": player.get("pos"),
        "facing": player.get("facing"),
        "front_tile": front_tile,
        "inventory": {
            str(key): int(value)
            for key, value in inventory_raw.items()
            if int(value) > 0 and str(key) not in SURVIVAL_INVENTORY_KEYS
        },
        "achievements": sorted(
            str(name)
            for name, value in achievements_raw.items()
            if int(value) > 0
        ),
        "local_tiles": dict(readout.get("local_tile_counts") or {}),
    }


def state_action_transition(*, readout: dict[str, Any], action: str) -> dict[str, Any]:
    return {
        "state": state_snapshot(readout),
        "action": str(action),
    }


def build_state_action_trace(
    *,
    puzzle_id: str,
    seed: int,
    engine_lane: str,
    transitions: list[dict[str, Any]],
    termination: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": TRACE_SCHEMA,
        "puzzle_id": puzzle_id,
        "seed": int(seed),
        "engine_lane": engine_lane,
        "transition_count": len(transitions),
        "transitions": transitions,
        "termination": termination,
    }
