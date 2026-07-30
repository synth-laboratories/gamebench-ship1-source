"""Task resolution for FrogsGame gold lanes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


def stable_config_string(task_id: str, seed: int, board: list[list[str]], max_steps: int) -> str:
    rows = ";".join(",".join(row) for row in board)
    return f"frogs:{task_id}:{seed}:{max_steps}:{rows}"


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    seed: int
    board: list[list[str]]
    rules: dict[str, Any]
    max_steps: int
    config_hash: str
    episode_id: str

    @property
    def n(self) -> int:
        return len(self.board)

    @property
    def colors(self) -> list[str]:
        return sorted({color for row in self.board for color in row})

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "seed": self.seed,
            "board": self.board,
            "rules": self.rules,
            "max_steps": self.max_steps,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }


def resolve_task(task: dict[str, Any], seed_override: int | None = None) -> ResolvedTask:
    task_id = str(task.get("task_id") or task.get("scenario_id") or "manual")
    seed = int(seed_override if seed_override is not None else task.get("seed", 0))
    raw_board = task.get("board") or task.get("grid")
    if raw_board is None:
        raise ValueError("frogs task requires board")
    board = [[str(cell) for cell in row] for row in raw_board]
    _validate_board(board)
    rules = dict(task.get("rules", {"base": "classic_frogs"}))
    max_steps = int(rules.get("overrides", {}).get("max_steps", task.get("max_steps", len(board) * 3)))
    config_hash = stable_hash(stable_config_string(task_id, seed, board, max_steps))
    episode_id = stable_hash(f"gamebench.frogs-singleplayer.episode:{task_id}:{seed}:{config_hash}", 32)
    return ResolvedTask(
        task_id=task_id,
        seed=seed,
        board=board,
        rules=rules,
        max_steps=max_steps,
        config_hash=config_hash,
        episode_id=episode_id,
    )


def _validate_board(board: list[list[str]]) -> None:
    if not board:
        raise ValueError("frogs board must be non-empty")
    n = len(board)
    if any(len(row) != n for row in board):
        raise ValueError("frogs board must be square")
    colors = {color for row in board for color in row}
    if len(colors) != n:
        raise ValueError(f"frogs board must have exactly {n} colors, found {len(colors)}")
