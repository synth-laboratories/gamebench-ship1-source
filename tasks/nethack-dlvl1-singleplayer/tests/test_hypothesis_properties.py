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
from typing import Any

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from gold_python.action_map import coerce_action
from scripts.fuzz_nle_differential import coverage_report
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
