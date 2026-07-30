"""Rollout policy: Groq agent_0 (70b) vs Groq agent_1 (8b) on multiplayer gold env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from gold.board import AGENT_IDS, AGENT_MARKS

from container.groq_agent_policy import GroqAgentPolicy, GroqPolicyConfig
from container.mp_env import SeedSpec, spawn_env, TictactoeMultiplayerEnv

DEFAULT_AGENT_0_MODEL = "llama-3.3-70b-versatile"
DEFAULT_AGENT_1_MODEL = "llama-3.1-8b-instant"


@dataclass
class EnvRolloutConfig:
    seed: int
    scenario_id: str
    max_plies: int = 9

    @classmethod
    def from_request(cls, seed: int, env_config: dict[str, Any]) -> EnvRolloutConfig:
        spec = SeedSpec(
            seed=seed,
            scenario_id=env_config.get("scenario_id"),
        )
        max_plies = max(int(env_config.get("max_plies", 9)), 1)
        return cls(
            seed=spec.seed,
            scenario_id=spec.resolved_scenario_id(),
            max_plies=max_plies,
        )

    def to_seed_spec(self) -> SeedSpec:
        return SeedSpec(
            seed=self.seed,
            scenario_id=self.scenario_id,
            task_id=self.scenario_id,
        )


@dataclass
class MultiplayerGroqRolloutPolicy:
    agents: dict[str, GroqAgentPolicy]

    @classmethod
    def from_policy_config(cls, policy_config: dict[str, Any]) -> MultiplayerGroqRolloutPolicy:
        raw = dict(policy_config)
        agent_0_raw = dict(raw.get("agent_0", raw.get("agent_0_policy", {})))
        agent_1_raw = dict(raw.get("agent_1", raw.get("agent_1_policy", {})))
        if "model" in raw and "agent_0" not in raw:
            agent_0_raw.setdefault("model", raw["model"])

        api_key = (
            str(raw.get("api_key", "")).strip()
            or os.environ.get("GROQ_API_KEY", "").strip()
        )
        if api_key:
            agent_0_raw.setdefault("api_key", api_key)
            agent_1_raw.setdefault("api_key", api_key)

        agent_0_model = str(
            agent_0_raw.get("model", os.environ.get("GROQ_AGENT_0_MODEL", DEFAULT_AGENT_0_MODEL))
        )
        agent_1_model = str(
            agent_1_raw.get("model", os.environ.get("GROQ_AGENT_1_MODEL", DEFAULT_AGENT_1_MODEL))
        )
        agent_0_raw.setdefault("model", agent_0_model)
        agent_1_raw.setdefault("model", agent_1_model)
        agent_0_raw.setdefault("actor", f"groq_{AGENT_IDS[0]}")
        agent_1_raw.setdefault("actor", f"groq_{AGENT_IDS[1]}")

        cfg_0 = GroqPolicyConfig.from_mapping(agent_0_raw, default_model=agent_0_model)
        cfg_1 = GroqPolicyConfig.from_mapping(agent_1_raw, default_model=agent_1_model)
        if not cfg_0.api_key:
            raise ValueError("missing GROQ_API_KEY (or policy api_key)")

        return cls(
            agents={
                AGENT_IDS[0]: GroqAgentPolicy(cfg_0, AGENT_IDS[0]),
                AGENT_IDS[1]: GroqAgentPolicy(cfg_1, AGENT_IDS[1]),
            }
        )

    async def run(
        self,
        env: TictactoeMultiplayerEnv | None,
        rollout_config: EnvRolloutConfig,
        trace_correlation_id: str,
        trial_id: str | None = None,
    ) -> dict[str, Any]:
        if env is None:
            env = spawn_env(rollout_config.to_seed_spec())

        turns: list[dict[str, Any]] = []
        action_history: list[dict[str, Any]] = []
        inference_errors = 0
        plies = 0

        while not env.engine.private.terminated and plies < rollout_config.max_plies:
            current_agent = env.engine.public.current_agent
            mark = AGENT_MARKS[current_agent]
            obs = env.observations_llm_text()[current_agent]
            policy = self.agents[current_agent]

            turn_result = await policy.choose(obs, mark, action_history)
            joint_action = env.joint_place(current_agent, turn_result.position)
            step = env.step_joint(joint_action)
            action_history.append(
                {
                    "agent_id": current_agent,
                    "mark": mark,
                    "position": turn_result.position,
                }
            )
            if turn_result.error:
                inference_errors += 1

            turns.append(
                {
                    "ply": plies,
                    "actor": policy.actor,
                    "agent_id": current_agent,
                    "mark": mark,
                    "position": turn_result.position,
                    "joint_action": joint_action,
                    "assistant_text": turn_result.assistant_text,
                    "invalid_parse": turn_result.invalid_parse,
                    "nev_message": step.nev_message,
                    "usage": turn_result.usage,
                    "request_id": turn_result.request_id,
                    "error": turn_result.error,
                    "model": policy.config.model,
                }
            )
            plies += 1

        winner = env.engine.public.winner
        agent_0_model = self.agents[AGENT_IDS[0]].config.model
        agent_1_model = self.agents[AGENT_IDS[1]].config.model

        return {
            "trace_correlation_id": trace_correlation_id,
            "rollout_id": env.engine.private.episode_id,
            "trial_id": trial_id or f"ttt-mp-{rollout_config.seed}",
            "success_status": "success",
            "status_detail": str(winner),
            "reward_info": {
                "outcome_reward": float(env.engine.private.total_reward.get(AGENT_IDS[0], 0.0)),
                "details": {
                    "seed": rollout_config.seed,
                    "winner": winner,
                    "agent_0_model": agent_0_model,
                    "agent_1_model": agent_1_model,
                    "agent_0_reward": env.engine.private.total_reward.get(AGENT_IDS[0], 0.0),
                    "agent_1_reward": env.engine.private.total_reward.get(AGENT_IDS[1], 0.0),
                    "llm_call_count": len(turns),
                    "inference_error_count": inference_errors,
                },
            },
            "events": env.legacy_events(),
            "nev": env.nev_export(),
            "state": env.terminal_snapshot(),
            "artifact": [{"artifact_type": "turns", "turns": turns}],
        }
