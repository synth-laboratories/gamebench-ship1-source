//! A research-safe, deterministic side-scrolling platformer for GameBench.
//!
//! The environment is an original clean-room implementation.  It contains no
//! ROM bytes, extracted maps, sprites, audio, or other Nintendo-derived assets.
//! The 32 courses are authored from compact capability-oriented blueprints and
//! intentionally do not claim pixel, map, timing, or content parity with SMB.

use serde::{Deserialize, Serialize};
use std::fmt;

pub const FRAME_WIDTH: usize = 256;
pub const FRAME_HEIGHT: usize = 240;
pub const TILE: i32 = 16;
pub const FP_ONE: i32 = 256;
pub const PLAYER_WIDTH: i32 = 12;
pub const PLAYER_HEIGHT: i32 = 16;
pub const ACTION_SPACE: [&str; 15] = [
    "neutral",
    "left",
    "right",
    "down",
    "jump",
    "run",
    "left_jump",
    "right_jump",
    "left_run",
    "right_run",
    "left_jump_run",
    "right_jump_run",
    "down_jump",
    "down_left",
    "down_right",
];

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq, Hash)]
pub struct LevelId {
    pub world: u8,
    pub level: u8,
}

impl LevelId {
    pub const fn new(world: u8, level: u8) -> Self {
        Self { world, level }
    }

    pub fn is_valid(self) -> bool {
        (1..=8).contains(&self.world) && (1..=4).contains(&self.level)
    }

    pub const fn index(self) -> usize {
        ((self.world.saturating_sub(1)) as usize * 4) + self.level.saturating_sub(1) as usize
    }

    pub fn parse(value: &str) -> Option<Self> {
        let mut parts = value.split(['-', '/']);
        let world = parts.next()?.parse().ok()?;
        let level = parts.next()?.parse().ok()?;
        let id = Self::new(world, level);
        id.is_valid().then_some(id)
    }
}

impl fmt::Display for LevelId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}-{}", self.world, self.level)
    }
}

pub const ODYSSEUS_LEVELS: [LevelId; 32] = {
    let mut out = [LevelId::new(1, 1); 32];
    let mut i = 0;
    while i < 32 {
        out[i] = LevelId::new((i / 4 + 1) as u8, (i % 4 + 1) as u8);
        i += 1;
    }
    out
};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Theme {
    Meadow,
    Cavern,
    Water,
    Sky,
    Castle,
}

impl Theme {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Meadow => "meadow",
            Self::Cavern => "cavern",
            Self::Water => "water",
            Self::Sky => "sky",
            Self::Castle => "castle",
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
pub struct Input {
    pub left: bool,
    pub right: bool,
    pub down: bool,
    pub jump: bool,
    pub run: bool,
    pub enter: bool,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Neutral,
    Left,
    Right,
    Down,
    Jump,
    Run,
    LeftJump,
    RightJump,
    LeftRun,
    RightRun,
    LeftJumpRun,
    RightJumpRun,
    DownJump,
    DownLeft,
    DownRight,
}

impl Action {
    pub fn parse(value: &str) -> Option<Self> {
        let normalized = value.trim().to_ascii_lowercase().replace(['+', ' '], "_");
        Some(match normalized.as_str() {
            "neutral" | "noop" | "none" => Self::Neutral,
            "left" => Self::Left,
            "right" => Self::Right,
            "down" => Self::Down,
            "jump" => Self::Jump,
            "run" => Self::Run,
            "left_jump" => Self::LeftJump,
            "right_jump" => Self::RightJump,
            "left_run" => Self::LeftRun,
            "right_run" => Self::RightRun,
            "left_jump_run" => Self::LeftJumpRun,
            "right_jump_run" => Self::RightJumpRun,
            "down_jump" => Self::DownJump,
            "down_left" => Self::DownLeft,
            "down_right" => Self::DownRight,
            _ => return None,
        })
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Neutral => "neutral",
            Self::Left => "left",
            Self::Right => "right",
            Self::Down => "down",
            Self::Jump => "jump",
            Self::Run => "run",
            Self::LeftJump => "left_jump",
            Self::RightJump => "right_jump",
            Self::LeftRun => "left_run",
            Self::RightRun => "right_run",
            Self::LeftJumpRun => "left_jump_run",
            Self::RightJumpRun => "right_jump_run",
            Self::DownJump => "down_jump",
            Self::DownLeft => "down_left",
            Self::DownRight => "down_right",
        }
    }

    pub fn input(self) -> Input {
        match self {
            Self::Neutral => Input::default(),
            Self::Left => Input {
                left: true,
                ..Input::default()
            },
            Self::Right => Input {
                right: true,
                ..Input::default()
            },
            Self::Down => Input {
                down: true,
                ..Input::default()
            },
            Self::Jump => Input {
                jump: true,
                ..Input::default()
            },
            Self::Run => Input {
                run: true,
                ..Input::default()
            },
            Self::LeftJump => Input {
                left: true,
                jump: true,
                ..Input::default()
            },
            Self::RightJump => Input {
                right: true,
                jump: true,
                ..Input::default()
            },
            Self::LeftRun => Input {
                left: true,
                run: true,
                ..Input::default()
            },
            Self::RightRun => Input {
                right: true,
                run: true,
                ..Input::default()
            },
            Self::LeftJumpRun => Input {
                left: true,
                jump: true,
                run: true,
                ..Input::default()
            },
            Self::RightJumpRun => Input {
                right: true,
                jump: true,
                run: true,
                ..Input::default()
            },
            Self::DownJump => Input {
                down: true,
                jump: true,
                ..Input::default()
            },
            Self::DownLeft => Input {
                down: true,
                left: true,
                ..Input::default()
            },
            Self::DownRight => Input {
                down: true,
                right: true,
                ..Input::default()
            },
        }
    }
}

impl From<Action> for Input {
    fn from(value: Action) -> Self {
        value.input()
    }
}

