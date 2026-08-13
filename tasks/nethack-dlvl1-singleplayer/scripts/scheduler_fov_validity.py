"""Fail-closed applicability gates for dynamic scheduler and FOV proposals.

These are *design* gates, not an emulator.  NLE 0.9.0 exposes rendered
``glyphs/chars/colors/specials`` planes, but it does not expose a stable
monster/object instance identifier, an entity's hidden stats, its AI state,
or the map square beneath a rendered entity.  Repeating a glyph at another
coordinate is presentation continuity, not an identity proof.

Keep a proposed rule out of a gold lane unless this module returns
``eligible``.  In particular, a fixed core/display seed is reproducibility
evidence; it is not a public entity-state serialization.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


STATIC_TERRAIN_CHARS = frozenset(".#|-+<>_{}~")


def _record(reasons: list[dict[str, str]], code: str, detail: str) -> None:
    reasons.append({"code": code, "detail": detail})


def require_equal_lane_denominators(
    lanes: Iterable[dict[str, Any]],
    contract_key: str,
    *,
    denominator_key: str = "comparisons",
) -> int:
    """Return a contract denominator only when both gold lanes agree.

    Choosing ``max`` when Python and Rust compare different numbers of source
    transitions can make an early-terminated lane disappear from a score.
    That is a malformed differential report, not a favorable denominator.
    The progress renderer can call this before aggregating any assertion lane.
    """

    values: set[int] = set()
    for lane in lanes:
        if not isinstance(lane, dict) or not isinstance(lane.get(contract_key), dict):
            raise ValueError(f"missing {contract_key} lane contract")
        value = lane[contract_key].get(denominator_key)
        if type(value) is not int or value < 0:
            raise ValueError(f"invalid {contract_key}.{denominator_key}")
        values.add(value)
    if len(values) != 1:
        raise ValueError(f"{contract_key}: gold lanes disagree on {denominator_key}: {sorted(values)}")
    if not values:
        raise ValueError(f"no lanes for {contract_key}")
    return values.pop()


def scheduler_applicability(
    evidence: dict[str, Any],
    *,
    min_distinct_source_cases: int = 3,
) -> dict[str, Any]:
    """Decide whether a dynamic-entity scheduler has public source authority.

    ``evidence`` is deliberately small and auditable:

    - ``entity_identity_kind`` must be ``stable_public_entity_id``.  The
      current NLE live artifacts instead supply
      ``presentation_continuity_only`` or
      ``unavailable_from_nle_presentation`` and therefore fail this gate.
    - ``pre_action_state_complete`` asserts that position alone is not being
      substituted for species, tame/peaceful state, HP, AI state, movement
      points, and occupancy.
    - each transition needs an independently replayed source case; one
      deterministic seed is not an identity or a scheduling rule.

    A future capture format may satisfy these requirements with an
    authoritative, pre-action entity annotation.  Public glyph repetition,
    ``glyph_to_mon`` and ``MG_PET`` are explicitly insufficient.
    """

    reasons: list[dict[str, str]] = []
    if int(min_distinct_source_cases) < 1:
        raise ValueError("min_distinct_source_cases must be positive")
    identity_kind = str(evidence.get("entity_identity_kind", ""))
    if identity_kind != "stable_public_entity_id":
        _record(
            reasons,
            "no_stable_public_entity_id",
            "NLE presentation glyphs, glyph_to_mon, MG_PET, and repeated chars do not identify an entity instance.",
        )
    if evidence.get("pre_action_state_complete") is not True:
        _record(
            reasons,
            "hidden_entity_state_missing",
            "A scheduler needs authoritative pre-action allegiance, HP, AI/movement state, and occupancy; pixels do not provide them.",
        )
    if evidence.get("underlay_complete") is not True:
        _record(
            reasons,
            "entity_underlay_missing",
            "A rendered entity does not disclose the terrain/object stack it occupies.",
        )

    transitions = evidence.get("transitions", [])
    if not isinstance(transitions, list) or not transitions:
        _record(reasons, "no_transition_evidence", "At least one source-observed dynamic transition is required.")
        transitions = []
    source_cases: set[str] = set()
    malformed = 0
    unnamed = 0
    unreplayed = 0
    non_authoritative = 0
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            malformed += 1
            continue
        source_case = transition.get("source_case")
        if not isinstance(source_case, str) or not source_case:
            unnamed += 1
        else:
            source_cases.add(source_case)
        if transition.get("replayed_exactly") is not True:
            unreplayed += 1
        if transition.get("pre_action_authoritative") is not True:
            non_authoritative += 1
    if malformed:
        _record(reasons, "malformed_transition", f"{malformed} transition records are not objects")
    if unnamed:
        _record(reasons, "transition_has_no_source_case", f"{unnamed} transitions have no independently named source case")
    if unreplayed:
        _record(reasons, "transition_not_replayed", f"{unreplayed} transitions lack same-input source repeatability evidence")
    if non_authoritative:
        _record(reasons, "transition_not_pre_action_authoritative", f"{non_authoritative} transitions depend on post-action or inferred state")
    if len(source_cases) < min_distinct_source_cases:
        _record(
            reasons,
            "insufficient_distinct_source_cases",
            f"need {min_distinct_source_cases} independently named source cases; observed {len(source_cases)}",
        )
    return {
        "schema": "gamebench.nethack.scheduler_applicability.v1",
        "status": "eligible" if not reasons else "rejected",
        "distinct_source_cases": len(source_cases),
        "min_distinct_source_cases": min_distinct_source_cases,
        "reasons": reasons,
        "acceptance": "Only an authoritative pre-action entity contract with stable instance identity may enable a scheduler.",
    }


def fov_underlay_applicability(
    proposal: dict[str, Any],
    *,
    min_distinct_source_cases: int = 3,
) -> dict[str, Any]:
    """Gate an underlay cache or FOV rule against future-observation leakage.

    A cache may preserve a directly observed static cell.  It may not create a
    terrain value for an unseen/hero/entity-covered square, even if a later
    frame eventually shows that square.  A general FOV rule also needs exact
    positive *and* negative held-out observations; matching only revealed
    floor cells rewards overly permissive visibility.
    """

    if int(min_distinct_source_cases) < 1:
        raise ValueError("min_distinct_source_cases must be positive")
    reasons: list[dict[str, str]] = []
    kind = str(proposal.get("kind", ""))
    if kind not in {"known_static_cache", "fov_visibility_rule"}:
        _record(reasons, "unsupported_rule_kind", "kind must be known_static_cache or fov_visibility_rule")
    cells = proposal.get("cells", [])
    if not isinstance(cells, list) or not cells:
        _record(reasons, "no_cells", "a proposed rule needs explicit coordinate-level source inputs")
        cells = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            _record(reasons, "malformed_cell", f"cell {index} is not an object")
            continue
        required = ("x", "y", "char", "glyph", "color", "observed_at_step", "applied_before_step", "provenance")
        if any(key not in cell for key in required):
            _record(reasons, "incomplete_cell_evidence", f"cell {index} lacks exact pre-action coordinate/value/provenance")
            continue
        if cell.get("provenance") != "direct_static_public_plane":
            _record(reasons, "nonstatic_or_inferred_cell", f"cell {index} is not a directly observed static source cell")
        if not isinstance(cell.get("char"), str) or cell["char"] not in STATIC_TERRAIN_CHARS:
            _record(reasons, "nonstatic_cell_character", f"cell {index} does not provide static terrain")
        if not all(type(cell.get(key)) is int for key in ("x", "y", "glyph", "color", "observed_at_step", "applied_before_step")):
            _record(reasons, "noninteger_cell_evidence", f"cell {index} has non-integer coordinate/plane/timeline evidence")
        elif int(cell["observed_at_step"]) >= int(cell["applied_before_step"]):
            _record(reasons, "future_observation_leak", f"cell {index} is first observed at/after the action it would justify")
        if cell.get("source_unknown") is True or cell.get("covered_by") in {"hero", "overlay", "unseen"}:
            _record(reasons, "covered_or_unknown_underlay", f"cell {index} is not a public static underlay")

    cases = proposal.get("heldout_source_cases", [])
    if kind == "fov_visibility_rule":
        if not isinstance(cases, list) or len(set(str(case) for case in cases if isinstance(case, str) and case)) < min_distinct_source_cases:
            _record(reasons, "insufficient_heldout_fov_cases", f"need positive and negative evidence in {min_distinct_source_cases} held-out source cases")
        controls = proposal.get("negative_controls", {})
        if not isinstance(controls, dict) or controls.get("unseen_cells_exact") is not True or controls.get("occluded_cells_exact") is not True:
            _record(reasons, "missing_fov_negative_controls", "FOV must prove both source-unseen and source-occluded cells remain absent.")
    return {
        "schema": "gamebench.nethack.fov_underlay_applicability.v1",
        "status": "eligible" if not reasons else "rejected",
        "reasons": reasons,
        "acceptance": (
            "A cache may reuse exact pre-action direct-static cells. A general FOV rule additionally needs held-out "
            "positive and negative source evidence without future-frame hydration."
        ),
    }


def masked_surface_audit(
    expected_snapshots: Iterable[dict[str, Any]],
    masked_coordinates: Iterable[tuple[int, int]],
) -> dict[str, Any]:
    """Expose direct later pixels hidden by a reset-underlay core mask.

    A reset underlay can be unjudgeable.  It does *not* authorize a score to
    call later source-visible overlays or non-static pixels equal.  This audit
    identifies those masked records so the caller can require a separate
    ``partial_unjudgeable`` result rather than silently granting core credit.
    It accepts only public source snapshots and never synthesizes terrain.
    """

    coordinates = {(int(x), int(y)) for x, y in masked_coordinates}
    direct_later: list[dict[str, Any]] = []
    for step, snapshot in enumerate(expected_snapshots):
        chars = snapshot.get("chars") if isinstance(snapshot, dict) else None
        glyphs = snapshot.get("glyphs") if isinstance(snapshot, dict) else None
        colors = snapshot.get("colors") if isinstance(snapshot, dict) else None
        if not (isinstance(chars, list) and isinstance(glyphs, list) and isinstance(colors, list)):
            continue
        for x, y in sorted(coordinates):
            if not (0 <= y < len(chars) and 0 <= y < len(glyphs) and 0 <= y < len(colors)):
                continue
            if not (isinstance(chars[y], str) and isinstance(glyphs[y], list) and isinstance(colors[y], list) and 0 <= x < len(chars[y]) and x < len(glyphs[y]) and x < len(colors[y])):
                continue
            char = chars[y][x]
            if char not in {" ", "@"} and char not in STATIC_TERRAIN_CHARS:
                direct_later.append({"step": step, "x": x, "y": y, "char": char, "glyph": glyphs[y][x], "color": colors[y][x], "reason": "later_direct_overlay_masked_by_reset_underlay"})
    reason_counts = Counter(record["reason"] for record in direct_later)
    return {
        "schema": "gamebench.nethack.masked_surface_audit.v1",
        "status": "partial_unjudgeable_required" if direct_later else "no_later_direct_overlay_masked",
        "masked_coordinate_count": len(coordinates),
        "later_direct_overlay_records": direct_later,
        "reason_counts": dict(reason_counts),
        "acceptance": "A core score may not report equal/pass solely by masking any listed later direct overlay.",
    }
