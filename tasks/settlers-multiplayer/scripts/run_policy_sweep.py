#!/usr/bin/env python3
"""Evaluate one Settlers code policy against fixed AlphaBeta-spirit opponents."""

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

from gold_python.engine import AGENTS, DICE, SettlersEnv
from policies.alphabeta_depth2 import AlphaBetaDepth2Baseline

PolicyFn = Callable[[dict[str, Any]], dict[str, Any]]


def load_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    required = ("suite_id", "seeds", "max_turns", "candidate_agent", "opponent_policy")
    missing = [key for key in required if key not in suite]
    if missing:
        raise ValueError(f"{path}: missing suite fields: {', '.join(missing)}")
    if tuple(suite.get("agents", [])) != AGENTS:
        raise ValueError(f"{path}: Settlers DEO requires fixed agents {list(AGENTS)}")
    if suite.get("turn_model") != "alternating":
        raise ValueError(f"{path}: Settlers DEO requires alternating turns")
    if suite["candidate_agent"] != AGENTS[0]:
        raise ValueError(f"{path}: only agent_0 is the evaluated policy slot")
    if suite["opponent_policy"] != "alphabeta_depth2_spirit":
        raise ValueError(f"{path}: only the owned AlphaBeta-depth-2-spirit opponent is supported")
    return suite


def load_policy(path: Path) -> PolicyFn:
    module_name = f"gamebench_settlers_policy_{hashlib.sha256(str(path).encode()).hexdigest()[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load policy module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    act = getattr(module, "act", None)
    if not callable(act):
        raise AttributeError(f"{path} must export act(observation)")

    def invoke(observation: dict[str, Any]) -> dict[str, Any]:
        action = act(observation)
        if not isinstance(action, dict) or not isinstance(action.get("kind"), str):
            raise TypeError("act(observation) must return an action object with a string kind")
        return dict(action)

    return invoke


def _fallback_action(observation: dict[str, Any]) -> dict[str, Any]:
    if observation.get("rolled_die") == 7 or "move_robber" in set(observation.get("legal_actions", [])):
        return {"kind": "move_robber", "tile": (int(observation["robber_tile"]) + 1) % 12}
    return {"kind": "end_turn"}


def policy_observation(env: SettlersEnv, observation: dict[str, Any]) -> dict[str, Any]:
    """Expose the public dice phase before a policy commits to its action.

    The compact gold API rolls the deterministic die inside ``step``.  Board
    game players know that roll before choosing how to answer it, so DEO gives
    code policies the same derived public field.  A policy must return
    ``move_robber`` when ``rolled_die`` is seven; ignoring it is scored as an
    invalid action instead of being hidden by evaluator recovery.
    """

    state = env._require_state()
    return {
        **observation,
        "turn": state.turn,
        "rolled_die": DICE[(state.seed + state.turn) % len(DICE)],
    }


def _candidate_score(*, won: bool, victory_points: int, invalid_actions: int, decisions: int) -> tuple[float, dict[str, float]]:
    """Score a policy by win outcome, VP progress, and action reliability.

    The explicit components prevent a policy from gaining credit solely by
    ending a game safely: wins dominate, VP differentiates turn-limit games,
    and invalid actions lower the reliability term.
    """

    outcome = 1.0 if won else 0.0
    vp_progress = min(max(float(victory_points) / 10.0, 0.0), 1.0)
    reliability = max(0.0, 1.0 - (float(invalid_actions) / max(1, decisions)))
    components = {
        "win_outcome": outcome,
        "vp_progress": vp_progress,
        "action_reliability": reliability,
    }
    return round(0.60 * outcome + 0.35 * vp_progress + 0.05 * reliability, 6), components


