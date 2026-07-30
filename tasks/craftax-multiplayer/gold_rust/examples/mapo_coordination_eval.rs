use craftax_coop_gamebench::{CraftaxCoopEnv, Player};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize, Serialize)]
struct DatasetConfig {
    schema: String,
    dataset_id: String,
    agent_count: usize,
    max_timesteps: u64,
    probes: Vec<String>,
    splits: BTreeMap<String, SeedRange>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct SeedRange {
    start: u64,
    count: u64,
}

#[derive(Debug, Deserialize)]
struct CandidateFile {
    schema: String,
    candidates: Vec<Candidate>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct Candidate {
    id: String,
    executor_profile: String,
    shared_prompt: String,
    role_prompts: BTreeMap<String, String>,
    protocol: Value,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum ProbeKind {
    IronHandoff,
    FoodRescue,
    MinerCraftPipeline,
    ExpiringRequestRepair,
}

impl ProbeKind {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "iron_handoff" => Ok(Self::IronHandoff),
            "food_rescue" => Ok(Self::FoodRescue),
            "miner_craft_pipeline" => Ok(Self::MinerCraftPipeline),
            "expiring_request_repair" => Ok(Self::ExpiringRequestRepair),
            other => Err(format!("unsupported coordination probe {other:?}")),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::IronHandoff => "iron_handoff",
            Self::FoodRescue => "food_rescue",
            Self::MinerCraftPipeline => "miner_craft_pipeline",
            Self::ExpiringRequestRepair => "expiring_request_repair",
        }
    }

    fn expected_trades(self) -> u64 {
        match self {
            Self::MinerCraftPipeline => 2,
            _ => 1,
        }
    }
}

#[derive(Clone)]
struct ProbeContext {
    kind: ProbeKind,
    checkpoint: String,
    checkpoint_digest: String,
    expected_resource: &'static str,
    giver: &'static str,
    recipient: &'static str,
}

#[derive(Clone, Debug, Serialize)]
struct StepTrace {
    index: usize,
    joint_action: BTreeMap<String, String>,
    rewards: BTreeMap<String, f64>,
    event_kinds: Vec<String>,
    trade_count: u64,
    requests: BTreeMap<String, Value>,
    inventories: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Serialize)]
struct EpisodeEvidence {
    split: String,
    seed: u64,
    probe: ProbeKind,
    checkpoint_digest: String,
    candidate_id: String,
    outcome_success: bool,
    coordination_success: bool,
    role_assignment_consistent: bool,
    request_action_aligned: bool,
    grounded_signal_count: usize,
    redundant_signal_count: usize,
    give_attempt_count: usize,
    successful_trade_count: u64,
    qualitative_score: f64,
    qualitative_rubric: Value,
    trace_retained: bool,
    trace: Vec<StepTrace>,
    final_state_digest: String,
}

#[derive(Default)]
struct Aggregate {
    count: usize,
    outcomes: usize,
    coordinated: usize,
    role_consistent: usize,
    aligned: usize,
    signals: usize,
    redundant: usize,
    give_attempts: usize,
    trades: u64,
    qualitative_sum: f64,
}

