#!/usr/bin/env python3
"""Generate canonical Craftax-Coop scenario, NEV, and state fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from scenario_fixtures import TASK_DIR, fixture_documents, load_scenarios


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    scenarios, eventlogs, states = fixture_documents(load_scenarios())
    outputs = {
        TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json": scenarios,
        TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json": eventlogs,
        TASK_DIR / "fixtures" / "gold" / "states" / "states.json": states,
    }
    for path, value in outputs.items():
        write_json(path, value)
    print(f"wrote {len(scenarios['scenarios'])} Craftax-Coop fixtures across {len(outputs)} artifacts")


if __name__ == "__main__":
    main()
