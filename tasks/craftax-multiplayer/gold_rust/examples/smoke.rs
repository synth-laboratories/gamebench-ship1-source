use craftax_coop_gamebench::CraftaxCoopEnv;
use std::collections::BTreeMap;

fn main() {
    let mut env = CraftaxCoopEnv::reset(101, 3, 100);
    let joint = BTreeMap::from([
        ("agent_0".into(), "request_iron".into()),
        ("agent_1".into(), "noop".into()),
        ("agent_2".into(), "noop".into()),
    ]);
    let result = env.step(&joint).expect("valid joint step");
    println!("{}", serde_json::to_string(&result).unwrap());
}
