use png::{ColorType, Decoder};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

use crate::render::{RgbFrame, RgbRows, UNKNOWN_RGB};

type Rgba = (u8, u8, u8, u8);
type SpriteRows = Vec<Vec<Rgba>>;

const NATIVE_SPRITE_PX: u32 = 16;

static ASSETS_DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
static SPRITE_CACHE: OnceLock<Mutex<HashMap<String, SpriteRows>>> = OnceLock::new();

pub fn sprites_available() -> bool {
    assets_dir().is_some()
}

pub fn assets_dir() -> Option<&'static Path> {
    ASSETS_DIR
        .get_or_init(resolve_assets_dir)
        .as_ref()
        .map(|path| path.as_path())
}

fn resolve_assets_dir() -> Option<PathBuf> {
    if let Ok(path) = std::env::var("GAMEBENCH_CRAFTER_ASSETS_DIR") {
        let path = PathBuf::from(path);
        if path.join("grass.png").is_file() {
            return Some(path);
        }
    }
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("shared/assets/crafter"));
        candidates.push(cwd.join("tasks/crafter-singleplayer/shared/assets/crafter"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.join("../shared/assets/crafter"));
            candidates.push(parent.join("../../shared/assets/crafter"));
            candidates.push(parent.join("../../../shared/assets/crafter"));
        }
    }
    candidates.push(PathBuf::from("shared/assets/crafter"));
    candidates.push(PathBuf::from("../shared/assets/crafter"));
    for path in candidates {
        if path.join("grass.png").is_file() {
            return Some(path.canonicalize().unwrap_or(path));
        }
    }
    None
}

pub fn render_rgb_frame_sprites_from_readout(readout: &Value, tile_size: u32) -> RgbFrame {
    let observation = readout
        .get("observation")
        .filter(|value| value.is_object())
        .unwrap_or(readout);
    let Some(view) = observation.get("view").and_then(Value::as_object) else {
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
        let Some(pos) = tile.get("pos").and_then(Value::as_array) else {
            continue;
        };
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
    let player_facing = observation
        .get("player")
        .and_then(|player| player.get("facing"))
        .and_then(Value::as_array);

    let width = grid_width * tile_size;
    let height = grid_height * tile_size;
    let mut canvas: RgbRows = vec![vec![UNKNOWN_RGB; width as usize]; height as usize];

    for y in min_y..=max_y {
        for x in min_x..=max_x {
            let kind = by_pos
                .get(&(x, y))
                .and_then(|tile| tile.get("kind"))
                .and_then(Value::as_str)
                .unwrap_or("unknown");
            blit_sprite(
                &mut canvas,
                ((x - min_x) as u32) * tile_size,
                ((y - min_y) as u32) * tile_size,
                tile_sprite_name(kind),
                tile_size,
                false,
            );
        }
    }

    if let Some(entities) = view.get("entities").and_then(Value::as_array) {
        for entity in entities {
            let Some(pos) = entity.get("pos").and_then(Value::as_array) else {
                continue;
            };
            if pos.len() < 2 {
                continue;
            }
            let ex = pos[0].as_i64().unwrap_or(0);
            let ey = pos[1].as_i64().unwrap_or(0);
            if (ex, ey) == player_pos {
                continue;
            }
            blit_sprite(
                &mut canvas,
                ((ex - min_x) as u32) * tile_size,
                ((ey - min_y) as u32) * tile_size,
                entity_sprite_name(entity),
                tile_size,
                true,
            );
        }
    }

    blit_sprite(
        &mut canvas,
        ((player_pos.0 - min_x) as u32) * tile_size,
        ((player_pos.1 - min_y) as u32) * tile_size,
        player_sprite_name(player_facing),
        tile_size,
        true,
    );

    (width, height, canvas)
}

fn tile_sprite_name(kind: &str) -> &str {
    if assets_dir()
        .is_some_and(|dir| dir.join(format!("{kind}.png")).is_file())
    {
        kind
    } else {
        "unknown"
    }
}

fn entity_sprite_name(entity: &Value) -> &str {
    let kind = entity
        .get("kind")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    if kind == "plant" {
        let grown = entity
            .get("metadata")
            .and_then(|meta| meta.get("grown"))
            .and_then(Value::as_i64)
            .unwrap_or(0);
        if grown >= 300 {
            return "plant-ripe";
        }
        return "plant";
    }
    kind
}

fn player_sprite_name(facing: Option<&Vec<Value>>) -> &'static str {
    let Some(facing) = facing else {
        return "player-down";
    };
    if facing.len() < 2 {
        return "player-down";
    }
    let fx = facing[0].as_i64().unwrap_or(0);
    let fy = facing[1].as_i64().unwrap_or(0);
    if fy == -1 {
        "player-up"
    } else if fy == 1 {
        "player-down"
    } else if fx == -1 {
        "player-left"
    } else if fx == 1 {
        "player-right"
    } else {
        "player-down"
    }
}

