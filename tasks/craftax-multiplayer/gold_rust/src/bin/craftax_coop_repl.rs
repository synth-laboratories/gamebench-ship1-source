//! JSONL evaluator bridge for the Craftax-Coop Rust authority.
//!
//! The evaluator collects one policy decision per specialized agent, then
//! advances the environment exactly once with the resulting simultaneous joint
//! action. This intentionally does not emulate the prior round-robin
//! shared-world adapter: a Craftax-Coop timestep is a joint action.

use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use craftax_coop_gamebench::render::{render_rgb, RenderMode};
use craftax_coop_gamebench::CraftaxCoopEnv;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::io::{self, BufRead, Write};

const COOP_AGENT_COUNT: usize = 3;

struct Session {
    env: CraftaxCoopEnv,
    pending_actions: BTreeMap<String, String>,
    task_id: String,
    total_reward: f64,
}

impl Session {
    fn reset(request: &Value) -> Result<Self, String> {
        let task = request.get("task").filter(|value| value.is_object()).unwrap_or(request);
        let agent_count = request
            .get("agent_count")
            .or_else(|| task.get("agent_count"))
            .and_then(Value::as_u64)
            .unwrap_or(COOP_AGENT_COUNT as u64) as usize;
        if agent_count != COOP_AGENT_COUNT {
            return Err(format!(
                "Craftax-Coop requires exactly {COOP_AGENT_COUNT} specialized agents (warrior, forager, miner), got {agent_count}"
            ));
        }
        let seed = request
            .get("seed")
            .or_else(|| task.get("seed"))
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let max_timesteps = task
            .get("max_timesteps")
            .or_else(|| task.get("max_steps"))
            .and_then(Value::as_u64)
            .unwrap_or(80);
        Ok(Self {
            env: CraftaxCoopEnv::reset(seed, COOP_AGENT_COUNT, max_timesteps),
            pending_actions: BTreeMap::new(),
            task_id: task
                .get("task_id")
                .and_then(Value::as_str)
                .unwrap_or("craftax-coop")
                .to_string(),
            total_reward: 0.0,
        })
    }

    fn agent_ids(&self) -> Vec<String> {
        self.env.state.players.iter().map(|player| player.agent_id.clone()).collect()
    }

    fn readout(&self, agent_id: &str) -> Result<Value, String> {
        let observations = self.env.observations(5);
        let observation = observations
            .get(agent_id)
            .cloned()
            .ok_or_else(|| format!("unknown Craftax-Coop agent: {agent_id}"))?;
        let state_json = serde_json::to_vec(&self.env.state).map_err(|error| error.to_string())?;
        let grid_hash = format!("{:x}", Sha256::digest(state_json));
        let done_reason = self.env.state.termination_reason.clone();
        let achievements = self.env.state.achievements.iter().cloned().collect::<Vec<_>>();
        Ok(json!({
            "task_id": self.task_id,
            "observation": observation,
            "observation_text": serde_json::to_string(&observations[agent_id]).map_err(|error| error.to_string())?,
            "ascii": observations[agent_id].get("ascii").and_then(Value::as_str).unwrap_or_default(),
            "valid_actions": observations[agent_id].get("legal_actions").cloned().unwrap_or_else(|| json!([])),
            "grid_hash": grid_hash,
            "active_agent": agent_id,
            "agent_ids": self.agent_ids(),
            "shared_achievements": achievements,
            "private": {
                "terminated": self.env.state.terminated,
                "truncated": self.env.state.termination_reason.as_deref() == Some("max_timesteps"),
                "done_reason": done_reason,
                "total_reward": self.total_reward,
                "step_index": self.env.state.timestep,
                "pending_joint_actions": self.pending_actions.len(),
                "trade_count": self.env.state.trade_count,
                "food_trade_count": self.env.state.food_trade_count,
                "drink_trade_count": self.env.state.drink_trade_count,
                "revives": self.env.state.revives,
            },
        }))
    }

