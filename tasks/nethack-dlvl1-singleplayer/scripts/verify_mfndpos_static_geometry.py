#!/usr/bin/env python3
"""Audit reset-map neighbourhood admissibility against exact ``mfndpos``.

The LLDB branch trace is source-only evidence.  This verifier compares only
the static, reset-owned terrain predicate against each invocation's exact
candidate array.  A missing source candidate is a concrete map-model bug;
an extra candidate is expected until occupancy, traps, line-of-sight and the
hero/monster attack branches are implemented.  Neither result is imported
into a gold runtime or a conformance denominator.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.source_scheduler import ResetOwnedScheduler


SCHEMA = "gamebench.nethack.mfndpos_static_geometry_audit.v1"
TRACE_SCHEMA = "gamebench.nethack.lldb_branch_candidate_trace.v1"
ZERO_CONTROLS = (
    "public_observation_mismatch_count",
    "native_boundary_mismatch_count",
    "final_rng_state_mismatch_count",
    "trace_replay_mismatch_count",
    "unmatched_event_count",
    "trace_error_count",
)


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x, y = value.get("native_x"), value.get("native_y")
    return (x, y) if type(x) is int and type(y) is int else None


def _static_candidates(
    reset_map: dict[str, Any],
    actor: tuple[int, int],
    hero: tuple[int, int] | None = None,
) -> set[tuple[int, int]]:
    """Return native-coordinate neighbours accepted by reset terrain alone.

    ``dog_move`` does not set ``ALLOW_U``.  When the trace provides the
    pre-action hero coordinate, the hero cell is therefore an exact static
    attack/collision exclusion rather than an unresolved occupancy guess.
    """

    scheduler = ResetOwnedScheduler({"entities": []}, None)
    source_x, source_y = actor[0] - 1, actor[1]
    result: set[tuple[int, int]] = set()
    for x in range(max(0, source_x - 1), min(78, source_x + 1) + 1):
        for y in range(max(0, source_y - 1), min(20, source_y + 1) + 1):
            if (x, y) != (source_x, source_y) and (hero is None or (x + 1, y) != hero) and scheduler._pet_cell_walkable(reset_map, x, y):
                result.add((x + 1, y))
    return result


def _load_map(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if isinstance(value.get("authoritative_reset_map"), dict):
        value = value["authoritative_reset_map"]
    if not isinstance(value, dict):
        raise ValueError(f"{path}: reset map is not an object")
    for name in ("terrain_type", "terrain_flags", "terrain_horizontal"):
        rows = value.get(name)
        if not isinstance(rows, list) or len(rows) != 21 or any(not isinstance(row, list) or len(row) != 79 for row in rows):
            raise ValueError(f"{path}: malformed {name} plane")
    return value


def _parse_map_args(values: list[str]) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--level-dump values must be SEED=PATH")
        seed_text, path_text = value.split("=", 1)
        seed = int(seed_text)
        if seed in result:
            raise ValueError(f"duplicate level-dump seed {seed}")
        result[seed] = Path(path_text)
    if not result:
        raise ValueError("at least one --level-dump SEED=PATH is required")
    return result


def audit(trace: dict[str, Any], maps: dict[int, Path]) -> dict[str, Any]:
    if trace.get("schema") != TRACE_SCHEMA:
        raise ValueError("trace schema mismatch")
    controls = trace.get("equivalence_gate", {}).get("controls") or trace.get("controls")
    if not isinstance(controls, dict) or any(controls.get(key) != 0 for key in ZERO_CONTROLS):
        raise ValueError("trace lacks zero-mismatch exact-wheel controls")
    candidate = trace.get("frontier_candidate", trace)
    records = candidate.get("branch_records") if isinstance(candidate, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError("trace has no branch records")
    loaded = {seed: _load_map(path) for seed, path in maps.items()}
    comparisons = 0
    missing_count = 0
    extra_count = 0
    structural_errors: list[dict[str, Any]] = []
    missing_examples: list[dict[str, Any]] = []
    extra_examples: list[dict[str, Any]] = []
    per_seed: Counter[int] = Counter()
    for index, record in enumerate(records):
        seed = record.get("seed")
        if seed not in loaded:
            continue
        mfndpos = record.get("mfndpos")
        if not isinstance(mfndpos, dict):
            structural_errors.append({"record": index, "seed": seed, "error": "missing_mfndpos"})
            continue
        actor = _point(mfndpos.get("actor_at_mfndpos_return"))
        candidates = mfndpos.get("candidates")
        if actor is None or not isinstance(candidates, list):
            structural_errors.append({"record": index, "seed": seed, "error": "malformed_actor_or_candidates"})
            continue
        source_points = {_point(value) for value in candidates}
        if None in source_points:
            structural_errors.append({"record": index, "seed": seed, "error": "malformed_candidate"})
            continue
        source_points = {value for value in source_points if value is not None}
        static_points = _static_candidates(loaded[seed], actor)
        missing = sorted(source_points - static_points)
        extra = sorted(static_points - source_points)
        comparisons += 1
        per_seed[seed] += 1
        missing_count += len(missing)
        extra_count += len(extra)
        if missing and len(missing_examples) < 20:
            missing_examples.append({"record": index, "seed": seed, "step": record.get("step"), "actor": {"native_x": actor[0], "native_y": actor[1]}, "missing": [{"native_x": x, "native_y": y} for x, y in missing]})
        if extra and len(extra_examples) < 20:
            extra_examples.append({"record": index, "seed": seed, "step": record.get("step"), "actor": {"native_x": actor[0], "native_y": actor[1]}, "extra": [{"native_x": x, "native_y": y} for x, y in extra]})
    static_eligible = comparisons > 0 and not structural_errors and missing_count == 0
    return {
        "schema": SCHEMA,
        "status": "source_static_geometry_eligible" if static_eligible else "source_static_geometry_blocked",
        "source_only": True,
        "gold_implementation_eligible": False,
        "controls": {
            "comparison_count": comparisons,
            "structural_error_count": len(structural_errors),
            "source_candidate_missing_from_static_map": missing_count,
            "static_candidate_not_in_source_mfndpos": extra_count,
        },
        "seed_comparison_counts": dict(sorted(per_seed.items())),
        "missing_examples": missing_examples,
        "extra_examples": extra_examples,
        "structural_errors": structural_errors,
        "interpretation": {
            "missing": "A source mfndpos candidate is rejected by the reset terrain model; this is an actionable map/door/passability defect.",
            "extra": "Reset terrain admits a neighbour that source filtered using occupancy, traps, line-of-sight, diagonal rules, or attack semantics; this is not evidence to move the pet.",
            "promotion": "Static geometry is necessary but insufficient for dog_move promotion; exact pre-action destination, collision/attack, RNG chronology, Python/Rust parity, and held-out replay remain required.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--level-dump", action="append", default=[], metavar="SEED=PATH")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.trace.read_text()), _parse_map_args(args.level_dump))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
