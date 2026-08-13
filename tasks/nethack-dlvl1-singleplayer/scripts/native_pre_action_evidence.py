"""Fail-closed native source evidence sidecars for NLE oracle tapes.

These records are captured before the action they name.  They are source
evidence only: neither level-dump construction nor conformance scoring may
read them.  Keeping the data beside, rather than inside, snapshots prevents a
later native frame from being mistaken for reset state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.oracle_tape import oracle_identity, sha256_json


SIDECAR_FILE = "native_pre_action_evidence.jsonl"
SIDECAR_SCHEMA = "gamebench.nethack.native_pre_action_evidence.v1"
RECORD_SCHEMA = "gamebench.nethack.native_pre_action_evidence_record.v1"
USAGE_POLICY = {
    "classification": "read_only_authoritative_source_evidence",
    "captured_before_action_only": True,
    "forbidden_uses": [
        "future_observation_hydration",
        "reset_level_dump_hydration",
        "gold_runtime_input",
        "conformance_denominator",
    ],
}


def _without_digest(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "record_sha256"}


def _assert_nonempty(value: Any, label: str) -> None:
    if value in (None, "", [], {}):
        raise ValueError(f"native pre-action evidence lacks {label}")


def _identity(runtime: dict[str, Any], binary_sha256: str) -> dict[str, Any]:
    _assert_nonempty(binary_sha256, "pinned native binary SHA-256")
    return {
        "oracle_identity_sha256": sha256_json(oracle_identity()),
        "capture_runtime_sha256": sha256_json(runtime),
        "binary_sha256": binary_sha256,
        "export_schemas": {
            "map_fov": "gamebench.nethack.native_map_fov_snapshot.v1",
            "entities": "gamebench.nethack.native_entity_snapshot.v1",
            "player": "gamebench.nethack.native_player_combat_snapshot.v1",
            "rng": "gamebench.nethack.authoritative_rng_snapshot.v1",
        },
    }


@dataclass
class NativePreActionExporters:
    """Pinned, read-only native readers bound to one live NLE process."""

    map_fov: Any
    entities: Any
    player: Any
    rng: Any
    nethack: Any

    @classmethod
    def from_env(cls, env: Any) -> "NativePreActionExporters":
        # Keep imports here: replay/judging historical tapes must not require
        # the macOS NLE oracle runtime or ctypes ABI support.
        from scripts.nle_native_entities import PinnedNleEntityReader
        from scripts.nle_native_map_fov import PinnedNleMapFovReader
        from scripts.nle_native_player import PinnedNlePlayerReader
        from scripts.nle_rng_state import PinnedNleRngReader

        nethack = getattr(env, "nethack", None)
        if nethack is None:
            raise RuntimeError("live NLE environment exposes no native nethack instance")
        return cls(
            map_fov=PinnedNleMapFovReader(nethack),
            entities=PinnedNleEntityReader(nethack),
            player=PinnedNlePlayerReader(nethack),
            rng=PinnedNleRngReader(nethack),
            nethack=nethack,
        )

    def export(self, observation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        # Readers are bound to the live ``Nethack`` wrapper, while the
        # presentation validators require the public glyph-classifier module.
        # Do not confuse the two: the wrapper has no glyph_is_* predicates.
        from nle import nethack as nle_nethack
        from scripts.nle_native_entities import validate_native_presentation

        map_snapshot = self.map_fov.snapshot()
        map_controls = self.map_fov.validate_against_public_pre_action(map_snapshot, observation, nle_nethack)
        entity_snapshot = self.entities.snapshot()
        entity_controls = validate_native_presentation(entity_snapshot, observation, nle_nethack)
        player_snapshot = self.player.snapshot()
        player_controls = self.player.validate_against_public_pre_action(player_snapshot, observation)
        rng_snapshot = self.rng.snapshot()
        map_record = map_snapshot.public_record()
        entity_record = entity_snapshot.public_record()
        player_record = player_snapshot.public_record()
        rng_record = rng_snapshot.public_record()
        hashes = {str(record.get("binary_sha256", "")) for record in (map_record, entity_record, player_record, rng_record)}
        if len(hashes) != 1 or "" in hashes:
            raise RuntimeError("native exporters disagree on their pinned live NLE binary identity")
        return (
            {"map_fov": map_record, "entities": entity_record, "player": player_record, "rng": rng_record},
            {"map_fov": map_controls, "entities": entity_controls, "player": player_controls},
        )


def capture_record(
    exporters: NativePreActionExporters,
    observation: dict[str, Any],
    *,
    fixture_id: str,
    action: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Copy one source boundary before the action is allowed to run."""

    if action.get("nle_stepped") is False and action.get("boundary") != "dlvl1_descend":
        raise ValueError("native source evidence may name only an executable action or dlvl1 boundary")
    step = action.get("step")
    if type(step) is not int or step < 1:
        raise ValueError("native source evidence action step must be positive")
    exports, controls = exporters.export(observation)
    return record_from_exports(
        fixture_id=fixture_id,
        action=action,
        runtime=runtime,
        exports=exports,
        controls=controls,
    )


