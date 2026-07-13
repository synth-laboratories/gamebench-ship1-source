use dungeongrid_gold::{
    Direction, DungeonGridAction, DungeonGridSession, GiveItemPayload, MessagePayload,
    ObservationConfig, Pos, Scenario, SpellPayload, Terrain,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize, Serialize)]
struct DatasetConfig {
    schema: String,
    dataset_id: String,
    party_roles: Vec<String>,
    observation: ObservationConfig,
    transforms: Vec<String>,
    role_orders: Vec<String>,
    probes: Vec<String>,
    splits: BTreeMap<String, Vec<String>>,
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
    PreBreach,
    CarrierAssignment,
    ExtractionHandoff,
}

impl ProbeKind {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "pre_breach" => Ok(Self::PreBreach),
            "carrier_assignment" => Ok(Self::CarrierAssignment),
            "extraction_handoff" => Ok(Self::ExtractionHandoff),
            other => Err(format!("unsupported coordination probe {other:?}")),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::PreBreach => "pre_breach",
            Self::CarrierAssignment => "carrier_assignment",
            Self::ExtractionHandoff => "extraction_handoff",
        }
    }
}

#[derive(Clone, Debug)]
struct ProbeContext {
    kind: ProbeKind,
    checkpoint: Value,
    checkpoint_digest: String,
    frontliner: String,
    support: String,
    target_id: String,
    objective_item: String,
}

#[derive(Clone, Debug, Serialize)]
struct EpisodeEvidence {
    split: String,
    base_scenario_id: String,
    scenario_id: String,
    transform: String,
    role_order: String,
    probe: ProbeKind,
    checkpoint_digest: String,
    candidate_id: String,
    outcome_success: bool,
    coordination_success: bool,
    role_assignment_consistent: bool,
    message_action_aligned: bool,
    invalid_action_count: usize,
    hazard_event_count: usize,
    action_count: usize,
    message_count: usize,
    message_chars: usize,
    redundant_message_count: usize,
    total_reward: f64,
    qualitative_score: f64,
    qualitative_rubric: Value,
    messages: Vec<String>,
    event_kinds: Vec<String>,
    trace: Vec<Value>,
    final_state_digest: String,
}

#[derive(Default)]
struct Aggregate {
    count: usize,
    outcomes: usize,
    coordinated: usize,
    role_consistent: usize,
    aligned: usize,
    invalid: usize,
    hazards: usize,
    actions: usize,
    messages: usize,
    message_chars: usize,
    redundant: usize,
    reward_sum: f64,
    qualitative_sum: f64,
}

struct RubricInputs {
    outcome: bool,
    coordinated: bool,
    role_consistent: bool,
    aligned: bool,
    invalid: usize,
    hazards: usize,
    message_count: usize,
    message_chars: usize,
}

fn main() -> Result<(), String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let task_dir = manifest_dir
        .parent()
        .ok_or_else(|| "gold_rust must have a task parent".to_string())?;
    let default_dataset = task_dir.join("defaults/mapo_coordination/dataset_v1.json");
    let default_candidates = task_dir.join("defaults/mapo_coordination/candidates_v1.json");
    let default_output = task_dir.join("reports/mapo_coordination_rust_eval.json");
    let args = parse_args(default_dataset, default_candidates, default_output)?;

    let dataset: DatasetConfig = read_json(&args.dataset)?;
    let candidate_file: CandidateFile = read_json(&args.candidates)?;
    validate_config(&dataset, &candidate_file)?;

    let scenario_dir = task_dir.join("defaults/scenarios");
    let base_scenarios = load_scenarios(&scenario_dir)?;
    let split_index = split_index(&dataset)?;
    let probe_kinds = dataset
        .probes
        .iter()
        .map(|value| ProbeKind::parse(value))
        .collect::<Result<Vec<_>, _>>()?;

    let mut evidence = Vec::new();
    let mut scenario_count_by_split: BTreeMap<String, usize> = BTreeMap::new();
    let mut probe_count_by_split: BTreeMap<String, usize> = BTreeMap::new();
    for base in base_scenarios {
        let Some(split) = split_index.get(&base.scenario_id).cloned() else {
            continue;
        };
        for transform in &dataset.transforms {
            for role_order in &dataset.role_orders {
                let scenario = variant_scenario(&base, transform, role_order, &dataset)?;
                *scenario_count_by_split.entry(split.clone()).or_default() += 1;
                for kind in &probe_kinds {
                    let context = prepare_probe(&scenario, *kind)?;
                    *probe_count_by_split.entry(split.clone()).or_default() += 1;
                    for candidate in &candidate_file.candidates {
                        evidence.push(run_probe(
                            &split,
                            &base.scenario_id,
                            transform,
                            role_order,
                            candidate,
                            &context,
                        )?);
                    }
                }
            }
        }
    }

    let aggregates = aggregate_evidence(&evidence);
    let paired_communication_gaps = paired_communication_gaps(&aggregates)?;
    let dataset_digest = digest_json(&serde_json::to_value(&dataset).map_err(string_error)?)?;
    let candidates_digest =
        digest_json(&serde_json::to_value(&candidate_file.candidates).map_err(string_error)?)?;
    let report = json!({
        "schema": "gamebench.mapo_coordination_eval.v1",
        "status": "completed",
        "lane": "rust",
        "env_family": "dungeongrid-multiplayer",
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "dataset_schema": dataset.schema,
            "dataset_path": report_path(&args.dataset, task_dir),
            "dataset_sha256": dataset_digest,
            "scenario_count": scenario_count_by_split.values().sum::<usize>(),
            "scenario_count_by_split": scenario_count_by_split,
            "probe_count": probe_count_by_split.values().sum::<usize>(),
            "probe_count_by_split": probe_count_by_split,
            "candidate_continuation_count": evidence.len(),
            "diversity_contract": {
                "base_scenario_family_heldout": true,
                "seed_is_not_counted_as_dynamic_diversity": true,
                "party_roles": dataset.party_roles,
                "observation": dataset.observation,
                "transforms": dataset.transforms,
                "role_orders": dataset.role_orders,
                "probes": dataset.probes,
            }
        },
        "candidates": {
            "schema": candidate_file.schema,
            "path": report_path(&args.candidates, task_dir),
            "sha256": candidates_digest,
            "executor": "dungeongrid_rust_reference_protocol_executor.v1",
            "executor_scope": "Typed reference behaviors make the supplied prompts concrete for checkpoint evaluation; arbitrary natural-language policy execution still requires a model-backed policy adapter.",
            "definitions": candidate_file.candidates,
        },
        "summary": aggregates,
        "paired_communication_gaps": paired_communication_gaps,
        "qualitative_evaluation": {
            "evaluator": "deterministic_trace_rubric.v1",
            "blinded_external_judge_run": false,
            "rubric_fields": [
                "shared_state_understanding",
                "role_clarity",
                "appropriate_initiative",
                "message_grounding",
                "action_consistency",
                "communication_efficiency"
            ],
            "trace_contract": "Each episode includes agent, event, action, and payload evidence suitable for a separate blinded model or human review."
        },
        "episodes": evidence,
    });

    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent).map_err(|err| format!("create {}: {err}", parent.display()))?;
    }
    fs::write(
        &args.output,
        serde_json::to_vec_pretty(&report).map_err(string_error)?,
    )
    .map_err(|err| format!("write {}: {err}", args.output.display()))?;

    let printable = json!({
        "status": "completed",
        "output": args.output,
        "scenario_count": report["dataset"]["scenario_count"],
        "probe_count": report["dataset"]["probe_count"],
        "candidate_continuation_count": report["dataset"]["candidate_continuation_count"],
        "summary": report["summary"],
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&printable).map_err(string_error)?
    );
    Ok(())
}

