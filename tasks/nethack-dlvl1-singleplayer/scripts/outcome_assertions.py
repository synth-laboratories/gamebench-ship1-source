"""Exact seeded transition outcomes for stochastic NetHack commands.

The live oracle owns outcomes; this module only describes observable deltas.
It never attempts to infer or clone NLE's private RNG state.
"""

from __future__ import annotations

from typing import Any


STOCHASTIC_DIRECTION_COMMANDS = frozenset(
    {
        "Command.FIGHT",
        "Command.FORCE",
        "Command.KICK",
    }
)


def _plane_changes(before: list[Any], after: list[Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for y, (before_row, after_row) in enumerate(zip(before, after, strict=False)):
        if isinstance(before_row, str) and isinstance(after_row, str):
            cells = zip(before_row, after_row, strict=False)
        elif isinstance(before_row, list) and isinstance(after_row, list):
            cells = zip(before_row, after_row, strict=False)
        else:
            if before_row != after_row:
                changes.append({"y": y, "x": None, "before": before_row, "after": after_row})
            continue
        for x, (left, right) in enumerate(cells):
            if left != right:
                changes.append({"y": y, "x": x, "before": left, "after": right})
    return changes


def _numeric_deltas(before: list[Any], after: list[Any]) -> list[dict[str, int]]:
    return [
        {"slot": slot, "before": int(left), "after": int(right), "delta": int(right) - int(left)}
        for slot, (left, right) in enumerate(zip(before, after, strict=False))
        if left != right
    ]


def transition_outcome(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Return every public effect needed to judge a seeded command outcome."""

    return {
        "message": after.get("message", ""),
        "message_raw": after.get("message_raw", []),
        "blstats_deltas": _numeric_deltas(
            list(before.get("blstats", [])),
            list(after.get("blstats", [])),
        ),
        "char_deltas": _plane_changes(
            list(before.get("chars", [])),
            list(after.get("chars", [])),
        ),
        "color_deltas": _plane_changes(
            list(before.get("colors", [])),
            list(after.get("colors", [])),
        ),
        "glyph_deltas": _plane_changes(
            list(before.get("glyphs", [])),
            list(after.get("glyphs", [])),
        ),
        "done": bool(after.get("done", False)),
        "terminal_reason": str(after.get("terminal_reason", "")),
    }


def stochastic_contexts(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Locate direction responses belonging to seeded stochastic commands."""

    pending: str | None = None
    contexts: list[dict[str, Any]] = []
    for record in actions:
        mode = str(record.get("input_mode", "unknown"))
        action_name = str(record.get("action_name", ""))
        if mode == "normal":
            pending = action_name if action_name in STOCHASTIC_DIRECTION_COMMANDS else None
            continue
        if mode == "direction" and pending is not None:
            contexts.append(
                {
                    "step": int(record["step"]),
                    "command": pending,
                    "response": action_name,
                }
            )
        pending = None
    return contexts


def _first_difference(expected: Any, actual: Any, path: str = "$.seeded_outcome") -> dict[str, Any] | None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            if key not in actual:
                return {"path": f"{path}.{key}", "expected": value, "actual": "<missing>"}
            difference = _first_difference(value, actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return {"path": path, "expected": f"length {len(expected)}", "actual": f"length {len(actual)}"}
        for index, value in enumerate(expected):
            difference = _first_difference(value, actual[index], f"{path}[{index}]")
            if difference:
                return difference
        return None
    if expected != actual:
        return {"path": path, "expected": expected, "actual": actual}
    return None


def seeded_outcome_report(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    through_step: int,
) -> dict[str, Any]:
    """Compare exact public outcome signatures through the trustworthy prefix."""

    comparisons: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for context in stochastic_contexts(actions):
        step = int(context["step"])
        if step > through_step or step <= 0 or step >= len(expected) or step >= len(actual):
            continue
        oracle = transition_outcome(expected[step - 1], expected[step])
        gold = transition_outcome(actual[step - 1], actual[step])
        comparison = {**context, "oracle": oracle, "gold": gold, "equal": oracle == gold}
        comparisons.append(comparison)
        if oracle != gold:
            difference = _first_difference(oracle, gold)
            errors.append({**context, **(difference or {"path": "$.seeded_outcome", "expected": oracle, "actual": gold})})
    return {
        "comparisons": len(comparisons),
        "error_count": len(errors),
        "errors": errors,
        "status": "not_exercised" if not comparisons else ("pass" if not errors else "errors_found"),
        "rng_claim": "observable seeded outcome only; private NLE RNG state is not inferred",
    }
