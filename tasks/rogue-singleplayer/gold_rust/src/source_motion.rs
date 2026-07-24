use crate::source_level::{Coord, Room, F_PASS, F_PNUM, F_REAL, F_SEEN, ISDARK};
use crate::{step_ok, DOOR, FLOOR, NUMCOLS, NUMLINES, PASSAGE, STAIRS};
use serde_json::{json, Value};

const TRAP: char = '^';
const F_TMASK: u8 = 0x07;
const LAMPDIST: i32 = 3;

const T_DOOR: i32 = 0;
const T_BEAR: i32 = 3;
const T_TELEP: i32 = 4;
const T_RUST: i32 = 6;

#[derive(Clone)]
struct MotionMap {
    rows: Vec<Vec<char>>,
    flags: Vec<Vec<u8>>,
    monsters: Vec<Vec<bool>>,
    rooms: Vec<Room>,
}

#[derive(Clone)]
struct MoveCase {
    name: &'static str,
    hero: Coord,
    delta: Coord,
    tiles: Vec<Tile>,
}

#[derive(Clone)]
struct Tile {
    coord: Coord,
    ch: char,
    flags: u8,
    monst: bool,
}

#[derive(Clone)]
struct RoomRef {
    kind: &'static str,
    index: i32,
}

impl MotionMap {
    fn base() -> Self {
        let mut rows = vec![vec![' '; NUMCOLS]; NUMLINES];
        let flags = vec![vec![F_REAL; NUMCOLS]; NUMLINES];
        let monsters = vec![vec![false; NUMCOLS]; NUMLINES];
        let mut rooms = vec![Room::default(); 9];
        rooms[0].pos = Coord { y: 1, x: 1 };
        rooms[0].max = Coord { y: 5, x: 10 };
        rooms[1].pos = Coord { y: 1, x: 20 };
        rooms[1].max = Coord { y: 5, x: 10 };
        rooms[1].flags = ISDARK;
        for y in 1..6 {
            for x in 1..11 {
                rows[y][x] = FLOOR;
            }
        }
        for x in 1..11 {
            rows[1][x] = '-';
            rows[5][x] = '-';
        }
        for row in rows.iter_mut().take(6).skip(1) {
            row[1] = '|';
            row[10] = '|';
        }
        for row in rows.iter_mut().take(6).skip(1) {
            for ch in row.iter_mut().take(30).skip(20) {
                *ch = FLOOR;
            }
        }
        Self {
            rows,
            flags,
            monsters,
            rooms,
        }
    }

    fn set_tile(&mut self, tile: Tile) {
        self.rows[tile.coord.y as usize][tile.coord.x as usize] = tile.ch;
        self.flags[tile.coord.y as usize][tile.coord.x as usize] = tile.flags;
        self.monsters[tile.coord.y as usize][tile.coord.x as usize] = tile.monst;
    }

    fn ch(&self, coord: Coord) -> char {
        self.rows[coord.y as usize][coord.x as usize]
    }

    fn flag(&self, coord: Coord) -> u8 {
        self.flags[coord.y as usize][coord.x as usize]
    }
}

pub fn source_motion_report() -> Value {
    json!({
        "move_cases": move_cases().into_iter().map(run_move_case).collect::<Vec<_>>(),
        "spatial_cases": spatial_cases(),
    })
}

fn diag_ok(game_map: &MotionMap, start: Coord, end: Coord) -> bool {
    if end.x < 0 || end.x >= NUMCOLS as i32 || end.y <= 0 || end.y >= NUMLINES as i32 - 1 {
        return false;
    }
    if end.x == start.x || end.y == start.y {
        return true;
    }
    step_ok(game_map.rows[end.y as usize][start.x as usize])
        && step_ok(game_map.rows[start.y as usize][end.x as usize])
}

fn turn_ok(game_map: &MotionMap, coord: Coord) -> bool {
    let flags = game_map.flag(coord);
    game_map.ch(coord) == DOOR || (flags & (F_REAL | F_PASS)) == (F_REAL | F_PASS)
}

