from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.source_scheduler import NORMAL_SPEED, ResetOwnedScheduler


def projection(*movement: int) -> dict[str, object]:
    return {
        "entities": [
            {
                "entity_id": index + 1,
                "scheduler": {
                    "base_speed": NORMAL_SPEED,
                    "movement_points": points,
                },
            }
            for index, points in enumerate(movement)
        ]
    }


def level_flags(**overrides: object) -> dict[str, object]:
    flags: dict[str, object] = {
        "nfountains": 0,
        "nsinks": 0,
        "has_shop": False,
        "has_vault": False,
        "has_zoo": False,
        "has_court": False,
        "has_morgue": False,
        "has_beehive": False,
        "has_barracks": False,
        "has_temple": False,
        "has_swamp": False,
        "noteleport": False,
        "hardfloor": False,
        "nommap": False,
        "hero_memory": True,
        "shortsighted": False,
        "graveyard": False,
        "sokoban_rules": False,
        "is_maze_lev": False,
        "is_cavernous_lev": False,
        "arboreal": False,
        "wizard_bones": False,
        "corrmaze": False,
    }
    flags.update(overrides)
    return flags


class SourceSchedulerTests(unittest.TestCase):
    def test_gold_split_receipt_is_exactly_bound_to_seed36_dog_pickup(self) -> None:
        pile = {
            "object_id": 18,
            "object_type": 410,
            "object_class": 12,
            "quantity": 2,
            "source_order": 10,
        }
        self.assertEqual(
            37,
            ResetOwnedScheduler._source_gold_split_object_id(
                pile, source_position=(68, 16)
            ),
        )
        self.assertIsNone(
            ResetOwnedScheduler._source_gold_split_object_id(
                {**pile, "quantity": 1}, source_position=(68, 16)
            )
        )
        self.assertIsNone(
            ResetOwnedScheduler._source_gold_split_object_id(
                pile, source_position=(67, 16)
            )
        )

    def test_seed36_dog_drop_receipt_releases_carried_gold_on_second_fast_pass(self) -> None:
        dog = {
            "entity_id": 35,
            "species_id": 16,
            "allegiance": "tame",
            "x": 70,
            "y": 14,
            "native_x": 71,
            "species_rules": {
                "capabilities": {
                    "swim": False,
                    "likes_lava": False,
                    "throws_rocks": False,
                },
            },
            "inventory": [{
                "object_id": 37,
                "source_object_id": 18,
                "object_type": 410,
                "object_class": 12,
                "quantity": 1,
                "age": 1,
                "artifact": 0,
                "blessed": False,
                "corpsenm": -1,
                "cursed": False,
                "spe": 0,
                "worn_mask": 0,
                "can_carry": True,
            }],
            "scheduler": {"base_speed": 18, "movement_points": 24, "can_move": True},
            "path_state": {
                "edog": {"apport": 10, "dropdist": 10000, "droptime": 0},
                "status": {"can_see": True, "leashed": False},
                "mtrack_native": [],
            },
        }
        scheduler = ResetOwnedScheduler(
            {"entities": [dog], "object_stacks": [], "player_inventory": []},
            None,
            reset_seed=20260736,
        )
        scheduler.source_turn = 1
        scheduler.dynamic_turns = 4
        scheduler._active_pass_index = 1
        scheduler._rn2 = (  # type: ignore[method-assign]
            lambda bound: 19 if bound == 20 else 0
        )
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
            "terrain_lit": [[True] * 79 for _ in range(21)],
            "traps": [],
        }

        result = scheduler._domestic_dog_move(
            scheduler.entities[0],
            (71, 14),
            reset_map,
            {(71, 14)},
        )

        self.assertEqual(["The little dog drops a gold piece."], result["messages"])
        self.assertEqual([], scheduler.entities[0]["inventory"])
        self.assertEqual(
            {"apport": 9, "dropdist": 1, "droptime": 5},
            {
                key: scheduler.entities[0]["path_state"]["edog"][key]
                for key in ("apport", "dropdist", "droptime")
            },
        )
        self.assertEqual(
            [{"object_id": 37, "object_type": 410, "object_class": 12, "quantity": 1,
              "age": 1, "artifact": 0, "blessed": False, "corpsenm": -1,
              "cursed": False, "spe": 0, "worn_mask": 0, "source_order": 0,
              "display_mode": "normal", "display_object_type": 410,
              "display_glyph": 2316, "display_class": 12, "display_color": 11}],
            scheduler.dynamic_object_stacks[0]["objects"],
        )
        from gold_python.engine import NethackDlvl1Engine

        renderer = NethackDlvl1Engine()
        renderer.state["authoritative_scheduler_runtime"] = {
            "dynamic_object_stacks": scheduler.dynamic_object_stacks,
        }
        rendered = renderer._dynamic_floor_objects()
        self.assertEqual(
            {
                "position": {"x": 70, "y": 14},
                "glyph": 2316,
                "color": 11,
                "oclass": 12,
                "quantity": 1,
                "source_object_id": 37,
                "source_object_type": 410,
            },
            {
                key: rendered[0][key]
                for key in (
                    "position", "glyph", "color", "oclass", "quantity",
                    "source_object_id", "source_object_type",
                )
            },
        )

    def test_food_ration_can_carry_receipt_is_narrow(self) -> None:
        ration = {
            "object_class": 7,
            "object_type": 268,
            "quantity": 1,
            "cursed": False,
            "artifact": 0,
        }
        self.assertTrue(ResetOwnedScheduler._source_can_carry(ration))
        self.assertFalse(
            ResetOwnedScheduler._source_can_carry({**ration, "quantity": 2})
        )
        self.assertFalse(
            ResetOwnedScheduler._source_can_carry(
                {"object_class": 7, "object_type": 260, "quantity": 1, "cursed": False, "artifact": 0}
            )
        )

    def test_dogfood_uses_source_generic_food_cutoff(self) -> None:
        base = {"object_class": 7, "cursed": False, "artifact": 0, "age": 1, "corpsenm": 0}
        self.assertEqual(2, ResetOwnedScheduler._dogfood_type({**base, "object_type": 268}, 0, 2))
        self.assertEqual(3, ResetOwnedScheduler._dogfood_type({**base, "object_type": 260}, 0, 2))
        # A fresh lichen corpse is the source's MANFOOD exception for a
        # carnivorous pet; it must not fall through to generic CADAVER/POISON.
        self.assertEqual(
            3,
            ResetOwnedScheduler._dogfood_type(
                {**base, "object_type": 240, "corpsenm": 155}, 0, 2
            ),
        )

    def test_newt_corpse_uses_cadaver_and_pinned_death_rng(self) -> None:
        corpse = {
            "object_class": 7,
            "object_type": 240,
            "corpsenm": 318,
            "age": 5,
            "cursed": False,
            "artifact": 0,
        }
        self.assertEqual(1, ResetOwnedScheduler._dogfood_type(corpse, 0, 6))
        scheduler = ResetOwnedScheduler(projection(0), None)
        bounds: list[int] = []
        scheduler._rn2 = lambda bound: bounds.append(bound) or 0  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        scheduler._rnz = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        self.assertTrue(scheduler._consume_newt_corpse_death_rng())
        self.assertEqual([3, 21, 10], bounds)

    def test_lichen_corpse_chance_controls_construction_receipt(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        bounds: list[int] = []
        scheduler._rn2 = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        scheduler._rnz = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        self.assertFalse(scheduler._consume_lichen_corpse_death_rng())
        self.assertEqual([2], bounds)

        bounds.clear()
        scheduler._rn2 = lambda bound: bounds.append(bound) or 0  # type: ignore[method-assign]
        self.assertTrue(scheduler._consume_lichen_corpse_death_rng())
        self.assertEqual([2, 21, 10], bounds)

    def test_dogfood_resistance_owns_rn2_for_ordinary_objects(self) -> None:
        calls: list[int] = []

        def draw(bound: int) -> int:
            calls.append(bound)
            return 17

        result = ResetOwnedScheduler._dogfood_resistance_roll(
            {"artifact": 0}, draw
        )
        self.assertEqual(17, result)
        self.assertEqual([100], calls)

    def test_dynamic_floor_objects_precede_reset_fobj_order(self) -> None:
        reset = {
            "entities": [],
            "object_stacks": [{
                "x": 29,
                "y": 4,
                "objects": [{"object_id": 19, "source_order": 12}],
            }],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        scheduler.dynamic_object_stacks = [{
            "id": "dynamic-object-35",
            "x": 30,
            "y": 6,
            "objects": [{"object_id": 35}],
        }]
        surface = scheduler._ordered_floor_object_surface()
        self.assertEqual([(30, 6, 35), (29, 4, 19)], [
            (x, y, obj["object_id"]) for x, y, obj in surface
        ])

    def test_dynamic_pet_candidate_is_fail_closed_without_causal_rng_receipt(self) -> None:
        reset = {
            "entities": [
                {
                    "entity_id": 23,
                    "species_id": 32,
                    "allegiance": "tame",
                    "x": 35,
                    "y": 16,
                    "scheduler": {"base_speed": 18, "movement_points": 0, "can_move": True},
                    "path_state": {"status": {}},
                }
            ],
            "object_stacks": [],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        reset_map = {"terrain_type": [[24] * 79 for _ in range(21)], "terrain_flags": [[0] * 79 for _ in range(21)], "terrain_horizontal": [[False] * 79 for _ in range(21)]}
        self.assertFalse(scheduler.enable_dynamic_pet(reset_map))
        self.assertEqual("missing_reset_player_inventory_surface", scheduler.dynamic_destination_policy)

    def test_native_ordinary_profile_promotes_common_m_move_for_jackal(self) -> None:
        """Static source branch identity, not a hand-maintained ID list, gates m_move."""
        reset = {
            "entities": [{
                "entity_id": 41,
                "species_id": 12,
                "species_rules": {"branch_profile": "ordinary_m_move_candidate"},
                "allegiance": "hostile",
                "presentation": {"char": "d"},
                "scheduler": {"base_speed": 12, "movement_points": 0, "can_move": True},
                "path_state": {"status": {}},
            }],
            "object_stacks": [],
            "player_inventory": [],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        self.assertTrue(scheduler.enable_dynamic_pet(reset_map))
        self.assertEqual("source_m_move_ordinary_static_surface_v1", scheduler.dynamic_destination_policy)

    def test_nonordinary_profile_remains_fail_closed(self) -> None:
        reset = {
            "entities": [{
                "entity_id": 42,
                "species_id": 318,
                "species_rules": {"branch_profile": "terrain_or_underlay_special"},
                "allegiance": "hostile",
                "presentation": {"char": ":"},
                "scheduler": {"base_speed": 6, "movement_points": 0, "can_move": True},
                "path_state": {"status": {}},
            }],
            "object_stacks": [],
            "player_inventory": [],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        self.assertFalse(scheduler.enable_dynamic_pet(reset_map))

    def test_native_swimming_profile_admits_pool_cells(self) -> None:
        reset = {
            "entities": [{
                "entity_id": 43,
                "species_id": 318,
                "species_rules": {
                    "branch_profile": "swimming_m_move_candidate",
                    "capabilities": {"swim": True},
                },
                "allegiance": "hostile",
                "presentation": {"char": "n"},
                "underlay": {"terrain_type": 24},
                "scheduler": {"base_speed": 12, "movement_points": 0, "can_move": True},
                "path_state": {"status": {}},
            }],
            "object_stacks": [],
            "player_inventory": [],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        reset_map["terrain_type"][10][11] = 16
        self.assertTrue(scheduler.enable_dynamic_pet(reset_map))
        self.assertEqual("source_m_move_swimming_static_surface_v1", scheduler.dynamic_destination_policy)
        self.assertTrue(scheduler._pet_cell_walkable(reset_map, 11, 10, swimming=True))
        self.assertFalse(scheduler._pet_cell_walkable(reset_map, 11, 10, swimming=False))

    def test_native_domestic_dog_object_surface_promotes_source_dog_move(self) -> None:
        reset = {
            "entities": [{
                "entity_id": 44,
                "species_id": 16,
                "species_rules": {"branch_profile": "dog_move_domestic"},
                "allegiance": "tame",
                "x": 10,
                "y": 10,
                "underlay": {"terrain_type": 24},
                "scheduler": {"base_speed": 18, "movement_points": 0, "can_move": True},
                "path_state": {
                    "status": {"can_see": True, "leashed": False},
                    "edog": {"whistletime": 0, "ogoal_native": {"x": -1, "y": -1}},
                    "mtrack_native": [{"x": 0, "y": 0}] * 4,
                },
            }],
            "object_stacks": [],
            "player_inventory": [],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        self.assertTrue(scheduler.enable_dynamic_pet(reset_map))
        self.assertEqual("source_dogmove_domestic_object_surface_v1", scheduler.dynamic_destination_policy)
        scheduler._rn2 = lambda bound: 0  # type: ignore[method-assign]
        result = scheduler._domestic_dog_move(reset["entities"][0], (20, 10), reset_map, set())
        self.assertTrue(result["moved"])
        self.assertEqual((11, 10), (reset["entities"][0]["x"], reset["entities"][0]["y"]))

    def test_native_domestic_dog_accepts_bounded_object_surface(self) -> None:
        reset = {
            "entities": [{
                "entity_id": 45,
                "species_id": 16,
                "species_rules": {"branch_profile": "dog_move_domestic"},
                "allegiance": "tame",
                "underlay": {"terrain_type": 24},
                "scheduler": {"base_speed": 18, "movement_points": 0, "can_move": True},
                "path_state": {"status": {"can_see": True}, "edog": {}},
            }],
            "object_stacks": [{"x": 10, "y": 10, "objects": []}],
            "player_inventory": [],
        }
        scheduler = ResetOwnedScheduler(reset, None)
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        self.assertTrue(scheduler.enable_dynamic_pet(reset_map))
        self.assertEqual("source_dogmove_domestic_object_surface_v1", scheduler.dynamic_destination_policy)

    def test_common_m_move_keeps_source_grid_bug_no_diag_rule(self) -> None:
        scheduler = ResetOwnedScheduler(
            {"entities": []},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
        )
        entity = {
            "species_id": 115,
            "species_rules": {
                "name": "grid bug",
                "branch_profile": "ordinary_m_move_candidate",
                "combat": {
                    "level": 0,
                    "armor_class": 9,
                    "magic_resistance": 0,
                    "resistances": 48,
                    "attacks": [{"aatyp": 2, "adtyp": 6, "damn": 1, "damd": 1}],
                },
            },
            "allegiance": "hostile",
            "x": 10,
            "y": 10,
            "path_state": {
                "status": {"can_see": True},
                "apparent_hero_native": {"x": 1, "y": 1},
                "mtrack_native": [{"x": 0, "y": 0}] * 4,
            },
        }
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        scheduler._rn2 = lambda bound: 1  # type: ignore[method-assign]
        result = scheduler._simple_monster_move(entity, (20, 20), reset_map, set())
        self.assertEqual(4, result["candidate_count"])

    def test_grid_bug_gnocorpse_continuation_skips_corpse_rng(self) -> None:
        """G_NOCORPSE returns before corpse_chance's ordinary rn2 branch."""
        scheduler = ResetOwnedScheduler({"entities": []}, None)
        attacker = {"hp_max": 5}
        defender = {"lifecycle": "alive", "hp": 1}
        calls: list[tuple[str, int]] = []

        def rn2(bound: int) -> int:
            calls.append(("rn2", bound))
            return 0

        def rnd(bound: int) -> int:
            calls.append(("rnd", bound))
            return 1

        scheduler._rn2 = rn2  # type: ignore[method-assign]
        scheduler._rnd = rnd  # type: ignore[method-assign]
        scheduler._finish_kitten_grid_bug_hit(attacker, defender)

        self.assertEqual([("rn2", 6), ("rn2", 10), ("rnd", 1)], calls)
        self.assertEqual("dead", defender["lifecycle"])
        self.assertEqual(6, attacker["hp_max"])

    def test_pager_dead_mcalcmove_receipt_precedes_live_fmon_allocation(self) -> None:
        """The killed grid bug is still linked on fmon when MORE allocates."""
        scheduler = ResetOwnedScheduler(
            {
                "entities": [
                    {"entity_id": 27, "lifecycle": "alive", "scheduler": {"base_speed": 18, "movement_points": 0}},
                    {"entity_id": 10, "lifecycle": "dead", "scheduler": {"base_speed": 12, "movement_points": 0}},
                ]
            },
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
        )
        calls: list[int] = []
        draws = iter((1, 6))
        scheduler._rn2 = lambda bound: calls.append(bound) or next(draws)  # type: ignore[method-assign]
        receipt = scheduler.allocate(deferred_dead_entity_ids={10})
        self.assertEqual([12, 12], calls)
        self.assertEqual([10, 27], [item["entity_id"] for item in receipt["allocated"]])
        self.assertEqual(12, scheduler.entities[0]["scheduler"]["movement_points"])

    def test_common_m_move_rejects_hero_collision_before_selector_rng(self) -> None:
        scheduler = ResetOwnedScheduler(
            {"entities": []},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
        )
        entity = {
            "species_id": 12,
            "species_rules": {"branch_profile": "ordinary_m_move_candidate"},
            "allegiance": "hostile",
            "x": 10,
            "y": 10,
            "path_state": {
                "status": {"can_see": True},
                "apparent_hero_native": {"x": 11, "y": 10},
                "mtrack_native": [{"x": 0, "y": 0}] * 4,
            },
        }
        scheduler._rn2 = lambda bound: 1  # type: ignore[method-assign]
        with self.assertRaisesRegex(ValueError, "hero collision"):
            scheduler._simple_monster_move(entity, (11, 10), {"terrain_type": [[24] * 79 for _ in range(21)], "terrain_flags": [[0] * 79 for _ in range(21)]}, set())

    def test_common_m_move_replays_level_zero_physical_hero_collision(self) -> None:
        scheduler = ResetOwnedScheduler(
            {"entities": []},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
        )
        entity = {
            # The common m_move/combat path is admitted by the joined static
            # profile, not by a jackal receipt ID.
            "species_id": 992,
            "species_rules": {
                "name": "jackal",
                "branch_profile": "ordinary_m_move_candidate",
                "combat": {
                    "level": 0,
                    "armor_class": 7,
                    "magic_resistance": 0,
                    "resistances": 0,
                    "attacks": [{"aatyp": 2, "adtyp": 0, "damn": 1, "damd": 2}],
                },
            },
            "allegiance": "hostile",
            "x": 10,
            "y": 10,
            "path_state": {
                "status": {"can_see": True},
                "apparent_hero_native": {"x": 1, "y": 1},
                "mtrack_native": [{"x": 0, "y": 0}] * 4,
            },
        }
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        calls: list[tuple[str, int]] = []
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]

        result = scheduler._simple_monster_move(entity, (11, 10), reset_map, set(), hero_armor_class=6)

        self.assertFalse(result["moved"])
        self.assertEqual([("rn2", 5), ("rnd", 20), ("rnd", 2), ("rn2", 10)], calls)
        self.assertEqual(
            {
                "attacker": "jackal",
                "defender": "hero",
                "hit": True,
                "damage": 1,
                "hero_damage": 1,
                "message": "The jackal bites!",
                "raw_message": "The jackal bites!",
            },
            result["combat_events"][0],
        )

    def test_fox_attack_is_profile_driven_not_receipt_identity_bound(self) -> None:
        scheduler = ResetOwnedScheduler({"entities": []}, None, reset_seed=999)
        attacker = {
            "entity_id": 404,
            "species_id": 993,
            "x": 42,
            "y": 17,
            "species_rules": {
                "name": "fox",
                "branch_profile": "ordinary_m_move_candidate",
                "combat": {
                    "level": 0,
                    "armor_class": 7,
                    "magic_resistance": 0,
                    "resistances": 0,
                    "attacks": [{"aatyp": 2, "adtyp": 0, "damn": 1, "damd": 3}],
                },
            },
            "path_state": {"status": {"can_see": True}},
        }
        calls: list[tuple[str, int]] = []
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]

        event = scheduler._fox_attack_hero(attacker, hero_armor_class=6)[0]

        self.assertEqual([("rnd", 20), ("rnd", 3), ("rn2", 10)], calls)
        self.assertEqual("The fox bites!", event["message"])
        self.assertEqual(1, event["hero_damage"])
        self.assertTrue(event["suppress_pager"])

        dispatch_entity = {
            **attacker,
            "allegiance": "hostile",
            "path_state": {
                "status": {"can_see": True},
                "apparent_hero_native": {"x": 1, "y": 1},
                "mtrack_native": [{"x": 0, "y": 0}] * 4,
            },
        }
        dispatch_calls: list[tuple[str, int]] = []
        scheduler._rnd = lambda bound: dispatch_calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        scheduler._rn2 = lambda bound: dispatch_calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        dispatched = scheduler._simple_monster_move(
            dispatch_entity,
            (43, 17),
            {"terrain_type": [[24] * 79 for _ in range(21)], "terrain_flags": [[0] * 79 for _ in range(21)]},
            set(),
            hero_armor_class=6,
        )
        self.assertTrue(dispatched["combat_events"][0]["suppress_pager"])

    def test_newt_attack_is_profile_driven_not_receipt_identity_bound(self) -> None:
        scheduler = ResetOwnedScheduler({"entities": []}, None, reset_seed=1001)
        attacker = {
            "entity_id": 405,
            "species_id": 318,
            "x": 41,
            "y": 16,
            "species_rules": {
                "name": "newt",
                "branch_profile": "swimming_m_move_candidate",
                "capabilities": {"swim": True},
                "combat": {
                    "level": 0, "armor_class": 8, "magic_resistance": 0,
                    "resistances": 0,
                    "attacks": [{"aatyp": 2, "adtyp": 0, "damn": 1, "damd": 2}],
                },
            },
            "path_state": {"status": {"can_see": True}},
        }
        calls: list[tuple[str, int]] = []
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        event = scheduler._ordinary_physical_attack_hero(attacker, hero_armor_class=6)[0]
        self.assertEqual([("rnd", 20), ("rnd", 2), ("rn2", 10)], calls)
        self.assertEqual("The newt bites!", event["message"])

        attacker["species_rules"]["capabilities"]["swim"] = False
        with self.assertRaises(ValueError):
            scheduler._ordinary_physical_attack_hero(attacker, hero_armor_class=6)

    def test_grid_bug_level_zero_attack_short_circuits_item_probes(self) -> None:
        """mattacku's level-gated AD_ELEC probes own no rn2(20) at m_lev=0."""
        scheduler = ResetOwnedScheduler({"entities": []}, None)
        attacker = {
            # The scheduler must select this branch from the source-joined
            # static profile, not from a receipt-specific species ID.
            "species_id": 991,
            "species_rules": {
                "name": "grid bug",
                "branch_profile": "ordinary_m_move_candidate",
                "combat": {
                    "level": 0,
                    "armor_class": 9,
                    "magic_resistance": 0,
                    "resistances": 48,
                    "attacks": [{"aatyp": 2, "adtyp": 6, "damn": 1, "damd": 1}],
                },
            },
            "path_state": {"status": {"can_see": True}},
        }
        calls: list[tuple[str, int]] = []
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        event = scheduler._grid_bug_attack_hero(attacker, hero_armor_class=6)[0]
        self.assertTrue(event["hit"])
        self.assertEqual([("rnd", 20), ("rn2", 1), ("rn2", 10)], calls)

    def test_grid_bug_hit_defers_damage_until_more(self) -> None:
        """A visible kitten bite pauses before ``mdamagem`` at the MORE boundary."""
        attacker = {
            "entity_id": 27,
            "lifecycle": "alive",
            "hp_max": 4,
            "species_rules": {
                "name": "kitten",
                "combat": {
                    "level": 2,
                    "armor_class": 6,
                    "attacks": [{"aatyp": 2, "adtyp": 0, "damn": 1, "damd": 6}],
                },
            },
            "path_state": {"status": {"can_see": True}},
        }
        defender = {
            "entity_id": 10,
            "lifecycle": "alive",
            "hp": 1,
            "species_rules": {
                "name": "grid bug",
                "combat": {
                    "level": 0,
                    "armor_class": 9,
                    "attacks": [{"aatyp": 2, "adtyp": 6, "damn": 1, "damd": 1}],
                },
            },
        }
        scheduler = ResetOwnedScheduler({"entities": [attacker, defender]}, None)
        attacker, defender = scheduler.entities
        calls: list[tuple[str, int]] = []
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]

        event = scheduler._kitten_attack_grid_bug(
            attacker, defender, defer_after_message=True
        )[0]
        self.assertEqual("The kitten bites the grid bug.", event["message"])
        self.assertEqual("alive", defender["lifecycle"])
        self.assertEqual(1, defender["hp"])
        self.assertEqual([("rnd", 20)], calls)
        self.assertEqual(
            {"kind": "kitten_grid_bug", "attacker_id": 27, "defender_id": 10, "strike": True},
            scheduler.pending_combat_continuation,
        )

        self.assertEqual([], scheduler._resume_combat_continuation())
        self.assertEqual("dead", defender["lifecycle"])
        self.assertEqual(0, defender["hp"])
        self.assertEqual(5, attacker["hp_max"])
        self.assertEqual(
            [("rnd", 20), ("rn2", 6), ("rn2", 10), ("rnd", 1)],
            calls,
        )

    def test_common_m_move_opens_only_source_joined_closed_door(self) -> None:
        scheduler = ResetOwnedScheduler(
            {"entities": []},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
        )
        terrain = [[1] * 79 for _ in range(21)]
        flags = [[0] * 79 for _ in range(21)]
        terrain[10][10] = 24
        terrain[10][11] = 22
        flags[10][11] = 4  # D_CLOSED
        entity = {
            "species_id": 235,
            "species_rules": {
                "branch_profile": "target_or_wander_special",
                "capabilities": {"no_hands": False, "very_small": False, "stalk": True},
            },
            "allegiance": "hostile",
            "x": 10,
            "y": 10,
            "path_state": {
                "status": {"can_see": True},
                "apparent_hero_native": {"x": 1, "y": 1},
                "mtrack_native": [{"x": 0, "y": 0}] * 4,
            },
        }
        scheduler._rn2 = lambda bound: 0  # type: ignore[method-assign]
        result = scheduler._simple_monster_move(
            entity,
            (20, 20),
            {
                "terrain_type": terrain,
                "terrain_flags": flags,
                "terrain_horizontal": [[False] * 79 for _ in range(21)],
            },
            set(),
        )
        self.assertEqual({"x": 11, "y": 10}, result["to"])
        self.assertEqual(2, flags[10][11])
        self.assertEqual("You hear a door open.", result["door_events"][0]["message"])

    def test_reset_player_inventory_is_preserved_as_source_ordered_surface(self) -> None:
        reset = projection(0)
        reset["player_inventory"] = [
            {"object_id": 1, "object_type": 37, "object_class": 2, "inventory_letter": "a", "quantity": 1, "spe": 1, "artifact": 0, "worn_mask": 0},
            {"object_id": 2, "object_type": 17, "object_class": 2, "inventory_letter": "b", "quantity": 1, "spe": 0, "artifact": 0, "worn_mask": 0},
        ]
        scheduler = ResetOwnedScheduler(reset, None)
        self.assertEqual([1, 2], [item["object_id"] for item in scheduler.player_inventory])

    def test_movemon_is_repeated_queue_ordered_passes(self) -> None:
        scheduler = ResetOwnedScheduler(projection(24, 12, 0), None)
        passes = scheduler.drain_eligible_passes()
        self.assertEqual(
            [(0, 1, 24, 12), (0, 2, 12, 0), (1, 1, 12, 0)],
            [
                (
                    item["pass_index"],
                    item["entity_id"],
                    item["movement_points_before"],
                    item["movement_points_after"],
                )
                for item in passes
            ],
        )
        self.assertTrue(all(item["destination_selected"] is False for item in passes))
        self.assertEqual([0, 0, 0], [entity["scheduler"]["movement_points"] for entity in scheduler.entities])

    def test_consume_time_allocates_after_all_existing_passes(self) -> None:
        scheduler = ResetOwnedScheduler(projection(24, 12), None)
        result = scheduler.consume_time()
        self.assertEqual(1, result["turn"])
        self.assertEqual([1, 2, 1], [item["entity_id"] for item in result["passes"]])
        self.assertEqual([12, 12], [item["movement_points"] for item in result["allocation"]["allocated"]])
        self.assertEqual([12, 12], [entity["scheduler"]["movement_points"] for entity in scheduler.entities])

    def test_snapshot_round_trip_preserves_queue_accounting(self) -> None:
        scheduler = ResetOwnedScheduler(projection(12, 0), None)
        scheduler.consume_time()
        restored = ResetOwnedScheduler.from_snapshot(scheduler.snapshot())
        self.assertEqual(scheduler.snapshot(), restored.snapshot())

    def test_snapshot_round_trip_preserves_reset_inventory_surface(self) -> None:
        reset = projection(0)
        reset["player_inventory"] = [
            {
                "object_id": 11,
                "object_type": 37,
                "object_class": 2,
                "inventory_letter": "a",
                "quantity": 1,
                "spe": 1,
                "artifact": 0,
                "worn_mask": 0,
            }
        ]
        scheduler = ResetOwnedScheduler(reset, None)
        restored = ResetOwnedScheduler.from_snapshot(scheduler.snapshot())
        self.assertEqual(scheduler.player_inventory, restored.player_inventory)
        self.assertEqual(scheduler.snapshot(), restored.snapshot())

    def test_open_door_is_a_source_legal_pet_candidate_but_closed_door_is_not(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        reset_map["terrain_type"][10][10] = 22
        self.assertTrue(scheduler._pet_cell_walkable(reset_map, 10, 10))
        reset_map["terrain_flags"][10][10] = 4
        self.assertFalse(scheduler._pet_cell_walkable(reset_map, 10, 10))

    def test_mfndpos_rejects_non_swimming_pool_lava_bars_and_rock_types(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        for terrain_type in (0, 15, 16, 17, 18, 19, 20, 21):
            reset_map["terrain_type"][10][10] = terrain_type
            self.assertFalse(scheduler._pet_cell_walkable(reset_map, 10, 10), terrain_type)
        reset_map["terrain_type"][10][10] = 23
        self.assertTrue(scheduler._pet_cell_walkable(reset_map, 10, 10))

    def test_source_candidate_order_excludes_hero_and_occupied_cells(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        entity = {"x": 10, "y": 10}
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        self.assertEqual(
            [(9, 10), (9, 11), (10, 9), (10, 11), (11, 9), (11, 10), (11, 11)],
            scheduler._pet_candidate_cells(entity, (10, 10), reset_map, {(9, 9)}),
        )

    def test_mfndpos_rejects_boulder_without_allow_rock(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        entity = {"x": 10, "y": 10}
        candidates = scheduler._pet_candidate_cells(
            entity,
            (0, 0),
            reset_map,
            set(),
            [{"x": 11, "y": 10, "objects": [{"object_type": 447}]}],
        )
        self.assertNotIn((11, 10), candidates)

    def test_source_candidate_order_blocks_diagonal_unbroken_door(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        entity = {"x": 10, "y": 10}
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
        }
        reset_map["terrain_type"][10][10] = 22
        reset_map["terrain_flags"][10][10] = 4
        self.assertNotIn((9, 9), scheduler._pet_candidate_cells(entity, (0, 0), reset_map, set()))

    def test_malformed_inventory_checkpoint_fails_closed(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), None)
        snapshot = scheduler.snapshot()
        snapshot["player_inventory"] = [{"object_id": 1, "inventory_letter": "a"}]
        with self.assertRaisesRegex(ValueError, "player_inventory entry"):
            ResetOwnedScheduler.from_snapshot(snapshot)

    def test_source_time_consumes_spawn_before_dosounds_and_engraving(self) -> None:
        scheduler = ResetOwnedScheduler(
            {
                "source_turn": 1,
                "entities": [{"entity_id": 23, "scheduler": {"base_speed": 12, "movement_points": 0}}],
            },
            {
                "lanes": {
                    "core": {"state_hex": ("00" * 4128)},
                },
            },
        )
        bounds: list[int] = []
        scheduler._rn2 = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        reset_map = {"level_flags": level_flags()}
        result = scheduler.consume_source_time(hero=(10, 10), reset_map=reset_map, engraving_bound=85)
        self.assertEqual([12, 70, 85], bounds)
        self.assertEqual(1, result["post_draws"]["spawn_70"])
        self.assertEqual(1, result["post_draws"]["engraving_roll"])

    def test_source_newt_spawn_receipt_is_exact_and_allocates_queue_head(self) -> None:
        terrain = [[23] * 79 for _ in range(21)]
        terrain[15][16] = 0  # first native candidate (17,15) is rejected
        reset_map = {
            "terrain_type": terrain,
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        entities = [
            {
                "entity_id": entity_id,
                "species_id": 32,
                "lifecycle": "alive",
                "x": entity_id,
                "y": 4,
                "scheduler": {"iteration_order": order, "base_speed": 12, "movement_points": 0},
            }
            for order, entity_id in enumerate((27, 15, 13, 12, 9))
        ]
        scheduler = ResetOwnedScheduler({"entities": entities}, None)
        rn2_values = iter((15, 15, 28, 7, 1, 1, 37, 72))
        rnd_values = iter((19, 4, 1))
        scheduler._rn2 = lambda bound: next(rn2_values)  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: next(rnd_values)  # type: ignore[method-assign]

        receipt = scheduler._spawn_source_monster(reset_map)

        self.assertEqual(
            {
                "entity_id": 28,
                "species_id": 318,
                "native_x": 30,
                "native_y": 7,
                "x": 29,
                "y": 7,
                "hp": 4,
                "rndmonst_choice": 19,
                "source_profile": "mons[PM_NEWT]",
            },
            {key: receipt[key] for key in ("entity_id", "species_id", "native_x", "native_y", "x", "y", "hp", "rndmonst_choice", "source_profile")},
        )
        self.assertEqual([28, 27, 15, 13, 12, 9], [entity["entity_id"] for entity in scheduler.entities])
        self.assertEqual([0, 1, 2, 3, 4, 5], [entity["scheduler"]["iteration_order"] for entity in scheduler.entities])

    def test_source_seed27_newt_spawn_receipt_is_exact_and_map_bound(self) -> None:
        terrain = [[0] * 79 for _ in range(21)]
        terrain[13][17] = 24  # native (18,13), the fourth accepted candidate
        reset_map = {
            "terrain_type": terrain,
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        entities = [
            {
                "entity_id": entity_id,
                "species_id": 318 if entity_id == 29 else 16,
                "lifecycle": "alive",
                "x": 0,
                "y": 0,
                "scheduler": {"iteration_order": order, "base_speed": 12, "movement_points": 0},
            }
            for order, entity_id in enumerate((49, 29, 17, 12, 9, 8))
        ]
        scheduler = ResetOwnedScheduler({"entities": entities}, None)
        position_values = iter((4, 6, 47, 14, 74, 19, 16, 13))
        init_values = iter((0, 33, 39, 68))
        scheduler._rn2 = lambda bound: next(position_values) if bound in (77, 21) else next(init_values)  # type: ignore[method-assign]
        rnd_values = iter((21, 2))
        scheduler._rnd = lambda bound: next(rnd_values)  # type: ignore[method-assign]
        receipt = scheduler._spawn_source_monster(reset_map)

        self.assertEqual(
            {
                "entity_id": 50,
                "species_id": 318,
                "native_x": 18,
                "native_y": 13,
                "x": 17,
                "y": 13,
                "hp": 2,
                "rndmonst_choice": 21,
                "source_profile": "mons[PM_NEWT]",
            },
            {key: receipt[key] for key in ("entity_id", "species_id", "native_x", "native_y", "x", "y", "hp", "rndmonst_choice", "source_profile")},
        )
        self.assertEqual([50, 49, 29, 17, 12, 9, 8], [entity["entity_id"] for entity in scheduler.entities])

        # The receipt is map-bound: changing only the selected terrain class
        # must reject the same RNG wheel rather than silently spawning there.
        bad_scheduler = ResetOwnedScheduler({"entities": entities}, None)
        bad_values = iter((4, 6, 47, 14, 74, 19, 16, 13, 0, 33, 39, 68))
        bad_scheduler._rn2 = lambda bound: next(bad_values)  # type: ignore[method-assign]
        bad_rnd = iter((21, 2))
        bad_scheduler._rnd = lambda bound: next(bad_rnd)  # type: ignore[method-assign]
        bad_map = {**reset_map, "terrain_type": [row[:] for row in terrain]}
        bad_map["terrain_type"][13][17] = 23
        with self.assertRaisesRegex(ValueError, "unexpected terrain type"):
            bad_scheduler._spawn_source_monster(bad_map)

    def test_source_grid_bug_spawn_receipt_is_exact_and_source_bound(self) -> None:
        raw_pairs = [
            (2, 14), (69, 17), (33, 2), (10, 3), (70, 13),
            (57, 7), (20, 9), (73, 1), (57, 20), (8, 19),
            (60, 6), (38, 3), (44, 11), (4, 13), (28, 1),
            (12, 18), (25, 13), (74, 1), (37, 3), (17, 13),
        ]
        terrain = [[23] * 79 for _ in range(21)]
        for raw_x, raw_y in raw_pairs[:-1]:
            terrain[raw_y][raw_x + 1] = 0
        terrain[13][18] = 22
        reset_map = {
            "terrain_type": terrain,
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        entities = [
            {
                "entity_id": entity_id,
                "species_id": 32,
                "lifecycle": "alive",
                "x": entity_id,
                "y": 4,
                "scheduler": {"iteration_order": order, "base_speed": 12, "movement_points": 0},
            }
            for order, entity_id in enumerate((40, 24, 15, 11))
        ]
        scheduler = ResetOwnedScheduler({"entities": entities}, None)
        iter_rn2 = iter([value for pair in raw_pairs for value in pair] + [1, 0, 31, 89, 74])
        scheduler._rn2 = lambda bound: next(iter_rn2)  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: next(iter_rnd)  # type: ignore[method-assign]
        iter_rnd = iter([2, 2])

        receipt = scheduler._spawn_source_monster(reset_map)

        self.assertEqual(
            {
                "entity_id": 41,
                "species_id": 115,
                "native_x": 19,
                "native_y": 13,
                "x": 18,
                "y": 13,
                "hp": 2,
                "rndmonst_choice": 2,
                "source_profile": "mons[PM_GRID_BUG]",
            },
            {key: receipt[key] for key in ("entity_id", "species_id", "native_x", "native_y", "x", "y", "hp", "rndmonst_choice", "source_profile")},
        )
        self.assertEqual([41, 40, 24, 15, 11], [entity["entity_id"] for entity in scheduler.entities])

    def test_newt_spawn_turn_consumes_fountain_but_omits_engraving_gate(self) -> None:
        entities = [
            {
                "entity_id": entity_id,
                "species_id": 318 if entity_id == 28 else 32,
                "x": 29 if entity_id == 28 else 0,
                "y": 7 if entity_id == 28 else 0,
                "lifecycle": "alive",
                "scheduler": {"base_speed": 6 if entity_id == 28 else 12, "movement_points": 0, "iteration_order": order},
            }
            for order, entity_id in enumerate((28, 27, 15, 13, 12, 9))
        ]
        scheduler = ResetOwnedScheduler(
            {"source_turn": 1, "entities": entities},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
        )
        scheduler.dynamic_turns = 15
        calls: list[tuple[str, int]] = []

        def rn2(bound: int) -> int:
            calls.append(("rn2", bound))
            return 0 if bound == 70 else 1

        scheduler._rn2 = rn2  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        scheduler._spawn_source_monster = lambda reset_map, hero=None: {  # type: ignore[method-assign]
            "entity_id": 28,
            "species_id": 318,
            "native_x": 30,
            "native_y": 7,
        }

        result = scheduler._finish_source_time(
            reset_map={
                "terrain_type": [[23] * 79 for _ in range(21)],
                "terrain_flags": [[0] * 79 for _ in range(21)],
                "level_flags": level_flags(nfountains=1),
            },
            hero=(0, 0),
            engraving_bound=73,
            exercise_rn2_bound=None,
            passes=[],
            combat_events=[],
            door_events=[],
            object_events=[],
        )

        self.assertEqual({"fountains_400": 1}, result["post_draws"]["sounds_gates"])
        self.assertIsNone(result["post_draws"]["engraving_roll"])
        self.assertNotIn(("rn2", 73), calls)

    def test_source_grid_bug_spawn_receipt_is_exact_and_uses_terrain22(self) -> None:
        terrain = [[0] * 79 for _ in range(21)]
        terrain[13][18] = 22  # final native candidate (19,13) is accepted
        reset_map = {
            "terrain_type": terrain,
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        native_attempts = (
            (4, 14), (71, 17), (35, 2), (12, 3), (72, 13),
            (59, 7), (22, 9), (75, 1), (59, 20), (10, 19),
            (62, 6), (40, 3), (46, 11), (6, 13), (30, 1),
            (14, 18), (27, 13), (76, 1), (39, 3), (19, 13),
        )
        rn2_values = iter(value for native_x, native_y in native_attempts for value in (native_x - 2, native_y))
        init_rn2_values = iter((1, 0, 31, 89, 74))
        scheduler = ResetOwnedScheduler(
            {
                "entities": [
                    {
                        "entity_id": entity_id,
                        "species_id": species_id,
                        "lifecycle": "alive",
                        "x": entity_id,
                        "y": 4,
                        "scheduler": {"iteration_order": order, "base_speed": 12, "movement_points": 0},
                    }
                    for order, (entity_id, species_id) in enumerate(((40, 32), (24, 12), (15, 69), (11, 155)))
                ],
            },
            None,
        )
        scheduler._rn2 = lambda bound: next(rn2_values) if bound in (77, 21) else next(init_rn2_values)  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: {2: 2, 4: 2}[bound]  # type: ignore[method-assign]

        receipt = scheduler._spawn_source_monster(reset_map)

        self.assertEqual(
            {
                "entity_id": 41,
                "species_id": 115,
                "native_x": 19,
                "native_y": 13,
                "x": 18,
                "y": 13,
                "hp": 2,
                "rndmonst_choice": 2,
                "rndmonst_choice_count": 2,
                "source_profile": "mons[PM_GRID_BUG]",
            },
            {key: receipt[key] for key in ("entity_id", "species_id", "native_x", "native_y", "x", "y", "hp", "rndmonst_choice", "rndmonst_choice_count", "source_profile")},
        )
        self.assertEqual([41, 40, 24, 15, 11], [entity["entity_id"] for entity in scheduler.entities])
        self.assertEqual([0, 1, 2, 3, 4], [entity["scheduler"]["iteration_order"] for entity in scheduler.entities])

    def test_source_turn_21_spawn_gate_requires_corpse_surface(self) -> None:
        """A clock value alone must not suppress allmain's spawn draw.

        The native corpse-drop tape omits ``rn2(70)`` only after a joined
        kitten/lichen-corpse return.  An unrelated reset population at the
        same ``(source_turn + dynamic_turns, dynamic_turns)`` boundary still
        consumes the ordinary spawn, sound, and engraving gates.
        """

        scheduler = ResetOwnedScheduler(
            {
                "source_turn": 1,
                "entities": [{"entity_id": 23, "scheduler": {"base_speed": 12, "movement_points": 0}}],
            },
            {"lanes": {"core": {"state_hex": ("00" * 4128)}}},
        )
        scheduler.dynamic_turns = 20
        bounds: list[int] = []
        scheduler._rn2 = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        result = scheduler.consume_source_time(
            hero=(10, 10), reset_map={"level_flags": level_flags()}, engraving_bound=85
        )
        self.assertEqual([12, 70, 85], bounds)
        self.assertEqual(1, result["post_draws"]["spawn_70"])

    def test_seed57_route_binds_post_kitten_budget_and_no_spawn_link(self) -> None:
        """The held-out seed-57 clock receipt keeps the gate, not makemon."""
        entities = [
            {
                "entity_id": 33,
                "species_id": 32,
                "lifecycle": "alive",
                "allegiance": "tame",
                "x": 39,
                "y": 6,
                "inventory": [],
                "scheduler": {"base_speed": 18, "movement_points": 0},
                "path_state": {"status": {}, "edog": {}},
            },
            {
                "entity_id": 12,
                "species_id": 318,
                "lifecycle": "alive",
                "x": 45,
                "y": 17,
                "inventory": [],
                "scheduler": {"base_speed": 6, "movement_points": 0},
                "path_state": {"status": {}, "edog": None},
            },
            {
                "entity_id": 9,
                "species_id": 12,
                "lifecycle": "alive",
                "x": 24,
                "y": 6,
                "inventory": [],
                "scheduler": {"base_speed": 12, "movement_points": 0},
                "path_state": {"status": {}, "edog": None},
            },
        ]
        scheduler = ResetOwnedScheduler(
            {"source_turn": 1, "entities": entities, "object_stacks": [], "player_inventory": []},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
            reset_seed=20260757,
        )
        scheduler.dynamic_turns = 3
        scheduler._rn2 = lambda bound: 1  # type: ignore[method-assign]
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
        }
        result = scheduler._finish_source_time(
            reset_map=reset_map,
            hero=(39, 5),
            engraving_bound=85,
            exercise_rn2_bound=None,
            passes=[],
            combat_events=[],
            door_events=[],
            object_events=[],
        )
        self.assertEqual(12, scheduler.entities[0]["scheduler"]["movement_points"])
        self.assertEqual(1, result["post_draws"]["spawn_70"])

        scheduler.dynamic_turns = 4
        scheduler.entities[0]["x"], scheduler.entities[0]["y"] = 40, 6
        result = scheduler._finish_source_time(
            reset_map=reset_map,
            hero=(39, 5),
            engraving_bound=85,
            exercise_rn2_bound=None,
            passes=[],
            combat_events=[],
            door_events=[],
            object_events=[],
        )
        self.assertEqual(1, result["post_draws"]["spawn_70"])
        self.assertIsNone(result["post_draws"]["spawn"])

    def test_seed53_dog_route_binds_post_turn_budget_and_track(self) -> None:
        """The held-out dog route keeps source allocation state exact."""

        def finish(dynamic_turns: int, x: int, y: int) -> ResetOwnedScheduler:
            scheduler = ResetOwnedScheduler(
                {
                    "source_turn": 1,
                    "entities": [
                        {
                            "entity_id": 43,
                            "species_id": 16,
                            "lifecycle": "alive",
                            "allegiance": "tame",
                            "x": x,
                            "y": y,
                            "inventory": [],
                            "scheduler": {"base_speed": 18, "movement_points": 0},
                            "path_state": {
                                "status": {},
                                "edog": {},
                                "mtrack_native": [
                                    {"x": 64, "y": 12},
                                    {"x": 64, "y": 13},
                                    {"x": 0, "y": 0},
                                    {"x": 0, "y": 0},
                                ],
                            },
                        }
                    ],
                    "object_stacks": [],
                    "player_inventory": [],
                },
                {"lanes": {"core": {"state_hex": "00" * 4128}}},
                reset_seed=20260753,
            )
            scheduler.dynamic_turns = dynamic_turns
            scheduler._rn2 = lambda bound: 1  # type: ignore[method-assign]
            scheduler._finish_source_time(
                reset_map={
                    "level_flags": level_flags(),
                    "terrain_type": [[24] * 79 for _ in range(21)],
                    "terrain_flags": [[0] * 79 for _ in range(21)],
                },
                hero=(62, 12),
                engraving_bound=85,
                exercise_rn2_bound=None,
                passes=[],
                combat_events=[],
                door_events=[],
                object_events=[],
            )
            return scheduler

        scheduler = finish(5, 63, 13)
        self.assertEqual(12, scheduler.entities[0]["scheduler"]["movement_points"])

        scheduler = finish(6, 63, 12)
        self.assertEqual(12, scheduler.entities[0]["scheduler"]["movement_points"])

        scheduler = finish(8, 62, 11)
        self.assertEqual(24, scheduler.entities[0]["scheduler"]["movement_points"])
        self.assertEqual(
            [
                {"x": 62, "y": 11},
                {"x": 63, "y": 11},
                {"x": 64, "y": 12},
                {"x": 64, "y": 13},
            ],
            scheduler.entities[0]["path_state"]["mtrack_native"],
        )

    def test_seed55_kick_potion_receipt_round_trips_through_kitten_inventory(self) -> None:
        """The KICK route owns the potion pickup and the later source drop."""
        entity = {
            "entity_id": 42,
            "species_id": 32,
            "species_rules": {
                "branch_profile": "dog_move_domestic",
                "capabilities": {"swim": False, "likes_lava": False, "throws_rocks": False},
            },
            "allegiance": "tame",
            "x": 13,
            "y": 4,
            "underlay": {"terrain_type": 24},
            "inventory": [],
            "scheduler": {"base_speed": 18, "movement_points": 12, "can_move": True},
            "path_state": {
                "status": {"can_see": True, "leashed": False},
                "edog": {"apport": 10, "whistletime": 0, "dropdist": 10000, "droptime": 0},
                "mtrack_native": [
                    {"x": 14, "y": 4},
                    {"x": 0, "y": 0},
                    {"x": 0, "y": 0},
                    {"x": 0, "y": 0},
                ],
            },
        }
        potion = {
            "object_id": 14,
            "object_type": 297,
            "object_class": 8,
            "quantity": 1,
            "cursed": False,
            "artifact": 0,
            "age": 1,
            "corpsenm": 0,
            "bitfield_hex": "100000000000",
            "source_order": 15,
        }
        gold = {
            "object_id": 13,
            "object_type": 410,
            "object_class": 12,
            "quantity": 5,
            "cursed": False,
            "artifact": 0,
            "age": 1,
            "corpsenm": -1,
            "bitfield_hex": "100000000000",
            "source_order": 16,
        }
        reset_map = {
            "level_flags": level_flags(),
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "terrain_horizontal": [[False] * 79 for _ in range(21)],
            "terrain_lit": [[True] * 79 for _ in range(21)],
            "traps": [],
        }
        pickup_scheduler = ResetOwnedScheduler(
            {
                "source_turn": 1,
                "entities": [entity],
                "object_stacks": [{"x": 13, "y": 4, "objects": [potion, gold]}],
                "player_inventory": [],
            },
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
            reset_seed=20260755,
        )
        pickup_scheduler.dynamic_turns = 3
        pickup_scheduler._active_pass_index = 1
        pickup_scheduler._rn2 = lambda bound: 0  # type: ignore[method-assign]
        pickup_events: list[dict[str, object]] = []
        pickup_scheduler._kitten_move(
            pickup_scheduler.entities[0],
            (13, 6),
            reset_map,
            set(),
            object_events=pickup_events,
        )
        self.assertEqual([14], [item["object_id"] for item in pickup_scheduler.entities[0]["inventory"]])
        self.assertEqual([], pickup_scheduler.object_stacks[0]["objects"])
        self.assertEqual("The kitten picks up a potion.", pickup_events[0]["message"])
        self.assertTrue(pickup_events[0]["suppress_message"])

        drop_entity = pickup_scheduler.entities[0]
        drop_entity["x"], drop_entity["y"] = 13, 5
        drop_scheduler = ResetOwnedScheduler(
            {"source_turn": 1, "entities": [drop_entity], "object_stacks": [], "player_inventory": []},
            {"lanes": {"core": {"state_hex": "00" * 4128}}},
            reset_seed=20260755,
        )
        drop_scheduler.dynamic_turns = 4
        drop_scheduler._active_pass_index = 0
        drop_scheduler._rn2 = lambda bound: 0  # type: ignore[method-assign]
        drop_events: list[dict[str, object]] = []
        drop_scheduler._kitten_move(
            drop_scheduler.entities[0],
            (13, 6),
            reset_map,
            set(),
            object_events=drop_events,
        )
        self.assertEqual([], drop_scheduler.entities[0]["inventory"])
        self.assertEqual("The kitten drops a potion.", drop_events[0]["message"])
        self.assertEqual(0, drop_scheduler.dynamic_object_stacks[0]["objects"][0]["source_order"])

    def test_fountain_sound_gate_consumes_its_source_message_draw(self) -> None:
        scheduler = ResetOwnedScheduler(
            {"entities": [{"entity_id": 23, "scheduler": {"base_speed": 12, "movement_points": 0}}]},
            {"lanes": {"core": {"state_hex": ("00" * 4128)}}},
        )
        values = iter((1, 1, 0, 2, 1))
        bounds: list[int] = []
        scheduler._rn2 = lambda bound: bounds.append(bound) or next(values)  # type: ignore[method-assign]
        result = scheduler.consume_source_time(
            hero=(10, 10),
            reset_map={"level_flags": level_flags(nfountains=1)},
        )
        gates = result["post_draws"]["sounds_gates"]
        self.assertEqual("the splashing of a naiad.", gates["fountains_message"])
        self.assertEqual([12, 70, 400, 3, 85], bounds)

    def test_reset_engraving_wipe_consumes_source_bound_before_actor(self) -> None:
        scheduler = ResetOwnedScheduler(projection(0), {"lanes": {"core": {"state_hex": ("00" * 4128)}}})
        bounds: list[int] = []
        scheduler._rn2 = lambda bound: bounds.append(bound) or 1  # type: ignore[method-assign]
        reset_map = {
            "terrain_type": [[24] * 79 for _ in range(21)],
            "terrain_flags": [[0] * 79 for _ in range(21)],
            "engravings": [{"native_x": 11, "y": 10, "engr_type": 4, "engr_time": 0, "engr_lth": 6, "text": "hello"}],
        }
        result = scheduler._wipe_engraving_at(reset_map, 10, 10)
        self.assertEqual({"present": True, "draw": 1, "bound": 26, "engr_type": 4}, result)
        self.assertEqual([26], bounds)


if __name__ == "__main__":
    unittest.main()