fn main() -> Result<(), String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let task_dir = manifest_dir
        .parent()
        .ok_or_else(|| "gold_rust must have a task parent".to_string())?;
    let args = parse_args(
        task_dir.join("defaults/mapo_coordination/dataset_v1.json"),
        task_dir.join("defaults/mapo_coordination/candidates_v1.json"),
        task_dir.join("reports/mapo_coordination_rust_eval.json"),
    )?;
    let dataset: DatasetConfig = read_json(&args.dataset)?;
    let candidates: CandidateFile = read_json(&args.candidates)?;
    validate_config(&dataset, &candidates)?;
    let probes = dataset
        .probes
        .iter()
        .map(|value| ProbeKind::parse(value))
        .collect::<Result<Vec<_>, _>>()?;

    let mut evidence = Vec::new();
    let mut scenario_count_by_split = BTreeMap::new();
    let mut probe_count_by_split = BTreeMap::new();
    for (split, range) in &dataset.splits {
        scenario_count_by_split.insert(split.clone(), range.count as usize);
        probe_count_by_split.insert(split.clone(), range.count as usize * probes.len());
        for seed in range.start..range.start + range.count {
            for probe in &probes {
                let context = prepare_probe(seed, dataset.max_timesteps, *probe)?;
                for candidate in &candidates.candidates {
                    evidence.push(run_probe(
                        split,
                        seed,
                        seed == range.start,
                        candidate,
                        &context,
                    )?);
                }
            }
        }
    }

    let report = json!({
        "schema": "gamebench.mapo_coordination_eval.v1",
        "status": "completed",
        "lane": "rust",
        "env_family": "craftax-multiplayer",
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "dataset_schema": dataset.schema,
            "dataset_path": stable_path(&args.dataset, task_dir),
            "dataset_digest": digest_text(&serde_json::to_string(&dataset).map_err(string_error)?),
            "scenario_count": scenario_count_by_split.values().sum::<usize>(),
            "scenario_count_by_split": scenario_count_by_split,
            "probe_count": probe_count_by_split.values().sum::<usize>(),
            "probe_count_by_split": probe_count_by_split,
            "candidate_continuation_count": evidence.len(),
            "diversity_contract": {
                "real_seeded_world_generation": true,
                "disjoint_seed_ranges": true,
                "probes": dataset.probes,
            }
        },
        "candidates": {
            "schema": candidates.schema,
            "path": stable_path(&args.candidates, task_dir),
            "digest": digest_text(&serde_json::to_string(&candidates.candidates).map_err(string_error)?),
            "executor": "craftax_coop_rust_reference_protocol_executor.v1",
            "executor_scope": "Typed reference behaviors make supplied prompt protocols concrete; arbitrary natural-language execution requires the model-backed policy adapter.",
            "definitions": candidates.candidates,
        },
        "qualitative_evaluation": {
            "evaluator": "deterministic_trace_rubric.v1",
            "blinded_external_judge_run": false,
            "rubric_fields": [
                "need_identification",
                "role_clarity",
                "request_action_grounding",
                "timing",
                "action_consistency",
                "signal_efficiency"
            ],
            "trace_contract": "All continuations retain compact episode receipts. One deterministic seed per split, candidate, and probe retains grounded request/give actions, request dashboard state, relevant inventory, trades, rewards, and event kinds for separate blinded review.",
            "qualitative_sample_count": evidence.iter().filter(|episode| episode.trace_retained).count()
        },
        "summary": aggregate_evidence(&evidence),
        "episode_receipts": evidence.iter().map(episode_receipt).collect::<Vec<_>>(),
        "qualitative_samples": evidence.iter().filter(|episode| episode.trace_retained).collect::<Vec<_>>(),
    });

    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent).map_err(|err| format!("create {}: {err}", parent.display()))?;
    }
    fs::write(
        &args.output,
        serde_json::to_vec_pretty(&report).map_err(string_error)?,
    )
    .map_err(|err| format!("write {}: {err}", args.output.display()))?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "status": report["status"],
            "output": args.output,
            "scenario_count": report["dataset"]["scenario_count"],
            "probe_count": report["dataset"]["probe_count"],
            "candidate_continuation_count": report["dataset"]["candidate_continuation_count"],
            "summary": report["summary"],
        }))
        .map_err(string_error)?
    );
    Ok(())
}

struct Args {
    dataset: PathBuf,
    candidates: PathBuf,
    output: PathBuf,
}

fn parse_args(dataset: PathBuf, candidates: PathBuf, output: PathBuf) -> Result<Args, String> {
    let mut parsed = Args {
        dataset,
        candidates,
        output,
    };
    let mut args = env::args().skip(1);
    while let Some(flag) = args.next() {
        let value = args
            .next()
            .ok_or_else(|| format!("{flag} requires a path"))?;
        match flag.as_str() {
            "--dataset" => parsed.dataset = PathBuf::from(value),
            "--candidates" => parsed.candidates = PathBuf::from(value),
            "--output" => parsed.output = PathBuf::from(value),
            other => return Err(format!("unsupported argument {other:?}")),
        }
    }
    Ok(parsed)
}

fn read_json<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<T, String> {
    let text = fs::read_to_string(path).map_err(|err| format!("read {}: {err}", path.display()))?;
    serde_json::from_str(&text).map_err(|err| format!("parse {}: {err}", path.display()))
}

