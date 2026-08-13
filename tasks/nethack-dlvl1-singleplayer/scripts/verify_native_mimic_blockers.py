#!/usr/bin/env python3
"""Construct and replay positive native mimic blockers through NLE wizard mode.

This is deliberately a source-oracle-only campaign.  It uses the pinned
wheel's documented wizard commands (``^G`` create monster and ``^V`` level
teleport), never a ctypes write or a source-state restore.  The action tape is
fully declared before reset: every contiguous seed receives six exact
``small mimic`` input transcripts, followed by a fixed level-2/level-1 round
trip.  Returning to level 1 makes NetHack run its own ``hide_monst`` path,
which is the legitimate source-controlled way to obtain mimicking appearances.

The report retains every input boundary's native mimic plane/records, native
state hash, and terminal hashes.  It repeats the whole fixed campaign in a
fresh process environment and fails closed unless those projected records are
bit-for-bit identical and include a nonzero positive mimic denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from scripts.nle_native_entities import PinnedNleEntityReader  # noqa: E402
from scripts.nle_native_map_fov import (  # noqa: E402
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
    PinnedNleMapFovReader,
)
from scripts.oracle_tape import capture_runtime_identity, sha256_file  # noqa: E402
from scripts.verify_native_dynamic_vision_inputs import assess_dynamic_vision_inputs  # noqa: E402
from scripts.verify_native_map_fov_transitions import public_render_summary  # noqa: E402


SCHEMA = "gamebench.nethack.native_mimic_blocker_construction.v1"
CHARACTER = "val-hum-fem-law"
SPAWN_COUNT = 6
MIMIC_NAME = "small mimic"
# ``PM_SMALL_MIMIC`` in the pinned source's generated monster table.  This is
# checked against the actual source entity list after each completed spawn; it
# is not an input to either gold implementation.
PINNED_SMALL_MIMIC_SPECIES_ID = 63


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _test_actions(nethack: Any) -> tuple[Any, ...]:
    """Add only the two documented wizard-mode control bytes to NLE's table."""

    return tuple(nethack.ACTIONS) + (
        nethack.WizardCommand.WIZGENESIS,
        nethack.WizardCommand.WIZLEVELPORT,
    )


def build_action_plan(nethack: Any) -> list[dict[str, Any]]:
    """Return the immutable, result-independent wizard input tape."""

    names_by_value: dict[int, str] = {}
    for action in _test_actions(nethack):
        value = int(action)
        # NLE intentionally has aliases (for example '$' is both a command
        # and a text character).  The declared transcript uses no ambiguous
        # byte; retain the first public table spelling solely for diagnostics.
        names_by_value.setdefault(value, f"{action.__class__.__name__}.{action.name}")
    required = [
        int(nethack.WizardCommand.WIZGENESIS),
        int(nethack.WizardCommand.WIZLEVELPORT),
        *[ord(character) for character in MIMIC_NAME],
        ord("\r"), ord("1"), ord("2"),
    ]
    if any(value not in names_by_value for value in required):
        raise AssertionError("pinned NLE action table cannot express the declared wizard transcript")

    plan: list[tuple[str, int]] = []
    for spawn_index in range(SPAWN_COUNT):
        plan.append((f"spawn_{spawn_index + 1}_begin", int(nethack.WizardCommand.WIZGENESIS)))
        plan.extend((f"spawn_{spawn_index + 1}_name", ord(character)) for character in MIMIC_NAME)
        plan.append((f"spawn_{spawn_index + 1}_submit", ord("\r")))
    plan.extend((
        ("level_port_to_2_begin", int(nethack.WizardCommand.WIZLEVELPORT)),
        ("level_port_to_2_value", ord("2")),
        ("level_port_to_2_submit", ord("\r")),
        ("level_port_to_1_begin", int(nethack.WizardCommand.WIZLEVELPORT)),
        ("level_port_to_1_value", ord("1")),
        ("level_port_to_1_submit", ord("\r")),
    ))
    return [
        {"step": index, "stage": stage, "action_name": names_by_value[value], "ascii": value}
        for index, (stage, value) in enumerate(plan, start=1)
    ]


def _new_env(nethack: Any) -> Any:
    import nle

    if getattr(nle, "__version__", None) != "0.9.0":
        raise RuntimeError("mimic construction campaign requires nle==0.9.0")
    return nle.env.NLE(
        character=CHARACTER,
        observation_keys=OBSERVATION_KEYS,
        actions=_test_actions(nethack),
        max_episode_steps=300,
        wizard=True,
        allow_all_modes=True,
        allow_all_yn_questions=True,
        # This disables independent normal monster generation so the six
        # wizard-created monsters are attributable to the fixed input tape.
        spawn_monsters=False,
    )


