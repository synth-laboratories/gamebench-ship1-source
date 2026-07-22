//! JSONL REPL for the authoritative shared-world Craftax MARL session.

use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use craftax_gamebench_gold::render::encode_png_rgb;
use craftax_gamebench_gold::multi::CraftaxMultiSession;
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

struct State { session: Option<CraftaxMultiSession>, request_id: u64 }

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    let mut state = State { session: None, request_id: 0 };
    for line in stdin.lock().lines() {
        let Ok(line) = line else { continue; };
        if line.trim().is_empty() { continue; }
        let request: Value = match serde_json::from_str(&line) { Ok(value) => value, Err(error) => { write(&mut stdout, Value::Null, json!({"ok": false, "error": error.to_string()})); continue; } };
        let id = request.get("id").cloned().unwrap_or(Value::Null);
        write(&mut stdout, id, handle(&mut state, &request));
    }
}

fn handle(state: &mut State, request: &Value) -> Value {
    state.request_id += 1;
    match request.get("op").and_then(Value::as_str).unwrap_or_default() {
        "ping" => json!({"ok": true, "lane": "craftax_multi_rust_repl"}),
        "close" => { state.session = None; json!({"ok": true}) }
        "reset" => match CraftaxMultiSession::reset_from_task(&request.get("task").cloned().unwrap_or_else(|| json!({})), request.get("seed").and_then(Value::as_i64), request.get("agent_count").and_then(Value::as_u64).unwrap_or(1) as usize) {
            Ok(mut session) => { let active = "agent_1"; let readout = session.readout(active).expect("fresh multi readout"); state.session = Some(session); json!({"ok": true, "active_agent": active, "readout": readout}) }
            Err(error) => json!({"ok": false, "error": error.to_string()}),
        },
        "readout" => with_session(state, request, |session, agent| session.readout(agent).map(|readout| json!({"ok": true, "active_agent": agent, "readout": readout}))),
        "step" => with_session(state, request, |session, agent| { session.step(agent, &request.get("action").cloned().unwrap_or_else(|| json!("noop")))?; let readout = session.readout(agent)?; Ok(json!({"ok": true, "active_agent": agent, "readout": readout, "terminated": session.is_done()})) }),
        "render_png" => with_session(state, request, |session, agent| { let frame = session.render_png(agent)?; let png = encode_png_rgb(frame.0, frame.1, &frame.2); Ok(json!({"ok": true, "png_base64": BASE64.encode(png), "width": frame.0, "height": frame.1})) }),
        other => json!({"ok": false, "error": format!("unknown op: {other}")}),
    }
}

fn with_session<F>(state: &mut State, request: &Value, operation: F) -> Value where F: FnOnce(&mut CraftaxMultiSession, &str) -> anyhow::Result<Value> {
    let Some(session) = state.session.as_mut() else { return json!({"ok": false, "error": "no active session; call reset first"}); };
    let agent = request.get("agent_id").and_then(Value::as_str).unwrap_or("agent_1");
    match operation(session, agent) { Ok(value) => value, Err(error) => json!({"ok": false, "error": error.to_string()}), }
}

fn write(stdout: &mut io::Stdout, id: Value, mut response: Value) {
    if let Some(object) = response.as_object_mut() { object.insert("id".to_string(), id); }
    let _ = writeln!(stdout, "{}", serde_json::to_string(&response).unwrap());
    let _ = stdout.flush();
}
