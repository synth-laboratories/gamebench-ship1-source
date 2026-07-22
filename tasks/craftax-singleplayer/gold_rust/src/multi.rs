//! Shared-world Craftax MARL authority built on the native Rust gold engine.
//!
//! The underlying map, entities, projectile simulation, and timestep remain
//! singular. Each survivor has independently persisted positional and player
//! state; the active survivor is loaded into the gold engine for one action,
//! then captured back before the next survivor acts.

use anyhow::{bail, Result};
use serde_json::{json, Value};

use crate::CraftaxRustSession;

#[derive(Clone)]
struct Survivor {
    id: String,
    pos: (i64, i64),
    direction: (i64, i64),
    level: i64,
    inventory: Value,
    achievements: Value,
    private: Value,
}

impl Survivor {
    fn from_engine(id: String, engine: &CraftaxRustSession) -> Self {
        Self {
            id,
            pos: engine.world.player_pos,
            direction: engine.world.player_direction,
            level: engine.world.player_level,
            inventory: engine.world.inventory.clone(),
            achievements: engine.world.achievements.clone(),
            private: engine.private.clone(),
        }
    }

    fn load_into(&self, engine: &mut CraftaxRustSession) {
        engine.world.player_pos = self.pos;
        engine.world.player_direction = self.direction;
        engine.world.player_level = self.level;
        engine.world.inventory = self.inventory.clone();
        engine.world.achievements = self.achievements.clone();
        engine.private = self.private.clone();
    }

    fn capture(&mut self, engine: &CraftaxRustSession) {
        self.pos = engine.world.player_pos;
        self.direction = engine.world.player_direction;
        self.level = engine.world.player_level;
        self.inventory = engine.world.inventory.clone();
        self.achievements = engine.world.achievements.clone();
        self.private = engine.private.clone();
    }

    fn public_value(&self) -> Value {
        json!({
            "id": self.id,
            "pos": [self.pos.0, self.pos.1],
            "level": self.level,
            "inventory": self.inventory,
            "achievements": self.achievements,
            "alive": self.private.get("terminated").and_then(Value::as_bool).map(|done| !done).unwrap_or(true),
        })
    }
}

/// A real shared Craftax world with one active model-controlled survivor per action.
pub struct CraftaxMultiSession {
    engine: CraftaxRustSession,
    survivors: Vec<Survivor>,
    terminal_reason: Option<String>,
    total_reward: f64,
}

impl CraftaxMultiSession {
    pub fn reset_from_task(task: &Value, seed_override: Option<i64>, agent_count: usize) -> Result<Self> {
        if !(1..=4).contains(&agent_count) {
            bail!("Craftax multi-agent count must be within 1..=4, got {agent_count}");
        }
        let engine = CraftaxRustSession::reset_from_task(task, seed_override)?;
        let mut survivors = vec![Survivor::from_engine("agent_1".to_string(), &engine)];
        let spawns = spawn_positions(&engine, agent_count);
        for index in 1..agent_count {
            let mut survivor = Survivor::from_engine(format!("agent_{}", index + 1), &engine);
            survivor.pos = spawns[index];
            survivors.push(survivor);
        }
        Ok(Self { engine, survivors, terminal_reason: None, total_reward: 0.0 })
    }

    pub fn is_done(&self) -> bool {
        self.terminal_reason.is_some()
    }

    pub fn survivor_ids(&self) -> Vec<&str> {
        self.survivors.iter().map(|survivor| survivor.id.as_str()).collect()
    }

    pub fn step(&mut self, agent_id: &str, action: &Value) -> Result<()> {
        if self.is_done() {
            bail!("Craftax multi-agent episode is terminal: {}", self.terminal_reason.as_deref().unwrap_or("unknown"));
        }
        let index = self.survivor_index(agent_id)?;
        self.survivors[index].load_into(&mut self.engine);
        self.engine.step(action)?;
        self.total_reward += self.engine.private.get("reward_last").and_then(Value::as_f64).unwrap_or(0.0);
        self.survivors[index].capture(&self.engine);
        if self.engine.is_done() {
            self.terminal_reason = self.engine.private.get("done_reason").and_then(Value::as_str).map(str::to_string);
        }
        Ok(())
    }

