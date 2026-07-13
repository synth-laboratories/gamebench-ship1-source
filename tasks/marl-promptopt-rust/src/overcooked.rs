use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fs;
use std::path::{Path, PathBuf};

use overcooked_v2_gold::{
    Action, Direction, EventRecord, JointAction, OvercookedV2Env, Position, RuntimeMetrics,
};
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

const ENVIRONMENT_ID: &str = "overcooked-v2-multiplayer";
const DATASET_SCHEMA: &str = "gamebench.mapo_promptopt_dataset.v1";

#[derive(Debug, Deserialize)]
struct DatasetConfig {
    schema: String,
    dataset_id: String,
    probe_rules: BTreeMap<String, Value>,
    splits: BTreeMap<String, Vec<TemplateRow>>,
}

#[derive(Clone, Debug, Deserialize)]
struct TemplateRow {
    row_id: String,
    layout_family: String,
    seed: u64,
    probe: String,
    layout: Value,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum ProbeKind {
    HiddenRecipeReveal,
    IngredientCookRoleAssignment,
    DeliveryHandoff,
}

impl ProbeKind {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "hidden_recipe_reveal" => Ok(Self::HiddenRecipeReveal),
            "ingredient_cook_role_assignment" => Ok(Self::IngredientCookRoleAssignment),
            "delivery_handoff" => Ok(Self::DeliveryHandoff),
            other => Err(format!("unsupported Overcooked MAPO probe {other:?}")),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::HiddenRecipeReveal => "hidden_recipe_reveal",
            Self::IngredientCookRoleAssignment => "ingredient_cook_role_assignment",
            Self::DeliveryHandoff => "delivery_handoff",
        }
    }

    fn critical_roles(self) -> &'static [&'static str] {
        match self {
            Self::HiddenRecipeReveal => &["cook", "ingredient_0"],
            Self::IngredientCookRoleAssignment => &["ingredient_0", "ingredient_1", "cook"],
            Self::DeliveryHandoff => &["cook", "delivery"],
        }
    }
}

#[derive(Clone, Debug)]
struct Task {
    task_id: String,
    dataset_split: String,
    template_row_id: String,
    layout_family: String,
    template_seed: u64,
    seed: u64,
    replica_index: usize,
    probe: ProbeKind,
    layout: Value,
    rules: Value,
    roles: Vec<String>,
    checkpoint_key: String,
}

struct ProbeContext {
    checkpoint: String,
    checkpoint_digest: String,
    checkpoint_state_digest: String,
}

#[derive(Clone, Copy)]
enum GroundedSignal {
    Button,
    PotState,
    CounterHandoff,
}

impl GroundedSignal {
    fn label(self) -> &'static str {
        match self {
            Self::Button => "recipe_button",
            Self::PotState => "pot_state",
            Self::CounterHandoff => "counter_handoff",
        }
    }

    fn matches(self, event: &EventRecord) -> bool {
        match self {
            Self::Button => event.message.starts_with("ButtonActivated("),
            Self::PotState => event.message.starts_with("PotIngredientAdded("),
            Self::CounterHandoff => {
                event.message.starts_with("ItemPicked(") && event.message.contains(",counter)")
            }
        }
    }
}

struct RunRecorder {
    action_trace: Vec<Value>,
    events: Vec<EventRecord>,
    per_agent: BTreeMap<String, AgentContribution>,
    idle_action_count: usize,
    interference_action_count: usize,
    grounded_signal_count: usize,
    masked_delivery_count: usize,
}

impl RunRecorder {
    fn new(environment: &OvercookedV2Env) -> Self {
        Self {
            action_trace: Vec::new(),
            events: Vec::new(),
            per_agent: environment
                .resolved()
                .agent_ids
                .iter()
                .cloned()
                .map(|agent_id| (agent_id, AgentContribution::default()))
                .collect(),
            idle_action_count: 0,
            interference_action_count: 0,
            grounded_signal_count: 0,
            masked_delivery_count: 0,
        }
    }
}

pub struct OvercookedBackend {
    dataset_id: String,
    defaults_dir: PathBuf,
    tasks: BTreeMap<String, Task>,
    split_counts: BTreeMap<String, usize>,
}