fn validate_config(dataset: &DatasetConfig, candidates: &CandidateFile) -> Result<(), String> {
    if dataset.schema != "gamebench.mapo_coordination_dataset.v1" {
        return Err(format!("unsupported dataset schema {:?}", dataset.schema));
    }
    if dataset.agent_count != 3 {
        return Err("Craftax coordination evaluator requires exactly three roles".to_string());
    }
    if candidates.schema != "gamebench.mapo_coordination_candidates.v1" {
        return Err(format!(
            "unsupported candidate schema {:?}",
            candidates.schema
        ));
    }
    let allowed = [
        "no_coordination",
        "request_only",
        "silent_action_only",
        "conflicting_signals",
        "event_triggered_compact",
    ];
    let mut ids = BTreeSet::new();
    for candidate in &candidates.candidates {
        if !ids.insert(candidate.id.clone()) {
            return Err(format!("duplicate candidate id {:?}", candidate.id));
        }
        if !allowed.contains(&candidate.executor_profile.as_str()) {
            return Err(format!(
                "candidate {:?} has unsupported executor profile {:?}",
                candidate.id, candidate.executor_profile
            ));
        }
    }
    let mut seen_seeds = BTreeSet::new();
    for range in dataset.splits.values() {
        for seed in range.start..range.start + range.count {
            if !seen_seeds.insert(seed) {
                return Err(format!("seed {seed} appears in multiple splits"));
            }
        }
    }
    Ok(())
}

fn prepare_probe(seed: u64, max_timesteps: u64, kind: ProbeKind) -> Result<ProbeContext, String> {
    let mut env = CraftaxCoopEnv::reset(seed, 3, max_timesteps);
    reset_resources(&mut env);
    let (resource, giver, recipient) = match kind {
        ProbeKind::IronHandoff => {
            inventory_mut(player_mut(&mut env, "agent_0")?, "iron")?.clone_from(&1);
            ("iron", "agent_0", "agent_2")
        }
        ProbeKind::FoodRescue => {
            player_mut(&mut env, "agent_0")?.food = 1;
            player_mut(&mut env, "agent_1")?.food = 9;
            ("food", "agent_1", "agent_0")
        }
        ProbeKind::MinerCraftPipeline => {
            inventory_mut(player_mut(&mut env, "agent_0")?, "iron")?.clone_from(&2);
            player_mut(&mut env, "agent_2")?.pickaxe = 0;
            ("iron", "agent_0", "agent_2")
        }
        ProbeKind::ExpiringRequestRepair => {
            inventory_mut(player_mut(&mut env, "agent_0")?, "iron")?.clone_from(&1);
            let recipient = player_mut(&mut env, "agent_2")?;
            recipient.request_type = Some("iron".to_string());
            recipient.request_duration = 1;
            ("iron", "agent_0", "agent_2")
        }
    };
    let checkpoint = env.checkpoint_json();
    let restored = CraftaxCoopEnv::restore_json(&checkpoint).map_err(string_error)?;
    if restored.state != env.state {
        return Err(format!(
            "checkpoint restore changed {} seed {seed}",
            kind.as_str()
        ));
    }
    Ok(ProbeContext {
        kind,
        checkpoint_digest: digest_text(&checkpoint),
        checkpoint,
        expected_resource: resource,
        giver,
        recipient,
    })
}

fn reset_resources(env: &mut CraftaxCoopEnv) {
    env.state.trade_count = 0;
    env.state.achievements.remove("trade");
    for player in &mut env.state.players {
        player.request_type = None;
        player.request_duration = 0;
        for amount in player.inventory.values_mut() {
            *amount = 0;
        }
    }
}

fn player_mut<'a>(env: &'a mut CraftaxCoopEnv, agent_id: &str) -> Result<&'a mut Player, String> {
    env.state
        .players
        .iter_mut()
        .find(|player| player.agent_id == agent_id)
        .ok_or_else(|| format!("missing player {agent_id}"))
}

fn inventory_mut<'a>(player: &'a mut Player, resource: &str) -> Result<&'a mut u16, String> {
    player
        .inventory
        .get_mut(resource)
        .ok_or_else(|| format!("{} missing resource {resource}", player.agent_id))
}

