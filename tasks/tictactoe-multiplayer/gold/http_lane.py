"""HTTP eval lane — joint-step multiplayer container."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from gold.monty import public_dict_from_engine, resolve_policy


DEFAULT_HTTP_URL = "http://127.0.0.1:18082"
DEFAULT_CANDIDATE_PORT = 18082


@dataclass
class HttpRequestTiming:
    path: str
    elapsed_ms: float


class HttpLaneClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.timings: list[HttpRequestTiming] = []

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["content-type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()
            raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.timings.append(HttpRequestTiming(path=path, elapsed_ms=elapsed_ms))
        return body

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def health(self) -> dict[str, Any]:
        return self.get("/health")

    def run_scenario(self, task: dict[str, Any]) -> dict[str, Any]:
        return self.post("/run_scenario", {"task": task})

    def reset(self, scenario_id: str, seed: int, task_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"scenario_id": scenario_id, "seed": seed}
        if task_id is not None:
            payload["task_id"] = task_id
        return self.post("/reset", payload)

    def step_joint(self, rollout_id: str, joint_action: dict[str, Any]) -> dict[str, Any]:
        return self.post(
            f"/rollouts/{rollout_id}/step",
            {"joint_action": joint_action, "observation_profile": "llm_text"},
        )

    def events(self, rollout_id: str) -> dict[str, Any]:
        return self.get(f"/rollouts/{rollout_id}/events")

    def save_checkpoint(self, rollout_id: str) -> dict[str, Any]:
        return self.post(f"/rollouts/{rollout_id}/checkpoints", {})

    def export_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        return self.get(f"/checkpoints/{checkpoint_id}/export")

    def import_checkpoint(self, checkpoint_id: str, blob_b64: str) -> dict[str, Any]:
        return self.post("/checkpoints/import", {"checkpoint_id": checkpoint_id, "blob": blob_b64})


def wait_for_health(base_url: str, proc: subprocess.Popen[Any], timeout_s: float = 15.0) -> None:
    client = HttpLaneClient(base_url)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("HTTP candidate process exited before becoming healthy")
        try:
            payload = client.health()
            if payload.get("ok") and payload.get("engine") == "tictactoe-multiplayer-gold":
                return
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            time.sleep(0.1)
    raise RuntimeError(f"HTTP candidate at {base_url} did not become healthy")


def spawn_candidate_server(task_dir: str, port: int) -> subprocess.Popen[Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = task_dir
    env["GAMEBENCH_TTT_HOST"] = "127.0.0.1"
    env["GAMEBENCH_TTT_PORT"] = str(port)
    run_service = os.path.join(task_dir, "scripts", "run_service.py")
    proc = subprocess.Popen(
        [sys.executable, run_service],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_health(f"http://127.0.0.1:{port}", proc)
    return proc


def collect_joint_actions_http(
    client: HttpLaneClient,
    rollout_id: str,
    task: dict[str, Any],
) -> list[dict[str, Any]]:
    from gold.engine import AGENT_IDS, WAIT_ACTION
    from gold.scenarios import _policy_spec

    seed = int(task.get("seed", 0))
    policies = {
        agent_id: resolve_policy(_policy_spec(task, agent_id), agent_id) for agent_id in AGENT_IDS
    }
    joint_actions: list[dict[str, Any]] = []
    state = client.get(f"/rollouts/{rollout_id}/state")
    ply = 0
    while not state["private"]["terminated"]:
        current = state["public"]["current_agent"]
        joint = {agent_id: dict(WAIT_ACTION) for agent_id in AGENT_IDS}
        public = state["public"]
        joint[current] = policies[current](public, seed, ply)
        joint_actions.append(joint)
        state = client.step_joint(rollout_id, joint)
        ply += 1
    return joint_actions