struct Args {
    dataset: PathBuf,
    candidates: PathBuf,
    output: PathBuf,
}

fn parse_args(
    default_dataset: PathBuf,
    default_candidates: PathBuf,
    default_output: PathBuf,
) -> Result<Args, String> {
    let mut args = env::args().skip(1);
    let mut parsed = Args {
        dataset: default_dataset,
        candidates: default_candidates,
        output: default_output,
    };
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
    if candidates.schema != "gamebench.mapo_coordination_candidates.v1" {
        return Err(format!(
            "unsupported candidate schema {:?}",
            candidates.schema
        ));
    }
    if candidates.candidates.is_empty() {
        return Err("candidate file must contain at least one candidate".to_string());
    }
    if dataset.party_roles.len() != 4 {
        return Err("MAPO DungeonGrid dataset must define exactly four party roles".to_string());
    }
    if dataset.observation.visibility_radius < 1 {
        return Err("local visibility_radius must be at least one".to_string());
    }
    let mut ids = BTreeSet::new();
    for candidate in &candidates.candidates {
        if !ids.insert(candidate.id.clone()) {
            return Err(format!("duplicate candidate id {:?}", candidate.id));
        }
        if !matches!(
            candidate.executor_profile.as_str(),
            "no_message"
                | "verbose_baseline"
                | "verbose_channel_masked"
                | "compact_message_only"
                | "silent_structured_actions"
                | "event_triggered_compact"
                | "event_triggered_channel_masked"
        ) {
            return Err(format!(
                "candidate {:?} has unsupported executor_profile {:?}",
                candidate.id, candidate.executor_profile
            ));
        }
    }
    Ok(())
}

fn load_scenarios(directory: &Path) -> Result<Vec<Scenario>, String> {
    let mut paths = fs::read_dir(directory)
        .map_err(|err| format!("read {}: {err}", directory.display()))?
        .map(|entry| entry.map(|value| value.path()).map_err(string_error))
        .collect::<Result<Vec<_>, _>>()?;
    paths.retain(|path| {
        path.extension()
            .is_some_and(|extension| extension == "json")
    });
    paths.sort();
    paths
        .into_iter()
        .map(|path| {
            let text = fs::read_to_string(&path)
                .map_err(|err| format!("read {}: {err}", path.display()))?;
            Scenario::from_json_str(&text)
        })
        .collect()
}

fn split_index(dataset: &DatasetConfig) -> Result<BTreeMap<String, String>, String> {
    let mut index = BTreeMap::new();
    for (split, scenario_ids) in &dataset.splits {
        for scenario_id in scenario_ids {
            if let Some(previous) = index.insert(scenario_id.clone(), split.clone()) {
                return Err(format!(
                    "base scenario {scenario_id:?} appears in both {previous:?} and {split:?}"
                ));
            }
        }
    }
    Ok(index)
}

