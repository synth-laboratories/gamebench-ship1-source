use serde::{Deserialize, Serialize};
use serde_json::map::Map;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const U64_MASK: u128 = 0xFFFF_FFFF_FFFF_FFFF;
const CHECKPOINT_SCHEMA: &str = "gamebench.checkpoint.v1";
const ENV_FAMILY: &str = "crafter-singleplayer";
const CHECKPOINT_LANE: &str = "rust_native";
const CHECKPOINT_ENCODING: &str = "gamebench.crafter.rust_native_checkpoint.v1";
const NEV_TAIL_EVENTS: usize = 8;
const SNAPSHOT_NEV_TAIL: usize = 8;
const G2: f64 = std::f64::consts::FRAC_1_SQRT_2;
const MAX_INVENTORY_VALUE: i32 = 9;
const MAX_INVENTORY_COUNTER: i64 = 9;
const MAX_ENTITY_HEALTH: u64 = 255;
const DEFAULT_HUNGER_RATE: f64 = 25.0;
const DEFAULT_THIRST_RATE: f64 = 20.0;
const DEFAULT_DAY_CYCLE_PERIOD: u64 = 300;
const DEFAULT_ZOMBIE_DESPAWN_RATE: f64 = 0.4;
const DEFAULT_COW_DESPAWN_RATE: f64 = 0.01;
const MIN_RECOVER_COUNTER: f64 = -15.0;
const MAX_RECOVER_COUNTER: f64 = 25.0;
const MIN_FATIGUE_COUNTER: i32 = -10;
const MAX_FATIGUE_COUNTER: i32 = 30;
const CHACHA_REFILL_WORDS: usize = 64;
const CHACHA_REFILL_BLOCKS: u32 = 4;

#[derive(Clone, Copy)]
struct CraftaxMobStats {
    passive: bool,
    melee_damage: i32,
    ranged_damage: i32,
    range: i32,
    cooldown: i32,
    ranged_damage_source: &'static str,
    projectile_kind: &'static str,
}

fn craftax_mob_stats(kind: &str) -> Option<CraftaxMobStats> {
    let stats = match kind {
        "orc_soldier" => CraftaxMobStats {
            passive: false,
            melee_damage: 3,
            ranged_damage: 0,
            range: 1,
            cooldown: 3,
            ranged_damage_source: "craftax_ranged",
            projectile_kind: "arrow",
        },
        "orc_mage" => CraftaxMobStats {
            passive: false,
            melee_damage: 1,
            ranged_damage: 3,
            range: 6,
            cooldown: 4,
            ranged_damage_source: "craftax_magic",
            projectile_kind: "fireball",
        },
        "knight" => CraftaxMobStats {
            passive: false,
            melee_damage: 6,
            ranged_damage: 0,
            range: 1,
            cooldown: 2,
            ranged_damage_source: "craftax_ranged",
            projectile_kind: "arrow",
        },
        "knight_archer" => CraftaxMobStats {
            passive: false,
            melee_damage: 2,
            ranged_damage: 5,
            range: 7,
            cooldown: 3,
            ranged_damage_source: "craftax_ranged",
            projectile_kind: "arrow",
        },
        "troll" => CraftaxMobStats {
            passive: false,
            melee_damage: 6,
            ranged_damage: 0,
            range: 1,
            cooldown: 3,
            ranged_damage_source: "craftax_ranged",
            projectile_kind: "arrow",
        },
        "bat" => CraftaxMobStats {
            passive: true,
            melee_damage: 0,
            ranged_damage: 0,
            range: 0,
            cooldown: 0,
            ranged_damage_source: "craftax_ranged",
            projectile_kind: "arrow",
        },
        "snail" => CraftaxMobStats {
            passive: true,
            melee_damage: 0,
            ranged_damage: 0,
            range: 0,
            cooldown: 0,
            ranged_damage_source: "craftax_ranged",
            projectile_kind: "arrow",
        },
        _ => return None,
    };
    Some(stats)
}

fn is_craftax_recipe_action(action: &str) -> bool {
    matches!(
        action,
        "make_diamond_pickaxe"
            | "make_diamond_sword"
            | "make_iron_armor"
            | "make_diamond_armor"
            | "make_bow"
            | "make_arrow"
    )
}

const WORLDGEN_DENSITY_KEYS: [&str; 7] = [
    "tree_density",
    "coal_density",
    "iron_density",
    "diamond_density",
    "cow_density",
    "zombie_density",
    "skeleton_density",
];

const DEFAULT_WORLD_MAP_LEGEND: [(&str, &str); 15] = [
    ("~", "water"),
    (".", "grass"),
    ("#", "stone"),
    (":", "path"),
    (",", "sand"),
    ("T", "tree"),
    ("L", "lava"),
    ("C", "coal"),
    ("I", "iron"),
    ("D", "diamond"),
    ("S", "sapphire"),
    ("R", "ruby"),
    ("$", "chest"),
    ("=", "table"),
    ("F", "furnace"),
];

const CRAFTAX_ONLY_ACTIONS: [&str; 12] = [
    "make_bow",
    "make_arrow",
    "make_iron_armor",
    "make_diamond_armor",
    "shoot",
    "drink_potion",
    "drink_potion_red",
    "drink_potion_green",
    "drink_potion_blue",
    "drink_potion_pink",
    "drink_potion_cyan",
    "drink_potion_yellow",
];

const CLASSIC_INVENTORY_SLOTS: [&str; 18] = [
    "health",
    "food",
    "drink",
    "energy",
    "sapling",
    "wood",
    "stone",
    "coal",
    "iron",
    "diamond",
    "wood_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "diamond_pickaxe",
    "wood_sword",
    "stone_sword",
    "iron_sword",
    "diamond_sword",
];

const ACTION_NAMES: [&str; 31] = [
    "noop",
    "move_left",
    "move_right",
    "move_up",
    "move_down",
    "do",
    "sleep",
    "place_stone",
    "place_table",
    "place_furnace",
    "place_plant",
    "make_wood_pickaxe",
    "make_stone_pickaxe",
    "make_iron_pickaxe",
    "make_diamond_pickaxe",
    "make_wood_sword",
    "make_stone_sword",
    "make_iron_sword",
    "make_diamond_sword",
    "make_bow",
    "make_arrow",
    "make_iron_armor",
    "make_diamond_armor",
    "shoot",
    "drink_potion",
    "drink_potion_red",
    "drink_potion_green",
    "drink_potion_blue",
    "drink_potion_pink",
    "drink_potion_cyan",
    "drink_potion_yellow",
];

const INVENTORY_KEYS: [&str; 35] = [
    "health",
    "food",
    "drink",
    "energy",
    "sapling",
    "wood",
    "stone",
    "coal",
    "iron",
    "diamond",
    "sapphire",
    "ruby",
    "wood_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "diamond_pickaxe",
    "wood_sword",
    "stone_sword",
    "iron_sword",
    "diamond_sword",
    "bow",
    "arrows",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
    "xp",
    "level",
    "stat_points",
];

const POTION_SLOTS: [(&str, &str); 6] = [
    ("red", "potion_red"),
    ("green", "potion_green"),
    ("blue", "potion_blue"),
    ("pink", "potion_pink"),
    ("cyan", "potion_cyan"),
    ("yellow", "potion_yellow"),
];

const ARMOR_SLOTS: [&str; 4] = [
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
];
const CRAFTAX_ITEM_INVENTORY_SLOTS: [&str; 15] = [
    "sapphire",
    "ruby",
    "bow",
    "arrows",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
    "stat_points",
];
const CRAFTAX_RECIPE_INVENTORY_SLOTS: [&str; 7] = [
    "diamond_pickaxe",
    "diamond_sword",
    "bow",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
];
const CRAFTAX_POTION_INVENTORY_SLOTS: [&str; 6] = [
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
];
const CRAFTAX_XP_INVENTORY_SLOTS: [&str; 3] = ["xp", "level", "stat_points"];
const CRAFTAX_ITEM_TERRAIN: [&str; 2] = ["sapphire", "ruby"];

pub const ACHIEVEMENTS: [&str; 39] = [
    "collect_coal",
    "collect_diamond",
    "collect_drink",
    "collect_iron",
    "collect_ruby",
    "collect_sapling",
    "collect_sapphire",
    "collect_stone",
    "collect_wood",
    "defeat_knight",
    "defeat_knight_archer",
    "defeat_orc_mage",
    "defeat_orc_soldier",
    "defeat_skeleton",
    "defeat_troll",
    "defeat_zombie",
    "drink_potion",
    "eat_cow",
    "eat_plant",
    "gain_xp",
    "make_arrow",
    "make_bow",
    "make_diamond_armor",
    "make_diamond_pickaxe",
    "make_diamond_sword",
    "make_iron_armor",
    "make_iron_pickaxe",
    "make_iron_sword",
    "make_stone_pickaxe",
    "make_stone_sword",
    "make_wood_pickaxe",
    "make_wood_sword",
    "place_furnace",
    "place_plant",
    "place_stone",
    "place_table",
    "open_chest",
    "reach_level",
    "wake_up",
];

const WALKABLE: [&str; 4] = ["grass", "path", "sand", "lava"];

