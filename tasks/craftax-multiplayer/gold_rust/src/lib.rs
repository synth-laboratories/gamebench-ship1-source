use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

mod achievement_map {
    use serde::{Deserialize, Deserializer, Serialize, Serializer};
    use std::collections::{BTreeMap, BTreeSet};

    pub fn serialize<S>(achievements: &BTreeSet<String>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        achievements
            .iter()
            .map(|achievement| (achievement.as_str(), true))
            .collect::<BTreeMap<_, _>>()
            .serialize(serializer)
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<BTreeSet<String>, D::Error>
    where
        D: Deserializer<'de>,
    {
        Ok(BTreeMap::<String, bool>::deserialize(deserializer)?
            .into_iter()
            .filter_map(|(achievement, earned)| earned.then_some(achievement))
            .collect())
    }
}

pub const MAP_SIZE: usize = 48;
pub const NUM_LEVELS: usize = 9;
pub const REQUEST_DURATION: u8 = 10;
pub const DAY_LENGTH: u64 = 300;
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
    pub mana: i16,
    pub alive: bool,
    pub inventory: BTreeMap<String, u16>,
    pub pickaxe: u8,
    pub sword: u8,
    pub armour: u8,
    pub arrows: u16,
    pub torches: u16,
    pub books: u16,
    pub saplings: u16,
    pub potions: BTreeMap<String, u16>,
    pub dexterity: u8,
    pub strength: u8,
    pub intelligence: u8,
    pub xp: u16,
    pub level_points: u8,
    pub sword_enchantment: Option<String>,
    pub armour_enchantment: Option<String>,
    pub bow_enchantment: Option<String>,
    pub sleeping: bool,
    pub facing: String,
    pub request_type: Option<String>,
    pub request_duration: u8,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Monster {
    pub id: String,
    pub kind: String,
    pub level: usize,
    pub x: usize,
    pub y: usize,
    pub health: i16,
    pub damage: i16,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Projectile {
    pub owner: String,
    pub level: usize,
    pub x: isize,
    pub y: isize,
    pub dx: isize,
    pub dy: isize,
    pub damage: i16,
    pub ttl: u8,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Plant {
    pub level: usize,
    pub x: usize,
    pub y: usize,
    pub age: u16,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Event {
    pub timestep: u64,
    pub kind: String,
    #[serde(flatten)]
    pub fields: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct State {
    pub seed: u64,
    pub timestep: u64,
    pub max_timesteps: u64,
    pub players: Vec<Player>,
    pub maps: Vec<Vec<Vec<String>>>,
    pub monsters: Vec<Monster>,
    pub projectiles: Vec<Projectile>,
    pub plants: Vec<Plant>,
    pub boss_health: i16,
    pub boss_progress: usize,
    pub boss_wave_timer: u16,
    pub light_level: f64,
    #[serde(with = "achievement_map")]
    pub achievements: BTreeSet<String>,
    pub trade_count: u64,
    pub terminated: bool,
    pub termination_reason: Option<String>,
    pub last_joint_event: Vec<Event>,
    pub nev: Vec<Event>,
    pub legacy_nev: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepResult {
    pub rewards: BTreeMap<String, f64>,
    pub dones: BTreeMap<String, bool>,
    pub events: Vec<Event>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Checkpoint {
    schema_version: String,
    state: State,
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
                mana: 9,
                alive: true,
                inventory: RESOURCES.iter().map(|r| (r.to_string(), 0)).collect(),
                pickaxe: 0,
                sword: 0,
                armour: 0,
                arrows: 0,
                torches: 0,
                books: 0,
                saplings: 0,
                potions: ["red", "green", "blue", "pink", "cyan", "yellow"]
                    .into_iter()
                    .map(|c| (c.into(), 0))
                    .collect(),
                dexterity: 0,
                strength: 0,
                intelligence: 0,
                xp: 0,
                level_points: 0,
                sword_enchantment: None,
                armour_enchantment: None,
                bow_enchantment: None,
                sleeping: false,
                facing: "down".into(),
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
                        if level < 6 {
                            "water"
                        } else if level == 6 {
                            "lava"
                        } else {
                            "ice_grass"
                        }
                    } else if roll < 180 {
                        [
                            "tree", "stone", "coal", "iron", "diamond", "ruby", "sapphire",
                        ][(((rng >> 16) as usize) + level / 2) % 7]
                    } else if roll < 190 {
                        "chest"
                    } else if roll < 200 && level == 0 {
                        "plant"
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
        for index in 0..agent_count {
            maps[0][3][3 + index] = "grass".into();
        }
        maps[0][5][5] = "fountain".into();
        let mut monsters = Vec::new();
        let kinds = [
            "cow",
            "bat",
            "zombie",
            "skeleton",
            "gnome",
            "orc",
            "troll",
            "fire_elemental",
            "ice_elemental",
            "necromancer_minion",
        ];
        let stats = [
            (3, 0),
            (2, 1),
            (5, 2),
            (4, 2),
            (5, 2),
            (7, 3),
            (10, 4),
            (8, 4),
            (8, 4),
            (10, 5),
        ];
        for level in 0..NUM_LEVELS - 1 {
            for index in 0..3 + level {
                let value = ((seed + 17)
                    .wrapping_mul(1_103_515_245)
                    .wrapping_add(level as u64 * 7919)
                    .wrapping_add(index as u64 * 104729))
                    & 0xffff_ffff;
                let (x, y) = (6 + (value as usize) % 36, 6 + ((value / 37) as usize) % 36);
                if ["grass", "path", "sand", "gravel"].contains(&maps[level][y][x].as_str()) {
                    let kind_index = (level + index % 2).min(kinds.len() - 1);
                    monsters.push(Monster {
                        id: format!("mob_{level}_{index}"),
                        kind: kinds[kind_index].into(),
                        level,
                        x,
                        y,
                        health: stats[kind_index].0,
                        damage: stats[kind_index].1,
                    });
                }
            }
        }
        let mut env = Self {
            state: State {
                seed,
                timestep: 0,
                max_timesteps,
                players,
                maps,
                monsters,
                projectiles: vec![],
                plants: vec![],
                boss_health: 24,
                boss_progress: 0,
                boss_wave_timer: 0,
                light_level: 1.0,
                achievements: BTreeSet::new(),
                trade_count: 0,
                terminated: false,
                termination_reason: None,
                last_joint_event: vec![],
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
        for player in &self.state.players {
            let action = &actions[&player.agent_id];
            if !self.legal_actions(&player.agent_id).contains(action) {
                return Err(format!("illegal action for {}: {action}", player.agent_id));
            }
        }
        self.state.last_joint_event.clear();
        let start = self.state.nev.len();
        let before = self.state.achievements.len();
        for player in &self.state.players {
            let fields = BTreeMap::from([
                ("agent_id".to_string(), json!(player.agent_id)),
                ("action".to_string(), json!(actions[&player.agent_id])),
            ]);
            let event = Event {
                timestep: self.state.timestep,
                kind: "joint_action".into(),
                fields: fields.clone(),
            };
            self.state.nev.push(event.clone());
            self.state.last_joint_event.push(event);
            self.state.legacy_nev.push(format!(
                "JointAction({},{})",
                event_field_text(&fields["agent_id"]),
                event_field_text(&fields["action"])
            ));
        }
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
        self.resolve_moves(actions);
        for idx in 0..self.state.players.len() {
            let action = actions[&self.state.players[idx].agent_id].clone();
            self.apply_action(idx, &action);
        }
        self.update_projectiles();
        self.update_monsters();
        self.update_plants();
        self.state.light_level = (1.0
            + (std::f64::consts::TAU * (self.state.timestep % DAY_LENGTH) as f64
                / DAY_LENGTH as f64)
                .cos())
            / 2.0;
        self.state.timestep += 1;
        for p in &mut self.state.players {
            if p.alive {
                if p.sleeping {
                    p.energy = (p.energy + 2).min(9);
                    if p.energy >= 9 {
                        p.sleeping = false;
                        self.state.achievements.insert("wake_up".into());
                    }
                    continue;
                }
                p.energy = (p.energy - 1).max(0);
                if self.state.timestep % 25 == 0 {
                    p.food = (p.food - 1).max(0);
                    p.drink = (p.drink - 1).max(0);
                }
                if p.food == 0 || p.drink == 0 {
                    p.health -= 1;
                }
                if p.level == NUM_LEVELS - 1 && self.state.boss_health > 0 {
                    p.health -= (2 - p.armour as i16).max(0);
                }
                if p.health <= 0 {
                    p.alive = false;
                    p.health = 0;
                }
            }
        }
        if self.state.players.iter().all(|p| p.alive) {
            self.state.achievements.insert("all_roles_alive".into());
        } else {
            self.state.achievements.remove("all_roles_alive");
        }
        if !self.state.players.iter().any(|p| p.alive) {
            self.finish("death");
        } else if self.state.boss_progress >= NUM_LEVELS - 1 {
            self.finish("boss");
        } else if self.state.timestep >= self.state.max_timesteps {
            self.finish("timestep");
        }
        let reward = (self.state.achievements.len() as isize - before as isize) as f64
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

    fn apply_action(&mut self, index: usize, action: &str) {
        if !self.state.players[index].alive {
            return;
        }
        if action.starts_with("give_") {
            self.give(index, action);
            return;
        }
        match action {
            "do" | "attack" => self.do_action(index),
            "rest" => {
                let amount = if self.state.players[index].role == "forager" {
                    4
                } else {
                    2
                };
                self.state.players[index].energy =
                    (self.state.players[index].energy + amount).min(9);
            }
            "sleep" => self.state.players[index].sleeping = true,
            "cast_spell"
                if self.state.players[index].role == "forager"
                    && self.state.players[index].mana >= 2 =>
            {
                self.state.players[index].mana -= 2;
                for player in &mut self.state.players {
                    player.health = (player.health + 2).min(9);
                }
                self.state.achievements.insert("cast_spell".into());
            }
            "shoot_arrow" => self.shoot_arrow(index),
            "descend" => self.change_floor(index, 1),
            "ascend" => self.change_floor(index, -1),
            value if value.starts_with("make_") => self.craft(index, value),
            value if value.starts_with("place_") => self.place(index, value),
            value if value.starts_with("drink_potion_") => {
                self.drink_potion(index, value.trim_start_matches("drink_potion_"))
            }
            "read_book" => self.read_book(index),
            value if value.starts_with("level_up_") => {
                self.level_up(index, value.trim_start_matches("level_up_"))
            }
            value if value.starts_with("enchant_") => {
                self.enchant(index, value.trim_start_matches("enchant_"))
            }
            _ => {}
        }
    }

    fn front(&self, index: usize) -> (usize, usize) {
        let p = &self.state.players[index];
        let (dx, dy) = match p.facing.as_str() {
            "left" => (-1, 0),
            "right" => (1, 0),
            "up" => (0, -1),
            "down" => (0, 1),
            other => panic!("invalid player facing: {other}"),
        };
        ((p.x as isize + dx) as usize, (p.y as isize + dy) as usize)
    }

    fn do_action(&mut self, index: usize) {
        let (x, y) = self.front(index);
        let level = self.state.players[index].level;
        let tile = self.state.maps[level][y][x].clone();
        let resource = match tile.as_str() {
            "tree" => Some("wood"),
            "stone" => Some("stone"),
            "coal" => Some("coal"),
            "iron" => Some("iron"),
            "diamond" => Some("diamond"),
            "ruby" => Some("ruby"),
            "sapphire" => Some("sapphire"),
            _ => None,
        };
        if let Some(resource) = resource {
            if ["coal", "iron", "diamond", "ruby", "sapphire"].contains(&resource)
                && self.state.players[index].role != "miner"
            {
                return;
            }
            let amount = if self.state.players[index].role == "miner" && resource != "wood" {
                2
            } else {
                1
            };
            *self.state.players[index]
                .inventory
                .get_mut(resource)
                .unwrap() += amount;
            self.state.maps[level][y][x] = "grass".into();
            if tile == "tree"
                && self.state.players[index].role == "forager"
                && (self.state.seed + self.state.timestep) % 2 == 0
            {
                self.state.players[index].saplings += 1;
                self.state.achievements.insert("collect_sapling".into());
            }
            self.state
                .achievements
                .insert(format!("collect_{resource}"));
            return;
        }
        if tile == "ripe_plant" && self.state.players[index].role == "forager" {
            self.state.players[index].food = (self.state.players[index].food + 4)
                .min(9 + 2 * self.state.players[index].dexterity as i16);
            self.state.maps[level][y][x] = "plant".into();
            self.state.achievements.insert("eat_plant".into());
            return;
        }
        if tile == "fountain" || tile == "water" {
            let amount = if self.state.players[index].role == "forager" {
                5
            } else {
                3
            };
            self.state.players[index].drink = (self.state.players[index].drink + amount)
                .min(9 + 2 * self.state.players[index].dexterity as i16);
            self.state.achievements.insert("drink_water".into());
            return;
        }
        if tile == "chest" {
            self.state.maps[level][y][x] = "grass".into();
            self.state.players[index].books += 1;
            self.state.players[index].arrows += 2;
            let colours = ["red", "green", "blue", "pink", "cyan", "yellow"];
            let colour =
                colours[((self.state.seed + self.state.timestep + level as u64) % 6) as usize];
            *self.state.players[index].potions.get_mut(colour).unwrap() += 1;
            if self.state.players[index].role == "miner" {
                let resource = ["coal", "iron", "diamond"][(level / 3).min(2)];
                *self.state.players[index]
                    .inventory
                    .get_mut(resource)
                    .unwrap() += 2;
            }
            self.state.achievements.insert("open_chest".into());
            return;
        }
        if let Some(mi) = self
            .state
            .monsters
            .iter()
            .position(|m| m.level == level && m.x == x && m.y == y)
        {
            let mut damage = 1
                + self.state.players[index].strength as i16
                + self.state.players[index].sword as i16 * 2;
            if self.state.players[index].role == "warrior" {
                damage *= 2
            }
            self.state.monsters[mi].health -= damage;
            if self.state.monsters[mi].health <= 0 {
                let kind = self.state.monsters[mi].kind.clone();
                self.state.monsters.remove(mi);
                self.state.players[index].xp += 1;
                if [3, 7, 12, 18].contains(&self.state.players[index].xp) {
                    self.state.players[index].level_points += 1;
                }
                if kind == "cow" {
                    self.state.players[index].food = (self.state.players[index].food + 4)
                        .min(9 + 2 * self.state.players[index].dexterity as i16);
                }
                self.state.achievements.insert("defeat_monster".into());
            }
            return;
        }
        if tile == "boss" && level == NUM_LEVELS - 1 {
            let damage =
                2 * (if self.state.players[index].role == "warrior" {
                    2
                } else {
                    1
                }) + self.state.players[index].sword as i16;
            self.state.boss_health -= damage;
            self.state.achievements.insert("damage_boss".into());
            if self.state.boss_health <= 0 {
                self.state.boss_progress = NUM_LEVELS - 1;
                self.state.achievements.insert("defeat_boss".into());
            }
        }
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
                if [
                    "grass",
                    "path",
                    "sand",
                    "gravel",
                    "fire_grass",
                    "ice_grass",
                    "stairs_down",
                    "stairs_up",
                    "crafting_table",
                    "furnace",
                    "enchantment_table_fire",
                    "enchantment_table_ice",
                ]
                .contains(&self.state.maps[p.level][ny][nx].as_str())
                {
                    desired[i] = Some((nx, ny));
                }
            }
        }
        for player in &mut self.state.players {
            if delta.contains_key(actions[&player.agent_id].as_str()) {
                player.facing = actions[&player.agent_id].clone();
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
    fn craft(&mut self, i: usize, action: &str) {
        if action == "make_arrow" && self.state.players[i].inventory["wood"] >= 1 {
            *self.state.players[i].inventory.get_mut("wood").unwrap() -= 1;
            self.state.players[i].arrows += 2;
            return;
        }
        if action == "make_torch"
            && self.state.players[i].inventory["wood"] >= 1
            && self.state.players[i].inventory["coal"] >= 1
        {
            *self.state.players[i].inventory.get_mut("wood").unwrap() -= 1;
            *self.state.players[i].inventory.get_mut("coal").unwrap() -= 1;
            self.state.players[i].torches += 2;
            return;
        }
        let recipe = match action {
            "make_wood_pickaxe" => Some(("wood", 1, "pickaxe", 1)),
            "make_stone_pickaxe" => Some(("stone", 2, "pickaxe", 2)),
            "make_iron_pickaxe" => Some(("iron", 2, "pickaxe", 3)),
            "make_diamond_pickaxe" => Some(("diamond", 2, "pickaxe", 4)),
            "make_wood_sword" => Some(("wood", 1, "sword", 1)),
            "make_stone_sword" => Some(("stone", 2, "sword", 2)),
            "make_iron_sword" => Some(("iron", 2, "sword", 3)),
            "make_diamond_sword" => Some(("diamond", 2, "sword", 4)),
            "make_iron_armour" => Some(("iron", 3, "armour", 1)),
            "make_diamond_armour" => Some(("diamond", 3, "armour", 2)),
            _ => None,
        };
        let Some((resource, cost, item, tier)) = recipe else {
            return;
        };
        if self.state.players[i].inventory[resource] < cost {
            return;
        }
        if ["iron", "diamond"].contains(&resource) && self.state.players[i].role != "miner" {
            return;
        }
        *self.state.players[i].inventory.get_mut(resource).unwrap() -= cost;
        match item {
            "pickaxe" => self.state.players[i].pickaxe = self.state.players[i].pickaxe.max(tier),
            "sword" => self.state.players[i].sword = self.state.players[i].sword.max(tier),
            _ => self.state.players[i].armour = self.state.players[i].armour.max(tier),
        };
        self.state.achievements.insert(format!("craft_{item}"));
    }
    fn place(&mut self, i: usize, action: &str) {
        if action == "place_plant" || action == "place_torch" {
            let (x, y) = self.front(i);
            let level = self.state.players[i].level;
            if !["grass", "path", "sand", "gravel"].contains(&self.state.maps[level][y][x].as_str())
            {
                return;
            }
            if action == "place_plant" && self.state.players[i].saplings > 0 {
                self.state.players[i].saplings -= 1;
                self.state.maps[level][y][x] = "plant".into();
                self.state.achievements.insert("place_plant".into());
            }
            if action == "place_torch" && self.state.players[i].torches > 0 {
                self.state.players[i].torches -= 1;
                self.state.maps[level][y][x] = "path".into();
            }
            return;
        }
        let Some((resource, cost, tile)) = (match action {
            "place_stone" => Some(("stone", 1, "stone")),
            "place_table" => Some(("wood", 2, "crafting_table")),
            "place_furnace" => Some(("stone", 4, "furnace")),
            _ => None,
        }) else {
            return;
        };
        let (x, y) = self.front(i);
        let level = self.state.players[i].level;
        if !["grass", "path", "sand", "gravel"].contains(&self.state.maps[level][y][x].as_str())
            || self.state.players[i].inventory[resource] < cost
        {
            return;
        }
        *self.state.players[i].inventory.get_mut(resource).unwrap() -= cost;
        self.state.maps[level][y][x] = tile.into();
        if action == "place_table" || action == "place_furnace" {
            self.state.achievements.insert(action.into());
        }
    }
    fn shoot_arrow(&mut self, i: usize) {
        if self.state.players[i].arrows == 0 {
            return;
        }
        self.state.players[i].arrows -= 1;
        let p = &self.state.players[i];
        let (dx, dy) = match p.facing.as_str() {
            "left" => (-1, 0),
            "right" => (1, 0),
            "up" => (0, -1),
            "down" => (0, 1),
            other => panic!("invalid player facing: {other}"),
        };
        self.state.projectiles.push(Projectile {
            owner: p.agent_id.clone(),
            level: p.level,
            x: p.x as isize,
            y: p.y as isize,
            dx,
            dy,
            damage: 2 + p.dexterity as i16 + if p.role == "warrior" { 2 } else { 0 },
            ttl: 8,
        });
        self.state.achievements.insert("shoot_arrow".into());
    }
    fn drink_potion(&mut self, i: usize, colour: &str) {
        if !self.state.players[i].potions.contains_key(colour)
            || self.state.players[i].potions[colour] == 0
        {
            return;
        }
        *self.state.players[i].potions.get_mut(colour).unwrap() -= 1;
        match colour {
            "red" => {
                self.state.players[i].health = (self.state.players[i].health + 5)
                    .min(9 + 2 * self.state.players[i].strength as i16)
            }
            "green" => {
                self.state.players[i].food = (self.state.players[i].food + 5)
                    .min(9 + 2 * self.state.players[i].dexterity as i16)
            }
            "blue" => {
                self.state.players[i].drink = (self.state.players[i].drink + 5)
                    .min(9 + 2 * self.state.players[i].dexterity as i16)
            }
            "pink" => {
                self.state.players[i].mana = (self.state.players[i].mana + 5)
                    .min(9 + 2 * self.state.players[i].intelligence as i16)
            }
            "cyan" => self.state.players[i].energy = (self.state.players[i].energy + 5).min(9),
            _ => self.state.players[i].level_points += 1,
        }
        self.state.achievements.insert("drink_potion".into());
    }
    fn read_book(&mut self, i: usize) {
        if self.state.players[i].books == 0 {
            return;
        }
        self.state.players[i].books -= 1;
        self.state.players[i].intelligence += 1;
        self.state.achievements.insert("read_book".into());
    }
    fn level_up(&mut self, i: usize, attribute: &str) {
        if self.state.players[i].level_points == 0 {
            return;
        }
        match attribute {
            "dexterity" => self.state.players[i].dexterity += 1,
            "strength" => self.state.players[i].strength += 1,
            "intelligence" => self.state.players[i].intelligence += 1,
            _ => return,
        }
        self.state.players[i].level_points -= 1;
        self.state.achievements.insert("level_up".into());
    }
    fn enchant(&mut self, i: usize, item: &str) {
        if !["sword", "armour", "bow"].contains(&item)
            || self.state.players[i].inventory["ruby"] == 0
            || self.state.players[i].inventory["sapphire"] == 0
        {
            return;
        }
        *self.state.players[i].inventory.get_mut("ruby").unwrap() -= 1;
        *self.state.players[i].inventory.get_mut("sapphire").unwrap() -= 1;
        let value = Some(
            if (self.state.seed + self.state.timestep) % 2 == 0 {
                "fire"
            } else {
                "ice"
            }
            .into(),
        );
        match item {
            "sword" => self.state.players[i].sword_enchantment = value,
            "armour" => self.state.players[i].armour_enchantment = value,
            _ => self.state.players[i].bow_enchantment = value,
        }
        self.state.achievements.insert("enchant_item".into());
    }
    fn change_floor(&mut self, i: usize, direction: isize) {
        let p = &self.state.players[i];
        let required = if direction > 0 {
            "stairs_down"
        } else {
            "stairs_up"
        };
        if self.state.maps[p.level][p.y][p.x] != required {
            return;
        }
        let next = p.level as isize + direction;
        if !(0..NUM_LEVELS as isize).contains(&next) {
            return;
        }
        self.state.players[i].level = next as usize;
        self.state.players[i].x = if direction > 0 { 2 } else { 45 };
        self.state.players[i].y = self.state.players[i].x;
        if direction > 0 {
            self.state.achievements.insert("descend".into());
        }
    }
    fn update_projectiles(&mut self) {
        let mut remaining = Vec::new();
        for mut shot in self.state.projectiles.drain(..) {
            shot.x += shot.dx;
            shot.y += shot.dy;
            shot.ttl -= 1;
            if shot.ttl == 0
                || shot.x < 0
                || shot.y < 0
                || shot.x >= MAP_SIZE as isize
                || shot.y >= MAP_SIZE as isize
            {
                continue;
            }
            if ["stone", "wall", "water"]
                .contains(&self.state.maps[shot.level][shot.y as usize][shot.x as usize].as_str())
            {
                continue;
            }
            if let Some(mi) = self.state.monsters.iter().position(|m| {
                m.level == shot.level && m.x == shot.x as usize && m.y == shot.y as usize
            }) {
                self.state.monsters[mi].health -= shot.damage;
                if self.state.monsters[mi].health <= 0 {
                    self.state.monsters.remove(mi);
                    self.state.achievements.insert("defeat_monster".into());
                }
                continue;
            }
            remaining.push(shot)
        }
        self.state.projectiles = remaining;
    }
    fn update_monsters(&mut self) {
        for mi in 0..self.state.monsters.len() {
            let level = self.state.monsters[mi].level;
            let Some((pi, _)) = self
                .state
                .players
                .iter()
                .enumerate()
                .filter(|(_, p)| p.alive && p.level == level)
                .map(|(i, p)| {
                    (
                        i,
                        (p.x.abs_diff(self.state.monsters[mi].x)
                            + p.y.abs_diff(self.state.monsters[mi].y)),
                    )
                })
                .min_by_key(|(_, d)| *d)
            else {
                continue;
            };
            let distance = self.state.players[pi].x.abs_diff(self.state.monsters[mi].x)
                + self.state.players[pi].y.abs_diff(self.state.monsters[mi].y);
            if distance <= 1 {
                let damage = (self.state.monsters[mi].damage
                    - (self.state.players[pi].armour as i16
                        + self.state.players[pi].strength as i16 / 2))
                    .max(0);
                self.state.players[pi].health -= damage;
            } else if distance <= 8 {
                let target_x = self.state.players[pi].x;
                let target_y = self.state.players[pi].y;
                let mob_x = self.state.monsters[mi].x;
                let mob_y = self.state.monsters[mi].y;
                let (dx, dy) = if target_x.abs_diff(mob_x) >= target_y.abs_diff(mob_y) {
                    (if target_x > mob_x { 1 } else { -1 }, 0)
                } else {
                    (0, if target_y > mob_y { 1 } else { -1 })
                };
                let nx = (mob_x as isize + dx) as usize;
                let ny = (mob_y as isize + dy) as usize;
                let open = !["stone", "wall", "water", "lava"]
                    .contains(&self.state.maps[level][ny][nx].as_str());
                let player_free = !self
                    .state
                    .players
                    .iter()
                    .any(|p| p.level == level && p.x == nx && p.y == ny);
                if open && player_free {
                    self.state.monsters[mi].x = nx;
                    self.state.monsters[mi].y = ny;
                }
            }
        }
    }

    fn update_plants(&mut self) {
        if self.state.timestep > 0 && self.state.timestep % 50 == 0 {
            for level in 0..NUM_LEVELS {
                for y in 0..MAP_SIZE {
                    for x in 0..MAP_SIZE {
                        if self.state.maps[level][y][x] == "plant" {
                            self.state.maps[level][y][x] = "ripe_plant".into();
                        }
                    }
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
        if resource == "food" || resource == "drink" {
            let stock = if resource == "food" {
                self.state.players[giver].food
            } else {
                self.state.players[giver].drink
            };
            let target_stock = if resource == "food" {
                self.state.players[target].food
            } else {
                self.state.players[target].drink
            };
            if stock <= 0 || target_stock >= 9 {
                return;
            }
            if resource == "food" {
                self.state.players[giver].food -= 1;
                self.state.players[target].food = (self.state.players[target].food + 1).min(9);
            } else {
                self.state.players[giver].drink -= 1;
                self.state.players[target].drink = (self.state.players[target].drink + 1).min(9);
            }
            self.state.players[target].request_type = None;
            self.state.players[target].request_duration = 0;
            self.state.trade_count += 1;
            self.state.achievements.insert("trade".into());
            return;
        }
        let stock = *self.state.players[giver]
            .inventory
            .get(resource)
            .unwrap_or(&0);
        if stock == 0 || self.state.players[target].inventory[resource] >= 99 {
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
            .map(|(k, v)| (k.into(), json!(v)))
            .collect();
        let event = Event {
            timestep: self.state.timestep,
            kind: kind.into(),
            fields,
        };
        self.state.nev.push(event.clone());
        self.state.last_joint_event.push(event);
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
                .map(event_field_text)
                .collect::<Vec<_>>()
                .join(",")
        ));
    }
    pub fn checkpoint_json(&self) -> String {
        serde_json::to_string(&Checkpoint {
            schema_version: "craftax-coop.checkpoint.v1".into(),
            state: self.state.clone(),
        })
        .expect("state serializes")
    }
    pub fn restore_json(raw: &str) -> Result<Self, serde_json::Error> {
        let checkpoint: Checkpoint = serde_json::from_str(raw)?;
        if checkpoint.schema_version != "craftax-coop.checkpoint.v1" {
            return Err(<serde_json::Error as serde::de::Error>::custom(
                "unsupported checkpoint schema",
            ));
        }
        if checkpoint
            .state
            .players
            .iter()
            .any(|player| !["warrior", "forager", "miner"].contains(&player.role.as_str()))
        {
            return Err(<serde_json::Error as serde::de::Error>::custom(
                "invalid player role in checkpoint",
            ));
        }
        if checkpoint
            .state
            .players
            .iter()
            .any(|player| !["left", "right", "up", "down"].contains(&player.facing.as_str()))
        {
            return Err(<serde_json::Error as serde::de::Error>::custom(
                "invalid player facing in checkpoint",
            ));
        }
        Ok(Self {
            state: checkpoint.state,
        })
    }

    pub fn legal_actions(&self, agent_id: &str) -> Vec<String> {
        let mut actions = [
            "noop",
            "left",
            "right",
            "up",
            "down",
            "do",
            "sleep",
            "rest",
            "descend",
            "ascend",
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
            "make_iron_armour",
            "make_diamond_armour",
            "shoot_arrow",
            "make_arrow",
            "cast_spell",
            "place_torch",
            "make_torch",
            "attack",
            "drink_potion_red",
            "drink_potion_green",
            "drink_potion_blue",
            "drink_potion_pink",
            "drink_potion_cyan",
            "drink_potion_yellow",
            "read_book",
            "enchant_sword",
            "enchant_armour",
            "enchant_bow",
            "level_up_dexterity",
            "level_up_strength",
            "level_up_intelligence",
        ]
        .into_iter()
        .map(str::to_string)
        .collect::<Vec<_>>();
        actions.extend(RESOURCES.into_iter().map(|r| format!("request_{r}")));
        for resource in RESOURCES {
            for player in &self.state.players {
                if player.agent_id != agent_id {
                    actions.push(format!("give_{resource}_to_{}", player.agent_id));
                }
            }
        }
        actions
    }

    pub fn observations(&self, radius: isize) -> BTreeMap<String, Value> {
        let dashboard = self
            .state
            .players
            .iter()
            .map(Self::player_json)
            .collect::<Vec<_>>();
        self.state.players.iter().enumerate().map(|(index,p)|{
            let mut view=Vec::new();
            for y in p.y as isize-radius..=p.y as isize+radius { let mut row=Vec::new(); for x in p.x as isize-radius..=p.x as isize+radius {
                let terrain=if x<0||y<0||x>=MAP_SIZE as isize||y>=MAP_SIZE as isize{"out_of_bounds"}else{self.state.maps[p.level][y as usize][x as usize].as_str()};
                let agents=self.state.players.iter().filter(|q|q.alive&&q.level==p.level&&q.x as isize==x&&q.y as isize==y).map(|q|q.agent_id.clone()).collect::<Vec<_>>();
                let mobs=self.state.monsters.iter().filter(|m|m.level==p.level&&m.x as isize==x&&m.y as isize==y).map(|m|m.id.clone()).collect::<Vec<_>>();
                row.push(json!({"x":x,"y":y,"terrain":terrain,"agents":agents,"mobs":mobs}));
            } view.push(Value::Array(row)); }
            let visible=self.state.monsters.iter().filter(|m|m.level==p.level&&m.x.abs_diff(p.x)<=radius as usize&&m.y.abs_diff(p.y)<=radius as usize).collect::<Vec<_>>();
            let achievements=self.state.achievements.iter().map(|name|(name.clone(),true)).collect::<BTreeMap<_,_>>();
            (p.agent_id.clone(),json!({"agent_id":p.agent_id,"agent_index":index,"role":p.role,"legal_agent_ids":self.state.players.iter().map(|q|q.agent_id.clone()).collect::<Vec<_>>(),"legal_actions":self.legal_actions(&p.agent_id),"self":Self::player_json(p),"teammate_dashboard":dashboard,"level":p.level,"map_size":[MAP_SIZE,MAP_SIZE],"num_levels":NUM_LEVELS,"local_view":view,"ascii":self.render_ascii(p,radius),"visible_monsters":visible,"last_joint_event":self.state.last_joint_event,"shared":{"timestep":self.state.timestep,"light_level":self.state.light_level,"boss_health":self.state.boss_health,"boss_progress":self.state.boss_progress,"trade_count":self.state.trade_count,"achievements":achievements}}))
        }).collect()
    }

    fn render_ascii(&self, player: &Player, radius: isize) -> String {
        (player.y as isize - radius..=player.y as isize + radius)
            .map(|y| {
                (player.x as isize - radius..=player.x as isize + radius)
                    .map(|x| {
                        if let Some((index, _)) =
                            self.state.players.iter().enumerate().find(|(_, p)| {
                                p.alive
                                    && p.level == player.level
                                    && p.x as isize == x
                                    && p.y as isize == y
                            })
                        {
                            return char::from_digit(index as u32, 10).unwrap_or('@');
                        }
                        if self.state.monsters.iter().any(|m| {
                            m.level == player.level && m.x as isize == x && m.y as isize == y
                        }) {
                            return 'M';
                        }
                        if x < 0 || y < 0 || x >= MAP_SIZE as isize || y >= MAP_SIZE as isize {
                            return ' ';
                        }
                        match self.state.maps[player.level][y as usize][x as usize].as_str() {
                            "grass" | "path" => '.',
                            "water" | "fountain" => '~',
                            "tree" => 'T',
                            "stone" => '#',
                            "coal" => 'c',
                            "iron" => 'i',
                            "diamond" => 'd',
                            "ruby" => 'r',
                            "sapphire" => 's',
                            "chest" => 'C',
                            "boss" => 'B',
                            "stairs_down" => '>',
                            "stairs_up" => '<',
                            "sand" => ':',
                            "ice_grass" => '*',
                            _ => '?',
                        }
                    })
                    .collect::<String>()
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    fn player_json(p: &Player) -> Value {
        json!({"agent_id":p.agent_id,"role":p.role,"position":[p.x,p.y],"level":p.level,"facing":p.facing,"health":p.health,"food":p.food,"drink":p.drink,"energy":p.energy,"mana":p.mana,"alive":p.alive,"sleeping":p.sleeping,"inventory":p.inventory,"equipment":{"pickaxe":p.pickaxe,"sword":p.sword,"armour":p.armour,"arrows":p.arrows,"torches":p.torches,"books":p.books,"saplings":p.saplings,"potions":p.potions,"enchantments":{"sword":p.sword_enchantment,"armour":p.armour_enchantment,"bow":p.bow_enchantment}},"attributes":{"dexterity":p.dexterity,"strength":p.strength,"intelligence":p.intelligence,"xp":p.xp,"level_points":p.level_points},"request":{"resource":p.request_type,"remaining":p.request_duration}})
    }
}

fn event_field_text(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        _ => value.to_string(),
    }
}
