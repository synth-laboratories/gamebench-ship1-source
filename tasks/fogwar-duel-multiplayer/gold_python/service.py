"""JSON-lines service for the Python Fog Duel Lite authority."""

from __future__ import annotations

import json
import sys
from typing import Any

from .engine import FogDuelEnv


def handle(env: FogDuelEnv, request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    if op == "reset":
        return {"ok": True, "observation": env.reset(str(request["scenario_id"]))}
    if op == "step":
        return {"ok": True, **env.step(dict(request.get("input", {})))}
    if op == "observe":
        return {"ok": True, "observation": env.observe(request.get("agent"))}
    if op == "state":
        return {"ok": True, "state": env.state_projection(), "nev": env.events}
    if op == "checkpoint":
        return {"ok": True, "checkpoint": env.checkpoint()}
    if op == "restore":
        return {"ok": True, "observation": env.restore(dict(request["checkpoint"]))}
    return {"ok": False, "error": "unknown_op"}


def serve() -> None:
    env = FogDuelEnv()
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            response = handle(env, request)
        except Exception as exc:  # A JSON-lines service reports errors without killing later requests.
            response = {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        print(json.dumps(response, sort_keys=True), flush=True)


if __name__ == "__main__":
    serve()
