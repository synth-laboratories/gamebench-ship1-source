"""Programmatic scoring for Rogue GameBench episodes."""

from __future__ import annotations

from typing import Any


def binary_success_score(private: dict[str, Any], objective: str) -> float:
    if objective == "descend":
        return 1.0 if int(private.get("dungeon_level", 1)) > 1 else 0.0
    if objective == "collect_gold":
        return 1.0 if int(private.get("purse", 0)) > 0 else 0.0
    return 1.0 if private.get("terminated") and private.get("terminal_reason") == "success" else 0.0
