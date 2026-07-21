use crate::{RogueRng, STICK};
use serde_json::{json, Value};

const ISGONE: i32 = 0o000002;

const CANHUH: i32 = 0o000001;
const ISCANC: i32 = 0o000010;
const ISHASTE: i32 = 0o000100;
const ISHELD: i32 = 0o000400;
const ISINVIS: i32 = 0o002000;
const ISRUN: i32 = 0o020000;
const ISSLOW: i32 = 0o100000;

const ISKNOW: i32 = 0o000002;

const WS_LIGHT: i32 = 0;
const WS_INVIS: i32 = 1;
const WS_ELECT: i32 = 2;
const WS_FIRE: i32 = 3;
const WS_COLD: i32 = 4;
const WS_POLYMORPH: i32 = 5;
const WS_MISSILE: i32 = 6;
const WS_HASTE_M: i32 = 7;
const WS_SLOW_M: i32 = 8;
const WS_DRAIN: i32 = 9;
const WS_NOP: i32 = 10;
const WS_TELAWAY: i32 = 11;
const WS_TELTO: i32 = 12;
const WS_CANCEL: i32 = 13;
const MAXSTICKS: usize = 14;

#[derive(Clone)]
pub struct StickObject {
    pub obj_type: char,
    pub which: i32,
    pub charges: i32,
    pub flags: i32,
    pub damage: String,
    pub hurldmg: String,
    pub hplus: i32,
    pub dplus: i32,
    pub launch: i32,
    pub is_staff: bool,
}

#[derive(Clone)]
pub struct StickMonster {
    pub monster_type: char,
    pub hp: i32,
    pub flags: i32,
    pub disguise: Option<char>,
    pub oldch: char,
    pub pack_count: i32,
    pub turn: bool,
    pub dest_hero: bool,
    pub visible: bool,
    pub cansee: bool,
}

