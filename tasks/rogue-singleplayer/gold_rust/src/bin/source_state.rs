use rogue_gold::source_state::source_state_report;

fn main() {
    println!("{}", serde_json::to_string(&source_state_report()).unwrap());
}
