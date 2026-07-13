"""Canonical Overcooked v2 layout catalog (Overcooked-AI + OvercookedV2 benchmark maps)."""

from __future__ import annotations

from typing import Any


def _convert_ascii(rows: list[str]) -> list[str]:
    mapping = {"W": "#", "X": "S", "B": "D"}
    converted: list[str] = []
    for row in rows:
        converted.append("".join(mapping.get(char, char) for char in row))
    return converted


LAYOUT_SPECS: dict[str, dict[str, Any]] = {
    "cramped_room": {
        "ascii": _convert_ascii(["WWPWW", "OA AO", "W W", "WBWXW"]),
        "possible_recipes": [[0, 0, 0]],
        "recipe_pool": ["trio_soup"],
        "swap_agents": True,
    },
    "asymm_advantages": {
        "ascii": _convert_ascii(["WWWWWWWWW", "O WXWOW X", "W P W", "W A PA W", "WWWBWBWWW"]),
        "possible_recipes": [[0, 0, 0]],
        "recipe_pool": ["trio_soup"],
    },
    "coord_ring": {
        "ascii": _convert_ascii(["WWWPW", "W A P", "BAW W", "O W", "WOXWW"]),
        "possible_recipes": [[0, 0, 0]],
        "recipe_pool": ["trio_soup"],
    },
    "forced_coord": {
        "ascii": _convert_ascii(["WWWPW", "O WAP", "OAW W", "B W W", "WWWXW"]),
        "possible_recipes": [[0, 0, 0]],
        "recipe_pool": ["trio_soup"],
    },
    "counter_circuit": {
        "ascii": _convert_ascii(["WWWPPWWW", "W A W", "B WWWW X", "W AW", "WWWOOWWW"]),
        "possible_recipes": [[0, 0, 0]],
        "recipe_pool": ["trio_soup"],
        "swap_agents": True,
    },
    "cramped_room_v2": {
        "ascii": _convert_ascii(["WWPWW", "0A A1", "W R", "WBWXW"]),
    },
    "asymm_advantages_recipes_center": {
        "ascii": _convert_ascii(["WWWWWWWWW", "0 WXR01 X", "1 P W", "W A PA W", "WWWBWBWWW"]),
    },
    "asymm_advantages_recipes_right": {
        "ascii": _convert_ascii(["WWWWWWWWW", "0 WXW01 X", "1 P R", "W A PA W", "WWWBWBWWW"]),
    },
    "asymm_advantages_recipes_left": {
        "ascii": _convert_ascii(["WWWWWWWWW", "0 WXW01 X", "1 P R", "R A PA W", "WWWBWBWWW"]),
    },
    "two_rooms": {
        "ascii": _convert_ascii(["WWWWWB10W", "W W R", "P A W A W", "W W X", "WWWWWWWWW"]),
    },
    "two_rooms_both": {
        "ascii": _convert_ascii(["W01BWB10W", "W W R", "P A W A W", "W W X", "WWWWWWWWW"]),
    },
    "long_room": {
        "ascii": _convert_ascii(["WWWWWWWWWWWWWWW", "B AP", "0 X", "WWWWWWWWWWWWWWW"]),
        "possible_recipes": [[0, 0, 0]],
        "recipe_pool": ["trio_soup"],
    },
    "more_fun_coordination": {
        "ascii": _convert_ascii(["WWWWWWWWW", "W X W", "RA P A1", "0 P 2", "W B W", "WWWWWWWWW"]),
        "possible_recipes": [[0, 1, 1], [0, 2, 2]],
        "recipe_pool": ["mixed_soup", "more_fun_coord_1"],
    },
    "fun_symmetries_plates": {
        "ascii": _convert_ascii(["WWWWWWW", "B W 0", "R APA X", "B W 1", "WWWWWWW"]),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "fun_symmetries": {
        "ascii": _convert_ascii(["WWWWBWW", "2 W 0", "R APA X", "2 W 1", "WWWWBWW"]),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "fun_symmetries1": {
        "ascii": _convert_ascii(["WWWWWBWW", "2 WW 0", "R AWPA X", "2 WW 1", "WWWWWBWW"]),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "grounded_coord_ring": {
        "ascii": _convert_ascii(
            [
                "WWW2R2WWW",
                "W W",
                "W WWLWW W",
                "2 0 B 2",
                "RAXAP X R",
                "2 1 B 2",
                "W WWLWW W",
                "W W",
                "WWW2R2WWW",
            ]
        ),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "test_time_simple": {
        "ascii": _convert_ascii(["WW2WWWWW", "W WB 0", "R AWPA X", "W WB 1", "WW2WWWWW"]),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "test_time_wide": {
        "ascii": _convert_ascii(["WWXBWW", "0 A 0", "1 1", "WPWPWW", "3 A 3", "W W", "WWRWWW"]),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "demo_cook_simple": {
        "ascii": _convert_ascii(["WWWWWR2W0WW", "0 W B", "W APA X", "1 W B", "WWWWWR2W1WW"]),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
    "demo_cook_wide": {
        "ascii": _convert_ascii(
            ["WWWWBXBWWWW", "WWW0 A 1WWW", "WWWWWPWWWWW", "W A W", "0 W3R3W 0", "W1WWWWWWW1W"]
        ),
        "possible_recipes": [[0, 0, 0], [1, 1, 1]],
        "recipe_pool": ["trio_soup", "tomato_trio"],
    },
}
