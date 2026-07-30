"""Agent-facing FrogsGame env adapter."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TASK_ROOT = Path(__file__).resolve().parents[2]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))
for extra in (TASK_ROOT / "gold_python", TASK_ROOT / "shared"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from gold_python.agent_io import format_agent_observation, parse_action_text
from gold_python.engine import FrogsEngine
from gold_python.render import render_png_bytes, render_svg
from task_resolve import resolve_task


@dataclass(frozen=True)
class SeedSpec:
    seed: int
    task_path: str | None = None
    task: dict[str, Any] | None = None
    task_id: str | None = None

    def load_task(self) -> dict[str, Any]:
        if self.task is not None:
            task = json.loads(json.dumps(self.task))
        elif self.task_path:
            task = json.loads((TASK_ROOT / self.task_path).read_text())
        else:
            task = json.loads((TASK_ROOT / "tasks" / "policy_dev_template.json").read_text())
        task["seed"] = self.seed
        if self.task_id:
            task["task_id"] = self.task_id
        else:
            task["task_id"] = f"{task.get('task_id', 'frogs_policy_dev')}_{self.seed}"
        return task


@dataclass
class StepOutcome:
    observation: dict[str, Any]
    terminated: bool
    truncated: bool
    nev_message: str | None
    public: dict[str, Any]
    private: dict[str, Any]
    parsed_action: dict[str, Any]


class FrogsSingleplayerEnv:
    ENV_FAMILY = "frogs-singleplayer"

    def __init__(self) -> None:
        self._engine = FrogsEngine()
        self._seed_spec: SeedSpec | None = None

    @property
    def engine(self) -> FrogsEngine:
        return self._engine

    def reset(self, spec: SeedSpec) -> dict[str, Any]:
        self._seed_spec = spec
        task = spec.load_task()
        self._engine.reset(resolve_task(task, seed_override=spec.seed))
        return self.observation_llm_text()

    def observation_llm_text(self) -> dict[str, Any]:
        payload = format_agent_observation(self._engine.symbolic_readout())
        if self._seed_spec is not None:
            payload["seed"] = self._seed_spec.seed
            payload["task_id"] = self._engine.resolved.task_id if self._engine.resolved else "unknown"
        return payload

    def step_text(self, raw_action: Any) -> StepOutcome:
        parsed = parse_action_text(raw_action, self._engine.valid_actions())
        before_cursor = self._engine.nev.cursor()
        self._engine.step(parsed.action)
        event = self._engine.nev.events[-1] if self._engine.nev.cursor() > before_cursor else None
        return StepOutcome(
            observation=self.observation_llm_text(),
            terminated=self._engine.private.terminated,
            truncated=self._engine.private.truncated,
            nev_message=event.message if event else None,
            public=self._engine.public.to_dict(),
            private=self._engine.private.to_dict(),
            parsed_action=parsed.to_dict(),
        )

    def legacy_events(self) -> list[str]:
        return self._engine.nev.legacy_strings()

    def nev_export(self) -> list[dict[str, Any]]:
        return self._engine.nev.export()

    def terminal_snapshot(self) -> dict[str, Any]:
        return {"public": self._engine.public.to_dict(), "private": self._engine.private.to_dict()}

    def render_payload(self) -> dict[str, Any]:
        return {
            "ascii": self._engine.symbolic_readout()["ascii"],
            "svg": render_svg(self._engine),
            "png_bytes": len(render_png_bytes(self._engine)),
        }


def spawn_env(spec: SeedSpec) -> FrogsSingleplayerEnv:
    env = FrogsSingleplayerEnv()
    env.reset(spec)
    return env


def spawn_many(specs: Iterable[SeedSpec]) -> list[FrogsSingleplayerEnv]:
    return [spawn_env(spec) for spec in specs]


def task_info_payload(spec: SeedSpec, *, task_family: str, policy_id: str) -> dict[str, Any]:
    env = spawn_env(spec)
    return {
        "status": "ok",
        "task_family": task_family,
        "env_family": FrogsSingleplayerEnv.ENV_FAMILY,
        "reward_type": "frogs_binary_submit",
        "supports_rollout": True,
        "supports_checkpoint": True,
        "supports_visual": True,
        "seed": spec.seed,
        "task_id": env.engine.resolved.task_id if env.engine.resolved else "unknown",
        "episode_id": env.engine.private.episode_id,
        "policy_id": policy_id,
        "initial_observation": env.observation_llm_text(),
    }


def task_info_many(specs: list[SeedSpec], *, task_family: str, policy_id: str) -> list[dict[str, Any]]:
    return [task_info_payload(spec, task_family=task_family, policy_id=policy_id) for spec in specs]
