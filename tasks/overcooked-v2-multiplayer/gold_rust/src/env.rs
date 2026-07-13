use crate::catalog::{resolve_task, sha256_hex, sorted_counts};
use crate::model::{
    Action, AgentState, Direction, EventRecord, JointAction, ParsedLayout, Position, PrivateState,
    PublicState, Readout, ResolvedTask, RuntimeMetrics, TerminalMetrics,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

const ENV_FAMILY: &str = "overcooked-v2-multiplayer";
const CHECKPOINT_SCHEMA: &str = "gamebench.overcooked_v2.checkpoint.v2";
const MAX_POT_SLOTS: u8 = 3;
const DELIVERY_REWARD: f64 = 1.0;

#[derive(Clone, Debug, Serialize, Deserialize)]
struct DeterministicRng {
    state: u64,
}

impl DeterministicRng {
    fn new(seed: u64) -> Self {
        Self {
            state: seed ^ 0x9e37_79b9_7f4a_7c15,
        }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut value = self.state;
        value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        value ^ (value >> 31)
    }

    fn index(&mut self, length: usize) -> usize {
        if length <= 1 {
            0
        } else {
            (self.next_u64() % length as u64) as usize
        }
    }

    fn unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1_u64 << 53) as f64
    }

    fn shuffle<T>(&mut self, items: &mut [T]) {
        for index in (1..items.len()).rev() {
            let swap_index = self.index(index + 1);
            items.swap(index, swap_index);
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct DynamicState {
    agents: BTreeMap<String, AgentState>,
    #[serde(with = "crate::model::position_map")]
    counter_items: BTreeMap<Position, String>,
    pot_ingredients: BTreeMap<u8, u8>,
    cooking_ticks: u32,
    soup_ready: bool,
    cooked_recipe_id: Option<String>,
    deliveries: u32,
    active_recipe_id: String,
    recipe_ingredients: Vec<u8>,
    required_onions: u8,
    cook_time: u32,
    button_activation_ticks: BTreeMap<String, u32>,
    ingredient_permutations: BTreeMap<String, Vec<u8>>,
    delivery_success_flag: bool,
    private: PrivateState,
    rng: DeterministicRng,
    runtime_metrics: RuntimeMetrics,
    terminal_reason: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Checkpoint {
    schema_version: String,
    env_family: String,
    episode_id: String,
    step_index: u32,
    nev_cursor: usize,
    config_hash: String,
    resolved: ResolvedTask,
    layout: ParsedLayout,
    dynamic: DynamicState,
    events: Vec<EventRecord>,
}

#[derive(Clone, Debug)]
pub struct OvercookedV2Env {
    resolved: ResolvedTask,
    layout: ParsedLayout,
    state: DynamicState,
    events: Vec<EventRecord>,
}

impl OvercookedV2Env {
    pub fn from_task_value(task: &Value, defaults_dir: impl AsRef<Path>) -> Result<Self, String> {
        let (resolved, layout) = resolve_task(task, defaults_dir.as_ref())?;
        Self::from_resolved(resolved, layout)
    }

    pub fn from_task_json(task_json: &str, defaults_dir: impl AsRef<Path>) -> Result<Self, String> {
        let task: Value = serde_json::from_str(task_json)
            .map_err(|error| format!("invalid Overcooked task JSON: {error}"))?;
        Self::from_task_value(&task, defaults_dir)
    }

    fn from_resolved(resolved: ResolvedTask, layout: ParsedLayout) -> Result<Self, String> {
        let mut rng = DeterministicRng::new(resolved.seed);
        let active_recipe_id = if resolved.recipe_pool.len() > 1 {
            resolved.recipe_pool[rng.index(resolved.recipe_pool.len())].clone()
        } else {
            resolved.recipe_id.clone()
        };
        let (recipe_ingredients, cook_time) = active_recipe_parameters(&resolved, &active_recipe_id);
        let required_onions = recipe_ingredients.iter().filter(|index| **index == 0).count() as u8;
        let agents = initial_agents(&resolved, &layout, &mut rng)?;
        let mut ingredient_permutations = BTreeMap::new();
        if resolved.op_ingredient_permutations {
            for agent_id in &resolved.agent_ids {
                let mut permutation = (0..layout.num_ingredients).collect::<Vec<_>>();
                rng.shuffle(&mut permutation);
                ingredient_permutations.insert(agent_id.clone(), permutation);
            }
        }
        let private = PrivateState {
            config_hash: resolved.config_hash.clone(),
            episode_id: resolved.episode_id.clone(),
            ..PrivateState::default()
        };
        let mut environment = Self {
            resolved,
            layout,
            state: DynamicState {
                agents,
                counter_items: BTreeMap::new(),
                pot_ingredients: BTreeMap::new(),
                cooking_ticks: 0,
                soup_ready: false,
                cooked_recipe_id: None,
                deliveries: 0,
                active_recipe_id,
                recipe_ingredients,
                required_onions,
                cook_time,
                button_activation_ticks: BTreeMap::new(),
                ingredient_permutations,
                delivery_success_flag: false,
                private,
                rng,
                runtime_metrics: RuntimeMetrics::default(),
                terminal_reason: None,
            },
            events: Vec::new(),
        };
        if environment.resolved.random_reset {
            environment.apply_random_reset()?;
        }
        environment.append_event(
            "task_resolved",
            format!(
                "TaskResolved({},{})",
                environment.resolved.task_id, environment.resolved.config_hash
            ),
            None,
            None,
            "info",
            json!({"task": environment.resolved}),
        );
        environment.append_event(
            "state_transition",
            format!("GameStarted({})", environment.resolved.scenario_id),
            None,
            None,
            "info",
            json!({
                "scenario_id": environment.resolved.scenario_id,
                "seed": environment.resolved.seed,
                "active_recipe_id": environment.state.active_recipe_id,
                "recipe_ingredients": environment.state.recipe_ingredients,
            }),
        );
        Ok(environment)
    }

    pub fn step_json(&mut self, joint_action: &Value) -> Result<Readout, String> {
        let object = joint_action
            .as_object()
            .ok_or_else(|| "joint action must be a JSON object keyed by agent id".to_string())?;
        let mut parsed = JointAction::new();
        for agent_id in &self.resolved.agent_ids {
            let action = match object.get(agent_id) {
                Some(value) => Action::from_json(value)?,
                None => Action::Wait,
            };
            parsed.insert(agent_id.clone(), action);
        }
        self.step(&parsed)
    }

    pub fn step(&mut self, joint_action: &JointAction) -> Result<Readout, String> {
        let action_value = serde_json::to_value(joint_action)
            .map_err(|error| format!("serialize joint action: {error}"))?;
        if self.state.private.terminated || self.state.private.truncated {
            self.state.private.invalid_action_count += 1;
            self.append_event(
                "rule_violation",
                "Blocked(terminal)".to_string(),
                Some(action_value),
                None,
                "error",
                json!({}),
            );
            return self.readout();
        }

        self.state.private.step_index += 1;
        self.state.private.reward_last = 0.0;
        self.state.delivery_success_flag = false;
        self.decay_button_ticks();
        self.append_event(
            "state_transition",
            "JointStepBegin".to_string(),
            Some(action_value.clone()),
            None,
            "info",
            json!({"step_index": self.state.private.step_index}),
        );
        let normalized = self
            .resolved
            .agent_ids
            .iter()
            .map(|agent_id| {
                (
                    agent_id.clone(),
                    joint_action.get(agent_id).cloned().unwrap_or(Action::Wait),
                )
            })
            .collect::<JointAction>();
        self.resolve_moves(&normalized, &action_value);
        let agent_ids = self.resolved.agent_ids.clone();
        for agent_id in agent_ids {
            if normalized.get(&agent_id) == Some(&Action::Interact) {
                self.interact(&agent_id, &action_value)?;
            }
        }
        self.advance_cooking();
        let visible_agent_turns = self
            .resolved
            .agent_ids
            .iter()
            .filter(|agent_id| self.recipe_visible_for(agent_id))
            .count() as u32;
        self.state.runtime_metrics.recipe_visible_agent_turns += visible_agent_turns;
        self.maybe_truncate();
        self.readout()
    }

    fn resolve_moves(&mut self, actions: &JointAction, action_value: &Value) {
        let move_intents = actions
            .iter()
            .filter_map(|(agent_id, action)| match action {
                Action::Move { direction } => Some((agent_id.clone(), *direction)),
                _ => None,
            })
            .collect::<BTreeMap<_, _>>();
        if move_intents.is_empty() {
            return;
        }
        let targets = move_intents
            .iter()
            .map(|(agent_id, direction)| {
                let target = self.state.agents[agent_id].position.step(*direction);
                (agent_id.clone(), target)
            })
            .collect::<BTreeMap<_, _>>();
        let mut blocked = BTreeSet::new();
        let target_set = targets.values().copied().collect::<BTreeSet<_>>();
        if target_set.len() != targets.len() {
            blocked.extend(move_intents.keys().cloned());
        }
        let intent_ids = move_intents.keys().cloned().collect::<Vec<_>>();
        for left_index in 0..intent_ids.len() {
            for right_index in left_index + 1..intent_ids.len() {
                let left = &intent_ids[left_index];
                let right = &intent_ids[right_index];
                if targets[left] == self.state.agents[right].position
                    && targets[right] == self.state.agents[left].position
                {
                    blocked.insert(left.clone());
                    blocked.insert(right.clone());
                }
            }
        }
        for (agent_id, target) in &targets {
            if blocked.contains(agent_id) {
                continue;
            }
            if self.agent_at(*target).is_some() || !self.is_walkable(*target) {
                blocked.insert(agent_id.clone());
            }
        }
        for (agent_id, direction) in move_intents {
            let target = targets[&agent_id];
            if blocked.contains(&agent_id) {
                if self.layout.is_fixture(target) && self.agent_at(target).is_none() {
                    self.state.agents.get_mut(&agent_id).unwrap().facing = direction;
                    self.append_event(
                        "action_applied",
                        format!("FaceApplied({agent_id},{})", direction_name(direction)),
                        Some(action_value.clone()),
                        Some("face"),
                        "info",
                        json!({}),
                    );
                } else {
                    self.state.runtime_metrics.blocked_moves += 1;
                    self.append_event(
                        "rule_violation",
                        format!("MoveBlocked({agent_id})"),
                        Some(action_value.clone()),
                        None,
                        "warn",
                        json!({"target": target}),
                    );
                }
                continue;
            }
            let agent = self.state.agents.get_mut(&agent_id).unwrap();
            agent.position = target;
            agent.facing = direction;
            self.append_event(
                "action_applied",
                format!("MoveApplied({agent_id},{})", direction_name(direction)),
                Some(action_value.clone()),
                Some("move"),
                "info",
                json!({}),
            );
        }
    }

    fn interact(&mut self, agent_id: &str, action_value: &Value) -> Result<(), String> {
        let agent = self
            .state
            .agents
            .get(agent_id)
            .cloned()
            .ok_or_else(|| format!("unknown agent {agent_id:?}"))?;
        let target = agent.position.step(agent.facing);

        if let Some(ingredient_index) = self.layout.ingredient_piles.get(&target).copied() {
            if agent.held.is_none() {
                let held = ingredient_name(ingredient_index);
                self.state.agents.get_mut(agent_id).unwrap().held = Some(held.clone());
                self.state.runtime_metrics.ingredients_picked += 1;
                self.append_event(
                    "action_applied",
                    format!("ItemPicked({agent_id},{held})"),
                    Some(action_value.clone()),
                    Some("pickup"),
                    "info",
                    json!({"ingredient_index": ingredient_index}),
                );
                return Ok(());
            }
        }

        if self.layout.dish_dispensers.contains(&target) && agent.held.is_none() {
            self.state.agents.get_mut(agent_id).unwrap().held = Some("dish".to_string());
            self.apply_shaped_reward("dish_pickup");
            self.append_event(
                "action_applied",
                format!("ItemPicked({agent_id},dish)"),
                Some(action_value.clone()),
                Some("pickup"),
                "info",
                json!({}),
            );
            return Ok(());
        }

        if self.layout.button_recipe_indicators.contains(&target) && agent.held.is_none() {
            self.activate_button(target, agent_id, action_value);
            return Ok(());
        }

        if self.layout.pots.contains(&target) {
            if let Some(ingredient_index) = agent.held.as_deref().and_then(held_ingredient_index) {
                if !self.state.soup_ready && self.state.cooking_ticks == 0 {
                    if pot_total(&self.state.pot_ingredients) < MAX_POT_SLOTS {
                        *self
                            .state
                            .pot_ingredients
                            .entry(ingredient_index)
                            .or_insert(0) += 1;
                        self.state.agents.get_mut(agent_id).unwrap().held = None;
                        self.state.runtime_metrics.ingredients_added += 1;
                        self.apply_shaped_reward("placement_in_pot");
                        self.append_event(
                            "state_transition",
                            format!(
                                "PotIngredientAdded(index={ingredient_index},pot={})",
                                compact_pot(&self.state.pot_ingredients)
                            ),
                            Some(action_value.clone()),
                            None,
                            "info",
                            json!({"pot_ingredients": self.state.pot_ingredients}),
                        );
                        if !self.resolved.start_cooking_interaction && self.pot_matches_recipe() {
                            self.start_cooking(action_value);
                        }
                    }
                    return Ok(());
                }
            }
            if self.resolved.start_cooking_interaction
                && agent.held.is_none()
                && !self.state.soup_ready
                && self.state.cooking_ticks == 0
                && self.pot_matches_recipe()
            {
                self.start_cooking(action_value);
                return Ok(());
            }
            if self.state.soup_ready && agent.held.is_none() {
                self.state.agents.get_mut(agent_id).unwrap().held = Some("soup".to_string());
                self.state.soup_ready = false;
                self.state.pot_ingredients.clear();
                self.append_event(
                    "action_applied",
                    format!("ItemPicked({agent_id},soup)"),
                    Some(action_value.clone()),
                    Some("pickup"),
                    "info",
                    json!({}),
                );
                return Ok(());
            }
            if self.state.soup_ready && agent.held.as_deref() == Some("dish") {
                self.state.agents.get_mut(agent_id).unwrap().held =
                    Some("plated_soup".to_string());
                self.state.soup_ready = false;
                self.state.pot_ingredients.clear();
                self.state.cooked_recipe_id = Some(self.state.active_recipe_id.clone());
                self.state.runtime_metrics.soups_plated += 1;
                self.apply_shaped_reward("plate_pickup");
                self.append_event(
                    "action_applied",
                    format!("ItemPlated({agent_id},soup)"),
                    Some(action_value.clone()),
                    Some("plate"),
                    "info",
                    json!({"recipe_id": self.state.cooked_recipe_id}),
                );
                return Ok(());
            }
        }

        if self.layout.serve_tiles.contains(&target)
            && matches!(agent.held.as_deref(), Some("soup" | "plated_soup"))
        {
            self.handle_delivery(agent_id, action_value);
            return Ok(());
        }

        if self.layout.counters.contains(&target) {
            self.interact_counter(agent_id, target, action_value);
            return Ok(());
        }

        self.state.runtime_metrics.interaction_no_effects += 1;
        self.append_event(
            "rule_violation",
            format!("InteractNoEffect({agent_id})"),
            Some(action_value.clone()),
            None,
            "warn",
            json!({"target": target}),
        );
        Ok(())
    }

    fn start_cooking(&mut self, action_value: &Value) {
        self.state.cooking_ticks = self.state.cook_time;
        self.state.runtime_metrics.cook_starts += 1;
        self.apply_shaped_reward("pot_start_cooking");
        self.append_event(
            "state_transition",
            format!(
                "CookStart(recipe={},ticks={})",
                self.state.active_recipe_id, self.state.cooking_ticks
            ),
            Some(action_value.clone()),
            None,
            "info",
            json!({
                "recipe_id": self.state.active_recipe_id,
                "cooking_ticks": self.state.cooking_ticks,
            }),
        );
    }

    fn activate_button(&mut self, target: Position, agent_id: &str, action_value: &Value) {
        let key = position_key(target);
        self.state
            .button_activation_ticks
            .insert(key.clone(), self.resolved.indicator_activation_time);
        self.state.runtime_metrics.button_activations += 1;
        if self.resolved.indicator_activation_cost > 0.0 {
            let penalty = -self.resolved.indicator_activation_cost;
            self.add_reward(penalty, format!("ButtonActivationCost({penalty})"));
        }
        self.append_event(
            "state_transition",
            format!("ButtonActivated({agent_id},{key})"),
            Some(action_value.clone()),
            None,
            "info",
            json!({"ticks": self.resolved.indicator_activation_time}),
        );
    }

    fn interact_counter(&mut self, agent_id: &str, target: Position, action_value: &Value) {
        let held = self.state.agents[agent_id].held.clone();
        let on_counter = self.state.counter_items.get(&target).cloned();
        if let (Some(item), None) = (held.as_ref(), on_counter.as_ref()) {
            self.state.counter_items.insert(target, item.clone());
            self.state.agents.get_mut(agent_id).unwrap().held = None;
            self.append_event(
                "action_applied",
                format!("ItemPlaced({agent_id},counter,{item})"),
                Some(action_value.clone()),
                Some("place"),
                "info",
                json!({"counter": target, "item": item}),
            );
            return;
        }
        if held.is_none() {
            if let Some(item) = on_counter {
                self.state.agents.get_mut(agent_id).unwrap().held = Some(item.clone());
                self.state.counter_items.remove(&target);
                self.state.runtime_metrics.counter_handoffs += 1;
                self.append_event(
                    "action_applied",
                    format!("ItemPicked({agent_id},{item},counter)"),
                    Some(action_value.clone()),
                    Some("pickup"),
                    "info",
                    json!({"counter": target, "item": item}),
                );
                return;
            }
        }
        self.state.runtime_metrics.interaction_no_effects += 1;
        self.append_event(
            "rule_violation",
            format!("InteractBlocked({agent_id},counter)"),
            Some(action_value.clone()),
            None,
            "warn",
            json!({"counter": target}),
        );
    }

    fn handle_delivery(&mut self, agent_id: &str, action_value: &Value) {
        self.state.runtime_metrics.delivery_attempts += 1;
        let delivered_recipe = self
            .state
            .cooked_recipe_id
            .clone()
            .unwrap_or_else(|| self.state.active_recipe_id.clone());
        let correct = delivered_recipe == self.state.active_recipe_id;
        if !correct && self.resolved.wrong_delivery_penalty < 0.0 {
            let penalty = self.resolved.wrong_delivery_penalty;
            self.state.agents.get_mut(agent_id).unwrap().held = None;
            self.state.runtime_metrics.wrong_deliveries += 1;
            self.add_reward(
                penalty,
                format!(
                    "WrongDelivery({delivered_recipe}!={})",
                    self.state.active_recipe_id
                ),
            );
            self.append_event(
                "rule_violation",
                format!(
                    "WrongDelivery({agent_id},{delivered_recipe}!={})",
                    self.state.active_recipe_id
                ),
                Some(action_value.clone()),
                None,
                "warn",
                json!({}),
            );
            return;
        }

        self.state.deliveries += 1;
        self.state.agents.get_mut(agent_id).unwrap().held = None;
        self.state.cooked_recipe_id = None;
        self.state.delivery_success_flag = true;
        if correct {
            self.state.runtime_metrics.correct_deliveries += 1;
        } else {
            self.state.runtime_metrics.wrong_deliveries += 1;
        }
        self.add_reward(
            DELIVERY_REWARD,
            format!(
                "RewardDelta({DELIVERY_REWARD:.2},total={:.2})",
                self.state.private.total_reward + DELIVERY_REWARD
            ),
        );
        self.append_event(
            "achievement",
            format!("Delivery({agent_id},{})", self.state.active_recipe_id),
            Some(action_value.clone()),
            None,
            "info",
            json!({"deliveries": self.state.deliveries, "delivered_recipe": delivered_recipe}),
        );
        if self.state.deliveries >= self.resolved.target_deliveries {
            self.terminate_success();
        } else if self.resolved.resample_on_delivery {
            self.resample_recipe();
        }
    }

    fn advance_cooking(&mut self) {
        if self.state.cooking_ticks == 0 || self.state.soup_ready {
            return;
        }
        self.state.cooking_ticks -= 1;
        if self.state.cooking_ticks == 0 {
            self.state.soup_ready = true;
            self.state.cooked_recipe_id = Some(self.state.active_recipe_id.clone());
            self.state.runtime_metrics.soups_cooked += 1;
            self.append_event(
                "state_transition",
                format!("CookComplete(recipe={})", self.state.active_recipe_id),
                None,
                None,
                "info",
                json!({
                    "pot_ingredients": self.state.pot_ingredients,
                    "recipe_id": self.state.cooked_recipe_id,
                }),
            );
        }
    }

    fn resample_recipe(&mut self) {
        if self.resolved.recipe_pool.len() <= 1 {
            return;
        }
        let mut choices = self
            .resolved
            .recipe_pool
            .iter()
            .filter(|recipe| recipe.as_str() != self.state.active_recipe_id.as_str())
            .cloned()
            .collect::<Vec<_>>();
        if choices.is_empty() {
            choices = self.resolved.recipe_pool.clone();
        }
        let next_recipe = choices[self.state.rng.index(choices.len())].clone();
        let (ingredients, cook_time) = active_recipe_parameters(&self.resolved, &next_recipe);
        self.state.active_recipe_id = next_recipe.clone();
        self.state.recipe_ingredients = ingredients;
        self.state.required_onions = self
            .state
            .recipe_ingredients
            .iter()
            .filter(|index| **index == 0)
            .count() as u8;
        self.state.cook_time = cook_time;
        self.state.pot_ingredients.clear();
        self.state.cooking_ticks = 0;
        self.state.soup_ready = false;
        self.state.cooked_recipe_id = None;
        self.append_event(
            "state_transition",
            format!("RecipeResampled({next_recipe})"),
            None,
            None,
            "info",
            json!({
                "active_recipe_id": next_recipe,
                "recipe_ingredients": self.state.recipe_ingredients,
            }),
        );
    }

    fn terminate_success(&mut self) {
        self.state.private.terminated = true;
        self.state.terminal_reason = Some("target_deliveries".to_string());
        self.append_event(
            "terminal",
            "Terminal(success)".to_string(),
            None,
            Some("success"),
            "info",
            json!({}),
        );
    }

    fn maybe_truncate(&mut self) {
        if self.state.private.terminated {
            return;
        }
        if self.state.private.step_index >= self.resolved.max_steps {
            self.state.private.truncated = true;
            self.state.terminal_reason = Some("max_steps".to_string());
            self.append_event(
                "terminal",
                "Terminal(truncated)".to_string(),
                None,
                Some("truncated"),
                "info",
                json!({}),
            );
        }
    }

    fn pot_matches_recipe(&self) -> bool {
        self.state.pot_ingredients == sorted_counts(&self.state.recipe_ingredients)
    }

    fn apply_shaped_reward(&mut self, key: &str) {
        if !self.resolved.shaped_rewards {
            return;
        }
        let reward = match key {
            "placement_in_pot" => 0.15,
            "pot_start_cooking" => 0.25,
            "dish_pickup" => 0.25,
            "plate_pickup" => 0.15,
            _ => 0.0,
        };
        if reward > 0.0 {
            self.add_reward(reward, format!("ShapedReward({key})"));
        }
    }

    fn add_reward(&mut self, reward: f64, message: String) {
        self.state.private.reward_last += reward;
        self.state.private.total_reward += reward;
        self.append_event(
            "resource_delta",
            message,
            None,
            None,
            "info",
            json!({
                "reward": reward,
                "total_reward": self.state.private.total_reward,
            }),
        );
    }

    fn decay_button_ticks(&mut self) {
        self.state.button_activation_ticks = self
            .state
            .button_activation_ticks
            .iter()
            .filter_map(|(key, ticks)| {
                if *ticks > 1 {
                    Some((key.clone(), ticks - 1))
                } else {
                    None
                }
            })
            .collect();
    }

    pub fn readout(&self) -> Result<Readout, String> {
        let ascii_rows = self.render_ascii_rows();
        let observations = self
            .resolved
            .agent_ids
            .iter()
            .map(|agent_id| {
                self.observation(agent_id, &ascii_rows)
                    .map(|observation| (agent_id.clone(), observation))
            })
            .collect::<Result<BTreeMap<_, _>, _>>()?;
        let agent_count = self.resolved.agent_ids.len().max(1) as f64;
        let rewards = self
            .resolved
            .agent_ids
            .iter()
            .map(|agent_id| {
                (
                    agent_id.clone(),
                    self.state.private.reward_last / agent_count,
                )
            })
            .collect();
        let done = self.state.private.terminated || self.state.private.truncated;
        let mut dones = self
            .resolved
            .agent_ids
            .iter()
            .map(|agent_id| (agent_id.clone(), done))
            .collect::<BTreeMap<_, _>>();
        dones.insert("__all__".to_string(), done);
        Ok(Readout {
            schema: "gamebench.overcooked_v2.readout.v2".to_string(),
            env_family: ENV_FAMILY.to_string(),
            task_id: self.resolved.task_id.clone(),
            scenario_id: self.resolved.scenario_id.clone(),
            observation_profile: self.resolved.observation_profile.clone(),
            public: self.public_state(),
            private: self.state.private.clone(),
            observations,
            rewards,
            dones,
            ascii: ascii_rows.join("\n"),
            grid_hash: self.resolved.config_hash.clone(),
            nev_cursor: self.events.len(),
            joint_valid_actions: self.joint_valid_actions(),
            metrics: self.state.runtime_metrics.clone(),
        })
    }

    pub fn public_state(&self) -> PublicState {
        PublicState {
            agents: self.state.agents.clone(),
            pot_ingredients: self
                .state
                .pot_ingredients
                .iter()
                .map(|(key, value)| (key.to_string(), *value))
                .collect(),
            pot_onions: self.state.pot_ingredients.get(&0).copied().unwrap_or(0),
            cooking_ticks: self.state.cooking_ticks,
            soup_ready: self.state.soup_ready,
            deliveries: self.state.deliveries,
            recipe_id: self.state.active_recipe_id.clone(),
            active_recipe_id: self.state.active_recipe_id.clone(),
            recipe_ingredients: self.state.recipe_ingredients.clone(),
            cooked_recipe_id: self.state.cooked_recipe_id.clone(),
            counter_items: self
                .state
                .counter_items
                .iter()
                .map(|(position, item)| (position_key(*position), item.clone()))
                .collect(),
            button_activation_ticks: self.state.button_activation_ticks.clone(),
            delivery_success_flag: self.state.delivery_success_flag,
            done: self.state.private.terminated,
        }
    }

    fn observation(&self, agent_id: &str, ascii_rows: &[String]) -> Result<Value, String> {
        let agent = self
            .state
            .agents
            .get(agent_id)
            .ok_or_else(|| format!("unknown observation agent {agent_id:?}"))?;
        let recipe_visible = self.recipe_visible_for(agent_id);
        let visible_agents = self
            .state
            .agents
            .iter()
            .filter(|(_, other)| self.in_view(agent.position, other.position))
            .map(|(other_id, other)| {
                serde_json::to_value(other)
                    .map(|value| (other_id.clone(), value))
                    .map_err(|error| format!("serialize visible agent: {error}"))
            })
            .collect::<Result<BTreeMap<_, _>, _>>()?;
        let pot_visible = self
            .layout
            .pots
            .iter()
            .any(|pot| self.in_view(agent.position, *pot));
        let visible_pot = if pot_visible {
            Some(
                self.state
                    .pot_ingredients
                    .iter()
                    .map(|(key, value)| (key.to_string(), *value))
                    .collect::<BTreeMap<_, _>>(),
            )
        } else {
            None
        };
        let visible_onions = if pot_visible {
            Some(self.state.pot_ingredients.get(&0).copied().unwrap_or(0))
        } else {
            None
        };
        let agent_index = agent_id
            .split_once('_')
            .and_then(|(_, suffix)| suffix.parse::<u32>().ok())
            .unwrap_or(0);
        Ok(json!({
            "agent_id": agent_id,
            "agent_index": agent_index,
            "ascii": self.mask_ascii(ascii_rows, agent.position),
            "position": agent.position,
            "facing": agent.facing,
            "held": agent.held,
            "pot_ingredients": visible_pot,
            "pot_onions": visible_onions,
            "cooking_ticks": self.state.cooking_ticks,
            "soup_ready": self.state.soup_ready,
            "recipe_id": if recipe_visible { Some(self.state.active_recipe_id.clone()) } else { None },
            "recipe_ingredients": if recipe_visible { Some(self.state.recipe_ingredients.clone()) } else { None },
            "required_onions": if recipe_visible { Some(self.state.required_onions) } else { None },
            "recipe_indicator_visible": recipe_visible,
            "delivery_success_flag": if self.resolved.indicate_successful_delivery { Some(self.state.delivery_success_flag) } else { None },
            "urgency_active": self.urgency_active(),
            "steps_remaining": self.steps_remaining(),
            "partial_obs": self.resolved.partial_obs,
            "view_radius": self.resolved.view_radius,
            "visible_agents": visible_agents,
            "valid_actions": self.valid_actions(agent_id),
            "observation_profile": self.resolved.observation_profile,
        }))
    }

    fn render_ascii_rows(&self) -> Vec<String> {
        let mut rows = Vec::new();
        for row in 0..self.layout.height {
            let mut characters = Vec::new();
            for col in 0..self.layout.width {
                let position = Position::new(row, col);
                let mut character = if self.layout.walls.contains(&position) {
                    '#'
                } else if let Some(index) = self.layout.ingredient_piles.get(&position) {
                    char::from_digit(*index as u32, 10).unwrap_or('?')
                } else if self.layout.dish_dispensers.contains(&position) {
                    'D'
                } else if self.layout.pots.contains(&position) {
                    'P'
                } else if self.layout.serve_tiles.contains(&position) {
                    'S'
                } else if self.layout.recipe_indicators.contains(&position) {
                    'R'
                } else if self.layout.button_recipe_indicators.contains(&position) {
                    if self
                        .state
                        .button_activation_ticks
                        .get(&position_key(position))
                        .copied()
                        .unwrap_or(0)
                        > 0
                    {
                        'L'
                    } else {
                        'l'
                    }
                } else if self.layout.counters.contains(&position) {
                    'C'
                } else if let Some(item) = self.state.counter_items.get(&position) {
                    held_ingredient_index(item)
                        .and_then(|index| char::from_digit(index as u32, 10))
                        .unwrap_or_else(|| item.chars().next().unwrap_or('?'))
                } else {
                    '.'
                };
                if let Some(agent_id) = self.agent_at(position) {
                    character = agent_id
                        .split_once('_')
                        .and_then(|(_, suffix)| suffix.chars().next())
                        .unwrap_or('?');
                }
                characters.push(character);
            }
            rows.push(characters.into_iter().collect());
        }
        rows
    }

    fn mask_ascii(&self, ascii_rows: &[String], observer: Position) -> String {
        if !self.resolved.partial_obs {
            return ascii_rows.join("\n");
        }
        ascii_rows
            .iter()
            .enumerate()
            .map(|(row, text)| {
                text.chars()
                    .enumerate()
                    .map(|(col, character)| {
                        if self.in_view(observer, Position::new(row as i32, col as i32)) {
                            character
                        } else {
                            '#'
                        }
                    })
                    .collect::<String>()
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    fn recipe_visible_for(&self, agent_id: &str) -> bool {
        if !self.resolved.hidden_recipe {
            return true;
        }
        let Some(agent) = self.state.agents.get(agent_id) else {
            return false;
        };
        if self
            .layout
            .recipe_indicators
            .iter()
            .any(|indicator| self.in_view(agent.position, *indicator))
        {
            return true;
        }
        self.layout.button_recipe_indicators.iter().any(|button| {
            self.state
                .button_activation_ticks
                .get(&position_key(*button))
                .copied()
                .unwrap_or(0)
                > 0
                && self.in_view(agent.position, *button)
        })
    }

    fn in_view(&self, observer: Position, target: Position) -> bool {
        if !self.resolved.partial_obs || self.resolved.view_radius <= 0 {
            return true;
        }
        observer.chebyshev(target) <= self.resolved.view_radius
    }

    pub fn valid_actions(&self, agent_id: &str) -> Vec<Action> {
        if self.state.private.terminated || self.state.private.truncated {
            return Vec::new();
        }
        let Some(agent) = self.state.agents.get(agent_id) else {
            return Vec::new();
        };
        let mut actions = vec![Action::Wait];
        for direction in Direction::ALL {
            let target = agent.position.step(direction);
            if self.agent_at(target).is_some() {
                continue;
            }
            if self.is_walkable(target) || self.layout.is_fixture(target) {
                actions.push(Action::Move { direction });
            }
        }
        actions.push(Action::Interact);
        actions
    }

    pub fn joint_valid_actions(&self) -> BTreeMap<String, Vec<Action>> {
        self.resolved
            .agent_ids
            .iter()
            .map(|agent_id| (agent_id.clone(), self.valid_actions(agent_id)))
            .collect()
    }

    pub fn steps_remaining(&self) -> u32 {
        self.resolved
            .max_steps
            .saturating_sub(self.state.private.step_index)
    }

    pub fn urgency_active(&self) -> bool {
        self.steps_remaining() < self.resolved.urgency_cutoff
    }

    fn is_walkable(&self, position: Position) -> bool {
        self.layout.is_static_walkable(position)
            && !self.state.counter_items.contains_key(&position)
    }

    fn agent_at(&self, position: Position) -> Option<String> {
        self.state
            .agents
            .iter()
            .find_map(|(agent_id, agent)| {
                (agent.position == position).then(|| agent_id.clone())
            })
    }

    pub fn planner_walkable(&self, position: Position, moving_agent: &str) -> bool {
        self.is_walkable(position)
            && self
                .state
                .agents
                .iter()
                .all(|(agent_id, agent)| agent_id == moving_agent || agent.position != position)
    }

    pub fn checkpoint_json(&self) -> Result<String, String> {
        serde_json::to_string(&self.checkpoint())
            .map_err(|error| format!("serialize Overcooked checkpoint: {error}"))
    }

    pub fn checkpoint_bytes(&self) -> Result<Vec<u8>, String> {
        self.checkpoint_json().map(String::into_bytes)
    }

    pub fn checkpoint_digest(&self) -> Result<String, String> {
        self.checkpoint_bytes().map(|bytes| sha256_hex(&bytes))
    }

    fn checkpoint(&self) -> Checkpoint {
        Checkpoint {
            schema_version: CHECKPOINT_SCHEMA.to_string(),
            env_family: ENV_FAMILY.to_string(),
            episode_id: self.resolved.episode_id.clone(),
            step_index: self.state.private.step_index,
            nev_cursor: self.events.len(),
            config_hash: self.resolved.config_hash.clone(),
            resolved: self.resolved.clone(),
            layout: self.layout.clone(),
            dynamic: self.state.clone(),
            events: self.events.clone(),
        }
    }

    pub fn from_checkpoint_json(checkpoint_json: &str) -> Result<Self, String> {
        let checkpoint: Checkpoint = serde_json::from_str(checkpoint_json)
            .map_err(|error| format!("invalid Overcooked checkpoint JSON: {error}"))?;
        validate_checkpoint(&checkpoint)?;
        Ok(Self {
            resolved: checkpoint.resolved,
            layout: checkpoint.layout,
            state: checkpoint.dynamic,
            events: checkpoint.events,
        })
    }

    pub fn restore_checkpoint_json(&mut self, checkpoint_json: &str) -> Result<usize, String> {
        let restored = Self::from_checkpoint_json(checkpoint_json)?;
        let cursor = restored.events.len();
        *self = restored;
        Ok(cursor)
    }

    pub fn clone_for_sim(&self) -> Result<Self, String> {
        Self::from_checkpoint_json(&self.checkpoint_json()?)
    }

    pub fn state_digest(&self) -> Result<String, String> {
        let value = json!({
            "resolved": self.resolved,
            "layout": self.layout,
            "dynamic": self.state,
            "nev_cursor": self.events.len(),
        });
        serde_json::to_vec(&value)
            .map(|bytes| sha256_hex(&bytes))
            .map_err(|error| format!("serialize Overcooked state digest input: {error}"))
    }

    pub fn terminal_metrics(&self) -> Result<TerminalMetrics, String> {
        Ok(TerminalMetrics {
            success: self.state.private.terminated
                && self.state.deliveries >= self.resolved.target_deliveries,
            terminated: self.state.private.terminated,
            truncated: self.state.private.truncated,
            terminal_reason: self.state.terminal_reason.clone(),
            steps: self.state.private.step_index,
            max_steps: self.resolved.max_steps,
            deliveries: self.state.deliveries,
            target_deliveries: self.resolved.target_deliveries,
            total_reward: self.state.private.total_reward,
            invalid_action_count: self.state.private.invalid_action_count,
            event_count: self.events.len(),
            runtime: self.state.runtime_metrics.clone(),
            state_digest: self.state_digest()?,
        })
    }

    pub fn resolved(&self) -> &ResolvedTask {
        &self.resolved
    }

    pub fn layout(&self) -> &ParsedLayout {
        &self.layout
    }

    pub fn agents(&self) -> &BTreeMap<String, AgentState> {
        &self.state.agents
    }

    pub fn events(&self) -> &[EventRecord] {
        &self.events
    }

    pub fn events_since(&self, cursor: usize) -> &[EventRecord] {
        self.events.get(cursor..).unwrap_or_default()
    }

    pub fn runtime_metrics(&self) -> &RuntimeMetrics {
        &self.state.runtime_metrics
    }

    pub fn soup_ready(&self) -> bool {
        self.state.soup_ready
    }

    pub fn cooking_ticks(&self) -> u32 {
        self.state.cooking_ticks
    }

    pub fn counter_items(&self) -> &BTreeMap<Position, String> {
        &self.state.counter_items
    }

    pub fn active_recipe_id(&self) -> &str {
        &self.state.active_recipe_id
    }

    pub fn recipe_ingredients(&self) -> &[u8] {
        &self.state.recipe_ingredients
    }

    pub fn is_recipe_visible(&self, agent_id: &str) -> bool {
        self.recipe_visible_for(agent_id)
    }

    fn apply_random_reset(&mut self) -> Result<(), String> {
        let mut walkable = self.layout.walkable_tiles();
        self.state.rng.shuffle(&mut walkable);
        if walkable.len() < self.resolved.agent_ids.len() {
            return Err("not enough walkable tiles for random_reset".to_string());
        }
        for agent_id in &self.resolved.agent_ids {
            let position = walkable
                .pop()
                .ok_or_else(|| "random_reset exhausted walkable tiles".to_string())?;
            let facing = Direction::ALL[self.state.rng.index(Direction::ALL.len())];
            let roll = self.state.rng.unit();
            let held = if roll < 0.5 {
                None
            } else if roll < 0.6 {
                Some("dish".to_string())
            } else if roll < 0.85 {
                Some(ingredient_name(
                    self.state.rng.index(self.layout.num_ingredients as usize) as u8,
                ))
            } else {
                Some("soup".to_string())
            };
            self.state.agents.insert(
                agent_id.clone(),
                AgentState {
                    agent_id: agent_id.clone(),
                    position,
                    facing,
                    held,
                },
            );
        }
        if !self.layout.pots.is_empty() {
            let roll = self.state.rng.unit();
            if roll >= 0.4 {
                let ingredient_count = self.layout.num_ingredients.max(1) as usize;
                let slots = if roll < 0.75 {
                    1 + self.state.rng.index(MAX_POT_SLOTS as usize)
                } else {
                    MAX_POT_SLOTS as usize
                };
                for _ in 0..slots {
                    let ingredient = self.state.rng.index(ingredient_count) as u8;
                    *self.state.pot_ingredients.entry(ingredient).or_insert(0) += 1;
                }
                if roll < 0.9 && roll >= 0.75 {
                    self.state.cooking_ticks = 1 + self.state.rng.index(20) as u32;
                } else if roll >= 0.9 {
                    self.state.soup_ready = true;
                    self.state.cooked_recipe_id = Some(self.state.active_recipe_id.clone());
                }
            }
        }
        let counter_positions = self.layout.counters.iter().copied().collect::<Vec<_>>();
        for counter in counter_positions {
            let roll = self.state.rng.unit();
            let item = if roll < 0.5 {
                None
            } else if roll < 0.6 {
                Some("dish".to_string())
            } else if roll < 0.9 {
                Some(ingredient_name(
                    self.state
                        .rng
                        .index(self.layout.num_ingredients.max(1) as usize) as u8,
                ))
            } else {
                Some("soup".to_string())
            };
            if let Some(item) = item {
                self.state.counter_items.insert(counter, item);
            }
        }
        self.append_event(
            "state_transition",
            "RandomResetApplied".to_string(),
            None,
            None,
            "info",
            json!({
                "agents": self.state.agents,
                "pot_ingredients": self.state.pot_ingredients,
                "counter_items": self.state.counter_items.iter().map(|(position, item)| (position_key(*position), item.clone())).collect::<BTreeMap<_, _>>(),
            }),
        );
        Ok(())
    }

    fn append_event(
        &mut self,
        kind: &str,
        message: String,
        action: Option<Value>,
        transition: Option<&str>,
        severity: &str,
        payload: Value,
    ) {
        self.events.push(EventRecord {
            step_index: self.state.private.step_index,
            tick: self.state.private.step_index,
            episode_id: self.resolved.episode_id.clone(),
            kind: kind.to_string(),
            action,
            transition: transition.map(str::to_string),
            severity: severity.to_string(),
            message,
            payload,
        });
    }
}

fn initial_agents(
    resolved: &ResolvedTask,
    layout: &ParsedLayout,
    rng: &mut DeterministicRng,
) -> Result<BTreeMap<String, AgentState>, String> {
    let mut agents = BTreeMap::new();
    if resolved.stochastic_spawn {
        let mut walkable = layout.walkable_tiles();
        rng.shuffle(&mut walkable);
        if walkable.len() < resolved.agent_ids.len() {
            return Err("not enough walkable tiles for stochastic_spawn".to_string());
        }
        for agent_id in &resolved.agent_ids {
            let position = walkable
                .pop()
                .ok_or_else(|| "stochastic_spawn exhausted walkable tiles".to_string())?;
            agents.insert(
                agent_id.clone(),
                AgentState {
                    agent_id: agent_id.clone(),
                    position,
                    facing: Direction::ALL[rng.index(Direction::ALL.len())],
                    held: None,
                },
            );
        }
        return Ok(agents);
    }
    for agent_id in &resolved.agent_ids {
        let position = layout
            .agent_starts
            .get(agent_id)
            .copied()
            .ok_or_else(|| format!("layout missing start for {agent_id}"))?;
        agents.insert(
            agent_id.clone(),
            AgentState {
                agent_id: agent_id.clone(),
                position,
                facing: Direction::South,
                held: None,
            },
        );
    }
    Ok(agents)
}

fn validate_checkpoint(checkpoint: &Checkpoint) -> Result<(), String> {
    if checkpoint.schema_version != CHECKPOINT_SCHEMA {
        return Err(format!(
            "unsupported Overcooked checkpoint schema {:?}",
            checkpoint.schema_version
        ));
    }
    if checkpoint.env_family != ENV_FAMILY {
        return Err(format!(
            "checkpoint env_family must be {ENV_FAMILY:?}, got {:?}",
            checkpoint.env_family
        ));
    }
    if checkpoint.episode_id != checkpoint.resolved.episode_id
        || checkpoint.dynamic.private.episode_id != checkpoint.resolved.episode_id
    {
        return Err("checkpoint episode_id fields disagree".to_string());
    }
    if checkpoint.config_hash != checkpoint.resolved.config_hash
        || checkpoint.dynamic.private.config_hash != checkpoint.resolved.config_hash
    {
        return Err("checkpoint config_hash fields disagree".to_string());
    }
    if checkpoint.step_index != checkpoint.dynamic.private.step_index {
        return Err("checkpoint step_index fields disagree".to_string());
    }
    if checkpoint.nev_cursor != checkpoint.events.len() {
        return Err("checkpoint nev_cursor does not match event count".to_string());
    }
    if !(2..=4).contains(&checkpoint.resolved.agent_ids.len()) {
        return Err("checkpoint must contain two to four agents".to_string());
    }
    let expected_agents = checkpoint
        .resolved
        .agent_ids
        .iter()
        .cloned()
        .collect::<BTreeSet<_>>();
    if expected_agents.len() != checkpoint.resolved.agent_ids.len() {
        return Err("checkpoint resolved task contains duplicate agent ids".to_string());
    }
    let actual_agents = checkpoint
        .dynamic
        .agents
        .keys()
        .cloned()
        .collect::<BTreeSet<_>>();
    if expected_agents != actual_agents {
        return Err("checkpoint agent set does not match resolved task".to_string());
    }
    let mut occupied = BTreeSet::new();
    for agent in checkpoint.dynamic.agents.values() {
        if !checkpoint.layout.is_static_walkable(agent.position) {
            return Err(format!(
                "checkpoint agent {} is not on a walkable tile {:?}",
                agent.agent_id, agent.position
            ));
        }
        if !occupied.insert(agent.position) {
            return Err("checkpoint contains overlapping agents".to_string());
        }
    }
    if checkpoint.dynamic.recipe_ingredients.is_empty()
        || checkpoint.dynamic.recipe_ingredients.len() > MAX_POT_SLOTS as usize
    {
        return Err("checkpoint recipe_ingredients has invalid cardinality".to_string());
    }
    Ok(())
}

fn active_recipe_parameters(resolved: &ResolvedTask, recipe_id: &str) -> (Vec<u8>, u32) {
    if recipe_id == resolved.recipe_id {
        return (resolved.recipe_ingredients.clone(), resolved.cook_time);
    }
    match recipe_id {
        "simple_soup" => (vec![0], 2),
        "trio_soup" => (vec![0, 0, 0], 3),
        "mixed_soup" => (vec![0, 1, 1], 3),
        "tomato_trio" => (vec![1, 1, 1], 3),
        "fun_coord_0" => (vec![0, 0, 2], 3),
        "fun_coord_1" => (vec![1, 1, 3], 3),
        "more_fun_coord_1" => (vec![0, 2, 2], 3),
        _ => (vec![0], 2),
    }
}

fn pot_total(ingredients: &BTreeMap<u8, u8>) -> u8 {
    ingredients.values().copied().sum()
}

fn ingredient_name(index: u8) -> String {
    format!("ing_{index}")
}

fn held_ingredient_index(held: &str) -> Option<u8> {
    if held == "onion" {
        return Some(0);
    }
    held.strip_prefix("ing_")?.parse().ok()
}

fn position_key(position: Position) -> String {
    format!("{},{}", position.row(), position.col())
}

fn compact_pot(ingredients: &BTreeMap<u8, u8>) -> String {
    let entries = ingredients
        .iter()
        .map(|(key, value)| format!("{key}:{value}"))
        .collect::<Vec<_>>()
        .join(", ");
    format!("{{{entries}}}")
}

fn direction_name(direction: Direction) -> &'static str {
    match direction {
        Direction::North => "north",
        Direction::South => "south",
        Direction::East => "east",
        Direction::West => "west",
    }
}
