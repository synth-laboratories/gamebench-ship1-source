from __future__ import annotations

import unittest

from gold_python.nethack_fov import (
    DOOR,
    D_CLOSED,
    D_ISOPEN,
    blocks_static_light,
    could_see,
    static_clear_plane,
)


def plane(value: int) -> list[list[int]]:
    return [[value] * 79 for _ in range(21)]


class NetHackFovTests(unittest.TestCase):
    def test_source_does_block_static_predicate(self) -> None:
        self.assertTrue(blocks_static_light(0, 0))
        self.assertTrue(blocks_static_light(13, 0))
        self.assertTrue(blocks_static_light(DOOR, D_CLOSED))
        self.assertFalse(blocks_static_light(DOOR, D_ISOPEN))
        self.assertFalse(blocks_static_light(24, 0))

    def test_native_left_boundary_is_not_treated_as_screen_terrain(self) -> None:
        terrain = plane(24)
        flags = plane(0)
        visible = could_see(terrain, flags, 0, 10)
        self.assertTrue(all(visible[y][x] for y in range(21) for x in range(79)))

    def test_blocking_wall_is_visible_but_hides_behind_cell(self) -> None:
        terrain = plane(24)
        flags = plane(0)
        for y in range(21):
            terrain[y][10] = 0
        visible = could_see(terrain, flags, 5, 10)
        self.assertTrue(visible[10][10])
        self.assertFalse(visible[10][11])

    def test_dynamic_blocker_is_a_separate_input(self) -> None:
        terrain = plane(24)
        flags = plane(0)
        no_blocker = could_see(terrain, flags, 5, 10)
        with_blocker = could_see(terrain, flags, 5, 10, dynamic_blockers=((8, 10),))
        self.assertTrue(no_blocker[10][12])
        self.assertFalse(with_blocker[10][12])
        self.assertTrue(with_blocker[10][8])

    def test_static_clear_plane_has_exact_shape(self) -> None:
        clear = static_clear_plane(plane(24), plane(0))
        self.assertEqual((21, 79), (len(clear), len(clear[0])))
        self.assertTrue(all(cell for row in clear for cell in row))


if __name__ == "__main__":
    unittest.main()

