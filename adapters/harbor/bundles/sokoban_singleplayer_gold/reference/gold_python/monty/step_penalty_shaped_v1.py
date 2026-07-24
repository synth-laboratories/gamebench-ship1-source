"""Shaped reward for pushes vs idle steps."""

from __future__ import annotations

from typing import Any


def score_transition(
    *,
    spec: dict[str, Any],
    event: str,
    pushed: bool = False,
    **_: Any,
) -> float:
    if event == "level_complete":
        return 0.0
    if pushed:
        return float(spec.get("push_bonus", 0.02))
    return float(spec.get("idle_penalty", -0.005))
