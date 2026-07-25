"""FastAPI service for the Python FrogsGame gold lane."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from core.checkpoint import RestoreReport
from engine import FrogsEngine
from render import render_png_bytes, render_svg
from scenarios import run_scenario
from task_resolve import resolve_task


DEFAULT_TASK = {
    "schema": "gamebench.task.frogs.v1",
    "task_id": "manual",
    "seed": 0,
    "board": [
        ["blue", "red", "green", "yellow"],
        ["green", "yellow", "red", "blue"],
        ["green", "blue", "yellow", "red"],
        ["red", "green", "yellow", "blue"],
    ],
    "rules": {"base": "classic_frogs", "overrides": {"max_steps": 16}},
}


class ScenarioRequest(BaseModel):
    task: dict[str, Any]


class RolloutRequest(BaseModel):
    task: dict[str, Any] | None = None
    seed: int | None = None


class StepRequest(BaseModel):
    action: dict[str, Any] | str


class RestoreRequest(BaseModel):
    blob: str


class SimulateRequest(BaseModel):
    blob: str
    sequences: list[list[dict[str, Any] | str]]


@dataclass
class RolloutSession:
    rollout_id: str
    engine: FrogsEngine
    checkpoints: dict[str, bytes] = field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="GameBench FrogsGame Python Gold", version="0.1.0")
    sessions: dict[str, RolloutSession] = {}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "lane": "python", "env_family": FrogsEngine.ENV_FAMILY, "sessions": len(sessions)}

    @app.post("/run_scenario")
    def run_scenario_route(body: ScenarioRequest) -> dict[str, Any]:
        return run_scenario(body.task)

    @app.post("/rollouts")
    def create_rollout(body: RolloutRequest) -> dict[str, Any]:
        task = body.task or DEFAULT_TASK
        engine = FrogsEngine()
        engine.reset(resolve_task(task, seed_override=body.seed))
        rollout_id = str(uuid.uuid4())
        sessions[rollout_id] = RolloutSession(rollout_id, engine)
        return _payload(sessions[rollout_id])

    @app.post("/rollouts/{rollout_id}/step")
    def step(rollout_id: str, body: StepRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        session.engine.step(body.action)
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

    @app.get("/rollouts/{rollout_id}/render.svg")
    def render_svg_route(rollout_id: str) -> Response:
        engine = _require(sessions, rollout_id).engine
        return Response(content=render_svg(engine), media_type="image/svg+xml")

    @app.get("/rollouts/{rollout_id}/render.png")
    def render_png_route(rollout_id: str) -> Response:
        engine = _require(sessions, rollout_id).engine
        return Response(content=render_png_bytes(engine), media_type="image/png")

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
