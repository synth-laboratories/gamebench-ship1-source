#!/usr/bin/env python3
"""Capture a raw NLE dlvl-1 tape without making NLE a gold dependency.

NLE imports are confined to this capture script and the optional live fuzzer;
gold engines never import it.  This script records action-space indices rather
than enum keycodes and preserves raw observation arrays.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))


OBSERVATION_KEYS = (
    "glyphs",
    "chars",
    "colors",
    "specials",
    "blstats",
    "message",
    "inv_glyphs",
    "inv_letters",
    "inv_oclasses",
    "inv_strs",
    "tty_chars",
    "tty_colors",
    "tty_cursor",
)
NLE_SEED_MASK = (1 << 63) - 1
DISPLAY_SEED_XOR = 0x5DEECE66D
STATIC_TERRAIN_CHARS = frozenset(".#|-+<>_{}~")
ANNOTATION_ENTITY_KEYS = frozenset(("objects", "inventory", "monsters", "traps"))
FIXTURE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
NLE_OCLASS_TO_KIND = {
    2: ")",  # WEAPON_CLASS
    3: "[",  # ARMOR_CLASS
    4: "=",  # RING_CLASS
    5: '"',  # AMULET_CLASS
    6: "(",  # TOOL_CLASS
    7: "%",  # FOOD_CLASS
    8: "!",  # POTION_CLASS
    9: "?",  # SCROLL_CLASS
    10: "+",  # SPBOOK_CLASS
    11: "/",  # WAND_CLASS
    12: "$",  # COIN_CLASS
    13: "*",  # GEM_CLASS
    14: "`",  # ROCK_CLASS
    15: "0",  # BALL_CLASS
    16: "_",  # CHAIN_CLASS
    17: ".",  # VENOM_CLASS
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def action_table(env: Any) -> list[list[Any]]:
    table: list[list[Any]] = []
    for index, action in enumerate(env.actions):
        table.append([index, f"{action.__class__.__name__}.{action.name}", int(action.value)])
    return table


def normalise_reset(result: Any) -> dict[str, Any]:
    if isinstance(result, tuple):
        return dict(result[0])
    return dict(result)


def to_json_array(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def bytes_to_text(value: Any) -> str:
    flat = to_json_array(value)
    if isinstance(flat, list):
        raw = bytes(int(entry) for entry in flat if isinstance(entry, int))
        return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
    return str(flat)


def project(observation: dict[str, Any]) -> dict[str, Any]:
    raw_message = [int(entry) for entry in to_json_array(observation.get("message", []))]
    return {
        "chars": to_json_array(observation.get("chars", [])),
        "colors": to_json_array(observation.get("colors", [])),
        "glyphs": to_json_array(observation.get("glyphs", [])),
        "specials": to_json_array(observation.get("specials", [])),
        "blstats": to_json_array(observation.get("blstats", [])),
        "message": " ".join(bytes_to_text(raw_message).split()),
        "message_raw": raw_message,
        "inventory": {
            "inv_letters": to_json_array(observation.get("inv_letters", [])),
            "inv_glyphs": to_json_array(observation.get("inv_glyphs", [])),
            "inv_oclasses": to_json_array(observation.get("inv_oclasses", [])),
            "inv_strs": to_json_array(observation.get("inv_strs", [])),
        },
        "tty_chars": to_json_array(observation.get("tty_chars", [])),
        "tty_colors": to_json_array(observation.get("tty_colors", [])),
        "tty_cursor_yx": to_json_array(observation.get("tty_cursor", [])),
    }


def _plane_rows(value: Any, *, height: int, width: int, fill: int) -> list[list[int]]:
    rows = to_json_array(value)
    result: list[list[int]] = []
    for row in rows[:height] if isinstance(rows, list) else []:
        cells = row if isinstance(row, list) else []
        result.append(([int(cell) for cell in cells[:width]] + [fill] * width)[:width])
    while len(result) < height:
        result.append([fill] * width)
    return result


def _visibility_mask(projection: dict[str, Any], *, unseen_glyph: int | None) -> list[list[bool]]:
    chars = projection["chars"]
    glyphs = projection["glyphs"]
    height = len(chars) if isinstance(chars, list) else 0
    width = max((len(row) for row in chars if isinstance(row, list)), default=0)
    char_rows = _plane_rows(chars, height=height, width=width, fill=ord(" "))
    glyph_rows = _plane_rows(glyphs, height=height, width=width, fill=unseen_glyph if unseen_glyph is not None else 0)
    return [
        [
            (glyph_rows[y][x] != unseen_glyph) if unseen_glyph is not None else (char_rows[y][x] != ord(" "))
            for x in range(width)
        ]
        for y in range(height)
    ]


def _capture_planes(initial_projection: dict[str, Any], projections: list[dict[str, Any]], *, unseen_glyph: int | None) -> dict[str, Any]:
    """Separate static cells discovered by a tape from its initial FOW planes."""

    initial_chars = to_json_array(initial_projection["chars"])
    height = len(initial_chars) if isinstance(initial_chars, list) else 0
    width = max((len(row) for row in initial_chars if isinstance(row, list)), default=0)
    terrain_cells = _plane_rows(initial_projection["chars"], height=height, width=width, fill=ord(" "))
    static_glyphs = _plane_rows(initial_projection["glyphs"], height=height, width=width, fill=0)
    static_colors = _plane_rows(initial_projection["colors"], height=height, width=width, fill=0)
    initial_seen = _visibility_mask(initial_projection, unseen_glyph=unseen_glyph)
    for y in range(height):
        for x in range(width):
            char = chr(terrain_cells[y][x])
            if char not in STATIC_TERRAIN_CHARS:
                terrain_cells[y][x] = ord(" ")
                static_glyphs[y][x] = 0
                static_colors[y][x] = 0
    for projection in projections[1:]:
        chars = _plane_rows(projection["chars"], height=height, width=width, fill=ord(" "))
        glyphs = _plane_rows(projection["glyphs"], height=height, width=width, fill=0)
        colors = _plane_rows(projection["colors"], height=height, width=width, fill=0)
        visible = _visibility_mask(projection, unseen_glyph=unseen_glyph)
        for y in range(height):
            for x in range(width):
                char = chr(chars[y][x])
                if not visible[y][x] or char not in STATIC_TERRAIN_CHARS:
                    continue
                if terrain_cells[y][x] == ord(" "):
                    terrain_cells[y][x] = chars[y][x]
                    static_glyphs[y][x] = glyphs[y][x]
                    static_colors[y][x] = colors[y][x]
    return {
        "terrain": ["".join(chr(cell) for cell in row) for row in terrain_cells],
        "glyphs": static_glyphs,
        "colors": static_colors,
        "seen": initial_seen,
        "unseen": {
            "chars": initial_projection["chars"],
            "glyphs": initial_projection["glyphs"],
            "colors": initial_projection["colors"],
        },
    }


def _apply_terrain_underlay(dump: dict[str, Any], annotations: dict[str, Any], initial_projection: dict[str, Any]) -> None:
    """Materialize static cells hidden beneath visible reset entities only."""

    underlay = annotations.get("terrain_underlay")
    if underlay is None:
        return
    if not isinstance(underlay, list):
        raise ValueError("terrain_underlay annotations must be a list")
    terrain = [list(row) for row in dump["terrain"]]
    glyphs = dump["glyphs"]
    colors = dump["colors"]
    initial_chars = _plane_rows(initial_projection["chars"], height=len(terrain), width=len(terrain[0]) if terrain else 0, fill=ord(" "))
    claimed: set[tuple[int, int]] = set()
    for entry in underlay:
        if not isinstance(entry, dict):
            raise ValueError("terrain_underlay entries must be objects")
        x, y = entry.get("x"), entry.get("y")
        char, glyph, color = entry.get("char"), entry.get("glyph"), entry.get("color")
        if type(x) is not int or type(y) is not int or not (0 <= y < len(terrain) and 0 <= x < len(terrain[y])):
            raise ValueError("terrain_underlay entry has an out-of-bounds position")
        if (x, y) in claimed:
            raise ValueError("terrain_underlay may not assign a cell twice")
        if not isinstance(char, str) or len(char) != 1 or char not in STATIC_TERRAIN_CHARS:
            raise ValueError("terrain_underlay char must be a static terrain character")
        if type(glyph) is not int or type(color) is not int:
            raise ValueError("terrain_underlay glyph and color must be integers")
        initial_char = chr(initial_chars[y][x])
        if not dump["seen"][y][x] or initial_char in STATIC_TERRAIN_CHARS or initial_char in {" ", "@"}:
            raise ValueError("terrain_underlay may fill only a visible reset monster or item cell")
        claimed.add((x, y))
        terrain[y][x] = char
        glyphs[y][x] = glyph
        colors[y][x] = color
    dump["terrain"] = ["".join(row) for row in terrain]


def _captured_inventory_items(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn directly observed NLE inventory arrays into owned generic items."""

    letters = inventory.get("inv_letters", [])
    glyphs = inventory.get("inv_glyphs", [])
    oclasses = inventory.get("inv_oclasses", [])
    strings = inventory.get("inv_strs", [])
    rows = [value for value in (letters, glyphs, oclasses, strings) if isinstance(value, list)]
    items: list[dict[str, Any]] = []
    for index in range(max((len(row) for row in rows), default=0)):
        raw_letter = letters[index] if isinstance(letters, list) and index < len(letters) else 0
        if type(raw_letter) is not int or raw_letter == 0:
            continue
        letter = chr(raw_letter)
        raw_name = bytes_to_text(strings[index]) if isinstance(strings, list) and index < len(strings) else ""
        name = raw_name.split(" - ", 1)[-1] if raw_name else "unknown object"
        raw_oclass = oclasses[index] if isinstance(oclasses, list) and index < len(oclasses) else ord(")")
        oclass = int(raw_oclass) if type(raw_oclass) is int else ord(")")
        kind = NLE_OCLASS_TO_KIND.get(oclass, chr(oclass) if 32 <= oclass <= 126 else ")")
        raw_glyph = glyphs[index] if isinstance(glyphs, list) and index < len(glyphs) else ord(kind)
        glyph = int(raw_glyph) if type(raw_glyph) is int else ord(kind)
        items.append({"id": f"nle-inventory-{index}", "letter": letter, "kind": kind, "name": name, "glyph": glyph, "oclass_code": oclass})
    return items


