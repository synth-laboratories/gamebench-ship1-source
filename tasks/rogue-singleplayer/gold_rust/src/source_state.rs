use crate::{PrivateState, PublicState, ResolvedTask, RogueRng, GOLD};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

const RSID_STATS: u32 = 0xABCD0001;
const RSID_THING: u32 = 0xABCD0002;
const RSID_OBJECT: u32 = 0xABCD0003;
const RSID_MAGICITEMS: u32 = 0xABCD0004;
const RSID_OBJECTLIST: u32 = 0xABCD0007;
const RSID_MONSTERLIST: u32 = 0xABCD0009;
const RSID_MONSTERS: u32 = 0xABCD000B;
const RSID_WINDOW: u32 = 0xABCD000D;
const RSID_DAEMONS: u32 = 0xABCD000E;
const RSID_ROOMS: u32 = 0xABCD0017;
const MAXROOMS: i32 = 9;
const NUMTHINGS: usize = 7;
const MAXPASS: usize = 13;
const MAXSTR: usize = 1024;
const MAXPOTIONS: usize = 14;
const MAXRINGS: usize = 14;
const MAXSCROLLS: usize = 18;
const MAXSTICKS: usize = 14;
const MAXARMORS: usize = 8;
const MAXWEAPONS: usize = 9;
const MAXNAME: usize = 40;
const MAXLINES: usize = 32;
const MAXCOLS: usize = 80;
const SOURCE_ROOM_ISDARK: i32 = 0o000001;
const SOURCE_ROOM_ISGONE: i32 = 0o000002;
const CHECKPOINT_VERSION: &str = "rogue-5.4.4";
const SOURCE_SAVE_VERSION: &str = "rogue (rogueforge) 09/05/07";
const SOURCE_ENCSTR: &[u8] = &[
    0o300, b'k', b'|', b'|', b'`', 0o251, b'Y', b'.', b'\'', 0o305, 0o321, 0o201, b'+', 0o277,
    b'~', b'r', b'"', b']', 0o240, b'_', 0o223, b'=', b'1', 0o341, b')', 0o222, 0o212, 0o241, b't',
    b';', b'\t', b'$', 0o270, 0o314, b'/', b'<', b'#', 0o201, 0o254,
];
const SOURCE_STATLIST: &[u8] = &[
    0o355, b'k', b'l', b'{', b'+', 0o204, 0o255, 0o313, b'i', b'd', b'J', 0o361, 0o214, b'=', b'4',
    b':', 0o311, 0o271, 0o341, b'w', b'K', b'<', 0o312, 0o321, 0o213, b',', b',', b'7', 0o271,
    b'/', b'R', b'k', b'%', b'\x08', 0o312, b'\x0c', 0o246,
];
const SOURCE_SAVE_IDENTITY_TEXT_FIELDS: &[&str] = &[
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
];
const SOURCE_SAVE_SCALAR_FIELDS: &[&str] = &[
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
];
const SOURCE_SAVE_PLAYER_REF_FIELDS: &[&str] = &[
    "player",
    "cur_armor",
    "cur_ring_left",
    "cur_ring_right",
    "cur_weapon",
    "l_last_pick",
    "last_pick",
];
const SOURCE_SAVE_LEVEL_STATE_FIELDS: &[&str] = &["lvl_obj", "mlist", "places"];
const SOURCE_SAVE_ROOM_STATE_FIELDS: &[&str] = &["max_stats", "rooms", "oldrp", "passages"];
const SOURCE_SAVE_INFO_STATE_FIELDS: &[&str] = &[
    "monsters",
    "things",
    "arm_info",
    "pot_info",
    "ring_info",
    "scr_info",
    "weap_info",
    "ws_info",
];
const SOURCE_SAVE_TAIL_STATE_FIELDS: &[&str] =
    &["d_list", "total", "between", "nh", "group", "stdscr"];
const SOURCE_A_CLASS: &[i32] = &[8, 7, 7, 6, 5, 4, 4, 3];
const SOURCE_E_LEVELS: &[i32] = &[
    10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000,
    800000, 2000000, 4000000, 8000000, 0,
];
const SOURCE_RAINBOW: &[&str] = &[
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
];
const SOURCE_SYLLS: &[&str] = &[
    "a", "ab", "ag", "aks", "ala", "an", "app", "arg", "arze", "ash", "bek", "bie", "bit", "bjor",
    "blu", "bot", "bu", "byt", "comp", "con", "cos", "cre", "dalf", "dan", "den", "do", "e", "eep",
    "el", "eng", "er", "ere", "erk", "esh", "evs", "fa", "fid", "fri", "fu", "gan", "gar", "glen",
    "gop", "gre", "ha", "hyd", "i", "ing", "ip", "ish", "it", "ite", "iv", "jo", "kho", "kli",
    "klis", "la", "lech", "mar", "me", "mi", "mic", "mik", "mon", "mung", "mur", "nej", "nelg",
    "nep", "ner", "nes", "nes", "nih", "nin", "o", "od", "ood", "org", "orn", "ox", "oxy", "pay",
    "ple", "plu", "po", "pot", "prok", "re", "rea", "rhov", "ri", "ro", "rog", "rok", "rol", "sa",
    "san", "sat", "sef", "seh", "shu", "ski", "sna", "sne", "snik", "sno", "so", "sol", "sri",
    "sta", "sun", "ta", "tab", "tem", "ther", "ti", "tox", "trol", "tue", "turs", "u", "ulk", "um",
    "un", "uni", "ur", "val", "viv", "vly", "vom", "wah", "wed", "werg", "wex", "whon", "wun",
    "xo", "y", "yot", "yu", "zant", "zeb", "zim", "zok", "zon", "zum",
];
const SOURCE_STONES: &[&str] = &[
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
];
const SOURCE_WOOD: &[&str] = &[
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
];
const SOURCE_METAL: &[&str] = &[
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
];
const SOURCE_INV_T_NAME: &[&str] = &["Overwrite", "Slow", "Clear"];
const SOURCE_TRAP_NAMES: &[&str] = &[
    "a trapdoor",
    "an arrow trap",
    "a sleeping gas trap",
    "a beartrap",
    "a teleport trap",
    "a poison dart trap",
    "a rust trap",
    "a mysterious trap",
];
const SOURCE_MONSTER_STATS: &[(u32, i32, i32, i32, i32, &str, i32)] = &[
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
];
const SOURCE_THINGS_INFO: &[(Option<&str>, i32, i32)] = &[
    (None, 26, 0),
    (None, 36, 0),
    (None, 16, 0),
    (None, 7, 0),
    (None, 7, 0),
    (None, 4, 0),
    (None, 4, 0),
];
const SOURCE_ARM_INFO: &[(Option<&str>, i32, i32)] = &[
    (Some("leather armor"), 20, 20),
    (Some("ring mail"), 15, 25),
    (Some("studded leather armor"), 15, 20),
    (Some("scale mail"), 13, 30),
    (Some("chain mail"), 12, 75),
    (Some("splint mail"), 10, 80),
    (Some("banded mail"), 10, 90),
    (Some("plate mail"), 5, 150),
];
const SOURCE_POT_INFO: &[(Option<&str>, i32, i32)] = &[
    (Some("confusion"), 7, 5),
    (Some("hallucination"), 8, 5),
    (Some("poison"), 8, 5),
    (Some("gain strength"), 13, 150),
    (Some("see invisible"), 3, 100),
    (Some("healing"), 13, 130),
    (Some("monster detection"), 6, 130),
    (Some("magic detection"), 6, 105),
    (Some("raise level"), 2, 250),
    (Some("extra healing"), 5, 200),
    (Some("haste self"), 5, 190),
    (Some("restore strength"), 13, 130),
    (Some("blindness"), 5, 5),
    (Some("levitation"), 6, 75),
];
const SOURCE_RING_INFO: &[(Option<&str>, i32, i32)] = &[
    (Some("protection"), 9, 400),
    (Some("add strength"), 9, 400),
    (Some("sustain strength"), 5, 280),
    (Some("searching"), 10, 420),
    (Some("see invisible"), 10, 310),
    (Some("adornment"), 1, 10),
    (Some("aggravate monster"), 10, 10),
    (Some("dexterity"), 8, 440),
    (Some("increase damage"), 8, 400),
    (Some("regeneration"), 4, 460),
    (Some("slow digestion"), 9, 240),
    (Some("teleportation"), 5, 30),
    (Some("stealth"), 7, 470),
    (Some("maintain armor"), 5, 380),
];
const SOURCE_SCR_INFO: &[(Option<&str>, i32, i32)] = &[
    (Some("monster confusion"), 7, 140),
    (Some("magic mapping"), 4, 150),
    (Some("hold monster"), 2, 180),
    (Some("sleep"), 3, 5),
    (Some("enchant armor"), 7, 160),
    (Some("identify potion"), 10, 80),
    (Some("identify scroll"), 10, 80),
    (Some("identify weapon"), 6, 80),
    (Some("identify armor"), 7, 100),
    (Some("identify ring, wand or staff"), 10, 115),
    (Some("scare monster"), 3, 200),
    (Some("food detection"), 2, 60),
    (Some("teleportation"), 5, 165),
    (Some("enchant weapon"), 8, 150),
    (Some("create monster"), 4, 75),
    (Some("remove curse"), 7, 105),
    (Some("aggravate monsters"), 3, 20),
    (Some("protect armor"), 2, 250),
];
const SOURCE_WEAP_INFO: &[(Option<&str>, i32, i32)] = &[
    (Some("mace"), 11, 8),
    (Some("long sword"), 11, 15),
    (Some("short bow"), 12, 15),
    (Some("arrow"), 12, 1),
    (Some("dagger"), 8, 3),
    (Some("two handed sword"), 10, 75),
    (Some("dart"), 12, 2),
    (Some("shuriken"), 12, 5),
    (Some("spear"), 12, 5),
    (None, 0, 0),
];
const SOURCE_WS_INFO: &[(Option<&str>, i32, i32)] = &[
    (Some("light"), 12, 250),
    (Some("invisibility"), 6, 5),
    (Some("lightning"), 3, 330),
    (Some("fire"), 3, 330),
    (Some("cold"), 3, 330),
    (Some("polymorph"), 15, 310),
    (Some("magic missile"), 10, 170),
    (Some("haste monster"), 10, 5),
    (Some("slow monster"), 11, 350),
    (Some("drain life"), 9, 300),
    (Some("nothing"), 1, 5),
    (Some("teleport away"), 6, 340),
    (Some("teleport to"), 6, 50),
    (Some("cancellation"), 5, 280),
];

#[derive(Clone)]
struct Coord {
    y: i32,
    x: i32,
}

#[derive(Clone)]
struct SourceStats {
    strength: u32,
    exp: i32,
    level: i32,
    armor: i32,
    hp: i32,
    damage: String,
    max_hp: i32,
}

#[derive(Clone)]
struct SourceMonsterInfo {
    stats: SourceStats,
}

#[derive(Clone)]
struct SourceObjInfo {
    prob: i32,
    worth: i32,
    guess: Option<String>,
    know: bool,
}

#[derive(Clone)]
struct SourceObject {
    object_id: String,
    obj_type: char,
    pos: Coord,
    launch: i32,
    packch: char,
    damage: String,
    hurldmg: String,
    count: i32,
    which: i32,
    hplus: i32,
    dplus: i32,
    arm: i32,
    flags: i32,
    group: i32,
    label: Option<String>,
}

#[derive(Clone)]
struct SourceRoom {
    pos: Coord,
    max: Coord,
    gold: Coord,
    goldval: i32,
    flags: i32,
    exits: Vec<Coord>,
}

