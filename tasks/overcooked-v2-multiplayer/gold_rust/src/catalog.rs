use crate::model::{LayoutDocument, ParsedLayout, Position, ResolvedTask};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

pub fn resolve_task(
    task: &Value,
    defaults_dir: &Path,
) -> Result<(ResolvedTask, ParsedLayout), String> {
    let task_object = task
        .as_object()
        .ok_or_else(|| "Overcooked task must be a JSON object".to_string())?;
    let task_id = string_field(task_object, "task_id")
        .or_else(|| string_field(task_object, "scenario_id"))
        .unwrap_or_else(|| "manual".to_string());
    let scenario_id = string_field(task_object, "scenario_id").unwrap_or_else(|| task_id.clone());
    let seed = integer_field(task_object.get("seed"))?.unwrap_or(0);

    let (layout_document, fallback_layout_id) = if let Some(inline) = task_object.get("layout") {
        let document: LayoutDocument = serde_json::from_value(inline.clone())
            .map_err(|error| format!("invalid inline Overcooked layout: {error}"))?;
        let fallback = string_field(task_object, "layout_id")
            .or_else(|| document.layout_id.clone())
            .unwrap_or_else(|| "inline".to_string());
        (document, fallback)
    } else {
        let layout_id = string_field(task_object, "layout_id").unwrap_or_else(|| "demo_tiny".to_string());
        let path = defaults_dir.join("layouts").join(format!("{layout_id}.json"));
        let raw = fs::read_to_string(&path)
            .map_err(|error| format!("read Overcooked layout {}: {error}", path.display()))?;
        let document: LayoutDocument = serde_json::from_str(&raw)
            .map_err(|error| format!("parse Overcooked layout {}: {error}", path.display()))?;
        (document, layout_id)
    };
    let layout = parse_layout(&layout_document, &fallback_layout_id)?;
    let mut agent_ids = layout.agent_starts.keys().cloned().collect::<Vec<_>>();
    agent_ids.sort();
    if !(2..=4).contains(&agent_ids.len()) {
        return Err(format!(
            "Overcooked multiplayer layout {} must define two to four agent starts; found {}",
            layout.layout_id,
            agent_ids.len()
        ));
    }

    let task_rules = task_object
        .get("rules")
        .cloned()
        .unwrap_or_else(|| serde_json::json!({"base": "cooperative_full_obs"}));
    let rules = resolve_rules(&task_rules, defaults_dir)?;
    let recipe_id = rules_value(&rules, "recipe_id")
        .and_then(Value::as_str)
        .map(str::to_string)
        .or_else(|| {
            if layout_document.recipe_pool.is_empty() {
                None
            } else {
                Some(layout_document.recipe_pool[0].clone())
            }
        })
        .unwrap_or_else(|| "simple_soup".to_string());
    let (default_ingredients, default_cook_time) = recipe_defaults(&recipe_id);
    let recipe_ingredients = rules_value(&rules, "recipe_ingredients")
        .map(parse_ingredient_list)
        .transpose()?
        .unwrap_or(default_ingredients);
    if recipe_ingredients.is_empty() || recipe_ingredients.len() > 3 {
        return Err("recipe_ingredients must contain one to three ingredient indices".to_string());
    }
    let cook_time = unsigned_value(rules_value(&rules, "cook_time"))?
        .map(|value| value as u32)
        .unwrap_or(default_cook_time);
    if cook_time == 0 {
        return Err("cook_time must be positive".to_string());
    }
    let required_onions = unsigned_value(rules_value(&rules, "required_onions"))?
        .map(|value| value as u8)
        .unwrap_or_else(|| recipe_ingredients.iter().filter(|index| **index == 0).count() as u8);
    let max_steps = unsigned_value(rules_value(&rules, "max_steps"))?
        .or(unsigned_value(task_object.get("max_steps"))?)
        .unwrap_or(64) as u32;
    if max_steps == 0 {
        return Err("max_steps must be positive".to_string());
    }
    let partial_obs = bool_value(rules_value(&rules, "partial_obs"))?.unwrap_or(false);
    let view_radius = signed_value(rules_value(&rules, "view_radius"))?
        .unwrap_or(if partial_obs { 2 } else { 0 }) as i32;
    let hidden_recipe = bool_value(rules_value(&rules, "hidden_recipe"))?.unwrap_or(false);
    let stochastic_spawn =
        bool_value(rules_value(&rules, "stochastic_spawn"))?.unwrap_or(false);
    let recipe_pool = if let Some(raw) = rules_value(&rules, "recipe_pool") {
        parse_string_list(raw, "recipe_pool")?
    } else if !layout_document.recipe_pool.is_empty() {
        layout_document.recipe_pool.clone()
    } else {
        vec![recipe_id.clone()]
    };
    if recipe_pool.is_empty() {
        return Err("recipe_pool must not be empty".to_string());
    }
    let resample_on_delivery =
        bool_value(rules_value(&rules, "resample_on_delivery"))?.unwrap_or(false);
    let target_deliveries = unsigned_value(rules_value(&rules, "target_deliveries"))?
        .unwrap_or(1) as u32;
    if target_deliveries == 0 {
        return Err("target_deliveries must be positive".to_string());
    }
    let wrong_delivery_penalty =
        float_value(rules_value(&rules, "wrong_delivery_penalty"))?.unwrap_or(0.0);
    let readout_profile = task_object
        .get("readouts")
        .and_then(Value::as_object)
        .and_then(|readouts| readouts.get("profile"))
        .and_then(Value::as_str);
    let observation_profile = rules_value(&rules, "observation_profile")
        .and_then(Value::as_str)
        .or(readout_profile)
        .unwrap_or("symbolic_compact")
        .to_string();
    if observation_profile != "symbolic_compact" {
        return Err(format!(
            "Rust authority currently supports observation_profile=symbolic_compact; requested {observation_profile:?}"
        ));
    }
    let indicator_activation_time =
        unsigned_value(rules_value(&rules, "indicator_activation_time"))?.unwrap_or(10) as u32;
    let indicator_activation_cost =
        float_value(rules_value(&rules, "indicator_activation_cost"))?.unwrap_or(0.0);
    let start_cooking_interaction =
        bool_value(rules_value(&rules, "start_cooking_interaction"))?.unwrap_or(false);
    let op_ingredient_permutations =
        bool_value(rules_value(&rules, "op_ingredient_permutations"))?.unwrap_or(false);
    let indicate_successful_delivery =
        bool_value(rules_value(&rules, "indicate_successful_delivery"))?.unwrap_or(false);
    let shaped_rewards = bool_value(rules_value(&rules, "shaped_rewards"))?.unwrap_or(false);
    let random_reset = bool_value(rules_value(&rules, "random_reset"))?.unwrap_or(false);
    let urgency_cutoff =
        unsigned_value(rules_value(&rules, "urgency_cutoff"))?.unwrap_or(40) as u32;

    let material = format!(
        "overcooked-v2:{task_id}:{seed}:{}:{}:{recipe_id}:{}:{cook_time}:{max_steps}:{}:{view_radius}:{}:{}:{}:{urgency_cutoff}:{}:{}:{target_deliveries}:{}:{observation_profile}:{indicator_activation_time}:{}:{}:{}:{}:{}",
        layout.layout_id,
        agent_ids.join(":"),
        recipe_ingredients
            .iter()
            .map(u8::to_string)
            .collect::<Vec<_>>()
            .join(","),
        py_bool(partial_obs),
        py_bool(hidden_recipe),
        py_bool(stochastic_spawn),
        py_bool(random_reset),
        recipe_pool.join(","),
        py_bool(resample_on_delivery),
        py_float(wrong_delivery_penalty),
        py_float(indicator_activation_cost),
        py_bool(start_cooking_interaction),
        py_bool(op_ingredient_permutations),
        py_bool(indicate_successful_delivery),
        py_bool(shaped_rewards),
    );
    let config_hash = sha256_prefix(&material, 16);
    let episode_id = sha256_prefix(
        &format!(
            "gamebench.overcooked-v2-multiplayer.episode:{task_id}:{seed}:{config_hash}"
        ),
        32,
    );
    let resolved = ResolvedTask {
        task_id,
        scenario_id,
        seed,
        layout_id: layout.layout_id.clone(),
        agent_ids,
        recipe_id,
        recipe_ingredients,
        required_onions,
        cook_time,
        max_steps,
        partial_obs,
        view_radius,
        hidden_recipe,
        stochastic_spawn,
        recipe_pool,
        resample_on_delivery,
        target_deliveries,
        wrong_delivery_penalty,
        observation_profile,
        indicator_activation_time,
        indicator_activation_cost,
        start_cooking_interaction,
        op_ingredient_permutations,
        indicate_successful_delivery,
        shaped_rewards,
        random_reset,
        urgency_cutoff,
        config_hash,
        episode_id,
    };
    Ok((resolved, layout))
}

