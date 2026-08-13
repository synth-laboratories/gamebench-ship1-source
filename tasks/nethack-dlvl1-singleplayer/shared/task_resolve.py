"""Resolve a capture-backed NetHack dlvl-1 task without importing NLE."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
NLE_ORACLE_DIR = TASK_DIR / "fixtures" / "nle_oracle"
PROCEDURAL_SPECIES_PATH = TASK_DIR / "shared" / "procedural_species.json"
PROCEDURAL_POPULATION_PATH = TASK_DIR / "shared" / "procedural_population.json"
VIEW_HEIGHT = 21
VIEW_WIDTH = 79


def _load_procedural_species_table() -> dict[str, Any]:
    table = json.loads(PROCEDURAL_SPECIES_PATH.read_text(encoding="utf-8"))
    if table.get("schema") != "gamebench.nethack.procedural_species.v1":
        raise ValueError("procedural species table schema is unsupported")
    bound = table.get("selector_bound")
    entries = table.get("entries")
    if type(bound) is not int or bound <= 0 or not isinstance(entries, list) or not entries:
        raise ValueError("procedural species table is malformed")
    previous = 0
    for entry in entries:
        upper = entry.get("upper_exclusive") if isinstance(entry, dict) else None
        profile = entry.get("profile") if isinstance(entry, dict) else None
        if type(upper) is not int or upper <= previous or upper > bound or not isinstance(profile, dict):
            raise ValueError("procedural species interval is malformed")
        population_fields = ("geno", "generation_frequency", "corpse_weight", "no_corpse")
        if any(field not in profile for field in population_fields):
            raise ValueError("procedural species population metadata is incomplete")
        geno = profile["geno"]
        generation_frequency = profile["generation_frequency"]
        corpse_weight = profile["corpse_weight"]
        no_corpse = profile["no_corpse"]
        if (
            type(geno) is not int
            or not 0 <= geno <= 0xFFFF
            or type(generation_frequency) is not int
            or not 0 <= generation_frequency <= 7
            or generation_frequency != (geno & 0x0007)
            or type(corpse_weight) is not int
            or not 0 <= corpse_weight <= 0xFFFF
            or type(no_corpse) is not bool
            or no_corpse != bool(geno & 0x0010)
        ):
            raise ValueError("procedural species population metadata is inconsistent")
        previous = upper
    if previous != bound:
        raise ValueError("procedural species intervals do not cover the selector")
    return table


PROCEDURAL_SPECIES_TABLE = _load_procedural_species_table()


def procedural_species_profile(selector: int) -> dict[str, Any]:
    """Return one source-derived low-level physical species profile."""

    bound = int(PROCEDURAL_SPECIES_TABLE["selector_bound"])
    value = int(selector)
    if not 0 <= value < bound:
        raise ValueError(f"procedural species selector must be in [0,{bound})")
    for entry in PROCEDURAL_SPECIES_TABLE["entries"]:
        if value < int(entry["upper_exclusive"]):
            return deepcopy(entry["profile"])
    raise AssertionError("validated procedural species table has an uncovered selector")


def _load_procedural_population_table() -> dict[str, Any]:
    table = json.loads(PROCEDURAL_POPULATION_PATH.read_text(encoding="utf-8"))
    if table.get("schema") != "gamebench.nethack.procedural_population.v1":
        raise ValueError("procedural population table schema is unsupported")
    if table.get("source") != "nle-0.9.0/src/monst.c":
        raise ValueError("procedural population source pin is unsupported")
    bound = table.get("selector_bound")
    entries = table.get("entries")
    if type(bound) is not int or bound <= 0 or not isinstance(entries, list) or not entries:
        raise ValueError("procedural population table is malformed")
    previous = 0
    for entry in entries:
        upper = entry.get("upper_exclusive") if isinstance(entry, dict) else None
        profile = entry.get("profile") if isinstance(entry, dict) else None
        if type(upper) is not int or upper <= previous or upper > bound or not isinstance(profile, dict):
            raise ValueError("procedural population interval is malformed")
        population_fields = ("species_id", "geno", "generation_frequency", "corpse_weight", "no_corpse")
        if any(field not in profile for field in population_fields):
            raise ValueError("procedural population metadata is incomplete")
        geno = profile["geno"]
        frequency = profile["generation_frequency"]
        if (
            type(profile["species_id"]) is not int
            or profile["species_id"] < 0
            or type(geno) is not int
            or not 0 <= geno <= 0xFFFF
            or type(frequency) is not int
            or not 0 <= frequency <= 7
            or frequency != (geno & 0x0007)
            or type(profile["corpse_weight"]) is not int
            or profile["corpse_weight"] < 0
            or type(profile["no_corpse"]) is not bool
            or profile["no_corpse"] != bool(geno & 0x0010)
        ):
            raise ValueError("procedural population metadata is inconsistent")
        if not isinstance(profile.get("attacks"), list) or not profile["attacks"]:
            raise ValueError("procedural population combat metadata is incomplete")
        previous = upper
    if previous != bound:
        raise ValueError("procedural population intervals do not cover the selector")
    return table


PROCEDURAL_POPULATION_TABLE = _load_procedural_population_table()


def procedural_population_profile(selector: int) -> dict[str, Any]:
    """Return a source-pinned hostile population profile for generic play."""

    bound = int(PROCEDURAL_POPULATION_TABLE["selector_bound"])
    value = int(selector)
    if not 0 <= value < bound:
        raise ValueError(f"procedural population selector must be in [0,{bound})")
    for entry in PROCEDURAL_POPULATION_TABLE["entries"]:
        if value < int(entry["upper_exclusive"]):
            return deepcopy(entry["profile"])
    raise AssertionError("validated procedural population table has an uncovered selector")
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


def _normalise_presentation_overlays(raw: Any, *, seen: list[list[bool]], hero: dict[str, int]) -> list[dict[str, Any]]:
    """Validate reset-only visual markers that have no game semantics."""

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("presentation_overlays must be a list")
    overlays: list[dict[str, Any]] = []
    claimed: set[tuple[int, int]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("presentation_overlays entries must be objects")
        allowed = {"x", "y", "char", "glyph", "color", "special", "provenance", "presentation_class", "identity_status"}
        if not set(entry) <= allowed or not {"x", "y", "char", "glyph", "color", "provenance", "presentation_class", "identity_status"} <= set(entry):
            raise ValueError("presentation_overlay has unsupported semantic fields")
        x, y = entry.get("x"), entry.get("y")
        char, glyph, color = entry.get("char"), entry.get("glyph"), entry.get("color")
        if type(x) is not int or type(y) is not int or not (0 <= x < VIEW_WIDTH and 0 <= y < VIEW_HEIGHT):
            raise ValueError("presentation_overlay has an out-of-bounds position")
        if (x, y) == (hero["x"], hero["y"]) or (x, y) in claimed or not seen[y][x]:
            raise ValueError("presentation_overlay must occupy one visible non-hero reset cell")
        # Classification comes from the source glyph, not terminal text: an
        # object can legitimately render with a terrain-looking character.
        if not isinstance(char, str) or len(char) != 1 or char in {"@", " "}:
            raise ValueError("presentation_overlay char must be non-hero presentation")
        if type(glyph) is not int or type(color) is not int:
            raise ValueError("presentation_overlay glyph and color must be integers")
        if "special" in entry and (type(entry["special"]) is not int or not 0 <= int(entry["special"]) <= 255):
            raise ValueError("presentation_overlay special must be an unsigned byte")
        if entry.get("provenance") != "nle_reset_presentation" or entry.get("identity_status") != "unavailable_from_nle_presentation":
            raise ValueError("presentation_overlay must be reset-only and identity-unavailable")
        if not isinstance(entry.get("presentation_class"), str) or not entry["presentation_class"]:
            raise ValueError("presentation_overlay must retain a glyph-derived presentation class")
        claimed.add((x, y))
        normalized = deepcopy(entry)
        normalized.setdefault("special", 0)
        overlays.append(normalized)
    return overlays


def _normalise_pet_interaction_markers(
    raw: Any,
    *,
    seen: list[list[bool]],
    hero: dict[str, int],
    overlays: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate the tiny source-proven pet subset without making a Monster.

    Markers are valid only when NLE's own glyph mapping supplied the species
    name and the matching reset pixel remains present.  They are intentionally
    not part of ``monsters``: no collision, combat, pathing, or scheduling can
    be inferred from this source contract.
    """

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("pet_interaction_markers must be a list")
    pixels = {(item["x"], item["y"], item["char"], item["glyph"], item["color"]) for item in overlays}
    markers: list[dict[str, Any]] = []
    claimed: set[tuple[int, int]] = set()
    expected = {"id", "name", "x", "y", "char", "glyph", "color", "provenance", "identity_source"}
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != expected:
            raise ValueError("pet_interaction_marker has unsupported fields")
        x, y = entry.get("x"), entry.get("y")
        name, marker_id = entry.get("name"), entry.get("id")
        char, glyph, color = entry.get("char"), entry.get("glyph"), entry.get("color")
        if (
            type(x) is not int or type(y) is not int or not (0 <= x < VIEW_WIDTH and 0 <= y < VIEW_HEIGHT)
            or (x, y) == (hero["x"], hero["y"]) or (x, y) in claimed or not seen[y][x]
            or not isinstance(name, str) or not name or not isinstance(marker_id, str) or not marker_id
            or not isinstance(char, str) or len(char) != 1 or type(glyph) is not int or type(color) is not int
            or (x, y, char, glyph, color) not in pixels
            or entry.get("provenance") != "nle_reset_pet_glyph" or entry.get("identity_source") != "glyph_to_mon_permonst"
        ):
            raise ValueError("pet_interaction_marker must be a visible matching authoritative reset pet pixel")
        claimed.add((x, y))
        markers.append({
            "id": marker_id, "name": name, "pet": True,
            "position": {"x": x, "y": y}, "char": char, "glyph": glyph, "color": color,
            "provenance": "nle_reset_pet_glyph", "identity_source": "glyph_to_mon_permonst",
        })
    return markers


