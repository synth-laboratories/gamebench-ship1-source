use rogue_gold::source_attack::source_attack_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_attack_report()).unwrap()
    );
}
