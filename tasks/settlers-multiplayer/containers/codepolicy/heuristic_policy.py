"""Conservative reference policy for the Settlers code-policy DEO lane.

The policy receives only the acting player's structured observation.  It is
deliberately modest: it resolves mandatory robber moves but otherwise ends its
turn.  It establishes a reproducible improvement target without assuming
access to the engine or to hidden opponent resources.
"""

from __future__ import annotations

from typing import Any


def act(observation: dict[str, Any]) -> dict[str, Any]:
    """Return one action for the active player.

    Code-policy candidates must export this function with the same
    observation-only contract.
    """

    legal_actions = set(observation.get("legal_actions", []))
    if observation.get("rolled_die") == 7 or "move_robber" in legal_actions:
        return {
            "kind": "move_robber",
            "tile": (int(observation["robber_tile"]) + 1) % 12,
            "victim": "agent_1",
        }
    return {"kind": "end_turn"}
