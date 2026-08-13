use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

pub const WALL: i32 = 0;
pub const FLOOR: i32 = 1;
pub const TARGET: i32 = 2;
pub const BOX_ON_TARGET: i32 = 3;
pub const BOX: i32 = 4;
pub const PLAYER: i32 = 5;
pub const PLAYER_ON_TARGET: i32 = 6;

#[derive(Clone, Debug)]
pub struct ResolvedTask {
    pub task_id: String,
    pub puzzle_id: String,
    pub seed: i64,
    pub config_hash: String,
    pub room_fixed: Vec<Vec<i32>>,
    pub room_state: Vec<Vec<i32>>,
    pub goals: Vec<(usize, usize)>,
    pub boxes: Vec<(usize, usize)>,
    pub player: (usize, usize),
    pub max_steps: usize,
    pub rewards: BTreeMap<String, f64>,
    pub errors: Value,
    pub curriculum: Value,
    pub monty_reward: Value,
    pub resolved_json: Value,
}

impl ResolvedTask {
    pub fn to_value(&self) -> Value {
        json!({
            "task_id": self.task_id,
            "puzzle_id": self.puzzle_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "room_fixed": self.room_fixed,
            "room_state": self.room_state,
            "goals": self.goals.iter().map(|(r,c)| json!([r, c])).collect::<Vec<_>>(),
            "boxes": self.boxes.iter().map(|(r,c)| json!([r, c])).collect::<Vec<_>>(),
            "player": [self.player.0, self.player.1],
            "max_steps": self.max_steps,
            "rewards": self.rewards,
            "errors": self.errors,
            "curriculum": self.curriculum,
            "monty_reward": self.monty_reward,
            "resolved_json": self.resolved_json,
        })
    }
}

fn task_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("gold_rust parent")
        .to_path_buf()
}

fn ascii_rows(value: &Value) -> Vec<String> {
    if let Some(s) = value.as_str() {
        return s.lines().filter(|l| !l.is_empty()).map(str::to_string).collect();
    }
    value
        .as_array()
        .expect("grid must be string or array")
        .iter()
        .map(|row| row.as_str().unwrap_or(&row.to_string()).to_string())
        .collect()
}

pub fn ascii_to_int_grids(
    rows: &[String],
) -> (
    Vec<Vec<i32>>,
    Vec<Vec<i32>>,
    Vec<(usize, usize)>,
    Vec<(usize, usize)>,
    (usize, usize),
) {
    let width = rows.iter().map(|r| r.len()).max().unwrap_or(0);
    let mut room_fixed = Vec::new();
    let mut room_state = Vec::new();
    let mut goals = Vec::new();
    let mut boxes = Vec::new();
    let mut player = None;
    for (r, raw_row) in rows.iter().enumerate() {
        let mut line = raw_row.clone();
        while line.len() < width {
            line.push('#');
        }
        let mut fixed_row = Vec::new();
        let mut state_row = Vec::new();
        for (c, ch) in line.chars().enumerate() {
            match ch {
                '#' => {
                    fixed_row.push(WALL);
                    state_row.push(WALL);
                }
                '.' | 'G' => {
                    fixed_row.push(TARGET);
                    state_row.push(TARGET);
                    goals.push((r, c));
                }
                '*' => {
                    fixed_row.push(TARGET);
                    state_row.push(BOX_ON_TARGET);
                    goals.push((r, c));
                    boxes.push((r, c));
                }
                '+' => {
                    fixed_row.push(TARGET);
                    state_row.push(PLAYER_ON_TARGET);
                    goals.push((r, c));
                    player = Some((r, c));
                }
                '$' => {
                    fixed_row.push(FLOOR);
                    state_row.push(BOX);
                    boxes.push((r, c));
                }
                '@' => {
                    fixed_row.push(FLOOR);
                    state_row.push(PLAYER);
                    player = Some((r, c));
                }
                _ => {
                    fixed_row.push(FLOOR);
                    state_row.push(FLOOR);
                }
            }
        }
        room_fixed.push(fixed_row);
        room_state.push(state_row);
    }
    (
        room_fixed,
        room_state,
        goals,
        boxes,
        player.expect("sokoban map has no player"),
    )
}

fn deep_merge(target: &mut Value, source: &Value) {
    if let (Some(t), Some(s)) = (target.as_object_mut(), source.as_object()) {
        for (k, v) in s {
            if let Some(existing) = t.get_mut(k) {
                if existing.is_object() && v.is_object() {
                    deep_merge(existing, v);
                    continue;
                }
            }
            t.insert(k.clone(), v.clone());
        }
    }
}