const GRAD3: [(f64, f64, f64); 32] = [
    (G2, G2, 0.0),
    (-G2, G2, 0.0),
    (G2, -G2, 0.0),
    (-G2, -G2, 0.0),
    (G2, 0.0, G2),
    (-G2, 0.0, G2),
    (G2, 0.0, -G2),
    (-G2, 0.0, -G2),
    (0.0, G2, G2),
    (0.0, -G2, G2),
    (0.0, G2, -G2),
    (0.0, -G2, -G2),
    (G2, G2, 0.0),
    (-G2, G2, 0.0),
    (G2, -G2, 0.0),
    (-G2, -G2, 0.0),
    (G2, 0.0, G2),
    (-G2, 0.0, G2),
    (G2, 0.0, -G2),
    (-G2, 0.0, -G2),
    (0.0, G2, G2),
    (0.0, -G2, G2),
    (0.0, G2, -G2),
    (0.0, -G2, -G2),
    (0.5773502691896258, 0.5773502691896258, 0.5773502691896258),
    (-0.5773502691896258, 0.5773502691896258, 0.5773502691896258),
    (0.5773502691896258, -0.5773502691896258, 0.5773502691896258),
    (-0.5773502691896258, -0.5773502691896258, 0.5773502691896258),
    (0.5773502691896258, 0.5773502691896258, -0.5773502691896258),
    (-0.5773502691896258, 0.5773502691896258, -0.5773502691896258),
    (0.5773502691896258, -0.5773502691896258, -0.5773502691896258),
    (
        -0.5773502691896258,
        -0.5773502691896258,
        -0.5773502691896258,
    ),
];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EventRecord {
    pub step_index: u64,
    pub sim_tick: u64,
    pub episode_id: String,
    pub kind: String,
    pub severity: String,
    pub message: String,
    pub action: Option<String>,
    pub transition: Option<Value>,
    pub payload: Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Entity {
    id: String,
    kind: String,
    pos: (i32, i32),
    health: i32,
    #[serde(default)]
    metadata: BTreeMap<String, Value>,
}

impl Entity {
    fn to_json(&self) -> Value {
        json!({
            "id": self.id,
            "kind": self.kind,
            "pos": [self.pos.0, self.pos.1],
            "health": self.health,
            "facing": self.metadata.get("facing").cloned().unwrap_or(Value::Null),
            "metadata": self.metadata
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct NativeWorld {
    width: usize,
    height: usize,
    view_radius: i32,
    max_steps: u64,
    seed: u64,
    tiles: Vec<Vec<String>>,
    player_pos: (i32, i32),
    player_facing: (i32, i32),
    player_sleeping: bool,
    daylight: f64,
    #[serde(default)]
    hunger_counter: f64,
    #[serde(default)]
    thirst_counter: f64,
    #[serde(default)]
    fatigue_counter: i32,
    #[serde(default)]
    recover_counter: f64,
    #[serde(default = "max_inventory_i32")]
    last_health: i32,
    #[serde(default)]
    last_damage_source: Option<String>,
    episode: u64,
    step: u64,
    inventory: BTreeMap<String, i64>,
    achievements: BTreeMap<String, i64>,
    entities: Vec<Entity>,
    #[serde(default)]
    next_entity_id: u64,
    rng: ChaCha8Rng,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct PrivateState {
    episode_id: String,
    task_id: String,
    scenario_id: String,
    seed: u64,
    config_hash: String,
    step_index: u64,
    reward_last: f32,
    total_reward: f32,
    reward_breakdown: Value,
    terminated: bool,
    truncated: bool,
    achievements: BTreeSet<String>,
    done_reason: Option<String>,
}

#[derive(Clone, Debug)]
struct RewardComponent {
    source: &'static str,
    component: &'static str,
    delta: f32,
    count: Option<usize>,
    achievements: Vec<String>,
}

#[derive(Clone, Copy, Debug)]
struct TickBefore {
    health: i32,
    food: i32,
    drink: i32,
    energy: i32,
    sleeping: bool,
}

#[derive(Clone, Debug)]
struct GeneratedWorld {
    tiles: Vec<Vec<String>>,
    entities: Vec<Entity>,
    rng: ChaCha8Rng,
}

#[derive(Clone, Copy, Debug)]
struct ClassicMobHealth {
    cow: i32,
    zombie: i32,
    skeleton: i32,
}

struct CraftaxWorldgenContext<'a> {
    config: &'a Value,
    resolved: &'a Value,
    runtime_mobs_enabled: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CrafterRustSession {
    pub task_id: String,
    pub scenario_id: String,
    pub seed: u64,
    pub config_hash: String,
    pub resolved_json: Value,
    pub episode_id: String,
    pub reward_last: f32,
    pub total_reward: f32,
    pub reward_breakdown: Value,
    pub terminated: bool,
    pub truncated: bool,
    pub done_reason: Option<String>,
    pub events: Vec<EventRecord>,
    pub event_cursor_offset: usize,
    world: NativeWorld,
    private: PrivateState,
}

impl CrafterRustSession {
    pub fn reset_from_entry(entry: &Value) -> Self {
        let task = scenario_to_task(entry);
        let mut session = Self::reset_from_task(&task);
        let checkpoint_after = entry.get("checkpoint_after").and_then(Value::as_u64);
        let mut checkpoint: Option<Vec<u8>> = None;
        if let Some(actions) = entry.get("actions").and_then(Value::as_array) {
            for (idx, action) in actions.iter().enumerate() {
                if session.terminated || session.truncated {
                    break;
                }
                session.step(action.as_str().unwrap_or("noop"));
                if checkpoint_after == Some((idx + 1) as u64) {
                    checkpoint = Some(session.checkpoint_bytes());
                }
            }
        }
        if let (Some(blob), Some(actions)) = (
            checkpoint,
            entry.get("restore_then_actions").and_then(Value::as_array),
        ) {
            session.restore_checkpoint_bytes(&blob);
            for action in actions {
                if session.terminated || session.truncated {
                    break;
                }
                session.step(action.as_str().unwrap_or("noop"));
            }
        }
        session
    }

    pub fn reset_from_task(task: &Value) -> Self {
        let resolved = resolve_task(task);
        let substrate_profile = resolved
            .get("substrate_profile")
            .and_then(Value::as_str)
            .unwrap_or("classic");
        if !matches!(substrate_profile, "classic" | "craftax_partial") {
            panic!(
                "unsupported gold_rust native Crafter substrate_profile: {}",
                substrate_profile
            );
        }
        let seed = resolved["seed"].as_u64().unwrap_or(0);
        let config_hash = resolved["config_hash"].as_str().unwrap().to_string();
        let task_id = resolved["task_id"].as_str().unwrap().to_string();
        let scenario_id = resolved["scenario_id"].as_str().unwrap().to_string();
        let episode_id = episode_id_for_task(&task_id, seed, &config_hash);
        let world = make_world(&resolved);
        let seeded_achievements = world
            .achievements
            .iter()
            .filter_map(|(name, count)| if *count > 0 { Some(name.clone()) } else { None })
            .collect::<BTreeSet<_>>();
        let mut private = PrivateState {
            episode_id: episode_id.clone(),
            task_id: task_id.clone(),
            scenario_id: scenario_id.clone(),
            seed,
            config_hash: config_hash.clone(),
            step_index: 0,
            reward_last: 0.0,
            total_reward: 0.0,
            reward_breakdown: initial_reward_breakdown(&resolved),
            terminated: false,
            truncated: false,
            achievements: seeded_achievements,
            done_reason: None,
        };
        private.reward_breakdown["achievement_count"] = json!(private.achievements.len());
        let mut session = Self {
            task_id,
            scenario_id: scenario_id.clone(),
            seed,
            config_hash: config_hash.clone(),
            resolved_json: resolved.clone(),
            episode_id,
            reward_last: 0.0,
            total_reward: 0.0,
            reward_breakdown: private.reward_breakdown.clone(),
            terminated: false,
            truncated: false,
            done_reason: None,
            events: vec![],
            event_cursor_offset: 0,
            world,
            private,
        };
        session.append(
            "task_resolved",
            "info",
            format!("TaskResolved({},{})", scenario_id, config_hash),
            None,
            None,
            json!({"resolved": resolved}),
        );
        session
    }

    pub fn step(&mut self, raw_action: &str) {
        let action_name = normalize_action(raw_action);
        if !ACTION_NAMES.contains(&action_name.as_str()) {
            self.reject_unknown_action(&action_name);
            return;
        }
        if self.terminated || self.truncated {
            self.reject(&action_name, "terminal");
            return;
        }
        if !action_allowed_for_resolved(&action_name, &self.resolved_json) {
            self.reject(&action_name, "rule");
            return;
        }

        let before_inventory = self.world.inventory.clone();
        let before_achievements = self.world.achievements.clone();
        let before_pos = self.world.player_pos;
        let before_facing = self.world.player_facing;
        let before_step = self.world.step;
        let before_player = self.player_observation(&before_inventory);
        let mut debug_events = Vec::new();
        let tick_before = TickBefore {
            health: counter_as_i32(before_inventory.get("health").copied().unwrap_or(0)),
            food: counter_as_i32(before_inventory.get("food").copied().unwrap_or(0)),
            drink: counter_as_i32(before_inventory.get("drink").copied().unwrap_or(0)),
            energy: counter_as_i32(before_inventory.get("energy").copied().unwrap_or(0)),
            sleeping: self.world.player_sleeping,
        };

        self.update_daylight_for_step(before_step + 1);
        self.process_action(&action_name, &mut debug_events);
        self.world.step += 1;
        self.advance_runtime(&action_name, tick_before, &mut debug_events);
        let done_reason = self.done_reason_now();
        let done = done_reason.is_some();
        if done_reason.as_deref() == Some("death") {
            let cause = self
                .world
                .last_damage_source
                .as_deref()
                .unwrap_or("unknown");
            debug_events.push(format!("Death cause: {}", cause));
        }
        self.private.step_index = self.world.step;
        self.private.terminated = done_reason.as_deref() == Some("death");
        self.private.truncated = done_reason.as_deref() == Some("max_steps");
        self.private.done_reason = done_reason.clone();
        self.terminated = self.private.terminated;
        self.truncated = self.private.truncated;
        self.done_reason = done_reason.clone();

        let after_achievements = self.world.achievements.clone();
        let newly_unlocked = newly_unlocked(&before_achievements, &after_achievements);
        let env_components = self.env_reward_components(&newly_unlocked, done_reason.as_deref());
        let monty_reward =
            self.monty_transition_reward(&before_inventory, &self.world.inventory, &newly_unlocked);
        self.apply_reward_deltas(&env_components, monty_reward);

        self.append(
            "action_applied",
            "info",
            format!("ActionApplied({},step={})", display_action(&action_name), self.world.step),
            Some(action_name.clone()),
            Some(json!({
                "player_pos": {"from": [before_pos.0, before_pos.1], "to": [self.world.player_pos.0, self.world.player_pos.1]},
                "step": {"from": before_step, "to": self.world.step}
            })),
            json!({"action": action_name, "done": done, "done_reason": done_reason}),
        );
        self.append_inventory_deltas(
            &action_name,
            &before_inventory,
            &self.world.inventory.clone(),
        );
        if before_pos != self.world.player_pos || before_facing != self.world.player_facing {
            self.append(
                "state_transition",
                "info",
                format!(
                    "StateTransition(pos=[{}, {}],facing=[{}, {}])",
                    self.world.player_pos.0,
                    self.world.player_pos.1,
                    self.world.player_facing.0,
                    self.world.player_facing.1
                ),
                Some(action_name.clone()),
                None,
                json!({"player_before": before_player, "player_after": self.player_observation(&self.world.inventory)}),
            );
        }
        for achievement in newly_unlocked {
            self.private.achievements.insert(achievement.clone());
            self.append(
                "achievement_unlocked",
                "info",
                format!("AchievementUnlocked({})", achievement),
                Some(action_name.clone()),
                None,
                json!({"achievement": achievement}),
            );
        }
        for debug in debug_events {
            self.append(
                "entity_transition",
                "info",
                format!("Debug({})", debug),
                Some(action_name.clone()),
                None,
                json!({"substrate_event": debug}),
            );
        }
        self.append_reward_delta_events(&action_name, &env_components, monty_reward);
        if done {
            let reason = self
                .done_reason
                .clone()
                .unwrap_or_else(|| "done".to_string());
            let terminal_kind = if reason == "death" {
                "death"
            } else {
                "episode_truncated"
            };
            let terminal_payload = termination_payload(&self.done_reason, &self.world.last_damage_source);
            self.append(
                terminal_kind,
                "info",
                format!("{}({})", title_event(terminal_kind), reason),
                Some(action_name.clone()),
                None,
                terminal_payload.clone(),
            );
            self.append(
                "terminal",
                "info",
                format!("Terminal({})", reason),
                Some(action_name),
                None,
                terminal_payload,
            );
        }
        self.append_checkpoint_cadence_event();
    }

    pub fn step_index(&self) -> u64 {
        self.world.step
    }

    pub fn valid_actions(&self) -> Vec<String> {
        if self.terminated || self.truncated {
            vec![]
        } else {
            ACTION_NAMES
                .iter()
                .filter(|name| action_allowed_for_resolved(name, &self.resolved_json))
                .map(|name| (*name).to_string())
                .collect()
        }
    }

    pub fn checkpoint_bytes(&self) -> Vec<u8> {
        let cursor = self.event_cursor();
        let nev_tail = self
            .events
            .iter()
            .rev()
            .take(NEV_TAIL_EVENTS)
            .cloned()
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect::<Vec<_>>();
        let payload = json!({
            "schema_version": CHECKPOINT_SCHEMA,
            "env_family": ENV_FAMILY,
            "lane": CHECKPOINT_LANE,
            "encoding": CHECKPOINT_ENCODING,
            "episode_id": self.episode_id,
            "step_index": self.world.step,
            "nev_cursor": cursor,
            "nev_event_digest": digest_json(&self.events),
            "nev_events_external": true,
            "nev_tail_cursor_offset": cursor.saturating_sub(nev_tail.len()),
            "nev_tail_events": nev_tail,
            "config_hash": self.config_hash,
            "sim": {
                "resolved": self.resolved_json,
                "world": self.world,
                "private": self.private_json()
            }
        });
        serde_json::to_vec(&payload).expect("native Crafter checkpoint must encode as JSON")
    }

    pub fn restore_checkpoint_bytes(&mut self, blob: &[u8]) -> usize {
        let payload: Value = serde_json::from_slice(blob).expect("checkpoint must be JSON");
        if payload.get("schema_version").and_then(Value::as_str) != Some(CHECKPOINT_SCHEMA) {
            panic!("unsupported checkpoint schema");
        }
        if payload.get("env_family").and_then(Value::as_str) != Some(ENV_FAMILY) {
            panic!("wrong checkpoint env_family");
        }
        if payload.get("lane").and_then(Value::as_str) != Some(CHECKPOINT_LANE) {
            panic!("wrong checkpoint lane");
        }
        if payload.get("encoding").and_then(Value::as_str) != Some(CHECKPOINT_ENCODING) {
            panic!("wrong checkpoint encoding");
        }
        let sim = checkpoint_required_object_field(&payload, "sim");
        self.resolved_json = checkpoint_required_object_value_field(sim, "resolved");
        let checkpoint_config_hash = checkpoint_required_string_field(&payload, "config_hash");
        validate_resolved_config_hash(&self.resolved_json, checkpoint_config_hash);
        self.world = serde_json::from_value(checkpoint_required_object_value_field(sim, "world"))
            .expect("checkpoint sim.world must decode");
        normalize_restored_world(&mut self.world);
        validate_restored_runtime_invariants(&self.resolved_json, &payload, &self.world);
        validate_restored_entity_ids(&self.world);
        self.config_hash = checkpoint_config_hash.to_string();
        self.episode_id = checkpoint_required_string_field(&payload, "episode_id").to_string();
        let top_step_index = checkpoint_usize_field(&payload, "step_index")
            .unwrap_or_else(|| panic!("native Crafter checkpoint missing step_index"));
        let private = checkpoint_required_object_field(sim, "private");
        let private_episode_id = private_required_string_field(private, "episode_id");
        if private_episode_id != self.episode_id {
            panic!(
                "native Crafter checkpoint private.episode_id {} does not match episode_id {}",
                private_episode_id, self.episode_id
            );
        }
        let private_config_hash = private_required_string_field(private, "config_hash");
        if private_config_hash != self.config_hash {
            panic!(
                "native Crafter checkpoint private.config_hash {} does not match config_hash {}",
                private_config_hash, self.config_hash
            );
        }
        self.task_id = private_required_string_field(private, "task_id").to_string();
        self.scenario_id = private_required_string_field(private, "scenario_id").to_string();
        self.seed = private_required_u64_field(private, "seed");
        self.reward_last = private_required_f32_field(private, "reward_last");
        self.total_reward = private_required_f32_field(private, "total_reward");
        self.reward_breakdown = private_required_object_value_field(private, "reward_breakdown");
        self.terminated = private_required_bool_field(private, "terminated");
        self.truncated = private_required_bool_field(private, "truncated");
        self.done_reason = private_required_optional_string_field(private, "done_reason");
        let private_step_index = private_required_u64_field(private, "step_index");
        if private_step_index != top_step_index as u64 {
            panic!(
                "native Crafter checkpoint private.step_index {} does not match step_index {}",
                private_step_index, top_step_index
            );
        }
        let private_achievements = private_achievement_set(private);
        self.private = PrivateState {
            episode_id: self.episode_id.clone(),
            task_id: self.task_id.clone(),
            scenario_id: self.scenario_id.clone(),
            seed: self.seed,
            config_hash: self.config_hash.clone(),
            step_index: top_step_index as u64,
            reward_last: self.reward_last,
            total_reward: self.total_reward,
            reward_breakdown: self.reward_breakdown.clone(),
            terminated: self.terminated,
            truncated: self.truncated,
            achievements: private_achievements,
            done_reason: self.done_reason.clone(),
        };
        self.validate_restored_private_invariants();
        self.private = self.private_state_snapshot();
        let tail_cursor_offset = checkpoint_usize_field(&payload, "nev_tail_cursor_offset");
        let full_events = decode_checkpoint_events(&payload, "nev_events");
        let tail_events = decode_checkpoint_events(&payload, "nev_tail_events");
        let cursor = checkpoint_usize_field(&payload, "nev_cursor")
            .unwrap_or_else(|| panic!("native Crafter checkpoint missing nev_cursor"));
        if let Some(events) = full_events {
            if cursor != events.len() {
                panic!(
                    "native Crafter checkpoint nev_cursor {} does not match nev_events length {}",
                    cursor,
                    events.len()
                );
            }
            if let Some(expected_digest) = checkpoint_string_field(&payload, "nev_event_digest") {
                let actual_digest = digest_json(&events);
                if expected_digest != actual_digest {
                    panic!(
                        "native Crafter checkpoint nev_event_digest {} does not match decoded events {}",
                        expected_digest, actual_digest
                    );
                }
            }
            self.event_cursor_offset = 0;
            self.events = events;
        } else {
            self.events = tail_events
                .unwrap_or_else(|| panic!("native Crafter checkpoint missing nev_tail_events"));
            self.event_cursor_offset = tail_cursor_offset.unwrap_or_else(|| {
                panic!("native Crafter checkpoint missing nev_tail_cursor_offset")
            });
            validate_tail_cursor(cursor, Some(self.event_cursor_offset), Some(&self.events));
        }
        validate_restored_event_records(
            &self.events,
            &self.episode_id,
            self.world.step,
            &self.resolved_json,
        );
        validate_restored_reward_history(
            &self.events,
            self.event_cursor_offset,
            self.world.step,
            self.reward_last,
            self.total_reward,
        );
        self.event_cursor()
    }

    pub fn legacy_strings(&self) -> Vec<String> {
        self.events
            .iter()
            .map(|event| event.message.clone())
            .collect()
    }

    pub fn event_cursor(&self) -> usize {
        self.event_cursor_offset + self.events.len()
    }

    pub fn achievements_unlocked(&self) -> Vec<String> {
        self.world
            .achievements
            .iter()
            .filter_map(|(name, count)| if *count > 0 { Some(name.clone()) } else { None })
            .collect()
    }

    pub fn private_json(&self) -> Value {
        let mut private = json!({
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "step_index": self.world.step,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "reward_breakdown": self.reward_breakdown,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "done_reason": self.done_reason,
            "max_steps": self.resolved_json.get("max_steps").cloned().unwrap_or(Value::Null),
            "unsupported_rules": self.resolved_json.get("unsupported_rules").cloned().unwrap_or_else(|| json!([])),
            "reward_mode": self.resolved_json.get("reward_mode").cloned().unwrap_or_else(|| json!("standard")),
            "objective": self.resolved_json.get("objective").cloned().unwrap_or(Value::Null),
            "achievements": self.achievements_unlocked()
        });
        if let Some(cause) = &self.world.last_damage_source {
            private["termination_cause"] = json!(cause);
        }
        let termination = termination_record(
            self.world.step,
            &self.done_reason,
            &self.world.last_damage_source,
        );
        if !termination.is_null() {
            private["termination"] = termination;
        }
        private
    }

    fn private_state_snapshot(&self) -> PrivateState {
        PrivateState {
            episode_id: self.episode_id.clone(),
            task_id: self.task_id.clone(),
            scenario_id: self.scenario_id.clone(),
            seed: self.seed,
            config_hash: self.config_hash.clone(),
            step_index: self.world.step,
            reward_last: self.reward_last,
            total_reward: self.total_reward,
            reward_breakdown: self.reward_breakdown.clone(),
            terminated: self.terminated,
            truncated: self.truncated,
            achievements: self.achievements_unlocked().into_iter().collect(),
            done_reason: self.done_reason.clone(),
        }
    }

    fn validate_restored_private_invariants(&self) {
        if self.seed != self.world.seed {
            panic!(
                "native Crafter checkpoint private seed {} does not match world seed {}",
                self.seed, self.world.seed
            );
        }
        let resolved_hash = self
            .resolved_json
            .get("config_hash")
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("native Crafter checkpoint resolved config_hash missing"));
        if self.config_hash != resolved_hash {
            panic!(
                "native Crafter checkpoint config_hash {} does not match resolved config_hash {}",
                self.config_hash, resolved_hash
            );
        }
        let resolved_task_id = self
            .resolved_json
            .get("task_id")
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("native Crafter checkpoint resolved task_id missing"));
        if self.task_id != resolved_task_id {
            panic!(
                "native Crafter checkpoint private task_id {} does not match resolved task_id {}",
                self.task_id, resolved_task_id
            );
        }
        let expected_episode_id = episode_id_for_task(&self.task_id, self.seed, &self.config_hash);
        if self.episode_id != expected_episode_id {
            panic!(
                "native Crafter checkpoint episode_id {} does not match deterministic episode_id {}",
                self.episode_id, expected_episode_id
            );
        }
        let resolved_scenario_id = self
            .resolved_json
            .get("scenario_id")
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("native Crafter checkpoint resolved scenario_id missing"));
        if self.scenario_id != resolved_scenario_id {
            panic!(
                "native Crafter checkpoint private scenario_id {} does not match resolved scenario_id {}",
                self.scenario_id, resolved_scenario_id
            );
        }
        if !self.reward_last.is_finite() {
            panic!("native Crafter checkpoint reward_last must be finite");
        }
        if !self.total_reward.is_finite() {
            panic!("native Crafter checkpoint total_reward must be finite");
        }
        validate_restored_reward_breakdown_state(
            &self.reward_breakdown,
            &self.resolved_json,
            &self.world,
        );
        if self.terminated && self.truncated {
            panic!("native Crafter checkpoint cannot be both terminated and truncated");
        }
        let expected_done_reason = self.done_reason_now();
        let expected_terminated = expected_done_reason.as_deref() == Some("death");
        let expected_truncated = expected_done_reason.as_deref() == Some("max_steps");
        if self.terminated != expected_terminated {
            panic!(
                "native Crafter checkpoint terminated={} does not match restored world terminal state",
                self.terminated
            );
        }
        if self.truncated != expected_truncated {
            panic!(
                "native Crafter checkpoint truncated={} does not match restored world terminal state",
                self.truncated
            );
        }
        if self.done_reason != expected_done_reason {
            panic!(
                "native Crafter checkpoint done_reason {:?} does not match restored world reason {:?}",
                self.done_reason, expected_done_reason
            );
        }
        let expected_achievements = self
            .achievements_unlocked()
            .into_iter()
            .collect::<BTreeSet<_>>();
        for achievement in &self.private.achievements {
            if !is_achievement_slot(achievement) {
                panic!(
                    "native Crafter checkpoint private achievement is unsupported: {}",
                    achievement
                );
            }
        }
        if self.private.achievements != expected_achievements {
            panic!("native Crafter checkpoint private achievements do not match restored world achievements");
        }
    }

    pub fn readout(&self) -> Value {
        let observation = self.current_observation();
        let private = self.private_json();
        let event_summary = event_summary(&self.events, self.event_cursor_offset);
        let public_inventory =
            project_inventory_for_resolved(&self.world.inventory, &self.resolved_json);
        let public_achievements =
            project_achievements_for_resolved(&self.world.achievements, &self.resolved_json);
        let mut readout = json!({
            "schema": "gamebench.crafter.readout.v1",
            "valid_actions": self.valid_actions(),
            "grid_hash": grid_hash(&observation),
            "local_tile_counts": local_tile_counts(&observation),
            "front_tile": front_tile(&observation),
            "public": {
                "observation": observation,
                "player_pos": [self.world.player_pos.0, self.world.player_pos.1],
                "inventory": public_inventory,
                "achievements": public_achievements,
                "done": self.terminated || self.truncated
            },
            "private": private,
            "observation": observation,
            "event_summary": event_summary,
            "nev_tail": self.legacy_strings().into_iter().rev().take(SNAPSHOT_NEV_TAIL).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>()
        });
        let text = observation_text(&readout);
        readout["observation_text"] = Value::String(text);
        readout
    }

    fn process_action(&mut self, action: &str, debug_events: &mut Vec<String>) {
        if self.world.player_sleeping && action != "noop" && action != "sleep" {
            self.wake_player();
            return;
        }
        match action {
            "move_left" | "move_right" | "move_up" | "move_down" => {
                self.move_player(action, debug_events)
            }
            "do" => self.do_action(debug_events),
            "sleep" => {
                if self.substrate_bool("fatigue_enabled", true)
                    && !self.adapter_hook("freeze_fatigue")
                    && self.inventory_amount("energy") < MAX_INVENTORY_VALUE
                {
                    self.world.player_sleeping = true;
                }
            }
            "place_stone" | "place_table" | "place_furnace" | "place_plant" => {
                self.place(action, debug_events)
            }
            "make_wood_pickaxe"
            | "make_stone_pickaxe"
            | "make_iron_pickaxe"
            | "make_diamond_pickaxe"
            | "make_wood_sword"
            | "make_stone_sword"
            | "make_iron_sword"
            | "make_diamond_sword"
            | "make_bow"
            | "make_arrow"
            | "make_iron_armor"
            | "make_diamond_armor" => self.craft(action, debug_events),
            "shoot" => self.shoot_arrow(debug_events),
            "drink_potion"
            | "drink_potion_red"
            | "drink_potion_green"
            | "drink_potion_blue"
            | "drink_potion_pink"
            | "drink_potion_cyan"
            | "drink_potion_yellow" => self.drink_potion(action, debug_events),
            _ => {}
        }
    }

    fn move_player(&mut self, action: &str, debug_events: &mut Vec<String>) {
        let dir = match action {
            "move_left" => (-1, 0),
            "move_right" => (1, 0),
            "move_up" => (0, -1),
            "move_down" => (0, 1),
            _ => (0, 0),
        };
        self.world.player_facing = dir;
        let target = (
            self.world.player_pos.0 + dir.0,
            self.world.player_pos.1 + dir.1,
        );
        if !self.in_bounds(target) || !WALKABLE.contains(&self.tile(target).as_str()) {
            return;
        }
        if self.entity_index_at(target).is_some() {
            return;
        }
        self.world.player_pos = target;
        if self.tile(target) == "lava" {
            self.apply_player_damage("lava", MAX_INVENTORY_VALUE);
        }
        debug_events.push(format!("ACTION: {}", display_action(action)));
    }

    fn do_action(&mut self, debug_events: &mut Vec<String>) {
        let target = self.front_pos();
        if let Some(idx) = self.entity_index_at(target) {
            let kind = self.world.entities[idx].kind.clone();
            self.interact_entity(idx);
            debug_events.push(format!(
                "ACTION: Do on {} at ({}, {})",
                kind, target.0, target.1
            ));
            return;
        }
        let tile = self.tile(target);
        match tile.as_str() {
            "tree" => {
                self.set_tile(target, "grass");
                self.add_inventory("wood", 1);
                self.add_achievement("collect_wood", 1);
            }
            "stone" if self.best_pickaxe_tier() >= 1 => {
                self.set_tile(target, "path");
                self.add_inventory("stone", 1);
                self.add_achievement("collect_stone", 1);
            }
            "coal" if self.best_pickaxe_tier() >= 1 => {
                self.set_tile(target, "path");
                self.add_inventory("coal", 1);
                self.add_achievement("collect_coal", 1);
            }
            "iron" if self.best_pickaxe_tier() >= 2 => {
                self.set_tile(target, "path");
                self.add_inventory("iron", 1);
                self.add_achievement("collect_iron", 1);
            }
            "diamond" if self.best_pickaxe_tier() >= 3 => {
                self.set_tile(target, "path");
                self.add_inventory("diamond", 1);
                self.add_achievement("collect_diamond", 1);
            }
            "sapphire" if self.craftax_items_enabled() && self.best_pickaxe_tier() >= 4 => {
                self.set_tile(target, "path");
                self.add_inventory("sapphire", 1);
                self.add_achievement("collect_sapphire", 1);
            }
            "ruby" if self.craftax_items_enabled() && self.best_pickaxe_tier() >= 4 => {
                self.set_tile(target, "path");
                self.add_inventory("ruby", 1);
                self.add_achievement("collect_ruby", 1);
            }
            "water" => {
                self.world.thirst_counter = 0.0;
                self.add_inventory("drink", 1);
                self.add_achievement("collect_drink", 1);
            }
            "grass" if self.world.rng.random_f32() < 0.1 => {
                self.add_inventory("sapling", 1);
                self.add_achievement("collect_sapling", 1);
            }
            "chest" => {
                if self.craftax_chests_enabled() {
                    self.set_tile(target, "path");
                    self.add_achievement("open_chest", 1);
                    self.open_chest();
                }
            }
            _ => {}
        }
        debug_events.push(format!(
            "ACTION: Do on {} at ({}, {})",
            tile, target.0, target.1
        ));
    }

    fn interact_entity(&mut self, idx: usize) {
        if self.world.entities[idx].kind == "plant" {
            if self.entity_i32(idx, "grown", 0) > 300 {
                self.set_entity_i32(idx, "grown", 0);
                self.add_inventory("food", 4);
                self.add_achievement("eat_plant", 1);
            }
            return;
        }
        if !self.craftax_feature_enabled("combat_enabled") {
            return;
        }
        let damage = self.attack_damage();
        self.world.entities[idx].health -= damage;
        if self.world.entities[idx].health > 0 {
            return;
        }
        let entity = self.world.entities.remove(idx);
        self.apply_defeat_rewards(&entity.kind);
    }

    fn place(&mut self, action: &str, debug_events: &mut Vec<String>) {
        let target = self.front_pos();
        if !self.in_bounds(target) || self.entity_index_at(target).is_some() {
            return;
        }
        let tile = self.tile(target);
        if action == "place_plant" {
            if tile != "grass" {
                return;
            }
            if self.use_inventory("sapling", 1) {
                self.add_achievement("place_plant", 1);
                let id = self.next_entity_id();
                self.world.entities.push(Entity {
                    id,
                    kind: "plant".to_string(),
                    pos: target,
                    health: 1,
                    metadata: BTreeMap::from([("grown".to_string(), json!(0))]),
                });
            }
            return;
        }
        let (material, resource, amount) = match action {
            "place_stone" => ("stone", "stone", 1),
            "place_table" => ("table", "wood", 2),
            "place_furnace" => ("furnace", "stone", 4),
            _ => return,
        };
        let allowed = match action {
            "place_stone" => matches!(tile.as_str(), "grass" | "sand" | "path" | "water" | "lava"),
            "place_table" | "place_furnace" => matches!(tile.as_str(), "grass" | "sand" | "path"),
            _ => false,
        };
        if !allowed {
            return;
        }
        if !self.use_inventory(resource, amount) {
            return;
        }
        self.set_tile(target, material);
        self.add_achievement(action, 1);
        debug_events.push(format!("ACTION: {}", display_action(action)));
    }

    fn craft(&mut self, action: &str, debug_events: &mut Vec<String>) {
        if is_craftax_recipe_action(action)
            && (!self.craftax_recipes_enabled() || !self.craftax_items_enabled())
        {
            return;
        }
        if !self.has_adjacent("table") {
            return;
        }
        let (recipe, item, gives, needs_furnace): (Vec<(&str, i32)>, &str, i32, bool) = match action
        {
            "make_wood_pickaxe" => (vec![("wood", 1)], "wood_pickaxe", 1, false),
            "make_stone_pickaxe" => (vec![("wood", 1), ("stone", 1)], "stone_pickaxe", 1, false),
            "make_diamond_pickaxe" => (
                vec![("wood", 1), ("diamond", 1)],
                "diamond_pickaxe",
                1,
                false,
            ),
            "make_wood_sword" => (vec![("wood", 1)], "wood_sword", 1, false),
            "make_stone_sword" => (vec![("wood", 1), ("stone", 1)], "stone_sword", 1, false),
            "make_diamond_sword" => (vec![("wood", 1), ("diamond", 2)], "diamond_sword", 1, false),
            "make_iron_pickaxe" => (
                vec![("wood", 1), ("coal", 1), ("iron", 1)],
                "iron_pickaxe",
                1,
                true,
            ),
            "make_iron_sword" => (
                vec![("wood", 1), ("coal", 1), ("iron", 1)],
                "iron_sword",
                1,
                true,
            ),
            "make_bow" => (vec![("wood", 2)], "bow", 1, false),
            "make_arrow" => (vec![("wood", 1), ("stone", 1)], "arrows", 3, false),
            "make_iron_armor" => (vec![("coal", 3), ("iron", 3)], "", 1, true),
            "make_diamond_armor" => (vec![("diamond", 3)], "", 2, false),
            _ => return,
        };
        if needs_furnace && !self.has_adjacent("furnace") {
            return;
        }
        if !recipe
            .iter()
            .all(|(key, amount)| self.inventory_amount(key) >= *amount)
        {
            return;
        }
        for (key, amount) in recipe {
            self.use_inventory(key, amount);
        }
        match action {
            "make_iron_armor" => self.set_armor_pieces(1),
            "make_diamond_armor" => self.set_armor_pieces(2),
            _ => self.add_inventory(item, gives),
        }
        self.add_achievement(action, 1);
        debug_events.push(format!("ACTION: {}", display_action(action)));
    }

    fn shoot_arrow(&mut self, debug_events: &mut Vec<String>) {
        if !self.craftax_feature_enabled("combat_enabled") || !self.craftax_items_enabled() {
            return;
        }
        let dir = self.world.player_facing;
        if dir == (0, 0) || self.inventory_amount("bow") <= 0 {
            return;
        }
        let target = self.front_pos();
        if !self.in_bounds(target) || self.entity_index_at(target).is_some() {
            return;
        }
        if !self.use_inventory("arrows", 1) {
            return;
        }
        let mut metadata = BTreeMap::new();
        metadata.insert("source".to_string(), json!("runtime"));
        metadata.insert("facing".to_string(), json!([dir.0, dir.1]));
        metadata.insert(
            "damage".to_string(),
            json!(scaled_damage(
                2.0 * self.substrate_f64("arrow_damage_mult", 1.0),
                1.0
            )),
        );
        metadata.insert("damage_source".to_string(), json!("player_arrow"));
        let id = self.next_entity_id();
        self.world.entities.push(Entity {
            id,
            kind: "arrow".to_string(),
            pos: target,
            health: 1,
            metadata,
        });
        debug_events.push(format!("ACTION: {}", display_action("shoot")));
    }

    fn drink_potion(&mut self, action: &str, debug_events: &mut Vec<String>) {
        if !self.craftax_potions_enabled() {
            return;
        }
        let Some((color, key)) = potion_for_action(action, &self.world.inventory) else {
            return;
        };
        if !self.use_inventory(key, 1) {
            return;
        }
        match color {
            "red" => self.add_inventory("health", 2),
            "green" => self.add_inventory("food", 2),
            "blue" => self.add_inventory("drink", 2),
            "yellow" => self.add_inventory("energy", 2),
            "pink" | "cyan" => {}
            _ => unreachable!("potion_for_action returns supported potion colors"),
        }
        self.add_achievement("drink_potion", 1);
        debug_events.push(format!(
            "ACTION: {}",
            display_action(&format!("drink_potion_{}", color))
        ));
    }

    fn open_chest(&mut self) {
        let items_enabled = self.craftax_items_enabled();
        let potions_enabled = self.craftax_potions_enabled();
        if self.world.rng.random_f32() < 0.5 {
            let arrows = self.world.rng.gen_range_u32_inclusive(2, 6) as i32;
            if items_enabled {
                self.add_inventory("arrows", arrows);
            }
        }
        if self.world.rng.random_f32() < 0.35 {
            let potion_idx = self.world.rng.gen_range_u32_inclusive(0, 5) as usize;
            if items_enabled && potions_enabled {
                self.add_inventory(POTION_SLOTS[potion_idx].1, 1);
            }
        }
        if self.world.rng.random_f32() < 0.2 {
            if self.world.rng.random_f32() < 0.5 {
                if items_enabled {
                    self.add_inventory("sapphire", 1);
                    self.add_achievement("collect_sapphire", 1);
                }
            } else if items_enabled {
                self.add_inventory("ruby", 1);
                self.add_achievement("collect_ruby", 1);
            }
        }
        if self.world.rng.random_f32() < 0.6 {
            let coal = self.world.rng.gen_range_u32_inclusive(1, 2) as i32;
            if items_enabled {
                self.add_inventory("coal", coal);
                self.add_achievement("collect_coal", 1);
            }
        }
        if self.world.rng.random_f32() < 0.4 {
            let iron = self.world.rng.gen_range_u32_inclusive(1, 2) as i32;
            if items_enabled {
                self.add_inventory("iron", iron);
                self.add_achievement("collect_iron", 1);
            }
        }
        if self.world.rng.random_f32() < 0.2 && items_enabled {
            self.add_inventory("diamond", 1);
            self.add_achievement("collect_diamond", 1);
        }
    }

    fn apply_defeat_rewards(&mut self, kind: &str) {
        match kind {
            "cow" => {
                self.add_inventory("food", 6);
                self.add_achievement("eat_cow", 1);
            }
            other => {
                if let Some(achievement) = defeat_achievement(other) {
                    self.add_achievement(achievement, 1);
                    if self.substrate_profile() == "craftax_partial" {
                        self.grant_xp(3);
                    } else if !matches!(other, "zombie" | "skeleton") {
                        self.grant_xp(2);
                    }
                }
            }
        }
    }

    fn grant_xp(&mut self, amount: i32) {
        if !self.craftax_feature_enabled("xp_enabled") {
            return;
        }
        let amount = i64::from(amount);
        let xp = self.inventory_counter("xp").saturating_add(amount).max(0);
        self.world.inventory.insert("xp".to_string(), xp);
        self.add_achievement("gain_xp", amount);
        let level = self.inventory_counter("level").max(0);
        let target_level = xp / 10;
        if target_level > level {
            let levels_gained = target_level - level;
            self.world
                .inventory
                .insert("level".to_string(), target_level);
            let stat_points = self
                .inventory_counter("stat_points")
                .saturating_add(levels_gained);
            self.world
                .inventory
                .insert("stat_points".to_string(), stat_points);
            self.add_achievement("reach_level", levels_gained);
        }
    }

    fn substrate_profile(&self) -> &str {
        self.resolved_json
            .get("substrate_profile")
            .and_then(Value::as_str)
            .unwrap_or("classic")
    }

    fn craftax_feature_enabled(&self, key: &str) -> bool {
        if self.substrate_profile() != "craftax_partial" {
            return true;
        }
        let craftax = self
            .resolved_json
            .get("rules")
            .and_then(|rules| rules.get("craftax"))
            .unwrap_or(&Value::Null);
        craftax_rule_bool(craftax, "enabled", true) && craftax_rule_bool(craftax, key, true)
    }

    fn craftax_items_enabled(&self) -> bool {
        self.substrate_profile() == "craftax_partial"
            && self.craftax_feature_enabled("items_enabled")
    }

    fn craftax_chests_enabled(&self) -> bool {
        self.craftax_items_enabled() && self.craftax_feature_enabled("chests_enabled")
    }

    fn craftax_potions_enabled(&self) -> bool {
        self.craftax_items_enabled() && self.craftax_feature_enabled("potions_enabled")
    }

    fn craftax_recipes_enabled(&self) -> bool {
        self.resolved_json
            .get("rules")
            .and_then(|rules| rules.get("crafting"))
            .map(|crafting| craftax_rule_bool(crafting, "craftax_recipes", false))
            .unwrap_or(false)
    }

    fn craftax_achievements_enabled(&self) -> bool {
        let include_craftax = self
            .resolved_json
            .get("rules")
            .and_then(|rules| rules.get("achievements"))
            .and_then(|achievements| achievements.get("enabled"))
            .and_then(Value::as_str)
            .unwrap_or("classic")
            == "classic_plus_craftax";
        include_craftax && self.craftax_feature_enabled("achievements_enabled")
    }

    fn advance_runtime(
        &mut self,
        action: &str,
        before: TickBefore,
        debug_events: &mut Vec<String>,
    ) {
        let drink_after_action = self.inventory_amount("drink");
        let food_after_action = self.inventory_amount("food");
        let energy_after_action = self.inventory_amount("energy");
        if drink_after_action != before.drink {
            debug_events.push(format!(
                "DRINK: {} -> {} (from action {})",
                before.drink,
                drink_after_action,
                display_action(action)
            ));
        }
        if food_after_action != before.food {
            debug_events.push(format!(
                "FOOD: {} -> {} (from action {})",
                before.food,
                food_after_action,
                display_action(action)
            ));
        }
        if energy_after_action != before.energy {
            debug_events.push(format!(
                "ENERGY: {} -> {} (from action {})",
                before.energy,
                energy_after_action,
                display_action(action)
            ));
        }

        self.update_life_stats();

        let drink_after_stats = self.inventory_amount("drink");
        let food_after_stats = self.inventory_amount("food");
        let energy_after_stats = self.inventory_amount("energy");
        if food_after_stats != food_after_action {
            debug_events.push(format!(
                "FOOD (hunger): {} -> {} (from life_stats)",
                food_after_action, food_after_stats
            ));
        }
        if drink_after_stats != drink_after_action {
            debug_events.push(format!(
                "DRINK (thirst): {} -> {} (from life_stats)",
                drink_after_action, drink_after_stats
            ));
        }
        if before.sleeping && energy_after_stats != energy_after_action {
            debug_events.push(format!(
                "ENERGY (sleeping): {} -> {} (from life_stats)",
                energy_after_action, energy_after_stats
            ));
        }

        if self.world.player_sleeping && self.inventory_amount("energy") >= MAX_INVENTORY_VALUE {
            self.wake_player();
        }

        self.process_mobs();
        self.process_arrows();
        self.process_plants();
        self.spawn_despawn_mobs();

        let health_after = self.inventory_amount("health");
        if health_after < before.health {
            let cause = self
                .world
                .last_damage_source
                .as_deref()
                .unwrap_or("unknown");
            debug_events.push(format!(
                "DAMAGE: {} -> {} (cause: {})",
                before.health, health_after, cause
            ));
        }
    }

    fn update_daylight_for_step(&mut self, step: u64) {
        if self.adapter_hook("freeze_daylight") {
            self.world.daylight = 1.0;
            return;
        }
        if !self.substrate_bool("day_night_cycle", true) {
            self.world.daylight = 1.0;
            return;
        }
        let period = self
            .substrate_u64("day_cycle_period", DEFAULT_DAY_CYCLE_PERIOD)
            .max(1);
        let progress = (step as f64 / period as f64) % 1.0 + 0.3;
        self.world.daylight = 1.0 - (std::f64::consts::PI * progress).cos().abs().powi(3);
    }

    fn update_life_stats(&mut self) {
        if self.substrate_bool("hunger_enabled", true) && !self.adapter_hook("freeze_hunger") {
            let increment = if self.world.player_sleeping { 0.5 } else { 1.0 };
            self.world.hunger_counter += increment;
            if self.world.hunger_counter > self.survival_f64("hunger_rate", DEFAULT_HUNGER_RATE) {
                self.world.hunger_counter = 0.0;
                if self.inventory_amount("food") > 0 {
                    self.add_inventory("food", -1);
                }
            }
        }

        if self.substrate_bool("thirst_enabled", true) && !self.adapter_hook("freeze_thirst") {
            let increment = if self.world.player_sleeping { 0.5 } else { 1.0 };
            self.world.thirst_counter += increment;
            if self.world.thirst_counter > self.survival_f64("thirst_rate", DEFAULT_THIRST_RATE) {
                self.world.thirst_counter = 0.0;
                if self.inventory_amount("drink") > 0 {
                    self.add_inventory("drink", -1);
                }
            }
        }

        if self.substrate_bool("fatigue_enabled", true) && !self.adapter_hook("freeze_fatigue") {
            if self.world.player_sleeping {
                self.world.fatigue_counter -= 1;
            } else {
                self.world.fatigue_counter += 1;
            }
            if self.world.fatigue_counter > 30 {
                self.world.fatigue_counter = 0;
                if self.inventory_amount("energy") > 0 {
                    self.add_inventory("energy", -1);
                }
            } else if self.world.fatigue_counter < -10 {
                self.world.fatigue_counter = 0;
                self.add_inventory("energy", 1);
            }
        }

        if !self.substrate_bool("health_enabled", true) {
            self.world.recover_counter = 0.0;
            self.world
                .inventory
                .insert("health".to_string(), i64::from(MAX_INVENTORY_VALUE));
            self.world.last_health = MAX_INVENTORY_VALUE;
            self.world.last_damage_source = None;
            return;
        }

        let hunger_enabled =
            self.substrate_bool("hunger_enabled", true) && !self.adapter_hook("freeze_hunger");
        let thirst_enabled =
            self.substrate_bool("thirst_enabled", true) && !self.adapter_hook("freeze_thirst");
        let fatigue_enabled =
            self.substrate_bool("fatigue_enabled", true) && !self.adapter_hook("freeze_fatigue");
        let has_energy =
            !fatigue_enabled || self.inventory_amount("energy") > 0 || self.world.player_sleeping;
        let depleted = (hunger_enabled && self.inventory_amount("food") == 0)
            || (thirst_enabled && self.inventory_amount("drink") == 0)
            || !has_energy;
        if depleted {
            let degen_rate = if self.world.player_sleeping { 0.5 } else { 1.0 };
            self.world.recover_counter -= degen_rate;
            if self.world.recover_counter < -15.0 {
                self.world.recover_counter = 0.0;
                let source = if hunger_enabled && self.inventory_amount("food") == 0 {
                    "starvation"
                } else if thirst_enabled && self.inventory_amount("drink") == 0 {
                    "thirst"
                } else {
                    "exhaustion"
                };
                self.apply_player_damage(source, 1);
            }
        } else {
            let recover_rate = if self.world.player_sleeping { 2.0 } else { 1.0 };
            self.world.recover_counter += recover_rate;
            if self.world.recover_counter > 25.0 {
                self.world.recover_counter = 0.0;
                self.add_inventory("health", 1);
            }
        }

        if self.world.player_sleeping && self.inventory_amount("health") < self.world.last_health {
            self.wake_player();
        }
        self.world.last_health = self.inventory_amount("health");
    }

    fn process_mobs(&mut self) {
        if self.adapter_hook("suppress_mobs") || !self.substrate_bool("mobs_enabled", true) {
            return;
        }
        let initial_len = self.world.entities.len();
        for idx in 0..initial_len {
            if idx >= self.world.entities.len() {
                break;
            }
            let kind = self.world.entities[idx].kind.clone();
            match kind.as_str() {
                "cow" => self.process_cow_ai(idx),
                "zombie" => self.process_zombie_ai(idx),
                "skeleton" => self.process_skeleton_ai(idx),
                _ if craftax_mob_stats(&kind).is_some() => {
                    if self.craftax_feature_enabled("mobs_enabled") {
                        self.process_craftax_mob_ai(idx);
                    }
                }
                _ => {}
            }
        }
    }

    fn process_cow_ai(&mut self, idx: usize) {
        if self.world.rng.random_f32() < 0.5 {
            return;
        }
        let pos = self.world.entities[idx].pos;
        let dir = self.random_direction();
        let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
        if self.is_empty_walkable(new_pos) {
            self.world.entities[idx].pos = new_pos;
        }
    }

    fn process_zombie_ai(&mut self, idx: usize) {
        let mut pos = self.world.entities[idx].pos;
        let dist = manhattan(pos, self.world.player_pos);
        if dist <= 8 && self.world.rng.random_f32() < 0.9 {
            let long_axis = self.world.rng.random_f32() < 0.8;
            let dir = self.toward_direction(pos, self.world.player_pos, long_axis);
            let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
            if self.is_empty_walkable(new_pos) {
                self.world.entities[idx].pos = new_pos;
                pos = new_pos;
            }
        } else {
            let dir = self.random_direction();
            let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
            if self.is_empty_walkable(new_pos) {
                self.world.entities[idx].pos = new_pos;
                pos = new_pos;
            }
        }

        if self.craftax_feature_enabled("combat_enabled")
            && manhattan(pos, self.world.player_pos) <= 1
        {
            let cooldown = self.entity_i32(idx, "cooldown", 0);
            if cooldown > 0 {
                self.set_entity_i32(idx, "cooldown", cooldown - 1);
            } else {
                let damage = scaled_damage(
                    2.0 * self.substrate_f64("zombie_damage_mult", 1.0),
                    if self.world.player_sleeping { 3.5 } else { 1.0 },
                );
                self.apply_player_damage("zombie", damage);
                if self.world.player_sleeping {
                    self.wake_player();
                }
                self.set_entity_i32(idx, "cooldown", 5);
            }
        }
    }

    fn process_skeleton_ai(&mut self, idx: usize) {
        let reload = self.entity_i32(idx, "reload", 0).saturating_sub(1).max(0);
        self.set_entity_i32(idx, "reload", reload);

        let pos = self.world.entities[idx].pos;
        let dist = manhattan(pos, self.world.player_pos);
        if dist <= 3 {
            let long_axis = self.world.rng.random_f32() < 0.6;
            let toward = self.toward_direction(pos, self.world.player_pos, long_axis);
            let dir = (-toward.0, -toward.1);
            let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
            if self.is_empty_walkable(new_pos) {
                self.world.entities[idx].pos = new_pos;
                return;
            }
        }

        if self.craftax_feature_enabled("combat_enabled")
            && dist <= 5
            && self.world.rng.random_f32() < 0.5
        {
            if reload == 0 {
                let dir = self.toward_direction(pos, self.world.player_pos, true);
                if dir != (0, 0) {
                    let arrow_pos = (pos.0 + dir.0, pos.1 + dir.1);
                    if self.in_bounds(arrow_pos)
                        && self.entity_index_at(arrow_pos).is_none()
                        && arrow_pos != self.world.player_pos
                    {
                        let mut metadata = BTreeMap::new();
                        metadata.insert("source".to_string(), json!("runtime"));
                        metadata.insert("facing".to_string(), json!([dir.0, dir.1]));
                        metadata.insert(
                            "damage".to_string(),
                            json!(scaled_damage(
                                2.0 * self.substrate_f64("arrow_damage_mult", 1.0),
                                1.0
                            )),
                        );
                        metadata.insert("damage_source".to_string(), json!("arrow"));
                        let id = self.next_entity_id();
                        self.world.entities.push(Entity {
                            id,
                            kind: "arrow".to_string(),
                            pos: arrow_pos,
                            health: 1,
                            metadata,
                        });
                    }
                    self.set_entity_i32(idx, "reload", 4);
                }
            }
        } else if dist <= 8 && self.world.rng.random_f32() < 0.3 {
            let long_axis = self.world.rng.random_f32() < 0.6;
            let dir = self.toward_direction(pos, self.world.player_pos, long_axis);
            let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
            if self.is_empty_walkable(new_pos) {
                self.world.entities[idx].pos = new_pos;
            }
        } else if self.world.rng.random_f32() < 0.2 {
            let dir = self.random_direction();
            let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
            if self.is_empty_walkable(new_pos) {
                self.world.entities[idx].pos = new_pos;
            }
        }
    }

    fn process_craftax_mob_ai(&mut self, idx: usize) {
        let kind = self.world.entities[idx].kind.clone();
        let Some(stats) = craftax_mob_stats(&kind) else {
            return;
        };
        let pos = self.world.entities[idx].pos;

        let cooldown = self.entity_i32(idx, "cooldown", 0);

        if stats.passive {
            let move_chance = match kind.as_str() {
                "bat" => 0.6,
                "snail" => 0.3,
                _ => 0.4,
            };
            if self.world.rng.random_f32() < move_chance {
                let dir = self.random_direction();
                let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
                let walkable = if kind == "bat" {
                    self.in_bounds(new_pos)
                        && self.entity_index_at(new_pos).is_none()
                        && new_pos != self.world.player_pos
                } else {
                    self.is_empty_walkable(new_pos)
                };
                if walkable {
                    self.world.entities[idx].pos = new_pos;
                }
            }
            return;
        }

        let dist = manhattan(pos, self.world.player_pos);
        let combat_enabled = self.craftax_feature_enabled("combat_enabled");
        let mut attacked = false;

        if combat_enabled && stats.ranged_damage > 0 && dist <= stats.range && cooldown <= 0 {
            let dir = self.toward_direction(pos, self.world.player_pos, true);
            if dir != (0, 0) {
                let arrow_pos = (pos.0 + dir.0, pos.1 + dir.1);
                if self.in_bounds(arrow_pos) {
                    if self.entity_index_at(arrow_pos).is_none()
                        && arrow_pos != self.world.player_pos
                    {
                        let mut metadata = BTreeMap::new();
                        metadata.insert("source".to_string(), json!("runtime"));
                        metadata.insert("facing".to_string(), json!([dir.0, dir.1]));
                        metadata.insert(
                            "damage".to_string(),
                            json!(scaled_damage(
                                stats.ranged_damage as f64,
                                self.substrate_f64("arrow_damage_mult", 1.0),
                            )),
                        );
                        metadata.insert(
                            "damage_source".to_string(),
                            json!(stats.ranged_damage_source),
                        );
                        metadata
                            .insert("projectile_kind".to_string(), json!(stats.projectile_kind));
                        let id = self.next_entity_id();
                        self.world.entities.push(Entity {
                            id,
                            kind: "arrow".to_string(),
                            pos: arrow_pos,
                            health: 1,
                            metadata,
                        });
                    }
                    self.set_entity_i32(idx, "cooldown", stats.cooldown);
                    attacked = true;
                }
            }
        }

        if combat_enabled && stats.melee_damage > 0 && dist <= 1 && cooldown <= 0 {
            let damage = scaled_damage(
                stats.melee_damage as f64,
                if self.world.player_sleeping { 3.5 } else { 1.0 },
            );
            self.apply_player_damage("craftax_melee", damage);
            if self.world.player_sleeping {
                self.wake_player();
            }
            self.set_entity_i32(idx, "cooldown", stats.cooldown);
            attacked = true;
        }

        if attacked {
            return;
        }

        if cooldown > 0 {
            self.set_entity_i32(idx, "cooldown", cooldown.saturating_sub(1));
        }

        let flee = stats.ranged_damage > 0 && dist <= 2;
        let move_toward = dist <= 8 && self.world.rng.random_f32() < 0.6;
        let move_random = self.world.rng.random_f32() < 0.2;
        let dir = if flee {
            let toward = self.toward_direction(pos, self.world.player_pos, true);
            (-toward.0, -toward.1)
        } else if move_toward {
            self.toward_direction(pos, self.world.player_pos, true)
        } else if move_random {
            self.random_direction()
        } else {
            (0, 0)
        };

        if dir != (0, 0) {
            let new_pos = (pos.0 + dir.0, pos.1 + dir.1);
            if self.is_empty_walkable(new_pos) {
                self.world.entities[idx].pos = new_pos;
            }
        }
    }

    fn process_arrows(&mut self) {
        let arrow_ids = self
            .world
            .entities
            .iter()
            .filter(|entity| entity.kind == "arrow")
            .map(|entity| entity.id.clone())
            .collect::<Vec<_>>();
        for id in arrow_ids {
            let Some(idx) = self.entity_index_by_id(&id) else {
                continue;
            };
            let arrow = self.world.entities[idx].clone();
            let facing = metadata_pos(&arrow.metadata, "facing").unwrap_or((0, 0));
            if facing == (0, 0) {
                self.remove_entity_by_id(&id);
                continue;
            }
            let next_pos = (arrow.pos.0 + facing.0, arrow.pos.1 + facing.1);
            let damage = self.entity_i32(idx, "damage", 2);
            let source = arrow
                .metadata
                .get("damage_source")
                .and_then(Value::as_str)
                .unwrap_or("arrow")
                .to_string();
            let craftax_mob_projectile =
                matches!(source.as_str(), "craftax_ranged" | "craftax_magic");

            if next_pos == self.world.player_pos {
                if source == "player_arrow" {
                    if let Some(idx) = self.entity_index_by_id(&id) {
                        self.world.entities[idx].pos = next_pos;
                    }
                    continue;
                }
                if self.craftax_feature_enabled("combat_enabled") {
                    self.apply_player_damage(&source, damage);
                }
                if self.world.player_sleeping {
                    self.wake_player();
                }
                self.remove_entity_by_id(&id);
                continue;
            }

            if let Some(target_idx) = self.entity_index_at(next_pos) {
                if target_idx != idx {
                    if craftax_mob_projectile {
                        self.remove_entity_by_id(&id);
                        continue;
                    }
                    if self.craftax_feature_enabled("combat_enabled") {
                        self.world.entities[target_idx].health -= damage;
                        if self.world.entities[target_idx].health <= 0 {
                            let defeated = self.world.entities.remove(target_idx);
                            if source == "player_arrow" {
                                self.apply_defeat_rewards(&defeated.kind);
                            }
                        }
                    }
                    self.remove_entity_by_id(&id);
                    continue;
                }
            }

            if !self.in_bounds(next_pos) {
                self.remove_entity_by_id(&id);
                continue;
            }
            let tile = self.tile(next_pos);
            if tile == "table" || tile == "furnace" {
                if craftax_mob_projectile {
                    self.set_tile(next_pos, "path");
                }
                self.remove_entity_by_id(&id);
                continue;
            }
            if !(WALKABLE.contains(&tile.as_str()) || tile == "water" || tile == "lava") {
                self.remove_entity_by_id(&id);
                continue;
            }
            if let Some(idx) = self.entity_index_by_id(&id) {
                self.world.entities[idx].pos = next_pos;
            }
        }
    }

    fn process_plants(&mut self) {
        let plant_ids = self
            .world
            .entities
            .iter()
            .filter(|entity| entity.kind == "plant")
            .map(|entity| entity.id.clone())
            .collect::<Vec<_>>();
        for id in plant_ids {
            let Some(idx) = self.entity_index_by_id(&id) else {
                continue;
            };
            let pos = self.world.entities[idx].pos;
            let damaged = [(0, 1), (0, -1), (1, 0), (-1, 0)].iter().any(|(dx, dy)| {
                self.entity_index_at((pos.0 + dx, pos.1 + dy))
                    .map(|adj| {
                        matches!(
                            self.world.entities[adj].kind.as_str(),
                            "cow"
                                | "zombie"
                                | "skeleton"
                                | "orc_soldier"
                                | "orc_mage"
                                | "knight"
                                | "knight_archer"
                                | "troll"
                        )
                    })
                    .unwrap_or(false)
            });
            if damaged {
                self.world.entities[idx].health -= 1;
            } else {
                let grown = self.entity_i32(idx, "grown", 0) + 1;
                self.set_entity_i32(idx, "grown", grown);
            }
        }
        self.world
            .entities
            .retain(|entity| !(entity.kind == "plant" && entity.health <= 0));
    }

    fn spawn_despawn_mobs(&mut self) {
        if self.adapter_hook("suppress_mobs") || !self.substrate_bool("mobs_enabled", true) {
            return;
        }
        let player_pos = self.world.player_pos;
        let cow_despawn_rate = self.mob_f64("cow_despawn_rate", DEFAULT_COW_DESPAWN_RATE);
        let zombie_despawn_rate = self.mob_f64("zombie_despawn_rate", DEFAULT_ZOMBIE_DESPAWN_RATE);
        let craftax_mobs_enabled = self.craftax_feature_enabled("mobs_enabled");
        let mut idx = 0;
        while idx < self.world.entities.len() {
            let pos = self.world.entities[idx].pos;
            let dist = manhattan(pos, player_pos);
            let remove = dist > 30
                && match self.world.entities[idx].kind.as_str() {
                    "cow" => self.world.rng.random_f64() < cow_despawn_rate,
                    "zombie" => self.world.rng.random_f64() < zombie_despawn_rate,
                    kind if craftax_mobs_enabled => craftax_mob_stats(kind)
                        .map(|stats| {
                            let rate = if stats.passive {
                                cow_despawn_rate
                            } else {
                                zombie_despawn_rate
                            };
                            self.world.rng.random_f64() < rate
                        })
                        .unwrap_or(false),
                    _ => false,
                };
            if remove {
                self.world.entities.remove(idx);
            } else {
                idx += 1;
            }
        }

        let zombie_spawn_rate = self.substrate_f64("zombie_spawn_rate", 0.3);
        if self.world.daylight < 0.5 && self.world.rng.random_f64() < zombie_spawn_rate * 0.01 {
            if let Some(pos) = self.random_spawn_near_player(15.0, 25.0) {
                self.spawn_entity(
                    "zombie",
                    pos,
                    resolved_entity_health(&self.resolved_json, "zombie"),
                );
            }
        }
        let cow_spawn_rate = self.substrate_f64("cow_spawn_rate", 0.01);
        if self.world.rng.random_f64() < cow_spawn_rate * 0.1 {
            if let Some(pos) = self.random_spawn_near_player(10.0, 25.0) {
                self.spawn_entity(
                    "cow",
                    pos,
                    resolved_entity_health(&self.resolved_json, "cow"),
                );
            }
        }

        if self.substrate_profile() != "craftax_partial" || !craftax_mobs_enabled {
            return;
        }
        if self.world.daylight < 0.5 {
            for (kind, base_rate) in [
                ("orc_soldier", 0.01),
                ("orc_mage", 0.008),
                ("knight", 0.004),
                ("knight_archer", 0.004),
                ("troll", 0.003),
            ] {
                if self.world.rng.random_f64() < base_rate {
                    if let Some(pos) = self.random_in_bounds_near_player(12.0, 20.0, 6) {
                        self.spawn_entity(
                            kind,
                            pos,
                            resolved_entity_health(&self.resolved_json, kind),
                        );
                    }
                }
            }
        }
        if self.world.rng.random_f64() < 0.02 {
            if let Some(pos) = self.random_in_bounds_near_player(8.0, 16.0, 6) {
                if self.tile(pos) == "grass" {
                    self.spawn_entity(
                        "snail",
                        pos,
                        resolved_entity_health(&self.resolved_json, "snail"),
                    );
                }
            }
        }
        if self.world.rng.random_f64() < 0.02 {
            if let Some(pos) = self.random_in_bounds_near_player(8.0, 16.0, 6) {
                if self.tile(pos) == "path" {
                    self.spawn_entity(
                        "bat",
                        pos,
                        resolved_entity_health(&self.resolved_json, "bat"),
                    );
                }
            }
        }
    }

    fn random_spawn_near_player(&mut self, min_dist: f64, max_dist: f64) -> Option<(i32, i32)> {
        let angle = self.world.rng.random_f64() * std::f64::consts::TAU;
        let dist = min_dist + self.world.rng.random_f64() * (max_dist - min_dist);
        let pos = (
            self.world.player_pos.0 + (angle.cos() * dist) as i32,
            self.world.player_pos.1 + (angle.sin() * dist) as i32,
        );
        if self.is_empty_walkable(pos) {
            return Some(pos);
        }
        None
    }

    fn random_in_bounds_near_player(
        &mut self,
        min_dist: f64,
        max_dist: f64,
        attempts: usize,
    ) -> Option<(i32, i32)> {
        if max_dist <= 0.0 || min_dist < 0.0 {
            return None;
        }
        for _ in 0..attempts {
            let angle = self.world.rng.random_f64() * std::f64::consts::TAU;
            let dist = min_dist + self.world.rng.random_f64() * (max_dist - min_dist);
            let pos = (
                self.world.player_pos.0 + (angle.cos() * dist) as i32,
                self.world.player_pos.1 + (angle.sin() * dist) as i32,
            );
            if self.in_bounds(pos) {
                return Some(pos);
            }
        }
        None
    }

    fn reject(&mut self, action: &str, reason: &str) {
        self.append(
            "action_rejected",
            "warn",
            format!(
                "ActionRejected({},{},step={})",
                action, reason, self.private.step_index
            ),
            Some(action.to_string()),
            None,
            json!({"reason": reason}),
        );
        if reason != "terminal" {
            self.append(
                "rule_violation",
                "warn",
                format!("RuleViolation({})", reason),
                Some(action.to_string()),
                None,
                json!({"reason": reason}),
            );
        }
        let env_components = self.rejection_reward_components(reason);
        let monty_reward = self.monty_rejection_reward(reason);
        self.apply_reward_deltas(&env_components, monty_reward);
        self.append_reward_delta_events(action, &env_components, monty_reward);
    }

    fn reject_unknown_action(&mut self, action: &str) {
        if self.terminated || self.truncated {
            self.reject(action, "terminal");
            return;
        }
        let before_step = self.world.step;
        self.update_daylight_for_step(before_step + 1);
        self.world.step += 1;
        let done_reason = self.done_reason_now();
        self.private.step_index = self.world.step;
        self.private.terminated = done_reason.as_deref() == Some("death");
        self.private.truncated = done_reason.as_deref() == Some("max_steps");
        self.private.done_reason = done_reason.clone();
        self.terminated = self.private.terminated;
        self.truncated = self.private.truncated;
        self.done_reason = done_reason.clone();

        self.reject(action, "unknown_action");
        self.append(
            "state_transition",
            "info",
            format!("StateTransition(step={}->{})", before_step, self.world.step),
            Some(action.to_string()),
            Some(json!({"step": {"from": before_step, "to": self.world.step}})),
            json!({"reason": "unknown_action"}),
        );
        if let Some(reason) = done_reason {
            let terminal_kind = if reason == "death" {
                "death"
            } else {
                "episode_truncated"
            };
            let terminal_payload = termination_payload(&self.done_reason, &self.world.last_damage_source);
            self.append(
                terminal_kind,
                "info",
                format!("{}({})", title_event(terminal_kind), reason),
                Some(action.to_string()),
                None,
                terminal_payload.clone(),
            );
            self.append(
                "terminal",
                "info",
                format!(
                    "Terminal({})",
                    self.done_reason.as_deref().unwrap_or("done")
                ),
                Some(action.to_string()),
                None,
                terminal_payload,
            );
        }
        self.append_checkpoint_cadence_event();
    }

    fn append(
        &mut self,
        kind: &str,
        severity: &str,
        message: String,
        action: Option<String>,
        transition: Option<Value>,
        payload: Value,
    ) {
        self.events.push(EventRecord {
            step_index: self.private.step_index,
            sim_tick: self.private.step_index,
            episode_id: self.episode_id.clone(),
            kind: kind.to_string(),
            severity: severity.to_string(),
            message,
            action,
            transition,
            payload,
        });
    }

    fn current_observation(&self) -> Value {
        let inventory = project_inventory_for_resolved(&self.world.inventory, &self.resolved_json);
        let achievements =
            project_achievements_for_resolved(&self.world.achievements, &self.resolved_json);
        json!({
            "step": self.world.step,
            "episode": self.world.episode,
            "world": self.symbolic_world(),
            "player": self.player_observation(&inventory),
            "achievements": achievements,
            "stats": {
                "score": achievements.values().filter(|count| **count > 0).count(),
                "daylight": self.world.daylight
            },
            "view": self.symbolic_view()
        })
    }

    fn player_observation(&self, inventory: &BTreeMap<String, i64>) -> Value {
        json!({
            "pos": [self.world.player_pos.0, self.world.player_pos.1],
            "facing": [self.world.player_facing.0, self.world.player_facing.1],
            "sleeping": self.world.player_sleeping,
            "health": inventory.get("health").copied().unwrap_or(0),
            "food": inventory.get("food").copied().unwrap_or(0),
            "drink": inventory.get("drink").copied().unwrap_or(0),
            "energy": inventory.get("energy").copied().unwrap_or(0),
            "inventory": inventory
        })
    }

    fn symbolic_world(&self) -> Value {
        if !self
            .resolved_json
            .get("readouts")
            .and_then(|value| value.get("full_world_state"))
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            return json!({"width": self.world.width, "height": self.world.height, "tiles": [], "entities": []});
        }
        let mut tiles = vec![];
        for y in 0..self.world.height {
            for x in 0..self.world.width {
                tiles.push(
                    json!({"pos": [x, y], "kind": self.world.tiles[y][x], "in_bounds": true}),
                );
            }
        }
        json!({
            "width": self.world.width,
            "height": self.world.height,
            "tiles": tiles,
            "entities": self.world.entities.iter().map(Entity::to_json).collect::<Vec<_>>()
        })
    }

    fn symbolic_view(&self) -> Value {
        let radius = self.world.view_radius;
        let (px, py) = self.world.player_pos;
        let mut tiles = vec![];
        for y in (py - radius)..=(py + radius) {
            for x in (px - radius)..=(px + radius) {
                let in_bounds = self.in_bounds((x, y));
                let kind = if in_bounds {
                    self.tile((x, y))
                } else {
                    "water".to_string()
                };
                tiles.push(json!({"pos": [x, y], "kind": kind, "in_bounds": in_bounds}));
            }
        }
        let entities = self
            .world
            .entities
            .iter()
            .filter(|entity| {
                (entity.pos.0 - px).abs() <= radius && (entity.pos.1 - py).abs() <= radius
            })
            .map(Entity::to_json)
            .collect::<Vec<_>>();
        json!({"center": [px, py], "radius": radius, "tiles": tiles, "entities": entities})
    }

    fn append_inventory_deltas(
        &mut self,
        action: &str,
        before: &BTreeMap<String, i64>,
        after: &BTreeMap<String, i64>,
    ) {
        let keys = before
            .keys()
            .chain(after.keys())
            .cloned()
            .collect::<BTreeSet<_>>();
        for key in keys {
            if matches!(key.as_str(), "health" | "food" | "drink" | "energy") {
                continue;
            }
            let before_value = before.get(&key).copied().unwrap_or(0);
            let after_value = after.get(&key).copied().unwrap_or(0);
            if before_value == after_value {
                continue;
            }
            self.append(
                "resource_delta",
                "info",
                format!("ResourceDelta({},{}->{})", key, before_value, after_value),
                Some(action.to_string()),
                None,
                json!({"resource": key, "before": before_value, "after": after_value, "delta": after_value - before_value}),
            );
        }
    }

    fn append_checkpoint_cadence_event(&mut self) {
        let interval = self
            .resolved_json
            .get("checkpoint_every_n_steps")
            .and_then(Value::as_u64)
            .unwrap_or(10);
        let step = self.world.step;
        if interval == 0 || step == 0 || !step.is_multiple_of(interval) {
            return;
        }
        let cursor_before = self.event_cursor();
        self.append(
            "checkpoint",
            "info",
            format!("Checkpoint(step={},interval={})", step, interval),
            None,
            None,
            json!({
                "source": "cadence",
                "step_index": step,
                "interval": interval,
                "nev_cursor_before": cursor_before
            }),
        );
    }

    fn env_reward_components(
        &self,
        newly_unlocked: &[String],
        done_reason: Option<&str>,
    ) -> Vec<RewardComponent> {
        let rewards = self.rule_reward_config();
        let mut components = vec![];
        let achievement_delta = rewards["achievement"] * newly_unlocked.len() as f32;
        if achievement_delta != 0.0 {
            components.push(RewardComponent {
                source: "achievement",
                component: "achievement",
                delta: achievement_delta,
                count: Some(newly_unlocked.len()),
                achievements: newly_unlocked.to_vec(),
            });
        }
        if rewards["step"] != 0.0 {
            components.push(RewardComponent {
                source: "env",
                component: "step",
                delta: rewards["step"],
                count: None,
                achievements: vec![],
            });
        }
        if done_reason == Some("death") && rewards["death"] != 0.0 {
            components.push(RewardComponent {
                source: "env",
                component: "death",
                delta: rewards["death"],
                count: None,
                achievements: vec![],
            });
        }
        components
    }

    fn rejection_reward_components(&self, reason: &str) -> Vec<RewardComponent> {
        let rewards = self.rule_reward_config();
        let mut components = vec![];
        if reason == "unknown_action" {
            if rewards["step"] != 0.0 {
                components.push(RewardComponent {
                    source: "env",
                    component: "step",
                    delta: rewards["step"],
                    count: None,
                    achievements: vec![],
                });
            }
            if rewards["invalid_action"] != 0.0 {
                components.push(RewardComponent {
                    source: "env",
                    component: "invalid_action",
                    delta: rewards["invalid_action"],
                    count: None,
                    achievements: vec![],
                });
            }
        }
        components
    }

    fn rule_reward_config(&self) -> BTreeMap<&'static str, f32> {
        let rewards = self
            .resolved_json
            .get("rules")
            .and_then(|rules| rules.get("rewards"))
            .and_then(Value::as_object);
        let mut result = BTreeMap::new();
        for (key, default) in [
            ("achievement", 1.0),
            ("invalid_action", 0.0),
            ("death", 0.0),
            ("step", 0.0),
        ] {
            result.insert(
                key,
                rewards
                    .and_then(|items| items.get(key))
                    .and_then(Value::as_f64)
                    .unwrap_or(default) as f32,
            );
        }
        result
    }

    fn apply_reward_deltas(&mut self, env_components: &[RewardComponent], monty_delta: f32) {
        let env_delta = reward_component_total(env_components);
        self.reward_last = env_delta + monty_delta;
        self.total_reward += self.reward_last;
        self.private.reward_last = self.reward_last;
        self.private.total_reward = self.total_reward;

        let mut breakdown = self.reward_breakdown.clone();
        breakdown["last_env"] = json!(env_delta);
        breakdown["last_monty"] = json!(monty_delta);
        breakdown["last_env_components"] = reward_components_json(env_components);
        breakdown["rule_rewards"] = json!(self.rule_reward_config());
        let env_total = breakdown
            .get("env_total")
            .and_then(Value::as_f64)
            .unwrap_or(0.0)
            + env_delta as f64;
        let monty_total = breakdown
            .get("monty_total")
            .and_then(Value::as_f64)
            .unwrap_or(0.0)
            + monty_delta as f64;
        let mut penalty_total = breakdown
            .get("penalty_total")
            .and_then(Value::as_f64)
            .unwrap_or(0.0);
        for component in env_components {
            if component.delta < 0.0 {
                penalty_total += component.delta as f64;
            }
        }
        if monty_delta < 0.0 {
            penalty_total += monty_delta as f64;
        }
        breakdown["env_total"] = json!(env_total);
        breakdown["monty_total"] = json!(monty_total);
        breakdown["penalty_total"] = json!(penalty_total);
        breakdown["achievement_count"] = json!(self
            .world
            .achievements
            .values()
            .filter(|count| **count > 0)
            .count());
        self.reward_breakdown = breakdown.clone();
        self.private.reward_breakdown = breakdown;
    }

    fn append_reward_delta_events(
        &mut self,
        action: &str,
        env_components: &[RewardComponent],
        monty_delta: f32,
    ) {
        let env_delta = reward_component_total(env_components);
        let mut running_total = self.total_reward - env_delta - monty_delta;
        for component in env_components {
            if component.delta == 0.0 {
                continue;
            }
            running_total += component.delta;
            let mut payload = json!({
                "delta": component.delta,
                "total": running_total,
                "source": component.source,
                "component": component.component
            });
            if let Some(count) = component.count {
                payload["count"] = json!(count);
            }
            if !component.achievements.is_empty() {
                payload["achievements"] = json!(component.achievements);
            }
            let message =
                if component.source == "achievement" && component.component == "achievement" {
                    format!(
                        "RewardDelta({:.2},total={:.2})",
                        component.delta, running_total
                    )
                } else {
                    format!(
                        "RewardDelta({:.2},total={:.2},source={},component={})",
                        component.delta, running_total, component.source, component.component
                    )
                };
            self.append(
                "reward_delta",
                "info",
                message,
                Some(action.to_string()),
                None,
                payload,
            );
        }
        if monty_delta != 0.0 {
            running_total += monty_delta;
            self.append(
                "reward_delta",
                "info",
                format!(
                    "RewardDelta({:.2},total={:.2},source=monty)",
                    monty_delta, running_total
                ),
                Some(action.to_string()),
                None,
                json!({"delta": monty_delta, "total": running_total, "source": "monty"}),
            );
        }
    }

    fn monty_transition_reward(
        &self,
        before_inventory: &BTreeMap<String, i64>,
        after_inventory: &BTreeMap<String, i64>,
        newly_unlocked: &[String],
    ) -> f32 {
        let Some(config) = monty_config(self.resolved_json.get("monty_reward")) else {
            return 0.0;
        };
        let achievement_default = config
            .get("achievement_default")
            .and_then(Value::as_f64)
            .unwrap_or(0.0) as f32;
        let mut total = 0.0;
        for achievement in newly_unlocked {
            total += monty_section_weight(&config, "achievement_rewards", achievement)
                .unwrap_or(achievement_default);
        }
        if let Some(resource_rewards) = config.get("resource_rewards").and_then(Value::as_object) {
            for (name, weight) in resource_rewards {
                let delta = after_inventory.get(name).copied().unwrap_or(0)
                    - before_inventory.get(name).copied().unwrap_or(0);
                if delta > 0 {
                    total += weight.as_f64().unwrap_or(0.0) as f32 * delta as f32;
                }
            }
        }
        total
    }

    fn monty_rejection_reward(&self, reason: &str) -> f32 {
        let Some(config) = monty_config(self.resolved_json.get("monty_reward")) else {
            return 0.0;
        };
        monty_section_weight(&config, "action_penalties", reason).unwrap_or(0.0)
    }

    fn done_reason_now(&self) -> Option<String> {
        if self.substrate_bool("health_enabled", true) && self.inventory_amount("health") <= 0 {
            Some("death".to_string())
        } else if self.world.step >= self.world.max_steps {
            Some("max_steps".to_string())
        } else {
            None
        }
    }

    fn front_pos(&self) -> (i32, i32) {
        (
            self.world.player_pos.0 + self.world.player_facing.0,
            self.world.player_pos.1 + self.world.player_facing.1,
        )
    }

    fn in_bounds(&self, pos: (i32, i32)) -> bool {
        pos.0 >= 0
            && pos.1 >= 0
            && (pos.0 as usize) < self.world.width
            && (pos.1 as usize) < self.world.height
    }

    fn tile(&self, pos: (i32, i32)) -> String {
        if !self.in_bounds(pos) {
            return "water".to_string();
        }
        self.world.tiles[pos.1 as usize][pos.0 as usize].clone()
    }

    fn set_tile(&mut self, pos: (i32, i32), value: &str) {
        if self.in_bounds(pos) {
            self.world.tiles[pos.1 as usize][pos.0 as usize] = value.to_string();
        }
    }

    fn entity_index_at(&self, pos: (i32, i32)) -> Option<usize> {
        self.world
            .entities
            .iter()
            .position(|entity| entity.pos == pos)
    }

    fn inventory_counter(&self, key: &str) -> i64 {
        self.world
            .inventory
            .get(canonical_inventory_key(key))
            .copied()
            .unwrap_or(0)
    }

    fn inventory_amount(&self, key: &str) -> i32 {
        counter_as_i32(self.inventory_counter(key))
    }

    fn add_inventory(&mut self, key: &str, amount: i32) {
        let canonical = canonical_inventory_key(key);
        let current = self.inventory_counter(canonical);
        self.world.inventory.insert(
            canonical.to_string(),
            clamp_inventory(canonical, current.saturating_add(i64::from(amount))),
        );
    }

    fn use_inventory(&mut self, key: &str, amount: i32) -> bool {
        let canonical = canonical_inventory_key(key);
        let amount = i64::from(amount);
        if self.inventory_counter(canonical) < amount {
            return false;
        }
        let current = self.inventory_counter(canonical);
        self.world
            .inventory
            .insert(canonical.to_string(), current - amount);
        true
    }

    fn set_armor_pieces(&mut self, tier: i32) {
        for key in ARMOR_SLOTS {
            let current = self.inventory_counter(key);
            self.world.inventory.insert(
                key.to_string(),
                clamp_inventory(key, current.max(i64::from(tier))),
            );
        }
    }

    fn armor_protection(&self) -> i32 {
        ARMOR_SLOTS
            .iter()
            .map(|key| self.inventory_amount(key))
            .min()
            .unwrap_or(0)
            .max(0)
    }

    fn add_achievement(&mut self, key: &str, amount: i64) {
        let canonical = canonical_achievement_key(key);
        if is_craftax_achievement(canonical) && !self.craftax_achievements_enabled() {
            return;
        }
        if self.world.achievements.contains_key(canonical) {
            let current = self.world.achievements.get(canonical).copied().unwrap_or(0);
            self.world
                .achievements
                .insert(canonical.to_string(), current.saturating_add(amount));
        }
    }

    fn best_pickaxe_tier(&self) -> i32 {
        if self.inventory_amount("diamond_pickaxe") > 0 {
            4
        } else if self.inventory_amount("iron_pickaxe") > 0 {
            3
        } else if self.inventory_amount("stone_pickaxe") > 0 {
            2
        } else if self.inventory_amount("wood_pickaxe") > 0 {
            1
        } else {
            0
        }
    }

    fn attack_damage(&self) -> i32 {
        let base = if self.inventory_amount("diamond_sword") > 0 {
            9
        } else if self.inventory_amount("iron_sword") > 0 {
            5
        } else if self.inventory_amount("stone_sword") > 0 {
            3
        } else if self.inventory_amount("wood_sword") > 0 {
            2
        } else {
            1
        };
        (base as f64 * self.substrate_f64("player_damage_mult", 1.0)).max(0.0) as i32
    }

    fn has_adjacent(&self, material: &str) -> bool {
        let (x, y) = self.world.player_pos;
        [(1, 0), (-1, 0), (0, 1), (0, -1)]
            .iter()
            .any(|(dx, dy)| self.tile((x + dx, y + dy)) == material)
    }

    fn wake_player(&mut self) {
        if self.world.player_sleeping {
            self.world.player_sleeping = false;
            self.add_achievement("wake_up", 1);
        }
    }

    fn apply_player_damage(&mut self, source: &str, amount: i32) {
        self.world.last_damage_source = Some(source.to_string());
        if !self.substrate_bool("health_enabled", true) {
            self.world
                .inventory
                .insert("health".to_string(), i64::from(MAX_INVENTORY_VALUE));
            self.world.last_health = MAX_INVENTORY_VALUE;
            self.world.last_damage_source = None;
            return;
        }
        let mut damage = amount.max(0);
        if damage > 0 && source != "lava" {
            damage = (damage - self.armor_protection()).max(0);
        }
        self.add_inventory("health", -damage);
    }

    fn adapter_hook(&self, key: &str) -> bool {
        self.resolved_json
            .get("adapter_hooks")
            .and_then(|hooks| hooks.get(key))
            .and_then(Value::as_bool)
            .unwrap_or(false)
    }

    fn substrate_bool(&self, key: &str, default: bool) -> bool {
        self.resolved_json
            .get("substrate_config")
            .and_then(|config| config.get(key))
            .and_then(Value::as_bool)
            .unwrap_or(default)
    }

    fn substrate_u64(&self, key: &str, default: u64) -> u64 {
        self.resolved_json
            .get("substrate_config")
            .and_then(|config| config.get(key))
            .and_then(Value::as_u64)
            .unwrap_or(default)
    }

    fn substrate_f64(&self, key: &str, default: f64) -> f64 {
        self.resolved_json
            .get("substrate_config")
            .and_then(|config| config.get(key))
            .and_then(Value::as_f64)
            .unwrap_or(default)
    }

    fn survival_f64(&self, key: &str, default: f64) -> f64 {
        self.resolved_json
            .get("substrate_config")
            .and_then(|config| config.get(key))
            .and_then(Value::as_f64)
            .or_else(|| {
                self.resolved_json
                    .get("rules")
                    .and_then(|rules| rules.get("survival"))
                    .and_then(|survival| survival.get(key))
                    .and_then(Value::as_f64)
            })
            .unwrap_or(default)
            .max(1.0)
    }

    fn mob_f64(&self, key: &str, default: f64) -> f64 {
        self.resolved_json
            .get("substrate_config")
            .and_then(|config| config.get(key))
            .and_then(Value::as_f64)
            .or_else(|| {
                self.resolved_json
                    .get("rules")
                    .and_then(|rules| rules.get("mobs"))
                    .and_then(|mobs| mobs.get(key))
                    .and_then(Value::as_f64)
            })
            .unwrap_or(default)
            .max(0.0)
    }

    fn random_direction(&mut self) -> (i32, i32) {
        match self.world.rng.next_u32() % 4 {
            0 => (0, 1),
            1 => (0, -1),
            2 => (1, 0),
            _ => (-1, 0),
        }
    }

    fn toward_direction(&self, from: (i32, i32), to: (i32, i32), long_axis: bool) -> (i32, i32) {
        let dx = to.0 - from.0;
        let dy = to.1 - from.1;
        let choose_x = if long_axis {
            dx.abs() > dy.abs()
        } else {
            dx.abs() <= dy.abs()
        };
        if choose_x {
            (dx.signum(), 0)
        } else {
            (0, dy.signum())
        }
    }

    fn is_empty_walkable(&self, pos: (i32, i32)) -> bool {
        self.in_bounds(pos)
            && WALKABLE.contains(&self.tile(pos).as_str())
            && self.entity_index_at(pos).is_none()
            && pos != self.world.player_pos
    }

    fn entity_i32(&self, idx: usize, key: &str, default: i32) -> i32 {
        self.world
            .entities
            .get(idx)
            .and_then(|entity| entity.metadata.get(key))
            .and_then(Value::as_i64)
            .unwrap_or(default as i64) as i32
    }

    fn set_entity_i32(&mut self, idx: usize, key: &str, value: i32) {
        if let Some(entity) = self.world.entities.get_mut(idx) {
            entity.metadata.insert(key.to_string(), json!(value));
        }
    }

    fn entity_index_by_id(&self, id: &str) -> Option<usize> {
        self.world
            .entities
            .iter()
            .position(|entity| entity.id == id)
    }

    fn remove_entity_by_id(&mut self, id: &str) {
        if let Some(idx) = self.entity_index_by_id(id) {
            self.world.entities.remove(idx);
        }
    }

    fn next_entity_id(&mut self) -> String {
        let id = self.world.next_entity_id;
        self.world.next_entity_id += 1;
        format!("world_{}", id)
    }

    fn spawn_entity(&mut self, kind: &str, pos: (i32, i32), health: i32) {
        if !self.is_empty_walkable(pos) {
            return;
        }
        let mut metadata = BTreeMap::new();
        metadata.insert("source".to_string(), json!("runtime"));
        let id = self.next_entity_id();
        self.world.entities.push(Entity {
            id,
            kind: kind.to_string(),
            pos,
            health,
            metadata,
        });
    }
}

fn decode_checkpoint_events(payload: &Value, key: &str) -> Option<Vec<EventRecord>> {
    let raw = payload.get(key)?;
    let events = raw
        .as_array()
        .unwrap_or_else(|| panic!("native Crafter checkpoint {} must be an array", key));
    Some(
        events
            .iter()
            .enumerate()
            .map(|(idx, event)| {
                serde_json::from_value(event.clone()).unwrap_or_else(|err| {
                    panic!(
                        "native Crafter checkpoint {}[{}] must be an event record: {}",
                        key, idx, err
                    )
                })
            })
            .collect(),
    )
}

fn checkpoint_usize_field(payload: &Value, key: &str) -> Option<usize> {
    let value = payload.get(key)?;
    let raw = value.as_u64().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} must be a nonnegative integer",
            key
        )
    });
    if raw > usize::MAX as u64 {
        panic!(
            "native Crafter checkpoint {} must fit in platform usize",
            key
        );
    }
    Some(raw as usize)
}

