use frogs_gold::FrogsSession;
use serde_json::{json, Value};
use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let entry: Value = serde_json::from_str(&input).unwrap();
    let session = FrogsSession::reset_from_entry(&entry);
    let scenario_id = entry
        .get("scenario_id")
        .and_then(Value::as_str)
        .unwrap_or("manual");
    println!(
        "{}",
        serde_json::to_string(&json!({
            "scenario_id": scenario_id,
            "events": session.legacy_strings(),
            "nev": session.events,
            "state": {
                "public": session.readout()["public"],
                "private": session.readout()["private"]
            },
            "readout": session.readout()
        }))
        .unwrap()
    );
}
