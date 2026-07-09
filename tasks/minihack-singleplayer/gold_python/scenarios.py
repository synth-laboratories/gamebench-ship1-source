"""Golden scenario runner for MiniHack symbolic gold."""

from __future__ import annotations

from typing import Any

from engine import MiniHackEngine
from task_resolve import resolve_task


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "gamebench.task.minihack.v1",
        "task_id": entry.get("task_id", entry["scenario_id"]),
        "scenario_id": entry["scenario_id"],
        "seed": entry.get("seed", 0),
        "profile": entry.get("profile"),
        "map": entry.get("map"),
        "rules": entry.get("rules", {"base": "navigation"}),
        "readouts": entry.get("readouts", {"profile": "ascii_map"}),
    }


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    if "scenario_id" in entry_or_task:
        scenario_id = str(entry_or_task["scenario_id"])
        task = scenario_to_task(entry_or_task)
        actions = list(entry_or_task.get("actions", []))
        seed = entry_or_task.get("seed")
    else:
        task = dict(entry_or_task)
        scenario_id = str(task.get("scenario_id", task.get("task_id", "manual")))
        actions = list(task.get("actions", []))
        seed = task.get("seed")
    engine = MiniHackEngine()
    engine.reset(resolve_task(task, seed_override=seed))
    for action in actions:
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(action)
    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "checkpoint_cursor": engine.nev.cursor(),
        "state": {"public": engine.public.to_dict(), "private": engine.private.to_dict()},
        "readout": engine.symbolic_readout(),
    }