impl OvercookedBackend {
    pub fn load(tasks_root: &Path) -> Result<Self, String> {
        let task_root = tasks_root.join("overcooked-v2-multiplayer");
        let defaults_dir = task_root.join("defaults");
        let dataset_path = defaults_dir.join("mapo_promptopt/dataset_v1.json");
        let text = fs::read_to_string(&dataset_path)
            .map_err(|error| format!("read {}: {error}", dataset_path.display()))?;
        let dataset: DatasetConfig = serde_json::from_str(&text)
            .map_err(|error| format!("parse {}: {error}", dataset_path.display()))?;
        if dataset.schema != DATASET_SCHEMA {
            return Err(format!(
                "unsupported Overcooked dataset schema {:?}",
                dataset.schema
            ));
        }
        let expected_splits = BTreeSet::from([
            "train".to_string(),
            "selection".to_string(),
            "heldout".to_string(),
        ]);
        if dataset.splits.keys().cloned().collect::<BTreeSet<_>>() != expected_splits {
            return Err(
                "Overcooked MAPO manifest must contain exactly train, selection, and heldout"
                    .to_string(),
            );
        }

        let mut tasks = BTreeMap::new();
        let mut split_counts = BTreeMap::new();
        let mut family_splits = BTreeMap::<String, String>::new();
        let mut template_seeds = BTreeSet::new();
        let mut replica_seeds = BTreeSet::new();
        for split in ["train", "selection", "heldout"] {
            let rows = dataset
                .splits
                .get(split)
                .ok_or_else(|| format!("missing Overcooked split {split:?}"))?;
            if rows.len() != 3 {
                return Err(format!(
                    "Overcooked internal {split} split must contain three manifest templates; found {}",
                    rows.len()
                ));
            }
            let expected_replicas = match split {
                "train" => 16usize,
                "selection" | "heldout" => 8usize,
                _ => unreachable!(),
            };
            let mut probes = BTreeSet::new();
            for row in rows {
                let probe = ProbeKind::parse(&row.probe)?;
                if !probes.insert(probe.as_str()) {
                    return Err(format!(
                        "Overcooked split {split:?} repeats probe {:?}",
                        row.probe
                    ));
                }
                let rules = dataset
                    .probe_rules
                    .get(&row.probe)
                    .cloned()
                    .ok_or_else(|| format!("missing rules for Overcooked probe {:?}", row.probe))?;
                if !template_seeds.insert(row.seed) {
                    return Err(format!(
                        "Overcooked template seed {} appears in multiple rows",
                        row.seed
                    ));
                }
                if let Some(previous_split) =
                    family_splits.insert(row.layout_family.clone(), split.to_string())
                {
                    if previous_split != split {
                        return Err(format!(
                            "Overcooked layout family {:?} crosses {previous_split:?} and {split:?}",
                            row.layout_family
                        ));
                    }
                }

                let validation_seed = replica_seed(row.seed, 1)?;
                let validation_task = task_value_parts(
                    &format!("{}_validation", row.row_id),
                    &row.layout_family,
                    validation_seed,
                    &row.layout,
                    &rules,
                )?;
                let validation_env =
                    OvercookedV2Env::from_task_value(&validation_task, &defaults_dir)?;
                let roles = roles_for(probe, validation_env.resolved().agent_ids.len())?;

                for replica_index in 1..=expected_replicas {
                    let seed = replica_seed(row.seed, replica_index)?;
                    if !replica_seeds.insert(seed) {
                        return Err(format!(
                            "Overcooked replica seed {seed} appears in multiple task rows"
                        ));
                    }
                    let task_id = format!(
                        "overcooked_v2_coordination_v1:{split}:{}:r{replica_index:02}:{}",
                        row.row_id,
                        probe.as_str()
                    );
                    let checkpoint_key = digest_text(&format!(
                        "{}|{split}|{}|{}|{replica_index}|{seed}|{}",
                        dataset.dataset_id,
                        row.row_id,
                        row.layout_family,
                        probe.as_str()
                    ));
                    let task = Task {
                        task_id: task_id.clone(),
                        dataset_split: split.to_string(),
                        template_row_id: row.row_id.clone(),
                        layout_family: row.layout_family.clone(),
                        template_seed: row.seed,
                        seed,
                        replica_index,
                        probe,
                        layout: row.layout.clone(),
                        rules: rules.clone(),
                        roles: roles.clone(),
                        checkpoint_key,
                    };
                    if tasks.insert(task_id.clone(), task).is_some() {
                        return Err(format!("duplicate Overcooked task id {task_id:?}"));
                    }
                    *split_counts.entry(split.to_string()).or_default() += 1;
                }
            }
            if probes
                != BTreeSet::from([
                    "hidden_recipe_reveal",
                    "ingredient_cook_role_assignment",
                    "delivery_handoff",
                ])
            {
                return Err(format!(
                    "Overcooked split {split:?} must contain all three probe templates"
                ));
            }
        }
        if split_counts.get("train") != Some(&48)
            || split_counts.get("selection") != Some(&24)
            || split_counts.get("heldout") != Some(&24)
        {
            return Err(format!(
                "Overcooked deterministic expansion produced unexpected counts {split_counts:?}"
            ));
        }

        Ok(Self {
            dataset_id: dataset.dataset_id,
            defaults_dir,
            tasks,
            split_counts,
        })
    }

