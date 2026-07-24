use rogue_gold::source_fight::source_fight_report;

fn main() {
    println!("{}", serde_json::to_string(&source_fight_report()).unwrap());
}
