use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use dungeongrid_gold::{
    DungeonGridAction, DungeonGridSession, EventRecord, GiveItemPayload, MessagePayload,
    ObservationConfig, Pos, Scenario, SpellPayload, Terrain,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::model::{
    contribution_coverage, AgentContribution, EpisodeEvidence, EpisodeMetrics, ExecutionSpec,
    ROW_SCHEMA,
};
use crate::protocol::{
    FollowerReply, HandoffPolicy, Priority, RequestPolicy, RoleMode, SpeakPolicy,
};

const ENVIRONMENT_ID: &str = "dungeongrid-multiplayer";
const DATASET_SCHEMA: &str = "gamebench.mapo_coordination_dataset.v1";

#[derive(Debug, Deserialize)]
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
            other => Err(format!(
                "unsupported DungeonGrid coordination probe {other:?}"
            )),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::PreBreach => "pre_breach",
            Self::CarrierAssignment => "carrier_assignment",
            Self::ExtractionHandoff => "extraction_handoff",
        }
    }

    fn required_signal(self) -> &'static str {
        match self {
            Self::PreBreach => "BREACH",
            Self::CarrierAssignment => "CARRIER",
            Self::ExtractionHandoff => "EXTRACT",
        }
    }
}

#[derive(Clone, Debug)]
struct Task {
    task_id: String,
    split: String,
    base_scenario_id: String,
    transform: String,
    role_order: String,
    probe: ProbeKind,
    checkpoint_key: String,
}

#[derive(Clone, Debug)]
struct ProbeContext {
    checkpoint: Value,
    checkpoint_digest: String,
    frontliner: String,
    support: String,
    target_id: String,
    objective_item: String,
}

#[derive(Clone, Debug)]
struct Intent {
    kind: &'static str,
    actor: String,
    action: DungeonGridAction,
    gate_signal: Option<&'static str>,
}

struct RunRecorder {
    event_start: usize,
    action_trace: Vec<Value>,
    per_agent: BTreeMap<String, AgentContribution>,
    idle_action_count: usize,
    interference_action_count: usize,
    masked_delivery_count: usize,
}

impl RunRecorder {
    fn new(session: &DungeonGridSession) -> Self {
        Self {
            event_start: session.event_log.len(),
            action_trace: Vec::new(),
            per_agent: session
                .heroes
                .keys()
                .cloned()
                .map(|agent_id| (agent_id, AgentContribution::default()))
                .collect(),
            idle_action_count: 0,
            interference_action_count: 0,
            masked_delivery_count: 0,
        }
    }
}

pub struct DungeonGridBackend {
    dataset_id: String,
    party_roles: Vec<String>,
    observation: ObservationConfig,
    tasks: BTreeMap<String, Task>,
    base_scenarios: BTreeMap<String, Scenario>,
    split_counts: BTreeMap<String, usize>,
}

