use overcooked_v2_gold::{
    sha256_digest, Action, Direction, JointAction, OvercookedV2Env, Position, RuntimeMetrics,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct Dataset {
    schema: String,
    dataset_id: String,
    environment: Value,
    prompt_program: Value,
    reference_executor: Value,
    reference_protocols: Vec<ReferenceProtocol>,
    probes: BTreeMap<String, Value>,
    probe_rules: BTreeMap<String, Value>,
    splits: BTreeMap<String, Vec<DatasetRow>>,
    leakage_guards: Value,
}

#[derive(Debug, Deserialize)]
struct ReferenceProtocol {
    id: String,
    executor_profile: String,
    purpose: String,
}

#[derive(Clone, Debug, Deserialize)]
struct DatasetRow {
    row_id: String,
    layout_family: String,
    seed: u64,
    probe: String,
    layout: Value,
}

#[derive(Default)]
struct Aggregate {
    continuations: usize,
    successes: usize,
    checkpoint_roundtrips: usize,
    successes_by_probe: BTreeMap<String, usize>,
}

fn main() -> Result<(), String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let task_dir = manifest_dir
        .parent()
        .ok_or_else(|| "gold_rust must have a task parent".to_string())?;
    let dataset_path = parse_dataset_arg(
        task_dir.join("defaults/mapo_promptopt/dataset_v1.json"),
    )?;
    let dataset_bytes = fs::read(&dataset_path)
        .map_err(|error| format!("read {}: {error}", dataset_path.display()))?;
    let dataset: Dataset = serde_json::from_slice(&dataset_bytes)
        .map_err(|error| format!("parse {}: {error}", dataset_path.display()))?;
    validate_dataset(&dataset)?;

    let defaults_dir = task_dir.join("defaults");
    let mut receipts = Vec::new();
    let mut summary = BTreeMap::<String, Aggregate>::new();
    let mut row_count_by_split = BTreeMap::new();
    for (split, rows) in &dataset.splits {
        row_count_by_split.insert(split.clone(), rows.len());
        for row in rows {
            let rules = dataset
                .probe_rules
                .get(&row.probe)
                .ok_or_else(|| format!("missing rules for probe {:?}", row.probe))?;
            let task = task_value(row, rules)?;
            let mut environment = OvercookedV2Env::from_task_value(&task, &defaults_dir)?;
            prepare_probe(&mut environment, row)?;
            let checkpoint_step = environment.readout()?.private.step_index;
            let checkpoint_cursor = environment.events().len();
            let checkpoint_json = environment.checkpoint_json()?;
            let checkpoint_digest = sha256_digest(checkpoint_json.as_bytes());
            let checkpoint_state_digest = environment.state_digest()?;
            let restored = OvercookedV2Env::from_checkpoint_json(&checkpoint_json)?;
            let roundtrip_exact = restored.checkpoint_json()? == checkpoint_json
                && restored.state_digest()? == checkpoint_state_digest;
            if !roundtrip_exact {
                return Err(format!(
                    "checkpoint roundtrip changed authoritative state for {}",
                    row.row_id
                ));
            }

            for protocol in &dataset.reference_protocols {
                let mut continuation = OvercookedV2Env::from_checkpoint_json(&checkpoint_json)?;
                let before = continuation.runtime_metrics().clone();
                let event_cursor = continuation.events().len();
                execute_protocol(&mut continuation, row, &protocol.executor_profile)?;
                let recent_events = continuation.events_since(event_cursor);
                let event_messages = recent_events
                    .iter()
                    .map(|event| event.message.clone())
                    .collect::<Vec<_>>();
                let event_kinds = recent_events
                    .iter()
                    .map(|event| event.kind.clone())
                    .collect::<Vec<_>>();
                let (success, evidence) = probe_success(&continuation, row, recent_events)?;
                let metrics_delta = metric_delta(&before, continuation.runtime_metrics());
                let final_readout = continuation.readout()?;
                let body = json!({
                    "split": split,
                    "row_id": row.row_id,
                    "layout_family": row.layout_family,
                    "seed": row.seed,
                    "agent_count": continuation.resolved().agent_ids.len(),
                    "probe": row.probe,
                    "protocol_id": protocol.id,
                    "executor_profile": protocol.executor_profile,
                    "executor_scope": "typed_reference_protocol_not_arbitrary_natural_language",
                    "checkpoint": {
                        "schema": "gamebench.overcooked_v2.checkpoint.v2",
                        "step_index": checkpoint_step,
                        "nev_cursor": checkpoint_cursor,
                        "digest": checkpoint_digest,
                        "state_digest": checkpoint_state_digest,
                        "roundtrip_exact": roundtrip_exact,
                    },
                    "continuation": {
                        "steps": final_readout.private.step_index.saturating_sub(checkpoint_step),
                        "event_kinds": event_kinds,
                        "event_messages": event_messages,
                        "metrics_delta": metrics_delta,
                    },
                    "outcome_success": success,
                    "coordination_success": success,
                    "evidence": evidence,
                    "terminal_metrics": continuation.terminal_metrics()?,
                    "final_state_digest": continuation.state_digest()?,
                });
                let receipt_digest = sha256_digest(
                    &serde_json::to_vec(&body)
                        .map_err(|error| format!("serialize receipt digest input: {error}"))?,
                );
                receipts.push(json!({
                    "receipt": body,
                    "receipt_digest": receipt_digest,
                }));
                let aggregate = summary.entry(protocol.id.clone()).or_default();
                aggregate.continuations += 1;
                aggregate.checkpoint_roundtrips += usize::from(roundtrip_exact);
                if success {
                    aggregate.successes += 1;
                    *aggregate
                        .successes_by_probe
                        .entry(row.probe.clone())
                        .or_insert(0) += 1;
                }
            }
        }
    }

    let summary_value = summary
        .into_iter()
        .map(|(protocol, aggregate)| {
            (
                protocol,
                json!({
                    "continuations": aggregate.continuations,
                    "successes": aggregate.successes,
                    "checkpoint_roundtrips": aggregate.checkpoint_roundtrips,
                    "successes_by_probe": aggregate.successes_by_probe,
                }),
            )
        })
        .collect::<BTreeMap<_, _>>();
    let report = json!({
        "schema": "gamebench.mapo_promptopt_checkpoint_receipts.v1",
        "status": "completed",
        "lane": "rust",
        "env_family": "overcooked-v2-multiplayer",
        "dataset": {
            "schema": dataset.schema,
            "dataset_id": dataset.dataset_id,
            "path": stable_path(&dataset_path, task_dir),
            "digest": sha256_digest(&dataset_bytes),
            "row_count": row_count_by_split.values().sum::<usize>(),
            "row_count_by_split": row_count_by_split,
            "probe_count": dataset.probes.len(),
            "continuation_count": receipts.len(),
            "layout_family_and_seed_splits_disjoint": true,
        },
        "environment_contract": dataset.environment,
        "prompt_program": dataset.prompt_program,
        "reference_executor": dataset.reference_executor,
        "reference_protocols": dataset.reference_protocols.iter().map(|protocol| json!({
            "id": protocol.id,
            "executor_profile": protocol.executor_profile,
            "purpose": protocol.purpose,
        })).collect::<Vec<_>>(),
        "leakage_guards": dataset.leakage_guards,
        "summary": summary_value,
        "receipts": receipts,
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .map_err(|error| format!("serialize replay report: {error}"))?
    );
    Ok(())
}

fn parse_dataset_arg(default_path: PathBuf) -> Result<PathBuf, String> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    if args.is_empty() {
        return Ok(default_path);
    }
    if args.len() == 2 && args[0] == "--dataset" {
        return Ok(PathBuf::from(&args[1]));
    }
    Err("usage: mapo_checkpoint_replay [--dataset PATH]".to_string())
}

