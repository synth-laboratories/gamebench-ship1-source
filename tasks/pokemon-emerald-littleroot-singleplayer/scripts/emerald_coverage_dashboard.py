#!/usr/bin/env python3
"""Report source-backed coverage for the scoped Pokémon Emerald route.

The dashboard deliberately distinguishes *coverage evidence* from Rust
implementation and transport checks.  In particular, a Rust-vs-Rust transport
contract can never raise a source-validity rate.  Missing evidence is emitted
as ``UNKNOWN`` (or ``UNSUPPORTED`` for an unreadable/new schema), never zero or
an inferred pass.

Only a source_behavior_oracle report with the pinned ROM/state identity counts
as a source differential.  Frozen-frame manifest entries are endpoint evidence
only; they do not imply a continuous tape.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# Keep the standalone dashboard and its ROM-free test importable from an
# arbitrary current working directory.  ``unittest discover`` and importlib
# loaders otherwise omit this script directory from ``sys.path``.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from emerald_oracle_registry import (
    RegistryError,
    load_registry as load_oracle_registry,
    oracle_quarantine_reason,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "fixtures/gold/coverage_registry.json"
DEFAULT_FRAMES = ROOT / "fixtures/gold/frames/manifest.json"
DEFAULT_ORACLE = ROOT / "fixtures/gold/oracle_manifest.json"
DEFAULT_ORACLE_REGISTRY = ROOT / "fixtures/gold/oracle_registry.json"
REGISTRY_SCHEMA = "gamebench.pokemon_emerald.coverage_registry.v1"
TAPE_SCHEMA = "gamebench.pokemon_emerald.coverage_tapes.v1"
FRAME_SCHEMA = "gamebench.pixel-oracle.v1"
ORACLE_SCHEMA = "gamebench.pokemon_emerald.mgba_oracle.v1"
SOURCE_TRACE_SCHEMA = "gamebench.pokemon_emerald.source_vblank_tape.v1"
CAPTURE_TRACE_SCHEMA = "gamebench.pokemon_emerald.capture_vblank_trace.v1"
CAPTURE_RECEIPT_SCHEMA = "gamebench.pokemon_emerald.oracle_snapshot_capture.v2"
UNKNOWN = {"status": "unknown"}
UNSUPPORTED = {"status": "unsupported"}


class DashboardError(RuntimeError):
    """An explicit input error; do not silently reinterpret evidence."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardError(f"cannot read JSON {path}: {exc}") from exc


def status_count(value: int) -> dict[str, Any]:
    return {"status": "known", "count": value}


def status_list(values: Iterable[str]) -> dict[str, Any]:
    return {"status": "known", "values": sorted(set(values))}


def status_rate(exact: int, total: int) -> dict[str, Any]:
    if total <= 0:
        return dict(UNKNOWN)
    return {"status": "known", "exact": exact, "total": total, "rate": exact / total}


def load_registry(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, dict) or data.get("schema") != REGISTRY_SCHEMA:
        raise DashboardError(f"unsupported coverage registry schema in {path}")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise DashboardError("coverage registry must contain a non-empty segments list")
    ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise DashboardError("coverage registry segment must be an object")
        segment_id = segment.get("id")
        name = segment.get("name")
        if not isinstance(segment_id, str) or not segment_id or not isinstance(name, str) or not name:
            raise DashboardError("coverage registry segments require non-empty id and name")
        if segment_id in ids:
            raise DashboardError(f"duplicate coverage segment id: {segment_id}")
        ids.add(segment_id)
        validated.append(segment)
    return validated


def load_manifest(path: Path, expected_schema: str) -> tuple[Any, str | None]:
    try:
        data = read_json(path)
    except DashboardError:
        return None, "unsupported"
    if not isinstance(data, dict) or data.get("schema") != expected_schema:
        return None, "unsupported"
    return data, None


