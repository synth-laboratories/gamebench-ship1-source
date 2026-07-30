#!/usr/bin/env python3
"""Compare Python and Rust Rogue gold lanes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared", TASK_DIR / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_io import parse_action_text
from engine import RogueEngine
from scenarios import run_scenario, scenario_to_task
from source_scrolls import S_ID_R_OR_S
from source_sticks import WS_FIRE, WS_LIGHT, WS_MISSILE, WS_TELAWAY, WS_TELTO
from source_traps import F_REAL, T_ARROW, T_BEAR, T_DOOR, T_MYST, T_TELEP
from task_resolve import resolve_task


def run_rust(entry: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--"], input=json.dumps(entry), text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def checkpoint_semantics_match() -> bool:
    entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"][0]
    engine = RogueEngine()
    engine.reset(resolve_task(scenario_to_task(entry)))
    for action in entry["actions"][:4]:
        engine.step(action)
    blob = engine.checkpoint_bytes()
    checkpoint_payload = json.loads(blob.decode("utf-8"))
    if checkpoint_payload.get("source_state_projection") != engine.source_state_projection():
        return False
    events_at_checkpoint = engine.nev.legacy_strings()
    engine.step("l")
    engine.restore_checkpoint(blob)
    if engine.nev.legacy_strings() != events_at_checkpoint:
        return False
    engine.step("l")
    restored_tail = engine.nev.legacy_strings()
    reference = RogueEngine()
    reference.reset(resolve_task(scenario_to_task(entry)))
    for action in [*entry["actions"][:4], "l"]:
        reference.step(action)
    return restored_tail == reference.nev.legacy_strings()


def checkpoint_source_projection_match() -> bool:
    entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"][0]
    prefix_entry = dict(entry)
    prefix_entry["actions"] = list(entry["actions"][:4])
    engine = RogueEngine()
    engine.reset(resolve_task(scenario_to_task(prefix_entry)))
    for action in prefix_entry["actions"]:
        engine.step(action)
    rust = run_rust(prefix_entry)
    return engine.source_state_projection() == rust["checkpoint"]["source_state_projection"]


def command_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_command_surface",
        "seed": 11,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@...*....%|      ",
            "  |....:.....|      ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 20}},
        "objective": "descend",
        "inventory": [
            {"id": "addstr", "type": "=", "which": 1, "arm": 2, "packch": "a"},
            {"id": "healing", "type": "!", "which": 5, "count": 1, "packch": "b"},
            {"id": "light", "type": "/", "which": 0, "charges": 2, "packch": "c"},
            {"id": "fooddet", "type": "?", "which": 11, "count": 1, "packch": "d"},
        ],
        "actions": ["P", "R", "q", "z", "r", "?", "x"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    return (
        py["events"] == rs["events"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["readout"]["command_dispatch"] == rs["readout"]["command_dispatch"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
    )


def combat_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_combat_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@........%|      ",
            "  |..........|      ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "monsters": [{"id": "kestrel", "type": "K", "row": 2, "col": 4, "hp": 1, "max_hp": 1, "arm": 20, "exp": 20, "damage": "1x1"}],
        "actions": ["l", "l"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
    )


def attack_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_attack_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@........%|      ",
            "  |..........|      ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "monsters": [{"id": "rattler", "type": "R", "row": 2, "col": 3, "hp": 8, "max_hp": 8, "level": 20, "damage": "1x1"}],
        "actions": ["."],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
    )


def chase_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_chase_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@........%|      ",
            "  |..........|      ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "monsters": [{"id": "kestrel", "type": "K", "row": 2, "col": 5, "hp": 8, "max_hp": 8, "level": 1, "damage": "1x1"}],
        "actions": ["."],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and py["readout"]["public"]["visible_monsters"] == {"2,4": "K"}
        and py["readout"]["private"]["hp"] == 12
    )


def do_chase_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_do_chase_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.*.....%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "monsters": [
            {
                "id": "collector",
                "type": "K",
                "row": 2,
                "col": 6,
                "hp": 8,
                "max_hp": 8,
                "level": 1,
                "damage": "1x1",
                "dest_kind": "object",
                "dest_row": 2,
                "dest_col": 5,
                "dest_room": 0,
            }
        ],
        "actions": ["."],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    py_monster = py["readout"]["private"]["source_monsters"][0]
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and py["readout"]["public"]["visible_items"] == {}
        and py["readout"]["public"]["visible_monsters"] == {"2,5": "K"}
        and py_monster["pack"] == [{"pos": {"x": 5, "y": 2}, "type": "*"}]
    )


def trap_surface_match() -> bool:
    arrow_entry = {
        "scenario_id": "inline_trap_arrow_surface",
        "seed": 76,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@^.....%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "traps": [{"id": "arrow", "row": 2, "col": 4, "kind": T_ARROW, "flags": F_REAL | T_ARROW}],
        "actions": ["l", ">"],
    }
    bear_entry = {
        "scenario_id": "inline_trap_bear_surface",
        "seed": -17,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@^.....%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "traps": [{"id": "bear", "row": 2, "col": 4, "kind": T_BEAR, "flags": F_REAL | T_BEAR}],
        "actions": ["l", "l"],
    }
    arrow_py = run_scenario(arrow_entry)
    arrow_rs = run_rust(arrow_entry)
    bear_py = run_scenario(bear_entry)
    bear_rs = run_rust(bear_entry)
    return (
        arrow_py["events"] == arrow_rs["events"]
        and arrow_py["readout"]["public"] == arrow_rs["readout"]["public"]
        and arrow_py["readout"]["private"] == arrow_rs["readout"]["private"]
        and arrow_py["checkpoint"]["source_state_projection"] == arrow_rs["checkpoint"]["source_state_projection"]
        and arrow_py["readout"]["private"]["hp"] < 12
        and arrow_py["readout"]["private"]["source_trap_markers"] == ["flush_type"]
        and bear_py["events"] == bear_rs["events"]
        and bear_py["readout"]["public"] == bear_rs["readout"]["public"]
        and bear_py["readout"]["private"] == bear_rs["readout"]["private"]
        and bear_py["checkpoint"]["source_state_projection"] == bear_rs["checkpoint"]["source_state_projection"]
        and bear_py["readout"]["public"]["hero"] == [2, 4]
        and bear_py["readout"]["private"]["no_move"] == 2
        and bear_py["readout"]["private"]["source_trap_markers"] == ["flush_type"]
    )


def search_surface_match() -> bool:
    trap_entry = {
        "scenario_id": "inline_search_hidden_trap_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  -----             ",
            "  |@..|             ",
            "  |...|             ",
            "  -----             ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "traps": [{"id": "hidden_arrow", "row": 2, "col": 4, "kind": T_ARROW, "flags": T_ARROW}],
        "actions": ["s"],
    }
    door_entry = {
        "scenario_id": "inline_search_secret_door_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  -----             ",
            "  |@||              ",
            "  |..|              ",
            "  -----             ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "source_map_cells": [{"id": "secret_door", "row": 2, "col": 4, "ch": "|", "flags": 0}],
        "actions": ["s"],
    }
    passage_entry = {
        "scenario_id": "inline_search_hidden_passage_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  -----             ",
            "  |@                ",
            "  |..|              ",
            "  -----             ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "source_map_cells": [{"id": "hidden_passage", "row": 2, "col": 4, "ch": " ", "flags": 0}],
        "actions": ["s"],
    }
    trap_py = run_scenario(trap_entry)
    trap_rs = run_rust(trap_entry)
    door_py = run_scenario(door_entry)
    door_rs = run_rust(door_entry)
    passage_py = run_scenario(passage_entry)
    passage_rs = run_rust(passage_entry)
    search_event = next(event for event in trap_py["nev"] if event["message"] == "SourceSearch()")
    trap = trap_py["readout"]["private"]["source_traps"][0]
    door_cell = door_py["readout"]["private"]["source_map_cells"][0]
    passage_cell = passage_py["readout"]["private"]["source_map_cells"][0]
    return (
        trap_py["events"] == trap_rs["events"]
        and trap_py["readout"]["public"] == trap_rs["readout"]["public"]
        and trap_py["readout"]["private"] == trap_rs["readout"]["private"]
        and trap_py["checkpoint"]["source_state_projection"] == trap_rs["checkpoint"]["source_state_projection"]
        and trap_py["readout"]["public"]["visible_items"]["2,4"] == "^"
        and trap["flags"] & F_REAL != 0
        and trap["flags"] & 0x40 != 0
        and "search_found_trap:hidden_arrow" in trap_py["readout"]["private"]["source_trap_markers"]
        and search_event["payload"]["found"] is True
        and door_py["events"] == door_rs["events"]
        and door_py["readout"]["public"] == door_rs["readout"]["public"]
        and door_py["readout"]["private"] == door_rs["readout"]["private"]
        and door_py["checkpoint"]["source_state_projection"] == door_rs["checkpoint"]["source_state_projection"]
        and door_py["readout"]["public"]["terrain"][2][4] == "+"
        and door_cell["ch"] == "+"
        and door_cell["flags"] & F_REAL != 0
        and "search_found_door:secret_door" in door_py["readout"]["private"]["source_trap_markers"]
        and passage_py["events"] == passage_rs["events"]
        and passage_py["readout"]["public"] == passage_rs["readout"]["public"]
        and passage_py["readout"]["private"] == passage_rs["readout"]["private"]
        and passage_py["checkpoint"]["source_state_projection"] == passage_rs["checkpoint"]["source_state_projection"]
        and passage_py["readout"]["public"]["terrain"][2][4] == "#"
        and passage_cell["ch"] == "#"
        and passage_cell["flags"] & F_REAL != 0
        and "search_found_passage:hidden_passage" in passage_py["readout"]["private"]["source_trap_markers"]
    )


def daemon_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_daemon_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "actions": ["."],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and "SourceDaemons(after)" in py["events"]
        and py["readout"]["private"]["food_left"] == 1299
        and py["readout"]["private"]["source_daemon_actions"] == [
            {"action": "doctor", "arg": 0, "time": -1, "type": 2},
            {"action": "stomach", "arg": 0, "time": -1, "type": 2},
        ]
    )


def new_level_surface_match() -> bool:
    descend_entry = {
        "scenario_id": "inline_new_level_descend_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@%.....|         ",
            "  |.......|         ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "collect_gold",
        "actions": ["l", ">"],
    }
    trapdoor_entry = {
        "scenario_id": "inline_new_level_trapdoor_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@^.....|         ",
            "  |.......|         ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "collect_gold",
        "traps": [{"id": "trapdoor", "row": 2, "col": 4, "kind": T_DOOR, "flags": F_REAL | T_DOOR}],
        "actions": ["l"],
    }
    descend_py = run_scenario(descend_entry)
    descend_rs = run_rust(descend_entry)
    trapdoor_py = run_scenario(trapdoor_entry)
    trapdoor_rs = run_rust(trapdoor_entry)
    return (
        descend_py["events"] == descend_rs["events"]
        and descend_py["readout"]["public"] == descend_rs["readout"]["public"]
        and descend_py["readout"]["private"] == descend_rs["readout"]["private"]
        and descend_py["checkpoint"]["source_state_projection"] == descend_rs["checkpoint"]["source_state_projection"]
        and descend_py["readout"]["private"]["dungeon_level"] == 2
        and descend_py["readout"]["private"]["max_level"] == 2
        and descend_py["readout"]["private"]["terminated"] is False
        and "SourceNewLevel(descend,level=2)" in descend_py["events"]
        and trapdoor_py["events"] == trapdoor_rs["events"]
        and trapdoor_py["readout"]["public"] == trapdoor_rs["readout"]["public"]
        and trapdoor_py["readout"]["private"] == trapdoor_rs["readout"]["private"]
        and trapdoor_py["checkpoint"]["source_state_projection"] == trapdoor_rs["checkpoint"]["source_state_projection"]
        and trapdoor_py["readout"]["private"]["dungeon_level"] == 2
        and trapdoor_py["readout"]["private"]["max_level"] == 2
        and trapdoor_py["readout"]["private"]["terminated"] is False
        and "SourceNewLevel(trapdoor,level=2)" in trapdoor_py["events"]
    )


def pickup_surface_match() -> bool:
    insert_entry = {
        "scenario_id": "inline_pickup_insert_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@!.....%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "addstr", "type": "=", "which": 1, "arm": 2, "packch": "a"}],
        "level_objects": [{"id": "floor_heal", "type": "!", "which": 5, "row": 2, "col": 4, "count": 1}],
        "actions": ["l"],
    }
    merge_entry = {
        "scenario_id": "inline_pickup_merge_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@!.....%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "healing_stack", "type": "!", "which": 5, "count": 1, "packch": "a"}],
        "level_objects": [{"id": "floor_heal", "type": "!", "which": 5, "row": 2, "col": 4, "count": 1}],
        "actions": ["l"],
    }
    insert_py = run_scenario(insert_entry)
    insert_rs = run_rust(insert_entry)
    merge_py = run_scenario(merge_entry)
    merge_rs = run_rust(merge_entry)
    inserted = insert_py["readout"]["private"]["source_inventory"]
    merged = merge_py["readout"]["private"]["source_inventory"]
    return (
        insert_py["events"] == insert_rs["events"]
        and insert_py["readout"]["public"] == insert_rs["readout"]["public"]
        and insert_py["readout"]["private"] == insert_rs["readout"]["private"]
        and insert_py["checkpoint"]["source_state_projection"] == insert_rs["checkpoint"]["source_state_projection"]
        and insert_py["readout"]["public"]["visible_items"] == {}
        and insert_py["readout"]["private"]["source_level_objects"] == []
        and len(inserted) == 2
        and inserted[1]["id"] == "floor_heal"
        and inserted[1]["packch"] == "b"
        and inserted[1]["flags"] & 0o000020 != 0
        and merge_py["events"] == merge_rs["events"]
        and merge_py["readout"]["public"] == merge_rs["readout"]["public"]
        and merge_py["readout"]["private"] == merge_rs["readout"]["private"]
        and merge_py["checkpoint"]["source_state_projection"] == merge_rs["checkpoint"]["source_state_projection"]
        and merge_py["readout"]["public"]["visible_items"] == {}
        and merge_py["readout"]["private"]["source_level_objects"] == []
        and len(merged) == 1
        and merged[0]["id"] == "healing_stack"
        and merged[0]["count"] == 2
        and merged[0]["packch"] == "a"
        and merged[0]["flags"] & 0o000020 != 0
    )


def drop_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_drop_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "healing_stack", "type": "!", "which": 5, "count": 2, "packch": "a"}],
        "actions": ["d"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    inventory = py["readout"]["private"]["source_inventory"]
    level_objects = py["readout"]["private"]["source_level_objects"]
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and py["readout"]["public"]["visible_items"] == {"2,3": "!"}
        and len(inventory) == 1
        and inventory[0]["id"] == "healing_stack"
        and inventory[0]["count"] == 1
        and len(level_objects) == 1
        and level_objects[0]["id"] == "healing_stack_drop1"
        and level_objects[0]["type"] == "!"
        and level_objects[0]["count"] == 1
        and level_objects[0]["pos"] == {"y": 2, "x": 3}
        and "SourceDrop(healing_stack_drop1)" in py["events"]
    )


def eat_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_eat_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "ration_stack", "type": ":", "which": 0, "count": 2, "packch": "a"}],
        "actions": ["e"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    inventory = py["readout"]["private"]["source_inventory"]
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and len(inventory) == 1
        and inventory[0]["id"] == "ration_stack"
        and inventory[0]["count"] == 1
        and py["readout"]["private"]["food_left"] == 1999
        and py["readout"]["private"]["hungry_state"] == 0
        and py["readout"]["private"]["source_effect_markers"][0] == "eat_food"
        and "SourceEat(ration_stack)" in py["events"]
    )


def equipment_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_equipment_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [
            {"id": "sword", "type": ")", "which": 0, "damage": "3x4", "hurldmg": "1x3", "packch": "a"},
            {"id": "mail", "type": "]", "which": 3, "arm": 4, "flags": 0, "packch": "b"},
            {"id": "armor_scroll", "type": "?", "which": 4, "count": 1, "packch": "c"},
        ],
        "actions": ["w", "W", "r", "T"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    inventory = {item["id"]: item for item in py["readout"]["private"]["source_inventory"]}
    projection = py["checkpoint"]["source_state_projection"]
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and py["readout"]["private"]["current_weapon_id"] == "sword"
        and py["readout"]["private"]["current_armor_id"] == ""
        and py["readout"]["private"]["player_armor"] == 6
        and inventory["mail"]["arm"] == 3
        and inventory["mail"]["flags"] & 0o000002 != 0
        and "armor_scroll" not in inventory
        and projection["current_weapon_id"] == "sword"
        and projection["current_armor_id"] == ""
        and "SourceWield(sword)" in py["events"]
        and "SourceWear(mail)" in py["events"]
        and "SourceEffect(r,armor_scroll)" in py["events"]
        and "SourceTakeOff(mail)" in py["events"]
    )


def stick_target_surface_match() -> bool:
    cancel_entry = {
        "scenario_id": "inline_stick_cancel_target_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |....@..%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "cancel_wand", "type": "/", "which": 13, "charges": 2, "packch": "a"}],
        "monsters": [{"id": "target", "type": "M", "row": 2, "col": 5, "hp": 8, "flags": 0o002001}],
        "actions": ["z"],
    }
    drain_entry = {
        "scenario_id": "inline_stick_drain_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |....@..%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "drain_wand", "type": "/", "which": 9, "charges": 2, "packch": "a"}],
        "monsters": [
            {"id": "weak", "type": "K", "row": 2, "col": 6, "hp": 3, "max_hp": 3},
            {"id": "ogre", "type": "O", "row": 2, "col": 3, "hp": 8, "max_hp": 8},
        ],
        "actions": ["z"],
    }
    directed_entry = {
        "scenario_id": "inline_stick_directed_cancel_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |.......%|        ",
            "  |...@....|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "cancel_wand", "type": "/", "which": 13, "charges": 2, "packch": "a"}],
        "monsters": [{"id": "upper_target", "type": "M", "row": 2, "col": 6, "hp": 8, "flags": 0o002001}],
        "actions": ["zk"],
    }
    cancel_py = run_scenario(cancel_entry)
    cancel_rs = run_rust(cancel_entry)
    drain_py = run_scenario(drain_entry)
    drain_rs = run_rust(drain_entry)
    directed_py = run_scenario(directed_entry)
    directed_rs = run_rust(directed_entry)
    cancel_effect = next(event for event in cancel_py["nev"] if event["message"] == "SourceEffect(z,cancel_wand)")
    directed_effect = next(event for event in directed_py["nev"] if event["message"] == "SourceEffect(z,cancel_wand)")
    drain_inventory = drain_py["readout"]["private"]["source_inventory"]
    drain_monsters = {monster["id"]: monster for monster in drain_py["readout"]["private"]["source_monsters"]}
    return (
        cancel_py["events"] == cancel_rs["events"]
        and cancel_py["readout"]["public"] == cancel_rs["readout"]["public"]
        and cancel_py["readout"]["private"] == cancel_rs["readout"]["private"]
        and cancel_py["checkpoint"]["source_state_projection"] == cancel_rs["checkpoint"]["source_state_projection"]
        and cancel_effect["payload"]["world"]["target"]["flags"] == 0o000010
        and cancel_py["readout"]["private"]["source_effect_markers"] == ["draw_disguise"]
        and drain_py["events"] == drain_rs["events"]
        and drain_py["readout"]["public"] == drain_rs["readout"]["public"]
        and drain_py["readout"]["private"] == drain_rs["readout"]["private"]
        and drain_py["checkpoint"]["source_state_projection"] == drain_rs["checkpoint"]["source_state_projection"]
        and drain_py["readout"]["private"]["hp"] == 6
        and drain_inventory[0]["charges"] == 1
        and "weak" not in drain_monsters
        and drain_monsters["ogre"]["hp"] == 5
        and "killed:K" in drain_py["readout"]["private"]["source_effect_markers"]
        and "runto:O" in drain_py["readout"]["private"]["source_effect_markers"]
        and directed_py["events"] == directed_rs["events"]
        and directed_py["readout"]["public"] == directed_rs["readout"]["public"]
        and directed_py["readout"]["private"] == directed_rs["readout"]["private"]
        and directed_py["checkpoint"]["source_state_projection"] == directed_rs["checkpoint"]["source_state_projection"]
        and "do_zap:k" in directed_py["readout"]["private"]["command_markers"]
        and directed_effect["action"] == "zk"
        and directed_effect["payload"]["world"]["target"]["flags"] == 0o000010
    )


def throw_surface_match() -> bool:
    hit_entry = {
        "scenario_id": "inline_throw_hit_surface",
        "seed": 3,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |.@....%|         ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "dagger_stack", "type": ")", "which": 4, "count": 2, "damage": "1x6", "hurldmg": "1x4", "launch": -1, "flags": 4, "packch": "a"}],
        "monsters": [{"id": "target", "type": "K", "row": 2, "col": 5, "hp": 1, "max_hp": 1, "arm": 20, "exp": 1}],
        "actions": ["tl"],
    }
    fall_entry = {
        "scenario_id": "inline_throw_fall_surface",
        "seed": 3,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |.@....%|         ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "dagger_stack", "type": ")", "which": 4, "count": 2, "damage": "1x6", "hurldmg": "1x4", "launch": -1, "flags": 4, "packch": "a"}],
        "actions": ["tl"],
    }
    hit_py = run_scenario(hit_entry)
    hit_rs = run_rust(hit_entry)
    fall_py = run_scenario(fall_entry)
    fall_rs = run_rust(fall_entry)
    hit_inventory = hit_py["readout"]["private"]["source_inventory"]
    fall_inventory = fall_py["readout"]["private"]["source_inventory"]
    fall_objects = fall_py["readout"]["private"]["source_level_objects"]
    hit_throw = next(event for event in hit_py["nev"] if event["message"].startswith("SourceThrow("))
    fall_throw = next(event for event in fall_py["nev"] if event["message"].startswith("SourceThrow("))
    return (
        hit_py["events"] == hit_rs["events"]
        and hit_py["readout"]["public"] == hit_rs["readout"]["public"]
        and hit_py["readout"]["private"] == hit_rs["readout"]["private"]
        and hit_py["checkpoint"]["source_state_projection"] == hit_rs["checkpoint"]["source_state_projection"]
        and hit_inventory[0]["id"] == "dagger_stack"
        and hit_inventory[0]["count"] == 1
        and hit_py["readout"]["private"]["source_monsters"] == []
        and hit_py["readout"]["private"]["source_level_objects"] == []
        and hit_throw["payload"]["hit"] is True
        and hit_throw["payload"]["thrown"]["id"] == "dagger_stack_throw1"
        and "missile:l" in hit_py["readout"]["private"]["source_effect_markers"]
        and fall_py["events"] == fall_rs["events"]
        and fall_py["readout"]["public"] == fall_rs["readout"]["public"]
        and fall_py["readout"]["private"] == fall_rs["readout"]["private"]
        and fall_py["checkpoint"]["source_state_projection"] == fall_rs["checkpoint"]["source_state_projection"]
        and fall_inventory[0]["id"] == "dagger_stack"
        and fall_inventory[0]["count"] == 1
        and len(fall_objects) == 1
        and fall_objects[0]["id"] == "dagger_stack_throw1"
        and fall_objects[0]["type"] == ")"
        and fall_objects[0]["count"] == 1
        and fall_throw["payload"]["hit"] is False
        and fall_throw["payload"]["fall_result"] == "fall"
        and ")" in fall_py["readout"]["public"]["visible_items"].values()
    )


def selection_surface_match() -> bool:
    drop_entry = {
        "scenario_id": "inline_pack_selection_drop_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [
            {"id": "healing", "type": "!", "which": 5, "count": 1, "packch": "a"},
            {"id": "mapping", "type": "?", "which": 1, "count": 1, "packch": "b"},
        ],
        "actions": ["db"],
    }
    quaff_entry = {
        "scenario_id": "inline_pack_selection_quaff_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [
            {"id": "blind", "type": "!", "which": 12, "count": 1, "packch": "a"},
            {"id": "healing", "type": "!", "which": 5, "count": 1, "packch": "b"},
        ],
        "actions": ["qb"],
    }
    wield_entry = {
        "scenario_id": "inline_pack_selection_wield_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@......%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [
            {"id": "mace", "type": ")", "which": 0, "damage": "2x4", "hurldmg": "1x3", "packch": "a"},
            {"id": "sword", "type": ")", "which": 1, "damage": "3x4", "hurldmg": "1x2", "packch": "b"},
        ],
        "actions": ["wb"],
    }
    drop_py = run_scenario(drop_entry)
    drop_rs = run_rust(drop_entry)
    quaff_py = run_scenario(quaff_entry)
    quaff_rs = run_rust(quaff_entry)
    wield_py = run_scenario(wield_entry)
    wield_rs = run_rust(wield_entry)
    drop_inventory = {item["id"]: item for item in drop_py["readout"]["private"]["source_inventory"]}
    drop_objects = drop_py["readout"]["private"]["source_level_objects"]
    quaff_inventory = {item["id"]: item for item in quaff_py["readout"]["private"]["source_inventory"]}
    return (
        drop_py["events"] == drop_rs["events"]
        and drop_py["readout"]["public"] == drop_rs["readout"]["public"]
        and drop_py["readout"]["private"] == drop_rs["readout"]["private"]
        and drop_py["checkpoint"]["source_state_projection"] == drop_rs["checkpoint"]["source_state_projection"]
        and set(drop_inventory) == {"healing"}
        and len(drop_objects) == 1
        and drop_objects[0]["id"] == "mapping"
        and drop_objects[0]["type"] == "?"
        and quaff_py["events"] == quaff_rs["events"]
        and quaff_py["readout"]["public"] == quaff_rs["readout"]["public"]
        and quaff_py["readout"]["private"] == quaff_rs["readout"]["private"]
        and quaff_py["checkpoint"]["source_state_projection"] == quaff_rs["checkpoint"]["source_state_projection"]
        and set(quaff_inventory) == {"blind"}
        and "SourceEffect(q,healing)" in quaff_py["events"]
        and wield_py["events"] == wield_rs["events"]
        and wield_py["readout"]["public"] == wield_rs["readout"]["public"]
        and wield_py["readout"]["private"] == wield_rs["readout"]["private"]
        and wield_py["checkpoint"]["source_state_projection"] == wield_rs["checkpoint"]["source_state_projection"]
        and wield_py["readout"]["private"]["current_weapon_id"] == "sword"
        and "SourceWield(sword)" in wield_py["events"]
    )


def relocation_surface_match() -> bool:
    scroll_entry = {
        "scenario_id": "inline_scroll_teleport_surface",
        "seed": 7,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "teleport_scroll", "type": "?", "which": 12, "count": 1, "packch": "a"}],
        "actions": ["r"],
    }
    trap_entry = {
        "scenario_id": "inline_trap_teleport_surface",
        "seed": 3,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.^....%|        ",
            "  |........|        ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "traps": [{"id": "telep", "row": 2, "col": 5, "kind": T_TELEP, "flags": F_REAL | T_TELEP}],
        "actions": ["l", "l"],
    }
    telto_entry = {
        "scenario_id": "inline_stick_telto_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "telto_wand", "type": "/", "which": WS_TELTO, "charges": 2, "packch": "a"}],
        "monsters": [{"id": "kestrel", "type": "K", "row": 2, "col": 8, "hp": 8, "max_hp": 8, "level": 1, "damage": "1x1"}],
        "actions": ["zl"],
    }
    telaway_entry = {
        "scenario_id": "inline_stick_telaway_surface",
        "seed": 9,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "telaway_wand", "type": "/", "which": WS_TELAWAY, "charges": 2, "packch": "a"}],
        "monsters": [{"id": "kestrel", "type": "K", "row": 2, "col": 8, "hp": 8, "max_hp": 8, "level": 1, "damage": "1x1"}],
        "actions": ["zl"],
    }
    scroll_py = run_scenario(scroll_entry)
    scroll_rs = run_rust(scroll_entry)
    trap_py = run_scenario(trap_entry)
    trap_rs = run_rust(trap_entry)
    telto_py = run_scenario(telto_entry)
    telto_rs = run_rust(telto_entry)
    telaway_py = run_scenario(telaway_entry)
    telaway_rs = run_rust(telaway_entry)
    scroll_teleport = next(event for event in scroll_py["nev"] if event["message"].startswith("SourceTeleport(scroll,"))
    trap_teleport = next(event for event in trap_py["nev"] if event["message"].startswith("SourceTeleport(trap,"))
    return (
        scroll_py["events"] == scroll_rs["events"]
        and scroll_py["readout"]["public"] == scroll_rs["readout"]["public"]
        and scroll_py["readout"]["private"] == scroll_rs["readout"]["private"]
        and scroll_py["checkpoint"]["source_state_projection"] == scroll_rs["checkpoint"]["source_state_projection"]
        and scroll_py["readout"]["public"]["hero"] != [2, 3]
        and scroll_teleport["payload"]["to"] == scroll_py["readout"]["public"]["hero"]
        and trap_py["events"] == trap_rs["events"]
        and trap_py["readout"]["public"] == trap_rs["readout"]["public"]
        and trap_py["readout"]["private"] == trap_rs["readout"]["private"]
        and trap_py["checkpoint"]["source_state_projection"] == trap_rs["checkpoint"]["source_state_projection"]
        and trap_py["readout"]["public"]["hero"] != [2, 5]
        and trap_teleport["payload"]["to"] == trap_py["readout"]["public"]["hero"]
        and telto_py["events"] == telto_rs["events"]
        and telto_py["readout"]["public"] == telto_rs["readout"]["public"]
        and telto_py["readout"]["private"] == telto_rs["readout"]["private"]
        and telto_py["checkpoint"]["source_state_projection"] == telto_rs["checkpoint"]["source_state_projection"]
        and "2,4" in telto_py["readout"]["public"]["visible_monsters"]
        and telaway_py["events"] == telaway_rs["events"]
        and telaway_py["readout"]["public"] == telaway_rs["readout"]["public"]
        and telaway_py["readout"]["private"] == telaway_rs["readout"]["private"]
        and telaway_py["checkpoint"]["source_state_projection"] == telaway_rs["checkpoint"]["source_state_projection"]
        and "2,8" not in telaway_py["readout"]["public"]["visible_monsters"]
    )


def directional_item_selection_surface_match() -> bool:
    throw_entry = {
        "scenario_id": "inline_directional_throw_selection_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [
            {"id": "mace", "type": ")", "which": 0, "damage": "2x4", "hurldmg": "1x3", "packch": "a"},
            {"id": "dagger_stack", "type": ")", "which": 4, "damage": "1x2", "hurldmg": "1x3", "count": 2, "packch": "b"},
        ],
        "actions": ["tbl"],
    }
    zap_entry = {
        "scenario_id": "inline_directional_zap_selection_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [
            {"id": "light_wand", "type": "/", "which": WS_LIGHT, "charges": 2, "packch": "a"},
            {"id": "missile_wand", "type": "/", "which": WS_MISSILE, "charges": 2, "packch": "b"},
        ],
        "monsters": [{"id": "kestrel", "type": "K", "row": 2, "col": 8, "hp": 8, "max_hp": 8, "level": 1, "damage": "1x1"}],
        "actions": ["zbl"],
    }
    throw_py = run_scenario(throw_entry)
    throw_rs = run_rust(throw_entry)
    zap_py = run_scenario(zap_entry)
    zap_rs = run_rust(zap_entry)
    throw_event = next(event for event in throw_py["nev"] if event["message"].startswith("SourceThrow("))
    zap_inventory = {item["id"]: item for item in zap_py["readout"]["private"]["source_inventory"]}
    return (
        throw_py["events"] == throw_rs["events"]
        and throw_py["readout"]["public"] == throw_rs["readout"]["public"]
        and throw_py["readout"]["private"] == throw_rs["readout"]["private"]
        and throw_py["checkpoint"]["source_state_projection"] == throw_rs["checkpoint"]["source_state_projection"]
        and throw_event["payload"]["thrown"]["id"] == "dagger_stack_throw1"
        and throw_event["payload"]["direction"] == "l"
        and throw_py["readout"]["private"]["source_inventory"][1]["id"] == "dagger_stack"
        and throw_py["readout"]["private"]["source_inventory"][1]["count"] == 1
        and zap_py["events"] == zap_rs["events"]
        and zap_py["readout"]["public"] == zap_rs["readout"]["public"]
        and zap_py["readout"]["private"] == zap_rs["readout"]["private"]
        and zap_py["checkpoint"]["source_state_projection"] == zap_rs["checkpoint"]["source_state_projection"]
        and "SourceEffect(z,missile_wand)" in zap_py["events"]
        and zap_inventory["light_wand"]["charges"] == 2
        and zap_inventory["missile_wand"]["charges"] == 1
        and "hit_monster:missile" in zap_py["readout"]["private"]["source_effect_markers"]
    )


def bolt_surface_match() -> bool:
    hit_entry = {
        "scenario_id": "inline_bolt_hit_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "fire_wand", "type": "/", "which": WS_FIRE, "charges": 2, "packch": "a"}],
        "monsters": [{"id": "kestrel", "type": "K", "row": 2, "col": 8, "hp": 1, "max_hp": 1, "level": 1, "arm": 20, "damage": "1x1"}],
        "actions": ["zal"],
    }
    dragon_entry = {
        "scenario_id": "inline_bolt_dragon_bounce_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ------------      ",
            "  |@.......%|       ",
            "  |.........|       ",
            "  ------------      ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "fire_wand", "type": "/", "which": WS_FIRE, "charges": 2, "packch": "a"}],
        "monsters": [{"id": "dragon", "type": "D", "row": 2, "col": 8, "hp": 20, "max_hp": 20, "level": 10, "arm": 20, "damage": "1x1"}],
        "actions": ["zal"],
    }
    reflected_entry = {
        "scenario_id": "inline_bolt_reflected_hero_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  ----              ",
            "  |@..|             ",
            "  |...|             ",
            "  ----              ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "inventory": [{"id": "fire_wand", "type": "/", "which": WS_FIRE, "charges": 2, "packch": "a"}],
        "actions": ["zal"],
    }
    hit_py = run_scenario(hit_entry)
    hit_rs = run_rust(hit_entry)
    dragon_py = run_scenario(dragon_entry)
    dragon_rs = run_rust(dragon_entry)
    reflected_py = run_scenario(reflected_entry)
    reflected_rs = run_rust(reflected_entry)
    hit_inventory = {item["id"]: item for item in hit_py["readout"]["private"]["source_inventory"]}
    dragon_inventory = {item["id"]: item for item in dragon_py["readout"]["private"]["source_inventory"]}
    reflected_inventory = {item["id"]: item for item in reflected_py["readout"]["private"]["source_inventory"]}
    return (
        hit_py["events"] == hit_rs["events"]
        and hit_py["readout"]["public"] == hit_rs["readout"]["public"]
        and hit_py["readout"]["private"] == hit_rs["readout"]["private"]
        and hit_py["checkpoint"]["source_state_projection"] == hit_rs["checkpoint"]["source_state_projection"]
        and hit_py["readout"]["private"]["source_monsters"] == []
        and "bolt_hit:kestrel" in hit_py["readout"]["private"]["source_effect_markers"]
        and "thunk" in hit_py["readout"]["private"]["source_combat_markers"]
        and hit_inventory["fire_wand"]["charges"] == 1
        and dragon_py["events"] == dragon_rs["events"]
        and dragon_py["readout"]["public"] == dragon_rs["readout"]["public"]
        and dragon_py["readout"]["private"] == dragon_rs["readout"]["private"]
        and dragon_py["checkpoint"]["source_state_projection"] == dragon_rs["checkpoint"]["source_state_projection"]
        and len(dragon_py["readout"]["private"]["source_monsters"]) == 1
        and dragon_py["readout"]["private"]["source_monsters"][0]["hp"] == 20
        and "bolt_bounced:dragon" in dragon_py["readout"]["private"]["source_effect_markers"]
        and dragon_inventory["fire_wand"]["charges"] == 1
        and reflected_py["events"] == reflected_rs["events"]
        and reflected_py["readout"]["public"] == reflected_rs["readout"]["public"]
        and reflected_py["readout"]["private"] == reflected_rs["readout"]["private"]
        and reflected_py["checkpoint"]["source_state_projection"] == reflected_rs["checkpoint"]["source_state_projection"]
        and reflected_py["readout"]["private"]["terminated"] is True
        and reflected_py["readout"]["private"]["terminal_reason"] == "death"
        and reflected_py["readout"]["private"]["hp"] == 0
        and "Terminal(death:b)" in reflected_py["events"]
        and "bolt_bounce" in reflected_py["readout"]["private"]["source_effect_markers"]
        and "bolt_hero_hit:19" in reflected_py["readout"]["private"]["source_effect_markers"]
        and "bolt_death:b" in reflected_py["readout"]["private"]["source_effect_markers"]
        and reflected_inventory["fire_wand"]["charges"] == 1
    )


def no_turn_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_no_turn_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  -----             ",
            "  |@^%|             ",
            "  |...|             ",
            "  -----             ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 24}},
        "objective": "descend",
        "inventory": [
            {"id": "sword", "type": ")", "which": 6, "count": 1, "damage": "1x8", "hurldmg": "1x4", "packch": "a"},
            {"id": "mail", "type": "]", "which": 2, "arm": 4, "packch": "b"},
            {"id": "ring", "type": "=", "which": 0, "arm": 1, "packch": "c"},
            {"id": "scroll", "type": "?", "which": 0, "count": 1, "packch": "d"},
            {"id": "identify_scroll", "type": "?", "which": S_ID_R_OR_S, "count": 1, "packch": "e"},
        ],
        "actions": ["wa", "Wb", "Pc", "i", "Ia", ")", "]", "=", "@", "?*", "/@", "rec", "D*", "^l", " ", "S", "o", "c"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    event_messages = py["events"]
    trap_event = next(event for event in py["nev"] if event["message"] == "SourceTrapQuery(l)")
    inventory_event = next(event for event in py["nev"] if event["message"] == "SourceInventory(i)")
    picky_event = next(event for event in py["nev"] if event["message"] == "SourceInventory(I)")
    current_event = next(event for event in py["nev"] if event["message"] == "SourceCurrent(current_weapon)")
    armor_event = next(event for event in py["nev"] if event["message"] == "SourceCurrent(current_armor)")
    rings_event = next(event for event in py["nev"] if event["message"] == "SourceCurrent(current_rings)")
    help_event = next(event for event in py["nev"] if event["message"] == "SourceHelp(*)")
    identify_event = next(event for event in py["nev"] if event["message"] == "SourceIdentify(@)")
    source_effect_event = next(event for event in py["nev"] if event["message"] == "SourceEffect(r,identify_scroll)")
    discovered_event = next(event for event in py["nev"] if event["message"] == "SourceDiscovered()")
    status_event = next(event for event in py["nev"] if event["message"] == "SourceStatus()")
    ring_inventory = next(item for item in py["readout"]["private"]["source_inventory"] if item["id"] == "ring")
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and "SourceInventory(i)" in event_messages
        and "SourceInventory(I)" in event_messages
        and "SourceCurrent(current_weapon)" in event_messages
        and "SourceCurrent(current_armor)" in event_messages
        and "SourceCurrent(current_rings)" in event_messages
        and "SourceStatus()" in event_messages
        and "SourceHelp(*)" in event_messages
        and "SourceIdentify(@)" in event_messages
        and "SourceEffect(r,identify_scroll)" in event_messages
        and "SourceDiscovered()" in event_messages
        and "SourceLegalIllegal()" in event_messages
        and "SourceSavePrompt()" in event_messages
        and "SourceNoTurn(option)" in event_messages
        and "SourceNoTurn(call)" in event_messages
        and inventory_event["payload"]["inventory"][0]["id"] == "sword"
        and inventory_event["payload"]["lines"] == ["a) A dart", "b) +3 studded leather armor [protection 6]", "c) A ring", "d) A scroll", "e) A scroll"]
        and picky_event["payload"]["prompt"] == "which item do you wish to inventory: "
        and picky_event["payload"]["selected"] == "a"
        and picky_event["payload"]["lines"] == ["a) A dart"]
        and current_event["payload"]["item"]["id"] == "sword"
        and current_event["payload"]["message"] == "you are wielding (a) a dart"
        and armor_event["payload"]["message"] == "you are wearing (b) +3 studded leather armor [protection 6]"
        and rings_event["payload"]["messages"] == ["you are wearing (c) a ring on left hand", "you are wearing nothing on right hand"]
        and help_event["payload"]["prompt"] == "character you want help for (* for all): "
        and help_event["payload"]["continue_prompt"] == "--Press space to continue--"
        and help_event["payload"]["lines"][0] == "?\tprints help"
        and "@\tprint current stats" in help_event["payload"]["lines"]
        and identify_event["payload"]["description"] == "you"
        and identify_event["payload"]["prompt"] == "what do you want identified? "
        and identify_event["payload"]["message"] == "'@': you"
        and source_effect_event["payload"]["world"]["trace"]["whatis_item"]["id"] == "ring"
        and "identified:=:0" in source_effect_event["payload"]["world"]["markers"]
        and ring_inventory["flags"] & 0o000002 != 0
        and py["readout"]["private"]["ring_known"][0] is True
        and discovered_event["payload"]["prompt"] == "for what type of object do you want a list? (* for all)"
        and discovered_event["payload"]["continue_prompt"] == "--Press space to continue--"
        and discovered_event["payload"]["sections"][0]["lines"] == ["Haven't discovered anything about any potions"]
        and discovered_event["payload"]["sections"][1]["lines"] == ["A scroll of identify ring, wand or staff"]
        and len(discovered_event["payload"]["sections"][2]["lines"]) == 1
        and discovered_event["payload"]["sections"][2]["lines"][0].startswith("A ring of protection(")
        and discovered_event["payload"]["sections"][3]["lines"] == ["Haven't discovered anything about any sticks"]
        and status_event["payload"]["display_armor"] == 6
        and status_event["payload"]["message"] == "Level: 1  Gold: 0      Hp: 12(12)  Str: 16(16)  Arm: 6   Exp: 1/0  "
        and trap_event["payload"]["found"] is True
        and trap_event["payload"]["kind"] == T_MYST
        and py["readout"]["private"]["source_traps"][0]["flags"] & 0x40 != 0
    )


def save_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_save_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  -----             ",
            "  |@.%|             ",
            "  |...|             ",
            "  -----             ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "descend",
        "actions": ["Srogue-save.dat"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    save_event = next(event for event in py["nev"] if event["message"] == "SourceSaveGame(rogue-save.dat)")
    save_file = save_event["payload"]["save_file"]
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and "Terminal(save)" in py["events"]
        and py["readout"]["private"]["terminated"] is True
        and py["readout"]["private"]["terminal_reason"] == "save"
        and save_event["payload"]["file_name"] == "rogue-save.dat"
        and save_event["payload"]["exit"] is True
        and save_file["schema"] == "gamebench.rogue.source_save_file.v1"
        and save_file["authority"] == "modern-rogue save.c encwrite + state.c rs_save_file projection"
        and save_file["encoding"] == "encwrite(version) + encwrite(geometry) + encwrite(rs_save_file_prefix + rs_save_file_identity_text + rs_save_file_scalars + rs_save_file_player_refs + rs_save_file_level_state + rs_save_file_room_state + rs_save_file_info_state + rs_save_file_tail_state)"
        and save_file["version"] == "rogue (rogueforge) 09/05/07"
        and save_file["geometry"] == "6 x 20\n"
        and save_file["len"] > 0
        and len(save_file["sha256"]) == 64
        and len(save_file["plain_subset_sha256"]) == 64
        and len(save_file["runtime_subset_sha256"]) == 64
        and save_file["rs_save_file_prefix_len"] == 64
        and len(save_file["rs_save_file_prefix_sha256"]) == 64
        and save_file["rs_save_file_prefix_fields"][:3] == ["after", "again", "noscore"]
        and save_file["rs_save_file_prefix_fields"][-2:] == ["wizard", "pack_used"]
        and save_file["rs_save_file_identity_text_len"] > 7000
        and len(save_file["rs_save_file_identity_text_sha256"]) == 64
        and save_file["rs_save_file_identity_text_fields"][:4] == ["dir_ch", "file_name", "huh", "potions"]
        and save_file["rs_save_file_identity_text_fields"][-3:] == ["last_comm", "last_dir", "tr_name"]
        and save_file["rs_save_file_scalar_len"] == 224
        and len(save_file["rs_save_file_scalar_sha256"]) == 64
        and save_file["rs_save_file_scalar_fields"][:4] == ["n_objs", "ntraps", "hungry_state", "inpack"]
        and save_file["rs_save_file_scalar_fields"][-3:] == ["delta", "oldpos", "stairs"]
        and save_file["rs_save_file_player_refs_len"] > 0
        and len(save_file["rs_save_file_player_refs_sha256"]) == 64
        and save_file["rs_save_file_player_refs_fields"] == ["player", "cur_armor", "cur_ring_left", "cur_ring_right", "cur_weapon", "l_last_pick", "last_pick"]
        and save_file["rs_save_file_level_state_len"] >= 15376
        and len(save_file["rs_save_file_level_state_sha256"]) == 64
        and save_file["rs_save_file_level_state_fields"] == ["lvl_obj", "mlist", "places"]
        and save_file["rs_save_file_level_state_places_count"] == 2560
        and save_file["rs_save_file_room_state_len"] > 2900
        and len(save_file["rs_save_file_room_state_sha256"]) == 64
        and save_file["rs_save_file_room_state_fields"] == ["max_stats", "rooms", "oldrp", "passages"]
        and save_file["rs_save_file_room_state_rooms_count"] == 9
        and save_file["rs_save_file_room_state_passages_count"] == 13
        and save_file["rs_save_file_info_state_len"] > 2600
        and len(save_file["rs_save_file_info_state_sha256"]) == 64
        and save_file["rs_save_file_info_state_fields"] == ["monsters", "things", "arm_info", "pot_info", "ring_info", "scr_info", "weap_info", "ws_info"]
        and save_file["rs_save_file_info_state_monsters_count"] == 26
        and save_file["rs_save_file_info_state_counts"] == {"things": 7, "arm_info": 8, "pot_info": 14, "ring_info": 14, "scr_info": 18, "weap_info": 10, "ws_info": 14}
        and save_file["rs_save_file_tail_state_len"] > 560
        and len(save_file["rs_save_file_tail_state_sha256"]) == 64
        and save_file["rs_save_file_tail_state_fields"] == ["d_list", "total", "between", "nh", "group", "stdscr"]
        and save_file["rs_save_file_tail_state_daemons_count"] == 20
        and save_file["rs_save_file_tail_state_window_height"] == 6
        and save_file["rs_save_file_tail_state_window_width"] == 20
        and save_file["len"] > save_file["rs_save_file_prefix_len"]
        and save_file["sha256"] != save_file["plain_subset_sha256"]
    )


def ascent_surface_match() -> bool:
    entry = {
        "scenario_id": "inline_amulet_ascent_surface",
        "seed": 1,
        "grid": [
            "                    ",
            "  -----             ",
            "  |@%.|             ",
            "  |...|             ",
            "  -----             ",
            "                    ",
        ],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 8}},
        "objective": "escape",
        "level_objects": [{"id": "amulet", "type": ",", "which": 0, "row": 2, "col": 3}],
        "actions": [",", "l", "<"],
    }
    py = run_scenario(entry)
    rs = run_rust(entry)
    return (
        py["events"] == rs["events"]
        and py["readout"]["public"] == rs["readout"]["public"]
        and py["readout"]["private"] == rs["readout"]["private"]
        and py["checkpoint"]["source_state_projection"] == rs["checkpoint"]["source_state_projection"]
        and "SourceWinner()" in py["events"]
        and "Terminal(success)" in py["events"]
        and py["readout"]["private"]["terminated"] is True
        and py["readout"]["private"]["terminal_reason"] == "success"
        and py["readout"]["private"]["total_reward"] == 1.0
    )


def agent_io_surface_match() -> bool:
    valid = RogueEngine().valid_actions()
    parsed_json = parse_action_text('{"action":"i"}', valid)
    parsed_text = parse_action_text("command: z", valid)
    parsed_invalid = parse_action_text("action: Q", valid)
    return (
        parsed_json.action == "i"
        and not parsed_json.invalid_parse
        and parsed_text.action == "z"
        and not parsed_text.invalid_parse
        and parsed_invalid.invalid_parse
        and parsed_invalid.repaired
        and parsed_invalid.action == valid[0]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parity-only", action="store_true")
    parser.add_argument("--output", default=str(TASK_DIR / "reports" / "lane_compare.json"))
    args = parser.parse_args()
    scenarios = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"]
    nev_mismatches = []
    symbolic_mismatches = []
    source_projection_mismatches = []
    command_dispatch_mismatches = []
    for entry in scenarios:
        py = run_scenario(entry)
        rs = run_rust(entry)
        if py["events"] != rs["events"]:
            nev_mismatches.append(entry["scenario_id"])
        if py["readout"]["public"] != rs["readout"]["public"] or py["readout"]["private"] != rs["readout"]["private"]:
            symbolic_mismatches.append(entry["scenario_id"])
        if py["checkpoint"]["source_state_projection"] != rs["checkpoint"]["source_state_projection"]:
            source_projection_mismatches.append(entry["scenario_id"])
        if py["readout"]["command_dispatch"] != rs["readout"]["command_dispatch"]:
            command_dispatch_mismatches.append(entry["scenario_id"])
    checkpoint_source_match = checkpoint_source_projection_match()
    command_surface = command_surface_match()
    combat_surface = combat_surface_match()
    attack_surface = attack_surface_match()
    chase_surface = chase_surface_match()
    do_chase_surface = do_chase_surface_match()
    trap_surface = trap_surface_match()
    search_surface = search_surface_match()
    daemon_surface = daemon_surface_match()
    new_level_surface = new_level_surface_match()
    pickup_surface = pickup_surface_match()
    drop_surface = drop_surface_match()
    eat_surface = eat_surface_match()
    equipment_surface = equipment_surface_match()
    stick_target_surface = stick_target_surface_match()
    throw_surface = throw_surface_match()
    selection_surface = selection_surface_match()
    relocation_surface = relocation_surface_match()
    directional_selection_surface = directional_item_selection_surface_match()
    bolt_surface = bolt_surface_match()
    no_turn_surface = no_turn_surface_match()
    save_surface = save_surface_match()
    ascent_surface = ascent_surface_match()
    agent_io_surface = agent_io_surface_match()
    report = {
        "schema": "gamebench.rogue.lane_compare.v1",
        "scenarios": [entry["scenario_id"] for entry in scenarios],
        "parity": {
            "nev_match": not nev_mismatches,
            "symbolic_match": not symbolic_mismatches,
            "checkpoint_semantics_match": checkpoint_semantics_match(),
            "checkpoint_source_projection_match": checkpoint_source_match,
            "command_dispatch_match": not command_dispatch_mismatches,
            "command_surface_match": command_surface,
            "combat_surface_match": combat_surface,
            "attack_surface_match": attack_surface,
            "chase_surface_match": chase_surface,
            "do_chase_surface_match": do_chase_surface,
            "trap_surface_match": trap_surface,
            "search_surface_match": search_surface,
            "daemon_surface_match": daemon_surface,
            "new_level_surface_match": new_level_surface,
            "pickup_surface_match": pickup_surface,
            "drop_surface_match": drop_surface,
            "eat_surface_match": eat_surface,
            "equipment_surface_match": equipment_surface,
            "stick_target_surface_match": stick_target_surface,
            "throw_surface_match": throw_surface,
            "selection_surface_match": selection_surface,
            "relocation_surface_match": relocation_surface,
            "directional_item_selection_surface_match": directional_selection_surface,
            "bolt_surface_match": bolt_surface,
            "no_turn_surface_match": no_turn_surface,
            "save_surface_match": save_surface,
            "ascent_surface_match": ascent_surface,
            "agent_io_surface_match": agent_io_surface,
            "nev_mismatches": nev_mismatches,
            "symbolic_mismatches": symbolic_mismatches,
            "source_projection_mismatches": source_projection_mismatches,
            "command_dispatch_mismatches": command_dispatch_mismatches,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if (
        nev_mismatches
        or symbolic_mismatches
        or source_projection_mismatches
        or command_dispatch_mismatches
        or not report["parity"]["checkpoint_semantics_match"]
        or not checkpoint_source_match
        or not command_surface
        or not combat_surface
        or not attack_surface
        or not chase_surface
        or not do_chase_surface
        or not trap_surface
        or not search_surface
        or not daemon_surface
        or not new_level_surface
        or not pickup_surface
        or not drop_surface
        or not eat_surface
        or not equipment_surface
        or not stick_target_surface
        or not throw_surface
        or not selection_surface
        or not relocation_surface
        or not directional_selection_surface
        or not bolt_surface
        or not no_turn_surface
        or not save_surface
        or not ascent_surface
        or not agent_io_surface
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
