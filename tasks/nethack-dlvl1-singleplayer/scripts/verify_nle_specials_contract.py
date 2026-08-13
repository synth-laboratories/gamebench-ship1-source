#!/usr/bin/env python3
"""Audit the public NLE v0.9.0 ``specials`` mapglyph plane.

This is an oracle evidence command, not a gold-engine dependency.  It proves
the public wire shape and the source-defined glyph-correlated bits across
multiple seeded resets, then records which observed flags need NetHack state
that the capture-backed gold task does not own.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset, project
from shared.nle_specials import (
    ALL_SPECIAL_BITS,
    MG_CORPSE,
    MG_DETECT,
    MG_INVIS,
    MG_OBJPILE,
    MG_PET,
    MG_RIDDEN,
    MG_STATUE,
    SOURCE_COMMIT,
    UNSUPPORTED_SPECIAL_BITS,
)


PREDICATE_BITS = (
    (MG_CORPSE, "glyph_is_body"),
    (MG_INVIS, "glyph_is_invisible"),
    (MG_DETECT, "glyph_is_detected_monster"),
    (MG_PET, "glyph_is_pet"),
    (MG_RIDDEN, "glyph_is_ridden_monster"),
    (MG_STATUE, "glyph_is_statue"),
)


def _assert_shape(plane: Any) -> list[list[int]]:
    if not isinstance(plane, list) or len(plane) != 21:
        raise AssertionError("NLE specials must be a 21-row public plane")
    rows: list[list[int]] = []
    for row in plane:
        if not isinstance(row, list) or len(row) != 79 or any(type(value) is not int or not 0 <= value <= 255 for value in row):
            raise AssertionError("NLE specials must be a 21x79 uint8 public plane")
        rows.append([int(value) for value in row])
    return rows


def observe_seed(seed: int, *, character: str) -> dict[str, Any]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - command guard
        raise RuntimeError("NLE 0.9.0 is required for the specials source audit") from error
    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        projection = project(normalise_reset(env.reset()))
        specials = _assert_shape(projection.get("specials"))
        glyphs = projection.get("glyphs")
        chars = projection.get("chars")
        if not isinstance(glyphs, list) or not isinstance(chars, list):
            raise AssertionError("NLE reset lacks glyphs/chars needed to audit specials")
        values: collections.Counter[int] = collections.Counter()
        bit_counts: collections.Counter[str] = collections.Counter()
        unsupported: list[dict[str, Any]] = []
        predicate_mismatches: list[dict[str, Any]] = []
        for y, row in enumerate(specials):
            for x, value in enumerate(row):
                if value & ~ALL_SPECIAL_BITS:
                    raise AssertionError(f"NLE specials contains an unknown bit at {(x, y)}: {value}")
                values[value] += 1
                glyph = int(glyphs[y][x])
                for bit, predicate_name in PREDICATE_BITS:
                    predicate = getattr(nethack, predicate_name, None)
                    if not callable(predicate):
                        raise AssertionError(f"pinned NLE runtime lacks {predicate_name}")
                    source_flag = bool(value & bit)
                    glyph_class = bool(predicate(glyph))
                    if source_flag != glyph_class:
                        predicate_mismatches.append({"x": x, "y": y, "value": value, "glyph": glyph, "bit": bit, "predicate": predicate_name})
                    if source_flag:
                        bit_counts[predicate_name] += 1
                if value & UNSUPPORTED_SPECIAL_BITS:
                    unsupported.append(
                        {
                            "x": x,
                            "y": y,
                            "value": value,
                            "glyph": glyph,
                            "char": chr(int(chars[y][x])),
                            "unexposed_bits": value & UNSUPPORTED_SPECIAL_BITS,
                        }
                    )
        if predicate_mismatches:
            raise AssertionError(f"mapglyph predicate mismatch in seed {seed}: {predicate_mismatches[0]!r}")
        return {
            "seed": seed,
            "nle_version": getattr(nle, "__version__", "unknown"),
            "value_counts": dict(sorted(values.items())),
            "source_predicate_bit_counts": dict(sorted(bit_counts.items())),
            "unsupported_examples": unsupported[:12],
            "unsupported_cell_count": len(unsupported),
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.cases < 2:
        raise SystemExit("specials source audit requires at least two distinct seeds")
    cases = [observe_seed(args.seed + offset, character=args.character) for offset in range(args.cases)]
    values: collections.Counter[int] = collections.Counter()
    unsupported = 0
    for case in cases:
        values.update({int(key): int(count) for key, count in case["value_counts"].items()})
        unsupported += int(case["unsupported_cell_count"])
    if not any(value & MG_PET for value in values):
        raise SystemExit("specials source audit saw no MG_PET observations; cannot validate the supported subset")
    # A real object-pile observation is the negative control: mapglyph.c sets
    # this from ``level.objects[x][y]->nexthere``, which no NLE observation
    # plane exposes.  A display glyph must therefore never be used to invent it.
    if not any(value & MG_OBJPILE for value in values):
        raise SystemExit("specials source audit saw no MG_OBJPILE negative control; increase --cases")
    report = {
        "schema": "gamebench.nethack.nle_specials_source_audit.v1",
        "status": "pass",
        "nle_source": {"version": "0.9.0", "commit": SOURCE_COMMIT, "netHack_version": "3.6.6"},
        "public_contract": {"shape": [21, 79], "dtype": "uint8", "all_source_bits": ALL_SPECIAL_BITS},
        "gold_contract": {
            "supported_bits": {str(MG_PET): "MG_PET only when an owned, visible materialized monster has pet=true"},
            "unjudgeable_bits": UNSUPPORTED_SPECIAL_BITS,
            "negative_control": "MG_OBJPILE depends on private level.objects[x][y]->nexthere; it is public in specials but not derivable from chars/glyphs/colors or a presentation overlay.",
        },
        "cases": cases,
        "aggregate_value_counts": dict(sorted(values.items())),
        "unsupported_source_cell_count": unsupported,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "cases": len(cases), "value_counts": dict(sorted(values.items())), "unsupported_source_cells": unsupported, "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
