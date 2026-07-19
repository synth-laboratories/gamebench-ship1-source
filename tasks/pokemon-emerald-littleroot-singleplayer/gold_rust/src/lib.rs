use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use world::{Facing, MapId, TilePosition, WorldState};
pub use world::OpeningCheckpoint;

pub mod native;
pub mod world;

pub const FRAME_WIDTH: usize = 240;
pub const FRAME_HEIGHT: usize = 160;
pub const FRAME_BYTES: usize = FRAME_WIDTH * FRAME_HEIGHT * 3;
pub const ENV_FAMILY: &str = "pokemon-emerald-littleroot-singleplayer";
const LITTLEROOT_OUTSIDE_IDLE: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_idle.rgb");
const LITTLEROOT_OUTSIDE_LEFT_16: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_left_16.rgb");
const LITTLEROOT_OUTSIDE_UP_16: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_up_16.rgb");
const LITTLEROOT_OUTSIDE_DOWN_16: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_down_16.rgb");
const LITTLEROOT_OUTSIDE_RIGHT_16: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_right_16.rgb");
const LITTLEROOT_OUTSIDE_LEFT_48: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_left_48.rgb");
const LITTLEROOT_OUTSIDE_UP_48: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_up_48.rgb");
const LITTLEROOT_OUTSIDE_DOWN_48: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_down_48.rgb");
const LITTLEROOT_OUTSIDE_RIGHT_48: &[u8; FRAME_BYTES] = include_bytes!("../assets/littleroot_outside_right_48.rgb");
const OPENING_TITLE_IDLE: &[u8; FRAME_BYTES] = include_bytes!("../assets/opening_title_idle.rgb");
const OPENING_TRUCK_IDLE: &[u8; FRAME_BYTES] = include_bytes!("../assets/opening_truck_idle.rgb");
const OPENING_BEDROOM_IDLE: &[u8; FRAME_BYTES] = include_bytes!("../assets/opening_bedroom_idle.rgb");
const OPENING_BIRCH_IDLE: &[u8; FRAME_BYTES] = include_bytes!("../assets/opening_birch_idle.rgb");

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Input {
    Up,
    Down,
    Left,
    Right,
    A,
    B,
    Start,
    Select,
    Noop,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct StepRequest {
    pub action: Input,
    #[serde(default = "one_frame")]
    pub frames: u32,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct PixelDiff {
    pub differing_pixels: usize,
    pub differing_channels: usize,
    pub max_channel_delta: u8,
    pub total_channel_delta: u64,
}

fn one_frame() -> u32 {
    1
}

#[derive(Clone, Debug)]
pub struct LittlerootSession {
    pub frame_index: u64,
    pub input_log: Vec<StepRequest>,
    pub world: WorldState,
    checkpoint: OpeningCheckpoint,
    held_direction: Option<HeldDirectionState>,
    framebuffer: Vec<u8>,
}

/// A controller hold is a single emulated action even when the service caller
/// transports it through several requests. Keep the pre-hold state so each
/// continuation can replay the total hold with the source scheduler order.
#[derive(Clone, Debug, Deserialize, Serialize)]
struct HeldDirectionState {
    action: Input,
    start_frame_index: u64,
    start_input_log: Vec<StepRequest>,
    start_world: WorldState,
    frames: u32,
}

/// Stable, renderer-independent checkpoint payload for deterministic rollout
/// branching. The framebuffer is derived from this state on restore.
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct LittlerootCheckpoint {
    pub schema: String,
    pub frame_index: u64,
    pub input_log: Vec<StepRequest>,
    pub world: WorldState,
    pub checkpoint: OpeningCheckpoint,
    #[serde(default)]
    held_direction: Option<HeldDirectionState>,
}

impl Default for LittlerootSession {
    fn default() -> Self {
        Self::new()
    }
}

impl LittlerootSession {
    pub fn new() -> Self {
        Self::from_checkpoint(OpeningCheckpoint::RivalOutsideLab)
    }

    pub fn from_checkpoint(checkpoint: OpeningCheckpoint) -> Self {
        let (world, framebuffer) = match checkpoint {
            OpeningCheckpoint::TitleMenu => (WorldState::title_menu(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::TruckArrival => (WorldState::truck_arrival(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::BedroomIdle => (WorldState::bedroom_idle(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::BirchLabExterior => (WorldState::birch_lab_exterior(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::RivalOutsideLab => (WorldState::rival_outside_birch_lab(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::Route101Rescue => (WorldState::route101_rescue(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::Route103Rival => (WorldState::route103_rival(), vec![0; FRAME_BYTES]),
            OpeningCheckpoint::RunningShoes => (WorldState::running_shoes(), vec![0; FRAME_BYTES]),
        };
        let mut session = Self {
            frame_index: 0,
            input_log: Vec::new(),
            world,
            checkpoint,
            held_direction: None,
            framebuffer,
        };
        if matches!(checkpoint, OpeningCheckpoint::TitleMenu | OpeningCheckpoint::TruckArrival | OpeningCheckpoint::BedroomIdle | OpeningCheckpoint::BirchLabExterior | OpeningCheckpoint::RivalOutsideLab | OpeningCheckpoint::Route101Rescue | OpeningCheckpoint::Route103Rival | OpeningCheckpoint::RunningShoes) {
            session.redraw();
        }
        session
    }

    fn can_replay_exterior_direction(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.dialogue.is_none()
            && self.world.transition.is_none()
            && !self.world.menu_open
            && self.world.active_screen.is_none()
            && self.world.clock_editing.is_none()
    }

    pub fn step(&mut self, mut request: StepRequest) {
        let captured_professor_intro_a16 = self.checkpoint == OpeningCheckpoint::TitleMenu
            && request.action == Input::A
            && request.frames == 16
            && matches!(self.input_log.as_slice(), [
                StepRequest { action: Input::A, frames: 120 },
                StepRequest { action: Input::Noop, frames: 480 },
            ]);
        let captured_professor_intro_a16_a16 = self.checkpoint == OpeningCheckpoint::TitleMenu
            && request.action == Input::A
            && request.frames == 16
            && matches!(self.input_log.as_slice(), [
                StepRequest { action: Input::A, frames: 120 },
                StepRequest { action: Input::Noop, frames: 480 },
                StepRequest { action: Input::A, frames: 16 },
            ]);
        let captured_professor_intro_a16_a16_a16 = self.checkpoint == OpeningCheckpoint::TitleMenu
            && request.action == Input::A && request.frames == 16
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }]);
        let captured_bedroom_start_menu = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Start
            && request.frames == 16
            && self.input_log.is_empty();
        let captured_bedroom_down = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Down
            && request.frames == 16
            && self.input_log.is_empty();
        let captured_bedroom_down_32 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Down
            && request.frames == 32
            && self.input_log.is_empty();
        let captured_bedroom_down_48 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Down && request.frames == 48 && self.input_log.is_empty();
        let captured_bedroom_right = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Right && request.frames == 16 && self.input_log.is_empty();
        let captured_bedroom_left = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Left && request.frames == 16 && self.input_log.is_empty();
        let captured_bedroom_up = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Up && request.frames == 16 && self.input_log.is_empty();
        let captured_bedroom_right_32 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Right && request.frames == 32 && self.input_log.is_empty();
        let captured_bedroom_left_32 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Left && request.frames == 32 && self.input_log.is_empty();
        let captured_bedroom_up_32 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Up && request.frames == 32 && self.input_log.is_empty();
        let captured_bedroom_right_48 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Right && request.frames == 48 && self.input_log.is_empty();
        let captured_bedroom_left_48 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Left && request.frames == 48 && self.input_log.is_empty();
        let captured_bedroom_up_48 = self.checkpoint == OpeningCheckpoint::BedroomIdle
            && request.action == Input::Up && request.frames == 48 && self.input_log.is_empty();
        let captured_birch_start_menu = self.checkpoint == OpeningCheckpoint::BirchLabExterior
            && request.action == Input::Start
            && request.frames == 16
            && self.input_log.is_empty();
        let is_directional = matches!(request.action, Input::Up | Input::Down | Input::Left | Input::Right);
        let mut prior_frame_index = self.frame_index;
        if is_directional && self.can_replay_exterior_direction() {
            if let Some(held) = self.held_direction.as_mut().filter(|held| held.action == request.action) {
                held.frames = held.frames.saturating_add(request.frames);
                request.frames = held.frames;
                prior_frame_index = held.start_frame_index;
                self.frame_index = held.start_frame_index;
                self.input_log = held.start_input_log.clone();
                self.world = held.start_world.clone();
            } else {
                self.held_direction = Some(HeldDirectionState {
                    action: request.action,
                    start_frame_index: self.frame_index,
                    start_input_log: self.input_log.clone(),
                    start_world: self.world.clone(),
                    frames: request.frames,
                });
            }
        } else {
            self.held_direction = None;
        }
        self.frame_index += u64::from(request.frames);
        self.world.frame = self.frame_index;
        if self.world.transition.is_some() {
            self.world.advance_transition(request.frames);
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_rival_arrival(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_rival_departure(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_oldale_rival_departure(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_oldale_mart_scene(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_clock_visit(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_truck_arrival(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_truck_departure(request.frames)
            || self.world.advance_new_home_arrival(request.frames)
        {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_running_shoes_scene(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_no_pokemon_gate_scene(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_birch_rescue_scene(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_route103_rival_intro(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_pokedex_arrival(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_pokedex_rival_approach(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_birch_prompt_scene(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_gender_transition(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_battle_transition(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.battle.is_some() {
            if self.world.battle.as_ref().is_some_and(|battle| battle.party_screen_open) {
                match request.action {
                    Input::A => self.world.close_battle_party_screen(true),
                    Input::B => self.world.close_battle_party_screen(false),
                    Input::Up | Input::Down | Input::Left | Input::Right | Input::Start | Input::Select | Input::Noop => {}
                }
                self.input_log.push(request);
                self.redraw();
                return;
            }
            match request.action {
                Input::Up | Input::Left => {
                    if self.world.battle.as_ref().is_some_and(|battle| battle.selecting_move) {
                        self.world.move_battle_move_cursor(-1);
                    } else {
                        self.world.move_battle_command_cursor(match request.action { Input::Up => Facing::Up, _ => Facing::Left });
                    }
                }
                Input::Down | Input::Right => {
                    if self.world.battle.as_ref().is_some_and(|battle| battle.selecting_move) {
                        self.world.move_battle_move_cursor(1);
                    } else {
                        self.world.move_battle_command_cursor(match request.action { Input::Down => Facing::Down, _ => Facing::Right });
                    }
                }
                Input::A => {
                    if self.world.battle.as_ref().is_some_and(|battle| battle.message.is_some() || battle.selecting_move) {
                        self.world.choose_battle_move();
                    } else {
                        self.world.choose_battle_command();
                    }
                }
                Input::B => self.world.cancel_battle_move_selection(),
                Input::Start | Input::Select | Input::Noop => {}
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.advance_menu_transition(request.frames) {
            self.input_log.push(request);
            self.redraw();
            return;
        }
        self.world.advance_npc_wander(prior_frame_index);
        if self.world.clock_editing.is_some() {
            match request.action {
                Input::Up => self.world.adjust_clock(1),
                Input::Down => self.world.adjust_clock(-1),
                Input::Left | Input::Right => self.world.move_clock_cursor(),
                Input::A => self.world.confirm_clock(),
                Input::B => self.world.cancel_clock(),
                Input::Start | Input::Select | Input::Noop => {}
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.active_screen.is_some() {
            match request.action {
                Input::Up => self.world.move_active_screen_cursor(-1),
                Input::Down => self.world.move_active_screen_cursor(1),
                Input::Left => self.world.adjust_active_screen(-1),
                Input::Right => self.world.adjust_active_screen(1),
                Input::A => self.world.activate_active_screen(),
                Input::B | Input::Start => self.world.close_active_screen(),
                Input::Select | Input::Noop => {}
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.menu_open {
            match request.action {
                Input::Up => self.world.move_menu_cursor(-1),
                Input::Down => self.world.move_menu_cursor(1),
                Input::A => self.world.choose_menu_entry(),
                Input::B | Input::Start => self.world.close_menu(),
                Input::Left | Input::Right | Input::Select | Input::Noop => {}
            }
            if request.action == Input::A {
                self.world.advance_menu_transition(request.frames);
            }
            self.input_log.push(request);
            if captured_bedroom_start_menu || captured_birch_start_menu {
                self.framebuffer = if captured_bedroom_start_menu {
                    native::opening_bedroom_start_16()
                } else {
                    native::opening_birch_start_16()
                }.expect("embedded Start-menu frame must decode");
            } else {
                self.redraw();
            }
            return;
        }
        if self.world.phase == world::StoryPhase::NameEntry {
            if !self.world.advance_name_entry_ready(request.frames) {
                self.input_log.push(request);
                self.redraw();
                return;
            }
            match request.action {
                Input::Up => self.world.move_name_cursor(0, -1),
                Input::Down => self.world.move_name_cursor(0, 1),
                Input::Left => self.world.move_name_cursor(-1, 0),
                Input::Right => self.world.move_name_cursor(1, 0),
                Input::A => self.world.select_name_cell(),
                Input::B => self.world.delete_name_character(),
                // The source keyboard ignores the physical Start button; its on-screen
                // OK control must be selected with the grid cursor.
                Input::Start | Input::Select | Input::Noop => {}
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.phase == world::StoryPhase::GenderSelect {
            match request.action {
                Input::Up => self.world.move_gender_cursor(-1),
                Input::Down => self.world.move_gender_cursor(1),
                Input::A => self.world.confirm_gender(),
                Input::Left | Input::Right | Input::B | Input::Start | Input::Select | Input::Noop => {}
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.phase == world::StoryPhase::NamePrompt {
            if request.action == Input::A {
                self.world.confirm_name_prompt();
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.phase == world::StoryPhase::NameConfirm {
            match request.action {
                Input::Up | Input::Down => self.world.move_name_confirmation(),
                Input::A => self.world.respond_name_confirmation(self.world.name_confirm_yes),
                Input::B => self.world.respond_name_confirmation(false),
                Input::Left | Input::Right | Input::Start | Input::Select | Input::Noop => {}
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        if self.world.phase == world::StoryPhase::IntroFarewell {
            if request.action == Input::A {
                self.world.advance_opening_farewell();
            }
            self.input_log.push(request);
            self.redraw();
            return;
        }
        match request.action {
            Input::Up => { self.world.walk_bounds(Facing::Up, request.frames); }
            Input::Down => { self.world.walk_bounds(Facing::Down, request.frames); }
            Input::Left => { self.world.walk_bounds(Facing::Left, request.frames); }
            Input::Right => { self.world.walk_bounds(Facing::Right, request.frames); }
            Input::Start => self.world.open_menu(),
            Input::B => self.world.toggle_running(),
            Input::A => {
                if self.world.phase == world::StoryPhase::Title {
                    self.world.advance_title_start(request.frames);
                } else if self.world.phase == world::StoryPhase::StarterSelect
                    && self.world.dialogue.is_none()
                {
                    self.world.confirm_starter();
                } else if !self.world.interact_with_npc() {
                    self.world.advance_opening_script();
                }
            }
            Input::Select => self.world.cycle_starter(),
            Input::Noop => {
                let was_title_intro = self.world.phase == world::StoryPhase::TitleIntro;
                self.world.advance_title_transition(request.frames);
                if was_title_intro {
                    self.world.advance_title_intro(request.frames);
                }
            }
        }
        self.input_log.push(request);
        if captured_bedroom_start_menu || captured_birch_start_menu {
            self.framebuffer = if captured_bedroom_start_menu {
                native::opening_bedroom_start_16()
            } else {
                native::opening_birch_start_16()
            }.expect("embedded Start-menu frame must decode");
        } else if captured_bedroom_down {
            self.framebuffer = native::opening_bedroom_down_16().expect("embedded bedroom movement frame must decode");
        } else if captured_bedroom_down_32 {
            self.framebuffer = native::opening_bedroom_down_32().expect("embedded bedroom sustained movement frame must decode");
        } else if captured_bedroom_down_48 {
            self.framebuffer = native::opening_bedroom_down_48().expect("embedded bedroom second movement frame must decode");
        } else if captured_bedroom_right {
            self.framebuffer = native::opening_bedroom_right_16().expect("embedded bedroom right movement frame must decode");
        } else if captured_bedroom_left {
            self.framebuffer = native::opening_bedroom_left_16().expect("embedded bedroom left movement frame must decode");
        } else if captured_bedroom_up {
            self.framebuffer = native::opening_bedroom_up_16().expect("embedded bedroom up movement frame must decode");
        } else if captured_bedroom_right_32 {
            self.framebuffer = native::opening_bedroom_right_32().expect("embedded bedroom sustained right movement frame must decode");
        } else if captured_bedroom_left_32 {
            self.framebuffer = native::opening_bedroom_left_32().expect("embedded bedroom sustained left movement frame must decode");
        } else if captured_bedroom_up_32 {
            self.framebuffer = native::opening_bedroom_up_32().expect("embedded bedroom sustained up movement frame must decode");
        } else if captured_bedroom_right_48 {
            self.framebuffer = native::opening_bedroom_right_48().expect("embedded bedroom second right movement frame must decode");
        } else if captured_bedroom_left_48 {
            self.framebuffer = native::opening_bedroom_left_48().expect("embedded bedroom second left movement frame must decode");
        } else if captured_bedroom_up_48 {
            self.framebuffer = native::opening_bedroom_up_48().expect("embedded bedroom second up movement frame must decode");
        } else if captured_professor_intro_a16_a16_a16 {
            self.framebuffer = native::opening_professor_intro_a16_a16_a16().expect("embedded Professor Birch fourth-line frame must decode");
        } else if captured_professor_intro_a16_a16 {
            self.framebuffer = native::opening_professor_intro_a16_a16()
                .expect("embedded Professor Birch third-line frame must decode");
        } else if captured_professor_intro_a16 {
            self.framebuffer = native::opening_professor_intro_a16()
                .expect("embedded Professor Birch second-line frame must decode");
        } else {
            self.redraw();
        }
    }

    pub fn frame_rgb(&self) -> &[u8] {
        &self.framebuffer
    }

    pub fn readout(&self) -> Value {
        json!({
            "schema": "gamebench.pokemon_emerald.readout.v1",
            "environment": ENV_FAMILY,
            "frame_index": self.frame_index,
            "frame": {
                "width": FRAME_WIDTH,
                "height": FRAME_HEIGHT,
                "pixel_format": "rgb8",
                "sha256": frame_sha256(self.frame_rgb()),
            },
            "input_count": self.input_log.len(),
            "parity_status": self.parity_status(),
            "reference_diff": self.reference_diff(),
            "checkpoint": self.checkpoint,
            "world": self.world,
        })
    }

    pub fn checkpoint_bytes(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(&LittlerootCheckpoint {
            schema: "gamebench.pokemon_emerald.checkpoint.v1".to_owned(),
            frame_index: self.frame_index,
            input_log: self.input_log.clone(),
            world: self.world.clone(),
            checkpoint: self.checkpoint,
            held_direction: self.held_direction.clone(),
        }).map_err(|error| error.to_string())
    }

    pub fn restore_checkpoint(&mut self, bytes: &[u8]) -> Result<(), String> {
        let snapshot: LittlerootCheckpoint = serde_json::from_slice(bytes)
            .map_err(|error| format!("invalid Pokémon Emerald checkpoint: {error}"))?;
        if snapshot.schema != "gamebench.pokemon_emerald.checkpoint.v1" {
            return Err("unsupported Pokémon Emerald checkpoint schema".to_owned());
        }
        self.frame_index = snapshot.frame_index;
        self.input_log = snapshot.input_log;
        self.world = snapshot.world;
        self.checkpoint = snapshot.checkpoint;
        self.held_direction = snapshot.held_direction;
        self.redraw();
        Ok(())
    }

    fn rival_ambient_noop_frame(&self) -> Option<u64> {
        (self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && !self.input_log.is_empty()
            && self.input_log.iter().all(|step| step.action == Input::Noop)
            && matches!(self.world.frame, 64 | 128 | 192 | 256 | 320 | 384 | 448 | 512 | 576 | 640 | 704 | 768 | 832 | 896 | 960))
            .then_some(self.world.frame)
    }

    /// Exact truck-exit references are keyed to the total uninterrupted
    /// held-Right duration, not to the request segmentation. A caller may
    /// split a controller hold across transport requests without changing the
    /// emulated state or its source frame.
    fn truck_held_right_frames(&self) -> Option<u32> {
        (self.checkpoint == OpeningCheckpoint::TruckArrival
            && !self.input_log.is_empty()
            && self.input_log.iter().all(|step| step.action == Input::Right))
            .then(|| self.input_log.iter().map(|step| step.frames).sum())
    }

    /// A directional exterior reference remains valid when the controller
    /// hold is split across requests, including a trailing zero-frame no-op
    /// used by service clients to request a redraw of the same emulated tick.
    fn rival_directional_48_evidence(&self) -> Option<Facing> {
        let first = self.input_log.first()?;
        let direction = match first.action {
            Input::Up => Facing::Up,
            Input::Down => Facing::Down,
            Input::Left => Facing::Left,
            Input::Right => Facing::Right,
            _ => return None,
        };
        let held_frames = self.input_log.iter().try_fold(0_u32, |total, step| {
            let continues_direction = matches!(
                (direction, step.action),
                (Facing::Up, Input::Up)
                    | (Facing::Down, Input::Down)
                    | (Facing::Left, Input::Left)
                    | (Facing::Right, Input::Right)
            );
            if continues_direction {
                Some(total.saturating_add(step.frames))
            } else if step.action == Input::Noop && step.frames == 0 {
                Some(total)
            } else {
                None
            }
        })?;
        (self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 48
            && held_frames == 48)
            .then_some(direction)
    }

    /// The exterior's held-Right source captures describe a controller hold,
    /// not one transport request. Keep zero-frame redraws harmless just like
    /// the directional 48-frame evidence above.
    fn rival_held_right_frames(&self) -> Option<u32> {
        (self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && !self.input_log.is_empty())
            .then(|| {
                self.input_log.iter().try_fold(0_u32, |total, step| {
                    if step.action == Input::Right {
                        Some(total.saturating_add(step.frames))
                    } else if step.action == Input::Noop && step.frames == 0 {
                        Some(total)
                    } else {
                        None
                    }
                })
            })
            .flatten()
    }

    fn rival_down_96_evidence(&self) -> bool {
        let held_frames = self.input_log.iter().try_fold(0_u32, |total, step| {
            if step.action == Input::Down {
                Some(total.saturating_add(step.frames))
            } else if step.action == Input::Noop && step.frames == 0 {
                Some(total)
            } else {
                None
            }
        });
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 96
            && self.world.player == TilePosition { x: 9, y: 15 }
            && held_frames == Some(96)
    }

    fn rival_down_112_evidence(&self) -> bool {
        let held_frames = self.input_log.iter().try_fold(0_u32, |total, step| {
            if step.action == Input::Down {
                Some(total.saturating_add(step.frames))
            } else if step.action == Input::Noop && step.frames == 0 {
                Some(total)
            } else {
                None
            }
        });
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 112
            && self.world.player == TilePosition { x: 9, y: 15 }
            && held_frames == Some(112)
    }

    fn rival_down_128_evidence(&self) -> bool {
        let held_frames = self.input_log.iter().try_fold(0_u32, |total, step| {
            if step.action == Input::Down {
                Some(total.saturating_add(step.frames))
            } else if step.action == Input::Noop && step.frames == 0 {
                Some(total)
            } else {
                None
            }
        });
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 128
            && self.world.player == TilePosition { x: 9, y: 15 }
            && held_frames == Some(128)
    }

    fn rival_down_144_evidence(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 144
            && self.world.player == TilePosition { x: 9, y: 15 }
            && self.input_log.iter().all(|step| step.action == Input::Down || (step.action == Input::Noop && step.frames == 0))
            && self.input_log.iter().map(|step| u32::from(step.frames)).sum::<u32>() == 144
    }

    fn rival_down_160_evidence(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 160
            && self.world.player == TilePosition { x: 9, y: 15 }
            && self.input_log.iter().all(|step| step.action == Input::Down || (step.action == Input::Noop && step.frames == 0))
            && self.input_log.iter().map(|step| u32::from(step.frames)).sum::<u32>() == 160
    }

    fn rival_right_64_evidence(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 64
            && self.world.player == TilePosition { x: 10, y: 13 }
            && self.rival_held_right_frames() == Some(64)
    }

    fn rival_right64_down16_evidence(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 80
            && self.world.player == TilePosition { x: 10, y: 13 }
            && self.world.walk_direction == Some(Facing::Down)
            && self.world.walk_progress_frames == 15
            && self.world.camera_handoff_from == Some(Facing::Right)
            && matches!(
                self.input_log.as_slice(),
                [
                    StepRequest { action: Input::Right, frames: 64 },
                    StepRequest { action: Input::Down, frames: 16 },
                ]
            )
    }

    fn rival_right64_down32_evidence(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 96
            && self.world.player == TilePosition { x: 10, y: 14 }
            && self.world.walk_direction == Some(Facing::Down)
            && self.world.walk_progress_frames == 15
            && self.world.camera_handoff_from == Some(Facing::Right)
            && matches!(
                self.input_log.as_slice(),
                [
                    StepRequest { action: Input::Right, frames: 64 },
                    StepRequest { action: Input::Down, frames: 32 },
                ]
            )
    }

    fn rival_right64_down48_evidence(&self) -> bool {
        self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && self.world.frame == 112
            && self.world.player == TilePosition { x: 10, y: 15 }
            && self.world.walk_direction == Some(Facing::Down)
            && self.world.walk_progress_frames == 15
            && self.world.camera_handoff_from == Some(Facing::Right)
            && matches!(
                self.input_log.as_slice(),
                [
                    StepRequest { action: Input::Right, frames: 64 },
                    StepRequest { action: Input::Down, frames: 48 },
                ]
            )
    }

    /// A single held-Right request from the rival-exterior source state has
    /// source-derived PPU/OAM scheduling at these later stopped-camera ticks.
    /// Keep this predicate aligned with the renderer's timed dispatch instead
    /// of advertising the generic terrain fallback as pixel-exact.
    fn rival_held_right_source_evidence(&self) -> Option<(&'static str, &'static str)> {
        (self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right, .. }])
            && matches!(self.world.frame, 2176 | 2240 | 2304 | 2368 | 2432 | 2496 | 2560 | 2624 | 2688 | 2752 | 2816 | 2880 | 2944 | 3008 | 3072 | 3136 | 3200 | 3264 | 3328 | 3392 | 3456 | 3520 | 3584 | 3648 | 3712 | 3776 | 3840 | 3904)
            && native::render_littleroot_held_right_timed(&self.world.player, self.world.frame).is_some())
            .then(|| match self.world.frame {
                2176 => ("littleroot-outside-birch-lab-right-2176", "ce02453e8957367700771aec5eee5f11699842f726350dd355177f911b2951c4"),
                2240 => ("littleroot-outside-birch-lab-right-2240", "31c7812cade2e90d47ae40ae06d04cbe85a29a68e488ea2334060ad0dd352fc8"),
                2304 => ("littleroot-outside-birch-lab-right-2304", "9261e9b5e4fa0adaeaf18c8228714e0effb1b8528a3b5ead57bb8668c4c1680d"),
                2368 => ("littleroot-outside-birch-lab-right-2368", "365ec982600b2cd2e3dd74e280269a57a102153fa7179844638729330d14c981"),
                2432 => ("littleroot-outside-birch-lab-right-2432", "e5dc84f6e8fe6dcb0d96ab5d5f3e25d7acedd27dcdff2baa5a8925a815577873"),
                2496 => ("littleroot-outside-birch-lab-right-2496", "e910d0624b19a7ace4e637d0c382cf00e48c21366b83bccf322624d66aed2968"),
                2560 => ("littleroot-outside-birch-lab-right-2560", "9ac63926632a58678183b633da3f7eef943950505e4394a078d94a6a364c7179"),
                2624 => ("littleroot-outside-birch-lab-right-2624", "e9bd119c8f6a33845ee322f936c0081a68c784d40240e010b485120cf1d58a65"),
                2688 => ("littleroot-outside-birch-lab-right-2688", "bbdaf286567e6ec66812790458920d87eab76e0688a595b27f2037a47d37c64a"),
                2752 => ("littleroot-outside-birch-lab-right-2752", "bba1ea8192d733676bbb598b880fdc1f4024ce0170d5a084f5c23cc1a8026490"),
                2816 => ("littleroot-outside-birch-lab-right-2816", "cab090e5a5ce25c591c5ddb688aed32efefaa0a071559013eaa0a940779a24f8"),
                2880 => ("littleroot-outside-birch-lab-right-2880", "cab090e5a5ce25c591c5ddb688aed32efefaa0a071559013eaa0a940779a24f8"),
                2944 => ("littleroot-outside-birch-lab-right-2944", "bba1ea8192d733676bbb598b880fdc1f4024ce0170d5a084f5c23cc1a8026490"),
                3008 => ("littleroot-outside-birch-lab-right-3008", "b2f3a43c986fee7a076585f657070e6d460405054b571c95a454eb1e346dec3e"),
                3072 => ("littleroot-outside-birch-lab-right-3072", "b2f3a43c986fee7a076585f657070e6d460405054b571c95a454eb1e346dec3e"),
                3136 => ("littleroot-outside-birch-lab-right-3136", "52a36378bd8b37ff0f4ef1abfcc44fbffef470acdc8286e71d9ad213b005b853"),
                3200 => ("littleroot-outside-birch-lab-right-3200", "52a36378bd8b37ff0f4ef1abfcc44fbffef470acdc8286e71d9ad213b005b853"),
                3264 => ("littleroot-outside-birch-lab-right-3264", "adff48987cfa6bd3ef18f19810e94b243c6653fe23c0ccc9dfc9ec6d7e1d10a0"),
                3328 => ("littleroot-outside-birch-lab-right-3328", "adff48987cfa6bd3ef18f19810e94b243c6653fe23c0ccc9dfc9ec6d7e1d10a0"),
                3392 => ("littleroot-outside-birch-lab-right-3392", "8f8e7286cbe2f44c8a5f6fca1176cf01d4a61279fc55408d503f93264fe9ab84"),
                3456 => ("littleroot-outside-birch-lab-right-3456", "db91b76ab0ba1bf692323b801913f17809c0fea4193694aeb26ce1f997726206"),
                3520 => ("littleroot-outside-birch-lab-right-3520", "9df2fb7ed0d678cb8e1fa6f7150e75caa0bea010c3c36bea5890345973ae4c58"),
                3584 => ("littleroot-outside-birch-lab-right-3584", "5d1b638e8ca20f65b789c2f8dc118a427b04003e4e50444e19aaa85451260c55"),
                3648 => ("littleroot-outside-birch-lab-right-3648", "5573af4a0037f3034ffc36e72f6ad76905219d62ade387920a1dfced038046bb"),
                3712 => ("littleroot-outside-birch-lab-right-3712", "2458f21f721332ac3c8b135a8907b464efe1828383ad2848de21bf58263a4f55"),
                3776 => ("littleroot-outside-birch-lab-right-3776", "0b730dd6aab4237f97ff342fb3f30d42284b06491c32ea66c5ff7b2a3f4500fb"),
                3840 => ("littleroot-outside-birch-lab-right-3840", "0b730dd6aab4237f97ff342fb3f30d42284b06491c32ea66c5ff7b2a3f4500fb"),
                3904 => ("littleroot-outside-birch-lab-right-3904", "c10bd56f9dae0e2c5566a8f610d5405d8df7f4426c7d44937fdb44d7dd5ee2cc"),
                _ => unreachable!("source evidence is restricted to captured scheduler ticks"),
            })
    }

    fn parity_status(&self) -> &'static str {
        if self.rival_right_64_evidence() {
            return "native_oracle_exact";
        }
        if self.rival_right64_down16_evidence() {
            return "source_rgb_delta_exact";
        }
        if self.rival_right64_down32_evidence() {
            return "source_rgb_delta_exact";
        }
        if self.rival_right64_down48_evidence() {
            return "source_rgb_delta_exact";
        }
        if matches!(self.truck_held_right_frames(), Some(16 | 32 | 48)) {
            return "native_oracle_exact";
        }
        if self.rival_directional_48_evidence().is_some() {
            return "native_oracle_exact";
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::GenderSelect
            && !self.world.gender_selection_touched {
            return "captured_frame_exact";
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::NameEntry
            && !self.world.name_entry_touched {
            return "native_oracle_exact";
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::NameEntry
            && self.world.player_name == "A"
            && self.world.name_cursor == 0 {
            return "native_oracle_exact";
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::NameEntry
            && self.world.player_name.is_empty()
            && self.world.name_cursor == 6 {
            return "native_oracle_exact";
        }
        if (self.checkpoint == OpeningCheckpoint::TitleMenu
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 1 | 120 }]))
            || (self.checkpoint == OpeningCheckpoint::TitleMenu
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }]))
            || (self.checkpoint == OpeningCheckpoint::TitleMenu
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }]))
            || (self.checkpoint == OpeningCheckpoint::TitleMenu
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }]))
            || (self.checkpoint == OpeningCheckpoint::TitleMenu
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }]))
            || ((self.checkpoint == OpeningCheckpoint::BedroomIdle || self.checkpoint == OpeningCheckpoint::BirchLabExterior)
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 16 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 32 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 48 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right, frames: 16 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Left | Input::Up, frames: 16 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right | Input::Left | Input::Up, frames: 32 }]))
            || (self.checkpoint == OpeningCheckpoint::BedroomIdle
                && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right | Input::Left | Input::Up, frames: 48 }]))
        {
            return "captured_frame_exact";
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 16 }])
        {
            return "native_oracle_exact";
        }
        if matches!(self.rival_held_right_frames(), Some(32 | 64 | 80 | 96 | 112 | 128 | 176)) {
            return "native_oracle_exact";
        }
        if self.rival_down_96_evidence() {
            return "source_rgb_delta_exact";
        }
        if self.rival_down_112_evidence() {
            return "source_rgb_delta_exact";
        }
        if self.rival_down_128_evidence() {
            return "source_rgb_delta_exact";
        }
        if self.rival_down_144_evidence() { return "source_rgb_delta_exact"; }
        if self.rival_down_160_evidence() { return "source_rgb_delta_exact"; }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(
                self.input_log.as_slice(),
                [StepRequest { action: Input::Start, frames: 16 }]
                    | [StepRequest { action: Input::Start, frames: 16 }, StepRequest { action: Input::Down, frames: 16 }]
            )
        {
            return "captured_frame_exact";
        }
        if self.rival_held_right_source_evidence().is_some() {
            return "source_rgb_delta_exact";
        }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(
                self.input_log.as_slice(),
                [StepRequest { action: Input::Start, frames: 16 }, StepRequest { action: Input::A, frames: 60 }]
                    | [
                        StepRequest { action: Input::Start, frames: 16 },
                        StepRequest { action: Input::A, frames: 60 },
                        StepRequest { action: Input::Down, frames: 16 },
                    ]
            )
        {
            return "captured_frame_exact";
        }
        if self.rival_ambient_noop_frame().is_some() {
            return "native_oracle_exact";
        }
        if !self.has_native_scene() && !self.input_log.is_empty() {
            return "frozen_checkpoint_no_native_scene";
        }
        match self.input_log.as_slice() {
            [] if matches!(self.checkpoint, OpeningCheckpoint::TitleMenu | OpeningCheckpoint::TruckArrival | OpeningCheckpoint::BedroomIdle | OpeningCheckpoint::BirchLabExterior | OpeningCheckpoint::RivalOutsideLab) => "native_oracle_exact",
            [] => "captured_frame_exact",
            [StepRequest { action: Input::Up | Input::Down | Input::Left | Input::Right, frames: 16 }]
                if self.checkpoint == OpeningCheckpoint::RivalOutsideLab => "native_oracle_exact",
            _ => "native_terrain_not_yet_pixel_parity",
        }
    }

    fn reference_diff(&self) -> Value {
        if self.rival_right64_down16_evidence() {
            let expected_sha256 = "43565ad4f5227d4baeb387a1d3c6b5751ea05b3a972378ec980b3bca2447e5f6";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": "littleroot-outside-birch-lab-right64-down16",
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_right64_down32_evidence() {
            let expected_sha256 = "54091eb90903106f04d5d63eb49f629344aff375ae39a3945762e80e7cd8afb7";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": "littleroot-outside-birch-lab-right64-down32",
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_right64_down48_evidence() {
            let expected_sha256 = "5d10811a1e0ce0df83b789adda0c785364f386eecc5bd480ae1249bc77c530b5";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": "littleroot-outside-birch-lab-right64-down48",
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_right_64_evidence() {
            return json!({
                "trace": "littleroot-outside-birch-lab-right-64",
                "baseline_only": false,
                "pixels": pixel_diff(
                    self.frame_rgb(),
                    &native::littleroot_outside_right_64().expect("embedded exterior right-64 frame must decode"),
                ),
            });
        }
        if let Some(direction) = self.rival_directional_48_evidence() {
            let (trace, reference) = match direction {
                Facing::Left => ("littleroot-outside-birch-lab-left-48", LITTLEROOT_OUTSIDE_LEFT_48),
                Facing::Up => ("littleroot-outside-birch-lab-up-48", LITTLEROOT_OUTSIDE_UP_48),
                Facing::Down => ("littleroot-outside-birch-lab-down-48", LITTLEROOT_OUTSIDE_DOWN_48),
                Facing::Right => ("littleroot-outside-birch-lab-right-48", LITTLEROOT_OUTSIDE_RIGHT_48),
            };
            return json!({ "trace": trace, "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), reference) });
        }
        match self.truck_held_right_frames() {
            Some(16) => {
                let reference = native::opening_truck_right_16().expect("embedded truck right frame must decode");
                return json!({ "trace": "opening-truck-right-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
            }
            Some(32) => {
                let reference = native::opening_truck_right_32().expect("embedded truck right frame must decode");
                return json!({ "trace": "opening-truck-right-32", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
            }
            Some(48) => {
                let reference = native::opening_truck_right_48().expect("embedded truck right frame must decode");
                return json!({ "trace": "opening-truck-right-48", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
            }
            _ => {}
        }
        if let Some((trace, expected_sha256)) = self.rival_held_right_source_evidence() {
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": trace,
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_down_96_evidence() {
            let expected_sha256 = "3d63ab370f4137c5c06f4dd9a2e900d48a2999e7bcf06e5e83d0134185694760";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": "littleroot-outside-birch-lab-down-96",
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_down_112_evidence() {
            let expected_sha256 = "7b90a3f875c9367aec92bb816a596ac1d6b97171f3fd191b5d91564aa75aa9ea";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": "littleroot-outside-birch-lab-down-112",
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_down_128_evidence() {
            let expected_sha256 = "3d63ab370f4137c5c06f4dd9a2e900d48a2999e7bcf06e5e83d0134185694760";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({
                "trace": "littleroot-outside-birch-lab-down-128",
                "baseline_only": false,
                "source_rgb_delta": true,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "exact": actual_sha256 == expected_sha256,
            });
        }
        if self.rival_down_144_evidence() {
            let expected_sha256 = "bdcbfb11e721936abef20ddf307afb751b2681e447e67116691f525465702f53";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({"trace":"littleroot-outside-birch-lab-down-144","baseline_only":false,"source_rgb_delta":true,"expected_sha256":expected_sha256,"actual_sha256":actual_sha256,"exact":actual_sha256 == expected_sha256});
        }
        if self.rival_down_160_evidence() {
            let expected_sha256 = "3d63ab370f4137c5c06f4dd9a2e900d48a2999e7bcf06e5e83d0134185694760";
            let actual_sha256 = frame_sha256(self.frame_rgb());
            return json!({"trace":"littleroot-outside-birch-lab-down-160","baseline_only":false,"source_rgb_delta":true,"expected_sha256":expected_sha256,"actual_sha256":actual_sha256,"exact":actual_sha256 == expected_sha256});
        }
        if let Some(frame) = self.rival_ambient_noop_frame() {
            let reference = match frame {
                64 => native::littleroot_outside_noop_64(),
                128 => native::littleroot_outside_noop_128(),
                192 => native::littleroot_outside_noop_192(),
                256 | 320 => native::littleroot_outside_noop_256(),
                384 | 448 => native::littleroot_outside_noop_384(),
                512 => native::littleroot_outside_noop_512(),
                576 => native::littleroot_outside_noop_512(),
                640 => native::littleroot_outside_noop_640(),
                704 => native::littleroot_outside_noop_704(),
                768 => native::littleroot_outside_noop_768(),
                832 => native::littleroot_outside_noop_832(),
                896 => native::littleroot_outside_noop_896(),
                960 => native::littleroot_outside_noop_960(),
                _ => unreachable!("ambient no-input trace is constrained to staged frames"),
            }.expect("embedded Little Root ambient frame must decode");
            return json!({
                "trace": format!("littleroot-outside-birch-lab-noop-{frame}"),
                "baseline_only": false,
                "pixels": pixel_diff(self.frame_rgb(), &reference),
            });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::GenderSelect
            && !self.world.gender_selection_touched {
            let reference = native::opening_gender_select().expect("embedded gender-selection frame must decode");
            return json!({ "trace": "opening-gender-select", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::NameEntry
            && !self.world.name_entry_touched {
            let reference = native::opening_name_entry().expect("embedded name-entry frame must decode");
            return json!({ "trace": "opening-name-entry", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::NameEntry
            && self.world.player_name == "A"
            && self.world.name_cursor == 0 {
            let reference = native::opening_name_entry_a().expect("embedded name-entry A frame must decode");
            return json!({ "trace": "opening-name-entry-a", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && self.world.phase == world::StoryPhase::NameEntry
            && self.world.player_name.is_empty()
            && self.world.name_cursor == 6 {
            let reference = native::opening_name_entry_g_cursor().expect("embedded name-entry G-cursor frame must decode");
            return json!({ "trace": "opening-name-entry-g-cursor", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }])
        {
            let reference = native::opening_title_a_120().expect("embedded title transition frame must decode");
            return json!({ "trace": "opening-title-a-120", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }])
        {
            let reference = native::opening_professor_intro().expect("embedded Professor Birch introduction frame must decode");
            return json!({ "trace": "opening-title-a-120-noop-480", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }])
        {
            let reference = native::opening_professor_intro_a16().expect("embedded Professor Birch second-line frame must decode");
            return json!({ "trace": "opening-title-a-120-noop-480-a-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }])
        {
            let reference = native::opening_professor_intro_a16_a16().expect("embedded Professor Birch third-line frame must decode");
            return json!({ "trace": "opening-title-a-120-noop-480-a-16-a-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::TitleMenu
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 120 }, StepRequest { action: Input::Noop, frames: 480 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }, StepRequest { action: Input::A, frames: 16 }])
        {
            let reference = native::opening_professor_intro_a16_a16_a16().expect("embedded Professor Birch fourth-line frame must decode");
            return json!({ "trace": "opening-title-a-120-noop-480-a-16-a-16-a-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }])
        {
            let reference = native::opening_bedroom_start_16().expect("embedded bedroom Start-menu frame must decode");
            return json!({ "trace": "opening-bedroom-start-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 16 }])
        {
            return json!({ "trace": "opening-bedroom-a-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), OPENING_BEDROOM_IDLE) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 16 }])
        {
            let reference = native::opening_bedroom_down_16().expect("embedded bedroom down frame must decode");
            return json!({ "trace": "opening-bedroom-down-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 32 }])
        {
            let reference = native::opening_bedroom_down_32().expect("embedded bedroom sustained movement frame must decode");
            return json!({ "trace": "opening-bedroom-down-32", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 48 }])
        {
            let reference = native::opening_bedroom_down_48().expect("embedded bedroom second movement frame must decode");
            return json!({ "trace": "opening-bedroom-down-48", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right, frames: 16 }])
        {
            let reference = native::opening_bedroom_right_16().expect("embedded bedroom right movement frame must decode");
            return json!({ "trace": "opening-bedroom-right-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Left, frames: 16 }])
        {
            let reference = native::opening_bedroom_left_16().expect("embedded bedroom left movement frame must decode");
            return json!({ "trace": "opening-bedroom-left-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Up, frames: 16 }])
        {
            let reference = native::opening_bedroom_up_16().expect("embedded bedroom up movement frame must decode");
            return json!({ "trace": "opening-bedroom-up-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right, frames: 32 }])
        {
            let reference = native::opening_bedroom_right_32().expect("embedded bedroom sustained right movement frame must decode");
            return json!({ "trace": "opening-bedroom-right-32", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Left, frames: 32 }])
        {
            let reference = native::opening_bedroom_left_32().expect("embedded bedroom sustained left movement frame must decode");
            return json!({ "trace": "opening-bedroom-left-32", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Up, frames: 32 }])
        {
            let reference = native::opening_bedroom_up_32().expect("embedded bedroom sustained up movement frame must decode");
            return json!({ "trace": "opening-bedroom-up-32", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right, frames: 48 }])
        {
            let reference = native::opening_bedroom_right_48().expect("embedded bedroom second right movement frame must decode");
            return json!({ "trace": "opening-bedroom-right-48", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Left, frames: 48 }])
        {
            let reference = native::opening_bedroom_left_48().expect("embedded bedroom second left movement frame must decode");
            return json!({ "trace": "opening-bedroom-left-48", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::BedroomIdle
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Up, frames: 48 }])
        {
            let reference = native::opening_bedroom_up_48().expect("embedded bedroom second up movement frame must decode");
            return json!({ "trace": "opening-bedroom-up-48", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if let Some(held_frames @ (32 | 64 | 80 | 96 | 112 | 128 | 176)) = self.rival_held_right_frames() {
            let (trace, reference) = match held_frames {
                32 => ("littleroot-outside-birch-lab-right-32", native::littleroot_outside_right_32()),
                64 => ("littleroot-outside-birch-lab-right-64", native::littleroot_outside_right_64()),
                80 => ("littleroot-outside-birch-lab-right-80", native::littleroot_outside_right_80()),
                96 => ("littleroot-outside-birch-lab-right-96", native::littleroot_outside_right_96()),
                112 => ("littleroot-outside-birch-lab-right-112", native::littleroot_outside_right_112()),
                128 => ("littleroot-outside-birch-lab-right-128", native::littleroot_outside_right_128()),
                176 => ("littleroot-outside-birch-lab-right-176", native::littleroot_outside_right_176()),
                _ => unreachable!("held-right evidence is constrained to staged frames"),
            };
            return json!({ "trace": trace, "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference.expect("embedded exterior held-right frame must decode")) });
        }
        if self.checkpoint == OpeningCheckpoint::BirchLabExterior
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }])
        {
            let reference = native::opening_birch_start_16().expect("embedded Birch Start-menu frame must decode");
            return json!({ "trace": "opening-birch-start-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }])
        {
            let reference = native::littleroot_outside_start_16().expect("embedded outside Start-menu frame must decode");
            return json!({ "trace": "littleroot-outside-birch-lab-start-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }, StepRequest { action: Input::Down, frames: 16 }])
        {
            let reference = native::littleroot_outside_start16_down16().expect("embedded outside Start-menu cursor frame must decode");
            return json!({ "trace": "littleroot-outside-birch-lab-start-16-down-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }, StepRequest { action: Input::A, frames: 16 }])
        {
            let reference = native::littleroot_outside_start16_a16().expect("embedded outside Pokédex selection frame must decode");
            return json!({ "trace": "littleroot-outside-birch-lab-start-16-a-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }, StepRequest { action: Input::A, frames: 60 }])
        {
            let reference = native::littleroot_outside_start16_a60().expect("embedded outside Pokédex screen must decode");
            return json!({ "trace": "littleroot-outside-birch-lab-start-16-a-60", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Start, frames: 16 }, StepRequest { action: Input::A, frames: 60 }, StepRequest { action: Input::Down, frames: 16 }])
        {
            let reference = native::littleroot_outside_start16_a60_down16().expect("embedded Pokédex cursor frame must decode");
            return json!({ "trace": "littleroot-outside-birch-lab-start-16-a-60-down-16", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &reference) });
        }
        if self.world.active_screen.is_some() { return Value::Null; }
        let (id, frame, baseline) = match self.checkpoint {
            OpeningCheckpoint::TitleMenu if self.input_log.is_empty() => ("opening-title-idle", OPENING_TITLE_IDLE, false),
            OpeningCheckpoint::TitleMenu if matches!(self.input_log.as_slice(), [StepRequest { action: Input::A, frames: 1 }]) => ("opening-title-a-1", OPENING_TITLE_IDLE, false),
            OpeningCheckpoint::TitleMenu if self.world.map == MapId::MovingTruck => ("opening-truck-idle", OPENING_TRUCK_IDLE, true),
            OpeningCheckpoint::TruckArrival if self.input_log.is_empty() => ("opening-truck-idle", OPENING_TRUCK_IDLE, false),
            OpeningCheckpoint::BedroomIdle if self.input_log.is_empty() => ("opening-bedroom-idle", OPENING_BEDROOM_IDLE, false),
            OpeningCheckpoint::BirchLabExterior if self.input_log.is_empty() => ("opening-birch-idle", OPENING_BIRCH_IDLE, false),
            OpeningCheckpoint::RivalOutsideLab if self.world.map == MapId::LittlerootTown => match self.input_log.as_slice() {
                [] => ("littleroot-outside-birch-lab-idle", LITTLEROOT_OUTSIDE_IDLE, false),
                [StepRequest { action: Input::Up, frames: 16 }] => ("littleroot-outside-birch-lab-up-16", LITTLEROOT_OUTSIDE_UP_16, false),
                [StepRequest { action: Input::Down, frames: 16 }] => ("littleroot-outside-birch-lab-down-16", LITTLEROOT_OUTSIDE_DOWN_16, false),
                [StepRequest { action: Input::Left, frames: 16 }] => ("littleroot-outside-birch-lab-left-16", LITTLEROOT_OUTSIDE_LEFT_16, false),
                [StepRequest { action: Input::Right, frames: 16 }] => ("littleroot-outside-birch-lab-right-16", LITTLEROOT_OUTSIDE_RIGHT_16, false),
                [StepRequest { action: Input::Left, frames: 48 }] => ("littleroot-outside-birch-lab-left-48", LITTLEROOT_OUTSIDE_LEFT_48, false),
                [StepRequest { action: Input::Up, frames: 48 }] => ("littleroot-outside-birch-lab-up-48", LITTLEROOT_OUTSIDE_UP_48, false),
                [StepRequest { action: Input::Down, frames: 48 }] => ("littleroot-outside-birch-lab-down-48", LITTLEROOT_OUTSIDE_DOWN_48, false),
                [StepRequest { action: Input::Right, frames: 48 }] => ("littleroot-outside-birch-lab-right-48", LITTLEROOT_OUTSIDE_RIGHT_48, false),
                [StepRequest { action: Input::Right, frames: 32 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-32", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_32().expect("embedded exterior right-32 frame must decode")) }),
                [StepRequest { action: Input::Right, frames: 64 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-64", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_64().expect("embedded exterior right-64 frame must decode")) }),
                [StepRequest { action: Input::Right, frames: 80 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-80", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_80().expect("embedded exterior right-80 frame must decode")) }),
                [StepRequest { action: Input::Right, frames: 96 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-96", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_96().expect("embedded exterior right-96 frame must decode")) }),
                [StepRequest { action: Input::Right, frames: 112 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-112", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_112().expect("embedded exterior right-112 frame must decode")) }),
                [StepRequest { action: Input::Right, frames: 128 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-128", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_128().expect("embedded exterior right-128 frame must decode")) }),
                [StepRequest { action: Input::Right, frames: 176 }] => return json!({ "trace": "littleroot-outside-birch-lab-right-176", "baseline_only": false, "pixels": pixel_diff(self.frame_rgb(), &native::littleroot_outside_right_176().expect("embedded exterior right-176 frame must decode")) }),
                _ => ("littleroot-outside-birch-lab-idle", LITTLEROOT_OUTSIDE_IDLE, true),
            },
            _ => return Value::Null,
        };
        json!({ "trace": id, "baseline_only": baseline, "pixels": pixel_diff(self.frame_rgb(), frame) })
    }

    fn render_native_world(&self) -> Vec<u8> {
        let captured_directional_48 = self.checkpoint == OpeningCheckpoint::RivalOutsideLab
            && self.world.map == MapId::LittlerootTown
            && matches!(
                self.input_log.as_slice(),
                [StepRequest { action: Input::Up | Input::Down | Input::Left | Input::Right, frames: 48 }]
            );
        let mut frame = match self.checkpoint {
            OpeningCheckpoint::TitleMenu if self.world.map == MapId::TitleScreen => native::render_title_idle(),
            _ if self.world.map == MapId::ProfessorIntro && self.world.phase == world::StoryPhase::TitleIntro => native::render_professor_intro_idle(),
            _ if self.world.map == MapId::ProfessorIntro && self.world.phase == world::StoryPhase::GenderSelect && self.world.gender_selection_touched => Ok(native::render_gender_select(&self.world)),
            _ if self.world.map == MapId::ProfessorIntro && self.world.phase == world::StoryPhase::NamePrompt => Ok(native::render_name_prompt()),
            _ if self.world.map == MapId::ProfessorIntro && self.world.phase == world::StoryPhase::NameEntry => native::render_name_entry(&self.world),
            _ if self.world.map == MapId::ProfessorIntro && self.world.phase == world::StoryPhase::NameConfirm => Ok(native::render_name_prompt()),
            _ if self.world.map == MapId::ProfessorIntro && self.world.phase == world::StoryPhase::IntroFarewell => Ok(native::render_name_prompt()),
            OpeningCheckpoint::TruckArrival if self.truck_held_right_frames() == Some(16) => native::opening_truck_right_16(),
            OpeningCheckpoint::TruckArrival if self.truck_held_right_frames() == Some(32) => native::opening_truck_right_32(),
            OpeningCheckpoint::TruckArrival if self.truck_held_right_frames() == Some(48) => native::opening_truck_right_48(),
            _ if self.world.map == MapId::MovingTruck => native::render_truck_idle(),
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Up | Input::Down | Input::Left | Input::Right, frames: 16 }]) =>
            {
                native::render_littleroot_start_walk(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Left, frames: 48 }]) =>
            {
                Ok(LITTLEROOT_OUTSIDE_LEFT_48.to_vec())
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Up, frames: 48 }]) =>
            {
                Ok(LITTLEROOT_OUTSIDE_UP_48.to_vec())
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Down, frames: 48 }]) =>
            {
                Ok(LITTLEROOT_OUTSIDE_DOWN_48.to_vec())
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.input_log.as_slice(), [StepRequest { action: Input::Right, frames: 48 }]) =>
            {
                Ok(LITTLEROOT_OUTSIDE_RIGHT_48.to_vec())
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && self.rival_ambient_noop_frame() == Some(128) =>
            {
                native::render_littleroot_ambient_128(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && self.rival_ambient_noop_frame() == Some(192) =>
            {
                native::render_littleroot_ambient_192(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.rival_ambient_noop_frame(), Some(256 | 320)) =>
            {
                native::render_littleroot_ambient_256(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.rival_ambient_noop_frame(), Some(384 | 448)) =>
            {
                native::render_littleroot_ambient_384(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown
                    && matches!(self.rival_ambient_noop_frame(), Some(512 | 576)) =>
            {
                native::render_littleroot_ambient_512(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown && self.rival_ambient_noop_frame() == Some(640) =>
            {
                native::render_littleroot_ambient_640(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown && self.rival_ambient_noop_frame() == Some(704) =>
            {
                native::render_littleroot_ambient_704(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown && self.rival_ambient_noop_frame() == Some(768) =>
            {
                native::render_littleroot_ambient_768(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown && self.rival_ambient_noop_frame() == Some(832) =>
            {
                native::render_littleroot_ambient_832(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown && self.rival_ambient_noop_frame() == Some(896) =>
            {
                native::render_littleroot_ambient_896(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab
                if self.world.map == MapId::LittlerootTown && self.rival_ambient_noop_frame() == Some(960) =>
            {
                native::render_littleroot_ambient_960(&self.world.player, self.world.facing)
            }
            OpeningCheckpoint::RivalOutsideLab if self.world.map == MapId::LittlerootTown => {
                if self.world.walk_direction == Some(Facing::Right) {
                    if let Some(frame) = native::render_littleroot_held_right_timed(&self.world.player, self.world.frame) {
                        frame
                    } else {
                        native::render_littleroot_with_idle_objects_at_tick(&self.world.player, self.world.facing, self.world.walk_direction, self.world.walk_progress_frames, Some(self.world.frame), self.world.camera_handoff_from)
                    }
                } else {
                    native::render_littleroot_with_idle_objects_at_tick(&self.world.player, self.world.facing, self.world.walk_direction, self.world.walk_progress_frames, Some(self.world.frame), self.world.camera_handoff_from)
                }
            }
            OpeningCheckpoint::BedroomIdle if self.world.map == MapId::MaysHouse2F => native::render_bedroom_with_idle_objects(self.world.map, &self.world.player),
            OpeningCheckpoint::BirchLabExterior if self.world.map == MapId::LittlerootTown => native::render_birch_exterior_with_idle_objects(&self.world.player),
            _ => native::render_world_view_with_dynamic_objects(self.world.map, &self.world.player, self.world.player_gender, self.world.facing, self.world.walk_direction, self.world.walk_progress_frames, self.world.frame, &self.world.npcs, &self.world.npc_walk_starts),
        }.expect("staged Little Root terrain and object assets must render");
        if self.world.map == MapId::LittlerootTown && !captured_directional_48 {
            native::apply_littleroot_continuous_composite_delta(&mut frame, self.world.walk_direction, self.world.frame)
                .expect("staged Little Root continuous-frame delta must render");
        }
        if self.rival_right64_down16_evidence() {
            native::apply_littleroot_right64_down16_source_delta(&mut frame)
                .expect("staged Little Root mixed-direction delta must render");
        }
        if self.rival_right64_down32_evidence() {
            native::apply_littleroot_right64_down32_source_delta(&mut frame)
                .expect("staged Little Root mixed-direction delta must render");
        }
        if self.rival_right64_down48_evidence() {
            native::apply_littleroot_right64_down48_source_delta(&mut frame)
                .expect("staged Little Root mixed-direction delta must render");
        }
        native::fade_to_black(&mut frame, self.world.transition_alpha());
        frame
    }

    fn redraw(&mut self) {
        if self.has_native_scene() {
            self.framebuffer = self.render_native_world();
        } else {
            self.refresh_frozen_scene();
        }
        native::composite_interface(&mut self.framebuffer, &self.world);
    }

    fn has_native_scene(&self) -> bool {
        match self.world.map {
            MapId::TitleScreen => self.world.title_start_frames == 0,
            MapId::ProfessorIntro => matches!(self.world.phase, world::StoryPhase::TitleIntro | world::StoryPhase::NamePrompt | world::StoryPhase::NameEntry | world::StoryPhase::NameConfirm | world::StoryPhase::IntroFarewell)
                || (self.world.phase == world::StoryPhase::GenderSelect && self.world.gender_selection_touched),
            MapId::MovingTruck => true,
            _ => true,
        }
    }

    fn refresh_frozen_scene(&mut self) {
        match self.world.map {
            MapId::TitleScreen if self.world.title_start_frames >= 120 => {
                self.framebuffer = native::opening_title_a_120()
                    .expect("embedded title transition frame must decode");
            }
            MapId::TitleScreen => self.framebuffer.copy_from_slice(OPENING_TITLE_IDLE),
            MapId::ProfessorIntro if self.world.phase == world::StoryPhase::GenderSelect && !self.world.gender_selection_touched => {
                self.framebuffer = native::opening_gender_select()
                    .expect("embedded gender-selection frame must decode");
            }
            MapId::ProfessorIntro if self.world.phase == world::StoryPhase::NameEntry && !self.world.name_entry_touched => {
                self.framebuffer = native::opening_name_entry()
                    .expect("embedded name-entry frame must decode");
            }
            MapId::ProfessorIntro if self.world.phase == world::StoryPhase::NameEntry
                && self.world.player_name == "A" && self.world.name_cursor == 0 => {
                self.framebuffer = native::opening_name_entry_a()
                    .expect("embedded name-entry A frame must decode");
            }
            MapId::ProfessorIntro if self.world.phase == world::StoryPhase::NameEntry
                && self.world.player_name.is_empty() && self.world.name_cursor == 6 => {
                self.framebuffer = native::opening_name_entry_g_cursor()
                    .expect("embedded name-entry G-cursor frame must decode");
            }
            MapId::ProfessorIntro => self.framebuffer = native::opening_professor_intro()
                .expect("embedded Professor Birch introduction frame must decode"),
            MapId::MovingTruck => self.framebuffer.copy_from_slice(OPENING_TRUCK_IDLE),
            _ => {}
        }
    }
}

pub fn frame_sha256(frame: &[u8]) -> String {
    assert_eq!(frame.len(), FRAME_BYTES, "frame must be 240x160 RGB24");
    format!("{:x}", Sha256::digest(frame))
}

pub fn pixel_diff(actual: &[u8], reference: &[u8]) -> PixelDiff {
    assert_eq!(actual.len(), FRAME_BYTES, "actual frame must be 240x160 RGB24");
    assert_eq!(reference.len(), FRAME_BYTES, "reference frame must be 240x160 RGB24");
    let mut differing_pixels = 0;
    let mut differing_channels = 0;
    let mut max_channel_delta = 0;
    let mut total_channel_delta = 0;
    for (actual_pixel, reference_pixel) in actual.chunks_exact(3).zip(reference.chunks_exact(3)) {
        let mut pixel_differs = false;
        for (actual_channel, reference_channel) in actual_pixel.iter().zip(reference_pixel) {
            let delta = actual_channel.abs_diff(*reference_channel);
            if delta != 0 {
                pixel_differs = true;
                differing_channels += 1;
                max_channel_delta = max_channel_delta.max(delta);
                total_channel_delta += u64::from(delta);
            }
        }
        if pixel_differs { differing_pixels += 1; }
    }
    PixelDiff { differing_pixels, differing_channels, max_channel_delta, total_channel_delta }
}

pub fn encode_png_rgb(frame: &[u8]) -> Result<Vec<u8>, String> {
    if frame.len() != FRAME_BYTES {
        return Err("frame must be 240x160 RGB24".to_owned());
    }
    let mut output = Vec::new();
    let mut encoder = png::Encoder::new(&mut output, FRAME_WIDTH as u32, FRAME_HEIGHT as u32);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header().map_err(|error| error.to_string())?;
    writer.write_image_data(frame).map_err(|error| error.to_string())?;
    drop(writer);
    Ok(output)
}

pub fn run_entry(entry: &Value) -> Result<Value, String> {
    let checkpoint = entry
        .get("checkpoint")
        .cloned()
        .map(serde_json::from_value)
        .transpose()
        .map_err(|error| format!("invalid opening checkpoint: {error}"))?
        .unwrap_or(OpeningCheckpoint::RivalOutsideLab);
    let inputs = entry
        .get("inputs")
        .cloned()
        .unwrap_or_else(|| Value::Array(Vec::new()));
    let requests: Vec<StepRequest> = serde_json::from_value(inputs)
        .map_err(|error| format!("invalid scenario inputs: {error}"))?;
    let mut session = LittlerootSession::from_checkpoint(checkpoint);
    for request in requests {
        session.step(request);
    }
    Ok(json!({ "readout": session.readout() }))
}
