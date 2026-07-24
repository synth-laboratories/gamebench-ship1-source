use flate2::write::ZlibEncoder;
use flate2::Compression;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::io::Write;
use std::process::Command;

pub type Rgb = (u8, u8, u8);
pub type RgbRows = Vec<Vec<Rgb>>;
pub type RgbFrame = (u32, u32, RgbRows);

pub const DEFAULT_RENDER_TILE_SIZE: u32 = 16;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum RenderMode {
    #[default]
    Auto,
    Symbolic,
    Sprites,
}

pub const UNKNOWN_RGB: Rgb = (30, 34, 38);
const PLAYER_RGB: Rgb = (246, 240, 205);
const ENTITY_RGB: Rgb = (42, 25, 20);

fn tile_rgb(kind: &str) -> Rgb {
    match kind {
        "water" => (46, 112, 176),
        "grass" => (74, 152, 74),
        "stone" => (116, 120, 126),
        "path" => (137, 116, 84),
        "sand" => (202, 186, 124),
        "tree" => (34, 105, 52),
        "lava" => (211, 69, 38),
        "coal" => (53, 57, 61),
        "iron" => (168, 131, 84),
        "diamond" => (86, 192, 202),
        "table" => (129, 83, 45),
        "furnace" => (78, 72, 66),
        "sapphire" => (70, 101, 204),
        "ruby" => (196, 50, 73),
        "chest" => (160, 96, 36),
        _ => UNKNOWN_RGB,
    }
}

pub fn render_rgb_frame_from_readout(readout: &Value, tile_size: u32, mode: RenderMode) -> RgbFrame {
    let resolved = match mode {
        RenderMode::Auto => {
            if crate::sprites::sprites_available() {
                RenderMode::Sprites
            } else {
                RenderMode::Symbolic
            }
        }
        other => other,
    };
    match resolved {
        RenderMode::Sprites => crate::sprites::render_rgb_frame_sprites_from_readout(readout, tile_size),
        RenderMode::Symbolic | RenderMode::Auto => {
            render_rgb_frame_symbolic_from_readout(readout, tile_size)
        }
    }
}

fn render_rgb_frame_symbolic_from_readout(readout: &Value, tile_size: u32) -> RgbFrame {
    let observation = readout
        .get("observation")
        .filter(|value| value.is_object())
        .unwrap_or(readout);
    let view = observation.get("view").and_then(Value::as_object);
    let Some(view) = view else {
        return (1, 1, vec![vec![UNKNOWN_RGB]]);
    };
    let tiles = view
        .get("tiles")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    if tiles.is_empty() {
        return (1, 1, vec![vec![UNKNOWN_RGB]]);
    }

    let mut xs = Vec::with_capacity(tiles.len());
    let mut ys = Vec::with_capacity(tiles.len());
    let mut by_pos: HashMap<(i64, i64), Value> = HashMap::new();
    for tile in &tiles {
        let pos = tile.get("pos").and_then(Value::as_array);
        let Some(pos) = pos else { continue };
        if pos.len() < 2 {
            continue;
        }
        let x = pos[0].as_i64().unwrap_or(0);
        let y = pos[1].as_i64().unwrap_or(0);
        xs.push(x);
        ys.push(y);
        by_pos.insert((x, y), tile.clone());
    }
    if xs.is_empty() {
        return (1, 1, vec![vec![UNKNOWN_RGB]]);
    }

    let min_x = *xs.iter().min().unwrap();
    let max_x = *xs.iter().max().unwrap();
    let min_y = *ys.iter().min().unwrap();
    let max_y = *ys.iter().max().unwrap();
    let grid_width = (max_x - min_x + 1) as u32;
    let grid_height = (max_y - min_y + 1) as u32;

    let player_pos = observation
        .get("player")
        .and_then(|player| player.get("pos"))
        .and_then(Value::as_array)
        .map(|pos| (pos[0].as_i64().unwrap_or(0), pos[1].as_i64().unwrap_or(0)))
        .unwrap_or((0, 0));

    let mut entity_pos = HashSet::new();
    if let Some(entities) = view.get("entities").and_then(Value::as_array) {
        for entity in entities {
            if let Some(pos) = entity.get("pos").and_then(Value::as_array) {
                if pos.len() >= 2 {
                    entity_pos.insert((pos[0].as_i64().unwrap_or(0), pos[1].as_i64().unwrap_or(0)));
                }
            }
        }
    }

    let mut pixel_rows: RgbRows = Vec::new();
    for y in min_y..=max_y {
        let mut tile_row: Vec<Rgb> = Vec::new();
        for x in min_x..=max_x {
            let rgb = if (x, y) == player_pos {
                PLAYER_RGB
            } else if entity_pos.contains(&(x, y)) {
                ENTITY_RGB
            } else {
                let kind = by_pos
                    .get(&(x, y))
                    .and_then(|tile| tile.get("kind"))
                    .and_then(Value::as_str)
                    .unwrap_or("unknown");
                tile_rgb(kind)
            };
            tile_row.extend(std::iter::repeat_n(rgb, tile_size as usize));
        }
        for _ in 0..tile_size {
            pixel_rows.push(tile_row.clone());
        }
    }

    (
        grid_width * tile_size,
        grid_height * tile_size,
        pixel_rows,
    )
}

