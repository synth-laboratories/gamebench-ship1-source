#!/usr/bin/env python3
"""Small standard-library HTTP contract and all-level smoke test."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


BASE = f"http://127.0.0.1:{os.environ.get('GAMEBENCH_CANDIDATE_PORT', '19099')}"


def request(path: str, payload: dict | None = None) -> tuple[dict | bytes, str]:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        body = response.read()
        content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        return json.loads(body), content_type
    return body, content_type


def main() -> int:
    health, _ = request("/health")
    assert health["ok"] is True and health["catalog_levels"] == 32
    info, _ = request("/info")
    assert "checkpoint" in info["capabilities"]

    handles = []
    for world in range(1, 9):
        for level in range(1, 5):
            response, _ = request("/rollouts", {"task": {"level_id": f"{world}-{level}"}, "seed": 17})
            assert response["readout"]["level_id"] == f"{world}-{level}"
            handles.append(response["rollout_id"])
    rollout = handles[0]
    checkpoint, _ = request(f"/rollouts/{rollout}/checkpoint", {})
    assert checkpoint["bytes"] > 0
    step, _ = request(f"/rollouts/{rollout}/step", {"action": "right_jump_run"})
    assert "progress" in step["step"] and "events" in step["step"]
    request(f"/rollouts/{rollout}/restore", {"blob": checkpoint["blob"]})
    simulated, _ = request(f"/rollouts/{rollout}/simulate", {"blob": checkpoint["blob"], "sequences": [["right"], ["right_jump_run", "neutral"]]})
    assert len(simulated["results"]) == 2
    event_log, _ = request(f"/rollouts/{rollout}/event_log")
    assert event_log["nev_cursor"] >= 1
    rgb, _ = request(f"/rollouts/{rollout}/render.rgb")
    assert rgb["width"] == 256 and rgb["height"] == 240 and len(rgb["data"]) > 100
    png, content_type = request(f"/rollouts/{rollout}/render.png")
    assert content_type.startswith("image/png") and png[:8] == b"\x89PNG\r\n\x1a\n"
    scenario, _ = request("/run_scenario", {"task": {"level_id": "8-4", "actions": ["right_run"] * 8}})
    assert scenario["readout"]["level_id"] == "8-4"
    print("super-mario-bros protocol smoke: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, urllib.error.URLError, TimeoutError) as exc:
        print(f"protocol smoke failed: {exc}", file=sys.stderr)
        raise
