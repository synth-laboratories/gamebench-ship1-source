"""FastAPI service for the Python Crafter gold lane."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

_GAMEBENCH_ROOT = Path(
    os.environ.get("GAMEBENCH_ROOT", "").strip() or str(Path(__file__).resolve().parents[3])
).resolve()
if str(_GAMEBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_GAMEBENCH_ROOT))

from runtime.session_pool import SessionPool, SessionPoolConfig, SessionPoolFullError

from core.checkpoint import RestoreReport, decode_checkpoint
from engine import CrafterEngine
from render import (
    DEFAULT_RENDER_TILE_SIZE,
    RGBFrame,
    encode_gif_via_ffmpeg,
    encode_png_rgb,
    render_png_bytes,
    render_rgb_frame,
    render_svg,
)
from scenarios import run_scenario
from task_resolve import resolve_task


class RolloutRequest(BaseModel):
    task: dict[str, Any] | None = None
    seed: int | None = None
    limits: dict[str, Any] | None = None


class ProgressUpdateRequest(BaseModel):
    llm_calls_completed: int | None = None
    llm_call_in_flight: bool | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    wall_clock_seconds: float | None = None


class BatchRolloutRequest(BaseModel):
    items: list[RolloutRequest] | None = None
    tasks: list[dict[str, Any]] | None = None
    seeds: list[int | None] | None = None


class ScenarioRequest(BaseModel):
    task: dict[str, Any]


class StepRequest(BaseModel):
    action: str


class RestoreRequest(BaseModel):
    blob: str


class CheckpointExport(BaseModel):
    checkpoint_id: str
    blob: str


class SimulateRequest(BaseModel):
    blob: str
    sequences: list[list[str]]


@dataclass
class RolloutSession:
    rollout_id: str
    engine: CrafterEngine
    limits: dict[str, Any] = field(default_factory=dict)
    agent_progress: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)
    checkpoints: dict[str, bytes] = field(default_factory=dict)
    checkpoint_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    frames: dict[int, bytes] = field(default_factory=dict)
    gif_frames: dict[int, RGBFrame] = field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="GameBench Crafter Python Gold", version="0.1.0")
    pool = SessionPool[RolloutSession](SessionPoolConfig.from_env())

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "engine": "crafter-singleplayer-python-gold",
            "lane": "python",
            "env_family": CrafterEngine.ENV_FAMILY,
            "pool": pool.stats(),
        }

    @app.get("/info")
    def info() -> dict[str, Any]:
        return {
            "env_family": CrafterEngine.ENV_FAMILY,
            "capabilities": [
                "rollout",
                "checkpoint",
                "checkpoint_list",
                "nev_log",
                "symbolic_readout",
                "render_svg",
                "render_png",
                "frame_manifest",
                "replay_gif",
                "session_pool",
                "batch_rollout",
                "simulate_from_checkpoint",
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

    @app.post("/rollout")
    @app.post("/run_scenario")
    def run_scenario_route(body: ScenarioRequest) -> dict[str, Any]:
        return run_scenario(body.task)

    @app.post("/reset")
    @app.post("/rollouts")
    def create_rollout(body: RolloutRequest) -> dict[str, Any]:
        engine = _engine_from_rollout_request(body)
        rollout_id = str(uuid.uuid4())
        try:
            session = _admit_session(
                pool,
                rollout_id=rollout_id,
                engine=engine,
                limits=body.limits or {},
            )
        except SessionPoolFullError as exc:
            raise HTTPException(status_code=429, detail={"message": "env session pool full", "pool": exc.stats})
        _capture_frame_if_enabled(session)
        return _session_payload(session)

    @app.post("/rollouts/batch")
    def create_rollout_batch(body: BatchRolloutRequest) -> dict[str, Any]:
        items = _batch_rollout_items(body)
        if not items:
            raise HTTPException(status_code=400, detail="batch must include at least one rollout item")
        prepared = [_engine_from_rollout_request(item) for item in items]
        pool.evict_terminated()
        pool.evict_idle()
        available = pool.config.max_active_sessions - len(pool.values())
        if len(prepared) > available:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "env session pool full",
                    "requested_new_sessions": len(prepared),
                    "available_sessions": available,
                    "pool": pool.stats(),
                },
            )
        rollouts: list[dict[str, Any]] = []
        for engine in prepared:
            session = _admit_session(pool, rollout_id=str(uuid.uuid4()), engine=engine)
            _capture_frame_if_enabled(session)
            rollouts.append(_session_payload(session))
        return {"count": len(rollouts), "rollouts": rollouts, "pool": pool.stats()}

    @app.post("/step")
    def step_legacy(body: dict[str, Any]) -> dict[str, Any]:
        rollout_id = str(body.get("rollout_id", ""))
        session = _require_session(pool, rollout_id)
        session.engine.step(str(body.get("action", "noop")))
        _maybe_save_cadence_checkpoint(session)
        _capture_frame_if_enabled(session)
        _touch_session(pool, session)
        return _session_payload(session)

    @app.post("/rollouts/{rollout_id}/step")
    def step(rollout_id: str, body: StepRequest) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        session.engine.step(body.action)
        _maybe_save_cadence_checkpoint(session)
        _capture_frame_if_enabled(session)
        _touch_session(pool, session)
        return _session_payload(session)

    @app.get("/state/{rollout_id}")
    @app.get("/rollouts/{rollout_id}/state")
    def state(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        return _session_payload(session)

    @app.post("/rollouts/{rollout_id}/progress")
    def update_progress(rollout_id: str, body: ProgressUpdateRequest) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        _merge_agent_progress(session, body.model_dump(exclude_none=True))
        pool.touch(rollout_id)
        return _session_payload(session)

    @app.get("/rollouts/{rollout_id}/readout")
    def readout(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        return session.engine.symbolic_readout()

    @app.get("/rollouts/{rollout_id}/events")
    @app.get("/rollouts/{rollout_id}/event_log")
    def event_log(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        engine = session.engine
        return {
            "rollout_id": rollout_id,
            "events": engine.nev.export(),
            "legacy": engine.nev.legacy_strings(),
            "nev_cursor": engine.nev.cursor(),
        }

    @app.delete("/rollouts/{rollout_id}")
    def close_rollout(rollout_id: str) -> dict[str, Any]:
        released = pool.release(rollout_id)
        if not released:
            raise HTTPException(status_code=404, detail="rollout not found")
        return {"rollout_id": rollout_id, "released": True, "pool": pool.stats()}

    @app.post("/checkpoint/{rollout_id}")
    @app.post("/rollouts/{rollout_id}/checkpoint")
    def checkpoint_with_blob(rollout_id: str) -> dict[str, Any]:
        return _save_checkpoint(pool, rollout_id, include_blob=True)

    @app.post("/rollouts/{rollout_id}/checkpoints")
    def checkpoint(rollout_id: str) -> dict[str, Any]:
        return _save_checkpoint(pool, rollout_id, include_blob=False)

    @app.get("/rollouts/{rollout_id}/checkpoints")
    def list_checkpoints(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        checkpoints = sorted(
            session.checkpoint_metadata.values(),
            key=lambda item: (int(item.get("saved_index", 0)), str(item.get("checkpoint_id", ""))),
        )
        return {
            "rollout_id": rollout_id,
            "checkpoint_count": len(checkpoints),
            "checkpoints": checkpoints,
        }

    @app.get("/checkpoints/{checkpoint_id}/export")
    def export_checkpoint(checkpoint_id: str) -> dict[str, Any]:
        for pooled in pool.values():
            session = pooled.value
            if checkpoint_id in session.checkpoints:
                blob = session.checkpoints[checkpoint_id]
                return {"checkpoint_id": checkpoint_id, "blob": base64.b64encode(blob).decode("ascii")}
        raise HTTPException(status_code=404, detail="checkpoint not found")

    @app.post("/checkpoints/import")
    def import_checkpoint(body: CheckpointExport) -> dict[str, Any]:
        return _restore_new(pool, body.blob, checkpoint_id=body.checkpoint_id)

    @app.post("/restore")
    def restore_new(body: RestoreRequest) -> dict[str, Any]:
        return _restore_new(pool, body.blob)

    @app.post("/rollouts/{rollout_id}/restore")
    def restore_in_place(rollout_id: str, body: RestoreRequest) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        blob = _decode_checkpoint_blob(body.blob)
        _ensure_checkpoint_config_matches(session, blob)
        restored = session.engine.restore_checkpoint(blob)
        _capture_frame_if_enabled(session, force=True)
        pool.touch(rollout_id)
        return {
            "rollout_id": rollout_id,
            "restore_report": RestoreReport(bytes=len(blob), wall_ms=0.0, nev_events_restored=restored).to_dict(),
            "state": _session_payload(session),
        }

    @app.post("/rollouts/{rollout_id}/simulate")
    def simulate(rollout_id: str, body: SimulateRequest) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        root_blob = _decode_checkpoint_blob(body.blob)
        _ensure_checkpoint_config_matches(session, root_blob)
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
        pool.touch(rollout_id)
        return {"rollout_id": rollout_id, "root_nev_cursor": session.engine.nev.cursor(), "results": results}

    @app.get("/rollouts/{rollout_id}/render.svg")
    def render_svg_route(rollout_id: str) -> Response:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        engine = session.engine
        return Response(content=render_svg(engine), media_type="image/svg+xml")

    @app.get("/rollouts/{rollout_id}/render.png")
    def render_png_route(rollout_id: str) -> Response:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        return Response(content=render_png_bytes(session.engine), media_type="image/png")

    @app.get("/rollouts/{rollout_id}/frames/manifest")
    def frame_manifest(rollout_id: str) -> dict[str, Any]:
        session = _require_session(pool, rollout_id)
        pool.touch(rollout_id)
        return _frame_manifest(session)

    @app.get("/rollouts/{rollout_id}/frames/{step}.png")
    def frame_png_route(rollout_id: str, step: int) -> Response:
        session = _require_session(pool, rollout_id)
        if step == session.engine.private.step_index and step not in session.frames:
            _store_frame(session, step=step)
        frame = session.frames.get(step)
        if frame is None:
            raise HTTPException(status_code=404, detail="frame not found")
        pool.touch(rollout_id)
        return Response(content=frame, media_type="image/png")

    @app.get("/rollouts/{rollout_id}/replay.gif")
    def replay_gif_route(rollout_id: str, through_step: int | None = None) -> Response:
        session = _require_session(pool, rollout_id)
        if not session.gif_frames:
            _store_frame(session, step=session.engine.private.step_index)
        steps = sorted(step for step in session.gif_frames if through_step is None or step <= through_step)
        if not steps:
            _store_frame(session, step=session.engine.private.step_index)
            steps = [session.engine.private.step_index]
        frames = [session.gif_frames[step] for step in steps]
        pool.touch(rollout_id)
        return Response(content=encode_gif_via_ffmpeg(frames, delay_cs=10), media_type="image/gif")

    return app


def _engine_from_rollout_request(body: RolloutRequest) -> CrafterEngine:
    task = body.task or {
        "schema": "gamebench.task.crafter.v1",
        "task_id": "manual",
        "world": {"use_default": "policy_dev_small"},
        "rules": {"base": "no_homeostasis"},
    }
    engine = CrafterEngine()
    engine.reset(resolve_task(task, seed_override=body.seed))
    return engine


def _batch_rollout_items(body: BatchRolloutRequest) -> list[RolloutRequest]:
    if body.items is not None:
        return body.items
    tasks = body.tasks or []
    seeds = body.seeds or []
    items: list[RolloutRequest] = []
    for index, task in enumerate(tasks):
        seed = seeds[index] if index < len(seeds) else None
        items.append(RolloutRequest(task=task, seed=seed))
    return items


def _admit_session(
    pool: SessionPool[RolloutSession],
    *,
    rollout_id: str,
    engine: CrafterEngine,
    limits: dict[str, Any] | None = None,
) -> RolloutSession:
    session = RolloutSession(
        rollout_id=rollout_id,
        engine=engine,
        limits=dict(limits or {}),
    )
    pooled = pool.upsert(
        rollout_id,
        session,
        seed=engine.private.seed,
        task_id=engine.private.task_id,
    )
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


def _capture_frame_if_enabled(session: RolloutSession, *, force: bool = False) -> None:
    engine = session.engine
    resolved = engine.resolved
    if not force and resolved is not None:
        visual_enabled = bool(resolved.readouts.get("visual", False))
        stream_enabled = bool(resolved.stream.get("enabled", False))
        persist_frames = bool(resolved.stream.get("persist_frames", False))
        if not (visual_enabled or stream_enabled or persist_frames):
            return
    _store_frame(session, step=engine.private.step_index)


def _store_frame(session: RolloutSession, *, step: int) -> None:
    width, height, rows = render_rgb_frame(session.engine, tile_size=DEFAULT_RENDER_TILE_SIZE)
    session.gif_frames[int(step)] = (width, height, rows)
    session.frames[int(step)] = encode_png_rgb(width, height, rows)


def _frame_manifest(session: RolloutSession) -> dict[str, Any]:
    frames = []
    for step in sorted(session.frames):
        blob = session.frames[step]
        frames.append(
            {
                "step": step,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "url": f"/rollouts/{session.rollout_id}/frames/{step}.png",
            }
        )
    return {
        "rollout_id": session.rollout_id,
        "frame_count": len(frames),
        "latest_step": frames[-1]["step"] if frames else None,
        "frames": frames,
    }


def _save_checkpoint(
    pool: SessionPool[RolloutSession],
    rollout_id: str,
    *,
    include_blob: bool,
) -> dict[str, Any]:
    session = _require_session(pool, rollout_id)
    payload = _store_checkpoint(session, source="manual", include_blob=include_blob)
    pool.touch(rollout_id)
    return payload


def _store_checkpoint(session: RolloutSession, *, source: str, include_blob: bool) -> dict[str, Any]:
    blob = session.engine.checkpoint_bytes()
    checkpoint_id = str(uuid.uuid4())
    session.checkpoints[checkpoint_id] = blob
    metadata = _checkpoint_metadata(session, checkpoint_id=checkpoint_id, blob=blob, source=source)
    session.checkpoint_metadata[checkpoint_id] = metadata
    payload = dict(metadata)
    if include_blob:
        payload["blob"] = base64.b64encode(blob).decode("ascii")
    return payload


def _maybe_save_cadence_checkpoint(session: RolloutSession) -> None:
    resolved = session.engine.resolved
    if resolved is None:
        return
    interval = int(resolved.checkpoint_every_n_steps)
    step_index = int(session.engine.private.step_index)
    if interval <= 0 or step_index <= 0 or step_index % interval != 0:
        return
    for metadata in session.checkpoint_metadata.values():
        if metadata.get("source") == "cadence" and int(metadata.get("step_index", -1)) == step_index:
            return
    _store_checkpoint(session, source="cadence", include_blob=False)


def _checkpoint_metadata(session: RolloutSession, *, checkpoint_id: str, blob: bytes, source: str) -> dict[str, Any]:
    engine = session.engine
    return {
        "rollout_id": session.rollout_id,
        "checkpoint_id": checkpoint_id,
        "saved_index": len(session.checkpoints),
        "source": source,
        "auto": source == "cadence",
        "bytes": len(blob),
        "step_index": engine.private.step_index,
        "nev_cursor": engine.nev.cursor(),
        "config_hash": engine.private.config_hash,
        "export_url": f"/checkpoints/{checkpoint_id}/export",
    }


def _restore_new(
    pool: SessionPool[RolloutSession],
    blob_b64: str,
    *,
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    blob = _decode_checkpoint_blob(blob_b64)
    engine = CrafterEngine()
    restored = engine.restore_checkpoint(blob)
    rollout_id = str(uuid.uuid4())
    try:
        session = _admit_session(pool, rollout_id=rollout_id, engine=engine)
    except SessionPoolFullError as exc:
        raise HTTPException(status_code=429, detail={"message": "env session pool full", "pool": exc.stats})
    payload = _session_payload(session)
    report = RestoreReport(bytes=len(blob), wall_ms=0.0, nev_events_restored=restored).to_dict()
    payload["restore_report"] = report
    if checkpoint_id is not None:
        payload["checkpoint_id"] = checkpoint_id
    return payload


def _decode_checkpoint_blob(blob_b64: str) -> bytes:
    try:
        return base64.b64decode(blob_b64.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise HTTPException(status_code=400, detail="checkpoint blob must be valid base64") from exc


def _checkpoint_config_hash(blob: bytes) -> str:
    try:
        payload = decode_checkpoint(blob)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="checkpoint blob must be a supported GameBench checkpoint") from exc
    config_hash = payload.get("config_hash")
    if not isinstance(config_hash, str) or not config_hash:
        raise HTTPException(status_code=400, detail="checkpoint blob missing config_hash")
    return config_hash


def _ensure_checkpoint_config_matches(session: RolloutSession, blob: bytes) -> None:
    checkpoint_hash = _checkpoint_config_hash(blob)
    live_hash = session.engine.private.config_hash
    if checkpoint_hash != live_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "checkpoint config_hash does not match rollout config_hash",
                "checkpoint_config_hash": checkpoint_hash,
                "rollout_config_hash": live_hash,
            },
        )


def _merge_agent_progress(session: RolloutSession, patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        session.agent_progress[key] = value


def _rollout_progress(session: RolloutSession) -> dict[str, Any]:
    engine = session.engine
    agent = session.agent_progress
    prompt_tokens = int(agent.get("prompt_tokens") or 0)
    completion_tokens = int(agent.get("completion_tokens") or 0)
    total_tokens = int(agent.get("total_tokens") or (prompt_tokens + completion_tokens))
    wall_clock_seconds = agent.get("wall_clock_seconds")
    if wall_clock_seconds is None:
        wall_clock_seconds = max(0.0, time.monotonic() - session.started_at)
    return {
        "env_steps": int(engine.private.step_index),
        "llm_calls_completed": int(agent.get("llm_calls_completed") or 0),
        "llm_call_in_flight": bool(agent.get("llm_call_in_flight") or False),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "wall_clock_seconds": float(wall_clock_seconds),
    }


def _session_payload(session: RolloutSession) -> dict[str, Any]:
    engine = session.engine
    return {
        "rollout_id": session.rollout_id,
        "public": engine.public.to_dict(),
        "private": engine.private.to_dict(),
        "readout": engine.symbolic_readout(),
        "reward": engine.private.total_reward,
        "terminated": engine.private.terminated,
        "truncated": engine.private.truncated,
        "limits": dict(session.limits),
        "progress": _rollout_progress(session),
        "nev_tail": engine.nev.export()[-5:],
        "nev_cursor": engine.nev.cursor(),
        "frames": {
            "count": len(session.frames),
            "latest_step": max(session.frames) if session.frames else None,
            "manifest_url": f"/rollouts/{session.rollout_id}/frames/manifest",
        },
    }


app = create_app()
