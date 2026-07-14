"""Scenario execution for synthetic Earthborne Rangers fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import EarthborneRangersEngine
from shared.scoring import score_summary
from task_resolve import SCHEMA, resolve_task


TASK_DIR = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "task_id": entry.get("task_id", entry["scenario_id"]),
        "scenario_id": entry["scenario_id"],
        "seed": entry.get("seed", 0),
        "ranger_id": entry.get("ranger_id", "synthetic_ranger"),
        "default_archetype": entry.get("default_archetype", "pathfinder"),
        "starting_location": entry.get("starting_location", "trailhead"),
        "max_steps": entry.get("max_steps", 24),
        "max_days": entry.get("max_days", 5),
        "objectives": entry.get("objectives"),
        "rules": entry.get("rules", {}),
        "reflexion": entry.get("reflexion", {}),
    }


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    is_fixture_scenario = "schema" not in entry_or_task and "scenario_id" in entry_or_task
    if is_fixture_scenario:
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
    engine = EarthborneRangersEngine()
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
    state = {"public": engine.public.to_dict(), "private": engine.private.to_dict(), "full_state": engine.symbolic_readout()["full_state"]}
    events = engine.nev.export()
    summary = score_summary(state, events)
    summary["archetype"] = engine.public.archetype
    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": events,
        "checkpoint_cursor": engine.nev.cursor(),
        "state": state,
        "readout": engine.symbolic_readout(),
        "summary": summary,
    }
