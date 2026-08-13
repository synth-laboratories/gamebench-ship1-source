#!/usr/bin/env python3
"""ROM-free tests for differential-fuzz minimisation helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).with_name("fuzz_emerald_differential.py")
SPEC = importlib.util.spec_from_file_location("emerald_fuzz", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
FUZZ = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FUZZ
SPEC.loader.exec_module(FUZZ)


def frame(*, pixels_equal: bool, semantic_equal: bool, world: dict | None = None):
    return FUZZ.OracleReplayFrame(
        vblank=1,
        button="start",
        rust_rgb=b"a" if pixels_equal else b"a",
        source_rgb=b"a" if pixels_equal else b"b",
        rust_readout={"world": world or {"map": "mays_house2_f"}},
        source_response={"source_state": {"map_group": 1, "map_number": 3}},
        semantic_equal=semantic_equal,
    )


class EmeraldFuzzHelpersTest(unittest.TestCase):
    def test_bedroom_targeted_tapes_pin_transition_boundaries(self) -> None:
        _, checkpoint = FUZZ.load_oracle_checkpoint("bedroom_idle")
        tapes = {tape["name"]: tape for tape in FUZZ.source_tapes(7, 0, 1, checkpoint)}
        select = tapes["fixture_select_modal_open_close"]
        self.assertEqual(67, len(select["tape"]))
        self.assertEqual([1, 4, 5, 64, 65, 67], select["semantic_boundaries"])
        self.assertEqual("select", select["tape"][0])
        self.assertEqual("b", select["tape"][64])

        handoff = tapes["fixture_start_menu_handoff"]
        self.assertEqual([1, 8, 9, 10], handoff["semantic_boundaries"])
        self.assertEqual(["start", *(["noop"] * 7), "up", "up"], handoff["tape"])

        north_exit = tapes["fixture_bedroom_north_exit_settle"]
        self.assertEqual(208, len(north_exit["tape"]))
        self.assertEqual([16, 32, 48, 64, 80, 208], north_exit["semantic_boundaries"])

    def test_mays_house_segment_starts_from_authenticated_bedroom(self) -> None:
        _, checkpoint = FUZZ.load_oracle_checkpoint("bedroom_idle")
        tapes = {
            tape["name"]: tape
            for tape in FUZZ.source_tapes(7, 0, 64, checkpoint, "mays_house_exit")
        }
        self.assertEqual(
            ["fixture_mays_house_1f_transition", "fixture_mays_house_1f_exit_to_littleroot"],
            list(tapes),
        )
        self.assertEqual(208, len(tapes["fixture_mays_house_1f_transition"]["tape"]))
        self.assertEqual(5134, len(tapes["fixture_mays_house_1f_exit_to_littleroot"]["tape"]))
        self.assertEqual(
            14,
            tapes["fixture_mays_house_1f_exit_to_littleroot"]["tape"].count("a"),
            "the fourteen source dialogue pages include their debounced A edges",
        )
        self.assertEqual("bedroom_idle", checkpoint.checkpoint_id)
        self.assertEqual("authenticated", checkpoint.status)

    def test_clock_tv_segment_pins_full_downstairs_program(self) -> None:
        _, checkpoint = FUZZ.load_oracle_checkpoint("bedroom_idle")
        tapes = FUZZ.source_tapes(7, 0, 64, checkpoint, "clock_tv")
        self.assertEqual(1, len(tapes))
        clock = tapes[0]
        self.assertEqual("fixture_bedroom_clock_tv_downstairs", clock["name"])
        self.assertEqual(3466, len(clock["tape"]))
        self.assertEqual(16, clock["tape"].count("a"))
        self.assertEqual([2986, 3226, 3466], clock["semantic_boundaries"][-3:])
        self.assertEqual("bedroom_idle", checkpoint.checkpoint_id)
        self.assertEqual("authenticated", checkpoint.status)

    def test_littleroot_field_segment_pins_long_camera_and_collision_holds(self) -> None:
        _, checkpoint = FUZZ.load_oracle_checkpoint("littleroot_field_ready")
        tapes = {
            tape["name"]: tape
            for tape in FUZZ.source_tapes(7, 0, 64, checkpoint, "littleroot_field")
        }
        self.assertEqual(
            [
                "fixture_littleroot_field_left_144",
                "fixture_littleroot_field_right_48",
                "fixture_littleroot_field_down_48",
                "fixture_littleroot_field_up_blocked_16",
            ],
            list(tapes),
        )
        self.assertEqual(144, len(tapes["fixture_littleroot_field_left_144"]["tape"]))
        self.assertEqual(48, len(tapes["fixture_littleroot_field_right_48"]["tape"]))
        self.assertEqual(48, len(tapes["fixture_littleroot_field_down_48"]["tape"]))
        self.assertEqual(16, len(tapes["fixture_littleroot_field_up_blocked_16"]["tape"]))
        self.assertEqual("littleroot_field_ready", checkpoint.checkpoint_id)
        self.assertEqual("authenticated", checkpoint.status)

    def test_route101_segment_separates_reload_receipt_from_live_pulse(self) -> None:
        _, checkpoint = FUZZ.load_oracle_checkpoint("route101_west_lane")
        tapes = {
            tape["name"]: tape
            for tape in FUZZ.source_tapes(7, 0, 64, checkpoint, "route101")
        }
        self.assertEqual(
            [
                "fixture_route101_west_lane_settled",
                "fixture_route101_west_lane_next_pulse",
            ],
            list(tapes),
        )
        self.assertEqual([], tapes["fixture_route101_west_lane_settled"]["tape"])
        self.assertEqual(
            ["noop"] * 16 + ["up"] * 16,
            tapes["fixture_route101_west_lane_next_pulse"]["tape"],
        )
        self.assertEqual("route101_west_lane", checkpoint.checkpoint_id)
        self.assertEqual("authenticated", checkpoint.status)

    def test_selects_first_requested_divergence(self) -> None:
        frames = [
            frame(pixels_equal=True, semantic_equal=True),
            frame(pixels_equal=False, semantic_equal=True),
            frame(pixels_equal=False, semantic_equal=False),
        ]
        self.assertIs(frames[1], FUZZ.first_selected_divergence(frames, "pixel"))
        self.assertIs(frames[2], FUZZ.first_selected_divergence(frames, "semantic"))

    def test_ddmin_deletes_and_neutralises_irrelevant_input(self) -> None:
        # This is a pure stand-in for a fresh oracle replay predicate: failure
        # requires the ordered A/B interaction, not any timing-specific index.
        calls: list[list[str]] = []

        def reproduces(tape: list[str]) -> bool:
            calls.append(list(tape))
            return any(
                tape[index : index + 2] == ["a", "b"]
                for index in range(len(tape) - 1)
            )

        result = FUZZ.ddmin_tape(["left", "a", "b", "right", "start"], reproduces)
        self.assertEqual(["a", "b"], result)
        self.assertGreater(len(calls), 1)

    def test_attribution_uses_transition_then_ui_then_field_evidence(self) -> None:
        transition = FUZZ.classify_failure_surface(
            frame(pixels_equal=False, semantic_equal=True, world={"transition": {"fade": 1}}),
            [],
        )
        self.assertEqual("transition", transition["surface"])
        ui = FUZZ.classify_failure_surface(
            frame(pixels_equal=False, semantic_equal=True, world={"menu_open": True}),
            [],
        )
        self.assertEqual("menu_ui", ui["surface"])
        field = FUZZ.classify_failure_surface(
            frame(pixels_equal=False, semantic_equal=True), ["left", "down"]
        )
        self.assertEqual("field", field["surface"])

    def test_bad_minimisation_target_never_becomes_success(self) -> None:
        with self.assertRaises(FUZZ.HarnessError):
            FUZZ.ddmin_tape(["a"], lambda _tape: False)


if __name__ == "__main__":
    unittest.main()