fn validate_dataset(dataset: &Dataset) -> Result<(), String> {
    if dataset.schema != "gamebench.mapo_promptopt_dataset.v1" {
        return Err(format!("unsupported dataset schema {:?}", dataset.schema));
    }
    let expected_splits = BTreeSet::from([
        "train".to_string(),
        "selection".to_string(),
        "heldout".to_string(),
    ]);
    if dataset.splits.keys().cloned().collect::<BTreeSet<_>>() != expected_splits {
        return Err("dataset must define exactly train, selection, and heldout".to_string());
    }
    let known_profiles = BTreeSet::from([
        "phase_aware_grounded_v1",
        "silent_wait_v1",
        "coordination_omission_v1",
    ]);
    if dataset.reference_protocols.is_empty() {
        return Err("reference_protocols must not be empty".to_string());
    }
    for protocol in &dataset.reference_protocols {
        if !known_profiles.contains(protocol.executor_profile.as_str()) {
            return Err(format!(
                "unsupported reference executor profile {:?}",
                protocol.executor_profile
            ));
        }
    }
    let mut row_ids = BTreeSet::new();
    let mut families = BTreeSet::new();
    let mut seeds = BTreeSet::new();
    for (split, rows) in &dataset.splits {
        let mut split_probes = BTreeSet::new();
        for row in rows {
            if !row_ids.insert(row.row_id.clone()) {
                return Err(format!("duplicate dataset row id {:?}", row.row_id));
            }
            if !families.insert(row.layout_family.clone()) {
                return Err(format!(
                    "layout family {:?} crosses split boundaries",
                    row.layout_family
                ));
            }
            if !seeds.insert(row.seed) {
                return Err(format!("seed {} crosses split boundaries", row.seed));
            }
            if !dataset.probes.contains_key(&row.probe)
                || !dataset.probe_rules.contains_key(&row.probe)
            {
                return Err(format!("row {} names unknown probe {:?}", row.row_id, row.probe));
            }
            if row.layout.get("ascii").and_then(Value::as_array).is_none() {
                return Err(format!("row {} must contain inline layout ascii", row.row_id));
            }
            split_probes.insert(row.probe.clone());
        }
        let expected_probes = dataset.probes.keys().cloned().collect::<BTreeSet<_>>();
        if split_probes != expected_probes {
            return Err(format!("split {split:?} must contain every probe exactly once"));
        }
    }
    Ok(())
}

