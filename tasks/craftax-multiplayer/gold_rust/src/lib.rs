use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const MAP_SIZE: usize = 48;
pub const NUM_LEVELS: usize = 9;
pub const REQUEST_DURATION: u8 = 10;
pub const RESOURCES: [&str; 9] = [
    "food", "drink", "wood", "stone", "iron", "coal", "diamond", "ruby", "sapphire",
];

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Player {
    pub agent_id: String,
    pub role: String,
    pub x: usize,
    pub y: usize,
    pub level: usize,
    pub health: i16,
    pub food: i16,
    pub drink: i16,
    pub energy: i16,
    pub alive: bool,
    pub inventory: BTreeMap<String, u16>,
    pub request_type: Option<String>,
    pub request_duration: u8,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Event {
    pub timestep: u64,
    pub kind: String,
    pub fields: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct State {
    pub seed: u64,
    pub timestep: u64,
    pub max_timesteps: u64,
    pub players: Vec<Player>,
    pub maps: Vec<Vec<Vec<String>>>,
    pub boss_health: i16,
    pub boss_progress: usize,
    pub achievements: BTreeSet<String>,
    pub trade_count: u64,
    pub terminated: bool,
    pub termination_reason: Option<String>,
    pub nev: Vec<Event>,
    pub legacy_nev: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepResult {
    pub rewards: BTreeMap<String, f64>,
    pub dones: BTreeMap<String, bool>,
    pub events: Vec<Event>,
}

#[derive(Clone, Debug)]
pub struct CraftaxCoopEnv {
    pub state: State,
}

impl CraftaxCoopEnv {
    pub fn reset(seed: u64, agent_count: usize, max_timesteps: u64) -> Self {
        assert!(agent_count >= 2);
        let roles = ["warrior", "forager", "miner"];
        let players = (0..agent_count)
            .map(|i| Player {
                agent_id: format!("agent_{i}"),
                role: roles[i % 3].into(),
                x: 3 + i,
                y: 3,
                level: 0,
                health: 9,
                food: 9,
                drink: 9,
                energy: 9,
                alive: true,
                inventory: RESOURCES.iter().map(|r| (r.to_string(), 0)).collect(),
                request_type: None,
                request_duration: 0,
            })
            .collect();
        let mut maps = vec![vec![vec!["grass".to_string(); MAP_SIZE]; MAP_SIZE]; NUM_LEVELS];
        for level in 0..NUM_LEVELS {
            let mut rng = (seed + 1)
                .wrapping_mul(1_000_003)
                .wrapping_add(level as u64 * 97);
            for i in 0..MAP_SIZE {
                maps[level][0][i] = "stone".into();
                maps[level][MAP_SIZE - 1][i] = "stone".into();
                maps[level][i][0] = "stone".into();
                maps[level][i][MAP_SIZE - 1] = "stone".into();
            }
            for y in 1..MAP_SIZE - 1 {
                for x in 1..MAP_SIZE - 1 {
                    rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    let roll = ((rng >> 32) % 1000) as usize;
                    maps[level][y][x] = if roll < 55 {
                        "water"
                    } else if roll < 180 {
                        [
                            "tree", "stone", "coal", "iron", "diamond", "ruby", "sapphire",
                        ][((rng as usize) + level / 2) % 7]
                    } else {
                        "grass"
                    }
                    .into();
                }
            }
            if level < NUM_LEVELS - 1 {
                maps[level][MAP_SIZE - 3][MAP_SIZE - 3] = "stairs_down".into();
            }
            if level > 0 {
                maps[level][2][2] = "stairs_up".into();
            }
        }
        maps[NUM_LEVELS - 1][MAP_SIZE / 2][MAP_SIZE / 2] = "boss".into();
        let mut env = Self {
            state: State {
                seed,
                timestep: 0,
                max_timesteps,
                players,
                maps,
                boss_health: 24,
                boss_progress: 0,
                achievements: BTreeSet::new(),
                trade_count: 0,
                terminated: false,
                termination_reason: None,
                nev: vec![],
                legacy_nev: vec![],
            },
        };
        env.event("game_started", [("task_id", "craftax-multiplayer")]);
        env
    }

    pub fn step(&mut self, actions: &BTreeMap<String, String>) -> Result<StepResult, String> {
        if self.state.terminated {
            return Err("step called after terminal state".into());
        }
        if actions.len() != self.state.players.len()
            || self
                .state
                .players
                .iter()
                .any(|p| !actions.contains_key(&p.agent_id))
        {
            return Err("joint action must contain every agent".into());
        }
        let start = self.state.nev.len();
        let before = self.state.achievements.len();
        for p in &mut self.state.players {
            p.request_duration = p.request_duration.saturating_sub(1);
            if p.request_duration == 0 {
                p.request_type = None;
            }
        }
        for idx in 0..self.state.players.len() {
            let action = &actions[&self.state.players[idx].agent_id];
            if let Some(resource) = action.strip_prefix("request_") {
                if RESOURCES.contains(&resource) {
                    self.state.players[idx].request_type = Some(resource.into());
                    self.state.players[idx].request_duration = REQUEST_DURATION;
                }
            }
        }
        for idx in 0..self.state.players.len() {
            let action = actions[&self.state.players[idx].agent_id].clone();
            if action.starts_with("give_") {
                self.give(idx, &action);
            } else if action == "cast_spell" && self.state.players[idx].role == "forager" {
                for p in &mut self.state.players {
                    p.health = (p.health + 2).min(9);
                }
            }
        }
        self.resolve_moves(actions);
        self.state.timestep += 1;
        for p in &mut self.state.players {
            if p.alive {
                p.energy = (p.energy - 1).max(0);
                if self.state.timestep % 25 == 0 {
                    p.food = (p.food - 1).max(0);
                    p.drink = (p.drink - 1).max(0);
                }
                if p.food == 0 || p.drink == 0 {
                    p.health -= 1;
                }
                if p.health <= 0 {
                    p.alive = false;
                    p.health = 0;
                }
            }
        }
        if !self.state.players.iter().any(|p| p.alive) {
            self.finish("death");
        } else if self.state.boss_progress >= NUM_LEVELS - 1 {
            self.finish("boss");
        } else if self.state.timestep >= self.state.max_timesteps {
            self.finish("timestep");
        }
        let reward = (self.state.achievements.len() - before) as f64
            + if self.state.termination_reason.as_deref() == Some("boss") {
                10.0
            } else {
                0.0
            };
        let rewards = self
            .state
            .players
            .iter()
            .map(|p| (p.agent_id.clone(), reward))
            .collect();
        let mut dones: BTreeMap<_, _> = self
            .state
            .players
            .iter()
            .map(|p| (p.agent_id.clone(), self.state.terminated))
            .collect();
        dones.insert("__all__".into(), self.state.terminated);
        Ok(StepResult {
            rewards,
            dones,
            events: self.state.nev[start..].to_vec(),
        })
    }

    fn resolve_moves(&mut self, actions: &BTreeMap<String, String>) {
        let delta = BTreeMap::from([
            ("left", (-1, 0)),
            ("right", (1, 0)),
            ("up", (0, -1)),
            ("down", (0, 1)),
        ]);
        let mut desired = vec![None; self.state.players.len()];
        for (i, p) in self.state.players.iter().enumerate() {
            if let Some(&(dx, dy)) = delta.get(actions[&p.agent_id].as_str()) {
                let nx = (p.x as isize + dx) as usize;
                let ny = (p.y as isize + dy) as usize;
                if !["stone", "water"].contains(&self.state.maps[p.level][ny][nx].as_str()) {
                    desired[i] = Some((nx, ny));
                }
            }
        }
        for i in 0..desired.len() {
            if let Some(pos) = desired[i] {
                let unique = desired.iter().filter(|v| **v == Some(pos)).count() == 1;
                let free = !self
                    .state
                    .players
                    .iter()
                    .any(|p| p.level == self.state.players[i].level && (p.x, p.y) == pos);
                if unique && free {
                    self.state.players[i].x = pos.0;
                    self.state.players[i].y = pos.1;
                }
            }
        }
    }
    fn give(&mut self, giver: usize, action: &str) {
        let Some(rest) = action.strip_prefix("give_") else {
            return;
        };
        let Some((resource, target_id)) = rest.split_once("_to_") else {
            return;
        };
        let Some(target) = self
            .state
            .players
            .iter()
            .position(|p| p.agent_id == target_id)
        else {
            return;
        };
        if giver == target
            || self.state.players[target].request_type.as_deref() != Some(resource)
            || self.state.players[target].request_duration == 0
        {
            return;
        }
        let stock = *self.state.players[giver]
            .inventory
            .get(resource)
            .unwrap_or(&0);
        if stock == 0 {
            return;
        }
        *self.state.players[giver]
            .inventory
            .get_mut(resource)
            .unwrap() -= 1;
        *self.state.players[target]
            .inventory
            .get_mut(resource)
            .unwrap() += 1;
        self.state.players[target].request_type = None;
        self.state.players[target].request_duration = 0;
        self.state.trade_count += 1;
        self.state.achievements.insert("trade".into());
    }
    fn finish(&mut self, reason: &str) {
        self.state.terminated = true;
        self.state.termination_reason = Some(reason.into());
        self.event("game_ended", [("outcome", reason)]);
    }
    fn event<const N: usize>(&mut self, kind: &str, fields: [(&str, &str); N]) {
        let fields: BTreeMap<_, _> = fields
            .into_iter()
            .map(|(k, v)| (k.into(), v.into()))
            .collect();
        self.state.nev.push(Event {
            timestep: self.state.timestep,
            kind: kind.into(),
            fields,
        });
        self.state.legacy_nev.push(format!(
            "{}({})",
            kind.split('_')
                .map(|s| {
                    let mut c = s.chars();
                    c.next()
                        .map(|x| x.to_uppercase().collect::<String>() + c.as_str())
                        .unwrap_or_default()
                })
                .collect::<String>(),
            self.state
                .nev
                .last()
                .unwrap()
                .fields
                .values()
                .cloned()
                .collect::<Vec<_>>()
                .join(",")
        ));
    }
    pub fn checkpoint_json(&self) -> String {
        serde_json::to_string(&self.state).expect("state serializes")
    }
    pub fn restore_json(raw: &str) -> Result<Self, serde_json::Error> {
        Ok(Self {
            state: serde_json::from_str(raw)?,
        })
    }
}