fn variant_scenario(
    base: &Scenario,
    transform: &str,
    role_order: &str,
    dataset: &DatasetConfig,
) -> Result<Scenario, String> {
    let mut scenario = base.clone();
    scenario.map_ascii = transform_map(&base.map_ascii, transform)?;
    scenario.hero_roles = dataset.party_roles.clone();
    scenario.observation = dataset.observation.clone();
    match role_order {
        "original" => {}
        "swapped" => {
            if scenario.hero_roles.len() < 2 {
                return Err("swapped role order requires at least two party roles".to_string());
            }
            scenario.hero_roles.swap(0, 1);
        }
        other => return Err(format!("unsupported role order {other:?}")),
    }
    scenario.scenario_id = format!("{}__{}__{}", base.scenario_id, transform, role_order);
    scenario.task_id = format!("{}__{}__{}", base.task_id, transform, role_order);
    scenario.seed = stable_seed(&scenario.scenario_id);
    scenario.metadata.insert(
        "mapo_dataset_variant".to_string(),
        json!({"base_scenario_id": base.scenario_id, "transform": transform, "role_order": role_order}),
    );
    Ok(scenario)
}

fn transform_map(map: &str, transform: &str) -> Result<String, String> {
    let mut rows = map
        .lines()
        .map(|line| line.chars().collect::<Vec<_>>())
        .collect::<Vec<_>>();
    match transform {
        "identity" => {}
        "mirror_x" => rows.iter_mut().for_each(|row| row.reverse()),
        "mirror_y" => rows.reverse(),
        "rotate_180" => {
            rows.reverse();
            rows.iter_mut().for_each(|row| row.reverse());
        }
        other => return Err(format!("unsupported map transform {other:?}")),
    }
    Ok(rows
        .into_iter()
        .map(|row| row.into_iter().collect::<String>())
        .collect::<Vec<_>>()
        .join("\n"))
}

fn stable_seed(value: &str) -> i64 {
    let digest = Sha256::digest(value.as_bytes());
    i64::from_be_bytes(digest[..8].try_into().expect("sha256 has eight bytes")) & i64::MAX
}

fn prepare_probe(scenario: &Scenario, kind: ProbeKind) -> Result<ProbeContext, String> {
    let mut session = DungeonGridSession::reset(scenario.clone())?;
    let frontliner = role_agent(&session, "barbarian")?;
    let support = role_agent(&session, "wizard")?;
    let mut turn_order = vec![support.clone(), frontliner.clone()];
    turn_order.extend(
        session
            .heroes
            .keys()
            .filter(|agent_id| *agent_id != &support && *agent_id != &frontliner)
            .cloned(),
    );
    session.turn_order = turn_order;
    session.turn_cursor = 0;
    session.active_agent = support.clone();
    for hero in session.heroes.values_mut() {
        hero.ap = hero.max_ap;
        hero.guarded = false;
    }

    let target_id = match kind {
        ProbeKind::PreBreach => prepare_breach(&mut session, &frontliner, &support)?,
        ProbeKind::CarrierAssignment => {
            prepare_carrier_assignment(&mut session, &frontliner, &support)?
        }
        ProbeKind::ExtractionHandoff => {
            prepare_extraction_handoff(&mut session, &frontliner, &support)?
        }
    };
    let checkpoint = session.checkpoint_json();
    let checkpoint_digest = digest_json(&checkpoint)?;
    let restored = DungeonGridSession::restore_from_checkpoint_value(checkpoint.clone())?;
    if restored.state_digest()? != session.state_digest()? {
        return Err(format!(
            "checkpoint restore changed state for {} {}",
            scenario.scenario_id,
            kind.as_str()
        ));
    }
    Ok(ProbeContext {
        kind,
        checkpoint,
        checkpoint_digest,
        frontliner,
        support,
        target_id,
        objective_item: scenario.objective_item.clone(),
    })
}

fn role_agent(session: &DungeonGridSession, role: &str) -> Result<String, String> {
    session
        .heroes
        .iter()
        .find_map(|(agent_id, hero)| (hero.role == role).then(|| agent_id.clone()))
        .ok_or_else(|| {
            format!(
                "scenario {} has no {role} hero",
                session.scenario.scenario_id
            )
        })
}

fn prepare_breach(
    session: &mut DungeonGridSession,
    frontliner: &str,
    support: &str,
) -> Result<String, String> {
    let (door_id, door_pos) = session
        .doors
        .iter()
        .find(|(_, door)| !door.open && !door.secret)
        .map(|(id, door)| (id.clone(), door.pos))
        .ok_or_else(|| {
            format!(
                "scenario {} has no visible breach door",
                session.scenario.scenario_id
            )
        })?;
    let monster_pos = session
        .monsters
        .values()
        .find(|monster| monster.hp > 0)
        .map(|monster| monster.pos)
        .ok_or_else(|| {
            format!(
                "scenario {} has no breach defender",
                session.scenario.scenario_id
            )
        })?;
    let front_pos = passable_positions(session)
        .into_iter()
        .filter(|pos| pos.manhattan(door_pos) == 1 && *pos != monster_pos)
        .max_by_key(|pos| pos.manhattan(monster_pos))
        .ok_or_else(|| {
            format!(
                "scenario {} has no staging tile at breach",
                session.scenario.scenario_id
            )
        })?;
    let support_pos = passable_positions(session)
        .into_iter()
        .filter(|pos| *pos != front_pos && pos.manhattan(monster_pos) <= 4)
        .min_by_key(|pos| (pos.manhattan(front_pos), pos.manhattan(monster_pos)))
        .ok_or_else(|| {
            format!(
                "scenario {} has no support casting tile",
                session.scenario.scenario_id
            )
        })?;
    session
        .heroes
        .get_mut(frontliner)
        .expect("frontliner exists")
        .pos = front_pos;
    session.heroes.get_mut(support).expect("support exists").pos = support_pos;
    for trap in session.traps.values_mut() {
        if trap.pos == front_pos || trap.pos == support_pos {
            trap.revealed = true;
            trap.armed = false;
        }
    }
    Ok(door_id)
}

