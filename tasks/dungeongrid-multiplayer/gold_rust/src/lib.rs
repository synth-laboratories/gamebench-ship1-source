use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd, Serialize, Deserialize)]
pub struct Pos {
    pub x: i32,
    pub y: i32,
}

impl Pos {
    pub fn step(self, direction: Direction) -> Self {
        let (dx, dy) = direction.delta();
        Self {
            x: self.x + dx,
            y: self.y + dy,
        }
    }

    pub fn manhattan(self, other: Pos) -> i32 {
        (self.x - other.x).abs() + (self.y - other.y).abs()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    North,
    South,
    West,
    East,
}

impl Direction {
    pub fn delta(self) -> (i32, i32) {
        match self {
            Direction::North => (0, -1),
            Direction::South => (0, 1),
            Direction::West => (-1, 0),
            Direction::East => (1, 0),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "type")]
pub enum DungeonGridAction {
    Move {
        direction: Direction,
    },
    OpenDoor {
        target: String,
    },
    AttackMelee {
        target: String,
    },
    Cast {
        target: String,
        payload: SpellPayload,
    },
    InspectTile {
        target: Pos,
    },
    SearchTraps,
    Interact {
        target: String,
    },
    Message {
        target: String,
        payload: MessagePayload,
    },
    UseItem {
        target: String,
    },
    GiveItem {
        target: String,
        payload: GiveItemPayload,
    },
    Guard,
    EndTurn,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct MessagePayload {
    pub text: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct DeliveredMessage {
    pub from: String,
    pub target: String,
    pub text: String,
    pub step_index: u32,
    pub turn_index: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObservationMode {
    Global,
    Local,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct ObservationConfig {
    pub mode: ObservationMode,
    pub visibility_radius: i32,
    pub communication_enabled: bool,
}

impl Default for ObservationConfig {
    fn default() -> Self {
        Self {
            mode: ObservationMode::Global,
            visibility_radius: 3,
            communication_enabled: true,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct SpellPayload {
    pub spell: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct GiveItemPayload {
    pub item: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EventRecord {
    pub step_index: u32,
    pub turn_index: u32,
    pub episode_id: String,
    pub agent_id: String,
    pub kind: String,
    pub severity: String,
    pub message: String,
    pub action: Option<Value>,
    pub transition: Option<Value>,
    pub payload: Value,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Terrain {
    Wall,
    Floor,
    Escape,
    Objective,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DoorState {
    pub id: String,
    pub pos: Pos,
    pub open: bool,
    pub secret: bool,
    pub discovered: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrapState {
    pub id: String,
    pub pos: Pos,
    pub revealed: bool,
    pub armed: bool,
    pub damage: i32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChestState {
    pub id: String,
    pub pos: Pos,
    pub opened: bool,
    pub contents: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MonsterState {
    pub id: String,
    pub role: String,
    pub pos: Pos,
    pub hp: i32,
    pub max_hp: i32,
    pub attack: i32,
    pub guard: i32,
    pub awake: bool,
    pub statuses: BTreeSet<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HeroState {
    pub agent_id: String,
    pub role: String,
    pub pos: Pos,
    pub hp: i32,
    pub max_hp: i32,
    pub ap: i32,
    pub max_ap: i32,
    pub inventory: Vec<String>,
    pub guarded: bool,
    pub messages_sent: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ObjectiveState {
    pub item_id: String,
    pub pos: Pos,
    pub holder: Option<String>,
    pub escape_tile: Pos,
    pub secured: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Scenario {
    pub task_id: String,
    pub scenario_id: String,
    pub quest_id: String,
    pub title: String,
    pub seed: i64,
    pub max_steps: u32,
    pub map_ascii: String,
    pub hero_roles: Vec<String>,
    pub objective_item: String,
    #[serde(default)]
    pub observation: ObservationConfig,
    pub metadata: BTreeMap<String, Value>,
}

impl Scenario {
    pub fn from_json_str(text: &str) -> Result<Self, String> {
        serde_json::from_str(text)
            .map_err(|err| format!("invalid DungeonGrid scenario JSON: {err}"))
    }

    pub fn from_json_value(value: Value) -> Result<Self, String> {
        serde_json::from_value(value)
            .map_err(|err| format!("invalid DungeonGrid scenario value: {err}"))
    }

    pub fn lantern_crypt_lite() -> Self {
        let metadata = BTreeMap::from([
            (
                "marl_axis".to_string(),
                json!("role-specialized causal counterplay"),
            ),
            (
                "coordination_type".to_string(),
                json!("support action before damage commitment"),
            ),
            (
                "coordination_skills".to_string(),
                json!([
                    "assign a clue reader or altar breaker before the boss engage",
                    "screen the support hero while counterplay is prepared",
                    "communicate when the guardian has been weakened enough to commit"
                ]),
            ),
        ]);
        Self {
            task_id: "dg_lantern_crypt_lite_rust_smoke".to_string(),
            scenario_id: "lantern_crypt_lite".to_string(),
            quest_id: "base:lantern_crypt:lite".to_string(),
            title: "Lantern Crypt Lite".to_string(),
            seed: 1,
            max_steps: 120,
            map_ascii: "###########\n#E..D.....#\n#...#..I..#\n#...#..R..#\n###D#######\n#..T.C....#\n###########".to_string(),
            hero_roles: vec!["barbarian".to_string(), "wizard".to_string()],
            objective_item: "little_ember_idol".to_string(),
            observation: ObservationConfig::default(),
            metadata,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DungeonGridSession {
    pub scenario: Scenario,
    pub episode_id: String,
    pub width: i32,
    pub height: i32,
    pub terrain: BTreeMap<Pos, Terrain>,
    pub doors: BTreeMap<String, DoorState>,
    pub traps: BTreeMap<String, TrapState>,
    pub chests: BTreeMap<String, ChestState>,
    pub monsters: BTreeMap<String, MonsterState>,
    pub heroes: BTreeMap<String, HeroState>,
    pub message_inboxes: BTreeMap<String, Vec<DeliveredMessage>>,
    pub active_agent: String,
    pub turn_order: Vec<String>,
    pub turn_cursor: usize,
    pub step_index: u32,
    pub turn_index: u32,
    pub reward_last: f64,
    pub total_reward: f64,
    pub done: bool,
    pub success: bool,
    pub terminal_reason: Option<String>,
    pub achievements: BTreeSet<String>,
    pub event_log: Vec<EventRecord>,
}

impl DungeonGridSession {
    pub fn reset(scenario: Scenario) -> Result<Self, String> {
        let parsed = ParsedMap::parse(&scenario)?;
        let mut heroes = BTreeMap::new();
        let mut turn_order = Vec::new();
        for (idx, role) in scenario.hero_roles.iter().enumerate() {
            let agent_id = format!("agent_{idx}");
            turn_order.push(agent_id.clone());
            heroes.insert(
                agent_id.clone(),
                HeroState {
                    agent_id,
                    role: role.clone(),
                    pos: parsed.entry,
                    hp: 6,
                    max_hp: 6,
                    ap: 2,
                    max_ap: 2,
                    inventory: starting_inventory(role),
                    guarded: false,
                    messages_sent: 0,
                },
            );
        }
        if turn_order.is_empty() {
            return Err("scenario must define at least one hero role".to_string());
        }
        let active_agent = turn_order[0].clone();
        let message_inboxes = turn_order
            .iter()
            .cloned()
            .map(|agent_id| (agent_id, Vec::new()))
            .collect();
        let episode_id = episode_id(&scenario);
        let mut session = Self {
            scenario,
            episode_id,
            width: parsed.width,
            height: parsed.height,
            terrain: parsed.terrain,
            doors: parsed.doors,
            traps: parsed.traps,
            chests: parsed.chests,
            monsters: parsed.monsters,
            heroes,
            message_inboxes,
            active_agent,
            turn_order,
            turn_cursor: 0,
            step_index: 0,
            turn_index: 1,
            reward_last: 0.0,
            total_reward: 0.0,
            done: false,
            success: false,
            terminal_reason: None,
            achievements: BTreeSet::new(),
            event_log: Vec::new(),
        };
        session.append_event(
            "episode_reset",
            "info",
            format!(
                "EpisodeReset({},{})",
                session.scenario.quest_id, session.episode_id
            ),
            None,
            None,
            json!({
                "scenario": session.scenario,
                "state": session.rich_state(),
            }),
        );
        session.append_event(
            "turn_started",
            "info",
            format!("TurnStarted({})", session.active_agent),
            None,
            None,
            json!({"active_agent": session.active_agent}),
        );
        Ok(session)
    }

    pub fn step(&mut self, action: DungeonGridAction) -> StepResult {
        let action_json = serde_json::to_value(&action).unwrap_or(json!(null));
        if self.done {
            self.reward_last = 0.0;
            self.append_event(
                "action_rejected",
                "warning",
                "ActionRejected(terminal)".to_string(),
                Some(action_json.clone()),
                None,
                json!({"reason": "terminal"}),
            );
            return self.step_result(false, vec![self.last_event().clone()]);
        }

        let before = self.transition_snapshot();
        self.reward_last = 0.0;
        let mut applied = true;
        let ap_cost = action_ap_cost(&action);
        if self.heroes[&self.active_agent].ap < ap_cost {
            self.reject(
                action_json.clone(),
                "insufficient_ap",
                json!({
                    "required": ap_cost,
                    "available": self.heroes[&self.active_agent].ap,
                }),
            );
            return self.step_result(false, vec![self.last_event().clone()]);
        }
        match action.clone() {
            DungeonGridAction::Move { direction } => {
                self.apply_move(direction, action_json.clone())
            }
            DungeonGridAction::OpenDoor { target } => {
                self.apply_open_door(&target, action_json.clone())
            }
            DungeonGridAction::AttackMelee { target } => {
                self.apply_attack_melee(&target, action_json.clone())
            }
            DungeonGridAction::Cast { target, payload } => {
                self.apply_cast(&target, &payload, action_json.clone())
            }
            DungeonGridAction::InspectTile { target } => {
                self.apply_inspect_tile(target, action_json.clone())
            }
            DungeonGridAction::SearchTraps => self.apply_search_traps(action_json.clone()),
            DungeonGridAction::Interact { target } => {
                self.apply_interact(&target, action_json.clone())
            }
            DungeonGridAction::Message { target, payload } => {
                self.apply_message(&target, &payload, action_json.clone())
            }
            DungeonGridAction::UseItem { target } => {
                self.apply_use_item(&target, action_json.clone())
            }
            DungeonGridAction::GiveItem { target, payload } => {
                self.apply_give_item(&target, &payload, action_json.clone())
            }
            DungeonGridAction::Guard => self.apply_guard(action_json.clone()),
            DungeonGridAction::EndTurn => {
                self.append_event(
                    "end_turn",
                    "info",
                    format!("EndTurn({})", self.active_agent),
                    Some(action_json.clone()),
                    None,
                    json!({}),
                );
                self.advance_turn();
            }
        }
        if self.last_event().kind == "action_rejected" {
            applied = false;
        }
        if applied && ap_cost > 0 {
            if let Some(hero) = self.heroes.get_mut(&self.active_agent) {
                hero.ap = (hero.ap - ap_cost).max(0);
            }
        }
        if applied && !self.done && !matches!(action, DungeonGridAction::EndTurn) {
            self.step_index += 1;
            self.check_trap();
            self.check_terminal();
            if self.step_index >= self.scenario.max_steps && !self.done {
                self.done = true;
                self.terminal_reason = Some("max_steps".to_string());
                self.append_event(
                    "episode_truncated",
                    "info",
                    format!("EpisodeTruncated(max_steps={})", self.scenario.max_steps),
                    None,
                    None,
                    json!({"max_steps": self.scenario.max_steps}),
                );
            }
        }
        if applied && self.reward_last != 0.0 {
            self.total_reward += self.reward_last;
            self.append_event(
                "reward",
                "info",
                format!(
                    "Reward({:.2},total={:.2})",
                    self.reward_last, self.total_reward
                ),
                None,
                None,
                json!({"reward_last": self.reward_last, "total_reward": self.total_reward}),
            );
        }
        let after = self.transition_snapshot();
        if applied {
            let transition = json!({"before": before, "after": after});
            self.append_event(
                "state_updated",
                "debug",
                format!("StateUpdated(step={})", self.step_index),
                Some(action_json),
                Some(transition),
                json!({}),
            );
        }
        let recent_events = self
            .event_log
            .iter()
            .rev()
            .take(8)
            .cloned()
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect();
        self.step_result(applied, recent_events)
    }

    pub fn rich_state(&self) -> Value {
        self.rich_state_core(true)
    }

    pub fn state_digest(&self) -> Result<String, String> {
        digest_json(&self.rich_state_core(false))
    }

    fn rich_state_core(&self, include_event_tail: bool) -> Value {
        let event_log_tail = if include_event_tail {
            self.event_log
                .iter()
                .rev()
                .take(12)
                .cloned()
                .collect::<Vec<_>>()
        } else {
            Vec::new()
        };
        json!({
            "schema": "gamebench.dungeongrid.state.v1",
            "episode_id": self.episode_id,
            "task_id": self.scenario.task_id,
            "scenario_id": self.scenario.scenario_id,
            "quest_id": self.scenario.quest_id,
            "title": self.scenario.title,
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "active_agent": self.active_agent,
            "turn_order": self.turn_order,
            "done": self.done,
            "success": self.success,
            "terminal_reason": self.terminal_reason,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "achievements": self.achievements,
            "metadata": self.scenario.metadata,
            "map": {
                "width": self.width,
                "height": self.height,
                "ascii": self.render_ascii(),
                "terrain": terrain_cells_json(&self.terrain),
            },
            "heroes": self.heroes,
            "message_inboxes": self.message_inboxes,
            "doors": self.doors,
            "traps": self.traps,
            "chests": self.chests,
            "monsters": self.monsters,
            "objective": self.objective_state(),
            "legal_actions": self.legal_actions(),
            "coordination": self.coordination_state(),
            "event_log_tail": event_log_tail,
        })
    }

    pub fn reset_to_initial(&mut self) -> Result<(), String> {
        *self = Self::reset(self.scenario.clone())?;
        Ok(())
    }

    pub fn checkpoint_json(&self) -> Value {
        json!({
            "schema": "gamebench.dungeongrid.checkpoint.v1",
            "episode_id": self.episode_id,
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "scenario": self.scenario,
            "dynamic": {
                "heroes": self.heroes,
                "message_inboxes": self.message_inboxes,
                "doors": self.doors,
                "traps": self.traps,
                "chests": self.chests,
                "monsters": self.monsters,
                "active_agent": self.active_agent,
                "turn_order": self.turn_order,
                "turn_cursor": self.turn_cursor,
                "reward_last": self.reward_last,
                "total_reward": self.total_reward,
                "done": self.done,
                "success": self.success,
                "terminal_reason": self.terminal_reason,
                "achievements": self.achievements,
                "event_log": self.event_log,
            },
        })
    }

    pub fn restore_from_checkpoint_value(value: Value) -> Result<Self, String> {
        if value.get("schema").and_then(Value::as_str)
            != Some("gamebench.dungeongrid.checkpoint.v1")
        {
            return Err(
                "checkpoint schema must be gamebench.dungeongrid.checkpoint.v1".to_string(),
            );
        }
        let scenario: Scenario = serde_json::from_value(
            value
                .get("scenario")
                .cloned()
                .ok_or_else(|| "checkpoint missing scenario".to_string())?,
        )
        .map_err(|err| format!("invalid DungeonGrid checkpoint scenario: {err}"))?;
        let mut session = Self::reset(scenario)?;
        let dynamic = value
            .get("dynamic")
            .ok_or_else(|| "checkpoint missing dynamic state".to_string())?;
        session.step_index = value
            .get("step_index")
            .and_then(Value::as_u64)
            .ok_or_else(|| "checkpoint missing step_index".to_string())?
            as u32;
        session.turn_index = value
            .get("turn_index")
            .and_then(Value::as_u64)
            .ok_or_else(|| "checkpoint missing turn_index".to_string())?
            as u32;
        session.heroes = restore_field(dynamic, "heroes")?;
        session.message_inboxes = dynamic
            .get("message_inboxes")
            .cloned()
            .map(serde_json::from_value)
            .transpose()
            .map_err(|err| format!("invalid checkpoint field message_inboxes: {err}"))?
            .unwrap_or_else(|| {
                session
                    .heroes
                    .keys()
                    .cloned()
                    .map(|agent_id| (agent_id, Vec::new()))
                    .collect()
            });
        session.doors = restore_field(dynamic, "doors")?;
        session.traps = restore_field(dynamic, "traps")?;
        session.chests = restore_field(dynamic, "chests")?;
        session.monsters = restore_field(dynamic, "monsters")?;
        session.active_agent = restore_field(dynamic, "active_agent")?;
        session.turn_order = restore_field(dynamic, "turn_order")?;
        session.turn_cursor = restore_field(dynamic, "turn_cursor")?;
        session.reward_last = restore_field(dynamic, "reward_last")?;
        session.total_reward = restore_field(dynamic, "total_reward")?;
        session.done = restore_field(dynamic, "done")?;
        session.success = restore_field(dynamic, "success")?;
        session.terminal_reason = restore_field(dynamic, "terminal_reason")?;
        session.achievements = restore_field(dynamic, "achievements")?;
        session.event_log = restore_field(dynamic, "event_log")?;
        session.append_event(
            "checkpoint_restored",
            "info",
            format!("CheckpointRestored(step={})", session.step_index),
            None,
            None,
            json!({"step_index": session.step_index, "turn_index": session.turn_index}),
        );
        Ok(session)
    }

    pub fn restore_from_checkpoint_str(text: &str) -> Result<Self, String> {
        let value: Value = serde_json::from_str(text)
            .map_err(|err| format!("invalid DungeonGrid checkpoint JSON: {err}"))?;
        Self::restore_from_checkpoint_value(value)
    }

    fn apply_move(&mut self, direction: Direction, action_json: Value) {
        let agent_id = self.active_agent.clone();
        let current = self.heroes[&agent_id].pos;
        let next = current.step(direction);
        if !self.is_passable(next) {
            self.reject(
                action_json,
                "blocked_move",
                json!({"from": current, "to": next}),
            );
            return;
        }
        let occupied = self
            .heroes
            .values()
            .any(|hero| hero.agent_id != agent_id && hero.pos == next);
        if occupied {
            self.reject(
                action_json,
                "hero_occupied",
                json!({"from": current, "to": next}),
            );
            return;
        }
        if let Some(hero) = self.heroes.get_mut(&agent_id) {
            hero.pos = next;
            hero.guarded = false;
        }
        self.reward_last += 0.05;
        self.append_event(
            "move_applied",
            "info",
            format!("MoveApplied({},{:?})", agent_id, direction),
            Some(action_json),
            None,
            json!({"agent_id": agent_id, "from": current, "to": next}),
        );
        self.unlock("movement.first_step");
    }

    fn apply_open_door(&mut self, target: &str, action_json: Value) {
        let agent_pos = self.heroes[&self.active_agent].pos;
        let Some(door) = self.doors.get(target).cloned() else {
            self.reject(action_json, "unknown_door", json!({"target": target}));
            return;
        };
        if agent_pos.manhattan(door.pos) > 1 {
            self.reject(
                action_json,
                "door_not_adjacent",
                json!({"target": target, "door": door}),
            );
            return;
        }
        if door.secret && !door.discovered {
            self.reject(action_json, "secret_door_hidden", json!({"target": target}));
            return;
        }
        if let Some(door) = self.doors.get_mut(target) {
            door.open = true;
        }
        let door = self.doors.get(target).cloned();
        self.reward_last += 0.3;
        self.append_event(
            "door_opened",
            "info",
            format!("DoorOpened({target})"),
            Some(action_json),
            None,
            json!({"door": door}),
        );
        self.unlock("routing.opened_door");
    }

    fn apply_attack_melee(&mut self, target: &str, action_json: Value) {
        let agent_id = self.active_agent.clone();
        let agent_pos = self.heroes[&agent_id].pos;
        let Some(monster) = self.monsters.get(target).cloned() else {
            self.reject(action_json, "unknown_monster", json!({"target": target}));
            return;
        };
        if monster.hp <= 0 {
            self.reject(
                action_json,
                "monster_already_defeated",
                json!({"target": target}),
            );
            return;
        }
        if agent_pos.manhattan(monster.pos) > 1 {
            self.reject(
                action_json,
                "monster_not_adjacent",
                json!({"target": target, "monster": monster}),
            );
            return;
        }
        let base_damage = hero_attack(&self.heroes[&agent_id].role);
        let guard = if monster.statuses.contains("counterplay_revealed") {
            0
        } else {
            monster.guard
        };
        let damage = (base_damage - guard).max(1);
        let defeated = if let Some(monster) = self.monsters.get_mut(target) {
            monster.awake = true;
            monster.hp = (monster.hp - damage).max(0);
            monster.hp == 0
        } else {
            false
        };
        self.reward_last += if defeated { 2.0 } else { 0.5 };
        self.append_event(
            "melee_attack",
            "info",
            format!("MeleeAttack({agent_id}->{target},damage={damage})"),
            Some(action_json),
            None,
            json!({
                "agent_id": agent_id,
                "target": target,
                "damage": damage,
                "defeated": defeated,
            }),
        );
        self.unlock("combat.first_hit");
        if defeated {
            self.append_event(
                "monster_defeated",
                "info",
                format!("MonsterDefeated({target})"),
                None,
                None,
                json!({"target": target}),
            );
            self.unlock("combat.monster_defeated");
        }
    }

    fn apply_cast(&mut self, target: &str, payload: &SpellPayload, action_json: Value) {
        let spell = payload.spell.as_str();
        if !self.heroes[&self.active_agent]
            .inventory
            .iter()
            .any(|item| item == spell)
        {
            self.reject(
                action_json,
                "spell_not_available",
                json!({"spell": spell, "target": target}),
            );
            return;
        }
        match spell {
            "spark_lance" => self.cast_spark_lance(target, action_json),
            "reveal_glyph" => self.cast_reveal_glyph(target, action_json),
            "ward_circle" => self.cast_ward_circle(target, action_json),
            _ => self.reject(
                action_json,
                "unknown_spell",
                json!({"spell": spell, "target": target}),
            ),
        }
    }

    fn cast_spark_lance(&mut self, target: &str, action_json: Value) {
        let agent_id = self.active_agent.clone();
        let agent_pos = self.heroes[&agent_id].pos;
        let Some(monster) = self.monsters.get(target).cloned() else {
            self.reject(action_json, "unknown_monster", json!({"target": target}));
            return;
        };
        if agent_pos.manhattan(monster.pos) > 4 {
            self.reject(
                action_json,
                "spell_target_out_of_range",
                json!({"target": target, "range": agent_pos.manhattan(monster.pos)}),
            );
            return;
        }
        let damage = 2;
        let defeated = if let Some(monster) = self.monsters.get_mut(target) {
            monster.awake = true;
            monster.hp = (monster.hp - damage).max(0);
            monster.hp == 0
        } else {
            false
        };
        self.reward_last += if defeated { 2.0 } else { 0.6 };
        self.append_event(
            "spell_cast",
            "info",
            format!("SpellCast({agent_id},spark_lance->{target},damage={damage})"),
            Some(action_json),
            None,
            json!({"spell": "spark_lance", "target": target, "damage": damage, "defeated": defeated}),
        );
        self.unlock("caster.spell_cast");
        if defeated {
            self.append_event(
                "monster_defeated",
                "info",
                format!("MonsterDefeated({target})"),
                None,
                None,
                json!({"target": target}),
            );
            self.unlock("combat.monster_defeated");
        }
    }

    fn cast_reveal_glyph(&mut self, target: &str, action_json: Value) {
        if target == "objective" || target == self.scenario.objective_item {
            let mut revealed = Vec::new();
            for trap in self.traps.values_mut() {
                if !trap.revealed {
                    trap.revealed = true;
                    revealed.push(trap.id.clone());
                }
            }
            self.reward_last += 0.7;
            self.append_event(
                "counterplay_revealed",
                "info",
                "CounterplayRevealed(objective)".to_string(),
                Some(action_json),
                None,
                json!({"target": target, "revealed_traps": revealed}),
            );
            self.unlock("support.counterplay_revealed");
            return;
        }
        let Some(monster) = self.monsters.get_mut(target) else {
            self.reject(
                action_json,
                "unknown_reveal_target",
                json!({"target": target}),
            );
            return;
        };
        monster.statuses.insert("counterplay_revealed".to_string());
        monster.guard = 0;
        self.reward_last += 0.8;
        self.append_event(
            "counterplay_revealed",
            "info",
            format!("CounterplayRevealed({target})"),
            Some(action_json),
            None,
            json!({"target": target, "effect": "monster_guard_removed"}),
        );
        self.unlock("support.counterplay_revealed");
    }

    fn cast_ward_circle(&mut self, target: &str, action_json: Value) {
        let target_agent = if target == "self" {
            self.active_agent.clone()
        } else {
            target.to_string()
        };
        if !self.heroes.contains_key(&target_agent) {
            self.reject(
                action_json,
                "unknown_hero",
                json!({"target": target, "resolved_target": target_agent}),
            );
            return;
        }
        if let Some(hero) = self.heroes.get_mut(&target_agent) {
            hero.guarded = true;
        }
        self.reward_last += 0.35;
        self.append_event(
            "spell_cast",
            "info",
            format!(
                "SpellCast({},ward_circle->{target_agent})",
                self.active_agent
            ),
            Some(action_json),
            None,
            json!({"spell": "ward_circle", "target": target_agent}),
        );
        self.unlock("coordination.guard_used");
    }

    fn apply_inspect_tile(&mut self, target: Pos, action_json: Value) {
        let terrain = self.terrain.get(&target).cloned();
        let door = self.doors.values().find(|door| door.pos == target).cloned();
        let trap = self.traps.values().find(|trap| trap.pos == target).cloned();
        self.reward_last += 0.1;
        self.append_event(
            "tile_inspected",
            "info",
            format!("TileInspected({}, {})", target.x, target.y),
            Some(action_json),
            None,
            json!({"target": target, "terrain": terrain, "door": door, "trap": trap}),
        );
    }

    fn apply_search_traps(&mut self, action_json: Value) {
        let agent_pos = self.heroes[&self.active_agent].pos;
        let mut revealed = Vec::new();
        for trap in self.traps.values_mut() {
            if agent_pos.manhattan(trap.pos) <= 2 && !trap.revealed {
                trap.revealed = true;
                revealed.push(trap.id.clone());
            }
        }
        if revealed.is_empty() {
            self.reward_last += 0.02;
        } else {
            self.reward_last += 0.4;
            self.unlock("support.revealed_trap");
        }
        self.append_event(
            "traps_searched",
            "info",
            format!("TrapsSearched({})", revealed.len()),
            Some(action_json),
            None,
            json!({"revealed": revealed}),
        );
    }

    fn apply_interact(&mut self, target: &str, action_json: Value) {
        if target == "objective" || target == self.scenario.objective_item {
            self.interact_objective(action_json);
            return;
        }
        if target == "escape" {
            self.interact_escape(action_json);
            return;
        }
        if self.chests.contains_key(target) {
            self.interact_chest(target, action_json);
            return;
        }
        self.reject(
            action_json,
            "unknown_interaction_target",
            json!({"target": target}),
        );
    }

    fn interact_objective(&mut self, action_json: Value) {
        let agent_id = self.active_agent.clone();
        let objective = self.objective_state();
        let objective_pos = objective.pos;
        if self.heroes[&agent_id].pos.manhattan(objective_pos) > 1 {
            self.reject(
                action_json,
                "objective_not_adjacent",
                json!({"objective": objective}),
            );
            return;
        }
        if self
            .heroes
            .values()
            .any(|hero| hero.inventory.contains(&self.scenario.objective_item))
        {
            self.reject(action_json, "objective_already_taken", json!({}));
            return;
        }
        if let Some(hero) = self.heroes.get_mut(&agent_id) {
            hero.inventory.push(self.scenario.objective_item.clone());
        }
        self.reward_last += 3.0;
        self.append_event(
            "objective_taken",
            "info",
            format!(
                "ObjectiveTaken({},{})",
                agent_id, self.scenario.objective_item
            ),
            Some(action_json),
            None,
            json!({"agent_id": agent_id, "item_id": self.scenario.objective_item}),
        );
        self.unlock("objective.secured");
    }

    fn interact_escape(&mut self, action_json: Value) {
        let agent_id = self.active_agent.clone();
        let escape = self.escape_tile();
        let hero = &self.heroes[&agent_id];
        if hero.pos != escape {
            self.reject(
                action_json,
                "not_on_escape_tile",
                json!({"escape_tile": escape}),
            );
            return;
        }
        if !hero.inventory.contains(&self.scenario.objective_item) {
            self.reject(
                action_json,
                "missing_objective_item",
                json!({"agent_id": agent_id}),
            );
            return;
        }
        self.reward_last += 5.0;
        self.done = true;
        self.success = true;
        self.terminal_reason = Some("escaped_with_objective".to_string());
        self.append_event(
            "objective_escaped",
            "info",
            format!("ObjectiveEscaped({agent_id})"),
            Some(action_json),
            None,
            json!({"agent_id": agent_id}),
        );
        self.unlock("objective.extracted");
        self.append_event(
            "terminal",
            "info",
            "Terminal(success)".to_string(),
            None,
            None,
            json!({"reason": "escaped_with_objective"}),
        );
    }

    fn interact_chest(&mut self, target: &str, action_json: Value) {
        let agent_id = self.active_agent.clone();
        let agent_pos = self.heroes[&agent_id].pos;
        let Some(chest) = self.chests.get_mut(target) else {
            self.reject(action_json, "unknown_chest", json!({"target": target}));
            return;
        };
        if agent_pos.manhattan(chest.pos) > 1 {
            self.reject(action_json, "chest_not_adjacent", json!({"target": target}));
            return;
        }
        if chest.opened {
            self.reject(action_json, "chest_already_open", json!({"target": target}));
            return;
        }
        chest.opened = true;
        let contents = chest.contents.clone();
        if let Some(hero) = self.heroes.get_mut(&agent_id) {
            hero.inventory.extend(contents.clone());
        }
        self.reward_last += 0.8;
        self.append_event(
            "chest_opened",
            "info",
            format!("ChestOpened({target})"),
            Some(action_json),
            None,
            json!({"target": target, "contents": contents, "agent_id": agent_id}),
        );
        self.unlock("optional.opened_chest");
    }

    fn apply_message(&mut self, target: &str, payload: &MessagePayload, action_json: Value) {
        if !self.scenario.observation.communication_enabled {
            self.reject(
                action_json,
                "communication_disabled",
                json!({"target": target}),
            );
            return;
        }
        if payload.text.trim().is_empty() {
            self.reject(action_json, "empty_message", json!({"target": target}));
            return;
        }
        let sender = self.active_agent.clone();
        let recipients = if target == "party" {
            self.heroes
                .keys()
                .filter(|agent_id| *agent_id != &sender)
                .cloned()
                .collect::<Vec<_>>()
        } else if self.heroes.contains_key(target) {
            vec![target.to_string()]
        } else {
            self.reject(
                action_json,
                "unknown_message_target",
                json!({"target": target}),
            );
            return;
        };
        let delivered = DeliveredMessage {
            from: sender.clone(),
            target: target.to_string(),
            text: payload.text.trim().to_string(),
            step_index: self.step_index,
            turn_index: self.turn_index,
        };
        for recipient in &recipients {
            self.message_inboxes
                .entry(recipient.clone())
                .or_default()
                .push(delivered.clone());
        }
        if let Some(hero) = self.heroes.get_mut(&self.active_agent) {
            hero.messages_sent += 1;
        }
        self.reward_last += 0.15;
        self.append_event(
            "message_sent",
            "info",
            format!("MessageSent({}->{target})", self.active_agent),
            Some(action_json),
            None,
            json!({
                "from": sender,
                "target": target,
                "recipients": recipients,
                "text": delivered.text,
            }),
        );
        self.unlock("coordination.message_sent");
    }

    fn apply_use_item(&mut self, target: &str, action_json: Value) {
        let agent_id = self.active_agent.clone();
        if !remove_one_item(
            &mut self.heroes.get_mut(&agent_id).unwrap().inventory,
            target,
        ) {
            self.reject(action_json, "item_not_carried", json!({"item": target}));
            return;
        }
        let mut effect = "consumed";
        if matches!(target, "healing_draught" | "iron_ration") {
            let amount = if target == "healing_draught" { 3 } else { 1 };
            if let Some(hero) = self.heroes.get_mut(&agent_id) {
                hero.hp = (hero.hp + amount).min(hero.max_hp);
            }
            effect = "healed";
            self.reward_last += 0.25;
        } else {
            self.reward_last += 0.05;
        }
        self.append_event(
            "item_used",
            "info",
            format!("ItemUsed({agent_id},{target})"),
            Some(action_json),
            None,
            json!({"agent_id": agent_id, "item": target, "effect": effect}),
        );
        self.unlock("inventory.item_used");
    }

    fn apply_give_item(&mut self, target: &str, payload: &GiveItemPayload, action_json: Value) {
        let agent_id = self.active_agent.clone();
        if !self.heroes.contains_key(target) {
            self.reject(action_json, "unknown_hero", json!({"target": target}));
            return;
        }
        let giver_pos = self.heroes[&agent_id].pos;
        let receiver_pos = self.heroes[target].pos;
        if giver_pos.manhattan(receiver_pos) > 1 {
            self.reject(
                action_json,
                "hero_not_adjacent",
                json!({"target": target, "item": payload.item}),
            );
            return;
        }
        if !remove_one_item(
            &mut self.heroes.get_mut(&agent_id).unwrap().inventory,
            &payload.item,
        ) {
            self.reject(
                action_json,
                "item_not_carried",
                json!({"target": target, "item": payload.item}),
            );
            return;
        }
        if let Some(receiver) = self.heroes.get_mut(target) {
            receiver.inventory.push(payload.item.clone());
        }
        self.reward_last += 0.2;
        self.append_event(
            "item_given",
            "info",
            format!("ItemGiven({agent_id}->{target},{})", payload.item),
            Some(action_json),
            None,
            json!({"from": agent_id, "target": target, "item": payload.item}),
        );
        self.unlock("coordination.item_handoff");
    }

    fn apply_guard(&mut self, action_json: Value) {
        if let Some(hero) = self.heroes.get_mut(&self.active_agent) {
            hero.guarded = true;
        }
        self.reward_last += 0.05;
        self.append_event(
            "guarded",
            "info",
            format!("Guarded({})", self.active_agent),
            Some(action_json),
            None,
            json!({"agent_id": self.active_agent}),
        );
        self.unlock("coordination.guard_used");
    }

    fn advance_turn(&mut self) {
        self.turn_cursor = (self.turn_cursor + 1) % self.turn_order.len();
        if self.turn_cursor == 0 {
            self.turn_index += 1;
        }
        self.active_agent = self.turn_order[self.turn_cursor].clone();
        if let Some(hero) = self.heroes.get_mut(&self.active_agent) {
            hero.ap = hero.max_ap;
        }
        self.append_event(
            "turn_started",
            "info",
            format!("TurnStarted({})", self.active_agent),
            None,
            None,
            json!({"active_agent": self.active_agent, "turn_index": self.turn_index}),
        );
    }

    fn check_trap(&mut self) {
        let agent_id = self.active_agent.clone();
        let pos = self.heroes[&agent_id].pos;
        let trap_id = self
            .traps
            .values()
            .find(|trap| trap.pos == pos && trap.armed)
            .map(|trap| trap.id.clone());
        let Some(trap_id) = trap_id else {
            return;
        };
        let damage = self.traps[&trap_id].damage;
        if let Some(trap) = self.traps.get_mut(&trap_id) {
            trap.revealed = true;
            trap.armed = false;
        }
        if let Some(hero) = self.heroes.get_mut(&agent_id) {
            hero.hp = (hero.hp - damage).max(0);
        }
        self.append_event(
            "trap_triggered",
            "warning",
            format!("TrapTriggered({trap_id},{agent_id})"),
            None,
            None,
            json!({"trap_id": trap_id, "agent_id": agent_id, "damage": damage}),
        );
        self.reward_last -= 0.2;
    }

    fn check_terminal(&mut self) {
        if self.heroes.values().all(|hero| hero.hp <= 0) {
            self.done = true;
            self.success = false;
            self.terminal_reason = Some("party_defeated".to_string());
            self.append_event(
                "terminal",
                "info",
                "Terminal(party_defeated)".to_string(),
                None,
                None,
                json!({"reason": "party_defeated"}),
            );
        }
    }

    fn is_passable(&self, pos: Pos) -> bool {
        if !matches!(
            self.terrain.get(&pos),
            Some(Terrain::Floor | Terrain::Escape | Terrain::Objective)
        ) {
            return false;
        }
        if self
            .doors
            .values()
            .any(|door| door.pos == pos && (!door.open || (door.secret && !door.discovered)))
        {
            return false;
        }
        if self
            .monsters
            .values()
            .any(|monster| monster.pos == pos && monster.hp > 0)
        {
            return false;
        }
        true
    }

    fn objective_state(&self) -> ObjectiveState {
        let holder = self.heroes.values().find_map(|hero| {
            if hero.inventory.contains(&self.scenario.objective_item) {
                Some(hero.agent_id.clone())
            } else {
                None
            }
        });
        let pos = self
            .terrain
            .iter()
            .find_map(|(pos, terrain)| {
                if terrain == &Terrain::Objective {
                    Some(*pos)
                } else {
                    None
                }
            })
            .unwrap_or(Pos { x: 0, y: 0 });
        ObjectiveState {
            item_id: self.scenario.objective_item.clone(),
            pos,
            holder: holder.clone(),
            escape_tile: self.escape_tile(),
            secured: holder.is_some(),
        }
    }

    fn escape_tile(&self) -> Pos {
        self.terrain
            .iter()
            .find_map(|(pos, terrain)| {
                if terrain == &Terrain::Escape {
                    Some(*pos)
                } else {
                    None
                }
            })
            .unwrap_or(Pos { x: 0, y: 0 })
    }

    fn legal_actions(&self) -> Value {
        let hero = &self.heroes[&self.active_agent];
        let adjacent_doors = self
            .doors
            .values()
            .filter(|door| hero.pos.manhattan(door.pos) <= 1 && !door.open)
            .map(|door| door.id.clone())
            .collect::<Vec<_>>();
        let adjacent_chests = self
            .chests
            .values()
            .filter(|chest| hero.pos.manhattan(chest.pos) <= 1 && !chest.opened)
            .map(|chest| chest.id.clone())
            .collect::<Vec<_>>();
        let adjacent_monsters = self
            .monsters
            .values()
            .filter(|monster| hero.pos.manhattan(monster.pos) <= 1 && monster.hp > 0)
            .map(|monster| monster.id.clone())
            .collect::<Vec<_>>();
        let ranged_monsters = self
            .monsters
            .values()
            .filter(|monster| {
                hero.pos.manhattan(monster.pos) <= 4
                    && monster.hp > 0
                    && self.position_visible_to(Some(&self.active_agent), monster.pos)
            })
            .map(|monster| monster.id.clone())
            .collect::<Vec<_>>();
        let adjacent_heroes = self
            .heroes
            .values()
            .filter(|other| other.agent_id != hero.agent_id && hero.pos.manhattan(other.pos) <= 1)
            .map(|other| other.agent_id.clone())
            .collect::<Vec<_>>();
        json!({
            "agent_id": self.active_agent,
            "ap": hero.ap,
            "base": self.base_actions(),
            "directions": ["north", "south", "west", "east"],
            "adjacent_doors": adjacent_doors,
            "adjacent_chests": adjacent_chests,
            "adjacent_monsters": adjacent_monsters,
            "ranged_monsters": ranged_monsters,
            "adjacent_heroes": adjacent_heroes,
            "carried_items": hero.inventory,
            "spells": hero.inventory.iter().filter(|item| matches!(item.as_str(), "spark_lance" | "reveal_glyph" | "ward_circle")).cloned().collect::<Vec<_>>(),
            "can_interact_objective": hero.pos.manhattan(self.objective_state().pos) <= 1,
            "can_escape": hero.pos == self.escape_tile()
                && hero.inventory.contains(&self.scenario.objective_item),
        })
    }

    fn coordination_state(&self) -> Value {
        let message_count: u32 = self.heroes.values().map(|hero| hero.messages_sent).sum();
        let guarded_agents = self
            .heroes
            .values()
            .filter(|hero| hero.guarded)
            .map(|hero| hero.agent_id.clone())
            .collect::<Vec<_>>();
        json!({
            "message_count": message_count,
            "guarded_agents": guarded_agents,
            "objective_holder": self.objective_state().holder,
            "active_role": self.heroes[&self.active_agent].role,
            "axis": self.scenario.metadata.get("marl_axis"),
            "skills": self.scenario.metadata.get("coordination_skills"),
        })
    }

    fn base_actions(&self) -> Vec<&'static str> {
        let mut actions = vec![
            "move",
            "inspect_tile",
            "search_traps",
            "guard",
            "use_item",
            "give_item",
            "end_turn",
        ];
        if self.scenario.observation.communication_enabled {
            actions.insert(3, "message");
        }
        actions
    }

    fn render_ascii(&self) -> String {
        self.render_ascii_for(None)
    }

    fn render_ascii_for(&self, viewer: Option<&str>) -> String {
        let mut rows = vec![vec![' '; self.width as usize]; self.height as usize];
        for (pos, terrain) in &self.terrain {
            if !self.position_visible_to(viewer, *pos) {
                rows[pos.y as usize][pos.x as usize] = '?';
                continue;
            }
            rows[pos.y as usize][pos.x as usize] = match terrain {
                Terrain::Wall => '#',
                Terrain::Floor => '.',
                Terrain::Escape => 'E',
                Terrain::Objective => 'I',
            };
        }
        for door in self.doors.values() {
            if !self.position_visible_to(viewer, door.pos) {
                continue;
            }
            rows[door.pos.y as usize][door.pos.x as usize] = if door.open { '/' } else { 'D' };
        }
        for trap in self.traps.values() {
            if !self.position_visible_to(viewer, trap.pos) {
                continue;
            }
            rows[trap.pos.y as usize][trap.pos.x as usize] = if trap.revealed { '^' } else { '.' };
        }
        for chest in self.chests.values() {
            if !self.position_visible_to(viewer, chest.pos) {
                continue;
            }
            rows[chest.pos.y as usize][chest.pos.x as usize] = if chest.opened { 'c' } else { 'C' };
        }
        for monster in self.monsters.values() {
            if monster.hp > 0 && self.position_visible_to(viewer, monster.pos) {
                rows[monster.pos.y as usize][monster.pos.x as usize] = 'R';
            }
        }
        for hero in self.heroes.values() {
            if self.position_visible_to(viewer, hero.pos) {
                let glyph = hero
                    .agent_id
                    .strip_prefix("agent_")
                    .and_then(|suffix| suffix.chars().next())
                    .unwrap_or('H');
                rows[hero.pos.y as usize][hero.pos.x as usize] = glyph;
            }
        }
        rows.into_iter()
            .map(|row| row.into_iter().collect::<String>())
            .collect::<Vec<_>>()
            .join("\n")
    }

    fn position_visible_to(&self, viewer: Option<&str>, pos: Pos) -> bool {
        let Some(agent_id) = viewer else {
            return true;
        };
        if self.scenario.observation.mode == ObservationMode::Global {
            return true;
        }
        self.heroes.get(agent_id).is_some_and(|hero| {
            hero.pos.manhattan(pos) <= self.scenario.observation.visibility_radius
        })
    }

    fn transition_snapshot(&self) -> Value {
        let hero_positions = self
            .heroes
            .iter()
            .map(|(agent_id, hero)| {
                json!({"agent_id": agent_id, "pos": hero.pos, "hp": hero.hp, "ap": hero.ap})
            })
            .collect::<Vec<_>>();
        let door_states = self
            .doors
            .iter()
            .map(|(door_id, door)| json!({"door_id": door_id, "open": door.open}))
            .collect::<Vec<_>>();
        json!({
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "active_agent": self.active_agent,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "done": self.done,
            "success": self.success,
            "terminal_reason": self.terminal_reason,
            "heroes": hero_positions,
            "doors": door_states,
            "objective": self.objective_state(),
            "achievements": self.achievements,
        })
    }

    fn reject(&mut self, action_json: Value, reason: &str, payload: Value) {
        self.reward_last = 0.0;
        self.append_event(
            "action_rejected",
            "warning",
            format!("ActionRejected({reason})"),
            Some(action_json),
            None,
            json!({"reason": reason, "details": payload}),
        );
    }

    fn unlock(&mut self, achievement: &str) {
        if self.achievements.insert(achievement.to_string()) {
            self.append_event(
                "achievement_unlocked",
                "info",
                format!("AchievementUnlocked({achievement})"),
                None,
                None,
                json!({"achievement": achievement}),
            );
        }
    }

    fn append_event(
        &mut self,
        kind: &str,
        severity: &str,
        message: String,
        action: Option<Value>,
        transition: Option<Value>,
        payload: Value,
    ) {
        self.event_log.push(EventRecord {
            step_index: self.step_index,
            turn_index: self.turn_index,
            episode_id: self.episode_id.clone(),
            agent_id: self.active_agent.clone(),
            kind: kind.to_string(),
            severity: severity.to_string(),
            message,
            action,
            transition,
            payload,
        });
    }

    fn last_event(&self) -> &EventRecord {
        self.event_log
            .last()
            .expect("DungeonGridSession always has at least one event after reset")
    }

    fn step_result(&self, applied: bool, recent_events: Vec<EventRecord>) -> StepResult {
        let local_mode = self.scenario.observation.mode == ObservationMode::Local;
        StepResult {
            applied,
            observation: self.observation_for(&self.active_agent),
            reward: self.reward_last,
            done: self.done,
            info: json!({
                "success": self.success,
                "terminal_reason": self.terminal_reason,
                "active_agent": self.active_agent,
                "rich_state": if local_mode {
                    self.local_state_for(&self.active_agent)
                } else {
                    self.rich_state()
                },
                "recent_events": if local_mode { Vec::new() } else { recent_events },
            }),
        }
    }

    pub fn observation_for(&self, agent_id: &str) -> Value {
        let local_mode = self.scenario.observation.mode == ObservationMode::Local;
        let objective_holder = if local_mode {
            self.visible_objective_holder(agent_id)
        } else {
            self.objective_state().holder
        };
        json!({
            "agent_id": agent_id,
            "active_agent": self.active_agent,
            "round": self.turn_index,
            "phase": if self.done { "terminal" } else { "hero_turn" },
            "text": format!(
                "{} active in {}. Objective holder: {:?}. Total reward {:.2}.",
                self.active_agent,
                self.scenario.title,
                objective_holder,
                self.total_reward
            ),
            "observation_mode": self.scenario.observation.mode,
            "visibility_radius": if local_mode {
                Some(self.scenario.observation.visibility_radius)
            } else {
                None
            },
            "communication_enabled": self.scenario.observation.communication_enabled,
            "visible_map": self.render_ascii_for(local_mode.then_some(agent_id)),
            "inbox": self.message_inboxes.get(agent_id).cloned().unwrap_or_default(),
            "symbolic": if local_mode {
                self.local_state_for(agent_id)
            } else {
                self.rich_state()
            },
        })
    }

    fn visible_objective_holder(&self, agent_id: &str) -> Option<String> {
        let holder = self.objective_state().holder?;
        if holder == agent_id {
            return Some(holder);
        }
        let pos = self.heroes.get(&holder)?.pos;
        self.position_visible_to(Some(agent_id), pos)
            .then_some(holder)
    }

    fn local_state_for(&self, agent_id: &str) -> Value {
        let visible_terrain = self
            .terrain
            .iter()
            .filter(|(pos, _)| self.position_visible_to(Some(agent_id), **pos))
            .map(|(pos, terrain)| json!({"x": pos.x, "y": pos.y, "terrain": terrain}))
            .collect::<Vec<_>>();
        let visible_heroes = self
            .heroes
            .iter()
            .filter(|(other_id, hero)| {
                *other_id == agent_id || self.position_visible_to(Some(agent_id), hero.pos)
            })
            .map(|(other_id, hero)| (other_id.clone(), hero.clone()))
            .collect::<BTreeMap<_, _>>();
        let visible_doors = self
            .doors
            .iter()
            .filter(|(_, door)| self.position_visible_to(Some(agent_id), door.pos))
            .map(|(id, door)| (id.clone(), door.clone()))
            .collect::<BTreeMap<_, _>>();
        let visible_traps = self
            .traps
            .iter()
            .filter(|(_, trap)| trap.revealed && self.position_visible_to(Some(agent_id), trap.pos))
            .map(|(id, trap)| (id.clone(), trap.clone()))
            .collect::<BTreeMap<_, _>>();
        let visible_chests = self
            .chests
            .iter()
            .filter(|(_, chest)| self.position_visible_to(Some(agent_id), chest.pos))
            .map(|(id, chest)| (id.clone(), chest.clone()))
            .collect::<BTreeMap<_, _>>();
        let visible_monsters = self
            .monsters
            .iter()
            .filter(|(_, monster)| {
                monster.hp > 0 && self.position_visible_to(Some(agent_id), monster.pos)
            })
            .map(|(id, monster)| (id.clone(), monster.clone()))
            .collect::<BTreeMap<_, _>>();
        let objective = self.objective_state();
        let objective_visible = self.position_visible_to(Some(agent_id), objective.pos)
            || objective.holder.as_deref() == Some(agent_id)
            || self.visible_objective_holder(agent_id).is_some();
        json!({
            "schema": "gamebench.dungeongrid.local_observation.v1",
            "episode_id": self.episode_id,
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "active_agent": self.active_agent,
            "self": self.heroes.get(agent_id),
            "map": {
                "width": self.width,
                "height": self.height,
                "ascii": self.render_ascii_for(Some(agent_id)),
                "visible_terrain": visible_terrain,
            },
            "visible_heroes": visible_heroes,
            "visible_doors": visible_doors,
            "visible_traps": visible_traps,
            "visible_chests": visible_chests,
            "visible_monsters": visible_monsters,
            "objective": if objective_visible { Some(objective) } else { None },
            "legal_actions": if agent_id == self.active_agent { Some(self.legal_actions()) } else { None },
            "inbox": self.message_inboxes.get(agent_id).cloned().unwrap_or_default(),
            "done": self.done,
            "success": self.success,
            "terminal_reason": self.terminal_reason,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepResult {
    pub applied: bool,
    pub observation: Value,
    pub reward: f64,
    pub done: bool,
    pub info: Value,
}

#[derive(Clone, Debug)]
struct ParsedMap {
    width: i32,
    height: i32,
    terrain: BTreeMap<Pos, Terrain>,
    doors: BTreeMap<String, DoorState>,
    traps: BTreeMap<String, TrapState>,
    chests: BTreeMap<String, ChestState>,
    monsters: BTreeMap<String, MonsterState>,
    entry: Pos,
}

impl ParsedMap {
    fn parse(scenario: &Scenario) -> Result<Self, String> {
        let lines = scenario.map_ascii.lines().collect::<Vec<_>>();
        if lines.is_empty() {
            return Err("map_ascii cannot be empty".to_string());
        }
        let width = lines[0].chars().count() as i32;
        if width == 0 {
            return Err("map width cannot be zero".to_string());
        }
        if lines
            .iter()
            .any(|line| line.chars().count() as i32 != width)
        {
            return Err("map_ascii must be rectangular".to_string());
        }
        let mut terrain = BTreeMap::new();
        let mut doors = BTreeMap::new();
        let mut traps = BTreeMap::new();
        let mut chests = BTreeMap::new();
        let mut monsters = BTreeMap::new();
        let mut entry = None;
        let mut door_count = 0;
        let mut trap_count = 0;
        let mut chest_count = 0;
        let mut monster_count = 0;
        for (y, line) in lines.iter().enumerate() {
            for (x, ch) in line.chars().enumerate() {
                let pos = Pos {
                    x: x as i32,
                    y: y as i32,
                };
                match ch {
                    '#' => {
                        terrain.insert(pos, Terrain::Wall);
                    }
                    'E' => {
                        terrain.insert(pos, Terrain::Escape);
                        entry = Some(pos);
                    }
                    'I' => {
                        terrain.insert(pos, Terrain::Objective);
                    }
                    'D' => {
                        terrain.insert(pos, Terrain::Floor);
                        door_count += 1;
                        let id = format!("door_{door_count}");
                        doors.insert(
                            id.clone(),
                            DoorState {
                                id,
                                pos,
                                open: false,
                                secret: false,
                                discovered: true,
                            },
                        );
                    }
                    'T' => {
                        terrain.insert(pos, Terrain::Floor);
                        trap_count += 1;
                        let id = format!("trap_{trap_count}");
                        traps.insert(
                            id.clone(),
                            TrapState {
                                id,
                                pos,
                                revealed: false,
                                armed: true,
                                damage: 1,
                            },
                        );
                    }
                    'C' => {
                        terrain.insert(pos, Terrain::Floor);
                        chest_count += 1;
                        let id = format!("chest_{chest_count}");
                        chests.insert(
                            id.clone(),
                            ChestState {
                                id,
                                pos,
                                opened: false,
                                contents: vec![
                                    "coin_cache".to_string(),
                                    "healing_draught".to_string(),
                                ],
                            },
                        );
                    }
                    'R' => {
                        terrain.insert(pos, Terrain::Floor);
                        monster_count += 1;
                        let id = format!("crypt_brute_{monster_count}");
                        monsters.insert(
                            id.clone(),
                            MonsterState {
                                id,
                                role: "crypt_brute".to_string(),
                                pos,
                                hp: 4,
                                max_hp: 4,
                                attack: 2,
                                guard: 1,
                                awake: false,
                                statuses: BTreeSet::new(),
                            },
                        );
                    }
                    '.' => {
                        terrain.insert(pos, Terrain::Floor);
                    }
                    other => {
                        return Err(format!("unsupported map glyph {other:?} at {},{}", x, y));
                    }
                }
            }
        }
        Ok(Self {
            width,
            height: lines.len() as i32,
            terrain,
            doors,
            traps,
            chests,
            monsters,
            entry: entry.ok_or_else(|| "map must include an E escape/entry tile".to_string())?,
        })
    }
}

fn starting_inventory(role: &str) -> Vec<String> {
    match role {
        "wizard" => vec![
            "ash_staff".to_string(),
            "spark_lance".to_string(),
            "reveal_glyph".to_string(),
            "ward_circle".to_string(),
        ],
        "barbarian" => vec!["broad_sword".to_string(), "iron_ration".to_string()],
        _ => Vec::new(),
    }
}

fn action_ap_cost(action: &DungeonGridAction) -> i32 {
    match action {
        DungeonGridAction::EndTurn => 0,
        DungeonGridAction::Move { .. }
        | DungeonGridAction::OpenDoor { .. }
        | DungeonGridAction::Interact { .. }
        | DungeonGridAction::Message { .. }
        | DungeonGridAction::UseItem { .. }
        | DungeonGridAction::GiveItem { .. }
        | DungeonGridAction::Guard => 1,
        DungeonGridAction::InspectTile { .. }
        | DungeonGridAction::SearchTraps
        | DungeonGridAction::AttackMelee { .. }
        | DungeonGridAction::Cast { .. } => 2,
    }
}

fn hero_attack(role: &str) -> i32 {
    match role {
        "barbarian" => 3,
        "wizard" => 1,
        _ => 2,
    }
}

fn remove_one_item(items: &mut Vec<String>, target: &str) -> bool {
    let Some(index) = items.iter().position(|item| item == target) else {
        return false;
    };
    items.remove(index);
    true
}

fn restore_field<T: DeserializeOwned>(dynamic: &Value, field: &str) -> Result<T, String> {
    serde_json::from_value(
        dynamic
            .get(field)
            .cloned()
            .ok_or_else(|| format!("checkpoint missing dynamic.{field}"))?,
    )
    .map_err(|err| format!("invalid checkpoint dynamic.{field}: {err}"))
}

fn episode_id(scenario: &Scenario) -> String {
    let mut hasher = Sha256::new();
    hasher.update(scenario.task_id.as_bytes());
    hasher.update(scenario.scenario_id.as_bytes());
    hasher.update(scenario.quest_id.as_bytes());
    hasher.update(scenario.seed.to_string().as_bytes());
    let digest = hasher.finalize();
    format!(
        "dg-{:x}",
        &digest[..8]
            .iter()
            .fold(0u64, |acc, byte| (acc << 8) | *byte as u64)
    )
}

fn terrain_cells_json(terrain: &BTreeMap<Pos, Terrain>) -> Vec<Value> {
    terrain
        .iter()
        .map(|(pos, tile)| json!({"x": pos.x, "y": pos.y, "terrain": tile}))
        .collect()
}

fn digest_json(value: &Value) -> Result<String, String> {
    let bytes = serde_json::to_vec(value)
        .map_err(|err| format!("failed to serialize DungeonGrid state digest input: {err}"))?;
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    Ok(format!("{:x}", hasher.finalize()))
}
