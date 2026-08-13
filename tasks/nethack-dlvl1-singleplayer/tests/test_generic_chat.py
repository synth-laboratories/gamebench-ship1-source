"""Parity coverage for authored directional monster chat."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def chat_task(seed: int = 131, *, peaceful: bool = True, chat: object = None) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 12):
        terrain[4][x] = "."
    monster: dict[str, object] = {
        "id": "chatty-actor",
        "name": "chatty actor",
        "char": "c",
        "position": {"x": 6, "y": 4},
        "hp": 5,
        "peaceful": peaceful,
        "movement": "stationary",
    }
    if chat is not None:
        monster["chat"] = chat
    return {
        "task_id": f"generic-chat-{seed}-{peaceful}-{chat}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "monsters": [monster],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericChatTests(unittest.TestCase):
    def test_directional_chat_prompt_and_authored_response_match(self) -> None:
        task = chat_task(chat=["The {name} purrs.", "The {name} nudges your hand."])
        task["actions"] = ["Command.CHAT", "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertTrue(any("ModeEnter(direction)" in event for event in python["events"]))
        self.assertIn("chatty actor", python["readout"]["public"]["message"])
        self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("Chat(chatty actor)" in event for event in python["events"]))

    def test_chat_fallbacks_and_empty_direction_are_zero_turn_or_actor_turn(self) -> None:
        for peaceful, expected in ((True, "You chat with the chatty actor."), (False, "The chatty actor ignores you.")):
            task = chat_task(seed=132, peaceful=peaceful)
            task["actions"] = ["Command.CHAT", "CompassDirection.E"]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"])
            self.assertTrue(any(f"Message({expected})" in event for event in python["events"]))
            self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])

        no_actor = chat_task(seed=133)
        no_actor["level_dump"]["monsters"][0]["position"] = {"x": 8, "y": 4}
        no_actor["actions"] = ["Command.CHAT", "CompassDirection.E"]
        python = run_python(no_actor)
        rust = run_rust(no_actor)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual("You see no one there to chat with.", python["readout"]["public"]["message"])
        self.assertEqual(0, python["readout"]["public"]["blstats_named"]["time"])

    def test_randomized_chat_tapes_match_across_both_lanes(self) -> None:
        for seed in range(140, 156):
            task = chat_task(seed=seed, chat=["{name} says hello.", "{name} asks for food.", "{name} yawns."])
            task["actions"] = [
                "Command.CHAT", "CompassDirection.E",
                "MiscDirection.WAIT",
                "Command.CHAT", "CompassDirection.E",
            ]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed {seed}")
            self.assertEqual(python["events"], rust["events"], f"events seed {seed}")


if __name__ == "__main__":
    unittest.main()