fn run_probe(
    split: &str,
    seed: u64,
    retain_trace: bool,
    candidate: &Candidate,
    context: &ProbeContext,
) -> Result<EpisodeEvidence, String> {
    let mut env = CraftaxCoopEnv::restore_json(&context.checkpoint).map_err(string_error)?;
    let initial_trade_count = env.state.trade_count;
    let plans = actions_for(candidate, context)?;
    let grounded_signal_count = plans
        .iter()
        .flat_map(BTreeMap::values)
        .filter(|action| action.starts_with("request_"))
        .count();
    let give_attempt_count = plans
        .iter()
        .flat_map(BTreeMap::values)
        .filter(|action| action.starts_with("give_"))
        .count();
    let mut trace = Vec::new();
    let trace_retained = retain_trace;
    for (index, joint_action) in plans.into_iter().enumerate() {
        let result = env.step(&joint_action)?;
        if trace_retained {
            trace.push(StepTrace {
                index,
                joint_action,
                rewards: result.rewards,
                event_kinds: result.events.into_iter().map(|event| event.kind).collect(),
                trade_count: env.state.trade_count,
                requests: request_snapshot(&env),
                inventories: inventory_snapshot(&env, context.expected_resource),
            });
        }
    }
    let successful_trade_count = env.state.trade_count - initial_trade_count;
    let outcome_success = probe_outcome(context, &env, successful_trade_count)?;
    let request_action_aligned = outcome_success
        && grounded_signal_count >= context.kind.expected_trades() as usize
        && give_attempt_count >= context.kind.expected_trades() as usize;
    let role_assignment_consistent = outcome_success && role_consistent(context, &env)?;
    let coordination_success =
        outcome_success && request_action_aligned && role_assignment_consistent;
    let expected_signals = context.kind.expected_trades() as usize;
    let redundant_signal_count = grounded_signal_count.saturating_sub(expected_signals);
    let qualitative_rubric = qualitative_rubric(
        outcome_success,
        coordination_success,
        role_assignment_consistent,
        request_action_aligned,
        grounded_signal_count,
        redundant_signal_count,
    );
    let qualitative_score = qualitative_rubric
        .as_object()
        .ok_or_else(|| "qualitative rubric must be an object".to_string())?
        .values()
        .filter_map(Value::as_f64)
        .sum::<f64>()
        / 6.0;
    Ok(EpisodeEvidence {
        split: split.to_string(),
        seed,
        probe: context.kind,
        checkpoint_digest: context.checkpoint_digest.clone(),
        candidate_id: candidate.id.clone(),
        outcome_success,
        coordination_success,
        role_assignment_consistent,
        request_action_aligned,
        grounded_signal_count,
        redundant_signal_count,
        give_attempt_count,
        successful_trade_count,
        qualitative_score,
        qualitative_rubric,
        trace_retained,
        trace,
        final_state_digest: digest_text(&env.checkpoint_json()),
    })
}

fn actions_for(
    candidate: &Candidate,
    context: &ProbeContext,
) -> Result<Vec<BTreeMap<String, String>>, String> {
    let noop = || joint("noop", "noop", "noop");
    let request = format!("request_{}", context.expected_resource);
    let give = format!(
        "give_{}_to_{}",
        context.expected_resource, context.recipient
    );
    let requester_index = agent_index(context.recipient)?;
    let giver_index = agent_index(context.giver)?;
    let mut request_step = noop();
    request_step.insert(context.recipient.to_string(), request.clone());
    let mut give_step = noop();
    give_step.insert(context.giver.to_string(), give.clone());
    let actions = match candidate.executor_profile.as_str() {
        "no_coordination" => vec![noop(); action_horizon(context.kind)],
        "request_only" => {
            let mut steps = Vec::new();
            for _ in 0..context.kind.expected_trades() {
                steps.push(request_step.clone());
                steps.push(noop());
            }
            if context.kind == ProbeKind::MinerCraftPipeline {
                steps.push(joint("noop", "noop", "make_iron_pickaxe"));
            }
            steps
        }
        "silent_action_only" => {
            let mut steps = Vec::new();
            for _ in 0..context.kind.expected_trades() {
                steps.push(give_step.clone());
                steps.push(noop());
            }
            if context.kind == ProbeKind::MinerCraftPipeline {
                steps.push(joint("noop", "noop", "make_iron_pickaxe"));
            }
            steps
        }
        "conflicting_signals" => {
            let mut steps = Vec::new();
            for _ in 0..context.kind.expected_trades() {
                steps.push(joint("request_food", "request_drink", "request_iron"));
                let mut conflict = joint("request_coal", "request_wood", "request_diamond");
                conflict.insert(context.giver.to_string(), give.clone());
                steps.push(conflict);
            }
            if context.kind == ProbeKind::MinerCraftPipeline {
                steps.push(joint("noop", "noop", "make_iron_pickaxe"));
            }
            steps
        }
        "event_triggered_compact" => {
            let mut steps = Vec::new();
            if context.kind == ProbeKind::ExpiringRequestRepair {
                let mut repair = noop();
                repair.insert(context.recipient.to_string(), request);
                repair.insert(context.giver.to_string(), give);
                steps.push(repair);
            } else {
                for _ in 0..context.kind.expected_trades() {
                    steps.push(request_step.clone());
                    steps.push(give_step.clone());
                }
                if context.kind == ProbeKind::MinerCraftPipeline {
                    steps.push(joint("noop", "noop", "make_iron_pickaxe"));
                }
            }
            steps
        }
        other => return Err(format!("unsupported executor profile {other:?}")),
    };
    if actions.iter().any(|step| step.len() != 3) {
        return Err(format!(
            "candidate {:?} produced an incomplete joint action",
            candidate.id
        ));
    }
    if requester_index == giver_index {
        return Err("probe giver and recipient must differ".to_string());
    }
    Ok(actions)
}

