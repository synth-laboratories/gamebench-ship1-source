//! Own Rust gold lane for capture-backed NetHack Main Dungeon dlvl 1.
//!
//! NLE appears only in fixture metadata and the checked-in action table; this
//! crate never links to, shells out to, or imports an NLE runtime.

use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub const ENV_FAMILY: &str = "nethack-dlvl1-singleplayer";
pub const VIEW_HEIGHT: usize = 21;
pub const VIEW_WIDTH: usize = 79;
const CHECKPOINT_SCHEMA: &str = "gamebench.checkpoint.v1";
const BLSTATS_FIELDS: [&str; 27] = [
    "x", "y", "strength", "strength_percent", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "score", "hp", "hp_max", "depth", "gold", "energy", "energy_max", "ac", "monster_level", "experience_level", "experience", "time", "hunger", "capacity", "dungeon_number", "dungeon_level", "condition", "alignment",
];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Position {
    pub x: i64,
    pub y: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Hero {
    pub x: i64,
    pub y: i64,
    pub glyph: i64,
    pub color: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Item {
    pub id: String,
    pub letter: String,
    pub kind: String,
    pub name: String,
    pub quantity: i64,
    pub glyph: i64,
    pub color: i64,
    pub oclass: i64,
    pub nutrition: i64,
    pub damage: i64,
    pub armor: i64,
    pub effect: String,
    pub position: Position,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Monster {
    pub id: String,
    pub name: String,
    pub char: String,
    pub glyph: i64,
    pub color: i64,
    pub hp: i64,
    pub hp_max: i64,
    pub attack: i64,
    pub experience: i64,
    pub peaceful: bool,
    pub pet: bool,
    pub position: Position,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Trap {
    pub id: String,
    pub kind: String,
    pub damage: i64,
    pub seen: bool,
    pub triggered: bool,
    pub position: Position,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NevEvent {
    pub step_index: i64,
    pub tick: i64,
    pub episode_id: String,
    pub kind: String,
    pub action: Option<String>,
    pub transition: Option<String>,
    pub severity: String,
    pub message: String,
    pub payload: Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameState {
    pub terrain: Vec<Vec<String>>,
    pub base_glyphs: Vec<Vec<i64>>,
    pub base_colors: Vec<Vec<i64>>,
    pub seen: Vec<Vec<bool>>,
    pub hero: Hero,
    pub floor_items: Vec<Item>,
    pub inventory: Vec<Item>,
    pub monsters: Vec<Monster>,
    pub traps: Vec<Trap>,
    pub step_index: i64,
    pub time: i64,
    pub rng: u32,
    pub message: String,
    pub message_raw: Vec<u8>,
    pub message_history: Vec<String>,
    pub input_mode: Value,
    pub terminated: bool,
    pub truncated: bool,
    pub terminal_reason: String,
    pub reward: f64,
    pub hp: i64,
    pub hp_max: i64,
    pub energy: i64,
    pub energy_max: i64,
    pub gold: i64,
    pub experience: i64,
    pub experience_level: i64,
    pub ac: i64,
    pub hunger: i64,
    pub hunger_state: String,
    pub strength: i64,
    pub dexterity: i64,
    pub constitution: i64,
    pub intelligence: i64,
    pub wisdom: i64,
    pub charisma: i64,
    pub wielded: String,
    pub worn: String,
    pub accessories: Vec<String>,
    pub quiver: String,
    pub last_command: String,
    pub engraving: String,
}

#[derive(Clone, Debug)]
pub struct ActionSpec {
    pub id: usize,
    pub canonical: String,
    pub value: i64,
}

impl ActionSpec {
    pub fn enum_class(&self) -> &str {
        self.canonical.split_once('.').map(|parts| parts.0).unwrap_or("")
    }

    pub fn name(&self) -> &str {
        self.canonical.split_once('.').map(|parts| parts.1).unwrap_or("")
    }

    pub fn key(&self) -> String {
        let value = self.value;
        let code = if (32..=126).contains(&value) {
            value
        } else if (128..=255).contains(&value) {
            value & 0x7f
        } else if (0..=31).contains(&value) {
            value
        } else {
            return String::new();
        };
        char::from_u32(code as u32).map(|ch| ch.to_string()).unwrap_or_default()
    }

    pub fn payload(&self) -> Value {
        json!({"id": self.id, "name": self.canonical, "value": self.value, "key": self.key()})
    }
}

#[derive(Clone, Debug)]
pub struct NethackSession {
    pub resolved: Value,
    pub state: GameState,
    pub events: Vec<NevEvent>,
}

impl NethackSession {
    pub fn reset_from_entry(entry: &Value) -> Result<Self, String> {
        let task = task_from_entry(entry);
        let resolved = resolve_task(&task, None)?;
        Self::reset(resolved)
    }

    pub fn reset(resolved: Value) -> Result<Self, String> {
        let level = resolved.get("level_dump").cloned().ok_or("resolved task lacks level_dump")?;
        let metadata = object_or_empty(level.get("metadata"));
        let hero_value = level.get("hero").cloned().unwrap_or_else(|| json!({}));
        let hero = Hero {
            x: integer(&hero_value, "x", 0),
            y: integer(&hero_value, "y", 0),
            glyph: integer(&hero_value, "glyph", '@' as i64),
            color: integer(&hero_value, "color", 15),
        };
        let mut inventory = level.get("inventory").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| item_from_value(item, index, false)).collect::<Vec<_>>();
        assign_inventory_letters(&mut inventory);
        let terrain = level.get("terrain").and_then(Value::as_array).cloned().unwrap_or_default().iter().map(|row| row.as_str().unwrap_or("").chars().map(|ch| ch.to_string()).collect::<Vec<_>>()).collect::<Vec<_>>();
        let base_glyphs = int_matrix(level.get("glyphs"));
        let base_colors = int_matrix(level.get("colors"));
        let seen = bool_matrix(level.get("seen"));
        let mut session = Self {
            resolved: resolved.clone(),
            state: GameState {
                terrain,
                base_glyphs,
                base_colors,
                seen,
                hero,
                floor_items: level.get("objects").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| item_from_value(item, index, true)).collect(),
                inventory,
                monsters: level.get("monsters").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| monster_from_value(item, index)).collect(),
                traps: level.get("traps").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| trap_from_value(item, index)).collect(),
                step_index: 0,
                time: 0,
                rng: integer(&resolved, "seed", 0) as u32,
                message: String::new(),
                message_raw: Vec::new(),
                message_history: Vec::new(),
                input_mode: normal_mode(),
                terminated: false,
                truncated: false,
                terminal_reason: String::new(),
                reward: 0.0,
                hp: integer_map(&metadata, "hp", 14),
                hp_max: integer_map(&metadata, "hp_max", integer_map(&metadata, "hp", 14)).max(1),
                energy: integer_map(&metadata, "energy", 0),
                energy_max: integer_map(&metadata, "energy_max", integer_map(&metadata, "energy", 0)).max(0),
                gold: integer_map(&metadata, "gold", 0),
                experience: integer_map(&metadata, "experience", 0),
                experience_level: integer_map(&metadata, "experience_level", 1).max(1),
                ac: integer_map(&metadata, "ac", 10),
                hunger: integer_map(&metadata, "hunger", 900),
                hunger_state: "Not Hungry".to_string(),
                strength: integer_map(&metadata, "strength", 18),
                dexterity: integer_map(&metadata, "dexterity", 10),
                constitution: integer_map(&metadata, "constitution", 10),
                intelligence: integer_map(&metadata, "intelligence", 8),
                wisdom: integer_map(&metadata, "wisdom", 8),
                charisma: integer_map(&metadata, "charisma", 8),
                wielded: String::new(),
                worn: String::new(),
                accessories: Vec::new(),
                quiver: String::new(),
                last_command: String::new(),
                engraving: String::new(),
            },
            events: Vec::new(),
        };
        session.reveal();
        session.event("task_resolved", "TaskResolved(dlvl1 capture-backed)", None, Some("reset"), "info", json!({"task_id": string(&resolved, "task_id", "manual"), "config_hash": string(&resolved, "config_hash", ""), "fixture_id": string(&resolved, "fixture_id", "")}));
        session.message("You enter the dungeon.");
        Ok(session)
    }

    pub fn step(&mut self, input: Value) -> Value {
        if self.state.terminated || self.state.truncated {
            self.event("rule_violation", "RuleViolation(terminal)", Some(input.to_string()), Some("reject"), "warn", json!({}));
            return self.readout();
        }
        let Some(action) = coerce_action(&input) else {
            self.message("Unknown NLE action id.");
            self.event("rule_violation", "RuleViolation(unknown_action)", Some(input.to_string()), Some("reject"), "warn", json!({}));
            return self.readout();
        };
        self.state.step_index += 1;
        self.event("action_applied", &format!("Action({})", action.canonical), Some(action.canonical.clone()), Some("dispatch"), "info", action.payload());
        let spent_turn = if mode_kind(&self.state.input_mode) == "normal" {
            self.dispatch_normal(&action)
        } else {
            self.consume_prompt(&action)
        };
        if spent_turn && !self.state.terminated {
            self.advance_turn();
        }
        self.reveal();
        self.check_truncation();
        self.readout()
    }

    pub fn readout(&self) -> Value {
        json!({"public": self.public_projection(), "private": self.private_projection(), "reward": self.state.reward, "terminated": self.state.terminated, "truncated": self.state.truncated, "nev_cursor": self.events.len()})
    }

    pub fn public_projection(&self) -> Value {
        let (chars, colors, glyphs) = self.render_planes();
        let blstats = self.blstats();
        let named = BLSTATS_FIELDS.iter().zip(blstats.iter()).map(|(key, value)| ((*key).to_string(), Value::from(*value))).collect::<Map<String, Value>>();
        json!({
            "schema": "gamebench.nethack.dlvl1.public.v1",
            "chars": chars,
            "colors": colors,
            "glyphs": glyphs,
            "blstats": blstats,
            "blstats_fields": BLSTATS_FIELDS,
            "blstats_named": named,
            "message": normalize_message(&self.state.message),
            "message_raw": self.state.message_raw,
            "inventory": self.inventory_projection(),
            "input_mode": self.state.input_mode,
            "done": self.state.terminated || self.state.truncated,
            "terminated": self.state.terminated,
            "truncated": self.state.truncated,
            "terminal_reason": self.state.terminal_reason,
        })
    }

    pub fn private_projection(&self) -> Value {
        json!({
            "task_id": string(&self.resolved, "task_id", "manual"),
            "fixture_id": string(&self.resolved, "fixture_id", ""),
            "episode_id": string(&self.resolved, "episode_id", ""),
            "config_hash": string(&self.resolved, "config_hash", ""),
            "step_index": self.state.step_index,
            "time": self.state.time,
            "rng": self.state.rng,
            "hero": self.state.hero,
            "hp": self.state.hp,
            "hp_max": self.state.hp_max,
            "gold": self.state.gold,
            "experience": self.state.experience,
            "experience_level": self.state.experience_level,
            "hunger": self.state.hunger,
            "hunger_state": self.state.hunger_state,
            "ac": self.state.ac,
            "wielded": self.state.wielded,
            "worn": self.state.worn,
            "accessories": self.state.accessories,
            "quiver": self.state.quiver,
            "inventory": self.state.inventory,
            "floor_items": self.state.floor_items,
            "monsters": self.state.monsters,
            "traps": self.state.traps,
            "seen": self.state.seen,
            "input_mode": self.state.input_mode,
            "terminated": self.state.terminated,
            "truncated": self.state.truncated,
            "terminal_reason": self.state.terminal_reason,
            "reward": self.state.reward,
        })
    }

    pub fn checkpoint_bytes(&self) -> Vec<u8> {
        let events = serde_json::to_value(&self.events).unwrap_or_else(|_| json!([]));
        let event_bytes = canonical_json(&events);
        let mut digest = Sha256::new();
        digest.update(event_bytes.as_bytes());
        let payload = json!({
            "schema_version": CHECKPOINT_SCHEMA,
            "env_family": ENV_FAMILY,
            "episode_id": string(&self.resolved, "episode_id", ""),
            "step_index": self.state.step_index,
            "nev_cursor": self.events.len(),
            "nev_event_digest": format!("sha256:{:x}", digest.finalize()),
            "nev_events_external": false,
            "nev_events": self.events,
            "config_hash": string(&self.resolved, "config_hash", ""),
            "resolved": self.resolved,
            "sim": self.state,
        });
        canonical_json(&payload).into_bytes()
    }

    pub fn restore_checkpoint(&mut self, bytes: &[u8]) -> Result<usize, String> {
        let payload: Value = serde_json::from_slice(bytes).map_err(|error| error.to_string())?;
        if string(&payload, "schema_version", "") != CHECKPOINT_SCHEMA {
            return Err(format!("unsupported checkpoint schema: {}", string(&payload, "schema_version", "")));
        }
        if string(&payload, "env_family", "") != ENV_FAMILY {
            return Err(format!("checkpoint belongs to {:?}", payload.get("env_family")));
        }
        self.resolved = payload.get("resolved").cloned().ok_or("checkpoint lacks resolved")?;
        self.state = serde_json::from_value(payload.get("sim").cloned().ok_or("checkpoint lacks sim")?).map_err(|error| error.to_string())?;
        self.events = serde_json::from_value(payload.get("nev_events").cloned().unwrap_or_else(|| json!([]))).map_err(|error| error.to_string())?;
        Ok(self.events.len())
    }

    pub fn legacy_strings(&self) -> Vec<String> {
        self.events.iter().map(|event| event.message.clone()).collect()
    }

    fn dispatch_normal(&mut self, action: &ActionSpec) -> bool {
        self.state.last_command = action.canonical.clone();
        if let Some(direction) = direction_for(action) {
            return self.move_hero(direction, action.enum_class() == "CompassDirectionLonger", false);
        }
        match action.canonical.as_str() {
            "MiscDirection.DOWN" => return self.descend(),
            "MiscDirection.UP" => {
                self.message("You can't go up here.");
                return false;
            }
            "MiscDirection.WAIT" => {
                self.message("You wait.");
                return true;
            }
            "MiscAction.MORE" => {
                self.message("Nothing more to display.");
                return false;
            }
            _ => {}
        }
        let name = action.name();
        if name == "ESC" {
            self.message("Never mind.");
            return false;
        }
        if name == "OPEN" {
            self.enter_mode("direction", action, "In what direction?", json!({"operation": "open"}));
            return false;
        }
        if matches!(name, "CLOSE" | "FIGHT" | "FORCE" | "KICK" | "MOVE" | "MOVEFAR" | "RUSH" | "RUSH2" | "SEETRAP" | "UNTRAP") {
            let operation = if matches!(name, "MOVEFAR" | "RUSH" | "RUSH2") {
                "move".to_string()
            } else {
                name.to_ascii_lowercase()
            };
            self.enter_mode("direction", action, "In what direction?", json!({"operation": operation, "running": matches!(name, "MOVEFAR" | "RUSH" | "RUSH2"), "force_move": name == "MOVE"}));
            return false;
        }
        if matches!(name, "APPLY" | "DIP" | "DROP" | "EAT" | "FIRE" | "INVOKE" | "PUTON" | "QUAFF" | "QUIVER" | "READ" | "REMOVE" | "RUB" | "TAKEOFF" | "THROW" | "TIP" | "WEAR" | "WIELD" | "ZAP") {
            self.enter_mode("inventory_letter", action, "What do you want to use?", json!({"operation": name.to_ascii_lowercase(), "after": if matches!(name, "FIRE" | "THROW" | "ZAP") { "direction" } else { "normal" }}));
            return false;
        }
        if name == "PICKUP" {
            return self.pickup(false);
        }
        if name == "SEARCH" {
            return self.search();
        }
        if matches!(name, "PRAY" | "QUIT" | "SAVE") {
            self.enter_mode("ynq", action, "Really do that? [ynq]", json!({"operation": name.to_ascii_lowercase()}));
            return false;
        }
        if matches!(name, "EXTCMD" | "ENGRAVE") {
            self.enter_mode("string", action, "What do you want to type?", json!({"operation": name.to_ascii_lowercase(), "buffer": ""}));
            return false;
        }
        if name == "LOOT" {
            self.enter_mode("menu", action, "Loot which item?", json!({"operation": "loot", "choices": []}));
            return false;
        }
        if name == "EXTLIST" {
            self.enter_mode("more", action, "--More--", json!({}));
            return false;
        }
        if is_info_command(name) || action.enum_class() == "TextCharacters" {
            self.message(&format!("{} is accepted in normal mode.", action.canonical));
            return false;
        }
        self.message(&format!("{} is accepted but has no fixture effect.", action.canonical));
        false
    }

    fn consume_prompt(&mut self, action: &ActionSpec) -> bool {
        let mode = self.state.input_mode.clone();
        let kind = mode_kind(&mode).to_string();
        if action.name() == "ESC" {
            self.exit_mode("Never mind.");
            return false;
        }
        match kind.as_str() {
            "more" => {
                if action.canonical == "MiscAction.MORE" || matches!(action.key().as_str(), "\r" | "\n" | " ") {
                    self.exit_mode("");
                } else {
                    self.message("--More--");
                }
                false
            }
            "direction" => {
                let Some(direction) = direction_for(action) else {
                    self.message("Specify a direction.");
                    return false;
                };
                self.exit_mode("");
                let operation = string(&mode, "operation", "move");
                match operation.as_str() {
                    "open" => self.open(direction),
                    "close" => self.close(direction),
                    "kick" => self.kick(direction),
                    "fight" | "force" => self.fight_direction(direction, true),
                    "seetrap" => self.inspect_trap(direction),
                    "untrap" => self.untrap(direction),
                    "fire" | "throw" | "zap" => self.projectile(direction, string(&mode, "item_id", ""), &operation),
                    _ => self.move_hero(direction, boolean(&mode, "running", false), boolean(&mode, "force_move", false)),
                }
            }
            "inventory_letter" => {
                let letter = action.key();
                if letter.is_empty() || !letter.chars().all(|ch| !ch.is_control()) {
                    self.message("Choose an inventory letter.");
                    return false;
                }
                let item = self.state.inventory.iter().find(|item| item.letter == letter).cloned();
                let Some(item) = item else {
                    self.message("You don't have that object.");
                    return false;
                };
                let operation = string(&mode, "operation", "apply");
                let after = string(&mode, "after", "normal");
                self.exit_mode("");
                if after == "direction" {
                    self.enter_mode("direction", action, "In what direction?", json!({"operation": operation, "item_id": item.id}));
                    false
                } else {
                    self.use_item(&operation, &item)
                }
            }
            "ynq" => {
                let answer = action.key().to_ascii_lowercase();
                if !matches!(answer.as_str(), "y" | "n" | "q") {
                    self.message("Please answer y, n, or q.");
                    return false;
                }
                let operation = string(&mode, "operation", "");
                self.exit_mode("");
                if answer != "y" {
                    self.message("Never mind.");
                    return false;
                }
                match operation.as_str() {
                    "quit" => {
                        self.terminal("quit", "You quit the dungeon.", "terminal", 0.0);
                        false
                    }
                    "save" => {
                        self.terminal("saved", "Saving is terminal in this single-episode service.", "terminal", 0.0);
                        false
                    }
                    "pray" => {
                        self.message("You begin praying.");
                        self.event("action_applied", "Pray()", None, Some("pray"), "info", json!({}));
                        true
                    }
                    _ => {
                        self.message("That answer is accepted.");
                        false
                    }
                }
            }
            "string" => {
                if action.canonical == "MiscAction.MORE" {
                    let operation = string(&mode, "operation", "command");
                    let text = string(&mode, "buffer", "");
                    self.exit_mode("");
                    if operation == "engrave" {
                        self.state.engraving = text.clone();
                        self.message("You engrave on the floor.");
                        self.event("action_applied", "Engrave()", None, Some("engrave"), "info", json!({"text": text}));
                        true
                    } else {
                        self.message(&format!("#{} is accepted by the capture adapter.", if text.is_empty() { "command" } else { &text }));
                        false
                    }
                } else {
                    let key = action.key();
                    if key.is_empty() || !key.chars().all(|ch| !ch.is_control()) {
                        self.message("Enter printable prompt text or MORE to finish.");
                        return false;
                    }
                    let mut updated = mode.clone();
                    let current = string(&updated, "buffer", "");
                    if let Value::Object(map) = &mut updated {
                        map.insert("buffer".to_string(), Value::String(format!("{current}{key}")));
                    }
                    self.state.input_mode = updated;
                    self.message(&string(&mode, "prompt", ""));
                    false
                }
            }
            "menu" => {
                self.exit_mode("Never mind.");
                false
            }
            _ => {
                self.message("Unknown input mode.");
                false
            }
        }
    }

    fn move_hero(&mut self, direction: (i64, i64), running: bool, force_move: bool) -> bool {
        let moves = if running { 8 } else { 1 };
        let mut moved = false;
        for _ in 0..moves {
            let x = self.state.hero.x + direction.0;
            let y = self.state.hero.y + direction.1;
            if !in_bounds(x, y) {
                if !moved {
                    self.message("You bump into the edge of the known level.");
                }
                break;
            }
            let monster = self.monster_index_at(x, y);
            if let Some(index) = monster {
                if !force_move {
                    self.fight(index);
                    return true;
                }
            }
            let terrain = self.terrain_at(x, y).to_string();
            if matches!(terrain.as_str(), " " | "|" | "-" | "+") {
                if !moved {
                    self.message("You bump into a wall.");
                }
                break;
            }
            if !is_passable(&terrain) {
                if !moved {
                    self.message("You cannot move there.");
                }
                break;
            }
            if monster.is_some() {
                self.message("There is a monster in the way.");
                break;
            }
            self.state.hero.x = x;
            self.state.hero.y = y;
            moved = true;
            self.event("move", &format!("Move({x},{y})"), None, Some("move"), "info", json!({"x": x, "y": y, "running": running}));
            if boolean(self.resolved.get("rules").unwrap_or(&Value::Null), "autopickup", false) {
                self.pickup(true);
            }
            self.trigger_trap(x, y);
            if self.state.terminated {
                return true;
            }
            if !running {
                break;
            }
        }
        if moved {
            self.message("You move.");
        }
        true
    }

    fn open(&mut self, direction: (i64, i64)) -> bool {
        let (x, y) = self.target(direction);
        if in_bounds(x, y) && self.terrain_at(x, y) == "+" {
            self.state.terrain[y as usize][x as usize] = ".".to_string();
            self.message("The door opens.");
            self.event("action_applied", "OpenDoor()", None, Some("open"), "info", json!({"x": x, "y": y}));
        } else {
            self.message("You see no door there.");
        }
        true
    }

    fn close(&mut self, direction: (i64, i64)) -> bool {
        let (x, y) = self.target(direction);
        if in_bounds(x, y) && self.terrain_at(x, y) == "." {
            self.state.terrain[y as usize][x as usize] = "+".to_string();
            self.message("The door closes.");
        } else {
            self.message("You see no open door there.");
        }
        true
    }

    fn kick(&mut self, direction: (i64, i64)) -> bool {
        let (x, y) = self.target(direction);
        if !in_bounds(x, y) || self.terrain_at(x, y) != "+" {
            self.message("You kick at empty space.");
            return true;
        }
        if self.roll(2) == 0 {
            self.state.terrain[y as usize][x as usize] = ".".to_string();
            self.message("The door crashes open!");
        } else {
            self.message("WHAMMM!!!");
        }
        true
    }

    fn fight_direction(&mut self, direction: (i64, i64), force: bool) -> bool {
        let (x, y) = self.target(direction);
        if let Some(index) = self.monster_index_at(x, y) {
            self.fight(index);
        } else if force {
            self.message("You attack thin air.");
        } else {
            self.message("There is nothing to fight.");
        }
        true
    }

    fn fight(&mut self, monster_index: usize) {
        let monster = self.state.monsters[monster_index].clone();
        let weapon_damage = self.item_by_id(&self.state.wielded).map(|item| item.damage).unwrap_or(0);
        let damage = 1 + self.roll(4) + weapon_damage;
        self.state.monsters[monster_index].hp -= damage;
        self.event("fight", &format!("Fight({})", monster.name), None, Some("attack"), "info", json!({"monster": monster.id, "damage": damage}));
        if self.state.monsters[monster_index].hp <= 0 {
            self.state.monsters.remove(monster_index);
            self.state.experience += monster.experience;
            self.state.reward += 0.1;
            self.message(&format!("You kill the {}!", monster.name));
            self.event("kill", &format!("Kill({})", monster.name), None, Some("kill"), "info", json!({"monster": monster.id, "experience": monster.experience}));
        } else {
            self.message(&format!("You hit the {}.", monster.name));
        }
    }

    fn pickup(&mut self, silent: bool) -> bool {
        let x = self.state.hero.x;
        let y = self.state.hero.y;
        let items = self.state.floor_items.iter().filter(|item| item.position.x == x && item.position.y == y).cloned().collect::<Vec<_>>();
        if items.is_empty() {
            if !silent {
                self.message("There is nothing here to pick up.");
            }
            return false;
        }
        for item in &items {
            if item.kind == "$" {
                self.state.gold += item.quantity;
                self.message(&format!("You pick up {} gold piece(s).", item.quantity));
            } else {
                self.state.inventory.push(item.clone());
                assign_inventory_letters(&mut self.state.inventory);
                self.message(&format!("You pick up {}.", item.name));
            }
            self.event("pickup", &format!("Pickup({})", item.name), None, Some("pickup"), "info", json!({"item": item.id, "kind": item.kind}));
            self.state.reward += 0.02;
        }
        let ids = items.iter().map(|item| item.id.clone()).collect::<BTreeSet<_>>();
        self.state.floor_items.retain(|item| !ids.contains(&item.id));
        true
    }

    fn use_item(&mut self, operation: &str, item: &Item) -> bool {
        match operation {
            "eat" => {
                self.remove_inventory_item(&item.id);
                self.state.hunger = (self.state.hunger + item.nutrition).min(2000);
                self.message(&format!("You eat {}.", item.name));
                self.event("eat", &format!("Eat({})", item.name), None, Some("eat"), "info", json!({"item": item.id, "nutrition": item.nutrition}));
                true
            }
            "quaff" => {
                self.remove_inventory_item(&item.id);
                let effect = if item.effect.is_empty() { "healing".to_string() } else { item.effect.clone() };
                if effect == "healing" {
                    self.state.hp = (self.state.hp + 6).min(self.state.hp_max);
                }
                self.message(&format!("You quaff {}.", item.name));
                self.event("action_applied", &format!("Quaff({})", item.name), None, Some("quaff"), "info", json!({"item": item.id, "effect": effect}));
                true
            }
            "read" => {
                self.remove_inventory_item(&item.id);
                self.message(&format!("You read {}.", item.name));
                self.event("action_applied", &format!("Read({})", item.name), None, Some("read"), "info", json!({"item": item.id, "effect": item.effect}));
                true
            }
            "wield" => {
                self.state.wielded = item.id.clone();
                self.message(&format!("You are now wielding {}.", item.name));
                self.event("wear", &format!("Wield({})", item.name), None, Some("wield"), "info", json!({"item": item.id}));
                true
            }
            "wear" => {
                self.state.worn = item.id.clone();
                self.state.ac = (10 - item.armor).max(-10);
                self.message(&format!("You are now wearing {}.", item.name));
                self.event("wear", &format!("Wear({})", item.name), None, Some("wear"), "info", json!({"item": item.id}));
                true
            }
            "takeoff" => {
                if self.state.worn == item.id {
                    self.state.worn.clear();
                    self.state.ac = 10;
                }
                self.message(&format!("You take off {}.", item.name));
                true
            }
            "puton" => {
                if !self.state.accessories.contains(&item.id) {
                    self.state.accessories.push(item.id.clone());
                }
                self.message(&format!("You put on {}.", item.name));
                self.event("wear", &format!("PutOn({})", item.name), None, Some("puton"), "info", json!({"item": item.id}));
                true
            }
            "remove" => {
                self.state.accessories.retain(|entry| entry != &item.id);
                self.message(&format!("You remove {}.", item.name));
                true
            }
            "quiver" => {
                self.state.quiver = item.id.clone();
                self.message(&format!("You ready {} in your quiver.", item.name));
                true
            }
            "drop" => {
                self.remove_inventory_item(&item.id);
                let mut item = item.clone();
                item.position = Position { x: self.state.hero.x, y: self.state.hero.y };
                self.state.floor_items.push(item.clone());
                self.message(&format!("You drop {}.", item.name));
                true
            }
            "fire" | "throw" | "zap" => {
                self.message("Specify a direction.");
                false
            }
            _ => {
                self.message(&format!("You apply {}.", item.name));
                self.event("action_applied", &format!("Use({})", item.name), None, Some(operation), "info", json!({"item": item.id}));
                true
            }
        }
    }

    fn projectile(&mut self, direction: (i64, i64), item_id: String, operation: &str) -> bool {
        let Some(item) = self.item_by_id(&item_id).cloned() else {
            self.message("That item is no longer available.");
            return false;
        };
        let (x, y) = self.target(direction);
        if let Some(index) = self.monster_index_at(x, y) {
            let monster = self.state.monsters[index].clone();
            let damage = (item.damage + self.roll(3)).max(1);
            self.state.monsters[index].hp -= damage;
            if self.state.monsters[index].hp <= 0 {
                self.state.monsters.remove(index);
                self.message(&format!("The {operation} kills the {}!", monster.name));
                self.event("kill", &format!("Kill({})", monster.name), None, Some(operation), "info", json!({"monster": monster.id, "damage": damage}));
            } else {
                self.message(&format!("The {operation} hits the {}.", monster.name));
            }
        } else {
            self.message(&format!("The {operation} flies harmlessly."));
        }
        true
    }

    fn search(&mut self) -> bool {
        let mut found = false;
        for trap in &mut self.state.traps {
            if !trap.seen && (trap.position.x - self.state.hero.x).abs().max((trap.position.y - self.state.hero.y).abs()) <= 1 {
                trap.seen = true;
                found = true;
            }
        }
        self.message(if found { "You find a trap." } else { "You search." });
        true
    }

    fn inspect_trap(&mut self, direction: (i64, i64)) -> bool {
        let (x, y) = self.target(direction);
        let trap = self.state.traps.iter().find(|trap| trap.position.x == x && trap.position.y == y && trap.seen);
        if let Some(trap) = trap {
            self.message(&format!("That is a {} trap.", trap.kind));
        } else {
            self.message("You see no trap there.");
        }
        false
    }

    fn untrap(&mut self, direction: (i64, i64)) -> bool {
        let (x, y) = self.target(direction);
        if let Some(index) = self.state.traps.iter().position(|trap| trap.position.x == x && trap.position.y == y) {
            self.state.traps.remove(index);
            self.message("You disarm the trap.");
        } else {
            self.message("You find no trap to disarm.");
        }
        true
    }

    fn descend(&mut self) -> bool {
        if self.terrain_at(self.state.hero.x, self.state.hero.y) != ">" {
            self.message("You can't go down here.");
            return false;
        }
        self.event("stairs_descend", "StairsDescend(dlvl1)", None, Some("descend"), "info", json!({"dungeon_level": 1}));
        self.terminal("descended", "You descend from dlvl 1.", "terminal", 1.0);
        false
    }

    fn advance_turn(&mut self) {
        self.state.time += 1;
        self.state.hunger = (self.state.hunger - 1).max(0);
        self.update_hunger_state();
        if self.state.hunger == 0 {
            self.state.hp -= 1;
            if self.state.hp <= 0 {
                self.terminal("death", "You die of hunger.", "death", -1.0);
                return;
            }
        }
        let hero = self.state.hero.clone();
        for index in 0..self.state.monsters.len() {
            let monster = self.state.monsters[index].clone();
            if monster.peaceful || monster.pet {
                continue;
            }
            let distance = (monster.position.x - hero.x).abs().max((monster.position.y - hero.y).abs());
            if distance <= 1 {
                let damage = (monster.attack + self.roll(2) - 1).max(1);
                self.state.hp -= damage;
                self.event("fight", &format!("MonsterAttack({})", monster.name), None, Some("monster_attack"), "info", json!({"monster": monster.id, "damage": damage}));
                if self.state.hp <= 0 {
                    self.terminal("death", &format!("You die from the {}'s attack.", monster.name), "death", -1.0);
                    return;
                }
                self.message(&format!("The {} bites!", monster.name));
            } else if distance <= 6 {
                self.move_monster_toward(index, &hero);
            }
        }
    }

    fn move_monster_toward(&mut self, index: usize, hero: &Hero) {
        let monster = self.state.monsters[index].clone();
        let dx = if monster.position.x == hero.x { 0 } else if hero.x > monster.position.x { 1 } else { -1 };
        let dy = if monster.position.y == hero.y { 0 } else if hero.y > monster.position.y { 1 } else { -1 };
        let x = monster.position.x + dx;
        let y = monster.position.y + dy;
        if in_bounds(x, y) && is_passable(self.terrain_at(x, y)) && self.monster_index_at(x, y).is_none() && (x, y) != (hero.x, hero.y) {
            self.state.monsters[index].position = Position { x, y };
        }
    }

    fn trigger_trap(&mut self, x: i64, y: i64) {
        if let Some(index) = self.state.traps.iter().position(|trap| !trap.triggered && trap.position.x == x && trap.position.y == y) {
            let trap = self.state.traps[index].clone();
            self.state.traps[index].triggered = true;
            self.state.traps[index].seen = true;
            self.state.hp -= trap.damage;
            self.message(&format!("You trigger a {} trap!", trap.kind));
            self.event("action_applied", &format!("Trap({})", trap.kind), None, Some("trap"), "info", json!({"trap": trap.id, "damage": trap.damage}));
            if self.state.hp <= 0 {
                self.terminal("death", "You die from a trap.", "death", -1.0);
            }
        }
    }

    fn terminal(&mut self, reason: &str, message: &str, kind: &str, reward_delta: f64) {
        self.state.terminated = true;
        self.state.terminal_reason = reason.to_string();
        self.state.reward += reward_delta;
        self.message(message);
        self.event(kind, &format!("Terminal({reason})"), None, Some(reason), "info", json!({"terminal_reason": reason, "reward_delta": reward_delta}));
    }

    fn check_truncation(&mut self) {
        let max_steps = integer(self.resolved.get("rules").unwrap_or(&Value::Null), "max_steps", 0);
        if max_steps > 0 && self.state.step_index >= max_steps && !self.state.terminated {
            self.state.truncated = true;
            self.state.terminal_reason = "max_steps".to_string();
            self.message("Episode truncated at max_steps.");
            self.event("episode_truncated", "Terminal(max_steps)", None, Some("max_steps"), "info", json!({"max_steps": max_steps}));
        }
    }

    fn render_planes(&self) -> (Vec<String>, Vec<Vec<i64>>, Vec<Vec<i64>>) {
        let mut chars = vec![vec![" ".to_string(); VIEW_WIDTH]; VIEW_HEIGHT];
        let mut colors = vec![vec![0; VIEW_WIDTH]; VIEW_HEIGHT];
        let mut glyphs = vec![vec![0; VIEW_WIDTH]; VIEW_HEIGHT];
        for y in 0..VIEW_HEIGHT {
            for x in 0..VIEW_WIDTH {
                if self.state.seen[y][x] {
                    chars[y][x] = self.state.terrain[y][x].clone();
                    colors[y][x] = self.state.base_colors[y][x];
                    glyphs[y][x] = self.state.base_glyphs[y][x];
                }
            }
        }
        for item in &self.state.floor_items {
            if in_bounds(item.position.x, item.position.y) && self.state.seen[item.position.y as usize][item.position.x as usize] {
                let x = item.position.x as usize;
                let y = item.position.y as usize;
                chars[y][x] = item.kind.clone();
                colors[y][x] = item.color;
                glyphs[y][x] = item.glyph;
            }
        }
        for monster in &self.state.monsters {
            if in_bounds(monster.position.x, monster.position.y) && self.state.seen[monster.position.y as usize][monster.position.x as usize] {
                let x = monster.position.x as usize;
                let y = monster.position.y as usize;
                chars[y][x] = monster.char.clone();
                colors[y][x] = monster.color;
                glyphs[y][x] = monster.glyph;
            }
        }
        let x = self.state.hero.x as usize;
        let y = self.state.hero.y as usize;
        chars[y][x] = "@".to_string();
        colors[y][x] = self.state.hero.color;
        glyphs[y][x] = self.state.hero.glyph;
        (chars.into_iter().map(|row| row.join("")).collect(), colors, glyphs)
    }

    fn inventory_projection(&self) -> Value {
        let mut letters = vec![0i64; 55];
        let mut glyphs = vec![0i64; 55];
        let mut oclasses = vec![0i64; 55];
        let mut strings = vec![String::new(); 55];
        for (index, item) in self.state.inventory.iter().take(55).enumerate() {
            letters[index] = item.letter.chars().next().map(|ch| ch as i64).unwrap_or(0);
            glyphs[index] = item.glyph;
            oclasses[index] = item.oclass;
            strings[index] = format!("{} - {}", item.letter, item.name);
        }
        json!({"inv_letters": letters, "inv_glyphs": glyphs, "inv_oclasses": oclasses, "inv_strs": strings, "items": self.state.inventory})
    }

    fn blstats(&self) -> Vec<i64> {
        vec![
            self.state.hero.x, self.state.hero.y, self.state.strength, 0, self.state.dexterity, self.state.constitution, self.state.intelligence, self.state.wisdom, self.state.charisma, self.state.experience,
            self.state.hp, self.state.hp_max, 1, self.state.gold, self.state.energy, self.state.energy_max, self.state.ac, 1, self.state.experience_level, self.state.experience,
            self.state.time, self.hunger_code(), 0, 0, 1, 0, self.alignment_code(),
        ]
    }

    fn alignment_code(&self) -> i64 {
        let align = self
            .resolved
            .get("character")
            .and_then(|character| character.get("align"))
            .and_then(Value::as_str)
            .unwrap_or("law")
            .to_ascii_lowercase();
        match align.as_str() {
            "law" | "lawful" => 1,
            "cha" | "chaotic" => -1,
            _ => 0,
        }
    }

    fn enter_mode(&mut self, kind: &str, action: &ActionSpec, prompt: &str, extra: Value) {
        let mut mode = Map::new();
        mode.insert("kind".to_string(), Value::String(kind.to_string()));
        mode.insert("command".to_string(), Value::String(action.canonical.clone()));
        mode.insert("prompt".to_string(), Value::String(prompt.to_string()));
        if let Value::Object(entries) = extra {
            for (key, value) in entries {
                mode.insert(key, value);
            }
        }
        self.state.input_mode = Value::Object(mode);
        self.message(prompt);
        self.event("mode_enter", &format!("ModeEnter({kind})"), Some(action.canonical.clone()), Some(kind), "info", self.state.input_mode.clone());
    }

    fn exit_mode(&mut self, message: &str) {
        let prior = self.state.input_mode.clone();
        let kind = mode_kind(&prior).to_string();
        self.state.input_mode = normal_mode();
        self.event("mode_exit", &format!("ModeExit({kind})"), None, Some(&kind), "info", json!({"prior": prior}));
        if !message.is_empty() {
            self.message(message);
        }
    }

    fn message(&mut self, text: &str) {
        self.state.message = text.to_string();
        self.state.message_raw = text.as_bytes().to_vec();
        self.state.message_history.push(text.to_string());
        self.event("message", &format!("Message({text})"), None, Some("message"), "info", json!({"raw": self.state.message_raw}));
    }

    fn event(&mut self, kind: &str, message: &str, action: Option<String>, transition: Option<&str>, severity: &str, payload: Value) {
        self.events.push(NevEvent {
            step_index: self.state.step_index,
            tick: self.state.step_index,
            episode_id: string(&self.resolved, "episode_id", "unresolved"),
            kind: kind.to_string(),
            action,
            transition: transition.map(ToString::to_string),
            severity: severity.to_string(),
            message: message.to_string(),
            payload,
        });
    }

    fn reveal(&mut self) {
        let radius = integer(self.resolved.get("rules").unwrap_or(&Value::Null), "vision_radius", 4);
        for y in (self.state.hero.y - radius).max(0)..=(self.state.hero.y + radius).min((VIEW_HEIGHT - 1) as i64) {
            for x in (self.state.hero.x - radius).max(0)..=(self.state.hero.x + radius).min((VIEW_WIDTH - 1) as i64) {
                self.state.seen[y as usize][x as usize] = true;
            }
        }
    }

    fn update_hunger_state(&mut self) {
        self.state.hunger_state = if self.state.hunger > 1400 {
            "Satiated"
        } else if self.state.hunger > 500 {
            "Not Hungry"
        } else if self.state.hunger > 200 {
            "Hungry"
        } else if self.state.hunger > 0 {
            "Weak"
        } else {
            "Fainting"
        }.to_string();
    }

    fn hunger_code(&self) -> i64 {
        match self.state.hunger_state.as_str() {
            "Satiated" => 0,
            "Not Hungry" => 1,
            "Hungry" => 2,
            "Weak" => 3,
            "Fainting" => 4,
            _ => 1,
        }
    }

    fn roll(&mut self, upper: i64) -> i64 {
        self.state.rng = self.state.rng.wrapping_mul(1664525).wrapping_add(1013904223);
        (self.state.rng as i64) % upper.max(1)
    }

    fn target(&self, direction: (i64, i64)) -> (i64, i64) {
        (self.state.hero.x + direction.0, self.state.hero.y + direction.1)
    }

    fn terrain_at(&self, x: i64, y: i64) -> &str {
        &self.state.terrain[y as usize][x as usize]
    }

    fn monster_index_at(&self, x: i64, y: i64) -> Option<usize> {
        self.state.monsters.iter().position(|monster| monster.position.x == x && monster.position.y == y)
    }

    fn item_by_id(&self, id: &str) -> Option<&Item> {
        self.state.inventory.iter().find(|item| item.id == id)
    }

    fn remove_inventory_item(&mut self, id: &str) {
        self.state.inventory.retain(|item| item.id != id);
        assign_inventory_letters(&mut self.state.inventory);
        if self.state.wielded == id {
            self.state.wielded.clear();
        }
        if self.state.worn == id {
            self.state.worn.clear();
            self.state.ac = 10;
        }
        self.state.accessories.retain(|entry| entry != id);
    }
}

pub fn run_scenario_entry(entry: &Value) -> Result<Value, String> {
    let task = task_from_entry(entry);
    let scenario_id = entry.get("scenario_id").or_else(|| task.get("task_id")).map(value_to_string).unwrap_or_else(|| "manual".to_string());
    let mut session = NethackSession::reset(resolve_task(&task, None)?)?;
    let actions = entry.get("actions").or_else(|| task.get("actions")).and_then(Value::as_array).cloned().unwrap_or_default();
    for action in actions {
        if session.state.terminated || session.state.truncated {
            break;
        }
        session.step(action);
    }
    let readout = session.readout();
    let public = readout.get("public").cloned().unwrap_or_else(|| json!({}));
    let private = readout.get("private").cloned().unwrap_or_else(|| json!({}));
    let checkpoint = String::from_utf8(session.checkpoint_bytes()).map_err(|error| error.to_string())?;
    Ok(json!({
        "scenario_id": scenario_id,
        "events": session.legacy_strings(),
        "nev": session.events,
        "state": {"public": public.clone(), "private": private.clone()},
        "readout": readout,
        "checkpoint": {"blob": checkpoint, "public": public, "private": private},
    }))
}

/// Run a scenario once and retain the public projection after every action.
///
/// This is an oracle-development adapter, not a second engine API: it lets a
/// live NLE fuzzer compare an entire Rust trace without spawning one Cargo
/// process for every action prefix.
pub fn run_scenario_trace_entry(entry: &Value) -> Result<Value, String> {
    let task = task_from_entry(entry);
    let scenario_id = entry
        .get("scenario_id")
        .or_else(|| task.get("task_id"))
        .map(value_to_string)
        .unwrap_or_else(|| "manual".to_string());
    let mut session = NethackSession::reset(resolve_task(&task, None)?)?;
    let actions = entry
        .get("actions")
        .or_else(|| task.get("actions"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut snapshots = vec![session.public_projection()];
    let mut applied_actions = Vec::new();
    for action in actions {
        if session.state.terminated || session.state.truncated {
            break;
        }
        applied_actions.push(action.clone());
        session.step(action);
        snapshots.push(session.public_projection());
    }
    let readout = session.readout();
    let checkpoint = String::from_utf8(session.checkpoint_bytes()).map_err(|error| error.to_string())?;
    Ok(json!({
        "scenario_id": scenario_id,
        "actions_applied": applied_actions,
        "snapshots": snapshots,
        "readout": readout,
        "checkpoint": checkpoint,
    }))
}

pub fn task_from_entry(entry: &Value) -> Value {
    if let Some(task) = entry.get("task") {
        return task.clone();
    }
    let mut task = object_or_empty(Some(entry));
    task.remove("actions");
    task.remove("expected");
    task.remove("required_nev_kinds");
    Value::Object(task)
}

pub fn resolve_task(task: &Value, seed_override: Option<i64>) -> Result<Value, String> {
    let data = object_or_empty(Some(task));
    let fixture_id = string_map(&data, "fixture_id", "");
    if !fixture_id.is_empty() && data.get("level_dump").is_none() {
        return Err(format!("Rust gold requires materialized level_dump for fixture {fixture_id:?}"));
    }
    let level_source = data.get("level_dump").cloned().unwrap_or_else(|| json!({"grid": data.get("grid").cloned().unwrap_or_else(|| json!([]))}));
    let level_dump = normalize_level_dump(&level_source)?;
    let mut character = Map::new();
    character.insert("role".to_string(), json!("val"));
    character.insert("race".to_string(), json!("hum"));
    character.insert("gender".to_string(), json!("fem"));
    character.insert("align".to_string(), json!("law"));
    character.insert("nle_character".to_string(), json!("val-hum-fem-law"));
    if let Some(Value::Object(overrides)) = data.get("character") {
        for (key, value) in overrides {
            character.insert(key.clone(), value.clone());
        }
    }
    let mut rules = Map::new();
    rules.insert("max_steps".to_string(), json!(0));
    rules.insert("autopickup".to_string(), json!(false));
    rules.insert("auto_more".to_string(), json!("raw_explicit"));
    rules.insert("vision_radius".to_string(), json!(4));
    if let Some(Value::Object(overrides)) = data.get("rules") {
        for (key, value) in overrides {
            rules.insert(key.clone(), value.clone());
        }
    }
    if string_map(&rules, "auto_more", "") != "raw_explicit" {
        return Err("only raw_explicit MORE is supported by the pinned capture contract".to_string());
    }
    let seed = seed_override.unwrap_or_else(|| integer_map(&data, "seed", 0));
    let task_id = data.get("task_id").or_else(|| data.get("scenario_id")).map(|value| value_to_string(value)).unwrap_or_else(|| if fixture_id.is_empty() { "manual".to_string() } else { fixture_id.clone() });
    let mut core = Map::new();
    core.insert("schema".to_string(), json!("gamebench.task.nethack_dlvl1.v1"));
    core.insert("task_id".to_string(), json!(task_id));
    core.insert("fixture_id".to_string(), json!(fixture_id));
    core.insert("seed".to_string(), json!(seed));
    core.insert("character".to_string(), Value::Object(character));
    core.insert("rules".to_string(), Value::Object(rules));
    core.insert("level_dump".to_string(), level_dump);
    core.insert("nle_meta".to_string(), json!({}));
    let config_hash = digest_value(&Value::Object(core.clone()));
    let task_id_for_episode = string_map(&core, "task_id", "manual");
    let episode_id = format!("nethack-dlvl1:{}:{}", task_id_for_episode, &config_hash[7..19]);
    core.insert("config_hash".to_string(), Value::String(config_hash));
    core.insert("episode_id".to_string(), Value::String(episode_id));
    Ok(Value::Object(core))
}

fn normalize_level_dump(raw: &Value) -> Result<Value, String> {
    let data = object_or_empty(Some(raw));
    let terrain_source = data.get("terrain").or_else(|| data.get("chars")).or_else(|| data.get("grid"));
    let mut terrain = normalise_rows(terrain_source);
    let hero_raw = data.get("hero").cloned().unwrap_or_else(|| json!({}));
    let hero_explicit = hero_raw.get("x").is_some() || hero_raw.get("y").is_some();
    let mut hero_x = integer(&hero_raw, "x", 0);
    let mut hero_y = integer(&hero_raw, "y", 0);
    let mut hero_found = false;
    for y in 0..VIEW_HEIGHT {
        for x in 0..VIEW_WIDTH {
            if terrain[y][x] == "@" {
                hero_x = x as i64;
                hero_y = y as i64;
                terrain[y][x] = ".".to_string();
                hero_found = true;
            }
        }
    }
    if !hero_found && !hero_explicit {
        return Err("level_dump must contain @ or an explicit hero position".to_string());
    }
    if !in_bounds(hero_x, hero_y) {
        return Err("level_dump must contain a hero position inside the 21x79 crop".to_string());
    }
    if data.get("branches").and_then(Value::as_array).map(|entries| !entries.is_empty()).unwrap_or(false) || data.get("mines_entry").and_then(Value::as_bool).unwrap_or(false) {
        return Err("dlvl-1 fixture contains a branch/Mines entry; reject it instead of modeling branch geography".to_string());
    }
    let depth = data.get("dungeon_level").or_else(|| data.get("depth")).and_then(Value::as_i64).unwrap_or(1);
    if depth != 1 {
        return Err(format!("only Main Dungeon dlvl 1 is in scope, got level {depth}"));
    }
    let glyphs = normalize_int_rows(data.get("glyphs"), &terrain, -1);
    let colors = normalize_int_rows(data.get("colors"), &terrain, 7);
    let seen = normalize_seen(data.get("seen"), &terrain);
    let objects = data.get("objects").or_else(|| data.get("items")).and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| serde_json::to_value(item_from_value(item, index, true)).unwrap()).collect::<Vec<_>>();
    let inventory = data.get("inventory").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| serde_json::to_value(item_from_value(item, index, false)).unwrap()).collect::<Vec<_>>();
    let monsters = data.get("monsters").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| serde_json::to_value(monster_from_value(item, index)).unwrap()).collect::<Vec<_>>();
    let traps = data.get("traps").and_then(Value::as_array).cloned().unwrap_or_default().iter().enumerate().map(|(index, item)| serde_json::to_value(trap_from_value(item, index)).unwrap()).collect::<Vec<_>>();
    let hero_object = json!({"x": hero_x, "y": hero_y, "glyph": integer(&hero_raw, "glyph", '@' as i64), "color": integer(&hero_raw, "color", 15)});
    Ok(json!({
        "schema": "gamebench.nethack.level_dump.v1",
        "terrain": terrain.iter().map(|row| row.join("")).collect::<Vec<_>>(),
        "glyphs": glyphs,
        "colors": colors,
        "seen": seen,
        "hero": hero_object,
        "objects": objects,
        "inventory": inventory,
        "monsters": monsters,
        "traps": traps,
        "dungeon_level": 1,
        "metadata": data.get("metadata").cloned().unwrap_or_else(|| json!({})),
    }))
}

fn normalise_rows(raw: Option<&Value>) -> Vec<Vec<String>> {
    let source = raw.and_then(Value::as_array).cloned().unwrap_or_default();
    let mut rows = Vec::new();
    for row in source.iter().take(VIEW_HEIGHT) {
        let mut cells = if let Some(text) = row.as_str() {
            text.chars().map(|ch| ch.to_string()).collect::<Vec<_>>()
        } else if let Some(values) = row.as_array() {
            values.iter().map(as_char).collect::<Vec<_>>()
        } else {
            Vec::new()
        };
        cells.resize(VIEW_WIDTH, " ".to_string());
        cells.truncate(VIEW_WIDTH);
        rows.push(cells);
    }
    while rows.len() < VIEW_HEIGHT {
        rows.push(vec![" ".to_string(); VIEW_WIDTH]);
    }
    rows
}

fn normalize_int_rows(raw: Option<&Value>, terrain: &[Vec<String>], default: i64) -> Vec<Vec<i64>> {
    let source = raw.and_then(Value::as_array).cloned().unwrap_or_default();
    (0..VIEW_HEIGHT).map(|y| {
        let original = source.get(y).and_then(Value::as_array).cloned().unwrap_or_default();
        (0..VIEW_WIDTH).map(|x| {
            match original.get(x) {
                Some(Value::Bool(value)) => i64::from(*value),
                Some(Value::Number(number)) => number.as_i64().unwrap_or_else(|| number.as_f64().unwrap_or(0.0) as i64),
                _ if default == -1 => terrain[y][x].chars().next().map(|ch| ch as i64).unwrap_or(' ' as i64),
                _ => default,
            }
        }).collect()
    }).collect()
}

fn normalize_seen(raw: Option<&Value>, terrain: &[Vec<String>]) -> Vec<Vec<bool>> {
    let source = raw.and_then(Value::as_array).cloned();
    (0..VIEW_HEIGHT).map(|y| {
        (0..VIEW_WIDTH).map(|x| {
            source.as_ref().and_then(|rows| rows.get(y)).and_then(Value::as_array).and_then(|row| row.get(x)).map(|value| value.as_bool().unwrap_or(false)).unwrap_or_else(|| terrain[y][x] != " ")
        }).collect()
    }).collect()
}

fn item_from_value(value: &Value, index: usize, floor: bool) -> Item {
    let data = object_or_empty(Some(value));
    let position_source = data.get("position").or_else(|| data.get("pos")).unwrap_or(value);
    let position = Position { x: integer(position_source, "x", 0), y: integer(position_source, "y", 0) };
    let letter = data.get("letter").or_else(|| data.get("inv_letter")).map(value_to_string).unwrap_or_default().chars().take(1).collect();
    let kind_source = data.get("kind").or_else(|| data.get("oclass")).or_else(|| data.get("class"));
    let kind = kind_source.map(value_to_string).unwrap_or_else(|| ")".to_string()).chars().next().unwrap_or(')').to_string();
    let name = data.get("name").or_else(|| data.get("description")).map(value_to_string).unwrap_or_else(|| "unknown object".to_string());
    let prefix = if floor { "floor" } else { "inventory" };
    Item {
        id: data.get("id").map(value_to_string).unwrap_or_else(|| format!("{prefix}-{index}")),
        letter,
        kind: kind.clone(),
        name,
        quantity: integer_map(&data, "quantity", integer_map(&data, "count", 1)).max(1),
        glyph: integer_map(&data, "glyph", kind.chars().next().unwrap_or(')') as i64),
        color: integer_map(&data, "color", 7),
        oclass: integer_map(&data, "oclass_code", kind.chars().next().unwrap_or(')') as i64),
        nutrition: integer_map(&data, "nutrition", if kind == "%" { 600 } else { 0 }),
        damage: integer_map(&data, "damage", if kind == ")" { 2 } else { 0 }).max(0),
        armor: integer_map(&data, "armor", if kind == "[" { 1 } else { 0 }),
        effect: string_map(&data, "effect", ""),
        position,
    }
}

fn monster_from_value(value: &Value, index: usize) -> Monster {
    let data = object_or_empty(Some(value));
    let position_source = data.get("position").or_else(|| data.get("pos")).unwrap_or(value);
    let char = data.get("char").or_else(|| data.get("symbol")).map(value_to_string).unwrap_or_else(|| "j".to_string()).chars().next().unwrap_or('j').to_string();
    let hp = integer_map(&data, "hp", 4).max(1);
    Monster {
        id: string_map(&data, "id", &format!("monster-{index}")),
        name: string_map(&data, "name", "jackal"),
        char: char.clone(),
        glyph: integer_map(&data, "glyph", char.chars().next().unwrap_or('j') as i64),
        color: integer_map(&data, "color", 6),
        hp,
        hp_max: integer_map(&data, "hp_max", hp).max(hp),
        attack: integer_map(&data, "attack", 2).max(0),
        experience: integer_map(&data, "experience", 2).max(0),
        peaceful: boolean_map(&data, "peaceful", false),
        pet: boolean_map(&data, "pet", false),
        position: Position { x: integer(position_source, "x", 0), y: integer(position_source, "y", 0) },
    }
}

fn trap_from_value(value: &Value, index: usize) -> Trap {
    let data = object_or_empty(Some(value));
    let position_source = data.get("position").or_else(|| data.get("pos")).unwrap_or(value);
    Trap {
        id: string_map(&data, "id", &format!("trap-{index}")),
        kind: string_map(&data, "kind", "arrow"),
        damage: integer_map(&data, "damage", 2).max(0),
        seen: boolean_map(&data, "seen", false),
        triggered: boolean_map(&data, "triggered", false),
        position: Position { x: integer(position_source, "x", 0), y: integer(position_source, "y", 0) },
    }
}

fn assign_inventory_letters(inventory: &mut [Item]) {
    let mut used = inventory.iter().filter_map(|item| if item.letter.is_empty() { None } else { Some(item.letter.clone()) }).collect::<BTreeSet<_>>();
    let mut candidates = ('a'..='z').map(|ch| ch.to_string());
    for item in inventory {
        if !item.letter.is_empty() {
            continue;
        }
        let letter = candidates.find(|candidate| !used.contains(candidate)).unwrap_or_else(|| "?".to_string());
        item.letter = letter.clone();
        used.insert(letter);
    }
}

fn action_specs() -> Vec<ActionSpec> {
    let raw: Value = serde_json::from_str(include_str!("../../shared/nle_action_map.json")).expect("valid checked-in action map");
    raw.get("actions").and_then(Value::as_array).cloned().unwrap_or_default().into_iter().filter_map(|entry| {
        let cells = entry.as_array()?;
        Some(ActionSpec { id: cells.first()?.as_u64()? as usize, canonical: cells.get(1)?.as_str()?.to_string(), value: cells.get(2)?.as_i64()? })
    }).collect()
}

fn coerce_action(input: &Value) -> Option<ActionSpec> {
    let actions = action_specs();
    if let Some(id) = input.as_i64() {
        return actions.into_iter().find(|action| action.id == id as usize);
    }
    let raw = input.as_str()?;
    let token = raw.trim();
    if let Ok(id) = token.parse::<usize>() {
        return actions.into_iter().find(|action| action.id == id);
    }
    if let Some(action) = actions.iter().find(|action| action.canonical == token) {
        return Some(action.clone());
    }
    let aliases = BTreeMap::from([
        ("up", "MiscDirection.UP"), ("down", "MiscDirection.DOWN"), ("wait", "MiscDirection.WAIT"), ("more", "MiscAction.MORE"), ("escape", "Command.ESC"), ("inventory", "Command.INVENTORY"), ("pickup", "Command.PICKUP"), ("open", "Command.OPEN"), ("close", "Command.CLOSE"), ("kick", "Command.KICK"), ("search", "Command.SEARCH"), ("eat", "Command.EAT"), ("wear", "Command.WEAR"), ("wield", "Command.WIELD"), ("quit", "Command.QUIT"),
    ]);
    if !token.contains('.') {
        if let Some(canonical) = aliases.get(token.to_ascii_lowercase().as_str()) {
            return actions.iter().find(|action| action.canonical == *canonical).cloned();
        }
        let upper = token.to_ascii_uppercase();
        for enum_class in ["CompassDirection", "CompassDirectionLonger", "MiscDirection", "MiscAction", "Command", "TextCharacters"] {
            let candidate = format!("{enum_class}.{upper}");
            if let Some(action) = actions.iter().find(|action| action.canonical == candidate) {
                return Some(action.clone());
            }
        }
    }
    if raw.chars().count() == 1 {
        return actions.into_iter().find(|action| action.key() == raw);
    }
    None
}

fn direction_for(action: &ActionSpec) -> Option<(i64, i64)> {
    if !matches!(action.enum_class(), "CompassDirection" | "CompassDirectionLonger") {
        return None;
    }
    match action.name() {
        "N" => Some((0, -1)), "E" => Some((1, 0)), "S" => Some((0, 1)), "W" => Some((-1, 0)),
        "NE" => Some((1, -1)), "SE" => Some((1, 1)), "SW" => Some((-1, 1)), "NW" => Some((-1, -1)),
        _ => None,
    }
}

fn is_info_command(name: &str) -> bool {
    matches!(name,
        "ADJUST" | "ANNOTATE" | "ATTRIBUTES" | "AUTOPICKUP" | "CALL" | "CONDUCT" | "ENHANCE" | "EXTLIST" | "GLANCE" | "HISTORY" | "INVENTTYPE" | "KNOWN" | "KNOWNCLASS" | "LOOK" | "MONSTER" | "OPTIONS" | "OVERVIEW" | "PAY" | "REDRAW" | "SEEALL" | "SEEAMULET" | "SEEARMOR" | "SEEGOLD" | "SEERINGS" | "SEESPELLS" | "SEETOOLS" | "SEEWEAPON" | "SHELL" | "SIT" | "SWAP" | "TELEPORT" | "TRAVEL" | "TURN" | "TWOWEAPON" | "VERSION" | "VERSIONSHORT" | "WHATDOES" | "WHATIS" | "WIPE"
    )
}

fn is_passable(cell: &str) -> bool {
    matches!(cell, "." | "#" | ">" | "<" | "_" | "{" | "}" | "\\" | "~" | "^")
}

fn in_bounds(x: i64, y: i64) -> bool {
    (0..VIEW_WIDTH as i64).contains(&x) && (0..VIEW_HEIGHT as i64).contains(&y)
}

fn normal_mode() -> Value {
    json!({"kind": "normal", "command": "", "prompt": "", "operation": ""})
}

fn mode_kind(value: &Value) -> &str {
    value.get("kind").and_then(Value::as_str).unwrap_or("")
}

fn normalize_message(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn object_or_empty(value: Option<&Value>) -> Map<String, Value> {
    value.and_then(Value::as_object).cloned().unwrap_or_default()
}

fn integer(value: &Value, key: &str, default: i64) -> i64 {
    value.get(key).and_then(|item| item.as_i64().or_else(|| item.as_f64().map(|number| number as i64))).unwrap_or(default)
}

fn integer_map(value: &Map<String, Value>, key: &str, default: i64) -> i64 {
    value.get(key).and_then(|item| item.as_i64().or_else(|| item.as_f64().map(|number| number as i64))).unwrap_or(default)
}

fn boolean(value: &Value, key: &str, default: bool) -> bool {
    value.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn boolean_map(value: &Map<String, Value>, key: &str, default: bool) -> bool {
    value.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn string(value: &Value, key: &str, default: &str) -> String {
    value.get(key).map(value_to_string).unwrap_or_else(|| default.to_string())
}

fn string_map(value: &Map<String, Value>, key: &str, default: &str) -> String {
    value.get(key).map(value_to_string).unwrap_or_else(|| default.to_string())
}

fn value_to_string(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        Value::Null => String::new(),
        Value::Bool(flag) => flag.to_string(),
        Value::Number(number) => number.to_string(),
        _ => value.to_string(),
    }
}

fn as_char(value: &Value) -> String {
    if let Some(number) = value.as_i64() {
        return char::from_u32(number as u32).map(|ch| ch.to_string()).unwrap_or_else(|| " ".to_string());
    }
    value_to_string(value).chars().next().unwrap_or(' ').to_string()
}

fn int_matrix(value: Option<&Value>) -> Vec<Vec<i64>> {
    value.and_then(Value::as_array).cloned().unwrap_or_default().into_iter().map(|row| row.as_array().cloned().unwrap_or_default().into_iter().map(|cell| cell.as_i64().unwrap_or(0)).collect()).collect()
}

fn bool_matrix(value: Option<&Value>) -> Vec<Vec<bool>> {
    value.and_then(Value::as_array).cloned().unwrap_or_default().into_iter().map(|row| row.as_array().cloned().unwrap_or_default().into_iter().map(|cell| cell.as_bool().unwrap_or(false)).collect()).collect()
}

fn canonical_json(value: &Value) -> String {
    match value {
        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_) => serde_json::to_string(value).expect("serializable scalar"),
        Value::Array(values) => format!("[{}]", values.iter().map(canonical_json).collect::<Vec<_>>().join(",")),
        Value::Object(values) => {
            let mut entries = values.iter().collect::<Vec<_>>();
            entries.sort_by(|left, right| left.0.cmp(right.0));
            let content = entries.into_iter().map(|(key, value)| format!("{}:{}", serde_json::to_string(key).expect("serializable key"), canonical_json(value))).collect::<Vec<_>>().join(",");
            format!("{{{content}}}")
        }
    }
}

fn digest_value(value: &Value) -> String {
    let mut digest = Sha256::new();
    digest.update(canonical_json(value).as_bytes());
    format!("sha256:{:x}", digest.finalize())
}