fn blit_sprite(canvas: &mut RgbRows, dest_x: u32, dest_y: u32, name: &str, tile_size: u32, alpha: bool) {
    let sprite = load_sprite(name);
    let native = sprite.len() as u32;
    if native == 0 {
        return;
    }
    let canvas_h = canvas.len() as u32;
    let canvas_w = canvas.first().map(|row| row.len() as u32).unwrap_or(0);
    for dy in 0..tile_size {
        let sy = ((dy * native) / tile_size).min(native.saturating_sub(1)) as usize;
        for dx in 0..tile_size {
            let sx = ((dx * native) / tile_size).min(native.saturating_sub(1)) as usize;
            let (sr, sg, sb, sa) = sprite[sy][sx];
            if alpha && sa == 0 {
                continue;
            }
            let y = dest_y + dy;
            let x = dest_x + dx;
            if y >= canvas_h || x >= canvas_w {
                continue;
            }
            if alpha && sa < 255 {
                let (dr, dg, db) = canvas[y as usize][x as usize];
                let blend = sa as f32 / 255.0;
                canvas[y as usize][x as usize] = (
                    (sr as f32 * blend + dr as f32 * (1.0 - blend)) as u8,
                    (sg as f32 * blend + dg as f32 * (1.0 - blend)) as u8,
                    (sb as f32 * blend + db as f32 * (1.0 - blend)) as u8,
                );
            } else {
                canvas[y as usize][x as usize] = (sr, sg, sb);
            }
        }
    }
}

fn load_sprite(name: &str) -> SpriteRows {
    let cache = SPRITE_CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut guard = cache.lock().unwrap();
    if let Some(sprite) = guard.get(name) {
        return sprite.clone();
    }
    let path = assets_dir()
        .map(|dir| dir.join(format!("{name}.png")))
        .filter(|path| path.is_file())
        .unwrap_or_else(|| {
            assets_dir()
                .map(|dir| dir.join("unknown.png"))
                .unwrap_or_else(|| PathBuf::from("unknown.png"))
        });
    let sprite = decode_png_rgba(&path).unwrap_or_else(|_| vec![vec![(30, 34, 38, 255); NATIVE_SPRITE_PX as usize]; NATIVE_SPRITE_PX as usize]);
    guard.insert(name.to_string(), sprite.clone());
    sprite
}

fn decode_png_rgba(path: &Path) -> Result<SpriteRows, String> {
    let file = std::fs::File::open(path).map_err(|err| err.to_string())?;
    let decoder = Decoder::new(file);
    let mut reader = decoder.read_info().map_err(|err| err.to_string())?;
    let width = reader.info().width as usize;
    let height = reader.info().height as usize;
    let bit_depth = reader.info().bit_depth;
    let color_type = reader.info().color_type;
    if bit_depth != png::BitDepth::Eight {
        return Err(format!("unsupported bit depth {bit_depth:?}"));
    }
    let mut buf = vec![0_u8; reader.output_buffer_size()];
    reader.next_frame(&mut buf).map_err(|err| err.to_string())?;
    let mut rows = Vec::with_capacity(height);
    match color_type {
        ColorType::Rgb => {
            for y in 0..height {
                let mut row = Vec::with_capacity(width);
                for x in 0..width {
                    let idx = (y * width + x) * 3;
                    row.push((buf[idx], buf[idx + 1], buf[idx + 2], 255));
                }
                rows.push(row);
            }
        }
        ColorType::Rgba => {
            for y in 0..height {
                let mut row = Vec::with_capacity(width);
                for x in 0..width {
                    let idx = (y * width + x) * 4;
                    row.push((buf[idx], buf[idx + 1], buf[idx + 2], buf[idx + 3]));
                }
                rows.push(row);
            }
        }
        other => return Err(format!("unsupported color type {other:?}")),
    }
    Ok(rows)
}
