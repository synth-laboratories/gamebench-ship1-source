from __future__ import annotations

import unittest

from scripts.verify_lldb_dogmove_returns import _join_pre_action_state, _valid


class DogMoveReturnTraceTests(unittest.TestCase):
    def test_return_one_without_displacement_is_a_valid_completion(self) -> None:
        event = {
            "kind": "dog_move_return", "event_id": 7, "step": 4, "return_code": 1,
            "actor": {"entity_id": 33, "native_x": 14, "native_y": 18},
            "actor_after": {"entity_id": 33, "native_x": 14, "native_y": 18},
        }
        self.assertEqual(([event], 0), _valid([event], 5))

    def test_bad_return_boundary_fails_closed(self) -> None:
        event = {"kind": "dog_move_return", "event_id": 1, "step": 1, "return_code": 9, "actor": {"entity_id": 1}, "actor_after": {"entity_id": 1}}
        self.assertEqual(([], 1), _valid([event], 1))

    def test_pre_action_join_binds_entity_and_hero_scheduler(self) -> None:
        event = {"step": 2, "actor": {"entity_id": 33}}
        run = {"frames": [{"entities": {"source_turn": {"moves": 0}, "entities": [{"entity_id": 33, "scheduler": {"movement_points": 0}}]}, "player": {"player": {"scheduler": {"movement_points": 0}}}}, {"entities": {"source_turn": {"moves": 1}, "entities": [{"entity_id": 33, "scheduler": {"movement_points": 12}}]}, "player": {"player": {"scheduler": {"movement_points": 12}}}}]}
        state, error = _join_pre_action_state(run, event)
        self.assertIsNone(error)
        self.assertEqual(12, state["entity"]["scheduler"]["movement_points"])
        self.assertEqual(12, state["player_scheduler"]["movement_points"])

    def test_pre_action_join_rejects_ambiguous_entity(self) -> None:
        event = {"step": 1, "actor": {"entity_id": 33}}
        run = {"frames": [{"entities": {"source_turn": {"moves": 0}, "entities": [{"entity_id": 33, "scheduler": {"movement_points": 0}}, {"entity_id": 33, "scheduler": {"movement_points": 0}}]}, "player": {"player": {"scheduler": {"movement_points": 0}}}}]}
        state, error = _join_pre_action_state(run, event)
        self.assertIsNone(state)
        self.assertEqual("pre_action_entity_join_not_unique", error)


if __name__ == "__main__":
    unittest.main()