#[derive(Clone)]
struct SourceThing {
    pos: Coord,
    turn: bool,
    thing_type: char,
    disguise: char,
    oldch: char,
    dest_kind: String,
    dest_index: i32,
    flags: i32,
    stats: SourceStats,
    room_index: i32,
    pack: Vec<SourceObject>,
}

#[derive(Clone)]
struct SourcePlace {
    ch: char,
    flags: i32,
    monster_index: i32,
}

#[derive(Clone)]
struct SourceDaemon {
    d_type: i32,
    func: i32,
    arg: i32,
    time: i32,
}

struct SourceSavePrefix {
    after: bool,
    again: bool,
    noscore: i32,
    seenstairs: bool,
    amulet: bool,
    door_stop: bool,
    fight_flush: bool,
    firstmove: bool,
    got_ltc: bool,
    has_hit: bool,
    in_shell: bool,
    inv_describe: bool,
    jump: bool,
    kamikaze: bool,
    lower_msg: bool,
    move_on: bool,
    msg_esc: bool,
    passgo: bool,
    playing: bool,
    q_comm: bool,
    running: bool,
    save_msg: bool,
    see_floor: bool,
    stat_msg: bool,
    terse: bool,
    to_death: bool,
    tombstone: bool,
    wizard: i32,
    pack_used: Vec<bool>,
}

#[derive(Clone)]
struct SourceStickIdentity {
    is_staff: bool,
    material_index: i32,
}

struct SourceSaveIdentityText {
    dir_ch: char,
    file_name: String,
    huh: String,
    potions: Vec<i32>,
    prbuf: String,
    rings: Vec<i32>,
    release: String,
    runch: char,
    scrolls: Vec<String>,
    take: char,
    whoami: String,
    sticks: Vec<SourceStickIdentity>,
    orig_dsusp: i32,
    fruit: String,
    home: String,
    inv_t_name: Vec<String>,
    l_last_comm: char,
    l_last_dir: char,
    last_comm: char,
    last_dir: char,
    tr_name: Vec<String>,
}

struct SourceSaveScalars {
    n_objs: i32,
    ntraps: i32,
    hungry_state: i32,
    inpack: i32,
    inv_type: i32,
    level: i32,
    max_level: i32,
    mpos: i32,
    no_food: i32,
    a_class: Vec<i32>,
    count: i32,
    food_left: i32,
    lastscore: i32,
    no_command: i32,
    no_move: i32,
    purse: i32,
    quiet: i32,
    vf_hit: i32,
    dnum: i32,
    seed: i32,
    e_levels: Vec<i32>,
    delta: Coord,
    oldpos: Coord,
    stairs: Coord,
}

struct StateWriter {
    data: Vec<u8>,
}

impl StateWriter {
    fn new() -> Self {
        Self { data: Vec::new() }
    }

    fn write_int(&mut self, value: i32) {
        self.data.extend_from_slice(&(value as u32).to_le_bytes());
    }

    fn write_ints(&mut self, values: &[i32]) {
        self.write_int(values.len() as i32);
        for value in values {
            self.write_int(*value);
        }
    }

    fn write_uint(&mut self, value: u32) {
        self.data.extend_from_slice(&value.to_le_bytes());
    }

    fn write_short(&mut self, value: i32) {
        self.data.extend_from_slice(&(value as u16).to_le_bytes());
    }

    fn write_char(&mut self, value: char) {
        self.data.push(value as u8);
    }

    fn write_boolean(&mut self, value: bool) {
        self.data.push(if value { 1 } else { 0 });
    }

    fn write_booleans(&mut self, values: &[bool]) {
        self.write_int(values.len() as i32);
        for value in values {
            self.write_boolean(*value);
        }
    }

    fn write_chars(&mut self, value: &[u8]) {
        self.write_int(value.len() as i32);
        self.data.extend_from_slice(value);
    }

    fn write_string(&mut self, value: Option<&str>) {
        let mut payload = Vec::new();
        if let Some(text) = value {
            payload.extend_from_slice(text.as_bytes());
            payload.push(0);
        }
        self.write_int(payload.len() as i32);
        self.write_chars(&payload);
    }

    fn write_strings(&mut self, values: &[String]) {
        self.write_int(values.len() as i32);
        for value in values {
            self.write_string(Some(value));
        }
    }

    fn write_marker(&mut self, marker: u32) {
        self.data.extend_from_slice(&marker.to_le_bytes());
    }

    fn write_coord(&mut self, coord: &Coord) {
        self.write_int(coord.x);
        self.write_int(coord.y);
    }

    fn write_stats(&mut self, stats: &SourceStats) {
        self.write_marker(RSID_STATS);
        self.write_uint(stats.strength);
        self.write_int(stats.exp);
        self.write_int(stats.level);
        self.write_int(stats.armor);
        self.write_int(stats.hp);
        self.write_chars(&fixed_bytes(&stats.damage, 13));
        self.write_int(stats.max_hp);
    }

    fn write_monsters(&mut self, monsters: &[SourceMonsterInfo]) {
        self.write_marker(RSID_MONSTERS);
        self.write_int(monsters.len() as i32);
        for monster in monsters {
            self.write_stats(&monster.stats);
        }
    }

    fn write_obj_info(&mut self, items: &[SourceObjInfo]) {
        self.write_marker(RSID_MAGICITEMS);
        self.write_int(items.len() as i32);
        for item in items {
            self.write_int(item.prob);
            self.write_int(item.worth);
            self.write_string(item.guess.as_deref());
            self.write_boolean(item.know);
        }
    }

    fn write_room(&mut self, room: &SourceRoom) {
        self.write_coord(&room.pos);
        self.write_coord(&room.max);
        self.write_coord(&room.gold);
        self.write_int(room.goldval);
        self.write_short(room.flags);
        self.write_int(room.exits.len() as i32);
        for index in 0..12 {
            let coord = room
                .exits
                .get(index)
                .cloned()
                .unwrap_or(Coord { y: 0, x: 0 });
            self.write_coord(&coord);
        }
    }

    fn write_rooms(&mut self, rooms: &[SourceRoom]) {
        self.write_int(rooms.len() as i32);
        for room in rooms {
            self.write_room(room);
        }
    }

    fn write_room_reference(&mut self, room_index: i32) {
        self.write_int(if (0..MAXROOMS).contains(&room_index) {
            room_index
        } else {
            -1
        });
    }

    fn write_object(&mut self, obj: &SourceObject) {
        self.write_marker(RSID_OBJECT);
        self.write_int(obj.obj_type as i32);
        self.write_coord(&obj.pos);
        self.write_int(obj.launch);
        self.write_char(obj.packch);
        self.write_chars(&fixed_bytes(&obj.damage, 8));
        self.write_chars(&fixed_bytes(&obj.hurldmg, 8));
        self.write_int(obj.count);
        self.write_int(obj.which);
        self.write_int(obj.hplus);
        self.write_int(obj.dplus);
        self.write_int(obj.arm);
        self.write_int(obj.flags);
        self.write_int(obj.group);
        self.write_string(obj.label.as_deref());
    }

    fn write_object_list(&mut self, objects: &[SourceObject]) {
        self.write_marker(RSID_OBJECTLIST);
        self.write_int(objects.len() as i32);
        for obj in objects {
            self.write_object(obj);
        }
    }

    fn write_object_reference(&mut self, objects: &[SourceObject], item_id: Option<&str>) {
        let mut index = -1;
        if let Some(id) = item_id {
            for (candidate_index, obj) in objects.iter().enumerate() {
                if obj.object_id == id {
                    index = candidate_index as i32;
                    break;
                }
            }
        }
        self.write_int(index);
    }

    fn write_thing(
        &mut self,
        thing: Option<&SourceThing>,
        monsters: &[SourceThing],
        objects: &[SourceObject],
    ) {
        self.write_marker(RSID_THING);
        let Some(thing) = thing else {
            self.write_int(0);
            return;
        };
        self.write_int(1);
        self.write_coord(&thing.pos);
        self.write_boolean(thing.turn);
        self.write_char(thing.thing_type);
        self.write_char(thing.disguise);
        self.write_char(thing.oldch);
        let (dest_list, dest_index) = dest_pair(thing, monsters, objects);
        self.write_int(dest_list);
        self.write_int(dest_index);
        self.write_short(thing.flags);
        self.write_stats(&thing.stats);
        self.write_room_reference(thing.room_index);
        self.write_object_list(&thing.pack);
    }

    fn write_thing_list(&mut self, things: &[SourceThing], objects: &[SourceObject]) {
        self.write_marker(RSID_MONSTERLIST);
        self.write_int(things.len() as i32);
        for thing in things {
            self.write_thing(Some(thing), things, objects);
        }
    }

    fn write_thing_reference(&mut self, things: &[SourceThing], index: i32) {
        self.write_int(if index >= 0 && (index as usize) < things.len() {
            index
        } else {
            -1
        });
    }

    fn write_places(&mut self, places: &[SourcePlace], monsters: &[SourceThing]) {
        for place in places {
            self.write_char(place.ch);
            self.write_char(char::from_u32((place.flags & 0xff) as u32).unwrap_or('\0'));
            self.write_thing_reference(monsters, place.monster_index);
        }
    }

    fn write_daemons(&mut self, daemons: &[SourceDaemon], count: usize) {
        self.write_marker(RSID_DAEMONS);
        self.write_int(count as i32);
        for index in 0..count {
            let daemon = daemons.get(index).cloned().unwrap_or(SourceDaemon {
                d_type: 0,
                func: 0,
                arg: 0,
                time: 0,
            });
            self.write_int(daemon.d_type);
            self.write_int(daemon.func);
            self.write_int(daemon.arg);
            self.write_int(daemon.time);
        }
    }

    fn write_window(&mut self, rows: &[String]) {
        let width = rows
            .iter()
            .map(|row| row.chars().count())
            .max()
            .unwrap_or(0);
        self.write_marker(RSID_WINDOW);
        self.write_int(rows.len() as i32);
        self.write_int(width as i32);
        for row in rows {
            let mut chars: Vec<char> = row.chars().collect();
            chars.resize(width, ' ');
            chars.truncate(width);
            for ch in chars {
                self.write_int(ch as i32);
            }
        }
    }

    fn write_save_identity_text_block(&mut self, block: &SourceSaveIdentityText) {
        self.write_char(block.dir_ch);
        self.write_chars(&fixed_bytes(&block.file_name, MAXSTR));
        self.write_chars(&fixed_bytes(&block.huh, MAXSTR));
        for index in int_list(&block.potions, MAXPOTIONS) {
            self.write_int(index);
        }
        self.write_chars(&fixed_bytes(&block.prbuf, 2 * MAXSTR));
        for index in int_list(&block.rings, MAXRINGS) {
            self.write_int(index);
        }
        self.write_string(Some(&block.release));
        self.write_char(block.runch);
        for name in string_list(&block.scrolls, MAXSCROLLS) {
            self.write_string(Some(&name));
        }
        self.write_char(block.take);
        self.write_chars(&fixed_bytes(&block.whoami, MAXSTR));
        for stick in stick_list(&block.sticks, MAXSTICKS) {
            self.write_int(if stick.is_staff { 0 } else { 1 });
            self.write_int(stick.material_index);
        }
        self.write_int(block.orig_dsusp);
        self.write_chars(&fixed_bytes(&block.fruit, MAXSTR));
        self.write_chars(&fixed_bytes(&block.home, MAXSTR));
        self.write_strings(&string_list(&block.inv_t_name, 3));
        self.write_char(block.l_last_comm);
        self.write_char(block.l_last_dir);
        self.write_char(block.last_comm);
        self.write_char(block.last_dir);
        self.write_strings(&string_list(&block.tr_name, 8));
    }

