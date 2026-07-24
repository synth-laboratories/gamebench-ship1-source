use rogue_gold::source_potions::source_potions_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_potions_report()).unwrap()
    );
}
