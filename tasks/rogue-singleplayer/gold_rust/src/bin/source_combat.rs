use rogue_gold::source_combat::source_combat_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_combat_report()).unwrap()
    );
}