    fn write_save_scalar_block(&mut self, block: &SourceSaveScalars) {
        self.write_int(block.n_objs);
        self.write_int(block.ntraps);
        self.write_int(block.hungry_state);
        self.write_int(block.inpack);
        self.write_int(block.inv_type);
        self.write_int(block.level);
        self.write_int(block.max_level);
        self.write_int(block.mpos);
        self.write_int(block.no_food);
        self.write_ints(&int_list(&block.a_class, MAXARMORS));
        self.write_int(block.count);
        self.write_int(block.food_left);
        self.write_int(block.lastscore);
        self.write_int(block.no_command);
        self.write_int(block.no_move);
        self.write_int(block.purse);
        self.write_int(block.quiet);
        self.write_int(block.vf_hit);
        self.write_int(block.dnum);
        self.write_int(block.seed);
        self.write_ints(&int_list(&block.e_levels, SOURCE_E_LEVELS.len()));
        self.write_coord(&block.delta);
        self.write_coord(&block.oldpos);
        self.write_coord(&block.stairs);
    }
}

pub fn source_state_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_state.v1",
        "cases": cases()
            .into_iter()
            .map(|(name, payload)| case_summary(name, &payload))
            .collect::<Vec<_>>(),
    })
}

pub fn runtime_source_checkpoint_projection(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
    nev_cursor: usize,
) -> Value {
    let payload = runtime_source_checkpoint_bytes(resolved, public, private, nev_cursor);
    json!({
        "schema": "gamebench.rogue.source_checkpoint.v1",
        "authority": "modern-rogue state.c/save.c projection",
        "encoding": "rs_save_file_runtime_subset",
        "len": payload.len(),
        "sha256": sha256_hex(&payload),
        "hex": hex(&payload),
        "current_weapon_id": &private.current_weapon_id,
        "current_armor_id": &private.current_armor_id,
    })
}

pub fn runtime_source_save_file_projection(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
    nev_cursor: usize,
    file_name: &str,
) -> Value {
    let runtime_subset_payload =
        runtime_source_checkpoint_bytes(resolved, public, private, nev_cursor);
    let plain_payload =
        runtime_source_save_file_plain_body_bytes(resolved, public, private, nev_cursor, file_name);
    let prefix_payload = runtime_source_save_prefix_bytes(public, private);
    let identity_text_payload =
        runtime_source_save_identity_text_bytes(resolved, private, file_name);
    let scalar_payload = runtime_source_save_scalar_bytes(resolved, public, private);
    let player_refs_payload = runtime_source_save_player_refs_bytes(public, private);
    let level_state_payload = runtime_source_save_level_state_bytes(public, private);
    let room_state_payload = runtime_source_save_room_state_bytes(public, private);
    let info_state_payload = runtime_source_save_info_state_bytes(private);
    let tail_state_payload = runtime_source_save_tail_state_bytes(public, private);
    let save_payload =
        runtime_source_save_file_bytes(resolved, public, private, nev_cursor, file_name);
    let info_state_counts = json!({
        "things": NUMTHINGS,
        "arm_info": MAXARMORS,
        "pot_info": MAXPOTIONS,
        "ring_info": MAXRINGS,
        "scr_info": MAXSCROLLS,
        "weap_info": MAXWEAPONS + 1,
        "ws_info": MAXSTICKS,
    });
    let width = public
        .terrain
        .iter()
        .map(|row| row.chars().count())
        .max()
        .unwrap_or(0);
    let mut projection = serde_json::Map::new();
    projection.insert(
        "schema".to_string(),
        json!("gamebench.rogue.source_save_file.v1"),
    );
    projection.insert(
        "authority".to_string(),
        json!("modern-rogue save.c encwrite + state.c rs_save_file projection"),
    );
    projection.insert(
        "encoding".to_string(),
        json!("encwrite(version) + encwrite(geometry) + encwrite(rs_save_file_prefix + rs_save_file_identity_text + rs_save_file_scalars + rs_save_file_player_refs + rs_save_file_level_state + rs_save_file_room_state + rs_save_file_info_state + rs_save_file_tail_state)"),
    );
    projection.insert("version".to_string(), json!(SOURCE_SAVE_VERSION));
    projection.insert(
        "geometry".to_string(),
        json!(format!("{} x {}\n", public.terrain.len(), width)),
    );
    projection.insert("len".to_string(), json!(save_payload.len()));
    projection.insert("sha256".to_string(), json!(sha256_hex(&save_payload)));
    projection.insert("hex".to_string(), json!(hex(&save_payload)));
    projection.insert(
        "plain_subset_sha256".to_string(),
        json!(sha256_hex(&plain_payload)),
    );
    projection.insert(
        "runtime_subset_sha256".to_string(),
        json!(sha256_hex(&runtime_subset_payload)),
    );
    projection.insert(
        "rs_save_file_prefix_len".to_string(),
        json!(prefix_payload.len()),
    );
    projection.insert(
        "rs_save_file_prefix_sha256".to_string(),
        json!(sha256_hex(&prefix_payload)),
    );
    projection.insert(
        "rs_save_file_prefix_fields".to_string(),
        json!(source_save_prefix_field_names()),
    );
    projection.insert(
        "rs_save_file_identity_text_len".to_string(),
        json!(identity_text_payload.len()),
    );
    projection.insert(
        "rs_save_file_identity_text_sha256".to_string(),
        json!(sha256_hex(&identity_text_payload)),
    );
    projection.insert(
        "rs_save_file_identity_text_fields".to_string(),
        json!(SOURCE_SAVE_IDENTITY_TEXT_FIELDS),
    );
    projection.insert(
        "rs_save_file_scalar_len".to_string(),
        json!(scalar_payload.len()),
    );
    projection.insert(
        "rs_save_file_scalar_sha256".to_string(),
        json!(sha256_hex(&scalar_payload)),
    );
    projection.insert(
        "rs_save_file_scalar_fields".to_string(),
        json!(SOURCE_SAVE_SCALAR_FIELDS),
    );
    projection.insert(
        "rs_save_file_player_refs_len".to_string(),
        json!(player_refs_payload.len()),
    );
    projection.insert(
        "rs_save_file_player_refs_sha256".to_string(),
        json!(sha256_hex(&player_refs_payload)),
    );
    projection.insert(
        "rs_save_file_player_refs_fields".to_string(),
        json!(SOURCE_SAVE_PLAYER_REF_FIELDS),
    );
    projection.insert(
        "rs_save_file_level_state_len".to_string(),
        json!(level_state_payload.len()),
    );
    projection.insert(
        "rs_save_file_level_state_sha256".to_string(),
        json!(sha256_hex(&level_state_payload)),
    );
    projection.insert(
        "rs_save_file_level_state_fields".to_string(),
        json!(SOURCE_SAVE_LEVEL_STATE_FIELDS),
    );
    projection.insert(
        "rs_save_file_level_state_places_count".to_string(),
        json!(MAXLINES * MAXCOLS),
    );
    projection.insert(
        "rs_save_file_room_state_len".to_string(),
        json!(room_state_payload.len()),
    );
    projection.insert(
        "rs_save_file_room_state_sha256".to_string(),
        json!(sha256_hex(&room_state_payload)),
    );
    projection.insert(
        "rs_save_file_room_state_fields".to_string(),
        json!(SOURCE_SAVE_ROOM_STATE_FIELDS),
    );
    projection.insert(
        "rs_save_file_room_state_rooms_count".to_string(),
        json!(MAXROOMS),
    );
    projection.insert(
        "rs_save_file_room_state_passages_count".to_string(),
        json!(MAXPASS),
    );
    projection.insert(
        "rs_save_file_info_state_len".to_string(),
        json!(info_state_payload.len()),
    );
    projection.insert(
        "rs_save_file_info_state_sha256".to_string(),
        json!(sha256_hex(&info_state_payload)),
    );
    projection.insert(
        "rs_save_file_info_state_fields".to_string(),
        json!(SOURCE_SAVE_INFO_STATE_FIELDS),
    );
    projection.insert(
        "rs_save_file_info_state_monsters_count".to_string(),
        json!(26),
    );
    projection.insert(
        "rs_save_file_info_state_counts".to_string(),
        info_state_counts,
    );
    projection.insert(
        "rs_save_file_tail_state_len".to_string(),
        json!(tail_state_payload.len()),
    );
    projection.insert(
        "rs_save_file_tail_state_sha256".to_string(),
        json!(sha256_hex(&tail_state_payload)),
    );
    projection.insert(
        "rs_save_file_tail_state_fields".to_string(),
        json!(SOURCE_SAVE_TAIL_STATE_FIELDS),
    );
    projection.insert(
        "rs_save_file_tail_state_daemons_count".to_string(),
        json!(20),
    );
    projection.insert(
        "rs_save_file_tail_state_window_height".to_string(),
        json!(public.terrain.len()),
    );
    projection.insert(
        "rs_save_file_tail_state_window_width".to_string(),
        json!(width),
    );
    Value::Object(projection)
}

pub fn runtime_source_save_file_bytes(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
    nev_cursor: usize,
    file_name: &str,
) -> Vec<u8> {
    let plain_payload =
        runtime_source_save_file_plain_body_bytes(resolved, public, private, nev_cursor, file_name);
    let width = public
        .terrain
        .iter()
        .map(|row| row.chars().count())
        .max()
        .unwrap_or(0);
    source_save_file_envelope(&plain_payload, public.terrain.len() as i32, width as i32)
}

pub fn runtime_source_save_file_plain_body_bytes(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
    _nev_cursor: usize,
    file_name: &str,
) -> Vec<u8> {
    let mut output = runtime_source_save_prefix_bytes(public, private);
    output.extend_from_slice(&runtime_source_save_identity_text_bytes(
        resolved, private, file_name,
    ));
    output.extend_from_slice(&runtime_source_save_scalar_bytes(resolved, public, private));
    output.extend_from_slice(&runtime_source_save_player_refs_bytes(public, private));
    output.extend_from_slice(&runtime_source_save_level_state_bytes(public, private));
    output.extend_from_slice(&runtime_source_save_room_state_bytes(public, private));
    output.extend_from_slice(&runtime_source_save_info_state_bytes(private));
    output.extend_from_slice(&runtime_source_save_tail_state_bytes(public, private));
    output
}

pub fn runtime_source_save_prefix_bytes(_public: &PublicState, private: &PrivateState) -> Vec<u8> {
    let mut writer = StateWriter::new();
    write_source_save_prefix(&mut writer, &runtime_source_save_prefix_values(private));
    writer.data
}

pub fn runtime_source_save_identity_text_bytes(
    resolved: &ResolvedTask,
    private: &PrivateState,
    file_name: &str,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_save_identity_text_block(&runtime_source_save_identity_text_values(
        resolved, private, file_name,
    ));
    writer.data
}

pub fn runtime_source_identity_display(resolved: &ResolvedTask, _private: &PrivateState) -> Value {
    let (potions, scrolls, rings, sticks) = source_identity_tables(resolved.seed as i32);
    json!({
        "potions": potions
            .iter()
            .map(|index| SOURCE_RAINBOW[*index as usize])
            .collect::<Vec<_>>(),
        "scrolls": scrolls,
        "rings": rings
            .iter()
            .map(|index| SOURCE_STONES[*index as usize])
            .collect::<Vec<_>>(),
        "sticks": sticks
            .iter()
            .map(|stick| {
                if stick.is_staff {
                    json!({"type": "staff", "material": SOURCE_WOOD[stick.material_index as usize]})
                } else {
                    json!({"type": "wand", "material": SOURCE_METAL[stick.material_index as usize]})
                }
            })
            .collect::<Vec<_>>(),
    })
}

pub fn runtime_source_save_scalar_bytes(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_save_scalar_block(&runtime_source_save_scalar_values(
        resolved, public, private,
    ));
    writer.data
}