    fn step(&mut self, agent_id: &str, action: &str) -> Result<Value, String> {
        if self.env.state.terminated {
            return Err("Craftax-Coop episode is terminal".to_string());
        }
        if self.pending_actions.contains_key(agent_id) {
            return Err(format!("joint action already supplied for {agent_id}"));
        }
        if !self.env.legal_actions(agent_id).iter().any(|legal| legal == action) {
            return Err(format!("illegal action for {agent_id}: {action}"));
        }
        self.pending_actions.insert(agent_id.to_string(), action.to_string());
        let mut environment_step = false;
        let mut events = json!([]);
        if self.pending_actions.len() == COOP_AGENT_COUNT {
            let result = self.env.step(&self.pending_actions)?;
            self.total_reward += result.rewards.values().sum::<f64>() / COOP_AGENT_COUNT as f64;
            self.pending_actions.clear();
            environment_step = true;
            events = serde_json::to_value(result.events).map_err(|error| error.to_string())?;
        }
        let readout = self.readout(agent_id)?;
        Ok(json!({
            "readout": readout,
            "environment_step": environment_step,
            "joint_events": events,
            "terminated": self.env.state.terminated,
            "truncated": self.env.state.termination_reason.as_deref() == Some("max_timesteps"),
        }))
    }

    fn render_png(&self) -> Result<Value, String> {
        let frame = render_rgb(&self.env, RenderMode::Auto)?;
        let png = frame.png()?;
        Ok(json!({
            "png_base64": BASE64.encode(png),
            "width": frame.width,
            "height": frame.height,
        }))
    }
}

struct Runtime {
    session: Option<Session>,
    request_id: u64,
}

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    let mut runtime = Runtime { session: None, request_id: 0 };
    for line in stdin.lock().lines() {
        let Ok(line) = line else { continue; };
        if line.trim().is_empty() { continue; }
        let request = match serde_json::from_str::<Value>(&line) {
            Ok(request) => request,
            Err(error) => {
                write_response(&mut stdout, Value::Null, Err(error.to_string()));
                continue;
            }
        };
        runtime.request_id += 1;
        let id = request.get("id").cloned().unwrap_or(Value::Null);
        let response = handle(&mut runtime, &request);
        write_response(&mut stdout, id, response);
    }
}

fn handle(runtime: &mut Runtime, request: &Value) -> Result<Value, String> {
    match request.get("op").and_then(Value::as_str).unwrap_or_default() {
        "ping" => Ok(json!({"lane":"craftax_coop_rust_repl","joint_action":true,"agent_count":COOP_AGENT_COUNT})),
        "close" => {
            runtime.session = None;
            Ok(json!({}))
        }
        "reset" => {
            let session = Session::reset(request)?;
            let active_agent = session.agent_ids().into_iter().next().ok_or_else(|| "Craftax-Coop has no agents".to_string())?;
            let agent_ids = session.agent_ids();
            let readout = session.readout(&active_agent)?;
            runtime.session = Some(session);
            Ok(json!({"active_agent":active_agent,"agent_ids":agent_ids,"readout":readout}))
        }
        "readout" => with_session(runtime, |session| {
            let agent_id = request.get("agent_id").and_then(Value::as_str).unwrap_or("agent_0");
            Ok(json!({"active_agent":agent_id,"readout":session.readout(agent_id)?}))
        }),
        "step" => with_session(runtime, |session| {
            let agent_id = request.get("agent_id").and_then(Value::as_str).ok_or_else(|| "Craftax-Coop step requires agent_id".to_string())?;
            let action = request.get("action").and_then(Value::as_str).ok_or_else(|| "Craftax-Coop step requires action".to_string())?;
            session.step(agent_id, action)
        }),
        "render_png" => with_session(runtime, |session| session.render_png()),
        other => Err(format!("unknown Craftax-Coop REPL operation: {other}")),
    }
}

fn with_session<F>(runtime: &mut Runtime, operation: F) -> Result<Value, String>
where
    F: FnOnce(&mut Session) -> Result<Value, String>,
{
    let session = runtime.session.as_mut().ok_or_else(|| "no active Craftax-Coop session; call reset first".to_string())?;
    operation(session)
}

fn write_response(stdout: &mut io::Stdout, id: Value, response: Result<Value, String>) {
    let mut payload = match response {
        Ok(payload) => json!({"ok":true,"result":payload}),
        Err(error) => json!({"ok":false,"error":error}),
    };
    let result = payload.as_object_mut().expect("JSON response object");
    result.insert("id".to_string(), id);
    if let Some(value) = result.remove("result") {
        if let Value::Object(values) = value {
            result.extend(values);
        }
    }
    let _ = writeln!(stdout, "{}", serde_json::to_string(&payload).expect("JSON response serialization"));
    let _ = stdout.flush();
}
