use crate::{RogueRng, AMULET, ARMOR, FOOD, GOLD, POTION, RING, SCROLL, STAIRS, STICK, WEAPON};
use serde_json::{json, Value};

const AMULETLEVEL: i32 = 26;
const LAMPDIST: i32 = 3;
const VS_MAGIC: i32 = 3;
const S_SCARE: i32 = 10;

const CANSEE: i32 = 0o000002;
const ISBLIND: i32 = 0o000004;
const ISCANC: i32 = 0o000010;
const ISLEVIT: i32 = 0o000010;
const ISFOUND: i32 = 0o000020;
const ISGREED: i32 = 0o000040;
const ISHASTE: i32 = 0o000100;
const ISHELD: i32 = 0o000400;
const ISHUH: i32 = 0o001000;
const ISINVIS: i32 = 0o002000;
const ISMEAN: i32 = 0o004000;
const ISHALU: i32 = 0o004000;
const ISREGEN: i32 = 0o010000;
const ISRUN: i32 = 0o020000;
const ISFLY: i32 = 0o040000;

const R_PROTECT: i32 = 0;
const R_STEALTH: i32 = 12;
const R_AGGR: i32 = 6;

const LVL_MONS: [char; 26] = [
    'K', 'E', 'B', 'S', 'H', 'I', 'R', 'O', 'Z', 'L', 'C', 'Q', 'A', 'N', 'Y', 'F', 'T', 'W', 'P',
    'X', 'U', 'M', 'V', 'G', 'J', 'D',
];
const WAND_MONS: [char; 26] = [
    'K', 'E', 'B', 'S', 'H', '\0', 'R', 'O', 'Z', '\0', 'C', 'Q', 'A', '\0', 'Y', '\0', 'T', 'W',
    'P', '\0', 'U', 'M', 'V', 'G', 'J', '\0',
];
const RND_THING_LIST: [char; 10] = [
    POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS, GOLD, AMULET,
];

const MONSTER_CARRY: [i32; 26] = [
    0, 0, 15, 100, 0, 0, 20, 0, 0, 70, 0, 0, 40, 100, 15, 0, 0, 0, 0, 50, 0, 20, 0, 30, 30, 0,
];
const MONSTER_EXP: [i32; 26] = [
    20, 1, 17, 5000, 2, 80, 2000, 3, 5, 3000, 1, 10, 200, 37, 5, 120, 15, 9, 2, 120, 190, 350, 55,
    100, 50, 6,
];
const MONSTER_LEVELS: [i32; 26] = [
    5, 1, 4, 10, 1, 8, 13, 1, 1, 15, 1, 3, 8, 3, 1, 8, 3, 2, 1, 6, 7, 8, 5, 7, 4, 2,
];
const MONSTER_ARMOR: [i32; 26] = [
    2, 3, 4, -1, 7, 3, 2, 5, 9, 6, 7, 8, 2, 9, 6, 3, 3, 3, 5, 4, -2, 1, 4, 7, 6, 8,
];
const MONSTER_DAMAGE: [&str; 26] = [
    "0x0/0x0",
    "1x2",
    "1x2/1x5/1x5",
    "1x8/1x8/3x10",
    "1x2",
    "%%%x0",
    "4x3/3x5",
    "1x8",
    "0x0",
    "2x12/2x4",
    "1x4",
    "1x1",
    "3x4/3x4/2x5",
    "0x0",
    "1x8",
    "4x4",
    "1x5/1x5",
    "1x6",
    "1x3",
    "1x8/1x8/2x6",
    "1x9/1x9/2x9",
    "1x10",
    "1x6",
    "4x4",
    "1x6/1x6",
    "1x8",
];
const MONSTER_FLAGS: [i32; 26] = [
    ISMEAN,
    ISFLY,
    0,
    ISMEAN,
    ISMEAN,
    ISMEAN,
    ISMEAN | ISFLY | ISREGEN,
    ISMEAN,
    0,
    0,
    ISMEAN | ISFLY,
    0,
    ISMEAN,
    0,
    ISGREED,
    ISINVIS,
    ISMEAN,
    ISMEAN,
    ISMEAN,
    ISREGEN | ISMEAN,
    ISMEAN,
    ISREGEN | ISMEAN,
    0,
    0,
    0,
    ISMEAN,
];