pub fn runtime_source_save_player_refs_bytes(
    public: &PublicState,
    private: &PrivateState,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    let pack = runtime_source_inventory_objects(public, private);
    let player = runtime_source_player_thing(public, private, &pack);
    writer.write_thing(Some(&player), &[], &pack);
    let refs = [
        private.current_armor_id.as_str(),
        private.left_ring_id.as_str(),
        private.right_ring_id.as_str(),
        private.current_weapon_id.as_str(),
        "",
        "",
    ];
    for item_id in refs {
        writer.write_object_reference(&player.pack, ref_id(item_id));
    }
    writer.data
}

pub fn runtime_source_save_level_state_bytes(
    public: &PublicState,
    private: &PrivateState,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    let level_objects = runtime_source_level_objects(public, private);
    let monsters = runtime_source_monsters(private, &level_objects);
    let places = runtime_source_places(public, private, &monsters);
    writer.write_object_list(&level_objects);
    writer.write_thing_list(&monsters, &level_objects);
    writer.write_places(&places, &monsters);
    writer.data
}

pub fn runtime_source_save_room_state_bytes(
    public: &PublicState,
    private: &PrivateState,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_stats(&runtime_source_max_stats(private));
    writer.write_rooms(&runtime_source_rooms(private));
    writer.write_room_reference(runtime_old_room_index(public, private));
    writer.write_rooms(&runtime_source_passages(private));
    writer.data
}

pub fn runtime_source_save_info_state_bytes(private: &PrivateState) -> Vec<u8> {
    let mut writer = StateWriter::new();
    write_source_save_info_state(&mut writer, private);
    writer.data
}

pub fn runtime_source_save_tail_state_bytes(
    public: &PublicState,
    private: &PrivateState,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_daemons(&runtime_source_daemons(private), 20);
    writer.write_int(0);
    writer.write_int(private.daemon_between);
    writer.write_coord(&runtime_source_nh(private));
    writer.write_int(0);
    writer.write_window(&runtime_source_window_rows(public));
    writer.data
}

pub fn runtime_source_checkpoint_bytes(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
    nev_cursor: usize,
) -> Vec<u8> {
    let mut writer = StateWriter::new();
    let width = public
        .terrain
        .iter()
        .map(|row| row.chars().count())
        .max()
        .unwrap_or(0);
    write_save_header_projection(
        &mut writer,
        CHECKPOINT_VERSION,
        public.terrain.len() as i32,
        width as i32,
    );
    writer.write_int(private.step_index as i32);
    writer.write_int(nev_cursor as i32);
    writer.write_int(private.dungeon_level as i32);
    writer.write_int(private.max_level as i32);
    writer.write_boolean(private.has_amulet);
    writer.write_int(private.purse as i32);
    writer.write_int(private.food as i32);
    writer.write_int(private.rng_seed);
    writer.write_boolean(private.command_after);
    writer.write_boolean(private.command_running);
    writer.write_int(private.command_count);
    writer.write_char(first_char(&private.command_last));
    writer.write_char(first_char(&private.command_direction));
    writer.write_char(first_char(&private.command_runch));
    writer.write_boolean(private.command_to_death);
    writer.write_int(private.player_flags);
    writer.write_int(private.strength);
    writer.write_int(private.max_strength);
    writer.write_int(private.no_command);
    writer.write_int(private.no_move);
    writer.write_int(private.food_left);
    writer.write_int(private.hungry_state);
    writer.write_int(private.quiet);
    writer.write_int(private.daemon_between);
    for known in [
        &private.pot_known,
        &private.ring_known,
        &private.scr_known,
        &private.ws_known,
    ] {
        writer.write_int(known.len() as i32);
        for value in known {
            writer.write_boolean(*value);
        }
    }
    writer.write_int(private.source_effect_markers.len() as i32);
    for marker in &private.source_effect_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.source_combat_markers.len() as i32);
    for marker in &private.source_combat_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.source_attack_markers.len() as i32);
    for marker in &private.source_attack_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.source_chase_markers.len() as i32);
    for marker in &private.source_chase_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.source_trap_markers.len() as i32);
    for marker in &private.source_trap_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.source_daemon_markers.len() as i32);
    for marker in &private.source_daemon_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.source_level_markers.len() as i32);
    for marker in &private.source_level_markers {
        writer.write_string(Some(marker));
    }
    writer.write_int(private.player_exp);
    writer.write_int(private.player_level);
    writer.write_int(private.player_armor);
    writer.write_string(Some(&private.player_damage));
    writer.write_string(Some(&private.current_weapon_id));
    writer.write_string(Some(&private.current_armor_id));
    writer.write_int(private.vf_hit);
    writer.write_int(private.max_hit);
    writer.write_boolean(private.kamikaze);
    writer.write_int(private.source_inventory.len() as i32);
    for item in &private.source_inventory {
        let text = serde_json::to_string(item).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_monsters.len() as i32);
    for monster in &private.source_monsters {
        let text = serde_json::to_string(monster).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_traps.len() as i32);
    for trap in &private.source_traps {
        let text = serde_json::to_string(trap).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_map_cells.len() as i32);
    for cell in &private.source_map_cells {
        let text = serde_json::to_string(cell).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_daemon_actions.len() as i32);
    for action in &private.source_daemon_actions {
        let text = serde_json::to_string(action).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_level_objects.len() as i32);
    for obj in &private.source_level_objects {
        let text = serde_json::to_string(obj).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_rooms.len() as i32);
    for room in &private.source_rooms {
        let text = serde_json::to_string(room).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(private.source_passages.len() as i32);
    for passage in &private.source_passages {
        let text = serde_json::to_string(passage).unwrap();
        writer.write_string(Some(&text));
    }
    writer.write_int(public.visible_monsters.len() as i32);
    for (key, value) in &public.visible_monsters {
        writer.write_string(Some(key));
        writer.write_string(Some(value));
    }
    writer.write_string(Some(&resolved.episode_id));
    writer.write_string(Some(&resolved.config_hash));
    writer.write_coord(&Coord {
        y: public.hero.0 as i32,
        x: public.hero.1 as i32,
    });
    writer.write_stats(&SourceStats {
        strength: 0x1010,
        exp: private.purse as i32,
        level: private.dungeon_level as i32,
        armor: 10,
        hp: private.hp as i32,
        damage: "1d4".to_string(),
        max_hp: private.max_hp as i32,
    });
    let objects = runtime_objects(public, private);
    writer.write_object_list(&objects);
    writer.write_int(public.terrain.len() as i32);
    writer.write_int(width as i32);
    writer.write_places(
        &runtime_places(
            &public.terrain,
            width,
            &private.source_traps,
            &private.source_map_cells,
        ),
        &[],
    );
    writer.data
}

fn cases() -> Vec<(&'static str, Vec<u8>)> {
    vec![
        ("primitive_block", primitive_block()),
        ("stats_and_rooms", stats_and_rooms()),
        ("object_list_and_refs", object_list_and_refs()),
        ("thing_list_and_places", thing_list_and_places()),
        (
            "daemons_and_save_header_projection",
            daemons_and_save_header_projection(),
        ),
        ("save_file_prefix_block", save_file_prefix_block()),
        (
            "save_file_identity_text_block",
            save_file_identity_text_block(),
        ),
        ("save_file_scalar_block", save_file_scalar_block()),
        ("save_file_player_refs_block", save_file_player_refs_block()),
        ("save_file_level_state_block", save_file_level_state_block()),
        ("save_file_room_state_block", save_file_room_state_block()),
        ("save_file_info_state_block", save_file_info_state_block()),
        ("save_file_tail_state_block", save_file_tail_state_block()),
        ("encwrite_known_bytes", encwrite_known_bytes()),
        (
            "save_file_envelope_projection",
            save_file_envelope_projection(),
        ),
    ]
}

fn primitive_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_int(0x12345678);
    writer.write_int(-2);
    writer.write_uint(0x89ABCDEF);
    writer.write_short(-1234);
    writer.write_boolean(true);
    writer.write_boolean(false);
    writer.write_char('A');
    writer.write_chars(b"abc");
    writer.write_string(Some("hello"));
    writer.write_string(None);
    writer.write_coord(&Coord { y: 7, x: 3 });
    writer.data
}

fn stats_and_rooms() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_stats(&SourceStats {
        strength: 0x1234,
        exp: 55,
        level: 4,
        armor: -2,
        hp: 17,
        damage: "1d8/1d3".to_string(),
        max_hp: 25,
    });
    writer.write_marker(RSID_ROOMS);
    writer.write_rooms(&[
        SourceRoom {
            pos: Coord { y: 2, x: 4 },
            max: Coord { y: 6, x: 10 },
            gold: Coord { y: 5, x: 9 },
            goldval: 73,
            flags: 0o000005,
            exits: vec![Coord { y: 2, x: 7 }, Coord { y: 6, x: 8 }],
        },
        SourceRoom {
            pos: Coord { y: 12, x: 20 },
            max: Coord { y: 4, x: 8 },
            gold: Coord { y: 0, x: 0 },
            goldval: 0,
            flags: 0,
            exits: Vec::new(),
        },
    ]);
    writer.write_room_reference(1);
    writer.write_room_reference(12);
    writer.data
}

fn object_list_and_refs() -> Vec<u8> {
    let objects = objects();
    let mut writer = StateWriter::new();
    writer.write_object_list(&objects);
    writer.write_object_reference(&objects, Some("weapon"));
    writer.write_object_reference(&objects, Some("missing"));
    writer.data
}

fn thing_list_and_places() -> Vec<u8> {
    let objects = objects();
    let monsters = monsters(&objects);
    let player = player(&objects);
    let mut writer = StateWriter::new();
    writer.write_thing(Some(&player), &monsters, &objects);
    writer.write_object_reference(&player.pack, Some("food"));
    writer.write_thing_list(&monsters, &objects);
    writer.write_places(
        &[
            SourcePlace {
                ch: '.',
                flags: 0x10,
                monster_index: -1,
            },
            SourcePlace {
                ch: 'A',
                flags: 0x50,
                monster_index: 0,
            },
            SourcePlace {
                ch: 'B',
                flags: 0x40,
                monster_index: 1,
            },
        ],
        &monsters,
    );
    writer.data
}

fn daemons_and_save_header_projection() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_daemons(
        &[
            SourceDaemon {
                d_type: 1,
                func: 2,
                arg: 0,
                time: 30,
            },
            SourceDaemon {
                d_type: 2,
                func: 5,
                arg: 7,
                time: 80,
            },
        ],
        4,
    );
    write_save_header_projection(&mut writer, "rogue-5.4.4", 24, 80);
    writer.data
}

fn save_file_prefix_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    write_source_save_prefix(
        &mut writer,
        &SourceSavePrefix {
            after: true,
            again: false,
            noscore: 7,
            seenstairs: true,
            amulet: true,
            door_stop: false,
            fight_flush: true,
            firstmove: false,
            got_ltc: false,
            has_hit: true,
            in_shell: false,
            inv_describe: true,
            jump: true,
            kamikaze: true,
            lower_msg: false,
            move_on: true,
            msg_esc: false,
            passgo: true,
            playing: true,
            q_comm: false,
            running: true,
            save_msg: true,
            see_floor: true,
            stat_msg: false,
            terse: true,
            to_death: true,
            tombstone: true,
            wizard: 0,
            pack_used: (0..26).map(|index| matches!(index, 0 | 2 | 25)).collect(),
        },
    );
    writer.data
}

