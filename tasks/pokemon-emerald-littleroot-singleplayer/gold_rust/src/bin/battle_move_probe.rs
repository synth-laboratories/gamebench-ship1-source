use pokemon_emerald_littleroot_gold::native::build_emerald_battle_move_ui_ppu;

fn main() -> Result<(), String> {
    let source_vram = std::env::args()
        .nth(1)
        .ok_or_else(|| {
            "usage: battle_move_probe SOURCE_VRAM [OUTPUT_VRAM] [SOURCE_PALETTE]".to_owned()
        })?;
    let output_vram = std::env::args().nth(2);
    let source_palette = std::env::args()
        .nth(3)
        .map(std::fs::read)
        .transpose()
        .map_err(|error| error.to_string())?;
    let source = std::fs::read(&source_vram).map_err(|error| error.to_string())?;
    let (memory, _) = build_emerald_battle_move_ui_ppu(0, &[("SCRATCH", 35), ("GROWL", 40)])?;
    let ranges = [
        ("bg0_tiles", 0x0000, 0x4000),
        ("bg0_map", 0xc000, 0xc800),
    ];
    for (name, start, end) in ranges {
        let actual = &memory.vram[start..end];
        let expected = &source[start..end];
        let differences = actual.iter().zip(expected).filter(|(a, b)| a != b).count();
        println!("{name}: {differences}/{} bytes differ", end - start);
    }
    if let Some(path) = output_vram {
        std::fs::write(path, &memory.vram).map_err(|error| error.to_string())?;
    }
    if let Some(palette) = source_palette {
        for bank in 0..16 {
            let start = bank * 32;
            let actual = &memory.palette[start..start + 32];
            let expected = &palette[start..start + 32];
            let differences = actual.iter().zip(expected).filter(|(a, b)| a != b).count();
            if differences != 0 {
                println!("palette bank {bank}: {differences}/32 bytes differ");
                println!(
                    "  source={}",
                    expected
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
                );
                println!(
                    "  rust  ={}",
                    actual
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
                );
            }
        }
    }
    Ok(())
}