fn parse_layout(document: &LayoutDocument, fallback_id: &str) -> Result<ParsedLayout, String> {
    if document.ascii.is_empty() {
        return Err("Overcooked layout requires non-empty ascii rows".to_string());
    }
    let layout_id = document
        .layout_id
        .clone()
        .unwrap_or_else(|| fallback_id.to_string());
    let height = document.ascii.len() as i32;
    let width = document
        .ascii
        .iter()
        .map(|row| row.chars().count())
        .max()
        .unwrap_or(0) as i32;
    let mut walls = BTreeSet::new();
    let mut ingredient_piles = BTreeMap::new();
    let mut dish_dispensers = BTreeSet::new();
    let mut pots = BTreeSet::new();
    let mut serve_tiles = BTreeSet::new();
    let mut counters = BTreeSet::new();
    let mut recipe_indicators = BTreeSet::new();
    let mut button_recipe_indicators = BTreeSet::new();
    let mut agent_starts = BTreeMap::new();
    let mut max_ingredient_index: i32 = -1;

    for (row, text) in document.ascii.iter().enumerate() {
        for (col, character) in text.chars().enumerate() {
            let position = Position::new(row as i32, col as i32);
            match character {
                '#' | 'W' => {
                    walls.insert(position);
                }
                'O' => {
                    ingredient_piles.insert(position, 0);
                    max_ingredient_index = max_ingredient_index.max(0);
                }
                'T' => {
                    ingredient_piles.insert(position, 1);
                    max_ingredient_index = max_ingredient_index.max(1);
                }
                '0'..='3' => {
                    agent_starts.insert(format!("agent_{character}"), position);
                }
                '4'..='9' => {
                    let index = character.to_digit(10).unwrap_or_default() as u8;
                    ingredient_piles.insert(position, index);
                    max_ingredient_index = max_ingredient_index.max(index as i32);
                }
                'D' | 'B' => {
                    dish_dispensers.insert(position);
                }
                'P' => {
                    pots.insert(position);
                }
                'S' | 'X' => {
                    serve_tiles.insert(position);
                }
                'C' => {
                    counters.insert(position);
                }
                'R' => {
                    recipe_indicators.insert(position);
                }
                'L' => {
                    button_recipe_indicators.insert(position);
                }
                'A' => {
                    if let Some(index) = (0..4).find(|index| {
                        !agent_starts.contains_key(&format!("agent_{index}"))
                    }) {
                        agent_starts.insert(format!("agent_{index}"), position);
                    }
                }
                _ => {}
            }
        }
    }
    Ok(ParsedLayout {
        layout_id,
        width,
        height,
        walls,
        ingredient_piles,
        dish_dispensers,
        pots,
        serve_tiles,
        counters,
        recipe_indicators,
        button_recipe_indicators,
        agent_starts,
        num_ingredients: (max_ingredient_index + 1).max(1) as u8,
    })
}

