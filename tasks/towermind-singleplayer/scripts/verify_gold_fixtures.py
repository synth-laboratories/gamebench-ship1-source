#!/usr/bin/env python3
"""Verify checked-in TowerMind fixtures without modifying them."""

from __future__ import annotations

import json

from scenario_fixtures import TASK_DIR, first_difference, fixture_documents


def main() -> None:
    generated = fixture_documents()
    paths = (
        TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json",
        TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json",
        TASK_DIR / "fixtures" / "gold" / "states" / "states.json",
    )
    failures: list[str] = []
    for path, actual in zip(paths, generated, strict=True):
        if not path.exists():
            failures.append(f"missing {path.relative_to(TASK_DIR)}")
            continue
        difference = first_difference(json.loads(path.read_text()), actual)
        if difference:
            failures.append(f"{path.name}: {difference}")
    if failures:
        raise SystemExit("TowerMind fixture verification FAILED\n" + "\n".join(failures))
    print(f"TowerMind fixture verification OK ({len(generated[0]['scenarios'])} scenarios)")


if __name__ == "__main__":
    main()