fn checkpoint_string_field<'a>(payload: &'a Value, key: &str) -> Option<&'a str> {
    let value = payload.get(key)?;
    Some(
        value
            .as_str()
            .unwrap_or_else(|| panic!("native Crafter checkpoint {} must be a string", key)),
    )
}

fn checkpoint_required_string_field<'a>(payload: &'a Value, key: &str) -> &'a str {
    checkpoint_string_field(payload, key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing {}", key))
}

fn checkpoint_required_object_field<'a>(payload: &'a Value, key: &str) -> &'a Value {
    let value = payload
        .get(key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing {}", key));
    if !value.is_object() {
        panic!("native Crafter checkpoint {} must be an object", key);
    }
    value
}

fn checkpoint_required_object_value_field(payload: &Value, key: &str) -> Value {
    checkpoint_required_object_field(payload, key).clone()
}

fn validate_resolved_config_hash(resolved: &Value, checkpoint_config_hash: &str) {
    let resolved_config_hash = resolved
        .get("config_hash")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("native Crafter checkpoint resolved config_hash missing"));
    if resolved_config_hash != checkpoint_config_hash {
        panic!(
            "native Crafter checkpoint config_hash {} does not match resolved config_hash {}",
            checkpoint_config_hash, resolved_config_hash
        );
    }
    let inner_resolved = resolved
        .get("resolved_json")
        .unwrap_or_else(|| panic!("native Crafter checkpoint resolved_json missing"));
    if !inner_resolved.is_object() {
        panic!("native Crafter checkpoint resolved_json must be an object");
    }
    let inner_config_hash = inner_resolved
        .get("config_hash")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("native Crafter checkpoint resolved_json config_hash missing"));
    if inner_config_hash != checkpoint_config_hash {
        panic!(
            "native Crafter checkpoint config_hash {} does not match resolved_json config_hash {}",
            checkpoint_config_hash, inner_config_hash
        );
    }
    let mut resolved_without_hash = inner_resolved.clone();
    let resolved_object = resolved_without_hash
        .as_object_mut()
        .unwrap_or_else(|| panic!("native Crafter checkpoint resolved_json must be an object"));
    resolved_object.remove("config_hash");
    let recomputed = format!(
        "sha256:{:x}",
        Sha256::digest(canonical_json(&resolved_without_hash))
    );
    if recomputed != resolved_config_hash {
        panic!(
            "native Crafter checkpoint resolved config_hash digest mismatch: expected {}, recomputed {}",
            resolved_config_hash, recomputed
        );
    }
    validate_resolved_projection(resolved, inner_resolved);
}

fn validate_resolved_projection(resolved: &Value, inner_resolved: &Value) {
    for key in [
        "task_id",
        "scenario_id",
        "seed",
        "reward_mode",
        "objective",
        "world",
        "rules",
        "readouts",
        "stream",
        "monty_reward",
        "checkpoint_every_n_steps",
    ] {
        validate_resolved_projection_field(resolved, key, inner_resolved, key);
    }
    validate_resolved_projection_field(
        resolved,
        "substrate_profile",
        &inner_resolved["substrate"],
        "profile",
    );
    validate_resolved_projection_field(
        resolved,
        "substrate_config",
        &inner_resolved["substrate"],
        "config",
    );
    validate_resolved_projection_field(
        resolved,
        "adapter_hooks",
        &inner_resolved["substrate"],
        "adapter_hooks",
    );
    validate_resolved_projection_field(
        resolved,
        "unsupported_rules",
        &inner_resolved["substrate"],
        "unsupported_rules",
    );
    validate_resolved_projection_field(
        resolved,
        "width",
        &inner_resolved["substrate"]["config"],
        "world_width",
    );
    validate_resolved_projection_field(
        resolved,
        "height",
        &inner_resolved["substrate"]["config"],
        "world_height",
    );
    validate_resolved_projection_field(
        resolved,
        "view_radius",
        &inner_resolved["substrate"]["config"],
        "view_radius",
    );
    validate_resolved_projection_field(
        resolved,
        "max_steps",
        &inner_resolved["substrate"]["config"],
        "max_steps",
    );
}

fn validate_resolved_projection_field(
    left: &Value,
    left_key: &str,
    right: &Value,
    right_key: &str,
) {
    let left_value = left.get(left_key).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint resolved projection missing {}",
            left_key
        )
    });
    let right_value = right.get(right_key).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint resolved projection missing {}",
            right_key
        )
    });
    if left_value != right_value {
        panic!(
            "native Crafter checkpoint resolved projection {} does not match {}",
            left_key, right_key
        );
    }
}

trait CheckpointPrivateFields {
    fn string_field(&self, key: &str) -> Option<&str>;
    fn optional_string_field(&self, key: &str) -> Option<&str>;
    fn u64_field(&self, key: &str) -> Option<u64>;
    fn f32_field(&self, key: &str) -> Option<f32>;
    fn bool_field(&self, key: &str) -> Option<bool>;
    fn object_value_field(&self, key: &str) -> Option<Value>;
}

impl CheckpointPrivateFields for Value {
    fn string_field(&self, key: &str) -> Option<&str> {
        let value = self.get(key)?;
        Some(value.as_str().unwrap_or_else(|| {
            panic!("native Crafter checkpoint private.{} must be a string", key)
        }))
    }

    fn optional_string_field(&self, key: &str) -> Option<&str> {
        let value = self.get(key)?;
        if value.is_null() {
            return None;
        }
        Some(value.as_str().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint private.{} must be a string or null",
                key
            )
        }))
    }

    fn u64_field(&self, key: &str) -> Option<u64> {
        let value = self.get(key)?;
        Some(value.as_u64().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint private.{} must be a nonnegative integer",
                key
            )
        }))
    }

    fn f32_field(&self, key: &str) -> Option<f32> {
        let value = self.get(key)?;
        let raw = value.as_f64().unwrap_or_else(|| {
            panic!("native Crafter checkpoint private.{} must be a number", key)
        });
        let narrowed = raw as f32;
        if !narrowed.is_finite() {
            panic!("native Crafter checkpoint private.{} must be finite", key);
        }
        Some(narrowed)
    }

    fn bool_field(&self, key: &str) -> Option<bool> {
        let value = self.get(key)?;
        Some(value.as_bool().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint private.{} must be a boolean",
                key
            )
        }))
    }

    fn object_value_field(&self, key: &str) -> Option<Value> {
        let value = self.get(key)?;
        if !value.is_object() {
            panic!(
                "native Crafter checkpoint private.{} must be an object",
                key
            );
        }
        Some(value.clone())
    }
}

fn private_required_string_field<'a>(private: &'a Value, key: &str) -> &'a str {
    private
        .string_field(key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing private.{}", key))
}