fn task_value(row: &DatasetRow, rules: &Value) -> Result<Value, String> {
    let mut layout = row
        .layout
        .as_object()
        .cloned()
        .ok_or_else(|| format!("row {} layout must be an object", row.row_id))?;
    layout.insert(
        "layout_id".to_string(),
        Value::String(format!("mapo_promptopt_{}", row.layout_family)),
    );
    Ok(json!({
        "task_id": row.row_id,
        "scenario_id": row.row_id,
        "seed": row.seed,
        "layout": layout,
        "rules": rules,
        "readouts": {"profile": "symbolic_compact"},
    }))
}

fn prepare_probe(environment: &mut OvercookedV2Env, row: &DatasetRow) -> Result<(), String> {
    match row.probe.as_str() {
        "hidden_recipe_reveal" => {
            let button = only_position(
                environment.layout().button_recipe_indicators.iter().copied(),
                "button",
            )?;
            navigate_adjacent(environment, "agent_0", button)?;
            if environment
                .resolved()
                .agent_ids
                .iter()
                .any(|agent_id| environment.is_recipe_visible(agent_id))
            {
                return Err(format!(
                    "{} reveal checkpoint leaked recipe visibility",
                    row.row_id
                ));
            }
        }
        "ingredient_cook_role_assignment" => {
            pickup_ingredient(environment, "agent_0", 0)?;
            pickup_ingredient(environment, "agent_1", 1)?;
            if environment.agents()["agent_0"].held.as_deref() != Some("ing_0")
                || environment.agents()["agent_1"].held.as_deref() != Some("ing_1")
            {
                return Err(format!(
                    "{} role checkpoint did not stage distinct carriers",
                    row.row_id
                ));
            }
        }
        "delivery_handoff" => {
            let carrier = "agent_0";
            pickup_ingredient(environment, carrier, 0)?;
            let pot = only_position(environment.layout().pots.iter().copied(), "pot")?;
            navigate_adjacent(environment, carrier, pot)?;
            interact(environment, carrier)?;
            while !environment.soup_ready() {
                wait_once(environment)?;
                if environment.readout()?.private.truncated {
                    return Err(format!("{} truncated while cooking probe soup", row.row_id));
                }
            }
            let dish = only_position(
                environment.layout().dish_dispensers.iter().copied(),
                "dish dispenser",
            )?;
            navigate_adjacent(environment, carrier, dish)?;
            interact(environment, carrier)?;
            navigate_adjacent(environment, carrier, pot)?;
            interact(environment, carrier)?;
            if environment.agents()[carrier].held.as_deref() != Some("plated_soup") {
                return Err(format!("{} setup failed to plate soup", row.row_id));
            }
            let counter = only_position(environment.layout().counters.iter().copied(), "counter")?;
            navigate_adjacent(environment, carrier, counter)?;
            interact(environment, carrier)?;
            let start = environment.layout().agent_starts[carrier];
            navigate_to(environment, carrier, start)?;
            if environment.counter_items().get(&counter).map(String::as_str)
                != Some("plated_soup")
                || environment.agents()["agent_1"].held.is_some()
            {
                return Err(format!("{} handoff checkpoint is not staged", row.row_id));
            }
        }
        other => return Err(format!("unsupported probe {other:?}")),
    }
    Ok(())
}

