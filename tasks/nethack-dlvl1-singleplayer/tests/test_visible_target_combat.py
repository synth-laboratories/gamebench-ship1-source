"""Validity guards for the live source-visible combat oracle."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.verify_visible_target_combat import PROMPT_RAW_TEXT, expected_raw, source_combat_target


class FakeSpecies:
    mname = "newt"


class FakeNethack:
    MG_PET = 8

    @staticmethod
    def glyph_is_monster(glyph: int) -> bool:
        return glyph in {101, 102}

    @staticmethod
    def glyph_is_pet(glyph: int) -> bool:
        return glyph == 102

    @staticmethod
    def glyph_to_mon(glyph: int) -> int:
        return glyph - 100

    @staticmethod
    def permonst(monster_id: int) -> FakeSpecies:
        assert monster_id == 1
        return FakeSpecies()


def reset(glyph: int, special: int = 0) -> dict[str, object]:
    return {
        "blstats": [1, 1],
        "chars": [[ord("."), ord("."), ord(".")], [ord("."), ord("@"), ord("n")], [ord("."), ord("."), ord(".")]],
        "glyphs": [[0, 0, 0], [0, 0, glyph], [0, 0, 0]],
        "colors": [[0, 0, 0], [0, 0, 2], [0, 0, 0]],
        "specials": [[0, 0, 0], [0, 0, special], [0, 0, 0]],
    }


class VisibleTargetCombatTests(unittest.TestCase):
    def test_normal_monster_is_observable_but_not_implementation_eligible(self) -> None:
        target = source_combat_target(reset(101), FakeNethack())
        assert target is not None
        self.assertEqual("E", target["direction"])
        self.assertEqual("newt", target["species_name"])
        self.assertFalse(target["implementation_eligible"])
        self.assertIn("no_source_hp_or_combat_rng_state", target["ineligibility"])

    def test_pet_surface_is_a_negative_control(self) -> None:
        self.assertIsNone(source_combat_target(reset(102), FakeNethack()))
        self.assertIsNone(source_combat_target(reset(101, special=8), FakeNethack()))

    def test_prompt_encoding_is_exact_and_bounded(self) -> None:
        self.assertEqual(list(PROMPT_RAW_TEXT.encode("ascii")) + [0, 0], expected_raw(PROMPT_RAW_TEXT, len(PROMPT_RAW_TEXT) + 2))
        with self.assertRaises(ValueError):
            expected_raw(PROMPT_RAW_TEXT, 2)


if __name__ == "__main__":
    unittest.main()
