use crate::{RogueRng, DOOR, FLOOR, PASSAGE};
use serde_json::{json, Value};

const ISGONE: i32 = 0o000002;
const ISCANC: i32 = 0o000010;
const ISGREED: i32 = 0o000040;
const ISTARGET: i32 = 0o000200;
const ISRUN: i32 = 0o020000;

const BOLT_LENGTH: i32 = 6;
const DRAGONSHOT: i32 = 5;

#[derive(Clone, Copy)]
pub struct Coord {
    pub y: i32,
    pub x: i32,
}

#[derive(Clone)]
pub struct ChaseRoom {
    pub index: i32,
    pub goldval: i32,
    pub flags: i32,
    pub exits: Vec<Coord>,
}

#[derive(Clone)]
pub struct ChaseObject {
    pub obj_type: char,
    pub pos: Coord,
}

#[derive(Clone)]
pub struct ChaseMonster {
    pub monster_type: char,
    pub pos: Coord,
    pub room: i32,
    pub flags: i32,
    pub dest_kind: String,
    pub dest_pos: Coord,
    pub pack: Vec<ChaseObject>,
}

pub struct DoChaseWorld {
    pub rng: RogueRng,
    pub hero: Coord,
    pub proom: i32,
    pub rooms: Vec<ChaseRoom>,
    pub passages: Vec<ChaseRoom>,
    pub objects: Vec<ChaseObject>,
    pub terrain: Vec<(Coord, char)>,
    pub dest_room: i32,
    pub passage_index: i32,
    pub chase_keep: bool,
    pub chase_pos: Coord,
    pub chase_room: i32,
    pub attack_return: i32,
    pub find_dest_kind: String,
    pub find_dest_pos: Coord,
    pub running: bool,
    pub count: i32,
    pub quiet: i32,
    pub has_hit: bool,
    pub to_death: bool,
    pub kamikaze: bool,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_do_chase_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_do_chase.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn do_chase(world: &mut DoChaseWorld, monster: &mut ChaseMonster) -> i32 {
    let mut rer = room_by_index(&world.rooms, monster.room).clone();
    if monster.flags & ISGREED != 0 && rer.goldval == 0 {
        monster.dest_kind = "hero".to_string();
        monster.dest_pos = world.hero;
        world
            .trace
            .insert("greed_dest_reset".to_string(), json!(true));
    }
    let ree_index = if monster.dest_kind == "hero" {
        world.proom
    } else {
        world.dest_room
    };
    let mut door = terrain_at(world, monster.pos) == DOOR;
    let mut target = monster.dest_pos;
    let mut mindist = 32767;
    let mut route_checks = Vec::new();

    while rer.index != ree_index {
        for exit_coord in &rer.exits {
            let curdist = dist(monster.dest_pos, *exit_coord);
            let mut check =
                json!({"room": rer.index, "exit": coord_json(*exit_coord), "dist": curdist});
            if curdist < mindist {
                target = *exit_coord;
                mindist = curdist;
                check
                    .as_object_mut()
                    .unwrap()
                    .insert("chosen".to_string(), json!(true));
            }
            route_checks.push(check);
        }
        if door {
            rer = room_by_index(&world.passages, world.passage_index).clone();
            door = false;
            continue;
        }
        break;
    }
    if rer.index == ree_index {
        target = monster.dest_pos;
        world.trace.insert("target".to_string(), coord_json(target));
        if dragon_flame(world, monster) {
            return 0;
        }
    }
    world
        .trace
        .insert("route_checks".to_string(), json!(route_checks));
    world.trace.insert("target".to_string(), coord_json(target));

    let stoprun;
    if !world.chase_keep {
        if coord_eq(target, world.hero) {
            world.markers.push("attack".to_string());
            return world.attack_return;
        }
        if coord_eq(target, monster.dest_pos) {
            let mut found_index = None;
            for (index, obj) in world.objects.iter().enumerate() {
                if coord_eq(obj.pos, monster.dest_pos) {
                    found_index = Some(index);
                    break;
                }
            }
            if let Some(index) = found_index {
                let obj = world.objects.remove(index);
                let obj_pos = obj.pos;
                monster.pack.insert(0, obj);
                let replacement = if room_by_index(&world.rooms, monster.room).flags & ISGONE != 0 {
                    PASSAGE
                } else {
                    FLOOR
                };
                set_terrain(world, obj_pos, replacement);
                monster.dest_kind = world.find_dest_kind.clone();
                monster.dest_pos = world.find_dest_pos;
                world.markers.push("pickup_object".to_string());
            }
            stoprun = monster.monster_type != 'F';
        } else {
            stoprun = false;
        }
    } else if monster.monster_type == 'F' {
        return 0;
    } else {
        stoprun = false;
    }

    if !coord_eq(world.chase_pos, monster.pos) {
        monster.pos = world.chase_pos;
        monster.room = world.chase_room;
        world.markers.push("relocate".to_string());
    }
    if stoprun && coord_eq(monster.pos, monster.dest_pos) {
        monster.flags &= !ISRUN;
    }
    0
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    monster_type: char,
    pos: Coord,
    room: i32,
    flags: i32,
    dest_kind: &'static str,
    dest_pos: Coord,
    hero: Coord,
    proom: i32,
    room_goldval: i32,
    room_flags: i32,
    dest_room: i32,
    tile: Option<char>,
    chase_keep: bool,
    chase_pos: Coord,
    chase_room: i32,
    attack_return: i32,
    objects: Vec<ChaseObject>,
    find_dest_kind: &'static str,
    find_dest_pos: Coord,
    has_hit: bool,
    to_death: bool,
    kamikaze: bool,
}

fn run_case(case: Case) -> Value {
    let mut world = world_for(&case);
    let mut monster = ChaseMonster {
        monster_type: case.monster_type,
        pos: case.pos,
        room: case.room,
        flags: case.flags,
        dest_kind: case.dest_kind.to_string(),
        dest_pos: case.dest_pos,
        pack: Vec::new(),
    };
    let returned = do_chase(&mut world, &mut monster);
    json!({"name": case.name, "seed": case.seed, "returned": returned, "monster": monster_json(&monster), "world": world_json(&world)})
}

fn cases() -> Vec<Case> {
    vec![
        base_case("different_room_routes_exit", 1).chase_pos(coord(6, 6)),
        base_case("door_reroutes_passage", 1)
            .tile(DOOR)
            .dest("object", coord(12, 12), 2)
            .chase_pos(coord(8, 3))
            .chase_room(9),
        base_case("dragon_flame", 1)
            .monster('D')
            .room(1)
            .pos(coord(5, 5))
            .dest("hero", coord(5, 10), 1)
            .hero(coord(5, 10))
            .has_hit(true)
            .to_death(true)
            .kamikaze(true),
        base_case("dragon_cancelled_chases", 1)
            .monster('D')
            .flags(ISRUN | ISCANC)
            .room(1)
            .pos(coord(5, 5))
            .dest("hero", coord(5, 10), 1)
            .hero(coord(5, 10))
            .chase_pos(coord(5, 6))
            .chase_room(1),
        base_case("attack_hero_return", 7)
            .room(1)
            .pos(coord(5, 5))
            .dest("hero", coord(10, 10), 1)
            .hero(coord(10, 10))
            .chase_keep(false)
            .chase_pos(coord(5, 5))
            .attack_return(-1),
        base_case("pickup_object_keeps_running_after_find_dest", 7)
            .room(1)
            .pos(coord(5, 5))
            .dest("object", coord(6, 6), 1)
            .chase_keep(false)
            .chase_pos(coord(6, 6))
            .chase_room(1)
            .objects(vec![object('*', coord(6, 6))])
            .find_dest("hero", coord(10, 10)),
        base_case("stoprun_at_destination", 7)
            .room(1)
            .pos(coord(5, 5))
            .dest("custom", coord(6, 6), 1)
            .chase_keep(false)
            .chase_pos(coord(6, 6))
            .chase_room(1),
        base_case("venus_flytrap_no_relocate", 7)
            .monster('F')
            .room(1)
            .pos(coord(5, 5))
            .dest("hero", coord(10, 10), 1)
            .hero(coord(10, 10))
            .chase_keep(true)
            .chase_pos(coord(6, 6))
            .chase_room(1),
        base_case("greed_gold_taken_resets_dest", 7)
            .monster('O')
            .flags(ISRUN | ISGREED)
            .room_goldval(0)
            .dest("object", coord(6, 6), 1)
            .chase_keep(true)
            .chase_pos(coord(5, 6)),
    ]
}

fn base_case(name: &'static str, seed: i32) -> Case {
    Case {
        name,
        seed,
        monster_type: 'K',
        pos: coord(5, 5),
        room: 0,
        flags: ISRUN,
        dest_kind: "hero",
        dest_pos: coord(10, 10),
        hero: coord(10, 10),
        proom: 1,
        room_goldval: 1,
        room_flags: 0,
        dest_room: 1,
        tile: None,
        chase_keep: true,
        chase_pos: coord(6, 6),
        chase_room: 0,
        attack_return: 0,
        objects: Vec::new(),
        find_dest_kind: "hero",
        find_dest_pos: coord(10, 10),
        has_hit: false,
        to_death: false,
        kamikaze: false,
    }
}

impl Case {
    fn monster(mut self, monster_type: char) -> Self {
        self.monster_type = monster_type;
        self
    }
    fn pos(mut self, pos: Coord) -> Self {
        self.pos = pos;
        self
    }
    fn room(mut self, room: i32) -> Self {
        self.room = room;
        self.chase_room = room;
        self
    }
    fn flags(mut self, flags: i32) -> Self {
        self.flags = flags;
        self
    }
    fn dest(mut self, kind: &'static str, pos: Coord, room: i32) -> Self {
        self.dest_kind = kind;
        self.dest_pos = pos;
        self.dest_room = room;
        self
    }
    fn hero(mut self, hero: Coord) -> Self {
        self.hero = hero;
        self
    }
    fn room_goldval(mut self, goldval: i32) -> Self {
        self.room_goldval = goldval;
        self
    }
    fn tile(mut self, tile: char) -> Self {
        self.tile = Some(tile);
        self
    }
    fn chase_keep(mut self, chase_keep: bool) -> Self {
        self.chase_keep = chase_keep;
        self
    }
    fn chase_pos(mut self, chase_pos: Coord) -> Self {
        self.chase_pos = chase_pos;
        self
    }
    fn chase_room(mut self, chase_room: i32) -> Self {
        self.chase_room = chase_room;
        self
    }
    fn attack_return(mut self, attack_return: i32) -> Self {
        self.attack_return = attack_return;
        self
    }
    fn objects(mut self, objects: Vec<ChaseObject>) -> Self {
        self.objects = objects;
        self
    }
    fn find_dest(mut self, kind: &'static str, pos: Coord) -> Self {
        self.find_dest_kind = kind;
        self.find_dest_pos = pos;
        self
    }
    fn has_hit(mut self, has_hit: bool) -> Self {
        self.has_hit = has_hit;
        self
    }
    fn to_death(mut self, to_death: bool) -> Self {
        self.to_death = to_death;
        self
    }
    fn kamikaze(mut self, kamikaze: bool) -> Self {
        self.kamikaze = kamikaze;
        self
    }
}

fn world_for(case: &Case) -> DoChaseWorld {
    let rooms = vec![
        ChaseRoom {
            index: 0,
            goldval: case.room_goldval,
            flags: case.room_flags,
            exits: vec![coord(2, 2), coord(6, 6)],
        },
        ChaseRoom {
            index: 1,
            goldval: 0,
            flags: 0,
            exits: vec![coord(10, 10)],
        },
        ChaseRoom {
            index: 2,
            goldval: 0,
            flags: 0,
            exits: vec![coord(4, 4)],
        },
    ];
    let passages = vec![ChaseRoom {
        index: 9,
        goldval: 0,
        flags: ISGONE,
        exits: vec![coord(3, 8), coord(8, 3)],
    }];
    let mut terrain = Vec::new();
    if let Some(tile) = case.tile {
        terrain.push((case.pos, tile));
    }
    DoChaseWorld {
        rng: RogueRng::new(case.seed),
        hero: case.hero,
        proom: case.proom,
        rooms,
        passages,
        objects: case.objects.clone(),
        terrain,
        dest_room: case.dest_room,
        passage_index: 9,
        chase_keep: case.chase_keep,
        chase_pos: case.chase_pos,
        chase_room: case.chase_room,
        attack_return: case.attack_return,
        find_dest_kind: case.find_dest_kind.to_string(),
        find_dest_pos: case.find_dest_pos,
        running: true,
        count: 1,
        quiet: 3,
        has_hit: case.has_hit,
        to_death: case.to_death,
        kamikaze: case.kamikaze,
        markers: Vec::new(),
        trace: serde_json::Map::new(),
    }
}

fn dragon_flame(world: &mut DoChaseWorld, monster: &ChaseMonster) -> bool {
    let aligned = monster.pos.y == world.hero.y
        || monster.pos.x == world.hero.x
        || (monster.pos.y - world.hero.y).abs() == (monster.pos.x - world.hero.x).abs();
    if monster.monster_type != 'D'
        || !aligned
        || dist(monster.pos, world.hero) > BOLT_LENGTH * BOLT_LENGTH
        || monster.flags & ISCANC != 0
    {
        return false;
    }
    let shot_roll = world.rng.rnd(DRAGONSHOT);
    world
        .trace
        .insert("dragon_roll".to_string(), json!(shot_roll));
    if shot_roll != 0 {
        return false;
    }
    world.trace.insert(
        "delta".to_string(),
        json!({"y": sign(world.hero.y - monster.pos.y), "x": sign(world.hero.x - monster.pos.x)}),
    );
    if world.has_hit {
        world.markers.push("endmsg".to_string());
    }
    world.markers.push("fire_bolt_flame".to_string());
    world.running = false;
    world.count = 0;
    world.quiet = 0;
    if world.to_death && monster.flags & ISTARGET == 0 {
        world.to_death = false;
        world.kamikaze = false;
    }
    true
}

fn room_by_index(rooms: &[ChaseRoom], index: i32) -> &ChaseRoom {
    rooms.iter().find(|room| room.index == index).unwrap()
}

fn terrain_at(world: &DoChaseWorld, pos: Coord) -> char {
    world
        .terrain
        .iter()
        .find(|(coord, _)| coord_eq(*coord, pos))
        .map(|(_, ch)| *ch)
        .unwrap_or(FLOOR)
}

fn set_terrain(world: &mut DoChaseWorld, pos: Coord, ch: char) {
    for (coord, value) in &mut world.terrain {
        if coord_eq(*coord, pos) {
            *value = ch;
            return;
        }
    }
    world.terrain.push((pos, ch));
}

fn dist(first: Coord, second: Coord) -> i32 {
    (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y)
}

fn coord_eq(first: Coord, second: Coord) -> bool {
    first.x == second.x && first.y == second.y
}

fn sign(value: i32) -> i32 {
    (value > 0) as i32 - (value < 0) as i32
}

fn coord(y: i32, x: i32) -> Coord {
    Coord { y, x }
}

fn object(obj_type: char, pos: Coord) -> ChaseObject {
    ChaseObject { obj_type, pos }
}

pub fn monster_json(monster: &ChaseMonster) -> Value {
    json!({
        "type": monster.monster_type.to_string(),
        "pos": coord_json(monster.pos),
        "room": monster.room,
        "flags": monster.flags,
        "dest": monster.dest_kind,
        "dest_pos": coord_json(monster.dest_pos),
        "pack": monster.pack.iter().map(object_json).collect::<Vec<_>>(),
    })
}

pub fn object_json(obj: &ChaseObject) -> Value {
    json!({"type": obj.obj_type.to_string(), "pos": coord_json(obj.pos)})
}

pub fn world_json(world: &DoChaseWorld) -> Value {
    let mut terrain = world
        .terrain
        .iter()
        .map(|(coord, ch)| json!({"y": coord.y, "x": coord.x, "ch": ch.to_string()}))
        .collect::<Vec<_>>();
    terrain.sort_by_key(|value| (value["y"].as_i64().unwrap(), value["x"].as_i64().unwrap()));
    json!({
        "rng_seed": world.rng.seed,
        "hero": coord_json(world.hero),
        "proom": world.proom,
        "objects": world.objects.iter().map(object_json).collect::<Vec<_>>(),
        "terrain": terrain,
        "running": world.running,
        "count": world.count,
        "quiet": world.quiet,
        "has_hit": world.has_hit,
        "to_death": world.to_death,
        "kamikaze": world.kamikaze,
        "markers": world.markers,
        "trace": world.trace,
    })
}

fn coord_json(coord: Coord) -> Value {
    json!({"y": coord.y, "x": coord.x})
}
