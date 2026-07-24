"""Reference Craftax code-policy candidate for the symbolic GameBench task."""

from __future__ import annotations

from typing import Any


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    obs = readout["observation"]
    inv = obs["inventory"]
    front = obs["player"]["front_tile"]
    achievements = set(obs.get("achievements", []))
    if engine is not None:
        best_action = _best_immediate_progress(engine, valid_actions)
        if best_action:
            return _decision(best_action, "checkpoint one-step lookahead found progress")
    if front == "tree":
        return _decision("do", "harvest adjacent tree")
    if front == "stone" and inv.get("pickaxe", 0) >= 1:
        return _decision("do", "mine adjacent stone")
    if front == "coal" and inv.get("pickaxe", 0) >= 1:
        return _decision("do", "mine adjacent coal")
    if front == "iron" and inv.get("pickaxe", 0) >= 2:
        return _decision("do", "mine adjacent iron")
    if inv.get("wood", 0) >= 2 and "place_table" not in achievements and _can_take(engine, "place_table"):
        return _decision("place_table", "place table once wood is available")
    if inv.get("wood", 0) >= 2 and "place_table" not in achievements:
        setup_action = _setup_for_action(engine, valid_actions, "place_table")
        if setup_action:
            return _decision(setup_action, "set up a valid table placement")
    if inv.get("sapling", 0) >= 1 and "place_plant" not in achievements and _can_take(engine, "place_plant"):
        return _decision("place_plant", "plant collected sapling")
    if inv.get("sapling", 0) >= 1 and "place_plant" not in achievements:
        setup_action = _setup_for_action(engine, valid_actions, "place_plant")
        if setup_action:
            return _decision(setup_action, "set up a valid plant placement")
    if inv.get("wood", 0) >= 1 and inv.get("pickaxe", 0) < 1 and _can_take(engine, "make_wood_pickaxe"):
        return _decision("make_wood_pickaxe", "craft wood pickaxe")
    if inv.get("wood", 0) >= 1 and inv.get("stone", 0) >= 1 and inv.get("pickaxe", 0) < 2 and _can_take(engine, "make_stone_pickaxe"):
        return _decision("make_stone_pickaxe", "upgrade to stone pickaxe")
    if inv.get("stone", 0) >= 1 and "place_furnace" not in achievements and _can_take(engine, "place_furnace"):
        return _decision("place_furnace", "place furnace")
    if inv.get("wood", 0) >= 1 and inv.get("stone", 0) >= 1 and inv.get("sword", 0) < 2 and _can_take(engine, "make_stone_sword"):
        return _decision("make_stone_sword", "make starter sword")
    if front == "grass" and "collect_sapling" not in achievements:
        return _decision("do", "roll grass for sapling")
    for action in _toward_interesting_tile(obs["local_map"]):
        if action in valid_actions:
            if engine is None or not _is_immediate_violation(engine, action):
                return _decision(action, "move toward nearby resource")
    return _decision(_safe_explore_action(engine, valid_actions), "explore")


def _decision(action: str, reason: str) -> dict[str, Any]:
    return {"actions": [action], "policy_reason": reason}


def _toward_interesting_tile(local_map: list[str]) -> list[str]:
    targets = "TSCIHDsr>"
    center_y = len(local_map) // 2
    center_x = len(local_map[0]) // 2 if local_map else 0
    best: tuple[int, int, int] | None = None
    for y, row in enumerate(local_map):
        for x, char in enumerate(row):
            if char in targets:
                dist = abs(x - center_x) + abs(y - center_y)
                if best is None or dist < best[0]:
                    best = (dist, x - center_x, y - center_y)
    if best is None:
        return ["right", "down", "left", "up"]
    _, dx, dy = best
    if abs(dx) >= abs(dy) and dx != 0:
        return ["right" if dx > 0 else "left"]
    if dy != 0:
        return ["down" if dy > 0 else "up"]
    return ["do"]


def _best_immediate_progress(engine: Any, valid_actions: list[str]) -> str | None:
    best: tuple[float, str] | None = None
    for action in valid_actions:
        if action == "noop":
            continue
        sim = engine.clone_for_sim()
        before_invalid = sim.private.invalid_action_count
        sim.step(action)
        if sim.private.invalid_action_count > before_invalid:
            continue
        reward = float(sim.private.reward_last)
        if reward > 0 and (best is None or reward > best[0]):
            best = (reward, action)
    return best[1] if best else None


def _is_immediate_violation(engine: Any, action: str) -> bool:
    sim = engine.clone_for_sim()
    before_invalid = sim.private.invalid_action_count
    sim.step(action)
    return sim.private.invalid_action_count > before_invalid


def _can_take(engine: Any, action: str) -> bool:
    return engine is None or not _is_immediate_violation(engine, action)


def _setup_for_action(engine: Any, valid_actions: list[str], target_action: str) -> str | None:
    if engine is None:
        return None
    for action in ("right", "down", "left", "up"):
        if action not in valid_actions:
            continue
        sim = engine.clone_for_sim()
        before_invalid = sim.private.invalid_action_count
        sim.step(action)
        if sim.private.invalid_action_count > before_invalid:
            continue
        probe = sim.clone_for_sim()
        before_probe_invalid = probe.private.invalid_action_count
        probe.step(target_action)
        if probe.private.invalid_action_count == before_probe_invalid and float(probe.private.reward_last) > 0:
            return action
    return None


def _safe_explore_action(engine: Any, valid_actions: list[str]) -> str:
    for action in ("right", "down", "left", "up", "noop"):
        if action not in valid_actions:
            continue
        if engine is None or not _is_immediate_violation(engine, action):
            return action
    return "noop"
