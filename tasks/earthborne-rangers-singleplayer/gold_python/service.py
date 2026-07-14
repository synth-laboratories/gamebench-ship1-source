"""FastAPI service for the synthetic Earthborne Rangers Python lane."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.checkpoint import RestoreReport
from engine import EarthborneRangersEngine
from scenarios import run_scenario
from task_resolve import SCHEMA, resolve_task


DEFAULT_TASK = {
    "schema": SCHEMA,
    "task_id": "manual",
    "scenario_id": "manual",
    "default_archetype": "pathfinder",
}


class ScenarioRequest(BaseModel):
    task: dict[str, Any]


class RolloutRequest(BaseModel):
    task: dict[str, Any] | None = None
    seed: int | None = None


class StepRequest(BaseModel):
    action: str | dict[str, Any]


class RestoreRequest(BaseModel):
    blob: str


class SimulateRequest(BaseModel):
    blob: str
    sequences: list[list[str]]


@dataclass
class RolloutSession:
    rollout_id: str
    engine: EarthborneRangersEngine
    checkpoints: dict[str, bytes] = field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="GameBench Earthborne Rangers Python Gold", version="0.1.0")
    sessions: dict[str, RolloutSession] = {}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "lane": "python", "env_family": EarthborneRangersEngine.ENV_FAMILY, "sessions": len(sessions)}

    @app.get("/info")
    def info() -> dict[str, Any]:
        return {
            "env_family": EarthborneRangersEngine.ENV_FAMILY,
            "capabilities": ["rollout", "checkpoint", "nev_log", "symbolic_readout", "simulate_from_checkpoint"],
        }

    @app.post("/run_scenario")
    @app.post("/rollout")
    def run_scenario_route(body: ScenarioRequest) -> dict[str, Any]:
        return run_scenario(body.task)

    @app.post("/rollouts")
    @app.post("/reset")
    def create_rollout(body: RolloutRequest) -> dict[str, Any]:
        engine = EarthborneRangersEngine()
        engine.reset(resolve_task(body.task or DEFAULT_TASK, seed_override=body.seed))
        rollout_id = str(uuid.uuid4())
        sessions[rollout_id] = RolloutSession(rollout_id, engine)
        return _payload(sessions[rollout_id])

    @app.post("/rollouts/{rollout_id}/step")
    def step(rollout_id: str, body: StepRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        session.engine.step(body.action)
        return _payload(session)

    @app.get("/rollouts/{rollout_id}/readout")
    @app.get("/rollouts/{rollout_id}/state")
    def readout(rollout_id: str) -> dict[str, Any]:
        return _require(sessions, rollout_id).engine.symbolic_readout()

    @app.get("/rollouts/{rollout_id}/event_log")
    @app.get("/rollouts/{rollout_id}/events")
    def event_log(rollout_id: str) -> dict[str, Any]:
        engine = _require(sessions, rollout_id).engine
        return {"rollout_id": rollout_id, "events": engine.nev.export(), "legacy": engine.nev.legacy_strings(), "nev_cursor": engine.nev.cursor()}

    @app.post("/rollouts/{rollout_id}/checkpoint")
    @app.post("/rollouts/{rollout_id}/checkpoints")
    def checkpoint(rollout_id: str) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        blob = session.engine.checkpoint_bytes()
        checkpoint_id = str(uuid.uuid4())
        session.checkpoints[checkpoint_id] = blob
        return {
            "rollout_id": rollout_id,
            "checkpoint_id": checkpoint_id,
            "blob": base64.b64encode(blob).decode("ascii"),
            "bytes": len(blob),
            "step_index": session.engine.private.step_index,
            "nev_cursor": session.engine.nev.cursor(),
            "config_hash": session.engine.private.config_hash,
        }

    @app.post("/rollouts/{rollout_id}/restore")
    def restore(rollout_id: str, body: RestoreRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        blob = base64.b64decode(body.blob.encode("ascii"))
        restored = session.engine.restore_checkpoint(blob)
        return {
            "rollout_id": rollout_id,
            "restore_report": RestoreReport(bytes=len(blob), wall_ms=0.0, nev_events_restored=restored).to_dict(),
            "state": _payload(session),
        }

    @app.post("/rollouts/{rollout_id}/simulate")
    def simulate(rollout_id: str, body: SimulateRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        root_blob = base64.b64decode(body.blob.encode("ascii"))
        results: list[dict[str, Any]] = []
        for index, sequence in enumerate(body.sequences):
            sim = session.engine.clone_for_sim()
            sim.restore_checkpoint(root_blob)
            for action in sequence:
                if sim.private.terminated or sim.private.truncated:
                    break
                sim.step(action)
            results.append(
                {
                    "index": index,
                    "actions": sequence,
                    "reward": sim.private.total_reward,
                    "terminated": sim.private.terminated,
                    "truncated": sim.private.truncated,
                    "readout": sim.symbolic_readout(),
                    "nev_cursor": sim.nev.cursor(),
                }
            )
        return {"rollout_id": rollout_id, "root_nev_cursor": session.engine.nev.cursor(), "results": results}

    return app


def _require(sessions: dict[str, RolloutSession], rollout_id: str) -> RolloutSession:
    session = sessions.get(rollout_id)
    if session is None:
        raise HTTPException(status_code=404, detail="rollout not found")
    return session


def _payload(session: RolloutSession) -> dict[str, Any]:
    engine = session.engine
    return {
        "rollout_id": session.rollout_id,
        "readout": engine.symbolic_readout(),
        "reward": engine.private.total_reward,
        "terminated": engine.private.terminated,
        "truncated": engine.private.truncated,
        "nev_cursor": engine.nev.cursor(),
    }


app = create_app()
