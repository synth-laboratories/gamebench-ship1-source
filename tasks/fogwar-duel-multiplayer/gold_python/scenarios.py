"""Pinned scenario loading for the Fog Duel Lite gold authorities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = TASK_ROOT / "defaults" / "scenarios"


def load_scenario(scenario_id: str) -> dict[str, Any]:
    path = SCENARIO_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise ValueError(f"unknown Fog Duel scenario: {scenario_id}")
    return json.loads(path.read_text())


def load_all_scenarios() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted(SCENARIO_DIR.glob("*.json"))]
