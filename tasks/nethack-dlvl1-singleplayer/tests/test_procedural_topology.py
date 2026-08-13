"""Structural and cross-lane contract tests for procedural dlvl-1 topology."""

from __future__ import annotations

from collections import deque
import json
import sys
import unittest
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust
from shared.task_resolve import resolve_task


SLOTS = (
    (2, 24, 1, 9),
    (28, 50, 1, 9),
    (54, 76, 1, 9),
    (2, 24, 11, 19),
    (28, 50, 11, 19),
    (54, 76, 11, 19),
)
PASSABLE = frozenset(".#+<>")


def species_name(selector: int) -> str:
    if selector < 6:
        return "sewer rat"
    if selector < 11:
        return "newt"
    return "fox"


def generated_task(seed: int) -> dict[str, Any]:
    return {
        "task_id": f"procedural-topology-{seed}",
        "seed": seed,
        "rules": {
            "max_steps": 0,
            "autopickup": False,
            "auto_more": "raw_explicit",
            "vision_radius": 6,
        },
        "actions": [],
    }


def position(entity: dict[str, Any]) -> tuple[int, int]:
    value = entity["position"]
    return int(value["x"]), int(value["y"])


def _bounds(value: dict[str, Any], kind: str) -> tuple[int, int, int, int]:
    """Read the documented bounds while tolerating the two natural key spellings."""

    bounds = value.get(kind, value.get(f"{kind}_bounds"))
    if not isinstance(bounds, dict):
        raise AssertionError(f"generated room lacks {kind} bounds: {value!r}")
    aliases = (
        ("left", "top", "right", "bottom"),
        ("x1", "y1", "x2", "y2"),
        ("min_x", "min_y", "max_x", "max_y"),
    )
    for keys in aliases:
        if all(key in bounds for key in keys):
            return tuple(int(bounds[key]) for key in keys)  # type: ignore[return-value]
    raise AssertionError(f"unsupported {kind} bounds schema: {bounds!r}")


def room_id(room: dict[str, Any]) -> int:
    value = room.get("id")
    if isinstance(value, int):
        return value
    text = str(value)
    suffix = text.rsplit("-", 1)[-1]
    if suffix.isdigit():
        return int(suffix)
    raise AssertionError(f"generated room has no numeric id: {value!r}")


