"""Shaped reward for box-on-target progress."""

from __future__ import annotations

from typing import Any


def score_transition(
    *,
    spec: dict[str, Any],
    before_public: dict[str, Any],
    after_public: dict[str, Any],
    event: str,
    **_: Any,
) -> float:
    delta = 0.0
    before_count = int(before_public.get("boxes_on_target", 0))
    after_count = int(after_public.get("boxes_on_target", 0))
    if after_count > before_count:
        delta += float(spec.get("box_on_target_bonus", 0.05)) * (after_count - before_count)
    if event == "level_complete":
        delta += float(spec.get("solve_bonus", 0.25))
    return delta
