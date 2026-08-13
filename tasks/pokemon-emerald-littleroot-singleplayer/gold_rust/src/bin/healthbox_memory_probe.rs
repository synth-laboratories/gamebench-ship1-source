use pokemon_emerald_littleroot_gold::native::{
    build_emerald_grass_command_healthbox_ppu, build_emerald_settled_command_ppu,
};
use pokemon_emerald_littleroot_gold::world::StarterSpecies;

fn main() -> Result<(), String> {
    let receipt = std::env::args()
        .nth(1)
        .ok_or_else(|| "usage: healthbox_memory_probe RECEIPT_DIR".to_owned())?;
    let mode = std::env::args().nth(2);
    let (memory, _) = match mode.as_deref() {
        Some("wild") => build_emerald_settled_command_ppu(
            StarterSpecies::Torchic,
            5,
            15,
            19,
            "POOCHYENA",
            2,
            13,
            13,
            true,
        )?,
        Some("rival") => build_emerald_settled_command_ppu(
            StarterSpecies::Torchic,
            6,
            15,
            21,
            "MUDKIP",
            5,
            20,
            20,
            false,
        )?,
        _ => build_emerald_grass_command_healthbox_ppu(0, "TORCHIC")?,
    };
    for (name, offset, length) in [
        ("player_tiles", 0, 0x1000),
        ("opponent_tiles", 0x1000, 0x800),
        ("healthbar_tiles", 0x2000, 17 * 32),
    ] {
        let reference =
            std::fs::read(format!("{receipt}/vram.bin")).map_err(|error| error.to_string())?;
        let actual = &memory.vram[0x10000 + offset..0x10000 + offset + length];
        let expected = &reference[0x10000 + offset..0x10000 + offset + length];
        let equal = actual.iter().zip(expected).filter(|(a, b)| a == b).count();
        let first = actual.iter().zip(expected).position(|(a, b)| a != b);
        println!("{name}: {equal}/{length} bytes exact; first differing byte {first:?}");
    }
    let reference =
        std::fs::read(format!("{receipt}/vram.bin")).map_err(|error| error.to_string())?;
    for (name, tile) in [("opponent_sprite", 341usize), ("player_sprite", 405usize)] {
        let actual = &memory.vram[0x10000 + tile * 32..0x10000 + tile * 32 + 0x800];
        let expected = &reference[0x10000 + tile * 32..0x10000 + tile * 32 + 0x800];
        println!(
            "{name}: {}/2048 bytes exact",
            actual.iter().zip(expected).filter(|(a, b)| a == b).count()
        );
    }
    let reference =
        std::fs::read(format!("{receipt}/oam.bin")).map_err(|error| error.to_string())?;
    for entry in [9usize, 10] {
        let actual = &memory.oam[entry * 8..entry * 8 + 8];
        let expected = &reference[entry * 8..entry * 8 + 8];
        println!(
            "oam_{entry}: {}/8 bytes exact actual={} expected={}",
            actual.iter().zip(expected).filter(|(a, b)| a == b).count(),
            actual
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<String>(),
            expected
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<String>()
        );
    }
    for (name, offset, length) in [
        ("player_name", 0x40, 6 * 32),
        ("player_name_tail", 0x800, 32),
        ("player_level", 0x820, 3 * 32),
        ("current_hp_head", 0x3e0, 32),
        ("current_hp_tail", 0xb00, 2 * 32),
        ("maximum_hp", 0xb40, 2 * 32),
        ("opponent_name", 0x1020, 7 * 32),
        ("opponent_level", 0x1400, 3 * 32),
    ] {
        let reference =
            std::fs::read(format!("{receipt}/vram.bin")).map_err(|error| error.to_string())?;
        let actual = &memory.vram[0x10000 + offset..0x10000 + offset + length];
        let expected = &reference[0x10000 + offset..0x10000 + offset + length];
        println!(
            "{name}: {}/{} bytes exact",
            actual.iter().zip(expected).filter(|(a, b)| a == b).count(),
            length
        );
    }
    let reference =
        std::fs::read(format!("{receipt}/palette.bin")).map_err(|error| error.to_string())?;
    let actual = &memory.palette[0x200 + 4 * 32..0x200 + 5 * 32];
    let expected = &reference[0x200 + 4 * 32..0x200 + 5 * 32];
    println!(
        "healthbox_palette: {}/32 bytes exact; first differing byte {:?}",
        actual.iter().zip(expected).filter(|(a, b)| a == b).count(),
        actual.iter().zip(expected).position(|(a, b)| a != b)
    );
    let actual = &memory.palette[0x200 + 5 * 32..0x200 + 6 * 32];
    let expected = &reference[0x200 + 5 * 32..0x200 + 6 * 32];
    println!(
        "healthbar_palette: {}/32 bytes exact; first differing byte {:?}",
        actual.iter().zip(expected).filter(|(a, b)| a == b).count(),
        actual.iter().zip(expected).position(|(a, b)| a != b)
    );
    for (name, bank) in [
        ("player_battler_palette", 0usize),
        ("opponent_battler_palette", 1),
    ] {
        let offset = 0x200 + bank * 32;
        let actual = &memory.palette[offset..offset + 32];
        let expected = &reference[offset..offset + 32];
        println!(
            "{name}: {}/32 bytes exact; first differing byte {:?}",
            actual.iter().zip(expected).filter(|(a, b)| a == b).count(),
            actual.iter().zip(expected).position(|(a, b)| a != b)
        );
    }
    Ok(())
}
