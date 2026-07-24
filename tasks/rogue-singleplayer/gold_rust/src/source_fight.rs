use crate::{RogueRng, GOLD, WEAPON};
use serde_json::{json, Value};

const CANHUH: i32 = 0o000001;
const ISBLIND: i32 = 0o000004;
const ISMISL: i32 = 0o000004;
const ISTARGET: i32 = 0o000200;
const ISHELD: i32 = 0o000400;
const ISHUH: i32 = 0o001000;
const ISHALU: i32 = 0o004000;
pub const ISRUN: i32 = 0o020000;

const NO_WEAPON: i32 = -1;
const BOW: i32 = 2;
const ARROW: i32 = 3;
const VS_MAGIC: i32 = 3;

const STR_PLUS: [i32; 32] = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 3,
];
const ADD_DAM: [i32; 32] = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 6,
];
pub const E_LEVELS: [i32; 21] = [
    10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000,
    800000, 2000000, 4000000, 8000000, 0,
];

#[derive(Clone)]
pub struct FightStats {
    pub strength: i32,
    pub exp: i32,
    pub level: i32,
    pub arm: i32,
    pub hp: i32,
    pub damage: String,
    pub max_hp: i32,
    pub flags: i32,
}

#[derive(Clone)]
pub struct FightWeapon {
    pub which: i32,
    pub hplus: i32,
    pub dplus: i32,
    pub damage: String,
    pub hurl_damage: String,
    pub launch: i32,
    pub flags: i32,
}

#[derive(Clone)]
pub struct FightObject {
    pub obj_type: char,
    pub name: String,
    pub goldval: i32,
}

#[derive(Clone)]
pub struct FightMonster {
    pub monster_type: char,
    pub stats: FightStats,
    pub flags: i32,
    pub disguise: Option<char>,
    pub pack: Vec<FightObject>,
    pub oldch: char,
}

