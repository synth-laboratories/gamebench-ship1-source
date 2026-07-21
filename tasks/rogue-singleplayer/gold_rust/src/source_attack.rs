use crate::RogueRng;
use serde_json::{json, Value};

const VS_POISON: i32 = 0;
const VS_MAGIC: i32 = 3;

const ISBLIND: i32 = 0o000004;
const ISCANC: i32 = 0o000010;
const ISTARGET: i32 = 0o000200;
const ISHELD: i32 = 0o000400;
const ISHALU: i32 = 0o004000;
pub const ISRUN: i32 = 0o020000;

const R_PROTECT: i32 = 0;
const BORE_LEVEL: i32 = 50;

const AMULET: char = ',';
const ARMOR: char = ']';
const POTION: char = '!';
const RING: char = '=';
const SCROLL: char = '?';
const STICK: char = '/';
const WEAPON: char = ')';

const STR_PLUS: [i32; 32] = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 3,
];
const ADD_DAM: [i32; 32] = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 6,
];
const E_LEVELS: [i32; 21] = [
    10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000,
    800000, 2000000, 4000000, 8000000, 0,
];

#[derive(Clone)]
pub struct Stats {
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
pub struct RingObj {
    pub which: i32,
    pub arm: i32,
}

#[derive(Clone)]
pub struct AttackItem {
    pub name: String,
    pub obj_type: char,
    pub magic: bool,
    pub equipped: bool,
}

#[derive(Clone)]
pub struct AttackMonster {
    pub monster_type: char,
    pub stats: Stats,
    pub flags: i32,
    pub disguise: Option<char>,
}

pub struct AttackWorld {
    pub rng: RogueRng,
    pub player: Stats,
    pub player_flags: i32,
    pub current_armor_arm: Option<i32>,
    pub left_ring: Option<RingObj>,
    pub right_ring: Option<RingObj>,
    pub sustain_strength: bool,
    pub running: bool,
    pub count: i32,
    pub quiet: i32,
    pub to_death: bool,
    pub kamikaze: bool,
    pub has_hit: bool,
    pub max_hit: i32,
    pub no_command: i32,
    pub purse: i32,
    pub level: i32,
    pub max_hp: i32,
    pub vf_hit: i32,
    pub fight_flush: bool,
    pub pack: Vec<AttackItem>,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_attack_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_attack.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn attack(world: &mut AttackWorld, monster: &mut AttackMonster) -> i32 {
    world.running = false;
    world.count = 0;
    world.quiet = 0;
    if world.to_death && monster.flags & ISTARGET == 0 {
        world.to_death = false;
        world.kamikaze = false;
        world
            .trace
            .insert("target_cancelled".to_string(), json!(true));
    }
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
    }

    let oldhp = world.player.hp;
    let result = roll_em(
        world.rng.seed,
        &monster.stats,
        &world.player,
        world.current_armor_arm,
        world.left_ring.as_ref(),
        world.right_ring.as_ref(),
    );
    world.rng.seed = result.rng_seed;
    world.player = result.defender;
    world
        .trace
        .insert("roll_hit".to_string(), json!(result.did_hit));
    world
        .trace
        .insert("roll_rng".to_string(), json!(result.rng_seed));

    let mut monster_removed = false;
    if result.did_hit {
        if monster.monster_type != 'I' {
            if world.has_hit {
                world.markers.push("addmsg_join".to_string());
            }
            world.markers.push("hit".to_string());
        } else if world.has_hit {
            world.markers.push("endmsg".to_string());
        }
        world.has_hit = false;
        if world.player.hp <= 0 {
            world
                .markers
                .push(format!("death:{}", monster.monster_type));
        } else if !world.kamikaze {
            let damage = oldhp - world.player.hp;
            if damage > world.max_hit {
                world.max_hit = damage;
            }
            if world.player.hp <= world.max_hit {
                world.to_death = false;
            }
        }
        if monster.flags & ISCANC == 0 {
            monster_removed = special_hit(world, monster);
        }
    } else if monster.monster_type != 'I' {
        if world.has_hit {
            world.markers.push("addmsg_join".to_string());
            world.has_hit = false;
        }
        if monster.monster_type == 'F' {
            world.player.hp -= world.vf_hit;
            if world.player.hp <= 0 {
                world.markers.push("death:F".to_string());
            }
        }
        world.markers.push("miss".to_string());
    }

