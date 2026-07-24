"""Crafter achievement scoring shared by sweeps and hillclimb reports."""

from __future__ import annotations

import math
from typing import Mapping


CRAFTER_ACHIEVEMENTS: tuple[str, ...] = (
    "collect_coal",
    "collect_diamond",
    "collect_drink",
    "collect_iron",
    "collect_sapling",
    "collect_stone",
    "collect_wood",
    "defeat_skeleton",
    "defeat_zombie",
    "eat_cow",
    "eat_plant",
    "make_iron_pickaxe",
    "make_iron_sword",
    "make_stone_pickaxe",
    "make_stone_sword",
    "make_wood_pickaxe",
    "make_wood_sword",
    "place_furnace",
    "place_plant",
    "place_stone",
    "place_table",
    "wake_up",
)


def crafter_achievement_universe() -> list[str]:
    return list(CRAFTER_ACHIEVEMENTS)


def achievement_success_score(achievement_frequency: Mapping[str, float | int], episode_count: int) -> float:
    """RunBench-compatible geometric mean over per-achievement success rates."""

    if episode_count <= 0:
        return 0.0
    log_terms: list[float] = []
    for name in CRAFTER_ACHIEVEMENTS:
        raw = float(achievement_frequency.get(name, 0.0))
        rate = min(1.0, max(0.0, raw / float(episode_count)))
        log_terms.append(math.log1p(rate))
    return math.exp(sum(log_terms) / len(log_terms)) - 1.0


def goal_success_score(achievements: set[str] | list[str], objective: str) -> float:
    """Return 1.0 when a goal-conditioned objective achievement was unlocked."""

    return 1.0 if objective in set(achievements) else 0.0


def standard_unique_achievement_reward(achievement_count: int) -> float:
    """Standard mode terminal env reward equals unique achievements unlocked."""

    return float(max(0, int(achievement_count)))


def achievement_frequency_from_sets(episodes: list[set[str]]) -> dict[str, int]:
    counts = {name: 0 for name in CRAFTER_ACHIEVEMENTS}
    for unlocked in episodes:
        for name in CRAFTER_ACHIEVEMENTS:
            if name in unlocked:
                counts[name] += 1
    return counts

