"""Golden scenario runner for Sokoban."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import SokobanEngine
from task_resolve import resolve_task


TASK_DIR = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    if "task" in entry:
        return dict(entry["task"])
    return {
        "schema": "gamebench.task.sokoban.v1",
        "task_id": entry["scenario_id"],
        "seed": int(entry.get("seed", 0)),
        "map": dict(entry["map"]),
        "rules": dict(entry.get("rules", {"base": "sparse_sokoban"})),
        "readouts": {"symbolic": "ascii_annotated", "visual": False},
        "checkpoint_every_n_steps": 1,
    }


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    if "scenario_id" in entry_or_task:
        scenario_id = str(entry_or_task["scenario_id"])
        task = scenario_to_task(entry_or_task)
        actions = list(entry_or_task.get("actions", []))
    else:
        task = dict(entry_or_task)
        scenario_id = str(task.get("task_id", "manual"))
        actions = list(task.get("actions", []))

    engine = SokobanEngine()
    engine.reset(resolve_task(task))
    for action in actions:
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(str(action))

    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "state": {
            "public": engine.public.to_dict(),
            "private": engine.private.to_dict(),
        },
        "readout": engine.symbolic_readout(),
    }