fn save_file_identity_text_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_save_identity_text_block(&SourceSaveIdentityText {
        dir_ch: 'h',
        file_name: "save.dat".to_string(),
        huh: "last message".to_string(),
        potions: (0..MAXPOTIONS as i32).collect(),
        prbuf: "scratch".to_string(),
        rings: (0..MAXRINGS as i32).rev().collect(),
        release: "5.4.4".to_string(),
        runch: 'l',
        scrolls: (0..MAXSCROLLS)
            .map(|index| format!("scroll {index}"))
            .collect(),
        take: '!',
        whoami: "player".to_string(),
        sticks: (0..MAXSTICKS)
            .map(|index| SourceStickIdentity {
                is_staff: index % 2 == 0,
                material_index: index as i32,
            })
            .collect(),
        orig_dsusp: 26,
        fruit: "slime-mold".to_string(),
        home: "/tmp/rogue".to_string(),
        inv_t_name: SOURCE_INV_T_NAME
            .iter()
            .map(|value| value.to_string())
            .collect(),
        l_last_comm: 's',
        l_last_dir: 'h',
        last_comm: 'f',
        last_dir: 'l',
        tr_name: SOURCE_TRAP_NAMES
            .iter()
            .map(|value| value.to_string())
            .collect(),
    });
    writer.data
}

fn save_file_scalar_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_save_scalar_block(&SourceSaveScalars {
        n_objs: 3,
        ntraps: 5,
        hungry_state: 2,
        inpack: 7,
        inv_type: 1,
        level: 9,
        max_level: 11,
        mpos: 13,
        no_food: 17,
        a_class: SOURCE_A_CLASS.to_vec(),
        count: 19,
        food_left: 1200,
        lastscore: -1,
        no_command: 4,
        no_move: 6,
        purse: 777,
        quiet: 8,
        vf_hit: 10,
        dnum: 12,
        seed: 12345,
        e_levels: SOURCE_E_LEVELS.to_vec(),
        delta: Coord { y: -1, x: 1 },
        oldpos: Coord { y: 2, x: 3 },
        stairs: Coord { y: 4, x: 5 },
    });
    writer.data
}

fn save_file_player_refs_block() -> Vec<u8> {
    let objects = objects();
    let player = player(&objects);
    let mut writer = StateWriter::new();
    writer.write_thing(Some(&player), &[], &objects);
    for item_id in [
        Some("food"),
        Some("weapon"),
        None,
        Some("weapon"),
        Some("food"),
        Some("missing"),
    ] {
        writer.write_object_reference(&player.pack, item_id);
    }
    writer.data
}

fn save_file_level_state_block() -> Vec<u8> {
    let objects = objects();
    let monsters = monsters(&objects);
    let places = [
        SourcePlace {
            ch: '.',
            flags: 0x10,
            monster_index: -1,
        },
        SourcePlace {
            ch: 'A',
            flags: 0x50,
            monster_index: 0,
        },
        SourcePlace {
            ch: 'B',
            flags: 0x40,
            monster_index: 1,
        },
    ];
    let mut writer = StateWriter::new();
    writer.write_object_list(&objects);
    writer.write_thing_list(&monsters, &objects);
    writer.write_places(&places, &monsters);
    writer.data
}

fn save_file_room_state_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_stats(&SourceStats {
        strength: 0x1010,
        exp: 220,
        level: 5,
        armor: 3,
        hp: 36,
        damage: "1d4".to_string(),
        max_hp: 40,
    });
    writer.write_rooms(&rooms());
    writer.write_room_reference(1);
    writer.write_rooms(&passages());
    writer.data
}

fn save_file_info_state_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    write_source_save_info_state_known(
        &mut writer,
        &[true, false],
        &[false, true],
        &[false, true],
        &[true],
    );
    writer.data
}

fn save_file_tail_state_block() -> Vec<u8> {
    let mut writer = StateWriter::new();
    writer.write_daemons(
        &[
            SourceDaemon {
                d_type: 2,
                func: 2,
                arg: 0,
                time: -1,
            },
            SourceDaemon {
                d_type: 1,
                func: 9,
                arg: 0,
                time: 5,
            },
        ],
        20,
    );
    writer.write_int(0);
    writer.write_int(3);
    writer.write_coord(&Coord { y: 4, x: 5 });
    writer.write_int(7);
    writer.write_window(&["@.%".to_string(), "  #".to_string()]);
    writer.data
}

fn encwrite_known_bytes() -> Vec<u8> {
    source_encwrite(b"abcdef\0")
}

fn save_file_envelope_projection() -> Vec<u8> {
    source_save_file_envelope(&primitive_block(), 24, 80)
}

fn write_save_header_projection(writer: &mut StateWriter, version: &str, lines: i32, cols: i32) {
    writer.data.extend_from_slice(version.as_bytes());
    writer.data.push(0);
    let geometry = format!("{lines} x {cols}\n");
    writer.data.extend_from_slice(geometry.as_bytes());
    writer
        .data
        .extend(std::iter::repeat(0).take(80 - geometry.len()));
}

fn source_save_file_envelope(body: &[u8], lines: i32, cols: i32) -> Vec<u8> {
    let geometry = format!("{lines} x {cols}\n");
    let mut geometry_bytes = geometry.into_bytes();
    geometry_bytes.extend(std::iter::repeat(0).take(80 - geometry_bytes.len()));
    let mut output = Vec::new();
    let mut version = SOURCE_SAVE_VERSION.as_bytes().to_vec();
    version.push(0);
    output.extend(source_encwrite(&version));
    output.extend(source_encwrite(&geometry_bytes));
    output.extend(source_encwrite(body));
    output
}

fn source_encwrite(data: &[u8]) -> Vec<u8> {
    let mut e1 = 0usize;
    let mut e2 = 0usize;
    let mut fb = 0u8;
    let mut output = Vec::with_capacity(data.len());
    for value in data {
        output.push(value ^ SOURCE_ENCSTR[e1] ^ SOURCE_STATLIST[e2] ^ fb);
        fb = fb.wrapping_add(SOURCE_ENCSTR[e1].wrapping_mul(SOURCE_STATLIST[e2]));
        e1 = (e1 + 1) % SOURCE_ENCSTR.len();
        e2 = (e2 + 1) % SOURCE_STATLIST.len();
    }
    output
}

fn write_source_save_prefix(writer: &mut StateWriter, values: &SourceSavePrefix) {
    writer.write_boolean(values.after);
    writer.write_boolean(values.again);
    writer.write_int(values.noscore);
    writer.write_boolean(values.seenstairs);
    writer.write_boolean(values.amulet);
    writer.write_boolean(values.door_stop);
    writer.write_boolean(values.fight_flush);
    writer.write_boolean(values.firstmove);
    writer.write_boolean(values.got_ltc);
    writer.write_boolean(values.has_hit);
    writer.write_boolean(values.in_shell);
    writer.write_boolean(values.inv_describe);
    writer.write_boolean(values.jump);
    writer.write_boolean(values.kamikaze);
    writer.write_boolean(values.lower_msg);
    writer.write_boolean(values.move_on);
    writer.write_boolean(values.msg_esc);
    writer.write_boolean(values.passgo);
    writer.write_boolean(values.playing);
    writer.write_boolean(values.q_comm);
    writer.write_boolean(values.running);
    writer.write_boolean(values.save_msg);
    writer.write_boolean(values.see_floor);
    writer.write_boolean(values.stat_msg);
    writer.write_boolean(values.terse);
    writer.write_boolean(values.to_death);
    writer.write_boolean(values.tombstone);
    writer.write_int(values.wizard);
    let mut pack_used = values.pack_used.clone();
    pack_used.resize(26, false);
    pack_used.truncate(26);
    writer.write_booleans(&pack_used);
}

fn runtime_source_save_prefix_values(private: &PrivateState) -> SourceSavePrefix {
    SourceSavePrefix {
        after: private.command_after,
        again: false,
        noscore: 0,
        seenstairs: false,
        amulet: private.has_amulet,
        door_stop: false,
        fight_flush: false,
        firstmove: false,
        got_ltc: false,
        has_hit: false,
        in_shell: false,
        inv_describe: true,
        jump: false,
        kamikaze: private.kamikaze,
        lower_msg: false,
        move_on: false,
        msg_esc: false,
        passgo: false,
        playing: !private.terminated,
        q_comm: false,
        running: private.command_running,
        save_msg: true,
        see_floor: true,
        stat_msg: false,
        terse: false,
        to_death: private.command_to_death,
        tombstone: true,
        wizard: 0,
        pack_used: runtime_pack_used(&private.source_inventory),
    }
}

fn runtime_pack_used(inventory: &[Value]) -> Vec<bool> {
    let mut used = vec![false; 26];
    for item in inventory {
        let Some(packch) = item
            .get("packch")
            .and_then(Value::as_str)
            .and_then(|value| value.chars().next())
        else {
            continue;
        };
        if packch.is_ascii_lowercase() {
            let index = packch as usize - 'a' as usize;
            if index < used.len() {
                used[index] = true;
            }
        }
    }
    used
}

fn runtime_source_save_identity_text_values(
    resolved: &ResolvedTask,
    private: &PrivateState,
    file_name: &str,
) -> SourceSaveIdentityText {
    let tables = source_identity_tables(resolved.seed as i32);
    SourceSaveIdentityText {
        dir_ch: first_char(&private.command_direction),
        file_name: file_name.to_string(),
        huh: String::new(),
        potions: tables.0,
        prbuf: String::new(),
        rings: tables.2,
        release: "5.4.4".to_string(),
        runch: first_char(&private.command_runch),
        scrolls: tables.1,
        take: '\0',
        whoami: "rogue".to_string(),
        sticks: tables.3,
        orig_dsusp: 0,
        fruit: "slime-mold".to_string(),
        home: String::new(),
        inv_t_name: SOURCE_INV_T_NAME
            .iter()
            .map(|value| value.to_string())
            .collect(),
        l_last_comm: '\0',
        l_last_dir: '\0',
        last_comm: first_char(&private.command_last),
        last_dir: first_char(&private.command_direction),
        tr_name: SOURCE_TRAP_NAMES
            .iter()
            .map(|value| value.to_string())
            .collect(),
    }
}

fn runtime_source_save_scalar_values(
    resolved: &ResolvedTask,
    public: &PublicState,
    private: &PrivateState,
) -> SourceSaveScalars {
    SourceSaveScalars {
        n_objs: 0,
        ntraps: private.source_traps.len() as i32,
        hungry_state: private.hungry_state,
        inpack: private.source_inventory.len() as i32,
        inv_type: 0,
        level: private.dungeon_level as i32,
        max_level: private.max_level as i32,
        mpos: 0,
        no_food: 0,
        a_class: SOURCE_A_CLASS.to_vec(),
        count: private.command_count,
        food_left: private.food_left,
        lastscore: -1,
        no_command: private.no_command,
        no_move: private.no_move,
        purse: private.purse as i32,
        quiet: private.quiet,
        vf_hit: private.vf_hit,
        dnum: 0,
        seed: if private.rng_seed != 0 {
            private.rng_seed
        } else {
            resolved.seed as i32
        },
        e_levels: SOURCE_E_LEVELS.to_vec(),
        delta: Coord { y: 0, x: 0 },
        oldpos: Coord {
            y: public.hero.0 as i32,
            x: public.hero.1 as i32,
        },
        stairs: find_terrain_coord(public, '%'),
    }
}

fn write_source_save_info_state(writer: &mut StateWriter, private: &PrivateState) {
    write_source_save_info_state_known(
        writer,
        &private.pot_known,
        &private.ring_known,
        &private.scr_known,
        &private.ws_known,
    );
}

