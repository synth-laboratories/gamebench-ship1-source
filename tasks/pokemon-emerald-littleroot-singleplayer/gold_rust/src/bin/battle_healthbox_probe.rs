use pokemon_emerald_littleroot_gold::{
    native::build_emerald_grass_command_healthbox_ppu, FRAME_BYTES, FRAME_WIDTH,
};
use serde_json::json;

fn main() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let reference_path = args.next().ok_or_else(|| {
        "usage: battle_healthbox_probe SOURCE_RGB [PLAYER] [CURSOR] [OUTPUT_RGB]".to_owned()
    })?;
    let player = args.next().unwrap_or_else(|| "TORCHIC".to_owned());
    let cursor = args
        .next()
        .map(|value| value.parse::<u8>())
        .transpose()
        .map_err(|error| format!("invalid cursor: {error}"))?
        .unwrap_or(0);
    let output_path = args.next();
    let expected =
        std::fs::read(&reference_path).map_err(|error| format!("{reference_path}: {error}"))?;
    if expected.len() != FRAME_BYTES {
        return Err(format!(
            "{reference_path} is {} bytes, expected {FRAME_BYTES}",
            expected.len()
        ));
    }
    let (memory, registers) = build_emerald_grass_command_healthbox_ppu(cursor, &player)?;
    let actual = memory.render(registers)?;
    if let Some(output_path) = output_path.as_deref() {
        std::fs::write(output_path, &actual).map_err(|error| format!("{output_path}: {error}"))?;
    }
    let regions = [
        ("opponent_healthbox", 12, 14, 128, 32),
        ("player_healthbox", 126, 72, 114, 40),
        ("battlefield", 0, 0, 240, 112),
        ("action_ui", 0, 112, 240, 48),
    ].into_iter().map(|(name, left, top, width, height)| {
        let mut changed_pixels = 0_usize;
        let mut changed_channels = 0_usize;
        for y in top..top + height {
            for x in left..left + width {
                let offset = (y * FRAME_WIDTH + x) * 3;
                changed_pixels += usize::from(actual[offset..offset + 3] != expected[offset..offset + 3]);
                changed_channels += actual[offset..offset + 3].iter().zip(&expected[offset..offset + 3])
                    .filter(|(left, right)| left != right).count();
            }
        }
        json!({"name": name, "changed_pixels": changed_pixels, "changed_channels": changed_channels})
    }).collect::<Vec<_>>();
    println!(
        "{}",
        serde_json::to_string(&json!({
            "schema": "gamebench.pokemon_emerald.battle_healthbox_probe.v1",
            "reference": reference_path,
            "player": player,
            "cursor": cursor,
            "output": output_path,
            "regions": regions,
        }))
        .map_err(|error| error.to_string())?
    );
    Ok(())
}
