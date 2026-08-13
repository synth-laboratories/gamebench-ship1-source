use crate::task::{
    episode_id_for_task, grid_to_ascii, resolve_task, ResolvedTask, BOX, BOX_ON_TARGET, FLOOR,
    PLAYER, PLAYER_ON_TARGET, TARGET, WALL,
};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const DIRS: &[(&str, i32, i32)] = &[
    ("up", -1, 0),
    ("down", 1, 0),
    ("left", 0, -1),
    ("right", 0, 1),
];

#[derive(Clone, Debug)]
pub struct EventRecord {
    pub step_index: usize,
    pub sim_tick: usize,
    pub episode_id: String,
    pub kind: String,
    pub severity: String,
    pub message: String,
    pub action: Option<String>,
    pub transition: Option<Value>,
    pub payload: Value,
}

impl EventRecord {
    pub fn to_value(&self) -> Value {
        json!({
            "step_index": self.step_index,
            "sim_tick": self.sim_tick,
            "episode_id": self.episode_id,
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "action": self.action,
            "transition": self.transition,
            "payload": self.payload,
        })
    }
}

#[derive(Clone, Debug)]
pub struct PublicState {
    pub room_state: Vec<Vec<i32>>,
    pub player: (usize, usize),
    pub boxes: Vec<(usize, usize)>,
    pub boxes_on_target: usize,
    pub done: bool,
}

impl PublicState {
    pub fn to_value(&self) -> Value {
        json!({
            "room_state": self.room_state,
            "player": [self.player.0, self.player.1],
            "boxes": self.boxes.iter().map(|(r,c)| json!([r,c])).collect::<Vec<_>>(),
            "boxes_on_target": self.boxes_on_target,
            "done": self.done,
        })
    }

    fn diff(&self, other: &PublicState) -> Value {
        let mut changes = serde_json::Map::new();
        if self.room_state != other.room_state {
            changes.insert(
                "room_state".into(),
                json!({"from": other.room_state, "to": self.room_state}),
            );
        }
        if self.player != other.player {
            changes.insert(
                "player".into(),
                json!({"from": [other.player.0, other.player.1], "to": [self.player.0, self.player.1]}),
            );
        }
        if self.boxes != other.boxes {
            changes.insert(
                "boxes".into(),
                json!({
                    "from": other.boxes.iter().map(|(r,c)| json!([r,c])).collect::<Vec<_>>(),
                    "to": self.boxes.iter().map(|(r,c)| json!([r,c])).collect::<Vec<_>>()
                }),
            );
        }
        if self.boxes_on_target != other.boxes_on_target {
            changes.insert(
                "boxes_on_target".into(),
                json!({"from": other.boxes_on_target, "to": self.boxes_on_target}),
            );
        }
        if self.done != other.done {
            changes.insert("done".into(), json!({"from": other.done, "to": self.done}));
        }
        Value::Object(changes)
    }
}

#[derive(Clone, Debug)]
pub struct PrivateState {
    pub episode_id: String,
    pub task_id: String,
    pub puzzle_id: String,
    pub seed: i64,
    pub config_hash: String,
    pub step_index: usize,
    pub reward_last: f64,
    pub total_reward: f64,
    pub terminated: bool,
    pub truncated: bool,
    pub achievements: BTreeSet<String>,
}

impl PrivateState {
    pub fn to_value(&self) -> Value {
        json!({
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "puzzle_id": self.puzzle_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "step_index": self.step_index,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "achievements": self.achievements.iter().cloned().collect::<Vec<_>>(),
        })
    }
}

#[derive(Clone, Debug)]
pub struct SokobanSession {
    pub resolved: Option<ResolvedTask>,
    pub room_fixed: Vec<Vec<i32>>,
    pub room_state: Vec<Vec<i32>>,
    pub player: (usize, usize),
    pub boxes: BTreeSet<(usize, usize)>,
    pub goals: BTreeSet<(usize, usize)>,
    pub public: PublicState,
    pub private: PrivateState,
    pub events: Vec<EventRecord>,
}

