use crate::{RogueRng, ARMOR, DOOR, PASSAGE, TRAP, WEAPON};
use serde_json::{json, Value};

pub const F_SEEN: i32 = 0x40;
pub const F_REAL: i32 = 0x10;
pub const F_TMASK: i32 = 0x07;

pub const T_DOOR: i32 = 0;
pub const T_ARROW: i32 = 1;
pub const T_SLEEP: i32 = 2;
pub const T_BEAR: i32 = 3;
pub const T_TELEP: i32 = 4;
pub const T_DART: i32 = 5;
pub const T_RUST: i32 = 6;
pub const T_MYST: i32 = 7;

const VS_POISON: i32 = 0;

pub const ISBLIND: i32 = 0o000004;
pub const ISLEVIT: i32 = 0o000010;
pub const ISRUN: i32 = 0o020000;
pub const ISHALU: i32 = 0o004000;
const ISMISL: i32 = 0o000004;
const ISMANY: i32 = 0o000010;
pub const ISPROT: i32 = 0o000040;

const LEATHER: i32 = 0;

pub const R_ADDSTR: i32 = 1;
pub const R_SUSTSTR: i32 = 2;
pub const R_SUSTARM: i32 = 13;

const ARROW: i32 = 3;
const DAGGER: i32 = 4;

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
const RAINBOW: [&str; 27] = [
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

#[derive(Clone)]
pub struct TrapCell {
    pub ch: char,
    pub flags: i32,
}

#[derive(Clone)]
pub struct TrapStats {
    pub strength: i32,
    pub max_strength: i32,
    pub level: i32,
    pub arm: i32,
    pub hp: i32,
    pub max_hp: i32,
}

#[derive(Clone)]
pub struct TrapRing {
    pub which: i32,
    pub arm: i32,
}

#[derive(Clone)]
pub struct TrapArmor {
    pub obj_type: char,
    pub which: i32,
    pub arm: i32,
    pub flags: i32,
}

#[derive(Clone)]
pub struct TrapObject {
    pub obj_type: char,
    pub which: i32,
    pub count: i32,
    pub group: i32,
    pub flags: i32,
    pub y: i32,
    pub x: i32,
    pub init_count: i32,
}

pub struct TrapState {
    pub rng: RogueRng,
    pub level: i32,
    pub no_move: i32,
    pub no_command: i32,
    pub player_flags: i32,
    pub stats: TrapStats,
    pub cell: TrapCell,
    pub running: bool,
    pub count: bool,
    pub weapon_group: i32,
    pub hero_y: i32,
    pub hero_x: i32,
    pub left_ring: Option<TrapRing>,
    pub right_ring: Option<TrapRing>,
    pub armor: Option<TrapArmor>,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
    pub arrow: Option<TrapObject>,
    pub terminal: bool,
}

#[derive(Clone)]
struct TrapCase {
    name: &'static str,
    seed: i32,
    trap_kind: i32,
    level: i32,
    no_move: i32,
    no_command: i32,
    player_flags: i32,
    stats: TrapStats,
    weapon_group: i32,
    left_ring: Option<TrapRing>,
    right_ring: Option<TrapRing>,
    armor: Option<TrapArmor>,
}

pub fn source_traps_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_traps.v1",
        "trap_cases": trap_cases().into_iter().map(run_case).collect::<Vec<_>>(),
        "search_cases": search_cases().into_iter().map(run_search_case).collect::<Vec<_>>(),
    })
}

fn run_case(case: TrapCase) -> Value {
    let mut state = TrapState {
        rng: RogueRng::new(case.seed),
        level: case.level,
        no_move: case.no_move,
        no_command: case.no_command,
        player_flags: case.player_flags,
        stats: case.stats,
        cell: TrapCell {
            ch: TRAP,
            flags: F_REAL | case.trap_kind,
        },
        running: true,
        count: true,
        weapon_group: case.weapon_group,
        hero_y: 10,
        hero_x: 20,
        left_ring: case.left_ring,
        right_ring: case.right_ring,
        armor: case.armor,
        markers: Vec::new(),
        trace: serde_json::Map::new(),
        arrow: None,
        terminal: false,
    };
    let returned = be_trapped(&mut state);
    json!({"name": case.name, "seed": case.seed, "trap_kind": case.trap_kind, "returned": returned, "state": state_json(&state)})
}