impl DungeonGridBackend {
    pub fn load(tasks_root: &Path) -> Result<Self, String> {
        let task_root = tasks_root.join("dungeongrid-multiplayer");
        let dataset_path = task_root.join("defaults/mapo_coordination/dataset_v1.json");
        let text = fs::read_to_string(&dataset_path)
            .map_err(|error| format!("read {}: {error}", dataset_path.display()))?;
        let dataset: DatasetConfig = serde_json::from_str(&text)
            .map_err(|error| format!("parse {}: {error}", dataset_path.display()))?;
        if dataset.schema != DATASET_SCHEMA {
            return Err(format!(
                "unsupported DungeonGrid dataset schema {:?}",
                dataset.schema
            ));
        }
        if dataset.party_roles.len() != 4 {
            return Err(
                "DungeonGrid prompt optimizer requires exactly four party roles".to_string(),
            );
        }
        let probes = dataset
            .probes
            .iter()
            .map(|value| ProbeKind::parse(value))
            .collect::<Result<Vec<_>, _>>()?;
        let scenario_ids = dataset
            .splits
            .values()
            .flatten()
            .cloned()
            .collect::<BTreeSet<_>>();
        let mut base_scenarios = BTreeMap::new();
        for scenario_id in scenario_ids {
            let path = task_root.join(format!("defaults/scenarios/{scenario_id}.json"));
            let text = fs::read_to_string(&path)
                .map_err(|error| format!("read {}: {error}", path.display()))?;
            let scenario = Scenario::from_json_str(&text)?;
            if scenario.scenario_id != scenario_id {
                return Err(format!(
                    "DungeonGrid scenario file {} declares {:?}",
                    path.display(),
                    scenario.scenario_id
                ));
            }
            base_scenarios.insert(scenario_id, scenario);
        }

        let mut tasks = BTreeMap::new();
        let mut split_counts = BTreeMap::new();
        let mut seen_scenarios = BTreeSet::new();
        for (split, ids) in &dataset.splits {
            validate_split(split)?;
            for base_scenario_id in ids {
                if !seen_scenarios.insert(base_scenario_id.clone()) {
                    return Err(format!(
                        "DungeonGrid scenario {base_scenario_id:?} appears in multiple splits"
                    ));
                }
                for transform in &dataset.transforms {
                    validate_transform(transform)?;
                    for role_order in &dataset.role_orders {
                        validate_role_order(role_order)?;
                        for probe in &probes {
                            let task_id = format!(
                                "dungeongrid_coordination_v1:{split}:{base_scenario_id}:{transform}:{role_order}:{}",
                                probe.as_str()
                            );
                            let task = Task {
                                checkpoint_key: digest_text(&format!(
                                    "{}|{split}|{base_scenario_id}|{transform}|{role_order}|{}",
                                    dataset.dataset_id,
                                    probe.as_str()
                                )),
                                task_id: task_id.clone(),
                                split: split.clone(),
                                base_scenario_id: base_scenario_id.clone(),
                                transform: transform.clone(),
                                role_order: role_order.clone(),
                                probe: *probe,
                            };
                            if tasks.insert(task_id.clone(), task).is_some() {
                                return Err(format!("duplicate DungeonGrid task id {task_id:?}"));
                            }
                            *split_counts.entry(split.clone()).or_default() += 1;
                        }
                    }
                }
            }
        }
        Ok(Self {
            dataset_id: dataset.dataset_id,
            party_roles: dataset.party_roles,
            observation: dataset.observation,
            tasks,
            base_scenarios,
            split_counts,
        })
    }

    pub fn environment_id(&self) -> &'static str {
        ENVIRONMENT_ID
    }

    pub fn valid_roles(&self) -> Vec<String> {
        self.party_roles.clone()
    }

    pub fn split_counts(&self) -> &BTreeMap<String, usize> {
        &self.split_counts
    }

    pub fn dataset_id(&self) -> &str {
        &self.dataset_id
    }

    pub fn task_rows(&self, split: &str, task_ids: &[String]) -> Result<Vec<Value>, String> {
        validate_split(split)?;
        task_ids
            .iter()
            .map(|task_id| {
                let task = self
                    .tasks
                    .get(task_id)
                    .filter(|task| task.split == split)
                    .ok_or_else(|| {
                        format!("task id {task_id:?} is not available in requested split {split:?}")
                    })?;
                Ok(json!({
                    "task_id": task.task_id,
                    "example_id": task.task_id,
                    "split": task.split,
                    "objective": "outcome_reward",
                    "row_schema": ROW_SCHEMA,
                    "dataset_id": self.dataset_id,
                    "dataset_version": "v1",
                    "environment": ENVIRONMENT_ID,
                    "checkpoint_key": task.checkpoint_key,
                }))
            })
            .collect()
    }

    pub fn has_task(&self, task_id: &str) -> bool {
        self.tasks.contains_key(task_id)
    }

    pub fn rollout(
        &self,
        task_id: &str,
        execution: &ExecutionSpec,
    ) -> Result<EpisodeEvidence, String> {
        let task = self
            .tasks
            .get(task_id)
            .ok_or_else(|| format!("unknown DungeonGrid task id {task_id:?}"))?;
        let base = self
            .base_scenarios
            .get(&task.base_scenario_id)
            .ok_or_else(|| format!("missing base scenario {:?}", task.base_scenario_id))?;
        let scenario = variant_scenario(
            base,
            &task.transform,
            &task.role_order,
            &self.party_roles,
            &self.observation,
        )?;
        let context = prepare_probe(&scenario, task.probe)?;
        run_probe(task, &context, execution)
    }
}

