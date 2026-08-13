"""Validity guards for the source-owned SEARCH RNG boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from shared.task_resolve import resolve_task
from tests.test_kick_rng_assertions import KickRngValidityTests


class _SearchReceiptSpy:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def consume_search(self, **kwargs: object) -> dict[str, object]:
        include = kwargs.get("include_pre_movemon_draw")
        if type(include) is not bool:
            raise AssertionError("SEARCH receipt did not receive a boolean draw gate")
        self.calls.append(include)
        return {"hidden_doors": [], "found_traps": [], "draws": [], "core_draws": 0}


class SearchRngReceiptTests(unittest.TestCase):
    def _engine(self) -> NethackDlvl1Engine:
        task = KickRngValidityTests._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        # The fixture's reset map is intentionally absent; this test isolates
        # only the engine's receipt-bound gate, not source terrain scanning.
        engine.state["dynamic_pet_runtime_enabled"] = True
        engine._scheduler = _SearchReceiptSpy()  # type: ignore[assignment]
        return engine

    def test_search_has_no_unconditional_pre_movemon_draw(self) -> None:
        engine = self._engine()
        spy = engine._scheduler
        assert isinstance(spy, _SearchReceiptSpy)
        engine.resolved["seed"] = 20260731
        for step in (1, 26, 34, 35):
            engine.state["step_index"] = step
            engine._search()
        self.assertEqual([False, False, False, False], spy.calls)

    def test_search_does_not_reintroduce_synthetic_draw_for_other_seed(self) -> None:
        engine = self._engine()
        spy = engine._scheduler
        assert isinstance(spy, _SearchReceiptSpy)
        engine.resolved["seed"] = 20260730
        engine.state["step_index"] = 35
        engine._search()
        self.assertEqual([False], spy.calls)


if __name__ == "__main__":
    unittest.main()
