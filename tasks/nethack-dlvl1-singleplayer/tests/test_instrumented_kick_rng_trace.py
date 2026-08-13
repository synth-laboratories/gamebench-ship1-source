from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.instrumented_oracle_gate import PINNED_BINARY_SHA256, PINNED_SOURCE_COMMIT, SCHEMA, evaluate
from scripts.verify_instrumented_kick_rng_trace import normalized_patch_bytes, source_call_site_id


class InstrumentedKickTraceTests(unittest.TestCase):
    def candidate(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "identity": {"source_commit": PINNED_SOURCE_COMMIT, "baseline_binary_sha256": PINNED_BINARY_SHA256, "instrumented_binary_sha256": "trace", "toolchain_identity_sha256": "toolchain", "patch_sha256": "patch"},
            "controls": {"independent_seed_count": 3, "transition_count": 3, "trace_event_count": 1, "public_observation_mismatch_count": 0, "native_boundary_mismatch_count": 0, "final_rng_state_mismatch_count": 0, "trace_replay_mismatch_count": 0, "two_independent_runs_exact": True},
            "validity": {"inputs_selected_before_results": True, "trace_read_only_from_gold_perspective": True, "trace_excluded_from_gold_runtime": True, "trace_excluded_from_conformance_denominator": True, "zero_and_unmatched_events_fail_closed": True},
            "instrumented_source_oracle_eligible": True,
        }

    def test_atos_mapping_is_canonical_and_unmapped_sites_fail(self) -> None:
        self.assertEqual("dokick.c:1243:rnd", source_call_site_id("dokick (in libnethack.so) (dokick.c:1243)", 2))
        with self.assertRaisesRegex(RuntimeError, "unmapped"):
            source_call_site_id("0x1234", 1)

    def test_patch_identity_ignores_only_git_abbreviation_width(self) -> None:
        short = b"diff --git a/x b/x\nindex abc..def 100644\n"
        long = b"diff --git a/x b/x\nindex abcdef123..def456789 100644\n"
        self.assertEqual(normalized_patch_bytes(short), normalized_patch_bytes(long))

    def test_gate_rejects_zero_event_even_with_a_recomputed_claim(self) -> None:
        candidate = self.candidate()
        candidate["controls"]["trace_event_count"] = 0  # type: ignore[index]
        result = evaluate(candidate)
        self.assertFalse(result["instrumented_source_oracle_eligible"])
        self.assertIn("zero_trace_event_count", result["failures"])


if __name__ == "__main__":
    unittest.main()
