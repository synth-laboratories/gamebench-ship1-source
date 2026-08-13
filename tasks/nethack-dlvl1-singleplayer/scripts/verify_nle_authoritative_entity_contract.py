#!/usr/bin/env python3
"""Audit whether pinned NLE exposes an authoritative dynamic-entity export.

This command intentionally cannot turn a reproducible seed into a scheduler.
It inspects every documented NLE 0.9.0 observation key and public method,
replays each held-out seed twice, and fails hard if public observation
repeatability changes.  A successful probe reports ``rejected`` because the
source lacks the required entity/underlay/scheduler/RNG export; that rejection
is the validity result, not a passing conformance lane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import deterministic_nle_seeds
from scripts.nle_authoritative_entity_contract import (
    NLE_090_OBSERVATION_KEYS,
    evaluate_nle_090_public_surface,
    validate_authoritative_entity_export,
)


def _array_digest(value: Any) -> str:
    """Hash public observation bytes plus shape/dtype, without serializing a map."""

    hasher = hashlib.sha256()
    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    hasher.update(repr(tuple(shape) if shape is not None else None).encode("utf-8"))
    hasher.update(repr(str(dtype)).encode("utf-8"))
    if hasattr(value, "tobytes"):
        hasher.update(value.tobytes())
    else:  # pragma: no cover - live NLE always returns numpy arrays
        hasher.update(repr(value).encode("utf-8"))
    return hasher.hexdigest()


def _public_observation_digest(observation: dict[str, Any]) -> dict[str, str]:
    missing = sorted(NLE_090_OBSERVATION_KEYS - set(observation))
    if missing:
        raise AssertionError(f"NLE live audit omitted documented observation buffers: {missing}")
    return {key: _array_digest(observation[key]) for key in sorted(NLE_090_OBSERVATION_KEYS)}


def _new_env() -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(
        character="val-hum-fem-law",
        observation_keys=tuple(sorted(NLE_090_OBSERVATION_KEYS)),
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def probe_seed(seed: int) -> dict[str, Any]:
    import nle
    from nle import nethack

    attempts: list[dict[str, str]] = []
    method_inventory: dict[str, list[str]] | None = None
    for _ in range(2):
        env = _new_env()
        try:
            core, display = deterministic_nle_seeds(seed)
            env.seed(core=core, disp=display, reseed=False)
            observation = env.reset()
            if not isinstance(observation, dict):
                raise AssertionError("expected NLE Dict observation for full public observation audit")
            attempts.append(_public_observation_digest(observation))
            candidate = {
                "observation_keys": sorted(nethack.OBSERVATION_DESC),
                "environment_methods": [name for name in dir(type(env)) if not name.startswith("_")],
                # ``env.nethack`` is NLE's documented raw wrapper.  Do not
                # reach through it to its private extension object: a private
                # pointer is not a versioned public capture contract.
                "low_level_methods": [name for name in dir(type(env.nethack)) if not name.startswith("_")],
            }
            if method_inventory is None:
                method_inventory = candidate
            elif candidate != method_inventory:
                raise AssertionError("NLE public capability inventory differed between identical held-out replays")
        finally:
            env.close()
    if attempts[0] != attempts[1]:
        changed = sorted(key for key in attempts[0] if attempts[0][key] != attempts[1][key])
        raise AssertionError(f"pinned NLE public observation was not repeatable for seed {seed}: {changed}")
    assert method_inventory is not None
    return {
        "seed": seed,
        "configured_seeds": {"core": deterministic_nle_seeds(seed)[0], "display": deterministic_nle_seeds(seed)[1], "reseed": False},
        "two_replays_exact": True,
        "public_observation_sha256": attempts[0],
        "public_capability_inventory": method_inventory,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.cases < 3:
        raise SystemExit("authoritative entity audit requires at least three held-out source seeds")
    try:
        import nle
    except ModuleNotFoundError as error:  # pragma: no cover - command guard
        raise SystemExit("NLE 0.9.0 is required for this audit") from error
    if getattr(nle, "__version__", None) != "0.9.0":
        raise SystemExit(f"pinned runtime required NLE 0.9.0, saw {getattr(nle, '__version__', 'unknown')}")

    cases = [probe_seed(args.seed + offset) for offset in range(args.cases)]
    first_inventory = cases[0]["public_capability_inventory"]
    if any(case["public_capability_inventory"] != first_inventory for case in cases[1:]):
        raise AssertionError("public capability inventory varied across held-out source seeds")
    capability = evaluate_nle_090_public_surface(**first_inventory)
    # Validation must reject NLE presentation as a possible exporter.  This
    # explicit malformed candidate makes the no-inference decision falsifiable
    # even if the capability inventory is later extended.
    export_gate = validate_authoritative_entity_export(
        {
            "schema": "gamebench.nethack.nle_presentation.v1",
            "source_step": 0,
            "captured_before_action": True,
            "entities": [],
            "turn_queue": [],
        },
        expected_source_step=0,
    )
    if capability["status"] != "rejected" or export_gate["status"] != "rejected":
        raise AssertionError("NLE entity authority audit unexpectedly became eligible; update capture contract before using it")
    report = {
        "schema": "gamebench.nethack.authoritative_entity_scheduler_probe.v1",
        "status": "blocked_by_source_contract",
        "nle_version": nle.__version__,
        "heldout_seed_count": len(cases),
        "repeated_source_replays_exact": all(case["two_replays_exact"] for case in cases),
        "capability": capability,
        "export_gate": export_gate,
        "cases": cases,
        "blocker": "NLE 0.9.0 public/package APIs expose no stable entity ID, complete underlay, allegiance/HP/AI/movement state, turn queue, or evolving RNG chronology. Seed configuration and repeated rendered frames are not substitutes.",
        "required_future_adapter": "Emit authoritative_entity_scheduler_export.v1 before every judged action from a separately versioned source API.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": len(cases), "repeatable": report["repeated_source_replays_exact"], "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
