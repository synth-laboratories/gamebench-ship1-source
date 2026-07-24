use crate::{step_ok, RogueRng, NUMCOLS, NUMLINES, SCROLL};
use serde_json::{json, Value};

const ISHUH: i32 = 0o001000;
const ISHASTE: i32 = 0o000100;
const ISSLOW: i32 = 0o100000;
const S_SCARE: i32 = 10;

#[derive(Clone, Copy)]
pub struct Coord {
    pub y: i32,
    pub x: i32,
}

#[derive(Clone)]
pub struct ChaseThing {
    pub monster_type: char,
    pub pos: Coord,
    pub flags: i32,
    pub turn: bool,
    pub disguise: char,
}

#[derive(Clone)]
pub struct ChaseObject {
    pub obj_type: char,
    pub which: i32,
    pub pos: Coord,
}

pub struct ChaseMap {
    pub terrain: Vec<(Coord, char)>,
    pub objects: Vec<ChaseObject>,
    pub monsters: Vec<ChaseThing>,
}

pub fn source_chase_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_chase.v1",
        "chase_cases": chase_cases().into_iter().map(run_chase_case).collect::<Vec<_>>(),
        "move_monst": move_cases().into_iter().map(run_move_case).collect::<Vec<_>>(),
    })
}

pub fn chase(
    rng: &mut RogueRng,
    game_map: &ChaseMap,
    thing: &mut ChaseThing,
    target: Coord,
    hero: Coord,
) -> Value {
    let mut trace = json!({"branch": "direct", "candidates": []});
    let mut random_branch = false;
    if thing.flags & ISHUH != 0 {
        let confused_roll = rng.rnd(5);
        trace
            .as_object_mut()
            .unwrap()
            .insert("confused_roll".to_string(), json!(confused_roll));
        random_branch = confused_roll != 0;
    }
    if !random_branch && thing.monster_type == 'P' {
        let phantom_roll = rng.rnd(5);
        trace
            .as_object_mut()
            .unwrap()
            .insert("phantom_roll".to_string(), json!(phantom_roll));
        random_branch = phantom_roll == 0;
    }
    if !random_branch && thing.monster_type == 'B' {
        let bat_roll = rng.rnd(2);
        trace
            .as_object_mut()
            .unwrap()
            .insert("bat_roll".to_string(), json!(bat_roll));
        random_branch = bat_roll == 0;
    }

    let chosen;
    let curdist;
    if random_branch {
        trace
            .as_object_mut()
            .unwrap()
            .insert("branch".to_string(), json!("random"));
        chosen = rndmove(rng, thing);
        curdist = dist(chosen, target);
        let clear_roll = rng.rnd(20);
        trace
            .as_object_mut()
            .unwrap()
            .insert("clear_roll".to_string(), json!(clear_roll));
        if clear_roll == 0 {
            thing.flags &= !ISHUH;
        }
    } else {
        let mut local_curdist = dist(thing.pos, target);
        let mut local_chosen = thing.pos;
        let mut plcnt = 1;
        let mut ey = thing.pos.y + 1;
        if ey >= NUMLINES as i32 - 1 {
            ey = NUMLINES as i32 - 2;
        }
        let mut ex = thing.pos.x + 1;
        if ex >= NUMCOLS as i32 {
            ex = NUMCOLS as i32 - 1;
        }
        for x in (thing.pos.x - 1)..=ex {
            if x < 0 {
                continue;
            }
            for y in (thing.pos.y - 1)..=ey {
                let tryp = Coord { y, x };
                let mut candidate = json!({"pos": coord_json(tryp)});
                if !diag_ok(game_map, thing.pos, tryp) {
                    candidate
                        .as_object_mut()
                        .unwrap()
                        .insert("skip".to_string(), json!("diag"));
                    push_candidate(&mut trace, candidate);
                    continue;
                }
                let ch = game_map.winat(tryp);
                candidate
                    .as_object_mut()
                    .unwrap()
                    .insert("ch".to_string(), json!(char_json(ch)));
                if !step_ok(ch) {
                    candidate
                        .as_object_mut()
                        .unwrap()
                        .insert("skip".to_string(), json!("blocked"));
                    push_candidate(&mut trace, candidate);
                    continue;
                }
                if ch == SCROLL {
                    if let Some(obj) = game_map.object_at(tryp) {
                        if obj.obj_type == SCROLL && obj.which == S_SCARE {
                            candidate
                                .as_object_mut()
                                .unwrap()
                                .insert("skip".to_string(), json!("scare_scroll"));
                            push_candidate(&mut trace, candidate);
                            continue;
                        }
                    }
                }
                if let Some(blocker) = game_map.moat(tryp) {
                    if blocker.monster_type == 'X' {
                        candidate
                            .as_object_mut()
                            .unwrap()
                            .insert("skip".to_string(), json!("xeroc"));
                        push_candidate(&mut trace, candidate);
                        continue;
                    }
                }
                let thisdist = dist(tryp, target);
                candidate
                    .as_object_mut()
                    .unwrap()
                    .insert("dist".to_string(), json!(thisdist));
                if thisdist < local_curdist {
                    plcnt = 1;
                    local_chosen = tryp;
                    local_curdist = thisdist;
                    candidate
                        .as_object_mut()
                        .unwrap()
                        .insert("chosen".to_string(), json!(true));
                } else if thisdist == local_curdist {
                    plcnt += 1;
                    let tie_roll = rng.rnd(plcnt);
                    candidate
                        .as_object_mut()
                        .unwrap()
                        .insert("tie_roll".to_string(), json!(tie_roll));
                    candidate
                        .as_object_mut()
                        .unwrap()
                        .insert("plcnt".to_string(), json!(plcnt));
                    if tie_roll == 0 {
                        local_chosen = tryp;
                        local_curdist = thisdist;
                        candidate
                            .as_object_mut()
                            .unwrap()
                            .insert("chosen".to_string(), json!(true));
                    }
                }
                push_candidate(&mut trace, candidate);
            }
        }
        chosen = local_chosen;
        curdist = local_curdist;
    }
    let keep_chasing = curdist != 0 && !coord_eq(chosen, hero);
    json!({
        "chosen": coord_json(chosen),
        "curdist": curdist,
        "keep_chasing": keep_chasing,
        "thing": thing_json(thing),
        "rng_seed": rng.seed,
        "trace": trace,
    })
}

