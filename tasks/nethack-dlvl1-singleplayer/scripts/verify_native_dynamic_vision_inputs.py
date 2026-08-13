#!/usr/bin/env python3
"""Replay-gated source evidence for dynamic NetHack vision inputs.

This deliberately audits three inputs to ``src/vision.c::does_block`` and
``do_light_sources`` without turning any source state into a gold input:

* floor boulders;
* still-mimicking monsters which block light; and
* live ``light_base`` entries.

The default is a contiguous, predeclared dlvl-1 seed range and the same two
safe actions for every seed.  A seed is never retained, removed, or routed
according to an observed result.  Every source/public boundary is copied
twice in independent runs and must compare byte-for-byte after JSON
canonicalisation.  The report is diagnostic source evidence only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import (  # noqa: E402
    OBSERVATION_KEYS,
    bytes_to_text,
    deterministic_nle_seeds,
    normalise_reset,
    to_json_array,
)
from scripts.nle_native_map_fov import (  # noqa: E402
    OBS_COLNO,
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
    ROWNO,
    PinnedNleMapFovReader,
    validate_semantic_vision_export,
)
from scripts.oracle_tape import capture_runtime_identity, sha256_file  # noqa: E402
from scripts.verify_native_map_fov_transitions import public_render_summary  # noqa: E402


SCHEMA = "gamebench.nethack.native_dynamic_vision_input_audit.v1"
# These inputs are intentionally independent of the seed and output. SEARCH
# gives a genuine consuming action boundary; WAIT avoids a coordinate-derived
# route. Campaigns that test an inventory prompt may use a different explicit
# action list, but apply that exact byte sequence to every seed.
DEFAULT_ACTIONS = ("MiscDirection.WAIT", "Command.SEARCH")
INPUT_KINDS = ("boulder", "mimic", "light")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _plane_cells(plane: Any, *, label: str) -> set[tuple[int, int]]:
    if not isinstance(plane, list) or len(plane) != ROWNO:
        raise AssertionError(f"{label} plane is not {ROWNO} rows")
    cells: set[tuple[int, int]] = set()
    for y, row in enumerate(plane):
        if not isinstance(row, list) or len(row) != OBS_COLNO:
            raise AssertionError(f"{label} plane row {y} is not {OBS_COLNO} cells")
        for x, value in enumerate(row):
            if type(value) is not bool:
                raise AssertionError(f"{label} plane cell ({x},{y}) is not boolean")
            if value:
                cells.add((x, y))
    return cells


def assess_dynamic_vision_inputs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Cross-check source records against their decision planes, fail closed.

    ``validate_semantic_vision_export`` checks shape, digests, and semantic
    predicates.  This additional check prevents a valid-looking positive
    boolean plane from being reported without a corresponding read-only
    object/monster record, and vice versa.
    """

    semantic_errors = validate_semantic_vision_export(snapshot)
    if semantic_errors:
        raise AssertionError("malformed semantic vision export: " + "; ".join(semantic_errors))
    if snapshot.get("binary_sha256") != PINNED_BINARY_SHA256:
        raise AssertionError("dynamic vision audit requires the exact pinned NLE binary")
    if snapshot.get("source_export_eligible") is not True or snapshot.get("gold_implementation_eligible") is not False:
        raise AssertionError("dynamic vision snapshot eligibility flags are malformed")

    blockers = snapshot.get("dynamic_vision_blockers")
    lighting = snapshot.get("lighting")
    if not isinstance(blockers, dict) or not isinstance(lighting, dict):
        raise AssertionError("dynamic vision snapshot lacks blockers or lighting")
    boulder_cells = _plane_cells(blockers.get("boulder"), label="boulder")
    mimic_cells = _plane_cells(blockers.get("visible_mimic"), label="visible mimic")
    effective_cells = _plane_cells(blockers.get("effective"), label="effective blocker")
    if effective_cells != boulder_cells | mimic_cells:
        raise AssertionError("effective dynamic blocker plane is not the exact boulder/mimic union")

    records = blockers.get("records")
    if not isinstance(records, list):
        raise AssertionError("dynamic blocker records are missing")
    seen: dict[str, set[tuple[int, int]]] = {"boulder": set(), "mimic": set()}
    for record in records:
        if not isinstance(record, dict):
            raise AssertionError("dynamic blocker record is not an object")
        kind = record.get("kind")
        x, y = record.get("x"), record.get("y")
        if kind not in seen or type(x) is not int or type(y) is not int:
            raise AssertionError("dynamic blocker record kind/coordinate is malformed")
        if (x, y) in seen[kind]:
            raise AssertionError(f"duplicate {kind} dynamic blocker record at {(x, y)}")
        seen[kind].add((x, y))
        if kind == "boulder":
            if type(record.get("object_id")) is not int or type(record.get("object_type")) is not int:
                raise AssertionError("boulder record lacks exact native object identity")
        else:
            required = ("monster_id", "appearance_type", "mappearance", "invisible", "see_invisible")
            if type(record.get("monster_id")) is not int or not all(type(record.get(name)) is int for name in ("appearance_type", "mappearance")) or not all(type(record.get(name)) is bool for name in ("invisible", "see_invisible")):
                raise AssertionError(f"mimic record lacks exact native state: required {required}")
    if seen["boulder"] != boulder_cells:
        raise AssertionError("boulder records do not exactly cover the boulder blocker plane")
    if seen["mimic"] != mimic_cells:
        raise AssertionError("mimic records do not exactly cover the visible-mimic blocker plane")

    sources = lighting.get("active_light_sources")
    if not isinstance(sources, list):
        raise AssertionError("active light-source list is missing")
    owners: set[tuple[str, int]] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise AssertionError("active light-source record is not an object")
        owner = (source.get("owner_kind"), source.get("owner_id"))
        if owner in owners:
            raise AssertionError("active light-source owner appears more than once")
        owners.add(owner)  # semantic validator already checks owner/range ABI.

    # The comparison denominator is source-record-to-plane membership plus
    # the exact union assertion.  It cannot be zero even in an all-absent
    # state; a caller separately requires positive requested input coverage.
    comparisons = len(records) + len(sources) + 1
    return {
        "boulder_cells": len(boulder_cells),
        "visible_mimic_cells": len(mimic_cells),
        "effective_blocker_cells": len(effective_cells),
        "active_light_sources": len(sources),
        "source_record_plane_comparisons": comparisons,
        "source_snapshot_sha256": sha256_json(snapshot),
    }