fn run_probe(
    task: &Task,
    context: &ProbeContext,
    execution: &ExecutionSpec,
) -> Result<EpisodeEvidence, String> {
    let mut session =
        DungeonGridSession::restore_from_checkpoint_value(context.checkpoint.clone())?;
    let mut recorder = RunRecorder::new(&session);
    let support_role = session
        .heroes
        .get(&context.support)
        .ok_or_else(|| "checkpoint missing support hero".to_string())?
        .role
        .clone();
    let frontliner_role = session
        .heroes
        .get(&context.frontliner)
        .ok_or_else(|| "checkpoint missing frontliner hero".to_string())?
        .role
        .clone();
    let support_mode = execution.protocol.role_mode(&support_role);
    let frontliner_mode = execution.protocol.role_mode(&frontliner_role);
    let (assigned_support, assigned_frontliner) = assigned_actors(
        context,
        support_mode,
        frontliner_mode,
        execution.arm.role_permuted,
    );
    let role_duplication_count = usize::from(support_mode == RoleMode::Duplicated)
        + usize::from(frontliner_mode == RoleMode::Duplicated);
    recorder.interference_action_count += role_duplication_count;

    let intents = build_intents(
        task.probe,
        context,
        execution,
        &assigned_support,
        &assigned_frontliner,
        support_mode,
        frontliner_mode,
    )?;
    for intent in intents {
        if session.done {
            break;
        }
        execute_intent(&mut session, &mut recorder, intent, execution)?;
    }

    let events = session.event_log[recorder.event_start..].to_vec();
    record_event_contributions(&events, &mut recorder.per_agent);
    let message_events = events
        .iter()
        .filter(|event| event.kind == "message_sent")
        .collect::<Vec<_>>();
    let message_count = message_events.len();
    let message_chars = message_events
        .iter()
        .filter_map(|event| event.payload.get("text").and_then(Value::as_str))
        .map(str::chars)
        .map(Iterator::count)
        .sum();
    let invalid_action_count = events
        .iter()
        .filter(|event| event.kind == "action_rejected")
        .count();
    let hazard_count = events
        .iter()
        .filter(|event| event.kind == "trap_triggered")
        .count();
    recorder.interference_action_count += hazard_count;
    let outcome_success = outcome_success(task.probe, &events);
    let role_consistency = role_consistent(context, task.probe, &events, &session)
        && assigned_support == context.support
        && assigned_frontliner == context.frontliner;
    let message_action_alignment = !execution.arm.channel_masked
        && aligned_message(task.probe, &events)
        && recorder.masked_delivery_count == 0;
    let coordination_success = outcome_success
        && role_consistency
        && message_action_alignment
        && invalid_action_count == 0
        && recorder.interference_action_count == 0;
    let metrics = EpisodeMetrics {
        outcome_success: bool_metric(outcome_success),
        coordination_success: bool_metric(coordination_success),
        message_action_alignment: bool_metric(message_action_alignment),
        role_consistency: bool_metric(role_consistency),
        role_duplication_count,
        invalid_action_count,
        idle_action_count: recorder.idle_action_count,
        interference_action_count: recorder.interference_action_count,
        message_count,
        message_chars,
        per_agent_contribution_coverage: contribution_coverage(&recorder.per_agent),
        engine_reward: session.total_reward,
    };
    let mut failure_signals = Vec::new();
    if !outcome_success {
        failure_signals.push("load_bearing_outcome_not_reached".to_string());
    }
    if message_count == 0 {
        failure_signals.push("no_coordination_message_emitted".to_string());
    } else if !message_action_alignment {
        failure_signals.push("message_not_delivered_or_not_aligned_with_action".to_string());
    }
    if !role_consistency {
        failure_signals.push("specialist_role_sequence_inconsistent".to_string());
    }
    if invalid_action_count > 0 {
        failure_signals.push("engine_rejected_one_or_more_actions".to_string());
    }
    if execution.arm.channel_masked && message_count > 0 {
        failure_signals.push("communication_delivery_masked".to_string());
    }
    let engine_events = events
        .iter()
        .map(|event| serde_json::to_value(event).map_err(display_error))
        .collect::<Result<Vec<_>, _>>()?;
    let summary_fields = BTreeMap::from([
        ("coordination_case".to_string(), json!(task.probe)),
        (
            "scenario_variant".to_string(),
            json!(session.scenario.scenario_id),
        ),
        ("transform".to_string(), json!(task.transform)),
        ("role_order".to_string(), json!(task.role_order)),
        ("assigned_support".to_string(), json!(assigned_support)),
        (
            "assigned_frontliner".to_string(),
            json!(assigned_frontliner),
        ),
        (
            "masked_delivery_count".to_string(),
            json!(recorder.masked_delivery_count),
        ),
    ]);
    Ok(EpisodeEvidence {
        task_id: task.task_id.clone(),
        split: task.split.clone(),
        environment: ENVIRONMENT_ID.to_string(),
        checkpoint_digest: context.checkpoint_digest.clone(),
        final_state_digest: session.state_digest()?,
        metrics,
        per_agent: recorder.per_agent,
        engine_events,
        action_trace: recorder.action_trace,
        failure_signals,
        summary_fields,
    })
}

