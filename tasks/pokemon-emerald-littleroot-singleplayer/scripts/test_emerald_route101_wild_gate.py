import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import emerald_route101_wild_gate as gate


def report(*, pixel_errors: int = 0) -> dict:
    cases = [
        {"result": "exact", "compared_source_frames": 65, "proof_tape": [{"semantic_comparable": True}] * 2},
        {"result": "exact", "compared_source_frames": 62, "proof_tape": [{"semantic_comparable": True}] * 3},
    ]
    if pixel_errors:
        cases[1]["result"] = "divergence"
    return {
        "lanes": [
            {"lane": "source_behavior_oracle", "oracle_checkpoint": "route101_wild_battle", "coverage_segment": "route101_wild_battle", "cases": cases, "pixel_mismatch_frames": pixel_errors, "semantic_boundary_mismatches": 0},
            {"lane": "rust_transport_contract", "case_count": 5, "violation_count": 0},
        ]
    }


class Route101WildGateTests(unittest.TestCase):
    def test_authenticated_entry_gate_passes(self) -> None:
        summary = gate.summarize(report())
        self.assertTrue(summary["acceptance"]["gate_passed"])

    def test_renderer_divergence_blocks_gate(self) -> None:
        summary = gate.summarize(report(pixel_errors=1))
        self.assertFalse(summary["acceptance"]["gate_passed"])


if __name__ == "__main__":
    unittest.main()
