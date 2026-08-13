#!/usr/bin/env python3
"""Audit whether pinned NLE exposes an authoritative pre-action map/FOV API.

This is an authority probe, deliberately separate from the gold emulator and
from the diagnostic prior-source-static replay lane.  A rendered
``glyphs/chars/colors/specials`` frame is valuable evidence of *what was
presented* at an action boundary, but it is not by itself a full level
serialization, an FOV mask, or an underlay export.  In particular, blank map
cells are rendered as the cmap background glyph, so treating every cmap glyph
as known terrain would manufacture an unseen map.

The audit first records that public limitation, then uses the exact
hash-verified pinned macOS binary's local ``level`` and ``viz_array`` symbols
through a strictly read-only ctypes reader.  It retains only reset/pre-action
source records.  A one-step observation is captured solely as a held-out
repeatability control and is never used to hydrate or justify the pre-action
export.

Exit status is intentionally successful when the runtime is repeatable but
does not provide a verified full-map/FOV contract: that is a concrete, valid
blocker.  It exits nonzero if the pinned API shape, native binary, layout, or
repeatability premise changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import deterministic_nle_seeds, to_json_array
from scripts.nle_native_map_fov import PinnedNleMapFovReader
from scripts.oracle_tape import capture_runtime_identity, sha256_file


PINNED_NLE_VERSION = "0.9.0"
# ``rm.typ`` alone is not semantic terrain for doors: vision.c::does_block
# consults rm.doormask (the rm.flags bitfield), and horizontal selects the
# rendered open-door orientation.  A full terrain/FOV source export therefore
# needs all three terrain-state planes as well as visibility and memory.
REQUIRED_FULL_MAP_FOV_FIELDS = frozenset((
    "full_map_terrain",
    "full_map_terrain_flags",
    "full_map_terrain_horizontal",
    "fov_visibility_mask",
    "map_memory",
))
EXPECTED_OBSERVATION_SHAPES = {
    "glyphs": (21, 79),
    "chars": (21, 79),
    "colors": (21, 79),
    "specials": (21, 79),
    "blstats": (27,),
    "message": (256,),
    "program_state": (6,),
    "internal": (9,),
    "inv_glyphs": (55,),
    "inv_letters": (55,),
    "inv_oclasses": (55,),
    "inv_strs": (55, 80),
    "screen_descriptions": (21, 79, 80),
    "tty_chars": (24, 80),
    "tty_colors": (24, 80),
    "tty_cursor": (2,),
    "misc": (3,),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _shape(value: Any) -> tuple[int, ...]:
    shape = getattr(value, "shape", None)
    if not isinstance(shape, tuple):
        raise ValueError("NLE observation lacks an ndarray shape")
    return tuple(int(part) for part in shape)


def assert_pinned_schema(observation_desc: dict[str, Any]) -> None:
    """Fail hard on an API change rather than assuming it remains non-authoritative."""

    actual = set(observation_desc)
    expected = set(EXPECTED_OBSERVATION_SHAPES)
    if actual != expected:
        raise AssertionError(
            "pinned NLE observation keys changed; re-audit full-map/FOV authority: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    for key, expected_shape in EXPECTED_OBSERVATION_SHAPES.items():
        shape = tuple(int(part) for part in observation_desc[key]["shape"])
        if shape != expected_shape:
            raise AssertionError(f"NLE observation {key!r} shape changed: {shape!r} != {expected_shape!r}")


def _map_surface_summary(observation: dict[str, Any], nethack: Any) -> dict[str, Any]:
    """Summarize one *current* rendered map without exporting inferred terrain."""

    glyphs = observation.get("glyphs")
    chars = observation.get("chars")
    colors = observation.get("colors")
    specials = observation.get("specials")
    if any(value is None for value in (glyphs, chars, colors, specials)):
        raise AssertionError("requested rendered map plane is absent")
    for key, value in (("glyphs", glyphs), ("chars", chars), ("colors", colors), ("specials", specials)):
        if _shape(value) != EXPECTED_OBSERVATION_SHAPES[key]:
            raise AssertionError(f"rendered map plane {key!r} has unexpected shape")

    direct_static: list[dict[str, int | str]] = []
    class_counts: Counter[str] = Counter()
    for y in range(EXPECTED_OBSERVATION_SHAPES["chars"][0]):
        for x in range(EXPECTED_OBSERVATION_SHAPES["chars"][1]):
            glyph = int(glyphs[y][x])
            char = chr(int(chars[y][x]))
            if bool(nethack.glyph_is_cmap(glyph)) and char in ".#|-+<>_{}~":
                class_counts["direct_static_cmap"] += 1
                direct_static.append({"x": x, "y": y, "char": char, "glyph": glyph, "color": int(colors[y][x])})
            elif bool(nethack.glyph_is_cmap(glyph)) and char == " ":
                # NLE 0.9.0's blank screen background is a cmap glyph.  It is
                # presentation blankness, never evidence for floor/underlay.
                class_counts["blank_cmap_background"] += 1
            elif char == "@":
                class_counts["hero_overlay"] += 1
            else:
                class_counts["nonstatic_presentation"] += 1
    return {
        "provenance": "current_pre_action_rendered_map_planes_only",
        "not_full_map": True,
        "not_fov_mask": True,
        "not_memory_map": True,
        "class_counts": dict(sorted(class_counts.items())),
        "direct_static_cell_count": len(direct_static),
        "direct_static_cells_sha256": sha256_json(direct_static),
        "blank_cmap_is_not_terrain": class_counts["blank_cmap_background"] > 0,
    }


def pre_action_export(observation: dict[str, Any], nethack: Any, *, seed: int) -> dict[str, Any]:
    """Create an auditable pre-action record with no post-action input channel."""

    if set(observation) != set(EXPECTED_OBSERVATION_SHAPES):
        raise AssertionError("pre-action export did not receive every pinned NLE observation")
    for key, expected_shape in EXPECTED_OBSERVATION_SHAPES.items():
        if _shape(observation[key]) != expected_shape:
            raise AssertionError(f"pre-action {key!r} shape changed")
    surface = _map_surface_summary(observation, nethack)
    return {
        "schema": "gamebench.nethack.pre_action_map_fov_export.v1",
        "source_runtime": {"nle_version": PINNED_NLE_VERSION, "nethack_version": "3.6.6"},
        "seed": int(seed),
        "boundary": "reset_before_any_action",
        "provenance": "direct_nle_public_observation_buffers",
        "timeline_guard": "contains reset observation only; no current/post/future action frame may populate this record",
        "map_surface": surface,
        "authoritative_fields_present": [],
        "status": "blocked_no_authoritative_full_map_fov_export",
    }


def full_map_fov_applicability(records: Iterable[dict[str, Any]], *, min_heldout_cases: int = 3) -> dict[str, Any]:
    """Fail closed unless a future source adds a direct full-map/FOV export.

    This does not promote visible static cells into a full-map assertion.  A
    future NLE interface must expose all three semantically distinct planes,
    label them pre-action, and pass independently replayed held-out records.
    """

    records = list(records)
    reasons: list[dict[str, str]] = []
    if min_heldout_cases < 3:
        raise ValueError("min_heldout_cases must be at least three")
    if len(records) < min_heldout_cases:
        reasons.append({"code": "insufficient_heldout_cases", "detail": f"need {min_heldout_cases}; got {len(records)}"})
    seeds: set[int] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            reasons.append({"code": "malformed_record", "detail": f"record {index} is not an object"})
            continue
        if record.get("boundary") != "reset_before_any_action":
            reasons.append({"code": "not_pre_action", "detail": f"record {index} is not explicitly pre-action"})
        if record.get("replayed_exactly") is not True:
            reasons.append({"code": "not_replayed_exactly", "detail": f"record {index} lacks repeated source evidence"})
        seed = record.get("seed")
        if type(seed) is not int:
            reasons.append({"code": "invalid_seed", "detail": f"record {index} lacks an integer source seed"})
        else:
            seeds.add(seed)
        fields = set(record.get("authoritative_fields_present", []))
        missing = REQUIRED_FULL_MAP_FOV_FIELDS - fields
        if missing:
            reasons.append({"code": "missing_authoritative_source_planes", "detail": f"record {index} lacks {sorted(missing)}"})
        export = record.get("authoritative_export")
        if not isinstance(export, dict) or export.get("provenance") != "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array":
            reasons.append({"code": "unverified_native_source", "detail": f"record {index} lacks a hash-verified read-only native export"})
        elif any(key not in export for key in REQUIRED_FULL_MAP_FOV_FIELDS):
            reasons.append({"code": "incomplete_native_source", "detail": f"record {index} native export lacks a required plane"})
    if len(seeds) < min_heldout_cases:
        reasons.append({"code": "insufficient_distinct_seed_cases", "detail": f"need {min_heldout_cases}; got {len(seeds)}"})
    return {
        "schema": "gamebench.nethack.full_map_fov_applicability.v1",
        "status": "eligible" if not reasons else "blocked",
        "source_export_eligible": not reasons,
        "gold_implementation_eligible": False,
        "distinct_heldout_seeds": len(seeds),
        "min_heldout_cases": min_heldout_cases,
        "reasons": reasons,
        "acceptance": "Only direct, pre-action full raw terrain type + flags/doormask + horizontal + FOV mask + memory planes with repeated held-out source evidence may authorize gold FOV/underlay behavior.",
    }


def _action_id(env: Any, name: str) -> int:
    for index, action in enumerate(env.actions):
        if f"{action.__class__.__name__}.{action.name}" == name:
            return index
    raise AssertionError(f"pinned NLE action {name!r} is absent")


def _raw_digest(observation: dict[str, Any]) -> str:
    return sha256_json({key: to_json_array(value) for key, value in sorted(observation.items())})


def run_once(seed: int, *, character: str) -> dict[str, Any]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - command-only dependency guard
        raise RuntimeError("NLE 0.9.0 is required for the map/FOV source audit") from error
    if getattr(nle, "__version__", None) != PINNED_NLE_VERSION:
        raise AssertionError(f"expected nle=={PINNED_NLE_VERSION}, got {getattr(nle, '__version__', None)!r}")
    assert_pinned_schema(nethack.OBSERVATION_DESC)
    env = nle.env.NLE(
        character=character,
        observation_keys=tuple(nethack.OBSERVATION_DESC),
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        core, display = deterministic_nle_seeds(seed)
        configured = tuple(int(value) for value in env.seed(core=core, disp=display, reseed=False))
        if configured != (core, display, False):
            raise AssertionError("NLE declined the deterministic source seed configuration")
        reset = env.reset()
        if not isinstance(reset, dict):
            raise AssertionError("expected legacy Gym reset observation dictionary")
        export = pre_action_export(reset, nethack, seed=seed)
        reader = PinnedNleMapFovReader(env.nethack)
        native_snapshot = reader.snapshot()
        # Two immediate copies must agree.  This is both a read-only
        # noninterference check and a guard against torn layout reads.
        if native_snapshot != reader.snapshot():
            raise AssertionError("native map/FOV reader changed or tore the source state while reading it")
        native_export = native_snapshot.public_record()
        native_controls = reader.validate_against_public_pre_action(native_snapshot, reset, nethack)
        export["authoritative_fields_present"] = sorted(REQUIRED_FULL_MAP_FOV_FIELDS)
        export["authoritative_export"] = native_export
        export["native_layout_controls"] = native_controls
        export["status"] = "eligible_native_pre_action_full_map_fov_export"
        # This frame is intentionally not handed to ``pre_action_export``.
        # It is a repeatability control and a source-change tripwire only.
        stepped, _reward, _done, _info = env.step(_action_id(env, "MiscDirection.WAIT"))
        if not isinstance(stepped, dict):
            raise AssertionError("expected legacy Gym step observation dictionary")
        return {
            "pre_action": export,
            "pre_action_raw_sha256": _raw_digest(reset),
            "heldout_post_wait_raw_sha256": _raw_digest(stepped),
            "configured_seeds": list(configured),
            "public_wrapper_methods": sorted(name for name in dir(env.nethack) if not name.startswith("_")),
            "native_wrapper_methods": sorted(name for name in dir(env.nethack._pynethack) if not name.startswith("_")),
        }
    finally:
        env.close()


def audit(seeds: list[int], *, character: str) -> dict[str, Any]:
    if len(seeds) < 6:
        raise ValueError("need at least six seeds: three calibration and three held-out")
    runs: list[dict[str, Any]] = []
    for seed in seeds:
        first = run_once(seed, character=character)
        second = run_once(seed, character=character)
        if first != second:
            raise AssertionError(f"same seeded NLE executions differ in public pre/post control evidence for seed {seed}")
        record = dict(first["pre_action"])
        record["replayed_exactly"] = True
        record["pre_action_raw_sha256"] = first["pre_action_raw_sha256"]
        # Explicitly label, but do not embed, the later control hash so no
        # consumer can accidentally use it as a source-state hydration plane.
        record["heldout_post_wait_control_sha256"] = first["heldout_post_wait_raw_sha256"]
        runs.append({"record": record, "wrapper_methods": {key: first[key] for key in ("public_wrapper_methods", "native_wrapper_methods")}})
    midpoint = len(runs) // 2
    calibration, heldout = runs[:midpoint], runs[midpoint:]
    applicability = full_map_fov_applicability([entry["record"] for entry in heldout])
    return {
        "schema": "gamebench.nethack.authoritative_map_fov_audit.v1",
        "status": "blocked_by_source_api" if applicability["status"] == "blocked" else "eligible",
        "source_export_eligible": bool(applicability["source_export_eligible"]),
        "gold_implementation_eligible": False,
        "runtime": capture_runtime_identity(__import__("nle")),
        "pinned_source": {
            "nle_version": PINNED_NLE_VERSION,
            "nethack_version": "3.6.6",
            "upstream_tag": "v0.9.0",
            "upstream_commit": "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa",
            "api_definition": "include/nleobs.h and win/rl/winrl.cc::NetHackRL::fill_obs",
        },
        "audit_script_sha256": "sha256:" + sha256_file(Path(__file__)),
        "observation_schema": {key: list(shape) for key, shape in sorted(EXPECTED_OBSERVATION_SHAPES.items())},
        "calibration": calibration,
        "heldout": heldout,
        "applicability": applicability,
        "validity": {
            "no_future_frame_leakage": "post-WAIT evidence is digest-only control data and is excluded from every pre-action export",
            "no_seed_coordinate_lookup": "seeds select independent source executions; no seed or coordinate table supplies terrain",
            "no_score_masking": "blocked source capability is reported as blocked, never counted as an equal gold comparison",
            "native_noninterference": "two consecutive native copies before any action must be byte-identical; all access is ctypes memory reads",
            "gold_behavior_changed": False,
            "gold_implementation_eligible": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(12)))
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, default=TASK_DIR / "reports" / "authoritative_map_fov_audit.json")
    args = parser.parse_args()
    report = audit([int(seed) for seed in args.seeds], character=str(args.character))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "heldout_cases": len(report["heldout"]), "report": str(args.report)}, sort_keys=True))


if __name__ == "__main__":
    main()
