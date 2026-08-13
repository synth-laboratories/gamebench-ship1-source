from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts.frontier_promotion_gate import evaluate as evaluate_frontier_gate
from scripts.verify_lldb_branch_trace import DEFAULT_ACTIONS, _merge_branch_records, _mismatches, build_candidate, frontier_candidate


ACTION = {"step": 1, "action_id": 18, "action_name": "MiscDirection.WAIT"}


def entity(entity_id: int = 7) -> dict[str, object]:
    return {
        "entity_id": entity_id,
        "x": 12,
        "y": 8,
        "native_x": 13,
        "native_y": 8,
        "scheduler": {"iteration_order": 0},
        "path_state": {"apparent_hero_native": {"x": 14, "y": 8}, "mtrack_native": []},
    }


def frame(*, public: str = "public", native: str = "native", rng: str = "rng", present: bool = True) -> dict[str, object]:
    return {
        "public_observation_sha256": public,
        "native_boundary_sha256": native,
        "rng": {"state": rng},
        "entities": {"source_turn": {"moves": 1, "monstermoves": 1}, "entities": [entity()] if present else []},
        "player": {"player": {"coordinates": {"native_x": 14, "native_y": 8}}},
    }


def run() -> dict[str, object]:
    return {"seed": 20261301, "actions": [ACTION], "frames": [frame(), frame(public="public-after", native="native-after", rng="rng-after")]}


def candidate_event() -> dict[str, object]:
    return {
        "kind": "mfndpos_candidates",
        "step": 1,
        "action": ACTION,
        "caller": "dog_move",
        "allowflags": 7,
        "actor": {"entity_id": 7, "native_x": 13, "native_y": 8},
        "event_id": 10,
        "candidate_count": 2,
        "candidates": [
            {"native_x": 13, "native_y": 8, "mfndpos_flags": 1},
            {"native_x": 14, "native_y": 8, "mfndpos_flags": 2},
        ],
    }


def cell(x: int, y: int, occupant: int | None) -> dict[str, object]:
    return {
        "coordinate": {"native_x": x, "native_y": y},
        "state": {
            "terrain": {"glyph": 1, "type": 24, "seen_vector": 0, "flags": 0},
            "object_stack": [],
            "object_stack_complete": True,
            "source_abi": "nethack_3_6_6_darwin_arm64_level_rm_obj_v1",
        },
        "occupancy": {"entity_id": occupant},
    }


def selector_return(*, candidate_id: int = 10, after_x: int = 14, after_y: int = 8, actor_id: int = 7) -> dict[str, object]:
    return {
        "kind": "selector_return",
        "step": 1,
        "action": ACTION,
        "selector": "dog_move",
        "actor": {"entity_id": actor_id, "native_x": 13, "native_y": 8},
        "actor_after": {"entity_id": actor_id, "native_x": after_x, "native_y": after_y},
        "return_code": 1,
        "bound_candidate_event_id": candidate_id,
        "event_id": candidate_id + 1,
        "source_underlay_before": cell(13, 8, actor_id),
        "source_underlay_after": cell(13, 8, None if (after_x, after_y) != (13, 8) else actor_id),
        "destination_underlay_before": cell(after_x, after_y, None),
        "destination_underlay_after": cell(after_x, after_y, actor_id),
    }


