"""Source-faithful Rogue portable save-state serialization slices."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from source_rogue import RogueRng


RSID_STATS = 0xABCD0001
RSID_THING = 0xABCD0002
RSID_OBJECT = 0xABCD0003
RSID_MAGICITEMS = 0xABCD0004
RSID_OBJECTLIST = 0xABCD0007
RSID_MONSTERLIST = 0xABCD0009
RSID_MONSTERS = 0xABCD000B
RSID_WINDOW = 0xABCD000D
RSID_DAEMONS = 0xABCD000E
RSID_ROOMS = 0xABCD0017

MAXROOMS = 9
NUMTHINGS = 7
MAXPASS = 13
MAXSTR = 1024
MAXPOTIONS = 14
MAXRINGS = 14
MAXSCROLLS = 18
MAXSTICKS = 14
MAXARMORS = 8
MAXWEAPONS = 9
MAXNAME = 40
MAXLINES = 32
MAXCOLS = 80
SOURCE_ROOM_ISDARK = 0o000001
SOURCE_ROOM_ISGONE = 0o000002
CHECKPOINT_VERSION = "rogue-5.4.4"
SOURCE_SAVE_VERSION = "rogue (rogueforge) 09/05/07"
SOURCE_ENCSTR = bytes(
    [
        0o300,
        ord("k"),
        ord("|"),
        ord("|"),
        ord("`"),
        0o251,
        ord("Y"),
        ord("."),
        ord("'"),
        0o305,
        0o321,
        0o201,
        ord("+"),
        0o277,
        ord("~"),
        ord("r"),
        ord('"'),
        ord("]"),
        0o240,
        ord("_"),
        0o223,
        ord("="),
        ord("1"),
        0o341,
        ord(")"),
        0o222,
        0o212,
        0o241,
        ord("t"),
        ord(";"),
        ord("\t"),
        ord("$"),
        0o270,
        0o314,
        ord("/"),
        ord("<"),
        ord("#"),
        0o201,
        0o254,
    ]
)
SOURCE_STATLIST = bytes(
    [
        0o355,
        ord("k"),
        ord("l"),
        ord("{"),
        ord("+"),
        0o204,
        0o255,
        0o313,
        ord("i"),
        ord("d"),
        ord("J"),
        0o361,
        0o214,
        ord("="),
        ord("4"),
        ord(":"),
        0o311,
        0o271,
        0o341,
        ord("w"),
        ord("K"),
        ord("<"),
        0o312,
        0o321,
        0o213,
        ord(","),
        ord(","),
        ord("7"),
        0o271,
        ord("/"),
        ord("R"),
        ord("k"),
        ord("%"),
        ord("\b"),
        0o312,
        ord("\f"),
        0o246,
    ]
)
SOURCE_SAVE_PREFIX_FIELDS = (
    ("after", "boolean"),
    ("again", "boolean"),
    ("noscore", "int"),
    ("seenstairs", "boolean"),
    ("amulet", "boolean"),
    ("door_stop", "boolean"),
    ("fight_flush", "boolean"),
    ("firstmove", "boolean"),
    ("got_ltc", "boolean"),
    ("has_hit", "boolean"),
    ("in_shell", "boolean"),
    ("inv_describe", "boolean"),
    ("jump", "boolean"),
    ("kamikaze", "boolean"),
    ("lower_msg", "boolean"),
    ("move_on", "boolean"),
    ("msg_esc", "boolean"),
    ("passgo", "boolean"),
    ("playing", "boolean"),
    ("q_comm", "boolean"),
    ("running", "boolean"),
    ("save_msg", "boolean"),
    ("see_floor", "boolean"),
    ("stat_msg", "boolean"),
    ("terse", "boolean"),
    ("to_death", "boolean"),
    ("tombstone", "boolean"),
    ("wizard", "int"),
    ("pack_used", "booleans[26]"),
)
SOURCE_SAVE_IDENTITY_TEXT_FIELDS = (
    "dir_ch",
    "file_name",
    "huh",
    "potions",
    "prbuf",
    "rings",
    "release",
    "runch",
    "scrolls",
    "take",
    "whoami",
    "sticks",
    "orig_dsusp",
    "fruit",
    "home",
    "inv_t_name",
    "l_last_comm",
    "l_last_dir",
    "last_comm",
    "last_dir",
    "tr_name",
)
SOURCE_SAVE_SCALAR_FIELDS = (
    "n_objs",
    "ntraps",
    "hungry_state",
    "inpack",
    "inv_type",
    "level",
    "max_level",
    "mpos",
    "no_food",
    "a_class",
    "count",
    "food_left",
    "lastscore",
    "no_command",
    "no_move",
    "purse",
    "quiet",
    "vf_hit",
    "dnum",
    "seed",
    "e_levels",
    "delta",
    "oldpos",
    "stairs",
)
SOURCE_SAVE_PLAYER_REF_FIELDS = (
    "player",
    "cur_armor",
    "cur_ring_left",
    "cur_ring_right",
    "cur_weapon",
    "l_last_pick",
    "last_pick",
)
SOURCE_SAVE_LEVEL_STATE_FIELDS = (
    "lvl_obj",
    "mlist",
    "places",
)
SOURCE_SAVE_ROOM_STATE_FIELDS = (
    "max_stats",
    "rooms",
    "oldrp",
    "passages",
)
SOURCE_SAVE_INFO_STATE_FIELDS = (
    "monsters",
    "things",
    "arm_info",
    "pot_info",
    "ring_info",
    "scr_info",
    "weap_info",
    "ws_info",
)
SOURCE_SAVE_TAIL_STATE_FIELDS = (
    "d_list",
    "total",
    "between",
    "nh",
    "group",
    "stdscr",
)
SOURCE_A_CLASS = (8, 7, 7, 6, 5, 4, 4, 3)
SOURCE_E_LEVELS = (
    10,
    20,
    40,
    80,
    160,
    320,
    640,
    1300,
    2600,
    5200,
    13000,
    26000,
    50000,
    100000,
    200000,
    400000,
    800000,
    2000000,
    4000000,
    8000000,
    0,
)
SOURCE_RAINBOW = (
    "amber",
    "aquamarine",
    "black",
    "blue",
    "brown",
    "clear",
    "crimson",
    "cyan",
    "ecru",
    "gold",
    "green",
    "grey",
    "magenta",
    "orange",
    "pink",
    "plaid",
    "purple",
    "red",
    "silver",
    "tan",
    "tangerine",
    "topaz",
    "turquoise",
    "vermilion",
    "violet",
    "white",
    "yellow",
)
SOURCE_SYLLS = (
    "a",
    "ab",
    "ag",
    "aks",
    "ala",
    "an",
    "app",
    "arg",
    "arze",
    "ash",
    "bek",
    "bie",
    "bit",
    "bjor",
    "blu",
    "bot",
    "bu",
    "byt",
    "comp",
    "con",
    "cos",
    "cre",
    "dalf",
    "dan",
    "den",
    "do",
    "e",
    "eep",
    "el",
    "eng",
    "er",
    "ere",
    "erk",
    "esh",
    "evs",
    "fa",
    "fid",
    "fri",
    "fu",
    "gan",
    "gar",
    "glen",
    "gop",
    "gre",
    "ha",
    "hyd",
    "i",
    "ing",
    "ip",
    "ish",
    "it",
    "ite",
    "iv",
    "jo",
    "kho",
    "kli",
    "klis",
    "la",
    "lech",
    "mar",
    "me",
    "mi",
    "mic",
    "mik",
    "mon",
    "mung",
    "mur",
    "nej",
    "nelg",
    "nep",
    "ner",
    "nes",
    "nes",
    "nih",
    "nin",
    "o",
    "od",
    "ood",
    "org",
    "orn",
    "ox",
    "oxy",
    "pay",
    "ple",
    "plu",
    "po",
    "pot",
    "prok",
    "re",
    "rea",
    "rhov",
    "ri",
    "ro",
    "rog",
    "rok",
    "rol",
    "sa",
    "san",
    "sat",
    "sef",
    "seh",
    "shu",
    "ski",
    "sna",
    "sne",
    "snik",
    "sno",
    "so",
    "sol",
    "sri",
    "sta",
    "sun",
    "ta",
    "tab",
    "tem",
    "ther",
    "ti",
    "tox",
    "trol",
    "tue",
    "turs",
    "u",
    "ulk",
    "um",
    "un",
    "uni",
    "ur",
    "val",
    "viv",
    "vly",
    "vom",
    "wah",
    "wed",
    "werg",
    "wex",
    "whon",
    "wun",
    "xo",
    "y",
    "yot",
    "yu",
    "zant",
    "zeb",
    "zim",
    "zok",
    "zon",
    "zum",
)
SOURCE_STONES = (
    "agate",
    "alexandrite",
    "amethyst",
    "carnelian",
    "diamond",
    "emerald",
    "germanium",
    "granite",
    "garnet",
    "jade",
    "kryptonite",
    "lapis lazuli",
    "moonstone",
    "obsidian",
    "onyx",
    "opal",
    "pearl",
    "peridot",
    "ruby",
    "sapphire",
    "stibotantalite",
    "tiger eye",
    "topaz",
    "turquoise",
    "taaffeite",
    "zircon",
)
SOURCE_WOOD = (
    "avocado wood",
    "balsa",
    "bamboo",
    "banyan",
    "birch",
    "cedar",
    "cherry",
    "cinnibar",
    "cypress",
    "dogwood",
    "driftwood",
    "ebony",
    "elm",
    "eucalyptus",
    "fall",
    "hemlock",
    "holly",
    "ironwood",
    "kukui wood",
    "mahogany",
    "manzanita",
    "maple",
    "oaken",
    "persimmon wood",
    "pecan",
    "pine",
    "poplar",
    "redwood",
    "rosewood",
    "spruce",
    "teak",
    "walnut",
    "zebrawood",
)
SOURCE_METAL = (
    "aluminum",
    "beryllium",
    "bone",
    "brass",
    "bronze",
    "copper",
    "electrum",
    "gold",
    "iron",
    "lead",
    "magnesium",
    "mercury",
    "nickel",
    "pewter",
    "platinum",
    "steel",
    "silver",
    "silicon",
    "tin",
    "titanium",
    "tungsten",
    "zinc",
)
SOURCE_INV_T_NAME = ("Overwrite", "Slow", "Clear")
SOURCE_TRAP_NAMES = (
    "a trapdoor",
    "an arrow trap",
    "a sleeping gas trap",
    "a beartrap",
    "a teleport trap",
    "a poison dart trap",
    "a rust trap",
    "a mysterious trap",
)
SOURCE_MONSTER_STATS = (
    (10, 20, 5, 2, 1, "0x0/0x0", 1),
    (10, 1, 1, 3, 1, "1x2", 1),
    (10, 17, 4, 4, 1, "1x2/1x5/1x5", 1),
    (10, 5000, 10, -1, 1, "1x8/1x8/3x10", 1),
    (10, 2, 1, 7, 1, "1x2", 1),
    (10, 80, 8, 3, 1, "%%%x0", 1),
    (10, 2000, 13, 2, 1, "4x3/3x5", 1),
    (10, 3, 1, 5, 1, "1x8", 1),
    (10, 5, 1, 9, 1, "0x0", 1),
    (10, 3000, 15, 6, 1, "2x12/2x4", 1),
    (10, 1, 1, 7, 1, "1x4", 1),
    (10, 10, 3, 8, 1, "1x1", 1),
    (10, 200, 8, 2, 1, "3x4/3x4/2x5", 1),
    (10, 37, 3, 9, 1, "0x0", 1),
    (10, 5, 1, 6, 1, "1x8", 1),
    (10, 120, 8, 3, 1, "4x4", 1),
    (10, 15, 3, 3, 1, "1x5/1x5", 1),
    (10, 9, 2, 3, 1, "1x6", 1),
    (10, 2, 1, 5, 1, "1x3", 1),
    (10, 120, 6, 4, 1, "1x8/1x8/2x6", 1),
    (10, 190, 7, -2, 1, "1x9/1x9/2x9", 1),
    (10, 350, 8, 1, 1, "1x10", 1),
    (10, 55, 5, 4, 1, "1x6", 1),
    (10, 100, 7, 7, 1, "4x4", 1),
    (10, 50, 4, 6, 1, "1x6/1x6", 1),
    (10, 6, 2, 8, 1, "1x8", 1),
)
SOURCE_THINGS_INFO = (
    (None, 26, 0),
    (None, 36, 0),
    (None, 16, 0),
    (None, 7, 0),
    (None, 7, 0),
    (None, 4, 0),
    (None, 4, 0),
)
SOURCE_ARM_INFO = (
    ("leather armor", 20, 20),
    ("ring mail", 15, 25),
    ("studded leather armor", 15, 20),
    ("scale mail", 13, 30),
    ("chain mail", 12, 75),
    ("splint mail", 10, 80),
    ("banded mail", 10, 90),
    ("plate mail", 5, 150),
)
SOURCE_POT_INFO = (
    ("confusion", 7, 5),
    ("hallucination", 8, 5),
    ("poison", 8, 5),
    ("gain strength", 13, 150),
    ("see invisible", 3, 100),
    ("healing", 13, 130),
    ("monster detection", 6, 130),
    ("magic detection", 6, 105),
    ("raise level", 2, 250),
    ("extra healing", 5, 200),
    ("haste self", 5, 190),
    ("restore strength", 13, 130),
    ("blindness", 5, 5),
    ("levitation", 6, 75),
)
SOURCE_RING_INFO = (
    ("protection", 9, 400),
    ("add strength", 9, 400),
    ("sustain strength", 5, 280),
    ("searching", 10, 420),
    ("see invisible", 10, 310),
    ("adornment", 1, 10),
    ("aggravate monster", 10, 10),
    ("dexterity", 8, 440),
    ("increase damage", 8, 400),
    ("regeneration", 4, 460),
    ("slow digestion", 9, 240),
    ("teleportation", 5, 30),
    ("stealth", 7, 470),
    ("maintain armor", 5, 380),
)
SOURCE_SCR_INFO = (
    ("monster confusion", 7, 140),
    ("magic mapping", 4, 150),
    ("hold monster", 2, 180),
    ("sleep", 3, 5),
    ("enchant armor", 7, 160),
    ("identify potion", 10, 80),
    ("identify scroll", 10, 80),
    ("identify weapon", 6, 80),
    ("identify armor", 7, 100),
    ("identify ring, wand or staff", 10, 115),
    ("scare monster", 3, 200),
    ("food detection", 2, 60),
    ("teleportation", 5, 165),
    ("enchant weapon", 8, 150),
    ("create monster", 4, 75),
    ("remove curse", 7, 105),
    ("aggravate monsters", 3, 20),
    ("protect armor", 2, 250),
)
SOURCE_WEAP_INFO = (
    ("mace", 11, 8),
    ("long sword", 11, 15),
    ("short bow", 12, 15),
    ("arrow", 12, 1),
    ("dagger", 8, 3),
    ("two handed sword", 10, 75),
    ("dart", 12, 2),
    ("shuriken", 12, 5),
    ("spear", 12, 5),
    (None, 0, 0),
)
SOURCE_WS_INFO = (
    ("light", 12, 250),
    ("invisibility", 6, 5),
    ("lightning", 3, 330),
    ("fire", 3, 330),
    ("cold", 3, 330),
    ("polymorph", 15, 310),
    ("magic missile", 10, 170),
    ("haste monster", 10, 5),
    ("slow monster", 11, 350),
    ("drain life", 9, 300),
    ("nothing", 1, 5),
    ("teleport away", 6, 340),
    ("teleport to", 6, 50),
    ("cancellation", 5, 280),
)


@dataclass
class Coord:
    y: int
    x: int


@dataclass
class SourceStats:
    strength: int
    exp: int
    level: int
    armor: int
    hp: int
    damage: str
    max_hp: int


@dataclass
class SourceMonsterInfo:
    stats: SourceStats


@dataclass
class SourceObjInfo:
    name: str | None
    prob: int
    worth: int
    guess: str | None = None
    know: bool = False


@dataclass
class SourceObject:
    object_id: str
    obj_type: str
    pos: Coord
    launch: int
    packch: str
    damage: str
    hurldmg: str
    count: int
    which: int
    hplus: int
    dplus: int
    arm: int
    flags: int
    group: int
    label: str | None = None


@dataclass
class SourceRoom:
    pos: Coord
    max: Coord
    gold: Coord
    goldval: int
    flags: int
    exits: list[Coord] = field(default_factory=list)


@dataclass
class SourceThing:
    thing_id: str
    pos: Coord
    turn: bool
    thing_type: str
    disguise: str
    oldch: str
    dest_kind: str
    dest_index: int
    flags: int
    stats: SourceStats
    room_index: int
    pack: list[SourceObject] = field(default_factory=list)


@dataclass
class SourcePlace:
    ch: str
    flags: int
    monster_index: int


@dataclass
class SourceDaemon:
    d_type: int
    func: int
    arg: int
    time: int


class StateWriter:
    def __init__(self) -> None:
        self.data = bytearray()

    def write_int(self, value: int) -> None:
        self.data.extend((int(value) & 0xFFFFFFFF).to_bytes(4, "little", signed=False))

    def write_ints(self, values: list[int]) -> None:
        self.write_int(len(values))
        for value in values:
            self.write_int(value)

    def write_uint(self, value: int) -> None:
        self.data.extend(int(value).to_bytes(4, "little", signed=False))

    def write_short(self, value: int) -> None:
        self.data.extend((int(value) & 0xFFFF).to_bytes(2, "little", signed=False))

    def write_char(self, value: str) -> None:
        self.data.extend(_char_byte(value))

    def write_boolean(self, value: bool) -> None:
        self.data.append(1 if value else 0)

    def write_booleans(self, values: list[bool]) -> None:
        self.write_int(len(values))
        for value in values:
            self.write_boolean(value)

    def write_chars(self, value: bytes) -> None:
        self.write_int(len(value))
        self.data.extend(value)

    def write_string(self, value: str | None) -> None:
        if value is None:
            payload = b""
        else:
            payload = value.encode("utf-8") + b"\0"
        self.write_int(len(payload))
        self.write_chars(payload)

    def write_strings(self, values: list[str | None]) -> None:
        self.write_int(len(values))
        for value in values:
            self.write_string(value)

    def write_marker(self, marker: int) -> None:
        self.write_int(marker)

    def write_coord(self, coord: Coord) -> None:
        self.write_int(coord.x)
        self.write_int(coord.y)

    def write_stats(self, stats: SourceStats) -> None:
        self.write_marker(RSID_STATS)
        self.write_uint(stats.strength)
        self.write_int(stats.exp)
        self.write_int(stats.level)
        self.write_int(stats.armor)
        self.write_int(stats.hp)
        self.write_chars(_fixed_bytes(stats.damage, 13))
        self.write_int(stats.max_hp)

    def write_monsters(self, monsters: list[SourceMonsterInfo]) -> None:
        self.write_marker(RSID_MONSTERS)
        self.write_int(len(monsters))
        for monster in monsters:
            self.write_stats(monster.stats)

    def write_obj_info(self, items: list[SourceObjInfo]) -> None:
        self.write_marker(RSID_MAGICITEMS)
        self.write_int(len(items))
        for item in items:
            self.write_int(item.prob)
            self.write_int(item.worth)
            self.write_string(item.guess)
            self.write_boolean(item.know)

    def write_room(self, room: SourceRoom) -> None:
        exits = (room.exits + [Coord(0, 0)] * 12)[:12]
        self.write_coord(room.pos)
        self.write_coord(room.max)
        self.write_coord(room.gold)
        self.write_int(room.goldval)
        self.write_short(room.flags)
        self.write_int(len(room.exits))
        for exit_coord in exits:
            self.write_coord(exit_coord)

    def write_rooms(self, rooms: list[SourceRoom]) -> None:
        self.write_int(len(rooms))
        for room in rooms:
            self.write_room(room)

    def write_room_reference(self, room_index: int) -> None:
        self.write_int(room_index if 0 <= room_index < MAXROOMS else -1)

    def write_object(self, obj: SourceObject) -> None:
        self.write_marker(RSID_OBJECT)
        self.write_int(ord(obj.obj_type))
        self.write_coord(obj.pos)
        self.write_int(obj.launch)
        self.write_char(obj.packch)
        self.write_chars(_fixed_bytes(obj.damage, 8))
        self.write_chars(_fixed_bytes(obj.hurldmg, 8))
        self.write_int(obj.count)
        self.write_int(obj.which)
        self.write_int(obj.hplus)
        self.write_int(obj.dplus)
        self.write_int(obj.arm)
        self.write_int(obj.flags)
        self.write_int(obj.group)
        self.write_string(obj.label)

    def write_object_list(self, objects: list[SourceObject]) -> None:
        self.write_marker(RSID_OBJECTLIST)
        self.write_int(len(objects))
        for obj in objects:
            self.write_object(obj)

    def write_object_reference(self, objects: list[SourceObject], item_id: str | None) -> None:
        index = -1
        if item_id is not None:
            for candidate_index, obj in enumerate(objects):
                if obj.object_id == item_id:
                    index = candidate_index
                    break
        self.write_int(index)

    def write_thing(self, thing: SourceThing | None, monsters: list[SourceThing], objects: list[SourceObject]) -> None:
        self.write_marker(RSID_THING)
        if thing is None:
            self.write_int(0)
            return
        self.write_int(1)
        self.write_coord(thing.pos)
        self.write_boolean(thing.turn)
        self.write_char(thing.thing_type)
        self.write_char(thing.disguise)
        self.write_char(thing.oldch)
        dest_list, dest_index = _dest_pair(thing, monsters, objects)
        self.write_int(dest_list)
        self.write_int(dest_index)
        self.write_short(thing.flags)
        self.write_stats(thing.stats)
        self.write_room_reference(thing.room_index)
        self.write_object_list(thing.pack)

    def write_thing_list(self, things: list[SourceThing], objects: list[SourceObject]) -> None:
        self.write_marker(RSID_MONSTERLIST)
        self.write_int(len(things))
        for thing in things:
            self.write_thing(thing, things, objects)

    def write_thing_reference(self, things: list[SourceThing], index: int) -> None:
        self.write_int(index if 0 <= index < len(things) else -1)

    def write_places(self, places: list[SourcePlace], monsters: list[SourceThing]) -> None:
        for place in places:
            self.write_char(place.ch)
            self.write_char(chr(place.flags & 0xFF))
            self.write_thing_reference(monsters, place.monster_index)

    def write_daemons(self, daemons: list[SourceDaemon], count: int) -> None:
        self.write_marker(RSID_DAEMONS)
        self.write_int(count)
        padded = (daemons + [SourceDaemon(0, 0, 0, 0)] * count)[:count]
        for daemon in padded:
            self.write_int(daemon.d_type)
            self.write_int(daemon.func)
            self.write_int(daemon.arg)
            self.write_int(daemon.time)

    def write_window(self, rows: list[str]) -> None:
        width = max((len(row) for row in rows), default=0)
        self.write_marker(RSID_WINDOW)
        self.write_int(len(rows))
        self.write_int(width)
        for row in rows:
            padded = (row + " " * width)[:width]
            for ch in padded:
                self.write_int(ord(ch))

    def write_save_identity_text_block(self, block: dict[str, Any]) -> None:
        self.write_char(str(block["dir_ch"])[:1])
        self.write_chars(_fixed_bytes(str(block["file_name"]), MAXSTR))
        self.write_chars(_fixed_bytes(str(block["huh"]), MAXSTR))
        for index in _int_list(block["potions"], MAXPOTIONS):
            self.write_int(index)
        self.write_chars(_fixed_bytes(str(block["prbuf"]), 2 * MAXSTR))
        for index in _int_list(block["rings"], MAXRINGS):
            self.write_int(index)
        self.write_string(str(block["release"]))
        self.write_char(str(block["runch"])[:1])
        for name in _string_list(block["scrolls"], MAXSCROLLS):
            self.write_string(name)
        self.write_char(str(block["take"])[:1])
        self.write_chars(_fixed_bytes(str(block["whoami"]), MAXSTR))
        for stick in _stick_list(block["sticks"], MAXSTICKS):
            self.write_int(0 if bool(stick["is_staff"]) else 1)
            self.write_int(int(stick["material_index"]))
        self.write_int(int(block["orig_dsusp"]))
        self.write_chars(_fixed_bytes(str(block["fruit"]), MAXSTR))
        self.write_chars(_fixed_bytes(str(block["home"]), MAXSTR))
        self.write_strings(_string_list(block["inv_t_name"], 3))
        self.write_char(str(block["l_last_comm"])[:1])
        self.write_char(str(block["l_last_dir"])[:1])
        self.write_char(str(block["last_comm"])[:1])
        self.write_char(str(block["last_dir"])[:1])
        self.write_strings(_string_list(block["tr_name"], 8))

    def write_save_scalar_block(self, block: dict[str, Any]) -> None:
        self.write_int(int(block["n_objs"]))
        self.write_int(int(block["ntraps"]))
        self.write_int(int(block["hungry_state"]))
        self.write_int(int(block["inpack"]))
        self.write_int(int(block["inv_type"]))
        self.write_int(int(block["level"]))
        self.write_int(int(block["max_level"]))
        self.write_int(int(block["mpos"]))
        self.write_int(int(block["no_food"]))
        self.write_ints(_int_list(block["a_class"], MAXARMORS))
        self.write_int(int(block["count"]))
        self.write_int(int(block["food_left"]))
        self.write_int(int(block["lastscore"]))
        self.write_int(int(block["no_command"]))
        self.write_int(int(block["no_move"]))
        self.write_int(int(block["purse"]))
        self.write_int(int(block["quiet"]))
        self.write_int(int(block["vf_hit"]))
        self.write_int(int(block["dnum"]))
        self.write_int(int(block["seed"]))
        self.write_ints(_int_list(block["e_levels"], len(SOURCE_E_LEVELS)))
        self.write_coord(_coord_value(block["delta"]))
        self.write_coord(_coord_value(block["oldpos"]))
        self.write_coord(_coord_value(block["stairs"]))


def source_state_report() -> dict[str, Any]:
    return {
        "schema": "gamebench.rogue.source_state.v1",
        "cases": [_case_summary(name, payload) for name, payload in _cases()],
    }


def runtime_source_checkpoint_projection(resolved: Any, public: Any, private: Any, nev_cursor: int) -> dict[str, Any]:
    payload = runtime_source_checkpoint_bytes(resolved, public, private, nev_cursor)
    return {
        "schema": "gamebench.rogue.source_checkpoint.v1",
        "authority": "modern-rogue state.c/save.c projection",
        "encoding": "rs_save_file_runtime_subset",
        "len": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
        "current_weapon_id": str(_field(private, "current_weapon_id", "")),
        "current_armor_id": str(_field(private, "current_armor_id", "")),
    }


def runtime_source_save_file_projection(resolved: Any, public: Any, private: Any, nev_cursor: int, file_name: str = "") -> dict[str, Any]:
    runtime_subset_payload = runtime_source_checkpoint_bytes(resolved, public, private, nev_cursor)
    plain_payload = runtime_source_save_file_plain_body_bytes(resolved, public, private, nev_cursor, file_name)
    prefix_payload = runtime_source_save_prefix_bytes(public, private)
    identity_text_payload = runtime_source_save_identity_text_bytes(resolved, private, file_name)
    scalar_payload = runtime_source_save_scalar_bytes(resolved, public, private)
    player_refs_payload = runtime_source_save_player_refs_bytes(public, private)
    level_state_payload = runtime_source_save_level_state_bytes(public, private)
    room_state_payload = runtime_source_save_room_state_bytes(public, private)
    info_state_payload = runtime_source_save_info_state_bytes(private)
    tail_state_payload = runtime_source_save_tail_state_bytes(public, private)
    save_payload = runtime_source_save_file_bytes(resolved, public, private, nev_cursor, file_name)
    terrain = list(_field(public, "terrain"))
    width = max((len(row) for row in terrain), default=0)
    return {
        "schema": "gamebench.rogue.source_save_file.v1",
        "authority": "modern-rogue save.c encwrite + state.c rs_save_file projection",
        "encoding": "encwrite(version) + encwrite(geometry) + encwrite(rs_save_file_prefix + rs_save_file_identity_text + rs_save_file_scalars + rs_save_file_player_refs + rs_save_file_level_state + rs_save_file_room_state + rs_save_file_info_state + rs_save_file_tail_state)",
        "version": SOURCE_SAVE_VERSION,
        "geometry": f"{len(terrain)} x {width}\n",
        "len": len(save_payload),
        "sha256": hashlib.sha256(save_payload).hexdigest(),
        "hex": save_payload.hex(),
        "plain_subset_sha256": hashlib.sha256(plain_payload).hexdigest(),
        "runtime_subset_sha256": hashlib.sha256(runtime_subset_payload).hexdigest(),
        "rs_save_file_prefix_len": len(prefix_payload),
        "rs_save_file_prefix_sha256": hashlib.sha256(prefix_payload).hexdigest(),
        "rs_save_file_prefix_fields": [field for field, _kind in SOURCE_SAVE_PREFIX_FIELDS],
        "rs_save_file_identity_text_len": len(identity_text_payload),
        "rs_save_file_identity_text_sha256": hashlib.sha256(identity_text_payload).hexdigest(),
        "rs_save_file_identity_text_fields": list(SOURCE_SAVE_IDENTITY_TEXT_FIELDS),
        "rs_save_file_scalar_len": len(scalar_payload),
        "rs_save_file_scalar_sha256": hashlib.sha256(scalar_payload).hexdigest(),
        "rs_save_file_scalar_fields": list(SOURCE_SAVE_SCALAR_FIELDS),
        "rs_save_file_player_refs_len": len(player_refs_payload),
        "rs_save_file_player_refs_sha256": hashlib.sha256(player_refs_payload).hexdigest(),
        "rs_save_file_player_refs_fields": list(SOURCE_SAVE_PLAYER_REF_FIELDS),
        "rs_save_file_level_state_len": len(level_state_payload),
        "rs_save_file_level_state_sha256": hashlib.sha256(level_state_payload).hexdigest(),
        "rs_save_file_level_state_fields": list(SOURCE_SAVE_LEVEL_STATE_FIELDS),
        "rs_save_file_level_state_places_count": MAXLINES * MAXCOLS,
        "rs_save_file_room_state_len": len(room_state_payload),
        "rs_save_file_room_state_sha256": hashlib.sha256(room_state_payload).hexdigest(),
        "rs_save_file_room_state_fields": list(SOURCE_SAVE_ROOM_STATE_FIELDS),
        "rs_save_file_room_state_rooms_count": MAXROOMS,
        "rs_save_file_room_state_passages_count": MAXPASS,
        "rs_save_file_info_state_len": len(info_state_payload),
        "rs_save_file_info_state_sha256": hashlib.sha256(info_state_payload).hexdigest(),
        "rs_save_file_info_state_fields": list(SOURCE_SAVE_INFO_STATE_FIELDS),
        "rs_save_file_info_state_monsters_count": 26,
        "rs_save_file_info_state_counts": {
            "things": NUMTHINGS,
            "arm_info": MAXARMORS,
            "pot_info": MAXPOTIONS,
            "ring_info": MAXRINGS,
            "scr_info": MAXSCROLLS,
            "weap_info": MAXWEAPONS + 1,
            "ws_info": MAXSTICKS,
        },
        "rs_save_file_tail_state_len": len(tail_state_payload),
        "rs_save_file_tail_state_sha256": hashlib.sha256(tail_state_payload).hexdigest(),
        "rs_save_file_tail_state_fields": list(SOURCE_SAVE_TAIL_STATE_FIELDS),
        "rs_save_file_tail_state_daemons_count": 20,
        "rs_save_file_tail_state_window_height": len(terrain),
        "rs_save_file_tail_state_window_width": width,
    }


def runtime_source_save_file_bytes(resolved: Any, public: Any, private: Any, nev_cursor: int, file_name: str = "") -> bytes:
    plain_payload = runtime_source_save_file_plain_body_bytes(resolved, public, private, nev_cursor, file_name)
    terrain = list(_field(public, "terrain"))
    width = max((len(row) for row in terrain), default=0)
    return _source_save_file_envelope(plain_payload, len(terrain), width)


def runtime_source_save_file_plain_body_bytes(resolved: Any, public: Any, private: Any, nev_cursor: int, file_name: str = "") -> bytes:
    del nev_cursor
    return (
        runtime_source_save_prefix_bytes(public, private)
        + runtime_source_save_identity_text_bytes(resolved, private, file_name)
        + runtime_source_save_scalar_bytes(resolved, public, private)
        + runtime_source_save_player_refs_bytes(public, private)
        + runtime_source_save_level_state_bytes(public, private)
        + runtime_source_save_room_state_bytes(public, private)
        + runtime_source_save_info_state_bytes(private)
        + runtime_source_save_tail_state_bytes(public, private)
    )


def runtime_source_save_prefix_bytes(public: Any, private: Any) -> bytes:
    writer = StateWriter()
    _write_source_save_prefix(writer, _runtime_source_save_prefix_values(public, private))
    return bytes(writer.data)


def runtime_source_save_identity_text_bytes(resolved: Any, private: Any, file_name: str = "") -> bytes:
    writer = StateWriter()
    writer.write_save_identity_text_block(_runtime_source_save_identity_text_values(resolved, private, file_name))
    return bytes(writer.data)


def runtime_source_identity_display(resolved: Any, private: Any) -> dict[str, Any]:
    tables = _source_identity_tables(int(_field(resolved, "seed", _field(private, "rng_seed", 0))))
    return {
        "potions": [SOURCE_RAINBOW[index] for index in tables["potions"]],
        "scrolls": list(tables["scrolls"]),
        "rings": [SOURCE_STONES[index] for index in tables["rings"]],
        "sticks": [
            {
                "type": "staff" if bool(stick["is_staff"]) else "wand",
                "material": SOURCE_WOOD[int(stick["material_index"])] if bool(stick["is_staff"]) else SOURCE_METAL[int(stick["material_index"])],
            }
            for stick in tables["sticks"]
        ],
    }


def runtime_source_save_scalar_bytes(resolved: Any, public: Any, private: Any) -> bytes:
    writer = StateWriter()
    writer.write_save_scalar_block(_runtime_source_save_scalar_values(resolved, public, private))
    return bytes(writer.data)


def runtime_source_save_player_refs_bytes(public: Any, private: Any) -> bytes:
    writer = StateWriter()
    pack = _runtime_source_inventory_objects(public, private)
    player = _runtime_source_player_thing(public, private, pack)
    writer.write_thing(player, [], pack)
    for item_id in (
        _ref_id(_field(private, "current_armor_id", "")),
        _ref_id(_field(private, "left_ring_id", "")),
        _ref_id(_field(private, "right_ring_id", "")),
        _ref_id(_field(private, "current_weapon_id", "")),
        _ref_id(_field(private, "l_last_pick_id", _field(private, "l_last_pick", ""))),
        _ref_id(_field(private, "last_pick_id", _field(private, "last_pick", ""))),
    ):
        writer.write_object_reference(player.pack, item_id)
    return bytes(writer.data)


def runtime_source_save_level_state_bytes(public: Any, private: Any) -> bytes:
    writer = StateWriter()
    level_objects = _runtime_source_level_objects(public, private)
    monsters = _runtime_source_monsters(private, level_objects)
    places = _runtime_source_places(public, private, monsters)
    writer.write_object_list(level_objects)
    writer.write_thing_list(monsters, level_objects)
    writer.write_places(places, monsters)
    return bytes(writer.data)


def runtime_source_save_room_state_bytes(public: Any, private: Any) -> bytes:
    writer = StateWriter()
    writer.write_stats(_runtime_source_max_stats(private))
    writer.write_rooms(_runtime_source_rooms(private))
    writer.write_room_reference(_runtime_old_room_index(public, private))
    writer.write_rooms(_runtime_source_passages(private))
    return bytes(writer.data)


def runtime_source_save_info_state_bytes(private: Any) -> bytes:
    writer = StateWriter()
    _write_source_save_info_state(writer, private)
    return bytes(writer.data)


def runtime_source_save_tail_state_bytes(public: Any, private: Any) -> bytes:
    writer = StateWriter()
    writer.write_daemons(_runtime_source_daemons(private), 20)
    writer.write_int(0)
    writer.write_int(int(_field(private, "daemon_between", 0)))
    writer.write_coord(_runtime_source_nh(private))
    writer.write_int(int(_field(private, "weapon_group", 0)))
    writer.write_window(_runtime_source_window_rows(public))
    return bytes(writer.data)


def runtime_source_checkpoint_bytes(resolved: Any, public: Any, private: Any, nev_cursor: int) -> bytes:
    terrain = list(_field(public, "terrain"))
    hero = tuple(_field(public, "hero"))
    visible_items = dict(_field(public, "visible_items", {}))
    visible_monsters = dict(_field(public, "visible_monsters", {}))
    item_values = dict(_field(private, "item_values", {}))
    writer = StateWriter()
    width = max((len(row) for row in terrain), default=0)
    _write_save_header_projection(writer, CHECKPOINT_VERSION, len(terrain), width)
    writer.write_int(int(_field(private, "step_index", 0)))
    writer.write_int(int(nev_cursor))
    writer.write_int(int(_field(private, "dungeon_level", 1)))
    writer.write_int(int(_field(private, "max_level", 1)))
    writer.write_boolean(bool(_field(private, "has_amulet", False)))
    writer.write_int(int(_field(private, "purse", 0)))
    writer.write_int(int(_field(private, "food", 0)))
    writer.write_int(int(_field(private, "rng_seed", 0)))
    writer.write_boolean(bool(_field(private, "command_after", True)))
    writer.write_boolean(bool(_field(private, "command_running", False)))
    writer.write_int(int(_field(private, "command_count", 0)))
    writer.write_char(str(_field(private, "command_last", ""))[:1])
    writer.write_char(str(_field(private, "command_direction", ""))[:1])
    writer.write_char(str(_field(private, "command_runch", ""))[:1])
    writer.write_boolean(bool(_field(private, "command_to_death", False)))
    writer.write_int(int(_field(private, "player_flags", 0)))
    writer.write_int(int(_field(private, "strength", 16)))
    writer.write_int(int(_field(private, "max_strength", 16)))
    writer.write_int(int(_field(private, "no_command", 0)))
    writer.write_int(int(_field(private, "no_move", 0)))
    writer.write_int(int(_field(private, "food_left", 1300)))
    writer.write_int(int(_field(private, "hungry_state", 0)))
    writer.write_int(int(_field(private, "quiet", 0)))
    writer.write_int(int(_field(private, "daemon_between", 0)))
    for known in (
        list(_field(private, "pot_known", [])),
        list(_field(private, "ring_known", [])),
        list(_field(private, "scr_known", [])),
        list(_field(private, "ws_known", [])),
    ):
        writer.write_int(len(known))
        for value in known:
            writer.write_boolean(bool(value))
    markers = [str(marker) for marker in list(_field(private, "source_effect_markers", []))]
    writer.write_int(len(markers))
    for marker in markers:
        writer.write_string(marker)
    combat_markers = [str(marker) for marker in list(_field(private, "source_combat_markers", []))]
    writer.write_int(len(combat_markers))
    for marker in combat_markers:
        writer.write_string(marker)
    attack_markers = [str(marker) for marker in list(_field(private, "source_attack_markers", []))]
    writer.write_int(len(attack_markers))
    for marker in attack_markers:
        writer.write_string(marker)
    chase_markers = [str(marker) for marker in list(_field(private, "source_chase_markers", []))]
    writer.write_int(len(chase_markers))
    for marker in chase_markers:
        writer.write_string(marker)
    trap_markers = [str(marker) for marker in list(_field(private, "source_trap_markers", []))]
    writer.write_int(len(trap_markers))
    for marker in trap_markers:
        writer.write_string(marker)
    daemon_markers = [str(marker) for marker in list(_field(private, "source_daemon_markers", []))]
    writer.write_int(len(daemon_markers))
    for marker in daemon_markers:
        writer.write_string(marker)
    level_markers = [str(marker) for marker in list(_field(private, "source_level_markers", []))]
    writer.write_int(len(level_markers))
    for marker in level_markers:
        writer.write_string(marker)
    writer.write_int(int(_field(private, "player_exp", 0)))
    writer.write_int(int(_field(private, "player_level", 1)))
    writer.write_int(int(_field(private, "player_armor", 6)))
    writer.write_string(str(_field(private, "player_damage", "1x4")))
    writer.write_string(str(_field(private, "current_weapon_id", "")))
    writer.write_string(str(_field(private, "current_armor_id", "")))
    writer.write_int(int(_field(private, "vf_hit", 0)))
    writer.write_int(int(_field(private, "max_hit", 0)))
    writer.write_boolean(bool(_field(private, "kamikaze", False)))
    inventory = [dict(item) for item in list(_field(private, "source_inventory", []))]
    writer.write_int(len(inventory))
    for item in inventory:
        writer.write_string(json.dumps(item, sort_keys=True, separators=(",", ":")))
    monsters = [dict(monster) for monster in list(_field(private, "source_monsters", []))]
    writer.write_int(len(monsters))
    for monster in monsters:
        writer.write_string(json.dumps(monster, sort_keys=True, separators=(",", ":")))
    traps = [dict(trap) for trap in list(_field(private, "source_traps", []))]
    writer.write_int(len(traps))
    for trap in traps:
        writer.write_string(json.dumps(trap, sort_keys=True, separators=(",", ":")))
    map_cells = [dict(cell) for cell in list(_field(private, "source_map_cells", []))]
    writer.write_int(len(map_cells))
    for cell in map_cells:
        writer.write_string(json.dumps(cell, sort_keys=True, separators=(",", ":")))
    daemon_actions = [dict(action) for action in list(_field(private, "source_daemon_actions", []))]
    writer.write_int(len(daemon_actions))
    for action in daemon_actions:
        writer.write_string(json.dumps(action, sort_keys=True, separators=(",", ":")))
    level_objects = [dict(obj) for obj in list(_field(private, "source_level_objects", []))]
    writer.write_int(len(level_objects))
    for obj in level_objects:
        writer.write_string(json.dumps(obj, sort_keys=True, separators=(",", ":")))
    rooms = [dict(room) for room in list(_field(private, "source_rooms", []))]
    writer.write_int(len(rooms))
    for room in rooms:
        writer.write_string(json.dumps(room, sort_keys=True, separators=(",", ":")))
    passages = [dict(passage) for passage in list(_field(private, "source_passages", []))]
    writer.write_int(len(passages))
    for passage in passages:
        writer.write_string(json.dumps(passage, sort_keys=True, separators=(",", ":")))
    writer.write_int(len(visible_monsters))
    for key, value in sorted(visible_monsters.items()):
        writer.write_string(str(key))
        writer.write_string(str(value))
    writer.write_string(str(_field(resolved, "episode_id", "")))
    writer.write_string(str(_field(resolved, "config_hash", "")))
    writer.write_coord(Coord(y=int(hero[0]), x=int(hero[1])))
    writer.write_stats(
        SourceStats(
            strength=0x1010,
            exp=int(_field(private, "purse", 0)),
            level=int(_field(private, "dungeon_level", 1)),
            armor=10,
            hp=int(_field(private, "hp", 0)),
            damage="1d4",
            max_hp=int(_field(private, "max_hp", 0)),
        )
    )
    writer.write_object_list(_runtime_objects(visible_items, item_values))
    writer.write_int(len(terrain))
    writer.write_int(width)
    writer.write_places(_runtime_places(terrain, width, traps, map_cells), [])
    return bytes(writer.data)


def _cases() -> list[tuple[str, bytes]]:
    return [
        ("primitive_block", _primitive_block()),
        ("stats_and_rooms", _stats_and_rooms()),
        ("object_list_and_refs", _object_list_and_refs()),
        ("thing_list_and_places", _thing_list_and_places()),
        ("daemons_and_save_header_projection", _daemons_and_save_header_projection()),
        ("save_file_prefix_block", _save_file_prefix_block()),
        ("save_file_identity_text_block", _save_file_identity_text_block()),
        ("save_file_scalar_block", _save_file_scalar_block()),
        ("save_file_player_refs_block", _save_file_player_refs_block()),
        ("save_file_level_state_block", _save_file_level_state_block()),
        ("save_file_room_state_block", _save_file_room_state_block()),
        ("save_file_info_state_block", _save_file_info_state_block()),
        ("save_file_tail_state_block", _save_file_tail_state_block()),
        ("encwrite_known_bytes", _encwrite_known_bytes()),
        ("save_file_envelope_projection", _save_file_envelope_projection()),
    ]


def _primitive_block() -> bytes:
    writer = StateWriter()
    writer.write_int(0x12345678)
    writer.write_int(-2)
    writer.write_uint(0x89ABCDEF)
    writer.write_short(-1234)
    writer.write_boolean(True)
    writer.write_boolean(False)
    writer.write_char("A")
    writer.write_chars(b"abc")
    writer.write_string("hello")
    writer.write_string(None)
    writer.write_coord(Coord(y=7, x=3))
    return bytes(writer.data)


def _stats_and_rooms() -> bytes:
    writer = StateWriter()
    writer.write_stats(SourceStats(strength=0x1234, exp=55, level=4, armor=-2, hp=17, damage="1d8/1d3", max_hp=25))
    writer.write_marker(RSID_ROOMS)
    writer.write_rooms(
        [
            SourceRoom(
                pos=Coord(2, 4),
                max=Coord(6, 10),
                gold=Coord(5, 9),
                goldval=73,
                flags=0o000005,
                exits=[Coord(2, 7), Coord(6, 8)],
            ),
            SourceRoom(pos=Coord(12, 20), max=Coord(4, 8), gold=Coord(0, 0), goldval=0, flags=0, exits=[]),
        ]
    )
    writer.write_room_reference(1)
    writer.write_room_reference(12)
    return bytes(writer.data)


def _object_list_and_refs() -> bytes:
    objects = _objects()
    writer = StateWriter()
    writer.write_object_list(objects)
    writer.write_object_reference(objects, "weapon")
    writer.write_object_reference(objects, "missing")
    return bytes(writer.data)


def _thing_list_and_places() -> bytes:
    objects = _objects()
    monsters = _monsters(objects)
    writer = StateWriter()
    writer.write_thing(_player(objects), monsters, objects)
    writer.write_object_reference(_player(objects).pack, "food")
    writer.write_thing_list(monsters, objects)
    writer.write_places(
        [
            SourcePlace(".", 0x10, -1),
            SourcePlace("A", 0x50, 0),
            SourcePlace("B", 0x40, 1),
        ],
        monsters,
    )
    return bytes(writer.data)


def _daemons_and_save_header_projection() -> bytes:
    writer = StateWriter()
    writer.write_daemons(
        [
            SourceDaemon(1, 2, 0, 30),
            SourceDaemon(2, 5, 7, 80),
        ],
        4,
    )
    _write_save_header_projection(writer, "rogue-5.4.4", 24, 80)
    return bytes(writer.data)


def _save_file_prefix_block() -> bytes:
    writer = StateWriter()
    _write_source_save_prefix(
        writer,
        {
            "after": True,
            "again": False,
            "noscore": 7,
            "seenstairs": True,
            "amulet": True,
            "door_stop": False,
            "fight_flush": True,
            "firstmove": False,
            "got_ltc": False,
            "has_hit": True,
            "in_shell": False,
            "inv_describe": True,
            "jump": True,
            "kamikaze": True,
            "lower_msg": False,
            "move_on": True,
            "msg_esc": False,
            "passgo": True,
            "playing": True,
            "q_comm": False,
            "running": True,
            "save_msg": True,
            "see_floor": True,
            "stat_msg": False,
            "terse": True,
            "to_death": True,
            "tombstone": True,
            "wizard": 0,
            "pack_used": [index in {0, 2, 25} for index in range(26)],
        },
    )
    return bytes(writer.data)


def _save_file_identity_text_block() -> bytes:
    writer = StateWriter()
    writer.write_save_identity_text_block(
        {
            "dir_ch": "h",
            "file_name": "save.dat",
            "huh": "last message",
            "potions": list(range(MAXPOTIONS)),
            "prbuf": "scratch",
            "rings": list(reversed(range(MAXRINGS))),
            "release": "5.4.4",
            "runch": "l",
            "scrolls": [f"scroll {index}" for index in range(MAXSCROLLS)],
            "take": "!",
            "whoami": "player",
            "sticks": [{"is_staff": index % 2 == 0, "material_index": index} for index in range(MAXSTICKS)],
            "orig_dsusp": 26,
            "fruit": "slime-mold",
            "home": "/tmp/rogue",
            "inv_t_name": list(SOURCE_INV_T_NAME),
            "l_last_comm": "s",
            "l_last_dir": "h",
            "last_comm": "f",
            "last_dir": "l",
            "tr_name": list(SOURCE_TRAP_NAMES),
        }
    )
    return bytes(writer.data)


def _save_file_scalar_block() -> bytes:
    writer = StateWriter()
    writer.write_save_scalar_block(
        {
            "n_objs": 3,
            "ntraps": 5,
            "hungry_state": 2,
            "inpack": 7,
            "inv_type": 1,
            "level": 9,
            "max_level": 11,
            "mpos": 13,
            "no_food": 17,
            "a_class": list(SOURCE_A_CLASS),
            "count": 19,
            "food_left": 1200,
            "lastscore": -1,
            "no_command": 4,
            "no_move": 6,
            "purse": 777,
            "quiet": 8,
            "vf_hit": 10,
            "dnum": 12,
            "seed": 12345,
            "e_levels": list(SOURCE_E_LEVELS),
            "delta": Coord(y=-1, x=1),
            "oldpos": Coord(y=2, x=3),
            "stairs": Coord(y=4, x=5),
        }
    )
    return bytes(writer.data)


def _save_file_player_refs_block() -> bytes:
    objects = _objects()
    player = _player(objects)
    writer = StateWriter()
    writer.write_thing(player, [], objects)
    for item_id in ("food", "weapon", None, "weapon", "food", "missing"):
        writer.write_object_reference(player.pack, item_id)
    return bytes(writer.data)


def _save_file_level_state_block() -> bytes:
    objects = _objects()
    monsters = _monsters(objects)
    places = [
        SourcePlace(".", 0x10, -1),
        SourcePlace("A", 0x50, 0),
        SourcePlace("B", 0x40, 1),
    ]
    writer = StateWriter()
    writer.write_object_list(objects)
    writer.write_thing_list(monsters, objects)
    writer.write_places(places, monsters)
    return bytes(writer.data)


def _save_file_room_state_block() -> bytes:
    writer = StateWriter()
    writer.write_stats(SourceStats(strength=0x1010, exp=220, level=5, armor=3, hp=36, damage="1d4", max_hp=40))
    writer.write_rooms(_rooms())
    writer.write_room_reference(1)
    writer.write_rooms(_passages())
    return bytes(writer.data)


def _save_file_info_state_block() -> bytes:
    writer = StateWriter()
    _write_source_save_info_state(writer, {"pot_known": [True, False], "ring_known": [False, True], "scr_known": [False, True], "ws_known": [True]})
    return bytes(writer.data)


def _save_file_tail_state_block() -> bytes:
    writer = StateWriter()
    writer.write_daemons(
        [
            SourceDaemon(2, 2, 0, -1),
            SourceDaemon(1, 9, 0, 5),
        ],
        20,
    )
    writer.write_int(0)
    writer.write_int(3)
    writer.write_coord(Coord(y=4, x=5))
    writer.write_int(7)
    writer.write_window(["@.%", "  #"])
    return bytes(writer.data)


def _encwrite_known_bytes() -> bytes:
    return _source_encwrite(b"abcdef\x00")


def _save_file_envelope_projection() -> bytes:
    return _source_save_file_envelope(_primitive_block(), 24, 80)


def _source_save_file_envelope(body: bytes, lines: int, cols: int) -> bytes:
    geometry = f"{lines} x {cols}\n".encode("ascii")
    geometry = geometry + b"\0" * (80 - len(geometry))
    return b"".join(
        (
            _source_encwrite(SOURCE_SAVE_VERSION.encode("utf-8") + b"\0"),
            _source_encwrite(geometry),
            _source_encwrite(body),
        )
    )


def _source_encwrite(data: bytes) -> bytes:
    e1 = 0
    e2 = 0
    fb = 0
    output = bytearray()
    for value in data:
        output.append((value ^ SOURCE_ENCSTR[e1] ^ SOURCE_STATLIST[e2] ^ fb) & 0xFF)
        fb = (fb + ((SOURCE_ENCSTR[e1] * SOURCE_STATLIST[e2]) & 0xFF)) & 0xFF
        e1 = (e1 + 1) % len(SOURCE_ENCSTR)
        e2 = (e2 + 1) % len(SOURCE_STATLIST)
    return bytes(output)


def _save_header_len(version: str) -> int:
    return len(version.encode("utf-8")) + 1 + 80


def _write_source_save_prefix(writer: StateWriter, values: dict[str, Any]) -> None:
    for field, kind in SOURCE_SAVE_PREFIX_FIELDS:
        if kind == "boolean":
            writer.write_boolean(bool(values[field]))
        elif kind == "int":
            writer.write_int(int(values[field]))
        elif kind == "booleans[26]":
            pack_used = [bool(value) for value in list(values[field])]
            writer.write_booleans((pack_used + [False] * 26)[:26])
        else:
            raise ValueError(f"unsupported source save prefix field kind: {kind}")


def _runtime_source_save_prefix_values(public: Any, private: Any) -> dict[str, Any]:
    del public
    return {
        "after": bool(_field(private, "command_after", True)),
        "again": False,
        "noscore": 0,
        "seenstairs": False,
        "amulet": bool(_field(private, "has_amulet", False)),
        "door_stop": False,
        "fight_flush": False,
        "firstmove": False,
        "got_ltc": False,
        "has_hit": False,
        "in_shell": False,
        "inv_describe": True,
        "jump": False,
        "kamikaze": bool(_field(private, "kamikaze", False)),
        "lower_msg": False,
        "move_on": False,
        "msg_esc": False,
        "passgo": False,
        "playing": not bool(_field(private, "terminated", False)),
        "q_comm": False,
        "running": bool(_field(private, "command_running", False)),
        "save_msg": True,
        "see_floor": True,
        "stat_msg": False,
        "terse": False,
        "to_death": bool(_field(private, "command_to_death", False)),
        "tombstone": True,
        "wizard": 0,
        "pack_used": _runtime_pack_used(list(_field(private, "source_inventory", []))),
    }


def _runtime_pack_used(inventory: list[Any]) -> list[bool]:
    used = [False] * 26
    for item in inventory:
        if not isinstance(item, dict):
            continue
        packch = str(item.get("packch", ""))[:1]
        if "a" <= packch <= "z":
            used[ord(packch) - ord("a")] = True
    return used


def _runtime_source_save_identity_text_values(resolved: Any, private: Any, file_name: str) -> dict[str, Any]:
    tables = _source_identity_tables(int(_field(resolved, "seed", _field(private, "rng_seed", 0))))
    return {
        "dir_ch": str(_field(private, "command_direction", ""))[:1],
        "file_name": file_name,
        "huh": "",
        "potions": tables["potions"],
        "prbuf": "",
        "rings": tables["rings"],
        "release": "5.4.4",
        "runch": str(_field(private, "command_runch", ""))[:1],
        "scrolls": tables["scrolls"],
        "take": "",
        "whoami": str(_field(private, "whoami", "rogue")),
        "sticks": tables["sticks"],
        "orig_dsusp": int(_field(private, "orig_dsusp", 0)),
        "fruit": str(_field(private, "fruit", "slime-mold")),
        "home": str(_field(private, "home", "")),
        "inv_t_name": list(SOURCE_INV_T_NAME),
        "l_last_comm": "",
        "l_last_dir": "",
        "last_comm": str(_field(private, "command_last", ""))[:1],
        "last_dir": str(_field(private, "command_direction", ""))[:1],
        "tr_name": list(SOURCE_TRAP_NAMES),
    }


def _runtime_source_save_scalar_values(resolved: Any, public: Any, private: Any) -> dict[str, Any]:
    hero = tuple(_field(public, "hero", (0, 0)))
    source_traps = list(_field(private, "source_traps", []))
    source_inventory = list(_field(private, "source_inventory", []))
    return {
        "n_objs": 0,
        "ntraps": len(source_traps),
        "hungry_state": int(_field(private, "hungry_state", 0)),
        "inpack": len(source_inventory),
        "inv_type": 0,
        "level": int(_field(private, "dungeon_level", 1)),
        "max_level": int(_field(private, "max_level", 1)),
        "mpos": 0,
        "no_food": 0,
        "a_class": list(SOURCE_A_CLASS),
        "count": int(_field(private, "command_count", 0)),
        "food_left": int(_field(private, "food_left", 1300)),
        "lastscore": -1,
        "no_command": int(_field(private, "no_command", 0)),
        "no_move": int(_field(private, "no_move", 0)),
        "purse": int(_field(private, "purse", 0)),
        "quiet": int(_field(private, "quiet", 0)),
        "vf_hit": int(_field(private, "vf_hit", 0)),
        "dnum": 0,
        "seed": int(_field(private, "rng_seed", _field(resolved, "seed", 0))),
        "e_levels": list(SOURCE_E_LEVELS),
        "delta": Coord(y=0, x=0),
        "oldpos": Coord(y=int(hero[0]), x=int(hero[1])),
        "stairs": _find_terrain_coord(public, "%"),
    }


def _write_source_save_info_state(writer: StateWriter, private: Any) -> None:
    writer.write_monsters(_source_monster_info())
    writer.write_obj_info(_source_obj_info(SOURCE_THINGS_INFO, NUMTHINGS))
    writer.write_obj_info(_source_obj_info(SOURCE_ARM_INFO, MAXARMORS))
    writer.write_obj_info(_source_obj_info(SOURCE_POT_INFO, MAXPOTIONS, known=_known_list(private, "pot_known", MAXPOTIONS)))
    writer.write_obj_info(_source_obj_info(SOURCE_RING_INFO, MAXRINGS, known=_known_list(private, "ring_known", MAXRINGS)))
    writer.write_obj_info(_source_obj_info(SOURCE_SCR_INFO, MAXSCROLLS, known=_known_list(private, "scr_known", MAXSCROLLS)))
    writer.write_obj_info(_source_obj_info(SOURCE_WEAP_INFO, MAXWEAPONS + 1))
    writer.write_obj_info(_source_obj_info(SOURCE_WS_INFO, MAXSTICKS, known=_known_list(private, "ws_known", MAXSTICKS)))


def _source_monster_info() -> list[SourceMonsterInfo]:
    return [
        SourceMonsterInfo(
            SourceStats(
                strength=strength,
                exp=exp,
                level=level,
                armor=armor,
                hp=hp,
                damage=damage,
                max_hp=max_hp,
            )
        )
        for strength, exp, level, armor, hp, damage, max_hp in SOURCE_MONSTER_STATS
    ]


def _source_obj_info(
    rows: tuple[tuple[str | None, int, int], ...],
    count: int,
    known: list[bool] | None = None,
    guesses: list[str | None] | None = None,
) -> list[SourceObjInfo]:
    known_values = (known or []) + [False] * count
    guess_values = (guesses or []) + [None] * count
    output = [
        SourceObjInfo(
            name=name,
            prob=prob,
            worth=worth,
            guess=guess_values[index],
            know=known_values[index],
        )
        for index, (name, prob, worth) in enumerate(rows[:count])
    ]
    return output + [SourceObjInfo(name=None, prob=0, worth=0)] * max(0, count - len(output))


def _known_list(private: Any, field: str, count: int) -> list[bool]:
    values = [bool(value) for value in list(_field(private, field, []))]
    return (values + [False] * count)[:count]


def _runtime_source_daemons(private: Any) -> list[SourceDaemon]:
    daemons: list[SourceDaemon] = []
    for action in list(_field(private, "source_daemon_actions", [])):
        if not isinstance(action, dict):
            continue
        daemons.append(
            SourceDaemon(
                d_type=int(action.get("type", 0)),
                func=_source_daemon_func(str(action.get("action", ""))),
                arg=int(action.get("arg", 0)),
                time=int(action.get("time", 0)),
            )
        )
    return daemons[:20]


def _source_daemon_func(action: str) -> int:
    return {
        "": 0,
        "rollwand": 1,
        "doctor": 2,
        "stomach": 3,
        "runners": 4,
        "swander": 5,
        "nohaste": 6,
        "unconfuse": 7,
        "unsee": 8,
        "sight": 9,
    }.get(action, -1)


def _runtime_source_nh(private: Any) -> Coord:
    value = _field(private, "nh", None)
    if value is None:
        return Coord(y=0, x=0)
    return _coord_value(value)


def _runtime_source_window_rows(public: Any) -> list[str]:
    terrain = [str(row) for row in list(_field(public, "terrain", []))]
    width = max((len(row) for row in terrain), default=0)
    return [(row + " " * width)[:width] for row in terrain]


def _source_identity_tables(seed: int) -> dict[str, Any]:
    rng = RogueRng(seed)
    return {
        "potions": _source_init_colors(rng),
        "scrolls": _source_init_scroll_names(rng),
        "rings": _source_init_stones(rng),
        "sticks": _source_init_materials(rng),
    }


def _source_init_colors(rng: RogueRng) -> list[int]:
    used = [False] * len(SOURCE_RAINBOW)
    colors: list[int] = []
    for _index in range(MAXPOTIONS):
        while True:
            candidate = rng.rnd(len(SOURCE_RAINBOW))
            if not used[candidate]:
                used[candidate] = True
                colors.append(candidate)
                break
    return colors


def _source_init_scroll_names(rng: RogueRng) -> list[str]:
    names: list[str] = []
    for _index in range(MAXSCROLLS):
        buffer = ""
        words = rng.rnd(3) + 2
        for _word in range(words):
            syllables = rng.rnd(3) + 1
            for _syllable in range(syllables):
                syllable = SOURCE_SYLLS[rng.rnd(len(SOURCE_SYLLS))]
                if len(buffer) + len(syllable) > MAXNAME:
                    break
                buffer += syllable
            buffer += " "
        names.append(buffer[:-1] if buffer else "")
    return names


def _source_init_stones(rng: RogueRng) -> list[int]:
    used = [False] * len(SOURCE_STONES)
    stones: list[int] = []
    for _index in range(MAXRINGS):
        while True:
            candidate = rng.rnd(len(SOURCE_STONES))
            if not used[candidate]:
                used[candidate] = True
                stones.append(candidate)
                break
    return stones


def _source_init_materials(rng: RogueRng) -> list[dict[str, int | bool]]:
    wood_used = [False] * len(SOURCE_WOOD)
    metal_used = [False] * len(SOURCE_METAL)
    sticks: list[dict[str, int | bool]] = []
    for _index in range(MAXSTICKS):
        while True:
            if rng.rnd(2) == 0:
                material = rng.rnd(len(SOURCE_METAL))
                if not metal_used[material]:
                    metal_used[material] = True
                    sticks.append({"is_staff": False, "material_index": material})
                    break
            else:
                material = rng.rnd(len(SOURCE_WOOD))
                if not wood_used[material]:
                    wood_used[material] = True
                    sticks.append({"is_staff": True, "material_index": material})
                    break
    return sticks


def _int_list(values: Any, count: int) -> list[int]:
    output = [int(value) for value in list(values)]
    return (output + [-1] * count)[:count]


def _string_list(values: Any, count: int) -> list[str | None]:
    output = [None if value is None else str(value) for value in list(values)]
    return (output + [None] * count)[:count]


def _stick_list(values: Any, count: int) -> list[dict[str, Any]]:
    output = []
    for value in list(values):
        entry = dict(value)
        output.append({"is_staff": bool(entry.get("is_staff", False)), "material_index": int(entry.get("material_index", -1))})
    return (output + [{"is_staff": False, "material_index": -1}] * count)[:count]


def _coord_value(value: Any) -> Coord:
    if isinstance(value, Coord):
        return value
    if isinstance(value, dict):
        return Coord(y=int(value.get("y", value.get("row", 0))), x=int(value.get("x", value.get("col", 0))))
    row, col = tuple(value)
    return Coord(y=int(row), x=int(col))


def _find_terrain_coord(public: Any, ch: str) -> Coord:
    terrain = list(_field(public, "terrain", []))
    for row_index, row in enumerate(terrain):
        col_index = str(row).find(ch)
        if col_index >= 0:
            return Coord(y=row_index, x=col_index)
    return Coord(y=0, x=0)


def _terrain_char(public: Any, coord: Coord, default: str = ".") -> str:
    terrain = list(_field(public, "terrain", []))
    if 0 <= coord.y < len(terrain):
        row = str(terrain[coord.y])
        if 0 <= coord.x < len(row):
            return row[coord.x]
    return default


def _write_save_header_projection(writer: StateWriter, version: str, lines: int, cols: int) -> None:
    writer.data.extend(version.encode("utf-8") + b"\0")
    geometry = f"{lines} x {cols}\n".encode("ascii")
    writer.data.extend(geometry + b"\0" * (80 - len(geometry)))


def _runtime_source_inventory_objects(public: Any, private: Any) -> list[SourceObject]:
    hero = tuple(_field(public, "hero", (0, 0)))
    default_pos = Coord(y=int(hero[0]), x=int(hero[1]))
    objects: list[SourceObject] = []
    for index, raw in enumerate(list(_field(private, "source_inventory", []))):
        item = dict(raw) if isinstance(raw, dict) else {}
        objects.append(_runtime_source_object_from_inventory(item, index, default_pos))
    return objects


def _runtime_source_level_objects(public: Any, private: Any) -> list[SourceObject]:
    visible_items = dict(_field(public, "visible_items", {}))
    item_values = dict(_field(private, "item_values", {}))
    objects: list[SourceObject] = []
    used_keys: set[str] = set()
    for index, raw in enumerate(list(_field(private, "source_level_objects", []))):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        pos = _runtime_item_pos(item, Coord(0, 0))
        used_keys.add(f"{pos.y},{pos.x}")
        objects.append(_runtime_source_object_from_level_item(item, index, item_values))
    for key, obj_type in sorted(visible_items.items()):
        if key in used_keys:
            continue
        try:
            row_text, col_text = key.split(",", 1)
            pos = Coord(y=int(row_text), x=int(col_text))
        except ValueError:
            pos = Coord(0, 0)
        index = len(objects)
        item = {
            "id": key,
            "type": str(obj_type)[:1],
            "pos": {"y": pos.y, "x": pos.x},
            "arm": int(item_values.get(key, 0)) if str(obj_type)[:1] == "*" else 0,
            "packch": chr(ord("a") + (index % 26)),
        }
        objects.append(_runtime_source_object_from_level_item(item, index, item_values))
    return objects


def _runtime_source_object_from_inventory(item: dict[str, Any], index: int, default_pos: Coord) -> SourceObject:
    obj_type = str(item.get("type", item.get("obj_type", "?")))[:1] or "?"
    packch = str(item.get("packch", chr(ord("a") + (index % 26))))[:1] or "a"
    label = item.get("label")
    return SourceObject(
        object_id=str(item.get("id", item.get("obj_id", f"pack{index}"))),
        obj_type=obj_type,
        pos=_runtime_item_pos(item, default_pos),
        launch=int(item.get("launch", -1)),
        packch=packch,
        damage=str(item.get("damage", "")),
        hurldmg=str(item.get("hurldmg", item.get("hurl_damage", ""))),
        count=int(item.get("count", 1)),
        which=int(item.get("which", 0)),
        hplus=int(item.get("hplus", 0)),
        dplus=int(item.get("dplus", 0)),
        arm=int(item.get("arm", item.get("charges", 0) if obj_type == "/" else 0)),
        flags=int(item.get("flags", 0)),
        group=int(item.get("group", 0)),
        label=None if label is None else str(label),
    )


def _runtime_source_object_from_level_item(item: dict[str, Any], index: int, item_values: dict[str, int]) -> SourceObject:
    obj_type = str(item.get("type", item.get("obj_type", "?")))[:1] or "?"
    pos = _runtime_item_pos(item, Coord(0, 0))
    object_id = str(item.get("id", item.get("obj_id", f"level_object{index}")))
    key = f"{pos.y},{pos.x}"
    if obj_type == "*":
        arm = int(item.get("goldval", item.get("arm", item_values.get(key, 0))))
    elif obj_type == "/":
        arm = int(item.get("arm", item.get("charges", 0)))
    else:
        arm = int(item.get("arm", 0))
    label = item.get("label")
    return SourceObject(
        object_id=object_id,
        obj_type=obj_type,
        pos=pos,
        launch=int(item.get("launch", -1)),
        packch=str(item.get("packch", chr(ord("a") + (index % 26))))[:1] or "a",
        damage=str(item.get("damage", "")),
        hurldmg=str(item.get("hurldmg", item.get("hurl_damage", ""))),
        count=int(item.get("count", 1)),
        which=int(item.get("which", 0)),
        hplus=int(item.get("hplus", 0)),
        dplus=int(item.get("dplus", 0)),
        arm=arm,
        flags=int(item.get("flags", 0)),
        group=int(item.get("group", 0)),
        label=None if label is None else str(label),
    )


def _runtime_source_player_thing(public: Any, private: Any, pack: list[SourceObject]) -> SourceThing:
    hero = tuple(_field(public, "hero", (0, 0)))
    pos = Coord(y=int(hero[0]), x=int(hero[1]))
    return SourceThing(
        thing_id="player",
        pos=pos,
        turn=False,
        thing_type="@",
        disguise="@",
        oldch=_terrain_char(public, pos, "."),
        dest_kind="null",
        dest_index=0,
        flags=int(_field(private, "player_flags", 0)),
        stats=SourceStats(
            strength=_source_strength_value(int(_field(private, "strength", 16)), int(_field(private, "max_strength", 16))),
            exp=int(_field(private, "player_exp", 0)),
            level=int(_field(private, "player_level", 1)),
            armor=int(_field(private, "player_armor", 6)),
            hp=int(_field(private, "hp", 0)),
            damage=_runtime_player_damage(private),
            max_hp=int(_field(private, "max_hp", 0)),
        ),
        room_index=0,
        pack=pack,
    )


def _runtime_item_pos(item: dict[str, Any], default: Coord) -> Coord:
    nested = item.get("pos", {})
    pos = dict(nested) if isinstance(nested, dict) else {}
    row = int(item.get("row", item.get("y", pos.get("y", default.y))))
    col = int(item.get("col", item.get("x", pos.get("x", default.x))))
    return Coord(y=row, x=col)


def _runtime_player_damage(private: Any) -> str:
    current_weapon_id = str(_field(private, "current_weapon_id", ""))
    for raw in list(_field(private, "source_inventory", [])):
        if not isinstance(raw, dict):
            continue
        if str(raw.get("id", "")) == current_weapon_id:
            return str(raw.get("damage", _field(private, "player_damage", "1x4")))
    return str(_field(private, "player_damage", "1x4"))


def _runtime_source_monsters(private: Any, level_objects: list[SourceObject]) -> list[SourceThing]:
    monsters: list[SourceThing] = []
    for index, raw in enumerate(list(_field(private, "source_monsters", []))):
        if not isinstance(raw, dict) or int(raw.get("hp", 0)) <= 0:
            continue
        monster = dict(raw)
        pos = Coord(y=int(monster.get("row", monster.get("y", 0))), x=int(monster.get("col", monster.get("x", 0))))
        pack = [
            _runtime_source_object_from_inventory(dict(item), pack_index, pos)
            for pack_index, item in enumerate(list(monster.get("pack", [])))
            if isinstance(item, dict)
        ]
        monsters.append(
            SourceThing(
                thing_id=str(monster.get("id", monster.get("monster_id", f"monster{index}"))),
                pos=pos,
                turn=bool(monster.get("turn", True)),
                thing_type=str(monster.get("type", monster.get("monster_type", "K")))[:1] or "K",
                disguise=str(monster.get("disguise", monster.get("type", "K")))[:1] or "K",
                oldch=str(monster.get("oldch", "."))[:1] or ".",
                dest_kind=str(monster.get("dest_kind", monster.get("dest", "hero"))),
                dest_index=_runtime_monster_dest_index(monster, level_objects),
                flags=int(monster.get("flags", 0)),
                stats=SourceStats(
                    strength=_source_strength_value(int(monster.get("strength", 16)), int(monster.get("max_strength", monster.get("strength", 16)))),
                    exp=int(monster.get("exp", 1)),
                    level=int(monster.get("level", 1)),
                    armor=int(monster.get("arm", 6)),
                    hp=int(monster.get("hp", 1)),
                    damage=str(monster.get("damage", "1x1")),
                    max_hp=int(monster.get("max_hp", monster.get("hp", 1))),
                ),
                room_index=int(monster.get("room", 0)),
                pack=pack,
            )
        )
    return monsters


def _runtime_monster_dest_index(monster: dict[str, Any], level_objects: list[SourceObject]) -> int:
    dest_kind = str(monster.get("dest_kind", monster.get("dest", "hero")))
    if dest_kind == "object":
        object_id = monster.get("dest_object_id", monster.get("dest_id"))
        if object_id is not None:
            for index, obj in enumerate(level_objects):
                if obj.object_id == str(object_id):
                    return index
        dest_row = monster.get("dest_row")
        dest_col = monster.get("dest_col")
        if dest_row is not None and dest_col is not None:
            for index, obj in enumerate(level_objects):
                if obj.pos.y == int(dest_row) and obj.pos.x == int(dest_col):
                    return index
        return int(monster.get("dest_index", -1))
    if dest_kind == "monster":
        return int(monster.get("dest_index", monster.get("dest_monster_index", -1)))
    if dest_kind == "room_gold":
        return int(monster.get("dest_room", monster.get("room", -1)))
    return 0


def _runtime_source_places(public: Any, private: Any, monsters: list[SourceThing]) -> list[SourcePlace]:
    terrain = list(_field(public, "terrain", []))
    traps = list(_field(private, "source_traps", []))
    map_cells = list(_field(private, "source_map_cells", []))
    trap_flags = {(int(trap["row"]), int(trap["col"])): int(trap.get("flags", 0x10)) for trap in traps}
    cell_flags = {(int(cell["row"]), int(cell["col"])): int(cell.get("flags", 0x10)) for cell in map_cells}
    monster_indices = {(monster.pos.y, monster.pos.x): index for index, monster in enumerate(monsters)}
    places: list[SourcePlace] = []
    for col_index in range(MAXCOLS):
        for row_index in range(MAXLINES):
            ch = " "
            if 0 <= row_index < len(terrain):
                row = str(terrain[row_index])
                if 0 <= col_index < len(row):
                    ch = row[col_index]
            flags = trap_flags.get((row_index, col_index), cell_flags.get((row_index, col_index), 0x10))
            places.append(SourcePlace(ch=ch, flags=flags, monster_index=monster_indices.get((row_index, col_index), -1)))
    return places


def _runtime_source_max_stats(private: Any) -> SourceStats:
    max_strength = int(_field(private, "max_strength", _field(private, "strength", 16)))
    return SourceStats(
        strength=_source_strength_value(max_strength, max_strength),
        exp=int(_field(private, "player_exp", 0)),
        level=int(_field(private, "player_level", 1)),
        armor=int(_field(private, "player_armor", 10)),
        hp=int(_field(private, "max_hp", _field(private, "hp", 12))),
        damage=str(_field(private, "player_damage", "1x4")),
        max_hp=int(_field(private, "max_hp", 12)),
    )


def _runtime_source_rooms(private: Any) -> list[SourceRoom]:
    return _runtime_room_list(list(_field(private, "source_rooms", [])), MAXROOMS, _default_room())


def _runtime_source_passages(private: Any) -> list[SourceRoom]:
    default_passage = _default_room(flags=SOURCE_ROOM_ISGONE | SOURCE_ROOM_ISDARK)
    return _runtime_room_list(list(_field(private, "source_passages", [])), MAXPASS, default_passage)


def _runtime_room_list(values: list[Any], count: int, default: SourceRoom) -> list[SourceRoom]:
    rooms: list[SourceRoom] = []
    for raw in values[:count]:
        if isinstance(raw, dict):
            rooms.append(_source_room_from_mapping(raw))
    while len(rooms) < count:
        rooms.append(_clone_room(default))
    return rooms[:count]


def _source_room_from_mapping(raw: dict[str, Any]) -> SourceRoom:
    exits = []
    for value in list(raw.get("exits", [])):
        exits.append(_coord_value(value))
    return SourceRoom(
        pos=_coord_value(raw.get("pos", {"y": raw.get("row", 0), "x": raw.get("col", 0)})),
        max=_coord_value(raw.get("max", {"y": raw.get("height", 0), "x": raw.get("width", 0)})),
        gold=_coord_value(raw.get("gold", {"y": raw.get("gold_y", 0), "x": raw.get("gold_x", 0)})),
        goldval=int(raw.get("goldval", 0)),
        flags=int(raw.get("flags", 0)),
        exits=exits,
    )


def _default_room(*, flags: int = 0) -> SourceRoom:
    return SourceRoom(pos=Coord(0, 0), max=Coord(0, 0), gold=Coord(0, 0), goldval=0, flags=flags, exits=[])


def _clone_room(room: SourceRoom) -> SourceRoom:
    return SourceRoom(
        pos=Coord(room.pos.y, room.pos.x),
        max=Coord(room.max.y, room.max.x),
        gold=Coord(room.gold.y, room.gold.x),
        goldval=room.goldval,
        flags=room.flags,
        exits=[Coord(exit_coord.y, exit_coord.x) for exit_coord in room.exits],
    )


def _runtime_old_room_index(public: Any, private: Any) -> int:
    explicit = _field(private, "old_room_index", _field(private, "oldrp", None))
    if explicit is not None:
        return int(explicit)
    hero = tuple(_field(public, "hero", (0, 0)))
    for index, room in enumerate(_runtime_source_rooms(private)):
        if room.flags & SOURCE_ROOM_ISGONE:
            continue
        if room.pos.y <= int(hero[0]) < room.pos.y + room.max.y and room.pos.x <= int(hero[1]) < room.pos.x + room.max.x:
            return index
    return -1


def _source_strength_value(strength: int, max_strength: int) -> int:
    return ((strength & 0xFF) << 8) | (max_strength & 0xFF)


def _ref_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _runtime_objects(visible_items: dict[str, str], item_values: dict[str, int]) -> list[SourceObject]:
    objects: list[SourceObject] = []
    for index, (key, item) in enumerate(sorted(visible_items.items())):
        row, col = [int(part) for part in key.split(",")]
        objects.append(
            SourceObject(
                object_id=key,
                obj_type=item,
                pos=Coord(y=row, x=col),
                launch=-1,
                packch=chr(ord("a") + (index % 26)),
                damage="",
                hurldmg="",
                count=1,
                which=0,
                hplus=0,
                dplus=0,
                arm=int(item_values.get(key, 0)),
                flags=0,
                group=0,
                label=None,
            )
        )
    return objects


def _runtime_places(terrain: list[str], width: int, traps: list[dict[str, Any]] | None = None, map_cells: list[dict[str, Any]] | None = None) -> list[SourcePlace]:
    trap_flags = {(int(trap["row"]), int(trap["col"])): int(trap.get("flags", 0x10)) for trap in traps or []}
    cell_flags = {(int(cell["row"]), int(cell["col"])): int(cell.get("flags", 0x10)) for cell in map_cells or []}
    places: list[SourcePlace] = []
    for row_index, row in enumerate(terrain):
        padded = row + " " * (width - len(row))
        for col_index, ch in enumerate(padded):
            flags = trap_flags.get((row_index, col_index), cell_flags.get((row_index, col_index), 0x10))
            places.append(SourcePlace(ch=ch, flags=flags, monster_index=-1))
    return places


def _field(value: Any, name: str, default: Any = None) -> Any:
    if hasattr(value, name):
        return getattr(value, name)
    if isinstance(value, dict):
        return value.get(name, default)
    return default


def _objects() -> list[SourceObject]:
    return [
        SourceObject(
            object_id="weapon",
            obj_type=")",
            pos=Coord(4, 5),
            launch=2,
            packch="a",
            damage="1d8",
            hurldmg="1d6",
            count=1,
            which=1,
            hplus=2,
            dplus=-1,
            arm=0,
            flags=0o000006,
            group=3,
            label="etched",
        ),
        SourceObject(
            object_id="food",
            obj_type=":",
            pos=Coord(8, 9),
            launch=-1,
            packch="b",
            damage="",
            hurldmg="",
            count=2,
            which=0,
            hplus=0,
            dplus=0,
            arm=0,
            flags=0,
            group=0,
            label=None,
        ),
    ]


def _rooms() -> list[SourceRoom]:
    return [
        SourceRoom(
            pos=Coord(2, 4),
            max=Coord(6, 10),
            gold=Coord(5, 9),
            goldval=73,
            flags=0o000005,
            exits=[Coord(2, 7), Coord(6, 8)],
        ),
        SourceRoom(pos=Coord(12, 20), max=Coord(4, 8), gold=Coord(0, 0), goldval=0, flags=0, exits=[]),
    ]


def _passages() -> list[SourceRoom]:
    return [
        SourceRoom(
            pos=Coord(0, 0),
            max=Coord(0, 0),
            gold=Coord(0, 0),
            goldval=0,
            flags=SOURCE_ROOM_ISGONE | SOURCE_ROOM_ISDARK,
            exits=[Coord(3, 8), Coord(8, 3), Coord(8, 9)],
        ),
        SourceRoom(
            pos=Coord(0, 0),
            max=Coord(0, 0),
            gold=Coord(0, 0),
            goldval=0,
            flags=SOURCE_ROOM_ISGONE | SOURCE_ROOM_ISDARK,
            exits=[],
        ),
    ]


def _player(objects: list[SourceObject]) -> SourceThing:
    return SourceThing(
        thing_id="player",
        pos=Coord(10, 11),
        turn=False,
        thing_type="@",
        disguise="@",
        oldch=".",
        dest_kind="null",
        dest_index=0,
        flags=0o020000,
        stats=SourceStats(0x1010, 220, 5, 3, 31, "1d4", 36),
        room_index=0,
        pack=objects,
    )


def _monsters(objects: list[SourceObject]) -> list[SourceThing]:
    return [
        SourceThing(
            thing_id="kestrel",
            pos=Coord(3, 30),
            turn=True,
            thing_type="K",
            disguise="K",
            oldch=".",
            dest_kind="hero",
            dest_index=1,
            flags=0o020040,
            stats=SourceStats(0x0909, 12, 1, 8, 4, "1d4", 4),
            room_index=1,
            pack=[],
        ),
        SourceThing(
            thing_id="nymph",
            pos=Coord(7, 35),
            turn=False,
            thing_type="N",
            disguise="N",
            oldch=".",
            dest_kind="object",
            dest_index=0,
            flags=0o020000,
            stats=SourceStats(0x0808, 50, 3, 9, 12, "0d0", 12),
            room_index=1,
            pack=[objects[1]],
        ),
        SourceThing(
            thing_id="dragon",
            pos=Coord(11, 40),
            turn=False,
            thing_type="D",
            disguise="D",
            oldch=".",
            dest_kind="monster",
            dest_index=0,
            flags=0o020000,
            stats=SourceStats(0x1515, 5000, 10, -1, 80, "1d8/1d8/3d10", 80),
            room_index=2,
            pack=[],
        ),
    ]


def _dest_pair(thing: SourceThing, monsters: list[SourceThing], objects: list[SourceObject]) -> tuple[int, int]:
    if thing.dest_kind == "hero":
        return 0, 1
    if thing.dest_kind == "monster":
        return 1, thing.dest_index if 0 <= thing.dest_index < len(monsters) else -1
    if thing.dest_kind == "object":
        return 2, thing.dest_index if 0 <= thing.dest_index < len(objects) else -1
    if thing.dest_kind == "room_gold":
        return 3, thing.dest_index if 0 <= thing.dest_index < MAXROOMS else -1
    return 0, 0


def _fixed_bytes(value: str, count: int) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > count:
        return raw[:count]
    return raw + b"\0" * (count - len(raw))


def _char_byte(value: str) -> bytes:
    if not value:
        return b"\0"
    return bytes([ord(value[0]) & 0xFF])


def _case_summary(name: str, payload: bytes) -> dict[str, Any]:
    return {
        "name": name,
        "len": len(payload),
        "hex": payload.hex(),
    }