fn private_required_optional_string_field(private: &Value, key: &str) -> Option<String> {
    if private.get(key).is_none() {
        panic!("native Crafter checkpoint missing private.{}", key);
    }
    private.optional_string_field(key).map(str::to_string)
}

fn private_required_u64_field(private: &Value, key: &str) -> u64 {
    private
        .u64_field(key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing private.{}", key))
}

fn private_required_f32_field(private: &Value, key: &str) -> f32 {
    private
        .f32_field(key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing private.{}", key))
}

fn private_required_bool_field(private: &Value, key: &str) -> bool {
    private
        .bool_field(key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing private.{}", key))
}

fn private_required_object_value_field(private: &Value, key: &str) -> Value {
    private
        .object_value_field(key)
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing private.{}", key))
}

fn private_achievement_set(private: &Value) -> BTreeSet<String> {
    let value = private
        .get("achievements")
        .unwrap_or_else(|| panic!("native Crafter checkpoint missing private.achievements"));
    let achievements = value.as_array().unwrap_or_else(|| {
        panic!("native Crafter checkpoint private.achievements must be an array")
    });
    achievements
        .iter()
        .enumerate()
        .map(|(idx, item)| {
            item.as_str()
                .unwrap_or_else(|| {
                    panic!(
                        "native Crafter checkpoint private.achievements[{}] must be a string",
                        idx
                    )
                })
                .to_string()
        })
        .collect()
}

fn validate_restored_reward_breakdown_state(
    breakdown: &Value,
    resolved: &Value,
    world: &NativeWorld,
) {
    let object = breakdown
        .as_object()
        .unwrap_or_else(|| panic!("native Crafter checkpoint reward_breakdown must be an object"));
    if object.get("schema").and_then(Value::as_str) != Some("gamebench.crafter.reward_breakdown.v1")
    {
        panic!("native Crafter checkpoint reward_breakdown schema is unsupported");
    }
    for key in [
        "env_total",
        "monty_total",
        "penalty_total",
        "last_env",
        "last_monty",
    ] {
        reward_breakdown_required_finite_number(object, key);
    }
    let achievement_count = object
        .get("achievement_count")
        .and_then(Value::as_u64)
        .unwrap_or_else(|| {
            panic!("native Crafter checkpoint reward_breakdown achievement_count must be a nonnegative integer")
        });
    let expected_achievement_count = world
        .achievements
        .values()
        .filter(|count| **count > 0)
        .count() as u64;
    if achievement_count != expected_achievement_count {
        panic!(
            "native Crafter checkpoint reward_breakdown achievement_count {} does not match restored achievements {}",
            achievement_count, expected_achievement_count
        );
    }
    let expected_rule_rewards = resolved
        .get("rules")
        .and_then(|rules| rules.get("rewards"))
        .unwrap_or_else(|| panic!("native Crafter checkpoint resolved rules.rewards missing"));
    if object.get("rule_rewards") != Some(expected_rule_rewards) {
        panic!(
            "native Crafter checkpoint reward_breakdown rule_rewards do not match resolved rules"
        );
    }
    let expected_monty = resolved.get("monty_reward").unwrap_or(&Value::Null);
    if object.get("monty") != Some(expected_monty) {
        panic!(
            "native Crafter checkpoint reward_breakdown monty does not match resolved monty_reward"
        );
    }
    let components = object
        .get("last_env_components")
        .and_then(Value::as_array)
        .unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint reward_breakdown last_env_components must be an array"
            )
        });
    for (idx, component) in components.iter().enumerate() {
        let component = component.as_object().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint reward_breakdown last_env_components[{}] must be an object",
                idx
            )
        });
        for key in ["source", "component"] {
            if component.get(key).and_then(Value::as_str).is_none() {
                panic!(
                    "native Crafter checkpoint reward_breakdown last_env_components[{}].{} must be a string",
                    idx, key
                );
            }
        }
        reward_breakdown_required_finite_number(component, "delta");
        if let Some(count) = component.get("count") {
            if count.as_u64().is_none() {
                panic!(
                    "native Crafter checkpoint reward_breakdown last_env_components[{}].count must be a nonnegative integer",
                    idx
                );
            }
        }
        if let Some(achievements) = component.get("achievements") {
            let achievements = achievements.as_array().unwrap_or_else(|| {
                panic!(
                    "native Crafter checkpoint reward_breakdown last_env_components[{}].achievements must be an array",
                    idx
                )
            });
            for (achievement_idx, achievement) in achievements.iter().enumerate() {
                let Some(name) = achievement.as_str() else {
                    panic!(
                        "native Crafter checkpoint reward_breakdown last_env_components[{}].achievements[{}] must be a string",
                        idx, achievement_idx
                    );
                };
                if !is_achievement_slot(name) {
                    panic!(
                        "native Crafter checkpoint reward_breakdown last_env_components[{}].achievements[{}] is unsupported: {}",
                        idx, achievement_idx, name
                    );
                }
            }
        }
    }
}

fn reward_breakdown_required_finite_number(object: &Map<String, Value>, key: &str) -> f64 {
    let value = object.get(key).and_then(Value::as_f64).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint reward_breakdown {} must be a number",
            key
        )
    });
    if !value.is_finite() {
        panic!(
            "native Crafter checkpoint reward_breakdown {} must be finite",
            key
        );
    }
    value
}

fn validate_restored_event_records(
    events: &[EventRecord],
    episode_id: &str,
    world_step: u64,
    resolved: &Value,
) {
    for (idx, event) in events.iter().enumerate() {
        if event.episode_id != episode_id {
            panic!(
                "native Crafter checkpoint event {} episode_id {} does not match restored episode_id {}",
                idx, event.episode_id, episode_id
            );
        }
        if event.sim_tick != event.step_index {
            panic!(
                "native Crafter checkpoint event {} sim_tick {} does not match step_index {}",
                idx, event.sim_tick, event.step_index
            );
        }
        if event.step_index > world_step {
            panic!(
                "native Crafter checkpoint event {} step_index {} exceeds restored world step {}",
                idx, event.step_index, world_step
            );
        }
        validate_restored_event_record_shape(idx, event, resolved);
    }
}

fn validate_restored_reward_history(
    events: &[EventRecord],
    cursor_offset: usize,
    world_step: u64,
    reward_last: f32,
    total_reward: f32,
) {
    let full_history = cursor_offset == 0;
    let mut last_total: Option<f64> = None;
    let mut current_step_delta = 0.0_f64;
    let mut current_step_reward_events = 0_u64;
    for (idx, event) in events.iter().enumerate() {
        if event.kind != "reward_delta" {
            continue;
        }
        let payload = event.payload.as_object().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload must be an object",
                idx
            )
        });
        let delta = reward_delta_event_number(payload, idx, "delta");
        let total = reward_delta_event_number(payload, idx, "total");
        if let Some(previous_total) = last_total {
            let expected_total = previous_total + delta;
            if !reward_values_close(total, expected_total) {
                panic!(
                    "native Crafter checkpoint reward_delta event {} total {} does not follow prior total {} plus delta {}",
                    idx, total, previous_total, delta
                );
            }
        } else if full_history && !reward_values_close(total, delta) {
            panic!(
                "native Crafter checkpoint reward_delta event {} total {} does not follow prior total 0 plus delta {}",
                idx, total, delta
            );
        }
        last_total = Some(total);
        if event.step_index == world_step {
            current_step_delta += delta;
            current_step_reward_events += 1;
            if current_step_reward_events > 2 {
                panic!(
                    "native Crafter checkpoint has more than two reward_delta events at restored step {}",
                    world_step
                );
            }
        }
    }
    if full_history {
        let restored_history_total = last_total.unwrap_or(0.0);
        if !reward_values_close(f64::from(total_reward), restored_history_total) {
            panic!(
                "native Crafter checkpoint total_reward {} does not match restored reward history {}",
                total_reward, restored_history_total
            );
        }
        let expected_reward_last = if current_step_reward_events == 0 {
            0.0
        } else {
            current_step_delta
        };
        if !reward_values_close(f64::from(reward_last), expected_reward_last) {
            panic!(
                "native Crafter checkpoint reward_last {} does not match restored current-step reward {}",
                reward_last, expected_reward_last
            );
        }
    } else if let Some(restored_tail_total) = last_total {
        if !reward_values_close(f64::from(total_reward), restored_tail_total) {
            panic!(
                "native Crafter checkpoint total_reward {} does not match restored reward tail total {}",
                total_reward, restored_tail_total
            );
        }
        if current_step_reward_events > 0
            && !reward_values_close(f64::from(reward_last), current_step_delta)
        {
            panic!(
                "native Crafter checkpoint reward_last {} does not match restored tail current-step reward {}",
                reward_last, current_step_delta
            );
        }
    }
}

fn validate_restored_event_record_shape(idx: usize, event: &EventRecord, resolved: &Value) {
    if !is_nev_event_kind(&event.kind) {
        panic!(
            "native Crafter checkpoint event {} kind is unsupported: {}",
            idx, event.kind
        );
    }
    if !matches!(event.severity.as_str(), "info" | "warn") {
        panic!(
            "native Crafter checkpoint event {} severity is unsupported: {}",
            idx, event.severity
        );
    }
    if event.message.is_empty() {
        panic!(
            "native Crafter checkpoint event {} message must be nonempty",
            idx
        );
    }
    if !event.payload.is_object() {
        panic!(
            "native Crafter checkpoint event {} payload must be an object",
            idx
        );
    }
    if let Some(action) = &event.action {
        if action.is_empty() || action.len() > 128 {
            panic!(
                "native Crafter checkpoint event {} action must be nonempty and at most 128 bytes",
                idx
            );
        }
    }
    if let Some(transition) = &event.transition {
        if !transition.is_object() {
            panic!(
                "native Crafter checkpoint event {} transition must be an object when present",
                idx
            );
        }
    }
    if event.kind == "reward_delta" {
        validate_restored_reward_delta_event(idx, event);
    } else {
        match event.kind.as_str() {
            "achievement_unlocked" => validate_restored_achievement_event(idx, event, resolved),
            "action_applied" => validate_restored_action_applied_event(idx, event),
            "action_rejected" => validate_restored_rejection_event(idx, event, true),
            "rule_violation" => validate_restored_rejection_event(idx, event, false),
            "resource_delta" => validate_restored_resource_delta_event(idx, event, resolved),
            "death" | "episode_truncated" | "terminal" => {
                validate_restored_terminal_event(idx, event)
            }
            "checkpoint" => validate_restored_checkpoint_event(idx, event),
            "task_resolved" => validate_restored_task_resolved_event(idx, event),
            "state_transition" => validate_restored_state_transition_event(idx, event),
            "entity_transition" => validate_restored_entity_transition_event(idx, event),
            _ => {}
        }
    }
}

fn event_payload_object(idx: usize, event: &EventRecord) -> &Map<String, Value> {
    event.payload.as_object().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint event {} payload must be an object",
            idx
        )
    })
}

fn event_payload_string<'a>(
    payload: &'a Map<String, Value>,
    idx: usize,
    kind: &str,
    key: &str,
) -> &'a str {
    payload.get(key).and_then(Value::as_str).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} payload.{} must be a string",
            kind, idx, key
        )
    })
}

fn event_payload_i64(payload: &Map<String, Value>, idx: usize, kind: &str, key: &str) -> i64 {
    payload.get(key).and_then(Value::as_i64).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} payload.{} must be an integer",
            kind, idx, key
        )
    })
}

fn event_payload_u64(payload: &Map<String, Value>, idx: usize, kind: &str, key: &str) -> u64 {
    payload.get(key).and_then(Value::as_u64).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} payload.{} must be a nonnegative integer",
            kind, idx, key
        )
    })
}

fn validate_restored_task_resolved_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    let resolved = payload.get("resolved").unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint task_resolved event {} payload.resolved is missing",
            idx
        )
    });
    if !resolved.is_object() {
        panic!(
            "native Crafter checkpoint task_resolved event {} payload.resolved must be an object",
            idx
        );
    }
}

fn validate_restored_action_applied_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    let action = event_payload_string(payload, idx, "action_applied", "action");
    if Some(action) != event.action.as_deref() {
        panic!(
            "native Crafter checkpoint action_applied event {} payload.action does not match event action",
            idx
        );
    }
    if !ACTION_NAMES.contains(&action) {
        panic!(
            "native Crafter checkpoint action_applied event {} action is unsupported: {}",
            idx, action
        );
    }
    if payload.get("done").and_then(Value::as_bool).is_none() {
        panic!(
            "native Crafter checkpoint action_applied event {} payload.done must be a boolean",
            idx
        );
    }
    if let Some(reason) = payload.get("done_reason") {
        if !(reason.is_null() || matches!(reason.as_str(), Some("death" | "max_steps" | "done"))) {
            panic!(
                "native Crafter checkpoint action_applied event {} payload.done_reason is unsupported",
                idx
            );
        }
    }
    let transition = event.transition.as_ref().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint action_applied event {} missing transition",
            idx
        )
    });
    let transition = transition.as_object().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint action_applied event {} transition must be an object",
            idx
        )
    });
    validate_from_to_coordinate_pair(
        idx,
        transition.get("player_pos"),
        "action_applied",
        "player_pos",
    );
    validate_from_to_step_pair(
        idx,
        transition.get("step"),
        "action_applied",
        "step",
        event.step_index,
    );
}

fn validate_from_to_coordinate_pair(idx: usize, value: Option<&Value>, kind: &str, field: &str) {
    let value = value.unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} transition.{} is missing",
            kind, idx, field
        )
    });
    let value = value.as_object().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} transition.{} must be an object",
            kind, idx, field
        )
    });
    for key in ["from", "to"] {
        let coord = value.get(key).and_then(Value::as_array).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint {} event {} transition.{}.{} must be an array",
                kind, idx, field, key
            )
        });
        if coord.len() != 2 || coord.iter().any(|value| value.as_i64().is_none()) {
            panic!(
                "native Crafter checkpoint {} event {} transition.{}.{} must be a two-element integer coordinate",
                kind, idx, field, key
            );
        }
    }
}

fn validate_from_to_step_pair(
    idx: usize,
    value: Option<&Value>,
    kind: &str,
    field: &str,
    expected_to: u64,
) {
    let value = value.unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} transition.{} is missing",
            kind, idx, field
        )
    });
    let value = value.as_object().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} transition.{} must be an object",
            kind, idx, field
        )
    });
    let from = value.get("from").and_then(Value::as_u64).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} transition.{}.from must be a nonnegative integer",
            kind, idx, field
        )
    });
    let to = value.get("to").and_then(Value::as_u64).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} transition.{}.to must be a nonnegative integer",
            kind, idx, field
        )
    });
    if to != expected_to {
        panic!(
            "native Crafter checkpoint {} event {} transition.{}.to {} does not match event step_index {}",
            kind, idx, field, to, expected_to
        );
    }
    if from + 1 != to {
        panic!(
            "native Crafter checkpoint {} event {} transition.{}.from {} and to {} must differ by exactly one",
            kind, idx, field, from, to
        );
    }
}

fn validate_restored_achievement_event(idx: usize, event: &EventRecord, resolved: &Value) {
    let payload = event_payload_object(idx, event);
    let achievement = event_payload_string(payload, idx, "achievement_unlocked", "achievement");
    if !is_achievement_slot(achievement) {
        panic!(
            "native Crafter checkpoint achievement_unlocked event {} achievement is unsupported: {}",
            idx, achievement
        );
    }
    if !craftax_achievements_enabled_for_resolved(resolved) && is_craftax_achievement(achievement) {
        panic!(
            "native Crafter checkpoint achievement_unlocked event {} achievement {} is Craftax-only while Craftax achievements are disabled",
            idx, achievement
        );
    }
}

fn validate_player_observation_object(idx: usize, value: &Value, kind: &str, field: &str) {
    let observation = value.as_object().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint {} event {} payload.{} must be an object",
            kind, idx, field
        )
    });
    let pos = observation
        .get("pos")
        .and_then(Value::as_array)
        .unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint {} event {} payload.{}.pos must be an array",
                kind, idx, field
            )
        });
    if pos.len() != 2 || pos.iter().any(|value| value.as_i64().is_none()) {
        panic!(
            "native Crafter checkpoint {} event {} payload.{}.pos must be a two-element integer coordinate",
            kind, idx, field
        );
    }
    let facing = observation
        .get("facing")
        .and_then(Value::as_array)
        .unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint {} event {} payload.{}.facing must be an array",
                kind, idx, field
            )
        });
    if facing.len() != 2 || facing.iter().any(|value| value.as_i64().is_none()) {
        panic!(
            "native Crafter checkpoint {} event {} payload.{}.facing must be a two-element integer direction",
            kind, idx, field
        );
    }
    if observation
        .get("sleeping")
        .and_then(Value::as_bool)
        .is_none()
    {
        panic!(
            "native Crafter checkpoint {} event {} payload.{}.sleeping must be a boolean",
            kind, idx, field
        );
    }
    for stat in ["health", "food", "drink", "energy"] {
        if observation.get(stat).and_then(Value::as_i64).is_none() {
            panic!(
                "native Crafter checkpoint {} event {} payload.{}.{} must be an integer",
                kind, idx, field, stat
            );
        }
    }
    if !observation
        .get("inventory")
        .map(Value::is_object)
        .unwrap_or(false)
    {
        panic!(
            "native Crafter checkpoint {} event {} payload.{}.inventory must be an object",
            kind, idx, field
        );
    }
}

fn validate_restored_state_transition_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    if payload.get("reason").and_then(Value::as_str) == Some("unknown_action") {
        let transition = event.transition.as_ref().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint state_transition event {} missing transition for unknown_action",
                idx
            )
        });
        let transition = transition.as_object().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint state_transition event {} transition must be an object",
                idx
            )
        });
        let step = transition.get("step").and_then(Value::as_object).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint state_transition event {} transition.step must be an object",
                idx
            )
        });
        let _from = step.get("from").and_then(Value::as_u64).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint state_transition event {} transition.step.from must be a nonnegative integer",
                idx
            )
        });
        let _to = step.get("to").and_then(Value::as_u64).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint state_transition event {} transition.step.to must be a nonnegative integer",
                idx
            )
        });
        return;
    }
    validate_player_observation_object(
        idx,
        payload
            .get("player_before")
            .unwrap_or_else(|| {
                panic!(
                    "native Crafter checkpoint state_transition event {} payload.player_before is missing",
                    idx
                )
            }),
        "state_transition",
        "player_before",
    );
    validate_player_observation_object(
        idx,
        payload
            .get("player_after")
            .unwrap_or_else(|| {
                panic!(
                    "native Crafter checkpoint state_transition event {} payload.player_after is missing",
                    idx
                )
            }),
        "state_transition",
        "player_after",
    );
}

fn validate_restored_entity_transition_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    let substrate_event =
        event_payload_string(payload, idx, "entity_transition", "substrate_event");
    if substrate_event.is_empty() {
        panic!(
            "native Crafter checkpoint entity_transition event {} payload.substrate_event must be nonempty",
            idx
        );
    }
}

fn validate_restored_rejection_event(idx: usize, event: &EventRecord, allow_terminal: bool) {
    let payload = event_payload_object(idx, event);
    let reason = event_payload_string(payload, idx, &event.kind, "reason");
    if !(reason == "unknown_action" || (allow_terminal && reason == "terminal")) {
        panic!(
            "native Crafter checkpoint {} event {} reason is unsupported: {}",
            event.kind, idx, reason
        );
    }
}

fn validate_restored_terminal_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    let reason = event_payload_string(payload, idx, &event.kind, "reason");
    let valid_reason = match event.kind.as_str() {
        "death" => reason == "death",
        "episode_truncated" => reason == "max_steps" || reason == "done",
        "terminal" => matches!(reason, "death" | "max_steps" | "done"),
        _ => false,
    };
    if !valid_reason {
        panic!(
            "native Crafter checkpoint {} event {} reason is unsupported: {}",
            event.kind, idx, reason
        );
    }
}

fn validate_restored_resource_delta_event(idx: usize, event: &EventRecord, resolved: &Value) {
    let payload = event_payload_object(idx, event);
    let resource = event_payload_string(payload, idx, "resource_delta", "resource");
    if !is_inventory_slot(resource) || matches!(resource, "health" | "food" | "drink" | "energy") {
        panic!(
            "native Crafter checkpoint resource_delta event {} resource is unsupported: {}",
            idx, resource
        );
    }
    let before = event_payload_i64(payload, idx, "resource_delta", "before");
    let after = event_payload_i64(payload, idx, "resource_delta", "after");
    let delta = event_payload_i64(payload, idx, "resource_delta", "delta");
    if after - before != delta {
        panic!(
            "native Crafter checkpoint resource_delta event {} delta does not match before/after",
            idx
        );
    }
    validate_resource_profile_for_restored_event(idx, resource, resolved);
}

fn validate_resource_profile_for_restored_event(idx: usize, resource: &str, resolved: &Value) {
    let slot = canonical_inventory_key(resource);
    if !craftax_items_enabled_for_resolved(resolved) && CRAFTAX_ITEM_INVENTORY_SLOTS.contains(&slot)
    {
        panic!(
            "native Crafter checkpoint resource_delta event {} resource {} is Craftax-only while Craftax items are disabled",
            idx, resource
        );
    }
    if !craftax_recipes_enabled_for_resolved(resolved)
        && CRAFTAX_RECIPE_INVENTORY_SLOTS.contains(&slot)
    {
        panic!(
            "native Crafter checkpoint resource_delta event {} resource {} is Craftax-recipe-only while Craftax recipes are disabled",
            idx, resource
        );
    }
    if !craftax_potions_enabled_for_resolved(resolved)
        && CRAFTAX_POTION_INVENTORY_SLOTS.contains(&slot)
    {
        panic!(
            "native Crafter checkpoint resource_delta event {} resource {} is Craftax-potion-only while Craftax potions are disabled",
            idx, resource
        );
    }
    if !craftax_xp_enabled_for_resolved(resolved) && CRAFTAX_XP_INVENTORY_SLOTS.contains(&slot) {
        panic!(
            "native Crafter checkpoint resource_delta event {} resource {} is Craftax-XP-only while Craftax XP is disabled",
            idx, resource
        );
    }
}

fn validate_restored_checkpoint_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    let source = event_payload_string(payload, idx, "checkpoint", "source");
    if source != "cadence" {
        panic!(
            "native Crafter checkpoint checkpoint event {} source is unsupported: {}",
            idx, source
        );
    }
    let step_index = event_payload_u64(payload, idx, "checkpoint", "step_index");
    if step_index != event.step_index {
        panic!(
            "native Crafter checkpoint checkpoint event {} payload.step_index does not match event step_index",
            idx
        );
    }
    let interval = event_payload_u64(payload, idx, "checkpoint", "interval");
    if interval == 0 || !step_index.is_multiple_of(interval) {
        panic!(
            "native Crafter checkpoint checkpoint event {} interval does not divide step_index",
            idx
        );
    }
    event_payload_u64(payload, idx, "checkpoint", "nev_cursor_before");
}

fn validate_restored_reward_delta_event(idx: usize, event: &EventRecord) {
    let payload = event_payload_object(idx, event);
    for key in ["delta", "total"] {
        let value = payload.get(key).and_then(Value::as_f64).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload.{} must be a number",
                idx, key
            )
        });
        if !value.is_finite() {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload.{} must be finite",
                idx, key
            );
        }
    }
    let source = payload
        .get("source")
        .and_then(Value::as_str)
        .unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload.source must be a string",
                idx
            )
        });
    if source.is_empty() {
        panic!(
            "native Crafter checkpoint reward_delta event {} payload.source must be nonempty",
            idx
        );
    }
    if let Some(component) = payload.get("component") {
        if component.as_str().is_none_or(str::is_empty) {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload.component must be a nonempty string",
                idx
            );
        }
    }
    if let Some(count) = payload.get("count") {
        if count.as_u64().is_none() {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload.count must be a nonnegative integer",
                idx
            );
        }
    }
    if let Some(achievements) = payload.get("achievements") {
        let achievements = achievements.as_array().unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint reward_delta event {} payload.achievements must be an array",
                idx
            )
        });
        for (achievement_idx, achievement) in achievements.iter().enumerate() {
            let Some(name) = achievement.as_str() else {
                panic!(
                    "native Crafter checkpoint reward_delta event {} payload.achievements[{}] must be a string",
                    idx, achievement_idx
                );
            };
            if !is_achievement_slot(name) {
                panic!(
                    "native Crafter checkpoint reward_delta event {} payload.achievements[{}] is unsupported: {}",
                    idx, achievement_idx, name
                );
            }
        }
    }
}

fn reward_delta_event_number(payload: &Map<String, Value>, idx: usize, key: &str) -> f64 {
    let value = payload.get(key).and_then(Value::as_f64).unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint reward_delta event {} payload.{} must be a number",
            idx, key
        )
    });
    if !value.is_finite() {
        panic!(
            "native Crafter checkpoint reward_delta event {} payload.{} must be finite",
            idx, key
        );
    }
    value
}

fn reward_values_close(left: f64, right: f64) -> bool {
    (left - right).abs() <= 1e-5
}

fn is_nev_event_kind(kind: &str) -> bool {
    matches!(
        kind,
        "task_resolved"
            | "action_applied"
            | "state_transition"
            | "achievement_unlocked"
            | "entity_transition"
            | "death"
            | "episode_truncated"
            | "terminal"
            | "action_rejected"
            | "rule_violation"
            | "resource_delta"
            | "checkpoint"
            | "reward_delta"
    )
}

fn validate_tail_cursor(cursor: usize, offset: Option<usize>, events: Option<&Vec<EventRecord>>) {
    if let Some(offset) = offset {
        if offset > cursor {
            panic!(
                "native Crafter checkpoint nev_tail_cursor_offset {} exceeds nev_cursor {}",
                offset, cursor
            );
        }
    }
    let Some(events) = events else {
        return;
    };
    let offset = offset.unwrap_or_else(|| cursor.saturating_sub(events.len()));
    if offset > cursor {
        panic!(
            "native Crafter checkpoint nev_tail_cursor_offset {} exceeds nev_cursor {}",
            offset, cursor
        );
    }
    let end = offset
        .checked_add(events.len())
        .unwrap_or_else(|| panic!("native Crafter checkpoint NEV cursor arithmetic overflowed"));
    if end != cursor {
        panic!(
            "native Crafter checkpoint nev_tail_cursor_offset {} plus {} tail events does not match nev_cursor {}",
            offset,
            events.len(),
            cursor
        );
    }
}

