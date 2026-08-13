"""Portable, reset-only ISAAC64 task contract for pinned NLE 0.9.0.

The contract deliberately serializes the *complete* two-lane ISAAC64 context
at ``env.reset()``.  It is a normal level-dump input, not a receipt and not a
per-action oracle sidecar.  Its algorithm is a literal unsigned-64-bit
translation of the pinned ``src/isaac64.c`` implementation.  It never calls
the native runtime after capture.
"""

from __future__ import annotations

import hashlib
import struct
from copy import deepcopy
from typing import Any

from scripts.oracle_tape import sha256_json
from scripts.nle_rng_state import (
    EXPECTED_CONTEXT_SIZE,
    ISAAC64_SIZE,
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
)


SCHEMA = "gamebench.nethack.authoritative_reset_rng.v1"
RESET_BOUNDARY = {"kind": "reset", "action_step": 0, "before_action_step": 1}
ISAAC64_SOURCE_SHA256 = "191a064fb1ef5301955f292a1d540bb7fc0e00d621b19f706ca9ca6336b366bb"
ISAAC64_HEADER_SHA256 = "9efc8b57f51c0436f5ff330d17936e710a5aad2a790c8cbb3beee25ae965b934"
MASK64 = (1 << 64) - 1
_LANES = ("core", "display")
_EXPECTED_KEYS = {
    "schema", "capture_boundary", "source_commit", "native_binary_sha256",
    "algorithm", "lanes", "projection_sha256",
}
_FORBIDDEN = {
    "native_reset_rng_state", "native_pre_action_evidence", "pre_action_records",
    "future_observation", "future_frames", "hydrated_from_step", "record_sha256",
    "runtime_receipt", "source_state_sha256",
}


def _u64(value: int) -> int:
    return value & MASK64


