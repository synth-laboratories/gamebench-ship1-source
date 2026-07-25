"""FastAPI container surface for multiplayer Tic-Tac-Toe gold reference."""

from __future__ import annotations

import base64
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_GAMEBENCH_ROOT = Path(__file__).resolve().parents[3]
if str(_GAMEBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_GAMEBENCH_ROOT))

from runtime.session_pool import SessionPool, SessionPoolConfig, SessionPoolFullError

from gold.core.checkpoint import RestoreReport
from gold.engine import AGENT_IDS, episode_id_from_task, TicTacToeMultiplayerEngine
from gold.observations import project_observations
from gold.render import build_render_state
from gold.scenarios import run_scenario


class StepRequest(BaseModel):
    joint_action: dict[str, Any]
    observation_profile: str = "llm_text"


class ResetRequest(BaseModel):
    scenario_id: str = "manual"
    seed: int = 0
    task_id: str | None = None


class ScenarioRequest(BaseModel):
    task: dict[str, Any]


class CheckpointExport(BaseModel):
    checkpoint_id: str
    blob: str


@dataclass
class RolloutSession:
    rollout_id: str
    engine: TicTacToeMultiplayerEngine
    checkpoints: dict[str, bytes] = field(default_factory=dict)


def create_app(pool_config: SessionPoolConfig | None = None) -> FastAPI:
    app = FastAPI(title="GameBench Tic-Tac-Toe Multiplayer Gold", version="0.1.0")
    pool = SessionPool[RolloutSession](pool_config or SessionPoolConfig.from_env())

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "engine": "tictactoe-multiplayer-gold",
            "env_family": "tictactoe-multiplayer",
            "pool": pool.stats(),
        }

    @app.get("/info")
    def info() -> dict[str, Any]:
        return {
            "env_family": "tictactoe-multiplayer",
            "agents": list(AGENT_IDS),
            "step_mode": "joint_action",
            "capabilities": [
                "rollout",
                "checkpoint",
                "nev_log",
                "render_state",
                "marl_observations",
                "session_pool",
            ],
            "pool": pool.stats(),
        }

    @app.get("/pool")
    def pool_stats() -> dict[str, Any]:
        return pool.stats()

    @app.post("/pool/evict_idle")
    def evict_idle() -> dict[str, Any]:
        evicted = pool.evict_idle()
        return {"evicted": evicted, "pool": pool.stats()}

    @app.get("/agents")
    def agents() -> dict[str, Any]:
        return {"agents": list(AGENT_IDS)}

    @app.post("/rollout")
    def rollout(body: ScenarioRequest) -> dict[str, Any]:
        result = run_scenario(body.task)
        episode_id = episode_id_from_task(body.task)
        engine = TicTacToeMultiplayerEngine()
        engine.reset(
            scenario_id=result["scenario_id"],
            seed=int(body.task.get("seed", 0)),
            episode_id=episode_id,
            task_id=str(body.task.get("task_id", result["scenario_id"])),
        )
        rollout_id = episode_id
        task_id = str(body.task.get("task_id", result["scenario_id"]))
        seed = int(body.task.get("seed", 0))
        try:
            _admit_session(
                pool,
                rollout_id=rollout_id,
                engine=engine,
                seed=seed,
                task_id=task_id,
                terminated=bool(result["state"]["private"]["terminated"]),
            )
        except SessionPoolFullError as exc:
            raise HTTPException(status_code=429, detail={"message": "env session pool full", "pool": exc.stats})
        return {
            "rollout_id": rollout_id,
            "scenario_id": result["scenario_id"],
            "events": result["events"],
            "nev": result["nev"],
            "rewards": result["state"]["private"]["total_reward"],
            "terminated": result["state"]["private"]["terminated"],
        }

    @app.post("/reset")
    def reset(body: ResetRequest) -> dict[str, Any]:
        task_id = body.task_id or body.scenario_id
        episode_id = episode_id_from_task(
            {
                "scenario_id": body.scenario_id,
                "seed": body.seed,
                "task_id": task_id,
            }
        )
        rollout_id = episode_id
        engine = TicTacToeMultiplayerEngine()
        engine.reset(
            scenario_id=body.scenario_id,
            seed=body.seed,
            episode_id=episode_id,
            task_id=task_id,
        )
        try:
            session = _admit_session(
                pool,
                rollout_id=rollout_id,
                engine=engine,
                seed=body.seed,
                task_id=task_id,
            )
        except SessionPoolFullError as exc:
            raise HTTPException(status_code=429, detail={"message": "env session pool full", "pool": exc.stats})
        return _session_payload(session)

    @app.post("/rollouts/{rollout_id}/step")
    def step(rollout_id: str, body: StepRequest) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        session.engine.step(body.joint_action)
        _touch_session(pool, session)
        payload = _session_payload(session, observation_profile=body.observation_profile)
        return payload

    @app.get("/rollouts/{rollout_id}/state")
    def state(rollout_id: str, observation_profile: str = "structured_facts") -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        return _session_payload(session, observation_profile=observation_profile)

    @app.get("/rollouts/{rollout_id}/events")
    def events(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        engine = session.engine
        return {
            "rollout_id": rollout_id,
            "nev_cursor": engine.nev.cursor(),
            "events": engine.nev.export(),
            "legacy": engine.nev.legacy_strings(),
        }

    @app.delete("/rollouts/{rollout_id}")
    def close_rollout(rollout_id: str) -> dict[str, Any]:
        released = pool.release(rollout_id)
        if not released:
            raise HTTPException(status_code=404, detail="rollout not found")
        return {"rollout_id": rollout_id, "released": True, "pool": pool.stats()}

    @app.post("/rollouts/{rollout_id}/checkpoints")
    def save_checkpoint(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        checkpoint_id = str(uuid.uuid4())
        blob = session.engine.checkpoint_bytes()
        session.checkpoints[checkpoint_id] = blob
        pool.touch(rollout_id)
        return {
            "checkpoint_id": checkpoint_id,
            "bytes": len(blob),
            "nev_cursor": session.engine.nev.cursor(),
        }

    @app.get("/checkpoints/{checkpoint_id}/export")
    def export_checkpoint(checkpoint_id: str) -> dict[str, Any]:
        for pooled in pool.values():
            session = pooled.value
            if checkpoint_id in session.checkpoints:
                blob = session.checkpoints[checkpoint_id]
                return {
                    "checkpoint_id": checkpoint_id,
                    "blob": base64.b64encode(blob).decode("ascii"),
                }
        raise HTTPException(status_code=404, detail="checkpoint not found")

    @app.post("/checkpoints/import")
    def import_checkpoint(body: CheckpointExport) -> dict[str, Any]:
        rollout_id = str(uuid.uuid4())
        engine = TicTacToeMultiplayerEngine()
        blob = base64.b64decode(body.blob.encode("ascii"))
        nev_count = engine.restore_checkpoint(blob)
        report = RestoreReport(bytes=len(blob), wall_ms=0.0, nev_events_restored=nev_count)
        try:
            session = _admit_session(pool, rollout_id=rollout_id, engine=engine)
        except SessionPoolFullError as exc:
            raise HTTPException(status_code=429, detail={"message": "env session pool full", "pool": exc.stats})
        return {
            "rollout_id": rollout_id,
            "restore_report": report.to_dict(),
            "state": _session_payload(session),
        }

    @app.post("/run_scenario")
    def run_scenario_route(body: ScenarioRequest) -> dict[str, Any]:
        return run_scenario(body.task)

    return app


def _admit_session(
    pool: SessionPool[RolloutSession],
    *,
    rollout_id: str,
    engine: TicTacToeMultiplayerEngine,
    seed: int | None = None,
    task_id: str | None = None,
    terminated: bool = False,
) -> RolloutSession:
    session = RolloutSession(rollout_id=rollout_id, engine=engine)
    pooled = pool.upsert(
        rollout_id,
        session,
        seed=seed,
        task_id=task_id,
    )
    if terminated:
        pool.touch(rollout_id, terminated=True)
        pool.release_if_terminal(rollout_id)
    return pooled.value


def _require_session(pool: SessionPool[RolloutSession], rollout_id: str) -> RolloutSession:
    pooled = pool.get(rollout_id)
    if pooled is None:
        raise HTTPException(status_code=404, detail="rollout not found")
    return pooled.value


def _touch_session(pool: SessionPool[RolloutSession], session: RolloutSession) -> None:
    engine = session.engine
    terminated = engine.private.terminated or engine.private.truncated
    pool.touch(session.rollout_id, terminated=terminated)


def _session_payload(
    session: RolloutSession,
    observation_profile: str = "llm_text",
) -> dict[str, Any]:
    engine = session.engine
    render = build_render_state(engine.public)
    last_joint_event = engine.nev.legacy_strings()[-1] if engine.nev.cursor() else None
    observations = project_observations(
        engine.public,
        engine.private,
        profile=observation_profile,
        last_joint_event=last_joint_event,
    )
    rewards, dones, info = engine.marl_step_return()
    return {
        "rollout_id": session.rollout_id,
        "public": engine.public.to_dict(),
        "private": engine.private.to_dict(),
        "observations": observations,
        "observation": observations.get(engine.public.current_agent),
        "render_state": render.to_dict(),
        "rewards": rewards,
        "dones": dones,
        "info": info,
        "nev_tail": engine.nev.export()[-5:],
        "nev_cursor": engine.nev.cursor(),
    }