pub struct StickWorld {
    pub rng: RogueRng,
    pub after: bool,
    pub player_flags: i32,
    pub hero_hp: i32,
    pub proom_flags: i32,
    pub current_weapon_which: Option<i32>,
    pub target: Option<StickMonster>,
    pub drain_monsters: Vec<StickMonster>,
    pub save_throw_success: bool,
    pub ws_known: Vec<bool>,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_sticks_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_sticks.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

fn fix_stick(world: &mut StickWorld, obj: &mut StickObject) {
    obj.damage = if obj.is_staff {
        "2x3".to_string()
    } else {
        "1x1".to_string()
    };
    obj.hurldmg = "1x1".to_string();
    obj.charges = if obj.which == WS_LIGHT {
        world.rng.rnd(10) + 10
    } else {
        world.rng.rnd(5) + 3
    };
    world
        .trace
        .insert("charges".to_string(), json!(obj.charges));
}

pub fn do_zap(world: &mut StickWorld, obj: &mut StickObject) {
    if obj.obj_type != STICK {
        world.after = false;
        world.markers.push("cant_zap".to_string());
        return;
    }
    if obj.charges == 0 {
        world.markers.push("nothing_happens".to_string());
        return;
    }
    match obj.which {
        WS_LIGHT => {
            world.ws_known[WS_LIGHT as usize] = true;
            if world.proom_flags & ISGONE != 0 {
                world.markers.push("corridor_glows".to_string());
            } else {
                world.proom_flags &= !ISGONE;
                world.markers.push("enter_room".to_string());
                world.markers.push("room_lit".to_string());
            }
        }
        WS_DRAIN => {
            if world.hero_hp < 2 {
                world.markers.push("too_weak".to_string());
                return;
            }
            drain(world);
        }
        WS_INVIS | WS_POLYMORPH | WS_TELAWAY | WS_TELTO | WS_CANCEL => {
            zap_target_effect(world, obj.which)
        }
        WS_MISSILE => {
            world.ws_known[WS_MISSILE as usize] = true;
            world.trace.insert(
                "missile_launch".to_string(),
                json!(world.current_weapon_which),
            );
            if world.target.is_some() && !world.save_throw_success {
                world.markers.push("hit_monster:missile".to_string());
            } else if world.target.is_some() {
                world.markers.push("missile_misses".to_string());
            } else {
                world.markers.push("missile_vanishes".to_string());
            }
        }
        WS_HASTE_M | WS_SLOW_M => {
            if let Some(monster) = &mut world.target {
                if obj.which == WS_HASTE_M {
                    if monster.flags & ISSLOW != 0 {
                        monster.flags &= !ISSLOW;
                    } else {
                        monster.flags |= ISHASTE;
                    }
                } else {
                    if monster.flags & ISHASTE != 0 {
                        monster.flags &= !ISHASTE;
                    } else {
                        monster.flags |= ISSLOW;
                    }
                    monster.turn = true;
                }
                world.markers.push("runto".to_string());
            }
        }
        WS_ELECT | WS_FIRE | WS_COLD => {
            let name = if obj.which == WS_ELECT {
                "bolt"
            } else if obj.which == WS_FIRE {
                "flame"
            } else {
                "ice"
            };
            fire_bolt(world, name);
            world.ws_known[obj.which as usize] = true;
        }
        WS_NOP => {}
        _ => world.markers.push("bizarre_schtick".to_string()),
    }
    obj.charges -= 1;
}

fn zap_target_effect(world: &mut StickWorld, which: i32) {
    let Some(monster) = &mut world.target else {
        return;
    };
    if monster.monster_type == 'F' {
        world.player_flags &= !ISHELD;
    }
    match which {
        WS_INVIS => {
            monster.flags |= ISINVIS;
            if monster.cansee {
                world.markers.push("draw_oldch".to_string());
            }
        }
        WS_POLYMORPH => {
            let oldch = monster.oldch;
            let pack_count = monster.pack_count;
            if monster.visible {
                world.markers.push("erase_monster".to_string());
            }
            monster.monster_type =
                char::from_u32((world.rng.rnd(26) as u32) + ('A' as u32)).unwrap();
            monster.oldch = oldch;
            monster.pack_count = pack_count;
            world.trace.insert(
                "polymorph_type".to_string(),
                json!(monster.monster_type.to_string()),
            );
            if monster.visible {
                world.markers.push("draw_new_monster".to_string());
                world.ws_known[WS_POLYMORPH as usize] = true;
            }
        }
        WS_CANCEL => {
            monster.flags |= ISCANC;
            monster.flags &= !(ISINVIS | CANHUH);
            monster.disguise = Some(monster.monster_type);
            if monster.visible {
                world.markers.push("draw_disguise".to_string());
            }
        }
        WS_TELAWAY | WS_TELTO => {
            monster.dest_hero = true;
            monster.flags |= ISRUN;
            if which == WS_TELAWAY {
                world.markers.push("relocate:random_floor".to_string());
            } else {
                world.markers.push("relocate:adjacent".to_string());
            }
        }
        _ => {}
    }
}

fn drain(world: &mut StickWorld) {
    if world.drain_monsters.is_empty() {
        world.markers.push("tingling".to_string());
        return;
    }
    world.hero_hp /= 2;
    let amount = world.hero_hp / world.drain_monsters.len() as i32;
    world
        .trace
        .insert("drain_amount".to_string(), json!(amount));
    for monster in &mut world.drain_monsters {
        monster.hp -= amount;
        if monster.hp <= 0 {
            world
                .markers
                .push(format!("killed:{}", monster.monster_type));
        } else {
            world
                .markers
                .push(format!("runto:{}", monster.monster_type));
        }
    }
}

fn fire_bolt(world: &mut StickWorld, name: &str) {
    world.markers.push(format!("fire_bolt:{name}"));
}

fn charge_str(obj: &StickObject, terse: bool) -> String {
    if obj.flags & ISKNOW == 0 {
        String::new()
    } else if terse {
        format!(" [{}]", obj.charges)
    } else {
        format!(" [{} charges]", obj.charges)
    }
}

fn run_case(case: Case) -> Value {
    let mut world = world_for(&case);
    let mut obj = case.obj.clone();
    let result = match case.op {
        CaseOp::FixStick => {
            if let Some(obj) = &mut obj {
                fix_stick(&mut world, obj);
            }
            Value::Null
        }
        CaseOp::DoZap => {
            if let Some(obj) = &mut obj {
                do_zap(&mut world, obj);
            }
            Value::Null
        }
        CaseOp::ChargeStr => json!(charge_str(obj.as_ref().unwrap(), case.terse)),
    };
    json!({"name": case.name, "seed": case.seed, "result": result, "world": world_json(&world, obj.as_ref())})
}

#[derive(Clone, Copy)]
enum CaseOp {
    FixStick,
    DoZap,
    ChargeStr,
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    op: CaseOp,
    after: bool,
    player_flags: i32,
    hero_hp: i32,
    proom_flags: i32,
    current_weapon_which: Option<i32>,
    target: Option<StickMonster>,
    drain_monsters: Vec<StickMonster>,
    save_throw_success: bool,
    terse: bool,
    obj: Option<StickObject>,
}

fn base_case(name: &'static str, seed: i32, op: CaseOp) -> Case {
    Case {
        name,
        seed,
        op,
        after: true,
        player_flags: 0,
        hero_hp: 12,
        proom_flags: 0,
        current_weapon_which: None,
        target: None,
        drain_monsters: Vec::new(),
        save_throw_success: false,
        terse: false,
        obj: None,
    }
}

impl Case {
    fn player_flags(mut self, flags: i32) -> Self {
        self.player_flags = flags;
        self
    }
    fn hero_hp(mut self, hp: i32) -> Self {
        self.hero_hp = hp;
        self
    }
    fn proom_flags(mut self, flags: i32) -> Self {
        self.proom_flags = flags;
        self
    }
    fn current_weapon_which(mut self, which: i32) -> Self {
        self.current_weapon_which = Some(which);
        self
    }
    fn target(mut self, monster: StickMonster) -> Self {
        self.target = Some(monster);
        self
    }
    fn drain_monsters(mut self, monsters: Vec<StickMonster>) -> Self {
        self.drain_monsters = monsters;
        self
    }
    fn save_throw_success(mut self, success: bool) -> Self {
        self.save_throw_success = success;
        self
    }
    fn terse(mut self, terse: bool) -> Self {
        self.terse = terse;
        self
    }
    fn obj(mut self, obj: StickObject) -> Self {
        self.obj = Some(obj);
        self
    }
}

fn cases() -> Vec<Case> {
    vec![
        base_case("fix_light_wand", 1, CaseOp::FixStick).obj(stick(WS_LIGHT, 0).staff(false)),
        base_case("fix_staff_nonlight", 1, CaseOp::FixStick).obj(stick(WS_FIRE, 0).staff(true)),
        base_case("zap_non_stick", 1, CaseOp::DoZap).obj(object('!', WS_LIGHT, 1)),
        base_case("zap_empty", 1, CaseOp::DoZap).obj(stick(WS_LIGHT, 0)),
        base_case("light_room", 1, CaseOp::DoZap)
            .proom_flags(0)
            .obj(stick(WS_LIGHT, 2)),
        base_case("light_corridor", 1, CaseOp::DoZap)
            .proom_flags(ISGONE)
            .obj(stick(WS_LIGHT, 2)),
        base_case("drain_too_weak", 1, CaseOp::DoZap)
            .hero_hp(1)
            .obj(stick(WS_DRAIN, 2)),
        base_case("drain_no_monsters", 1, CaseOp::DoZap)
            .hero_hp(12)
            .obj(stick(WS_DRAIN, 2)),
        base_case("drain_hits_monsters", 1, CaseOp::DoZap)
            .hero_hp(20)
            .drain_monsters(vec![monster('K', 4), monster('O', 10)])
            .obj(stick(WS_DRAIN, 2)),
        base_case("invis_flytrap_unholds", 1, CaseOp::DoZap)
            .player_flags(ISHELD)
            .target(monster('F', 8))
            .obj(stick(WS_INVIS, 2)),
        base_case("polymorph_visible", 1, CaseOp::DoZap)
            .target(monster('K', 8).oldch('.').pack_count(2).visible(true))
            .obj(stick(WS_POLYMORPH, 2)),
        base_case("cancel_invisible_confuser", 1, CaseOp::DoZap)
            .target(monster('M', 8).flags(ISINVIS | CANHUH))
            .obj(stick(WS_CANCEL, 2)),
        base_case("telaway_sets_run", 1, CaseOp::DoZap)
            .target(monster('K', 8))
            .obj(stick(WS_TELAWAY, 2)),
        base_case("telto_sets_run", 1, CaseOp::DoZap)
            .target(monster('K', 8))
            .obj(stick(WS_TELTO, 2)),
        base_case("missile_hits", 1, CaseOp::DoZap)
            .current_weapon_which(3)
            .target(monster('K', 8))
            .save_throw_success(false)
            .obj(stick(WS_MISSILE, 2)),
        base_case("missile_misses", 1, CaseOp::DoZap)
            .target(monster('K', 8))
            .save_throw_success(true)
            .obj(stick(WS_MISSILE, 2)),
        base_case("haste_clears_slow", 1, CaseOp::DoZap)
            .target(monster('K', 8).flags(ISSLOW))
            .obj(stick(WS_HASTE_M, 2)),
        base_case("haste_sets_haste", 1, CaseOp::DoZap)
            .target(monster('K', 8))
            .obj(stick(WS_HASTE_M, 2)),
        base_case("slow_clears_haste", 1, CaseOp::DoZap)
            .target(monster('K', 8).flags(ISHASTE))
            .obj(stick(WS_SLOW_M, 2)),
        base_case("slow_sets_slow_turn", 1, CaseOp::DoZap)
            .target(monster('K', 8))
            .obj(stick(WS_SLOW_M, 2)),
        base_case("fire_bolt", 1, CaseOp::DoZap).obj(stick(WS_FIRE, 2)),
        base_case("cold_bolt", 1, CaseOp::DoZap).obj(stick(WS_COLD, 2)),
        base_case("nop_consumes_charge", 1, CaseOp::DoZap).obj(stick(WS_NOP, 2)),
        base_case("charge_unknown", 1, CaseOp::ChargeStr).obj(stick(WS_LIGHT, 7).flags(0)),
        base_case("charge_known_verbose", 1, CaseOp::ChargeStr)
            .obj(stick(WS_LIGHT, 7).flags(ISKNOW))
            .terse(false),
        base_case("charge_known_terse", 1, CaseOp::ChargeStr)
            .obj(stick(WS_LIGHT, 7).flags(ISKNOW))
            .terse(true),
    ]
}

fn object(obj_type: char, which: i32, charges: i32) -> StickObject {
    StickObject {
        obj_type,
        which,
        charges,
        flags: 0,
        damage: String::new(),
        hurldmg: String::new(),
        hplus: 0,
        dplus: 0,
        launch: -1,
        is_staff: false,
    }
}

fn stick(which: i32, charges: i32) -> StickObject {
    object(STICK, which, charges)
}

impl StickObject {
    fn staff(mut self, is_staff: bool) -> Self {
        self.is_staff = is_staff;
        self
    }
    fn flags(mut self, flags: i32) -> Self {
        self.flags = flags;
        self
    }
}

fn monster(monster_type: char, hp: i32) -> StickMonster {
    StickMonster {
        monster_type,
        hp,
        flags: 0,
        disguise: None,
        oldch: '.',
        pack_count: 0,
        turn: false,
        dest_hero: false,
        visible: true,
        cansee: true,
    }
}

impl StickMonster {
    fn flags(mut self, flags: i32) -> Self {
        self.flags = flags;
        self
    }
    fn oldch(mut self, oldch: char) -> Self {
        self.oldch = oldch;
        self
    }
    fn pack_count(mut self, count: i32) -> Self {
        self.pack_count = count;
        self
    }
    fn visible(mut self, visible: bool) -> Self {
        self.visible = visible;
        self
    }
}

fn world_for(case: &Case) -> StickWorld {
    StickWorld {
        rng: RogueRng::new(case.seed),
        after: case.after,
        player_flags: case.player_flags,
        hero_hp: case.hero_hp,
        proom_flags: case.proom_flags,
        current_weapon_which: case.current_weapon_which,
        target: case.target.clone(),
        drain_monsters: case.drain_monsters.clone(),
        save_throw_success: case.save_throw_success,
        ws_known: vec![false; MAXSTICKS],
        markers: Vec::new(),
        trace: serde_json::Map::new(),
    }
}

fn object_json(obj: &StickObject) -> Value {
    json!({
        "type": obj.obj_type.to_string(),
        "which": obj.which,
        "charges": obj.charges,
        "flags": obj.flags,
        "damage": obj.damage,
        "hurldmg": obj.hurldmg,
        "hplus": obj.hplus,
        "dplus": obj.dplus,
        "launch": obj.launch,
        "is_staff": obj.is_staff,
    })
}

fn monster_json(monster: &StickMonster) -> Value {
    json!({
        "type": monster.monster_type.to_string(),
        "hp": monster.hp,
        "flags": monster.flags,
        "disguise": monster.disguise.map(|ch| ch.to_string()),
        "oldch": monster.oldch.to_string(),
        "pack_count": monster.pack_count,
        "turn": monster.turn,
        "dest_hero": monster.dest_hero,
        "visible": monster.visible,
        "cansee": monster.cansee,
    })
}

pub fn world_json(world: &StickWorld, obj: Option<&StickObject>) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "after": world.after,
        "player_flags": world.player_flags,
        "hero_hp": world.hero_hp,
        "proom_flags": world.proom_flags,
        "current_weapon_which": world.current_weapon_which,
        "object": obj.map(object_json),
        "target": world.target.as_ref().map(monster_json),
        "drain_monsters": world.drain_monsters.iter().map(monster_json).collect::<Vec<_>>(),
        "ws_known": world.ws_known,
        "markers": world.markers,
        "trace": world.trace,
    })
}
