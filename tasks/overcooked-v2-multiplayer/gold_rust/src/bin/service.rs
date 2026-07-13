use overcooked_v2_gold::OvercookedV2Env;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;

struct Service {
    defaults_dir: PathBuf,
    rollouts: BTreeMap<String, OvercookedV2Env>,
    next_rollout: u64,
}

impl Service {
    fn new() -> Result<Self, String> {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let task_dir = manifest_dir
            .parent()
            .ok_or_else(|| "gold_rust must have a task parent".to_string())?;
        Ok(Self {
            defaults_dir: task_dir.join("defaults"),
            rollouts: BTreeMap::new(),
            next_rollout: 1,
        })
    }

    fn task_from_body<'a>(&self, body: &'a Value) -> Result<&'a Value, String> {
        body.get("task")
            .filter(|value| value.is_object())
            .or_else(|| body.is_object().then_some(body))
            .ok_or_else(|| "request must contain a task object".to_string())
    }

    fn new_environment(&self, body: &Value) -> Result<OvercookedV2Env, String> {
        let task = self.task_value(body)?;
        OvercookedV2Env::from_task_value(&task, &self.defaults_dir)
    }

    fn task_value(&self, body: &Value) -> Result<Value, String> {
        let mut task = self
            .task_from_body(body)?
            .as_object()
            .cloned()
            .ok_or_else(|| "task must be an object".to_string())?;
        if !task.contains_key("seed") {
            if let Some(seed) = body.get("seed") {
                task.insert("seed".to_string(), seed.clone());
            }
        }
        if let Some(profile) = body.get("observation_profile") {
            let readouts = task
                .entry("readouts".to_string())
                .or_insert_with(|| json!({}));
            let readouts = readouts
                .as_object_mut()
                .ok_or_else(|| "task.readouts must be an object".to_string())?;
            readouts.insert("profile".to_string(), profile.clone());
        }
        Ok(Value::Object(task))
    }

    fn payload(rollout_id: Option<&str>, environment: &OvercookedV2Env) -> Result<Value, String> {
        let readout = environment.readout()?;
        let mut payload = json!({
            "readout": readout,
            "reward": readout.private.total_reward,
            "terminated": readout.private.terminated,
            "truncated": readout.private.truncated,
            "nev_cursor": readout.nev_cursor,
            "terminal_metrics": environment.terminal_metrics()?,
        });
        if let (Some(rollout_id), Some(object)) = (rollout_id, payload.as_object_mut()) {
            object.insert("rollout_id".to_string(), json!(rollout_id));
        }
        Ok(payload)
    }

    fn checkpoint_payload(
        rollout_id: Option<&str>,
        environment: &OvercookedV2Env,
    ) -> Result<Value, String> {
        let blob = environment.checkpoint_json()?;
        let checkpoint: Value = serde_json::from_str(&blob)
            .map_err(|error| format!("parse serialized checkpoint: {error}"))?;
        Ok(json!({
            "rollout_id": rollout_id,
            "checkpoint": checkpoint,
            "blob": blob,
            "encoding": "utf8_json",
            "bytes": blob.len(),
            "digest": environment.checkpoint_digest()?,
            "nev_cursor": environment.events().len(),
        }))
    }

    fn checkpoint_text(body: &Value) -> Result<String, String> {
        if let Some(blob) = body.get("blob").and_then(Value::as_str) {
            return Ok(blob.to_string());
        }
        if let Some(checkpoint) = body.get("checkpoint") {
            return serde_json::to_string(checkpoint)
                .map_err(|error| format!("serialize checkpoint request: {error}"));
        }
        if body.get("schema_version").is_some() {
            return serde_json::to_string(body)
                .map_err(|error| format!("serialize checkpoint request: {error}"));
        }
        Err("restore requires checkpoint object or UTF-8 JSON blob".to_string())
    }

    fn run_scenario(&self, body: &Value) -> Result<Value, String> {
        let inline_task = self.task_from_body(body)?;
        let task = self.task_value(body)?;
        let mut environment = OvercookedV2Env::from_task_value(&task, &self.defaults_dir)?;
        let joint_actions = body
            .get("joint_actions")
            .or_else(|| inline_task.get("joint_actions"))
            .and_then(Value::as_array);
        if let Some(actions) = joint_actions {
            for action in actions {
                let readout = environment.step_json(action)?;
                if readout.dones.get("__all__").copied().unwrap_or(false) {
                    break;
                }
            }
        }
        Ok(json!({
            "scenario_id": environment.resolved().scenario_id,
            "events": environment.events().iter().map(|event| event.message.clone()).collect::<Vec<_>>(),
            "nev": environment.events(),
            "checkpoint_cursor": environment.events().len(),
            "readout": environment.readout()?,
            "terminal_metrics": environment.terminal_metrics()?,
        }))
    }

    fn simulate(environment: &OvercookedV2Env, body: &Value) -> Result<Value, String> {
        let checkpoint_text = if body.get("checkpoint").is_some() || body.get("blob").is_some() {
            Self::checkpoint_text(body)?
        } else {
            environment.checkpoint_json()?
        };
        let sequences = body
            .get("sequences")
            .and_then(Value::as_array)
            .ok_or_else(|| "simulate requires sequences array".to_string())?;
        let mut results = Vec::new();
        for (index, sequence) in sequences.iter().enumerate() {
            let mut simulation = OvercookedV2Env::from_checkpoint_json(&checkpoint_text)?;
            let actions = sequence
                .as_array()
                .ok_or_else(|| format!("simulate sequence {index} must be an array"))?;
            for action in actions {
                let readout = simulation.step_json(action)?;
                if readout.dones.get("__all__").copied().unwrap_or(false) {
                    break;
                }
            }
            results.push(json!({
                "index": index,
                "readout": simulation.readout()?,
                "terminal_metrics": simulation.terminal_metrics()?,
                "state_digest": simulation.state_digest()?,
            }));
        }
        Ok(json!({
            "root_checkpoint_digest": overcooked_v2_gold::sha256_digest(checkpoint_text.as_bytes()),
            "results": results,
        }))
    }
}

