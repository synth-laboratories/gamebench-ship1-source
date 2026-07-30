use frogs_gold::{resolve_task, FrogsSession};
use serde_json::{json, Value};
use std::{env, time::Instant};

fn main() {
    let mut iterations = 300usize;
    let args: Vec<String> = env::args().collect();
    let mut i = 1;
    while i < args.len() {
        if args[i] == "--iterations" && i + 1 < args.len() {
            iterations = args[i + 1].parse().unwrap();
            i += 2;
        } else {
            i += 1;
        }
    }
    let task: Value = json!({
        "schema": "gamebench.task.frogs.v1",
        "task_id": "bench",
        "seed": 1,
        "board": [
            ["blue", "red", "green", "yellow"],
            ["green", "yellow", "red", "blue"],
            ["green", "blue", "yellow", "red"],
            ["red", "green", "yellow", "blue"]
        ],
        "rules": {"base": "classic_frogs", "overrides": {"max_steps": 16}}
    });
    let mut session = FrogsSession::default();
    session.reset(resolve_task(&task, None));
    session.step_value(json!({"kind": "place_frog", "row": 0, "col": 1}));
    session.step_value(json!({"kind": "place_frog", "row": 1, "col": 3}));
    session.step_value(json!({"kind": "place_frog", "row": 2, "col": 0}));
    let mut save_ms = Vec::new();
    let mut restore_ms = Vec::new();
    let mut bytes = Vec::new();
    for _ in 0..iterations {
        let start = Instant::now();
        let blob = session.checkpoint_bytes();
        save_ms.push(start.elapsed().as_secs_f64() * 1000.0);
        let mut clone = FrogsSession::default();
        let start = Instant::now();
        clone.restore_checkpoint(&blob);
        restore_ms.push(start.elapsed().as_secs_f64() * 1000.0);
        bytes.push(blob.len() as f64);
    }
    println!(
        "{}",
        serde_json::to_string(&json!({
            "iterations": iterations,
            "bytes_mean": mean(&bytes),
            "save_p50_ms": percentile(&save_ms, 50.0),
            "save_p99_ms": percentile(&save_ms, 99.0),
            "restore_p50_ms": percentile(&restore_ms, 50.0),
            "restore_p99_ms": percentile(&restore_ms, 99.0)
        }))
        .unwrap()
    );
}

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

fn percentile(values: &[f64], pct: f64) -> f64 {
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let index = ((pct / 100.0) * (sorted.len().saturating_sub(1)) as f64).round() as usize;
    sorted[index.min(sorted.len() - 1)]
}
