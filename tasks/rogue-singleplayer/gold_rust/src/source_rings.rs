use crate::{RogueRng, RING};
use serde_json::{json, Value};

pub const LEFT: i32 = 0;
pub const RIGHT: i32 = 1;

const ISCURSED: i32 = 0o000001;
const ISKNOW: i32 = 0o000002;

const R_PROTECT: i32 = 0;
const R_ADDSTR: i32 = 1;
const R_SEARCH: i32 = 3;
const R_SEEINVIS: i32 = 4;
const R_NOP: i32 = 5;
const R_AGGR: i32 = 6;
const R_ADDHIT: i32 = 7;
const R_ADDDAM: i32 = 8;
const R_REGEN: i32 = 9;
const R_DIGEST: i32 = 10;

#[derive(Clone)]
pub struct RingObject {
    pub obj_id: String,
    pub obj_type: char,
    pub which: i32,
    pub arm: i32,
    pub flags: i32,
    pub packch: char,
}

pub struct RingWorld {
    pub rng: RogueRng,
    pub strength: i32,
    pub left_ring: Option<RingObject>,
    pub right_ring: Option<RingObject>,
    pub selected_hand: i32,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_rings_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_rings.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn ring_on(world: &mut RingWorld, obj: Option<RingObject>) {
    let Some(obj) = obj else {
        return;
    };
    if obj.obj_type != RING {
        world.markers.push("not_ring".to_string());
        return;
    }
    if is_current(world, &obj) {
        world.markers.push("in_use".to_string());
        return;
    }
    let ring = if world.left_ring.is_none() && world.right_ring.is_none() {
        if world.selected_hand < 0 {
            world.markers.push("gethand_cancelled".to_string());
            return;
        }
        world.selected_hand
    } else if world.left_ring.is_none() {
        LEFT
    } else if world.right_ring.is_none() {
        RIGHT
    } else {
        world.markers.push("wearing_two".to_string());
        return;
    };

    if ring == LEFT {
        world.left_ring = Some(obj.clone());
    } else {
        world.right_ring = Some(obj.clone());
    }
    match obj.which {
        R_ADDSTR => {
            world.strength += obj.arm;
            world.markers.push("chg_str".to_string());
        }
        R_SEEINVIS => world.markers.push("invis_on".to_string()),
        R_AGGR => world.markers.push("aggravate".to_string()),
        _ => {}
    }
    world.markers.push(format!("wear:{ring}"));
}

pub fn ring_off(world: &mut RingWorld) {
    if world.left_ring.is_none() && world.right_ring.is_none() {
        world.markers.push("no_rings".to_string());
        return;
    }
    let ring = if world.left_ring.is_none() {
        RIGHT
    } else if world.right_ring.is_none() {
        LEFT
    } else {
        if world.selected_hand < 0 {
            world.markers.push("gethand_cancelled".to_string());
            return;
        }
        world.selected_hand
    };
    let obj = if ring == LEFT {
        world.left_ring.clone()
    } else {
        world.right_ring.clone()
    };
    let Some(obj) = obj else {
        world.markers.push("not_wearing".to_string());
        return;
    };
    if dropcheck(world, Some(obj.clone())) {
        world.markers.push(format!("was_wearing:{}", obj.packch));
    }
}

pub fn dropcheck(world: &mut RingWorld, obj: Option<RingObject>) -> bool {
    let Some(obj) = obj else {
        return true;
    };
    let Some(hand) = current_hand(world, &obj) else {
        return true;
    };
    if obj.flags & ISCURSED != 0 {
        world.markers.push("cursed".to_string());
        return false;
    }
    if hand == LEFT {
        world.left_ring = None;
    } else {
        world.right_ring = None;
    }
    match obj.which {
        R_ADDSTR => {
            world.strength -= obj.arm;
            world.markers.push("chg_str".to_string());
        }
        R_SEEINVIS => {
            world.markers.push("unsee".to_string());
            world.markers.push("extinguish_unsee".to_string());
        }
        _ => {}
    }
    true
}

fn ring_eat(world: &mut RingWorld, hand: i32) -> i32 {
    let ring = if hand == LEFT {
        world.left_ring.clone()
    } else {
        world.right_ring.clone()
    };
    let uses = [1, 1, 1, -3, -5, 0, 0, -3, -3, 2, -2, 0, 1, 1];
    let Some(ring) = ring else {
        return 0;
    };
    let mut eat = uses[ring.which as usize];
    if eat < 0 {
        eat = if world.rng.rnd(-eat) == 0 { 1 } else { 0 };
    }
    if ring.which == R_DIGEST {
        eat = -eat;
    }
    world.trace.insert("eat".to_string(), json!(eat));
    eat
}

fn ring_num(obj: RingObject) -> String {
    if obj.flags & ISKNOW == 0 {
        return String::new();
    }
    match obj.which {
        R_PROTECT | R_ADDSTR | R_ADDDAM | R_ADDHIT => format!(" [{}]", num(obj.arm)),
        _ => String::new(),
    }
}

fn num(value: i32) -> String {
    if value < 0 {
        value.to_string()
    } else {
        format!("+{value}")
    }
}

fn is_current(world: &RingWorld, obj: &RingObject) -> bool {
    same_obj(world.left_ring.as_ref(), obj) || same_obj(world.right_ring.as_ref(), obj)
}

fn current_hand(world: &RingWorld, obj: &RingObject) -> Option<i32> {
    if same_obj(world.left_ring.as_ref(), obj) {
        Some(LEFT)
    } else if same_obj(world.right_ring.as_ref(), obj) {
        Some(RIGHT)
    } else {
        None
    }
}

fn same_obj(left: Option<&RingObject>, right: &RingObject) -> bool {
    left.is_some_and(|left| left.obj_id == right.obj_id)
}

fn run_case(case: Case) -> Value {
    let mut world = RingWorld {
        rng: RogueRng::new(case.seed),
        strength: case.strength,
        left_ring: case.left_ring.clone(),
        right_ring: case.right_ring.clone(),
        selected_hand: case.selected_hand,
        markers: Vec::new(),
        trace: serde_json::Map::new(),
    };
    let result = match case.op {
        CaseOp::RingOn => {
            ring_on(&mut world, case.obj);
            Value::Null
        }
        CaseOp::RingOff => {
            ring_off(&mut world);
            Value::Null
        }
        CaseOp::RingEat => json!(ring_eat(&mut world, case.hand)),
        CaseOp::RingNum => json!(ring_num(
            case.obj
                .unwrap_or_else(|| ring("none", RING, R_NOP, 0, 0, 'a'))
        )),
    };
    json!({"name": case.name, "seed": case.seed, "result": result, "world": world_json(&world)})
}

#[derive(Clone, Copy)]
enum CaseOp {
    RingOn,
    RingOff,
    RingEat,
    RingNum,
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    op: CaseOp,
    strength: i32,
    left_ring: Option<RingObject>,
    right_ring: Option<RingObject>,
    selected_hand: i32,
    hand: i32,
    obj: Option<RingObject>,
}

fn base_case(name: &'static str, seed: i32, op: CaseOp) -> Case {
    Case {
        name,
        seed,
        op,
        strength: 16,
        left_ring: None,
        right_ring: None,
        selected_hand: LEFT,
        hand: LEFT,
        obj: None,
    }
}

impl Case {
    fn strength(mut self, strength: i32) -> Self {
        self.strength = strength;
        self
    }
    fn left_ring(mut self, ring: RingObject) -> Self {
        self.left_ring = Some(ring);
        self
    }
    fn right_ring(mut self, ring: RingObject) -> Self {
        self.right_ring = Some(ring);
        self
    }
    fn selected_hand(mut self, selected_hand: i32) -> Self {
        self.selected_hand = selected_hand;
        self
    }
    fn hand(mut self, hand: i32) -> Self {
        self.hand = hand;
        self
    }
    fn obj(mut self, obj: RingObject) -> Self {
        self.obj = Some(obj);
        self
    }
}

fn cases() -> Vec<Case> {
    vec![
        base_case("wear_addstr_chosen_left", 1, CaseOp::RingOn)
            .selected_hand(LEFT)
            .obj(ring("addstr", RING, R_ADDSTR, 2, 0, 'a')),
        base_case("wear_seeinvis_auto_right", 1, CaseOp::RingOn)
            .left_ring(ring("left", RING, R_PROTECT, 1, 0, 'l'))
            .obj(ring("see", RING, R_SEEINVIS, 0, 0, 'b')),
        base_case("wear_aggravate_auto_left", 1, CaseOp::RingOn)
            .right_ring(ring("right", RING, R_PROTECT, 1, 0, 'r'))
            .obj(ring("aggr", RING, R_AGGR, 0, 0, 'c')),
        base_case("wear_non_ring_rejected", 1, CaseOp::RingOn)
            .obj(ring("food", ':', R_NOP, 0, 0, 'a')),
        base_case("wear_current_rejected", 1, CaseOp::RingOn)
            .left_ring(ring("same", RING, R_PROTECT, 1, 0, 'a'))
            .obj(ring("same", RING, R_PROTECT, 1, 0, 'a')),
        base_case("wear_two_rejected", 1, CaseOp::RingOn)
            .left_ring(ring("left", RING, R_PROTECT, 1, 0, 'a'))
            .right_ring(ring("right", RING, R_ADDHIT, 1, 0, 'a'))
            .obj(ring("third", RING, R_REGEN, 0, 0, 'a')),
        base_case("off_no_rings", 1, CaseOp::RingOff),
        base_case("off_addstr_uncursed", 1, CaseOp::RingOff)
            .strength(18)
            .left_ring(ring("addstr", RING, R_ADDSTR, 2, 0, 'a')),
        base_case("off_cursed_keeps_ring", 1, CaseOp::RingOff)
            .left_ring(ring("bad", RING, R_ADDSTR, 2, ISCURSED, 'b')),
        base_case("off_seeinvis_unsee", 1, CaseOp::RingOff)
            .right_ring(ring("see", RING, R_SEEINVIS, 0, 0, 'c')),
        base_case("eat_none", 1, CaseOp::RingEat).hand(LEFT),
        base_case("eat_regen", 1, CaseOp::RingEat)
            .hand(LEFT)
            .left_ring(ring("regen", RING, R_REGEN, 0, 0, 'a')),
        base_case("eat_search_random", 1, CaseOp::RingEat)
            .hand(LEFT)
            .left_ring(ring("search", RING, R_SEARCH, 0, 0, 'a')),
        base_case("eat_digest_negative", 1, CaseOp::RingEat)
            .hand(LEFT)
            .left_ring(ring("digest", RING, R_DIGEST, 0, 0, 'a')),
        base_case("num_unknown", 1, CaseOp::RingNum).obj(ring("unk", RING, R_ADDSTR, 2, 0, 'a')),
        base_case("num_addhit_positive", 1, CaseOp::RingNum)
            .obj(ring("hit", RING, R_ADDHIT, 3, ISKNOW, 'a')),
        base_case("num_adddam_negative", 1, CaseOp::RingNum)
            .obj(ring("dam", RING, R_ADDDAM, -1, ISKNOW, 'a')),
        base_case("num_regen_empty", 1, CaseOp::RingNum)
            .obj(ring("regen", RING, R_REGEN, 0, ISKNOW, 'a')),
    ]
}

fn ring(
    obj_id: &'static str,
    obj_type: char,
    which: i32,
    arm: i32,
    flags: i32,
    packch: char,
) -> RingObject {
    RingObject {
        obj_id: obj_id.to_string(),
        obj_type,
        which,
        arm,
        flags,
        packch,
    }
}

fn ring_json(ring: &RingObject) -> Value {
    json!({"id": ring.obj_id, "type": ring.obj_type.to_string(), "which": ring.which, "arm": ring.arm, "flags": ring.flags, "packch": ring.packch.to_string()})
}

pub fn world_json(world: &RingWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "strength": world.strength,
        "left_ring": world.left_ring.as_ref().map(ring_json),
        "right_ring": world.right_ring.as_ref().map(ring_json),
        "markers": world.markers,
        "trace": world.trace,
    })
}
