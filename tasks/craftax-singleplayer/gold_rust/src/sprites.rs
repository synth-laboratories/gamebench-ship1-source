use png::{ColorType, Decoder};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

use crate::render::{Rgb, RgbFrame, RgbRows, UNKNOWN_RGB};
use crate::CraftaxWorld;

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
    if let Ok(path) = std::env::var("GAMEBENCH_CRAFTAX_ASSETS_DIR") {
        let path = PathBuf::from(path);
        if path.join("grass.png").is_file() {
            return Some(path);
        }
    }
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("shared/assets/craftax"));
        candidates.push(cwd.join("tasks/craftax-singleplayer/shared/assets/craftax"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.join("../shared/assets/craftax"));
            candidates.push(parent.join("../../shared/assets/craftax"));
            candidates.push(parent.join("../../../shared/assets/craftax"));
        }
    }
    candidates.push(PathBuf::from("shared/assets/craftax"));
    candidates.push(PathBuf::from("../shared/assets/craftax"));
    for path in candidates {
        if path.join("grass.png").is_file() {
            return Some(path.canonicalize().unwrap_or(path));
        }
    }
    None
}

pub fn render_rgb_frame_sprites_from_world(world: &CraftaxWorld, tile_size: u32) -> RgbFrame {
    let width = (world.width.max(1) as u32) * tile_size;
    let height = (world.height.max(1) as u32) * tile_size;
    let level = usize::try_from(world.player_level.max(0)).unwrap_or(0);
    let mut canvas: RgbRows = vec![vec![UNKNOWN_RGB; width as usize]; height as usize];

    for y in 0..world.height {
        for x in 0..world.width {
            let ux = usize::try_from(x).unwrap_or(0);
            let uy = usize::try_from(y).unwrap_or(0);
            let block = world.maps[level][uy][ux].as_str();
            let dest_x = (x as u32) * tile_size;
            let dest_y = (y as u32) * tile_size;
            if block == "darkness" {
                fill_solid(&mut canvas, dest_x, dest_y, tile_size, (2, 6, 23));
                continue;
            }
            blit_sprite(
                &mut canvas,
                dest_x,
                dest_y,
                block_sprite_name(block),
                tile_size,
                false,
            );
            let item = world.item_maps[level][uy][ux].as_str();
            if item != "none" {
                if let Some(name) = item_sprite_name(item) {
                    blit_sprite(&mut canvas, dest_x, dest_y, name, tile_size, true);
                }
            }
        }
    }

    for entity in &world.entities {
        if !entity.mask || entity.level != world.player_level {
            continue;
        }
        if entity.pos == world.player_pos {
            continue;
        }
        blit_sprite(
            &mut canvas,
            (entity.pos.0 as u32) * tile_size,
            (entity.pos.1 as u32) * tile_size,
            entity_sprite_name(&entity.kind),
            tile_size,
            true,
        );
    }

    for projectile in world
        .player_projectiles
        .iter()
        .chain(world.mob_projectiles.iter())
    {
        if !projectile.mask || projectile.level != world.player_level {
            continue;
        }
        blit_sprite(
            &mut canvas,
            (projectile.pos.0 as u32) * tile_size,
            (projectile.pos.1 as u32) * tile_size,
            projectile_sprite_name(&projectile.kind, &projectile.owner),
            tile_size,
            true,
        );
    }

    blit_sprite(
        &mut canvas,
        (world.player_pos.0 as u32) * tile_size,
        (world.player_pos.1 as u32) * tile_size,
        player_sprite_name(world.player_direction),
        tile_size,
        true,
    );

    (width, height, canvas)
}

fn block_sprite_name(tile: &str) -> &str {
    match tile {
        "grass" => "grass",
        "water" => "water",
        "stone" => "stone",
        "tree" => "tree",
        "fire_tree" => "fire_tree",
        "ice_shrub" => "ice_shrub",
        "wood" => "wood",
        "path" => "path",
        "coal" => "coal",
        "iron" => "iron",
        "diamond" => "diamond",
        "crafting_table" => "table",
        "furnace" => "furnace",
        "sand" => "sand",
        "lava" => "lava",
        "plant" => "plant_on_grass",
        "ripe_plant" => "ripe_plant_on_grass",
        "wall" => "wall2",
        "wall_moss" => "wall_moss",
        "stalagmite" => "stalagmite",
        "sapphire" => "sapphire",
        "ruby" => "ruby",
        "chest" => "chest",
        "fountain" => "fountain",
        "fire_grass" => "fire_grass",
        "ice_grass" => "ice_grass",
        "gravel" => "gravel",
        "enchantment_table_fire" => "enchantment_table_fire",
        "enchantment_table_ice" => "enchantment_table_ice",
        "necromancer" => "necromancer",
        "necromancer_vulnerable" => "necromancer_vulnerable",
        "grave" => "grave",
        "grave2" => "grave2",
        "grave3" => "grave3",
        _ => sprite_if_exists(tile).unwrap_or("debug_tile"),
    }
}

fn item_sprite_name(item: &str) -> Option<&'static str> {
    match item {
        "torch" => Some("torch_in_inventory"),
        "ladder_down" => Some("ladder_down"),
        "ladder_up" => Some("ladder_up"),
        "ladder_down_blocked" => Some("ladder_down_blocked"),
        _ => None,
    }
}

fn entity_sprite_name(kind: &str) -> &str {
    match kind {
        "orc_solider" => "orc_soldier",
        other => other,
    }
}

fn projectile_sprite_name(kind: &str, owner: &str) -> &'static str {
    if owner == "mob" {
        return "arrow-up";
    }
    match kind {
        "fireball" | "fireball2" => "fireball",
        "iceball" | "iceball2" => "iceball",
        _ => "dagger",
    }
}

fn player_sprite_name(direction: (i64, i64)) -> &'static str {
    match direction {
        (0, -1) => "player-up",
        (0, 1) => "player-down",
        (-1, 0) => "player-left",
        (1, 0) => "player-right",
        _ => "player-down",
    }
}

fn sprite_if_exists(name: &str) -> Option<&str> {
    assets_dir()
        .and_then(|dir| dir.join(format!("{name}.png")).is_file().then_some(name))
}

fn fill_solid(canvas: &mut RgbRows, dest_x: u32, dest_y: u32, tile_size: u32, rgb: Rgb) {
    let canvas_h = canvas.len() as u32;
    let canvas_w = canvas.first().map(|row| row.len() as u32).unwrap_or(0);
    for dy in 0..tile_size {
        for dx in 0..tile_size {
            let y = dest_y + dy;
            let x = dest_x + dx;
            if y < canvas_h && x < canvas_w {
                canvas[y as usize][x as usize] = rgb;
            }
        }
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
                .map(|dir| dir.join("debug_tile.png"))
                .unwrap_or_else(|| PathBuf::from("debug_tile.png"))
        });
    let sprite = decode_png_rgba(&path).unwrap_or_else(|_| {
        vec![vec![(30, 34, 38, 255); NATIVE_SPRITE_PX as usize]; NATIVE_SPRITE_PX as usize]
    });
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
