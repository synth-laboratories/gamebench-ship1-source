#!/usr/bin/env python3
"""Score a Hanabi code policy with a fixed cooperative partner."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import HanabiEnv
from policies.heuristic_baseline import act as partner_act

PolicyFn = Callable[[dict[str, Any]], dict[str, Any]]


def load_policy(path: Path) -> PolicyFn:
    name = f"gamebench_hanabi_policy_{hashlib.sha256(str(path).encode()).hexdigest()[:16]}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy = getattr(module, "act", None)
    if not callable(policy):
        raise AttributeError(f"{path} must define act(observation)")
    return policy


def safe_action(policy: PolicyFn, observation: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    try:
        action = policy(observation)
    except Exception as exc:
        return {"kind": "policy_exception"}, f"{type(exc).__name__}: {exc}"
    if not isinstance(action, dict):
        return {"kind": "policy_invalid_return"}, "policy returned a non-object action"
    return action, None


def rollout(policy: PolicyFn, seed: int, max_turns: int) -> dict[str, Any]:
    env = HanabiEnv()
    observation = env.reset(seed)
    failures: list[str] = []
    illegal_actions = 0
    turns = 0
    while env.state_projection()["terminal"] is None and turns < max_turns:
        actor = observation["active_agent"]
        action, failure = safe_action(policy if actor == "agent_0" else partner_act, observation)
        if failure is not None and actor == "agent_0":
            failures.append(failure)
        start = len(env.events)
        result = env.step(action)
        if actor == "agent_0":
            illegal_actions += sum(event["kind"] == "illegal_action" for event in env.events[start:])
        observation = result["observation"]
        turns += 1
    terminal = env.state_projection()["terminal"]
    if terminal is None:
        raise RuntimeError(f"seed {seed} did not terminate within {max_turns} turns")
    return {"seed": seed, "score": terminal["score"], "reason": terminal["reason"], "turns": turns, "candidate_illegal_actions": illegal_actions, "candidate_policy_failures": failures}


def run(policy_path: Path, suite_path: Path, output_path: Path) -> dict[str, Any]:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    if suite.get("schema") != "gamebench.hanabi.policy_sweep.v1":
        raise ValueError(f"unsupported Hanabi policy suite: {suite_path}")
    policy = load_policy(policy_path)
    rows = [rollout(policy, int(seed), int(suite["max_turns"])) for seed in suite["seeds"]]
    report = {
        "schema": "gamebench.hanabi.policy_report.v1",
        "suite_id": suite["suite_id"],
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "score": round(sum(row["score"] for row in rows) / len(rows), 6),
        "perfect_game_rate": round(sum(row["score"] == 25 for row in rows) / len(rows), 6),
        "invalid_action_count": sum(row["candidate_illegal_actions"] for row in rows),
        "games": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--suite", type=Path, default=TASK_DIR / "defaults/policy_sweep/policy_dev_v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.policy, args.suite, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