impl TryFrom<&str> for Action {
    type Error = &'static str;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        Self::parse(value).ok_or("unsupported action")
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PowerState {
    Small,
    Big,
    Fire,
    Star,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum EnemyKind {
    Walker,
    Shell,
    Flyer,
    Fish,
    Spike,
}

impl EnemyKind {
    fn speed(self) -> i32 {
        match self {
            Self::Walker => 32,
            Self::Shell => 42,
            Self::Flyer => 24,
            Self::Fish => 20,
            Self::Spike => 0,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum CollectibleKind {
    Coin,
    Mushroom,
    Flower,
    Star,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BlockKind {
    Solid,
    Question,
    Breakable,
    Used,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Motion {
    Horizontal,
    Vertical,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum HazardKind {
    Pit,
    Lava,
    Water,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Span {
    pub start: i32,
    pub end: i32,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct BlockSpec {
    pub x: i32,
    pub y: i32,
    pub kind: BlockKind,
    pub contents: Option<CollectibleKind>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct CoinSpec {
    pub x: i32,
    pub y: i32,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct EnemySpec {
    pub kind: EnemyKind,
    pub x: i32,
    pub y: i32,
    pub patrol_min: i32,
    pub patrol_max: i32,
    pub spawn_frame: u64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct PlatformSpec {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub amplitude: i32,
    pub period: u16,
    pub phase: u16,
    pub motion: Motion,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct PipeSpec {
    pub x: i32,
    pub y: i32,
    pub destination_x: i32,
    pub destination_y: i32,
    pub route_label: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct HazardSpec {
    pub span: Span,
    pub kind: HazardKind,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct RouteNode {
    pub x: i32,
    pub label: String,
    pub required_coins: u16,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct LevelSpec {
    pub id: LevelId,
    pub title: String,
    pub theme: Theme,
    pub width_tiles: i32,
    pub height_tiles: i32,
    pub timer_frames: u32,
    pub goal_x: i32,
    pub floor_spans: Vec<Span>,
    pub blocks: Vec<BlockSpec>,
    pub coins: Vec<CoinSpec>,
    pub enemies: Vec<EnemySpec>,
    pub moving_platforms: Vec<PlatformSpec>,
    pub pipes: Vec<PipeSpec>,
    pub hazards: Vec<HazardSpec>,
    pub route: Vec<RouteNode>,
    pub capability_tags: Vec<String>,
    pub authoring_signature: u32,
}

impl LevelSpec {
    pub fn fingerprint(&self) -> u64 {
        // This is a fingerprint of our own authored blueprint, never of ROM
        // bytes or extracted proprietary content.
        let mut hash = 0xcbf29ce484222325u64 ^ self.authoring_signature as u64;
        for byte in serde_json::to_vec(self).expect("LevelSpec is serializable") {
            hash ^= u64::from(byte);
            hash = hash.wrapping_mul(0x100000001b3);
        }
        hash
    }
}

#[derive(Clone, Copy)]
struct Authoring {
    theme: Theme,
    width: u16,
    gaps: [[u16; 2]; 2],
    ledges: [[u16; 3]; 4],
    blocks: [u16; 4],
    coins: [u16; 4],
    enemies: [u16; 4],
    platform: [u16; 4],
    pipes: [u16; 2],
    route: [u16; 3],
    signature: u32,
}

// Each row is an independent, original capability blueprint.  The values
// describe mechanics and abstract geometry only; they were not copied from a
// ROM or an extracted level representation.
const AUTHORED: [Authoring; 32] = [
    Authoring {
        theme: Theme::Meadow,
        width: 122,
        gaps: [[24, 27], [65, 69]],
        ledges: [[10, 4, 10], [35, 5, 8], [54, 3, 11], [86, 6, 9]],
        blocks: [14, 39, 58, 91],
        coins: [12, 18, 42, 88],
        enemies: [20, 44, 73, 101],
        platform: [52, 10, 4, 3],
        pipes: [30, 78],
        route: [40, 76, 99],
        signature: 0x1101,
    },
    Authoring {
        theme: Theme::Cavern,
        width: 128,
        gaps: [[31, 34], [91, 95]],
        ledges: [[8, 5, 9], [42, 4, 7], [63, 7, 10], [104, 5, 8]],
        blocks: [16, 46, 68, 108],
        coins: [13, 25, 49, 106],
        enemies: [22, 52, 82, 112],
        platform: [70, 6, 5, 4],
        pipes: [36, 83],
        route: [48, 85, 108],
        signature: 0x1102,
    },
    Authoring {
        theme: Theme::Sky,
        width: 116,
        gaps: [[19, 22], [57, 61]],
        ledges: [[6, 4, 10], [27, 5, 7], [72, 4, 9], [91, 7, 6]],
        blocks: [11, 33, 76, 98],
        coins: [9, 17, 74, 94],
        enemies: [18, 39, 68, 103],
        platform: [44, 7, 4, 5],
        pipes: [25, 80],
        route: [37, 70, 96],
        signature: 0x1103,
    },
    Authoring {
        theme: Theme::Castle,
        width: 134,
        gaps: [[28, 32], [72, 77]],
        ledges: [[12, 5, 9], [40, 3, 6], [83, 6, 10], [111, 5, 7]],
        blocks: [17, 45, 88, 116],
        coins: [15, 24, 51, 114],
        enemies: [23, 56, 92, 121],
        platform: [59, 8, 5, 4],
        pipes: [35, 98],
        route: [52, 96, 117],
        signature: 0x1104,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 138,
        gaps: [[36, 40], [104, 108]],
        ledges: [[9, 6, 10], [48, 4, 8], [72, 5, 11], [119, 7, 9]],
        blocks: [18, 53, 78, 126],
        coins: [14, 31, 70, 122],
        enemies: [26, 58, 89, 113],
        platform: [83, 9, 5, 3],
        pipes: [43, 96],
        route: [55, 101, 124],
        signature: 0x1201,
    },
    Authoring {
        theme: Theme::Water,
        width: 130,
        gaps: [[22, 28], [78, 84]],
        ledges: [[7, 5, 9], [35, 4, 7], [92, 5, 10], [108, 6, 8]],
        blocks: [13, 42, 96, 115],
        coins: [11, 26, 48, 101],
        enemies: [17, 50, 88, 118],
        platform: [62, 7, 6, 4],
        pipes: [31, 87],
        route: [45, 83, 113],
        signature: 0x1202,
    },
    Authoring {
        theme: Theme::Water,
        width: 142,
        gaps: [[29, 34], [95, 101]],
        ledges: [[11, 4, 10], [45, 6, 8], [67, 4, 11], [115, 7, 7]],
        blocks: [15, 50, 73, 121],
        coins: [13, 24, 61, 117],
        enemies: [20, 55, 86, 128],
        platform: [76, 6, 5, 5],
        pipes: [38, 108],
        route: [56, 106, 126],
        signature: 0x1203,
    },
    Authoring {
        theme: Theme::Castle,
        width: 146,
        gaps: [[41, 45], [88, 93]],
        ledges: [[14, 5, 8], [52, 4, 10], [73, 6, 7], [124, 5, 9]],
        blocks: [20, 59, 79, 130],
        coins: [18, 38, 69, 126],
        enemies: [26, 66, 98, 136],
        platform: [94, 7, 4, 4],
        pipes: [48, 113],
        route: [63, 111, 134],
        signature: 0x1204,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 126,
        gaps: [[26, 29], [70, 74]],
        ledges: [[8, 4, 11], [33, 6, 9], [55, 4, 7], [93, 7, 10]],
        blocks: [12, 37, 62, 98],
        coins: [10, 21, 57, 95],
        enemies: [19, 45, 78, 109],
        platform: [48, 8, 5, 3],
        pipes: [32, 82],
        route: [44, 80, 103],
        signature: 0x1301,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 132,
        gaps: [[34, 38], [81, 85]],
        ledges: [[10, 5, 9], [44, 4, 6], [63, 6, 10], [101, 5, 8]],
        blocks: [16, 48, 70, 108],
        coins: [13, 27, 59, 105],
        enemies: [21, 54, 88, 116],
        platform: [73, 7, 4, 4],
        pipes: [40, 93],
        route: [51, 91, 112],
        signature: 0x1302,
    },
    Authoring {
        theme: Theme::Sky,
        width: 140,
        gaps: [[18, 23], [61, 66]],
        ledges: [[7, 5, 10], [29, 4, 7], [76, 6, 9], [110, 7, 6]],
        blocks: [13, 36, 81, 116],
        coins: [10, 20, 78, 112],
        enemies: [17, 43, 72, 123],
        platform: [47, 6, 5, 5],
        pipes: [25, 96],
        route: [39, 86, 115],
        signature: 0x1303,
    },
    Authoring {
        theme: Theme::Castle,
        width: 150,
        gaps: [[25, 30], [102, 108]],
        ledges: [[13, 6, 8], [49, 3, 10], [75, 5, 7], [123, 7, 9]],
        blocks: [18, 56, 82, 133],
        coins: [16, 27, 68, 129],
        enemies: [22, 63, 94, 141],
        platform: [91, 8, 5, 4],
        pipes: [36, 115],
        route: [58, 111, 138],
        signature: 0x1304,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 136,
        gaps: [[42, 46], [89, 94]],
        ledges: [[9, 4, 10], [37, 6, 8], [66, 4, 11], [112, 5, 9]],
        blocks: [14, 42, 72, 118],
        coins: [12, 30, 64, 110],
        enemies: [20, 50, 83, 125],
        platform: [79, 9, 4, 3],
        pipes: [34, 100],
        route: [48, 98, 121],
        signature: 0x1401,
    },
    Authoring {
        theme: Theme::Cavern,
        width: 144,
        gaps: [[32, 36], [117, 122]],
        ledges: [[12, 5, 9], [47, 4, 7], [70, 6, 10], [127, 5, 8]],
        blocks: [17, 52, 78, 134],
        coins: [15, 28, 66, 130],
        enemies: [24, 61, 92, 138],
        platform: [84, 7, 6, 4],
        pipes: [40, 103],
        route: [56, 101, 133],
        signature: 0x1402,
    },
    Authoring {
        theme: Theme::Sky,
        width: 124,
        gaps: [[21, 25], [54, 59]],
        ledges: [[5, 5, 9], [28, 4, 6], [68, 5, 10], [88, 7, 7]],
        blocks: [10, 34, 73, 96],
        coins: [8, 18, 65, 92],
        enemies: [15, 40, 61, 106],
        platform: [44, 6, 4, 5],
        pipes: [26, 79],
        route: [37, 77, 101],
        signature: 0x1403,
    },
    Authoring {
        theme: Theme::Castle,
        width: 152,
        gaps: [[47, 52], [85, 91]],
        ledges: [[15, 4, 10], [54, 6, 7], [72, 4, 9], [128, 7, 6]],
        blocks: [21, 62, 79, 137],
        coins: [19, 35, 68, 132],
        enemies: [29, 69, 101, 145],
        platform: [96, 8, 5, 4],
        pipes: [43, 116],
        route: [61, 114, 143],
        signature: 0x1404,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 156,
        gaps: [[27, 31], [108, 113]],
        ledges: [[8, 6, 10], [39, 4, 8], [80, 5, 11], [126, 7, 9]],
        blocks: [14, 46, 85, 135],
        coins: [12, 25, 76, 130],
        enemies: [20, 55, 98, 145],
        platform: [92, 9, 6, 3],
        pipes: [35, 118],
        route: [52, 116, 141],
        signature: 0x1501,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 148,
        gaps: [[38, 42], [69, 74]],
        ledges: [[11, 5, 8], [48, 6, 10], [61, 3, 6], [117, 5, 9]],
        blocks: [17, 54, 66, 124],
        coins: [15, 29, 58, 120],
        enemies: [23, 64, 88, 133],
        platform: [82, 7, 5, 4],
        pipes: [45, 104],
        route: [59, 102, 129],
        signature: 0x1502,
    },
    Authoring {
        theme: Theme::Sky,
        width: 160,
        gaps: [[17, 22], [73, 79]],
        ledges: [[6, 4, 10], [31, 7, 7], [90, 5, 9], [132, 8, 6]],
        blocks: [11, 38, 96, 140],
        coins: [9, 20, 86, 136],
        enemies: [16, 48, 80, 150],
        platform: [57, 6, 5, 6],
        pipes: [25, 111],
        route: [42, 99, 145],
        signature: 0x1503,
    },
    Authoring {
        theme: Theme::Castle,
        width: 158,
        gaps: [[33, 38], [120, 126]],
        ledges: [[14, 5, 9], [52, 4, 7], [82, 6, 10], [135, 6, 8]],
        blocks: [19, 58, 89, 143],
        coins: [17, 30, 77, 138],
        enemies: [25, 66, 106, 151],
        platform: [101, 8, 5, 4],
        pipes: [44, 128],
        route: [64, 125, 148],
        signature: 0x1504,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 162,
        gaps: [[45, 49], [99, 105]],
        ledges: [[10, 5, 10], [41, 6, 8], [71, 4, 11], [128, 7, 7]],
        blocks: [15, 48, 76, 137],
        coins: [13, 33, 69, 132],
        enemies: [21, 58, 91, 149],
        platform: [86, 9, 5, 3],
        pipes: [37, 118],
        route: [54, 116, 143],
        signature: 0x1601,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 154,
        gaps: [[24, 28], [82, 87]],
        ledges: [[8, 4, 9], [35, 5, 7], [64, 6, 10], [119, 5, 8]],
        blocks: [12, 43, 70, 127],
        coins: [10, 23, 61, 123],
        enemies: [18, 52, 98, 139],
        platform: [77, 7, 6, 4],
        pipes: [31, 108],
        route: [47, 106, 132],
        signature: 0x1602,
    },
    Authoring {
        theme: Theme::Sky,
        width: 166,
        gaps: [[29, 34], [58, 64]],
        ledges: [[5, 5, 10], [22, 4, 6], [76, 7, 9], [141, 6, 7]],
        blocks: [9, 29, 83, 149],
        coins: [7, 17, 72, 145],
        enemies: [14, 44, 68, 155],
        platform: [48, 6, 5, 6],
        pipes: [37, 120],
        route: [52, 105, 151],
        signature: 0x1603,
    },
    Authoring {
        theme: Theme::Castle,
        width: 170,
        gaps: [[40, 46], [109, 115]],
        ledges: [[13, 6, 8], [56, 3, 10], [81, 6, 7], [139, 8, 9]],
        blocks: [18, 63, 88, 149],
        coins: [16, 34, 75, 145],
        enemies: [27, 70, 101, 160],
        platform: [96, 8, 6, 5],
        pipes: [49, 126],
        route: [67, 124, 157],
        signature: 0x1604,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 174,
        gaps: [[20, 24], [130, 136]],
        ledges: [[7, 6, 10], [45, 5, 8], [74, 4, 11], [145, 7, 9]],
        blocks: [12, 52, 80, 155],
        coins: [10, 29, 72, 149],
        enemies: [17, 62, 99, 165],
        platform: [93, 9, 5, 3],
        pipes: [33, 122],
        route: [57, 120, 161],
        signature: 0x1701,
    },
    Authoring {
        theme: Theme::Cavern,
        width: 168,
        gaps: [[35, 40], [94, 100]],
        ledges: [[11, 4, 9], [51, 6, 7], [70, 5, 10], [137, 6, 8]],
        blocks: [16, 58, 78, 145],
        coins: [14, 31, 66, 141],
        enemies: [23, 69, 108, 158],
        platform: [85, 7, 6, 4],
        pipes: [45, 117],
        route: [63, 115, 153],
        signature: 0x1702,
    },
    Authoring {
        theme: Theme::Sky,
        width: 176,
        gaps: [[26, 31], [67, 73]],
        ledges: [[6, 5, 9], [30, 4, 6], [86, 6, 10], [148, 8, 7]],
        blocks: [11, 37, 93, 157],
        coins: [9, 20, 81, 151],
        enemies: [16, 50, 76, 166],
        platform: [52, 6, 5, 6],
        pipes: [39, 129],
        route: [55, 111, 163],
        signature: 0x1703,
    },
    Authoring {
        theme: Theme::Castle,
        width: 180,
        gaps: [[49, 55], [121, 128]],
        ledges: [[15, 5, 8], [58, 5, 10], [88, 4, 7], [149, 9, 9]],
        blocks: [21, 66, 94, 160],
        coins: [19, 38, 83, 154],
        enemies: [29, 73, 111, 170],
        platform: [104, 8, 6, 5],
        pipes: [46, 135],
        route: [70, 133, 167],
        signature: 0x1704,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 184,
        gaps: [[32, 37], [143, 149]],
        ledges: [[9, 6, 10], [43, 4, 8], [79, 6, 11], [155, 7, 7]],
        blocks: [15, 50, 85, 166],
        coins: [13, 27, 75, 160],
        enemies: [20, 61, 105, 176],
        platform: [98, 9, 6, 3],
        pipes: [39, 132],
        route: [60, 130, 173],
        signature: 0x1801,
    },
    Authoring {
        theme: Theme::Meadow,
        width: 178,
        gaps: [[23, 27], [91, 96]],
        ledges: [[8, 5, 9], [35, 7, 7], [69, 4, 10], [144, 6, 8]],
        blocks: [12, 44, 75, 153],
        coins: [10, 24, 64, 148],
        enemies: [18, 55, 111, 164],
        platform: [84, 7, 6, 4],
        pipes: [30, 120],
        route: [49, 118, 160],
        signature: 0x1802,
    },
    Authoring {
        theme: Theme::Castle,
        width: 186,
        gaps: [[44, 50], [101, 108]],
        ledges: [[12, 5, 10], [52, 4, 6], [82, 7, 9], [157, 8, 7]],
        blocks: [17, 59, 91, 168],
        coins: [15, 33, 74, 161],
        enemies: [24, 67, 119, 177],
        platform: [112, 8, 5, 5],
        pipes: [41, 139],
        route: [62, 137, 174],
        signature: 0x1803,
    },
    Authoring {
        theme: Theme::Castle,
        width: 192,
        gaps: [[55, 61], [128, 135]],
        ledges: [[16, 6, 8], [64, 5, 10], [96, 4, 7], [164, 9, 9]],
        blocks: [22, 73, 102, 176],
        coins: [20, 40, 88, 170],
        enemies: [31, 79, 121, 183],
        platform: [120, 8, 6, 5],
        pipes: [48, 146],
        route: [76, 144, 181],
        signature: 0x1804,
    },
];

pub fn level_spec(id: LevelId) -> Result<LevelSpec, &'static str> {
    if !id.is_valid() {
        return Err("level must be world 1-8, level 1-4");
    }
    let a = AUTHORED[id.index()];
    let width = i32::from(a.width);
    let mut floor_spans = Vec::new();
    let mut cursor = 0;
    for gap in a.gaps {
        if cursor < i32::from(gap[0]) {
            floor_spans.push(Span {
                start: cursor,
                end: i32::from(gap[0]),
            });
        }
        cursor = i32::from(gap[1]);
    }
    floor_spans.push(Span {
        start: cursor,
        end: width,
    });

    let mut blocks = Vec::new();
    for (i, x) in a.blocks.into_iter().enumerate() {
        let kind = match (i + id.index()) % 4 {
            0 => BlockKind::Question,
            1 => BlockKind::Breakable,
            _ => BlockKind::Solid,
        };
        let contents = if kind == BlockKind::Question {
            Some(match id.index() % 4 {
                0 => CollectibleKind::Mushroom,
                1 => CollectibleKind::Coin,
                2 => CollectibleKind::Flower,
                _ => CollectibleKind::Star,
            })
        } else {
            None
        };
        blocks.push(BlockSpec {
            x: i32::from(x),
            y: 7 + i as i32 % 3,
            kind,
            contents,
        });
    }
    for (i, ledge) in a.ledges.into_iter().enumerate() {
        for dx in 0..ledge[1] {
            let offset = dx + i as u16;
            let breakable = offset / 3 * 3 == offset;
            blocks.push(BlockSpec {
                x: i32::from(ledge[0] + dx),
                y: i32::from(ledge[2]),
                kind: if breakable {
                    BlockKind::Breakable
                } else {
                    BlockKind::Solid
                },
                contents: None,
            });
        }
    }

    let coins = a
        .coins
        .into_iter()
        .enumerate()
        .map(|(i, x)| CoinSpec {
            x: i32::from(x),
            y: 6 + (i as i32 % 3) * 2,
        })
        .collect();

    let enemy_kind = |i: usize| match a.theme {
        Theme::Water => {
            if i & 1 == 0 {
                EnemyKind::Fish
            } else {
                EnemyKind::Walker
            }
        }
        Theme::Sky => {
            if i & 1 == 0 {
                EnemyKind::Flyer
            } else {
                EnemyKind::Walker
            }
        }
        Theme::Castle => {
            if i == 2 {
                EnemyKind::Spike
            } else {
                EnemyKind::Shell
            }
        }
        Theme::Cavern => {
            if i == 3 {
                EnemyKind::Spike
            } else {
                EnemyKind::Walker
            }
        }
        Theme::Meadow => {
            if i == 3 {
                EnemyKind::Shell
            } else {
                EnemyKind::Walker
            }
        }
    };
    let enemies = a
        .enemies
        .into_iter()
        .enumerate()
        .map(|(i, x)| EnemySpec {
            kind: enemy_kind(i),
            x: i32::from(x) * TILE,
            y: if matches!(enemy_kind(i), EnemyKind::Fish | EnemyKind::Flyer) {
                120 * FP_ONE
            } else {
                0
            },
            patrol_min: (i32::from(x) - 5).max(1) * TILE,
            patrol_max: (i32::from(x) + 5).min(width - 2) * TILE,
            spawn_frame: (i as u64 * 42) + (id.index() as u64 % 3) * 7,
        })
        .collect();

    let platform_x = i32::from(a.platform[0]) * TILE;
    let moving_platforms = vec![
        PlatformSpec {
            x: platform_x,
            y: i32::from(a.platform[1]) * TILE,
            width: i32::from(a.platform[2].max(3)) * TILE,
            amplitude: i32::from(a.platform[3].max(2)) * TILE,
            period: 96 + id.world as u16 * 4,
            phase: id.level as u16 * 11,
            motion: if id.level == 3 {
                Motion::Vertical
            } else {
                Motion::Horizontal
            },
        },
        PlatformSpec {
            x: (platform_x + 17 * TILE).min((width - 8) * TILE),
            y: 6 * TILE,
            width: 4 * TILE,
            amplitude: (2 + id.level as i32) * TILE,
            period: 128,
            phase: 31 + id.world as u16,
            motion: if a.theme == Theme::Sky {
                Motion::Vertical
            } else {
                Motion::Horizontal
            },
        },
    ];

    let pipes = a
        .pipes
        .into_iter()
        .enumerate()
        .map(|(i, x)| PipeSpec {
            x: i32::from(x),
            y: if i == 0 { 11 } else { 10 },
            destination_x: i32::from(a.route[i]),
            destination_y: 11,
            route_label: if i == 0 { "lower_route" } else { "upper_route" }.to_string(),
        })
        .collect();

    let hazards = a
        .gaps
        .into_iter()
        .map(|gap| HazardSpec {
            span: Span {
                start: i32::from(gap[0]),
                end: i32::from(gap[1]),
            },
            kind: match a.theme {
                Theme::Castle => HazardKind::Lava,
                Theme::Water => HazardKind::Water,
                _ => HazardKind::Pit,
            },
        })
        .collect();

    let mut route = vec![
        RouteNode {
            x: 2,
            label: "spawn".to_string(),
            required_coins: 0,
        },
        RouteNode {
            x: i32::from(a.route[0]),
            label: "first_checkpoint".to_string(),
            required_coins: 0,
        },
        RouteNode {
            x: i32::from(a.route[1]),
            label: "branch_checkpoint".to_string(),
            required_coins: (id.index() % 3) as u16,
        },
        RouteNode {
            x: i32::from(a.route[2]),
            label: "goal_approach".to_string(),
            required_coins: 0,
        },
        RouteNode {
            x: width - 5,
            label: "terminal_goal".to_string(),
            required_coins: 0,
        },
    ];
    route.sort_by_key(|node| node.x);

    let mut tags = vec![
        "fixed_point".to_string(),
        "route_progress".to_string(),
        "rgb_observation".to_string(),
    ];
    match a.theme {
        Theme::Meadow => tags.extend([
            "gaps".to_string(),
            "blocks".to_string(),
            "walkers".to_string(),
        ]),
        Theme::Cavern => tags.extend([
            "vertical_clearance".to_string(),
            "breakable_blocks".to_string(),
            "pipes".to_string(),
        ]),
        Theme::Water => tags.extend([
            "water_physics".to_string(),
            "fish_schedule".to_string(),
            "moving_platforms".to_string(),
        ]),
        Theme::Sky => tags.extend([
            "moving_platforms".to_string(),
            "air_control".to_string(),
            "flyers".to_string(),
        ]),
        Theme::Castle => tags.extend([
            "lava".to_string(),
            "damage".to_string(),
            "shells".to_string(),
            "terminal_goal".to_string(),
        ]),
    }
    tags.push(format!("authoring_variant_{:x}", a.signature));

    Ok(LevelSpec {
        id,
        title: format!(
            "Research course W{}-{} ({})",
            id.world,
            id.level,
            a.theme.as_str()
        ),
        theme: a.theme,
        width_tiles: width,
        height_tiles: 15,
        timer_frames: 3_600 + (id.world as u32 * 90) + (id.level as u32 * 30),
        goal_x: width - 5,
        floor_spans,
        blocks,
        coins,
        enemies,
        moving_platforms,
        pipes,
        hazards,
        route,
        capability_tags: tags,
        authoring_signature: a.signature,
    })
}

pub fn all_level_specs() -> Vec<LevelSpec> {
    ODYSSEUS_LEVELS
        .iter()
        .map(|&id| level_spec(id).expect("catalog level"))
        .collect()
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Player {
    pub x: i32,
    pub y: i32,
    pub vx: i32,
    pub vy: i32,
    pub grounded: bool,
    pub facing: i8,
    pub power: PowerState,
    pub invincibility_frames: u16,
    pub lives: u8,
    pub score: u32,
    pub coins: u16,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct EnemyState {
    pub id: u16,
    pub kind: EnemyKind,
    pub x: i32,
    pub y: i32,
    pub vx: i32,
    pub vy: i32,
    pub active: bool,
    pub defeated: bool,
    pub spawn_frame: u64,
    pub patrol_min: i32,
    pub patrol_max: i32,
    pub base_y: i32,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct CollectibleState {
    pub id: u16,
    pub kind: CollectibleKind,
    pub x: i32,
    pub y: i32,
    pub vx: i32,
    pub vy: i32,
    pub active: bool,
    pub from_block: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct BlockState {
    pub id: u16,
    pub x: i32,
    pub y: i32,
    pub kind: BlockKind,
    pub contents: Option<CollectibleKind>,
    pub active: bool,
    pub used: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct PlatformState {
    pub id: u16,
    pub x: i32,
    pub y: i32,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TerminalReason {
    Completed,
    Death,
    Timeout,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Snapshot {
    pub level: LevelId,
    pub seed: u64,
    pub frame: u64,
    pub player: Player,
    pub enemies: Vec<EnemyState>,
    pub collectibles: Vec<CollectibleState>,
    pub blocks: Vec<BlockState>,
    pub platforms: Vec<PlatformState>,
    pub terminal: bool,
    pub terminal_reason: Option<TerminalReason>,
    pub max_tile_x: i32,
    pub max_height_px: i32,
    pub route_index: usize,
    pub timer_frames: u32,
    pub visited_routes: Vec<String>,
    #[serde(default)]
    pub event_log: Vec<Event>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Event {
    EpisodeStarted {
        level: LevelId,
        seed: u64,
        theme: Theme,
    },
    Jumped,
    Landed,
    Progress {
        tile_x: i32,
        route_index: usize,
        progress_milli: u16,
    },
    RouteCheckpoint {
        index: usize,
        label: String,
    },
    EntitySpawned {
        id: u16,
        enemy_kind: EnemyKind,
    },
    BlockHit {
        id: u16,
        contents: Option<CollectibleKind>,
    },
    BlockBroken {
        id: u16,
    },
    CollectibleSpawned {
        id: u16,
        collectible_kind: CollectibleKind,
    },
    CoinCollected {
        total: u16,
    },
    PowerChanged {
        from: PowerState,
        to: PowerState,
    },
    EnemyStomped {
        id: u16,
        enemy_kind: EnemyKind,
    },
    DamageTaken {
        power: PowerState,
    },
    PipeEntered {
        route_label: String,
    },
    Transitioned {
        x_tile: i32,
    },
    MovingPlatformLanded {
        id: u16,
    },
    TimedOut,
    Died {
        cause: String,
        lives_remaining: u8,
    },
    LevelCompleted {
        score: u32,
        coins: u16,
    },
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct ProgressReport {
    pub progress_milli: u16,
    pub max_tile_x: i32,
    pub route_index: usize,
    pub route_count: usize,
    pub route_label: String,
    pub axis: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Step {
    pub events: Vec<Event>,
    pub terminal: bool,
    pub terminal_reason: Option<TerminalReason>,
    pub progress: ProgressReport,
    pub progress_milli: u16,
    pub reward: i32,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Readout {
    pub level_id: String,
    pub title: String,
    pub theme: Theme,
    pub frame: u64,
    pub timer_frames: u32,
    pub terminal: bool,
    pub terminal_reason: Option<TerminalReason>,
    pub score: u32,
    pub coins: u16,
    pub lives: u8,
    pub power: PowerState,
    pub player_x_px: i32,
    pub player_y_px: i32,
    pub progress: ProgressReport,
    pub active_entities: usize,
    pub defeated_entities: usize,
    pub remaining_collectibles: usize,
    pub capability_tags: Vec<String>,
    pub allowed_actions: Vec<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Rect {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
}

impl Rect {
    fn overlaps(self, other: Self) -> bool {
        self.x < other.x + other.w
            && self.x + self.w > other.x
            && self.y < other.y + other.h
            && self.y + self.h > other.y
    }

    fn horizontal_overlap(self, other: Self) -> bool {
        self.x < other.x + other.w && self.x + self.w > other.x
    }
}

/// Fixed-point simulation. Each [`step`](Env::step) advances exactly one 60 Hz frame.
#[derive(Clone)]
pub struct Env {
    spec: LevelSpec,
    state: Snapshot,
    events: Vec<Event>,
}

impl Env {
    pub fn reset(level: LevelId, seed: u64) -> Result<Self, &'static str> {
        let spec = level_spec(level)?;
        let floor_y = 13 * TILE;
        let player = Player {
            x: 2 * TILE * FP_ONE,
            y: (floor_y - PLAYER_HEIGHT) * FP_ONE,
            vx: 0,
            vy: 0,
            grounded: true,
            facing: 1,
            power: PowerState::Small,
            invincibility_frames: 0,
            lives: 3,
            score: 0,
            coins: 0,
        };
        let enemies = spec
            .enemies
            .iter()
            .enumerate()
            .map(|(i, enemy)| EnemyState {
                id: i as u16,
                kind: enemy.kind,
                x: enemy.x,
                y: if enemy.y == 0 {
                    (floor_y - 12) * FP_ONE
                } else {
                    enemy.y
                },
                vx: enemy.kind.speed(),
                vy: 0,
                active: false,
                defeated: false,
                spawn_frame: enemy.spawn_frame,
                patrol_min: enemy.patrol_min,
                patrol_max: enemy.patrol_max,
                base_y: enemy.y,
            })
            .collect();
        let collectibles = spec
            .coins
            .iter()
            .enumerate()
            .map(|(i, coin)| CollectibleState {
                id: i as u16,
                kind: CollectibleKind::Coin,
                x: coin.x * TILE * FP_ONE,
                y: coin.y * TILE * FP_ONE,
                vx: 0,
                vy: 0,
                active: true,
                from_block: false,
            })
            .collect();
        let blocks = spec
            .blocks
            .iter()
            .enumerate()
            .map(|(i, block)| BlockState {
                id: i as u16,
                x: block.x,
                y: block.y,
                kind: block.kind,
                contents: block.contents,
                active: true,
                used: false,
            })
            .collect();
        let platforms = spec
            .moving_platforms
            .iter()
            .enumerate()
            .map(|(i, platform)| PlatformState {
                id: i as u16,
                x: platform.x,
                y: platform.y,
            })
            .collect();
        let episode_event = Event::EpisodeStarted {
            level,
            seed,
            theme: spec.theme,
        };
        let state = Snapshot {
            level,
            seed,
            frame: 0,
            player,
            enemies,
            collectibles,
            blocks,
            platforms,
            terminal: false,
            terminal_reason: None,
            max_tile_x: 2,
            max_height_px: 0,
            route_index: 0,
            timer_frames: spec.timer_frames,
            visited_routes: vec!["spawn".to_string()],
            event_log: vec![episode_event.clone()],
        };
        Ok(Self {
            events: vec![episode_event],
            spec,
            state,
        })
    }

    pub fn restore(snapshot: Snapshot) -> Result<Self, &'static str> {
        let spec = level_spec(snapshot.level)?;
        if snapshot.frame > 100_000 || snapshot.route_index > spec.route.len() {
            return Err("snapshot is outside supported bounds");
        }
        Ok(Self {
            spec,
            events: snapshot.event_log.clone(),
            state: snapshot,
        })
    }

    pub fn snapshot(&self) -> Snapshot {
        self.state.clone()
    }

    pub fn checkpoint_bytes(&self) -> Result<Vec<u8>, serde_json::Error> {
        serde_json::to_vec(&self.state)
    }

    pub fn from_checkpoint_bytes(bytes: &[u8]) -> Result<Self, &'static str> {
        let snapshot: Snapshot = serde_json::from_slice(bytes).map_err(|_| "invalid checkpoint")?;
        Self::restore(snapshot)
    }

    pub fn level_spec(&self) -> &LevelSpec {
        &self.spec
    }

    pub fn drain_events(&mut self) -> Vec<Event> {
        std::mem::take(&mut self.events)
    }

    pub fn events(&self) -> &[Event] {
        &self.events
    }

    pub fn readout(&self) -> Readout {
        Readout {
            level_id: self.state.level.to_string(),
            title: self.spec.title.clone(),
            theme: self.spec.theme,
            frame: self.state.frame,
            timer_frames: self.state.timer_frames,
            terminal: self.state.terminal,
            terminal_reason: self.state.terminal_reason,
            score: self.state.player.score,
            coins: self.state.player.coins,
            lives: self.state.player.lives,
            power: self.state.player.power,
            player_x_px: self.state.player.x / FP_ONE,
            player_y_px: self.state.player.y / FP_ONE,
            progress: self.progress_report(),
            active_entities: self
                .state
                .enemies
                .iter()
                .filter(|e| e.active && !e.defeated)
                .count(),
            defeated_entities: self.state.enemies.iter().filter(|e| e.defeated).count(),
            remaining_collectibles: self.state.collectibles.iter().filter(|c| c.active).count(),
            capability_tags: self.spec.capability_tags.clone(),
            allowed_actions: ACTION_SPACE.iter().map(|s| (*s).to_string()).collect(),
        }
    }

    pub fn legacy_strings(&self) -> Vec<String> {
        self.events
            .iter()
            .map(event_name)
            .map(str::to_string)
            .collect()
    }

    pub fn step_action(&mut self, action: Action) -> Step {
        self.step(action.input())
    }

    pub fn step(&mut self, input: Input) -> Step {
        if self.state.terminal {
            return self.result(Vec::new(), 0);
        }
        let previous_progress = self.progress_report().progress_milli;
        self.state.frame += 1;
        self.state.timer_frames = self.state.timer_frames.saturating_sub(1);
        let mut emitted = Vec::new();
        let mut reward = 0;
        self.update_platforms();
        self.schedule_entities(&mut emitted);
        self.update_enemies();
        self.update_collectibles();
        self.integrate_player(input, &mut emitted);
        if !self.state.terminal {
            reward += self.collect_collectibles(&mut emitted);
            reward += self.resolve_enemy_collisions(&mut emitted);
            self.try_pipe_transition(input, &mut emitted);
            self.update_route(&mut emitted);
            if self.progress_report().progress_milli > previous_progress {
                reward += 1;
            }
            if self.state.timer_frames == 0 {
                self.state.terminal = true;
                self.state.terminal_reason = Some(TerminalReason::Timeout);
                emitted.push(Event::TimedOut);
                reward -= 10;
            }
            self.check_goal(&mut emitted, &mut reward);
        }
        self.events.extend(emitted.clone());
        self.state.event_log.extend(emitted.clone());
        self.result(emitted, reward)
    }

    fn result(&self, events: Vec<Event>, reward: i32) -> Step {
        let progress = self.progress_report();
        Step {
            progress_milli: progress.progress_milli,
            progress,
            terminal: self.state.terminal,
            terminal_reason: self.state.terminal_reason,
            events,
            reward,
        }
    }

    fn progress_report(&self) -> ProgressReport {
        let x_tile = self.state.max_tile_x;
        let max = (self.spec.goal_x - 2).max(1);
        let progress = ((x_tile - 2).max(0) * 1000 / max).clamp(0, 1000) as u16;
        let label = self
            .spec
            .route
            .get(self.state.route_index)
            .map(|node| node.label.clone())
            .unwrap_or_else(|| "terminal_goal".to_string());
        ProgressReport {
            progress_milli: progress,
            max_tile_x: x_tile,
            route_index: self.state.route_index,
            route_count: self.spec.route.len(),
            route_label: label,
            axis: if matches!(self.spec.theme, Theme::Sky) {
                "horizontal_vertical"
            } else {
                "horizontal"
            }
            .to_string(),
        }
    }

    fn update_platforms(&mut self) {
        for (state, spec) in self
            .state
            .platforms
            .iter_mut()
            .zip(self.spec.moving_platforms.iter())
        {
            let period = i32::from(spec.period.max(2));
            let phase = (self.state.frame as i32 + i32::from(spec.phase)) % period;
            let half = period / 2;
            let offset = if phase <= half {
                spec.amplitude * phase / half.max(1)
            } else {
                spec.amplitude * (period - phase) / (period - half).max(1)
            };
            match spec.motion {
                Motion::Horizontal => {
                    state.x = spec.x + offset;
                    state.y = spec.y;
                }
                Motion::Vertical => {
                    state.x = spec.x;
                    state.y = spec.y - offset;
                }
            }
        }
    }

    fn schedule_entities(&mut self, emitted: &mut Vec<Event>) {
        let frame = self.state.frame;
        for enemy in &mut self.state.enemies {
            if !enemy.active && !enemy.defeated && frame >= enemy.spawn_frame {
                enemy.active = true;
                emitted.push(Event::EntitySpawned {
                    id: enemy.id,
                    enemy_kind: enemy.kind,
                });
            }
        }
    }

    fn update_enemies(&mut self) {
        let solids = self.solid_rects();
        let frame = self.state.frame;
        for enemy in &mut self.state.enemies {
            if !enemy.active || enemy.defeated {
                continue;
            }
            let width = 14;
            let height = 12;
            match enemy.kind {
                EnemyKind::Spike => {}
                EnemyKind::Fish => {
                    let oscillation = ((frame as i32 + i32::from(enemy.id) * 17) % 80) - 40;
                    enemy.y = enemy.base_y + oscillation * FP_ONE / 3;
                }
                EnemyKind::Flyer => {
                    let oscillation = ((frame as i32 + i32::from(enemy.id) * 13) % 96) - 48;
                    enemy.y = enemy.base_y + oscillation * FP_ONE / 4;
                    enemy.x += enemy.vx;
                    if enemy.x < enemy.patrol_min || enemy.x > enemy.patrol_max {
                        enemy.vx = -enemy.vx;
                    }
                }
                EnemyKind::Walker | EnemyKind::Shell => {
                    enemy.x += enemy.vx;
                    let rect = Rect {
                        x: enemy.x / FP_ONE,
                        y: enemy.y / FP_ONE,
                        w: width,
                        h: height,
                    };
                    if enemy.x < enemy.patrol_min
                        || enemy.x > enemy.patrol_max
                        || solids.iter().any(|solid| rect.overlaps(*solid))
                    {
                        enemy.vx = -enemy.vx;
                        enemy.x += enemy.vx * 2;
                    }
                    let old_bottom = enemy.y / FP_ONE + height;
                    enemy.vy = (enemy.vy + 42).min(900);
                    let new_y = enemy.y / FP_ONE + enemy.vy / FP_ONE;
                    let new_bottom = new_y + height;
                    if let Some(surface) = landing_surface(&solids, rect, old_bottom, new_bottom) {
                        enemy.y = (surface - height) * FP_ONE;
                        enemy.vy = 0;
                    } else {
                        enemy.y += enemy.vy;
                    }
                }
            }
            if enemy.y / FP_ONE > FRAME_HEIGHT as i32 + 64 {
                enemy.active = false;
            }
        }
    }

    fn update_collectibles(&mut self) {
        let solids = self.solid_rects();
        for collectible in &mut self.state.collectibles {
            if !collectible.active || matches!(collectible.kind, CollectibleKind::Coin) {
                continue;
            }
            collectible.x += collectible.vx;
            collectible.vy = (collectible.vy + 42).min(800);
            let rect = Rect {
                x: collectible.x / FP_ONE,
                y: collectible.y / FP_ONE,
                w: 12,
                h: 12,
            };
            let old_bottom = rect.y + rect.h;
            let new_bottom = old_bottom + collectible.vy / FP_ONE;
            if let Some(surface) = landing_surface(&solids, rect, old_bottom, new_bottom) {
                collectible.y = (surface - rect.h) * FP_ONE;
                collectible.vy = 0;
            } else {
                collectible.y += collectible.vy;
            }
        }
    }

    fn integrate_player(&mut self, input: Input, emitted: &mut Vec<Event>) {
        let acceleration = if input.run { 42 } else { 28 };
        let max_speed = if input.run { 560 } else { 380 };
        let water = self.spec.theme == Theme::Water;
        {
            let p = &mut self.state.player;
            if p.invincibility_frames > 0 {
                p.invincibility_frames -= 1;
            }
            if input.left ^ input.right {
                if input.left {
                    p.vx -= acceleration;
                    p.facing = -1;
                } else {
                    p.vx += acceleration;
                    p.facing = 1;
                }
            } else {
                p.vx = p.vx * 7 / 8;
            }
            p.vx = p.vx.clamp(-max_speed, max_speed);
            if input.jump && p.grounded {
                p.vy = if water { -620 } else { -960 };
                p.grounded = false;
                emitted.push(Event::Jumped);
            }
            p.vy = (p.vy + if water { 26 } else { 54 }).min(1100);
        }

        let old_bottom = self.state.player.y / FP_ONE + PLAYER_HEIGHT;
        self.move_player_horizontal();
        self.move_player_vertical(old_bottom, emitted);
        self.update_progress(emitted);
        self.check_hazards(emitted);
    }

    fn move_player_horizontal(&mut self) {
        let solids = self.solid_rects();
        let vx = self.state.player.vx;
        let old_x = self.state.player.x / FP_ONE;
        let new_x = old_x + vx / FP_ONE;
        let candidate = Rect {
            x: new_x,
            y: self.state.player.y / FP_ONE,
            w: PLAYER_WIDTH,
            h: PLAYER_HEIGHT,
        };
        if solids.iter().any(|solid| candidate.overlaps(*solid)) {
            if vx > 0 {
                let edge = solids
                    .iter()
                    .filter(|solid| candidate.overlaps(**solid))
                    .map(|solid| solid.x)
                    .min()
                    .unwrap_or(new_x + PLAYER_WIDTH);
                self.state.player.x = (edge - PLAYER_WIDTH) * FP_ONE;
            } else if vx < 0 {
                let edge = solids
                    .iter()
                    .filter(|solid| candidate.overlaps(**solid))
                    .map(|solid| solid.x + solid.w)
                    .max()
                    .unwrap_or(new_x);
                self.state.player.x = edge * FP_ONE;
            }
            self.state.player.vx = 0;
        } else {
            self.state.player.x += vx;
        }
    }

    fn move_player_vertical(&mut self, old_bottom: i32, emitted: &mut Vec<Event>) {
        let vy = self.state.player.vy;
        let px = self.state.player.x / FP_ONE;
        let old_y = self.state.player.y / FP_ONE;
        let new_y = old_y + vy / FP_ONE;
        if vy < 0 {
            let head = Rect {
                x: px,
                y: new_y,
                w: PLAYER_WIDTH,
                h: 2,
            };
            let hit = self
                .state
                .blocks
                .iter()
                .enumerate()
                .find(|(_, block)| {
                    block.active
                        && (Rect {
                            x: block.x * TILE,
                            y: block.y * TILE,
                            w: TILE,
                            h: TILE,
                        })
                        .overlaps(head)
                })
                .map(|(i, _)| i);
            if let Some(index) = hit {
                self.handle_block_hit(index, emitted);
                let block_y = self.state.blocks[index].y * TILE;
                self.state.player.y = (block_y + TILE) * FP_ONE;
                self.state.player.vy = 0;
                return;
            }
        }
        let candidate = Rect {
            x: px,
            y: new_y,
            w: PLAYER_WIDTH,
            h: PLAYER_HEIGHT,
        };
        let new_bottom = new_y + PLAYER_HEIGHT;
        let solids = self.solid_rects();
        if vy >= 0 {
            if let Some(surface) = landing_surface(&solids, candidate, old_bottom, new_bottom) {
                let was_grounded = self.state.player.grounded;
                self.state.player.y = (surface - PLAYER_HEIGHT) * FP_ONE;
                self.state.player.vy = 0;
                self.state.player.grounded = true;
                if !was_grounded {
                    emitted.push(Event::Landed);
                }
                if let Some(platform) = self.state.platforms.iter().find(|platform| {
                    platform.x < candidate.x + candidate.w
                        && platform.x + 64 > candidate.x
                        && platform.y == surface
                }) {
                    emitted.push(Event::MovingPlatformLanded { id: platform.id });
                }
            } else {
                self.state.player.y += vy;
                self.state.player.grounded = false;
            }
        } else {
            self.state.player.y += vy;
            self.state.player.grounded = false;
        }
    }

    fn handle_block_hit(&mut self, index: usize, emitted: &mut Vec<Event>) {
        let block = &mut self.state.blocks[index];
        if !block.active || block.used {
            return;
        }
        if block.kind == BlockKind::Breakable
            && !matches!(
                self.state.player.power,
                PowerState::Big | PowerState::Fire | PowerState::Star
            )
        {
            emitted.push(Event::BlockHit {
                id: block.id,
                contents: None,
            });
            return;
        }
        if block.kind == BlockKind::Breakable {
            block.active = false;
            emitted.push(Event::BlockBroken { id: block.id });
            return;
        }
        if block.kind == BlockKind::Question {
            block.used = true;
            block.kind = BlockKind::Used;
            emitted.push(Event::BlockHit {
                id: block.id,
                contents: block.contents,
            });
            if let Some(kind) = block.contents {
                if kind == CollectibleKind::Coin {
                    self.state.player.coins = self.state.player.coins.saturating_add(1);
                    self.state.player.score = self.state.player.score.saturating_add(200);
                    emitted.push(Event::CoinCollected {
                        total: self.state.player.coins,
                    });
                } else {
                    let id = self.state.collectibles.len() as u16;
                    self.state.collectibles.push(CollectibleState {
                        id,
                        kind,
                        x: block.x * TILE * FP_ONE + 2 * FP_ONE,
                        y: (block.y * TILE - 12) * FP_ONE,
                        vx: 24,
                        vy: -420,
                        active: true,
                        from_block: true,
                    });
                    emitted.push(Event::CollectibleSpawned {
                        id,
                        collectible_kind: kind,
                    });
                }
            }
        } else {
            emitted.push(Event::BlockHit {
                id: block.id,
                contents: None,
            });
        }
    }

    fn update_progress(&mut self, emitted: &mut Vec<Event>) {
        let tile_x = self.state.player.x / FP_ONE / TILE;
        if tile_x > self.state.max_tile_x {
            self.state.max_tile_x = tile_x;
            let progress = self.progress_report().progress_milli;
            emitted.push(Event::Progress {
                tile_x,
                route_index: self.state.route_index,
                progress_milli: progress,
            });
        }
        let height = (-self.state.player.y / FP_ONE).max(0);
        self.state.max_height_px = self.state.max_height_px.max(height);
    }

    fn check_hazards(&mut self, emitted: &mut Vec<Event>) {
        let player = Rect {
            x: self.state.player.x / FP_ONE,
            y: self.state.player.y / FP_ONE,
            w: PLAYER_WIDTH,
            h: PLAYER_HEIGHT,
        };
        let bottom = player.y + player.h;
        if bottom > FRAME_HEIGHT as i32 + 24 {
            self.kill("fell", emitted);
            return;
        }
        let tile_x = (player.x + player.w / 2) / TILE;
        for hazard in &self.spec.hazards {
            if tile_x >= hazard.span.start && tile_x < hazard.span.end && bottom >= 13 * TILE {
                if hazard.kind == HazardKind::Lava {
                    self.kill("lava", emitted);
                }
                return;
            }
        }
    }

    fn collect_collectibles(&mut self, emitted: &mut Vec<Event>) -> i32 {
        let player = Rect {
            x: self.state.player.x / FP_ONE,
            y: self.state.player.y / FP_ONE,
            w: PLAYER_WIDTH,
            h: PLAYER_HEIGHT,
        };
        let mut reward = 0;
        let mut collected = Vec::new();
        for collectible in &mut self.state.collectibles {
            if collectible.active
                && player.overlaps(Rect {
                    x: collectible.x / FP_ONE,
                    y: collectible.y / FP_ONE,
                    w: 12,
                    h: 12,
                })
            {
                collectible.active = false;
                collected.push((collectible.id, collectible.kind));
            }
        }
        for (_, kind) in collected {
            match kind {
                CollectibleKind::Coin => {
                    self.state.player.coins = self.state.player.coins.saturating_add(1);
                    self.state.player.score = self.state.player.score.saturating_add(100);
                    emitted.push(Event::CoinCollected {
                        total: self.state.player.coins,
                    });
                    reward += 2;
                }
                CollectibleKind::Mushroom => {
                    let from = self.state.player.power;
                    self.state.player.power = PowerState::Big;
                    self.state.player.score = self.state.player.score.saturating_add(1_000);
                    emitted.push(Event::PowerChanged {
                        from,
                        to: PowerState::Big,
                    });
                    reward += 5;
                }
                CollectibleKind::Flower => {
                    let from = self.state.player.power;
                    self.state.player.power = PowerState::Fire;
                    self.state.player.score = self.state.player.score.saturating_add(2_000);
                    emitted.push(Event::PowerChanged {
                        from,
                        to: PowerState::Fire,
                    });
                    reward += 7;
                }
                CollectibleKind::Star => {
                    let from = self.state.player.power;
                    self.state.player.power = PowerState::Star;
                    self.state.player.invincibility_frames = 480;
                    self.state.player.score = self.state.player.score.saturating_add(2_500);
                    emitted.push(Event::PowerChanged {
                        from,
                        to: PowerState::Star,
                    });
                    reward += 8;
                }
            }
        }
        reward
    }

    fn resolve_enemy_collisions(&mut self, emitted: &mut Vec<Event>) -> i32 {
        let player = Rect {
            x: self.state.player.x / FP_ONE,
            y: self.state.player.y / FP_ONE,
            w: PLAYER_WIDTH,
            h: PLAYER_HEIGHT,
        };
        let previous_bottom = player.y + PLAYER_HEIGHT - self.state.player.vy / FP_ONE;
        let mut reward = 0;
        let mut stomped = Vec::new();
        let mut damage = false;
        for enemy in &self.state.enemies {
            if enemy.active && !enemy.defeated {
                let h = if matches!(enemy.kind, EnemyKind::Spike) {
                    16
                } else {
                    12
                };
                let rect = Rect {
                    x: enemy.x / FP_ONE,
                    y: enemy.y / FP_ONE,
                    w: 14,
                    h,
                };
                if player.overlaps(rect) {
                    if self.state.player.vy >= 0
                        && previous_bottom <= rect.y + 5
                        && enemy.kind != EnemyKind::Spike
                    {
                        stomped.push(enemy.id);
                    } else if self.state.player.invincibility_frames == 0 {
                        damage = true;
                        reward -= 5;
                    }
                }
            }
        }
        if damage {
            self.take_damage(emitted);
        }
        for id in stomped {
            if let Some(enemy) = self.state.enemies.iter_mut().find(|enemy| enemy.id == id) {
                enemy.defeated = true;
                enemy.active = false;
                self.state.player.vy = -520;
                self.state.player.score = self.state.player.score.saturating_add(100);
                emitted.push(Event::EnemyStomped {
                    id,
                    enemy_kind: enemy.kind,
                });
                reward += 4;
            }
        }
        reward
    }

    fn take_damage(&mut self, emitted: &mut Vec<Event>) {
        let from = self.state.player.power;
        match from {
            PowerState::Small => self.kill("enemy", emitted),
            PowerState::Big => {
                self.state.player.power = PowerState::Small;
                self.state.player.invincibility_frames = 120;
                emitted.push(Event::PowerChanged {
                    from,
                    to: PowerState::Small,
                });
                emitted.push(Event::DamageTaken {
                    power: PowerState::Small,
                });
            }
            PowerState::Fire => {
                self.state.player.power = PowerState::Big;
                self.state.player.invincibility_frames = 120;
                emitted.push(Event::PowerChanged {
                    from,
                    to: PowerState::Big,
                });
                emitted.push(Event::DamageTaken {
                    power: PowerState::Big,
                });
            }
            PowerState::Star => {
                self.state.player.invincibility_frames = 120;
                emitted.push(Event::DamageTaken {
                    power: PowerState::Star,
                });
            }
        }
    }

    fn try_pipe_transition(&mut self, input: Input, emitted: &mut Vec<Event>) {
        if !input.down || !self.state.player.grounded {
            return;
        }
        let player_x = self.state.player.x / FP_ONE;
        let player_y = self.state.player.y / FP_ONE + PLAYER_HEIGHT;
        if let Some(pipe) = self.spec.pipes.iter().find(|pipe| {
            (player_x + PLAYER_WIDTH / 2 - pipe.x * TILE).abs() <= TILE / 2
                && player_y >= pipe.y * TILE - 3
        }) {
            self.state.player.x = pipe.destination_x * TILE * FP_ONE;
            self.state.player.y = (pipe.destination_y * TILE - PLAYER_HEIGHT) * FP_ONE;
            self.state.player.vx = 0;
            self.state.player.vy = 0;
            emitted.push(Event::PipeEntered {
                route_label: pipe.route_label.clone(),
            });
            emitted.push(Event::Transitioned {
                x_tile: pipe.destination_x,
            });
        }
    }

    fn update_route(&mut self, emitted: &mut Vec<Event>) {
        let x = self.state.player.x / FP_ONE / TILE;
        while self.state.route_index + 1 < self.spec.route.len() {
            let next = &self.spec.route[self.state.route_index + 1];
            if x < next.x || self.state.player.coins < next.required_coins {
                break;
            }
            self.state.route_index += 1;
            self.state.visited_routes.push(next.label.clone());
            emitted.push(Event::RouteCheckpoint {
                index: self.state.route_index,
                label: next.label.clone(),
            });
        }
    }

    fn check_goal(&mut self, emitted: &mut Vec<Event>, reward: &mut i32) {
        if self.state.player.x / FP_ONE / TILE >= self.spec.goal_x {
            self.state.terminal = true;
            self.state.terminal_reason = Some(TerminalReason::Completed);
            self.state.player.score = self
                .state
                .player
                .score
                .saturating_add(self.state.timer_frames);
            emitted.push(Event::LevelCompleted {
                score: self.state.player.score,
                coins: self.state.player.coins,
            });
            *reward += 100;
        }
    }

    fn kill(&mut self, cause: &str, emitted: &mut Vec<Event>) {
        if self.state.terminal {
            return;
        }
        self.state.player.lives = self.state.player.lives.saturating_sub(1);
        self.state.terminal = true;
        self.state.terminal_reason = Some(TerminalReason::Death);
        emitted.push(Event::Died {
            cause: cause.to_string(),
            lives_remaining: self.state.player.lives,
        });
    }

    fn solid_rects(&self) -> Vec<Rect> {
        let mut rects = Vec::new();
        for span in &self.spec.floor_spans {
            rects.push(Rect {
                x: span.start * TILE,
                y: 13 * TILE,
                w: (span.end - span.start) * TILE,
                h: 48,
            });
        }
        for block in &self.state.blocks {
            if block.active {
                rects.push(Rect {
                    x: block.x * TILE,
                    y: block.y * TILE,
                    w: TILE,
                    h: TILE,
                });
            }
        }
        for pipe in &self.spec.pipes {
            rects.push(Rect {
                x: pipe.x * TILE,
                y: pipe.y * TILE,
                w: TILE,
                h: (13 - pipe.y) * TILE,
            });
        }
        for (state, spec) in self
            .state
            .platforms
            .iter()
            .zip(self.spec.moving_platforms.iter())
        {
            rects.push(Rect {
                x: state.x,
                y: state.y,
                w: spec.width,
                h: 8,
            });
        }
        rects
    }

    /// Asset-free RGB observation using geometric primitives and original colors.
    pub fn render_rgb(&self) -> Vec<u8> {
        let mut rgb = vec![0; FRAME_WIDTH * FRAME_HEIGHT * 3];
        let background = match self.spec.theme {
            Theme::Meadow => [105, 180, 231],
            Theme::Cavern => [20, 25, 45],
            Theme::Water => [35, 116, 170],
            Theme::Sky => [178, 218, 247],
            Theme::Castle => [42, 34, 48],
        };
        for px in rgb.chunks_exact_mut(3) {
            px.copy_from_slice(&background);
        }
        let camera_x = (self.state.player.x / FP_ONE - 96).max(0);
        let camera_y = if self.spec.theme == Theme::Sky {
            (-self.state.max_height_px + 40).clamp(-80, 80)
        } else {
            0
        };
        let terrain_color = match self.spec.theme {
            Theme::Meadow => [74, 157, 76],
            Theme::Cavern => [107, 88, 112],
            Theme::Water => [67, 145, 178],
            Theme::Sky => [194, 171, 93],
            Theme::Castle => [131, 75, 74],
        };
        for span in &self.spec.floor_spans {
            draw_rect(
                &mut rgb,
                span.start * TILE - camera_x,
                13 * TILE - camera_y,
                (span.end - span.start) * TILE,
                48,
                terrain_color,
            );
        }
        for hazard in &self.spec.hazards {
            let color = match hazard.kind {
                HazardKind::Pit => [22, 31, 55],
                HazardKind::Lava => [228, 76, 32],
                HazardKind::Water => [35, 177, 214],
            };
            draw_rect(
                &mut rgb,
                hazard.span.start * TILE - camera_x,
                13 * TILE - camera_y,
                (hazard.span.end - hazard.span.start) * TILE,
                32,
                color,
            );
        }
        for block in &self.state.blocks {
            if !block.active {
                continue;
            }
            let color = match block.kind {
                BlockKind::Question => [235, 167, 54],
                BlockKind::Breakable => [181, 111, 56],
                BlockKind::Solid | BlockKind::Used => [124, 113, 104],
            };
            draw_rect(
                &mut rgb,
                block.x * TILE - camera_x,
                block.y * TILE - camera_y,
                TILE - 1,
                TILE - 1,
                color,
            );
            if block.kind == BlockKind::Question {
                draw_rect(
                    &mut rgb,
                    block.x * TILE + 5 - camera_x,
                    block.y * TILE + 4 - camera_y,
                    5,
                    8,
                    [255, 241, 166],
                );
            }
        }
        for pipe in &self.spec.pipes {
            draw_rect(
                &mut rgb,
                pipe.x * TILE - camera_x,
                pipe.y * TILE - camera_y,
                TILE,
                (13 - pipe.y) * TILE,
                [46, 161, 91],
            );
            draw_rect(
                &mut rgb,
                pipe.x * TILE - 2 - camera_x,
                pipe.y * TILE - camera_y,
                TILE + 4,
                4,
                [72, 202, 111],
            );
        }
        for (state, spec) in self
            .state
            .platforms
            .iter()
            .zip(self.spec.moving_platforms.iter())
        {
            draw_rect(
                &mut rgb,
                state.x - camera_x,
                state.y - camera_y,
                spec.width,
                8,
                [235, 212, 100],
            );
        }
        for collectible in &self.state.collectibles {
            if !collectible.active {
                continue;
            }
            let color = match collectible.kind {
                CollectibleKind::Coin => [255, 226, 73],
                CollectibleKind::Mushroom => [221, 63, 68],
                CollectibleKind::Flower => [245, 105, 190],
                CollectibleKind::Star => [255, 244, 107],
            };
            draw_rect(
                &mut rgb,
                collectible.x / FP_ONE - camera_x,
                collectible.y / FP_ONE - camera_y,
                10,
                10,
                color,
            );
        }
        for enemy in &self.state.enemies {
            if !enemy.active || enemy.defeated {
                continue;
            }
            let color = match enemy.kind {
                EnemyKind::Walker => [157, 89, 49],
                EnemyKind::Shell => [50, 139, 75],
                EnemyKind::Flyer => [174, 77, 145],
                EnemyKind::Fish => [242, 94, 95],
                EnemyKind::Spike => [218, 218, 228],
            };
            draw_rect(
                &mut rgb,
                enemy.x / FP_ONE - camera_x,
                enemy.y / FP_ONE - camera_y,
                14,
                if enemy.kind == EnemyKind::Spike {
                    16
                } else {
                    12
                },
                color,
            );
        }
        let player_color = match self.state.player.power {
            PowerState::Small => [247, 94, 72],
            PowerState::Big => [248, 158, 71],
            PowerState::Fire => [248, 241, 193],
            PowerState::Star => [247, 244, 92],
        };
        draw_rect(
            &mut rgb,
            self.state.player.x / FP_ONE - camera_x,
            self.state.player.y / FP_ONE - camera_y,
            PLAYER_WIDTH,
            PLAYER_HEIGHT,
            player_color,
        );
        draw_rect(
            &mut rgb,
            self.state.player.x / FP_ONE + if self.state.player.facing > 0 { 8 } else { 2 }
                - camera_x,
            self.state.player.y / FP_ONE + 4 - camera_y,
            2,
            2,
            [24, 35, 55],
        );
        draw_rect(
            &mut rgb,
            self.spec.goal_x * TILE - camera_x,
            7 * TILE - camera_y,
            4,
            6 * TILE,
            [236, 236, 220],
        );
        rgb
    }
}

fn landing_surface(
    solids: &[Rect],
    candidate: Rect,
    old_bottom: i32,
    new_bottom: i32,
) -> Option<i32> {
    solids
        .iter()
        .filter(|solid| {
            candidate.horizontal_overlap(**solid) && old_bottom <= solid.y && new_bottom >= solid.y
        })
        .map(|solid| solid.y)
        .min()
}

fn draw_rect(rgb: &mut [u8], x: i32, y: i32, width: i32, height: i32, color: [u8; 3]) {
    for py in y.max(0)..(y + height).min(FRAME_HEIGHT as i32) {
        for px in x.max(0)..(x + width).min(FRAME_WIDTH as i32) {
            put(rgb, px, py, color);
        }
    }
}

fn put(rgb: &mut [u8], x: i32, y: i32, color: [u8; 3]) {
    if x < 0 || y < 0 || x >= FRAME_WIDTH as i32 || y >= FRAME_HEIGHT as i32 {
        return;
    }
    let i = (y as usize * FRAME_WIDTH + x as usize) * 3;
    rgb[i..i + 3].copy_from_slice(&color);
}

fn event_name(event: &Event) -> &'static str {
    match event {
        Event::EpisodeStarted { .. } => "episode_started",
        Event::Jumped => "jumped",
        Event::Landed => "landed",
        Event::Progress { .. } => "progress",
        Event::RouteCheckpoint { .. } => "route_checkpoint",
        Event::EntitySpawned { .. } => "entity_spawned",
        Event::BlockHit { .. } => "block_hit",
        Event::BlockBroken { .. } => "block_broken",
        Event::CollectibleSpawned { .. } => "collectible_spawned",
        Event::CoinCollected { .. } => "coin_collected",
        Event::PowerChanged { .. } => "power_changed",
        Event::EnemyStomped { .. } => "enemy_stomped",
        Event::DamageTaken { .. } => "damage_taken",
        Event::PipeEntered { .. } => "pipe_entered",
        Event::Transitioned { .. } => "transitioned",
        Event::MovingPlatformLanded { .. } => "moving_platform_landed",
        Event::TimedOut => "timed_out",
        Event::Died { .. } => "died",
        Event::LevelCompleted { .. } => "level_completed",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catalog_has_32_independent_authored_specs() {
        let specs = all_level_specs();
        assert_eq!(specs.len(), 32);
        let fingerprints: std::collections::HashSet<_> =
            specs.iter().map(LevelSpec::fingerprint).collect();
        assert_eq!(fingerprints.len(), 32);
        let contents: std::collections::HashSet<_> = specs
            .iter()
            .flat_map(|spec| spec.blocks.iter().filter_map(|block| block.contents))
            .collect();
        assert_eq!(contents.len(), 4);
        for (i, spec) in specs.iter().enumerate() {
            assert_eq!(spec.id, ODYSSEUS_LEVELS[i]);
            assert!(spec.width_tiles >= 116);
            assert!(spec
                .capability_tags
                .iter()
                .any(|tag| tag.starts_with("authoring_variant_")));
            assert!(!spec.blocks.is_empty());
            assert!(!spec.enemies.is_empty());
        }
    }

    #[test]
    fn action_space_is_closed_and_parseable() {
        for action in ACTION_SPACE {
            assert_eq!(Action::parse(action).unwrap().as_str(), action);
        }
        assert!(Action::parse("teleport").is_none());
    }

    #[test]
    fn replay_checkpoint_render_and_events_are_deterministic() {
        let mut a = Env::reset(LevelId::new(3, 3), 7).unwrap();
        a.drain_events();
        let tape = [
            Action::RightRun,
            Action::RightRun,
            Action::RightJump,
            Action::Neutral,
            Action::Left,
        ];
        for i in 0..70 {
            a.step_action(tape[i % tape.len()]);
        }
        let snap = a.snapshot();
        let bytes = a.checkpoint_bytes().unwrap();
        let mut b = Env::restore(snap.clone()).unwrap();
        let mut c = Env::from_checkpoint_bytes(&bytes).unwrap();
        for i in 0..90 {
            let action = tape[(i + 2) % tape.len()];
            a.step_action(action);
            b.step_action(action);
            c.step_action(action);
        }
        assert_eq!(a.snapshot(), b.snapshot());
        assert_eq!(a.snapshot(), c.snapshot());
        assert_eq!(a.render_rgb(), b.render_rgb());
        assert!(bytes.len() < 32_000);
    }

    #[test]
    fn every_level_runs_without_panics_and_renders_rgb() {
        for id in ODYSSEUS_LEVELS {
            let mut env = Env::reset(id, 1234).unwrap();
            for frame in 0..180 {
                env.step_action(if frame % 41 == 0 {
                    Action::RightJumpRun
                } else {
                    Action::RightRun
                });
                if env.state.terminal {
                    break;
                }
            }
            assert_eq!(env.render_rgb().len(), FRAME_WIDTH * FRAME_HEIGHT * 3);
            assert!(env.readout().progress.progress_milli <= 1000);
        }
    }

    #[test]
    fn block_hit_stomp_and_power_damage_are_semantic() {
        let mut env = Env::reset(LevelId::new(1, 1), 1).unwrap();
        env.drain_events();
        let block_index = env
            .state
            .blocks
            .iter()
            .position(|b| b.kind == BlockKind::Question)
            .unwrap();
        let block = env.state.blocks[block_index].clone();
        env.state.player.x = block.x * TILE * FP_ONE;
        env.state.player.y = (block.y * TILE + TILE + 1) * FP_ONE;
        env.state.player.vy = -1024;
        env.move_player_vertical(env.state.player.y / FP_ONE + PLAYER_HEIGHT, &mut Vec::new());
        assert!(env.state.blocks[block_index].used);
        assert!(env.events.is_empty());

        let enemy = env.state.enemies[0].clone();
        env.state.enemies[0].active = true;
        env.state.enemies[0].x = env.state.player.x;
        env.state.enemies[0].y = env.state.player.y + (PLAYER_HEIGHT - 4) * FP_ONE;
        env.state.player.vy = 100;
        let mut events = Vec::new();
        let reward = env.resolve_enemy_collisions(&mut events);
        assert!(reward >= 0);
        assert!(
            events
                .iter()
                .any(|e| matches!(e, Event::EnemyStomped { .. }))
                || enemy.kind == EnemyKind::Spike
        );
    }
}