fn make_world(resolved: &Value) -> NativeWorld {
    let generated = generate_world(resolved);
    let width = resolved["width"].as_u64().unwrap_or(64) as usize;
    let height = resolved["height"].as_u64().unwrap_or(64) as usize;
    let mut world = NativeWorld {
        width,
        height,
        view_radius: resolved["view_radius"].as_u64().unwrap_or(4) as i32,
        max_steps: resolved["max_steps"].as_u64().unwrap_or(10_000),
        seed: resolved["seed"].as_u64().unwrap_or(0),
        tiles: generated.tiles,
        player_pos: ((width / 2) as i32, (height / 2) as i32),
        player_facing: (0, 1),
        player_sleeping: false,
        daylight: 1.0,
        hunger_counter: 0.0,
        thirst_counter: 0.0,
        fatigue_counter: 0,
        recover_counter: 0.0,
        last_health: MAX_INVENTORY_VALUE,
        last_damage_source: None,
        episode: 0,
        step: 0,
        inventory: default_inventory(),
        achievements: ACHIEVEMENTS
            .iter()
            .map(|name| ((*name).to_string(), 0))
            .collect(),
        entities: generated.entities,
        next_entity_id: 0,
        rng: generated.rng,
    };
    apply_initial_state(
        &mut world,
        resolved
            .get("world")
            .and_then(|world| world.get("initial_state")),
    );
    world.next_entity_id = next_entity_seed(&world.entities);
    world.last_health = world
        .inventory
        .get("health")
        .copied()
        .map(counter_as_i32)
        .unwrap_or(MAX_INVENTORY_VALUE);
    if resolved
        .get("adapter_hooks")
        .and_then(|hooks| hooks.get("freeze_daylight"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        world.daylight = 1.0;
    }
    normalize_disabled_daylight_state(&mut world, resolved);
    if resolved
        .get("adapter_hooks")
        .and_then(|hooks| hooks.get("suppress_mobs"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        world.entities.retain(|entity| {
            entity.metadata.get("source").and_then(Value::as_str) == Some("initial_state")
        });
    }
    if resolved
        .get("adapter_hooks")
        .and_then(|hooks| hooks.get("suppress_hostile_mobs"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        world
            .entities
            .retain(|entity| !matches!(entity.kind.as_str(), "zombie" | "skeleton"));
    }
    validate_achievement_profile_state(
        &world.achievements,
        resolved,
        "world.initial_state.achievements",
    );
    validate_inventory_profile_state(&world.inventory, resolved, "world.initial_state.inventory");
    validate_terrain_profile_state(&world.tiles, resolved, "world.initial_state.tiles");
    normalize_disabled_survival_state(&mut world, resolved);
    validate_enabled_survival_state(resolved, &world, "world.initial_state.player");
    normalize_disabled_health_state(&mut world, resolved);
    validate_enabled_health_state(resolved, &world, "world.initial_state.player");
    validate_combat_profile_state(&world, resolved, "world.initial_state.entities");
    validate_mob_profile_state(&world, resolved, "world.initial_state.entities");
    validate_projectile_profile_state(&world, resolved, "world.initial_state.entities");
    validate_entity_health_profile_state(&world, resolved, "world.initial_state.entities");
    validate_entity_runtime_metadata_state(&world, "world.initial_state.entities");
    world
}

fn default_inventory() -> BTreeMap<String, i64> {
    let mut inventory = INVENTORY_KEYS
        .iter()
        .map(|key| ((*key).to_string(), 0))
        .collect::<BTreeMap<_, _>>();
    for key in ["health", "food", "drink", "energy"] {
        inventory.insert(key.to_string(), i64::from(MAX_INVENTORY_VALUE));
    }
    inventory
}

fn normalize_restored_world(world: &mut NativeWorld) {
    normalize_checkpoint_inventory(&mut world.inventory);
    normalize_checkpoint_achievements(&mut world.achievements);
    validate_checkpoint_rng(world);
    if !pos_in_world_bounds(world.width, world.height, world.player_pos) {
        panic!("native Crafter checkpoint player_pos must be within world bounds");
    }
    if !is_unit_facing(world.player_facing) {
        panic!("native Crafter checkpoint player_facing must be a cardinal unit vector");
    }
    for key in world.inventory.keys() {
        if !is_inventory_slot(key) {
            panic!(
                "unsupported inventory slot in native Crafter checkpoint: {}",
                key
            );
        }
    }
    complete_checkpoint_inventory(&mut world.inventory);

    complete_checkpoint_achievements(&mut world.achievements);

    if world.tiles.len() != world.height {
        panic!("native Crafter checkpoint tile height must match world height");
    }
    for (y, row) in world.tiles.iter().enumerate() {
        if row.len() != world.width {
            panic!(
                "native Crafter checkpoint tile row {} width must match world width",
                y
            );
        }
        for material in row {
            if !is_known_material(material) {
                panic!(
                    "unsupported material in native Crafter checkpoint: {}",
                    material
                );
            }
        }
    }
    validate_player_terrain(
        &world.tiles,
        world.player_pos,
        "native Crafter checkpoint player_pos",
    );
    let mut occupied = BTreeSet::new();
    for entity in &world.entities {
        if !is_entity_kind(&entity.kind) {
            panic!(
                "unsupported entity kind in native Crafter checkpoint: {}",
                entity.kind
            );
        }
        if !pos_in_world_bounds(world.width, world.height, entity.pos) {
            panic!(
                "native Crafter checkpoint entity {} position must be within world bounds",
                entity.id
            );
        }
        validate_entity_terrain(
            &world.tiles,
            &entity.kind,
            entity.pos,
            &format!("native Crafter checkpoint entity {}", entity.id),
        );
        if entity.pos == world.player_pos {
            panic!(
                "native Crafter checkpoint entity {} overlaps player_pos",
                entity.id
            );
        }
        if !occupied.insert(entity.pos) {
            panic!(
                "native Crafter checkpoint has duplicate entity position at [{}, {}]",
                entity.pos.0, entity.pos.1
            );
        }
        if entity.health <= 0 || entity.health as u64 > MAX_ENTITY_HEALTH {
            panic!(
                "native Crafter checkpoint entity {} health must be between 1 and {}",
                entity.id, MAX_ENTITY_HEALTH
            );
        }
        validate_checkpoint_entity_metadata(entity);
        if entity.kind == "arrow" {
            let facing = metadata_pos(&entity.metadata, "facing").unwrap_or_else(|| {
                panic!(
                    "native Crafter checkpoint arrow {} missing facing metadata",
                    entity.id
                )
            });
            if !is_unit_facing(facing) {
                panic!(
                    "native Crafter checkpoint arrow {} facing must be a cardinal unit vector",
                    entity.id
                );
            }
            let damage = entity
                .metadata
                .get("damage")
                .map(|value| {
                    value.as_i64().unwrap_or_else(|| {
                        panic!(
                            "native Crafter checkpoint arrow {} damage must be an integer",
                            entity.id
                        )
                    })
                })
                .unwrap_or(2);
            if !(0..=255).contains(&damage) {
                panic!(
                    "native Crafter checkpoint arrow {} damage must be between 0 and 255",
                    entity.id
                );
            }
            let damage_source = entity
                .metadata
                .get("damage_source")
                .and_then(Value::as_str)
                .unwrap_or("arrow");
            if !matches!(
                damage_source,
                "arrow" | "player_arrow" | "craftax_ranged" | "craftax_magic"
            ) {
                panic!(
                    "native Crafter checkpoint arrow {} damage_source is unsupported: {}",
                    entity.id, damage_source
                );
            }
            let projectile_kind = entity
                .metadata
                .get("projectile_kind")
                .map(|value| {
                    let projectile_kind = value.as_str().unwrap_or_else(|| {
                        panic!("native Crafter checkpoint arrow projectile_kind must be a string")
                    });
                    if !is_projectile_kind(projectile_kind) {
                        panic!(
                            "unsupported native Crafter checkpoint arrow projectile_kind: {}",
                            projectile_kind
                        );
                    }
                    projectile_kind
                })
                .unwrap_or("arrow");
            validate_projectile_kind_for_damage_source(
                projectile_kind,
                damage_source,
                &format!("native Crafter checkpoint arrow {}", entity.id),
            );
        }
    }
}

fn validate_checkpoint_entity_metadata(entity: &Entity) {
    for (key, value) in &entity.metadata {
        if key == "source" {
            let source = value.as_str().unwrap_or_else(|| {
                panic!(
                    "native Crafter checkpoint entity {} source metadata must be a string",
                    entity.id
                )
            });
            if !matches!(source, "worldgen" | "runtime" | "initial_state") {
                panic!(
                    "native Crafter checkpoint entity {} source metadata is unsupported: {}",
                    entity.id, source
                );
            }
            continue;
        }
        if matches!(
            key.as_str(),
            "facing" | "damage" | "damage_source" | "projectile_kind"
        ) {
            if entity.kind != "arrow" {
                panic!(
                    "native Crafter checkpoint entity {} metadata.{} is only supported for arrow entities",
                    entity.id, key
                );
            }
            continue;
        }
        let counter_owner = match key.as_str() {
            "grown" if entity.kind == "plant" => None,
            "cooldown" if entity.kind == "zombie" || craftax_mob_stats(&entity.kind).is_some() => {
                None
            }
            "reload" if entity.kind == "skeleton" => None,
            "grown" => Some("plant"),
            "cooldown" => Some("zombie or Craftax mob"),
            "reload" => Some("skeleton"),
            _ => {
                panic!(
                    "unsupported native Crafter checkpoint entity {} metadata key: {}",
                    entity.id, key
                );
            }
        };
        if let Some(owner) = counter_owner {
            panic!(
                "native Crafter checkpoint entity {} metadata.{} is only supported for {} entities",
                entity.id, key, owner
            );
        }
        validate_checkpoint_entity_counter(value, &entity.id, key);
    }
}

fn validate_checkpoint_entity_counter(value: &Value, entity_id: &str, key: &str) {
    let counter = value.as_u64().unwrap_or_else(|| {
        panic!(
            "native Crafter checkpoint entity {} metadata.{} must be a nonnegative integer",
            entity_id, key
        )
    });
    if counter > i32::MAX as u64 {
        panic!(
            "native Crafter checkpoint entity {} metadata.{} must be <= {}",
            entity_id,
            key,
            i32::MAX
        );
    }
}

fn validate_checkpoint_rng(world: &NativeWorld) {
    let rng = &world.rng;
    let seeded = chacha_seed_from_u64(world.seed);
    for (idx, expected) in seeded
        .iter()
        .enumerate()
        .take(12)
        .chain(seeded.iter().enumerate().skip(14))
    {
        if rng.state[idx] != *expected {
            panic!(
                "native Crafter checkpoint rng state[{}] does not match world seed",
                idx
            );
        }
    }
    if rng.buffer.is_empty() {
        if rng.index != 0 {
            panic!("native Crafter checkpoint rng index must be 0 when buffer is empty");
        }
        return;
    }
    if rng.buffer.len() != CHACHA_REFILL_WORDS {
        panic!(
            "native Crafter checkpoint rng buffer must contain {} words when present",
            CHACHA_REFILL_WORDS
        );
    }
    if rng.index > rng.buffer.len() {
        panic!(
            "native Crafter checkpoint rng index {} exceeds buffer length {}",
            rng.index,
            rng.buffer.len()
        );
    }
    let mut replay = ChaCha8Rng {
        state: rng.state,
        buffer: vec![],
        index: 0,
    };
    if !rewind_chacha_counter(&mut replay.state, CHACHA_REFILL_BLOCKS) {
        panic!("native Crafter checkpoint rng buffer is inconsistent with counter state");
    }
    let expected_buffer = replay.refill4();
    if replay.state != rng.state || expected_buffer != rng.buffer {
        panic!("native Crafter checkpoint rng buffer does not match counter state");
    }
}

fn rewind_chacha_counter(state: &mut [u32; 16], blocks: u32) -> bool {
    let (low, borrowed) = state[12].overflowing_sub(blocks);
    state[12] = low;
    if borrowed {
        let (high, high_borrowed) = state[13].overflowing_sub(1);
        if high_borrowed {
            return false;
        }
        state[13] = high;
    }
    true
}

fn validate_restored_runtime_invariants(resolved: &Value, payload: &Value, world: &NativeWorld) {
    let expected_width = required_resolved_u64(resolved, "width");
    let expected_height = required_resolved_u64(resolved, "height");
    let expected_view_radius = required_resolved_u64(resolved, "view_radius");
    let expected_max_steps = required_resolved_u64(resolved, "max_steps");
    let expected_seed = required_resolved_u64(resolved, "seed");
    if world.width as u64 != expected_width {
        panic!(
            "native Crafter checkpoint world.width {} does not match resolved width {}",
            world.width, expected_width
        );
    }
    if world.height as u64 != expected_height {
        panic!(
            "native Crafter checkpoint world.height {} does not match resolved height {}",
            world.height, expected_height
        );
    }
    if world.view_radius < 0 || world.view_radius as u64 != expected_view_radius {
        panic!(
            "native Crafter checkpoint view_radius {} does not match resolved view_radius {}",
            world.view_radius, expected_view_radius
        );
    }
    if world.max_steps != expected_max_steps {
        panic!(
            "native Crafter checkpoint max_steps {} does not match resolved max_steps {}",
            world.max_steps, expected_max_steps
        );
    }
    if world.seed != expected_seed {
        panic!(
            "native Crafter checkpoint seed {} does not match resolved seed {}",
            world.seed, expected_seed
        );
    }
    if world.step > world.max_steps {
        panic!(
            "native Crafter checkpoint step {} exceeds max_steps {}",
            world.step, world.max_steps
        );
    }
    if let Some(step_index) =
        checkpoint_usize_field(payload, "step_index").map(|value| value as u64)
    {
        if step_index != world.step {
            panic!(
                "native Crafter checkpoint step_index {} does not match world.step {}",
                step_index, world.step
            );
        }
    }
    if !world.daylight.is_finite() || !(0.0..=1.0).contains(&world.daylight) {
        panic!("native Crafter checkpoint daylight must be between 0.0 and 1.0");
    }
    validate_disabled_daylight_state(resolved, world, "native Crafter checkpoint");
    if !world.hunger_counter.is_finite() || world.hunger_counter < 0.0 {
        panic!("native Crafter checkpoint hunger_counter must be finite and nonnegative");
    }
    if !world.thirst_counter.is_finite() || world.thirst_counter < 0.0 {
        panic!("native Crafter checkpoint thirst_counter must be finite and nonnegative");
    }
    validate_disabled_survival_state(resolved, world, "native Crafter checkpoint");
    validate_enabled_survival_state(resolved, world, "native Crafter checkpoint");
    if !world.recover_counter.is_finite() {
        panic!("native Crafter checkpoint recover_counter must be finite");
    }
    if !(0..=MAX_INVENTORY_VALUE).contains(&world.last_health) {
        panic!(
            "native Crafter checkpoint last_health must be between 0 and {}",
            MAX_INVENTORY_VALUE
        );
    }
    if let Some(source) = &world.last_damage_source {
        if !matches!(
            source.as_str(),
            "lava"
                | "starvation"
                | "thirst"
                | "exhaustion"
                | "zombie"
                | "craftax_melee"
                | "arrow"
                | "player_arrow"
                | "craftax_ranged"
                | "craftax_magic"
        ) {
            panic!(
                "native Crafter checkpoint last_damage_source is unsupported: {}",
                source
            );
        }
    }
    validate_achievement_profile_state(
        &world.achievements,
        resolved,
        "native Crafter checkpoint achievements",
    );
    validate_inventory_profile_state(
        &world.inventory,
        resolved,
        "native Crafter checkpoint inventory",
    );
    validate_terrain_profile_state(&world.tiles, resolved, "native Crafter checkpoint tiles");
    validate_disabled_health_state(resolved, world, "native Crafter checkpoint");
    validate_enabled_health_state(resolved, world, "native Crafter checkpoint");
    validate_combat_profile_state(world, resolved, "native Crafter checkpoint entities");
    validate_mob_profile_state(world, resolved, "native Crafter checkpoint entities");
    validate_projectile_profile_state(world, resolved, "native Crafter checkpoint entities");
    validate_entity_health_profile_state(world, resolved, "native Crafter checkpoint entities");
    validate_entity_runtime_metadata_state(world, "native Crafter checkpoint entities");
}

fn validate_combat_profile_state(world: &NativeWorld, resolved: &Value, context: &str) {
    if craftax_feature_enabled_for_resolved(resolved, "combat_enabled") {
        return;
    }
    for entity in &world.entities {
        if entity.kind == "arrow" {
            panic!(
                "{} contains arrow entity {} while Craftax combat is disabled",
                context, entity.id
            );
        }
    }
}

fn validate_mob_profile_state(world: &NativeWorld, resolved: &Value, context: &str) {
    let classic_mobs_enabled = classic_mobs_enabled_for_resolved(resolved);
    let craftax_mobs_enabled = craftax_mobs_enabled_for_resolved(resolved);
    for entity in &world.entities {
        let authored_initial = entity
            .metadata
            .get("source")
            .and_then(Value::as_str)
            == Some("initial_state");
        if is_classic_mob_kind(&entity.kind) && !classic_mobs_enabled && !authored_initial {
            panic!(
                "{} contains mob entity {} of kind {} while rules.mobs.enabled=false",
                context, entity.id, entity.kind
            );
        }
        if craftax_mob_stats(&entity.kind).is_some() && !craftax_mobs_enabled && !authored_initial
        {
            panic!(
                "{} contains Craftax mob entity {} of kind {} while Craftax mobs are disabled",
                context, entity.id, entity.kind
            );
        }
    }
}

fn validate_projectile_profile_state(world: &NativeWorld, resolved: &Value, context: &str) {
    let craftax_player_projectiles_enabled =
        craftax_player_projectiles_enabled_for_resolved(resolved);
    let craftax_mob_projectiles_enabled = craftax_mob_projectiles_enabled_for_resolved(resolved);
    for entity in &world.entities {
        if entity.kind != "arrow" {
            continue;
        }
        let damage_source = entity
            .metadata
            .get("damage_source")
            .and_then(Value::as_str)
            .unwrap_or("arrow");
        if damage_source == "player_arrow" && !craftax_player_projectiles_enabled {
            panic!(
                "{} contains player arrow entity {} while Craftax player projectiles are disabled",
                context, entity.id
            );
        }
        if matches!(damage_source, "craftax_ranged" | "craftax_magic")
            && !craftax_mob_projectiles_enabled
        {
            panic!(
                "{} contains Craftax mob projectile entity {} while Craftax mob projectiles are disabled",
                context, entity.id
            );
        }
        let projectile_kind = entity
            .metadata
            .get("projectile_kind")
            .and_then(Value::as_str)
            .unwrap_or("arrow");
        if projectile_kind != "arrow" && !craftax_mob_projectiles_enabled {
            panic!(
                "{} contains Craftax projectile entity {} of kind {} while Craftax mob projectiles are disabled",
                context, entity.id, projectile_kind
            );
        }
    }
}

fn validate_entity_health_profile_state(world: &NativeWorld, resolved: &Value, context: &str) {
    for entity in &world.entities {
        let max_health = resolved_entity_health(resolved, &entity.kind);
        if entity.health > max_health {
            panic!(
                "{} contains entity {} of kind {} with health {} above configured max {}",
                context, entity.id, entity.kind, entity.health, max_health
            );
        }
    }
}

fn validate_entity_runtime_metadata_state(world: &NativeWorld, context: &str) {
    for entity in &world.entities {
        if let Some(reload) = entity.metadata.get("reload") {
            let reload = metadata_counter_i32(reload, &entity.id, "reload");
            if entity.kind == "skeleton" && reload > 4 {
                panic!(
                    "{} contains skeleton {} reload {} above runtime max 4",
                    context, entity.id, reload
                );
            }
        }
        if let Some(cooldown) = entity.metadata.get("cooldown") {
            let cooldown = metadata_counter_i32(cooldown, &entity.id, "cooldown");
            let max_cooldown = if entity.kind == "zombie" {
                Some(5)
            } else {
                craftax_mob_stats(&entity.kind).map(|stats| stats.cooldown)
            };
            if let Some(max_cooldown) = max_cooldown {
                if cooldown > max_cooldown {
                    panic!(
                        "{} contains entity {} of kind {} cooldown {} above runtime max {}",
                        context, entity.id, entity.kind, cooldown, max_cooldown
                    );
                }
            }
        }
    }
}

fn metadata_counter_i32(value: &Value, entity_id: &str, key: &str) -> i32 {
    let raw = value.as_i64().unwrap_or_else(|| {
        panic!(
            "native Crafter entity {} metadata.{} must be a nonnegative integer",
            entity_id, key
        )
    });
    i32::try_from(raw).unwrap_or_else(|_| {
        panic!(
            "native Crafter entity {} metadata.{} must fit in i32",
            entity_id, key
        )
    })
}

fn validate_inventory_profile_state(
    inventory: &BTreeMap<String, i64>,
    resolved: &Value,
    context: &str,
) {
    if !craftax_items_enabled_for_resolved(resolved) {
        validate_zero_inventory_slots(
            inventory,
            &CRAFTAX_ITEM_INVENTORY_SLOTS,
            context,
            "Craftax items are disabled",
        );
    }
    if !craftax_recipes_enabled_for_resolved(resolved) {
        validate_zero_inventory_slots(
            inventory,
            &CRAFTAX_RECIPE_INVENTORY_SLOTS,
            context,
            "Craftax recipes are disabled",
        );
    }
    if !craftax_potions_enabled_for_resolved(resolved) {
        validate_zero_inventory_slots(
            inventory,
            &CRAFTAX_POTION_INVENTORY_SLOTS,
            context,
            "Craftax potions are disabled",
        );
    }
    if !craftax_xp_enabled_for_resolved(resolved) {
        validate_zero_inventory_slots(
            inventory,
            &CRAFTAX_XP_INVENTORY_SLOTS,
            context,
            "Craftax XP is disabled",
        );
    }
}

fn validate_terrain_profile_state(tiles: &[Vec<String>], resolved: &Value, context: &str) {
    let items_enabled = craftax_items_enabled_for_resolved(resolved);
    let chests_enabled = craftax_chests_enabled_for_resolved(resolved);
    for (y, row) in tiles.iter().enumerate() {
        for (x, material) in row.iter().enumerate() {
            if !items_enabled && CRAFTAX_ITEM_TERRAIN.contains(&material.as_str()) {
                panic!(
                    "{}[{}][{}] is {} while Craftax items are disabled",
                    context, y, x, material
                );
            }
            if material == "chest" && !chests_enabled {
                panic!(
                    "{}[{}][{}] is chest while Craftax chests are disabled",
                    context, y, x
                );
            }
        }
    }
}

fn validate_zero_inventory_slots(
    inventory: &BTreeMap<String, i64>,
    slots: &[&str],
    context: &str,
    reason: &str,
) {
    for slot in slots {
        let amount = inventory.get(*slot).copied().unwrap_or(0);
        if amount != 0 {
            panic!("{}.{} is {} while {}", context, slot, amount, reason);
        }
    }
}

fn normalize_disabled_survival_state(world: &mut NativeWorld, resolved: &Value) {
    if !hunger_enabled_for_resolved(resolved) {
        world.hunger_counter = 0.0;
    }
    if !thirst_enabled_for_resolved(resolved) {
        world.thirst_counter = 0.0;
    }
    if !fatigue_enabled_for_resolved(resolved) {
        world.fatigue_counter = 0;
        world.player_sleeping = false;
    }
}

fn validate_disabled_survival_state(resolved: &Value, world: &NativeWorld, context: &str) {
    if !hunger_enabled_for_resolved(resolved) && world.hunger_counter != 0.0 {
        panic!(
            "{} hunger_counter must be 0.0 when hunger is disabled or frozen",
            context
        );
    }
    if !thirst_enabled_for_resolved(resolved) && world.thirst_counter != 0.0 {
        panic!(
            "{} thirst_counter must be 0.0 when thirst is disabled or frozen",
            context
        );
    }
    if !fatigue_enabled_for_resolved(resolved) {
        if world.fatigue_counter != 0 {
            panic!(
                "{} fatigue_counter must be 0 when fatigue is disabled or frozen",
                context
            );
        }
        if world.player_sleeping {
            panic!(
                "{} player_sleeping must be false when fatigue is disabled or frozen",
                context
            );
        }
    }
}

fn validate_enabled_survival_state(resolved: &Value, world: &NativeWorld, context: &str) {
    if hunger_enabled_for_resolved(resolved) {
        let max_hunger = survival_rate_for_resolved(resolved, "hunger_rate", DEFAULT_HUNGER_RATE);
        if world.hunger_counter > max_hunger {
            panic!(
                "{} hunger_counter {} exceeds hunger_rate {}",
                context, world.hunger_counter, max_hunger
            );
        }
    }
    if thirst_enabled_for_resolved(resolved) {
        let max_thirst = survival_rate_for_resolved(resolved, "thirst_rate", DEFAULT_THIRST_RATE);
        if world.thirst_counter > max_thirst {
            panic!(
                "{} thirst_counter {} exceeds thirst_rate {}",
                context, world.thirst_counter, max_thirst
            );
        }
    }
    if fatigue_enabled_for_resolved(resolved)
        && !(MIN_FATIGUE_COUNTER..=MAX_FATIGUE_COUNTER).contains(&world.fatigue_counter)
    {
        panic!(
            "{} fatigue_counter must be between {} and {}",
            context, MIN_FATIGUE_COUNTER, MAX_FATIGUE_COUNTER
        );
    }
    if fatigue_enabled_for_resolved(resolved)
        && world.player_sleeping
        && world.inventory.get("energy").copied().unwrap_or(0) >= i64::from(MAX_INVENTORY_VALUE)
    {
        panic!(
            "{} player_sleeping must be false when energy is already {}",
            context, MAX_INVENTORY_VALUE
        );
    }
}

fn normalize_disabled_daylight_state(world: &mut NativeWorld, resolved: &Value) {
    if daylight_enabled_for_resolved(resolved) {
        return;
    }
    world.daylight = 1.0;
}

fn validate_disabled_daylight_state(resolved: &Value, world: &NativeWorld, context: &str) {
    if daylight_enabled_for_resolved(resolved) {
        return;
    }
    if world.daylight != 1.0 {
        panic!(
            "{} daylight must be 1.0 when rules.day_night.enabled=false or daylight is frozen",
            context
        );
    }
}

fn normalize_disabled_health_state(world: &mut NativeWorld, resolved: &Value) {
    if health_enabled_for_resolved(resolved) {
        return;
    }
    world
        .inventory
        .insert("health".to_string(), i64::from(MAX_INVENTORY_VALUE));
    world.last_health = MAX_INVENTORY_VALUE;
    world.recover_counter = 0.0;
    world.last_damage_source = None;
}

fn validate_disabled_health_state(resolved: &Value, world: &NativeWorld, context: &str) {
    if health_enabled_for_resolved(resolved) {
        return;
    }
    if world.inventory.get("health").copied().unwrap_or(0) != i64::from(MAX_INVENTORY_VALUE) {
        panic!(
            "{} health must be {} when rules.survival.health_enabled=false",
            context, MAX_INVENTORY_VALUE
        );
    }
    if world.last_health != MAX_INVENTORY_VALUE {
        panic!(
            "{} last_health must be {} when rules.survival.health_enabled=false",
            context, MAX_INVENTORY_VALUE
        );
    }
    if world.recover_counter != 0.0 {
        panic!(
            "{} recover_counter must be 0.0 when rules.survival.health_enabled=false",
            context
        );
    }
    if world.last_damage_source.is_some() {
        panic!(
            "{} last_damage_source must be absent when rules.survival.health_enabled=false",
            context
        );
    }
}

fn validate_enabled_health_state(resolved: &Value, world: &NativeWorld, context: &str) {
    if !health_enabled_for_resolved(resolved) {
        return;
    }
    if !(MIN_RECOVER_COUNTER..=MAX_RECOVER_COUNTER).contains(&world.recover_counter) {
        panic!(
            "{} recover_counter must be between {} and {}",
            context, MIN_RECOVER_COUNTER, MAX_RECOVER_COUNTER
        );
    }
    let health = world.inventory.get("health").copied().unwrap_or(0);
    if i64::from(world.last_health) < health {
        panic!(
            "{} last_health {} must be >= current health {}",
            context, world.last_health, health
        );
    }
}

fn health_enabled_for_resolved(resolved: &Value) -> bool {
    resolved
        .get("substrate_config")
        .and_then(|config| config.get("health_enabled"))
        .and_then(Value::as_bool)
        .unwrap_or(true)
}

fn hunger_enabled_for_resolved(resolved: &Value) -> bool {
    survival_enabled_for_resolved(resolved, "hunger_enabled", "freeze_hunger")
}

fn thirst_enabled_for_resolved(resolved: &Value) -> bool {
    survival_enabled_for_resolved(resolved, "thirst_enabled", "freeze_thirst")
}

fn fatigue_enabled_for_resolved(resolved: &Value) -> bool {
    survival_enabled_for_resolved(resolved, "fatigue_enabled", "freeze_fatigue")
}

fn survival_enabled_for_resolved(resolved: &Value, config_key: &str, freeze_hook: &str) -> bool {
    let frozen = resolved
        .get("adapter_hooks")
        .and_then(|hooks| hooks.get(freeze_hook))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if frozen {
        return false;
    }
    resolved
        .get("substrate_config")
        .and_then(|config| config.get(config_key))
        .and_then(Value::as_bool)
        .unwrap_or(true)
}

fn survival_rate_for_resolved(resolved: &Value, key: &str, default: f64) -> f64 {
    resolved
        .get("substrate_config")
        .and_then(|config| config.get(key))
        .and_then(Value::as_f64)
        .or_else(|| {
            resolved
                .get("rules")
                .and_then(|rules| rules.get("survival"))
                .and_then(|survival| survival.get(key))
                .and_then(Value::as_f64)
        })
        .unwrap_or(default)
        .max(1.0)
}

fn daylight_enabled_for_resolved(resolved: &Value) -> bool {
    let freeze_daylight = resolved
        .get("adapter_hooks")
        .and_then(|hooks| hooks.get("freeze_daylight"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if freeze_daylight {
        return false;
    }
    resolved
        .get("substrate_config")
        .and_then(|config| config.get("day_night_cycle"))
        .and_then(Value::as_bool)
        .unwrap_or(true)
}

fn classic_mobs_enabled_for_resolved(resolved: &Value) -> bool {
    resolved
        .get("substrate_config")
        .and_then(|config| config.get("mobs_enabled"))
        .and_then(Value::as_bool)
        .unwrap_or(true)
}

fn craftax_mobs_enabled_for_resolved(resolved: &Value) -> bool {
    if resolved.get("substrate_profile").and_then(Value::as_str) != Some("craftax_partial") {
        return false;
    }
    if !classic_mobs_enabled_for_resolved(resolved) {
        return false;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "enabled", true) && craftax_rule_bool(craftax, "mobs_enabled", true)
}

fn craftax_combat_enabled_for_resolved(resolved: &Value) -> bool {
    if resolved.get("substrate_profile").and_then(Value::as_str) != Some("craftax_partial") {
        return false;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "enabled", true)
        && craftax_rule_bool(craftax, "combat_enabled", true)
}

fn craftax_player_projectiles_enabled_for_resolved(resolved: &Value) -> bool {
    craftax_combat_enabled_for_resolved(resolved) && craftax_items_enabled_for_resolved(resolved)
}

fn craftax_mob_projectiles_enabled_for_resolved(resolved: &Value) -> bool {
    craftax_combat_enabled_for_resolved(resolved) && craftax_mobs_enabled_for_resolved(resolved)
}

fn craftax_items_enabled_for_resolved(resolved: &Value) -> bool {
    if resolved.get("substrate_profile").and_then(Value::as_str) != Some("craftax_partial") {
        return false;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "enabled", true) && craftax_rule_bool(craftax, "items_enabled", true)
}

fn craftax_recipes_enabled_for_resolved(resolved: &Value) -> bool {
    if !craftax_items_enabled_for_resolved(resolved) {
        return false;
    }
    resolved
        .get("rules")
        .and_then(|rules| rules.get("crafting"))
        .map(|crafting| craftax_rule_bool(crafting, "craftax_recipes", false))
        .unwrap_or(false)
}

fn craftax_potions_enabled_for_resolved(resolved: &Value) -> bool {
    if !craftax_items_enabled_for_resolved(resolved) {
        return false;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "potions_enabled", true)
}

fn craftax_chests_enabled_for_resolved(resolved: &Value) -> bool {
    if !craftax_items_enabled_for_resolved(resolved) {
        return false;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "chests_enabled", true)
}

fn craftax_xp_enabled_for_resolved(resolved: &Value) -> bool {
    if resolved.get("substrate_profile").and_then(Value::as_str) != Some("craftax_partial") {
        return false;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "enabled", true) && craftax_rule_bool(craftax, "xp_enabled", true)
}

fn validate_achievement_profile_state(
    achievements: &BTreeMap<String, i64>,
    resolved: &Value,
    context: &str,
) {
    if craftax_achievements_enabled_for_resolved(resolved) {
        return;
    }
    for (key, count) in achievements {
        if *count > 0 && is_craftax_achievement(key) {
            panic!(
                "{}.{} is Craftax-only but Craftax achievements are disabled",
                context, key
            );
        }
    }
}

fn craftax_achievements_enabled_for_resolved(resolved: &Value) -> bool {
    let include_craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("achievements"))
        .and_then(|achievements| achievements.get("enabled"))
        .and_then(Value::as_str)
        .unwrap_or("classic")
        == "classic_plus_craftax";
    include_craftax && craftax_feature_enabled_for_resolved(resolved, "achievements_enabled")
}

fn craftax_feature_enabled_for_resolved(resolved: &Value, key: &str) -> bool {
    if resolved.get("substrate_profile").and_then(Value::as_str) != Some("craftax_partial") {
        return true;
    }
    let craftax = resolved
        .get("rules")
        .and_then(|rules| rules.get("craftax"))
        .unwrap_or(&Value::Null);
    craftax_rule_bool(craftax, "enabled", true) && craftax_rule_bool(craftax, key, true)
}

fn required_resolved_u64(resolved: &Value, key: &str) -> u64 {
    resolved
        .get(key)
        .and_then(Value::as_u64)
        .unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint resolved.{} must be an integer",
                key
            )
        })
}

fn pos_in_world_bounds(width: usize, height: usize, pos: (i32, i32)) -> bool {
    pos.0 >= 0 && pos.1 >= 0 && (pos.0 as usize) < width && (pos.1 as usize) < height
}

fn is_unit_facing(pos: (i32, i32)) -> bool {
    matches!(pos, (-1, 0) | (1, 0) | (0, -1) | (0, 1))
}

fn normalize_checkpoint_inventory(inventory: &mut BTreeMap<String, i64>) {
    if let Some(value) = inventory.remove("armor") {
        validate_checkpoint_inventory_amount("armor", value);
        for armor_key in ARMOR_SLOTS {
            if inventory.contains_key(armor_key) {
                panic!(
                    "duplicate native Crafter checkpoint inventory slot after alias normalization: {}",
                    armor_key
                );
            }
            inventory.insert(armor_key.to_string(), value);
        }
    }
    let aliases = inventory
        .keys()
        .filter_map(|key| {
            let canonical = canonical_inventory_key(key);
            if canonical == key {
                None
            } else {
                Some((key.clone(), canonical.to_string()))
            }
        })
        .collect::<Vec<_>>();
    for (alias, canonical) in aliases {
        let value = inventory.remove(&alias).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint inventory alias {} disappeared during normalization",
                alias
            )
        });
        validate_checkpoint_inventory_amount(&alias, value);
        if inventory.contains_key(&canonical) {
            panic!(
                "duplicate native Crafter checkpoint inventory slot after alias normalization: {}",
                canonical
            );
        }
        inventory.insert(canonical, value);
    }
}

fn complete_checkpoint_inventory(inventory: &mut BTreeMap<String, i64>) {
    for key in INVENTORY_KEYS {
        let value = inventory.get(key).copied().unwrap_or(0);
        validate_checkpoint_inventory_amount(key, value);
        inventory.insert(key.to_string(), value);
    }
}

fn validate_checkpoint_inventory_amount(key: &str, value: i64) {
    let limit = inventory_limit(key);
    if !(0..=limit).contains(&value) {
        panic!(
            "native Crafter checkpoint inventory.{} must be between 0 and {}",
            key, limit
        );
    }
}

fn normalize_checkpoint_achievements(achievements: &mut BTreeMap<String, i64>) {
    let aliases = achievements
        .keys()
        .filter_map(|key| {
            let canonical = canonical_achievement_key(key);
            if canonical == key {
                None
            } else {
                Some((key.clone(), canonical.to_string()))
            }
        })
        .collect::<Vec<_>>();
    for (alias, canonical) in aliases {
        let value = achievements.remove(&alias).unwrap_or_else(|| {
            panic!(
                "native Crafter checkpoint achievement alias {} disappeared during normalization",
                alias
            )
        });
        validate_checkpoint_achievement_amount(&alias, value);
        if achievements.contains_key(&canonical) {
            panic!(
                "duplicate native Crafter checkpoint achievement after alias normalization: {}",
                canonical
            );
        }
        achievements.insert(canonical, value);
    }
}

fn complete_checkpoint_achievements(achievements: &mut BTreeMap<String, i64>) {
    for key in achievements.keys() {
        if !is_achievement_slot(key) {
            panic!(
                "unsupported achievement in native Crafter checkpoint: {}",
                key
            );
        }
    }
    for key in ACHIEVEMENTS {
        let value = achievements.get(key).copied().unwrap_or(0);
        validate_checkpoint_achievement_amount(key, value);
        achievements.insert(key.to_string(), value);
    }
}

fn validate_checkpoint_achievement_amount(key: &str, value: i64) {
    if value < 0 {
        panic!(
            "native Crafter checkpoint achievement.{} must be nonnegative",
            key
        );
    }
}

fn apply_initial_state(world: &mut NativeWorld, initial: Option<&Value>) {
    let Some(initial) = initial else {
        return;
    };
    if let Some(daylight) = initial.get("daylight").and_then(Value::as_f64) {
        world.daylight = daylight;
    }
    if let Some(step) = initial.get("step").and_then(Value::as_u64) {
        world.step = step;
    }
    if let Some(tiles) = initial.get("tiles").and_then(Value::as_array) {
        for patch in tiles {
            let pos = value_pos(patch.get("pos").unwrap_or(&Value::Null));
            let kind = patch.get("kind").and_then(Value::as_str).unwrap_or("grass");
            if !is_known_material(kind) {
                panic!(
                    "unsupported material in native Crafter initial_state: {}",
                    kind
                );
            }
            if pos.0 >= 0
                && pos.1 >= 0
                && (pos.0 as usize) < world.width
                && (pos.1 as usize) < world.height
            {
                world.tiles[pos.1 as usize][pos.0 as usize] = kind.to_string();
            }
        }
    }
    if let Some(player) = initial.get("player") {
        if let Some(pos) = player.get("pos") {
            world.player_pos = value_pos(pos);
        }
        if let Some(facing) = player.get("facing") {
            world.player_facing = value_pos(facing);
        }
        if let Some(sleeping) = player.get("sleeping").and_then(Value::as_bool) {
            world.player_sleeping = sleeping;
        }
        if let Some(value) = player.get("hunger_counter").and_then(Value::as_f64) {
            world.hunger_counter = value;
        }
        if let Some(value) = player.get("thirst_counter").and_then(Value::as_f64) {
            world.thirst_counter = value;
        }
        if let Some(value) = player.get("fatigue_counter").and_then(Value::as_i64) {
            world.fatigue_counter = value as i32;
        }
        if let Some(value) = player.get("recover_counter").and_then(Value::as_f64) {
            world.recover_counter = value;
        }
    }
    validate_player_terrain(
        &world.tiles,
        world.player_pos,
        "world.initial_state.player.pos",
    );
    for entity in &world.entities {
        validate_entity_terrain(
            &world.tiles,
            &entity.kind,
            entity.pos,
            &format!("world.initial_state existing entity {}", entity.id),
        );
    }
    if world
        .entities
        .iter()
        .any(|entity| entity.pos == world.player_pos)
    {
        panic!("world.initial_state.player.pos is occupied by an existing entity");
    }
    if let Some(inventory) = initial.get("inventory").and_then(Value::as_object) {
        for (key, value) in inventory {
            if !is_inventory_slot(key) {
                panic!(
                    "unsupported inventory slot in native Crafter initial_state: {}",
                    key
                );
            }
            let amount = value.as_i64().unwrap_or(0);
            if key == "armor" {
                for armor_key in ARMOR_SLOTS {
                    world
                        .inventory
                        .insert(armor_key.to_string(), clamp_inventory(armor_key, amount));
                }
                continue;
            }
            let canonical = canonical_inventory_key(key);
            world
                .inventory
                .insert(canonical.to_string(), clamp_inventory(canonical, amount));
        }
    }
    if let Some(achievements) = initial.get("achievements").and_then(Value::as_object) {
        for (key, value) in achievements {
            if !is_achievement_slot(key) {
                panic!(
                    "unsupported achievement in native Crafter initial_state: {}",
                    key
                );
            }
            let canonical = canonical_achievement_key(key);
            world
                .achievements
                .insert(canonical.to_string(), value.as_i64().unwrap_or(0));
        }
    }
    if let Some(entities) = initial.get("entities").and_then(Value::as_array) {
        let mut occupied = world
            .entities
            .iter()
            .map(|entity| entity.pos)
            .collect::<BTreeSet<_>>();
        for (idx, raw) in entities.iter().enumerate() {
            let kind = raw.get("kind").and_then(Value::as_str).unwrap_or("");
            if !is_entity_kind(kind) {
                panic!(
                    "unsupported entity kind in native Crafter initial_state: {}",
                    kind
                );
            }
            let pos = value_pos(raw.get("pos").unwrap_or(&Value::Null));
            if pos == world.player_pos {
                panic!(
                    "world.initial_state.entities[{}].pos is occupied by the player",
                    idx
                );
            }
            if !occupied.insert(pos) {
                panic!(
                    "world.initial_state.entities[{}].pos is occupied by another entity",
                    idx
                );
            }
            validate_entity_terrain(
                &world.tiles,
                kind,
                pos,
                &format!("world.initial_state.entities[{}].pos", idx),
            );
            let mut metadata = BTreeMap::new();
            metadata.insert("source".to_string(), json!("initial_state"));
            if kind == "arrow" {
                let facing = raw.get("facing").unwrap_or_else(|| {
                    panic!(
                        "world.initial_state.entities[{}].facing is required for arrow entities",
                        idx
                    )
                });
                let facing = value_pos(facing);
                metadata.insert("facing".to_string(), json!([facing.0, facing.1]));
                let damage = raw
                    .get("damage")
                    .and_then(Value::as_i64)
                    .or_else(|| {
                        raw.get("damage")
                            .and_then(Value::as_u64)
                            .map(|value| value as i64)
                    })
                    .unwrap_or(2);
                metadata.insert("damage".to_string(), json!(damage));
                let damage_source = raw
                    .get("damage_source")
                    .and_then(Value::as_str)
                    .unwrap_or("arrow");
                metadata.insert("damage_source".to_string(), json!(damage_source));
                if let Some(projectile_kind) = raw.get("projectile_kind").and_then(Value::as_str) {
                    metadata.insert("projectile_kind".to_string(), json!(projectile_kind));
                }
            }
            for key in ["grown", "cooldown", "reload"] {
                if let Some(value) = raw.get(key).and_then(Value::as_i64) {
                    metadata.insert(key.to_string(), json!(value));
                }
            }
            world.entities.push(Entity {
                id: format!("initial_{}_{}", kind, idx),
                kind: kind.to_string(),
                pos,
                health: raw
                    .get("health")
                    .and_then(Value::as_i64)
                    .unwrap_or(default_entity_health(kind) as i64) as i32,
                metadata,
            });
        }
    }
}

