//! Independent Rust authority for the TowerMind semantic tower-defense task.
//!
//! This intentionally owns a compact discrete game loop instead of importing
//! Unity, ML-Agents, or the upstream implementation.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;

#[derive(Clone, Debug, Deserialize)]
struct Level {
    id: String,
    availability: String,
    #[serde(default)]
    progression_note: String,
    #[serde(default)]
    width: i64,
    #[serde(default)]
    height: i64,
    #[serde(default)]
    base_hp: i64,
    #[serde(default)]
    hero_start: Vec<i64>,
    #[serde(default)]
    road: Vec<Vec<i64>>,
    #[serde(default)]
    build_slots: HashMap<String, Vec<i64>>,
    #[serde(default)]
    fog_cells: Vec<Vec<i64>>,
    #[serde(default)]
    coin_spawns: Vec<CoinSpawn>,
    #[serde(default)]
    waves: Vec<Wave>,
}

#[derive(Clone, Debug, Deserialize)]
struct CoinSpawn {
    tick: i64,
    id: String,
    at: Vec<i64>,
    value: i64,
}

#[derive(Clone, Debug, Deserialize)]
struct Wave {
    id: String,
    kind: String,
    count: i64,
    hp: i64,
    spawn_tick: i64,
    spawn_every: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Friendly {
    id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    source: Option<String>,
    pos: Vec<i64>,
    hp: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Tower {
    id: String,
    kind: String,
    slot: String,
    pos: Vec<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Enemy {
    id: String,
    kind: String,
    hp: i64,
    path_index: usize,
    pos: Vec<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Coin {
    id: String,
    at: Vec<i64>,
    value: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct State {
    level: String,
    seed: i64,
    availability: String,
    tick: i64,
    base_hp: Option<i64>,
    gold: i64,
    hero: Option<Friendly>,
    knights: Vec<Friendly>,
    towers: Vec<Tower>,
    enemies: Vec<Enemy>,
    coins: Vec<Coin>,
    total_reward: f64,
    illegal_actions: i64,
    terminated: bool,
    termination_reason: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Event {
    step_index: i64,
    tick: i64,
    kind: String,
    transition: String,
    severity: String,
    message: String,
    payload: Value,
}

pub struct TowerMindEnv {
    level: Level,
    state: State,
    events: Vec<Event>,
}

impl TowerMindEnv {
    pub fn reset(level_id: &str, seed: i64, initial_gold: i64) -> Result<Self, String> {
        let level = load_level(level_id)?;
        let is_stub = level.availability == "stub";
        let state = State {
            level: level_id.to_string(),
            seed,
            availability: level.availability.clone(),
            tick: 0,
            base_hp: if is_stub { None } else { Some(level.base_hp) },
            gold: initial_gold,
            hero: if is_stub { None } else { Some(Friendly { id: "hero".into(), source: None, pos: level.hero_start.clone(), hp: 5 }) },
            knights: Vec::new(),
            towers: Vec::new(),
            enemies: Vec::new(),
            coins: Vec::new(),
            total_reward: 0.0,
            illegal_actions: 0,
            terminated: false,
            termination_reason: None,
        };
        let mut env = Self { level, state, events: Vec::new() };
        if is_stub {
            env.event("level_stub", "preview", format!("LevelStub({level_id})"), json!({"note": env.level.progression_note}));
        } else {
            env.event("state_transition", "reset", format!("Reset(level={level_id},seed={seed})"), json!({"level": level_id, "seed": seed}));
            env.spawn_due();
        }
        Ok(env)
    }

    pub fn step(&mut self, action: Value) -> Value {
        if self.state.availability == "stub" {
            self.illegal(action, "level_stub", "L3-L5 are declared progression stubs in v0");
            return self.transition_result();
        }
        if self.state.terminated {
            self.illegal(action, "terminal", "episode has already ended");
            return self.transition_result();
        }
        match action.get("kind").and_then(Value::as_str) {
            Some("build") => self.build(&action),
            Some("move") => self.move_friendly(&action),
            Some("collect") => self.collect(&action),
            Some("attack") => self.attack(&action),
            Some("wait") => self.event("action_applied", "wait", "Wait()", json!({"action": action})),
            _ => self.illegal(action, "unknown_action", "unknown action kind"),
        }
        self.advance_world();
        self.transition_result()
    }

    pub fn projection(&self) -> Value {
        json!({"state": self.state, "events": self.events, "observation": self.observation()})
    }

    pub fn checkpoint(&self) -> String {
        canonical_json(&json!({"version": 1, "state": self.state, "events": self.events}))
    }

    pub fn restore(checkpoint: &str) -> Result<Self, String> {
        let value: Value = serde_json::from_str(checkpoint).map_err(|error| error.to_string())?;
        if value.get("version").and_then(Value::as_i64) != Some(1) {
            return Err("unsupported checkpoint version".into());
        }
        let state: State = serde_json::from_value(value.get("state").cloned().ok_or("missing checkpoint state")?).map_err(|error| error.to_string())?;
        let events: Vec<Event> = serde_json::from_value(value.get("events").cloned().ok_or("missing checkpoint events")?).map_err(|error| error.to_string())?;
        Ok(Self { level: load_level(&state.level)?, state, events })
    }

    fn build(&mut self, action: &Value) {
        let tower_kind = action.get("tower").and_then(Value::as_str).unwrap_or("");
        let slot = action.get("target").and_then(Value::as_str).unwrap_or("");
        let (cost, _range, _damage) = match tower_rule(tower_kind) {
            Some(rule) => rule,
            None => {
                self.illegal(action.clone(), "unknown_tower", &format!("unknown tower {tower_kind}"));
                return;
            }
        };
        let position = match self.level.build_slots.get(slot) {
            Some(position) => position.clone(),
            None => {
                self.illegal(action.clone(), "unknown_slot", &format!("unknown build slot {slot}"));
                return;
            }
        };
        if self.state.towers.iter().any(|tower| tower.slot == slot) {
            self.illegal(action.clone(), "occupied_slot", &format!("build slot {slot} is occupied"));
            return;
        }
        if self.state.gold < cost {
            self.illegal(action.clone(), "insufficient_gold", &format!("{tower_kind} costs {cost} pickup gold"));
            return;
        }
        self.state.gold -= cost;
        let tower_id = format!("tower_{}", self.state.towers.len());
        self.state.towers.push(Tower { id: tower_id.clone(), kind: tower_kind.into(), slot: slot.into(), pos: position.clone() });
        self.event("tower_built", "build", format!("TowerBuilt({tower_kind},{slot})"), json!({"tower": tower_kind, "slot": slot, "gold": self.state.gold}));
        if tower_kind == "knight" {
            let knight_id = format!("knight_{}", self.state.knights.len());
            self.state.knights.push(Friendly { id: knight_id.clone(), source: Some(tower_id.clone()), pos: position.clone(), hp: 3 });
            self.event("knight_summoned", "summon", format!("KnightSummoned({knight_id})"), json!({"knight": knight_id, "source": tower_id, "at": position}));
        }
    }

    fn move_friendly(&mut self, action: &Value) {
        let actor_id = action.get("actor").and_then(Value::as_str).unwrap_or("");
        let target = value_position(action.get("target"));
        let position = match self.actor_position(actor_id) {
            Some(position) => position,
            None => {
                self.illegal(action.clone(), "unknown_actor", &format!("unknown friendly {actor_id}"));
                return;
            }
        };
        if self.in_fog(&position) {
            self.illegal(action.clone(), "friendly_disabled_by_fog", &format!("{actor_id} is disabled in fog"));
            return;
        }
        let target = match target {
            Some(target) if self.valid_cell(&target) => target,
            _ => {
                self.illegal(action.clone(), "out_of_bounds", "move target is outside the discrete map");
                return;
            }
        };
        if distance(&position, &target) != 1 {
            self.illegal(action.clone(), "non_adjacent_move", "friendly movement is one Manhattan cell per step");
            return;
        }
        self.set_actor_position(actor_id, target.clone());
        self.event("friendly_moved", "move", format!("FriendlyMoved({actor_id})"), json!({"actor": actor_id, "to": target}));
    }

    fn collect(&mut self, action: &Value) {
        let actor_id = action.get("actor").and_then(Value::as_str).unwrap_or("");
        let target = value_position(action.get("target"));
        let position = match self.actor_position(actor_id) {
            Some(position) => position,
            None => {
                self.illegal(action.clone(), "unknown_actor", &format!("unknown friendly {actor_id}"));
                return;
            }
        };
        if self.in_fog(&position) {
            self.illegal(action.clone(), "friendly_disabled_by_fog", &format!("{actor_id} is disabled in fog"));
            return;
        }
        let target = match target {
            Some(target) if position == target => target,
            _ => {
                self.illegal(action.clone(), "collect_not_at_target", "collect requires the friendly to stand on target");
                return;
            }
        };
        let index = match self.state.coins.iter().position(|coin| coin.at == target) {
            Some(index) => index,
            None => {
                self.illegal(action.clone(), "missing_coin", "no spawned coin is present at target");
                return;
            }
        };
        let coin = self.state.coins.remove(index);
        self.state.gold += coin.value;
        self.event("coin_collected", "collect", format!("CoinCollected({})", coin.id), json!({"coin": coin.id, "actor": actor_id, "value": coin.value, "gold": self.state.gold}));
    }

    fn attack(&mut self, action: &Value) {
        let actor_id = action.get("actor").and_then(Value::as_str).unwrap_or("");
        let target_id = action.get("target").and_then(Value::as_str).unwrap_or("");
        let position = match self.actor_position(actor_id) {
            Some(position) => position,
            None => {
                self.illegal(action.clone(), "unknown_actor", &format!("unknown friendly {actor_id}"));
                return;
            }
        };
        if self.in_fog(&position) {
            self.illegal(action.clone(), "friendly_disabled_by_fog", &format!("{actor_id} is disabled in fog"));
            return;
        }
        let enemy_position = match self.state.enemies.iter().find(|enemy| enemy.id == target_id) {
            Some(enemy) => enemy.pos.clone(),
            None => {
                self.illegal(action.clone(), "unknown_enemy", &format!("unknown enemy {target_id}"));
                return;
            }
        };
        if distance(&position, &enemy_position) > 1 {
            self.illegal(action.clone(), "out_of_range", "hero and knights attack adjacent enemies only");
            return;
        }
        let damage = if actor_id.starts_with("knight_") { 2 } else { 1 };
        self.damage_by_id(target_id, damage, actor_id, "friendly_attack");
    }

    fn advance_world(&mut self) {
        self.state.tick += 1;
        self.spawn_due();
        let path = self.level.road.clone();
        let mut index = 0;
        while index < self.state.enemies.len() {
            self.state.enemies[index].path_index += 1;
            if self.state.enemies[index].path_index >= path.len() - 1 {
                let enemy = self.state.enemies.remove(index);
                let base_hp = self.state.base_hp.unwrap_or_default() - 1;
                self.state.base_hp = Some(base_hp);
                self.state.total_reward -= 1.0;
                self.event("enemy_leaked", "leak", format!("EnemyLeaked({})", enemy.id), json!({"enemy": enemy.id, "base_hp": base_hp, "reward_delta": -1.0}));
            } else {
                self.state.enemies[index].pos = path[self.state.enemies[index].path_index].clone();
                index += 1;
            }
        }
        self.tower_phase();
        if self.state.base_hp.unwrap_or_default() <= 0 {
            self.state.terminated = true;
            self.state.termination_reason = Some("base_destroyed".into());
            self.event("terminal", "base_destroyed", "Terminal(base_destroyed)", json!({"base_hp": self.state.base_hp}));
        } else if self.waves_finished() && self.state.enemies.is_empty() {
            self.state.terminated = true;
            self.state.termination_reason = Some("waves_cleared".into());
            self.event("terminal", "waves_cleared", "Terminal(waves_cleared)", json!({"base_hp": self.state.base_hp}));
        }
    }

    fn spawn_due(&mut self) {
        let tick = self.state.tick;
        for spec in self.level.coin_spawns.clone() {
            if spec.tick == tick && !self.state.coins.iter().any(|coin| coin.id == spec.id) {
                self.state.coins.push(Coin { id: spec.id.clone(), at: spec.at.clone(), value: spec.value });
                self.event("coin_spawned", "spawn", format!("CoinSpawned({})", spec.id), json!({"coin": spec.id, "at": spec.at, "value": spec.value}));
            }
        }
        for wave in self.level.waves.clone() {
            let offset = tick - wave.spawn_tick;
            if offset < 0 || offset % wave.spawn_every != 0 {
                continue;
            }
            let ordinal = offset / wave.spawn_every;
            if ordinal >= wave.count {
                continue;
            }
            let enemy_id = format!("enemy_{}", self.spawn_sequence(&wave.id, ordinal));
            self.state.enemies.push(Enemy { id: enemy_id.clone(), kind: wave.kind.clone(), hp: wave.hp, path_index: 0, pos: self.level.road[0].clone() });
            self.event("enemy_spawned", "spawn", format!("EnemySpawned({enemy_id})"), json!({"enemy": enemy_id, "kind": wave.kind}));
        }
    }

    fn tower_phase(&mut self) {
        let towers = self.state.towers.clone();
        for tower in towers {
            if tower.kind == "knight" {
                continue;
            }
            if self.in_fog(&tower.pos) {
                self.event("friendly_disabled_by_fog", "tower_disabled", format!("TowerDisabledByFog({})", tower.id), json!({"tower": tower.id}));
                continue;
            }
            let range = tower_rule(&tower.kind).expect("known tower").1;
            let mut targets: Vec<&Enemy> = self.state.enemies.iter().filter(|enemy| distance(&tower.pos, &enemy.pos) <= range).collect();
            if targets.is_empty() {
                continue;
            }
            targets.sort_by(|left, right| right.path_index.cmp(&left.path_index).then_with(|| right.id.cmp(&left.id)));
            let first = targets[0].clone();
            if tower.kind == "archer" {
                self.damage_by_id(&first.id, 2, &tower.id, "archer_attack");
            } else {
                let ids: Vec<String> = self.state.enemies.iter().filter(|enemy| distance(&first.pos, &enemy.pos) <= 1).map(|enemy| enemy.id.clone()).collect();
                for enemy_id in ids {
                    self.damage_by_id(&enemy_id, 1, &tower.id, "magician_aoe");
                }
            }
        }
    }

    fn damage_by_id(&mut self, target_id: &str, damage: i64, source: &str, transition: &str) {
        let index = match self.state.enemies.iter().position(|enemy| enemy.id == target_id) {
            Some(index) => index,
            None => return,
        };
        self.state.enemies[index].hp -= damage;
        let hp = self.state.enemies[index].hp;
        self.event("enemy_damaged", transition, format!("EnemyDamaged({target_id},{damage})"), json!({"enemy": target_id, "damage": damage, "source": source, "hp": hp}));
        if hp <= 0 {
            self.state.enemies.remove(index);
            self.event("enemy_defeated", "defeat", format!("EnemyDefeated({target_id})"), json!({"enemy": target_id, "source": source, "gold_awarded": 0}));
        }
    }

    fn waves_finished(&self) -> bool {
        let latest = self.level.waves.iter().map(|wave| wave.spawn_tick + (wave.count - 1) * wave.spawn_every).max().unwrap_or(0);
        self.state.tick >= latest
    }

    fn spawn_sequence(&self, wave_id: &str, ordinal: i64) -> i64 {
        let mut sequence = 0;
        for wave in &self.level.waves {
            if wave.id == wave_id {
                return sequence + ordinal;
            }
            sequence += wave.count;
        }
        panic!("unknown wave {wave_id}")
    }

    fn observation(&self) -> Value {
        let friendlies: Vec<Value> = self.friendlies().iter().map(|friendly| self.friendly_view(friendly)).collect();
        let towers: Vec<Value> = self.state.towers.iter().map(|tower| self.tower_view(tower)).collect();
        let enemies: Vec<Value> = self.state.enemies.iter().map(|enemy| json!({"id": enemy.id, "kind": enemy.kind, "hp": enemy.hp, "pos": enemy.pos, "path_index": enemy.path_index})).collect();
        let structured = json!({
            "level": self.state.level,
            "availability": self.state.availability,
            "tick": self.state.tick,
            "base_hp": self.state.base_hp,
            "gold": self.state.gold,
            "friendlies": friendlies,
            "towers": towers,
            "enemies": enemies,
            "coins": self.state.coins,
            "build_slots": self.level.build_slots,
            "fog_cells": self.level.fog_cells,
            "illegal_actions": self.state.illegal_actions,
            "terminated": self.state.terminated,
            "termination_reason": self.state.termination_reason,
        });
        let text = canonical_json(&structured);
        json!({"structured": structured, "text": text})
    }

    fn friendlies(&self) -> Vec<&Friendly> {
        let mut all = Vec::new();
        if let Some(hero) = &self.state.hero {
            all.push(hero);
        }
        all.extend(self.state.knights.iter());
        all
    }

    fn friendly_view(&self, friendly: &Friendly) -> Value {
        let disabled = self.in_fog(&friendly.pos);
        json!({"id": friendly.id, "hp": friendly.hp, "pos": if disabled { Value::Null } else { json!(friendly.pos) }, "occluded": disabled, "disabled": disabled})
    }

    fn tower_view(&self, tower: &Tower) -> Value {
        let disabled = self.in_fog(&tower.pos);
        json!({"id": tower.id, "kind": tower.kind, "slot": tower.slot, "pos": if disabled { Value::Null } else { json!(tower.pos) }, "occluded": disabled, "disabled": disabled})
    }

    fn actor_position(&self, actor_id: &str) -> Option<Vec<i64>> {
        if actor_id == "hero" {
            return self.state.hero.as_ref().map(|hero| hero.pos.clone());
        }
        self.state.knights.iter().find(|knight| knight.id == actor_id).map(|knight| knight.pos.clone())
    }

    fn set_actor_position(&mut self, actor_id: &str, target: Vec<i64>) {
        if actor_id == "hero" {
            if let Some(hero) = &mut self.state.hero {
                hero.pos = target;
            }
            return;
        }
        if let Some(knight) = self.state.knights.iter_mut().find(|knight| knight.id == actor_id) {
            knight.pos = target;
        }
    }

    fn valid_cell(&self, position: &[i64]) -> bool {
        position.len() == 2 && position[0] >= 0 && position[1] >= 0 && position[0] < self.level.width && position[1] < self.level.height
    }

    fn in_fog(&self, position: &[i64]) -> bool {
        self.level.fog_cells.iter().any(|cell| cell == position)
    }

    fn illegal(&mut self, action: Value, code: &str, message: &str) {
        self.state.illegal_actions += 1;
        self.event_with_severity("illegal_action", "rejected", format!("IllegalAction({code})"), json!({"action": action, "code": code, "hallucination": true, "message": message}), "warning");
    }

    fn event(&mut self, kind: &str, transition: &str, message: impl Into<String>, payload: Value) {
        self.event_severity(kind, transition, message, payload, "info");
    }

    fn event_severity(&mut self, kind: &str, transition: &str, message: impl Into<String>, payload: Value, severity: &str) {
        self.events.push(Event { step_index: self.state.tick, tick: self.state.tick, kind: kind.into(), transition: transition.into(), severity: severity.into(), message: message.into(), payload });
    }

    fn event_with_severity(&mut self, kind: &str, transition: &str, message: impl Into<String>, payload: Value, severity: &str) {
        self.event_severity(kind, transition, message, payload, severity);
    }

    fn transition_result(&self) -> Value {
        json!({"observation": self.observation(), "reward": self.state.total_reward, "terminated": self.state.terminated, "info": {"illegal_actions": self.state.illegal_actions, "nev_cursor": self.events.len()}})
    }
}

fn tower_rule(kind: &str) -> Option<(i64, i64, i64)> {
    match kind {
        "archer" => Some((3, 3, 2)),
        "magician" => Some((4, 3, 1)),
        "knight" => Some((5, 0, 0)),
        _ => None,
    }
}

fn value_position(value: Option<&Value>) -> Option<Vec<i64>> {
    value?.as_array()?.iter().map(Value::as_i64).collect()
}

fn distance(left: &[i64], right: &[i64]) -> i64 {
    (left[0] - right[0]).abs() + (left[1] - right[1]).abs()
}

fn load_level(level_id: &str) -> Result<Level, String> {
    let source = match level_id {
        "L1" => include_str!("../../defaults/levels/l1.json"),
        "L2" => include_str!("../../defaults/levels/l2.json"),
        "L3" => include_str!("../../defaults/levels/l3_stub.json"),
        "L4" => include_str!("../../defaults/levels/l4_stub.json"),
        "L5" => include_str!("../../defaults/levels/l5_stub.json"),
        _ => return Err(format!("unknown TowerMind level {level_id:?}")),
    };
    serde_json::from_str(source).map_err(|error| error.to_string())
}

pub fn run_scenario(document: Value) -> Result<Value, String> {
    let id = document.get("id").and_then(Value::as_str).ok_or("scenario id missing")?.to_string();
    let level = document.get("level").and_then(Value::as_str).ok_or("scenario level missing")?;
    let seed = document.get("seed").and_then(Value::as_i64).unwrap_or(0);
    let initial_gold = document.get("initial_gold").and_then(Value::as_i64).unwrap_or(0);
    let mut env = TowerMindEnv::reset(level, seed, initial_gold)?;
    for action in document.get("actions").and_then(Value::as_array).cloned().unwrap_or_default() {
        if env.state.terminated {
            break;
        }
        env.step(action);
    }
    Ok(json!({"scenario": id, "projection": env.projection(), "checkpoint": env.checkpoint()}))
}

pub fn canonical_json(value: &Value) -> String {
    match value {
        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_) => serde_json::to_string(value).expect("serializable primitive"),
        Value::Array(items) => format!("[{}]", items.iter().map(canonical_json).collect::<Vec<_>>().join(",")),
        Value::Object(entries) => {
            let mut keys: Vec<&String> = entries.keys().collect();
            keys.sort();
            let parts = keys.into_iter().map(|key| format!("{}:{}", serde_json::to_string(key).expect("serializable key"), canonical_json(&entries[key]))).collect::<Vec<_>>();
            format!("{{{}}}", parts.join(","))
        }
    }
}
