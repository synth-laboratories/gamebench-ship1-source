use crate::RogueRng;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const VS_POISON: i32 = 0;
const VS_MAGIC: i32 = 3;

const ISRUN: i32 = 0o020000;
const ISMISL: i32 = 0o000004;

const R_PROTECT: i32 = 0;
const R_ADDHIT: i32 = 7;
const R_ADDDAM: i32 = 8;

const BOW: i32 = 2;
const ARROW: i32 = 3;
const NO_WEAPON: i32 = -1;

const STR_PLUS: [i32; 32] = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 3,
];
const ADD_DAM: [i32; 32] = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 6,
];

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SourceStats {
    strength: i32,
    exp: i32,
    level: i32,
    arm: i32,
    hp: i32,
    damage: String,
    max_hp: i32,
    flags: i32,
}

#[derive(Clone, Debug)]
struct SourceWeapon {
    which: i32,
    hplus: i32,
    dplus: i32,
    damage: String,
    hurl_damage: String,
    launch: i32,
    flags: i32,
}

#[derive(Clone, Debug)]
struct SourceRing {
    which: i32,
    arm: i32,
}

#[derive(Clone, Debug, Serialize)]
struct RollEmResult {
    did_hit: bool,
    attacker: SourceStats,
    defender: SourceStats,
    rng_seed: i32,
    attacks: Vec<Value>,
    damage_expression: String,
    hplus: i32,
    dplus: i32,
    defender_arm: i32,
}

pub fn source_combat_report() -> Value {
    json!({
        "swing": [
            swing_case(1, 1, 6, 0),
            swing_case(7, 5, 2, 3),
            swing_case(-17, 12, -1, 5),
        ],
        "save": [
            save_throw_case(1, VS_POISON, 1),
            save_case(7, VS_MAGIC, stats(16, 0, 5, 6, 12, "1x4", 12, 0), Some(ring(R_PROTECT, 2)), None),
            save_case(-17, VS_MAGIC, stats(16, 0, 10, 6, 20, "1x4", 20, 0), Some(ring(R_PROTECT, 1)), Some(ring(R_PROTECT, 3))),
        ],
        "roll_em": [
            json!({"name": "monster_claw", "result": roll_em(1, stats(10, 0, 3, 5, 12, "1x3/1x3", 12, 0), stats(10, 0, 1, 7, 10, "1x4", 10, 0), RollOptions::default())}),
            json!({"name": "current_mace_with_rings", "result": roll_em(
                7,
                stats(18, 0, 4, 5, 20, "1x4", 20, 0),
                stats(10, 0, 5, 4, 30, "1x6", 30, 0),
                RollOptions {
                    weapon: Some(weapon(0, 1, 1, "2x4", "1x3", NO_WEAPON, 0)),
                    weapon_is_current: true,
                    left_ring: Some(ring(R_ADDHIT, 2)),
                    right_ring: Some(ring(R_ADDDAM, 3)),
                    ..RollOptions::default()
                },
            )}),
            json!({"name": "hurled_arrow_with_bow", "result": roll_em(
                12345,
                stats(16, 0, 6, 5, 22, "1x4", 22, 0),
                stats(10, 0, 8, 2, 45, "2x6", 45, 0),
                RollOptions {
                    weapon: Some(weapon(ARROW, 0, 0, "1x1", "2x3", BOW, ISMISL)),
                    hurl: true,
                    current_weapon: Some(weapon(BOW, 1, 2, "1x1", "1x1", NO_WEAPON, 0)),
                    ..RollOptions::default()
                },
            )}),
            json!({"name": "defender_player_protection", "result": roll_em(
                -17,
                stats(20, 0, 9, 2, 50, "3x4/2x5", 50, 0),
                stats(16, 0, 7, 8, 35, "1x4", 35, 0),
                RollOptions {
                    defender_is_player: true,
                    current_armor_arm: Some(4),
                    left_ring: Some(ring(R_PROTECT, 1)),
                    right_ring: Some(ring(R_PROTECT, 2)),
                    ..RollOptions::default()
                },
            )}),
        ],
        "exp_add": [
            {"level": 1, "max_hp": 7, "value": exp_add(1, 7)},
            {"level": 5, "max_hp": 30, "value": exp_add(5, 30)},
            {"level": 8, "max_hp": 48, "value": exp_add(8, 48)},
            {"level": 12, "max_hp": 90, "value": exp_add(12, 90)},
        ],
    })
}

#[derive(Clone, Debug, Default)]
struct RollOptions {
    weapon: Option<SourceWeapon>,
    hurl: bool,
    weapon_is_current: bool,
    current_weapon: Option<SourceWeapon>,
    current_armor_arm: Option<i32>,
    left_ring: Option<SourceRing>,
    right_ring: Option<SourceRing>,
    defender_is_player: bool,
}

fn swing_case(seed: i32, at_lvl: i32, op_arm: i32, wplus: i32) -> Value {
    let mut rng = RogueRng::new(seed);
    let payload = swing(&mut rng, at_lvl, op_arm, wplus);
    json!({"seed": seed, "roll": payload.0, "need": payload.1, "hit": payload.2, "rng_seed": rng.seed})
}

