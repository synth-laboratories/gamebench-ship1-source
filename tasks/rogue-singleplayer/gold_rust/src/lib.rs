use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub mod source_attack;
pub mod source_chase;
pub mod source_combat;
pub mod source_command;
pub mod source_daemons;
pub mod source_do_chase;
pub mod source_fight;
pub mod source_level;
pub mod source_monsters;
pub mod source_motion;
pub mod source_pack;
pub mod source_potions;
pub mod source_rings;
pub mod source_scrolls;
pub mod source_state;
pub mod source_sticks;
pub mod source_traps;

pub type Position = (usize, usize);

pub const MAXROOMS: usize = 9;
pub const MAXTHINGS: usize = 9;
pub const MAXOBJ: usize = 9;
pub const MAXPACK: usize = 23;
pub const MAXTRAPS: usize = 10;
pub const AMULETLEVEL: usize = 26;
pub const NUMTHINGS: usize = 7;
pub const MAXPASS: usize = 13;
pub const NUMLINES: usize = 24;
pub const NUMCOLS: usize = 80;
pub const STATLINE: usize = NUMLINES - 1;
pub const BORE_LEVEL: usize = 50;

pub const PASSAGE: char = '#';
pub const DOOR: char = '+';
pub const FLOOR: char = '.';
pub const PLAYER: char = '@';
pub const TRAP: char = '^';
pub const STAIRS: char = '%';
pub const GOLD: char = '*';
pub const POTION: char = '!';
pub const SCROLL: char = '?';
pub const MAGIC: char = '$';
pub const FOOD: char = ':';
pub const WEAPON: char = ')';
pub const ARMOR: char = ']';
pub const AMULET: char = ',';
pub const RING: char = '=';
pub const STICK: char = '/';
const ISCURSED: i32 = 0o000001;
const ISKNOW: i32 = 0o000002;
const ISFOUND: i32 = 0o000020;
const ISHELD: i32 = 0o000400;
const SOURCE_ROOM_ISGONE: i32 = 0o000002;
const SOURCE_ROOM_ISMAZE: i32 = 0o000004;
const TRAP_F_SEEN: i32 = 0x40;
const TRAP_F_TMASK: i32 = 0x07;
const VS_MAGIC: i32 = 3;
const R_PROTECT: i32 = 0;
const BOLT_LENGTH: usize = 6;
const FLAME_WEAPON: i32 = 9;
const WS_ELECT: i32 = 2;
const WS_FIRE: i32 = 3;
const WS_COLD: i32 = 4;
const S_SCARE: i32 = 10;
const S_ID_POTION: i32 = 5;
const S_ID_SCROLL: i32 = 6;
const S_ID_WEAPON: i32 = 7;
const S_ID_ARMOR: i32 = 8;
const S_ID_R_OR_S: i32 = 9;
const R_OR_S_FILTER: i32 = -2;
const S_TELEP: usize = 12;
const HUNGERTIME: i32 = 1300;
const STOMACHSIZE: i32 = 2000;

#[derive(Clone, Copy)]
enum SourceWhatisType {
    Object(char),
    RingOrStick,
}

const MONSTER_NAMES: [&str; 26] = [
    "aquator",
    "bat",
    "centaur",
    "dragon",
    "emu",
    "venus flytrap",
    "griffin",
    "hobgoblin",
    "ice monster",
    "jabberwock",
    "kestrel",
    "leprechaun",
    "medusa",
    "nymph",
    "orc",
    "phantom",
    "quagga",
    "rattlesnake",
    "snake",
    "troll",
    "black unicorn",
    "vampire",
    "wraith",
    "xeroc",
    "yeti",
    "zombie",
];
const SOURCE_WEAPON_NAMES: [&str; 10] = [
    "mace",
    "long sword",
    "short bow",
    "arrow",
    "dagger",
    "two handed sword",
    "dart",
    "shuriken",
    "spear",
    "flame",
];
const SOURCE_ARMOR_NAMES: [&str; 8] = [
    "leather armor",
    "ring mail",
    "studded leather armor",
    "scale mail",
    "chain mail",
    "splint mail",
    "banded mail",
    "plate mail",
];
const SOURCE_A_CLASS: [i32; 8] = [8, 7, 7, 6, 5, 4, 4, 3];
const SOURCE_POTION_NAMES: [&str; 14] = [
    "confusion",
    "hallucination",
    "poison",
    "gain strength",
    "see invisible",
    "healing",
    "monster detection",
    "magic detection",
    "raise level",
    "extra healing",
    "haste self",
    "restore strength",
    "blindness",
    "levitation",
];
const SOURCE_RING_NAMES: [&str; 14] = [
    "protection",
    "add strength",
    "sustain strength",
    "searching",
    "see invisible",
    "adornment",
    "aggravate monster",
    "dexterity",
    "increase damage",
    "regeneration",
    "slow digestion",
    "teleportation",
    "stealth",
    "maintain armor",
];
const SOURCE_SCROLL_NAMES: [&str; 18] = [
    "monster confusion",
    "magic mapping",
    "hold monster",
    "sleep",
    "enchant armor",
    "identify potion",
    "identify scroll",
    "identify weapon",
    "identify armor",
    "identify ring, wand or staff",
    "scare monster",
    "food detection",
    "teleportation",
    "enchant weapon",
    "create monster",
    "remove curse",
    "aggravate monsters",
    "protect armor",
];
const SOURCE_STICK_NAMES: [&str; 14] = [
    "light",
    "invisibility",
    "lightning",
    "fire",
    "cold",
    "polymorph",
    "magic missile",
    "haste monster",
    "slow monster",
    "drain life",
    "nothing",
    "teleport away",
    "teleport to",
    "cancellation",
];
const SOURCE_HELP_ENTRIES: [(char, &str, bool); 65] = [
    ('?', "\tprints help", true),
    ('/', "\tidentify object", true),
    ('h', "\tleft", true),
    ('j', "\tdown", true),
    ('k', "\tup", true),
    ('l', "\tright", true),
    ('y', "\tup & left", true),
    ('u', "\tup & right", true),
    ('b', "\tdown & left", true),
    ('n', "\tdown & right", true),
    ('H', "\trun left", false),
    ('J', "\trun down", false),
    ('K', "\trun up", false),
    ('L', "\trun right", false),
    ('Y', "\trun up & left", false),
    ('U', "\trun up & right", false),
    ('B', "\trun down & left", false),
    ('N', "\trun down & right", false),
    ('\x08', "\trun left until adjacent", false),
    ('\x0a', "\trun down until adjacent", false),
    ('\x0b', "\trun up until adjacent", false),
    ('\x0c', "\trun right until adjacent", false),
    ('\x19', "\trun up & left until adjacent", false),
    ('\x15', "\trun up & right until adjacent", false),
    ('\x02', "\trun down & left until adjacent", false),
    ('\x0e', "\trun down & right until adjacent", false),
    ('\0', "\t<SHIFT><dir>: run that way", true),
    ('\0', "\t<CTRL><dir>: run till adjacent", true),
    ('f', "<dir>\tfight till death or near death", true),
    ('t', "<dir>\tthrow something", true),
    ('m', "<dir>\tmove onto without picking up", true),
    ('z', "<dir>\tzap a wand in a direction", true),
    ('^', "<dir>\tidentify trap type", true),
    ('s', "\tsearch for trap/secret door", true),
    ('>', "\tgo down a staircase", true),
    ('<', "\tgo up a staircase", true),
    ('.', "\trest for a turn", true),
    (',', "\tpick something up", true),
    ('i', "\tinventory", true),
    ('I', "\tinventory single item", true),
    ('q', "\tquaff potion", true),
    ('r', "\tread scroll", true),
    ('e', "\teat food", true),
    ('w', "\twield a weapon", true),
    ('W', "\twear armor", true),
    ('T', "\ttake armor off", true),
    ('P', "\tput on ring", true),
    ('R', "\tremove ring", true),
    ('d', "\tdrop object", true),
    ('c', "\tcall object", true),
    ('a', "\trepeat last command", true),
    (')', "\tprint current weapon", true),
    (']', "\tprint current armor", true),
    ('=', "\tprint current rings", true),
    ('@', "\tprint current stats", true),
    ('D', "\trecall what's been discovered", true),
    ('o', "\texamine/set options", true),
    ('\x12', "\tredraw screen", true),
    ('\x10', "\trepeat last message", true),
    ('\x1b', "\tcancel command", true),
    ('S', "\tsave game", true),
    ('Q', "\tquit", true),
    ('!', "\tshell escape", true),
    ('F', "<dir>\tfight till either of you dies", true),
    ('v', "\tprint version number", true),
];
const SOURCE_HUNGER_NAMES: [&str; 4] = ["", "Hungry", "Weak", "Faint"];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RogueRng {
    pub seed: i32,
}

impl RogueRng {
    pub fn new(seed: i32) -> Self {
        Self { seed }
    }

    pub fn rn(&mut self) -> i32 {
        self.seed = self.seed.wrapping_mul(11109).wrapping_add(13849);
        (self.seed >> 16) & 0xffff
    }

    pub fn rnd(&mut self, range: i32) -> i32 {
        if range == 0 {
            0
        } else {
            self.rn().abs() % range
        }
    }

    pub fn roll(&mut self, mut number: i32, sides: i32) -> i32 {
        let mut total = 0;
        while number > 0 {
            total += self.rnd(sides) + 1;
            number -= 1;
        }
        total
    }

    pub fn spread(&mut self, nm: i32) -> i32 {
        nm - (nm / 20) + self.rnd(nm / 10)
    }

    pub fn gold_calc(&mut self, level: i32) -> i32 {
        self.rnd(50 + 10 * level) + 2
    }
}

pub fn direction_delta(ch: char) -> Option<(isize, isize)> {
    command_move_delta(ch.to_ascii_lowercase())
}

pub fn command_move_delta(ch: char) -> Option<(isize, isize)> {
    DIRECTIONS
        .iter()
        .find(|(key, _, _)| key.chars().next().unwrap() == ch)
        .map(|(_, dy, dx)| (*dy, *dx))
}

