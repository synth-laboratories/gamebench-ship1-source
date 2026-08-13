"""Fail-closed contract for source-authoritative dynamic NetHack entities.

NLE 0.9.0's public observations are valuable *presentation* evidence.  They
are not an entity export: a map glyph can identify a monster species, and
``MG_PET`` can identify a currently rendered pet surface, but neither is a
stable monster instance or its complete pre-action state.  This module makes
that boundary executable.

Do not loosen this schema for a seed, coordinate, glyph-continuity, or
post-action observation.  A future authoritative source adapter must emit the
whole record before the input it is intended to justify.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


SCHEMA = "gamebench.nethack.authoritative_entity_scheduler_export.v1"
REQUIRED_ENTITY_FIELDS = frozenset(
    {
        "entity_id",
        "species_id",
        "allegiance",
        "x",
        "y",
        "hp",
        "hp_max",
        "underlay",
        "scheduler",
    }
)
PUBLIC_SCHEDULER_FIELDS = frozenset({"speed", "movement_points", "ai_state", "turn_order"})
NATIVE_SCHEDULER_FIELDS = frozenset({"base_speed", "movement_points", "speed_state", "can_move", "sleeping", "fleeing", "strategy", "special_cooldown", "iteration_order"})
PUBLIC_UNDERLAY_FIELDS = frozenset({"terrain_glyph", "terrain_char", "object_stack_complete"})
NATIVE_UNDERLAY_FIELDS = frozenset({"terrain_type", "object_stack", "object_stack_complete"})
REQUIRED_EXPORT_FIELDS = frozenset({"schema", "source_step", "captured_before_action", "entities", "turn_queue"})

# This is the complete NLE 0.9.0 public observation vocabulary, not merely
# the smaller collection usually recorded in GameBench tapes.  A probe must
# inspect it all before claiming an authority gap.
NLE_090_OBSERVATION_KEYS = frozenset(
    {
        "glyphs",
        "chars",
        "colors",
        "specials",
        "blstats",
        "message",
        "program_state",
        "internal",
        "inv_glyphs",
        "inv_letters",
        "inv_oclasses",
        "inv_strs",
        "screen_descriptions",
        "tty_chars",
        "tty_colors",
        "tty_cursor",
        "misc",
    }
)


def _reason(reasons: list[dict[str, str]], code: str, detail: str) -> None:
    reasons.append({"code": code, "detail": detail})


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def validate_authoritative_entity_export(export: dict[str, Any], *, expected_source_step: int | None = None) -> dict[str, Any]:
    """Validate one pre-action dynamic-source export without inference.

    The acceptance path is deliberately real and narrow, so a future adapter
    can become eligible.  ``entity_id`` is allowed to be an int or a string,
    but it must be unique *within the same pre-action frame*; unique glyphs,
    species IDs, and coordinates do not qualify.  ``turn_queue`` is required
    independently because a per-entity speed snapshot is not a scheduler.
    """

    reasons: list[dict[str, str]] = []
    if not isinstance(export, dict):
        return {
            "schema": SCHEMA,
            "status": "rejected",
            "entities": 0,
            "reasons": [{"code": "malformed_export", "detail": "export must be an object"}],
        }
    missing = sorted(REQUIRED_EXPORT_FIELDS - set(export))
    if missing:
        _reason(reasons, "missing_export_fields", f"missing required fields: {', '.join(missing)}")
    if export.get("schema") != SCHEMA:
        _reason(reasons, "wrong_schema", f"expected {SCHEMA}")
    if export.get("captured_before_action") is not True:
        _reason(reasons, "not_pre_action", "entity state must be captured before the action it judges")
    native_adapter = export.get("source_adapter") == "pinned_native_macho_v1"
    if native_adapter:
        if export.get("gold_scheduler_implementation_eligible") is not False:
            _reason(
                reasons,
                "native_scope_not_explicit",
                "native source evidence must explicitly deny general gold AI/scheduler implementation eligibility",
            )
        scope = export.get("scope")
        if not isinstance(scope, str) or "assert" not in scope.lower() or "ai" not in scope.lower():
            _reason(
                reasons,
                "native_scope_missing",
                "native source evidence must state its assertion-only/no-AI scope",
            )
    source_step = export.get("source_step")
    if not _nonnegative_int(source_step):
        _reason(reasons, "invalid_source_step", "source_step must be a non-negative integer")
    elif expected_source_step is not None and source_step != expected_source_step:
        _reason(reasons, "source_step_mismatch", f"expected pre-action source_step {expected_source_step}, saw {source_step}")

    entities = export.get("entities")
    if not isinstance(entities, list):
        _reason(reasons, "invalid_entities", "entities must be an explicit list (including an empty list)")
        entities = []
    turn_queue = export.get("turn_queue")
    if not isinstance(turn_queue, list):
        _reason(reasons, "invalid_turn_queue", "turn_queue must be an explicit ordered list of entity IDs")
        turn_queue = []

    ids: list[int | str] = []
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            _reason(reasons, "malformed_entity", f"entity {index} is not an object")
            continue
        entity_missing = sorted(REQUIRED_ENTITY_FIELDS - set(entity))
        if entity_missing:
            _reason(reasons, "missing_entity_fields", f"entity {index} lacks: {', '.join(entity_missing)}")
            continue
        entity_id = entity.get("entity_id")
        if not ((type(entity_id) is int and entity_id >= 0) or _nonempty_string(entity_id)):
            _reason(reasons, "invalid_entity_id", f"entity {index} needs a stable source instance ID, not a glyph or coordinate")
        else:
            ids.append(entity_id)
        if not _nonnegative_int(entity.get("species_id")):
            _reason(reasons, "invalid_species_id", f"entity {index} species_id must be a non-negative source species ID")
        if entity.get("allegiance") not in {"hostile", "peaceful", "tame"}:
            _reason(reasons, "invalid_allegiance", f"entity {index} allegiance must be hostile, peaceful, or tame")
        if not (_nonnegative_int(entity.get("x")) and _nonnegative_int(entity.get("y"))):
            _reason(reasons, "invalid_position", f"entity {index} position must be source coordinates")
        if not (_nonnegative_int(entity.get("hp")) and _positive_int(entity.get("hp_max")) and int(entity.get("hp", -1)) <= int(entity.get("hp_max", -1))):
            _reason(reasons, "invalid_hp", f"entity {index} needs complete non-negative HP and positive HP maximum")

        underlay = entity.get("underlay")
        public_underlay = isinstance(underlay, dict) and not (PUBLIC_UNDERLAY_FIELDS - set(underlay))
        native_underlay = isinstance(underlay, dict) and not (NATIVE_UNDERLAY_FIELDS - set(underlay))
        if not isinstance(underlay, dict) or not (public_underlay or native_underlay):
            _reason(reasons, "missing_complete_underlay", f"entity {index} needs terrain and complete object-stack underlay")
        elif public_underlay and not (
                _nonnegative_int(underlay.get("terrain_glyph"))
                and _nonempty_string(underlay.get("terrain_char"))
                and underlay.get("object_stack_complete") is True
        ):
            _reason(reasons, "invalid_underlay", f"entity {index} underlay is not source-complete")
        elif native_underlay and not (
                _nonnegative_int(underlay.get("terrain_type"))
                and isinstance(underlay.get("object_stack"), list)
                and underlay.get("object_stack_complete") is True
        ):
            _reason(reasons, "invalid_underlay", f"entity {index} native terrain/object-stack underlay is not source-complete")

        scheduler = entity.get("scheduler")
        public_scheduler = isinstance(scheduler, dict) and not (PUBLIC_SCHEDULER_FIELDS - set(scheduler))
        native_scheduler = isinstance(scheduler, dict) and not (NATIVE_SCHEDULER_FIELDS - set(scheduler))
        if not isinstance(scheduler, dict) or not (public_scheduler or native_scheduler):
            _reason(reasons, "missing_scheduler_state", f"entity {index} needs source speed, movement points, AI state, and turn order")
        elif public_scheduler and not (
                _positive_int(scheduler.get("speed"))
                and _nonnegative_int(scheduler.get("movement_points"))
                and _nonempty_string(scheduler.get("ai_state"))
                and _nonnegative_int(scheduler.get("turn_order"))
        ):
            _reason(reasons, "invalid_scheduler_state", f"entity {index} scheduler fields are malformed")
        elif native_scheduler and not (
                _nonnegative_int(scheduler.get("base_speed"))
                and type(scheduler.get("movement_points")) is int
                and _nonnegative_int(scheduler.get("speed_state"))
                and all(type(scheduler.get(key)) is bool for key in ("can_move", "sleeping", "fleeing"))
                and _nonnegative_int(scheduler.get("strategy"))
                and _nonnegative_int(scheduler.get("special_cooldown"))
                and _nonnegative_int(scheduler.get("iteration_order"))
        ):
            _reason(reasons, "invalid_scheduler_state", f"entity {index} native scheduler fields are malformed")

    duplicates = sorted(str(entity_id) for entity_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        _reason(reasons, "duplicate_entity_id", f"source frame repeats entity IDs: {', '.join(duplicates)}")
    if len(ids) != len(entities):
        _reason(reasons, "incomplete_entity_identity", "every entity must carry a valid stable source instance ID")
    if len(turn_queue) != len(ids) or set(turn_queue) != set(ids):
        _reason(reasons, "turn_queue_not_complete", "turn_queue must name every source entity exactly once")
    elif len(set(turn_queue)) != len(turn_queue):
        _reason(reasons, "turn_queue_duplicate_entity", "turn_queue repeats an entity ID")

    return {
        "schema": SCHEMA,
        "status": "eligible" if not reasons else "rejected",
        "entities": len(entities),
        "stable_entity_ids": len(ids),
        "gold_scheduler_implementation_eligible": False,
        "reasons": reasons,
        "acceptance": "Eligible means usable for exact source assertions only. It never by itself authorizes gold AI, pathing, collision, combat, or destination implementation.",
    }


def evaluate_nle_090_public_surface(
    *,
    observation_keys: Iterable[str],
    environment_methods: Iterable[str],
    low_level_methods: Iterable[str],
) -> dict[str, Any]:
    """Classify the official NLE 0.9.0 public surface without guessing state.

    The method lists are arguments to keep this logic unit-testable and to
    make the live verifier record exactly what it inspected.  An undocumented
    private extension object is intentionally not accepted as an authority
    path: it is not a pinned public capture contract.
    """

    keys = {str(value) for value in observation_keys}
    env_methods = {str(value) for value in environment_methods}
    raw_methods = {str(value) for value in low_level_methods}
    reasons: list[dict[str, str]] = []
    if keys != NLE_090_OBSERVATION_KEYS:
        _reason(reasons, "unexpected_observation_surface", "NLE 0.9.0 observation vocabulary differs from its pinned contract")
    forbidden_entity_exports = {
        "entities", "entity_state", "monster_state", "monsters", "turn_queue", "scheduler_state", "map_underlay", "rng_state"
    }
    exposed = sorted(forbidden_entity_exports & (env_methods | raw_methods | keys))
    if exposed:
        _reason(reasons, "unexpected_entity_export", f"audit taxonomy must be updated; public surface exposes: {', '.join(exposed)}")
    # We record a reason even when the method inventory itself is stable: the
    # absence is the actual result that prohibits a scheduler implementation.
    _reason(
        reasons,
        "no_authoritative_entity_export",
        "public NLE 0.9.0 exposes rendered/map/player/UI buffers and seed configuration, not stable entity IDs, complete underlays, per-entity HP/allegiance/AI/movement state, turn queue, or evolving RNG state.",
    )
    return {
        "schema": "gamebench.nethack.nle_090_public_entity_capability.v1",
        "status": "rejected",
        "observation_keys": sorted(keys),
        "environment_methods": sorted(env_methods),
        "low_level_methods": sorted(raw_methods),
        "reasons": reasons,
        "acceptance": "Only a separately versioned, public pre-action source entity export can satisfy authoritative_entity_scheduler_export.v1.",
    }
