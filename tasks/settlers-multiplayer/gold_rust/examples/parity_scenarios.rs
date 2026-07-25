use settlers_rules_gamebench::SettlersEnv;
use serde_json::{json, Value};

fn scenario(seed: i32, actions: Vec<Value>) -> Value {
    let mut env = SettlersEnv::reset(seed, 80);
    let mut checkpoint_equivalent = true;
    let midpoint = actions.len() / 2;
    for (index, action) in actions.into_iter().enumerate() {
        env.step(action);
        if index + 1 == midpoint {
            let restored = SettlersEnv::restore(env.checkpoint()).expect("owned mid-episode checkpoint restores");
            checkpoint_equivalent &= env.compact_projection() == restored.compact_projection();
            env = restored;
        }
    }
    let checkpoint = env.checkpoint();
    let restored = SettlersEnv::restore(checkpoint).expect("owned checkpoint restores");
    checkpoint_equivalent &= env.compact_projection() == restored.compact_projection();
    json!({"projection": env.compact_projection(), "checkpoint_equivalent": checkpoint_equivalent})
}
fn main() {
    let opening = scenario(0, vec![json!({"kind":"build_road","edge":1}), json!({"kind":"trade_propose","to":"agent_2","give":"wood","want":"ore"}), json!({"kind":"trade_accept"}), json!({"kind":"buy_dev"}), json!({"kind":"move_robber","tile":2,"victim":"agent_1"}), json!("end_turn"), json!({"kind":"build_city","vertex":12}), json!("end_turn")]);
    let robber = scenario(4, vec![json!({"kind":"build_road","edge":1}), json!({"kind":"move_robber","tile":3,"victim":"agent_1"}), json!("end_turn"), json!("end_turn"), json!("end_turn"), json!({"kind":"build_settlement","vertex":2})]);
    let longest_road = scenario(2, vec![json!({"kind":"build_road","edge":1}), json!("end_turn"), json!({"kind":"move_robber","tile":1,"victim":"agent_1"}), json!("end_turn"), json!({"kind":"build_road","edge":2}), json!("end_turn"), json!("end_turn"), json!("end_turn"), json!({"kind":"build_road","edge":23})]);
    let city = scenario(8, vec![json!({"kind":"build_city","vertex":0}), json!("end_turn"), json!("end_turn"), json!("end_turn")]);
    let development = scenario(1, vec![json!("buy_dev"), json!("end_turn"), json!("end_turn"), json!({"kind":"move_robber","tile":1,"victim":"agent_0"}), json!({"kind":"play_dev","card":"knight","tile":2,"victim":"agent_1"}), json!("end_turn"), json!("end_turn"), json!("end_turn"), json!("buy_dev"), json!("end_turn"), json!("end_turn"), json!("end_turn"), json!({"kind":"play_dev","card":"knight","tile":3,"victim":"agent_2"}), json!({"kind":"move_robber","tile":4,"victim":"agent_0"}), json!("end_turn"), json!("end_turn"), json!("buy_dev"), json!("end_turn"), json!("end_turn"), json!("end_turn"), json!({"kind":"play_dev","card":"knight","tile":5,"victim":"agent_3"})]);
    println!("{}", json!({"city_upgrade_victory_point": city, "four_player_opening_trade_city": opening, "robber_and_illegal_action_reliability": robber, "longest_road_network_race": longest_road, "largest_army_development_race": development}));
}
