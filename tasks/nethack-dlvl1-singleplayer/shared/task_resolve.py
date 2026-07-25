"""Resolve a capture-backed NetHack dlvl-1 task without importing NLE."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
NLE_ORACLE_DIR = TASK_DIR / "fixtures" / "nle_oracle"
VIEW_HEIGHT = 21
VIEW_WIDTH = 79
DEFAULT_CHARACTER = {
    "role": "val",
    "race": "hum",
    "gender": "fem",
    "align": "law",
    "nle_character": "val-hum-fem-law",
}
BLSTATS_FIELDS = (
    "x",
    "y",
    "strength",
    "strength_percent",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
    "score",
    "hp",
    "hp_max",
    "depth",
    "gold",
    "energy",
    "energy_max",
    "ac",
    "monster_level",
    "experience_level",
    "experience",
    "time",
    "hunger",
    "capacity",
    "dungeon_number",
    "dungeon_level",
    "condition",
    "alignment",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _as_char(value: Any) -> str:
    if isinstance(value, int):
        return chr(value) if 0 <= value <= 0x10FFFF else " "
    text = str(value)
    return text[:1] if text else " "


def _normalise_rows(raw: Any, *, fill: str = " ") -> list[list[str]]:
    source = raw if isinstance(raw, list) else []
    rows: list[list[str]] = []
    for row in source[:VIEW_HEIGHT]:
        if isinstance(row, str):
            chars = list(row)
        elif isinstance(row, list):
            chars = [_as_char(cell) for cell in row]
        else:
            chars = []
        rows.append((chars + [fill] * VIEW_WIDTH)[:VIEW_WIDTH])
    while len(rows) < VIEW_HEIGHT:
        rows.append([fill] * VIEW_WIDTH)
    return rows


def _normalise_int_rows(raw: Any, *, fallback: list[list[str]], default: int) -> list[list[int]]:
    source = raw if isinstance(raw, list) else []
    rows: list[list[int]] = []
    for y in range(VIEW_HEIGHT):
        original = source[y] if y < len(source) and isinstance(source[y], list) else []
        row: list[int] = []
        for x in range(VIEW_WIDTH):
            candidate = original[x] if x < len(original) else None
            if isinstance(candidate, bool):
                row.append(int(candidate))
            elif isinstance(candidate, int):
                row.append(candidate)
            else:
                row.append(ord(fallback[y][x]) if default == -1 else default)
        rows.append(row)
    return rows


def _normalise_seen(raw: Any, *, terrain: list[list[str]]) -> list[list[bool]]:
    if isinstance(raw, list):
        output: list[list[bool]] = []
        for y in range(VIEW_HEIGHT):
            source = raw[y] if y < len(raw) and isinstance(raw[y], list) else []
            output.append([bool(source[x]) if x < len(source) else False for x in range(VIEW_WIDTH)])
        return output
    return [[cell != " " for cell in row] for row in terrain]


def _normalise_unseen(raw: Any) -> dict[str, list[list[Any]]]:
    data = dict(raw) if isinstance(raw, dict) else {}
    chars = _normalise_rows(data.get("chars"), fill=" ")
    return {
        "chars": chars,
        "glyphs": _normalise_int_rows(data.get("glyphs"), fallback=chars, default=0),
        "colors": _normalise_int_rows(data.get("colors"), fallback=chars, default=0),
    }


def _position(value: Any) -> dict[str, int]:
    data = value if isinstance(value, dict) else {}
    return {"x": int(data.get("x", 0)), "y": int(data.get("y", 0))}


def _normalise_item(value: Any, *, index: int, floor: bool = False) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    position = _position(data.get("position", data.get("pos", data)))
    letter = str(data.get("letter", data.get("inv_letter", "")))[:1]
    kind = str(data.get("kind", data.get("oclass", data.get("class", ")"))))[:1] or ")"
    name = str(data.get("name", data.get("description", "unknown object")))
    return {
        "id": str(data.get("id", f"{'floor' if floor else 'inventory'}-{index}")),
        "letter": letter,
        "kind": kind,
        "name": name,
        "quantity": max(1, int(data.get("quantity", data.get("count", 1)))),
        "glyph": int(data.get("glyph", ord(kind))),
        "color": int(data.get("color", 7)),
        "oclass": int(data.get("oclass_code", ord(kind))),
        "nutrition": int(data.get("nutrition", 600 if kind == "%" else 0)),
        "damage": max(0, int(data.get("damage", 2 if kind == ")" else 0))),
        "armor": int(data.get("armor", 1 if kind == "[" else 0)),
        "effect": str(data.get("effect", "")),
        "position": position,
    }


def _normalise_monster(value: Any, *, index: int) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    position = _position(data.get("position", data.get("pos", data)))
    char = str(data.get("char", data.get("symbol", "j")))[:1] or "j"
    hp = max(1, int(data.get("hp", 4)))
    return {
        "id": str(data.get("id", f"monster-{index}")),
        "name": str(data.get("name", "jackal")),
        "char": char,
        "glyph": int(data.get("glyph", ord(char))),
        "color": int(data.get("color", 6)),
        "hp": hp,
        "hp_max": max(hp, int(data.get("hp_max", hp))),
        "attack": max(0, int(data.get("attack", 2))),
        "experience": max(0, int(data.get("experience", 2))),
        "peaceful": bool(data.get("peaceful", False)),
        "pet": bool(data.get("pet", False)),
        "position": position,
    }


def _normalise_trap(value: Any, *, index: int) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    return {
        "id": str(data.get("id", f"trap-{index}")),
        "kind": str(data.get("kind", "arrow")),
        "damage": max(0, int(data.get("damage", 2))),
        "seen": bool(data.get("seen", False)),
        "triggered": bool(data.get("triggered", False)),
        "position": _position(data.get("position", data.get("pos", data))),
    }


def normalise_level_dump(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-only 21×79 dump suitable for either independent gold lane."""

    data = dict(raw)
    if "visibility_schedule" in data:
        raise ValueError("level_dump may not encode a future action-indexed visibility schedule")
    terrain = _normalise_rows(data.get("terrain", data.get("chars", data.get("grid", []))))
    hero_raw = data.get("hero", {})
    hero = _position(hero_raw)
    hero_explicit = isinstance(hero_raw, dict) and ("x" in hero_raw or "y" in hero_raw)
    hero_found = False
    for y, row in enumerate(terrain):
        for x, cell in enumerate(row):
            if cell == "@":
                hero = {"x": x, "y": y}
                row[x] = "."
                hero_found = True
    if not hero_found and not hero_explicit:
        raise ValueError("level_dump must contain @ or an explicit hero position")
    if not (0 <= hero["x"] < VIEW_WIDTH and 0 <= hero["y"] < VIEW_HEIGHT):
        raise ValueError("level_dump must contain a hero position inside the 21x79 crop")
    glyphs = _normalise_int_rows(data.get("glyphs"), fallback=terrain, default=-1)
    colors = _normalise_int_rows(data.get("colors"), fallback=terrain, default=7)
    seen = _normalise_seen(data.get("seen"), terrain=terrain)
    hero = {
        **hero,
        "glyph": int(dict(hero_raw).get("glyph", ord("@"))) if isinstance(hero_raw, dict) else ord("@"),
        "color": int(dict(hero_raw).get("color", 15)) if isinstance(hero_raw, dict) else 15,
    }
    floor_items = [_normalise_item(item, index=index, floor=True) for index, item in enumerate(data.get("objects", data.get("items", [])))]
    inventory = [_normalise_item(item, index=index) for index, item in enumerate(data.get("inventory", []))]
    monsters = [_normalise_monster(monster, index=index) for index, monster in enumerate(data.get("monsters", []))]
    traps = [_normalise_trap(trap, index=index) for index, trap in enumerate(data.get("traps", []))]
    if any(bool(branch) for branch in data.get("branches", [])) or data.get("mines_entry"):
        raise ValueError("dlvl-1 fixture contains a branch/Mines entry; reject it instead of modeling branch geography")
    depth = int(data.get("dungeon_level", data.get("depth", 1)))
    if depth != 1:
        raise ValueError(f"only Main Dungeon dlvl 1 is in scope, got level {depth}")
    return {
        "schema": "gamebench.nethack.level_dump.v1",
        "terrain": ["".join(row) for row in terrain],
        "glyphs": glyphs,
        "colors": colors,
        "seen": seen,
        "unseen": _normalise_unseen(data.get("unseen")),
        "hero": hero,
        "objects": floor_items,
        "inventory": inventory,
        "monsters": monsters,
        "traps": traps,
        "dungeon_level": 1,
        "metadata": deepcopy(dict(data.get("metadata", {}))),
    }


