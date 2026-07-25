"""Dependency-free local HTTP service for the Python gold lane."""

from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .engine import TowerMindEnv


class TowerMindService:
    def __init__(self) -> None:
        self.sessions: dict[str, TowerMindEnv] = {}

    def reset(self, body: dict[str, Any]) -> dict[str, Any]:
        env = TowerMindEnv()
        observation = env.reset(str(body.get("level", "L1")), seed=int(body.get("seed", 0)), initial_gold=int(body.get("initial_gold", 0)))
        rollout_id = str(uuid.uuid4())
        self.sessions[rollout_id] = env
        return {"rollout_id": rollout_id, "observation": observation, "nev_cursor": len(env.events)}

    def step(self, rollout_id: str, body: dict[str, Any]) -> dict[str, Any]:
        env = self.sessions[rollout_id]
        return {"rollout_id": rollout_id, **env.step(body.get("action", {}))}

    def checkpoint(self, rollout_id: str) -> dict[str, Any]:
        env = self.sessions[rollout_id]
        return {"rollout_id": rollout_id, "checkpoint": env.checkpoint(), "nev_cursor": len(env.events)}

    def restore(self, rollout_id: str, body: dict[str, Any]) -> dict[str, Any]:
        env = self.sessions[rollout_id]
        return {"rollout_id": rollout_id, "observation": env.restore(body["checkpoint"]), "nev_cursor": len(env.events)}


def serve(host: str = "127.0.0.1", port: int = 8094) -> None:
    service = TowerMindService()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - stdlib callback spelling
            if self.path == "/health":
                self._reply(200, {"ok": True, "lane": "python", "env_family": TowerMindEnv.ENV_FAMILY, "sessions": len(service.sessions)})
                return
            self._reply(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback spelling
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size) or b"{}")
                parts = [part for part in self.path.split("/") if part]
                if parts == ["rollouts"]:
                    self._reply(200, service.reset(body))
                elif len(parts) == 3 and parts[0] == "rollouts" and parts[2] == "step":
                    self._reply(200, service.step(parts[1], body))
                elif len(parts) == 3 and parts[0] == "rollouts" and parts[2] == "checkpoint":
                    self._reply(200, service.checkpoint(parts[1]))
                elif len(parts) == 3 and parts[0] == "rollouts" and parts[2] == "restore":
                    self._reply(200, service.restore(parts[1], body))
                else:
                    self._reply(404, {"error": "not found"})
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                self._reply(400, {"error": str(error)})

        def log_message(self, _format: str, *_args: object) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()