    pub fn readout(&mut self, agent_id: &str) -> Result<Value> {
        let index = self.survivor_index(agent_id)?;
        self.survivors[index].load_into(&mut self.engine);
        let mut readout = self.engine.readout();
        let teammates: Vec<Value> = self.survivors.iter().filter(|survivor| survivor.id != agent_id).map(Survivor::public_value).collect();
        let mut shared_achievements: Vec<String> = self.survivors.iter().flat_map(|survivor| survivor.private.get("achievements").and_then(Value::as_array).into_iter().flatten()).filter_map(Value::as_str).map(str::to_string).collect();
        shared_achievements.sort();
        shared_achievements.dedup();
        let private = readout.get_mut("private").and_then(Value::as_object_mut);
        if let Some(private) = private {
            private.insert("terminated".to_string(), json!(self.is_done()));
            private.insert("truncated".to_string(), json!(self.terminal_reason.as_deref() == Some("max_steps")));
            private.insert("done_reason".to_string(), self.terminal_reason.clone().map(Value::String).unwrap_or(Value::Null));
            private.insert("total_reward".to_string(), json!(self.total_reward));
        }
        let object = readout.as_object_mut().expect("Craftax readout is an object");
        object.insert("env_family".to_string(), json!("craftax-multiplayer"));
        object.insert("active_agent".to_string(), json!(agent_id));
        object.insert("agent_count".to_string(), json!(self.survivors.len()));
        object.insert("teammates".to_string(), json!(teammates));
        object.insert("shared_achievements".to_string(), json!(shared_achievements));
        object.insert("shared_world".to_string(), json!({"timestep": self.engine.world.timestep, "grid_hash": self.engine.readout().get("grid_hash").cloned().unwrap_or(Value::Null)}));
        Ok(readout)
    }

    pub fn render_png(&mut self, agent_id: &str) -> Result<(u32, u32, Vec<Vec<(u8, u8, u8)>>)> {
        let index = self.survivor_index(agent_id)?;
        self.survivors[index].load_into(&mut self.engine);
        Ok(crate::render::render_rgb_frame_from_world(&self.engine.world, crate::DEFAULT_RENDER_TILE_SIZE, crate::RenderMode::Auto))
    }

    fn survivor_index(&self, agent_id: &str) -> Result<usize> {
        self.survivors.iter().position(|survivor| survivor.id == agent_id).ok_or_else(|| anyhow::anyhow!("unknown Craftax survivor: {agent_id}"))
    }
}

fn spawn_positions(engine: &CraftaxRustSession, agent_count: usize) -> Vec<(i64, i64)> {
    let base = engine.world.player_pos;
    let level = usize::try_from(engine.world.player_level).unwrap_or(0);
    let offsets = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)];
    let mut positions = Vec::with_capacity(agent_count);
    for (dx, dy) in offsets {
        let candidate = (base.0 + dx, base.1 + dy);
        let tile = if candidate.0 >= 0 && candidate.1 >= 0 && candidate.0 < engine.world.width && candidate.1 < engine.world.height {
            engine.world.maps[level][candidate.1 as usize][candidate.0 as usize].as_str()
        } else {
            "wall"
        };
        if is_spawnable(tile) && !positions.contains(&candidate) {
            positions.push(candidate);
            if positions.len() == agent_count { return positions; }
        }
    }
    while positions.len() < agent_count { positions.push(base); }
    positions
}

fn is_spawnable(tile: &str) -> bool {
    matches!(tile, "grass" | "path" | "sand" | "gravel" | "fire_grass" | "ice_grass")
}
