"""Golden scenario runner for Crafter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import CrafterEngine
from task_resolve import resolve_task


TASK_DIR = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    if "task" in entry:
        return dict(entry["task"])
    task = {
        "schema": "gamebench.task.crafter.v1",
        "task_id": entry["scenario_id"],
        "scenario_id": entry["scenario_id"],
        "world": dict(entry.get("world", {"use_default": "policy_dev_small", "seed": int(entry.get("seed", 101))})),
        "rules": dict(entry.get("rules", {"base": "no_homeostasis"})),
        "readouts": dict(entry.get("readouts", {"symbolic": "symbolic_compact", "visual": False})),
        "checkpoint_every_n_steps": int(entry.get("checkpoint_every_n_steps", 10)),
    }
    for key in ("stream", "monty_reward", "agent_policy"):
        if key in entry:
            task[key] = entry[key]
    return task


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    if "scenario_id" in entry_or_task:
        scenario_id = str(entry_or_task["scenario_id"])
        task = scenario_to_task(entry_or_task)
        actions = list(entry_or_task.get("actions", []))
    else:
        task = dict(entry_or_task)
        scenario_id = str(task.get("scenario_id", task.get("task_id", "manual")))
        actions = list(task.get("actions", []))

    engine = CrafterEngine()
    engine.reset(resolve_task(task))
    checkpoint_cursor: int | None = None
    checkpoint_blob: bytes | None = None
    for index, action in enumerate(actions):
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(action)
        if entry_or_task.get("checkpoint_after") == index + 1:
            checkpoint_blob = engine.checkpoint_bytes()
            checkpoint_cursor = engine.nev.cursor()
    if checkpoint_blob and entry_or_task.get("restore_then_actions"):
        engine.restore_checkpoint(checkpoint_blob)
        for action in entry_or_task["restore_then_actions"]:
            if engine.private.terminated or engine.private.truncated:
                break
            engine.step(action)

    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "checkpoint_cursor": checkpoint_cursor,
        "state": {
            "public": engine.public.to_dict(),
            "private": engine.private.to_dict(),
        },
        "readout": engine.symbolic_readout(),
    }
