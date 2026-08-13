"""Constrained property checks for the own NetHack dlvl-1 gold lanes.

These generate only valid Main Dungeon dlvl-1 room fixtures.  They verify
engine integrity and independent Python/Rust agreement; they are deliberately
not a substitute for frozen NLE conformance captures.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from gold_python.action_map import coerce_action
from scripts.capture_nle_fixture import level_dump
from scripts.compare_nle_discrepancies import compare_fixture
from scripts.fuzz_nle_differential import coverage_report
from scripts.promote_nle_fixture import validate_descend_boundary
from shared.task_resolve import BLSTATS_FIELDS, VIEW_HEIGHT, VIEW_WIDTH, resolve_task


ACTION_POOL = (
    "CompassDirection.N",
    "CompassDirection.E",
    "CompassDirection.S",
    "CompassDirection.W",
    "CompassDirection.NE",
    "CompassDirection.SW",
    "MiscDirection.WAIT",
    "MiscDirection.DOWN",
    "Command.PICKUP",
    "Command.SEARCH",
    "Command.OPEN",
    "Command.CLOSE",
    "Command.KICK",
    "Command.FIGHT",
    "Command.EAT",
    "Command.WIELD",
    "Command.EXTLIST",
    "Command.ENGRAVE",
    "Command.APPLY",
    "Command.ESC",
    "MiscAction.MORE",
)
KNOWN_INPUT_MODES = {"normal", "direction", "inventory_letter", "ynq", "string", "menu", "more"}
TERMINAL_REASONS = {"descended", "death", "quit", "saved", "max_steps"}
ACTION_MAP = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())
PINNED_ACTIONS = [tuple(entry) for entry in ACTION_MAP["actions"]]
UNSAFE_ACTIONS = [tuple(entry) for entry in ACTION_MAP["accepted_unsafe_keycodes"]]
UNSAFE_ALIASES = {"UnsafeActions.HELP": "help", "UnsafeActions.PREVMSG": "prevmsg"}


def room_terrain(*, hero_on_stairs: bool = False) -> list[str]:
    """Build a valid bounded dlvl-1 room with a real down stair."""

    grid = [[" "] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    for x in range(2, 13):
        grid[2][x] = "-"
        grid[6][x] = "-"
    for y in range(3, 6):
        grid[y][2] = "|"
        grid[y][12] = "|"
        for x in range(3, 12):
            grid[y][x] = "."
    grid[3][2] = "+"
    grid[4][10] = ">"
    grid[4][5] = ">" if hero_on_stairs else "@"
    return ["".join(row) for row in grid]


@st.composite
def constrained_case(draw: st.DrawFn) -> tuple[dict[str, Any], list[str]]:
    """Generate a small, internally consistent task and a short action tape."""

    hp_max = draw(st.integers(min_value=8, max_value=30))
    hp = draw(st.integers(min_value=6, max_value=hp_max))
    energy_max = draw(st.integers(min_value=0, max_value=12))
    include_monster = draw(st.booleans())
    include_trap = draw(st.booleans())
    include_floor_food = draw(st.booleans())
    task = {
        "schema": "gamebench.nethack.scenario.v1",
        "task_id": f"hypothesis-{draw(st.integers(min_value=0, max_value=1_000_000))}",
        "seed": draw(st.integers(min_value=0, max_value=0xFFFFFFFF)),
        "character": {
            "role": "val",
            "race": "hum",
            "gender": "fem",
            "align": draw(st.sampled_from(("law", "neu", "cha"))),
        },
        "rules": {
            "max_steps": draw(st.integers(min_value=4, max_value=12)),
            "autopickup": draw(st.booleans()),
            "auto_more": "raw_explicit",
            "vision_radius": 4,
        },
        "level_dump": {
            "terrain": room_terrain(),
            "inventory": [
                {"id": "ration", "kind": "%", "name": "a food ration", "nutrition": draw(st.integers(min_value=400, max_value=900))},
                {"id": "dagger", "kind": ")", "name": "a dagger", "damage": draw(st.integers(min_value=1, max_value=5))},
            ],
            "metadata": {
                "hp": hp,
                "hp_max": hp_max,
                "energy": draw(st.integers(min_value=0, max_value=energy_max)),
                "energy_max": energy_max,
                "hunger": draw(st.integers(min_value=50, max_value=1_200)),
                "gold": draw(st.integers(min_value=0, max_value=100)),
            },
        },
    }
    level = task["level_dump"]
    if include_floor_food:
        level["objects"] = [
            {
                "id": "floor-ration",
                "position": {"x": 6, "y": 4},
                "kind": "%",
                "name": "a floor ration",
                "nutrition": 600,
            }
        ]
    if include_monster:
        level["monsters"] = [
            {
                "id": "jackal",
                "name": "jackal",
                "char": "j",
                "position": {"x": 8, "y": 4},
                "hp": draw(st.integers(min_value=1, max_value=7)),
                "attack": draw(st.integers(min_value=0, max_value=3)),
                "experience": 2,
            }
        ]
    if include_trap:
        level["traps"] = [
            {
                "id": "dart-trap",
                "kind": "dart",
                "position": {"x": 4, "y": 4},
                "damage": draw(st.integers(min_value=0, max_value=5)),
            }
        ]
    actions = draw(st.lists(st.sampled_from(ACTION_POOL), min_size=0, max_size=8))
    return task, actions


def explicit_stair_task() -> dict[str, Any]:
    """Use explicit coordinates so the terrain under the hero remains `>`.

    This is the valid task representation for checking the dlvl-1 terminal
    boundary: `@` in a terrain row is normalized into floor terrain.
    """

    return {
        "task_id": "hypothesis-terminal-boundary",
        "seed": 1,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": room_terrain(hero_on_stairs=True),
            "hero": {"x": 5, "y": 4},
            "metadata": {"hp": 14, "hp_max": 14, "hunger": 900},
        },
    }


def adapter_task() -> dict[str, Any]:
    """A nonterminal task for checking every pinned input adapter."""

    return {
        "task_id": "hypothesis-action-adapter",
        "seed": 23,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": room_terrain(),
            "inventory": [
                {"id": "ration", "kind": "%", "name": "a food ration", "nutrition": 600},
                {"id": "dagger", "kind": ")", "name": "a dagger", "damage": 2},
            ],
            "metadata": {"hp": 20, "hp_max": 20, "hunger": 900},
        },
    }


def captured_inventory_task() -> dict[str, Any]:
    """A source-shaped Valkyrie inventory with its raw NLE presentation."""

    entries = [
        ("a", 2, "a +1 long sword (weapon in hand)", ")"),
        ("b", 2, "a +0 dagger (alternate weapon; not wielded)", ")"),
        ("c", 3, "an uncursed +3 small shield (being worn)", "["),
        ("d", 7, "2 uncursed food rations", "%"),
        ("e", 6, "an uncursed oil lamp", "("),
    ]
    task = adapter_task()
    level = task["level_dump"]
    level["inventory"] = [
        {"id": f"capture-{letter}", "letter": letter, "kind": kind, "name": name, "oclass_code": object_class}
        for letter, object_class, name, kind in entries
    ]
    level["metadata"]["nle_inventory"] = {
        "inv_letters": [ord(letter) for letter, _, _, _ in entries] + [0] * 50,
        "inv_glyphs": [0] * 55,
        "inv_oclasses": [object_class for _, object_class, _, _ in entries] + [18] * 50,
        "inv_strs": [capture_buffer(name, width=80) for _, _, name, _ in entries] + [[0] * 80 for _ in range(50)],
    }
    return task


def capture_buffer(text: str, *, width: int) -> list[int]:
    """Build an NLE-style fixed-width NUL-padded byte buffer."""

    return (list(text.encode("utf-8")) + [0] * width)[:width]


def seen_mask(*points: tuple[int, int]) -> list[list[bool]]:
    mask = [[False] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    for x, y in points:
        mask[y][x] = True
    return mask


def capture_state_task() -> tuple[dict[str, Any], dict[str, Any]]:
    """A two-snapshot fixture exercising captured observation state directly."""

    hero = (5, 4)
    revealed_on_move = (8, 4)
    terrain = [list(row) for row in room_terrain()]
    terrain[revealed_on_move[1]][revealed_on_move[0]] = "."
    glyphs = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    colors = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    glyphs[revealed_on_move[1]][revealed_on_move[0]] = 411
    colors[revealed_on_move[1]][revealed_on_move[0]] = 44
    unseen_chars = [[" "] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    unseen_glyphs = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    unseen_colors = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    unseen_chars[revealed_on_move[1]][revealed_on_move[0]] = "?"
    unseen_glyphs[revealed_on_move[1]][revealed_on_move[0]] = 901
    unseen_colors[revealed_on_move[1]][revealed_on_move[0]] = 31

    initial_message = "Captured baseline"
    message_width = 48
    baseline_blstats = [
        hero[0], hero[1], 18, 50, 11, 12, 13, 14, 15, 1234,
        17, 19, 1, 77, 3, 9, -2, 1, 2, 55,
        400, 9, 88, 3, 1, 7, 1,
    ]
    inventory_width = 28
    inventory_strings = [
        capture_buffer("a - captured ration", width=inventory_width),
        capture_buffer("b - captured dagger", width=inventory_width),
        *([[0] * inventory_width for _ in range(53)]),
    ]
    captured_inventory = {
        "inv_letters": [97, 98, *([0] * 53)],
        "inv_glyphs": [801, 802, *([0] * 53)],
        "inv_oclasses": [37, 41, *([0] * 53)],
        "inv_strs": inventory_strings,
    }
    task = {
        "task_id": "capture-state-regression",
        "seed": 101,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 2},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": hero[0], "y": hero[1], "glyph": 333, "color": 14},
            "glyphs": glyphs,
            "colors": colors,
            "seen": seen_mask(hero),
            "unseen": {"chars": unseen_chars, "glyphs": unseen_glyphs, "colors": unseen_colors},
            "inventory": [
                {"id": "ration", "letter": "a", "kind": "%", "name": "a runtime ration", "glyph": 501, "color": 2, "oclass_code": 37},
                {"id": "dagger", "letter": "b", "kind": ")", "name": "a runtime dagger", "glyph": 502, "color": 3, "oclass_code": 41},
            ],
            "metadata": {
                "hp": 17,
                "hp_max": 19,
                "gold": 77,
                "energy": 3,
                "energy_max": 9,
                "ac": -2,
                "experience_level": 2,
                "experience": 55,
                "hunger": 900,
                "nle_blstats": baseline_blstats,
                "nle_message_raw": capture_buffer(initial_message, width=message_width),
                "nle_inventory": captured_inventory,
            },
        },
    }
    expected = {
        "hero": hero,
        "revealed_on_move": revealed_on_move,
        "baseline_blstats": baseline_blstats,
        "initial_message": initial_message,
        "initial_message_raw": capture_buffer(initial_message, width=message_width),
        "wait_message_raw": capture_buffer("You wait.", width=message_width),
        "search_message_raw": capture_buffer("", width=message_width),
        "eat_message_raw": capture_buffer("What do you want to eat? [a or ?*] ", width=message_width),
        "inventory": {
            "inv_letters": captured_inventory["inv_letters"],
            "inv_glyphs": captured_inventory["inv_glyphs"],
            "inv_oclasses": captured_inventory["inv_oclasses"],
            "inv_strs": ["a - captured ration", "b - captured dagger", *([""] * 53)],
        },
    }
    return task, expected


def door_state_task(closed_glyph: int) -> dict[str, Any]:
    """Build a glyph-identified door case without conflating it with floor."""

    hero = (5, 4)
    door = (6, 4)
    beyond = (7, 4)
    terrain = [[" "] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    glyphs = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    colors = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
    for x in range(4, 9):
        terrain[4][x] = "."
        glyphs[4][x] = 2378
        colors[4][x] = 7
    terrain[door[1]][door[0]] = "+"
    glyphs[door[1]][door[0]] = closed_glyph
    colors[door[1]][door[0]] = 3
    return {
        "task_id": f"hypothesis-door-{closed_glyph}",
        "seed": closed_glyph,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": hero[0], "y": hero[1], "glyph": 340, "color": 15},
            "glyphs": glyphs,
            "colors": colors,
            "seen": seen_mask(hero, door),
            "unseen": {
                "chars": [[" "] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)],
                "glyphs": [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)],
                "colors": [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)],
            },
            "metadata": {"hp": 14, "hp_max": 14, "hunger": 900},
        },
        "door": door,
        "beyond": beyond,
    }


def reset_engine(task: dict[str, Any]) -> NethackDlvl1Engine:
    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    return engine


def apply_tape(engine: NethackDlvl1Engine, actions: list[int | str]) -> None:
    for action in actions:
        if engine.state["terminated"] or engine.state["truncated"]:
            return
        engine.step(action)


def python_public_trace(task: dict[str, Any], actions: list[int | str]) -> list[dict[str, Any]]:
    engine = reset_engine(task)
    snapshots = [engine.public_projection()]
    for action in actions:
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        engine.step(action)
        snapshots.append(engine.public_projection())
    return snapshots


def run_rust(arguments: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "scenario",
            "--",
            *arguments,
        ],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def rust_public_trace(task: dict[str, Any], actions: list[int | str]) -> list[dict[str, Any]]:
    result = run_rust(["--trace-stdin"], {**deepcopy(task), "actions": list(actions)})
    return list(result["snapshots"])


def rust_restore(checkpoint: bytes, actions: list[int | str]) -> dict[str, Any]:
    return run_rust(
        ["--checkpoint-replay-stdin"],
        {"checkpoint": checkpoint.decode("utf-8"), "actions": list(actions)},
    )


def frozen_nle_projection(public: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields persisted by an NLE frozen snapshot."""

    inventory = public["inventory"]
    return {
        "chars": list(public["chars"]),
        "colors": public["colors"],
        "glyphs": public["glyphs"],
        "blstats": public["blstats"],
        "message": public["message"],
        "message_raw": public["message_raw"],
        "inventory": {
            "inv_letters": inventory["inv_letters"],
            "inv_glyphs": inventory["inv_glyphs"],
            "inv_oclasses": inventory["inv_oclasses"],
            "inv_strs": inventory["inv_strs"],
        },
    }