def _normalise_item(value: Any, *, index: int, floor: bool = False) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    position = _position(data.get("position", data.get("pos", data)))
    letter = str(data.get("letter", data.get("inv_letter", "")))[:1]
    kind = str(data.get("kind", data.get("oclass", data.get("class", ")"))))[:1] or ")"
    name = str(data.get("name", data.get("description", "unknown object")))
    item = {
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
    if "special" in data:
        special = int(data["special"])
        if not 0 <= special <= 255:
            raise ValueError("item special must be an unsigned byte")
        item["special"] = special
    if "weight" in data:
        item["weight"] = max(0, int(data["weight"]))
    if "damage_type" in data:
        damage_type = str(data["damage_type"]).strip().lower()
        if damage_type:
            item["damage_type"] = damage_type
    return item


def _normalise_monster(value: Any, *, index: int) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    if "base_speed" in data:
        incompatible = [
            field
            for field in ("speed", "turn_period", "turn_offset")
            if field in data
        ]
        if incompatible:
            raise ValueError(
                "monster base_speed cannot be combined with "
                + ", ".join(incompatible)
            )
    position = _position(data.get("position", data.get("pos", data)))
    char = str(data.get("char", data.get("symbol", "j")))[:1] or "j"
    hp = max(1, int(data.get("hp", 4)))
    monster = {
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
    if "species_id" in data:
        monster["species_id"] = max(0, int(data["species_id"]))
    for field in ("geno", "generation_frequency", "corpse_weight"):
        if field in data:
            monster[field] = max(0, int(data[field]))
    if "no_corpse" in data:
        monster["no_corpse"] = bool(data["no_corpse"])
    # Authored/open levels may opt into a portable attack-vs-defense model.
    # Keep the historical damage-only contract byte-for-byte unchanged for
    # old inputs and for all capture-backed reset actors.  An explicit combat
    # field is the evidence that the caller supplied enough semantics for the
    # generic model; a rendered monster glyph alone never enables it.
    combat_fields = {"armor_class", "level", "damage_dice", "damage_sides", "to_hit"}
    if str(data.get("combat_model", "")).lower() == "d20" or combat_fields.intersection(data):
        level = max(0, int(data.get("level", 1)))
        default_damage_sides = max(1, int(data.get("attack", 2)))
        monster.update(
            {
                "combat_model": "d20",
                "armor_class": int(data.get("armor_class", 10)),
                "level": level,
                "to_hit": int(data.get("to_hit", level)),
                "damage_dice": max(1, int(data.get("damage_dice", 1))),
                "damage_sides": max(1, int(data.get("damage_sides", default_damage_sides))),
            }
        )
    # Authored levels may opt into an explicit actor inventory/schedule. Keep
    # these fields absent for historical capture dumps so their private shape
    # and source-backed behavior remain unchanged.
    if "inventory" in data:
        monster["inventory"] = [
            _normalise_item(item, index=item_index)
            for item_index, item in enumerate(data.get("inventory", []))
        ]
    if "drops" in data:
        monster["drops"] = [
            _normalise_item(item, index=item_index, floor=True)
            for item_index, item in enumerate(data.get("drops", []))
        ]
    if "base_speed" in data:
        monster["base_speed"] = max(0, int(data["base_speed"]))
        monster["movement_points"] = max(0, int(data.get("movement_points", 0)))
    if "corpse" in data and data.get("corpse") not in (False, None):
        raw_corpse = data.get("corpse")
        if not isinstance(raw_corpse, (bool, dict)):
            raise ValueError("monster corpse must be a boolean or object")
        corpse = dict(raw_corpse) if isinstance(raw_corpse, dict) else {}
        corpse.setdefault("id", f"{monster['id']}-corpse")
        corpse.setdefault("kind", "%")
        corpse.setdefault("name", f"a {monster['name']} corpse")
        corpse.setdefault("nutrition", max(0, int(data.get("corpse_nutrition", 200))))
        monster["corpse"] = _normalise_item(corpse, index=index, floor=True)
    for field in (
        "pickup",
        "vision",
        "speed",
        "attack_range",
        "flee_distance",
        "turn_period",
        "turn_offset",
        "initiative",
        "hunger_drain",
        "eat_threshold",
        "starve_damage",
    ):
        if field in data:
            if field == "pickup":
                monster[field] = bool(data[field])
            elif field == "initiative":
                # Initiative is an ordering offset, so authored negative
                # values are meaningful and must remain signed.
                monster[field] = int(data[field])
            else:
                monster[field] = max(0, int(data[field]))
    if "movement" in data:
        monster["movement"] = str(data["movement"])
    if "opens_doors" in data:
        monster["opens_doors"] = bool(data["opens_doors"])
    if "see_invisible" in data:
        monster["see_invisible"] = bool(data["see_invisible"])
    if "attack_monsters" in data:
        monster["attack_monsters"] = bool(data["attack_monsters"])
    if "eat" in data:
        monster["eat"] = bool(data["eat"])
    if "hunger" in data:
        monster["hunger"] = max(0, int(data["hunger"]))
    if "hunger_max" in data:
        monster["hunger_max"] = max(0, int(data["hunger_max"]))
    if "flee" in data:
        monster["flee"] = bool(data["flee"])
    if "flee_turns" in data:
        monster["flee_turns"] = max(0, int(data["flee_turns"]))
    if "undead" in data:
        monster["undead"] = bool(data["undead"])
    if "turn_difficulty" in data:
        monster["turn_difficulty"] = max(0, int(data["turn_difficulty"]))
    if "chat" in data:
        raw_chat = data["chat"]
        if isinstance(raw_chat, list):
            monster["chat"] = [str(message) for message in raw_chat if str(message)]
        else:
            message = str(raw_chat)
            monster["chat"] = [message] if message else []
    if "mountable" in data:
        monster["mountable"] = bool(data["mountable"])
    if "special" in data:
        special = int(data["special"])
        if not 0 <= special <= 255:
            raise ValueError("monster special must be an unsigned byte")
        monster["special"] = special
    if isinstance(data.get("status_effects"), dict):
        monster["status_effects"] = {
            str(name): max(0, int(duration))
            for name, duration in data["status_effects"].items()
            if int(duration) > 0
        }
    if isinstance(data.get("resistances"), dict):
        monster["resistances"] = {
            str(damage_type).strip().lower(): max(0, min(100, int(reduction)))
            for damage_type, reduction in data["resistances"].items()
            if str(damage_type).strip()
        }
    if "attack_effect" in data:
        attack_effect = str(data.get("attack_effect", "")).strip().lower()
        if attack_effect:
            monster["attack_effect"] = attack_effect
    if "attack_effect_duration" in data:
        monster["attack_effect_duration"] = max(0, int(data["attack_effect_duration"]))
    if "death_effect" in data:
        death_effect = str(data.get("death_effect", "")).strip().lower()
        if death_effect:
            monster["death_effect"] = death_effect
    if "attacks" in data:
        raw_attacks = data["attacks"]
        if not isinstance(raw_attacks, list):
            raise ValueError("monster attacks must be a list")
        inherited_model = str(monster.get("combat_model", "damage"))
        inherited_dice = int(monster.get("damage_dice", 1))
        inherited_sides = int(monster.get("damage_sides", max(1, int(monster.get("attack", 2)))))
        inherited_to_hit = int(monster.get("to_hit", monster.get("level", 1)))
        inherited_effect = str(monster.get("attack_effect", ""))
        inherited_duration = int(monster.get("attack_effect_duration", 0))
        inherited_damage_type = str(data.get("damage_type", "")).strip().lower()
        attacks: list[dict[str, Any]] = []
        for attack_index, raw_attack in enumerate(raw_attacks):
            if not isinstance(raw_attack, dict):
                raise ValueError("monster attack entries must be objects")
            model = str(raw_attack.get("combat_model", inherited_model)).strip().lower()
            if model not in {"d20", "damage"}:
                raise ValueError("monster attack combat_model must be d20 or damage")
            attack_id = str(raw_attack.get("id", f"{monster['id']}-attack-{attack_index}"))
            attack_name = str(raw_attack.get("name", attack_id))
            if model == "d20":
                default_sides = inherited_sides
                default_flat = 0
            else:
                default_sides = 2
                default_flat = max(0, int(monster.get("attack", 2)) - 1)
            attack = {
                "id": attack_id,
                "name": attack_name,
                "combat_model": model,
                "damage_dice": max(1, int(raw_attack.get("damage_dice", inherited_dice if model == "d20" else 1))),
                "damage_sides": max(1, int(raw_attack.get("damage_sides", default_sides))),
                "damage": int(raw_attack.get("damage", raw_attack.get("flat_damage", default_flat))),
            }
            if model == "d20":
                attack["to_hit"] = int(raw_attack.get("to_hit", inherited_to_hit))
            damage_type = str(raw_attack.get("damage_type", inherited_damage_type)).strip().lower()
            if damage_type:
                attack["damage_type"] = damage_type
            effect = str(raw_attack.get("attack_effect", raw_attack.get("effect", inherited_effect))).strip().lower()
            if effect:
                attack["attack_effect"] = effect
                attack["attack_effect_duration"] = max(
                    0,
                    int(raw_attack.get("attack_effect_duration", raw_attack.get("effect_duration", inherited_duration))),
                )
            attacks.append(attack)
        monster["attacks"] = attacks
    return monster


def _normalise_trap(value: Any, *, index: int) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    trap = {
        "id": str(data.get("id", f"trap-{index}")),
        "kind": str(data.get("kind", "arrow")),
        "damage": max(0, int(data.get("damage", 2))),
        "seen": bool(data.get("seen", False)),
        "triggered": bool(data.get("triggered", False)),
        "position": _position(data.get("position", data.get("pos", data))),
    }
    if "effect" in data:
        trap["effect"] = str(data["effect"])
    if "damage_type" in data:
        damage_type = str(data["damage_type"]).strip().lower()
        if damage_type:
            trap["damage_type"] = damage_type
    if "damage_dice" in data or "damage_sides" in data:
        trap["damage_dice"] = max(1, int(data.get("damage_dice", 1)))
        trap["damage_sides"] = max(1, int(data.get("damage_sides", max(1, int(data.get("damage", 2))))))
    if "rearm" in data:
        trap["rearm"] = max(0, int(data["rearm"]))
    if "disarm_difficulty" in data:
        trap["disarm_difficulty"] = max(0, int(data["disarm_difficulty"]))
    if "one_shot" in data:
        trap["one_shot"] = bool(data["one_shot"])
    if "rearm" in data:
        # This is runtime state rather than a second authoring knob.  A trap
        # that is already triggered at reset starts its authored cooldown;
        # an armed trap begins at zero and receives the cooldown on trigger.
        trap["rearm_remaining"] = (
            0
            if bool(trap.get("one_shot", False))
            else max(0, int(data.get("rearm_remaining", data["rearm"] if trap["triggered"] else 0)))
        )
    elif "rearm_remaining" in data:
        trap["rearm_remaining"] = max(0, int(data["rearm_remaining"]))
    if "message" in data:
        trap["message"] = str(data["message"])
    return trap


def _normalise_engraving(value: Any, *, index: int) -> dict[str, Any]:
    """Normalize one authored floor engraving for the generic runtime."""

    data = dict(value) if isinstance(value, dict) else {}
    position = _position(data.get("position", data.get("pos", data)))
    text = str(data.get("text", data.get("message", "")))
    if not text:
        raise ValueError("engraving text must not be empty")
    if len(text) > 256:
        raise ValueError("engraving text is too long")
    return {
        "id": str(data.get("id", f"engraving-{index}")),
        "position": position,
        "text": text,
        "kind": str(data.get("kind", "dust")),
    }


def _normalise_light_source(value: Any, *, index: int, hero: dict[str, int]) -> dict[str, Any]:
    """Normalize one authored dynamic light source.

    A source may be fixed at ``position`` or follow ``hero``/an authored
    monster id.  ``duration`` is measured in consumed turns; an omitted
    duration is permanent for the episode.
    """

    data = dict(value) if isinstance(value, dict) else {}
    follow = data.get("follow")
    if follow is not None:
        follow = str(follow)
        if not follow:
            raise ValueError("light source follow must not be empty")
    has_position = any(key in data for key in ("position", "pos", "x", "y"))
    if not has_position and follow == "hero":
        position = {"x": int(hero["x"]), "y": int(hero["y"])}
    else:
        position = _position(data.get("position", data.get("pos", data)))
    if not (0 <= position["x"] < VIEW_WIDTH and 0 <= position["y"] < VIEW_HEIGHT):
        raise ValueError("light source position must be inside the 21x79 crop")
    duration = None if "duration" not in data or data.get("duration") is None else max(0, int(data["duration"]))
    active = bool(data.get("active", True)) and duration != 0
    return {
        "id": str(data.get("id", f"light-source-{index}")),
        "position": position,
        "radius": max(0, int(data.get("radius", 3))),
        "active": active,
        "duration": duration,
        "follow": follow,
    }


def normalise_level_dump(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-only 21×79 dump suitable for either independent gold lane."""

    data = dict(raw)
    forbidden_source_artifacts = {
        "native_reset_entity_state",
        "authoritative_reset_entity_state",
        "native_pre_action_evidence",
        "pre_action_records",
        "future_observation",
        "future_frames",
        "hydrated_from_step",
    }
    present_artifacts = sorted(forbidden_source_artifacts & set(data))
    if present_artifacts:
        raise ValueError("level_dump may not embed native receipts, pre-action sidecars, or future frames: " + ", ".join(present_artifacts))
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
    engravings = [
        _normalise_engraving(engraving, index=index)
        for index, engraving in enumerate(data.get("engravings", []))
    ]
    light_sources = [
        _normalise_light_source(source, index=index, hero=hero)
        for index, source in enumerate(data.get("light_sources", []))
    ]
    presentation_overlays = _normalise_presentation_overlays(data.get("presentation_overlays"), seen=seen, hero=hero)
    pet_interaction_markers = _normalise_pet_interaction_markers(
        data.get("pet_interaction_markers"), seen=seen, hero=hero, overlays=presentation_overlays,
    )
    if any(bool(branch) for branch in data.get("branches", [])) or data.get("mines_entry"):
        raise ValueError("dlvl-1 fixture contains a branch/Mines entry; reject it instead of modeling branch geography")
    depth = int(data.get("dungeon_level", data.get("depth", 1)))
    if depth != 1:
        raise ValueError(f"only Main Dungeon dlvl 1 is in scope, got level {depth}")
    metadata = deepcopy(dict(data.get("metadata", {})))
    authoritative_reset_entities = data.get("authoritative_reset_entities")
    if authoritative_reset_entities is not None:
        # The portable reset projection is task data, but only if it binds to
        # the public reset player/time and passes the same complete native
        # entity structure checks used by capture.  This validator does not
        # read a native receipt or any future action boundary.
        from scripts.native_reset_entity_state import validate_portable_reset_projection

        reset_blstats = metadata.get("nle_blstats")
        failures = validate_portable_reset_projection(
            authoritative_reset_entities,
            reset_projection={"blstats": reset_blstats},
        )
        if failures:
            raise ValueError("invalid authoritative_reset_entities: " + "; ".join(failures))
    authoritative_reset_rng = data.get("authoritative_reset_rng")
    if authoritative_reset_rng is not None:
        # This is the complete immutable state at reset, not an action-sidecar
        # or a native receipt.  Its validator proves algorithm/source pinning
        # and rejects all future-frame hydration fields before either lane can
        # consume it.
        from scripts.portable_reset_rng import validate_portable_reset_rng_projection

        failures = validate_portable_reset_rng_projection(authoritative_reset_rng)
        if failures:
            raise ValueError("invalid authoritative_reset_rng: " + "; ".join(failures))
    authoritative_reset_map = data.get("authoritative_reset_map")
    if authoritative_reset_map is not None:
        # Immutable reset topology is a separate portable projection.  It is
        # validated here before either gold lane can consume it, and may not
        # contain native receipts or any action-indexed/future visibility.
        from scripts.portable_reset_map import validate_portable_reset_map_projection

        failures = validate_portable_reset_map_projection(authoritative_reset_map)
        if failures:
            raise ValueError("invalid authoritative_reset_map: " + "; ".join(failures))

    result = {
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
        "engravings": engravings,
        "light_sources": light_sources,
        "presentation_overlays": presentation_overlays,
        "pet_interaction_markers": pet_interaction_markers,
        "dungeon_level": 1,
        "metadata": metadata,
    }
    if authoritative_reset_entities is not None:
        # Preserve exactly the already validated task projection.  It is not
        # translated into legacy ``monsters`` or presentation overlays.
        result["authoritative_reset_entities"] = deepcopy(authoritative_reset_entities)
    if authoritative_reset_rng is not None:
        result["authoritative_reset_rng"] = deepcopy(authoritative_reset_rng)
    if authoritative_reset_map is not None:
        result["authoritative_reset_map"] = deepcopy(authoritative_reset_map)
    return result


def procedural_level_dump(seed: int) -> dict[str, Any]:
    """Build a deterministic playable dlvl-1 when no capture is supplied.

    This is the authored/open-level bootstrap, not an attempt to claim that
    NetHack's private dungeon generator has been reconstructed.  The layout
    is fully causal: six rooms, closed doors, connecting corridors, stairs,
    ordinary objects, traps, and explicit combat data.  Generation consumes
    exactly 56 LCG draws for every seed.
    """

    state = int(seed) & 0xFFFFFFFF
    draw_count = 0

    def draw(upper: int) -> int:
        nonlocal state, draw_count
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        draw_count += 1
        return state % max(1, upper)

    terrain = [[" "] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]

    slot_x_bounds = ((2, 24), (28, 50), (54, 76))
    slot_y_bounds = ((1, 9), (11, 19))
    rooms: list[dict[str, Any]] = []
    for row, (slot_top, slot_bottom) in enumerate(slot_y_bounds):
        for column, (slot_left, slot_right) in enumerate(slot_x_bounds):
            interior_width = 4 + draw(7)
            interior_height = 3 + draw(3)
            slot_width = slot_right - slot_left + 1
            slot_height = slot_bottom - slot_top + 1
            outer_left = slot_left + draw(slot_width - interior_width - 1)
            outer_top = slot_top + draw(slot_height - interior_height - 1)
            outer_right = outer_left + interior_width + 1
            outer_bottom = outer_top + interior_height + 1
            room_id = row * 3 + column
            room = {
                "id": f"generated-room-{room_id}",
                "outer": {
                    "left": outer_left,
                    "right": outer_right,
                    "top": outer_top,
                    "bottom": outer_bottom,
                },
                "interior": {
                    "left": outer_left + 1,
                    "right": outer_right - 1,
                    "top": outer_top + 1,
                    "bottom": outer_bottom - 1,
                },
            }
            rooms.append(room)
            for x in range(outer_left, outer_right + 1):
                terrain[outer_top][x] = "-"
                terrain[outer_bottom][x] = "-"
            for y in range(outer_top + 1, outer_bottom):
                terrain[y][outer_left] = "|"
                terrain[y][outer_right] = "|"
                for x in range(outer_left + 1, outer_right):
                    terrain[y][x] = "."

    primary_column = draw(3)
    extra_enabled = draw(2)
    extra_offset = 1 + draw(2)
    extra_column = (primary_column + extra_offset) % 3
    candidate_edges = [
        (0, 1, "horizontal"),
        (1, 2, "horizontal"),
        (3, 4, "horizontal"),
        (4, 5, "horizontal"),
        (primary_column, primary_column + 3, "vertical"),
        (extra_column, extra_column + 3, "vertical"),
    ]
    doors: list[dict[str, Any]] = []
    legacy_door_ids = (
        "generated-left-door",
        "generated-right-door",
        "generated-middle-door",
    )

    def carve_corridor(points: list[tuple[int, int]]) -> None:
        for x, y in points:
            if terrain[y][x] in {" ", "#"}:
                terrain[y][x] = "#"

    for edge_index, (source_id, target_id, orientation) in enumerate(candidate_edges):
        source = rooms[source_id]
        target = rooms[target_id]
        if orientation == "horizontal":
            source_height = source["interior"]["bottom"] - source["interior"]["top"] + 1
            target_height = target["interior"]["bottom"] - target["interior"]["top"] + 1
            source_offset = draw(source_height)
            target_offset = draw(target_height)
            source_door = (
                source["outer"]["right"],
                source["interior"]["top"] + source_offset,
            )
            target_door = (
                target["outer"]["left"],
                target["interior"]["top"] + target_offset,
            )
            source_exterior = (source_door[0] + 1, source_door[1])
            target_exterior = (target_door[0] - 1, target_door[1])
            midpoint = (source_exterior[0] + target_exterior[0]) // 2
            path = [
                *((x, source_exterior[1]) for x in range(source_exterior[0], midpoint + 1)),
                *((midpoint, y) for y in range(
                    min(source_exterior[1], target_exterior[1]),
                    max(source_exterior[1], target_exterior[1]) + 1,
                )),
                *((x, target_exterior[1]) for x in range(midpoint, target_exterior[0] + 1)),
            ]
        else:
            source_width = source["interior"]["right"] - source["interior"]["left"] + 1
            target_width = target["interior"]["right"] - target["interior"]["left"] + 1
            source_offset = draw(source_width)
            target_offset = draw(target_width)
            source_door = (
                source["interior"]["left"] + source_offset,
                source["outer"]["bottom"],
            )
            target_door = (
                target["interior"]["left"] + target_offset,
                target["outer"]["top"],
            )
            source_exterior = (source_door[0], source_door[1] + 1)
            target_exterior = (target_door[0], target_door[1] - 1)
            midpoint = (source_exterior[1] + target_exterior[1]) // 2
            path = [
                *((source_exterior[0], y) for y in range(source_exterior[1], midpoint + 1)),
                *((x, midpoint) for x in range(
                    min(source_exterior[0], target_exterior[0]),
                    max(source_exterior[0], target_exterior[0]) + 1,
                )),
                *((target_exterior[0], y) for y in range(midpoint, target_exterior[1] + 1)),
            ]

        active = edge_index < 5 or bool(extra_enabled)
        if not active:
            continue
        for side, (x, y) in enumerate((source_door, target_door)):
            terrain[y][x] = "+"
            door_number = len(doors)
            doors.append({
                "id": (
                    legacy_door_ids[door_number]
                    if door_number < len(legacy_door_ids)
                    else f"generated-door-{edge_index}-{side}"
                ),
                "position": {"x": x, "y": y},
                "locked": False,
                "trapped": False,
                "open": False,
            })
        carve_corridor(path)

    reserved: set[tuple[int, int]] = set()

    def place_in_room(room_id: int) -> tuple[int, int]:
        interior = rooms[room_id]["interior"]
        width = interior["right"] - interior["left"] + 1
        height = interior["bottom"] - interior["top"] + 1
        area = width * height
        start = draw(area)
        for offset in range(area):
            index = (start + offset) % area
            position = (
                interior["left"] + index % width,
                interior["top"] + index // width,
            )
            if position not in reserved:
                reserved.add(position)
                return position
        raise AssertionError(f"generated room {room_id} has no unreserved interior cell")

    hero_x, hero_y = place_in_room(0)
    stair_x, stair_y = place_in_room(5)
    monster_one_x, monster_one_y = place_in_room(1)
    monster_two_x, monster_two_y = place_in_room(2)
    gold_x, gold_y = place_in_room(3)
    pet_x, pet_y = place_in_room(3)
    trap_x, trap_y = place_in_room(4)
    monster_three_x, monster_three_y = place_in_room(4)
    potion_x, potion_y = place_in_room(5)
    terrain[hero_y][hero_x] = "<"
    terrain[stair_y][stair_x] = ">"

    gold_quantity = 10 + draw(40)
    pet_speed_selector = draw(2)
    pet_base_speed = 12 if pet_speed_selector == 0 else 18
    pet_nutrition = 300 + draw(301)
    light_radius = 2 + draw(3)
    trap_effect = "poison" if draw(2) else ""
    hostile_profiles = [procedural_species_profile(draw(16)) for _ in range(3)]
    if draw_count != 56:
        raise AssertionError(f"procedural generation consumed {draw_count} draws instead of 56")
    seen = [
        [max(abs(x - hero_x), abs(y - hero_y)) <= 5 for x in range(VIEW_WIDTH)]
        for y in range(VIEW_HEIGHT)
    ]

    return {
        "terrain": ["".join(row) for row in terrain],
        "seen": seen,
        "hero": {"x": hero_x, "y": hero_y},
        "objects": [
            {
                "id": "generated-gold",
                "position": {"x": gold_x, "y": gold_y},
                "kind": "$",
                "name": "gold piece",
                "quantity": gold_quantity,
            },
            {
                "id": "generated-potion",
                "position": {"x": potion_x, "y": potion_y},
                "kind": "!",
                "name": "a potion of healing",
                "effect": "healing",
            },
            {
                "id": "generated-pet-ration",
                "position": {"x": pet_x, "y": pet_y},
                "kind": "%",
                "name": "a pet ration",
                "nutrition": pet_nutrition,
            },
        ],
        "inventory": [
            {"id": "generated-dagger", "letter": "a", "kind": ")", "name": "a dagger", "damage": 2},
            {"id": "generated-ration", "letter": "b", "kind": "%", "name": "a food ration", "nutrition": 600},
        ],
        "monsters": [
            {
                "id": "generated-hostile-1",
                **hostile_profiles[0],
                "position": {"x": monster_one_x, "y": monster_one_y},
            },
            {
                "id": "generated-hostile-2",
                **hostile_profiles[1],
                "position": {"x": monster_two_x, "y": monster_two_y},
            },
            {
                "id": "generated-hostile-3",
                **hostile_profiles[2],
                "position": {"x": monster_three_x, "y": monster_three_y},
            },
            {
                "id": "generated-dog",
                "name": "dog",
                "char": "d",
                "position": {"x": pet_x, "y": pet_y},
                "hp": 4,
                "attack": 1,
                "experience": 1,
                "pet": True,
                "movement": "follow",
                "pickup": True,
                "eat": True,
                "hunger": 0,
                "hunger_max": 1000,
                "hunger_drain": 1,
                "eat_threshold": 100,
                "base_speed": pet_base_speed,
                "movement_points": 0,
                "vision": 20,
            },
        ],
        "traps": [
            {
                "id": "generated-arrow-trap",
                "kind": "arrow",
                "damage": 3,
                "seen": False,
                "position": {"x": trap_x, "y": trap_y},
                "effect": trap_effect,
            }
        ],
        "light_sources": [{
            "id": "generated-pet-light",
            "position": {"x": pet_x, "y": pet_y},
            "follow": "generated-dog",
            "radius": light_radius,
            "active": True,
        }],
        "dungeon_level": 1,
        "metadata": {
            "hp": 14,
            "hp_max": 14,
            "hunger": 900,
            "ac": 10,
            "experience_level": 1,
            "generated_rooms": rooms,
            "doors": doors,
            "procedural_population": {
                "schema": PROCEDURAL_POPULATION_TABLE["schema"],
                "selector_bound": PROCEDURAL_POPULATION_TABLE["selector_bound"],
                "spawn_interval": PROCEDURAL_POPULATION_TABLE["spawn_interval"],
                "max_monsters": PROCEDURAL_POPULATION_TABLE["max_monsters"],
            },
        },
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
    seed = int(seed_override if seed_override is not None else data.get("seed", fixture.get("meta", {}).get("seed", 0)))
    level_source = data.get("level_dump", fixture.get("level_dump", {}))
    if not level_source:
        grid = data.get("grid", [])
        level_source = {"grid": grid} if grid else procedural_level_dump(seed)
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