    if world.fight_flush && !world.to_death {
        world.markers.push("flush_type".to_string());
    }
    world.count = 0;
    world.markers.push("status".to_string());
    if monster_removed {
        -1
    } else {
        0
    }
}

fn special_hit(world: &mut AttackWorld, monster: &mut AttackMonster) -> bool {
    match monster.monster_type {
        'A' => world.markers.push("rust_armor".to_string()),
        'I' => {
            world.player_flags &= !ISRUN;
            if world.no_command == 0 {
                world.markers.push("freeze_msg".to_string());
            }
            let freeze_roll = world.rng.rnd(2) + 2;
            world
                .trace
                .insert("ice_roll".to_string(), json!(freeze_roll));
            world.no_command += freeze_roll;
            if world.no_command > BORE_LEVEL {
                world.markers.push("death:h".to_string());
            }
        }
        'R' => {
            let payload = save(world, VS_POISON);
            world
                .trace
                .insert("poison_saved".to_string(), json!(payload.saved));
            world
                .trace
                .insert("poison_roll".to_string(), json!(payload.roll));
            if !payload.saved {
                if !world.sustain_strength {
                    world.player.strength -= 1;
                    world.markers.push("chg_str:-1".to_string());
                } else if !world.to_death {
                    world.markers.push("sustain_strength".to_string());
                }
            }
        }
        'W' | 'V' => {
            let drain_roll = world.rng.rnd(100);
            world
                .trace
                .insert("drain_roll".to_string(), json!(drain_roll));
            let threshold = if monster.monster_type == 'W' { 15 } else { 30 };
            if drain_roll < threshold {
                let fewer = if monster.monster_type == 'W' {
                    if world.player.exp == 0 {
                        world.markers.push("death:W".to_string());
                    }
                    world.player.level -= 1;
                    if world.player.level == 0 {
                        world.player.exp = 0;
                        world.player.level = 1;
                    } else {
                        world.player.exp = E_LEVELS[(world.player.level - 1) as usize] + 1;
                    }
                    world.rng.roll(1, 10)
                } else {
                    world.rng.roll(1, 3)
                };
                world.trace.insert("drain_fewer".to_string(), json!(fewer));
                world.player.hp -= fewer;
                world.max_hp -= fewer;
                if world.player.hp <= 0 {
                    world.player.hp = 1;
                }
                if world.max_hp <= 0 {
                    world
                        .markers
                        .push(format!("death:{}", monster.monster_type));
                }
                world.markers.push("drain".to_string());
            }
        }
        'F' => {
            world.player_flags |= ISHELD;
            world.vf_hit += 1;
            monster.stats.damage = format!("{}x1", world.vf_hit);
            world.player.hp -= 1;
            if world.player.hp <= 0 {
                world.markers.push("death:F".to_string());
            }
        }
        'L' => {
            let lastpurse = world.purse;
            world.purse -= world.rng.gold_calc(world.level);
            let payload = save(world, VS_MAGIC);
            world
                .trace
                .insert("gold_saved".to_string(), json!(payload.saved));
            world
                .trace
                .insert("gold_save_roll".to_string(), json!(payload.roll));
            if !payload.saved {
                for _ in 0..4 {
                    world.purse -= world.rng.gold_calc(world.level);
                }
            }
            if world.purse < 0 {
                world.purse = 0;
            }
            world.markers.push("remove_mon".to_string());
            if world.purse != lastpurse {
                world.markers.push("purse_lighter".to_string());
            }
            return true;
        }
        'N' => {
            if let Some(stolen_index) = pick_nymph_steal(world) {
                let stolen = world.pack.remove(stolen_index);
                world.trace.insert("stolen".to_string(), json!(stolen.name));
                world.markers.push("remove_mon".to_string());
                world.markers.push("leave_pack".to_string());
                world.markers.push("discard".to_string());
                return true;
            }
        }
        _ => {}
    }
    false
}

struct SavePayload {
    roll: i32,
    saved: bool,
}

fn save(world: &mut AttackWorld, which: i32) -> SavePayload {
    let mut adjusted = which;
    if which == VS_MAGIC {
        if let Some(left) = &world.left_ring {
            if left.which == R_PROTECT {
                adjusted -= left.arm;
            }
        }
        if let Some(right) = &world.right_ring {
            if right.which == R_PROTECT {
                adjusted -= right.arm;
            }
        }
    }
    let need = 14 + adjusted - world.player.level / 2;
    let roll = world.rng.roll(1, 20);
    SavePayload {
        roll,
        saved: roll >= need,
    }
}

fn pick_nymph_steal(world: &mut AttackWorld) -> Option<usize> {
    let mut steal_index = None;
    let mut nobj = 0;
    for (index, item) in world.pack.iter().enumerate() {
        if item.equipped || !is_magic(item) {
            continue;
        }
        nobj += 1;
        if world.rng.rnd(nobj) == 0 {
            steal_index = Some(index);
        }
    }
    steal_index
}

fn is_magic(item: &AttackItem) -> bool {
    matches!(item.obj_type, POTION | SCROLL | STICK | RING | AMULET)
        || (matches!(item.obj_type, ARMOR | WEAPON) && item.magic)
}

struct RollResult {
    did_hit: bool,
    defender: Stats,
    rng_seed: i32,
}

fn roll_em(
    seed: i32,
    attacker: &Stats,
    defender: &Stats,
    current_armor_arm: Option<i32>,
    left_ring: Option<&RingObj>,
    right_ring: Option<&RingObj>,
) -> RollResult {
    let mut rng = RogueRng::new(seed);
    let mut hplus = 0;
    let dplus = 0;
    if defender.flags & ISRUN == 0 {
        hplus += 4;
    }
    let mut defender_arm = defender.arm;
    if let Some(armor) = current_armor_arm {
        defender_arm = armor;
    }
    if let Some(left) = left_ring {
        if left.which == R_PROTECT {
            defender_arm -= left.arm;
        }
    }
    if let Some(right) = right_ring {
        if right.which == R_PROTECT {
            defender_arm -= right.arm;
        }
    }
    let mut updated_defender = defender.clone();
    let mut did_hit = false;
    for (ndice, nsides) in damage_terms(&attacker.damage) {
        let result = rng.rnd(20);
        let need = (20 - attacker.level) - defender_arm;
        if result + hplus + STR_PLUS[attacker.strength as usize] >= need {
            let damage_roll = rng.roll(ndice, nsides);
            let damage = dplus + damage_roll + ADD_DAM[attacker.strength as usize];
            updated_defender.hp -= damage.max(0);
            did_hit = true;
        }
    }
    RollResult {
        did_hit,
        defender: updated_defender,
        rng_seed: rng.seed,
    }
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
    let mut monster = AttackMonster {
        monster_type: case.monster_type,
        stats: case.monster_stats,
        flags: case.monster_flags,
        disguise: case.disguise,
    };
    let returned = attack(&mut world, &mut monster);
    json!({"name": case.name, "seed": case.seed, "returned": returned, "monster": monster_json(&monster), "world": world_json(&world)})
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    monster_type: char,
    monster_stats: Stats,
    player_stats: Stats,
    monster_flags: i32,
    disguise: Option<char>,
    player_flags: i32,
    armor_arm: Option<i32>,
    left_ring: Option<RingObj>,
    right_ring: Option<RingObj>,
    sustain_strength: bool,
    running: bool,
    count: i32,
    quiet: i32,
    to_death: bool,
    kamikaze: bool,
    has_hit: bool,
    max_hit: i32,
    no_command: i32,
    purse: i32,
    level: i32,
    max_hp: i32,
    vf_hit: i32,
    fight_flush: bool,
    pack: Vec<AttackItem>,
}

fn base_case(name: &'static str, seed: i32, monster_type: char) -> Case {
    Case {
        name,
        seed,
        monster_type,
        monster_stats: stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN),
        player_stats: stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN),
        monster_flags: ISRUN,
        disguise: Some(monster_type),
        player_flags: ISRUN,
        armor_arm: Some(6),
        left_ring: None,
        right_ring: None,
        sustain_strength: false,
        running: true,
        count: 4,
        quiet: 7,
        to_death: false,
        kamikaze: false,
        has_hit: false,
        max_hit: 0,
        no_command: 0,
        purse: 200,
        level: 1,
        max_hp: 30,
        vf_hit: 0,
        fight_flush: true,
        pack: Vec::new(),
    }
}