pub fn step_ok(ch: char) -> bool {
    !matches!(ch, ' ' | '|' | '-') && !ch.is_ascii_alphabetic()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResolvedTask {
    pub task_id: String,
    pub seed: i64,
    pub grid: Vec<String>,
    pub max_steps: usize,
    pub objective: String,
    #[serde(default)]
    pub inventory: Vec<Value>,
    #[serde(default)]
    pub monsters: Vec<Value>,
    #[serde(default)]
    pub traps: Vec<Value>,
    #[serde(default)]
    pub source_map_cells: Vec<Value>,
    #[serde(default)]
    pub level_objects: Vec<Value>,
    pub config_hash: String,
    pub episode_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EventRecord {
    pub step_index: usize,
    pub tick: usize,
    pub episode_id: String,
    pub kind: String,
    pub action: Option<String>,
    pub transition: Option<String>,
    pub severity: String,
    pub message: String,
    pub payload: Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PublicState {
    pub terrain: Vec<String>,
    pub hero: Position,
    pub visible_items: BTreeMap<String, String>,
    #[serde(default)]
    pub visible_monsters: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PrivateState {
    pub step_index: usize,
    pub total_reward: f64,
    pub terminated: bool,
    pub truncated: bool,
    pub terminal_reason: String,
    pub dungeon_level: usize,
    #[serde(default = "default_player_level_usize")]
    pub max_level: usize,
    #[serde(default)]
    pub has_amulet: bool,
    pub purse: usize,
    pub food: usize,
    pub hp: usize,
    pub max_hp: usize,
    #[serde(default)]
    pub rng_seed: i32,
    #[serde(default)]
    pub item_values: BTreeMap<String, usize>,
    #[serde(default)]
    pub source_inventory: Vec<Value>,
    #[serde(default)]
    pub left_ring_id: String,
    #[serde(default)]
    pub right_ring_id: String,
    #[serde(default)]
    pub current_weapon_id: String,
    #[serde(default)]
    pub current_armor_id: String,
    #[serde(default)]
    pub player_flags: i32,
    #[serde(default = "default_strength")]
    pub strength: i32,
    #[serde(default = "default_strength")]
    pub max_strength: i32,
    #[serde(default)]
    pub no_command: i32,
    #[serde(default)]
    pub no_move: i32,
    #[serde(default = "default_food_left")]
    pub food_left: i32,
    #[serde(default)]
    pub hungry_state: i32,
    #[serde(default)]
    pub quiet: i32,
    #[serde(default)]
    pub daemon_between: i32,
    #[serde(default = "default_pot_known")]
    pub pot_known: Vec<bool>,
    #[serde(default = "default_ring_known")]
    pub ring_known: Vec<bool>,
    #[serde(default = "default_scr_known")]
    pub scr_known: Vec<bool>,
    #[serde(default = "default_ws_known")]
    pub ws_known: Vec<bool>,
    #[serde(default)]
    pub seen_tiles: Vec<String>,
    #[serde(default)]
    pub scout_score: usize,
    #[serde(default)]
    pub scout_last: usize,
    #[serde(default)]
    pub acquired_item_classes: Vec<String>,
    #[serde(default)]
    pub killed_monster_types: Vec<String>,
    #[serde(default)]
    pub synth_shaped_reward: f64,
    #[serde(default)]
    pub synth_shaped_reward_last: f64,
    #[serde(default)]
    pub source_effect_markers: Vec<String>,
    #[serde(default)]
    pub source_monsters: Vec<Value>,
    #[serde(default)]
    pub source_combat_markers: Vec<String>,
    #[serde(default)]
    pub source_attack_markers: Vec<String>,
    #[serde(default)]
    pub source_chase_markers: Vec<String>,
    #[serde(default)]
    pub source_traps: Vec<Value>,
    #[serde(default)]
    pub source_trap_markers: Vec<String>,
    #[serde(default)]
    pub source_map_cells: Vec<Value>,
    #[serde(default)]
    pub source_daemon_actions: Vec<Value>,
    #[serde(default)]
    pub source_daemon_markers: Vec<String>,
    #[serde(default)]
    pub source_level_objects: Vec<Value>,
    #[serde(default)]
    pub source_rooms: Vec<Value>,
    #[serde(default)]
    pub source_passages: Vec<Value>,
    #[serde(default)]
    pub source_level_markers: Vec<String>,
    #[serde(default)]
    pub player_exp: i32,
    #[serde(default = "default_player_level")]
    pub player_level: i32,
    #[serde(default = "default_player_armor")]
    pub player_armor: i32,
    #[serde(default = "default_player_damage")]
    pub player_damage: String,
    #[serde(default)]
    pub vf_hit: i32,
    #[serde(default)]
    pub max_hit: i32,
    #[serde(default)]
    pub kamikaze: bool,
    #[serde(default = "default_true")]
    pub command_after: bool,
    #[serde(default)]
    pub command_running: bool,
    #[serde(default)]
    pub command_count: i32,
    #[serde(default)]
    pub command_last: String,
    #[serde(default)]
    pub command_direction: String,
    #[serde(default)]
    pub command_runch: String,
    #[serde(default)]
    pub command_to_death: bool,
    #[serde(default)]
    pub command_markers: Vec<String>,
    pub config_hash: String,
    pub episode_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RogueSession {
    pub resolved: ResolvedTask,
    pub public: PublicState,
    pub private: PrivateState,
    pub events: Vec<EventRecord>,
}

const DIRECTIONS: [(&str, isize, isize); 8] = [
    ("h", 0, -1),
    ("j", 1, 0),
    ("k", -1, 0),
    ("l", 0, 1),
    ("y", -1, -1),
    ("u", -1, 1),
    ("b", 1, -1),
    ("n", 1, 1),
];

impl Default for RogueSession {
    fn default() -> Self {
        let task = json!({
            "task_id": "manual",
            "seed": 1,
            "grid": [
                "                    ",
                "  ------------      ",
                "  |@...*....%|      ",
                "  |....:.....|      ",
                "  ------------      ",
                "                    "
            ],
            "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 40}},
            "objective": "descend"
        });
        let resolved = resolve_task(&task, None);
        let mut session = Self {
            resolved: resolved.clone(),
            public: PublicState {
                terrain: Vec::new(),
                hero: (0, 0),
                visible_items: BTreeMap::new(),
                visible_monsters: BTreeMap::new(),
            },
            private: PrivateState {
                step_index: 0,
                total_reward: 0.0,
                terminated: false,
                truncated: false,
                terminal_reason: String::new(),
                dungeon_level: 1,
                max_level: 1,
                has_amulet: false,
                purse: 0,
                food: 1,
                hp: 12,
                max_hp: 12,
                rng_seed: resolved.seed as i32,
                item_values: BTreeMap::new(),
                source_inventory: Vec::new(),
                left_ring_id: String::new(),
                right_ring_id: String::new(),
                current_weapon_id: String::new(),
                current_armor_id: String::new(),
                player_flags: 0,
                strength: 16,
                max_strength: 16,
                no_command: 0,
                no_move: 0,
                food_left: 1300,
                hungry_state: 0,
                quiet: 0,
                daemon_between: 0,
                pot_known: default_pot_known(),
                ring_known: default_ring_known(),
                scr_known: default_scr_known(),
                ws_known: default_ws_known(),
                seen_tiles: Vec::new(),
                scout_score: 0,
                scout_last: 0,
                acquired_item_classes: Vec::new(),
                killed_monster_types: Vec::new(),
                synth_shaped_reward: 0.0,
                synth_shaped_reward_last: 0.0,
                source_effect_markers: Vec::new(),
                source_monsters: Vec::new(),
                source_combat_markers: Vec::new(),
                source_attack_markers: Vec::new(),
                source_chase_markers: Vec::new(),
                source_traps: Vec::new(),
                source_trap_markers: Vec::new(),
                source_map_cells: Vec::new(),
                source_daemon_actions: Vec::new(),
                source_daemon_markers: Vec::new(),
                source_level_objects: Vec::new(),
                source_rooms: Vec::new(),
                source_passages: Vec::new(),
                source_level_markers: Vec::new(),
                player_exp: 0,
                player_level: 1,
                player_armor: 6,
                player_damage: "1x4".to_string(),
                vf_hit: 0,
                max_hit: 0,
                kamikaze: false,
                command_after: true,
                command_running: false,
                command_count: 0,
                command_last: String::new(),
                command_direction: String::new(),
                command_runch: String::new(),
                command_to_death: false,
                command_markers: Vec::new(),
                config_hash: resolved.config_hash.clone(),
                episode_id: resolved.episode_id.clone(),
            },
            events: Vec::new(),
        };
        session.reset(resolved);
        session
    }
}

impl RogueSession {
    pub const ENV_FAMILY: &'static str = "rogue-singleplayer";

    pub fn reset(&mut self, resolved: ResolvedTask) {
        let mut terrain = Vec::new();
        let mut items = BTreeMap::new();
        let mut item_values = BTreeMap::new();
        let mut hero = (0usize, 0usize);
        let mut rng = RogueRng::new(resolved.seed as i32);
        for (row, line) in resolved.grid.iter().enumerate() {
            let mut chars: Vec<char> = line.chars().collect();
            for (col, ch) in chars.iter_mut().enumerate() {
                if *ch == '@' {
                    hero = (row, col);
                    *ch = '.';
                } else if *ch == GOLD || *ch == FOOD {
                    let key = format!("{},{}", row, col);
                    items.insert(key.clone(), ch.to_string());
                    if *ch == GOLD {
                        item_values.insert(key, rng.gold_calc(1) as usize);
                    }
                    *ch = '.';
                }
            }
            terrain.push(chars.into_iter().collect());
        }
        self.resolved = resolved.clone();
        let source_monsters = normalize_monsters(&resolved.monsters);
        let source_traps = normalize_traps(&resolved.traps, &terrain);
        let source_map_cells = normalize_source_map_cells(&resolved.source_map_cells);
        apply_source_map_cell_display(&mut terrain, &source_map_cells);
        let source_level_objects = normalize_level_objects(&resolved.level_objects);
        for obj in &source_level_objects {
            let (row, col) = level_object_pos(obj);
            let key = format!("{},{}", row, col);
            let obj_type = item_char(obj, "type", '?');
            items.insert(key.clone(), obj_type.to_string());
            if obj_type == GOLD {
                item_values.insert(key, item_i32(obj, "goldval", 0).max(0) as usize);
            }
            if row >= 0 && (row as usize) < terrain.len() {
                let mut chars: Vec<char> = terrain[row as usize].chars().collect();
                if col >= 0 && (col as usize) < chars.len() && chars[col as usize] == obj_type {
                    chars[col as usize] = '.';
                    terrain[row as usize] = chars.into_iter().collect();
                }
            }
        }
        self.public = PublicState {
            terrain,
            hero,
            visible_items: items,
            visible_monsters: visible_monsters(&source_monsters),
        };
        self.private = PrivateState {
            step_index: 0,
            total_reward: 0.0,
            terminated: false,
            truncated: false,
            terminal_reason: String::new(),
            dungeon_level: 1,
            max_level: 1,
            has_amulet: false,
            purse: 0,
            food: 1,
            hp: 12,
            max_hp: 12,
            rng_seed: rng.seed,
            item_values,
            source_inventory: normalize_inventory(&resolved.inventory),
            left_ring_id: String::new(),
            right_ring_id: String::new(),
            current_weapon_id: String::new(),
            current_armor_id: String::new(),
            player_flags: 0,
            strength: 16,
            max_strength: 16,
            no_command: 0,
            no_move: 0,
            food_left: 1300,
            hungry_state: 0,
            quiet: 0,
            daemon_between: 0,
            pot_known: default_pot_known(),
            ring_known: default_ring_known(),
            scr_known: default_scr_known(),
            ws_known: default_ws_known(),
            seen_tiles: Vec::new(),
            scout_score: 0,
            scout_last: 0,
            acquired_item_classes: Vec::new(),
            killed_monster_types: Vec::new(),
            synth_shaped_reward: 0.0,
            synth_shaped_reward_last: 0.0,
            source_effect_markers: Vec::new(),
            source_monsters,
            source_combat_markers: Vec::new(),
            source_attack_markers: Vec::new(),
            source_chase_markers: Vec::new(),
            source_traps,
            source_trap_markers: Vec::new(),
            source_map_cells,
            source_daemon_actions: default_daemon_actions(),
            source_daemon_markers: Vec::new(),
            source_level_objects,
            source_rooms: Vec::new(),
            source_passages: Vec::new(),
            source_level_markers: Vec::new(),
            player_exp: 0,
            player_level: 1,
            player_armor: 6,
            player_damage: "1x4".to_string(),
            vf_hit: 0,
            max_hit: 0,
            kamikaze: false,
            command_after: true,
            command_running: false,
            command_count: 0,
            command_last: String::new(),
            command_direction: String::new(),
            command_runch: String::new(),
            command_to_death: false,
            command_markers: Vec::new(),
            config_hash: resolved.config_hash.clone(),
            episode_id: resolved.episode_id.clone(),
        };
        self.events.clear();
        self.refresh_progress_metrics(None, false);
        self.event(
            "state_transition",
            format!(
                "TaskResolved({},{})",
                resolved.task_id, resolved.config_hash
            ),
            None,
            Some("reset"),
            "info",
            json!({"task": resolved}),
        );
    }

    pub fn reset_from_entry(entry: &Value) -> Self {
        let task = scenario_to_task(entry);
        let mut session = Self::default();
        session.reset(resolve_task(&task, None));
        if let Some(actions) = entry.get("actions").and_then(Value::as_array) {
            for action in actions {
                if session.private.terminated || session.private.truncated {
                    break;
                }
                session.step(action.as_str().unwrap_or(""));
            }
        }
        session
    }

    pub fn step(&mut self, action: &str) {
        if self.private.terminated || self.private.truncated {
            self.event(
                "rule_violation",
                "RuleViolation(terminal)".to_string(),
                Some(action),
                Some("reject"),
                "warn",
                json!({}),
            );
            return;
        }
        self.private.step_index += 1;
        self.run_source_daemon_phase(action, source_daemons::BEFORE, "before");
        if self.private.terminated || self.private.truncated {
            return;
        }
        let command = effective_command(action);
        let projection = self.apply_command_projection(action);
        self.event(
            "command_dispatch",
            format!(
                "CommandDispatch({})",
                projection["command"].as_str().unwrap_or("")
            ),
            Some(action),
            Some("command"),
            "info",
            projection.clone(),
        );
        let markers = projection["final"]["markers"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        if markers
            .iter()
            .any(|marker| marker.as_str() == Some("no_command_wait"))
        {
            self.event("action_applied", "NoCommandWait()".to_string(), Some(action), Some("no_command_wait"), "info", json!({"markers": projection["final"]["markers"], "no_command": self.private.no_command}));
        } else if let Some((dy, dx)) = command_move_delta(command) {
            self.move_hero(&command.to_string(), dy, dx);
        } else if command == '.' {
            self.event(
                "action_applied",
                "Rest()".to_string(),
                Some(action),
                Some("rest"),
                "info",
                json!({}),
            );
        } else if command == ',' {
            self.pickup(action);
        } else if command == '>' {
            self.descend(action);
        } else if command == '<' {
            self.ascend(action);
        } else if command == 's' {
            self.search(action);
        } else if matches!(command, 'f' | 'F') {
            if !self.apply_source_fight_command(command, action) {
                self.event(
                    "action_applied",
                    format!("SourceCommandPending({})", projection["command"].as_str().unwrap_or("")),
                    Some(action),
                    Some("source_pending"),
                    "info",
                    json!({"command": projection["command"], "markers": projection["final"]["markers"]}),
                );
            }
        } else if matches!(
            command,
            'q' | 'r' | 'z' | 'P' | 'R' | 'd' | 'e' | 'w' | 'W' | 'T' | 't'
        ) {
            if !self.apply_source_item_command(command, action) {
                self.event(
                    "action_applied",
                    format!("SourceCommandPending({})", projection["command"].as_str().unwrap_or("")),
                    Some(action),
                    Some("source_pending"),
                    "info",
                    json!({"command": projection["command"], "markers": projection["final"]["markers"]}),
                );
            }
        } else if self.apply_source_no_turn_command(command, action, &projection) {
        } else if projection["known"].as_bool().unwrap_or(false) {
            let transition = if self.private.command_after {
                "source_pending"
            } else {
                "source_no_turn"
            };
            self.event(
                "action_applied",
                format!("SourceCommandPending({})", projection["command"].as_str().unwrap_or("")),
                Some(action),
                Some(transition),
                "info",
                json!({"command": projection["command"], "markers": projection["final"]["markers"]}),
            );
        } else {
            self.event(
                "rule_violation",
                format!("RuleViolation(illegal_command:{})", action),
                Some(action),
                Some("illegal"),
                "warn",
                json!({"command": projection["command"]}),
            );
        }
        if self.private.command_after && !self.private.terminated && !self.private.truncated {
            self.run_source_daemon_phase(action, source_daemons::AFTER, "after");
        }
        if self.private.command_after && !self.private.terminated && !self.private.truncated {
            self.run_source_monster_turns(action);
        }
        self.refresh_progress_metrics(Some(action), true);
        if self.private.step_index >= self.resolved.max_steps && !self.private.terminated {
            self.private.truncated = true;
            self.private.terminal_reason = "truncated".to_string();
            self.event(
                "terminal",
                "Terminal(truncated)".to_string(),
                Some(action),
                Some("truncate"),
                "info",
                json!({}),
            );
        }
    }

    fn move_hero(&mut self, action: &str, dy: isize, dx: isize) {
        if self.private.no_move > 0 {
            self.private.no_move -= 1;
            self.event(
                "action_applied",
                format!("NoMoveWait(remaining={})", self.private.no_move),
                Some(action),
                Some("no_move_wait"),
                "info",
                json!({"no_move": self.private.no_move}),
            );
            return;
        }
        let (row, col) = self.public.hero;
        let nr = row as isize + dy;
        let nc = col as isize + dx;
        if nr < 0
            || nc < 0
            || !self.in_bounds(nr as usize, nc as usize)
            || self.blocked(nr as usize, nc as usize)
            || !self.diag_ok(row, col, nr as usize, nc as usize)
        {
            self.event(
                "rule_violation",
                "Bump(wall)".to_string(),
                Some(action),
                Some("blocked"),
                "warn",
                json!({"from": [row, col], "to": [nr, nc]}),
            );
            return;
        }
        if let Some(monster) = self.monster_at(nr as usize, nc as usize) {
            self.fight_monster(action, monster, false);
            return;
        }
        self.public.hero = (nr as usize, nc as usize);
        self.event(
            "action_applied",
            format!("Move({},{},{})", action, nr, nc),
            Some(action),
            Some("move"),
            "info",
            json!({"hero": [nr, nc]}),
        );
        let trap_kind = self.apply_source_trap(action, (row, col));
        if self.private.terminated
            || matches!(
                trap_kind,
                Some(source_traps::T_DOOR | source_traps::T_TELEP)
            )
        {
            return;
        }
        self.pickup(action);
    }

    fn pickup(&mut self, action: &str) {
        let (row, col) = self.public.hero;
        let key = format!("{},{}", row, col);
        if let Some(item) = self.public.visible_items.remove(&key) {
            let level_object_index = self.source_level_object_index_at(row as i32, col as i32);
            if item == GOLD.to_string() {
                let gold = self.private.item_values.remove(&key).unwrap();
                self.private.purse += gold;
                self.record_acquired_item_class(GOLD);
                if let Some(index) = level_object_index {
                    self.private.source_level_objects.remove(index);
                }
                self.event(
                    "resource_delta",
                    format!("GoldPicked({},total={})", gold, self.private.purse),
                    Some(action),
                    Some("pickup"),
                    "info",
                    json!({"gold": gold, "purse": self.private.purse}),
                );
            } else if item == FOOD.to_string() && level_object_index.is_none() {
                self.private.food += 1;
                self.record_acquired_item_class(FOOD);
                self.event(
                    "resource_delta",
                    format!("FoodPicked(total={})", self.private.food),
                    Some(action),
                    Some("pickup"),
                    "info",
                    json!({"food": self.private.food}),
                );
            } else if let Some(index) = level_object_index {
                let picked = self.private.source_level_objects.remove(index);
                let result = self.add_source_inventory_object(&picked);
                if result == "no_room" {
                    self.private
                        .source_level_objects
                        .insert(index, picked.clone());
                    self.public.visible_items.insert(key, item);
                    self.event(
                        "rule_violation",
                        "RuleViolation(pack_full)".to_string(),
                        Some(action),
                        Some("pickup_blocked"),
                        "warn",
                        json!({"item": picked}),
                    );
                    return;
                }
                self.record_acquired_item_class(item_char(
                    &picked,
                    "type",
                    item.chars().next().unwrap_or('?'),
                ));
                self.event(
                    "resource_delta",
                    format!("SourceItemPicked({},{})", item_str(&picked, "id", ""), result),
                    Some(action),
                    Some("pickup"),
                    "info",
                    json!({"item": picked, "result": result, "inventory": self.private.source_inventory.clone()}),
                );
            } else {
                self.public.visible_items.insert(key, item);
            }
        } else if action == "," {
            self.event(
                "state_transition",
                "NothingHere()".to_string(),
                Some(action),
                Some("pickup_empty"),
                "info",
                json!({}),
            );
        }
    }

    fn refresh_progress_metrics(&mut self, action: Option<&str>, emit: bool) {
        let mut seen: BTreeSet<String> = self.private.seen_tiles.iter().cloned().collect();
        let old_shaped = self.private.synth_shaped_reward;
        let newly_seen: Vec<String> = self
            .currently_observed_tile_keys()
            .into_iter()
            .filter(|key| !seen.contains(key))
            .collect();
        if !newly_seen.is_empty() {
            for key in &newly_seen {
                seen.insert(key.clone());
            }
            self.private.seen_tiles = seen.into_iter().collect();
            self.private
                .seen_tiles
                .sort_by_key(|key| scout_tile_sort_key(key));
        }
        self.private.scout_score = self.private.seen_tiles.len();
        self.private.scout_last = if emit { newly_seen.len() } else { 0 };
        let shaped = self.compute_synth_shaped_reward();
        let shaped_delta = if emit { shaped - old_shaped } else { 0.0 };
        self.private.synth_shaped_reward = shaped;
        self.private.synth_shaped_reward_last = shaped_delta;
        if emit && !newly_seen.is_empty() {
            self.event(
                "resource_delta",
                format!(
                    "ScoutDelta({},total={})",
                    newly_seen.len(),
                    self.private.scout_score
                ),
                action,
                Some("scout"),
                "info",
                json!({"new_tiles": newly_seen, "scout_delta": self.private.scout_last, "scout_score": self.private.scout_score}),
            );
        }
        if emit && shaped_delta.abs() > 1e-9 {
            self.event(
                "resource_delta",
                format!("SynthShapedRewardDelta({shaped_delta:.2},total={shaped:.2})"),
                action,
                Some("synth_shaped_reward"),
                "info",
                self.progress_metrics_payload(),
            );
        }
    }

    fn currently_observed_tile_keys(&self) -> Vec<String> {
        let (row, col) = self.public.hero;
        let mut keys = Vec::new();
        for seen_row in row.saturating_sub(1)..=(row + 1) {
            for seen_col in col.saturating_sub(1)..=(col + 1) {
                if self.in_bounds(seen_row, seen_col) && self.terrain(seen_row, seen_col) != ' ' {
                    keys.push(format!(
                        "{},{},{}",
                        self.private.dungeon_level, seen_row, seen_col
                    ));
                }
            }
        }
        keys
    }

    fn record_acquired_item_class(&mut self, obj_type: char) {
        if obj_type == '\0' {
            return;
        }
        let mut classes: BTreeSet<String> =
            self.private.acquired_item_classes.iter().cloned().collect();
        classes.insert(obj_type.to_string());
        self.private.acquired_item_classes = classes.into_iter().collect();
    }

    fn record_killed_monster_type(&mut self, monster_type: char) {
        if monster_type == '\0' {
            return;
        }
        let mut killed: BTreeSet<String> =
            self.private.killed_monster_types.iter().cloned().collect();
        killed.insert(monster_type.to_string());
        self.private.killed_monster_types = killed.into_iter().collect();
    }

    fn compute_synth_shaped_reward(&self) -> f64 {
        self.private.scout_score as f64
            + 100.0 * self.private.max_level.saturating_sub(1) as f64
            + self.private.purse as f64 / 10.0
            + self.private.player_exp.max(0) as f64 / 20.0
            + 5.0 * self.known_identity_count() as f64
            + 5.0 * self.private.acquired_item_classes.len() as f64
            + 10.0 * self.private.killed_monster_types.len() as f64
    }

    fn known_identity_count(&self) -> usize {
        self.private
            .pot_known
            .iter()
            .filter(|value| **value)
            .count()
            + self
                .private
                .scr_known
                .iter()
                .filter(|value| **value)
                .count()
            + self
                .private
                .ring_known
                .iter()
                .filter(|value| **value)
                .count()
            + self.private.ws_known.iter().filter(|value| **value).count()
    }

    fn achievement_names(&self) -> Vec<String> {
        let mut names: Vec<String> = self
            .private
            .seen_tiles
            .iter()
            .map(|tile_key| format!("scout.tile_seen:{tile_key}"))
            .collect();
        for level in 2..=self.private.max_level {
            names.push(format!("depth.reached_level:{level}"));
        }
        if self.private.purse > 0 {
            names.push("treasure.gold_collected".to_string());
        }
        if self.private.player_exp > 0 {
            names.push("combat.experience_gained".to_string());
        }
        for (family, known_values) in [
            ("potion", &self.private.pot_known),
            ("scroll", &self.private.scr_known),
            ("ring", &self.private.ring_known),
            ("wand", &self.private.ws_known),
        ] {
            for (index, known) in known_values.iter().enumerate() {
                if *known {
                    names.push(format!("identify.known:{family}:{index}"));
                }
            }
        }
        for item_class in &self.private.acquired_item_classes {
            names.push(format!("inventory.acquired_class:{item_class}"));
        }
        for monster_type in &self.private.killed_monster_types {
            names.push(format!("combat.killed_monster_type:{monster_type}"));
        }
        names
    }

    fn progress_metrics_payload(&self) -> Value {
        json!({
            "scout_score": self.private.scout_score,
            "scout_last": self.private.scout_last,
            "synth_shaped_reward": self.private.synth_shaped_reward,
            "synth_shaped_reward_last": self.private.synth_shaped_reward_last,
            "achievement_names": self.achievement_names(),
            "acquired_item_classes": self.private.acquired_item_classes,
            "killed_monster_types": self.private.killed_monster_types,
            "known_identity_count": self.known_identity_count(),
            "max_level": self.private.max_level,
            "purse": self.private.purse,
            "player_exp": self.private.player_exp,
        })
    }

    fn descend(&mut self, action: &str) {
        let (row, col) = self.public.hero;
        if self.terrain(row, col) != '%' {
            self.event(
                "rule_violation",
                "RuleViolation(no_stairs)".to_string(),
                Some(action),
                Some("reject"),
                "warn",
                json!({}),
            );
            return;
        }
        self.apply_source_new_level(action, "descend", self.private.dungeon_level + 1);
        let reward = if self.resolved.objective == "descend" && self.private.dungeon_level > 1 {
            1.0
        } else {
            0.0
        };
        self.private.total_reward += reward;
        self.event(
            "state_transition",
            format!("Descend(level={})", self.private.dungeon_level),
            Some(action),
            Some("descend"),
            "info",
            json!({}),
        );
        self.event(
            "resource_delta",
            format!(
                "RewardDelta({:.2},total={:.2})",
                reward, self.private.total_reward
            ),
            Some(action),
            Some("reward"),
            "info",
            json!({"reward": reward, "total_reward": self.private.total_reward}),
        );
        if reward > 0.0 {
            self.private.terminated = true;
            self.private.terminal_reason = "success".to_string();
            self.event(
                "terminal",
                "Terminal(success)".to_string(),
                Some(action),
                Some("success"),
                "info",
                json!({}),
            );
        }
    }

    fn search(&mut self, action: &str) {
        let (row, col) = self.public.hero;
        let mut rng = RogueRng::new(self.private.rng_seed);
        let result = source_traps::search_hidden_traps(
            &mut rng,
            &mut self.private.source_traps,
            &mut self.private.source_map_cells,
            row as i32,
            col as i32,
            self.private.player_flags,
        );
        self.private.rng_seed = rng.seed;
        if result
            .get("found")
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            self.private.command_running = false;
            self.private.command_count = 0;
        }
        self.private.source_trap_markers = result
            .get("markers")
            .and_then(Value::as_array)
            .map(|markers| {
                markers
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
        for trap in &self.private.source_traps {
            if item_i32(trap, "flags", 0) & source_traps::F_REAL != 0
                && item_i32(trap, "flags", 0) & source_traps::F_SEEN != 0
                && item_char(trap, "ch", '\0') == TRAP
            {
                self.public.visible_items.insert(
                    format!("{},{}", item_i32(trap, "row", 0), item_i32(trap, "col", 0)),
                    TRAP.to_string(),
                );
            }
        }
        let map_cells = self.private.source_map_cells.clone();
        for cell in &map_cells {
            if item_i32(cell, "flags", 0) & source_traps::F_REAL != 0 {
                let row = item_i32(cell, "row", -1);
                let col = item_i32(cell, "col", -1);
                if row >= 0 && col >= 0 {
                    self.set_terrain(row as usize, col as usize, item_char(cell, "ch", ' '));
                }
            }
        }
        self.event(
            "action_applied",
            "SourceSearch()".to_string(),
            Some(action),
            Some("search"),
            "info",
            result,
        );
    }

    fn ascend(&mut self, action: &str) {
        let (row, col) = self.public.hero;
        if self.terrain(row, col) != '%' {
            self.event(
                "rule_violation",
                "RuleViolation(no_stairs_up)".to_string(),
                Some(action),
                Some("reject"),
                "warn",
                json!({}),
            );
            return;
        }
        if !self.private.has_amulet {
            self.event(
                "rule_violation",
                "RuleViolation(up_blocked_no_amulet)".to_string(),
                Some(action),
                Some("reject"),
                "warn",
                json!({}),
            );
            return;
        }
        let next_level = self.private.dungeon_level.saturating_sub(1);
        if next_level == 0 {
            self.private.dungeon_level = 0;
            self.private.terminated = true;
            self.private.terminal_reason = "success".to_string();
            let reward = if self.resolved.objective == "descend" {
                if self.private.dungeon_level > 1 {
                    1.0
                } else {
                    0.0
                }
            } else if self.private.terminal_reason == "success" {
                1.0
            } else {
                0.0
            };
            self.private.total_reward += reward;
            self.event(
                "state_transition",
                "SourceWinner()".to_string(),
                Some(action),
                Some("ascend_win"),
                "info",
                json!({"level": 0, "has_amulet": self.private.has_amulet}),
            );
            self.event(
                "resource_delta",
                format!(
                    "RewardDelta({:.2},total={:.2})",
                    reward, self.private.total_reward
                ),
                Some(action),
                Some("reward"),
                "info",
                json!({"reward": reward, "total_reward": self.private.total_reward}),
            );
            self.event(
                "terminal",
                "Terminal(success)".to_string(),
                Some(action),
                Some("success"),
                "info",
                json!({}),
            );
            return;
        }
        self.apply_source_new_level(action, "ascend", next_level);
        self.event(
            "state_transition",
            format!("Ascend(level={})", self.private.dungeon_level),
            Some(action),
            Some("ascend"),
            "info",
            json!({"level": self.private.dungeon_level, "has_amulet": self.private.has_amulet}),
        );
    }

    fn apply_source_new_level(&mut self, action: &str, reason: &str, level: usize) {
        let max_level = self.private.max_level.max(level);
        let draft = source_level::generate_new_level_slice(
            self.private.rng_seed,
            level as i32,
            max_level as i32,
            self.private.has_amulet,
        );
        self.sync_source_level_draft(&draft);
        self.event(
            "state_transition",
            format!("SourceNewLevel({reason},level={level})"),
            Some(action),
            Some("source_new_level"),
            "info",
            json!({"reason": reason, "level": level, "hero": draft.hero, "rng_seed": draft.rng_seed}),
        );
    }

    fn sync_source_level_draft(&mut self, draft: &source_level::SourceLevelDraft) {
        let mut terrain_rows: Vec<Vec<char>> =
            draft.rows.iter().map(|row| row.chars().collect()).collect();
        let mut visible_items = BTreeMap::new();
        let mut item_values = BTreeMap::new();
        let mut source_level_objects = Vec::new();
        for (index, obj) in draft.level_objects.iter().enumerate() {
            let obj_payload = source_level_object_value(draft.level, index, obj);
            source_level_objects.push(obj_payload);
            let row = obj.pos.y as usize;
            let col = obj.pos.x as usize;
            let key = format!("{},{}", row, col);
            let obj_type = obj.obj_type.chars().next().unwrap_or(' ');
            visible_items.insert(key.clone(), obj_type.to_string());
            if obj_type == GOLD {
                item_values.insert(key, obj.goldval.max(0) as usize);
            }
            if row < terrain_rows.len()
                && col < terrain_rows[row].len()
                && terrain_rows[row][col] == obj_type
            {
                terrain_rows[row][col] = FLOOR;
            }
        }
        self.public.terrain = terrain_rows
            .into_iter()
            .map(|row| row.into_iter().collect())
            .collect();
        self.public.hero = (draft.hero.y as usize, draft.hero.x as usize);
        self.public.visible_items = visible_items;
        self.private.item_values = item_values;
        self.private.source_level_objects = source_level_objects;
        self.private.source_monsters = draft
            .monsters
            .iter()
            .enumerate()
            .map(|(index, monster)| source_level_monster_value(draft.level, index, monster))
            .collect();
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
        self.private.source_traps = draft
            .traps
            .iter()
            .enumerate()
            .map(|(index, trap)| {
                json!({
                    "id": format!("level{}_trap{}", draft.level, index),
                    "row": trap.pos.y,
                    "col": trap.pos.x,
                    "kind": trap.kind,
                    "flags": trap.kind,
                    "ch": "^",
                    "weapon_group": 1,
                })
            })
            .collect();
        self.private.source_rooms = draft.rooms.iter().map(|room| json!(room)).collect();
        self.private.source_passages = draft
            .passages
            .iter()
            .map(|passage| json!(passage))
            .collect();
        self.private.source_map_cells = draft
            .source_map_cells
            .iter()
            .map(source_map_cell_value)
            .collect();
        self.private.source_level_markers = vec![
            format!("new_level:{}", draft.level),
            format!("objects:{}", self.private.source_level_objects.len()),
            format!("monsters:{}", self.private.source_monsters.len()),
            format!("traps:{}", self.private.source_traps.len()),
            format!("map_cells:{}", self.private.source_map_cells.len()),
        ];
        self.private.dungeon_level = draft.level.max(0) as usize;
        self.private.max_level = draft.max_level.max(0) as usize;
        self.private.has_amulet = draft.amulet;
        self.private.rng_seed = draft.rng_seed;
    }

    fn source_level_object_index_at(&self, row: i32, col: i32) -> Option<usize> {
        self.private
            .source_level_objects
            .iter()
            .position(|obj| level_object_pos(obj) == (row, col))
    }

    fn add_source_inventory_object(&mut self, obj: &Value) -> &'static str {
        let obj_type = item_char(obj, "type", '?');
        let which = item_i32(obj, "which", 0);
        let group = item_i32(obj, "group", 0);
        let flags = item_i32(obj, "flags", 0);
        if obj_type == SCROLL && which == S_SCARE && flags & ISFOUND != 0 {
            return "scare_dust";
        }
        if self.private.source_inventory.is_empty() {
            if !self.pack_room(0) {
                return "no_room";
            }
            let mut item = inventory_item_from_level_object(obj);
            set_value_string(&mut item, "packch", &self.next_packch());
            let flags = item_i32(&item, "flags", 0) | ISFOUND;
            set_value_i32(&mut item, "flags", flags);
            self.private.source_inventory.push(item);
            if obj_type == AMULET {
                self.private.has_amulet = true;
            }
            return "added";
        }
        let mut insert_after: Option<usize> = None;
        let mut index = 0usize;
        while index < self.private.source_inventory.len() {
            if item_char(&self.private.source_inventory[index], "type", '?') != obj_type {
                insert_after = Some(index);
                index += 1;
                continue;
            }
            while item_char(&self.private.source_inventory[index], "type", '?') == obj_type
                && item_i32(&self.private.source_inventory[index], "which", 0) != which
            {
                insert_after = Some(index);
                if index + 1 == self.private.source_inventory.len() {
                    break;
                }
                index += 1;
            }
            if item_char(&self.private.source_inventory[index], "type", '?') == obj_type
                && item_i32(&self.private.source_inventory[index], "which", 0) == which
            {
                if is_mult_inventory(obj_type) {
                    if !self.pack_room(0) {
                        return "no_room";
                    }
                    let count = item_i32(&self.private.source_inventory[index], "count", 1) + 1;
                    set_value_i32(&mut self.private.source_inventory[index], "count", count);
                    let new_flags =
                        item_i32(&self.private.source_inventory[index], "flags", 0) | ISFOUND;
                    set_value_i32(
                        &mut self.private.source_inventory[index],
                        "flags",
                        new_flags,
                    );
                    if obj_type == AMULET {
                        self.private.has_amulet = true;
                    }
                    return "added";
                }
                if group != 0 {
                    insert_after = Some(index);
                    while item_char(&self.private.source_inventory[index], "type", '?') == obj_type
                        && item_i32(&self.private.source_inventory[index], "which", 0) == which
                        && item_i32(&self.private.source_inventory[index], "group", 0) != group
                    {
                        insert_after = Some(index);
                        if index + 1 == self.private.source_inventory.len() {
                            break;
                        }
                        index += 1;
                    }
                    if item_char(&self.private.source_inventory[index], "type", '?') == obj_type
                        && item_i32(&self.private.source_inventory[index], "which", 0) == which
                        && item_i32(&self.private.source_inventory[index], "group", 0) == group
                    {
                        if !self.pack_room(-1) {
                            return "no_room";
                        }
                        let count = item_i32(&self.private.source_inventory[index], "count", 1)
                            + item_i32(obj, "count", 1);
                        set_value_i32(&mut self.private.source_inventory[index], "count", count);
                        let new_flags =
                            item_i32(&self.private.source_inventory[index], "flags", 0) | ISFOUND;
                        set_value_i32(
                            &mut self.private.source_inventory[index],
                            "flags",
                            new_flags,
                        );
                        return "added";
                    }
                } else {
                    insert_after = Some(index);
                }
            }
            break;
        }
        let Some(insert_after) = insert_after else {
            return "added";
        };
        if !self.pack_room(0) {
            return "no_room";
        }
        let mut item = inventory_item_from_level_object(obj);
        set_value_string(&mut item, "packch", &self.next_packch());
        let flags = item_i32(&item, "flags", 0) | ISFOUND;
        set_value_i32(&mut item, "flags", flags);
        self.private.source_inventory.insert(insert_after + 1, item);
        if obj_type == AMULET {
            self.private.has_amulet = true;
        }
        "added"
    }

    fn pack_room(&self, adjust: isize) -> bool {
        let occupied = self.current_inpack();
        occupied + 1 + adjust <= MAXPACK as isize
    }

    fn current_inpack(&self) -> isize {
        self.private
            .source_inventory
            .iter()
            .map(|item| {
                let count = item_i32(item, "count", 1);
                if is_mult_inventory(item_char(item, "type", '?')) {
                    count.max(0) as isize
                } else if count > 0 {
                    1
                } else {
                    0
                }
            })
            .sum()
    }

    fn next_packch(&self) -> String {
        let used = self
            .private
            .source_inventory
            .iter()
            .filter_map(|item| item.get("packch").and_then(Value::as_str))
            .filter_map(|text| text.chars().next())
            .collect::<BTreeSet<_>>();
        for offset in 0..26 {
            let candidate = (b'a' + offset as u8) as char;
            if !used.contains(&candidate) {
                return candidate.to_string();
            }
        }
        panic!("Rogue pack_char exhausted");
    }

    fn in_bounds(&self, row: usize, col: usize) -> bool {
        row < self.public.terrain.len() && col < self.public.terrain[0].len()
    }

    fn terrain(&self, row: usize, col: usize) -> char {
        self.public.terrain[row].as_bytes()[col] as char
    }

    fn set_terrain(&mut self, row: usize, col: usize, ch: char) {
        if !self.in_bounds(row, col) {
            return;
        }
        let mut chars: Vec<char> = self.public.terrain[row].chars().collect();
        chars[col] = ch;
        self.public.terrain[row] = chars.into_iter().collect();
    }

    fn blocked(&self, row: usize, col: usize) -> bool {
        !step_ok(self.terrain(row, col))
    }

    fn diag_ok(&self, row: usize, col: usize, nr: usize, nc: usize) -> bool {
        if row.abs_diff(nr) != 1 || col.abs_diff(nc) != 1 {
            return true;
        }
        !self.blocked(row, nc) && !self.blocked(nr, col)
    }

    fn source_room_index_at(&self, row: usize, col: usize) -> Option<usize> {
        self.private
            .source_rooms
            .iter()
            .enumerate()
            .find_map(|(index, room)| {
                if item_i32(room, "flags", 0) & SOURCE_ROOM_ISGONE != 0 {
                    return None;
                }
                let top = item_coord_field(room, "pos", "y", 0);
                let left = item_coord_field(room, "pos", "x", 0);
                let height = item_coord_field(room, "max", "y", 0);
                let width = item_coord_field(room, "max", "x", 0);
                let row = row as i32;
                let col = col as i32;
                if row >= top && row < top + height && col >= left && col < left + width {
                    Some(index)
                } else {
                    None
                }
            })
    }

    fn source_floor_candidate_ok(
        &self,
        row: usize,
        col: usize,
        monst: bool,
        compchar: Option<char>,
        avoid_hero: bool,
    ) -> bool {
        if !self.in_bounds(row, col) {
            return false;
        }
        if avoid_hero && self.public.hero == (row, col) {
            return false;
        }
        let terrain = self.terrain(row, col);
        if monst {
            self.monster_at(row, col).is_none() && step_ok(terrain)
        } else {
            compchar.map(|ch| terrain == ch).unwrap_or(false)
        }
    }

    fn find_source_floor(&mut self, monst: bool, avoid_hero: bool) -> Option<Position> {
        let mut rng = RogueRng::new(self.private.rng_seed);
        let rooms = self.private.source_rooms.clone();
        if !rooms.is_empty() {
            for _ in 0..4096 {
                let room = &rooms[rng.rnd(rooms.len() as i32) as usize];
                if item_i32(room, "flags", 0) & SOURCE_ROOM_ISGONE != 0 {
                    continue;
                }
                let width = item_coord_field(room, "max", "x", 0);
                let height = item_coord_field(room, "max", "y", 0);
                if width <= 2 || height <= 2 {
                    continue;
                }
                let col = item_coord_field(room, "pos", "x", 0) + rng.rnd(width - 2) + 1;
                let row = item_coord_field(room, "pos", "y", 0) + rng.rnd(height - 2) + 1;
                if row < 0 || col < 0 {
                    continue;
                }
                let compchar = if item_i32(room, "flags", 0) & SOURCE_ROOM_ISMAZE != 0 {
                    PASSAGE
                } else {
                    FLOOR
                };
                let row = row as usize;
                let col = col as usize;
                if self.source_floor_candidate_ok(row, col, monst, Some(compchar), avoid_hero) {
                    self.private.rng_seed = rng.seed;
                    return Some((row, col));
                }
            }
        }
        let mut candidates = Vec::new();
        for row in 0..self.public.terrain.len() {
            for col in 0..self.public.terrain[row].len() {
                if self.source_floor_candidate_ok(row, col, monst, Some(FLOOR), avoid_hero) {
                    candidates.push((row, col));
                }
            }
        }
        if candidates.is_empty() {
            self.private.rng_seed = rng.seed;
            return None;
        }
        let selected = candidates[rng.rnd(candidates.len() as i32) as usize];
        self.private.rng_seed = rng.seed;
        Some(selected)
    }

    fn apply_source_teleport(&mut self, action: &str, reason: &str) -> bool {
        let previous = self.public.hero;
        let previous_room = self.source_room_index_at(previous.0, previous.1);
        let Some(destination) = self.find_source_floor(true, false) else {
            return false;
        };
        self.public.hero = destination;
        self.private.player_flags &= !ISHELD;
        self.private.vf_hit = 0;
        self.private.no_move = 0;
        self.private.command_count = 0;
        self.private.command_running = false;
        let changed_room = if previous_room.is_some() {
            self.source_room_index_at(destination.0, destination.1) != previous_room
        } else {
            destination != previous
        };
        self.event(
            "action_applied",
            format!("SourceTeleport({reason},{},{})", destination.0, destination.1),
            Some(action),
            Some("source_teleport"),
            "info",
            json!({"reason": reason, "from": [previous.0, previous.1], "to": [destination.0, destination.1], "changed_room": changed_room}),
        );
        changed_room
    }

    fn event(
        &mut self,
        kind: &str,
        message: String,
        action: Option<&str>,
        transition: Option<&str>,
        severity: &str,
        payload: Value,
    ) {
        self.events.push(EventRecord {
            step_index: self.private.step_index,
            tick: self.private.step_index,
            episode_id: self.resolved.episode_id.clone(),
            kind: kind.to_string(),
            action: action.map(str::to_string),
            transition: transition.map(str::to_string),
            severity: severity.to_string(),
            message,
            payload,
        });
    }

    pub fn valid_actions(&self) -> Vec<&'static str> {
        if self.private.terminated || self.private.truncated {
            Vec::new()
        } else {
            vec![
                "h", "j", "k", "l", "y", "u", "b", "n", ".", ",", ">", "s", "H", "J", "K", "L",
                "Y", "U", "B", "N", "q", "r", "e", "w", "W", "T", "P", "R", "d", "i", "I", "z",
                "t", "f", "F", "m", "<", "?", "/", "c", "o", "D", "S", ")", "]", "=", "@", "^",
                " ",
            ]
        }
    }

    pub fn readout(&self) -> Value {
        let mut rows: Vec<Vec<char>> = self
            .public
            .terrain
            .iter()
            .map(|row| row.chars().collect())
            .collect();
        for (key, item) in &self.public.visible_items {
            let parts: Vec<usize> = key.split(',').map(|part| part.parse().unwrap()).collect();
            rows[parts[0]][parts[1]] = item.chars().next().unwrap();
        }
        for (key, monster) in &self.public.visible_monsters {
            let parts: Vec<usize> = key.split(',').map(|part| part.parse().unwrap()).collect();
            rows[parts[0]][parts[1]] = monster.chars().next().unwrap();
        }
        rows[self.public.hero.0][self.public.hero.1] = '@';
        let ascii = rows
            .into_iter()
            .map(|row| row.into_iter().collect::<String>())
            .collect::<Vec<_>>()
            .join("\n");
        json!({
            "schema": "gamebench.rogue.readout.v1",
            "env_family": Self::ENV_FAMILY,
            "task_id": self.resolved.task_id,
            "public": self.public,
            "private": self.private,
            "progress_metrics": self.progress_metrics_payload(),
            "ascii": ascii,
            "valid_actions": self.valid_actions(),
            "command_dispatch": self.command_dispatch_readout(),
            "grid_hash": self.private.config_hash,
            "nev_cursor": self.events.len()
        })
    }

    pub fn legacy_strings(&self) -> Vec<String> {
        self.events
            .iter()
            .map(|event| event.message.clone())
            .collect()
    }

    pub fn command_dispatch_readout(&self) -> Value {
        json!({
            "schema": "gamebench.rogue.command_state.v1",
            "after": self.private.command_after,
            "running": self.private.command_running,
            "count": self.private.command_count,
            "last_comm": self.private.command_last,
            "direction": self.private.command_direction,
            "runch": self.private.command_runch,
            "to_death": self.private.command_to_death,
            "markers": self.private.command_markers,
        })
    }

    fn apply_command_projection(&mut self, action: &str) -> Value {
        let projection = source_command::runtime_command_projection(
            action,
            self.private.command_running,
            self.private.command_count,
            first_char(&self.private.command_last),
            first_char(&self.private.command_direction),
            self.item_at_hero().is_some(),
            self.private.no_command,
            direction_input(action, 'h'),
            true,
        );
        let final_state = projection.get("final").unwrap();
        self.private.command_after = final_state
            .get("after")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        self.private.command_running = final_state
            .get("running")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        self.private.command_count = final_state
            .get("count")
            .and_then(Value::as_i64)
            .unwrap_or(0) as i32;
        self.private.command_last = final_state
            .get("last_comm")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        self.private.command_direction = final_state
            .get("direction")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        self.private.command_runch = final_state
            .get("runch")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        self.private.command_to_death = final_state
            .get("to_death")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        self.private.no_command = final_state
            .get("no_command")
            .and_then(Value::as_i64)
            .unwrap_or(self.private.no_command as i64) as i32;
        self.private.command_markers = final_state
            .get("markers")
            .and_then(Value::as_array)
            .map(|markers| {
                markers
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
        projection
    }

    fn item_at_hero(&self) -> Option<&String> {
        let (row, col) = self.public.hero;
        self.public.visible_items.get(&format!("{},{}", row, col))
    }

    fn run_source_daemon_phase(&mut self, action: &str, flag: i32, phase: &str) {
        let mut world = self.daemon_world();
        let before = source_daemons::world_json(&world);
        source_daemons::do_daemons(&mut world, flag);
        source_daemons::do_fuses(&mut world, flag);
        let after = source_daemons::world_json(&world);
        self.sync_daemon_world(&world);
        if before != after || !world.markers.is_empty() {
            self.event(
                "action_applied",
                format!("SourceDaemons({phase})"),
                Some(action),
                Some(&format!("source_daemons_{phase}")),
                "info",
                json!({"flag": flag, "world": after}),
            );
        }
        if world.markers.iter().any(|marker| marker == "death:s") {
            self.private.hp = 0;
            self.private.terminated = true;
            self.private.terminal_reason = "death".to_string();
            self.event(
                "terminal",
                "Terminal(death:s)".to_string(),
                Some(action),
                Some("death"),
                "info",
                json!({}),
            );
        }
    }

    fn daemon_world(&self) -> source_daemons::DaemonWorld {
        let mut actions: Vec<source_daemons::DelayedAction> = self
            .private
            .source_daemon_actions
            .iter()
            .map(|action| source_daemons::DelayedAction {
                action: daemon_action_name(&item_str(action, "action", "")),
                action_type: item_i32(action, "type", source_daemons::EMPTY),
                arg: item_i32(action, "arg", 0),
                time: item_i32(action, "time", 0),
            })
            .collect();
        actions.resize(
            source_daemons::MAXDAEMONS,
            source_daemons::DelayedAction {
                action: "",
                action_type: source_daemons::EMPTY,
                arg: 0,
                time: 0,
            },
        );
        source_daemons::DaemonWorld {
            rng: RogueRng::new(self.private.rng_seed),
            stats: source_daemons::SourceStats {
                level: self.private.player_level,
                hp: self.private.hp as i32,
            },
            max_hp: self.private.max_hp as i32,
            quiet: self.private.quiet,
            player_flags: self.private.player_flags,
            left_ring: self.daemon_ring(&self.private.left_ring_id),
            right_ring: self.daemon_ring(&self.private.right_ring_id),
            food_left: self.private.food_left,
            hungry_state: self.private.hungry_state,
            no_command: self.private.no_command,
            amulet: 0,
            running: self.private.command_running,
            to_death: self.private.command_to_death,
            count: self.private.command_count,
            proom_gone: false,
            visible_invisible: 0,
            between: self.private.daemon_between,
            actions,
            markers: Vec::new(),
            trace: serde_json::Map::new(),
        }
    }

    fn sync_daemon_world(&mut self, world: &source_daemons::DaemonWorld) {
        self.private.rng_seed = world.rng.seed;
        self.private.player_level = world.stats.level;
        self.private.hp = world.stats.hp.max(0) as usize;
        self.private.max_hp = world.max_hp.max(0) as usize;
        self.private.quiet = world.quiet;
        self.private.player_flags = world.player_flags;
        self.private.food_left = world.food_left;
        self.private.hungry_state = world.hungry_state;
        self.private.no_command = world.no_command;
        self.private.command_running = world.running;
        self.private.command_to_death = world.to_death;
        self.private.command_count = world.count;
        self.private.daemon_between = world.between;
        self.private.source_daemon_actions = world
            .actions
            .iter()
            .filter(|action| action.action_type != source_daemons::EMPTY)
            .map(|action| json!({"action": action.action, "type": action.action_type, "arg": action.arg, "time": action.time}))
            .collect();
        self.private.source_daemon_markers = world.markers.clone();
    }

    fn daemon_ring(&self, item_id: &str) -> Option<source_daemons::SourceRing> {
        self.ring_item_by_id(item_id)
            .map(|item| source_daemons::SourceRing {
                which: item_i32(&item, "which", 0),
            })
    }

    fn apply_source_fight_command(&mut self, command: char, action: &str) -> bool {
        let direction = first_char(&self.private.command_direction);
        if direction == '\0' {
            self.private.source_combat_markers = vec![format!("no_direction:{command}")];
            self.event(
                "action_applied",
                format!("SourceFightNoDirection({command})"),
                Some(action),
                Some("source_no_direction"),
                "info",
                json!({"command": command.to_string()}),
            );
            return true;
        }
        let Some((dy, dx)) = command_move_delta(direction.to_ascii_lowercase()) else {
            return false;
        };
        let (row, col) = self.public.hero;
        let nr = row as isize + dy;
        let nc = col as isize + dx;
        if nr < 0 || nc < 0 {
            self.private.source_combat_markers = vec![format!("no_monster:{command}")];
            self.event(
                "action_applied",
                format!("SourceFightNoMonster({command})"),
                Some(action),
                Some("source_no_monster"),
                "info",
                json!({"command": command.to_string(), "direction": direction.to_string()}),
            );
            return true;
        }
        if let Some(monster) = self.monster_at(nr as usize, nc as usize) {
            self.fight_monster(action, monster, false);
        } else {
            self.private.source_combat_markers = vec![format!("no_monster:{command}")];
            self.event(
                "action_applied",
                format!("SourceFightNoMonster({command})"),
                Some(action),
                Some("source_no_monster"),
                "info",
                json!({"command": command.to_string(), "direction": direction.to_string()}),
            );
        }
        true
    }

    fn fight_monster(&mut self, action: &str, monster: Value, thrown: bool) -> bool {
        self.fight_monster_with_weapon(action, monster, thrown, None)
    }

    fn fight_monster_with_weapon(
        &mut self,
        action: &str,
        monster: Value,
        thrown: bool,
        weapon: Option<source_fight::FightWeapon>,
    ) -> bool {
        let selected = monster.clone();
        let mut world = source_fight::FightWorld {
            rng: RogueRng::new(self.private.rng_seed),
            player: self.fight_player_stats(),
            player_flags: self.private.player_flags | source_fight::ISRUN,
            current_weapon: self.current_fight_weapon(),
            count: self.private.command_count,
            quiet: 7,
            terse: false,
            to_death: self.private.command_to_death,
            has_hit: false,
            fight_flush: true,
            level: self.private.dungeon_level as i32,
            max_level: self.private.dungeon_level as i32,
            max_hp: self.private.max_hp as i32,
            vf_hit: self.private.vf_hit,
            fallpos_ok: true,
            monster_present: true,
            markers: Vec::new(),
            dropped: Vec::new(),
            trace: serde_json::Map::new(),
        };
        let mut source_monster = fight_monster_object(&monster);
        let returned =
            source_fight::fight(&mut world, &mut source_monster, weapon.as_ref(), thrown);
        self.private.rng_seed = world.rng.seed;
        self.private.player_flags = world.player_flags;
        self.private.strength = world.player.strength;
        self.private.player_exp = world.player.exp;
        self.private.player_level = world.player.level;
        self.private.player_armor = world.player.arm;
        self.private.hp = world.player.hp.max(0) as usize;
        self.private.max_hp = world.max_hp.max(0) as usize;
        self.private.command_count = world.count;
        self.private.command_to_death = world.to_death;
        self.private.vf_hit = world.vf_hit;
        self.private.source_combat_markers = world.markers.clone();
        let monster_id = item_str(&monster, "id", "");
        if world.monster_present && source_monster.stats.hp > 0 {
            self.sync_monster(&monster_id, &source_monster);
        } else {
            self.remove_monster(&monster_id);
        }
        self.event(
            "action_applied",
            format!("SourceFight({monster_id})"),
            Some(action),
            Some("source_fight"),
            "info",
            json!({
                "monster": selected,
                "returned": returned,
                "world": source_fight::world_json(&world),
                "result_monster": source_fight::monster_json(&source_monster),
                "monsters": self.private.source_monsters.clone(),
            }),
        );
        returned
    }

    fn fight_player_stats(&self) -> source_fight::FightStats {
        source_fight::FightStats {
            strength: self.private.strength,
            exp: self.private.player_exp,
            level: self.private.player_level,
            arm: self.private.player_armor,
            hp: self.private.hp as i32,
            damage: self.current_player_damage(),
            max_hp: self.private.max_hp as i32,
            flags: source_fight::ISRUN,
        }
    }

    fn monster_at(&self, row: usize, col: usize) -> Option<Value> {
        self.private
            .source_monsters
            .iter()
            .find(|monster| {
                item_i32(monster, "row", -1) == row as i32
                    && item_i32(monster, "col", -1) == col as i32
            })
            .cloned()
    }

    fn trap_at_index(&self, row: usize, col: usize) -> Option<usize> {
        self.private.source_traps.iter().position(|trap| {
            item_i32(trap, "row", -1) == row as i32 && item_i32(trap, "col", -1) == col as i32
        })
    }

    fn apply_source_trap(&mut self, action: &str, previous: Position) -> Option<i32> {
        let (row, col) = self.public.hero;
        let trap_index = if let Some(index) = self.trap_at_index(row, col) {
            index
        } else if self.terrain(row, col) == TRAP {
            self.private.source_traps.push(json!({
                "id": format!("trap{}", self.private.source_traps.len()),
                "row": row as i32,
                "col": col as i32,
                "kind": source_traps::T_MYST,
                "flags": source_traps::F_REAL | source_traps::T_MYST,
                "ch": "^",
                "weapon_group": 1,
            }));
            self.private.source_traps.len() - 1
        } else {
            return None;
        };
        let trap = self.private.source_traps[trap_index].clone();
        let mut state = source_traps::TrapState {
            rng: RogueRng::new(self.private.rng_seed),
            level: self.private.dungeon_level as i32,
            no_move: self.private.no_move,
            no_command: self.private.no_command,
            player_flags: self.private.player_flags,
            stats: source_traps::TrapStats {
                strength: self.private.strength,
                max_strength: self.private.max_strength,
                level: self.private.player_level,
                arm: self.private.player_armor,
                hp: self.private.hp as i32,
                max_hp: self.private.max_hp as i32,
            },
            cell: source_traps::TrapCell {
                ch: TRAP,
                flags: item_i32(
                    &trap,
                    "flags",
                    source_traps::F_REAL | item_i32(&trap, "kind", source_traps::T_MYST),
                ),
            },
            running: self.private.command_running,
            count: self.private.command_count != 0,
            weapon_group: item_i32(&trap, "weapon_group", 1),
            hero_y: row as i32,
            hero_x: col as i32,
            left_ring: self.trap_ring(&self.private.left_ring_id),
            right_ring: self.trap_ring(&self.private.right_ring_id),
            armor: self.trap_armor(),
            markers: Vec::new(),
            trace: serde_json::Map::new(),
            arrow: None,
            terminal: false,
        };
        let returned = source_traps::be_trapped(&mut state);
        if let Some(object) = self.private.source_traps[trap_index].as_object_mut() {
            object.insert("flags".to_string(), json!(state.cell.flags));
            object.insert("ch".to_string(), json!(state.cell.ch.to_string()));
            object.insert("weapon_group".to_string(), json!(state.weapon_group));
        }
        self.sync_source_trap_state(&state);
        if returned == Some(source_traps::T_DOOR) {
            self.public.hero = previous;
        } else if returned == Some(source_traps::T_TELEP) {
            self.apply_source_teleport(action, "trap");
        }
        self.event(
            "action_applied",
            format!("SourceTrap({})", returned.map(|kind| kind.to_string()).unwrap_or_else(|| "None".to_string())),
            Some(action),
            Some("source_trap"),
            "info",
            json!({"trap": self.private.source_traps[trap_index].clone(), "returned": returned, "state": source_traps::state_json(&state)}),
        );
        if returned == Some(source_traps::T_DOOR) {
            self.apply_source_new_level(action, "trapdoor", self.private.dungeon_level);
        }
        if state.terminal {
            self.private.terminated = true;
            self.private.terminal_reason = "death".to_string();
            self.event(
                "terminal",
                "Terminal(death)".to_string(),
                Some(action),
                Some("death"),
                "info",
                json!({}),
            );
        }
        returned
    }

    fn sync_source_trap_state(&mut self, state: &source_traps::TrapState) {
        self.private.rng_seed = state.rng.seed;
        self.private.dungeon_level = state.level.max(0) as usize;
        self.private.no_move = state.no_move;
        self.private.no_command = state.no_command;
        self.private.player_flags = state.player_flags;
        self.private.strength = state.stats.strength;
        self.private.max_strength = state.stats.max_strength;
        self.private.player_level = state.stats.level;
        self.private.player_armor = state.stats.arm;
        self.private.hp = state.stats.hp.max(0) as usize;
        self.private.max_hp = state.stats.max_hp.max(0) as usize;
        self.private.command_running = state.running;
        if !state.count {
            self.private.command_count = 0;
        }
        self.private.source_trap_markers = state.markers.clone();
        if let Some(arrow) = &state.arrow {
            self.public.visible_items.insert(
                format!("{},{}", arrow.y, arrow.x),
                arrow.obj_type.to_string(),
            );
        }
        if let Some(armor) = &state.armor {
            if let Some(index) = self.inventory_index_by_id(&self.private.current_armor_id) {
                set_inventory_i32(
                    &mut self.private.source_inventory[index],
                    "which",
                    armor.which,
                );
                set_inventory_i32(&mut self.private.source_inventory[index], "arm", armor.arm);
                set_inventory_i32(
                    &mut self.private.source_inventory[index],
                    "flags",
                    armor.flags,
                );
                self.private.player_armor = armor.arm;
            }
        }
    }

    fn trap_ring(&self, item_id: &str) -> Option<source_traps::TrapRing> {
        self.ring_item_by_id(item_id)
            .map(|item| source_traps::TrapRing {
                which: item_i32(&item, "which", 0),
                arm: item_i32(&item, "arm", 0),
            })
    }

    fn trap_armor(&self) -> Option<source_traps::TrapArmor> {
        let index = self.inventory_index_by_id(&self.private.current_armor_id)?;
        let item = &self.private.source_inventory[index];
        Some(source_traps::TrapArmor {
            obj_type: ARMOR,
            which: item_i32(item, "which", 0),
            arm: item_i32(item, "arm", 0),
            flags: item_i32(item, "flags", 0),
        })
    }

    fn sync_monster(&mut self, monster_id: &str, monster: &source_fight::FightMonster) {
        for entry in &mut self.private.source_monsters {
            if item_str(entry, "id", "") == monster_id {
                *entry = monster_value_from_source(entry, monster);
                break;
            }
        }
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
    }

    fn remove_monster(&mut self, monster_id: &str) {
        let removed_type = self
            .private
            .source_monsters
            .iter()
            .find(|monster| item_str(monster, "id", "") == monster_id)
            .map(|monster| item_char(monster, "type", '\0'))
            .unwrap_or('\0');
        if removed_type != '\0' {
            self.record_killed_monster_type(removed_type);
        }
        self.private
            .source_monsters
            .retain(|monster| item_str(monster, "id", "") != monster_id);
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
    }

    fn run_source_monster_turns(&mut self, action: &str) {
        let skip_attack_ids = self.run_source_chase_turns(action);
        if !self.private.terminated && !self.private.truncated {
            self.run_adjacent_monster_attacks(action, &skip_attack_ids);
        }
    }

    fn run_source_chase_turns(&mut self, action: &str) -> BTreeSet<String> {
        let monsters = self.private.source_monsters.clone();
        let mut markers = Vec::new();
        let mut moved_adjacent_ids = BTreeSet::new();
        let mut attack_ready_ids = BTreeSet::new();
        for stale_monster in monsters {
            let monster_id = item_str(&stale_monster, "id", "");
            let Some(monster) = self.monster_by_id(&monster_id) else {
                continue;
            };
            if item_i32(&monster, "hp", 1) <= 0 || self.is_adjacent_to_hero(&monster) {
                continue;
            }
            let mut thing = chase_thing_object(&monster);
            let schedule = source_chase::move_monst_schedule(&mut thing, &[0, 0]);
            let calls = schedule.get("calls").and_then(Value::as_i64).unwrap_or(0) as i32;
            let mut outcomes = Vec::new();
            for _ in 0..calls {
                let Some(current) = self.monster_by_id(&monster_id) else {
                    break;
                };
                if self.is_adjacent_to_hero(&current) {
                    attack_ready_ids.insert(monster_id.clone());
                    break;
                }
                thing.pos = source_chase::Coord {
                    y: item_i32(&current, "row", 0),
                    x: item_i32(&current, "col", 0),
                };
                let hero = source_chase::Coord {
                    y: self.public.hero.0 as i32,
                    x: self.public.hero.1 as i32,
                };
                let target = self.do_chase_target(&current);
                let mut rng = RogueRng::new(self.private.rng_seed);
                let outcome = source_chase::chase(
                    &mut rng,
                    &self.chase_map(&monster_id),
                    &mut thing,
                    target,
                    hero,
                );
                self.private.rng_seed = outcome
                    .get("rng_seed")
                    .and_then(Value::as_i64)
                    .unwrap_or(self.private.rng_seed as i64)
                    as i32;
                let old_row = item_i32(&current, "row", 0);
                let old_col = item_i32(&current, "col", 0);
                let (mut do_world, mut do_monster) =
                    self.do_chase_runtime_state(&current, &outcome);
                let returned = source_do_chase::do_chase(&mut do_world, &mut do_monster);
                self.sync_do_chase_state(&monster_id, &do_monster, &do_world);
                thing = self
                    .monster_by_id(&monster_id)
                    .map(|updated| chase_thing_object(&updated))
                    .unwrap_or(thing);
                let keep = outcome
                    .get("keep_chasing")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                let do_markers = do_world.markers.clone();
                if do_markers.iter().any(|marker| marker == "attack") {
                    attack_ready_ids.insert(monster_id.clone());
                }
                let final_after_do = self
                    .monster_by_id(&monster_id)
                    .unwrap_or_else(|| current.clone());
                if do_markers.iter().any(|marker| marker == "relocate")
                    && self.is_adjacent_to_hero(&final_after_do)
                {
                    moved_adjacent_ids.insert(monster_id.clone());
                }
                let final_monster = self
                    .monster_by_id(&monster_id)
                    .unwrap_or_else(|| current.clone());
                markers.push(format!(
                    "{}:{},{}->{},{}:keep={}:do={}",
                    monster_id,
                    old_row,
                    old_col,
                    item_i32(&final_monster, "row", old_row),
                    item_i32(&final_monster, "col", old_col),
                    keep,
                    do_markers.join(",")
                ));
                outcomes.push(json!({"chase": outcome, "do_chase": source_do_chase::world_json(&do_world), "result_monster": source_do_chase::monster_json(&do_monster), "returned": returned}));
            }
            self.sync_chase_monster(&monster_id, &thing);
            if calls == 0 {
                markers.push(format!("{monster_id}:schedule:0"));
            }
            if !outcomes.is_empty() || calls == 0 {
                self.event(
                    "action_applied",
                    format!("SourceChase({monster_id})"),
                    Some(action),
                    Some("source_chase"),
                    "info",
                    json!({"monster": stale_monster, "schedule": schedule, "outcomes": outcomes, "monsters": self.private.source_monsters.clone()}),
                );
            }
        }
        self.private.source_chase_markers = markers;
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
        moved_adjacent_ids
            .difference(&attack_ready_ids)
            .cloned()
            .collect()
    }

    fn monster_by_id(&self, monster_id: &str) -> Option<Value> {
        self.private
            .source_monsters
            .iter()
            .find(|monster| item_str(monster, "id", "") == monster_id)
            .cloned()
    }

    fn sync_chase_monster(&mut self, monster_id: &str, thing: &source_chase::ChaseThing) {
        for entry in &mut self.private.source_monsters {
            if item_str(entry, "id", "") == monster_id {
                if let Some(object) = entry.as_object_mut() {
                    object.insert("flags".to_string(), json!(thing.flags));
                    object.insert("turn".to_string(), json!(thing.turn));
                    object.insert("disguise".to_string(), json!(thing.disguise.to_string()));
                    object.insert("row".to_string(), json!(thing.pos.y));
                    object.insert("col".to_string(), json!(thing.pos.x));
                }
                break;
            }
        }
    }

    fn do_chase_target(&self, monster: &Value) -> source_chase::Coord {
        let dest = monster_dest_coord_chase(monster, self.public.hero);
        let monster_room = item_i32(monster, "room", 0);
        let dest_kind = item_str(monster, "dest_kind", &item_str(monster, "dest", "hero"));
        let ree_index = if dest_kind == "hero" {
            item_i32(monster, "proom", monster_room)
        } else {
            item_i32(monster, "dest_room", monster_room)
        };
        if monster_room == ree_index {
            return dest;
        }
        let exits = monster_room_exits(monster);
        if exits.is_empty() {
            return dest;
        }
        exits
            .into_iter()
            .min_by_key(|coord| {
                (dest.x - coord.x) * (dest.x - coord.x) + (dest.y - coord.y) * (dest.y - coord.y)
            })
            .unwrap_or(dest)
    }

    fn do_chase_runtime_state(
        &self,
        monster: &Value,
        chase_outcome: &Value,
    ) -> (source_do_chase::DoChaseWorld, source_do_chase::ChaseMonster) {
        let hero = source_do_chase::Coord {
            y: self.public.hero.0 as i32,
            x: self.public.hero.1 as i32,
        };
        let monster_room = item_i32(monster, "room", 0);
        let dest_kind = item_str(monster, "dest_kind", &item_str(monster, "dest", "hero"));
        let dest = monster_dest_coord_do(monster, self.public.hero);
        let dest_room = item_i32(monster, "dest_room", monster_room);
        let proom = item_i32(monster, "proom", monster_room);
        let mut rooms = vec![source_do_chase::ChaseRoom {
            index: monster_room,
            goldval: item_i32(monster, "room_goldval", 1),
            flags: item_i32(monster, "room_flags", 0),
            exits: monster_room_exits(monster)
                .into_iter()
                .map(|coord| source_do_chase::Coord {
                    y: coord.y,
                    x: coord.x,
                })
                .collect(),
        }];
        if !rooms.iter().any(|room| room.index == dest_room) {
            rooms.push(source_do_chase::ChaseRoom {
                index: dest_room,
                goldval: item_i32(monster, "dest_room_goldval", 0),
                flags: item_i32(monster, "dest_room_flags", 0),
                exits: vec![dest],
            });
        }
        if !rooms.iter().any(|room| room.index == proom) {
            rooms.push(source_do_chase::ChaseRoom {
                index: proom,
                goldval: 0,
                flags: 0,
                exits: vec![hero],
            });
        }
        let passage_index = item_i32(monster, "passage_index", 9);
        let objects = self
            .public
            .visible_items
            .iter()
            .filter_map(|(key, item)| {
                let parts: Vec<i32> = key
                    .split(',')
                    .filter_map(|part| part.parse::<i32>().ok())
                    .collect();
                (parts.len() == 2).then(|| source_do_chase::ChaseObject {
                    obj_type: first_char(item),
                    pos: source_do_chase::Coord {
                        y: parts[0],
                        x: parts[1],
                    },
                })
            })
            .collect();
        let chosen = chase_outcome.get("chosen").unwrap_or(&Value::Null);
        let chase_pos = source_do_chase::Coord {
            y: chosen
                .get("y")
                .and_then(Value::as_i64)
                .unwrap_or(item_i32(monster, "row", 0) as i64) as i32,
            x: chosen
                .get("x")
                .and_then(Value::as_i64)
                .unwrap_or(item_i32(monster, "col", 0) as i64) as i32,
        };
        let terrain = vec![(
            source_do_chase::Coord {
                y: item_i32(monster, "row", 0),
                x: item_i32(monster, "col", 0),
            },
            self.terrain(
                item_i32(monster, "row", 0) as usize,
                item_i32(monster, "col", 0) as usize,
            ),
        )];
        let world = source_do_chase::DoChaseWorld {
            rng: RogueRng::new(self.private.rng_seed),
            hero,
            proom,
            rooms,
            passages: vec![source_do_chase::ChaseRoom {
                index: passage_index,
                goldval: 0,
                flags: item_i32(monster, "passage_flags", 0o000002),
                exits: Vec::new(),
            }],
            objects,
            terrain,
            dest_room,
            passage_index,
            chase_keep: chase_outcome
                .get("keep_chasing")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            chase_pos,
            chase_room: item_i32(monster, "chase_room", monster_room),
            attack_return: 0,
            find_dest_kind: item_str(monster, "find_dest_kind", "hero"),
            find_dest_pos: monster_find_dest_coord_do(monster, self.public.hero),
            running: self.private.command_running,
            count: self.private.command_count,
            quiet: 0,
            has_hit: item_bool(monster, "has_hit", false),
            to_death: self.private.command_to_death,
            kamikaze: self.private.kamikaze,
            markers: Vec::new(),
            trace: serde_json::Map::new(),
        };
        let source_monster = source_do_chase::ChaseMonster {
            monster_type: item_char(monster, "type", 'K'),
            pos: source_do_chase::Coord {
                y: item_i32(monster, "row", 0),
                x: item_i32(monster, "col", 0),
            },
            room: monster_room,
            flags: item_i32(monster, "flags", source_fight::ISRUN),
            dest_kind,
            dest_pos: dest,
            pack: monster_pack_do(monster),
        };
        (world, source_monster)
    }

    fn sync_do_chase_state(
        &mut self,
        monster_id: &str,
        monster: &source_do_chase::ChaseMonster,
        world: &source_do_chase::DoChaseWorld,
    ) {
        self.private.rng_seed = world.rng.seed;
        self.private.command_running = world.running;
        self.private.command_count = world.count;
        self.private.command_to_death = world.to_death;
        self.private.kamikaze = world.kamikaze;
        let remaining: BTreeSet<String> = world
            .objects
            .iter()
            .map(|obj| format!("{},{}", obj.pos.y, obj.pos.x))
            .collect();
        let removed: Vec<String> = self
            .public
            .visible_items
            .keys()
            .filter(|key| !remaining.contains(*key))
            .cloned()
            .collect();
        for key in removed {
            self.public.visible_items.remove(&key);
            self.private.item_values.remove(&key);
        }
        for entry in &mut self.private.source_monsters {
            if item_str(entry, "id", "") == monster_id {
                if let Some(object) = entry.as_object_mut() {
                    object.insert("type".to_string(), json!(monster.monster_type.to_string()));
                    object.insert("row".to_string(), json!(monster.pos.y));
                    object.insert("col".to_string(), json!(monster.pos.x));
                    object.insert("room".to_string(), json!(monster.room));
                    object.insert("flags".to_string(), json!(monster.flags));
                    object.insert("dest_kind".to_string(), json!(monster.dest_kind.clone()));
                    object.insert("dest_row".to_string(), json!(monster.dest_pos.y));
                    object.insert("dest_col".to_string(), json!(monster.dest_pos.x));
                    object.insert(
                        "pack".to_string(),
                        json!(monster
                            .pack
                            .iter()
                            .map(source_do_chase::object_json)
                            .collect::<Vec<_>>()),
                    );
                }
                break;
            }
        }
    }

    fn chase_map(&self, selected_id: &str) -> source_chase::ChaseMap {
        let mut terrain = Vec::new();
        for row in 0..NUMLINES {
            let source_row: Vec<char> = self
                .public
                .terrain
                .get(row)
                .map(|text| text.chars().collect())
                .unwrap_or_default();
            for col in 0..NUMCOLS {
                let ch = source_row.get(col).copied().unwrap_or(' ');
                terrain.push((
                    source_chase::Coord {
                        y: row as i32,
                        x: col as i32,
                    },
                    ch,
                ));
            }
        }
        let mut objects = Vec::new();
        for (key, item) in &self.public.visible_items {
            let parts: Vec<i32> = key
                .split(',')
                .filter_map(|part| part.parse::<i32>().ok())
                .collect();
            if parts.len() == 2 {
                objects.push(source_chase::ChaseObject {
                    obj_type: first_char(item),
                    which: 0,
                    pos: source_chase::Coord {
                        y: parts[0],
                        x: parts[1],
                    },
                });
            }
        }
        let monsters = self
            .private
            .source_monsters
            .iter()
            .filter(|monster| {
                item_i32(monster, "hp", 1) > 0 && item_str(monster, "id", "") != selected_id
            })
            .map(chase_thing_object)
            .collect();
        source_chase::ChaseMap {
            terrain,
            objects,
            monsters,
        }
    }

    fn run_adjacent_monster_attacks(&mut self, action: &str, skip_attack_ids: &BTreeSet<String>) {
        let monsters = self.private.source_monsters.clone();
        let mut attack_markers = Vec::new();
        for monster in monsters {
            if skip_attack_ids.contains(&item_str(&monster, "id", "")) {
                continue;
            }
            if !self.is_adjacent_to_hero(&monster) {
                continue;
            }
            let selected = monster.clone();
            let mut source_monster = attack_monster_object(&monster);
            let mut world = self.attack_world();
            let returned = source_attack::attack(&mut world, &mut source_monster);
            self.sync_attack_world(&world);
            if returned < 0 {
                self.remove_monster(&item_str(&monster, "id", ""));
            } else {
                self.sync_attack_monster(&item_str(&monster, "id", ""), &source_monster);
            }
            attack_markers.extend(world.markers.clone());
            self.event(
                "action_applied",
                format!("SourceAttack({})", item_str(&selected, "id", "")),
                Some(action),
                Some("source_attack"),
                "info",
                json!({
                    "monster": selected,
                    "returned": returned,
                    "world": source_attack::world_json(&world),
                    "result_monster": source_attack::monster_json(&source_monster),
                }),
            );
            if self.private.hp == 0 {
                self.private.terminated = true;
                self.private.terminal_reason = "death".to_string();
                self.event(
                    "terminal",
                    "Terminal(death)".to_string(),
                    Some(action),
                    Some("death"),
                    "info",
                    json!({}),
                );
                break;
            }
        }
        if !attack_markers.is_empty() {
            self.private.source_attack_markers = attack_markers;
        }
    }

    fn is_adjacent_to_hero(&self, monster: &Value) -> bool {
        let (row, col) = self.public.hero;
        let monster_row = item_i32(monster, "row", -1000) as isize;
        let monster_col = item_i32(monster, "col", -1000) as isize;
        (monster_row - row as isize)
            .abs()
            .max((monster_col - col as isize).abs())
            == 1
    }

    fn attack_world(&self) -> source_attack::AttackWorld {
        source_attack::AttackWorld {
            rng: RogueRng::new(self.private.rng_seed),
            player: source_attack::Stats {
                strength: self.private.strength,
                exp: self.private.player_exp,
                level: self.private.player_level,
                arm: self.private.player_armor,
                hp: self.private.hp as i32,
                damage: self.private.player_damage.clone(),
                max_hp: self.private.max_hp as i32,
                flags: source_attack::ISRUN,
            },
            player_flags: self.private.player_flags | source_attack::ISRUN,
            current_armor_arm: if self.private.current_armor_id.is_empty() {
                None
            } else {
                Some(self.private.player_armor)
            },
            left_ring: self.attack_ring(&self.private.left_ring_id),
            right_ring: self.attack_ring(&self.private.right_ring_id),
            sustain_strength: self.wearing_ring(2),
            running: self.private.command_running,
            count: self.private.command_count,
            quiet: 0,
            to_death: self.private.command_to_death,
            kamikaze: self.private.kamikaze,
            has_hit: false,
            max_hit: self.private.max_hit,
            no_command: self.private.no_command,
            purse: self.private.purse as i32,
            level: self.private.dungeon_level as i32,
            max_hp: self.private.max_hp as i32,
            vf_hit: self.private.vf_hit,
            fight_flush: true,
            pack: self.attack_pack(),
            markers: Vec::new(),
            trace: serde_json::Map::new(),
        }
    }

    fn sync_attack_world(&mut self, world: &source_attack::AttackWorld) {
        self.private.rng_seed = world.rng.seed;
        self.private.player_flags = world.player_flags;
        self.private.strength = world.player.strength;
        self.private.player_exp = world.player.exp;
        self.private.player_level = world.player.level;
        self.private.player_armor = world.player.arm;
        self.private.hp = world.player.hp.max(0) as usize;
        self.private.max_hp = world.max_hp.max(0) as usize;
        self.private.command_running = world.running;
        self.private.command_count = world.count;
        self.private.command_to_death = world.to_death;
        self.private.kamikaze = world.kamikaze;
        self.private.max_hit = world.max_hit;
        self.private.no_command = world.no_command;
        self.private.purse = world.purse.max(0) as usize;
        self.private.vf_hit = world.vf_hit;
        self.sync_attack_inventory(&world.pack);
    }

    fn sync_attack_monster(&mut self, monster_id: &str, monster: &source_attack::AttackMonster) {
        for entry in &mut self.private.source_monsters {
            if item_str(entry, "id", "") == monster_id {
                set_value_string(entry, "type", &monster.monster_type.to_string());
                set_value_i32(entry, "hp", monster.stats.hp);
                set_value_i32(entry, "max_hp", monster.stats.max_hp);
                set_value_i32(entry, "strength", monster.stats.strength);
                set_value_i32(entry, "exp", monster.stats.exp);
                set_value_i32(entry, "level", monster.stats.level);
                set_value_i32(entry, "arm", monster.stats.arm);
                set_value_string(entry, "damage", &monster.stats.damage);
                set_value_i32(entry, "stats_flags", monster.stats.flags);
                set_value_i32(entry, "flags", monster.flags);
                set_value_string(
                    entry,
                    "disguise",
                    &monster
                        .disguise
                        .map(|ch| ch.to_string())
                        .unwrap_or_else(|| monster.monster_type.to_string()),
                );
                break;
            }
        }
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
    }

    fn attack_ring(&self, item_id: &str) -> Option<source_attack::RingObj> {
        self.ring_item_by_id(item_id)
            .map(|item| source_attack::RingObj {
                which: item_i32(&item, "which", 0),
                arm: item_i32(&item, "arm", 0),
            })
    }

    fn wearing_ring(&self, which: i32) -> bool {
        [
            self.private.left_ring_id.as_str(),
            self.private.right_ring_id.as_str(),
        ]
        .iter()
        .filter_map(|item_id| self.ring_item_by_id(item_id))
        .any(|item| item_i32(&item, "which", 0) == which)
    }

    fn attack_pack(&self) -> Vec<source_attack::AttackItem> {
        self.private
            .source_inventory
            .iter()
            .map(|item| {
                let id = item_str(item, "id", "");
                source_attack::AttackItem {
                    name: id.clone(),
                    obj_type: item_char(item, "type", '?'),
                    magic: is_magic_attack_item(item),
                    equipped: id == self.private.left_ring_id
                        || id == self.private.right_ring_id
                        || id == self.private.current_weapon_id
                        || id == self.private.current_armor_id,
                }
            })
            .collect()
    }

    fn sync_attack_inventory(&mut self, pack: &[source_attack::AttackItem]) {
        let remaining: Vec<String> = pack.iter().map(|item| item.name.clone()).collect();
        let left = self.private.left_ring_id.clone();
        let right = self.private.right_ring_id.clone();
        let weapon = self.private.current_weapon_id.clone();
        let armor = self.private.current_armor_id.clone();
        self.private.source_inventory.retain(|item| {
            let id = item_str(item, "id", "");
            remaining.contains(&id) || id == left || id == right || id == weapon || id == armor
        });
    }

    fn apply_source_item_command(&mut self, command: char, action: &str) -> bool {
        match command {
            'w' => {
                let current_id = self.private.current_weapon_id.clone();
                if let Some(current) = self.inventory_item_by_id(&current_id) {
                    if item_i32(&current, "flags", 0) & ISCURSED != 0 {
                        self.private.source_effect_markers = vec!["cursed".to_string()];
                        self.event(
                            "action_applied",
                            format!("SourceWieldBlocked({})", item_str(&current, "id", "")),
                            Some(action),
                            Some("source_wield_blocked"),
                            "info",
                            json!({"item": current, "markers": self.private.source_effect_markers.clone()}),
                        );
                        return true;
                    }
                }
                let Some(index) = self.inventory_index_for_action(action, Some(WEAPON)) else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                let selected_id = item_str(&selected, "id", "");
                if selected_id == self.private.current_weapon_id {
                    self.private.command_after = false;
                    self.private.source_effect_markers = vec!["in_use".to_string()];
                    self.event(
                        "action_applied",
                        format!("SourceWieldCurrent({selected_id})"),
                        Some(action),
                        Some("source_wield_current"),
                        "info",
                        json!({"item": selected, "markers": self.private.source_effect_markers.clone()}),
                    );
                    return true;
                }
                self.private.current_weapon_id = selected_id.clone();
                self.private.source_effect_markers = vec!["wield".to_string()];
                self.event(
                    "action_applied",
                    format!("SourceWield({selected_id})"),
                    Some(action),
                    Some("source_wield"),
                    "info",
                    json!({"item": selected, "current_weapon_id": self.private.current_weapon_id}),
                );
                true
            }
            'W' => {
                if !self.private.current_armor_id.is_empty() {
                    self.private.command_after = false;
                    let current_id = self.private.current_armor_id.clone();
                    let current = self.inventory_item_by_id(&current_id);
                    self.private.source_effect_markers = vec!["already_wearing".to_string()];
                    self.event(
                        "action_applied",
                        format!("SourceWearBlocked({current_id})"),
                        Some(action),
                        Some("source_wear_blocked"),
                        "info",
                        json!({"item": current, "markers": self.private.source_effect_markers.clone()}),
                    );
                    return true;
                }
                let Some(index) = self.inventory_index_for_action(action, Some(ARMOR)) else {
                    return self.source_no_item(command, action);
                };
                let flags = item_i32(&self.private.source_inventory[index], "flags", 0) | ISKNOW;
                set_inventory_i32(&mut self.private.source_inventory[index], "flags", flags);
                let selected = self.private.source_inventory[index].clone();
                let selected_id = item_str(&selected, "id", "");
                self.private.current_armor_id = selected_id.clone();
                self.private.player_armor = item_i32(&selected, "arm", self.private.player_armor);
                self.private.source_effect_markers = vec!["wear".to_string()];
                self.event(
                    "action_applied",
                    format!("SourceWear({selected_id})"),
                    Some(action),
                    Some("source_wear"),
                    "info",
                    json!({"item": selected, "current_armor_id": self.private.current_armor_id}),
                );
                true
            }
            'T' => {
                let current_id = self.private.current_armor_id.clone();
                let Some(selected) = self.inventory_item_by_id(&current_id) else {
                    self.private.command_after = false;
                    return self.source_no_item(command, action);
                };
                if item_i32(&selected, "flags", 0) & ISCURSED != 0 {
                    self.private.source_effect_markers = vec!["cursed".to_string()];
                    self.event(
                        "action_applied",
                        format!("SourceTakeOffBlocked({})", item_str(&selected, "id", "")),
                        Some(action),
                        Some("source_takeoff_blocked"),
                        "info",
                        json!({"item": selected, "markers": self.private.source_effect_markers.clone()}),
                    );
                    return true;
                }
                let selected_id = item_str(&selected, "id", "");
                self.private.current_armor_id.clear();
                self.private.player_armor = 6;
                self.private.source_effect_markers = vec!["take_off".to_string()];
                self.event(
                    "action_applied",
                    format!("SourceTakeOff({selected_id})"),
                    Some(action),
                    Some("source_takeoff"),
                    "info",
                    json!({"item": selected, "current_armor_id": ""}),
                );
                true
            }
            't' => {
                let Some(index) = self.directional_inventory_index_for_action(action, WEAPON)
                else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                if !self.dropcheck_item(&selected) {
                    self.event(
                        "action_applied",
                        format!("SourceThrowBlocked({})", item_str(&selected, "id", "")),
                        Some(action),
                        Some("source_throw_blocked"),
                        "info",
                        json!({"item": selected, "markers": self.private.source_effect_markers.clone()}),
                    );
                    return true;
                }
                let thrown = self.leave_inventory_for_throw(index);
                let direction = self.missile_direction();
                let (impact_row, impact_col, monster) = self.projectile_impact(direction);
                let mut hit = false;
                if let Some(monster) = monster {
                    hit = self.fight_monster_with_weapon(
                        action,
                        monster,
                        true,
                        self.fight_weapon(Some(thrown.clone())),
                    );
                }
                let fall_result = if hit {
                    None
                } else {
                    Some(self.fall_projectile(thrown.clone(), impact_row, impact_col))
                };
                let mut markers = vec!["leave_pack".to_string(), format!("missile:{direction}")];
                markers.push(if hit {
                    "hit".to_string()
                } else {
                    fall_result.clone().unwrap_or_else(|| "fall".to_string())
                });
                self.private.source_effect_markers = markers.clone();
                self.event(
                    "action_applied",
                    format!("SourceThrow({})", item_str(&thrown, "id", "")),
                    Some(action),
                    Some("source_throw"),
                    "info",
                    json!({
                        "item": selected,
                        "thrown": thrown,
                        "direction": direction.to_string(),
                        "impact": [impact_row, impact_col],
                        "hit": hit,
                        "fall_result": fall_result,
                        "inventory": self.private.source_inventory.clone(),
                        "level_objects": self.private.source_level_objects.clone(),
                        "markers": markers,
                    }),
                );
                true
            }
            'd' => {
                let Some(index) = self.inventory_index_for_action(action, None) else {
                    return self.source_no_item(command, action);
                };
                let (row, col) = self.public.hero;
                let key = format!("{},{}", row, col);
                if !matches!(self.terrain(row, col), FLOOR | PASSAGE)
                    || self.public.visible_items.contains_key(&key)
                {
                    self.private.command_after = false;
                    self.event(
                        "rule_violation",
                        "RuleViolation(drop_occupied)".to_string(),
                        Some(action),
                        Some("drop_blocked"),
                        "warn",
                        json!({"hero": [row, col], "terrain": self.terrain(row, col).to_string()}),
                    );
                    return true;
                }
                let selected = self.private.source_inventory[index].clone();
                if !self.dropcheck_item(&selected) {
                    self.event(
                        "action_applied",
                        format!("SourceDropBlocked({})", item_str(&selected, "id", "")),
                        Some(action),
                        Some("source_drop_blocked"),
                        "info",
                        json!({"item": selected, "markers": self.private.source_effect_markers.clone()}),
                    );
                    return true;
                }
                let mut dropped = self.leave_inventory_for_drop(index);
                if let Some(object) = dropped.as_object_mut() {
                    object.insert("pos".to_string(), json!({"y": row as i32, "x": col as i32}));
                }
                let dropped_type = item_char(&dropped, "type", '?');
                self.private.source_level_objects.insert(0, dropped.clone());
                self.public
                    .visible_items
                    .insert(key, dropped_type.to_string());
                if dropped_type == AMULET {
                    self.private.has_amulet = false;
                }
                self.private.source_effect_markers =
                    vec!["leave_pack".to_string(), "drop".to_string()];
                self.event(
                    "action_applied",
                    format!("SourceDrop({})", item_str(&dropped, "id", "")),
                    Some(action),
                    Some("source_drop"),
                    "info",
                    json!({"item": dropped, "inventory": self.private.source_inventory.clone(), "level_objects": self.private.source_level_objects.clone()}),
                );
                true
            }
            'e' => {
                let Some(index) = self.inventory_index_for_action(action, Some(FOOD)) else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                let mut rng = RogueRng::new(self.private.rng_seed);
                if self.private.food_left < 0 {
                    self.private.food_left = 0;
                }
                let food_add = HUNGERTIME - 200 + rng.rnd(400);
                self.private.food_left = (self.private.food_left + food_add).min(STOMACHSIZE);
                self.private.hungry_state = 0;
                let mut markers = vec![if item_i32(&selected, "which", 0) == 1 {
                    "eat_fruit".to_string()
                } else {
                    "eat_food".to_string()
                }];
                let mut trace = serde_json::Map::new();
                trace.insert("food_add".to_string(), json!(food_add));
                if item_i32(&selected, "which", 0) != 1 {
                    let taste_roll = rng.rnd(100);
                    trace.insert("taste_roll".to_string(), json!(taste_roll));
                    if taste_roll > 70 {
                        self.private.player_exp += 1;
                        markers.push("awful".to_string());
                        let level_add = self.check_player_level(&mut rng);
                        if level_add > 0 {
                            markers.push(format!("welcome:{}", self.private.player_level));
                            trace.insert("level_add".to_string(), json!(level_add));
                        }
                    } else {
                        markers.push("good".to_string());
                    }
                }
                self.private.rng_seed = rng.seed;
                self.private.source_effect_markers = markers.clone();
                self.decrement_or_remove_item(index);
                self.event(
                    "action_applied",
                    format!("SourceEat({})", item_str(&selected, "id", "")),
                    Some(action),
                    Some("source_eat"),
                    "info",
                    json!({"item": selected, "markers": markers, "trace": trace, "inventory": self.private.source_inventory.clone(), "food_left": self.private.food_left}),
                );
                true
            }
            'q' => {
                let Some(index) = self.inventory_index_for_action(action, Some(POTION)) else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                let selected_id = item_str(&selected, "id", "");
                let mut world = source_potions::PotionWorld {
                    rng: RogueRng::new(self.private.rng_seed),
                    player_flags: self.private.player_flags,
                    strength: self.private.strength,
                    max_strength: self.private.max_strength,
                    level: self.private.dungeon_level as i32,
                    exp: self.private.purse as i32,
                    hp: self.private.hp as i32,
                    max_hp: self.private.max_hp as i32,
                    no_command: self.private.no_command,
                    after: self.private.command_after,
                    current_weapon_is_obj: self.private.current_weapon_id == selected_id,
                    left_ring: self.potion_source_ring(&self.private.left_ring_id),
                    right_ring: self.potion_source_ring(&self.private.right_ring_id),
                    pot_known: self.private.pot_known.clone(),
                    actions: Vec::new(),
                    magic_count: 0,
                    new_monsters: 0,
                    invisible_visible: 0,
                    stairs_visible: false,
                    seenstairs: false,
                    proom_gone: false,
                    markers: Vec::new(),
                    trace: serde_json::Map::new(),
                };
                source_potions::quaff(&mut world, Some(potion_object(&selected)));
                self.private.rng_seed = world.rng.seed;
                self.private.player_flags = world.player_flags;
                self.private.strength = world.strength;
                self.private.max_strength = world.max_strength;
                self.private.hp = world.hp.max(0) as usize;
                self.private.max_hp = world.max_hp.max(0) as usize;
                self.private.no_command = world.no_command;
                self.private.command_after = world.after;
                self.private.pot_known = world.pot_known.clone();
                self.private.source_effect_markers = world.markers.clone();
                if !world.current_weapon_is_obj
                    && world
                        .markers
                        .iter()
                        .any(|marker| marker == "unwield_potion")
                {
                    self.private.current_weapon_id.clear();
                }
                self.decrement_or_remove_item(index);
                self.source_effect_event(
                    command,
                    &selected,
                    source_potions::world_json(&world),
                    action,
                );
                true
            }
            'r' => {
                let Some(index) = self.inventory_index_for_action(action, Some(SCROLL)) else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                let selected_id = item_str(&selected, "id", "");
                let mut world = source_scrolls::ScrollWorld {
                    rng: RogueRng::new(self.private.rng_seed),
                    player_flags: self.private.player_flags,
                    no_command: self.private.no_command,
                    current_weapon_is_obj: self.private.current_weapon_id == selected_id,
                    current_weapon: self.scroll_item_from_inventory(
                        self.inventory_item_by_id(&self.private.current_weapon_id),
                    ),
                    current_armor: self.scroll_item_from_inventory(
                        self.inventory_item_by_id(&self.private.current_armor_id),
                    ),
                    left_ring: self.scroll_ring_item(&self.private.left_ring_id),
                    right_ring: self.scroll_ring_item(&self.private.right_ring_id),
                    nearby_monsters: Vec::new(),
                    create_candidates: 0,
                    food_count: self.food_count_for_scrolls(),
                    teleport_room_changed: false,
                    map_cells: Vec::new(),
                    scr_known: self.private.scr_known.clone(),
                    markers: Vec::new(),
                    trace: serde_json::Map::new(),
                };
                source_scrolls::read_scroll(&mut world, Some(scroll_object(&selected)));
                self.private.rng_seed = world.rng.seed;
                self.private.player_flags = world.player_flags;
                self.private.no_command = world.no_command;
                self.private.scr_known = world.scr_known.clone();
                if world.markers.iter().any(|marker| marker == "teleport") {
                    let changed_room = self.apply_source_teleport(action, "scroll");
                    world.teleport_room_changed = changed_room;
                    if changed_room && self.private.scr_known.len() > S_TELEP {
                        self.private.scr_known[S_TELEP] = true;
                        world.scr_known = self.private.scr_known.clone();
                    }
                }
                if !world.current_weapon_is_obj
                    && world
                        .markers
                        .iter()
                        .any(|marker| marker == "unwield_scroll")
                {
                    self.private.current_weapon_id.clear();
                }
                self.sync_scroll_equipment(&world);
                self.apply_source_whatis_for_scroll(&selected, action, &mut world);
                self.private.source_effect_markers = world.markers.clone();
                self.decrement_or_remove_item(index);
                self.source_effect_event(
                    command,
                    &selected,
                    source_scrolls::world_json(&world),
                    action,
                );
                true
            }
            'z' => {
                let Some(index) = self.directional_inventory_index_for_action(action, STICK) else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                let mut obj = stick_object(&selected);
                let target_id = self.zap_target_id();
                let drain_ids: Vec<String> = self
                    .private
                    .source_monsters
                    .iter()
                    .filter(|monster| item_i32(monster, "hp", 1) > 0)
                    .map(|monster| item_str(monster, "id", ""))
                    .collect();
                let mut rng = RogueRng::new(self.private.rng_seed);
                let mut save_throw_success = false;
                if target_id.is_some() && item_i32(&selected, "which", 0) == 6 {
                    save_throw_success =
                        self.source_save_throw(&mut rng, 3, self.private.player_level);
                }
                let mut world = source_sticks::StickWorld {
                    rng,
                    after: self.private.command_after,
                    player_flags: self.private.player_flags,
                    hero_hp: self.private.hp as i32,
                    proom_flags: 0,
                    current_weapon_which: self.current_weapon_which(),
                    target: target_id
                        .as_ref()
                        .and_then(|monster_id| self.monster_by_id(monster_id))
                        .map(|monster| stick_monster_object(&monster)),
                    drain_monsters: self
                        .private
                        .source_monsters
                        .iter()
                        .filter(|monster| item_i32(monster, "hp", 1) > 0)
                        .map(stick_monster_object)
                        .collect(),
                    save_throw_success,
                    ws_known: self.private.ws_known.clone(),
                    markers: Vec::new(),
                    trace: serde_json::Map::new(),
                };
                source_sticks::do_zap(&mut world, &mut obj);
                set_inventory_i32(
                    &mut self.private.source_inventory[index],
                    "charges",
                    obj.charges,
                );
                self.private.rng_seed = world.rng.seed;
                self.private.command_after = world.after;
                self.private.player_flags = world.player_flags;
                self.private.hp = world.hero_hp.max(0) as usize;
                self.private.ws_known = world.ws_known.clone();
                self.private.source_effect_markers = world.markers.clone();
                self.sync_stick_world(target_id.as_deref(), &drain_ids, &world);
                self.apply_stick_relocation(target_id.as_deref(), &world);
                self.apply_stick_bolt(action, target_id.as_deref(), &selected, &world);
                self.source_effect_event(
                    command,
                    &selected,
                    source_sticks::world_json(&world, Some(&obj)),
                    action,
                );
                if self.private.hp == 0
                    && self
                        .private
                        .source_effect_markers
                        .iter()
                        .any(|marker| marker == "bolt_death:b")
                {
                    self.private.terminated = true;
                    self.private.terminal_reason = "death".to_string();
                    self.event(
                        "terminal",
                        "Terminal(death:b)".to_string(),
                        Some(action),
                        Some("death"),
                        "info",
                        json!({}),
                    );
                }
                true
            }
            'P' => {
                let Some(index) = self.unworn_ring_index_for_action(action) else {
                    return self.source_no_item(command, action);
                };
                let selected = self.private.source_inventory[index].clone();
                let mut world = self.ring_world();
                source_rings::ring_on(&mut world, Some(ring_object(&selected)));
                self.sync_ring_world(&world);
                self.private.source_effect_markers = world.markers.clone();
                self.source_effect_event(
                    command,
                    &selected,
                    source_rings::world_json(&world),
                    action,
                );
                true
            }
            'R' => {
                let selected_id = if self.private.left_ring_id.is_empty() {
                    self.private.right_ring_id.clone()
                } else {
                    self.private.left_ring_id.clone()
                };
                let Some(selected) = self.ring_item_by_id(&selected_id) else {
                    return self.source_no_item(command, action);
                };
                let mut world = self.ring_world();
                source_rings::ring_off(&mut world);
                self.sync_ring_world(&world);
                self.private.source_effect_markers = world.markers.clone();
                self.source_effect_event(
                    command,
                    &selected,
                    source_rings::world_json(&world),
                    action,
                );
                true
            }
            _ => false,
        }
    }

    fn source_no_item(&mut self, command: char, action: &str) -> bool {
        self.private.source_effect_markers = vec![format!("no_item:{command}")];
        self.event(
            "action_applied",
            format!("SourceCommandNoItem({command})"),
            Some(action),
            Some("source_no_item"),
            "info",
            json!({"command": command.to_string(), "inventory": self.private.source_inventory.clone()}),
        );
        true
    }

    fn source_effect_event(&mut self, command: char, item: &Value, world: Value, action: &str) {
        self.event(
            "action_applied",
            format!("SourceEffect({},{})", command, item_str(item, "id", "")),
            Some(action),
            Some("source_effect"),
            "info",
            json!({"command": command.to_string(), "item": item, "world": world, "inventory": self.private.source_inventory.clone()}),
        );
    }

    fn apply_source_no_turn_command(
        &mut self,
        command: char,
        action: &str,
        projection: &Value,
    ) -> bool {
        let markers = projection_markers(projection);
        match command {
            'i' | 'I' => {
                let payload = source_inventory_payload(
                    command,
                    action,
                    &self.private.source_inventory,
                    markers,
                );
                self.event(
                    "action_applied",
                    format!("SourceInventory({command})"),
                    Some(action),
                    Some("source_inventory"),
                    "info",
                    payload,
                );
                true
            }
            ')' | ']' | '=' => {
                let slot = current_action_name(command).unwrap_or("");
                let payload = if command == ')' {
                    let item = self.current_item_payload(&self.private.current_weapon_id);
                    let message = source_current_message(item.as_ref(), "wielding", None);
                    json!({
                        "slot": slot,
                        "markers": markers,
                        "item": item,
                        "message": message,
                    })
                } else if command == ']' {
                    let item = self.current_item_payload(&self.private.current_armor_id);
                    let message = source_current_message(item.as_ref(), "wearing", None);
                    json!({
                        "slot": slot,
                        "markers": markers,
                        "item": item,
                        "message": message,
                    })
                } else {
                    let left = self.current_item_payload(&self.private.left_ring_id);
                    let right = self.current_item_payload(&self.private.right_ring_id);
                    let left_message =
                        source_current_message(left.as_ref(), "wearing", Some("on left hand"));
                    let right_message =
                        source_current_message(right.as_ref(), "wearing", Some("on right hand"));
                    json!({
                        "slot": slot,
                        "markers": markers,
                        "left": left,
                        "right": right,
                        "messages": [left_message, right_message],
                    })
                };
                self.event(
                    "action_applied",
                    format!("SourceCurrent({slot})"),
                    Some(action),
                    Some("source_current"),
                    "info",
                    payload,
                );
                true
            }
            '?' => {
                let topic = source_command_tail(action).chars().next().unwrap_or('*');
                let payload = source_help_payload(topic, markers);
                self.event(
                    "action_applied",
                    format!("SourceHelp({topic})"),
                    Some(action),
                    Some("source_help"),
                    "info",
                    payload,
                );
                true
            }
            '/' => {
                let target = source_command_tail(action).chars().next().unwrap_or('\0');
                let target_text = if target == '\0' {
                    String::new()
                } else {
                    target.to_string()
                };
                self.event(
                    "action_applied",
                    format!("SourceIdentify({target_text})"),
                    Some(action),
                    Some("source_identify"),
                    "info",
                    source_identify_payload(target, markers),
                );
                true
            }
            '^' => {
                let mut payload = self.trap_query_payload(action);
                if let Some(object) = payload.as_object_mut() {
                    object.insert("markers".to_string(), json!(markers));
                }
                let direction = payload
                    .get("direction")
                    .and_then(Value::as_str)
                    .unwrap_or("");
                self.event(
                    "action_applied",
                    format!("SourceTrapQuery({direction})"),
                    Some(action),
                    Some("source_trap_query"),
                    "info",
                    payload,
                );
                true
            }
            'D' => {
                let payload =
                    source_discovered_payload(action, &self.resolved, &mut self.private, markers);
                self.event(
                    "action_applied",
                    "SourceDiscovered()".to_string(),
                    Some(action),
                    Some("source_discovered"),
                    "info",
                    payload,
                );
                true
            }
            '@' => {
                self.event(
                    "action_applied",
                    "SourceStatus()".to_string(),
                    Some(action),
                    Some("source_status"),
                    "info",
                    source_status_payload(&self.private, markers),
                );
                true
            }
            'S' => {
                let filename = source_command_tail(action).trim().to_string();
                if filename.is_empty() || filename == "\x1b" {
                    self.event(
                        "action_applied",
                        "SourceSavePrompt()".to_string(),
                        Some(action),
                        Some("source_save_prompt"),
                        "info",
                        json!({"markers": markers, "requires_file_name": true, "cancelled": filename == "\x1b"}),
                    );
                    return true;
                }
                let save_file = source_state::runtime_source_save_file_projection(
                    &self.resolved,
                    &self.public,
                    &self.private,
                    self.events.len(),
                    &filename,
                );
                self.event(
                    "action_applied",
                    format!("SourceSaveGame({filename})"),
                    Some(action),
                    Some("source_save"),
                    "info",
                    json!({"file_name": filename, "markers": markers, "save_file": save_file, "exit": true}),
                );
                self.private.terminated = true;
                self.private.terminal_reason = "save".to_string();
                self.event(
                    "terminal",
                    "Terminal(save)".to_string(),
                    Some(action),
                    Some("save"),
                    "info",
                    json!({}),
                );
                true
            }
            'Q' => {
                self.event(
                    "action_applied",
                    "SourceQuit()".to_string(),
                    Some(action),
                    Some("source_quit"),
                    "info",
                    json!({"markers": markers}),
                );
                self.private.terminated = true;
                self.private.terminal_reason = "quit".to_string();
                self.event(
                    "terminal",
                    "Terminal(quit)".to_string(),
                    Some(action),
                    Some("quit"),
                    "info",
                    json!({}),
                );
                true
            }
            ' ' => {
                self.event(
                    "action_applied",
                    "SourceLegalIllegal()".to_string(),
                    Some(action),
                    Some("source_no_turn"),
                    "info",
                    json!({"markers": markers}),
                );
                true
            }
            '\x1b' => {
                self.event(
                    "action_applied",
                    "SourceEscape()".to_string(),
                    Some(action),
                    Some("source_no_turn"),
                    "info",
                    json!({"markers": markers}),
                );
                true
            }
            _ => {
                let Some(action_name) = no_turn_action_name(command) else {
                    return false;
                };
                self.event(
                    "action_applied",
                    format!("SourceNoTurn({action_name})"),
                    Some(action),
                    Some(&format!("source_{action_name}")),
                    "info",
                    json!({"command": command.to_string(), "action": action_name, "markers": markers}),
                );
                true
            }
        }
    }

    fn current_item_payload(&self, item_id: &str) -> Option<Value> {
        self.inventory_item_by_id(item_id)
    }

    fn trap_query_payload(&mut self, action: &str) -> Value {
        let direction = direction_input(action, 'h');
        let Some((dy, dx)) = command_move_delta(direction) else {
            return json!({"direction": direction.to_string(), "found": false, "trap": Value::Null});
        };
        let (row, col) = self.public.hero;
        let target_row = row as isize + dy;
        let target_col = col as isize + dx;
        if target_row < 0 || target_col < 0 {
            return json!({"direction": direction.to_string(), "found": false, "trap": Value::Null});
        }
        let target_row = target_row as usize;
        let target_col = target_col as usize;
        let Some(index) = self.trap_at_index(target_row, target_col) else {
            return json!({"direction": direction.to_string(), "found": false, "trap": Value::Null});
        };
        let flags = item_i32(&self.private.source_traps[index], "flags", 0) | TRAP_F_SEEN;
        set_value_i32(&mut self.private.source_traps[index], "flags", flags);
        let trap = self.private.source_traps[index].clone();
        json!({"direction": direction.to_string(), "found": true, "trap": trap, "kind": flags & TRAP_F_TMASK})
    }

    fn first_inventory_index(&self, obj_type: char) -> Option<usize> {
        self.private.source_inventory.iter().position(|item| {
            item_char(item, "type", '?') == obj_type && item_i32(item, "count", 1) > 0
        })
    }

    fn inventory_index_for_action(&self, action: &str, obj_type: Option<char>) -> Option<usize> {
        let packch = packch_from_action(action);
        if packch != '\0' {
            return self.private.source_inventory.iter().position(|item| {
                item_char(item, "packch", '\0') == packch
                    && item_i32(item, "count", 1) > 0
                    && obj_type
                        .map(|kind| item_char(item, "type", '?') == kind)
                        .unwrap_or(true)
            });
        }
        if let Some(kind) = obj_type {
            self.first_inventory_index(kind)
        } else {
            self.first_any_inventory_index()
        }
    }

    fn apply_source_whatis_for_scroll(
        &mut self,
        selected: &Value,
        action: &str,
        world: &mut source_scrolls::ScrollWorld,
    ) {
        let Some(id_type) = source_whatis_type_for_scroll(item_i32(selected, "which", -1)) else {
            return;
        };
        let consumed_id = item_str(selected, "id", "");
        let consumed_removed = item_i32(selected, "count", 1) <= 1;
        let Some(index) = self.source_whatis_inventory_index_for_action(
            action,
            id_type,
            &consumed_id,
            consumed_removed,
        ) else {
            world
                .markers
                .push(format!("whatis_no_item:{}", source_whatis_marker(id_type)));
            world.trace.insert("whatis_item".to_string(), Value::Null);
            world.trace.insert(
                "whatis_type".to_string(),
                source_whatis_trace_value(id_type),
            );
            return;
        };
        let obj_type = item_char(&self.private.source_inventory[index], "type", '?');
        let which = item_i32(&self.private.source_inventory[index], "which", 0);
        let flags = item_i32(&self.private.source_inventory[index], "flags", 0) | ISKNOW;
        set_value_i32(&mut self.private.source_inventory[index], "flags", flags);
        self.source_identify_known_type(obj_type, which);
        if obj_type == SCROLL {
            world.scr_known = self.private.scr_known.clone();
        }
        let item = self.private.source_inventory[index].clone();
        world
            .markers
            .push(format!("whatis_selected:{obj_type}:{which}"));
        world.markers.push(format!("identified:{obj_type}:{which}"));
        world.trace.insert("whatis_item".to_string(), item);
        world.trace.insert(
            "whatis_type".to_string(),
            source_whatis_trace_value(id_type),
        );
    }

    fn source_whatis_inventory_index_for_action(
        &self,
        action: &str,
        id_type: SourceWhatisType,
        consumed_id: &str,
        consumed_removed: bool,
    ) -> Option<usize> {
        let packch = source_whatis_packch_from_action(action);
        if packch != '\0' {
            return self.private.source_inventory.iter().position(|item| {
                item_char(item, "packch", '\0') == packch
                    && source_whatis_candidate(item, id_type, consumed_id, consumed_removed)
            });
        }
        self.private
            .source_inventory
            .iter()
            .position(|item| source_whatis_candidate(item, id_type, consumed_id, consumed_removed))
    }

    fn source_identify_known_type(&mut self, obj_type: char, which: i32) {
        let Ok(index) = usize::try_from(which) else {
            return;
        };
        match obj_type {
            POTION if index < self.private.pot_known.len() => self.private.pot_known[index] = true,
            SCROLL if index < self.private.scr_known.len() => self.private.scr_known[index] = true,
            RING if index < self.private.ring_known.len() => self.private.ring_known[index] = true,
            STICK if index < self.private.ws_known.len() => self.private.ws_known[index] = true,
            _ => {}
        }
    }

    fn directional_inventory_index_for_action(
        &self,
        action: &str,
        obj_type: char,
    ) -> Option<usize> {
        let packch = directional_packch_from_action(action);
        if packch != '\0' {
            return self.private.source_inventory.iter().position(|item| {
                item_char(item, "packch", '\0') == packch
                    && item_i32(item, "count", 1) > 0
                    && item_char(item, "type", '?') == obj_type
            });
        }
        self.first_inventory_index(obj_type)
    }

    fn first_any_inventory_index(&self) -> Option<usize> {
        self.private
            .source_inventory
            .iter()
            .position(|item| item_i32(item, "count", 1) > 0)
    }

    fn inventory_index_by_id(&self, item_id: &str) -> Option<usize> {
        if item_id.is_empty() {
            return None;
        }
        self.private
            .source_inventory
            .iter()
            .position(|item| item_str(item, "id", "") == item_id)
    }

    fn first_unworn_ring_index(&self) -> Option<usize> {
        self.private.source_inventory.iter().position(|item| {
            item_char(item, "type", '?') == RING
                && item_str(item, "id", "") != self.private.left_ring_id
                && item_str(item, "id", "") != self.private.right_ring_id
        })
    }

    fn unworn_ring_index_for_action(&self, action: &str) -> Option<usize> {
        let packch = packch_from_action(action);
        if packch != '\0' {
            return self.private.source_inventory.iter().position(|item| {
                item_char(item, "packch", '\0') == packch
                    && item_char(item, "type", '?') == RING
                    && item_i32(item, "count", 1) > 0
                    && item_str(item, "id", "") != self.private.left_ring_id
                    && item_str(item, "id", "") != self.private.right_ring_id
            });
        }
        self.first_unworn_ring_index()
    }

    fn inventory_item_by_id(&self, item_id: &str) -> Option<Value> {
        self.inventory_index_by_id(item_id)
            .map(|index| self.private.source_inventory[index].clone())
    }

    fn ring_item_by_id(&self, item_id: &str) -> Option<Value> {
        self.inventory_item_by_id(item_id)
    }

    fn decrement_or_remove_item(&mut self, index: usize) {
        let count = item_i32(&self.private.source_inventory[index], "count", 1);
        if count > 1 {
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "count",
                count - 1,
            );
        } else {
            self.private.source_inventory.remove(index);
        }
    }

    fn dropcheck_item(&mut self, item: &Value) -> bool {
        let item_id = item_str(item, "id", "");
        if item_id == self.private.current_weapon_id {
            if item_i32(item, "flags", 0) & ISCURSED != 0 {
                self.private.source_effect_markers = vec!["cursed".to_string()];
                return false;
            }
            self.private.current_weapon_id.clear();
            return true;
        }
        if item_id == self.private.current_armor_id {
            if item_i32(item, "flags", 0) & ISCURSED != 0 {
                self.private.source_effect_markers = vec!["cursed".to_string()];
                return false;
            }
            self.private.current_armor_id.clear();
            self.private.player_armor = 6;
            return true;
        }
        if item_id != self.private.left_ring_id && item_id != self.private.right_ring_id {
            return true;
        }
        let mut world = self.ring_world();
        let ok = source_rings::dropcheck(&mut world, Some(ring_object(item)));
        self.sync_ring_world(&world);
        self.private.source_effect_markers = world.markers.clone();
        ok
    }

    fn leave_inventory_for_drop(&mut self, index: usize) -> Value {
        let item = self.private.source_inventory[index].clone();
        let obj_type = item_char(&item, "type", '?');
        let all_items = !is_mult_inventory(obj_type);
        let count = item_i32(&item, "count", 1);
        if count > 1 && !all_items {
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "count",
                count - 1,
            );
            let mut dropped = item;
            set_value_i32(&mut dropped, "count", 1);
            let dropped_id = format!(
                "{}_drop{}",
                item_str(&dropped, "id", ""),
                self.private.step_index
            );
            set_value_string(&mut dropped, "id", &dropped_id);
            dropped
        } else {
            self.private.source_inventory.remove(index)
        }
    }

    fn leave_inventory_for_throw(&mut self, index: usize) -> Value {
        let item = self.private.source_inventory[index].clone();
        let count = item_i32(&item, "count", 1);
        if count > 1 {
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "count",
                count - 1,
            );
            let mut thrown = item;
            set_value_i32(&mut thrown, "count", 1);
            let thrown_id = format!(
                "{}_throw{}",
                item_str(&thrown, "id", ""),
                self.private.step_index
            );
            set_value_string(&mut thrown, "id", &thrown_id);
            thrown
        } else {
            self.private.source_inventory.remove(index)
        }
    }

    fn check_player_level(&mut self, rng: &mut RogueRng) -> i32 {
        let mut next_level = 1;
        for threshold in source_fight::E_LEVELS {
            if threshold == 0 || threshold > self.private.player_exp {
                break;
            }
            next_level += 1;
        }
        let old_level = self.private.player_level;
        self.private.player_level = next_level;
        if next_level <= old_level {
            return 0;
        }
        let level_add = rng.roll(next_level - old_level, 10);
        self.private.max_hp += level_add.max(0) as usize;
        self.private.hp += level_add.max(0) as usize;
        level_add
    }

    fn current_player_damage(&self) -> String {
        self.inventory_item_by_id(&self.private.current_weapon_id)
            .map(|weapon| item_str(&weapon, "damage", &self.private.player_damage))
            .unwrap_or_else(|| self.private.player_damage.clone())
    }

    fn current_fight_weapon(&self) -> Option<source_fight::FightWeapon> {
        self.fight_weapon(self.inventory_item_by_id(&self.private.current_weapon_id))
    }

    fn fight_weapon(&self, item: Option<Value>) -> Option<source_fight::FightWeapon> {
        let item = item?;
        if item_char(&item, "type", '?') != WEAPON {
            return None;
        }
        Some(source_fight::FightWeapon {
            which: item_i32(&item, "which", 0),
            hplus: item_i32(&item, "hplus", 0),
            dplus: item_i32(&item, "dplus", 0),
            damage: item_str(&item, "damage", "1x1"),
            hurl_damage: item_str(&item, "hurldmg", &item_str(&item, "hurl_damage", "1x1")),
            launch: item_i32(&item, "launch", -1),
            flags: item_i32(&item, "flags", 0),
        })
    }

    fn missile_direction(&self) -> char {
        let fallback = first_char(&self.private.command_direction);
        self.private
            .command_markers
            .iter()
            .find_map(|marker| marker.strip_prefix("missile:"))
            .and_then(|text| text.chars().next())
            .or_else(|| {
                if fallback == '\0' {
                    None
                } else {
                    Some(fallback)
                }
            })
            .unwrap_or('h')
    }

    fn projectile_impact(&self, direction: char) -> (i32, i32, Option<Value>) {
        let Some((dy, dx)) = command_move_delta(direction) else {
            let (row, col) = self.public.hero;
            return (row as i32, col as i32, None);
        };
        let (row, col) = self.public.hero;
        let mut nr = row as isize;
        let mut nc = col as isize;
        loop {
            nr += dy;
            nc += dx;
            if nr < 0 || nc < 0 || !self.in_bounds(nr as usize, nc as usize) {
                return (nr as i32, nc as i32, None);
            }
            let terrain = self.terrain(nr as usize, nc as usize);
            if !step_ok(terrain) || terrain == DOOR {
                return (
                    nr as i32,
                    nc as i32,
                    self.monster_at(nr as usize, nc as usize),
                );
            }
            if let Some(monster) = self.monster_at(nr as usize, nc as usize) {
                return (nr as i32, nc as i32, Some(monster));
            }
        }
    }

    fn fall_projectile(&mut self, mut item: Value, impact_row: i32, impact_col: i32) -> String {
        let mut rng = RogueRng::new(self.private.rng_seed);
        let mut count = 0;
        let mut chosen: Option<(usize, usize)> = None;
        let hero = self.public.hero;
        for row in (impact_row - 1)..=(impact_row + 1) {
            for col in (impact_col - 1)..=(impact_col + 1) {
                if row < 0 || col < 0 {
                    continue;
                }
                let row_usize = row as usize;
                let col_usize = col as usize;
                if (row_usize, col_usize) == hero || !self.in_bounds(row_usize, col_usize) {
                    continue;
                }
                let key = format!("{row},{col}");
                if !matches!(self.terrain(row_usize, col_usize), FLOOR | PASSAGE)
                    || self.public.visible_items.contains_key(&key)
                    || self.monster_at(row_usize, col_usize).is_some()
                {
                    continue;
                }
                count += 1;
                if rng.rnd(count) == 0 {
                    chosen = Some((row_usize, col_usize));
                }
            }
        }
        self.private.rng_seed = rng.seed;
        let Some((row, col)) = chosen else {
            return "vanish".to_string();
        };
        if let Some(object) = item.as_object_mut() {
            object.insert("pos".to_string(), json!({"y": row as i32, "x": col as i32}));
        }
        let obj_type = item_char(&item, "type", '?');
        self.private.source_level_objects.insert(0, item);
        self.public
            .visible_items
            .insert(format!("{row},{col}"), obj_type.to_string());
        "fall".to_string()
    }

    fn zap_direction(&self) -> char {
        let fallback = first_char(&self.private.command_direction);
        self.private
            .command_markers
            .iter()
            .find_map(|marker| marker.strip_prefix("do_zap:"))
            .and_then(|text| text.chars().next())
            .or_else(|| {
                if fallback == '\0' {
                    None
                } else {
                    Some(fallback)
                }
            })
            .unwrap_or('h')
    }

    fn zap_target_id(&self) -> Option<String> {
        let (dy, dx) = command_move_delta(self.zap_direction())?;
        let (row, col) = self.public.hero;
        let mut nr = row as isize + dy;
        let mut nc = col as isize + dx;
        while nr >= 0 && nc >= 0 && self.in_bounds(nr as usize, nc as usize) {
            if !step_ok(self.terrain(nr as usize, nc as usize)) {
                return None;
            }
            if let Some(monster) = self.monster_at(nr as usize, nc as usize) {
                if item_i32(&monster, "hp", 1) > 0 {
                    return Some(item_str(&monster, "id", ""));
                }
            }
            nr += dy;
            nc += dx;
        }
        None
    }

    fn sync_stick_world(
        &mut self,
        target_id: Option<&str>,
        drain_ids: &[String],
        world: &source_sticks::StickWorld,
    ) {
        if let (Some(monster_id), Some(monster)) = (target_id, world.target.as_ref()) {
            self.sync_stick_monster(monster_id, monster);
        }
        for (monster_id, monster) in drain_ids.iter().zip(world.drain_monsters.iter()) {
            self.sync_stick_monster(monster_id, monster);
        }
        self.private
            .source_monsters
            .retain(|monster| item_i32(monster, "hp", 1) > 0);
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
    }

    fn apply_stick_relocation(
        &mut self,
        target_id: Option<&str>,
        world: &source_sticks::StickWorld,
    ) {
        let Some(target_id) = target_id else {
            return;
        };
        let mut destination = None;
        if world
            .markers
            .iter()
            .any(|marker| marker == "relocate:random_floor")
        {
            destination = self.find_source_floor(true, true);
        } else if world
            .markers
            .iter()
            .any(|marker| marker == "relocate:adjacent")
        {
            if let Some((dy, dx)) = command_move_delta(self.zap_direction()) {
                let (row, col) = self.public.hero;
                let nr = row as isize + dy;
                let nc = col as isize + dx;
                if nr >= 0 && nc >= 0 && self.in_bounds(nr as usize, nc as usize) {
                    destination = Some((nr as usize, nc as usize));
                }
            }
        }
        let Some((row, col)) = destination else {
            return;
        };
        for monster in &mut self.private.source_monsters {
            if item_str(monster, "id", "") == target_id {
                set_value_i32(monster, "row", row as i32);
                set_value_i32(monster, "col", col as i32);
                break;
            }
        }
        self.public.visible_monsters = visible_monsters(&self.private.source_monsters);
    }

    fn apply_stick_bolt(
        &mut self,
        action: &str,
        target_id: Option<&str>,
        item: &Value,
        world: &source_sticks::StickWorld,
    ) {
        let which = item_i32(item, "which", 0);
        if !matches!(which, WS_ELECT | WS_FIRE | WS_COLD)
            || !world
                .markers
                .iter()
                .any(|marker| marker.starts_with("fire_bolt:"))
        {
            return;
        }
        let Some(target_id) = target_id else {
            if !self.apply_reflected_bolt_hero_hit() {
                self.private
                    .source_effect_markers
                    .push("bolt_vanishes".to_string());
            }
            return;
        };
        let Some(monster) = self.monster_by_id(target_id) else {
            if !self.apply_reflected_bolt_hero_hit() {
                self.private
                    .source_effect_markers
                    .push("bolt_vanishes".to_string());
            }
            return;
        };
        let bolt_name = match which {
            WS_ELECT => "bolt",
            WS_FIRE => "flame",
            _ => "ice",
        };
        let mut rng = RogueRng::new(self.private.rng_seed);
        let saved = self.source_save_throw(&mut rng, VS_MAGIC, item_i32(&monster, "level", 1));
        self.private.rng_seed = rng.seed;
        if saved {
            self.private
                .source_effect_markers
                .push(format!("bolt_saved:{target_id}"));
            return;
        }
        if bolt_name == "flame" && item_char(&monster, "type", '?') == 'D' {
            self.private
                .source_effect_markers
                .push(format!("bolt_bounced:{target_id}"));
            return;
        }
        let hit = self.fight_monster_with_weapon(
            action,
            monster,
            true,
            Some(bolt_fight_weapon(bolt_name)),
        );
        self.private.source_effect_markers.push(if hit {
            format!("bolt_hit:{target_id}")
        } else {
            format!("bolt_missed:{target_id}")
        });
    }

    fn apply_reflected_bolt_hero_hit(&mut self) -> bool {
        let Some((mut dy, mut dx)) = command_move_delta(self.zap_direction()) else {
            return false;
        };
        let (hero_row, hero_col) = self.public.hero;
        let mut row = hero_row as isize;
        let mut col = hero_col as isize;
        let mut hit_hero = false;
        let mut changed = false;
        let mut bounced = false;
        let mut steps = 0usize;
        let mut guard = 0usize;
        while steps < BOLT_LENGTH && guard < BOLT_LENGTH * 6 {
            guard += 1;
            row += dy;
            col += dx;
            let terrain = if row >= 0 && col >= 0 && self.in_bounds(row as usize, col as usize) {
                self.terrain(row as usize, col as usize)
            } else {
                ' '
            };
            if matches!(terrain, DOOR | '|' | '-' | ' ') {
                if !changed {
                    hit_hero = !hit_hero;
                }
                changed = false;
                dy = -dy;
                dx = -dx;
                bounced = true;
                self.private
                    .source_effect_markers
                    .push("bolt_bounce".to_string());
                continue;
            }
            if hit_hero && row == hero_row as isize && col == hero_col as isize {
                let mut rng = RogueRng::new(self.private.rng_seed);
                let saved = self.source_player_magic_save(&mut rng);
                self.private.rng_seed = rng.seed;
                if saved {
                    self.private
                        .source_effect_markers
                        .push("bolt_hero_saved".to_string());
                    return true;
                }
                let damage = rng.roll(6, 6).max(0) as usize;
                self.private.rng_seed = rng.seed;
                self.private.hp = self.private.hp.saturating_sub(damage);
                self.private
                    .source_effect_markers
                    .push(format!("bolt_hero_hit:{damage}"));
                if self.private.hp == 0 {
                    self.private
                        .source_effect_markers
                        .push("bolt_death:b".to_string());
                }
                return true;
            }
            steps += 1;
        }
        bounced
    }

    fn source_player_magic_save(&self, rng: &mut RogueRng) -> bool {
        let mut adjusted = VS_MAGIC;
        let left = self.ring_item_by_id(&self.private.left_ring_id);
        let right = self.ring_item_by_id(&self.private.right_ring_id);
        for ring in [&left, &right].into_iter().flatten() {
            if item_i32(ring, "which", 0) == R_PROTECT {
                adjusted -= item_i32(ring, "arm", 0);
            }
        }
        self.source_save_throw(rng, adjusted, self.private.player_level)
    }

    fn sync_stick_monster(&mut self, monster_id: &str, monster: &source_sticks::StickMonster) {
        for entry in &mut self.private.source_monsters {
            if item_str(entry, "id", "") != monster_id {
                continue;
            }
            set_value_string(entry, "type", &monster.monster_type.to_string());
            set_value_i32(entry, "hp", monster.hp);
            set_value_i32(entry, "flags", monster.flags);
            set_value_string(
                entry,
                "disguise",
                &monster
                    .disguise
                    .map(|ch| ch.to_string())
                    .unwrap_or_else(|| monster.monster_type.to_string()),
            );
            set_value_string(entry, "oldch", &monster.oldch.to_string());
            if let Some(object) = entry.as_object_mut() {
                object.insert("turn".to_string(), json!(monster.turn));
            }
            if monster.dest_hero {
                let (row, col) = self.public.hero;
                set_value_string(entry, "dest_kind", "hero");
                set_value_i32(entry, "dest_row", row as i32);
                set_value_i32(entry, "dest_col", col as i32);
            }
            break;
        }
    }

    fn current_weapon_which(&self) -> Option<i32> {
        self.inventory_item_by_id(&self.private.current_weapon_id)
            .map(|weapon| item_i32(&weapon, "which", 0))
    }

    fn source_save_throw(&self, rng: &mut RogueRng, which: i32, level: i32) -> bool {
        let need = 14 + which - level / 2;
        let roll = rng.roll(1, 20);
        roll >= need
    }

    fn potion_source_ring(&self, item_id: &str) -> Option<source_potions::SourceRing> {
        self.ring_item_by_id(item_id)
            .map(|item| source_potions::SourceRing {
                which: item_i32(&item, "which", 0),
                arm: item_i32(&item, "arm", 0),
            })
    }

    fn scroll_item_from_inventory(
        &self,
        item: Option<Value>,
    ) -> Option<source_scrolls::ScrollItem> {
        let item = item?;
        Some(source_scrolls::ScrollItem {
            obj_type: item_char(&item, "type", '?'),
            which: item_i32(&item, "which", 0),
            flags: item_i32(&item, "flags", 0),
            arm: item_i32(&item, "arm", 0),
            hplus: item_i32(&item, "hplus", 0),
            dplus: item_i32(&item, "dplus", 0),
        })
    }

    fn sync_scroll_equipment(&mut self, world: &source_scrolls::ScrollWorld) {
        if let (Some(index), Some(armor)) = (
            self.inventory_index_by_id(&self.private.current_armor_id),
            world.current_armor.as_ref(),
        ) {
            set_inventory_i32(&mut self.private.source_inventory[index], "arm", armor.arm);
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "flags",
                armor.flags,
            );
            self.private.player_armor = armor.arm;
        }
        if let (Some(index), Some(weapon)) = (
            self.inventory_index_by_id(&self.private.current_weapon_id),
            world.current_weapon.as_ref(),
        ) {
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "hplus",
                weapon.hplus,
            );
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "dplus",
                weapon.dplus,
            );
            set_inventory_i32(
                &mut self.private.source_inventory[index],
                "flags",
                weapon.flags,
            );
        }
    }

    fn scroll_ring_item(&self, item_id: &str) -> Option<source_scrolls::ScrollItem> {
        self.ring_item_by_id(item_id)
            .map(|item| source_scrolls::ScrollItem {
                obj_type: RING,
                which: item_i32(&item, "which", 0),
                flags: item_i32(&item, "flags", 0),
                arm: item_i32(&item, "arm", 0),
                hplus: item_i32(&item, "hplus", 0),
                dplus: item_i32(&item, "dplus", 0),
            })
    }

    fn ring_world(&self) -> source_rings::RingWorld {
        source_rings::RingWorld {
            rng: RogueRng::new(self.private.rng_seed),
            strength: self.private.strength,
            left_ring: self
                .ring_item_by_id(&self.private.left_ring_id)
                .map(|item| ring_object(&item)),
            right_ring: self
                .ring_item_by_id(&self.private.right_ring_id)
                .map(|item| ring_object(&item)),
            selected_hand: source_rings::LEFT,
            markers: Vec::new(),
            trace: serde_json::Map::new(),
        }
    }

    fn sync_ring_world(&mut self, world: &source_rings::RingWorld) {
        self.private.rng_seed = world.rng.seed;
        self.private.strength = world.strength;
        self.private.left_ring_id = world
            .left_ring
            .as_ref()
            .map(|ring| ring.obj_id.clone())
            .unwrap_or_default();
        self.private.right_ring_id = world
            .right_ring
            .as_ref()
            .map(|ring| ring.obj_id.clone())
            .unwrap_or_default();
    }

    fn food_count_for_scrolls(&self) -> i32 {
        let visible_food = self
            .public
            .visible_items
            .values()
            .filter(|item| item.chars().next() == Some(FOOD))
            .count() as i32;
        let inventory_food: i32 = self
            .private
            .source_inventory
            .iter()
            .filter(|item| item_char(item, "type", '?') == FOOD)
            .map(|item| item_i32(item, "count", 1))
            .sum();
        self.private.food as i32 + visible_food + inventory_food
    }

    pub fn checkpoint_bytes(&self) -> Vec<u8> {
        serde_json::to_vec(&json!({
            "schema_version": "gamebench.checkpoint.v1",
            "env_family": Self::ENV_FAMILY,
            "episode_id": self.resolved.episode_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.events.len(),
            "config_hash": self.resolved.config_hash,
            "source_state_projection": self.source_state_projection(),
            "sim": {"resolved": self.resolved, "public": self.public, "private": self.private, "events": self.events}
        })).unwrap()
    }

    pub fn source_state_projection(&self) -> Value {
        source_state::runtime_source_checkpoint_projection(
            &self.resolved,
            &self.public,
            &self.private,
            self.events.len(),
        )
    }

    pub fn restore_checkpoint(&mut self, blob: &[u8]) -> usize {
        let payload: Value = serde_json::from_slice(blob).unwrap();
        let sim = payload.get("sim").unwrap();
        self.resolved = serde_json::from_value(sim.get("resolved").unwrap().clone()).unwrap();
        self.public = serde_json::from_value(sim.get("public").unwrap().clone()).unwrap();
        self.private = serde_json::from_value(sim.get("private").unwrap().clone()).unwrap();
        self.events = serde_json::from_value(sim.get("events").unwrap().clone()).unwrap();
        self.events.len()
    }
}

fn effective_command(action: &str) -> char {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    chars.next().unwrap_or('.')
}

fn direction_input(action: &str, default: char) -> char {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    let command = chars.next().unwrap_or('.');
    if matches!(command, 't' | 'z') {
        let tail: Vec<char> = chars.collect();
        if tail.len() >= 2 && command_move_delta(tail[1]).is_some() {
            return tail[1];
        }
        if !tail.is_empty() && command_move_delta(tail[0]).is_some() {
            return tail[0];
        }
        return default;
    }
    let Some(candidate) = chars.next() else {
        return default;
    };
    if command_move_delta(candidate).is_some() {
        candidate
    } else {
        default
    }
}

fn source_command_tail(action: &str) -> String {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    chars.next();
    chars.collect()
}

fn projection_markers(projection: &Value) -> Vec<String> {
    projection
        .get("final")
        .and_then(|final_state| final_state.get("markers"))
        .and_then(Value::as_array)
        .map(|markers| {
            markers
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn current_action_name(command: char) -> Option<&'static str> {
    match command {
        ')' => Some("current_weapon"),
        ']' => Some("current_armor"),
        '=' => Some("current_rings"),
        _ => None,
    }
}

fn source_help_payload(topic: char, markers: Vec<String>) -> Value {
    let mut payload = json!({
        "topic": topic.to_string(),
        "prompt": "character you want help for (* for all): ",
        "markers": markers,
    });
    let object = payload.as_object_mut().unwrap();
    if topic == '*' {
        let lines: Vec<String> = SOURCE_HELP_ENTRIES
            .iter()
            .filter(|(_, _, printable)| *printable)
            .map(|(ch, desc, _)| source_help_line(*ch, desc))
            .collect();
        object.insert("known".to_string(), Value::Bool(true));
        object.insert("lines".to_string(), json!(lines));
        object.insert(
            "continue_prompt".to_string(),
            Value::String("--Press space to continue--".to_string()),
        );
        return payload;
    }

    if let Some((ch, desc, _)) = SOURCE_HELP_ENTRIES
        .iter()
        .find(|(entry_ch, _, _)| *entry_ch == topic)
    {
        object.insert("known".to_string(), Value::Bool(true));
        object.insert(
            "message".to_string(),
            Value::String(source_help_line(*ch, desc)),
        );
    } else {
        object.insert("known".to_string(), Value::Bool(false));
        object.insert(
            "message".to_string(),
            Value::String(format!("unknown character '{}'", source_unctrl(topic))),
        );
    }
    payload
}

fn source_help_line(ch: char, desc: &str) -> String {
    if ch == '\0' {
        desc.to_string()
    } else {
        format!("{}{}", source_unctrl(ch), desc)
    }
}

fn no_turn_action_name(command: char) -> Option<&'static str> {
    match command {
        '!' => Some("shell"),
        'Q' => Some("quit"),
        'i' => Some("inventory"),
        'I' => Some("picky_inventory"),
        'o' => Some("option"),
        'c' => Some("call"),
        '>' => Some("down_level"),
        '<' => Some("up_level"),
        '?' => Some("help"),
        '/' => Some("identify"),
        'D' => Some("discovered"),
        '\x10' => Some("huh"),
        '\x12' => Some("redraw"),
        'v' => Some("version"),
        'S' => Some("save_game"),
        '@' => Some("status"),
        _ => None,
    }
}

fn source_identify_payload(target: char, markers: Vec<String>) -> Value {
    let target_text = if target == '\0' {
        String::new()
    } else {
        target.to_string()
    };
    let description = identify_description(target);
    let mut payload = json!({
        "target": target_text,
        "description": description,
        "prompt": "what do you want identified? ",
        "markers": markers,
    });
    let object = payload.as_object_mut().unwrap();
    if target == '\x1b' {
        object.insert("cancelled".to_string(), Value::Bool(true));
        object.insert("message".to_string(), Value::String(String::new()));
    } else {
        object.insert(
            "message".to_string(),
            Value::String(format!("'{}': {}", source_unctrl(target), description)),
        );
    }
    payload
}

fn identify_description(target: char) -> String {
    if target == '\0' {
        return "unknown character".to_string();
    }
    if target.is_ascii_uppercase() {
        return MONSTER_NAMES[(target as u8 - b'A') as usize].to_string();
    }
    match target {
        '|' | '-' => "wall of a room",
        GOLD => "gold",
        STAIRS => "a staircase",
        DOOR => "door",
        FLOOR => "room floor",
        PLAYER => "you",
        PASSAGE => "passage",
        TRAP => "trap",
        POTION => "potion",
        SCROLL => "scroll",
        FOOD => "food",
        WEAPON => "weapon",
        ' ' => "solid rock",
        ARMOR => "armor",
        AMULET => "the Amulet of Yendor",
        RING => "ring",
        STICK => "wand or staff",
        _ => "unknown character",
    }
    .to_string()
}

fn source_status_payload(private: &PrivateState, markers: Vec<String>) -> Value {
    let hunger_index = private
        .hungry_state
        .clamp(0, (SOURCE_HUNGER_NAMES.len() - 1) as i32) as usize;
    let display_armor = 10 - private.player_armor;
    json!({
        "level": private.dungeon_level,
        "gold": private.purse,
        "hp": private.hp,
        "max_hp": private.max_hp,
        "strength": private.strength,
        "max_strength": private.max_strength,
        "armor": private.player_armor,
        "display_armor": display_armor,
        "exp": private.player_exp,
        "player_level": private.player_level,
        "hunger": private.hungry_state,
        "message": source_status_message(private, display_armor, SOURCE_HUNGER_NAMES[hunger_index]),
        "markers": markers,
    })
}

fn source_status_message(private: &PrivateState, display_armor: i32, hunger: &str) -> String {
    let hp_width = private.max_hp.max(1).to_string().len();
    format!(
        "Level: {}  Gold: {:<5}  Hp: {:>width$}({:>width$})  Str: {:>2}({})  Arm: {:<2}  Exp: {}/{}  {}",
        private.dungeon_level,
        private.purse,
        private.hp,
        private.max_hp,
        private.strength,
        private.max_strength,
        display_armor,
        private.player_level,
        private.player_exp,
        hunger,
        width = hp_width,
    )
}

fn source_discovered_payload(
    action: &str,
    resolved: &ResolvedTask,
    private: &mut PrivateState,
    markers: Vec<String>,
) -> Value {
    let topic = source_command_tail(action).chars().next().unwrap_or('*');
    let mut payload = json!({
        "type": topic.to_string(),
        "prompt": "for what type of object do you want a list? (* for all)",
        "pot_known": private.pot_known.clone(),
        "ring_known": private.ring_known.clone(),
        "scr_known": private.scr_known.clone(),
        "ws_known": private.ws_known.clone(),
        "markers": markers,
    });
    let object = payload.as_object_mut().unwrap();
    if topic == '\x1b' {
        object.insert("cancelled".to_string(), Value::Bool(true));
        object.insert("message".to_string(), Value::String(String::new()));
        return payload;
    }
    if !matches!(topic, POTION | SCROLL | RING | STICK | '*') {
        object.insert("valid".to_string(), Value::Bool(false));
        object.insert(
            "message".to_string(),
            Value::String(format!(
                "Please type one of {POTION}{SCROLL}{RING}{STICK} (ESCAPE to quit)"
            )),
        );
        return payload;
    }

    let identity = source_state::runtime_source_identity_display(resolved, private);
    let mut rng = RogueRng::new(private.rng_seed);
    let section_types = if topic == '*' {
        vec![POTION, SCROLL, RING, STICK]
    } else {
        vec![topic]
    };
    let mut sections = Vec::new();
    let mut lines = Vec::new();
    for (index, section_type) in section_types.iter().enumerate() {
        let section_lines = source_discovery_lines(*section_type, &identity, &mut rng, private);
        sections.push(json!({"type": section_type.to_string(), "lines": section_lines.clone()}));
        if index != 0 {
            lines.push(String::new());
        }
        lines.extend(section_lines);
    }
    private.rng_seed = rng.seed;
    object.insert("valid".to_string(), Value::Bool(true));
    object.insert("sections".to_string(), json!(sections));
    object.insert("lines".to_string(), json!(lines));
    object.insert(
        "continue_prompt".to_string(),
        Value::String("--Press space to continue--".to_string()),
    );
    payload
}

fn source_discovery_lines(
    obj_type: char,
    identity: &Value,
    rng: &mut RogueRng,
    private: &PrivateState,
) -> Vec<String> {
    let count = match obj_type {
        POTION => SOURCE_POTION_NAMES.len(),
        SCROLL => SOURCE_SCROLL_NAMES.len(),
        RING => SOURCE_RING_NAMES.len(),
        STICK => SOURCE_STICK_NAMES.len(),
        _ => 0,
    };
    let mut lines = Vec::new();
    for which in source_discovery_order(count, rng) {
        if source_discovery_known(obj_type, which, private) {
            lines.push(source_discovery_name(obj_type, which, identity));
        }
    }
    if lines.is_empty() {
        lines.push(source_discovery_nothing(obj_type));
    }
    lines
}

fn source_discovery_order(count: usize, rng: &mut RogueRng) -> Vec<usize> {
    let mut order: Vec<usize> = (0..count).collect();
    for index in (1..=count).rev() {
        let chosen = rng.rnd(index as i32) as usize;
        order.swap(index - 1, chosen);
    }
    order
}

fn source_discovery_known(obj_type: char, which: usize, private: &PrivateState) -> bool {
    match obj_type {
        POTION => private.pot_known.get(which).copied().unwrap_or(false),
        SCROLL => private.scr_known.get(which).copied().unwrap_or(false),
        RING => private.ring_known.get(which).copied().unwrap_or(false),
        STICK => private.ws_known.get(which).copied().unwrap_or(false),
        _ => false,
    }
}

fn source_discovery_name(obj_type: char, which: usize, identity: &Value) -> String {
    match obj_type {
        POTION => {
            let color = identity_value(identity, "potions", which);
            format!("A potion of {}({color})", SOURCE_POTION_NAMES[which])
        }
        SCROLL => format!("A scroll of {}", SOURCE_SCROLL_NAMES[which]),
        RING => {
            let stone = identity_value(identity, "rings", which);
            format!("A ring of {}({stone})", SOURCE_RING_NAMES[which])
        }
        STICK => {
            let stick = identity
                .get("sticks")
                .and_then(Value::as_array)
                .and_then(|values| values.get(which))
                .unwrap_or(&Value::Null);
            let stick_type = stick.get("type").and_then(Value::as_str).unwrap_or("wand");
            let material = stick
                .get("material")
                .and_then(Value::as_str)
                .unwrap_or("wood");
            format!(
                "A {stick_type} of {}({material})",
                SOURCE_STICK_NAMES[which]
            )
        }
        _ => String::new(),
    }
}

fn identity_value(identity: &Value, key: &str, index: usize) -> String {
    identity
        .get(key)
        .and_then(Value::as_array)
        .and_then(|values| values.get(index))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string()
}

fn source_discovery_nothing(obj_type: char) -> String {
    let type_name = match obj_type {
        POTION => "potion",
        SCROLL => "scroll",
        RING => "ring",
        STICK => "stick",
        _ => "object",
    };
    format!("Haven't discovered anything about any {type_name}s")
}

fn source_current_message(item: Option<&Value>, how: &str, where_text: Option<&str>) -> String {
    let suffix = where_text
        .map(|value| format!(" {value}"))
        .unwrap_or_default();
    let Some(item) = item else {
        return format!("you are {how} nothing{suffix}");
    };
    let packch = item_char(item, "packch", '?');
    format!(
        "you are {how} ({packch}) {}{suffix}",
        source_inv_name(item, true)
    )
}

fn source_unctrl(ch: char) -> String {
    if ch == '\0' {
        return String::new();
    }
    let code = ch as u32;
    if code < 32 {
        format!("^{}", char::from_u32(code + 64).unwrap_or('?'))
    } else if code == 127 {
        "^?".to_string()
    } else {
        ch.to_string()
    }
}

fn source_inventory_payload(
    command: char,
    action: &str,
    inventory: &[Value],
    markers: Vec<String>,
) -> Value {
    let mode = if command == 'I' { "picky" } else { "full" };
    let mut payload = json!({"mode": mode, "inventory": inventory, "markers": markers});
    let object = payload.as_object_mut().unwrap();
    if command == 'i' {
        let lines = source_inventory_lines(inventory);
        if lines.is_empty() {
            object.insert(
                "message".to_string(),
                Value::String("you are empty handed".to_string()),
            );
        }
        object.insert("lines".to_string(), json!(lines));
        return payload;
    }

    if inventory.is_empty() {
        object.insert("lines".to_string(), json!([]));
        object.insert(
            "message".to_string(),
            Value::String("you aren't carrying anything".to_string()),
        );
        return payload;
    }
    if inventory.len() == 1 {
        object.insert(
            "lines".to_string(),
            json!([source_inventory_line(&inventory[0])]),
        );
        return payload;
    }

    object.insert(
        "prompt".to_string(),
        Value::String("which item do you wish to inventory: ".to_string()),
    );
    let selected = source_command_tail(action).chars().next().unwrap_or('\0');
    if selected == '\0' {
        object.insert("lines".to_string(), json!([]));
        return payload;
    }

    object.insert("selected".to_string(), Value::String(selected.to_string()));
    if let Some(item) = inventory
        .iter()
        .find(|item| item_char(item, "packch", '\0') == selected)
    {
        object.insert("lines".to_string(), json!([source_inventory_line(item)]));
    } else {
        object.insert("lines".to_string(), json!([]));
        object.insert(
            "message".to_string(),
            Value::String(format!("'{selected}' not in pack")),
        );
    }
    payload
}

fn source_inventory_lines(inventory: &[Value]) -> Vec<String> {
    inventory
        .iter()
        .filter(|item| item_i32(item, "count", 1) > 0)
        .map(source_inventory_line)
        .collect()
}

fn source_inventory_line(item: &Value) -> String {
    let packch = item_char(item, "packch", '?');
    format!("{packch}) {}", source_inv_name(item, false))
}

fn source_inv_name(item: &Value, drop_case: bool) -> String {
    let obj_type = item_char(item, "type", '?');
    let which = item_i32(item, "which", 0) as usize;
    let count = item_i32(item, "count", 1).max(1);
    let flags = item_i32(item, "flags", 0);
    let label = item.get("label").and_then(Value::as_str).unwrap_or("");
    let text = match obj_type {
        WEAPON => {
            let name = SOURCE_WEAPON_NAMES.get(which).copied().unwrap_or("weapon");
            let mut text = if count > 1 {
                format!("{count} ")
            } else {
                format!("A{} ", vowel_suffix(name))
            };
            if flags & ISKNOW != 0 {
                text.push_str(&format!(
                    "{} {name}",
                    source_num(
                        item_i32(item, "hplus", 0),
                        item_i32(item, "dplus", 0),
                        WEAPON
                    )
                ));
            } else {
                text.push_str(name);
            }
            if count > 1 {
                text.push('s');
            }
            if !label.is_empty() {
                text.push_str(&format!(" called {label}"));
            }
            text
        }
        ARMOR => {
            let name = SOURCE_ARMOR_NAMES.get(which).copied().unwrap_or("armor");
            let mut text = if flags & ISKNOW != 0 {
                let arm = item_i32(item, "arm", 0);
                let source_class = SOURCE_A_CLASS.get(which).copied().unwrap_or(10);
                format!(
                    "{} {name} [protection {}]",
                    source_num(source_class - arm, 0, ARMOR),
                    10 - arm
                )
            } else {
                name.to_string()
            };
            if !label.is_empty() {
                text.push_str(&format!(" called {label}"));
            }
            text
        }
        FOOD => {
            if count == 1 {
                "Some food".to_string()
            } else {
                format!("{count} rations of food")
            }
        }
        AMULET => "The Amulet of Yendor".to_string(),
        GOLD => format!(
            "{} Gold pieces",
            item_i32(item, "arm", item_i32(item, "gold", 0))
        ),
        RING => {
            if flags & ISKNOW != 0 {
                let name = SOURCE_RING_NAMES.get(which).copied().unwrap_or("ring");
                format!("A ring of {name}{}", source_ring_num(item))
            } else {
                "A ring".to_string()
            }
        }
        STICK => {
            if item
                .get("is_staff")
                .and_then(Value::as_bool)
                .unwrap_or(false)
            {
                "A staff".to_string()
            } else {
                "A wand".to_string()
            }
        }
        POTION => "A potion".to_string(),
        SCROLL => {
            if count == 1 {
                "A scroll".to_string()
            } else {
                format!("{count} scrolls")
            }
        }
        _ => item_str(item, "name", &item_str(item, "id", "something")).to_string(),
    };
    source_drop_case(&text, drop_case)
}

fn source_drop_case(text: &str, drop_case: bool) -> String {
    let Some(first) = text.chars().next() else {
        return String::new();
    };
    if drop_case && first.is_uppercase() {
        let mut output = first.to_lowercase().collect::<String>();
        output.push_str(&text[first.len_utf8()..]);
        output
    } else if !drop_case && first.is_lowercase() {
        let mut output = first.to_uppercase().collect::<String>();
        output.push_str(&text[first.len_utf8()..]);
        output
    } else {
        text.to_string()
    }
}

fn vowel_suffix(text: &str) -> &'static str {
    match text.chars().next().map(|ch| ch.to_ascii_lowercase()) {
        Some('a' | 'e' | 'i' | 'o' | 'u') => "n",
        _ => "",
    }
}

fn source_num(n1: i32, n2: i32, obj_type: char) -> String {
    let mut text = format!("{n1:+}");
    if obj_type == WEAPON {
        text.push_str(&format!(",{n2:+}"));
    }
    text
}

fn source_ring_num(item: &Value) -> String {
    match item_i32(item, "which", 0) {
        1 | 7 | 8 => format!(" {:+}", item_i32(item, "arm", 0)),
        _ => String::new(),
    }
}

fn packch_from_action(action: &str) -> char {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    chars.next();
    chars.next().unwrap_or('\0')
}

fn source_whatis_type_for_scroll(which: i32) -> Option<SourceWhatisType> {
    match which {
        S_ID_POTION => Some(SourceWhatisType::Object(POTION)),
        S_ID_SCROLL => Some(SourceWhatisType::Object(SCROLL)),
        S_ID_WEAPON => Some(SourceWhatisType::Object(WEAPON)),
        S_ID_ARMOR => Some(SourceWhatisType::Object(ARMOR)),
        S_ID_R_OR_S => Some(SourceWhatisType::RingOrStick),
        _ => None,
    }
}

fn source_whatis_candidate(
    item: &Value,
    id_type: SourceWhatisType,
    consumed_id: &str,
    consumed_removed: bool,
) -> bool {
    if item_i32(item, "count", 1) <= 0 {
        return false;
    }
    if consumed_removed && !consumed_id.is_empty() && item_str(item, "id", "") == consumed_id {
        return false;
    }
    let obj_type = item_char(item, "type", '?');
    match id_type {
        SourceWhatisType::Object(kind) => obj_type == kind,
        SourceWhatisType::RingOrStick => matches!(obj_type, RING | STICK),
    }
}

fn source_whatis_packch_from_action(action: &str) -> char {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    chars.next();
    chars.next();
    chars.next().unwrap_or('\0')
}

fn source_whatis_marker(id_type: SourceWhatisType) -> String {
    match id_type {
        SourceWhatisType::Object(kind) => kind.to_string(),
        SourceWhatisType::RingOrStick => R_OR_S_FILTER.to_string(),
    }
}

fn source_whatis_trace_value(id_type: SourceWhatisType) -> Value {
    match id_type {
        SourceWhatisType::Object(kind) => json!(kind.to_string()),
        SourceWhatisType::RingOrStick => json!(R_OR_S_FILTER),
    }
}

fn scout_tile_sort_key(key: &str) -> (i32, i32, i32) {
    let mut parts = key.split(',').map(|part| part.parse::<i32>().unwrap_or(0));
    (
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
    )
}

fn directional_packch_from_action(action: &str) -> char {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    let command = chars.next().unwrap_or('.');
    if !matches!(command, 't' | 'z') {
        return chars.next().unwrap_or('\0');
    }
    let tail: Vec<char> = chars.collect();
    if tail.is_empty() {
        return '\0';
    }
    if tail.len() == 1 && command_move_delta(tail[0]).is_some() {
        return '\0';
    }
    tail[0]
}

fn first_char(value: &str) -> char {
    value.chars().next().unwrap_or('\0')
}

fn normalize_inventory(inventory: &[Value]) -> Vec<Value> {
    inventory
        .iter()
        .enumerate()
        .map(|(index, item)| {
            let default_packch = char::from_u32(('a' as u32) + index as u32)
                .unwrap_or('a')
                .to_string();
            json!({
                "id": item_str(item, "id", &item_str(item, "obj_id", &format!("item{index}"))),
                "type": item_str(item, "type", &item_str(item, "obj_type", "?")),
                "which": item_i32(item, "which", 0),
                "count": item_i32(item, "count", 1),
                "flags": item_i32(item, "flags", 0),
                "arm": item_i32(item, "arm", 0),
                "hplus": item_i32(item, "hplus", 0),
                "dplus": item_i32(item, "dplus", 0),
                "charges": item_i32(item, "charges", 0),
                "group": item_i32(item, "group", 0),
                "packch": item_str(item, "packch", &default_packch),
                "damage": item_str(item, "damage", ""),
                "hurldmg": item_str(item, "hurldmg", ""),
                "launch": item_i32(item, "launch", -1),
                "is_staff": item_bool(item, "is_staff", false),
            })
        })
        .collect()
}

fn normalize_level_objects(objects: &[Value]) -> Vec<Value> {
    objects
        .iter()
        .enumerate()
        .map(|(index, raw)| {
            let obj_type = item_char(raw, "type", item_char(raw, "obj_type", '?'));
            let row = item_i32(
                raw,
                "row",
                item_i32(raw, "y", item_coord_field(raw, "pos", "y", 0)),
            );
            let col = item_i32(
                raw,
                "col",
                item_i32(raw, "x", item_coord_field(raw, "pos", "x", 0)),
            );
            let default_arm = if obj_type == STICK {
                item_i32(raw, "charges", 0)
            } else {
                0
            };
            let arm = item_i32(raw, "arm", default_arm);
            json!({
                "id": item_str(raw, "id", &item_str(raw, "obj_id", &format!("level_object{index}"))),
                "type": obj_type.to_string(),
                "which": item_i32(raw, "which", 0),
                "pos": {"y": row, "x": col},
                "count": item_i32(raw, "count", 1),
                "hplus": item_i32(raw, "hplus", 0),
                "dplus": item_i32(raw, "dplus", 0),
                "arm": arm,
                "flags": item_i32(raw, "flags", 0),
                "group": item_i32(raw, "group", 0),
                "goldval": item_i32(raw, "goldval", 0),
                "charges": item_i32(raw, "charges", if obj_type == STICK { arm } else { 0 }),
                "damage": item_str(raw, "damage", ""),
                "hurldmg": item_str(raw, "hurldmg", ""),
                "launch": item_i32(raw, "launch", -1),
                "is_staff": item_bool(raw, "is_staff", false),
            })
        })
        .collect()
}

fn normalize_monsters(monsters: &[Value]) -> Vec<Value> {
    monsters
        .iter()
        .enumerate()
        .map(|(index, monster)| {
            let monster_type = item_str(monster, "type", &item_str(monster, "monster_type", "K"));
            let hp = item_i32(monster, "hp", item_i32(monster, "max_hp", 1));
            json!({
                "id": item_str(monster, "id", &item_str(monster, "monster_id", &format!("monster{index}"))),
                "type": monster_type,
                "row": item_i32(monster, "row", item_i32(monster, "y", 0)),
                "col": item_i32(monster, "col", item_i32(monster, "x", 0)),
                "strength": item_i32(monster, "strength", 16),
                "exp": item_i32(monster, "exp", 1),
                "level": item_i32(monster, "level", 1),
                "arm": item_i32(monster, "arm", 6),
                "hp": hp,
                "max_hp": item_i32(monster, "max_hp", hp),
                "damage": item_str(monster, "damage", "1x1"),
                "stats_flags": item_i32(monster, "stats_flags", source_fight::ISRUN),
                "flags": item_i32(monster, "flags", source_fight::ISRUN),
                "turn": item_bool(monster, "turn", true),
                "room": item_i32(monster, "room", 0),
                "dest_kind": item_str(monster, "dest_kind", &item_str(monster, "dest", "hero")),
                "dest_row": item_i32(monster, "dest_row", item_coord_index(monster, "dest_pos", 0, 0)),
                "dest_col": item_i32(monster, "dest_col", item_coord_index(monster, "dest_pos", 1, 0)),
                "dest_room": item_i32(monster, "dest_room", item_i32(monster, "room", 0)),
                "find_dest_kind": item_str(monster, "find_dest_kind", "hero"),
                "find_dest_row": item_i32(monster, "find_dest_row", item_coord_index(monster, "find_dest_pos", 0, 0)),
                "find_dest_col": item_i32(monster, "find_dest_col", item_coord_index(monster, "find_dest_pos", 1, 0)),
                "room_goldval": item_i32(monster, "room_goldval", 1),
                "room_flags": item_i32(monster, "room_flags", 0),
                "dest_room_goldval": item_i32(monster, "dest_room_goldval", 0),
                "dest_room_flags": item_i32(monster, "dest_room_flags", 0),
                "passage_index": item_i32(monster, "passage_index", 9),
                "passage_flags": item_i32(monster, "passage_flags", 0o000002),
                "chase_room": item_i32(monster, "chase_room", item_i32(monster, "room", 0)),
                "room_exits": monster.get("room_exits").and_then(Value::as_array).cloned().unwrap_or_default(),
                "disguise": item_str(monster, "disguise", &monster_type),
                "oldch": item_str(monster, "oldch", "."),
                "pack": monster.get("pack").and_then(Value::as_array).cloned().unwrap_or_default(),
            })
        })
        .collect()
}

fn normalize_traps(traps: &[Value], terrain: &[String]) -> Vec<Value> {
    let mut normalized = Vec::new();
    let mut occupied = BTreeSet::new();
    for (index, trap) in traps.iter().enumerate() {
        let row = item_i32(trap, "row", item_i32(trap, "y", 0));
        let col = item_i32(trap, "col", item_i32(trap, "x", 0));
        let kind = item_i32(
            trap,
            "kind",
            item_i32(trap, "trap_kind", source_traps::T_MYST),
        );
        let flags = item_i32(trap, "flags", source_traps::F_REAL | kind);
        normalized.push(json!({
            "id": item_str(trap, "id", &item_str(trap, "trap_id", &format!("trap{index}"))),
            "row": row,
            "col": col,
            "kind": kind,
            "flags": flags,
            "ch": item_str(trap, "ch", "^"),
            "weapon_group": item_i32(trap, "weapon_group", 1),
        }));
        occupied.insert((row, col));
    }
    let mut next_index = normalized.len();
    for (row, text) in terrain.iter().enumerate() {
        for (col, ch) in text.chars().enumerate() {
            let coord = (row as i32, col as i32);
            if ch == TRAP && !occupied.contains(&coord) {
                normalized.push(json!({
                    "id": format!("trap{next_index}"),
                    "row": row as i32,
                    "col": col as i32,
                    "kind": source_traps::T_MYST,
                    "flags": source_traps::F_REAL | source_traps::T_MYST,
                    "ch": "^",
                    "weapon_group": 1,
                }));
                next_index += 1;
            }
        }
    }
    normalized
}

fn normalize_source_map_cells(cells: &[Value]) -> Vec<Value> {
    cells
        .iter()
        .enumerate()
        .map(|(index, raw)| {
            json!({
                "id": item_str(raw, "id", &item_str(raw, "cell_id", &format!("cell{index}"))),
                "row": item_i32(raw, "row", item_i32(raw, "y", 0)),
                "col": item_i32(raw, "col", item_i32(raw, "x", 0)),
                "ch": item_str(raw, "ch", " ").chars().next().unwrap_or(' ').to_string(),
                "flags": item_i32(raw, "flags", 0),
            })
        })
        .collect()
}

fn apply_source_map_cell_display(terrain: &mut [String], cells: &[Value]) {
    for cell in cells {
        let row = item_i32(cell, "row", -1);
        let col = item_i32(cell, "col", -1);
        if row < 0 || col < 0 {
            continue;
        }
        let row = row as usize;
        let col = col as usize;
        if row >= terrain.len() {
            continue;
        }
        let mut chars: Vec<char> = terrain[row].chars().collect();
        if col >= chars.len() {
            continue;
        }
        chars[col] = item_char(cell, "ch", ' ');
        terrain[row] = chars.into_iter().collect();
    }
}

fn default_daemon_actions() -> Vec<Value> {
    vec![
        json!({"action": "doctor", "type": source_daemons::AFTER, "arg": 0, "time": source_daemons::DAEMON}),
        json!({"action": "stomach", "type": source_daemons::AFTER, "arg": 0, "time": source_daemons::DAEMON}),
    ]
}

fn daemon_action_name(action: &str) -> &'static str {
    match action {
        "doctor" => "doctor",
        "stomach" => "stomach",
        "swander" => "swander",
        "rollwand" => "rollwand",
        "sight" => "sight",
        "unconfuse" => "unconfuse",
        "unsee" => "unsee",
        "nohaste" => "nohaste",
        "land" => "land",
        _ => "",
    }
}

