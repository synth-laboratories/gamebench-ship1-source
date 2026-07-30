use crate::{RogueRng, ARMOR, DOOR, FLOOR, PASSAGE, POTION, SCROLL, STAIRS, TRAP, WEAPON};
use serde_json::{json, Value};

const R_OR_S: i32 = -2;

const F_PASS: i32 = 0x80;
const F_SEEN: i32 = 0x40;
const F_REAL: i32 = 0x10;

const ISCURSED: i32 = 0o000001;
const ISPROT: i32 = 0o000040;

const CANHUH: i32 = 0o000001;
const ISHELD: i32 = 0o000400;
const ISRUN: i32 = 0o020000;
const SEEMONST: i32 = 0o040000;

const S_CONFUSE: i32 = 0;
const S_MAP: i32 = 1;
const S_HOLD: i32 = 2;
const S_SLEEP: i32 = 3;
const S_ARMOR: i32 = 4;
const S_ID_POTION: i32 = 5;
const S_ID_SCROLL: i32 = 6;
const S_ID_WEAPON: i32 = 7;
const S_ID_ARMOR: i32 = 8;
const S_ID_R_OR_S: i32 = 9;
const S_SCARE: i32 = 10;
const S_FDET: i32 = 11;
const S_TELEP: i32 = 12;
const S_ENCH: i32 = 13;
const S_CREATE: i32 = 14;
const S_REMOVE: i32 = 15;
const S_AGGR: i32 = 16;
const S_PROTECT: i32 = 17;
const MAXSCROLLS: usize = 18;

#[derive(Clone)]
pub struct ScrollObject {
    pub obj_type: char,
    pub which: i32,
    pub count: i32,
}

#[derive(Clone)]
pub struct ScrollItem {
    pub obj_type: char,
    pub which: i32,
    pub flags: i32,
    pub arm: i32,
    pub hplus: i32,
    pub dplus: i32,
}

#[derive(Clone)]
pub struct ScrollMonster {
    pub monster_type: char,
    pub flags: i32,
    pub oldch: char,
}

#[derive(Clone)]
pub struct MapCell {
    pub ch: char,
    pub flags: i32,
    pub monster: Option<ScrollMonster>,
}