pub fn be_trapped(state: &mut TrapState) -> Option<i32> {
    if state.player_flags & ISLEVIT != 0 {
        return Some(T_RUST);
    }

    state.running = false;
    state.count = false;
    state.cell.ch = TRAP;
    let trap_kind = state.cell.flags & F_TMASK;
    state.cell.flags |= F_SEEN;

    match trap_kind {
        T_DOOR => {
            state.level += 1;
            state.markers.push("new_level".to_string());
        }
        T_BEAR => {
            state.no_move += state.rng.spread(3);
        }
        T_MYST => {
            let mystery_roll = state.rng.rnd(11);
            state
                .trace
                .insert("mystery_roll".to_string(), json!(mystery_roll));
            if matches!(mystery_roll, 1 | 4 | 6 | 10) {
                let color_index = state.rng.rnd(RAINBOW.len() as i32);
                state
                    .trace
                    .insert("color_index".to_string(), json!(color_index));
                state
                    .trace
                    .insert("color".to_string(), json!(RAINBOW[color_index as usize]));
            }
        }
        T_SLEEP => {
            state.no_command += state.rng.spread(5);
            state.player_flags &= !ISRUN;
        }
        T_ARROW => {
            let swing_payload = swing(&mut state.rng, state.stats.level - 1, state.stats.arm, 1);
            state
                .trace
                .insert("arrow_swing".to_string(), swing_payload.clone());
            if swing_payload["hit"].as_bool().unwrap() {
                let damage = state.rng.roll(1, 6);
                state.stats.hp -= damage;
                state
                    .trace
                    .insert("arrow_damage".to_string(), json!(damage));
                if state.stats.hp <= 0 {
                    state.markers.push("death_a".to_string());
                    state.terminal = true;
                    return None;
                }
            } else {
                let mut arrow = init_weapon(state, ARROW);
                arrow.count = 1;
                arrow.y = state.hero_y;
                arrow.x = state.hero_x;
                state.arrow = Some(arrow);
                state.markers.push("fall_arrow".to_string());
            }
        }
        T_TELEP => {
            state.markers.push("teleport".to_string());
        }
        T_DART => {
            let swing_payload = swing(&mut state.rng, state.stats.level + 1, state.stats.arm, 1);
            state
                .trace
                .insert("dart_swing".to_string(), swing_payload.clone());
            if swing_payload["hit"].as_bool().unwrap() {
                let damage = state.rng.roll(1, 4);
                state.stats.hp -= damage;
                state.trace.insert("dart_damage".to_string(), json!(damage));
                if state.stats.hp <= 0 {
                    state.markers.push("death_d".to_string());
                    state.terminal = true;
                    return None;
                }
                if !is_wearing(state, R_SUSTSTR) {
                    let save_payload = save_throw(&mut state.rng, VS_POISON, state.stats.level);
                    let saved = save_payload["saved"].as_bool().unwrap();
                    state.trace.insert("poison_save".to_string(), save_payload);
                    if !saved {
                        chg_str(state, -1);
                        state.markers.push("poison_strength".to_string());
                    }
                }
            }
        }
        T_RUST => {
            state.markers.push("rust_armor".to_string());
            rust_armor(state);
        }
        _ => {}
    }

    state.markers.push("flush_type".to_string());
    Some(trap_kind)
}