fn prepare_carrier_assignment(
    session: &mut DungeonGridSession,
    frontliner: &str,
    support: &str,
) -> Result<String, String> {
    for door in session.doors.values_mut() {
        door.open = true;
        door.discovered = true;
    }
    for monster in session.monsters.values_mut() {
        monster.hp = 0;
    }
    let objective = terrain_pos(session, Terrain::Objective)?;
    let mut nearby = passable_positions(session)
        .into_iter()
        .filter(|pos| pos.manhattan(objective) == 1)
        .collect::<Vec<_>>();
    nearby.sort();
    let front_pos = *nearby.first().ok_or_else(|| {
        format!(
            "scenario {} has no objective staging tile",
            session.scenario.scenario_id
        )
    })?;
    let support_pos = passable_positions(session)
        .into_iter()
        .filter(|pos| *pos != front_pos)
        .min_by_key(|pos| pos.manhattan(front_pos))
        .ok_or_else(|| {
            format!(
                "scenario {} has no support objective tile",
                session.scenario.scenario_id
            )
        })?;
    session
        .heroes
        .get_mut(frontliner)
        .expect("frontliner exists")
        .pos = front_pos;
    session.heroes.get_mut(support).expect("support exists").pos = support_pos;
    for hero in session.heroes.values_mut() {
        hero.inventory
            .retain(|item| item != &session.scenario.objective_item);
    }
    Ok("objective".to_string())
}

fn prepare_extraction_handoff(
    session: &mut DungeonGridSession,
    frontliner: &str,
    support: &str,
) -> Result<String, String> {
    for door in session.doors.values_mut() {
        door.open = true;
        door.discovered = true;
    }
    for monster in session.monsters.values_mut() {
        monster.hp = 0;
    }
    let escape = terrain_pos(session, Terrain::Escape)?;
    let support_pos = passable_positions(session)
        .into_iter()
        .find(|pos| pos.manhattan(escape) == 1)
        .ok_or_else(|| {
            format!(
                "scenario {} has no extraction handoff tile",
                session.scenario.scenario_id
            )
        })?;
    session
        .heroes
        .get_mut(frontliner)
        .expect("frontliner exists")
        .pos = escape;
    session.heroes.get_mut(support).expect("support exists").pos = support_pos;
    for hero in session.heroes.values_mut() {
        hero.inventory
            .retain(|item| item != &session.scenario.objective_item);
    }
    session
        .heroes
        .get_mut(support)
        .expect("support exists")
        .inventory
        .push(session.scenario.objective_item.clone());
    Ok("escape".to_string())
}

fn terrain_pos(session: &DungeonGridSession, terrain: Terrain) -> Result<Pos, String> {
    session
        .terrain
        .iter()
        .find_map(|(pos, value)| (*value == terrain).then_some(*pos))
        .ok_or_else(|| {
            format!(
                "scenario {} is missing {terrain:?}",
                session.scenario.scenario_id
            )
        })
}

fn passable_positions(session: &DungeonGridSession) -> Vec<Pos> {
    session
        .terrain
        .iter()
        .filter_map(|(pos, terrain)| {
            matches!(
                terrain,
                Terrain::Floor | Terrain::Escape | Terrain::Objective
            )
            .then_some(*pos)
        })
        .filter(|pos| {
            !session
                .doors
                .values()
                .any(|door| door.pos == *pos && !door.open)
        })
        .filter(|pos| {
            !session
                .monsters
                .values()
                .any(|monster| monster.pos == *pos && monster.hp > 0)
        })
        .collect()
}