fn source_level_object_value(level: i32, index: usize, obj: &source_level::SourceObject) -> Value {
    json!({
        "id": format!("level{}_object{}", level, index),
        "type": obj.obj_type,
        "which": obj.which,
        "pos": obj.pos,
        "count": obj.count,
        "hplus": obj.hplus,
        "dplus": obj.dplus,
        "arm": obj.arm,
        "flags": obj.flags,
        "group": obj.group,
        "goldval": obj.goldval,
    })
}

fn source_map_cell_value(cell: &source_level::SourceMapCell) -> Value {
    json!({
        "id": cell.id,
        "row": cell.row,
        "col": cell.col,
        "ch": cell.ch.to_string(),
        "flags": cell.flags,
    })
}

fn source_level_monster_value(
    level: i32,
    index: usize,
    monster: &source_level::SourceMonster,
) -> Value {
    json!({
        "id": format!("level{}_monster{}", level, index),
        "type": monster.monster_type,
        "row": monster.pos.y,
        "col": monster.pos.x,
        "level": monster.level,
        "hp": monster.hp,
        "max_hp": monster.hp,
        "flags": monster.flags,
        "disguise": monster.disguise,
        "pack": monster.pack.iter().map(source_level_pack_object_value).collect::<Vec<_>>(),
    })
}

