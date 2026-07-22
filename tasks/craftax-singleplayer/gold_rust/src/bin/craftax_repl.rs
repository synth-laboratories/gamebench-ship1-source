//! Newline-delimited JSON REPL for low-latency Craftax rollouts from Python workers.
//!
//! One engine session per process; no HTTP or cross-rollout locking.

use craftax_gamebench_gold::CraftaxRustSession;
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

enum ReadoutMode {
    Full,
    Policy,
}

struct ReplState {
    session: Option<CraftaxRustSession>,
}

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    let mut state = ReplState { session: None };
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(value) => value,
            Err(error) => {
                write_error(&mut stdout, Value::Null, error.to_string());
                continue;
            }
        };
        if line.trim().is_empty() {
            continue;
        }
        let request = match serde_json::from_str::<Value>(&line) {
            Ok(value) => value,
            Err(error) => {
                write_error(&mut stdout, Value::Null, error.to_string());
                continue;
            }
        };
        let request_id = request.get("id").cloned().unwrap_or(Value::Null);
        let response = handle_request(&mut state, &request);
        write_response(&mut stdout, request_id, response);
    }
}

fn handle_request(state: &mut ReplState, request: &Value) -> Value {
    let op = request
        .get("op")
        .and_then(Value::as_str)
        .unwrap_or_default();
    match op {
        "ping" => json!({"ok": true, "lane": "rust_repl"}),
        "close" => {
            state.session = None;
            json!({"ok": true})
        }
        "reset" => {
            let task = request.get("task").cloned().unwrap_or_else(|| json!({}));
            let seed = request.get("seed").and_then(Value::as_i64);
            let readout_mode = match parse_readout_mode(request) {
                Ok(mode) => mode,
                Err(error) => return json!({"ok": false, "error": error}),
            };
            match CraftaxRustSession::reset_from_task(&task, seed) {
                Ok(session) => {
                    state.session = Some(session);
                    session_payload(
                        state.session.as_ref().expect("session inserted"),
                        readout_mode,
                    )
                }
                Err(error) => json!({"ok": false, "error": error.to_string()}),
            }
        }
        "step" => {
            let Some(session) = state.session.as_mut() else {
                return json!({"ok": false, "error": "no active session; call reset first"});
            };
            let readout_mode = match parse_readout_mode(request) {
                Ok(mode) => mode,
                Err(error) => return json!({"ok": false, "error": error}),
            };
            let action = request
                .get("action")
                .cloned()
                .unwrap_or_else(|| json!("noop"));
            if !session.is_done() {
                if let Err(error) = session.step(&action) {
                    return json!({"ok": false, "error": error.to_string()});
                }
            }
            session_payload(session, readout_mode)
        }
        "steps" => {
            let Some(session) = state.session.as_mut() else {
                return json!({"ok": false, "error": "no active session; call reset first"});
            };
            let readout_mode = match parse_readout_mode(request) {
                Ok(mode) => mode,
                Err(error) => return json!({"ok": false, "error": error}),
            };
            let Some(actions) = request.get("actions").and_then(Value::as_array) else {
                return json!({"ok": false, "error": "steps requires actions array"});
            };
            let mut steps_executed = 0usize;
            for action in actions {
                if session.is_done() {
                    break;
                }
                if let Err(error) = session.step(action) {
                    return json!({"ok": false, "error": error.to_string()});
                }
                steps_executed += 1;
            }
            let mut payload = session_payload(session, readout_mode);
            if let Some(object) = payload.as_object_mut() {
                object.insert("steps_executed".to_string(), json!(steps_executed));
            }
            payload
        }
        "readout" => {
            let Some(session) = state.session.as_ref() else {
                return json!({"ok": false, "error": "no active session; call reset first"});
            };
            let readout_mode = match parse_readout_mode(request) {
                Ok(mode) => mode,
                Err(error) => return json!({"ok": false, "error": error}),
            };
            session_payload(session, readout_mode)
        }
        other => json!({"ok": false, "error": format!("unknown op: {other}")}),
    }
}

fn parse_readout_mode(request: &Value) -> Result<ReadoutMode, String> {
    match request
        .get("readout_mode")
        .and_then(Value::as_str)
        .unwrap_or("full")
    {
        "full" => Ok(ReadoutMode::Full),
        "policy" => Ok(ReadoutMode::Policy),
        other => Err(format!("unsupported readout_mode: {other}")),
    }
}

fn session_payload(session: &CraftaxRustSession, readout_mode: ReadoutMode) -> Value {
    let readout = match readout_mode {
        ReadoutMode::Full => session.readout(),
        ReadoutMode::Policy => session.policy_readout(),
    };
    json!({
        "ok": true,
        "readout": readout,
        "terminated": session.private.get("terminated").and_then(Value::as_bool).unwrap_or(false),
        "truncated": session.private.get("truncated").and_then(Value::as_bool).unwrap_or(false),
        "reward": session.private.get("total_reward").cloned().unwrap_or(json!(0.0)),
    })
}

fn write_error(stdout: &mut io::Stdout, request_id: Value, message: String) {
    write_response(stdout, request_id, json!({"ok": false, "error": message}));
}

fn write_response(stdout: &mut io::Stdout, request_id: Value, mut response: Value) {
    if let Some(object) = response.as_object_mut() {
        object.insert("id".to_string(), request_id);
    }
    let encoded = serde_json::to_string(&response).unwrap_or_else(|error| {
        json!({"ok": false, "error": format!("encode response failed: {error}")}).to_string()
    });
    let _ = writeln!(stdout, "{encoded}");
    let _ = stdout.flush();
}