    pub fn environment_id(&self) -> &'static str {
        ENVIRONMENT_ID
    }

    pub fn valid_roles(&self) -> Vec<String> {
        ["ingredient_0", "ingredient_1", "cook", "delivery"]
            .into_iter()
            .map(str::to_string)
            .collect()
    }

    pub fn task_roles(&self, task_id: &str) -> Option<Vec<String>> {
        self.tasks.get(task_id).map(|task| task.roles.clone())
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
                    .filter(|task| public_split(&task.dataset_split) == Some(split))
                    .ok_or_else(|| {
                        format!("task id {task_id:?} is not available in requested split {split:?}")
                    })?;
                Ok(json!({
                    "task_id": task.task_id,
                    "example_id": task.task_id,
                    "split": split,
                    "dataset_split": task.dataset_split,
                    "objective": "outcome_reward",
                    "row_schema": ROW_SCHEMA,
                    "dataset_id": self.dataset_id,
                    "dataset_version": "v1",
                    "environment": ENVIRONMENT_ID,
                    "checkpoint_key": task.checkpoint_key,
                    "roles": task.roles,
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
            .ok_or_else(|| format!("unknown Overcooked task id {task_id:?}"))?;
        let context = prepare_probe(task, &self.defaults_dir)?;
        run_probe(task, &context, execution)
    }
}

fn replica_seed(template_seed: u64, replica_index: usize) -> Result<u64, String> {
    template_seed
        .checked_mul(100)
        .and_then(|seed| seed.checked_add(replica_index as u64))
        .ok_or_else(|| format!("Overcooked replica seed overflow for {template_seed}"))
}

fn roles_for(probe: ProbeKind, agent_count: usize) -> Result<Vec<String>, String> {
    let roles = match probe {
        ProbeKind::HiddenRecipeReveal if agent_count == 2 => vec!["cook", "ingredient_0"],
        ProbeKind::IngredientCookRoleAssignment if agent_count == 3 => {
            vec!["ingredient_0", "ingredient_1", "cook"]
        }
        ProbeKind::IngredientCookRoleAssignment if agent_count == 4 => {
            vec!["ingredient_0", "ingredient_1", "cook", "delivery"]
        }
        ProbeKind::DeliveryHandoff if agent_count == 2 => vec!["cook", "delivery"],
        _ => {
            return Err(format!(
                "Overcooked probe {} is not valid for {agent_count} agents",
                probe.as_str()
            ))
        }
    };
    Ok(roles.into_iter().map(str::to_string).collect())
}

fn task_value(task: &Task) -> Result<Value, String> {
    task_value_parts(
        &task.task_id,
        &task.layout_family,
        task.seed,
        &task.layout,
        &task.rules,
    )
}

fn task_value_parts(
    task_id: &str,
    layout_family: &str,
    seed: u64,
    layout: &Value,
    rules: &Value,
) -> Result<Value, String> {
    let mut layout = layout
        .as_object()
        .cloned()
        .ok_or_else(|| format!("Overcooked task {task_id:?} layout must be an object"))?;
    layout.insert(
        "layout_id".to_string(),
        Value::String(format!("mapo_promptopt_{layout_family}")),
    );
    Ok(json!({
        "task_id": task_id,
        "scenario_id": task_id,
        "seed": seed,
        "layout": layout,
        "rules": rules,
        "readouts": {"profile": "symbolic_compact"},
    }))
}

fn prepare_probe(task: &Task, defaults_dir: &Path) -> Result<ProbeContext, String> {
    let task_value = task_value(task)?;
    let mut environment = OvercookedV2Env::from_task_value(&task_value, defaults_dir)?;
    match task.probe {
        ProbeKind::HiddenRecipeReveal => {
            let button = only_position(
                environment
                    .layout()
                    .button_recipe_indicators
                    .iter()
                    .copied(),
                "button",
            )?;
            navigate_adjacent_raw(&mut environment, "agent_0", button)?;
            if environment
                .resolved()
                .agent_ids
                .iter()
                .any(|agent_id| environment.is_recipe_visible(agent_id))
            {
                return Err(format!(
                    "{} reveal checkpoint leaked recipe visibility",
                    task.task_id
                ));
            }
        }
        ProbeKind::IngredientCookRoleAssignment => {
            pickup_ingredient_raw(&mut environment, "agent_0", 0)?;
            pickup_ingredient_raw(&mut environment, "agent_1", 1)?;
            if environment.agents()["agent_0"].held.as_deref() != Some("ing_0")
                || environment.agents()["agent_1"].held.as_deref() != Some("ing_1")
            {
                return Err(format!(
                    "{} role checkpoint did not stage distinct carriers",
                    task.task_id
                ));
            }
        }
        ProbeKind::DeliveryHandoff => {
            let carrier = "agent_0";
            pickup_ingredient_raw(&mut environment, carrier, 0)?;
            let pot = only_position(environment.layout().pots.iter().copied(), "pot")?;
            navigate_adjacent_raw(&mut environment, carrier, pot)?;
            interact_raw(&mut environment, carrier)?;
            while !environment.soup_ready() {
                wait_raw(&mut environment)?;
                if environment.readout()?.private.truncated {
                    return Err(format!(
                        "{} truncated while preparing delivery checkpoint",
                        task.task_id
                    ));
                }
            }
            let dish = only_position(
                environment.layout().dish_dispensers.iter().copied(),
                "dish dispenser",
            )?;
            navigate_adjacent_raw(&mut environment, carrier, dish)?;
            interact_raw(&mut environment, carrier)?;
            navigate_adjacent_raw(&mut environment, carrier, pot)?;
            interact_raw(&mut environment, carrier)?;
            if environment.agents()[carrier].held.as_deref() != Some("plated_soup") {
                return Err(format!("{} setup failed to plate soup", task.task_id));
            }
            let counter = only_position(environment.layout().counters.iter().copied(), "counter")?;
            navigate_adjacent_raw(&mut environment, carrier, counter)?;
            interact_raw(&mut environment, carrier)?;
            let start = environment.layout().agent_starts[carrier];
            navigate_to_raw(&mut environment, carrier, start)?;
            if environment
                .counter_items()
                .get(&counter)
                .map(String::as_str)
                != Some("plated_soup")
                || environment.agents()["agent_1"].held.is_some()
            {
                return Err(format!("{} handoff checkpoint is not staged", task.task_id));
            }
        }
    }

    let checkpoint = environment.checkpoint_json()?;
    let checkpoint_digest = format!("sha256:{}", environment.checkpoint_digest()?);
    let checkpoint_state_digest = format!("sha256:{}", environment.state_digest()?);
    let restored = OvercookedV2Env::from_checkpoint_json(&checkpoint)?;
    if restored.checkpoint_json()? != checkpoint
        || format!("sha256:{}", restored.state_digest()?) != checkpoint_state_digest
    {
        return Err(format!(
            "Overcooked checkpoint roundtrip changed {}",
            task.task_id
        ));
    }
    Ok(ProbeContext {
        checkpoint,
        checkpoint_digest,
        checkpoint_state_digest,
    })
}

fn run_probe(
    task: &Task,
    context: &ProbeContext,
    execution: &ExecutionSpec,
) -> Result<EpisodeEvidence, String> {
    let mut environment = OvercookedV2Env::from_checkpoint_json(&context.checkpoint)?;
    let before = environment.readout()?;
    let canonical = canonical_assignments(task.probe, &environment.resolved().agent_ids)?;
    let modes = task
        .roles
        .iter()
        .map(|role| (role.clone(), execution.protocol.role_mode(role)))
        .collect::<BTreeMap<_, _>>();
    let assignments = resolved_assignments(task, &canonical, &modes, execution)?;
    let role_duplication_count = modes
        .values()
        .filter(|mode| **mode == RoleMode::Duplicated)
        .count();
    let mut recorder = RunRecorder::new(&environment);
    recorder.interference_action_count += role_duplication_count;

    execute_probe(
        &mut environment,
        &mut recorder,
        task,
        execution,
        &modes,
        &assignments,
    )?;
    execute_duplication_interference(&mut environment, &mut recorder, &modes, &assignments)?;

    recorder.interference_action_count += recorder.masked_delivery_count;
    let after = environment.readout()?;
    let outcome_success = probe_outcome(task.probe, &recorder.events);
    let message_action_alignment = !execution.arm.channel_masked
        && recorder.grounded_signal_count > 0
        && grounded_signal_aligned(task.probe, &recorder.events);
    let role_consistency = task.probe.critical_roles().iter().all(|role| {
        modes.get(*role).is_some_and(|mode| role_active(*mode))
            && assignments.get(*role).and_then(Option::as_deref)
                == canonical.get(*role).map(String::as_str)
    });
    let invalid_action_count = runtime_invalid_delta(&before.metrics, &after.metrics)
        + after
            .private
            .invalid_action_count
            .saturating_sub(before.private.invalid_action_count) as usize;
    let coordination_success = outcome_success
        && message_action_alignment
        && role_consistency
        && invalid_action_count == 0
        && recorder.interference_action_count == 0;
    let engine_reward = after.private.total_reward - before.private.total_reward;
    let metrics = EpisodeMetrics {
        outcome_success: bool_metric(outcome_success),
        coordination_success: bool_metric(coordination_success),
        message_action_alignment: bool_metric(message_action_alignment),
        role_consistency: bool_metric(role_consistency),
        role_duplication_count,
        invalid_action_count,
        idle_action_count: recorder.idle_action_count,
        interference_action_count: recorder.interference_action_count,
        message_count: recorder.grounded_signal_count,
        message_chars: 0,
        per_agent_contribution_coverage: contribution_coverage(&recorder.per_agent),
        engine_reward,
    };

    let mut failure_signals = Vec::new();
    if !outcome_success {
        failure_signals.push("overcooked_probe_outcome_not_reached".to_string());
    }
    if recorder.grounded_signal_count == 0 {
        failure_signals.push("no_authority_grounded_signal_emitted".to_string());
    } else if !message_action_alignment {
        failure_signals.push("grounded_signal_not_used_by_dependent_action".to_string());
    }
    if !role_consistency {
        failure_signals.push("prompt_role_assignment_inconsistent".to_string());
    }
    if invalid_action_count > 0 {
        failure_signals.push("authority_rejected_or_blocked_action".to_string());
    }
    if execution.arm.channel_masked && recorder.grounded_signal_count > 0 {
        failure_signals.push("grounded_signal_delivery_masked_in_executor".to_string());
    }

    let engine_events = recorder
        .events
        .iter()
        .map(|event| serde_json::to_value(event).map_err(display_error))
        .collect::<Result<Vec<_>, _>>()?;
    let summary_fields = BTreeMap::from([
        ("coordination_case".to_string(), json!(task.probe)),
        ("dataset_split".to_string(), json!(task.dataset_split)),
        ("template_row_id".to_string(), json!(task.template_row_id)),
        ("layout_family".to_string(), json!(task.layout_family)),
        ("template_seed".to_string(), json!(task.template_seed)),
        ("replica_seed".to_string(), json!(task.seed)),
        ("replica_index".to_string(), json!(task.replica_index)),
        ("roles".to_string(), json!(task.roles)),
        ("canonical_role_assignments".to_string(), json!(canonical)),
        ("assigned_roles".to_string(), json!(assignments)),
        (
            "communication_modality".to_string(),
            json!("grounded_engine_signal"),
        ),
        ("free_text_engine_messages".to_string(), json!(0)),
        (
            "grounded_signal_count".to_string(),
            json!(recorder.grounded_signal_count),
        ),
        (
            "masked_delivery_count".to_string(),
            json!(recorder.masked_delivery_count),
        ),
        (
            "checkpoint_state_digest".to_string(),
            json!(context.checkpoint_state_digest),
        ),
        (
            "authority_runtime_delta".to_string(),
            runtime_delta(&before.metrics, &after.metrics),
        ),
    ]);
    Ok(EpisodeEvidence {
        task_id: task.task_id.clone(),
        split: public_split(&task.dataset_split)
            .ok_or_else(|| format!("invalid Overcooked dataset split {:?}", task.dataset_split))?
            .to_string(),
        environment: ENVIRONMENT_ID.to_string(),
        checkpoint_digest: context.checkpoint_digest.clone(),
        final_state_digest: format!("sha256:{}", environment.state_digest()?),
        metrics,
        per_agent: recorder.per_agent,
        engine_events,
        action_trace: recorder.action_trace,
        failure_signals,
        summary_fields,
    })
}

fn canonical_assignments(
    probe: ProbeKind,
    agent_ids: &[String],
) -> Result<BTreeMap<String, String>, String> {
    let actor = |index: usize| {
        agent_ids.get(index).cloned().ok_or_else(|| {
            format!(
                "Overcooked probe {} requires agent index {index}",
                probe.as_str()
            )
        })
    };
    let assignments = match probe {
        ProbeKind::HiddenRecipeReveal => BTreeMap::from([
            ("cook".to_string(), actor(0)?),
            ("ingredient_0".to_string(), actor(1)?),
        ]),
        ProbeKind::IngredientCookRoleAssignment => {
            let mut values = BTreeMap::from([
                ("ingredient_0".to_string(), actor(0)?),
                ("ingredient_1".to_string(), actor(1)?),
                ("cook".to_string(), actor(2)?),
            ]);
            if agent_ids.len() == 4 {
                values.insert("delivery".to_string(), actor(3)?);
            }
            values
        }
        ProbeKind::DeliveryHandoff => BTreeMap::from([
            ("cook".to_string(), actor(0)?),
            ("delivery".to_string(), actor(1)?),
        ]),
    };
    Ok(assignments)
}

fn resolved_assignments(
    task: &Task,
    canonical: &BTreeMap<String, String>,
    modes: &BTreeMap<String, RoleMode>,
    execution: &ExecutionSpec,
) -> Result<BTreeMap<String, Option<String>>, String> {
    let mut actor_map = canonical.clone();
    if execution.arm.role_permuted {
        match task.probe {
            ProbeKind::HiddenRecipeReveal => {
                swap_assignments(&mut actor_map, "cook", "ingredient_0")?
            }
            ProbeKind::IngredientCookRoleAssignment => {
                swap_assignments(&mut actor_map, "ingredient_0", "ingredient_1")?;
                if actor_map.contains_key("delivery") {
                    swap_assignments(&mut actor_map, "cook", "delivery")?;
                }
            }
            ProbeKind::DeliveryHandoff => {
                swap_assignments(&mut actor_map, "cook", "delivery")?;
            }
        }
    }
    task.roles
        .iter()
        .map(|role| {
            let mode = modes
                .get(role)
                .copied()
                .ok_or_else(|| format!("missing role mode for {role:?}"))?;
            let actor = if mode == RoleMode::Silent {
                None
            } else {
                Some(
                    actor_map
                        .get(role)
                        .cloned()
                        .ok_or_else(|| format!("missing actor assignment for {role:?}"))?,
                )
            };
            Ok((role.clone(), actor))
        })
        .collect()
}

fn swap_assignments(
    assignments: &mut BTreeMap<String, String>,
    left: &str,
    right: &str,
) -> Result<(), String> {
    let left_actor = assignments
        .get(left)
        .cloned()
        .ok_or_else(|| format!("cannot permute missing Overcooked role {left:?}"))?;
    let right_actor = assignments
        .get(right)
        .cloned()
        .ok_or_else(|| format!("cannot permute missing Overcooked role {right:?}"))?;
    assignments.insert(left.to_string(), right_actor);
    assignments.insert(right.to_string(), left_actor);
    Ok(())
}

fn execute_probe(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    task: &Task,
    execution: &ExecutionSpec,
    modes: &BTreeMap<String, RoleMode>,
    assignments: &BTreeMap<String, Option<String>>,
) -> Result<(), String> {
    match task.probe {
        ProbeKind::HiddenRecipeReveal => {
            execute_hidden_reveal(environment, recorder, execution, modes, assignments)
        }
        ProbeKind::IngredientCookRoleAssignment => {
            execute_ingredient_cook(environment, recorder, execution, modes, assignments)
        }
        ProbeKind::DeliveryHandoff => {
            execute_delivery_handoff(environment, recorder, execution, modes, assignments)
        }
    }
}

fn execute_hidden_reveal(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    execution: &ExecutionSpec,
    modes: &BTreeMap<String, RoleMode>,
    assignments: &BTreeMap<String, Option<String>>,
) -> Result<(), String> {
    let request_enabled = request_enabled(execution);
    let cook_actor = assignment_actor(assignments, "cook");
    if !request_enabled || !role_is_active(modes, "cook") || cook_actor.is_none() {
        return explicit_hold(environment, recorder, "seed_hidden_recipe_hold", cook_actor);
    }
    let cook_actor = cook_actor.unwrap();
    let button = only_position(
        environment
            .layout()
            .button_recipe_indicators
            .iter()
            .copied(),
        "button",
    )?;
    navigate_adjacent_traced(environment, recorder, cook_actor, button, "button_signal")?;
    let signal_emitted = act_one_traced(
        environment,
        recorder,
        "button_signal",
        cook_actor,
        Action::Interact,
        Some(GroundedSignal::Button),
        execution.arm.channel_masked,
    )?;
    let signaler_home = environment
        .layout()
        .agent_starts
        .get(cook_actor)
        .copied()
        .ok_or_else(|| format!("missing start position for {cook_actor:?}"))?;
    navigate_to_traced(
        environment,
        recorder,
        cook_actor,
        signaler_home,
        "button_signaler_lane_clear",
    )?;
    follower_ack(
        environment,
        recorder,
        assignment_actor(assignments, "ingredient_0"),
        execution,
        signal_emitted,
    )?;
    if !signal_emitted || !protocol_action_enabled(execution) {
        return explicit_hold(
            environment,
            recorder,
            "hidden_recipe_action_gate_hold",
            assignment_actor(assignments, "ingredient_0"),
        );
    }
    if execution.arm.channel_masked {
        recorder.interference_action_count += 1;
        return explicit_hold(
            environment,
            recorder,
            "masked_recipe_choice_hold",
            assignment_actor(assignments, "ingredient_0"),
        );
    }
    let ingredient_actor = assignment_actor(assignments, "ingredient_0");
    if !role_is_active(modes, "ingredient_0") || ingredient_actor.is_none() {
        return explicit_hold(
            environment,
            recorder,
            "unassigned_recipe_follower_hold",
            ingredient_actor,
        );
    }
    let ingredient_actor = ingredient_actor.unwrap();
    let ingredient_index = environment
        .recipe_ingredients()
        .first()
        .copied()
        .ok_or_else(|| "revealed Overcooked recipe has no ingredients".to_string())?;
    pickup_ingredient_traced(
        environment,
        recorder,
        ingredient_actor,
        ingredient_index,
        "revealed_recipe_pickup",
    )?;
    Ok(())
}

fn execute_ingredient_cook(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    execution: &ExecutionSpec,
    modes: &BTreeMap<String, RoleMode>,
    assignments: &BTreeMap<String, Option<String>>,
) -> Result<(), String> {
    if !protocol_action_enabled(execution) {
        return explicit_hold(
            environment,
            recorder,
            "seed_ingredient_assignment_hold",
            assignment_actor(assignments, "cook"),
        );
    }
    let pot = only_position(environment.layout().pots.iter().copied(), "pot")?;
    let signals_before = recorder.grounded_signal_count;
    for role in ["ingredient_0", "ingredient_1"] {
        let actor = assignment_actor(assignments, role);
        if !role_is_active(modes, role) || actor.is_none() {
            continue;
        }
        let actor = actor.unwrap();
        navigate_adjacent_traced(environment, recorder, actor, pot, "ingredient_pot_signal")?;
        act_one_traced(
            environment,
            recorder,
            "ingredient_pot_signal",
            actor,
            Action::Interact,
            Some(GroundedSignal::PotState),
            execution.arm.channel_masked,
        )?;
        let actor_home = environment
            .layout()
            .agent_starts
            .get(actor)
            .copied()
            .ok_or_else(|| format!("missing start position for {actor:?}"))?;
        navigate_to_traced(
            environment,
            recorder,
            actor,
            actor_home,
            "ingredient_carrier_lane_clear",
        )?;
    }
    let emitted = recorder
        .grounded_signal_count
        .saturating_sub(signals_before);
    follower_ack(
        environment,
        recorder,
        assignment_actor(assignments, "cook"),
        execution,
        emitted > 0,
    )?;
    if execution.arm.channel_masked && emitted > 0 {
        recorder.interference_action_count += 1;
        return explicit_hold(
            environment,
            recorder,
            "masked_pot_state_hold",
            assignment_actor(assignments, "cook"),
        );
    }
    let cook_actor = assignment_actor(assignments, "cook");
    if emitted < 2 || !role_is_active(modes, "cook") || cook_actor.is_none() {
        return explicit_hold(
            environment,
            recorder,
            "cook_assignment_incomplete_hold",
            cook_actor,
        );
    }
    let cook_actor = cook_actor.unwrap();
    navigate_adjacent_traced(environment, recorder, cook_actor, pot, "cook_start")?;
    act_one_traced(
        environment,
        recorder,
        "cook_start",
        cook_actor,
        Action::Interact,
        None,
        false,
    )?;
    Ok(())
}

fn execute_delivery_handoff(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    execution: &ExecutionSpec,
    modes: &BTreeMap<String, RoleMode>,
    assignments: &BTreeMap<String, Option<String>>,
) -> Result<(), String> {
    let delivery_actor = assignment_actor(assignments, "delivery");
    if !protocol_action_enabled(execution)
        || !role_is_active(modes, "cook")
        || !role_is_active(modes, "delivery")
        || delivery_actor.is_none()
    {
        return explicit_hold(
            environment,
            recorder,
            "seed_delivery_handoff_hold",
            delivery_actor,
        );
    }
    let delivery_actor = delivery_actor.unwrap();
    let counter = only_position(environment.layout().counters.iter().copied(), "counter")?;
    navigate_adjacent_traced(
        environment,
        recorder,
        delivery_actor,
        counter,
        "counter_handoff_signal",
    )?;
    let signal_emitted = act_one_traced(
        environment,
        recorder,
        "counter_handoff_signal",
        delivery_actor,
        Action::Interact,
        Some(GroundedSignal::CounterHandoff),
        execution.arm.channel_masked,
    )?;
    follower_ack(
        environment,
        recorder,
        Some(delivery_actor),
        execution,
        signal_emitted,
    )?;
    if execution.arm.channel_masked && signal_emitted {
        recorder.interference_action_count += 1;
        return explicit_hold(
            environment,
            recorder,
            "masked_counter_handoff_hold",
            Some(delivery_actor),
        );
    }
    if !signal_emitted {
        return explicit_hold(
            environment,
            recorder,
            "counter_handoff_missing_hold",
            Some(delivery_actor),
        );
    }
    let serve = only_position(
        environment.layout().serve_tiles.iter().copied(),
        "serve tile",
    )?;
    navigate_adjacent_traced(
        environment,
        recorder,
        delivery_actor,
        serve,
        "delivery_action",
    )?;
    act_one_traced(
        environment,
        recorder,
        "delivery_action",
        delivery_actor,
        Action::Interact,
        None,
        false,
    )?;
    Ok(())
}

fn request_enabled(execution: &ExecutionSpec) -> bool {
    execution.protocol.request != RequestPolicy::ActionOnly
        && execution.protocol.speak != SpeakPolicy::Silent
}

fn protocol_action_enabled(execution: &ExecutionSpec) -> bool {
    execution.protocol.priority == Priority::Delivery
        && execution.protocol.request != RequestPolicy::RequestOnly
        && execution.protocol.handoff != HandoffPolicy::None
        && (execution.protocol.handoff != HandoffPolicy::Required || request_enabled(execution))
}

fn role_active(mode: RoleMode) -> bool {
    matches!(mode, RoleMode::Specialist | RoleMode::Duplicated)
}

fn role_is_active(modes: &BTreeMap<String, RoleMode>, role: &str) -> bool {
    modes.get(role).copied().is_some_and(role_active)
}

fn assignment_actor<'a>(
    assignments: &'a BTreeMap<String, Option<String>>,
    role: &str,
) -> Option<&'a str> {
    assignments.get(role).and_then(Option::as_deref)
}

