"""FastAPI service for the Python Overcooked v2 multiplayer gold lane."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.checkpoint import RestoreReport
from engine import OvercookedV2Engine
from scenarios import run_scenario
from task_resolve import resolve_task


class ScenarioRequest(BaseModel):
    task: dict[str, Any]


class RolloutRequest(BaseModel):
    task: dict[str, Any] | None = None
    seed: int | None = None
    observation_profile: str | None = None


class JointStepRequest(BaseModel):
    joint_action: dict[str, Any]


class RestoreRequest(BaseModel):
    blob: str


class SimulateRequest(BaseModel):
    blob: str
    sequences: list[list[dict[str, Any]]]


@dataclass
class RolloutSession:
    rollout_id: str
    engine: OvercookedV2Engine
    checkpoints: dict[str, bytes] = field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="GameBench Overcooked v2 Python Gold", version="0.1.0")
    sessions: dict[str, RolloutSession] = {}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "lane": "python",
            "env_family": OvercookedV2Engine.ENV_FAMILY,
            "sessions": len(sessions),
        }

    @app.post("/run_scenario")
    def run_scenario_route(body: ScenarioRequest) -> dict[str, Any]:
        return run_scenario(body.task)

    @app.post("/rollouts")
    def create_rollout(body: RolloutRequest) -> dict[str, Any]:
        task = body.task or {
            "schema": "gamebench.task.overcooked_v2.v1",
            "task_id": "manual",
            "layout_id": "demo_tiny",
            "seed": body.seed or 1,
            "rules": {"base": "cooperative_full_obs", "overrides": {"max_steps": 64}},
        }
        if body.observation_profile:
            task = dict(task)
            task["readouts"] = {"profile": body.observation_profile}
        engine = OvercookedV2Engine()
        engine.reset_from_task(task, seed_override=body.seed)
        rollout_id = str(uuid.uuid4())
        sessions[rollout_id] = RolloutSession(rollout_id, engine)
        return _payload(sessions[rollout_id])

    @app.post("/rollouts/{rollout_id}/step")
    def step(rollout_id: str, body: JointStepRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        session.engine.step(body.joint_action)
        return _payload(session)

    @app.post("/rollouts/{rollout_id}/checkpoint")
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
            "nev_cursor": session.engine.nev.cursor(),
        }

    @app.post("/rollouts/{rollout_id}/restore")
    def restore(rollout_id: str, body: RestoreRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        blob = base64.b64decode(body.blob.encode("ascii"))
        restored = session.engine.restore_checkpoint(blob)
        return {
            "rollout_id": rollout_id,
            "restore_report": RestoreReport(bytes=len(blob), wall_ms=0.0, nev_events_restored=restored).to_dict(),
            "readout": session.engine.symbolic_readout(),
        }

    @app.post("/rollouts/{rollout_id}/simulate")
    def simulate(rollout_id: str, body: SimulateRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        root_blob = base64.b64decode(body.blob.encode("ascii"))
        results: list[dict[str, Any]] = []
        for index, sequence in enumerate(body.sequences):
            sim = session.engine.clone_for_sim()
            sim.restore_checkpoint(root_blob)
            for joint_action in sequence:
                if sim.private.terminated or sim.private.truncated:
                    break
                sim.step(joint_action)
            results.append(
                {
                    "index": index,
                    "joint_actions": sequence,
                    "reward": sim.private.total_reward,
                    "terminated": sim.private.terminated,
                    "truncated": sim.private.truncated,
                    "readout": sim.symbolic_readout(),
                    "nev_cursor": sim.nev.cursor(),
                }
            )
        return {
            "rollout_id": rollout_id,
            "root_nev_cursor": session.engine.nev.cursor(),
            "results": results,
        }

    @app.get("/rollouts/{rollout_id}/readout")
    def readout(rollout_id: str) -> dict[str, Any]:
        return _require(sessions, rollout_id).engine.symbolic_readout()

    @app.get("/rollouts/{rollout_id}/event_log")
    def event_log(rollout_id: str) -> dict[str, Any]:
        engine = _require(sessions, rollout_id).engine
        return {"events": engine.nev.export(), "legacy": engine.nev.legacy_strings(), "nev_cursor": engine.nev.cursor()}

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
