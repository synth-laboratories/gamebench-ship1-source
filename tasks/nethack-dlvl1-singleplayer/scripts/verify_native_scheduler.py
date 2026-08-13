#!/usr/bin/env python3
"""Held-out native causal scheduler evidence, deliberately not a gold model.

Every input boundary is captured in this order:

1. full native entity list, movement points, list order, and complete grid;
2. exact two-lane ISAAC state;
3. one action from a seed- and coordinate-independent action plan;
4. immediate post-action copies of the same source state.

The resulting evidence can assert what the pinned source did.  It cannot
make a destination, pathing, collision, or AI policy eligible for either gold
lane.  The companion promotion candidate encodes that distinction explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset
from scripts.frontier_promotion_gate import SCHEMA as PROMOTION_SCHEMA, evaluate as evaluate_promotion
from scripts.native_scheduler_assertions import (
    causal_transition_evidence,
    destination_collision_rule_assessment,
    static_vacated_underlay_assertion,
)
from scripts.nle_native_entities import PinnedNleEntityReader, SOURCE_COMMIT, validate_native_presentation
from scripts.nle_native_player import PinnedNlePlayerReader
from scripts.nle_rng_state import PinnedNleRngReader, bounded_call_count


# This is an input-family sweep, not a result-selected route.  In particular,
# the same cardinal input is attempted for every held-out seed even when the
# source map makes it a bump rather than a hero move.
DEFAULT_ACTIONS = ("Command.SEARCH", "MiscDirection.WAIT", "CompassDirection.E", "Command.SEARCH", "MiscDirection.WAIT")


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _new_env() -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(
        character="val-hum-fem-law",
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def _action_ids(env: Any, action_names: tuple[str, ...]) -> list[dict[str, Any]]:
    table = {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}
    unknown = [name for name in action_names if name not in table]
    if unknown:
        raise AssertionError(f"pinned NLE action table lacks: {', '.join(unknown)}")
    return [{"action_id": table[name], "action_name": name} for name in action_names]


def _rng_boundary(reader: PinnedNleRngReader, before: Any, after: Any) -> dict[str, Any]:
    """Prove the exact per-lane chronology from raw ISAAC64 copies.

    The reader replays each count against a private ctypes clone using the
    pinned binary's own ISAAC64 routine.  It never invokes a draw on NLE's
    live RNG and it is assertion evidence, never gold-engine state.
    """

    boundary: dict[str, Any] = {
        "before": before.public_record(),
        "after": after.public_record(),
        "exact_state_boundary": True,
    }
    chronology_ownership: dict[str, str] = {}
    for lane in ("core", "display"):
        exact = reader.exact_call_count(before, after, lane, max_draws=512)
        bounded = bounded_call_count(before, after, lane)
        if exact != bounded:
            raise AssertionError(
                f"{lane} RNG chronology disagrees: raw-state replay found {exact}, index bound found {bounded}"
            )
        boundary[f"{lane}_calls_exact_raw_state"] = exact
        boundary[f"{lane}_calls_bounded_index"] = bounded
        chronology_ownership[lane] = "pinned_native_isaac64_private_snapshot_replay_assertion_only"
    boundary["chronology_ownership"] = chronology_ownership
    return boundary


def _one_run(seed: int, *, action_names: tuple[str, ...]) -> dict[str, Any]:
    import nle

    env = _new_env()
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        raw = normalise_reset(env.reset())
        reader = PinnedNleEntityReader(env.nethack)
        player = PinnedNlePlayerReader(env.nethack)
        rng = PinnedNleRngReader(env.nethack)
        validate_native_presentation(reader.snapshot(), raw, nle.nethack)
        player.validate_against_public_pre_action(player.snapshot(), raw)
        actions = _action_ids(env, action_names)
        source_case = f"heldout-core-{seed}"
        records: list[dict[str, Any]] = []
        for step, action in enumerate(actions, start=1):
            # The entire underlay/occupancy grid is frozen before the action.
            # No code below selects a seed-specific coordinate or reads a
            # later screen to repair the source transition.
            before = reader.snapshot().public_record()
            before_player = player.snapshot().public_record()
            before_cells = reader.source_cells()
            before_rng = rng.snapshot()
            raw_after, _, terminated, info = env.step(action["action_id"])
            after = reader.snapshot().public_record()
            after_player = player.snapshot().public_record()
            after_cells = reader.source_cells()
            after_rng = rng.snapshot()
            causal = causal_transition_evidence(
                before,
                after,
                before_cells=before_cells,
                after_cells=after_cells,
                source_case=source_case,
                action=action,
            )
            if causal["status"] != "pass":
                raise AssertionError(causal["errors"])
            after_index = {(cell["x"], cell["y"]): cell for cell in after_cells}
            underlay = static_vacated_underlay_assertion(
                {"events": causal["records"]},
                after_cells=after_index,
                after_glyphs=raw_after["glyphs"].tolist(),
                after_chars=raw_after["chars"].tolist(),
            )
            if underlay["status"] != "pass":
                raise AssertionError(underlay["errors"])
            records.append(
                {
                    "step": step,
                    "captured_before_action": True,
                    "action": action,
                    "before_source_step": before["source_turn"],
                    "after_source_step": after["source_turn"],
                    "hero_scheduler": {
                        "before": before_player["player"]["scheduler"],
                        "after": after_player["player"]["scheduler"],
                    },
                    "before_full_grid_sha256": _json_hash(before_cells),
                    "after_full_grid_sha256": _json_hash(after_cells),
                    "causal_transition": causal,
                    "underlay": underlay,
                    "rng": _rng_boundary(rng, before_rng, after_rng),
                    "terminated": bool(terminated),
                    # Gym-era NLE returns ``(observation, reward, done,
                    # info)`` rather than Gymnasium's terminated/truncated
                    # pair.  Treating its nonempty info dictionary as a
                    # truncation would silently discard every source case.
                    "truncated": False,
                    "end_status": str(info.get("end_status", "unknown")) if isinstance(info, dict) else "unknown",
                }
            )
            if terminated:
                break
        if len(records) != len(actions):
            raise AssertionError("held-out action plan terminated before all causal boundaries were captured")
        return {"seed": seed, "source_case": source_case, "steps": records}
    finally:
        env.close()


def _source_citations() -> dict[str, Any]:
    """Pinned-source call-path locations checked before making any claim."""

    return {
        "source_commit": SOURCE_COMMIT,
        "action_to_scheduler": [
            {"file": "src/allmain.c", "lines": [99, 125], "role": "a time-consuming hero action enters movemon and replenishes monster movement"},
            {"file": "src/mon.c", "lines": [720, 779], "role": "movemon walks fmon, skips movement < NORMAL_SPEED, then debits movement"},
        ],
        "destination_and_collision_not_reduced": [
            {"file": "src/monmove.c", "lines": [369, 1222], "role": "dochug/m_move depends on target state and can route monster-on-monster attacks"},
            {"file": "src/dogmove.c", "lines": [862, 1207], "role": "pet dog_move uses mfndpos, pet state, objects, and allowed move flags"},
        ],
        "conclusion": "The call path supports a movemon-pass eligibility threshold after allocation, not an action-boundary threshold or a sufficient destination/collision policy.",
    }


def _promotion_candidate(
    *,
    cases: list[dict[str, Any]],
    rule_assessment: dict[str, Any],
    source_error_count: int,
    repeated_exact: bool,
) -> dict[str, Any]:
    records = [
        record
        for case in cases
        for step in case["steps"]
        for record in step["causal_transition"]["records"]
    ]
    source_comparisons = len(records) + sum(
        int(step["underlay"]["comparisons"])
        for case in cases
        for step in case["steps"]
    )
    boundary_ambiguities = sum(
        len(step["causal_transition"].get("boundary_ambiguities", []))
        for case in cases
        for step in case["steps"]
    )
    counterexamples = sum(
        len(rule_assessment[name].get("sufficiency_counterexamples", []))
        for name in ("movement_points_threshold",)
    )
    return {
        "schema": PROMOTION_SCHEMA,
        "subsystem": "native_dynamic_entity_scheduler_destination_collision_underlay",
        "validity": {
            "source_identity_pinned": True,
            "captured_pre_action_only": True,
            "no_future_or_reset_hydration": True,
            "no_seed_or_coordinate_lookup": True,
            "source_assertion_repeatable": repeated_exact,
            # There is intentionally no behavior candidate in either gold
            # language. Do not call baseline parity a scheduler promotion.
            "python_rust_parity": False,
        },
        "source_assertions": {"comparison_count": source_comparisons, "error_count": source_error_count, "boundary_ambiguity_count": boundary_ambiguities},
        "heldout": {
            "case_count": len(cases),
            "comparison_count": len(records),
            "counterexample_count": counterexamples,
            "baseline_first_divergence_step": None,
            "candidate_first_divergence_step": None,
            "baseline_error_count": 0,
            "candidate_error_count": 0,
            "first_divergence_contract": "No candidate exists. Any future candidate must report its first held-out divergence, not only totals.",
        },
        "gold_implementation_eligible": False,
        "blocker": rule_assessment["blocker"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20261101, help="first held-out core seed; no result-specific seed selection")
    parser.add_argument("--actions", default=",".join(DEFAULT_ACTIONS), help="comma-separated pinned action names, chosen independently of seed and coordinates")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--promotion-candidate", type=Path, help="standalone frontier_promotion_gate.v1 candidate path")
    args = parser.parse_args()
    action_names = tuple(name.strip() for name in args.actions.split(",") if name.strip())
    if args.cases < 3 or len(action_names) < 2:
        raise SystemExit("scheduler verifier requires at least three held-out seeds and two seed-independent actions")
    if len(set(action_names)) < 2:
        raise SystemExit("scheduler verifier requires at least two distinct action names; WAIT-only probes cannot establish action-boundary robustness")

    first = [_one_run(args.seed + offset, action_names=action_names) for offset in range(args.cases)]
    second = [_one_run(args.seed + offset, action_names=action_names) for offset in range(args.cases)]
    repeated_exact = first == second
    if not repeated_exact:
        raise AssertionError("native causal scheduler/RNG evidence did not exactly repeat across independent held-out runs")

    transitions = [step["causal_transition"] for case in first for step in case["steps"]]
    rule_assessment = destination_collision_rule_assessment(transitions)
    source_error_count = sum(
        len(step["causal_transition"]["errors"]) + len(step["underlay"]["errors"])
        for case in first
        for step in case["steps"]
    )
    # Each action-bound boundary contains both independently copied ISAAC64
    # lanes.  ``_rng_boundary`` has already replayed every exact count and
    # compared it with the raw index bound above; keep the aggregate derived
    # from those records so an RNG candidate emitter never trusts a hand-set
    # summary total.
    exact_rng_lane_comparisons = sum(
        2
        for case in first
        for step in case["steps"]
        if all(
            type(step["rng"].get(f"{lane}_calls_exact_raw_state")) is int
            and type(step["rng"].get(f"{lane}_calls_bounded_index")) is int
            and step["rng"][f"{lane}_calls_exact_raw_state"] == step["rng"][f"{lane}_calls_bounded_index"]
            for lane in ("core", "display")
        )
    )
    if exact_rng_lane_comparisons != 2 * sum(len(case["steps"]) for case in first):
        raise AssertionError("native scheduler report has an unauditable raw ISAAC64 action boundary")
    candidate = _promotion_candidate(
        cases=first,
        rule_assessment=rule_assessment,
        source_error_count=source_error_count,
        repeated_exact=repeated_exact,
    )
    gate = evaluate_promotion(candidate)
    if gate["gold_implementation_eligible"]:
        raise AssertionError("assertion-only native evidence unexpectedly promoted a gold scheduler")
    if not gate["source_assertion_eligible"]:
        raise AssertionError(f"native source assertions are not eligible: {gate['failures']}")

    report = {
        "schema": "gamebench.nethack.native_causal_scheduler_probe.v2",
        "status": "assertion_only_gold_blocked",
        "heldout_seed_count": len(first),
        "action_plan": list(action_names),
        "action_plan_contract": "The identical action-name sequence is used for every seed; no seed, coordinate, destination, or future source state selects an input.",
        "two_independent_runs_exact": repeated_exact,
        "source_assertion_eligible": gate["source_assertion_eligible"],
        "gold_scheduler_pathing_eligible": False,
        "gold_implementation_eligible": gate["gold_implementation_eligible"],
        "exact_rng_lane_comparisons": exact_rng_lane_comparisons,
        "boundary_ambiguity_count": candidate["source_assertions"]["boundary_ambiguity_count"],
        "rng_eligibility": {
            "source_assertion_eligible": bool(repeated_exact and exact_rng_lane_comparisons > 0),
            "gold_rng_or_branch_implementation_eligible": False,
            "scope": "Exact full-state core/display boundary counts only; neither a source call-site label nor a gold runtime input.",
        },
        "source_citations": _source_citations(),
        "rule_assessment": rule_assessment,
        "promotion_candidate": candidate,
        "promotion_gate": gate,
        "cases": first,
        "blocker": rule_assessment["blocker"],
    }
    candidate_path = args.promotion_candidate or args.report.with_name(f"{args.report.stem}_promotion_candidate.json")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    candidate_path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "cases": len(first),
                "source_assertion_eligible": report["source_assertion_eligible"],
                "gold_implementation_eligible": report["gold_implementation_eligible"],
                "report": str(args.report.resolve()),
                "promotion_candidate": str(candidate_path.resolve()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
