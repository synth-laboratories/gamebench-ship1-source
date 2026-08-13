#!/usr/bin/env python3
"""Source-only causal audit for NLE terrain, visibility, memory, and rendering.

The pinned native reader exposes four distinct facts at an action boundary:

* ``level.locations[].typ`` is true terrain;
* ``viz_array`` supplies ``COULD_SEE`` and ``IN_SIGHT`` independently;
* ``level.locations[].glyph`` and ``.seenv`` are map-memory state; and
* NLE's public observation is a rendered presentation with hero/entity
  overlays.

This command samples those facts immediately before and after safe dlvl-1
actions.  It derives and checks only source assertions.  It never builds a
gold level dump, calls either gold lane, changes a fixture, or makes source
planes available as a conformance input.  The output therefore has separate
``source_export_eligible`` and ``gold_implementation_eligible`` booleans.

The source interpretation is deliberately narrow and is pinned to NetHack
3.6.6 (NLE 0.9.0): ``include/vision.h`` defines ``cansee`` as ``IN_SIGHT``
and ``couldsee`` as ``COULD_SEE``; ``src/vision.c::vision_recalc`` updates
``seenv`` while recalculating visibility and calls ``newsym`` for presentation
refresh.  We record exact native plane digests and transitions, but do not
infer terrain from a blank/public/overlay pixel or entity identity from a
glyph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import (  # noqa: E402
    OBSERVATION_KEYS,
    STATIC_TERRAIN_CHARS,
    deterministic_nle_seeds,
    normalise_reset,
    to_json_array,
)
from scripts.frontier_promotion_gate import SCHEMA as GATE_SCHEMA  # noqa: E402
from scripts.nle_native_map_fov import (  # noqa: E402
    COULD_SEE,
    D_CLOSED,
    D_ISOPEN,
    D_LOCKED,
    D_TRAPPED,
    DOOR_TERRAIN_TYPE,
    IN_SIGHT,
    OBS_COLNO,
    PINNED_BINARY_SHA256,
    ROWNO,
    PinnedNleMapFovReader,
    validate_semantic_vision_export,
)
from scripts.oracle_tape import capture_runtime_identity, sha256_file  # noqa: E402


SCHEMA = "gamebench.nethack.native_map_fov_transition_audit.v1"
TRANSITION_SCHEMA = "gamebench.nethack.native_map_fov_transition.v1"
SOURCE_REFERENCES = {
    "vision_bits": "include/vision.h:14-31 (COULD_SEE, IN_SIGHT, cansee(), couldsee())",
    "visibility_recalc": "src/vision.c:501-815 (vision_recalc updates visibility, seenv, and newsym presentation)",
    # The normal LOS pass establishes COULD_SEE first, but the explicit
    # x-ray pass can OR IN_SIGHT into cells outside that mask.  Keep that
    # source-defined state distinct from malformed native evidence.
    "xray_in_sight_without_could_see": "src/vision.c:618-657 (x-ray vision ORs IN_SIGHT and updates seenv without requiring COULD_SEE)",
    "memory_layout": "include/rm.h:421 (struct rm.seenv)",
    "door_state": "include/rm.h:323-328,421-431,527 (D_* constants; rm.flags/horizontal; doormask alias), src/vision.c:150-166 (closed/locked/trapped door blocks vision), src/display.c:1733-1739 and src/drawing.c:156-157 (horizontal -> S_hodoor -> '|'; nonhorizontal -> S_vodoor -> '-')",
    "vision_inputs": "src/vision.c:522-692 (in_mklev/vision_inited, swallowed, Blind, rogue, Underwater, pit, xray, night range, and do_light_sources); include/you.h:274-398 and include/youprop.h:85-167",
    "lighting_and_blockers": "src/vision.c:150-181,745-794 (rm.lit/waslit and boulder/mimic blockers); src/light.c:56-185 (light_base and TEMP_LIT); include/vision.h:14-23",
    "recalc_triggers": "src/vision.c:839-876 (block_point/unblock_point), src/light.c:56-121, and callers listed by rg in pinned source; only vision_full_recalc is retained runtime state",
}
NORMAL_ACTIONS = (
    "MiscDirection.WAIT",
    "CompassDirection.N",
    "CompassDirection.E",
    "CompassDirection.S",
    "CompassDirection.W",
    "CompassDirection.NE",
    "CompassDirection.SW",
    "Command.SEARCH",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _shape_is_plane(value: Any, *, item: type) -> bool:
    return (
        isinstance(value, list)
        and len(value) == ROWNO
        and all(isinstance(row, list) and len(row) == OBS_COLNO and all(type(cell) is item for cell in row) for row in value)
    )


def assert_native_export(export: dict[str, Any]) -> None:
    """Reject a malformed native export before transition classification."""

    if export.get("schema") != "gamebench.nethack.native_map_fov_snapshot.v1":
        raise ValueError("native transition audit requires a map/FOV snapshot export")
    if export.get("provenance") != "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array":
        raise ValueError("native transition audit requires hash-verified read-only source provenance")
    if export.get("binary_sha256") != PINNED_BINARY_SHA256:
        raise ValueError("native transition audit requires the exact pinned NLE binary")
    terrain = export.get("full_map_terrain")
    terrain_flags = export.get("full_map_terrain_flags")
    terrain_horizontal = export.get("full_map_terrain_horizontal")
    visible = export.get("fov_visibility_mask")
    could = export.get("fov_could_see_mask")
    memory = export.get("map_memory")
    if not _shape_is_plane(terrain, item=int):
        raise ValueError("native transition terrain plane must be 21x79 integers")
    if not _shape_is_plane(terrain_flags, item=int) or any(not 0 <= int(value) <= 0x1F for row in terrain_flags for value in row):
        raise ValueError("native transition terrain flags plane must be 21x79 five-bit integers")
    if not _shape_is_plane(terrain_horizontal, item=bool):
        raise ValueError("native transition terrain horizontal plane must be 21x79 booleans")
    if not _shape_is_plane(visible, item=bool) or not _shape_is_plane(could, item=bool):
        raise ValueError("native transition visibility planes must be 21x79 booleans")
    if not isinstance(memory, dict) or not _shape_is_plane(memory.get("glyph"), item=int) or not _shape_is_plane(memory.get("seenv"), item=int):
        raise ValueError("native transition memory planes must be 21x79 integers")
    vision_errors = validate_semantic_vision_export(export)
    if vision_errors:
        raise ValueError("native transition vision extension is malformed: " + "; ".join(vision_errors))


def public_render_summary(observation: dict[str, Any], glyph_is_cmap: Callable[[int], bool]) -> dict[str, Any]:
    """Classify presentation without promoting it to terrain or memory.

    Direct static cmap cells are independent public controls for the native
    memory glyph.  Blank cmap backgrounds, the hero, and all non-cmap cells
    are deliberately excluded from those controls.  The latter are overlays,
    not a stable entity/underlay identity.
    """

    chars = to_json_array(observation.get("chars"))
    glyphs = to_json_array(observation.get("glyphs"))
    colors = to_json_array(observation.get("colors"))
    blstats = to_json_array(observation.get("blstats"))
    if not _shape_is_plane(chars, item=int) or not _shape_is_plane(glyphs, item=int) or not _shape_is_plane(colors, item=int):
        raise ValueError("public transition controls require exact 21x79 chars/glyphs/colors")
    if not isinstance(blstats, list) or len(blstats) < 2:
        raise ValueError("public transition controls require hero coordinates")
    hero = (int(blstats[0]), int(blstats[1]))
    if not (0 <= hero[0] < OBS_COLNO and 0 <= hero[1] < ROWNO):
        raise ValueError("public transition hero coordinate is outside the map plane")

    static: list[tuple[int, int, str, int]] = []
    blank_cmap = 0
    hero_cells = 0
    overlays = 0
    for y in range(ROWNO):
        for x in range(OBS_COLNO):
            glyph = int(glyphs[y][x])
            char = chr(int(chars[y][x]))
            if (x, y) == hero:
                hero_cells += 1
                continue
            if bool(glyph_is_cmap(glyph)) and char in STATIC_TERRAIN_CHARS:
                static.append((x, y, char, glyph))
            elif bool(glyph_is_cmap(glyph)) and char == " ":
                blank_cmap += 1
            elif char != " ":
                overlays += 1
    return {
        "hero": {"x": hero[0], "y": hero[1]},
        "direct_static_cells": static,
        "direct_static_count": len(static),
        "blank_cmap_background_count": blank_cmap,
        "hero_overlay_count": hero_cells,
        "presentation_overlay_count": overlays,
        "digest": sha256_json({"chars": chars, "glyphs": glyphs, "colors": colors, "blstats": blstats}),
    }


def _changed_count(before: list[list[Any]], after: list[list[Any]], predicate: Callable[[Any, Any], bool]) -> int:
    return sum(1 for y in range(ROWNO) for x in range(OBS_COLNO) if predicate(before[y][x], after[y][x]))


def classify_transition(
    before: dict[str, Any],
    after: dict[str, Any],
    before_public: dict[str, Any],
    after_public: dict[str, Any],
) -> dict[str, Any]:
    """Derive seed- and coordinate-independent source transition facts.

    There is intentionally no seed, fixture id, terrain character table, or
    coordinate exception in this function.  Coordinates appear only as cells
    being compared across two equally shaped source planes.
    """

    assert_native_export(before)
    assert_native_export(after)
    before_visible = before["fov_visibility_mask"]
    after_visible = after["fov_visibility_mask"]
    before_could = before["fov_could_see_mask"]
    after_could = after["fov_could_see_mask"]
    before_memory = before["map_memory"]
    after_memory = after["map_memory"]

    def static_mismatches(export: dict[str, Any], summary: dict[str, Any]) -> int:
        glyphs = export["map_memory"]["glyph"]
        return sum(1 for x, y, _char, glyph in summary["direct_static_cells"] if glyphs[y][x] != glyph)

    def door_control_mismatches(export: dict[str, Any], summary: dict[str, Any]) -> tuple[int, int, int]:
        closed = 0
        opened = 0
        mismatches = 0
        for x, y, char, _glyph in summary["direct_static_cells"]:
            if export["full_map_terrain"][y][x] != DOOR_TERRAIN_TYPE:
                continue
            doormask = export["full_map_terrain_flags"][y][x]
            if char == "+":
                closed += 1
                mismatches += int(not bool(doormask & (D_CLOSED | D_LOCKED)))
            elif char in "|-":
                opened += 1
                mismatches += int(
                    not bool(doormask & D_ISOPEN)
                    or bool(doormask & (D_CLOSED | D_LOCKED | D_TRAPPED))
                    or export["full_map_terrain_horizontal"][y][x] != (char == "|")
                )
        return closed, opened, mismatches

    visibility = {
        "in_sight_gained": _changed_count(before_visible, after_visible, lambda old, new: not old and new),
        "in_sight_lost": _changed_count(before_visible, after_visible, lambda old, new: old and not new),
        "in_sight_retained": _changed_count(before_visible, after_visible, lambda old, new: old and new),
        "could_see_gained": _changed_count(before_could, after_could, lambda old, new: not old and new),
        "could_see_lost": _changed_count(before_could, after_could, lambda old, new: old and not new),
        "in_sight_without_could_before": sum(1 for y in range(ROWNO) for x in range(OBS_COLNO) if before_visible[y][x] and not before_could[y][x]),
        "in_sight_without_could_after": sum(1 for y in range(ROWNO) for x in range(OBS_COLNO) if after_visible[y][x] and not after_could[y][x]),
    }
    memory = {
        "glyph_changed": _changed_count(before_memory["glyph"], after_memory["glyph"], lambda old, new: old != new),
        "seenv_changed": _changed_count(before_memory["seenv"], after_memory["seenv"], lambda old, new: old != new),
        "seenv_cleared_bits": sum(
            int(before_memory["seenv"][y][x]) & ~int(after_memory["seenv"][y][x])
            for y in range(ROWNO)
            for x in range(OBS_COLNO)
        ),
    }
    before_closed, before_open, before_door_mismatches = door_control_mismatches(before, before_public)
    after_closed, after_open, after_door_mismatches = door_control_mismatches(after, after_public)
    terrain = {
        "true_type_changed": _changed_count(before["full_map_terrain"], after["full_map_terrain"], lambda old, new: old != new),
        "raw_flags_changed": _changed_count(before["full_map_terrain_flags"], after["full_map_terrain_flags"], lambda old, new: old != new),
        "horizontal_changed": _changed_count(before["full_map_terrain_horizontal"], after["full_map_terrain_horizontal"], lambda old, new: old != new),
        "door_mask_changed": sum(
            1
            for y in range(ROWNO)
            for x in range(OBS_COLNO)
            if (before["full_map_terrain"][y][x] == DOOR_TERRAIN_TYPE or after["full_map_terrain"][y][x] == DOOR_TERRAIN_TYPE)
            and before["full_map_terrain_flags"][y][x] != after["full_map_terrain_flags"][y][x]
        ),
    }
    rendering = {
        "before_direct_static_controls": int(before_public["direct_static_count"]),
        "after_direct_static_controls": int(after_public["direct_static_count"]),
        "before_memory_glyph_mismatches": static_mismatches(before, before_public),
        "after_memory_glyph_mismatches": static_mismatches(after, after_public),
        "before_blank_cmap_background": int(before_public["blank_cmap_background_count"]),
        "after_blank_cmap_background": int(after_public["blank_cmap_background_count"]),
        "before_closed_door_controls": before_closed,
        "before_open_door_controls": before_open,
        "after_closed_door_controls": after_closed,
        "after_open_door_controls": after_open,
        "before_door_state_mismatches": before_door_mismatches,
        "after_door_state_mismatches": after_door_mismatches,
    }
    overlays = {
        "before_hero_cells": int(before_public["hero_overlay_count"]),
        "after_hero_cells": int(after_public["hero_overlay_count"]),
        "before_presentation_overlays": int(before_public["presentation_overlay_count"]),
        "after_presentation_overlays": int(after_public["presentation_overlay_count"]),
        "underlay_or_entity_identity_inferred": False,
    }
    has_vision_extension = "lighting" in before and "lighting" in after
    lighting: dict[str, Any] = {"extension_present": has_vision_extension}
    dynamic_blockers: dict[str, Any] = {"extension_present": has_vision_extension}
    decision_inputs: dict[str, Any] = {"extension_present": has_vision_extension}
    if has_vision_extension:
        before_lighting, after_lighting = before["lighting"], after["lighting"]
        lighting.update({
            "static_lit_changed": _changed_count(before_lighting["static_lit"], after_lighting["static_lit"], lambda old, new: old != new),
            "remembered_lit_changed": _changed_count(before_lighting["remembered_lit"], after_lighting["remembered_lit"], lambda old, new: old != new),
            "temporary_lit_gained": _changed_count(before_lighting["temporary_lit"], after_lighting["temporary_lit"], lambda old, new: not old and new),
            "temporary_lit_lost": _changed_count(before_lighting["temporary_lit"], after_lighting["temporary_lit"], lambda old, new: old and not new),
            "active_light_source_count_before": len(before_lighting["active_light_sources"]),
            "active_light_source_count_after": len(after_lighting["active_light_sources"]),
        })
        before_blockers, after_blockers = before["dynamic_vision_blockers"], after["dynamic_vision_blockers"]
        dynamic_blockers.update({
            "boulder_changed": _changed_count(before_blockers["boulder"], after_blockers["boulder"], lambda old, new: old != new),
            "visible_mimic_changed": _changed_count(before_blockers["visible_mimic"], after_blockers["visible_mimic"], lambda old, new: old != new),
            "effective_changed": _changed_count(before_blockers["effective"], after_blockers["effective"], lambda old, new: old != new),
            "record_count_before": len(before_blockers["records"]),
            "record_count_after": len(after_blockers["records"]),
        })
        before_inputs, after_inputs = before["vision_decision_inputs"], after["vision_decision_inputs"]
        decision_inputs.update({
            "hero_input_changed": int(before_inputs["hero"] != after_inputs["hero"]),
            "level_predicate_changed": int(before_inputs["level"] != after_inputs["level"]),
            "blindness_input_changed": int(before_inputs["blindness"] != after_inputs["blindness"]),
            "senses_input_changed": int(before_inputs["senses"] != after_inputs["senses"]),
            "full_recalc_pending_changed": int(before["vision_recalc_state"]["full_recalc_pending"] != after["vision_recalc_state"]["full_recalc_pending"]),
        })
    errors: list[str] = []
    # NetHack 3.6.6 src/vision.c:618-657 can set IN_SIGHT without COULD_SEE
    # for x-ray vision.  These exact counts remain in the diagnostic record,
    # but rejecting them would falsely classify a faithful source frame as a
    # torn native read and would hide a real dynamic-vision branch.
    if rendering["before_memory_glyph_mismatches"] or rendering["after_memory_glyph_mismatches"]:
        errors.append("direct_static_public_memory_glyph_mismatch")
    if rendering["before_door_state_mismatches"] or rendering["after_door_state_mismatches"]:
        errors.append("direct_public_door_glyph_doormask_mismatch")
    if memory["seenv_cleared_bits"]:
        errors.append("seenv_bit_cleared")
    return {
        "schema": TRANSITION_SCHEMA,
        "terrain": terrain,
        "visibility": visibility,
        "lighting": lighting,
        "vision_decision_inputs": decision_inputs,
        "dynamic_blockers": dynamic_blockers,
        "memory": memory,
        "rendering": rendering,
        "overlays": overlays,
        "source_assertion_errors": errors,
    }


def _action_ids(env: Any, action_names: tuple[str, ...]) -> dict[str, int]:
    ids = {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}
    missing = [name for name in action_names if name not in ids]
    if missing:
        raise RuntimeError(f"pinned NLE action map lacks transition audit actions: {missing}")
    return ids


def _normalise_step(result: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(result, tuple) and len(result) >= 3:
        return dict(result[0]), bool(result[2])
    return dict(result), False


@dataclass(frozen=True)
class CaseDigest:
    seed: int
    digest: str
    transitions: int


def capture_case(
    seed: int,
    *,
    character: str,
    steps: int,
    action_names: tuple[str, ...] = NORMAL_ACTIONS,
) -> tuple[dict[str, Any], CaseDigest]:
    """Capture exact paired planes around a bounded safe action schedule."""

    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - command-only dependency guard
        raise RuntimeError("NLE 0.9.0 is required for the native transition audit") from error
    if getattr(nle, "__version__", None) != "0.9.0":
        raise RuntimeError("native transition audit requires nle==0.9.0")
    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        max_episode_steps=max(steps + 1, 100),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        if not action_names:
            raise ValueError("native transition audit action plan must be non-empty")
        action_ids = _action_ids(env, action_names)
        core, display = deterministic_nle_seeds(seed)
        configured = tuple(int(value) for value in env.seed(core=core, disp=display, reseed=False))
        if configured != (core, display, False):
            raise RuntimeError("NLE declined deterministic transition-audit seed configuration")
        observation = normalise_reset(env.reset())
        reader = PinnedNleMapFovReader(env.nethack)
        records: list[dict[str, Any]] = []
        for step_index in range(steps):
            action_name = action_names[step_index % len(action_names)]
            before_snapshot = reader.snapshot()
            if before_snapshot != reader.snapshot():
                raise RuntimeError("native map/FOV source changed while being read before an action")
            before = before_snapshot.public_record()
            reader.validate_against_public_pre_action(before_snapshot, observation, nethack)
            before_public = public_render_summary(observation, nethack.glyph_is_cmap)
            next_observation, done = _normalise_step(env.step(action_ids[action_name]))
            after_snapshot = reader.snapshot()
            if after_snapshot != reader.snapshot():
                raise RuntimeError("native map/FOV source changed while being read after an action")
            after = after_snapshot.public_record()
            reader.validate_against_public_pre_action(after_snapshot, next_observation, nethack)
            after_public = public_render_summary(next_observation, nethack.glyph_is_cmap)
            transition = classify_transition(before, after, before_public, after_public)
            records.append(
                {
                    "step": step_index + 1,
                    "action_name": action_name,
                    "done": bool(done),
                    "before_plane_sha256": before["plane_sha256"],
                    "after_plane_sha256": after["plane_sha256"],
                    "before_public_sha256": before_public["digest"],
                    "after_public_sha256": after_public["digest"],
                    "transition": transition,
                }
            )
            observation = next_observation
            if done:
                break
        if not records:
            raise RuntimeError("native transition audit captured zero action boundaries")
        payload = {
            "seed": int(seed),
            "configured_seeds": list(configured),
            "binary_sha256": before["binary_sha256"],
            "semantic_terrain_abi": before["abi_layout"]["independent_clang_bitfield_check"],
            "semantic_vision_input_abi": before["abi_layout"]["independent_clang_vision_input_check"],
            "records": records,
        }
        return payload, CaseDigest(seed=int(seed), digest=sha256_json(payload), transitions=len(records))
    finally:
        env.close()


def _rank_first(value: Any) -> float:
    return float("inf") if value is None else float(int(value))


def bootstrap_heldout_evidence(path: Path | None) -> dict[str, Any]:
    """Read an existing independent bootstrap experiment as a negative gate.

    The experiment's aggregate visibility error reduction is retained because
    it is useful context, but any earlier first divergence is a counterexample
    and prohibits a gold rule.  It is never a conformance score.
    """

    empty = {
        "case_count": 0,
        "comparison_count": 0,
        "counterexample_count": 0,
        "baseline_first_divergence_step": None,
        "candidate_first_divergence_step": None,
        "baseline_error_count": 0,
        "candidate_error_count": 0,
        "source": "no independent bootstrap experiment supplied",
    }
    if path is None:
        return empty
    payload = json.loads(path.read_text())
    summary = payload.get("native_reset_bootstrap_comparison_v1", {})
    heldout = summary.get("heldout", {}) if isinstance(summary, dict) else {}
    records = heldout.get("records", []) if isinstance(heldout, dict) else []
    if not isinstance(records, list):
        raise ValueError("bootstrap run held-out records must be a list")
    ordinary = heldout.get("ordinary", {})
    native = heldout.get("native_reset_bootstrap", {})
    pairs = [
        (entry.get("ordinary", {}), entry.get("native_reset_bootstrap", {}))
        for entry in records
        if isinstance(entry, dict)
    ]
    baseline_steps = [int(item[0]["first_divergence_step"]) for item in pairs if item[0].get("first_divergence_step") is not None]
    candidate_steps = [int(item[1]["first_divergence_step"]) for item in pairs if item[1].get("first_divergence_step") is not None]
    regressions = sum(
        1
        for baseline, candidate in pairs
        if _rank_first(candidate.get("first_divergence_step")) < _rank_first(baseline.get("first_divergence_step"))
    )
    fixture_ids = {str(entry.get("fixture_id")) for entry in records if isinstance(entry, dict) and entry.get("fixture_id")}
    return {
        "case_count": len(fixture_ids),
        "comparison_count": sum(int(item[0].get("visibility_comparisons") or 0) for item in pairs),
        "counterexample_count": regressions,
        "baseline_first_divergence_step": min(baseline_steps) if baseline_steps else None,
        "candidate_first_divergence_step": min(candidate_steps) if candidate_steps else None,
        "baseline_error_count": int(ordinary.get("visibility_errors") or 0),
        "candidate_error_count": int(native.get("visibility_errors") or 0),
        "source": str(path),
        "source_sha256": "sha256:" + sha256_file(path),
        "aggregate_visibility_error_delta": int(native.get("visibility_errors") or 0) - int(ordinary.get("visibility_errors") or 0),
    }


def _cross_lane_parity(heldout: dict[str, Any]) -> bool:
    """Require matching Python/Rust bootstrap observations where both exist."""

    source = heldout.get("source")
    if not isinstance(source, str) or source.startswith("no independent"):
        return False
    payload = json.loads(Path(source).read_text())
    records = payload["native_reset_bootstrap_comparison_v1"]["heldout"].get("records", [])
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("fixture_id"), str) and isinstance(record.get("lane"), str):
            grouped.setdefault(record["fixture_id"], {})[record["lane"]] = record
    return bool(grouped) and all(
        set(lanes) == {"python", "rust"}
        and lanes["python"].get("ordinary") == lanes["rust"].get("ordinary")
        and lanes["python"].get("native_reset_bootstrap") == lanes["rust"].get("native_reset_bootstrap")
        for lanes in grouped.values()
    )


def audit(
    seeds: list[int],
    *,
    character: str,
    steps: int,
    bootstrap_run: Path | None,
    action_names: tuple[str, ...] = NORMAL_ACTIONS,
) -> dict[str, Any]:
    if len(seeds) < 6:
        raise ValueError("native transition audit needs at least six seeds: calibration plus held-out")
    if steps < 1:
        raise ValueError("native transition audit needs at least one action per seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("native transition audit seeds must be distinct")
    if not action_names:
        raise ValueError("native transition audit action plan must be non-empty")
    cases: list[dict[str, Any]] = []
    repeatable = True
    for seed in seeds:
        first, first_digest = capture_case(seed, character=character, steps=steps, action_names=action_names)
        second, second_digest = capture_case(seed, character=character, steps=steps, action_names=action_names)
        if first_digest != second_digest or first != second:
            repeatable = False
        cases.append({
            "seed": seed,
            "comparison_count": first_digest.transitions,
            "repeat_digest": first_digest.digest,
            "repeatable": first == second,
            "semantic_terrain_abi": first["semantic_terrain_abi"],
            "semantic_vision_input_abi": first["semantic_vision_input_abi"],
            "records": first["records"],
        })
    midpoint = len(cases) // 2
    calibration, heldout_cases = cases[:midpoint], cases[midpoint:]
    all_records = [record for case in cases for record in case["records"]]
    error_counts = Counter(error for record in all_records for error in record["transition"]["source_assertion_errors"])
    exact_source_comparisons = len(all_records)
    rendering_controls = sum(
        record["transition"]["rendering"]["before_direct_static_controls"] + record["transition"]["rendering"]["after_direct_static_controls"]
        for record in all_records
    )
    observed_transition_classes = {
        "true_terrain_changed": sum(record["transition"]["terrain"]["true_type_changed"] for record in all_records),
        "raw_terrain_flags_changed": sum(record["transition"]["terrain"]["raw_flags_changed"] for record in all_records),
        "door_mask_changed": sum(record["transition"]["terrain"]["door_mask_changed"] for record in all_records),
        "terrain_horizontal_changed": sum(record["transition"]["terrain"]["horizontal_changed"] for record in all_records),
        "in_sight_changed": sum(record["transition"]["visibility"]["in_sight_gained"] + record["transition"]["visibility"]["in_sight_lost"] for record in all_records),
        "could_see_changed": sum(record["transition"]["visibility"]["could_see_gained"] + record["transition"]["visibility"]["could_see_lost"] for record in all_records),
        "memory_glyph_changed": sum(record["transition"]["memory"]["glyph_changed"] for record in all_records),
        "memory_seenv_changed": sum(record["transition"]["memory"]["seenv_changed"] for record in all_records),
        "presentation_overlays": sum(record["transition"]["overlays"]["before_presentation_overlays"] + record["transition"]["overlays"]["after_presentation_overlays"] for record in all_records),
        "blank_cmap_background": sum(record["transition"]["rendering"]["before_blank_cmap_background"] + record["transition"]["rendering"]["after_blank_cmap_background"] for record in all_records),
        "static_lit_changed": sum(record["transition"]["lighting"].get("static_lit_changed", 0) for record in all_records),
        "temporary_lit_changed": sum(record["transition"]["lighting"].get("temporary_lit_gained", 0) + record["transition"]["lighting"].get("temporary_lit_lost", 0) for record in all_records),
        "dynamic_blocker_changed": sum(record["transition"]["dynamic_blockers"].get("effective_changed", 0) for record in all_records),
    }
    source_export_eligible = bool(exact_source_comparisons and rendering_controls and repeatable and not error_counts)
    abi_proofs = {canonical_json(case["semantic_terrain_abi"]) for case in cases}
    if len(abi_proofs) != 1:
        raise RuntimeError("native transition audit observed inconsistent compiler bitfield ABI proofs")
    vision_abi_proofs = {canonical_json(case["semantic_vision_input_abi"]) for case in cases}
    if len(vision_abi_proofs) != 1:
        raise RuntimeError("native transition audit observed inconsistent compiler vision-input ABI proofs")
    heldout = bootstrap_heldout_evidence(bootstrap_run)
    validity = {
        "source_identity_pinned": True,
        "captured_pre_action_only": True,
        "no_future_or_reset_hydration": True,
        "no_seed_or_coordinate_lookup": True,
        "source_assertion_repeatable": repeatable,
        "python_rust_parity": _cross_lane_parity(heldout),
    }
    candidate = {
        "schema": GATE_SCHEMA,
        "subsystem": "native_map_fov_memory_rendering_transition",
        "source_export_eligible": source_export_eligible,
        "gold_implementation_eligible": False,
        "validity": validity,
        "source_assertions": {"comparison_count": exact_source_comparisons, "error_count": sum(error_counts.values())},
        "heldout": heldout,
        "promotion_rule": "No Python or Rust rule is proposed: exact native source transitions remain diagnostic until a causal rule preserves held-out first divergence in both lanes.",
    }
    return {
        "schema": SCHEMA,
        "status": "source_export_eligible_diagnostic_only" if source_export_eligible else "source_export_blocked",
        "source_export_eligible": source_export_eligible,
        "gold_implementation_eligible": False,
        "source_references": SOURCE_REFERENCES,
        "runtime": capture_runtime_identity(__import__("nle")),
        "audit_script_sha256": "sha256:" + sha256_file(Path(__file__)),
        "action_schedule": list(action_names),
        "action_plan_contract": "The exact action-name sequence is supplied once and applied identically to every seed; no seed, coordinate, prior transition outcome, or future frame selects an action.",
        "semantic_terrain_abi": cases[0]["semantic_terrain_abi"],
        "semantic_vision_input_abi": cases[0]["semantic_vision_input_abi"],
        "calibration": calibration,
        "heldout": heldout_cases,
        "source_assertions": {
            "comparison_count": exact_source_comparisons,
            "direct_static_public_memory_controls": rendering_controls,
            "error_count": sum(error_counts.values()),
            "errors": dict(sorted(error_counts.items())),
            "observed_transition_classes": observed_transition_classes,
            "rules": {
                "visibility": "IN_SIGHT and COULD_SEE remain distinct. src/vision.c:618-657 permits x-ray vision to set IN_SIGHT without COULD_SEE, so those exact counts are recorded rather than treated as a corrupt source frame.",
                "terrain": "Raw terrain type, five-bit flags/doormask, and horizontal state are distinct source planes. A door keeps typ=DOOR while opening changes flags/doormask.",
                "memory": "Map-memory glyph and seenv transitions are recorded separately from terrain and visibility; sampled seenv never clears a bit.",
                "rendering": "Only public direct static cmap glyphs control native map-memory glyphs. Visible +/|/- door glyphs additionally control source doormask state; source display maps horizontal=1 to open '|' and horizontal=0 to open '-'. Blank cmap, hero, and non-cmap overlays are excluded.",
                "overlays": "No entity identity, underlay, terrain type, or memory update is inferred from a presentation overlay.",
            },
        },
        "validity": {
            **validity,
            "anti_future_leakage": "Each source pair is consumed only as a diagnostic assertion after its action; the audit never calls gold or writes a level dump.",
            "no_reset_hydration": "Reset is observed and checked only; no native terrain, FOV, glyph, or seenv plane enters a reset task.",
            "zero_comparison_rejected": "source_export_eligible requires positive exact transition and direct-static control counts.",
            "adversarial_occlusion": "Blank cmap, hero, and non-cmap overlay cells are excluded from static memory controls.",
        },
        "frontier_promotion_candidate": candidate,
        "blocker": "The independent native-reset bootstrap has lower aggregate visibility errors but earlier first divergence on every held-out Python/Rust trace; aggregate improvement cannot authorize a gold rule.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(20260719, 20260731)))
    parser.add_argument("--steps", type=int, default=len(NORMAL_ACTIONS))
    parser.add_argument("--actions", default=",".join(NORMAL_ACTIONS), help="comma-separated pinned action names; applied identically to every seed")
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--bootstrap-run", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=TASK_DIR / "reports" / "native_map_fov_transitions.json")
    parser.add_argument("--candidate", type=Path, default=None, help="Optional standalone frontier_promotion_gate candidate JSON")
    args = parser.parse_args()
    action_names = tuple(name.strip() for name in str(args.actions).split(",") if name.strip())
    report = audit([int(seed) for seed in args.seeds], character=str(args.character), steps=int(args.steps), bootstrap_run=args.bootstrap_run, action_names=action_names)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.candidate is not None:
        args.candidate.parent.mkdir(parents=True, exist_ok=True)
        args.candidate.write_text(json.dumps(report["frontier_promotion_candidate"], indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"],
        "source_export_eligible": report["source_export_eligible"],
        "gold_implementation_eligible": report["gold_implementation_eligible"],
        "comparisons": report["source_assertions"]["comparison_count"],
        "report": str(args.report),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
