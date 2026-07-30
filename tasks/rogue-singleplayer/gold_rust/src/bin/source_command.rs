use rogue_gold::source_command::source_command_report;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&source_command_report()).unwrap()
    );
}
