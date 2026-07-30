"""Run Rogue code policies in-process."""

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
from gold_python.engine import RogueEngine
from task_resolve import resolve_task


PolicyFn = Callable[..., dict[str, Any]]


def task_root() -> Path:
    return TASK_ROOT


def load_policy_module(policy_path: Path, *, entry: str = "choose_actions") -> PolicyFn:
    resolved = policy_path.expanduser().resolve()
    spec = importlib.util.spec_from_file_location(f"rogue_codepolicy_{resolved.stem}", resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy module: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fn = getattr(module, entry, None)
    if fn is None or not callable(fn):
        raise ValueError(f"policy module {resolved} missing callable {entry}")
    return fn


def rollout_code_policy(
    *,
    policy_path: Path,
    seed: int,
    task_path: str = "tasks/policy_dev_template.json",
    task_payload: dict[str, Any] | None = None,
    max_steps: int = 40,
    include_trace: bool = True,
    candidate_fn: PolicyFn | None = None,
) -> dict[str, Any]:
    task = dict(task_payload) if task_payload is not None else json.loads((TASK_ROOT / task_path).read_text())
    task["seed"] = seed
    task["task_id"] = str(task.get("task_id", "rogue_policy_dev"))
    rules = dict(task.get("rules", {}))
    overrides = dict(rules.get("overrides", {}))
    overrides["max_steps"] = max_steps
    rules["overrides"] = overrides
    task["rules"] = rules
    engine = RogueEngine()
    engine.reset(resolve_task(task, seed_override=seed))
    candidate = candidate_fn or load_policy_module(policy_path)
    turns = []
    invalid_actions = 0
    ply = 0
    while not engine.private.terminated and not engine.private.truncated and ply < max_steps:
        readout = engine.symbolic_readout()
        observation = format_agent_observation(readout)
        decision = candidate(observation_text=observation["observation_text"], session={"rollout_id": engine.private.episode_id, "ply": ply}, valid_actions=engine.valid_actions(), engine=engine.clone_for_sim(), seed=seed, ply=ply, readout=readout)
        raw_action = str((decision.get("actions") or [""])[0])
        parsed = parse_action_text(raw_action, engine.valid_actions())
        if parsed.invalid_parse:
            invalid_actions += 1
        engine.step(parsed.action)
        readout_after = engine.symbolic_readout()
        turns.append({"ply": ply, "action": parsed.to_dict(), "policy_reason": decision.get("policy_reason", ""), "reward_total": engine.private.total_reward, "scout_score": engine.private.scout_score, "scout_last": engine.private.scout_last, "synth_shaped_reward": engine.private.synth_shaped_reward, "synth_shaped_reward_last": engine.private.synth_shaped_reward_last, "grid_hash": readout_after["grid_hash"]})
        ply += 1
    outcome = "success" if engine.private.total_reward >= 1.0 else "truncated" if engine.private.truncated else "failure"
    progress_metrics = engine.symbolic_readout()["progress_metrics"]
    result: dict[str, Any] = {
        "trace_correlation_id": f"rogue-codepolicy-{seed}",
        "rollout_id": engine.private.episode_id,
        "success_status": "success",
        "status_detail": outcome,
        "reward_info": {"outcome_reward": float(engine.private.total_reward), "details": {"seed": seed, "task_id": engine.resolved.task_id if engine.resolved else "unknown", "outcome": outcome, "steps": engine.private.step_index, "invalid_action_count": invalid_actions, "policy_path": str(policy_path.expanduser().resolve()), **progress_metrics}},
        "state": {"public": engine.public.to_dict(), "private": engine.private.to_dict()},
        "progress_metrics": progress_metrics,
        "artifact": [{"artifact_type": "turns", "turns": turns}],
    }
    if include_trace:
        result["events"] = engine.nev.legacy_strings()
        result["nev"] = engine.nev.export()
    return result


def compile_check_policy(policy_path: Path) -> dict[str, Any]:
    fn = load_policy_module(policy_path)
    result = rollout_code_policy(policy_path=policy_path, seed=1, max_steps=1, include_trace=False, candidate_fn=fn)
    return {"policy_path": str(policy_path.expanduser().resolve()), "sample_status": result["status_detail"]}