fn default_sparse_rules() -> Value {
    json!({
        "max_steps": 120,
        "push_semantics": "standard",
        "rewards": {
            "step": -0.01,
            "push": 0.0,
            "box_on_target": 0.1,
            "goal": 1.0,
            "blocked": -0.02
        },
        "errors": { "mode": "silent" },
        "achievements": {
            "first_push": true,
            "first_box_on_target": true,
            "level_complete": true
        }
    })
}

fn resolve_rules(rules_spec: &Value) -> Value {
    let base_name = rules_spec
        .get("base")
        .and_then(Value::as_str)
        .unwrap_or("sparse_sokoban");
    let path = task_dir()
        .join("defaults")
        .join("rules")
        .join(format!("{base_name}.json"));
    let mut merged = if path.exists() {
        serde_json::from_str(&fs::read_to_string(&path).expect("read rules")).expect("parse rules")
    } else {
        default_sparse_rules()
    };
    if let Some(overrides) = rules_spec.get("overrides") {
        deep_merge(&mut merged, overrides);
    }
    merged
}

fn resolve_map(map_spec: &Value, seed: i64) -> (String, Vec<String>, Value, Value) {
    if map_spec.get("source").and_then(Value::as_str) == Some("inline") || map_spec.get("grid").is_some()
    {
        let puzzle_id = map_spec
            .get("puzzle_id")
            .and_then(Value::as_str)
            .unwrap_or("inline")
            .to_string();
        let grid = ascii_rows(map_spec.get("grid").expect("inline grid"));
        let metadata = map_spec.get("metadata").cloned().unwrap_or_else(|| json!({}));
        return (puzzle_id, grid, metadata, json!({}));
    }
    if let Some(puzzle_ref) = map_spec
        .get("puzzle_ref")
        .or_else(|| map_spec.get("puzzle_id"))
        .and_then(Value::as_str)
    {
        let source = map_spec.get("source").and_then(Value::as_str);
        if source.is_none() || matches!(source, Some("verified") | Some("puzzle_ref")) {
            let path = task_dir()
                .join("defaults")
                .join("levels")
                .join("verified_puzzles.json");
            let doc: Value =
                serde_json::from_str(&fs::read_to_string(&path).expect("verified puzzles")).unwrap();
            let puzzle = doc
                .get("puzzles")
                .and_then(|p| p.get(puzzle_ref))
                .unwrap_or_else(|| panic!("unknown puzzle_ref: {puzzle_ref}"));
            let grid = ascii_rows(puzzle.get("grid").unwrap());
            let metadata = json!({
                "puzzle_ref": puzzle_ref,
                "name": puzzle.get("name").unwrap_or(&json!(puzzle_ref)),
                "optimal_steps": puzzle.get("optimal_steps"),
            });
            return (
                puzzle
                    .get("id")
                    .and_then(Value::as_str)
                    .unwrap_or(puzzle_ref)
                    .to_string(),
                grid,
                metadata,
                json!({}),
            );
        }
    }
    let default_name = map_spec
        .get("use_default")
        .and_then(Value::as_str)
        .unwrap_or("curriculum_easy");
    let path = task_dir()
        .join("defaults")
        .join("levels")
        .join(format!("{default_name}.json"));
    let level_doc: Value =
        serde_json::from_str(&fs::read_to_string(&path).expect("level bank")).unwrap();
    let levels = level_doc.get("levels").and_then(Value::as_array).unwrap();
    let index = if map_spec.get("seed").is_some() || seed != 0 {
        (seed.rem_euclid(levels.len() as i64)) as usize
    } else {
        map_spec
            .get("index")
            .and_then(Value::as_u64)
            .unwrap_or(0) as usize
            % levels.len()
    };
    let chosen = &levels[index];
    let grid = ascii_rows(chosen.get("grid").unwrap());
    let metadata = json!({
        "default": default_name,
        "index": index,
        "name": chosen.get("name").unwrap_or(chosen.get("id").unwrap()),
        "optimal_steps": chosen.get("optimal_steps"),
    });
    let curriculum_extra = json!({
        "tier": level_doc.get("tier").unwrap_or(&json!(default_name)),
        "num_boxes": chosen.get("num_boxes"),
    });
    (
        chosen
            .get("id")
            .and_then(Value::as_str)
            .unwrap_or("level")
            .to_string(),
        grid,
        metadata,
        curriculum_extra,
    )
}

