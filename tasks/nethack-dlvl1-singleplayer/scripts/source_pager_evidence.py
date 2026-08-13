"""Validate source-backed pager evidence without hydrating the gold runtime.

The pager contract in :mod:`gold_python.source_pager` describes one promoted
terminal boundary.  This module is deliberately judge-side: it joins that
contract to the native pre-action sidecar and checks that the records really
are the pinned fixture/step/action boundaries whose source-state digests the
contract names.  It never supplies a pager message, queue, or digest to gold.

Historical tapes do not contain this optional sidecar.  Their absence is
reported as an explicit non-denominator limitation rather than a conformance
failure.  A present but malformed sidecar fails closed.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from gold_python.source_pager import validate_source_pager_contract


SIDECAR_FILE = "source_pager_evidence.json"
SIDECAR_SCHEMA = "gamebench.nethack.source_pager_evidence.v1"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        errors.append(f"{label} must be a lowercase 64-character SHA-256 digest")


def _action_name(record: dict[str, Any]) -> str | None:
    action = record.get("action")
    if not isinstance(action, dict):
        return None
    value = action.get("action_name")
    return value if isinstance(value, str) else None


def _native_index(native_records: list[dict[str, Any]] | None, errors: list[str]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for number, record in enumerate(native_records or [], start=1):
        if not isinstance(record, dict):
            errors.append(f"native pre-action record {number} is not an object")
            continue
        step = record.get("step")
        if type(step) is not int or step < 1:
            errors.append(f"native pre-action record {number} has an invalid step")
            continue
        if step in indexed:
            errors.append(f"native pre-action evidence has duplicate step {step}")
        indexed[step] = record
    return indexed


def _check_native_binding(
    pager_record: dict[str, Any],
    native: dict[str, Any] | None,
    *,
    fixture_id: str,
    errors: list[str],
) -> None:
    """Cross-check one pager row against the full native evidence record."""

    step = pager_record.get("step")
    prefix = f"pager evidence step {step}"
    if native is None:
        errors.append(f"{prefix}: missing matching native pre-action record")
        return
    if native.get("fixture_id") != fixture_id:
        errors.append(f"{prefix}: native fixture identity mismatch")
    if native.get("step") != step or native.get("captured_before_action") is not True:
        errors.append(f"{prefix}: native record is not the requested pre-action boundary")
    native_action = native.get("action")
    pager_action = pager_record.get("action")
    if not isinstance(native_action, dict) or not isinstance(pager_action, dict):
        errors.append(f"{prefix}: native/pager action binding is missing")
    else:
        if native_action.get("step") != step or pager_action.get("step") != step:
            errors.append(f"{prefix}: nested action step mismatch")
        if native_action.get("action_name") != pager_action.get("action_name"):
            errors.append(f"{prefix}: native/pager action mismatch")
    _digest(pager_record.get("source_state_sha256"), f"{prefix} source_state_sha256", errors)
    if pager_record.get("source_state_sha256") != native.get("source_state_sha256"):
        errors.append(f"{prefix}: source-state digest does not match native evidence")
    native_record_digest = pager_record.get("native_record_sha256")
    _digest(native_record_digest, f"{prefix} native_record_sha256", errors)
    if native_record_digest != native.get("record_sha256"):
        errors.append(f"{prefix}: native record digest binding mismatch")


def validate_source_pager_evidence(
    payload: Any,
    *,
    fixture_id: str,
    native_records: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Return a fail-hard report for an optional pager evidence sidecar.

    ``native_records`` must be the records from the validated
    ``native_pre_action_evidence.jsonl`` sidecar.  The pager sidecar contains
    only role/action/digest bindings and never becomes gold input.
    """

    base = {
        "schema": SIDECAR_SCHEMA,
        "status": "failed",
        "fixture_id": fixture_id,
        "conformance_denominator_included": False,
        "error_count": 0,
        "errors": [],
    }
    if payload is None:
        base.update({
            "status": "not_exercised",
            "limitation": "No source pager evidence sidecar is present.",
        })
        return base
    if not isinstance(payload, dict):
        base["errors"] = ["source pager evidence sidecar must be an object"]
        base["error_count"] = 1
        return base

    errors: list[str] = []
    if set(payload) != {"schema", "fixture_id", "contract", "records"}:
        errors.append("source pager evidence has unsupported or missing fields")
    if payload.get("schema") != SIDECAR_SCHEMA:
        errors.append("source pager evidence schema mismatch")
    if payload.get("fixture_id") != fixture_id:
        errors.append("source pager evidence fixture identity mismatch")
    contract: dict[str, Any] | None = None
    try:
        contract = validate_source_pager_contract(payload.get("contract"))
    except (TypeError, ValueError) as error:
        errors.append(f"source pager contract invalid: {error}")

    records = payload.get("records")
    if not isinstance(records, list) or not records:
        errors.append("source pager evidence records must be a non-empty list")
        records = []
    elif any(not isinstance(record, dict) for record in records):
        errors.append("source pager evidence records must contain only objects")
        records = [record for record in records if isinstance(record, dict)]

    native_index = _native_index(native_records, errors)
    if native_records is None:
        errors.append("source pager evidence requires native pre-action evidence")

    required: dict[int, tuple[str, str | None, str | None]] = {}
    if contract is not None:
        trigger = contract["trigger"]
        start = int(trigger["step"])
        required = {
            start: ("trigger", str(trigger["action"]), None),
            start + 1: ("page", "MiscAction.MORE", contract["page"]["source_state_sha256"]),
            start + 2: ("continuation", None, contract["continuation"]["source_state_sha256"]),
        }

    by_step: dict[int, dict[str, Any]] = {}
    for number, record in enumerate(records, start=1):
        step = record.get("step")
        if type(step) is not int or step < 1:
            errors.append(f"pager evidence record {number} has an invalid step")
            continue
        if step in by_step:
            errors.append(f"pager evidence has duplicate step {step}")
        by_step[step] = record
        if record.get("fixture_id") != fixture_id:
            errors.append(f"pager evidence step {step}: fixture identity mismatch")
        action = record.get("action")
        if not isinstance(action, dict) or type(action.get("step")) is not int:
            errors.append(f"pager evidence step {step}: action step is missing")
        elif action["step"] != step:
            errors.append(f"pager evidence step {step}: nested action step mismatch")

    for step, (role, expected_action, expected_digest) in required.items():
        record = by_step.get(step)
        if record is None:
            errors.append(f"pager evidence missing required {role} record at step {step}")
            continue
        action_name = _action_name(record)
        if expected_action is not None and action_name != expected_action:
            errors.append(f"pager evidence step {step}: expected action {expected_action}, got {action_name}")
        if expected_digest is not None and record.get("source_state_sha256") != expected_digest:
            errors.append(f"pager evidence {role} digest mismatch at step {step}")
        _check_native_binding(record, native_index.get(step), fixture_id=fixture_id, errors=errors)

    # The contract is the sole source of pinned values; a sidecar may not
    # quietly add a fourth pager boundary that the judge never checks.
    if required and set(by_step) != set(required):
        extras = sorted(set(by_step) - set(required))
        if extras:
            errors.append(f"pager evidence contains unsupported steps: {extras}")

    base.update({
        "status": "pass" if not errors else "failed",
        "error_count": len(errors),
        "errors": errors,
        "conformance_denominator_included": not errors,
        "required_steps": sorted(required),
    })
    if contract is not None:
        base["contract"] = deepcopy(contract)
    return base


def manifest_provenance(payload: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Return stable manifest metadata without copying native source data."""

    from scripts.oracle_tape import sha256_json

    return {
        "status": report.get("status", "failed"),
        "conformance_denominator_included": bool(report.get("conformance_denominator_included", False)),
        "contract_sha256": sha256_json(payload.get("contract")),
        "records_sha256": sha256_json(payload.get("records", [])),
        "required_steps": report.get("required_steps", []),
        "error_count": int(report.get("error_count", 0)),
    }


__all__ = [
    "SIDECAR_FILE",
    "SIDECAR_SCHEMA",
    "manifest_provenance",
    "validate_source_pager_evidence",
]
