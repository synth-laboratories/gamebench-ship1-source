from __future__ import annotations

import unittest

from scripts.nle_specials_assertions import specials_step_report, specials_trace_report
from shared.nle_specials import MG_OBJPILE, MG_PET


class NleSpecialsAssertionsTests(unittest.TestCase):
    def test_exact_zero_and_materialized_pet_are_judgeable(self) -> None:
        report = specials_step_report([[0, MG_PET]], [[0, MG_PET]], step=2)
        self.assertEqual(2, report["comparisons"])
        self.assertEqual(0, report["unjudgeable"])
        self.assertEqual([], report["errors"])

    def test_source_pet_without_owned_entity_is_unjudgeable_not_equal(self) -> None:
        report = specials_step_report([[MG_PET]], [[0]], step=0)
        self.assertEqual(0, report["comparisons"])
        self.assertEqual(1, report["unjudgeable"])
        self.assertEqual([], report["errors"])

    def test_object_pile_is_unjudgeable_even_when_gold_zero(self) -> None:
        report = specials_step_report([[MG_OBJPILE]], [[0]], step=0)
        self.assertEqual(0, report["comparisons"])
        self.assertEqual(1, report["unjudgeable"])
        self.assertEqual("source_requires_unexposed_mapglyph_state", next(iter(report["reason_counts"])))

    def test_gold_must_not_fabricate_pet_marker(self) -> None:
        report = specials_step_report([[0]], [[MG_PET]], step=0)
        self.assertEqual(1, report["comparisons"])
        self.assertEqual("gold_fabricated_pet_marker", report["errors"][0]["reason"])

    def test_partial_unjudgeable_cannot_be_a_pass(self) -> None:
        report = specials_trace_report(
            [{"specials": [[0, MG_PET]]}],
            [{"specials": [[0, 0]]}],
            through_step=0,
        )
        self.assertEqual("partially_unjudgeable", report["status"])


if __name__ == "__main__":
    unittest.main()
