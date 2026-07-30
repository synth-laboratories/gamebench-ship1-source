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
parser.add_argument("--rules-profile", choices=("alem_coord_v0",))
parser.add_argument("--alem-scenario", choices=("sync_2", "sync_all", "handover"), default="sync_2")
parser.add_argument("--alem-alpha", type=float, choices=(0.3, 0.6, 0.9), default=0.3)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location("candidate_policy", args.policy); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
env = CraftaxCoopEnv(rules_profile=args.rules_profile, coordination={"scenario": args.alem_scenario, "alpha": args.alem_alpha} if args.rules_profile else None); observations, _ = env.reset(args.seed); total = 0.0
for _ in range(args.steps):
    joint = {agent: module.act(observations[agent]) for agent in env.agent_ids}
    observations, rewards, dones, _ = env.step(joint); total += rewards[env.agent_ids[0]]
    if dones["__all__"]: break
state = env._require_state()
print(json.dumps({"seed":args.seed,"steps":state.timestep,"shared_reward":total,"achievements":[k for k,v in state.achievements.items() if v],"trades":state.trade_count,"termination_reason":state.termination_reason,"state_hash":env.state_hash(),"alem_metrics":env.alem_metrics() if state.alem_coord else None}, sort_keys=True))
