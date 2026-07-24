"""HTTP gold-lane rollout adapter for dual-lane code-policy sweeps."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin


@dataclass
class _PrivateState:
    episode_id: str
    task_id: str
    puzzle_id: str
    seed: int
    step_index: int
    total_reward: float
    terminated: bool
    truncated: bool
    achievements: list[str]


class HttpSimEngine:
    """In-memory sim branch backed by an isolated HTTP rollout."""

    def __init__(self, client: HttpRolloutEngine) -> None:
        self._client = client.fork_sim()

    def checkpoint_bytes(self) -> bytes:
        return self._client.checkpoint_bytes()

    def restore_checkpoint(self, blob: bytes) -> int:
        return self._client.restore_checkpoint(blob)

    def step(self, action: str) -> None:
        self._client.step(action)

    def valid_actions(self) -> list[str]:
        return self._client.valid_actions()

    @property
    def private(self) -> _PrivateState:
        return self._client.private

    @property
    def nev(self) -> Any:
        return self._client


class HttpRolloutEngine:
    """Step a Sokoban rollout through a python or rust gold HTTP service."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.rollout_id = ""
        self._readout: dict[str, Any] = {}
        self._last_task: dict[str, Any] = {}
        self._last_seed: int | None = None
        self.private = _PrivateState("", "", "", 0, 0, 0.0, False, False, [])

    def reset(self, task: dict[str, Any], *, seed: int | None = None) -> None:
        self._last_task = dict(task)
        self._last_seed = seed
        payload = self._request("POST", "/rollouts", {"task": task, "seed": seed})
        self.rollout_id = str(payload["rollout_id"])
        self._sync(payload)

    def fork_sim(self) -> HttpRolloutEngine:
        fork = HttpRolloutEngine(self.base_url)
        fork.reset(self._last_task, seed=self._last_seed)
        fork.restore_checkpoint(self.checkpoint_bytes())
        return fork

    def symbolic_readout(self) -> dict[str, Any]:
        payload = self._request("GET", f"/rollouts/{self.rollout_id}/readout")
        self._readout = dict(payload)
        return dict(payload)

    def valid_actions(self) -> list[str]:
        readout = self.symbolic_readout()
        return list(readout.get("valid_actions") or [])

    def step(self, action: str) -> None:
        payload = self._request("POST", f"/rollouts/{self.rollout_id}/step", {"action": action})
        self._sync(payload)

    def checkpoint_bytes(self) -> bytes:
        payload = self._request("POST", f"/rollouts/{self.rollout_id}/checkpoint")
        return base64.b64decode(str(payload["blob"]).encode("ascii"))

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = self._request(
            "POST",
            f"/rollouts/{self.rollout_id}/restore",
            {"blob": base64.b64encode(blob).decode("ascii")},
        )
        self._sync({"readout": payload.get("readout", {})})
        report = dict(payload.get("restore_report") or {})
        return int(report.get("nev_events_restored", 0))

    def clone_for_sim(self) -> HttpSimEngine:
        return HttpSimEngine(self)

    def _sync(self, payload: dict[str, Any]) -> None:
        readout = dict(payload.get("readout") or {})
        self._readout = readout
        private = dict(readout.get("private") or {})
        public = dict(readout.get("public") or {})
        self.private = _PrivateState(
            episode_id=str(private.get("episode_id") or self.rollout_id),
            task_id=str(private.get("task_id") or ""),
            puzzle_id=str(private.get("puzzle_id") or ""),
            seed=int(private.get("seed") or 0),
            step_index=int(private.get("step_index") or 0),
            total_reward=float(payload.get("reward", private.get("total_reward", 0.0))),
            terminated=bool(payload.get("terminated", private.get("terminated", public.get("done", False)))),
            truncated=bool(payload.get("truncated", private.get("truncated", False))),
            achievements=[str(item) for item in private.get("achievements") or []],
        )

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"content-type": "application/json"} if data is not None else {}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {method} {path}: {body}") from exc
