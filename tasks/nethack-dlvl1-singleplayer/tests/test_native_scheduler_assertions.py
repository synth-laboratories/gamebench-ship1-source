from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.native_scheduler_assertions import (
    causal_transition_evidence,
    destination_collision_rule_assessment,
    occupancy_map,
    scheduler_transition,
    static_vacated_underlay_assertion,
)
from scripts.frontier_promotion_gate import evaluate as evaluate_promotion
from scripts.verify_native_scheduler import _promotion_candidate


def entity(entity_id: int, x: int, y: int, movement: int) -> dict[str, object]:
    return {"entity_id": entity_id, "x": x, "y": y, "scheduler": {"movement_points": movement, "iteration_order": 0}}


def frame(entity_id: int, x: int, y: int, movement: int, *, moves: int = 1, monstermoves: int | None = None) -> dict[str, object]:
    return {
        "source_turn": {"moves": moves, "monstermoves": moves if monstermoves is None else monstermoves},
        "turn_queue": [entity_id],
        "entities": [entity(entity_id, x, y, movement)],
    }


def cell(x: int, y: int, monster_id: int | None) -> dict[str, object]:
    return {
        "x": x,
        "y": y,
        "native_x": x + 1,
        "terrain_type": 24,
        "terrain_memory_glyph": 2378,
        "object_stack": [],
        "object_stack_complete": True,
        "monster_id": monster_id,
    }


def full_cells(occupied: dict[tuple[int, int], int]) -> list[dict[str, object]]:
    return [
        cell(x, y, occupied.get((x, y)))
        for y in range(21)
        for x in range(79)
    ]


