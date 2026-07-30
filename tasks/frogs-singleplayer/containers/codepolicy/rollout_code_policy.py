"""Run FrogsGame code policies in-process against the gold Python engine."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

TASK_ROOT = Path(__file__).resolve().parents[2]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))
for extra in (TASK_ROOT / "gold_python", TASK_ROOT / "shared", TASK_ROOT / "policies"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from gold_python.agent_io import format_agent_observation, parse_action_text
from gold_python.engine import FrogsEngine
from task_resolve import resolve_task


PolicyFn = Callable[..., dict[str, Any]]
_POLICY_CACHE: dict[tuple[str, str], PolicyFn] = {}


def task_root() -> Path:
    return TASK_ROOT


def load_policy_module(policy_path: Path, *, entry: str = "choose_actions") -> PolicyFn:
    resolved = policy_path.expanduser().resolve()
    cache_key = (str(resolved), entry)
    if cache_key in _POLICY_CACHE:
        return _POLICY_CACHE[cache_key]
    if not resolved.is_file():
        raise ValueError(f"policy file not found: {resolved}")
    module_name = f"frogs_codepolicy_{resolved.stem}_{abs(hash(resolved)) % 10_000_000}"
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


def compile_check_policy(policy_path: Path, *, entry: str = "choose_actions") -> dict[str, Any]:
    fn = load_policy_module(policy_path, entry=entry)
    task = _load_task("tasks/policy_dev_template.json", seed=1)
    engine = FrogsEngine()
    engine.reset(resolve_task(task))
    readout = engine.symbolic_readout()
    result = fn(
        observation_text=format_agent_observation(readout)["observation_text"],
        session={"rollout_id": engine.private.episode_id, "ply": 0},
        valid_actions=engine.valid_actions(),
        engine=engine.clone_for_sim(),
        seed=1,
        ply=0,
        readout=readout,
    )
    if not isinstance(result, dict) or not isinstance(result.get("actions"), list):
        raise ValueError("choose_actions must return {'actions': [...]}")
    parsed = parse_action_text(result["actions"][0], engine.valid_actions())
    return {"policy_path": str(policy_path.expanduser().resolve()), "entry": entry, "sample_action": parsed.action}


def rollout_code_policy(
    *,
    policy_path: Path,
    seed: int,
    task_path: str = "tasks/policy_dev_template.json",
    max_steps: int = 16,
    policy_entry: str = "choose_actions",
    include_trace: bool = True,
    candidate_fn: PolicyFn | None = None,
) -> dict[str, Any]:
    task = _load_task(task_path, seed=seed)
    engine = FrogsEngine()
    engine.reset(resolve_task(task, seed_override=seed))
    candidate = candidate_fn or load_policy_module(policy_path, entry=policy_entry)
    turns: list[dict[str, Any]] = []
    invalid_actions = 0
    ply = 0
    while not engine.private.terminated and not engine.private.truncated and ply < max_steps:
        readout = engine.symbolic_readout()
        decision = candidate(
            observation_text=format_agent_observation(readout)["observation_text"],
            session={"rollout_id": engine.private.episode_id, "ply": ply},
            valid_actions=engine.valid_actions(),
            engine=engine.clone_for_sim(),
            seed=seed,
            ply=ply,
            readout=readout,
        )
        raw_action = (decision.get("actions") or [""])[0]
        parsed = parse_action_text(raw_action, engine.valid_actions())
        if parsed.invalid_parse:
            invalid_actions += 1
        engine.step(parsed.action)
        turns.append(
            {
                "ply": ply,
                "action": parsed.to_dict(),
                "policy_reason": decision.get("policy_reason", ""),
                "reward_total": engine.private.total_reward,
                "grid_hash": engine.symbolic_readout()["grid_hash"],
            }
        )
        ply += 1
    outcome = "success" if engine.private.total_reward >= 1.0 else "truncated" if engine.private.truncated else "failure"
    result: dict[str, Any] = {
        "trace_correlation_id": f"frogs-codepolicy-{seed}",
        "rollout_id": engine.private.episode_id,
        "success_status": "success",
        "status_detail": outcome,
        "reward_info": {
            "outcome_reward": float(engine.private.total_reward),
            "details": {
                "seed": seed,
                "task_id": engine.resolved.task_id if engine.resolved else "unknown",
                "outcome": outcome,
                "steps": engine.private.step_index,
                "invalid_action_count": invalid_actions,
                "policy_path": str(policy_path.expanduser().resolve()),
            },
        },
        "state": {"public": engine.public.to_dict(), "private": engine.private.to_dict()},
        "artifact": [{"artifact_type": "turns", "turns": turns}],
    }
    if include_trace:
        result["events"] = engine.nev.legacy_strings()
        result["nev"] = engine.nev.export()
    return result


def _load_task(task_path: str, *, seed: int) -> dict[str, Any]:
    task = json.loads((TASK_ROOT / task_path).read_text())
    task["seed"] = seed
    task["task_id"] = f"{task.get('task_id', 'frogs_policy_dev')}_{seed}"
    return task