def write_descend_boundary_fixture(root: Path, task: dict[str, Any], *, fixture_id: str) -> Path:
    """Build a no-NLE frozen fixture whose step one is pre-dlvl2 by contract."""

    down_id = next(int(action_id) for action_id, canonical, _ in PINNED_ACTIONS if canonical == "MiscDirection.DOWN")
    pre_action = frozen_nle_projection(reset_engine(task).public_projection())
    fixture_dir = root / fixture_id
    fixture_dir.mkdir()
    (fixture_dir / "meta.json").write_text(
        json.dumps({"fixture_id": fixture_id, "seed": task["seed"], "character": {}, "auto_more": "raw_explicit"})
    )
    (fixture_dir / "level_dump.json").write_text(json.dumps(task["level_dump"]))
    (fixture_dir / "actions.jsonl").write_text(
        json.dumps(
            {
                "step": 1,
                "action_id": down_id,
                "action_name": "MiscDirection.DOWN",
                "boundary": "dlvl1_descend",
            }
        )
        + "\n"
    )
    snapshots = (
        {"step": 0, "projection": pre_action, "done": False, "terminal_reason": ""},
        {
            "step": 1,
            "projection": pre_action,
            "done": True,
            "terminal_reason": "descended",
            "oracle_boundary": "pre_dlvl2",
        },
    )
    (fixture_dir / "snapshots.jsonl").write_text("".join(json.dumps(snapshot) + "\n" for snapshot in snapshots))
    return fixture_dir


