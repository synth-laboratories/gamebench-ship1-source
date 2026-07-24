"""Parsed MiniHack ASCII layout."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedLayout:
    walls: frozenset[tuple[int, int]]
    goals: frozenset[tuple[int, int]]
    targets: frozenset[tuple[int, int]]
    player_start: tuple[int, int]
    boulders_start: frozenset[tuple[int, int]]
    monsters_start: frozenset[tuple[int, int]]
    lava_start: frozenset[tuple[int, int]]
    frozen_start: frozenset[tuple[int, int]]
    items_start: frozenset[tuple[tuple[int, int], str]]
    width: int
    height: int