fn write_source_save_info_state_known(
    writer: &mut StateWriter,
    pot_known: &[bool],
    ring_known: &[bool],
    scr_known: &[bool],
    ws_known: &[bool],
) {
    writer.write_monsters(&source_monster_info());
    writer.write_obj_info(&source_obj_info(SOURCE_THINGS_INFO, NUMTHINGS, None, None));
    writer.write_obj_info(&source_obj_info(SOURCE_ARM_INFO, MAXARMORS, None, None));
    writer.write_obj_info(&source_obj_info(
        SOURCE_POT_INFO,
        MAXPOTIONS,
        Some(&known_list(pot_known, MAXPOTIONS)),
        None,
    ));
    writer.write_obj_info(&source_obj_info(
        SOURCE_RING_INFO,
        MAXRINGS,
        Some(&known_list(ring_known, MAXRINGS)),
        None,
    ));
    writer.write_obj_info(&source_obj_info(
        SOURCE_SCR_INFO,
        MAXSCROLLS,
        Some(&known_list(scr_known, MAXSCROLLS)),
        None,
    ));
    writer.write_obj_info(&source_obj_info(
        SOURCE_WEAP_INFO,
        MAXWEAPONS + 1,
        None,
        None,
    ));
    writer.write_obj_info(&source_obj_info(
        SOURCE_WS_INFO,
        MAXSTICKS,
        Some(&known_list(ws_known, MAXSTICKS)),
        None,
    ));
}

fn source_monster_info() -> Vec<SourceMonsterInfo> {
    SOURCE_MONSTER_STATS
        .iter()
        .map(
            |(strength, exp, level, armor, hp, damage, max_hp)| SourceMonsterInfo {
                stats: SourceStats {
                    strength: *strength,
                    exp: *exp,
                    level: *level,
                    armor: *armor,
                    hp: *hp,
                    damage: (*damage).to_string(),
                    max_hp: *max_hp,
                },
            },
        )
        .collect()
}

fn source_obj_info(
    rows: &[(Option<&str>, i32, i32)],
    count: usize,
    known: Option<&[bool]>,
    guesses: Option<&[Option<String>]>,
) -> Vec<SourceObjInfo> {
    let mut output = Vec::new();
    for index in 0..count {
        let (_name, prob, worth) = rows.get(index).copied().unwrap_or((None, 0, 0));
        output.push(SourceObjInfo {
            prob,
            worth,
            guess: guesses
                .and_then(|values| values.get(index))
                .cloned()
                .flatten(),
            know: known
                .and_then(|values| values.get(index))
                .copied()
                .unwrap_or(false),
        });
    }
    output
}

fn known_list(values: &[bool], count: usize) -> Vec<bool> {
    let mut output = values.to_vec();
    output.resize(count, false);
    output.truncate(count);
    output
}

fn runtime_source_daemons(private: &PrivateState) -> Vec<SourceDaemon> {
    private
        .source_daemon_actions
        .iter()
        .take(20)
        .map(|action| SourceDaemon {
            d_type: state_value_i32(action, "type", 0),
            func: source_daemon_func(action.get("action").and_then(Value::as_str).unwrap_or("")),
            arg: state_value_i32(action, "arg", 0),
            time: state_value_i32(action, "time", 0),
        })
        .collect()
}

fn source_daemon_func(action: &str) -> i32 {
    match action {
        "" => 0,
        "rollwand" => 1,
        "doctor" => 2,
        "stomach" => 3,
        "runners" => 4,
        "swander" => 5,
        "nohaste" => 6,
        "unconfuse" => 7,
        "unsee" => 8,
        "sight" => 9,
        _ => -1,
    }
}

fn runtime_source_nh(_private: &PrivateState) -> Coord {
    Coord { y: 0, x: 0 }
}

fn runtime_source_window_rows(public: &PublicState) -> Vec<String> {
    let width = public
        .terrain
        .iter()
        .map(|row| row.chars().count())
        .max()
        .unwrap_or(0);
    public
        .terrain
        .iter()
        .map(|row| {
            let mut chars: Vec<char> = row.chars().collect();
            chars.resize(width, ' ');
            chars.truncate(width);
            chars.into_iter().collect::<String>()
        })
        .collect()
}

fn source_identity_tables(
    seed: i32,
) -> (Vec<i32>, Vec<String>, Vec<i32>, Vec<SourceStickIdentity>) {
    let mut rng = RogueRng::new(seed);
    let potions = source_init_colors(&mut rng);
    let scrolls = source_init_scroll_names(&mut rng);
    let rings = source_init_stones(&mut rng);
    let sticks = source_init_materials(&mut rng);
    (potions, scrolls, rings, sticks)
}

fn source_init_colors(rng: &mut RogueRng) -> Vec<i32> {
    let mut used = vec![false; SOURCE_RAINBOW.len()];
    let mut colors = Vec::new();
    for _index in 0..MAXPOTIONS {
        loop {
            let candidate = rng.rnd(SOURCE_RAINBOW.len() as i32) as usize;
            if !used[candidate] {
                used[candidate] = true;
                colors.push(candidate as i32);
                break;
            }
        }
    }
    colors
}

fn source_init_scroll_names(rng: &mut RogueRng) -> Vec<String> {
    let mut names = Vec::new();
    for _index in 0..MAXSCROLLS {
        let mut buffer = String::new();
        let words = rng.rnd(3) + 2;
        for _word in 0..words {
            let syllables = rng.rnd(3) + 1;
            for _syllable in 0..syllables {
                let syllable = SOURCE_SYLLS[rng.rnd(SOURCE_SYLLS.len() as i32) as usize];
                if buffer.len() + syllable.len() > MAXNAME {
                    break;
                }
                buffer.push_str(syllable);
            }
            buffer.push(' ');
        }
        if buffer.ends_with(' ') {
            buffer.pop();
        }
        names.push(buffer);
    }
    names
}

fn source_init_stones(rng: &mut RogueRng) -> Vec<i32> {
    let mut used = vec![false; SOURCE_STONES.len()];
    let mut stones = Vec::new();
    for _index in 0..MAXRINGS {
        loop {
            let candidate = rng.rnd(SOURCE_STONES.len() as i32) as usize;
            if !used[candidate] {
                used[candidate] = true;
                stones.push(candidate as i32);
                break;
            }
        }
    }
    stones
}

fn source_init_materials(rng: &mut RogueRng) -> Vec<SourceStickIdentity> {
    let mut wood_used = vec![false; SOURCE_WOOD.len()];
    let mut metal_used = vec![false; SOURCE_METAL.len()];
    let mut sticks = Vec::new();
    for _index in 0..MAXSTICKS {
        loop {
            if rng.rnd(2) == 0 {
                let material = rng.rnd(SOURCE_METAL.len() as i32) as usize;
                if !metal_used[material] {
                    metal_used[material] = true;
                    sticks.push(SourceStickIdentity {
                        is_staff: false,
                        material_index: material as i32,
                    });
                    break;
                }
            } else {
                let material = rng.rnd(SOURCE_WOOD.len() as i32) as usize;
                if !wood_used[material] {
                    wood_used[material] = true;
                    sticks.push(SourceStickIdentity {
                        is_staff: true,
                        material_index: material as i32,
                    });
                    break;
                }
            }
        }
    }
    sticks
}

fn int_list(values: &[i32], count: usize) -> Vec<i32> {
    let mut output = values.to_vec();
    output.resize(count, -1);
    output.truncate(count);
    output
}

fn string_list(values: &[String], count: usize) -> Vec<String> {
    let mut output = values.to_vec();
    output.resize(count, String::new());
    output.truncate(count);
    output
}

fn stick_list(values: &[SourceStickIdentity], count: usize) -> Vec<SourceStickIdentity> {
    let mut output = values.to_vec();
    output.resize(
        count,
        SourceStickIdentity {
            is_staff: false,
            material_index: -1,
        },
    );
    output.truncate(count);
    output
}

fn find_terrain_coord(public: &PublicState, target: char) -> Coord {
    for (row_index, row) in public.terrain.iter().enumerate() {
        if let Some(col_index) = row.chars().position(|ch| ch == target) {
            return Coord {
                y: row_index as i32,
                x: col_index as i32,
            };
        }
    }
    Coord { y: 0, x: 0 }
}

fn source_save_prefix_field_names() -> Vec<&'static str> {
    vec![
        "after",
        "again",
        "noscore",
        "seenstairs",
        "amulet",
        "door_stop",
        "fight_flush",
        "firstmove",
        "got_ltc",
        "has_hit",
        "in_shell",
        "inv_describe",
        "jump",
        "kamikaze",
        "lower_msg",
        "move_on",
        "msg_esc",
        "passgo",
        "playing",
        "q_comm",
        "running",
        "save_msg",
        "see_floor",
        "stat_msg",
        "terse",
        "to_death",
        "tombstone",
        "wizard",
        "pack_used",
    ]
}

fn runtime_source_inventory_objects(
    public: &PublicState,
    private: &PrivateState,
) -> Vec<SourceObject> {
    let default_pos = Coord {
        y: public.hero.0 as i32,
        x: public.hero.1 as i32,
    };
    private
        .source_inventory
        .iter()
        .enumerate()
        .map(|(index, item)| runtime_source_object_from_inventory(item, index, &default_pos))
        .collect()
}

fn runtime_source_level_objects(public: &PublicState, private: &PrivateState) -> Vec<SourceObject> {
    let mut objects = Vec::new();
    let mut used_keys = std::collections::BTreeSet::new();
    for item in &private.source_level_objects {
        let pos = state_value_pos(item, &Coord { y: 0, x: 0 });
        used_keys.insert(format!("{},{}", pos.y, pos.x));
        let index = objects.len();
        objects.push(runtime_source_object_from_level_item(item, index, private));
    }
    for (key, obj_type) in &public.visible_items {
        if used_keys.contains(key) {
            continue;
        }
        let pos = parse_visible_item_key(key);
        let index = objects.len();
        let arm = if obj_type.chars().next().unwrap_or('?') == '*' {
            *private.item_values.get(key).unwrap_or(&0) as i32
        } else {
            0
        };
        let item = json!({
            "id": key,
            "type": obj_type,
            "pos": {"y": pos.y, "x": pos.x},
            "arm": arm,
            "packch": char::from_u32('a' as u32 + (index % 26) as u32).unwrap_or('a').to_string(),
        });
        objects.push(runtime_source_object_from_level_item(&item, index, private));
    }
    objects
}

fn runtime_source_object_from_inventory(
    item: &Value,
    index: usize,
    default_pos: &Coord,
) -> SourceObject {
    let obj_type = state_value_char(item, "type", state_value_char(item, "obj_type", '?'));
    let default_packch = char::from_u32('a' as u32 + (index % 26) as u32).unwrap_or('a');
    SourceObject {
        object_id: state_value_str(
            item,
            "id",
            &state_value_str(item, "obj_id", &format!("pack{index}")),
        ),
        obj_type,
        pos: state_value_pos(item, default_pos),
        launch: state_value_i32(item, "launch", -1),
        packch: state_value_char(item, "packch", default_packch),
        damage: state_value_str(item, "damage", ""),
        hurldmg: state_value_str(item, "hurldmg", &state_value_str(item, "hurl_damage", "")),
        count: state_value_i32(item, "count", 1),
        which: state_value_i32(item, "which", 0),
        hplus: state_value_i32(item, "hplus", 0),
        dplus: state_value_i32(item, "dplus", 0),
        arm: state_value_i32(
            item,
            "arm",
            if obj_type == '/' {
                state_value_i32(item, "charges", 0)
            } else {
                0
            },
        ),
        flags: state_value_i32(item, "flags", 0),
        group: state_value_i32(item, "group", 0),
        label: state_value_optional_str(item, "label"),
    }
}

