use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub type Position = (usize, usize);

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Violation {
    pub code: String,
    pub message: String,
    pub cells: Vec<[usize; 2]>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResolvedTask {
    pub task_id: String,
    pub seed: i64,
    pub board: Vec<Vec<String>>,
    pub rules: Value,
    pub max_steps: usize,
    pub config_hash: String,
    pub episode_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EventRecord {
    pub step_index: usize,
    pub tick: usize,
    pub episode_id: String,
    pub kind: String,
    pub action: Option<Value>,
    pub transition: Option<String>,
    pub severity: String,
    pub message: String,
    pub payload: Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PublicState {
    pub board: Vec<Vec<String>>,
    pub frogs: Vec<Position>,
    pub submitted: bool,
    pub violations: Vec<Violation>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PrivateState {
    pub step_index: usize,
    pub tool_call_count: usize,
    pub max_tool_calls: usize,
    pub total_reward: f64,
    pub terminated: bool,
    pub truncated: bool,
    pub config_hash: String,
    pub episode_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FrogsSession {
    pub resolved: ResolvedTask,
    pub public: PublicState,
    pub private: PrivateState,
    pub events: Vec<EventRecord>,
}

impl Default for FrogsSession {
    fn default() -> Self {
        let task = json!({
            "schema": "gamebench.task.frogs.v1",
            "task_id": "manual",
            "seed": 0,
            "board": [
                ["blue", "red", "green", "yellow"],
                ["green", "yellow", "red", "blue"],
                ["green", "blue", "yellow", "red"],
                ["red", "green", "yellow", "blue"]
            ],
            "rules": {"base": "classic_frogs", "overrides": {"max_steps": 16}}
        });
        let resolved = resolve_task(&task, None);
        let mut session = Self {
            resolved: resolved.clone(),
            public: PublicState {
                board: resolved.board.clone(),
                frogs: Vec::new(),
                submitted: false,
                violations: Vec::new(),
            },
            private: PrivateState {
                step_index: 0,
                tool_call_count: 0,
                max_tool_calls: 200,
                total_reward: 0.0,
                terminated: false,
                truncated: false,
                config_hash: resolved.config_hash.clone(),
                episode_id: resolved.episode_id.clone(),
            },
            events: Vec::new(),
        };
        session.reset(resolved);
        session
    }
}

impl FrogsSession {
    pub const ENV_FAMILY: &'static str = "frogs-singleplayer";

    pub fn reset(&mut self, resolved: ResolvedTask) {
        self.resolved = resolved.clone();
        self.public = PublicState {
            board: resolved.board.clone(),
            frogs: Vec::new(),
            submitted: false,
            violations: Vec::new(),
        };
        let max_tool_calls = resolved
            .rules
            .get("overrides")
            .and_then(|overrides| overrides.get("max_tool_calls"))
            .and_then(Value::as_u64)
            .unwrap_or(200) as usize;
        self.private = PrivateState {
            step_index: 0,
            tool_call_count: 0,
            max_tool_calls,
            total_reward: 0.0,
            terminated: false,
            truncated: false,
            config_hash: resolved.config_hash.clone(),
            episode_id: resolved.episode_id.clone(),
        };
        self.events.clear();
        self.append_event(
            "state_transition",
            None,
            Some("reset"),
            "info",
            format!("TaskResolved({},{})", resolved.task_id, resolved.config_hash),
            json!({"task": resolved}),
        );
    }

    pub fn reset_from_entry(entry: &Value) -> Self {
        let task = scenario_to_task(entry);
        let mut session = Self::default();
        session.reset(resolve_task(&task, None));
        if let Some(actions) = entry.get("actions").and_then(Value::as_array) {
            for action in actions {
                if session.private.terminated || session.private.truncated {
                    break;
                }
                session.step_value(action.clone());
            }
        }
        session
    }

    pub fn step_str(&mut self, action: &str) {
        let value = if action.trim_start().starts_with('{') {
            serde_json::from_str(action).unwrap_or_else(|_| json!({"kind": action}))
        } else {
            json!({"kind": action})
        };
        self.step_value(value);
    }

    pub fn step_value(&mut self, action: Value) {
        let parsed = normalize_action(action);
        self.private.step_index += 1;
        if self.private.terminated || self.private.truncated {
            self.rule_violation("terminal", "episode already ended", parsed, Vec::new());
            return;
        }
        let kind = parsed.get("kind").and_then(Value::as_str).unwrap_or("");
        let action_for_terminal = parsed.clone();
        match kind {
            "place_frog" => {
                let row = parsed.get("row").and_then(Value::as_u64).unwrap_or(usize::MAX as u64) as usize;
                let col = parsed.get("col").and_then(Value::as_u64).unwrap_or(usize::MAX as u64) as usize;
                self.place(row, col, parsed);
            }
            "remove_frog" => {
                let row = parsed.get("row").and_then(Value::as_u64).unwrap_or(usize::MAX as u64) as usize;
                let col = parsed.get("col").and_then(Value::as_u64).unwrap_or(usize::MAX as u64) as usize;
                self.remove(row, col, parsed);
            }
            "submit" => self.submit(parsed),
            "reset" => self.soft_reset(parsed),
            _ => self.rule_violation("unknown_action", &format!("unknown action {}", kind), parsed, Vec::new()),
        }
        if self.private.step_index >= self.resolved.max_steps && !self.private.terminated {
            self.private.truncated = true;
            self.append_event(
                "terminal",
                Some(action_for_terminal),
                Some("truncate"),
                "info",
                "Terminal(truncated)".to_string(),
                json!({"max_steps": self.resolved.max_steps}),
            );
        }
    }

    fn place(&mut self, row: usize, col: usize, action: Value) {
        let n = self.resolved.board.len();
        if row >= n || col >= n {
            self.rule_violation("out_of_bounds", &format!("cannot place frog outside board at ({},{})", row, col), action, Vec::new());
            return;
        }
        if self.public.frogs.contains(&(row, col)) {
            self.rule_violation("duplicate_cell", &format!("frog already placed at ({},{})", row, col), action, Vec::new());
            return;
        }
        let mut candidate = self.public.frogs.clone();
        candidate.push((row, col));
        candidate.sort();
        let violations = validate_frogs(&self.resolved.board, &candidate, false);
        if !violations.is_empty() {
            self.public.violations = violations.clone();
            let code = violations[0].code.clone();
            let message = violations[0].message.clone();
            self.rule_violation(&code, &message, action, violations);
            return;
        }
        self.public.frogs = candidate;
        self.public.violations.clear();
        self.append_event(
            "action_applied",
            Some(action),
            Some("place"),
            "info",
            format!("FrogPlaced({},{})", row, col),
            json!({"cell": [row, col], "color": self.resolved.board[row][col]}),
        );
    }

    fn remove(&mut self, row: usize, col: usize, action: Value) {
        if !self.public.frogs.contains(&(row, col)) {
            self.rule_violation("missing_frog", &format!("no frog at ({},{})", row, col), action, Vec::new());
            return;
        }
        self.public.frogs.retain(|cell| *cell != (row, col));
        self.public.violations = validate_frogs(&self.resolved.board, &self.public.frogs, false);
        self.append_event(
            "action_applied",
            Some(action),
            Some("remove"),
            "info",
            format!("FrogRemoved({},{})", row, col),
            json!({"cell": [row, col]}),
        );
    }

    fn submit(&mut self, action: Value) {
        self.public.submitted = true;
        self.public.violations = validate_frogs(&self.resolved.board, &self.public.frogs, true);
        let reward = if self.public.violations.is_empty() { 1.0 } else { 0.0 };
        self.private.total_reward += reward;
        self.private.terminated = true;
        let correct = reward == 1.0;
        self.append_event(
            "state_transition",
            Some(action.clone()),
            Some("submit"),
            "info",
            format!("SubmissionChecked(correct={},reward={:.1})", correct, reward),
            json!({"violations": self.public.violations}),
        );
        self.append_event(
            "resource_delta",
            Some(action.clone()),
            Some("reward"),
            "info",
            format!("RewardDelta({:.2},total={:.2})", reward, self.private.total_reward),
            json!({"reward": reward, "total_reward": self.private.total_reward}),
        );
        let terminal = if correct { "success" } else { "failure" };
        self.append_event(
            "terminal",
            Some(action),
            Some(terminal),
            "info",
            format!("Terminal({})", terminal),
            json!({"correct": correct}),
        );
    }

    fn soft_reset(&mut self, action: Value) {
        self.public.frogs.clear();
        self.public.submitted = false;
        self.public.violations.clear();
        self.private.total_reward = 0.0;
        self.append_event(
            "state_transition",
            Some(action),
            Some("reset_board"),
            "info",
            "BoardReset()".to_string(),
            json!({}),
        );
    }

    fn rule_violation(&mut self, code: &str, message: &str, action: Value, violations: Vec<Violation>) {
        self.append_event(
            "rule_violation",
            Some(action),
            Some("reject"),
            "warn",
            format!("RuleViolation({})", code),
            json!({"code": code, "message": message, "violations": violations}),
        );
    }

    fn append_event(
        &mut self,
        kind: &str,
        action: Option<Value>,
        transition: Option<&str>,
        severity: &str,
        message: String,
        payload: Value,
    ) {
        self.events.push(EventRecord {
            step_index: self.private.step_index,
            tick: self.private.step_index,
            episode_id: self.resolved.episode_id.clone(),
            kind: kind.to_string(),
            action,
            transition: transition.map(str::to_string),
            severity: severity.to_string(),
            message,
            payload,
        });
    }

    pub fn legacy_strings(&self) -> Vec<String> {
        self.events.iter().map(|event| event.message.clone()).collect()
    }

    pub fn readout(&self) -> Value {
        let frog_set: BTreeSet<Position> = self.public.frogs.iter().copied().collect();
        let mut rows = Vec::new();
        for (row_index, row) in self.resolved.board.iter().enumerate() {
            let mut cells = Vec::new();
            for (col_index, color) in row.iter().enumerate() {
                let marker = if frog_set.contains(&(row_index, col_index)) { "F" } else { "." };
                cells.push(format!("{}:{}", color, marker));
            }
            rows.push(cells.join(" "));
        }
        json!({
            "schema": "gamebench.frogs.readout.v1",
            "env_family": Self::ENV_FAMILY,
            "task_id": self.resolved.task_id,
            "public": public_to_value(&self.public),
            "private": self.private,
            "ascii": rows.join("\n"),
            "grid_hash": self.resolved.config_hash,
            "nev_cursor": self.events.len()
        })
    }

    pub fn checkpoint_bytes(&self) -> Vec<u8> {
        serde_json::to_vec(&json!({
            "schema_version": "gamebench.checkpoint.v1",
            "env_family": Self::ENV_FAMILY,
            "episode_id": self.resolved.episode_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.events.len(),
            "config_hash": self.resolved.config_hash,
            "sim": {
                "resolved": self.resolved,
                "public": public_to_value(&self.public),
                "private": self.private,
                "events": self.events
            }
        }))
        .unwrap()
    }

    pub fn restore_checkpoint(&mut self, blob: &[u8]) -> usize {
        let payload: Value = serde_json::from_slice(blob).unwrap();
        let sim = payload.get("sim").unwrap();
        self.resolved = serde_json::from_value(sim.get("resolved").unwrap().clone()).unwrap();
        self.public = public_from_value(sim.get("public").unwrap());
        self.private = serde_json::from_value(sim.get("private").unwrap().clone()).unwrap();
        self.events = serde_json::from_value(sim.get("events").unwrap().clone()).unwrap();
        self.events.len()
    }
}

pub fn resolve_task(task: &Value, seed_override: Option<i64>) -> ResolvedTask {
    let task_id = task
        .get("task_id")
        .or_else(|| task.get("scenario_id"))
        .and_then(Value::as_str)
        .unwrap_or("manual")
        .to_string();
    let seed = seed_override.unwrap_or_else(|| task.get("seed").and_then(Value::as_i64).unwrap_or(0));
    let board_value = task.get("board").or_else(|| task.get("grid")).expect("frogs task requires board");
    let board: Vec<Vec<String>> = board_value
        .as_array()
        .unwrap()
        .iter()
        .map(|row| row.as_array().unwrap().iter().map(|cell| cell.as_str().unwrap().to_string()).collect())
        .collect();
    validate_board(&board);
    let rules = task.get("rules").cloned().unwrap_or_else(|| json!({"base": "classic_frogs"}));
    let max_steps = rules
        .get("overrides")
        .and_then(|overrides| overrides.get("max_steps"))
        .or_else(|| task.get("max_steps"))
        .and_then(Value::as_u64)
        .unwrap_or((board.len() * 3) as u64) as usize;
    let config_hash = stable_hash(&stable_config_string(&task_id, seed, &board, max_steps), 16);
    let episode_id = stable_hash(
        &format!("gamebench.frogs-singleplayer.episode:{}:{}:{}", task_id, seed, config_hash),
        32,
    );
    ResolvedTask {
        task_id,
        seed,
        board,
        rules,
        max_steps,
        config_hash,
        episode_id,
    }
}

fn scenario_to_task(entry: &Value) -> Value {
    if let Some(task) = entry.get("task") {
        return task.clone();
    }
    json!({
        "schema": "gamebench.task.frogs.v1",
        "task_id": entry.get("scenario_id").and_then(Value::as_str).unwrap_or("manual"),
        "seed": entry.get("seed").and_then(Value::as_i64).unwrap_or(0),
        "board": entry.get("board").unwrap(),
        "rules": entry.get("rules").cloned().unwrap_or_else(|| json!({"base": "classic_frogs"})),
        "readouts": {"symbolic": "color_grid", "visual": false},
        "checkpoint_every_n_steps": 1
    })
}

fn normalize_action(action: Value) -> Value {
    if action.is_object() {
        let mut object = action.as_object().unwrap().clone();
        if !object.contains_key("kind") {
            if let Some(kind) = object.get("type").cloned() {
                object.insert("kind".to_string(), kind);
            }
        }
        Value::Object(object)
    } else if let Some(kind) = action.as_str() {
        json!({"kind": kind})
    } else {
        json!({"kind": "invalid"})
    }
}

fn validate_board(board: &[Vec<String>]) {
    assert!(!board.is_empty(), "frogs board must be non-empty");
    let n = board.len();
    assert!(board.iter().all(|row| row.len() == n), "frogs board must be square");
    let colors: BTreeSet<&String> = board.iter().flat_map(|row| row.iter()).collect();
    assert_eq!(colors.len(), n, "frogs board must have exactly {} colors", n);
}

pub fn validate_frogs(board: &[Vec<String>], frogs: &[Position], require_complete: bool) -> Vec<Violation> {
    let n = board.len();
    let mut violations = Vec::new();
    let mut seen = BTreeSet::new();
    for &(row, col) in frogs {
        if row >= n || col >= n {
            violations.push(Violation {
                code: "out_of_bounds".to_string(),
                message: format!("frog outside board at ({},{})", row, col),
                cells: vec![[row, col]],
            });
        } else if !seen.insert((row, col)) {
            violations.push(Violation {
                code: "duplicate_cell".to_string(),
                message: format!("duplicate frog at ({},{})", row, col),
                cells: vec![[row, col]],
            });
        }
    }

    let mut rows: BTreeMap<usize, Vec<Position>> = BTreeMap::new();
    let mut cols: BTreeMap<usize, Vec<Position>> = BTreeMap::new();
    let mut colors: BTreeMap<String, Vec<Position>> = BTreeMap::new();
    for &(row, col) in frogs {
        rows.entry(row).or_default().push((row, col));
        cols.entry(col).or_default().push((row, col));
        if row < n && col < n {
            colors.entry(board[row][col].clone()).or_default().push((row, col));
        }
    }
    for (row, cells) in rows {
        if cells.len() > 1 {
            violations.push(Violation {
                code: "row_conflict".to_string(),
                message: format!("multiple frogs in row {}", row),
                cells: positions_to_cells(cells),
            });
        }
    }
    for (col, cells) in cols {
        if cells.len() > 1 {
            violations.push(Violation {
                code: "column_conflict".to_string(),
                message: format!("multiple frogs in column {}", col),
                cells: positions_to_cells(cells),
            });
        }
    }
    for (color, cells) in colors.iter() {
        if cells.len() > 1 {
            violations.push(Violation {
                code: "color_conflict".to_string(),
                message: format!("multiple frogs in color {}", color),
                cells: positions_to_cells(cells.clone()),
            });
        }
    }

    let mut ordered = frogs.to_vec();
    ordered.sort();
    for i in 0..ordered.len() {
        for second in ordered.iter().skip(i + 1) {
            let first = ordered[i];
            if first.0.abs_diff(second.0) <= 1 && first.1.abs_diff(second.1) <= 1 {
                violations.push(Violation {
                    code: "adjacency_conflict".to_string(),
                    message: "frogs touch orthogonally or diagonally".to_string(),
                    cells: vec![[first.0, first.1], [second.0, second.1]],
                });
            }
        }
    }

    if require_complete {
        if frogs.len() != n {
            violations.push(Violation {
                code: "incomplete".to_string(),
                message: format!("expected {} frogs, found {}", n, frogs.len()),
                cells: Vec::new(),
            });
        }
    }
    violations
}

fn positions_to_cells(mut cells: Vec<Position>) -> Vec<[usize; 2]> {
    cells.sort();
    cells.into_iter().map(|(row, col)| [row, col]).collect()
}

fn public_to_value(public: &PublicState) -> Value {
    let mut frogs = public.frogs.clone();
    frogs.sort();
    json!({
        "board": public.board,
        "frogs": frogs.into_iter().map(|(row, col)| json!([row, col])).collect::<Vec<_>>(),
        "submitted": public.submitted,
        "violations": public.violations
    })
}

fn public_from_value(value: &Value) -> PublicState {
    let frogs = value
        .get("frogs")
        .and_then(Value::as_array)
        .unwrap_or(&Vec::new())
        .iter()
        .map(|cell| {
            let values = cell.as_array().unwrap();
            (values[0].as_u64().unwrap() as usize, values[1].as_u64().unwrap() as usize)
        })
        .collect();
    PublicState {
        board: serde_json::from_value(value.get("board").unwrap().clone()).unwrap(),
        frogs,
        submitted: value.get("submitted").and_then(Value::as_bool).unwrap_or(false),
        violations: serde_json::from_value(value.get("violations").cloned().unwrap_or_else(|| json!([]))).unwrap(),
    }
}

fn stable_config_string(task_id: &str, seed: i64, board: &[Vec<String>], max_steps: usize) -> String {
    let rows = board.iter().map(|row| row.join(",")).collect::<Vec<_>>().join(";");
    format!("frogs:{}:{}:{}:{}", task_id, seed, max_steps, rows)
}

fn stable_hash(text: &str, length: usize) -> String {
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hasher.finalize();
    let full = format!("{:x}", digest);
    full[..length].to_string()
}
