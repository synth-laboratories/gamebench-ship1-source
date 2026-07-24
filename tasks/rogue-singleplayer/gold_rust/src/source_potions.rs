use crate::{RogueRng, AMULET, ARMOR, POTION, RING, SCROLL, STICK, WEAPON};
use serde_json::{json, Value};

const BEFORE: i32 = 1;
const AFTER: i32 = 2;
const DAEMON: i32 = -1;

const HEALTIME: i32 = 30;
const HUHDURATION: i32 = 20;
const SEEDURATION: i32 = 850;

const ISPROT: i32 = 0o000040;

const CANSEE: i32 = 0o000002;
const ISBLIND: i32 = 0o000004;
const ISLEVIT: i32 = 0o000010;
const ISHASTE: i32 = 0o000100;
const ISHUH: i32 = 0o001000;
const ISHALU: i32 = 0o004000;
const ISRUN: i32 = 0o020000;
const SEEMONST: i32 = 0o040000;

const P_CONFUSE: i32 = 0;
const P_LSD: i32 = 1;
const P_POISON: i32 = 2;
const P_STRENGTH: i32 = 3;
const P_SEEINVIS: i32 = 4;
const P_HEALING: i32 = 5;
const P_MFIND: i32 = 6;
const P_TFIND: i32 = 7;
const P_RAISE: i32 = 8;
const P_XHEAL: i32 = 9;
const P_HASTE: i32 = 10;
const P_RESTORE: i32 = 11;
const P_BLIND: i32 = 12;
const P_LEVIT: i32 = 13;
const MAXPOTIONS: usize = 14;

const R_ADDSTR: i32 = 1;
const R_SUSTSTR: i32 = 2;

const E_LEVELS: [i32; 21] = [
    10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000,
    800000, 2000000, 4000000, 8000000, 0,
];
const A_CLASS: [i32; 8] = [8, 7, 7, 6, 5, 4, 4, 3];

#[derive(Clone)]
pub struct PotionObject {
    pub obj_type: char,
    pub which: i32,
    pub count: i32,
    pub flags: i32,
    pub arm: i32,
    pub hplus: i32,
    pub dplus: i32,
}

#[derive(Clone)]
pub struct SourceRing {
    pub which: i32,
    pub arm: i32,
}

#[derive(Clone)]
pub struct DelayedAction {
    pub action: &'static str,
    pub action_type: i32,
    pub arg: i32,
    pub time: i32,
}

