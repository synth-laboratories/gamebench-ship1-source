use rogue_gold::source_pack::source_pack_report;

fn main() {
    println!("{}", serde_json::to_string(&source_pack_report()).unwrap());
}
