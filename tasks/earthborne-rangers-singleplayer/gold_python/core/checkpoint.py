"""Checkpoint blob helpers for synthetic Earthborne Rangers."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


CHECKPOINT_SCHEMA = "gamebench.checkpoint.v1"


@dataclass(frozen=True)
class RestoreReport:
    bytes: int
    wall_ms: float
    nev_events_restored: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bytes": self.bytes,
            "wall_ms": self.wall_ms,
            "nev_events_restored": self.nev_events_restored,
        }


def encode_checkpoint(
    *,
    env_family: str,
    episode_id: str,
    step_index: int,
    nev_cursor: int,
    config_hash: str,
    sim: dict[str, Any],
    nev_events: list[dict[str, Any]],
) -> bytes:
    payload = {
        "schema_version": CHECKPOINT_SCHEMA,
        "env_family": env_family,
        "episode_id": episode_id,
        "step_index": step_index,
        "nev_cursor": nev_cursor,
        "nev_event_digest": digest_json(nev_events),
        "config_hash": config_hash,
        "sim": sim,
        "nev_events": nev_events,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_checkpoint(blob: bytes) -> dict[str, Any]:
    payload = json.loads(blob.decode("utf-8"))
    if payload.get("schema_version") != CHECKPOINT_SCHEMA:
        raise ValueError(f"unsupported checkpoint schema: {payload.get('schema_version')}")
    return payload


def bench_restore(blob: bytes, restore_fn: Any) -> RestoreReport:
    start = time.perf_counter()
    restored = restore_fn(blob)
    return RestoreReport(bytes=len(blob), wall_ms=(time.perf_counter() - start) * 1000, nev_events_restored=restored)


def digest_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
