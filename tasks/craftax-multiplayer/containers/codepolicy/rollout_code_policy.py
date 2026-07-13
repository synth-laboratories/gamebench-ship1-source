"""In-process joint code-policy rollouts for Craftax-Coop."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TASK_ROOT))
from gold_python.engine import CraftaxCoopEnv


def load_policy(path: Path):
    spec = importlib.util.spec_from_file_location("craftax_coop_candidate", path.resolve())
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, "act", None)
    if not callable(function):
        raise ValueError("policy must export act(observation)")
    return function


def rollout(policy_path: Path, seed: int, max_steps: int) -> dict[str, Any]:
    policy = load_policy(policy_path)
    env = CraftaxCoopEnv()
    observations, _ = env.reset(seed)
    shared_reward = 0.0
    trace = []
    for ply in range(max_steps):
        joint_action = {agent: policy(observations[agent]) for agent in env.agent_ids}
        observations, rewards, dones, info = env.step(joint_action)
        shared_reward += rewards[env.agent_ids[0]]
        trace.append({"ply": ply, "joint_action": joint_action, "reward": rewards[env.agent_ids[0]], "events": info["events"]})
        if dones["__all__"]:
            break
    state = env._require_state()
    return {
        "schema_version": "gamebench.rollout.v1",
        "env_family": env.env_family,
        "lane": "python",
        "policy_kind": "code",
        "policy_path": str(policy_path.resolve()),
        "seed": seed,
        "steps": state.timestep,
        "shared_reward": shared_reward,
        "achievements": sorted(name for name, value in state.achievements.items() if value),
        "trades": state.trade_count,
        "termination_reason": state.termination_reason,
        "state_hash": env.state_hash(),
        "trace": trace,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = rollout(args.policy, args.seed, args.steps)
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
