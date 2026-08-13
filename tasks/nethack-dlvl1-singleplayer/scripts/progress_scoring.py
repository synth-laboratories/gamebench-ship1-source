"""Pure, fail-closed scoring helpers for diagnostic live-fuzz reports."""

from __future__ import annotations

from collections import Counter
from typing import Any


def source_trace_metrics(
    reports: list[dict[str, Any]],
    action_counts: dict[str, int],
    *,
    lanes_key: str,
) -> dict[str, Any]:
    """Score only source-eligible transitions, never lane-multiplied turns.

    Eligibility is derived from the NLE source tape, not the own-engine lane;
    disagreement between Python and Rust is therefore a malformed report and
    fails closed rather than letting ``max`` hide a denominator error.
    """

    matched = 0
    possible = 0
    unjudgeable = 0
    failed_cases = 0
    classes: Counter[str] = Counter()
    for case in reports:
        fixture_id = str(case["fixture_id"])
        lanes = case[lanes_key]
        if not isinstance(lanes, list) or not lanes:
            raise ValueError(f"{fixture_id}: no lanes for {lanes_key}")
        eligibility_counts = {
            (
                int(lane["source_state_eligibility_v1"]["judgeable_action_steps"]),
                int(lane["source_state_eligibility_v1"]["unjudgeable_action_steps"]),
            )
            for lane in lanes
        }
        if len(eligibility_counts) != 1:
            raise ValueError(f"{fixture_id}: source-state eligibility differs across lanes")
        judgeable, unknown = eligibility_counts.pop()
        action_count = int(action_counts[fixture_id])
        if judgeable < 0 or unknown < 0 or judgeable + unknown != action_count:
            raise ValueError(f"{fixture_id}: invalid source-state eligibility denominator")
        possible += judgeable
        unjudgeable += unknown
        differences = [
            lane["strict_snapshot_v1"].get("first_difference")
            for lane in lanes
            if lane["strict_snapshot_v1"].get("first_difference")
        ]
        if differences:
            failed_cases += 1
            # Difference step N follows N actions.  Its action is not a match;
            # never credit an action beyond the eligible prefix.
            matched += max(0, min(judgeable, min(int(difference["step"]) for difference in differences) - 1))
        else:
            matched += judgeable
        unique = {
            (
                mismatch["class"],
                mismatch["path"],
                repr(mismatch.get("expected")),
                repr(mismatch.get("actual")),
            )
            for lane in lanes
            for mismatch in lane["first_divergent_step_census_v1"]["mismatches"]
        }
        classes.update(item[0] for item in unique)
    return {
        "failed_cases": failed_cases,
        "turns": possible,
        "unjudgeable_turns": unjudgeable,
        "pixel_errors": classes["pixel"],
        "state_errors": sum(count for name, count in classes.items() if name != "pixel"),
        "score": round(100.0 * matched / possible, 1) if possible else None,
    }


def source_behavior_result(metrics: dict[str, Any]) -> str:
    """A source-unknown campaign has a distinct result, never a pass."""

    if int(metrics["failed_cases"]):
        return "divergences_found"
    return "partial_unjudgeable" if int(metrics["unjudgeable_turns"]) else "pass"
