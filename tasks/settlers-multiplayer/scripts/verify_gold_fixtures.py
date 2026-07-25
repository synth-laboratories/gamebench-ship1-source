#!/usr/bin/env python3
"""Verify fixtures without modifying them."""
from __future__ import annotations
import json
from scenario_fixtures import TASK_DIR, fixture_documents

def main() -> None:
    generated = fixture_documents()
    paths = (TASK_DIR / "fixtures/gold/scenarios/scenarios.json", TASK_DIR / "fixtures/gold/eventlogs/eventlogs.json", TASK_DIR / "fixtures/gold/states/states.json")
    mismatches = [str(path.relative_to(TASK_DIR)) for path, actual in zip(paths, generated, strict=True) if not path.exists() or json.loads(path.read_text()) != actual]
    if mismatches:
        raise SystemExit("settlers fixture mismatch: " + ", ".join(mismatches))
    print(f"Settlers fixture verification OK ({len(generated[0]['scenarios'])} scenarios)")

if __name__ == "__main__":
    main()
