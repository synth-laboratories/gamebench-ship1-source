"""Checkpoint helpers for Rogue."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RestoreReport:
    bytes: int
    wall_ms: float
    nev_events_restored: int

    def to_dict(self) -> dict[str, float | int]:
        return {"bytes": self.bytes, "wall_ms": self.wall_ms, "nev_events_restored": self.nev_events_restored}