#[derive(Clone, Copy)]
struct Coord {
    y: i32,
    x: i32,
}

#[derive(Clone)]
struct MonsterStats {
    strength: i32,
    exp: i32,
    level: i32,
    arm: i32,
    hp: i32,
    damage: &'static str,
    max_hp: i32,
}

#[derive(Clone)]
struct Monster {
    monster_type: char,
    disguise: char,
    pos: Coord,
    oldch: char,
    room: i32,
    dest: &'static str,
    dest_pos: Option<Coord>,
    flags: i32,
    turn: bool,
    stats: MonsterStats,
    pack_count: i32,
}

#[derive(Clone)]
struct SourceObject {
    obj_type: char,
    which: i32,
    pos: Coord,
    room: i32,
}

#[derive(Clone)]
struct SourceRing {
    which: i32,
    arm: i32,
}

struct MonsterWorld {
    rng: RogueRng,
    level: i32,
    max_level: i32,
    hero: Coord,
    proom: i32,
    proom_gold: Coord,
    proom_goldval: i32,
    room_dark: Vec<(i32, bool)>,
    player_flags: i32,
    left_ring: Option<SourceRing>,
    right_ring: Option<SourceRing>,
    objects: Vec<SourceObject>,
    claimed_dests: Vec<Coord>,
    markers: Vec<String>,
    trace: serde_json::Map<String, Value>,
}

pub fn source_monsters_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_monsters.v1",
        "randmonster": randmonster_cases(),
        "new_monster": new_monster_cases(),
        "runto_find_dest": runto_cases(),
        "wake_monster": wake_cases(),
    })
}

fn randmonster(rng: &mut RogueRng, level: i32, wander: bool) -> Value {
    let monsters = if wander { &WAND_MONS } else { &LVL_MONS };
    let mut attempts = Vec::new();
    loop {
        let raw = level + (rng.rnd(10) - 6);
        let mut index = raw;
        if index < 0 {
            index = rng.rnd(5);
        }
        if index > 25 {
            index = rng.rnd(5) + 21;
        }
        let monster = monsters[index as usize];
        attempts.push(json!({"raw": raw, "index": index, "monster": char_json(monster)}));
        if monster != '\0' {
            return json!({"level": level, "wander": wander, "monster": char_json(monster), "attempts": attempts, "rng_seed": rng.seed});
        }
    }
}

fn new_monster(
    world: &mut MonsterWorld,
    monster_type: char,
    pos: Coord,
    room: i32,
    oldch: char,
) -> Monster {
    let index = monster_index(monster_type);
    let lev_add = (world.level - AMULETLEVEL).max(0);
    let monster_level = MONSTER_LEVELS[index] + lev_add;
    let hp = world.rng.roll(monster_level, 8);
    let max_hp = hp;
    let arm = MONSTER_ARMOR[index] - lev_add;
    let exp = MONSTER_EXP[index] + lev_add * 10 + exp_add(monster_level, max_hp);
    let disguise = if monster_type == 'X' {
        rnd_thing(&mut world.rng, world.level)
    } else {
        monster_type
    };
    let mut flags = MONSTER_FLAGS[index];
    if world.level > 29 {
        flags |= ISHASTE;
    }
    let mut monster = Monster {
        monster_type,
        disguise,
        pos,
        oldch,
        room,
        dest: "none",
        dest_pos: None,
        flags,
        turn: true,
        stats: MonsterStats {
            strength: 10,
            exp,
            level: monster_level,
            arm,
            hp,
            damage: MONSTER_DAMAGE[index],
            max_hp,
        },
        pack_count: 0,
    };
    if is_wearing(world, R_AGGR) {
        runto(world, &mut monster);
    }
    monster
}

