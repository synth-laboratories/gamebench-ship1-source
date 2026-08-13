"""Unit checks for the replay-gated dynamic-vision source audit."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_native_map_fov import (  # noqa: E402
    EXPECTED_VISION_INPUT_ABI,
    IN_SIGHT,
    NativeMapFovSnapshot,
    OBS_COLNO,
    PINNED_BINARY_SHA256,
    ROWNO,
)
from scripts.verify_native_dynamic_vision_inputs import (  # noqa: E402
    DEFAULT_ACTIONS,
    INPUT_KINDS,
    SCHEMA,
    _observed_counts,
    assess_dynamic_vision_inputs,
)


def grid(value: object) -> tuple[tuple[object, ...], ...]:
    return tuple(tuple(value for _ in range(OBS_COLNO)) for _ in range(ROWNO))


def snapshot() -> dict:
    boulder = [list(row) for row in grid(False)]
    boulder[3][4] = True
    inputs = {
        "hero": {"native_x": 1, "native_y": 0, "night_vision_range": 1, "xray_range": -1, "swallowed": False, "underwater": False, "pit_trapped": False},
        "level": {"rogue_level": False, "water_level": False, "underwater_branch_active": False},
        "blindness": {"roleplay_blind": False, "blinded_intrinsic": 0, "blindfolded": False, "has_eyes": True, "eyes_of_overworld_override": False, "cream_timeout": 0, "blind": False},
        "senses": {"see_invisible": {"intrinsic": 0, "extrinsic": 0, "effective": False}, "infravision": {"intrinsic": 0, "extrinsic": 0, "effective": False, "vision_recalc_input": False}},
    }
    blockers = {
        "boulder": boulder,
        "visible_mimic": [list(row) for row in grid(False)],
        "effective": boulder,
        "records": [{"kind": "boulder", "x": 4, "y": 3, "native_x": 5, "object_id": 1, "object_type": 447}],
    }
    return NativeMapFovSnapshot(
        terrain_type=grid(24), terrain_flags=grid(0), terrain_horizontal=grid(False),
        map_memory_glyph=grid(2378), map_memory_seenv=grid(0), visibility_bits=grid(IN_SIGHT),
        binary_sha256=PINNED_BINARY_SHA256, terrain_lit=grid(True), terrain_was_lit=grid(True),
        vision_inputs=inputs, dynamic_blockers=blockers, light_sources=(),
        recalc_state={"full_recalc_pending": False, "vision_initialized": True, "in_level_generation": False},
        compiler_vision_abi=EXPECTED_VISION_INPUT_ABI,
    ).public_record()


class NativeDynamicVisionInputTests(unittest.TestCase):
    def test_source_records_exactly_cover_positive_boulder_plane(self) -> None:
        assessed = assess_dynamic_vision_inputs(snapshot())
        self.assertEqual(1, assessed["boulder_cells"])
        self.assertEqual(1, assessed["effective_blocker_cells"])
        self.assertEqual(0, assessed["visible_mimic_cells"])
        self.assertGreater(assessed["source_record_plane_comparisons"], 0)

    def test_record_plane_disagreement_and_wrong_binary_fail_closed(self) -> None:
        forged = snapshot()
        forged["dynamic_vision_blockers"]["records"] = []
        with self.assertRaisesRegex(AssertionError, "records do not exactly cover"):
            assess_dynamic_vision_inputs(forged)
        wrong_binary = snapshot()
        wrong_binary["binary_sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "exact pinned"):
            assess_dynamic_vision_inputs(wrong_binary)

    def test_positive_coverage_counts_all_predeclared_boundaries(self) -> None:
        assessed = assess_dynamic_vision_inputs(snapshot())
        empty = deepcopy(assessed)
        empty.update({"boulder_cells": 0, "visible_mimic_cells": 0, "active_light_sources": 0})
        counts = _observed_counts([{"initial_assessment": assessed, "boundaries": [{"before_assessment": empty, "after_assessment": assessed}]}])
        self.assertEqual(2, counts["boulder"])
        self.assertEqual(0, counts["mimic"])
        self.assertEqual(0, counts["light"])

    def test_contract_never_marks_gold_eligible(self) -> None:
        self.assertEqual("gamebench.nethack.native_dynamic_vision_input_audit.v1", SCHEMA)
        self.assertEqual(("MiscDirection.WAIT", "Command.SEARCH"), DEFAULT_ACTIONS)
        self.assertEqual(("boulder", "mimic", "light"), INPUT_KINDS)


if __name__ == "__main__":
    unittest.main()
