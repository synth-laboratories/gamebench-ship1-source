"""Scenario execution for GameBench Craftax fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import CraftaxEngine
from task_resolve import resolve_task


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "gamebench.task.craftax.v1",
        "task_id": entry.get("task_id", entry["scenario_id"]),
        "scenario_id": entry["scenario_id"],
        "seed": entry.get("seed", 0),
        "world": entry.get("world", {"use_default": "policy_dev_small"}),
        "rules": entry.get("rules", {"base": "symbolic_no_homeostasis"}),
        "readouts": entry.get("readouts", {"profile": "symbolic_compact"}),
    }


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    if "scenario_id" in entry_or_task:
        entry = entry_or_task
        scenario_id = str(entry["scenario_id"])
        task = scenario_to_task(entry)
        actions = list(entry.get("actions", []))
        checkpoint_after = entry.get("checkpoint_after")
        restore_then_actions = list(entry.get("restore_then_actions", []))
        seed = entry.get("seed")
    else:
        task = dict(entry_or_task)
        scenario_id = str(task.get("scenario_id", task.get("task_id", "manual")))
        actions = list(task.get("actions", []))
        checkpoint_after = task.get("checkpoint_after")
        restore_then_actions = list(task.get("restore_then_actions", []))
        seed = task.get("seed")
    engine = CraftaxEngine()
    engine.reset(resolve_task(task, seed_override=seed))
    checkpoint_blob: bytes | None = None
    for index, action in enumerate(actions, start=1):
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(action)
        if checkpoint_after == index:
            checkpoint_blob = engine.checkpoint_bytes()
    if checkpoint_blob is not None:
        engine.restore_checkpoint(checkpoint_blob)
        for action in restore_then_actions:
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

