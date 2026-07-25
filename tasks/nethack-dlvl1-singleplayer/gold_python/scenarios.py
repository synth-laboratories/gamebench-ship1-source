"""Scenario runner for the NetHack dlvl-1 Python gold lane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.task_resolve import resolve_task

from .engine import NethackDlvl1Engine


TASK_DIR = Path(__file__).resolve().parents[1]


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    if "task" in entry:
        return dict(entry["task"])
    return {key: value for key, value in entry.items() if key not in {"actions", "expected", "required_nev_kinds"}}


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    entry = dict(entry_or_task)
    task = scenario_to_task(entry)
    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    for action in list(entry.get("actions", task.get("actions", []))):
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        engine.step(action)
    readout = engine.symbolic_readout()
    return {
        "scenario_id": str(entry.get("scenario_id", task.get("task_id", "manual"))),
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "state": {"public": readout["public"], "private": readout["private"]},
        "readout": readout,
        "checkpoint": {"blob": engine.checkpoint_bytes().decode("utf-8"), "public": readout["public"], "private": readout["private"]},
    }


def load_scenario(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
