#!/usr/bin/env python3
"""ROM-free regression tests for mGBA JSONL controller encoding.

``python-mgba`` exposes the GBA button constants as enum indices and
``Core.set_keys(*keys)`` accepts those indices as positional arguments.  A
JSONL chord must therefore remain separate arguments; OR-ing enum indices
loses buttons before the binding performs its own bit-mask conversion.
"""

from __future__ import annotations

import importlib.util
import importlib.metadata
import inspect
import ast
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


def load_adapter():
    """Import the adapter with a deliberately tiny, ROM-free mGBA stub."""
    mgba = types.ModuleType("mgba")
    core = types.ModuleType("mgba.core")
    image = types.ModuleType("mgba.image")
    log = types.ModuleType("mgba.log")
    mgba.core = core
    mgba.image = image
    mgba.log = log
    prior = {name: sys.modules.get(name) for name in ("mgba", "mgba.core", "mgba.image", "mgba.log")}
    sys.modules.update({"mgba": mgba, "mgba.core": core, "mgba.image": image, "mgba.log": log})
    try:
        path = Path(__file__).with_name("mgba_jsonl_oracle.py")
        prior_path = list(sys.path)
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location("emerald_mgba_adapter_under_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        # The actual binding is deliberately only installed in the pinned
        # oracle image. Its version is not relevant to this pure encoding
        # contract, so keep the test host-independent.
        with mock.patch.object(importlib.metadata, "version", return_value="test"):
            spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = prior_path
        for name, value in prior.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


ADAPTER = load_adapter()


class FakeCore:
    KEY_A = 0
    KEY_B = 1
    KEY_SELECT = 2
    KEY_START = 3
    KEY_RIGHT = 4
    KEY_LEFT = 5
    KEY_UP = 6
    KEY_DOWN = 7
    KEY_R = 8
    KEY_L = 9

    def __init__(self) -> None:
        self.key_calls: list[tuple[int, ...]] = []
        self.frame_count = 0

    def set_keys(self, *keys: int) -> None:
        self.key_calls.append(keys)

    def run_frame(self) -> None:
        self.frame_count += 1


class MgbaJsonlInputEncodingTest(unittest.TestCase):
    def oracle_with_fake_core(self) -> tuple[object, FakeCore]:
        oracle = ADAPTER.Oracle()
        core = FakeCore()
        oracle.core = core
        # ``step``'s controller behavior is the subject here; a real frame or
        # source-state memory map would make this a ROM-bearing integration test.
        oracle._response = lambda _rgb: {"ok": True}  # type: ignore[method-assign]
        oracle._frame_rgb = lambda: b""  # type: ignore[method-assign]
        return oracle, core

    def test_each_named_button_is_its_single_enum_index(self) -> None:
        expected = {
            "a": 0, "b": 1, "select": 2, "start": 3, "right": 4,
            "left": 5, "up": 6, "down": 7, "r": 8, "l": 9,
        }
        for button, index in expected.items():
            with self.subTest(button=button):
                oracle, core = self.oracle_with_fake_core()
                oracle.step({"buttons": [button]})
                self.assertEqual([(index,), ()], core.key_calls)
                self.assertEqual(1, core.frame_count)

    def test_multiple_buttons_remain_separate_positional_indices(self) -> None:
        oracle, core = self.oracle_with_fake_core()
        oracle.step({"buttons": ["a", "up", "left", "r"]})
        self.assertEqual([(0, 6, 5, 8), ()], core.key_calls)
        self.assertEqual(1, core.frame_count)

    def test_zero_is_never_used_as_a_positional_release_key(self) -> None:
        # In python-mGBA, KEY_A is enum index zero. Calling ``set_keys(0)``
        # after a frame therefore holds A for the next frame rather than
        # clearing the key list. This covers both ``load`` and ``step``.
        tree = ast.parse(inspect.getsource(ADAPTER.Oracle))
        bad_calls = [
            call
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "set_keys"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == 0
        ]
        self.assertEqual([], bad_calls)

    def test_duplicate_and_unknown_buttons_are_rejected_before_core_access(self) -> None:
        oracle, core = self.oracle_with_fake_core()
        with self.assertRaisesRegex(ValueError, "duplicates"):
            oracle.step({"buttons": ["a", "a"]})
        with self.assertRaisesRegex(ValueError, "unknown button"):
            oracle.step({"buttons": ["turbo"]})
        self.assertEqual([], core.key_calls)
        self.assertEqual(0, core.frame_count)


if __name__ == "__main__":
    unittest.main()
