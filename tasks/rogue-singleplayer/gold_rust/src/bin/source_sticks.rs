use rogue_gold::source_sticks::source_sticks_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_sticks_report()).unwrap()
    );
}