fn source_level_pack_object_value(obj: &source_level::SourceObject) -> Value {
    json!({
        "type": obj.obj_type,
        "which": obj.which,
        "pos": obj.pos,
        "count": obj.count,
        "hplus": obj.hplus,
        "dplus": obj.dplus,
        "arm": obj.arm,
        "flags": obj.flags,
        "group": obj.group,
        "goldval": obj.goldval,
    })
}

fn level_object_pos(item: &Value) -> (i32, i32) {
    (
        item_i32(
            item,
            "row",
            item_i32(item, "y", item_coord_field(item, "pos", "y", 0)),
        ),
        item_i32(
            item,
            "col",
            item_i32(item, "x", item_coord_field(item, "pos", "x", 0)),
        ),
    )
}

fn inventory_item_from_level_object(obj: &Value) -> Value {
    let obj_type = item_char(obj, "type", '?');
    let arm = item_i32(obj, "arm", 0);
    json!({
        "id": item_str(obj, "id", "object"),
        "type": obj_type.to_string(),
        "which": item_i32(obj, "which", 0),
        "count": item_i32(obj, "count", 1),
        "flags": item_i32(obj, "flags", 0),
        "arm": arm,
        "hplus": item_i32(obj, "hplus", 0),
        "dplus": item_i32(obj, "dplus", 0),
        "charges": item_i32(obj, "charges", if obj_type == STICK { arm } else { 0 }),
        "packch": item_str(obj, "packch", ""),
        "damage": item_str(obj, "damage", ""),
        "hurldmg": item_str(obj, "hurldmg", ""),
        "launch": item_i32(obj, "launch", -1),
        "is_staff": item_bool(obj, "is_staff", false),
        "group": item_i32(obj, "group", 0),
    })
}