fn build_intents(
    probe: ProbeKind,
    context: &ProbeContext,
    execution: &ExecutionSpec,
    support_actor: &str,
    frontliner_actor: &str,
    support_mode: RoleMode,
    frontliner_mode: RoleMode,
) -> Result<Vec<Intent>, String> {
    let mut intents = Vec::new();
    let request_enabled = execution.protocol.request != RequestPolicy::ActionOnly
        && execution.protocol.speak != SpeakPolicy::Silent;
    let action_enabled = execution.protocol.priority == Priority::Extraction
        && execution.protocol.request != RequestPolicy::RequestOnly;
    let support_specialized = matches!(support_mode, RoleMode::Specialist | RoleMode::Duplicated);
    let frontliner_active = frontliner_mode != RoleMode::Silent;

    if request_enabled && support_mode != RoleMode::Silent {
        let message = if support_specialized {
            protocol_message(probe)
        } else {
            "STATUS HOLD; CONTINUE CAUTIOUSLY"
        };
        if execution.protocol.speak == SpeakPolicy::Always {
            intents.push(Intent {
                kind: "planning_message",
                actor: support_actor.to_string(),
                action: message_action(&truncate_chars(
                    "Planning update: coordinate before committing.",
                    execution.protocol.max_chars,
                )),
                gate_signal: None,
            });
        }
        intents.push(Intent {
            kind: "event_message",
            actor: support_actor.to_string(),
            action: message_action(&truncate_chars(message, execution.protocol.max_chars)),
            gate_signal: None,
        });
    }

    if !action_enabled {
        intents.push(Intent {
            kind: "safety_hold",
            actor: frontliner_actor.to_string(),
            action: DungeonGridAction::Guard,
            gate_signal: None,
        });
        return Ok(intents);
    }

    match probe {
        ProbeKind::PreBreach => {
            if support_specialized {
                let monster = context
                    .checkpoint
                    .pointer("/dynamic/monsters")
                    .and_then(Value::as_object)
                    .and_then(|monsters| monsters.keys().next())
                    .cloned()
                    .ok_or_else(|| "breach checkpoint has no monster".to_string())?;
                intents.push(Intent {
                    kind: "support_counterplay",
                    actor: support_actor.to_string(),
                    action: DungeonGridAction::Cast {
                        target: monster,
                        payload: SpellPayload {
                            spell: "reveal_glyph".to_string(),
                        },
                    },
                    gate_signal: None,
                });
            }
            add_follower_reply(
                &mut intents,
                frontliner_actor,
                execution.protocol.follower_reply,
                request_enabled,
                execution.protocol.max_chars,
            );
            if frontliner_active {
                intents.push(Intent {
                    kind: "breach_action",
                    actor: frontliner_actor.to_string(),
                    action: DungeonGridAction::OpenDoor {
                        target: context.target_id.clone(),
                    },
                    gate_signal: request_enabled.then_some(probe.required_signal()),
                });
            }
        }
        ProbeKind::CarrierAssignment => {
            add_follower_reply(
                &mut intents,
                frontliner_actor,
                execution.protocol.follower_reply,
                request_enabled,
                execution.protocol.max_chars,
            );
            if frontliner_active {
                intents.push(Intent {
                    kind: "carrier_action",
                    actor: frontliner_actor.to_string(),
                    action: DungeonGridAction::Interact {
                        target: "objective".to_string(),
                    },
                    gate_signal: request_enabled.then_some(probe.required_signal()),
                });
            }
        }
        ProbeKind::ExtractionHandoff => {
            if execution.protocol.handoff == HandoffPolicy::Required && support_specialized {
                intents.push(Intent {
                    kind: "objective_handoff",
                    actor: support_actor.to_string(),
                    action: DungeonGridAction::GiveItem {
                        target: frontliner_actor.to_string(),
                        payload: GiveItemPayload {
                            item: context.objective_item.clone(),
                        },
                    },
                    gate_signal: None,
                });
            }
            add_follower_reply(
                &mut intents,
                frontliner_actor,
                execution.protocol.follower_reply,
                request_enabled,
                execution.protocol.max_chars,
            );
            if frontliner_active && execution.protocol.handoff != HandoffPolicy::None {
                intents.push(Intent {
                    kind: "extraction_action",
                    actor: frontliner_actor.to_string(),
                    action: DungeonGridAction::Interact {
                        target: "escape".to_string(),
                    },
                    gate_signal: request_enabled.then_some(probe.required_signal()),
                });
            }
        }
    }
    if support_mode == RoleMode::Duplicated || frontliner_mode == RoleMode::Duplicated {
        intents.push(Intent {
            kind: "duplicated_role_action",
            actor: support_actor.to_string(),
            action: DungeonGridAction::Guard,
            gate_signal: None,
        });
    }
    Ok(intents)
}

