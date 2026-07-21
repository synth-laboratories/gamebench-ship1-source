"""Source-faithful Rogue primitives ported from modern-rogue."""

from __future__ import annotations

from dataclasses import dataclass


MAXROOMS = 9
MAXTHINGS = 9
MAXOBJ = 9
MAXPACK = 23
MAXTRAPS = 10
AMULETLEVEL = 26
NUMTHINGS = 7
MAXPASS = 13
NUMLINES = 24
NUMCOLS = 80
STATLINE = NUMLINES - 1
BORE_LEVEL = 50

PASSAGE = "#"
DOOR = "+"
FLOOR = "."
PLAYER = "@"
TRAP = "^"
STAIRS = "%"
GOLD = "*"
POTION = "!"
SCROLL = "?"
MAGIC = "$"
FOOD = ":"
WEAPON = ")"
ARMOR = "]"
AMULET = ","
RING = "="
STICK = "/"

DIRECTIONS: dict[str, tuple[int, int]] = {
    "h": (0, -1),
    "j": (1, 0),
    "k": (-1, 0),
    "l": (0, 1),
    "y": (-1, -1),
    "u": (-1, 1),
    "b": (1, -1),
    "n": (1, 1),
}


def _i32(value: int) -> int:
    value &= 0xFFFF_FFFF
    if value >= 0x8000_0000:
        value -= 0x1_0000_0000
    return value


def c_div(numerator: int, denominator: int) -> int:
    """C integer division truncates toward zero."""

    if denominator == 0:
        raise ZeroDivisionError("division by zero")
    sign = -1 if (numerator < 0) ^ (denominator < 0) else 1
    return sign * (abs(numerator) // abs(denominator))


@dataclass
class RogueRng:
    """Rogue RN macro and helpers from extern.h/main.c."""

    seed: int

    def __post_init__(self) -> None:
        self.seed = _i32(self.seed)

    def rn(self) -> int:
        self.seed = _i32((self.seed * 11109) + 13849)
        return (self.seed >> 16) & 0xFFFF

    def rnd(self, range_: int) -> int:
        return 0 if range_ == 0 else abs(self.rn()) % range_

    def roll(self, number: int, sides: int) -> int:
        total = 0
        while number > 0:
            total += self.rnd(sides) + 1
            number -= 1
        return total

    def spread(self, nm: int) -> int:
        return nm - c_div(nm, 20) + self.rnd(c_div(nm, 10))

    def gold_calc(self, level: int) -> int:
        return self.rnd(50 + 10 * level) + 2


def direction_delta(ch: str) -> tuple[int, int] | None:
    if len(ch) != 1:
        return None
    return DIRECTIONS.get(ch.lower())


def command_move_delta(ch: str) -> tuple[int, int] | None:
    return DIRECTIONS.get(ch)


def step_ok(ch: str) -> bool:
    if ch in {" ", "|", "-"}:
        return False
    return not _is_ascii_alpha(ch)


def _is_ascii_alpha(ch: str) -> bool:
    return len(ch) == 1 and (("A" <= ch <= "Z") or ("a" <= ch <= "z"))
