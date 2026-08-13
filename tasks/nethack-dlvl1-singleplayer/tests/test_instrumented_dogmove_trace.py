from __future__ import annotations

import ctypes
import unittest

from scripts.verify_instrumented_dogmove_trace import (
    DEFAULT_ACTIONS,
    DogTraceEvent,
    DogTraceReader,
    TRACE_KINDS,
    first_difference,
)


class FakeDogTraceLibrary:
    def __init__(self, event: DogTraceEvent | None = None, *, overflow: bool = False, readable: bool = True):
        self.event = event
        self.overflow_value = overflow
        self.readable = readable

    def nle_dog_trace_overflow(self) -> int:
        return int(self.overflow_value)

    def nle_dog_trace_count(self) -> int:
        return 1 if self.event is not None else 0

    def nle_dog_trace_get(self, index: int, output: ctypes.POINTER(DogTraceEvent)) -> int:
        if not self.readable or self.event is None or index != 0:
            return 0
        ctypes.memmove(output, ctypes.byref(self.event), ctypes.sizeof(DogTraceEvent))
        return 1


def reader_for(event: DogTraceEvent | None = None, **kwargs: object) -> DogTraceReader:
    reader = DogTraceReader.__new__(DogTraceReader)
    reader.lib = FakeDogTraceLibrary(event, **kwargs)  # type: ignore[assignment]
    return reader


class InstrumentedDogmoveTraceTests(unittest.TestCase):
    def test_abi_layout_and_action_tape_are_pinned(self) -> None:
        self.assertEqual(80, ctypes.sizeof(DogTraceEvent))
        self.assertEqual(list(range(1, 10)), sorted(TRACE_KINDS))
        self.assertEqual(32, len(DEFAULT_ACTIONS))
        self.assertEqual(DEFAULT_ACTIONS, [1, 3, 0, 7, 4, 6, 3, 3, 0, 0, 6, 2, 3, 4, 3, 5, 0, 4, 7, 4, 5, 6, 2, 6, 3, 3, 3, 2, 6, 7, 7, 5])

    def test_valid_object_event_decodes(self) -> None:
        event = DogTraceEvent(kind=3, entity_id=23, object_id=7, object_type=37, object_where=3, object_quantity=2)
        decoded = reader_for(event).events()
        self.assertEqual("dogfood", decoded[0]["kind"])
        self.assertEqual(7, decoded[0]["object_id"])

    def test_overflow_unknown_and_unmatched_events_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "overflow"):
            reader_for(DogTraceEvent(kind=3, entity_id=23, object_id=1), overflow=True).events()
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            reader_for(DogTraceEvent(kind=99, entity_id=23, object_id=1)).events()
        with self.assertRaisesRegex(RuntimeError, "no entity"):
            reader_for(DogTraceEvent(kind=1, entity_id=0)).events()
        with self.assertRaisesRegex(RuntimeError, "no object"):
            reader_for(DogTraceEvent(kind=4, object_id=0)).events()
        with self.assertRaisesRegex(RuntimeError, "unreadable"):
            reader_for(DogTraceEvent(kind=3, entity_id=23, object_id=1), readable=False).events()

    def test_first_difference_identifies_step_without_comparing_prefix_only(self) -> None:
        self.assertIsNone(first_difference([{"x": 1}], [{"x": 1}]))
        difference = first_difference([{"x": 1}, {"x": 2}], [{"x": 1}, {"x": 3}])
        self.assertEqual(1, difference["step"])
        self.assertEqual("length", first_difference([1], [1, 2])["reason"])


if __name__ == "__main__":
    unittest.main()
