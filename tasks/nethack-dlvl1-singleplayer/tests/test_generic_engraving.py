"""Cross-lane coverage for authored floor engravings and prompt state."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def engraving_task(seed: int = 401, initial: bool = True) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 12):
        terrain[5][x] = "."
    level: dict[str, object] = {
        "terrain": ["".join(row) for row in terrain],
        "hero": {"x": 5, "y": 5},
        "metadata": {"hp": 20, "hp_max": 20, "hunger": 900, "ac": 100},
    }
    if initial:
        level["engravings"] = [{
            "id": "old-engraving",
            "position": {"x": 6, "y": 5},
            "text": "old mark",
            "kind": "dust",
        }]
    return {
        "task_id": f"generic-engraving-{seed}-{initial}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": level,
        "actions": [],
    }


def text_actions(text: str) -> list[str]:
    names = {
        "0": "TextCharacters.NUM_0",
        "1": "TextCharacters.NUM_1",
        "2": "TextCharacters.NUM_2",
        "3": "TextCharacters.NUM_3",
        "4": "TextCharacters.NUM_4",
        "5": "TextCharacters.NUM_5",
        "6": "TextCharacters.NUM_6",
        "7": "TextCharacters.NUM_7",
        "8": "TextCharacters.NUM_8",
        "9": "TextCharacters.NUM_9",
        "+": "TextCharacters.PLUS",
        "-": "TextCharacters.MINUS",
        " ": "TextCharacters.SPACE",
    }
    return [names[character] for character in text]


class GenericEngravingTests(unittest.TestCase):
    def test_engraving_is_cell_bound_inspectable_and_persistent(self) -> None:
        task = engraving_task()
        task["actions"] = [
            "Command.LOOK", "CompassDirection.E",
            "Command.ENGRAVE", *text_actions("1+2"), "MiscAction.MORE",
            "CompassDirection.E",
            "Command.LOOK", "CompassDirection.W",
            "CompassDirection.W",
        ]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        private = python["readout"]["private"]
        self.assertEqual(
            [
                {"id": "old-engraving", "position": {"x": 6, "y": 5}, "text": "old mark", "kind": "dust"},
                {"id": "engraving:5:5", "position": {"x": 5, "y": 5}, "text": "1+2", "kind": "dust"},
            ],
            private["engravings"],
        )
        self.assertTrue(any(
            'Message(You see an engraving reading "old mark".)' in event
            for event in python["events"]
        ))
        self.assertEqual(3, python["readout"]["public"]["blstats_named"]["time"])

    def test_engraving_replaces_only_the_current_cell_and_consumes_a_turn(self) -> None:
        task = engraving_task(seed=402, initial=False)
        task["actions"] = [
            "Command.ENGRAVE", *text_actions("1-2"), "MiscAction.MORE",
            "Command.ENGRAVE", *text_actions("3+4"), "MiscAction.MORE",
        ]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(1, len(python["readout"]["private"]["engravings"]))
        self.assertEqual("3+4", python["readout"]["private"]["engravings"][0]["text"])
        self.assertEqual(2, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("Engrave(replace)" in event for event in python["events"]))

    def test_randomized_engraving_tapes_match_across_both_lanes(self) -> None:
        for seed in range(403, 419):
            text = f"{seed % 10}+{(seed + 1) % 10}"
            task = engraving_task(seed=seed, initial=seed % 2 == 0)
            task["actions"] = [
                "Command.ENGRAVE", *text_actions(text), "MiscAction.MORE",
                "CompassDirection.E", "Command.LOOK", "CompassDirection.W",
            ]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed={seed}")
            self.assertEqual(python["events"], rust["events"], f"seed={seed}")


if __name__ == "__main__":
    unittest.main()
