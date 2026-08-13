use pokemon_emerald_littleroot_gold::{
    native::build_emerald_battle_action_ui_ppu, FRAME_BYTES, FRAME_WIDTH,
};
use serde_json::json;

fn main() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let Some(reference_path) = args.next() else {
        return Err("usage: action_ui_probe SOURCE_RGB [PLAYER] [CURSOR]".to_owned());
    };
    let player = args.next().unwrap_or_else(|| "TORCHIC".to_owned());
    let cursor = args
        .next()
        .map(|value| value.parse::<u8>())
        .transpose()
        .map_err(|error| format!("invalid cursor: {error}"))?
        .unwrap_or(0);
    let output_path = args.next();
    let vram_output_path = args.next();
    let expected =
        std::fs::read(&reference_path).map_err(|error| format!("{reference_path}: {error}"))?;
    if expected.len() != FRAME_BYTES {
        return Err(format!(
            "{reference_path} is {} bytes, expected {FRAME_BYTES}",
            expected.len()
        ));
    }
    let (memory, registers) = build_emerald_battle_action_ui_ppu(cursor, &player)?;
    let actual = memory.render(registers)?;
    if let Some(output_path) = output_path.as_deref() {
        std::fs::write(output_path, &actual).map_err(|error| format!("{output_path}: {error}"))?;
    }
    if let Some(vram_output_path) = vram_output_path.as_deref() {
        std::fs::write(vram_output_path, &memory.vram)
            .map_err(|error| format!("{vram_output_path}: {error}"))?;
    }
    let mut changed_pixels = 0_usize;
    let mut changed_channels = 0_usize;
    let mut total_absolute_delta = 0_u64;
    for y in 112..160 {
        for x in 0..FRAME_WIDTH {
            let offset = (y * FRAME_WIDTH + x) * 3;
            let same = actual[offset..offset + 3] == expected[offset..offset + 3];
            if !same {
                changed_pixels += 1;
            }
            for channel in 0..3 {
                let delta = actual[offset + channel].abs_diff(expected[offset + channel]);
                changed_channels += usize::from(delta != 0);
                total_absolute_delta += u64::from(delta);
            }
        }
    }
    println!(
        "{}",
        serde_json::to_string(&json!({
            "schema": "gamebench.pokemon_emerald.action_ui_probe.v1",
            "reference": reference_path,
            "player": player,
            "cursor": cursor,
            "output": output_path,
            "vram_output": vram_output_path,
            "region": {"x": 0, "y": 112, "width": 240, "height": 48},
            "total_pixels": 240 * 48,
            "changed_pixels": changed_pixels,
            "changed_channels": changed_channels,
            "total_absolute_delta": total_absolute_delta,
        }))
        .map_err(|error| error.to_string())?
    );
    Ok(())
}
