use rogue_gold::source_do_chase::source_do_chase_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_do_chase_report()).unwrap()
    );
}
