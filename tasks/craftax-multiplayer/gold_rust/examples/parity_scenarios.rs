use craftax_coop_gamebench::{CraftaxCoopEnv, Monster};
use serde_json::{json, Value};
use std::collections::BTreeMap;

fn joint(a: &str, b: &str, c: &str) -> BTreeMap<String, String> {
    BTreeMap::from([
        ("agent_0".into(), a.into()),
        ("agent_1".into(), b.into()),
        ("agent_2".into(), c.into()),
    ])
}
fn noop() -> BTreeMap<String, String> {
    joint("noop", "noop", "noop")
}
fn main() {
    let mut out = serde_json::Map::new();
    let mut env = CraftaxCoopEnv::reset(17, 3, 100);
    out.insert("reset".into(),json!({"maps":[env.state.maps[0][10][10],env.state.maps[6][10][10],env.state.maps[8][24][24]],"monsters":env.state.monsters.iter().take(5).collect::<Vec<_>>() }));
    env.step(&joint("request_ruby", "noop", "noop")).unwrap();
    for _ in 0..10 {
        env.step(&noop()).unwrap();
    }
    out.insert(
        "request_expiry".into(),
        json!([
            env.state.players[0].request_type,
            env.state.players[0].request_duration
        ]),
    );
    let mut env = CraftaxCoopEnv::reset(17, 3, 100);
    env.state.monsters.clear();
    let p = &env.state.players[2];
    env.state.maps[p.level][p.y + 1][p.x] = "iron".into();
    let step = env.step(&joint("noop", "noop", "do")).unwrap();
    out.insert("collect".into(),json!({"iron":env.state.players[2].inventory["iron"],"tile":env.state.maps[0][4][5],"reward":step.rewards["agent_0"],"achievements":env.state.achievements}));
    let mut env = CraftaxCoopEnv::reset(17, 3, 100);
    env.state.monsters = vec![Monster {
        id: "fixture".into(),
        kind: "zombie".into(),
        level: 0,
        x: 3,
        y: 4,
        health: 4,
        damage: 2,
    }];
    env.step(&joint("do", "noop", "noop")).unwrap();
    env.step(&joint("do", "noop", "noop")).unwrap();
    out.insert("combat".into(),json!({"monsters":env.state.monsters,"xp":env.state.players[0].xp,"achievements":env.state.achievements}));
    let mut env = CraftaxCoopEnv::reset(17, 3, 100);
    env.state.monsters.clear();
    for p in &mut env.state.players {
        p.level = 8;
        p.x = 24;
        p.y = 23;
        p.facing = "down".into();
    }
    for _ in 0..3 {
        if !env.state.terminated {
            env.step(&joint("do", "do", "do")).unwrap();
        }
    }
    out.insert("boss".into(),json!({"health":env.state.boss_health,"progress":env.state.boss_progress,"terminated":env.state.terminated,"reason":env.state.termination_reason,"achievements":env.state.achievements}));
    let mut env = CraftaxCoopEnv::reset(17, 3, 100);
    env.state.monsters.clear();
    for p in &mut env.state.players {
        p.health = 1;
        p.food = 0;
        p.drink = 0;
    }
    env.step(&noop()).unwrap();
    out.insert("death".into(),json!({"health":env.state.players.iter().map(|p|p.health).collect::<Vec<_>>(),"terminated":env.state.terminated,"reason":env.state.termination_reason}));
    let mut env = CraftaxCoopEnv::reset(17, 3, 1);
    env.state.monsters.clear();
    env.step(&noop()).unwrap();
    out.insert("timestep".into(),json!({"timestep":env.state.timestep,"terminated":env.state.terminated,"reason":env.state.termination_reason}));
    let mut env = CraftaxCoopEnv::reset(17, 3, 100);
    env.state.monsters.clear();
    env.state.timestep = 50;
    env.state.maps[0][8][8] = "plant".into();
    env.step(&noop()).unwrap();
    out.insert("plant_light".into(),json!({"tile":env.state.maps[0][8][8],"timestep":env.state.timestep,"light":env.state.light_level}));
    let restored = CraftaxCoopEnv::restore_json(&env.checkpoint_json()).unwrap();
    out.insert(
        "checkpoint".into(),
        Value::Bool(env.state == restored.state),
    );
    println!("{}", Value::Object(out));
}
