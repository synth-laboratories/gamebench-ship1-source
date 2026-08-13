#!/usr/bin/env python3
"""ROM-free regression tests for the bedroom gate classification."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("emerald_bedroom_gate.py")
SPEC = importlib.util.spec_from_file_location("emerald_bedroom_gate", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def case(*, name="case", pixels=1, semantic=0, source_map="mays_house2_f", rust_map="mays_house2_f"):
    return {
        "name": name,
        "origin": "checked-in source fixture",
        "result": "divergence" if pixels or semantic else "exact",
        "compared_source_frames": 2,
        "pixel_mismatch_frames": pixels,
        "semantic_boundary_mismatches": semantic,
        "first_mismatch": {"vblank": 1},
        "proof_tape": [
            {
                "vblank": 2,
                "semantic_equal": False,
                "source_semantic": {"map": source_map},
                "rust_semantic": {"map": rust_map},
            }
        ] if semantic else [],
    }


class BedroomGateTests(unittest.TestCase):
    def test_pixel_only_is_renderer(self):
        self.assertEqual(GATE.classify(case())[0], "renderer")

    def test_same_map_semantic_is_scheduler(self):
        self.assertEqual(GATE.classify(case(semantic=1))[0], "scheduler")

    def test_map_change_semantic_is_warp(self):
        self.assertEqual(
            GATE.classify(case(semantic=1, source_map="emerald_map_1_2"))[0],
            "warp",
        )

    def test_gate_requires_random_and_mandatory(self):
        report = {"lanes": [{"lane": "source_behavior_oracle", "cases": [
            {**case(pixels=0, semantic=0), "result": "exact", "first_mismatch": None},
            {**case(name="random", pixels=0, semantic=0), "origin": "deterministic random fuzz", "result": "exact", "first_mismatch": None},
        ]}, {"lane": "rust_transport_contract", "case_count": 21, "violation_count": 0}]}
        summary = GATE.gate_summary(report)
        self.assertFalse(summary["acceptance"]["gate_passed"])
        self.assertIn("tapes", summary["count_failures"])

    def test_gate_exposes_fixed_acceptance_contract(self):
        self.assertEqual(
            GATE.EXPECTED_BEDROOM_GATE,
            {"tapes": 26, "compared_vblanks": 1687, "state_checks": 977, "transport_contracts": 21},
        )


if __name__ == "__main__":
    unittest.main()