def _contract(seed: int) -> dict[str, Any]:
    """Independent oracle for the fixed-cost 56-draw generation contract."""

    state = int(seed) & 0xFFFFFFFF
    draws = 0

    def draw(upper: int) -> int:
        nonlocal state, draws
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        draws += 1
        return state % max(1, upper)

    rooms: list[dict[str, tuple[int, int, int, int] | int]] = []
    for room_index, (slot_left, slot_right, slot_top, slot_bottom) in enumerate(SLOTS):
        width = 4 + draw(7)
        height = 3 + draw(3)
        slot_width = slot_right - slot_left + 1
        slot_height = slot_bottom - slot_top + 1
        left = slot_left + draw(slot_width - width - 1)
        top = slot_top + draw(slot_height - height - 1)
        rooms.append(
            {
                "id": room_index,
                "outer": (left, top, left + width + 1, top + height + 1),
                "interior": (left + 1, top + 1, left + width, top + height),
            }
        )

    terrain = [[" "] * 79 for _ in range(21)]
    for room in rooms:
        left, top, right, bottom = room["outer"]  # type: ignore[misc]
        for x in range(left, right + 1):
            terrain[top][x] = "-"
            terrain[bottom][x] = "-"
        for y in range(top + 1, bottom):
            terrain[y][left] = "|"
            terrain[y][right] = "|"
            for x in range(left + 1, right):
                terrain[y][x] = "."

    primary_column = draw(3)
    extra_enabled = bool(draw(2))
    extra_column = (primary_column + 1 + draw(2)) % 3
    candidates = [
        (0, 1, True, True),
        (1, 2, True, True),
        (3, 4, True, True),
        (4, 5, True, True),
        (primary_column, primary_column + 3, False, True),
        (extra_column, extra_column + 3, False, extra_enabled),
    ]
    doors: list[tuple[int, int]] = []

    def carve(x: int, y: int) -> None:
        if terrain[y][x] in {" ", "#"}:
            terrain[y][x] = "#"

    for first_index, second_index, horizontal, active in candidates:
        first = rooms[first_index]
        second = rooms[second_index]
        first_interior = first["interior"]  # type: ignore[assignment]
        second_interior = second["interior"]  # type: ignore[assignment]
        first_offset = draw(
            first_interior[3] - first_interior[1] + 1
            if horizontal
            else first_interior[2] - first_interior[0] + 1
        )
        second_offset = draw(
            second_interior[3] - second_interior[1] + 1
            if horizontal
            else second_interior[2] - second_interior[0] + 1
        )
        if not active:
            continue
        first_outer = first["outer"]  # type: ignore[assignment]
        second_outer = second["outer"]  # type: ignore[assignment]
        if horizontal:
            first_door = (first_outer[2], first_interior[1] + first_offset)
            second_door = (second_outer[0], second_interior[1] + second_offset)
            midpoint = (first_door[0] + second_door[0]) // 2
            for x in range(first_door[0] + 1, midpoint + 1):
                carve(x, first_door[1])
            low_y, high_y = sorted((first_door[1], second_door[1]))
            for y in range(low_y, high_y + 1):
                carve(midpoint, y)
            for x in range(midpoint, second_door[0]):
                carve(x, second_door[1])
        else:
            first_door = (first_interior[0] + first_offset, first_outer[3])
            second_door = (second_interior[0] + second_offset, second_outer[1])
            midpoint = (first_door[1] + second_door[1]) // 2
            for y in range(first_door[1] + 1, midpoint + 1):
                carve(first_door[0], y)
            low_x, high_x = sorted((first_door[0], second_door[0]))
            for x in range(low_x, high_x + 1):
                carve(x, midpoint)
            for y in range(midpoint, second_door[1]):
                carve(second_door[0], y)
        for x, y in (first_door, second_door):
            terrain[y][x] = "+"
            doors.append((x, y))

    reserved: set[tuple[int, int]] = set()

    def pick(room_index: int) -> tuple[int, int]:
        left, top, right, bottom = rooms[room_index]["interior"]  # type: ignore[misc]
        cells = [(x, y) for y in range(top, bottom + 1) for x in range(left, right + 1)]
        start = draw(len(cells))
        for offset in range(len(cells)):
            candidate = cells[(start + offset) % len(cells)]
            if candidate not in reserved:
                reserved.add(candidate)
                return candidate
        raise AssertionError("room-relative placement exhausted a room")

    names_and_rooms = (
        ("hero", 0),
        ("down", 5),
        ("generated-hostile-1", 1),
        ("generated-hostile-2", 2),
        ("generated-gold", 3),
        ("generated-dog", 3),
        ("generated-arrow-trap", 4),
        ("generated-hostile-3", 4),
        ("generated-potion", 5),
    )
    placements = {name: pick(room_index) for name, room_index in names_and_rooms}
    hero_x, hero_y = placements["hero"]
    down_x, down_y = placements["down"]
    terrain[hero_y][hero_x] = "<"
    terrain[down_y][down_x] = ">"

    properties = {
        "gold_quantity": 10 + draw(40),
        "pet_base_speed": 12 if draw(2) == 0 else 18,
        "pet_nutrition": 300 + draw(301),
        "light_radius": 2 + draw(3),
        "trap_effect": "poison" if draw(2) else "",
        "species_selectors": tuple(draw(16) for _ in range(3)),
    }
    if draws != 56:
        raise AssertionError(f"contract oracle consumed {draws} draws instead of 56")
    return {
        "rooms": rooms,
        "terrain": ["".join(row) for row in terrain],
        "doors": doors,
        "placements": placements,
        "properties": properties,
        "lcg_state": state,
    }