def _new_env(*, character: str) -> Any:
    import nle
    from nle import nethack

    if getattr(nle, "__version__", None) != "0.9.0":
        raise RuntimeError("native dynamic-vision audit requires nle==0.9.0")
    return nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        max_episode_steps=100,
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def _action_ids(env: Any, action_names: tuple[str, ...]) -> list[dict[str, Any]]:
    table = {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}
    unknown = [name for name in action_names if name not in table]
    if unknown:
        raise AssertionError("pinned NLE action table lacks: " + ", ".join(unknown))
    return [{"action_name": name, "action_id": int(table[name])} for name in action_names]


def _step(result: Any) -> tuple[dict[str, Any], bool]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise AssertionError("pinned Gym NLE step result is malformed")
    return dict(result[0]), bool(result[2])


def _public_evidence(observation: dict[str, Any], nethack: Any) -> dict[str, Any]:
    """Keep exact terminal/pixel hashes, plus a bounded prompt transcript.

    The text is diagnostic only. The complete raw terminal planes stay behind
    their hashes, so no rendered fact becomes a gold behavior input.
    """

    render = public_render_summary(observation, nethack.glyph_is_cmap)
    terminal = {
        "tty_chars": to_json_array(observation.get("tty_chars", [])),
        "tty_colors": to_json_array(observation.get("tty_colors", [])),
        "tty_cursor": to_json_array(observation.get("tty_cursor", [])),
        "message_raw": to_json_array(observation.get("message", [])),
    }
    return {
        "render_sha256": render["digest"],
        "terminal_ui_sha256": sha256_json(terminal),
        "message_text": bytes_to_text(observation.get("message", [])).strip(),
    }