fn follower_ack(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    actor: Option<&str>,
    execution: &ExecutionSpec,
    signal_emitted: bool,
) -> Result<(), String> {
    let should_ack = match execution.protocol.follower_reply {
        FollowerReply::Ack => signal_emitted,
        FollowerReply::OnRequest => signal_emitted && request_enabled(execution),
        FollowerReply::Silent => false,
    };
    if should_ack {
        explicit_hold(environment, recorder, "grounded_follower_ack", actor)?;
    }
    Ok(())
}

fn explicit_hold(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    kind: &str,
    actor: Option<&str>,
) -> Result<(), String> {
    let actor = actor
        .map(str::to_string)
        .or_else(|| environment.resolved().agent_ids.first().cloned())
        .ok_or_else(|| "Overcooked environment has no active agents".to_string())?;
    act_one_traced(
        environment,
        recorder,
        kind,
        &actor,
        Action::Wait,
        None,
        false,
    )?;
    Ok(())
}

fn execute_duplication_interference(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    modes: &BTreeMap<String, RoleMode>,
    assignments: &BTreeMap<String, Option<String>>,
) -> Result<(), String> {
    let duplicated = modes
        .iter()
        .filter(|(_, mode)| **mode == RoleMode::Duplicated)
        .filter_map(|(role, _)| {
            assignment_actor(assignments, role).map(|actor| (role.clone(), actor.to_string()))
        })
        .collect::<Vec<_>>();
    for (role, actor) in duplicated {
        act_one_traced(
            environment,
            recorder,
            &format!("duplicated_{role}_action"),
            &actor,
            Action::Interact,
            None,
            false,
        )?;
    }
    Ok(())
}