impl Default for SokobanSession {
    fn default() -> Self {
        let task = json!({
            "schema": "gamebench.task.sokoban.v1",
            "task_id": "manual",
            "map": {"source": "inline", "grid": ["#####", "#@$.#", "#####"]},
            "rules": {"base": "sparse_sokoban"},
        });
        let mut session = Self::empty();
        session.reset(resolve_task(&task, None));
        session
    }
}

impl SokobanSession {
    pub const ENV_FAMILY: &'static str = "sokoban-singleplayer";

    fn empty() -> Self {
        Self {
            resolved: None,
            room_fixed: vec![],
            room_state: vec![],
            player: (0, 0),
            boxes: BTreeSet::new(),
            goals: BTreeSet::new(),
            public: PublicState {
                room_state: vec![],
                player: (0, 0),
                boxes: vec![],
                boxes_on_target: 0,
                done: false,
            },
            private: PrivateState {
                episode_id: String::new(),
                task_id: String::new(),
                puzzle_id: String::new(),
                seed: 0,
                config_hash: String::new(),
                step_index: 0,
                reward_last: 0.0,
                total_reward: 0.0,
                terminated: false,
                truncated: false,
                achievements: BTreeSet::new(),
            },
            events: vec![],
        }
    }

    pub fn reset_from_task(task: &Value, seed: Option<i64>) -> Self {
        let mut session = Self::empty();
        session.reset(resolve_task(task, seed));
        session
    }

    pub fn reset(&mut self, resolved: ResolvedTask) {
        self.room_fixed = resolved.room_fixed.clone();
        self.player = resolved.player;
        self.boxes = resolved.boxes.iter().copied().collect();
        self.goals = resolved.goals.iter().copied().collect();
        self.room_state = self.compose_room_state();
        let episode_id =
            episode_id_for_task(&resolved.task_id, resolved.seed, &resolved.config_hash);
        self.private = PrivateState {
            episode_id: episode_id.clone(),
            task_id: resolved.task_id.clone(),
            puzzle_id: resolved.puzzle_id.clone(),
            seed: resolved.seed,
            config_hash: resolved.config_hash.clone(),
            step_index: 0,
            reward_last: 0.0,
            total_reward: 0.0,
            terminated: false,
            truncated: false,
            achievements: BTreeSet::new(),
        };
        self.public = self.public_state();
        self.events.clear();
        self.resolved = Some(resolved.clone());
        self.append_nev(
            "task_resolved",
            "info",
            format!("TaskResolved({},{})", resolved.puzzle_id, resolved.config_hash),
            None,
            None,
            json!({"resolved": resolved.to_value()}),
        );
    }

