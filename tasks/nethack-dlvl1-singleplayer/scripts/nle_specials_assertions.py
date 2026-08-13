"""Fail-closed scoring for the NLE v0.9.0 ``specials`` public plane.

Only a complete zero cell, or a visible materialized ``MG_PET`` cell that
both oracle and gold emit, is currently judgeable.  Source bits requiring
unexposed NetHack state make that cell unjudgeable; they do not become a
gold error or an accidental pass.
"""

from __future__ import annotations

from typing import Any

from shared.nle_specials import MG_PET, UNSUPPORTED_SPECIAL_BITS


def _rows(value: Any) -> list[list[int]] | None:
    if not isinstance(value, list):
        return None
    result: list[list[int]] = []
    for row in value:
        if not isinstance(row, list) or any(type(cell) is not int or not 0 <= cell <= 255 for cell in row):
            return None
        result.append([int(cell) for cell in row])
    return result


def specials_step_report(expected: Any, actual: Any, *, step: int) -> dict[str, Any]:
    """Compare one plane without claiming unexposed mapglyph state.

    Any gold output outside ``{0, MG_PET}`` is a contract violation: the gold
    implementation has no causal source for it.  A source ``MG_PET`` which
    gold cannot materialize is *unjudgeable*, not a false discrepancy.
    """

    source, gold = _rows(expected), _rows(actual)
    if source is None or gold is None or len(source) != len(gold) or any(len(left) != len(right) for left, right in zip(source or [], gold or [], strict=True)):
        return {
            "step": step,
            "comparisons": 0,
            "zero_comparisons": 0,
            "pet_comparisons": 0,
            "unjudgeable": 0,
            "unsupported_source_cells": 0,
            "unmaterialized_pet_cells": 0,
            "errors": [{"step": step, "path": "$.specials", "expected": "valid rectangular uint8 plane", "actual": actual}],
            "reason_counts": {"malformed_plane": 1},
        }
    comparisons = 0
    zero_comparisons = 0
    pet_comparisons = 0
    unjudgeable = 0
    unsupported_source_cells = 0
    unmaterialized_pet_cells = 0
    errors: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for y, (source_row, gold_row) in enumerate(zip(source, gold, strict=True)):
        for x, (source_value, gold_value) in enumerate(zip(source_row, gold_row, strict=True)):
            path = f"$.specials[{y}][{x}]"
            if gold_value & UNSUPPORTED_SPECIAL_BITS:
                errors.append({"step": step, "path": path, "expected": source_value, "actual": gold_value, "reason": "gold_emitted_unsupported_special_bit"})
                continue
            if source_value & UNSUPPORTED_SPECIAL_BITS:
                unjudgeable += 1
                unsupported_source_cells += 1
                reasons["source_requires_unexposed_mapglyph_state"] = reasons.get("source_requires_unexposed_mapglyph_state", 0) + 1
                continue
            if source_value == 0:
                comparisons += 1
                zero_comparisons += 1
                if gold_value != 0:
                    errors.append({"step": step, "path": path, "expected": 0, "actual": gold_value, "reason": "gold_fabricated_pet_marker"})
                continue
            if source_value == MG_PET:
                if gold_value == MG_PET:
                    comparisons += 1
                    pet_comparisons += 1
                elif gold_value == 0:
                    unjudgeable += 1
                    unmaterialized_pet_cells += 1
                    reasons["source_pet_has_no_materialized_gold_entity"] = reasons.get("source_pet_has_no_materialized_gold_entity", 0) + 1
                else:  # guarded above, retained as a future-proof hard failure
                    errors.append({"step": step, "path": path, "expected": source_value, "actual": gold_value, "reason": "unsupported_gold_special_encoding"})
                continue
            # Every v0.9.0 bit is represented by the masks above.  Keep this
            # branch fail-closed if a later runtime changes that assumption.
            unjudgeable += 1
            reasons["unknown_source_special_encoding"] = reasons.get("unknown_source_special_encoding", 0) + 1
    return {
        "step": step,
        "comparisons": comparisons,
        "zero_comparisons": zero_comparisons,
        "pet_comparisons": pet_comparisons,
        "unjudgeable": unjudgeable,
        "unsupported_source_cells": unsupported_source_cells,
        "unmaterialized_pet_cells": unmaterialized_pet_cells,
        "errors": errors,
        "reason_counts": dict(sorted(reasons.items())),
    }


def specials_trace_report(expected: list[dict[str, Any]], actual: list[dict[str, Any]], *, through_step: int) -> dict[str, Any]:
    """Aggregate strict special-plane evidence through an eligible trace."""

    transitions: list[dict[str, Any]] = []
    for step in range(min(through_step, len(expected) - 1, len(actual) - 1) + 1):
        # Older pure-engine tests deliberately have no public specials plane.
        # Absence on both sides is not a malformed NLE plane and must not be
        # scored as an oracle error.
        if expected[step].get("specials") is None and actual[step].get("specials") is None:
            continue
        transitions.append(specials_step_report(expected[step].get("specials"), actual[step].get("specials"), step=step))
    comparisons = sum(int(entry["comparisons"]) for entry in transitions)
    zero_comparisons = sum(int(entry["zero_comparisons"]) for entry in transitions)
    pet_comparisons = sum(int(entry["pet_comparisons"]) for entry in transitions)
    unjudgeable = sum(int(entry["unjudgeable"]) for entry in transitions)
    unsupported_source_cells = sum(int(entry["unsupported_source_cells"]) for entry in transitions)
    unmaterialized_pet_cells = sum(int(entry["unmaterialized_pet_cells"]) for entry in transitions)
    errors = [error for entry in transitions for error in entry["errors"]]
    if errors:
        status = "errors_found"
    elif unjudgeable:
        status = "partially_unjudgeable"
    elif comparisons:
        status = "pass"
    else:
        status = "not_exercised"
    return {
        "comparisons": comparisons,
        "zero_comparisons": zero_comparisons,
        "pet_comparisons": pet_comparisons,
        "unjudgeable_cells": unjudgeable,
        "unsupported_source_cells": unsupported_source_cells,
        "unmaterialized_pet_cells": unmaterialized_pet_cells,
        "error_count": len(errors),
        "errors": errors,
        "transitions": transitions,
        "gold_contract": "MG_PET only when a visible materialized gold pet exists; other mapglyph flags fail closed as unjudgeable",
        "status": status,
    }
