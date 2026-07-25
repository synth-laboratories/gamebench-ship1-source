#!/usr/bin/env python3
"""Generate the checked-in deterministic Fog Duel Lite fixture bundle."""

from __future__ import annotations

import json
from pathlib import Path

from scenario_fixtures import TASK_DIR, fixture_documents


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    scenarios, events, states, checkpoints = fixture_documents()
    outputs = {
        TASK_DIR / "fixtures/gold/scenarios/scenarios.json": scenarios,
        TASK_DIR / "fixtures/gold/eventlogs/eventlogs.json": events,
        TASK_DIR / "fixtures/gold/states/states.json": states,
        TASK_DIR / "fixtures/gold/checkpoints/checkpoints.json": checkpoints,
    }
    for path, value in outputs.items():
        write(path, value)
    print(f"wrote {len(scenarios['scenarios'])} Fog Duel Lite fixtures")


if __name__ == "__main__":
    main()
