"""Built-in Sokoban code policies."""

from __future__ import annotations

import random
from typing import Any


def choose_action(policy_id: str, readout: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    if policy_id == "random_v1":
        return random_policy(readout, seed=seed, ply=ply)
    if policy_id == "greedy_distance_v1":
        return greedy_distance_policy(readout, seed=seed, ply=ply)
    if policy_id == "scripted_demo_v1":
        return scripted_demo_policy(readout, seed=seed, ply=ply)
    raise KeyError(f"unknown sokoban policy_id: {policy_id}")


def random_policy(readout: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    actions = list(readout.get("valid_actions", []))
    return random.Random(seed + ply).choice(actions) if actions else ""


def scripted_demo_policy(readout: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    del seed
    actions = ["right", "down", "left", "up"]
    valid = set(readout.get("valid_actions", []))
    for offset in range(len(actions)):
        action = actions[(ply + offset) % len(actions)]
        if action in valid:
            return action
    return next(iter(valid), "")


def greedy_distance_policy(readout: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    del seed, ply
    actions = list(readout.get("valid_actions", []))
    if not actions:
        return ""
    public = readout["public"]
    room = public["room_state"]
    player = tuple(public["player"])
    boxes = [tuple(pos) for pos in public["boxes"]]
    goals = [(r, c) for r, row in enumerate(room) for c, cell in enumerate(row) if cell in (2, 3, 6)]
    deltas = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    best_action = actions[0]
    best_score = -10**9
    for action in actions:
        dr, dc = deltas[action]
        candidate_player = (player[0] + dr, player[1] + dc)
        score = -_min_distance(candidate_player, boxes)
        next_box = candidate_player
        if next_box in boxes:
            pushed_box = (next_box[0] + dr, next_box[1] + dc)
            score += 5.0 - _min_distance(pushed_box, goals)
        if score > best_score:
            best_score = score
            best_action = action
    return best_action


def _min_distance(pos: tuple[int, int], others: list[tuple[int, int]]) -> float:
    if not others:
        return 0.0
    return float(min(abs(pos[0] - other[0]) + abs(pos[1] - other[1]) for other in others))
