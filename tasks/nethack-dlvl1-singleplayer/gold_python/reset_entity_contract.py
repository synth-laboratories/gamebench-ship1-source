"""Runtime boundary for portable reset entities versus native receipts.

Only ``level_dump.authoritative_reset_entities`` is task state.  The raw
``native_reset_entity_state.json`` receipt and all per-turn sidecars are
source-audit artifacts and must never enter a rollout or checkpoint.
"""

from __future__ import annotations

from typing import Any


RESET_ENTITY_SIDECAR_FILE = "native_reset_entity_state.json"
RESET_ENTITY_SCHEMA = "gamebench.nethack.native_reset_entity_scheduler_state.v1"
PORTABLE_RESET_ENTITY_SCHEMA = "gamebench.nethack.authoritative_reset_entities.v1"

_FORBIDDEN_RUNTIME_KEYS = frozenset(
    {
        "native_reset_entity_state",
        "authoritative_reset_entity_state",
        "reset_entity_scheduler_state",
        "native_pre_action_evidence",
        "pre_action_records",
        "future_observation",
        "future_frames",
        "hydrated_from_step",
    }
)


def reject_runtime_source_state(value: Any, *, context: str) -> None:
    """Fail closed before any reset sidecar can become runtime state.

    Do not call the source-side validator here: evaluating the contents is
    unnecessary for a forbidden ingestion path and risks making a valid receipt
    look like an accepted gold input.
    """

    if value is not None:
        raise ValueError(
            f"{context} may not ingest {RESET_ENTITY_SIDECAR_FILE}; "
            "reset-only native entity/scheduler evidence is assertion-only"
        )


def reject_forbidden_runtime_fields(container: Any, *, context: str) -> None:
    """Reject explicit sidecar aliases in resolved inputs and checkpoints."""

    if not isinstance(container, dict):
        return
    present = sorted(_FORBIDDEN_RUNTIME_KEYS & set(container))
    if present:
        raise ValueError(f"{context} contains forbidden source-sidecar field(s): {', '.join(present)}")