fn action_horizon(kind: ProbeKind) -> usize {
    match kind {
        ProbeKind::MinerCraftPipeline => 5,
        ProbeKind::ExpiringRequestRepair => 1,
        _ => 2,
    }
}

fn joint(agent_0: &str, agent_1: &str, agent_2: &str) -> BTreeMap<String, String> {
    BTreeMap::from([
        ("agent_0".to_string(), agent_0.to_string()),
        ("agent_1".to_string(), agent_1.to_string()),
        ("agent_2".to_string(), agent_2.to_string()),
    ])
}

fn agent_index(agent_id: &str) -> Result<usize, String> {
    agent_id
        .strip_prefix("agent_")
        .ok_or_else(|| format!("invalid agent id {agent_id:?}"))?
        .parse::<usize>()
        .map_err(string_error)
}

fn probe_outcome(
    context: &ProbeContext,
    env: &CraftaxCoopEnv,
    trades: u64,
) -> Result<bool, String> {
    let recipient = player(env, context.recipient)?;
    let objective_reached = match context.kind {
        ProbeKind::FoodRescue => recipient.food >= 2,
        ProbeKind::MinerCraftPipeline => recipient.pickaxe >= 3,
        _ => recipient.inventory[context.expected_resource] >= 1,
    };
    Ok(trades >= context.kind.expected_trades() && objective_reached)
}

fn role_consistent(context: &ProbeContext, env: &CraftaxCoopEnv) -> Result<bool, String> {
    let giver = player(env, context.giver)?;
    let recipient = player(env, context.recipient)?;
    let expected = match context.kind {
        ProbeKind::FoodRescue => giver.role == "forager" && recipient.role == "warrior",
        _ => giver.role == "warrior" && recipient.role == "miner",
    };
    Ok(expected)
}

fn player<'a>(env: &'a CraftaxCoopEnv, agent_id: &str) -> Result<&'a Player, String> {
    env.state
        .players
        .iter()
        .find(|player| player.agent_id == agent_id)
        .ok_or_else(|| format!("missing player {agent_id}"))
}

fn request_snapshot(env: &CraftaxCoopEnv) -> BTreeMap<String, Value> {
    env.state
        .players
        .iter()
        .map(|player| {
            (
                player.agent_id.clone(),
                json!({
                    "resource": player.request_type,
                    "remaining": player.request_duration,
                }),
            )
        })
        .collect()
}

fn inventory_snapshot(env: &CraftaxCoopEnv, relevant_resource: &str) -> BTreeMap<String, Value> {
    env.state
        .players
        .iter()
        .map(|player| {
            (
                player.agent_id.clone(),
                json!({
                    "role": player.role,
                    "food": player.food,
                    "drink": player.drink,
                    "relevant_resource": relevant_resource,
                    "relevant_resource_amount": player.inventory.get(relevant_resource).copied().unwrap_or(0),
                    "pickaxe": player.pickaxe,
                }),
            )
        })
        .collect()
}

