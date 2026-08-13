"""Small, source-shaped implementation of NetHack's Algorithm C vision pass.

This module intentionally models only ``view_from``/``COULD_SEE``.  NetHack's
``vision_recalc`` applies lighting, x-ray/night-vision, boulder/mimic blockers,
and ``seenv``/``IN_SIGHT`` presentation after that pass.  Those inputs are not
part of the portable reset map, so callers must keep this result separate from
the final public-render decision.

The implementation follows the pinned NLE 0.9.0 ``src/vision.c`` Algorithm C:
the contiguous-row pointers are built by ``vision_reset`` and the four
quadrant path tests use the generalized integer Bresenham loops from
``q1_path`` through ``q4_path``.  It is deliberately dependency-free so Rust
can carry the same contract without importing Python or native state.
"""

from __future__ import annotations

from typing import Iterable, Sequence


VIEW_HEIGHT = 21
VIEW_WIDTH = 79

# NetHack 3.6.6 include/rm.h::enum levl_typ_types.
STONE = 0
POOL = 16
MOAT = 17
WATER = 18
CLOUD = 35
DOOR = 22
D_ISOPEN = 2
D_CLOSED = 4
D_LOCKED = 8
D_TRAPPED = 16


def _validate_plane(plane: Sequence[Sequence[object]], *, name: str) -> None:
    if len(plane) != VIEW_HEIGHT or any(len(row) != VIEW_WIDTH for row in plane):
        raise ValueError(f"{name} must be a 21x79 plane")


def blocks_static_light(terrain_type: int, flags: int, *, underwater: bool = False) -> bool:
    """Return the static part of ``src/vision.c::does_block``.

    Objects (boulders), monsters (light-blocking mimics), and dynamic level
    predicates are intentionally not accepted here; they require a separate
    pre-action source contract.
    """

    if type(terrain_type) is not int or type(flags) is not int:
        raise ValueError("terrain type and flags must be integers")
    if terrain_type < POOL:  # IS_ROCK, including trees and secret doors
        return True
    if terrain_type == DOOR:
        return bool(flags & (D_CLOSED | D_LOCKED | D_TRAPPED))
    if terrain_type in {CLOUD, WATER}:
        return True
    if terrain_type == MOAT and underwater:
        return True
    return False


def static_clear_plane(
    terrain_type: Sequence[Sequence[int]],
    terrain_flags: Sequence[Sequence[int]],
    *,
    underwater: bool = False,
    dynamic_blockers: Iterable[tuple[int, int]] = (),
) -> list[list[bool]]:
    """Build the ``viz_clear`` predicate used by ``view_from``."""

    _validate_plane(terrain_type, name="terrain_type")
    _validate_plane(terrain_flags, name="terrain_flags")
    blockers = {(int(x), int(y)) for x, y in dynamic_blockers}
    clear = []
    for y in range(VIEW_HEIGHT):
        row: list[bool] = []
        for x in range(VIEW_WIDTH):
            row.append(
                not blocks_static_light(int(terrain_type[y][x]), int(terrain_flags[y][x]), underwater=underwater)
                and (x, y) not in blockers
            )
        clear.append(row)
    return clear


def _run_tables(clear: Sequence[Sequence[bool]]) -> tuple[list[list[int]], list[list[int]]]:
    """Reproduce ``vision_reset``'s left/right row-pointer construction."""

    if len(clear) != VIEW_HEIGHT or not clear or any(len(row) != len(clear[0]) for row in clear):
        raise ValueError("clear must be a rectangular 21-row plane")
    width = len(clear[0])
    left = [[0] * width for _ in range(VIEW_HEIGHT)]
    right = [[0] * width for _ in range(VIEW_HEIGHT)]
    for y in range(VIEW_HEIGHT):
        dig_left = 0
        block = True  # x=0 is outside the valid level and is always stone.
        for x in range(1, width):
            next_block = not bool(clear[y][x])
            if block != next_block:
                if block:
                    for i in range(dig_left, x):
                        left[y][i] = dig_left
                        right[y][i] = x - 1
                else:
                    i = dig_left
                    if dig_left:
                        dig_left -= 1
                    # The source keeps ``i`` at the first clear-run cell
                    # while moving ``dig_left`` one cell left to include the
                    # preceding boundary in the shadow pointers.
                    for i in range(i, x):
                        left[y][i] = dig_left
                        right[y][i] = x
                dig_left = x
                block = next_block
        i = dig_left
        if not block and dig_left:
            dig_left -= 1
        # As above, the boundary shift changes the pointer value, not the
        # first cell covered by the final run.
        for i in range(i, width):
            left[y][i] = dig_left
            right[y][i] = width - 1
    return left, right


