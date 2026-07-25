use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

pub mod render;

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

mod achievement_maps {
    use serde::{Deserialize, Deserializer, Serialize, Serializer};
    use std::collections::{BTreeMap, BTreeSet};

    pub fn serialize<S>(
        value: &BTreeMap<String, BTreeSet<String>>,
        serializer: S,
    ) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        value
            .iter()
            .map(|(agent, earned)| {
                (
                    agent,
                    earned
                        .iter()
                        .map(|name| (name, true))
                        .collect::<BTreeMap<_, _>>(),
                )
            })
            .collect::<BTreeMap<_, _>>()
            .serialize(serializer)
    }
    pub fn deserialize<'de, D>(
        deserializer: D,
    ) -> Result<BTreeMap<String, BTreeSet<String>>, D::Error>
    where
        D: Deserializer<'de>,
    {
        Ok(
            BTreeMap::<String, BTreeMap<String, bool>>::deserialize(deserializer)?
                .into_iter()
                .map(|(agent, flags)| {
                    (
                        agent,
                        flags
                            .into_iter()
                            .filter_map(|(name, earned)| earned.then_some(name))
                            .collect(),
                    )
                })
                .collect(),
        )
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
    pub health: f64,
    pub food: i16,
    pub drink: i16,
    pub energy: i16,
    pub mana: i16,
    pub alive: bool,
    pub inventory: BTreeMap<String, u16>,
    pub pickaxe: u8,
    pub sword: u8,
    pub armour: u8,
    pub armour_slots: Vec<u8>,
    pub bow: u8,
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
    pub armour_enchantments: Vec<Option<String>>,
    pub bow_enchantment: Option<String>,
    pub learned_spell: bool,
    pub sleeping: bool,
    pub resting: bool,
    pub recover: f64,
    pub hunger: f64,
    pub thirst: f64,
    pub fatigue: f64,
    pub recover_mana: f64,
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
    pub health: f64,
    pub damage: i16,
    pub category: String,
    pub attack_cooldown: i16,
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
    pub kind: String,
    pub hostile: bool,
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
pub struct CoordSite {
    pub site_id: String,
    pub site_index: u8,
    pub kind: String,
    pub level: usize,
    pub x: usize,
    pub y: usize,
    pub participants: Vec<String>,
    pub required_role: Option<String>,
    pub receiver_role: Option<String>,
    pub resource: Option<String>,
    pub window: u64,
    pub status: String,
    pub opened_at: Option<u64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct AlemCoordState {
    pub scenario: String,
    pub alpha_milli: u16,
    pub sites: Vec<CoordSite>,
    pub base_reward: f64,
    pub coord_reward: f64,
    pub site_metrics: BTreeMap<String, BTreeMap<String, u64>>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AlemCoordConfig {
    pub scenario: String,
    pub alpha_milli: u16,
}

impl AlemCoordConfig {
    pub fn new(scenario: impl Into<String>, alpha_milli: u16) -> Result<Self, String> {
        if ![300, 600, 900].contains(&alpha_milli) {
            return Err("alem_coord_v0 alpha must be one of 0.3, 0.6, 0.9".into());
        }
        let scenario = scenario.into();
        if !["sync_2", "sync_all", "handover"].contains(&scenario.as_str()) {
            return Err("alem_coord_v0 scenario must be sync_2, sync_all, or handover".into());
        }
        Ok(Self { scenario, alpha_milli })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct State {
    pub seed: u64,
    pub timestep: u64,
    pub max_timesteps: u64,
    pub players: Vec<Player>,
    pub maps: Vec<Vec<Vec<String>>>,
    pub item_maps: Vec<Vec<Vec<Option<String>>>>,
    pub light_maps: Vec<Vec<Vec<f64>>>,
    pub ladders_up: Vec<Vec<(usize, usize)>>,
    pub ladders_down: Vec<Vec<(usize, usize)>>,
    pub monsters: Vec<Monster>,
    pub projectiles: Vec<Projectile>,
    pub plants: Vec<Plant>,
    pub boss_health: i16,
    pub boss_progress: usize,
    pub boss_wave_timer: u16,
    pub chests_opened: Vec<Vec<bool>>,
    pub monsters_killed: Vec<u16>,
    pub potion_mapping: Vec<String>,
    pub light_level: f64,
    #[serde(with = "achievement_map")]
    pub achievements: BTreeSet<String>,
    #[serde(with = "achievement_maps")]
    pub achievements_by_agent: BTreeMap<String, BTreeSet<String>>,
    pub trade_count: u64,
    pub food_trade_count: u64,
    pub drink_trade_count: u64,
    pub revives: u64,
    pub ff_damage_dealt: f64,
    pub terminated: bool,
    pub termination_reason: Option<String>,
    pub last_joint_event: Vec<Event>,
    pub nev: Vec<Event>,
    pub legacy_nev: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub alem_coord: Option<AlemCoordState>,
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
        Self::reset_with_profile(seed, agent_count, max_timesteps, None)
    }

    pub fn reset_alem(
        seed: u64,
        agent_count: usize,
        max_timesteps: u64,
        config: AlemCoordConfig,
    ) -> Self {
        Self::reset_with_profile(seed, agent_count, max_timesteps, Some(config))
    }

    fn reset_with_profile(
        seed: u64,
        agent_count: usize,
        max_timesteps: u64,
        profile: Option<AlemCoordConfig>,
    ) -> Self {
        assert!(agent_count >= 2);
        if profile.is_some() {
            assert_eq!(agent_count, 3, "alem_coord_v0 requires exactly three agents");
        }
        let roles = ["warrior", "forager", "miner"];
        let mut players: Vec<Player> = (0..agent_count)
            .map(|i| Player {
                agent_id: format!("agent_{i}"),
                role: roles[i % 3].into(),
                x: 3 + i,
                y: 3,
                level: 0,
                health: 9.0,
                food: 9,
                drink: 9,
                energy: 9,
                mana: 9,
                alive: true,
                inventory: RESOURCES.iter().map(|r| (r.to_string(), 0)).collect(),
                pickaxe: 0,
                sword: 0,
                armour: 0,
                armour_slots: vec![0; 4],
                bow: 0,
                arrows: 0,
                torches: 0,
                books: 0,
                saplings: 0,
                potions: ["red", "green", "blue", "pink", "cyan", "yellow"]
                    .into_iter()
                    .map(|c| (c.into(), 0))
                    .collect(),
                dexterity: 1,
                strength: 1,
                intelligence: 1,
                xp: 0,
                level_points: 0,
                sword_enchantment: None,
                armour_enchantment: None,
                armour_enchantments: vec![None; 4],
                bow_enchantment: None,
                learned_spell: false,
                sleeping: false,
                resting: false,
                recover: 0.0,
                hunger: 0.0,
                thirst: 0.0,
                fatigue: 0.0,
                recover_mana: 0.0,
                facing: "down".into(),
                request_type: None,
                request_duration: 0,
            })
            .collect();
        let mut maps = vec![vec![vec!["grass".to_string(); MAP_SIZE]; MAP_SIZE]; NUM_LEVELS];
        let biomes = [
            ["grass", "water", "stone", "tree"],
            ["path", "water", "stone", "stalagmite"],
            ["path", "water", "stone", "stalagmite"],
            ["path", "water", "stone", "stalagmite"],
            ["path", "water", "stone", "stalagmite"],
            ["path", "water", "stone", "stalagmite"],
            ["fire_grass", "lava", "stone", "fire_tree"],
            ["ice_grass", "water", "stone", "ice_shrub"],
            ["path", "wall", "wall", "grave"],
        ];
        let floor_resources: [&[&str]; 9] = [
            &[],
            &["coal", "iron"],
            &["coal", "iron"],
            &["iron"],
            &["diamond"],
            &["diamond", "ruby", "sapphire"],
            &["ruby"],
            &["sapphire"],
            &[],
        ];
        for level in 0..NUM_LEVELS {
            let mut rng = (seed + 1)
                .wrapping_mul(1_000_003)
                .wrapping_add(level as u64 * 97);
            for i in 0..MAP_SIZE {
                maps[level][0][i] = biomes[level][2].into();
                maps[level][MAP_SIZE - 1][i] = biomes[level][2].into();
                maps[level][i][0] = biomes[level][2].into();
                maps[level][i][MAP_SIZE - 1] = biomes[level][2].into();
            }
            for y in 1..MAP_SIZE - 1 {
                for x in 1..MAP_SIZE - 1 {
                    rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    let roll = ((rng >> 32) % 1000) as usize;
                    maps[level][y][x] = if roll < 55 {
                        biomes[level][1]
                    } else if roll < 110 {
                        biomes[level][2]
                    } else if roll < 150 {
                        biomes[level][3]
                    } else if roll < 180 {
                        let choices = floor_resources[level];
                        if choices.is_empty() {
                            biomes[level][3]
                        } else {
                            choices[(((rng >> 16) as usize) + level) % choices.len()]
                        }
                    } else if roll < 190 {
                        "chest"
                    } else if roll < 200 && level == 0 {
                        "plant"
                    } else {
                        biomes[level][0]
                    }
                    .into();
                }
            }
            if [1, 3, 4].contains(&level) {
                maps[level] = vec![vec!["wall".into(); MAP_SIZE]; MAP_SIZE];
                let mut rooms = Vec::new();
                for row in 0..2 {
                    for column in 0..4 {
                        let room = (2 + column * 11, 3 + row * 22, 9, 17);
                        rooms.push(room);
                        for y in room.1..room.1 + room.3 {
                            for x in room.0..room.0 + room.2 {
                                maps[level][y][x] = "path".into();
                            }
                        }
                    }
                }
                for row in 0..2 {
                    for column in 0..3 {
                        let left = rooms[row * 4 + column];
                        let right = rooms[row * 4 + column + 1];
                        let y = left.1 + left.3 / 2;
                        for x in left.0 + left.2..=right.0 {
                            maps[level][y][x] = "path".into();
                        }
                    }
                }
                for column in 0..4 {
                    let top = rooms[column];
                    let bottom = rooms[column + 4];
                    let x = top.0 + top.2 / 2;
                    for y in top.1 + top.3..=bottom.1 {
                        maps[level][y][x] = "path".into();
                    }
                }
                for (index, room) in rooms.into_iter().enumerate() {
                    let (cx, cy) = (room.0 + room.2 / 2, room.1 + room.3 / 2);
                    if index % 2 == 0 {
                        maps[level][cy][cx] = "chest".into();
                    }
                    if level == 3 && [1, 6].contains(&index) {
                        maps[level][cy][cx] = "fountain".into();
                    }
                    let choices = floor_resources[level];
                    if !choices.is_empty() {
                        maps[level][room.1 + 2][room.0 + 2] = choices[index % choices.len()].into();
                    }
                }
            }
            if level < NUM_LEVELS - 1 {
                maps[level][MAP_SIZE - 3][MAP_SIZE - 3] = "stairs_down".into();
            }
            if level > 0 {
                maps[level][2][2] = "stairs_up".into();
            }
            if level == 6 {
                maps[level][10][10] = "enchantment_table_fire".into();
            }
            if level == 7 {
                maps[level][10][10] = "enchantment_table_ice".into();
            }
        }
        maps[NUM_LEVELS - 1][MAP_SIZE / 2][MAP_SIZE / 2] = "necromancer".into();
        for (offset, tile) in (-3isize..=3).zip([
            "grave", "grave2", "grave3", "grave", "grave3", "grave2", "grave",
        ]) {
            maps[NUM_LEVELS - 1][MAP_SIZE / 2 + 3][(MAP_SIZE as isize / 2 + offset) as usize] =
                tile.into();
        }
        for index in 0..agent_count {
            maps[0][3][3 + index] = "grass".into();
        }
        maps[0][5][5] = "fountain".into();
        let ladders_up = (0..NUM_LEVELS)
            .map(|_| (0..agent_count).map(|i| (2 + i, 2)).collect::<Vec<_>>())
            .collect::<Vec<_>>();
        let ladders_down = (0..NUM_LEVELS)
            .map(|_| {
                (0..agent_count)
                    .map(|i| (MAP_SIZE - 3 - i, MAP_SIZE - 3))
                    .collect::<Vec<_>>()
            })
            .collect::<Vec<_>>();
        let mut item_maps = vec![vec![vec![None; MAP_SIZE]; MAP_SIZE]; NUM_LEVELS];
        let mut light_maps: Vec<Vec<Vec<f64>>> = (0..NUM_LEVELS)
            .map(|level| {
                vec![
                    vec![
                        if level == 0 {
                            1.0
                        } else if [6, 7].contains(&level) {
                            0.15
                        } else {
                            0.0
                        };
                        MAP_SIZE
                    ];
                    MAP_SIZE
                ]
            })
            .collect();
        for level in 0..NUM_LEVELS {
            if level < NUM_LEVELS - 1 {
                for &(x, y) in &ladders_down[level] {
                    maps[level][y][x] = "stairs_down".into();
                    item_maps[level][y][x] = Some("ladder_down".into());
                }
            }
            if [1, 3, 4].contains(&level) {
                for (x, y) in [(8, 11), (19, 33), (30, 11), (41, 33)] {
                    if maps[level][y][x] == "path" {
                        item_maps[level][y][x] = Some("torch".into());
                        for yy in y.saturating_sub(4)..(y + 5).min(MAP_SIZE) {
                            for xx in x.saturating_sub(4)..(x + 5).min(MAP_SIZE) {
                                let light =
                                    (1.0 - (xx.abs_diff(x) + yy.abs_diff(y)) as f64 / 6.0).max(0.0);
                                light_maps[level][yy][xx] = light_maps[level][yy][xx].max(light);
                            }
                        }
                    }
                }
            }
            if level > 0 {
                for &(x, y) in &ladders_up[level] {
                    maps[level][y][x] = "stairs_up".into();
                    item_maps[level][y][x] = Some("ladder_up".into());
                }
            }
        }
        let alem_coord = profile.map(|config| {
            let positions = match config.scenario.as_str() {
                "sync_2" => [(4, 3, "down"), (3, 4, "right"), (5, 3, "down")],
                "sync_all" => [(4, 3, "down"), (3, 4, "right"), (5, 4, "left")],
                "handover" => [(5, 3, "down"), (3, 4, "right"), (4, 3, "down")],
                _ => unreachable!("AlemCoordConfig validates scenario"),
            };
            for (player, (x, y, facing)) in players.iter_mut().zip(positions) {
                player.x = x;
                player.y = y;
                player.facing = facing.into();
            }
            maps[0][4][4] = "coord_site".into();
            if config.scenario == "handover" {
                *players[2].inventory.get_mut("iron").unwrap() = 1;
            }
            alem_coord_state(config)
        });
        let monsters = Vec::new();
        let mut env = Self {
            state: State {
                seed,
                timestep: 0,
                max_timesteps,
                players,
                maps,
                item_maps,
                light_maps,
                ladders_up,
                ladders_down,
                monsters,
                projectiles: vec![],
                plants: vec![],
                boss_health: 8,
                boss_progress: 0,
                boss_wave_timer: 7,
                chests_opened: vec![vec![false; agent_count]; NUM_LEVELS],
                monsters_killed: [vec![10], vec![0; NUM_LEVELS - 1]].concat(),
                potion_mapping: potion_mapping(seed),
                light_level: 1.0,
                achievements: BTreeSet::new(),
                achievements_by_agent: (0..agent_count)
                    .map(|i| (format!("agent_{i}"), BTreeSet::new()))
                    .collect(),
                trade_count: 0,
                food_trade_count: 0,
                drink_trade_count: 0,
                revives: 0,
                ff_damage_dealt: 0.0,
                terminated: false,
                termination_reason: None,
                last_joint_event: vec![],
                nev: vec![],
                legacy_nev: vec![],
                alem_coord,
            },
        };
        env.event_values(
            "game_started",
            BTreeMap::from([
                ("seed".into(), json!(seed)),
                ("task_id".into(), json!("craftax-multiplayer")),
            ]),
        );
        if let Some(coord) = env.state.alem_coord.clone() {
            for site in coord.sites {
                env.event_values(
                    "coord_site_spawned",
                    BTreeMap::from([
                        ("alpha_milli".into(), json!(coord.alpha_milli)),
                        ("participants".into(), json!(site.participants)),
                        ("site_id".into(), json!(site.site_id)),
                        ("site_kind".into(), json!(site.kind)),
                        ("target".into(), json!([site.level, site.x, site.y])),
                    ]),
                );
            }
        }
        env
    }

    pub fn step(&mut self, actions: &BTreeMap<String, String>) -> Result<StepResult, String> {
        let values = actions
            .iter()
            .map(|(agent, action)| (agent.clone(), Value::String(action.clone())))
            .collect();
        self.step_json(&values)
    }

    pub fn step_json(&mut self, raw_actions: &BTreeMap<String, Value>) -> Result<StepResult, String> {
        if self.state.terminated {
            return Err("step called after terminal state".into());
        }
        if raw_actions.len() != self.state.players.len()
            || self
                .state
                .players
                .iter()
                .any(|p| !raw_actions.contains_key(&p.agent_id))
        {
            return Err("joint action must contain every agent".into());
        }
        let mut actions = BTreeMap::new();
        let mut messages = Vec::new();
        for player in &self.state.players {
            let raw = &raw_actions[&player.agent_id];
            let action = raw
                .as_str()
                .or_else(|| raw.get("kind").and_then(Value::as_str))
                .ok_or_else(|| format!("invalid action for {}", player.agent_id))?
                .to_string();
            if !self.legal_actions(&player.agent_id).contains(&action) {
                return Err(format!("illegal action for {}: {action}", player.agent_id));
            }
            if action == "say" {
                let object = raw.as_object().ok_or_else(|| "ALEM say must be an object".to_string())?;
                if object.keys().any(|key| !["kind", "to", "code", "site_id"].contains(&key.as_str())) {
                    return Err("ALEM messages permit only kind, to, code, and optional site_id".into());
                }
                let to = object.get("to").and_then(Value::as_str).ok_or_else(|| "ALEM say requires to".to_string())?;
                if to == player.agent_id || (to != "all" && !self.state.players.iter().any(|other| other.agent_id == to)) {
                    return Err("ALEM message recipient must be another agent or all".into());
                }
                let code = object.get("code").and_then(Value::as_str).ok_or_else(|| "ALEM say requires code".to_string())?;
                if !["NEED_IRON", "MEET_AT", "ATTACK_MOB", "BUILD_HERE"].contains(&code) {
                    return Err("invalid ALEM message code".into());
                }
                let mut fields = BTreeMap::from([
                    ("sender".into(), json!(player.agent_id)),
                    ("to".into(), json!(to)),
                    ("code".into(), json!(code)),
                ]);
                if let Some(site_id) = object.get("site_id") {
                    let site_id = site_id.as_str().ok_or_else(|| "ALEM message site_id must be a string".to_string())?;
                    fields.insert("site_id".into(), json!(site_id));
                }
                messages.push((player.agent_id.clone(), fields));
            }
            actions.insert(player.agent_id.clone(), action);
        }
        self.state.last_joint_event.clear();
        let start = self.state.nev.len();
        let before = self.state.achievements_by_agent.clone();
        let before_health = self.state.players.iter().map(|p| p.health).sum::<f64>();
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
                event_field_text(&fields["action"]),
                event_field_text(&fields["agent_id"])
            ));
        }
        for (sender, fields) in messages {
            self.event_values("message", fields);
            let index = self
                .state
                .players
                .iter()
                .position(|player| player.agent_id == sender)
                .expect("message sender is a player");
            self.award("coord_message", &[index]);
        }
        let effective = self
            .state
            .players
            .iter()
            .map(|p| {
                (
                    p.agent_id.clone(),
                    if !p.alive || p.sleeping || p.resting || actions[&p.agent_id] == "say" {
                        "noop".into()
                    } else {
                        actions[&p.agent_id].clone()
                    },
                )
            })
            .collect::<BTreeMap<_, _>>();
        self.resolve_floor_actions(&effective);
        let coord_step_reward = self.resolve_coord_sites(&effective);
        self.resolve_joint_do(&effective);
        for idx in 0..self.state.players.len() {
            let action = effective[&self.state.players[idx].agent_id].clone();
            if !["do", "attack"].contains(&action.as_str()) {
                self.apply_action(idx, &action);
            }
        }
        for p in &mut self.state.players {
            p.request_duration = p.request_duration.saturating_sub(1);
            if p.request_duration == 0 {
                p.request_type = None;
            }
        }
        for idx in 0..self.state.players.len() {
            let action = &effective[&self.state.players[idx].agent_id];
            if let Some(resource) = action.strip_prefix("request_") {
                if RESOURCES.contains(&resource) {
                    self.state.players[idx].request_type = Some(resource.into());
                    self.state.players[idx].request_duration = REQUEST_DURATION;
                    self.event_values(
                        "request_made",
                        BTreeMap::from([
                            ("agent_id".into(), json!(self.state.players[idx].agent_id)),
                            ("duration".into(), json!(REQUEST_DURATION)),
                            ("resource".into(), json!(resource)),
                        ]),
                    );
                }
            }
        }
        self.resolve_moves(&effective);
        self.update_projectiles();
        self.update_monsters();
        self.spawn_mobs();
        self.update_boss();
        self.update_plants();
        self.state.light_level = ((((1.0
            + (std::f64::consts::TAU * (self.state.timestep % DAY_LENGTH) as f64
                / DAY_LENGTH as f64)
                .cos())
            / 2.0)
            .max(0.1) * 100_000_000_000_000.0).round()) / 100_000_000_000_000.0;
        self.state.timestep += 1;
        let mut woke = Vec::new();
        for (player_index, p) in self.state.players.iter_mut().enumerate() {
            if p.alive {
                let decay = 1.0 - 0.125 * (p.dexterity as f64 - 1.0);
                p.hunger += if p.sleeping { 0.5 } else { 1.0 } * decay;
                p.thirst += if p.sleeping { 0.5 } else { 1.0 } * decay;
                if p.hunger > 25.0 {
                    p.food = (p.food - if p.level == NUM_LEVELS - 1 { 0 } else { 1 }).max(0);
                    p.hunger = 0.0;
                }
                if p.thirst > 20.0 {
                    p.drink = (p.drink - if p.level == NUM_LEVELS - 1 { 0 } else { 1 }).max(0);
                    p.thirst = 0.0;
                }
                p.fatigue += if p.sleeping { -1.0 } else { decay };
                if p.fatigue > 30.0 {
                    p.energy = (p.energy - 1).max(0);
                    p.fatigue = 0.0;
                }
                if p.fatigue < -10.0 {
                    p.energy = (p.energy + 1).min(max_energy(p));
                    p.fatigue = 0.0;
                }
                let necessities = p.food > 0 && p.drink > 0 && (p.energy > 0 || p.sleeping);
                p.recover += if necessities {
                    if p.sleeping {
                        2.0
                    } else {
                        1.0
                    }
                } else if p.sleeping {
                    -0.5
                } else {
                    -1.0
                };
                if p.recover > 25.0 {
                    p.health = (p.health + 2.0).min(max_health(p));
                    p.recover = 0.0;
                }
                if p.recover < -15.0 {
                    p.health -= if p.level == NUM_LEVELS - 1 { 0.0 } else { 1.0 };
                    p.recover = 0.0;
                }
                p.recover_mana = (p.recover_mana + if p.sleeping { 2.0 } else { 1.0 })
                    * (1.0 + 0.25 * (p.intelligence as f64 - 1.0));
                if p.recover_mana > 30.0 {
                    p.mana = (p.mana + 1).min(max_mana(p));
                    p.recover_mana = 0.0;
                }
                if p.sleeping && p.energy >= max_energy(p) {
                    p.sleeping = false;
                    woke.push(player_index);
                }
                if p.resting && (p.health >= max_health(p) || p.food <= 0 || p.drink <= 0) {
                    p.resting = false;
                }
                if p.health <= 0.0 {
                    p.alive = false;
                    p.health = 0.0;
                }
            }
        }
        for index in woke {
            self.award("wake_up", &[index]);
        }
        self.calculate_inventory_achievements();
        if self.state.players.iter().all(|p| p.alive) {
            self.award(
                "all_roles_alive",
                &(0..self.state.players.len()).collect::<Vec<_>>(),
            );
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
        let base_reward = self
            .state
            .achievements_by_agent
            .iter()
            .map(|(agent, earned)| {
                earned
                    .difference(&before[agent])
                    .map(|name| achievement_reward(name))
                    .sum::<f64>()
            })
            .sum::<f64>()
            + 0.1 * (self.state.players.iter().map(|p| p.health).sum::<f64>() - before_health);
        if let Some(coord) = &mut self.state.alem_coord {
            coord.base_reward += base_reward;
        }
        let reward = base_reward + coord_step_reward;
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

    fn resolve_coord_sites(&mut self, actions: &BTreeMap<String, String>) -> f64 {
        let site_count = self
            .state
            .alem_coord
            .as_ref()
            .map(|coord| coord.sites.len())
            .unwrap_or(0);
        let mut reward = 0.0;
        for site_index in 0..site_count {
            let site = self.state.alem_coord.as_ref().unwrap().sites[site_index].clone();
            if ["sync_2", "sync_all"].contains(&site.kind.as_str()) && site.status == "open" {
                let actors = self
                    .state
                    .players
                    .iter()
                    .enumerate()
                    .filter_map(|(index, player)| {
                        (site.participants.contains(&player.agent_id)
                            && ["do", "attack"].contains(&actions[&player.agent_id].as_str())
                            && player.level == site.level
                            && self.front(index) == (site.x, site.y))
                            .then_some(index)
                    })
                    .collect::<Vec<_>>();
                if !actors.is_empty() {
                    if actors.len() != site.participants.len() {
                        reward += self.resolve_coord_site(
                            site_index,
                            false,
                            "coord_sync_fail",
                            BTreeMap::from([("reason".into(), json!("missing_participant"))]),
                        );
                    } else if actors
                        .iter()
                        .map(|index| self.soft_role_allowed(site_index, *index, site.required_role.as_deref()))
                        .collect::<Vec<_>>()
                        .into_iter()
                        .all(|success| success)
                    {
                        reward += self.resolve_coord_site(
                            site_index,
                            true,
                            "coord_sync_success",
                            BTreeMap::new(),
                        );
                    } else {
                        reward += self.resolve_coord_site(
                            site_index,
                            false,
                            "coord_sync_fail",
                            BTreeMap::from([("reason".into(), json!("soft_role_denied"))]),
                        );
                    }
                }
                continue;
            }
            if site.kind != "handover" {
                continue;
            }
            let provider = self
                .state
                .players
                .iter()
                .position(|player| player.agent_id == site.participants[0])
                .expect("handover provider exists");
            let receiver = self
                .state
                .players
                .iter()
                .position(|player| player.agent_id == site.participants[1])
                .expect("handover receiver exists");
            let provider_acts = self.state.players[provider].level == site.level
                && ["do", "attack"].contains(&actions[&site.participants[0]].as_str())
                && self.front(provider) == (site.x, site.y);
            let receiver_acts = self.state.players[receiver].level == site.level
                && ["do", "attack"].contains(&actions[&site.participants[1]].as_str())
                && self.front(receiver) == (site.x, site.y);
            if site.status == "open"
                && provider_acts
                && self.soft_role_allowed(site_index, provider, site.required_role.as_deref())
            {
                let resource = site.resource.as_ref().expect("handover resource");
                if self.state.players[provider].inventory[resource] > 0 {
                    *self.state.players[provider].inventory.get_mut(resource).unwrap() -= 1;
                    {
                        let current = &mut self.state.alem_coord.as_mut().unwrap().sites[site_index];
                        current.status = "opened".into();
                        current.opened_at = Some(self.state.timestep);
                    }
                    self.award("coord_handover_offer", &[provider]);
                    self.event_values(
                        "handover_opened",
                        BTreeMap::from([
                            ("giver".into(), json!(site.participants[0])),
                            ("receiver".into(), json!(site.participants[1])),
                            ("resource".into(), json!(resource)),
                            ("site_id".into(), json!(site.site_id)),
                            ("window".into(), json!(site.window)),
                        ]),
                    );
                }
            }
            let current = self.state.alem_coord.as_ref().unwrap().sites[site_index].clone();
            if current.status == "opened"
                && receiver_acts
                && self.soft_role_allowed(site_index, receiver, current.receiver_role.as_deref())
            {
                let resource = current.resource.as_ref().expect("handover resource");
                let amount = self.state.players[receiver].inventory[resource];
                *self.state.players[receiver].inventory.get_mut(resource).unwrap() = (amount + 1).min(99);
                reward += self.resolve_coord_site(
                    site_index,
                    true,
                    "handover_completed",
                    BTreeMap::from([
                        ("giver".into(), json!(site.participants[0])),
                        ("receiver".into(), json!(site.participants[1])),
                        ("resource".into(), json!(resource)),
                    ]),
                );
            } else if current.status == "opened"
                && current
                    .opened_at
                    .is_some_and(|opened_at| self.state.timestep - opened_at >= current.window)
            {
                reward += self.resolve_coord_site(
                    site_index,
                    false,
                    "handover_expired",
                    BTreeMap::from([
                        ("giver".into(), json!(site.participants[0])),
                        ("receiver".into(), json!(site.participants[1])),
                        ("resource".into(), json!(current.resource)),
                    ]),
                );
            }
        }
        reward
    }

    fn soft_role_allowed(&mut self, site_index: usize, player_index: usize, required_role: Option<&str>) -> bool {
        let Some(required_role) = required_role else {
            return true;
        };
        let site = self.state.alem_coord.as_ref().unwrap().sites[site_index].clone();
        let alpha_milli = self.state.alem_coord.as_ref().unwrap().alpha_milli;
        let player = &self.state.players[player_index];
        let role = player.role.clone();
        let roll = mix64(
            self.state.seed
                ^ self.state.timestep
                ^ ((site.site_index as u64) << 16)
                ^ player_index as u64,
        ) % 10_000;
        let success = role == required_role || roll < 10_000 - alpha_milli as u64 * 10;
        let agent_id = player.agent_id.clone();
        self.event_values(
            "soft_role_roll",
            BTreeMap::from([
                ("agent_id".into(), json!(agent_id)),
                ("alpha_milli".into(), json!(alpha_milli)),
                ("required_role".into(), json!(required_role)),
                ("roll".into(), json!(roll)),
                ("site_id".into(), json!(site.site_id)),
                ("success".into(), json!(success)),
            ]),
        );
        if success && role != required_role {
            self.award("coord_soft_role", &[player_index]);
        }
        success
    }

    fn resolve_coord_site(
        &mut self,
        site_index: usize,
        success: bool,
        event_kind: &str,
        mut fields: BTreeMap<String, Value>,
    ) -> f64 {
        let (site_id, kind) = {
            let coord = self.state.alem_coord.as_mut().expect("ALEM profile enabled");
            let site = &mut coord.sites[site_index];
            site.status = if success { "completed" } else { "failed" }.into();
            let metrics = coord.site_metrics.get_mut(&site.kind).expect("site metrics initialized");
            *metrics.get_mut("resolved").unwrap() += 1;
            if success {
                *metrics.get_mut("success").unwrap() += 1;
            }
            (site.site_id.clone(), site.kind.clone())
        };
        fields.insert("site_id".into(), json!(site_id));
        fields.insert("site_kind".into(), json!(kind));
        fields.insert("success".into(), json!(success));
        self.event_values(event_kind, fields);
        if !success {
            return 0.0;
        }
        let achievement = match kind.as_str() {
            "sync_2" => "coord_sync_2",
            "sync_all" => "coord_sync_all",
            "handover" => "coord_handover",
            _ => unreachable!("ALEM has only known site kinds"),
        };
        self.award(achievement, &(0..self.state.players.len()).collect::<Vec<_>>());
        let reward = match kind.as_str() {
            "sync_2" => 2.0,
            "sync_all" => 3.0,
            "handover" => 2.0,
            _ => unreachable!(),
        };
        self.state.alem_coord.as_mut().unwrap().coord_reward += reward;
        reward
    }

    pub fn alem_metrics(&self) -> Option<Value> {
        self.state.alem_coord.as_ref().map(|coord| {
            let success_rate = coord
                .site_metrics
                .iter()
                .map(|(kind, values)| {
                    let success = values["success"];
                    let resolved = values["resolved"];
                    (
                        kind.clone(),
                        json!({"success":success,"resolved":resolved,"rate":if resolved == 0 { 0.0 } else { success as f64 / resolved as f64 }}),
                    )
                })
                .collect::<BTreeMap<_, _>>();
            json!({"base_reward":coord.base_reward,"coord_reward":coord.coord_reward,"coord_success_rate":success_rate})
        })
    }

    fn award(&mut self, name: &str, recipients: &[usize]) {
        self.state.achievements.insert(name.into());
        for &index in recipients {
            self.state
                .achievements_by_agent
                .get_mut(&self.state.players[index].agent_id)
                .unwrap()
                .insert(name.into());
        }
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
                self.state.players[index].resting =
                    self.state.players[index].health < max_health(&self.state.players[index]);
            }
            "sleep" => {
                self.state.players[index].sleeping =
                    self.state.players[index].energy < max_energy(&self.state.players[index])
            }
            "cast_spell" => self.cast_spell(index),
            "shoot_arrow" => self.shoot_arrow(index),
            "descend" | "ascend" => {}
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

    fn resolve_joint_do(&mut self, actions: &BTreeMap<String, String>) {
        let mut groups: BTreeMap<(usize, usize, usize), Vec<usize>> = BTreeMap::new();
        for (index, player) in self.state.players.iter().enumerate() {
            if ["do", "attack"].contains(&actions[&player.agent_id].as_str()) {
                let (x, y) = self.front(index);
                groups.entry((player.level, x, y)).or_default().push(index);
            }
        }
        for ((level, x, y), players) in groups {
            if players.len() == 1 {
                self.do_action(players[0]);
                continue;
            }
            let tile = self.state.maps[level][y][x].clone();
            if let Some(target) = (0..self.state.players.len()).find(|i| {
                !players.contains(i)
                    && self.state.players[*i].level == level
                    && (self.state.players[*i].x, self.state.players[*i].y) == (x, y)
            }) {
                if !self.state.players[target].alive {
                    self.state.players[target].health = 1.0;
                    self.state.players[target].alive = true;
                    self.state.revives += 1;
                } else {
                    let sleeping = self.state.players[target].sleeping;
                    let damage = players
                        .iter()
                        .map(|i| {
                            Self::damage(
                                Self::player_damage_vector(&self.state.players[*i]),
                                Self::defense_vector(&self.state.players[target]),
                            ) * if sleeping { 3.5 } else { 1.0 }
                        })
                        .sum::<f64>();
                    self.state.players[target].health -= damage;
                    self.state.ff_damage_dealt += damage;
                }
                continue;
            }
            if let Some(mi) = self
                .state
                .monsters
                .iter()
                .position(|m| m.level == level && (m.x, m.y) == (x, y))
            {
                let damage = players
                    .iter()
                    .map(|i| {
                        Self::damage_to_mob(
                            Self::player_damage_vector(&self.state.players[*i]),
                            &self.state.monsters[mi],
                        )
                    })
                    .sum::<f64>();
                self.state.monsters[mi].health -= damage;
                if self.state.monsters[mi].health <= 0.0 {
                    let monster = self.state.monsters.remove(mi);
                    if monster.category != "passive" {
                        self.state.monsters_killed[level] += 1;
                    }
                    for &index in &players {
                        if monster.category == "passive"
                            && self.state.players[index].role == "forager"
                        {
                            self.state.players[index].food = (self.state.players[index].food + 6)
                                .min(max_food(&self.state.players[index]));
                            self.state.players[index].hunger = 0.0;
                        }
                        if monster.category != "passive"
                            || self.state.players[index].role == "forager"
                        {
                            if let Some(name) = kill_achievement(&monster.kind) {
                                self.award(name, &[index]);
                            }
                        }
                    }
                }
                continue;
            }
            let resource = match tile.as_str() {
                "tree" => Some(("wood", 0, "grass")),
                "fire_tree" => Some(("wood", 0, "fire_grass")),
                "ice_shrub" => Some(("wood", 0, "ice_grass")),
                "stone" => Some(("stone", 1, "path")),
                "stalagmite" => Some(("stone", 1, "path")),
                "coal" => Some(("coal", 1, "path")),
                "iron" => Some(("iron", 2, "path")),
                "diamond" => Some(("diamond", 3, "path")),
                "ruby" => Some(("ruby", 4, "path")),
                "sapphire" => Some(("sapphire", 4, "path")),
                _ => None,
            };
            if let Some((resource, tier, replacement)) = resource {
                for &index in &players {
                    if self.state.players[index].pickaxe >= tier {
                        let stock = self.state.players[index]
                            .inventory
                            .get_mut(resource)
                            .unwrap();
                        *stock = (*stock + 1).min(99);
                        self.award(&format!("collect_{resource}"), &[index]);
                    }
                }
                self.state.maps[level][y][x] = replacement.into();
                continue;
            }
            if tile == "chest" {
                for &index in &players {
                    self.loot_chest(index);
                    self.state.chests_opened[level][index] = true;
                    self.award("open_chest", &[index]);
                }
                self.state.maps[level][y][x] = "path".into();
                continue;
            }
            if tile == "ripe_plant" {
                for &index in &players {
                    self.state.players[index].food = (self.state.players[index].food + 4)
                        .min(max_food(&self.state.players[index]));
                    self.state.players[index].hunger = 0.0;
                    self.award("eat_plant", &[index]);
                }
                self.state.maps[level][y][x] = "plant".into();
                continue;
            }
            for index in players {
                self.do_action(index);
            }
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
        if let Some(target) = self.state.players.iter().position(|player| {
            player.agent_id != self.state.players[index].agent_id
                && player.level == level
                && player.x == x
                && player.y == y
        }) {
            if !self.state.players[target].alive {
                self.state.players[target].health = 1.0;
                self.state.players[target].alive = true;
                self.state.revives += 1;
                self.event_values(
                    "player_revived",
                    BTreeMap::from([
                        (
                            "agent_id".into(),
                            json!(self.state.players[target].agent_id),
                        ),
                        ("by".into(), json!(self.state.players[index].agent_id)),
                    ]),
                );
            } else {
                let damage = Self::damage(
                    Self::player_damage_vector(&self.state.players[index]),
                    Self::defense_vector(&self.state.players[target]),
                ) * if self.state.players[target].sleeping {
                    3.5
                } else {
                    1.0
                };
                self.state.players[target].health -= damage;
                self.state.ff_damage_dealt += damage;
                self.event_values(
                    "friendly_fire",
                    BTreeMap::from([
                        ("attacker".into(), json!(self.state.players[index].agent_id)),
                        ("damage".into(), json!(damage)),
                        ("target".into(), json!(self.state.players[target].agent_id)),
                    ]),
                );
            }
            return;
        }
        let resource = match tile.as_str() {
            "tree" => Some(("wood", "grass")),
            "fire_tree" => Some(("wood", "fire_grass")),
            "ice_shrub" => Some(("wood", "ice_grass")),
            "stone" | "stalagmite" => Some(("stone", "path")),
            "coal" => Some(("coal", "path")),
            "iron" => Some(("iron", "path")),
            "diamond" => Some(("diamond", "path")),
            "ruby" => Some(("ruby", "path")),
            "sapphire" => Some(("sapphire", "path")),
            _ => None,
        };
        if let Some((resource, replacement)) = resource {
            let required = match resource {
                "stone" | "coal" => 1,
                "iron" => 2,
                "diamond" => 3,
                "ruby" | "sapphire" => 4,
                _ => 0,
            };
            if self.state.players[index].pickaxe < required {
                return;
            }
            let amount = 1;
            *self.state.players[index]
                .inventory
                .get_mut(resource)
                .unwrap() = (self.state.players[index].inventory[resource] + amount).min(99);
            self.state.maps[level][y][x] = replacement.into();
            self.award(&format!("collect_{resource}"), &[index]);
            self.event_values(
                "resource_collected",
                BTreeMap::from([
                    ("agent_id".into(), json!(self.state.players[index].agent_id)),
                    ("amount".into(), json!(amount)),
                    ("resource".into(), json!(resource)),
                ]),
            );
            return;
        }
        if ["crafting_table", "furnace"].contains(&tile.as_str()) {
            self.state.maps[level][y][x] = "path".into();
            return;
        }
        if tile == "grass"
            && self.state.players[index].role == "forager"
            && mix64(self.state.seed ^ self.state.timestep ^ index as u64) % 5 == 0
        {
            self.state.players[index].saplings += 1;
            self.award("collect_sapling", &[index]);
            return;
        }
        if tile == "ripe_plant" {
            self.state.players[index].food =
                (self.state.players[index].food + 4).min(max_food(&self.state.players[index]));
            self.state.players[index].hunger = 0.0;
            self.state.maps[level][y][x] = "plant".into();
            if let Some(plant) = self
                .state
                .plants
                .iter_mut()
                .find(|plant| (plant.level, plant.x, plant.y) == (level, x, y))
            {
                plant.age = 0;
            }
            self.award("eat_plant", &[index]);
            self.event_values(
                "plant_eaten",
                BTreeMap::from([("agent_id".into(), json!(self.state.players[index].agent_id))]),
            );
            return;
        }
        if tile == "fountain" || tile == "water" {
            if self.state.players[index].role != "forager" {
                return;
            }
            let amount = 4;
            self.state.players[index].drink = (self.state.players[index].drink + amount)
                .min(max_drink(&self.state.players[index]));
            self.award("collect_drink", &[index]);
            self.event_values(
                if tile == "fountain" {
                    "fountain_used"
                } else {
                    "water_drunk"
                },
                BTreeMap::from([("agent_id".into(), json!(self.state.players[index].agent_id))]),
            );
            return;
        }
        if tile == "chest" {
            self.state.maps[level][y][x] = "path".into();
            self.loot_chest(index);
            self.state.chests_opened[level][index] = true;
            self.award("open_chest", &[index]);
            self.event_values(
                "chest_opened",
                BTreeMap::from([("agent_id".into(), json!(self.state.players[index].agent_id))]),
            );
            return;
        }
        if let Some(mi) = self
            .state
            .monsters
            .iter()
            .position(|m| m.level == level && m.x == x && m.y == y)
        {
            let damage = Self::damage_to_mob(
                Self::player_damage_vector(&self.state.players[index]),
                &self.state.monsters[mi],
            );
            self.state.monsters[mi].health -= damage;
            let mob_id = self.state.monsters[mi].id.clone();
            self.event_values(
                "mob_damaged",
                BTreeMap::from([
                    ("agent_id".into(), json!(self.state.players[index].agent_id)),
                    ("damage".into(), json!(damage)),
                    ("mob_id".into(), json!(mob_id)),
                ]),
            );
            if self.state.monsters[mi].health <= 0.0 {
                let monster = self.state.monsters.remove(mi);
                if monster.category != "passive" {
                    self.state.monsters_killed[level] += 1;
                }
                if monster.category == "passive" && self.state.players[index].role == "forager" {
                    self.state.players[index].food = (self.state.players[index].food + 6)
                        .min(max_food(&self.state.players[index]));
                    self.state.players[index].hunger = 0.0;
                }
                if monster.category != "passive" || self.state.players[index].role == "forager" {
                    if let Some(achievement) = kill_achievement(&monster.kind) {
                        self.award(achievement, &[index]);
                    }
                }
                self.event_values(
                    "mob_defeated",
                    BTreeMap::from([
                        ("agent_id".into(), json!(self.state.players[index].agent_id)),
                        ("mob_id".into(), json!(monster.id)),
                    ]),
                );
            }
            return;
        }
        if ["boss", "necromancer", "necromancer_vulnerable"].contains(&tile.as_str())
            && level == NUM_LEVELS - 1
            && self.state.boss_wave_timer == 0
            && !self.state.monsters.iter().any(|mob| mob.level == level)
        {
            self.state.boss_progress += 1;
            self.state.boss_health =
                (NUM_LEVELS as i16 - 1 - self.state.boss_progress as i16).max(0);
            self.state.boss_wave_timer = 7;
            self.state.maps[level][y][x] = "necromancer".into();
            self.award("damage_necromancer", &[index]);
            self.event_values(
                "boss_damaged",
                BTreeMap::from([
                    ("agent_id".into(), json!(self.state.players[index].agent_id)),
                    ("damage".into(), json!(1)),
                    ("remaining".into(), json!(self.state.boss_health)),
                ]),
            );
            if self.state.boss_progress >= NUM_LEVELS - 1 {
                self.award("defeat_necromancer", &[index]);
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
                    .any(|p| p.level == self.state.players[i].level && (p.x, p.y) == pos)
                    && !self
                        .state
                        .monsters
                        .iter()
                        .any(|m| m.level == self.state.players[i].level && (m.x, m.y) == pos);
                if unique && free {
                    self.state.players[i].x = pos.0;
                    self.state.players[i].y = pos.1;
                    self.event_values(
                        "move_applied",
                        BTreeMap::from([
                            ("agent_id".into(), json!(self.state.players[i].agent_id)),
                            ("level".into(), json!(self.state.players[i].level)),
                            ("x".into(), json!(pos.0)),
                            ("y".into(), json!(pos.1)),
                        ]),
                    );
                }
            }
        }
    }
    fn craft(&mut self, i: usize, action: &str) {
        let table = self.near(i, "crafting_table");
        let furnace = self.near(i, "furnace");
        if action == "make_arrow" {
            if self.state.players[i].role != "warrior"
                || !table
                || !self.has(i, &[("wood", 1), ("stone", 1)])
            {
                return;
            }
            self.spend(i, &[("wood", 1), ("stone", 1)]);
            self.state.players[i].arrows += 2;
        } else if action == "make_torch" {
            if self.state.players[i].role != "miner"
                || !table
                || !self.has(i, &[("wood", 1), ("coal", 1)])
            {
                return;
            }
            self.spend(i, &[("wood", 1), ("coal", 1)]);
            self.state.players[i].torches += 4;
        } else if ["make_iron_armour", "make_diamond_armour"].contains(&action) {
            let tier = if action == "make_iron_armour" { 1 } else { 2 };
            let costs = if tier == 1 {
                vec![("iron", 3), ("coal", 3)]
            } else {
                vec![("diamond", 3)]
            };
            if !table
                || (tier == 1 && !furnace)
                || !self.has(i, &costs)
                || !self.state.players[i]
                    .armour_slots
                    .iter()
                    .any(|slot| *slot < tier)
            {
                return;
            }
            self.spend(i, &costs);
            let slot = self.state.players[i]
                .armour_slots
                .iter()
                .position(|value| *value < tier)
                .unwrap();
            self.state.players[i].armour_slots[slot] = tier;
            self.state.players[i].armour =
                *self.state.players[i].armour_slots.iter().max().unwrap();
        } else {
            let (costs, item, tier, role, needs_furnace) = match action {
                "make_wood_pickaxe" => (vec![("wood", 1)], "pickaxe", 1, Some("miner"), false),
                "make_stone_pickaxe" => (
                    vec![("wood", 1), ("stone", 1)],
                    "pickaxe",
                    2,
                    Some("miner"),
                    false,
                ),
                "make_iron_pickaxe" => (
                    vec![("wood", 1), ("stone", 1), ("iron", 1), ("coal", 1)],
                    "pickaxe",
                    3,
                    Some("miner"),
                    true,
                ),
                "make_diamond_pickaxe" => (
                    vec![("wood", 1), ("diamond", 3)],
                    "pickaxe",
                    4,
                    Some("miner"),
                    false,
                ),
                "make_wood_sword" => (vec![("wood", 1)], "sword", 1, None, false),
                "make_stone_sword" => (
                    vec![("wood", 1), ("stone", 1)],
                    "sword",
                    2,
                    Some("warrior"),
                    false,
                ),
                "make_iron_sword" => (
                    vec![("wood", 1), ("stone", 1), ("iron", 1), ("coal", 1)],
                    "sword",
                    3,
                    Some("warrior"),
                    true,
                ),
                "make_diamond_sword" => (
                    vec![("wood", 1), ("diamond", 2)],
                    "sword",
                    4,
                    Some("warrior"),
                    false,
                ),
                _ => return,
            };
            let current = if item == "pickaxe" {
                self.state.players[i].pickaxe
            } else {
                self.state.players[i].sword
            };
            if !table
                || (needs_furnace && !furnace)
                || role.is_some_and(|role| self.state.players[i].role != role)
                || current >= tier
                || !self.has(i, &costs)
            {
                return;
            }
            self.spend(i, &costs);
            if item == "pickaxe" {
                self.state.players[i].pickaxe = tier
            } else {
                self.state.players[i].sword = tier
            }
        }
        self.award(action, &[i]);
        self.event_values(
            "item_crafted",
            BTreeMap::from([
                ("agent_id".into(), json!(self.state.players[i].agent_id)),
                (
                    "item".into(),
                    json!(action.strip_prefix("make_").unwrap_or(action)),
                ),
            ]),
        );
    }
    fn near(&self, i: usize, tile: &str) -> bool {
        let p = &self.state.players[i];
        (-1..=1).any(|dx| {
            (-1..=1).any(|dy| {
                if dx == 0 && dy == 0 {
                    return false;
                }
                let x = p.x as isize + dx;
                let y = p.y as isize + dy;
                x >= 0
                    && y >= 0
                    && x < MAP_SIZE as isize
                    && y < MAP_SIZE as isize
                    && self.state.maps[p.level][y as usize][x as usize] == tile
            })
        })
    }
    fn has(&self, i: usize, costs: &[(&str, u16)]) -> bool {
        costs
            .iter()
            .all(|(resource, amount)| self.state.players[i].inventory[*resource] >= *amount)
    }
    fn spend(&mut self, i: usize, costs: &[(&str, u16)]) {
        for (resource, amount) in costs {
            *self.state.players[i].inventory.get_mut(*resource).unwrap() -= *amount;
        }
    }
    fn place(&mut self, i: usize, action: &str) {
        if action == "place_plant" || action == "place_torch" {
            let (x, y) = self.front(i);
            let level = self.state.players[i].level;
            let valid = if action == "place_plant" {
                vec!["grass"]
            } else {
                vec!["grass", "path", "sand", "gravel", "fire_grass", "ice_grass"]
            };
            if !valid.contains(&self.state.maps[level][y][x].as_str())
                || self.state.item_maps[level][y][x].is_some()
                || self
                    .state
                    .players
                    .iter()
                    .any(|p| p.alive && p.level == level && p.x == x && p.y == y)
                || self
                    .state
                    .monsters
                    .iter()
                    .any(|m| m.level == level && m.x == x && m.y == y)
            {
                return;
            }
            if action == "place_plant" && self.state.players[i].saplings > 0 {
                self.state.players[i].saplings -= 1;
                self.state.maps[level][y][x] = "plant".into();
                self.state.plants.push(Plant {
                    level,
                    x,
                    y,
                    age: 0,
                });
                self.award("place_plant", &[i]);
                self.event_values(
                    "block_placed",
                    BTreeMap::from([
                        ("agent_id".into(), json!(self.state.players[i].agent_id)),
                        ("tile".into(), json!("plant")),
                        ("x".into(), json!(x)),
                        ("y".into(), json!(y)),
                    ]),
                );
            }
            if action == "place_torch" && self.state.players[i].torches > 0 {
                self.state.players[i].torches -= 1;
                self.state.item_maps[level][y][x] = Some("torch".into());
                for yy in y.saturating_sub(4)..(y + 5).min(MAP_SIZE) {
                    for xx in x.saturating_sub(4)..(x + 5).min(MAP_SIZE) {
                        let light = (1.0 - (xx.abs_diff(x) + yy.abs_diff(y)) as f64 / 6.0).max(0.0);
                        self.state.light_maps[level][yy][xx] =
                            self.state.light_maps[level][yy][xx].max(light);
                    }
                }
                self.award("place_torch", &[i]);
                self.event_values(
                    "block_placed",
                    BTreeMap::from([
                        ("agent_id".into(), json!(self.state.players[i].agent_id)),
                        ("tile".into(), json!(self.state.maps[level][y][x])),
                        ("x".into(), json!(x)),
                        ("y".into(), json!(y)),
                    ]),
                );
            }
            return;
        }
        let Some((resource, cost, tile)) = (match action {
            "place_stone" => Some(("stone", 1, "stone")),
            "place_table" => Some(("wood", 2, "crafting_table")),
            "place_furnace" => Some(("stone", 1, "furnace")),
            _ => None,
        }) else {
            return;
        };
        let (x, y) = self.front(i);
        let level = self.state.players[i].level;
        let valid = if action == "place_stone" {
            vec![
                "grass",
                "path",
                "sand",
                "gravel",
                "fire_grass",
                "ice_grass",
                "water",
            ]
        } else {
            vec!["grass", "path", "sand", "gravel", "fire_grass", "ice_grass"]
        };
        if !valid.contains(&self.state.maps[level][y][x].as_str())
            || self.state.players[i].inventory[resource] < cost
            || self.state.item_maps[level][y][x].is_some()
            || (action == "place_stone" && self.state.players[i].role != "miner")
            || self
                .state
                .players
                .iter()
                .any(|p| p.alive && p.level == level && p.x == x && p.y == y)
            || self
                .state
                .monsters
                .iter()
                .any(|m| m.level == level && m.x == x && m.y == y)
        {
            return;
        }
        *self.state.players[i].inventory.get_mut(resource).unwrap() -= cost;
        self.state.maps[level][y][x] = tile.into();
        if action == "place_table" || action == "place_furnace" {
            self.award(action, &[i]);
        }
        self.event_values(
            "block_placed",
            BTreeMap::from([
                ("agent_id".into(), json!(self.state.players[i].agent_id)),
                ("tile".into(), json!(tile)),
                ("x".into(), json!(x)),
                ("y".into(), json!(y)),
            ]),
        );
    }
    fn shoot_arrow(&mut self, i: usize) {
        if self.state.players[i].arrows == 0
            || self.state.players[i].bow == 0
            || self.state.projectiles.iter().filter(|p| !p.hostile).count()
                >= self.state.players.len() * 3
        {
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
            damage: 5 + p.dexterity as i16,
            ttl: MAP_SIZE as u8,
            kind: "arrow2".into(),
            hostile: false,
        });
        self.award("fire_bow", &[i]);
        self.event_values(
            "arrow_shot",
            BTreeMap::from([("agent_id".into(), json!(self.state.players[i].agent_id))]),
        );
    }
    fn drink_potion(&mut self, i: usize, colour: &str) {
        if !self.state.players[i].potions.contains_key(colour)
            || self.state.players[i].potions[colour] == 0
        {
            return;
        }
        *self.state.players[i].potions.get_mut(colour).unwrap() -= 1;
        let colours = ["red", "green", "blue", "pink", "cyan", "yellow"];
        let effect = self.state.potion_mapping
            [colours.iter().position(|value| *value == colour).unwrap()]
        .as_str();
        match effect {
            "health" => {
                self.state.players[i].health =
                    (self.state.players[i].health + 8.0).min(max_health(&self.state.players[i]))
            }
            "harm" => self.state.players[i].health -= 3.0,
            "mana" => {
                self.state.players[i].mana =
                    (self.state.players[i].mana + 8).min(max_mana(&self.state.players[i]))
            }
            "drain_mana" => self.state.players[i].mana = (self.state.players[i].mana - 3).max(0),
            "energy" => self.state.players[i].energy = (self.state.players[i].energy + 8).min(9),
            _ => self.state.players[i].energy = (self.state.players[i].energy - 3).max(0),
        }
        self.award("drink_potion", &[i]);
        self.event_values(
            "potion_drunk",
            BTreeMap::from([
                ("agent_id".into(), json!(self.state.players[i].agent_id)),
                ("colour".into(), json!(colour)),
            ]),
        );
    }
    fn read_book(&mut self, i: usize) {
        if self.state.players[i].books == 0 {
            return;
        }
        self.state.players[i].books -= 1;
        self.state.players[i].learned_spell = true;
        self.award("learn_spell", &[i]);
        self.event_values(
            "book_read",
            BTreeMap::from([("agent_id".into(), json!(self.state.players[i].agent_id))]),
        );
    }
    fn level_up(&mut self, i: usize, attribute: &str) {
        if self.state.players[i].xp == 0 {
            return;
        }
        match attribute {
            "dexterity" if self.state.players[i].dexterity < 5 => {
                self.state.players[i].dexterity += 1
            }
            "strength" if self.state.players[i].strength < 5 => self.state.players[i].strength += 1,
            "intelligence" if self.state.players[i].intelligence < 5 => {
                self.state.players[i].intelligence += 1
            }
            _ => return,
        }
        self.state.players[i].xp -= 1;
        self.award("level_up", &[i]);
        self.event_values(
            "attribute_leveled",
            BTreeMap::from([
                ("agent_id".into(), json!(self.state.players[i].agent_id)),
                ("attribute".into(), json!(attribute)),
            ]),
        );
    }
    fn enchant(&mut self, i: usize, item: &str) {
        if !["sword", "armour", "bow"].contains(&item) {
            return;
        }
        let (x, y) = self.front(i);
        let table = self.state.maps[self.state.players[i].level][y][x].as_str();
        let (element, gem) = match table {
            "enchantment_table_fire" => ("fire", "ruby"),
            "enchantment_table_ice" => ("ice", "sapphire"),
            _ => return,
        };
        if self.state.players[i].mana < 9
            || self.state.players[i].inventory[gem] == 0
            || (["sword", "bow"].contains(&item) && self.state.players[i].role != "warrior")
            || (item == "sword" && self.state.players[i].sword == 0)
            || (item == "bow" && self.state.players[i].bow == 0)
            || (item == "armour"
                && !self.state.players[i]
                    .armour_slots
                    .iter()
                    .any(|tier| *tier > 0))
        {
            return;
        }
        let value = Some(element.into());
        match item {
            "sword" => self.state.players[i].sword_enchantment = value,
            "armour" => {
                let Some(slot) = self.state.players[i]
                    .armour_enchantments
                    .iter()
                    .position(Option::is_none)
                    .or_else(|| {
                        self.state.players[i]
                            .armour_enchantments
                            .iter()
                            .position(|current| current.as_deref() != Some(element))
                    })
                else {
                    return;
                };
                self.state.players[i].armour_enchantments[slot] = value.clone();
                self.state.players[i].armour_enchantment = value;
            }
            _ => self.state.players[i].bow_enchantment = value,
        }
        *self.state.players[i].inventory.get_mut(gem).unwrap() -= 1;
        self.state.players[i].mana -= 9;
        if item == "sword" {
            self.award("enchant_sword", &[i]);
        }
        if item == "armour" {
            self.award("enchant_armour", &[i]);
        }
        self.event_values(
            "item_enchanted",
            BTreeMap::from([
                ("agent_id".into(), json!(self.state.players[i].agent_id)),
                ("element".into(), json!(element)),
                ("item".into(), json!(item)),
            ]),
        );
    }
    fn change_floor(&mut self, i: usize, direction: isize) {
        let p = &self.state.players[i];
        let required = if direction > 0 {
            "stairs_down"
        } else {
            "stairs_up"
        };
        if self.state.maps[p.level][p.y][p.x] != required
            || (direction > 0 && self.state.monsters_killed[p.level] < 8)
        {
            return;
        }
        let next = p.level as isize + direction;
        if !(0..NUM_LEVELS as isize).contains(&next) {
            return;
        }
        let next = next as usize;
        let first = direction > 0
            && level_achievement(next)
                .is_some_and(|achievement| !self.state.achievements.contains(achievement));
        let destinations = if direction < 0 {
            self.state.ladders_down[next].clone()
        } else {
            self.state.ladders_up[next].clone()
        };
        for (index, player) in self.state.players.iter_mut().enumerate() {
            player.level = next;
            (player.x, player.y) = destinations[index];
            if first {
                player.xp += 1;
            }
        }
        if direction > 0 {
            if let Some(achievement) = level_achievement(next) {
                self.award(
                    achievement,
                    &(0..self.state.players.len()).collect::<Vec<_>>(),
                );
            }
        }
        self.event_values(
            "level_changed",
            BTreeMap::from([
                ("agent_id".into(), json!(self.state.players[i].agent_id)),
                ("level".into(), json!(next)),
            ]),
        );
    }
    fn resolve_floor_actions(&mut self, actions: &BTreeMap<String, String>) {
        if let Some(i) = self
            .state
            .players
            .iter()
            .position(|p| actions[&p.agent_id] == "descend")
        {
            self.change_floor(i, 1);
            return;
        }
        if let Some(i) = self
            .state
            .players
            .iter()
            .position(|p| actions[&p.agent_id] == "ascend")
        {
            self.change_floor(i, -1);
        }
    }
    fn player_damage_vector(player: &Player) -> [f64; 3] {
        let base = [1.0, 2.0, 3.0, 5.0, 8.0][player.sword as usize]
            * if player.role == "warrior" { 2.0 } else { 1.0 };
        let physical = base * (1.0 + 0.25 * (player.strength as f64 - 1.0));
        let element = base * 0.5 * (1.0 + 0.05 * (player.intelligence as f64 - 1.0));
        [
            physical,
            if player.sword_enchantment.as_deref() == Some("fire") {
                element
            } else {
                0.0
            },
            if player.sword_enchantment.as_deref() == Some("ice") {
                element
            } else {
                0.0
            },
        ]
    }
    fn defense_vector(player: &Player) -> [f64; 3] {
        [
            player.armour_slots.iter().map(|v| *v as f64 * 0.1).sum(),
            player
                .armour_enchantments
                .iter()
                .filter(|v| v.as_deref() == Some("fire"))
                .count() as f64
                * 0.2,
            player
                .armour_enchantments
                .iter()
                .filter(|v| v.as_deref() == Some("ice"))
                .count() as f64
                * 0.2,
        ]
    }
    fn damage(vector: [f64; 3], defense: [f64; 3]) -> f64 {
        (0..3).map(|i| (1.0 - defense[i]) * vector[i]).sum()
    }
    fn damage_to_mob(vector: [f64; 3], mob: &Monster) -> f64 {
        let physical = if mob.level == 4 {
            0.5
        } else if mob.level == 5 && mob.category == "melee" {
            0.2
        } else if [6, 7].contains(&mob.level) {
            0.9
        } else {
            0.0
        };
        Self::damage(
            vector,
            [
                physical,
                if mob.level == 6 { 1.0 } else { 0.0 },
                if mob.level == 7 { 1.0 } else { 0.0 },
            ],
        )
        .max(0.0)
    }
    fn incoming(vector: [f64; 3], player: &Player, boss: bool) -> f64 {
        (Self::damage(vector, Self::defense_vector(player)) * if boss { 1.5 } else { 1.0 }).max(0.0)
    }
    fn player_projectile_vector(&self, shot: &Projectile) -> [f64; 3] {
        let Some(owner) = self.state.players.iter().find(|p| p.agent_id == shot.owner) else {
            return projectile_vector(&shot.kind);
        };
        if shot.kind == "arrow2" {
            let physical = 5.0 * (1.0 + 0.2 * (owner.dexterity as f64 - 1.0));
            [
                physical,
                if owner.bow_enchantment.as_deref() == Some("fire") {
                    2.5
                } else {
                    0.0
                },
                if owner.bow_enchantment.as_deref() == Some("ice") {
                    2.5
                } else {
                    0.0
                },
            ]
        } else if shot.kind == "fireball" {
            [
                0.0,
                3.0 * (1.0 + 0.5 * (owner.intelligence as f64 - 1.0)),
                0.0,
            ]
        } else {
            projectile_vector(&shot.kind)
        }
    }
    fn loot_chest(&mut self, i: usize) {
        let level = self.state.players[i].level;
        let agent_sum = self.state.players[i]
            .agent_id
            .bytes()
            .map(u64::from)
            .sum::<u64>();
        let value = mix64(
            self.state.seed ^ (self.state.timestep << 17) ^ ((level as u64) << 9) ^ agent_sum,
        );
        if self.state.players[i].role == "miner" && value % 10 < 6 {
            *self.state.players[i].inventory.get_mut("wood").unwrap() += 1 + (value % 5) as u16;
            self.state.players[i].torches += 4 + ((value / 7) % 4) as u16;
            let ore = ["coal", "iron", "diamond", "sapphire", "ruby"][((value / 11) % 5) as usize];
            let span = if ore == "coal" { 3 } else { 2 };
            *self.state.players[i].inventory.get_mut(ore).unwrap() +=
                1 + ((value / 13) % span) as u16;
            self.state.players[i].pickaxe = self.state.players[i]
                .pickaxe
                .max(1 + ((value / 17) % 4) as u8);
        }
        let colour =
            ["red", "green", "blue", "pink", "cyan", "yellow"][((value / 19) % 6) as usize];
        if (value / 23) % 2 == 0 {
            *self.state.players[i].potions.get_mut(colour).unwrap() +=
                1 + ((value / 29) % 2) as u16;
        }
        let opened = self.state.chests_opened[level][i];
        if self.state.players[i].role == "warrior" {
            if (value / 31) % 2 == 0 {
                self.state.players[i].arrows += 4 + ((value / 37) % 5) as u16;
            }
            if level == 1 && !opened {
                self.state.players[i].bow = self.state.players[i].bow.max(1);
                self.award("find_bow", &[i]);
            }
        }
        if [3, 4].contains(&level) && !opened {
            self.state.players[i].books += 1;
        }
    }
    fn cast_spell(&mut self, i: usize) {
        if !self.state.players[i].learned_spell {
            return;
        }
        if self.state.players[i].role == "forager" && self.state.players[i].mana >= 6 {
            self.state.players[i].mana -= 6;
            for player in &mut self.state.players {
                if player.alive {
                    player.health = (player.health + 2.0).min(max_health(player));
                }
            }
            self.award("cast_spell", &[i]);
            self.event_values(
                "spell_cast",
                BTreeMap::from([
                    ("agent_id".into(), json!(self.state.players[i].agent_id)),
                    ("spell".into(), json!("heal")),
                ]),
            );
        } else if ["warrior", "miner"].contains(&self.state.players[i].role.as_str())
            && self.state.players[i].mana >= 2
            && self.state.projectiles.iter().filter(|p| !p.hostile).count()
                < self.state.players.len() * 3
        {
            self.state.players[i].mana -= 2;
            let p = &self.state.players[i];
            let (dx, dy) = direction(&p.facing);
            let damage = (3.0 * (1.0 + 0.5 * (p.intelligence as f64 - 1.0)))
                .round()
                .max(1.0) as i16;
            self.state.projectiles.push(Projectile {
                owner: p.agent_id.clone(),
                level: p.level,
                x: p.x as isize,
                y: p.y as isize,
                dx,
                dy,
                damage,
                ttl: MAP_SIZE as u8,
                kind: "fireball".into(),
                hostile: false,
            });
            self.award("cast_spell", &[i]);
            self.event_values(
                "spell_cast",
                BTreeMap::from([
                    ("agent_id".into(), json!(self.state.players[i].agent_id)),
                    ("spell".into(), json!("fireball")),
                ]),
            );
        }
    }
    fn update_projectiles(&mut self) {
        let mut remaining = Vec::new();
        let shots = std::mem::take(&mut self.state.projectiles);
        for mut shot in shots {
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
            let tile = self.state.maps[shot.level][shot.y as usize][shot.x as usize].as_str();
            if ["crafting_table", "furnace"].contains(&tile) && shot.hostile {
                self.state.maps[shot.level][shot.y as usize][shot.x as usize] = "path".into();
                continue;
            }
            if [
                "stone",
                "wall",
                "water",
                "tree",
                "coal",
                "iron",
                "diamond",
                "ruby",
                "sapphire",
                "stalagmite",
                "fire_tree",
                "ice_shrub",
            ]
            .contains(&tile)
            {
                continue;
            }
            if shot.hostile {
                if let Some(pi) = self.state.players.iter().position(|p| {
                    p.alive
                        && p.level == shot.level
                        && p.x == shot.x as usize
                        && p.y == shot.y as usize
                }) {
                    let damage = Self::incoming(
                        projectile_vector(&shot.kind),
                        &self.state.players[pi],
                        shot.level == NUM_LEVELS - 1,
                    );
                    self.state.players[pi].health -= damage;
                    self.state.players[pi].sleeping = false;
                    self.state.players[pi].resting = false;
                    continue;
                }
            } else if let Some(pi) = self.state.players.iter().position(|p| {
                p.alive
                    && p.agent_id != shot.owner
                    && p.level == shot.level
                    && p.x == shot.x as usize
                    && p.y == shot.y as usize
            }) {
                let damage = Self::incoming(
                    self.player_projectile_vector(&shot),
                    &self.state.players[pi],
                    false,
                );
                self.state.players[pi].health -= damage;
                self.state.players[pi].sleeping = false;
                self.state.players[pi].resting = false;
                self.state.ff_damage_dealt += damage as f64;
                continue;
            }
            if let Some(mi) = self.state.monsters.iter().position(|m| {
                !shot.hostile
                    && m.level == shot.level
                    && m.x == shot.x as usize
                    && m.y == shot.y as usize
            }) {
                let damage = Self::damage_to_mob(
                    self.player_projectile_vector(&shot),
                    &self.state.monsters[mi],
                );
                self.state.monsters[mi].health -= damage;
                if self.state.monsters[mi].health <= 0.0 {
                    let monster = self.state.monsters.remove(mi);
                    if monster.category != "passive" {
                        self.state.monsters_killed[monster.level] += 1;
                    }
                    if let Some(owner) = self
                        .state
                        .players
                        .iter()
                        .position(|p| p.agent_id == shot.owner)
                    {
                        if let Some(achievement) = kill_achievement(&monster.kind) {
                            self.award(achievement, &[owner]);
                        }
                    }
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
            let category = self.state.monsters[mi].category.clone();
            if category == "passive" {
                let target_x = self.state.players[pi].x;
                let target_y = self.state.players[pi].y;
                let mob_x = self.state.monsters[mi].x;
                let mob_y = self.state.monsters[mi].y;
                let (dx, dy) = if target_x.abs_diff(mob_x) >= target_y.abs_diff(mob_y) {
                    (if target_x > mob_x { -1 } else { 1 }, 0)
                } else {
                    (0, if target_y > mob_y { -1 } else { 1 })
                };
                self.move_mob(mi, dx, dy);
            } else if category == "ranged"
                && distance <= 6
                && self.state.monsters[mi].attack_cooldown <= 0
                && self.state.projectiles.iter().filter(|p| p.hostile).count()
                    < self.state.players.len() * 3
            {
                let target_x = self.state.players[pi].x;
                let target_y = self.state.players[pi].y;
                let mob_x = self.state.monsters[mi].x;
                let mob_y = self.state.monsters[mi].y;
                let (dx, dy) = if target_x.abs_diff(mob_x) >= target_y.abs_diff(mob_y) {
                    (if target_x > mob_x { 1 } else { -1 }, 0)
                } else {
                    (0, if target_y > mob_y { 1 } else { -1 })
                };
                let kind = projectile_kind(&self.state.monsters[mi].kind).to_string();
                let damage = self.state.monsters[mi].damage;
                self.state.projectiles.push(Projectile {
                    owner: self.state.monsters[mi].id.clone(),
                    level,
                    x: mob_x as isize,
                    y: mob_y as isize,
                    dx,
                    dy,
                    damage,
                    ttl: MAP_SIZE as u8,
                    kind,
                    hostile: true,
                });
                self.state.monsters[mi].attack_cooldown = 5;
            } else if category == "ranged" {
                let target_x = self.state.players[pi].x;
                let target_y = self.state.players[pi].y;
                let mob_x = self.state.monsters[mi].x;
                let mob_y = self.state.monsters[mi].y;
                let (tx, ty) = if target_x.abs_diff(mob_x) >= target_y.abs_diff(mob_y) {
                    (if target_x > mob_x { 1 } else { -1 }, 0)
                } else {
                    (0, if target_y > mob_y { 1 } else { -1 })
                };
                if distance <= 3 {
                    self.move_mob(mi, -tx, -ty)
                } else if distance >= 6 {
                    self.move_mob(mi, tx, ty)
                } else {
                    let dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)];
                    let key = self.state.monsters[mi]
                        .id
                        .bytes()
                        .map(u64::from)
                        .sum::<u64>();
                    let (dx, dy) =
                        dirs[(mix64(self.state.seed ^ self.state.timestep ^ key) % 4) as usize];
                    self.move_mob(mi, dx, dy)
                }
            } else if distance <= 1 && self.state.monsters[mi].attack_cooldown <= 0 {
                let damage = Self::incoming(
                    mob_damage_vector(&self.state.monsters[mi].kind),
                    &self.state.players[pi],
                    level == NUM_LEVELS - 1,
                );
                let sleeping = self.state.players[pi].sleeping;
                self.state.players[pi].health -= damage * if sleeping { 3.5 } else { 1.0 };
                self.state.players[pi].sleeping = false;
                self.state.players[pi].resting = false;
                if sleeping {
                    self.award("wake_up", &[pi]);
                }
                self.state.monsters[mi].attack_cooldown = 5;
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
                self.move_mob(mi, dx, dy);
            }
            self.state.monsters[mi].attack_cooldown =
                (self.state.monsters[mi].attack_cooldown - 1).max(0);
        }
    }

    fn move_mob(&mut self, mi: usize, dx: isize, dy: isize) {
        let level = self.state.monsters[mi].level;
        let nx = (self.state.monsters[mi].x as isize + dx) as usize;
        let ny = (self.state.monsters[mi].y as isize + dy) as usize;
        if nx >= MAP_SIZE || ny >= MAP_SIZE {
            return;
        }
        let tile = self.state.maps[level][ny][nx].as_str();
        let kind = self.state.monsters[mi].kind.as_str();
        let open = if ["bat", "fire_elemental", "ice_elemental"].contains(&kind) {
            true
        } else if kind == "deep_thing" {
            tile == "water"
        } else if kind == "lizard" {
            !["stone", "wall", "lava"].contains(&tile)
        } else {
            !["stone", "wall", "water", "lava"].contains(&tile)
        };
        let player_free = !self
            .state
            .players
            .iter()
            .any(|p| p.level == level && p.x == nx && p.y == ny);
        let mob_free = !self
            .state
            .monsters
            .iter()
            .enumerate()
            .any(|(i, m)| i != mi && m.level == level && m.x == nx && m.y == ny);
        if open && player_free && mob_free {
            self.state.monsters[mi].x = nx;
            self.state.monsters[mi].y = ny;
        }
    }

    fn update_plants(&mut self) {
        for plant in &mut self.state.plants {
            plant.age = (plant.age + 1).min(500);
            if plant.age >= 500 && self.state.maps[plant.level][plant.y][plant.x] == "plant" {
                self.state.maps[plant.level][plant.y][plant.x] = "ripe_plant".into();
            }
        }
    }
    fn calculate_inventory_achievements(&mut self) {
        let mut awards = Vec::new();
        for (index, p) in self.state.players.iter().enumerate() {
            for resource in [
                "wood", "stone", "coal", "iron", "diamond", "ruby", "sapphire",
            ] {
                if p.inventory[resource] > 0 {
                    awards.push((format!("collect_{resource}"), index));
                }
            }
            if p.saplings > 0 {
                awards.push(("collect_sapling".into(), index));
            }
            if p.bow > 0 {
                awards.push(("find_bow".into(), index));
            }
            if p.arrows > 0 {
                awards.push(("make_arrow".into(), index));
            }
            if p.torches > 0 {
                awards.push(("make_torch".into(), index));
            }
            for (item, value) in [("pickaxe", p.pickaxe), ("sword", p.sword)] {
                for (tier, name) in ["wood", "stone", "iron", "diamond"].into_iter().enumerate() {
                    if value >= tier as u8 + 1 {
                        awards.push((format!("make_{name}_{item}"), index));
                    }
                }
            }
        }
        for (name, index) in awards {
            self.award(&name, &[index]);
        }
    }
    fn spawn_mobs(&mut self) {
        let alive = self
            .state
            .players
            .iter()
            .filter(|p| p.alive)
            .cloned()
            .collect::<Vec<_>>();
        if alive.is_empty() {
            return;
        }
        let level = alive[0].level;
        if level == NUM_LEVELS - 1 {
            return;
        }
        self.state.monsters.retain(|m| {
            m.level != level
                || alive
                    .iter()
                    .map(|p| p.x.abs_diff(m.x) + p.y.abs_diff(m.y))
                    .min()
                    .unwrap_or(0)
                    < 14
        });
        let kinds = [
            [Some("cow"), Some("zombie"), Some("skeleton")],
            [Some("snail"), Some("orc_soldier"), Some("orc_mage")],
            [Some("bat"), Some("gnome_warrior"), Some("gnome_archer")],
            [Some("bat"), Some("lizard"), Some("kobold")],
            [None, Some("knight"), Some("archer")],
            [None, Some("troll"), Some("deep_thing")],
            [None, Some("pigman"), Some("fire_elemental")],
            [None, Some("frost_troll"), Some("ice_elemental")],
        ];
        let health = [
            [3, 5, 3],
            [6, 9, 6],
            [4, 7, 5],
            [8, 11, 8],
            [0, 12, 12],
            [0, 20, 4],
            [0, 20, 14],
            [0, 24, 16],
        ];
        let categories = ["passive", "melee", "ranged"];
        let caps = if [1, 3, 4].contains(&level) {
            [3, 3, 2]
        } else {
            [
                self.state.players.len() * 3,
                self.state.players.len() * 3,
                self.state.players.len() * 2,
            ]
        };
        let mut chances = if level == 0 {
            [
                0.1,
                0.02 + 0.1 * (1.0 - self.state.light_level).powi(2),
                0.05,
            ]
        } else {
            [if level == 7 { 0.0 } else { 0.1 }, 0.06, 0.05]
        };
        if self.state.monsters_killed[level] < 8 {
            for chance in &mut chances {
                *chance = (*chance * 3.0_f64).min(1.0_f64);
            }
        }
        for category in 0..3 {
            let Some(kind) = kinds[level][category] else {
                continue;
            };
            if self
                .state
                .monsters
                .iter()
                .filter(|m| m.level == level && m.category == categories[category])
                .count()
                >= caps[category]
            {
                continue;
            }
            let roll = (mix64(
                self.state.seed
                    ^ self.state.timestep
                    ^ ((level as u64) << 8)
                    ^ ((category as u64) << 16),
            ) % 10_000) as f64
                / 10_000.0;
            if roll >= chances[category] {
                continue;
            }
            let start =
                (mix64(self.state.seed ^ (self.state.timestep << 11) ^ ((category as u64) << 25))
                    % (MAP_SIZE * MAP_SIZE) as u64) as usize;
            for offset in 0..MAP_SIZE * MAP_SIZE {
                let cell = (start + offset) % (MAP_SIZE * MAP_SIZE);
                let (x, y) = (cell % MAP_SIZE, cell / MAP_SIZE);
                let distance = alive
                    .iter()
                    .map(|p| p.x.abs_diff(x) + p.y.abs_diff(y))
                    .min()
                    .unwrap();
                if distance <= 9
                    || distance >= 14
                    || !(if kind == "deep_thing" {
                        self.state.maps[level][y][x] == "water"
                    } else {
                        ["grass", "path", "sand", "gravel", "fire_grass", "ice_grass"]
                            .contains(&self.state.maps[level][y][x].as_str())
                    })
                    || self
                        .state
                        .monsters
                        .iter()
                        .any(|m| m.level == level && m.x == x && m.y == y)
                {
                    continue;
                }
                self.state.monsters.push(Monster {
                    id: format!("spawn_{level}_{}_{category}", self.state.timestep),
                    kind: kind.into(),
                    level,
                    x,
                    y,
                    health: health[level][category] as f64,
                    damage: mob_damage(kind),
                    category: categories[category].into(),
                    attack_cooldown: 0,
                });
                break;
            }
        }
    }
    fn update_boss(&mut self) {
        if !self
            .state
            .players
            .iter()
            .any(|p| p.alive && p.level == NUM_LEVELS - 1)
        {
            return;
        }
        if self.state.boss_wave_timer > 0 {
            self.state.boss_wave_timer -= 1;
            let category = 1 + (self.state.boss_wave_timer as usize % 2);
            let floor = self.state.boss_progress.min(7);
            let kinds = [
                [Some("cow"), Some("zombie"), Some("skeleton")],
                [Some("snail"), Some("orc_soldier"), Some("orc_mage")],
                [Some("bat"), Some("gnome_warrior"), Some("gnome_archer")],
                [Some("bat"), Some("lizard"), Some("kobold")],
                [None, Some("knight"), Some("archer")],
                [None, Some("troll"), Some("deep_thing")],
                [None, Some("pigman"), Some("fire_elemental")],
                [None, Some("frost_troll"), Some("ice_elemental")],
            ];
            if let Some(kind) = kinds[floor][category] {
                if self
                    .state
                    .monsters
                    .iter()
                    .filter(|m| m.level == NUM_LEVELS - 1)
                    .count()
                    < 6
                {
                    let graves = self.state.maps[NUM_LEVELS - 1]
                        .iter()
                        .enumerate()
                        .flat_map(|(y, row)| {
                            row.iter().enumerate().filter_map(move |(x, tile)| {
                                ["grave", "grave2", "grave3"]
                                    .contains(&tile.as_str())
                                    .then_some((x, y))
                            })
                        })
                        .collect::<Vec<_>>();
                    if !graves.is_empty() {
                        let (x, y) = graves[(mix64(
                            self.state.seed ^ self.state.timestep ^ self.state.boss_progress as u64,
                        ) % graves.len() as u64)
                            as usize];
                        self.state.monsters.push(Monster {
                            id: format!(
                                "boss_{}_{}_{}",
                                self.state.boss_progress, self.state.timestep, category
                            ),
                            kind: kind.into(),
                            level: NUM_LEVELS - 1,
                            x,
                            y,
                            health: [
                                [3, 5, 3],
                                [6, 9, 6],
                                [4, 7, 5],
                                [8, 11, 8],
                                [0, 12, 12],
                                [0, 20, 4],
                                [0, 20, 14],
                                [0, 24, 16],
                            ][floor][category] as f64,
                            damage: mob_damage(kind),
                            category: ["passive", "melee", "ranged"][category].into(),
                            attack_cooldown: 0,
                        });
                    }
                }
            }
        }
        if self.state.boss_wave_timer == 0
            && !self
                .state
                .monsters
                .iter()
                .any(|m| m.level == NUM_LEVELS - 1)
        {
            for row in &mut self.state.maps[NUM_LEVELS - 1] {
                for tile in row {
                    if tile == "necromancer" {
                        *tile = "necromancer_vulnerable".into();
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
            let cap = if resource == "food" {
                max_food(&self.state.players[target])
            } else {
                max_drink(&self.state.players[target])
            };
            if stock <= 0 || target_stock >= cap {
                return;
            }
            if resource == "food" {
                self.state.players[giver].food -= 1;
                self.state.players[target].food = (self.state.players[target].food + 1).min(cap);
            } else {
                self.state.players[giver].drink -= 1;
                self.state.players[target].drink = (self.state.players[target].drink + 1).min(cap);
            }
            self.state.trade_count += 1;
            if resource == "food" {
                self.state.players[target].hunger = 0.0;
                self.state.food_trade_count += 1;
            }
            if resource == "drink" {
                self.state.players[target].thirst = 0.0;
                self.state.drink_trade_count += 1;
            }
            self.award(&format!("collect_{resource}"), &[target]);
            self.award("trade", &[giver, target]);
            self.event_values(
                "trade_applied",
                BTreeMap::from([
                    ("giver".into(), json!(self.state.players[giver].agent_id)),
                    (
                        "receiver".into(),
                        json!(self.state.players[target].agent_id),
                    ),
                    ("resource".into(), json!(resource)),
                ]),
            );
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
        self.state.trade_count += 1;
        self.award("trade", &[giver, target]);
        self.event_values(
            "trade_applied",
            BTreeMap::from([
                ("giver".into(), json!(self.state.players[giver].agent_id)),
                (
                    "receiver".into(),
                    json!(self.state.players[target].agent_id),
                ),
                ("resource".into(), json!(resource)),
            ]),
        );
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
        self.event_values(kind, fields);
    }
    fn event_values(&mut self, kind: &str, fields: BTreeMap<String, Value>) {
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
            schema_version: "craftax-coop.checkpoint.v2".into(),
            state: self.state.clone(),
        })
        .expect("state serializes")
    }
    pub fn restore_json(raw: &str) -> Result<Self, serde_json::Error> {
        let checkpoint: Checkpoint = serde_json::from_str(raw)?;
        if checkpoint.schema_version != "craftax-coop.checkpoint.v2" {
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
        if self.state.alem_coord.is_some() {
            actions.push("say".into());
        }
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
                let item=if x<0||y<0||x>=MAP_SIZE as isize||y>=MAP_SIZE as isize{None}else{self.state.item_maps[p.level][y as usize][x as usize].clone()};
                let light=if x<0||y<0||x>=MAP_SIZE as isize||y>=MAP_SIZE as isize{0.0}else{self.state.light_maps[p.level][y as usize][x as usize]*if p.level==0{self.state.light_level}else{1.0}};
                row.push(json!({"x":x,"y":y,"terrain":terrain,"item":item,"light":light,"agents":agents,"mobs":mobs}));
            } view.push(Value::Array(row)); }
            let visible=self.state.monsters.iter().filter(|m|m.level==p.level&&m.x.abs_diff(p.x)<=radius as usize&&m.y.abs_diff(p.y)<=radius as usize).collect::<Vec<_>>();
            let achievements=self.state.achievements.iter().map(|name|(name.clone(),true)).collect::<BTreeMap<_,_>>();
            let personal=self.state.achievements_by_agent[&p.agent_id].iter().map(|name|(name.clone(),true)).collect::<BTreeMap<_,_>>();
            (p.agent_id.clone(),json!({"agent_id":p.agent_id,"agent_index":index,"role":p.role,"legal_agent_ids":self.state.players.iter().map(|q|q.agent_id.clone()).collect::<Vec<_>>(),"legal_actions":self.legal_actions(&p.agent_id),"self":Self::player_json(p),"achievements":personal,"teammate_dashboard":dashboard,"level":p.level,"map_size":[MAP_SIZE,MAP_SIZE],"num_levels":NUM_LEVELS,"local_view":view,"ascii":self.render_ascii(p,radius),"visible_monsters":visible,"last_joint_event":self.state.last_joint_event,"shared":{"timestep":self.state.timestep,"light_level":self.state.light_level,"boss_health":self.state.boss_health,"boss_progress":self.state.boss_progress,"trade_count":self.state.trade_count,"food_trade_count":self.state.food_trade_count,"drink_trade_count":self.state.drink_trade_count,"revives":self.state.revives,"friendly_fire_damage":self.state.ff_damage_dealt,"chests_opened":self.state.chests_opened,"monsters_killed":self.state.monsters_killed,"achievements":achievements}}))
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
        json!({"agent_id":p.agent_id,"role":p.role,"position":[p.x,p.y],"level":p.level,"facing":p.facing,"health":p.health,"food":p.food,"drink":p.drink,"energy":p.energy,"mana":p.mana,"alive":p.alive,"sleeping":p.sleeping,"resting":p.resting,"inventory":p.inventory,"equipment":{"pickaxe":p.pickaxe,"sword":p.sword,"armour":p.armour,"armour_slots":p.armour_slots,"bow":p.bow,"arrows":p.arrows,"torches":p.torches,"books":p.books,"saplings":p.saplings,"potions":p.potions,"learned_spell":p.learned_spell,"enchantments":{"sword":p.sword_enchantment,"armour":p.armour_enchantment,"armour_slots":p.armour_enchantments,"bow":p.bow_enchantment}},"attributes":{"dexterity":p.dexterity,"strength":p.strength,"intelligence":p.intelligence,"xp":p.xp,"level_points":p.level_points},"intrinsics":{"recover":p.recover,"hunger":p.hunger,"thirst":p.thirst,"fatigue":p.fatigue,"recover_mana":p.recover_mana},"request":{"resource":p.request_type,"remaining":p.request_duration}})
    }
}

fn alem_coord_state(config: AlemCoordConfig) -> AlemCoordState {
    let site = match config.scenario.as_str() {
        "sync_2" => CoordSite {
            site_id: "sync_2_site".into(),
            site_index: 0,
            kind: "sync_2".into(),
            level: 0,
            x: 4,
            y: 4,
            participants: vec!["agent_0".into(), "agent_1".into()],
            required_role: Some("warrior".into()),
            receiver_role: None,
            resource: None,
            window: 0,
            status: "open".into(),
            opened_at: None,
        },
        "sync_all" => CoordSite {
            site_id: "sync_all_site".into(),
            site_index: 1,
            kind: "sync_all".into(),
            level: 0,
            x: 4,
            y: 4,
            participants: vec!["agent_0".into(), "agent_1".into(), "agent_2".into()],
            required_role: Some("warrior".into()),
            receiver_role: None,
            resource: None,
            window: 0,
            status: "open".into(),
            opened_at: None,
        },
        "handover" => CoordSite {
            site_id: "handover_site".into(),
            site_index: 2,
            kind: "handover".into(),
            level: 0,
            x: 4,
            y: 4,
            participants: vec!["agent_2".into(), "agent_1".into()],
            required_role: Some("miner".into()),
            receiver_role: Some("forager".into()),
            resource: Some("iron".into()),
            window: 2,
            status: "open".into(),
            opened_at: None,
        },
        _ => unreachable!("AlemCoordConfig validates scenario"),
    };
    AlemCoordState {
        scenario: config.scenario,
        alpha_milli: config.alpha_milli,
        sites: vec![site],
        base_reward: 0.0,
        coord_reward: 0.0,
        site_metrics: ["sync_2", "sync_all", "handover"]
            .into_iter()
            .map(|kind| {
                (
                    kind.into(),
                    BTreeMap::from([("success".into(), 0), ("resolved".into(), 0)]),
                )
            })
            .collect(),
    }
}

fn event_field_text(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        _ => value.to_string(),
    }
}

fn mix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e3779b97f4a7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d049bb133111eb);
    value ^ (value >> 31)
}

fn potion_mapping(seed: u64) -> Vec<String> {
    let mut effects = [
        "health",
        "harm",
        "mana",
        "drain_mana",
        "energy",
        "exhaustion",
    ];
    effects
        .sort_by_key(|effect| mix64(seed.wrapping_add(effect.bytes().map(u64::from).sum::<u64>())));
    effects.into_iter().map(str::to_string).collect()
}

fn direction(facing: &str) -> (isize, isize) {
    match facing {
        "left" => (-1, 0),
        "right" => (1, 0),
        "up" => (0, -1),
        "down" => (0, 1),
        other => panic!("invalid player facing: {other}"),
    }
}

fn max_health(player: &Player) -> f64 {
    8.0 + player.strength as f64
}
fn max_food(player: &Player) -> i16 {
    (7 + 2 * player.dexterity as i16) * if player.role == "forager" { 3 } else { 1 }
}
fn max_drink(player: &Player) -> i16 {
    max_food(player)
}
fn max_energy(player: &Player) -> i16 {
    7 + 2 * player.dexterity as i16
}
fn max_mana(player: &Player) -> i16 {
    6 + 3 * player.intelligence as i16
}

fn mob_damage(kind: &str) -> i16 {
    match kind {
        "zombie" | "skeleton" => 2,
        "gnome_warrior" | "gnome_archer" => 4,
        "orc_soldier" | "orc_mage" => 3,
        "lizard" => 5,
        "kobold" => 3,
        "knight" => 6,
        "archer" => 5,
        "troll" => 8,
        "deep_thing" => 10,
        "pigman" | "fire_elemental" => 8,
        "frost_troll" | "ice_elemental" => 9,
        _ => 0,
    }
}

fn projectile_kind(kind: &str) -> &'static str {
    match kind {
        "skeleton" | "gnome_archer" => "arrow",
        "orc_mage" => "fireball",
        "kobold" => "dagger",
        "archer" => "arrow2",
        "deep_thing" => "slimeball",
        "fire_elemental" => "fireball2",
        "ice_elemental" => "iceball2",
        _ => "arrow",
    }
}
fn projectile_vector(kind: &str) -> [f64; 3] {
    match kind {
        "arrow" => [2., 0., 0.],
        "dagger" => [4., 0., 0.],
        "fireball" => [0., 3., 0.],
        "iceball" => [0., 0., 3.],
        "arrow2" => [5., 0., 0.],
        "slimeball" => [4., 3., 3.],
        "fireball2" => [3., 5., 0.],
        "iceball2" => [4., 0., 5.],
        _ => [1., 0., 0.],
    }
}
fn mob_damage_vector(kind: &str) -> [f64; 3] {
    match kind {
        "zombie" => [2., 0., 0.],
        "gnome_warrior" => [4., 0., 0.],
        "orc_soldier" => [3., 0., 0.],
        "lizard" => [5., 0., 0.],
        "knight" => [6., 0., 0.],
        "troll" => [6., 1., 1.],
        "pigman" => [3., 5., 0.],
        "frost_troll" => [4., 0., 5.],
        _ => [mob_damage(kind) as f64, 0., 0.],
    }
}