fn qualitative_rubric(
    outcome: bool,
    coordinated: bool,
    role_consistent: bool,
    aligned: bool,
    signals: usize,
    redundant: usize,
) -> Value {
    let need_identification = if aligned {
        5.0
    } else if signals > 0 {
        2.0
    } else {
        1.0
    };
    let role_clarity = if role_consistent { 5.0 } else { 1.0 };
    let grounding = if aligned {
        5.0
    } else if signals > 0 {
        2.0
    } else {
        1.0
    };
    let timing = if coordinated {
        5.0
    } else if outcome {
        3.0
    } else {
        1.0
    };
    let consistency = if coordinated {
        5.0
    } else if outcome {
        3.0
    } else {
        1.0
    };
    let efficiency = if coordinated && redundant == 0 {
        5.0
    } else if signals == 0 {
        2.0
    } else if redundant == 0 {
        3.0
    } else {
        1.0
    };
    json!({
        "need_identification": need_identification,
        "role_clarity": role_clarity,
        "request_action_grounding": grounding,
        "timing": timing,
        "action_consistency": consistency,
        "signal_efficiency": efficiency,
    })
}

fn episode_receipt(episode: &EpisodeEvidence) -> Value {
    json!({
        "split": episode.split,
        "seed": episode.seed,
        "probe": episode.probe,
        "checkpoint_digest": episode.checkpoint_digest,
        "candidate_id": episode.candidate_id,
        "outcome_success": episode.outcome_success,
        "coordination_success": episode.coordination_success,
        "role_assignment_consistent": episode.role_assignment_consistent,
        "request_action_aligned": episode.request_action_aligned,
        "grounded_signal_count": episode.grounded_signal_count,
        "redundant_signal_count": episode.redundant_signal_count,
        "give_attempt_count": episode.give_attempt_count,
        "successful_trade_count": episode.successful_trade_count,
        "qualitative_score": episode.qualitative_score,
        "final_state_digest": episode.final_state_digest,
    })
}

fn aggregate_evidence(evidence: &[EpisodeEvidence]) -> Value {
    let mut values: BTreeMap<String, BTreeMap<String, Aggregate>> = BTreeMap::new();
    for episode in evidence {
        let aggregate = values
            .entry(episode.split.clone())
            .or_default()
            .entry(episode.candidate_id.clone())
            .or_default();
        aggregate.count += 1;
        aggregate.outcomes += usize::from(episode.outcome_success);
        aggregate.coordinated += usize::from(episode.coordination_success);
        aggregate.role_consistent += usize::from(episode.role_assignment_consistent);
        aggregate.aligned += usize::from(episode.request_action_aligned);
        aggregate.signals += episode.grounded_signal_count;
        aggregate.redundant += episode.redundant_signal_count;
        aggregate.give_attempts += episode.give_attempt_count;
        aggregate.trades += episode.successful_trade_count;
        aggregate.qualitative_sum += episode.qualitative_score;
    }
    let mut output = serde_json::Map::new();
    for (split, candidates) in values {
        let mut candidate_values = serde_json::Map::new();
        for (candidate, aggregate) in candidates {
            let denominator = aggregate.count.max(1) as f64;
            candidate_values.insert(
                candidate,
                json!({
                    "n_probes": aggregate.count,
                    "outcome_successes": aggregate.outcomes,
                    "outcome_success_rate": aggregate.outcomes as f64 / denominator,
                    "coordination_successes": aggregate.coordinated,
                    "coordination_success_rate": aggregate.coordinated as f64 / denominator,
                    "role_consistency_rate": aggregate.role_consistent as f64 / denominator,
                    "request_action_alignment_rate": aggregate.aligned as f64 / denominator,
                    "grounded_signal_count": aggregate.signals,
                    "redundant_signal_count": aggregate.redundant,
                    "give_attempt_count": aggregate.give_attempts,
                    "successful_trade_count": aggregate.trades,
                    "signals_per_coordination_success": if aggregate.coordinated == 0 { Value::Null } else { json!(aggregate.signals as f64 / aggregate.coordinated as f64) },
                    "mean_qualitative_score": aggregate.qualitative_sum / denominator,
                }),
            );
        }
        output.insert(split, Value::Object(candidate_values));
    }
    Value::Object(output)
}

fn digest_text(text: &str) -> String {
    let mut hash = 0xcbf29ce484222325_u64;
    for byte in text.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x100000001b3);
    }
    format!("fnv1a64:{hash:016x}")
}

fn stable_path(path: &Path, task_dir: &Path) -> String {
    path.strip_prefix(task_dir)
        .unwrap_or(path)
        .to_string_lossy()
        .into_owned()
}

fn string_error(error: impl std::fmt::Display) -> String {
    error.to_string()
}