impl Case {
    fn monster_stats(mut self, stats: Stats) -> Self {
        self.monster_stats = stats;
        self
    }
    fn player_stats(mut self, stats: Stats) -> Self {
        self.player_stats = stats;
        self.max_hp = self.player_stats.max_hp;
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
    fn player_flags(mut self, flags: i32) -> Self {
        self.player_flags = flags;
        self
    }
    fn armor_arm(mut self, armor_arm: i32) -> Self {
        self.armor_arm = Some(armor_arm);
        self
    }
    fn left_ring(mut self, ring: RingObj) -> Self {
        self.left_ring = Some(ring);
        self
    }
    fn sustain_strength(mut self, sustain_strength: bool) -> Self {
        self.sustain_strength = sustain_strength;
        self
    }
    fn to_death(mut self, to_death: bool, kamikaze: bool) -> Self {
        self.to_death = to_death;
        self.kamikaze = kamikaze;
        self
    }
    fn has_hit(mut self, has_hit: bool) -> Self {
        self.has_hit = has_hit;
        self
    }
    fn max_hit(mut self, max_hit: i32) -> Self {
        self.max_hit = max_hit;
        self
    }
    fn no_command(mut self, no_command: i32) -> Self {
        self.no_command = no_command;
        self
    }
    fn purse(mut self, purse: i32) -> Self {
        self.purse = purse;
        self
    }
    fn level(mut self, level: i32) -> Self {
        self.level = level;
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
    fn pack(mut self, pack: Vec<AttackItem>) -> Self {
        self.pack = pack;
        self
    }
}

fn cases() -> Vec<Case> {
    let hard_to_hit_player = stats(16, 100, 1, -10, 30, "1x1", 30, ISRUN);
    vec![
        base_case("basic_hit_updates_max_hit", 1, 'K')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x4", 30, ISRUN))
            .player_stats(stats(16, 100, 20, 6, 20, "1x1", 20, ISRUN))
            .max_hit(1),
        base_case("basic_miss_message", 7, 'K')
            .monster_stats(stats(16, 100, 1, 6, 30, "1x1", 30, ISRUN))
            .player_stats(hard_to_hit_player.clone())
            .armor_arm(-10)
            .has_hit(true),
        base_case("target_keeps_to_death", 1, 'K')
            .monster_flags(ISRUN | ISTARGET)
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .to_death(true, true),
        base_case("xeroc_hallu_reveals", 7, 'X')
            .disguise('A')
            .player_flags(ISRUN | ISHALU)
            .monster_stats(stats(16, 100, 1, 6, 30, "1x1", 30, ISRUN))
            .player_stats(hard_to_hit_player.clone())
            .armor_arm(-10),
        base_case("aquator_rusts_armor", 1, 'A')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN)),
        base_case("ice_freezes_player", 1, 'I')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .no_command(49),
        base_case("rattlesnake_poison_strength", 2, 'R')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .player_stats(stats(16, 100, 1, 6, 30, "1x1", 30, ISRUN)),
        base_case("rattlesnake_sustain_strength", 2, 'R')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .player_stats(stats(16, 100, 1, 6, 30, "1x1", 30, ISRUN))
            .sustain_strength(true),
        base_case("wraith_energy_drain", 3, 'W')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .player_stats(stats(16, 200, 5, 6, 30, "1x1", 30, ISRUN))
            .max_hp(30),
        base_case("venus_flytrap_hit_holds", 1, 'F')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .vf_hit(1),
        base_case("venus_flytrap_miss_crushes", 7, 'F')
            .monster_stats(stats(16, 100, 1, 6, 30, "1x1", 30, ISRUN))
            .player_stats(hard_to_hit_player)
            .armor_arm(-10)
            .vf_hit(3),
        base_case("leprechaun_steals_gold", 1, 'L')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .purse(200)
            .level(4)
            .left_ring(ring(R_PROTECT, 2)),
        base_case("nymph_steals_magic_item", 1, 'N')
            .monster_stats(stats(16, 100, 20, 6, 30, "1x1", 30, ISRUN))
            .pack(vec![
                item("plain-food", ':', false, false),
                item("worn-armor", ARMOR, true, true),
                item("wand", STICK, true, false),
                item("plus-mace", WEAPON, true, false),
            ]),
    ]
}