    pub fn step(&mut self, action: &str) {
        let action = action.to_lowercase();
        let action = action.trim();
        let dir = DIRS.iter().find(|(name, _, _)| *name == action);
        if dir.is_none() {
            self.blocked(action, "unknown_action", 0.0);
            return;
        }
        if self.private.terminated || self.private.truncated {
            self.blocked(action, "terminal", 0.0);
            return;
        }
        let prev_public = self.public_state();
        let prev_on_targets = prev_public.boxes_on_target;
        let (_, dr, dc) = dir.unwrap();
        let (pr, pc) = self.player;
        let nr = pr as i32 + dr;
        let nc = pc as i32 + dc;
        let mut reward = self.reward("step");

        if self.is_wall(nr, nc) {
            self.blocked(action, "wall", reward);
            return;
        }
        let nr = nr as usize;
        let nc = nc as usize;
        let mut pushed = false;
        if self.boxes.contains(&(nr, nc)) {
            let br = nr as i32 + dr;
            let bc = nc as i32 + dc;
            if self.is_wall(br, bc) || self.boxes.contains(&(br as usize, bc as usize)) {
                self.blocked(action, "box_blocked", reward);
                return;
            }
            self.boxes.remove(&(nr, nc));
            self.boxes.insert((br as usize, bc as usize));
            pushed = true;
            reward += self.reward("push");
        }
        self.player = (nr, nc);
        self.private.step_index += 1;
        self.room_state = self.compose_room_state();
        self.public = self.public_state();
        self.private.reward_last = reward;
        self.private.total_reward += reward;

        let transition = self.public.diff(&prev_public);
        self.append_nev(
            "action_applied",
            "info",
            format!("ActionApplied({},step={})", action, self.private.step_index),
            Some(action.to_string()),
            Some(transition),
            json!({"action": action, "pushed": pushed}),
        );
        if pushed {
            self.append_nev(
                "push_applied",
                "info",
                format!(
                    "PushApplied({},boxes_on_target={})",
                    action, self.public.boxes_on_target
                ),
                Some(action.to_string()),
                None,
                json!({"boxes": self.boxes.iter().map(|(r,c)| json!([r,c])).collect::<Vec<_>>()}),
            );
            self.unlock("first_push");
        }
        if self.public.boxes_on_target > prev_on_targets {
            let extra = self.reward("box_on_target");
            self.private.reward_last += extra;
            self.private.total_reward += extra;
            self.append_nev(
                "box_on_target",
                "info",
                format!(
                    "BoxOnTarget({}/{})",
                    self.public.boxes_on_target,
                    self.goals.len()
                ),
                None,
                None,
                json!({"boxes_on_target": self.public.boxes_on_target, "goals": self.goals.len()}),
            );
            self.unlock("first_box_on_target");
        }
        if self.private.reward_last != 0.0 {
            self.append_nev(
                "reward_delta",
                "info",
                format!(
                    "RewardDelta({:.2},total={:.2})",
                    self.private.reward_last, self.private.total_reward
                ),
                None,
                None,
                json!({"delta": self.private.reward_last, "total": self.private.total_reward}),
            );
        }
        if self.is_solved() {
            let extra = self.reward("goal");
            self.private.reward_last += extra;
            self.private.total_reward += extra;
            self.private.terminated = true;
            self.public.done = true;
            self.append_nev(
                "level_complete",
                "info",
                format!("LevelComplete({})", self.private.step_index),
                None,
                None,
                json!({"steps": self.private.step_index}),
            );
            self.unlock("level_complete");
            self.append_nev(
                "terminal",
                "info",
                "Terminal(success)".into(),
                None,
                None,
                json!({"reason": "success"}),
            );
        } else if let Some(resolved) = &self.resolved {
            if self.private.step_index >= resolved.max_steps {
                self.private.truncated = true;
                self.public.done = true;
                self.append_nev(
                    "episode_truncated",
                    "info",
                    format!("EpisodeTruncated(max_steps={})", resolved.max_steps),
                    None,
                    None,
                    json!({"max_steps": resolved.max_steps}),
                );
                self.append_nev(
                    "terminal",
                    "info",
                    "Terminal(truncated)".into(),
                    None,
                    None,
                    json!({"reason": "truncated"}),
                );
            }
        }
    }

    fn blocked(&mut self, action: &str, reason: &str, base_reward: f64) {
        self.private.step_index += 1;
        let strict = self
            .resolved
            .as_ref()
            .and_then(|r| r.errors.get("mode"))
            .and_then(Value::as_str)
            == Some("strict");
        let severity = if strict { "error" } else { "warn" };
        self.private.reward_last = base_reward + self.reward("blocked");
        self.private.total_reward += self.private.reward_last;
        self.append_nev(
            "push_blocked",
            severity,
            format!(
                "PushBlocked({},{},step={})",
                action, reason, self.private.step_index
            ),
            Some(action.to_string()),
            None,
            json!({"reason": reason}),
        );
        if strict {
            self.append_nev(
                "rule_violation",
                severity,
                format!("RuleViolation({reason})"),
                Some(action.to_string()),
                None,
                json!({"reason": reason}),
            );
        }
        if self.private.reward_last != 0.0 {
            self.append_nev(
                "reward_delta",
                "info",
                format!(
                    "RewardDelta({:.2},total={:.2})",
                    self.private.reward_last, self.private.total_reward
                ),
                None,
                None,
                json!({"delta": self.private.reward_last, "total": self.private.total_reward}),
            );
        }
        if let Some(resolved) = &self.resolved {
            if self.private.step_index >= resolved.max_steps {
                self.private.truncated = true;
                self.public.done = true;
                self.append_nev(
                    "episode_truncated",
                    "info",
                    format!("EpisodeTruncated(max_steps={})", resolved.max_steps),
                    None,
                    None,
                    json!({"max_steps": resolved.max_steps}),
                );
                self.append_nev(
                    "terminal",
                    "info",
                    "Terminal(truncated)".into(),
                    None,
                    None,
                    json!({"reason": "truncated"}),
                );
            }
        }
    }