fn resolve_rules(task_rules: &Value, defaults_dir: &Path) -> Result<Value, String> {
    let object = task_rules
        .as_object()
        .ok_or_else(|| "Overcooked rules must be a JSON object".to_string())?;
    let base = object
        .get("base")
        .and_then(Value::as_str)
        .unwrap_or("cooperative_full_obs");
    let mut visiting = BTreeSet::new();
    let mut merged = load_rule_profile(base, defaults_dir, &mut visiting)?;
    deep_merge(&mut merged, task_rules.clone());
    Ok(merged)
}

fn load_rule_profile(
    profile: &str,
    defaults_dir: &Path,
    visiting: &mut BTreeSet<String>,
) -> Result<Value, String> {
    if !visiting.insert(profile.to_string()) {
        return Err(format!("cyclic Overcooked rule profile inheritance at {profile:?}"));
    }
    let path = defaults_dir.join("rules").join(format!("{profile}.json"));
    if !path.is_file() {
        visiting.remove(profile);
        return Ok(Value::Object(Map::new()));
    }
    let raw = fs::read_to_string(&path)
        .map_err(|error| format!("read Overcooked rules {}: {error}", path.display()))?;
    let profile_value: Value = serde_json::from_str(&raw)
        .map_err(|error| format!("parse Overcooked rules {}: {error}", path.display()))?;
    let parent = profile_value
        .get("base")
        .and_then(Value::as_str)
        .filter(|parent| *parent != profile);
    let mut merged = if let Some(parent) = parent {
        load_rule_profile(parent, defaults_dir, visiting)?
    } else {
        Value::Object(Map::new())
    };
    deep_merge(&mut merged, profile_value);
    visiting.remove(profile);
    Ok(merged)
}

