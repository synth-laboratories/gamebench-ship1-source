#!/usr/bin/env python3
"""Generate defaults/layouts/*.json from the canonical layout catalog."""

from __future__ import annotations

import json
from pathlib import Path

from layout_catalog import LAYOUT_SPECS


TASK_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = TASK_DIR / "defaults" / "layouts"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for layout_id, spec in sorted(LAYOUT_SPECS.items()):
        doc = {"layout_id": layout_id, "ascii": list(spec["ascii"])}
        if spec.get("possible_recipes"):
            doc["possible_recipes"] = spec["possible_recipes"]
        if spec.get("recipe_pool"):
            doc["recipe_pool"] = spec["recipe_pool"]
        if spec.get("swap_agents"):
            doc["swap_agents"] = True
        path = OUTPUT_DIR / f"{layout_id}.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        written.append(layout_id)
    index_path = OUTPUT_DIR / "index.json"
    index_path.write_text(
        json.dumps({"schema": "gamebench.overcooked_v2.layout_index.v1", "layout_ids": written}, indent=2)
        + "\n"
    )
    print(f"wrote {len(written)} catalog layouts to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
