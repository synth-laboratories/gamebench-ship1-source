"""Convention-aware Hanabi baseline using only the acting player's observation."""

from __future__ import annotations

from typing import Any


def act(observation: dict[str, Any]) -> dict[str, Any]:
    fireworks = observation["fireworks"]
    for card in observation["own_hand"]:
        known = card["knowledge"]
        if known["color"] is not None and known["rank"] is not None:
            if fireworks[known["color"]] + 1 == known["rank"]:
                return {"kind": "play", "slot": card["slot"]}
    if observation["information_tokens"] > 0:
        for card in observation["partner_hand"]:
            if fireworks[card["color"]] + 1 != card["rank"]:
                continue
            known = card["knowledge"]
            if known["rank"] != card["rank"]:
                return {"kind": "hint", "rank": card["rank"]}
            if known["color"] != card["color"]:
                return {"kind": "hint", "color": card["color"]}
    if observation["information_tokens"] < 8:
        for card in observation["own_hand"]:
            known = card["knowledge"]
            if known["color"] is not None and known["rank"] is not None:
                if known["rank"] <= fireworks[known["color"]]:
                    return {"kind": "discard", "slot": card["slot"]}
        return {"kind": "discard", "slot": 0}
    partner = observation["partner_hand"][0]
    return {"kind": "hint", "color": partner["color"]}
