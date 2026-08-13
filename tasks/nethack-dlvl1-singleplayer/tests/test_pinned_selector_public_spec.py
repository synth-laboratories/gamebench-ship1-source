from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from scripts.pinned_selector_public_spec import (
    MISSING_PUBLIC_CONTROLS,
    PINNED_NLE_COMMIT,
    PUBLIC_GOLD_SCHEMA,
    assess_public_pre_action,
    verify_pinned_source_tree,
)


def public_state() -> dict[str, object]:
    return {
        "schema": PUBLIC_GOLD_SCHEMA,
        "chars": ["."],
        "colors": [[7]],
        "glyphs": [[2378]],
        "specials": [[0]],
        "blstats": [0] * 27,
        "blstats_fields": [],
        "blstats_named": {},
        "message": "",
        "message_raw": [],
        "inventory": {},
        "input_mode": {"kind": "normal"},
        "done": False,
        "terminated": False,
        "truncated": False,
        "terminal_reason": "",
        "terminal_tty": None,
    }


class PinnedSelectorPublicSpecTests(unittest.TestCase):
    def test_valid_public_gold_frame_is_explicitly_not_a_selector_input(self) -> None:
        result = assess_public_pre_action(public_state())
        self.assertIs(result["public_snapshot_schema_valid"], True)
        self.assertEqual("blocked", result["decision"])
        self.assertIsNone(result["destination"])
        self.assertIs(result["gold_implementation_eligible"], False)
        self.assertEqual(
            [item["id"] for item in MISSING_PUBLIC_CONTROLS],
            [item["id"] for item in result["missing_controls"]],
        )

    def test_native_or_trace_extension_is_rejected_not_treated_as_public_state(self) -> None:
        forged = deepcopy(public_state())
        forged["native_pre_action_evidence"] = {"rng": "not public"}
        result = assess_public_pre_action(forged)
        self.assertIs(result["public_snapshot_schema_valid"], False)
        self.assertTrue(any(reason.startswith("nonpublic_or_sidecar_fields:") for reason in result["malformed_input_reasons"]))
        self.assertEqual("blocked", result["decision"])

    def test_source_verifier_rejects_a_non_pinned_tree(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            result = verify_pinned_source_tree(Path(directory))
        self.assertIs(result["source_tree_verified"], False)
        self.assertIn("nle_commit_mismatch", result["failures"])
        self.assertEqual(PINNED_NLE_COMMIT, result["source_manifest"]["nle_commit"])
