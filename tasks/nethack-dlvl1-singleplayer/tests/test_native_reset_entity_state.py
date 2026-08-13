from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))
sys.path.insert(0, str(TASK_DIR / "tests"))

from scripts.native_reset_entity_state import (  # noqa: E402
    RESET_BOUNDARY,
    RNG_POLICY,
    USAGE_POLICY,
    capture_reset_state,
    record_from_reset_capture,
    validate_reset_entity_state,
)
from test_native_pre_action_evidence import NativePreActionEvidenceTests  # noqa: E402


class NativeResetEntityStateTests(unittest.TestCase):
    fixture_id = "reset-entity-unit"
    runtime = {"schema": "gamebench.nethack.capture_runtime.v1", "unit": "reset-entity"}
    level_dump = {"schema": "gamebench.nethack.level_dump.v1", "terrain": ["."]}
    reset_projection = {"blstats": [0] * 20 + [1]}

    def actions(self) -> list[dict[str, object]]:
        return [{"step": 1, "action_id": 0, "action_name": "CompassDirection.N", "nle_stepped": True}]

    def capture(self) -> dict[str, object]:
        exports = NativePreActionEvidenceTests().exports()
        return {
            "capture_boundary": deepcopy(RESET_BOUNDARY),
            "captured_at_reset_only": True,
            "state": {"entities": exports["entities"], "player": exports["player"]},
            "controls": {"entities": {"checked": 1}, "player": {"checked": 1}},
            "rng": deepcopy(RNG_POLICY),
        }

    def record(self) -> tuple[dict[str, object], list[dict[str, object]]]:
        actions = self.actions()
        capture = self.capture()
        level_dump = self.level_for(capture)
        return (
            record_from_reset_capture(
                capture,
                fixture_id=self.fixture_id,
                runtime=self.runtime,
                level_dump=level_dump,
                actions=actions,
                reset_projection=self.reset_projection,
            ),
            actions,
        )

    def level_for(self, capture: dict[str, object]) -> dict[str, object]:
        from scripts.native_reset_entity_state import portable_reset_projection

        level_dump = deepcopy(self.level_dump)
        level_dump["authoritative_reset_entities"] = portable_reset_projection(capture)
        return level_dump

    def failures(self, record: dict[str, object], actions: list[dict[str, object]]) -> list[str]:
        capture = {
            "capture_boundary": deepcopy(RESET_BOUNDARY),
            "captured_at_reset_only": True,
            "state": deepcopy(record["state"]),
        }
        return validate_reset_entity_state(
            record,
            fixture_id=self.fixture_id,
            runtime=self.runtime,
            level_dump=self.level_for(capture),
            actions=actions,
            reset_projection=self.reset_projection,
            require_native=True,
        )

    def test_reset_only_record_is_action_and_level_bound(self) -> None:
        record, actions = self.record()
        self.assertEqual([], self.failures(record, actions))
        self.assertEqual(RESET_BOUNDARY, record["capture_boundary"])
        self.assertEqual(USAGE_POLICY, record["usage_policy"])

    def test_capture_helper_discards_map_and_rng_even_if_exporter_returns_them(self) -> None:
        class Exporter:
            def export(self, observation: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
                del observation
                exports = NativePreActionEvidenceTests().exports()
                return exports, {"entities": {"checked": 1}, "player": {"checked": 1}}

        capture = capture_reset_state(Exporter(), {})
        self.assertEqual({"entities", "player"}, set(capture["state"]))
        self.assertEqual(RNG_POLICY, capture["rng"])

    def test_portable_projection_is_level_dump_data_but_not_native_receipt(self) -> None:
        from scripts.native_reset_entity_state import portable_reset_projection, validate_portable_reset_projection
        from scripts.oracle_tape import sha256_json

        projection = portable_reset_projection(self.capture())
        self.assertEqual([], validate_portable_reset_projection(projection, reset_projection=self.reset_projection))
        self.assertEqual(
            {"schema", "capture_boundary", "source_state_sha256", "source_turn", "turn_queue", "entities", "player", "player_inventory", "projection_sha256"},
            set(projection),
        )
        forged = deepcopy(projection)
        forged["player"]["future_frames"] = [{"step": 1}]
        forged["projection_sha256"] = sha256_json({key: value for key, value in forged.items() if key != "projection_sha256"})
        self.assertIn("prohibited receipt/pre-action/future", "; ".join(validate_portable_reset_projection(forged, reset_projection=self.reset_projection)))

    def test_future_sidecar_and_recomputed_digest_are_rejected(self) -> None:
        record, actions = self.record()
        forged = deepcopy(record)
        forged["native_pre_action_evidence"] = "later-sidecar-digest"
        forged["record_sha256"] = ""
        # A malicious writer can recompute the outer hash; the semantic future
        # reference must still be independently rejected.
        from scripts.oracle_tape import sha256_json

        forged["record_sha256"] = sha256_json({key: value for key, value in forged.items() if key != "record_sha256"})
        self.assertIn("prohibited future/pre-action", "; ".join(self.failures(forged, actions)))

    def test_tape_binding_and_reset_turn_cannot_be_rebound(self) -> None:
        record, actions = self.record()
        changed_actions = [{**actions[0], "action_id": 1}]
        self.assertIn("actions_sha256 mismatch", "; ".join(self.failures(record, changed_actions)))

        forged = deepcopy(record)
        forged["state"]["player"]["source_turn"] = 2
        from scripts.oracle_tape import sha256_json

        forged["reset_source_state_sha256"] = sha256_json(forged["state"])
        forged["record_sha256"] = sha256_json({key: value for key, value in forged.items() if key != "record_sha256"})
        self.assertIn("source turn does not bind", "; ".join(self.failures(forged, actions)))

    def test_missing_v1_receipt_is_explicitly_ineligible_for_new_capture(self) -> None:
        failures = validate_reset_entity_state(
            None,
            fixture_id=self.fixture_id,
            runtime=self.runtime,
            level_dump=self.level_dump,
            actions=self.actions(),
            reset_projection=self.reset_projection,
            require_native=True,
        )
        self.assertIn("required for this v2 capture", "; ".join(failures))


if __name__ == "__main__":
    unittest.main()