fn execute_protocol(
    environment: &mut OvercookedV2Env,
    row: &DatasetRow,
    executor_profile: &str,
) -> Result<(), String> {
    match executor_profile {
        "phase_aware_grounded_v1" => execute_phase_aware(environment, row),
        "silent_wait_v1" => {
            wait_once(environment)?;
            wait_once(environment)
        }
        "coordination_omission_v1" => execute_omission(environment, row),
        other => Err(format!("unsupported executor profile {other:?}")),
    }
}

fn execute_phase_aware(
    environment: &mut OvercookedV2Env,
    row: &DatasetRow,
) -> Result<(), String> {
    match row.probe.as_str() {
        "hidden_recipe_reveal" => interact(environment, "agent_0"),
        "ingredient_cook_role_assignment" => {
            let pot = only_position(environment.layout().pots.iter().copied(), "pot")?;
            for carrier in ["agent_0", "agent_1"] {
                let start = environment.layout().agent_starts[carrier];
                navigate_adjacent(environment, carrier, pot)?;
                interact(environment, carrier)?;
                navigate_to(environment, carrier, start)?;
            }
            navigate_adjacent(environment, "agent_2", pot)?;
            interact(environment, "agent_2")
        }
        "delivery_handoff" => {
            let counter = only_position(environment.layout().counters.iter().copied(), "counter")?;
            let serve = only_position(
                environment.layout().serve_tiles.iter().copied(),
                "serve tile",
            )?;
            navigate_adjacent(environment, "agent_1", counter)?;
            interact(environment, "agent_1")?;
            navigate_adjacent(environment, "agent_1", serve)?;
            interact(environment, "agent_1")
        }
        other => Err(format!("unsupported probe {other:?}")),
    }
}

fn execute_omission(
    environment: &mut OvercookedV2Env,
    row: &DatasetRow,
) -> Result<(), String> {
    match row.probe.as_str() {
        "hidden_recipe_reveal" => wait_once(environment),
        "ingredient_cook_role_assignment" => {
            let pot = only_position(environment.layout().pots.iter().copied(), "pot")?;
            let start = environment.layout().agent_starts["agent_0"];
            navigate_adjacent(environment, "agent_0", pot)?;
            interact(environment, "agent_0")?;
            navigate_to(environment, "agent_0", start)?;
            navigate_adjacent(environment, "agent_2", pot)?;
            interact(environment, "agent_2")
        }
        "delivery_handoff" => {
            let serve = only_position(
                environment.layout().serve_tiles.iter().copied(),
                "serve tile",
            )?;
            navigate_adjacent(environment, "agent_1", serve)?;
            interact(environment, "agent_1")
        }
        other => Err(format!("unsupported probe {other:?}")),
    }
}

