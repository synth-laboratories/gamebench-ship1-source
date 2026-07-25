"""Hidden flawed policy — submits before board is complete."""

from __future__ import annotations

from typing import Any


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[dict[str, Any]],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    del observation_text, engine, seed, ply, valid_actions
    public = readout["public"]
    placed = len(public.get("frogs", []))
    if placed >= 2:
        return {"actions": [{"kind": "submit"}], "policy_reason": "early submit rusher"}
    return {
        "actions": [{"kind": "place_frog", "row": 0, "col": placed}],
        "policy_reason": "place before early submit",
    }
