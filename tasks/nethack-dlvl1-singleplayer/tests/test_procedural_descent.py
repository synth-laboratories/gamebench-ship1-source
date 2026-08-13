"""End-to-end descent certification for fixture-free procedural levels."""

from __future__ import annotations

from collections import deque
import sys
import unittest
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust
from shared.task_resolve import resolve_task


CARDINAL_DIRECTIONS = (
    (0, -1, "CompassDirection.N"),
    (-1, 0, "CompassDirection.W"),
    (1, 0, "CompassDirection.E"),
    (0, 1, "CompassDirection.S"),
)


def generated_task(seed: int, actions: list[int | str] | None = None) -> dict[str, Any]:
    return {
        "task_id": f"procedural-descent-{seed}",
        "seed": seed,
        "rules": {
            "max_steps": 0,
            "autopickup": False,
            "auto_more": "raw_explicit",
            "vision_radius": 6,
        },
        "actions": list(actions or []),
    }


def down_stair(state: dict[str, Any]) -> tuple[int, int]:
    stairs = [
        (x, y)
        for y, row in enumerate(state["terrain"])
        for x, tile in enumerate(row)
        if tile == ">"
    ]
    if len(stairs) != 1:
        raise AssertionError(f"procedural level must have exactly one down stair: {stairs}")
    return stairs[0]


def next_route_step(
    state: dict[str, Any],
    goal: tuple[int, int],
    *,
    block_actors: bool,
) -> tuple[tuple[int, int], str] | None:
    """Return one deterministic cardinal step, avoiding known trap cells."""

    hero = state["hero"]
    start = (int(hero["x"]), int(hero["y"]))
    terrain = state["terrain"]
    traps = {
        (int(trap["position"]["x"]), int(trap["position"]["y"]))
        for trap in state["traps"]
    }
    actors = (
        {
            (int(monster["position"]["x"]), int(monster["position"]["y"]))
            for monster in state["monsters"]
        }
        if block_actors
        else set()
    )
    actors.discard(goal)

    frontier = deque([start])
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    actions: dict[tuple[int, int], str] = {}
    while frontier:
        current = frontier.popleft()
        if current == goal:
            break
        for dx, dy, action in CARDINAL_DIRECTIONS:
            candidate = (current[0] + dx, current[1] + dy)
            x, y = candidate
            if (
                candidate in parents
                or candidate in traps
                or candidate in actors
                or not (0 <= y < len(terrain) and 0 <= x < len(terrain[y]))
                or terrain[y][x] not in {".", "#", "+", "<", ">"}
            ):
                continue
            parents[candidate] = current
            actions[candidate] = action
            frontier.append(candidate)

    if goal not in parents:
        return None
    cursor = goal
    while parents[cursor] != start:
        parent = parents[cursor]
        if parent is None:
            return None
        cursor = parent
    return cursor, actions[cursor]


def build_descent_tape(seed: int) -> list[int | str]:
    """Drive one lane online, recording a lane-neutral causal action tape."""

    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(generated_task(seed)))
    tape: list[int | str] = []

    for _ in range(300):
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        state = engine.state
        hero = state["hero"]
        hero_position = (int(hero["x"]), int(hero["y"]))
        stair = down_stair(state)
        if hero_position == stair:
            engine.step("MiscDirection.DOWN")
            tape.append("MiscDirection.DOWN")
            break

        route_step = next_route_step(state, stair, block_actors=True)
        actor_blocked_route = route_step is None
        if route_step is None:
            # Live actors may temporarily seal a one-cell door. Allow their
            # cell in the plan; attempting the move spends a turn, after which
            # actor scheduling changes occupancy and the policy replans.
            route_step = next_route_step(state, stair, block_actors=False)
        if route_step is None:
            engine.step("MiscDirection.WAIT")
            tape.append("MiscDirection.WAIT")
            continue

        destination, direction = route_step
        blocking_hostile = next(
            (
                monster
                for monster in state["monsters"]
                if not monster.get("pet")
                and not monster.get("peaceful")
                and (
                    int(monster["position"]["x"]),
                    int(monster["position"]["y"]),
                )
                == destination
            ),
            None,
        )
        if actor_blocked_route and blocking_hostile is not None:
            # Combat is a last-resort path operation. Ordinarily the policy
            # routes around live actors, avoiding unnecessary corpse/economy
            # side effects while still handling a hostile that seals the only
            # legal route.
            for action in ("Command.FIGHT", direction):
                engine.step(action)
                tape.append(action)
            continue

        closed_door = any(
            not door.get("open", False)
            and (
                int(door["position"]["x"]),
                int(door["position"]["y"]),
            )
            == destination
            for door in state["door_properties"]
        )
        actions = ("Command.OPEN", direction) if closed_door else (direction,)
        for action in actions:
            engine.step(action)
            tape.append(action)

    reason = str(engine.state.get("terminal_reason", ""))
    if reason != "descended":
        raise AssertionError(
            f"procedural descent policy failed for seed {seed}: "
            f"reason={reason!r}, hp={engine.state.get('hp')}, actions={len(tape)}"
        )
    return tape


class ProceduralDescentTests(unittest.TestCase):
    def test_online_policy_descends_with_complete_cross_lane_parity(self) -> None:
        for seed in (-39, -30, -26):
            with self.subTest(seed=seed):
                tape = build_descent_tape(seed)
                self.assertIn("Command.OPEN", tape)
                self.assertEqual(1, tape.count("MiscDirection.DOWN"))

                task = generated_task(seed, tape)
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

                readout = python["readout"]
                self.assertTrue(readout["terminated"])
                self.assertFalse(readout["truncated"])
                self.assertEqual("descended", readout["public"]["terminal_reason"])
                self.assertEqual("descended", readout["private"]["terminal_reason"])
                self.assertEqual(1.0, readout["reward"])
                self.assertEqual(1, python["events"].count("StairsDescend(dlvl1)"))
                self.assertEqual(1, python["events"].count("Terminal(descended)"))

    def test_down_away_from_stairs_is_nonterminal_and_parity_safe(self) -> None:
        task = generated_task(0, ["MiscDirection.DOWN"])
        resolved = resolve_task(task)
        hero = resolved["level_dump"]["hero"]
        stair = next(
            (x, y)
            for y, row in enumerate(resolved["level_dump"]["terrain"])
            for x, tile in enumerate(row)
            if tile == ">"
        )
        self.assertNotEqual((hero["x"], hero["y"]), stair)

        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertFalse(python["readout"]["terminated"])
        self.assertEqual("", python["readout"]["public"]["terminal_reason"])
        self.assertEqual("You can't go down here.", python["readout"]["public"]["message"])
        self.assertNotIn("StairsDescend(dlvl1)", python["events"])


if __name__ == "__main__":
    unittest.main()
