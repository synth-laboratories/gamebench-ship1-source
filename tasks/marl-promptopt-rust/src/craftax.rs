use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use craftax_coop_gamebench::{CraftaxCoopEnv, Event, Player};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::model::{
    contribution_coverage, public_split, validate_public_split, AgentContribution, EpisodeEvidence,
    EpisodeMetrics, ExecutionSpec, ROW_SCHEMA,
};
use crate::protocol::{
    FollowerReply, HandoffPolicy, Priority, RequestPolicy, RoleMode, SpeakPolicy,
};

const ENVIRONMENT_ID: &str = "craftax-multiplayer";
const DATASET_SCHEMA: &str = "gamebench.mapo_coordination_dataset.v1";

#[derive(Debug, Deserialize)]
struct DatasetConfig {
    schema: String,
    dataset_id: String,
    agent_count: usize,
    max_timesteps: u64,
    probes: Vec<String>,
    splits: BTreeMap<String, SeedRange>,
}

#[derive(Clone, Debug, Deserialize)]
struct SeedRange {
    start: u64,
    count: u64,
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
            other => Err(format!("unsupported Craftax coordination probe {other:?}")),
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

    fn expected_trades(self) -> usize {
        if self == Self::MinerCraftPipeline {
            2
        } else {
            1
        }
    }
}

#[derive(Clone, Debug)]
struct Task {
    task_id: String,
    split: String,
    seed: u64,
    probe: ProbeKind,
    checkpoint_key: String,
}

#[derive(Clone, Debug)]
struct ProbeContext {
    checkpoint: String,
    checkpoint_digest: String,
    expected_resource: &'static str,
    giver: &'static str,
    recipient: &'static str,
}

#[derive(Clone, Debug)]
struct PlannedStep {
    kind: &'static str,
    generated: BTreeMap<String, String>,
}

pub struct CraftaxBackend {
    dataset_id: String,
    max_timesteps: u64,
    tasks: BTreeMap<String, Task>,
    split_counts: BTreeMap<String, usize>,
}

impl CraftaxBackend {
    pub fn load(tasks_root: &Path) -> Result<Self, String> {
        let path =
            tasks_root.join("craftax-multiplayer/defaults/mapo_coordination/dataset_v1.json");
        let text = fs::read_to_string(&path)
            .map_err(|error| format!("read {}: {error}", path.display()))?;
        let dataset: DatasetConfig = serde_json::from_str(&text)
            .map_err(|error| format!("parse {}: {error}", path.display()))?;
        if dataset.schema != DATASET_SCHEMA {
            return Err(format!(
                "unsupported Craftax dataset schema {:?}",
                dataset.schema
            ));
        }
        if dataset.agent_count != 3 {
            return Err("Craftax prompt optimizer requires exactly three agents".to_string());
        }
        let probes = dataset
            .probes
            .iter()
            .map(|value| ProbeKind::parse(value))
            .collect::<Result<Vec<_>, _>>()?;
        let mut tasks = BTreeMap::new();
        let mut split_counts = BTreeMap::new();
        let mut seeds = BTreeSet::new();
        for (split, range) in &dataset.splits {
            validate_split(split)?;
            for seed in range.start..range.start + range.count {
                if !seeds.insert(seed) {
                    return Err(format!("Craftax seed {seed} appears in multiple splits"));
                }
                for probe in &probes {
                    let task_id =
                        format!("craftax_coordination_v1:{split}:{seed}:{}", probe.as_str());
                    let task = Task {
                        checkpoint_key: digest_text(&format!(
                            "{}|{split}|{seed}|{}",
                            dataset.dataset_id,
                            probe.as_str()
                        )),
                        task_id: task_id.clone(),
                        split: split.clone(),
                        seed,
                        probe: *probe,
                    };
                    if tasks.insert(task_id.clone(), task).is_some() {
                        return Err(format!("duplicate Craftax task id {task_id:?}"));
                    }
                    *split_counts.entry(split.clone()).or_default() += 1;
                }
            }
        }
        Ok(Self {
            dataset_id: dataset.dataset_id,
            max_timesteps: dataset.max_timesteps,
            tasks,
            split_counts,
        })
    }