def _inside(point: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


class ProceduralTopologyTests(unittest.TestCase):
    def test_exact_fixed_cost_topology_and_placements(self) -> None:
        for seed in (-19, -1, 0, 1, 23, 20260806, 0x7FFFFFFF):
            with self.subTest(seed=seed):
                level = resolve_task(generated_task(seed))["level_dump"]
                expected = _contract(seed)
                rooms = sorted(level["metadata"]["generated_rooms"], key=room_id)
                self.assertEqual(6, len(rooms))
                self.assertEqual(
                    [room["outer"] for room in expected["rooms"]],
                    [_bounds(room, "outer") for room in rooms],
                )
                self.assertEqual(
                    [room["interior"] for room in expected["rooms"]],
                    [_bounds(room, "interior") for room in rooms],
                )
                self.assertEqual(expected["terrain"], level["terrain"])

                door_positions = [position(door) for door in level["metadata"]["doors"]]
                self.assertEqual(sorted(expected["doors"]), sorted(door_positions))
                self.assertIn(len(door_positions), {10, 12})
                self.assertEqual(len(door_positions), len(set(door_positions)))
                self.assertTrue(all(not door["open"] for door in level["metadata"]["doors"]))

                monsters = {monster["id"]: monster for monster in level["monsters"]}
                objects = {item["id"]: item for item in level["objects"]}
                trap = level["traps"][0]
                actual_positions = {
                    "hero": (level["hero"]["x"], level["hero"]["y"]),
                    "down": next(
                        (x, y)
                        for y, row in enumerate(level["terrain"])
                        for x, tile in enumerate(row)
                        if tile == ">"
                    ),
                    **{key: position(monsters[key]) for key in ("generated-hostile-1", "generated-hostile-2", "generated-dog", "generated-hostile-3")},
                    **{key: position(objects[key]) for key in ("generated-gold", "generated-potion")},
                    "generated-arrow-trap": position(trap),
                }
                self.assertEqual(expected["placements"], actual_positions)
                self.assertEqual(position(monsters["generated-dog"]), position(objects["generated-pet-ration"]))
                self.assertEqual("generated-dog", level["light_sources"][0]["follow"])

                properties = expected["properties"]
                self.assertEqual(properties["gold_quantity"], objects["generated-gold"]["quantity"])
                self.assertEqual(properties["pet_base_speed"], monsters["generated-dog"]["base_speed"])
                self.assertEqual(properties["pet_nutrition"], objects["generated-pet-ration"]["nutrition"])
                self.assertEqual(properties["light_radius"], level["light_sources"][0]["radius"])
                self.assertEqual(properties["trap_effect"], trap["effect"])
                hostiles = [monsters[f"generated-hostile-{index}"] for index in range(1, 4)]
                self.assertEqual(
                    [species_name(selector) for selector in properties["species_selectors"]],
                    [monster["name"] for monster in hostiles],
                )
                self.assertTrue(all(monster["movement_points"] == 0 for monster in hostiles))

    def test_room_geometry_connectivity_and_entity_invariants(self) -> None:
        for seed in range(-12, 13):
            with self.subTest(seed=seed):
                level = resolve_task(generated_task(seed))["level_dump"]
                terrain = level["terrain"]
                rooms = sorted(level["metadata"]["generated_rooms"], key=room_id)
                outer_bounds = [_bounds(room, "outer") for room in rooms]
                interior_bounds = [_bounds(room, "interior") for room in rooms]

                for index, (outer, interior, slot) in enumerate(zip(outer_bounds, interior_bounds, SLOTS)):
                    left, top, right, bottom = outer
                    inner_left, inner_top, inner_right, inner_bottom = interior
                    self.assertEqual((left + 1, top + 1, right - 1, bottom - 1), interior)
                    self.assertGreaterEqual(inner_right - inner_left + 1, 4)
                    self.assertGreaterEqual(inner_bottom - inner_top + 1, 3)
                    slot_left, slot_right, slot_top, slot_bottom = slot
                    canonical_slot = (slot_left, slot_top, slot_right, slot_bottom)
                    self.assertTrue(_inside((left, top), canonical_slot), index)
                    self.assertTrue(_inside((right, bottom), canonical_slot), index)
                    for other in outer_bounds[index + 1 :]:
                        self.assertFalse(
                            not (right < other[0] or other[2] < left or bottom < other[1] or other[3] < top)
                        )
                    for x in range(left, right + 1):
                        self.assertIn(terrain[top][x], {"-", "+"})
                        self.assertIn(terrain[bottom][x], {"-", "+"})
                    for y in range(top + 1, bottom):
                        self.assertIn(terrain[y][left], {"|", "+"})
                        self.assertIn(terrain[y][right], {"|", "+"})
                        for x in range(left + 1, right):
                            self.assertIn(terrain[y][x], {".", "<", ">"})

                self.assertTrue(any("#" in row for row in terrain))
                passable = {
                    (x, y)
                    for y, row in enumerate(terrain)
                    for x, tile in enumerate(row)
                    if tile in PASSABLE
                }
                start = (int(level["hero"]["x"]), int(level["hero"]["y"]))
                reached = {start}
                frontier = deque([start])
                while frontier:
                    x, y = frontier.popleft()
                    for candidate in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if candidate in passable and candidate not in reached:
                            reached.add(candidate)
                            frontier.append(candidate)
                self.assertEqual(passable, reached)

                self.assertEqual(1, sum(row.count("<") for row in terrain))
                self.assertEqual(1, sum(row.count(">") for row in terrain))
                self.assertEqual("<", terrain[start[1]][start[0]])
                all_entities = [*level["monsters"], *level["objects"], *level["traps"]]
                for entity in all_entities:
                    self.assertTrue(any(_inside(position(entity), bounds) for bounds in interior_bounds), entity["id"])

                monsters = {monster["id"]: monster for monster in level["monsters"]}
                objects = {item["id"]: item for item in level["objects"]}
                intentional_pair = {"generated-dog", "generated-pet-ration"}
                occupants: dict[tuple[int, int], set[str]] = {}
                for entity in all_entities:
                    occupants.setdefault(position(entity), set()).add(entity["id"])
                self.assertEqual(
                    [intentional_pair],
                    [ids for ids in occupants.values() if len(ids) > 1],
                )
                self.assertEqual(position(monsters["generated-dog"]), position(objects["generated-pet-ration"]))

    def test_signed_seeds_produce_semantic_variation(self) -> None:
        signatures = set()
        species_sets = set()
        for seed in range(-32, 33):
            level = resolve_task(generated_task(seed))["level_dump"]
            rooms = sorted(level["metadata"]["generated_rooms"], key=room_id)
            signatures.add(
                (
                    tuple(_bounds(room, "outer") for room in rooms),
                    tuple(level["terrain"]),
                    tuple(position(monster) for monster in level["monsters"]),
                )
            )
            species_sets.add(tuple(monster["name"] for monster in level["monsters"][:3]))
        self.assertGreater(len(signatures), 50)
        self.assertGreater(len(species_sets), 8)

    def test_complete_python_rust_resolved_reset_parity(self) -> None:
        for seed in (-17, -1, 0, 1, 23, 20260806):
            with self.subTest(seed=seed):
                task = generated_task(seed)
                python = run_python(task)
                rust = run_rust(task)
                python_checkpoint = json.loads(python["checkpoint"]["blob"])
                rust_checkpoint = json.loads(rust["checkpoint"]["blob"])
                self.assertEqual(python_checkpoint["resolved"], rust_checkpoint["resolved"])
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])


if __name__ == "__main__":
    unittest.main()
