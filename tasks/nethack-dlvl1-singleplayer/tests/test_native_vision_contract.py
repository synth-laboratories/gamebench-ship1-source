"""Unit checks for the source-only ``vision_recalc`` decision-input export."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_native_map_fov import (  # noqa: E402
    EXPECTED_LEVEL_FLAGS_ABI,
    EXPECTED_VISION_INPUT_ABI,
    IN_SIGHT,
    NativeMapFovSnapshot,
    OBS_COLNO,
    ROWNO,
    validate_semantic_vision_export,
    validate_level_flags_export,
)


def grid(value: object) -> tuple[tuple[object, ...], ...]:
    return tuple(tuple(value for _ in range(OBS_COLNO)) for _ in range(ROWNO))


def snapshot() -> NativeMapFovSnapshot:
    inputs = {
        "hero": {"native_x": 1, "native_y": 0, "night_vision_range": 1, "xray_range": -1, "swallowed": False, "underwater": False, "pit_trapped": False},
        "level": {"rogue_level": False, "water_level": False, "underwater_branch_active": False},
        "blindness": {"roleplay_blind": False, "blinded_intrinsic": 0, "blindfolded": False, "has_eyes": True, "eyes_of_overworld_override": False, "cream_timeout": 0, "blind": False},
        "senses": {
            "see_invisible": {"intrinsic": 0, "extrinsic": 0, "effective": False},
            "infravision": {"intrinsic": 0, "extrinsic": 0, "effective": False, "vision_recalc_input": False},
        },
    }
    blockers = {"boulder": [list(row) for row in grid(False)], "visible_mimic": [list(row) for row in grid(False)], "effective": [list(row) for row in grid(False)], "records": []}
    return NativeMapFovSnapshot(
        terrain_type=grid(24), terrain_flags=grid(0), terrain_horizontal=grid(False),
        map_memory_glyph=grid(2378), map_memory_seenv=grid(0),
        visibility_bits=grid(IN_SIGHT), binary_sha256="pinned",
        terrain_lit=grid(True), terrain_was_lit=grid(True), vision_inputs=inputs,
        dynamic_blockers=blockers, light_sources=(),
        recalc_state={"full_recalc_pending": False, "vision_initialized": True, "in_level_generation": False},
        compiler_vision_abi=EXPECTED_VISION_INPUT_ABI,
    )


class NativeVisionContractTests(unittest.TestCase):
    def test_complete_source_extension_separates_lighting_blockers_and_presentation(self) -> None:
        record = snapshot().public_record()
        self.assertEqual([], validate_semantic_vision_export(record))
        self.assertTrue(record["lighting"]["static_lit"][0][0])
        self.assertFalse(record["lighting"]["temporary_lit"][0][0])
        self.assertFalse(record["vision_decision_inputs"]["senses"]["infravision"]["vision_recalc_input"])
        self.assertFalse(record["gold_implementation_eligible"])
        self.assertEqual(list(EXPECTED_VISION_INPUT_ABI), record["abi_layout"]["independent_clang_vision_input_check"]["result"])

    def test_partial_extension_and_recomputed_digest_tampering_fail_closed(self) -> None:
        record = snapshot().public_record()
        partial = deepcopy(record)
        partial.pop("lighting")
        self.assertIn("partial", "; ".join(validate_semantic_vision_export(partial)))

        forged = deepcopy(record)
        forged["dynamic_vision_blockers"]["effective"][0][0] = True
        # An attacker may recompute the outer record hash; this structural
        # validator still catches the stale inner plane digest/union.
        failures = "; ".join(validate_semantic_vision_export(forged))
        self.assertIn("plane digest mismatch", failures)

    def test_blindness_and_underwater_equivalence_predicates_are_not_free_text(self) -> None:
        record = snapshot().public_record()
        malformed = deepcopy(record)
        malformed["vision_decision_inputs"]["blindness"]["blind"] = True
        self.assertIn("blindness macro mismatch", "; ".join(validate_semantic_vision_export(malformed)))
        malformed = deepcopy(record)
        malformed["vision_decision_inputs"]["level"]["underwater_branch_active"] = True
        self.assertIn("level predicate mismatch", "; ".join(validate_semantic_vision_export(malformed)))

    def test_level_flags_extension_is_abi_bound_and_source_only(self) -> None:
        flags = {
            "nfountains": 1, "nsinks": 0, "has_shop": False, "has_vault": False,
            "has_zoo": False, "has_court": False, "has_morgue": False,
            "has_beehive": False, "has_barracks": False, "has_temple": False,
            "has_swamp": False, "noteleport": False, "hardfloor": False,
            "nommap": False, "hero_memory": True, "shortsighted": False,
            "graveyard": False, "sokoban_rules": False, "is_maze_lev": False,
            "is_cavernous_lev": False, "arboreal": False, "wizard_bones": False,
            "corrmaze": False,
        }
        record = NativeMapFovSnapshot(
            terrain_type=grid(24), terrain_flags=grid(0), terrain_horizontal=grid(False),
            map_memory_glyph=grid(2378), map_memory_seenv=grid(0), visibility_bits=grid(IN_SIGHT),
            binary_sha256="pinned", level_flags=flags,
        ).public_record()
        self.assertEqual([], validate_level_flags_export(record))
        self.assertEqual(list(EXPECTED_LEVEL_FLAGS_ABI), record["abi_layout"]["independent_clang_level_flags_check"]["result"])
        forged = deepcopy(record)
        forged["semantic_level_flags"]["abi"]["flags_offset"] += 1
        self.assertIn("ABI contract", "; ".join(validate_level_flags_export(forged)))
        partial = deepcopy(record)
        partial.pop("semantic_level_flags")
        self.assertIn("both", "; ".join(validate_level_flags_export(partial)))


if __name__ == "__main__":
    unittest.main()
