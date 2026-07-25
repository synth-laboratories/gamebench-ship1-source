#!/usr/bin/env python3
"""Run the bundled deterministic Fog Duel Lite baseline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_python.engine import FogDuelEnv

parser = argparse.ArgumentParser()
parser.add_argument("--scenario", default="fogwar_illegal_reliability_v0")
parser.add_argument("--steps", type=int, default=16)
parser.add_argument("--policy", default=str(ROOT / "policies" / "heuristic_baseline.py"))
args = parser.parse_args()

spec = importlib.util.spec_from_file_location("fogwar_policy", args.policy)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
env = FogDuelEnv()
observation = env.reset(args.scenario)
for _ in range(args.steps):
    result = env.step(module.act(observation))
    observation = result["observation"]
    if result["state"]["terminal"] is not None:
        break
print(json.dumps({"scenario": args.scenario, "steps": len(env.events), "terminal": env.state_projection()["terminal"], "illegal_actions": sum(event["kind"] == "illegal_action" for event in env.events)}, sort_keys=True))
