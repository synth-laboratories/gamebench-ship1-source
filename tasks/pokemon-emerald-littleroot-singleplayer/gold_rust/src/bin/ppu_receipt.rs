//! Recompose an external, receipt-backed mode-0 PPU capture and report exact
//! RGB differences. This is a verification tool; it never stages receipt data
//! into the game binary.

use pokemon_emerald_littleroot_gold::native::{
    composite_gba_mode0_ppu_frame, gba_mode0_window_mask_rgb, GbaPpuRegisters,
};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

const WIDTH: usize = 240;
const HEIGHT: usize = 160;

fn required_u16(value: &Value, name: &str) -> Result<u16, String> {
    value[name]
        .as_u64()
        .and_then(|number| u16::try_from(number).ok())
        .ok_or_else(|| format!("receipt register {name} is missing or not u16"))
}

fn required_u16_array(value: &Value, name: &str, expected: usize) -> Result<Vec<u16>, String> {
    let values = value[name]
        .as_array()
        .ok_or_else(|| format!("receipt register {name} is missing or not an array"))?;
    if values.len() != expected {
        return Err(format!(
            "receipt register {name} has {} items, expected {expected}",
            values.len()
        ));
    }
    values
        .iter()
        .map(|item| {
            item.as_u64()
                .and_then(|number| u16::try_from(number).ok())
                .ok_or_else(|| format!("receipt register {name} contains a non-u16 value"))
        })
        .collect()
}

fn file_bytes(root: &Path, receipt: &Value, name: &str) -> Result<Vec<u8>, String> {
    let relative = receipt["files"][name]["path"]
        .as_str()
        .ok_or_else(|| format!("receipt file {name} has no path"))?;
    let path = root.join(relative);
    let bytes =
        fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
    let expected = receipt["files"][name]["bytes"]
        .as_u64()
        .and_then(|number| usize::try_from(number).ok())
        .ok_or_else(|| format!("receipt file {name} has no byte count"))?;
    if bytes.len() != expected {
        return Err(format!("receipt file {name} has wrong size"));
    }
    Ok(bytes)
}

fn region_diff(
    source: &[u8],
    actual: &[u8],
    x: usize,
    y: usize,
    width: usize,
    height: usize,
) -> Value {
    let mut differing_pixels = 0_u64;
    let mut differing_channels = 0_u64;
    let mut total_channel_delta = 0_u64;
    for row in y..y + height {
        for column in x..x + width {
            let offset = (row * WIDTH + column) * 3;
            let mut differs = false;
            for channel in 0..3 {
                let delta = source[offset + channel].abs_diff(actual[offset + channel]);
                differs |= delta != 0;
                differing_channels += u64::from(delta != 0);
                total_channel_delta += u64::from(delta);
            }
            differing_pixels += u64::from(differs);
        }
    }
    json!({
        "x": x, "y": y, "width": width, "height": height,
        "pixels": width * height,
        "differing_pixels": differing_pixels,
        "differing_channels": differing_channels,
        "total_channel_delta": total_channel_delta,
    })
}

fn rgb_sha256(rgb: &[u8]) -> String {
    format!("{:x}", Sha256::digest(rgb))
}

fn write_ppm(path: &Path, rgb: &[u8]) -> Result<(), String> {
    if path.exists() {
        return Err(format!("refusing to overwrite output: {}", path.display()));
    }
    let mut ppm = b"P6\n240 160\n255\n".to_vec();
    ppm.extend_from_slice(rgb);
    fs::write(path, ppm).map_err(|error| format!("cannot write {}: {error}", path.display()))
}

