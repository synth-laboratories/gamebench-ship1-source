use base64::{engine::general_purpose::STANDARD, Engine as _};
use pokemon_emerald_littleroot_gold::{
    frame_sha256, pixel_diff, run_entry, LittlerootSession, OpeningCheckpoint, StepRequest,
    FRAME_BYTES,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::io::{self, Read};
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct FrameManifest {
    traces: Vec<FrameTrace>,
}

#[derive(Debug, Deserialize)]
struct FrameTrace {
    id: String,
    source_state: String,
    #[serde(default)]
    input: Vec<StepRequest>,
    #[serde(default)]
    replay: Option<String>,
    #[serde(default)]
    input_limit: Option<usize>,
    frame: String,
    sha256: String,
}

fn checkpoint_for_source_state(source_state: &str) -> Result<OpeningCheckpoint, String> {
    if source_state.contains("00_init") {
        Ok(OpeningCheckpoint::TitleMenu)
    } else if source_state.contains("01_tutorial") {
        Ok(OpeningCheckpoint::TruckArrival)
    } else if source_state.contains("02_starter") {
        Ok(OpeningCheckpoint::BedroomIdle)
    } else if source_state.contains("03_birch") {
        Ok(OpeningCheckpoint::BirchLabExterior)
    } else if source_state.contains("04_rival") {
        Ok(OpeningCheckpoint::RivalOutsideLab)
    } else {
        Err(format!(
            "no Rust checkpoint is registered for {source_state}"
        ))
    }
}

fn decode_reference_frame(task_root: &Path, reference: &str) -> Result<Vec<u8>, String> {
    let path = task_root.join(reference);
    let bytes = std::fs::read(&path).map_err(|error| format!("{}: {error}", path.display()))?;
    if reference.ends_with(".rgb") {
        if bytes.len() != FRAME_BYTES {
            return Err(format!(
                "{} is {} bytes, expected {FRAME_BYTES}",
                path.display(),
                bytes.len()
            ));
        }
        return Ok(bytes);
    }
    if reference.ends_with(".rgb.b64") {
        let encoded: Vec<u8> = bytes
            .into_iter()
            .filter(|byte| !byte.is_ascii_whitespace())
            .collect();
        let frame = STANDARD
            .decode(encoded)
            .map_err(|error| format!("{}: {error}", path.display()))?;
        if frame.len() != FRAME_BYTES {
            return Err(format!(
                "{} decodes to {} bytes, expected {FRAME_BYTES}",
                path.display(),
                frame.len()
            ));
        }
        return Ok(frame);
    }
    if !reference.ends_with(".png.b64") {
        return Err(format!("unsupported reference format: {}", path.display()));
    }
    let encoded: Vec<u8> = bytes
        .into_iter()
        .filter(|byte| !byte.is_ascii_whitespace())
        .collect();
    let png_bytes = STANDARD
        .decode(encoded)
        .map_err(|error| format!("{}: {error}", path.display()))?;
    let decoder = png::Decoder::new(std::io::Cursor::new(png_bytes));
    let mut reader = decoder
        .read_info()
        .map_err(|error| format!("{}: {error}", path.display()))?;
    let mut buffer = vec![0; reader.output_buffer_size()];
    let info = reader
        .next_frame(&mut buffer)
        .map_err(|error| format!("{}: {error}", path.display()))?;
    if info.color_type != png::ColorType::Rgb || info.bit_depth != png::BitDepth::Eight {
        return Err(format!("{} must decode as RGB8", path.display()));
    }
    let frame = buffer[..info.buffer_size()].to_vec();
    if frame.len() != FRAME_BYTES {
        return Err(format!(
            "{} decodes to {} bytes, expected {FRAME_BYTES}",
            path.display(),
            frame.len()
        ));
    }
    Ok(frame)
}

fn verify_manifest(manifest_path: &Path) -> Result<(), String> {
    let manifest_bytes = std::fs::read(manifest_path)
        .map_err(|error| format!("{}: {error}", manifest_path.display()))?;
    let manifest: FrameManifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("{}: {error}", manifest_path.display()))?;
    let task_root = manifest_path.ancestors().nth(4).ok_or_else(|| {
        format!(
            "{} is not below fixtures/gold/frames",
            manifest_path.display()
        )
    })?;
    let mut failures = Vec::new();
    for trace in &manifest.traces {
        let checkpoint = checkpoint_for_source_state(&trace.source_state)?;
        let mut session = LittlerootSession::from_checkpoint(checkpoint);
        for input in trace_inputs(trace, task_root)? {
            session.step(input);
        }
        let actual_sha256 = frame_sha256(session.frame_rgb());
        let reference = decode_reference_frame(task_root, &trace.frame)?;
        let diff = pixel_diff(session.frame_rgb(), &reference);
        if actual_sha256 != trace.sha256 || diff.differing_pixels != 0 {
            failures.push(json!({
                "id": trace.id,
                "expected_sha256": trace.sha256,
                "actual_sha256": actual_sha256,
                "pixel_diff": diff,
            }));
        }
    }
    println!(
        "{}",
        serde_json::to_string(&json!({
            "manifest": manifest_path,
            "traces": manifest.traces.len(),
            "passed": manifest.traces.len() - failures.len(),
            "failures": failures,
        }))
        .map_err(|error| error.to_string())?
    );
    if failures.is_empty() {
        Ok(())
    } else {
        Err(format!("{} manifest traces failed", failures.len()))
    }
}

fn trace_inputs(trace: &FrameTrace, task_root: &Path) -> Result<Vec<StepRequest>, String> {
    let Some(replay) = trace.replay.as_deref() else {
        if trace.input_limit.is_some() {
            return Err(format!("{} sets input_limit without replay", trace.id));
        }
        return Ok(trace.input.clone());
    };
    if !trace.input.is_empty() {
        return Err(format!("{} mixes direct input and replay input", trace.id));
    }
    let replay_path = task_root.join(replay);
    let replay: Value = serde_json::from_slice(
        &std::fs::read(&replay_path).map_err(|error| format!("{}: {error}", replay_path.display()))?,
    )
    .map_err(|error| format!("{}: {error}", replay_path.display()))?;
    let program = replay
        .get("program")
        .and_then(Value::as_array)
        .ok_or_else(|| format!("{} has no replay program", replay_path.display()))?;
    let mut inputs = expand_program(program)?
        .into_iter()
        .map(serde_json::from_value)
        .collect::<Result<Vec<StepRequest>, _>>()
        .map_err(|error| format!("{} contains an invalid step: {error}", replay_path.display()))?;
    if let Some(limit) = trace.input_limit {
        if limit > inputs.len() {
            return Err(format!("{} input_limit exceeds {} replay steps", trace.id, inputs.len()));
        }
        inputs.truncate(limit);
    }
    Ok(inputs)
}

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
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("--verify-manifest") {
        let manifest_path = args.get(2).map(PathBuf::from).unwrap_or_else(|| {
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .expect("gold_rust must have a task parent")
                .join("fixtures/gold/frames/manifest.json")
        });
        return verify_manifest(&manifest_path);
    }
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
        output.insert("replay_verification".to_owned(), json!({ "passed": true }));
    }
    println!(
        "{}",
        serde_json::to_string(&output).map_err(|error| error.to_string())?
    );
    Ok(())
}
