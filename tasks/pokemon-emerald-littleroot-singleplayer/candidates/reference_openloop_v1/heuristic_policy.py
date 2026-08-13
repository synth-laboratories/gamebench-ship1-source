"""Open-loop reference tape: short scripted holds per checkpoint family."""

from __future__ import annotations

from typing import Any


_TAPES: dict[str, list[dict[str, Any]]] = {
    "bedroom_idle": [
        {"action": "down", "frames": 16},
        {"action": "down", "frames": 16},
        {"action": "right", "frames": 16},
        {"action": "right", "frames": 16},
        {"action": "down", "frames": 16},
        {"action": "a", "frames": 1},
    ],
    "rival_outside_lab": [
        {"action": "up", "frames": 16},
        {"action": "right", "frames": 16},
        {"action": "down", "frames": 16},
        {"action": "left", "frames": 16},
        {"action": "a", "frames": 1},
    ],
    "birch_lab_exterior": [
        {"action": "down", "frames": 16},
        {"action": "left", "frames": 16},
        {"action": "right", "frames": 16},
        {"action": "a", "frames": 1},
    ],
    "truck_arrival": [
        {"action": "right", "frames": 16},
        {"action": "right", "frames": 16},
        {"action": "a", "frames": 1},
    ],
}


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    checkpoint = str(readout.get("checkpoint") or "bedroom_idle")
    tape = _TAPES.get(checkpoint) or _TAPES["bedroom_idle"]
    step = tape[min(ply, len(tape) - 1)]
    return {"actions": [step], "policy_reason": f"tape:{checkpoint}:{ply}"}
