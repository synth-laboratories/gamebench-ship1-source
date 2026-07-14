"""Structured NEV log for synthetic Earthborne Rangers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    TASK_RESOLVED = "task_resolved"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    DECK_SELECTED = "deck_selected"
    CARD_DRAWN = "card_drawn"
    CARD_PLAYED = "card_played"
    TEST_RESOLVED = "test_resolved"
    FATIGUE_TAKEN = "fatigue_taken"
    FATIGUE_RECOVERED = "fatigue_recovered"
    LOCATION_CHANGED = "location_changed"
    OBJECTIVE_PROGRESS = "objective_progress"
    OBJECTIVE_COMPLETED = "objective_completed"
    DAY_ENDED = "day_ended"
    CAMPAIGN_SEGMENT_COMPLETED = "campaign_segment_completed"
    STRATEGY_NOTE_WRITTEN = "strategy_note_written"
    REFLECTION_EXPOSED = "reflection_exposed"
    RULE_VIOLATION = "rule_violation"
    TERMINAL = "terminal"
    CHECKPOINT = "checkpoint"
    CAMPAIGN_SETUP = "campaign_setup"
    DAY_STARTED = "day_started"
    MISSION_STATE_CHANGED = "mission_state_changed"
    REWARD_ADDED = "reward_added"
    CARD_DISCARDED = "card_discarded"
    FATIGUE_SOOTHED = "fatigue_soothed"
    INJURY_TAKEN = "injury_taken"
    MALADY_ADDED = "malady_added"
    DECK_EXHAUSTED = "deck_exhausted"
    ENERGY_SPENT = "energy_spent"
    CARD_COMMITTED = "card_committed"
    CHALLENGE_REVEALED = "challenge_revealed"
    CHALLENGE_EFFECT_RESOLVED = "challenge_effect_resolved"
    CARD_EXHAUSTED = "card_exhausted"
    CARD_READIED = "card_readied"
    PATH_DECK_BUILT = "path_deck_built"
    PATH_CARD_REVEALED = "path_card_revealed"
    PATH_CARD_PLACED = "path_card_placed"
    RANGE_CHECKED = "range_checked"
    OBSTACLE_BLOCKED = "obstacle_blocked"
    WORLD_CARD_ENTERED = "world_card_entered"
    PROGRESS_ADDED = "progress_added"
    HARM_ADDED = "harm_added"
    PRESENCE_CHANGED = "presence_changed"
    ATTACHMENT_ADDED = "attachment_added"
    CARD_CLEARED = "card_cleared"
    KEYWORD_RESOLVED = "keyword_resolved"
    ROUND_STARTED = "round_started"
    RANGER_RESTED = "ranger_rested"
    ROUND_ENDED = "round_ended"
    TRAVEL_AVAILABLE = "travel_available"
    TRAVEL_COMPLETED = "travel_completed"
    REFRESH_COMPLETED = "refresh_completed"
    TRIGGER_QUEUED = "trigger_queued"
    EFFECT_RESOLVED = "effect_resolved"
    REPLACEMENT_APPLIED = "replacement_applied"
    CHOICE_PRESENTED = "choice_presented"
    CHOICE_RESOLVED = "choice_resolved"
    ACTIVE_RANGER_CHANGED = "active_ranger_changed"
    ASSIST_COMMITTED = "assist_committed"
    RANGER_AREA_CHANGED = "ranger_area_changed"
    SCORE_SUMMARY_EMITTED = "score_summary_emitted"
    ATTEMPT_COMPLETED = "attempt_completed"


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventRecord":
        return cls(
            step_index=int(data["step_index"]),
            sim_tick=int(data.get("sim_tick", data["step_index"])),
            episode_id=str(data["episode_id"]),
            kind=EventKind(data["kind"]),
            severity=EventSeverity(data.get("severity", "info")),
            message=str(data["message"]),
            action=data.get("action"),
            transition=data.get("transition"),
            payload=dict(data.get("payload") or {}),
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
