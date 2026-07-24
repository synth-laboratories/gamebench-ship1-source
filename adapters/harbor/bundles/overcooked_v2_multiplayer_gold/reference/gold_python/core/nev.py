"""NEV log for Overcooked v2 symbolic MARL gold."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventRecord:
    step_index: int
    tick: int
    episode_id: str
    kind: str
    message: str
    action: dict[str, Any] | None = None
    transition: str | None = None
    severity: str = "info"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "tick": self.tick,
            "episode_id": self.episode_id,
            "kind": self.kind,
            "action": self.action,
            "transition": self.transition,
            "severity": self.severity,
            "message": self.message,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventRecord":
        return cls(
            step_index=int(data["step_index"]),
            tick=int(data["tick"]),
            episode_id=str(data["episode_id"]),
            kind=str(data["kind"]),
            message=str(data["message"]),
            action=data.get("action"),
            transition=data.get("transition"),
            severity=str(data.get("severity", "info")),
            payload=dict(data.get("payload", {})),
        )


@dataclass
class NevLog:
    events: list[EventRecord] = field(default_factory=list)

    def append(
        self,
        *,
        step_index: int,
        episode_id: str,
        kind: str,
        message: str,
        action: dict[str, Any] | None = None,
        transition: str | None = None,
        severity: str = "info",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            EventRecord(
                step_index=step_index,
                tick=step_index,
                episode_id=episode_id,
                kind=kind,
                message=message,
                action=action,
                transition=transition,
                severity=severity,
                payload=payload or {},
            )
        )

    def cursor(self) -> int:
        return len(self.events)

    def export(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def legacy_strings(self) -> list[str]:
        return [event.message for event in self.events]

    @classmethod
    def from_export(cls, events: list[dict[str, Any]]) -> "NevLog":
        return cls(events=[EventRecord.from_dict(item) for item in events])
