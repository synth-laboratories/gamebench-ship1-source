"""A stronger, stateless Fog Duel Lite policy for the fixed DEO suite.

It receives only the actor-private observation supplied by the Python gold
engine.  It does not import the engine, read scenario identity, retain state,
or inspect the opponent's hidden resources.
"""

from __future__ import annotations

from typing import Any


def _chebyshev_distance(left: list[int], right: list[int]) -> int:
    return max(abs(left[0] - right[0]), abs(left[1] - right[1]))


def act(observation: dict[str, Any]) -> dict[str, Any]:
    """Choose only a legal action justified by this observation."""
    agent = observation.get("you")
    resources = observation.get("own_resources", {})
    own_buildings = [
        item
        for item in observation.get("visible_buildings", [])
        if item.get("owner") == agent
    ]
    has_ready_silo = any(
        item.get("kind") == "silo" and not item.get("under_construction")
        for item in own_buildings
    )
    if (
        has_ready_silo
        and observation.get("enemy_base_discovered")
        and int(resources.get("uranium", 0)) >= 25
    ):
        return {"actions": [{"kind": "launch"}]}

    enemy_bases = [
        item
        for item in observation.get("visible_buildings", [])
        if item.get("owner") != agent and item.get("kind") == "base"
    ]
    own_tanks = [
        item
        for item in observation.get("visible_units", [])
        if item.get("owner") == agent and item.get("kind") == "tank"
    ]
    for tank in own_tanks:
        for base in enemy_bases:
            if _chebyshev_distance(list(tank["pos"]), list(base["pos"])) <= 2:
                return {
                    "actions": [
                        {
                            "kind": "attack",
                            "unit_id": tank["id"],
                            "target_pos": list(base["pos"]),
                        }
                    ]
                }
    return {"actions": [{"kind": "wait"}]}
