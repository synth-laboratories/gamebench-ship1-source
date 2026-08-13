use pokemon_emerald_littleroot_gold::native::build_emerald_grass_command_scene_ppu;

fn main() -> Result<(), String> {
    let output = std::env::args()
        .nth(1)
        .ok_or_else(|| "usage: battle_ppu_dump OUTPUT_DIR".to_owned())?;
    let output = std::path::Path::new(&output);
    std::fs::create_dir_all(output).map_err(|error| error.to_string())?;
    let (memory, _registers) = build_emerald_grass_command_scene_ppu(0, "TORCHIC")?;
    std::fs::write(output.join("vram.bin"), &memory.vram).map_err(|error| error.to_string())?;
    std::fs::write(output.join("palette.bin"), &memory.palette)
        .map_err(|error| error.to_string())?;
    std::fs::write(output.join("oam.bin"), &memory.oam).map_err(|error| error.to_string())?;
    Ok(())
}
