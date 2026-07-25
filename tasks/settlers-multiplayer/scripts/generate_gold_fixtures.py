#!/usr/bin/env python3
"""Generate deterministic owned-gold fixtures."""
from __future__ import annotations
import json
from pathlib import Path
from scenario_fixtures import TASK_DIR, fixture_documents

def main() -> None:
    documents = fixture_documents()
    paths = (TASK_DIR / "fixtures/gold/scenarios/scenarios.json", TASK_DIR / "fixtures/gold/eventlogs/eventlogs.json", TASK_DIR / "fixtures/gold/states/states.json")
    for path, document in zip(paths, documents, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(documents[0]['scenarios'])} settlers-rules fixtures")

if __name__ == "__main__":
    main()
