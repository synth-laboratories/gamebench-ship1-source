"""Scenario runner — joint-step policy-vs-policy rollouts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gold.board import MARK_TO_AGENT
from gold.core.nev import EventKind
from gold.engine import AGENT_IDS, episode_id_from_task, TicTacToeMultiplayerEngine, WAIT_ACTION
from gold.monty import public_dict_from_engine, resolve_policy

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def load_task(task_path: Path) -> dict[str, Any]:
    return json.loads(task_path.read_text())


def _policy_spec(task: dict[str, Any], agent_id: str) -> dict[str, Any]:
    if agent_id == "agent_0":
        if "agent_0_policy" in task:
            return task["agent_0_policy"]
        if "x_policy" in task:
            return task["x_policy"]
    if agent_id == "agent_1":
        if "agent_1_policy" in task:
            return task["agent_1_policy"]
        if "o_policy" in task:
            return task["o_policy"]
    raise KeyError(f"no policy spec for {agent_id}")


def scenario_from_legacy(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "gamebench.task.v1",
        "task_id": entry["scenario_id"],
        "scenario_id": entry["scenario_id"],
        "seed": entry["seed"],
        "max_plies": entry.get("max_plies", 9),
        "opening_moves": list(entry.get("opening_moves", [])),
        "agent_0_policy": {
            "kind": "registry",
            "policy_id": entry.get("agent_0_policy_id", entry.get("x_policy_id")),
        },
        "agent_1_policy": {
            "kind": "registry",
            "policy_id": entry.get("agent_1_policy_id", entry.get("o_policy_id")),
        },
    }


def _joint_from_opening(opening: dict[str, Any]) -> dict[str, Any]:
    if "joint_action" in opening:
        return dict(opening["joint_action"])
    mark = str(opening["player"])
    agent_id = MARK_TO_AGENT[mark]
    joint = {agent: dict(WAIT_ACTION) for agent in AGENT_IDS}
    joint[agent_id] = {"kind": "place", "position": int(opening["position"])}
    return joint


def run_scenario(task: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(task["scenario_id"])
    seed = int(task.get("seed", 0))
    max_plies = int(task.get("max_plies", 9))
    opening_moves = list(task.get("opening_moves", []))

    policies = {
        agent_id: resolve_policy(_policy_spec(task, agent_id), agent_id) for agent_id in AGENT_IDS
    }

    engine = TicTacToeMultiplayerEngine()
    engine.reset(
        scenario_id=scenario_id,
        seed=seed,
        episode_id=episode_id_from_task(task),
        task_id=str(task.get("task_id", scenario_id)),
    )

    for opening in opening_moves:
        engine.step(_joint_from_opening(dict(opening)))

    plies = 0
    while not engine.private.terminated and not engine.private.truncated and plies < max_plies:
        current = engine.public.current_agent
        joint_action = {agent_id: dict(WAIT_ACTION) for agent_id in AGENT_IDS}
        public = public_dict_from_engine(engine.public)
        joint_action[current] = policies[current](public, seed, plies)
        engine.step(joint_action)
        plies += 1

    if not engine.private.terminated and not engine.private.truncated:
        engine._append_nev(
            kind=EventKind.DEBUG,
            message=f"RolloutStopped(max_plies={max_plies})",
            payload={"max_plies": max_plies},
        )

    return {
        "scenario_id": scenario_id,
        "events": engine.nev.legacy_strings(),
        "nev": engine.nev.export(),
        "state": {
            "public": engine.public.to_dict(),
            "private": engine.private.to_dict(),
        },
    }
