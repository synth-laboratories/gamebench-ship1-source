import unittest
from copy import deepcopy

from scripts.nle_native_entities import EXPECTED_BINARY_SHA256
from scripts.nle_native_entities import SOURCE_COMMIT
from scripts.oracle_tape import sha256_json
from scripts.portable_reset_map import portable_reset_map_projection
from scripts.portable_reset_map import reset_map_surface
from scripts.portable_reset_map import validate_portable_reset_map_projection
from shared.task_resolve import normalise_level_dump
from gold_python.engine import NethackDlvl1Engine


def source_map():
    return {
        "schema": "gamebench.nethack.native_map_fov_snapshot.v1",
        "binary_sha256": EXPECTED_BINARY_SHA256,
        "source_export_eligible": True,
        "gold_implementation_eligible": False,
        "full_map_terrain": [[0] * 79 for _ in range(21)],
        "full_map_terrain_flags": [[0] * 79 for _ in range(21)],
        "full_map_terrain_horizontal": [[False] * 79 for _ in range(21)],
    }


def dynamic_blockers(*, boulder: tuple[int, int] | None = None, mimic: tuple[int, int] | None = None):
    planes = {
        name: [[False] * 79 for _ in range(21)]
        for name in ("boulder", "visible_mimic", "effective")
    }
    records = []
    if boulder is not None:
        x, y = boulder
        planes["boulder"][y][x] = True
        records.append({"kind": "boulder", "x": x, "y": y, "native_x": x + 1, "object_id": 1, "object_type": 447})
    if mimic is not None:
        x, y = mimic
        planes["visible_mimic"][y][x] = True
        records.append({"kind": "mimic", "x": x, "y": y, "native_x": x + 1, "monster_id": 2, "appearance_type": 1, "mappearance": 1, "invisible": False, "see_invisible": False})
    for y in range(21):
        for x in range(79):
            planes["effective"][y][x] = planes["boulder"][y][x] or planes["visible_mimic"][y][x]
    return {**planes, "records": records}


