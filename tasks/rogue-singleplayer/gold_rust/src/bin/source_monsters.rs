use rogue_gold::source_monsters::source_monsters_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_monsters_report()).unwrap()
    );
}