fn value_pos(value: &Value) -> (i32, i32) {
    let arr = value
        .as_array()
        .unwrap_or_else(|| panic!("expected [x, y] position"));
    (
        arr.first().and_then(Value::as_i64).unwrap_or(0) as i32,
        arr.get(1).and_then(Value::as_i64).unwrap_or(0) as i32,
    )
}

fn terrain_at<'a>(tiles: &'a [Vec<String>], pos: (i32, i32), context: &str) -> &'a str {
    let y = usize::try_from(pos.1)
        .unwrap_or_else(|_| panic!("{} must be within world bounds", context));
    let x = usize::try_from(pos.0)
        .unwrap_or_else(|_| panic!("{} must be within world bounds", context));
    tiles
        .get(y)
        .and_then(|row| row.get(x))
        .map(String::as_str)
        .unwrap_or_else(|| panic!("{} must be within world bounds", context))
}

fn validate_player_terrain(tiles: &[Vec<String>], pos: (i32, i32), context: &str) {
    let tile = terrain_at(tiles, pos, context);
    if !WALKABLE.contains(&tile) {
        panic!("{} must be on walkable terrain, got {}", context, tile);
    }
}

fn validate_entity_terrain(tiles: &[Vec<String>], kind: &str, pos: (i32, i32), context: &str) {
    let tile = terrain_at(tiles, pos, context);
    let valid = match kind {
        "arrow" => WALKABLE.contains(&tile) || tile == "water",
        "plant" => tile == "grass",
        _ => WALKABLE.contains(&tile),
    };
    if !valid {
        panic!(
            "{} must be on valid {} terrain, got {}",
            context, kind, tile
        );
    }
}

fn metadata_pos(metadata: &BTreeMap<String, Value>, key: &str) -> Option<(i32, i32)> {
    metadata.get(key).and_then(|value| {
        let arr = value.as_array()?;
        Some((
            arr.first().and_then(Value::as_i64).unwrap_or(0) as i32,
            arr.get(1).and_then(Value::as_i64).unwrap_or(0) as i32,
        ))
    })
}

fn manhattan(a: (i32, i32), b: (i32, i32)) -> i32 {
    (a.0 - b.0).abs() + (a.1 - b.1).abs()
}

fn scaled_damage(base_damage: f64, multiplier: f64) -> i32 {
    let damage = (base_damage * multiplier).max(0.0);
    let rounded = damage.round() as i32;
    if rounded == 0 && damage > 0.0 {
        1
    } else {
        rounded
    }
}

fn max_inventory_i32() -> i32 {
    MAX_INVENTORY_VALUE
}

fn next_entity_seed(entities: &[Entity]) -> u64 {
    entities
        .iter()
        .filter_map(|entity| entity.id.strip_prefix("world_"))
        .filter_map(|suffix| suffix.parse::<u64>().ok())
        .max()
        .unwrap_or(0)
        + 1
}

fn validate_restored_entity_ids(world: &NativeWorld) {
    let mut ids = BTreeSet::new();
    let mut max_world_id = None;
    for entity in &world.entities {
        if entity.id.is_empty() {
            panic!("native Crafter checkpoint entity id must be nonempty");
        }
        if !ids.insert(entity.id.as_str()) {
            panic!(
                "native Crafter checkpoint duplicate entity id: {}",
                entity.id
            );
        }
        if let Some(suffix) = entity.id.strip_prefix("world_") {
            let parsed = suffix.parse::<u64>().unwrap_or_else(|_| {
                panic!(
                    "native Crafter checkpoint entity id {} has invalid world_ suffix",
                    entity.id
                )
            });
            max_world_id = Some(max_world_id.map_or(parsed, |current: u64| current.max(parsed)));
        }
    }
    let expected_next_entity_id = next_entity_seed(&world.entities);
    if world.next_entity_id < expected_next_entity_id {
        panic!(
            "native Crafter checkpoint next_entity_id {} must be at least {}",
            world.next_entity_id, expected_next_entity_id
        );
    }
    if let Some(max_world_id) = max_world_id {
        if world.next_entity_id <= max_world_id {
            panic!(
                "native Crafter checkpoint next_entity_id {} must exceed existing world entity id {}",
                world.next_entity_id, max_world_id
            );
        }
    }
}

fn world_map_tiles(map: &Value, width: usize, height: usize) -> Vec<Vec<String>> {
    let rows = map
        .get("tiles")
        .and_then(Value::as_array)
        .expect("resolved world.map.tiles must be an array");
    if rows.len() != height {
        panic!("resolved world.map height mismatch");
    }
    rows.iter()
        .enumerate()
        .map(|(y, row)| {
            let row = row
                .as_array()
                .unwrap_or_else(|| panic!("resolved world.map.tiles[{}] must be an array", y));
            if row.len() != width {
                panic!("resolved world.map row {} width mismatch", y);
            }
            row.iter()
                .enumerate()
                .map(|(x, value)| {
                    let material = value.as_str().unwrap_or_else(|| {
                        panic!("resolved world.map.tiles[{}][{}] must be a material", y, x)
                    });
                    if !is_known_material(material) {
                        panic!("unsupported resolved world.map material: {}", material);
                    }
                    material.to_string()
                })
                .collect()
        })
        .collect()
}

fn generate_world(resolved: &Value) -> GeneratedWorld {
    let seed = resolved["seed"].as_u64().unwrap_or(0);
    let mut rng = ChaCha8Rng::new(seed);
    let width = resolved["width"].as_u64().unwrap_or(64) as usize;
    let height = resolved["height"].as_u64().unwrap_or(64) as usize;
    if let Some(map) = resolved.get("world").and_then(|world| world.get("map")) {
        return GeneratedWorld {
            tiles: world_map_tiles(map, width, height),
            entities: vec![],
            rng,
        };
    }
    let simplex = OpenSimplex3::new(seed as u32);
    let player_pos = ((width / 2) as i32, (height / 2) as i32);
    let mut densities = BTreeMap::new();
    let mut runtime_mobs_enabled = true;
    if let Some(config) = resolved.get("substrate_config").and_then(Value::as_object) {
        for (key, value) in config {
            if key == "mobs_enabled" {
                runtime_mobs_enabled = value.as_bool().unwrap_or(true);
            }
            if let Some(number) = value.as_f64() {
                densities.insert(key.clone(), number);
            }
        }
    }
    if !runtime_mobs_enabled {
        densities.insert("cow_density".to_string(), 0.0);
        densities.insert("zombie_density".to_string(), 0.0);
        densities.insert("skeleton_density".to_string(), 0.0);
    }
    let mut tiles = vec![vec!["grass".to_string(); width]; height];
    let mut tunnels = vec![vec![false; height]; width];
    for y in 0..height {
        for x in 0..width {
            let (material, tunnel) = terrain_material(
                x as f64, y as f64, player_pos, &simplex, &mut rng, &densities,
            );
            tiles[y][x] = material;
            tunnels[x][y] = tunnel;
        }
    }
    let mut entities = spawn_classic_entities(
        &tiles,
        &tunnels,
        player_pos,
        &mut rng,
        &densities,
        ClassicMobHealth {
            cow: resolved_entity_health(resolved, "cow"),
            zombie: resolved_entity_health(resolved, "zombie"),
            skeleton: resolved_entity_health(resolved, "skeleton"),
        },
    );
    if resolved.get("substrate_profile").and_then(Value::as_str) == Some("craftax_partial") {
        let craftax_config = resolved
            .get("rules")
            .and_then(|rules| rules.get("craftax"))
            .unwrap_or(&Value::Null);
        if craftax_rule_bool(craftax_config, "enabled", true)
            && craftax_rule_bool(craftax_config, "worldgen_enabled", true)
        {
            apply_craftax_worldgen(
                &mut tiles,
                &tunnels,
                &mut entities,
                player_pos,
                &mut rng,
                CraftaxWorldgenContext {
                    config: craftax_config,
                    resolved,
                    runtime_mobs_enabled,
                },
            );
        }
    }
    validate_generated_terrain_occupancy(&tiles, &entities, player_pos);
    GeneratedWorld {
        tiles,
        entities,
        rng,
    }
}

fn validate_generated_terrain_occupancy(
    tiles: &[Vec<String>],
    entities: &[Entity],
    player_pos: (i32, i32),
) {
    validate_player_terrain(tiles, player_pos, "native Crafter generated player_pos");
    let mut occupied = BTreeSet::new();
    occupied.insert(player_pos);
    for entity in entities {
        validate_entity_terrain(
            tiles,
            &entity.kind,
            entity.pos,
            &format!("native Crafter generated entity {}", entity.id),
        );
        if !occupied.insert(entity.pos) {
            panic!(
                "native Crafter generated entity {} has duplicate occupied position [{}, {}]",
                entity.id, entity.pos.0, entity.pos.1
            );
        }
    }
}

fn terrain_material(
    x: f64,
    y: f64,
    player_pos: (i32, i32),
    simplex: &OpenSimplex3,
    rng: &mut ChaCha8Rng,
    densities: &BTreeMap<String, f64>,
) -> (String, bool) {
    let px = player_pos.0 as f64;
    let py = player_pos.1 as f64;
    let dist = ((x - px).powi(2) + (y - py).powi(2)).sqrt();
    let mut start = 4.0 - dist;
    start += 2.0 * simplex3_single(simplex, x, y, 8.0, 3.0);
    start = 1.0 / (1.0 + (-start).exp());
    let mut water = simplex3(simplex, x, y, 3.0, &[(15.0, 1.0), (5.0, 0.15)], false) + 0.1;
    water -= 2.0 * start;
    let mut mountain = simplex3(simplex, x, y, 0.0, &[(15.0, 1.0), (5.0, 0.3)], true);
    mountain -= 4.0 * start + 0.3 * water;
    if start > 0.5 {
        return ("grass".to_string(), false);
    }
    if mountain > 0.15 {
        return mountain_material(x, y, mountain, simplex, rng, densities);
    }
    if water > 0.25 && water <= 0.35 && simplex3_single(simplex, x, y, 4.0, 9.0) > -0.2 {
        return ("sand".to_string(), false);
    }
    if water > 0.3 {
        return ("water".to_string(), false);
    }
    (grassland_material(x, y, simplex, rng, densities), false)
}

fn mountain_material(
    x: f64,
    y: f64,
    mountain: f64,
    simplex: &OpenSimplex3,
    rng: &mut ChaCha8Rng,
    densities: &BTreeMap<String, f64>,
) -> (String, bool) {
    if simplex3_single(simplex, x, y, 6.0, 7.0) > 0.15 && mountain > 0.3 {
        return ("path".to_string(), false);
    }
    if simplex3_single(simplex, 2.0 * x, y / 5.0, 7.0, 3.0) > 0.4 {
        return ("path".to_string(), true);
    }
    if simplex3_single(simplex, x / 5.0, 2.0 * y, 7.0, 3.0) > 0.4 {
        return ("path".to_string(), true);
    }
    if simplex3_single(simplex, x, y, 1.0, 8.0) > 0.0
        && rng.random_f64() > scaled_threshold(0.30, density(densities, "coal_density"))
    {
        return ("coal".to_string(), false);
    }
    if simplex3_single(simplex, x, y, 2.0, 6.0) > 0.3
        && rng.random_f64() > scaled_threshold(0.30, density(densities, "iron_density"))
    {
        return ("iron".to_string(), false);
    }
    if mountain > 0.18
        && rng.random_f64() > scaled_threshold(0.016, density(densities, "diamond_density"))
    {
        return ("diamond".to_string(), false);
    }
    if mountain > 0.3 && simplex3_single(simplex, x, y, 6.0, 5.0) > 0.35 {
        return ("lava".to_string(), false);
    }
    ("stone".to_string(), false)
}

fn grassland_material(
    x: f64,
    y: f64,
    simplex: &OpenSimplex3,
    rng: &mut ChaCha8Rng,
    densities: &BTreeMap<String, f64>,
) -> String {
    if simplex3_single(simplex, x, y, 5.0, 7.0) > 0.0
        && rng.random_f64() > scaled_threshold(0.2, density(densities, "tree_density"))
    {
        "tree".to_string()
    } else {
        "grass".to_string()
    }
}

fn spawn_classic_entities(
    tiles: &[Vec<String>],
    tunnels: &[Vec<bool>],
    player_pos: (i32, i32),
    rng: &mut ChaCha8Rng,
    densities: &BTreeMap<String, f64>,
    mob_health: ClassicMobHealth,
) -> Vec<Entity> {
    let mut entities = vec![];
    let mut occupied = BTreeSet::new();
    occupied.insert(player_pos);
    for (y, row) in tiles.iter().enumerate() {
        for (x, tile) in row.iter().enumerate() {
            if !WALKABLE.contains(&tile.as_str()) {
                continue;
            }
            let pos = (x as i32, y as i32);
            let dist_sq = (pos.0 - player_pos.0).pow(2) + (pos.1 - player_pos.1).pow(2);
            if tile == "grass"
                && dist_sq > 9
                && rng.random_f64() > scaled_threshold(0.015, density(densities, "cow_density"))
                && !occupied.contains(&pos)
            {
                occupied.insert(pos);
                entities.push(entity("cow", pos, mob_health.cow, entities.len()));
            }
            if dist_sq > 100
                && rng.random_f64() > scaled_threshold(0.007, density(densities, "zombie_density"))
                && !occupied.contains(&pos)
            {
                occupied.insert(pos);
                entities.push(entity("zombie", pos, mob_health.zombie, entities.len()));
            }
            if tile == "path"
                && tunnels
                    .get(x)
                    .and_then(|col| col.get(y))
                    .copied()
                    .unwrap_or(false)
                && rng.random_f64() > scaled_threshold(0.05, density(densities, "skeleton_density"))
                && !occupied.contains(&pos)
            {
                occupied.insert(pos);
                entities.push(entity("skeleton", pos, mob_health.skeleton, entities.len()));
            }
        }
    }
    entities
}

fn apply_craftax_worldgen(
    tiles: &mut [Vec<String>],
    tunnels: &[Vec<bool>],
    entities: &mut Vec<Entity>,
    player_pos: (i32, i32),
    rng: &mut ChaCha8Rng,
    context: CraftaxWorldgenContext<'_>,
) {
    let mut occupied = entities
        .iter()
        .map(|entity| entity.pos)
        .collect::<BTreeSet<_>>();
    occupied.insert(player_pos);
    let items_enabled = craftax_rule_bool(context.config, "items_enabled", true);
    let chests_enabled = craftax_rule_bool(context.config, "chests_enabled", true);
    let mobs_enabled =
        craftax_rule_bool(context.config, "mobs_enabled", true) && context.runtime_mobs_enabled;
    for (y, row) in tiles.iter_mut().enumerate() {
        for (x, cell) in row.iter_mut().enumerate() {
            let pos = (x as i32, y as i32);
            let dist_sq = (pos.0 - player_pos.0).pow(2) + (pos.1 - player_pos.1).pow(2);
            let tile = cell.clone();
            if items_enabled && tile == "stone" {
                if rng.random_f32() < 0.004 {
                    *cell = "sapphire".to_string();
                    continue;
                }
                if rng.random_f32() < 0.003 {
                    *cell = "ruby".to_string();
                    continue;
                }
            }
            if items_enabled
                && chests_enabled
                && dist_sq > 36
                && matches!(tile.as_str(), "grass" | "path")
                && !occupied.contains(&pos)
                && rng.random_f32() < 0.002
            {
                *cell = "chest".to_string();
                continue;
            }
            if !mobs_enabled {
                continue;
            }
            if tile == "grass"
                && dist_sq > 16
                && rng.random_f32() < 0.01
                && !occupied.contains(&pos)
            {
                occupied.insert(pos);
                entities.push(entity(
                    "snail",
                    pos,
                    resolved_entity_health(context.resolved, "snail"),
                    entities.len(),
                ));
                continue;
            }
            if tile == "path"
                && tunnels
                    .get(x)
                    .and_then(|col| col.get(y))
                    .copied()
                    .unwrap_or(false)
                && rng.random_f32() < 0.02
                && !occupied.contains(&pos)
            {
                occupied.insert(pos);
                entities.push(entity(
                    "bat",
                    pos,
                    resolved_entity_health(context.resolved, "bat"),
                    entities.len(),
                ));
                continue;
            }
            if dist_sq > 100
                && matches!(tile.as_str(), "grass" | "path" | "sand" | "lava")
                && !occupied.contains(&pos)
            {
                let mut spawned = false;
                for (kind, probability) in [
                    ("orc_soldier", 0.004_f32),
                    ("orc_mage", 0.003_f32),
                    ("knight", 0.003_f32),
                    ("knight_archer", 0.003_f32),
                ] {
                    if rng.random_f32() < probability {
                        occupied.insert(pos);
                        entities.push(entity(
                            kind,
                            pos,
                            resolved_entity_health(context.resolved, kind),
                            entities.len(),
                        ));
                        spawned = true;
                        break;
                    }
                }
                if !spawned && (tile == "lava" || rng.random_f32() < 0.002) {
                    occupied.insert(pos);
                    entities.push(entity(
                        "troll",
                        pos,
                        resolved_entity_health(context.resolved, "troll"),
                        entities.len(),
                    ));
                }
            }
        }
    }
}

fn entity(kind: &str, pos: (i32, i32), health: i32, idx: usize) -> Entity {
    Entity {
        id: format!("world_{}", idx),
        kind: kind.to_string(),
        pos,
        health,
        metadata: BTreeMap::from([("source".to_string(), json!("worldgen"))]),
    }
}

fn density(densities: &BTreeMap<String, f64>, key: &str) -> f64 {
    densities.get(key).copied().unwrap_or(1.0)
}

fn scaled_threshold(base_probability: f64, multiplier: f64) -> f64 {
    1.0 - (base_probability * multiplier.max(0.0)).min(1.0)
}

fn simplex3(
    simplex: &OpenSimplex3,
    x: f64,
    y: f64,
    z: f64,
    sizes: &[(f64, f64)],
    normalize: bool,
) -> f64 {
    let mut value = 0.0;
    let mut total = 0.0;
    for (size, weight) in sizes {
        value += weight * simplex.get(x / size, y / size, z);
        total += weight;
    }
    if normalize && total != 0.0 {
        value / total
    } else {
        value
    }
}