fn runto(world: &mut MonsterWorld, monster: &mut Monster) {
    monster.flags |= ISRUN;
    monster.flags &= !ISHELD;
    let (dest, dest_pos) = find_dest(world, monster);
    monster.dest = dest;
    monster.dest_pos = dest_pos;
}

fn wake_monster(world: &mut MonsterWorld, monster: &mut Monster) {
    if monster.flags & ISRUN == 0 {
        let wake_roll = world.rng.rnd(3);
        world
            .trace
            .insert("wake_roll".to_string(), json!(wake_roll));
        if wake_roll != 0
            && monster.flags & ISMEAN != 0
            && monster.flags & ISHELD == 0
            && !is_wearing(world, R_STEALTH)
            && world.player_flags & ISLEVIT == 0
        {
            monster.dest = "hero";
            monster.dest_pos = Some(world.hero);
            monster.flags |= ISRUN;
            world.markers.push("monster_runs".to_string());
        }
    }

    if monster.monster_type == 'M'
        && world.player_flags & ISBLIND == 0
        && world.player_flags & ISHALU == 0
        && monster.flags & ISFOUND == 0
        && monster.flags & ISCANC == 0
        && monster.flags & ISRUN != 0
    {
        let visible = (monster.room == world.proom && !room_dark(world, world.proom))
            || dist(monster.pos, world.hero) < LAMPDIST;
        world
            .trace
            .insert("medusa_visible".to_string(), json!(visible));
        if visible {
            monster.flags |= ISFOUND;
            let save_payload = save(world, VS_MAGIC, 1);
            let saved = save_payload["saved"].as_bool().unwrap();
            world.trace.insert("medusa_save".to_string(), save_payload);
            if !saved {
                world.player_flags |= ISHUH;
                world.markers.push("confuse_player".to_string());
                world.markers.push("fuse_unconfuse".to_string());
            }
        }
    }

    if monster.flags & ISGREED != 0 && monster.flags & ISRUN == 0 {
        monster.flags |= ISRUN;
        if world.proom_goldval != 0 {
            monster.dest = "gold";
            monster.dest_pos = Some(world.proom_gold);
        } else {
            monster.dest = "hero";
            monster.dest_pos = Some(world.hero);
        }
        world.markers.push("greed_runs".to_string());
    }
}

fn find_dest(world: &mut MonsterWorld, monster: &Monster) -> (&'static str, Option<Coord>) {
    let carry_prob = MONSTER_CARRY[monster_index(monster.monster_type)];
    if carry_prob <= 0 || monster.room == world.proom || see_monst(world, monster) {
        return ("hero", Some(world.hero));
    }
    for obj in world.objects.clone() {
        if obj.obj_type == SCROLL && obj.which == S_SCARE {
            continue;
        }
        if obj.room == monster.room {
            let roll = world.rng.rnd(100);
            push_find_dest_roll(world, obj.pos, roll, carry_prob);
            if roll < carry_prob
                && !world
                    .claimed_dests
                    .iter()
                    .any(|claimed| coord_eq(obj.pos, *claimed))
            {
                return ("object", Some(obj.pos));
            }
        }
    }
    ("hero", Some(world.hero))
}

fn randmonster_cases() -> Vec<Value> {
    vec![
        randmonster_case(1, 1, false),
        randmonster_case(7, 12, false),
        randmonster_case(-17, 30, false),
        randmonster_case(5, 6, true),
        randmonster_case(10, 18, true),
    ]
}

fn randmonster_case(seed: i32, level: i32, wander: bool) -> Value {
    let mut rng = RogueRng::new(seed);
    let mut value = randmonster(&mut rng, level, wander);
    value
        .as_object_mut()
        .unwrap()
        .insert("seed".to_string(), json!(seed));
    value
}

