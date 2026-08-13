from __future__ import annotations

import unittest
from pathlib import Path

from shared.nle_specials import (
    MG_BW_LAVA,
    MG_CORPSE,
    MG_DETECT,
    MG_INVIS,
    MG_OBJPILE,
    MG_PET,
    MG_RIDDEN,
    MG_STATUE,
    pet_specials,
    reset_overlay_specials,
    unsupported_bits,
)
from gold_python.engine import NethackDlvl1Engine
from scripts.compare_nle_discrepancies import expected_public, fixture_task
from shared.task_resolve import resolve_task


class NleSpecialsContractTests(unittest.TestCase):
    def test_pinned_source_bit_values(self) -> None:
        self.assertEqual((1, 2, 4, 8, 16, 32, 64, 128), (MG_CORPSE, MG_INVIS, MG_DETECT, MG_PET, MG_RIDDEN, MG_STATUE, MG_OBJPILE, MG_BW_LAVA))

    def test_only_visible_materialised_pet_sets_a_bit(self) -> None:
        plane = pet_specials(
            [[True, False], [True, True]],
            [
                {"pet": True, "position": {"x": 0, "y": 0}},
                {"pet": True, "position": {"x": 1, "y": 0}},
                {"pet": False, "position": {"x": 1, "y": 1}},
            ],
            height=2,
            width=2,
        )
        self.assertEqual([[MG_PET, 0], [0, 0]], plane)

    def test_render_precedence_prevents_a_hidden_pet_bit(self) -> None:
        plane = pet_specials(
            [[True]],
            [
                {"pet": True, "position": {"x": 0, "y": 0}},
                {"pet": False, "position": {"x": 0, "y": 0}},
            ],
            height=1,
            width=1,
        )
        self.assertEqual([[0]], plane)

    def test_non_pet_bits_are_explicitly_not_derivable(self) -> None:
        self.assertEqual(MG_CORPSE | MG_OBJPILE, unsupported_bits(MG_CORPSE | MG_PET | MG_OBJPILE))

    def test_reset_overlay_can_carry_exact_public_special_byte(self) -> None:
        plane = reset_overlay_specials(
            [[True, True]],
            [{"x": 0, "y": 0, "special": MG_CORPSE | MG_OBJPILE}, {"x": 1, "y": 0}],
            height=1,
            width=2,
        )
        self.assertEqual([[MG_CORPSE | MG_OBJPILE, 0]], plane)

    def test_frozen_source_pet_plane_is_strictly_replayed(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "nle_oracle" / "val-east-seed-20260725"
        task, _actions, snapshots = fixture_task(fixture)
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertEqual(expected_public(snapshots[0])["specials"], engine.public_projection()["specials"])


if __name__ == "__main__":
    unittest.main()