fn run_probe(
    split: &str,
    base_scenario_id: &str,
    transform: &str,
    role_order: &str,
    candidate: &Candidate,
    context: &ProbeContext,
) -> Result<EpisodeEvidence, String> {
    let mut session =
        DungeonGridSession::restore_from_checkpoint_value(context.checkpoint.clone())?;
    let event_start = session.event_log.len();
    let actions = actions_for(candidate, context)?;
    let mut action_count = 0;
    for action in actions {
        if is_channel_masked(&candidate.executor_profile)
            && matches!(action, DungeonGridAction::Message { .. })
        {
            continue;
        }
        let action = gate_load_bearing_action(candidate, context, &session, action);
        session.step(action);
        action_count += 1;
        if session.done {
            break;
        }
    }
    let events = &session.event_log[event_start..];
    let messages = events
        .iter()
        .filter(|event| event.kind == "message_sent")
        .filter_map(|event| event.payload.get("text").and_then(Value::as_str))
        .map(str::to_string)
        .collect::<Vec<_>>();
    let message_chars = messages.iter().map(String::len).sum();
    let invalid_action_count = events
        .iter()
        .filter(|event| event.kind == "action_rejected")
        .count();
    let hazard_event_count = events
        .iter()
        .filter(|event| event.kind == "trap_triggered")
        .count();
    let outcome_success = outcome_success(context.kind, events);
    let role_assignment_consistent = role_consistent(context, &session, events);
    let message_action_aligned = aligned_message(context.kind, events);
    let coordination_success = coordination_success(
        context.kind,
        events,
        outcome_success,
        role_assignment_consistent,
        invalid_action_count,
        hazard_event_count,
    );
    let redundant_message_count = messages.len().saturating_sub(1);
    let qualitative_rubric = qualitative_rubric(RubricInputs {
        outcome: outcome_success,
        coordinated: coordination_success,
        role_consistent: role_assignment_consistent,
        aligned: message_action_aligned,
        invalid: invalid_action_count,
        hazards: hazard_event_count,
        message_count: messages.len(),
        message_chars,
    });
    let qualitative_score = qualitative_rubric
        .as_object()
        .expect("rubric is an object")
        .values()
        .filter_map(Value::as_f64)
        .sum::<f64>()
        / 6.0;
    Ok(EpisodeEvidence {
        split: split.to_string(),
        base_scenario_id: base_scenario_id.to_string(),
        scenario_id: session.scenario.scenario_id.clone(),
        transform: transform.to_string(),
        role_order: role_order.to_string(),
        probe: context.kind,
        checkpoint_digest: context.checkpoint_digest.clone(),
        candidate_id: candidate.id.clone(),
        outcome_success,
        coordination_success,
        role_assignment_consistent,
        message_action_aligned,
        invalid_action_count,
        hazard_event_count,
        action_count,
        message_count: messages.len(),
        message_chars,
        redundant_message_count,
        total_reward: session.total_reward,
        qualitative_score,
        qualitative_rubric,
        messages,
        event_kinds: events.iter().map(|event| event.kind.clone()).collect(),
        trace: events
            .iter()
            .map(|event| {
                json!({
                    "step_index": event.step_index,
                    "turn_index": event.turn_index,
                    "agent_id": event.agent_id,
                    "kind": event.kind,
                    "action": event.action,
                    "payload": event.payload,
                })
            })
            .collect(),
        final_state_digest: session.state_digest()?,
    })
}

