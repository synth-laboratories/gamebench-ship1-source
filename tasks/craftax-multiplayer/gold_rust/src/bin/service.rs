use craftax_coop_gamebench::CraftaxCoopEnv;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

struct Service {
    env: CraftaxCoopEnv,
    rollouts: BTreeMap<String, CraftaxCoopEnv>,
    next_rollout: u64,
}

impl Service {
    fn new() -> Self {
        Self {
            env: CraftaxCoopEnv::reset(0, 3, 100_000),
            rollouts: BTreeMap::new(),
            next_rollout: 1,
        }
    }

    fn configuration(body: &Value) -> Result<(u64, usize, u64), String> {
        let task = body
            .get("task")
            .filter(|value| value.is_object())
            .unwrap_or(body);
        let seed = body
            .get("seed")
            .or_else(|| task.get("seed"))
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let agent_count = task
            .get("agent_count")
            .and_then(Value::as_u64)
            .map(|value| value as usize)
            .or_else(|| {
                task.get("agents")
                    .and_then(Value::as_array)
                    .filter(|agents| !agents.is_empty())
                    .map(Vec::len)
            })
            .unwrap_or(3);
        if agent_count < 2 {
            return Err("Craftax-Coop requires at least two agents".into());
        }
        let max_timesteps = task
            .get("max_timesteps")
            .or_else(|| task.get("max_steps"))
            .and_then(Value::as_u64)
            .unwrap_or(100_000);
        Ok((seed, agent_count, max_timesteps))
    }

    fn new_env(body: &Value) -> Result<CraftaxCoopEnv, String> {
        let (seed, agent_count, max_timesteps) = Self::configuration(body)?;
        Ok(CraftaxCoopEnv::reset(seed, agent_count, max_timesteps))
    }

    fn agent_ids(env: &CraftaxCoopEnv) -> Vec<String> {
        env.state
            .players
            .iter()
            .map(|player| player.agent_id.clone())
            .collect()
    }

    fn joint_action(
        env: &CraftaxCoopEnv,
        raw: Option<&Value>,
        fill_missing: bool,
    ) -> Result<BTreeMap<String, String>, String> {
        let object = raw
            .and_then(Value::as_object)
            .ok_or_else(|| "joint_action must be an object".to_string())?;
        let mut actions = object
            .iter()
            .map(|(agent, value)| {
                let action = value
                    .as_str()
                    .or_else(|| value.get("kind").and_then(Value::as_str))
                    .ok_or_else(|| format!("invalid action for {agent}"))?;
                Ok((agent.clone(), action.to_string()))
            })
            .collect::<Result<BTreeMap<_, _>, String>>()?;
        if fill_missing {
            for agent in Self::agent_ids(env) {
                actions.entry(agent).or_insert_with(|| "noop".into());
            }
        }
        Ok(actions)
    }

    fn readout(env: &CraftaxCoopEnv) -> Value {
        json!({
            "observations": env.observations(5),
            "state": env.state,
            "terminated": env.state.terminated,
            "termination_reason": env.state.termination_reason,
            "timestep": env.state.timestep,
        })
    }

    fn nev(env: &CraftaxCoopEnv, rollout_id: Option<&str>) -> Value {
        let mut payload = Map::from_iter([
            ("structured".into(), json!(env.state.nev)),
            ("legacy".into(), json!(env.state.legacy_nev)),
            ("nev_cursor".into(), json!(env.state.nev.len())),
        ]);
        if let Some(rollout_id) = rollout_id {
            payload.insert("rollout_id".into(), json!(rollout_id));
        }
        Value::Object(payload)
    }

    fn step_payload(
        env: &mut CraftaxCoopEnv,
        actions: BTreeMap<String, String>,
        rollout_id: Option<&str>,
    ) -> Result<Value, String> {
        let step = env.step(&actions)?;
        let mut payload = Map::from_iter([
            ("observations".into(), json!(env.observations(5))),
            ("rewards".into(), json!(step.rewards)),
            ("dones".into(), json!(step.dones)),
            (
                "info".into(),
                json!({"events":step.events,"termination_reason":env.state.termination_reason}),
            ),
        ]);
        if let Some(rollout_id) = rollout_id {
            payload.insert("rollout_id".into(), json!(rollout_id));
        }
        Ok(Value::Object(payload))
    }

    fn run_scenario(body: &Value) -> Result<Value, String> {
        let task = body
            .get("task")
            .filter(|value| value.is_object())
            .ok_or_else(|| "task must be an object".to_string())?;
        let mut env = Self::new_env(task)?;
        let scenario_id = task
            .get("scenario_id")
            .or_else(|| task.get("task_id"))
            .and_then(Value::as_str)
            .unwrap_or("manual");
        let checkpoint_after = task.get("checkpoint_after").and_then(Value::as_u64);
        let mut checkpoint: Option<String> = None;
        if let Some(joint_actions) = task.get("joint_actions").and_then(Value::as_array) {
            for (index, raw_action) in joint_actions.iter().enumerate() {
                if env.state.terminated {
                    break;
                }
                let actions = Self::joint_action(&env, Some(raw_action), true)?;
                env.step(&actions)?;
                if checkpoint_after == Some(index as u64 + 1) {
                    checkpoint = Some(env.checkpoint_json());
                }
            }
        }
        if let Some(checkpoint) = checkpoint {
            env = CraftaxCoopEnv::restore_json(&checkpoint).map_err(|error| error.to_string())?;
            if let Some(actions) = task.get("restore_then_actions").and_then(Value::as_array) {
                for raw_action in actions {
                    if env.state.terminated {
                        break;
                    }
                    let joint = Self::joint_action(&env, Some(raw_action), true)?;
                    env.step(&joint)?;
                }
            }
        }
        Ok(json!({
            "scenario_id": scenario_id,
            "events": env.state.legacy_nev,
            "nev": env.state.nev,
            "checkpoint_cursor": env.state.nev.len(),
            "state": env.state,
            "readout": Self::readout(&env),
        }))
    }
}

