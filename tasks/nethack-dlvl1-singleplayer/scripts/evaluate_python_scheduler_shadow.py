#!/usr/bin/env python3
"""Run a fail-closed, public-state-only Python scheduler shadow diagnostic.

This is intentionally *not* an implementation of NetHack monster movement.
The Python gold lane exposes terminal planes, hero blstats, messages,
inventory, and input mode; it does not expose a stable monster identity, its
movement points, target, or a source-cell underlay.  The pinned source makes
those fields prerequisites for ``movemon``/``dochug``/``dog_move`` decisions.

Accordingly the fixed candidate reports ``indeterminate`` at every boundary.
That negative result is useful: it is live-tested on predeclared calibration
and held-out seeds, but cannot silently turn terminal pixels, LLDB records,
or native sidecars into scheduler inputs.  It is kept entirely in this shadow
script and never alters ``gold_python``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Iterable


TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.capture_nle_fixture import (
    OBSERVATION_KEYS,
    action_table,
    deterministic_nle_seeds,
    dungeon_identity,
    level_dump,
    normalise_reset,
)
from scripts.frontier_promotion_gate import SCHEMA as GATE_SCHEMA
from scripts.frontier_promotion_gate import evaluate as evaluate_gate
from shared.task_resolve import resolve_task


SCHEMA = "gamebench.nethack.python_public_scheduler_shadow.v1"
RULE_ID = "public_projection_requires_stable_actor_before_destination_v1"
PINNED_SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
# These are source semantics, rather than a source-state input channel.  In
# particular, this module never imports an LLDB callback, native reader, or
# pre-action sidecar module.
PINNED_SOURCE_SEMANTICS = {
    "source_commit": PINNED_SOURCE_COMMIT,
    "nethack_version": "3.6.6",
    "locations": [
        {"file": "src/mon.c", "lines": [720, 779], "meaning": "movemon orders ready monsters by native fmon state"},
        {"file": "src/monmove.c", "lines": [369, 1222], "meaning": "dochug/m_move needs target and monster state"},
        {"file": "src/dogmove.c", "lines": [862, 1207], "meaning": "dog_move destination depends on pet state and legal move flags"},
    ],
    "conclusion": "A rendered overlay is not a stable actor or a sufficient destination input.",
}
DEFAULT_ACTIONS = ("Command.SEARCH", "MiscDirection.WAIT", "CompassDirection.E", "Command.SEARCH", "MiscDirection.WAIT")


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _module_sha256() -> str:
    """Bind a frozen split to this exact candidate implementation text."""

    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _public_input(public: dict[str, Any]) -> dict[str, Any]:
    """Copy only documented Python public projection fields into the shadow.

    The candidate receives a new JSON-shaped value, not an engine reference,
    so it cannot reach private state after this boundary.
    """

    fields = ("chars", "colors", "glyphs", "specials", "blstats", "message", "message_raw", "inventory", "input_mode", "done")
    return {key: json.loads(json.dumps(public.get(key))) for key in fields}


def public_destination_candidate(public: dict[str, Any]) -> dict[str, Any]:
    """Return the only sound public-state result: no destination claim."""

    state = _public_input(public)
    blstats = state.get("blstats")
    hero = None
    if isinstance(blstats, list) and len(blstats) >= 2 and type(blstats[0]) is int and type(blstats[1]) is int:
        hero = {"x": blstats[0], "y": blstats[1]}
    overlays = 0
    chars = state.get("chars")
    if isinstance(chars, list):
        for row in chars:
            if isinstance(row, str):
                overlays += sum(char not in " .#|-+<>_{}~@\0" for char in row)
            elif isinstance(row, list):
                overlays += sum(type(value) is int and chr(value) not in " .#|-+<>_{}~@\0" for value in row)
    return {
        "schema": "gamebench.nethack.python_public_scheduler_shadow_prediction.v1",
        "rule_id": RULE_ID,
        "input_sha256": _sha256(state),
        "hero": hero,
        "visible_unidentified_overlay_count": overlays,
        "status": "indeterminate",
        "destination": None,
        "reason": "public projection has no stable actor identity, movement points, target state, legal-move flags, or source-cell underlay",
    }


def split_manifest(*, calibration_seeds: Iterable[int], heldout_seeds: Iterable[int], actions: Iterable[str]) -> dict[str, Any]:
    calibration, heldout, action_list = list(calibration_seeds), list(heldout_seeds), list(actions)
    if not calibration or not heldout or set(calibration) & set(heldout):
        raise ValueError("calibration and heldout seeds must be non-empty and disjoint")
    if len(set(calibration + heldout)) != len(calibration + heldout):
        raise ValueError("seed split contains duplicate entries")
    if len(action_list) < 2 or len(set(action_list)) < 2:
        raise ValueError("shadow campaign requires at least two distinct predeclared actions")
    contract = {
        "schema": "gamebench.nethack.python_public_scheduler_shadow_split.v1",
        "rule_id": RULE_ID,
        "candidate_sha256": _module_sha256(),
        "calibration_seeds": calibration,
        "heldout_seeds": heldout,
        "actions": action_list,
        "source_semantics": PINNED_SOURCE_SEMANTICS,
    }
    return {**contract, "split_contract_sha256": _sha256(contract)}


def validate_manifest(manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    actual = {key: value for key, value in manifest.items() if key != "split_contract_sha256"}
    expected_contract = {key: value for key, value in expected.items() if key != "split_contract_sha256"}
    if actual != expected_contract:
        raise ValueError("split manifest is not the exact frozen candidate/split/action contract")
    if manifest.get("split_contract_sha256") != _sha256(expected_contract):
        raise ValueError("split manifest digest mismatch")


def _new_env() -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(
        character="val-hum-fem-law",
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def _named_actions(env: Any, actions: tuple[str, ...]) -> list[tuple[str, int]]:
    indices = {name: index for index, name, _ in action_table(env)}
    unknown = [name for name in actions if name not in indices]
    if unknown:
        raise RuntimeError("pinned NLE action table lacks " + ", ".join(unknown))
    return [(name, indices[name]) for name in actions]


def run_live_case(seed: int, *, phase: str, actions: tuple[str, ...], env_factory: Callable[[], Any] = _new_env) -> dict[str, Any]:
    """Exercise a case without giving the candidate the NLE observation.

    NLE is only an external comparator.  The candidate sees ``engine``'s
    public projection before each action.  The raw native observation is used
    only to step the live comparator and is never serialized into the shadow
    prediction record.
    """

    env = env_factory()
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        raw = normalise_reset(env.reset())
        if dungeon_identity(raw) != (0, 1):
            raise RuntimeError("live scheduler shadow started outside Main Dungeon dlvl 1")
        task = {
            "task_id": f"python-scheduler-shadow-{phase}-{seed}",
            "seed": seed,
            "rules": {"max_steps": len(actions), "auto_more": "raw_explicit"},
            "level_dump": level_dump(raw, {}, observations=[raw]),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        records: list[dict[str, Any]] = []
        for step, (action_name, action_id) in enumerate(_named_actions(env, actions), start=1):
            prediction = public_destination_candidate(engine.public_projection())
            # A prediction with no stable actor/destination is deliberately
            # not compared to a post-action screen.  Such a comparison would
            # backfill the very value the shadow lacks.
            raw_after, _, done, _ = env.step(action_id)
            raw = normalise_reset(raw_after)
            engine.step(action_name)
            records.append(
                {
                    "step": step,
                    "action": action_name,
                    "input_sha256": prediction["input_sha256"],
                    "candidate_status": prediction["status"],
                    "candidate_destination": prediction["destination"],
                    "candidate_outcome_comparison_count": 0,
                    "unavailable_reason": prediction["reason"],
                    "live_nle_stepped": True,
                    "gold_python_stepped": True,
                    "nle_done": bool(done),
                }
            )
            if done:
                break
        return {
            "seed": seed,
            "phase": phase,
            "live_boundary_count": len(records),
            "candidate_outcome_comparison_count": 0,
            "indeterminate_count": len(records),
            "records": records,
        }
    finally:
        env.close()


def _phase_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(cases),
        "live_boundary_count": sum(int(case["live_boundary_count"]) for case in cases),
        "candidate_outcome_comparison_count": 0,
        "indeterminate_count": sum(int(case["indeterminate_count"]) for case in cases),
        "cases": cases,
    }


def build_report(manifest: dict[str, Any], calibration_cases: list[dict[str, Any]], heldout_cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the ordinary promotion gate; this Python-only shadow must fail."""

    calibration, heldout = _phase_summary(calibration_cases), _phase_summary(heldout_cases)
    lane_record = {
        "fixture_id": "python-public-scheduler-shadow-heldout",
        "lane": "python",
        "comparison_count": 0,
        "baseline_first_divergence_step": None,
        "candidate_first_divergence_step": None,
        "baseline_error_count": 0,
        "candidate_error_count": 0,
        "blocker": "no public pre-action actor identity or destination target exists",
    }
    candidate = {
        "schema": GATE_SCHEMA,
        "subsystem": "python_public_scheduler_destination_shadow",
        "validity": {
            "source_identity_pinned": True,
            "captured_pre_action_only": True,
            "no_future_or_reset_hydration": True,
            "no_seed_or_coordinate_lookup": True,
            "source_assertion_repeatable": True,
            "python_rust_parity": False,
            "split_frozen_before_candidate": True,
            "artifact_identity_pinned": True,
        },
        "source_assertions": {"comparison_count": 0, "error_count": 0},
        "heldout": {
            "case_count": heldout["case_count"],
            "comparison_count": 0,
            "counterexample_count": 0,
            "baseline_first_divergence_step": None,
            "candidate_first_divergence_step": None,
            "baseline_error_count": 0,
            "candidate_error_count": 0,
            "calibration_identity_sha256": _sha256(manifest["calibration_seeds"]),
            "heldout_identity_sha256": _sha256(manifest["heldout_seeds"]),
            "artifact_sha256": _sha256(manifest),
            "records": [lane_record],
        },
        "source_export_eligible": False,
        "gold_implementation_eligible": False,
    }
    gate = evaluate_gate(candidate)
    return {
        "schema": SCHEMA,
        "status": "shadow_evaluated_gold_blocked",
        "shadow_only": True,
        "gold_files_modified": False,
        "fixed_before_scoring": manifest,
        "candidate_contract": {
            "rule_id": RULE_ID,
            "input_scope": "gold_python.public_projection() at the action boundary only",
            "forbidden_inputs": ["lldb", "native_sidecar", "mfndpos_candidate_array", "selector_return", "post_action_observation", "gold_python.private_projection"],
            "pinned_source_semantics": PINNED_SOURCE_SEMANTICS,
        },
        "calibration": calibration,
        "heldout": heldout,
        "promotion_candidate": candidate,
        "promotion_gate": gate,
        "gold_implementation_eligible": False,
        "implementation_blockers": gate["failures"],
    }