fn pickup_ingredient_traced(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    agent_id: &str,
    ingredient_index: u8,
    kind: &str,
) -> Result<(), String> {
    let pile = environment
        .layout()
        .ingredient_piles
        .iter()
        .find_map(|(position, index)| (*index == ingredient_index).then_some(*position))
        .ok_or_else(|| format!("layout has no ingredient {ingredient_index} pile"))?;
    navigate_adjacent_traced(environment, recorder, agent_id, pile, kind)?;
    act_one_traced(
        environment,
        recorder,
        kind,
        agent_id,
        Action::Interact,
        None,
        false,
    )?;
    Ok(())
}

fn navigate_adjacent_traced(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    agent_id: &str,
    target: Position,
    kind: &str,
) -> Result<(), String> {
    let goals = Direction::ALL
        .into_iter()
        .map(|direction| target.step(direction))
        .filter(|position| environment.planner_walkable(*position, agent_id))
        .collect::<BTreeSet<_>>();
    if goals.is_empty() {
        return Err(format!(
            "no walkable interaction tile adjacent to {target:?}"
        ));
    }
    let path = find_path(environment, agent_id, &goals)?;
    execute_path_traced(environment, recorder, agent_id, &path, kind)?;
    let current = environment
        .agents()
        .get(agent_id)
        .ok_or_else(|| format!("unknown Overcooked agent {agent_id:?}"))?
        .position;
    let direction = Direction::from_adjacent(current, target).ok_or_else(|| {
        format!("planner stopped at {current:?}, which is not adjacent to {target:?}")
    })?;
    act_one_traced(
        environment,
        recorder,
        &format!("{kind}_face"),
        agent_id,
        Action::Move { direction },
        None,
        false,
    )?;
    if environment.agents()[agent_id].position != current
        || environment.agents()[agent_id].facing != direction
    {
        return Err(format!(
            "fixture-facing move for {agent_id} did not preserve position"
        ));
    }
    Ok(())
}

