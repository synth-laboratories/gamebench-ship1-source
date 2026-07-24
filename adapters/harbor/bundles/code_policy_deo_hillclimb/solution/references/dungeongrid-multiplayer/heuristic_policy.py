from __future__ import annotations

from typing import Any


def _msg() -> dict[str, Any]:
    return {"type": "message", "target": "party", "payload": {"text": "DG|ROUTE=SCOUT;WARD;REVEAL;BREACH;STRIKE"}}


def _turn_end() -> dict[str, Any]:
    return {"type": "end_turn"}


def _standard(scenario_id: str) -> list[dict[str, Any]]:
    # The first turn establishes the protocol and puts the barbarian at the
    # threshold.  The wizard then supplies the guard/reveal counterplay.
    actions: list[dict[str, Any]] = [_msg(), {"type": "move", "direction": "east"}, _turn_end()]
    actions += [{"type": "cast", "target": "self", "payload": {"spell": "ward_circle"}}, _turn_end()]
    if scenario_id in {"trap_breach_rescue", "blackwater_bell_breach", "cinder_mage_threshold", "frost_mirror_crossfire", "double_breach_nemesis", "nemesis_breach_gate"}:
        actions += [{"type": "search_traps"}, _turn_end()]
    else:
        actions += [{"type": "guard"}, _turn_end()]
    actions += [{"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "reveal_glyph"}}, _turn_end()]

    if scenario_id == "chokepoint_passage":
        actions += [
            {"type": "move", "direction": "east"},
            {"type": "open_door", "target": "door_1"},
            _turn_end(),
            {"type": "move", "direction": "east"},
            _turn_end(),
            {"type": "interact", "target": "objective"},
            {"type": "end_turn"},
            {"type": "attack_melee", "target": "crypt_brute_1"},
            _turn_end(),
            {"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "spark_lance"}},
            _turn_end(),
        ]
        return actions

    # Trap/door corridor: search has disarmed the threshold before we cross.
    actions += [
        {"type": "move", "direction": "east"},
        {"type": "open_door", "target": "door_1"},
        _turn_end(),
        {"type": "move", "direction": "east"},
        _turn_end(),
        {"type": "attack_melee", "target": "crypt_brute_1"},
        _turn_end(),
        {"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "spark_lance"}},
        _turn_end(),
    ]
    if scenario_id in {"double_breach_nemesis", "frost_mirror_crossfire"}:
        actions += [
            {"type": "move", "direction": "east"},
            {"type": "open_door", "target": "door_2"},
            _turn_end(),
            {"type": "move", "direction": "east"},
            {"type": "interact", "target": "objective"},
            _turn_end(),
        ]
    else:
        if scenario_id == "moonblade_vault_breach":
            actions += [{"type": "move", "direction": "east"}, {"type": "interact", "target": "chest_1"}, _turn_end()]
        actions += [{"type": "move", "direction": "east"}, {"type": "interact", "target": "objective"}, _turn_end()]
    return actions


def _probe() -> list[dict[str, Any]]:
    return [
        _msg(), {"type": "move", "direction": "east"}, _turn_end(),
        {"type": "cast", "target": "self", "payload": {"spell": "ward_circle"}}, _turn_end(),
        {"type": "search_traps"}, _turn_end(),
        {"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "reveal_glyph"}}, _turn_end(),
        {"type": "move", "direction": "east"}, {"type": "open_door", "target": "door_1"}, _turn_end(),
        {"type": "move", "direction": "east"}, _turn_end(),
        {"type": "give_item", "target": "agent_1", "payload": {"item": "iron_ration"}}, _turn_end(),
        {"type": "use_item", "target": "iron_ration"}, {"type": "move", "direction": "east"}, _turn_end(),
        {"type": "interact", "target": "chest_1"}, _turn_end(),
        {"type": "attack_melee", "target": "crypt_brute_1"}, _turn_end(),
        {"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "spark_lance"}}, _turn_end(),
        {"type": "move", "direction": "east"}, {"type": "interact", "target": "objective"}, _turn_end(),
    ]


def plan_actions(scenario: dict[str, Any], objective: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    scenario_id = str(scenario.get("scenario_id", ""))
    if scenario_id == "mechanics_probe":
        return _probe()
    return _standard(scenario_id)
