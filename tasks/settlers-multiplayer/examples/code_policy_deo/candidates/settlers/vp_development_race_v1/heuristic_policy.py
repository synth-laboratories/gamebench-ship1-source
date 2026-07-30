"""Observation-only DEO candidate: turn early production into public VP races."""

from __future__ import annotations

from typing import Any


def _road_action(observation: dict[str, Any]) -> dict[str, Any] | None:
    player = observation["self"]
    resources = player["resources"]
    if resources.get("wood", 0) < 1 or resources.get("brick", 0) < 1:
        return None
    own_roads = {int(edge) for edge in player["roads"]}
    occupied = {
        int(edge)
        for public_player in observation["public"].values()
        for edge in public_player["roads"]
    }
    own_vertices = {int(vertex) for vertex in player["settlements"] + player["cities"]}
    for edge in range(24):
        if edge in occupied:
            continue
        endpoints = {edge, (edge + 1) % 24}
        if endpoints & own_vertices:
            return {"kind": "build_road", "edge": edge}
        if any(endpoints & {road, (road + 1) % 24} for road in own_roads):
            return {"kind": "build_road", "edge": edge}
    return None


def _bank_trade_for_progress(resources: dict[str, int]) -> dict[str, Any] | None:
    """Trade a genuine surplus toward city or development-card thresholds."""

    for want, target in (("ore", 3), ("wheat", 2)):
        if resources.get(want, 0) >= target:
            continue
        give = next(
            (
                resource
                for resource in ("wood", "brick", "sheep", "wheat", "ore")
                if resource != want and resources.get(resource, 0) >= 4
            ),
            None,
        )
        if give is not None:
            return {"kind": "bank_trade", "give": give, "want": want}
    return None


def act(observation: dict[str, Any]) -> dict[str, Any]:
    """Prioritize durable VP and the two public award races over road sprawl."""

    legal_actions = set(observation.get("legal_actions", []))
    player = observation["self"]
    resources = player["resources"]
    if observation.get("rolled_die") == 7 or "move_robber" in legal_actions:
        opponents = [
            (int(public["vp"]), agent_id)
            for agent_id, public in observation["public"].items()
            if agent_id != player["agent_id"]
        ]
        victim = max(opponents, default=(0, "agent_1"))[1]
        return {
            "kind": "move_robber",
            "tile": (int(observation["robber_tile"]) + 1) % 12,
            "victim": victim,
        }

    if "knight" in player["dev_cards"]:
        opponents = [
            (int(public["vp"]), agent_id)
            for agent_id, public in observation["public"].items()
            if agent_id != player["agent_id"]
        ]
        victim = max(opponents, default=(0, "agent_1"))[1]
        return {
            "kind": "play_dev",
            "card": "knight",
            "tile": (int(observation["robber_tile"]) + 1) % 12,
            "victim": victim,
        }

    if resources.get("ore", 0) >= 3 and resources.get("wheat", 0) >= 2 and player["settlements"]:
        return {"kind": "build_city", "vertex": min(int(vertex) for vertex in player["settlements"])}

    bank_trade = _bank_trade_for_progress(resources)
    if bank_trade is not None:
        return bank_trade

    if resources.get("ore", 0) >= 1 and resources.get("sheep", 0) >= 1 and resources.get("wheat", 0) >= 1:
        return {"kind": "buy_dev"}

    road = _road_action(observation)
    if road is not None:
        return road
    return {"kind": "end_turn"}