fn level_achievement(level: usize) -> Option<&'static str> {
    [
        None,
        Some("enter_dungeon"),
        Some("enter_gnomish_mines"),
        Some("enter_sewers"),
        Some("enter_vault"),
        Some("enter_troll_mines"),
        Some("enter_fire_realm"),
        Some("enter_ice_realm"),
        Some("enter_graveyard"),
    ][level]
}

fn kill_achievement(kind: &str) -> Option<&'static str> {
    Some(match kind {
        "cow" => "eat_cow",
        "bat" => "eat_bat",
        "snail" => "eat_snail",
        "zombie" => "defeat_zombie",
        "skeleton" => "defeat_skeleton",
        "gnome_warrior" => "defeat_gnome_warrior",
        "gnome_archer" => "defeat_gnome_archer",
        "orc_soldier" => "defeat_orc_soldier",
        "orc_mage" => "defeat_orc_mage",
        "lizard" => "defeat_lizard",
        "kobold" => "defeat_kobold",
        "knight" => "defeat_knight",
        "archer" => "defeat_archer",
        "troll" => "defeat_troll",
        "deep_thing" => "defeat_deep_thing",
        "pigman" => "defeat_pigman",
        "fire_elemental" => "defeat_fire_elemental",
        "frost_troll" => "defeat_frost_troll",
        "ice_elemental" => "defeat_ice_elemental",
        _ => return None,
    })
}