fn is_mult_inventory(obj_type: char) -> bool {
    matches!(obj_type, POTION | SCROLL | FOOD)
}

fn visible_monsters(monsters: &[Value]) -> BTreeMap<String, String> {
    monsters
        .iter()
        .filter(|monster| item_i32(monster, "hp", 1) > 0)
        .map(|monster| {
            (
                format!(
                    "{},{}",
                    item_i32(monster, "row", 0),
                    item_i32(monster, "col", 0)
                ),
                item_str(monster, "type", "K"),
            )
        })
        .collect()
}

fn item_str(item: &Value, key: &str, default: &str) -> String {
    item.get(key)
        .and_then(Value::as_str)
        .unwrap_or(default)
        .chars()
        .next()
        .map(|first| {
            if matches!(key, "type" | "obj_type" | "packch") {
                first.to_string()
            } else {
                item.get(key)
                    .and_then(Value::as_str)
                    .unwrap_or(default)
                    .to_string()
            }
        })
        .unwrap_or_else(|| default.to_string())
}

fn item_char(item: &Value, key: &str, default: char) -> char {
    item.get(key)
        .and_then(Value::as_str)
        .and_then(|text| text.chars().next())
        .unwrap_or(default)
}

fn item_i32(item: &Value, key: &str, default: i32) -> i32 {
    item.get(key)
        .and_then(Value::as_i64)
        .map(|value| value as i32)
        .unwrap_or(default)
}

