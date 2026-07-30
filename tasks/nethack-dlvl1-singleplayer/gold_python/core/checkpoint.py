"""JSON checkpoint helpers shared by the Python gold lane."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


CHECKPOINT_SCHEMA = "gamebench.checkpoint.v1"


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def encode_checkpoint(*, env_family: str, resolved: dict[str, Any], state: dict[str, Any], nev_events: list[dict[str, Any]]) -> bytes:
    payload = {
        "schema_version": CHECKPOINT_SCHEMA,
        "env_family": env_family,
        "episode_id": resolved["episode_id"],
        "step_index": int(state["step_index"]),
        "nev_cursor": len(nev_events),
        "nev_event_digest": "sha256:" + hashlib.sha256(_canonical(nev_events)).hexdigest(),
        "nev_events_external": False,
        "nev_events": deepcopy(nev_events),
        "config_hash": resolved["config_hash"],
        "resolved": deepcopy(resolved),
        "sim": deepcopy(state),
    }
    return _canonical(payload)


def decode_checkpoint(blob: bytes) -> dict[str, Any]:
    payload = json.loads(blob.decode("utf-8"))
    if payload.get("schema_version") != CHECKPOINT_SCHEMA:
        raise ValueError(f"unsupported checkpoint schema: {payload.get('schema_version')}")
    return payload
