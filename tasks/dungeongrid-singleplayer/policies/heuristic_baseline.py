from __future__ import annotations

from typing import Any


def plan_actions(scenario: dict[str, Any], objective: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Weak scout baseline: a few safe steps only.

    Intentionally unsaturated so code-policy hillclimb has room to climb on the
    unbounded composite (gold / achievements / armor / spells / steps).
    """

    _ = scenario, objective
    return [
        {"type": "message", "target": "party", "payload": {"text": "DG|SCOUT"}},
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
        {"type": "guard"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
    ]