def level_dump(
    observation: dict[str, Any],
    annotations: dict[str, Any],
    *,
    observations: list[dict[str, Any]] | None = None,
    unseen_glyph: int | None = None,
) -> dict[str, Any]:
    projection = project(observation)
    projections = [project(entry) for entry in (observations or [observation])]
    planes = _capture_planes(projection, projections, unseen_glyph=unseen_glyph)
    glyphs = planes["glyphs"]
    colors = planes["colors"]
    initial_glyphs = projection["glyphs"]
    initial_colors = projection["colors"]
    blstats = projection["blstats"]
    x = int(blstats[0]) if len(blstats) > 0 else 0
    y = int(blstats[1]) if len(blstats) > 1 else 0
    hero_glyph = int(initial_glyphs[y][x]) if y < len(initial_glyphs) and x < len(initial_glyphs[y]) else ord("@")
    hero_color = int(initial_colors[y][x]) if y < len(initial_colors) and x < len(initial_colors[y]) else 15
    dump = {
        "schema": "gamebench.nethack.level_dump.v1",
        "terrain": planes["terrain"],
        "glyphs": glyphs,
        "colors": colors,
        "seen": planes["seen"],
        "unseen": planes["unseen"],
        "hero": {"x": x, "y": y, "glyph": hero_glyph, "color": hero_color},
        "metadata": {
            "hp": int(blstats[10]) if len(blstats) > 10 else 1,
            "hp_max": int(blstats[11]) if len(blstats) > 11 else 1,
            "gold": int(blstats[13]) if len(blstats) > 13 else 0,
            "energy": int(blstats[14]) if len(blstats) > 14 else 0,
            "energy_max": int(blstats[15]) if len(blstats) > 15 else 0,
            "ac": int(blstats[16]) if len(blstats) > 16 else 10,
            "experience_level": int(blstats[18]) if len(blstats) > 18 else 1,
            "experience": int(blstats[19]) if len(blstats) > 19 else 0,
            "hunger": 900,
            "nle_blstats": blstats,
            "nle_message_raw": projection["message_raw"],
            "nle_inventory": projection["inventory"],
        },
        "objects": [],
        "inventory": _captured_inventory_items(projection["inventory"]),
        "monsters": [],
        "traps": [],
    }
    _apply_terrain_underlay(dump, annotations, projection)
    # Raw screen arrays do not expose monster hit points or object identities.
    # Annotations can materialize only owned entities needed by a tape.  They
    # cannot replace the captured reset projection or choose later visibility.
    unknown_annotation_keys = set(annotations) - (ANNOTATION_ENTITY_KEYS | {"terrain_underlay"})
    if unknown_annotation_keys:
        raise ValueError(f"unsupported annotation keys: {', '.join(sorted(unknown_annotation_keys))}")
    for key in ANNOTATION_ENTITY_KEYS:
        if key in annotations:
            dump[key] = annotations[key]
    return dump