pub fn move_monst_schedule(thing: &mut ChaseThing, do_chase_results: &[i32]) -> Value {
    let mut calls = 0;
    let mut returned = 0;
    if thing.flags & ISSLOW == 0 || thing.turn {
        calls += 1;
        if !do_chase_results.is_empty() && do_chase_results[0] == -1 {
            returned = -1;
            return move_schedule_payload(thing, calls, returned);
        }
    }
    if thing.flags & ISHASTE != 0 {
        calls += 1;
        if do_chase_results.len() > 1 && do_chase_results[1] == -1 {
            returned = -1;
            return move_schedule_payload(thing, calls, returned);
        }
    }
    thing.turn = !thing.turn;
    move_schedule_payload(thing, calls, returned)
}

#[derive(Clone)]
struct ChaseCase {
    name: &'static str,
    seed: i32,
    monster_type: char,
    flags: i32,
    pos: Coord,
    target: Coord,
    hero: Coord,
    tiles: Vec<(Coord, char)>,
    objects: Vec<ChaseObject>,
    monsters: Vec<ChaseThing>,
}

struct MoveCase {
    name: &'static str,
    monster_type: char,
    flags: i32,
    turn: bool,
    results: Vec<i32>,
}

fn run_chase_case(case: ChaseCase) -> Value {
    let game_map = ChaseMap {
        terrain: case.tiles,
        objects: case.objects,
        monsters: case.monsters,
    };
    let mut thing = ChaseThing {
        monster_type: case.monster_type,
        pos: case.pos,
        flags: case.flags,
        turn: true,
        disguise: case.monster_type,
    };
    let mut rng = RogueRng::new(case.seed);
    json!({"name": case.name, "seed": case.seed, "outcome": chase(&mut rng, &game_map, &mut thing, case.target, case.hero)})
}

fn run_move_case(case: MoveCase) -> Value {
    let mut thing = ChaseThing {
        monster_type: case.monster_type,
        pos: coord(5, 5),
        flags: case.flags,
        turn: case.turn,
        disguise: case.monster_type,
    };
    json!({"name": case.name, "outcome": move_monst_schedule(&mut thing, &case.results)})
}

fn chase_cases() -> Vec<ChaseCase> {
    vec![
        chase_case(
            "direct_east",
            1,
            'K',
            0,
            coord(5, 5),
            coord(5, 7),
            coord(5, 7),
        ),
        chase_case(
            "tie_break",
            7,
            'K',
            0,
            coord(5, 5),
            coord(7, 7),
            coord(9, 9),
        ),
        chase_case(
            "wall_blocks_diagonal",
            7,
            'K',
            0,
            coord(5, 5),
            coord(4, 4),
            coord(4, 4),
        )
        .tiles(vec![(coord(4, 5), '|'), (coord(5, 4), '-')]),
        chase_case(
            "scare_scroll_skip",
            7,
            'K',
            0,
            coord(5, 5),
            coord(5, 4),
            coord(5, 4),
        )
        .tiles(vec![(coord(5, 4), SCROLL)])
        .objects(vec![object(SCROLL, S_SCARE, coord(5, 4))]),
        chase_case(
            "ordinary_scroll_allowed",
            7,
            'K',
            0,
            coord(5, 5),
            coord(5, 4),
            coord(5, 4),
        )
        .tiles(vec![(coord(5, 4), SCROLL)])
        .objects(vec![object(SCROLL, 1, coord(5, 4))]),
        chase_case(
            "xeroc_skip",
            7,
            'K',
            0,
            coord(5, 5),
            coord(5, 4),
            coord(5, 4),
        )
        .monsters(vec![thing('X', coord(5, 4), 0, ':')]),
        chase_case(
            "confused_random",
            5,
            'K',
            ISHUH,
            coord(5, 5),
            coord(7, 7),
            coord(7, 7),
        ),
        chase_case(
            "phantom_random",
            1,
            'P',
            0,
            coord(5, 5),
            coord(7, 7),
            coord(7, 7),
        ),
        chase_case(
            "bat_random",
            1,
            'B',
            0,
            coord(5, 5),
            coord(7, 7),
            coord(7, 7),
        ),
    ]
}

