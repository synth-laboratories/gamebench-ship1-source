#!/usr/bin/env python3
"""Run one DungeonGrid code-policy candidate on a fixed suite."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gold_python import DungeonGridSession, load_scenario
from mechanics_probe_common import mechanics_probe_scenario


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("dungeongrid_candidate_policy", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load policy module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "plan_actions"):
        raise AttributeError(f"{path} must define plan_actions(scenario, objective=None)")
    return module


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_from_source(source: str) -> dict[str, Any]:
    if source == "mechanics_probe_common":
        return mechanics_probe_scenario()
    path = TASK_DIR / source
    return load_scenario(path)


def _planned_actions(module: Any, scenario: dict[str, Any], objective: dict[str, Any]) -> list[dict[str, Any]]:
    actions = module.plan_actions(copy.deepcopy(scenario), copy.deepcopy(objective))
    if not isinstance(actions, list):
        raise TypeError("plan_actions must return a list of action dictionaries")
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            raise TypeError(f"action {index} must be a dictionary with a string type")
    return copy.deepcopy(actions)


def _protocol_check(actions: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    if not bool(item.get("require_code_protocol", False)):
        return {"required": False, "ok": True, "messages": [], "failures": []}
    prefix = str(item.get("protocol_prefix", "DG|"))
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_|=;,+:.-/>")
    messages = [
        str(action.get("payload", {}).get("text", ""))
        for action in actions
        if action.get("type") == "message"
    ]
    failures: list[str] = []
    if not messages:
        failures.append("protocol_message_missing")
    for message in messages:
        if not message.startswith(prefix):
            failures.append("protocol_prefix_missing")
        if any(char not in allowed for char in message):
            failures.append("protocol_non_code_character")
        if " " in message:
            failures.append("protocol_contains_space")
    return {
        "required": True,
        "ok": not failures,
        "messages": messages,
        "failures": sorted(set(failures)),
    }


def _failure_modes(session: DungeonGridSession, invalid_actions: int, targets: set[str]) -> list[str]:
    if invalid_actions:
        return ["invalid_action"]
    missing = sorted(targets - set(session.achievements))
    modes: list[str] = []
    if missing:
        modes.append("missing_achievements")
    if any(target.startswith("objective.") for target in missing):
        modes.append("objective_incomplete")
    if any(target.startswith("combat.") for target in missing):
        modes.append("combat_incomplete")
    if any(target.startswith("coordination.") for target in missing):
        modes.append("coordination_incomplete")
    return modes or ["unsolved"]


def run_episode(module: Any, item: dict[str, Any], include_trace: bool) -> dict[str, Any]:
    scenario = _scenario_from_source(str(item["source"]))
    session = DungeonGridSession.reset(scenario)
    targets = set(str(target) for target in item.get("target_achievements", []))
    max_actions = int(item.get("max_actions", item.get("suite_max_actions", 80)))
    min_reward = float(item.get("min_reward", 0.0))
    objective = {
        "target_achievements": sorted(targets),
        "min_reward": min_reward,
        "max_actions": max_actions,
        "scenario_id": scenario["scenario_id"],
    }
    actions = _planned_actions(module, scenario, objective)[:max_actions]
    protocol = _protocol_check(actions, item)
    trace: list[dict[str, Any]] = []
    invalid_actions = 0
    for index, action in enumerate(actions):
        result = session.step(action)
        if not result["applied"]:
            invalid_actions += 1
        if include_trace:
            trace.append(
                {
                    "index": index,
                    "action": action,
                    "applied": bool(result["applied"]),
                    "active_agent": session.active_agent,
                    "total_reward": round(session.total_reward, 4),
                    "achievements": sorted(session.achievements),
                }
            )
        if session.done:
            break
    achievements = set(session.achievements)
    achievement_rate = len(targets & achievements) / len(targets) if targets else 1.0
    reward_rate = min(session.total_reward / min_reward, 1.0) if min_reward > 0 else 1.0
    solved = achievement_rate >= 1.0 and reward_rate >= 1.0 and invalid_actions == 0 and bool(protocol["ok"])
    score = 1.0 if solved else round((0.75 * achievement_rate) + (0.25 * reward_rate), 6)
    if protocol["required"] and not protocol["ok"]:
        score = min(score, 0.85)
    report = {
        "scenario_id": scenario["scenario_id"],
        "score": score,
        "solved": solved,
        "achievement_rate": round(achievement_rate, 6),
        "reward_rate": round(reward_rate, 6),
        "total_reward": round(session.total_reward, 4),
        "invalid_action_count": invalid_actions,
        "steps_executed": len(actions),
        "target_achievements": sorted(targets),
        "achievements": sorted(achievements),
        "missing_achievements": sorted(targets - achievements),
        "protocol": protocol,
        "failure_modes": [] if solved else _failure_modes(session, invalid_actions, targets),
        "state_digest": session.state_digest(),
    }
    if protocol["required"] and not protocol["ok"]:
        report["failure_modes"] = sorted(set(report["failure_modes"]) | set(protocol["failures"]))
    if include_trace:
        report["trace"] = trace
    return report


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    include_trace: bool = False,
) -> dict[str, Any]:
    started = time.time()
    module = load_policy_module(policy_path)
    suite = load_suite(suite_path)
    suite_max_actions = int(suite.get("max_actions", 80))
    episodes = []
    for raw_item in suite["scenarios"]:
        item = dict(raw_item)
        item["suite_max_actions"] = suite_max_actions
        episodes.append(run_episode(module, item, include_trace))
    scores = [float(item["score"]) for item in episodes]
    rewards = [float(item["total_reward"]) for item in episodes]
    successes = sum(1 for item in episodes if item["solved"])
    failure_counts = Counter(mode for item in episodes for mode in item["failure_modes"])
    invalid_actions = sum(int(item["invalid_action_count"]) for item in episodes)
    score = round(statistics.mean(scores), 6) if scores else 0.0
    report = {
        "schema": "gamebench.dungeongrid.policy_sweep_summary.v1",
        "env_family": "dungeongrid-multiplayer",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "score_metric": str(suite.get("score_metric", "mean_objective_score")),
        "n_scenarios": len(episodes),
        "successes": successes,
        "success_rate": round(successes / len(episodes), 4) if episodes else 0.0,
        "score": score,
        "mean_objective_score": score,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "invalid_action_count": invalid_actions,
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "elapsed_s": round(time.time() - started, 3),
        "episodes": episodes,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a DungeonGrid code-policy sweep.")
    parser.add_argument("--policy", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    report = run_policy_sweep(
        policy_path=Path(args.policy).expanduser().resolve(),
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve(),
        include_trace=bool(args.include_trace),
    )
    printable = {
        key: report[key]
        for key in ("suite_id", "score", "success_rate", "mean_reward", "failure_mode_counts", "elapsed_s")
    }
    print(json.dumps(printable, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