def _parse_seeds(value: str) -> list[int]:
    try:
        return [int(item) for item in value.split(",") if item]
    except ValueError as error:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-seeds", default="20261401,20261402,20261403")
    parser.add_argument("--heldout-seeds", default="20261404,20261405,20261406")
    parser.add_argument("--actions", default=",".join(DEFAULT_ACTIONS))
    parser.add_argument("--write-split-manifest", type=Path)
    parser.add_argument("--split-manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    calibration, heldout = _parse_seeds(args.calibration_seeds), _parse_seeds(args.heldout_seeds)
    actions = tuple(item.strip() for item in args.actions.split(",") if item.strip())
    expected = split_manifest(calibration_seeds=calibration, heldout_seeds=heldout, actions=actions)
    if args.write_split_manifest:
        if args.split_manifest or args.report:
            raise SystemExit("write the frozen split manifest in a separate command before scoring")
        args.write_split_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_split_manifest.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "split_frozen", "manifest": str(args.write_split_manifest.resolve())}, sort_keys=True))
        return
    if not args.split_manifest or not args.report:
        raise SystemExit("scoring requires a pre-existing --split-manifest and --report")
    manifest = json.loads(args.split_manifest.read_text())
    validate_manifest(manifest, expected)
    calibration_cases = [run_live_case(seed, phase="calibration", actions=actions) for seed in calibration]
    heldout_cases = [run_live_case(seed, phase="heldout", actions=actions) for seed in heldout]
    report = build_report(manifest, calibration_cases, heldout_cases)
    report["split_manifest_path"] = str(args.split_manifest.resolve())
    report["split_manifest_file_sha256"] = "sha256:" + hashlib.sha256(args.split_manifest.read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "gold_implementation_eligible": False, "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