fn assigned_actors(
    context: &ProbeContext,
    support_mode: RoleMode,
    frontliner_mode: RoleMode,
    role_permuted: bool,
) -> (String, String) {
    if role_permuted {
        return (context.frontliner.clone(), context.support.clone());
    }
    let support = match support_mode {
        RoleMode::Specialist | RoleMode::Duplicated => context.support.clone(),
        RoleMode::Flexible => "agent_0".to_string(),
        RoleMode::Silent => context.support.clone(),
    };
    let frontliner = match frontliner_mode {
        RoleMode::Specialist | RoleMode::Duplicated => context.frontliner.clone(),
        RoleMode::Flexible => "agent_1".to_string(),
        RoleMode::Silent => context.frontliner.clone(),
    };
    (support, frontliner)
}

fn add_follower_reply(
    intents: &mut Vec<Intent>,
    actor: &str,
    policy: FollowerReply,
    request_enabled: bool,
    max_chars: usize,
) {
    let should_reply = match policy {
        FollowerReply::Ack => true,
        FollowerReply::OnRequest => request_enabled,
        FollowerReply::Silent => false,
    };
    if should_reply {
        intents.push(Intent {
            kind: "follower_reply",
            actor: actor.to_string(),
            action: message_action(&truncate_chars("ACK; ROLE ASSIGNMENT RECEIVED", max_chars)),
            gate_signal: None,
        });
    }
}