fn item_bool(item: &Value, key: &str, default: bool) -> bool {
    item.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn item_coord_index(item: &Value, key: &str, index: usize, default: i32) -> i32 {
    item.get(key)
        .and_then(Value::as_array)
        .and_then(|values| values.get(index))
        .and_then(Value::as_i64)
        .map(|value| value as i32)
        .unwrap_or(default)
}

fn item_coord_field(item: &Value, key: &str, field: &str, default: i32) -> i32 {
    item.get(key)
        .and_then(Value::as_object)
        .and_then(|values| values.get(field))
        .and_then(Value::as_i64)
        .map(|value| value as i32)
        .or_else(|| {
            let index = if field == "y" { 0 } else { 1 };
            item.get(key)
                .and_then(Value::as_array)
                .and_then(|values| values.get(index))
                .and_then(Value::as_i64)
                .map(|value| value as i32)
        })
        .unwrap_or(default)
}

fn set_inventory_i32(item: &mut Value, key: &str, value: i32) {
    if let Some(object) = item.as_object_mut() {
        object.insert(key.to_string(), json!(value));
    }
}

fn set_value_i32(item: &mut Value, key: &str, value: i32) {
    if let Some(object) = item.as_object_mut() {
        object.insert(key.to_string(), json!(value));
    }
}

fn set_value_string(item: &mut Value, key: &str, value: &str) {
    if let Some(object) = item.as_object_mut() {
        object.insert(key.to_string(), json!(value));
    }
}

fn potion_object(item: &Value) -> source_potions::PotionObject {
    source_potions::PotionObject {
        obj_type: item_char(item, "type", '?'),
        which: item_i32(item, "which", 0),
        count: item_i32(item, "count", 1),
        flags: item_i32(item, "flags", 0),
        arm: item_i32(item, "arm", 0),
        hplus: item_i32(item, "hplus", 0),
        dplus: item_i32(item, "dplus", 0),
    }
}

fn scroll_object(item: &Value) -> source_scrolls::ScrollObject {
    source_scrolls::ScrollObject {
        obj_type: item_char(item, "type", '?'),
        which: item_i32(item, "which", 0),
        count: item_i32(item, "count", 1),
    }
}

fn bolt_fight_weapon(_name: &str) -> source_fight::FightWeapon {
    source_fight::FightWeapon {
        which: FLAME_WEAPON,
        hplus: 100,
        dplus: 0,
        damage: "1x1".to_string(),
        hurl_damage: "6x6".to_string(),
        launch: -1,
        flags: 0,
    }
}

fn stick_object(item: &Value) -> source_sticks::StickObject {
    source_sticks::StickObject {
        obj_type: item_char(item, "type", '?'),
        which: item_i32(item, "which", 0),
        charges: item_i32(item, "charges", 0),
        flags: item_i32(item, "flags", 0),
        damage: item_str(item, "damage", ""),
        hurldmg: item_str(item, "hurldmg", ""),
        hplus: item_i32(item, "hplus", 0),
        dplus: item_i32(item, "dplus", 0),
        launch: item_i32(item, "launch", -1),
        is_staff: item_bool(item, "is_staff", false),
    }
}

fn stick_monster_object(monster: &Value) -> source_sticks::StickMonster {
    source_sticks::StickMonster {
        monster_type: item_char(monster, "type", 'K'),
        hp: item_i32(monster, "hp", 1),
        flags: item_i32(monster, "flags", source_fight::ISRUN),
        disguise: Some(item_char(
            monster,
            "disguise",
            item_char(monster, "type", 'K'),
        )),
        oldch: item_char(monster, "oldch", '.'),
        pack_count: monster
            .get("pack")
            .and_then(Value::as_array)
            .map(|pack| pack.len() as i32)
            .unwrap_or(0),
        turn: item_bool(monster, "turn", true),
        dest_hero: item_str(monster, "dest_kind", &item_str(monster, "dest", "hero")) == "hero",
        visible: item_i32(monster, "hp", 1) > 0,
        cansee: item_i32(monster, "hp", 1) > 0,
    }
}

fn ring_object(item: &Value) -> source_rings::RingObject {
    source_rings::RingObject {
        obj_id: item_str(item, "id", ""),
        obj_type: item_char(item, "type", '?'),
        which: item_i32(item, "which", 0),
        arm: item_i32(item, "arm", 0),
        flags: item_i32(item, "flags", 0),
        packch: item_char(item, "packch", 'a'),
    }
}

fn fight_monster_object(monster: &Value) -> source_fight::FightMonster {
    source_fight::FightMonster {
        monster_type: item_char(monster, "type", 'K'),
        stats: source_fight::FightStats {
            strength: item_i32(monster, "strength", 16),
            exp: item_i32(monster, "exp", 1),
            level: item_i32(monster, "level", 1),
            arm: item_i32(monster, "arm", 6),
            hp: item_i32(monster, "hp", 1),
            damage: item_str(monster, "damage", "1x1"),
            max_hp: item_i32(monster, "max_hp", item_i32(monster, "hp", 1)),
            flags: item_i32(monster, "stats_flags", source_fight::ISRUN),
        },
        flags: item_i32(monster, "flags", source_fight::ISRUN),
        disguise: Some(item_char(
            monster,
            "disguise",
            item_char(monster, "type", 'K'),
        )),
        pack: monster
            .get("pack")
            .and_then(Value::as_array)
            .map(|pack| {
                pack.iter()
                    .map(|obj| source_fight::FightObject {
                        obj_type: item_char(obj, "type", item_char(obj, "obj_type", GOLD)),
                        name: item_str(obj, "name", &item_str(obj, "id", "object")),
                        goldval: item_i32(obj, "goldval", 0),
                    })
                    .collect()
            })
            .unwrap_or_default(),
        oldch: item_char(monster, "oldch", '.'),
    }
}

fn attack_monster_object(monster: &Value) -> source_attack::AttackMonster {
    source_attack::AttackMonster {
        monster_type: item_char(monster, "type", 'K'),
        stats: source_attack::Stats {
            strength: item_i32(monster, "strength", 16),
            exp: item_i32(monster, "exp", 1),
            level: item_i32(monster, "level", 1),
            arm: item_i32(monster, "arm", 6),
            hp: item_i32(monster, "hp", 1),
            damage: item_str(monster, "damage", "1x1"),
            max_hp: item_i32(monster, "max_hp", item_i32(monster, "hp", 1)),
            flags: item_i32(monster, "stats_flags", source_attack::ISRUN),
        },
        flags: item_i32(monster, "flags", source_attack::ISRUN),
        disguise: Some(item_char(
            monster,
            "disguise",
            item_char(monster, "type", 'K'),
        )),
    }
}

fn chase_thing_object(monster: &Value) -> source_chase::ChaseThing {
    source_chase::ChaseThing {
        monster_type: item_char(monster, "type", 'K'),
        pos: source_chase::Coord {
            y: item_i32(monster, "row", 0),
            x: item_i32(monster, "col", 0),
        },
        flags: item_i32(monster, "flags", source_fight::ISRUN),
        turn: item_bool(monster, "turn", true),
        disguise: item_char(monster, "disguise", item_char(monster, "type", 'K')),
    }
}

fn monster_dest_coord_chase(monster: &Value, hero: Position) -> source_chase::Coord {
    if item_str(monster, "dest_kind", &item_str(monster, "dest", "hero")) == "hero" {
        return source_chase::Coord {
            y: hero.0 as i32,
            x: hero.1 as i32,
        };
    }
    source_chase::Coord {
        y: item_i32(monster, "dest_row", hero.0 as i32),
        x: item_i32(monster, "dest_col", hero.1 as i32),
    }
}

fn monster_dest_coord_do(monster: &Value, hero: Position) -> source_do_chase::Coord {
    if item_str(monster, "dest_kind", &item_str(monster, "dest", "hero")) == "hero" {
        return source_do_chase::Coord {
            y: hero.0 as i32,
            x: hero.1 as i32,
        };
    }
    source_do_chase::Coord {
        y: item_i32(monster, "dest_row", hero.0 as i32),
        x: item_i32(monster, "dest_col", hero.1 as i32),
    }
}

fn monster_find_dest_coord_do(monster: &Value, hero: Position) -> source_do_chase::Coord {
    source_do_chase::Coord {
        y: item_i32(monster, "find_dest_row", hero.0 as i32),
        x: item_i32(monster, "find_dest_col", hero.1 as i32),
    }
}

fn monster_room_exits(monster: &Value) -> Vec<source_chase::Coord> {
    monster
        .get("room_exits")
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(|coord| {
                    let parts = coord.as_array()?;
                    Some(source_chase::Coord {
                        y: parts.first().and_then(Value::as_i64).unwrap_or(0) as i32,
                        x: parts.get(1).and_then(Value::as_i64).unwrap_or(0) as i32,
                    })
                })
                .collect()
        })
        .unwrap_or_default()
}