pub fn encode_png_rgb(width: u32, height: u32, rows: &RgbRows) -> Vec<u8> {
    let mut raw = Vec::new();
    for row in rows {
        raw.push(0);
        for (red, green, blue) in row {
            raw.extend([*red, *green, *blue]);
        }
    }
    let header = [
        (width >> 24) as u8,
        (width >> 16) as u8,
        (width >> 8) as u8,
        width as u8,
        (height >> 24) as u8,
        (height >> 16) as u8,
        (height >> 8) as u8,
        height as u8,
        8,
        2,
        0,
        0,
        0,
    ];
    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::new(6));
    encoder.write_all(&raw).unwrap();
    let idat = encoder.finish().unwrap();
    let mut out = Vec::new();
    out.extend(b"\x89PNG\r\n\x1a\n");
    out.extend(png_chunk(b"IHDR", &header));
    out.extend(png_chunk(b"IDAT", &idat));
    out.extend(png_chunk(b"IEND", &[]));
    out
}

fn png_chunk(kind: &[u8; 4], payload: &[u8]) -> Vec<u8> {
    let mut chunk = Vec::new();
    chunk.extend((payload.len() as u32).to_be_bytes());
    chunk.extend(kind);
    chunk.extend(payload);
    let mut hasher = crc32fast::Hasher::new();
    hasher.update(kind);
    hasher.update(payload);
    chunk.extend(hasher.finalize().to_be_bytes());
    chunk
}

pub fn encode_gif_rgb_frames(frames: &[RgbFrame], delay_cs: u16) -> Vec<u8> {
    let owned_fallback = (1_u32, 1_u32, vec![vec![UNKNOWN_RGB]]);
    let mut usable: Vec<&RgbFrame> = frames
        .iter()
        .filter(|frame| frame.0 > 0 && frame.1 > 0 && !frame.2.is_empty())
        .collect();
    if usable.is_empty() {
        usable = vec![&owned_fallback];
    }
    let (width, height, _) = *usable[0];
    usable.retain(|frame| frame.0 == width && frame.1 == height);

    let mut palette: Vec<Rgb> = Vec::new();
    let mut palette_index: BTreeMap<Rgb, u8> = BTreeMap::new();
    for (_, _, rows) in &usable {
        for row in rows {
            for &rgb in row {
                if !palette_index.contains_key(&rgb) {
                    if palette.len() >= 256 {
                        panic!("GIF palette cannot exceed 256 colors");
                    }
                    palette_index.insert(rgb, palette.len() as u8);
                    palette.push(rgb);
                }
            }
        }
    }

    let mut color_count = 2usize;
    while color_count < palette.len() {
        color_count *= 2;
    }
    color_count = color_count.clamp(2, 256);
    palette.extend(std::iter::repeat((0, 0, 0)).take(color_count.saturating_sub(palette.len())));

    let color_bits = usize::max(1, (color_count - 1).ilog2() as usize + 1);
    let min_code_size = 2_u8.max(color_bits as u8);
    let packed_field =
        0x80_u8 | (((color_bits - 1) as u8) << 4) | ((int_bit_length(color_count) - 2) as u8 & 0x07);

    let mut header = Vec::new();
    header.extend(b"GIF89a");
    header.extend((width as u16).to_le_bytes());
    header.extend((height as u16).to_le_bytes());
    header.push(packed_field);
    header.extend([0x00, 0x00]);
    for (red, green, blue) in &palette {
        header.extend([*red, *green, *blue]);
    }
    header.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00");

    let delay = delay_cs.clamp(1, 65535);
    for (_, _, rows) in usable {
        let indexed: Vec<u8> = rows
            .iter()
            .flat_map(|row| row.iter().map(|rgb| palette_index[rgb]))
            .collect();
        header.extend(b"\x21\xf9\x04\x00");
        header.extend(delay.to_le_bytes());
        header.extend([0x00, 0x00]);
        header.push(0x2C);
        header.extend((0_u16).to_le_bytes());
        header.extend((0_u16).to_le_bytes());
        header.extend((width as u16).to_le_bytes());
        header.extend((height as u16).to_le_bytes());
        header.push(0);
        header.push(min_code_size);
        let encoded = gif_lzw_encode(&indexed, min_code_size);
        for chunk in encoded.chunks(255) {
            header.push(chunk.len() as u8);
            header.extend(chunk);
        }
        header.push(0);
    }
    header.push(0x3B);
    header
}

