use serde_json::Value;
use std::env;
use std::fs;
use std::io::{self, Read};
use towermind_singleplayer_gold::{canonical_json, run_scenario, TowerMindEnv};

fn main() {
    let args: Vec<String> = env::args().collect();
    let output = if args.get(1).map(String::as_str) == Some("--checkpoint-stdin") {
        let mut input = String::new();
        io::stdin().read_to_string(&mut input).expect("read checkpoint");
        let env = TowerMindEnv::restore(&input).expect("restore checkpoint");
        serde_json::json!({"projection": env.projection(), "checkpoint": env.checkpoint()})
    } else if args.get(1).map(String::as_str) == Some("--checkpoint-replay-stdin") {
        let mut input = String::new();
        io::stdin().read_to_string(&mut input).expect("read replay request");
        let request: Value = serde_json::from_str(&input).expect("parse replay request");
        let mut env = TowerMindEnv::restore(request.get("checkpoint").and_then(Value::as_str).expect("checkpoint string")).expect("restore checkpoint");
        for action in request.get("actions").and_then(Value::as_array).cloned().unwrap_or_default() {
            if env.projection().get("state").and_then(|state| state.get("terminated")).and_then(Value::as_bool) == Some(true) {
                break;
            }
            env.step(action);
        }
        serde_json::json!({"projection": env.projection(), "checkpoint": env.checkpoint()})
    } else {
        let path = args.get(1).expect("usage: towermind_replay <scenario.json> | --checkpoint-stdin | --checkpoint-replay-stdin");
        let document: Value = serde_json::from_str(&fs::read_to_string(path).expect("read scenario")).expect("parse scenario");
        run_scenario(document).expect("run scenario")
    };
    println!("{}", canonical_json(&output));
}