pub struct FightWorld {
    pub rng: RogueRng,
    pub player: FightStats,
    pub player_flags: i32,
    pub current_weapon: Option<FightWeapon>,
    pub count: i32,
    pub quiet: i32,
    pub terse: bool,
    pub to_death: bool,
    pub has_hit: bool,
    pub fight_flush: bool,
    pub level: i32,
    pub max_level: i32,
    pub max_hp: i32,
    pub vf_hit: i32,
    pub fallpos_ok: bool,
    pub monster_present: bool,
    pub markers: Vec<String>,
    pub dropped: Vec<FightObject>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_fight_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_fight.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn fight(
    world: &mut FightWorld,
    monster: &mut FightMonster,
    weapon: Option<&FightWeapon>,
    thrown: bool,
) -> bool {
    world.count = 0;
    world.quiet = 0;
    world.markers.push("runto".to_string());
    if monster.monster_type == 'X'
        && monster.disguise != Some('X')
        && world.player_flags & ISBLIND == 0
    {
        monster.disguise = Some('X');
        world.markers.push("xeroc_reveal".to_string());
        if world.player_flags & ISHALU != 0 {
            let hallu = char::from_u32((world.rng.rnd(26) as u32) + ('A' as u32)).unwrap();
            world
                .trace
                .insert("xeroc_hallu".to_string(), json!(hallu.to_string()));
        }
        if !thrown {
            return false;
        }
    }

    world.has_hit = world.terse && !world.to_death;
    let result = roll_em(
        &mut world.rng,
        &world.player,
        &mut monster.stats,
        weapon,
        thrown,
        world.current_weapon.as_ref(),
    );
    world
        .trace
        .insert("roll_hit".to_string(), json!(result.did_hit));
    world
        .trace
        .insert("roll_rng".to_string(), json!(world.rng.seed));
    if result.did_hit {
        if thrown {
            world.markers.push("thunk".to_string());
        } else {
            world.markers.push("hit".to_string());
        }
        let mut did_confuse = false;
        if world.player_flags & CANHUH != 0 {
            did_confuse = true;
            monster.flags |= ISHUH;
            world.player_flags &= !CANHUH;
            world.markers.push("endmsg".to_string());
            world.markers.push("hands_stop_glowing".to_string());
            world.has_hit = false;
        }
        if monster.stats.hp <= 0 {
            killed(world, monster, true);
        } else if did_confuse && world.player_flags & ISBLIND == 0 {
            world.markers.push("appears_confused".to_string());
        }
        true
    } else {
        if thrown {
            world.markers.push("bounce".to_string());
        } else {
            world.markers.push("miss".to_string());
        }
        false
    }
}

fn killed(world: &mut FightWorld, monster: &mut FightMonster, pr: bool) {
    world.player.exp += monster.stats.exp;
    if monster.monster_type == 'F' {
        world.player_flags &= !ISHELD;
        world.vf_hit = 0;
        monster.stats.damage = "000x0".to_string();
    }
    if monster.monster_type == 'L' && world.fallpos_ok && world.level >= world.max_level {
        let mut goldval = world.rng.gold_calc(world.level);
        let saved = save_magic(world);
        world
            .trace
            .insert("leprechaun_gold_saved".to_string(), json!(saved));
        if saved {
            for _ in 0..4 {
                goldval += world.rng.gold_calc(world.level);
            }
        }
        monster.pack.insert(
            0,
            FightObject {
                obj_type: GOLD,
                name: "gold".to_string(),
                goldval,
            },
        );
    }
    remove_mon(world, monster, true);
    if pr {
        if world.has_hit {
            world.markers.push("defeated_join".to_string());
            world.has_hit = false;
        } else {
            world.markers.push("defeated".to_string());
        }
    }
    check_level(world);
    if world.fight_flush {
        world.markers.push("flush_type".to_string());
    }
}

fn remove_mon(world: &mut FightWorld, monster: &mut FightMonster, waskill: bool) {
    let pack = std::mem::take(&mut monster.pack);
    for obj in pack {
        if waskill {
            world.markers.push(format!("fall:{}", obj.name));
            world.dropped.push(obj);
        } else {
            world.markers.push(format!("discard:{}", obj.name));
        }
    }
    world.monster_present = false;
    world.markers.push(format!("mvaddch:{}", monster.oldch));
    world.markers.push("detach_monster".to_string());
    if monster.flags & ISTARGET != 0 {
        world
            .trace
            .insert("target_removed".to_string(), json!(true));
        world.to_death = false;
        if world.fight_flush {
            world.markers.push("flush_type".to_string());
        }
    }
    world.markers.push("discard_monster".to_string());
}

struct RollResult {
    did_hit: bool,
}

fn roll_em(
    rng: &mut RogueRng,
    attacker: &FightStats,
    defender: &mut FightStats,
    weapon: Option<&FightWeapon>,
    hurl: bool,
    current_weapon: Option<&FightWeapon>,
) -> RollResult {
    let (damage_expression, mut hplus, dplus) = if let Some(weap) = weapon {
        let mut hplus = weap.hplus;
        let mut dplus = weap.dplus;
        let mut expression = weap.damage.clone();
        if hurl {
            if weap.flags & ISMISL != 0 {
                if let Some(current) = current_weapon {
                    if current.which == weap.launch {
                        expression = weap.hurl_damage.clone();
                        hplus += current.hplus;
                        dplus += current.dplus;
                    }
                }
            } else if weap.launch < 0 {
                expression = weap.hurl_damage.clone();
            }
        }
        (expression, hplus, dplus)
    } else {
        (attacker.damage.clone(), 0, 0)
    };
    if defender.flags & ISRUN == 0 {
        hplus += 4;
    }
    let mut did_hit = false;
    for (ndice, nsides) in damage_terms(&damage_expression) {
        let swing_roll = rng.rnd(20);
        let need = (20 - attacker.level) - defender.arm;
        if swing_roll + hplus + STR_PLUS[attacker.strength as usize] >= need {
            let damage_roll = rng.roll(ndice, nsides);
            let damage = dplus + damage_roll + ADD_DAM[attacker.strength as usize];
            defender.hp -= damage.max(0);
            did_hit = true;
        }
    }
    RollResult { did_hit }
}

fn check_level(world: &mut FightWorld) {
    let mut next_level = 1;
    for threshold in E_LEVELS {
        if threshold == 0 || threshold > world.player.exp {
            break;
        }
        next_level += 1;
    }
    let old_level = world.player.level;
    world.player.level = next_level;
    if next_level > old_level {
        let add = world.rng.roll(next_level - old_level, 10);
        world.max_hp += add;
        world.player.hp += add;
        world.markers.push(format!("welcome:{}", next_level));
        world.trace.insert("level_add".to_string(), json!(add));
    }
}

fn save_magic(world: &mut FightWorld) -> bool {
    let need = 14 + VS_MAGIC - world.player.level / 2;
    let roll = world.rng.roll(1, 20);
    world
        .trace
        .insert("magic_save_roll".to_string(), json!(roll));
    roll >= need
}

fn damage_terms(expression: &str) -> Vec<(i32, i32)> {
    expression
        .split('/')
        .filter_map(|part| {
            let (ndice, nsides) = part.split_once('x')?;
            Some((ndice.parse().unwrap(), nsides.parse().unwrap()))
        })
        .collect()
}

fn run_case(case: Case) -> Value {
    let mut world = world_for(&case);
    let mut monster = FightMonster {
        monster_type: case.monster_type,
        stats: case.monster_stats,
        flags: case.monster_flags,
        disguise: case.disguise,
        pack: case.monster_pack,
        oldch: case.oldch,
    };
    let returned = fight(&mut world, &mut monster, case.weapon.as_ref(), case.thrown);
    json!({"name": case.name, "seed": case.seed, "returned": returned, "monster": monster_json(&monster), "world": world_json(&world)})
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    monster_type: char,
    monster_stats: FightStats,
    monster_flags: i32,
    disguise: Option<char>,
    monster_pack: Vec<FightObject>,
    oldch: char,
    player_stats: FightStats,
    player_flags: i32,
    current_weapon: Option<FightWeapon>,
    weapon: Option<FightWeapon>,
    thrown: bool,
    count: i32,
    quiet: i32,
    terse: bool,
    to_death: bool,
    has_hit: bool,
    fight_flush: bool,
    level: i32,
    max_level: i32,
    max_hp: i32,
    vf_hit: i32,
    fallpos_ok: bool,
}

fn base_case(name: &'static str, seed: i32, monster_type: char) -> Case {
    Case {
        name,
        seed,
        monster_type,
        monster_stats: stats(16, 0, 5, 6, 30, "1x1", 30, ISRUN),
        monster_flags: ISRUN,
        disguise: Some(monster_type),
        monster_pack: Vec::new(),
        oldch: '.',
        player_stats: stats(16, 0, 5, 6, 30, "1x1", 30, ISRUN),
        player_flags: ISRUN,
        current_weapon: None,
        weapon: None,
        thrown: false,
        count: 4,
        quiet: 7,
        terse: false,
        to_death: false,
        has_hit: false,
        fight_flush: true,
        level: 1,
        max_level: 1,
        max_hp: 30,
        vf_hit: 0,
        fallpos_ok: false,
    }
}

impl Case {
    fn monster_stats(mut self, stats: FightStats) -> Self {
        self.monster_stats = stats;
        self
    }
    fn monster_flags(mut self, flags: i32) -> Self {
        self.monster_flags = flags;
        self
    }
    fn disguise(mut self, disguise: char) -> Self {
        self.disguise = Some(disguise);
        self
    }
    fn monster_pack(mut self, pack: Vec<FightObject>) -> Self {
        self.monster_pack = pack;
        self
    }
    fn player_stats(mut self, stats: FightStats) -> Self {
        self.max_hp = stats.max_hp;
        self.player_stats = stats;
        self
    }
    fn player_flags(mut self, flags: i32) -> Self {
        self.player_flags = flags;
        self
    }
    fn current_weapon(mut self, weapon: FightWeapon) -> Self {
        self.current_weapon = Some(weapon);
        self
    }
    fn weapon(mut self, weapon: FightWeapon) -> Self {
        self.weapon = Some(weapon);
        self
    }
    fn thrown(mut self, thrown: bool) -> Self {
        self.thrown = thrown;
        self
    }
    fn to_death(mut self, to_death: bool) -> Self {
        self.to_death = to_death;
        self
    }
    fn max_hp(mut self, max_hp: i32) -> Self {
        self.max_hp = max_hp;
        self
    }
    fn vf_hit(mut self, vf_hit: i32) -> Self {
        self.vf_hit = vf_hit;
        self
    }
    fn fallpos_ok(mut self, fallpos_ok: bool) -> Self {
        self.fallpos_ok = fallpos_ok;
        self
    }
    fn level(mut self, level: i32, max_level: i32) -> Self {
        self.level = level;
        self.max_level = max_level;
        self
    }
}

fn cases() -> Vec<Case> {
    let hard_to_hit = stats(16, 0, 1, -10, 30, "1x1", 30, ISRUN);
    vec![
        base_case("xeroc_melee_reveal_returns_false", 1, 'X')
            .disguise('A')
            .player_flags(ISRUN | ISHALU)
            .monster_stats(hard_to_hit.clone()),
        base_case("thrown_xeroc_continues_hits", 1, 'X')
            .disguise('A')
            .monster_stats(stats(16, 0, 5, 20, 30, "1x1", 30, ISRUN))
            .thrown(true)
            .weapon(weapon(
                WEAPON, ARROW, 0, 0, "1x1", "2x3", BOW, ISMISL, "arrow",
            ))
            .current_weapon(weapon(WEAPON, BOW, 1, 2, "1x1", "1x1", NO_WEAPON, 0, "bow")),
        base_case("melee_miss", 7, 'K').monster_stats(hard_to_hit),
        base_case("canhuh_confuses_monster", 1, 'K')
            .player_flags(ISRUN | CANHUH)
            .monster_stats(stats(16, 0, 5, 20, 30, "1x1", 30, ISRUN)),
        base_case("kill_regular_levels_up", 1, 'K')
            .player_stats(stats(16, 9, 1, 6, 12, "1x1", 12, ISRUN))
            .monster_stats(stats(16, 20, 5, 20, 1, "1x1", 30, ISRUN))
            .max_hp(12),
        base_case("kill_flytrap_unholds", 1, 'F')
            .player_flags(ISRUN | ISHELD)
            .monster_stats(stats(16, 5, 5, 20, 1, "1x1", 30, ISRUN))
            .vf_hit(3),
        base_case("kill_leprechaun_drops_gold", 1, 'L')
            .player_stats(stats(16, 0, 10, 6, 30, "1x1", 30, ISRUN))
            .monster_stats(stats(16, 10, 5, 20, 1, "1x1", 30, ISRUN))
            .level(8, 8)
            .fallpos_ok(true),
        base_case("kill_target_clears_to_death", 1, 'K')
            .monster_flags(ISRUN | ISTARGET)
            .monster_stats(stats(16, 1, 5, 20, 1, "1x1", 30, ISRUN))
            .to_death(true),
        base_case("remove_mon_drops_pack", 1, 'K')
            .monster_stats(stats(16, 1, 5, 20, 1, "1x1", 30, ISRUN))
            .monster_pack(vec![object(WEAPON, "club", 0), object(GOLD, "gold", 12)]),
    ]
}

fn world_for(case: &Case) -> FightWorld {
    FightWorld {
        rng: RogueRng::new(case.seed),
        player: case.player_stats.clone(),
        player_flags: case.player_flags,
        current_weapon: case.current_weapon.clone(),
        count: case.count,
        quiet: case.quiet,
        terse: case.terse,
        to_death: case.to_death,
        has_hit: case.has_hit,
        fight_flush: case.fight_flush,
        level: case.level,
        max_level: case.max_level,
        max_hp: case.max_hp,
        vf_hit: case.vf_hit,
        fallpos_ok: case.fallpos_ok,
        monster_present: true,
        markers: Vec::new(),
        dropped: Vec::new(),
        trace: serde_json::Map::new(),
    }
}

fn stats(
    strength: i32,
    exp: i32,
    level: i32,
    arm: i32,
    hp: i32,
    damage: &str,
    max_hp: i32,
    flags: i32,
) -> FightStats {
    FightStats {
        strength,
        exp,
        level,
        arm,
        hp,
        damage: damage.to_string(),
        max_hp,
        flags,
    }
}

fn weapon(
    _obj_type: char,
    which: i32,
    hplus: i32,
    dplus: i32,
    damage: &str,
    hurl_damage: &str,
    launch: i32,
    flags: i32,
    _name: &'static str,
) -> FightWeapon {
    FightWeapon {
        which,
        hplus,
        dplus,
        damage: damage.to_string(),
        hurl_damage: hurl_damage.to_string(),
        launch,
        flags,
    }
}

fn object(obj_type: char, name: &'static str, goldval: i32) -> FightObject {
    FightObject {
        obj_type,
        name: name.to_string(),
        goldval,
    }
}

fn stats_json(stats: &FightStats) -> Value {
    json!({
        "strength": stats.strength,
        "exp": stats.exp,
        "level": stats.level,
        "arm": stats.arm,
        "hp": stats.hp,
        "damage": stats.damage,
        "max_hp": stats.max_hp,
        "flags": stats.flags,
    })
}

fn object_json(obj: &FightObject) -> Value {
    json!({"type": obj.obj_type.to_string(), "name": obj.name, "goldval": obj.goldval})
}

pub fn monster_json(monster: &FightMonster) -> Value {
    json!({
        "type": monster.monster_type.to_string(),
        "stats": stats_json(&monster.stats),
        "flags": monster.flags,
        "disguise": monster.disguise.map(|ch| ch.to_string()),
        "pack": monster.pack.iter().map(object_json).collect::<Vec<_>>(),
        "oldch": monster.oldch.to_string(),
    })
}

pub fn world_json(world: &FightWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "player": stats_json(&world.player),
        "player_flags": world.player_flags,
        "count": world.count,
        "quiet": world.quiet,
        "terse": world.terse,
        "to_death": world.to_death,
        "has_hit": world.has_hit,
        "level": world.level,
        "max_level": world.max_level,
        "max_hp": world.max_hp,
        "vf_hit": world.vf_hit,
        "monster_present": world.monster_present,
        "markers": world.markers,
        "dropped": world.dropped.iter().map(object_json).collect::<Vec<_>>(),
        "trace": world.trace,
    })
}
