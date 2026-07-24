"""Task resolution for the Rogue singleplayer GameBench lane."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    seed: int
    grid: list[str]
    max_steps: int
    objective: str
    inventory: list[dict[str, Any]]
    monsters: list[dict[str, Any]]
    traps: list[dict[str, Any]]
    source_map_cells: list[dict[str, Any]]
    level_objects: list[dict[str, Any]]
    config_hash: str
    episode_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "seed": self.seed,
            "grid": self.grid,
            "max_steps": self.max_steps,
            "objective": self.objective,
            "inventory": self.inventory,
            "monsters": self.monsters,
            "traps": self.traps,
            "source_map_cells": self.source_map_cells,
            "level_objects": self.level_objects,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }


def resolve_task(task: dict[str, Any], seed_override: int | None = None) -> ResolvedTask:
    task_id = str(task.get("task_id") or task.get("scenario_id") or "manual")
    seed = int(seed_override if seed_override is not None else task.get("seed", 0))
    grid = [str(row) for row in task.get("grid", [])]
    _validate_grid(grid)
    rules = dict(task.get("rules", {}))
    overrides = dict(rules.get("overrides", {}))
    max_steps = int(overrides.get("max_steps", task.get("max_steps", 80)))
    objective = str(task.get("objective", overrides.get("objective", "descend")))
    inventory = [dict(item) for item in overrides.get("inventory", task.get("inventory", []))]
    monsters = [dict(monster) for monster in overrides.get("monsters", task.get("monsters", []))]
    traps = [dict(trap) for trap in overrides.get("traps", task.get("traps", []))]
    source_map_cells = [dict(cell) for cell in overrides.get("source_map_cells", task.get("source_map_cells", task.get("map_cells", [])))]
    level_objects = [dict(obj) for obj in overrides.get("level_objects", task.get("level_objects", []))]
    inventory_text = json.dumps(inventory, sort_keys=True, separators=(",", ":"))
    monsters_text = json.dumps(monsters, sort_keys=True, separators=(",", ":"))
    traps_text = json.dumps(traps, sort_keys=True, separators=(",", ":"))
    source_map_cells_text = json.dumps(source_map_cells, sort_keys=True, separators=(",", ":"))
    level_objects_text = json.dumps(level_objects, sort_keys=True, separators=(",", ":"))
    if source_map_cells:
        text = f"rogue:{task_id}:{seed}:{max_steps}:{objective}:{';'.join(grid)}:{inventory_text}:{monsters_text}:{traps_text}:{source_map_cells_text}:{level_objects_text}"
    else:
        text = f"rogue:{task_id}:{seed}:{max_steps}:{objective}:{';'.join(grid)}:{inventory_text}:{monsters_text}:{traps_text}:{level_objects_text}"
    config_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    episode_id = hashlib.sha256(f"gamebench.rogue:{task_id}:{seed}:{config_hash}".encode("utf-8")).hexdigest()[:32]
    return ResolvedTask(task_id, seed, grid, max_steps, objective, inventory, monsters, traps, source_map_cells, level_objects, config_hash, episode_id)


def _validate_grid(grid: list[str]) -> None:
    if not grid:
        raise ValueError("rogue grid must be non-empty")
    width = len(grid[0])
    if width == 0:
        raise ValueError("rogue grid rows must be non-empty")
    if any(len(row) != width for row in grid):
        raise ValueError("rogue grid must be rectangular")
    if sum(row.count("@") for row in grid) != 1:
        raise ValueError("rogue grid must contain exactly one @ player start")
