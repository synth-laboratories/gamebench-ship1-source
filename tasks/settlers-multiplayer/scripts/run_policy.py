#!/usr/bin/env python3
"""Run four AlphaBeta-depth-2-spirit policies for a deterministic DEO score."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

TASK_DIR = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(TASK_DIR))
from gold_python.engine import AGENTS, SettlersEnv
from policies.alphabeta_depth2 import AlphaBetaDepth2Baseline

def play(seed: int, max_turns: int) -> dict:
    env = SettlersEnv(max_turns=max_turns); env.reset(seed); policies = {agent: AlphaBetaDepth2Baseline() for agent in AGENTS}
    while not env._require_state().terminated:
        env.step(policies[env.current_agent()].choose_action(env))
    state = env._require_state()
    return {"seed": seed, "winner": state.winner, "reason": state.termination_reason, "turns": state.turn, "vp": {agent: env.victory_points(agent) for agent in AGENTS}, "state_hash": env.state_hash()}

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--seed", type=int, default=11); parser.add_argument("--episodes", type=int, default=3); parser.add_argument("--max-turns", type=int, default=80); parser.add_argument("--output", type=Path)
    args = parser.parse_args(); results = [play(args.seed + index, args.max_turns) for index in range(args.episodes)]
    report = {"baseline": "alphabeta_depth2_spirit", "episodes": results, "win_rate_by_agent": {agent: sum(game["winner"] == agent for game in results) / len(results) for agent in AGENTS}, "mean_vp": {agent: sum(game["vp"][agent] for game in results) / len(results) for agent in AGENTS}}
    if args.output: args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))

if __name__ == "__main__": main()
