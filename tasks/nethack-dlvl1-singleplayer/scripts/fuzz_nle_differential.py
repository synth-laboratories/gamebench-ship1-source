#!/usr/bin/env python3
"""Live NLE differential fuzzer for the own dlvl-1 gold engines.

This is deliberately an oracle-development tool.  It imports NLE only while
the command is running, starts both own lanes from an NLE-derived level dump,
and writes candidate captures only to a caller-selected output directory.
Results are diagnostics, never evidence for the 33-tape conformance corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.capture_nle_fixture import (
    OBSERVATION_KEYS,
    STATIC_TERRAIN_CHARS,
    action_table,
    canonical_json,
    deterministic_nle_seeds,
    dungeon_identity,
    hero_position,
    level_dump,
    normalise_reset,
    terminal_reason_for_capture,
    project,
    read_actions,
    visible_down_stairs,
)
from scripts.compare_nle_discrepancies import expected_public
from scripts.judge_nle_tapes import layers as judge_layers
from scripts.outcome_assertions import seeded_outcome_report
from scripts.nle_specials_assertions import specials_trace_report
from scripts.nle_native_map_fov import PinnedNleMapFovReader
from scripts.native_pre_action_evidence import NativePreActionExporters, SIDECAR_FILE, capture_record as capture_native_pre_action_record, manifest_provenance, validate_records as validate_native_pre_action_records
from scripts.native_reset_entity_state import (
    SIDECAR_FILE as RESET_ENTITY_SIDECAR_FILE,
    capture_reset_state,
    portable_reset_projection,
    portable_reset_rng_projection_from_capture,
    record_from_reset_capture,
    validate_reset_entity_state,
)
from scripts.oracle_tape import capture_runtime_identity
from scripts.rust_scenario import run_scenario
from shared.task_resolve import resolve_task


PASSABLE = {ord("."), ord("#"), ord("<"), ord(">"), ord("_"), ord("{"), ord("}"), ord("~")}
DIRECTIONS = (
    ("CompassDirection.N", 0, -1),
    ("CompassDirection.E", 1, 0),
    ("CompassDirection.S", 0, 1),
    ("CompassDirection.W", -1, 0),
    ("CompassDirection.NE", 1, -1),
    ("CompassDirection.SE", 1, 1),
    ("CompassDirection.SW", -1, 1),
    ("CompassDirection.NW", -1, -1),
)
PROMPT_PROBE_ACTIONS = (
    "Command.SEARCH",
    "Command.OPEN",
    "Command.CLOSE",
    "Command.KICK",
    "Command.INVENTORY",
    "Command.APPLY",
    "Command.EAT",
)
STATIC_SCREEN_CHARS = frozenset(".#|-+<>_{}~ @")

# NetHack 3.6.6 ``back_to_glyph`` terrain families.  This is deliberately a
# movement/FOV substrate, not a claim that the current terminal presentation
# of an unseen cell is known.  Direct reset cmap pixels below override these
# coarse values exactly; entity/hero overlays keep their existing capture
# annotations.  The native source type remains recorded alongside this
# projection so any unsupported type can be audited rather than hidden.
NATIVE_TERRAIN_CHARS = {
    0: " ", 1: "|", 2: "-", 3: "-", 4: "-", 5: "-", 6: "-", 7: "-", 8: "-", 9: "-", 10: "|", 11: "|", 12: "#", 13: "#", 14: " ", 15: " ",
    16: "}", 17: "}", 18: "}", 19: "#", 20: "}", 21: "#", 22: "+", 23: "#", 24: ".", 25: ".", 26: ".", 27: "{", 28: "\\", 29: "#", 30: "|", 31: "_", 32: ".", 33: ".", 34: " ", 35: "#",
}
NATIVE_BOOTSTRAP_REQUIRED_FIELDS = frozenset(("full_map_terrain", "fov_visibility_mask", "map_memory"))
NLE_GLYPH_CMAP_OFF = 2359
D_NODOOR = 0
D_ISOPEN = 2
D_CLOSED = 4
D_LOCKED = 8
D_TRAPPED = 16
NATIVE_CMAP_BY_TERRAIN = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9,
    10: 10, 11: 11, 12: 7, 13: 18, 14: 12, 15: 21, 16: 32, 17: 32,
    18: 41, 19: 35, 20: 34, 21: 17, 23: 21, 24: 19, 25: 19, 26: 25,
    27: 31, 28: 29, 29: 30, 30: 28, 31: 27, 32: 33, 33: 35, 34: 39,
    35: 40,
}


def native_surface_for_terrain(terrain_type: int, flags: int = 0, horizontal: bool = False) -> tuple[str, int]:
    """Project reset-only native terrain into its visible cmap surface.

    ``rm.typ == DOOR`` is not enough to render a door: ``D_NODOOR`` is an
    open doorway whose cmap is ``S_ndoor`` (a floor dot), while the doormask
    and horizontal bit choose the open/closed door glyph.  This helper is
    deliberately scoped to the diagnostic native-reset bootstrap; it does not
    turn a future observation into gold runtime state.
    """

    if terrain_type != 22:  # DOOR in the pinned NetHack 3.6.6 rm.h enum
        cmap = NATIVE_CMAP_BY_TERRAIN.get(terrain_type, 0)
        return NATIVE_TERRAIN_CHARS.get(terrain_type, " "), NLE_GLYPH_CMAP_OFF + cmap
    if flags & (D_CLOSED | D_LOCKED | D_TRAPPED):
        return "+", NLE_GLYPH_CMAP_OFF + (15 if horizontal else 16)
    if flags & D_ISOPEN:
        return ("-" if horizontal else "|"), NLE_GLYPH_CMAP_OFF + (13 if horizontal else 14)
    if flags == D_NODOOR:
        return ".", NLE_GLYPH_CMAP_OFF + 12
    return ".", NLE_GLYPH_CMAP_OFF + 12


def _char_rows(projection: dict[str, Any]) -> list[str]:
    """Return a rectangular-enough character plane without inventing cells."""

    rows = projection.get("chars", [])
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        if isinstance(row, str):
            result.append(row)
        elif isinstance(row, list):
            result.append("".join(chr(int(cell)) for cell in row if isinstance(cell, int)))
    return result


def _plane_value(projection: dict[str, Any], key: str, x: int, y: int, default: int) -> int:
    plane = projection.get(key, [])
    if isinstance(plane, list) and y < len(plane) and isinstance(plane[y], list) and x < len(plane[y]):
        value = plane[y][x]
        if isinstance(value, int):
            return int(value)
    return default


def _cell(x: int, y: int, char: str, projection: dict[str, Any], *, provenance: str) -> dict[str, Any]:
    return {
        "x": x,
        "y": y,
        "char": char,
        "glyph": _plane_value(projection, "glyphs", x, y, ord(char)),
        "color": _plane_value(projection, "colors", x, y, 0),
        "provenance": provenance,
    }


def _reset_underlay_provenance(reset_level: dict[str, Any] | None, x: int, y: int) -> str:
    """Name reset-only terrain evidence without using it to guess a later cell."""

    if not isinstance(reset_level, dict):
        return "unknown"
    terrain = reset_level.get("terrain", [])
    seen = reset_level.get("seen", [])
    if not (
        isinstance(terrain, list)
        and y < len(terrain)
        and isinstance(terrain[y], str)
        and x < len(terrain[y])
        and terrain[y][x] in STATIC_TERRAIN_CHARS
    ):
        return "unknown"
    if isinstance(seen, list) and y < len(seen) and isinstance(seen[y], list) and x < len(seen[y]) and bool(seen[y][x]):
        return "reset_observed_static"
    return "reset_terrain_annotation"


def visible_cell_layers(projection: dict[str, Any], *, reset_level: dict[str, Any] | None = None) -> dict[str, Any]:
    """Split a rendered plane into directly observed static terrain and overlays.

    NLE's public observation has no stable monster/object identifier.  A
    non-terrain glyph is therefore an ``entity_overlay`` with presentation
    metadata, *not* an asserted monster or object identity.  This distinction
    keeps live diagnostics from turning a coincidentally repeated ``d`` glyph
    into an invented pet trajectory.
    """

    static: dict[tuple[int, int], dict[str, Any]] = {}
    overlays: dict[tuple[int, int], dict[str, Any]] = {}
    unknown: list[dict[str, Any]] = []
    for y, row in enumerate(_char_rows(projection)):
        for x, char in enumerate(row):
            if char in STATIC_TERRAIN_CHARS:
                static[(x, y)] = _cell(x, y, char, projection, provenance="observed_surface_static")
            elif char == "@":
                # The hero conceals its underlay.  It is neither evidence of a
                # static cell nor an independently identified entity overlay.
                unknown.append(
                    {
                        "x": x,
                        "y": y,
                        "reason": "hero_underlay_not_visible",
                        "underlay_provenance": _reset_underlay_provenance(reset_level, x, y),
                    }
                )
            elif char == " ":
                continue
            else:
                overlay = _cell(x, y, char, projection, provenance="observed_surface_overlay")
                overlay["identity_status"] = "unavailable_from_nle_presentation"
                overlay["underlay_provenance"] = _reset_underlay_provenance(reset_level, x, y)
                overlays[(x, y)] = overlay
    return {"static": static, "overlays": overlays, "unknown": unknown}


def _sorted_cells(cells: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(cells, key=lambda cell: (int(cell["y"]), int(cell["x"]), str(cell.get("char", "")), int(cell.get("glyph", 0))))


def _cell_key(cell: dict[str, Any]) -> tuple[int, int, str, int, int]:
    return (int(cell["x"]), int(cell["y"]), str(cell["char"]), int(cell["glyph"]), int(cell["color"]))


def _presentation_key(cell: dict[str, Any]) -> tuple[str, int, int]:
    return (str(cell["char"]), int(cell["glyph"]), int(cell["color"]))


def _static_transition(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    before_static = dict(before["static"])
    after_static = dict(after["static"])
    before_overlays = dict(before["overlays"])
    newly_revealed = [cell for coordinate, cell in after_static.items() if coordinate not in before_static and coordinate not in before_overlays]
    retained = [cell for coordinate, cell in after_static.items() if coordinate in before_static and _cell_key(cell) == _cell_key(before_static[coordinate])]
    # An overlay still proves the square is visible; only a blank/unseen cell is
    # a visibility-forgetting event.
    forgotten = [cell for coordinate, cell in before_static.items() if coordinate not in after_static and coordinate not in after["overlays"]]
    return {
        "newly_revealed": _sorted_cells(newly_revealed),
        "retained": _sorted_cells(retained),
        "forgotten": _sorted_cells(forgotten),
    }


def _reset_unknown_surface_coordinates(reset_level: dict[str, Any] | None) -> dict[tuple[int, int], str]:
    """Return reset pixels whose underlay cannot be inferred causally.

    The reset screen can render ``@`` or an entity/object overlay over these
    squares. A later source frame may expose terrain after movement, but that
    evidence cannot be fed back into the simulated reset. Presentation
    overlays expire on the first consumed gold turn specifically to avoid an
    invented schedule; their newly exposed underlays remain unjudgeable.
    """

    coordinates: dict[tuple[int, int], str] = {}
    if not isinstance(reset_level, dict):
        return coordinates
    hero = reset_level.get("hero")
    terrain = reset_level.get("terrain")
    if isinstance(hero, dict) and isinstance(terrain, list):
        x, y = hero.get("x"), hero.get("y")
        if type(x) is int and type(y) is int and 0 <= y < len(terrain):
            row = terrain[y]
            if isinstance(row, str) and 0 <= x < len(row) and row[x] not in STATIC_TERRAIN_CHARS:
                coordinates[(x, y)] = "reset_hero_underlay_unknown"
    overlays = reset_level.get("presentation_overlays", [])
    if isinstance(overlays, list):
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            x, y = overlay.get("x"), overlay.get("y")
            if type(x) is int and type(y) is int:
                coordinates[(x, y)] = "reset_presentation_overlay_underlay_unknown"
    return coordinates


def _mask_unknown_surface_cells(
    snapshot: dict[str, Any],
    coordinates: set[tuple[int, int]],
) -> dict[str, Any]:
    """Remove only causally unavailable reset underlays from core equality.

    Sparse specials and entity motion have dedicated assertion lanes. This
    mask is limited to exact reset pixels known to conceal unknown terrain;
    it never masks messages, mechanics, lifecycle, or any other coordinate.
    """

    masked = deepcopy(snapshot)
    for plane, neutral in (("chars", "\0"), ("glyphs", 0), ("colors", 0)):
        rows = masked.get(plane)
        if not isinstance(rows, list):
            continue
        for x, y in coordinates:
            if not (0 <= y < len(rows)):
                continue
            row = rows[y]
            if isinstance(row, str):
                if 0 <= x < len(row):
                    rows[y] = row[:x] + str(neutral) + row[x + 1 :]
            elif isinstance(row, list) and 0 <= x < len(row):
                row[x] = neutral
    return masked


def _without_coordinates(cells: list[dict[str, Any]], coordinates: set[tuple[int, int]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate source-unjudgeable surface records before comparison."""

    retained: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for cell in cells:
        target = (int(cell.get("x", -1)), int(cell.get("y", -1)))
        (quarantined if target in coordinates else retained).append(cell)
    return retained, quarantined


