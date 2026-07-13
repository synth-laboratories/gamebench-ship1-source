use craftax_coop_gamebench::CraftaxCoopEnv;
use std::io::{self, Read};

fn main() {
    let mut checkpoint = String::new();
    io::stdin()
        .read_to_string(&mut checkpoint)
        .expect("checkpoint stdin must be readable");
    let environment = CraftaxCoopEnv::restore_json(&checkpoint)
        .expect("Python checkpoint must satisfy the shared checkpoint schema");
    println!("{}", environment.checkpoint_json());
}