fn actions_for(
    candidate: &Candidate,
    context: &ProbeContext,
) -> Result<Vec<DungeonGridAction>, String> {
    let message = |text: &str| DungeonGridAction::Message {
        target: "party".to_string(),
        payload: MessagePayload {
            text: text.to_string(),
        },
    };
    let end = || DungeonGridAction::EndTurn;
    let executor_profile = match candidate.executor_profile.as_str() {
        "event_triggered_channel_masked" => "event_triggered_compact",
        "verbose_channel_masked" => "verbose_baseline",
        profile => profile,
    };
    let actions = match (executor_profile, context.kind) {
        ("no_message", ProbeKind::PreBreach) => vec![
            end(),
            DungeonGridAction::OpenDoor {
                target: context.target_id.clone(),
            },
        ],
        ("no_message", ProbeKind::CarrierAssignment) => vec![
            end(),
            DungeonGridAction::Interact {
                target: "objective".to_string(),
            },
        ],
        ("no_message", ProbeKind::ExtractionHandoff) => vec![
            end(),
            DungeonGridAction::Interact {
                target: "escape".to_string(),
            },
        ],
        ("verbose_baseline", ProbeKind::PreBreach) => vec![
            message(
                "I am considering how we should approach this room and will keep everyone updated.",
            ),
            message(
                "We should probably be careful and continue coordinating before anybody commits.",
            ),
            end(),
            message("I acknowledge the plan and am now opening the nearby door as discussed."),
            DungeonGridAction::OpenDoor {
                target: context.target_id.clone(),
            },
        ],
        ("verbose_baseline", ProbeKind::CarrierAssignment) => vec![
            message("The objective is nearby and one of us should probably pick it up when ready."),
            message("I will continue narrating while the party decides who should carry it."),
            end(),
            message("I am close to the objective and will interact with it now."),
            DungeonGridAction::Interact {
                target: "objective".to_string(),
            },
        ],
        ("verbose_baseline", ProbeKind::ExtractionHandoff) => vec![
            message(
                "We have reached the extraction area and should think carefully about leaving.",
            ),
            message("The party is coordinating around the escape tile and the carried objective."),
            end(),
            DungeonGridAction::Interact {
                target: "escape".to_string(),
            },
        ],
        ("compact_message_only", ProbeKind::PreBreach) => vec![
            message("DG|BREACH=HOLD;WIZ=REVEAL;BARB=OPEN"),
            end(),
            DungeonGridAction::OpenDoor {
                target: context.target_id.clone(),
            },
        ],
        ("compact_message_only", ProbeKind::CarrierAssignment) => vec![
            message("DG|CARRIER=BARB;OBJECTIVE=TAKE;SUPPORT=HOLD"),
            end(),
            DungeonGridAction::Interact {
                target: "objective".to_string(),
            },
        ],
        ("compact_message_only", ProbeKind::ExtractionHandoff) => vec![
            message("DG|HANDOFF=OBJECTIVE;EXTRACT=BARB"),
            end(),
            DungeonGridAction::Interact {
                target: "escape".to_string(),
            },
        ],
        ("silent_structured_actions", ProbeKind::PreBreach) => {
            let monster = context
                .checkpoint
                .pointer("/dynamic/monsters")
                .and_then(Value::as_object)
                .and_then(|monsters| monsters.keys().next())
                .cloned()
                .ok_or_else(|| "breach checkpoint has no monster".to_string())?;
            vec![
                DungeonGridAction::Cast {
                    target: monster,
                    payload: SpellPayload {
                        spell: "reveal_glyph".to_string(),
                    },
                },
                end(),
                DungeonGridAction::OpenDoor {
                    target: context.target_id.clone(),
                },
            ]
        }
        ("silent_structured_actions", ProbeKind::CarrierAssignment) => vec![
            end(),
            DungeonGridAction::Interact {
                target: "objective".to_string(),
            },
        ],
        ("silent_structured_actions", ProbeKind::ExtractionHandoff) => vec![
            DungeonGridAction::GiveItem {
                target: context.frontliner.clone(),
                payload: GiveItemPayload {
                    item: context.objective_item.clone(),
                },
            },
            end(),
            DungeonGridAction::Interact {
                target: "escape".to_string(),
            },
        ],
        ("event_triggered_compact", ProbeKind::PreBreach) => {
            let monster = context
                .checkpoint
                .pointer("/dynamic/monsters")
                .and_then(Value::as_object)
                .and_then(|monsters| monsters.keys().next())
                .cloned()
                .ok_or_else(|| "breach checkpoint has no monster".to_string())?;
            let mut actions = vec![
                message("DG|BREACH=HOLD;WIZ=REVEAL;BARB=OPEN"),
                end(),
                DungeonGridAction::Guard,
                end(),
            ];
            let party_size = context
                .checkpoint
                .pointer("/dynamic/turn_order")
                .and_then(Value::as_array)
                .map(Vec::len)
                .unwrap_or(2);
            actions.extend((0..party_size.saturating_sub(2)).map(|_| end()));
            actions.extend([
                DungeonGridAction::Cast {
                    target: monster,
                    payload: SpellPayload {
                        spell: "reveal_glyph".to_string(),
                    },
                },
                end(),
                DungeonGridAction::OpenDoor {
                    target: context.target_id.clone(),
                },
            ]);
            actions
        }
        ("event_triggered_compact", ProbeKind::CarrierAssignment) => vec![
            message("DG|CARRIER=BARB;OBJECTIVE=TAKE;SUPPORT=HOLD"),
            end(),
            DungeonGridAction::Interact {
                target: "objective".to_string(),
            },
        ],
        ("event_triggered_compact", ProbeKind::ExtractionHandoff) => vec![
            message("DG|HANDOFF=OBJECTIVE;EXTRACT=BARB"),
            DungeonGridAction::GiveItem {
                target: context.frontliner.clone(),
                payload: GiveItemPayload {
                    item: context.objective_item.clone(),
                },
            },
            end(),
            DungeonGridAction::Interact {
                target: "escape".to_string(),
            },
        ],
        (profile, kind) => {
            return Err(format!(
                "unsupported executor profile/probe pair {profile:?}/{}",
                kind.as_str()
            ))
        }
    };
    Ok(actions)
}

fn is_channel_masked(profile: &str) -> bool {
    matches!(
        profile,
        "verbose_channel_masked" | "event_triggered_channel_masked"
    )
}

fn gate_load_bearing_action(
    candidate: &Candidate,
    context: &ProbeContext,
    session: &DungeonGridSession,
    action: DungeonGridAction,
) -> DungeonGridAction {
    if !matches!(
        candidate.executor_profile.as_str(),
        "event_triggered_compact" | "event_triggered_channel_masked"
    ) || session.active_agent != context.frontliner
    {
        return action;
    }
    let required_signal = match (&action, context.kind) {
        (DungeonGridAction::OpenDoor { .. }, ProbeKind::PreBreach) => Some("BREACH"),
        (DungeonGridAction::Interact { target }, ProbeKind::CarrierAssignment)
            if target == "objective" =>
        {
            Some("CARRIER")
        }
        (DungeonGridAction::Interact { target }, ProbeKind::ExtractionHandoff)
            if target == "escape" =>
        {
            Some("EXTRACT")
        }
        _ => None,
    };
    let Some(required_signal) = required_signal else {
        return action;
    };
    let signal_received = session
        .message_inboxes
        .get(&context.frontliner)
        .is_some_and(|messages| {
            messages
                .iter()
                .any(|message| message.text.to_ascii_uppercase().contains(required_signal))
        });
    if signal_received {
        action
    } else {
        DungeonGridAction::Guard
    }
}

fn outcome_success(kind: ProbeKind, events: &[dungeongrid_gold::EventRecord]) -> bool {
    let target = match kind {
        ProbeKind::PreBreach => "door_opened",
        ProbeKind::CarrierAssignment => "objective_taken",
        ProbeKind::ExtractionHandoff => "objective_escaped",
    };
    events.iter().any(|event| event.kind == target)
}

