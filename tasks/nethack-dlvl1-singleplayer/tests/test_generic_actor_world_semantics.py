"""Parity coverage for generic actor inventory, stairs, traps, and scheduling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def corridor() -> list[str]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 18):
        terrain[5][x] = "."
    return ["".join(row) for row in terrain]


def base_task(*, task_id: str, hero: dict[str, int], monsters: list[dict[str, object]] | None = None, objects: list[dict[str, object]] | None = None, traps: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "task_id": task_id,
        "seed": 137,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": corridor(),
            "hero": hero,
            "monsters": monsters or [],
            "objects": objects or [],
            "traps": traps or [],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericActorWorldSemanticsTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python, rust

    def test_pickup_capable_monster_carries_an_object(self) -> None:
        task = base_task(
            task_id="generic-monster-pickup",
            hero={"x": 3, "y": 5},
            objects=[{"id": "monster-ration", "kind": "%", "name": "a ration", "position": {"x": 10, "y": 5}, "nutrition": 600}],
            monsters=[{
                "id": "pack-mule",
                "name": "pack mule",
                "char": "m",
                "position": {"x": 10, "y": 5},
                "hp": 8,
                "peaceful": True,
                "pickup": True,
                "movement": "stationary",
            }],
        )
        task["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        monster = python["readout"]["private"]["monsters"][0]
        self.assertEqual([], python["readout"]["private"]["floor_items"])
        self.assertEqual("monster-ration", monster["inventory"][0]["id"])
        self.assertTrue(any("MonsterPickup(pack mule,a ration)" in event for event in python["events"]))

    def test_authored_prayer_applies_explicit_effect_and_matches_both_lanes(self) -> None:
        task = base_task(
            task_id="generic-prayer-contract",
            hero={"x": 3, "y": 5},
        )
        task["level_dump"]["metadata"]["hp"] = 4
        task["level_dump"]["metadata"]["hp_max"] = 20
        task["level_dump"]["metadata"]["prayer"] = {
            "effect": "healing",
            "amount": 7,
            "message": "A warm blessing surrounds you.",
        }
        task["actions"] = ["Command.PRAY", "y"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual(11, python["readout"]["private"]["hp"])
        self.assertTrue(any("Pray()" in event for event in python["events"]))
        self.assertEqual("A warm blessing surrounds you.", python["readout"]["public"]["message"])

    def test_empty_monster_trap_effect_is_omitted_from_both_nev_payloads(self) -> None:
        task = base_task(
            task_id="generic-empty-monster-trap-effect",
            hero={"x": 3, "y": 5},
            traps=[{
                "id": "plain-arrow-trap",
                "kind": "arrow",
                "damage": 0,
                "effect": "",
                "position": {"x": 9, "y": 5},
            }],
            monsters=[{
                "id": "trap-walker",
                "name": "trap walker",
                "char": "g",
                "position": {"x": 10, "y": 5},
                "hp": 8,
                "movement": "chase",
                "vision": 20,
            }],
        )
        task["actions"] = ["MiscDirection.WAIT"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["nev"], rust["nev"])
        trap_event = next(event for event in rust["nev"] if event["kind"] == "monster_trap")
        self.assertNotIn("effect", trap_event["payload"])

    def test_killing_authored_monster_drops_explicit_loot(self) -> None:
        task = base_task(
            task_id="generic-monster-drop",
            hero={"x": 5, "y": 5},
            monsters=[{
                "id": "loot-goblin",
                "name": "loot goblin",
                "char": "g",
                "position": {"x": 6, "y": 5},
                "hp": 1,
                "experience": 4,
                "armor_class": 1,
                "level": 1,
                "to_hit": 0,
                "damage_dice": 1,
                "damage_sides": 1,
                "drops": [{"id": "goblin-gem", "kind": "*", "name": "a gem", "quantity": 1}],
            }],
        )
        task["actions"] = ["Command.FIGHT", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual([], python["readout"]["private"]["monsters"])
        self.assertEqual("goblin-gem", python["readout"]["private"]["floor_items"][0]["id"])
        self.assertTrue(any("MonsterDrop(loot goblin,a gem)" in event for event in python["events"]))

    def test_authored_trap_effect_blocks_movement_and_exits_up_stairs(self) -> None:
        task = base_task(
            task_id="generic-trap-effect",
            hero={"x": 5, "y": 5},
            traps=[{
                "id": "web-trap",
                "kind": "web",
                "damage": 0,
                "effect": "web",
                "position": {"x": 6, "y": 5},
            }],
        )
        task["level_dump"]["terrain"][5] = corridor()[5][:4] + "<" + corridor()[5][5:]
        task["actions"] = ["CompassDirection.E", "CompassDirection.E", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertEqual({"x": 6, "y": 5}, {key: private["hero"][key] for key in ("x", "y")})
        self.assertTrue(any("Trap(web)" in event for event in python["events"]))
        self.assertTrue(any("You are unable to move." in event for event in python["events"]))
        self.assertFalse(any("Move(7,5)" in event for event in python["events"]))

    def test_typed_trap_damage_respects_hero_and_monster_resistance(self) -> None:
        hero_task = base_task(
            task_id="generic-typed-trap-hero",
            hero={"x": 5, "y": 5},
            traps=[{
                "id": "fire-pit",
                "kind": "pit",
                "damage": 9,
                "damage_type": "fire",
                "position": {"x": 6, "y": 5},
            }],
        )
        hero_task["level_dump"]["metadata"]["resistances"] = {"fire": 100}
        hero_task["actions"] = ["CompassDirection.E"]
        hero_python, _ = self.assert_lanes_match(hero_task)
        self.assertEqual(20, hero_python["readout"]["private"]["hp"])

        actor_task = base_task(
            task_id="generic-typed-trap-actor",
            hero={"x": 3, "y": 5},
            traps=[{
                "id": "fire-pit",
                "kind": "pit",
                "damage": 9,
                "damage_type": "fire",
                "position": {"x": 9, "y": 5},
            }],
            monsters=[{
                "id": "fireproof-walker",
                "name": "fireproof walker",
                "char": "w",
                "position": {"x": 10, "y": 5},
                "hp": 20,
                "resistances": {"fire": 100},
                "vision": 10,
            }],
        )
        actor_task["actions"] = ["MiscDirection.WAIT"]
        actor_python, _ = self.assert_lanes_match(actor_task)
        self.assertEqual(20, actor_python["readout"]["private"]["monsters"][0]["hp"])

    def test_dice_traps_share_rng_damage_for_hero_and_monster_targets(self) -> None:
        hero_task = base_task(
            task_id="generic-dice-trap-hero",
            hero={"x": 5, "y": 5},
            traps=[{
                "id": "dice-pit",
                "kind": "pit",
                "damage": 2,
                "damage_dice": 2,
                "damage_sides": 4,
                "position": {"x": 6, "y": 5},
            }],
        )
        hero_task["actions"] = ["CompassDirection.E"]
        hero_python, _ = self.assert_lanes_match(hero_task)
        hero_hp = hero_python["readout"]["private"]["hp"]
        self.assertGreaterEqual(hero_hp, 10)
        self.assertLessEqual(hero_hp, 16)

        actor_task = base_task(
            task_id="generic-dice-trap-actor",
            hero={"x": 3, "y": 5},
            traps=[{
                "id": "dice-pit",
                "kind": "pit",
                "damage": 2,
                "damage_dice": 2,
                "damage_sides": 4,
                "position": {"x": 9, "y": 5},
            }],
            monsters=[{
                "id": "dice-walker",
                "name": "dice walker",
                "char": "w",
                "position": {"x": 10, "y": 5},
                "hp": 20,
                "vision": 10,
            }],
        )
        actor_task["actions"] = ["MiscDirection.WAIT"]
        actor_python, _ = self.assert_lanes_match(actor_task)
        actor_hp = actor_python["readout"]["private"]["monsters"][0]["hp"]
        self.assertGreaterEqual(actor_hp, 10)
        self.assertLessEqual(actor_hp, 16)

    def test_generic_terminal_boundaries_clear_primary_planes_and_expose_tty(self) -> None:
        task = base_task(
            task_id="generic-terminal-death-ui",
            hero={"x": 5, "y": 5},
            traps=[{"id": "fatal", "kind": "pit", "damage": 99, "position": {"x": 6, "y": 5}}],
        )
        task["actions"] = ["CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        public = python["readout"]["public"]
        self.assertEqual("death", public["terminal_reason"])
        self.assertEqual(24, len(public["terminal_tty"]["char_rows"]))
        self.assertEqual(80, len(public["terminal_tty"]["char_rows"][0]))
        self.assertTrue(all(row == "\0" * 79 for row in public["chars"]))

        saved = base_task(task_id="generic-terminal-save-ui", hero={"x": 5, "y": 5})
        saved["actions"] = ["Command.SAVE", "CompassDirection.NW"]
        python, _ = self.assert_lanes_match(saved)
        self.assertEqual("saved", python["readout"]["public"]["terminal_reason"])
        self.assertIsNotNone(python["readout"]["public"]["terminal_tty"])

    def test_wandering_speed_and_up_stair_terminal_are_parity_safe(self) -> None:
        task = base_task(
            task_id="generic-wanderer",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "wanderer",
                "name": "wanderer",
                "char": "w",
                "position": {"x": 12, "y": 5},
                "hp": 4,
                "peaceful": True,
                "movement": "wander",
                "speed": 2,
            }],
        )
        task["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertTrue(any("MonsterMove(wanderer" in event for event in python["events"]))

        stair_task = base_task(task_id="generic-ascend", hero={"x": 4, "y": 5})
        terrain = corridor()
        terrain[5] = terrain[5][:4] + "<" + terrain[5][5:]
        stair_task["level_dump"]["terrain"] = terrain
        stair_task["actions"] = ["MiscDirection.UP"]
        python, _ = self.assert_lanes_match(stair_task)
        self.assertTrue(python["readout"]["terminated"])
        self.assertEqual("ascended", python["readout"]["private"]["terminal_reason"])

    def test_fleeing_actor_increases_distance_and_honors_stop_distance(self) -> None:
        task = base_task(
            task_id="generic-fleeing-actor",
            hero={"x": 5, "y": 5},
            monsters=[{
                "id": "fleeing-actor",
                "name": "fleeing actor",
                "char": "f",
                "position": {"x": 7, "y": 5},
                "hp": 4,
                "movement": "flee",
                "speed": 1,
            }],
        )
        task["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 8, "y": 5}, python["readout"]["private"]["monsters"][0]["position"])
        self.assertTrue(any("MonsterMove(fleeing actor,8,5)" in event for event in python["events"]))

        held = base_task(
            task_id="generic-fleeing-actor-threshold",
            hero={"x": 5, "y": 5},
            monsters=[{
                "id": "fleeing-actor",
                "name": "fleeing actor",
                "char": "f",
                "position": {"x": 9, "y": 5},
                "hp": 4,
                "movement": "flee",
                "flee_distance": 4,
            }],
        )
        held["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(held)
        self.assertEqual({"x": 9, "y": 5}, python["readout"]["private"]["monsters"][0]["position"])

    def test_authored_turn_period_and_offset_gate_actor_passes(self) -> None:
        task = base_task(
            task_id="generic-actor-turn-period",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "slow-chaser",
                "name": "slow chaser",
                "char": "s",
                "position": {"x": 10, "y": 5},
                "hp": 4,
                "movement": "chase",
                "vision": 20,
                "turn_period": 2,
            }],
        )
        task["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 8, "y": 5}, python["readout"]["private"]["monsters"][0]["position"])
        self.assertEqual(3, python["readout"]["private"]["monsters"][0]["last_turn"])

    def test_authored_initiative_orders_actor_passes_and_rng(self) -> None:
        task = base_task(task_id="generic-initiative-order", hero={"x": 5, "y": 5})
        task["level_dump"]["metadata"].update({"hp": 1, "hp_max": 1, "ac": 100})
        task["level_dump"]["monsters"] = [
            {
                "id": "low-initiative",
                "name": "low initiative",
                "char": "l",
                "position": {"x": 4, "y": 5},
                "hp": 4,
                "initiative": 1,
                "armor_class": 100,
                "level": 1,
                "to_hit": 0,
                "damage_dice": 1,
                "damage_sides": 1,
            },
            {
                "id": "high-initiative",
                "name": "high initiative",
                "char": "h",
                "position": {"x": 6, "y": 5},
                "hp": 4,
                "initiative": 10,
                "armor_class": 100,
                "level": 1,
                "to_hit": 200,
                "damage_dice": 1,
                "damage_sides": 1,
            },
        ]
        task["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertTrue(python["readout"]["terminated"])
        self.assertTrue(any("MonsterAttack(high initiative)" in event for event in python["events"]))
        self.assertFalse(any("MonsterAttack(low initiative)" in event for event in python["events"]))

        delayed = base_task(
            task_id="generic-actor-turn-offset",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "delayed-chaser",
                "name": "delayed chaser",
                "char": "d",
                "position": {"x": 10, "y": 5},
                "hp": 4,
                "movement": "chase",
                "vision": 20,
                "turn_period": 2,
                "turn_offset": 2,
            }],
        )
        delayed["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(delayed)
        self.assertEqual({"x": 9, "y": 5}, python["readout"]["private"]["monsters"][0]["position"])
        self.assertEqual(3, python["readout"]["private"]["monsters"][0]["last_turn"])

    def test_authored_door_properties_control_open_and_close(self) -> None:
        task = base_task(task_id="generic-door-properties", hero={"x": 5, "y": 5})
        terrain = corridor()
        terrain[5] = terrain[5][:6] + "+" + terrain[5][7:]
        task["level_dump"]["terrain"] = terrain
        task["level_dump"]["metadata"]["doors"] = [{"position": {"x": 6, "y": 5}, "locked": False, "trapped": False}]
        task["actions"] = ["Command.OPEN", "CompassDirection.E", "Command.CLOSE", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertFalse(python["readout"]["private"]["door_properties"][0]["open"])
        self.assertTrue(any("OpenDoor()" in event for event in python["events"]))

        locked = base_task(task_id="generic-locked-door", hero={"x": 5, "y": 5})
        locked["level_dump"]["terrain"] = terrain
        locked["level_dump"]["metadata"]["doors"] = [{"position": {"x": 6, "y": 5}, "locked": True}]
        locked["actions"] = ["Command.OPEN", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(locked)
        self.assertTrue(any("The door is locked." in event for event in python["events"]))

        blocked = base_task(task_id="generic-boulder-blocks-close", hero={"x": 5, "y": 5})
        blocked["level_dump"]["terrain"] = terrain
        blocked["level_dump"]["metadata"]["doors"] = [{"position": {"x": 6, "y": 5}, "locked": False, "open": False}]
        blocked["level_dump"]["objects"] = [{
            "id": "door-boulder",
            "kind": "0",
            "name": "a boulder",
            "position": {"x": 6, "y": 5},
        }]
        blocked["actions"] = ["Command.OPEN", "CompassDirection.E", "Command.CLOSE", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(blocked)
        self.assertTrue(any("The door is blocked." in event for event in python["events"]))
        self.assertTrue(python["readout"]["private"]["door_properties"][0]["open"])

    def test_authored_boulder_push_blocks_movement_and_current_fov(self) -> None:
        task = base_task(task_id="generic-boulder-push", hero={"x": 4, "y": 5})
        task["level_dump"]["objects"] = [{
            "id": "authored-boulder",
            "kind": "0",
            "name": "a boulder",
            "position": {"x": 5, "y": 5},
        }]
        task["level_dump"]["monsters"] = [{
            "id": "blocked-behind-boulder",
            "name": "blocked target",
            "char": "m",
            "position": {"x": 8, "y": 5},
            "hp": 4,
            "peaceful": True,
            "movement": "stationary",
        }]
        task["actions"] = ["CompassDirection.E", "Command.KICK", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertEqual({"x": 4, "y": 5}, {key: private["hero"][key] for key in ("x", "y")})
        self.assertEqual({"x": 6, "y": 5}, private["floor_items"][0]["position"])
        self.assertEqual(".", python["readout"]["public"]["chars"][5][8])
        self.assertTrue(any("BoulderPush(authored-boulder,6,5)" in event for event in python["events"]))
        self.assertTrue(any("There is a boulder in the way." in event for event in python["events"]))

    def test_authored_boulder_push_stops_at_walls_and_is_not_pickupable(self) -> None:
        task = base_task(task_id="generic-boulder-blocked", hero={"x": 4, "y": 5})
        terrain = corridor()
        terrain[5] = terrain[5][:6] + "|" + terrain[5][7:]
        task["level_dump"]["terrain"] = terrain
        task["level_dump"]["objects"] = [{
            "id": "blocked-boulder",
            "kind": "0",
            "name": "a boulder",
            "position": {"x": 5, "y": 5},
        }]
        task["actions"] = ["Command.KICK", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 5, "y": 5}, python["readout"]["private"]["floor_items"][0]["position"])
        self.assertTrue(any("The boulder won't budge." in event for event in python["events"]))

        pickup = {**task, "task_id": "generic-boulder-pickup", "actions": ["Command.PICKUP"]}
        python, _ = self.assert_lanes_match(pickup)
        self.assertEqual([], python["readout"]["private"]["inventory"])
        self.assertEqual("There is nothing here to pick up.", python["readout"]["public"]["message"])

        monster_task = base_task(
            task_id="generic-monster-opens-door",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "door-goblin",
                "name": "door goblin",
                "char": "g",
                "position": {"x": 7, "y": 5},
                "vision": 10,
                "opens_doors": True,
            }],
        )
        monster_terrain = corridor()
        monster_terrain[5] = monster_terrain[5][:6] + "+" + monster_terrain[5][7:]
        monster_task["level_dump"]["terrain"] = monster_terrain
        monster_task["level_dump"]["metadata"]["doors"] = [{"position": {"x": 6, "y": 5}, "locked": False}]
        monster_task["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(monster_task)
        self.assertTrue(python["readout"]["private"]["door_properties"][0]["open"])
        self.assertTrue(any("MonsterOpenDoor(door goblin,6,5)" in event for event in python["events"]))

    def test_seen_traps_and_blind_status_change_the_rendered_planes(self) -> None:
        trap_task = base_task(
            task_id="generic-trap-render",
            hero={"x": 5, "y": 5},
            traps=[{"id": "visible-dart", "kind": "dart", "damage": 1, "position": {"x": 6, "y": 5}}],
        )
        trap_task["actions"] = ["Command.SEARCH"]
        python, _ = self.assert_lanes_match(trap_task)
        self.assertEqual("^", python["readout"]["public"]["chars"][5][6])

        blind_task = base_task(task_id="generic-blind-render", hero={"x": 5, "y": 5})
        blind_task["level_dump"]["inventory"] = [{"id": "blind-potion", "letter": "a", "kind": "!", "name": "a blindness potion", "effect": "blind"}]
        blind_task["actions"] = ["Command.QUAFF", 24]
        python, _ = self.assert_lanes_match(blind_task)
        visible = [char for row in python["readout"]["public"]["chars"] for char in row if char not in {" ", "\0"}]
        self.assertEqual(["@"], visible)

    def test_xray_effect_reveals_through_walls_then_expires(self) -> None:
        task = base_task(
            task_id="generic-xray-lifecycle",
            hero={"x": 4, "y": 5},
            monsters=[{
                "id": "behind-wall",
                "name": "behind wall",
                "char": "g",
                "position": {"x": 7, "y": 5},
                "hp": 8,
                "movement": "stationary",
            }],
        )
        terrain = corridor()
        terrain[5] = terrain[5][:6] + "|" + terrain[5][7:]
        task["level_dump"]["terrain"] = terrain
        task["level_dump"]["inventory"] = [{
            "id": "xray-potion",
            "letter": "a",
            "kind": "!",
            "name": "a potion of x-ray vision",
            "effect": "xray",
        }]
        task["actions"] = ["Command.QUAFF", 24]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual(4, python["readout"]["private"]["status_effects"]["xray"])
        self.assertEqual("g", python["readout"]["public"]["chars"][5][7])

        expired = dict(task)
        expired["task_id"] = "generic-xray-expired"
        expired["actions"] = ["Command.QUAFF", 24] + ["MiscDirection.WAIT"] * 4
        python, _ = self.assert_lanes_match(expired)
        self.assertNotIn("xray", python["readout"]["private"]["status_effects"])
        self.assertNotEqual("g", python["readout"]["public"]["chars"][5][7])

    def test_confused_actor_wanders_and_blind_actor_does_not_acquire_hero(self) -> None:
        terrain = [list(row) for row in corridor()]
        for y in range(3, 8):
            for x in range(2, 15):
                terrain[y][x] = "."
        terrain = ["".join(row) for row in terrain]
        confused = base_task(
            task_id="generic-confused-actor",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "confused-actor",
                "name": "confused actor",
                "char": "m",
                "position": {"x": 10, "y": 5},
                "hp": 8,
                "movement": "chase",
                "speed": 1,
                "vision": 20,
                "status_effects": {"confused": 1},
            }],
        )
        confused["level_dump"]["terrain"] = terrain
        confused["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(confused)
        actor = python["readout"]["private"]["monsters"][0]
        self.assertNotEqual({"x": 9, "y": 5}, actor["position"])
        self.assertTrue(any("MonsterMove(confused actor" in event for event in python["events"]))

        blind = dict(confused)
        blind["task_id"] = "generic-blind-actor"
        blind["level_dump"] = dict(confused["level_dump"])
        blind["level_dump"]["monsters"] = [dict(confused["level_dump"]["monsters"][0])]
        blind["level_dump"]["monsters"][0]["id"] = "blind-actor"
        blind["level_dump"]["monsters"][0]["name"] = "blind actor"
        blind["level_dump"]["monsters"][0]["status_effects"] = {"blind": 1}
        python, _ = self.assert_lanes_match(blind)
        self.assertEqual({"x": 10, "y": 5}, python["readout"]["private"]["monsters"][0]["position"])

    def test_rearming_trap_can_trigger_again_after_its_cooldown(self) -> None:
        task = base_task(
            task_id="generic-rearming-trap",
            hero={"x": 5, "y": 5},
            traps=[{
                "id": "reusable-dart",
                "kind": "dart",
                "damage": 1,
                "rearm": 2,
                "one_shot": False,
                "position": {"x": 6, "y": 5},
            }],
        )
        task["actions"] = ["CompassDirection.E", "CompassDirection.W", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual(18, python["readout"]["private"]["hp"])
        trap = python["readout"]["private"]["traps"][0]
        self.assertTrue(trap["triggered"])
        self.assertEqual(2, sum("Trap(dart)" in event for event in python["events"]))
        self.assertTrue(any("TrapRearmed(dart)" in event for event in python["events"]))

    def test_monster_triggers_trap_and_drops_loot(self) -> None:
        task = base_task(
            task_id="generic-monster-trap",
            hero={"x": 3, "y": 5},
            traps=[{
                "id": "monster-pit",
                "kind": "pit",
                "damage": 1,
                "position": {"x": 9, "y": 5},
            }],
            monsters=[{
                "id": "trap-goblin",
                "name": "trap goblin",
                "char": "g",
                "position": {"x": 10, "y": 5},
                "hp": 1,
                "vision": 10,
                "drops": [{"id": "trap-gem", "kind": "*", "name": "a gem", "quantity": 1}],
            }],
        )
        task["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual([], python["readout"]["private"]["monsters"])
        self.assertEqual("trap-gem", python["readout"]["private"]["floor_items"][0]["id"])
        self.assertTrue(any("MonsterTrap(trap goblin,pit)" in event for event in python["events"]))
        self.assertTrue(any("MonsterKilled(trap goblin)" in event for event in python["events"]))

    def test_zero_speed_actor_holds_position_and_blind_clears_specials(self) -> None:
        task = base_task(
            task_id="generic-zero-speed",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "slow-wanderer",
                "name": "slow wanderer",
                "char": "w",
                "position": {"x": 12, "y": 5},
                "peaceful": True,
                "movement": "wander",
                "speed": 0,
            }],
        )
        task["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 12, "y": 5}, python["readout"]["private"]["monsters"][0]["position"])
        self.assertFalse(any("MonsterMove(slow wanderer" in event for event in python["events"]))

        blind = base_task(
            task_id="generic-blind-pet-special",
            hero={"x": 5, "y": 5},
            monsters=[{
                "id": "blind-pet",
                "name": "blind pet",
                "char": "d",
                "position": {"x": 8, "y": 5},
                "pet": True,
            }],
        )
        blind["level_dump"]["inventory"] = [{"id": "blind-potion", "letter": "a", "kind": "!", "name": "a blindness potion", "effect": "blind"}]
        blind["actions"] = ["Command.QUAFF", 24]
        python, _ = self.assert_lanes_match(blind)
        self.assertTrue(all(value == 0 for row in python["readout"]["public"]["specials"] for value in row))

    def test_live_monster_uses_current_los_but_remembers_its_terrain_underlay(self) -> None:
        task = base_task(
            task_id="generic-current-los-underlay",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "distant-stationary",
                "name": "distant stationary",
                "char": "d",
                "position": {"x": 8, "y": 5},
                "movement": "stationary",
            }],
        )
        task["actions"] = ["CompassDirection.W"]
        python, _ = self.assert_lanes_match(task)
        # The cell remains remembered in the map, but the live actor is now
        # outside the five-cell current LOS radius.
        self.assertTrue(python["readout"]["private"]["seen"][5][8])
        self.assertEqual(".", python["readout"]["public"]["chars"][5][8])

    def test_authored_special_bytes_follow_visible_objects_and_actors(self) -> None:
        task = base_task(
            task_id="generic-special-bytes",
            hero={"x": 3, "y": 5},
            objects=[{
                "id": "pile-marker",
                "kind": "%",
                "name": "a marked ration pile",
                "position": {"x": 6, "y": 5},
                "special": 64,
            }],
            monsters=[{
                "id": "marked-pet",
                "name": "marked pet",
                "char": "d",
                "position": {"x": 8, "y": 5},
                "hp": 4,
                "pet": True,
                "movement": "stationary",
                "special": 32,
            }],
        )
        task["actions"] = ["MiscDirection.WAIT", "CompassDirection.W"]
        python, _ = self.assert_lanes_match(task)
        public = python["readout"]["public"]
        self.assertEqual(64, public["specials"][5][6])
        self.assertEqual(0, public["specials"][5][8])
        self.assertEqual(".", public["chars"][5][8])
        self.assertEqual(64, python["readout"]["private"]["floor_items"][0]["special"])
        self.assertEqual(32, python["readout"]["private"]["monsters"][0]["special"])

    def test_generic_teleport_and_seeall_commands_have_world_effects(self) -> None:
        teleport = base_task(task_id="generic-teleport-command", hero={"x": 3, "y": 5})
        teleport["actions"] = ["Command.TELEPORT"]
        python, _ = self.assert_lanes_match(teleport)
        self.assertNotEqual({"x": 3, "y": 5}, {key: python["readout"]["private"]["hero"][key] for key in ("x", "y")})
        self.assertTrue(any("Teleport(hero)" in event for event in python["events"]))

        seeall = base_task(task_id="generic-seeall-command", hero={"x": 3, "y": 5})
        seeall["actions"] = ["Command.SEEALL"]
        python, _ = self.assert_lanes_match(seeall)
        self.assertTrue(all(python["readout"]["private"]["seen"][5][x] for x in range(2, 18)))
        self.assertTrue(any("MapRevealed(all)" in event for event in python["events"]))

    def test_generic_jump_uses_direction_prompt_and_moves_two_cells(self) -> None:
        task = base_task(task_id="generic-jump", hero={"x": 3, "y": 5})
        task["actions"] = ["Command.JUMP", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 5, "y": 5}, {key: python["readout"]["private"]["hero"][key] for key in ("x", "y")})
        self.assertTrue(any("Jump(5,5)" in event for event in python["events"]))

    def test_generic_extended_command_dispatches_into_jump(self) -> None:
        task = base_task(task_id="generic-extcmd-jump", hero={"x": 3, "y": 5})
        task["actions"] = ["Command.EXTCMD", "j", "u", "m", "p", "MiscAction.MORE", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 5, "y": 5}, {key: python["readout"]["private"]["hero"][key] for key in ("x", "y")})
        self.assertTrue(any("ModeEnter(direction)" in event for event in python["events"]))

    def test_generic_loot_menu_transfers_one_floor_item(self) -> None:
        task = base_task(
            task_id="generic-loot-menu",
            hero={"x": 3, "y": 5},
            objects=[{"id": "floor-gem", "kind": "*", "name": "a gem", "position": {"x": 3, "y": 5}}],
        )
        task["actions"] = ["Command.LOOT", 24]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual([], python["readout"]["private"]["floor_items"])
        self.assertEqual("floor-gem", python["readout"]["private"]["inventory"][0]["id"])
        self.assertTrue(any("Loot(a gem)" in event for event in python["events"]))

    def test_monster_trap_effects_block_and_resume_actor_turns(self) -> None:
        task = base_task(
            task_id="generic-monster-trap-status",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "sleeping-target",
                "name": "sleeping target",
                "char": "s",
                "position": {"x": 10, "y": 5},
                "hp": 10,
                "movement": "chase",
                "vision": 10,
            }],
            traps=[{
                "id": "sleeping-trap",
                "kind": "sleep",
                "damage": 0,
                "effect": "sleep",
                "position": {"x": 9, "y": 5},
            }],
        )
        task["actions"] = ["MiscDirection.WAIT"] * 5
        python, _ = self.assert_lanes_match(task)
        monster = python["readout"]["private"]["monsters"][0]
        self.assertEqual({"x": 8, "y": 5}, monster["position"])
        self.assertTrue(any("MonsterStatusTick(sleeping target,sleeping)" in event for event in python["events"]))
        self.assertTrue(any("MonsterStatusExpired(sleeping target,sleeping)" in event for event in python["events"]))

        teleport = base_task(
            task_id="generic-monster-trap-teleport",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "teleport-target",
                "name": "teleport target",
                "char": "t",
                "position": {"x": 10, "y": 5},
                "movement": "chase",
                "vision": 10,
            }],
            traps=[{
                "id": "teleport-trap",
                "kind": "teleport",
                "damage": 0,
                "effect": "teleport",
                "position": {"x": 9, "y": 5},
            }],
        )
        teleport["actions"] = ["MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(teleport)
        teleported = python["readout"]["private"]["monsters"][0]["position"]
        self.assertNotEqual({"x": 3, "y": 5}, teleported)
        self.assertTrue(any("MonsterTeleport(teleport target" in event for event in python["events"]))

    def test_invisibility_blocks_hostile_detection_unless_monster_can_see_it(self) -> None:
        task = base_task(
            task_id="generic-invisibility-detection",
            hero={"x": 5, "y": 5},
            monsters=[{
                "id": "blind-to-invisible",
                "name": "blind to invisible",
                "char": "b",
                "position": {"x": 6, "y": 5},
                "movement": "chase",
            }],
        )
        task["level_dump"]["inventory"] = [{"id": "invisibility-potion", "letter": "a", "kind": "!", "name": "a potion of invisibility", "effect": "invisibility"}]
        task["actions"] = ["Command.QUAFF", 24, "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual(20, python["readout"]["private"]["hp"])
        self.assertFalse(any("MonsterAttack(blind to invisible)" in event for event in python["events"]))

        detector = base_task(
            task_id="generic-see-invisible-detection",
            hero={"x": 5, "y": 5},
            monsters=[{
                "id": "see-invisible",
                "name": "see invisible",
                "char": "s",
                "position": {"x": 6, "y": 5},
                "movement": "chase",
                "see_invisible": True,
            }],
        )
        detector["level_dump"]["inventory"] = [{"id": "invisibility-potion", "letter": "a", "kind": "!", "name": "a potion of invisibility", "effect": "invisibility"}]
        detector["actions"] = ["Command.QUAFF", 24]
        python, _ = self.assert_lanes_match(detector)
        self.assertLess(python["readout"]["private"]["hp"], 20)
        self.assertTrue(any("MonsterAttack(see invisible)" in event for event in python["events"]))

    def test_generic_pet_collision_does_not_attack_the_pet(self) -> None:
        task = base_task(
            task_id="generic-pet-collision",
            hero={"x": 3, "y": 5},
            monsters=[{
                "id": "friendly-dog",
                "name": "friendly dog",
                "char": "d",
                "position": {"x": 4, "y": 5},
                "hp": 7,
                "pet": True,
                "movement": "stationary",
            }],
        )
        task["actions"] = ["CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual({"x": 3, "y": 5}, {key: python["readout"]["private"]["hero"][key] for key in ("x", "y")})
        self.assertEqual(7, python["readout"]["private"]["monsters"][0]["hp"])
        self.assertTrue(any("friendly dog is in the way" in event for event in python["events"]))


if __name__ == "__main__":
    unittest.main()
