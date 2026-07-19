use pokemon_emerald_littleroot_gold::run_entry;
use serde_json::{json, Value};
use std::io::{self, Read};

fn expand_program(steps: &[Value]) -> Result<Vec<Value>, String> {
    let mut expanded = Vec::new();
    for step in steps {
        if let Some(nested) = step.get("steps") {
            let repeat = step
                .get("repeat")
                .and_then(Value::as_u64)
                .ok_or_else(|| "replay group requires a non-negative repeat count".to_owned())?;
            let nested = nested
                .as_array()
                .ok_or_else(|| "replay group steps must be an array".to_owned())?;
            let nested = expand_program(nested)?;
            for _ in 0..repeat {
                expanded.extend(nested.iter().cloned());
            }
        } else {
            expanded.push(step.clone());
        }
    }
    Ok(expanded)
}

fn verify_subset(expected: &Value, actual: &Value, path: &str) -> Result<(), String> {
    match expected {
        Value::Object(expected) => {
            let actual = actual
                .as_object()
                .ok_or_else(|| format!("{path} expected an object, got {actual}"))?;
            for (key, expected) in expected {
                let actual = actual
                    .get(key)
                    .ok_or_else(|| format!("{path}.{key} was absent from replay output"))?;
                verify_subset(expected, actual, &format!("{path}.{key}"))?;
            }
            Ok(())
        }
        _ if expected == actual => Ok(()),
        _ => Err(format!("{path} expected {expected}, got {actual}")),
    }
}

fn main() -> Result<(), String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|error| error.to_string())?;
    let mut entry: Value = serde_json::from_str(&input).map_err(|error| error.to_string())?;
    let expected = entry.get("expected").cloned();
    if let Some(program) = entry.get("program") {
        let program = program
            .as_array()
            .ok_or_else(|| "replay program must be an array".to_owned())?;
        let inputs = expand_program(program)?;
        let entry = entry
            .as_object_mut()
            .ok_or_else(|| "scenario entry must be an object".to_owned())?;
        entry.remove("program");
        entry.remove("expected");
        entry.insert("inputs".to_owned(), Value::Array(inputs));
    }
    let mut output = run_entry(&entry)?;
    if let Some(expected) = expected {
        verify_subset(&expected, &output["readout"], "readout")?;
        let output = output
            .as_object_mut()
            .ok_or_else(|| "scenario output must be an object".to_owned())?;
        output.insert(
            "replay_verification".to_owned(),
            json!({ "passed": true }),
        );
    }
    println!("{}", serde_json::to_string(&output).map_err(|error| error.to_string())?);
    Ok(())
}
