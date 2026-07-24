use crate::{
    step_ok, RogueRng, AMULET, AMULETLEVEL, ARMOR, DOOR, FLOOR, FOOD, GOLD, MAXOBJ, MAXPASS,
    MAXROOMS, MAXTRAPS, NUMCOLS, NUMLINES, PASSAGE, POTION, RING, SCROLL, STAIRS, STICK, WEAPON,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const ISDARK: i16 = 0o000001;
pub const ISGONE: i16 = 0o000002;
pub const ISMAZE: i16 = 0o000004;

pub const ISCURSED: i32 = 0o000001;
pub const ISMISL: i32 = 0o000004;
pub const ISMANY: i32 = 0o000010;

pub const F_PASS: u8 = 0x80;
pub const F_SEEN: u8 = 0x40;
pub const F_REAL: u8 = 0x10;
pub const F_PNUM: u8 = 0x0f;

const GOLDGRP: i32 = 1;
const TREAS_ROOM: i32 = 20;
const MAXTREAS: i32 = 10;
const MINTREAS: i32 = 2;
const MAXTRIES: i32 = 10;
const NTRAPS: i32 = 8;

const ISGREED: i32 = 0o000040;
const ISHASTE: i32 = 0o000100;
const ISINVIS: i32 = 0o002000;
const ISMEAN: i32 = 0o004000;
const ISREGEN: i32 = 0o010000;
const ISFLY: i32 = 0o040000;

const R_PROTECT: i32 = 0;
const R_ADDSTR: i32 = 1;
const R_AGGR: i32 = 6;
const R_ADDHIT: i32 = 7;
const R_ADDDAM: i32 = 8;
const R_TELEPORT: i32 = 11;
const WS_LIGHT: i32 = 0;
const DAGGER: i32 = 4;

const LVL_MONS: [char; 26] = [
    'K', 'E', 'B', 'S', 'H', 'I', 'R', 'O', 'Z', 'L', 'C', 'Q', 'A', 'N', 'Y', 'F', 'T', 'W', 'P',
    'X', 'U', 'M', 'V', 'G', 'J', 'D',
];
const MONSTER_CARRY: [i32; 26] = [
    0, 0, 15, 100, 0, 0, 20, 0, 0, 70, 0, 0, 40, 100, 15, 0, 0, 0, 0, 50, 0, 20, 0, 30, 30, 0,
];
const MONSTER_LEVELS: [i32; 26] = [
    5, 1, 4, 10, 1, 8, 13, 1, 1, 15, 1, 3, 8, 3, 1, 8, 3, 2, 1, 6, 7, 8, 5, 7, 4, 2,
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
const THING_PROBS: [i32; 7] = [26, 36, 16, 7, 7, 4, 4];
const ARMOR_PROBS: [i32; 8] = [20, 15, 15, 13, 12, 10, 10, 5];
const POTION_PROBS: [i32; 14] = [7, 8, 8, 13, 3, 13, 6, 6, 2, 5, 5, 13, 5, 6];
const RING_PROBS: [i32; 14] = [9, 9, 5, 10, 10, 1, 10, 8, 8, 4, 9, 5, 7, 5];
const SCROLL_PROBS: [i32; 18] = [7, 4, 2, 3, 7, 10, 10, 6, 7, 10, 3, 2, 5, 8, 4, 7, 3, 2];
const WEAPON_PROBS: [i32; 9] = [11, 11, 12, 12, 8, 10, 12, 12, 12];
const STICK_PROBS: [i32; 14] = [12, 6, 3, 3, 3, 15, 10, 10, 11, 9, 1, 6, 6, 5];
const A_CLASS: [i32; 8] = [8, 7, 7, 6, 5, 4, 4, 3];
const INIT_WEAPON_FLAGS: [i32; 9] = [
    0,
    0,
    0,
    ISMANY | ISMISL,
    ISMISL | ISMISL,
    0,
    ISMANY | ISMISL,
    ISMANY | ISMISL,
    ISMISL,
];
const RND_THING_LIST: [char; 10] = [
    POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS, GOLD, AMULET,
];

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize)]
pub struct Coord {
    pub y: i32,
    pub x: i32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Room {
    pub pos: Coord,
    pub max: Coord,
    pub gold: Coord,
    pub goldval: i32,
    pub flags: i16,
    pub nexits: usize,
    pub exits: Vec<Coord>,
}

impl Default for Room {
    fn default() -> Self {
        Self {
            pos: Coord::default(),
            max: Coord::default(),
            gold: Coord::default(),
            goldval: 0,
            flags: 0,
            nexits: 0,
            exits: Vec::new(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct Place {
    pub ch: char,
    pub flags: u8,
    pub monst: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SourceObject {
    #[serde(rename = "type")]
    pub obj_type: String,
    pub which: i32,
    pub pos: Coord,
    pub count: i32,
    pub hplus: i32,
    pub dplus: i32,
    pub arm: i32,
    pub flags: i32,
    pub group: i32,
    pub goldval: i32,
}

impl Default for SourceObject {
    fn default() -> Self {
        Self {
            obj_type: String::new(),
            which: 0,
            pos: Coord::default(),
            count: 1,
            hplus: 0,
            dplus: 0,
            arm: 11,
            flags: 0,
            group: 0,
            goldval: 0,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SourceMonster {
    #[serde(rename = "type")]
    pub monster_type: String,
    pub pos: Coord,
    pub level: i32,
    pub hp: i32,
    pub disguise: String,
    pub flags: i32,
    pub pack: Vec<SourceObject>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SourceTrap {
    pub pos: Coord,
    pub kind: i32,
}

#[derive(Clone, Debug)]
pub struct SourceMapCell {
    pub id: String,
    pub row: i32,
    pub col: i32,
    pub ch: char,
    pub flags: i32,
}

impl Default for Place {
    fn default() -> Self {
        Self {
            ch: ' ',
            flags: F_REAL,
            monst: false,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SourceLevelDraft {
    pub level: i32,
    pub max_level: i32,
    pub amulet: bool,
    pub rooms: Vec<Room>,
    pub rows: Vec<String>,
    pub gold_positions: BTreeMap<String, i32>,
    pub monster_slots: Vec<Coord>,
    pub monsters: Vec<SourceMonster>,
    pub level_objects: Vec<SourceObject>,
    pub traps: Vec<SourceTrap>,
    pub stairs: Coord,
    pub hero: Coord,
    pub ntraps: i32,
    pub no_food: i32,
    pub rng_seed: i32,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub passages: Vec<Room>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub hidden_passages: Vec<Coord>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub passage_numbers: BTreeMap<String, i32>,
    #[serde(default, skip)]
    pub source_map_cells: Vec<SourceMapCell>,
}

pub fn generate_room_slice(
    seed: i32,
    level: i32,
    max_level: i32,
    amulet: bool,
) -> SourceLevelDraft {
    let mut builder = RoomBuilder::new(seed, level, max_level, amulet);
    builder.do_rooms();
    builder.finish(false)
}

pub fn generate_passage_slice(
    seed: i32,
    level: i32,
    max_level: i32,
    amulet: bool,
) -> SourceLevelDraft {
    let mut builder = RoomBuilder::new(seed, level, max_level, amulet);
    builder.do_rooms();
    builder.do_passages();
    builder.finish(true)
}

pub fn generate_new_level_slice(
    seed: i32,
    level: i32,
    max_level: i32,
    amulet: bool,
) -> SourceLevelDraft {
    let mut builder = RoomBuilder::new(seed, level, max_level, amulet);
    builder.do_rooms();
    builder.do_passages();
    builder.no_food += 1;
    builder.put_things();
    builder.place_traps();
    builder.place_stairs();
    builder.assign_monster_rooms();
    builder.place_hero();
    builder.finish(true)
}

struct RoomBuilder {
    rng: RogueRng,
    level: i32,
    max_level: i32,
    amulet: bool,
    rooms: Vec<Room>,
    passages: Vec<Room>,
    places: Vec<Vec<Place>>,
    gold_positions: BTreeMap<String, i32>,
    monster_slots: Vec<Coord>,
    monsters: Vec<SourceMonster>,
    level_objects: Vec<SourceObject>,
    traps: Vec<SourceTrap>,
    stairs: Coord,
    hero: Coord,
    ntraps: i32,
    maze_maxy: i32,
    maze_maxx: i32,
    maze_starty: i32,
    maze_startx: i32,
    pnum: i32,
    newpnum: bool,
    no_food: i32,
    weapon_group: i32,
}

impl RoomBuilder {
    fn new(seed: i32, level: i32, max_level: i32, amulet: bool) -> Self {
        Self {
            rng: RogueRng::new(seed),
            level,
            max_level,
            amulet,
            rooms: vec![Room::default(); MAXROOMS],
            passages: vec![Room::default(); MAXPASS],
            places: vec![vec![Place::default(); NUMCOLS]; NUMLINES],
            gold_positions: BTreeMap::new(),
            monster_slots: Vec::new(),
            monsters: Vec::new(),
            level_objects: Vec::new(),
            traps: Vec::new(),
            stairs: Coord::default(),
            hero: Coord::default(),
            ntraps: 0,
            maze_maxy: 0,
            maze_maxx: 0,
            maze_starty: 0,
            maze_startx: 0,
            pnum: 0,
            newpnum: false,
            no_food: 0,
            weapon_group: 2,
        }
    }

    fn do_rooms(&mut self) {
        let bsze = Coord {
            y: (NUMLINES / 3) as i32,
            x: (NUMCOLS / 3) as i32,
        };
        for index in 0..self.rooms.len() {
            self.rooms[index].goldval = 0;
            self.rooms[index].nexits = 0;
            self.rooms[index].exits.clear();
            self.rooms[index].flags = 0;
        }
        let left_out = self.rng.rnd(4);
        for _ in 0..left_out {
            let room_index = self.rnd_room();
            self.rooms[room_index].flags |= ISGONE;
        }
        for index in 0..MAXROOMS {
            let top = Coord {
                y: (index as i32 / 3) * bsze.y,
                x: (index as i32 % 3) * bsze.x + 1,
            };
            if self.rooms[index].flags & ISGONE != 0 {
                loop {
                    self.rooms[index].pos.x = top.x + self.rng.rnd(bsze.x - 2) + 1;
                    self.rooms[index].pos.y = top.y + self.rng.rnd(bsze.y - 2) + 1;
                    self.rooms[index].max.x = -(NUMCOLS as i32);
                    self.rooms[index].max.y = -(NUMLINES as i32);
                    if self.rooms[index].pos.y > 0
                        && self.rooms[index].pos.y < (NUMLINES as i32 - 1)
                    {
                        break;
                    }
                }
                continue;
            }
            if self.rng.rnd(10) < self.level - 1 {
                self.rooms[index].flags |= ISDARK;
                if self.rng.rnd(15) == 0 {
                    self.rooms[index].flags = ISMAZE;
                }
            }
            if self.rooms[index].flags & ISMAZE != 0 {
                self.rooms[index].max.x = bsze.x - 1;
                self.rooms[index].max.y = bsze.y - 1;
                self.rooms[index].pos.x = top.x;
                if self.rooms[index].pos.x == 1 {
                    self.rooms[index].pos.x = 0;
                }
                self.rooms[index].pos.y = top.y;
                if self.rooms[index].pos.y == 0 {
                    self.rooms[index].pos.y += 1;
                    self.rooms[index].max.y -= 1;
                }
            } else {
                loop {
                    self.rooms[index].max.x = self.rng.rnd(bsze.x - 4) + 4;
                    self.rooms[index].max.y = self.rng.rnd(bsze.y - 4) + 4;
                    self.rooms[index].pos.x =
                        top.x + self.rng.rnd(bsze.x - self.rooms[index].max.x);
                    self.rooms[index].pos.y =
                        top.y + self.rng.rnd(bsze.y - self.rooms[index].max.y);
                    if self.rooms[index].pos.y != 0 {
                        break;
                    }
                }
            }
            self.draw_room(index);
            if self.rng.rnd(2) == 0 && (!self.amulet || self.level >= self.max_level) {
                let goldval = self.rng.gold_calc(self.level);
                let gold = self.find_floor(Some(index), 0, false);
                self.rooms[index].goldval = goldval;
                self.rooms[index].gold = gold;
                self.set_ch(gold.y, gold.x, GOLD);
                self.gold_positions
                    .insert(format!("{},{}", gold.y, gold.x), goldval);
                let mut gold_object = self.new_item();
                gold_object.goldval = goldval;
                gold_object.pos = gold;
                gold_object.flags = ISMANY;
                gold_object.group = GOLDGRP;
                gold_object.obj_type = GOLD.to_string();
                self.attach_object(gold_object);
            }
            if self.rng.rnd(100)
                < if self.rooms[index].goldval > 0 {
                    80
                } else {
                    25
                }
            {
                let monster_slot = self.find_floor(Some(index), 0, true);
                self.place_mut(monster_slot.y, monster_slot.x).monst = true;
                self.monster_slots.push(monster_slot);
                let monster_type = self.randmonster(false);
                let mut monster = self.new_monster(monster_type, monster_slot);
                self.give_pack(&mut monster);
                self.monsters.insert(0, monster);
            }
        }
    }

    fn finish(self, include_passages: bool) -> SourceLevelDraft {
        let rows = self.rows();
        let mut hidden_passages = Vec::new();
        let mut passage_numbers = BTreeMap::new();
        let mut source_map_cells = Vec::new();
        if include_passages {
            for (y, row) in self.places.iter().enumerate() {
                for (x, place) in row.iter().enumerate() {
                    if place.flags & F_REAL == 0 && matches!(place.ch, '|' | '-' | ' ') {
                        source_map_cells.push(SourceMapCell {
                            id: format!("cell{}", source_map_cells.len()),
                            row: y as i32,
                            col: x as i32,
                            ch: place.ch,
                            flags: place.flags as i32,
                        });
                    }
                    if place.flags & F_PASS != 0 && place.ch != PASSAGE {
                        hidden_passages.push(Coord {
                            y: y as i32,
                            x: x as i32,
                        });
                    }
                    let pnum = place.flags & F_PNUM;
                    if pnum != 0 {
                        passage_numbers.insert(format!("{},{}", y, x), pnum as i32);
                    }
                }
            }
        }
        SourceLevelDraft {
            level: self.level,
            max_level: self.max_level,
            amulet: self.amulet,
            rooms: self.rooms,
            rows,
            gold_positions: self.gold_positions,
            monster_slots: self.monster_slots,
            monsters: self.monsters,
            level_objects: self.level_objects,
            traps: self.traps,
            stairs: self.stairs,
            hero: self.hero,
            ntraps: self.ntraps,
            no_food: self.no_food,
            rng_seed: self.rng.seed,
            passages: if include_passages {
                self.passages
            } else {
                Vec::new()
            },
            hidden_passages,
            passage_numbers,
            source_map_cells,
        }
    }

    fn put_things(&mut self) {
        if self.amulet && self.level < self.max_level {
            return;
        }
        if self.rng.rnd(TREAS_ROOM) == 0 {
            self.treas_room();
        }
        for _ in 0..MAXOBJ {
            if self.rng.rnd(100) < 36 {
                let mut obj = self.new_thing();
                obj.pos = self.find_floor(None, 0, false);
                self.set_ch(obj.pos.y, obj.pos.x, obj.obj_type.chars().next().unwrap());
                self.attach_object(obj);
            }
        }
        if self.level >= AMULETLEVEL as i32 && !self.amulet {
            let mut obj = self.new_item();
            obj.hplus = 0;
            obj.dplus = 0;
            obj.arm = 11;
            obj.obj_type = AMULET.to_string();
            obj.pos = self.find_floor(None, 0, false);
            self.set_ch(obj.pos.y, obj.pos.x, AMULET);
            self.attach_object(obj);
        }
    }

    fn treas_room(&mut self) {
        let room_index = self.rnd_room();
        let room = self.rooms[room_index].clone();
        let mut spots = (room.max.y - 2) * (room.max.x - 2) - MINTREAS;
        if spots > MAXTREAS - MINTREAS {
            spots = MAXTREAS - MINTREAS;
        }
        let num_monst = self.rng.rnd(spots) + MINTREAS;
        for _ in 0..num_monst {
            let coord = self.find_floor(Some(room_index), 2 * MAXTRIES, false);
            let mut obj = self.new_thing();
            obj.pos = coord;
            self.set_ch(coord.y, coord.x, obj.obj_type.chars().next().unwrap());
            self.attach_object(obj);
        }
        let mut monster_count = self.rng.rnd(spots) + MINTREAS;
        if monster_count < num_monst + 2 {
            monster_count = num_monst + 2;
        }
        spots = (room.max.y - 2) * (room.max.x - 2);
        if monster_count > spots {
            monster_count = spots;
        }
        self.level += 1;
        for _ in 0..monster_count {
            if let Some(coord) = self.try_find_floor(Some(room_index), MAXTRIES, true) {
                self.place_mut(coord.y, coord.x).monst = true;
                self.monster_slots.push(coord);
                let monster_type = self.randmonster(false);
                let mut monster = self.new_monster(monster_type, coord);
                monster.flags |= ISMEAN;
                self.give_pack(&mut monster);
                self.monsters.insert(0, monster);
            }
        }
        self.level -= 1;
    }

    fn place_traps(&mut self) {
        if self.rng.rnd(10) >= self.level {
            return;
        }
        self.ntraps = self.rng.rnd(self.level / 4) + 1;
        if self.ntraps > MAXTRAPS as i32 {
            self.ntraps = MAXTRAPS as i32;
        }
        for _ in 0..self.ntraps {
            let coord = loop {
                let candidate = self.find_floor(None, 0, false);
                if self.place(candidate.y, candidate.x).ch == FLOOR {
                    break candidate;
                }
            };
            let trap_kind = self.rng.rnd(NTRAPS);
            let place = self.place_mut(coord.y, coord.x);
            place.flags &= !F_REAL;
            place.flags |= trap_kind as u8;
            self.traps.push(SourceTrap {
                pos: coord,
                kind: trap_kind,
            });
        }
    }

    fn place_stairs(&mut self) {
        self.stairs = self.find_floor(None, 0, false);
        self.set_ch(self.stairs.y, self.stairs.x, STAIRS);
    }

    fn assign_monster_rooms(&mut self) {}

    fn place_hero(&mut self) {
        self.hero = self.find_floor(None, 0, true);
    }

    fn do_passages(&mut self) {
        let connections = [
            [false, true, false, true, false, false, false, false, false],
            [true, false, true, false, true, false, false, false, false],
            [false, true, false, false, false, true, false, false, false],
            [true, false, false, false, true, false, true, false, false],
            [false, true, false, true, false, true, false, true, false],
            [false, false, true, false, true, false, false, false, true],
            [false, false, false, true, false, false, false, true, false],
            [false, false, false, false, true, false, true, false, true],
            [false, false, false, false, false, true, false, true, false],
        ];
        let mut isconn = [[false; MAXROOMS]; MAXROOMS];
        let mut ingraph = [false; MAXROOMS];
        let mut roomcount = 1;
        let mut r1 = self.rng.rnd(MAXROOMS as i32) as usize;
        ingraph[r1] = true;
        while roomcount < MAXROOMS {
            let mut count = 0;
            let mut r2 = 0;
            for index in 0..MAXROOMS {
                if connections[r1][index] && !ingraph[index] {
                    count += 1;
                    if self.rng.rnd(count) == 0 {
                        r2 = index;
                    }
                }
            }
            if count == 0 {
                loop {
                    r1 = self.rng.rnd(MAXROOMS as i32) as usize;
                    if ingraph[r1] {
                        break;
                    }
                }
            } else {
                ingraph[r2] = true;
                self.conn(r1, r2);
                isconn[r1][r2] = true;
                isconn[r2][r1] = true;
                roomcount += 1;
            }
        }
        let mut extra = self.rng.rnd(5);
        while extra > 0 {
            r1 = self.rng.rnd(MAXROOMS as i32) as usize;
            let mut count = 0;
            let mut r2 = 0;
            for index in 0..MAXROOMS {
                if connections[r1][index] && !isconn[r1][index] {
                    count += 1;
                    if self.rng.rnd(count) == 0 {
                        r2 = index;
                    }
                }
            }
            if count != 0 {
                self.conn(r1, r2);
                isconn[r1][r2] = true;
                isconn[r2][r1] = true;
            }
            extra -= 1;
        }
        self.passnum();
    }

    fn conn(&mut self, r1: usize, r2: usize) {
        let (room_index, direc) = if r1 < r2 {
            (r1, if r1 + 1 == r2 { 'r' } else { 'd' })
        } else {
            (r2, if r2 + 1 == r1 { 'r' } else { 'd' })
        };
        let source = self.rooms[room_index].clone();
        let target_index;
        let target;
        let delta;
        let mut start;
        let mut end;
        let distance;
        let turn_delta;
        let mut turn_distance;
        if direc == 'd' {
            target_index = room_index + 3;
            target = self.rooms[target_index].clone();
            delta = Coord { y: 1, x: 0 };
            start = Coord {
                y: source.pos.y,
                x: source.pos.x,
            };
            end = Coord {
                y: target.pos.y,
                x: target.pos.x,
            };
            if source.flags & ISGONE == 0 {
                loop {
                    start.x = source.pos.x + self.rng.rnd(source.max.x - 2) + 1;
                    start.y = source.pos.y + source.max.y - 1;
                    if source.flags & ISMAZE == 0 || self.flags(start.y, start.x) & F_PASS != 0 {
                        break;
                    }
                }
            }
            if target.flags & ISGONE == 0 {
                loop {
                    end.x = target.pos.x + self.rng.rnd(target.max.x - 2) + 1;
                    if target.flags & ISMAZE == 0 || self.flags(end.y, end.x) & F_PASS != 0 {
                        break;
                    }
                }
            }
            distance = (start.y - end.y).abs() - 1;
            turn_delta = Coord {
                y: 0,
                x: if start.x < end.x { 1 } else { -1 },
            };
            turn_distance = (start.x - end.x).abs();
        } else {
            target_index = room_index + 1;
            target = self.rooms[target_index].clone();
            delta = Coord { y: 0, x: 1 };
            start = Coord {
                y: source.pos.y,
                x: source.pos.x,
            };
            end = Coord {
                y: target.pos.y,
                x: target.pos.x,
            };
            if source.flags & ISGONE == 0 {
                loop {
                    start.x = source.pos.x + source.max.x - 1;
                    start.y = source.pos.y + self.rng.rnd(source.max.y - 2) + 1;
                    if source.flags & ISMAZE == 0 || self.flags(start.y, start.x) & F_PASS != 0 {
                        break;
                    }
                }
            }
            if target.flags & ISGONE == 0 {
                loop {
                    end.y = target.pos.y + self.rng.rnd(target.max.y - 2) + 1;
                    if target.flags & ISMAZE == 0 || self.flags(end.y, end.x) & F_PASS != 0 {
                        break;
                    }
                }
            }
            distance = (start.x - end.x).abs() - 1;
            turn_delta = Coord {
                y: if start.y < end.y { 1 } else { -1 },
                x: 0,
            };
            turn_distance = (start.y - end.y).abs();
        }
        let turn_spot = self.rng.rnd(distance - 1) + 1;
        if source.flags & ISGONE == 0 {
            self.door(room_index, start);
        } else {
            self.putpass(start);
        }
        if target.flags & ISGONE == 0 {
            self.door(target_index, end);
        } else {
            self.putpass(end);
        }
        let mut curr = start;
        let mut remaining = distance;
        while remaining > 0 {
            curr.x += delta.x;
            curr.y += delta.y;
            if remaining == turn_spot {
                while turn_distance > 0 {
                    self.putpass(curr);
                    curr.x += turn_delta.x;
                    curr.y += turn_delta.y;
                    turn_distance -= 1;
                }
            }
            self.putpass(curr);
            remaining -= 1;
        }
    }

    fn door(&mut self, room_index: usize, coord: Coord) {
        self.rooms[room_index].exits.push(coord);
        self.rooms[room_index].nexits = self.rooms[room_index].exits.len();
        if self.rooms[room_index].flags & ISMAZE != 0 {
            return;
        }
        let room = self.rooms[room_index].clone();
        let secret = self.rng.rnd(10) + 1 < self.level && self.rng.rnd(5) == 0;
        let place = self.place_mut(coord.y, coord.x);
        if secret {
            if coord.y == room.pos.y || coord.y == room.pos.y + room.max.y - 1 {
                place.ch = '-';
            } else {
                place.ch = '|';
            }
            place.flags &= !F_REAL;
        } else {
            place.ch = DOOR;
        }
    }

    fn passnum(&mut self) {
        self.pnum = 0;
        self.newpnum = false;
        for passage in &mut self.passages {
            passage.exits.clear();
            passage.nexits = 0;
        }
        for room_index in 0..self.rooms.len() {
            let exits = self.rooms[room_index].exits.clone();
            for exit_coord in exits {
                self.newpnum = true;
                self.numpass(exit_coord.y, exit_coord.x);
            }
        }
    }

    fn numpass(&mut self, y: i32, x: i32) {
        if x >= NUMCOLS as i32 || x < 0 || y >= NUMLINES as i32 || y <= 0 {
            return;
        }
        if self.flags(y, x) & F_PNUM != 0 {
            return;
        }
        if self.newpnum {
            self.pnum += 1;
            self.newpnum = false;
        }
        let ch = self.place(y, x).ch;
        let flags = self.flags(y, x);
        if ch == DOOR || (flags & F_REAL == 0 && matches!(ch, '|' | '-')) {
            let passage = &mut self.passages[self.pnum as usize];
            passage.exits.push(Coord { y, x });
            passage.nexits = passage.exits.len();
        } else if flags & F_PASS == 0 {
            return;
        }
        self.place_mut(y, x).flags |= self.pnum as u8;
        self.numpass(y + 1, x);
        self.numpass(y - 1, x);
        self.numpass(y, x + 1);
        self.numpass(y, x - 1);
    }

    fn randmonster(&mut self, wander: bool) -> char {
        if wander {
            panic!("wandering monster table is not needed for this source slice");
        }
        loop {
            let mut monster_index = self.level + (self.rng.rnd(10) - 6);
            if monster_index < 0 {
                monster_index = self.rng.rnd(5);
            }
            if monster_index > 25 {
                monster_index = self.rng.rnd(5) + 21;
            }
            let monster = LVL_MONS[monster_index as usize];
            if monster != '\0' {
                return monster;
            }
        }
    }

    fn new_monster(&mut self, monster_type: char, pos: Coord) -> SourceMonster {
        let lev_add = (self.level - 26).max(0);
        let monster_index = (monster_type as u8 - b'A') as usize;
        let monster_level = MONSTER_LEVELS[monster_index] + lev_add;
        let hp = self.rng.roll(monster_level, 8);
        let disguise = if monster_type == 'X' {
            self.rnd_thing()
        } else {
            monster_type
        };
        let mut flags = MONSTER_FLAGS[monster_index];
        if self.level > 29 {
            flags |= ISHASTE;
        }
        SourceMonster {
            monster_type: monster_type.to_string(),
            pos,
            level: monster_level,
            hp,
            disguise: disguise.to_string(),
            flags,
            pack: Vec::new(),
        }
    }

    fn give_pack(&mut self, monster: &mut SourceMonster) {
        let monster_index = (monster.monster_type.as_bytes()[0] - b'A') as usize;
        if self.level >= self.max_level && self.rng.rnd(100) < MONSTER_CARRY[monster_index] {
            monster.pack.insert(0, self.new_thing());
        }
    }

    fn rnd_thing(&mut self) -> char {
        if self.level >= 26 {
            RND_THING_LIST[self.rng.rnd(RND_THING_LIST.len() as i32) as usize]
        } else {
            RND_THING_LIST[self.rng.rnd(RND_THING_LIST.len() as i32 - 1) as usize]
        }
    }

    fn new_thing(&mut self) -> SourceObject {
        let mut obj = self.new_item();
        obj.hplus = 0;
        obj.dplus = 0;
        obj.arm = 11;
        obj.count = 1;
        obj.group = 0;
        obj.flags = 0;
        let object_kind = if self.no_food > 3 {
            2
        } else {
            self.pick_one(&THING_PROBS)
        };
        match object_kind {
            0 => {
                obj.obj_type = POTION.to_string();
                obj.which = self.pick_one(&POTION_PROBS);
            }
            1 => {
                obj.obj_type = SCROLL.to_string();
                obj.which = self.pick_one(&SCROLL_PROBS);
            }
            2 => {
                obj.obj_type = FOOD.to_string();
                self.no_food = 0;
                obj.which = if self.rng.rnd(10) != 0 { 0 } else { 1 };
            }
            3 => {
                let which = self.pick_one(&WEAPON_PROBS);
                self.init_weapon(&mut obj, which);
                let roll = self.rng.rnd(100);
                if roll < 10 {
                    obj.flags |= ISCURSED;
                    obj.hplus -= self.rng.rnd(3) + 1;
                } else if roll < 15 {
                    obj.hplus += self.rng.rnd(3) + 1;
                }
            }
            4 => {
                obj.obj_type = ARMOR.to_string();
                obj.which = self.pick_one(&ARMOR_PROBS);
                obj.arm = A_CLASS[obj.which as usize];
                let roll = self.rng.rnd(100);
                if roll < 20 {
                    obj.flags |= ISCURSED;
                    obj.arm += self.rng.rnd(3) + 1;
                } else if roll < 28 {
                    obj.arm -= self.rng.rnd(3) + 1;
                }
            }
            5 => {
                obj.obj_type = RING.to_string();
                obj.which = self.pick_one(&RING_PROBS);
                if matches!(obj.which, R_ADDSTR | R_PROTECT | R_ADDHIT | R_ADDDAM) {
                    obj.arm = self.rng.rnd(3);
                    if obj.arm == 0 {
                        obj.arm = -1;
                        obj.flags |= ISCURSED;
                    }
                } else if matches!(obj.which, R_AGGR | R_TELEPORT) {
                    obj.flags |= ISCURSED;
                }
            }
            6 => {
                obj.obj_type = STICK.to_string();
                obj.which = self.pick_one(&STICK_PROBS);
                obj.arm = if obj.which == WS_LIGHT {
                    self.rng.rnd(10) + 10
                } else {
                    self.rng.rnd(5) + 3
                };
            }
            _ => panic!("unknown Rogue object kind {}", object_kind),
        }
        obj
    }

    fn new_item(&self) -> SourceObject {
        SourceObject {
            count: 0,
            arm: 0,
            ..SourceObject::default()
        }
    }

    fn attach_object(&mut self, obj: SourceObject) {
        self.level_objects.insert(0, obj);
    }

    fn pick_one(&mut self, probabilities: &[i32]) -> i32 {
        let value = self.rng.rnd(100);
        for (index, probability) in probabilities.iter().enumerate() {
            if value < *probability {
                return index as i32;
            }
        }
        0
    }

    fn init_weapon(&mut self, obj: &mut SourceObject, which: i32) {
        obj.obj_type = WEAPON.to_string();
        obj.which = which;
        obj.flags = INIT_WEAPON_FLAGS[which as usize];
        obj.hplus = 0;
        obj.dplus = 0;
        if which == DAGGER {
            obj.count = self.rng.rnd(4) + 2;
            obj.group = self.weapon_group;
            self.weapon_group += 1;
        } else if obj.flags & ISMANY != 0 {
            obj.count = self.rng.rnd(8) + 8;
            obj.group = self.weapon_group;
            self.weapon_group += 1;
        } else {
            obj.count = 1;
            obj.group = 0;
        }
    }

    fn rnd_room(&mut self) -> usize {
        loop {
            let room_index = self.rng.rnd(MAXROOMS as i32) as usize;
            if self.rooms[room_index].flags & ISGONE == 0 {
                return room_index;
            }
        }
    }

    fn draw_room(&mut self, room_index: usize) {
        if self.rooms[room_index].flags & ISMAZE != 0 {
            self.do_maze(room_index);
            return;
        }
        let room = self.rooms[room_index].clone();
        self.vert(room_index, room.pos.x);
        self.vert(room_index, room.pos.x + room.max.x - 1);
        self.horiz(room_index, room.pos.y);
        self.horiz(room_index, room.pos.y + room.max.y - 1);
        for y in room.pos.y + 1..room.pos.y + room.max.y - 1 {
            for x in room.pos.x + 1..room.pos.x + room.max.x - 1 {
                self.set_ch(y, x, FLOOR);
            }
        }
    }

    fn vert(&mut self, room_index: usize, startx: i32) {
        let room = self.rooms[room_index].clone();
        for y in room.pos.y + 1..=room.max.y + room.pos.y - 1 {
            self.set_ch(y, startx, '|');
        }
    }

    fn horiz(&mut self, room_index: usize, starty: i32) {
        let room = self.rooms[room_index].clone();
        for x in room.pos.x..=room.pos.x + room.max.x - 1 {
            self.set_ch(starty, x, '-');
        }
    }

    fn do_maze(&mut self, room_index: usize) {
        let room = self.rooms[room_index].clone();
        self.maze_maxy = room.max.y;
        self.maze_maxx = room.max.x;
        self.maze_starty = room.pos.y;
        self.maze_startx = room.pos.x;
        let starty = (self.rng.rnd(room.max.y) / 2) * 2;
        let startx = (self.rng.rnd(room.max.x) / 2) * 2;
        self.putpass(Coord {
            y: starty + self.maze_starty,
            x: startx + self.maze_startx,
        });
        self.dig(starty, startx);
    }

    fn dig(&mut self, y: i32, x: i32) {
        let deltas = [
            Coord { y: 2, x: 0 },
            Coord { y: -2, x: 0 },
            Coord { y: 0, x: 2 },
            Coord { y: 0, x: -2 },
        ];
        loop {
            let mut count = 0;
            let mut nexty = 0;
            let mut nextx = 0;
            for delta in deltas {
                let newy = y + delta.y;
                let newx = x + delta.x;
                if newy < 0 || newy > self.maze_maxy || newx < 0 || newx > self.maze_maxx {
                    continue;
                }
                if self.flags(newy + self.maze_starty, newx + self.maze_startx) & F_PASS != 0 {
                    continue;
                }
                count += 1;
                if self.rng.rnd(count) == 0 {
                    nexty = newy;
                    nextx = newx;
                }
            }
            if count == 0 {
                return;
            }
            let mid = if nexty == y {
                Coord {
                    y: y + self.maze_starty,
                    x: nextx + self.maze_startx + if nextx - x < 0 { 1 } else { -1 },
                }
            } else {
                Coord {
                    y: nexty + self.maze_starty + if nexty - y < 0 { 1 } else { -1 },
                    x: x + self.maze_startx,
                }
            };
            self.putpass(mid);
            self.putpass(Coord {
                y: nexty + self.maze_starty,
                x: nextx + self.maze_startx,
            });
            self.dig(nexty, nextx);
        }
    }

    fn putpass(&mut self, coord: Coord) {
        let level = self.level;
        let secret = self.rng.rnd(10) + 1 < level && self.rng.rnd(40) == 0;
        let place = self.place_mut(coord.y, coord.x);
        place.flags |= F_PASS;
        if secret {
            place.flags &= !F_REAL;
        } else {
            place.ch = PASSAGE;
        }
    }

    fn rnd_pos(&mut self, room_index: usize) -> Coord {
        let room = self.rooms[room_index].clone();
        let x = room.pos.x + self.rng.rnd(room.max.x - 2) + 1;
        let y = room.pos.y + self.rng.rnd(room.max.y - 2) + 1;
        Coord { y, x }
    }

    fn find_floor(&mut self, room_index: Option<usize>, limit: i32, monst: bool) -> Coord {
        self.try_find_floor(room_index, limit, monst)
            .unwrap_or_else(|| panic!("Rogue find_floor limit exhausted"))
    }

    fn try_find_floor(
        &mut self,
        room_index: Option<usize>,
        limit: i32,
        monst: bool,
    ) -> Option<Coord> {
        let pickroom = room_index.is_none();
        let mut current_room = room_index;
        let mut count = limit;
        let mut compchar = current_room.map(|index| {
            if self.rooms[index].flags & ISMAZE != 0 {
                PASSAGE
            } else {
                FLOOR
            }
        });
        loop {
            if limit != 0 && count == 0 {
                return None;
            }
            if limit != 0 {
                count -= 1;
            }
            if pickroom {
                let index = self.rnd_room();
                current_room = Some(index);
                compchar = Some(if self.rooms[index].flags & ISMAZE != 0 {
                    PASSAGE
                } else {
                    FLOOR
                });
            }
            let coord = self.rnd_pos(current_room.unwrap());
            let place = self.place(coord.y, coord.x);
            if monst {
                if !place.monst && step_ok(place.ch) {
                    return Some(coord);
                }
            } else if place.ch == compchar.unwrap() {
                return Some(coord);
            }
        }
    }

    fn rows(&self) -> Vec<String> {
        self.places
            .iter()
            .take(NUMLINES)
            .map(|row| row.iter().map(|place| place.ch).collect::<String>())
            .collect()
    }

    fn place(&self, y: i32, x: i32) -> &Place {
        &self.places[y as usize][x as usize]
    }

    fn place_mut(&mut self, y: i32, x: i32) -> &mut Place {
        &mut self.places[y as usize][x as usize]
    }

    fn flags(&self, y: i32, x: i32) -> u8 {
        self.place(y, x).flags
    }

    fn set_ch(&mut self, y: i32, x: i32, ch: char) {
        self.place_mut(y, x).ch = ch;
    }
}
