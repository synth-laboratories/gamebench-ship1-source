"""Structured GameBench NEV log."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NevLog:
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        *,
        step_index: int,
        episode_id: str,
        kind: str,
        message: str,
        action: str | None = None,
        transition: str | None = None,
        severity: str = "info",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "step_index": int(step_index),
                "tick": int(step_index),
                "episode_id": episode_id,
                "kind": kind,
                "action": action,
                "transition": transition,
                "severity": severity,
                "message": message,
                "payload": deepcopy(payload or {}),
            }
        )

    def cursor(self) -> int:
        return len(self.events)

    def export(self) -> list[dict[str, Any]]:
        return deepcopy(self.events)

    def legacy_strings(self) -> list[str]:
        return [str(event["message"]) for event in self.events]

    @classmethod
    def from_export(cls, payload: list[dict[str, Any]]) -> "NevLog":
        return cls(events=deepcopy(payload))