def record_from_exports(
    *,
    fixture_id: str,
    action: dict[str, Any],
    runtime: dict[str, Any],
    exports: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    """Build a boundary record from already-read native exports.

    Kept separate from :func:`capture_record` so the fail-closed tape contract
    is unit-testable without a live macOS NLE process.  Callers must never use
    this to synthesize evidence; production capture always calls the readers
    immediately before this construction.
    """

    step = action.get("step")
    if action.get("nle_stepped") is False and action.get("boundary") != "dlvl1_descend":
        raise ValueError("native source evidence may name only an executable action or dlvl1 boundary")
    if type(step) is not int or step < 1:
        raise ValueError("native source evidence action step must be positive")
    binary_sha256 = str(exports["map_fov"].get("binary_sha256", ""))
    record = {
        "schema": RECORD_SCHEMA,
        "fixture_id": fixture_id,
        "step": step,
        "captured_before_action": True,
        "action": action,
        "action_sha256": sha256_json(action),
        "native_identity": _identity(runtime, binary_sha256),
        "exports": exports,
        "controls": controls,
        "usage_policy": USAGE_POLICY,
    }
    record["source_state_sha256"] = sha256_json({"native_identity": record["native_identity"], "exports": exports})
    record["record_sha256"] = sha256_json(_without_digest(record))
    return record


def validate_records(
    records: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    fixture_id: str,
    runtime: dict[str, Any] | None,
    require_native: bool,
) -> list[str]:
    """Validate alignment, pinning and anti-hydration policy without replaying."""

    from scripts.nle_native_entities import validate_native_entity_record
    from scripts.nle_native_map_fov import validate_engraving_export, validate_level_flags_export, validate_search_surface_export, validate_semantic_terrain_export, validate_semantic_vision_export
    from scripts.nle_rng_state import validate_rng_record
    from scripts.nle_native_player import validate_player_record

    if not require_native:
        return [] if not records else ["legacy tape unexpectedly carries native evidence"]
    if runtime is None:
        return ["native evidence requires exact capture_runtime provenance"]
    if not actions:
        return ["native evidence requires at least one action"]
    if not records:
        return ["native evidence contains zero pre-action records"]
    if len(records) != len(actions):
        return [f"native evidence has {len(records)} records for {len(actions)} actions"]
    failures: list[str] = []
    runtime_digest = sha256_json(runtime)
    oracle_digest = sha256_json(oracle_identity())
    for index, (record, action) in enumerate(zip(records, actions, strict=True), start=1):
        prefix = f"native evidence step {index}"
        if record.get("schema") != RECORD_SCHEMA or record.get("fixture_id") != fixture_id:
            failures.append(f"{prefix}: invalid schema or fixture identity")
        if record.get("step") != index or record.get("captured_before_action") is not True:
            failures.append(f"{prefix}: record is not aligned to its pre-action boundary")
        if record.get("action") != action or record.get("action_sha256") != sha256_json(action):
            failures.append(f"{prefix}: action binding or action digest mismatch")
        if record.get("usage_policy") != USAGE_POLICY:
            failures.append(f"{prefix}: prohibited hydration/conformance usage policy")
        identity = record.get("native_identity")
        exports = record.get("exports")
        controls = record.get("controls")
        if not isinstance(identity, dict) or not isinstance(exports, dict) or not isinstance(controls, dict):
            failures.append(f"{prefix}: missing identity, exports, or controls")
            continue
        if identity.get("capture_runtime_sha256") != runtime_digest or identity.get("oracle_identity_sha256") != oracle_digest:
            failures.append(f"{prefix}: runtime or oracle identity is not pinned")
        binary_sha256 = identity.get("binary_sha256")
        if not isinstance(binary_sha256, str) or not binary_sha256:
            failures.append(f"{prefix}: missing native binary identity")
        expected_schemas = _identity(runtime, str(binary_sha256)).get("export_schemas")
        if identity.get("export_schemas") != expected_schemas:
            failures.append(f"{prefix}: native export schema pin mismatch")
        for name, schema in expected_schemas.items():
            if name not in exports or not isinstance(exports[name], dict) or exports[name].get("schema") != schema:
                failures.append(f"{prefix}: {name} export schema mismatch")
        for name in ("map_fov", "entities", "player", "rng"):
            exported = exports.get(name)
            if not isinstance(exported, dict) or not exported:
                failures.append(f"{prefix}: missing or zero {name} export")
            elif exported.get("binary_sha256") != binary_sha256:
                failures.append(f"{prefix}: {name} binary identity mismatch")
        map_fov_export = exports.get("map_fov")
        if isinstance(map_fov_export, dict):
            # Fields are optional for historical v1 sidecars.  New records
            # carrying the semantic terrain extension must be complete and
            # shaped correctly; their digest is already bound below.
            failures.extend(f"{prefix}: {failure}" for failure in validate_semantic_terrain_export(map_fov_export))
            failures.extend(f"{prefix}: {failure}" for failure in validate_level_flags_export(map_fov_export))
            failures.extend(f"{prefix}: {failure}" for failure in validate_engraving_export(map_fov_export))
            failures.extend(f"{prefix}: {failure}" for failure in validate_search_surface_export(map_fov_export))
            failures.extend(f"{prefix}: {failure}" for failure in validate_semantic_vision_export(map_fov_export))
        entity_export = exports.get("entities")
        if isinstance(entity_export, dict):
            # Entity records are source-only, but they are part of the
            # action-bound digest.  Check their stable-ID/scheduler/underlay
            # structure before accepting recomputed outer hashes.
            failures.extend(f"{prefix}: {failure}" for failure in validate_native_entity_record(entity_export))
        rng_export = exports.get("rng")
        if isinstance(rng_export, dict):
            failures.extend(f"{prefix}: {failure}" for failure in validate_rng_record(rng_export))
        player_export = exports.get("player")
        if isinstance(player_export, dict):
            failures.extend(f"{prefix}: {failure}" for failure in validate_player_record(player_export))
        if not record.get("source_state_sha256") or record.get("source_state_sha256") != sha256_json({"native_identity": identity, "exports": exports}):
            failures.append(f"{prefix}: source-state digest mismatch")
        if record.get("record_sha256") != sha256_json(_without_digest(record)):
            failures.append(f"{prefix}: boundary record digest mismatch")
    return failures


def manifest_provenance(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Keep historical tapes judgeable while making native absence explicit."""

    if not records:
        return {
            "status": "legacy_no_native_pre_action_evidence",
            "conformance_denominator_included": False,
            "usage_policy": USAGE_POLICY,
            "limitation": "This tape predates pinned native map/FOV/door, entity/path, player, and RNG sidecars.",
        }
    return {
        "status": "present_pre_action_evidence_only",
        "record_count": len(records),
        "records_sha256": sha256_json(records),
        "conformance_denominator_included": False,
        "usage_policy": USAGE_POLICY,
    }