fn roomin(game_map: &MotionMap, coord: Coord) -> Option<RoomRef> {
    let flags = game_map.flag(coord);
    if flags & F_PASS != 0 {
        return Some(RoomRef {
            kind: "passage",
            index: (flags & F_PNUM) as i32,
        });
    }
    for (index, room) in game_map.rooms.iter().enumerate() {
        if coord.x <= room.pos.x + room.max.x
            && room.pos.x <= coord.x
            && coord.y <= room.pos.y + room.max.y
            && room.pos.y <= coord.y
        {
            return Some(RoomRef {
                kind: "room",
                index: index as i32,
            });
        }
    }
    None
}

fn cansee(game_map: &MotionMap, hero: Coord, target: Coord, is_blind: bool) -> bool {
    if is_blind {
        return false;
    }
    if dist(target.y, target.x, hero.y, hero.x) < LAMPDIST {
        if game_map.flag(target) & F_PASS != 0
            && target.y != hero.y
            && target.x != hero.x
            && !step_ok(game_map.rows[target.y as usize][hero.x as usize])
            && !step_ok(game_map.rows[hero.y as usize][target.x as usize])
        {
            return false;
        }
        return true;
    }
    let Some(target_room) = roomin(game_map, target) else {
        return false;
    };
    let Some(hero_room) = roomin(game_map, hero) else {
        return false;
    };
    if target_room.kind != hero_room.kind || target_room.index != hero_room.index {
        return false;
    }
    if target_room.kind != "room" {
        return true;
    }
    game_map.rooms[target_room.index as usize].flags & ISDARK == 0
}

fn classify_move(game_map: &mut MotionMap, hero: Coord, dy: i32, dx: i32) -> Value {
    let target = Coord {
        y: hero.y + dy,
        x: hero.x + dx,
    };
    if target.x < 0
        || target.x >= NUMCOLS as i32
        || target.y <= 0
        || target.y >= NUMLINES as i32 - 1
    {
        return move_payload(
            "blocked",
            hero,
            target,
            false,
            json!({"reason": "boundary"}),
        );
    }
    if !diag_ok(game_map, hero, target) {
        return move_payload(
            "blocked",
            hero,
            target,
            false,
            json!({"reason": "diagonal"}),
        );
    }
    let mut flags = game_map.flag(target);
    let mut ch = game_map.ch(target);
    let mut revealed_hidden_trap = false;
    if flags & F_REAL == 0 && ch == FLOOR {
        ch = TRAP;
        game_map.rows[target.y as usize][target.x as usize] = TRAP;
        flags |= F_REAL;
        game_map.flags[target.y as usize][target.x as usize] = flags;
        revealed_hidden_trap = true;
    }
    if matches!(ch, ' ' | '|' | '-') {
        return move_payload(
            "blocked",
            hero,
            target,
            false,
            json!({"reason": "wall", "tile": ch.to_string()}),
        );
    }
    if ch == DOOR {
        return move_payload("door", hero, target, true, json!({"tile": ch.to_string()}));
    }
    if ch == TRAP {
        let trap_kind = be_trapped(game_map, target);
        let moved = !matches!(trap_kind, T_DOOR | T_TELEP);
        return move_payload(
            if moved { "trap_move" } else { "trap_no_move" },
            hero,
            target,
            moved,
            json!({
                "tile": ch.to_string(),
                "trap_kind": trap_kind,
                "revealed_hidden_trap": revealed_hidden_trap,
                "cell_after": cell_after(game_map, target),
            }),
        );
    }
    if ch == PASSAGE {
        return move_payload(
            "passage",
            hero,
            target,
            true,
            json!({"tile": ch.to_string()}),
        );
    }
    if ch == FLOOR {
        if flags & F_REAL == 0 {
            be_trapped(game_map, hero);
        }
        return move_payload("floor", hero, target, true, json!({"tile": ch.to_string()}));
    }
    if ch == STAIRS {
        return move_payload(
            "stairs",
            hero,
            target,
            true,
            json!({"tile": ch.to_string(), "seenstairs": true}),
        );
    }
    if ch.is_ascii_uppercase() || game_map.monsters[target.y as usize][target.x as usize] {
        return move_payload(
            "fight",
            hero,
            target,
            false,
            json!({"tile": ch.to_string(), "fight": true}),
        );
    }
    move_payload(
        "item",
        hero,
        target,
        true,
        json!({"tile": ch.to_string(), "take": ch.to_string()}),
    )
}