fn achievement_reward(name: &str) -> f64 {
    if [
        "trade", "all_roles_alive", "level_up", "coord_sync_2", "coord_sync_all",
        "coord_handover", "coord_message", "coord_soft_role", "coord_handover_offer",
    ]
    .contains(&name)
    {
        return 0.0;
    }
    if [
        "collect_wood",
        "place_table",
        "eat_cow",
        "collect_sapling",
        "collect_drink",
        "collect_food",
        "make_wood_pickaxe",
        "make_wood_sword",
        "place_plant",
        "defeat_zombie",
        "collect_stone",
        "place_stone",
        "eat_plant",
        "defeat_skeleton",
        "make_stone_pickaxe",
        "make_stone_sword",
        "wake_up",
        "place_furnace",
        "collect_coal",
        "collect_iron",
        "collect_diamond",
        "make_iron_pickaxe",
        "make_iron_sword",
        "make_arrow",
        "make_torch",
        "place_torch",
    ]
    .contains(&name)
    {
        1.0
    } else if [
        "collect_sapphire",
        "collect_ruby",
        "make_diamond_pickaxe",
        "make_diamond_sword",
        "make_iron_armour",
        "make_diamond_armour",
        "enter_gnomish_mines",
        "enter_dungeon",
        "defeat_gnome_warrior",
        "defeat_gnome_archer",
        "defeat_orc_soldier",
        "defeat_orc_mage",
        "eat_bat",
        "eat_snail",
        "find_bow",
        "fire_bow",
        "open_chest",
        "drink_potion",
    ]
    .contains(&name)
    {
        3.0
    } else if [
        "enter_fire_realm",
        "enter_ice_realm",
        "enter_graveyard",
        "defeat_pigman",
        "defeat_fire_elemental",
        "defeat_frost_troll",
        "defeat_ice_elemental",
        "damage_necromancer",
        "defeat_necromancer",
    ]
    .contains(&name)
    {
        8.0
    } else {
        5.0
    }
}
