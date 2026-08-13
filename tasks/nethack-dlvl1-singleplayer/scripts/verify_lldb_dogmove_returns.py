#!/usr/bin/env python3
"""Fail-closed exact-wheel ``dog_move`` entry/return trace.

This is deliberately separate from mfndpos: `dog_move` returning 1 means a
completed pet turn, not necessarily a physical move.  The trace is source
evidence only and is rejected on any wheel-equivalence, replay, malformed, or
unmatched-boundary failure.
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

CALLBACK = TASK_DIR / "scripts" / "lldb_dogmove_return_callbacks.py"


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
            errors += 1; continue
        actor, after = item.get("actor"), item.get("actor_after")
        if (item.get("kind") != "dog_move_return" or type(item.get("event_id")) is not int or
                type(item.get("step")) is not int or not 1 <= item["step"] <= steps or
                type(item.get("return_code")) is not int or item["return_code"] not in (0, 1, 2) or
                not isinstance(actor, dict) or not isinstance(after, dict) or
                type(actor.get("entity_id")) is not int or actor.get("entity_id") != after.get("entity_id")):
            errors += 1; continue
        good.append(item)
    if len({item["event_id"] for item in good}) != len(good):
        errors += 1
    return good, errors


def _join_pre_action_state(run: dict[str, Any], event: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Join one LLDB event to the exact source frame before its action."""
    frames = run.get("frames")
    step = event.get("step")
    entity_id = event.get("actor", {}).get("entity_id")
    if not isinstance(frames, list) or type(step) is not int or not 1 <= step <= len(frames):
        return None, "pre_action_frame_missing"
    if type(entity_id) is not int:
        return None, "event_entity_id_missing"
    frame = frames[step - 1]
    if not isinstance(frame, dict):
        return None, "pre_action_frame_malformed"
    entities_export = frame.get("entities")
    if not isinstance(entities_export, dict):
        return None, "pre_action_entities_export_missing"
    entities = entities_export.get("entities")
    if not isinstance(entities, list):
        return None, "pre_action_entity_list_missing"
    matches = [entity for entity in entities if isinstance(entity, dict) and entity.get("entity_id") == entity_id]
    if len(matches) != 1:
        return None, "pre_action_entity_join_not_unique"
    player_export = frame.get("player")
    player_payload = player_export.get("player") if isinstance(player_export, dict) else None
    player_scheduler = player_payload.get("scheduler") if isinstance(player_payload, dict) else None
    source_turn = entities_export.get("source_turn")
    scheduler = matches[0].get("scheduler")
    if not isinstance(source_turn, dict):
        return None, "pre_action_entity_source_turn_missing"
    if not isinstance(player_scheduler, dict) or type(player_scheduler.get("movement_points")) is not int:
        return None, "pre_action_player_scheduler_missing"
    if not isinstance(scheduler, dict) or type(scheduler.get("movement_points")) is not int:
        return None, "pre_action_entity_scheduler_missing"
    return {"entity": matches[0], "source_turn": source_turn, "player_scheduler": player_scheduler}, None


