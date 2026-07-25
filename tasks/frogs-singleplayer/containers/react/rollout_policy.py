"""FrogsGame ReAct/code-agent rollout policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from containers.react.agent_policy import AgentPolicy, AgentPolicyConfig
from containers.react.frogs_env import FrogsSingleplayerEnv, SeedSpec, spawn_env


@dataclass
class EnvRolloutConfig:
    seed: int
    task_path: str = "tasks/policy_dev_template.json"
    max_steps: int = 16
    task: dict[str, Any] | None = None

    @classmethod
    def from_request(cls, seed: int, env_config: dict[str, Any]) -> "EnvRolloutConfig":
        return cls(
            seed=seed,
            task_path=str(env_config.get("task_path", "tasks/policy_dev_template.json")),
            max_steps=max(int(env_config.get("max_steps", 16)), 1),
            task=env_config.get("task"),
        )

    def to_seed_spec(self) -> SeedSpec:
        return SeedSpec(seed=self.seed, task_path=self.task_path, task=self.task)


@dataclass
class RolloutPolicy:
    agent: AgentPolicy

    @classmethod
    def from_policy_config(cls, policy_config: dict[str, Any]) -> "RolloutPolicy":
        return cls(agent=AgentPolicy(AgentPolicyConfig.from_mapping(policy_config)))

    async def run(
        self,
        env: FrogsSingleplayerEnv | None,
        rollout_config: EnvRolloutConfig,
        trace_correlation_id: str,
        trial_id: str | None = None,
    ) -> dict[str, Any]:
        if env is None:
            env = spawn_env(rollout_config.to_seed_spec())

        turns: list[dict[str, Any]] = []
        action_history: list[dict[str, Any]] = []
        inference_errors = 0
        invalid_actions = 0
        ply = 0

        while not env.engine.private.terminated and not env.engine.private.truncated and ply < rollout_config.max_steps:
            observation = env.observation_llm_text()
            turn = await self.agent.choose(observation, action_history, rollout_config.seed, ply)
            step = env.step_text(turn.raw_action)
            if turn.invalid_parse or step.parsed_action.get("invalid_parse"):
                invalid_actions += 1
            if turn.error:
                inference_errors += 1
            action_history.append({"action": step.parsed_action.get("action"), "ply": ply})
            turns.append(
                {
                    "ply": ply,
                    "actor": AgentPolicy.ACTOR,
                    "action": step.parsed_action,
                    "assistant_text": turn.assistant_text,
                    "invalid_parse": turn.invalid_parse,
                    "repaired": turn.repaired,
                    "nev_message": step.nev_message,
                    "usage": turn.usage,
                    "request_id": turn.request_id,
                    "error": turn.error,
                    "model": turn.model,
                    "reward_total": env.engine.private.total_reward,
                    "grid_hash": step.observation.get("grid_hash"),
                }
            )
            ply += 1

        outcome = "success" if env.engine.private.total_reward >= 1.0 else "truncated" if env.engine.private.truncated else "failure"
        return {
            "trace_correlation_id": trace_correlation_id,
            "rollout_id": env.engine.private.episode_id,
            "trial_id": trial_id or f"frogs-agent-{rollout_config.seed}",
            "success_status": "success",
            "status_detail": outcome,
            "reward_info": {
                "outcome_reward": float(env.engine.private.total_reward),
                "details": {
                    "seed": rollout_config.seed,
                    "task_id": env.engine.resolved.task_id if env.engine.resolved else "unknown",
                    "outcome": outcome,
                    "steps": env.engine.private.step_index,
                    "invalid_action_count": invalid_actions,
                    "inference_error_count": inference_errors,
                    "policy_id": self.agent.config.policy_id,
                    "model": self.agent.config.model if self.agent.config.use_lm else self.agent.config.policy_id,
                },
            },
            "events": env.legacy_events(),
            "nev": env.nev_export(),
            "state": env.terminal_snapshot(),
            "artifact": [{"artifact_type": "turns", "turns": turns}, {"artifact_type": "render", **env.render_payload()}],
        }