fn runtime_source_object_from_level_item(
    item: &Value,
    index: usize,
    private: &PrivateState,
) -> SourceObject {
    let obj_type = state_value_char(item, "type", state_value_char(item, "obj_type", '?'));
    let pos = state_value_pos(item, &Coord { y: 0, x: 0 });
    let key = format!("{},{}", pos.y, pos.x);
    let default_packch = char::from_u32('a' as u32 + (index % 26) as u32).unwrap_or('a');
    let arm = if obj_type == '*' {
        state_value_i32(
            item,
            "goldval",
            state_value_i32(
                item,
                "arm",
                *private.item_values.get(&key).unwrap_or(&0) as i32,
            ),
        )
    } else if obj_type == '/' {
        state_value_i32(item, "arm", state_value_i32(item, "charges", 0))
    } else {
        state_value_i32(item, "arm", 0)
    };
    SourceObject {
        object_id: state_value_str(
            item,
            "id",
            &state_value_str(item, "obj_id", &format!("level_object{index}")),
        ),
        obj_type,
        pos,
        launch: state_value_i32(item, "launch", -1),
        packch: state_value_char(item, "packch", default_packch),
        damage: state_value_str(item, "damage", ""),
        hurldmg: state_value_str(item, "hurldmg", &state_value_str(item, "hurl_damage", "")),
        count: state_value_i32(item, "count", 1),
        which: state_value_i32(item, "which", 0),
        hplus: state_value_i32(item, "hplus", 0),
        dplus: state_value_i32(item, "dplus", 0),
        arm,
        flags: state_value_i32(item, "flags", 0),
        group: state_value_i32(item, "group", 0),
        label: state_value_optional_str(item, "label"),
    }
}

fn runtime_source_player_thing(
    public: &PublicState,
    private: &PrivateState,
    pack: &[SourceObject],
) -> SourceThing {
    let pos = Coord {
        y: public.hero.0 as i32,
        x: public.hero.1 as i32,
    };
    SourceThing {
        pos: pos.clone(),
        turn: false,
        thing_type: '@',
        disguise: '@',
        oldch: terrain_char(public, &pos, '.'),
        dest_kind: "null".to_string(),
        dest_index: 0,
        flags: private.player_flags,
        stats: SourceStats {
            strength: source_strength_value(private.strength, private.max_strength),
            exp: private.player_exp,
            level: private.player_level,
            armor: private.player_armor,
            hp: private.hp as i32,
            damage: runtime_player_damage(private),
            max_hp: private.max_hp as i32,
        },
        room_index: 0,
        pack: pack.to_vec(),
    }
}

fn state_value_pos(item: &Value, default: &Coord) -> Coord {
    let pos = item.get("pos").unwrap_or(&Value::Null);
    Coord {
        y: state_value_i32(
            item,
            "row",
            state_value_i32(item, "y", state_nested_i32(pos, "y", default.y)),
        ),
        x: state_value_i32(
            item,
            "col",
            state_value_i32(item, "x", state_nested_i32(pos, "x", default.x)),
        ),
    }
}

fn runtime_player_damage(private: &PrivateState) -> String {
    for item in &private.source_inventory {
        if state_value_str(item, "id", "") == private.current_weapon_id.as_str() {
            return state_value_str(item, "damage", &private.player_damage);
        }
    }
    private.player_damage.clone()
}