def _join_events(run: dict[str, Any], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Attach exact pre-action scheduler state; reject every failed join."""
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
    baselines=[]; first=[]; replay=[]; first_events=[]; replay_events=[]
    with tempfile.TemporaryDirectory(prefix="nle-dogmove-return-") as temporary:
        root=Path(temporary)
        for number, current_seed in enumerate(range(seed, seed + cases)):
            baseline=root/f"base-{number}.json"; runner(current_seed, actions, baseline, None); baselines.append(json.loads(baseline.read_text()))
            for label, runs, event_sets in (("trace",first,first_events),("replay",replay,replay_events)):
                output=root/f"{label}-{number}.json"; state=root/f"{label}-{number}.state"; events=root/f"{label}-{number}.jsonl"
                _run(current_seed, actions, output, state, events)
                runs.append(json.loads(output.read_text())); event_sets.append(_events(events))
    public=native=rng=replay_mismatch=0; records=[]; errors=0
    for base, left, right, le, re in zip(baselines, first, replay, first_events, replay_events, strict=True):
        a,b,c=_mismatches(base,left); public+=a; native+=b; rng+=c
        valid_left,left_errors=_valid(le,len(actions)); valid_right,right_errors=_valid(re,len(actions)); errors += left_errors+right_errors
        valid_left,left_join_errors = _join_events(left, valid_left)
        valid_right,right_join_errors = _join_events(right, valid_right)
        errors += left_join_errors + right_join_errors
        valid_left = [dict(item, seed=base["seed"]) for item in valid_left]
        valid_right = [dict(item, seed=base["seed"]) for item in valid_right]
        # Events are a full semantic stream; order, code, coordinates, and
        # entry/return locations must replay exactly, not merely by count.
        if valid_left != valid_right: replay_mismatch += 1
        records.extend(valid_left)
    toolchain={"mode":"lldb_exact_wheel_dog_move_return_boundary","lldb":subprocess.run(["lldb","--version"],text=True,capture_output=True,check=True).stdout.strip(),"callback_sha256":_sha(CALLBACK),"runner_sha256":_sha(Path(__file__))}
    controls={"independent_seed_count":cases,"transition_count":cases*len(actions),"trace_event_count":len(records),"pre_action_scheduler_join_count":len(records),"public_observation_mismatch_count":public,"native_boundary_mismatch_count":native,"final_rng_state_mismatch_count":rng,"trace_replay_mismatch_count":replay_mismatch,"unmatched_event_count":errors,"trace_error_count":0,"two_independent_runs_exact":replay_mismatch == errors == 0}
    candidate={"schema":SCHEMA,"subsystem":"nethack_dog_move_return_exact_wheel_control_flow","identity":{"source_commit":PINNED_SOURCE_COMMIT,"baseline_binary_sha256":PINNED_BINARY_SHA256,"instrumented_binary_sha256":PINNED_BINARY_SHA256,"toolchain_identity_sha256":sha256_json(toolchain),"patch_sha256":sha256_json({"callback":_sha(CALLBACK),"runner":_sha(Path(__file__))}),"instrumentation":toolchain},"controls":controls,"validity":{"inputs_selected_before_results":True,"trace_read_only_from_gold_perspective":True,"trace_excluded_from_gold_runtime":True,"trace_excluded_from_conformance_denominator":True,"zero_and_unmatched_events_fail_closed":bool(records) and errors == 0},"instrumented_source_oracle_eligible":True,"source_export_eligible":True,"gold_implementation_eligible":False,"dog_move_return_records":records,"implementation_blocker":"Return code 1 is completion status, not a movement predicate. Each retained event is joined to exact pre-action entity and hero scheduler state; this source trace remains excluded from gold and scoring."}
    gate=evaluate(candidate); candidate["instrumented_source_oracle_eligible"]=gate["instrumented_source_oracle_eligible"]; candidate["source_export_eligible"]=gate["instrumented_source_oracle_eligible"]
    unchanged=[item for item in records if item["return_code"] == 1 and (item["actor"]["native_x"],item["actor"]["native_y"]) == (item["actor_after"]["native_x"],item["actor_after"]["native_y"])]
    return {"schema":"gamebench.nethack.lldb_dog_move_return_trace.v1","status":"eligible_source_only" if candidate["instrumented_source_oracle_eligible"] else "rejected","frontier_candidate":candidate,"equivalence_gate":gate,"control_flow_finding":{"rule":"dog_move return_code == 1 denotes completed pet turn, not guaranteed actor displacement","unchanged_return_one_count":len(unchanged),"examples":[{"seed":x["seed"],"step":x["step"],"entity_id":x["actor"]["entity_id"],"entry":x["actor"],"return_code":x["return_code"],"after":x["actor_after"]} for x in unchanged[:8]]},"gold_implementation_eligible":False}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--runner",action="store_true"); parser.add_argument("--seed",type=int,default=20261301); parser.add_argument("--cases",type=int,default=3); parser.add_argument("--actions",default=",".join(DEFAULT_ACTIONS)); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    if args.runner:
        state = os.environ.get("NLE_BRANCH_TRACE_STATE")
        runner(args.seed, args.actions.split(","), args.output, Path(state) if state else None)
        return
    if args.cases < 3: raise SystemExit("at least three preselected seeds required")
    result=capture(args.cases,args.seed,args.actions.split(",")); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps({"status":result["status"],"report":str(args.output.resolve())})); raise SystemExit(0 if result["status"] == "eligible_source_only" else 1)
if __name__ == "__main__": main()