def _path_clear(clear: Sequence[Sequence[bool]], source: tuple[int, int], target: tuple[int, int]) -> bool:
    """NetHack's q1/q2/q3/q4 path test, excluding endpoints."""

    sy, sx = source[1], source[0]
    y2, x2 = target[1], target[0]
    dx = x2 - sx
    dy = y2 - sy
    step_x = 1 if dx > 0 else -1 if dx < 0 else 0
    step_y = 1 if dy > 0 else -1 if dy < 0 else 0
    dx = abs(dx)
    dy = abs(dy)
    x, y = sx, sy
    dx2, dy2 = dx << 1, dy << 1
    if dy > dx:
        error = dx2 - dy
        for _ in range(dy - 1):
            if error >= 0:
                x += step_x
                error -= dy2
            y += step_y
            error += dx2
            if not clear[y][x]:
                return False
    else:
        error = dy2 - dx
        for _ in range(dx - 1):
            if error >= 0:
                y += step_y
                error -= dx2
            x += step_x
            error += dy2
            if not clear[y][x]:
                return False
    return True


def could_see(
    terrain_type: Sequence[Sequence[int]],
    terrain_flags: Sequence[Sequence[int]],
    source_x: int,
    source_y: int,
    *,
    underwater: bool = False,
    dynamic_blockers: Iterable[tuple[int, int]] = (),
) -> list[list[bool]]:
    """Calculate NetHack Algorithm C's ``COULD_SEE`` plane.

    The source ``view_from`` call used by ordinary dlvl-1 vision has an
    unlimited range (``range == 0``), which is the only range exposed here.
    Endpoints are visible even when they are blocking, matching NetHack's
    source path routines.
    """

    _validate_plane(terrain_type, name="terrain_type")
    _validate_plane(terrain_flags, name="terrain_flags")
    if type(source_x) is not int or type(source_y) is not int or not (0 <= source_x < VIEW_WIDTH and 0 <= source_y < VIEW_HEIGHT):
        raise ValueError("source coordinate is outside the 21x79 plane")
    screen_clear = static_clear_plane(
        terrain_type,
        terrain_flags,
        underwater=underwater,
        dynamic_blockers=dynamic_blockers,
    )
    # NetHack's native level has COLNO=80 columns, with native x=0 as an
    # always-blocked sentinel.  The public 79-column crop starts at native
    # x=1.  Keeping that sentinel in the algorithm is essential for the
    # source row-pointer boundary behavior at the left edge.
    clear = [[False, *row] for row in screen_clear]
    left_ptr, right_ptr = _run_tables(clear)
    width = len(clear[0])
    source_x_native = source_x + 1
    visible_native = [[False] * width for _ in range(VIEW_HEIGHT)]

    def mark(row: int, start: int, stop: int) -> None:
        if not (0 <= row < VIEW_HEIGHT):
            return
        for col in range(max(0, start), min(width - 1, stop) + 1):
            visible_native[row][col] = True

    def right_side(row: int, left_mark: int, right_mark: int, step: int) -> None:
        nrow = row + step
        deeper = 0 <= nrow < VIEW_HEIGHT
        lim_max = width - 1
        while left_mark <= right_mark:
            right_edge = min(right_ptr[row][left_mark], lim_max)
            if not clear[row][left_mark]:
                if right_edge > right_mark:
                    right_edge = right_mark + 1 if clear[row - step][right_mark] else right_mark
                mark(row, left_mark, right_edge)
                left_mark = right_edge + 1
                continue

            if left_mark != source_x_native:
                found = None
                for candidate in range(left_mark, right_edge + 1):
                    if _path_clear(clear, (source_x_native, source_y), (candidate, row)):
                        found = candidate
                        break
                # The C loop leaves ``left`` one past the edge when every
                # candidate is blocked; the boundary checks below then retain
                # the far wall as an observable endpoint.  Returning here
                # would incorrectly erase that wall.
                left_mark = found if found is not None else right_edge + 1
                if left_mark >= lim_max:
                    mark(row, lim_max, lim_max)
                    return
                if left_mark >= right_edge:
                    left_mark = right_edge
                    continue

            if right_mark < right_edge:
                # Source ``q*_path`` loop increments ``right`` once after
                # the last successful candidate, then decrements it.  Keep
                # that exact off-by-one behavior at a blocked opening edge.
                candidate = right_mark
                while candidate <= right_edge and _path_clear(clear, (source_x_native, source_y), (candidate, row)):
                    candidate += 1
                right = candidate - 1
            else:
                right = right_edge
            if left_mark <= right:
                if left_mark == right and left_mark == source_x_native and source_x_native < width - 1 and not clear[row][source_x_native + 1]:
                    right = source_x_native + 1
                right = min(right, lim_max)
                mark(row, left_mark, right)
                if deeper:
                    right_side(nrow, left_mark, right, step)
                left_mark = right + 1

    def left_side(row: int, left_mark: int, right_mark: int, step: int) -> None:
        nrow = row + step
        deeper = 0 <= nrow < VIEW_HEIGHT
        lim_min = 0
        while right_mark >= left_mark:
            left_edge = max(left_ptr[row][right_mark], lim_min)
            if not clear[row][right_mark]:
                if left_edge < left_mark:
                    left_edge = left_mark - 1 if clear[row - step][left_mark] else left_mark
                mark(row, left_edge, right_mark)
                right_mark = left_edge - 1
                continue

            if right_mark != source_x_native:
                found = None
                for candidate in range(right_mark, left_edge - 1, -1):
                    if _path_clear(clear, (source_x_native, source_y), (candidate, row)):
                        found = candidate
                        break
                # Mirror the source loop: a fully blocked opening leaves the
                # marker one before the edge and is handled by the boundary
                # checks rather than terminating the quadrant.
                right_mark = found if found is not None else left_edge - 1
                if right_mark <= lim_min:
                    mark(row, lim_min, lim_min)
                    return
                if right_mark <= left_edge:
                    right_mark = left_edge
                    continue

            if left_mark > left_edge:
                candidate = left_mark
                while candidate >= left_edge and _path_clear(clear, (source_x_native, source_y), (candidate, row)):
                    candidate -= 1
                # The source loop increments ``left`` after the first
                # blocked candidate (or after exhausting the opening).
                left = candidate + 1
            else:
                left = left_edge
            if left <= right_mark:
                if left == right_mark and right_mark == source_x_native and source_x_native > 0 and not clear[row][source_x_native - 1]:
                    left = source_x_native - 1
                left = max(left, lim_min)
                mark(row, left, right_mark)
                if deeper:
                    left_side(nrow, left, right_mark, step)
                right_mark = left - 1

    if clear[source_y][source_x_native]:
        left = left_ptr[source_y][source_x_native]
        right = right_ptr[source_y][source_x_native]
    else:
        left = 0 if source_x_native == 0 else (left_ptr[source_y][source_x_native - 1] if clear[source_y][source_x_native - 1] else source_x_native - 1)
        right = width - 1 if source_x_native == width - 1 else (right_ptr[source_y][source_x_native + 1] if clear[source_y][source_x_native + 1] else source_x_native + 1)
    mark(source_y, left, right)
    if source_y + 1 < VIEW_HEIGHT:
        right_side(source_y + 1, source_x_native, right, 1)
        left_side(source_y + 1, left, source_x_native, 1)
    if source_y - 1 >= 0:
        right_side(source_y - 1, source_x_native, right, -1)
        left_side(source_y - 1, left, source_x_native, -1)
    return [row[1:] for row in visible_native]
