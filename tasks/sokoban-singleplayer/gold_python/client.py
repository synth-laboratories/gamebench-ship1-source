"""Small HTTP client for Sokoban gold services."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class SokobanGoldClient:
    base_url: str
    timeout: float = 60.0

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def create_rollout(self, task: dict[str, Any], *, seed: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"task": task}
        if seed is not None:
            body["seed"] = seed
        return self._post("/rollouts", body)

    def step(self, rollout_id: str, action: str) -> dict[str, Any]:
        return self._post(f"/rollouts/{rollout_id}/step", {"action": action})

    def checkpoint(self, rollout_id: str) -> dict[str, Any]:
        return self._post(f"/rollouts/{rollout_id}/checkpoint", {})

    def restore(self, rollout_id: str, blob: bytes) -> dict[str, Any]:
        return self._post(f"/rollouts/{rollout_id}/restore", {"blob": base64.b64encode(blob).decode("ascii")})

    def simulate(self, rollout_id: str, blob: bytes, sequences: list[list[str]]) -> dict[str, Any]:
        return self._post(
            f"/rollouts/{rollout_id}/simulate",
            {"blob": base64.b64encode(blob).decode("ascii"), "sequences": sequences},
        )

    def readout(self, rollout_id: str) -> dict[str, Any]:
        return self._get(f"/rollouts/{rollout_id}/readout")

    def event_log(self, rollout_id: str) -> dict[str, Any]:
        return self._get(f"/rollouts/{rollout_id}/event_log")

    def _get(self, path: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url.rstrip('/')}{path}")
            response.raise_for_status()
            return response.json()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url.rstrip('/')}{path}", json=body)
            response.raise_for_status()
            return response.json()