fn runtime_source_monsters(
    private: &PrivateState,
    level_objects: &[SourceObject],
) -> Vec<SourceThing> {
    private
        .source_monsters
        .iter()
        .enumerate()
        .filter(|(_, monster)| state_value_i32(monster, "hp", 0) > 0)
        .map(|(_index, monster)| {
            let pos = Coord {
                y: state_value_i32(monster, "row", state_value_i32(monster, "y", 0)),
                x: state_value_i32(monster, "col", state_value_i32(monster, "x", 0)),
            };
            let pack = monster
                .get("pack")
                .and_then(Value::as_array)
                .map(|items| {
                    items
                        .iter()
                        .enumerate()
                        .map(|(pack_index, item)| {
                            runtime_source_object_from_inventory(item, pack_index, &pos)
                        })
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default();
            let monster_type = state_value_char(
                monster,
                "type",
                state_value_char(monster, "monster_type", 'K'),
            );
            let strength = state_value_i32(monster, "strength", 16);
            SourceThing {
                pos,
                turn: state_value_bool(monster, "turn", true),
                thing_type: monster_type,
                disguise: state_value_char(monster, "disguise", monster_type),
                oldch: state_value_char(monster, "oldch", '.'),
                dest_kind: state_value_str(
                    monster,
                    "dest_kind",
                    &state_value_str(monster, "dest", "hero"),
                ),
                dest_index: runtime_monster_dest_index(monster, level_objects),
                flags: state_value_i32(monster, "flags", 0),
                stats: SourceStats {
                    strength: source_strength_value(
                        strength,
                        state_value_i32(monster, "max_strength", strength),
                    ),
                    exp: state_value_i32(monster, "exp", 1),
                    level: state_value_i32(monster, "level", 1),
                    armor: state_value_i32(monster, "arm", 6),
                    hp: state_value_i32(monster, "hp", 1),
                    damage: state_value_str(monster, "damage", "1x1"),
                    max_hp: state_value_i32(monster, "max_hp", state_value_i32(monster, "hp", 1)),
                },
                room_index: state_value_i32(monster, "room", 0),
                pack,
            }
        })
        .collect()
}

fn runtime_monster_dest_index(monster: &Value, level_objects: &[SourceObject]) -> i32 {
    let dest_kind = state_value_str(
        monster,
        "dest_kind",
        &state_value_str(monster, "dest", "hero"),
    );
    if dest_kind == "object" {
        if let Some(object_id) = state_value_optional_str(monster, "dest_object_id")
            .or_else(|| state_value_optional_str(monster, "dest_id"))
        {
            for (index, obj) in level_objects.iter().enumerate() {
                if obj.object_id == object_id {
                    return index as i32;
                }
            }
        }
        let dest_row = monster.get("dest_row").and_then(Value::as_i64);
        let dest_col = monster.get("dest_col").and_then(Value::as_i64);
        if let (Some(row), Some(col)) = (dest_row, dest_col) {
            for (index, obj) in level_objects.iter().enumerate() {
                if obj.pos.y == row as i32 && obj.pos.x == col as i32 {
                    return index as i32;
                }
            }
        }
        return state_value_i32(monster, "dest_index", -1);
    }
    if dest_kind == "monster" {
        return state_value_i32(
            monster,
            "dest_index",
            state_value_i32(monster, "dest_monster_index", -1),
        );
    }
    if dest_kind == "room_gold" {
        return state_value_i32(monster, "dest_room", state_value_i32(monster, "room", -1));
    }
    0
}

fn runtime_source_places(
    public: &PublicState,
    private: &PrivateState,
    monsters: &[SourceThing],
) -> Vec<SourcePlace> {
    let trap_flags = private
        .source_traps
        .iter()
        .filter_map(|trap| {
            Some((
                (
                    state_value_i32(trap, "row", 0),
                    state_value_i32(trap, "col", 0),
                ),
                state_value_i32(trap, "flags", 0x10),
            ))
        })
        .collect::<Vec<_>>();
    let cell_flags = private
        .source_map_cells
        .iter()
        .filter_map(|cell| {
            Some((
                (
                    state_value_i32(cell, "row", 0),
                    state_value_i32(cell, "col", 0),
                ),
                state_value_i32(cell, "flags", 0x10),
            ))
        })
        .collect::<Vec<_>>();
    let monster_indices = monsters
        .iter()
        .enumerate()
        .map(|(index, monster)| ((monster.pos.y, monster.pos.x), index as i32))
        .collect::<Vec<_>>();
    let mut places = Vec::new();
    for col_index in 0..MAXCOLS {
        for row_index in 0..MAXLINES {
            let ch = public
                .terrain
                .get(row_index)
                .and_then(|row| row.chars().nth(col_index))
                .unwrap_or(' ');
            let flags = trap_flags
                .iter()
                .find(|((row, col), _)| *row == row_index as i32 && *col == col_index as i32)
                .map(|(_, flags)| *flags)
                .or_else(|| {
                    cell_flags
                        .iter()
                        .find(|((row, col), _)| {
                            *row == row_index as i32 && *col == col_index as i32
                        })
                        .map(|(_, flags)| *flags)
                })
                .unwrap_or(0x10);
            let monster_index = monster_indices
                .iter()
                .find(|((row, col), _)| *row == row_index as i32 && *col == col_index as i32)
                .map(|(_, index)| *index)
                .unwrap_or(-1);
            places.push(SourcePlace {
                ch,
                flags,
                monster_index,
            });
        }
    }
    places
}

fn runtime_source_max_stats(private: &PrivateState) -> SourceStats {
    SourceStats {
        strength: source_strength_value(private.max_strength, private.max_strength),
        exp: private.player_exp,
        level: private.player_level,
        armor: private.player_armor,
        hp: private.max_hp as i32,
        damage: private.player_damage.clone(),
        max_hp: private.max_hp as i32,
    }
}

fn runtime_source_rooms(private: &PrivateState) -> Vec<SourceRoom> {
    runtime_room_list(&private.source_rooms, MAXROOMS as usize, default_room(0))
}

fn runtime_source_passages(private: &PrivateState) -> Vec<SourceRoom> {
    runtime_room_list(
        &private.source_passages,
        MAXPASS,
        default_room(SOURCE_ROOM_ISGONE | SOURCE_ROOM_ISDARK),
    )
}

fn runtime_room_list(values: &[Value], count: usize, default: SourceRoom) -> Vec<SourceRoom> {
    let mut rooms = values
        .iter()
        .take(count)
        .map(source_room_from_value)
        .collect::<Vec<_>>();
    while rooms.len() < count {
        rooms.push(default.clone());
    }
    rooms.truncate(count);
    rooms
}

fn source_room_from_value(raw: &Value) -> SourceRoom {
    let exits = raw
        .get("exits")
        .and_then(Value::as_array)
        .map(|items| items.iter().map(coord_from_value).collect::<Vec<_>>())
        .unwrap_or_default();
    SourceRoom {
        pos: coord_field(
            raw,
            "pos",
            Coord {
                y: state_value_i32(raw, "row", 0),
                x: state_value_i32(raw, "col", 0),
            },
        ),
        max: coord_field(
            raw,
            "max",
            Coord {
                y: state_value_i32(raw, "height", 0),
                x: state_value_i32(raw, "width", 0),
            },
        ),
        gold: coord_field(
            raw,
            "gold",
            Coord {
                y: state_value_i32(raw, "gold_y", 0),
                x: state_value_i32(raw, "gold_x", 0),
            },
        ),
        goldval: state_value_i32(raw, "goldval", 0),
        flags: state_value_i32(raw, "flags", 0),
        exits,
    }
}

fn default_room(flags: i32) -> SourceRoom {
    SourceRoom {
        pos: Coord { y: 0, x: 0 },
        max: Coord { y: 0, x: 0 },
        gold: Coord { y: 0, x: 0 },
        goldval: 0,
        flags,
        exits: Vec::new(),
    }
}

fn runtime_old_room_index(public: &PublicState, private: &PrivateState) -> i32 {
    let hero = Coord {
        y: public.hero.0 as i32,
        x: public.hero.1 as i32,
    };
    for (index, room) in runtime_source_rooms(private).iter().enumerate() {
        if room.flags & SOURCE_ROOM_ISGONE != 0 {
            continue;
        }
        if hero.y >= room.pos.y
            && hero.y < room.pos.y + room.max.y
            && hero.x >= room.pos.x
            && hero.x < room.pos.x + room.max.x
        {
            return index as i32;
        }
    }
    -1
}

fn source_strength_value(strength: i32, max_strength: i32) -> u32 {
    (((strength & 0xff) as u32) << 8) | ((max_strength & 0xff) as u32)
}

fn ref_id(value: &str) -> Option<&str> {
    if value.is_empty() {
        None
    } else {
        Some(value)
    }
}

fn terrain_char(public: &PublicState, coord: &Coord, default: char) -> char {
    if coord.y >= 0 && coord.x >= 0 {
        if let Some(row) = public.terrain.get(coord.y as usize) {
            return row.chars().nth(coord.x as usize).unwrap_or(default);
        }
    }
    default
}

fn state_value_str(item: &Value, key: &str, default: &str) -> String {
    item.get(key)
        .and_then(Value::as_str)
        .unwrap_or(default)
        .to_string()
}

fn state_value_optional_str(item: &Value, key: &str) -> Option<String> {
    item.get(key)
        .and_then(Value::as_str)
        .map(std::string::ToString::to_string)
}

fn state_value_char(item: &Value, key: &str, default: char) -> char {
    item.get(key)
        .and_then(Value::as_str)
        .and_then(|text| text.chars().next())
        .unwrap_or(default)
}

fn state_value_i32(item: &Value, key: &str, default: i32) -> i32 {
    item.get(key)
        .and_then(Value::as_i64)
        .map(|value| value as i32)
        .unwrap_or(default)
}

fn state_value_bool(item: &Value, key: &str, default: bool) -> bool {
    item.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn state_nested_i32(item: &Value, key: &str, default: i32) -> i32 {
    item.get(key)
        .and_then(Value::as_i64)
        .map(|value| value as i32)
        .unwrap_or(default)
}

fn coord_field(item: &Value, key: &str, default: Coord) -> Coord {
    item.get(key).map(coord_from_value).unwrap_or(default)
}

fn coord_from_value(value: &Value) -> Coord {
    if let Some(object) = value.as_object() {
        return Coord {
            y: object
                .get("y")
                .or_else(|| object.get("row"))
                .and_then(Value::as_i64)
                .unwrap_or(0) as i32,
            x: object
                .get("x")
                .or_else(|| object.get("col"))
                .and_then(Value::as_i64)
                .unwrap_or(0) as i32,
        };
    }
    if let Some(items) = value.as_array() {
        return Coord {
            y: items.first().and_then(Value::as_i64).unwrap_or(0) as i32,
            x: items.get(1).and_then(Value::as_i64).unwrap_or(0) as i32,
        };
    }
    Coord { y: 0, x: 0 }
}

fn parse_visible_item_key(key: &str) -> Coord {
    let parts = key
        .split(',')
        .map(|part| part.parse::<i32>().unwrap_or(0))
        .collect::<Vec<_>>();
    Coord {
        y: *parts.first().unwrap_or(&0),
        x: *parts.get(1).unwrap_or(&0),
    }
}

fn runtime_objects(public: &PublicState, private: &PrivateState) -> Vec<SourceObject> {
    let mut objects = Vec::new();
    for (index, (key, item)) in public.visible_items.iter().enumerate() {
        let parts = key
            .split(',')
            .map(|part| part.parse::<i32>().unwrap())
            .collect::<Vec<_>>();
        let obj_type = item.chars().next().unwrap_or(' ');
        let arm = if obj_type == GOLD {
            *private.item_values.get(key).unwrap_or(&0) as i32
        } else {
            0
        };
        objects.push(SourceObject {
            object_id: key.clone(),
            obj_type,
            pos: Coord {
                y: parts[0],
                x: parts[1],
            },
            launch: -1,
            packch: (b'a' + (index % 26) as u8) as char,
            damage: String::new(),
            hurldmg: String::new(),
            count: 1,
            which: 0,
            hplus: 0,
            dplus: 0,
            arm,
            flags: 0,
            group: 0,
            label: None,
        });
    }
    objects
}

fn runtime_places(
    terrain: &[String],
    width: usize,
    traps: &[Value],
    map_cells: &[Value],
) -> Vec<SourcePlace> {
    let trap_flags: Vec<((usize, usize), i32)> = traps
        .iter()
        .filter_map(|trap| {
            Some((
                (
                    trap.get("row")?.as_i64()? as usize,
                    trap.get("col")?.as_i64()? as usize,
                ),
                trap.get("flags").and_then(Value::as_i64).unwrap_or(0x10) as i32,
            ))
        })
        .collect();
    let cell_flags: Vec<((usize, usize), i32)> = map_cells
        .iter()
        .filter_map(|cell| {
            Some((
                (
                    cell.get("row")?.as_i64()? as usize,
                    cell.get("col")?.as_i64()? as usize,
                ),
                cell.get("flags").and_then(Value::as_i64).unwrap_or(0x10) as i32,
            ))
        })
        .collect();
    let mut places = Vec::new();
    for (row_index, row) in terrain.iter().enumerate() {
        let mut chars = row.chars().collect::<Vec<_>>();
        chars.resize(width, ' ');
        for (col_index, ch) in chars.into_iter().enumerate() {
            let flags = trap_flags
                .iter()
                .find(|((trap_row, trap_col), _)| *trap_row == row_index && *trap_col == col_index)
                .map(|(_, flags)| *flags)
                .or_else(|| {
                    cell_flags
                        .iter()
                        .find(|((cell_row, cell_col), _)| {
                            *cell_row == row_index && *cell_col == col_index
                        })
                        .map(|(_, flags)| *flags)
                })
                .unwrap_or(0x10);
            places.push(SourcePlace {
                ch,
                flags,
                monster_index: -1,
            });
        }
    }
    places
}

fn first_char(value: &str) -> char {
    value.chars().next().unwrap_or('\0')
}

fn objects() -> Vec<SourceObject> {
    vec![
        SourceObject {
            object_id: "weapon".to_string(),
            obj_type: ')',
            pos: Coord { y: 4, x: 5 },
            launch: 2,
            packch: 'a',
            damage: "1d8".to_string(),
            hurldmg: "1d6".to_string(),
            count: 1,
            which: 1,
            hplus: 2,
            dplus: -1,
            arm: 0,
            flags: 0o000006,
            group: 3,
            label: Some("etched".to_string()),
        },
        SourceObject {
            object_id: "food".to_string(),
            obj_type: ':',
            pos: Coord { y: 8, x: 9 },
            launch: -1,
            packch: 'b',
            damage: String::new(),
            hurldmg: String::new(),
            count: 2,
            which: 0,
            hplus: 0,
            dplus: 0,
            arm: 0,
            flags: 0,
            group: 0,
            label: None,
        },
    ]
}

fn rooms() -> Vec<SourceRoom> {
    vec![
        SourceRoom {
            pos: Coord { y: 2, x: 4 },
            max: Coord { y: 6, x: 10 },
            gold: Coord { y: 5, x: 9 },
            goldval: 73,
            flags: 0o000005,
            exits: vec![Coord { y: 2, x: 7 }, Coord { y: 6, x: 8 }],
        },
        SourceRoom {
            pos: Coord { y: 12, x: 20 },
            max: Coord { y: 4, x: 8 },
            gold: Coord { y: 0, x: 0 },
            goldval: 0,
            flags: 0,
            exits: Vec::new(),
        },
    ]
}

fn passages() -> Vec<SourceRoom> {
    vec![
        SourceRoom {
            pos: Coord { y: 0, x: 0 },
            max: Coord { y: 0, x: 0 },
            gold: Coord { y: 0, x: 0 },
            goldval: 0,
            flags: SOURCE_ROOM_ISGONE | SOURCE_ROOM_ISDARK,
            exits: vec![
                Coord { y: 3, x: 8 },
                Coord { y: 8, x: 3 },
                Coord { y: 8, x: 9 },
            ],
        },
        SourceRoom {
            pos: Coord { y: 0, x: 0 },
            max: Coord { y: 0, x: 0 },
            gold: Coord { y: 0, x: 0 },
            goldval: 0,
            flags: SOURCE_ROOM_ISGONE | SOURCE_ROOM_ISDARK,
            exits: Vec::new(),
        },
    ]
}

fn player(objects: &[SourceObject]) -> SourceThing {
    SourceThing {
        pos: Coord { y: 10, x: 11 },
        turn: false,
        thing_type: '@',
        disguise: '@',
        oldch: '.',
        dest_kind: "null".to_string(),
        dest_index: 0,
        flags: 0o020000,
        stats: SourceStats {
            strength: 0x1010,
            exp: 220,
            level: 5,
            armor: 3,
            hp: 31,
            damage: "1d4".to_string(),
            max_hp: 36,
        },
        room_index: 0,
        pack: objects.to_vec(),
    }
}

fn monsters(objects: &[SourceObject]) -> Vec<SourceThing> {
    vec![
        SourceThing {
            pos: Coord { y: 3, x: 30 },
            turn: true,
            thing_type: 'K',
            disguise: 'K',
            oldch: '.',
            dest_kind: "hero".to_string(),
            dest_index: 1,
            flags: 0o020040,
            stats: SourceStats {
                strength: 0x0909,
                exp: 12,
                level: 1,
                armor: 8,
                hp: 4,
                damage: "1d4".to_string(),
                max_hp: 4,
            },
            room_index: 1,
            pack: Vec::new(),
        },
        SourceThing {
            pos: Coord { y: 7, x: 35 },
            turn: false,
            thing_type: 'N',
            disguise: 'N',
            oldch: '.',
            dest_kind: "object".to_string(),
            dest_index: 0,
            flags: 0o020000,
            stats: SourceStats {
                strength: 0x0808,
                exp: 50,
                level: 3,
                armor: 9,
                hp: 12,
                damage: "0d0".to_string(),
                max_hp: 12,
            },
            room_index: 1,
            pack: vec![objects[1].clone()],
        },
        SourceThing {
            pos: Coord { y: 11, x: 40 },
            turn: false,
            thing_type: 'D',
            disguise: 'D',
            oldch: '.',
            dest_kind: "monster".to_string(),
            dest_index: 0,
            flags: 0o020000,
            stats: SourceStats {
                strength: 0x1515,
                exp: 5000,
                level: 10,
                armor: -1,
                hp: 80,
                damage: "1d8/1d8/3d10".to_string(),
                max_hp: 80,
            },
            room_index: 2,
            pack: Vec::new(),
        },
    ]
}

fn dest_pair(
    thing: &SourceThing,
    monsters: &[SourceThing],
    objects: &[SourceObject],
) -> (i32, i32) {
    match thing.dest_kind.as_str() {
        "hero" => (0, 1),
        "monster" => (
            1,
            if thing.dest_index >= 0 && (thing.dest_index as usize) < monsters.len() {
                thing.dest_index
            } else {
                -1
            },
        ),
        "object" => (
            2,
            if thing.dest_index >= 0 && (thing.dest_index as usize) < objects.len() {
                thing.dest_index
            } else {
                -1
            },
        ),
        "room_gold" => (
            3,
            if (0..MAXROOMS).contains(&thing.dest_index) {
                thing.dest_index
            } else {
                -1
            },
        ),
        _ => (0, 0),
    }
}

fn fixed_bytes(value: &str, count: usize) -> Vec<u8> {
    let raw = value.as_bytes();
    let mut out = Vec::new();
    out.extend_from_slice(&raw[..raw.len().min(count)]);
    out.extend(std::iter::repeat(0).take(count - out.len()));
    out
}

fn case_summary(name: &str, payload: &[u8]) -> Value {
    json!({
        "name": name,
        "len": payload.len(),
        "hex": hex(payload),
    })
}

fn hex(payload: &[u8]) -> String {
    let mut out = String::with_capacity(payload.len() * 2);
    for byte in payload {
        out.push_str(&format!("{byte:02x}"));
    }
    out
}

fn sha256_hex(payload: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(payload);
    format!("{:x}", hasher.finalize())
}
