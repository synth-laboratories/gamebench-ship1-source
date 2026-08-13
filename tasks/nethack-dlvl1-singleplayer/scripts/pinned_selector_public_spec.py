#!/usr/bin/env python3
"""Fail-closed, source-pinned boundary for NetHack monster destination choice.

This is deliberately a *decision-specification audit*, not a replacement
implementation of NetHack AI.  It covers the smallest causal path relevant to
the dlvl-1 held-out traces:

``m_move`` dispatches tame monsters to ``dog_move``; both functions call
``mfndpos``; then their own subsequent code either attacks, displaces, stays,
or moves.  ``mfndpos`` is therefore a candidate filter, not a destination
selector.  A result may be derived only from a complete, public gold
pre-action snapshot.  The current public projection intentionally does not
contain the source controls below, so the only valid result is ``blocked``.

No native sidecar, LLDB callback, post-action state, seed table, coordinate
lookup, or runtime trace is accepted as an input to this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "gamebench.nethack.pinned_selector_public_preaction_spec.v1"
PINNED_NLE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
PINNED_NETHACK_VERSION = "3.6.6"
SOURCE_URL = "https://github.com/facebookresearch/nle.git"

# SHA-256 values are for the files checked out at the pinned NLE v0.9.0 tag,
# not for a locally rebuilt or instrumented NetHack binary.
PINNED_FILES = {
    "src/dogmove.c": "e50bbc79f475bd128a7e215ea0123a1074f6691b04dfa13e1d6c09f2f2756ed1",
    "src/monmove.c": "037b0ff6eecf871fe34f8b50c88b3125b681218a2cf00db485ff82e4805141af",
    "src/mon.c": "8b3385090338c3b4fceff9eb2a308044c11889fbeb1baf005f39100c9fe1de9d",
    "include/mfndpos.h": "2d24bdba6795345a1d24ea6c038a1d99e0c0dce3522d6375bf7e6c9788cf9d48",
}

# These line anchors are explanatory source pins.  The executable source-tree
# verifier below additionally checks the complete-file digest and git commit.
SOURCE_PATH = {
    "m_move_dispatch": "src/monmove.c:790-828",
    "m_move_generic_selection": "src/monmove.c:1079-1257",
    "dog_move_candidate_and_choice": "src/dogmove.c:891-1126",
    "dog_move_effect": "src/dogmove.c:1185-1265",
    "mfndpos_filter": "src/mon.c:1303-1547",
    "mfndpos_flags": "include/mfndpos.h:9-29",
}

# Every item is read by the pinned path, is absent from the frozen gold public
# projection, and can change candidate membership or the later selected
# outcome.  This is the minimum sufficient *category* list; adding a rendered
# glyph or a seed does not substitute for any category.
MISSING_PUBLIC_CONTROLS = (
    {
        "id": "selector_dispatch_and_actor_state",
        "source": ("src/monmove.c:790-828", "src/dogmove.c:862-967"),
        "needed_for": "whether m_move reaches dog_move and every early return",
        "missing": (
            "stable actor identity", "tame/minion status", "trap/eating state",
            "species capabilities", "visibility/confusion/leash state",
        ),
    },
    {
        "id": "complete_native_level_and_entities",
        "source": ("src/mon.c:1324-1547",),
        "needed_for": "mfndpos candidate membership and per-candidate flags",
        "missing": (
            "raw terrain type and door mask", "complete object stacks and cursed bits",
            "trap type plus per-actor trap knowledge", "all monster occupancy and attributes",
            "regions, room/sanctuary state, and worm segments",
        ),
    },
    {
        "id": "per_actor_path_memory_and_pet_extension",
        "source": ("src/dogmove.c:913-925", "src/dogmove.c:1076-1123", "src/monmove.c:811-939"),
        "needed_for": "goal, backtracking, food/cursed-object preference, and approach direction",
        "missing": (
            "mux/muy apparent target", "mtrack history", "strategy", "edog hunger/goal/whistle state",
            "actor inventory and weapon state", "player hidden/displacement state",
        ),
    },
    {
        "id": "rng_state_and_prior_draw_chronology",
        "source": ("src/dogmove.c:1003-1123", "src/monmove.c:1142-1158"),
        "needed_for": "source random branch outcomes and tie selection",
        "missing": ("evolving native RNG lanes", "all earlier draws on the same action path", "draw ownership"),
    },
    {
        "id": "effect_and_scheduler_boundary",
        "source": ("src/dogmove.c:1003-1050", "src/dogmove.c:1185-1265", "src/monmove.c:1165-1257"),
        "needed_for": "whether an apparent destination is an attack, displacement, blocked turn, or physical move",
        "missing": (
            "combat outcome state", "displacement target state", "m_in_out_region result",
            "native monster turn ordering and repeated-move chronology",
        ),
    },
)

COUNTEREXAMPLES = (
    {
        "id": "candidate_filter_is_not_selector",
        "source": ("src/mon.c:1538-1547", "src/dogmove.c:990-1126", "src/monmove.c:1133-1158"),
        "claim_refuted": "mfndpos candidate array alone determines destination",
        "reason": "Both callers score/filter the returned array after mfndpos; both contain RNG-dependent branches.",
    },
    {
        "id": "return_one_is_not_displacement",
        "source": ("src/dogmove.c:1185-1265", "src/monmove.c:1258-1265"),
        "claim_refuted": "a successful dog_move/m_move return necessarily moved the actor",
        "reason": "dog_move returns 1 after the newdogpos label even when nix/niy remain omx/omy.",
    },
    {
        "id": "rendered_square_is_not_native_candidate_state",
        "source": ("src/mon.c:1417-1536", "src/dogmove.c:1076-1099"),
        "claim_refuted": "public chars/glyphs/specials are sufficient to recreate mfndpos and pet filtering",
        "reason": "The path reads hidden occupancy, objects/cursed bits, traps and actor memory not carried by a rendered cell.",
    },
)

PUBLIC_GOLD_SCHEMA = "gamebench.nethack.dlvl1.public.v1"
PUBLIC_GOLD_FIELDS = frozenset({
    "schema", "chars", "colors", "glyphs", "specials", "blstats", "blstats_fields",
    "blstats_named", "message", "message_raw", "inventory", "input_mode", "done",
    "terminated", "truncated", "terminal_reason", "terminal_tty",
})


def source_manifest() -> dict[str, Any]:
    return {
        "nle_commit": PINNED_NLE_COMMIT,
        "nethack_version": PINNED_NETHACK_VERSION,
        "source_url": SOURCE_URL,
        "files_sha256": dict(PINNED_FILES),
        "source_path": dict(SOURCE_PATH),
    }


def verify_pinned_source_tree(root: Path) -> dict[str, Any]:
    """Verify an independently obtained checkout before citing its source.

    This does not clone or write a source tree.  Callers supply one; every
    mismatch is reported rather than silently falling back to similar source.
    """

    failures: list[str] = []
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
        failures.append("unreadable_git_checkout")
    if commit != PINNED_NLE_COMMIT:
        failures.append("nle_commit_mismatch")
    actual: dict[str, str | None] = {}
    for relative, expected in PINNED_FILES.items():
        path = root / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        actual[relative] = digest
        if digest != expected:
            failures.append(f"source_file_mismatch:{relative}")
    return {
        "schema": SCHEMA,
        "source_manifest": source_manifest(),
        "source_tree_verified": not failures,
        "actual_commit": commit,
        "actual_files_sha256": actual,
        "failures": failures,
    }


def assess_public_pre_action(public_state: dict[str, Any]) -> dict[str, Any]:
    """Assess whether a public gold frame can determine an NLE selector result.

    The answer is intentionally not a prediction.  Current gold public
    snapshots are valid presentation objects, but they cannot expose hidden
    source state without ceasing to be the public gold contract.
    """

    malformed: list[str] = []
    if not isinstance(public_state, dict):
        malformed.append("public_state_not_object")
        public_state = {}
    if public_state.get("schema") != PUBLIC_GOLD_SCHEMA:
        malformed.append("unexpected_public_gold_schema")
    unknown = sorted(set(public_state) - PUBLIC_GOLD_FIELDS)
    if unknown:
        # Reject sidecar injection explicitly.  Native selector traces cannot
        # be smuggled in as an extension of a public gold snapshot.
        malformed.append("nonpublic_or_sidecar_fields:" + ",".join(unknown))
    missing_presentation = sorted({"chars", "colors", "glyphs", "specials", "blstats", "inventory"} - set(public_state))
    if missing_presentation:
        malformed.append("incomplete_public_projection:" + ",".join(missing_presentation))
    missing = [dict(item) for item in MISSING_PUBLIC_CONTROLS]
    return {
        "schema": SCHEMA,
        "source_manifest": source_manifest(),
        "input_kind": "public_gold_pre_action_only",
        "public_snapshot_schema_valid": not malformed,
        "malformed_input_reasons": malformed,
        "decision": "blocked",
        "destination": None,
        "selector": None,
        "gold_implementation_eligible": False,
        "missing_controls": missing,
        "counterexamples": [dict(item) for item in COUNTEREXAMPLES],
        "blocker": (
            "The pinned selector cannot be evaluated from the public gold pre-action contract. "
            "Do not use native sidecars, post-action results, seeds, coordinates, or LLDB traces as substitutes."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-state", type=Path, help="public gold pre-action JSON object to assess")
    parser.add_argument("--verify-source-root", type=Path, help="read-only checkout expected to be NLE v0.9.0")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    if (args.public_state is None) == (args.verify_source_root is None):
        raise SystemExit("provide exactly one of --public-state or --verify-source-root")
    result = (
        assess_public_pre_action(json.loads(args.public_state.read_text()))
        if args.public_state is not None
        else verify_pinned_source_tree(args.verify_source_root)
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
