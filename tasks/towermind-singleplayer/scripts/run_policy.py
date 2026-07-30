#!/usr/bin/env python3
"""Run a local policy against the independent Python TowerMind gold lane."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_python.engine import TowerMindEnv


def load_policy(path: Path):
    spec = importlib.util.spec_from_file_location("towermind_policy", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load policy {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=str(ROOT / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--level", default="L1")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--steps", type=int, default=40)
    args = parser.parse_args()
    policy = load_policy(Path(args.policy))
    env = TowerMindEnv()
    observation = env.reset(args.level, seed=args.seed)
    actions: list[dict[str, object]] = []
    for _ in range(args.steps):
        action = policy.act(observation)
        actions.append(action)
        result = env.step(action)
        observation = result["observation"]
        if result["terminated"]:
            break
    state = env.state or {}
    print(json.dumps({"level": args.level, "seed": args.seed, "steps": state.get("tick"), "reward": state.get("total_reward"), "termination_reason": state.get("termination_reason"), "illegal_actions": state.get("illegal_actions"), "actions": actions}, sort_keys=True))


if __name__ == "__main__":
    main()