fn new_monster_cases() -> Vec<Value> {
    vec![
        new_monster_case("kestrel_level_1", 1, 1, 'K', coord(4, 5), 0, None),
        new_monster_case("dragon_level_30", 7, 30, 'D', coord(7, 8), 1, None),
        new_monster_case("xeroc_disguise", -17, 26, 'X', coord(10, 20), 2, None),
        new_monster_case(
            "aggravate_ring_sets_dest",
            3,
            12,
            'C',
            coord(3, 4),
            1,
            Some(ring(R_AGGR, 0)),
        ),
    ]
}

fn new_monster_case(
    name: &'static str,
    seed: i32,
    level: i32,
    monster_type: char,
    pos: Coord,
    room: i32,
    left_ring: Option<SourceRing>,
) -> Value {
    let mut world = MonsterWorld::new(seed, level, coord(1, 1), 0);
    world.left_ring = left_ring;
    let monster = new_monster(&mut world, monster_type, pos, room, '.');
    json!({"name": name, "seed": seed, "world": world_json(&world), "monster": monster_json(&monster)})
}

fn runto_cases() -> Vec<Value> {
    vec![
        runto_case(
            "same_room_goes_hero",
            1,
            'C',
            0,
            0,
            Vec::new(),
            Vec::new(),
            coord(1, 1),
        ),
        runto_case(
            "carry_object_dest",
            7,
            'C',
            1,
            0,
            vec![object(FOOD, 0, coord(6, 7), 1)],
            Vec::new(),
            coord(1, 1),
        ),
        runto_case(
            "scare_scroll_skipped",
            7,
            'C',
            1,
            0,
            vec![
                object(SCROLL, S_SCARE, coord(6, 7), 1),
                object(FOOD, 0, coord(6, 8), 1),
            ],
            Vec::new(),
            coord(1, 1),
        ),
        runto_case(
            "claimed_object_goes_hero",
            7,
            'C',
            1,
            0,
            vec![object(FOOD, 0, coord(6, 7), 1)],
            vec![coord(6, 7)],
            coord(1, 1),
        ),
        runto_case(
            "visible_goes_hero",
            7,
            'C',
            1,
            0,
            vec![object(FOOD, 0, coord(6, 7), 1)],
            Vec::new(),
            coord(5, 6),
        ),
    ]
}

fn runto_case(
    name: &'static str,
    seed: i32,
    monster_type: char,
    room: i32,
    proom: i32,
    objects: Vec<SourceObject>,
    claimed: Vec<Coord>,
    hero: Coord,
) -> Value {
    let mut world = MonsterWorld::new(seed, 12, hero, proom);
    world.objects = objects;
    world.claimed_dests = claimed;
    world.room_dark = vec![(proom, false), (room, false)];
    let mut monster = Monster {
        monster_type,
        disguise: monster_type,
        pos: coord(5, 5),
        oldch: '.',
        room,
        dest: "none",
        dest_pos: None,
        flags: MONSTER_FLAGS[monster_index(monster_type)],
        turn: true,
        stats: base_stats(monster_type),
        pack_count: 0,
    };
    runto(&mut world, &mut monster);
    json!({"name": name, "seed": seed, "world": world_json(&world), "monster": monster_json(&monster)})
}

