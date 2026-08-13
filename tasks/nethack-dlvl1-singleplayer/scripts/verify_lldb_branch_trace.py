#!/usr/bin/env python3
"""Fail-closed LLDB trace of exact-wheel ``mfndpos`` candidate branches.

The tracee always loads the shipped, hash-pinned NLE wheel.  LLDB only reads
registers and memory at the ``mfndpos`` return boundary and at ``dog_move`` /
``m_move`` returns.  A separate unattached run must produce byte-identical
public projections, native source-boundary digests, and final raw RNG state
before any trace data is accepted as source evidence.

No data from this script is imported by either gold engine or a conformance
denominator.  A non-empty eligible trace remains source-only; the standard
frontier gate is a separate prerequisite for any gold implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import deterministic_nle_seeds, normalise_reset, to_json_array
from scripts.frontier_promotion_gate import SCHEMA as FRONTIER_GATE_SCHEMA, evaluate as evaluate_frontier_gate
from scripts.instrumented_oracle_gate import PINNED_BINARY_SHA256, PINNED_SOURCE_COMMIT, SCHEMA as GATE_SCHEMA, evaluate as evaluate_gate
from scripts.nle_authoritative_entity_contract import NLE_090_OBSERVATION_KEYS
from scripts.nle_native_entities import PinnedNleEntityReader
from scripts.nle_native_map_fov import PinnedNleMapFovReader
from scripts.nle_native_player import PinnedNlePlayerReader
from scripts.nle_rng_state import PinnedNleRngReader
from scripts.oracle_tape import sha256_json


SCHEMA = "gamebench.nethack.lldb_branch_candidate_trace.v1"
# Preselected before any result is inspected.  The final SPACE is a bounded
# prompt-resume deadline for a native --More-- yielded by a pet attack during
# this campaign; it is not chosen from the resulting screen.
DEFAULT_ACTIONS = ("Command.SEARCH", "MiscDirection.WAIT", "CompassDirection.E", "Command.SEARCH", "TextCharacters.SPACE")
TRACE_CALLBACK = TASK_DIR / "scripts" / "lldb_branch_trace_callbacks.py"
# Equivalence must cover the whole documented NLE v0.9.0 public surface, not
# merely the smaller plane selection normally archived in a task tape.
PUBLIC_OBSERVATION_KEYS = tuple(sorted(NLE_090_OBSERVATION_KEYS))


def _action_id(env: Any, action_name: str) -> int:
    for index, action in enumerate(env.actions):
        if f"{action.__class__.__name__}.{action.name}" == action_name:
            return index
    raise ValueError(f"pinned NLE action table lacks {action_name}")


def _new_env() -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(
        character="val-hum-fem-law",
        observation_keys=PUBLIC_OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def _public_projection(observation: dict[str, Any]) -> dict[str, Any]:
    # Preserve every requested public array without interpreting it.  The
    # canonical JSON hash below is the byte-exact comparison boundary for the
    # independent launch; no renderer-specific field is discarded.
    return {name: to_json_array(observation[name]) for name in PUBLIC_OBSERVATION_KEYS}


def _native_boundary(
    entities: PinnedNleEntityReader,
    map_fov: PinnedNleMapFovReader,
    player: PinnedNlePlayerReader,
    rng: PinnedNleRngReader,
) -> dict[str, Any]:
    return {
        "entities": entities.snapshot().public_record(),
        "map_fov": map_fov.snapshot().public_record(),
        "player": player.snapshot().public_record(),
        "rng": rng.snapshot().public_record(),
    }


def _frame(
    observation: dict[str, Any],
    entities: PinnedNleEntityReader,
    map_fov: PinnedNleMapFovReader,
    player: PinnedNlePlayerReader,
    rng: PinnedNleRngReader,
) -> dict[str, Any]:
    public = _public_projection(observation)
    native = _native_boundary(entities, map_fov, player, rng)
    return {
        "public_observation_sha256": sha256_json(public),
        "native_boundary_sha256": sha256_json(native),
        "rng": native["rng"],
        # Only the dynamic pieces needed to bind LLDB actor IDs to source
        # snapshots are retained in this runner output.  Map/FOV is included
        # in native_boundary_sha256 and compared there as a full plane.
        "entities": native["entities"],
        "player": native["player"],
        "prompt_evidence": _prompt_evidence(observation),
    }


def _prompt_evidence(observation: dict[str, Any]) -> dict[str, Any]:
    """Keep small exact terminal evidence for fixed prompt-resume inputs."""

    tty = to_json_array(observation.get("tty_chars", []))
    rows = tty if isinstance(tty, list) else []
    text = "\n".join(
        "".join(chr(int(cell)) for cell in row if type(cell) is int)
        for row in rows
        if isinstance(row, list)
    )
    message = to_json_array(observation.get("message", []))
    raw_message = [int(cell) for cell in message if type(cell) is int] if isinstance(message, list) else []
    return {
        "more_prompt_visible": "--More--" in text,
        "tty_chars_sha256": sha256_json(tty),
        "message_raw": raw_message,
    }


def _write_state(path: Path | None, payload: dict[str, Any]) -> None:
    if path is not None:
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def runner(seed: int, actions: list[str], output: Path, state_path: Path | None) -> None:
    """Run one fixed action sequence, exposing only preselected step tokens."""

    env = _new_env()
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        observation = normalise_reset(env.reset())
        readers = (
            PinnedNleEntityReader(env.nethack),
            PinnedNleMapFovReader(env.nethack),
            PinnedNlePlayerReader(env.nethack),
            PinnedNleRngReader(env.nethack),
        )
        frames = [_frame(observation, *readers)]
        chosen: list[dict[str, Any]] = []
        prompt_boundaries: list[dict[str, Any]] = []
        pending_more: dict[str, Any] | None = None
        _write_state(state_path, {"phase": "idle"})
        for step, action_name in enumerate(actions, start=1):
            # Both action-table spellings represent the same explicit space
            # byte on the pinned NLE wheel. Fuzz tapes normally retain the
            # semantic ``MiscAction.MORE`` selector; the older branch-trace
            # default used ``TextCharacters.SPACE``. Accept either without
            # accepting arbitrary input at the pager boundary.
            if pending_more is not None and action_name not in {"TextCharacters.SPACE", "MiscAction.MORE"}:
                raise RuntimeError(
                    f"fixed --More-- resume deadline after step {pending_more['opened_after_step']} requires TextCharacters.SPACE, got {action_name}"
                )
            action = {"step": step, "action_id": _action_id(env, action_name), "action_name": action_name}
            # This happens before env.step and is the only input the LLDB
            # callback accepts.  It never sees a post-action observation when
            # deciding whether to retain a branch event.
            _write_state(state_path, {"phase": "action", "step": step, "action": action})
            observation = normalise_reset(env.step(action["action_id"]))
            frames.append(_frame(observation, *readers))
            chosen.append(action)
            evidence = frames[-1]["prompt_evidence"]
            if pending_more is not None:
                if evidence["more_prompt_visible"] is True:
                    raise RuntimeError(f"fixed --More-- resume deadline at step {step} did not clear the prompt")
                pending_more["resumed_by_step"] = step
                pending_more["resume_action"] = action_name
                pending_more = None
            if evidence["more_prompt_visible"] is True:
                pending_more = {
                    "opened_after_step": step,
                    "resume_deadline_step": step + 1,
                    "tty_chars_sha256": evidence["tty_chars_sha256"],
                    "message_raw": evidence["message_raw"],
                }
                prompt_boundaries.append(pending_more)
        _write_state(state_path, {"phase": "idle"})
        if pending_more is not None:
            raise RuntimeError(f"--More-- opened at step {pending_more['opened_after_step']} without its fixed resume input")
        payload = {
            "schema": "gamebench.nethack.lldb_branch_runner.v1",
            "seed": seed,
            "actions": chosen,
            "public_observation_keys": list(PUBLIC_OBSERVATION_KEYS),
            "frames": frames,
            "prompt_boundaries": prompt_boundaries,
            "binary_sha256": frames[0]["entities"]["binary_sha256"],
        }
        output.write_text(json.dumps(payload, sort_keys=True) + "\n")
    finally:
        _write_state(state_path, {"phase": "idle"})
        env.close()


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"LLDB event {line_number} is not an object")
        events.append(value)
    return events


def _run_lldb(seed: int, actions: list[str], output: Path, state: Path, events: Path) -> subprocess.CompletedProcess[str]:
    if not TRACE_CALLBACK.is_file():
        raise RuntimeError("LLDB branch callback script is missing")
    command_file = output.with_suffix(".lldb")
    action_text = ",".join(actions)
    command_file.write_text(
        "\n".join(
            (
                # Do not resolve the venv interpreter symlink: resolving it
                # selects the base uv Python and silently drops this task's
                # pinned NLE installation from sys.path.
                f"target create {Path(sys.executable).absolute()}",
                f"command script import {TRACE_CALLBACK}",
                f"settings set target.env-vars NLE_BRANCH_TRACE_STATE={state} NLE_BRANCH_TRACE_EVENTS={events}",
                # Breakpoint callbacks run in LLDB's host Python, not in the
                # target process, so mirror the two read-only handoff paths
                # into that interpreter as well.
                f"script import os; os.environ['NLE_BRANCH_TRACE_STATE'] = {str(state)!r}; os.environ['NLE_BRANCH_TRACE_EVENTS'] = {str(events)!r}",
                f"settings set -- target.run-args {Path(__file__).resolve()} --runner --seed {seed} --actions {action_text} --output {output}",
                "run",
            )
        )
        + "\n"
    )
    try:
        return subprocess.run(["lldb", "--batch", "-s", str(command_file)], text=True, capture_output=True, check=False)
    finally:
        if command_file.exists():
            command_file.unlink()


def _mismatches(baseline: dict[str, Any], traced: dict[str, Any]) -> tuple[int, int, int]:
    if (
        baseline.get("seed") != traced.get("seed")
        or baseline.get("actions") != traced.get("actions")
        or baseline.get("public_observation_keys") != traced.get("public_observation_keys")
    ):
        raise ValueError("equivalence runs have different preselected seed/actions/public observation surface")
    baseline_frames = baseline.get("frames")
    traced_frames = traced.get("frames")
    if not isinstance(baseline_frames, list) or not isinstance(traced_frames, list) or len(baseline_frames) != len(traced_frames):
        raise ValueError("equivalence runs have different frame counts")
    public = native = 0
    for left, right in zip(baseline_frames, traced_frames, strict=True):
        if left.get("public_observation_sha256") != right.get("public_observation_sha256"):
            public += 1
        if left.get("native_boundary_sha256") != right.get("native_boundary_sha256"):
            native += 1
    final_rng = int(baseline_frames[-1].get("rng") != traced_frames[-1].get("rng"))
    return public, native, final_rng


def _actor_record(
    event: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    selector_return: dict[str, Any],
    seed: int,
) -> dict[str, Any] | None:
    actor = event.get("actor")
    if not isinstance(actor, dict) or type(actor.get("entity_id")) is not int or actor["entity_id"] <= 0:
        return None
    entity_id = actor["entity_id"]
    before_entities = before.get("entities", {}).get("entities") if isinstance(before.get("entities"), dict) else None
    after_entities = after.get("entities", {}).get("entities") if isinstance(after.get("entities"), dict) else None
    if not isinstance(before_entities, list) or not isinstance(after_entities, list):
        return None
    source = next((entity for entity in before_entities if isinstance(entity, dict) and entity.get("entity_id") == entity_id), None)
    if source is None:
        return None
    destination = next((entity for entity in after_entities if isinstance(entity, dict) and entity.get("entity_id") == entity_id), None)
    source_order = source.get("scheduler", {}).get("iteration_order") if isinstance(source.get("scheduler"), dict) else None
    if type(source_order) is not int:
        return None
    return {
        "schema": "gamebench.nethack.native_branch_candidate_record.v1",
        "seed": seed,
        "step": event["step"],
        "action": event["action"],
        "stable_entity_id": entity_id,
        "source_list_order": source_order,
        "source_turn": before["entities"].get("source_turn"),
        "pre_action_target_path_state": source.get("path_state"),
        "pre_action_player_state": before["player"].get("player"),
        "pre_action_rng_boundary": before.get("rng"),
        "mfndpos": {
            "caller": event.get("caller"),
            "actor_at_mfndpos_return": actor,
            "allowflags": event.get("allowflags"),
            "candidate_count": event.get("candidate_count"),
            "candidates": event.get("candidates"),
        },
        "selected_result": {
            # This is the unique return boundary for this exact mfndpos
            # invocation.  Do not replace it with the action-end state or a
            # list of same-actor calls: fast monsters may invoke dog_move
            # more than once in one player transition.
            "branch_selector_return": selector_return,
            "post_action_entity": destination,
            "post_action_rng_boundary": after.get("rng"),
        },
        "scope": "read-only exact-wheel source evidence; candidates were captured at mfndpos return before the caller selected one and are excluded from gold/scoring.",
    }


def _native_point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x, y = value.get("native_x"), value.get("native_y")
    if type(x) is not int or type(y) is not int or not (1 <= x <= 79 and 0 <= y <= 20):
        return None
    return x, y


def _valid_boundary_cell(value: Any) -> bool:
    """Accept only a complete portable raw-cell snapshot from LLDB.

    This validator intentionally does not infer terrain/object identity from
    a rendered plane or action-end source export.  It accepts exactly the
    ABI-tagged cell copied by the callback at a selector boundary.
    """

    if not isinstance(value, dict) or _native_point(value.get("coordinate")) is None:
        return False
    state, occupancy = value.get("state"), value.get("occupancy")
    if not isinstance(state, dict) or not isinstance(occupancy, dict):
        return False
    terrain = state.get("terrain")
    if not isinstance(terrain, dict) or any(type(terrain.get(name)) is not int for name in ("glyph", "type", "seen_vector", "flags")):
        return False
    if state.get("source_abi") != "nethack_3_6_6_darwin_arm64_level_rm_obj_v1" or state.get("object_stack_complete") is not True:
        return False
    objects = state.get("object_stack")
    if not isinstance(objects, list):
        return False
    object_ids: set[int] = set()
    for obj in objects:
        if not isinstance(obj, dict) or any(type(obj.get(name)) is not int for name in ("object_id", "object_type", "quantity")):
            return False
        object_id = obj["object_id"]
        if object_id <= 0 or object_id in object_ids:
            return False
        object_ids.add(object_id)
    occupant = occupancy.get("entity_id")
    return occupant is None or (type(occupant) is int and occupant > 0)


def _selector_boundary_is_causal(event: dict[str, Any], selector_return: dict[str, Any]) -> bool:
    """Require the four source/destination cells to name one invocation."""

    actor, after = event.get("actor"), selector_return.get("actor_after")
    if not isinstance(actor, dict) or not isinstance(after, dict):
        return False
    actor_id = actor.get("entity_id")
    if type(actor_id) is not int or actor_id <= 0 or after.get("entity_id") != actor_id:
        return False
    source_before = selector_return.get("source_underlay_before")
    source_after = selector_return.get("source_underlay_after")
    destination_before = selector_return.get("destination_underlay_before")
    destination_after = selector_return.get("destination_underlay_after")
    cells = (source_before, source_after, destination_before, destination_after)
    if not all(_valid_boundary_cell(cell) for cell in cells):
        return False
    source = _native_point(actor)
    destination = _native_point(after)
    if source is None or destination is None:
        return False
    if _native_point(source_before["coordinate"]) != source or _native_point(source_after["coordinate"]) != source:
        return False
    if _native_point(destination_before["coordinate"]) != destination or _native_point(destination_after["coordinate"]) != destination:
        return False
    if source_before["occupancy"].get("entity_id") != actor_id:
        return False
    if destination_after["occupancy"].get("entity_id") != actor_id:
        return False
    return True


def _merge_branch_records(trace_run: dict[str, Any], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    frames = trace_run.get("frames")
    if not isinstance(frames, list):
        raise ValueError("trace runner lacks frames")
    # A selector return names the candidate event whose caller-frame return
    # breakpoint produced it.  Do not reconstruct this relation from actor,
    # seed, coordinate, or temporal adjacency: fast monsters can make several
    # calls in one action and one selector can invoke another selector.
    selectors: dict[int, dict[str, Any]] = {}
    candidate_events: list[dict[str, Any]] = []
    candidate_ids: set[int] = set()
    errors = 0
    for event in events:
        if event.get("kind") == "trace_error":
            errors += 1
        elif event.get("kind") == "selector_return":
            actor = event.get("actor")
            selector = event.get("selector")
            bound_candidate_event_id = event.get("bound_candidate_event_id")
            if (
                isinstance(actor, dict)
                and type(event.get("step")) is int
                and type(actor.get("entity_id")) is int
                and selector in {"dog_move", "m_move"}
                and isinstance(event.get("actor_after"), dict)
                and type(bound_candidate_event_id) is int
                and bound_candidate_event_id >= 0
            ):
                if bound_candidate_event_id in selectors:
                    errors += 1
                else:
                    selectors[bound_candidate_event_id] = event
            else:
                errors += 1
        elif event.get("kind") == "mfndpos_candidates":
            event_id = event.get("event_id")
            if type(event_id) is not int or event_id < 0 or event_id in candidate_ids:
                errors += 1
            else:
                candidate_ids.add(event_id)
                candidate_events.append(event)
    # A return which names no candidate is not harmless extra telemetry: it
    # means an invocation boundary cannot be reconstructed uniquely.
    unmatched = sum(1 for event_id in selectors if event_id not in candidate_ids)
    records: list[dict[str, Any]] = []
    consumed_candidate_ids: set[int] = set()
    for event in sorted(candidate_events, key=lambda value: value.get("event_id", -1)):
        step = event.get("step")
        actor = event.get("actor")
        if type(step) is not int or not 1 <= step < len(frames) or not isinstance(actor, dict) or type(actor.get("entity_id")) is not int:
            unmatched += 1
            continue
        caller = event.get("caller")
        if caller not in {"dog_move", "m_move"}:
            unmatched += 1
            continue
        event_id = event.get("event_id")
        if type(event_id) is not int:
            unmatched += 1
            continue
        selector_return = selectors.get(event_id)
        if selector_return is None:
            unmatched += 1
            continue
        if event_id in consumed_candidate_ids:
            unmatched += 1
            continue
        if (
            selector_return.get("step") != step
            or selector_return.get("selector") != caller
            or not isinstance(selector_return.get("actor"), dict)
            or selector_return["actor"].get("entity_id") != actor["entity_id"]
        ):
            errors += 1
            continue
        if not _selector_boundary_is_causal(event, selector_return):
            errors += 1
            continue
        consumed_candidate_ids.add(event_id)
        seed = trace_run.get("seed")
        if type(seed) is not int:
            unmatched += 1
            continue
        record = _actor_record(event, frames[step - 1], frames[step], selector_return, seed)
        if record is None:
            unmatched += 1
        else:
            records.append(record)
    # One malformed, duplicate, or unbound callback makes the run
    # non-authoritative.  Do not retain a convenient subset of its records:
    # that would turn missing selector boundaries into a hidden denominator.
    if unmatched or errors:
        return [], unmatched, errors
    return records, unmatched, errors


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _toolchain_identity() -> dict[str, Any]:
    lldb = subprocess.run(["lldb", "--version"], text=True, capture_output=True, check=True).stdout.strip()
    return {
        "mode": "lldb_exact_wheel_read_only_breakpoints",
        "lldb": lldb,
        "python": sys.version,
        "platform": platform.platform(),
        "callback_sha256": _sha256_file(TRACE_CALLBACK),
        "runner_sha256": _sha256_file(Path(__file__)),
    }


def build_candidate(
    *,
    seeds: list[int],
    baseline_runs: list[dict[str, Any]],
    traced_runs: list[dict[str, Any]],
    replay_runs: list[dict[str, Any]],
    traced_events: list[list[dict[str, Any]]],
    replay_events: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    public_mismatches = native_mismatches = final_rng_mismatches = replay_mismatches = 0
    all_records: list[dict[str, Any]] = []
    unmatched = trace_errors = 0
    for baseline, traced, replay, first_events, second_events in zip(
        baseline_runs, traced_runs, replay_runs, traced_events, replay_events, strict=True
    ):
        public, native, rng = _mismatches(baseline, traced)
        public_mismatches += public
        native_mismatches += native
        final_rng_mismatches += rng
        records, case_unmatched, case_errors = _merge_branch_records(traced, first_events)
        replay_records, replay_unmatched, replay_errors = _merge_branch_records(replay, second_events)
        unmatched += case_unmatched + replay_unmatched
        trace_errors += case_errors + replay_errors
        if records != replay_records:
            replay_mismatches += 1
        all_records.extend(records)
    toolchain = _toolchain_identity()
    validity = {
        "inputs_selected_before_results": True,
        "trace_read_only_from_gold_perspective": True,
        "trace_excluded_from_gold_runtime": True,
        "trace_excluded_from_conformance_denominator": True,
        "zero_and_unmatched_events_fail_closed": bool(all_records) and unmatched == 0 and trace_errors == 0,
    }
    provisional_eligible = (
        len(seeds) > 0
        and bool(all_records)
        and public_mismatches == native_mismatches == final_rng_mismatches == replay_mismatches == 0
        and all(validity.values())
    )
    candidate = {
        "schema": GATE_SCHEMA,
        "subsystem": "nethack_mfndpos_candidate_selection_lldb_exact_wheel",
        "identity": {
            "source_commit": PINNED_SOURCE_COMMIT,
            "baseline_binary_sha256": PINNED_BINARY_SHA256,
            # LLDB attaches to the baseline wheel; this identity being equal
            # is intentional and proves no replacement build was substituted.
            "instrumented_binary_sha256": PINNED_BINARY_SHA256,
            "toolchain_identity_sha256": sha256_json(toolchain),
            "patch_sha256": sha256_json({"callback": _sha256_file(TRACE_CALLBACK), "runner": _sha256_file(Path(__file__))}),
            "instrumentation": toolchain,
        },
        "controls": {
            "independent_seed_count": len(seeds),
            "transition_count": sum(len(run.get("actions", [])) for run in baseline_runs),
            "trace_event_count": len(all_records),
            "public_observation_mismatch_count": public_mismatches,
            "native_boundary_mismatch_count": native_mismatches,
            "final_rng_state_mismatch_count": final_rng_mismatches,
            "trace_replay_mismatch_count": replay_mismatches,
            "unmatched_event_count": unmatched,
            "trace_error_count": trace_errors,
            "two_independent_runs_exact": replay_mismatches == 0 and unmatched == 0 and trace_errors == 0,
        },
        "validity": validity,
        # The gate checks a claimed result against its own independent
        # evaluation.  Claim eligibility only from the full local evidence,
        # then replace it with the gate result below.
        "instrumented_source_oracle_eligible": provisional_eligible,
        "source_export_eligible": provisional_eligible,
        "gold_implementation_eligible": False,
        "branch_records": all_records,
        "implementation_blocker": (
            "This exact-wheel trace establishes branch-local source evidence only. A general causal destination/collision rule "
            "must still pass an independent held-out frontier gate before either gold engine can change."
        ),
    }
    decision = evaluate_gate(candidate)
    candidate["instrumented_source_oracle_eligible"] = decision["instrumented_source_oracle_eligible"]
    candidate["source_export_eligible"] = decision["instrumented_source_oracle_eligible"]
    return candidate


def frontier_candidate(instrumented_candidate: dict[str, Any]) -> dict[str, Any]:
    """Describe the remaining non-promotion decision in the standard gate.

    ``mfndpos`` arrays are copied after a hero action has entered the native
    turn but before that invocation's caller selects a candidate.  That is
    exact branch evidence, not an action-bound pre-action gold input.  Keep
    the standard promotion gate deliberately negative until a genuinely
    general, cross-language causal destination/collision rule exists.
    """

    controls = instrumented_candidate.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("instrumented candidate lacks controls")
    trace_count = controls.get("trace_event_count")
    cases = controls.get("independent_seed_count")
    if type(trace_count) is not int or trace_count <= 0 or type(cases) is not int or cases <= 0:
        raise ValueError("instrumented candidate lacks positive source trace coverage")
    counterexamples = [
        {
            "code": "branch_local_mfndpos_not_action_prestate_rule",
            "evidence": (
                "mfndpos arrays are copied before their dog_move/m_move caller chooses, but only after the hero action has "
                "entered native turn processing; they are not an action-bound gold input."
            ),
        },
        {
            "code": "no_general_cross_language_destination_collision_candidate",
            "evidence": (
                "The exact-wheel probe observes source branch choices but supplies no destination/collision implementation "
                "to test independently in both gold languages."
            ),
        },
    ]
    return {
        "schema": FRONTIER_GATE_SCHEMA,
        "subsystem": "native_lldb_mfndpos_dog_move_m_move_branch_trace",
        "source_identity": {
            "nethack_commit": PINNED_SOURCE_COMMIT,
            "binary_sha256": PINNED_BINARY_SHA256,
            "instrumented_oracle_equivalence": instrumented_candidate.get("identity"),
        },
        "validity": {
            "source_identity_pinned": True,
            # Intentionally false: an array is created by mfndpos inside the
            # action, although the associated entity/player/RNG boundary was
            # frozen before it.  Do not collapse preselection into pre-action.
            "captured_pre_action_only": False,
            "no_future_or_reset_hydration": True,
            "no_seed_or_coordinate_lookup": True,
            "source_assertion_repeatable": controls.get("two_independent_runs_exact") is True,
            "python_rust_parity": False,
        },
        "source_assertions": {
            "comparison_count": trace_count,
            "error_count": int(controls.get("trace_error_count", 0)) + int(controls.get("unmatched_event_count", 0)),
            "scope": "exact-wheel branch-local source evidence only",
        },
        # Branch-local traces do not yet carry the independent before/after
        # underlay evidence needed to prove these conservation laws.  Keep
        # each denominator explicit and zero so the generic gate fails closed
        # rather than treating absence as success.
        "selector_conservation": {
            plane: {"comparison_count": 0, "error_count": 0}
            for plane in ("outcome_membership", "destination", "underlay")
        },
        "heldout": {
            "case_count": cases,
            "comparison_count": trace_count,
            "counterexample_count": len(counterexamples),
            "counterexamples": counterexamples,
            "baseline_first_divergence_step": None,
            "candidate_first_divergence_step": None,
            "baseline_error_count": 0,
            "candidate_error_count": 0,
        },
        "source_export_eligible": instrumented_candidate.get("instrumented_source_oracle_eligible") is True,
        "gold_implementation_eligible": False,
        "implementation_blocker": "No independently held-out, cross-language general destination/collision rule exists.",
    }


def _capture(args: argparse.Namespace) -> dict[str, Any]:
    if args.seeds:
        try:
            seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
        except ValueError as error:
            raise ValueError("--seeds must be a comma-separated integer list") from error
        if len(seeds) != len(set(seeds)):
            raise ValueError("--seeds must not repeat a seed")
    else:
        seeds = [args.seed + offset for offset in range(args.cases)]
    actions = list(args.actions.split(",")) if args.actions else list(DEFAULT_ACTIONS)
    if len(seeds) < 3:
        raise ValueError("branch trace needs at least three held-out seeds")
    if not actions or any(not action for action in actions):
        raise ValueError("branch trace needs non-empty preselected action names")
    baseline_runs: list[dict[str, Any]] = []
    traced_runs: list[dict[str, Any]] = []
    replay_runs: list[dict[str, Any]] = []
    traced_events: list[list[dict[str, Any]]] = []
    replay_events: list[list[dict[str, Any]]] = []
    with tempfile.TemporaryDirectory(prefix="nle-lldb-branch-") as directory:
        root = Path(directory)
        for index, seed in enumerate(seeds):
            baseline = root / f"baseline-{index}.json"
            runner(seed, actions, baseline, None)
            baseline_runs.append(json.loads(baseline.read_text()))
            for label, runs, event_sets in (("trace", traced_runs, traced_events), ("replay", replay_runs, replay_events)):
                output = root / f"{label}-{index}.json"
                state = root / f"{label}-{index}.state.json"
                events = root / f"{label}-{index}.events.jsonl"
                completed = _run_lldb(seed, actions, output, state, events)
                if completed.returncode != 0 or not output.is_file():
                    raise RuntimeError(
                        f"LLDB {label} run failed for seed {seed}: {completed.stdout[-1000:]} {completed.stderr[-1000:]}"
                    )
                runs.append(json.loads(output.read_text()))
                event_sets.append(_load_events(events))
    candidate = build_candidate(
        seeds=seeds,
        baseline_runs=baseline_runs,
        traced_runs=traced_runs,
        replay_runs=replay_runs,
        traced_events=traced_events,
        replay_events=replay_events,
    )
    decision = evaluate_gate(candidate)
    promotion = frontier_candidate(candidate)
    promotion_gate = evaluate_frontier_gate(promotion)
    def digests(run: dict[str, Any]) -> list[dict[str, Any]]:
        frames = run.get("frames")
        if not isinstance(frames, list):
            raise ValueError("equivalence run lacks frames")
        return [
            {
                "public_observation_sha256": frame.get("public_observation_sha256"),
                "native_boundary_sha256": frame.get("native_boundary_sha256"),
                "raw_rng_boundary_sha256": sha256_json(frame.get("rng")),
            }
            for frame in frames
        ]
    return {
        "schema": SCHEMA,
        "status": "eligible_source_only" if decision["instrumented_source_oracle_eligible"] else "rejected",
        "frontier_candidate": candidate,
        "equivalence_gate": decision,
        "promotion_candidate": promotion,
        "promotion_gate": promotion_gate,
        "equivalence_evidence": [
            {
                "seed": seed,
                "baseline": digests(baseline),
                "lldb_trace": digests(traced),
                "lldb_replay": digests(replay),
            }
            for seed, baseline, traced, replay in zip(seeds, baseline_runs, traced_runs, replay_runs, strict=True)
        ],
        # Prompt state is public terminal evidence, not an inferred source
        # rule.  Retain all three runs so the fixed SPACE resume is visibly
        # preselected and byte-exactly repeatable.
        "prompt_evidence": [
            {
                "seed": seed,
                "baseline": baseline.get("prompt_boundaries", []),
                "lldb_trace": traced.get("prompt_boundaries", []),
                "lldb_replay": replay.get("prompt_boundaries", []),
            }
            for seed, baseline, traced, replay in zip(seeds, baseline_runs, traced_runs, replay_runs, strict=True)
        ],
        "gold_implementation_eligible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", action="store_true", help="internal: execute one NLE run under LLDB")
    parser.add_argument("--seed", type=int, default=20261301)
    parser.add_argument("--cases", type=int, default=6)
    parser.add_argument("--seeds", help="optional explicit comma-separated seed split; overrides --seed/--cases")
    parser.add_argument("--actions", default=",".join(DEFAULT_ACTIONS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, help="optional standalone instrumented-oracle gate candidate")
    parser.add_argument("--promotion-candidate", type=Path, help="optional standalone standard frontier-promotion candidate")
    parser.add_argument("--promotion-gate", type=Path, help="optional frontier-promotion gate report")
    args = parser.parse_args()
    actions = args.actions.split(",") if args.actions else []
    if args.runner:
        state = Path(os.environ["NLE_BRANCH_TRACE_STATE"]) if os.environ.get("NLE_BRANCH_TRACE_STATE") else None
        runner(args.seed, actions, args.output, state)
        return
    result = _capture(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if args.candidate is not None:
        args.candidate.parent.mkdir(parents=True, exist_ok=True)
        args.candidate.write_text(json.dumps(result["frontier_candidate"], indent=2, sort_keys=True) + "\n")
    if args.promotion_candidate is not None:
        args.promotion_candidate.parent.mkdir(parents=True, exist_ok=True)
        args.promotion_candidate.write_text(json.dumps(result["promotion_candidate"], indent=2, sort_keys=True) + "\n")
    if args.promotion_gate is not None:
        args.promotion_gate.parent.mkdir(parents=True, exist_ok=True)
        args.promotion_gate.write_text(json.dumps(result["promotion_gate"], indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output.resolve())}, sort_keys=True))
    if result["status"] != "eligible_source_only":
        raise SystemExit("LLDB exact-wheel branch trace did not satisfy its fail-closed equivalence gate")


if __name__ == "__main__":
    main()
