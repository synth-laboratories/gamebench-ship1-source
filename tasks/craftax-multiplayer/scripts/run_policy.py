#!/usr/bin/env python3
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_python.engine import CraftaxCoopEnv

parser = argparse.ArgumentParser()
parser.add_argument("--policy", default=str(ROOT / "policies/heuristic_baseline.py"))
parser.add_argument("--seed", type=int, default=101)
parser.add_argument("--steps", type=int, default=100)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location("candidate_policy", args.policy); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
env = CraftaxCoopEnv(); observations, _ = env.reset(args.seed); total = 0.0
for _ in range(args.steps):
    joint = {agent: module.act(observations[agent]) for agent in env.agent_ids}
    observations, rewards, dones, _ = env.step(joint); total += rewards[env.agent_ids[0]]
    if dones["__all__"]: break
state = env._require_state()
print(json.dumps({"seed":args.seed,"steps":state.timestep,"shared_reward":total,"achievements":[k for k,v in state.achievements.items() if v],"trades":state.trade_count,"termination_reason":state.termination_reason,"state_hash":env.state_hash()}, sort_keys=True))
