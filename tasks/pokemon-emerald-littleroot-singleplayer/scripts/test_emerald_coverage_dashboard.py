#!/usr/bin/env python3
"""ROM-free tests for the coverage dashboard's evidence accounting."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("emerald_coverage_dashboard.py")
SPEC = importlib.util.spec_from_file_location("emerald_coverage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
DASHBOARD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DASHBOARD
SPEC.loader.exec_module(DASHBOARD)


ROM = "a" * 64
STATE = "b" * 64


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class CoverageDashboardTest(unittest.TestCase):
    def fixture_paths(self, directory: Path) -> tuple[Path, Path, Path]:
        registry = write(directory / "registry.json", {
            "schema": DASHBOARD.REGISTRY_SCHEMA,
            "segments": [
                {"id": "bedroom", "name": "Bedroom", "checkpoint": "bedroom_idle", "oracle_state_sha256": STATE, "frozen_source_state_contains": "02_starter"},
                {"id": "rival", "name": "Rival battle", "checkpoint": "route103_rival"},
            ],
        })
        frames = write(directory / "frames.json", {
            "schema": DASHBOARD.FRAME_SCHEMA,
            "traces": [{"source_state": "splits/02_starter.state"}],
        })
        oracle = write(directory / "oracle.json", {
            "schema": DASHBOARD.ORACLE_SCHEMA,
            "source": {"rom_sha256": ROM, "state_sha256": STATE},
        })
        return registry, frames, oracle

    def test_authenticated_source_lane_gets_rates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            registry, frames, oracle = self.fixture_paths(directory)
            report = write(directory / "report.json", {
                "schema_version": 3,
                "lanes": [{
                    "lane": "source_behavior_oracle", "rom_sha256": ROM, "state_sha256": STATE,
                    "pixel_comparison": {"cadence": "every VBlank", "tolerance": 0},
                    "cases": [{
                        "checkpoint": "bedroom_idle", "compared_source_frames": 10,
                        "pixel_mismatch_frames": 2, "semantic_boundaries": [3, 7],
                        "semantic_boundary_mismatches": 1,
                    }],
                }],
            })
            result = DASHBOARD.build_dashboard(registry, frames, oracle, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [report], [])
            bedroom, rival = result["segments"]
            self.assertEqual("source_differential", bedroom["evidence_level"])
            self.assertEqual({"status": "authenticated", "available": True}, bedroom["authenticated_source_state"])
            self.assertEqual(8, bedroom["exact_pixel_rate"]["exact"])
            self.assertEqual(10, bedroom["exact_pixel_rate"]["total"])
            self.assertEqual(2, bedroom["exact_state_rate"]["exact"])
            self.assertEqual(3, bedroom["exact_state_rate"]["total"])
            self.assertEqual(1, bedroom["frozen_endpoint_frames"]["count"])
            self.assertEqual("functional_only", rival["evidence_level"])
            self.assertEqual("unknown", rival["exact_pixel_rate"]["status"])

    def test_transport_lane_never_counts_as_source_validity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            registry, frames, oracle = self.fixture_paths(directory)
            report = write(directory / "transport.json", {
                "schema_version": 3,
                "lanes": [{"lane": "rust_transport_contract", "case_count": 999, "result": "pass"}],
            })
            result = DASHBOARD.build_dashboard(registry, frames, oracle, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [report], [])
            bedroom = result["segments"][0]
            self.assertEqual("frozen_frame", bedroom["evidence_level"])
            self.assertEqual("unknown", bedroom["exact_state_rate"]["status"])
            self.assertEqual("unknown", bedroom["canonical_tapes"]["status"])

    def test_unexecuted_tape_spec_is_not_a_pass_or_visited_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            registry, frames, oracle = self.fixture_paths(directory)
            tape = write(directory / "tapes.json", {
                "schema": DASHBOARD.TAPE_SCHEMA,
                "tapes": [{
                    "id": "future-rival", "segment": "rival", "canonical": True,
                    "visited": {
                        "input_owner_task_states": ["battle:command"],
                        "transitions": ["battle_entry"], "outcomes": ["victory"],
                    },
                }],
            })
            result = DASHBOARD.build_dashboard(registry, frames, oracle, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [], [tape])
            rival = result["segments"][1]
            self.assertEqual("tape_spec_unexecuted", rival["evidence_level"])
            self.assertEqual("unknown", rival["exact_pixel_rate"]["status"])
            self.assertEqual("unknown", rival["input_owner_task_states_visited"]["status"])

    def test_quarantined_checkpoint_has_no_source_validity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            registry = write(directory / "registry.json", {
                "schema": DASHBOARD.REGISTRY_SCHEMA,
                "segments": [{
                    "id": "clock", "name": "Clock", "checkpoint": "clock_tv_downstairs",
                    "oracle_checkpoints": ["clock_tv_downstairs"],
                    "oracle_state_sha256": "7c26d2f1e3e53b3eaf76da04a29250e245c2923fb19dc243e34bde0add236ad1",
                }],
            })
            frames = write(directory / "frames.json", {"schema": DASHBOARD.FRAME_SCHEMA, "traces": []})
            oracle = write(directory / "oracle.json", {"schema": DASHBOARD.ORACLE_SCHEMA, "source": {}})
            result = DASHBOARD.build_dashboard(registry, frames, oracle, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [], [])
            clock = result["segments"][0]
            self.assertEqual("functional_only", clock["evidence_level"])
            self.assertEqual("unknown", clock["authenticated_source_state"]["status"])
            self.assertEqual("unknown", clock["exact_pixel_rate"]["status"])

    def test_unsupported_inputs_are_visible_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            registry, _, oracle = self.fixture_paths(directory)
            bad_frames = write(directory / "bad-frames.json", {"schema": "new.schema"})
            result = DASHBOARD.build_dashboard(registry, bad_frames, oracle, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [], [])
            self.assertEqual("unsupported", result["segments"][0]["frozen_endpoint_frames"]["status"])
            self.assertTrue(any("UNSUPPORTED frozen-frame" in item for item in result["diagnostics"]))

    def test_authenticated_capture_receipt_counts_live_source_trace_not_rust_validity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            registry, frames, oracle = self.fixture_paths(directory)
            source_registry = write(directory / "source-registry.json", {
                "schema": "gamebench.pokemon_emerald.mgba_oracle_registry.v1",
                "rom_sha256": ROM,
                "default_checkpoint": "bedroom_idle",
                "oracle": {
                    "trust_status": "trusted",
                    "emulator": {"core": "mGBA", "version": "x", "config_sha256": "c" * 64},
                    "config": {"audio": False},
                },
                "checkpoints": [{
                    "id": "bedroom_idle", "status": "authenticated", "rust_checkpoint": "bedroom_idle",
                    "source_split": "local.state", "normalization": {}, "capture": {},
                    "source": {"state_sha256": STATE, "initial_rgb_sha256": "d" * 64, "initial_state": {"map_group": 1}},
                }],
            })
            trace = {
                "schema": DASHBOARD.CAPTURE_TRACE_SCHEMA,
                "source_identity": {
                    "rom_sha256": ROM, "source_state_sha256": STATE,
                    "emulator": {"core": "mGBA", "version": "x", "config_sha256": "c" * 64}, "config": {"audio": False},
                },
                "capture_tape": {"coverage_segment": "rival"},
                "frame_count": 2,
                "frames": [
                    {"source_state": {"map_group": 1, "map_number": 1}},
                    {"source_state": {"map_group": 1, "map_number": 2}},
                ],
                "terminal_snapshot_state_sha256": "e" * 64,
            }
            trace["trace_sha256"] = __import__("hashlib").sha256(
                DASHBOARD.canonical_json(trace).encode("utf-8")
            ).hexdigest()
            trace_path = write(directory / "trace.json", trace)
            receipt = {
                "schema": DASHBOARD.CAPTURE_RECEIPT_SCHEMA, "round_trip": "exact_no_input_continuation",
                "capture_trace_path": str(trace_path), "capture_trace_sha256": trace["trace_sha256"],
                "snapshot_state_sha256": "e" * 64, "terminal_source_position": {"map_group": 1, "map_number": 2, "player_x": 1, "player_y": 1},
            }
            receipt["receipt_sha256"] = __import__("hashlib").sha256(
                DASHBOARD.canonical_json(receipt).encode("utf-8")
            ).hexdigest()
            receipt_path = write(directory / "receipt.json", receipt)
            result = DASHBOARD.build_dashboard(
                registry, frames, oracle, source_registry, [], [], [], [receipt_path]
            )
            rival = result["segments"][1]
            self.assertEqual("source_trace_only", rival["evidence_level"])
            self.assertEqual(1, rival["source_tapes_captured"]["count"])
            self.assertEqual(2, rival["source_vblanks_captured"]["count"])
            self.assertEqual(["map:1:1→1:2"], rival["observed_map_transitions"]["values"])
            self.assertEqual("unknown", rival["exact_pixel_rate"]["status"])

    def test_superseded_v7_trace_identity_cannot_count_under_v8_registry(self) -> None:
        source_registry = DASHBOARD.load_oracle_registry(
            DASHBOARD.DEFAULT_ORACLE_REGISTRY
        )
        registry, checkpoints = source_registry
        bedroom = checkpoints["bedroom_idle"]
        assert bedroom.source is not None
        current = {
            "rom_sha256": registry["rom_sha256"],
            "source_state_sha256": bedroom.source["state_sha256"],
            "emulator": registry["oracle"]["emulator"],
            "config": registry["oracle"]["config"],
        }
        self.assertEqual(
            "bedroom_idle",
            DASHBOARD.authenticated_checkpoint_for_identity(
                current, source_registry
            ),
        )
        v7 = json.loads(json.dumps(current))
        v7["config"]["adapter_version"] = "7"
        v7["config"]["adapter_source_sha256"] = (
            "f7102b2fbf66f8e96f26dd77f2054b9bfd20fdc60e7a8886c74a2408afd815cf"
        )
        v7["config"].pop("observability_source_sha256", None)
        self.assertIsNone(
            DASHBOARD.authenticated_checkpoint_for_identity(
                v7, source_registry
            )
        )

    def test_provenance_audited_registry_aggregates_without_claiming_differential_exactness(self) -> None:
        result = DASHBOARD.build_dashboard(
            DASHBOARD.DEFAULT_REGISTRY, DASHBOARD.DEFAULT_FRAMES,
            DASHBOARD.DEFAULT_ORACLE, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [], [],
        )
        totals = result["registry_capture_chain_totals"]
        # The provenance audit deliberately demoted all stale/reload-sensitive
        # evidence rather than allowing historical capture volume to inflate
        # the current source-validity inventory. One continuous Route 103
        # victory trace was subsequently promoted after its terminal state,
        # upstream input boundary, and tape digest were independently bound.
        self.assertEqual(69, totals["authenticated_checkpoints"])
        self.assertEqual(9, totals["capture_required_checkpoints"])
        self.assertEqual(31, totals["quarantined_checkpoints"])
        self.assertEqual(61021, totals["snapshot_vblank_total"])
        self.assertEqual(2, totals["continuous_battle_traces"])
        self.assertEqual(6461, totals["continuous_battle_vblank_total"])
        self.assertEqual([], totals["unassigned"]["ids"])
        rival = next(row for row in result["segments"] if row["id"] == "route103_rival")
        self.assertEqual("authenticated_capture_chain", rival["evidence_level"])
        self.assertTrue(rival["capture_chain_snapshot_vblanks"]["overlapping_non_unique"])
        self.assertFalse(rival["capture_chain_snapshot_vblanks"]["differential_exactness"])
        self.assertEqual("unknown", rival["exact_pixel_rate"]["status"])

    def test_final_route101_departure_is_explicitly_quarantined_not_hidden_or_credited(self) -> None:
        result = DASHBOARD.build_dashboard(
            DASHBOARD.DEFAULT_REGISTRY, DASHBOARD.DEFAULT_FRAMES,
            DASHBOARD.DEFAULT_ORACLE, DASHBOARD.DEFAULT_ORACLE_REGISTRY, [], [],
        )
        departure = result["final_route101_departure"]
        self.assertEqual("quarantined_provenance", departure["status"])
        self.assertEqual(
            {"map_group": 0, "map_number": 16, "player_x": 10, "player_y": 19},
            departure["source_state"],
        )
        self.assertIn("not an authenticated endpoint", departure["claim"])
        self.assertIn("or differential exactness", departure["claim"])


if __name__ == "__main__":
    unittest.main()
