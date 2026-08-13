#!/usr/bin/env python3
"""Validated registry for authenticated Pokémon Emerald mGBA checkpoints.

The registry deliberately distinguishes a source split that *should* exist from
an authenticated checkpoint that can be used for differential testing.  A
missing local split is useful coverage planning information, but must never be
silently promoted into an oracle identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = TASK_ROOT / "fixtures" / "gold" / "oracle_registry.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
AUTHENTICATED = "authenticated"
CAPTURE_REQUIRED = "capture_required"
QUARANTINED_MISLABELED = "quarantined_mislabeled"
# These rows retain source hashes and capture metadata for audit/re-capture, but
# must never be selected as differential-test oracle boundaries.  In contrast
# to capture_required, their source identity is deliberately preserved so the
# exact provenance failure remains reviewable.
QUARANTINED_PROVENANCE = "quarantined_provenance"
# Every artifact produced before the final v6 release/reset validation is
# evidence of an adapter defect, not of Pokémon Emerald. Keep these identities
# explicit so an old trace cannot regain validity merely because its hashes
# still parse.
QUARANTINED_ADAPTER_SOURCE_SHA256 = {
    "7a99bffead91e44c6aa8a25b8ca6cb5915a22687470a455160f22aa39100eba5",  # v4
    "11745f89ccdc5d58cc6cb08411b84602ed78d5d94e71098d3aa689b8d5f24868",  # v5 pre-pin
    "8644c09a3e3e479521de51133912e96e417c523e221512cd334f8694922227bb",  # v5 pinned
    "0e0efc74e92a16e818aae78a48902e51be6e0c35013b581a0bba6afdd69a31aa",  # v6 set_keys(0) probe
}
# v7 corrected controller transport and its raw snapshots remain useful, but
# v8 changes the per-VBlank evidence schema by adding source observability.
# Therefore v7 receipts/traces are integrity-auditable, not current behavioral
# evidence.
SUPERSEDED_ADAPTER_SOURCE_SHA256 = {
    "f7102b2fbf66f8e96f26dd77f2054b9bfd20fdc60e7a8886c74a2408afd815cf",
}


class RegistryError(RuntimeError):
    """Registry data is malformed or cannot be used as a source oracle."""


@dataclass(frozen=True)
class OracleCheckpoint:
    """One named differential-test source boundary."""

    checkpoint_id: str
    status: str
    rust_checkpoint: str
    source_split: str
    source: dict[str, Any] | None
    normalization: dict[str, Any]
    capture: dict[str, Any]

    @property
    def authenticated(self) -> bool:
        return self.status == AUTHENTICATED


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"{label} must be an object")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{label} must be a non-empty string")
    return value


def _require_sha256(value: Any, label: str) -> str:
    value = _require_text(value, label)
    if not SHA256_RE.fullmatch(value):
        raise RegistryError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _validate_identity(identity: dict[str, Any]) -> None:
    emulator = _require_mapping(identity.get("emulator"), "oracle.emulator")
    for field in ("core", "version", "config_sha256"):
        _require_text(emulator.get(field), f"oracle.emulator.{field}")
    _require_sha256(emulator["config_sha256"], "oracle.emulator.config_sha256")
    _require_mapping(identity.get("config"), "oracle.config")


def oracle_quarantine_reason(registry: dict[str, Any]) -> str | None:
    """Return an explicit reason when the pinned adapter cannot be evidence."""
    identity = registry.get("oracle")
    if not isinstance(identity, dict):
        return "oracle identity is malformed"
    if identity.get("trust_status") != "trusted":
        return str(identity.get("quarantine_reason", "oracle is not marked trusted"))
    config = identity.get("config")
    if not isinstance(config, dict):
        return "oracle config is malformed"
    source = config.get("adapter_source_sha256")
    if source in QUARANTINED_ADAPTER_SOURCE_SHA256:
        return f"adapter source {source} is quarantined"
    return None


def require_trusted_oracle(registry: dict[str, Any]) -> None:
    reason = oracle_quarantine_reason(registry)
    if reason is not None:
        raise RegistryError(f"source oracle is quarantined: {reason}")


def _validate_checkpoint(raw: Any, seen_ids: set[str]) -> OracleCheckpoint:
    value = _require_mapping(raw, "checkpoint")
    checkpoint_id = _require_text(value.get("id"), "checkpoint.id")
    if checkpoint_id in seen_ids:
        raise RegistryError(f"duplicate checkpoint id: {checkpoint_id}")
    seen_ids.add(checkpoint_id)
    status = _require_text(value.get("status"), f"checkpoint {checkpoint_id}.status")
    if status not in (
        AUTHENTICATED,
        CAPTURE_REQUIRED,
        QUARANTINED_MISLABELED,
        QUARANTINED_PROVENANCE,
    ):
        raise RegistryError(f"checkpoint {checkpoint_id} has unsupported status {status!r}")
    rust_checkpoint = _require_text(
        value.get("rust_checkpoint"), f"checkpoint {checkpoint_id}.rust_checkpoint"
    )
    source_split = _require_text(
        value.get("source_split"), f"checkpoint {checkpoint_id}.source_split"
    )
    normalization = _require_mapping(
        value.get("normalization"), f"checkpoint {checkpoint_id}.normalization"
    )
    capture = _require_mapping(value.get("capture"), f"checkpoint {checkpoint_id}.capture")
    source_raw = value.get("source")
    if status in (AUTHENTICATED, QUARANTINED_MISLABELED, QUARANTINED_PROVENANCE):
        source = _require_mapping(source_raw, f"checkpoint {checkpoint_id}.source")
        _require_sha256(source.get("state_sha256"), f"checkpoint {checkpoint_id}.source.state_sha256")
        _require_sha256(source.get("initial_rgb_sha256"), f"checkpoint {checkpoint_id}.source.initial_rgb_sha256")
        initial_state = _require_mapping(
            source.get("initial_state"), f"checkpoint {checkpoint_id}.source.initial_state"
        )
        if not initial_state:
            raise RegistryError(f"checkpoint {checkpoint_id}.source.initial_state cannot be empty")
        battle_assertion = capture.get("battle_memory_assertion")
        if battle_assertion is not None:
            battle_assertion = _require_mapping(
                battle_assertion,
                f"checkpoint {checkpoint_id}.capture.battle_memory_assertion",
            )
            if battle_assertion.get("status") != "verified_external_sidecar":
                raise RegistryError(
                    f"checkpoint {checkpoint_id} battle memory assertion is not verified"
                )
            _require_sha256(
                battle_assertion.get("receipt_sha256"),
                f"checkpoint {checkpoint_id}.capture.battle_memory_assertion.receipt_sha256",
            )
            assertion_state = _require_sha256(
                battle_assertion.get("state_sha256"),
                f"checkpoint {checkpoint_id}.capture.battle_memory_assertion.state_sha256",
            )
            if assertion_state != source["state_sha256"]:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} battle memory assertion state differs from source"
                )
            _require_sha256(
                battle_assertion.get("script_sha256"),
                f"checkpoint {checkpoint_id}.capture.battle_memory_assertion.script_sha256",
            )
            _require_sha256(
                battle_assertion.get("symbol_manifest_sha256"),
                f"checkpoint {checkpoint_id}.capture.battle_memory_assertion.symbol_manifest_sha256",
            )
            _require_text(
                battle_assertion.get("receipt_path"),
                f"checkpoint {checkpoint_id}.capture.battle_memory_assertion.receipt_path",
            )
        field_assertion = capture.get("field_state_assertion")
        if field_assertion is not None:
            field_assertion = _require_mapping(
                field_assertion,
                f"checkpoint {checkpoint_id}.capture.field_state_assertion",
            )
            if field_assertion.get("status") != "verified_external_sidecar":
                raise RegistryError(
                    f"checkpoint {checkpoint_id} field state assertion is not verified"
                )
            for field in (
                "receipt_sha256",
                "state_sha256",
                "script_sha256",
                "symbol_manifest_sha256",
            ):
                _require_sha256(
                    field_assertion.get(field),
                    f"checkpoint {checkpoint_id}.capture.field_state_assertion.{field}",
                )
            if field_assertion["state_sha256"] != source["state_sha256"]:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} field state assertion state differs from source"
                )
            expected_flags = _require_mapping(
                field_assertion.get("expected_flags"),
                f"checkpoint {checkpoint_id}.capture.field_state_assertion.expected_flags",
            )
            if expected_flags != {
                "FLAG_RECEIVED_RUNNING_SHOES": True,
                "FLAG_SYS_B_DASH": True,
            }:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} field state assertion flags are invalid"
                )
            _require_text(
                field_assertion.get("receipt_path"),
                f"checkpoint {checkpoint_id}.capture.field_state_assertion.receipt_path",
            )
        continuous_trace = capture.get("continuous_battle_trace_smoke")
        if continuous_trace is not None:
            continuous_trace = _require_mapping(
                continuous_trace,
                f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_smoke",
            )
            if continuous_trace.get("status") != "validated_continuous":
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous battle trace is not validated"
                )
            for field in (
                "receipt_sha256", "input_state_sha256",
                "terminal_state_sha256", "tape_sha256",
            ):
                _require_sha256(
                    continuous_trace.get(field),
                    f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_smoke.{field}",
                )
            if continuous_trace["input_state_sha256"] != source["state_sha256"]:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous trace input differs from source"
                )
            if continuous_trace.get("intermediate_reload_count") != 0:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous trace contains a reload"
                )
            vblanks = continuous_trace.get("vblank_count")
            samples = continuous_trace.get("sample_count")
            if (
                not isinstance(vblanks, int)
                or vblanks < 0
                or samples != vblanks + 1
            ):
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous trace sample count is invalid"
                )
            _require_text(
                continuous_trace.get("receipt_path"),
                f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_smoke.receipt_path",
            )
        # A trace attached to an outcome boundary starts from a *different*,
        # already authenticated checkpoint. Its terminal snapshot is this
        # row's source identity, so it cannot use the input-trace contract.
        output_trace = capture.get("continuous_battle_trace_output")
        if output_trace is not None:
            output_trace = _require_mapping(
                output_trace,
                f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_output",
            )
            if output_trace.get("status") != "validated_continuous":
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous output trace is not validated"
                )
            _require_text(
                output_trace.get("source_checkpoint"),
                f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_output.source_checkpoint",
            )
            for field in (
                "receipt_sha256", "input_state_sha256",
                "terminal_state_sha256", "tape_sha256",
            ):
                _require_sha256(
                    output_trace.get(field),
                    f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_output.{field}",
                )
            if output_trace["terminal_state_sha256"] != source["state_sha256"]:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous output terminal differs from source"
                )
            if output_trace.get("intermediate_reload_count") != 0:
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous output trace contains a reload"
                )
            vblanks = output_trace.get("vblank_count")
            samples = output_trace.get("sample_count")
            if (
                not isinstance(vblanks, int)
                or vblanks < 0
                or samples != vblanks + 1
            ):
                raise RegistryError(
                    f"checkpoint {checkpoint_id} continuous output trace sample count is invalid"
                )
            _require_text(
                output_trace.get("receipt_path"),
                f"checkpoint {checkpoint_id}.capture.continuous_battle_trace_output.receipt_path",
            )
        provenance = capture.get("provenance")
        if status == AUTHENTICATED and isinstance(provenance, dict):
            evidence_status = provenance.get("evidence_status")
            if evidence_status == "audit_only_superseded_adapter_identity":
                raise RegistryError(
                    f"checkpoint {checkpoint_id} is authenticated with superseded adapter evidence"
                )
            if (
                "receipt_sha256" not in provenance
                and "continuous_chain_receipt_sha256" not in provenance
            ):
                raise RegistryError(
                    f"checkpoint {checkpoint_id} is authenticated without a receipt identity"
                )
            for receipt_key in ("receipt_sha256", "continuous_chain_receipt_sha256"):
                if receipt_key in provenance:
                    _require_sha256(
                        provenance[receipt_key],
                        f"checkpoint {checkpoint_id}.capture.provenance.{receipt_key}",
                    )
        if status == AUTHENTICATED and source_split.upper().startswith("QUARANTINED"):
            raise RegistryError(
                f"checkpoint {checkpoint_id} is authenticated despite its quarantined source split"
            )
    else:
        # Pending rows document the expected capture; hashes or coordinates in
        # them would look authoritative despite having no source artifact.
        if source_raw is not None:
            raise RegistryError(
                f"checkpoint {checkpoint_id} is capture_required and must not contain source identity"
            )
        source = None
    return OracleCheckpoint(
        checkpoint_id=checkpoint_id,
        status=status,
        rust_checkpoint=rust_checkpoint,
        source_split=source_split,
        source=source,
        normalization=normalization,
        capture=capture,
    )


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> tuple[dict[str, Any], dict[str, OracleCheckpoint]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load oracle registry {path}: {exc}") from exc
    root = _require_mapping(raw, "oracle registry")
    if root.get("schema") != "gamebench.pokemon_emerald.mgba_oracle_registry.v1":
        raise RegistryError("oracle registry has an unsupported schema")
    _require_sha256(root.get("rom_sha256"), "rom_sha256")
    identity = _require_mapping(root.get("oracle"), "oracle")
    _validate_identity(identity)
    checkpoint_values = root.get("checkpoints")
    if not isinstance(checkpoint_values, list) or not checkpoint_values:
        raise RegistryError("oracle registry must contain a non-empty checkpoints list")
    seen_ids: set[str] = set()
    checkpoints = {
        checkpoint.checkpoint_id: checkpoint
        for checkpoint in (_validate_checkpoint(value, seen_ids) for value in checkpoint_values)
    }
    for checkpoint in checkpoints.values():
        output_trace = checkpoint.capture.get("continuous_battle_trace_output")
        if output_trace is None:
            continue
        upstream_id = output_trace["source_checkpoint"]
        upstream = checkpoints.get(upstream_id)
        if upstream is None or not upstream.authenticated or upstream.source is None:
            raise RegistryError(
                f"checkpoint {checkpoint.checkpoint_id} continuous output trace "
                f"does not start from an authenticated checkpoint"
            )
        if upstream.source["state_sha256"] != output_trace["input_state_sha256"]:
            raise RegistryError(
                f"checkpoint {checkpoint.checkpoint_id} continuous output trace "
                f"input differs from {upstream_id}"
            )
    default_id = _require_text(root.get("default_checkpoint"), "default_checkpoint")
    if default_id not in checkpoints:
        raise RegistryError("default_checkpoint is not present in checkpoints")
    if not checkpoints[default_id].authenticated:
        raise RegistryError("default_checkpoint must be authenticated")
    return root, checkpoints


def resolve_checkpoint(
    checkpoint_id: str | None, path: Path = DEFAULT_REGISTRY_PATH
) -> tuple[dict[str, Any], OracleCheckpoint]:
    registry, checkpoints = load_registry(path)
    selected_id = checkpoint_id or registry["default_checkpoint"]
    try:
        return registry, checkpoints[selected_id]
    except KeyError as exc:
        available = ", ".join(sorted(checkpoints))
        raise RegistryError(
            f"unknown oracle checkpoint {selected_id!r}; available: {available}"
        ) from exc


def require_authenticated(checkpoint: OracleCheckpoint) -> OracleCheckpoint:
    if checkpoint.authenticated:
        return checkpoint
    procedure = checkpoint.capture.get("procedure", "capture a source state and register it")
    raise RegistryError(
        f"oracle checkpoint {checkpoint.checkpoint_id!r} is {checkpoint.status}; {procedure}"
    )


def initial_state_matches(checkpoint: OracleCheckpoint, source_state: dict[str, Any]) -> bool:
    """Compare only the explicitly captured fields for this checkpoint."""
    source = require_authenticated(checkpoint).source
    assert source is not None
    expected = source["initial_state"]
    return all(source_state.get(field) == value for field, value in expected.items())


def normalize_source_semantics(
    checkpoint: OracleCheckpoint, source_state: dict[str, Any]
) -> dict[str, Any]:
    """Apply a checkpoint's explicit map and coordinate projection.

    Unknown maps remain source-addressed rather than being guessed as a Rust
    map name.  That preserves useful mismatch evidence for newly captured
    scenes that have not received a projection yet.
    """
    required = ("player_x", "player_y", "map_group", "map_number")
    if not all(isinstance(source_state.get(field), int) for field in required):
        raise RegistryError("oracle source_state is missing Emerald position/map integers")
    normalization = checkpoint.normalization
    map_key = f"{source_state['map_group']}:{source_state['map_number']}"
    map_names = normalization.get("map_names", {})
    map_name = map_names.get(
        map_key, f"emerald_map_{source_state['map_group']}_{source_state['map_number']}"
    )
    # A checkpoint may cross map families with different coordinate
    # projections.  The bedroom source uses the hidden two-row interior
    # border on maps 1:2/1:3, while its house-exit continuation is already in
    # raw Littleroot coordinates (0:9).  Prefer an explicit per-map offset;
    # retain the legacy single offset for checkpoints that never cross maps.
    offsets_by_map = normalization.get("player_offsets", {})
    if offsets_by_map:
        if not isinstance(offsets_by_map, dict):
            raise RegistryError(
                f"checkpoint {checkpoint.checkpoint_id} player_offsets must be an object"
            )
        offset = offsets_by_map.get(map_key, normalization.get("player_offset", {}))
    else:
        offset = normalization.get("player_offset", {})
    if not isinstance(offset, dict):
        raise RegistryError(f"checkpoint {checkpoint.checkpoint_id} player_offset must be an object")
    offset_x = offset.get("x", 0)
    offset_y = offset.get("y", 0)
    if not isinstance(offset_x, int) or not isinstance(offset_y, int):
        raise RegistryError(f"checkpoint {checkpoint.checkpoint_id} player offsets must be integers")
    return {
        "player": {"x": source_state["player_x"] + offset_x, "y": source_state["player_y"] + offset_y},
        "map": map_name,
    }