fn deep_merge(target: &mut Value, overlay: Value) {
    match (target, overlay) {
        (Value::Object(target_object), Value::Object(overlay_object)) => {
            for (key, value) in overlay_object {
                if let Some(existing) = target_object.get_mut(&key) {
                    deep_merge(existing, value);
                } else {
                    target_object.insert(key, value);
                }
            }
        }
        (target_value, overlay_value) => *target_value = overlay_value,
    }
}

fn rules_value<'a>(rules: &'a Value, key: &str) -> Option<&'a Value> {
    rules
        .get("overrides")
        .and_then(Value::as_object)
        .and_then(|overrides| overrides.get(key))
        .or_else(|| rules.get(key))
}

fn recipe_defaults(recipe_id: &str) -> (Vec<u8>, u32) {
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

fn parse_ingredient_list(value: &Value) -> Result<Vec<u8>, String> {
    value
        .as_array()
        .ok_or_else(|| "recipe_ingredients must be an array".to_string())?
        .iter()
        .map(|item| {
            item.as_u64()
                .and_then(|index| u8::try_from(index).ok())
                .ok_or_else(|| "recipe ingredient indices must be unsigned bytes".to_string())
        })
        .collect()
}

fn parse_string_list(value: &Value, field: &str) -> Result<Vec<String>, String> {
    value
        .as_array()
        .ok_or_else(|| format!("{field} must be an array"))?
        .iter()
        .map(|item| {
            item.as_str()
                .map(str::to_string)
                .ok_or_else(|| format!("{field} entries must be strings"))
        })
        .collect()
}

fn string_field(object: &Map<String, Value>, key: &str) -> Option<String> {
    object.get(key).and_then(Value::as_str).map(str::to_string)
}

fn integer_field(value: Option<&Value>) -> Result<Option<u64>, String> {
    unsigned_value(value)
}

fn unsigned_value(value: Option<&Value>) -> Result<Option<u64>, String> {
    match value {
        None => Ok(None),
        Some(raw) => raw
            .as_u64()
            .map(Some)
            .ok_or_else(|| format!("expected unsigned integer, got {raw}")),
    }
}

fn signed_value(value: Option<&Value>) -> Result<Option<i64>, String> {
    match value {
        None => Ok(None),
        Some(raw) => raw
            .as_i64()
            .map(Some)
            .ok_or_else(|| format!("expected integer, got {raw}")),
    }
}

fn float_value(value: Option<&Value>) -> Result<Option<f64>, String> {
    match value {
        None => Ok(None),
        Some(raw) => raw
            .as_f64()
            .map(Some)
            .ok_or_else(|| format!("expected number, got {raw}")),
    }
}

fn bool_value(value: Option<&Value>) -> Result<Option<bool>, String> {
    match value {
        None => Ok(None),
        Some(raw) => raw
            .as_bool()
            .map(Some)
            .ok_or_else(|| format!("expected boolean, got {raw}")),
    }
}

fn py_bool(value: bool) -> &'static str {
    if value {
        "True"
    } else {
        "False"
    }
}

fn py_float(value: f64) -> String {
    if value.fract() == 0.0 {
        format!("{value:.1}")
    } else {
        value.to_string()
    }
}

pub(crate) fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn sha256_prefix(text: &str, length: usize) -> String {
    sha256_hex(text.as_bytes())[..length].to_string()
}

pub(crate) fn sorted_counts(items: &[u8]) -> BTreeMap<u8, u8> {
    let mut counts = BTreeMap::new();
    for item in items {
        *counts.entry(*item).or_insert(0) += 1;
    }
    counts
}
