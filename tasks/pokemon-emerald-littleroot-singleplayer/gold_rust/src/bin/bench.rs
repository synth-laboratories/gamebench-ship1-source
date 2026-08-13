use pokemon_emerald_littleroot_gold::world::{Facing, TilePosition};
use pokemon_emerald_littleroot_gold::{frame_sha256, native, pixel_diff, LittlerootSession};

fn main() -> Result<(), String> {
    if std::env::args().nth(1).as_deref() == Some("--gender") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing gender reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let native_frame = native::opening_gender_select()?;
        if let Some(output) = std::env::args().nth(3) {
            std::fs::write(output, &native_frame).map_err(|error| error.to_string())?;
        }
        println!(
            "gender_reference={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--gender-native") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing gender reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let mut world = pokemon_emerald_littleroot_gold::world::WorldState::title_menu();
        world.phase = pokemon_emerald_littleroot_gold::world::StoryPhase::GenderSelect;
        world.map = pokemon_emerald_littleroot_gold::world::MapId::ProfessorIntro;
        let native_frame = native::render_gender_select(&world);
        if let Some(output) = std::env::args().nth(3) {
            std::fs::write(output, &native_frame).map_err(|error| error.to_string())?;
        }
        println!("native_gender={:?}", pixel_diff(&native_frame, &reference));
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--name-entry") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing name-entry reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let native_frame = native::render_name_entry_idle()?;
        if let Some(output) = std::env::args().nth(3) {
            std::fs::write(output, &native_frame).map_err(|error| error.to_string())?;
        }
        println!(
            "native_name_entry_idle={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--name-entry-g") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing name-entry G reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let mut world = pokemon_emerald_littleroot_gold::world::WorldState::title_menu();
        world.player_name.clear();
        world.name_cursor = 6;
        let native_frame = native::render_name_entry(&world)?;
        println!(
            "native_name_entry_g={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--name-entry-a") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing name-entry A reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let mut world = pokemon_emerald_littleroot_gold::world::WorldState::title_menu();
        world.player_name = "A".to_owned();
        world.name_cursor = 0;
        let native_frame = native::render_name_entry(&world)?;
        println!(
            "native_name_entry_a={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--professor") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing Professor reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let native_frame = native::render_professor_intro_idle()?;
        println!(
            "native_professor_idle={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--professor-artifact") {
        let reference = native::opening_professor_intro()?;
        let native_frame = native::render_professor_intro_idle()?;
        println!(
            "native_professor_artifact={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--truck") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing truck reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let native_frame = native::render_truck_idle()?;
        println!(
            "native_truck_idle={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--title") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing title reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let native_frame = native::render_title_idle()?;
        if let Some(output) = std::env::args().nth(3) {
            std::fs::write(output, &native_frame).map_err(|error| error.to_string())?;
        }
        println!(
            "native_title_idle={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--bedroom-fit") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing bedroom reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let mut best = (0_i16, 0_i16, usize::MAX);
        for y in 0..8 {
            for x in 0..9 {
                let frame = native::render_bedroom_with_idle_objects(
                    pokemon_emerald_littleroot_gold::world::MapId::MaysHouse2F,
                    &TilePosition { x, y },
                    Facing::Down,
                    None,
                    0,
                    0,
                    false,
                    None,
                    pokemon_emerald_littleroot_gold::world::BedroomPlayerSprite::Base,
                    false,
                    false,
                    0,
                    None,
                )?;
                let diff = pixel_diff(&frame, &reference);
                if diff.differing_pixels < best.2 {
                    best = (x, y, diff.differing_pixels);
                }
            }
        }
        println!("bedroom_fit={best:?}");
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--bedroom") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing bedroom reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let player = TilePosition {
            x: std::env::args()
                .nth(3)
                .map(|value| value.parse::<i16>())
                .transpose()
                .map_err(|error| error.to_string())?
                .unwrap_or(1),
            y: std::env::args()
                .nth(4)
                .map(|value| value.parse::<i16>())
                .transpose()
                .map_err(|error| error.to_string())?
                .unwrap_or(1),
        };
        let native_frame = native::render_bedroom_with_idle_objects(
            pokemon_emerald_littleroot_gold::world::MapId::MaysHouse2F,
            &player,
            Facing::Down,
            None,
            0,
            0,
            false,
            None,
            pokemon_emerald_littleroot_gold::world::BedroomPlayerSprite::Base,
            false,
            false,
            0,
            None,
        )?;
        if let Some(output) = std::env::args().nth(5) {
            std::fs::write(output, &native_frame).map_err(|error| error.to_string())?;
        }
        println!(
            "native_bedroom_idle={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("--birch") {
        let path = std::env::args()
            .nth(2)
            .ok_or_else(|| "missing Birch reference path".to_owned())?;
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let (camera_x, camera_y, error) = native::fit_littleroot_camera(&reference)?;
        println!("camera_x={camera_x} camera_y={camera_y} sampled_error={error}");
        let player = TilePosition {
            x: std::env::args()
                .nth(3)
                .map(|value| value.parse::<i16>())
                .transpose()
                .map_err(|error| error.to_string())?
                .unwrap_or(7),
            y: std::env::args()
                .nth(4)
                .map(|value| value.parse::<i16>())
                .transpose()
                .map_err(|error| error.to_string())?
                .unwrap_or(16),
        };
        let native_frame = native::render_birch_exterior_with_idle_objects(&player)?;
        if let Some(output) = std::env::args().nth(5) {
            std::fs::write(output, &native_frame).map_err(|error| error.to_string())?;
        }
        println!(
            "native_birch_idle={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    if let Some(path) = std::env::args().nth(1) {
        let reference = std::fs::read(path).map_err(|error| error.to_string())?;
        let facing = match std::env::args().nth(2).as_deref().unwrap_or("right") {
            "up" => Facing::Up,
            "down" => Facing::Down,
            "left" => Facing::Left,
            "right" => Facing::Right,
            direction => return Err(format!("unsupported facing: {direction}")),
        };
        let progress = std::env::args()
            .nth(3)
            .map(|frames| frames.parse::<u8>().map_err(|error| error.to_string()))
            .transpose()?
            .unwrap_or(15);
        let player = TilePosition {
            x: std::env::args()
                .nth(4)
                .map(|value| value.parse::<i16>())
                .transpose()
                .map_err(|error| error.to_string())?
                .unwrap_or(10),
            y: std::env::args()
                .nth(5)
                .map(|value| value.parse::<i16>())
                .transpose()
                .map_err(|error| error.to_string())?
                .unwrap_or(13),
        };
        let (camera_x, camera_y, error) = native::fit_littleroot_camera(&reference)?;
        println!("camera_x={camera_x} camera_y={camera_y} sampled_error={error}");
        let native_frame = native::render_littleroot_with_idle_objects(
            &player,
            facing,
            if progress == 0 { None } else { Some(facing) },
            progress,
        )?;
        println!(
            "native_{facing:?}_{progress}={:?}",
            pixel_diff(&native_frame, &reference)
        );
        return Ok(());
    }
    let session = LittlerootSession::new();
    println!("frame_bytes={}", session.frame_rgb().len());
    println!("frame_sha256={}", frame_sha256(session.frame_rgb()));
    Ok(())
}