def load_tape_specs(paths: list[Path], known_ids: set[str]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    by_segment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    problems: list[str] = []
    for path in paths:
        data, issue = load_manifest(path, TAPE_SCHEMA)
        if issue:
            problems.append(f"UNSUPPORTED tape spec: {path}")
            continue
        tapes = data.get("tapes")
        if not isinstance(tapes, list):
            problems.append(f"UNSUPPORTED tape spec (missing tapes): {path}")
            continue
        for tape in tapes:
            if not isinstance(tape, dict) or not isinstance(tape.get("segment"), str):
                problems.append(f"UNSUPPORTED tape entry: {path}")
                continue
            if tape["segment"] not in known_ids:
                problems.append(f"UNKNOWN tape segment {tape['segment']}: {path}")
                continue
            by_segment[tape["segment"]].append(tape)
    return by_segment, problems


def source_reports(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return only explicitly identified source-oracle lanes.

    Unknown report schemas are retained as a diagnostic, rather than being
    mistaken for a successful source run.  Rust transport lanes are ignored.
    """
    lanes: list[dict[str, Any]] = []
    problems: list[str] = []
    for path in paths:
        try:
            report = read_json(path)
        except DashboardError:
            problems.append(f"UNSUPPORTED report: {path}")
            continue
        if not isinstance(report, dict) or report.get("schema_version") not in (2, 3):
            problems.append(f"UNSUPPORTED report schema: {path}")
            continue
        report_lanes = report.get("lanes")
        if not isinstance(report_lanes, list):
            problems.append(f"UNSUPPORTED report lanes: {path}")
            continue
        for lane in report_lanes:
            if isinstance(lane, dict) and lane.get("lane") == "source_behavior_oracle":
                lanes.append({"path": str(path), "lane": lane})
    return lanes, problems


def authenticated_lane(
    lane: dict[str, Any],
    oracle: dict[str, Any] | None,
    state_sha: str | None,
    source_registry: tuple[dict[str, Any], dict[str, Any]] | None,
) -> bool:
    """Accept a lane only when it matches an explicitly registered source identity."""
    if source_registry is not None and oracle_quarantine_reason(source_registry[0]) is not None:
        return False
    comparison = lane.get("pixel_comparison")
    if not isinstance(comparison, dict):
        return False
    if comparison.get("cadence") != "every VBlank" or comparison.get("tolerance") != 0:
        return False
    checkpoint_id = lane.get("oracle_checkpoint")
    if source_registry is not None and isinstance(checkpoint_id, str):
        registry, checkpoints = source_registry
        checkpoint = checkpoints.get(checkpoint_id)
        if checkpoint is None or not checkpoint.authenticated or checkpoint.source is None:
            return False
        return (
            lane.get("rom_sha256") == registry.get("rom_sha256")
            and lane.get("state_sha256") == checkpoint.source.get("state_sha256")
        )
    if oracle is None or state_sha is None:
        return False
    source = oracle.get("source")
    if not isinstance(source, dict):
        return False
    return (
        lane.get("rom_sha256") == source.get("rom_sha256")
        and lane.get("state_sha256") == state_sha
        and source.get("state_sha256") == state_sha
    )


def segment_has_authenticated_source_state(
    segment: dict[str, Any],
    source_registry: tuple[dict[str, Any], dict[str, Any]] | None,
) -> bool:
    """Whether a segment names an authenticated, identity-consistent source state.

    This is intentionally weaker than ``authenticated_lane``: it makes an
    authenticated endpoint visible, but does not turn a snapshot into a
    differential pass.  A stale ``oracle_state_sha256`` is rejected rather
    than silently accepting the registry's newer state.
    """
    if source_registry is None:
        return False
    _, checkpoints = source_registry
    ids: list[str] = []
    checkpoint = segment.get("checkpoint")
    if isinstance(checkpoint, str):
        ids.append(checkpoint)
    declared = segment.get("oracle_checkpoints")
    if isinstance(declared, list):
        ids.extend(value for value in declared if isinstance(value, str))
    expected_sha = segment.get("oracle_state_sha256")
    if expected_sha is not None and not isinstance(expected_sha, str):
        return False
    for checkpoint_id in ids:
        candidate = checkpoints.get(checkpoint_id)
        if candidate is None or not candidate.authenticated or candidate.source is None:
            continue
        if expected_sha is None or candidate.source.get("state_sha256") == expected_sha:
            return True
    return False


def segment_for_case(case: dict[str, Any], segments: list[dict[str, Any]], lane: dict[str, Any]) -> str | None:
    explicit = case.get("coverage_segment")
    if isinstance(explicit, str):
        return explicit
    checkpoint = case.get("checkpoint")
    if isinstance(checkpoint, str):
        for segment in segments:
            if segment.get("checkpoint") == checkpoint:
                return str(segment["id"])
    oracle_checkpoint = lane.get("oracle_checkpoint")
    if isinstance(oracle_checkpoint, str):
        for segment in segments:
            if oracle_checkpoint in segment.get("oracle_checkpoints", []):
                return str(segment["id"])
    state_sha = lane.get("state_sha256")
    for segment in segments:
        if state_sha and segment.get("oracle_state_sha256") == state_sha:
            return str(segment["id"])
    return None


def accumulated_oracle_metrics(
    segment_id: str,
    segments: list[dict[str, Any]],
    lanes: list[dict[str, Any]],
    oracle: dict[str, Any] | None,
    source_registry: tuple[dict[str, Any], dict[str, Any]] | None,
) -> dict[str, Any] | None:
    matched: list[dict[str, Any]] = []
    for entry in lanes:
        lane = entry["lane"]
        segment = next(item for item in segments if item["id"] == segment_id)
        if not authenticated_lane(lane, oracle, segment.get("oracle_state_sha256"), source_registry):
            continue
        cases = lane.get("cases")
        if not isinstance(cases, list):
            continue
        selected = [case for case in cases if isinstance(case, dict) and segment_for_case(case, segments, lane) == segment_id]
        if selected:
            matched.extend(selected)
    if not matched:
        return None
    frames = sum(int(case.get("compared_source_frames", 0)) for case in matched)
    canonical = [
        case
        for case in matched
        if case.get("canonical") is True
        or case.get("origin") != "deterministic random fuzz"
    ]
    pixel_mismatches = sum(int(case.get("pixel_mismatch_frames", 0)) for case in matched)
    semantic_total = sum(1 + len(case.get("semantic_boundaries", [])) for case in matched)
    semantic_mismatches = sum(int(case.get("semantic_boundary_mismatches", 0)) for case in matched)
    return {
        "canonical_tapes": len(canonical),
        "source_tapes": len(matched),
        "vblanks": frames,
        "pixel_rate": status_rate(frames - pixel_mismatches, frames),
        "semantic_rate": status_rate(semantic_total - semantic_mismatches, semantic_total),
        "semantic_fields": ["map", "player.x", "player.y"],
    }


def frozen_count(segment: dict[str, Any], traces: list[Any] | None) -> int | None:
    if traces is None:
        return None
    needle = segment.get("frozen_source_state_contains")
    if not isinstance(needle, str):
        return 0
    return sum(
        1
        for trace in traces
        if isinstance(trace, dict) and needle in str(trace.get("source_state", ""))
    )


def checkpoint_segment(checkpoint_id: str, segments: list[dict[str, Any]]) -> str | None:
    """Resolve registry evidence through the declarative coverage mapping."""
    for segment in segments:
        if checkpoint_id in segment.get("oracle_checkpoints", []):
            return str(segment["id"])
    for segment in segments:
        excluded = segment.get("oracle_checkpoint_excluded_prefixes", [])
        if any(checkpoint_id.startswith(prefix) for prefix in excluded):
            continue
        prefixes = segment.get("oracle_checkpoint_prefixes", [])
        if any(checkpoint_id.startswith(prefix) for prefix in prefixes):
            return str(segment["id"])
    return None


def snapshot_vblanks(checkpoint: Any) -> int | None:
    capture = checkpoint.capture
    provenance = capture.get("provenance")
    if not isinstance(provenance, dict):
        return None
    value = provenance.get("snapshot_frame_number")
    return value if isinstance(value, int) and value >= 0 else None


def continuous_battle_evidence(checkpoint: Any) -> tuple[int, int]:
    """Return explicit continuous-trace count/VBlanks, never inferred parity."""
    capture = checkpoint.capture
    smoke = capture.get("continuous_battle_trace_smoke")
    if isinstance(smoke, dict) and smoke.get("status") == "validated_continuous":
        vblanks = smoke.get("vblank_count")
        return 1, vblanks if isinstance(vblanks, int) and vblanks >= 0 else 0
    procedure = str(capture.get("procedure", "")).lower()
    source_split = str(checkpoint.source_split).lower()
    explicitly_continuous = (
        "continuous" in checkpoint.checkpoint_id
        or "continuous battle trace" in procedure
        or "continuous no-reload" in source_split
    )
    if not explicitly_continuous:
        return 0, 0
    return 1, snapshot_vblanks(checkpoint) or 0


def registry_coverage_evidence(
    segments: list[dict[str, Any]],
    source_registry: tuple[dict[str, Any], dict[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {
        str(segment["id"]): {
            "authenticated_checkpoints": 0,
            "capture_required_checkpoints": 0,
            "quarantined_checkpoints": 0,
            "snapshot_vblank_total": 0,
            "snapshots_with_vblank_count": 0,
            "snapshots_without_vblank_count": 0,
            "continuous_battle_traces": 0,
            "continuous_battle_vblank_total": 0,
            "checkpoint_ids": [],
        }
        for segment in segments
    }
    unassigned = {"authenticated": 0, "capture_required": 0, "quarantined": 0, "ids": []}
    if source_registry is None:
        return buckets, {"status": "unsupported", "unassigned": unassigned}
    _, checkpoints = source_registry
    for checkpoint_id, checkpoint in checkpoints.items():
        segment_id = checkpoint_segment(checkpoint_id, segments)
        if segment_id is None:
            status_key = (
                "authenticated" if checkpoint.status == "authenticated"
                else "quarantined" if checkpoint.status.startswith("quarantined")
                else "capture_required"
            )
            unassigned[status_key] += 1
            unassigned["ids"].append(checkpoint_id)
            continue
        bucket = buckets[segment_id]
        bucket["checkpoint_ids"].append(checkpoint_id)
        if checkpoint.status == "authenticated":
            bucket["authenticated_checkpoints"] += 1
            vblanks = snapshot_vblanks(checkpoint)
            if vblanks is None:
                bucket["snapshots_without_vblank_count"] += 1
            else:
                bucket["snapshot_vblank_total"] += vblanks
                bucket["snapshots_with_vblank_count"] += 1
            trace_count, trace_vblanks = continuous_battle_evidence(checkpoint)
            bucket["continuous_battle_traces"] += trace_count
            bucket["continuous_battle_vblank_total"] += trace_vblanks
        elif checkpoint.status.startswith("quarantined"):
            bucket["quarantined_checkpoints"] += 1
        else:
            bucket["capture_required_checkpoints"] += 1
    totals = {
        "status": "known",
        "authenticated_checkpoints": sum(b["authenticated_checkpoints"] for b in buckets.values()),
        "capture_required_checkpoints": sum(b["capture_required_checkpoints"] for b in buckets.values()),
        "quarantined_checkpoints": sum(b["quarantined_checkpoints"] for b in buckets.values()),
        "snapshot_vblank_total": sum(b["snapshot_vblank_total"] for b in buckets.values()),
        "continuous_battle_traces": sum(b["continuous_battle_traces"] for b in buckets.values()),
        "continuous_battle_vblank_total": sum(b["continuous_battle_vblank_total"] for b in buckets.values()),
        "unassigned": unassigned,
        "counting_note": "Snapshot and continuous-trace VBlank totals overlap across capture chains and branches; they are non-unique evidence volume, not route length or differential exactness.",
    }
    return buckets, totals


def spec_coverage(tapes: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Count task labels only after a spec declares source-authenticated execution."""
    executed = [
        tape for tape in tapes
        if isinstance(tape.get("source_execution"), dict)
        and tape["source_execution"].get("status") == "authenticated"
    ]
    if not executed:
        return dict(UNKNOWN), dict(UNKNOWN), dict(UNKNOWN)
    states: list[str] = []
    transitions: list[str] = []
    outcomes: list[str] = []
    for tape in executed:
        visited = tape.get("visited")
        if not isinstance(visited, dict):
            continue
        for key, destination in (("input_owner_task_states", states), ("transitions", transitions), ("outcomes", outcomes)):
            values = visited.get(key)
            if isinstance(values, list) and all(isinstance(item, str) for item in values):
                destination.extend(values)
    return (
        status_list(states) if states else dict(UNKNOWN),
        status_list(transitions) if transitions else dict(UNKNOWN),
        status_list(outcomes) if outcomes else dict(UNKNOWN),
    )


def digest_is_valid(value: dict[str, Any], field: str) -> bool:
    """Validate a write-once evidence digest without treating absent as pass."""
    stored = value.get(field)
    if not isinstance(stored, str) or len(stored) != 64:
        return False
    reduced = dict(value)
    reduced.pop(field, None)
    return stored == hashlib.sha256(canonical_json(reduced).encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def authenticated_checkpoint_for_identity(
    identity: Any, source_registry: tuple[dict[str, Any], dict[str, Any]] | None
) -> str | None:
    if not isinstance(identity, dict) or source_registry is None:
        return None
    if oracle_quarantine_reason(source_registry[0]) is not None:
        return None
    registry, checkpoints = source_registry
    if identity.get("rom_sha256") != registry.get("rom_sha256"):
        return None
    if identity.get("emulator") != registry["oracle"].get("emulator"):
        return None
    if identity.get("config") != registry["oracle"].get("config"):
        return None
    source_sha = identity.get("state_sha256", identity.get("source_state_sha256"))
    for checkpoint_id, checkpoint in checkpoints.items():
        if checkpoint.authenticated and checkpoint.source and source_sha == checkpoint.source.get("state_sha256"):
            return checkpoint_id
    return None


def observed_map_transitions(frames: Any) -> list[str]:
    if not isinstance(frames, list):
        return []
    transitions: list[str] = []
    previous: tuple[int, int] | None = None
    for frame in frames:
        state = frame.get("source_state") if isinstance(frame, dict) else None
        if not isinstance(state, dict) or not isinstance(state.get("map_group"), int) or not isinstance(state.get("map_number"), int):
            continue
        current = (state["map_group"], state["map_number"])
        if previous is not None and current != previous:
            transitions.append(f"map:{previous[0]}:{previous[1]}→{current[0]}:{current[1]}")
        previous = current
    return sorted(set(transitions))


def segment_for_trace(
    declared: Any, checkpoint_id: str, trace_id: Any, segments: list[dict[str, Any]]
) -> str | None:
    known = {str(segment["id"]) for segment in segments}
    if isinstance(declared, str) and declared in known:
        return declared
    if isinstance(trace_id, str):
        explicit = [
            str(segment["id"]) for segment in segments
            if trace_id in segment.get("source_trace_ids", [])
        ]
        if len(explicit) == 1:
            return explicit[0]
    matching = [
        str(segment["id"])
        for segment in segments
        if checkpoint_id in segment.get("oracle_checkpoints", []) or segment.get("checkpoint") == checkpoint_id
    ]
    return matching[0] if len(matching) == 1 else None


def trace_evidence(
    trace_paths: list[Path], receipt_paths: list[Path],
    source_registry: tuple[dict[str, Any], dict[str, Any]] | None,
    segments: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], int]:
    """Return source-captured (not source-differential) accounting by segment.

    A route trace proves that live mGBA traversed the recorded VBlanks.  It is
    useful coverage, but deliberately carries no Rust pixel/state success
    rate.  A planned tape or a frozen frame cannot enter this function.
    """
    result: dict[str, dict[str, Any]] = defaultdict(lambda: {"tapes": 0, "vblanks": 0, "transitions": []})
    diagnostics: list[str] = []
    unassigned = 0

    def accept(trace: dict[str, Any], trace_path: Path, *, receipt: dict[str, Any] | None = None) -> None:
        nonlocal unassigned
        schema = trace.get("schema")
        if schema not in (SOURCE_TRACE_SCHEMA, CAPTURE_TRACE_SCHEMA) or not digest_is_valid(trace, "trace_sha256"):
            diagnostics.append(f"UNSUPPORTED or invalid source trace: {trace_path}")
            return
        checkpoint_id = authenticated_checkpoint_for_identity(trace.get("source_identity"), source_registry)
        if checkpoint_id is None:
            diagnostics.append(f"UNAUTHENTICATED source trace identity: {trace_path}")
            return
        if not isinstance(trace.get("frames"), list) or not trace["frames"]:
            diagnostics.append(f"INVALID source trace frames: {trace_path}")
            return
        declared: Any = None
        trace_id: Any = None
        if schema == SOURCE_TRACE_SCHEMA and isinstance(trace.get("tape"), dict):
            declared = trace["tape"].get("coverage_segment")
            trace_id = trace["tape"].get("id")
        if schema == CAPTURE_TRACE_SCHEMA and isinstance(trace.get("capture_tape"), dict):
            declared = trace["capture_tape"].get("coverage_segment")
            trace_id = trace["capture_tape"].get("id")
        segment_id = segment_for_trace(declared, checkpoint_id, trace_id, segments)
        if segment_id is None:
            unassigned += 1
            diagnostics.append(f"UNASSIGNED authenticated source trace (declare coverage_segment): {trace_path}")
            return
        if receipt is not None and receipt.get("capture_trace_sha256") != trace.get("trace_sha256"):
            diagnostics.append(f"capture receipt/trace mismatch: {trace_path}")
            return
        result[segment_id]["tapes"] += 1
        result[segment_id]["vblanks"] += int(trace.get("frame_count", len(trace["frames"])))
        result[segment_id]["transitions"].extend(observed_map_transitions(trace["frames"]))

    for path in trace_paths:
        try:
            accept(read_json(path), path)
        except DashboardError:
            diagnostics.append(f"UNSUPPORTED source trace: {path}")
    for receipt_path in receipt_paths:
        try:
            receipt = read_json(receipt_path)
        except DashboardError:
            diagnostics.append(f"UNSUPPORTED capture receipt: {receipt_path}")
            continue
        if receipt.get("schema") != CAPTURE_RECEIPT_SCHEMA or not digest_is_valid(receipt, "receipt_sha256"):
            diagnostics.append(f"UNSUPPORTED or invalid capture receipt: {receipt_path}")
            continue
        raw_path = receipt.get("capture_trace_path")
        trace_path = Path(raw_path) if isinstance(raw_path, str) else None
        if trace_path is None or not trace_path.is_file():
            diagnostics.append(f"capture receipt trace unavailable: {receipt_path}")
            continue
        try:
            accept(read_json(trace_path), trace_path, receipt=receipt)
        except DashboardError:
            diagnostics.append(f"UNSUPPORTED capture trace: {trace_path}")
    for values in result.values():
        values["transitions"] = sorted(set(values["transitions"]))
    return result, diagnostics, unassigned


def build_dashboard(
    registry_path: Path,
    frames_path: Path,
    oracle_path: Path,
    oracle_registry_path: Path,
    report_paths: list[Path],
    tape_paths: list[Path],
    source_trace_paths: list[Path] | None = None,
    capture_receipt_paths: list[Path] | None = None,
) -> dict[str, Any]:
    segments = load_registry(registry_path)
    frame_manifest, frame_issue = load_manifest(frames_path, FRAME_SCHEMA)
    oracle, oracle_issue = load_manifest(oracle_path, ORACLE_SCHEMA)
    try:
        source_registry = load_oracle_registry(oracle_registry_path)
        quarantine_reason = oracle_quarantine_reason(source_registry[0])
        oracle_registry_issue = f"quarantined: {quarantine_reason}" if quarantine_reason else None
    except RegistryError:
        source_registry = None
        oracle_registry_issue = "unsupported"
    traces = frame_manifest.get("traces") if isinstance(frame_manifest, dict) and isinstance(frame_manifest.get("traces"), list) else None
    if frame_manifest is not None and traces is None:
        frame_issue = "unsupported"
    specs, spec_problems = load_tape_specs(tape_paths, {str(segment["id"]) for segment in segments})
    lanes, report_problems = source_reports(report_paths)
    trace_metrics, trace_problems, unassigned_traces = trace_evidence(
        source_trace_paths or [], capture_receipt_paths or [], source_registry, segments
    )
    registry_buckets, registry_totals = registry_coverage_evidence(segments, source_registry)
    rows: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = str(segment["id"])
        oracle_metrics = accumulated_oracle_metrics(
            segment_id, segments, lanes, oracle, source_registry
        )
        tape_specs = specs.get(segment_id, [])
        owners, transitions, outcomes = spec_coverage(tape_specs)
        trace_metric = trace_metrics.get(segment_id)
        registry_evidence = registry_buckets[segment_id]
        frozen = frozen_count(segment, traces)
        if oracle_metrics:
            level = "source_differential"
            source_state = {"status": "authenticated", "available": True}
            tapes = status_count(oracle_metrics["canonical_tapes"])
            vblanks = status_count(oracle_metrics["vblanks"])
            semantic_fields = status_list(oracle_metrics["semantic_fields"])
            semantic_rate = oracle_metrics["semantic_rate"]
            pixel_rate = oracle_metrics["pixel_rate"]
        elif registry_evidence["authenticated_checkpoints"] > 0:
            # A verified source savestate proves that the named boundary is
            # reproducible. It is deliberately not credited as behavior or
            # pixel correctness until a matching source-vs-Rust lane exists.
            level = "authenticated_capture_chain"
            source_state = {"status": "authenticated", "available": True}
            tapes, vblanks, semantic_fields, semantic_rate, pixel_rate = (dict(UNKNOWN),) * 5
        elif frozen is not None and frozen > 0:
            level = "frozen_frame"
            source_state = {"status": "frozen_reference_only", "available": False}
            tapes, vblanks, semantic_fields, semantic_rate, pixel_rate = (dict(UNKNOWN),) * 5
        else:
            level = "functional_only"
            source_state = dict(UNKNOWN)
            tapes, vblanks, semantic_fields, semantic_rate, pixel_rate = (dict(UNKNOWN),) * 5
        if tape_specs and not oracle_metrics:
            # A declarative plan proves intended coverage only, not execution.
            level = "tape_spec_unexecuted"
        # Source-only route recordings are live, authenticated coverage but
        # cannot be presented as Rust correctness.  A differential lane still
        # takes precedence when both exist.
        if trace_metric and not oracle_metrics:
            level = "source_trace_only"
            source_state = {"status": "authenticated", "available": True}
        observed = status_list(trace_metric["transitions"]) if trace_metric else dict(UNKNOWN)
        rows.append({
            "id": segment_id,
            "name": segment["name"],
            "checkpoint": segment.get("checkpoint"),
            "authenticated_source_state": source_state,
            "canonical_tapes": tapes,
            "source_tapes_compared": status_count(oracle_metrics["source_tapes"]) if oracle_metrics else dict(UNKNOWN),
            "source_tapes_captured": status_count(trace_metric["tapes"]) if trace_metric else dict(UNKNOWN),
            "source_vblanks_captured": status_count(trace_metric["vblanks"]) if trace_metric else dict(UNKNOWN),
            "vblanks": vblanks,
            "semantic_fields_compared": semantic_fields,
            "input_owner_task_states_visited": owners,
            "transitions_exercised": transitions,
            "outcomes_exercised": outcomes,
            "observed_map_transitions": observed,
            "exact_state_rate": semantic_rate,
            "exact_pixel_rate": pixel_rate,
            "frozen_endpoint_frames": dict(UNSUPPORTED) if frame_issue else status_count(frozen or 0),
            "registry_checkpoint_evidence": registry_evidence,
            "capture_chain_snapshot_vblanks": {
                "status": "known" if source_registry is not None else "unsupported",
                "total": registry_evidence["snapshot_vblank_total"],
                "overlapping_non_unique": True,
                "differential_exactness": False,
            },
            "continuous_battle_trace_count": status_count(registry_evidence["continuous_battle_traces"]),
            "continuous_battle_trace_vblanks": {
                "status": "known" if source_registry is not None else "unsupported",
                "total": registry_evidence["continuous_battle_vblank_total"],
                "overlapping_non_unique": True,
                "differential_exactness": False,
            },
            "evidence_level": level,
        })
    diagnostics = spec_problems + report_problems + trace_problems
    if unassigned_traces:
        diagnostics.append(f"UNASSIGNED authenticated source traces: {unassigned_traces}")
    if frame_issue:
        diagnostics.append(f"UNSUPPORTED frozen-frame manifest: {frames_path}")
    if oracle_issue:
        diagnostics.append(f"UNSUPPORTED oracle manifest: {oracle_path}")
    if oracle_registry_issue:
        prefix = "QUARANTINED" if oracle_registry_issue.startswith("quarantined:") else "UNSUPPORTED"
        diagnostics.append(f"{prefix} oracle registry: {oracle_registry_path}; {oracle_registry_issue}")
    final_departure: dict[str, Any] = {"status": "unknown"}
    if source_registry is not None:
        departure = source_registry[1].get("running_shoes_departure")
        if departure is not None and departure.source is not None:
            if departure.authenticated:
                claim = (
                    "Stable Route 101 field boundary after Running Shoes; "
                    "endpoint/capture-chain evidence, not differential exactness."
                )
            elif departure.status.startswith("quarantined"):
                claim = (
                    "Route 101 snapshot metadata is retained for audit but its "
                    "provenance is quarantined; it is not an authenticated "
                    "endpoint, capture-chain evidence, or differential exactness."
                )
            else:
                claim = (
                    "Route 101 source snapshot is not authenticated; it does not "
                    "count as endpoint, capture-chain, or differential evidence."
                )
            final_departure = {
                "status": departure.status,
                "checkpoint": departure.checkpoint_id,
                "source_state": departure.source["initial_state"],
                "snapshot_frame_number": snapshot_vblanks(departure),
                "claim": claim,
            }
    return {
        "schema": "gamebench.pokemon_emerald.coverage_dashboard.v1",
        "scope": "opening through Running Shoes / Route 101 departure",
        "rules": {
            "source_validity": "Only authenticated source_behavior_oracle lanes count as source correctness.",
            "transport_contracts": "Rust-vs-Rust transport checks are excluded from source validity and rates.",
            "missing_evidence": "UNKNOWN/UNSUPPORTED is fail-closed and is never converted to a zero or pass."
        },
        "inputs": {
            "reports": [str(path) for path in report_paths],
            "tape_specs": [str(path) for path in tape_paths],
            "source_traces": [str(path) for path in source_trace_paths or []],
            "capture_receipts": [str(path) for path in capture_receipt_paths or []],
            "oracle_registry": str(oracle_registry_path),
        },
        "diagnostics": diagnostics,
        "registry_capture_chain_totals": registry_totals,
        "final_route101_departure": final_departure,
        "segments": rows,
    }


def format_rate(metric: dict[str, Any]) -> str:
    if metric.get("status") != "known":
        return metric.get("status", "unknown").upper()
    return f"{metric['exact']}/{metric['total']} ({metric['rate'] * 100:.1f}%)"


def format_count(metric: dict[str, Any]) -> str:
    return str(metric["count"]) if metric.get("status") == "known" else metric.get("status", "unknown").upper()


def format_table_text(dashboard: dict[str, Any]) -> str:
    lines = [
        "Coverage evidence only — transport/self-consistency is excluded from validity",
        "segment | evidence | diff tapes/VB | state exact | pixel exact | registry A/P/Q | snapshot VB* | continuous battle traces/VB",
    ]
    for row in dashboard["segments"]:
        registry = row["registry_checkpoint_evidence"]
        lines.append(" | ".join((
            row["id"], row["evidence_level"],
            f"{format_count(row['canonical_tapes'])}/{format_count(row['vblanks'])}",
            format_rate(row["exact_state_rate"]), format_rate(row["exact_pixel_rate"]),
            f"{registry['authenticated_checkpoints']}/{registry['capture_required_checkpoints']}/{registry['quarantined_checkpoints']}",
            str(row["capture_chain_snapshot_vblanks"]["total"]),
            f"{format_count(row['continuous_battle_trace_count'])}/{row['continuous_battle_trace_vblanks']['total']}",
        )))
    lines.append("* snapshot/continuous VBlank totals overlap across branches and capture chains; they are non-unique evidence volume, never differential exactness")
    departure = dashboard.get("final_route101_departure", {})
    lines.append(f"final Route101 departure: {departure.get('status', 'unknown')}")
    return "\n".join(lines) + "\n"


def print_table(dashboard: dict[str, Any]) -> None:
    print(format_table_text(dashboard), end="")
    for diagnostic in dashboard["diagnostics"]:
        print(f"diagnostic: {diagnostic}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--frames", type=Path, default=DEFAULT_FRAMES)
    parser.add_argument("--oracle-manifest", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--oracle-registry", type=Path, default=DEFAULT_ORACLE_REGISTRY)
    parser.add_argument("--report", type=Path, action="append", default=[])
    parser.add_argument("--tape-spec", type=Path, action="append", default=[])
    parser.add_argument("--source-trace", type=Path, action="append", default=[], help="authenticated live source-only VBlank trace")
    parser.add_argument("--capture-receipt", type=Path, action="append", default=[], help="authenticated snapshot receipt with capture trace")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--table-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        dashboard = build_dashboard(
            args.registry, args.frames, args.oracle_manifest, args.oracle_registry,
            args.report, args.tape_spec, args.source_trace, args.capture_receipt,
        )
    except DashboardError as exc:
        print(f"coverage dashboard failed closed: {exc}", file=sys.stderr)
        return 2
    print_table(dashboard)
    encoded = json.dumps(dashboard, indent=2, sort_keys=True) + "\n"
    for output in (args.json_out, args.table_out):
        if output is not None and output.exists():
            print(f"coverage dashboard failed closed: refusing to overwrite {output}", file=sys.stderr)
            return 2
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded, encoding="utf-8")
    else:
        print(encoded)
    if args.table_out:
        args.table_out.parent.mkdir(parents=True, exist_ok=True)
        args.table_out.write_text(format_table_text(dashboard), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
