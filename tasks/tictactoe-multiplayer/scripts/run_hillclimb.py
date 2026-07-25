#!/usr/bin/env python3
"""Rank multiplayer Tic-Tac-Toe heuristic_policy candidates on fixed seeds."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable


TASK_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"
DEFAULT_BASELINE = TASK_DIR / "containers" / "codepolicy" / "heuristic_policy.py"

if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold.engine import AGENT_IDS, WAIT_ACTION, TicTacToeMultiplayerEngine, episode_id_for_task
from gold.monty import public_dict_from_engine
from policies.registry import choose_position

PolicyFn = Callable[[dict[str, Any], str, int, int], dict[str, Any]]


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_paths(candidate_root: Path) -> list[tuple[str, Path]]:
    if not candidate_root.exists():
        return []
    env_root = candidate_root / "tictactoe_mp"
    search_root = env_root if env_root.is_dir() else candidate_root
    return [(path.parent.name, path) for path in sorted(search_root.glob("*/heuristic_policy.py"))]


def load_policy(path: Path) -> PolicyFn:
    module_name = f"gb_ttt_mp_policy_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load policy module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "choose_action", None)
    if not callable(fn):
        raise AttributeError(f"{path} must define choose_action")

    def choose(public: dict[str, Any], agent_id: str, seed: int, ply: int) -> dict[str, Any]:
        try:
            action = fn(public, agent_id, seed, ply)
        except TypeError:
            action = fn(public, seed, ply)
        if not isinstance(action, dict):
            raise TypeError("choose_action must return a dict")
        return dict(action)

    return choose


def _registry_joint_action(public: dict[str, Any], agent_id: str, policy_id: str, seed: int, ply: int) -> dict[str, Any]:
    position = choose_position(
        policy_id,
        {
            "board": list(public["board"]),
            "turn": public["turn"],
            "winner": public.get("winner"),
        },
        seed=seed,
        ply=ply,
    )
    return {"agent_id": agent_id, "kind": "place", "position": position}


def _normalize_place(action: dict[str, Any], agent_id: str) -> dict[str, Any]:
    if "position" not in action:
        raise ValueError("policy action must include position")
    return {"kind": "place", "position": int(action["position"])}


def _joint_for(agent_id: str, action: dict[str, Any]) -> dict[str, Any]:
    joint = {agent: dict(WAIT_ACTION) for agent in AGENT_IDS}
    joint[agent_id] = _normalize_place(action, agent_id)
    return joint


def rollout_candidate(
    *,
    candidate_fn: PolicyFn,
    seed: int,
    opponent_policy_id: str,
    max_plies: int,
) -> dict[str, Any]:
    scenario_id = f"ttt_mp_policy_dev_{seed}"
    engine = TicTacToeMultiplayerEngine()
    engine.reset(
        scenario_id=scenario_id,
        seed=seed,
        episode_id=episode_id_for_task(scenario_id, seed, scenario_id),
        task_id=scenario_id,
    )
    plies = 0
    failures: list[str] = []
    while not engine.private.terminated and not engine.private.truncated and plies < max_plies:
        current = engine.public.current_agent
        public = public_dict_from_engine(engine.public)
        try:
            if current == AGENT_IDS[0]:
                action = candidate_fn(public, current, seed, plies)
            else:
                action = _registry_joint_action(public, current, opponent_policy_id, seed, plies)
            engine.step(_joint_for(current, action))
        except Exception as exc:
            failures.append(f"{current}: {type(exc).__name__}: {exc}")
            engine.step(_joint_for(current, {"position": _fallback_position(public)}))
        plies += 1

    winner = engine.public.winner
    if winner == AGENT_IDS[0]:
        outcome = "win"
        reward = 1.0
    elif winner == "draw":
        outcome = "draw"
        reward = 0.5
    elif winner == AGENT_IDS[1]:
        outcome = "loss"
        reward = 0.0
    else:
        outcome = "unfinished"
        reward = 0.0
    return {
        "seed": seed,
        "scenario_id": scenario_id,
        "outcome": outcome,
        "winner": winner,
        "reward": reward,
        "plies": plies,
        "failures": failures,
    }


def _fallback_position(public: dict[str, Any]) -> int:
    for index, value in enumerate(public["board"]):
        if not value:
            return index
    return 0


def run_policy(policy_path: Path, suite: dict[str, Any]) -> dict[str, Any]:
    candidate_fn = load_policy(policy_path)
    seeds = [int(seed) for seed in suite["seeds"]]
    results = [
        rollout_candidate(
            candidate_fn=candidate_fn,
            seed=seed,
            opponent_policy_id=str(suite.get("opponent_policy_id", "block_win_center_v1")),
            max_plies=int(suite.get("max_plies", 9)),
        )
        for seed in seeds
    ]
    wins = sum(1 for row in results if row["outcome"] == "win")
    draws = sum(1 for row in results if row["outcome"] == "draw")
    losses = sum(1 for row in results if row["outcome"] == "loss")
    unfinished = sum(1 for row in results if row["outcome"] == "unfinished")
    n = len(results)
    mean_reward = sum(float(row["reward"]) for row in results) / n if n else 0.0
    return {
        "score": round(mean_reward, 4),
        "win_rate": round(wins / n, 4) if n else 0.0,
        "mean_outcome_reward": round(mean_reward, 4),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "unfinished": unfinished,
        "n_seeds": n,
        "results": results,
        "opponent_policy_id": str(suite.get("opponent_policy_id", "block_win_center_v1")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tic-Tac-Toe multiplayer policy hillclimb leaderboard.")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE))
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--candidate-root", default=str(TASK_DIR / "candidates"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite = load_suite(Path(args.suite).expanduser().resolve())
    baseline_path = Path(args.baseline).expanduser().resolve()
    policies: list[tuple[str, Path]] = [("baseline", baseline_path)]
    policies.extend(candidate_paths(Path(args.candidate_root).expanduser().resolve()))
    if not policies:
        raise SystemExit("no policies found")

    rankings: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    for candidate_id, policy_path in policies:
        report = run_policy(policy_path, suite)
        reports[candidate_id] = report
        rankings.append(
            {
                "candidate_id": candidate_id,
                "policy_path": str(policy_path),
                "score": report["score"],
                "win_rate": report["win_rate"],
                "mean_outcome_reward": report["mean_outcome_reward"],
                "wins": report["wins"],
                "draws": report["draws"],
                "losses": report["losses"],
                "unfinished": report["unfinished"],
            }
        )
        candidate_dir = output / "candidates" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "summary.json").write_text(
            json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (candidate_dir / "results.json").write_text(
            json.dumps(report["results"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    baseline_score = float(reports["baseline"]["score"])
    rankings.sort(
        key=lambda item: (float(item["score"]), float(item["win_rate"]), int(item["wins"])),
        reverse=True,
    )
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "tictactoe-multiplayer",
        "suite_id": str(suite["suite_id"]),
        "baseline_score": baseline_score,
        "best_score": float(best["score"]),
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "opponent_policy_id": str(suite.get("opponent_policy_id", "block_win_center_v1")),
        "rankings": [
            {
                **item,
                "delta_vs_baseline": float(item["score"]) - baseline_score,
                "status": "accepted" if item["candidate_id"] == best["candidate_id"] else "rejected",
                "accepted": item["candidate_id"] == best["candidate_id"],
            }
            for item in rankings
        ],
    }
    (output / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(leaderboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
