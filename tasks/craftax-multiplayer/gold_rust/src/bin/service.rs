use craftax_coop_gamebench::CraftaxCoopEnv;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

fn response(stream: &mut TcpStream, status: u16, payload: Value) {
    let body = serde_json::to_string(&payload).unwrap();
    let label = if status == 200 {
        "OK"
    } else if status == 404 {
        "Not Found"
    } else {
        "Bad Request"
    };
    let raw=format!("HTTP/1.1 {status} {label}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",body.len());
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

fn handle(stream: &mut TcpStream, env: &mut CraftaxCoopEnv) {
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
    let result: Result<Value, String> = match (method, path) {
        ("GET", "/health") => {
            Ok(json!({"ok":true,"env_family":"craftax-multiplayer","runtime":"rust"}))
        }
        ("GET", "/agents") => Ok(json!(env
            .state
            .players
            .iter()
            .map(|p| p.agent_id.clone())
            .collect::<Vec<_>>())),
        ("POST", "/reset") => {
            let seed = match body.get("seed") {
                None => 0,
                Some(value) => match value.as_u64() {
                    Some(seed) => seed,
                    None => {
                        response(
                            stream,
                            400,
                            json!({"error":"seed must be an unsigned integer"}),
                        );
                        return;
                    }
                },
            };
            *env = CraftaxCoopEnv::reset(seed, 3, 100_000);
            Ok(json!({"observations":env.observations(5),"info":{"seed":seed}}))
        }
        ("POST", "/step") => {
            let joint = body
                .get("joint_action")
                .and_then(Value::as_object)
                .ok_or_else(|| "joint_action required".to_string())
                .and_then(|map| {
                    map.iter()
                        .map(|(agent, value)| {
                            let action = value
                                .as_str()
                                .or_else(|| value.get("kind").and_then(Value::as_str))
                                .ok_or_else(|| format!("invalid action for {agent}"))?;
                            Ok((agent.clone(), action.to_string()))
                        })
                        .collect::<Result<BTreeMap<_, _>, String>>()
                });
            match joint.and_then(|actions| env.step(&actions)) {
                Ok(step) => Ok(
                    json!({"observations":env.observations(5),"rewards":step.rewards,"dones":step.dones,"info":{"events":step.events,"termination_reason":env.state.termination_reason}}),
                ),
                Err(error) => Err(error),
            }
        }
        ("GET", "/checkpoint") => {
            serde_json::from_str(&env.checkpoint_json()).map_err(|e| e.to_string())
        }
        ("POST", "/restore") => match CraftaxCoopEnv::restore_json(&body.to_string()) {
            Ok(restored) => {
                *env = restored;
                Ok(json!({"observations":env.observations(5)}))
            }
            Err(error) => Err(error.to_string()),
        },
        ("GET", "/nev") => Ok(json!({"structured":env.state.nev,"legacy":env.state.legacy_nev})),
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
    let address = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "127.0.0.1:8081".into());
    let listener = TcpListener::bind(&address).unwrap_or_else(|e| panic!("bind {address}: {e}"));
    let mut env = CraftaxCoopEnv::reset(0, 3, 100_000);
    for connection in listener.incoming() {
        if let Ok(mut stream) = connection {
            handle(&mut stream, &mut env)
        }
    }
}