fn simplex3_single(simplex: &OpenSimplex3, x: f64, y: f64, z: f64, size: f64) -> f64 {
    simplex.get(x / size, y / size, z)
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ChaCha8Rng {
    state: [u32; 16],
    buffer: Vec<u32>,
    index: usize,
}

impl ChaCha8Rng {
    fn new(seed: u64) -> Self {
        Self {
            state: chacha_seed_from_u64(seed),
            buffer: vec![],
            index: 0,
        }
    }

    fn next_u32(&mut self) -> u32 {
        if self.index >= self.buffer.len() {
            self.buffer = self.refill4();
            self.index = 0;
        }
        let value = self.buffer[self.index];
        self.index += 1;
        value
    }

    fn next_u64(&mut self) -> u64 {
        let low = self.next_u32() as u64;
        let high = self.next_u32() as u64;
        low | (high << 32)
    }

    fn random_f64(&mut self) -> f64 {
        ((self.next_u64() >> 11) as f64) * (1.0 / ((1u64 << 53) as f64))
    }

    fn random_f32(&mut self) -> f32 {
        ((self.next_u32() >> 8) as f32) * (1.0 / ((1u32 << 24) as f32))
    }

    fn gen_range_u32_inclusive(&mut self, low: u32, high: u32) -> u32 {
        assert!(low <= high);
        let exclusive_high = high
            .checked_add(1)
            .expect("inclusive RNG upper bound must be below u32::MAX");
        sample_u32_exclusive(low, exclusive_high, || self.next_u32())
    }

    fn refill4(&mut self) -> Vec<u32> {
        let mut out = vec![];
        let mut base = self.state;
        for _ in 0..4 {
            let mut block_state = base;
            for _ in 0..4 {
                chacha_double_round(&mut block_state);
            }
            for (idx, value) in block_state.iter().enumerate() {
                out.push(value.wrapping_add(base[idx]));
            }
            base[12] = base[12].wrapping_add(1);
            if base[12] == 0 {
                base[13] = base[13].wrapping_add(1);
            }
        }
        self.state[12] = base[12];
        self.state[13] = base[13];
        out
    }
}

#[derive(Clone, Debug)]
struct XorShiftRng {
    x: u32,
    y: u32,
    z: u32,
    w: u32,
}

impl XorShiftRng {
    fn new(seed: u32) -> Self {
        let mut data = [0u8; 16];
        data[0] = 1;
        for idx in 1..4 {
            let start = idx * 4;
            data[start] = (seed & 0xFF) as u8;
            data[start + 1] = ((seed >> 8) & 0xFF) as u8;
            data[start + 2] = ((seed >> 16) & 0xFF) as u8;
            data[start + 3] = ((seed >> 24) & 0xFF) as u8;
        }
        Self {
            x: read_u32_le(&data, 0),
            y: read_u32_le(&data, 4),
            z: read_u32_le(&data, 8),
            w: read_u32_le(&data, 12),
        }
    }

    fn next_u32(&mut self) -> u32 {
        let x = self.x;
        let t = x ^ x.wrapping_shl(11);
        self.x = self.y;
        self.y = self.z;
        self.z = self.w;
        let w = self.w;
        self.w = w ^ (w >> 19) ^ (t ^ (t >> 8));
        self.w
    }
}

#[derive(Clone, Debug)]
struct PermutationTable {
    values: [usize; 256],
}

impl PermutationTable {
    fn new(seed: u32) -> Self {
        let mut rng = XorShiftRng::new(seed);
        let mut values = [0usize; 256];
        for (idx, value) in values.iter_mut().enumerate() {
            *value = idx;
        }
        for idx in (1..=255).rev() {
            let swap_idx = gen_index_u32(&mut rng, idx + 1);
            values.swap(idx, swap_idx);
        }
        Self { values }
    }

    fn hash3(&self, x: i32, y: i32, z: i32) -> usize {
        let mut index = self.values[(x & 0xFF) as usize] ^ ((y & 0xFF) as usize);
        index = self.values[index] ^ ((z & 0xFF) as usize);
        self.values[index]
    }
}

#[derive(Clone, Debug)]
struct OpenSimplex3 {
    perm: PermutationTable,
}

impl OpenSimplex3 {
    fn new(seed: u32) -> Self {
        Self {
            perm: PermutationTable::new(seed),
        }
    }

    fn get(&self, x: f64, y: f64, z: f64) -> f64 {
        let stretch_constant = -1.0 / 6.0;
        let squish_constant = 1.0 / 3.0;
        let stretch_offset = (x + y + z) * stretch_constant;
        let sx = x + stretch_offset;
        let sy = y + stretch_offset;
        let sz = z + stretch_offset;
        let sfx = noise_floor_to_isize(sx);
        let sfy = noise_floor_to_isize(sy);
        let sfz = noise_floor_to_isize(sz);
        let squish_offset = ((sfx + sfy + sfz) as f64) * squish_constant;
        let ox = sfx as f64 + squish_offset;
        let oy = sfy as f64 + squish_offset;
        let oz = sfz as f64 + squish_offset;
        let rx = sx - sfx as f64;
        let ry = sy - sfy as f64;
        let rz = sz - sfz as f64;
        let region_sum = rx + ry + rz;
        let rpx = x - ox;
        let rpy = y - oy;
        let rpz = z - oz;

        let contribute = |dx: i32, dy: i32, dz: i32| -> f64 {
            let offset_sum = dx + dy + dz;
            let px = rpx - squish_constant * offset_sum as f64 - dx as f64;
            let py = rpy - squish_constant * offset_sum as f64 - dy as f64;
            let pz = rpz - squish_constant * offset_sum as f64 - dz as f64;
            let t = 2.0 - (px * px + py * py + pz * pz);
            if t <= 0.0 {
                return 0.0;
            }
            let grad = GRAD3[self.perm.hash3(sfx + dx, sfy + dy, sfz + dz) % 32];
            t.powi(4) * (px * grad.0 + py * grad.1 + pz * grad.2)
        };

        let value = if region_sum <= 1.0 {
            contribute(0, 0, 0) + contribute(1, 0, 0) + contribute(0, 1, 0) + contribute(0, 0, 1)
        } else if region_sum >= 2.0 {
            contribute(1, 1, 0) + contribute(1, 0, 1) + contribute(0, 1, 1) + contribute(1, 1, 1)
        } else {
            contribute(1, 0, 0)
                + contribute(0, 1, 0)
                + contribute(0, 0, 1)
                + contribute(1, 1, 0)
                + contribute(1, 0, 1)
                + contribute(0, 1, 1)
        };
        value / 14.0
    }
}

fn gen_index_u32(rng: &mut XorShiftRng, ubound: usize) -> usize {
    sample_single_u32(rng, 0, ubound as u32) as usize
}

fn sample_single_u32(rng: &mut XorShiftRng, low: u32, high: u32) -> u32 {
    sample_u32_exclusive(low, high, || rng.next_u32())
}

fn sample_u32_exclusive<F>(low: u32, high: u32, mut next_u32: F) -> u32
where
    F: FnMut() -> u32,
{
    assert!(low < high);
    let range_value = high - low;
    let bit_length = 32 - range_value.leading_zeros();
    let zone = (((range_value as u64) << (32 - bit_length)) - 1) as u32;
    loop {
        let value = next_u32();
        let product = value as u64 * range_value as u64;
        let hi = (product >> 32) as u32;
        let lo = product as u32;
        if lo <= zone {
            return low + hi;
        }
    }
}

fn read_u32_le(data: &[u8], offset: usize) -> u32 {
    data[offset] as u32
        | ((data[offset + 1] as u32) << 8)
        | ((data[offset + 2] as u32) << 16)
        | ((data[offset + 3] as u32) << 24)
}

fn noise_floor_to_isize(value: f64) -> i32 {
    if value <= 0.0 {
        value as i32 - 1
    } else {
        value as i32
    }
}

fn chacha_seed_from_u64(seed: u64) -> [u32; 16] {
    let mut state = seed as u128;
    let mut data = vec![];
    for _ in 0..8 {
        state = (state * 6364136223846793005u128 + 11634580027462260723u128) & U64_MASK;
        let xorshifted = (((state >> 18) ^ state) >> 27) as u32;
        let rot = ((state >> 59) & 31) as u32;
        let value = xorshifted.rotate_right(rot);
        data.extend([
            (value & 0xFF) as u8,
            ((value >> 8) & 0xFF) as u8,
            ((value >> 16) & 0xFF) as u8,
            ((value >> 24) & 0xFF) as u8,
        ]);
    }
    let mut key = [0u32; 8];
    for (idx, slot) in key.iter_mut().enumerate() {
        *slot = read_u32_le(&data, idx * 4);
    }
    [
        0x61707865, 0x3320646E, 0x79622D32, 0x6B206574, key[0], key[1], key[2], key[3], key[4],
        key[5], key[6], key[7], 0, 0, 0, 0,
    ]
}

fn chacha_double_round(state: &mut [u32; 16]) {
    quarter_round(state, 0, 4, 8, 12);
    quarter_round(state, 1, 5, 9, 13);
    quarter_round(state, 2, 6, 10, 14);
    quarter_round(state, 3, 7, 11, 15);
    quarter_round(state, 0, 5, 10, 15);
    quarter_round(state, 1, 6, 11, 12);
    quarter_round(state, 2, 7, 8, 13);
    quarter_round(state, 3, 4, 9, 14);
}

fn quarter_round(state: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize) {
    state[a] = state[a].wrapping_add(state[b]);
    state[d] = (state[d] ^ state[a]).rotate_left(16);
    state[c] = state[c].wrapping_add(state[d]);
    state[b] = (state[b] ^ state[c]).rotate_left(12);
    state[a] = state[a].wrapping_add(state[b]);
    state[d] = (state[d] ^ state[a]).rotate_left(8);
    state[c] = state[c].wrapping_add(state[d]);
    state[b] = (state[b] ^ state[c]).rotate_left(7);
}

fn scenario_to_task(entry: &Value) -> Value {
    if let Some(task) = entry.get("task") {
        return task.clone();
    }
    let mut task = json!({
        "schema": "gamebench.task.crafter.v1",
        "task_id": entry.get("scenario_id").and_then(Value::as_str).unwrap_or("crafter_manual"),
        "scenario_id": entry.get("scenario_id").and_then(Value::as_str).unwrap_or("crafter_manual"),
        "world": entry.get("world").cloned().unwrap_or_else(|| json!({"use_default": "policy_dev_small", "seed": entry.get("seed").and_then(Value::as_u64).unwrap_or(101)})),
        "rules": entry.get("rules").cloned().unwrap_or_else(|| json!({"base": "no_homeostasis"})),
        "readouts": entry.get("readouts").cloned().unwrap_or_else(|| json!({"symbolic": "symbolic_compact", "visual": false})),
        "checkpoint_every_n_steps": entry.get("checkpoint_every_n_steps").and_then(Value::as_u64).unwrap_or(10)
    });
    for key in ["stream", "monty_reward", "agent_policy"] {
        if let Some(value) = entry.get(key) {
            task[key] = value.clone();
        }
    }
    task
}

fn resolve_task(task: &Value) -> Value {
    let mut world = resolve_world(task.get("world").unwrap_or(&json!({})));
    let rules = resolve_rules(task.get("rules").unwrap_or(&json!({})));
    let width = positive_rule_u64(world.get("width"), 64, "world.width");
    let height = positive_rule_u64(world.get("height"), 64, "world.height");
    let view_radius = nonnegative_rule_u64(world.get("view_radius"), 4, "world.view_radius");
    let max_steps = positive_rule_u64(
        task.get("max_steps").or_else(|| world.get("max_steps")),
        10000,
        "max_steps",
    );
    if world.get("tiles").is_some() && world.get("map").is_some() {
        panic!("world.tiles and world.map are mutually exclusive");
    }
    if let Some(tiles) = world.get("tiles").cloned() {
        if let Some(obj) = world.as_object_mut() {
            obj.remove("tiles");
        }
        world["map"] = normalize_world_map(&json!({"rows": tiles}), width, height, &rules);
    } else if let Some(map) = world.get("map").cloned() {
        world["map"] = normalize_world_map(&map, width, height, &rules);
    }
    if let Some(initial_state) = world.get("initial_state").cloned() {
        world["initial_state"] = normalize_initial_state(&initial_state, width, height, max_steps);
    }
    if let Some(map) = world.get("map") {
        validate_authored_map_profile(map, &rules);
    }
    let seed = world.get("seed").and_then(Value::as_u64).unwrap_or(0);
    let task_id = task
        .get("task_id")
        .and_then(Value::as_str)
        .unwrap_or("crafter_manual");
    let scenario_id = task
        .get("scenario_id")
        .and_then(Value::as_str)
        .unwrap_or(task_id);
    let readouts = resolve_readouts(
        task.get("readouts")
            .unwrap_or(&json!({"symbolic": "symbolic_compact", "visual": false})),
    );
    let substrate_profile = rules
        .get("substrate_profile")
        .and_then(Value::as_str)
        .or_else(|| {
            world
                .get("worldgen")
                .and_then(|value| value.get("profile"))
                .and_then(Value::as_str)
        })
        .unwrap_or("classic");
    if !matches!(substrate_profile, "classic" | "craftax_partial") {
        panic!(
            "unsupported native Rust Crafter substrate_profile: {}",
            substrate_profile
        );
    }
    let mut substrate_config = json!({
        "world_width": width,
        "world_height": height,
        "view_radius": view_radius,
        "max_steps": max_steps,
        "profile": if substrate_profile == "classic" { Value::Null } else { json!(substrate_profile) },
        "full_world_state": readouts.get("full_world_state").and_then(Value::as_bool).unwrap_or(false)
    });
    if let Some(config) = substrate_config.as_object_mut() {
        let survival = rules.get("survival").unwrap_or(&Value::Null);
        let day_night = rules.get("day_night").unwrap_or(&Value::Null);
        for key in WORLDGEN_DENSITY_KEYS {
            config.insert(key.to_string(), json!(worldgen_density(&world, key)));
        }
        config.insert(
            "hunger_enabled".to_string(),
            json!(rule_bool(
                survival.get("hunger_enabled"),
                true,
                "rules.survival.hunger_enabled"
            )),
        );
        config.insert(
            "thirst_enabled".to_string(),
            json!(rule_bool(
                survival.get("thirst_enabled"),
                true,
                "rules.survival.thirst_enabled"
            )),
        );
        config.insert(
            "fatigue_enabled".to_string(),
            json!(rule_bool(
                survival.get("fatigue_enabled"),
                true,
                "rules.survival.fatigue_enabled"
            )),
        );
        config.insert(
            "health_enabled".to_string(),
            json!(rule_bool(
                survival.get("health_enabled"),
                true,
                "rules.survival.health_enabled"
            )),
        );
        if survival.get("hunger_rate").is_some() {
            config.insert(
                "hunger_rate".to_string(),
                json!(positive_rule_u64(
                    survival.get("hunger_rate"),
                    25,
                    "rules.survival.hunger_rate"
                )),
            );
        }
        if survival.get("thirst_rate").is_some() {
            config.insert(
                "thirst_rate".to_string(),
                json!(positive_rule_u64(
                    survival.get("thirst_rate"),
                    20,
                    "rules.survival.thirst_rate"
                )),
            );
        }
        config.insert(
            "day_night_cycle".to_string(),
            json!(rule_bool(
                day_night.get("enabled"),
                true,
                "rules.day_night.enabled"
            )),
        );
        config.insert(
            "day_cycle_period".to_string(),
            json!(positive_rule_u64(
                rules.get("day_night").and_then(|value| value.get("period")),
                300,
                "rules.day_night.period"
            )),
        );
        let mobs = rules.get("mobs").unwrap_or(&Value::Null);
        let mobs_enabled = rule_bool(mobs.get("enabled"), true, "rules.mobs.enabled");
        config.insert("mobs_enabled".to_string(), json!(mobs_enabled));
        config.insert(
            "zombie_spawn_rate".to_string(),
            json!(if mobs_enabled {
                nonnegative_rule_number(
                    mobs.get("zombie_spawn_rate"),
                    0.3,
                    "rules.mobs.zombie_spawn_rate",
                )
            } else {
                0.0
            }),
        );
        config.insert(
            "cow_spawn_rate".to_string(),
            json!(if mobs_enabled {
                nonnegative_rule_number(
                    mobs.get("cow_spawn_rate"),
                    0.01,
                    "rules.mobs.cow_spawn_rate",
                )
            } else {
                0.0
            }),
        );
        for (key, default) in [
            ("zombie_despawn_rate", 0.4),
            ("cow_despawn_rate", 0.01),
            ("zombie_damage_mult", 1.0),
            ("arrow_damage_mult", 1.0),
            ("player_damage_mult", 1.0),
        ] {
            if mobs.get(key).is_some() {
                config.insert(
                    key.to_string(),
                    json!(nonnegative_rule_number(
                        mobs.get(key),
                        default,
                        &format!("rules.mobs.{}", key),
                    )),
                );
            }
        }
        for (key, default) in [
            ("cow_health", default_entity_health("cow")),
            ("zombie_health", default_entity_health("zombie")),
            ("skeleton_health", default_entity_health("skeleton")),
            ("orc_soldier_health", default_entity_health("orc_soldier")),
            ("orc_mage_health", default_entity_health("orc_mage")),
            ("knight_health", default_entity_health("knight")),
            (
                "knight_archer_health",
                default_entity_health("knight_archer"),
            ),
            ("troll_health", default_entity_health("troll")),
            ("bat_health", default_entity_health("bat")),
            ("snail_health", default_entity_health("snail")),
        ] {
            if mobs.get(key).is_some() {
                config.insert(
                    key.to_string(),
                    json!(entity_health_rule(
                        mobs.get(key),
                        default,
                        &format!("rules.mobs.{}", key),
                    )),
                );
            }
        }
    }
    let adapter_hooks = adapter_hooks();
    let unsupported_rules = unsupported_rules(&world, &rules, &adapter_hooks, substrate_profile);
    let has_unsupported_rules = unsupported_rules
        .as_array()
        .map(|items| !items.is_empty())
        .unwrap_or(false);
    if has_unsupported_rules
        && rules
            .get("strict_rule_support")
            .and_then(Value::as_bool)
            .unwrap_or(false)
    {
        let joined = unsupported_rules
            .as_array()
            .unwrap()
            .iter()
            .filter_map(Value::as_str)
            .collect::<Vec<_>>()
            .join(", ");
        panic!(
            "resolved task requires unsupported native Crafter rule knobs: {}",
            joined
        );
    }
    let mut stream = json!({"enabled": false, "every_n_steps": 1, "persist_frames": false});
    if let Some(raw_stream) = task.get("stream") {
        merge_value(&mut stream, raw_stream);
    }
    let checkpoint_every_n_steps = nonnegative_rule_u64(
        task.get("checkpoint_every_n_steps"),
        10,
        "checkpoint_every_n_steps",
    );
    let monty_reward_raw = resolve_monty_reward(task.get("monty_reward"));
    let (patched_rules, monty_reward, reward_mode, objective) =
        apply_reward_mode(task, rules.clone(), monty_reward_raw);
    let resolved_without_hash = json!({
        "schema": "gamebench.task.crafter.v1",
        "task_id": task_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "reward_mode": reward_mode,
        "objective": objective,
        "world": world,
        "rules": patched_rules,
        "readouts": readouts,
        "stream": stream,
        "monty_reward": monty_reward,
        "agent_policy": task.get("agent_policy").cloned().unwrap_or(Value::Null),
        "checkpoint_every_n_steps": checkpoint_every_n_steps,
        "substrate": {
            "engine": "gamebench-native",
            "profile": substrate_profile,
            "config": substrate_config,
            "adapter_hooks": adapter_hooks,
            "unsupported_rules": unsupported_rules
        }
    });
    let config_hash = format!(
        "sha256:{:x}",
        Sha256::digest(canonical_json(&resolved_without_hash))
    );
    let mut resolved_json = resolved_without_hash;
    resolved_json["config_hash"] = Value::String(config_hash.clone());
    json!({
        "task_id": task_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "reward_mode": resolved_json["reward_mode"].clone(),
        "objective": resolved_json["objective"].clone(),
        "width": width,
        "height": height,
        "view_radius": view_radius,
        "max_steps": max_steps,
        "world": resolved_json["world"].clone(),
        "rules": resolved_json["rules"].clone(),
        "readouts": resolved_json["readouts"].clone(),
        "stream": resolved_json["stream"].clone(),
        "monty_reward": resolved_json["monty_reward"].clone(),
        "checkpoint_every_n_steps": checkpoint_every_n_steps,
        "substrate_profile": substrate_profile,
        "substrate_config": resolved_json["substrate"]["config"].clone(),
        "adapter_hooks": resolved_json["substrate"]["adapter_hooks"].clone(),
        "unsupported_rules": resolved_json["substrate"]["unsupported_rules"].clone(),
        "config_hash": config_hash,
        "resolved_json": resolved_json
    })
}

fn resolve_world(raw: &Value) -> Value {
    let default_ref = raw.get("use_default").and_then(Value::as_str).or_else(|| {
        if raw.get("width").is_none() || raw.get("height").is_none() {
            Some("classic_64")
        } else {
            None
        }
    });
    let mut world = match default_ref {
        Some("policy_dev_small") => json!({
            "seed": 101,
            "width": 32,
            "height": 32,
            "view_radius": 5,
            "max_steps": 120,
            "worldgen": {"profile": "classic", "tree_density": 1.0, "coal_density": 1.0, "iron_density": 1.0, "diamond_density": 1.0, "cow_density": 0.2, "zombie_density": 0.0, "skeleton_density": 0.0},
            "default_ref": "policy_dev_small"
        }),
        Some("classic_64") => json!({
            "seed": 0,
            "width": 64,
            "height": 64,
            "view_radius": 4,
            "max_steps": 10000,
            "worldgen": {"profile": "classic", "tree_density": 1.0, "coal_density": 1.0, "iron_density": 1.0, "diamond_density": 1.0, "cow_density": 1.0, "zombie_density": 1.0, "skeleton_density": 1.0},
            "default_ref": "classic_64"
        }),
        Some("policy_puzzle_mob_small") => json!({
            "seed": 301,
            "width": 32,
            "height": 32,
            "view_radius": 5,
            "max_steps": 120,
            "worldgen": {"profile": "classic", "tree_density": 1.0, "coal_density": 1.0, "iron_density": 1.0, "diamond_density": 1.0, "cow_density": 0.0, "zombie_density": 1.5, "skeleton_density": 1.0},
            "default_ref": "policy_puzzle_mob_small"
        }),
        Some("craftax_partial_64") => json!({
            "seed": 0,
            "width": 64,
            "height": 64,
            "view_radius": 5,
            "max_steps": 10000,
            "worldgen": {"profile": "craftax_partial", "tree_density": 1.0, "coal_density": 1.0, "iron_density": 1.0, "diamond_density": 1.0, "cow_density": 1.0, "zombie_density": 1.0, "skeleton_density": 1.0},
            "default_ref": "craftax_partial_64"
        }),
        None => raw.clone(),
        Some(other) => panic!("unsupported native Crafter world default: {}", other),
    };
    merge_value(&mut world, raw);
    if let Some(profile) = world
        .get("worldgen")
        .and_then(|value| value.get("profile"))
        .and_then(Value::as_str)
    {
        if !matches!(profile, "classic" | "craftax_partial") {
            panic!("unsupported native Crafter worldgen profile: {}", profile);
        }
    }
    if let Some(worldgen) = world.get("worldgen") {
        let worldgen = worldgen
            .as_object()
            .expect("world.worldgen must be an object");
        for key in worldgen.keys() {
            if key != "profile" && !WORLDGEN_DENSITY_KEYS.contains(&key.as_str()) {
                panic!("unsupported native Crafter world.worldgen key: {}", key);
            }
        }
    }
    world
}

fn resolve_rules(raw: &Value) -> Value {
    let base = raw.get("base").and_then(Value::as_str).unwrap_or("classic");
    let mut rules = match base {
        "no_homeostasis" => json!({
            "schema": "gamebench.crafter.rules.v1",
            "substrate_profile": "classic",
            "survival": {"hunger_enabled": false, "thirst_enabled": false, "fatigue_enabled": false, "health_enabled": true},
            "day_night": {"enabled": false, "period": 300},
            "mobs": {"enabled": false, "zombie_spawn_rate": 0.0, "cow_spawn_rate": 0.0},
            "crafting": {"classic_recipes": true, "craftax_recipes": false},
            "craftax": {"enabled": false},
            "rewards": {"achievement": 1.0, "invalid_action": 0.0, "death": 0.0, "step": 0.0},
            "achievements": {"enabled": "classic"},
            "strict_rule_support": false,
            "base_ref": base
        }),
        "policy_puzzle_mobs" => json!({
            "schema": "gamebench.crafter.rules.v1",
            "substrate_profile": "craftax_partial",
            "survival": {"hunger_enabled": false, "thirst_enabled": false, "fatigue_enabled": false, "health_enabled": true},
            "day_night": {"enabled": false, "period": 300},
            "mobs": {"enabled": true, "zombie_spawn_rate": 0.0, "cow_spawn_rate": 0.0},
            "crafting": {"classic_recipes": true, "craftax_recipes": true},
            "craftax": {
                "enabled": true,
                "mobs_enabled": true,
                "combat_enabled": true,
                "worldgen_enabled": false,
                "items_enabled": false,
                "chests_enabled": false,
                "potions_enabled": false,
                "xp_enabled": false,
                "achievements_enabled": false
            },
            "rewards": {"achievement": 1.0, "invalid_action": 0.0, "death": 0.0, "step": 0.0},
            "achievements": {"enabled": "classic_plus_craftax"},
            "strict_rule_support": false,
            "base_ref": base
        }),
        "classic" => json!({
            "schema": "gamebench.crafter.rules.v1",
            "substrate_profile": "classic",
            "survival": {"hunger_enabled": true, "thirst_enabled": true, "fatigue_enabled": true, "health_enabled": true},
            "day_night": {"enabled": true, "period": 300},
            "mobs": {"enabled": true, "zombie_spawn_rate": 0.3, "cow_spawn_rate": 0.01},
            "crafting": {"classic_recipes": true, "craftax_recipes": false},
            "craftax": {"enabled": false},
            "rewards": {"achievement": 1.0, "invalid_action": 0.0, "death": 0.0, "step": 0.0},
            "achievements": {"enabled": "classic"},
            "strict_rule_support": false,
            "base_ref": base
        }),
        "craftax_partial" => json!({
            "schema": "gamebench.crafter.rules.v1",
            "substrate_profile": "craftax_partial",
            "survival": {"hunger_enabled": true, "thirst_enabled": true, "fatigue_enabled": true, "health_enabled": true},
            "day_night": {"enabled": true, "period": 300},
            "mobs": {"enabled": true, "zombie_spawn_rate": 0.3, "cow_spawn_rate": 0.01},
            "crafting": {"classic_recipes": true, "craftax_recipes": true},
            "craftax": {
                "enabled": true,
                "mobs_enabled": true,
                "worldgen_enabled": true,
                "items_enabled": true,
                "combat_enabled": true,
                "chests_enabled": true,
                "potions_enabled": true,
                "xp_enabled": true,
                "achievements_enabled": true
            },
            "rewards": {"achievement": 1.0, "invalid_action": 0.0, "death": 0.0, "step": 0.0},
            "achievements": {"enabled": "classic_plus_craftax"},
            "strict_rule_support": false,
            "base_ref": base
        }),
        other => panic!("unsupported native Crafter rules base: {}", other),
    };
    for (key, value) in raw.as_object().into_iter().flatten() {
        if key != "base" && key != "overrides" {
            let mut patch = Map::new();
            patch.insert(key.clone(), value.clone());
            merge_value(&mut rules, &Value::Object(patch));
        }
    }
    if let Some(overrides) = raw.get("overrides") {
        merge_value(&mut rules, overrides);
    }
    validate_rule_shape(&rules);
    if rules
        .get("crafting")
        .and_then(|value| value.get("classic_recipes"))
        .and_then(Value::as_bool)
        == Some(false)
    {
        panic!("native Rust Crafter requires classic recipes");
    }
    if let Some(craftax) = rules.get("craftax").and_then(Value::as_object) {
        for key in craftax.keys() {
            if !matches!(
                key.as_str(),
                "enabled"
                    | "mobs_enabled"
                    | "worldgen_enabled"
                    | "items_enabled"
                    | "combat_enabled"
                    | "chests_enabled"
                    | "potions_enabled"
                    | "xp_enabled"
                    | "achievements_enabled"
            ) {
                panic!("native Rust Crafter does not support rules.craftax.{}", key);
            }
        }
    }
    if let Some(enabled) = rules
        .get("achievements")
        .and_then(|value| value.get("enabled"))
    {
        if !matches!(
            enabled.as_str(),
            Some("classic") | Some("classic_plus_craftax")
        ) {
            panic!(
                "native Rust Crafter supports only classic or classic_plus_craftax achievements"
            );
        }
    }
    rules["rewards"] = normalize_rule_rewards(rules.get("rewards"));
    rules["base_ref"] = Value::String(base.to_string());
    rules
}

fn validate_rule_shape(rules: &Value) {
    let obj = rules.as_object().expect("rules must be an object");
    for key in obj.keys() {
        if !matches!(
            key.as_str(),
            "schema"
                | "substrate_profile"
                | "survival"
                | "day_night"
                | "mobs"
                | "crafting"
                | "craftax"
                | "rewards"
                | "achievements"
                | "strict_rule_support"
                | "base_ref"
        ) {
            panic!("unsupported native Crafter rules key: {}", key);
        }
    }
    validate_rule_section(
        rules,
        "survival",
        &[
            "hunger_enabled",
            "thirst_enabled",
            "fatigue_enabled",
            "health_enabled",
            "hunger_rate",
            "thirst_rate",
        ],
    );
    validate_rule_section(rules, "day_night", &["enabled", "period"]);
    validate_rule_section(
        rules,
        "mobs",
        &[
            "enabled",
            "zombie_spawn_rate",
            "cow_spawn_rate",
            "zombie_despawn_rate",
            "cow_despawn_rate",
            "zombie_damage_mult",
            "arrow_damage_mult",
            "player_damage_mult",
            "cow_health",
            "zombie_health",
            "skeleton_health",
            "orc_soldier_health",
            "orc_mage_health",
            "knight_health",
            "knight_archer_health",
            "troll_health",
            "bat_health",
            "snail_health",
        ],
    );
    validate_rule_section(rules, "crafting", &["classic_recipes", "craftax_recipes"]);
    validate_rule_section(
        rules,
        "craftax",
        &[
            "enabled",
            "mobs_enabled",
            "worldgen_enabled",
            "items_enabled",
            "combat_enabled",
            "chests_enabled",
            "potions_enabled",
            "xp_enabled",
            "achievements_enabled",
        ],
    );
    validate_rule_section(
        rules,
        "rewards",
        &["achievement", "invalid_action", "death", "step"],
    );
    validate_rule_section(rules, "achievements", &["enabled"]);
}

fn validate_rule_section(rules: &Value, section: &str, allowed: &[&str]) {
    let Some(section_value) = rules.get(section) else {
        return;
    };
    let obj = section_value
        .as_object()
        .unwrap_or_else(|| panic!("rules.{} must be an object", section));
    for key in obj.keys() {
        if !allowed.contains(&key.as_str()) {
            panic!("unsupported native Crafter rules.{}.{}", section, key);
        }
    }
}

fn resolve_readouts(raw: &Value) -> Value {
    let symbolic = raw
        .as_str()
        .or_else(|| raw.get("symbolic").and_then(Value::as_str))
        .unwrap_or("symbolic_compact");
    let mut readouts = match symbolic {
        "symbolic_full" => {
            json!({"symbolic": true, "observation_text": true, "local_map": true, "full_world_state": true, "visual": false, "profile_ref": symbolic})
        }
        "rgb_tiles" => {
            json!({"symbolic": true, "observation_text": true, "local_map": true, "full_world_state": false, "visual": true, "profile_ref": symbolic})
        }
        _ => {
            json!({"symbolic": true, "observation_text": true, "local_map": true, "full_world_state": false, "visual": false, "profile_ref": symbolic})
        }
    };
    if let Some(visual) = raw.get("visual") {
        if let Some(name) = visual.as_str() {
            readouts["visual_profile_ref"] = Value::String(name.to_string());
            readouts["visual"] = Value::Bool(true);
        } else {
            readouts["visual"] = visual.clone();
        }
    }
    if let Some(obj) = raw.as_object() {
        for (key, value) in obj {
            if key != "symbolic" && key != "visual" {
                readouts[key] = value.clone();
            }
        }
    }
    readouts
}

fn adapter_hooks() -> Value {
    json!({
        "freeze_hunger": false,
        "freeze_thirst": false,
        "freeze_fatigue": false,
        "suppress_mobs": false,
        "suppress_hostile_mobs": false,
        "freeze_daylight": false
    })
}

fn unsupported_rules(
    _world: &Value,
    rules: &Value,
    _adapter_hooks: &Value,
    substrate_profile: &str,
) -> Value {
    let mut unsupported = vec![];
    if substrate_profile == "craftax_partial"
        && rules
            .get("craftax")
            .and_then(|craftax| craftax.get("enabled"))
            .and_then(Value::as_bool)
            == Some(false)
    {
        unsupported.push(Value::String(
            "craftax.enabled=false with craftax_partial substrate".to_string(),
        ));
    }
    Value::Array(unsupported)
}

fn normalize_initial_state(raw: &Value, width: u64, height: u64, max_steps: u64) -> Value {
    let obj = raw
        .as_object()
        .expect("world.initial_state must be an object");
    for key in obj.keys() {
        if !matches!(
            key.as_str(),
            "daylight" | "step" | "player" | "inventory" | "tiles" | "entities" | "achievements"
        ) {
            panic!("unsupported world.initial_state key: {}", key);
        }
    }
    let mut resolved = Map::new();
    if let Some(daylight) = obj.get("daylight") {
        resolved.insert(
            "daylight".to_string(),
            json!(normalize_daylight(daylight, "world.initial_state.daylight")),
        );
    }
    if let Some(step) = obj.get("step") {
        let step = nonnegative_rule_u64(Some(step), 0, "world.initial_state.step");
        if step >= max_steps {
            panic!(
                "world.initial_state.step must be less than max_steps ({})",
                max_steps
            );
        }
        resolved.insert("step".to_string(), json!(step));
    }
    if let Some(player_raw) = obj.get("player") {
        let player_raw = player_raw
            .as_object()
            .expect("world.initial_state.player must be an object");
        for key in player_raw.keys() {
            if !matches!(
                key.as_str(),
                "pos"
                    | "facing"
                    | "sleeping"
                    | "hunger_counter"
                    | "thirst_counter"
                    | "fatigue_counter"
                    | "recover_counter"
            ) {
                panic!("unsupported world.initial_state.player key: {}", key);
            }
        }
        let mut player = Map::new();
        if let Some(pos) = player_raw.get("pos") {
            player.insert(
                "pos".to_string(),
                normalize_position(pos, "world.initial_state.player.pos", width, height),
            );
        }
        if let Some(facing) = player_raw.get("facing") {
            player.insert(
                "facing".to_string(),
                normalize_facing(facing, "world.initial_state.player.facing"),
            );
        }
        if let Some(sleeping) = player_raw.get("sleeping") {
            player.insert(
                "sleeping".to_string(),
                json!(sleeping.as_bool().unwrap_or_else(|| panic!(
                    "world.initial_state.player.sleeping must be a boolean"
                ))),
            );
        }
        if let Some(counter) = player_raw.get("hunger_counter") {
            player.insert(
                "hunger_counter".to_string(),
                json!(nonnegative_rule_number(
                    Some(counter),
                    0.0,
                    "world.initial_state.player.hunger_counter",
                )),
            );
        }
        if let Some(counter) = player_raw.get("thirst_counter") {
            player.insert(
                "thirst_counter".to_string(),
                json!(nonnegative_rule_number(
                    Some(counter),
                    0.0,
                    "world.initial_state.player.thirst_counter",
                )),
            );
        }
        if let Some(counter) = player_raw.get("fatigue_counter") {
            player.insert(
                "fatigue_counter".to_string(),
                json!(normalize_i32_counter(
                    counter,
                    "world.initial_state.player.fatigue_counter",
                )),
            );
        }
        if let Some(counter) = player_raw.get("recover_counter") {
            player.insert(
                "recover_counter".to_string(),
                json!(finite_rule_number(
                    Some(counter),
                    0.0,
                    "world.initial_state.player.recover_counter",
                )),
            );
        }
        if !player.is_empty() {
            resolved.insert("player".to_string(), Value::Object(player));
        }
    }
    if let Some(inventory_raw) = obj.get("inventory") {
        let inventory_raw = inventory_raw
            .as_object()
            .expect("world.initial_state.inventory must be an object");
        let mut inventory = Map::new();
        let mut keys = inventory_raw.keys().collect::<Vec<_>>();
        keys.sort();
        for key in keys {
            if !is_inventory_slot(key) {
                panic!("unsupported native Crafter inventory slot: {}", key);
            }
            let canonical = canonical_inventory_key(key);
            if inventory.contains_key(canonical) {
                panic!(
                    "duplicate world.initial_state.inventory slot after alias normalization: {}",
                    canonical
                );
            }
            let amount = inventory_raw[key].as_i64().unwrap_or_else(|| {
                panic!("world.initial_state.inventory.{} must be an integer", key)
            });
            if key == "armor" {
                let max_value = inventory_limit("armor_helmet");
                if !(0..=max_value).contains(&amount) {
                    panic!(
                        "world.initial_state.inventory.{} must be between 0 and {}",
                        key, max_value
                    );
                }
                for armor_key in ARMOR_SLOTS {
                    if inventory.contains_key(armor_key) {
                        panic!(
                            "duplicate world.initial_state.inventory slot after alias normalization: {}",
                            armor_key
                        );
                    }
                    inventory.insert(armor_key.to_string(), json!(amount));
                }
                continue;
            }
            let max_value = inventory_limit(canonical) as i64;
            if !(0..=max_value).contains(&amount) {
                panic!(
                    "world.initial_state.inventory.{} must be between 0 and {}",
                    key, max_value
                );
            }
            inventory.insert(canonical.to_string(), json!(amount));
        }
        resolved.insert("inventory".to_string(), Value::Object(inventory));
    }
    if let Some(tiles_raw) = obj.get("tiles") {
        let tiles_raw = tiles_raw
            .as_array()
            .expect("world.initial_state.tiles must be an array");
        let mut tiles = vec![];
        let mut seen = BTreeSet::new();
        for (idx, patch) in tiles_raw.iter().enumerate() {
            let patch = patch
                .as_object()
                .unwrap_or_else(|| panic!("world.initial_state.tiles[{}] must be an object", idx));
            for key in patch.keys() {
                if !matches!(key.as_str(), "pos" | "kind") {
                    panic!(
                        "unsupported world.initial_state.tiles[{}] key: {}",
                        idx, key
                    );
                }
            }
            let pos = normalize_position(
                patch.get("pos").unwrap_or(&Value::Null),
                &format!("world.initial_state.tiles[{}].pos", idx),
                width,
                height,
            );
            let pos_key = value_pos(&pos);
            if !seen.insert(pos_key) {
                panic!("duplicate world.initial_state tile patch at {:?}", pos_key);
            }
            let kind = patch
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_ascii_lowercase();
            if !is_known_material(&kind) {
                panic!("unsupported native Crafter material: {}", kind);
            }
            tiles.push(json!({"pos": pos, "kind": kind}));
        }
        resolved.insert("tiles".to_string(), Value::Array(tiles));
    }
    if let Some(entities_raw) = obj.get("entities") {
        let entities_raw = entities_raw
            .as_array()
            .expect("world.initial_state.entities must be an array");
        let mut entities = vec![];
        let mut seen = BTreeSet::new();
        for (idx, entity) in entities_raw.iter().enumerate() {
            let entity = entity.as_object().unwrap_or_else(|| {
                panic!("world.initial_state.entities[{}] must be an object", idx)
            });
            let kind = entity
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_ascii_lowercase();
            if !is_entity_kind(&kind) {
                panic!("unsupported native Crafter entity kind: {}", kind);
            }
            for key in entity.keys() {
                let projectile_field = matches!(
                    key.as_str(),
                    "facing" | "damage" | "damage_source" | "projectile_kind"
                );
                if projectile_field && kind != "arrow" {
                    panic!(
                        "world.initial_state.entities[{}].{} is only supported for arrow entities",
                        idx, key
                    );
                }
                let counter_owner = match key.as_str() {
                    "grown" if kind != "plant" => Some("plant"),
                    "cooldown" if kind != "zombie" && craftax_mob_stats(&kind).is_none() => {
                        Some("zombie or Craftax mob")
                    }
                    "reload" if kind != "skeleton" => Some("skeleton"),
                    _ => None,
                };
                if let Some(owner) = counter_owner {
                    panic!(
                        "world.initial_state.entities[{}].{} is only supported for {} entities",
                        idx, key, owner
                    );
                }
                if !matches!(
                    key.as_str(),
                    "kind"
                        | "pos"
                        | "health"
                        | "facing"
                        | "damage"
                        | "damage_source"
                        | "projectile_kind"
                        | "grown"
                        | "cooldown"
                        | "reload"
                ) {
                    panic!(
                        "unsupported world.initial_state.entities[{}] key: {}",
                        idx, key
                    );
                }
            }
            let pos = normalize_position(
                entity.get("pos").unwrap_or(&Value::Null),
                &format!("world.initial_state.entities[{}].pos", idx),
                width,
                height,
            );
            let pos_key = value_pos(&pos);
            if !seen.insert(pos_key) {
                panic!("duplicate world.initial_state entity at {:?}", pos_key);
            }
            let health = entity
                .get("health")
                .and_then(Value::as_u64)
                .unwrap_or_else(|| default_entity_health(&kind));
            if health == 0 || health > MAX_ENTITY_HEALTH {
                panic!(
                    "world.initial_state.entities[{}].health must be between 1 and {}",
                    idx, MAX_ENTITY_HEALTH
                );
            }
            if kind == "arrow" {
                let facing = normalize_facing(
                    entity.get("facing").unwrap_or_else(|| {
                        panic!(
                            "world.initial_state.entities[{}].facing is required for arrow entities",
                            idx
                        )
                    }),
                    &format!("world.initial_state.entities[{}].facing", idx),
                );
                let damage = entity
                    .get("damage")
                    .map(|value| {
                        value.as_u64().unwrap_or_else(|| {
                            panic!(
                                "world.initial_state.entities[{}].damage must be a nonnegative integer",
                                idx
                            )
                        })
                    })
                    .unwrap_or(2);
                if damage > 255 {
                    panic!(
                        "world.initial_state.entities[{}].damage must be between 0 and 255",
                        idx
                    );
                }
                let damage_source = entity
                    .get("damage_source")
                    .map(|value| {
                        value.as_str().unwrap_or_else(|| {
                            panic!(
                                "world.initial_state.entities[{}].damage_source must be a string",
                                idx
                            )
                        })
                    })
                    .unwrap_or("arrow");
                if !matches!(
                    damage_source,
                    "arrow" | "player_arrow" | "craftax_ranged" | "craftax_magic"
                ) {
                    panic!(
                        "world.initial_state.entities[{}].damage_source must be 'arrow', 'player_arrow', 'craftax_ranged', or 'craftax_magic'",
                        idx
                    );
                }
                let projectile_kind = entity
                    .get("projectile_kind")
                    .map(|value| {
                        value.as_str().unwrap_or_else(|| {
                            panic!(
                                "world.initial_state.entities[{}].projectile_kind must be a string",
                                idx
                            )
                        })
                    })
                    .unwrap_or("arrow")
                    .to_ascii_lowercase();
                if !is_projectile_kind(&projectile_kind) {
                    panic!(
                        "world.initial_state.entities[{}].projectile_kind is unsupported: {}",
                        idx, projectile_kind
                    );
                }
                validate_projectile_kind_for_damage_source(
                    &projectile_kind,
                    damage_source,
                    &format!("world.initial_state.entities[{}]", idx),
                );
                entities.push(json!({
                    "kind": kind,
                    "pos": pos,
                    "health": health,
                    "facing": facing,
                    "damage": damage as i64,
                    "damage_source": damage_source,
                    "projectile_kind": projectile_kind,
                }));
            } else {
                let mut payload = json!({"kind": kind, "pos": pos, "health": health});
                for key in ["grown", "cooldown", "reload"] {
                    if let Some(value) = entity.get(key) {
                        payload[key] = json!(normalize_entity_counter(
                            value,
                            &format!("world.initial_state.entities[{}].{}", idx, key),
                        ));
                    }
                }
                entities.push(payload);
            }
        }
        resolved.insert("entities".to_string(), Value::Array(entities));
    }
    if let Some(achievements_raw) = obj.get("achievements") {
        let achievements_raw = achievements_raw
            .as_object()
            .expect("world.initial_state.achievements must be an object");
        let mut achievements = Map::new();
        let mut keys = achievements_raw.keys().collect::<Vec<_>>();
        keys.sort();
        for key in keys {
            if !is_achievement_slot(key) {
                panic!("unsupported native Crafter achievement: {}", key);
            }
            let canonical = canonical_achievement_key(key);
            if achievements.contains_key(canonical) {
                panic!(
                    "duplicate world.initial_state.achievements key after alias normalization: {}",
                    canonical
                );
            }
            let amount = achievements_raw[key].as_i64().unwrap_or_else(|| {
                panic!(
                    "world.initial_state.achievements.{} must be an integer",
                    key
                )
            });
            if amount < 0 {
                panic!("world.initial_state.achievements.{} must be >= 0", key);
            }
            achievements.insert(canonical.to_string(), json!(amount));
        }
        resolved.insert("achievements".to_string(), Value::Object(achievements));
    }
    Value::Object(resolved)
}

fn normalize_daylight(raw: &Value, field: &str) -> f64 {
    let value = finite_rule_number(Some(raw), 1.0, field);
    if !(0.0..=1.0).contains(&value) {
        panic!("{} must be between 0.0 and 1.0", field);
    }
    value
}

fn normalize_world_map(raw: &Value, width: u64, height: u64, rules: &Value) -> Value {
    let obj = raw.as_object().expect("world.map must be an object");
    for key in obj.keys() {
        if !matches!(key.as_str(), "rows" | "tiles" | "legend") {
            panic!("unsupported world.map key: {}", key);
        }
    }
    if obj.contains_key("rows") && obj.contains_key("tiles") {
        panic!("world.map.rows and world.map.tiles are mutually exclusive");
    }
    let rows = obj
        .get("rows")
        .or_else(|| obj.get("tiles"))
        .unwrap_or_else(|| panic!("world.map requires rows or tiles"))
        .as_array()
        .expect("world.map rows must be an array");
    if rows.len() != height as usize {
        panic!("world.map must have exactly {} rows", height);
    }
    let mut legend = default_world_map_legend();
    if let Some(legend_raw) = obj.get("legend") {
        let legend_raw = legend_raw
            .as_object()
            .expect("world.map.legend must be an object");
        for (key, value) in legend_raw {
            if key.chars().count() != 1 {
                panic!("world.map.legend keys must be single-character strings");
            }
            let material = value
                .as_str()
                .unwrap_or_else(|| panic!("world.map.legend.{} must be a material string", key))
                .to_ascii_lowercase();
            if !is_known_material(&material) {
                panic!("unsupported world.map.legend material: {}", material);
            }
            if !material_allowed_for_rules(&material, rules) {
                panic!(
                    "world.map.legend material {} is unsupported for substrate profile {}",
                    material,
                    substrate_profile_from_rules(rules)
                );
            }
            legend.insert(key.clone(), material);
        }
    }

    let mut normalized_rows = vec![];
    for (y, row) in rows.iter().enumerate() {
        if let Some(row) = row.as_str() {
            let symbols = row.chars().collect::<Vec<_>>();
            if symbols.len() != width as usize {
                panic!("world.map row {} must be exactly {} characters", y, width);
            }
            let mut normalized = vec![];
            for (x, symbol) in symbols.into_iter().enumerate() {
                let key = symbol.to_string();
                let material = legend.get(&key).unwrap_or_else(|| {
                    panic!("world.map.rows[{}][{}] has no legend entry: {}", y, x, key)
                });
                normalized.push(Value::String(material.clone()));
            }
            normalized_rows.push(Value::Array(normalized));
            continue;
        }
        let row = row
            .as_array()
            .unwrap_or_else(|| panic!("world.map row {} must be a string or array", y));
        if row.len() != width as usize {
            panic!("world.map row {} must have exactly {} columns", y, width);
        }
        let mut normalized = vec![];
        for (x, cell) in row.iter().enumerate() {
            normalized.push(Value::String(normalize_world_map_cell(
                cell, &legend, y, x, rules,
            )));
        }
        normalized_rows.push(Value::Array(normalized));
    }
    json!({
        "encoding": "gamebench.crafter.world_map.v1",
        "tiles": normalized_rows
    })
}

fn default_world_map_legend() -> BTreeMap<String, String> {
    DEFAULT_WORLD_MAP_LEGEND
        .iter()
        .map(|(key, value)| ((*key).to_string(), (*value).to_string()))
        .collect()
}

fn normalize_world_map_cell(
    cell: &Value,
    legend: &BTreeMap<String, String>,
    y: usize,
    x: usize,
    rules: &Value,
) -> String {
    let cell = cell.as_str().unwrap_or_else(|| {
        panic!(
            "world.map.rows[{}][{}] must be a material name or symbol",
            y, x
        )
    });
    let material = cell.to_ascii_lowercase();
    if is_known_material(&material) {
        if !material_allowed_for_rules(&material, rules) {
            panic!(
                "world.map.rows[{}][{}] material {} is unsupported for substrate profile {}",
                y,
                x,
                material,
                substrate_profile_from_rules(rules)
            );
        }
        return material;
    }
    if cell.chars().count() == 1 {
        if let Some(material) = legend.get(cell) {
            if !material_allowed_for_rules(material, rules) {
                panic!(
                    "world.map.rows[{}][{}] material {} is unsupported for substrate profile {}",
                    y,
                    x,
                    material,
                    substrate_profile_from_rules(rules)
                );
            }
            return material.clone();
        }
    }
    panic!(
        "unsupported world.map.rows[{}][{}] material: {}",
        y, x, cell
    );
}

fn validate_authored_map_profile(map: &Value, rules: &Value) {
    let tiles = map
        .get("tiles")
        .and_then(Value::as_array)
        .unwrap_or_else(|| panic!("world.map.tiles must be an array"));
    for (y, row) in tiles.iter().enumerate() {
        let row = row
            .as_array()
            .unwrap_or_else(|| panic!("world.map row {} must be an array", y));
        for (x, cell) in row.iter().enumerate() {
            let material = cell.as_str().unwrap_or_else(|| {
                panic!("world.map.tiles[{}][{}] must be a material string", y, x)
            });
            if !material_allowed_for_rules(material, rules) {
                panic!(
                    "world.map.tiles[{}][{}] is {} while profile disallows Craftax terrain",
                    y, x, material
                );
            }
        }
    }
}

fn normalize_position(raw: &Value, field: &str, width: u64, height: u64) -> Value {
    let items = raw
        .as_array()
        .unwrap_or_else(|| panic!("{} must be a two-item [x, y] array", field));
    if items.len() != 2 {
        panic!("{} must be a two-item [x, y] array", field);
    }
    let x = items[0]
        .as_u64()
        .unwrap_or_else(|| panic!("{}[0] must be a nonnegative integer", field));
    let y = items[1]
        .as_u64()
        .unwrap_or_else(|| panic!("{}[1] must be a nonnegative integer", field));
    if x >= width || y >= height {
        panic!("{} must be within world bounds", field);
    }
    json!([x, y])
}

fn normalize_facing(raw: &Value, field: &str) -> Value {
    let items = raw
        .as_array()
        .unwrap_or_else(|| panic!("{} must be a two-item [dx, dy] array", field));
    if items.len() != 2 {
        panic!("{} must be a two-item [dx, dy] array", field);
    }
    let dx = items[0]
        .as_i64()
        .unwrap_or_else(|| panic!("{}[0] must be an integer", field));
    let dy = items[1]
        .as_i64()
        .unwrap_or_else(|| panic!("{}[1] must be an integer", field));
    if !matches!((dx, dy), (-1, 0) | (1, 0) | (0, -1) | (0, 1)) {
        panic!("{} must be one of [1,0], [-1,0], [0,1], or [0,-1]", field);
    }
    json!([dx, dy])
}

fn normalize_entity_counter(raw: &Value, field: &str) -> i64 {
    let value = raw
        .as_u64()
        .unwrap_or_else(|| panic!("{} must be a nonnegative integer", field));
    if value > i32::MAX as u64 {
        panic!("{} must be <= {}", field, i32::MAX);
    }
    value as i64
}

fn normalize_i32_counter(raw: &Value, field: &str) -> i32 {
    let value = raw
        .as_i64()
        .unwrap_or_else(|| panic!("{} must be an integer", field));
    if value < i32::MIN as i64 || value > i32::MAX as i64 {
        panic!("{} must be between {} and {}", field, i32::MIN, i32::MAX);
    }
    value as i32
}

fn resolve_monty_reward(raw: Option<&Value>) -> Value {
    let Some(raw) = raw else {
        return Value::Null;
    };
    let obj = raw.as_object().expect("monty_reward must be an object");
    for key in obj.keys() {
        if !matches!(
            key.as_str(),
            "kind"
                | "default_ref"
                | "use_default"
                | "module"
                | "entry"
                | "achievement_default"
                | "achievement_rewards"
                | "resource_rewards"
                | "action_penalties"
        ) {
            panic!("unsupported monty_reward key: {}", key);
        }
    }

    let mut default_name = obj
        .get("use_default")
        .and_then(Value::as_str)
        .map(str::to_string);
    if default_name.is_none() {
        if let Some(module) = obj.get("module").and_then(Value::as_str) {
            if is_monty_module(module) {
                default_name = Some(module.to_string());
            }
        }
    }
    let mut source = if let Some(name) = default_name.as_deref() {
        monty_default_spec(name)
    } else {
        raw.clone()
    };
    if let Some(default_name) = default_name {
        let mut overrides = Map::new();
        for (key, value) in obj {
            if key != "use_default" {
                overrides.insert(key.clone(), value.clone());
            }
        }
        merge_value(&mut source, &Value::Object(overrides));
        source["default_ref"] = json!(default_name);
    }

    let kind = source
        .get("kind")
        .and_then(Value::as_str)
        .unwrap_or("monty_python");
    if kind != "monty_python" {
        panic!("unsupported monty_reward.kind: {}", kind);
    }
    let entry = source
        .get("entry")
        .and_then(Value::as_str)
        .unwrap_or("score_transition");
    if entry != "score_transition" {
        panic!("unsupported monty_reward.entry: {}", entry);
    }

    let mut resolved = Map::new();
    resolved.insert("kind".to_string(), json!(kind));
    resolved.insert("entry".to_string(), json!(entry));
    if let Some(default_ref) = source.get("default_ref").and_then(Value::as_str) {
        resolved.insert("default_ref".to_string(), json!(default_ref));
    }
    if let Some(module) = source.get("module").and_then(Value::as_str) {
        if !is_monty_module(module) {
            panic!("unsupported monty_reward.module: {}", module);
        }
        resolved.insert("module".to_string(), json!(module));
    }
    if let Some(default) = source.get("achievement_default").and_then(Value::as_f64) {
        resolved.insert("achievement_default".to_string(), json!(default));
    }
    for section in [
        "achievement_rewards",
        "resource_rewards",
        "action_penalties",
    ] {
        if let Some(values) = source.get(section) {
            let values = values
                .as_object()
                .unwrap_or_else(|| panic!("monty_reward.{} must be an object", section));
            let mut section_values = Map::new();
            let mut keys = values.keys().collect::<Vec<_>>();
            keys.sort();
            for key in keys {
                if !monty_section_key_allowed(section, key) {
                    panic!("unsupported monty_reward.{} key: {}", section, key);
                }
                let value = values[key]
                    .as_f64()
                    .unwrap_or_else(|| panic!("monty_reward.{}.{} must be a number", section, key));
                if !value.is_finite() {
                    panic!("monty_reward.{}.{} must be finite", section, key);
                }
                let resolved_key = if section == "resource_rewards" {
                    canonical_inventory_key(key)
                } else {
                    key.as_str()
                };
                if section_values.contains_key(resolved_key) {
                    panic!(
                        "duplicate monty_reward.{} key after alias normalization: {}",
                        section, resolved_key
                    );
                }
                section_values.insert(resolved_key.to_string(), json!(value));
            }
            resolved.insert(section.to_string(), Value::Object(section_values));
        }
    }
    Value::Object(resolved)
}

fn apply_reward_mode(
    task: &Value,
    mut rules: Value,
    monty_reward: Value,
) -> (Value, Value, String, Value) {
    let reward_mode = task
        .get("reward_mode")
        .and_then(Value::as_str)
        .unwrap_or("standard")
        .to_string();
    if reward_mode != "standard" && reward_mode != "goal_binary" {
        panic!("unsupported reward_mode: {}", reward_mode);
    }
    let objective = task
        .get("objective")
        .and_then(Value::as_str)
        .map(str::to_string);
    if reward_mode == "standard" {
        return (
            rules,
            monty_reward,
            reward_mode,
            objective.map(Value::String).unwrap_or(Value::Null),
        );
    }
    let objective =
        objective.unwrap_or_else(|| panic!("reward_mode goal_binary requires objective"));
    if !is_achievement_slot(&objective) {
        panic!("unsupported objective: {}", objective);
    }
    if let Some(rewards) = rules.get_mut("rewards").and_then(Value::as_object_mut) {
        rewards.insert("achievement".to_string(), json!(0.0));
    }
    let mut patched_monty = if monty_reward.is_null() {
        resolve_monty_reward(Some(&json!({"use_default": "goal_binary_v1"})))
    } else {
        monty_reward
    };
    patched_monty["achievement_default"] = json!(0.0);
    if patched_monty
        .get("achievement_rewards")
        .and_then(Value::as_object)
        .is_none()
    {
        patched_monty["achievement_rewards"] = json!({});
    }
    if let Some(rewards) = patched_monty
        .get_mut("achievement_rewards")
        .and_then(Value::as_object_mut)
    {
        rewards.insert(objective.clone(), json!(1.0));
    }
    let patched_monty = resolve_monty_reward(Some(&patched_monty));
    (rules, patched_monty, reward_mode, Value::String(objective))
}

fn monty_default_spec(name: &str) -> Value {
    match name {
        "collect_wood_shaped_v1" => json!({
            "kind": "monty_python",
            "module": "collect_wood_shaped_v1",
            "entry": "score_transition",
            "achievement_rewards": {
                "collect_wood": 0.25,
                "place_table": 0.4,
                "make_wood_pickaxe": 0.5,
                "collect_stone": 0.25
            },
            "resource_rewards": {
                "wood": 0.02,
                "stone": 0.02
            },
            "action_penalties": {
                "unknown_action": -0.5
            }
        }),
        "achievement_ladder_v1" => json!({
            "kind": "monty_python",
            "module": "achievement_ladder_v1",
            "entry": "score_transition",
            "achievement_default": 0.25,
            "action_penalties": {
                "unknown_action": -0.5
            }
        }),
        "sparse_classic" => json!({
            "kind": "monty_python",
            "module": "sparse_classic",
            "entry": "score_transition",
            "achievement_default": 1.0
        }),
        "goal_binary_v1" => json!({
            "kind": "monty_python",
            "module": "goal_binary_v1",
            "entry": "score_transition",
            "achievement_default": 0.0
        }),
        other => panic!("unsupported monty_reward.use_default: {}", other),
    }
}

fn is_monty_module(module: &str) -> bool {
    matches!(
        module,
        "collect_wood_shaped_v1" | "achievement_ladder_v1" | "sparse_classic" | "goal_binary_v1"
    )
}

fn monty_section_key_allowed(section: &str, key: &str) -> bool {
    match section {
        "achievement_rewards" => is_achievement_slot(key),
        "resource_rewards" => is_inventory_slot(key),
        "action_penalties" => matches!(key, "unknown_action" | "terminal"),
        _ => false,
    }
}

fn normalize_rule_rewards(raw: Option<&Value>) -> Value {
    let obj = raw.and_then(Value::as_object);
    let mut values = Map::new();
    for (key, default) in [
        ("achievement", 1.0),
        ("invalid_action", 0.0),
        ("death", 0.0),
        ("step", 0.0),
    ] {
        values.insert(
            key.to_string(),
            json!(finite_rule_number(
                obj.and_then(|items| items.get(key)),
                default,
                &format!("rules.rewards.{}", key),
            )),
        );
    }
    Value::Object(values)
}

fn worldgen_density(world: &Value, key: &str) -> f64 {
    nonnegative_rule_number(
        world.get("worldgen").and_then(|value| value.get(key)),
        1.0,
        &format!("world.worldgen.{}", key),
    )
}

fn finite_rule_number(raw: Option<&Value>, default: f64, field: &str) -> f64 {
    let Some(raw) = raw else {
        return default;
    };
    let value = raw
        .as_f64()
        .unwrap_or_else(|| panic!("{} must be a finite number", field));
    if !value.is_finite() {
        panic!("{} must be a finite number", field);
    }
    value
}

fn nonnegative_rule_number(raw: Option<&Value>, default: f64, field: &str) -> f64 {
    let value = finite_rule_number(raw, default, field);
    if value < 0.0 {
        panic!("{} must be nonnegative", field);
    }
    value
}

fn rule_bool(raw: Option<&Value>, default: bool, field: &str) -> bool {
    let Some(raw) = raw else {
        return default;
    };
    raw.as_bool()
        .unwrap_or_else(|| panic!("{} must be a boolean", field))
}

fn craftax_rule_bool(craftax_config: &Value, key: &str, default: bool) -> bool {
    let field = format!("rules.craftax.{}", key);
    rule_bool(craftax_config.get(key), default, &field)
}

fn positive_rule_u64(raw: Option<&Value>, default: u64, field: &str) -> u64 {
    let Some(raw) = raw else {
        return default;
    };
    let value = raw
        .as_u64()
        .unwrap_or_else(|| panic!("{} must be a positive integer", field));
    if value == 0 {
        panic!("{} must be a positive integer", field);
    }
    value
}

fn nonnegative_rule_u64(raw: Option<&Value>, default: u64, field: &str) -> u64 {
    let Some(raw) = raw else {
        return default;
    };
    raw.as_u64()
        .unwrap_or_else(|| panic!("{} must be a nonnegative integer", field))
}

fn entity_health_rule(raw: Option<&Value>, default: u64, field: &str) -> u64 {
    let value = positive_rule_u64(raw, default, field);
    if value > MAX_ENTITY_HEALTH {
        panic!("{} must be <= {}", field, MAX_ENTITY_HEALTH);
    }
    value
}

fn merge_value(target: &mut Value, source: &Value) {
    match (target, source) {
        (Value::Object(dst), Value::Object(src)) => {
            for (key, value) in src {
                if key == "use_default" || key == "base" {
                    continue;
                }
                merge_value(dst.entry(key).or_insert(Value::Null), value);
            }
        }
        (target_slot, source_value) => *target_slot = source_value.clone(),
    }
}

fn canonical_json(value: &Value) -> Vec<u8> {
    canonical_string(value).into_bytes()
}

fn canonical_string(value: &Value) -> String {
    match value {
        Value::Null => "null".to_string(),
        Value::Bool(v) => v.to_string(),
        Value::Number(v) => v.to_string(),
        Value::String(v) => serde_json::to_string(v).unwrap(),
        Value::Array(items) => format!(
            "[{}]",
            items
                .iter()
                .map(canonical_string)
                .collect::<Vec<_>>()
                .join(",")
        ),
        Value::Object(map) => {
            let mut keys = map.keys().collect::<Vec<_>>();
            keys.sort();
            let inner = keys
                .into_iter()
                .map(|key| {
                    format!(
                        "{}:{}",
                        serde_json::to_string(key).unwrap(),
                        canonical_string(&map[key])
                    )
                })
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{}}}", inner)
        }
    }
}