pub fn search_hidden_traps(
    rng: &mut RogueRng,
    traps: &mut [Value],
    map_cells: &mut [Value],
    hero_y: i32,
    hero_x: i32,
    player_flags: i32,
) -> Value {
    let mut probinc = 0;
    if player_flags & ISHALU != 0 {
        probinc += 3;
    }
    if player_flags & ISBLIND != 0 {
        probinc += 2;
    }
    let mut markers = Vec::new();
    let mut found = false;
    for row in (hero_y - 1)..=(hero_y + 1) {
        for col in (hero_x - 1)..=(hero_x + 1) {
            if row == hero_y && col == hero_x {
                continue;
            }
            if let Some(index) = map_cell_at(map_cells, row, col) {
                if trap_i32(&map_cells[index], "flags", 0) & F_REAL == 0 {
                    let ch = trap_str(&map_cells[index], "ch", " ");
                    let cell_id = trap_str(&map_cells[index], "id", "");
                    if matches!(ch.chars().next().unwrap_or(' '), '|' | '-') {
                        let roll = rng.rnd(5 + probinc);
                        markers.push(format!("search_cell_roll:{cell_id}:{roll}"));
                        if roll != 0 {
                            continue;
                        }
                        let flags = trap_i32(&map_cells[index], "flags", 0) | F_REAL;
                        trap_set_i32(&mut map_cells[index], "flags", flags);
                        trap_set_string(&mut map_cells[index], "ch", &DOOR.to_string());
                        markers.push(format!("search_found_door:{cell_id}"));
                        found = true;
                        continue;
                    }
                    if ch == " " {
                        let roll = rng.rnd(3 + probinc);
                        markers.push(format!("search_cell_roll:{cell_id}:{roll}"));
                        if roll != 0 {
                            continue;
                        }
                        let flags = trap_i32(&map_cells[index], "flags", 0) | F_REAL;
                        trap_set_i32(&mut map_cells[index], "flags", flags);
                        trap_set_string(&mut map_cells[index], "ch", &PASSAGE.to_string());
                        markers.push(format!("search_found_passage:{cell_id}"));
                        found = true;
                        continue;
                    }
                }
            }
            let Some(index) = trap_at(traps, row, col) else {
                continue;
            };
            if trap_i32(&traps[index], "flags", 0) & F_REAL != 0 {
                continue;
            }
            let trap_id = trap_str(&traps[index], "id", "");
            let roll = rng.rnd(2 + probinc);
            markers.push(format!("search_trap_roll:{trap_id}:{roll}"));
            if roll != 0 {
                continue;
            }
            let flags = trap_i32(&traps[index], "flags", 0) | F_REAL | F_SEEN;
            trap_set_i32(&mut traps[index], "flags", flags);
            trap_set_string(&mut traps[index], "ch", &TRAP.to_string());
            markers.push(format!("search_found_trap:{trap_id}"));
            found = true;
        }
    }
    json!({"rng_seed": rng.seed, "found": found, "traps": traps.to_vec(), "map_cells": map_cells.to_vec(), "markers": markers})
}

fn trap_cases() -> Vec<TrapCase> {
    vec![
        case("levitating_arrow_returns_rust", 1, T_ARROW).player_flags(ISRUN | ISLEVIT),
        case("trapdoor_new_level", 1, T_DOOR).level(4),
        case("bear_trap_holds", -17, T_BEAR).no_move(1),
        case("mystery_plain", -184, T_MYST),
        case("mystery_color_1", -178, T_MYST),
        case("mystery_color_4", -160, T_MYST),
        case("mystery_color_6", -148, T_MYST),
        case("mystery_color_10", -190, T_MYST),
        case("sleep_trap_stops_run", 7, T_SLEEP).no_command(2),
        case("arrow_hit", 76, T_ARROW).stats(stats(16, 16, 1, 6, 12, 12)),
        case("arrow_miss_falls", 1, T_ARROW)
            .stats(stats(16, 16, 1, 6, 12, 12))
            .weapon_group(9),
        case("arrow_death", 76, T_ARROW).stats(stats(16, 16, 1, 6, 1, 12)),
        case("teleport_marker", 7, T_TELEP),
        case("dart_miss", 1, T_DART).stats(stats(16, 16, 1, 6, 12, 12)),
        case("dart_poison_strength", 64, T_DART).stats(stats(10, 10, 1, 6, 12, 12)),
        case("dart_poison_saved", 68, T_DART).stats(stats(10, 10, 1, 6, 12, 12)),
        case("dart_sustain_strength", 64, T_DART)
            .stats(stats(10, 10, 1, 6, 12, 12))
            .left_ring(ring(R_SUSTSTR, 0)),
        case("rust_armor", 5, T_RUST).armor(armor(ARMOR, 1, 4, 0)),
        case("rust_protected_armor", 5, T_RUST).armor(armor(ARMOR, 1, 4, ISPROT)),
        case("rust_sustain_armor", 5, T_RUST)
            .armor(armor(ARMOR, 1, 4, 0))
            .right_ring(ring(R_SUSTARM, 0)),
    ]
}

fn run_search_case(case: Value) -> Value {
    let mut traps = case
        .get("traps")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut map_cells = case
        .get("map_cells")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let seed = trap_i32(&case, "seed", 1);
    let hero_y = trap_i32(&case, "hero_y", 2);
    let hero_x = trap_i32(&case, "hero_x", 3);
    let player_flags = trap_i32(&case, "player_flags", 0);
    let mut rng = RogueRng::new(seed);
    let result = search_hidden_traps(
        &mut rng,
        &mut traps,
        &mut map_cells,
        hero_y,
        hero_x,
        player_flags,
    );
    json!({"name": trap_str(&case, "name", ""), "seed": seed, "result": result})
}

