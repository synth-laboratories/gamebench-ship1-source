#!/usr/bin/env python3
"""Discover a deterministic Emerald field route with fresh mGBA reloads.

This is a semantic route-discovery tool, not a framebuffer oracle.  It runs
inside the same pinned mGBA image as the JSONL adapter, reloads the immutable
input raw state for *every BFS branch*, and records each one-tile input edge,
collision, and map warp.  A discovered route must still be replayed through
the JSONL adapter/capture CLI before it becomes authenticated evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any

import mgba.core
import mgba.image
import mgba.log


WIDTH, HEIGHT = 240, 160
DIRECTIONS = ("up", "down", "left", "right")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_position(core: Any) -> dict[str, int]:
    block = core.memory.u32[0x03005D8C]
    if not 0x02000000 <= block < 0x02040000:
        raise RuntimeError(f"invalid Emerald gSaveBlock1Ptr: 0x{block:08x}")
    return {
        "map_group": core.memory.s8[block + 4],
        "map_number": core.memory.s8[block + 5],
        "player_x": core.memory.s16[block],
        "player_y": core.memory.s16[block + 2],
    }


def position_key(position: dict[str, int]) -> tuple[int, int, int, int]:
    return tuple(position[field] for field in ("map_group", "map_number", "player_x", "player_y"))


class Navigator:
    def __init__(self, rom: Path, state: Path, press_vblanks: int, settle_vblanks: int) -> None:
        mgba.log.silence()
        core = mgba.core.load_path(str(rom))
        if core is None:
            raise RuntimeError(f"mGBA could not load ROM: {rom}")
        core.reset()
        image = mgba.image.Image(WIDTH, HEIGHT)
        core.set_video_buffer(image)
        core.reset()
        self.core = core
        self.initial_raw_state = state.read_bytes()
        self.press_vblanks = press_vblanks
        self.settle_vblanks = settle_vblanks
        self.keys = {name: getattr(core, f"KEY_{name.upper()}") for name in DIRECTIONS}

    def reload(self) -> dict[str, int]:
        loaded = self.core.load_raw_state(self.initial_raw_state)
        if loaded is False:
            raise RuntimeError("mGBA rejected the navigator input raw state")
        # Match the source adapter/PokeAgent boundary after every raw reload.
        self.core.set_keys()
        self.core.run_frame()
        return source_position(self.core)

    def walk_branch(self, path: list[str]) -> tuple[dict[str, int], list[dict[str, Any]]]:
        """Reload, replay the path, and return terminal state plus all edges."""
        current = self.reload()
        edges: list[dict[str, Any]] = []
        for direction in path:
            before = current
            first_motion: int | None = None
            first_warp: int | None = None
            intermediate: list[dict[str, int]] = []
            for vblank in range(1, self.press_vblanks + 1):
                self.core.set_keys(self.keys[direction])
                self.core.run_frame()
                self.core.set_keys()
                observed = source_position(self.core)
                if first_motion is None and position_key(observed) != position_key(before):
                    first_motion = vblank
                if first_warp is None and (
                    observed["map_group"] != before["map_group"]
                    or observed["map_number"] != before["map_number"]
                ):
                    first_warp = vblank
                intermediate.append(observed)
            for _ in range(self.settle_vblanks):
                self.core.set_keys()
                self.core.run_frame()
                intermediate.append(source_position(self.core))
            current = intermediate[-1]
            warped = (before["map_group"], before["map_number"]) != (
                current["map_group"], current["map_number"]
            )
            edges.append(
                {
                    "direction": direction,
                    "from": before,
                    "to": current,
                    "press_vblanks": self.press_vblanks,
                    "settle_vblanks": self.settle_vblanks,
                    "first_motion_vblank": first_motion,
                    "first_warp_vblank": first_warp,
                    "collision": not warped and position_key(before) == position_key(current),
                    "warp": warped,
                }
            )
        return current, edges


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-depth", type=int, default=64)
    parser.add_argument("--max-nodes", type=int, default=512)
    parser.add_argument("--press-vblanks", type=int, default=16)
    parser.add_argument("--settle-vblanks", type=int, default=16)
    parser.add_argument("--prefix", default="", help="comma-separated known route prefix, replayed after every fresh reload")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.rom.is_file() or not args.state.is_file():
        raise SystemExit("--rom and --state must name readable files")
    if args.output.exists() or not args.output.parent.is_dir():
        raise SystemExit("--output must be a new file in an existing directory")
    if min(args.max_depth, args.max_nodes, args.press_vblanks, args.settle_vblanks) < 1:
        raise SystemExit("depth and VBlank counts must be positive")

    navigator = Navigator(args.rom, args.state, args.press_vblanks, args.settle_vblanks)
    prefix = [part for part in args.prefix.split(",") if part]
    if any(part not in DIRECTIONS for part in prefix):
        raise SystemExit("--prefix must contain only up,down,left,right")
    start = navigator.reload()
    prefix_edges: list[dict[str, Any]] = []
    if prefix:
        start, prefix_edges = navigator.walk_branch(prefix)
    start_key = position_key(start)
    queue: deque[tuple[list[str], dict[str, int]]] = deque([([], start)])
    routes: dict[tuple[int, int, int, int], list[str]] = {start_key: []}
    nodes: dict[tuple[int, int, int, int], dict[str, Any]] = {start_key: {"position": start, "path": []}}
    edges: list[dict[str, Any]] = []

    while queue:
        if len(nodes) >= args.max_nodes:
            break
        path, origin = queue.popleft()
        if len(path) >= args.max_depth:
            continue
        for direction in DIRECTIONS:
            candidate = [*prefix, *path, direction]
            terminal, replay_edges = navigator.walk_branch(candidate)
            edge = replay_edges[-1]
            edge["path"] = candidate
            edges.append(edge)
            terminal_key = position_key(terminal)
            if edge["collision"] or terminal_key in routes:
                continue
            relative_path = [*path, direction]
            routes[terminal_key] = relative_path
            nodes[terminal_key] = {"position": terminal, "path": candidate}
            queue.append((relative_path, terminal))

    result = {
        "schema": "gamebench.pokemon_emerald.field_navigation_graph.v1",
        "purpose": "semantic source route discovery only; replay route through the JSONL capture oracle before promotion",
        "source": {
            "runtime": "pinned mGBA image direct core",
            "fresh_raw_reload_per_branch": True,
            "rom_sha256": sha256_file(args.rom),
            "state_sha256": sha256_file(args.state),
        },
        "tile_action": {"press_vblanks": args.press_vblanks, "settle_vblanks": args.settle_vblanks},
        "start": start,
        "prefix": prefix,
        "prefix_edges": prefix_edges,
        "max_depth": args.max_depth,
        "max_nodes": args.max_nodes,
        "nodes": sorted(nodes.values(), key=lambda node: (len(node["path"]), node["path"])),
        "edges": edges,
        "summary": {
            "reachable_nodes": len(nodes),
            "attempted_edges": len(edges),
            "collisions": sum(1 for edge in edges if edge["collision"]),
            "warps": sum(1 for edge in edges if edge["warp"]),
            "reachable_maps": sorted({(node["position"]["map_group"], node["position"]["map_number"]) for node in nodes.values()}),
        },
    }
    result["graph_sha256"] = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