fn normalize_action(action: &str) -> String {
    match action.trim().to_lowercase().replace(' ', "_").as_str() {
        "up" => "move_up".to_string(),
        "down" => "move_down".to_string(),
        "left" => "move_left".to_string(),
        "right" => "move_right".to_string(),
        "wait" => "noop".to_string(),
        "shoot_arrow" => "shoot".to_string(),
        "make_armor" => "make_iron_armor".to_string(),
        other => other.to_string(),
    }
}

fn episode_id_for_task(task_id: &str, seed: u64, config_hash: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(format!(
        "gamebench.crafter-singleplayer.episode:{}:{}:{}",
        task_id, seed, config_hash
    ));
    format!("{:x}", hasher.finalize())[..32].to_string()
}

fn display_action(action: &str) -> String {
    action
        .split('_')
        .map(|part| {
            let mut chars = part.chars();
            match chars.next() {
                Some(first) => format!("{}{}", first.to_ascii_uppercase(), chars.as_str()),
                None => String::new(),
            }
        })
        .collect::<String>()
}

fn title_event(kind: &str) -> String {
    kind.split('_').map(display_action).collect::<String>()
}

fn initial_reward_breakdown(resolved: &Value) -> Value {
    json!({
        "schema": "gamebench.crafter.reward_breakdown.v1",
        "env_total": 0.0,
        "monty_total": 0.0,
        "penalty_total": 0.0,
        "last_env": 0.0,
        "last_monty": 0.0,
        "last_env_components": [],
        "achievement_count": 0,
        "rule_rewards": resolved.get("rules").and_then(|rules| rules.get("rewards")).cloned().unwrap_or_else(|| json!({"achievement": 1.0, "invalid_action": 0.0, "death": 0.0, "step": 0.0})),
        "monty": resolved.get("monty_reward").cloned().unwrap_or(Value::Null)
    })
}

fn reward_component_total(components: &[RewardComponent]) -> f32 {
    components.iter().map(|component| component.delta).sum()
}

fn reward_components_json(components: &[RewardComponent]) -> Value {
    Value::Array(
        components
            .iter()
            .map(|component| {
                let mut value = json!({"source": component.source, "component": component.component, "delta": component.delta});
                if let Some(count) = component.count {
                    value["count"] = json!(count);
                }
                if !component.achievements.is_empty() {
                    value["achievements"] = json!(component.achievements);
                }
                value
            })
            .collect(),
    )
}

fn monty_config(spec: Option<&Value>) -> Option<Value> {
    let spec = spec?;
    let obj = spec.as_object()?;
    if obj
        .get("kind")
        .and_then(Value::as_str)
        .is_some_and(|kind| kind != "monty_python")
    {
        return None;
    }
    if obj
        .get("entry")
        .and_then(Value::as_str)
        .is_some_and(|entry| entry != "score_transition")
    {
        return None;
    }
    let module = obj.get("module").and_then(Value::as_str).unwrap_or("");
    let mut config = match module {
        "collect_wood_shaped_v1" => {
            json!({"achievement_rewards": {"collect_wood": 0.25, "place_table": 0.40, "make_wood_pickaxe": 0.50, "collect_stone": 0.25}, "resource_rewards": {"wood": 0.02, "stone": 0.02}, "action_penalties": {"unknown_action": -0.50}})
        }
        "achievement_ladder_v1" => {
            json!({"achievement_default": 0.25, "action_penalties": {"unknown_action": -0.50}})
        }
        "sparse_classic" => json!({"achievement_default": 1.0}),
        "goal_binary_v1" => json!({"achievement_default": 0.0}),
        _ => json!({}),
    };
    for section in [
        "achievement_rewards",
        "resource_rewards",
        "action_penalties",
    ] {
        if let Some(overrides) = obj.get(section).and_then(Value::as_object) {
            if config.get(section).and_then(Value::as_object).is_none() {
                config[section] = json!({});
            }
            let target = config
                .get_mut(section)
                .and_then(Value::as_object_mut)
                .unwrap();
            for (name, value) in overrides {
                if let Some(number) = value.as_f64() {
                    target.insert(name.clone(), json!(number));
                }
            }
        }
    }
    if let Some(default) = obj.get("achievement_default").and_then(Value::as_f64) {
        config["achievement_default"] = json!(default);
    }
    if config.as_object().is_some_and(|items| items.is_empty()) {
        return None;
    }
    config["module"] = json!(module);
    Some(config)
}

fn monty_section_weight(config: &Value, section: &str, name: &str) -> Option<f32> {
    config
        .get(section)
        .and_then(Value::as_object)
        .and_then(|items| items.get(name))
        .and_then(Value::as_f64)
        .map(|value| value as f32)
}

fn newly_unlocked(before: &BTreeMap<String, i64>, after: &BTreeMap<String, i64>) -> Vec<String> {
    after
        .iter()
        .filter_map(|(name, count)| {
            if *count > 0 && before.get(name).copied().unwrap_or(0) <= 0 {
                Some(name.clone())
            } else {
                None
            }
        })
        .collect()
}

fn termination_payload(
    done_reason: &Option<String>,
    last_damage_source: &Option<String>,
) -> Value {
    let reason = done_reason
        .clone()
        .unwrap_or_else(|| "done".to_string());
    let mut payload = json!({"reason": reason});
    if reason == "death" {
        if let Some(cause) = last_damage_source {
            payload["cause"] = json!(cause);
        }
    }
    payload
}

fn termination_record(
    step_index: u64,
    done_reason: &Option<String>,
    last_damage_source: &Option<String>,
) -> Value {
    let Some(reason) = done_reason else {
        return Value::Null;
    };
    let mut record = json!({
        "reason": reason,
        "step_index": step_index,
    });
    if reason == "death" {
        if let Some(cause) = last_damage_source {
            record["cause"] = json!(cause);
        }
    }
    record
}

fn event_summary(events: &[EventRecord], cursor_offset: usize) -> Value {
    let mut event_kind_counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut severity_counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut action_counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut transition_counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut reward_source_totals: BTreeMap<String, f64> = BTreeMap::new();
    let mut reward_component_totals: BTreeMap<String, f64> = BTreeMap::new();
    let mut terminal = Value::Null;
    for event in events {
        *event_kind_counts.entry(event.kind.clone()).or_insert(0) += 1;
        *severity_counts.entry(event.severity.clone()).or_insert(0) += 1;
        if let Some(action) = &event.action {
            *action_counts.entry(action.clone()).or_insert(0) += 1;
        }
        if let Some(transition) = &event.transition {
            if let Some(map) = transition.as_object() {
                for key in map.keys() {
                    *transition_counts.entry(key.clone()).or_insert(0) += 1;
                }
            }
        }
        if event.kind == "reward_delta" {
            let delta = event
                .payload
                .get("delta")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            let source = event
                .payload
                .get("source")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .to_string();
            let component = event
                .payload
                .get("component")
                .and_then(Value::as_str)
                .unwrap_or(&source)
                .to_string();
            *reward_source_totals.entry(source).or_insert(0.0) += delta;
            *reward_component_totals.entry(component).or_insert(0.0) += delta;
        }
        if event.kind == "terminal" || event.kind == "death" {
            let mut term = json!({
                "step_index": event.step_index,
                "reason": event.payload.get("reason").cloned().unwrap_or(Value::Null),
            });
            if let Some(cause) = event.payload.get("cause") {
                term["cause"] = cause.clone();
            }
            terminal = term;
        }
    }
    json!({
        "schema": "gamebench.crafter.event_summary.v1",
        "event_count": events.len(),
        "nev_cursor": cursor_offset + events.len(),
        "cursor_offset": cursor_offset,
        "first_step_index": events.first().map(|event| event.step_index),
        "last_step_index": events.last().map(|event| event.step_index),
        "event_kind_counts": event_kind_counts,
        "severity_counts": severity_counts,
        "action_counts": action_counts,
        "transition_counts": transition_counts,
        "reward_source_totals": reward_source_totals,
        "reward_component_totals": reward_component_totals,
        "terminal": terminal
    })
}

fn grid_hash(observation: &Value) -> String {
    let tiles = observation
        .get("world")
        .and_then(|world| world.get("tiles"))
        .and_then(Value::as_array)
        .filter(|items| !items.is_empty())
        .or_else(|| {
            observation
                .get("view")
                .and_then(|view| view.get("tiles"))
                .and_then(Value::as_array)
        });
    let Some(tiles) = tiles else {
        return String::new();
    };
    let mut parts = tiles
        .iter()
        .map(|tile| {
            let pos = tile
                .get("pos")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let x = pos.first().and_then(Value::as_i64).unwrap_or(0);
            let y = pos.get(1).and_then(Value::as_i64).unwrap_or(0);
            let kind = tile
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or("unknown");
            (y, x, format!("{},{}:{}", x, y, kind))
        })
        .collect::<Vec<_>>();
    parts.sort_by_key(|(y, x, _)| (*y, *x));
    let payload = parts
        .into_iter()
        .map(|(_, _, part)| part)
        .collect::<Vec<_>>()
        .join("|");
    format!("{:x}", Sha256::digest(payload.as_bytes()))[..16].to_string()
}

fn local_tile_counts(observation: &Value) -> Value {
    let mut counts: BTreeMap<String, u64> = BTreeMap::new();
    if let Some(tiles) = observation
        .get("view")
        .and_then(|view| view.get("tiles"))
        .and_then(Value::as_array)
    {
        for tile in tiles {
            let kind = tile
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or("unknown");
            *counts.entry(kind.to_string()).or_insert(0) += 1;
        }
    }
    json!(counts)
}

fn front_tile(observation: &Value) -> Value {
    let player = observation.get("player").unwrap_or(&Value::Null);
    let pos = value_pos(player.get("pos").unwrap_or(&Value::Null));
    let facing = value_pos(player.get("facing").unwrap_or(&Value::Null));
    let target = (pos.0 + facing.0, pos.1 + facing.1);
    if let Some(tiles) = observation
        .get("view")
        .and_then(|view| view.get("tiles"))
        .and_then(Value::as_array)
    {
        for tile in tiles {
            if value_pos(tile.get("pos").unwrap_or(&Value::Null)) == target {
                return tile.clone();
            }
        }
    }
    Value::Null
}

fn observation_text(readout: &Value) -> String {
    let obs = readout.get("observation").unwrap_or(&Value::Null);
    let player = obs.get("player").unwrap_or(&Value::Null);
    let inventory = player
        .get("inventory")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let nonzero_inventory = inventory
        .into_iter()
        .filter(|(_, value)| value.as_i64().unwrap_or(0) != 0)
        .collect::<Map<_, _>>();
    let achievements = obs
        .get("achievements")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let unlocked = achievements
        .into_iter()
        .filter_map(|(name, count)| {
            if count.as_i64().unwrap_or(0) > 0 {
                Some(name)
            } else {
                None
            }
        })
        .collect::<Vec<_>>();
    let front = readout.get("front_tile").unwrap_or(&Value::Null);
    let stats = obs.get("stats").unwrap_or(&Value::Null);
    let private = readout.get("private").unwrap_or(&Value::Null);
    let event_summary = readout.get("event_summary").unwrap_or(&Value::Null);
    [
        format!(
            "step={} max_steps={}",
            obs.get("step").and_then(Value::as_u64).unwrap_or(0),
            private.get("max_steps").cloned().unwrap_or(Value::Null)
        ),
        format!(
            "pos={} facing={} sleeping={}",
            player.get("pos").cloned().unwrap_or(Value::Null),
            player.get("facing").cloned().unwrap_or(Value::Null),
            player
                .get("sleeping")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        ),
        format!(
            "vitals=health:{} food:{} drink:{} energy:{}",
            player.get("health").cloned().unwrap_or(Value::Null),
            player.get("food").cloned().unwrap_or(Value::Null),
            player.get("drink").cloned().unwrap_or(Value::Null),
            player.get("energy").cloned().unwrap_or(Value::Null)
        ),
        format!(
            "front_tile={} at {}",
            front.get("kind").cloned().unwrap_or(Value::Null),
            front.get("pos").cloned().unwrap_or(Value::Null)
        ),
        format!("inventory={}", Value::Object(nonzero_inventory)),
        format!("achievements={}", json!(unlocked)),
        format!(
            "score={} daylight={}",
            stats.get("score").cloned().unwrap_or(Value::Null),
            stats.get("daylight").cloned().unwrap_or(Value::Null)
        ),
        format!(
            "reward=last:{} total:{} breakdown:{}",
            private.get("reward_last").cloned().unwrap_or(Value::Null),
            private.get("total_reward").cloned().unwrap_or(Value::Null),
            private
                .get("reward_breakdown")
                .cloned()
                .unwrap_or(Value::Null)
        ),
        format!(
            "events={}",
            event_summary
                .get("event_kind_counts")
                .cloned()
                .unwrap_or(Value::Null)
        ),
        format!(
            "transitions={}",
            event_summary
                .get("transition_counts")
                .cloned()
                .unwrap_or(Value::Null)
        ),
        format!(
            "nearby_tiles={}",
            readout
                .get("local_tile_counts")
                .cloned()
                .unwrap_or(Value::Null)
        ),
        format!(
            "valid_actions={}",
            readout.get("valid_actions").cloned().unwrap_or(Value::Null)
        ),
    ]
    .join("\n")
}

fn is_inventory_slot(key: &str) -> bool {
    key == "armor" || INVENTORY_KEYS.contains(&canonical_inventory_key(key))
}

fn canonical_inventory_key(key: &str) -> &str {
    match key {
        "arrow" => "arrows",
        "potion" => "potion_red",
        "armor" => "armor_chestplate",
        other => other,
    }
}

fn potion_slot(color: &str) -> Option<(&'static str, &'static str)> {
    POTION_SLOTS
        .iter()
        .copied()
        .find(|(candidate, _)| *candidate == color)
}

fn potion_for_action(
    action: &str,
    inventory: &BTreeMap<String, i64>,
) -> Option<(&'static str, &'static str)> {
    if let Some(color) = action.strip_prefix("drink_potion_") {
        return potion_slot(color);
    }
    if action != "drink_potion" {
        return None;
    }
    POTION_SLOTS
        .iter()
        .copied()
        .find(|(_, key)| inventory.get(*key).copied().unwrap_or(0) > 0)
}

fn is_achievement_slot(key: &str) -> bool {
    ACHIEVEMENTS.contains(&canonical_achievement_key(key))
}

fn is_craftax_achievement(key: &str) -> bool {
    matches!(
        canonical_achievement_key(key),
        "collect_sapphire"
            | "collect_ruby"
            | "open_chest"
            | "make_bow"
            | "make_arrow"
            | "make_iron_armor"
            | "make_diamond_armor"
            | "defeat_orc_soldier"
            | "defeat_orc_mage"
            | "defeat_knight"
            | "defeat_knight_archer"
            | "defeat_troll"
            | "drink_potion"
            | "gain_xp"
            | "reach_level"
    )
}

fn canonical_achievement_key(key: &str) -> &str {
    match key {
        "make_armor" => "make_iron_armor",
        other => other,
    }
}

fn is_crafter_base_material(kind: &str) -> bool {
    matches!(
        kind,
        "water"
            | "grass"
            | "stone"
            | "path"
            | "sand"
            | "tree"
            | "lava"
            | "coal"
            | "iron"
            | "diamond"
            | "table"
            | "furnace"
    )
}

fn is_known_material(kind: &str) -> bool {
    is_crafter_base_material(kind) || CRAFTAX_ITEM_TERRAIN.contains(&kind) || kind == "chest"
}

fn substrate_profile_from_rules(rules: &Value) -> &str {
    rules
        .get("substrate_profile")
        .and_then(Value::as_str)
        .unwrap_or("classic")
}

fn resolved_probe_from_rules(rules: &Value) -> Value {
    json!({
        "substrate_profile": substrate_profile_from_rules(rules),
        "rules": rules,
    })
}

fn material_allowed_for_resolved(material: &str, resolved: &Value) -> bool {
    if is_crafter_base_material(material) {
        return true;
    }
    if material == "chest" {
        return craftax_chests_enabled_for_resolved(resolved);
    }
    if CRAFTAX_ITEM_TERRAIN.contains(&material) {
        return craftax_items_enabled_for_resolved(resolved);
    }
    false
}

fn material_allowed_for_rules(material: &str, rules: &Value) -> bool {
    material_allowed_for_resolved(material, &resolved_probe_from_rules(rules))
}

fn action_allowed_for_resolved(action: &str, resolved: &Value) -> bool {
    if !CRAFTAX_ONLY_ACTIONS.contains(&action) {
        return true;
    }
    if action.starts_with("drink_potion") {
        return craftax_potions_enabled_for_resolved(resolved);
    }
    if matches!(
        action,
        "make_bow" | "make_arrow" | "make_iron_armor" | "make_diamond_armor"
    ) {
        return craftax_recipes_enabled_for_resolved(resolved);
    }
    if action == "shoot" {
        return craftax_player_projectiles_enabled_for_resolved(resolved);
    }
    false
}

fn inventory_slot_visible_for_resolved(slot: &str, resolved: &Value) -> bool {
    let slot = canonical_inventory_key(slot);
    if CLASSIC_INVENTORY_SLOTS.contains(&slot) {
        return true;
    }
    if !craftax_items_enabled_for_resolved(resolved) {
        return false;
    }
    if CRAFTAX_RECIPE_INVENTORY_SLOTS.contains(&slot) {
        return craftax_recipes_enabled_for_resolved(resolved);
    }
    if CRAFTAX_POTION_INVENTORY_SLOTS.contains(&slot) {
        return craftax_potions_enabled_for_resolved(resolved);
    }
    if CRAFTAX_XP_INVENTORY_SLOTS.contains(&slot) {
        return craftax_xp_enabled_for_resolved(resolved);
    }
    CRAFTAX_ITEM_INVENTORY_SLOTS.contains(&slot)
}

fn project_inventory_for_resolved(
    inventory: &BTreeMap<String, i64>,
    resolved: &Value,
) -> BTreeMap<String, i64> {
    inventory
        .iter()
        .filter(|(slot, _)| inventory_slot_visible_for_resolved(slot, resolved))
        .map(|(slot, amount)| (slot.clone(), *amount))
        .collect()
}

fn project_achievements_for_resolved(
    achievements: &BTreeMap<String, i64>,
    resolved: &Value,
) -> BTreeMap<String, i64> {
    achievements
        .iter()
        .filter(|(name, _)| {
            !is_craftax_achievement(name) || craftax_achievements_enabled_for_resolved(resolved)
        })
        .map(|(name, count)| (name.clone(), *count))
        .collect()
}

fn is_entity_kind(kind: &str) -> bool {
    matches!(
        kind,
        "cow"
            | "zombie"
            | "skeleton"
            | "orc_soldier"
            | "orc_mage"
            | "knight"
            | "knight_archer"
            | "troll"
            | "bat"
            | "snail"
            | "plant"
            | "arrow"
    )
}

fn is_classic_mob_kind(kind: &str) -> bool {
    matches!(kind, "cow" | "zombie" | "skeleton")
}

fn is_projectile_kind(kind: &str) -> bool {
    matches!(
        kind,
        "arrow"
            | "dagger"
            | "fireball"
            | "iceball"
            | "arrow2"
            | "slimeball"
            | "fireball2"
            | "iceball2"
    )
}

fn validate_projectile_kind_for_damage_source(
    projectile_kind: &str,
    damage_source: &str,
    context: &str,
) {
    let allowed = match damage_source {
        "arrow" | "player_arrow" | "craftax_ranged" => projectile_kind == "arrow",
        "craftax_magic" => projectile_kind == "fireball",
        _ => false,
    };
    if !allowed {
        panic!(
            "{} projectile_kind {} is unsupported for damage_source {}",
            context, projectile_kind, damage_source
        );
    }
}

fn default_entity_health(kind: &str) -> u64 {
    match kind {
        "cow" => 3,
        "zombie" => 5,
        "skeleton" => 3,
        "orc_soldier" => 5,
        "orc_mage" => 3,
        "knight" => 9,
        "knight_archer" => 8,
        "troll" => 12,
        "bat" => 2,
        "snail" => 3,
        "plant" | "arrow" => 1,
        _ => panic!("unsupported entity kind: {}", kind),
    }
}

fn defeat_achievement(kind: &str) -> Option<&'static str> {
    match kind {
        "zombie" => Some("defeat_zombie"),
        "skeleton" => Some("defeat_skeleton"),
        "orc_soldier" => Some("defeat_orc_soldier"),
        "orc_mage" => Some("defeat_orc_mage"),
        "knight" => Some("defeat_knight"),
        "knight_archer" => Some("defeat_knight_archer"),
        "troll" => Some("defeat_troll"),
        _ => None,
    }
}

fn resolved_entity_health(resolved: &Value, kind: &str) -> i32 {
    let key = format!("{}_health", kind);
    let value = resolved
        .get("substrate_config")
        .and_then(|config| config.get(&key))
        .and_then(Value::as_u64)
        .unwrap_or_else(|| default_entity_health(kind));
    if value == 0 || value > MAX_ENTITY_HEALTH {
        panic!(
            "resolved substrate_config.{} must be between 1 and {}",
            key, MAX_ENTITY_HEALTH
        );
    }
    value as i32
}

fn counter_as_i32(value: i64) -> i32 {
    value.clamp(i64::from(i32::MIN), i64::from(i32::MAX)) as i32
}

fn clamp_inventory(key: &str, value: i64) -> i64 {
    value.clamp(0, inventory_limit(key))
}

fn inventory_limit(key: &str) -> i64 {
    match canonical_inventory_key(key) {
        "arrows" => 99,
        "xp" | "level" | "stat_points" => i64::MAX,
        _ => MAX_INVENTORY_COUNTER,
    }
}

fn digest_json<T: Serialize>(value: &T) -> String {
    let encoded = serde_json::to_vec(value).unwrap_or_default();
    format!("sha256:{:x}", Sha256::digest(encoded))
}