fn response(stream: &mut TcpStream, status: u16, payload: Value) {
    let body = serde_json::to_string(&payload).unwrap();
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
    let mut chunk = [0u8; 16_384];
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
        return;
    };
    let Some(request_line) = raw.lines().next() else {
        response(stream, 400, json!({"error":"missing request line"}));
        return;
    };
    let mut parts = request_line.split_whitespace();
    let Some(method) = parts.next() else {
        response(stream, 400, json!({"error":"missing HTTP method"}));
        return;
    };
    let Some(path) = parts.next() else {
        response(stream, 400, json!({"error":"missing HTTP path"}));
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
        let Some(env) = service.rollouts.get_mut(rollout_id) else {
            response(stream, 404, json!({"error":"rollout_not_found"}));
            return;
        };
        let result = match (method, operation) {
            ("POST", "step") => Service::joint_action(env, body.get("joint_action"), false)
                .and_then(|actions| Service::step_payload(env, actions, Some(rollout_id))),
            ("GET" | "POST", "checkpoint" | "checkpoints") => {
                let checkpoint = serde_json::from_str::<Value>(&env.checkpoint_json())
                    .map_err(|error| error.to_string());
                checkpoint.map(|checkpoint| {
                    let bytes = serde_json::to_vec(&checkpoint).map(|value| value.len()).unwrap_or(0);
                    json!({"rollout_id":rollout_id,"checkpoint":checkpoint,"bytes":bytes,"nev_cursor":env.state.nev.len()})
                })
            }
            ("POST", "restore") => {
                let checkpoint = body.get("checkpoint").unwrap_or(&body);
                match CraftaxCoopEnv::restore_json(&checkpoint.to_string()) {
                    Ok(restored) => {
                        *env = restored;
                        Ok(
                            json!({"rollout_id":rollout_id,"observations":env.observations(5),"readout":Service::readout(env)}),
                        )
                    }
                    Err(error) => Err(error.to_string()),
                }
            }
            ("GET", "readout" | "state") => {
                let readout = Service::readout(env);
                Ok(
                    json!({"rollout_id":rollout_id,"observations":readout["observations"],"state":readout["state"],"terminated":readout["terminated"],"termination_reason":readout["termination_reason"],"timestep":readout["timestep"]}),
                )
            }
            ("GET", "nev" | "event_log" | "events") => Ok(Service::nev(env, Some(rollout_id))),
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
        ("GET", "/health") => Ok(json!({"ok":true,"env_family":"craftax-multiplayer","runtime":"rust","sessions":service.rollouts.len()})),
        ("GET", "/agents") => Ok(json!(Service::agent_ids(&service.env))),
        ("POST", "/run_scenario") => Service::run_scenario(&body),
        ("POST", "/rollouts") => Service::new_env(&body).map(|env| {
            let rollout_id = format!("rollout-{}", service.next_rollout);
            service.next_rollout += 1;
            let observations = env.observations(5);
            let seed = env.state.seed;
            let readout = Service::readout(&env);
            service.rollouts.insert(rollout_id.clone(), env);
            json!({"rollout_id":rollout_id,"observations":observations,"info":{"seed":seed},"readout":readout})
        }),
        ("POST", "/reset") => Service::new_env(&body).map(|env| {
            let seed = env.state.seed;
            let observations = env.observations(5);
            service.env = env;
            json!({"observations":observations,"info":{"seed":seed}})
        }),
        ("POST", "/step") => Service::joint_action(&service.env, body.get("joint_action"), false)
            .and_then(|actions| Service::step_payload(&mut service.env, actions, None)),
        ("GET", "/checkpoint") => {
            serde_json::from_str(&service.env.checkpoint_json()).map_err(|error| error.to_string())
        }
        ("POST", "/restore") => match CraftaxCoopEnv::restore_json(&body.to_string()) {
            Ok(restored) => {
                service.env = restored;
                Ok(json!({"observations":service.env.observations(5)}))
            }
            Err(error) => Err(error.to_string()),
        },
        ("GET", "/nev") => Ok(Service::nev(&service.env, None)),
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

fn main() {
    let argument = std::env::args().nth(1);
    if argument
        .as_deref()
        .is_some_and(|value| ["-h", "--help"].contains(&value))
    {
        println!("Usage: service [HOST:PORT]\nDefault: 127.0.0.1:8081");
        return;
    }
    let address = argument.unwrap_or_else(|| "127.0.0.1:8081".into());
    let listener =
        TcpListener::bind(&address).unwrap_or_else(|error| panic!("bind {address}: {error}"));
    let mut service = Service::new();
    for connection in listener.incoming() {
        if let Ok(mut stream) = connection {
            handle(&mut stream, &mut service)
        }
    }
}
