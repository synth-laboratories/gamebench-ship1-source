use craftax_coop_gamebench::CraftaxCoopEnv;
use serde_json::json;
use std::collections::BTreeMap;

fn joint(a:&str,b:&str,c:&str)->BTreeMap<String,String>{BTreeMap::from([("agent_0".into(),a.into()),("agent_1".into(),b.into()),("agent_2".into(),c.into())])}
fn projection(env:&CraftaxCoopEnv)->serde_json::Value{json!({"timestep":env.state.timestep,"players":env.state.players,"trade_count":env.state.trade_count,"achievements":env.state.achievements,"boss_health":env.state.boss_health,"boss_progress":env.state.boss_progress,"terminated":env.state.terminated,"termination_reason":env.state.termination_reason,"map_samples":[env.state.maps[0][4][5].clone(),env.state.maps[0][10][10].clone(),env.state.maps[8][24][24].clone()],"monster_count":env.state.monsters.len()})}
fn main(){let mut env=CraftaxCoopEnv::reset(101,3,100);*env.state.players[2].inventory.get_mut("iron").unwrap()=2;env.step(&joint("request_iron","cast_spell","give_iron_to_agent_0")).unwrap();env.step(&joint("right","down","left")).unwrap();env.step(&joint("rest","noop","make_iron_pickaxe")).unwrap();println!("{}",serde_json::to_string(&projection(&env)).unwrap());}
