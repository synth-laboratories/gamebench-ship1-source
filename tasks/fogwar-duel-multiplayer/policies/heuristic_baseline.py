"""Small deterministic baseline for Fog Duel Lite policy experiments."""

from __future__ import annotations

from typing import Any


def act(observation: dict[str, Any]) -> dict[str, Any]:
    own_buildings = observation.get("visible_buildings", [])
    has_silo = any(item.get("owner") == observation.get("you") and item.get("kind") == "silo" and not item.get("under_construction") for item in own_buildings)
    resources = observation.get("own_resources", {})
    if has_silo and observation.get("enemy_base_discovered") and resources.get("uranium", 0) >= 25:
        return {"actions": [{"kind": "launch"}]}
    return {"actions": [{"kind": "wait"}]}
