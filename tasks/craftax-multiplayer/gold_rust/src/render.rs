//! Deterministic composite renderer for Craftax-Coop.
//!
//! Each player receives a private 11×11 panel for their current level, followed by
//! teammate and inventory dashboards. The horizontal team strip keeps split-level
//! agents inspectable without revealing an omniscient map. Sprite mode consumes the
//! separately licensed shared asset bundle; symbolic mode has no asset dependency.

use crate::{CraftaxCoopEnv, MAP_SIZE};
use font8x8::{UnicodeFonts, BASIC_FONTS};
use image::codecs::gif::{GifEncoder, Repeat};
use image::codecs::png::{CompressionType, FilterType, PngEncoder};
use image::imageops::FilterType as ResizeFilter;
use image::{Delay, DynamicImage, Frame, ImageEncoder, Rgb, RgbImage, RgbaImage};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub const TILE_SIZE: u32 = 16;
pub const VIEW_SIZE: u32 = 11;
pub const TEAMMATE_ROWS: u32 = 2;
pub const INVENTORY_ROWS: u32 = 4;
pub const PANEL_WIDTH: u32 = VIEW_SIZE * TILE_SIZE;
pub const PANEL_HEIGHT: u32 = (TEAMMATE_ROWS + VIEW_SIZE + INVENTORY_ROWS) * TILE_SIZE;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RenderMode {
    Auto,
    Sprites,
    Symbolic,
}

impl RenderMode {
    pub fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.unwrap_or("auto") {
            "auto" => Ok(Self::Auto),
            "sprites" => Ok(Self::Sprites),
            "symbolic" => Ok(Self::Symbolic),
            other => Err(format!(
                "unsupported render_mode {other:?}; expected auto, sprites, or symbolic"
            )),
        }
    }
}

#[derive(Clone, Debug)]
pub struct RgbFrame {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>,
}

impl RgbFrame {
    pub fn png(&self) -> Result<Vec<u8>, String> {
        let mut bytes = Vec::new();
        PngEncoder::new_with_quality(&mut bytes, CompressionType::Fast, FilterType::Adaptive)
            .write_image(
                &self.pixels,
                self.width,
                self.height,
                image::ExtendedColorType::Rgb8,
            )
            .map_err(|error| error.to_string())?;
        Ok(bytes)
    }
}

fn asset_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../shared/assets/craftax_coop")
}

fn sprites_available() -> bool {
    asset_dir().join("grass.png").is_file()
}

fn resolved_mode(mode: RenderMode) -> Result<RenderMode, String> {
    match mode {
        RenderMode::Auto if sprites_available() => Ok(RenderMode::Sprites),
        RenderMode::Auto => Ok(RenderMode::Symbolic),
        RenderMode::Sprites if !sprites_available() => Err(format!(
            "sprite assets not found at {}",
            asset_dir().display()
        )),
        value => Ok(value),
    }
}

fn terrain_color(name: &str) -> Rgb<u8> {
    Rgb(match name {
        "grass" => [69, 132, 62],
        "path" => [126, 111, 84],
        "sand" => [202, 181, 112],
        "water" | "fountain" => [44, 105, 173],
        "lava" => [215, 63, 33],
        "stone" | "wall" | "wall2" => [82, 87, 91],
        "tree" => [31, 91, 45],
        "fire_grass" => [116, 60, 37],
        "fire_tree" => [126, 43, 25],
        "ice_grass" => [142, 202, 215],
        "ice_shrub" => [103, 176, 198],
        "coal" => [38, 40, 42],
        "iron" => [143, 119, 93],
        "diamond" => [69, 209, 218],
        "ruby" => [190, 45, 62],
        "sapphire" => [47, 89, 205],
        "chest" => [164, 105, 38],
        "stairs_up" | "stairs_down" => [225, 213, 155],
        "grave" | "grave2" | "grave3" => [91, 84, 105],
        "necromancer" | "boss" => [98, 35, 118],
        _ => [92, 92, 78],
    })
}

fn asset_name(name: &str) -> &str {
    match name {
        "stairs_up" => "ladder_up",
        "stairs_down" => "ladder_down",
        "grave2" | "grave3" => "grave",
        "necromancer" | "boss" => "necromancer",
        "crafting_table" => "table",
        "ripe_plant" => "plant-ripe",
        "torch" => "torch_on_path",
        "archer" => "knight_archer",
        "arrow2" => "arrow",
        "fireball2" => "fireball",
        "iceball2" => "iceball",
        other => other,
    }
}

fn sprite(name: &str, cache: &mut BTreeMap<String, RgbaImage>) -> Option<RgbaImage> {
    if let Some(image) = cache.get(name) {
        return Some(image.clone());
    }
    let path = asset_dir().join(format!("{}.png", asset_name(name)));
    let loaded = image::open(path)
        .ok()?
        .resize_exact(TILE_SIZE, TILE_SIZE, ResizeFilter::Nearest)
        .to_rgba8();
    cache.insert(name.to_string(), loaded.clone());
    Some(loaded)
}

