use rogue_gold::source_chase::source_chase_report;

fn main() {
    println!("{}", serde_json::to_string(&source_chase_report()).unwrap());
}
