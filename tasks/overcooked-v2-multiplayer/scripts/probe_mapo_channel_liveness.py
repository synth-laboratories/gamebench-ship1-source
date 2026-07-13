#!/usr/bin/env python3
"""Probe grounded-button channel liveness for MAPO Overcooked v2 candidates."""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared", TASK_DIR / "policies"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_io import format_joint_observation, normalize_joint_action
from engine import OvercookedV2Engine
from kitchen_nav import (
    WAIT,
    agent_positions,
    choose_joint_actions_heuristic,
    choose_worker_action,
    interact_toward,
    move_toward_fixture,
    nearest_fixture,
    resolve_kitchen_map,
)
from scenarios import scenario_to_task


def scenario_max_steps(suite: dict[str, Any], scenario: dict[str, Any]) -> int:
    overrides = dict((scenario.get("rules") or {}).get("overrides", {}))
    if "max_steps" in overrides:
        return int(overrides["max_steps"])
    return int(suite.get("max_steps", 96))


def button_first_action(engine: OvercookedV2Engine, readout: dict[str, Any]) -> dict[str, Any] | None:
    if engine.button_activation_ticks or not engine.button_recipe_indicators:
        return None
    joint_valid = readout.get("joint_valid_actions") or engine.joint_valid_actions()
    map_model = resolve_kitchen_map(readout, engine)
    positions = agent_positions(readout)
    for agent_id in sorted(joint_valid):
        obs = (readout.get("observations") or {}).get(agent_id) or {}
        if obs.get("held") is not None:
            continue
        valid = list(joint_valid.get(agent_id, [WAIT]))
        position = positions.get(agent_id)
        if position is None:
            continue
        blocked = {pos for other_id, pos in positions.items() if other_id != agent_id}
        target = nearest_fixture(position, set(engine.button_recipe_indicators), map_model, blocked)
        if target is None:
            continue
        action = interact_toward(position, str(obs.get("facing", "south")), target, valid)
        if action == WAIT:
            action = move_toward_fixture(position, set(engine.button_recipe_indicators), valid, map_model, blocked)
        if action == WAIT:
            continue
        return {candidate_id: action if candidate_id == agent_id else WAIT for candidate_id in sorted(joint_valid)}
    return None


def observation_recipe_visible(readout: dict[str, Any]) -> bool:
    observations = readout.get("observations") or {}
    return any((obs or {}).get("recipe_indicator_visible") for obs in observations.values())


def hide_public_recipe_until_visible(readout: dict[str, Any]) -> dict[str, Any]:
    if observation_recipe_visible(readout):
        return readout
    updated = copy.deepcopy(readout)
    public = updated.get("public") or {}
    public["recipe_id"] = None
    public["active_recipe_id"] = None
    public["recipe_ingredients"] = None
    updated["public"] = public
    return updated


def helper_free_joint_action(engine: OvercookedV2Engine, readout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sanitized = hide_public_recipe_until_visible(readout)
    joint_valid = sanitized.get("joint_valid_actions") or engine.joint_valid_actions()
    map_model = resolve_kitchen_map(sanitized, engine)
    positions = agent_positions(sanitized)
    actions: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(joint_valid):
        blocked = {pos for other_id, pos in positions.items() if other_id != agent_id}
        actions[agent_id] = choose_worker_action(
            agent_id,
            sanitized,
            list(joint_valid.get(agent_id, [WAIT])),
            map_model,
            blocked,
        )
    return actions


def run_one(suite: dict[str, Any], scenario: dict[str, Any], *, arm: str) -> dict[str, Any]:
    task = scenario_to_task(scenario)
    seed = int(scenario.get("seed", 0))
    max_steps = scenario_max_steps(suite, scenario)
    engine = OvercookedV2Engine()
    engine.reset_from_task(task, seed_override=seed)
    recipe_visible_turns = 0
    button_active_turns = 0
    ply = 0
    while not engine.private.terminated and not engine.private.truncated and ply < max_steps:
        readout = engine.symbolic_readout()
        observations = readout.get("observations") or {}
        if any((obs or {}).get("recipe_indicator_visible") for obs in observations.values()):
            recipe_visible_turns += 1
        if engine.button_activation_ticks:
            button_active_turns += 1
        if arm == "button_first":
            joint_action = button_first_action(engine, readout)
        else:
            joint_action = None
        if joint_action is None:
            joint_action = helper_free_joint_action(engine, readout)
            if not joint_action:
                decision = choose_joint_actions_heuristic(
                    hide_public_recipe_until_visible(readout),
                    readout.get("joint_valid_actions") or engine.joint_valid_actions(),
                    ply,
                    engine=engine.clone_for_sim(),
                )
                joint_action = normalize_joint_action(decision.get("joint_action") or {}, tuple(sorted(engine.agent_ids)))
        engine.step(joint_action)
        ply += 1
    messages = [event.message for event in engine.nev.events]
    button_activations = sum(1 for message in messages if str(message).startswith("ButtonActivated("))
    outcome = "success" if engine.private.terminated else "truncated" if engine.private.truncated else "failure"
    return {
        "arm": arm,
        "scenario_id": scenario.get("scenario_id", task.get("scenario_id")),
        "layout_id": scenario.get("layout_id"),
        "seed": seed,
        "outcome": outcome,
        "success": outcome == "success",
        "deliveries": int(engine.deliveries),
        "reward": float(engine.private.total_reward),
        "steps": int(engine.private.step_index),
        "button_activations": button_activations,
        "button_active_turns": button_active_turns,
        "recipe_visible_turns": recipe_visible_turns,
        "event_count": len(messages),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = sum(1 for row in rows if row["success"])
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_rate": round(successes / len(rows), 4) if rows else 0.0,
        "mean_reward": round(statistics.mean(float(row["reward"]) for row in rows), 4) if rows else 0.0,
        "button_activations": sum(int(row["button_activations"]) for row in rows),
        "button_active_turns": sum(int(row["button_active_turns"]) for row in rows),
        "recipe_visible_turns": sum(int(row["recipe_visible_turns"]) for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Overcooked v2 grounded-button channel liveness.")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    suite_path = Path(args.suite).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    suite = json.loads(suite_path.read_text())
    scenarios = list(suite.get("scenarios") or [])
    started = time.time()
    no_message = [run_one(suite, scenario, arm="no_message") for scenario in scenarios]
    button_first = [run_one(suite, scenario, arm="button_first") for scenario in scenarios]
    report = {
        "schema": "gamebench.overcooked_v2.mapo_channel_liveness.v1",
        "suite_id": suite.get("suite_id"),
        "suite_path": str(suite_path),
        "arms": {
            "no_message": summarize(no_message),
            "button_first": summarize(button_first),
        },
        "deltas": {
            "success_rate": round(summarize(button_first)["success_rate"] - summarize(no_message)["success_rate"], 4),
            "button_activations": summarize(button_first)["button_activations"] - summarize(no_message)["button_activations"],
            "recipe_visible_turns": summarize(button_first)["recipe_visible_turns"] - summarize(no_message)["recipe_visible_turns"],
        },
        "rows": {
            "no_message": no_message,
            "button_first": button_first,
        },
        "elapsed_s": round(time.time() - started, 3),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"suite_id": report["suite_id"], "arms": report["arms"], "deltas": report["deltas"]}, indent=2))


if __name__ == "__main__":
    main()
