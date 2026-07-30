"""Minimal Rogue ReAct/code-agent rollout policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gold_python.agent_io import format_agent_observation, parse_action_text
from gold_python.engine import RogueEngine
from policies.registry import choose_action
from task_resolve import resolve_task


@dataclass
class EnvRolloutConfig:
    seed: int
    task_path: str = "tasks/policy_dev_template.json"
    max_steps: int = 40


@dataclass
class RolloutPolicy:
    policy_id: str = "stairs_v1"

    @classmethod
    def from_policy_config(cls, policy_config: dict[str, Any]) -> "RolloutPolicy":
        return cls(policy_id=str(policy_config.get("policy_id", "stairs_v1")))

    async def run(self, env: Any, rollout_config: EnvRolloutConfig, trace_correlation_id: str, trial_id: str | None = None) -> dict[str, Any]:
        import json
        from pathlib import Path

        task_root = Path(__file__).resolve().parents[2]
        task = json.loads((task_root / rollout_config.task_path).read_text())
        task["seed"] = rollout_config.seed
        task["task_id"] = f"{task.get('task_id', 'rogue_policy_dev')}_{rollout_config.seed}"
        engine = RogueEngine()
        engine.reset(resolve_task(task, seed_override=rollout_config.seed))
        turns = []
        ply = 0
        invalid_actions = 0
        while not engine.private.terminated and not engine.private.truncated and ply < rollout_config.max_steps:
            observation = format_agent_observation(engine.symbolic_readout())
            raw_action = choose_action(self.policy_id, observation, seed=rollout_config.seed, ply=ply)
            parsed = parse_action_text(raw_action, engine.valid_actions())
            if parsed.invalid_parse:
                invalid_actions += 1
            engine.step(parsed.action)
            turns.append({"ply": ply, "action": parsed.to_dict(), "reward_total": engine.private.total_reward, "scout_score": engine.private.scout_score, "scout_last": engine.private.scout_last, "synth_shaped_reward": engine.private.synth_shaped_reward, "synth_shaped_reward_last": engine.private.synth_shaped_reward_last})
            ply += 1
        outcome = "success" if engine.private.total_reward >= 1.0 else "truncated" if engine.private.truncated else "failure"
        progress_metrics = engine.symbolic_readout()["progress_metrics"]
        return {"trace_correlation_id": trace_correlation_id, "rollout_id": engine.private.episode_id, "trial_id": trial_id or f"rogue-agent-{rollout_config.seed}", "success_status": "success", "status_detail": outcome, "reward_info": {"outcome_reward": float(engine.private.total_reward), "details": {"seed": rollout_config.seed, "task_id": engine.resolved.task_id if engine.resolved else "unknown", "outcome": outcome, "steps": engine.private.step_index, "invalid_action_count": invalid_actions, "policy_id": self.policy_id, **progress_metrics}}, "events": engine.nev.legacy_strings(), "nev": engine.nev.export(), "state": {"public": engine.public.to_dict(), "private": engine.private.to_dict()}, "progress_metrics": progress_metrics, "artifact": [{"artifact_type": "turns", "turns": turns}]}
