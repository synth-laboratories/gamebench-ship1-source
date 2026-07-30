use crafter_gamebench_gold::{CrafterRustSession, ACHIEVEMENTS};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use std::thread;
use std::time::Instant;

const ACTION_PATTERN: [&str; 6] = [
    "move_right",
    "do",
    "move_down",
    "do",
    "move_left",
    "move_up",
];
const CHECKPOINT_BUDGET_BYTES: f64 = 64.0 * 1024.0;
#[derive(Clone)]
struct EpisodeOutcome {
    seed: u64,
    steps: u64,
    reward: f32,
    achievements: BTreeSet<String>,
    event_kind_counts: BTreeMap<String, u64>,
    done_reason: Option<String>,
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--throughput") {
        println!(
            "{}",
            serde_json::to_string_pretty(&throughput_report(&args)).unwrap()
        );
        return;
    }
    let steps: usize = args
        .first()
        .and_then(|value| value.parse().ok())
        .unwrap_or(300);
    println!(
        "{}",
        serde_json::to_string_pretty(&checkpoint_report(steps)).unwrap()
    );
}

fn checkpoint_report(iterations: usize) -> serde_json::Value {
    let bench_steps = iterations;
    let entry = json!({
        "scenario_id": "bench_policy_dev",
        "world": {"use_default": "policy_dev_small", "seed": 101},
        "rules": {"base": "no_homeostasis"},
        "actions": []
    });
    let mut session = CrafterRustSession::reset_from_entry(&entry);
    let started = Instant::now();
    for idx in 0..bench_steps {
        let action = match idx % 6 {
            0 => "move_right",
            1 => "do",
            2 => "move_down",
            3 => "do",
            4 => "move_left",
            _ => "move_up",
        };
        session.step(action);
        if session.truncated || session.terminated {
            break;
        }
    }
    let step_elapsed = started.elapsed().as_secs_f64();
    let mut save_ms = Vec::with_capacity(iterations);
    let mut restore_ms = Vec::with_capacity(iterations);
    let mut sizes = Vec::with_capacity(iterations);
    for _ in 0..iterations {
        let start = Instant::now();
        let bytes = session.checkpoint_bytes();
        save_ms.push(start.elapsed().as_secs_f64() * 1000.0);
        sizes.push(bytes.len() as f64);
        let start = Instant::now();
        session.restore_checkpoint_bytes(&bytes);
        restore_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    json!({
        "schema": "gamebench.crafter.rust_bench.v1",
        "lane": "rust",
        "mode": "checkpoint",
        "build_profile": "release",
        "iterations": iterations,
        "steps": bench_steps,
        "step_elapsed_s": step_elapsed,
        "steps_per_s": if step_elapsed > 0.0 { bench_steps as f64 / step_elapsed } else { 0.0 },
        "checkpoint_budget_bytes": CHECKPOINT_BUDGET_BYTES as usize,
        "checkpoint_budget_pass": percentile(&mut sizes.clone(), 0.99) <= CHECKPOINT_BUDGET_BYTES,
        "checkpoint_bytes_p50": percentile(&mut sizes.clone(), 0.50),
        "checkpoint_bytes_p99": percentile(&mut sizes.clone(), 0.99),
        "checkpoint_save_p50_ms": percentile(&mut save_ms.clone(), 0.50),
        "checkpoint_save_p99_ms": percentile(&mut save_ms.clone(), 0.99),
        "checkpoint_restore_p50_ms": percentile(&mut restore_ms.clone(), 0.50),
        "checkpoint_restore_p99_ms": percentile(&mut restore_ms.clone(), 0.99),
        "last_blob_bytes": sizes.last().copied().unwrap_or(0.0) as usize
    })
}

fn throughput_report(args: &[String]) -> serde_json::Value {
    let episodes = parse_flag(args, "--episodes", 20);
    let max_steps = parse_flag(args, "--max-steps", 120);
    let workers = parse_flag(args, "--workers", 4).max(1).min(episodes.max(1));
    let started = Instant::now();
    let mut handles = vec![];
    let chunk = episodes.div_ceil(workers);
    for worker in 0..workers {
        let start_idx = worker * chunk;
        let end_idx = ((worker + 1) * chunk).min(episodes);
        if start_idx >= end_idx {
            continue;
        }
        handles.push(thread::spawn(move || {
            let mut outcomes = vec![];
            for idx in start_idx..end_idx {
                outcomes.push(run_episode(101 + idx as u64, max_steps as u64));
            }
            outcomes
        }));
    }
    let mut outcomes = vec![];
    for handle in handles {
        outcomes.extend(handle.join().unwrap());
    }
    outcomes.sort_by_key(|outcome| outcome.seed);
    let elapsed = started.elapsed().as_secs_f64();
    let total_steps: u64 = outcomes.iter().map(|outcome| outcome.steps).sum();
    let reward_sum: f64 = outcomes.iter().map(|outcome| outcome.reward as f64).sum();
    let mut achievement_frequency: BTreeMap<String, u64> = ACHIEVEMENTS
        .iter()
        .map(|name| ((*name).to_string(), 0))
        .collect();
    let mut event_kind_counts: BTreeMap<String, u64> = BTreeMap::new();
    for outcome in &outcomes {
        for achievement in &outcome.achievements {
            if let Some(count) = achievement_frequency.get_mut(achievement) {
                *count += 1;
            }
        }
        for (kind, count) in &outcome.event_kind_counts {
            *event_kind_counts.entry(kind.clone()).or_insert(0) += count;
        }
    }
    json!({
        "schema": "gamebench.crafter.rollout_throughput.v1",
        "lane": "rust",
        "engine_mode": "rust_release_in_process",
        "build_profile": "release",
        "episode_count": outcomes.len(),
        "workers": workers,
        "max_steps": max_steps,
        "total_steps": total_steps,
        "elapsed_s": elapsed,
        "steps_per_s": if elapsed > 0.0 { total_steps as f64 / elapsed } else { 0.0 },
        "episodes_per_s": if elapsed > 0.0 { outcomes.len() as f64 / elapsed } else { 0.0 },
        "mean_reward": if outcomes.is_empty() { 0.0 } else { reward_sum / outcomes.len() as f64 },
        "achievement_frequency": achievement_frequency,
        "achievement_score": achievement_score(&achievement_frequency, outcomes.len()),
        "event_kind_counts": event_kind_counts,
        "sample_episodes": outcomes.iter().take(5).map(|outcome| json!({
            "seed": outcome.seed,
            "steps": outcome.steps,
            "reward": outcome.reward,
            "achievements": outcome.achievements,
            "done_reason": outcome.done_reason
        })).collect::<Vec<_>>()
    })
}

fn run_episode(seed: u64, max_steps: u64) -> EpisodeOutcome {
    let task = json!({
        "schema": "gamebench.task.crafter.v1",
        "task_id": format!("throughput_policy_dev_{}", seed),
        "scenario_id": format!("throughput_policy_dev_{}", seed),
        "world": {"use_default": "policy_dev_small", "seed": seed, "max_steps": max_steps},
        "rules": {"base": "no_homeostasis"},
        "readouts": {"symbolic": "symbolic_compact", "visual": false}
    });
    let mut session = CrafterRustSession::reset_from_task(&task);
    let mut cursor = 0;
    while !session.terminated && !session.truncated && session.step_index() < max_steps {
        session.step(ACTION_PATTERN[cursor % ACTION_PATTERN.len()]);
        cursor += 1;
    }
    let mut achievements = BTreeSet::new();
    let mut event_kind_counts: BTreeMap<String, u64> = BTreeMap::new();
    for event in &session.events {
        *event_kind_counts.entry(event.kind.clone()).or_insert(0) += 1;
        if event.kind == "achievement_unlocked" {
            if let Some(name) = event
                .payload
                .get("achievement")
                .and_then(serde_json::Value::as_str)
            {
                achievements.insert(name.to_string());
            }
        }
    }
    EpisodeOutcome {
        seed,
        steps: session.step_index(),
        reward: session.total_reward,
        achievements,
        event_kind_counts,
        done_reason: session.done_reason,
    }
}

fn parse_flag(args: &[String], name: &str, default: usize) -> usize {
    args.iter()
        .position(|arg| arg == name)
        .and_then(|index| args.get(index + 1))
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn percentile(values: &mut [f64], quantile: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.sort_by(|left, right| left.partial_cmp(right).unwrap());
    let idx = ((values.len() - 1) as f64 * quantile).round() as usize;
    values[idx.min(values.len() - 1)]
}

fn achievement_score(frequency: &BTreeMap<String, u64>, episode_count: usize) -> f64 {
    if episode_count == 0 {
        return 0.0;
    }
    let total = ACHIEVEMENTS
        .iter()
        .map(|name| {
            let raw = *frequency.get(*name).unwrap_or(&0) as f64;
            let rate = (raw / episode_count as f64).clamp(0.0, 1.0);
            (1.0 + rate).ln()
        })
        .sum::<f64>();
    (total / ACHIEVEMENTS.len() as f64).exp() - 1.0
}
