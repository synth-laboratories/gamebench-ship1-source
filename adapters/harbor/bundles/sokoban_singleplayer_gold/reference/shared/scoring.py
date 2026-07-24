"""Sokoban policy scoring shared by sweeps and hillclimb reports."""

from __future__ import annotations

from typing import Mapping


SOKOBAN_MILESTONES: tuple[str, ...] = (
    "first_push",
    "first_box_on_target",
    "level_complete",
)


def sokoban_milestone_universe() -> list[str]:
    return list(SOKOBAN_MILESTONES)


def milestone_frequency_from_episodes(episodes: list[set[str]]) -> dict[str, int]:
    counts = {name: 0 for name in SOKOBAN_MILESTONES}
    for unlocked in episodes:
        for name in SOKOBAN_MILESTONES:
            if name in unlocked:
                counts[name] += 1
    return counts


def puzzle_success_score(episodes: list[dict[str, object]]) -> float:
    """Primary hillclimb score: solved puzzles / episodes."""

    if not episodes:
        return 0.0
    solved = sum(1 for episode in episodes if bool(episode.get("solved")))
    return solved / len(episodes)


def milestone_coverage_score(frequency: Mapping[str, int | float], episode_count: int) -> float:
    if episode_count <= 0:
        return 0.0
    rates = [
        min(1.0, max(0.0, float(frequency.get(name, 0)) / float(episode_count)))
        for name in SOKOBAN_MILESTONES
    ]
    return sum(rates) / len(rates)


def composite_policy_score(episodes: list[dict[str, object]]) -> float:
    """Weight solved puzzles heavily; milestone coverage breaks ties."""

    if not episodes:
        return 0.0
    success = puzzle_success_score(episodes)
    milestone_sets = [set(episode.get("achievements") or []) for episode in episodes]
    coverage = milestone_coverage_score(milestone_frequency_from_episodes(milestone_sets), len(episodes))
    return round((0.85 * success) + (0.15 * coverage), 6)