fn world_for(case: &Case) -> AttackWorld {
    AttackWorld {
        rng: RogueRng::new(case.seed),
        player: case.player_stats.clone(),
        player_flags: case.player_flags,
        current_armor_arm: case.armor_arm,
        left_ring: case.left_ring.clone(),
        right_ring: case.right_ring.clone(),
        sustain_strength: case.sustain_strength,
        running: case.running,
        count: case.count,
        quiet: case.quiet,
        to_death: case.to_death,
        kamikaze: case.kamikaze,
        has_hit: case.has_hit,
        max_hit: case.max_hit,
        no_command: case.no_command,
        purse: case.purse,
        level: case.level,
        max_hp: case.max_hp,
        vf_hit: case.vf_hit,
        fight_flush: case.fight_flush,
        pack: case.pack.clone(),
        markers: Vec::new(),
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
) -> Stats {
    Stats {
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

fn ring(which: i32, arm: i32) -> RingObj {
    RingObj { which, arm }
}

fn item(name: &'static str, obj_type: char, magic: bool, equipped: bool) -> AttackItem {
    AttackItem {
        name: name.to_string(),
        obj_type,
        magic,
        equipped,
    }
}

fn stats_json(stats: &Stats) -> Value {
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

pub fn monster_json(monster: &AttackMonster) -> Value {
    json!({
        "type": monster.monster_type.to_string(),
        "flags": monster.flags,
        "disguise": monster.disguise.map(|ch| ch.to_string()),
        "stats": stats_json(&monster.stats),
    })
}

pub fn item_json(item: &AttackItem) -> Value {
    json!({"name": item.name, "type": item.obj_type.to_string(), "magic": item.magic, "equipped": item.equipped})
}

pub fn world_json(world: &AttackWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "player": stats_json(&world.player),
        "player_flags": world.player_flags,
        "running": world.running,
        "count": world.count,
        "quiet": world.quiet,
        "to_death": world.to_death,
        "kamikaze": world.kamikaze,
        "has_hit": world.has_hit,
        "max_hit": world.max_hit,
        "no_command": world.no_command,
        "purse": world.purse,
        "level": world.level,
        "max_hp": world.max_hp,
        "vf_hit": world.vf_hit,
        "pack": world.pack.iter().map(item_json).collect::<Vec<_>>(),
        "markers": world.markers,
        "trace": world.trace,
    })
}
