"""Intentionally simple Fog Duel Lite DEO baseline.

The policy is a pure function of the actor-private observation.  Its eager
movement rule is deliberately brittle: it tries to move any friendly tank to a
fixed distant cell without checking the Tank movement range.  The fixed suite
therefore exposes both its missed military win and its illegal-action rate.
"""

from __future__ import annotations

from typing import Any


def act(observation: dict[str, Any]) -> dict[str, Any]:
    """Return one structured request without reading environment state."""
    resources = observation.get("own_resources", {})
    own_buildings = [
        item
        for item in observation.get("visible_buildings", [])
        if item.get("owner") == observation.get("you")
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

    own_tanks = [
        item
        for item in observation.get("visible_units", [])
        if item.get("owner") == observation.get("you") and item.get("kind") == "tank"
    ]
    if own_tanks:
        return {
            "actions": [
                {
                    "kind": "move",
                    "unit_id": own_tanks[0]["id"],
                    "to": [12, 6],
                }
            ]
        }
    if int(resources.get("credits", 0)) >= 4:
        return {"actions": [{"kind": "produce", "unit": "tank"}]}
    return {"actions": [{"kind": "wait"}]}
