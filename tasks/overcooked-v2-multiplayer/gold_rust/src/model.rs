use serde::{Deserialize, Deserializer, Serialize, Serializer};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

#[derive(
    Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize,
)]
#[serde(transparent)]
pub struct Position(pub [i32; 2]);

impl Position {
    pub const fn new(row: i32, col: i32) -> Self {
        Self([row, col])
    }

    pub const fn row(self) -> i32 {
        self.0[0]
    }

    pub const fn col(self) -> i32 {
        self.0[1]
    }

    pub fn step(self, direction: Direction) -> Self {
        let (dr, dc) = direction.delta();
        Self::new(self.row() + dr, self.col() + dc)
    }

    pub fn chebyshev(self, other: Self) -> i32 {
        (self.row() - other.row())
            .abs()
            .max((self.col() - other.col()).abs())
    }

    pub fn manhattan(self, other: Self) -> i32 {
        (self.row() - other.row()).abs() + (self.col() - other.col()).abs()
    }
}

#[derive(
    Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize,
)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    North,
    South,
    East,
    West,
}

impl Direction {
    pub const ALL: [Self; 4] = [Self::North, Self::South, Self::East, Self::West];

    pub const fn delta(self) -> (i32, i32) {
        match self {
            Self::North => (-1, 0),
            Self::South => (1, 0),
            Self::East => (0, 1),
            Self::West => (0, -1),
        }
    }