pub fn resolve_task(task: &Value, seed_override: Option<i64>) -> ResolvedTask {
    if let Some(schema) = task.get("schema").and_then(Value::as_str) {
        if schema != "gamebench.task.sokoban.v1" {
            panic!("unsupported sokoban task schema: {schema}");
        }
    }
    let seed = seed_override.unwrap_or_else(|| {
        task.get("seed")
            .or_else(|| task.pointer("/map/seed"))
            .and_then(Value::as_i64)
            .unwrap_or(0)
    });
    let task_id = task
        .get("task_id")
        .and_then(Value::as_str)
        .unwrap_or("sokoban_manual")
        .to_string();
    let map_spec = task.get("map").cloned().unwrap_or_else(|| json!({}));
    let (puzzle_id, grid, metadata, curriculum_extra) = resolve_map(&map_spec, seed);
    let rules = resolve_rules(task.get("rules").unwrap_or(&json!({})));
    let monty_reward = json!({});
    let (room_fixed, room_state, goals, boxes, player) = ascii_to_int_grids(&grid);

    let mut curriculum = metadata.clone();
    if let (Some(c), Some(e)) = (curriculum.as_object_mut(), curriculum_extra.as_object()) {
        for (k, v) in e {
            c.insert(k.clone(), v.clone());
        }
    }

    let readouts = task
        .get("readouts")
        .cloned()
        .unwrap_or_else(|| json!({"symbolic": "ascii_annotated", "visual": false}));
    let resolved = json!({
        "schema": "gamebench.task.sokoban.v1",
        "task_id": task_id,
        "seed": seed,
        "map": {
            "puzzle_id": puzzle_id,
            "grid": grid,
            "metadata": metadata,
        },
        "rules": rules,
        "readouts": readouts,
        "checkpoint_every_n_steps": task.get("checkpoint_every_n_steps").and_then(Value::as_u64).unwrap_or(1),
    });
    let canonical = serde_json::to_string(&sort_value(&resolved)).expect("canonical json");
    // Python: json.dumps(resolved, sort_keys=True, separators=(",", ":"))
    // serde_json Map is sorted if we use BTree-backed sort
    let digest = hex_sha256(canonical.as_bytes());
    let config_hash = format!("sha256:{digest}");

    let rewards = rules
        .get("rewards")
        .and_then(Value::as_object)
        .map(|m| {
            m.iter()
                .map(|(k, v)| (k.clone(), v.as_f64().unwrap_or(0.0)))
                .collect()
        })
        .unwrap_or_default();

    ResolvedTask {
        task_id,
        puzzle_id: resolved["map"]["puzzle_id"].as_str().unwrap().to_string(),
        seed,
        config_hash,
        room_fixed,
        room_state,
        goals,
        boxes,
        player,
        max_steps: rules.get("max_steps").and_then(Value::as_u64).unwrap_or(120) as usize,
        rewards,
        errors: rules
            .get("errors")
            .cloned()
            .unwrap_or_else(|| json!({"mode": "silent"})),
        curriculum,
        monty_reward,
        resolved_json: resolved,
    }
}

fn sort_value(v: &Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut out = Map::new();
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            for k in keys {
                out.insert(k.clone(), sort_value(&map[&k]));
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.iter().map(sort_value).collect()),
        other => other.clone(),
    }
}

fn hex_sha256(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

pub fn episode_id_for_task(task_id: &str, seed: i64, config_hash: &str) -> String {
    let payload = format!("gamebench.sokoban-singleplayer.episode:{task_id}:{seed}:{config_hash}");
    hex_sha256(payload.as_bytes())[..32].to_string()
}

pub fn grid_to_ascii(
    room_fixed: &[Vec<i32>],
    player: (usize, usize),
    boxes: &std::collections::BTreeSet<(usize, usize)>,
) -> Vec<String> {
    let mut rows = Vec::new();
    for (r, fixed_row) in room_fixed.iter().enumerate() {
        let mut chars = Vec::new();
        for (c, &fixed) in fixed_row.iter().enumerate() {
            let pos = (r, c);
            let on_target = fixed == TARGET;
            if fixed == WALL {
                chars.push('#');
            } else if pos == player {
                chars.push(if on_target { '+' } else { '@' });
            } else if boxes.contains(&pos) {
                chars.push(if on_target { '*' } else { '$' });
            } else if on_target {
                chars.push('.');
            } else {
                chars.push(' ');
            }
        }
        let s: String = chars.into_iter().collect();
        rows.push(s.trim_end().to_string());
    }
    rows
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parity_mini_config_hash() {
        let task = json!({
            "schema": "gamebench.task.sokoban.v1",
            "task_id": "parity_mini",
            "map": {"source": "inline", "grid": ["#####", "#@$.#", "#####"]},
            "rules": {"base": "sparse_sokoban"},
        });
        let resolved = resolve_task(&task, Some(0));
        assert_eq!(
            resolved.config_hash,
            "sha256:8a394a9a0194f5f0ccfcde0895a088e4db9a36de1d99e8af598289b0e3a4d446"
        );
        assert_eq!(
            episode_id_for_task(&resolved.task_id, resolved.seed, &resolved.config_hash),
            "e975703ab53c245268e7148a7b9f4282"
        );
    }
}