fn response(stream: &mut TcpStream, status: u16, payload: Value) {
    let body = serde_json::to_string(&payload).unwrap_or_else(|error| {
        json!({"error":"response_serialization_failed","message":error.to_string()}).to_string()
    });
    let label = match status {
        200 => "OK",
        404 => "Not Found",
        _ => "Bad Request",
    };
    let raw = format!(
        "HTTP/1.1 {status} {label}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(raw.as_bytes());
}

fn read_request(stream: &mut TcpStream) -> Option<String> {
    let mut buffer = Vec::with_capacity(262_144);
    let mut chunk = [0_u8; 16_384];
    loop {
        let size = stream.read(&mut chunk).ok()?;
        if size == 0 {
            return None;
        }
        buffer.extend_from_slice(&chunk[..size]);
        if let Some(header_end) = buffer.windows(4).position(|window| window == b"\r\n\r\n") {
            let headers = String::from_utf8_lossy(&buffer[..header_end]);
            let content_length = headers
                .lines()
                .find_map(|line| {
                    let (name, value) = line.split_once(':')?;
                    name.eq_ignore_ascii_case("content-length")
                        .then(|| value.trim().parse::<usize>().ok())
                        .flatten()
                })
                .unwrap_or(0);
            if buffer.len() >= header_end + 4 + content_length {
                return String::from_utf8(buffer[..header_end + 4 + content_length].to_vec()).ok();
            }
        }
        if buffer.len() > 8 * 1024 * 1024 {
            return None;
        }
    }
}

fn handle(stream: &mut TcpStream, service: &mut Service) {
    let Some(raw) = read_request(stream) else {
        return;
    };
    let Some(header_end) = raw.find("\r\n\r\n") else {
        response(stream, 400, json!({"error":"missing_headers"}));
        return;
    };
    let Some(request_line) = raw.lines().next() else {
        response(stream, 400, json!({"error":"missing_request_line"}));
        return;
    };
    let mut parts = request_line.split_whitespace();
    let Some(method) = parts.next() else {
        response(stream, 400, json!({"error":"missing_method"}));
        return;
    };
    let Some(path) = parts.next() else {
        response(stream, 400, json!({"error":"missing_path"}));
        return;
    };
    let body_text = &raw[header_end + 4..];
    let body = if body_text.is_empty() {
        json!({})
    } else {
        match serde_json::from_str::<Value>(body_text) {
            Ok(value) => value,
            Err(error) => {
                response(
                    stream,
                    400,
                    json!({"error":"invalid_json","message":error.to_string()}),
                );
                return;
            }
        }
    };

    let path_parts = path.trim_matches('/').split('/').collect::<Vec<_>>();
    if path_parts.len() == 3 && path_parts[0] == "rollouts" {
        let rollout_id = path_parts[1];
        let operation = path_parts[2];
        let Some(environment) = service.rollouts.get_mut(rollout_id) else {
            response(stream, 404, json!({"error":"rollout_not_found"}));
            return;
        };
        let result = match (method, operation) {
            ("POST", "step") => body
                .get("joint_action")
                .ok_or_else(|| "step requires joint_action".to_string())
                .and_then(|joint_action| environment.step_json(joint_action))
                .and_then(|_| Service::payload(Some(rollout_id), environment)),
            ("GET" | "POST", "checkpoint" | "checkpoints") => {
                Service::checkpoint_payload(Some(rollout_id), environment)
            }
            ("POST", "restore") => Service::checkpoint_text(&body).and_then(|checkpoint| {
                environment.restore_checkpoint_json(&checkpoint)?;
                Service::payload(Some(rollout_id), environment)
            }),
            ("POST", "simulate") => Service::simulate(environment, &body),
            ("GET", "readout" | "state") => Service::payload(Some(rollout_id), environment),
            ("GET", "event_log" | "events" | "nev") => Ok(json!({
                "rollout_id": rollout_id,
                "events": environment.events(),
                "legacy": environment.events().iter().map(|event| event.message.clone()).collect::<Vec<_>>(),
                "nev_cursor": environment.events().len(),
            })),
            _ => {
                response(stream, 404, json!({"error":"not_found"}));
                return;
            }
        };
        match result {
            Ok(payload) => response(stream, 200, payload),
            Err(error) => response(stream, 400, json!({"error":error})),
        }
        return;
    }

    let result: Result<Value, String> = match (method, path) {
        ("GET", "/health") => Ok(json!({
            "ok": true,
            "lane": "rust",
            "env_family": "overcooked-v2-multiplayer",
            "sessions": service.rollouts.len(),
        })),
        ("GET", "/info") => Ok(json!({
            "env_family": "overcooked-v2-multiplayer",
            "runtime": "rust",
            "capabilities": ["simultaneous_joint_step", "partial_symbolic_observation", "checkpoint_restore", "simulate", "nev_log", "terminal_metrics"],
            "observation_profiles": ["symbolic_compact"],
        })),
        ("POST", "/run_scenario") => service.run_scenario(&body),
        ("POST", "/rollouts") => service.new_environment(&body).and_then(|environment| {
            let rollout_id = format!("rollout-{}", service.next_rollout);
            service.next_rollout += 1;
            let payload = Service::payload(Some(&rollout_id), &environment)?;
            service.rollouts.insert(rollout_id, environment);
            Ok(payload)
        }),
        _ => {
            response(stream, 404, json!({"error":"not_found"}));
            return;
        }
    };
    match result {
        Ok(payload) => response(stream, 200, payload),
        Err(error) => response(stream, 400, json!({"error":error})),
    }
}

fn main() -> Result<(), String> {
    let argument = std::env::args().nth(1);
    if argument
        .as_deref()
        .is_some_and(|value| ["-h", "--help"].contains(&value))
    {
        println!("Usage: service [HOST:PORT]\nDefault: 127.0.0.1:8081");
        return Ok(());
    }
    let address = argument.unwrap_or_else(|| "127.0.0.1:8081".to_string());
    let listener = TcpListener::bind(&address)
        .map_err(|error| format!("bind Rust Overcooked service {address}: {error}"))?;
    let mut service = Service::new()?;
    for mut stream in listener.incoming().flatten() {
        handle(&mut stream, &mut service);
    }
    Ok(())
}