    pub fn from_adjacent(from: Position, to: Position) -> Option<Self> {
        Self::ALL
            .into_iter()
            .find(|direction| from.step(*direction) == to)
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Action {
    Move { direction: Direction },
    Interact,
    #[serde(alias = "noop")]
    Wait,
}

impl Action {
    pub fn from_json(value: &Value) -> Result<Self, String> {
        if let Some(raw) = value.as_str() {
            return match raw {
                "north" => Ok(Self::Move {
                    direction: Direction::North,
                }),
                "south" => Ok(Self::Move {
                    direction: Direction::South,
                }),
                "east" => Ok(Self::Move {
                    direction: Direction::East,
                }),
                "west" => Ok(Self::Move {
                    direction: Direction::West,
                }),
                "interact" => Ok(Self::Interact),
                "wait" | "noop" => Ok(Self::Wait),
                other => Err(format!("unsupported Overcooked action string {other:?}")),
            };
        }
        serde_json::from_value(value.clone())
            .map_err(|error| format!("invalid Overcooked action JSON: {error}"))
    }
}

pub type JointAction = BTreeMap<String, Action>;

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct LayoutDocument {
    #[serde(default)]
    pub layout_id: Option<String>,
    #[serde(default)]
    pub ascii: Vec<String>,
    #[serde(default)]
    pub recipe_pool: Vec<String>,
    #[serde(default)]
    pub possible_recipes: Vec<Vec<u8>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ParsedLayout {
    pub layout_id: String,
    pub width: i32,
    pub height: i32,
    pub walls: BTreeSet<Position>,
    #[serde(with = "position_map")]
    pub ingredient_piles: BTreeMap<Position, u8>,
    pub dish_dispensers: BTreeSet<Position>,
    pub pots: BTreeSet<Position>,
    pub serve_tiles: BTreeSet<Position>,
    pub counters: BTreeSet<Position>,
    pub recipe_indicators: BTreeSet<Position>,
    pub button_recipe_indicators: BTreeSet<Position>,
    pub agent_starts: BTreeMap<String, Position>,
    pub num_ingredients: u8,
}

pub(crate) mod position_map {
    use super::{BTreeMap, Deserialize, Deserializer, Position, Serialize, Serializer};
    use serde::de::Error as DeError;
    use serde::ser::SerializeMap;

    pub fn serialize<S, V>(map: &BTreeMap<Position, V>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
        V: Serialize,
    {
        let mut output = serializer.serialize_map(Some(map.len()))?;
        for (position, value) in map {
            output.serialize_entry(
                &format!("{},{}", position.row(), position.col()),
                value,
            )?;
        }
        output.end()
    }

    pub fn deserialize<'de, D, V>(deserializer: D) -> Result<BTreeMap<Position, V>, D::Error>
    where
        D: Deserializer<'de>,
        V: Deserialize<'de>,
    {
        let raw = BTreeMap::<String, V>::deserialize(deserializer)?;
        raw.into_iter()
            .map(|(key, value)| {
                let (row, col) = key
                    .split_once(',')
                    .ok_or_else(|| D::Error::custom(format!("invalid position key {key:?}")))?;
                let row = row.parse::<i32>().map_err(|error| {
                    D::Error::custom(format!("invalid position row in {key:?}: {error}"))
                })?;
                let col = col.parse::<i32>().map_err(|error| {
                    D::Error::custom(format!("invalid position col in {key:?}: {error}"))
                })?;
                Ok((Position::new(row, col), value))
            })
            .collect()
    }
}

impl ParsedLayout {
    pub fn in_bounds(&self, position: Position) -> bool {
        position.row() >= 0
            && position.col() >= 0
            && position.row() < self.height
            && position.col() < self.width
    }

    pub fn is_fixture(&self, position: Position) -> bool {
        self.ingredient_piles.contains_key(&position)
            || self.dish_dispensers.contains(&position)
            || self.pots.contains(&position)
            || self.serve_tiles.contains(&position)
            || self.counters.contains(&position)
            || self.recipe_indicators.contains(&position)
            || self.button_recipe_indicators.contains(&position)
    }

    pub fn is_static_walkable(&self, position: Position) -> bool {
        self.in_bounds(position)
            && !self.walls.contains(&position)
            && !self.is_fixture(position)
    }

    pub fn walkable_tiles(&self) -> Vec<Position> {
        let mut tiles = Vec::new();
        for row in 0..self.height {
            for col in 0..self.width {
                let position = Position::new(row, col);
                if self.is_static_walkable(position) {
                    tiles.push(position);
                }
            }
        }
        tiles
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResolvedTask {
    pub task_id: String,
    pub scenario_id: String,
    pub seed: u64,
    pub layout_id: String,
    pub agent_ids: Vec<String>,
    pub recipe_id: String,
    pub recipe_ingredients: Vec<u8>,
    pub required_onions: u8,
    pub cook_time: u32,
    pub max_steps: u32,
    pub partial_obs: bool,
    pub view_radius: i32,
    pub hidden_recipe: bool,
    pub stochastic_spawn: bool,
    pub recipe_pool: Vec<String>,
    pub resample_on_delivery: bool,
    pub target_deliveries: u32,
    pub wrong_delivery_penalty: f64,
    pub observation_profile: String,
    pub indicator_activation_time: u32,
    pub indicator_activation_cost: f64,
    pub start_cooking_interaction: bool,
    pub op_ingredient_permutations: bool,
    pub indicate_successful_delivery: bool,
    pub shaped_rewards: bool,
    pub random_reset: bool,
    pub urgency_cutoff: u32,
    pub config_hash: String,
    pub episode_id: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct AgentState {
    pub agent_id: String,
    pub position: Position,
    pub facing: Direction,
    pub held: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct PrivateState {
    pub step_index: u32,
    pub total_reward: f64,
    pub reward_last: f64,
    pub terminated: bool,
    pub truncated: bool,
    pub config_hash: String,
    pub episode_id: String,
    pub invalid_action_count: u32,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PublicState {
    pub agents: BTreeMap<String, AgentState>,
    pub pot_ingredients: BTreeMap<String, u8>,
    pub pot_onions: u8,
    pub cooking_ticks: u32,
    pub soup_ready: bool,
    pub deliveries: u32,
    pub recipe_id: String,
    pub active_recipe_id: String,
    pub recipe_ingredients: Vec<u8>,
    pub cooked_recipe_id: Option<String>,
    pub counter_items: BTreeMap<String, String>,
    pub button_activation_ticks: BTreeMap<String, u32>,
    pub delivery_success_flag: bool,
    pub done: bool,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct RuntimeMetrics {
    pub blocked_moves: u32,
    pub interaction_no_effects: u32,
    pub ingredients_picked: u32,
    pub ingredients_added: u32,
    pub cook_starts: u32,
    pub soups_cooked: u32,
    pub soups_plated: u32,
    pub counter_handoffs: u32,
    pub button_activations: u32,
    pub recipe_visible_agent_turns: u32,
    pub delivery_attempts: u32,
    pub correct_deliveries: u32,
    pub wrong_deliveries: u32,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TerminalMetrics {
    pub success: bool,
    pub terminated: bool,
    pub truncated: bool,
    pub terminal_reason: Option<String>,
    pub steps: u32,
    pub max_steps: u32,
    pub deliveries: u32,
    pub target_deliveries: u32,
    pub total_reward: f64,
    pub invalid_action_count: u32,
    pub event_count: usize,
    pub runtime: RuntimeMetrics,
    pub state_digest: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct EventRecord {
    pub step_index: u32,
    pub tick: u32,
    pub episode_id: String,
    pub kind: String,
    pub action: Option<Value>,
    pub transition: Option<String>,
    pub severity: String,
    pub message: String,
    pub payload: Value,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Readout {
    pub schema: String,
    pub env_family: String,
    pub task_id: String,
    pub scenario_id: String,
    pub observation_profile: String,
    pub public: PublicState,
    pub private: PrivateState,
    pub observations: BTreeMap<String, Value>,
    pub rewards: BTreeMap<String, f64>,
    pub dones: BTreeMap<String, bool>,
    pub ascii: String,
    pub grid_hash: String,
    pub nev_cursor: usize,
    pub joint_valid_actions: BTreeMap<String, Vec<Action>>,
    pub metrics: RuntimeMetrics,
}