fn probe_success(
    environment: &OvercookedV2Env,
    row: &DatasetRow,
    recent_events: &[overcooked_v2_gold::EventRecord],
) -> Result<(bool, Value), String> {
    let has_event = |prefix: &str| {
        recent_events
            .iter()
            .any(|event| event.message.starts_with(prefix))
    };
    match row.probe.as_str() {
        "hidden_recipe_reveal" => {
            let visible = environment
                .resolved()
                .agent_ids
                .iter()
                .map(|agent_id| (agent_id.clone(), environment.is_recipe_visible(agent_id)))
                .collect::<BTreeMap<_, _>>();
            let success = has_event("ButtonActivated(") && visible.values().all(|value| *value);
            Ok((success, json!({
                "button_activated": has_event("ButtonActivated("),
                "recipe_visible_by_agent": visible,
            })))
        }
        "ingredient_cook_role_assignment" => {
            let success = has_event("CookStart(")
                && environment.runtime_metrics().ingredients_added >= 2;
            Ok((success, json!({
                "role_assignment": {
                    "ingredient_0": "agent_0",
                    "ingredient_1": "agent_1",
                    "cook": "agent_2",
                    "plate_or_observer": if environment.resolved().agent_ids.len() == 4 { Some("agent_3") } else { None },
                },
                "cook_started": has_event("CookStart("),
                "authoritative_pot_ingredients": environment.public_state().pot_ingredients,
            })))
        }
        "delivery_handoff" => {
            let success = has_event("ItemPicked(agent_1,plated_soup,counter)")
                && has_event("Delivery(agent_1,");
            Ok((success, json!({
                "counter_pickup": has_event("ItemPicked(agent_1,plated_soup,counter)"),
                "receiver_delivery": has_event("Delivery(agent_1,"),
                "deliveries": environment.public_state().deliveries,
            })))
        }
        other => Err(format!("unsupported probe {other:?}")),
    }
}

fn pickup_ingredient(
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
    navigate_adjacent(environment, agent_id, pile)?;
    interact(environment, agent_id)
}

fn navigate_adjacent(
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
        return Err(format!("no walkable interaction tile adjacent to {target:?}"));
    }
    let path = find_path(environment, agent_id, &goals)?;
    execute_path(environment, agent_id, &path)?;
    let current = environment.agents()[agent_id].position;
    let direction = Direction::from_adjacent(current, target).ok_or_else(|| {
        format!("planner stopped at {current:?}, which is not adjacent to {target:?}")
    })?;
    act_one(environment, agent_id, Action::Move { direction })?;
    if environment.agents()[agent_id].position != current
        || environment.agents()[agent_id].facing != direction
    {
        return Err(format!(
            "fixture-facing move for {agent_id} did not preserve position"
        ));
    }
    Ok(())
}

fn navigate_to(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    goal: Position,
) -> Result<(), String> {
    let goals = BTreeSet::from([goal]);
    let path = find_path(environment, agent_id, &goals)?;
    execute_path(environment, agent_id, &path)
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
    let mut cursor = found.ok_or_else(|| {
        format!(
            "no path for {agent_id} from {start:?} to any of {:?}",
            goals
        )
    })?;
    let mut path = Vec::new();
    while cursor != start {
        let (parent, direction) = previous[&cursor];
        path.push(direction);
        cursor = parent;
    }
    path.reverse();
    Ok(path)
}

fn execute_path(
    environment: &mut OvercookedV2Env,
    agent_id: &str,
    path: &[Direction],
) -> Result<(), String> {
    for direction in path {
        let before = environment.agents()[agent_id].position;
        act_one(
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

fn interact(environment: &mut OvercookedV2Env, agent_id: &str) -> Result<(), String> {
    act_one(environment, agent_id, Action::Interact)
}

fn wait_once(environment: &mut OvercookedV2Env) -> Result<(), String> {
    let joint = environment
        .resolved()
        .agent_ids
        .iter()
        .map(|agent_id| (agent_id.clone(), Action::Wait))
        .collect::<JointAction>();
    environment.step(&joint).map(|_| ())
}

fn act_one(
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
        return Err(format!("unknown actor {agent_id:?}"));
    }
    joint.insert(agent_id.to_string(), action);
    environment.step(&joint).map(|_| ())
}

fn only_position(
    positions: impl Iterator<Item = Position>,
    label: &str,
) -> Result<Position, String> {
    let values = positions.collect::<Vec<_>>();
    if values.len() != 1 {
        return Err(format!(
            "reference probe requires exactly one {label}; found {}",
            values.len()
        ));
    }
    Ok(values[0])
}

fn metric_delta(before: &RuntimeMetrics, after: &RuntimeMetrics) -> Value {
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

fn stable_path(path: &Path, task_dir: &Path) -> String {
    path.strip_prefix(task_dir)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
}