fn be_trapped(game_map: &mut MotionMap, coord: Coord) -> i32 {
    game_map.rows[coord.y as usize][coord.x as usize] = TRAP;
    let trap_kind = (game_map.flags[coord.y as usize][coord.x as usize] & F_TMASK) as i32;
    game_map.flags[coord.y as usize][coord.x as usize] |= F_SEEN;
    trap_kind
}

fn move_payload(transition: &str, hero: Coord, target: Coord, moved: bool, extra: Value) -> Value {
    let mut payload = json!({
        "transition": transition,
        "from": coord_json(hero),
        "to": coord_json(target),
        "hero_after": coord_json(if moved { target } else { hero }),
        "moved": moved,
        "reason": "",
        "tile": "",
        "trap_kind": Value::Null,
        "revealed_hidden_trap": false,
        "seenstairs": false,
        "fight": false,
        "take": "",
        "cell_after": Value::Null,
    });
    let target_obj = payload.as_object_mut().unwrap();
    for (key, value) in extra.as_object().unwrap() {
        target_obj.insert(key.clone(), value.clone());
    }
    payload
}

fn cell_after(game_map: &MotionMap, coord: Coord) -> Value {
    json!({"ch": game_map.ch(coord).to_string(), "flags": game_map.flag(coord)})
}

fn run_move_case(case: MoveCase) -> Value {
    let mut game_map = MotionMap::base();
    for tile in case.tiles {
        game_map.set_tile(tile);
    }
    let target = Coord {
        y: case.hero.y + case.delta.y,
        x: case.hero.x + case.delta.x,
    };
    let outcome = classify_move(&mut game_map, case.hero, case.delta.y, case.delta.x);
    json!({
        "name": case.name,
        "diag_ok": diag_ok(&game_map, case.hero, target),
        "room_before": room_ref_json(roomin(&game_map, case.hero)),
        "room_target": if target.y >= 0 && target.y < NUMLINES as i32 && target.x >= 0 && target.x < NUMCOLS as i32 {
            room_ref_json(roomin(&game_map, target))
        } else {
            Value::Null
        },
        "outcome": outcome,
    })
}

fn spatial_cases() -> Vec<Value> {
    let mut cases = Vec::new();
    let lit = MotionMap::base();
    cases.push(spatial_payload(
        "lit_same_room_far",
        &lit,
        Coord { y: 3, x: 3 },
        Coord { y: 4, x: 8 },
    ));
    let dark = MotionMap::base();
    cases.push(spatial_payload(
        "dark_same_room_far",
        &dark,
        Coord { y: 3, x: 22 },
        Coord { y: 4, x: 28 },
    ));
    let mut blocked = MotionMap::base();
    blocked.set_tile(tile(4, 4, PASSAGE, F_REAL | F_PASS | 1));
    blocked.set_tile(tile(4, 3, '|', F_REAL));
    blocked.set_tile(tile(3, 4, '|', F_REAL));
    cases.push(spatial_payload(
        "near_passage_blocked_diagonal",
        &blocked,
        Coord { y: 3, x: 3 },
        Coord { y: 4, x: 4 },
    ));
    let mut clear = MotionMap::base();
    clear.set_tile(tile(4, 4, PASSAGE, F_REAL | F_PASS | 1));
    clear.set_tile(tile(4, 3, FLOOR, F_REAL));
    clear.set_tile(tile(3, 4, '|', F_REAL));
    cases.push(spatial_payload(
        "near_passage_clear_diagonal",
        &clear,
        Coord { y: 3, x: 3 },
        Coord { y: 4, x: 4 },
    ));
    let mut turn = MotionMap::base();
    turn.set_tile(tile(3, 4, DOOR, F_REAL));
    turn.set_tile(tile(3, 5, PASSAGE, F_REAL | F_PASS | 2));
    turn.set_tile(tile(3, 6, PASSAGE, F_PASS | 2));
    cases.push(json!({
        "name": "turn_ok",
        "door": turn_ok(&turn, Coord { y: 3, x: 4 }),
        "real_passage": turn_ok(&turn, Coord { y: 3, x: 5 }),
        "hidden_passage": turn_ok(&turn, Coord { y: 3, x: 6 }),
    }));
    cases
}

