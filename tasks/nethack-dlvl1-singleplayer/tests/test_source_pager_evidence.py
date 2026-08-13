from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.source_pager import (  # noqa: E402
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
    SOURCE_PAGER_SCHEMA,
)
from scripts.source_pager_evidence import (  # noqa: E402
    SIDECAR_SCHEMA,
    validate_source_pager_evidence,
)


FIXTURE_ID = "fuzz-case-0006-seed-20260731"
PAGE_DIGEST = "749e8b0a340371d5f423ff1c53a870c6a54ade58a28864e4934a66e49774e470"
CONTINUATION_DIGEST = "e215f11678e326c7995d70bd40f1a5f283e3ef9aaa1dfda9023f4207ecc4dbd8"


def _contract() -> dict[str, object]:
    page = "The kitten misses the grid bug.  The grid bug bites!  You get zapped!"
    return {
        "schema": SOURCE_PAGER_SCHEMA,
        "fixture_id": FIXTURE_ID,
        "source_commit": PINNED_SOURCE_COMMIT,
        "binary_sha256": PINNED_BINARY_SHA256,
        "trigger": {"step": 15, "action": "CompassDirection.SE"},
        "before": {
            "source_turn": 14,
            "nle_time": 14,
            "message": "The kitten misses the grid bug.",
            "queue": [27, 10],
        },
        "page": {
            "message": page,
            "tty_message": page + "--More--",
            "input_mode": "more",
            "source_state_sha256": PAGE_DIGEST,
        },
        "continuation": {
            "action": "MiscAction.MORE",
            "source_turn": 15,
            "nle_time": 15,
            "message": "The kitten bites the grid bug.  The grid bug is killed!",
            "queue": [27],
            "input_mode": "normal",
            "consumes_player_turn": False,
            "source_state_sha256": CONTINUATION_DIGEST,
        },
    }


def _native_record(step: int, action_name: str, source_digest: str) -> dict[str, object]:
    # The full shape is validated by native_pre_action_evidence.  These tests
    # exercise this guard's cross-sidecar binding with the smallest record
    # carrying the fields it is authorized to inspect.
    return {
        "schema": "gamebench.nethack.native_pre_action_evidence_record.v1",
        "fixture_id": FIXTURE_ID,
        "step": step,
        "captured_before_action": True,
        "action": {"step": step, "action_name": action_name},
        "source_state_sha256": source_digest,
        "record_sha256": f"{step:064x}",
        "native_identity": {"binary_sha256": PINNED_BINARY_SHA256},
        "exports": {},
    }


def _payload() -> tuple[dict[str, object], list[dict[str, object]]]:
    pager_records = [
        {
            "fixture_id": FIXTURE_ID,
            "step": 15,
            "action": {"step": 15, "action_name": "CompassDirection.SE"},
            "source_state_sha256": "0" * 64,
            "native_record_sha256": f"{15:064x}",
        },
        {
            "fixture_id": FIXTURE_ID,
            "step": 16,
            "action": {"step": 16, "action_name": "MiscAction.MORE"},
            "source_state_sha256": PAGE_DIGEST,
            "native_record_sha256": f"{16:064x}",
        },
        {
            "fixture_id": FIXTURE_ID,
            "step": 17,
            "action": {"step": 17, "action_name": "CompassDirection.E"},
            "source_state_sha256": CONTINUATION_DIGEST,
            "native_record_sha256": f"{17:064x}",
        },
    ]
    native_records = [
        _native_record(15, "CompassDirection.SE", "0" * 64),
        _native_record(16, "MiscAction.MORE", PAGE_DIGEST),
        _native_record(17, "CompassDirection.E", CONTINUATION_DIGEST),
    ]
    return {
        "schema": SIDECAR_SCHEMA,
        "fixture_id": FIXTURE_ID,
        "contract": _contract(),
        "records": pager_records,
    }, native_records


class SourcePagerEvidenceTests(unittest.TestCase):
    def test_pinned_sidecar_passes_and_is_in_denominator(self) -> None:
        payload, native_records = _payload()
        report = validate_source_pager_evidence(payload, fixture_id=FIXTURE_ID, native_records=native_records)
        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["error_count"])
        self.assertTrue(report["conformance_denominator_included"])
        self.assertEqual([15, 16, 17], report["required_steps"])

    def test_page_digest_tampering_fails_contract_validation(self) -> None:
        payload, native_records = _payload()
        payload["contract"]["page"]["source_state_sha256"] = "f" * 64  # type: ignore[index]
        report = validate_source_pager_evidence(payload, fixture_id=FIXTURE_ID, native_records=native_records)
        self.assertEqual("failed", report["status"])
        self.assertTrue(any("contract invalid" in error and "digest mismatch" in error for error in report["errors"]))

    def test_page_record_digest_tampering_fails_native_binding(self) -> None:
        payload, native_records = _payload()
        payload["records"][1]["source_state_sha256"] = "f" * 64  # type: ignore[index]
        report = validate_source_pager_evidence(payload, fixture_id=FIXTURE_ID, native_records=native_records)
        self.assertEqual("failed", report["status"])
        self.assertTrue(any("page digest mismatch" in error for error in report["errors"]))
        self.assertTrue(any("does not match native evidence" in error for error in report["errors"]))

    def test_fixture_step_and_action_tampering_fails_hard(self) -> None:
        payload, native_records = _payload()
        payload["records"][0]["fixture_id"] = "other-fixture"  # type: ignore[index]
        payload["records"][1]["step"] = 19  # type: ignore[index]
        payload["records"][2]["action"]["action_name"] = "CompassDirection.W"  # type: ignore[index]
        report = validate_source_pager_evidence(payload, fixture_id=FIXTURE_ID, native_records=native_records)
        self.assertEqual("failed", report["status"])
        self.assertTrue(any("fixture identity mismatch" in error for error in report["errors"]))
        self.assertTrue(any("missing required page record" in error for error in report["errors"]))
        self.assertTrue(any("native/pager action mismatch" in error for error in report["errors"]))

    def test_duplicate_or_missing_boundary_is_rejected(self) -> None:
        payload, native_records = _payload()
        payload["records"].append(copy.deepcopy(payload["records"][1]))  # type: ignore[index]
        report = validate_source_pager_evidence(payload, fixture_id=FIXTURE_ID, native_records=native_records)
        self.assertTrue(any("duplicate step 16" in error for error in report["errors"]))
        payload, native_records = _payload()
        payload["records"] = payload["records"][:2]  # type: ignore[index]
        report = validate_source_pager_evidence(payload, fixture_id=FIXTURE_ID, native_records=native_records)
        self.assertTrue(any("missing required continuation" in error for error in report["errors"]))

    def test_legacy_absence_is_not_a_failed_conformance_comparison(self) -> None:
        report = validate_source_pager_evidence(None, fixture_id="historical-fixture", native_records=None)
        self.assertEqual("not_exercised", report["status"])
        self.assertEqual(0, report["error_count"])
        self.assertFalse(report["conformance_denominator_included"])


if __name__ == "__main__":
    unittest.main()
