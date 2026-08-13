"""Pinned NLE 0.9.0 ``specials`` observation contract.

``specials`` is not a private NetHack state dump.  It is the ``unsigned
char`` mapglyph special-return plane (``ROWNO × (COLNO - 1)``) exposed by
NLE's public API.  These constants are pinned from NLE v0.9.0 source commit
``2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa`` ``include/hack.h``.

Gold can derive ``MG_PET`` from a materialized visible pet, and may also carry
an optional exact ``special`` byte attached to a reset-only presentation
overlay.  That byte is a copied public reset plane, not a glyph inference or
future state.  Unsupported bits remain unjudgeable once the overlay expires.
"""

from __future__ import annotations

from typing import Any, Iterable


MG_CORPSE = 0x01
MG_INVIS = 0x02
MG_DETECT = 0x04
MG_PET = 0x08
MG_RIDDEN = 0x10
MG_STATUE = 0x20
MG_OBJPILE = 0x40
MG_BW_LAVA = 0x80

ALL_SPECIAL_BITS = (
    MG_CORPSE
    | MG_INVIS
    | MG_DETECT
    | MG_PET
    | MG_RIDDEN
    | MG_STATUE
    | MG_OBJPILE
    | MG_BW_LAVA
)
DERIVABLE_SPECIAL_BITS = MG_PET
UNSUPPORTED_SPECIAL_BITS = ALL_SPECIAL_BITS & ~DERIVABLE_SPECIAL_BITS
SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"


def zero_specials(height: int, width: int) -> list[list[int]]:
    """Return a complete NLE-shaped all-zero special plane."""

    return [[0] * width for _ in range(height)]


def pet_specials(
    seen: list[list[bool]],
    monsters: Iterable[dict[str, Any]],
    *,
    height: int,
    width: int,
) -> list[list[int]]:
    """Render only the source-proven, causal ``MG_PET`` subset.

    A pet bit attaches to the presented pet glyph.  An unseen monster is not
    a displayed map glyph and gets no bit.  If multiple materialized monsters
    occupy one cell, no precedence is invented: the visible pet bit is set
    only when a pet is actually the top-level rendered monster in both gold
    lanes' existing model.
    """

    plane = zero_specials(height, width)
    occupied: dict[tuple[int, int], dict[str, Any]] = {}
    for monster in monsters:
        position = monster.get("position", {})
        if not isinstance(position, dict):
            continue
        x, y = position.get("x"), position.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x < width and 0 <= y < height):
            continue
        # Match the established renderer: later monsters overwrite earlier
        # presentation at a shared coordinate.
        occupied[(x, y)] = monster
    for (x, y), monster in occupied.items():
        if y < len(seen) and x < len(seen[y]) and bool(seen[y][x]) and bool(monster.get("pet", False)):
            plane[y][x] = MG_PET
    return plane


def reset_overlay_specials(
    seen: list[list[bool]],
    overlays: Iterable[dict[str, Any]],
    *,
    height: int,
    width: int,
) -> list[list[int]]:
    """Render exact reset-time mapglyph bits attached to a captured pixel.

    This is deliberately presentation-only: the optional ``special`` byte is
    copied from NLE's reset observation and is never inferred from a glyph or
    used for collision, pickup, scheduling, or future frames.  Older captures
    omit it and therefore retain the all-zero fallback.
    """

    plane = zero_specials(height, width)
    for overlay in overlays:
        if not isinstance(overlay, dict) or type(overlay.get("special")) is not int:
            continue
        x, y = overlay.get("x"), overlay.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x < width and 0 <= y < height):
            continue
        if y < len(seen) and x < len(seen[y]) and bool(seen[y][x]):
            plane[y][x] = int(overlay["special"]) & 0xFF
    return plane


def unsupported_bits(value: int) -> int:
    """Return non-PET source bits that gold must not claim to derive."""

    return int(value) & UNSUPPORTED_SPECIAL_BITS
