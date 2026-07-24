"""HTTP gold-lane rollout adapter for Crafter code-policy sweeps."""

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
    scenario_id: str
    seed: int
    config_hash: str
    step_index: int
    total_reward: float
    terminated: bool
    truncated: bool
    done_reason: str
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

    def simulate(self, sequences: list[list[str]]) -> list[dict[str, Any]]:
        """Batch-evaluate open-loop action sequences from the current state.

        Routes to the rust ``/rollouts/:id/simulate`` endpoint: one round-trip
        replays every sequence natively from the current checkpoint and returns
        each one's final achievements + reward. Leaf-evaluation primitive for
        search / MCTS code policies; mirrors ``CrafterEngine.simulate``.
        """
        return self._client.simulate(sequences)

    @property
    def private(self) -> _PrivateState:
        return self._client.private

    @property
    def nev(self) -> Any:
        return self._client


class HttpRolloutEngine:
    """Step a Crafter rollout through the rust (or python) gold HTTP service."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.rollout_id = ""
        self._readout: dict[str, Any] = {}
        self._last_task: dict[str, Any] = {}
        self._last_seed: int | None = None
        self.private = _PrivateState("", "", "", 0, "", 0, 0.0, False, False, "", [])

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
        self._sync({"readout": payload.get("readout", {}), **payload})
        report = dict(payload.get("restore_report") or {})
        return int(report.get("nev_events_restored", 0))

    def clone_for_sim(self) -> HttpSimEngine:
        return HttpSimEngine(self)

    def simulate(self, sequences: list[list[str]]) -> list[dict[str, Any]]:
        blob = base64.b64encode(self.checkpoint_bytes()).decode("ascii")
        payload = self._request(
            "POST",
            f"/rollouts/{self.rollout_id}/simulate",
            {"blob": blob, "sequences": [list(seq) for seq in sequences]},
        )
        results: list[dict[str, Any]] = []
        for item in payload.get("results") or []:
            readout = dict(item.get("readout") or {})
            observation = dict(readout.get("observation") or {})
            raw_achievements = observation.get("achievements") or {}
            if isinstance(raw_achievements, dict):
                unlocked = sorted(name for name, count in raw_achievements.items() if int(count) > 0)
            else:
                unlocked = sorted(str(name) for name in raw_achievements)
            results.append(
                {
                    "index": int(item.get("index", len(results))),
                    "actions": list(item.get("actions") or []),
                    "achievements": unlocked,
                    "achievement_unlock_steps": {
                        str(name): int(step)
                        for name, step in (item.get("achievement_unlock_steps") or {}).items()
                    },
                    "reward": float(item.get("reward", 0.0)),
                    "reward_trace": [float(r) for r in (item.get("reward_trace") or [])],
                    "terminated": bool(item.get("terminated", False)),
                    "truncated": bool(item.get("truncated", False)),
                    "steps": int(item.get("steps", len(item.get("actions") or []))),
                }
            )
        results.sort(key=lambda record: record["index"])
        return results

    def _sync(self, payload: dict[str, Any]) -> None:
        readout = dict(payload.get("readout") or {})
        self._readout = readout
        private = dict(readout.get("private") or payload.get("private") or {})
        public = dict(readout.get("public") or {})
        self.private = _PrivateState(
            episode_id=str(private.get("episode_id") or self.rollout_id),
            task_id=str(private.get("task_id") or ""),
            scenario_id=str(private.get("scenario_id") or ""),
            seed=int(private.get("seed") or self._last_seed or 0),
            config_hash=str(private.get("config_hash") or ""),
            step_index=int(private.get("step_index") or 0),
            total_reward=float(payload.get("reward", private.get("total_reward", 0.0))),
            terminated=bool(payload.get("terminated", private.get("terminated", public.get("done", False)))),
            truncated=bool(payload.get("truncated", private.get("truncated", False))),
            done_reason=str(private.get("done_reason") or ""),
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
