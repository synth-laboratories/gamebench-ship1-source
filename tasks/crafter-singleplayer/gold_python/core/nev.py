"""Crafter NEV log."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    TASK_RESOLVED = "task_resolved"
    ACTION_APPLIED = "action_applied"
    ACTION_REJECTED = "action_rejected"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    RULE_VIOLATION = "rule_violation"
    RESOURCE_DELTA = "resource_delta"
    REWARD_DELTA = "reward_delta"
    HEALTH_DELTA = "health_delta"
    ENTITY_TRANSITION = "entity_transition"
    STATE_TRANSITION = "state_transition"
    CHECKPOINT = "checkpoint"
    DEATH = "death"
    EPISODE_TRUNCATED = "episode_truncated"
    TERMINAL = "terminal"


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
    cursor_offset: int = 0

    def cursor(self) -> int:
        return self.cursor_offset + len(self.events)

    def append(self, record: EventRecord) -> EventRecord:
        self.events.append(record)
        return record

    def export(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def export_tail(self, limit: int) -> list[dict[str, Any]]:
        limit = max(0, int(limit))
        if limit <= 0:
            return []
        return [event.to_dict() for event in self.events[-limit:]]

    def summarize(self) -> dict[str, Any]:
        event_kind_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        transition_counts: dict[str, int] = {}
        reward_source_totals: dict[str, float] = {}
        reward_component_totals: dict[str, float] = {}
        terminal: dict[str, Any] | None = None

        for event in self.events:
            kind = event.kind.value
            event_kind_counts[kind] = event_kind_counts.get(kind, 0) + 1
            severity = event.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            if event.action:
                action_counts[event.action] = action_counts.get(event.action, 0) + 1
            if isinstance(event.transition, dict):
                for key in event.transition:
                    transition_counts[str(key)] = transition_counts.get(str(key), 0) + 1
            payload = event.payload
            if kind == EventKind.REWARD_DELTA.value:
                delta = float(payload.get("delta", 0.0))
                source = str(payload.get("source", "unknown"))
                component = str(payload.get("component", source))
                reward_source_totals[source] = reward_source_totals.get(source, 0.0) + delta
                reward_component_totals[component] = reward_component_totals.get(component, 0.0) + delta
            if kind == EventKind.TERMINAL.value:
                terminal = {
                    "step_index": int(event.step_index),
                    "reason": payload.get("reason"),
                }

        return {
            "schema": "gamebench.crafter.event_summary.v1",
            "event_count": len(self.events),
            "nev_cursor": self.cursor(),
            "first_step_index": int(self.events[0].step_index) if self.events else None,
            "last_step_index": int(self.events[-1].step_index) if self.events else None,
            "event_kind_counts": dict(sorted(event_kind_counts.items())),
            "severity_counts": dict(sorted(severity_counts.items())),
            "action_counts": dict(sorted(action_counts.items())),
            "transition_counts": dict(sorted(transition_counts.items())),
            "reward_source_totals": {key: float(value) for key, value in sorted(reward_source_totals.items())},
            "reward_component_totals": {key: float(value) for key, value in sorted(reward_component_totals.items())},
            "terminal": terminal,
        }

    def import_events(self, events: list[dict[str, Any]], *, cursor_offset: int = 0) -> None:
        self.events = [EventRecord.from_dict(event) for event in events]
        self.cursor_offset = max(0, int(cursor_offset))

    def legacy_strings(self) -> list[str]:
        return [event.message for event in self.events]

    def legacy_tail(self, limit: int) -> list[str]:
        limit = max(0, int(limit))
        if limit <= 0:
            return []
        return [event.message for event in self.events[-limit:]]
