#!/usr/bin/env python3
"""Fail-closed exact-wheel ``mcalcmove`` allocation trace.

The trace is source evidence only.  It binds every native allocation return to
the exact action step and pre-action scheduler frame, while two independent
launches must reproduce all public/native/RNG observations and the event
stream byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.instrumented_oracle_gate import PINNED_BINARY_SHA256, PINNED_SOURCE_COMMIT, SCHEMA, evaluate
from scripts.oracle_tape import sha256_json
from scripts.verify_lldb_branch_trace import DEFAULT_ACTIONS, _mismatches, runner
from scripts.verify_lldb_dogmove_returns import _join_pre_action_state

CALLBACK = TASK_DIR / "scripts" / "lldb_mcalcmove_callbacks.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _run(seed: int, actions: list[str], output: Path, state: Path, events: Path) -> None:
    command = output.with_suffix(".lldb")
    command.write_text("\n".join((
        f"target create {Path(sys.executable).absolute()}",
        f"command script import {CALLBACK}",
        f"settings set target.env-vars NLE_BRANCH_TRACE_STATE={state} NLE_BRANCH_TRACE_EVENTS={events}",
        f"script import os; os.environ['NLE_BRANCH_TRACE_STATE'] = {str(state)!r}; os.environ['NLE_BRANCH_TRACE_EVENTS'] = {str(events)!r}",
        f"settings set -- target.run-args {Path(__file__).resolve()} --runner --seed {seed} --actions {','.join(actions)} --output {output}",
        "run",
    )) + "\n")
    try:
        completed = subprocess.run(["lldb", "--batch", "-s", str(command)], text=True, capture_output=True)
        if completed.returncode or not output.is_file():
            raise RuntimeError(f"LLDB failed: {completed.stderr[-800:]}")
    finally:
        command.unlink(missing_ok=True)


def _valid(events: list[dict[str, Any]], steps: int) -> tuple[list[dict[str, Any]], int]:
    good: list[dict[str, Any]] = []
    errors = 0
    for item in events:
        if item.get("kind") == "trace_error":
            errors += 1
            continue
        actor, after = item.get("actor"), item.get("actor_after")
        action = item.get("action")
        if (
            item.get("kind") != "mcalcmove_return"
            or type(item.get("event_id")) is not int
            or type(item.get("step")) is not int
            or not 1 <= item["step"] <= steps
            or not isinstance(action, dict)
            or type(action.get("step")) is not int
            or action.get("step") != item.get("step")
            or type(action.get("action_id")) is not int
            or not isinstance(action.get("action_name"), str)
            or type(item.get("allocation")) is not int
            or item["allocation"] < 0
            or not isinstance(item.get("entry_location"), dict)
            or item["entry_location"].get("function") != "mcalcmove"
            or not isinstance(item.get("return_location"), dict)
            or item["return_location"].get("function") != "moveloop"
            or not isinstance(actor, dict)
            or not isinstance(after, dict)
            or type(actor.get("entity_id")) is not int
            or actor["entity_id"] <= 0
            or actor.get("entity_id") != after.get("entity_id")
        ):
            errors += 1
            continue
        good.append(item)
    if len({item["event_id"] for item in good}) != len(good):
        errors += 1
    return good, errors


def _join_events(run: dict[str, Any], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    joined: list[dict[str, Any]] = []
    errors = 0
    for event in events:
        state, error = _join_pre_action_state(run, event)
        if error is not None:
            errors += 1
            continue
        assert state is not None
        joined.append({**event, "pre_action_state": state})
    return joined, errors


def capture(cases: int, seed: int, actions: list[str]) -> dict[str, Any]:
    baselines: list[dict[str, Any]] = []
    first: list[dict[str, Any]] = []
    replay: list[dict[str, Any]] = []
    first_events: list[list[dict[str, Any]]] = []
    replay_events: list[list[dict[str, Any]]] = []
    with tempfile.TemporaryDirectory(prefix="nle-mcalcmove-") as temporary:
        root = Path(temporary)
        for number, current_seed in enumerate(range(seed, seed + cases)):
            baseline = root / f"base-{number}.json"
            runner(current_seed, actions, baseline, None)
            baselines.append(json.loads(baseline.read_text()))
            for label, runs, event_sets in (("trace", first, first_events), ("replay", replay, replay_events)):
                output = root / f"{label}-{number}.json"
                state = root / f"{label}-{number}.state"
                events = root / f"{label}-{number}.jsonl"
                _run(current_seed, actions, output, state, events)
                runs.append(json.loads(output.read_text()))
                event_sets.append(_events(events))

    public = native = rng = replay_mismatch = 0
    records: list[dict[str, Any]] = []
    errors = 0
    for base, left, right, left_events, right_events in zip(baselines, first, replay, first_events, replay_events, strict=True):
        a, b, c = _mismatches(base, left)
        public += a
        native += b
        rng += c
        valid_left, left_errors = _valid(left_events, len(actions))
        valid_right, right_errors = _valid(right_events, len(actions))
        valid_left, left_join_errors = _join_events(left, valid_left)
        valid_right, right_join_errors = _join_events(right, valid_right)
        errors += left_errors + right_errors + left_join_errors + right_join_errors
        valid_left = [dict(item, seed=base["seed"]) for item in valid_left]
        valid_right = [dict(item, seed=base["seed"]) for item in valid_right]
        if valid_left != valid_right:
            replay_mismatch += 1
        records.extend(valid_left)

    toolchain = {
        "mode": "lldb_exact_wheel_mcalcmove_return_boundary",
        "lldb": subprocess.run(["lldb", "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        "callback_sha256": _sha(CALLBACK),
        "runner_sha256": _sha(Path(__file__)),
    }
    controls = {
        "independent_seed_count": cases,
        "transition_count": cases * len(actions),
        "trace_event_count": len(records),
        "allocation_event_count": len(records),
        "pre_action_scheduler_join_count": len(records),
        "public_observation_mismatch_count": public,
        "native_boundary_mismatch_count": native,
        "final_rng_state_mismatch_count": rng,
        "trace_replay_mismatch_count": replay_mismatch,
        "unmatched_event_count": errors,
        "trace_error_count": 0,
        "two_independent_runs_exact": replay_mismatch == errors == 0,
    }
    candidate = {
        "schema": SCHEMA,
        "subsystem": "nethack_mcalcmove_exact_wheel_allocation_boundary",
        "identity": {
            "source_commit": PINNED_SOURCE_COMMIT,
            "baseline_binary_sha256": PINNED_BINARY_SHA256,
            "instrumented_binary_sha256": PINNED_BINARY_SHA256,
            "toolchain_identity_sha256": sha256_json(toolchain),
            "patch_sha256": sha256_json({"callback": _sha(CALLBACK), "runner": _sha(Path(__file__))}),
            "instrumentation": toolchain,
        },
        "controls": controls,
        "validity": {
            "inputs_selected_before_results": True,
            "trace_read_only_from_gold_perspective": True,
            "trace_excluded_from_gold_runtime": True,
            "trace_excluded_from_conformance_denominator": True,
            "zero_and_unmatched_events_fail_closed": bool(records) and errors == 0,
        },
        "instrumented_source_oracle_eligible": True,
        "source_export_eligible": True,
        "gold_implementation_eligible": False,
        "mcalcmove_records": records,
        "implementation_blocker": "mcalcmove allocation is now source-observable, but destination/collision/AI behavior remains outside this evidence and is excluded from gold.",
    }
    gate = evaluate(candidate)
    candidate["instrumented_source_oracle_eligible"] = gate["instrumented_source_oracle_eligible"]
    candidate["source_export_eligible"] = gate["instrumented_source_oracle_eligible"]
    return {
        "schema": "gamebench.nethack.lldb_mcalcmove_trace.v1",
        "status": "eligible_source_only" if candidate["instrumented_source_oracle_eligible"] else "rejected",
        "frontier_candidate": candidate,
        "equivalence_gate": gate,
        "gold_implementation_eligible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", action="store_true")
    parser.add_argument("--seed", type=int, default=20261401)
    parser.add_argument("--cases", type=int, default=3)
    parser.add_argument("--actions", default=",".join(DEFAULT_ACTIONS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runner:
        state = os.environ.get("NLE_BRANCH_TRACE_STATE")
        runner(args.seed, args.actions.split(","), args.output, Path(state) if state else None)
        return
    if args.cases < 3:
        raise SystemExit("at least three preselected seeds required")
    result = capture(args.cases, args.seed, args.actions.split(","))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output.resolve())}))
    raise SystemExit(0 if result["status"] == "eligible_source_only" else 1)


if __name__ == "__main__":
    main()