class PortableResetMapTests(unittest.TestCase):
    def test_projection_is_reset_bound_and_pointer_free(self):
        projection = portable_reset_map_projection(source_map())
        self.assertEqual(projection["source_commit"], SOURCE_COMMIT)
        self.assertEqual(projection["capture_boundary"], {"kind": "reset", "action_step": 0, "before_action_step": 1})
        self.assertEqual(validate_portable_reset_map_projection(projection), [])

    def test_optional_lighting_extension_is_reset_bound_and_complete(self):
        source = source_map()
        source["lighting"] = {
            "static_lit": [[True] * 79 for _ in range(21)],
            "remembered_lit": [[False] * 79 for _ in range(21)],
        }
        source["vision_decision_inputs"] = {"hero": {"night_vision_range": 1}}
        projection = portable_reset_map_projection(source)
        self.assertEqual(projection["night_vision_range"], 1)
        self.assertEqual(validate_portable_reset_map_projection(projection), [])
        projection.pop("terrain_waslit")
        self.assertTrue(any("lighting extension" in failure for failure in validate_portable_reset_map_projection(projection)))

    def test_dynamic_blocker_extension_is_identity_bound_and_fail_closed(self):
        source = source_map()
        source["dynamic_vision_blockers"] = dynamic_blockers(boulder=(7, 4))
        projection = portable_reset_map_projection(source)
        blockers = projection["dynamic_vision_blockers"]
        self.assertEqual([], validate_portable_reset_map_projection(projection))
        self.assertTrue(blockers["boulder"][4][7])
        self.assertEqual({"kind": "boulder", "x": 7, "y": 4, "native_x": 8, "object_id": 1, "object_type": 447}, blockers["records"][0])

        malformed = deepcopy(projection)
        malformed["dynamic_vision_blockers"]["effective"][4][7] = False
        malformed["projection_sha256"] = sha256_json({key: value for key, value in malformed.items() if key != "projection_sha256"})
        self.assertTrue(any("effective plane" in failure for failure in validate_portable_reset_map_projection(malformed)))

        incomplete = deepcopy(projection)
        incomplete["dynamic_vision_blockers"]["records"] = []
        incomplete["projection_sha256"] = sha256_json({key: value for key, value in incomplete.items() if key != "projection_sha256"})
        self.assertTrue(any("records do not cover" in failure for failure in validate_portable_reset_map_projection(incomplete)))

    def test_static_surface_mapping_keeps_doors_flag_driven(self):
        source = source_map()
        source["full_map_terrain"][3][4] = 22
        source["full_map_terrain_flags"][3][4] = 4
        source["full_map_terrain_horizontal"][3][4] = True
        projection = portable_reset_map_projection(source)
        self.assertEqual(reset_map_surface(projection, 4, 3), ("+", 2374))
        projection["terrain_flags"][3][4] = 2
        projection["projection_sha256"] = sha256_json({key: value for key, value in projection.items() if key != "projection_sha256"})
        self.assertEqual(reset_map_surface(projection, 4, 3), ("|", 2373))
        projection["terrain_horizontal"][3][4] = False
        projection["projection_sha256"] = sha256_json({key: value for key, value in projection.items() if key != "projection_sha256"})
        self.assertEqual(reset_map_surface(projection, 4, 3), ("-", 2372))

    def test_stairs_and_ladders_use_source_direction_bit(self):
        source = source_map()
        source["full_map_terrain"][4][5] = 25
        source["full_map_terrain_flags"][4][5] = 1
        projection = portable_reset_map_projection(source)
        self.assertEqual(reset_map_surface(projection, 5, 4), ("<", 2382))
        projection["terrain_flags"][4][5] = 2
        projection["projection_sha256"] = sha256_json({key: value for key, value in projection.items() if key != "projection_sha256"})
        self.assertEqual(reset_map_surface(projection, 5, 4), (">", 2383))
        source["full_map_terrain"][4][5] = 26
        source["full_map_terrain_flags"][4][5] = 1
        ladder = portable_reset_map_projection(source)
        self.assertEqual(reset_map_surface(ladder, 5, 4), ("<", 2384))

    def test_tamper_and_future_fields_fail_closed(self):
        projection = portable_reset_map_projection(source_map())
        projection["terrain_type"][0][0] = 35
        self.assertTrue(any("digest" in failure for failure in validate_portable_reset_map_projection(projection)))
        projection = portable_reset_map_projection(source_map())
        projection["future_frames"] = []
        self.assertTrue(any("prohibited" in failure for failure in validate_portable_reset_map_projection(projection)))

    def test_source_export_must_be_complete(self):
        incomplete = source_map()
        del incomplete["full_map_terrain_flags"]
        with self.assertRaises(ValueError):
            portable_reset_map_projection(incomplete)

    def test_map_survives_task_resolution_and_checkpoint_boundary(self):
        projection = portable_reset_map_projection(source_map())
        terrain = [" " * 79 for _ in range(21)]
        terrain[1] = " " + "@" + " " * 77
        level = normalise_level_dump({"terrain": terrain, "hero": {"x": 1, "y": 1}, "authoritative_reset_map": projection})
        self.assertEqual(projection, level["authoritative_reset_map"])
        engine = NethackDlvl1Engine()
        resolved = {
            "task_id": "map-boundary",
            "fixture_id": "",
            "episode_id": "map-boundary",
            "config_hash": "sha256:test",
            "seed": 1,
            "level_dump": level,
        }
        engine.reset(resolved)
        self.assertEqual((0, 0, False), engine.reset_map_cell(0, 0))
        restored = NethackDlvl1Engine()
        restored.restore_checkpoint(engine.checkpoint_bytes())
        self.assertEqual((0, 0, False), restored.reset_map_cell(0, 0))


if __name__ == "__main__":
    unittest.main()