class NativeSchedulerAssertionsTests(unittest.TestCase):
    def test_only_stable_source_id_can_classify_movement(self) -> None:
        result = scheduler_transition({"entities": [entity(7, 2, 3, 12)]}, {"entities": [entity(7, 3, 3, 0)]})
        self.assertEqual("pass", result["status"])
        self.assertEqual("moved", result["events"][0]["kind"])
        self.assertTrue(result["events"][0]["ready_before"])
        self.assertEqual(12, result["events"][0]["movement_points_before"])
        self.assertEqual(0, result["events"][0]["movement_points_after"])
        self.assertEqual(-12, result["events"][0]["movement_points_delta"])

    def test_move_without_pre_action_points_is_a_boundary_ambiguity_not_an_oracle_error(self) -> None:
        result = scheduler_transition({"entities": [entity(7, 2, 3, 11)]}, {"entities": [entity(7, 3, 3, 0)]})
        self.assertEqual("pass", result["status"])
        self.assertEqual([], result["violations"])
        self.assertEqual("movement_budget_replenished_after_pre_action_boundary", result["ambiguities"][0]["code"])

    def test_static_empty_vacated_cell_uses_exact_post_source_underlay_only(self) -> None:
        transition = scheduler_transition({"entities": [entity(7, 2, 3, 12)]}, {"entities": [entity(7, 3, 3, 0)]})
        result = static_vacated_underlay_assertion(
            transition,
            after_cells={(2, 3): {"terrain_memory_glyph": 2378, "object_stack": [], "monster_id": None}},
            after_glyphs=[[0] * 5 for _ in range(5)],
        )
        self.assertEqual("errors_found", result["status"])
        result = static_vacated_underlay_assertion(
            transition,
            after_cells={(2, 3): {"terrain_memory_glyph": 2378, "object_stack": [], "monster_id": None}},
            after_glyphs=[[0] * 5 for _ in range(3)] + [[0, 0, 2378, 0, 0]] + [[0] * 5],
        )
        self.assertEqual("pass", result["status"])

    def test_object_covered_vacated_cell_is_unjudged_not_granted_credit(self) -> None:
        transition = scheduler_transition({"entities": [entity(7, 2, 3, 12)]}, {"entities": [entity(7, 3, 3, 0)]})
        result = static_vacated_underlay_assertion(
            transition,
            after_cells={(2, 3): {"terrain_memory_glyph": 2378, "object_stack": [{"object_id": 1}], "monster_id": None}},
            after_glyphs=[[0] * 5 for _ in range(5)],
        )
        self.assertEqual(0, result["comparisons"])
        self.assertEqual("pass", result["status"])

    def test_unseen_vacated_cell_is_unjudged_not_a_false_underlay_error(self) -> None:
        transition = scheduler_transition({"entities": [entity(7, 2, 3, 12)]}, {"entities": [entity(7, 3, 3, 0)]})
        result = static_vacated_underlay_assertion(
            transition,
            after_cells={(2, 3): {"terrain_memory_glyph": 2378, "object_stack": [], "monster_id": None}},
            after_glyphs=[[0] * 5 for _ in range(5)],
            after_chars=[[32] * 5 for _ in range(5)],
        )
        self.assertEqual("pass", result["status"])
        self.assertEqual(0, result["comparisons"])

    def test_causal_join_requires_pre_frozen_occupancy_and_underlay(self) -> None:
        result = causal_transition_evidence(
            frame(7, 2, 3, 12),
            frame(7, 3, 3, 0, moves=2),
            before_cells=full_cells({(2, 3): 7}),
            after_cells=full_cells({(3, 3): 7}),
            source_case="heldout-core-9001",
            action={"action_id": 75, "action_name": "Command.SEARCH"},
        )

        self.assertEqual("pass", result["status"])
        self.assertEqual([7], result["before_occupancy"]["turn_queue"])
        record = result["records"][0]
        self.assertEqual("none", record["destination_pre_monster_occupancy"])
        self.assertEqual(2378, record["destination_cell_before"]["terrain_memory_glyph"])
        self.assertEqual([], record["destination_cell_before"]["object_stack"])
        self.assertEqual({"moves": 1, "monstermoves": 1}, result["source_turn"]["before"])
        self.assertEqual({"moves": 1, "monstermoves": 1}, result["source_turn"]["delta"])
        self.assertEqual("none", record["destination_pre_occupant_boundary_status"])

    def test_causal_join_fails_when_entity_list_and_grid_disagree(self) -> None:
        with self.assertRaisesRegex(ValueError, "disagree"):
            causal_transition_evidence(
                frame(7, 2, 3, 12),
                frame(7, 3, 3, 0, moves=2),
                before_cells=full_cells({}),
                after_cells=full_cells({(3, 3): 7}),
                source_case="heldout-core-9001",
                action={"action_id": 75, "action_name": "Command.SEARCH"},
            )

    def test_causal_join_rejects_a_post_selected_destination_cell_slice(self) -> None:
        with self.assertRaisesRegex(ValueError, "complete 79x21"):
            causal_transition_evidence(
                frame(7, 2, 3, 12),
                frame(7, 3, 3, 0, moves=2),
                before_cells=[cell(2, 3, 7), cell(3, 3, None)],
                after_cells=[cell(2, 3, None), cell(3, 3, 7)],
                source_case="heldout-core-9001",
                action={"action_id": 75, "action_name": "Command.SEARCH"},
            )

    def test_occupancy_rejects_a_queue_that_does_not_preserve_native_list_order(self) -> None:
        bad = frame(7, 2, 3, 12)
        bad["turn_queue"] = []
        with self.assertRaisesRegex(ValueError, "turn_queue"):
            occupancy_map(bad)

    def test_ready_is_not_sufficient_for_a_destination(self) -> None:
        stationary = causal_transition_evidence(
            frame(7, 2, 3, 12),
            frame(7, 2, 3, 0, moves=2),
            before_cells=full_cells({(2, 3): 7}),
            after_cells=full_cells({(2, 3): 7}),
            source_case="heldout-core-9002",
            action={"action_id": 83, "action_name": "MiscDirection.WAIT"},
        )
        moved = causal_transition_evidence(
            frame(8, 4, 3, 12),
            frame(8, 5, 3, 0, moves=2),
            before_cells=full_cells({(4, 3): 8}),
            after_cells=full_cells({(5, 3): 8}),
            source_case="heldout-core-9003",
            action={"action_id": 75, "action_name": "Command.SEARCH"},
        )
        assessment = destination_collision_rule_assessment([stationary, moved])

        movement = assessment["movement_points_threshold"]
        self.assertTrue(movement["observed_necessary_within_sample"])
        self.assertFalse(movement["observed_sufficient"])
        self.assertEqual("counterexample_found", movement["sufficiency_status"])
        self.assertEqual(7, movement["sufficiency_counterexamples"][0]["entity_id"])
        self.assertFalse(assessment["gold_scheduler_pathing_eligible"])

    def test_causal_join_preserves_preoccupied_destination_boundary_fate_without_calling_it_combat(self) -> None:
        before = {
            "source_turn": {"moves": 20, "monstermoves": 20},
            "turn_queue": [7, 8],
            "entities": [
                entity(7, 2, 3, 12),
                {**entity(8, 3, 3, 12), "scheduler": {"movement_points": 12, "iteration_order": 1}},
            ],
        }
        after = {
            "source_turn": {"moves": 20, "monstermoves": 20},
            "turn_queue": [7],
            "entities": [entity(7, 3, 3, 0)],
        }
        result = causal_transition_evidence(
            before,
            after,
            before_cells=full_cells({(2, 3): 7, (3, 3): 8}),
            after_cells=full_cells({(3, 3): 7}),
            source_case="heldout-core-9005",
            action={"action_id": 83, "action_name": "MiscDirection.WAIT"},
        )

        moved = next(record for record in result["records"] if record["entity_id"] == 7)
        self.assertEqual("other_entity", moved["destination_pre_monster_occupancy"])
        self.assertEqual(8, moved["destination_pre_monster_id"])
        self.assertEqual(1, moved["destination_pre_occupant_iteration_order_before"])
        self.assertEqual("removed", moved["destination_pre_occupant_boundary_status"])
        self.assertIsNone(moved["destination_pre_occupant_post_position"])
        self.assertEqual({"moves": 0, "monstermoves": 0}, result["source_turn"]["delta"])

        assessment = destination_collision_rule_assessment([result])
        outcomes = assessment["preoccupied_destination_boundary_outcomes"]
        self.assertEqual(1, outcomes["observed_count"])
        self.assertEqual({"removed": 1}, outcomes["outcomes"])
        self.assertFalse(assessment["gold_scheduler_pathing_eligible"])

    def test_causal_join_rejects_missing_or_invalid_source_turn_provenance(self) -> None:
        missing_before = frame(7, 2, 3, 12)
        missing_before.pop("source_turn")
        with self.assertRaisesRegex(ValueError, "before source_turn"):
            causal_transition_evidence(
                missing_before,
                frame(7, 3, 3, 0, moves=2),
                before_cells=full_cells({(2, 3): 7}),
                after_cells=full_cells({(3, 3): 7}),
                source_case="heldout-core-9006",
                action={"action_id": 75, "action_name": "Command.SEARCH"},
            )

        invalid_after = frame(7, 3, 3, 0, moves=2)
        invalid_after["source_turn"] = {"moves": -1, "monstermoves": 2}
        with self.assertRaisesRegex(ValueError, "invalid after source_turn.moves"):
            causal_transition_evidence(
                frame(7, 2, 3, 12),
                invalid_after,
                before_cells=full_cells({(2, 3): 7}),
                after_cells=full_cells({(3, 3): 7}),
                source_case="heldout-core-9007",
                action={"action_id": 75, "action_name": "Command.SEARCH"},
            )

    def test_assertion_only_promotion_candidate_is_schema_complete_but_gold_blocked(self) -> None:
        causal = causal_transition_evidence(
            frame(7, 2, 3, 12),
            frame(7, 2, 3, 0, moves=2),
            before_cells=full_cells({(2, 3): 7}),
            after_cells=full_cells({(2, 3): 7}),
            source_case="heldout-core-9004",
            action={"action_id": 83, "action_name": "MiscDirection.WAIT"},
        )
        assessment = destination_collision_rule_assessment([causal])
        candidate = _promotion_candidate(
            cases=[{"steps": [{"causal_transition": causal, "underlay": {"comparisons": 0}}]}],
            rule_assessment=assessment,
            source_error_count=0,
            repeated_exact=True,
        )
        gate = evaluate_promotion(candidate)

        self.assertTrue(gate["source_assertion_eligible"])
        self.assertFalse(gate["gold_implementation_eligible"])
        self.assertIn("python_rust_parity_not_proven", gate["failures"])
        self.assertFalse(candidate["gold_implementation_eligible"])


if __name__ == "__main__":
    unittest.main()
