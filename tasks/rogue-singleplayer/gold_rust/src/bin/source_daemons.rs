use rogue_gold::source_daemons::source_daemons_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_daemons_report()).unwrap()
    );
}