def assert_public_contract(public: dict[str, Any], private: dict[str, Any]) -> None:
    """Assert the public API shape plus core cross-projection invariants."""

    assert public["schema"] == "gamebench.nethack.dlvl1.public.v1"
    assert public["blstats_fields"] == list(BLSTATS_FIELDS)
    assert len(public["blstats"]) == len(BLSTATS_FIELDS)
    assert public["blstats_named"] == dict(zip(BLSTATS_FIELDS, public["blstats"], strict=True))
    assert len(public["chars"]) == VIEW_HEIGHT
    assert len(public["colors"]) == VIEW_HEIGHT
    assert len(public["glyphs"]) == VIEW_HEIGHT
    for row in public["chars"]:
        assert isinstance(row, str)
        assert len(row) == VIEW_WIDTH
    for plane in (public["colors"], public["glyphs"]):
        for row in plane:
            assert len(row) == VIEW_WIDTH
            assert all(isinstance(value, int) for value in row)
    x, y = public["blstats"][:2]
    assert 0 <= x < VIEW_WIDTH
    assert 0 <= y < VIEW_HEIGHT
    assert public["chars"][y][x] == "@"
    assert private["hero"] == {"x": x, "y": y, "glyph": private["hero"]["glyph"], "color": private["hero"]["color"]}
    assert public["done"] == (public["terminated"] or public["truncated"])
    assert not (public["terminated"] and public["truncated"])
    if public["done"]:
        assert public["terminal_reason"] in TERMINAL_REASONS
    else:
        assert public["terminal_reason"] == ""
    assert public["input_mode"]["kind"] in KNOWN_INPUT_MODES
    inventory = public["inventory"]
    for key in ("inv_letters", "inv_glyphs", "inv_oclasses", "inv_strs"):
        assert len(inventory[key]) == 55
    assert all(isinstance(letter, int) and 0 <= letter <= 255 for letter in inventory["inv_letters"])
    letters = [item["letter"] for item in inventory["items"] if item["letter"]]
    assert len(letters) == len(set(letters))


