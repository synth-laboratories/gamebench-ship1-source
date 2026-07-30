use rogue_gold::source_traps::source_traps_report;

fn main() {
    println!("{}", serde_json::to_string(&source_traps_report()).unwrap());
}
