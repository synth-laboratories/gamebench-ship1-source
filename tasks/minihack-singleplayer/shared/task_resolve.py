"""Task resolution for MiniHack symbolic gold lanes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from layout import ParsedLayout
from worldgen import build_layout, parse_ascii_rows


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    seed: int
    profile: str
    width: int
    height: int
    walls: frozenset[tuple[int, int]]
    goals: frozenset[tuple[int, int]]
    targets: frozenset[tuple[int, int]]
    player_start: tuple[int, int]
    boulders_start: frozenset[tuple[int, int]]
    monsters_start: frozenset[tuple[int, int]]
    lava_start: frozenset[tuple[int, int]]
    frozen_start: frozenset[tuple[int, int]]
    items_start: frozenset[tuple[tuple[int, int], str]]
    rules: dict[str, Any]
    max_steps: int
    win_mode: str
    config_hash: str
    episode_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "seed": self.seed,
            "profile": self.profile,
            "width": self.width,
            "height": self.height,
            "walls": [list(pos) for pos in sorted(self.walls)],
            "goals": [list(pos) for pos in sorted(self.goals)],
            "targets": [list(pos) for pos in sorted(self.targets)],
            "player_start": list(self.player_start),
            "boulders_start": [list(pos) for pos in sorted(self.boulders_start)],
            "monsters_start": [list(pos) for pos in sorted(self.monsters_start)],
            "lava_start": [list(pos) for pos in sorted(self.lava_start)],
            "frozen_start": [list(pos) for pos in sorted(self.frozen_start)],
            "items_start": [[list(pos), item_id] for pos, item_id in sorted(self.items_start)],
            "rules": self.rules,
            "max_steps": self.max_steps,
            "win_mode": self.win_mode,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }


def _layout_to_resolved(
    task_id: str,
    seed: int,
    profile: str,
    layout: ParsedLayout,
    rules: dict[str, Any],
    max_steps: int,
    win_mode: str,
) -> ResolvedTask:
    items_repr = sorted(layout.items_start)
    config_material = (
        f"minihack:{task_id}:{seed}:{profile}:{layout.width}x{layout.height}:"
        f"{sorted(layout.walls)}:{sorted(layout.goals)}:{sorted(layout.targets)}:"
        f"{layout.player_start}:{sorted(layout.boulders_start)}:"
        f"{sorted(layout.monsters_start)}:{sorted(layout.lava_start)}:"
        f"{sorted(layout.frozen_start)}:{items_repr}:{win_mode}:{max_steps}"
    )
    config_hash = stable_hash(config_material)
    episode_id = stable_hash(f"gamebench.minihack-singleplayer.episode:{task_id}:{seed}:{config_hash}", 32)
    return ResolvedTask(
        task_id=task_id,
        seed=seed,
        profile=profile,
        width=layout.width,
        height=layout.height,
        walls=layout.walls,
        goals=layout.goals,
        targets=layout.targets,
        player_start=layout.player_start,
        boulders_start=layout.boulders_start,
        monsters_start=layout.monsters_start,
        lava_start=layout.lava_start,
        frozen_start=layout.frozen_start,
        items_start=layout.items_start,
        rules=rules,
        max_steps=max_steps,
        win_mode=win_mode,
        config_hash=config_hash,
        episode_id=episode_id,
    )


def resolve_task(task: dict[str, Any], seed_override: int | None = None) -> ResolvedTask:
    task_id = str(task.get("task_id") or task.get("scenario_id") or "manual")
    seed = int(seed_override if seed_override is not None else task.get("seed", 0))
    profile = str(task.get("profile") or task.get("world", {}).get("profile") or "corridor_straight")
    rules = dict(task.get("rules", {"base": "navigation"}))
    overrides = dict(rules.get("overrides", {}))
    max_steps = int(overrides.get("max_steps", task.get("max_steps", 64)))
    win_mode = str(overrides.get("win_mode", _default_win_mode(rules.get("base"))))
    if task.get("map"):
        layout = parse_ascii_rows([str(row) for row in task["map"]])
    else:
        layout = build_layout(profile, seed)
    return _layout_to_resolved(task_id, seed, profile, layout, rules, max_steps, win_mode)


def _default_win_mode(base: str | None) -> str:
    if base == "boxoban":
        return "all_boulders_on_targets"
    return "reach_goal"
