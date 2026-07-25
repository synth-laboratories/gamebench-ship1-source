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
import sys
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


def level_dump(observation: dict[str, Any], annotations: dict[str, Any]) -> dict[str, Any]:
    projection = project(observation)
    chars = projection["chars"]
    glyphs = projection["glyphs"]
    colors = projection["colors"]
    blstats = projection["blstats"]
    x = int(blstats[0]) if len(blstats) > 0 else 0
    y = int(blstats[1]) if len(blstats) > 1 else 0
    hero_glyph = int(glyphs[y][x]) if y < len(glyphs) and x < len(glyphs[y]) else ord("@")
    hero_color = int(colors[y][x]) if y < len(colors) and x < len(colors[y]) else 15
    terrain = ["".join(chr(int(cell)) for cell in row) for row in chars]
    dump = {
        "schema": "gamebench.nethack.level_dump.v1",
        "terrain": terrain,
        "glyphs": glyphs,
        "colors": colors,
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
        },
        "objects": [],
        "inventory": [],
        "monsters": [],
        "traps": [],
    }
    # Raw screen arrays do not expose monster hit points or object identities.
    # Fixture authors may add only those NLE-observed/annotated entities needed
    # by a tape; annotations are preserved verbatim in the frozen dump.
    for key in ("objects", "inventory", "monsters", "traps", "seen", "metadata"):
        if key in annotations:
            if key == "metadata":
                dump[key] = {**dump[key], **dict(annotations[key])}
            else:
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
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--annotations", type=Path, default=None, help="Optional JSON entity annotations for dynamics absent from screen observations")
    parser.add_argument("--accept-action-map-drift", action="store_true")
    args = parser.parse_args()
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:
        raise SystemExit("NLE capture requires optional dev dependency nle==0.9.0; gold replay does not. Install it in a dedicated capture environment and rerun.") from error

    output = args.output or TASK_DIR / "fixtures" / "nle_oracle" / args.fixture_id
    annotations = json.loads(args.annotations.read_text()) if args.annotations else {}
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
    initial_observation = deepcopy(observation)
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
        if action_name == "MiscDirection.DOWN":
            position = hero_position(observation)
            if position in known_down_stairs:
                action_records.append({"step": step, "action_id": action_id, "action_name": action_name, "boundary": "dlvl1_descend"})
                snapshots.append({"step": step, "projection": pre_action_projection, "done": True, "terminal_reason": "descended", "oracle_boundary": "pre_dlvl2"})
                break
        pre_action_dungeon = dungeon_identity(observation)
        stepped = env.step(action_id)
        if isinstance(stepped, tuple) and len(stepped) >= 3:
            next_observation = dict(stepped[0])
            done = bool(stepped[2])
        else:
            next_observation = dict(stepped)
            done = False
        if action_name == "MiscDirection.DOWN" and dungeon_identity(next_observation) != pre_action_dungeon:
            action_records.append({"step": step, "action_id": action_id, "action_name": action_name, "boundary": "dlvl1_descend"})
            snapshots.append({"step": step, "projection": pre_action_projection, "done": True, "terminal_reason": "descended", "oracle_boundary": "pre_dlvl2"})
            break
        observation = next_observation
        known_down_stairs.update(visible_down_stairs(observation))
        action_records.append({"step": step, "action_id": action_id, "action_name": action_name})
        snapshots.append({"step": step, "projection": project(observation), "done": done, "terminal_reason": "death" if done else ""})
        if done:
            break
    output.mkdir(parents=True, exist_ok=True)
    (output / "meta.json").write_text(json.dumps({"schema": "gamebench.nethack.nle_capture.v1", "fixture_id": args.fixture_id, "nle_version": getattr(nle, "__version__", "unknown"), "nethack_version": "3.6.6", "character": {"nle_character": args.character}, "seed": args.seed, "nle_seeds": {"core": int(seeded[0]), "display": int(seeded[1]), "reseed": bool(seeded[2])}, "observation_keys": OBSERVATION_KEYS, "auto_more": "raw_explicit", "action_table": table, "action_table_sha256": table_hash}, indent=2, sort_keys=True) + "\n")
    (output / "level_dump.json").write_text(json.dumps(level_dump(initial_observation, annotations), indent=2, sort_keys=True) + "\n")
    (output / "actions.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in action_records))
    (output / "snapshots.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in snapshots))
    print(json.dumps({"fixture": str(output), "actions": len(action_records), "snapshots": len(snapshots), "action_table_sha256": table_hash}, sort_keys=True))


if __name__ == "__main__":
    main()
