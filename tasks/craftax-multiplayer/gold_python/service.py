from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .engine import CraftaxCoopEnv
from .render import RGBFrame, RenderMode, encode_gif, render_rgb


@dataclass(frozen=True, slots=True)
class MediaPayload:
    content_type: str
    body: bytes


class CraftaxService:
    def __init__(self) -> None:
        self.env = CraftaxCoopEnv()
        self.rollouts: dict[str, CraftaxCoopEnv] = {}
        self.frames: dict[str, dict[int, RGBFrame]] = {}
        self.capture_frames: dict[str, bool] = {}
        self.render_modes: dict[str, RenderMode] = {}
        self._next_rollout = 1

    @staticmethod
    def _configuration(body: dict[str, Any]) -> tuple[int, int, int, int, str | None, dict[str, Any]]:
        task = body.get("task") if isinstance(body.get("task"), dict) else body
        seed = int(body.get("seed", task.get("seed", 0)))
        agent_count = int(task.get("agent_count", len(task.get("agents", ())) or 3))
        max_timesteps = int(task.get("max_timesteps", task.get("max_steps", 100_000)))
        view_radius = int(task.get("view_radius", 5))
        rules_profile = task.get("rules_profile")
        if rules_profile is not None and not isinstance(rules_profile, str):
            raise ValueError("rules_profile must be a string")
        coordination = task.get("coordination", {})
        if not isinstance(coordination, dict):
            raise ValueError("coordination must be an object")
        return seed, agent_count, max_timesteps, view_radius, rules_profile, coordination

    @staticmethod
    def _joint_action(env: CraftaxCoopEnv, raw: Any, *, fill_missing: bool = False) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise TypeError("joint_action must be an object")
        if fill_missing:
            return {agent_id: raw.get(agent_id, {"kind": "noop"}) for agent_id in env.agent_ids}
        return dict(raw)

    @staticmethod
    def _readout(env: CraftaxCoopEnv) -> dict[str, Any]:
        state = env._require_state()
        return {
            "observations": env.observations(),
            "state": state.to_dict(),
            "terminated": state.terminated,
            "termination_reason": state.termination_reason,
            "timestep": state.timestep,
        }

    @staticmethod
    def _nev(env: CraftaxCoopEnv, rollout_id: str | None = None) -> dict[str, Any]:
        state = env._require_state()
        payload: dict[str, Any] = {
            "structured": state.nev,
            "legacy": state.legacy_nev,
            "nev_cursor": len(state.nev),
        }
        if rollout_id is not None:
            payload["rollout_id"] = rollout_id
        return payload

    @staticmethod
    def _step_payload(
        env: CraftaxCoopEnv,
        joint_action: dict[str, Any],
        rollout_id: str | None = None,
    ) -> dict[str, Any]:
        observations, rewards, dones, info = env.step(joint_action)
        payload: dict[str, Any] = {
            "observations": observations,
            "rewards": rewards,
            "dones": dones,
            "info": info,
        }
        if rollout_id is not None:
            payload["rollout_id"] = rollout_id
        return payload

    def _new_env(self, body: dict[str, Any]) -> tuple[CraftaxCoopEnv, dict[str, dict[str, Any]], dict[str, Any]]:
        seed, agent_count, max_timesteps, view_radius, rules_profile, coordination = self._configuration(body)
        env = CraftaxCoopEnv(agent_count, max_timesteps, view_radius, rules_profile, coordination)
        observations, info = env.reset(seed)
        return env, observations, info

    def _require_rollout(self, rollout_id: str) -> CraftaxCoopEnv:
        try:
            return self.rollouts[rollout_id]
        except KeyError as exc:
            raise KeyError(f"rollout not found: {rollout_id}") from exc

    @staticmethod
    def _visual_configuration(body: dict[str, Any]) -> tuple[bool, RenderMode]:
        task = body.get("task") if isinstance(body.get("task"), dict) else body
        readouts = task.get("readouts") if isinstance(task.get("readouts"), dict) else {}
        stream = readouts.get("stream") if isinstance(readouts.get("stream"), dict) else {}
        capture = bool(readouts.get("visual") or stream.get("enabled") or stream.get("persist_frames"))
        mode = task.get("render_mode", readouts.get("render_mode", "auto"))
        if mode not in ("auto", "sprites", "symbolic"):
            raise ValueError(f"unsupported render_mode {mode!r}")
        return capture, mode

    def _store_frame(self, rollout_id: str) -> RGBFrame:
        env = self._require_rollout(rollout_id)
        frame = render_rgb(env, self.render_modes.get(rollout_id, "auto"))
        self.frames.setdefault(rollout_id, {})[env._require_state().timestep] = frame
        return frame

    def _frame_manifest(self, rollout_id: str) -> dict[str, Any]:
        entries = []
        for step, frame in sorted(self.frames.get(rollout_id, {}).items()):
            blob = frame.png()
            entries.append({
                "step": step,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "url": f"/rollouts/{rollout_id}/frames/{step}.png",
            })
        return {
            "rollout_id": rollout_id,
            "frame_count": len(entries),
            "latest_step": entries[-1]["step"] if entries else None,
            "frames": entries,
        }

    def _run_scenario(self, body: dict[str, Any]) -> dict[str, Any]:
        task = body.get("task")
        if not isinstance(task, dict):
            raise TypeError("task must be an object")
        env, _, _ = self._new_env(task)
        scenario_id = str(task.get("scenario_id", task.get("task_id", "manual")))
        checkpoint_after = task.get("checkpoint_after")
        checkpoint: dict[str, Any] | None = None
        for index, raw_action in enumerate(task.get("joint_actions", ()), start=1):
            if env._require_state().terminated:
                break
            env.step(self._joint_action(env, raw_action, fill_missing=True))
            if checkpoint_after == index:
                checkpoint = env.checkpoint()
        if checkpoint is not None:
            env.restore(checkpoint)
            for raw_action in task.get("restore_then_actions", ()):
                if env._require_state().terminated:
                    break
                env.step(self._joint_action(env, raw_action, fill_missing=True))
        state = env._require_state()
        return {
            "scenario_id": scenario_id,
            "events": state.legacy_nev,
            "nev": state.nev,
            "checkpoint_cursor": len(state.nev),
            "state": state.to_dict(),
            "readout": self._readout(env),
        }

    def handle(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, list[str]] | None = None,
    ) -> tuple[int, Any]:
        body = {} if body is None else body
        query = {} if query is None else query
        if method == "GET" and path == "/health":
            return 200, {"ok": True, "env_family": self.env.env_family, "runtime": "python", "sessions": len(self.rollouts)}
        if method == "GET" and path == "/info":
            return 200, {"env_family": self.env.env_family, "runtime": "python", "capabilities": ["rollout", "checkpoint", "nev_log", "symbolic_readout", "render_png", "frame_manifest", "frame_png", "replay_gif"]}
        if method == "GET" and path == "/agents":
            return 200, list(self.env.agent_ids)
        if method == "POST" and path == "/run_scenario":
            return 200, self._run_scenario(body)
        if method == "POST" and path == "/rollouts":
            env, observations, info = self._new_env(body)
            rollout_id = f"rollout-{self._next_rollout}"
            self._next_rollout += 1
            self.rollouts[rollout_id] = env
            capture, render_mode = self._visual_configuration(body)
            self.frames[rollout_id] = {}
            self.capture_frames[rollout_id] = capture
            self.render_modes[rollout_id] = render_mode
            if capture:
                self._store_frame(rollout_id)
            return 200, {
                "rollout_id": rollout_id,
                "observations": observations,
                "info": info,
                "readout": self._readout(env),
                "visual": {
                    "render_url": f"/rollouts/{rollout_id}/render.png",
                    "frame_manifest_url": f"/rollouts/{rollout_id}/frames/manifest",
                    "replay_gif_url": f"/rollouts/{rollout_id}/replay.gif",
                },
            }

        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[0] == "rollouts" and parts[2] == "frames":
            rollout_id, requested = parts[1], parts[3]
            if rollout_id not in self.rollouts:
                return 404, {"error": "rollout_not_found"}
            if method == "GET" and requested == "manifest":
                return 200, self._frame_manifest(rollout_id)
            if method == "GET" and requested.endswith(".png"):
                try:
                    step = int(requested.removesuffix(".png"))
                except ValueError:
                    return 404, {"error": "frame_not_found"}
                current = self.rollouts[rollout_id]._require_state().timestep
                if step == current and step not in self.frames.get(rollout_id, {}):
                    self._store_frame(rollout_id)
                frame = self.frames.get(rollout_id, {}).get(step)
                return (200, MediaPayload("image/png", frame.png())) if frame else (404, {"error": "frame_not_found"})
        if len(parts) == 3 and parts[0] == "rollouts":
            rollout_id, operation = parts[1], parts[2]
            if rollout_id not in self.rollouts:
                return 404, {"error": "rollout_not_found"}
            env = self._require_rollout(rollout_id)
            if method == "GET" and operation == "render.png":
                mode = query.get("render_mode", [self.render_modes.get(rollout_id, "auto")])[0]
                return 200, MediaPayload("image/png", render_rgb(env, mode).png())
            if method == "GET" and operation == "replay.gif":
                if not self.frames.get(rollout_id):
                    self._store_frame(rollout_id)
                raw_limit = query.get("through_step", [None])[0]
                limit = int(raw_limit) if raw_limit is not None else None
                frames = [frame for step, frame in sorted(self.frames[rollout_id].items()) if limit is None or step <= limit]
                return 200, MediaPayload("image/gif", encode_gif(frames, 10))
            if method == "POST" and operation == "step":
                payload = self._step_payload(env, self._joint_action(env, body.get("joint_action")), rollout_id)
                if self.capture_frames.get(rollout_id, False):
                    self._store_frame(rollout_id)
                return 200, payload
            if method in ("GET", "POST") and operation in ("checkpoint", "checkpoints"):
                checkpoint = env.checkpoint()
                return 200, {"rollout_id": rollout_id, "checkpoint": checkpoint, "bytes": len(json.dumps(checkpoint, separators=(",", ":"))), "nev_cursor": len(env._require_state().nev)}
            if method == "POST" and operation == "restore":
                checkpoint = body.get("checkpoint", body)
                if not isinstance(checkpoint, dict):
                    raise TypeError("checkpoint must be an object")
                observations = env.restore(checkpoint)
                timestep = env._require_state().timestep
                self.frames[rollout_id] = {
                    step: frame
                    for step, frame in self.frames.get(rollout_id, {}).items()
                    if step <= timestep
                }
                if self.capture_frames.get(rollout_id, False):
                    self._store_frame(rollout_id)
                return 200, {"rollout_id": rollout_id, "observations": observations, "readout": self._readout(env)}
            if method == "GET" and operation in ("readout", "state"):
                return 200, {"rollout_id": rollout_id, **self._readout(env)}
            if method == "GET" and operation in ("nev", "event_log", "events"):
                return 200, self._nev(env, rollout_id)

        if method == "POST" and path == "/reset":
            self.env, observations, info = self._new_env(body)
            return 200, {"observations": observations, "info": info}
        if method == "POST" and path == "/step":
            return 200, self._step_payload(self.env, self._joint_action(self.env, body.get("joint_action")))
        if method == "GET" and path == "/checkpoint":
            return 200, self.env.checkpoint()
        if method == "POST" and path == "/restore":
            return 200, {"observations": self.env.restore(body)}
        if method == "GET" and path == "/nev":
            return 200, self._nev(self.env)
        return 404, {"error": "not_found"}


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    service = CraftaxService()

    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                target = urlsplit(self.path)
                status, payload = service.handle(self.command, target.path, json.loads(raw), parse_qs(target.query))
            except (KeyError, OSError, TypeError, ValueError, RuntimeError) as exc:
                status, payload = 400, {"error": type(exc).__name__, "message": str(exc)}
            if isinstance(payload, MediaPayload):
                encoded = payload.body
                content_type = payload.content_type
            else:
                encoded = json.dumps(payload, separators=(",", ":")).encode()
                content_type = "application/json"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        do_GET = do_POST = _dispatch

        def log_message(self, format: str, *args: object) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()