fn fill(image: &mut RgbImage, x: u32, y: u32, width: u32, height: u32, color: Rgb<u8>) {
    for py in y..(y + height).min(image.height()) {
        for px in x..(x + width).min(image.width()) {
            image.put_pixel(px, py, color);
        }
    }
}

fn blit_rgb(image: &mut RgbImage, sprite: &RgbaImage, x: u32, y: u32, light: f64) {
    for sy in 0..sprite.height() {
        for sx in 0..sprite.width() {
            let pixel = sprite.get_pixel(sx, sy).0;
            if pixel[3] == 0 {
                continue;
            }
            let lit = [
                (pixel[0] as f64 * light) as u8,
                (pixel[1] as f64 * light) as u8,
                (pixel[2] as f64 * light) as u8,
            ];
            image.put_pixel(x + sx, y + sy, Rgb(lit));
        }
    }
}

fn blit_tinted_rgb(image: &mut RgbImage, sprite: &RgbaImage, x: u32, y: u32, tint: Rgb<u8>) {
    for sy in 0..sprite.height() {
        for sx in 0..sprite.width() {
            let pixel = sprite.get_pixel(sx, sy).0;
            if pixel[3] == 0 {
                continue;
            }
            let brightness = pixel[0].max(pixel[1]).max(pixel[2]) as u16;
            image.put_pixel(
                x + sx,
                y + sy,
                Rgb([
                    ((pixel[0] as u16 + brightness * tint[0] as u16 / 255 * 2) / 3) as u8,
                    ((pixel[1] as u16 + brightness * tint[1] as u16 / 255 * 2) / 3) as u8,
                    ((pixel[2] as u16 + brightness * tint[2] as u16 / 255 * 2) / 3) as u8,
                ]),
            );
        }
    }
}

fn text(image: &mut RgbImage, x: u32, y: u32, value: &str, color: Rgb<u8>, scale: u32, max_x: u32) {
    let mut cursor = x;
    for character in value.to_ascii_uppercase().chars() {
        if let Some(glyph) = BASIC_FONTS.get(character) {
            for (row, bits) in glyph.iter().enumerate() {
                for column in 0..8 {
                    if bits & (1 << column) != 0 && cursor + column * scale < max_x {
                        fill(
                            image,
                            cursor + column * scale,
                            y + row as u32 * scale,
                            scale,
                            scale,
                            color,
                        );
                    }
                }
            }
        }
        cursor += 8 * scale;
    }
}

fn marker(image: &mut RgbImage, x: u32, y: u32, color: Rgb<u8>) {
    fill(image, x + 1, y + 1, TILE_SIZE - 2, TILE_SIZE - 2, color);
    fill(image, x + 2, y, TILE_SIZE - 4, TILE_SIZE, color);
}

fn dim_rect(image: &mut RgbImage, x: u32, y: u32, light: f64) {
    for py in y..y + TILE_SIZE {
        for px in x..x + TILE_SIZE {
            let value = image.get_pixel(px, py).0;
            image.put_pixel(
                px,
                py,
                Rgb([
                    (value[0] as f64 * light) as u8,
                    (value[1] as f64 * light) as u8,
                    (value[2] as f64 * light) as u8,
                ]),
            );
        }
    }
}

fn draw_tile(
    image: &mut RgbImage,
    x: u32,
    y: u32,
    name: &str,
    light: f64,
    mode: RenderMode,
    cache: &mut BTreeMap<String, RgbaImage>,
) {
    if mode == RenderMode::Sprites {
        if let Some(sprite) = sprite(name, cache) {
            blit_rgb(image, &sprite, x, y, light);
            return;
        }
    }
    let base = terrain_color(name).0;
    fill(
        image,
        x,
        y,
        TILE_SIZE,
        TILE_SIZE,
        Rgb([
            (base[0] as f64 * light) as u8,
            (base[1] as f64 * light) as u8,
            (base[2] as f64 * light) as u8,
        ]),
    );
    if matches!(
        name,
        "tree" | "stone" | "coal" | "iron" | "diamond" | "ruby" | "sapphire" | "chest"
    ) {
        let accent = Rgb([
            base[0].saturating_add(36),
            base[1].saturating_add(36),
            base[2].saturating_add(36),
        ]);
        fill(image, x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4, accent);
    }
}

fn entity(
    image: &mut RgbImage,
    x: u32,
    y: u32,
    sprite_name: &str,
    color: Rgb<u8>,
    mode: RenderMode,
    cache: &mut BTreeMap<String, RgbaImage>,
) {
    if mode == RenderMode::Sprites {
        if let Some(sprite) = sprite(sprite_name, cache) {
            blit_rgb(image, &sprite, x, y, 1.0);
            return;
        }
    }
    marker(image, x, y, color);
}