PROPERTY_SETTINGS = settings(max_examples=12, deadline=None, derandomize=True, database=None)
RUST_PROPERTY_SETTINGS = settings(max_examples=6, deadline=None, derandomize=True, database=None)


class TestNetHackProperties(unittest.TestCase):
    def test_promotion_descend_boundary_requires_prior_raw_stair(self) -> None:
        actions = [
            {
                "step": 1,
                "action_id": 17,
                "action_name": "MiscDirection.DOWN",
                "boundary": "dlvl1_descend",
                "observed_down_stair": {"x": 1, "y": 0},
            }
        ]
        snapshots = [
            {"step": 0, "projection": {"chars": [[ord("@"), ord(">")]], "blstats": [0, 0]}},
            {
                "step": 1,
                "projection": {"chars": [[ord("@"), ord(">")]], "blstats": [1, 0]},
                "done": True,
                "terminal_reason": "descended",
                "oracle_boundary": "pre_dlvl2",
            },
        ]
        validate_descend_boundary(actions, snapshots)

        without_stair_evidence = deepcopy(snapshots)
        without_stair_evidence[0]["projection"]["chars"][0][1] = ord(".")
        with self.assertRaisesRegex(SystemExit, "lacks an auditable raw NLE down-stair observation"):
            validate_descend_boundary(actions, without_stair_evidence)

    def test_capture_hydrates_later_static_cell_and_preserves_initial_screen(self) -> None:
        """A dynamic reset glyph must not erase static terrain learned later."""

        initial = {
            "chars": [[ord("@"), ord("j"), ord(".")]],
            "glyphs": [[333, 501, 601]],
            "colors": [[15, 6, 7]],
            "blstats": [0, 0],
            "message": [],
            "inv_letters": [],
            "inv_glyphs": [],
            "inv_oclasses": [],
            "inv_strs": [],
        }
        later = deepcopy(initial)
        later["chars"][0][1] = ord(".")
        later["glyphs"][0][1] = 701
        later["colors"][0][1] = 12

        hydrated = level_dump(initial, {}, observations=[initial, later])
        self.assertEqual(".", hydrated["terrain"][0][1])
        self.assertEqual(701, hydrated["glyphs"][0][1])
        self.assertEqual(12, hydrated["colors"][0][1])
        self.assertTrue(hydrated["seen"][0][1])
        self.assertEqual(ord("j"), hydrated["unseen"]["chars"][0][1])
        self.assertEqual(501, hydrated["unseen"]["glyphs"][0][1])
        self.assertEqual(6, hydrated["unseen"]["colors"][0][1])

        underlaid = level_dump(
            initial,
            {"terrain_underlay": [{"x": 1, "y": 0, "char": ".", "glyph": 702, "color": 13}]},
        )
        self.assertEqual(".", underlaid["terrain"][0][1])
        self.assertEqual(702, underlaid["glyphs"][0][1])
        self.assertEqual(13, underlaid["colors"][0][1])
        hero_underlaid = level_dump(
            initial,
            {"terrain_underlay": [{"x": 0, "y": 0, "char": "<", "glyph": 703, "color": 7}]},
        )
        self.assertEqual("<", hero_underlaid["terrain"][0][0])
        self.assertEqual(703, hero_underlaid["glyphs"][0][0])
        self.assertEqual(7, hero_underlaid["colors"][0][0])
        with self.assertRaisesRegex(ValueError, "visible reset entity cell"):
            level_dump(
                initial,
                {"terrain_underlay": [{"x": 2, "y": 0, "char": "#", "glyph": 703, "color": 14}]},
            )
        with self.assertRaisesRegex(ValueError, "unsupported annotation keys: metadata"):
            level_dump(initial, {"metadata": {"hp": 999}})

        inventory_observation = deepcopy(initial)
        inventory_observation.update(
            {
                "inv_letters": [ord("d")],
                "inv_glyphs": [2174],
                "inv_oclasses": [7],
                "inv_strs": [capture_buffer("an uncursed food ration", width=32)],
            }
        )
        captured_inventory = level_dump(inventory_observation, {})["inventory"]
        self.assertEqual(
            [{"letter": "d", "kind": "%", "name": "an uncursed food ration", "oclass_code": 7}],
            [{key: item[key] for key in ("letter", "kind", "name", "oclass_code")} for item in captured_inventory],
        )

    def test_dark_corridor_visibility_stops_at_room_boundary_but_not_inside_corridor(self) -> None:
        """Keep the NLE entering-corridor boundary in both independent lanes."""

        def task(*, hero_on_corridor: bool) -> dict[str, Any]:
            result = adapter_task()
            result["rules"]["vision_radius"] = 5
            result["level_dump"]["hero"] = {"x": 5, "y": 4}
            result["level_dump"]["seen"] = seen_mask((5, 4))
            terrain = [list(row) for row in result["level_dump"]["terrain"]]
            if hero_on_corridor:
                for x in range(5, 10):
                    terrain[4][x] = "#"
            else:
                terrain[4][9] = "#"
            result["level_dump"]["terrain"] = ["".join(row) for row in terrain]
            return result

        room_trace = python_public_trace(task(hero_on_corridor=False), ["CompassDirection.E"])
        self.assertEqual(room_trace, rust_public_trace(task(hero_on_corridor=False), ["CompassDirection.E"]))
        self.assertEqual(" ", room_trace[-1]["chars"][4][9])

        corridor_trace = python_public_trace(task(hero_on_corridor=True), ["CompassDirection.E"])
        self.assertEqual(corridor_trace, rust_public_trace(task(hero_on_corridor=True), ["CompassDirection.E"]))
        self.assertEqual("#", corridor_trace[-1]["chars"][4][9])

    def test_capture_state_baselines_and_gold_owned_fov_match_across_lanes(self) -> None:
        task, expected = capture_state_task()
        python_trace = python_public_trace(task, ["MiscDirection.WAIT"])
        rust_trace = rust_public_trace(task, ["MiscDirection.WAIT"])
        self.assertEqual(python_trace, rust_trace)
        self.assertEqual(2, len(python_trace))
        reset, one_step = python_trace
        reveal_x, reveal_y = expected["revealed_on_move"]

        self.assertEqual(expected["baseline_blstats"], reset["blstats"])
        self.assertEqual(expected["initial_message"], reset["message"])
        self.assertEqual(expected["initial_message_raw"], reset["message_raw"])
        self.assertEqual(expected["inventory"], {key: reset["inventory"][key] for key in expected["inventory"]})
        self.assertEqual("?", reset["chars"][reveal_y][reveal_x])
        self.assertEqual(901, reset["glyphs"][reveal_y][reveal_x])
        self.assertEqual(31, reset["colors"][reveal_y][reveal_x])

        expected_one_step_blstats = list(expected["baseline_blstats"])
        expected_one_step_blstats[20] += 1
        expected_one_step_blstats[21] = 1
        self.assertEqual(expected_one_step_blstats, one_step["blstats"])
        self.assertEqual("You wait.", one_step["message"])
        self.assertEqual(expected["wait_message_raw"], one_step["message_raw"])
        self.assertEqual(expected["inventory"], {key: one_step["inventory"][key] for key in expected["inventory"]})
        self.assertEqual("?", one_step["chars"][reveal_y][reveal_x])
        self.assertEqual(901, one_step["glyphs"][reveal_y][reveal_x])
        self.assertEqual(31, one_step["colors"][reveal_y][reveal_x])

        python_search_trace = python_public_trace(task, ["Command.SEARCH"])
        rust_search_trace = rust_public_trace(task, ["Command.SEARCH"])
        self.assertEqual(python_search_trace, rust_search_trace)
        self.assertEqual(2, len(python_search_trace))
        search_step = python_search_trace[1]
        self.assertEqual("", search_step["message"])
        self.assertEqual(expected["search_message_raw"], search_step["message_raw"])
        self.assertEqual(expected_one_step_blstats, search_step["blstats"])

        python_move_trace = python_public_trace(task, ["CompassDirection.E"])
        rust_move_trace = rust_public_trace(task, ["CompassDirection.E"])
        self.assertEqual(python_move_trace, rust_move_trace)
        self.assertEqual(2, len(python_move_trace))
        move_step = python_move_trace[1]
        self.assertEqual([expected["hero"][0] + 1, expected["hero"][1]], move_step["blstats"][:2])
        self.assertEqual(".", move_step["chars"][reveal_y][reveal_x])
        self.assertEqual(411, move_step["glyphs"][reveal_y][reveal_x])
        self.assertEqual(44, move_step["colors"][reveal_y][reveal_x])

        python_open_trace = python_public_trace(task, ["Command.OPEN"])
        rust_open_trace = rust_public_trace(task, ["Command.OPEN"])
        self.assertEqual(python_open_trace, rust_open_trace)
        self.assertEqual(2, len(python_open_trace))
        open_prompt = python_open_trace[1]
        self.assertEqual("In what direction?", open_prompt["message"])
        self.assertEqual(
            {"kind": "direction", "command": "Command.OPEN", "prompt": "In what direction?", "operation": "open"},
            open_prompt["input_mode"],
        )
        self.assertEqual(
            capture_buffer("In what direction? ", width=len(expected["initial_message_raw"])),
            open_prompt["message_raw"],
        )

        python_eat_trace = python_public_trace(task, ["Command.EAT"])
        rust_eat_trace = rust_public_trace(task, ["Command.EAT"])
        self.assertEqual(python_eat_trace, rust_eat_trace)
        self.assertEqual(2, len(python_eat_trace))
        eat_prompt = python_eat_trace[1]
        self.assertEqual("What do you want to eat? [a or ?*]", eat_prompt["message"])
        self.assertEqual(
            {
                "kind": "inventory_letter",
                "command": "Command.EAT",
                "prompt": "What do you want to eat? [a or ?*]",
                "operation": "eat",
                "after": "normal",
            },
            eat_prompt["input_mode"],
        )
        self.assertEqual(expected["eat_message_raw"], eat_prompt["message_raw"])

    @RUST_PROPERTY_SETTINGS
    @given(closed_glyph=st.sampled_from((2374, 2375)))
    def test_glyph_identified_doors_preserve_orientation_visibility_and_checkpoints(self, closed_glyph: int) -> None:
        task = door_state_task(closed_glyph)
        door_x, door_y = task["door"]
        beyond_x, beyond_y = task["beyond"]
        opened_glyph = 2372 if closed_glyph == 2374 else 2373
        opened_char = "-" if closed_glyph == 2374 else "|"
        actions = ["Command.OPEN", "CompassDirection.E", "CompassDirection.E", "CompassDirection.W", "Command.CLOSE", "CompassDirection.E"]

        python_trace = python_public_trace(task, actions)
        rust_trace = rust_public_trace(task, actions)
        self.assertEqual(python_trace, rust_trace)
        before, open_prompt, opened, crossed, returned, close_prompt, closed = python_trace
        self.assertEqual("In what direction?", open_prompt["message"])
        self.assertEqual("The door opens.", opened["message"])
        self.assertEqual(opened_char, opened["chars"][door_y][door_x])
        self.assertEqual(opened_glyph, opened["glyphs"][door_y][door_x])
        self.assertEqual(3, opened["colors"][door_y][door_x])
        self.assertEqual(".", opened["chars"][beyond_y][beyond_x])
        self.assertEqual(before["blstats"][20] + 1, opened["blstats"][20])
        self.assertEqual([door_x, door_y], crossed["blstats"][:2])
        self.assertEqual([door_x - 1, door_y], returned["blstats"][:2])
        self.assertEqual("In what direction?", close_prompt["message"])
        self.assertEqual("The door closes.", closed["message"])
        self.assertEqual("+", closed["chars"][door_y][door_x])
        self.assertEqual(closed_glyph, closed["glyphs"][door_y][door_x])
        self.assertEqual(3, closed["colors"][door_y][door_x])

        engine = reset_engine(task)
        apply_tape(engine, actions[:2])
        checkpoint = engine.checkpoint_bytes()
        apply_tape(engine, actions[2:])
        restored = rust_restore(checkpoint, actions[2:])
        self.assertEqual(engine.symbolic_readout(), restored["projection"])

    def test_plain_terrain_door_remains_openable_without_a_glyph_plane(self) -> None:
        """Legacy authored '+' terrain is a behavioral fallback, not NLE evidence."""

        task = door_state_task(2374)
        door_x, door_y = task["door"]
        task["task_id"] = "hypothesis-plain-terrain-door"
        task["level_dump"]["glyphs"][door_y][door_x] = 0
        actions = ["Command.OPEN", "CompassDirection.E", "CompassDirection.E"]

        python_trace = python_public_trace(task, actions)
        rust_trace = rust_public_trace(task, actions)
        self.assertEqual(python_trace, rust_trace)
        opened = python_trace[2]
        self.assertEqual("The door opens.", opened["message"])
        self.assertEqual("-", opened["chars"][door_y][door_x])
        self.assertEqual(2372, opened["glyphs"][door_y][door_x])
        self.assertEqual([door_x, door_y], python_trace[3]["blstats"][:2])

    def test_frozen_descend_boundary_compares_pre_action_then_checks_terminal_contract(self) -> None:
        """Frozen dlvl-1 captures never compare a gold dlvl-2-adjacent message."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            descend_fixture = write_descend_boundary_fixture(root, explicit_stair_task(), fixture_id="descend")
            for lane in ("python", "rust"):
                self.assertEqual([], compare_fixture(descend_fixture, lane))

            no_stairs = explicit_stair_task()
            no_stairs["level_dump"]["terrain"] = room_terrain(hero_on_stairs=False)
            nonterminal_fixture = write_descend_boundary_fixture(root, no_stairs, fixture_id="not-descend")
            for lane in ("python", "rust"):
                failures = compare_fixture(nonterminal_fixture, lane)
                self.assertEqual(1, len(failures))
                self.assertIn("descent terminal contract", failures[0])

    def test_pickup_on_empty_down_stair_is_message_only_in_both_lanes(self) -> None:
        task = explicit_stair_task()
        self.assertEqual(">", task["level_dump"]["terrain"][4][5])
        self.assertNotIn("objects", task["level_dump"])

        python_trace = python_public_trace(task, ["Command.PICKUP"])
        rust_trace = rust_public_trace(task, ["Command.PICKUP"])
        self.assertEqual(python_trace, rust_trace)
        self.assertEqual(2, len(python_trace))
        before, after = python_trace
        self.assertEqual("The stairs are solidly fixed to the floor.", after["message"])
        self.assertEqual(before["blstats"], after["blstats"])

    def test_apply_without_an_applicable_tool_is_message_only_in_both_lanes(self) -> None:
        for task in (explicit_stair_task(), adapter_task()):
            python_trace = python_public_trace(task, ["Command.APPLY"])
            rust_trace = rust_public_trace(task, ["Command.APPLY"])
            self.assertEqual(python_trace, rust_trace)
            before, after = python_trace
            self.assertEqual("You don't have anything to use or apply.", after["message"])
            self.assertEqual(before["blstats"], after["blstats"])
            self.assertEqual("normal", after["input_mode"]["kind"])

    def test_apply_uses_nle_tool_prompt_and_letter_list_in_both_lanes(self) -> None:
        task = adapter_task()
        task["level_dump"]["inventory"].append({"id": "lamp", "kind": "(", "name": "an oil lamp"})
        python_trace = python_public_trace(task, ["Command.APPLY"])
        rust_trace = rust_public_trace(task, ["Command.APPLY"])
        self.assertEqual(python_trace, rust_trace)
        before, after = python_trace
        self.assertEqual("What do you want to use or apply? [c or ?*]", after["message"])
        self.assertEqual(before["blstats"], after["blstats"])
        self.assertEqual("inventory_letter", after["input_mode"]["kind"])

    def test_inventory_is_an_empty_message_zero_turn_display_command_in_both_lanes(self) -> None:
        task = adapter_task()
        python_trace = python_public_trace(task, ["Command.INVENTORY"])
        rust_trace = rust_public_trace(task, ["Command.INVENTORY"])
        self.assertEqual(python_trace, rust_trace)
        before, after = python_trace
        self.assertEqual("", after["message"])
        self.assertEqual([], after["message_raw"])
        self.assertEqual(before["blstats"], after["blstats"])
        self.assertEqual("inventory_display", after["input_mode"]["kind"])

    def test_captured_inventory_display_persists_until_escape_in_both_lanes(self) -> None:
        task = captured_inventory_task()
        actions = ["Command.INVENTORY", "Command.SEARCH", "Command.ESC"]
        python_trace = python_public_trace(task, actions)
        rust_trace = rust_public_trace(task, actions)
        self.assertEqual(python_trace, rust_trace)
        before, displayed, ignored, dismissed = python_trace
        self.assertEqual("inventory_display", displayed["input_mode"]["kind"])
        self.assertEqual("", displayed["message"])
        self.assertEqual(displayed["blstats"], ignored["blstats"])
        self.assertEqual("inventory_display", ignored["input_mode"]["kind"])
        self.assertEqual("normal", dismissed["input_mode"]["kind"])
        self.assertEqual("", dismissed["message"])
        self.assertEqual(before["blstats"], dismissed["blstats"])

    def test_quit_uses_the_nle_confirmation_prompt_in_both_lanes(self) -> None:
        task = adapter_task()
        python_trace = python_public_trace(task, ["Command.QUIT"])
        rust_trace = rust_public_trace(task, ["Command.QUIT"])
        self.assertEqual(python_trace, rust_trace)
        before, after = python_trace
        self.assertEqual("Really quit? [yn] (n)", after["message"])
        self.assertEqual(before["blstats"], after["blstats"])
        self.assertEqual("ynq", after["input_mode"]["kind"])

    def test_close_against_non_door_is_message_only_in_both_lanes(self) -> None:
        task = explicit_stair_task()
        actions = ["Command.CLOSE", "CompassDirection.E"]
        python_trace = python_public_trace(task, actions)
        rust_trace = rust_public_trace(task, actions)
        self.assertEqual(python_trace, rust_trace)
        before, prompt, after = python_trace
        self.assertEqual("In what direction?", prompt["message"])
        self.assertEqual("You see no door there.", after["message"])
        self.assertEqual(before["blstats"], after["blstats"])
        self.assertEqual("normal", after["input_mode"]["kind"])

    def test_all_pinned_ids_and_canonical_names_use_the_same_adapter(self) -> None:
        self.assertEqual(list(range(121)), [int(action_id) for action_id, _, _ in PINNED_ACTIONS])
        for action_id, canonical, value in PINNED_ACTIONS:
            for wire_input in (int(action_id), str(action_id), str(canonical)):
                action = coerce_action(wire_input)
                self.assertIsNotNone(action, wire_input)
                assert action is not None
                self.assertEqual(int(action_id), action.id)
                self.assertEqual(str(canonical), action.canonical)
                self.assertEqual(int(value), action.value)

        task = adapter_task()
        ids = [int(action_id) for action_id, _, _ in PINNED_ACTIONS]
        canonicals = [str(canonical) for _, canonical, _ in PINNED_ACTIONS]
        python_by_id = python_public_trace(task, ids)
        self.assertEqual(python_by_id, python_public_trace(task, canonicals))
        rust_by_id = rust_public_trace(task, ids)
        self.assertEqual(rust_by_id, rust_public_trace(task, canonicals))
        self.assertEqual(python_by_id, rust_by_id)

    def test_unsafe_action_aliases_are_accepted_in_both_lanes(self) -> None:
        self.assertEqual({"UnsafeActions.HELP", "UnsafeActions.PREVMSG"}, {str(canonical) for canonical, _ in UNSAFE_ACTIONS})
        expected_messages = {
            "UnsafeActions.HELP": "Use the action map for the full NLE command surface.",
            "UnsafeActions.PREVMSG": "No previous message.",
        }
        task = adapter_task()
        for canonical, keycode in UNSAFE_ACTIONS:
            canonical = str(canonical)
            raw_key = chr(int(keycode))
            inputs = (canonical, UNSAFE_ALIASES[canonical], raw_key, f"  {raw_key}  ")
            for wire_input in inputs:
                action = coerce_action(wire_input)
                self.assertIsNotNone(action, wire_input)
                assert action is not None
                self.assertIsNone(action.id)
                self.assertEqual(canonical, action.canonical)
                self.assertEqual(int(keycode), action.value)

            python_canonical = python_public_trace(task, [canonical])
            self.assertEqual(expected_messages[canonical], python_canonical[-1]["message"])
            self.assertEqual(python_canonical, python_public_trace(task, [UNSAFE_ALIASES[canonical]]))
            self.assertEqual(python_canonical, python_public_trace(task, [raw_key]))
            self.assertEqual(python_canonical, python_public_trace(task, [f"  {raw_key}  "]))

            rust_canonical = rust_public_trace(task, [canonical])
            self.assertEqual(python_canonical, rust_canonical)
            self.assertEqual(rust_canonical, rust_public_trace(task, [UNSAFE_ALIASES[canonical]]))
            self.assertEqual(rust_canonical, rust_public_trace(task, [raw_key]))
            self.assertEqual(rust_canonical, rust_public_trace(task, [f"  {raw_key}  "]))

    def test_raw_whitespace_action_keys_remain_literal_inputs(self) -> None:
        task = adapter_task()
        for action_id, canonical, raw_key in (
            (19, "MiscAction.MORE", "\r"),
            (107, "TextCharacters.SPACE", " "),
        ):
            action = coerce_action(raw_key)
            self.assertIsNotNone(action, raw_key)
            assert action is not None
            self.assertEqual(action_id, action.id)
            self.assertEqual(canonical, action.canonical)

            python_canonical = python_public_trace(task, [canonical])
            self.assertEqual(python_canonical, python_public_trace(task, [raw_key]))
            rust_canonical = rust_public_trace(task, [canonical])
            self.assertEqual(python_canonical, rust_canonical)
            self.assertEqual(rust_canonical, rust_public_trace(task, [raw_key]))

    def test_coverage_separates_selected_from_nle_stepped_ids(self) -> None:
        more_id = next(int(action_id) for action_id, canonical, _ in PINNED_ACTIONS if canonical == "MiscAction.MORE")
        down_id = next(int(action_id) for action_id, canonical, _ in PINNED_ACTIONS if canonical == "MiscDirection.DOWN")
        coverage = coverage_report(
            [list(action) for action in PINNED_ACTIONS],
            [
                {
                    "meta": {"fixture_id": "coverage-metric-boundary"},
                    "actions": [
                        {"action_id": more_id, "action_name": "MiscAction.MORE", "input_mode": "normal", "selection": "provided_tape", "nle_stepped": True},
                        {"action_id": down_id, "action_name": "MiscDirection.DOWN", "input_mode": "normal", "selection": "provided_tape", "boundary": "dlvl1_descend", "nle_stepped": False},
                    ],
                    "snapshots": [{"projection": {"blstats": []}, "terminal_reason": ""}],
                    "report": {"lanes": []},
                }
            ],
        )
        self.assertEqual(sorted([more_id, down_id]), coverage["action_ids"]["selected"])
        self.assertEqual([more_id], coverage["action_ids"]["nle_stepped"])
        self.assertEqual(2, coverage["action_ids"]["selected_count"])
        self.assertEqual(1, coverage["action_ids"]["nle_stepped_count"])

    @PROPERTY_SETTINGS
    @given(case=constrained_case())
    def test_public_observation_invariants_for_constrained_tapes(self, case: tuple[dict[str, Any], list[str]]) -> None:
        task, actions = case
        engine = reset_engine(task)
        assert_public_contract(engine.public_projection(), engine.private_projection())
        for action in actions:
            if engine.state["terminated"] or engine.state["truncated"]:
                break
            engine.step(action)
            assert_public_contract(engine.public_projection(), engine.private_projection())

    @PROPERTY_SETTINGS
    @given(case=constrained_case())
    def test_python_replay_and_checkpoint_round_trip_are_deterministic(self, case: tuple[dict[str, Any], list[str]]) -> None:
        task, actions = case
        first_trace = python_public_trace(task, actions)
        second_trace = python_public_trace(task, actions)
        self.assertEqual(first_trace, second_trace)

        cut = len(actions) // 2
        uninterrupted = reset_engine(task)
        apply_tape(uninterrupted, actions[:cut])
        checkpoint = uninterrupted.checkpoint_bytes()
        self.assertEqual(checkpoint, uninterrupted.clone_for_sim().checkpoint_bytes())
        apply_tape(uninterrupted, actions[cut:])

        restored = NethackDlvl1Engine()
        restored.restore_checkpoint(checkpoint)
        apply_tape(restored, actions[cut:])
        self.assertEqual(uninterrupted.symbolic_readout(), restored.symbolic_readout())

    @RUST_PROPERTY_SETTINGS
    @given(case=constrained_case())
    def test_python_rust_trace_and_checkpoint_bridge_agree(self, case: tuple[dict[str, Any], list[str]]) -> None:
        task, actions = case
        self.assertEqual(python_public_trace(task, actions), rust_public_trace(task, actions))

        cut = len(actions) // 2
        python = reset_engine(task)
        apply_tape(python, actions[:cut])
        checkpoint = python.checkpoint_bytes()
        apply_tape(python, actions[cut:])
        restored = rust_restore(checkpoint, actions[cut:])
        self.assertEqual(python.symbolic_readout(), restored["projection"])

    @PROPERTY_SETTINGS
    @given(actions=st.lists(st.sampled_from(ACTION_POOL), min_size=0, max_size=8))
    def test_terminal_public_projection_is_sticky(self, actions: list[str]) -> None:
        engine = reset_engine(explicit_stair_task())
        engine.step("MiscDirection.DOWN")
        terminal = engine.public_projection()
        self.assertTrue(terminal["done"])
        self.assertTrue(terminal["terminated"])
        self.assertEqual("descended", terminal["terminal_reason"])
        for action in actions:
            engine.step(action)
            self.assertEqual(terminal, engine.public_projection())


class NetHackPublicInvariantMachine(RuleBasedStateMachine):
    """Exercise state transitions while maintaining the public API invariant."""

    def __init__(self) -> None:
        super().__init__()
        task = {
            "task_id": "hypothesis-state-machine",
            "seed": 19,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
            "level_dump": {
                "terrain": room_terrain(),
                "inventory": [
                    {"id": "ration", "kind": "%", "name": "a food ration", "nutrition": 600},
                    {"id": "dagger", "kind": ")", "name": "a dagger", "damage": 2},
                ],
                "objects": [{"id": "floor-ration", "position": {"x": 6, "y": 4}, "kind": "%", "name": "a floor ration", "nutrition": 600}],
                "monsters": [{"id": "jackal", "name": "jackal", "char": "j", "position": {"x": 8, "y": 4}, "hp": 4, "attack": 1, "experience": 2}],
                "traps": [{"id": "dart-trap", "kind": "dart", "position": {"x": 4, "y": 4}, "damage": 1}],
                "metadata": {"hp": 20, "hp_max": 20, "hunger": 900},
            },
        }
        self.engine = reset_engine(task)

    @rule(action=st.sampled_from(ACTION_POOL))
    def apply_action(self, action: str) -> None:
        before = self.engine.public_projection()
        self.engine.step(action)
        if before["done"]:
            assert self.engine.public_projection() == before

    @precondition(lambda self: not self.engine.state["terminated"] and not self.engine.state["truncated"] and self.engine.state["input_mode"]["kind"] == "normal")
    @rule()
    def open_prompt_can_be_cancelled(self) -> None:
        self.engine.step("Command.OPEN")
        assert self.engine.public_projection()["input_mode"]["kind"] == "direction"
        self.engine.step("Command.ESC")
        assert self.engine.public_projection()["input_mode"]["kind"] == "normal"

    @invariant()
    def public_observation_stays_well_formed(self) -> None:
        assert_public_contract(self.engine.public_projection(), self.engine.private_projection())


TestNetHackPublicInvariantMachine = NetHackPublicInvariantMachine.TestCase
TestNetHackPublicInvariantMachine.settings = settings(
    max_examples=8,
    stateful_step_count=10,
    deadline=None,
    derandomize=True,
    database=None,
)
