"""Checkpoint blob encode/decode."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any


CHECKPOINT_SCHEMA = "gamebench.checkpoint.v1"


@dataclass
class RestoreReport:
    bytes: int
    wall_ms: float
    nev_events_restored: int
    render_cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "bytes": self.bytes,
            "wall_ms": self.wall_ms,
            "nev_events_restored": self.nev_events_restored,
            "render_cache_hit": self.render_cache_hit,
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
        "config_hash": config_hash,
        "sim": sim,
        "nev_events": nev_events,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def decode_checkpoint(blob: bytes) -> dict[str, Any]:
    payload = json.loads(blob.decode())
    if payload.get("schema_version") != CHECKPOINT_SCHEMA:
        raise ValueError(f"unsupported checkpoint schema: {payload.get('schema_version')}")
    return payload


def bench_restore(blob: bytes, restore_fn: Any) -> RestoreReport:
    start = time.perf_counter()
    nev_count = restore_fn(blob)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return RestoreReport(
        bytes=len(blob),
        wall_ms=elapsed_ms,
        nev_events_restored=nev_count,
    )
