"""Run Overcooked v2 code policies in-process against the gold Python engine."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

TASK_ROOT = Path(__file__).resolve().parents[2]
# Force task gold_python ahead of any inherited PYTHONPATH / shadowed `core`.
_task_paths = (TASK_ROOT, TASK_ROOT / "gold_python", TASK_ROOT / "shared", TASK_ROOT / "policies")
for extra in reversed(_task_paths):
    text = str(extra)
    while text in sys.path:
        sys.path.remove(text)
    sys.path.insert(0, text)

from agent_io import format_joint_observation, normalize_joint_action
from engine import OvercookedV2Engine
from scenarios import scenario_to_task
from task_resolve import resolve_task

PolicyFn = Callable[..., dict[str, Any]]
_POLICY_CACHE: dict[tuple[str, str], PolicyFn] = {}


def load_policy_module(policy_path: Path, *, entry: str = "choose_joint_actions") -> PolicyFn:
    resolved = policy_path.expanduser().resolve()
    cache_key = (str(resolved), entry)
    if cache_key in _POLICY_CACHE:
        return _POLICY_CACHE[cache_key]
    if not resolved.is_file():
        raise ValueError(f"policy file not found: {resolved}")
    module_name = f"overcooked_codepolicy_{resolved.stem}_{abs(hash(resolved)) % 10_000_000}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy module: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fn = getattr(module, entry, None)
    if fn is None or not callable(fn):
        raise ValueError(f"policy module {resolved} missing callable {entry}")
    _POLICY_CACHE[cache_key] = fn
    return fn


def compile_check_policy(policy_path: Path, *, entry: str = "choose_joint_actions") -> dict[str, Any]:
    fn = load_policy_module(policy_path, entry=entry)
    task = scenario_to_task({"scenario_id": "compile_check", "layout_id": "demo_tiny", "seed": 1})
    engine = OvercookedV2Engine()
    engine.reset_from_task(task, seed_override=1)
    readout = engine.symbolic_readout()
    result = fn(
        observation_text=format_joint_observation(readout)["observation_text"],
        session={"rollout_id": engine.private.episode_id, "ply": 0},
        valid_actions=readout["joint_valid_actions"],
        engine=engine.clone_for_sim(),
        seed=1,
        ply=0,
        readout=readout,
    )
    joint = normalize_joint_action(result.get("joint_action") or {})
    return {"policy_path": str(policy_path.expanduser().resolve()), "entry": entry, "sample_action": joint}


def rollout_code_policy(
    *,
    policy_path: Path,
    scenario: dict[str, Any],
    max_steps: int,
    policy_entry: str = "choose_joint_actions",
    include_trace: bool = True,
    candidate_fn: PolicyFn | None = None,
) -> dict[str, Any]:
    task = scenario_to_task(scenario)
    seed = int(scenario.get("seed", 0))
    engine = OvercookedV2Engine()
    engine.reset_from_task(task, seed_override=seed)
    candidate = candidate_fn or load_policy_module(policy_path, entry=policy_entry)
    turns: list[dict[str, Any]] = []
    invalid_actions = 0
    ply = 0
    while not engine.private.terminated and not engine.private.truncated and ply < max_steps:
        readout = engine.symbolic_readout()
        decision = candidate(
            observation_text=format_joint_observation(readout)["observation_text"],
            session={"rollout_id": engine.private.episode_id, "ply": ply},
            valid_actions=readout["joint_valid_actions"],
            engine=engine.clone_for_sim(),
            seed=seed,
            ply=ply,
            readout=readout,
        )
        joint_action = normalize_joint_action(decision.get("joint_action") or {})
        engine.step(joint_action)
        turns.append(
            {
                "ply": ply,
                "joint_action": joint_action,
                "policy_reason": decision.get("policy_reason", ""),
                "reward_last": engine.private.reward_last,
                "reward_total": engine.private.total_reward,
                "deliveries": engine.deliveries,
            }
        )
        ply += 1
    outcome = "success" if engine.private.terminated else "truncated" if engine.private.truncated else "failure"
    result: dict[str, Any] = {
        "trace_correlation_id": f"overcooked-codepolicy-{scenario.get('scenario_id', 'manual')}-{seed}",
        "rollout_id": engine.private.episode_id,
        "success_status": "success" if outcome == "success" else "failure",
        "status_detail": outcome,
        "reward_info": {
            "outcome_reward": float(engine.private.total_reward),
            "details": {
                "seed": seed,
                "scenario_id": scenario.get("scenario_id", task.get("scenario_id")),
                "layout_id": scenario.get("layout_id", "demo_tiny"),
                "outcome": outcome,
                "deliveries": engine.deliveries,
                "invalid_action_count": invalid_actions,
            },
        },
    }
    if include_trace:
        result["turns"] = turns
    return result