fn search_cases() -> Vec<Value> {
    vec![
        json!({"name": "search_hidden_trap_found", "seed": 1, "traps": [search_trap("hidden_arrow", T_ARROW, 2, 4, T_ARROW)]}),
        json!({"name": "search_hidden_trap_missed", "seed": 5, "traps": [search_trap("hidden_bear", T_BEAR, 2, 4, T_BEAR)]}),
        json!({"name": "search_ignores_real_trap", "seed": 1, "traps": [search_trap("real_arrow", T_ARROW, 2, 4, F_REAL | T_ARROW)]}),
        json!({"name": "search_secret_door_found", "seed": 1, "traps": [], "map_cells": [search_cell("secret_door", "|", 2, 4, 0)]}),
        json!({"name": "search_hidden_passage_found", "seed": 1, "traps": [], "map_cells": [search_cell("hidden_passage", " ", 2, 4, 0)]}),
        json!({"name": "search_secret_door_missed", "seed": 5, "traps": [], "map_cells": [search_cell("missed_door", "-", 2, 4, 0)]}),
    ]
}

fn search_trap(trap_id: &str, kind: i32, row: i32, col: i32, flags: i32) -> Value {
    json!({"id": trap_id, "row": row, "col": col, "kind": kind, "flags": flags, "ch": "^", "weapon_group": 1})
}

fn search_cell(cell_id: &str, ch: &str, row: i32, col: i32, flags: i32) -> Value {
    json!({"id": cell_id, "row": row, "col": col, "ch": ch, "flags": flags})
}

fn trap_at(traps: &[Value], row: i32, col: i32) -> Option<usize> {
    traps
        .iter()
        .position(|trap| trap_i32(trap, "row", -1) == row && trap_i32(trap, "col", -1) == col)
}

fn map_cell_at(cells: &[Value], row: i32, col: i32) -> Option<usize> {
    cells
        .iter()
        .position(|cell| trap_i32(cell, "row", -1) == row && trap_i32(cell, "col", -1) == col)
}

fn trap_i32(value: &Value, key: &str, default: i32) -> i32 {
    value
        .get(key)
        .and_then(Value::as_i64)
        .map(|number| number as i32)
        .unwrap_or(default)
}

fn trap_str(value: &Value, key: &str, default: &str) -> String {
    value
        .get(key)
        .and_then(Value::as_str)
        .unwrap_or(default)
        .to_string()
}

fn trap_set_i32(value: &mut Value, key: &str, number: i32) {
    if let Some(object) = value.as_object_mut() {
        object.insert(key.to_string(), json!(number));
    }
}

fn trap_set_string(value: &mut Value, key: &str, text: &str) {
    if let Some(object) = value.as_object_mut() {
        object.insert(key.to_string(), json!(text));
    }
}

fn case(name: &'static str, seed: i32, trap_kind: i32) -> TrapCase {
    TrapCase {
        name,
        seed,
        trap_kind,
        level: 1,
        no_move: 0,
        no_command: 0,
        player_flags: ISRUN,
        stats: stats(16, 16, 1, 6, 12, 12),
        weapon_group: 1,
        left_ring: None,
        right_ring: None,
        armor: None,
    }
}

impl TrapCase {
    fn level(mut self, level: i32) -> Self {
        self.level = level;
        self
    }

    fn no_move(mut self, no_move: i32) -> Self {
        self.no_move = no_move;
        self
    }

    fn no_command(mut self, no_command: i32) -> Self {
        self.no_command = no_command;
        self
    }

    fn player_flags(mut self, player_flags: i32) -> Self {
        self.player_flags = player_flags;
        self
    }

    fn stats(mut self, stats: TrapStats) -> Self {
        self.stats = stats;
        self
    }

    fn weapon_group(mut self, weapon_group: i32) -> Self {
        self.weapon_group = weapon_group;
        self
    }

    fn left_ring(mut self, ring: TrapRing) -> Self {
        self.left_ring = Some(ring);
        self
    }

    fn right_ring(mut self, ring: TrapRing) -> Self {
        self.right_ring = Some(ring);
        self
    }

    fn armor(mut self, armor: TrapArmor) -> Self {
        self.armor = Some(armor);
        self
    }
}

fn stats(
    strength: i32,
    max_strength: i32,
    level: i32,
    arm: i32,
    hp: i32,
    max_hp: i32,
) -> TrapStats {
    TrapStats {
        strength,
        max_strength,
        level,
        arm,
        hp,
        max_hp,
    }
}

fn ring(which: i32, arm: i32) -> TrapRing {
    TrapRing { which, arm }
}

fn armor(obj_type: char, which: i32, arm: i32, flags: i32) -> TrapArmor {
    TrapArmor {
        obj_type,
        which,
        arm,
        flags,
    }
}

