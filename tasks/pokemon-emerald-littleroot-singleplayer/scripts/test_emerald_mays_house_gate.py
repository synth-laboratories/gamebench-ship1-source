#!/usr/bin/env python3
"""ROM-free tests for the Mays House acceptance contract."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("emerald_mays_house_gate.py")
SPEC = importlib.util.spec_from_file_location("emerald_mays_house_gate", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def tick(*, comparable=True):
    return {"semantic_comparable": comparable}


def report(*, exact=True, tapes=18, frames=6384, states=968, transport=21):
    result = "exact" if exact else "divergence"
    first_frames = 209
    first_states = min(states, first_frames)
    second_frames = frames - first_frames
    second_states = max(0, states - first_states)
    source_cases = [
        {
            "name": "fixture_mays_house_1f_transition",
            "origin": "checked-in source fixture",
            "result": result,
            "compared_source_frames": 209,
            "pixel_mismatch_frames": 0 if exact else 1,
            "semantic_boundary_mismatches": 0,
            "proof_tape": [
                tick(comparable=index < first_states) for index in range(first_frames)
            ],
        },
        {
            "name": "fixture_mays_house_1f_exit_to_littleroot",
            "origin": "checked-in source fixture",
            "result": result,
            "compared_source_frames": second_frames,
            "pixel_mismatch_frames": 0,
            "semantic_boundary_mismatches": 0,
            "proof_tape": [
                tick(comparable=index < second_states) for index in range(second_frames)
            ],
        },
    ]
    for index in range(max(0, tapes - 2)):
        source_cases.append(
            {
                "name": f"random_seed_{index:03d}",
                "origin": "deterministic random fuzz",
                "result": "exact",
                "compared_source_frames": 0,
                "pixel_mismatch_frames": 0,
                "semantic_boundary_mismatches": 0,
                "proof_tape": [],
            }
        )
    return {
        "lanes": [
            {
                "lane": "source_behavior_oracle",
                "oracle_checkpoint": "bedroom_idle",
                "coverage_segment": "mays_house_exit",
                "cases": source_cases,
            },
            {
                "lane": "rust_transport_contract",
                "case_count": transport,
                "violation_count": 0,
            },
        ]
    }


class MaysHouseGateTests(unittest.TestCase):
    def test_authenticated_contract_passes(self):
        summary = GATE.gate_summary(report())
        self.assertTrue(summary["acceptance"]["gate_passed"])

    def test_fewer_random_tapes_block(self):
        summary = GATE.gate_summary(report(tapes=17, frames=6320, states=952))
        self.assertFalse(summary["acceptance"]["gate_passed"])
        self.assertIn("tapes", summary["count_failures"])

    def test_pixel_divergence_blocks_even_with_full_counts(self):
        summary = GATE.gate_summary(report(exact=False))
        self.assertFalse(summary["acceptance"]["gate_passed"])
        self.assertEqual(summary["exact_failures"]["case_divergences"], 2)

    def test_wrong_identity_blocks(self):
        value = report()
        value["lanes"][0]["coverage_segment"] = "bedroom"
        summary = GATE.gate_summary(value)
        self.assertFalse(summary["acceptance"]["gate_passed"])
        self.assertFalse(summary["acceptance"]["segment_exact"])

    def test_contract_is_fixed(self):
        self.assertEqual(
            GATE.EXPECTED_MAYS_HOUSE_GATE,
            {"tapes": 18, "compared_vblanks": 6384, "state_checks": 968, "transport_contracts": 21},
        )


if __name__ == "__main__":
    unittest.main()
