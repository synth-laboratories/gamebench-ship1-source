"""Programmatic scoring for FrogsGame placements."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


Position = tuple[int, int]


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    cells: tuple[Position, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "cells": [[row, col] for row, col in self.cells],
        }


def validate_frogs(
    board: list[list[str]],
    frogs: list[Position],
    *,
    require_complete: bool,
) -> list[Violation]:
    n = len(board)
    violations: list[Violation] = []
    seen = set()
    for row, col in frogs:
        if not 0 <= row < n or not 0 <= col < n:
            violations.append(Violation("out_of_bounds", f"frog outside board at ({row},{col})", ((row, col),)))
        elif (row, col) in seen:
            violations.append(Violation("duplicate_cell", f"duplicate frog at ({row},{col})", ((row, col),)))
        seen.add((row, col))

    row_counts = Counter(row for row, _ in frogs)
    for row, count in sorted(row_counts.items()):
        if count > 1:
            cells = tuple(sorted((r, c) for r, c in frogs if r == row))
            violations.append(Violation("row_conflict", f"multiple frogs in row {row}", cells))

    col_counts = Counter(col for _, col in frogs)
    for col, count in sorted(col_counts.items()):
        if count > 1:
            cells = tuple(sorted((r, c) for r, c in frogs if c == col))
            violations.append(Violation("column_conflict", f"multiple frogs in column {col}", cells))

    colors: list[str] = []
    for row, col in frogs:
        if 0 <= row < n and 0 <= col < n:
            colors.append(board[row][col])
    color_counts = Counter(colors)
    for color, count in sorted(color_counts.items()):
        if count > 1:
            cells = tuple(sorted((r, c) for r, c in frogs if 0 <= r < n and 0 <= c < n and board[r][c] == color))
            violations.append(Violation("color_conflict", f"multiple frogs in color {color}", cells))

    ordered = sorted(frogs)
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            if abs(first[0] - second[0]) <= 1 and abs(first[1] - second[1]) <= 1:
                violations.append(Violation("adjacency_conflict", "frogs touch orthogonally or diagonally", (first, second)))

    if require_complete:
        if len(frogs) != n:
            violations.append(Violation("incomplete", f"expected {n} frogs, found {len(frogs)}"))

    return violations


def binary_success_score(board: list[list[str]], frogs: list[Position]) -> float:
    """Return 1.0 exactly when the submitted placement is complete and valid."""

    return 0.0 if validate_frogs(board, frogs, require_complete=True) else 1.0
