"""Sokoban NEV log."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    TASK_RESOLVED = "task_resolved"
    ACTION_APPLIED = "action_applied"
    PUSH_APPLIED = "push_applied"
    PUSH_BLOCKED = "push_blocked"
    RULE_VIOLATION = "rule_violation"
    BOX_ON_TARGET = "box_on_target"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    REWARD_DELTA = "reward_delta"
    LEVEL_COMPLETE = "level_complete"
    EPISODE_TRUNCATED = "episode_truncated"
    TERMINAL = "terminal"
    CHECKPOINT = "checkpoint"


class EventSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class EventRecord:
    step_index: int
    sim_tick: int
    episode_id: str
    kind: EventKind
    severity: EventSeverity
    message: str
    action: str | None = None
    transition: dict[str, Any] | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "sim_tick": self.sim_tick,
            "episode_id": self.episode_id,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "message": self.message,
            "action": self.action,
            "transition": self.transition,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EventRecord":
        return cls(
            step_index=int(payload["step_index"]),
            sim_tick=int(payload["sim_tick"]),
            episode_id=str(payload["episode_id"]),
            kind=EventKind(payload["kind"]),
            severity=EventSeverity(payload["severity"]),
            message=str(payload["message"]),
            action=payload.get("action"),
            transition=payload.get("transition"),
            payload=dict(payload.get("payload", {})),
        )


@dataclass
class NevLog:
    events: list[EventRecord] = field(default_factory=list)

    def cursor(self) -> int:
        return len(self.events)

    def append(self, record: EventRecord) -> EventRecord:
        self.events.append(record)
        return record

    def export(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def import_events(self, events: list[dict[str, Any]]) -> None:
        self.events = [EventRecord.from_dict(event) for event in events]

    def legacy_strings(self) -> list[str]:
        return [event.message for event in self.events]