def _snapshot(reader: PinnedNleMapFovReader, observation: dict[str, Any], nethack: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    first_native = reader.snapshot()
    snapshot = first_native.public_record()
    # A second independent copy proves the inspection itself did not perturb
    # source state.  This detects torn reads and accidental native writes.
    if snapshot != reader.snapshot().public_record():
        raise AssertionError("read-only dynamic-vision snapshot changed native source state")
    reader.validate_against_public_pre_action(first_native, observation, nethack)
    return snapshot, _public_evidence(observation, nethack)


def capture_case(seed: int, *, character: str, action_names: tuple[str, ...]) -> dict[str, Any]:
    """Capture one whole predeclared seed without outcome-selected routing."""

    import nle

    env = _new_env(character=character)
    try:
        core, display = deterministic_nle_seeds(seed)
        configured = tuple(int(value) for value in env.seed(core=core, disp=display, reseed=False))
        if configured != (core, display, False):
            raise AssertionError("NLE declined deterministic dynamic-vision seed configuration")
        observation = normalise_reset(env.reset())
        reader = PinnedNleMapFovReader(env.nethack)
        actions = _action_ids(env, action_names)
        initial, initial_public = _snapshot(reader, observation, nle.nethack)
        initial_assessment = assess_dynamic_vision_inputs(initial)
        boundaries: list[dict[str, Any]] = []
        for step_index, action in enumerate(actions, start=1):
            before, before_public = _snapshot(reader, observation, nle.nethack)
            before_assessment = assess_dynamic_vision_inputs(before)
            next_observation, done = _step(env.step(action["action_id"]))
            after, after_public = _snapshot(reader, next_observation, nle.nethack)
            after_assessment = assess_dynamic_vision_inputs(after)
            boundaries.append({
                "step": step_index,
                "input": action,
                "done": done,
                "before": before,
                "after": after,
                "before_public_evidence": before_public,
                "after_public_evidence": after_public,
                "before_assessment": before_assessment,
                "after_assessment": after_assessment,
            })
            observation = next_observation
            if done:
                raise AssertionError("predeclared dynamic-vision action plan terminated early")
        return {
            "seed": int(seed),
            "configured_seeds": list(configured),
            "initial": initial,
            "initial_public_evidence": initial_public,
            "initial_assessment": initial_assessment,
            "boundaries": boundaries,
        }
    finally:
        env.close()


def _observed_counts(cases: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for case in cases:
        states = [case["initial_assessment"]]
        for boundary in case["boundaries"]:
            states.extend((boundary["before_assessment"], boundary["after_assessment"]))
        for state in states:
            counts["boulder"] += int(state["boulder_cells"] > 0)
            counts["mimic"] += int(state["visible_mimic_cells"] > 0)
            counts["light"] += int(state["active_light_sources"] > 0)
            counts["source_record_plane_comparisons"] += int(state["source_record_plane_comparisons"])
    return counts


def audit(*, seed: int, cases: int, character: str, action_names: tuple[str, ...], required: tuple[str, ...]) -> dict[str, Any]:
    if cases < 6:
        raise ValueError("dynamic-vision audit requires at least six contiguous preselected seeds")
    if len(action_names) < 2 or len(set(action_names)) < 2:
        raise ValueError("dynamic-vision audit requires at least two distinct preselected actions")
    if not required or any(kind not in INPUT_KINDS for kind in required):
        raise ValueError("required dynamic-vision kinds must be a nonempty subset of boulder,mimic,light")

    seeds = list(range(seed, seed + cases))
    first = [capture_case(value, character=character, action_names=action_names) for value in seeds]
    second = [capture_case(value, character=character, action_names=action_names) for value in seeds]
    repeated_exact = first == second
    if not repeated_exact:
        raise AssertionError("dynamic-vision source evidence did not exactly replay across independent same-seed runs")
    counts = _observed_counts(first)
    comparison_count = int(counts["source_record_plane_comparisons"])
    if comparison_count <= 0:
        raise AssertionError("dynamic-vision source audit produced zero record/plane comparisons")
    missing = [kind for kind in required if not counts[kind]]
    source_export_eligible = not missing and repeated_exact and comparison_count > 0
    return {
        "schema": SCHEMA,
        "status": "pass_source_only" if source_export_eligible else "blocked_missing_required_dynamic_input",
        "source_export_eligible": source_export_eligible,
        "gold_implementation_eligible": False,
        "source_identity": {
            "nle_version": "0.9.0",
            "source_commit": PINNED_SOURCE_COMMIT,
            "binary_sha256": PINNED_BINARY_SHA256,
            "runtime": capture_runtime_identity(__import__("nle")),
            "audit_script_sha256": "sha256:" + sha256_file(Path(__file__)),
        },
        "action_plan": list(action_names),
        "character": character,
        "action_plan_contract": "Two fixed action names are applied in order to every seed. In a NetHack prompt, an action's existing ASCII value is interpreted by the native UI as that prompt response; this context effect is recorded, never hidden. The seed set is the contiguous interval [seed, seed+cases); no source outcome, coordinate, public frame, or future state alters it.",
        "seed_contract": {"first_seed": seed, "cases": cases, "seeds": seeds, "contiguous_preselected": True},
        "required_positive_inputs": list(required),
        "coverage": {
            "positive_state_observations": {kind: int(counts[kind]) for kind in INPUT_KINDS},
            "source_record_plane_comparisons": comparison_count,
            "mimic_and_light_interpretation": "Zero is a measured unreached input in this bounded dlvl-1 campaign, not proof of source impossibility.",
        },
        "two_independent_runs_exact": True,
        "cases": first,
        "validity": {
            "read_only_source_state": True,
            "source_identity_pinned": True,
            "captured_pre_action_and_post_action": True,
            "exact_public_terminal_render_digests": True,
            "no_future_or_reset_hydration": True,
            "no_seed_coordinate_or_outcome_lookup": True,
            "zero_comparison_rejected": True,
            "gold_input_or_behavior_changed": False,
        },
        "blocker": "Boulder presence establishes only the native does_block input. Mimic blockers and active light sources remain unreached unless their positive state count is nonzero; no collision, FOV, lighting, memory, or rendering rule is promoted from this audit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260730, help="first contiguous preselected seed")
    parser.add_argument("--cases", type=int, default=12, help="number of contiguous preselected seeds; minimum six")
    parser.add_argument("--character", default="val-hum-fem-law", help="fixed NLE character for every seed")
    parser.add_argument("--actions", default=",".join(DEFAULT_ACTIONS), help="comma-separated fixed action names")
    parser.add_argument("--require", default="boulder", help="comma-separated positive inputs required for pass: boulder,mimic,light")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    action_names = tuple(value.strip() for value in args.actions.split(",") if value.strip())
    required = tuple(value.strip() for value in args.require.split(",") if value.strip())
    report = audit(seed=int(args.seed), cases=int(args.cases), character=str(args.character), action_names=action_names, required=required)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"],
        "source_export_eligible": report["source_export_eligible"],
        "positive_state_observations": report["coverage"]["positive_state_observations"],
        "report": str(args.report.resolve()),
    }, sort_keys=True))
    if not report["source_export_eligible"]:
        raise SystemExit("required dynamic vision input was not reached; see report")


if __name__ == "__main__":
    main()
