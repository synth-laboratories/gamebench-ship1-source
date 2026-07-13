from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .engine import CraftaxCoopEnv


class CraftaxService:
    def __init__(self) -> None:
        self.env = CraftaxCoopEnv()

    def handle(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        body = {} if body is None else body
        if method == "GET" and path == "/health": return 200, {"ok": True, "env_family": self.env.env_family, "runtime": "python"}
        if method == "GET" and path == "/agents": return 200, list(self.env.agent_ids)
        if method == "POST" and path == "/reset":
            obs, info = self.env.reset(int(body.get("seed", 0))); return 200, {"observations": obs, "info": info}
        if method == "POST" and path == "/step":
            obs, rewards, dones, info = self.env.step(body["joint_action"]); return 200, {"observations": obs, "rewards": rewards, "dones": dones, "info": info}
        if method == "GET" and path == "/checkpoint": return 200, self.env.checkpoint()
        if method == "POST" and path == "/restore": return 200, {"observations": self.env.restore(body)}
        if method == "GET" and path == "/nev":
            state = self.env._require_state(); return 200, {"structured": state.nev, "legacy": state.legacy_nev}
        return 404, {"error": "not_found"}


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    service = CraftaxService()
    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            length = int(self.headers.get("Content-Length", "0")); raw = self.rfile.read(length) if length else b"{}"
            try: status, payload = service.handle(self.command, self.path, json.loads(raw))
            except (KeyError, TypeError, ValueError, RuntimeError) as exc: status, payload = 400, {"error": type(exc).__name__, "message": str(exc)}
            encoded = json.dumps(payload, separators=(",", ":")).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
        do_GET = do_POST = _dispatch
        def log_message(self, format: str, *args: object) -> None: return
    ThreadingHTTPServer((host, port), Handler).serve_forever()
