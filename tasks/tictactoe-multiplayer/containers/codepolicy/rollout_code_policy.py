"""Deterministic code-policy rollouts for multiplayer Tic-Tac-Toe."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

TASK_ROOT = Path(__file__).resolve().parents[2]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))
if str(TASK_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(TASK_ROOT / "scripts"))

from gold.board import AGENT_IDS
from gold.engine import TicTacToeMultiplayerEngine, episode_id_for_task
from gold.monty import public_dict_from_engine
from run_hillclimb import (
    PolicyFn,
    _fallback_position,
    _joint_for,
    _registry_joint_action,
    load_policy as load_hillclimb_policy,
)

DEFAULT_OPPONENT_POLICY_ID = "block_win_center_v1"
_POLICY_CACHE: dict[tuple[str, str], PolicyFn] = {}


def task_root() -> Path:
    return TASK_ROOT


def load_policy_module(policy_path: Path, *, entry: str = "choose_action") -> PolicyFn:
    resolved = policy_path.expanduser().resolve()
    cache_key = (str(resolved), entry)
    if cache_key in _POLICY_CACHE:
        return _POLICY_CACHE[cache_key]
    return load_hillclimb_policy(resolved)


def compile_check_policy(policy_path: Path, *, entry: str = "choose_action") -> dict[str, Any]:
    fn = load_policy_module(policy_path, entry=entry)
    sample_public = {
        "board": ["", "", "", "", "", "", "", "", ""],
        "turn": "X",
        "winner": None,
    }
    action = fn(sample_public, AGENT_IDS[0], seed=101, ply=0)
    if not isinstance(action, dict):
        raise ValueError("choose_action must return a dict action")
    if "position" not in action:
        raise ValueError("choose_action must return {position}")
    return {
        "policy_path": str(policy_path.expanduser().resolve()),
        "entry": entry,
        "sample_action": dict(action),
    }


def rollout_code_policy(
    *,
    policy_path: Path,
    seed: int,
    opponent_policy_id: str = DEFAULT_OPPONENT_POLICY_ID,
    max_plies: int = 9,
    include_trace: bool = False,
    candidate_fn: PolicyFn | None = None,
    policy_entry: str = "choose_action",
) -> dict[str, Any]:
    resolved_path = policy_path.expanduser().resolve()
    candidate = candidate_fn or load_policy_module(resolved_path, entry=policy_entry)
    scenario_id = f"ttt_mp_codepolicy_{seed}"
    engine = TicTacToeMultiplayerEngine()
    engine.reset(
        scenario_id=scenario_id,
        seed=seed,
        episode_id=episode_id_for_task(scenario_id, seed, scenario_id),
        task_id=scenario_id,
    )
    plies = 0
    failures: list[str] = []
    candidate_moves: list[int] = []
    while not engine.private.terminated and not engine.private.truncated and plies < max_plies:
        current = engine.public.current_agent
        public = public_dict_from_engine(engine.public)
        try:
            if current == AGENT_IDS[0]:
                action = candidate(public, current, seed, plies)
                candidate_moves.append(int(action["position"]))
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

    mark = "X"
    events = [f"MoveApplied({mark},{position})" for position in candidate_moves]
    result: dict[str, Any] = {
        "trace_correlation_id": f"codepolicy-{scenario_id}-{seed}",
        "rollout_id": engine.private.episode_id,
        "success_status": "success",
        "status_detail": outcome,
        "reward_info": {
            "outcome_reward": reward,
            "details": {
                "seed": seed,
                "scenario_id": scenario_id,
                "candidate_agent": AGENT_IDS[0],
                "candidate_mark": mark,
                "opponent_policy_id": opponent_policy_id,
                "policy_path": str(resolved_path),
                "winner": winner,
                "outcome": outcome,
                "plies": plies,
                "failures": failures,
                "candidate_moves": candidate_moves,
            },
        },
        "state": {
            "public": engine.public.to_dict(),
            "private": engine.private.to_dict(),
        },
        "events": events,
    }
    if include_trace:
        result["nev"] = engine.nev.export()
    return result
