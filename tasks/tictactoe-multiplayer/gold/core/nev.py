"""NEV log — in-game narrative/event log."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    ACTION_APPLIED = "action_applied"
    STATE_TRANSITION = "state_transition"
    RULE_VIOLATION = "rule_violation"
    ACHIEVEMENT = "achievement"
    RESOURCE_DELTA = "resource_delta"
    ENTITY_SPAWN = "entity_spawn"
    ENTITY_DESPAWN = "entity_despawn"
    TERMINAL = "terminal"
    DEBUG = "debug"


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
    action: dict[str, Any] | None = None
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


@dataclass
class NevLog:
    """Append-only in-sim event log."""

    events: list[EventRecord] = field(default_factory=list)

    def cursor(self) -> int:
        return len(self.events)

    def append(self, record: EventRecord) -> None:
        self.events.append(record)

    def tail(self, count: int) -> list[EventRecord]:
        if count <= 0:
            return []
        return self.events[-count:]

    def export(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def legacy_strings(self) -> list[str]:
        return [event.message for event in self.events]

    def diff_messages(self, other_messages: list[str]) -> str:
        left = self.legacy_strings()
        lines: list[str] = []
        max_len = max(len(left), len(other_messages))
        for index in range(max_len):
            expected = other_messages[index] if index < len(other_messages) else None
            actual = left[index] if index < len(left) else None
            if expected != actual:
                lines.append(f"  [{index}] expected={expected!r} actual={actual!r}")
        if not lines:
            return "NEV logs match"
        return "NEV diff:\n" + "\n".join(lines)