def _load_oracle_fixture(fixture_id: str) -> dict[str, Any]:
    fixture_dir = NLE_ORACLE_DIR / fixture_id
    level_path = fixture_dir / "level_dump.json"
    meta_path = fixture_dir / "meta.json"
    if not level_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"missing frozen NLE fixture {fixture_id!r} under {fixture_dir}")
    return {"level_dump": json.loads(level_path.read_text()), "meta": json.loads(meta_path.read_text())}


def resolve_task(task: dict[str, Any], *, seed_override: int | None = None) -> dict[str, Any]:
    """Validate and canonicalize a GameBench task into a lane-neutral reset payload."""

    data = dict(task)
    fixture_id = str(data.get("fixture_id", ""))
    fixture: dict[str, Any] = {}
    if fixture_id:
        fixture = _load_oracle_fixture(fixture_id)
    level_source = data.get("level_dump", fixture.get("level_dump", {}))
    if not level_source:
        level_source = {"grid": data.get("grid", [])}
    level_dump = normalise_level_dump(dict(level_source))
    character = {**DEFAULT_CHARACTER, **dict(data.get("character", fixture.get("meta", {}).get("character", {})))}
    rules = {
        "max_steps": 0,
        "autopickup": False,
        "auto_more": "raw_explicit",
        "vision_radius": 5,
        **dict(data.get("rules", {})),
    }
    if str(rules.get("auto_more")) != "raw_explicit":
        raise ValueError("only raw_explicit MORE is supported by the pinned capture contract")
    seed = int(seed_override if seed_override is not None else data.get("seed", fixture.get("meta", {}).get("seed", 0)))
    task_id = str(data.get("task_id", data.get("scenario_id", fixture_id or "manual")))
    core = {
        "schema": "gamebench.task.nethack_dlvl1.v1",
        "task_id": task_id,
        "fixture_id": fixture_id,
        "seed": seed,
        "character": character,
        "rules": rules,
        "level_dump": level_dump,
        "nle_meta": deepcopy(dict(fixture.get("meta", {}))),
    }
    core["config_hash"] = digest(core)
    core["episode_id"] = f"nethack-dlvl1:{task_id}:{core['config_hash'][7:19]}"
    return core
