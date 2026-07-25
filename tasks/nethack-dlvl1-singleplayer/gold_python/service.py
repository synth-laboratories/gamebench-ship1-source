"""FastAPI service for the own NetHack dlvl-1 Python gold lane."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.task_resolve import resolve_task

from .engine import NethackDlvl1Engine
from .scenarios import run_scenario


TASK_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TASK = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "bootstrap_descend.json").read_text())


class ScenarioRequest(BaseModel):
    task: dict[str, Any]


class RolloutRequest(BaseModel):
    task: dict[str, Any] | None = None
    seed: int | None = None


class StepRequest(BaseModel):
    action: int | str


class RestoreRequest(BaseModel):
    blob: str


class SimulateRequest(BaseModel):
    blob: str
    sequences: list[list[int | str]]


@dataclass
class RolloutSession:
    rollout_id: str
    engine: NethackDlvl1Engine
    checkpoints: dict[str, bytes] = field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="GameBench NetHack dlvl-1 Python Gold", version="0.1.0")
    sessions: dict[str, RolloutSession] = {}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "lane": "python", "env_family": NethackDlvl1Engine.ENV_FAMILY, "sessions": len(sessions)}

    @app.post("/run_scenario")
    def run_scenario_route(body: ScenarioRequest) -> dict[str, Any]:
        return run_scenario(body.task)

    @app.post("/rollouts")
    def create_rollout(body: RolloutRequest) -> dict[str, Any]:
        task = dict(body.task or DEFAULT_TASK)
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task, seed_override=body.seed))
        rollout_id = str(uuid.uuid4())
        session = RolloutSession(rollout_id=rollout_id, engine=engine)
        sessions[rollout_id] = session
        return _payload(session)

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
            "readout": session.engine.symbolic_readout(),
        }

    @app.post("/rollouts/{rollout_id}/restore")
    def restore(rollout_id: str, body: RestoreRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        try:
            blob = base64.b64decode(body.blob.encode("ascii"), validate=True)
            restored = session.engine.restore_checkpoint(blob)
        except (ValueError, UnicodeError) as error:
            raise HTTPException(status_code=400, detail=f"invalid checkpoint: {error}") from error
        return {"rollout_id": rollout_id, "restore_report": {"bytes": len(blob), "wall_ms": 0.0, "nev_events_restored": restored}, "readout": session.engine.symbolic_readout()}

    @app.post("/rollouts/{rollout_id}/simulate")
    def simulate(rollout_id: str, body: SimulateRequest) -> dict[str, Any]:
        session = _require(sessions, rollout_id)
        try:
            blob = base64.b64decode(body.blob.encode("ascii"), validate=True)
        except (ValueError, UnicodeError) as error:
            raise HTTPException(status_code=400, detail=f"invalid checkpoint: {error}") from error
        results: list[dict[str, Any]] = []
        for index, sequence in enumerate(body.sequences):
            sim = session.engine.clone_for_sim()
            sim.restore_checkpoint(blob)
            for action in sequence:
                if sim.state["terminated"] or sim.state["truncated"]:
                    break
                sim.step(action)
            results.append({"index": index, "actions": sequence, "reward": sim.state["reward"], "terminated": sim.state["terminated"], "truncated": sim.state["truncated"], "readout": sim.symbolic_readout(), "nev_cursor": sim.nev.cursor()})
        return {"rollout_id": rollout_id, "root_nev_cursor": session.engine.nev.cursor(), "results": results}

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
    readout = session.engine.symbolic_readout()
    return {"rollout_id": session.rollout_id, "readout": readout, "reward": session.engine.state["reward"], "terminated": session.engine.state["terminated"], "truncated": session.engine.state["truncated"], "nev_cursor": session.engine.nev.cursor()}


app = create_app()
