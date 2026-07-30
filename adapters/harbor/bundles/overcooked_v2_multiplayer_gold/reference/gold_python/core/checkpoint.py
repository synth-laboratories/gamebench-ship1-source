"""Checkpoint helpers for Overcooked v2 symbolic gold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RestoreReport:
    bytes: int
    wall_ms: float
    nev_events_restored: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bytes": self.bytes,
            "wall_ms": self.wall_ms,
            "nev_events_restored": self.nev_events_restored,
        }