def rollout_candidate(*, candidate_fn: PolicyFn, seed: int, max_turns: int, candidate_agent: str, include_trace: bool) -> dict[str, Any]:
    env = SettlersEnv(max_turns=max_turns)
    observations, _ = env.reset(seed)
    opponent = AlphaBetaDepth2Baseline()
    candidate_decisions = 0
    candidate_invalid_actions = 0
    opponent_invalid_actions = 0
    policy_failures: list[str] = []
    trace: list[dict[str, Any]] = []
    total_decisions = 0
    decision_cap = max_turns * 2

    while not env._require_state().terminated and total_decisions < decision_cap:
        actor = env.current_agent()
        observation = observations[actor]
        if actor == candidate_agent:
            candidate_decisions += 1
            try:
                action = candidate_fn(policy_observation(env, observation))
            except Exception as exc:  # A policy error receives a safe fallback but no silent credit.
                action = _fallback_action(observation)
                policy_failures.append(f"{type(exc).__name__}: {exc}")
        else:
            action = opponent.choose_action(env)

        nev_start = len(env._require_state().nev)
        observations, _, _, info = env.step(action)
        total_decisions += 1
        new_events = env._require_state().nev[nev_start:]
        candidate_illegals = sum(
            event.get("kind") == "illegal_action" and event.get("agent_id") == candidate_agent
            for event in new_events
        )
        candidate_invalid_actions += candidate_illegals
        opponent_invalid_actions += sum(
            event.get("kind") == "illegal_action" and event.get("agent_id") != candidate_agent
            for event in new_events
        )
        if include_trace:
            trace.append(
                {
                    "actor": actor,
                    "action": action,
                    "events": new_events,
                    "state_hash": info["state_hash"],
                }
            )

    state = env._require_state()
    if not state.terminated:
        # This is evaluator truncation, not an owned-engine terminal claim.
        termination_reason = "policy_decision_cap"
    else:
        termination_reason = state.termination_reason
    candidate_vp = env.victory_points(candidate_agent)
    opponent_vps = {agent: env.victory_points(agent) for agent in AGENTS if agent != candidate_agent}
    score, components = _candidate_score(
        won=state.winner == candidate_agent,
        victory_points=candidate_vp,
        invalid_actions=candidate_invalid_actions + len(policy_failures),
        decisions=candidate_decisions,
    )
    result = {
        "seed": seed,
        "winner": state.winner,
        "outcome": "win" if state.winner == candidate_agent else "loss" if state.winner else "turn_limit",
        "termination_reason": termination_reason,
        "turns": state.turn,
        "candidate_agent": candidate_agent,
        "candidate_vp": candidate_vp,
        "best_opponent_vp": max(opponent_vps.values()),
        "opponent_vp": opponent_vps,
        "candidate_decision_count": candidate_decisions,
        "candidate_invalid_action_count": candidate_invalid_actions,
        "opponent_invalid_action_count": opponent_invalid_actions,
        "policy_failure_count": len(policy_failures),
        "policy_failures": policy_failures,
        "score": score,
        "score_components": components,
        "state_hash": env.state_hash(),
    }
    if include_trace:
        result["trace"] = trace
    return result


def run_policy_sweep(*, policy_path: Path, suite_path: Path, output_path: Path, include_trace: bool = False) -> dict[str, Any]:
    suite = load_suite(suite_path)
    policy = load_policy(policy_path)
    episodes = [
        rollout_candidate(
            candidate_fn=policy,
            seed=int(seed),
            max_turns=int(suite["max_turns"]),
            candidate_agent=str(suite["candidate_agent"]),
            include_trace=include_trace,
        )
        for seed in suite["seeds"]
    ]
    n_episodes = len(episodes)
    report = {
        "schema": "gamebench.settlers.policy_sweep.v1",
        "env_family": "settlers-multiplayer",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "candidate_agent": suite["candidate_agent"],
        "opponent_policy": suite["opponent_policy"],
        "turn_model": suite["turn_model"],
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "score_metric": "0.60_win_outcome + 0.35_vp_progress + 0.05_action_reliability",
        "score": round(sum(float(row["score"]) for row in episodes) / n_episodes, 6),
        "win_rate": round(sum(row["outcome"] == "win" for row in episodes) / n_episodes, 6),
        "mean_candidate_vp": round(sum(int(row["candidate_vp"]) for row in episodes) / n_episodes, 6),
        "mean_best_opponent_vp": round(sum(int(row["best_opponent_vp"]) for row in episodes) / n_episodes, 6),
        "invalid_action_count": sum(int(row["candidate_invalid_action_count"]) for row in episodes),
        "policy_failure_count": sum(int(row["policy_failure_count"]) for row in episodes),
        "episodes": episodes,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Settlers code policy against AlphaBeta-depth-2-spirit opponents.")
    parser.add_argument("--policy", required=True)
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
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("suite_id", "score", "win_rate", "mean_candidate_vp", "invalid_action_count")
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