class LldbBranchTraceTests(unittest.TestCase):
    def test_prompt_resume_is_fixed_preselected_input(self) -> None:
        self.assertEqual(
            ("Command.SEARCH", "MiscDirection.WAIT", "CompassDirection.E", "Command.SEARCH", "TextCharacters.SPACE"),
            DEFAULT_ACTIONS,
        )

    def test_merge_binds_full_preselected_candidate_set_to_source_state(self) -> None:
        records, unmatched, errors = _merge_branch_records(
            run(),
            [
                candidate_event(),
                selector_return(),
            ],
        )

        self.assertEqual(0, unmatched)
        self.assertEqual(0, errors)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(7, record["stable_entity_id"])
        self.assertEqual(0, record["source_list_order"])
        self.assertEqual([1, 2], [candidate["mfndpos_flags"] for candidate in record["mfndpos"]["candidates"]])
        self.assertEqual(7, record["mfndpos"]["actor_at_mfndpos_return"]["entity_id"])
        self.assertEqual(1, record["selected_result"]["branch_selector_return"]["return_code"])
        self.assertEqual({"moves": 1, "monstermoves": 1}, record["source_turn"])

    def test_zero_or_unmatched_events_fail_closed_before_gate(self) -> None:
        unmatched_event = candidate_event()
        unmatched_event["actor"] = {"entity_id": 99}
        records, unmatched, errors = _merge_branch_records(run(), [unmatched_event, {"kind": "trace_error", "step": 1, "action": ACTION}])

        self.assertEqual([], records)
        self.assertEqual(1, unmatched)
        self.assertEqual(1, errors)

    def test_exact_return_binding_does_not_conflate_fast_movement_calls(self) -> None:
        first = candidate_event()
        first["event_id"] = 10
        second = candidate_event()
        second["event_id"] = 20
        records, unmatched, errors = _merge_branch_records(
            run(),
            [
                first,
                selector_return(after_x=13),
                second,
                selector_return(candidate_id=20),
            ],
        )
        self.assertEqual((0, 0), (unmatched, errors))
        self.assertEqual([13, 14], [record["selected_result"]["branch_selector_return"]["actor_after"]["native_x"] for record in records])

    def test_missing_or_wrong_causal_binding_fails_closed(self) -> None:
        missing = candidate_event()
        records, unmatched, errors = _merge_branch_records(
            run(),
            [missing, selector_return(candidate_id=99)],
        )
        self.assertEqual([], records)
        # Both sides are rejected: the candidate has no exact return and the
        # return names no candidate invocation.
        self.assertEqual(2, unmatched)
        self.assertEqual(0, errors)

        wrong_actor = candidate_event()
        records, unmatched, errors = _merge_branch_records(
            run(),
            [wrong_actor, selector_return(actor_id=8)],
        )
        self.assertEqual([], records)
        self.assertEqual(0, unmatched)
        self.assertEqual(1, errors)

    def test_missing_raw_boundary_or_duplicate_event_id_fails_closed(self) -> None:
        incomplete = selector_return()
        del incomplete["destination_underlay_before"]
        records, unmatched, errors = _merge_branch_records(run(), [candidate_event(), incomplete])
        self.assertEqual([], records)
        self.assertEqual((0, 1), (unmatched, errors))

        duplicate = candidate_event()
        records, unmatched, errors = _merge_branch_records(run(), [candidate_event(), duplicate, selector_return()])
        self.assertEqual([], records)
        self.assertEqual((0, 1), (unmatched, errors))

    def test_equivalence_comparison_detects_public_native_and_rng_perturbations(self) -> None:
        baseline = run()
        public = copy.deepcopy(baseline)
        public["frames"][1]["public_observation_sha256"] = "changed"
        self.assertEqual((1, 0, 0), _mismatches(baseline, public))
        native = copy.deepcopy(baseline)
        native["frames"][1]["native_boundary_sha256"] = "changed"
        self.assertEqual((0, 1, 0), _mismatches(baseline, native))
        rng = copy.deepcopy(baseline)
        rng["frames"][1]["rng"] = {"state": "changed"}
        self.assertEqual((0, 0, 1), _mismatches(baseline, rng))

    def test_replay_or_zero_event_perturbation_rejects_source_oracle_claim(self) -> None:
        baseline = run()
        events = [[candidate_event(), selector_return()]]
        with patch("scripts.verify_lldb_branch_trace._toolchain_identity", return_value={"mode": "unit"}):
            good = build_candidate(
                seeds=[20261301],
                baseline_runs=[baseline],
                traced_runs=[copy.deepcopy(baseline)],
                replay_runs=[copy.deepcopy(baseline)],
                traced_events=events,
                replay_events=copy.deepcopy(events),
            )
            self.assertTrue(good["instrumented_source_oracle_eligible"])
            self.assertFalse(good["gold_implementation_eligible"])
            promotion = frontier_candidate(good)
            promotion_decision = evaluate_frontier_gate(promotion)
            self.assertTrue(promotion["source_export_eligible"])
            self.assertFalse(promotion["gold_implementation_eligible"])
            self.assertFalse(promotion_decision["gold_implementation_eligible"])
            self.assertIn("captured_pre_action_only_not_proven", promotion_decision["failures"])
            self.assertIn("heldout_counterexamples", promotion_decision["failures"])

            zero = build_candidate(
                seeds=[20261301],
                baseline_runs=[baseline],
                traced_runs=[copy.deepcopy(baseline)],
                replay_runs=[copy.deepcopy(baseline)],
                traced_events=[[]],
                replay_events=[[]],
            )
            self.assertFalse(zero["instrumented_source_oracle_eligible"])
            self.assertEqual(0, zero["controls"]["trace_event_count"])

            replay = copy.deepcopy(events)
            replay[0][0]["candidates"][0]["mfndpos_flags"] = 99
            divergent = build_candidate(
                seeds=[20261301],
                baseline_runs=[baseline],
                traced_runs=[copy.deepcopy(baseline)],
                replay_runs=[copy.deepcopy(baseline)],
                traced_events=events,
                replay_events=replay,
            )
            self.assertFalse(divergent["instrumented_source_oracle_eligible"])
            self.assertEqual(1, divergent["controls"]["trace_replay_mismatch_count"])


if __name__ == "__main__":
    unittest.main()
