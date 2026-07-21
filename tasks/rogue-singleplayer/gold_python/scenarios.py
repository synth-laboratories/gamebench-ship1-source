"""Golden scenario runner for Rogue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import RogueEngine
from task_resolve import resolve_task


TASK_DIR = Path(__file__).resolve().parents[1]


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    if "task" in entry:
        return dict(entry["task"])
    task = {
        "schema": "gamebench.task.rogue.v1",
        "task_id": entry["scenario_id"],
        "seed": int(entry.get("seed", 0)),
        "grid": list(entry["grid"]),
        "rules": dict(entry.get("rules", {"base": "modern_rogue_core"})),
        "objective": str(entry.get("objective", "descend")),
        "readouts": {"symbolic": "ascii", "visual": True},
        "checkpoint_every_n_steps": 1,
    }
    if "inventory" in entry:
        task["inventory"] = [dict(item) for item in entry["inventory"]]
    if "monsters" in entry:
        task["monsters"] = [dict(monster) for monster in entry["monsters"]]
    if "traps" in entry:
        task["traps"] = [dict(trap) for trap in entry["traps"]]
    if "source_map_cells" in entry:
        task["source_map_cells"] = [dict(cell) for cell in entry["source_map_cells"]]
    if "map_cells" in entry:
        task["source_map_cells"] = [dict(cell) for cell in entry["map_cells"]]
    if "level_objects" in entry:
        task["level_objects"] = [dict(obj) for obj in entry["level_objects"]]
    return task


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    if "scenario_id" in entry_or_task:
        scenario_id = str(entry_or_task["scenario_id"])
        task = scenario_to_task(entry_or_task)
        actions = list(entry_or_task.get("actions", []))
    else:
        task = dict(entry_or_task)
        scenario_id = str(task.get("task_id", "manual"))
        actions = list(task.get("actions", []))
    engine = RogueEngine()
    engine.reset(resolve_task(task))
    for action in actions:
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(str(action))
    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "state": {"public": engine.public.to_dict(), "private": engine.private.to_dict()},
        "readout": engine.symbolic_readout(),
        "checkpoint": {"source_state_projection": engine.source_state_projection()},
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