def read_actions(path: Path) -> list[int]:
    actions: list[int] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, int):
            actions.append(value)
        elif isinstance(value, dict) and "action_id" in value:
            actions.append(int(value["action_id"]))
        else:
            raise ValueError(f"unsupported action tape line: {value!r}")
    return actions


def deterministic_nle_seeds(seed: int) -> tuple[int, int]:
    """Pin both NetHack RNGs; NLE otherwise samples the display RNG itself."""

    core = int(seed) & NLE_SEED_MASK
    return core, (core ^ DISPLAY_SEED_XOR) & NLE_SEED_MASK


def hero_position(observation: dict[str, Any]) -> tuple[int, int] | None:
    projected = project(observation)
    blstats = projected["blstats"]
    if len(blstats) < 2:
        return None
    return int(blstats[0]), int(blstats[1])


def dungeon_identity(observation: dict[str, Any]) -> tuple[int, ...]:
    """Read only NLE blstats to keep an unexpected descent out of the capture."""

    raw_blstats = to_json_array(observation.get("blstats", []))
    if not isinstance(raw_blstats, list):
        return ()
    blstats = [int(value) for value in raw_blstats]
    if len(blstats) >= 25:
        return int(blstats[23]), int(blstats[24])
    if len(blstats) >= 13:
        return (int(blstats[12]),)
    return ()