fn monster_pack_do(monster: &Value) -> Vec<source_do_chase::ChaseObject> {
    monster
        .get("pack")
        .and_then(Value::as_array)
        .map(|pack| {
            pack.iter()
                .map(|obj| source_do_chase::ChaseObject {
                    obj_type: item_char(obj, "type", item_char(obj, "obj_type", GOLD)),
                    pos: pack_object_coord_do(obj),
                })
                .collect()
        })
        .unwrap_or_default()
}

fn pack_object_coord_do(obj: &Value) -> source_do_chase::Coord {
    if let Some(pos) = obj.get("pos").and_then(Value::as_object) {
        return source_do_chase::Coord {
            y: pos.get("y").and_then(Value::as_i64).unwrap_or(0) as i32,
            x: pos.get("x").and_then(Value::as_i64).unwrap_or(0) as i32,
        };
    }
    source_do_chase::Coord {
        y: item_coord_index(obj, "pos", 0, 0),
        x: item_coord_index(obj, "pos", 1, 0),
    }
}

fn monster_value_from_source(previous: &Value, monster: &source_fight::FightMonster) -> Value {
    json!({
        "id": item_str(previous, "id", ""),
        "type": monster.monster_type.to_string(),
        "row": item_i32(previous, "row", 0),
        "col": item_i32(previous, "col", 0),
        "strength": monster.stats.strength,
        "exp": monster.stats.exp,
        "level": monster.stats.level,
        "arm": monster.stats.arm,
        "hp": monster.stats.hp,
        "max_hp": monster.stats.max_hp,
        "damage": monster.stats.damage.clone(),
        "stats_flags": monster.stats.flags,
        "flags": monster.flags,
        "turn": item_bool(previous, "turn", true),
        "disguise": monster.disguise.map(|ch| ch.to_string()).unwrap_or_else(|| monster.monster_type.to_string()),
        "oldch": monster.oldch.to_string(),
        "pack": monster.pack.iter().map(|obj| json!({"type": obj.obj_type.to_string(), "name": obj.name.clone(), "goldval": obj.goldval})).collect::<Vec<_>>(),
    })
}

