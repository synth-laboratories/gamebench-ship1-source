#!/usr/bin/env python3
"""Plan a static Emerald field path from the matching pokeemerald map data.

This is deliberately a *structural* planner.  It parses the map layout's
packed collision/elevation cells and returns a shortest cardinal path.  It
does not claim that NPCs, scripts, warps, or controller timing agree with the
live ROM: callers must replay the returned directions in short JSONL pulses
and authenticate that replay before using it as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import deque
from pathlib import Path
from typing import Any


CARDINALS = (("up", 0, -1), ("down", 0, 1), ("left", -1, 0), ("right", 1, 0))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_layout(decomp: Path, map_name: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    map_json = decomp / "data" / "maps" / map_name / "map.json"
    maps = json.loads(map_json.read_text(encoding="utf-8"))
    layouts = json.loads((decomp / "data" / "layouts" / "layouts.json").read_text(encoding="utf-8"))
    layout = next((item for item in layouts["layouts"] if item["id"] == maps["layout"]), None)
    if layout is None:
        raise ValueError(f"layout {maps['layout']!r} was not found in layouts.json")
    blockdata = decomp / layout["blockdata_filepath"]
    return maps, layout, blockdata


def parse_point(value: str, width: int, height: int) -> tuple[int, int]:
    try:
        x_text, y_text = value.split(",", 1)
        point = int(x_text), int(y_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("points must be x,y") from exc
    x, y = point
    if not (0 <= x < width and 0 <= y < height):
        raise argparse.ArgumentTypeError(f"point {value!r} is outside {width}x{height}")
    return point


def unpack_cells(blockdata: Path, width: int, height: int) -> tuple[int, ...]:
    raw = blockdata.read_bytes()
    expected = width * height * 2
    if len(raw) != expected:
        raise ValueError(f"{blockdata} is {len(raw)} bytes; expected {expected}")
    return struct.unpack(f"<{width * height}H", raw)


def is_passable(cells: tuple[int, ...], width: int, x: int, y: int, unsafe: set[tuple[int, int]] | None = None) -> bool:
    # pokeemerald global.fieldmap.h: collision occupies packed bits 10-11.
    return ((cells[y * width + x] >> 10) & 0x3) == 0 and (unsafe is None or (x, y) not in unsafe)


def elevation(cells: tuple[int, ...], width: int, x: int, y: int) -> int:
    return (cells[y * width + x] >> 12) & 0xF


def find_path(cells: tuple[int, ...], width: int, height: int, start: tuple[int, int], goal: tuple[int, int], unsafe: set[tuple[int, int]]) -> list[str]:
    if not is_passable(cells, width, *start, unsafe) or not is_passable(cells, width, *goal, unsafe):
        raise ValueError("start and goal must both be collision-passable")
    queue: deque[tuple[int, int]] = deque([start])
    previous: dict[tuple[int, int], tuple[tuple[int, int], str] | None] = {start: None}
    while queue:
        x, y = queue.popleft()
        if (x, y) == goal:
            break
        for direction, dx, dy in CARDINALS:
            candidate = x + dx, y + dy
            nx, ny = candidate
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if candidate in previous or not is_passable(cells, width, nx, ny, unsafe):
                continue
            # A transition cell (elevation 0) is allowed because vanilla
            # field movement resolves it; non-transition elevations must match.
            here, there = elevation(cells, width, x, y), elevation(cells, width, nx, ny)
            if here and there and here != 0xF and there != 0xF and here != there:
                continue
            previous[candidate] = ((x, y), direction)
            queue.append(candidate)
    if goal not in previous:
        raise ValueError("no collision/elevation-valid static path exists")
    path: list[str] = []
    cursor = goal
    while previous[cursor] is not None:
        cursor, direction = previous[cursor]  # type: ignore[misc]
        path.append(direction)
    return list(reversed(path))


def compress(path: list[str]) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for direction in path:
        if result and result[-1]["direction"] == direction:
            result[-1]["tiles"] = int(result[-1]["tiles"]) + 1
        else:
            result.append({"direction": direction, "tiles": 1})
    return result


def encounter_cells(decomp: Path, layout: dict[str, Any], cells: tuple[int, ...], width: int, height: int) -> set[tuple[int, int]]:
    """Return cells whose vanilla metatile behavior can initiate encounters."""
    primary = struct.unpack("<512H", (decomp / "data/tilesets/primary/general/metatile_attributes.bin").read_bytes())
    secondary_name = layout["secondary_tileset"].removeprefix("gTileset_").lower()
    attributes_path = decomp / "data" / "tilesets" / "secondary" / secondary_name / "metatile_attributes.bin"
    secondary_raw = attributes_path.read_bytes()
    secondary = struct.unpack(f"<{len(secondary_raw) // 2}H", secondary_raw)
    # MB_TALL_GRASS, MB_LONG_GRASS, MB_LONG_GRASS_SOUTH_EDGE, MB_INDOOR_ENCOUNTER.
    encounter_behaviors = {2, 3, 9, 11}
    result: set[tuple[int, int]] = set()
    for y in range(height):
        for x in range(width):
            tile = cells[y * width + x] & 0x3FF
            behavior = (primary[tile] if tile < 512 else secondary[tile - 512]) & 0xFF
            if behavior in encounter_behaviors:
                result.add((x, y))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decomp-root", type=Path, required=True)
    parser.add_argument("--map", dest="map_name", required=True, help="decomp map directory name, e.g. Route101")
    parser.add_argument("--start", required=True, help="source player coordinate x,y")
    parser.add_argument("--goal", help="source player coordinate x,y")
    parser.add_argument("--goal-edge", choices=("up", "down", "left", "right"), help="choose the closest passable cell on this map edge")
    parser.add_argument("--avoid-encounters", action="store_true", help="exclude vanilla grass/indoor encounter metatile behaviors")
    parser.add_argument("--output", type=Path, help="optional JSON output file")
    args = parser.parse_args()
    if bool(args.goal) == bool(args.goal_edge):
        parser.error("supply exactly one of --goal or --goal-edge")
    maps, layout, blockdata = load_layout(args.decomp_root, args.map_name)
    width, height = layout["width"], layout["height"]
    start = parse_point(args.start, width, height)
    cells = unpack_cells(blockdata, width, height)
    unsafe = encounter_cells(args.decomp_root, layout, cells, width, height) if args.avoid_encounters else set()
    if args.goal:
        goals = [parse_point(args.goal, width, height)]
    elif args.goal_edge == "up":
        goals = [(x, 0) for x in range(width)]
    elif args.goal_edge == "down":
        goals = [(x, height - 1) for x in range(width)]
    elif args.goal_edge == "left":
        goals = [(0, y) for y in range(height)]
    else:
        goals = [(width - 1, y) for y in range(height)]
    candidates: list[tuple[list[str], tuple[int, int]]] = []
    for goal in goals:
        if is_passable(cells, width, *goal, unsafe):
            try:
                candidates.append((find_path(cells, width, height, start, goal, unsafe), goal))
            except ValueError:
                pass
    if not candidates:
        raise SystemExit("no static path to the requested goal/edge")
    path, goal = min(candidates, key=lambda item: len(item[0]))
    result: dict[str, Any] = {
        "schema": "gamebench.pokemon_emerald.static_decomp_path.v1",
        "purpose": "structural route proposal only; live JSONL pulse replay and capture receipt are required for evidence",
        "map": {"id": maps["id"], "name": maps["name"], "layout": layout["id"], "width": width, "height": height},
        "blockdata": {"path": str(blockdata), "sha256": sha256(blockdata)},
        "passability_model": "packed map.bin collision==0; reject unequal non-transition elevations; dynamic objects/directional metatile behavior are not modeled" + ("; grass/indoor encounter behaviors are excluded" if args.avoid_encounters else ""),
        "excluded_encounter_cells": len(unsafe),
        "start": {"x": start[0], "y": start[1]},
        "goal": {"x": goal[0], "y": goal[1]},
        "tile_path": path,
        "segments": compress(path),
        "tile_count": len(path),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite {args.output}")
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