def _without_restoration_coordinates(records: list[dict[str, Any]], coordinates: set[tuple[int, int]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    retained: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for record in records:
        vacated = record.get("vacated", {})
        coordinate = (int(vacated.get("x", -1)), int(vacated.get("y", -1))) if isinstance(vacated, dict) else (-1, -1)
        (quarantined if coordinate in coordinates else retained).append(record)
    return retained, quarantined


def _entity_transition(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_entities = dict(before["overlays"])
    after_entities = dict(after["overlays"])
    before_by_presentation: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    after_by_presentation: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    for cell in before_entities.values():
        before_by_presentation.setdefault(_presentation_key(cell), []).append(cell)
    for cell in after_entities.values():
        after_by_presentation.setdefault(_presentation_key(cell), []).append(cell)

    moved: list[dict[str, Any]] = []
    identity_unknown: list[dict[str, Any]] = []
    matched_before: set[tuple[int, int]] = set()
    matched_after: set[tuple[int, int]] = set()
    for key in sorted(set(before_by_presentation) | set(after_by_presentation)):
        prior = _sorted_cells(before_by_presentation.get(key, []))
        current = _sorted_cells(after_by_presentation.get(key, []))
        if len(prior) == len(current) == 1:
            old, new = prior[0], current[0]
            if (old["x"], old["y"]) == (new["x"], new["y"]):
                matched_before.add((int(old["x"]), int(old["y"])))
                matched_after.add((int(new["x"]), int(new["y"])))
            else:
                # This is a presentation-continuity observation, not an entity
                # identity assertion.  NLE does not expose a stable id here.
                moved.append({"from": old, "to": new, "identity_status": "presentation_continuity_only"})
                matched_before.add((int(old["x"]), int(old["y"])))
                matched_after.add((int(new["x"]), int(new["y"])))
        elif prior or current:
            identity_unknown.append(
                {
                    "presentation": {"char": key[0], "glyph": key[1], "color": key[2]},
                    "before": prior,
                    "after": current,
                    "reason": "ambiguous_or_missing_stable_entity_identity",
                }
            )
    appeared = [cell for coordinate, cell in after_entities.items() if coordinate not in matched_after]
    disappeared = [cell for coordinate, cell in before_entities.items() if coordinate not in matched_before]
    restoration = [
        {"vacated": cell, "restored_static": after["static"][coordinate]}
        for coordinate, cell in before_entities.items()
        if coordinate not in after_entities and coordinate in after["static"]
    ]
    return {
        "appeared": _sorted_cells(appeared),
        "disappeared": _sorted_cells(disappeared),
        "moved": sorted(moved, key=lambda event: (event["from"]["y"], event["from"]["x"], event["to"]["y"], event["to"]["x"])),
        "vacated_cell_restoration": sorted(restoration, key=lambda event: (event["vacated"]["y"], event["vacated"]["x"])),
        "identity_unavailable": identity_unknown,
    }


def _records_difference(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return exact expected-only and actual-only records, preserving coordinates."""

    expected_by_json = {canonical_json(record): record for record in expected}
    actual_by_json = {canonical_json(record): record for record in actual}
    return (
        [expected_by_json[key] for key in sorted(expected_by_json.keys() - actual_by_json.keys())],
        [actual_by_json[key] for key in sorted(actual_by_json.keys() - expected_by_json.keys())],
    )


def layered_transition_report(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    *,
    reset_level: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report per-transition visibility and overlay deltas without identity guesses."""

    transitions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    source_limits: list[dict[str, Any]] = []
    causal_unknown_coordinates = _reset_unknown_surface_coordinates(reset_level)
    comparisons = max(0, min(len(expected), len(actual)) - 1)
    for step in range(1, comparisons + 1):
        expected_before = visible_cell_layers(expected[step - 1], reset_level=reset_level)
        expected_after = visible_cell_layers(expected[step], reset_level=reset_level)
        actual_before = visible_cell_layers(actual[step - 1], reset_level=reset_level)
        actual_after = visible_cell_layers(actual[step], reset_level=reset_level)
        expected_static = _static_transition(expected_before, expected_after)
        actual_static = _static_transition(actual_before, actual_after)
        expected_entities = _entity_transition(expected_before, expected_after)
        actual_entities = _entity_transition(actual_before, actual_after)
        transition_errors: list[dict[str, Any]] = []
        for name in ("newly_revealed", "retained", "forgotten"):
            expected_cells, quarantined = _without_coordinates(expected_static[name], set(causal_unknown_coordinates))
            actual_cells, _ = _without_coordinates(actual_static[name], set(causal_unknown_coordinates))
            for cell in quarantined:
                source_limits.append(
                    {
                        "step": step,
                        "path": f"$.visibility_entity.static.{name}",
                        "coordinate": {"x": cell["x"], "y": cell["y"]},
                        "source_state": causal_unknown_coordinates[(int(cell["x"]), int(cell["y"]))],
                        "expected_later_surface": cell,
                    }
                )
            missed, false_positive = _records_difference(expected_cells, actual_cells)
            transition_errors.extend(
                {"path": f"$.visibility_entity.static.{name}.missed", "expected": record, "actual": "<missing>"} for record in missed
            )
            transition_errors.extend(
                {"path": f"$.visibility_entity.static.{name}.false_positive", "expected": "<absent>", "actual": record} for record in false_positive
            )
        # Current surfaces catch static false positives/misses even when the
        # first divergent snapshot predates this transition.
        expected_current, quarantined_current = _without_coordinates(_sorted_cells(expected_after["static"].values()), set(causal_unknown_coordinates))
        actual_current, _ = _without_coordinates(_sorted_cells(actual_after["static"].values()), set(causal_unknown_coordinates))
        for cell in quarantined_current:
            source_limits.append(
                {
                    "step": step,
                    "path": "$.visibility_entity.static.current",
                    "coordinate": {"x": cell["x"], "y": cell["y"]},
                    "source_state": causal_unknown_coordinates[(int(cell["x"]), int(cell["y"]))],
                    "expected_later_surface": cell,
                }
            )
        missed_static, false_static = _records_difference(expected_current, actual_current)
        transition_errors.extend(
            {"path": "$.visibility_entity.static.current.missed", "expected": record, "actual": "<missing>"} for record in missed_static
        )
        transition_errors.extend(
            {"path": "$.visibility_entity.static.current.false_positive", "expected": "<absent>", "actual": record} for record in false_static
        )
        for name in ("appeared", "disappeared", "moved", "vacated_cell_restoration"):
            if name == "vacated_cell_restoration":
                expected_records, quarantined = _without_restoration_coordinates(expected_entities[name], set(causal_unknown_coordinates))
                actual_records, _ = _without_restoration_coordinates(actual_entities[name], set(causal_unknown_coordinates))
                for record in quarantined:
                    vacated = record["vacated"]
                    source_limits.append(
                        {
                            "step": step,
                            "path": "$.visibility_entity.entities.vacated_cell_restoration",
                            "coordinate": {"x": vacated["x"], "y": vacated["y"]},
                            "source_state": causal_unknown_coordinates[(int(vacated["x"]), int(vacated["y"]))],
                            "expected_later_surface": record["restored_static"],
                        }
                    )
            else:
                expected_records, actual_records = expected_entities[name], actual_entities[name]
            missed, false_positive = _records_difference(expected_records, actual_records)
            transition_errors.extend(
                {"path": f"$.visibility_entity.entities.{name}.missed", "expected": record, "actual": "<missing>"} for record in missed
            )
            transition_errors.extend(
                {"path": f"$.visibility_entity.entities.{name}.false_positive", "expected": "<absent>", "actual": record} for record in false_positive
            )
        for error in transition_errors:
            error["step"] = step
        errors.extend(transition_errors)
        transitions.append(
            {
                "step": step,
                "static": {**expected_static, "false_positive_current": false_static, "missed_current": missed_static},
                "entities": expected_entities,
                "actual_static": actual_static,
                "actual_entities": actual_entities,
                "identity_limits": {
                    "expected_unknown": expected_entities["identity_unavailable"],
                    "actual_unknown": actual_entities["identity_unavailable"],
                    "note": "NLE presentation planes do not provide stable entity ids; ambiguous overlays are reported, not matched.",
                },
                "error_count": len(transition_errors),
                "first_error": transition_errors[0] if transition_errors else None,
            }
        )
    failed_steps = {int(error["step"]) for error in errors}
    status = "not_exercised" if comparisons == 0 else ("pass" if not errors and not source_limits else ("partial_unjudgeable" if not errors else "errors_found"))
    return {
        "comparisons": comparisons,
        "error_count": len(errors),
        "errors": errors,
        "failed_transition_count": len(failed_steps),
        "score": round(100.0 * (comparisons - len(failed_steps)) / comparisons, 1) if comparisons else None,
        "status": status,
        "transitions": transitions,
        "first_error": errors[0] if errors else None,
        "source_state_limits": source_limits,
        "unjudgeable_surface_record_count": len(source_limits),
        "causal_unknown_coordinates": [
            {"x": x, "y": y, "source_state": source_state}
            for (x, y), source_state in sorted(causal_unknown_coordinates.items())
        ],
        "identity_contract": "static terrain is direct surface evidence; entity identity is unavailable unless a future oracle exposes stable ids",
    }
SOURCE_PROVENANCE = frozenset(("reset-observed", "prior-turn-observed", "capture-annotation", "unknown"))
# These commands have a result which depends on the cell currently hidden by
# the hero.  A raw NLE screen deliberately does not disclose that underlay.
# Keep this deliberately small: an unsupported command is a fidelity gap, not
# evidence that every command has unknowable source state.
HERO_CELL_REQUIREMENTS = {
    "Command.PICKUP": ("hero_terrain_underlay", "hero_floor_object_set"),
    "MiscDirection.DOWN": ("hero_terrain_underlay",),
}


def compact(value: Any, *, limit: int = 240) -> Any:
    """Keep report values inspectable without embedding a 21×79 plane twice."""

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def difference_paths(expected: Any, actual: Any, *, path: str = "$") -> Iterable[str]:
    """Yield every mismatched expected leaf, with `chars` compared cellwise."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            yield path
            return
        for key, value in expected.items():
            if key not in actual:
                yield f"{path}.{key}"
            else:
                yield from difference_paths(value, actual[key], path=f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            yield path
            return
        for index, value in enumerate(expected):
            yield from difference_paths(value, actual[index], path=f"{path}[{index}]")
        return
    cellwise_string = path.startswith("$.chars[") or path.startswith("$.terminal_ui.char_rows[")
    if cellwise_string and isinstance(expected, str) and isinstance(actual, str):
        if len(expected) != len(actual):
            yield path
            return
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left != right:
                yield f"{path}[{index}]"
        return
    if expected != actual:
        yield path


def mismatch_records(expected: Any, actual: Any, *, path: str = "$") -> Iterable[dict[str, Any]]:
    """Yield every expected-subset leaf mismatch with compact values."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            yield {"path": path, "expected": compact(expected), "actual": compact(actual)}
            return
        for key, value in expected.items():
            child = f"{path}.{key}"
            if key not in actual:
                yield {"path": child, "expected": compact(value), "actual": "<missing>"}
            else:
                yield from mismatch_records(value, actual[key], path=child)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            yield {"path": path, "expected": compact(expected), "actual": compact(actual)}
            return
        for index, value in enumerate(expected):
            yield from mismatch_records(value, actual[index], path=f"{path}[{index}]")
        return
    cellwise_string = path.startswith("$.chars[") or path.startswith("$.terminal_ui.char_rows[")
    if cellwise_string and isinstance(expected, str) and isinstance(actual, str):
        if len(expected) != len(actual):
            yield {"path": path, "expected": compact(expected), "actual": compact(actual)}
            return
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left != right:
                yield {"path": f"{path}[{index}]", "expected": left, "actual": right}
        return
    if expected != actual:
        yield {"path": path, "expected": compact(expected), "actual": compact(actual)}


def mismatch_class(path: str) -> str:
    if path.startswith(("$.chars", "$.colors", "$.glyphs", "$.tty_", "$.terminal_ui")):
        return "pixel"
    if path.startswith("$.specials"):
        return "special"
    if path.startswith("$.input_mode"):
        return "mode"
    if path.startswith("$.turn_effect"):
        return "turn"
    if path.startswith(("$.done", "$.terminal_reason", "$.terminated", "$.truncated")):
        return "terminal"
    return "state"


def first_difference(expected: Any, actual: Any, *, ignored: set[str] | None = None, path: str = "$") -> dict[str, Any] | None:
    """Return one structured expected-subset difference, honoring a baseline mask."""

    if ignored and path in ignored:
        return None
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return {"path": path, "expected": compact(expected), "actual": compact(actual)}
        for key, value in expected.items():
            child = f"{path}.{key}"
            if key not in actual:
                if not ignored or child not in ignored:
                    return {"path": child, "expected": compact(value), "actual": "<missing>"}
                continue
            difference = first_difference(value, actual[key], ignored=ignored, path=child)
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return {"path": path, "expected": compact(expected), "actual": compact(actual)}
        for index, value in enumerate(expected):
            difference = first_difference(value, actual[index], ignored=ignored, path=f"{path}[{index}]")
            if difference:
                return difference
        return None
    if path.startswith("$.chars[") and isinstance(expected, str) and isinstance(actual, str):
        if len(expected) != len(actual):
            return {"path": path, "expected": compact(expected), "actual": compact(actual)}
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            child = f"{path}[{index}]"
            if left != right and (not ignored or child not in ignored):
                return {"path": child, "expected": left, "actual": right}
        return None
    if expected != actual:
        return {"path": path, "expected": compact(expected), "actual": compact(actual)}
    return None


def first_transition_difference(expected_base: Any, actual_base: Any, expected: Any, actual: Any, *, path: str = "$") -> dict[str, Any] | None:
    """Compare a step while masking only subtrees still unchanged from both resets."""

    if expected_base != actual_base and expected == expected_base and actual == actual_base:
        return None
    if isinstance(expected_base, dict) and isinstance(actual_base, dict) and isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            child = f"{path}.{key}"
            if key not in actual or key not in expected_base or key not in actual_base:
                return first_difference(value, actual.get(key, "<missing>"), path=child)
            difference = first_transition_difference(expected_base[key], actual_base[key], value, actual[key], path=child)
            if difference:
                return difference
        return None
    if isinstance(expected_base, list) and isinstance(actual_base, list) and isinstance(expected, list) and isinstance(actual, list):
        if len(expected_base) != len(actual_base) or len(expected) != len(actual):
            return first_difference(expected, actual, path=path)
        for index, value in enumerate(expected):
            difference = first_transition_difference(expected_base[index], actual_base[index], value, actual[index], path=f"{path}[{index}]")
            if difference:
                return difference
        return None
    if path.startswith("$.chars[") and all(isinstance(value, str) for value in (expected_base, actual_base, expected, actual)):
        if len(expected_base) != len(actual_base) or len(expected) != len(actual):
            return first_difference(expected, actual, path=path)
        for index, (expected_base_cell, actual_base_cell, expected_cell, actual_cell) in enumerate(zip(expected_base, actual_base, expected, actual, strict=True)):
            child = f"{path}[{index}]"
            if expected_base_cell != actual_base_cell and expected_cell == expected_base_cell and actual_cell == actual_base_cell:
                continue
            if expected_cell != actual_cell:
                return {"path": child, "expected": expected_cell, "actual": actual_cell}
        return None
    if expected_base != actual_base and expected == expected_base and actual == actual_base:
        return None
    return first_difference(expected, actual, path=path)


def nle_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    return expected_public(snapshot)


def action_id_by_name(table: list[list[Any]], name: str) -> int:
    for action_id, canonical, _ in table:
        if canonical == name:
            return int(action_id)
    raise ValueError(f"pinned NLE action {name!r} is unavailable")


def tty_text(observation: dict[str, Any]) -> str:
    rows = observation.get("tty_chars", [])
    if not hasattr(rows, "tolist"):
        return ""
    values = rows.tolist()
    if not isinstance(values, list):
        return ""
    return "\n".join("".join(chr(int(cell)) for cell in row if isinstance(cell, int)) for row in values)


def inferred_input_mode(observation: dict[str, Any]) -> str:
    """Classify the raw NLE screen for campaign recovery and coverage metrics."""

    tty = tty_text(observation).lower()
    message = str(project(observation).get("message", "")).lower()
    text = f"{tty}\n{message}"
    if "(end)" in tty:
        return "inventory_display"
    if "--more--" in text:
        return "more"
    if "in what direction" in text or "what direction" in text:
        return "direction"
    if "(y/n" in text or "[yn" in text or "[y/n" in text:
        return "ynq"
    if "what do you want to use" in text or "what do you want to eat" in text or "what do you want to wield" in text:
        return "inventory_letter"
    if "pick an object" in text or "pick a category" in text:
        return "menu"
    if "what do you want to call" in text or "what do you want to name" in text:
        return "string"
    return "normal"


def choose_navigation_action(observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    """Choose a safe movement/MORE action using only the visible NLE plane."""

    if "--More--" in tty_text(observation):
        return action_id_by_name(table, "MiscAction.MORE"), "tty_more", [action_id_by_name(table, "MiscAction.MORE")]

    blstats = observation.get("blstats")
    chars = observation.get("chars")
    if not hasattr(blstats, "tolist") or not hasattr(chars, "tolist"):
        return action_id_by_name(table, "MiscDirection.WAIT"), "missing_visible_plane", [action_id_by_name(table, "MiscDirection.WAIT")]
    stats = blstats.tolist()
    plane = chars.tolist()
    if len(stats) < 2 or not isinstance(plane, list):
        return action_id_by_name(table, "MiscDirection.WAIT"), "missing_hero_position", [action_id_by_name(table, "MiscDirection.WAIT")]
    x, y = int(stats[0]), int(stats[1])
    candidates: list[int] = []
    for name, dx, dy in DIRECTIONS:
        target_x, target_y = x + dx, y + dy
        if not (0 <= target_y < len(plane) and isinstance(plane[target_y], list) and 0 <= target_x < len(plane[target_y])):
            continue
        if int(plane[target_y][target_x]) in PASSABLE:
            candidates.append(action_id_by_name(table, name))
    if not candidates:
        wait = action_id_by_name(table, "MiscDirection.WAIT")
        return wait, "no_visible_navigation_target", [wait]
    return rng.choice(candidates), "visible_navigation", candidates


def choose_prompt_probe_action(observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    """Probe judgeable commands and recover raw NLE prompts.

    PICKUP is intentionally exercised by ``verify_known_underlay_pickup.py``:
    a reset hero hides both terrain and the complete floor stack, so selecting
    it here would make that action and the remaining random trace unjudgeable.
    """

    mode = inferred_input_mode(observation)
    if mode == "more":
        action_id = action_id_by_name(table, "MiscAction.MORE")
        return action_id, "prompt_recovery_more", [action_id]
    if mode == "direction":
        candidates = [action_id_by_name(table, name) for name, _, _ in DIRECTIONS]
        return rng.choice(candidates), "prompt_recovery_direction", candidates
    if mode != "normal":
        action_id = action_id_by_name(table, "Command.ESC")
        return action_id, f"prompt_recovery_{mode}", [action_id]
    candidates = [action_id_by_name(table, name) for name in PROMPT_PROBE_ACTIONS]
    return rng.choice(candidates), "safe_prompt_probe", candidates


def choose_terminal_probe_action(observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    """Exercise an isolated explicit quit boundary without leaving the NLE process."""

    del rng
    mode = inferred_input_mode(observation)
    if mode == "more":
        action_id = action_id_by_name(table, "MiscAction.MORE")
        return action_id, "terminal_recovery_more", [action_id]
    if mode == "ynq":
        # CompassDirection.NW carries the raw `y` key while NLE is in a y/n prompt.
        action_id = action_id_by_name(table, "CompassDirection.NW")
        return action_id, "terminal_confirm_yes", [action_id]
    if mode != "normal":
        action_id = action_id_by_name(table, "Command.ESC")
        return action_id, f"terminal_recovery_{mode}", [action_id]
    action_id = action_id_by_name(table, "Command.QUIT")
    return action_id, "terminal_quit", [action_id]


def choose_campaign_action(campaign: str, observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    if campaign == "navigation-v0":
        return choose_navigation_action(observation, table, rng)
    if campaign == "prompt-probe-v0":
        return choose_prompt_probe_action(observation, table, rng)
    if campaign == "terminal-probe-v0":
        return choose_terminal_probe_action(observation, table, rng)
    raise ValueError(f"unsupported live NLE campaign {campaign!r}")


def glyph_presentation_class(glyph: int) -> str:
    """Classify a raw NLE glyph without claiming an entity identity.

    The helpers are part of the pinned source runtime, not a hand-maintained
    character heuristic.  In particular, an alphabetic screen character is
    not sufficient evidence that a glyph is a monster, much less a pet.  The
    result is diagnostic metadata only and must never select gold behavior.
    """

    try:
        from nle import nethack
    except ModuleNotFoundError:
        # Keep the adapter usable in the lightweight gold/test environment.
        # NetHack's cmap family is a pinned contiguous glyph range in the
        # capture contract; this fallback classifies only that range and
        # leaves entity/object glyphs unclassified when the optional NLE
        # package is unavailable.
        if NLE_GLYPH_CMAP_OFF <= int(glyph) < NLE_GLYPH_CMAP_OFF + 128:
            return "cmap_presentation"
        return "unclassified_presentation"
    checks = (
        ("pet_presentation", "glyph_is_pet"),
        ("normal_monster_presentation", "glyph_is_normal_monster"),
        ("detected_monster_presentation", "glyph_is_detected_monster"),
        ("ridden_monster_presentation", "glyph_is_ridden_monster"),
        ("monster_presentation", "glyph_is_monster"),
        ("statue_presentation", "glyph_is_statue"),
        ("object_presentation", "glyph_is_normal_object"),
        ("object_presentation", "glyph_is_object"),
        ("body_presentation", "glyph_is_body"),
        ("trap_presentation", "glyph_is_trap"),
        ("cmap_presentation", "glyph_is_cmap"),
        ("warning_presentation", "glyph_is_warning"),
        ("invisible_presentation", "glyph_is_invisible"),
    )
    for label, name in checks:
        predicate = getattr(nethack, name, None)
        if callable(predicate) and bool(predicate(int(glyph))):
            return label
    return "other_presentation"


def observed_entity_annotations(observation: dict[str, Any], *, nethack: Any | None = None) -> dict[str, list[dict[str, Any]]]:
    """Preserve reset-only glyph overlays as inert presentation markers.

    No visible glyph is materialized as a monster or object.  NLE's public
    planes do not expose allegiance, a pet identity, HP, attack stats, or a
    future trajectory.  The marker merely reproduces the captured reset pixel
    at that coordinate; all gameplay actions continue to use source-owned
    state only.
    """

    projection = project(observation)
    chars = projection["chars"]
    glyphs = projection["glyphs"]
    colors = projection["colors"]
    glyph_rows = glyphs if isinstance(glyphs, list) else []
    color_rows = colors if isinstance(colors, list) else []
    special_rows = projection.get("specials", [])
    overlays: list[dict[str, Any]] = []
    pet_markers: list[dict[str, Any]] = []
    blstats = projection.get("blstats", [])
    hero = (int(blstats[0]), int(blstats[1])) if isinstance(blstats, list) and len(blstats) >= 2 else None
    for y, row in enumerate(chars if isinstance(chars, list) else []):
        if not isinstance(row, list):
            continue
        for x, raw_char in enumerate(row):
            char = chr(int(raw_char))
            glyph = int(glyph_rows[y][x]) if y < len(glyph_rows) and isinstance(glyph_rows[y], list) and x < len(glyph_rows[y]) else ord(char)
            color = int(color_rows[y][x]) if y < len(color_rows) and isinstance(color_rows[y], list) and x < len(color_rows[y]) else 7
            # NLE's hero glyph itself falls within the monster glyph range;
            # screen coordinates, not glyph classification, establish this
            # one special case.  Cmap glyphs are the only static surfaces.
            if (x, y) == hero or char in {"@", " "}:
                continue
            presentation_class = glyph_presentation_class(glyph)
            if presentation_class == "cmap_presentation" or (presentation_class == "unclassified_presentation" and char in STATIC_SCREEN_CHARS):
                continue
            special = int(special_rows[y][x]) if isinstance(special_rows, list) and y < len(special_rows) and isinstance(special_rows[y], list) and x < len(special_rows[y]) else 0
            overlay = {
                    "x": x,
                    "y": y,
                    "char": char,
                    "glyph": glyph,
                    "color": color,
                    "provenance": "nle_reset_presentation",
                    "presentation_class": presentation_class,
                    "identity_status": "unavailable_from_nle_presentation",
            }
            if isinstance(special_rows, list) and y < len(special_rows) and isinstance(special_rows[y], list) and x < len(special_rows[y]):
                overlay["special"] = special
            overlays.append(overlay)
            # A source pet is exceptional: NLE exposes both a pet predicate
            # and a glyph-to-species table.  Materialize only that narrow
            # interaction contract, never a schedulable Monster.
            predicate = getattr(nethack, "glyph_is_pet", None) if nethack is not None else None
            glyph_to_mon = getattr(nethack, "glyph_to_mon", None) if nethack is not None else None
            permonst = getattr(nethack, "permonst", None) if nethack is not None else None
            mg_pet = int(getattr(nethack, "MG_PET", 8)) if nethack is not None else 8
            if callable(predicate) and callable(glyph_to_mon) and callable(permonst) and (bool(predicate(glyph)) or bool(special & mg_pet)):
                try:
                    name = str(permonst(int(glyph_to_mon(glyph))).mname)
                except (IndexError, TypeError, ValueError):
                    name = ""
                if name:
                    pet_markers.append({
                        "id": f"nle-reset-pet-{x}-{y}", "name": name,
                        "x": x, "y": y, "char": char, "glyph": glyph, "color": color,
                        "provenance": "nle_reset_pet_glyph", "identity_source": "glyph_to_mon_permonst",
                    })
    result: dict[str, list[dict[str, Any]]] = {"presentation_overlays": overlays}
    if pet_markers:
        result["pet_interaction_markers"] = pet_markers
    return result


def observed_hero_underlay(
    initial_observation: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    unseen_glyph: int,
) -> list[dict[str, Any]]:
    """Recover only static terrain initially occluded by the reset hero.

    This is source state, not a future visibility grant: the annotation is
    limited to the reset hero cell and is accepted only after that exact cell
    is exposed by a later raw NLE observation as static terrain.
    """

    initial = project(initial_observation)
    blstats = list(initial.get("blstats", []))
    if len(blstats) < 2:
        return []
    x, y = int(blstats[0]), int(blstats[1])
    for observation in observations[1:]:
        projection = project(observation)
        chars = projection.get("chars", [])
        glyphs = projection.get("glyphs", [])
        colors = projection.get("colors", [])
        if not (
            isinstance(chars, list)
            and isinstance(glyphs, list)
            and isinstance(colors, list)
            and 0 <= y < len(chars)
            and 0 <= y < len(glyphs)
            and 0 <= y < len(colors)
            and 0 <= x < len(chars[y])
            and 0 <= x < len(glyphs[y])
            and 0 <= x < len(colors[y])
        ):
            continue
        char = chr(int(chars[y][x]))
        glyph = int(glyphs[y][x])
        if char in STATIC_SCREEN_CHARS - {" ", "@"} and glyph != unseen_glyph:
            return [{"x": x, "y": y, "char": char, "glyph": glyph, "color": int(colors[y][x])}]
    return []


def _static_cell_observation(observation: dict[str, Any], x: int, y: int, *, unseen_glyph: int) -> dict[str, Any] | None:
    """Return a raw, visible static cell; a hero or entity is not an underlay."""

    projection = project(observation)
    chars = projection.get("chars", [])
    glyphs = projection.get("glyphs", [])
    colors = projection.get("colors", [])
    if not (
        isinstance(chars, list)
        and isinstance(glyphs, list)
        and isinstance(colors, list)
        and 0 <= y < len(chars)
        and 0 <= y < len(glyphs)
        and 0 <= y < len(colors)
        and isinstance(chars[y], list)
        and isinstance(glyphs[y], list)
        and isinstance(colors[y], list)
        and 0 <= x < len(chars[y])
        and 0 <= x < len(glyphs[y])
        and 0 <= x < len(colors[y])
    ):
        return None
    char = chr(int(chars[y][x]))
    glyph = int(glyphs[y][x])
    if char not in STATIC_SCREEN_CHARS - {" ", "@"} or glyph == unseen_glyph:
        return None
    return {"char": char, "glyph": glyph, "color": int(colors[y][x])}


def action_source_eligibility(
    action_name: str,
    observations: list[dict[str, Any]],
    *,
    step: int,
    unseen_glyph: int,
    source_annotations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """State whether an action can be judged using only its pre-action source.

    ``observations[:step]`` is intentional: observation ``step`` is the result
    of this action and must never backfill an eligibility decision.  Capture
    annotations are accepted only when explicitly supplied as such, never when
    inferred from a later live screen.
    """

    required = HERO_CELL_REQUIREMENTS.get(action_name, ())
    if not required:
        return {"status": "eligible", "requirements": []}
    if not observations or step < 1 or step > len(observations):
        return {
            "status": "unjudgeable",
            "requirements": [
                {"key": key, "provenance": "unknown", "reason": "missing_pre_action_observation"}
                for key in required
            ],
        }
    before = project(observations[step - 1])
    blstats = list(before.get("blstats", []))
    if len(blstats) < 2:
        return {
            "status": "unjudgeable",
            "requirements": [
                {"key": key, "provenance": "unknown", "reason": "missing_hero_position"}
                for key in required
            ],
        }
    x, y = int(blstats[0]), int(blstats[1])
    annotations = source_annotations or {}
    annotation_underlay = {
        (int(entry["x"]), int(entry["y"])): entry
        for entry in annotations.get("terrain_underlay", [])
        if isinstance(entry, dict) and type(entry.get("x")) is int and type(entry.get("y")) is int
    } if isinstance(annotations.get("terrain_underlay", []), list) else {}
    annotation_floor_objects = {
        (int(entry["x"]), int(entry["y"])): entry
        for entry in annotations.get("floor_objects", [])
        if isinstance(entry, dict) and type(entry.get("x")) is int and type(entry.get("y")) is int
    } if isinstance(annotations.get("floor_objects", []), list) else {}

    requirements: list[dict[str, Any]] = []
    for key in required:
        if key == "hero_terrain_underlay":
            observed: dict[str, Any] | None = None
            observed_at: int | None = None
            # Do not inspect observations[step:] -- they are future state.
            for index, observation in enumerate(observations[:step]):
                observed = _static_cell_observation(observation, x, y, unseen_glyph=unseen_glyph)
                if observed:
                    observed_at = index
                    break
            if observed:
                requirements.append(
                    {
                        "key": key,
                        "position": {"x": x, "y": y},
                        "provenance": "reset-observed" if observed_at == 0 else "prior-turn-observed",
                        "observed_at_step": observed_at,
                    }
                )
            elif (x, y) in annotation_underlay:
                requirements.append(
                    {"key": key, "position": {"x": x, "y": y}, "provenance": "capture-annotation"}
                )
            else:
                requirements.append(
                    {"key": key, "position": {"x": x, "y": y}, "provenance": "unknown", "reason": "hero_cell_occluded"}
                )
        elif key == "hero_floor_object_set":
            # A glyph seen before stepping onto a square cannot establish a
            # complete floor stack.  Require an explicit capture annotation.
            if (x, y) in annotation_floor_objects:
                requirements.append(
                    {"key": key, "position": {"x": x, "y": y}, "provenance": "capture-annotation"}
                )
            else:
                requirements.append(
                    {"key": key, "position": {"x": x, "y": y}, "provenance": "unknown", "reason": "floor_object_set_not_authoritative"}
                )
    if any(requirement["provenance"] not in SOURCE_PROVENANCE for requirement in requirements):
        raise AssertionError("source-state provenance must use the closed provenance vocabulary")
    return {"status": "eligible" if all(requirement["provenance"] != "unknown" for requirement in requirements) else "unjudgeable", "requirements": requirements}


def comparison_eligibility(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn source eligibility into a causal comparison boundary for one lane."""

    first_unjudgeable: int | None = None
    steps: list[dict[str, Any]] = []
    for index, action in enumerate(actions, start=1):
        source = action.get("source_state_eligibility", {"status": "eligible", "requirements": []})
        if not isinstance(source, dict):
            raise AssertionError("source-state eligibility records must be objects")
        source_status = str(source.get("status", "unjudgeable"))
        requirements = source.get("requirements", [])
        if source_status not in {"eligible", "unjudgeable"} or not isinstance(requirements, list):
            raise AssertionError("source-state eligibility record has an invalid status or requirements list")
        provenances: list[str] = []
        for requirement in requirements:
            if not isinstance(requirement, dict) or not isinstance(requirement.get("provenance"), str):
                raise AssertionError("every required source state must carry provenance")
            provenance = str(requirement["provenance"])
            if provenance not in SOURCE_PROVENANCE:
                raise AssertionError(f"unsupported source-state provenance {provenance!r}")
            provenances.append(provenance)
        if source_status == "eligible" and "unknown" in provenances:
            raise AssertionError("an eligibility record with unknown source state cannot be eligible")
        if source_status == "unjudgeable" and requirements and "unknown" not in provenances:
            raise AssertionError("an unjudgeable source-state record must identify unknown required state")
        if first_unjudgeable is not None:
            status = "unjudgeable"
            reason = "prior_unjudgeable_transition"
        elif source_status != "eligible":
            first_unjudgeable = index
            status = "unjudgeable"
            reason = "unknown_required_source_state"
        else:
            status = "eligible"
            reason = ""
        steps.append({"step": index, "action_name": action.get("action_name", ""), "status": status, "reason": reason, "source_state": source})
    return {
        "schema": "gamebench.nethack.source_state_eligibility.v1",
        "status": "unjudgeable" if first_unjudgeable is not None else "eligible",
        "first_unjudgeable_step": first_unjudgeable,
        "judgeable_action_steps": sum(step["status"] == "eligible" for step in steps),
        "unjudgeable_action_steps": sum(step["status"] == "unjudgeable" for step in steps),
        "steps": steps,
    }


def normalise_step(result: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(result, tuple) and len(result) >= 3:
        return dict(result[0]), bool(result[2])
    return dict(result), False


@dataclass
class TraceRun:
    """Replay snapshots plus an explicit fail-hard runtime boundary."""

    snapshots: list[dict[str, Any]]
    runtime_error: dict[str, Any] | None = None


def _runtime_error(record: dict[str, Any] | None, error: BaseException) -> dict[str, Any]:
    return {
        "step": int(record.get("step", 0)) if isinstance(record, dict) else 0,
        "action_id": int(record.get("action_id", -1)) if isinstance(record, dict) else -1,
        "action_name": str(record.get("action_name", "")) if isinstance(record, dict) else "",
        "error_type": type(error).__name__,
        "message": str(error),
    }


def python_trace(task: dict[str, Any], actions: list[dict[str, Any]]) -> TraceRun:
    engine = NethackDlvl1Engine()
    try:
        engine.reset(resolve_task(task))
    except BaseException as error:
        return TraceRun([], _runtime_error(None, error))
    projections = [engine.public_projection()]
    for record in actions:
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        try:
            engine.step(int(record["action_id"]))
        except BaseException as error:
            return TraceRun(projections, _runtime_error(record, error))
        projections.append(engine.public_projection())
    return TraceRun(projections)


def rust_trace(task: dict[str, Any], actions: list[dict[str, Any]]) -> TraceRun:
    entry = {**task, "actions": [int(record["action_id"]) for record in actions]}
    try:
        snapshots = list(run_scenario(entry, ("--trace-stdin",))["snapshots"])
        # Rust keeps a fail-hard scheduler contract violation as an explicit
        # terminal boundary so the service cannot continue with guessed state.
        # Normalize that owned boundary to the same runtime-error denominator
        # used by Python; otherwise a real gold-lane contract failure appears
        # as an artificial Python/Rust comparison-count mismatch.
        for index, snapshot in enumerate(snapshots[1:], start=1):
            if snapshot.get("terminal_reason") == "scheduler_contract_violation":
                record = actions[index - 1] if index - 1 < len(actions) else (actions[-1] if actions else None)
                return TraceRun(
                    snapshots[:index],
                    _runtime_error(record, RuntimeError("scheduler_contract_violation")),
                )
        return TraceRun(snapshots)
    except BaseException as error:
        if isinstance(error, subprocess.CalledProcessError):
            detail = error.stderr.decode() if isinstance(error.stderr, bytes) else str(error.stderr or error)
            error = RuntimeError(detail.strip() or str(error))
        return TraceRun([], _runtime_error(actions[0] if actions else None, error))


def source_static_frame(projection: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Extract the narrow, glyph-classified static part of one NLE screen.

    This adapter is intentionally stricter than looking at a display character:
    a `.`/`+` drawn by an object or another overlay is not terrain.  The frame
    is supplied only before the *next* action in source-state replay, never to
    repair the action that produced it.
    """

    chars = _char_rows(projection)
    glyphs = projection.get("glyphs", [])
    colors = projection.get("colors", [])
    cells: list[dict[str, Any]] = []
    rejected_non_cmap = 0
    for y, row in enumerate(chars):
        for x, char in enumerate(row):
            if char not in STATIC_SCREEN_CHARS - {" ", "@"}:
                continue
            glyph = _plane_value(projection, "glyphs", x, y, -1)
            color = _plane_value(projection, "colors", x, y, 0)
            if glyph_presentation_class(int(glyph)) != "cmap_presentation":
                rejected_non_cmap += 1
                continue
            cells.append({"x": x, "y": y, "char": char, "glyph": int(glyph), "color": int(color)})
    return cells, {"static_cmap_cells": len(cells), "rejected_static_char_non_cmap": rejected_non_cmap}


def python_source_state_trace(
    task: dict[str, Any],
    actions: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, int]]]:
    """Replay with source-static memory from strictly prior oracle frames."""

    if len(expected) < len(actions):
        raise ValueError("source-state replay requires one prior source frame per action")
    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    projections = [engine.public_projection()]
    reconciliations: list[dict[str, Any]] = []
    frame_audit: list[dict[str, int]] = []
    for index, record in enumerate(actions):
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        cells, audit = source_static_frame(expected[index])
        counts = engine.reconcile_source_static_cells(cells)
        reconciliations.append({"before_action_step": index + 1, "counts": counts})
        frame_audit.append(audit)
        engine.step(int(record["action_id"]))
        projections.append(engine.public_projection())
    return projections, reconciliations, frame_audit


def rust_source_state_trace(
    task: dict[str, Any],
    actions: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, int]]]:
    if len(expected) < len(actions):
        raise ValueError("source-state replay requires one prior source frame per action")
    frames_and_audits = [source_static_frame(expected[index]) for index in range(len(actions))]
    entry = {
        **task,
        "actions": [int(record["action_id"]) for record in actions],
        "source_static_frames": [cells for cells, _ in frames_and_audits],
    }
    replay = run_scenario(entry, ("--source-state-replay-stdin",))
    return (
        list(replay["snapshots"]),
        list(replay["source_static_reconciliations"]),
        [audit for _, audit in frames_and_audits],
    )


def source_state_replay_report(
    lane: str,
    task: dict[str, Any],
    actions: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    *,
    strict_baseline: bool,
    oracle_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Judge a labelled prior-source-memory replay without replacing gold's core lane."""

    if lane == "python":
        actual, reconciliations, frame_audit = python_source_state_trace(task, actions, expected)
    elif lane == "rust":
        actual, reconciliations, frame_audit = rust_source_state_trace(task, actions, expected)
    else:
        raise ValueError(f"unsupported source-state replay lane {lane!r}")
    judged = lane_report(
        lane,
        expected,
        actual,
        actions,
        strict_baseline=strict_baseline,
        oracle_snapshots=oracle_snapshots,
        reset_level=task["level_dump"],
    )
    static_counts = {
        "source_static_cmap_cells": sum(int(frame["static_cmap_cells"]) for frame in frame_audit),
        "rejected_static_char_non_cmap": sum(int(frame["rejected_static_char_non_cmap"]) for frame in frame_audit),
        "hydrated": sum(int(entry["counts"]["hydrated"]) for entry in reconciliations),
        "already_known": sum(int(entry["counts"]["already_known"]) for entry in reconciliations),
        "conflicts": sum(int(entry["counts"]["conflicts"]) for entry in reconciliations),
    }
    return {
        "schema": "gamebench.nethack.prior_source_static_replay.v1",
        "status": "diagnostic_only",
        "not_a_gold_conformance_lane": True,
        "ordering_contract": "source_static_frames[step-1] is reconciled before action step; no current/future frame is admitted",
        "static_cell_contract": "glyph-classified cmap/static cells only; overlays, hero underlays, blanks, and conflicts are excluded",
        "frame_audit": frame_audit,
        "reconciliations": reconciliations,
        "static_counts": static_counts,
        "judge_summary": {
            "strict_snapshot_v1": judged["strict_snapshot_v1"],
            "bootstrap_masked_transition_v0": judged["bootstrap_masked_transition_v0"],
            "visibility_entity_transition_oracle_v1": {
                key: judged["visibility_entity_transition_oracle_v1"][key]
                for key in ("status", "comparisons", "error_count", "failed_transition_count", "score", "first_error", "unjudgeable_surface_record_count")
            },
            "terminal_ui_oracle_v1": {
                key: judged["terminal_ui_oracle_v1"][key]
                for key in ("status", "comparisons", "error_count")
            },
        },
    }


def _turn_effect(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_stats = list(before.get("blstats", []))
    after_stats = list(after.get("blstats", []))
    return {
        "turn_consumed": bool(len(before_stats) > 20 and len(after_stats) > 20 and after_stats[20] != before_stats[20]),
        "time_delta": int(after_stats[20]) - int(before_stats[20]) if len(before_stats) > 20 and len(after_stats) > 20 else None,
        "hero_delta": [
            int(after_stats[0]) - int(before_stats[0]),
            int(after_stats[1]) - int(before_stats[1]),
        ] if len(before_stats) > 1 and len(after_stats) > 1 else None,
        "done": bool(after.get("done", False)),
    }


def lane_report(
    lane: str,
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    strict_baseline: bool,
    oracle_snapshots: list[dict[str, Any]] | None = None,
    reset_level: dict[str, Any] | None = None,
    runtime_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # `specials` has its own fail-closed layer because only MG_PET is currently
    # causally derivable by gold.  Do not let an unsupported sparse bit at
    # reset truncate prompt, turn, UI, visibility, and semantic comparisons.
    # The plane is still judged below; this is separation, not masking.
    unknown_surface_coordinates = set(_reset_unknown_surface_coordinates(reset_level))
    expected_core = [
        _mask_unknown_surface_cells(
            {key: value for key, value in snapshot.items() if key != "specials"},
            unknown_surface_coordinates,
        )
        for snapshot in expected
    ]
    actual_core = [
        _mask_unknown_surface_cells(
            {key: value for key, value in snapshot.items() if key != "specials"},
            unknown_surface_coordinates,
        )
        for snapshot in actual
    ]
    baseline_mask = set() if strict_baseline else set(difference_paths(expected_core[0], actual_core[0]))
    eligibility = comparison_eligibility(actions)
    first_unjudgeable = eligibility["first_unjudgeable_step"]
    # Snapshot zero is always a reset comparison.  A source-unknown action
    # taints its result and every later transition, so they are recorded but
    # never called equal/diverged and never enter a fidelity denominator.
    comparison_limit = min(
        len(expected) - 1,
        len(actual) - 1,
        (int(first_unjudgeable) - 1) if first_unjudgeable is not None else min(len(expected) - 1, len(actual) - 1),
    )

    strict_difference: dict[str, Any] | None = None
    transition_difference: dict[str, Any] | None = None
    for step, expected_snapshot in enumerate(expected_core[: comparison_limit + 1]):
        action = actions[step - 1] if step > 0 and step - 1 < len(actions) else None
        if step >= len(actual_core):
            difference = {"path": "$.trace", "expected": f"snapshot at step {step}", "actual": "trace ended early"}
        else:
            difference = first_difference(expected_snapshot, actual_core[step])
        if difference and strict_difference is None:
            strict_difference = {"step": step, "action": action, **difference}
        if step >= len(actual):
            masked = difference
        elif strict_baseline:
            masked = first_difference(expected_snapshot, actual_core[step])
        else:
            masked = first_transition_difference(expected_core[0], actual_core[0], expected_snapshot, actual_core[step])
        if masked and transition_difference is None:
            transition_difference = {"step": step, "action": action, **masked}

    first_step = int(strict_difference["step"]) if strict_difference else comparison_limit
    census: list[dict[str, Any]] = []
    if strict_difference and first_step < len(expected_core) and first_step < len(actual_core):
        census = list(mismatch_records(expected_core[first_step], actual_core[first_step]))
        for record in census:
            record["class"] = mismatch_class(str(record["path"]))
    census_counts = Counter(str(record["class"]) for record in census)

    mode_errors: list[dict[str, Any]] = []
    turn_errors: list[dict[str, Any]] = []
    terminal_errors: list[dict[str, Any]] = []
    terminal_comparisons = 0
    terminal_ui_errors: list[dict[str, Any]] = []
    extended_limit = min(first_step, comparison_limit)
    if oracle_snapshots:
        for step in range(0, extended_limit + 1):
            expected_mode = str(oracle_snapshots[step].get("inferred_input_mode", "unknown"))
            actual_mode_value = actual[step].get("input_mode", {})
            actual_mode = str(actual_mode_value.get("kind", "unknown")) if isinstance(actual_mode_value, dict) else "unknown"
            # Gold retains an operation-specific internal state; NLE exposes
            # only the public yes/no/question input family.
            if actual_mode == "attack_confirm":
                actual_mode = "ynq"
            if expected_mode != actual_mode:
                mode_errors.append({"step": step, "expected": expected_mode, "actual": actual_mode})

            expected_terminal_ui, actual_terminal_ui = judge_layers(oracle_snapshots[step], actual[step])["terminal_ui"]
            ui_mismatches = list(mismatch_records(expected_terminal_ui, actual_terminal_ui, path="$.terminal_ui"))
            terminal_ui_errors.extend({"step": step, **record} for record in ui_mismatches)

            if step > 0:
                expected_effect = _turn_effect(expected[step - 1], expected[step])
                actual_effect = _turn_effect(actual[step - 1], actual[step])
                effect_mismatches = list(mismatch_records(expected_effect, actual_effect, path="$.turn_effect"))
                turn_errors.extend({"step": step, **record} for record in effect_mismatches)

    for step in range(comparison_limit + 1):
        if not bool(expected[step].get("done", False)):
            continue
        terminal_comparisons += 1
        expected_terminal = {
            "done": True,
            "terminal_reason": expected[step].get("terminal_reason", ""),
        }
        if expected_terminal["terminal_reason"] == "nle_done_unknown":
            expected_terminal.pop("terminal_reason")
        actual_terminal = {
            "done": bool(actual[step].get("done", False)),
            "terminal_reason": str(actual[step].get("terminal_reason", "")),
        }
        terminal_mismatches = list(mismatch_records(expected_terminal, actual_terminal, path="$.terminal"))
        terminal_errors.extend({"step": step, **record} for record in terminal_mismatches)

    visibility_entity = layered_transition_report(
        expected[: comparison_limit + 1],
        actual[: comparison_limit + 1],
        reset_level=reset_level,
    )
    seeded_outcomes = seeded_outcome_report(
        expected,
        actual,
        actions,
        through_step=min(first_step, comparison_limit),
    )
    specials = specials_trace_report(
        expected,
        actual,
        through_step=extended_limit,
    )
    strict_status = "diverged" if strict_difference is not None else ("unjudgeable" if first_unjudgeable is not None else "equal")
    transition_status = "diverged" if transition_difference is not None else ("unjudgeable" if first_unjudgeable is not None else "equal")
    return {
        "lane": lane,
        "runtime_error_v1": {
            "status": "errors_found" if runtime_error else "pass",
            "error": runtime_error,
        },
        "source_state_eligibility_v1": eligibility,
        "strict_snapshot_v1": {
            "status": strict_status,
            "first_difference": strict_difference,
            "comparison_through_step": comparison_limit,
            "unjudgeable_from_step": first_unjudgeable,
            "source_unknown_surface_coordinates": [
                {"x": x, "y": y} for x, y in sorted(unknown_surface_coordinates)
            ],
        },
        "bootstrap_masked_transition_v0": {
            "status": transition_status,
            "first_difference": transition_difference,
            "baseline_masked_path_count": len(baseline_mask),
            "strict_baseline": strict_baseline,
            "comparison_through_step": comparison_limit,
            "unjudgeable_from_step": first_unjudgeable,
        },
        "first_divergent_step_census_v1": {
            "step": strict_difference["step"] if strict_difference else None,
            "mismatch_count": len(census),
            "counts_by_class": dict(sorted(census_counts.items())),
            "mismatches": census,
        },
        "prompt_mode_oracle_v1": {
            "comparisons": extended_limit + 1 if oracle_snapshots else 0,
            "error_count": len(mode_errors),
            "errors": mode_errors,
            "status": "pass" if oracle_snapshots and not mode_errors else ("not_exercised" if not oracle_snapshots else "errors_found"),
        },
        "turn_consumption_oracle_v1": {
            "comparisons": extended_limit if oracle_snapshots else 0,
            "error_count": len(turn_errors),
            "errors": turn_errors,
            "status": "pass" if oracle_snapshots and not turn_errors else ("not_exercised" if not oracle_snapshots else "errors_found"),
        },
        "terminal_ui_oracle_v1": {
            "comparisons": extended_limit + 1 if oracle_snapshots else 0,
            "error_count": len(terminal_ui_errors),
            "errors": terminal_ui_errors,
            "status": "pass" if oracle_snapshots and not terminal_ui_errors else ("not_exercised" if not oracle_snapshots else "errors_found"),
        },
        "specials_oracle_v1": specials,
        "terminal_boundary_oracle_v1": {
            "comparisons": terminal_comparisons,
            "error_count": len(terminal_errors),
            "errors": terminal_errors,
            "status": "pass" if terminal_comparisons and not terminal_errors else ("not_exercised" if terminal_comparisons == 0 else "errors_found"),
        },
        "seeded_outcome_oracle_v1": seeded_outcomes,
        "visibility_entity_transition_oracle_v1": visibility_entity,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def action_family(action_name: str) -> str:
    return action_name.partition(".")[0] or "unknown"


def changed_blstats_slots(snapshots: list[dict[str, Any]]) -> list[int]:
    if not snapshots:
        return []
    initial = list(dict(snapshots[0].get("projection", {})).get("blstats", []))
    changed: set[int] = set()
    for snapshot in snapshots[1:]:
        current = list(dict(snapshot.get("projection", {})).get("blstats", []))
        for index, (before, after) in enumerate(zip(initial, current, strict=False)):
            if before != after:
                changed.add(index)
    return sorted(changed)


def coverage_report(table: list[list[Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize selected and NLE-stepped inputs, not a parity claim."""

    actions = [record for case in cases for record in case["actions"]]
    selected_action_ids = sorted({int(record["action_id"]) for record in actions})
    nle_stepped_actions = [record for record in actions if record.get("nle_stepped") is True]
    nle_stepped_action_ids = sorted({int(record["action_id"]) for record in nle_stepped_actions})
    contexts = sorted(
        {
            (
                int(record["action_id"]),
                str(record["action_name"]),
                str(record.get("input_mode", "unknown")),
                record.get("nle_stepped") is True,
            )
            for record in actions
        }
    )
    family_counts = Counter(action_family(str(record["action_name"])) for record in actions)
    mode_counts = Counter(str(record.get("input_mode", "unknown")) for record in actions)
    selection_counts = Counter(str(record.get("selection", "unknown")) for record in actions)
    terminal_counts = Counter(
        str(snapshot.get("terminal_reason", ""))
        for case in cases
        for snapshot in case["snapshots"]
        if snapshot.get("terminal_reason")
    )
    mutable_blstats = sorted({slot for case in cases for slot in changed_blstats_slots(case["snapshots"])})
    observation_delta_counts = Counter()
    for case in cases:
        snapshots = case["snapshots"]
        if not snapshots:
            continue
        baseline = dict(snapshots[0].get("projection", {}))
        for snapshot in snapshots[1:]:
            current = dict(snapshot.get("projection", {}))
            for key in ("chars", "colors", "glyphs", "message_raw", "inventory"):
                if baseline.get(key) != current.get(key):
                    observation_delta_counts[key] += 1
    differential_counts = Counter()
    first_paths = Counter()
    signatures: list[dict[str, Any]] = []
    for case in cases:
        report = case["report"]
        for lane in report["lanes"]:
            status = str(lane["bootstrap_masked_transition_v0"]["status"])
            differential_counts[f"transition_{status}"] += 1
            difference = lane["bootstrap_masked_transition_v0"].get("first_difference")
            if difference:
                first_paths[str(difference.get("path", "unknown"))] += 1
        initial = dict(case["snapshots"][0].get("projection", {})) if case["snapshots"] else {}
        signature_payload = {
            "initial_chars": initial.get("chars", []),
            "contexts": [
                (record["action_id"], record.get("input_mode", "unknown"), record.get("nle_stepped") is True)
                for record in case["actions"]
            ],
            "terminal_reasons": [snapshot.get("terminal_reason", "") for snapshot in case["snapshots"] if snapshot.get("terminal_reason")],
        }
        signatures.append(
            {
                "fixture_id": case["meta"]["fixture_id"],
                "sha256": hashlib.sha256(canonical_json(signature_payload).encode("utf-8")).hexdigest(),
            }
        )
    return {
        "schema": "gamebench.nethack.live_fuzz_coverage.v1",
        "diagnostic_fuzz": True,
        "not_a_conformance_pass": True,
        "cases": len(cases),
        "action_ids": {
            "selected": selected_action_ids,
            "selected_count": len(selected_action_ids),
            "nle_stepped": nle_stepped_action_ids,
            "nle_stepped_count": len(nle_stepped_action_ids),
            "pinned_count": len(table),
            "selected_fraction": len(selected_action_ids) / len(table) if table else 0.0,
            "nle_stepped_fraction": len(nle_stepped_action_ids) / len(table) if table else 0.0,
        },
        "action_contexts": [
            {"action_id": action_id, "action_name": action_name, "input_mode": input_mode, "nle_stepped": nle_stepped}
            for action_id, action_name, input_mode, nle_stepped in contexts
        ],
        "enum_family_step_counts": dict(sorted(family_counts.items())),
        "input_mode_step_counts": dict(sorted(mode_counts.items())),
        "selection_step_counts": dict(sorted(selection_counts.items())),
        "terminal_reason_counts": dict(sorted(terminal_counts.items())),
        "observation": {
            "changed_blstats_slots": mutable_blstats,
            "changed_blstats_slot_count": len(mutable_blstats),
            "snapshot_delta_counts": dict(sorted(observation_delta_counts.items())),
        },
        "differential": {
            "transition_lane_counts": dict(sorted(differential_counts.items())),
            "first_difference_paths": dict(sorted(first_paths.items())),
        },
        "novelty_signatures": signatures,
    }


def causal_level_dump(initial_observation: dict[str, Any], annotations: dict[str, Any], *, unseen_glyph: int) -> dict[str, Any]:
    """Materialize only reset-observable state for a live differential case."""

    return level_dump(
        initial_observation,
        annotations,
        observations=[initial_observation],
        unseen_glyph=unseen_glyph,
    )


def native_bootstrap_level_dump(
    causal_level: dict[str, Any],
    initial_observation: dict[str, Any],
    native_export: dict[str, Any],
    *,
    nethack: Any,
) -> dict[str, Any]:
    """Freeze one authoritative *reset* terrain/FOV export into a diagnostic task.

    The native export is produced before action one from the hash-verified NLE
    binary.  This function intentionally has no ``observations`` argument: a
    later source frame cannot enter this bootstrap by construction.  It is not
    a core gold input or a conformance score; it is a separate navigation
    experiment to determine whether exact reset terrain/FOV is sufficient to
    improve later fidelity.
    """

    if native_export.get("provenance") != "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array":
        raise ValueError("native bootstrap requires a verified read-only NLE source export")
    if not NATIVE_BOOTSTRAP_REQUIRED_FIELDS <= set(native_export):
        raise ValueError("native bootstrap lacks an authoritative terrain/FOV/memory plane")
    terrain_types = native_export["full_map_terrain"]
    fov = native_export["fov_visibility_mask"]
    memory = native_export["map_memory"]
    memory_glyphs = memory.get("glyph") if isinstance(memory, dict) else None
    memory_seenv = memory.get("seenv") if isinstance(memory, dict) else None
    dimensions = (21, 79)
    planes = (terrain_types, fov, memory_glyphs, memory_seenv)
    if any(not isinstance(plane, list) or len(plane) != dimensions[0] or any(not isinstance(row, list) or len(row) != dimensions[1] for row in plane) for plane in planes):
        raise ValueError("native bootstrap planes must be exact NLE 21x79 arrays")
    if any(type(value) is not int or value not in NATIVE_TERRAIN_CHARS for row in terrain_types for value in row):
        raise ValueError("native bootstrap contains an unsupported NetHack terrain type")
    if any(type(value) is not bool for row in fov for value in row):
        raise ValueError("native bootstrap FOV mask must be boolean")
    if any(type(value) is not int for plane in (memory_glyphs, memory_seenv) for row in plane for value in row):
        raise ValueError("native bootstrap memory planes must be integer")

    result = deepcopy(causal_level)
    terrain = [[NATIVE_TERRAIN_CHARS[int(value)] for value in row] for row in terrain_types]
    glyphs = [[int(value) for value in row] for row in memory_glyphs]
    colors = [[7 for _ in range(dimensions[1])] for _ in range(dimensions[0])]
    terrain_flags = native_export.get("full_map_terrain_flags", [[0] * dimensions[1] for _ in range(dimensions[0])])
    terrain_horizontal = native_export.get("full_map_terrain_horizontal", [[False] * dimensions[1] for _ in range(dimensions[0])])
    if not (
        isinstance(terrain_flags, list)
        and len(terrain_flags) == dimensions[0]
        and all(isinstance(row, list) and len(row) == dimensions[1] for row in terrain_flags)
        and isinstance(terrain_horizontal, list)
        and len(terrain_horizontal) == dimensions[0]
        and all(isinstance(row, list) and len(row) == dimensions[1] for row in terrain_horizontal)
    ):
        raise ValueError("native bootstrap semantic terrain planes must be exact 21x79 arrays")
    native_door_semantics = 0
    for y in range(dimensions[0]):
        for x in range(dimensions[1]):
            terrain[y][x], fallback_glyph = native_surface_for_terrain(
                int(terrain_types[y][x]), int(terrain_flags[y][x]), bool(terrain_horizontal[y][x])
            )
            # A reset-hidden cell has no rendered memory glyph.  Seed its
            # own terrain-derived cmap glyph so later source-visible static
            # rendering does not retain the blank-background glyph. Direct
            # reset pixels below still take precedence for exact orientation,
            # color, and special furniture/stair presentation.
            if int(terrain_types[y][x]) == 22:
                native_door_semantics += 1
            if int(memory_seenv[y][x]) == 0:
                glyphs[y][x] = fallback_glyph
    projected = project(initial_observation)
    source_chars = projected.get("chars", [])
    source_glyphs = projected.get("glyphs", [])
    source_colors = projected.get("colors", [])
    direct_static_controls = 0
    for y in range(dimensions[0]):
        for x in range(dimensions[1]):
            if not (
                isinstance(source_chars, list) and isinstance(source_glyphs, list) and isinstance(source_colors, list)
                and y < len(source_chars) and y < len(source_glyphs) and y < len(source_colors)
                and isinstance(source_chars[y], list) and isinstance(source_glyphs[y], list) and isinstance(source_colors[y], list)
                and x < len(source_chars[y]) and x < len(source_glyphs[y]) and x < len(source_colors[y])
            ):
                continue
            glyph = int(source_glyphs[y][x])
            char = chr(int(source_chars[y][x]))
            if bool(nethack.glyph_is_cmap(glyph)) and char in STATIC_TERRAIN_CHARS:
                # Exact direct public pixels take precedence over any coarse
                # type family.  This controls wall/door orientation and color
                # without ever asking a future frame.
                terrain[y][x] = char
                glyphs[y][x] = glyph
                colors[y][x] = int(source_colors[y][x])
                direct_static_controls += 1
    result["terrain"] = ["".join(row) for row in terrain]
    result["glyphs"] = glyphs
    result["colors"] = colors
    result["seen"] = [[bool(value) for value in row] for row in fov]
    metadata = dict(result.get("metadata", {}))
    metadata["native_bootstrap"] = {
        "schema": "gamebench.nethack.native_reset_bootstrap.v1",
        "provenance": native_export["provenance"],
        "binary_sha256": native_export.get("binary_sha256"),
        "coordinate_contract": native_export.get("coordinate_contract"),
        "ordering": "single native snapshot after reset and before action 1; no later source observation admitted",
        "direct_static_public_controls": direct_static_controls,
        "native_door_semantics_cells": native_door_semantics,
        "native_door_semantics_contract": "DOOR uses rm.flags/doormask and rm.horizontal; D_NODOOR renders S_ndoor floor-dot, open/closed doors retain orientation",
        "native_plane_sha256": deepcopy(native_export.get("plane_sha256", {})),
        "native_map_memory_seenv_sha256": hashlib.sha256(canonical_json(memory_seenv).encode("utf-8")).hexdigest(),
        "diagnostic_only": True,
        "not_a_gold_conformance_lane": True,
    }
    result["metadata"] = metadata
    return result


def native_bootstrap_negative_controls(
    task: dict[str, Any],
    initial_observation: dict[str, Any],
    native_export: dict[str, Any],
) -> dict[str, Any]:
    """Prove reset-unknown cells remain hidden in the bootstrap render."""

    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    rendered = engine.public_projection()
    source = project(initial_observation)
    fov = native_export.get("fov_visibility_mask", [])
    hero = task["level_dump"]["hero"]
    checked = 0
    for y, row in enumerate(fov if isinstance(fov, list) else []):
        if not isinstance(row, list):
            continue
        for x, visible in enumerate(row):
            if visible or (x, y) == (int(hero["x"]), int(hero["y"])):
                continue
            if not (
                isinstance(source.get("chars"), list) and isinstance(source.get("glyphs"), list) and isinstance(source.get("colors"), list)
                and y < len(source["chars"]) and y < len(source["glyphs"]) and y < len(source["colors"])
                and isinstance(source["chars"][y], list) and isinstance(source["glyphs"][y], list) and isinstance(source["colors"][y], list)
                and x < len(source["chars"][y]) and x < len(source["glyphs"][y]) and x < len(source["colors"][y])
            ):
                continue
            actual = (rendered["chars"][y][x], int(rendered["glyphs"][y][x]), int(rendered["colors"][y][x]))
            expected = (chr(int(source["chars"][y][x])), int(source["glyphs"][y][x]), int(source["colors"][y][x]))
            if actual != expected:
                raise AssertionError(f"native bootstrap leaked true terrain into reset render at {(x, y)}")
            checked += 1
    if checked == 0:
        raise AssertionError("native bootstrap has no reset-hidden negative controls")
    return {
        "status": "pass",
        "reset_hidden_render_controls": checked,
        "assertion": "native true terrain is internal bootstrap state only; reset pixels at source-not-in-sight cells remain exactly source-rendered",
    }


def native_bootstrap_metrics(report: dict[str, Any]) -> dict[str, Any]:
    """Compact apples-to-apples diagnostics; never a conformance score."""

    strict = dict(report.get("strict_snapshot_v1", {}))
    first = strict.get("first_difference")
    census = dict(report.get("first_divergent_step_census_v1", {}))
    visibility = dict(report.get("visibility_entity_transition_oracle_v1", {}))
    return {
        "strict_status": strict.get("status"),
        "first_divergence_step": first.get("step") if isinstance(first, dict) else None,
        "first_divergence_path": first.get("path") if isinstance(first, dict) else None,
        "first_divergence_mismatch_count": census.get("mismatch_count"),
        "visibility_comparisons": visibility.get("comparisons"),
        "visibility_errors": visibility.get("error_count"),
        "visibility_unjudgeable_surface_records": visibility.get("unjudgeable_surface_record_count"),
    }


def native_bootstrap_comparison_summary(reports: list[dict[str, Any]], *, heldout_fixture_ids: set[str]) -> dict[str, Any]:
    """Aggregate ordinary-vs-bootstrap diagnostics without manufacturing a score."""

    phases: dict[str, list[dict[str, Any]]] = {"calibration": [], "heldout": []}
    for case in reports:
        fixture_id = str(case.get("fixture_id", ""))
        phase = "heldout" if fixture_id in heldout_fixture_ids else "calibration"
        ordinary = case.get("lanes", [])
        bootstrap = case.get("native_reset_bootstrap_navigation_v1", [])
        if not isinstance(ordinary, list) or not isinstance(bootstrap, list) or len(ordinary) != len(bootstrap):
            raise ValueError("native bootstrap summary requires equal ordinary/native lane counts")
        for own, native in zip(ordinary, bootstrap, strict=True):
            if not isinstance(own, dict) or not isinstance(native, dict):
                raise ValueError("native bootstrap summary lanes must be objects")
            own_metrics = native_bootstrap_metrics(own)
            native_metrics = dict(native.get("metrics", {}))
            phases[phase].append({"fixture_id": fixture_id, "lane": own.get("lane"), "ordinary": own_metrics, "native_reset_bootstrap": native_metrics})

    def aggregate(entries: list[dict[str, Any]]) -> dict[str, Any]:
        def numeric(side: str, key: str) -> int:
            return sum(int(entry[side].get(key) or 0) for entry in entries)
        return {
            "lane_traces": len(entries),
            "ordinary": {
                "first_divergence_step_counts": dict(sorted(Counter(str(entry["ordinary"].get("first_divergence_step")) for entry in entries).items())),
                "first_divergence_mismatch_total": numeric("ordinary", "first_divergence_mismatch_count"),
                "visibility_errors": numeric("ordinary", "visibility_errors"),
                "visibility_comparisons": numeric("ordinary", "visibility_comparisons"),
            },
            "native_reset_bootstrap": {
                "first_divergence_step_counts": dict(sorted(Counter(str(entry["native_reset_bootstrap"].get("first_divergence_step")) for entry in entries).items())),
                "first_divergence_mismatch_total": numeric("native_reset_bootstrap", "first_divergence_mismatch_count"),
                "visibility_errors": numeric("native_reset_bootstrap", "visibility_errors"),
                "visibility_comparisons": numeric("native_reset_bootstrap", "visibility_comparisons"),
            },
            "records": entries,
        }

    heldout = aggregate(phases["heldout"])
    heldout_checks: list[dict[str, Any]] = []
    for fixture_id in sorted({str(entry["fixture_id"]) for entry in phases["heldout"]}):
        entries = [entry for entry in phases["heldout"] if str(entry["fixture_id"]) == fixture_id]
        lane_checks: list[dict[str, Any]] = []
        for entry in entries:
            ordinary_step = entry["ordinary"].get("first_divergence_step")
            native_step = entry["native_reset_bootstrap"].get("first_divergence_step")
            # ``None`` means no divergence through the eligible trace and is
            # therefore better than every numeric step.
            ordinary_rank = float("inf") if ordinary_step is None else int(ordinary_step)
            native_rank = float("inf") if native_step is None else int(native_step)
            preserves_first_divergence = native_rank >= ordinary_rank
            preserves_visibility = int(entry["native_reset_bootstrap"].get("visibility_errors") or 0) <= int(entry["ordinary"].get("visibility_errors") or 0)
            lane_checks.append(
                {
                    "lane": entry["lane"],
                    "preserves_or_improves_first_divergence": preserves_first_divergence,
                    "preserves_or_improves_visibility_errors": preserves_visibility,
                    "passes": preserves_first_divergence and preserves_visibility,
                }
            )
        heldout_checks.append({"fixture_id": fixture_id, "lane_checks": lane_checks, "passes": bool(lane_checks) and all(check["passes"] for check in lane_checks)})
    heldout_seed_count = len(heldout_checks)
    all_heldout_pass = heldout_seed_count >= 3 and all(check["passes"] for check in heldout_checks)
    promotion_status = (
        "eligible_for_manual_implementation_review" if all_heldout_pass
        else "rejected_no_general_rule" if heldout_seed_count >= 3
        else "not_met"
    )
    return {
        "schema": "gamebench.nethack.native_reset_bootstrap_comparison.v1",
        "status": "diagnostic_only",
        "not_a_gold_conformance_score": True,
        "promotion_gate": {
            "status": promotion_status,
            "heldout_source_seed_count": heldout_seed_count,
            "heldout_rule_checks": heldout_checks,
            "requirement": "Promote a terrain/FOV rule only after at least three held-out source seeds preserve or improve both first-divergence timing and visibility errors in every lane, and every reset-hidden negative control passes.",
        },
        "calibration": aggregate(phases["calibration"]),
        "heldout": heldout,
    }


def live_level_dumps(
    initial_observation: dict[str, Any],
    reset_annotations: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    unseen_glyph: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build two reset-causal bootstraps without promoting a future reveal.

    ``observations`` remains an argument so callers can retain a future tape
    for diagnostics, but it must not alter reset state.  In particular, a
    later exposure of the reset hero square is evidence about that later turn,
    not a capture annotation for step one.
    """

    del observations
    task_annotations = deepcopy(reset_annotations)
    return (
        causal_level_dump(initial_observation, task_annotations, unseen_glyph=unseen_glyph),
        causal_level_dump(initial_observation, reset_annotations, unseen_glyph=unseen_glyph),
    )


def capture_case(*, case_index: int, seed: int, character: str, steps: int, campaign: str, table: list[list[Any]], tape: list[int], output: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:
        raise SystemExit("Live NLE fuzzing requires the optional nle==0.9.0 oracle environment. Create the CPython 3.10 dev venv documented in README.md.") from error

    case_seed = seed + case_index
    rng = random.Random(case_seed)
    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        max_episode_steps=max(steps + 1, 100),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        live_table = action_table(env)
        if live_table != table:
            raise RuntimeError("NLE action table drifted from shared/nle_action_map.json; refuse to fuzz against mismatched action ids")
        core_seed, display_seed = deterministic_nle_seeds(case_seed)
        if hasattr(env, "seed"):
            nle_seeds = env.seed(core=core_seed, disp=display_seed, reseed=False)
        else:
            nle_seeds = (core_seed, display_seed, False)
        observation = normalise_reset(env.reset())
        if dungeon_identity(observation) != (0, 1):
            raise RuntimeError(f"live fuzz must start on Main Dungeon dlvl 1, got {dungeon_identity(observation)!r}")
        initial_observation = deepcopy(observation)
        native_reader = PinnedNleMapFovReader(env.nethack)
        native_snapshot = native_reader.snapshot()
        if native_snapshot != native_reader.snapshot():
            raise RuntimeError("native reset map/FOV reader was not read-only/repeatable before action one")
        native_export = native_snapshot.public_record()
        native_layout_controls = native_reader.validate_against_public_pre_action(native_snapshot, initial_observation, nethack)
        capture_runtime = capture_runtime_identity(nle)
        native_pre_action_exporters = NativePreActionExporters.from_env(env)
        native_reset_capture = capture_reset_state(native_pre_action_exporters, observation)
        native_pre_action_records: list[dict[str, Any]] = []
        fixture_id = f"fuzz-case-{case_index:04d}-seed-{case_seed}"
        observations = [deepcopy(observation)]
        unseen_glyph = int(getattr(nethack, "GLYPH_CMAP_OFF", -1))
        known_down_stairs = visible_down_stairs(observation)
        snapshots = [{"step": 0, "projection": project(observation), "inferred_input_mode": inferred_input_mode(observation), "done": False, "terminal_reason": ""}]
        action_records: list[dict[str, Any]] = []
        pending_terminal_operation = ""
        stop_reason = "step_budget"
        for step in range(1, steps + 1):
            input_mode = inferred_input_mode(observation)
            if step <= len(tape):
                action_id = int(tape[step - 1])
                selection = "provided_tape"
                candidates = [action_id]
            else:
                action_id, selection, candidates = choose_campaign_action(campaign, observation, table, rng)
            if not 0 <= action_id < len(table):
                raise ValueError(f"fuzz action {action_id} is outside pinned NLE action table length {len(table)}")
            action_name = str(table[action_id][1])
            known_down_stairs.update(visible_down_stairs(observation))
            pre_action_projection = project(observation)
            source_state = action_source_eligibility(
                action_name,
                observations,
                step=step,
                unseen_glyph=unseen_glyph,
            )
            action_record = {
                "step": step,
                "action_id": action_id,
                "action_name": action_name,
                "input_mode": input_mode,
                "selection": selection,
                "candidates": candidates,
                "nle_stepped": action_name != "MiscDirection.DOWN",
                "source_state_eligibility": source_state,
            }
            if action_name in {"Command.QUIT", "Command.SAVE"}:
                pending_terminal_operation = action_name.rsplit(".", 1)[-1].lower()
                action_record["terminal_prompt_operation"] = pending_terminal_operation
            if action_name == "MiscDirection.DOWN":
                position = hero_position(observation)
                if position not in known_down_stairs:
                    raise RuntimeError("live fuzz refuses DOWN without an earlier raw visible Main Dungeon dlvl-1 stair")
                action_record.update({"boundary": "dlvl1_descend", "observed_down_stair": {"x": position[0], "y": position[1]}})
                native_pre_action_records.append(capture_native_pre_action_record(native_pre_action_exporters, observation, fixture_id=fixture_id, action=action_record, runtime=capture_runtime))
                action_records.append(action_record)
                snapshots.append({"step": step, "projection": pre_action_projection, "inferred_input_mode": input_mode, "done": True, "terminal_reason": "descended", "oracle_boundary": "pre_dlvl2"})
                observations.append(deepcopy(observation))
                stop_reason = "dlvl1_descend"
                break
            native_pre_action_records.append(capture_native_pre_action_record(native_pre_action_exporters, observation, fixture_id=fixture_id, action=action_record, runtime=capture_runtime))
            result = env.step(action_id)
            next_observation, done = normalise_step(result)
            if not done and dungeon_identity(next_observation) != (0, 1):
                raise RuntimeError(f"live fuzz left Main Dungeon dlvl 1 after {action_name}; refuse out-of-scope artifact")
            observation = next_observation
            observations.append(deepcopy(observation))
            known_down_stairs.update(visible_down_stairs(observation))
            action_records.append(action_record)
            terminal_reason = terminal_reason_for_capture(done=done, pending_operation=pending_terminal_operation)
            snapshots.append({"step": step, "projection": project(observation), "inferred_input_mode": inferred_input_mode(observation), "done": done, "terminal_reason": terminal_reason})
            if done or action_name not in {"Command.QUIT", "Command.SAVE"}:
                pending_terminal_operation = ""
            if done:
                stop_reason = "nle_done"
                break
        meta = {
            "schema": "gamebench.nethack.nle_capture.v1",
            "fixture_id": fixture_id,
            "nle_version": getattr(nle, "__version__", "unknown"),
            "nethack_version": "3.6.6",
            "character": {"nle_character": character},
            "seed": case_seed,
            "nle_seeds": {"core": int(nle_seeds[0]), "display": int(nle_seeds[1]), "reseed": bool(nle_seeds[2])},
            "observation_keys": OBSERVATION_KEYS,
            "auto_more": "raw_explicit",
            "action_table": table,
            "action_table_sha256": hashlib.sha256(canonical_json(table).encode("utf-8")).hexdigest(),
            "capture_runtime": capture_runtime,
            "fuzz": {"diagnostic_fuzz": True, "not_a_conformance_pass": True, "campaign": campaign, "requested_steps": steps, "stop_reason": stop_reason},
        }
        annotations = observed_entity_annotations(initial_observation, nethack=nethack)
        # A simulated reset must be derived only from NLE's reset observation.
        # Feeding future snapshots into ``level_dump`` would materialize cells the
        # player has not yet observed; the gold FOV could then reveal that leaked
        # terrain before NLE does.  The tape remains the authoritative source for
        # every later observation, but it is not bootstrap state.
        causal_level, heldout_level = live_level_dumps(
            initial_observation,
            annotations,
            observations,
            unseen_glyph=unseen_glyph,
        )
        task = {
            "task_id": fixture_id,
            "seed": case_seed,
            "character": {"nle_character": character},
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": causal_level,
        }
        task["level_dump"]["authoritative_reset_entities"] = portable_reset_projection(native_reset_capture)
        task["level_dump"]["authoritative_reset_rng"] = portable_reset_rng_projection_from_capture(native_reset_capture)
        if native_reset_capture.get("portable_reset_map") is not None:
            task["level_dump"]["authoritative_reset_map"] = deepcopy(native_reset_capture["portable_reset_map"])
        heldout_task = {
            **task,
            "task_id": f"{fixture_id}-heldout",
            "level_dump": heldout_level,
        }
        if native_reset_capture.get("portable_reset_map") is not None:
            heldout_task["level_dump"]["authoritative_reset_map"] = deepcopy(native_reset_capture["portable_reset_map"])
        native_bootstrap_level = native_bootstrap_level_dump(
            causal_level,
            initial_observation,
            native_export,
            nethack=nethack,
        )
        native_bootstrap_task = {
            **task,
            "task_id": f"{fixture_id}-native-reset-bootstrap",
            "level_dump": native_bootstrap_level,
        }
        if native_reset_capture.get("portable_reset_map") is not None:
            native_bootstrap_task["level_dump"]["authoritative_reset_map"] = deepcopy(native_reset_capture["portable_reset_map"])
        native_negative_controls = native_bootstrap_negative_controls(
            native_bootstrap_task,
            initial_observation,
            native_export,
        )
        native_bootstrap_evidence = {
            "schema": "gamebench.nethack.native_reset_bootstrap_evidence.v1",
            "status": "diagnostic_only",
            "not_a_gold_conformance_lane": True,
            "source_snapshot_boundary": "after reset and before action 1",
            "no_future_source_frames": True,
            "native_layout_controls": native_layout_controls,
            "negative_controls": native_negative_controls,
            "native_export": native_export,
        }
        case_dir = output / "cases" / fixture_id
        write_json(case_dir / "meta.json", meta)
        write_json(case_dir / "level_dump.json", task["level_dump"])
        write_json(case_dir / "heldout_level_dump.json", heldout_task["level_dump"])
        write_json(case_dir / "native_reset_bootstrap_level_dump.json", native_bootstrap_task["level_dump"])
        write_json(case_dir / "native_reset_bootstrap_evidence.json", native_bootstrap_evidence)
        write_jsonl(case_dir / "actions.jsonl", action_records)
        write_jsonl(case_dir / "snapshots.jsonl", snapshots)
        native_failures = validate_native_pre_action_records(native_pre_action_records, action_records, fixture_id=fixture_id, runtime=capture_runtime, require_native=True)
        if native_failures:
            raise RuntimeError("native pre-action evidence validation failed: " + "; ".join(native_failures))
        write_jsonl(case_dir / SIDECAR_FILE, native_pre_action_records)
        reset_entity_record = record_from_reset_capture(
            native_reset_capture,
            fixture_id=fixture_id,
            runtime=capture_runtime,
            level_dump=task["level_dump"],
            actions=action_records,
            reset_projection=snapshots[0]["projection"],
        )
        reset_entity_failures = validate_reset_entity_state(
            reset_entity_record,
            fixture_id=fixture_id,
            runtime=capture_runtime,
            level_dump=task["level_dump"],
            actions=action_records,
            reset_projection=snapshots[0]["projection"],
            require_native=True,
        )
        if reset_entity_failures:
            raise RuntimeError("native reset entity state validation failed: " + "; ".join(reset_entity_failures))
        write_json(case_dir / RESET_ENTITY_SIDECAR_FILE, reset_entity_record)
        return meta, task, heldout_task, native_bootstrap_task, native_bootstrap_evidence, action_records, snapshots, native_pre_action_records
    finally:
        env.close()


def replay_nle_actions(*, seed: int, character: str, table: list[list[Any]], actions: list[dict[str, Any]], fixture_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Repeat an exact source tape to prove the oracle itself is deterministic."""

    import nle
    from nle import nethack

    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        max_episode_steps=max(len(actions) + 1, 100),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        if action_table(env) != table:
            raise RuntimeError("NLE action table drifted during repeatability replay")
        core_seed, display_seed = deterministic_nle_seeds(seed)
        if hasattr(env, "seed"):
            env.seed(core=core_seed, disp=display_seed, reseed=False)
        observation = normalise_reset(env.reset())
        capture_runtime = capture_runtime_identity(nle)
        native_pre_action_exporters = NativePreActionExporters.from_env(env)
        native_records: list[dict[str, Any]] = []
        snapshots = [
            {
                "step": 0,
                "projection": project(observation),
                "inferred_input_mode": inferred_input_mode(observation),
                "done": False,
                "terminal_reason": "",
            }
        ]
        pending_terminal_operation = ""
        for record in actions:
            step = int(record["step"])
            native_records.append(capture_native_pre_action_record(native_pre_action_exporters, observation, fixture_id=fixture_id, action=record, runtime=capture_runtime))
            if record.get("boundary") == "dlvl1_descend":
                snapshots.append(
                    {
                        "step": step,
                        "projection": project(observation),
                        "inferred_input_mode": inferred_input_mode(observation),
                        "done": True,
                        "terminal_reason": "descended",
                        "oracle_boundary": "pre_dlvl2",
                    }
                )
                break
            observation, done = normalise_step(env.step(int(record["action_id"])))
            if not done and dungeon_identity(observation) != (0, 1):
                raise RuntimeError("repeatability replay left Main Dungeon dlvl 1")
            snapshots.append(
                {
                    "step": step,
                    "projection": project(observation),
                    "inferred_input_mode": inferred_input_mode(observation),
                    "done": done,
                    "terminal_reason": terminal_reason_for_capture(
                        done=done,
                        pending_operation=pending_terminal_operation,
                    ),
                }
            )
            if done:
                pending_terminal_operation = ""
                break
            if record.get("action_name") in {"Command.QUIT", "Command.SAVE"}:
                pending_terminal_operation = str(record["action_name"]).rsplit(".", 1)[-1].lower()
            else:
                pending_terminal_operation = ""
        return snapshots, native_records
    finally:
        env.close()


def checkpoint_contract(task: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare uninterrupted traces with Python and Python-to-Rust continuation."""

    action_ids = [int(record["action_id"]) for record in actions]
    cut = max(0, len(action_ids) // 2)
    engine = NethackDlvl1Engine()
    failing_record: dict[str, Any] | None = None
    try:
        engine.reset(resolve_task(task))
        for index, action_id in enumerate(action_ids[:cut]):
            failing_record = actions[index]
            if engine.state["terminated"] or engine.state["truncated"]:
                break
            engine.step(action_id)
    except BaseException as error:
        return {
            "status": "errors_found",
            "cut": cut,
            "comparisons": 0,
            "error_count": 1,
            "errors": [{"lane": "checkpoint", "runtime_error": _runtime_error(failing_record, error)}],
        }
    checkpoint = engine.checkpoint_bytes().decode("utf-8")

    restored_python = NethackDlvl1Engine()
    try:
        restored_python.restore_checkpoint(checkpoint.encode("utf-8"))
        for index, action_id in enumerate(action_ids[cut:], start=cut):
            failing_record = actions[index]
            if restored_python.state["terminated"] or restored_python.state["truncated"]:
                break
            restored_python.step(action_id)
    except BaseException as error:
        return {
            "status": "errors_found",
            "cut": cut,
            "comparisons": 0,
            "error_count": 1,
            "errors": [{"lane": "checkpoint", "runtime_error": _runtime_error(failing_record, error)}],
        }

    direct_python = python_trace(task, actions).snapshots
    python_difference = first_difference(direct_python[-1], restored_python.public_projection())

    try:
        completed = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "--manifest-path",
                str(TASK_DIR / "gold_rust" / "Cargo.toml"),
                "--bin",
                "scenario",
                "--",
                "--checkpoint-replay-stdin",
            ],
            input=json.dumps({"checkpoint": checkpoint, "actions": action_ids[cut:]}),
            text=True,
            capture_output=True,
            check=True,
        )
    except BaseException as error:
        return {
            "status": "errors_found",
            "cut": cut,
            "comparisons": 0,
            "error_count": 1,
            "errors": [{"lane": "checkpoint", "runtime_error": _runtime_error(actions[cut] if cut < len(actions) else None, error)}],
        }
    restored_rust = json.loads(completed.stdout)["projection"]["public"]
    direct_rust = rust_trace(task, actions).snapshots
    rust_difference = first_difference(direct_rust[-1], restored_rust)
    failures = [
        {"lane": "python", **python_difference} if python_difference else None,
        {"lane": "rust", **rust_difference} if rust_difference else None,
    ]
    failures = [failure for failure in failures if failure]
    return {
        "status": "pass" if not failures else "errors_found",
        "cut": cut,
        "comparisons": 2,
        "error_count": len(failures),
        "errors": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=1)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--lane", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--campaign", choices=("navigation-v0", "prompt-probe-v0", "terminal-probe-v0"), default="navigation-v0", help="State-aware action family; supplied --actions always takes priority.")
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--actions", type=Path, default=None, help="Optional JSONL action tape; remaining steps use the selected campaign.")
    parser.add_argument("--output", type=Path, required=True, help="Explicit out-of-tree artifact root; candidate captures are never written to fixtures/nle_oracle.")
    parser.set_defaults(strict_baseline=True)
    parser.add_argument("--strict-baseline", dest="strict_baseline", action="store_true", help="Require exact reset and transition observations (the default).")
    parser.add_argument("--mask-baseline", dest="strict_baseline", action="store_false", help="Diagnostic-only: mask reset mismatches to isolate later transitions.")
    parser.add_argument("--allow-divergences", action="store_true", help="Report diagnostic discrepancies but exit zero after writing artifacts.")
    args = parser.parse_args()
    if args.cases < 1 or args.steps < 1:
        raise SystemExit("--cases and --steps must both be positive")
    output = args.output.resolve()
    if TASK_DIR.resolve() in output.parents or output == TASK_DIR.resolve():
        raise SystemExit("--output must be outside the task directory so fuzz artifacts cannot accidentally enter the canonical corpus")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError as error:
        raise SystemExit("--output must not already exist; fuzz into a new diagnostic directory") from error
    tape = read_actions(args.actions) if args.actions else []
    pinned_table = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())["actions"]
    reports: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    heldout_fixture_ids: set[str] = set()
    for case_index in range(args.cases):
        meta, task, heldout_task, native_bootstrap_task, native_bootstrap_evidence, actions, snapshots, native_pre_action_records = capture_case(case_index=case_index, seed=args.seed, character=args.character, steps=args.steps, campaign=args.campaign, table=pinned_table, tape=tape, output=output)
        expected = [nle_projection(snapshot) for snapshot in snapshots]
        lanes = ("python", "rust") if args.lane == "both" else (args.lane,)
        case_reports: list[dict[str, Any]] = []
        heldout_reports: list[dict[str, Any]] = []
        native_bootstrap_reports: list[dict[str, Any]] = []
        for lane in lanes:
            actual_run = python_trace(task, actions) if lane == "python" else rust_trace(task, actions)
            actual = actual_run.snapshots
            report = lane_report(
                lane,
                expected,
                actual,
                actions,
                strict_baseline=args.strict_baseline,
                oracle_snapshots=snapshots,
                reset_level=task["level_dump"],
                runtime_error=actual_run.runtime_error,
            )
            # Keep this separate from the ordinary reset-only engine trace.
            # It is a tape-oracle diagnostic that admits only frame t-1's
            # static source surface before evaluating action t.
            if actual_run.runtime_error:
                report["prior_source_static_replay_v1"] = {
                    "schema": "gamebench.nethack.prior_source_static_replay.v1",
                    "status": "unavailable_due_runtime_error",
                    "runtime_error": actual_run.runtime_error,
                }
            else:
                report["prior_source_static_replay_v1"] = source_state_replay_report(
                    lane,
                    task,
                    actions,
                    expected,
                    strict_baseline=args.strict_baseline,
                    oracle_snapshots=snapshots,
                )
            case_reports.append(report)
            heldout_run = python_trace(heldout_task, actions) if lane == "python" else rust_trace(heldout_task, actions)
            heldout_actual = heldout_run.snapshots
            heldout_reports.append(
                lane_report(
                    lane,
                    expected,
                    heldout_actual,
                    actions,
                    strict_baseline=args.strict_baseline,
                    oracle_snapshots=snapshots,
                    reset_level=heldout_task["level_dump"],
                    runtime_error=heldout_run.runtime_error,
                )
            )
            native_run = python_trace(native_bootstrap_task, actions) if lane == "python" else rust_trace(native_bootstrap_task, actions)
            native_actual = native_run.snapshots
            native_report = lane_report(
                lane,
                expected,
                native_actual,
                actions,
                strict_baseline=args.strict_baseline,
                oracle_snapshots=snapshots,
                reset_level=native_bootstrap_task["level_dump"],
                runtime_error=native_run.runtime_error,
            )
            native_bootstrap_reports.append(
                {
                    "schema": "gamebench.nethack.native_reset_bootstrap_navigation.v1",
                    "status": "diagnostic_only",
                    "not_a_gold_conformance_lane": True,
                    "source_evidence": {
                        "source_snapshot_boundary": native_bootstrap_evidence["source_snapshot_boundary"],
                        "no_future_source_frames": native_bootstrap_evidence["no_future_source_frames"],
                        "native_layout_controls": native_bootstrap_evidence["native_layout_controls"],
                        "negative_controls": native_bootstrap_evidence["negative_controls"],
                    },
                    "comparison": native_report,
                    "metrics": native_bootstrap_metrics(native_report),
                }
            )
        repeated_snapshots, repeated_native_records = replay_nle_actions(
            seed=int(meta["seed"]),
            character=args.character,
            table=pinned_table,
            actions=actions,
            fixture_id=str(meta["fixture_id"]),
        )
        repeatability_difference = first_difference(snapshots, repeated_snapshots)
        native_repeatability_difference = first_difference(native_pre_action_records, repeated_native_records)
        repeatability = {
            "status": "pass" if repeatability_difference is None else "errors_found",
            "comparison_steps": min(len(snapshots), len(repeated_snapshots)),
            "first_difference": repeatability_difference,
        }
        native_sidecar_repeatability = {
            "status": "pass" if native_repeatability_difference is None else "errors_found",
            "comparison_records": min(len(native_pre_action_records), len(repeated_native_records)),
            "first_difference": native_repeatability_difference,
            "source_evidence_only": True,
            "conformance_denominator_included": False,
        }
        checkpoint = checkpoint_contract(task, actions)
        report = {
            "schema": "gamebench.nethack.live_fuzz_result.v1",
            "diagnostic_fuzz": True,
            "not_a_conformance_pass": True,
            "fixture_id": meta["fixture_id"],
            "artifact": str(output / "cases" / meta["fixture_id"]),
            "lanes": case_reports,
            "heldout_lanes": heldout_reports,
            "native_reset_bootstrap_navigation_v1": native_bootstrap_reports,
            "native_pre_action_evidence_v1": manifest_provenance(native_pre_action_records),
            "native_pre_action_repeatability_v1": native_sidecar_repeatability,
            "oracle_repeatability": repeatability,
            "checkpoint_replay_contract": checkpoint,
        }
        if case_index >= args.cases // 2:
            heldout_fixture_ids.add(str(meta["fixture_id"]))
            report["native_reset_bootstrap_phase"] = "heldout"
        else:
            report["native_reset_bootstrap_phase"] = "calibration"
        write_json(output / "results" / f"{meta['fixture_id']}.json", report)
        reports.append(report)
        cases.append({"meta": meta, "actions": actions, "snapshots": snapshots, "report": report, "native_pre_action_evidence": manifest_provenance(native_pre_action_records)})
    coverage = coverage_report(pinned_table, cases)
    native_bootstrap_summary = native_bootstrap_comparison_summary(reports, heldout_fixture_ids=heldout_fixture_ids)
    write_json(output / "coverage.json", coverage)
    summary = {
        "schema": "gamebench.nethack.live_fuzz_run.v1",
        "diagnostic_fuzz": True,
        "not_a_conformance_pass": True,
        "cases": args.cases,
        "steps": args.steps,
        "seed": args.seed,
        "lane": args.lane,
        "campaign": args.campaign,
        "strict_baseline": args.strict_baseline,
        "coverage": coverage,
        "reports": reports,
        "native_reset_bootstrap_comparison_v1": native_bootstrap_summary,
    }
    write_json(output / "run.json", summary)
    diverged = any(
        lane["bootstrap_masked_transition_v0"]["status"] == "diverged"
        for report in reports
        for lane in report["lanes"]
    )
    print(json.dumps({"status": "diverged" if diverged else "no_new_transition_divergence", "artifact_root": str(output), "cases": args.cases, "lanes": args.lane, "campaign": args.campaign, "distinct_selected_action_ids": coverage["action_ids"]["selected_count"], "distinct_nle_stepped_action_ids": coverage["action_ids"]["nle_stepped_count"], "diagnostic_fuzz": True}, sort_keys=True))
    if diverged and not args.allow_divergences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