pub struct PotionWorld {
    pub rng: RogueRng,
    pub player_flags: i32,
    pub strength: i32,
    pub max_strength: i32,
    pub level: i32,
    pub exp: i32,
    pub hp: i32,
    pub max_hp: i32,
    pub no_command: i32,
    pub after: bool,
    pub current_weapon_is_obj: bool,
    pub left_ring: Option<SourceRing>,
    pub right_ring: Option<SourceRing>,
    pub pot_known: Vec<bool>,
    pub actions: Vec<DelayedAction>,
    pub magic_count: i32,
    pub new_monsters: i32,
    pub invisible_visible: i32,
    pub stairs_visible: bool,
    pub seenstairs: bool,
    pub proom_gone: bool,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_potions_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_potions.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn quaff(world: &mut PotionWorld, obj: Option<PotionObject>) {
    let Some(obj) = obj else {
        return;
    };
    if obj.obj_type != POTION {
        world.markers.push("undrinkable".to_string());
        return;
    }
    if world.current_weapon_is_obj {
        world.current_weapon_is_obj = false;
        world.markers.push("unwield_potion".to_string());
    }
    let trip = world.player_flags & ISHALU != 0;
    let discardit = obj.count == 1;
    world.markers.push("leave_pack".to_string());
    match obj.which {
        P_CONFUSE => do_pot(world, P_CONFUSE, !trip),
        P_POISON => {
            world.pot_known[P_POISON as usize] = true;
            if is_wearing(world, R_SUSTSTR) {
                world.markers.push("msg_momentarily_sick".to_string());
            } else {
                let loss = world.rng.rnd(3) + 1;
                world.trace.insert("poison_loss".to_string(), json!(loss));
                chg_str(world, -loss);
                world.markers.push("msg_very_sick".to_string());
                come_down(world);
            }
        }
        P_HEALING => {
            world.pot_known[P_HEALING as usize] = true;
            let heal = world.rng.roll(world.level, 4);
            world.trace.insert("heal_roll".to_string(), json!(heal));
            world.hp += heal;
            if world.hp > world.max_hp {
                world.max_hp += 1;
                world.hp = world.max_hp;
            }
            sight(world);
            world.markers.push("msg_better".to_string());
        }
        P_STRENGTH => {
            world.pot_known[P_STRENGTH as usize] = true;
            chg_str(world, 1);
            world.markers.push("msg_stronger".to_string());
        }
        P_MFIND => {
            world.player_flags |= SEEMONST;
            fuse(world, "turn_see", 1, HUHDURATION, AFTER);
            if !turn_see(world, false) {
                world.markers.push("msg_monster_fleeting".to_string());
            }
        }
        P_TFIND => {
            if world.magic_count > 0 {
                world.pot_known[P_TFIND as usize] = true;
                world
                    .markers
                    .push(format!("show_magic:{}", world.magic_count));
                world.markers.push("show_win_magic".to_string());
            } else {
                world.markers.push("msg_magic_fleeting".to_string());
            }
        }
        P_LSD => {
            if !trip {
                if world.player_flags & SEEMONST != 0 {
                    turn_see(world, false);
                }
                start_daemon(world, "visuals", 0, BEFORE);
                world.seenstairs = world.stairs_visible;
            }
            do_pot(world, P_LSD, true);
        }
        P_SEEINVIS => {
            let show = world.player_flags & CANSEE != 0;
            do_pot(world, P_SEEINVIS, false);
            if !show {
                invis_on(world);
            }
            sight(world);
        }
        P_RAISE => {
            world.pot_known[P_RAISE as usize] = true;
            world.markers.push("msg_raise".to_string());
            raise_level(world);
        }
        P_XHEAL => {
            world.pot_known[P_XHEAL as usize] = true;
            let heal = world.rng.roll(world.level, 8);
            world.trace.insert("xheal_roll".to_string(), json!(heal));
            world.hp += heal;
            if world.hp > world.max_hp {
                if world.hp > world.max_hp + world.level + 1 {
                    world.max_hp += 1;
                }
                world.max_hp += 1;
                world.hp = world.max_hp;
            }
            sight(world);
            come_down(world);
            world.markers.push("msg_much_better".to_string());
        }
        P_HASTE => {
            world.pot_known[P_HASTE as usize] = true;
            world.after = false;
            if add_haste(world, true) {
                world.markers.push("msg_much_faster".to_string());
            }
        }
        P_RESTORE => {
            restore_strength(world);
            world.markers.push("msg_restore".to_string());
        }
        P_BLIND => do_pot(world, P_BLIND, true),
        P_LEVIT => do_pot(world, P_LEVIT, true),
        _ => {
            world.markers.push("odd_tasting".to_string());
            return;
        }
    }
    world.markers.push("status".to_string());
    world.markers.push(format!("call_it:{}", obj.which));
    if discardit {
        world.markers.push("discard".to_string());
    }
}

fn is_magic(obj: &PotionObject) -> bool {
    if obj.obj_type == ARMOR {
        let base = A_CLASS.get(obj.which as usize).copied().unwrap_or(obj.arm);
        obj.flags & ISPROT != 0 || obj.arm != base
    } else if obj.obj_type == WEAPON {
        obj.hplus != 0 || obj.dplus != 0
    } else {
        matches!(obj.obj_type, POTION | SCROLL | STICK | RING | AMULET)
    }
}

fn do_pot(world: &mut PotionWorld, potion_type: i32, knowit: bool) {
    let action = potion_action(potion_type);
    if !world.pot_known[potion_type as usize] {
        world.pot_known[potion_type as usize] = knowit;
    }
    let duration = world.rng.spread(action.time);
    if world.player_flags & action.flag == 0 {
        world.player_flags |= action.flag;
        fuse(world, action.daemon, 0, duration, AFTER);
        world.markers.push("look:false".to_string());
    } else {
        lengthen(world, action.daemon, duration);
    }
    world
        .trace
        .insert(format!("duration_{potion_type}"), json!(duration));
    world.markers.push(format!("msg_pot:{potion_type}"));
}

struct PotionAction {
    flag: i32,
    daemon: &'static str,
    time: i32,
}

fn potion_action(potion_type: i32) -> PotionAction {
    match potion_type {
        P_CONFUSE => PotionAction {
            flag: ISHUH,
            daemon: "unconfuse",
            time: HUHDURATION,
        },
        P_LSD => PotionAction {
            flag: ISHALU,
            daemon: "come_down",
            time: SEEDURATION,
        },
        P_SEEINVIS => PotionAction {
            flag: CANSEE,
            daemon: "unsee",
            time: SEEDURATION,
        },
        P_BLIND => PotionAction {
            flag: ISBLIND,
            daemon: "sight",
            time: SEEDURATION,
        },
        P_LEVIT => PotionAction {
            flag: ISLEVIT,
            daemon: "land",
            time: HEALTIME,
        },
        _ => unreachable!(),
    }
}

fn invis_on(world: &mut PotionWorld) {
    world.player_flags |= CANSEE;
    for _ in 0..world.invisible_visible {
        world.markers.push("draw_invisible".to_string());
    }
}

fn turn_see(world: &mut PotionWorld, turn_off: bool) -> bool {
    if turn_off {
        world.player_flags &= !SEEMONST;
        world.markers.push("turn_see:off".to_string());
        return false;
    }
    let mut hallu = Vec::new();
    for _ in 0..world.new_monsters {
        if world.player_flags & ISHALU != 0 {
            let ch = char::from_u32((world.rng.rnd(26) as u32) + ('A' as u32)).unwrap();
            hallu.push(ch.to_string());
        }
    }
    if !hallu.is_empty() {
        world
            .trace
            .insert("turn_see_hallu".to_string(), json!(hallu));
    }
    world.player_flags |= SEEMONST;
    world
        .markers
        .push(format!("turn_see:on:{}", world.new_monsters));
    world.new_monsters != 0
}

fn sight(world: &mut PotionWorld) {
    if world.player_flags & ISBLIND != 0 {
        extinguish(world, "sight");
        world.player_flags &= !ISBLIND;
        if !world.proom_gone {
            world.markers.push("enter_room".to_string());
        }
        world.markers.push("msg_sight".to_string());
    }
}

fn come_down(world: &mut PotionWorld) {
    if world.player_flags & ISHALU == 0 {
        return;
    }
    kill_daemon(world, "visuals");
    world.player_flags &= !ISHALU;
    world.markers.push("come_down".to_string());
    if world.player_flags & ISBLIND != 0 {
        return;
    }
    world.markers.push("redraw_after_hallu".to_string());
}

fn raise_level(world: &mut PotionWorld) {
    world.exp = E_LEVELS[(world.level - 1) as usize] + 1;
    check_level(world);
}

fn check_level(world: &mut PotionWorld) {
    let mut next_level = 1;
    for threshold in E_LEVELS {
        if threshold == 0 || threshold > world.exp {
            break;
        }
        next_level += 1;
    }
    let old_level = world.level;
    world.level = next_level;
    if next_level > old_level {
        let add = world.rng.roll(next_level - old_level, 10);
        world.max_hp += add;
        world.hp += add;
        world.trace.insert("level_add".to_string(), json!(add));
        world.markers.push(format!("welcome:{next_level}"));
    }
}

fn add_haste(world: &mut PotionWorld, potion: bool) -> bool {
    if world.player_flags & ISHASTE != 0 {
        let faint = world.rng.rnd(8);
        world.trace.insert("haste_faint".to_string(), json!(faint));
        world.no_command += faint;
        world.player_flags &= !(ISRUN | ISHASTE);
        extinguish(world, "nohaste");
        world.markers.push("msg_faint_exhaustion".to_string());
        false
    } else {
        world.player_flags |= ISHASTE;
        if potion {
            let duration = world.rng.rnd(4) + 4;
            world
                .trace
                .insert("haste_duration".to_string(), json!(duration));
            fuse(world, "nohaste", 0, duration, AFTER);
        }
        true
    }
}

fn restore_strength(world: &mut PotionWorld) {
    if ring_arm_if(world.left_ring.as_ref(), R_ADDSTR).is_some() {
        world.strength = add_str(world.strength, -world.left_ring.as_ref().unwrap().arm);
    }
    if ring_arm_if(world.right_ring.as_ref(), R_ADDSTR).is_some() {
        world.strength = add_str(world.strength, -world.right_ring.as_ref().unwrap().arm);
    }
    if world.strength < world.max_strength {
        world.strength = world.max_strength;
    }
    if ring_arm_if(world.left_ring.as_ref(), R_ADDSTR).is_some() {
        world.strength = add_str(world.strength, world.left_ring.as_ref().unwrap().arm);
    }
    if ring_arm_if(world.right_ring.as_ref(), R_ADDSTR).is_some() {
        world.strength = add_str(world.strength, world.right_ring.as_ref().unwrap().arm);
    }
}

fn chg_str(world: &mut PotionWorld, amount: i32) {
    if amount == 0 {
        return;
    }
    world.strength = add_str(world.strength, amount);
    let mut comp = world.strength;
    if let Some(arm) = ring_arm_if(world.left_ring.as_ref(), R_ADDSTR) {
        comp = add_str(comp, -arm);
    }
    if let Some(arm) = ring_arm_if(world.right_ring.as_ref(), R_ADDSTR) {
        comp = add_str(comp, -arm);
    }
    if comp > world.max_strength {
        world.max_strength = comp;
    }
}

fn add_str(value: i32, amount: i32) -> i32 {
    let value = value + amount;
    if value < 3 {
        3
    } else if value > 31 {
        31
    } else {
        value
    }
}

fn is_wearing(world: &PotionWorld, which: i32) -> bool {
    is_ring(world.left_ring.as_ref(), which) || is_ring(world.right_ring.as_ref(), which)
}

fn is_ring(ring: Option<&SourceRing>, which: i32) -> bool {
    ring.is_some_and(|ring| ring.which == which)
}

fn ring_arm_if(ring: Option<&SourceRing>, which: i32) -> Option<i32> {
    ring.and_then(|ring| {
        if ring.which == which {
            Some(ring.arm)
        } else {
            None
        }
    })
}

fn fuse(world: &mut PotionWorld, action: &'static str, arg: i32, time: i32, action_type: i32) {
    world.actions.push(DelayedAction {
        action,
        action_type,
        arg,
        time,
    });
}

fn start_daemon(world: &mut PotionWorld, action: &'static str, arg: i32, action_type: i32) {
    world.actions.push(DelayedAction {
        action,
        action_type,
        arg,
        time: DAEMON,
    });
}

fn kill_daemon(world: &mut PotionWorld, action: &'static str) {
    if let Some(index) = world
        .actions
        .iter()
        .position(|delayed| delayed.action == action)
    {
        world.actions.remove(index);
    }
}

fn lengthen(world: &mut PotionWorld, action: &'static str, extra_time: i32) {
    if let Some(delayed) = world
        .actions
        .iter_mut()
        .find(|delayed| delayed.action == action)
    {
        delayed.time += extra_time;
    }
}

fn extinguish(world: &mut PotionWorld, action: &'static str) {
    if let Some(index) = world
        .actions
        .iter()
        .position(|delayed| delayed.action == action)
    {
        world.actions.remove(index);
    }
}

fn run_case(case: Case) -> Value {
    let mut world = world_for(&case);
    let result = match case.op {
        CaseOp::Quaff => {
            quaff(&mut world, case.obj);
            Value::Null
        }
        CaseOp::IsMagic => json!(is_magic(case.obj.as_ref().unwrap())),
    };
    json!({"name": case.name, "seed": case.seed, "result": result, "world": world_json(&world)})
}

#[derive(Clone, Copy)]
enum CaseOp {
    Quaff,
    IsMagic,
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    op: CaseOp,
    player_flags: i32,
    strength: i32,
    max_strength: i32,
    level: i32,
    exp: i32,
    hp: i32,
    max_hp: i32,
    no_command: i32,
    after: bool,
    current_weapon_is_obj: bool,
    left_ring: Option<SourceRing>,
    right_ring: Option<SourceRing>,
    pot_known: Vec<bool>,
    actions: Vec<DelayedAction>,
    magic_count: i32,
    new_monsters: i32,
    invisible_visible: i32,
    stairs_visible: bool,
    seenstairs: bool,
    proom_gone: bool,
    obj: Option<PotionObject>,
}

fn base_case(name: &'static str, seed: i32, op: CaseOp) -> Case {
    Case {
        name,
        seed,
        op,
        player_flags: 0,
        strength: 16,
        max_strength: 16,
        level: 5,
        exp: 100,
        hp: 12,
        max_hp: 20,
        no_command: 0,
        after: true,
        current_weapon_is_obj: false,
        left_ring: None,
        right_ring: None,
        pot_known: vec![false; MAXPOTIONS],
        actions: Vec::new(),
        magic_count: 0,
        new_monsters: 0,
        invisible_visible: 0,
        stairs_visible: false,
        seenstairs: false,
        proom_gone: false,
        obj: None,
    }
}

impl Case {
    fn player_flags(mut self, flags: i32) -> Self {
        self.player_flags = flags;
        self
    }
    fn strength(mut self, strength: i32, max_strength: i32) -> Self {
        self.strength = strength;
        self.max_strength = max_strength;
        self
    }
    fn level(mut self, level: i32, exp: i32, hp: i32, max_hp: i32) -> Self {
        self.level = level;
        self.exp = exp;
        self.hp = hp;
        self.max_hp = max_hp;
        self
    }
    fn after(mut self, after: bool) -> Self {
        self.after = after;
        self
    }
    fn current_weapon_is_obj(mut self) -> Self {
        self.current_weapon_is_obj = true;
        self
    }
    fn left_ring(mut self, ring: SourceRing) -> Self {
        self.left_ring = Some(ring);
        self
    }
    fn actions(mut self, actions: Vec<DelayedAction>) -> Self {
        self.actions = actions;
        self
    }
    fn magic_count(mut self, magic_count: i32) -> Self {
        self.magic_count = magic_count;
        self
    }
    fn new_monsters(mut self, new_monsters: i32) -> Self {
        self.new_monsters = new_monsters;
        self
    }
    fn invisible_visible(mut self, invisible_visible: i32) -> Self {
        self.invisible_visible = invisible_visible;
        self
    }
    fn stairs_visible(mut self) -> Self {
        self.stairs_visible = true;
        self
    }
    fn obj(mut self, obj: PotionObject) -> Self {
        self.obj = Some(obj);
        self
    }
}

fn cases() -> Vec<Case> {
    vec![
        base_case("quaff_non_potion_rejected", 1, CaseOp::Quaff).obj(object(':', 0, 1, 0, 0, 0, 0)),
        base_case("confuse_new", 1, CaseOp::Quaff).obj(potion(P_CONFUSE, 1)),
        base_case("confuse_lengthens", 1, CaseOp::Quaff)
            .player_flags(ISHUH)
            .actions(vec![action("unconfuse", AFTER, 0, 5)])
            .obj(potion(P_CONFUSE, 1)),
        base_case("poison_sustained", 1, CaseOp::Quaff)
            .left_ring(ring(R_SUSTSTR, 0))
            .obj(potion(P_POISON, 1)),
        base_case("poison_strength_loss_come_down", 1, CaseOp::Quaff)
            .player_flags(ISHALU)
            .strength(16, 16)
            .actions(vec![action("visuals", BEFORE, 0, DAEMON)])
            .obj(potion(P_POISON, 1)),
        base_case("healing_caps_hp", 1, CaseOp::Quaff)
            .level(4, 100, 19, 20)
            .obj(potion(P_HEALING, 1)),
        base_case("strength_updates_max", 1, CaseOp::Quaff)
            .strength(16, 16)
            .obj(potion(P_STRENGTH, 1)),
        base_case("mfind_fleeting", 1, CaseOp::Quaff)
            .new_monsters(0)
            .obj(potion(P_MFIND, 1)),
        base_case("mfind_reveals", 1, CaseOp::Quaff)
            .new_monsters(2)
            .obj(potion(P_MFIND, 1)),
        base_case("tfind_shows_magic", 1, CaseOp::Quaff)
            .magic_count(3)
            .obj(potion(P_TFIND, 1)),
        base_case("tfind_fleeting", 1, CaseOp::Quaff)
            .magic_count(0)
            .obj(potion(P_TFIND, 1)),
        base_case("lsd_starts_visuals", 1, CaseOp::Quaff)
            .player_flags(SEEMONST)
            .new_monsters(1)
            .stairs_visible()
            .obj(potion(P_LSD, 1)),
        base_case("seeinvis_new", 1, CaseOp::Quaff)
            .invisible_visible(2)
            .obj(potion(P_SEEINVIS, 1)),
        base_case("seeinvis_existing_blind", 1, CaseOp::Quaff)
            .player_flags(CANSEE | ISBLIND)
            .actions(vec![
                action("unsee", AFTER, 0, 5),
                action("sight", AFTER, 0, 5),
            ])
            .obj(potion(P_SEEINVIS, 1)),
        base_case("raise_level", 1, CaseOp::Quaff)
            .level(5, 100, 12, 20)
            .obj(potion(P_RAISE, 1)),
        base_case("xheal_big_come_down_blind", 1, CaseOp::Quaff)
            .player_flags(ISHALU | ISBLIND)
            .level(5, 100, 19, 20)
            .obj(potion(P_XHEAL, 1)),
        base_case("haste_new", 1, CaseOp::Quaff)
            .after(true)
            .obj(potion(P_HASTE, 1)),
        base_case("haste_exhaustion", 1, CaseOp::Quaff)
            .player_flags(ISHASTE | ISRUN)
            .actions(vec![action("nohaste", AFTER, 0, 5)])
            .obj(potion(P_HASTE, 1)),
        base_case("restore_with_addstr", 1, CaseOp::Quaff)
            .strength(10, 16)
            .left_ring(ring(R_ADDSTR, 2))
            .obj(potion(P_RESTORE, 1)),
        base_case("blind_new", 1, CaseOp::Quaff).obj(potion(P_BLIND, 1)),
        base_case("levit_new_unwields", 1, CaseOp::Quaff)
            .current_weapon_is_obj()
            .obj(potion(P_LEVIT, 1)),
        base_case("is_magic_protected_armor", 1, CaseOp::IsMagic)
            .obj(object(ARMOR, 0, 1, ISPROT, 8, 0, 0)),
        base_case("is_magic_plain_weapon", 1, CaseOp::IsMagic)
            .obj(object(WEAPON, 0, 1, 0, 0, 0, 0)),
        base_case("is_magic_enchanted_weapon", 1, CaseOp::IsMagic)
            .obj(object(WEAPON, 0, 1, 0, 0, 1, 0)),
        base_case("is_magic_ring", 1, CaseOp::IsMagic).obj(object(RING, 0, 1, 0, 0, 0, 0)),
    ]
}

fn potion(which: i32, count: i32) -> PotionObject {
    object(POTION, which, count, 0, 0, 0, 0)
}

fn object(
    obj_type: char,
    which: i32,
    count: i32,
    flags: i32,
    arm: i32,
    hplus: i32,
    dplus: i32,
) -> PotionObject {
    PotionObject {
        obj_type,
        which,
        count,
        flags,
        arm,
        hplus,
        dplus,
    }
}

fn ring(which: i32, arm: i32) -> SourceRing {
    SourceRing { which, arm }
}

fn action(action_name: &'static str, action_type: i32, arg: i32, time: i32) -> DelayedAction {
    DelayedAction {
        action: action_name,
        action_type,
        arg,
        time,
    }
}

fn world_for(case: &Case) -> PotionWorld {
    PotionWorld {
        rng: RogueRng::new(case.seed),
        player_flags: case.player_flags,
        strength: case.strength,
        max_strength: case.max_strength,
        level: case.level,
        exp: case.exp,
        hp: case.hp,
        max_hp: case.max_hp,
        no_command: case.no_command,
        after: case.after,
        current_weapon_is_obj: case.current_weapon_is_obj,
        left_ring: case.left_ring.clone(),
        right_ring: case.right_ring.clone(),
        pot_known: case.pot_known.clone(),
        actions: case.actions.clone(),
        magic_count: case.magic_count,
        new_monsters: case.new_monsters,
        invisible_visible: case.invisible_visible,
        stairs_visible: case.stairs_visible,
        seenstairs: case.seenstairs,
        proom_gone: case.proom_gone,
        markers: Vec::new(),
        trace: serde_json::Map::new(),
    }
}

fn action_json(action: &DelayedAction) -> Value {
    json!({"action": action.action, "type": action.action_type, "arg": action.arg, "time": action.time})
}

pub fn world_json(world: &PotionWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "player_flags": world.player_flags,
        "strength": world.strength,
        "max_strength": world.max_strength,
        "level": world.level,
        "exp": world.exp,
        "hp": world.hp,
        "max_hp": world.max_hp,
        "no_command": world.no_command,
        "after": world.after,
        "current_weapon_is_obj": world.current_weapon_is_obj,
        "pot_known": world.pot_known,
        "actions": world.actions.iter().map(action_json).collect::<Vec<_>>(),
        "seenstairs": world.seenstairs,
        "markers": world.markers,
        "trace": world.trace,
    })
}
