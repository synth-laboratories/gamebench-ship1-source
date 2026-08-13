from __future__ import annotations

import unittest

from scripts.verify_mfndpos_static_geometry import _static_candidates, audit


def reset_map() -> dict[str, object]:
    return {
        "terrain_type": [[24] * 79 for _ in range(21)],
        "terrain_flags": [[0] * 79 for _ in range(21)],
        "terrain_horizontal": [[False] * 79 for _ in range(21)],
    }


def trace(candidates: list[tuple[int, int]]) -> dict[str, object]:
    return {
        "schema": "gamebench.nethack.lldb_branch_candidate_trace.v1",
        "equivalence_gate": {"controls": {name: 0 for name in (
            "public_observation_mismatch_count",
            "native_boundary_mismatch_count",
            "final_rng_state_mismatch_count",
            "trace_replay_mismatch_count",
            "unmatched_event_count",
            "trace_error_count",
        )}},
        "frontier_candidate": {
            "branch_records": [{
                "seed": 7,
                "step": 1,
                "mfndpos": {
                    "actor_at_mfndpos_return": {"native_x": 11, "native_y": 10},
                    "allowflags": 0,
                    "candidates": [{"native_x": x, "native_y": y} for x, y in candidates],
                },
            }],
        },
    }


class MfndposStaticGeometryTests(unittest.TestCase):
    def test_open_door_is_admitted_by_reset_geometry(self) -> None:
        value = reset_map()
        value["terrain_type"][10][10] = 22  # native (11, 10), open door
        self.assertIn((11, 10), _static_candidates(value, (10, 10)))

    def test_missing_source_candidate_blocks_audit(self) -> None:
        value = reset_map()
        value["terrain_type"][10][11] = 0
        result = audit(trace([(12, 10)]), {7: self._write_map(value)})
        self.assertEqual("source_static_geometry_blocked", result["status"])
        self.assertEqual(1, result["controls"]["source_candidate_missing_from_static_map"])

    def test_static_audit_does_not_promote_gold(self) -> None:
        result = audit(trace([(10, 9)]), {7: self._write_map(reset_map())})
        self.assertEqual("source_static_geometry_eligible", result["status"])
        self.assertFalse(result["gold_implementation_eligible"])

    @staticmethod
    def _write_map(value: dict[str, object]):
        import json
        from pathlib import Path
        import tempfile

        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        with handle:
            json.dump({"authoritative_reset_map": value}, handle)
        return Path(handle.name)


if __name__ == "__main__":
    unittest.main()
