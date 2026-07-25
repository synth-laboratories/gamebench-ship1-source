use craftax_coop_gamebench::CraftaxCoopEnv;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::io::{self, Read};

fn joint(raw: &Value) -> BTreeMap<String, Value> {
    raw.as_object()
        .expect("joint_action is an object")
        .iter()
        .map(|(agent, action)| (agent.clone(), action.clone()))
        .collect()
}

fn observations(env: &CraftaxCoopEnv) -> Value {
    Value::Object(
        env.observations(5)
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

fn coordination_state(env: &CraftaxCoopEnv) -> Value {
    json!({
        "alem_coord": env.state.alem_coord,
        "players": env.state.players.iter().map(|player| json!({
            "agent_id": player.agent_id,
            "level": player.level,
            "position": [player.x, player.y],
            "facing": player.facing,
            "iron": player.inventory["iron"],
        })).collect::<Vec<_>>(),
    })
}

fn snapshot(env: &CraftaxCoopEnv) -> Value {
    json!({
        "state": coordination_state(env),
        "observations": observations(env),
        "nev": env.state.nev,
    })
}

fn main() {
    let mut raw = String::new();
    io::stdin().read_to_string(&mut raw).unwrap();
    let input: Value = serde_json::from_str(&raw).unwrap();
    let checkpoint = serde_json::to_string(&input["checkpoint"]).unwrap();
    let mut env = CraftaxCoopEnv::restore_json(&checkpoint).unwrap();
    let restored = snapshot(&env);
    let cursor = env.state.nev.len();
    let step = env.step_json(&joint(&input["joint_action"])).unwrap();
    println!(
        "{}",
        json!({
            "restored": restored,
            "after": {
                "state": coordination_state(&env),
                "observations": observations(&env),
                "nev_suffix": &env.state.nev[cursor..],
                "step_events": step.events,
            },
        })
    );
}
