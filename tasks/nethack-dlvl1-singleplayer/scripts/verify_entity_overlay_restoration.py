#!/usr/bin/env python3
"""Verify the source-visible part of dynamic overlay vacating.

This deliberately consumes the existing live differential artifact rather than
adding another fuzzer contract.  A matching glyph is only presentation
continuity; it does not identify a NetHack monster or pet.  The assertion is
therefore limited to the part NLE actually exposes: when a presentation
continuity event vacates a still-visible square, the next source plane renders
direct static terrain at that exact coordinate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATIC_TERRAIN = frozenset(".#|-+<>_{}~")


def restoration_report(run: dict[str, Any], *, min_distinct_seeds: int = 3) -> dict[str, Any]:
    """Extract a bounded, multi-seed source assertion from a live run."""

    observed: list[dict[str, Any]] = []
    not_visible: list[dict[str, Any]] = []
    for case in run.get("reports", []):
        if not isinstance(case, dict):
            continue
        fixture_id = str(case.get("fixture_id", ""))
        # Both lanes have the same NLE expectation.  Reading one avoids
        # counting source events twice and does not prefer either gold lane.
        lanes = case.get("lanes", [])
        if not isinstance(lanes, list) or not lanes:
            continue
        contract = lanes[0].get("visibility_entity_transition_oracle_v1", {})
        if not isinstance(contract, dict):
            continue
        for transition in contract.get("transitions", []):
            if not isinstance(transition, dict):
                continue
            entities = transition.get("entities", {})
            if not isinstance(entities, dict):
                continue
            restorations = entities.get("vacated_cell_restoration", [])
            restored_by_coordinate = {
                (int(entry["vacated"]["x"]), int(entry["vacated"]["y"])): entry
                for entry in restorations
                if isinstance(entry, dict) and isinstance(entry.get("vacated"), dict) and isinstance(entry.get("restored_static"), dict)
            }
            for movement in entities.get("moved", []):
                if not isinstance(movement, dict) or movement.get("identity_status") != "presentation_continuity_only":
                    continue
                origin = movement.get("from")
                if not isinstance(origin, dict):
                    continue
                coordinate = (int(origin["x"]), int(origin["y"]))
                context = {"fixture_id": fixture_id, "step": int(transition.get("step", -1)), "movement": movement}
                restoration = restored_by_coordinate.get(coordinate)
                if restoration is None:
                    not_visible.append(context)
                    continue
                static = restoration["restored_static"]
                if static.get("provenance") != "observed_surface_static" or static.get("char") not in STATIC_TERRAIN:
                    raise AssertionError(f"restoration at {fixture_id}:{coordinate} is not direct static source evidence: {static!r}")
                observed.append({**context, "restoration": restoration})
    seeds = sorted({entry["fixture_id"] for entry in observed})
    return {
        "schema": "gamebench.nethack.entity_overlay_restoration.v1",
        "identity_claim": "presentation continuity only; no entity identity is inferred",
        "distinct_source_cases": len(seeds),
        "min_distinct_source_cases": min_distinct_seeds,
        "visible_vacated_restorations": observed,
        "not_visible_after_presentation_motion": not_visible,
        "status": "pass" if len(seeds) >= min_distinct_seeds else "insufficient_source_evidence",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Live fuzzer run.json")
    parser.add_argument("--min-distinct-seeds", type=int, default=3)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.min_distinct_seeds < 1:
        raise SystemExit("--min-distinct-seeds must be positive")
    report = restoration_report(json.loads(args.run.read_text()), min_distinct_seeds=args.min_distinct_seeds)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report), "distinct_source_cases": report["distinct_source_cases"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