fn navigate_to_traced(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    agent_id: &str,
    goal: Position,
    kind: &str,
) -> Result<(), String> {
    let path = find_path(environment, agent_id, &BTreeSet::from([goal]))?;
    execute_path_traced(environment, recorder, agent_id, &path, kind)
}

fn execute_path_traced(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    agent_id: &str,
    path: &[Direction],
    kind: &str,
) -> Result<(), String> {
    for direction in path {
        let before = environment.agents()[agent_id].position;
        act_one_traced(
            environment,
            recorder,
            &format!("{kind}_navigate"),
            agent_id,
            Action::Move {
                direction: *direction,
            },
            None,
            false,
        )?;
        let expected = before.step(*direction);
        if environment.agents()[agent_id].position != expected {
            return Err(format!(
                "planner move for {agent_id} was blocked: {before:?} -> {expected:?}"
            ));
        }
    }
    Ok(())
}

fn act_one_traced(
    environment: &mut OvercookedV2Env,
    recorder: &mut RunRecorder,
    kind: &str,
    agent_id: &str,
    action: Action,
    signal: Option<GroundedSignal>,
    suppress_delivery: bool,
) -> Result<bool, String> {
    let mut joint = environment
        .resolved()
        .agent_ids
        .iter()
        .map(|active_id| (active_id.clone(), Action::Wait))
        .collect::<JointAction>();
    if !joint.contains_key(agent_id) {
        return Err(format!("unknown Overcooked actor {agent_id:?}"));
    }
    let is_wait = action == Action::Wait;
    joint.insert(agent_id.to_string(), action.clone());
    {
        let contribution = recorder
            .per_agent
            .get_mut(agent_id)
            .ok_or_else(|| format!("missing contribution row for {agent_id:?}"))?;
        if is_wait {
            recorder.idle_action_count += 1;
        } else {
            contribution.generated_actions += 1;
        }
    }

    let cursor = environment.events().len();
    let readout = environment.step(&joint)?;
    let recent = environment.events_since(cursor).to_vec();
    let signal_emitted = signal.is_some_and(|kind| recent.iter().any(|event| kind.matches(event)));
    let successful_events = recent
        .iter()
        .filter(|event| successful_event(event))
        .count();
    {
        let contribution = recorder
            .per_agent
            .get_mut(agent_id)
            .ok_or_else(|| format!("missing contribution row for {agent_id:?}"))?;
        contribution.engine_events += recent.len();
        contribution.successful_contributions += successful_events;
        if !is_wait
            && recent
                .iter()
                .any(|event| event.kind != "rule_violation" && event.message != "JointStepBegin")
        {
            contribution.applied_actions += 1;
        }
        if signal_emitted {
            contribution.messages_sent += 1;
        }
    }
    for (active_id, reward) in &readout.rewards {
        if let Some(contribution) = recorder.per_agent.get_mut(active_id) {
            contribution.reward += *reward;
        }
    }
    if signal_emitted {
        recorder.grounded_signal_count += 1;
        if suppress_delivery {
            recorder.masked_delivery_count += 1;
        }
    }

    let event_values = recent
        .iter()
        .map(|event| serde_json::to_value(event).map_err(display_error))
        .collect::<Result<Vec<_>, _>>()?;
    let joint_value = serde_json::to_value(&joint).map_err(display_error)?;
    recorder.action_trace.push(json!({
        "index": recorder.action_trace.len(),
        "kind": kind,
        "actor": agent_id,
        "generated_joint_action": joint_value,
        "applied_joint_action": joint_value,
        "grounded_signal": signal.map(GroundedSignal::label),
        "grounded_signal_emitted": signal_emitted,
        "executor_information_delivery_suppressed": signal_emitted && suppress_delivery,
        "free_text_message": null,
        "engine_events": event_values,
        "step_index": readout.private.step_index,
        "authority_reward": readout.private.reward_last,
    }));
    recorder.events.extend(recent);
    Ok(signal_emitted)
}