fn player_entity(
    image: &mut RgbImage,
    x: u32,
    y: u32,
    alive: bool,
    sleeping: bool,
    facing: &str,
    color: Rgb<u8>,
    mode: RenderMode,
    cache: &mut BTreeMap<String, RgbaImage>,
) {
    if !alive {
        entity(image, x, y, "player-dead", color, mode, cache);
        return;
    }
    let sprite_name = if sleeping {
        "player-sleep".to_string()
    } else {
        format!("player-{facing}")
    };
    if mode == RenderMode::Sprites {
        if let Some(sprite) = sprite(&sprite_name, cache) {
            blit_tinted_rgb(image, &sprite, x, y, color);
            return;
        }
    }
    marker(image, x, y, color);
}

pub fn render_rgb(env: &CraftaxCoopEnv, requested_mode: RenderMode) -> Result<RgbFrame, String> {
    let mode = resolved_mode(requested_mode)?;
    let count = env.state.players.len().max(1) as u32;
    let width = count * PANEL_WIDTH;
    let height = PANEL_HEIGHT;
    let mut canvas = RgbImage::from_pixel(width, height, Rgb([17, 20, 24]));
    let mut cache = BTreeMap::new();
    for (panel, focus) in env.state.players.iter().enumerate() {
        let ox = panel as u32 * PANEL_WIDTH;
        fill(
            &mut canvas,
            ox,
            0,
            PANEL_WIDTH,
            PANEL_HEIGHT,
            Rgb([19, 23, 28]),
        );
        let teammates = env
            .state
            .players
            .iter()
            .enumerate()
            .filter(|(_, player)| player.agent_id != focus.agent_id)
            .take(TEAMMATE_ROWS as usize);
        for (row, (index, teammate)) in teammates.enumerate() {
            let y = row as u32 * TILE_SIZE;
            let colors = [
                Rgb([72, 169, 255]),
                Rgb([255, 180, 52]),
                Rgb([180, 94, 235]),
                Rgb([72, 220, 141]),
            ];
            player_entity(
                &mut canvas,
                ox,
                y,
                teammate.alive,
                teammate.sleeping,
                &teammate.facing,
                colors[index % colors.len()],
                mode,
                &mut cache,
            );
            text(
                &mut canvas,
                ox + 18,
                y + 1,
                &format!(
                    "{} {} L{}",
                    teammate.agent_id, teammate.role, teammate.level
                ),
                Rgb([226, 231, 236]),
                1,
                ox + PANEL_WIDTH,
            );
            text(
                &mut canvas,
                ox + 18,
                y + 9,
                &format!(
                    "H{} F{} D{} E{} R{}",
                    teammate.health.max(0.0) as i16,
                    teammate.food,
                    teammate.drink,
                    teammate.energy,
                    teammate.request_duration
                ),
                Rgb([177, 192, 205]),
                1,
                ox + PANEL_WIDTH,
            );
        }
        let map_origin_y = TEAMMATE_ROWS * TILE_SIZE;
        let radius = (VIEW_SIZE / 2) as isize;
        for vy in 0..VIEW_SIZE as isize {
            for vx in 0..VIEW_SIZE as isize {
                let world_x = focus.x as isize - radius + vx;
                let world_y = focus.y as isize - radius + vy;
                let px = ox + vx as u32 * TILE_SIZE;
                let py = map_origin_y + vy as u32 * TILE_SIZE;
                if world_x < 0
                    || world_y < 0
                    || world_x >= MAP_SIZE as isize
                    || world_y >= MAP_SIZE as isize
                {
                    fill(&mut canvas, px, py, TILE_SIZE, TILE_SIZE, Rgb([4, 5, 7]));
                    continue;
                }
                let x = world_x as usize;
                let y = world_y as usize;
                draw_tile(
                    &mut canvas,
                    px,
                    py,
                    &env.state.maps[focus.level][y][x],
                    1.0,
                    mode,
                    &mut cache,
                );
                if let Some(item) = &env.state.item_maps[focus.level][y][x] {
                    entity(
                        &mut canvas,
                        px,
                        py,
                        item,
                        Rgb([247, 219, 94]),
                        mode,
                        &mut cache,
                    );
                }
                if let Some(plant) = env
                    .state
                    .plants
                    .iter()
                    .find(|plant| plant.level == focus.level && plant.x == x && plant.y == y)
                {
                    let name = if plant.age >= 500 {
                        "plant-ripe"
                    } else {
                        "plant"
                    };
                    entity(
                        &mut canvas,
                        px,
                        py,
                        name,
                        Rgb([75, 207, 73]),
                        mode,
                        &mut cache,
                    );
                }
                for (index, player) in env.state.players.iter().enumerate().filter(|(_, player)| {
                    player.level == focus.level && player.x == x && player.y == y
                }) {
                    let colors = [
                        Rgb([72, 169, 255]),
                        Rgb([255, 180, 52]),
                        Rgb([180, 94, 235]),
                        Rgb([72, 220, 141]),
                    ];
                    player_entity(
                        &mut canvas,
                        px,
                        py,
                        player.alive,
                        player.sleeping,
                        &player.facing,
                        colors[index % colors.len()],
                        mode,
                        &mut cache,
                    );
                }
                for monster in env.state.monsters.iter().filter(|monster| {
                    monster.level == focus.level && monster.x == x && monster.y == y
                }) {
                    entity(
                        &mut canvas,
                        px,
                        py,
                        &monster.kind,
                        Rgb([202, 66, 73]),
                        mode,
                        &mut cache,
                    );
                }
                for projectile in env.state.projectiles.iter().filter(|projectile| {
                    projectile.level == focus.level
                        && projectile.x == world_x
                        && projectile.y == world_y
                }) {
                    let color = if projectile.hostile {
                        Rgb([255, 78, 50])
                    } else {
                        Rgb([245, 231, 91])
                    };
                    entity(
                        &mut canvas,
                        px,
                        py,
                        &projectile.kind,
                        color,
                        mode,
                        &mut cache,
                    );
                }
                let mut light = env.state.light_maps[focus.level][y][x];
                if focus.level == 0 {
                    light *= env.state.light_level;
                }
                light = (0.22 + 0.78 * light).clamp(0.12, 1.0);
                dim_rect(&mut canvas, px, py, light);
            }
        }
        let y = (TEAMMATE_ROWS + VIEW_SIZE) * TILE_SIZE;
        text(
            &mut canvas,
            ox + 2,
            y + 1,
            &format!(
                "{} {} L{} T{}",
                focus.agent_id, focus.role, focus.level, env.state.timestep
            ),
            Rgb([231, 235, 239]),
            1,
            ox + PANEL_WIDTH,
        );
        text(
            &mut canvas,
            ox + 2,
            y + 17,
            &format!(
                "HP{} F{} D{} E{} M{} XP{}",
                focus.health.max(0.0) as i16,
                focus.food,
                focus.drink,
                focus.energy,
                focus.mana,
                focus.xp
            ),
            Rgb([205, 215, 224]),
            1,
            ox + PANEL_WIDTH,
        );
        text(
            &mut canvas,
            ox + 2,
            y + 33,
            &format!(
                "P{} S{} A{} B{} AR{}",
                focus.pickaxe, focus.sword, focus.armour, focus.bow, focus.arrows
            ),
            Rgb([205, 215, 224]),
            1,
            ox + PANEL_WIDTH,
        );
        let inventory = crate::RESOURCES
            .iter()
            .filter_map(|resource| {
                let value = focus.inventory.get(*resource).copied().unwrap_or(0);
                (value > 0).then(|| format!("{}:{}", &resource[..resource.len().min(3)], value))
            })
            .collect::<Vec<_>>()
            .join(" ");
        let request = focus.request_type.as_deref().unwrap_or("NONE");
        text(
            &mut canvas,
            ox + 2,
            y + 49,
            &format!(
                "{} R:{} B{} W{}",
                if inventory.is_empty() {
                    "INV EMPTY"
                } else {
                    &inventory
                },
                request,
                env.state.boss_health,
                env.state.boss_progress
            ),
            Rgb([255, 207, 93]),
            1,
            ox + PANEL_WIDTH,
        );
    }
    Ok(RgbFrame {
        width,
        height,
        pixels: canvas.into_raw(),
    })
}

pub fn encode_gif(frames: &[RgbFrame], delay_centiseconds: u32) -> Result<Vec<u8>, String> {
    let first = frames
        .first()
        .ok_or_else(|| "cannot encode an empty replay".to_string())?;
    if frames
        .iter()
        .any(|frame| frame.width != first.width || frame.height != first.height)
    {
        return Err("all replay frames must have identical dimensions".into());
    }
    let mut bytes = Vec::new();
    {
        let mut encoder = GifEncoder::new_with_speed(&mut bytes, 10);
        encoder
            .set_repeat(Repeat::Infinite)
            .map_err(|error| error.to_string())?;
        let delay = Delay::from_numer_denom_ms(delay_centiseconds * 10, 1);
        let images = frames.iter().map(|rgb| {
            let image = RgbImage::from_raw(rgb.width, rgb.height, rgb.pixels.clone())
                .expect("validated RGB frame");
            Frame::from_parts(DynamicImage::ImageRgb8(image).to_rgba8(), 0, 0, delay)
        });
        encoder
            .encode_frames(images)
            .map_err(|error| error.to_string())?;
    }
    Ok(bytes)
}