    fn unlock(&mut self, name: &str) {
        if self.private.achievements.contains(name) {
            return;
        }
        self.private.achievements.insert(name.to_string());
        self.append_nev(
            "achievement_unlocked",
            "info",
            format!("AchievementUnlocked({name})"),
            None,
            None,
            json!({"achievement": name}),
        );
    }

    fn append_nev(
        &mut self,
        kind: &str,
        severity: &str,
        message: String,
        action: Option<String>,
        transition: Option<Value>,
        payload: Value,
    ) {
        self.events.push(EventRecord {
            step_index: self.private.step_index,
            sim_tick: self.private.step_index,
            episode_id: self.private.episode_id.clone(),
            kind: kind.to_string(),
            severity: severity.to_string(),
            message,
            action,
            transition,
            payload,
        });
    }

    fn reward(&self, key: &str) -> f64 {
        self.resolved
            .as_ref()
            .and_then(|r| r.rewards.get(key).copied())
            .unwrap_or(0.0)
    }

    fn is_wall(&self, r: i32, c: i32) -> bool {
        if r < 0 || c < 0 {
            return true;
        }
        let r = r as usize;
        let c = c as usize;
        r >= self.room_fixed.len()
            || c >= self.room_fixed[0].len()
            || self.room_fixed[r][c] == WALL
    }

    fn is_solved(&self) -> bool {
        self.goals.iter().all(|g| self.boxes.contains(g))
    }

    fn compose_room_state(&self) -> Vec<Vec<i32>> {
        let mut state = Vec::new();
        for (r, fixed_row) in self.room_fixed.iter().enumerate() {
            let mut row = Vec::new();
            for (c, &fixed) in fixed_row.iter().enumerate() {
                let pos = (r, c);
                if fixed == WALL {
                    row.push(WALL);
                } else if pos == self.player {
                    row.push(if fixed == TARGET {
                        PLAYER_ON_TARGET
                    } else {
                        PLAYER
                    });
                } else if self.boxes.contains(&pos) {
                    row.push(if fixed == TARGET { BOX_ON_TARGET } else { BOX });
                } else {
                    row.push(if fixed == TARGET { TARGET } else { FLOOR });
                }
            }
            state.push(row);
        }
        state
    }

    fn public_state(&self) -> PublicState {
        PublicState {
            room_state: self.room_state.clone(),
            player: self.player,
            boxes: self.boxes.iter().copied().collect(),
            boxes_on_target: self.boxes.iter().filter(|b| self.goals.contains(b)).count(),
            done: self.private.terminated || self.private.truncated,
        }
    }

    pub fn valid_actions(&self) -> Vec<String> {
        if self.private.terminated || self.private.truncated {
            return vec![];
        }
        DIRS.iter().map(|(n, _, _)| (*n).to_string()).collect()
    }

    pub fn grid_hash(&self) -> String {
        let payload = self
            .room_state
            .iter()
            .map(|row| {
                row.iter()
                    .map(|c| c.to_string())
                    .collect::<Vec<_>>()
                    .join(",")
            })
            .collect::<Vec<_>>()
            .join("|");
        let mut hasher = Sha256::new();
        hasher.update(payload.as_bytes());
        let digest = hasher.finalize();
        digest.iter().take(8).map(|b| format!("{b:02x}")).collect()
    }

