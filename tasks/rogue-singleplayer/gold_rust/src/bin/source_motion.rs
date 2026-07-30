use rogue_gold::source_motion::source_motion_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_motion_report()).unwrap()
    );
}
