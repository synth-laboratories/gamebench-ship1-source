#!/usr/bin/env python3
"""Verify canonical Craftax-Coop fixtures without rewriting them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenario_fixtures import TASK_DIR, fixture_documents, load_scenarios


def main() -> None:
    generated = fixture_documents(load_scenarios())
    paths = (
        TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json",
        TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json",
        TASK_DIR / "fixtures" / "gold" / "states" / "states.json",
    )
    failures: list[str] = []
    for path, actual in zip(paths, generated, strict=True):
        if not path.exists():
            failures.append(f"missing fixture: {path.relative_to(TASK_DIR)}")
            continue
        expected = json.loads(path.read_text())
        if expected != actual:
            failures.append(_first_difference(path, expected, actual))
    if failures:
        print("Craftax-Coop fixture verification FAILED")
        print("\n".join(failures))
        raise SystemExit(1)
    print(f"Craftax-Coop fixture verification OK ({len(generated[0]['scenarios'])} scenarios)")


def _first_difference(path: Path, expected: Any, actual: Any, location: str = "$") -> str:
    if type(expected) is not type(actual):
        return f"{path.name} {location}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return f"{path.name} {location}: key mismatch expected={sorted(expected)} actual={sorted(actual)}"
        for key in expected:
            if expected[key] != actual[key]:
                return _first_difference(path, expected[key], actual[key], f"{location}.{key}")
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path.name} {location}: length expected={len(expected)} actual={len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left != right:
                return _first_difference(path, left, right, f"{location}[{index}]")
    return f"{path.name} {location}: expected={expected!r} actual={actual!r}"


if __name__ == "__main__":
    main()
