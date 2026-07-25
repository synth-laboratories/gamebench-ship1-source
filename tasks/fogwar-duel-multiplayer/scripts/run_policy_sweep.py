#!/usr/bin/env python3
"""Score a Fog Duel Lite code policy on a fixed, private-observation suite."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable


TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import FogDuelEnv


PolicyFn = Callable[[dict[str, Any]], dict[str, Any]]


def load_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    if suite.get("schema") != "gamebench.fogwar_duel.policy_sweep.v1":
        raise ValueError(f"unsupported Fogwar policy suite: {path}")
    if suite.get("candidate_agent") != "agent_0":
        raise ValueError("Fogwar DEO currently evaluates agent_0 under fixed alternation")
    if suite.get("opponent_policy") != "passive_wait_v1":
        raise ValueError("Fogwar DEO requires the fixed passive_wait_v1 opponent")
    if not isinstance(suite.get("scenarios"), list) or not suite["scenarios"]:
        raise ValueError("Fogwar DEO suite must define at least one scenario")
    return suite


def load_policy(path: Path) -> PolicyFn:
    module_name = f"gamebench_fogwar_policy_{hashlib.sha256(str(path).encode()).hexdigest()[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy = getattr(module, "act", None)
    if not callable(policy):
        raise AttributeError(f"{path} must define act(observation)")
    return policy


def _policy_request(policy: PolicyFn, observation: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    try:
        request = policy(observation)
    except Exception as exc:  # score a candidate failure as one invalid request
        return {"actions": [{"kind": "policy_exception"}]}, f"{type(exc).__name__}: {exc}"
    if not isinstance(request, dict):
        return {"actions": [{"kind": "policy_invalid_return"}]}, "policy returned a non-object request"
    return request, None


def _submitted_action_count(request: dict[str, Any]) -> int:
    actions = request.get("actions")
    return len(actions) if isinstance(actions, list) else 1


def _policy_illegal_count(events: list[dict[str, Any]], *, start: int) -> int:
    return sum(
        event.get("kind") == "illegal_action" and event.get("actor") == "agent_0"
        for event in events[start:]
    )


def rollout_policy(*, policy: PolicyFn, scenario_id: str, max_half_turns: int) -> dict[str, Any]:
    """Run agent_0 policy versus fixed agent_1 wait requests in engine turn order."""
    env = FogDuelEnv()
    observation = env.reset(scenario_id)
    submitted_actions = 0
    illegal_actions = 0
    policy_failures: list[str] = []
    half_turns = 0

    while env.state_projection()["terminal"] is None and half_turns < max_half_turns:
        active_agent = observation.get("active_agent")
        event_start = len(env.events)
        if active_agent == "agent_0":
            request, failure = _policy_request(policy, observation)
            submitted_actions += _submitted_action_count(request)
            if failure is not None:
                policy_failures.append(failure)
        elif active_agent == "agent_1":
            request = {"actions": [{"kind": "wait"}]}
        else:
            raise RuntimeError(f"unknown active agent in Fogwar rollout: {active_agent!r}")
        result = env.step(request)
        if active_agent == "agent_0":
            illegal_actions += _policy_illegal_count(env.events, start=event_start)
        observation = result["observation"]
        half_turns += 1

    terminal = env.state_projection()["terminal"]
    if terminal is None:
        raise RuntimeError(
            f"scenario {scenario_id} did not terminate within {max_half_turns} half-turns"
        )
    reward = float(terminal["scores"]["agent_0"])
    reliability = max(0.0, 1.0 - illegal_actions / max(1, submitted_actions))
    score = 0.80 * (reward / 3.0) + 0.20 * reliability
    return {
        "scenario_id": scenario_id,
        "terminal_reason": terminal["reason"],
        "winner": terminal["winner"],
        "agent_0_terminal_reward": reward,
        "submitted_policy_actions": submitted_actions,
        "invalid_policy_actions": illegal_actions,
        "reliability": round(reliability, 6),
        "scenario_score": round(score, 6),
        "half_turns": half_turns,
        "policy_failures": policy_failures,
    }


def run_policy_sweep(*, policy_path: Path, suite_path: Path, output_path: Path) -> dict[str, Any]:
    """Run the policy and write its canonical per-candidate summary."""
    suite = load_suite(suite_path)
    policy = load_policy(policy_path)
    results = [
        rollout_policy(
            policy=policy,
            scenario_id=str(scenario["scenario_id"]),
            max_half_turns=int(suite["max_half_turns"]),
        )
        for scenario in suite["scenarios"]
    ]
    count = len(results)
    report = {
        "schema": "gamebench.fogwar_duel.policy_report.v1",
        "suite_id": suite["suite_id"],
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "score_metric": suite["score"]["metric"],
        "score": round(sum(float(row["scenario_score"]) for row in results) / count, 6),
        "mean_terminal_reward": round(
            sum(float(row["agent_0_terminal_reward"]) for row in results) / count,
            6,
        ),
        "mean_reliability": round(sum(float(row["reliability"]) for row in results) / count, 6),
        "invalid_action_count": sum(int(row["invalid_policy_actions"]) for row in results),
        "submitted_action_count": sum(int(row["submitted_policy_actions"]) for row in results),
        "success_rate": round(
            sum(row["winner"] == "agent_0" for row in results) / count,
            6,
        ),
        "scenarios": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