fn execute_intent(
    session: &mut DungeonGridSession,
    recorder: &mut RunRecorder,
    intent: Intent,
    execution: &ExecutionSpec,
) -> Result<(), String> {
    align_turn(
        session,
        recorder,
        &intent.actor,
        required_ap(&intent.action),
        execution,
    )?;
    let mut action = intent.action;
    if let Some(signal) = intent.gate_signal {
        let delivered = session
            .message_inboxes
            .get(&intent.actor)
            .is_some_and(|messages| {
                messages
                    .iter()
                    .any(|message| message.text.to_ascii_uppercase().contains(signal))
            });
        if !delivered {
            action = DungeonGridAction::Guard;
            recorder.interference_action_count += 1;
        }
    }
    execute_action(session, recorder, intent.kind, action, execution)
}

fn align_turn(
    session: &mut DungeonGridSession,
    recorder: &mut RunRecorder,
    actor: &str,
    required_ap: i32,
    execution: &ExecutionSpec,
) -> Result<(), String> {
    let party_size = session.turn_order.len();
    if !session.heroes.contains_key(actor) {
        return Err(format!("assigned actor {actor:?} is not in checkpoint"));
    }
    let needs_refresh = session.active_agent == actor
        && session
            .heroes
            .get(actor)
            .is_some_and(|hero| hero.ap < required_ap);
    if needs_refresh {
        execute_action(
            session,
            recorder,
            "turn_refresh",
            DungeonGridAction::EndTurn,
            execution,
        )?;
    }
    let mut advances = 0usize;
    while session.active_agent != actor {
        if advances > party_size {
            return Err(format!(
                "could not advance turn to assigned actor {actor:?}"
            ));
        }
        execute_action(
            session,
            recorder,
            "turn_alignment",
            DungeonGridAction::EndTurn,
            execution,
        )?;
        advances += 1;
    }
    Ok(())
}

fn execute_action(
    session: &mut DungeonGridSession,
    recorder: &mut RunRecorder,
    kind: &str,
    action: DungeonGridAction,
    execution: &ExecutionSpec,
) -> Result<(), String> {
    let actor = session.active_agent.clone();
    let before_event = session.event_log.len();
    let before_inboxes = session
        .message_inboxes
        .iter()
        .map(|(agent_id, messages)| (agent_id.clone(), messages.len()))
        .collect::<BTreeMap<_, _>>();
    let serialized_action = serde_json::to_value(&action).map_err(display_error)?;
    let is_message = matches!(action, DungeonGridAction::Message { .. });
    let is_idle = matches!(
        action,
        DungeonGridAction::EndTurn | DungeonGridAction::Guard
    );
    let result = session.step(action);
    let contribution = recorder
        .per_agent
        .get_mut(&actor)
        .ok_or_else(|| format!("missing contribution row for {actor}"))?;
    contribution.generated_actions += 1;
    if result.applied {
        contribution.applied_actions += 1;
    }
    contribution.reward += result.reward;
    if is_message {
        contribution.messages_sent += 1;
    }
    if is_idle {
        recorder.idle_action_count += 1;
    }
    let mut delivery_dropped_for = Vec::new();
    if is_message && execution.arm.channel_masked {
        for (agent_id, messages) in &mut session.message_inboxes {
            let previous = before_inboxes.get(agent_id).copied().unwrap_or_default();
            if messages.len() > previous {
                messages.truncate(previous);
                delivery_dropped_for.push(agent_id.clone());
            }
        }
        recorder.masked_delivery_count += delivery_dropped_for.len();
    }
    let events = session.event_log[before_event..]
        .iter()
        .map(|event| serde_json::to_value(event).map_err(display_error))
        .collect::<Result<Vec<_>, _>>()?;
    recorder.action_trace.push(json!({
        "index": recorder.action_trace.len(),
        "kind": kind,
        "actor": actor,
        "action": serialized_action,
        "applied": result.applied,
        "reward": result.reward,
        "delivery_dropped_for": delivery_dropped_for,
        "engine_events": events,
    }));
    Ok(())
}

fn required_ap(action: &DungeonGridAction) -> i32 {
    match action {
        DungeonGridAction::EndTurn => 0,
        DungeonGridAction::InspectTile { .. }
        | DungeonGridAction::SearchTraps
        | DungeonGridAction::AttackMelee { .. }
        | DungeonGridAction::Cast { .. } => 2,
        _ => 1,
    }
}