pub struct ScrollWorld {
    pub rng: RogueRng,
    pub player_flags: i32,
    pub no_command: i32,
    pub current_weapon_is_obj: bool,
    pub current_weapon: Option<ScrollItem>,
    pub current_armor: Option<ScrollItem>,
    pub left_ring: Option<ScrollItem>,
    pub right_ring: Option<ScrollItem>,
    pub nearby_monsters: Vec<ScrollMonster>,
    pub create_candidates: i32,
    pub food_count: i32,
    pub teleport_room_changed: bool,
    pub map_cells: Vec<MapCell>,
    pub scr_known: Vec<bool>,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_scrolls_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_scrolls.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn read_scroll(world: &mut ScrollWorld, obj: Option<ScrollObject>) {
    let Some(obj) = obj else {
        return;
    };
    if obj.obj_type != SCROLL {
        world.markers.push("nothing_to_read".to_string());
        return;
    }
    if world.current_weapon_is_obj {
        world.current_weapon_is_obj = false;
        world.markers.push("unwield_scroll".to_string());
    }
    let discardit = obj.count == 1;
    world.markers.push("leave_pack".to_string());
    match obj.which {
        S_CONFUSE => {
            world.player_flags |= CANHUH;
            world.markers.push("hands_glow".to_string());
        }
        S_ARMOR => {
            if let Some(armor) = &mut world.current_armor {
                armor.arm -= 1;
                armor.flags &= !ISCURSED;
                world.markers.push("armor_glows".to_string());
            }
        }
        S_HOLD => {
            let mut held = 0;
            for monster in &mut world.nearby_monsters {
                if monster.flags & ISRUN != 0 {
                    monster.flags &= !ISRUN;
                    monster.flags |= ISHELD;
                    held += 1;
                }
            }
            if held != 0 {
                world.scr_known[S_HOLD as usize] = true;
                world.markers.push(format!("monsters_freeze:{held}"));
            } else {
                world.markers.push("loss".to_string());
            }
        }
        S_SLEEP => {
            world.scr_known[S_SLEEP as usize] = true;
            let sleep_time = world.rng.spread(5);
            let sleep_roll = world.rng.rnd(sleep_time);
            world
                .trace
                .insert("sleep_time".to_string(), json!(sleep_time));
            world
                .trace
                .insert("sleep_roll".to_string(), json!(sleep_roll));
            world.no_command += sleep_roll + 4;
            world.player_flags &= !ISRUN;
            world.markers.push("fall_asleep".to_string());
        }
        S_CREATE => create_monster(world),
        S_ID_POTION | S_ID_SCROLL | S_ID_WEAPON | S_ID_ARMOR | S_ID_R_OR_S => {
            world.scr_known[obj.which as usize] = true;
            let id_type = match obj.which {
                S_ID_POTION => POTION.to_string(),
                S_ID_SCROLL => SCROLL.to_string(),
                S_ID_WEAPON => WEAPON.to_string(),
                S_ID_ARMOR => ARMOR.to_string(),
                _ => R_OR_S.to_string(),
            };
            world.markers.push(format!("id_scroll:{}", obj.which));
            world.markers.push(format!("whatis:{id_type}"));
        }
        S_MAP => {
            world.scr_known[S_MAP as usize] = true;
            world.markers.push("map_msg".to_string());
            magic_map(world);
        }
        S_FDET => {
            if world.food_count > 0 {
                world.scr_known[S_FDET as usize] = true;
                world
                    .markers
                    .push(format!("show_food:{}", world.food_count));
            } else {
                world.markers.push("nose_tingles".to_string());
            }
        }
        S_TELEP => {
            world.markers.push("teleport".to_string());
            if world.teleport_room_changed {
                world.scr_known[S_TELEP as usize] = true;
            }
        }
        S_ENCH => {
            if let Some(weapon) = &mut world.current_weapon {
                if weapon.obj_type == WEAPON {
                    weapon.flags &= !ISCURSED;
                    if world.rng.rnd(2) == 0 {
                        weapon.hplus += 1;
                        world.trace.insert("enchanted".to_string(), json!("hplus"));
                    } else {
                        weapon.dplus += 1;
                        world.trace.insert("enchanted".to_string(), json!("dplus"));
                    }
                    world.markers.push("weapon_glows".to_string());
                } else {
                    world.markers.push("loss".to_string());
                }
            } else {
                world.markers.push("loss".to_string());
            }
        }
        S_SCARE => world.markers.push("laughter".to_string()),
        S_REMOVE => {
            uncurse(&mut world.current_armor);
            uncurse(&mut world.current_weapon);
            uncurse(&mut world.left_ring);
            uncurse(&mut world.right_ring);
            world.markers.push("remove_curse".to_string());
        }
        S_AGGR => {
            world.markers.push("aggravate".to_string());
            world.markers.push("hum".to_string());
        }
        S_PROTECT => {
            if let Some(armor) = &mut world.current_armor {
                armor.flags |= ISPROT;
                world.markers.push("protect_armor".to_string());
            } else {
                world.markers.push("loss".to_string());
            }
        }
        _ => {
            world.markers.push("puzzling".to_string());
            return;
        }
    }
    world.markers.push("look:true".to_string());
    world.markers.push("status".to_string());
    world.markers.push(format!("call_it:{}", obj.which));
    if discardit {
        world.markers.push("discard".to_string());
    }
}

fn create_monster(world: &mut ScrollWorld) {
    let mut selected = -1;
    for index in 0..world.create_candidates {
        if world.rng.rnd(index + 1) == 0 {
            selected = index;
        }
    }
    if selected < 0 {
        world.markers.push("faint_cry".to_string());
    } else {
        world
            .trace
            .insert("create_selected".to_string(), json!(selected));
        world.markers.push("new_monster".to_string());
    }
}

fn magic_map(world: &mut ScrollWorld) {
    let mut draw_count = 0;
    let mut oldch_count = 0;
    let player_sees_monsters = world.player_flags & SEEMONST != 0;
    for cell in &mut world.map_cells {
        let display = apply_map_cell(cell);
        if display != ' ' {
            if let Some(monster) = &mut cell.monster {
                monster.oldch = display;
                oldch_count += 1;
            }
            if cell.monster.is_none() || !player_sees_monsters {
                draw_count += 1;
            }
        }
    }
    world
        .trace
        .insert("map_draw".to_string(), json!(draw_count));
    world
        .trace
        .insert("map_oldch".to_string(), json!(oldch_count));
}

fn apply_map_cell(cell: &mut MapCell) -> char {
    let ch = cell.ch;
    if matches!(ch, DOOR | STAIRS) {
        return ch;
    }
    if matches!(ch, '-' | '|') {
        if cell.flags & F_REAL == 0 {
            cell.ch = DOOR;
            cell.flags |= F_REAL;
            return DOOR;
        }
        return ch;
    }
    if ch == ' ' {
        if cell.flags & F_REAL != 0 {
            return map_default(cell);
        }
        cell.flags |= F_REAL;
        cell.ch = PASSAGE;
    }
    if cell.ch == PASSAGE {
        if cell.flags & F_REAL == 0 {
            cell.ch = PASSAGE;
        }
        cell.flags |= F_SEEN | F_REAL;
        return PASSAGE;
    }
    if ch == FLOOR {
        if cell.flags & F_REAL != 0 {
            return ' ';
        }
        cell.ch = TRAP;
        cell.flags |= F_SEEN | F_REAL;
        return TRAP;
    }
    map_default(cell)
}

fn map_default(cell: &mut MapCell) -> char {
    if cell.flags & F_PASS != 0 {
        if cell.flags & F_REAL == 0 {
            cell.ch = PASSAGE;
        }
        cell.flags |= F_SEEN | F_REAL;
        PASSAGE
    } else {
        ' '
    }
}

fn uncurse(item: &mut Option<ScrollItem>) {
    if let Some(item) = item {
        item.flags &= !ISCURSED;
    }
}

fn run_case(case: Case) -> Value {
    let mut world = world_for(&case);
    read_scroll(&mut world, case.obj.clone());
    json!({"name": case.name, "seed": case.seed, "world": world_json(&world)})
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    obj: Option<ScrollObject>,
    player_flags: i32,
    no_command: i32,
    current_weapon_is_obj: bool,
    current_weapon: Option<ScrollItem>,
    current_armor: Option<ScrollItem>,
    left_ring: Option<ScrollItem>,
    right_ring: Option<ScrollItem>,
    nearby_monsters: Vec<ScrollMonster>,
    create_candidates: i32,
    food_count: i32,
    teleport_room_changed: bool,
    map_cells: Vec<MapCell>,
    scr_known: Vec<bool>,
}

fn base_case(name: &'static str, seed: i32) -> Case {
    Case {
        name,
        seed,
        obj: None,
        player_flags: 0,
        no_command: 0,
        current_weapon_is_obj: false,
        current_weapon: None,
        current_armor: None,
        left_ring: None,
        right_ring: None,
        nearby_monsters: Vec::new(),
        create_candidates: 0,
        food_count: 0,
        teleport_room_changed: false,
        map_cells: Vec::new(),
        scr_known: vec![false; MAXSCROLLS],
    }
}

impl Case {
    fn obj(mut self, obj: ScrollObject) -> Self {
        self.obj = Some(obj);
        self
    }
    fn player_flags(mut self, flags: i32) -> Self {
        self.player_flags = flags;
        self
    }
    fn no_command(mut self, no_command: i32) -> Self {
        self.no_command = no_command;
        self
    }
    fn current_weapon_is_obj(mut self) -> Self {
        self.current_weapon_is_obj = true;
        self
    }
    fn current_weapon(mut self, item: ScrollItem) -> Self {
        self.current_weapon = Some(item);
        self
    }
    fn current_armor(mut self, item: ScrollItem) -> Self {
        self.current_armor = Some(item);
        self
    }
    fn left_ring(mut self, item: ScrollItem) -> Self {
        self.left_ring = Some(item);
        self
    }
    fn right_ring(mut self, item: ScrollItem) -> Self {
        self.right_ring = Some(item);
        self
    }
    fn nearby_monsters(mut self, monsters: Vec<ScrollMonster>) -> Self {
        self.nearby_monsters = monsters;
        self
    }
    fn create_candidates(mut self, count: i32) -> Self {
        self.create_candidates = count;
        self
    }
    fn food_count(mut self, count: i32) -> Self {
        self.food_count = count;
        self
    }
    fn teleport_room_changed(mut self, changed: bool) -> Self {
        self.teleport_room_changed = changed;
        self
    }
    fn map_cells(mut self, cells: Vec<MapCell>) -> Self {
        self.map_cells = cells;
        self
    }
}

fn cases() -> Vec<Case> {
    vec![
        base_case("non_scroll_rejected", 1).obj(scroll_object('!', 0, 1)),
        base_case("confuse_sets_canhuh", 1).obj(scroll(S_CONFUSE, 1)),
        base_case("armor_enchants_uncurses", 1)
            .current_armor(item(ARMOR).arm(5).flags(ISCURSED))
            .obj(scroll(S_ARMOR, 1)),
        base_case("hold_two_monsters", 1)
            .nearby_monsters(vec![
                monster('K').flags(ISRUN),
                monster('O').flags(ISRUN),
                monster('B'),
            ])
            .obj(scroll(S_HOLD, 1)),
        base_case("hold_none", 1)
            .nearby_monsters(vec![monster('K')])
            .obj(scroll(S_HOLD, 1)),
        base_case("sleep_stops_running", 1)
            .player_flags(ISRUN)
            .no_command(2)
            .obj(scroll(S_SLEEP, 1)),
        base_case("create_no_space", 1)
            .create_candidates(0)
            .obj(scroll(S_CREATE, 1)),
        base_case("create_selects_space", 1)
            .create_candidates(4)
            .obj(scroll(S_CREATE, 1)),
        base_case("id_potion", 1).obj(scroll(S_ID_POTION, 1)),
        base_case("id_ring_or_stick", 1).obj(scroll(S_ID_R_OR_S, 1)),
        base_case("magic_map_cells", 1)
            .map_cells(vec![
                map_case_cell(DOOR, 0, None),
                map_case_cell('-', 0, None),
                map_case_cell(' ', 0, None),
                map_case_cell(PASSAGE, 0, None),
                map_case_cell(FLOOR, 0, Some(monster('K'))),
                map_case_cell(FLOOR, F_REAL, None),
                map_case_cell('x', F_PASS, None),
            ])
            .obj(scroll(S_MAP, 1)),
        base_case("food_detect_found", 1)
            .food_count(2)
            .obj(scroll(S_FDET, 1)),
        base_case("food_detect_none", 1)
            .food_count(0)
            .obj(scroll(S_FDET, 1)),
        base_case("teleport_changes_room", 1)
            .teleport_room_changed(true)
            .obj(scroll(S_TELEP, 1)),
        base_case("teleport_same_room", 1)
            .teleport_room_changed(false)
            .obj(scroll(S_TELEP, 1)),
        base_case("enchant_weapon_hplus", 1)
            .current_weapon(item(WEAPON).flags(ISCURSED))
            .obj(scroll(S_ENCH, 1)),
        base_case("enchant_no_weapon", 1).obj(scroll(S_ENCH, 1)),
        base_case("scare_laughter", 1).obj(scroll(S_SCARE, 1)),
        base_case("remove_curse_all", 1)
            .current_armor(item(ARMOR).flags(ISCURSED).arm(5))
            .current_weapon(item(WEAPON).flags(ISCURSED))
            .left_ring(item('=').flags(ISCURSED))
            .right_ring(item('=').flags(ISCURSED))
            .obj(scroll(S_REMOVE, 1)),
        base_case("aggravate", 1).obj(scroll(S_AGGR, 1)),
        base_case("protect_armor", 1)
            .current_armor(item(ARMOR).arm(5))
            .obj(scroll(S_PROTECT, 1)),
        base_case("protect_no_armor", 1).obj(scroll(S_PROTECT, 1)),
        base_case("unwield_scroll_multi_count", 1)
            .current_weapon_is_obj()
            .obj(scroll(S_CONFUSE, 2)),
    ]
}

fn scroll(which: i32, count: i32) -> ScrollObject {
    scroll_object(SCROLL, which, count)
}

fn scroll_object(obj_type: char, which: i32, count: i32) -> ScrollObject {
    ScrollObject {
        obj_type,
        which,
        count,
    }
}

fn item(obj_type: char) -> ScrollItem {
    ScrollItem {
        obj_type,
        which: 0,
        flags: 0,
        arm: 0,
        hplus: 0,
        dplus: 0,
    }
}

impl ScrollItem {
    fn flags(mut self, flags: i32) -> Self {
        self.flags = flags;
        self
    }
    fn arm(mut self, arm: i32) -> Self {
        self.arm = arm;
        self
    }
}

fn monster(monster_type: char) -> ScrollMonster {
    ScrollMonster {
        monster_type,
        flags: 0,
        oldch: ' ',
    }
}

impl ScrollMonster {
    fn flags(mut self, flags: i32) -> Self {
        self.flags = flags;
        self
    }
}

fn map_case_cell(ch: char, flags: i32, monster: Option<ScrollMonster>) -> MapCell {
    MapCell { ch, flags, monster }
}

fn world_for(case: &Case) -> ScrollWorld {
    ScrollWorld {
        rng: RogueRng::new(case.seed),
        player_flags: case.player_flags,
        no_command: case.no_command,
        current_weapon_is_obj: case.current_weapon_is_obj,
        current_weapon: case.current_weapon.clone(),
        current_armor: case.current_armor.clone(),
        left_ring: case.left_ring.clone(),
        right_ring: case.right_ring.clone(),
        nearby_monsters: case.nearby_monsters.clone(),
        create_candidates: case.create_candidates,
        food_count: case.food_count,
        teleport_room_changed: case.teleport_room_changed,
        map_cells: case.map_cells.clone(),
        scr_known: case.scr_known.clone(),
        markers: Vec::new(),
        trace: serde_json::Map::new(),
    }
}

fn item_json(item: &ScrollItem) -> Value {
    json!({"type": item.obj_type.to_string(), "which": item.which, "flags": item.flags, "arm": item.arm, "hplus": item.hplus, "dplus": item.dplus})
}

fn monster_json(monster: &ScrollMonster) -> Value {
    json!({"type": monster.monster_type.to_string(), "flags": monster.flags, "oldch": monster.oldch.to_string()})
}

fn map_cell_json(cell: &MapCell) -> Value {
    json!({"ch": cell.ch.to_string(), "flags": cell.flags, "monster": cell.monster.as_ref().map(monster_json)})
}

pub fn world_json(world: &ScrollWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "player_flags": world.player_flags,
        "no_command": world.no_command,
        "current_weapon_is_obj": world.current_weapon_is_obj,
        "current_weapon": world.current_weapon.as_ref().map(item_json),
        "current_armor": world.current_armor.as_ref().map(item_json),
        "left_ring": world.left_ring.as_ref().map(item_json),
        "right_ring": world.right_ring.as_ref().map(item_json),
        "nearby_monsters": world.nearby_monsters.iter().map(monster_json).collect::<Vec<_>>(),
        "map_cells": world.map_cells.iter().map(map_cell_json).collect::<Vec<_>>(),
        "scr_known": world.scr_known,
        "markers": world.markers,
        "trace": world.trace,
    })
}
