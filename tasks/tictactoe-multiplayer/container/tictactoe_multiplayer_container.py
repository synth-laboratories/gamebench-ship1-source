"""GameBench tictactoe-multiplayer container — Groq 70b (agent_0) vs 8b (agent_1)."""

from __future__ import annotations

import os
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from container.mp_env import seed_specs_from_ints, task_info_many
from container.mp_rollout_policy import (
    DEFAULT_AGENT_0_MODEL,
    DEFAULT_AGENT_1_MODEL,
    EnvRolloutConfig,
    MultiplayerGroqRolloutPolicy,
)

TASK_FAMILY = "tictactoe_multiplayer_groq_70b_vs_8b"

app = FastAPI(title="gamebench-tictactoe-multiplayer-container", version="0.1.0")


class RolloutEnvSpec(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None


class RolloutPolicySpec(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class RolloutRequest(BaseModel):
    trace_correlation_id: str
    trial_id: str | None = None
    env: RolloutEnvSpec = Field(default_factory=RolloutEnvSpec)
    policy: RolloutPolicySpec = Field(default_factory=RolloutPolicySpec)


def _agent_models(policy_config: dict[str, Any]) -> tuple[str, str]:
    raw = dict(policy_config)
    agent_0 = dict(raw.get("agent_0", {}))
    agent_1 = dict(raw.get("agent_1", {}))
    m0 = str(agent_0.get("model", os.environ.get("GROQ_AGENT_0_MODEL", DEFAULT_AGENT_0_MODEL)))
    m1 = str(agent_1.get("model", os.environ.get("GROQ_AGENT_1_MODEL", DEFAULT_AGENT_1_MODEL)))
    return m0, m1


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "gamebench_tictactoe_multiplayer_container",
        "env_family": "tictactoe-multiplayer",
        "supports_many_live_seeds": True,
        "agent_0_default_model": os.environ.get("GROQ_AGENT_0_MODEL", DEFAULT_AGENT_0_MODEL),
        "agent_1_default_model": os.environ.get("GROQ_AGENT_1_MODEL", DEFAULT_AGENT_1_MODEL),
    }


@app.get("/task_info")
async def task_info(
    seed: int = 101,
    seeds: list[int] = Query(default=[]),
) -> dict[str, Any] | list[dict[str, Any]]:
    seed_list = seeds if seeds else [seed]
    m0, m1 = _agent_models({})
    specs = seed_specs_from_ints(seed_list)
    payloads = task_info_many(
        specs,
        agent_0_model=m0,
        agent_1_model=m1,
        task_family=TASK_FAMILY,
    )
    if len(payloads) == 1:
        return payloads[0]
    return payloads


@app.post("/rollout")
async def rollout(request: RolloutRequest) -> dict[str, Any]:
    env_config = request.env.config
    seed = int(request.env.seed or env_config.get("seed", 0))
    try:
        rollout_policy = MultiplayerGroqRolloutPolicy.from_policy_config(request.policy.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rollout_config = EnvRolloutConfig.from_request(seed, env_config)
    result = await rollout_policy.run(
        None,
        rollout_config,
        trace_correlation_id=request.trace_correlation_id,
        trial_id=request.trial_id,
    )
    result.setdefault("rollout_id", result.get("rollout_id") or f"tictactoe-mp-{uuid.uuid4()}")
    return result


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8091"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
