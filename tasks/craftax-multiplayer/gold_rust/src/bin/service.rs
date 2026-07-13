use craftax_coop_gamebench::render::{encode_gif, render_rgb, RenderMode, RgbFrame};
use craftax_coop_gamebench::CraftaxCoopEnv;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

struct Service {
    env: CraftaxCoopEnv,
    rollouts: BTreeMap<String, CraftaxCoopEnv>,
    frames: BTreeMap<String, BTreeMap<u64, RgbFrame>>,
    capture_frames: BTreeMap<String, bool>,
    render_modes: BTreeMap<String, RenderMode>,
    next_rollout: u64,
}

impl Service {
    fn new() -> Self {
        Self {
            env: CraftaxCoopEnv::reset(0, 3, 100_000),
            rollouts: BTreeMap::new(),
            frames: BTreeMap::new(),
            capture_frames: BTreeMap::new(),
            render_modes: BTreeMap::new(),
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

    fn visual_configuration(body: &Value) -> Result<(bool, RenderMode), String> {
        let task = body
            .get("task")
            .filter(|value| value.is_object())
            .unwrap_or(body);
        let readouts = task.get("readouts");
        let visual = readouts
            .and_then(|value| value.get("visual"))
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let stream = readouts.and_then(|value| value.get("stream"));
        let capture = visual
            || stream
                .and_then(|value| value.get("enabled"))
                .and_then(Value::as_bool)
                .unwrap_or(false)
            || stream
                .and_then(|value| value.get("persist_frames"))
                .and_then(Value::as_bool)
                .unwrap_or(false);
        let raw_mode = task
            .get("render_mode")
            .or_else(|| {
                task.get("readouts")
                    .and_then(|value| value.get("render_mode"))
            })
            .and_then(Value::as_str);
        Ok((capture, RenderMode::parse(raw_mode)?))
    }

    fn store_frame(&mut self, rollout_id: &str) -> Result<(), String> {
        let env = self
            .rollouts
            .get(rollout_id)
            .ok_or_else(|| "rollout_not_found".to_string())?;
        let mode = self
            .render_modes
            .get(rollout_id)
            .copied()
            .unwrap_or(RenderMode::Auto);
        let frame = render_rgb(env, mode)?;
        self.frames
            .entry(rollout_id.to_string())
            .or_default()
            .insert(env.state.timestep, frame);
        Ok(())
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

fn binary_response(stream: &mut TcpStream, status: u16, content_type: &str, body: &[u8]) {
    let label = if status == 200 { "OK" } else { "Not Found" };
    let headers = format!(
        "HTTP/1.1 {status} {label}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(headers.as_bytes());
    let _ = stream.write_all(body);
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
    let Some(request_target) = parts.next() else {
        response(stream, 400, json!({"error":"missing HTTP path"}));
        return;
    };
    let (path, query) = request_target
        .split_once('?')
        .unwrap_or((request_target, ""));
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

    let query_value = |name: &str| {
        query.split('&').find_map(|part| {
            let (key, value) = part.split_once('=')?;
            (key == name).then_some(value)
        })
    };
    let path_parts = path.trim_matches('/').split('/').collect::<Vec<_>>();
    if path_parts.len() == 4 && path_parts[0] == "rollouts" && path_parts[2] == "frames" {
        let rollout_id = path_parts[1];
        if !service.rollouts.contains_key(rollout_id) {
            response(stream, 404, json!({"error":"rollout_not_found"}));
            return;
        }
        if path_parts[3] == "manifest" && method == "GET" {
            let frames = service.frames.get(rollout_id).into_iter().flat_map(|frames| frames.iter()).filter_map(|(step, frame)| {
                let png = frame.png().ok()?;
                let sha256 = format!("{:x}", Sha256::digest(&png));
                Some(json!({"step":step,"bytes":png.len(),"sha256":sha256,"url":format!("/rollouts/{rollout_id}/frames/{step}.png")}))
            }).collect::<Vec<_>>();
            response(
                stream,
                200,
                json!({"rollout_id":rollout_id,"frame_count":frames.len(),"latest_step":frames.last().and_then(|frame|frame.get("step")).cloned(),"frames":frames}),
            );
            return;
        }
        if method == "GET" {
            let Some(step_text) = path_parts[3].strip_suffix(".png") else {
                response(stream, 404, json!({"error":"not_found"}));
                return;
            };
            let Ok(step) = step_text.parse::<u64>() else {
                response(stream, 404, json!({"error":"frame_not_found"}));
                return;
            };
            let current = service.rollouts[rollout_id].state.timestep;
            if step == current
                && !service
                    .frames
                    .get(rollout_id)
                    .is_some_and(|frames| frames.contains_key(&step))
            {
                if let Err(error) = service.store_frame(rollout_id) {
                    response(stream, 400, json!({"error":error}));
                    return;
                }
            }
            match service
                .frames
                .get(rollout_id)
                .and_then(|frames| frames.get(&step))
                .and_then(|frame| frame.png().ok())
            {
                Some(png) => binary_response(stream, 200, "image/png", &png),
                None => response(stream, 404, json!({"error":"frame_not_found"})),
            }
            return;
        }
    }
    if path_parts.len() == 3 && path_parts[0] == "rollouts" {
        let rollout_id = path_parts[1];
        let operation = path_parts[2];
        if method == "GET" && operation == "render.png" {
            let Some(env) = service.rollouts.get(rollout_id) else {
                response(stream, 404, json!({"error":"rollout_not_found"}));
                return;
            };
            let mode = match query_value("render_mode")
                .map(|value| RenderMode::parse(Some(value)))
                .unwrap_or_else(|| {
                    Ok(service
                        .render_modes
                        .get(rollout_id)
                        .copied()
                        .unwrap_or(RenderMode::Auto))
                }) {
                Ok(mode) => mode,
                Err(error) => {
                    response(stream, 400, json!({"error":error}));
                    return;
                }
            };
            match render_rgb(env, mode).and_then(|frame| frame.png()) {
                Ok(png) => binary_response(stream, 200, "image/png", &png),
                Err(error) => response(stream, 400, json!({"error":error})),
            }
            return;
        }
        if method == "GET" && operation == "replay.gif" {
            if !service.rollouts.contains_key(rollout_id) {
                response(stream, 404, json!({"error":"rollout_not_found"}));
                return;
            }
            if service
                .frames
                .get(rollout_id)
                .is_none_or(BTreeMap::is_empty)
            {
                if let Err(error) = service.store_frame(rollout_id) {
                    response(stream, 400, json!({"error":error}));
                    return;
                }
            }
            let through_step =
                query_value("through_step").and_then(|value| value.parse::<u64>().ok());
            let frames = service
                .frames
                .get(rollout_id)
                .into_iter()
                .flat_map(|frames| frames.iter())
                .filter(|(step, _)| through_step.is_none_or(|limit| **step <= limit))
                .map(|(_, frame)| frame.clone())
                .collect::<Vec<_>>();
            match encode_gif(&frames, 10) {
                Ok(gif) => binary_response(stream, 200, "image/gif", &gif),
                Err(error) => response(stream, 400, json!({"error":error})),
            }
            return;
        }
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
        if result.is_ok() && operation == "restore" {
            let timestep = service.rollouts[rollout_id].state.timestep;
            if let Some(frames) = service.frames.get_mut(rollout_id) {
                frames.retain(|step, _| *step <= timestep);
            }
            if service
                .capture_frames
                .get(rollout_id)
                .copied()
                .unwrap_or(false)
            {
                if let Err(error) = service.store_frame(rollout_id) {
                    response(stream, 400, json!({"error":error}));
                    return;
                }
            }
        }
        if result.is_ok()
            && operation == "step"
            && service
                .capture_frames
                .get(rollout_id)
                .copied()
                .unwrap_or(false)
        {
            if let Err(error) = service.store_frame(rollout_id) {
                response(stream, 400, json!({"error":error}));
                return;
            }
        }
        match result {
            Ok(payload) => response(stream, 200, payload),
            Err(error) => response(stream, 400, json!({"error":error})),
        }
        return;
    }

    let result: Result<Value, String> = match (method, path) {
        ("GET", "/health") => Ok(json!({"ok":true,"env_family":"craftax-multiplayer","runtime":"rust","sessions":service.rollouts.len()})),
        ("GET", "/info") => Ok(json!({"env_family":"craftax-multiplayer","runtime":"rust","capabilities":["rollout","checkpoint","nev_log","symbolic_readout","render_png","frame_manifest","frame_png","replay_gif"]})),
        ("GET", "/agents") => Ok(json!(Service::agent_ids(&service.env))),
        ("POST", "/run_scenario") => Service::run_scenario(&body),
        ("POST", "/rollouts") => Service::new_env(&body).and_then(|env| {
            let (capture, render_mode) = Service::visual_configuration(&body)?;
            let rollout_id = format!("rollout-{}", service.next_rollout);
            service.next_rollout += 1;
            let observations = env.observations(5);
            let seed = env.state.seed;
            let readout = Service::readout(&env);
            service.rollouts.insert(rollout_id.clone(), env);
            service.frames.insert(rollout_id.clone(), BTreeMap::new());
            service.capture_frames.insert(rollout_id.clone(), capture);
            service.render_modes.insert(rollout_id.clone(), render_mode);
            if capture { service.store_frame(&rollout_id)?; }
            Ok(json!({"rollout_id":rollout_id,"observations":observations,"info":{"seed":seed},"readout":readout,"visual":{"render_url":format!("/rollouts/{rollout_id}/render.png"),"frame_manifest_url":format!("/rollouts/{rollout_id}/frames/manifest"),"replay_gif_url":format!("/rollouts/{rollout_id}/replay.gif")}}))
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
