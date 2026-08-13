from __future__ import annotations

import unittest

from scripts.verify_lldb_mcalcmove import _join_events, _valid


def _event(*, event_id: int = 0, step: int = 1, allocation: int = 12) -> dict[str, object]:
    actor = {"entity_id": 7, "movement_points": 0, "native_x": 12, "native_y": 8}
    return {
        "kind": "mcalcmove_return",
        "event_id": event_id,
        "step": step,
        "action": {"step": step, "action_id": 75, "action_name": "Command.SEARCH"},
        "allocation": allocation,
        "entry_location": {"function": "mcalcmove"},
        "return_location": {"function": "moveloop"},
        "actor": actor,
        "actor_after": dict(actor),
    }


class McalcmoveTraceTests(unittest.TestCase):
    def test_zero_allocation_is_a_valid_source_return(self) -> None:
        events, errors = _valid([_event(allocation=0)], 1)
        self.assertEqual(1, len(events))
        self.assertEqual(0, errors)

    def test_negative_allocation_fails_closed(self) -> None:
        events, errors = _valid([_event(allocation=-1)], 1)
        self.assertEqual([], events)
        self.assertEqual(1, errors)

    def test_join_rejects_missing_scheduler_frame(self) -> None:
        events, errors = _join_events({"frames": [{"entities": {"entities": [], "source_turn": {"moves": 1, "monstermoves": 1}}}]}, [_event()])
        self.assertEqual([], events)
        self.assertEqual(1, errors)


if __name__ == "__main__":
    unittest.main()