fn int_bit_length(value: usize) -> usize {
    if value <= 1 {
        1
    } else {
        usize::BITS as usize - (value - 1).leading_zeros() as usize
    }
}

fn gif_lzw_encode(indices: &[u8], min_code_size: u8) -> Vec<u8> {
    let clear_code = 1 << min_code_size;
    let end_code = clear_code + 1;

    struct Table {
        entries: HashMap<Vec<u8>, u16>,
        next_code: u16,
        code_size: u8,
    }

    fn reset_table(min_code_size: u8, clear_code: u16, end_code: u16) -> Table {
        let mut entries = HashMap::new();
        for idx in 0..clear_code {
            entries.insert(vec![idx as u8], idx);
        }
        Table {
            entries,
            next_code: end_code + 1,
            code_size: min_code_size + 1,
        }
    }

    let end_code = end_code as u16;
    let clear_code = clear_code as u16;
    let mut table = reset_table(min_code_size, clear_code, end_code);
    let mut output_codes: Vec<(u16, u8)> = vec![(clear_code, table.code_size)];

    if indices.is_empty() {
        output_codes.push((end_code, table.code_size));
        return pack_gif_codes(&output_codes);
    }

    let mut word = vec![indices[0]];
    for &value in &indices[1..] {
        let mut candidate = word.clone();
        candidate.push(value);
        if table.entries.contains_key(&candidate) {
            word = candidate;
            continue;
        }
        let code = table.entries[&word];
        output_codes.push((code, table.code_size));
        if table.next_code < 4096 {
            table.entries.insert(candidate, table.next_code);
            table.next_code += 1;
            if table.next_code == (1 << table.code_size) && table.code_size < 12 {
                table.code_size += 1;
            }
        } else {
            output_codes.push((clear_code, table.code_size));
            table = reset_table(min_code_size, clear_code, end_code);
        }
        word = vec![value];
    }
    output_codes.push((table.entries[&word], table.code_size));
    output_codes.push((end_code, table.code_size));
    pack_gif_codes(&output_codes)
}

fn pack_gif_codes(output_codes: &[(u16, u8)]) -> Vec<u8> {
    let mut packed = Vec::new();
    let mut bit_buffer: u32 = 0;
    let mut bit_count = 0;
    for (code, size) in output_codes {
        bit_buffer |= (*code as u32) << bit_count;
        bit_count += *size as i32;
        while bit_count >= 8 {
            packed.push((bit_buffer & 0xFF) as u8);
            bit_buffer >>= 8;
            bit_count -= 8;
        }
    }
    if bit_count > 0 {
        packed.push((bit_buffer & 0xFF) as u8);
    }
    packed
}

pub fn frame_sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn encode_gif_via_ffmpeg(frames: &[RgbFrame], delay_cs: u16) -> Result<Vec<u8>, String> {
    if frames.is_empty() {
        return Err("cannot encode GIF with zero frames".into());
    }
    let fps = (100_u32 / delay_cs.max(1) as u32).clamp(1, 50);
    let temp = tempfile::tempdir().map_err(|err| err.to_string())?;
    for (idx, (width, height, rows)) in frames.iter().enumerate() {
        let path = temp.path().join(format!("frame_{idx:04}.png"));
        std::fs::write(&path, encode_png_rgb(*width, *height, rows)).map_err(|err| err.to_string())?;
    }
    let output = temp.path().join("replay.gif");
    let status = Command::new("ffmpeg")
        .args([
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            &fps.to_string(),
            "-i",
        ])
        .arg(temp.path().join("frame_%04d.png"))
        .args([
            "-frames:v",
            &frames.len().to_string(),
            "-vf",
            &format!(
                "fps={fps},split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=none"
            ),
        ])
        .arg(&output)
        .status()
        .map_err(|err| err.to_string())?;
    if !status.success() {
        return Err("ffmpeg GIF encode failed".into());
    }
    std::fs::read(&output).map_err(|err| err.to_string())
}