fn wake_cases() -> Vec<Value> {
    vec![
        wake_case(
            "mean_starts_running",
            5,
            'K',
            MONSTER_FLAGS[monster_index('K')],
            None,
            0,
            false,
            coord(5, 6),
            0,
        ),
        wake_case(
            "mean_roll_zero_stays",
            1,
            'K',
            MONSTER_FLAGS[monster_index('K')],
            None,
            0,
            false,
            coord(5, 6),
            0,
        ),
        wake_case(
            "stealth_prevents_running",
            5,
            'K',
            MONSTER_FLAGS[monster_index('K')],
            Some(ring(R_STEALTH, 0)),
            0,
            false,
            coord(5, 6),
            0,
        ),
        wake_case(
            "levitation_prevents_running",
            5,
            'K',
            MONSTER_FLAGS[monster_index('K')],
            None,
            ISLEVIT,
            false,
            coord(5, 6),
            0,
        ),
        wake_case(
            "medusa_confuses",
            5,
            'M',
            MONSTER_FLAGS[monster_index('M')],
            None,
            0,
            false,
            coord(5, 6),
            0,
        ),
        wake_case(
            "medusa_save",
            10,
            'M',
            MONSTER_FLAGS[monster_index('M')],
            None,
            0,
            false,
            coord(5, 6),
            0,
        ),
        wake_case(
            "medusa_dark_room_no_gaze",
            5,
            'M',
            MONSTER_FLAGS[monster_index('M')],
            None,
            0,
            true,
            coord(8, 8),
            0,
        ),
        wake_case(
            "greed_guards_gold",
            1,
            'O',
            MONSTER_FLAGS[monster_index('O')],
            None,
            0,
            false,
            coord(5, 6),
            25,
        ),
        wake_case(
            "greed_runs_hero_without_gold",
            1,
            'O',
            MONSTER_FLAGS[monster_index('O')],
            None,
            0,
            false,
            coord(5, 6),
            0,
        ),
    ]
}

fn wake_case(
    name: &'static str,
    seed: i32,
    monster_type: char,
    flags: i32,
    left_ring: Option<SourceRing>,
    player_flags: i32,
    is_room_dark: bool,
    pos: Coord,
    proom_goldval: i32,
) -> Value {
    let mut world = MonsterWorld::new(seed, 12, coord(5, 5), 0);
    world.proom_goldval = proom_goldval;
    world.room_dark = vec![(0, is_room_dark)];
    world.player_flags = player_flags;
    world.left_ring = left_ring;
    let mut monster = Monster {
        monster_type,
        disguise: monster_type,
        pos,
        oldch: '.',
        room: 0,
        dest: "none",
        dest_pos: None,
        flags,
        turn: true,
        stats: base_stats(monster_type),
        pack_count: 0,
    };
    wake_monster(&mut world, &mut monster);
    json!({"name": name, "seed": seed, "world": world_json(&world), "monster": monster_json(&monster)})
}

impl MonsterWorld {
    fn new(seed: i32, level: i32, hero: Coord, proom: i32) -> Self {
        Self {
            rng: RogueRng::new(seed),
            level,
            max_level: level,
            hero,
            proom,
            proom_gold: coord(2, 2),
            proom_goldval: 0,
            room_dark: Vec::new(),
            player_flags: 0,
            left_ring: None,
            right_ring: None,
            objects: Vec::new(),
            claimed_dests: Vec::new(),
            markers: Vec::new(),
            trace: serde_json::Map::new(),
        }
    }
}

fn exp_add(level: i32, max_hp: i32) -> i32 {
    let mut modifier = if level == 1 { max_hp / 8 } else { max_hp / 6 };
    if level > 9 {
        modifier *= 20;
    } else if level > 6 {
        modifier *= 4;
    }
    modifier
}

fn rnd_thing(rng: &mut RogueRng, level: i32) -> char {
    if level >= AMULETLEVEL {
        RND_THING_LIST[rng.rnd(RND_THING_LIST.len() as i32) as usize]
    } else {
        RND_THING_LIST[rng.rnd(RND_THING_LIST.len() as i32 - 1) as usize]
    }
}

fn save(world: &mut MonsterWorld, which: i32, player_level: i32) -> Value {
    let mut adjusted = which;
    if which == VS_MAGIC {
        if let Some(left) = &world.left_ring {
            if left.which == R_PROTECT {
                adjusted -= left.arm;
            }
        }
        if let Some(right) = &world.right_ring {
            if right.which == R_PROTECT {
                adjusted -= right.arm;
            }
        }
    }
    let need = 14 + adjusted - player_level / 2;
    let roll = world.rng.roll(1, 20);
    json!({"which": adjusted, "original_which": which, "level": player_level, "need": need, "roll": roll, "saved": roll >= need, "rng_seed": world.rng.seed})
}

