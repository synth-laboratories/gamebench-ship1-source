use rogue_gold::source_scrolls::source_scrolls_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_scrolls_report()).unwrap()
    );
}
