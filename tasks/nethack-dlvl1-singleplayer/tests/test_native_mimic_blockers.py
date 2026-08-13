from __future__ import annotations

import unittest

from scripts.verify_native_mimic_blockers import (
    MIMIC_NAME,
    PINNED_SMALL_MIMIC_SPECIES_ID,
    SCHEMA,
    SPAWN_COUNT,
    build_action_plan,
)


class NativeMimicBlockerConstructionTests(unittest.TestCase):
    def test_declared_tape_is_fixed_and_contains_all_prompt_bytes(self) -> None:
        from nle import nethack

        plan = build_action_plan(nethack)
        self.assertEqual(SPAWN_COUNT * (len(MIMIC_NAME) + 2) + 6, len(plan))
        self.assertEqual("WizardCommand.WIZGENESIS", plan[0]["action_name"])
        self.assertEqual(ord("s"), plan[1]["ascii"])
        self.assertEqual(ord("\r"), plan[len(MIMIC_NAME) + 1]["ascii"])
        self.assertEqual("level_port_to_1_submit", plan[-1]["stage"])

    def test_contract_is_explicitly_source_only(self) -> None:
        self.assertEqual("gamebench.nethack.native_mimic_blocker_construction.v1", SCHEMA)
        self.assertEqual(63, PINNED_SMALL_MIMIC_SPECIES_ID)


if __name__ == "__main__":
    unittest.main()
