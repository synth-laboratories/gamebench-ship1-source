#!/usr/bin/env python3
"""Regenerate checked-in canonical TowerMind fixture artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from scenario_fixtures import TASK_DIR, fixture_documents


def main() -> None:
    scenarios, eventlogs, states = fixture_documents()
    outputs = {
        TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json": scenarios,
        TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json": eventlogs,
        TASK_DIR / "fixtures" / "gold" / "states" / "states.json": states,
    }
    for path, document in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(scenarios['scenarios'])} TowerMind fixtures across {len(outputs)} artifacts")


if __name__ == "__main__":
    main()