fn spatial_payload(name: &str, game_map: &MotionMap, hero: Coord, target: Coord) -> Value {
    json!({
        "name": name,
        "hero_room": room_ref_json(roomin(game_map, hero)),
        "target_room": room_ref_json(roomin(game_map, target)),
        "diag_ok": diag_ok(game_map, hero, target),
        "cansee": cansee(game_map, hero, target, false),
    })
}

fn move_cases() -> Vec<MoveCase> {
    vec![
        move_case("floor_east", 3, 3, 0, 1, vec![tile(3, 4, FLOOR, F_REAL)]),
        move_case("wall_west", 3, 2, 0, -1, vec![tile(3, 1, '|', F_REAL)]),
        move_case("boundary_top", 1, 4, -1, 0, vec![]),
        move_case(
            "diagonal_blocked",
            3,
            3,
            -1,
            1,
            vec![
                tile(2, 4, FLOOR, F_REAL),
                tile(2, 3, '|', F_REAL),
                tile(3, 4, FLOOR, F_REAL),
            ],
        ),
        move_case(
            "diagonal_open",
            3,
            3,
            -1,
            1,
            vec![
                tile(2, 4, FLOOR, F_REAL),
                tile(2, 3, FLOOR, F_REAL),
                tile(3, 4, FLOOR, F_REAL),
            ],
        ),
        move_case("door_east", 3, 3, 0, 1, vec![tile(3, 4, DOOR, F_REAL)]),
        move_case(
            "passage_east",
            3,
            3,
            0,
            1,
            vec![tile(3, 4, PASSAGE, F_REAL | F_PASS | 1)],
        ),
        move_case("stairs_east", 3, 3, 0, 1, vec![tile(3, 4, STAIRS, F_REAL)]),
        move_case("item_food_east", 3, 3, 0, 1, vec![tile(3, 4, ':', F_REAL)]),
        move_case(
            "monster_fight_east",
            3,
            3,
            0,
            1,
            vec![tile(3, 4, 'A', F_REAL)],
        ),
        move_case(
            "hidden_bear_trap",
            3,
            3,
            0,
            1,
            vec![tile(3, 4, FLOOR, T_BEAR as u8)],
        ),
        move_case(
            "visible_trapdoor",
            3,
            3,
            0,
            1,
            vec![tile(3, 4, TRAP, F_REAL | T_DOOR as u8)],
        ),
        move_case(
            "visible_rust_trap",
            3,
            3,
            0,
            1,
            vec![tile(3, 4, TRAP, F_REAL | T_RUST as u8)],
        ),
    ]
}

fn move_case(
    name: &'static str,
    hero_y: i32,
    hero_x: i32,
    dy: i32,
    dx: i32,
    tiles: Vec<Tile>,
) -> MoveCase {
    MoveCase {
        name,
        hero: Coord {
            y: hero_y,
            x: hero_x,
        },
        delta: Coord { y: dy, x: dx },
        tiles,
    }
}

fn tile(y: i32, x: i32, ch: char, flags: u8) -> Tile {
    Tile {
        coord: Coord { y, x },
        ch,
        flags,
        monst: false,
    }
}

fn room_ref_json(ref_: Option<RoomRef>) -> Value {
    match ref_ {
        Some(value) => json!({"kind": value.kind, "index": value.index}),
        None => Value::Null,
    }
}

fn coord_json(coord: Coord) -> Value {
    json!({"y": coord.y, "x": coord.x})
}

fn dist(y1: i32, x1: i32, y2: i32, x2: i32) -> i32 {
    (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)
}
