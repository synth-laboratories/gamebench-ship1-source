"""Reachability helpers for Overcooked v2 featurized observations."""

from __future__ import annotations

from collections import deque
from typing import Callable

from state import DIRECTIONS


def flood_fill_region(
    start: tuple[int, int],
    height: int,
    width: int,
    is_blocked: Callable[[tuple[int, int]], bool],
) -> set[tuple[int, int]]:
    if is_blocked(start):
        return {start}
    region: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        pos = queue.popleft()
        if pos in region:
            continue
        if is_blocked(pos):
            continue
        region.add(pos)
        row, col = pos
        for dr, dc in DIRECTIONS.values():
            neighbor = (row + dr, col + dc)
            if 0 <= neighbor[0] < height and 0 <= neighbor[1] < width:
                queue.append(neighbor)
    return region


def bfs_closest_delta(
    start: tuple[int, int],
    targets: set[tuple[int, int]],
    reachable: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
) -> tuple[tuple[int, int], bool]:
    if not targets:
        return (0, 0), False
    if start in targets:
        return (0, 0), True
    queue: deque[tuple[tuple[int, int], tuple[int, int]]] = deque([(start, (0, 0))])
    seen = {start}
    while queue:
        pos, delta = queue.popleft()
        row, col = pos
        for direction, (dr, dc) in DIRECTIONS.items():
            neighbor = (row + dr, col + dc)
            if neighbor in seen or neighbor not in reachable or neighbor in blocked:
                continue
            next_delta = (delta[0] + dr, delta[1] + dc)
            if neighbor in targets:
                return next_delta, True
            seen.add(neighbor)
            queue.append((neighbor, next_delta))
    return (0, 0), False


def adjacent_cells(position: tuple[int, int]) -> dict[str, tuple[int, int]]:
    row, col = position
    return {
        direction: (row + dr, col + dc)
        for direction, (dr, dc) in DIRECTIONS.items()
    }


def wall_features(
    position: tuple[int, int],
    height: int,
    width: int,
    is_wall: Callable[[tuple[int, int]], bool],
) -> list[float]:
    row, col = position
    checks = [
        (row - 1, col),
        (row + 1, col),
        (row, col + 1),
        (row, col - 1),
    ]
    features: list[float] = []
    for check_row, check_col in checks:
        if check_row < 0 or check_row >= height or check_col < 0 or check_col >= width:
            features.append(1.0)
        else:
            features.append(1.0 if is_wall((check_row, check_col)) else 0.0)
    return features
