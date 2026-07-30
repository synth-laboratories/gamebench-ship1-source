"""Gold multiplayer env adapter — one isolated live instance per seed."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TASK_ROOT = Path(__file__).resolve().parents[1]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))

from gold.board import AGENT_IDS, AGENT_MARKS
from gold.engine import episode_id_for_task, TicTacToeMultiplayerEngine, WAIT_ACTION
from gold.observations import project_observation_for_agent
from gold.render import build_render_state


@dataclass(frozen=True)
class SeedSpec:
    seed: int
    scenario_id: str | None = None
    task_id: str | None = None

    def resolved_scenario_id(self) -> str:
        return self.scenario_id or f"groq_70b_vs_8b_{self.seed}"

    def resolved_task_id(self) -> str:
        return self.task_id or self.resolved_scenario_id()


@dataclass
class StepOutcome:
    observations: dict[str, dict[str, Any]]
    terminated: bool
    truncated: bool
    nev_message: str | None
    rewards: dict[str, float]
    dones: dict[str, bool]


class TictactoeMultiplayerEnv:
    """One live MARL episode. Never share across seeds or concurrent rollouts."""

    ENV_FAMILY = "tictactoe-multiplayer"

    def __init__(self) -> None:
        self._engine = TicTacToeMultiplayerEngine()
        self._seed_spec: SeedSpec | None = None

    @property
    def engine(self) -> TicTacToeMultiplayerEngine:
        return self._engine

    @property
    def seed_spec(self) -> SeedSpec | None:
        return self._seed_spec

    def reset(self, scenario_id: str, seed: int, task_id: str | None = None) -> dict[str, dict[str, Any]]:
        self._seed_spec = SeedSpec(seed=seed, scenario_id=scenario_id, task_id=task_id)
        episode_id = episode_id_for_task(scenario_id, seed, task_id or scenario_id)
        self._engine.reset(
            scenario_id=scenario_id,
            seed=seed,
            episode_id=episode_id,
            task_id=task_id or scenario_id,
        )
        return self.observations_llm_text()

    def observations_llm_text(self) -> dict[str, dict[str, Any]]:
        observations: dict[str, dict[str, Any]] = {}
        for agent_id in AGENT_IDS:
            obs = project_observation_for_agent(
                self._engine.public,
                self._engine.private,
                agent_id,
                profile="llm_text",
            )
            obs["board"] = list(self._engine.public.board)
            obs["mark"] = AGENT_MARKS[agent_id]
            obs["render_state"] = build_render_state(self._engine.public).to_dict()
            if self._seed_spec is not None:
                obs["seed"] = self._seed_spec.seed
                obs["scenario_id"] = self._seed_spec.resolved_scenario_id()
            observations[agent_id] = obs
        return observations

    def step_joint(self, joint_action: dict[str, Any]) -> StepOutcome:
        _, event = self._engine.step(dict(joint_action))
        rewards, dones, _ = self._engine.marl_step_return()
        return StepOutcome(
            observations=self.observations_llm_text(),
            terminated=self._engine.private.terminated,
            truncated=self._engine.private.truncated,
            nev_message=event.message if event else None,
            rewards=rewards,
            dones=dones,
        )

    @staticmethod
    def joint_place(agent_id: str, position: int) -> dict[str, Any]:
        joint: dict[str, Any] = {agent: dict(WAIT_ACTION) for agent in AGENT_IDS}
        joint[agent_id] = {"kind": "place", "position": position}
        return joint

    def legacy_events(self) -> list[str]:
        return self._engine.nev.legacy_strings()

    def nev_export(self) -> list[dict[str, Any]]:
        return self._engine.nev.export()

    def terminal_snapshot(self) -> dict[str, Any]:
        return {
            "public": self._engine.public.to_dict(),
            "private": self._engine.private.to_dict(),
        }


def spawn_env(spec: SeedSpec) -> TictactoeMultiplayerEnv:
    env = TictactoeMultiplayerEnv()
    env.reset(
        scenario_id=spec.resolved_scenario_id(),
        seed=spec.seed,
        task_id=spec.resolved_task_id(),
    )
    return env


def seed_specs_from_ints(
    seeds: list[int],
    *,
    scenario_prefix: str = "groq_70b_vs_8b",
) -> list[SeedSpec]:
    return [SeedSpec(seed=seed, scenario_id=f"{scenario_prefix}_{seed}") for seed in seeds]


def task_info_payload(
    spec: SeedSpec,
    *,
    agent_0_model: str,
    agent_1_model: str,
    task_family: str,
) -> dict[str, Any]:
    env = spawn_env(spec)
    return {
        "status": "ok",
        "task_family": task_family,
        "env_family": TictactoeMultiplayerEnv.ENV_FAMILY,
        "supports_rollout": True,
        "seed": spec.seed,
        "scenario_id": spec.resolved_scenario_id(),
        "episode_id": env.engine.private.episode_id,
        "agent_0_model": agent_0_model,
        "agent_1_model": agent_1_model,
        "agents": list(AGENT_IDS),
        "initial_observations": env.observations_llm_text(),
    }


def task_info_many(
    specs: list[SeedSpec],
    *,
    agent_0_model: str,
    agent_1_model: str,
    task_family: str,
) -> list[dict[str, Any]]:
    return [
        task_info_payload(
            spec,
            agent_0_model=agent_0_model,
            agent_1_model=agent_1_model,
            task_family=task_family,
        )
        for spec in specs
    ]
