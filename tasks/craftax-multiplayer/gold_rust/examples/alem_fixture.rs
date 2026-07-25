use craftax_coop_gamebench::{AlemCoordConfig, CraftaxCoopEnv};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::io::{self, Read};

fn joint(raw: &Value) -> BTreeMap<String, Value> {
    raw.as_object()
        .expect("fixture joint action is an object")
        .iter()
        .map(|(agent, action)| (agent.clone(), action.clone()))
        .collect()
}

fn player_summaries(env: &CraftaxCoopEnv) -> Vec<Value> {
    let observations = env.observations(5);
    env.state
        .players
        .iter()
        .map(|player| observations[&player.agent_id]["self"].clone())
        .collect()
}

fn profile_observations(env: &CraftaxCoopEnv) -> Value {
    let observations = env.observations(5);
    Value::Object(
        observations
            .into_iter()
            .map(|(agent_id, observation)| {
                (
                    agent_id,
                    json!({
                        "legal_action_count": observation["legal_actions"].as_array().unwrap().len(),
                        "shared": observation["shared"],
                        "last_joint_event": observation["last_joint_event"],
                    }),
                )
            })
            .collect(),
    )
}

fn main() {
    let mut raw = String::new();
    io::stdin().read_to_string(&mut raw).unwrap();
    let scenario: Value = serde_json::from_str(&raw).unwrap();
    let coordination = scenario["coordination"].as_object().unwrap();
    let alpha_milli = (coordination["alpha"].as_f64().unwrap() * 1000.0).round() as u16;
    let config = AlemCoordConfig::new(coordination["scenario"].as_str().unwrap(), alpha_milli).unwrap();
    let mut env = CraftaxCoopEnv::reset_alem(
        scenario["seed"].as_u64().unwrap(),
        3,
        scenario["max_timesteps"].as_u64().unwrap(),
        config,
    );
    let checkpoint_after = scenario.get("checkpoint_after").and_then(Value::as_u64);
    let initial_observations = profile_observations(&env);
    let mut checkpoint_equivalent = true;
    let mut steps = Vec::new();
    for (index, raw_action) in scenario["joint_actions"].as_array().unwrap().iter().enumerate() {
        let actions = joint(raw_action);
        let step = env.step_json(&actions).unwrap();
        steps.push(json!({
            "index": index,
            "joint_action": raw_action,
            "rewards": step.rewards,
            "dones": step.dones,
            "events": step.events,
        }));
        if checkpoint_after == Some(index as u64 + 1) {
            let before = env.state.clone();
            env = CraftaxCoopEnv::restore_json(&env.checkpoint_json()).unwrap();
            checkpoint_equivalent &= env.state == before;
        }
    }
    let final_before = env.state.clone();
    env = CraftaxCoopEnv::restore_json(&env.checkpoint_json()).unwrap();
    checkpoint_equivalent &= env.state == final_before;
    println!(
        "{}",
        json!({
            "scenario_id": scenario["scenario_id"],
            "checkpoint_equivalent": checkpoint_equivalent,
            "structured_nev": env.state.nev,
            "legacy_nev": env.state.legacy_nev,
            "steps": steps,
            "players": player_summaries(&env),
            "alem_coord": env.state.alem_coord,
            "alem_metrics": env.alem_metrics(),
            "initial_observations": initial_observations,
            "final_observations": profile_observations(&env),
        })
    );
}
