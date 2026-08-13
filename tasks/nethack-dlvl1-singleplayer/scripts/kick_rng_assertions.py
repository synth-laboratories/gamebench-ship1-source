"""Fail-closed eligibility for the narrow wall-KICK oracle contract.

NLE's public observations can prove an immediate kick into a reset-visible
static wall has a particular message and one consumed turn.  They do *not*
expose NetHack's internal random-number state, its random-call chronology, or
the state/actions of dynamic creatures that may act during a turn.  Keep those
two claims separate so a seeded replay never turns into a guessed RNG model.
"""

from __future__ import annotations

from typing import Any


WALL_KICK_RAW = "Ouch!  That hurts!"
WALL_KICK_NORMALIZED = "Ouch! That hurts!"
STATIC_WALL_PROVENANCE = "observed_surface_static"


def wall_kick_eligibility(
    *,
    target: dict[str, Any],
    reset_turn: int | None,
    pre_kick_turn: int | None,
    action_history: list[str],
) -> dict[str, Any]:
    """Return independently scored message and injury eligibility.

    A no-turn history is deliberately stricter than an empty action list: the
    source state must still be at the reset turn.  This rejects prompt cycles
    or any future history where a hidden random call may already have occurred.
    """

    requirements = [
        {
            "key": "target_surface",
            "expected": "static_wall",
            "actual": str(target.get("class", "")),
            "provenance": str(target.get("provenance", "unknown")),
        },
        {
            "key": "target_identity",
            "expected": "not_applicable",
            "actual": str(target.get("identity_status", "")),
            "provenance": "observed_surface_static",
        },
        {
            "key": "pre_kick_turn",
            "expected": reset_turn,
            "actual": pre_kick_turn,
            "provenance": "observed_blstats_time",
        },
        {
            "key": "action_history",
            "expected": "no_prior_consumed_turn",
            "actual": list(action_history),
            "provenance": "recorded_input_tape",
        },
    ]
    message_eligible = (
        target.get("class") == "wall"
        and target.get("provenance") == STATIC_WALL_PROVENANCE
        and target.get("identity_status") == "not_applicable"
        and reset_turn is not None
        and pre_kick_turn == reset_turn
        and not action_history
    )
    return {
        "schema": "gamebench.nethack.wall_kick_eligibility.v1",
        "message": {
            "status": "eligible" if message_eligible else "unjudgeable",
            "requirements": requirements,
            "contract": "exact normalized/raw message, exact TTY frame, and one consumed direction turn",
        },
        "injury_rng": {
            "status": "unjudgeable",
            "reason": "authoritative_pre_action_rng_snapshot_and_draw_to_branch_chronology_are_not_attached_to_this_transition",
            "missing_source_state": [
                "verified pinned-native ISAAC64 snapshot at this exact pre-action boundary",
                "source mapping from consumed draws to KICK injury branches",
                "dynamic actor scheduling/outcomes during the consumed turn",
            ],
            "diagnostic_note": "The pinned macOS oracle now supports a separate read-only native RNG-state probe; configured get_seeds values alone remain insufficient.",
        },
    }


def direct_wall_message_assertion(case: dict[str, Any]) -> dict[str, Any]:
    """Assert only the exact direct-reset wall contract; fail closed otherwise."""

    eligibility = dict(case.get("eligibility", {})).get("message", {})
    outcome = dict(case.get("outcome", {}))
    turns = list(case.get("turns", []))
    raw = list(outcome.get("message_raw", []))
    expected_raw = list(WALL_KICK_RAW.encode("ascii")) + [0] * max(0, len(raw) - len(WALL_KICK_RAW))
    checks = {
        "eligible": eligibility.get("status") == "eligible",
        "message": outcome.get("message") == WALL_KICK_NORMALIZED,
        "message_raw": raw == expected_raw,
        "turn": len(turns) >= 3 and int(turns[-1]) == int(turns[-2]) + 1,
        "tty_exact_replay": bool(dict(case.get("tty", {})).get("exact_replay")),
    }
    return {
        "status": "pass" if all(checks.values()) else ("unjudgeable" if not checks["eligible"] else "errors_found"),
        "checks": checks,
    }
