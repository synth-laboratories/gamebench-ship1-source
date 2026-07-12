use rogue_gold::source_rings::source_rings_report;

fn main() {
    println!("{}", serde_json::to_string(&source_rings_report()).unwrap());
}
