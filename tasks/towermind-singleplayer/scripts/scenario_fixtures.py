"""Shared deterministic fixture projection helpers; not used by either gold lane."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))
from gold_python.engine import run_scenario


def load_scenarios() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted((TASK_DIR / "defaults" / "scenarios").glob("*.json"))]


def fixture_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scenarios = load_scenarios()
    completed = [run_scenario(item) for item in scenarios]
    return (
        {"schema": "gamebench.towermind.fixtures.v1", "scenarios": scenarios},
        {"schema": "gamebench.towermind.eventlogs.v1", "eventlogs": [{"id": item["scenario"], "events": item["projection"]["events"]} for item in completed]},
        {"schema": "gamebench.towermind.states.v1", "states": [{"id": item["scenario"], "projection": item["projection"], "checkpoint": item["checkpoint"]} for item in completed]},
    )


def first_difference(expected: Any, actual: Any, location: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{location}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return f"{location}: keys differ expected={sorted(expected)} actual={sorted(actual)}"
        for key in expected:
            result = first_difference(expected[key], actual[key], f"{location}.{key}")
            if result:
                return result
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{location}: lengths differ expected={len(expected)} actual={len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            result = first_difference(left, right, f"{location}[{index}]")
            if result:
                return result
    if expected != actual:
        return f"{location}: expected={expected!r} actual={actual!r}"
    return None