fn protocol_message(probe: ProbeKind) -> &'static str {
    match probe {
        ProbeKind::PreBreach => "BREACH HOLD; WIZARD REVEAL; BARBARIAN OPEN",
        ProbeKind::CarrierAssignment => "CARRIER BARBARIAN; TAKE OBJECTIVE; SUPPORT HOLD",
        ProbeKind::ExtractionHandoff => "HANDOFF OBJECTIVE; EXTRACT BARBARIAN",
    }
}

fn message_action(text: &str) -> DungeonGridAction {
    DungeonGridAction::Message {
        target: "party".to_string(),
        payload: MessagePayload {
            text: text.to_string(),
        },
    }
}

fn truncate_chars(text: &str, max_chars: usize) -> String {
    text.chars().take(max_chars).collect()
}

fn outcome_success(probe: ProbeKind, events: &[EventRecord]) -> bool {
    let event_kind = match probe {
        ProbeKind::PreBreach => "door_opened",
        ProbeKind::CarrierAssignment => "objective_taken",
        ProbeKind::ExtractionHandoff => "objective_escaped",
    };
    events.iter().any(|event| event.kind == event_kind)
}

fn role_consistent(
    context: &ProbeContext,
    probe: ProbeKind,
    events: &[EventRecord],
    session: &DungeonGridSession,
) -> bool {
    match probe {
        ProbeKind::PreBreach => {
            event_agent(events, "counterplay_revealed") == Some(&context.support)
                && event_agent(events, "door_opened") == Some(&context.frontliner)
        }
        ProbeKind::CarrierAssignment => {
            event_agent(events, "objective_taken") == Some(&context.frontliner)
                && session
                    .heroes
                    .get(&context.frontliner)
                    .is_some_and(|hero| hero.inventory.contains(&context.objective_item))
        }
        ProbeKind::ExtractionHandoff => {
            event_agent(events, "item_given") == Some(&context.support)
                && event_agent(events, "objective_escaped") == Some(&context.frontliner)
        }
    }
}

fn aligned_message(probe: ProbeKind, events: &[EventRecord]) -> bool {
    let action_kind = match probe {
        ProbeKind::PreBreach => "counterplay_revealed",
        ProbeKind::CarrierAssignment => "objective_taken",
        ProbeKind::ExtractionHandoff => "item_given",
    };
    let Some(action_index) = events.iter().position(|event| event.kind == action_kind) else {
        return false;
    };
    events[..action_index].iter().any(|event| {
        event.kind == "message_sent"
            && event
                .payload
                .get("text")
                .and_then(Value::as_str)
                .is_some_and(|text| {
                    let text = text.to_ascii_uppercase();
                    match probe {
                        ProbeKind::PreBreach => text.contains("BREACH") && text.contains("REVEAL"),
                        ProbeKind::CarrierAssignment => {
                            text.contains("CARRIER") && text.contains("BARBARIAN")
                        }
                        ProbeKind::ExtractionHandoff => {
                            text.contains("HANDOFF") && text.contains("EXTRACT")
                        }
                    }
                })
    })
}

fn event_agent<'a>(events: &'a [EventRecord], kind: &str) -> Option<&'a String> {
    events
        .iter()
        .find(|event| event.kind == kind)
        .map(|event| &event.agent_id)
}

fn record_event_contributions(
    events: &[EventRecord],
    contributions: &mut BTreeMap<String, AgentContribution>,
) {
    let successful = [
        "counterplay_revealed",
        "door_opened",
        "objective_taken",
        "item_given",
        "objective_escaped",
    ];
    for event in events {
        if let Some(contribution) = contributions.get_mut(&event.agent_id) {
            contribution.engine_events += 1;
            if successful.contains(&event.kind.as_str()) {
                contribution.successful_contributions += 1;
            }
        }
    }
}