fn swing(rng: &mut RogueRng, at_lvl: i32, op_arm: i32, wplus: i32) -> Value {
    let result = rng.rnd(20);
    let need = (20 - at_lvl) - op_arm;
    json!({"roll": result, "need": need, "hit": result + wplus >= need, "rng_seed": rng.seed})
}

fn save_throw(rng: &mut RogueRng, which: i32, level: i32) -> Value {
    let need = 14 + which - level / 2;
    let roll = rng.roll(1, 20);
    json!({"which": which, "level": level, "need": need, "roll": roll, "saved": roll >= need, "rng_seed": rng.seed})
}

fn init_weapon(state: &mut TrapState, which: i32) -> TrapObject {
    let flags = INIT_WEAPON_FLAGS[which as usize];
    let mut init_count = 1;
    let mut group = 0;
    if which == DAGGER {
        init_count = state.rng.rnd(4) + 2;
        group = state.weapon_group;
        state.weapon_group += 1;
    } else if flags & ISMANY != 0 {
        init_count = state.rng.rnd(8) + 8;
        group = state.weapon_group;
        state.weapon_group += 1;
    }
    TrapObject {
        obj_type: WEAPON,
        which,
        count: init_count,
        group,
        flags,
        y: 0,
        x: 0,
        init_count,
    }
}

fn is_wearing(state: &TrapState, ring_kind: i32) -> bool {
    state
        .left_ring
        .as_ref()
        .is_some_and(|ring| ring.which == ring_kind)
        || state
            .right_ring
            .as_ref()
            .is_some_and(|ring| ring.which == ring_kind)
}

fn chg_str(state: &mut TrapState, amount: i32) {
    state.stats.strength = (state.stats.strength + amount).clamp(3, 31);
    let mut comparable = state.stats.strength;
    if let Some(left) = &state.left_ring {
        if left.which == R_ADDSTR {
            comparable = (comparable - left.arm).clamp(3, 31);
        }
    }
    if let Some(right) = &state.right_ring {
        if right.which == R_ADDSTR {
            comparable = (comparable - right.arm).clamp(3, 31);
        }
    }
    if comparable > state.stats.max_strength {
        state.stats.max_strength = comparable;
    }
}

fn rust_armor(state: &mut TrapState) {
    let Some(armor) = state.armor.as_ref() else {
        return;
    };
    if armor.obj_type != ARMOR || armor.which == LEATHER || armor.arm >= 9 {
        return;
    }
    if armor.flags & ISPROT != 0 || is_wearing(state, R_SUSTARM) {
        state.markers.push("rust_vanishes".to_string());
        return;
    }
    let armor = state.armor.as_mut().unwrap();
    armor.arm += 1;
    state.markers.push("armor_weakened".to_string());
}

pub fn state_json(state: &TrapState) -> Value {
    json!({
        "rng_seed": state.rng.seed,
        "level": state.level,
        "no_move": state.no_move,
        "no_command": state.no_command,
        "player_flags": state.player_flags,
        "stats": stats_json(&state.stats),
        "cell": {"ch": state.cell.ch.to_string(), "flags": state.cell.flags},
        "running": state.running,
        "count": state.count,
        "weapon_group": state.weapon_group,
        "hero": {"y": state.hero_y, "x": state.hero_x},
        "left_ring": state.left_ring.as_ref().map(ring_json),
        "right_ring": state.right_ring.as_ref().map(ring_json),
        "armor": state.armor.as_ref().map(armor_json),
        "arrow": state.arrow.as_ref().map(object_json),
        "markers": state.markers,
        "trace": state.trace,
        "terminal": state.terminal,
    })
}

fn stats_json(stats: &TrapStats) -> Value {
    json!({
        "strength": stats.strength,
        "max_strength": stats.max_strength,
        "level": stats.level,
        "arm": stats.arm,
        "hp": stats.hp,
        "max_hp": stats.max_hp,
    })
}

fn ring_json(ring: &TrapRing) -> Value {
    json!({"which": ring.which, "arm": ring.arm})
}

fn armor_json(armor: &TrapArmor) -> Value {
    json!({"type": armor.obj_type.to_string(), "which": armor.which, "arm": armor.arm, "flags": armor.flags})
}

fn object_json(obj: &TrapObject) -> Value {
    json!({
        "type": obj.obj_type.to_string(),
        "which": obj.which,
        "count": obj.count,
        "group": obj.group,
        "flags": obj.flags,
        "y": obj.y,
        "x": obj.x,
        "init_count": obj.init_count,
    })
}