fn find_path(
    environment: &OvercookedV2Env,
    agent_id: &str,
    goals: &BTreeSet<Position>,
) -> Result<Vec<Direction>, String> {
    let start = environment
        .agents()
        .get(agent_id)
        .ok_or_else(|| format!("unknown planner agent {agent_id:?}"))?
        .position;
    if goals.contains(&start) {
        return Ok(Vec::new());
    }
    let mut queue = VecDeque::from([start]);
    let mut previous = BTreeMap::<Position, (Position, Direction)>::new();
    let mut seen = BTreeSet::from([start]);
    let mut found = None;
    while let Some(position) = queue.pop_front() {
        for direction in Direction::ALL {
            let next = position.step(direction);
            if seen.contains(&next) || !environment.planner_walkable(next, agent_id) {
                continue;
            }
            seen.insert(next);
            previous.insert(next, (position, direction));
            if goals.contains(&next) {
                found = Some(next);
                break;
            }
            queue.push_back(next);
        }
        if found.is_some() {
            break;
        }
    }
    let mut cursor = found
        .ok_or_else(|| format!("no path for {agent_id} from {start:?} to any of {goals:?}"))?;
    let mut path = Vec::new();
    while cursor != start {
        let (parent, direction) = previous[&cursor];
        path.push(direction);
        cursor = parent;
    }
    path.reverse();
    Ok(path)
}

fn pickup_ingredient_raw(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    ingredient_index: u8,
) -> Result<(), String> {
    let pile = environment
        .layout()
        .ingredient_piles
        .iter()
        .find_map(|(position, index)| (*index == ingredient_index).then_some(*position))
        .ok_or_else(|| format!("layout has no ingredient {ingredient_index} pile"))?;
    navigate_adjacent_raw(environment, agent_id, pile)?;
    interact_raw(environment, agent_id)
}