fn variant_scenario(
    base: &Scenario,
    transform: &str,
    role_order: &str,
    party_roles: &[String],
    observation: &ObservationConfig,
) -> Result<Scenario, String> {
    let mut scenario = base.clone();
    scenario.map_ascii = transform_map(&base.map_ascii, transform)?;
    scenario.hero_roles = party_roles.to_vec();
    scenario.observation = observation.clone();
    match role_order {
        "original" => {}
        "swapped" => scenario.hero_roles.swap(0, 1),
        other => return Err(format!("unsupported DungeonGrid role order {other:?}")),
    }
    scenario.scenario_id = format!("{}__{}__{}", base.scenario_id, transform, role_order);
    scenario.task_id = format!("{}__{}__{}", base.task_id, transform, role_order);
    scenario.seed = stable_seed(&scenario.scenario_id);
    scenario.metadata.insert(
        "mapo_dataset_variant".to_string(),
        json!({
            "base_scenario_id": base.scenario_id,
            "transform": transform,
            "role_order": role_order,
        }),
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
        other => return Err(format!("unsupported DungeonGrid map transform {other:?}")),
    }
    Ok(rows
        .into_iter()
        .map(|row| row.into_iter().collect::<String>())
        .collect::<Vec<_>>()
        .join("\n"))
}

fn prepare_probe(scenario: &Scenario, probe: ProbeKind) -> Result<ProbeContext, String> {
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
    let target_id = match probe {
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
            "DungeonGrid checkpoint restore changed {} {}",
            scenario.scenario_id,
            probe.as_str()
        ));
    }
    Ok(ProbeContext {
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
                "scenario {} has no breach staging tile",
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
    clear_encounter(session);
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
    remove_objective_from_party(session);
    Ok("objective".to_string())
}

fn prepare_extraction_handoff(
    session: &mut DungeonGridSession,
    frontliner: &str,
    support: &str,
) -> Result<String, String> {
    clear_encounter(session);
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
    remove_objective_from_party(session);
    session
        .heroes
        .get_mut(support)
        .expect("support exists")
        .inventory
        .push(session.scenario.objective_item.clone());
    Ok("escape".to_string())
}

fn clear_encounter(session: &mut DungeonGridSession) {
    for door in session.doors.values_mut() {
        door.open = true;
        door.discovered = true;
    }
    for monster in session.monsters.values_mut() {
        monster.hp = 0;
    }
}

fn remove_objective_from_party(session: &mut DungeonGridSession) {
    for hero in session.heroes.values_mut() {
        hero.inventory
            .retain(|item| item != &session.scenario.objective_item);
    }
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

fn validate_split(split: &str) -> Result<(), String> {
    if matches!(split, "train" | "selection" | "heldout") {
        Ok(())
    } else {
        Err(format!("unsupported task split {split:?}"))
    }
}

fn validate_transform(transform: &str) -> Result<(), String> {
    if matches!(
        transform,
        "identity" | "mirror_x" | "mirror_y" | "rotate_180"
    ) {
        Ok(())
    } else {
        Err(format!("unsupported DungeonGrid transform {transform:?}"))
    }
}

fn validate_role_order(role_order: &str) -> Result<(), String> {
    if matches!(role_order, "original" | "swapped") {
        Ok(())
    } else {
        Err(format!("unsupported DungeonGrid role order {role_order:?}"))
    }
}

fn stable_seed(value: &str) -> i64 {
    let digest = Sha256::digest(value.as_bytes());
    i64::from_be_bytes(digest[..8].try_into().expect("sha256 has eight bytes")) & i64::MAX
}

fn digest_text(text: &str) -> String {
    let digest = Sha256::digest(text.as_bytes());
    format!("sha256:{digest:x}")
}

fn digest_json(value: &Value) -> Result<String, String> {
    let bytes = serde_json::to_vec(value).map_err(display_error)?;
    let digest = Sha256::digest(bytes);
    Ok(format!("sha256:{digest:x}"))
}

fn bool_metric(value: bool) -> f64 {
    if value {
        1.0
    } else {
        0.0
    }
}

fn display_error(error: impl std::fmt::Display) -> String {
    error.to_string()
}