def visible_down_stairs(observation: dict[str, Any]) -> set[tuple[int, int]]:
    """Return down-stair coordinates seen before a hero glyph can cover them."""

    projected = project(observation)
    chars = projected["chars"]
    return {
        (x, y)
        for y, row in enumerate(chars)
        if isinstance(row, list)
        for x, cell in enumerate(row)
        if int(cell) == ord(">")
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--actions", type=Path, required=True, help="JSONL of NLE action-space indices or {action_id: ...} records")
    parser.add_argument("--output", type=Path, required=True, help="Explicit out-of-tree staging directory; reviewed promotion into fixtures/nle_oracle is manual.")
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--annotations", type=Path, default=None, help="Optional JSON entity annotations and constrained static terrain underlay")
    parser.add_argument("--accept-action-map-drift", action="store_true")
    args = parser.parse_args()
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:
        raise SystemExit("NLE capture requires optional dev dependency nle==0.9.0; gold replay does not. Install it in a dedicated capture environment and rerun.") from error

    output = args.output.resolve()
    if output == TASK_DIR.resolve() or TASK_DIR.resolve() in output.parents:
        raise SystemExit("--output must be outside the task directory; candidate captures require explicit review before canonical promotion")
    if not FIXTURE_ID.fullmatch(args.fixture_id):
        raise SystemExit("--fixture-id may contain only letters, digits, '.', '_', and '-'")
    if output.exists():
        raise SystemExit("--output must not already exist; capture into a new staging directory")
    annotations = json.loads(args.annotations.read_text()) if args.annotations else {}
    if not isinstance(annotations, dict):
        raise SystemExit("--annotations must contain a JSON object")
    env = nle.env.NLE(
        character=args.character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    core_seed, display_seed = deterministic_nle_seeds(args.seed)
    if hasattr(env, "seed"):
        seeded = env.seed(core=core_seed, disp=display_seed, reseed=False)
    else:
        seeded = (core_seed, display_seed, False)
    observation = normalise_reset(env.reset())
    if dungeon_identity(observation) != (0, 1):
        raise RuntimeError(f"capture must start on Main Dungeon dlvl 1, got {dungeon_identity(observation)!r}")
    initial_observation = deepcopy(observation)
    observations = [deepcopy(observation)]
    unseen_glyph = int(getattr(nethack, "GLYPH_CMAP_OFF", -1))
    known_down_stairs = visible_down_stairs(observation)
    table = action_table(env)
    expected_table = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())["actions"]
    table_hash = hashlib.sha256(canonical_json(table).encode("utf-8")).hexdigest()
    expected_hash = hashlib.sha256(canonical_json(expected_table).encode("utf-8")).hexdigest()
    if table_hash != expected_hash and not args.accept_action_map_drift:
        raise SystemExit(f"NLE action table drift: capture={table_hash} pinned={expected_hash}. Refuse capture; update the pinned map deliberately or pass --accept-action-map-drift for investigation.")
    actions = read_actions(args.actions)
    snapshots = [{"step": 0, "projection": project(observation), "done": False, "terminal_reason": ""}]
    action_records: list[dict[str, Any]] = []
    for step, action_id in enumerate(actions, start=1):
        if not 0 <= action_id < len(table):
            raise ValueError(f"action id {action_id} is outside NLE action table length {len(table)}")
        action_name = table[action_id][1]
        known_down_stairs.update(visible_down_stairs(observation))
        pre_action_projection = project(observation)
        pre_action_position = hero_position(observation)
        if action_name == "MiscDirection.DOWN":
            if pre_action_position not in known_down_stairs:
                raise RuntimeError("DOWN requires an earlier raw visible Main Dungeon dlvl-1 stair; refuse to step NLE across an unauditable boundary")
            action_records.append({"step": step, "action_id": action_id, "action_name": action_name, "boundary": "dlvl1_descend", "observed_down_stair": {"x": pre_action_position[0], "y": pre_action_position[1]}})
            snapshots.append({"step": step, "projection": pre_action_projection, "done": True, "terminal_reason": "descended", "oracle_boundary": "pre_dlvl2"})
            observations.append(deepcopy(observation))
            break
        stepped = env.step(action_id)
        if isinstance(stepped, tuple) and len(stepped) >= 3:
            next_observation = dict(stepped[0])
            done = bool(stepped[2])
        else:
            next_observation = dict(stepped)
            done = False
        if dungeon_identity(next_observation) != (0, 1):
            raise RuntimeError(f"capture left Main Dungeon dlvl 1 after {action_name}; refuse out-of-scope fixture")
        observation = next_observation
        observations.append(deepcopy(observation))
        known_down_stairs.update(visible_down_stairs(observation))
        action_records.append({"step": step, "action_id": action_id, "action_name": action_name})
        snapshots.append({"step": step, "projection": project(observation), "done": done, "terminal_reason": "death" if done else ""})
        if done:
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=f".{args.fixture_id}.capture-") as temporary:
        staged = Path(temporary) / args.fixture_id
        staged.mkdir()
        (staged / "meta.json").write_text(json.dumps({"schema": "gamebench.nethack.nle_capture.v1", "fixture_id": args.fixture_id, "nle_version": getattr(nle, "__version__", "unknown"), "nethack_version": "3.6.6", "character": {"nle_character": args.character}, "seed": args.seed, "nle_seeds": {"core": int(seeded[0]), "display": int(seeded[1]), "reseed": bool(seeded[2])}, "observation_keys": OBSERVATION_KEYS, "auto_more": "raw_explicit", "unseen_glyph": unseen_glyph, "action_table": table, "action_table_sha256": table_hash}, indent=2, sort_keys=True) + "\n")
        (staged / "level_dump.json").write_text(json.dumps(level_dump(initial_observation, annotations, observations=observations, unseen_glyph=unseen_glyph), indent=2, sort_keys=True) + "\n")
        (staged / "actions.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in action_records))
        (staged / "snapshots.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in snapshots))
        staged.replace(output)
    print(json.dumps({"fixture": str(output), "actions": len(action_records), "snapshots": len(snapshots), "action_table_sha256": table_hash}, sort_keys=True))


if __name__ == "__main__":
    main()