fn main() -> Result<(), String> {
    let arguments: Vec<_> = env::args().skip(1).collect();
    let receipt_path = arguments.first().ok_or_else(|| {
        "usage: ppu_receipt RECEIPT_JSON [OUTPUT_RGB] [--layers-dir DIR]".to_owned()
    })?;
    let mut output_path = None;
    let mut layers_dir = None;
    let mut index = 1;
    while index < arguments.len() {
        let argument = &arguments[index];
        if argument == "--layers-dir" {
            index += 1;
            let directory = arguments
                .get(index)
                .ok_or_else(|| "--layers-dir requires a directory".to_owned())?;
            if layers_dir.replace(PathBuf::from(directory)).is_some() {
                return Err("--layers-dir specified twice".to_owned());
            }
        } else if output_path.is_none() {
            output_path = Some(PathBuf::from(argument));
        } else {
            return Err(
                "usage: ppu_receipt RECEIPT_JSON [OUTPUT_RGB] [--layers-dir DIR]".to_owned(),
            );
        }
        index += 1;
    }
    let receipt_file = PathBuf::from(receipt_path);
    let root = receipt_file
        .parent()
        .ok_or_else(|| "receipt has no parent directory".to_owned())?;
    let receipt: Value = serde_json::from_slice(
        &fs::read(&receipt_file).map_err(|error| format!("cannot read receipt: {error}"))?,
    )
    .map_err(|error| format!("invalid receipt JSON: {error}"))?;
    if receipt["schema"] != "gamebench.pokemon_emerald.ppu_receipt.v2" {
        return Err("receipt has an unsupported schema".to_owned());
    }
    let registers = &receipt["registers"];
    let bgcnt = required_u16_array(registers, "bgcnt", 4)?;
    let offsets = required_u16_array(registers, "bg_offsets", 8)?;
    let ppu = GbaPpuRegisters {
        dispcnt: required_u16(registers, "dispcnt")?,
        bgcnt: [bgcnt[0], bgcnt[1], bgcnt[2], bgcnt[3]],
        bg_offsets: [
            offsets[0], offsets[1], offsets[2], offsets[3], offsets[4], offsets[5], offsets[6],
            offsets[7],
        ],
        win0h: required_u16(registers, "win0h")?,
        win1h: required_u16(registers, "win1h")?,
        win0v: required_u16(registers, "win0v")?,
        win1v: required_u16(registers, "win1v")?,
        winin: required_u16(registers, "winin")?,
        winout: required_u16(registers, "winout")?,
    };
    let vram = file_bytes(root, &receipt, "vram")?;
    let palette = file_bytes(root, &receipt, "palette")?;
    let oam = file_bytes(root, &receipt, "oam")?;
    let actual = composite_gba_mode0_ppu_frame(&vram, &palette, &oam, ppu)?;
    let source = file_bytes(root, &receipt, "rgb")?;
    if source.len() != WIDTH * HEIGHT * 3 {
        return Err("receipt RGB has wrong size".to_owned());
    }
    if let Some(output) = output_path {
        if output.exists() {
            return Err(format!(
                "refusing to overwrite output: {}",
                output.display()
            ));
        }
        fs::write(output, &actual).map_err(|error| format!("cannot write output: {error}"))?;
    }
    let mut layers = serde_json::Map::new();
    if let Some(directory) = layers_dir {
        if directory.exists() {
            return Err(format!(
                "refusing to reuse layer directory: {}",
                directory.display()
            ));
        }
        fs::create_dir_all(&directory)
            .map_err(|error| format!("cannot create layer directory: {error}"))?;
        let mut emit = |name: &str, image: Vec<u8>| -> Result<(), String> {
            let path = directory.join(format!("{name}.ppm"));
            write_ppm(&path, &image)?;
            layers.insert(
                name.to_owned(),
                json!({"path": path, "rgb_sha256": rgb_sha256(&image)}),
            );
            Ok(())
        };
        for bg in 0..4 {
            let mut isolated = ppu;
            isolated.dispcnt = (ppu.dispcnt & !0x1f00) | (1 << (8 + bg));
            emit(
                &format!("bg{bg}"),
                composite_gba_mode0_ppu_frame(&vram, &palette, &oam, isolated)?,
            )?;
        }
        let mut obj = ppu;
        obj.dispcnt = (ppu.dispcnt & !0x1f00) | (1 << 12);
        emit(
            "obj",
            composite_gba_mode0_ppu_frame(&vram, &palette, &oam, obj)?,
        )?;
        emit("window_mask", gba_mode0_window_mask_rgb(&vram, &oam, ppu)?)?;
        emit("final", actual.clone())?;
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema": "gamebench.pokemon_emerald.ppu_receipt_comparison.v2",
            "receipt": receipt_file,
            "vblank": receipt["vblank"],
            "source_rgb_sha256": receipt["frame_rgb_sha256"],
            "layer_artifacts": layers,
            "regions": {
                "full_frame": region_diff(&source, &actual, 0, 0, WIDTH, HEIGHT),
                "battlefield": region_diff(&source, &actual, 0, 0, WIDTH, 112),
                "command_ui": region_diff(&source, &actual, 0, 112, WIDTH, 48),
                "upper_half": region_diff(&source, &actual, 0, 0, WIDTH, 80),
                "lower_half": region_diff(&source, &actual, 0, 80, WIDTH, 80),
            },
        }))
        .map_err(|error| error.to_string())?
    );
    Ok(())
}
