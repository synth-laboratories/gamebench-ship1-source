use rogue_gold::{resolve_task, RogueSession};
use serde_json::json;
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
    let task = json!({
        "task_id": "bench",
        "seed": 1,
        "grid": ["                    ","  ------------      ","  |@...*....%|      ","  |....:.....|      ","  ------------      ","                    "],
        "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 40}},
        "objective": "descend"
    });
    let mut session = RogueSession::default();
    session.reset(resolve_task(&task, None));
    for action in ["l", "l", "l", "l"] {
        session.step(action);
    }
    let mut save_ms = Vec::new();
    let mut restore_ms = Vec::new();
    let mut bytes = Vec::new();
    for _ in 0..iterations {
        let start = Instant::now();
        let blob = session.checkpoint_bytes();
        save_ms.push(start.elapsed().as_secs_f64() * 1000.0);
        let mut clone = RogueSession::default();
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
    sorted[((pct / 100.0) * (sorted.len().saturating_sub(1)) as f64).round() as usize]
}
