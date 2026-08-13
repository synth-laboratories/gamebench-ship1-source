use nethack_dlvl1_gold::{
    run_scenario_entry, run_scenario_trace_entry, run_source_state_replay_entry, NethackSession,
};
use serde_json::{json, Value};
use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .expect("read scenario JSON");
    let args = std::env::args().collect::<Vec<_>>();
    let result = if args.iter().any(|argument| argument == "--checkpoint-stdin") {
        restore_projection(&input, &[])
    } else if args
        .iter()
        .any(|argument| argument == "--checkpoint-replay-stdin")
    {
        let request: Value = serde_json::from_str(&input).expect("parse checkpoint replay request");
        let checkpoint = request
            .get("checkpoint")
            .and_then(Value::as_str)
            .expect("checkpoint string");
        let actions = request
            .get("actions")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        restore_projection(checkpoint, &actions)
    } else if args.iter().any(|argument| argument == "--trace-stdin") {
        let entry: Value = serde_json::from_str(&input).expect("parse trace scenario JSON");
        run_scenario_trace_entry(&entry).expect("run own Rust scenario trace")
    } else if args
        .iter()
        .any(|argument| argument == "--source-state-replay-stdin")
    {
        let entry: Value = serde_json::from_str(&input).expect("parse source-state replay JSON");
        run_source_state_replay_entry(&entry).expect("run own Rust source-state replay")
    } else {
        let entry: Value = serde_json::from_str(&input).expect("parse scenario JSON");
        run_scenario_entry(&entry).expect("run own Rust scenario")
    };
    println!(
        "{}",
        serde_json::to_string(&result).expect("serialize scenario projection")
    );
}

fn restore_projection(checkpoint: &str, actions: &[Value]) -> Value {
    let payload: Value = serde_json::from_str(checkpoint).expect("parse checkpoint JSON");
    let resolved = payload
        .get("resolved")
        .cloned()
        .expect("checkpoint resolved");
    let mut session = NethackSession::reset(resolved).expect("reset before restore");
    session
        .restore_checkpoint(checkpoint.as_bytes())
        .expect("restore checkpoint");
    for action in actions {
        if session.state.terminated || session.state.truncated {
            break;
        }
        session.step(action.clone());
    }
    json!({"projection": session.readout(), "checkpoint": String::from_utf8(session.checkpoint_bytes()).expect("utf8 checkpoint")})
}
