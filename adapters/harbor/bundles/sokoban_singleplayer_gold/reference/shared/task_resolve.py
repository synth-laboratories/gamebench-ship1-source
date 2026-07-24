"""Deterministic Sokoban task resolver shared by gold lanes."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
WALL = 0
FLOOR = 1
TARGET = 2
BOX_ON_TARGET = 3
BOX = 4
PLAYER = 5
PLAYER_ON_TARGET = 6


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    puzzle_id: str
    seed: int
    config_hash: str
    room_fixed: list[list[int]]
    room_state: list[list[int]]
    goals: list[tuple[int, int]]
    boxes: list[tuple[int, int]]
    player: tuple[int, int]
    max_steps: int
    rewards: dict[str, float]
    errors: dict[str, Any]
    curriculum: dict[str, Any] = field(default_factory=dict)
    monty_reward: dict[str, Any] = field(default_factory=dict)
    resolved_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "puzzle_id": self.puzzle_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "room_fixed": self.room_fixed,
            "room_state": self.room_state,
            "goals": [list(pos) for pos in self.goals],
            "boxes": [list(pos) for pos in self.boxes],
            "player": list(self.player),
            "max_steps": self.max_steps,
            "rewards": self.rewards,
            "errors": self.errors,
            "curriculum": self.curriculum,
            "monty_reward": self.monty_reward,
            "resolved_json": self.resolved_json,
        }


def resolve_task(task: dict[str, Any], seed_override: int | None = None) -> ResolvedTask:
    if task.get("schema") not in (None, "gamebench.task.sokoban.v1"):
        raise ValueError(f"unsupported sokoban task schema: {task.get('schema')}")

    seed = int(seed_override if seed_override is not None else task.get("seed", task.get("map", {}).get("seed", 0)))
    task_id = str(task.get("task_id", "sokoban_manual"))
    map_doc = _resolve_map(task.get("map", {}), seed)
    rules = _resolve_rules(task.get("rules", {}))
    monty_reward = _resolve_monty_reward(task, rules)
    grid = _ascii_rows(map_doc["grid"])
    room_fixed, room_state, goals, boxes, player = ascii_to_int_grids(grid)

    resolved = {
        "schema": "gamebench.task.sokoban.v1",
        "task_id": task_id,
        "seed": seed,
        "map": {
            "puzzle_id": map_doc["puzzle_id"],
            "grid": grid,
            "metadata": map_doc.get("metadata", {}),
        },
        "rules": rules,
        "readouts": task.get("readouts", {"symbolic": "ascii_annotated", "visual": False}),
        "checkpoint_every_n_steps": int(task.get("checkpoint_every_n_steps", 1)),
    }
    digest = hashlib.sha256(json.dumps(resolved, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    curriculum_meta = dict(map_doc.get("metadata", {}))
    curriculum_meta.update(map_doc.get("curriculum_extra", {}))
    return ResolvedTask(
        task_id=task_id,
        puzzle_id=str(map_doc["puzzle_id"]),
        seed=seed,
        config_hash=f"sha256:{digest}",
        room_fixed=room_fixed,
        room_state=room_state,
        goals=goals,
        boxes=boxes,
        player=player,
        max_steps=int(rules.get("max_steps", 120)),
        rewards={key: float(value) for key, value in rules.get("rewards", {}).items()},
        errors=dict(rules.get("errors", {"mode": "silent"})),
        curriculum=curriculum_meta,
        monty_reward=monty_reward,
        resolved_json=resolved,
    )


def ascii_to_int_grids(rows: list[str]) -> tuple[list[list[int]], list[list[int]], list[tuple[int, int]], list[tuple[int, int]], tuple[int, int]]:
    width = max(len(row) for row in rows)
    room_fixed: list[list[int]] = []
    room_state: list[list[int]] = []
    goals: list[tuple[int, int]] = []
    boxes: list[tuple[int, int]] = []
    player: tuple[int, int] | None = None
    for r, raw_row in enumerate(rows):
        fixed_row: list[int] = []
        state_row: list[int] = []
        for c, ch in enumerate(raw_row.ljust(width, "#")):
            if ch == "#":
                fixed_row.append(WALL)
                state_row.append(WALL)
            elif ch in (".", "G"):
                fixed_row.append(TARGET)
                state_row.append(TARGET)
                goals.append((r, c))
            elif ch == "*":
                fixed_row.append(TARGET)
                state_row.append(BOX_ON_TARGET)
                goals.append((r, c))
                boxes.append((r, c))
            elif ch == "+":
                fixed_row.append(TARGET)
                state_row.append(PLAYER_ON_TARGET)
                goals.append((r, c))
                player = (r, c)
            elif ch == "$":
                fixed_row.append(FLOOR)
                state_row.append(BOX)
                boxes.append((r, c))
            elif ch == "@":
                fixed_row.append(FLOOR)
                state_row.append(PLAYER)
                player = (r, c)
            else:
                fixed_row.append(FLOOR)
                state_row.append(FLOOR)
        room_fixed.append(fixed_row)
        room_state.append(state_row)
    if player is None:
        raise ValueError("sokoban map has no player")
    if not goals:
        raise ValueError("sokoban map has no goals")
    if not boxes:
        raise ValueError("sokoban map has no boxes")
    return room_fixed, room_state, goals, boxes, player


def grid_to_ascii(room_fixed: list[list[int]], player: tuple[int, int], boxes: set[tuple[int, int]]) -> list[str]:
    rows: list[str] = []
    for r, fixed_row in enumerate(room_fixed):
        chars: list[str] = []
        for c, fixed in enumerate(fixed_row):
            pos = (r, c)
            on_target = fixed == TARGET
            if fixed == WALL:
                chars.append("#")
            elif pos == player:
                chars.append("+" if on_target else "@")
            elif pos in boxes:
                chars.append("*" if on_target else "$")
            elif on_target:
                chars.append(".")
            else:
                chars.append(" ")
        rows.append("".join(chars).rstrip())
    return rows


def canonical_task(task: dict[str, Any]) -> str:
    return json.dumps(task, sort_keys=True, separators=(",", ":"))


def load_task_path(path: Path | str) -> dict[str, Any]:
    task_path = Path(path)
    if not task_path.is_absolute():
        task_path = TASK_DIR / task_path
    return json.loads(task_path.read_text())


def _resolve_rules(rules_spec: dict[str, Any]) -> dict[str, Any]:
    base_name = rules_spec.get("base", "sparse_sokoban")
    base_path = TASK_DIR / "defaults" / "rules" / f"{base_name}.json"
    if not base_path.exists():
        raise FileNotFoundError(f"missing rules default: {base_path}")
    merged = json.loads(base_path.read_text())
    _deep_merge(merged, rules_spec.get("overrides", {}))
    return merged


def _resolve_monty_reward(task: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    spec = task.get("monty_reward") or rules.get("monty_reward")
    if spec is None:
        return {}
    if isinstance(spec, str):
        path = TASK_DIR / "defaults" / "monty_rewards" / f"{spec}.json"
        if not path.exists():
            raise FileNotFoundError(f"missing monty reward default: {path}")
        return dict(json.loads(path.read_text()))
    return dict(spec)


def _level_bank_path(name: str) -> Path:
    curriculum_path = TASK_DIR / "defaults" / "curriculum.json"
    if curriculum_path.exists():
        tiers = dict(json.loads(curriculum_path.read_text()).get("tiers", {}))
        if name in tiers:
            return TASK_DIR / "defaults" / tiers[name]
    direct = TASK_DIR / "defaults" / "levels" / f"{name}.json"
    if direct.exists():
        return direct
    raise FileNotFoundError(f"missing sokoban level bank: {name}")


def _resolve_puzzle_ref(puzzle_ref: str) -> dict[str, Any]:
    verified_path = TASK_DIR / "defaults" / "levels" / "verified_puzzles.json"
    if not verified_path.exists():
        raise FileNotFoundError(f"missing verified puzzle bank: {verified_path}")
    puzzles = dict(json.loads(verified_path.read_text()).get("puzzles", {}))
    puzzle = puzzles.get(puzzle_ref)
    if puzzle is None:
        raise KeyError(f"unknown puzzle_ref: {puzzle_ref}")
    return {
        "puzzle_id": str(puzzle["id"]),
        "grid": _ascii_rows(puzzle["grid"]),
        "metadata": {
            "puzzle_ref": puzzle_ref,
            "name": puzzle.get("name", puzzle["id"]),
            "optimal_steps": puzzle.get("optimal_steps"),
        },
    }


def _resolve_map(map_spec: dict[str, Any], seed: int) -> dict[str, Any]:
    if map_spec.get("source") == "inline" or "grid" in map_spec:
        return {
            "puzzle_id": str(map_spec.get("puzzle_id", "inline")),
            "grid": _ascii_rows(map_spec["grid"]),
            "metadata": dict(map_spec.get("metadata", {})),
        }
    puzzle_ref = map_spec.get("puzzle_ref") or map_spec.get("puzzle_id")
    if puzzle_ref and map_spec.get("source") in (None, "verified", "puzzle_ref"):
        return _resolve_puzzle_ref(str(puzzle_ref))
    default_name = str(map_spec.get("use_default", "curriculum_easy"))
    level_doc = json.loads(_level_bank_path(default_name).read_text())
    levels = list(level_doc["levels"])
    if "seed" in map_spec or seed:
        index = int(seed) % len(levels)
    else:
        index = int(map_spec.get("index", 0)) % len(levels)
    chosen = levels[index]
    return {
        "puzzle_id": str(chosen["id"]),
        "grid": _ascii_rows(chosen["grid"]),
        "metadata": {
            "default": default_name,
            "index": index,
            "name": chosen.get("name", chosen["id"]),
            "optimal_steps": chosen.get("optimal_steps"),
        },
        "curriculum_extra": {
            "tier": level_doc.get("tier", default_name),
            "num_boxes": chosen.get("num_boxes"),
        },
    }


def _ascii_rows(value: Any) -> list[str]:
    if isinstance(value, str):
        rows = [row for row in value.splitlines() if row]
    else:
        rows = [str(row) for row in value]
    if not rows:
        raise ValueError("empty sokoban grid")
    return rows


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