fn is_magic_attack_item(item: &Value) -> bool {
    let obj_type = item_char(item, "type", '?');
    matches!(obj_type, POTION | SCROLL | STICK | RING | AMULET)
        || (matches!(obj_type, WEAPON | ARMOR)
            && (item_i32(item, "hplus", 0) != 0
                || item_i32(item, "dplus", 0) != 0
                || item_i32(item, "arm", 0) != 0
                || item_i32(item, "flags", 0) != 0))
}

fn default_true() -> bool {
    true
}

fn default_strength() -> i32 {
    16
}

fn default_food_left() -> i32 {
    1300
}

fn default_player_level() -> i32 {
    1
}

fn default_player_level_usize() -> usize {
    1
}

fn default_player_armor() -> i32 {
    6
}

fn default_player_damage() -> String {
    "1x4".to_string()
}

fn default_pot_known() -> Vec<bool> {
    vec![false; 14]
}

fn default_ring_known() -> Vec<bool> {
    vec![false; 14]
}

fn default_scr_known() -> Vec<bool> {
    vec![false; 18]
}

fn default_ws_known() -> Vec<bool> {
    vec![false; 14]
}

pub fn resolve_task(task: &Value, seed_override: Option<i64>) -> ResolvedTask {
    let task_id = task
        .get("task_id")
        .or_else(|| task.get("scenario_id"))
        .and_then(Value::as_str)
        .unwrap_or("manual")
        .to_string();
    let seed =
        seed_override.unwrap_or_else(|| task.get("seed").and_then(Value::as_i64).unwrap_or(0));
    let grid: Vec<String> = task
        .get("grid")
        .unwrap()
        .as_array()
        .unwrap()
        .iter()
        .map(|row| row.as_str().unwrap().to_string())
        .collect();
    let rules = task.get("rules").cloned().unwrap_or_else(|| json!({}));
    let max_steps = rules
        .get("overrides")
        .and_then(|o| o.get("max_steps"))
        .or_else(|| task.get("max_steps"))
        .and_then(Value::as_u64)
        .unwrap_or(80) as usize;
    let objective = task
        .get("objective")
        .or_else(|| rules.get("overrides").and_then(|o| o.get("objective")))
        .and_then(Value::as_str)
        .unwrap_or("descend")
        .to_string();
    let inventory = rules
        .get("overrides")
        .and_then(|o| o.get("inventory"))
        .or_else(|| task.get("inventory"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let monsters = rules
        .get("overrides")
        .and_then(|o| o.get("monsters"))
        .or_else(|| task.get("monsters"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let traps = rules
        .get("overrides")
        .and_then(|o| o.get("traps"))
        .or_else(|| task.get("traps"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let source_map_cells = rules
        .get("overrides")
        .and_then(|o| o.get("source_map_cells"))
        .or_else(|| task.get("source_map_cells"))
        .or_else(|| task.get("map_cells"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let level_objects = rules
        .get("overrides")
        .and_then(|o| o.get("level_objects"))
        .or_else(|| task.get("level_objects"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let inventory_text = stable_json(&Value::Array(inventory.clone()));
    let monsters_text = stable_json(&Value::Array(monsters.clone()));
    let traps_text = stable_json(&Value::Array(traps.clone()));
    let source_map_cells_text = stable_json(&Value::Array(source_map_cells.clone()));
    let level_objects_text = stable_json(&Value::Array(level_objects.clone()));
    let text = if source_map_cells.is_empty() {
        format!(
            "rogue:{}:{}:{}:{}:{}:{}:{}:{}:{}",
            task_id,
            seed,
            max_steps,
            objective,
            grid.join(";"),
            inventory_text,
            monsters_text,
            traps_text,
            level_objects_text
        )
    } else {
        format!(
            "rogue:{}:{}:{}:{}:{}:{}:{}:{}:{}:{}",
            task_id,
            seed,
            max_steps,
            objective,
            grid.join(";"),
            inventory_text,
            monsters_text,
            traps_text,
            source_map_cells_text,
            level_objects_text
        )
    };
    let config_hash = stable_hash(&text, 16);
    let episode_id = stable_hash(
        &format!("gamebench.rogue:{}:{}:{}", task_id, seed, config_hash),
        32,
    );
    ResolvedTask {
        task_id,
        seed,
        grid,
        max_steps,
        objective,
        inventory,
        monsters,
        traps,
        source_map_cells,
        level_objects,
        config_hash,
        episode_id,
    }
}

fn scenario_to_task(entry: &Value) -> Value {
    if let Some(task) = entry.get("task") {
        return task.clone();
    }
    let mut task = json!({
        "schema": "gamebench.task.rogue.v1",
        "task_id": entry.get("scenario_id").and_then(Value::as_str).unwrap_or("manual"),
        "seed": entry.get("seed").and_then(Value::as_i64).unwrap_or(0),
        "grid": entry.get("grid").unwrap(),
        "rules": entry.get("rules").cloned().unwrap_or_else(|| json!({"base": "modern_rogue_core"})),
        "objective": entry.get("objective").and_then(Value::as_str).unwrap_or("descend")
    });
    if let Some(inventory) = entry.get("inventory") {
        task["inventory"] = inventory.clone();
    }
    if let Some(monsters) = entry.get("monsters") {
        task["monsters"] = monsters.clone();
    }
    if let Some(traps) = entry.get("traps") {
        task["traps"] = traps.clone();
    }
    if let Some(source_map_cells) = entry.get("source_map_cells") {
        task["source_map_cells"] = source_map_cells.clone();
    }
    if let Some(map_cells) = entry.get("map_cells") {
        task["source_map_cells"] = map_cells.clone();
    }
    if let Some(level_objects) = entry.get("level_objects") {
        task["level_objects"] = level_objects.clone();
    }
    task
}

fn stable_hash(text: &str, length: usize) -> String {
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hasher.finalize();
    format!("{:x}", digest)[..length].to_string()
}

fn stable_json(value: &Value) -> String {
    match value {
        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_) => {
            serde_json::to_string(value).unwrap()
        }
        Value::Array(values) => format!(
            "[{}]",
            values.iter().map(stable_json).collect::<Vec<_>>().join(",")
        ),
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let fields = keys
                .into_iter()
                .map(|key| {
                    format!(
                        "{}:{}",
                        serde_json::to_string(key).unwrap(),
                        stable_json(map.get(key).unwrap())
                    )
                })
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{fields}}}")
        }
    }
}