    pub fn readout(&self) -> Value {
        let ascii = grid_to_ascii(&self.room_fixed, self.player, &self.boxes).join("\n");
        let mut private = self.private.to_value();
        if let Some(resolved) = &self.resolved {
            private
                .as_object_mut()
                .unwrap()
                .insert("max_steps".into(), json!(resolved.max_steps));
        }
        json!({
            "ascii": ascii,
            "valid_actions": self.valid_actions(),
            "grid_hash": self.grid_hash(),
            "public": self.public.to_value(),
            "private": private,
        })
    }

    pub fn checkpoint_bytes(&self) -> Vec<u8> {
        let payload = json!({
            "schema_version": "gamebench.checkpoint.v1",
            "env_family": Self::ENV_FAMILY,
            "episode_id": self.private.episode_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.events.len(),
            "config_hash": self.private.config_hash,
            "sim": {
                "resolved": self.resolved.as_ref().map(|r| r.to_value()),
                "room_fixed": self.room_fixed,
                "player": [self.player.0, self.player.1],
                "boxes": self.boxes.iter().map(|(r,c)| json!([r,c])).collect::<Vec<_>>(),
                "goals": self.goals.iter().map(|(r,c)| json!([r,c])).collect::<Vec<_>>(),
                "private": self.private.to_value(),
            },
            "nev_events": self.events.iter().map(|e| e.to_value()).collect::<Vec<_>>(),
        });
        // sort_keys like Python encode
        serde_json::to_vec(&crate_sort(&payload)).unwrap()
    }

