//! Rust gold lane for GameBench Sokoban — parity with `gold_python`.

mod engine;
mod task;

pub use engine::SokobanSession;
pub use task::{resolve_task, ResolvedTask, BOX, BOX_ON_TARGET, FLOOR, PLAYER, PLAYER_ON_TARGET, TARGET, WALL};