fn swing(rng: &mut RogueRng, at_lvl: i32, op_arm: i32, wplus: i32) -> (i32, i32, bool) {
    let result = rng.rnd(20);
    let need = (20 - at_lvl) - op_arm;
    (result, need, result + wplus >= need)
}

fn save_throw_case(seed: i32, which: i32, level: i32) -> Value {
    let mut rng = RogueRng::new(seed);
    let (need, roll, saved) = save_throw(&mut rng, which, level);
    json!({"seed": seed, "which": which, "level": level, "need": need, "roll": roll, "saved": saved, "rng_seed": rng.seed})
}

fn save_case(
    seed: i32,
    which: i32,
    player: SourceStats,
    left_ring: Option<SourceRing>,
    right_ring: Option<SourceRing>,
) -> Value {
    let mut rng = RogueRng::new(seed);
    let mut adjusted = which;
    if which == VS_MAGIC {
        if let Some(left) = &left_ring {
            if left.which == R_PROTECT {
                adjusted -= left.arm;
            }
        }
        if let Some(right) = &right_ring {
            if right.which == R_PROTECT {
                adjusted -= right.arm;
            }
        }
    }
    let (need, roll, saved) = save_throw(&mut rng, adjusted, player.level);
    json!({"seed": seed, "which": adjusted, "original_which": which, "level": player.level, "need": need, "roll": roll, "saved": saved, "rng_seed": rng.seed})
}

fn save_throw(rng: &mut RogueRng, which: i32, level: i32) -> (i32, i32, bool) {
    let need = 14 + which - level / 2;
    let roll = rng.roll(1, 20);
    (need, roll, roll >= need)
}

fn roll_em(
    seed: i32,
    attacker: SourceStats,
    mut defender: SourceStats,
    options: RollOptions,
) -> RollEmResult {
    let mut rng = RogueRng::new(seed);
    let (damage_expression, mut hplus, dplus) = if let Some(weap) = &options.weapon {
        let mut hplus = weap.hplus;
        let mut dplus = weap.dplus;
        if options.weapon_is_current {
            if let Some(left) = &options.left_ring {
                if left.which == R_ADDDAM {
                    dplus += left.arm;
                } else if left.which == R_ADDHIT {
                    hplus += left.arm;
                }
            }
            if let Some(right) = &options.right_ring {
                if right.which == R_ADDDAM {
                    dplus += right.arm;
                } else if right.which == R_ADDHIT {
                    hplus += right.arm;
                }
            }
        }
        let mut expression = weap.damage.clone();
        if options.hurl {
            if weap.flags & ISMISL != 0 {
                if let Some(current) = &options.current_weapon {
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
    let mut defender_arm = defender.arm;
    if options.defender_is_player {
        if let Some(armor) = options.current_armor_arm {
            defender_arm = armor;
        }
        if let Some(left) = &options.left_ring {
            if left.which == R_PROTECT {
                defender_arm -= left.arm;
            }
        }
        if let Some(right) = &options.right_ring {
            if right.which == R_PROTECT {
                defender_arm -= right.arm;
            }
        }
    }
    let mut did_hit = false;
    let mut attacks = Vec::new();
    for (ndice, nsides) in damage_terms(&damage_expression) {
        let (roll_value, need, hit) = swing(
            &mut rng,
            attacker.level,
            defender_arm,
            hplus + STR_PLUS[attacker.strength as usize],
        );
        let mut attack = json!({
            "ndice": ndice,
            "nsides": nsides,
            "swing": {"roll": roll_value, "need": need, "hit": hit, "rng_seed": rng.seed},
            "damage_roll": 0,
            "damage": 0,
        });
        if hit {
            let damage_roll = rng.roll(ndice, nsides);
            let damage = dplus + damage_roll + ADD_DAM[attacker.strength as usize];
            let applied = damage.max(0);
            defender.hp -= applied;
            did_hit = true;
            let obj = attack.as_object_mut().unwrap();
            obj.insert("damage_roll".to_string(), json!(damage_roll));
            obj.insert("damage".to_string(), json!(damage));
            obj.insert("applied".to_string(), json!(applied));
        }
        attacks.push(attack);
    }
    RollEmResult {
        did_hit,
        attacker,
        defender,
        rng_seed: rng.seed,
        attacks,
        damage_expression,
        hplus,
        dplus,
        defender_arm,
    }
}

fn exp_add(level: i32, max_hp: i32) -> i32 {
    let mut modifier = if level == 1 { max_hp / 8 } else { max_hp / 6 };
    if level > 9 {
        modifier *= 20;
    } else if level > 6 {
        modifier *= 4;
    }
    modifier
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

fn stats(
    strength: i32,
    exp: i32,
    level: i32,
    arm: i32,
    hp: i32,
    damage: &str,
    max_hp: i32,
    flags: i32,
) -> SourceStats {
    SourceStats {
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
    which: i32,
    hplus: i32,
    dplus: i32,
    damage: &str,
    hurl_damage: &str,
    launch: i32,
    flags: i32,
) -> SourceWeapon {
    SourceWeapon {
        which,
        hplus,
        dplus,
        damage: damage.to_string(),
        hurl_damage: hurl_damage.to_string(),
        launch,
        flags,
    }
}

fn ring(which: i32, arm: i32) -> SourceRing {
    SourceRing { which, arm }
}