fn role_consistent(
    context: &ProbeContext,
    session: &DungeonGridSession,
    events: &[dungeongrid_gold::EventRecord],
) -> bool {
    match context.kind {
        ProbeKind::PreBreach => {
            event_agent(events, "counterplay_revealed") == Some(&context.support)
                && event_agent(events, "door_opened") == Some(&context.frontliner)
        }
        ProbeKind::CarrierAssignment => session
            .heroes
            .get(&context.frontliner)
            .is_some_and(|hero| hero.inventory.contains(&context.objective_item)),
        ProbeKind::ExtractionHandoff => {
            event_agent(events, "item_given") == Some(&context.support)
                && event_agent(events, "objective_escaped") == Some(&context.frontliner)
        }
    }
}

fn event_agent<'a>(events: &'a [dungeongrid_gold::EventRecord], kind: &str) -> Option<&'a String> {
    events
        .iter()
        .find(|event| event.kind == kind)
        .map(|event| &event.agent_id)
}

fn aligned_message(kind: ProbeKind, events: &[dungeongrid_gold::EventRecord]) -> bool {
    let action_kind = match kind {
        ProbeKind::PreBreach => "counterplay_revealed",
        ProbeKind::CarrierAssignment => "objective_taken",
        ProbeKind::ExtractionHandoff => "item_given",
    };
    let Some(action_index) = events.iter().position(|event| event.kind == action_kind) else {
        return false;
    };
    events[..action_index].iter().any(|event| {
        if event.kind != "message_sent" {
            return false;
        }
        let text = event
            .payload
            .get("text")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_ascii_uppercase();
        match kind {
            ProbeKind::PreBreach => text.contains("BREACH") && text.contains("REVEAL"),
            ProbeKind::CarrierAssignment => text.contains("CARRIER") && text.contains("BARB"),
            ProbeKind::ExtractionHandoff => text.contains("HANDOFF") && text.contains("EXTRACT"),
        }
    })
}

fn coordination_success(
    kind: ProbeKind,
    events: &[dungeongrid_gold::EventRecord],
    outcome: bool,
    role_consistent: bool,
    invalid: usize,
    hazards: usize,
) -> bool {
    if !outcome || !role_consistent || invalid > 0 || hazards > 0 {
        return false;
    }
    match kind {
        ProbeKind::PreBreach => ordered(events, "counterplay_revealed", "door_opened"),
        ProbeKind::CarrierAssignment => true,
        ProbeKind::ExtractionHandoff => ordered(events, "item_given", "objective_escaped"),
    }
}

fn ordered(events: &[dungeongrid_gold::EventRecord], first: &str, second: &str) -> bool {
    let first_index = events.iter().position(|event| event.kind == first);
    let second_index = events.iter().position(|event| event.kind == second);
    matches!((first_index, second_index), (Some(left), Some(right)) if left < right)
}