fn navigate_adjacent_raw(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    target: Position,
) -> Result<(), String> {
    let goals = Direction::ALL
        .into_iter()
        .map(|direction| target.step(direction))
        .filter(|position| environment.planner_walkable(*position, agent_id))
        .collect::<BTreeSet<_>>();
    if goals.is_empty() {
        return Err(format!(
            "no walkable interaction tile adjacent to {target:?}"
        ));
    }
    let path = find_path(environment, agent_id, &goals)?;
    execute_path_raw(environment, agent_id, &path)?;
    let current = environment.agents()[agent_id].position;
    let direction = Direction::from_adjacent(current, target).ok_or_else(|| {
        format!("planner stopped at {current:?}, which is not adjacent to {target:?}")
    })?;
    act_one_raw(environment, agent_id, Action::Move { direction })?;
    if environment.agents()[agent_id].position != current
        || environment.agents()[agent_id].facing != direction
    {
        return Err(format!(
            "fixture-facing move for {agent_id} did not preserve position"
        ));
    }
    Ok(())
}

fn navigate_to_raw(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    goal: Position,
) -> Result<(), String> {
    let path = find_path(environment, agent_id, &BTreeSet::from([goal]))?;
    execute_path_raw(environment, agent_id, &path)
}

fn execute_path_raw(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    path: &[Direction],
) -> Result<(), String> {
    for direction in path {
        let before = environment.agents()[agent_id].position;
        act_one_raw(
            environment,
            agent_id,
            Action::Move {
                direction: *direction,
            },
        )?;
        let expected = before.step(*direction);
        if environment.agents()[agent_id].position != expected {
            return Err(format!(
                "planner move for {agent_id} was blocked: {before:?} -> {expected:?}"
            ));
        }
    }
    Ok(())
}

fn interact_raw(environment: &mut OvercookedV2Env, agent_id: &str) -> Result<(), String> {
    act_one_raw(environment, agent_id, Action::Interact)
}

fn wait_raw(environment: &mut OvercookedV2Env) -> Result<(), String> {
    let joint = environment
        .resolved()
        .agent_ids
        .iter()
        .map(|agent_id| (agent_id.clone(), Action::Wait))
        .collect::<JointAction>();
    environment.step(&joint).map(|_| ())
}

fn act_one_raw(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    action: Action,
) -> Result<(), String> {
    let mut joint = environment
        .resolved()
        .agent_ids
        .iter()
        .map(|active_id| (active_id.clone(), Action::Wait))
        .collect::<JointAction>();
    if !joint.contains_key(agent_id) {
        return Err(format!("unknown Overcooked actor {agent_id:?}"));
    }
    joint.insert(agent_id.to_string(), action);
    environment.step(&joint).map(|_| ())
}

fn probe_outcome(probe: ProbeKind, events: &[EventRecord]) -> bool {
    match probe {
        ProbeKind::HiddenRecipeReveal => {
            has_event(events, "ButtonActivated(") && has_ingredient_pickup(events)
        }
        ProbeKind::IngredientCookRoleAssignment => {
            event_count(events, "PotIngredientAdded(") >= 2 && has_event(events, "CookStart(")
        }
        ProbeKind::DeliveryHandoff => has_counter_pickup(events) && has_event(events, "Delivery("),
    }
}

fn grounded_signal_aligned(probe: ProbeKind, events: &[EventRecord]) -> bool {
    probe_outcome(probe, events)
}

fn has_event(events: &[EventRecord], prefix: &str) -> bool {
    events.iter().any(|event| event.message.starts_with(prefix))
}

fn event_count(events: &[EventRecord], prefix: &str) -> usize {
    events
        .iter()
        .filter(|event| event.message.starts_with(prefix))
        .count()
}

fn has_counter_pickup(events: &[EventRecord]) -> bool {
    events.iter().any(|event| {
        event.message.starts_with("ItemPicked(") && event.message.contains(",counter)")
    })
}

fn has_ingredient_pickup(events: &[EventRecord]) -> bool {
    events
        .iter()
        .any(|event| event.message.starts_with("ItemPicked(") && event.message.contains(",ing_"))
}

fn successful_event(event: &EventRecord) -> bool {
    event.message.starts_with("ButtonActivated(")
        || (event.message.starts_with("ItemPicked(") && event.message.contains(",ing_"))
        || event.message.starts_with("PotIngredientAdded(")
        || event.message.starts_with("CookStart(")
        || (event.message.starts_with("ItemPicked(") && event.message.contains(",counter)"))
        || event.message.starts_with("Delivery(")
}

fn runtime_invalid_delta(before: &RuntimeMetrics, after: &RuntimeMetrics) -> usize {
    after.blocked_moves.saturating_sub(before.blocked_moves) as usize
        + after
            .interaction_no_effects
            .saturating_sub(before.interaction_no_effects) as usize
}

fn runtime_delta(before: &RuntimeMetrics, after: &RuntimeMetrics) -> Value {
    json!({
        "blocked_moves": after.blocked_moves.saturating_sub(before.blocked_moves),
        "interaction_no_effects": after.interaction_no_effects.saturating_sub(before.interaction_no_effects),
        "ingredients_picked": after.ingredients_picked.saturating_sub(before.ingredients_picked),
        "ingredients_added": after.ingredients_added.saturating_sub(before.ingredients_added),
        "cook_starts": after.cook_starts.saturating_sub(before.cook_starts),
        "soups_cooked": after.soups_cooked.saturating_sub(before.soups_cooked),
        "soups_plated": after.soups_plated.saturating_sub(before.soups_plated),
        "counter_handoffs": after.counter_handoffs.saturating_sub(before.counter_handoffs),
        "button_activations": after.button_activations.saturating_sub(before.button_activations),
        "recipe_visible_agent_turns": after.recipe_visible_agent_turns.saturating_sub(before.recipe_visible_agent_turns),
        "delivery_attempts": after.delivery_attempts.saturating_sub(before.delivery_attempts),
        "correct_deliveries": after.correct_deliveries.saturating_sub(before.correct_deliveries),
        "wrong_deliveries": after.wrong_deliveries.saturating_sub(before.wrong_deliveries),
    })
}

fn only_position(
    positions: impl Iterator<Item = Position>,
    label: &str,
) -> Result<Position, String> {
    let values = positions.collect::<Vec<_>>();
    if values.len() != 1 {
        return Err(format!(
            "Overcooked probe requires exactly one {label}; found {}",
            values.len()
        ));
    }
    Ok(values[0])
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