fn move_cases() -> Vec<MoveCase> {
    vec![
        move_case("normal_one_chase", 'K', 0, true, vec![0]),
        move_case("slow_turn_skips", 'K', ISSLOW, false, vec![]),
        move_case("slow_turn_moves", 'K', ISSLOW, true, vec![0]),
        move_case("haste_two_chases", 'K', ISHASTE, true, vec![0, 0]),
        move_case("first_chase_stops", 'K', ISHASTE, true, vec![-1, 0]),
        move_case("second_chase_stops", 'K', ISHASTE, true, vec![0, -1]),
    ]
}

fn chase_case(
    name: &'static str,
    seed: i32,
    monster_type: char,
    flags: i32,
    pos: Coord,
    target: Coord,
    hero: Coord,
) -> ChaseCase {
    ChaseCase {
        name,
        seed,
        monster_type,
        flags,
        pos,
        target,
        hero,
        tiles: Vec::new(),
        objects: Vec::new(),
        monsters: Vec::new(),
    }
}

impl ChaseCase {
    fn tiles(mut self, tiles: Vec<(Coord, char)>) -> Self {
        self.tiles = tiles;
        self
    }

    fn objects(mut self, objects: Vec<ChaseObject>) -> Self {
        self.objects = objects;
        self
    }

    fn monsters(mut self, monsters: Vec<ChaseThing>) -> Self {
        self.monsters = monsters;
        self
    }
}

fn move_case(
    name: &'static str,
    monster_type: char,
    flags: i32,
    turn: bool,
    results: Vec<i32>,
) -> MoveCase {
    MoveCase {
        name,
        monster_type,
        flags,
        turn,
        results,
    }
}

impl ChaseMap {
    fn chat(&self, coord: Coord) -> char {
        self.terrain
            .iter()
            .find(|(pos, _)| coord_eq(*pos, coord))
            .map(|(_, ch)| *ch)
            .unwrap_or('.')
    }

    fn moat(&self, coord: Coord) -> Option<&ChaseThing> {
        self.monsters
            .iter()
            .find(|monster| coord_eq(monster.pos, coord))
    }

    fn winat(&self, coord: Coord) -> char {
        self.moat(coord)
            .map(|monster| monster.disguise)
            .unwrap_or_else(|| self.chat(coord))
    }

    fn object_at(&self, coord: Coord) -> Option<&ChaseObject> {
        self.objects.iter().find(|obj| coord_eq(obj.pos, coord))
    }
}

fn rndmove(rng: &mut RogueRng, thing: &ChaseThing) -> Coord {
    Coord {
        y: thing.pos.y + rng.rnd(3) - 1,
        x: thing.pos.x + rng.rnd(3) - 1,
    }
}

fn diag_ok(game_map: &ChaseMap, start: Coord, end: Coord) -> bool {
    if end.x < 0 || end.x >= NUMCOLS as i32 || end.y <= 0 || end.y >= NUMLINES as i32 - 1 {
        return false;
    }
    if end.x == start.x || end.y == start.y {
        return true;
    }
    step_ok(game_map.chat(Coord {
        y: end.y,
        x: start.x,
    })) && step_ok(game_map.chat(Coord {
        y: start.y,
        x: end.x,
    }))
}

fn dist(first: Coord, second: Coord) -> i32 {
    (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y)
}

fn coord_eq(first: Coord, second: Coord) -> bool {
    first.x == second.x && first.y == second.y
}

fn push_candidate(trace: &mut Value, candidate: Value) {
    trace
        .as_object_mut()
        .unwrap()
        .get_mut("candidates")
        .unwrap()
        .as_array_mut()
        .unwrap()
        .push(candidate);
}

fn coord(y: i32, x: i32) -> Coord {
    Coord { y, x }
}

fn object(obj_type: char, which: i32, pos: Coord) -> ChaseObject {
    ChaseObject {
        obj_type,
        which,
        pos,
    }
}

fn thing(monster_type: char, pos: Coord, flags: i32, disguise: char) -> ChaseThing {
    ChaseThing {
        monster_type,
        pos,
        flags,
        turn: true,
        disguise,
    }
}

fn move_schedule_payload(thing: &ChaseThing, calls: i32, returned: i32) -> Value {
    json!({"calls": calls, "returned": returned, "thing": thing_json(thing)})
}

fn thing_json(thing: &ChaseThing) -> Value {
    json!({
        "type": char_json(thing.monster_type),
        "pos": coord_json(thing.pos),
        "flags": thing.flags,
        "turn": thing.turn,
        "disguise": char_json(thing.disguise),
    })
}

fn coord_json(coord: Coord) -> Value {
    json!({"y": coord.y, "x": coord.x})
}

fn char_json(ch: char) -> String {
    ch.to_string()
}