def _find_forbidden(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        found: list[str] = []
        for key, nested in value.items():
            if key in _FORBIDDEN:
                found.append(f"{path}.{key}")
            found.extend(_find_forbidden(nested, f"{path}.{key}"))
        return found
    if isinstance(value, list):
        return [bad for index, nested in enumerate(value) for bad in _find_forbidden(nested, f"{path}[{index}]")]
    return []


def decode_context(state_hex: str) -> dict[str, Any]:
    """Decode pinned ABI bytes explicitly, never using host struct layout."""

    if not isinstance(state_hex, str):
        raise ValueError("ISAAC64 context must be lowercase/uppercase hex text")
    try:
        raw = bytes.fromhex(state_hex)
    except ValueError as error:
        raise ValueError("ISAAC64 context hex is malformed") from error
    if len(raw) != EXPECTED_CONTEXT_SIZE:
        raise ValueError("ISAAC64 context has wrong exact byte length")
    # ABI: uint32 n; four bytes padding; r[256], m[256], a, b, c, all LE u64.
    n = struct.unpack_from("<I", raw, 0)[0]
    if n > ISAAC64_SIZE or raw[4:8] != b"\0\0\0\0":
        raise ValueError("ISAAC64 context index/padding is not the pinned ABI")
    words = struct.unpack_from("<515Q", raw, 8)
    return {"n": n, "r": list(words[:256]), "m": list(words[256:512]), "a": words[512], "b": words[513], "c": words[514]}


def encode_context(context: dict[str, Any]) -> str:
    try:
        n = context["n"]
        r = context["r"]
        m = context["m"]
        a, b, c = context["a"], context["b"], context["c"]
    except (KeyError, TypeError) as error:
        raise ValueError("ISAAC64 context fields are incomplete") from error
    values = [*r, *m, a, b, c]
    if type(n) is not int or not 0 <= n <= ISAAC64_SIZE or len(r) != 256 or len(m) != 256 or any(type(value) is not int or not 0 <= value <= MASK64 for value in values):
        raise ValueError("ISAAC64 context values are malformed")
    return (struct.pack("<I", n) + b"\0\0\0\0" + struct.pack("<515Q", *values)).hex()


def _update(context: dict[str, Any]) -> None:
    m, r = context["m"], context["r"]
    a = context["a"]
    b = _u64(context["b"] + _u64(context["c"] + 1))
    context["c"] = _u64(context["c"] + 1)
    for offset in (0, 128):
        for i in range(offset, offset + 128, 4):
            x = m[i]; a = _u64(~_u64(a ^ _u64(a << 21)) + m[i + (128 if offset == 0 else -128)]); y = _u64(m[(x & 2040) >> 3] + a + b); m[i] = y; b = _u64(m[(y >> 11) & 255] + x); r[i] = b
            i += 1; x = m[i]; a = _u64(_u64(a ^ (a >> 5)) + m[i + (128 if offset == 0 else -128)]); y = _u64(m[(x & 2040) >> 3] + a + b); m[i] = y; b = _u64(m[(y >> 11) & 255] + x); r[i] = b
            i += 1; x = m[i]; a = _u64(_u64(a ^ _u64(a << 12)) + m[i + (128 if offset == 0 else -128)]); y = _u64(m[(x & 2040) >> 3] + a + b); m[i] = y; b = _u64(m[(y >> 11) & 255] + x); r[i] = b
            i += 1; x = m[i]; a = _u64(_u64(a ^ (a >> 33)) + m[i + (128 if offset == 0 else -128)]); y = _u64(m[(x & 2040) >> 3] + a + b); m[i] = y; b = _u64(m[(y >> 11) & 255] + x); r[i] = b
    context["a"], context["b"], context["n"] = a, b, 256


def next_uint64(context: dict[str, Any]) -> int:
    """Advance one portable copy using the pinned C next-value semantics."""

    if context["n"] == 0:
        _update(context)
    context["n"] -= 1
    return int(context["r"][context["n"]])


def replay(state_hex: str, draws: int) -> tuple[list[int], str]:
    if type(draws) is not int or draws < 0:
        raise ValueError("ISAAC64 replay draw count must be non-negative")
    context = decode_context(state_hex)
    values = [next_uint64(context) for _ in range(draws)]
    return values, encode_context(context)


def _lane_record(source_lane: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source_lane, dict):
        raise ValueError("reset RNG source lane is missing")
    state_hex = source_lane.get("state_hex")
    context = decode_context(state_hex)
    raw = bytes.fromhex(state_hex)
    if source_lane.get("byte_length") != EXPECTED_CONTEXT_SIZE or source_lane.get("state_sha256") != hashlib.sha256(raw).hexdigest() or source_lane.get("n") != context["n"]:
        raise ValueError("reset RNG source lane digest/index is invalid")
    return {"state_hex": state_hex, "state_sha256": hashlib.sha256(raw).hexdigest(), "n": context["n"], "byte_length": EXPECTED_CONTEXT_SIZE}


def portable_reset_rng_projection(rng_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a live reset reader record into portable level-dump task data."""

    if not isinstance(rng_snapshot, dict) or rng_snapshot.get("schema") != "gamebench.nethack.authoritative_rng_snapshot.v1":
        raise ValueError("portable reset RNG requires an exact native ISAAC64 snapshot")
    if rng_snapshot.get("binary_sha256") != PINNED_BINARY_SHA256:
        raise ValueError("portable reset RNG requires the pinned native binary")
    lanes = {lane: _lane_record(rng_snapshot.get(lane)) for lane in _LANES}
    projection = {
        "schema": SCHEMA,
        "capture_boundary": deepcopy(RESET_BOUNDARY),
        "source_commit": PINNED_SOURCE_COMMIT,
        "native_binary_sha256": PINNED_BINARY_SHA256,
        "algorithm": {
            "name": "isaac64", "source_file": "src/isaac64.c", "source_sha256": ISAAC64_SOURCE_SHA256,
            "header_file": "include/isaac64.h", "header_sha256": ISAAC64_HEADER_SHA256,
            "word_bits": 64, "byte_order": "little", "context_bytes": EXPECTED_CONTEXT_SIZE,
            "lanes": ["core", "display"], "next_semantics": "if_n_zero_update_then_return_r_predecrement_n",
        },
        "lanes": lanes,
    }
    projection["projection_sha256"] = sha256_json(projection)
    return projection


def validate_portable_reset_rng_projection(projection: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(projection, dict):
        return ["authoritative reset RNG must be an object"]
    forbidden = _find_forbidden(projection)
    if forbidden:
        failures.append("authoritative reset RNG contains prohibited receipt/pre-action/future fields: " + ", ".join(forbidden))
    if set(projection) != _EXPECTED_KEYS or projection.get("schema") != SCHEMA:
        failures.append("authoritative reset RNG schema/field contract mismatch")
    if projection.get("capture_boundary") != RESET_BOUNDARY:
        failures.append("authoritative reset RNG is not reset-bound")
    if projection.get("source_commit") != PINNED_SOURCE_COMMIT or projection.get("native_binary_sha256") != PINNED_BINARY_SHA256:
        failures.append("authoritative reset RNG source/binary identity mismatch")
    expected_algorithm = portable_reset_rng_projection({"schema": "gamebench.nethack.authoritative_rng_snapshot.v1", "binary_sha256": PINNED_BINARY_SHA256, "core": {"state_hex": encode_context({"n": 0, "r": [0]*256, "m": [0]*256, "a": 0, "b": 0, "c": 0}), "state_sha256": hashlib.sha256(bytes(EXPECTED_CONTEXT_SIZE)).hexdigest(), "n": 0, "byte_length": EXPECTED_CONTEXT_SIZE}, "display": {"state_hex": encode_context({"n": 0, "r": [0]*256, "m": [0]*256, "a": 0, "b": 0, "c": 0}), "state_sha256": hashlib.sha256(bytes(EXPECTED_CONTEXT_SIZE)).hexdigest(), "n": 0, "byte_length": EXPECTED_CONTEXT_SIZE}})["algorithm"]
    if projection.get("algorithm") != expected_algorithm:
        failures.append("authoritative reset RNG algorithm pin mismatch")
    lanes = projection.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != set(_LANES):
        failures.append("authoritative reset RNG requires exactly core/display lanes")
    else:
        for lane in _LANES:
            try:
                normalized = _lane_record(lanes[lane])
                if lanes[lane] != normalized:
                    failures.append(f"authoritative reset RNG {lane} lane shape mismatch")
            except ValueError as error:
                failures.append(f"authoritative reset RNG {lane}: {error}")
    claimed = projection.get("projection_sha256")
    payload = {key: value for key, value in projection.items() if key != "projection_sha256"}
    if not isinstance(claimed, str) or claimed != sha256_json(payload):
        failures.append("authoritative reset RNG projection digest mismatch")
    return failures


def replay_projection(projection: dict[str, Any], lane: str, draws: int) -> tuple[list[int], str]:
    failures = validate_portable_reset_rng_projection(projection)
    if failures:
        raise ValueError("invalid authoritative reset RNG: " + "; ".join(failures))
    if lane not in _LANES:
        raise ValueError("portable reset RNG lane must be core or display")
    return replay(str(projection["lanes"][lane]["state_hex"]), draws)
