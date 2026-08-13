"""Unit guards for the validity boundary of the live dynamic-pet probe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.verify_dynamic_pet_presentation import classify_transition


class FakeNethack:
    MG_PET = 8

    @staticmethod
    def glyph_is_pet(glyph: int) -> bool:
        return glyph == 397

    @staticmethod
    def glyph_is_cmap(glyph: int) -> bool:
        return glyph == 2359


def snapshot(*, pet_x: int, pet_y: int, time: int, hero: tuple[int, int] = (0, 0), destination_char: str = ".") -> dict[str, object]:
    glyphs = [[2359 for _ in range(4)] for _ in range(3)]
    chars = [[ord(destination_char) for _ in range(4)] for _ in range(3)]
    colors = [[7 for _ in range(4)] for _ in range(3)]
    specials = [[0 for _ in range(4)] for _ in range(3)]
    glyphs[pet_y][pet_x] = 397
    chars[pet_y][pet_x] = ord("d")
    specials[pet_y][pet_x] = 8
    stats = [0] * 27
    stats[0], stats[1], stats[20] = hero[0], hero[1], time
    return {"glyphs": glyphs, "chars": chars, "colors": colors, "specials": specials, "blstats": stats}


class DynamicPetPresentationTests(unittest.TestCase):
    def test_same_pet_pixel_is_presentation_continuity_not_identity(self) -> None:
        result = classify_transition(snapshot(pet_x=1, pet_y=1, time=1), snapshot(pet_x=1, pet_y=1, time=2), nethack=FakeNethack())
        self.assertEqual("presentation_continuity_only", result["status"])
        self.assertEqual(0, result["displacement"]["chebyshev"])
        self.assertIn("no stable entity id", result["identity_contract"])
        self.assertNotIn("id", result["from"])

    def test_visible_static_destination_is_diagnostic_not_a_path_claim(self) -> None:
        before = snapshot(pet_x=1, pet_y=1, time=1)
        after = snapshot(pet_x=2, pet_y=1, time=2)
        result = classify_transition(before, after, nethack=FakeNethack())
        self.assertEqual("direct_static_surface", result["prior_destination_surface"]["status"])
        self.assertTrue(result["prior_destination_surface"]["passable_by_visible_cmap"])
        self.assertEqual(1, result["displacement"]["chebyshev"])

    def test_multiple_source_pet_pixels_fail_closed(self) -> None:
        before = snapshot(pet_x=1, pet_y=1, time=1)
        before["glyphs"][1][2] = 397  # type: ignore[index]
        before["specials"][1][2] = 8  # type: ignore[index]
        result = classify_transition(before, snapshot(pet_x=1, pet_y=1, time=2), nethack=FakeNethack())
        self.assertEqual("unjudgeable", result["status"])
        self.assertEqual("zero_or_multiple_source_pet_pixels", result["reason"])


if __name__ == "__main__":
    unittest.main()
