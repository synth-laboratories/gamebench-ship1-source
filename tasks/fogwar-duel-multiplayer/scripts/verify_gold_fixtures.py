#!/usr/bin/env python3
"""Verify checked-in Fog Duel Lite fixtures without rewriting them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenario_fixtures import TASK_DIR, fixture_documents


def compare(path: Path, expected: Any, actual: Any) -> str | None:
    if expected != actual:
        return f"fixture drift: {path.relative_to(TASK_DIR)}"
    return None


def main() -> None:
    documents = fixture_documents()
    paths = (
        TASK_DIR / "fixtures/gold/scenarios/scenarios.json",
        TASK_DIR / "fixtures/gold/eventlogs/eventlogs.json",
        TASK_DIR / "fixtures/gold/states/states.json",
        TASK_DIR / "fixtures/gold/checkpoints/checkpoints.json",
    )
    failures = [compare(path, json.loads(path.read_text()), actual) if path.exists() else f"missing fixture: {path.relative_to(TASK_DIR)}" for path, actual in zip(paths, documents, strict=True)]
    failures = [failure for failure in failures if failure]
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Fog Duel Lite fixture verification OK ({len(documents[0]['scenarios'])} scenarios)")


if __name__ == "__main__":
    main()
