use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde_json::json;

const GRASS_PALETTE_B64: &str = include_str!("../../assets/battle_tall_grass_palette.pal.b64");

fn main() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let palette_path = args.next().ok_or_else(|| {
        "usage: battle_palette_probe RECEIPT_PALETTE_BIN [SOURCE_JASC_PALETTE]".to_owned()
    })?;
    let source_path = args.next();
    let actual =
        std::fs::read(&palette_path).map_err(|error| format!("{palette_path}: {error}"))?;
    if actual.len() != 0x400 {
        return Err(format!(
            "{palette_path} has {} bytes, expected 1024",
            actual.len()
        ));
    }
    let source = if let Some(source_path) = source_path.as_deref() {
        std::fs::read(source_path).map_err(|error| format!("{source_path}: {error}"))?
    } else {
        STANDARD
            .decode(
                GRASS_PALETTE_B64
                    .bytes()
                    .filter(|byte| !byte.is_ascii_whitespace())
                    .collect::<Vec<_>>(),
            )
            .map_err(|error| error.to_string())?
    };
    let text = std::str::from_utf8(&source).map_err(|error| error.to_string())?;
    let mut lines = text.lines();
    if lines.next() != Some("JASC-PAL")
        || lines.next() != Some("0100")
        || lines.next() != Some("48")
    {
        return Err("unexpected staged tall-grass palette format".to_owned());
    }
    let expected = lines
        .map(|line| {
            let channels = line
                .split_whitespace()
                .map(|value| value.parse::<u8>().map_err(|error| error.to_string()))
                .collect::<Result<Vec<_>, _>>()?;
            let [r, g, b] = channels.as_slice() else {
                return Err("invalid JASC color".to_owned());
            };
            Ok(u16::from(*r >> 3) | (u16::from(*g >> 3) << 5) | (u16::from(*b >> 3) << 10))
        })
        .collect::<Result<Vec<_>, String>>()?;
    let entries = expected
        .iter()
        .enumerate()
        .map(|(index, expected)| {
            let offset = (2 * 16 + index) * 2;
            let observed = u16::from_le_bytes([actual[offset], actual[offset + 1]]);
            json!({
                "index": index,
                "expected_bgr555": format!("{expected:#06x}"),
                "observed_bgr555": format!("{observed:#06x}"),
                "matches": observed == *expected,
            })
        })
        .collect::<Vec<_>>();
    let matches = entries
        .iter()
        .filter(|entry| entry["matches"] == true)
        .count();
    println!("{}", serde_json::to_string(&json!({
        "schema": "gamebench.pokemon_emerald.battle_palette_probe.v1",
        "palette": palette_path,
        "source": source_path.unwrap_or_else(|| "graphics/battle_environment/tall_grass/palette.pal".to_owned()),
        "source_bank": 2,
        "matches": matches,
        "total": entries.len(),
        "entries": entries,
    })).map_err(|error| error.to_string())?);
    Ok(())
}