fn qualitative_rubric(inputs: RubricInputs) -> Value {
    let RubricInputs {
        outcome,
        coordinated,
        role_consistent,
        aligned,
        invalid,
        hazards,
        message_count,
        message_chars,
    } = inputs;
    let shared_state = if aligned {
        5.0
    } else if coordinated {
        4.0
    } else if outcome {
        3.0
    } else {
        1.0
    };
    let role_clarity = if role_consistent { 5.0 } else { 1.0 };
    let initiative = if coordinated {
        5.0
    } else if outcome {
        3.0
    } else {
        1.0
    };
    let grounding = if aligned && invalid == 0 && hazards == 0 {
        5.0
    } else if invalid == 0 && hazards == 0 {
        3.0
    } else {
        1.0
    };
    let action_consistency = if coordinated && hazards == 0 {
        5.0
    } else if outcome {
        3.0
    } else {
        1.0
    };
    let communication_efficiency = if message_count == 1 && message_chars <= 140 {
        5.0
    } else if message_count == 0 {
        3.0
    } else if message_count <= 2 && message_chars <= 280 {
        2.0
    } else {
        1.0
    };
    json!({
        "shared_state_understanding": shared_state,
        "role_clarity": role_clarity,
        "appropriate_initiative": initiative,
        "message_grounding": grounding,
        "action_consistency": action_consistency,
        "communication_efficiency": communication_efficiency,
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
        aggregate.aligned += usize::from(episode.message_action_aligned);
        aggregate.invalid += episode.invalid_action_count;
        aggregate.hazards += episode.hazard_event_count;
        aggregate.actions += episode.action_count;
        aggregate.messages += episode.message_count;
        aggregate.message_chars += episode.message_chars;
        aggregate.redundant += episode.redundant_message_count;
        aggregate.reward_sum += episode.total_reward;
        aggregate.qualitative_sum += episode.qualitative_score;
    }
    let mut output = serde_json::Map::new();
    for (split, candidates) in values {
        let mut candidate_values = serde_json::Map::new();
        for (candidate, aggregate) in candidates {
            let denominator = aggregate.count.max(1) as f64;
            let chars_per_coordination_success = if aggregate.coordinated == 0 {
                Value::Null
            } else {
                json!(aggregate.message_chars as f64 / aggregate.coordinated as f64)
            };
            candidate_values.insert(
                candidate,
                json!({
                    "n_probes": aggregate.count,
                    "outcome_successes": aggregate.outcomes,
                    "outcome_success_rate": aggregate.outcomes as f64 / denominator,
                    "coordination_successes": aggregate.coordinated,
                    "coordination_success_rate": aggregate.coordinated as f64 / denominator,
                    "role_consistency_rate": aggregate.role_consistent as f64 / denominator,
                    "message_action_alignment_rate": aggregate.aligned as f64 / denominator,
                    "invalid_action_count": aggregate.invalid,
                    "hazard_event_count": aggregate.hazards,
                    "mean_action_count": aggregate.actions as f64 / denominator,
                    "message_count": aggregate.messages,
                    "message_chars": aggregate.message_chars,
                    "redundant_message_count": aggregate.redundant,
                    "message_chars_per_coordination_success": chars_per_coordination_success,
                    "mean_total_reward": aggregate.reward_sum / denominator,
                    "mean_qualitative_score": aggregate.qualitative_sum / denominator,
                }),
            );
        }
        output.insert(split, Value::Object(candidate_values));
    }
    Value::Object(output)
}

fn paired_communication_gaps(summary: &Value) -> Result<Value, String> {
    let mut splits = serde_json::Map::new();
    for split in ["train", "selection", "heldout"] {
        let pre = communication_pair(summary, split, "verbose_baseline", "verbose_channel_masked")?;
        let post = communication_pair(
            summary,
            split,
            "event_triggered_compact",
            "event_triggered_channel_masked",
        )?;
        let outcome_difference_in_differences_pp =
            metric(&post, "outcome_gap_pp")? - metric(&pre, "outcome_gap_pp")?;
        let coordination_difference_in_differences_pp =
            metric(&post, "coordination_gap_pp")? - metric(&pre, "coordination_gap_pp")?;
        let qualitative_difference_in_differences =
            metric(&post, "qualitative_gap")? - metric(&pre, "qualitative_gap")?;
        splits.insert(
            split.to_string(),
            json!({
                "pre_opt": pre,
                "post_opt": post,
                "difference_in_differences": {
                    "outcome_pp": outcome_difference_in_differences_pp,
                    "coordination_pp": coordination_difference_in_differences_pp,
                    "qualitative_score": qualitative_difference_in_differences,
                }
            }),
        );
    }
    Ok(json!({
        "design": "paired_2x2_same_checkpoint_reference_executor",
        "gap_definition": "communication_enabled_minus_channel_masked",
        "reward_warning": "DungeonGrid awards a direct message reward, so reward gaps are reported diagnostically and are not causal outcome evidence.",
        "splits": splits,
    }))
}

fn communication_pair(
    summary: &Value,
    split: &str,
    enabled_candidate: &str,
    masked_candidate: &str,
) -> Result<Value, String> {
    let enabled = summary
        .pointer(&format!("/{split}/{enabled_candidate}"))
        .ok_or_else(|| format!("summary missing {split}/{enabled_candidate}"))?;
    let masked = summary
        .pointer(&format!("/{split}/{masked_candidate}"))
        .ok_or_else(|| format!("summary missing {split}/{masked_candidate}"))?;
    Ok(json!({
        "communication_enabled_candidate": enabled_candidate,
        "channel_masked_candidate": masked_candidate,
        "outcome_gap_pp": 100.0 * (metric(enabled, "outcome_success_rate")? - metric(masked, "outcome_success_rate")?),
        "coordination_gap_pp": 100.0 * (metric(enabled, "coordination_success_rate")? - metric(masked, "coordination_success_rate")?),
        "qualitative_gap": metric(enabled, "mean_qualitative_score")? - metric(masked, "mean_qualitative_score")?,
        "mean_action_count_gap": metric(enabled, "mean_action_count")? - metric(masked, "mean_action_count")?,
        "message_count_gap": metric(enabled, "message_count")? - metric(masked, "message_count")?,
        "message_chars_gap": metric(enabled, "message_chars")? - metric(masked, "message_chars")?,
        "diagnostic_reward_gap": metric(enabled, "mean_total_reward")? - metric(masked, "mean_total_reward")?,
    }))
}

fn metric(value: &Value, field: &str) -> Result<f64, String> {
    value
        .get(field)
        .and_then(Value::as_f64)
        .ok_or_else(|| format!("metric {field:?} missing or non-numeric"))
}

fn digest_json(value: &Value) -> Result<String, String> {
    let bytes = serde_json::to_vec(value).map_err(string_error)?;
    let digest = Sha256::digest(bytes);
    Ok(format!("{digest:x}"))
}

fn report_path(path: &Path, task_dir: &Path) -> String {
    path.strip_prefix(task_dir)
        .map(|relative| {
            format!(
                "tasks/dungeongrid-multiplayer/{}",
                relative.to_string_lossy()
            )
        })
        .unwrap_or_else(|_| path.to_string_lossy().into_owned())
}

fn string_error(error: impl std::fmt::Display) -> String {
    error.to_string()
}

#[allow(dead_code)]
fn direction_between(from: Pos, to: Pos) -> Result<Direction, String> {
    match (to.x - from.x, to.y - from.y) {
        (0, -1) => Ok(Direction::North),
        (0, 1) => Ok(Direction::South),
        (-1, 0) => Ok(Direction::West),
        (1, 0) => Ok(Direction::East),
        delta => Err(format!("positions are not adjacent: {delta:?}")),
    }
}
