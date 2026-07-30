use pokemon_emerald_littleroot_gold::native::{fit_littleroot_camera, render_littleroot_map, render_littleroot_with_idle_objects};
use pokemon_emerald_littleroot_gold::world::{Facing, TilePosition};
use std::fs;

fn main() -> Result<(), String> {
    let frame = render_littleroot_map()?;
    fs::write("/tmp/littleroot-native-map.rgb", frame).map_err(|error| error.to_string())?;
    let reference: &[u8] = include_bytes!("../../assets/littleroot_outside_idle.rgb");
    let (camera_x, camera_y, error) = fit_littleroot_camera(reference)?;
    println!("camera_x={camera_x} camera_y={camera_y} rgb_abs_error={error}");
    let facing = match std::env::args().nth(1).as_deref().unwrap_or("right") {
        "up" => Facing::Up,
        "down" => Facing::Down,
        "left" => Facing::Left,
        "right" => Facing::Right,
        direction => return Err(format!("unsupported facing: {direction}")),
    };
    let player = TilePosition {
        x: std::env::args().nth(3).map(|value| value.parse()).transpose().map_err(|error| format!("invalid x coordinate: {error}"))?.unwrap_or(10),
        y: std::env::args().nth(4).map(|value| value.parse()).transpose().map_err(|error| format!("invalid y coordinate: {error}"))?.unwrap_or(13),
    };
    let viewport = if std::env::args().nth(2).as_deref() == Some("start") {
        pokemon_emerald_littleroot_gold::native::render_littleroot_start_walk(&player, facing)?
    } else {
        render_littleroot_with_idle_objects(&player, facing, Some(facing), 15)?
    };
    fs::write("/tmp/littleroot-native-viewport.rgb", viewport).map_err(|error| error.to_string())
}