fn see_monst(world: &MonsterWorld, monster: &Monster) -> bool {
    if world.player_flags & ISBLIND != 0 {
        return false;
    }
    if monster.flags & ISINVIS != 0 && world.player_flags & CANSEE == 0 {
        return false;
    }
    if dist(monster.pos, world.hero) < LAMPDIST {
        return true;
    }
    if monster.room != world.proom {
        return false;
    }
    !room_dark(world, monster.room)
}

fn room_dark(world: &MonsterWorld, room: i32) -> bool {
    world
        .room_dark
        .iter()
        .find(|(index, _)| *index == room)
        .map(|(_, dark)| *dark)
        .unwrap_or(false)
}

fn is_wearing(world: &MonsterWorld, ring_kind: i32) -> bool {
    world
        .left_ring
        .as_ref()
        .is_some_and(|ring| ring.which == ring_kind)
        || world
            .right_ring
            .as_ref()
            .is_some_and(|ring| ring.which == ring_kind)
}

fn dist(first: Coord, second: Coord) -> i32 {
    (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y)
}

fn coord_eq(first: Coord, second: Coord) -> bool {
    first.x == second.x && first.y == second.y
}

fn monster_index(monster_type: char) -> usize {
    monster_type as usize - 'A' as usize
}

fn coord(y: i32, x: i32) -> Coord {
    Coord { y, x }
}

fn ring(which: i32, arm: i32) -> SourceRing {
    SourceRing { which, arm }
}

fn object(obj_type: char, which: i32, pos: Coord, room: i32) -> SourceObject {
    SourceObject {
        obj_type,
        which,
        pos,
        room,
    }
}

fn base_stats(monster_type: char) -> MonsterStats {
    let index = monster_index(monster_type);
    MonsterStats {
        strength: 10,
        exp: MONSTER_EXP[index],
        level: MONSTER_LEVELS[index],
        arm: MONSTER_ARMOR[index],
        hp: 1,
        damage: MONSTER_DAMAGE[index],
        max_hp: 1,
    }
}

fn push_find_dest_roll(world: &mut MonsterWorld, pos: Coord, roll: i32, prob: i32) {
    if !world.trace.contains_key("find_dest_rolls") {
        world.trace.insert("find_dest_rolls".to_string(), json!([]));
    }
    let rolls = world
        .trace
        .get_mut("find_dest_rolls")
        .unwrap()
        .as_array_mut()
        .unwrap();
    rolls.push(json!({"pos": coord_json(pos), "roll": roll, "prob": prob}));
}

fn world_json(world: &MonsterWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "level": world.level,
        "max_level": world.max_level,
        "hero": coord_json(world.hero),
        "proom": world.proom,
        "proom_gold": coord_json(world.proom_gold),
        "proom_goldval": world.proom_goldval,
        "player_flags": world.player_flags,
        "left_ring": world.left_ring.as_ref().map(ring_json),
        "right_ring": world.right_ring.as_ref().map(ring_json),
        "markers": world.markers,
        "trace": world.trace,
    })
}

fn monster_json(monster: &Monster) -> Value {
    json!({
        "type": char_json(monster.monster_type),
        "disguise": char_json(monster.disguise),
        "pos": coord_json(monster.pos),
        "oldch": char_json(monster.oldch),
        "room": monster.room,
        "dest": monster.dest,
        "dest_pos": monster.dest_pos.map(coord_json),
        "flags": monster.flags,
        "turn": monster.turn,
        "stats": stats_json(&monster.stats),
        "pack_count": monster.pack_count,
    })
}

fn stats_json(stats: &MonsterStats) -> Value {
    json!({
        "strength": stats.strength,
        "exp": stats.exp,
        "level": stats.level,
        "arm": stats.arm,
        "hp": stats.hp,
        "damage": stats.damage,
        "max_hp": stats.max_hp,
    })
}

fn ring_json(ring: &SourceRing) -> Value {
    json!({"which": ring.which, "arm": ring.arm})
}

fn coord_json(coord: Coord) -> Value {
    json!({"y": coord.y, "x": coord.x})
}

fn char_json(ch: char) -> String {
    ch.to_string()
}
