from __future__ import annotations

from typing import Any


def mechanics_probe_scenario() -> dict[str, Any]:
    return {
        "task_id": "dg_mechanics_probe",
        "scenario_id": "mechanics_probe",
        "quest_id": "gamebench:mechanics_probe:rust",
        "title": "Lantern Crypt Mechanics Probe",
        "seed": 99,
        "max_steps": 80,
        "map_ascii": "########\n#E.DCI.#\n#.TR...#\n########",
        "hero_roles": ["barbarian", "wizard"],
        "objective_item": "probe_idol",
        "metadata": {
            "source_seed": {
                "quest_id": "lantern_crypt",
                "title": "The Lantern Crypt",
                "tier": "full",
                "distillation": "compresses the full crypt into a mechanics-rich breach covering trap, door, handoff, item, chest, combat, spell, and objective flow",
            },
            "marl_axis": "mechanics coverage for event-rich state snapshots",
            "coordination_skills": [
                "communicate before route commitment",
                "support reveals counterplay before the frontline attacks",
                "handoff and consume inventory while maintaining turn order",
            ],
        },
    }


def mechanics_probe_actions() -> list[dict[str, Any]]:
    return [
        {
            "type": "message",
            "target": "party",
            "payload": {"text": "Probe route: reveal, hand off ration, open chest, defeat brute."},
        },
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
        {"type": "cast", "target": "self", "payload": {"spell": "ward_circle"}},
        {"type": "end_turn"},
        {"type": "search_traps"},
        {"type": "end_turn"},
        {"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "reveal_glyph"}},
        {"type": "end_turn"},
        {"type": "open_door", "target": "door_1"},
        {"type": "give_item", "target": "agent_1", "payload": {"item": "iron_ration"}},
        {"type": "end_turn"},
        {"type": "use_item", "target": "iron_ration"},
        {"type": "guard"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "interact", "target": "chest_1"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
        {"type": "attack_melee", "target": "crypt_brute_1"},
        {"type": "end_turn"},
        {"type": "cast", "target": "crypt_brute_1", "payload": {"spell": "spark_lance"}},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "interact", "target": "objective"},
        {"type": "end_turn"},
        {"type": "inspect_tile", "target": {"x": 5, "y": 1}},
    ]