    pub fn environment_id(&self) -> &'static str {
        ENVIRONMENT_ID
    }

    pub fn valid_roles(&self) -> Vec<String> {
        ["warrior", "forager", "miner"]
            .into_iter()
            .map(str::to_string)
            .collect()
    }

    pub fn task_roles(&self, task_id: &str) -> Option<Vec<String>> {
        self.tasks.contains_key(task_id).then(|| self.valid_roles())
    }

    pub fn split_counts(&self) -> &BTreeMap<String, usize> {
        &self.split_counts
    }

    pub fn dataset_id(&self) -> &str {
        &self.dataset_id
    }

    pub fn task_rows(&self, split: &str, task_ids: &[String]) -> Result<Vec<Value>, String> {
        validate_public_split(split)?;
        task_ids
            .iter()
            .map(|task_id| {
                let task = self
                    .tasks
                    .get(task_id)
                    .filter(|task| public_split(&task.split) == Some(split))
                    .ok_or_else(|| {
                        format!("task id {task_id:?} is not available in requested split {split:?}")
                    })?;
                Ok(json!({
                    "task_id": task.task_id,
                    "example_id": task.task_id,
                    "split": split,
                    "dataset_split": task.split,
                    "objective": "outcome_reward",
                    "row_schema": ROW_SCHEMA,
                    "dataset_id": self.dataset_id,
                    "dataset_version": "v1",
                    "environment": ENVIRONMENT_ID,
                    "checkpoint_key": task.checkpoint_key,
                    "roles": self.valid_roles(),
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
            .ok_or_else(|| format!("unknown Craftax task id {task_id:?}"))?;
        let context = prepare_probe(task.seed, self.max_timesteps, task.probe)?;
        run_probe(task, &context, execution)
    }
}

fn prepare_probe(seed: u64, max_timesteps: u64, kind: ProbeKind) -> Result<ProbeContext, String> {
    let mut env = CraftaxCoopEnv::reset(seed, 3, max_timesteps);
    reset_resources(&mut env);
    let (resource, giver, recipient) = match kind {
        ProbeKind::IronHandoff => {
            *inventory_mut(player_mut(&mut env, "agent_0")?, "iron")? = 1;
            ("iron", "agent_0", "agent_2")
        }
        ProbeKind::FoodRescue => {
            player_mut(&mut env, "agent_0")?.food = 1;
            player_mut(&mut env, "agent_1")?.food = 9;
            ("food", "agent_1", "agent_0")
        }
        ProbeKind::MinerCraftPipeline => {
            *inventory_mut(player_mut(&mut env, "agent_0")?, "iron")? = 2;
            player_mut(&mut env, "agent_2")?.pickaxe = 0;
            ("iron", "agent_0", "agent_2")
        }
        ProbeKind::ExpiringRequestRepair => {
            *inventory_mut(player_mut(&mut env, "agent_0")?, "iron")? = 1;
            let recipient = player_mut(&mut env, "agent_2")?;
            recipient.request_type = Some("iron".to_string());
            recipient.request_duration = 1;
            ("iron", "agent_0", "agent_2")
        }
    };
    let checkpoint = env.checkpoint_json();
    let restored = CraftaxCoopEnv::restore_json(&checkpoint).map_err(display_error)?;
    if restored.state != env.state {
        return Err(format!(
            "Craftax checkpoint restore changed {} seed {seed}",
            kind.as_str()
        ));
    }
    Ok(ProbeContext {
        checkpoint_digest: digest_text(&checkpoint),
        checkpoint,
        expected_resource: resource,
        giver,
        recipient,
    })
}

fn run_probe(
    task: &Task,
    context: &ProbeContext,
    execution: &ExecutionSpec,
) -> Result<EpisodeEvidence, String> {
    let mut env = CraftaxCoopEnv::restore_json(&context.checkpoint).map_err(display_error)?;
    let giver_role = player(&env, context.giver)?.role.clone();
    let recipient_role = player(&env, context.recipient)?.role.clone();
    let giver_mode = execution.protocol.role_mode(&giver_role);
    let recipient_mode = execution.protocol.role_mode(&recipient_role);
    let (assigned_giver, assigned_recipient) = assigned_agents(
        context,
        giver_mode,
        recipient_mode,
        execution.arm.role_permuted,
    );
    let role_duplication_count = usize::from(giver_mode == RoleMode::Duplicated)
        + usize::from(recipient_mode == RoleMode::Duplicated);
    let plans = plan_steps(
        task.probe,
        context,
        execution,
        assigned_giver.as_deref(),
        assigned_recipient.as_deref(),
        giver_mode,
        recipient_mode,
    );

    let initial_trade_count = env.state.trade_count;
    let mut invalid_action_count = 0usize;
    let mut idle_action_count = 0usize;
    let mut message_count = 0usize;
    let mut message_chars = 0usize;
    let mut generated_give_count = 0usize;
    let mut action_trace = Vec::new();
    let mut engine_events = Vec::new();
    let mut per_agent = env
        .state
        .players
        .iter()
        .map(|player| (player.agent_id.clone(), AgentContribution::default()))
        .collect::<BTreeMap<_, _>>();

    for (index, plan) in plans.into_iter().enumerate() {
        let mut applied = plan.generated.clone();
        for (agent_id, action) in &plan.generated {
            let contribution = per_agent
                .get_mut(agent_id)
                .ok_or_else(|| format!("missing contribution row for {agent_id}"))?;
            if action != "noop" {
                contribution.generated_actions += 1;
            }
            if action.starts_with("request_") {
                message_count += 1;
                message_chars += action.chars().count();
                contribution.messages_sent += 1;
                if action.chars().count() > execution.protocol.max_chars {
                    applied.insert(agent_id.clone(), "noop".to_string());
                    invalid_action_count += 1;
                }
            }
            if action.starts_with("give_") {
                generated_give_count += 1;
            }
        }
        for (agent_id, action) in applied.clone() {
            if !env.legal_actions(&agent_id).contains(&action) {
                applied.insert(agent_id, "noop".to_string());
                invalid_action_count += 1;
            }
        }
        for (agent_id, action) in &applied {
            let contribution = per_agent
                .get_mut(agent_id)
                .ok_or_else(|| format!("missing contribution row for {agent_id}"))?;
            if action == "noop" {
                idle_action_count += 1;
            } else {
                contribution.applied_actions += 1;
            }
        }
        let result = env.step(&applied)?;
        for (agent_id, reward) in &result.rewards {
            if let Some(contribution) = per_agent.get_mut(agent_id) {
                contribution.reward += *reward;
            }
        }
        record_craftax_events(&result.events, &mut per_agent);
        let serialized_events = result
            .events
            .iter()
            .map(|event| serde_json::to_value(event).map_err(display_error))
            .collect::<Result<Vec<_>, _>>()?;
        engine_events.extend(serialized_events.clone());

        let mut delivery_dropped = Vec::new();
        if execution.arm.channel_masked {
            for (agent_id, action) in &plan.generated {
                if action.starts_with("request_") {
                    let player = player_mut(&mut env, agent_id)?;
                    player.request_type = None;
                    player.request_duration = 0;
                    delivery_dropped.push(agent_id.clone());
                }
            }
        }
        action_trace.push(json!({
            "index": index,
            "kind": plan.kind,
            "generated_joint_action": plan.generated,
            "applied_joint_action": applied,
            "delivery_dropped_for": delivery_dropped,
            "engine_events": serialized_events,
            "engine_rewards": result.rewards,
            "trade_count": env.state.trade_count,
            "requests": request_snapshot(&env),
        }));
    }

    let successful_trades = (env.state.trade_count - initial_trade_count) as usize;
    let outcome_success = probe_outcome(task.probe, context, &env, successful_trades)?;
    let message_action_alignment = aligned_request_and_trade(&engine_events, context);
    let role_consistency = trade_roles_consistent(&engine_events, context)
        && assigned_giver.as_deref() == Some(context.giver)
        && assigned_recipient.as_deref() == Some(context.recipient);
    let failed_give_count = generated_give_count.saturating_sub(successful_trades);
    let interference_action_count = failed_give_count + role_duplication_count;
    let coordination_success = outcome_success
        && message_action_alignment
        && role_consistency
        && invalid_action_count == 0
        && interference_action_count == 0;
    let coverage = contribution_coverage(&per_agent);
    let metrics = EpisodeMetrics {
        outcome_success: bool_metric(outcome_success),
        coordination_success: bool_metric(coordination_success),
        message_action_alignment: bool_metric(message_action_alignment),
        role_consistency: bool_metric(role_consistency),
        role_duplication_count,
        invalid_action_count,
        idle_action_count,
        interference_action_count,
        message_count,
        message_chars,
        per_agent_contribution_coverage: coverage,
        engine_reward: per_agent.values().map(|entry| entry.reward).sum(),
    };
    let mut failure_signals = Vec::new();
    if !outcome_success {
        failure_signals.push("delivery_or_craft_outcome_not_reached".to_string());
    }
    if message_count == 0 {
        failure_signals.push("no_grounded_request_emitted".to_string());
    } else if !message_action_alignment {
        failure_signals.push("request_not_aligned_with_successful_handoff".to_string());
    }
    if !role_consistency {
        failure_signals.push("role_assignment_inconsistent_with_engine_events".to_string());
    }
    if execution.arm.channel_masked && message_count > 0 {
        failure_signals.push("communication_delivery_masked".to_string());
    }
    let summary_fields = BTreeMap::from([
        ("coordination_case".to_string(), json!(task.probe)),
        ("dataset_split".to_string(), json!(task.split)),
        ("seed".to_string(), json!(task.seed)),
        (
            "successful_trade_count".to_string(),
            json!(successful_trades),
        ),
        (
            "expected_trade_count".to_string(),
            json!(task.probe.expected_trades()),
        ),
        ("assigned_giver".to_string(), json!(assigned_giver)),
        ("assigned_recipient".to_string(), json!(assigned_recipient)),
    ]);
    Ok(EpisodeEvidence {
        task_id: task.task_id.clone(),
        split: public_split(&task.split)
            .ok_or_else(|| format!("invalid Craftax dataset split {:?}", task.split))?
            .to_string(),
        environment: ENVIRONMENT_ID.to_string(),
        checkpoint_digest: context.checkpoint_digest.clone(),
        final_state_digest: digest_text(&env.checkpoint_json()),
        metrics,
        per_agent,
        engine_events,
        action_trace,
        failure_signals,
        summary_fields,
    })
}

fn assigned_agents(
    context: &ProbeContext,
    giver_mode: RoleMode,
    recipient_mode: RoleMode,
    role_permuted: bool,
) -> (Option<String>, Option<String>) {
    if role_permuted {
        return (
            Some(context.recipient.to_string()),
            Some(context.giver.to_string()),
        );
    }
    let giver = match giver_mode {
        RoleMode::Specialist | RoleMode::Duplicated => Some(context.giver.to_string()),
        RoleMode::Flexible => Some("agent_0".to_string()),
        RoleMode::Silent => None,
    };
    let recipient = match recipient_mode {
        RoleMode::Specialist | RoleMode::Duplicated => Some(context.recipient.to_string()),
        RoleMode::Flexible => Some("agent_1".to_string()),
        RoleMode::Silent => None,
    };
    (giver, recipient)
}

fn plan_steps(
    probe: ProbeKind,
    context: &ProbeContext,
    execution: &ExecutionSpec,
    assigned_giver: Option<&str>,
    assigned_recipient: Option<&str>,
    giver_mode: RoleMode,
    recipient_mode: RoleMode,
) -> Vec<PlannedStep> {
    let mut plans = Vec::new();
    let request_enabled = execution.protocol.request != RequestPolicy::ActionOnly
        && execution.protocol.speak != SpeakPolicy::Silent;
    let action_enabled = execution.protocol.priority == Priority::Delivery
        && execution.protocol.request != RequestPolicy::RequestOnly
        && execution.protocol.handoff != HandoffPolicy::None
        && (execution.protocol.handoff != HandoffPolicy::Required || request_enabled);
    for _ in 0..probe.expected_trades() {
        if request_enabled {
            let mut actions = noop_joint();
            if recipient_mode == RoleMode::Duplicated
                || execution.protocol.speak == SpeakPolicy::Always
            {
                for action in actions.values_mut() {
                    *action = format!("request_{}", context.expected_resource);
                }
            } else if let Some(recipient) = assigned_recipient {
                actions.insert(
                    recipient.to_string(),
                    format!("request_{}", context.expected_resource),
                );
                add_follower_replies(
                    &mut actions,
                    recipient,
                    context.expected_resource,
                    execution.protocol.follower_reply,
                );
            }
            plans.push(PlannedStep {
                kind: "request",
                generated: actions,
            });
        }
        if action_enabled {
            let mut actions = noop_joint();
            let Some(recipient) = assigned_recipient else {
                plans.push(PlannedStep {
                    kind: "handoff",
                    generated: actions,
                });
                continue;
            };
            let give = format!("give_{}_to_{recipient}", context.expected_resource);
            if giver_mode == RoleMode::Duplicated {
                for (agent_id, action) in &mut actions {
                    if agent_id != recipient {
                        *action = give.clone();
                    }
                }
            } else if let Some(giver) = assigned_giver {
                if giver != recipient {
                    actions.insert(giver.to_string(), give);
                }
            }
            plans.push(PlannedStep {
                kind: "handoff",
                generated: actions,
            });
        }
    }
    if probe == ProbeKind::MinerCraftPipeline && action_enabled {
        let mut actions = noop_joint();
        if let Some(recipient) = assigned_recipient {
            actions.insert(recipient.to_string(), "make_iron_pickaxe".to_string());
        }
        plans.push(PlannedStep {
            kind: "craft",
            generated: actions,
        });
    }
    if plans.is_empty() {
        plans.push(PlannedStep {
            kind: "idle",
            generated: noop_joint(),
        });
    }
    plans
}

fn add_follower_replies(
    actions: &mut BTreeMap<String, String>,
    requester: &str,
    resource: &str,
    policy: FollowerReply,
) {
    let followers = actions
        .keys()
        .filter(|agent_id| agent_id.as_str() != requester)
        .cloned()
        .collect::<Vec<_>>();
    match policy {
        FollowerReply::Silent => {}
        FollowerReply::OnRequest => {
            if let Some(follower) = followers.first() {
                actions.insert(follower.clone(), format!("request_{resource}"));
            }
        }
        FollowerReply::Ack => {
            for follower in followers {
                actions.insert(follower, format!("request_{resource}"));
            }
        }
    }
}

fn aligned_request_and_trade(events: &[Value], context: &ProbeContext) -> bool {
    let mut request_seen = false;
    for event in events {
        match event.get("kind").and_then(Value::as_str) {
            Some("request_made") => {
                request_seen |= event.pointer("/agent_id").and_then(Value::as_str)
                    == Some(context.recipient)
                    && event.pointer("/resource").and_then(Value::as_str)
                        == Some(context.expected_resource);
            }
            Some("trade_applied") if request_seen => {
                if event.pointer("/receiver").and_then(Value::as_str) == Some(context.recipient)
                    && event.pointer("/resource").and_then(Value::as_str)
                        == Some(context.expected_resource)
                {
                    return true;
                }
            }
            _ => {}
        }
    }
    false
}

fn trade_roles_consistent(events: &[Value], context: &ProbeContext) -> bool {
    let trades = events
        .iter()
        .filter(|event| event.get("kind").and_then(Value::as_str) == Some("trade_applied"))
        .collect::<Vec<_>>();
    !trades.is_empty()
        && trades.iter().all(|event| {
            event.pointer("/giver").and_then(Value::as_str) == Some(context.giver)
                && event.pointer("/receiver").and_then(Value::as_str) == Some(context.recipient)
                && event.pointer("/resource").and_then(Value::as_str)
                    == Some(context.expected_resource)
        })
}

fn record_craftax_events(
    events: &[Event],
    contributions: &mut BTreeMap<String, AgentContribution>,
) {
    for event in events {
        if let Some(agent_id) = event.fields.get("agent_id").and_then(Value::as_str) {
            if let Some(contribution) = contributions.get_mut(agent_id) {
                contribution.engine_events += 1;
            }
        }
        if event.kind == "trade_applied" {
            for key in ["giver", "receiver"] {
                if let Some(agent_id) = event.fields.get(key).and_then(Value::as_str) {
                    if let Some(contribution) = contributions.get_mut(agent_id) {
                        contribution.successful_contributions += 1;
                    }
                }
            }
        }
    }
}

fn probe_outcome(
    probe: ProbeKind,
    context: &ProbeContext,
    env: &CraftaxCoopEnv,
    trades: usize,
) -> Result<bool, String> {
    let recipient = player(env, context.recipient)?;
    let reached = match probe {
        ProbeKind::FoodRescue => recipient.food >= 2,
        ProbeKind::MinerCraftPipeline => recipient.pickaxe >= 3,
        ProbeKind::IronHandoff | ProbeKind::ExpiringRequestRepair => {
            recipient.inventory[context.expected_resource] >= 1
        }
    };
    Ok(trades >= probe.expected_trades() && reached)
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
        .ok_or_else(|| format!("missing Craftax player {agent_id}"))
}

fn player<'a>(env: &'a CraftaxCoopEnv, agent_id: &str) -> Result<&'a Player, String> {
    env.state
        .players
        .iter()
        .find(|player| player.agent_id == agent_id)
        .ok_or_else(|| format!("missing Craftax player {agent_id}"))
}

fn inventory_mut<'a>(player: &'a mut Player, resource: &str) -> Result<&'a mut u16, String> {
    player
        .inventory
        .get_mut(resource)
        .ok_or_else(|| format!("{} missing resource {resource}", player.agent_id))
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

fn noop_joint() -> BTreeMap<String, String> {
    BTreeMap::from([
        ("agent_0".to_string(), "noop".to_string()),
        ("agent_1".to_string(), "noop".to_string()),
        ("agent_2".to_string(), "noop".to_string()),
    ])
}

fn validate_split(split: &str) -> Result<(), String> {
    if matches!(split, "train" | "selection" | "heldout") {
        Ok(())
    } else {
        Err(format!("unsupported task split {split:?}"))
    }
}

fn digest_text(text: &str) -> String {
    let digest = Sha256::digest(text.as_bytes());
    format!("sha256:{digest:x}")
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
