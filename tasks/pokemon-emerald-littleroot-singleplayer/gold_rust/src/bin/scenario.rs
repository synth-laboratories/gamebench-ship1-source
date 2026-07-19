use pokemon_emerald_littleroot_gold::run_entry;
use serde_json::Value;
use std::io::{self, Read};

fn main() -> Result<(), String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|error| error.to_string())?;
    let entry: Value = serde_json::from_str(&input).map_err(|error| error.to_string())?;
    let output = run_entry(&entry)?;
    println!("{}", serde_json::to_string(&output).map_err(|error| error.to_string())?);
    Ok(())
}
