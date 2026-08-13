"""Pinned source-message pager contract.

This module models only the terminal boundary around a captured native
message.  It deliberately carries no actor, damage, RNG, or map transition;
those fields remain fail-closed until their own source contracts are promoted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SOURCE_PAGER_SCHEMA = "gamebench.nethack.source_pager_contract.v1"
PINNED_SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
PINNED_BINARY_SHA256 = "7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057"


def _require(mapping: dict[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if type(value) is not expected:
        raise ValueError(f"source pager {key} must be {expected.__name__}")
    return value


def _require_int_list(mapping: dict[str, Any], key: str) -> list[int]:
    value = mapping.get(key)
    if type(value) is not list or any(type(item) is not int or item < 0 for item in value):
        raise ValueError(f"source pager {key} must be a list of non-negative integers")
    return list(value)


def validate_source_pager_contract(contract: Any) -> dict[str, Any]:
    """Validate and copy a captured pager receipt.

    The shape is intentionally exact.  A pager receipt is not allowed to
    smuggle a future frame, actor state, or RNG state into the gold runtime.
    """

    if not isinstance(contract, dict):
        raise ValueError("source pager contract must be an object")
    required = {
        "schema", "fixture_id", "source_commit", "binary_sha256", "trigger",
        "before", "page", "continuation",
    }
    if set(contract) != required:
        raise ValueError("source pager contract has unsupported or missing fields")
    if contract.get("schema") != SOURCE_PAGER_SCHEMA:
        raise ValueError("source pager schema mismatch")
    if contract.get("source_commit") != PINNED_SOURCE_COMMIT:
        raise ValueError("source pager source identity mismatch")
    if contract.get("binary_sha256") != PINNED_BINARY_SHA256:
        raise ValueError("source pager binary identity mismatch")
    if not isinstance(contract.get("fixture_id"), str) or not contract["fixture_id"]:
        raise ValueError("source pager fixture_id must be non-empty")

    trigger = contract["trigger"]
    before = contract["before"]
    page = contract["page"]
    continuation = contract["continuation"]
    if not all(isinstance(value, dict) for value in (trigger, before, page, continuation)):
        raise ValueError("source pager trigger/before/page/continuation must be objects")
    if set(trigger) != {"step", "action"} or type(trigger["step"]) is not int or trigger["step"] <= 0 or type(trigger["action"]) is not str or not trigger["action"]:
        raise ValueError("source pager trigger must contain a positive step and action")
    if set(before) != {"source_turn", "nle_time", "message", "queue"}:
        raise ValueError("source pager before has unsupported or missing fields")
    if type(before["source_turn"]) is not int or before["source_turn"] < 0 or type(before["nle_time"]) is not int or before["nle_time"] < 0:
        raise ValueError("source pager before counters must be non-negative integers")
    if type(before["message"]) is not str or not before["message"]:
        raise ValueError("source pager before message must be non-empty")
    _require_int_list(before, "queue")
    if set(page) != {"message", "tty_message", "input_mode", "source_state_sha256"}:
        raise ValueError("source pager page has unsupported or missing fields")
    if type(page["source_state_sha256"]) is not str or len(page["source_state_sha256"]) != 64 or any(character not in "0123456789abcdef" for character in page["source_state_sha256"]):
        raise ValueError("source pager page source-state digest must be lowercase hex")
    if type(page["message"]) is not str or not page["message"] or type(page["tty_message"]) is not str or page["tty_message"] != page["message"] + "--More--" or page["input_mode"] != "more":
        raise ValueError("source pager page message/TTY contract mismatch")
    if set(continuation) != {"action", "source_turn", "nle_time", "message", "queue", "input_mode", "consumes_player_turn", "source_state_sha256"}:
        raise ValueError("source pager continuation has unsupported or missing fields")
    if continuation["action"] != "MiscAction.MORE" or continuation["input_mode"] != "normal" or continuation["consumes_player_turn"] is not False:
        raise ValueError("source pager continuation must be an explicit non-turn MORE")
    if type(continuation["source_turn"]) is not int or continuation["source_turn"] < before["source_turn"] or type(continuation["nle_time"]) is not int or continuation["nle_time"] < before["nle_time"]:
        raise ValueError("source pager continuation counters must be monotonic integers")
    if type(continuation["source_state_sha256"]) is not str or len(continuation["source_state_sha256"]) != 64 or any(character not in "0123456789abcdef" for character in continuation["source_state_sha256"]):
        raise ValueError("source pager continuation source-state digest must be lowercase hex")
    if type(continuation["message"]) is not str or not continuation["message"]:
        raise ValueError("source pager continuation message must be non-empty")
    _require_int_list(continuation, "queue")

    # Keep the contract source-backed and terminal-only. These two receipts
    # are intentionally the only mutable values a MORE continuation may use.
    if continuation["source_turn"] != before["source_turn"] + 1 or continuation["nle_time"] != before["nle_time"] + 1:
        raise ValueError("source pager continuation must close exactly one source turn")
    # This first promotion is deliberately pinned to the observed grid-bug
    # pager. A broader message/queue family needs its own source trace.
    if contract["fixture_id"] != "fuzz-case-0006-seed-20260731" or trigger["step"] != 15 or trigger["action"] != "CompassDirection.SE":
        raise ValueError("source pager promotion is limited to the pinned seed20260731 boundary")
    if before["source_turn"] != 14 or before["nle_time"] != 14 or before["queue"] != [27, 10] or continuation["queue"] != [27]:
        raise ValueError("source pager pinned queue boundary mismatch")
    if page["source_state_sha256"] != "749e8b0a340371d5f423ff1c53a870c6a54ade58a28864e4934a66e49774e470" or continuation["source_state_sha256"] != "e215f11678e326c7995d70bd40f1a5f283e3ef9aaa1dfda9023f4207ecc4dbd8":
        raise ValueError("source pager pinned source-state digest mismatch")
    if before["message"] != "The kitten misses the grid bug." or page["message"] != "The kitten misses the grid bug.  The grid bug bites!  You get zapped!" or continuation["message"] != "The kitten bites the grid bug.  The grid bug is killed!":
        raise ValueError("source pager pinned message boundary mismatch")
    return deepcopy(contract)


def arm_source_pager(contract: Any, *, current_time: int, current_message: str, input_mode: str) -> dict[str, Any]:
    """Check the precondition and return an active pager state."""

    validated = validate_source_pager_contract(contract)
    before = validated["before"]
    if input_mode != "normal":
        raise RuntimeError("source pager requires normal input mode")
    if current_time != before["nle_time"]:
        raise RuntimeError("source pager source-time precondition failed")
    if current_message != before["message"]:
        raise RuntimeError("source pager preceding message precondition failed")
    return {"phase": "active", "contract": validated, "queue": list(before["queue"]), "source_turn": before["source_turn"]}


def consume_source_pager(active: Any, *, action_name: str, action_key: str, current_time: int, current_message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Consume the one captured MORE and return (completed state, receipt)."""

    if not isinstance(active, dict) or active.get("phase") != "active":
        raise RuntimeError("source pager is not active")
    contract = validate_source_pager_contract(active.get("contract"))
    continuation = contract["continuation"]
    if action_name != "MiscAction.MORE" and action_key not in {" ", "\r", "\n"}:
        raise RuntimeError("source pager accepts only explicit MORE continuation")
    before = contract["before"]
    if current_time != before["nle_time"] or current_message != contract["page"]["message"]:
        raise RuntimeError("source pager active-state precondition failed")
    completed = {
        "phase": "complete",
        "contract": contract,
        "queue": list(continuation["queue"]),
        "source_turn": continuation["source_turn"],
    }
    receipt = {
        "message": continuation["message"],
        "message_raw": list(continuation["message"].encode("utf-8")),
        "queue_before": list(active["queue"]),
        "queue_after": list(continuation["queue"]),
        "source_turn_before": before["source_turn"],
        "source_turn_after": continuation["source_turn"],
        "nle_time_before": before["nle_time"],
        "nle_time_after": continuation["nle_time"],
        "consumes_player_turn": False,
    }
    return completed, receipt
