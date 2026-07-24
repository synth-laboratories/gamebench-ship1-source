"""Golden scenario runner for Overcooked v2 multiplayer symbolic gold."""

from __future__ import annotations

from typing import Any

from engine import OvercookedV2Engine
from task_resolve import resolve_task

WAIT = {"kind": "wait"}


def scenario_to_task(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "gamebench.task.overcooked_v2.v1",
        "task_id": entry.get("task_id", entry["scenario_id"]),
        "scenario_id": entry["scenario_id"],
        "seed": entry.get("seed", 0),
        "layout_id": entry.get("layout_id", "demo_tiny"),
        "rules": entry.get("rules", {"base": "cooperative_full_obs"}),
        "readouts": dict(entry.get("readouts", {})),
    }


def _normalize_joint_action(raw: dict[str, Any], agent_ids: tuple[str, ...]) -> dict[str, Any]:
    normalized = {agent_id: dict(raw.get(agent_id, WAIT)) for agent_id in agent_ids}
    return normalized


def run_scenario(entry_or_task: dict[str, Any]) -> dict[str, Any]:
    if "scenario_id" in entry_or_task and "joint_actions" in entry_or_task:
        entry = entry_or_task
        scenario_id = str(entry["scenario_id"])
        task = scenario_to_task(entry)
        joint_actions = entry.get("joint_actions", [])
        checkpoint_after = entry.get("checkpoint_after")
        restore_then_actions = list(entry.get("restore_then_actions", []))
        seed = entry.get("seed")
    else:
        task = dict(entry_or_task)
        scenario_id = str(task.get("scenario_id", task.get("task_id", "manual")))
        joint_actions = list(task.get("joint_actions", []))
        checkpoint_after = task.get("checkpoint_after")
        restore_then_actions = list(task.get("restore_then_actions", []))
        seed = task.get("seed")

    engine = OvercookedV2Engine()
    engine.reset(resolve_task(task, seed_override=seed))
    agent_ids = engine.agent_ids
    checkpoint_blob: bytes | None = None
    for index, joint_action in enumerate(joint_actions, start=1):
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(_normalize_joint_action(joint_action, agent_ids))
        if checkpoint_after == index:
            checkpoint_blob = engine.checkpoint_bytes()
    if checkpoint_blob is not None:
        engine.restore_checkpoint(checkpoint_blob)
        for joint_action in restore_then_actions:
            if engine.private.terminated or engine.private.truncated:
                break
            engine.step(_normalize_joint_action(joint_action, agent_ids))
    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "checkpoint_cursor": engine.nev.cursor(),
        "state": {"public": engine.public.to_dict(), "private": engine.private.to_dict()},
        "readout": engine.symbolic_readout(),
    }