    pub fn restore_checkpoint(&mut self, blob: &[u8]) -> usize {
        let payload: Value = serde_json::from_slice(blob).expect("checkpoint json");
        assert_eq!(
            payload.get("schema_version").and_then(Value::as_str),
            Some("gamebench.checkpoint.v1")
        );
        assert_eq!(
            payload.get("env_family").and_then(Value::as_str),
            Some(Self::ENV_FAMILY)
        );
        let sim = payload.get("sim").cloned().unwrap();
        // Restore via re-resolve is complex; rebuild from sim fields.
        let room_fixed: Vec<Vec<i32>> =
            serde_json::from_value(sim.get("room_fixed").cloned().unwrap()).unwrap();
        let player_arr = sim.get("player").unwrap().as_array().unwrap();
        self.player = (
            player_arr[0].as_u64().unwrap() as usize,
            player_arr[1].as_u64().unwrap() as usize,
        );
        self.boxes = sim
            .get("boxes")
            .unwrap()
            .as_array()
            .unwrap()
            .iter()
            .map(|p| {
                let a = p.as_array().unwrap();
                (a[0].as_u64().unwrap() as usize, a[1].as_u64().unwrap() as usize)
            })
            .collect();
        self.goals = sim
            .get("goals")
            .unwrap()
            .as_array()
            .unwrap()
            .iter()
            .map(|p| {
                let a = p.as_array().unwrap();
                (a[0].as_u64().unwrap() as usize, a[1].as_u64().unwrap() as usize)
            })
            .collect();
        self.room_fixed = room_fixed;
        let priv_v = sim.get("private").unwrap();
        self.private = PrivateState {
            episode_id: payload
                .get("episode_id")
                .and_then(Value::as_str)
                .unwrap()
                .to_string(),
            task_id: priv_v.get("task_id").and_then(Value::as_str).unwrap().into(),
            puzzle_id: priv_v
                .get("puzzle_id")
                .and_then(Value::as_str)
                .unwrap()
                .into(),
            seed: priv_v.get("seed").and_then(Value::as_i64).unwrap(),
            config_hash: payload
                .get("config_hash")
                .and_then(Value::as_str)
                .unwrap()
                .into(),
            step_index: payload.get("step_index").and_then(Value::as_u64).unwrap() as usize,
            reward_last: priv_v.get("reward_last").and_then(Value::as_f64).unwrap_or(0.0),
            total_reward: priv_v
                .get("total_reward")
                .and_then(Value::as_f64)
                .unwrap_or(0.0),
            terminated: priv_v
                .get("terminated")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            truncated: priv_v
                .get("truncated")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            achievements: priv_v
                .get("achievements")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .filter_map(|v| v.as_str().map(str::to_string))
                        .collect()
                })
                .unwrap_or_default(),
        };
        // Keep prior resolved if present; otherwise leave None (simulate still works for board).
        if let Some(resolved_doc) = sim.get("resolved").filter(|v| !v.is_null()) {
            // Minimal reconstruct for max_steps/rewards
            let mut rewards = BTreeMap::new();
            if let Some(obj) = resolved_doc.get("rewards").and_then(Value::as_object) {
                for (k, v) in obj {
                    rewards.insert(k.clone(), v.as_f64().unwrap_or(0.0));
                }
            }
            self.resolved = Some(ResolvedTask {
                task_id: resolved_doc
                    .get("task_id")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .into(),
                puzzle_id: resolved_doc
                    .get("puzzle_id")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .into(),
                seed: resolved_doc.get("seed").and_then(Value::as_i64).unwrap_or(0),
                config_hash: resolved_doc
                    .get("config_hash")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .into(),
                room_fixed: self.room_fixed.clone(),
                room_state: self.room_state.clone(),
                goals: self.goals.iter().copied().collect(),
                boxes: self.boxes.iter().copied().collect(),
                player: self.player,
                max_steps: resolved_doc
                    .get("max_steps")
                    .and_then(Value::as_u64)
                    .unwrap_or(120) as usize,
                rewards,
                errors: resolved_doc
                    .get("errors")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
                curriculum: resolved_doc
                    .get("curriculum")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
                monty_reward: resolved_doc
                    .get("monty_reward")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
                resolved_json: resolved_doc
                    .get("resolved_json")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
            });
        }
        self.room_state = self.compose_room_state();
        self.public = self.public_state();
        self.events.clear();
        if let Some(arr) = payload.get("nev_events").and_then(Value::as_array) {
            for ev in arr {
                self.events.push(EventRecord {
                    step_index: ev.get("step_index").and_then(Value::as_u64).unwrap_or(0) as usize,
                    sim_tick: ev.get("sim_tick").and_then(Value::as_u64).unwrap_or(0) as usize,
                    episode_id: ev
                        .get("episode_id")
                        .and_then(Value::as_str)
                        .unwrap_or("")
                        .into(),
                    kind: ev.get("kind").and_then(Value::as_str).unwrap_or("").into(),
                    severity: ev
                        .get("severity")
                        .and_then(Value::as_str)
                        .unwrap_or("info")
                        .into(),
                    message: ev.get("message").and_then(Value::as_str).unwrap_or("").into(),
                    action: ev
                        .get("action")
                        .and_then(Value::as_str)
                        .map(str::to_string),
                    transition: ev.get("transition").cloned(),
                    payload: ev.get("payload").cloned().unwrap_or_else(|| json!({})),
                });
            }
        }
        self.events.len()
    }

    pub fn legacy_strings(&self) -> Vec<String> {
        self.events.iter().map(|e| e.message.clone()).collect()
    }
}

fn crate_sort(v: &Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut out = serde_json::Map::new();
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            for k in keys {
                out.insert(k.clone(), crate_sort(&map[&k]));
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.iter().map(crate_sort).collect()),
        other => other.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parity_mini_solve() {
        let task = json!({
            "schema": "gamebench.task.sokoban.v1",
            "task_id": "parity_mini",
            "map": {"source": "inline", "grid": ["#####", "#@$.#", "#####"]},
            "rules": {"base": "sparse_sokoban"},
        });
        let mut session = SokobanSession::reset_from_task(&task, Some(0));
        let reset = session.readout();
        assert_eq!(reset["ascii"], "#####\n#@$.#\n#####");
        assert_eq!(reset["grid_hash"], "33abd76821e455d7");
        session.step("right");
        let after = session.readout();
        assert_eq!(after["ascii"], "#####\n# @*#\n#####");
        assert_eq!(after["grid_hash"], "1358d72987b72f1f");
        assert!(session.private.terminated);
        assert!((session.private.total_reward - 1.09).abs() < 1e-9);
        assert!(session.private.achievements.contains("level_complete"));
        assert!(session.private.achievements.contains("first_push"));
        assert!(session.private.achievements.contains("first_box_on_target"));
    }
}