def _public_evidence(observation: dict[str, Any], nethack: Any) -> dict[str, Any]:
    terminal = {
        "tty_chars": to_json_array(observation.get("tty_chars", [])),
        "tty_colors": to_json_array(observation.get("tty_colors", [])),
        "tty_cursor": to_json_array(observation.get("tty_cursor", [])),
        "message_raw": to_json_array(observation.get("message", [])),
    }
    return {
        "render_sha256": public_render_summary(observation, nethack.glyph_is_cmap)["digest"],
        "terminal_ui_sha256": sha256_json(terminal),
        "message_text": bytes_to_text(observation.get("message", [])).strip(),
    }


def _mimic_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Retain the full exact decision plane and prove record membership."""

    assessment = assess_dynamic_vision_inputs(snapshot)
    blockers = snapshot["dynamic_vision_blockers"]
    plane = blockers["visible_mimic"]
    records = [record for record in blockers["records"] if record["kind"] == "mimic"]
    plane_cells = {
        (x, y)
        for y, row in enumerate(plane)
        for x, value in enumerate(row)
        if value is True
    }
    record_cells = {(int(record["x"]), int(record["y"])) for record in records}
    if record_cells != plane_cells or len(record_cells) != len(records):
        raise AssertionError("native mimic records do not exactly cover their positive decision plane")
    return {
        "native_snapshot_sha256": sha256_json(snapshot),
        "native_plane_sha256": snapshot["plane_sha256"]["dynamic_blocker_visible_mimic"],
        "visible_mimic_plane": plane,
        "visible_mimic_records": records,
        "visible_mimic_cells": len(plane_cells),
        "record_plane_comparisons": len(records) + 1,
        "dynamic_vision_assessment": assessment,
    }


def _source_state(map_reader: PinnedNleMapFovReader, entity_reader: PinnedNleEntityReader, observation: dict[str, Any], nethack: Any) -> dict[str, Any]:
    first_native = map_reader.snapshot()
    snapshot = first_native.public_record()
    # Independent repeats ensure that the read-only oracle sidecar itself did
    # not perturb or tear the source state.
    if snapshot != map_reader.snapshot().public_record():
        raise AssertionError("read-only mimic source snapshot changed native state")
    # Do not call ``validate_against_public_pre_action`` here: that helper is
    # a normal-play terrain/glyph assertion and deliberately rejects the
    # wizard-induced level re-entry display while NetHack is repainting hidden
    # mimics.  This campaign's authority is the independently semantic-
    # validated native ``does_block`` plane; terminal state is retained as
    # exact replay evidence below, never reverse-engineered into a source map.
    entities = entity_reader.snapshot()
    if entities != entity_reader.snapshot():
        raise AssertionError("read-only mimic entity snapshot changed native state")
    small_mimics = [
        {
            "entity_id": entity["entity_id"], "species_id": entity["species_id"],
            "x": entity["x"], "y": entity["y"], "native_x": entity["native_x"],
            "status": entity["path_state"]["status"],
        }
        for entity in entities.entities
        if entity["species_id"] == PINNED_SMALL_MIMIC_SPECIES_ID
    ]
    return {
        "depth": int(observation["blstats"][12]),
        "mimic": _mimic_projection(snapshot),
        "small_mimic_entities": small_mimics,
        "entity_snapshot_sha256": sha256_json(entities.entities),
        "public": _public_evidence(observation, nethack),
    }


def capture_case(seed: int, plan: list[dict[str, Any]]) -> dict[str, Any]:
    """Run every declared input; no state can alter the tape or seed set."""

    import nle
    from nle import nethack

    env = _new_env(nethack)
    try:
        core, display = deterministic_nle_seeds(seed)
        configured = tuple(int(value) for value in env.seed(core=core, disp=display, reseed=False))
        if configured != (core, display, False):
            raise AssertionError("NLE declined deterministic mimic-campaign seed configuration")
        table = {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}
        observation = normalise_reset(env.reset())
        map_reader = PinnedNleMapFovReader(env.nethack)
        entity_reader = PinnedNleEntityReader(env.nethack)
        initial = _source_state(map_reader, entity_reader, observation, nethack)
        boundaries: list[dict[str, Any]] = []
        for action in plan:
            if action["action_name"] not in table:
                raise AssertionError(f"declared action unavailable in constructed NLE table: {action['action_name']}")
            before = _source_state(map_reader, entity_reader, observation, nethack)
            result = env.step(int(table[action["action_name"]]))
            if not isinstance(result, tuple) or len(result) < 3:
                raise AssertionError("pinned Gym NLE step result is malformed")
            observation, done = dict(result[0]), bool(result[2])
            if done:
                raise AssertionError("fixed mimic construction tape terminated early")
            after = _source_state(map_reader, entity_reader, observation, nethack)
            if action["stage"] == "level_port_to_2_submit" and after["depth"] != 2:
                raise AssertionError("fixed wizard level-port transcript did not reach level 2")
            if action["stage"] == "level_port_to_1_submit":
                if after["depth"] != 1:
                    raise AssertionError("fixed wizard level-port transcript did not return to level 1")
                if len(after["small_mimic_entities"]) != SPAWN_COUNT:
                    raise AssertionError("fixed wizard transcript did not retain exactly six created small mimics")
            boundaries.append({"input": action, "before": before, "after": after})
        return {"seed": seed, "configured_seeds": list(configured), "initial": initial, "boundaries": boundaries}
    finally:
        env.close()


def audit(*, seed: int, cases: int) -> dict[str, Any]:
    if cases < 6:
        raise ValueError("mimic construction requires at least six contiguous preselected seeds")
    from nle import nethack
    import nle

    seeds = list(range(seed, seed + cases))
    plan = build_action_plan(nethack)
    first = [capture_case(value, plan) for value in seeds]
    second = [capture_case(value, plan) for value in seeds]
    if first != second:
        raise AssertionError("fixed wizard mimic campaign did not exactly replay in independent runs")
    states = [case["initial"] for case in first]
    states.extend(boundary[position] for case in first for boundary in case["boundaries"] for position in ("before", "after"))
    positive_states = [state for state in states if state["mimic"]["visible_mimic_cells"] > 0]
    comparisons = sum(int(state["mimic"]["record_plane_comparisons"]) for state in states)
    positive_cells = sum(int(state["mimic"]["visible_mimic_cells"]) for state in positive_states)
    if comparisons <= 0 or positive_cells <= 0:
        raise AssertionError("mimic campaign has a zero exact positive comparison denominator")
    return {
        "schema": SCHEMA,
        "status": "pass_source_only",
        "source_export_eligible": True,
        "gold_implementation_eligible": False,
        "source_identity": {
            "nle_version": "0.9.0", "source_commit": PINNED_SOURCE_COMMIT,
            "binary_sha256": PINNED_BINARY_SHA256, "runtime": capture_runtime_identity(nle),
            "audit_script_sha256": "sha256:" + sha256_file(Path(__file__)),
        },
        "test_mode_identity": {
            "wizard": True, "spawn_monsters": False, "character": CHARACTER,
            "construction": "six ^G small-mimic transcripts followed by a fixed ^V 2 / ^V 1 round trip",
            "source_controlled_only": True,
        },
        "seed_contract": {"first_seed": seed, "cases": cases, "seeds": seeds, "contiguous_preselected": True},
        "input_plan": plan,
        "input_plan_sha256": sha256_json(plan),
        "coverage": {
            "total_input_boundaries": len(plan) * cases,
            "state_observations": len(states),
            "positive_mimic_state_observations": len(positive_states),
            "positive_visible_mimic_cells": positive_cells,
            "exact_record_plane_comparisons": comparisons,
        },
        "two_independent_runs_exact": True,
        "cases": first,
        "validity": {
            "inputs_and_seeds_preselected_before_results": True,
            "wizard_commands_are_pinned_wheel_test_mode_inputs": True,
            "no_ctypes_writes_or_source_restore": True,
            "source_snapshot_and_record_plane_membership_checked_each_boundary": True,
            "exact_native_and_terminal_hashes_recorded_each_boundary": True,
            "zero_positive_denominator_rejected": True,
            "gold_input_or_behavior_changed": False,
        },
        "blocker": "This proves only that pinned NLE can expose positive mimic does_block inputs under a declared wizard test-mode tape. It does not promote collision, FOV, lighting, memory, rendering, or any gold behavior.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--cases", type=int, default=6)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = audit(seed=int(args.seed), cases=int(args.cases))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "coverage": report["coverage"], "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
