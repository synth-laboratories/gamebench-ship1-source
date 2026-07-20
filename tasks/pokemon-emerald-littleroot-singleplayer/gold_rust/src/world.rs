use serde::{Deserialize, Serialize};

const SOURCE_RIVAL_RUNNING_SHOES_TRIGGER: u8 = 6;
/// The counterpart-rival approach and PC scripts use `walk_in_place_faster_*`
/// for every compact turn, whose source object-event duration is four frames.
const BEDROOM_RIVAL_FASTER_TURN_FRAMES: u16 = 4;
/// The 2F doorway rail previously treated its terminal
/// `walk_in_place_faster_*` turn as the eight-frame fast variant. Both
/// counterpart scripts use the four-frame faster action, so this preserves
/// the existing entry beat while releasing the approach four frames sooner.
const BEDROOM_RIVAL_ENTRY_FRAMES: u16 = 96;

fn bedroom_rival_movement_frames(faster: bool) -> u16 {
    if faster {
        BEDROOM_RIVAL_FASTER_TURN_FRAMES
    } else {
        16
    }
}

/// `PetalburgGymReport{Male,Female}` spends one faster in-place turn, an
/// exclamation emote, and `Common_Movement_Delay48` before Mom speaks.
const TV_BROADCAST_INTRO_FRAMES: u16 = 84;
/// `Common_Movement_ExclamationMark` completes its object movement in one
/// tick, while the spawned field-effect icon stays animated for 60 frames.
const RIVAL_MOM_EMOTE_MOVEMENT_FRAMES: u16 = 1;
const RIVAL_MOM_EXCLAMATION_FRAMES: u8 = 60;
const RIVAL_MOM_DELAY_FRAMES: u16 = 48;
const RIVAL_MOM_NORMAL_STEP_FRAMES: u16 = 16;
const RIVAL_MOM_APPROACH_FRAMES: u16 = RIVAL_MOM_NORMAL_STEP_FRAMES * 6;
/// The map script waits for the one-tick emote, Delay48, and six normal
/// movement actions before its first new-neighbor message can open.
const RIVAL_MOM_INTRO_FRAMES: u16 = RIVAL_MOM_EMOTE_MOVEMENT_FRAMES
    + RIVAL_MOM_DELAY_FRAMES
    + RIVAL_MOM_APPROACH_FRAMES;
/// `PlayerApproachTVForGym{Male,Female}` is five ordinary 16-frame strides
/// after Mom's first Gym-report message closes.
const TV_BROADCAST_APPROACH_FRAMES: u16 = 80;
const TV_BROADCAST_APPROACH_STEP_FRAMES: u16 = 16;
/// After `MaybeDadWillBeOn` closes, Mom walks sideways and turns before the
/// player takes the final TV stride and faster up-facing turn.
const TV_BROADCAST_VIEW_MOM_STEP_FRAMES: u16 = 16;
const TV_BROADCAST_VIEW_FASTER_TURN_FRAMES: u16 = 4;
const TV_BROADCAST_VIEW_PLAYER_STEP_FRAMES: u16 = 16;
const TV_BROADCAST_VIEW_FRAMES: u16 = TV_BROADCAST_VIEW_MOM_STEP_FRAMES
    + TV_BROADCAST_VIEW_FASTER_TURN_FRAMES
    + TV_BROADCAST_VIEW_PLAYER_STEP_FRAMES
    + TV_BROADCAST_VIEW_FASTER_TURN_FRAMES;

fn default_tv_screen_on() -> bool {
    true
}
/// `MomApproachDoor` completes after its 24-frame pause and normal walk;
/// `PlayerApproachDoor` adds a four-frame fast up-facing turn, which controls
/// the shared `waitmovement` release.
const TRUCK_DEPARTURE_APPROACH_FRAMES: u16 = 44;
/// `opendoor` / `closedoor` each run four five-tick source frames before
/// `waitdooranim` releases the Little Root moving-in script.
const LITTLEROOT_DOOR_ANIMATION_FRAMES: u16 = 20;
/// `MomEnterHouse` is a single normal upward stride, while
/// `PlayerEnterHouse` takes two; both start as soon as the door opens.
const TRUCK_DEPARTURE_ENTRY_FRAMES: u16 = 32;
const TRUCK_DEPARTURE_FRAMES: u16 = TRUCK_DEPARTURE_APPROACH_FRAMES
    + LITTLEROOT_DOOR_ANIMATION_FRAMES
    + TRUCK_DEPARTURE_ENTRY_FRAMES
    + LITTLEROOT_DOOR_ANIMATION_FRAMES;
/// The Running Shoes return routes that end beside the player's home have
/// the same open / enter / close tail as the truck scene, but only Mom moves.
const RUNNING_SHOES_RETURN_DOOR_FRAMES: u16 = LITTLEROOT_DOOR_ANIMATION_FRAMES
    + 16
    + LITTLEROOT_DOOR_ANIMATION_FRAMES;
const NEW_HOME_FACE_PLAYER_FRAMES: u8 = 1;
// `walk_in_place_faster_{left,right}` follows Mom's source `face_player`
// action and lasts four frames, rather than the eight-frame fast cadence.
const NEW_HOME_PLAYER_FAST_TURN_FRAMES: u8 = 4;
const NEW_HOME_ORIENTATION_FRAMES: u8 =
    NEW_HOME_FACE_PLAYER_FRAMES + NEW_HOME_PLAYER_FAST_TURN_FRAMES;
/// Matches the port's existing post-input `MUS_OBTAIN_ITEM` receipt cadence.
const POKE_BALL_GIFT_FANFARE_REMAINING_FRAMES: u16 = 144;
/// `EventScript_ReceivePokedex` uses the same `MUS_OBTAIN_ITEM` fanfare as
/// `giveitem ITEM_POKE_BALL, 5`, so it retains the same post-input rail.
const POKEDEX_RECEIPT_FANFARE_REMAINING_FRAMES: u16 = POKE_BALL_GIFT_FANFARE_REMAINING_FRAMES;
/// `MomEnters{Male,Female}` takes 68 frames. The wall-clock script then
/// waits for the player's four-frame `WalkInPlaceFaster` turn before Mom can
/// open her upstairs message.
/// `CB2_StartWallClock` initializes its editable clock to 10:00 AM before
/// it creates the two hand sprites (`tHours = 10`, `tMinutes = 0`).
const WALL_CLOCK_START_MINUTES: u16 = 10 * 60;
/// `SpriteCB_PMIndicator` and `SpriteCB_AMIndicator` both settle in 21
/// VBlanks: fifteen one-degree steps, then six five-degree steps.
const WALL_CLOCK_PERIOD_TRANSITION_FRAMES: u8 = 21;
const CLOCK_VISIT_MOM_ENTRY_FRAMES: u16 = 68;
const CLOCK_VISIT_PLAYER_TURN_FRAMES: u16 = 4;
const CLOCK_VISIT_ENTRY_FRAMES: u16 =
    CLOCK_VISIT_MOM_ENTRY_FRAMES + CLOCK_VISIT_PLAYER_TURN_FRAMES;
/// Route103's north watcher spends 44 frames in its authored movement while
/// the rival's first two normal steps take 32. `waitmovement` then releases
/// the 112-frame ledge stream (`jump_2_down`, `delay_16`, four walks).
const ROUTE103_RIVAL_EXIT_NORTH_FRAMES: u16 = 156;
/// The east/west watcher delays 16 frames then makes a four-frame turn, so
/// its first parallel movement stream holds the shared ledge exit for 20.
const ROUTE103_RIVAL_EXIT_SIDE_FRAMES: u16 = 116;
/// A south-facing player has no watcher movement; the first rival step holds
/// the second stream for its normal 16-frame duration.
const ROUTE103_RIVAL_EXIT_SOUTH_FRAMES: u16 = 112;

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MapId {
    TitleScreen,
    ProfessorIntro,
    MovingTruck,
    LittlerootTown,
    Route101,
    OldaleTown,
    Route103,
    BrendansHouse1F,
    BrendansHouse2F,
    MaysHouse1F,
    MaysHouse2F,
    ProfessorBirchsLab,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum OpeningCheckpoint {
    TitleMenu,
    TruckArrival,
    BedroomIdle,
    BirchLabExterior,
    RivalOutsideLab,
    Route101Rescue,
    Route103Rival,
    RunningShoes,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum StoryPhase {
    Title,
    TitleIntro,
    GenderSelect,
    NamePrompt,
    NameEntry,
    NameConfirm,
    IntroFarewell,
    IntroTruck,
    TruckArrival,
    NewHome,
    ClockSet,
    ClockVisit,
    TvBroadcast,
    MeetRival,
    MetRival,
    BirchRescue,
    StarterSelect,
    /// The source's short, input-locked affine reveal after a Poké Ball is
    /// chosen and before its standard confirmation menu appears.
    StarterReveal,
    StarterConfirm,
    BirchBattle,
    StarterChosen,
    RivalBattle,
    RivalDefeated,
    BirchRescued,
    StarterLab,
    PokedexHandoff,
    PokedexReceived,
    RunningShoesReceived,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Facing { Up, Down, Left, Right }

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PlayerGender { Brendan, May }

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct GenderTransition {
    pub outgoing: PlayerGender,
    pub incoming: PlayerGender,
    pub frames_remaining: u8,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MenuEntry { Pokedex, Pokemon, Bag, Player, Save, Option, Exit }

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClockField { Hours, Minutes }

/// The wall-clock editor's AM/PM badges are independent source OAM sprites.
/// Keep their actual angular state, rather than snapping badges whenever the
/// displayed time crosses noon or midnight.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct ClockPeriodTransition {
    pm_angle: u8,
    am_angle: u8,
    target_is_pm: bool,
    elapsed_frames: u8,
}

fn wall_clock_settled_period_angles(is_pm: bool) -> (u8, u8) {
    if is_pm { (90, 135) } else { (45, 90) }
}

/// Exact `SpriteCB_PMIndicator` angle update from `src/wallclock.c`.
fn wall_clock_advance_pm_indicator(angle: u8, target_is_pm: bool) -> u8 {
    let mut angle = angle;
    if target_is_pm {
        if (60..90).contains(&angle) { angle += 5; }
        if angle < 60 { angle += 1; }
    } else {
        if (46..76).contains(&angle) { angle -= 5; }
        if angle > 75 { angle -= 1; }
    }
    angle
}

/// Exact `SpriteCB_AMIndicator` angle update from `src/wallclock.c`.
fn wall_clock_advance_am_indicator(angle: u8, target_is_pm: bool) -> u8 {
    let mut angle = angle;
    if target_is_pm {
        if (105..135).contains(&angle) { angle += 5; }
        if angle < 105 { angle += 1; }
    } else {
        if (91..121).contains(&angle) { angle -= 5; }
        if angle > 120 { angle -= 1; }
    }
    angle
}

/// `NAMING_SCREEN_PLAYER` and `NAMING_SCREEN_NICKNAME` share Emerald's
/// keyboard controls but commit to different saved data.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NamingTarget { Player, Starter }

/// The three source controls in the naming screen's action-button column.
/// The two middle keyboard rows both route to Emerald's Back control.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NamingActionButton { Page, Back, Ok }

/// Serialized mirror of `Task_UpdateButtonFlash` in `naming_screen.c`.
/// `applied_color` is the most recent value written into the source's faded
/// OBJ palette; the remaining fields directly model the task's data slots.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct NamingActionButtonPulse {
    pub button: NamingActionButton,
    pub color: i16,
    pub color_incr: i16,
    pub color_delay: i16,
    pub color_delta: i16,
    pub keep_flashing: bool,
    pub allow_flash: bool,
    pub applied_color: u8,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StarterSpecies { Treecko, Torchic, Mudkip }

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BattleOpponent { Zigzagoon, Poochyena, Wingull, Wurmple, Rival }

// `gActionSelectionCursor` is a row-major two-bit source cursor. Keeping the
// state values identical to `HandleInputChooseAction` lets the renderer use
// `ActionSelectionCreateCursorAt`'s tile coordinates directly.
pub const BATTLE_COMMAND_FIGHT: u8 = 0;
pub const BATTLE_COMMAND_BAG: u8 = 1;
pub const BATTLE_COMMAND_POKEMON: u8 = 2;
pub const BATTLE_COMMAND_RUN: u8 = 3;
/// `PlayerHandleIntroTrainerBallThrow` translates the player trainer back
/// sprite from `(80, 80)` to `(-40, 80)` over fifty frames before the
/// regular Poké Ball release controller takes over.
pub const BATTLE_PLAYER_INTRO_SENDOUT_FRAMES: u8 = 50;
/// `Task_StartSendOutAnim` waits through its thirty-one source counter ticks;
/// the follow-up ball task then spends one frame idling before it creates the
/// player-side Poké Ball OBJ.
pub const BATTLE_PLAYER_SENDOUT_BALL_SPAWN_FRAME: u8 = 34;
/// `SpriteCB_PlayerMonSendOut_1` prepares the 25-frame arc one tick after
/// the ball appears, so this is the first `TranslateAnimHorizontalArc` frame.
pub const BATTLE_PLAYER_SENDOUT_BALL_FIRST_ARC_FRAME: u8 = 36;
pub const BATTLE_PLAYER_SENDOUT_BALL_ARC_FRAMES: u8 = 25;
/// The last arc callback commits the ball's accumulated offset and hands it
/// to `SpriteCB_ReleaseMonFromBall`. The release callback then runs the
/// source twelve-tick `BATTLER_AFFINE_EMERGE` sequence before the command
/// controller is released; particles and sound remain a separate rail.
pub const BATTLE_PLAYER_SENDOUT_TOTAL_FRAMES: u8 = 61;
/// `sAffineAnim_Battler_Emerge` seeds 0x28 and adds 0x12 for twelve ticks,
/// reaching the normal 0x100 matrix scale. Keep the visual hand-off inside
/// the existing serialized send-out lock so a save resumes the same phase.
pub const BATTLE_PLAYER_SENDOUT_RELEASE_FRAMES: u8 = 12;
pub const BATTLE_PLAYER_SENDOUT_COMPLETE_FRAMES: u8 =
    BATTLE_PLAYER_SENDOUT_TOTAL_FRAMES + BATTLE_PLAYER_SENDOUT_RELEASE_FRAMES;

/// A source moveset slot, retained independently of the currently selected
/// move so an opponent controller can choose from the original four slots.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct BattleMoveSlot {
    pub name: String,
    pub pp: u8,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct BattleState {
    pub opponent: BattleOpponent,
    /// Emerald's global `Random()` stream as it enters this active battle.
    /// Keeping it with the serializable battle means a restored mid-turn
    /// checkpoint continues accuracy, critical, and damage-variance draws.
    #[serde(default = "default_battle_rng_state")]
    pub rng_state: u32,
    #[serde(default = "default_player_species")]
    pub player_species: String,
    #[serde(default = "default_opponent_species")]
    pub opponent_species: String,
    #[serde(default = "default_opponent_move_name")]
    pub opponent_move_name: String,
    /// Ordered as `gBattleMons[battler].moves`: ordinary wild opponents
    /// sample its four slots, while trainers score the populated slots.
    #[serde(default = "default_opponent_move_slots")]
    pub opponent_moves: Vec<BattleMoveSlot>,
    /// The source slot chosen for the current opponent action. It makes a
    /// restored battle retain both the displayed move and the PP owner.
    #[serde(default)]
    pub opponent_move_slot: Option<u8>,
    /// Completed opponent actions, used by Route 103 Treecko's source
    /// `AI_SCRIPT_SETUP_FIRST_TURN` behavior.
    #[serde(default)]
    pub opponent_turn_count: u8,
    /// Only Brendan's Route 103 Treecko trainer has
    /// `AI_SCRIPT_SETUP_FIRST_TURN`; May's matching Treecko uses viability.
    #[serde(default)]
    pub rival_setup_first_turn: bool,
    #[serde(default = "default_opponent_move_damage")]
    pub opponent_move_damage: u8,
    pub player_hp: u8,
    #[serde(default = "default_player_battle_hp")]
    pub player_max_hp: u8,
    #[serde(default = "default_battle_level")]
    pub player_level: u8,
    #[serde(default = "default_battle_stat")]
    pub player_attack: u8,
    #[serde(default = "default_battle_stat")]
    pub player_defense: u8,
    #[serde(default = "default_battle_stat")]
    pub player_speed: u8,
    #[serde(default = "default_battle_stat")]
    pub player_special_attack: u8,
    #[serde(default = "default_battle_stat")]
    pub player_special_defense: u8,
    pub rival_hp: u8,
    #[serde(default = "default_opponent_battle_hp")]
    pub opponent_max_hp: u8,
    #[serde(default = "default_battle_level")]
    pub opponent_level: u8,
    #[serde(default = "default_battle_stat")]
    pub opponent_attack: u8,
    #[serde(default = "default_battle_stat")]
    pub opponent_defense: u8,
    #[serde(default = "default_battle_stat")]
    pub opponent_speed: u8,
    #[serde(default = "default_battle_stat")]
    pub opponent_special_attack: u8,
    #[serde(default = "default_battle_stat")]
    pub opponent_special_defense: u8,
    #[serde(default = "default_player_move_damage")]
    pub player_move_damage: u8,
    #[serde(default = "default_player_move_name")]
    pub player_move_name: String,
    #[serde(default = "default_player_status_move_name")]
    pub player_status_move_name: String,
    #[serde(default = "default_player_move_pp")]
    pub player_move_pp: u8,
    #[serde(default = "default_player_status_move_pp")]
    pub player_status_move_pp: u8,
    /// Negative after Growl; bounded to Emerald's six-stage stat range.
    #[serde(default)]
    pub opponent_attack_stage: i8,
    /// Negative after Leer; the compact battle slice applies this to the
    /// player's subsequent physical opening move.
    #[serde(default)]
    pub opponent_defense_stage: i8,
    /// The three stat stages that the scoped opponent status moves can
    /// change: Growl, Leer, and String Shot.
    #[serde(default)]
    pub player_attack_stage: i8,
    #[serde(default)]
    pub player_defense_stage: i8,
    #[serde(default)]
    pub player_speed_stage: i8,
    /// Source `gActionSelectionCursor`: FIGHT/BAG across the top, then
    /// POKéMON/RUN across the bottom (0 through 3 in row-major order).
    #[serde(default)]
    pub command_cursor: u8,
    /// True after choosing FIGHT, when the two opening moves are shown.
    #[serde(default)]
    pub selecting_move: bool,
    /// The opening slice has one party member, but retains a distinct party
    /// view so the POKéMON battle command has the same modal behavior as the
    /// field and later multi-member engine.
    #[serde(default)]
    pub party_screen_open: bool,
    /// A wild encounter can return to the field without changing the story
    /// phase; trainer and Birch-rescue battles remain locked.
    #[serde(default)]
    pub escaped: bool,
    /// `AI_FirstBattle` can submit `B_ACTION_RUN` when the player's HP is at
    /// or below 20 percent. Keep that opponent action distinct from a player
    /// escape so restored rescue battles preserve the controller decision.
    #[serde(default)]
    pub opponent_fled: bool,
    /// Distinguishes an ordinary Route 101 wild Poochyena from the scripted
    /// Birch-rescue Zigzagoon battle, which has a different post-battle path.
    #[serde(default)]
    pub wild: bool,
    pub move_cursor: u8,
    pub player_fainted: bool,
    pub message: Option<String>,
    /// Encounter wipe remaining before the battle command screen accepts
    /// input. Keeping it on the battle itself makes an interrupted save/load
    /// resume the same encounter instead of dropping directly into a turn.
    #[serde(default)]
    pub entry_transition_frames: u16,
    /// Battle introduction message page: challenge/appearance, send-out, and
    /// starter send-out. Older serialized battle snapshots resume at the
    /// command screen rather than replaying a new introduction.
    #[serde(default = "default_battle_intro_stage")]
    pub intro_stage: u8,
    /// The displayed `Go!` page is distinct from ordinary battle text so
    /// confirming it can begin Emerald's player trainer exit rather than
    /// treating a later move-result page as a second send-out.
    #[serde(default)]
    pub intro_player_sendout_pending: bool,
    /// Remaining source ticks in `PlayerHandleIntroTrainerBallThrow`'s
    /// 50-frame player-back-sprite exit. This is serialized so a replay
    /// resumed during the hand-off retains the same visual phase and input
    /// lock without consulting an emulator.
    #[serde(default)]
    pub intro_player_sendout_frames: u8,
    /// The source player-send-out task begins the ball controller before the
    /// fifty-frame trainer exit has finished. Preserve its shared timeline
    /// separately so the ball can overlap the departing trainer and a save
    /// made during the arc resumes at the same source subphase.
    #[serde(default)]
    pub intro_player_sendout_elapsed_frames: u8,
    /// Older snapshots intentionally resume at the command screen. This
    /// explicit marker prevents their default intro stage from replaying a
    /// new send-out just because the new elapsed field deserializes to zero.
    #[serde(default)]
    pub intro_player_sendout_started: bool,
    /// Outcome metadata for the most recently resolved move. It keeps the
    /// deterministic RNG decision observable without inventing battle UI.
    #[serde(default)]
    pub last_move_hit: bool,
    #[serde(default)]
    pub last_move_critical: bool,
    #[serde(default)]
    pub last_damage_variance: Option<u8>,
}

fn default_player_battle_hp() -> u8 { 24 }
fn default_opponent_battle_hp() -> u8 { 22 }
fn default_player_move_damage() -> u8 { 9 }
fn default_player_move_name() -> String { "TACKLE".to_owned() }
fn default_player_status_move_name() -> String { "GROWL".to_owned() }
fn default_player_move_pp() -> u8 { 35 }
fn default_player_status_move_pp() -> u8 { 30 }
fn default_opponent_species() -> String { "ZIGZAGOON".to_owned() }
fn default_opponent_move_name() -> String { "TACKLE".to_owned() }
fn default_opponent_move_slots() -> Vec<BattleMoveSlot> {
    vec![BattleMoveSlot { name: default_opponent_move_name(), pp: 35 }]
}
fn default_opponent_move_damage() -> u8 { 4 }
fn default_battle_intro_stage() -> u8 { 2 }
fn default_battle_rng_state() -> u32 { default_ambient_rng() }
fn default_player_species() -> String { "TREECKO".to_owned() }
fn default_battle_level() -> u8 { 5 }
fn default_battle_stat() -> u8 { 10 }

fn battle_opponent_name(opponent: BattleOpponent) -> &'static str {
    match opponent {
        BattleOpponent::Zigzagoon => "ZIGZAGOON",
        BattleOpponent::Poochyena => "POOCHYENA",
        BattleOpponent::Wingull => "WINGULL",
        BattleOpponent::Wurmple => "WURMPLE",
        BattleOpponent::Rival => "your RIVAL",
    }
}

fn fast_path_position(start: TilePosition, path: &[Facing], completed: usize, idle_facing: Facing) -> (TilePosition, Facing) {
    let mut position = start;
    let mut facing = idle_facing;
    for step in path.iter().take(completed) {
        facing = *step;
        match step {
            Facing::Up => position.y -= 1,
            Facing::Down => position.y += 1,
            Facing::Left => position.x -= 1,
            Facing::Right => position.x += 1,
        }
    }
    (position, facing)
}

// `Route101_EventScript_StartBirchRescue` waits for the longest actor
// stream: 48 frames entering, Zigzagoon's 31-step / 248-frame circle, then
// Birch's four-frame turn and the paired 32-frame facing actions.
const ROUTE101_RESCUE_CHOREOGRAPHY_FRAMES: u16 = 332;

#[derive(Clone, Copy, PartialEq, Eq)]
enum BattleType { Normal, Grass, Fire, Water, Dark, Bug, Flying }

#[derive(Clone, Copy)]
struct SpeciesBattleProfile {
    name: &'static str, base_hp: u8, base_attack: u8, base_defense: u8,
    base_speed: u8, base_special_attack: u8, base_special_defense: u8,
    types: (BattleType, BattleType),
}

#[derive(Clone, Copy)]
struct MoveBattleProfile { name: &'static str, power: u8, accuracy: u8, pp: u8, move_type: BattleType, special: bool }

#[derive(Clone, Copy)]
struct CombatantBattleProfile {
    species: SpeciesBattleProfile, level: u8, max_hp: u8, attack: u8, defense: u8, speed: u8,
    special_attack: u8, special_defense: u8, moves: [Option<MoveBattleProfile>; 4],
}

/// Persistent source-shaped party state for the one Pokémon reachable in the
/// opening slice. BattleState remains an active combat projection; this owns
/// HP and PP between encounters just as gPlayerParty does.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct StarterPartyState {
    pub species: StarterSpecies,
    /// `CreateMon` begins with the species name. A `None` nickname preserves
    /// that source default for restored checkpoints written before nickname
    /// ownership was serialized.
    #[serde(default)]
    pub nickname: Option<String>,
    pub level: u8,
    pub hp: u8,
    pub max_hp: u8,
    pub attack: u8,
    pub defense: u8,
    pub speed: u8,
    pub special_attack: u8,
    pub special_defense: u8,
    pub physical_move_pp: u8,
    pub status_move_pp: u8,
}

#[derive(Clone, Copy)]
struct StatIvs { hp: u8, attack: u8, defense: u8, speed: u8, special_attack: u8, special_defense: u8 }

#[derive(Clone, Copy)]
struct NatureModifiers { attack: (u8, u8), defense: (u8, u8), speed: (u8, u8), special_attack: (u8, u8), special_defense: (u8, u8) }

const NEUTRAL_NATURE: NatureModifiers = NatureModifiers { attack: (1, 1), defense: (1, 1), speed: (1, 1), special_attack: (1, 1), special_defense: (1, 1) };

fn species_battle_profile(name: &str) -> SpeciesBattleProfile {
    // Source: src/data/pokemon/species_info.h. This is deliberately limited
    // to species reachable in the scoped opening route.
    match name {
        "TORCHIC" => SpeciesBattleProfile { name: "TORCHIC", base_hp: 45, base_attack: 60, base_defense: 40, base_speed: 45, base_special_attack: 70, base_special_defense: 50, types: (BattleType::Fire, BattleType::Fire) },
        "MUDKIP" => SpeciesBattleProfile { name: "MUDKIP", base_hp: 50, base_attack: 70, base_defense: 50, base_speed: 40, base_special_attack: 50, base_special_defense: 50, types: (BattleType::Water, BattleType::Water) },
        "ZIGZAGOON" => SpeciesBattleProfile { name: "ZIGZAGOON", base_hp: 38, base_attack: 30, base_defense: 41, base_speed: 60, base_special_attack: 30, base_special_defense: 41, types: (BattleType::Normal, BattleType::Normal) },
        "POOCHYENA" => SpeciesBattleProfile { name: "POOCHYENA", base_hp: 35, base_attack: 55, base_defense: 35, base_speed: 35, base_special_attack: 30, base_special_defense: 30, types: (BattleType::Dark, BattleType::Dark) },
        "WURMPLE" => SpeciesBattleProfile { name: "WURMPLE", base_hp: 45, base_attack: 45, base_defense: 35, base_speed: 20, base_special_attack: 20, base_special_defense: 30, types: (BattleType::Bug, BattleType::Bug) },
        "WINGULL" => SpeciesBattleProfile { name: "WINGULL", base_hp: 40, base_attack: 30, base_defense: 30, base_speed: 85, base_special_attack: 55, base_special_defense: 30, types: (BattleType::Water, BattleType::Flying) },
        _ => SpeciesBattleProfile { name: "TREECKO", base_hp: 40, base_attack: 45, base_defense: 35, base_speed: 70, base_special_attack: 65, base_special_defense: 55, types: (BattleType::Grass, BattleType::Grass) },
    }
}

fn move_battle_profile(name: &str) -> MoveBattleProfile {
    // Source: src/data/battle_moves.h.
    match name {
        "POUND" => MoveBattleProfile { name: "POUND", power: 40, accuracy: 100, pp: 35, move_type: BattleType::Normal, special: false },
        "SCRATCH" => MoveBattleProfile { name: "SCRATCH", power: 40, accuracy: 100, pp: 35, move_type: BattleType::Normal, special: false },
        "LEER" => MoveBattleProfile { name: "LEER", power: 0, accuracy: 100, pp: 30, move_type: BattleType::Normal, special: false },
        "GROWL" => MoveBattleProfile { name: "GROWL", power: 0, accuracy: 100, pp: 40, move_type: BattleType::Normal, special: false },
        "STRING SHOT" => MoveBattleProfile { name: "STRING SHOT", power: 0, accuracy: 95, pp: 40, move_type: BattleType::Bug, special: false },
        "WATER GUN" => MoveBattleProfile { name: "WATER GUN", power: 40, accuracy: 100, pp: 25, move_type: BattleType::Water, special: true },
        _ => MoveBattleProfile { name: "TACKLE", power: 35, accuracy: 95, pp: 35, move_type: BattleType::Normal, special: false },
    }
}

fn starter_species_name(starter: Option<StarterSpecies>) -> &'static str {
    match starter.unwrap_or(StarterSpecies::Treecko) {
        StarterSpecies::Treecko => "TREECKO", StarterSpecies::Torchic => "TORCHIC", StarterSpecies::Mudkip => "MUDKIP",
    }
}

fn source_random(state: &mut u32) -> u16 {
    *state = state.wrapping_mul(0x41c6_4e6d).wrapping_add(0x0000_6073);
    (*state >> 16) as u16
}

fn source_random32(state: &mut u32) -> u32 { u32::from(source_random(state)) | (u32::from(source_random(state)) << 16) }

fn nature_modifiers(nature: u8) -> NatureModifiers {
    // gNatureStatTable order: Atk, Def, Speed, Sp.Atk, Sp.Def.
    const TABLE: [(Option<usize>, Option<usize>); 25] = [
        (None,None),(Some(0),Some(1)),(Some(0),Some(2)),(Some(0),Some(3)),(Some(0),Some(4)),
        (Some(1),Some(0)),(None,None),(Some(1),Some(2)),(Some(1),Some(3)),(Some(1),Some(4)),
        (Some(2),Some(0)),(Some(2),Some(1)),(None,None),(Some(2),Some(3)),(Some(2),Some(4)),
        (Some(3),Some(0)),(Some(3),Some(1)),(Some(3),Some(2)),(None,None),(Some(3),Some(4)),
        (Some(4),Some(0)),(Some(4),Some(1)),(Some(4),Some(2)),(Some(4),Some(3)),(None,None),
    ];
    let (raise, lower) = TABLE[usize::from(nature % 25)];
    let mut stats = [(1, 1); 5];
    if let Some(stat) = raise { stats[stat] = (110, 100); }
    if let Some(stat) = lower { stats[stat] = (90, 100); }
    NatureModifiers { attack: stats[0], defense: stats[1], speed: stats[2], special_attack: stats[3], special_defense: stats[4] }
}

fn source_random_ivs(seed: u32) -> (StatIvs, NatureModifiers) {
    // ScriptGiveMon → CreateMon(... USE_RANDOM_IVS ...): Random32 for the
    // personality followed by two packed six-IV Random calls.
    let mut rng = seed;
    let personality = source_random32(&mut rng);
    let first = u32::from(source_random(&mut rng));
    let second = u32::from(source_random(&mut rng));
    (StatIvs { hp: (first & 31) as u8, attack: ((first >> 5) & 31) as u8, defense: ((first >> 10) & 31) as u8, speed: (second & 31) as u8, special_attack: ((second >> 5) & 31) as u8, special_defense: ((second >> 10) & 31) as u8 }, nature_modifiers((personality % 25) as u8))
}

fn source_stat(base: u8, iv: u8, level: u8, modifier: (u8, u8)) -> u8 {
    let raw = ((u16::from(2 * base + iv) * u16::from(level)) / 100) + 5;
    ((raw * u16::from(modifier.0)) / u16::from(modifier.1)) as u8
}

fn source_hp(base: u8, iv: u8, level: u8) -> u8 { (((u16::from(2 * base + iv) * u16::from(level)) / 100) + u16::from(level) + 10) as u8 }

fn combatant_profile(species: SpeciesBattleProfile, level: u8, ivs: StatIvs, nature: NatureModifiers, move_names: &[&str]) -> CombatantBattleProfile {
    let mut moves = [None; 4];
    for (slot, name) in move_names.iter().take(moves.len()).enumerate() {
        moves[slot] = Some(move_battle_profile(name));
    }
    CombatantBattleProfile {
        species, level, max_hp: source_hp(species.base_hp, ivs.hp, level),
        attack: source_stat(species.base_attack, ivs.attack, level, nature.attack), defense: source_stat(species.base_defense, ivs.defense, level, nature.defense), speed: source_stat(species.base_speed, ivs.speed, level, nature.speed),
        special_attack: source_stat(species.base_special_attack, ivs.special_attack, level, nature.special_attack), special_defense: source_stat(species.base_special_defense, ivs.special_defense, level, nature.special_defense),
        moves,
    }
}

fn starter_battle_profile(starter: Option<StarterSpecies>) -> CombatantBattleProfile {
    let (ivs, nature) = source_random_ivs(default_ambient_rng());
    let (physical, status) = match starter.unwrap_or(StarterSpecies::Treecko) {
        StarterSpecies::Treecko => ("POUND", "LEER"), StarterSpecies::Torchic => ("SCRATCH", "GROWL"), StarterSpecies::Mudkip => ("TACKLE", "GROWL"),
    };
    combatant_profile(species_battle_profile(starter_species_name(starter)), 5, ivs, nature, &[physical, status])
}

fn starter_party_state(starter: StarterSpecies) -> StarterPartyState {
    let profile = starter_battle_profile(Some(starter));
    let physical_move = profile.moves[0].expect("starter must have a physical opening move");
    let status_move = profile.moves[1].expect("starter must have a status opening move");
    StarterPartyState {
        species: starter,
        nickname: None,
        level: profile.level,
        hp: profile.max_hp,
        max_hp: profile.max_hp,
        attack: profile.attack,
        defense: profile.defense,
        speed: profile.speed,
        special_attack: profile.special_attack,
        special_defense: profile.special_defense,
        physical_move_pp: physical_move.pp,
        status_move_pp: status_move.pp,
    }
}

fn rival_battle_profile(starter: Option<StarterSpecies>, player_gender: PlayerGender) -> CombatantBattleProfile {
    // Route 103's trainer tables use level 5, IV 0, default moves. The
    // source name-hashed trainer personality determines the shown nature.
    let name = match starter.unwrap_or(StarterSpecies::Treecko) { StarterSpecies::Treecko => "TORCHIC", StarterSpecies::Torchic => "MUDKIP", StarterSpecies::Mudkip => "TREECKO" };
    let nature = match (player_gender, name) {
        (PlayerGender::Brendan, "TREECKO") => nature_modifiers(1), (PlayerGender::Brendan, "TORCHIC") => nature_modifiers(20), (PlayerGender::Brendan, "MUDKIP") => nature_modifiers(17),
        (PlayerGender::May, "TREECKO") => nature_modifiers(20), (PlayerGender::May, "TORCHIC") => nature_modifiers(14), (PlayerGender::May, "MUDKIP") => nature_modifiers(11), _ => NEUTRAL_NATURE,
    };
    let (physical, status) = match name { "TREECKO" => ("POUND", "LEER"), "TORCHIC" => ("SCRATCH", "GROWL"), _ => ("TACKLE", "GROWL") };
    combatant_profile(species_battle_profile(name), 5, StatIvs { hp: 0, attack: 0, defense: 0, speed: 0, special_attack: 0, special_defense: 0 }, nature, &[physical, status])
}

fn wild_battle_profile(name: &str, level: u8, move_names: &[&str]) -> CombatantBattleProfile {
    let name_hash = name.bytes().fold(0u32, |hash, byte| hash.wrapping_mul(31).wrapping_add(u32::from(byte)));
    let (ivs, nature) = source_random_ivs(default_ambient_rng() ^ u32::from(level) ^ name_hash);
    combatant_profile(species_battle_profile(name), level, ivs, nature, move_names)
}

fn source_stage_stat(stat: u8, stage: i8) -> u8 {
    let stage = stage.clamp(-6, 6);
    if stage >= 0 { ((u16::from(stat) * (2 + stage) as u16) / 2) as u8 } else { ((u16::from(stat) * 2) / (2 - stage) as u16) as u8 }
}

fn type_multiplier(move_type: BattleType, types: (BattleType, BattleType)) -> (u8, u8) {
    let mut numerator = 1;
    let mut denominator = 1;
    for (index, defending) in [types.0, types.1].iter().enumerate() {
        if index == 1 && types.0 == types.1 { break; }
        let (up, down) = match (move_type, *defending) { (BattleType::Water, BattleType::Grass | BattleType::Water) => (1, 2), (BattleType::Water, BattleType::Fire) => (2, 1), _ => (1, 1) };
        numerator *= up; denominator *= down;
    }
    (numerator, denominator)
}

fn source_move_damage(level: u8, attacker: SpeciesBattleProfile, attack: u8, special_attack: u8, attacker_stage: i8, defender: SpeciesBattleProfile, defense: u8, special_defense: u8, defender_stage: i8, move_data: MoveBattleProfile, critical: bool) -> u8 {
    if move_data.power == 0 { return 0; }
    let attack_stat = if move_data.special { special_attack } else { attack };
    let defense_stat = if move_data.special { special_defense } else { defense };
    // `CalculateBaseDamage` ignores an attacker's negative stage and a
    // defender's positive stage on a critical hit, but preserves the
    // favorable stage in either direction.
    let attacking = if critical && attacker_stage <= 0 { attack_stat } else { source_stage_stat(attack_stat, attacker_stage) };
    let defending = (if critical && defender_stage >= 0 { defense_stat } else { source_stage_stat(defense_stat, defender_stage) }).max(1);
    let scaled = (u32::from(2 * level / 5 + 2) * u32::from(move_data.power) * u32::from(attacking)) / u32::from(defending);
    let mut damage = ((scaled / 50) + 2) as u16;
    if critical { damage *= 2; }
    if attacker.types.0 == move_data.move_type || attacker.types.1 == move_data.move_type { damage = (damage * 15) / 10; }
    let (numerator, denominator) = type_multiplier(move_data.move_type, defender.types);
    damage = (damage * u16::from(numerator)) / u16::from(denominator);
    damage.max(1) as u8
}

fn player_battle_damage(battle: &BattleState, critical: bool) -> u8 {
    source_move_damage(battle.player_level, species_battle_profile(&battle.player_species), battle.player_attack, battle.player_special_attack, battle.player_attack_stage, species_battle_profile(&battle.opponent_species), battle.opponent_defense, battle.opponent_special_defense, battle.opponent_defense_stage, move_battle_profile(&battle.player_move_name), critical)
}

fn opponent_battle_damage_for(battle: &BattleState, move_data: MoveBattleProfile, critical: bool) -> u8 {
    source_move_damage(battle.opponent_level, species_battle_profile(&battle.opponent_species), battle.opponent_attack, battle.opponent_special_attack, battle.opponent_attack_stage, species_battle_profile(&battle.player_species), battle.player_defense, battle.player_special_defense, battle.player_defense_stage, move_data, critical)
}

fn opening_battle_state(opponent: BattleOpponent, player: CombatantBattleProfile, enemy: CombatantBattleProfile, wild: bool, message: String, entry_transition_frames: u16, rng_state: u32, rival_setup_first_turn: bool) -> BattleState {
    let player_physical = player.moves[0].expect("starter must have a physical opening move");
    let player_status = player.moves[1].expect("starter must have a status opening move");
    let opponent_initial = enemy.moves[0].expect("opening opponent must have a first move slot");
    let player_move_damage = source_move_damage(player.level, player.species, player.attack, player.special_attack, 0, enemy.species, enemy.defense, enemy.special_defense, 0, player_physical, false);
    let opponent_move_damage = source_move_damage(enemy.level, enemy.species, enemy.attack, enemy.special_attack, 0, player.species, player.defense, player.special_defense, 0, opponent_initial, false);
    let opponent_moves = enemy.moves.iter().flatten().map(|move_data| BattleMoveSlot {
        name: move_data.name.to_owned(),
        pp: move_data.pp,
    }).collect();
    BattleState {
        opponent, rng_state, player_species: player.species.name.to_owned(), opponent_species: enemy.species.name.to_owned(), opponent_move_name: opponent_initial.name.to_owned(), opponent_moves, opponent_move_slot: None, opponent_turn_count: 0, rival_setup_first_turn, opponent_move_damage,
        player_hp: player.max_hp, player_max_hp: player.max_hp, player_level: player.level, player_attack: player.attack, player_defense: player.defense, player_speed: player.speed, player_special_attack: player.special_attack, player_special_defense: player.special_defense,
        rival_hp: enemy.max_hp, opponent_max_hp: enemy.max_hp, opponent_level: enemy.level, opponent_attack: enemy.attack, opponent_defense: enemy.defense, opponent_speed: enemy.speed, opponent_special_attack: enemy.special_attack, opponent_special_defense: enemy.special_defense,
        player_move_damage, player_move_name: player_physical.name.to_owned(), player_status_move_name: player_status.name.to_owned(), player_move_pp: player_physical.pp, player_status_move_pp: player_status.pp,
        opponent_attack_stage: 0, opponent_defense_stage: 0, player_attack_stage: 0, player_defense_stage: 0, player_speed_stage: 0, command_cursor: BATTLE_COMMAND_FIGHT, selecting_move: false, party_screen_open: false, escaped: false, opponent_fled: false, wild, move_cursor: 0, player_fainted: false, message: Some(message), entry_transition_frames, intro_stage: 0, intro_player_sendout_pending: false, intro_player_sendout_frames: 0, intro_player_sendout_elapsed_frames: 0, intro_player_sendout_started: false, last_move_hit: false, last_move_critical: false, last_damage_variance: None,
    }
}

#[derive(Clone, Copy)]
struct BattleMoveResolution { hit: bool, critical: bool, damage: u8 }

#[derive(Clone, Copy)]
enum OpponentChoice {
    Move(usize),
    Flee,
}

fn battle_random(battle: &mut BattleState) -> u16 {
    source_random(&mut battle.rng_state)
}

fn source_hp_percent(hp: u8, max_hp: u8) -> u8 {
    (u16::from(hp) * 100 / u16::from(max_hp.max(1))) as u8
}

fn legal_opponent_move_slots(battle: &BattleState) -> Vec<usize> {
    battle.opponent_moves.iter().enumerate()
        .filter_map(|(slot, move_slot)| (move_slot.pp > 0).then_some(slot))
        .collect()
}

fn opponent_move_data(battle: &BattleState, slot: usize) -> Option<MoveBattleProfile> {
    battle.opponent_moves.get(slot)
        .filter(|move_slot| move_slot.pp > 0)
        .map(|move_slot| move_battle_profile(&move_slot.name))
}

fn choose_tied_opponent_move(battle: &mut BattleState, choices: &[usize]) -> usize {
    choices[usize::from(battle_random(battle)) % choices.len()]
}

fn battle_ai_simulated_variance(battle: &mut BattleState) -> [u8; 4] {
    // `BattleAI_SetupAIData` fills all four `simulatedRNG` slots before it
    // evaluates the source scripts, including empty move positions.
    let mut variance = [0; 4];
    for percent in &mut variance {
        *percent = 100 - (battle_random(battle) % 16) as u8;
    }
    variance
}

fn rival_attack_down_score_penalty(battle: &mut BattleState) -> i16 {
    // Exact opening branch of `AI_CV_AttackDown` for the Route 103
    // Torchic/Mudkip trainer: the player's Grass/Fire target types are not
    // in the script's physical-type table, so its final 50% branch runs.
    let mut penalty = 0;
    let target_stage = i16::from(battle.player_attack_stage) + 6;
    if target_stage != 6 {
        penalty += 1;
        if source_hp_percent(battle.rival_hp, battle.opponent_max_hp) <= 90 {
            penalty += 1;
        }
        if target_stage <= 3 && battle_random(battle) % 256 >= 50 {
            penalty += 2;
        }
    }
    if source_hp_percent(battle.player_hp, battle.player_max_hp) <= 70 {
        penalty += 2;
    }
    if battle_random(battle) % 256 >= 50 {
        penalty += 2;
    }
    penalty
}

fn rival_defense_down_score_penalty(battle: &mut BattleState) -> i16 {
    // May's Route 103 Treecko runs `AI_CV_DefenseDown` for Leer. Unlike
    // Growl's branch, it has no type check; its only opening random branch
    // is reached once Treecko is below 70% HP or the target's Defense is
    // already reduced to stage -3 or below.
    let mut penalty = 0;
    let target_stage = i16::from(battle.player_defense_stage) + 6;
    if source_hp_percent(battle.rival_hp, battle.opponent_max_hp) < 70 || target_stage <= 3 {
        if battle_random(battle) % 256 >= 50 {
            penalty += 2;
        }
    }
    if source_hp_percent(battle.player_hp, battle.player_max_hp) <= 70 {
        penalty += 2;
    }
    penalty
}

fn select_route103_rival_move(battle: &mut BattleState) -> usize {
    let simulated_variance = battle_ai_simulated_variance(battle);
    let legal_slots = legal_opponent_move_slots(battle);
    let physical_slot = legal_slots.iter().copied()
        .find(|slot| opponent_move_data(battle, *slot).is_some_and(|move_data| move_data.power > 0))
        .expect("Route 103 rival must have a damaging move");
    let status_slot = legal_slots.iter().copied()
        .find(|slot| opponent_move_data(battle, *slot).is_some_and(|move_data| move_data.power == 0));
    let physical_move = opponent_move_data(battle, physical_slot).expect("selected rival move must remain usable");
    let simulated_damage = (u16::from(opponent_battle_damage_for(battle, physical_move, false))
        * u16::from(simulated_variance[physical_slot]) / 100).max(1) as u8;
    let physical_score = if simulated_damage >= battle.player_hp { 104 } else { 100 };
    let mut scores = legal_slots.iter().map(|_| 100_i16).collect::<Vec<_>>();
    if let Some(status_slot) = status_slot {
        let status_index = legal_slots.iter().position(|slot| *slot == status_slot)
            .expect("status move must be a legal move");
        let status_move = opponent_move_data(battle, status_slot)
            .expect("selected rival status move must remain usable");
        scores[status_index] = if battle.rival_setup_first_turn {
            if battle.opponent_turn_count == 0 {
                // Brendan's Route 103 Treecko has AI_SCRIPT_SETUP_FIRST_TURN.
                // Leer is its sole setup effect, and the script scores it +2
                // only when `if_random_less_than 80` does not jump.
                100 + if battle_random(battle) % 256 >= 80 { 2 } else { 0 }
            } else {
                // That trainer does not also enable AI_SCRIPT_CHECK_VIABILITY.
                100
            }
        } else {
            match status_move.name {
                // Torchic/Mudkip and May's Treecko use viability, with the
                // source routine selected by the actual status move effect.
                "GROWL" => 100 - rival_attack_down_score_penalty(battle),
                "LEER" => 100 - rival_defense_down_score_penalty(battle),
                _ => 100,
            }
        };
    }
    let physical_index = legal_slots.iter().position(|slot| *slot == physical_slot)
        .expect("damaging move must be a legal move");
    scores[physical_index] = physical_score;
    let best_score = scores.iter().copied().max().expect("rival has legal moves");
    let best_slots = legal_slots.iter().zip(scores).filter_map(|(slot, score)| {
        (score == best_score).then_some(*slot)
    }).collect::<Vec<_>>();
    // `ChooseMoveOrAction_Singles` always rolls the final index, even for a
    // unique best move (`Random() % 1`).
    choose_tied_opponent_move(battle, &best_slots)
}

fn select_first_battle_move(battle: &mut BattleState) -> OpponentChoice {
    let _simulated_variance = battle_ai_simulated_variance(battle);
    // `AI_FirstBattle` tests the target's integer HP percentage with
    // `if_hp_equal` / `if_hp_less_than`, then returns `AI_CHOICE_FLEE`.
    // It consumes no final best-move tie-break draw in that branch.
    if source_hp_percent(battle.player_hp, battle.player_max_hp) <= 20 {
        return OpponentChoice::Flee;
    }
    let legal_slots = legal_opponent_move_slots(battle);
    // Above 20% player HP, the script does not change either opening score,
    // leaving the source tie-break selection.
    OpponentChoice::Move(choose_tied_opponent_move(battle, &legal_slots))
}

fn select_wild_opponent_move(battle: &mut BattleState) -> usize {
    // The ordinary wild branch of `OpponentHandleChooseMove` samples its
    // four source move slots until it reaches a non-MOVE_NONE entry; this
    // controller selection does not inspect PP.
    loop {
        let slot = usize::from(battle_random(battle) % 4);
        if battle.opponent_moves.get(slot).is_some() {
            return slot;
        }
    }
}

fn select_opening_opponent_choice(battle: &mut BattleState) -> OpponentChoice {
    let choice = match battle.opponent {
        BattleOpponent::Rival => OpponentChoice::Move(select_route103_rival_move(battle)),
        BattleOpponent::Zigzagoon => select_first_battle_move(battle),
        BattleOpponent::Poochyena | BattleOpponent::Wingull | BattleOpponent::Wurmple => OpponentChoice::Move(select_wild_opponent_move(battle)),
    };
    if let OpponentChoice::Move(slot) = choice {
        let move_slot = battle.opponent_moves.get(slot).expect("selected opponent slot must exist");
        battle.opponent_move_name = move_slot.name.clone();
        battle.opponent_move_slot = Some(slot as u8);
    }
    choice
}

fn resolve_opponent_flee(battle: &mut BattleState) {
    debug_assert_eq!(battle.opponent, BattleOpponent::Zigzagoon);
    battle.opponent_fled = true;
    battle.selecting_move = false;
    battle.message = Some(format!("Wild {} fled!", battle.opponent_species));
}

fn battle_accuracy_check(battle: &mut BattleState, move_data: MoveBattleProfile) -> bool {
    // `Cmd_accuracycheck` always consumes `Random() % 100 + 1`, including
    // the source opening moves with 100% accuracy.
    let hit = (battle_random(battle) % 100 + 1) <= u16::from(move_data.accuracy);
    battle.last_move_hit = hit;
    battle.last_move_critical = false;
    battle.last_damage_variance = None;
    hit
}

fn battle_critical_check(battle: &mut BattleState) -> bool {
    // `BATTLE_TYPE_FIRST_BATTLE` short-circuits before its `Random()` call.
    // The Birch-rescue Zigzagoon is that opening tutorial battle, so neither
    // side can crit nor consume a critical-roll RNG value there.
    battle.opponent != BattleOpponent::Zigzagoon && battle_random(battle).is_multiple_of(16)
}

fn apply_battle_damage_variance(battle: &mut BattleState, damage: u8) -> u8 {
    // `Cmd_adjustnormaldamage`: 100 - (`Random() % 16), i.e. 85–100%.
    let percent = 100 - (battle_random(battle) % 16) as u8;
    battle.last_damage_variance = Some(percent);
    (u16::from(damage) * u16::from(percent) / 100).max(1) as u8
}

fn resolve_player_damage_move(battle: &mut BattleState) -> BattleMoveResolution {
    let move_data = move_battle_profile(&battle.player_move_name);
    if !battle_accuracy_check(battle, move_data) {
        return BattleMoveResolution { hit: false, critical: false, damage: 0 };
    }
    let critical = battle_critical_check(battle);
    let damage = apply_battle_damage_variance(battle, player_battle_damage(battle, critical));
    battle.last_move_critical = critical;
    BattleMoveResolution { hit: true, critical, damage }
}

fn resolve_opponent_damage_move(battle: &mut BattleState) -> BattleMoveResolution {
    let selected_slot = battle.opponent_move_slot.map(usize::from).or_else(|| {
        battle.opponent_moves.iter().position(|move_slot| {
            move_slot.pp > 0 && move_slot.name == battle.opponent_move_name
        })
    });
    let Some(selected_slot) = selected_slot else {
        return BattleMoveResolution { hit: false, critical: false, damage: 0 };
    };
    let Some(move_data) = opponent_move_data(battle, selected_slot) else {
        return BattleMoveResolution { hit: false, critical: false, damage: 0 };
    };
    battle.opponent_move_slot = Some(selected_slot as u8);
    battle.opponent_move_name = move_data.name.to_owned();
    if let Some(move_slot) = battle.opponent_moves.get_mut(selected_slot) {
        // `ppreduce` runs on both successful and missed source moves.
        move_slot.pp = move_slot.pp.saturating_sub(1);
    }
    if !battle_accuracy_check(battle, move_data) {
        battle.opponent_turn_count = battle.opponent_turn_count.saturating_add(1);
        return BattleMoveResolution { hit: false, critical: false, damage: 0 };
    }
    if move_data.power == 0 {
        match move_data.name {
            "GROWL" => battle.player_attack_stage = (battle.player_attack_stage - 1).max(-6),
            "LEER" => battle.player_defense_stage = (battle.player_defense_stage - 1).max(-6),
            "STRING SHOT" => battle.player_speed_stage = (battle.player_speed_stage - 1).max(-6),
            _ => {}
        }
        battle.opponent_turn_count = battle.opponent_turn_count.saturating_add(1);
        return BattleMoveResolution { hit: true, critical: false, damage: 0 };
    }
    let critical = battle_critical_check(battle);
    let damage = apply_battle_damage_variance(battle, opponent_battle_damage_for(battle, move_data, critical));
    battle.last_move_critical = critical;
    battle.opponent_turn_count = battle.opponent_turn_count.saturating_add(1);
    BattleMoveResolution { hit: true, critical, damage }
}

fn resolved_move_text(actor: &str, move_name: &str, resolution: BattleMoveResolution) -> String {
    if !resolution.hit {
        format!("{actor} used {move_name}, but it missed!")
    } else if resolution.critical {
        format!("{actor} used {move_name}! A critical hit!")
    } else {
        format!("{actor} used {move_name}.")
    }
}

fn rival_trainer_name(player_gender: PlayerGender) -> &'static str {
    match player_gender {
        PlayerGender::Brendan => "MAY",
        PlayerGender::May => "BRENDAN",
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct TilePosition { pub x: i16, pub y: i16 }

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct NpcState {
    pub id: String,
    pub map: MapId,
    pub position: TilePosition,
    pub facing: Facing,
}

/// Start frame for the most recent successful ambient object-event step.
/// This is kept beside map state (rather than inferred from facing) so a
/// blocked movement attempt turns in place without rendering a false walk.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct NpcWalkStart {
    pub id: String,
    pub frame: u64,
    /// Source object-event duration. Ordinary walks use 16 frames while the
    /// Route 101 chase's `walk_fast_*` commands use 8.
    #[serde(default = "default_npc_walk_duration")]
    pub duration_frames: u8,
    /// The source OBJ animation direction can survive a completed movement
    /// even after the ObjectEvent turns to face a different direction.
    #[serde(default)]
    pub sprite_facing: Option<Facing>,
    /// `walk_in_place_*` advances the source sprite cadence without moving
    /// its object-event coordinate.  Retain that distinction so the OBJ
    /// layer does not invent an eight- or four-pixel translation.
    #[serde(default)]
    pub in_place: bool,
}

fn default_npc_walk_duration() -> u8 { 16 }

/// Source `MOVEMENT_TYPE_WANDER_*` objects do not share a global cadence.
/// Each sprite first completes its facing action, waits for a separately
/// randomized delay, chooses a direction, and only then performs one walk.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub enum AmbientWanderMode {
    Face { remaining_frames: u8 },
    Delay { remaining_frames: u8 },
    Walk { remaining_frames: u8 },
    /// A frozen source checkpoint can begin mid-object-event. This retains a
    /// measured stable pose until the next EWRAM-proven scheduler boundary.
    MeasuredWait { release_frame: u64 },
}

/// Serialized progress for an ambient object-event. Keeping this in world
/// state makes a checkpoint resume the same object-event, rather than
/// re-phasing every resident from the transport request shape.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct AmbientWanderState {
    pub id: String,
    pub mode: AmbientWanderMode,
    /// A checkpoint can capture an object after its source scheduler has
    /// already selected a direction but before the 16-frame walk begins.
    /// Preserve that pending choice instead of asking a later replay request
    /// to re-roll it.
    #[serde(default)]
    pub pending_direction: Option<Facing>,
}

fn default_ambient_rng() -> u32 { 0x5eed_0001 }

fn default_starter_lab_choice_yes() -> bool { true }

fn default_starter_confirm_yes() -> bool { true }

fn default_naming_target() -> NamingTarget { NamingTarget::Player }

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct MapTransition {
    pub destination_map: MapId,
    pub destination: TilePosition,
    pub frames_remaining: u8,
    pub total_frames: u8,
    /// `false` fades the departing map out; `true` fades the arrived map in.
    pub fading_in: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct WorldState {
    pub map: MapId,
    pub phase: StoryPhase,
    /// Gameplay position in the authored map's coordinate space. For the
    /// frozen rival checkpoint this is Emerald's `ObjectEvent.currentCoords`
    /// minus `MAP_OFFSET`, not the separately fitted camera coordinate.
    pub player: TilePosition,
    /// Optional source-fitted terrain/camera coordinate. The rival exterior
    /// reference begins at logical `(8,17)` while its captured compositor is
    /// fitted at `(9,13)`; all ordinary maps render the gameplay position.
    #[serde(default)]
    pub render_position: Option<TilePosition>,
    pub elevation: u8,
    pub npcs: Vec<NpcState>,
    #[serde(default)]
    pub npc_walk_starts: Vec<NpcWalkStart>,
    #[serde(default)]
    pub ambient_wanders: Vec<AmbientWanderState>,
    /// Emerald's object-event movement types draw their delays and directions
    /// from the shared field RNG, not from a per-request scheduler tick.
    #[serde(default = "default_ambient_rng")]
    pub ambient_rng: u32,
    pub facing: Facing,
    pub menu_open: bool,
    pub menu_cursor: Option<u8>,
    pub menu_selection: Option<MenuEntry>,
    pub active_screen: Option<MenuEntry>,
    /// Cursor local to the currently open Start-menu application.  Keeping
    /// this separate from the field-menu cursor makes Bag, Options, and Save
    /// usable without changing the entry highlighted when the player returns
    /// to the field menu.
    #[serde(default)]
    pub active_screen_cursor: u8,
    /// Lightweight persistent settings exposed by the opening Options page.
    #[serde(default)]
    pub text_speed_fast: bool,
    #[serde(default)]
    pub battle_style_set: bool,
    /// The Save page records an explicit in-world save acknowledgement. This
    /// is intentionally game state, not a filesystem side effect.
    #[serde(default)]
    pub save_count: u16,
    /// Source Start-menu selections keep the field scene/menu visible through
    /// a short fade before the selected screen is installed.
    #[serde(default)]
    pub menu_transition_frames: Option<u8>,
    pub pokedex_cursor: u16,
    pub dialogue: Option<String>,
    pub clock_minutes: Option<u16>,
    pub clock_editing: Option<ClockField>,
    pub clock_confirming: bool,
    pub clock_confirm_yes: bool,
    /// The source wall-clock script first displays its stopped-clock message
    /// before it hands control to `StartWallClock`.
    #[serde(default)]
    pub clock_prompt_active: bool,
    /// Active source OAM settling state for the AM/PM period badges.
    #[serde(default)]
    pub clock_period_transition: Option<ClockPeriodTransition>,
    pub pending_running_shoes: bool,
    /// Source frames before Mom's initial Running Shoes `Wait` box accepts a
    /// dismiss input. The trigger frame itself is not a valid close.
    #[serde(default)]
    pub running_shoes_wait_frames: Option<u8>,
    /// Remaining frames in Mom's scripted approach before the item dialogue.
    pub running_shoes_frames: Option<u16>,
    /// After the eligible Running Shoes return path reaches the home door,
    /// source waits for open, Mom's one upward entry stride, and close.
    #[serde(default)]
    pub running_shoes_return_door_frames: Option<u16>,
    /// `LittlerootTown_EventScript_GiveRunningShoes` waits `delay 30` after
    /// Mom's final page, before it starts the selected `MomReturnHome*`
    /// movement stream.
    #[serde(default)]
    pub running_shoes_return_delay_frames: Option<u8>,
    /// True once Mom's item message has been presented in the current scene.
    pub running_shoes_item_shown: bool,
    /// Source Running Shoes scene state: approach, item pages, and return.
    #[serde(default)]
    pub running_shoes_stage: u8,
    /// Current two-line source message page within the active Running Shoes
    /// stage. The field engine only advances the stage after its final page.
    #[serde(default)]
    pub running_shoes_dialogue_page: u8,
    /// Remaining source frames while the current Running Shoes page prints.
    /// A request that reaches zero is still consumed by the text engine.
    #[serde(default)]
    pub running_shoes_dialogue_frames: Option<u16>,
    #[serde(default)]
    pub running_shoes_trigger: Option<u8>,
    /// Remaining frames in the source Little Root Twin warning gesture before
    /// its Route 101 prompt opens.
    #[serde(default)]
    pub birch_prompt_frames: Option<u16>,
    /// The warning prompt has opened and must be dismissed before the Route
    /// 101 connection is available.
    #[serde(default)]
    pub birch_prompt_active: bool,
    /// Mirrors `VAR_LITTLEROOT_TOWN_STATE = 2` after the Twin prompt closes.
    #[serde(default)]
    pub birch_prompt_complete: bool,
    /// State for the pre-rival source gate at Little Root `(10|11, 1)`.
    /// Stages are Twin approach, player pushback, and Twin return.
    #[serde(default)]
    pub no_pokemon_gate_frames: Option<u16>,
    #[serde(default)]
    pub no_pokemon_gate_stage: u8,
    #[serde(default)]
    pub no_pokemon_gate_right: bool,
    /// Route101_EventScript_StartBirchRescue staged chase state.
    #[serde(default)]
    pub birch_rescue_frames: Option<u16>,
    #[serde(default)]
    pub birch_rescue_stage: u8,
    /// `Route101_EventScript_BirchsBag` waits for Birch's one-tile normal
    /// approach after the starter battle before opening his rescue dialogue.
    #[serde(default)]
    pub birch_post_battle_frames: Option<u8>,
    /// Route103 rival face/exclamation/delay sequence before its challenge.
    #[serde(default)]
    pub route103_rival_intro_frames: Option<u16>,
    #[serde(default)]
    pub route103_rival_intro_stage: u8,
    /// Captures `VAR_FACING` when Route103_EventScript_RivalExit begins so
    /// scripted player turns cannot change which exit branch is running.
    #[serde(default)]
    pub route103_rival_departure_facing: Option<Facing>,
    /// `PlayerEnterLabForPokedex`: seven northward steps after Route 103.
    #[serde(default)]
    pub pokedex_arrival_frames: Option<u16>,
    /// Rival's approach after Birch explains the Pokédex.
    #[serde(default)]
    pub pokedex_rival_frames: Option<u16>,
    /// Remaining source frames in `EventScript_ReceivePokedex`'s
    /// `MUS_OBTAIN_ITEM` receipt fanfare.
    #[serde(default)]
    pub pokedex_receipt_fanfare_frames: Option<u16>,
    /// Remaining source frames in the rival's `giveitem ITEM_POKE_BALL, 5`
    /// obtain-item fanfare.
    #[serde(default)]
    pub pokedex_poke_ball_fanfare_frames: Option<u16>,
    /// The fanfare has opened the source's pocket receipt; its close begins
    /// Birch's following catch-explanation message.
    #[serde(default)]
    pub pokedex_poke_ball_pocket_receipt: bool,
    /// Direction of a Route 101 rescue-time exit guard after its message.
    #[serde(default)]
    pub route101_exit_push: Option<Facing>,
    /// The source's deterministic Wurmple encounter has been escaped, so its
    /// collision boundary cannot immediately open the same battle again.
    #[serde(default)]
    pub route101_wurmple_resolved: bool,
    /// The pre-Oldale Zigzagoon encounter from the 03_birch source path is
    /// resolved and must not retrigger when the player remains in its grass.
    #[serde(default)]
    pub route101_poochyena_resolved: bool,
    /// The source Route 103 Wingull encounter is resolved and must not
    /// retrigger when the player remains in the eastern grass.
    #[serde(default)]
    pub route103_wingull_resolved: bool,
    pub pending_rival_meeting: bool,
    /// Remaining source-script frames before the rival arrival dialogue opens.
    pub rival_arrival_frames: Option<u16>,
    /// Remaining Route 103 rival departure frames after the authored
    /// post-battle dialogue. Input remains locked while the rival walks and
    /// jumps down the southern ledge.
    #[serde(default)]
    pub rival_departure_frames: Option<u16>,
    /// Remaining frames in Oldale's post-Route-103 rival exit script.
    #[serde(default)]
    pub oldale_rival_departure_frames: Option<u16>,
    /// Oldale's south-edge rival approach runs before its homeward message.
    /// The three source triggers use zero, one, or two leftward strides,
    /// followed by the player's four-frame faster right turn.
    #[serde(default)]
    pub oldale_rival_approach_frames: Option<u8>,
    /// Remaining frames in the Oldale Mart employee's guided walk to the
    /// storefront after the introductory invitation closes.
    #[serde(default)]
    pub oldale_mart_scene_frames: Option<u16>,
    /// Script stage for `OldaleTown_EventScript_MartEmployee`.
    #[serde(default)]
    pub oldale_mart_scene_stage: u8,
    /// Player-facing branch selected by the Mart employee script.
    #[serde(default)]
    pub oldale_mart_scene_route: Option<Facing>,
    /// Remaining frames while the current Oldale Mart invitation page prints.
    #[serde(default)]
    pub oldale_mart_dialogue_frames: Option<u16>,
    /// Active source message page within the Oldale Mart script.
    #[serde(default)]
    pub oldale_mart_dialogue_page: u8,
    /// Remaining source frames in `giveitem ITEM_POTION`'s obtain-item
    /// fanfare. It runs concurrently with the initial obtained-item text.
    #[serde(default)]
    pub oldale_mart_item_fanfare_frames: Option<u16>,
    /// Remaining frames while a regular overworld message prints. Story
    /// scripts with their own message sequencing retain dedicated clocks.
    #[serde(default)]
    pub field_dialogue_frames: Option<u16>,
    /// Remaining frames in the post-clock upstairs entry, including the
    /// player's final fast in-place turn before Mom's message opens.
    pub clock_visit_frames: Option<u16>,
    /// `PlayersHouse_2F_EventScript_WallClock` waits thirty frames after the
    /// clock editor closes before it creates Mom's upstairs object event.
    #[serde(default)]
    pub clock_settle_frames: Option<u8>,
    /// Remaining source frames after the downstairs OnFrame event starts and
    /// before Mom opens the first Petalburg Gym broadcast message.
    #[serde(default)]
    pub tv_broadcast_intro_frames: Option<u16>,
    /// Little Root rival-house OnFrame sequence: Mom's exclamation, Delay48,
    /// and six-step approach before the new-neighbor greeting.
    #[serde(default)]
    pub rival_mom_intro_frames: Option<u16>,
    /// The independent 60-frame source field-effect lifetime for Mom's
    /// exclamation icon; it overlaps the tail of Delay48 and her first walk.
    #[serde(default)]
    pub rival_mom_exclamation_frames: Option<u8>,
    /// Remaining source frames in `PlayerApproachTVForGym{Male,Female}`.
    /// The locked five-step stream runs after Mom's first report message and
    /// before `MaybeDadWillBeOn` opens.
    #[serde(default)]
    pub tv_broadcast_approach_frames: Option<u16>,
    /// Remaining source frames after `MaybeDadWillBeOn` closes: Mom makes
    /// room, then the player moves to and faces the television before the
    /// report message opens.
    #[serde(default)]
    pub tv_broadcast_view_frames: Option<u16>,
    /// `TurnOffTVScreen` replaces every television metatile immediately
    /// after the Petalburg Gym report message closes.
    #[serde(default = "default_tv_screen_on")]
    pub tv_screen_on: bool,
    /// Remaining frames in the source truck-arrival choreography before Mom
    /// opens her first Little Root dialogue. Input is locked throughout.
    #[serde(default)]
    pub truck_arrival_frames: Option<u16>,
    /// Remaining frames while the active Little Root truck-arrival page
    /// prints. The source accepts page dismissal only after this completes.
    #[serde(default)]
    pub truck_arrival_dialogue_frames: Option<u16>,
    #[serde(default)]
    pub truck_departure_frames: Option<u16>,
    /// The post-page-one movement gate after Mom immediately faces the
    /// player and before the player's fast turn completes.
    #[serde(default)]
    pub new_home_orientation_frames: Option<u8>,
    #[serde(default)]
    pub new_home_arrival_frames: Option<u16>,
    pub transition: Option<MapTransition>,
    pub walk_progress_frames: u8,
    /// Physical frames accumulated toward the next map-tile commit. This is
    /// intentionally distinct from `walk_progress_frames`: Emerald commits
    /// the field coordinate at each 16-frame boundary while the renderer
    /// still displays the just-completed stride.
    #[serde(default)]
    pub walk_elapsed_frames: u8,
    pub walk_direction: Option<Facing>,
    #[serde(default)]
    pub camera_handoff_from: Option<Facing>,
    /// The prior tile whose terrain/camera remains visible during the final
    /// fifteen pixels of a committed stride.
    #[serde(default)]
    pub walk_render_origin: Option<TilePosition>,
    pub running: bool,
    /// The source run animation switches feet after each eight-frame stride.
    /// This affects only player rendering; `walk_bounds` retains field logic.
    #[serde(default)]
    pub running_step_uses_second_foot: bool,
    pub starter: Option<StarterSpecies>,
    /// The source's gPlayerParty[0] projection for the opening starter.
    /// Older snapshots lazily construct it from the selected starter.
    #[serde(default)]
    pub starter_party: Option<StarterPartyState>,
    /// Elapsed frames of `sAffineAnim_StarterPokemon` / `StarterCircle`.
    /// `None` is the ordinary selector or post-reveal confirmation state.
    #[serde(default)]
    pub starter_reveal_frames: Option<u8>,
    /// The `SpriteCB_SelectionHand` sine-table index. The source advances it
    /// by four every rendered frame while Birch's chooser is active.
    #[serde(default)]
    pub starter_hand_phase: u8,
    /// Elapsed frame in the selected Poké Ball's 128-frame
    /// `sAnim_Pokeball_Moving` loop. This is intentionally separate from
    /// the hand's 64-frame sine phase: the source objects advance on the
    /// same video tick, but their loop lengths differ.
    #[serde(default)]
    pub starter_pokeball_animation_frame: u8,
    /// `Task_HandleConfirmStarterInput` starts its standard menu on YES.
    /// Kept separately from Birch Lab's later YES/NO branches so a declined
    /// Poké Ball returns to the bounded three-ball selector unchanged.
    #[serde(default = "default_starter_confirm_yes")]
    pub starter_confirm_yes: bool,
    /// Cursor state for Birch's Lab `GoSeeRival` / decline YES-NO branches.
    /// Old checkpoints predate the interactive menu and therefore resume on
    /// its source-default YES option.
    #[serde(default = "default_starter_lab_choice_yes")]
    pub starter_lab_choice_yes: bool,
    /// Persistent opening progression awarded by Birch's Lab script.
    pub has_pokedex: bool,
    pub poke_balls: u8,
    /// Opening-item inventory granted by the Oldale Mart employee.
    #[serde(default)]
    pub potions: u8,
    /// `VAR_OLDALE_RIVAL_STATE == 2` / `FLAG_HIDE_OLDALE_TOWN_RIVAL`.
    #[serde(default)]
    pub oldale_rival_departed: bool,
    /// `FLAG_BIRCH_AIDE_MET`, used by the Lab aide's first interaction.
    #[serde(default)]
    pub birch_aide_met: bool,
    pub battle: Option<BattleState>,
    /// Consecutive title-screen A frames accepted by the source gate.
    pub title_start_frames: u8,
    /// Idle frames elapsed after the captured title fade.
    pub title_transition_frames: u16,
    /// Current page in the Professor Birch introduction script.
    pub title_intro_step: u8,
    /// Frames elapsed while the current introduction page is printing.
    pub title_intro_frames: u16,
    pub player_name: String,
    pub name_cursor: u8,
    /// Player and starter nickname screens share keyboard state, but write to
    /// the same fields their source naming-screen callbacks own.
    #[serde(default = "default_naming_target")]
    pub naming_target: NamingTarget,
    /// Input buffer for `NAMING_SCREEN_NICKNAME`. The source leaves the
    /// original species name intact when this remains empty.
    #[serde(default)]
    pub starter_nickname_entry: String,
    pub player_gender: PlayerGender,
    pub gender_selection_touched: bool,
    /// Birch-speech selector transition: outgoing sprite slides right, then
    /// the replacement slides in from the right while input is locked.
    pub gender_transition: Option<GenderTransition>,
    pub name_entry_touched: bool,
    /// Source `Task_UpdateButtonFlash` state for the naming action column.
    /// Older snapshots predate the fidelity pass and start at the static
    /// source palette until an action button is selected.
    #[serde(default)]
    pub naming_action_button_pulse: Option<NamingActionButtonPulse>,
    /// Frames since the naming screen opened; its input grid is not ready immediately.
    pub name_entry_ready_frames: u32,
    /// Whether the name keyboard is showing its lowercase/effect character page.
    pub name_entry_lowercase: bool,
    /// Selected answer in the source's post-name YES/NO confirmation menu.
    pub name_confirm_yes: bool,
    /// The naming keyboard remains visible for the confirming input frame;
    /// the source opens the YES/NO page on the following video update.
    #[serde(default)]
    pub name_confirm_transition_frames: Option<u16>,
    pub frame: u64,
}

impl WorldState {
    pub fn title_menu() -> Self {
        Self {
            map: MapId::TitleScreen,
            phase: StoryPhase::Title,
            player: TilePosition { x: 0, y: 0 },
            render_position: None,
            elevation: 0,
            npcs: Vec::new(),
            npc_walk_starts: Vec::new(),
            ambient_wanders: Vec::new(),
            ambient_rng: default_ambient_rng(),
            facing: Facing::Down,
            menu_open: false,
            menu_cursor: None,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            pokedex_cursor: 0,
            dialogue: None,
            clock_minutes: None,
            clock_editing: None,
            clock_confirming: false,
            clock_confirm_yes: true,
            clock_prompt_active: false,
            clock_period_transition: None,
            pending_running_shoes: false,
            running_shoes_wait_frames: None,
            running_shoes_frames: None,
            running_shoes_return_door_frames: None,
            running_shoes_return_delay_frames: None,
            running_shoes_item_shown: false,
            running_shoes_stage: 0,
            running_shoes_dialogue_page: 0,
            running_shoes_dialogue_frames: None,
            running_shoes_trigger: None,
            birch_prompt_frames: None,
            birch_prompt_active: false,
            birch_prompt_complete: false,
            no_pokemon_gate_frames: None,
            no_pokemon_gate_stage: 0,
            no_pokemon_gate_right: false,
            birch_rescue_frames: None,
            birch_rescue_stage: 0,
            birch_post_battle_frames: None,
            route103_rival_intro_frames: None,
            route103_rival_intro_stage: 0,
            route103_rival_departure_facing: None,
            pokedex_arrival_frames: None,
            pokedex_rival_frames: None,
            pokedex_receipt_fanfare_frames: None,
            pokedex_poke_ball_fanfare_frames: None,
            pokedex_poke_ball_pocket_receipt: false,
            route101_exit_push: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_rival_approach_frames: None,
            oldale_mart_scene_frames: None,
            oldale_mart_scene_stage: 0,
            oldale_mart_scene_route: None,
            oldale_mart_dialogue_frames: None,
            oldale_mart_dialogue_page: 0,
            oldale_mart_item_fanfare_frames: None,
            field_dialogue_frames: None,
            clock_visit_frames: None,
            clock_settle_frames: None,
            tv_broadcast_intro_frames: None,
            rival_mom_intro_frames: None,
            rival_mom_exclamation_frames: None,
            tv_broadcast_approach_frames: None,
            tv_broadcast_view_frames: None,
            tv_screen_on: true,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            camera_handoff_from: None,
            walk_render_origin: None,
            running: false,
            running_step_uses_second_foot: false,
            starter: None,
            starter_party: None,
            starter_reveal_frames: None,
            starter_hand_phase: 0,
            starter_pokeball_animation_frame: 0,
            starter_confirm_yes: true,
            starter_lab_choice_yes: true,
            has_pokedex: false,
            poke_balls: 0,
            potions: 0,
            oldale_rival_departed: false,
            birch_aide_met: false,
            battle: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: String::new(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            // Emerald's captured selector starts on BOY (Brendan).
            player_gender: PlayerGender::Brendan,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    pub fn truck_arrival() -> Self {
        Self {
            map: MapId::MovingTruck,
            phase: StoryPhase::IntroTruck,
            // InsideOfTruck's three exit triggers are at (3, 1..=3), with
            // the right-hand warp tiles at x=4. The viewport is offset when
            // rendered, but gameplay coordinates remain the authored 5×5.
            player: TilePosition { x: 3, y: 2 },
            render_position: None,
            elevation: 0,
            npcs: Vec::new(),
            npc_walk_starts: Vec::new(),
            ambient_wanders: Vec::new(),
            ambient_rng: default_ambient_rng(),
            facing: Facing::Down,
            menu_open: false,
            menu_cursor: None,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            pokedex_cursor: 0,
            dialogue: None,
            clock_minutes: None,
            clock_editing: None,
            clock_confirming: false,
            clock_confirm_yes: true,
            clock_prompt_active: false,
            clock_period_transition: None,
            pending_running_shoes: false,
            running_shoes_wait_frames: None,
            running_shoes_frames: None,
            running_shoes_return_door_frames: None,
            running_shoes_return_delay_frames: None,
            running_shoes_item_shown: false,
            running_shoes_stage: 0,
            running_shoes_dialogue_page: 0,
            running_shoes_dialogue_frames: None,
            running_shoes_trigger: None,
            birch_prompt_frames: None,
            birch_prompt_active: false,
            birch_prompt_complete: false,
            no_pokemon_gate_frames: None,
            no_pokemon_gate_stage: 0,
            no_pokemon_gate_right: false,
            birch_rescue_frames: None,
            birch_rescue_stage: 0,
            birch_post_battle_frames: None,
            route103_rival_intro_frames: None,
            route103_rival_intro_stage: 0,
            route103_rival_departure_facing: None,
            pokedex_arrival_frames: None,
            pokedex_rival_frames: None,
            pokedex_receipt_fanfare_frames: None,
            pokedex_poke_ball_fanfare_frames: None,
            pokedex_poke_ball_pocket_receipt: false,
            route101_exit_push: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_rival_approach_frames: None,
            oldale_mart_scene_frames: None,
            oldale_mart_scene_stage: 0,
            oldale_mart_scene_route: None,
            oldale_mart_dialogue_frames: None,
            oldale_mart_dialogue_page: 0,
            oldale_mart_item_fanfare_frames: None,
            field_dialogue_frames: None,
            clock_visit_frames: None,
            clock_settle_frames: None,
            tv_broadcast_intro_frames: None,
            rival_mom_intro_frames: None,
            rival_mom_exclamation_frames: None,
            tv_broadcast_approach_frames: None,
            tv_broadcast_view_frames: None,
            tv_screen_on: true,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            camera_handoff_from: None,
            walk_render_origin: None,
            running: false,
            running_step_uses_second_foot: false,
            starter: None,
            starter_party: None,
            starter_reveal_frames: None,
            starter_hand_phase: 0,
            starter_pokeball_animation_frame: 0,
            starter_confirm_yes: true,
            starter_lab_choice_yes: true,
            has_pokedex: false,
            poke_balls: 0,
            potions: 0,
            oldale_rival_departed: false,
            birch_aide_met: false,
            battle: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: "CASEY".to_owned(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            // The supplied tutorial and downstream source saves use the
            // female player branch: May's House is the player's home.
            player_gender: PlayerGender::May,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    pub fn bedroom_idle() -> Self {
        Self {
            map: MapId::MaysHouse2F,
            // The staged source state is already upstairs after Mom's
            // moving-in dialogue. Its first actionable script is the wall
            // clock, so ordinary A input elsewhere must remain idle.
            phase: StoryPhase::ClockSet,
            // The 02_starter reference's stitched map identifies this as
            // May's upstairs bedroom at the authored [1, 1] spawn tile.
            player: TilePosition { x: 1, y: 1 },
            render_position: None,
            elevation: 3,
            npcs: Vec::new(),
            npc_walk_starts: Vec::new(),
            ambient_wanders: Vec::new(),
            ambient_rng: default_ambient_rng(),
            facing: Facing::Down,
            menu_open: false,
            menu_cursor: None,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            pokedex_cursor: 0,
            dialogue: None,
            clock_minutes: None,
            clock_editing: None,
            clock_confirming: false,
            clock_confirm_yes: true,
            clock_prompt_active: false,
            clock_period_transition: None,
            pending_running_shoes: false,
            running_shoes_wait_frames: None,
            running_shoes_frames: None,
            running_shoes_return_door_frames: None,
            running_shoes_return_delay_frames: None,
            running_shoes_item_shown: false,
            running_shoes_stage: 0,
            running_shoes_dialogue_page: 0,
            running_shoes_dialogue_frames: None,
            running_shoes_trigger: None,
            birch_prompt_frames: None,
            birch_prompt_active: false,
            birch_prompt_complete: false,
            no_pokemon_gate_frames: None,
            no_pokemon_gate_stage: 0,
            no_pokemon_gate_right: false,
            birch_rescue_frames: None,
            birch_rescue_stage: 0,
            birch_post_battle_frames: None,
            route103_rival_intro_frames: None,
            route103_rival_intro_stage: 0,
            route103_rival_departure_facing: None,
            pokedex_arrival_frames: None,
            pokedex_rival_frames: None,
            pokedex_receipt_fanfare_frames: None,
            pokedex_poke_ball_fanfare_frames: None,
            pokedex_poke_ball_pocket_receipt: false,
            route101_exit_push: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_rival_approach_frames: None,
            oldale_mart_scene_frames: None,
            oldale_mart_scene_stage: 0,
            oldale_mart_scene_route: None,
            oldale_mart_dialogue_frames: None,
            oldale_mart_dialogue_page: 0,
            oldale_mart_item_fanfare_frames: None,
            field_dialogue_frames: None,
            clock_visit_frames: None,
            clock_settle_frames: None,
            tv_broadcast_intro_frames: None,
            rival_mom_intro_frames: None,
            rival_mom_exclamation_frames: None,
            tv_broadcast_approach_frames: None,
            tv_broadcast_view_frames: None,
            tv_screen_on: true,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            camera_handoff_from: None,
            walk_render_origin: None,
            running: false,
            running_step_uses_second_foot: false,
            starter: None,
            starter_party: None,
            starter_reveal_frames: None,
            starter_hand_phase: 0,
            starter_pokeball_animation_frame: 0,
            starter_confirm_yes: true,
            starter_lab_choice_yes: true,
            has_pokedex: false,
            poke_balls: 0,
            potions: 0,
            oldale_rival_departed: false,
            birch_aide_met: false,
            battle: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: "CASEY".to_owned(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            player_gender: PlayerGender::May,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    pub fn birch_lab_exterior() -> Self {
        Self {
            map: MapId::LittlerootTown,
            phase: StoryPhase::BirchRescued,
            // Live 03_birch EWRAM entry 0 reports ObjectEvent.currentCoords
            // `(14,24)`. Emerald's field map stores those coordinates with
            // `MAP_OFFSET = 7`, yielding the authored Little Root spawn.
            player: TilePosition { x: 7, y: 17 },
            render_position: None,
            elevation: 3,
            npcs: littleroot_town_npcs(StoryPhase::BirchRescued, PlayerGender::May),
            npc_walk_starts: Vec::new(),
            ambient_wanders: Vec::new(),
            ambient_rng: default_ambient_rng(),
            facing: Facing::Down,
            menu_open: false,
            menu_cursor: None,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            pokedex_cursor: 0,
            dialogue: None,
            clock_minutes: Some(720),
            clock_editing: None,
            clock_confirming: false,
            clock_confirm_yes: true,
            clock_prompt_active: false,
            clock_period_transition: None,
            pending_running_shoes: false,
            running_shoes_wait_frames: None,
            running_shoes_frames: None,
            running_shoes_return_door_frames: None,
            running_shoes_return_delay_frames: None,
            running_shoes_item_shown: false,
            running_shoes_stage: 0,
            running_shoes_dialogue_page: 0,
            running_shoes_dialogue_frames: None,
            running_shoes_trigger: None,
            birch_prompt_frames: None,
            birch_prompt_active: false,
            birch_prompt_complete: false,
            no_pokemon_gate_frames: None,
            no_pokemon_gate_stage: 0,
            no_pokemon_gate_right: false,
            birch_rescue_frames: None,
            birch_rescue_stage: 0,
            birch_post_battle_frames: None,
            route103_rival_intro_frames: None,
            route103_rival_intro_stage: 0,
            route103_rival_departure_facing: None,
            pokedex_arrival_frames: None,
            pokedex_rival_frames: None,
            pokedex_receipt_fanfare_frames: None,
            pokedex_poke_ball_fanfare_frames: None,
            pokedex_poke_ball_pocket_receipt: false,
            route101_exit_push: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_rival_approach_frames: None,
            oldale_mart_scene_frames: None,
            oldale_mart_scene_stage: 0,
            oldale_mart_scene_route: None,
            oldale_mart_dialogue_frames: None,
            oldale_mart_dialogue_page: 0,
            oldale_mart_item_fanfare_frames: None,
            field_dialogue_frames: None,
            clock_visit_frames: None,
            clock_settle_frames: None,
            tv_broadcast_intro_frames: None,
            rival_mom_intro_frames: None,
            rival_mom_exclamation_frames: None,
            tv_broadcast_approach_frames: None,
            tv_broadcast_view_frames: None,
            tv_screen_on: true,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            camera_handoff_from: None,
            walk_render_origin: None,
            running: false,
            running_step_uses_second_foot: false,
            starter: Some(StarterSpecies::Treecko),
            starter_party: None,
            starter_reveal_frames: None,
            starter_hand_phase: 0,
            starter_pokeball_animation_frame: 0,
            starter_confirm_yes: true,
            starter_lab_choice_yes: true,
            has_pokedex: false,
            poke_balls: 0,
            potions: 0,
            oldale_rival_departed: false,
            birch_aide_met: false,
            battle: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: "CASEY".to_owned(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            player_gender: PlayerGender::May,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    pub fn rival_outside_birch_lab() -> Self {
        let mut npcs = littleroot_town_npcs(StoryPhase::PokedexReceived, PlayerGender::May);
        // `04_rival.state` is not a freshly entered town: EWRAM
        // `ObjectEvent.currentCoords` proves the source residents have
        // already wandered away from their template home tiles. Keep those
        // live coordinates in gameplay space (raw map coordinates minus the
        // source `MAP_OFFSET = 7`) so collision and later dynamic OAM share
        // the same origin as the checkpoint.
        for npc in &mut npcs {
            match npc.id.as_str() {
                "twin" => {
                    npc.position = TilePosition { x: 16, y: 10 };
                    npc.facing = Facing::Down;
                }
                "fat_man" => {
                    npc.position = TilePosition { x: 13, y: 14 };
                    npc.facing = Facing::Down;
                }
                "boy" => {
                    npc.position = TilePosition { x: 16, y: 17 };
                    npc.facing = Facing::Down;
                }
                _ => {}
            }
        }
        Self {
            map: MapId::LittlerootTown,
            phase: StoryPhase::PokedexReceived,
            // EWRAM `ObjectEvent.currentCoords` is `(15,24)` here. Emerald
            // stores map-grid coordinates with `MAP_OFFSET = 7`, so gameplay
            // begins at authored `(8,17)`.
            player: TilePosition { x: 8, y: 17 },
            // The source-fitted native compositor keeps its distinct camera
            // pose while logical movement and collision use the map grid.
            render_position: Some(TilePosition { x: 9, y: 13 }),
            elevation: 3,
            npcs,
            npc_walk_starts: Vec::new(),
            ambient_wanders: Vec::new(),
            ambient_rng: default_ambient_rng(),
            // The source checkpoint is captured with the player facing right.
            // Keeping that pose makes the initial native compositor reproduce
            // the idle Little Root reference before any directional input.
            facing: Facing::Right,
            menu_open: false,
            menu_cursor: None,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            pokedex_cursor: 0,
            dialogue: None,
            clock_minutes: Some(720),
            clock_editing: None,
            clock_confirming: false,
            clock_confirm_yes: true,
            clock_prompt_active: false,
            clock_period_transition: None,
            pending_running_shoes: false,
            running_shoes_wait_frames: None,
            running_shoes_frames: None,
            running_shoes_return_door_frames: None,
            running_shoes_return_delay_frames: None,
            running_shoes_item_shown: false,
            running_shoes_stage: 0,
            running_shoes_dialogue_page: 0,
            running_shoes_dialogue_frames: None,
            running_shoes_trigger: None,
            birch_prompt_frames: None,
            birch_prompt_active: false,
            birch_prompt_complete: false,
            no_pokemon_gate_frames: None,
            no_pokemon_gate_stage: 0,
            no_pokemon_gate_right: false,
            birch_rescue_frames: None,
            birch_rescue_stage: 0,
            birch_post_battle_frames: None,
            route103_rival_intro_frames: None,
            route103_rival_intro_stage: 0,
            route103_rival_departure_facing: None,
            pokedex_arrival_frames: None,
            pokedex_rival_frames: None,
            pokedex_receipt_fanfare_frames: None,
            pokedex_poke_ball_fanfare_frames: None,
            pokedex_poke_ball_pocket_receipt: false,
            route101_exit_push: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_rival_approach_frames: None,
            oldale_mart_scene_frames: None,
            oldale_mart_scene_stage: 0,
            oldale_mart_scene_route: None,
            oldale_mart_dialogue_frames: None,
            oldale_mart_dialogue_page: 0,
            oldale_mart_item_fanfare_frames: None,
            field_dialogue_frames: None,
            clock_visit_frames: None,
            clock_settle_frames: None,
            tv_broadcast_intro_frames: None,
            rival_mom_intro_frames: None,
            rival_mom_exclamation_frames: None,
            tv_broadcast_approach_frames: None,
            tv_broadcast_view_frames: None,
            tv_screen_on: true,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            camera_handoff_from: None,
            walk_render_origin: None,
            running: false,
            running_step_uses_second_foot: false,
            starter: Some(StarterSpecies::Treecko),
            starter_party: None,
            starter_reveal_frames: None,
            starter_hand_phase: 0,
            starter_pokeball_animation_frame: 0,
            starter_confirm_yes: true,
            starter_lab_choice_yes: true,
            has_pokedex: true,
            poke_balls: 5,
            potions: 0,
            oldale_rival_departed: false,
            birch_aide_met: false,
            battle: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: "CASEY".to_owned(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            player_gender: PlayerGender::May,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    pub fn route101_rescue() -> Self {
        let mut world = Self::rival_outside_birch_lab();
        world.map = MapId::Route101;
        world.phase = StoryPhase::BirchRescue;
        // The north Little Root connection delivers the source scene into
        // Route 101's authored x=10 lane. `StartBirchRescue` then owns the
        // four fast northward player strides from this south-edge tile.
        world.player = TilePosition { x: 10, y: 19 };
        world.render_position = None;
        world.elevation = crate::native::tile_elevation(world.map, world.player.x, world.player.y)
            .expect("Route 101 rescue start must be on staged terrain");
        world.facing = Facing::Up;
        world.starter = None;
        world.has_pokedex = false;
        world.poke_balls = 0;
        world.npcs = route101_npcs(world.phase);
        world.dialogue = Some("H-help me!".to_owned());
        world
    }

    pub fn route103_rival() -> Self {
        let mut world = Self::rival_outside_birch_lab();
        world.map = MapId::Route103;
        world.phase = StoryPhase::StarterChosen;
        world.player = TilePosition { x: 10, y: 4 };
        world.render_position = None;
        world.elevation = crate::native::tile_elevation(world.map, world.player.x, world.player.y)
            .expect("Route 103 rival start must be on staged terrain");
        world.facing = Facing::Up;
        world.starter = Some(StarterSpecies::Treecko);
        world.has_pokedex = false;
        world.poke_balls = 0;
        world.npcs = route103_npcs(world.phase);
        world.dialogue = None;
        world
    }

    pub fn running_shoes() -> Self {
        let mut world = Self::rival_outside_birch_lab();
        world.phase = StoryPhase::PokedexReceived;
        world.player = TilePosition { x: 7, y: 9 };
        world.render_position = None;
        world.elevation = crate::native::tile_elevation(world.map, world.player.x, world.player.y)
            .expect("running-shoes start must be on staged Littleroot terrain");
        world.facing = Facing::Right;
        world.npcs = littleroot_town_npcs(world.phase, world.player_gender);
        world.dialogue = None;
        world
    }

    pub fn checkpoint_json(&self) -> serde_json::Value {
        serde_json::json!({ "schema": "gamebench.checkpoint.pokemon_emerald_littleroot.v1", "world": self })
    }

    pub fn face(&mut self, facing: Facing) {
        self.facing = facing;
    }

    /// Starts a source-map object interaction for the tile in front of the
    /// player. Scripted story beats retain precedence when no object is there.
    pub fn interact_with_npc(&mut self) -> bool {
        if self.dialogue.is_some() { return false; }
        let (x, y) = match self.facing {
            Facing::Up => (self.player.x, self.player.y - 1),
            Facing::Down => (self.player.x, self.player.y + 1),
            Facing::Left => (self.player.x - 1, self.player.y),
            Facing::Right => (self.player.x + 1, self.player.y),
        };
        if self.phase == StoryPhase::BirchRescue
            && self.map == MapId::Route101
            && self.birch_rescue_stage == 3
            && (x, y) == (7, 14)
            && self.dialogue.is_none() {
            // Route101_EventScript_BirchsBag fades the scene, removes the
            // Zigzagoon, then fixes the player at (6,13) facing left before
            // `ChooseStarter` takes control. Keep that authored ordering in
            // the state layer even though the battle transition is not yet
            // pixel-staged.
            self.player = TilePosition { x: 6, y: 13 };
            self.elevation = crate::native::tile_elevation(self.map, 6, 13)
                .expect("Route 101 starter-selection tile must be staged");
            self.facing = Facing::Left;
            self.phase = StoryPhase::StarterSelect;
            // `CB2_ChooseStarter` owns its own UI rather than opening a
            // field message. Its task starts on selection index 1, which is
            // Torchic in Emerald's Treecko/Torchic/Mudkip table.
            self.starter = Some(StarterSpecies::Torchic);
            self.starter_reveal_frames = None;
            self.starter_hand_phase = 0;
            self.starter_pokeball_animation_frame = 0;
            self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
            return true;
        }
        if self.phase == StoryPhase::StarterChosen
            && self.map == MapId::Route103
            && (x, y) == (10, 3) {
            self.phase = StoryPhase::RivalBattle;
            self.title_intro_step = 0;
            self.begin_field_dialogue(rival_route103_observation(self.player_gender));
            return true;
        }
        if self.phase == StoryPhase::MeetRival && self.is_rival_pokeball(x, y) {
            self.pending_rival_meeting = true;
            // The 2F source script holds the doorway for ten frames before
            // creating the rival and immediately starting `*Enters`.
            self.rival_arrival_frames = Some(BEDROOM_RIVAL_ENTRY_FRAMES);
            return true;
        }
        if let Some(text) = self.house_background_text(x, y) {
            self.begin_field_dialogue(text.to_owned());
            return true;
        }
        let Some(npc) = self.npcs.iter_mut().find(|npc| npc.map == self.map && npc.position.x == x && npc.position.y == y) else {
            return false;
        };
        npc.facing = match self.facing {
            Facing::Up => Facing::Down,
            Facing::Down => Facing::Up,
            Facing::Left => Facing::Right,
            Facing::Right => Facing::Left,
        };
        let dialogue = match npc.id.as_str() {
            "twin" if self.phase >= StoryPhase::PokedexReceived => {
                "Are you going to catch POKéMON?\nGood luck!".to_owned()
            }
            "twin" if self.phase >= StoryPhase::BirchRescued => {
                "You saved PROF. BIRCH!\nI'm so glad!".to_owned()
            }
            "twin" if self.phase >= StoryPhase::MetRival => {
                "Um, hi!\n\nThere are scary POKéMON outside!\nI can hear their cries!\n\nI want to go see what's going on,\nbut I don't have any POKéMON…\n\nCan you go see what's happening\nfor me?".to_owned()
            }
            "twin" => "Um, um, um!\n\nIf you go outside and go in the grass,\nwild POKéMON will jump out!".to_owned(),
            "fat_man" => "If you use a PC, you can store items\nand POKéMON.\n\nThe power of science is staggering!".to_owned(),
            "boy" => "PROF. BIRCH spends days in his LAB\nstudying, then he'll suddenly go out in\nthe wild to do more research…\n\nWhen does PROF. BIRCH spend time\nat home?".to_owned(),
            "youngster" => "If POKéMON get tired, take them to\na POKéMON CENTER.\nThere's a POKéMON CENTER in OLDALE\nTOWN right close by.".to_owned(),
            "route101_boy" => "Wild POKéMON will jump out at you in\ntall grass.\nIf you want to catch POKéMON, you have\nto go into the tall grass and search.".to_owned(),
            "zigzagoon" => "ZIGZAGOON is circling PROF. BIRCH!".to_owned(),
            // Authored Oldale Town object-event text and the first stage of
            // the Mart employee's guided promotional-item script.
            "oldale_girl" => "I want to take a rest, so I'm saving my\nprogress.".to_owned(),
            "mart_employee" if self.potions == 0 => {
                self.oldale_mart_scene_stage = 1;
                self.oldale_mart_scene_route = Some(self.facing);
                self.oldale_mart_dialogue_frames = Some(16);
                self.oldale_mart_dialogue_page = 0;
                "Hi!\nI work at a POKéMON MART.".to_owned()
            }
            "mart_employee" => "A POTION can be used anytime, so it's\neven more useful than a POKéMON CENTER\nin certain situations.".to_owned(),
            // `FLAG_ADVENTURE_STARTED` is set by Birch only after the
            // Pokédex/Poké Ball handoff, not when the starter is chosen.
            "footprints_man" if self.phase >= StoryPhase::PokedexReceived => {
                "I finished sketching the footprints of\na rare POKéMON.\nBut it turns out they were only my\nown footprints…".to_owned()
            }
            "footprints_man" => "I just discovered the footprints of\na rare POKéMON!\nWait until I finish sketching\nthem, okay?".to_owned(),
            "oldale_rival" => match self.player_gender {
                PlayerGender::Brendan => format!("MAY: {}!\nOver here!\nLet's hurry home!", self.player_name),
                PlayerGender::May => format!("BRENDAN: I'm heading back to my dad's\nLAB now.\n{}, you should hustle back, too.", self.player_name),
            },
            "mom" => match self.phase {
                StoryPhase::NewHome => "MOM: Your room is upstairs. Go set the clock.".to_owned(),
                StoryPhase::PokedexReceived => "MOM: Be careful on your Pokémon journey!".to_owned(),
                _ => "MOM: We are so happy to be here in Littleroot.".to_owned(),
            },
            "aide" if self.phase >= StoryPhase::StarterChosen => {
                format!("PROF. BIRCH is studying the habitats\nand distribution of POKéMON.\n\nThe PROF enjoys {}'s help, too.\nThere's a lot of love there.", rival_name(self.player_gender))
            }
            "aide" if self.birch_aide_met => {
                "The PROF isn't one for doing desk work.\nHe's the type of person who would\nrather go outside and experience\nthings than read about them here.".to_owned()
            }
            "aide" => {
                self.birch_aide_met = true;
                "Hunh? PROF. BIRCH?\n\nThe PROF's away on fieldwork.\nErgo, he isn't here.\n\nOh, let me explain what fieldwork is.\n\nIt is to study things in the natural\nenvironment, like fields and mountains,\ninstead of a laboratory.\n\nThe PROF isn't one for doing desk work.\nHe's the type of person who would\nrather go outside and experience\nthings than read about them here.".to_owned()
            }
            "birch" if self.phase >= StoryPhase::PokedexReceived => {
                "PROF. BIRCH: Countless POKéMON\nawait you!\n\nArgh, I'm getting the itch to get out\nand do fieldwork again!".to_owned()
            }
            "birch" => format!("PROF. BIRCH: {}?\nGone home, I think.\n\nOr maybe that kid's scrabbling around\nin tall grass again somewhere…\n\nIf you or your POKéMON get tired,\nyou should get some rest at home.", rival_name(self.player_gender)),
            "rival" => match self.player_gender {
                PlayerGender::Brendan => "MAY: I wonder where I should go look\nfor POKéMON next…".to_owned(),
                PlayerGender::May => "BRENDAN: Where should I look for\nPOKéMON next…".to_owned(),
            },
            _ => return false,
        };
        if self.oldale_mart_dialogue_frames.is_some() {
            self.field_dialogue_frames = None;
            self.dialogue = Some(dialogue);
        } else {
            self.begin_field_dialogue(dialogue);
        }
        true
    }

    /// Starts a normal object/background field message. Emerald's text box
    /// has a lead-in before revealing one glyph per frame, so the message is
    /// not dismissible on the same input that opened it.
    fn begin_field_dialogue(&mut self, dialogue: String) {
        self.field_dialogue_frames = Some(dialogue_printer_duration(&dialogue));
        self.dialogue = Some(dialogue);
    }

    pub fn open_menu(&mut self) {
        if self.dialogue.is_none() {
            self.menu_open = true;
            self.menu_cursor = Some(0);
            self.menu_selection = None;
        }
    }

    pub fn close_menu(&mut self) {
        self.menu_open = false;
        self.menu_cursor = None;
    }

    pub fn move_menu_cursor(&mut self, delta: i8) {
        let count = self.menu_entries().len() as i8;
        let current = self.menu_cursor.unwrap_or(0) as i8;
        self.menu_cursor = Some((current + delta).rem_euclid(count) as u8);
    }

    pub fn choose_menu_entry(&mut self) {
        let cursor = self.menu_cursor.unwrap_or(0) as usize;
        self.menu_selection = self.menu_entries().get(cursor).copied();
        self.pokedex_cursor = 0;
        self.close_menu();
        if self.menu_selection == Some(MenuEntry::Exit) {
            self.active_screen = None;
            self.active_screen_cursor = 0;
            self.menu_transition_frames = None;
        } else {
            self.active_screen = None;
            self.active_screen_cursor = 0;
            self.menu_transition_frames = Some(60);
        }
    }

    pub fn close_active_screen(&mut self) {
        self.active_screen = None;
        self.active_screen_cursor = 0;
    }

    /// Advances the source-observed Start-menu fade. While it runs the menu
    /// remains visually present but input-locked; only completion opens the
    /// requested menu screen.
    pub fn advance_menu_transition(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.menu_transition_frames else { return false; };
        let next = remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if next == 0 {
            self.menu_transition_frames = None;
            self.active_screen = self.menu_selection.filter(|entry| *entry != MenuEntry::Exit);
            self.active_screen_cursor = 0;
        } else {
            self.menu_transition_frames = Some(next);
        }
        true
    }

    pub fn move_pokedex_cursor(&mut self, delta: i16) {
        if self.active_screen == Some(MenuEntry::Pokedex) {
            self.pokedex_cursor = (i16::try_from(self.pokedex_cursor).unwrap_or(0) + delta).clamp(0, 201) as u16;
        }
    }

    /// Navigate the focused Start-menu application.  The real game gives
    /// each page its own cursor state; this compact opening slice keeps the
    /// same property for the pages which are reachable before Petalburg.
    pub fn move_active_screen_cursor(&mut self, delta: i8) {
        match self.active_screen {
            Some(MenuEntry::Pokedex) => self.move_pokedex_cursor(i16::from(delta)),
            Some(MenuEntry::Bag) => {
                let rows = if self.potions > 0 { 2 } else { 1 };
                self.active_screen_cursor = (i16::from(self.active_screen_cursor) + i16::from(delta))
                    .rem_euclid(rows) as u8;
            }
            Some(MenuEntry::Option) => {
                self.active_screen_cursor = (i16::from(self.active_screen_cursor) + i16::from(delta))
                    .rem_euclid(2) as u8;
            }
            Some(MenuEntry::Save) => {
                self.active_screen_cursor = (i16::from(self.active_screen_cursor) + i16::from(delta))
                    .rem_euclid(2) as u8;
            }
            Some(MenuEntry::Pokemon | MenuEntry::Player | MenuEntry::Exit) | None => {}
        }
    }

    /// Performs the focused Start-menu action.  Potion selection mirrors the
    /// early-game field constraint: it is only consumed when an injured
    /// party member exists. Save is an in-memory deterministic acknowledgement
    /// so a rollout never mutates host files.
    pub fn activate_active_screen(&mut self) {
        match self.active_screen {
            Some(MenuEntry::Bag) if self.active_screen_cursor == 1 && self.potions > 0 => {
                self.close_active_screen();
                self.dialogue = Some("There are no injured POKéMON.".to_owned());
            }
            Some(MenuEntry::Save) if self.active_screen_cursor == 0 => {
                self.save_count = self.save_count.saturating_add(1);
                self.close_active_screen();
                self.dialogue = Some(format!("{} saved the game.", self.player_name));
            }
            Some(MenuEntry::Save) => self.close_active_screen(),
            Some(MenuEntry::Option) => {
                if self.active_screen_cursor == 0 {
                    self.text_speed_fast = !self.text_speed_fast;
                } else {
                    self.battle_style_set = !self.battle_style_set;
                }
            }
            _ => {}
        }
    }

    pub fn adjust_active_screen(&mut self, delta: i8) {
        if self.active_screen == Some(MenuEntry::Option) {
            self.activate_active_screen();
        } else if delta != 0 {
            self.move_active_screen_cursor(delta);
        }
    }

    pub fn begin_clock_edit(&mut self) {
        if self.phase == StoryPhase::ClockSet
            && self.dialogue.is_none()
            && !self.clock_prompt_active
        {
            // `PlayersHouse_2F_EventScript_WallClock` opens this message
            // before it calls `StartWallClock`; the editor is not the first
            // result of interacting with the background event.
            self.clock_prompt_active = true;
            self.begin_field_dialogue(
                "The clock is stopped…\nBetter set it and start it!".to_owned(),
            );
        }
    }

    fn start_clock_editor(&mut self) {
        self.clock_minutes.get_or_insert(WALL_CLOCK_START_MINUTES);
        self.clock_editing = Some(ClockField::Hours);
        self.clock_confirming = false;
        self.clock_confirm_yes = true;
        self.clock_period_transition = None;
    }

    pub fn move_clock_cursor(&mut self) {
        if self.clock_confirming {
            self.clock_confirm_yes = !self.clock_confirm_yes;
            return;
        }
        self.clock_editing = match self.clock_editing {
            Some(ClockField::Hours) => Some(ClockField::Minutes),
            Some(ClockField::Minutes) => Some(ClockField::Hours),
            None => None,
        };
    }

    /// Advances the two independent period-indicator OAM callbacks while the
    /// clock task remains interactive. Source runs these callbacks after its
    /// input task every VBlank, including frames with no button press.
    pub fn advance_clock_period_transition(&mut self, frames: u32) {
        let Some(transition) = self.clock_period_transition else { return; };
        let elapsed = transition.elapsed_frames.saturating_add(
            frames.min(u32::from(u8::MAX)) as u8,
        );
        if elapsed >= WALL_CLOCK_PERIOD_TRANSITION_FRAMES {
            self.clock_period_transition = None;
        } else {
            self.clock_period_transition = Some(ClockPeriodTransition {
                elapsed_frames: elapsed,
                ..transition
            });
        }
    }

    /// Returns the source OAM angles in PM, AM order. At rest these are
    /// `(45, 90)` for AM and `(90, 135)` for PM; during a period flip each
    /// angle follows its own callback's one-degree/five-degree bands.
    pub fn clock_period_indicator_angles(&self) -> (u8, u8) {
        let Some(transition) = self.clock_period_transition else {
            return wall_clock_settled_period_angles(
                self.clock_minutes.unwrap_or(WALL_CLOCK_START_MINUTES) >= 12 * 60,
            );
        };
        let mut pm_angle = transition.pm_angle;
        let mut am_angle = transition.am_angle;
        for _ in 0..transition.elapsed_frames {
            pm_angle = wall_clock_advance_pm_indicator(pm_angle, transition.target_is_pm);
            am_angle = wall_clock_advance_am_indicator(am_angle, transition.target_is_pm);
        }
        (pm_angle, am_angle)
    }

    pub fn adjust_clock(&mut self, delta: i16) {
        if self.clock_confirming { return; }
        let Some(field) = self.clock_editing else { return; };
        let step = match field { ClockField::Hours => 60, ClockField::Minutes => 1 };
        let current = i16::try_from(self.clock_minutes.unwrap_or(WALL_CLOCK_START_MINUTES))
            .unwrap_or(i16::try_from(WALL_CLOCK_START_MINUTES).expect("wall-clock default fits i16"));
        let was_pm = current >= 12 * 60;
        let (pm_angle, am_angle) = self.clock_period_indicator_angles();
        let adjusted = (current + delta * step).rem_euclid(1440) as u16;
        let is_pm = adjusted >= 12 * 60;
        self.clock_minutes = Some(adjusted);
        if was_pm != is_pm {
            // `Task_SetClock_HandleInput` changes `tPeriod` before the
            // sprite callbacks run for the current VBlank. Start at one
            // elapsed source callback so this request includes that first
            // visible degree of period-badge movement.
            self.clock_period_transition = Some(ClockPeriodTransition {
                pm_angle,
                am_angle,
                target_is_pm: is_pm,
                elapsed_frames: 1,
            });
        }
    }

    pub fn confirm_clock(&mut self) {
        if self.clock_editing.is_none() { return; }
        if !self.clock_confirming {
            self.clock_confirming = true;
            self.clock_confirm_yes = true;
        } else if self.clock_confirm_yes {
            self.clock_editing = None;
            self.clock_confirming = false;
            self.clock_period_transition = None;
            // `PlayersHouse_2F_EventScript_WallClock` waits thirty frames
            // after `StartWallClock` before it creates Mom's upstairs object
            // event, then runs Mom's 68-frame entry and the player's
            // four-frame in-place turn before opening Mom's message.
            self.phase = StoryPhase::ClockVisit;
            self.clock_settle_frames = Some(30);
            self.clock_visit_frames = None;
            self.dialogue = None;
            self.npcs.clear();
        } else {
            self.clock_confirming = false;
        }
    }

    /// Advances the deterministic rival-arrival script. While active it
    /// consumes gameplay input, then exposes the following dialogue beat.
    pub fn advance_rival_arrival(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.rival_arrival_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if self.title_intro_step == 2 {
            let rival = self.npcs.iter().find(|npc| npc.id == "rival" && npc.map == self.map)
                .expect("rival must exist during bedroom PC walk");
            let (steps, player_facing) = bedroom_rival_pc_route(self.map, &rival.position);
            let total = steps.iter().map(|(_, faster)| bedroom_rival_movement_frames(*faster)).sum::<u16>();
            let elapsed_before = total.saturating_sub(remaining);
            let elapsed_after = total.saturating_sub(next_remaining);
            let mut boundary = 0u16;
            for (direction, faster) in steps {
                boundary += bedroom_rival_movement_frames(*faster);
                if elapsed_before < boundary && boundary <= elapsed_after {
                    let rival = self.npcs.iter().find(|npc| npc.id == "rival" && npc.map == self.map)
                        .expect("rival must remain during bedroom PC walk");
                    let position = if *faster { rival.position.clone() } else { stepped_position(&rival.position, *direction) };
                    if *faster {
                        self.move_faster_scripted_npc("rival", self.map, position, *direction);
                    } else {
                        self.move_scripted_npc("rival", self.map, position, *direction);
                    }
                }
            }
            if next_remaining == 0 {
                self.rival_arrival_frames = None;
                self.title_intro_step = 0;
                self.facing = player_facing;
                self.phase = StoryPhase::MetRival;
            } else {
                self.rival_arrival_frames = Some(next_remaining);
            }
            return true;
        }
        if self.title_intro_step == 1 {
            let (steps, player_facing) = bedroom_rival_approach(self.map, self.facing);
            let walk_frames = steps.iter().map(|(_, faster)| bedroom_rival_movement_frames(*faster)).sum::<u16>();
            let total = walk_frames + BEDROOM_RIVAL_FASTER_TURN_FRAMES;
            let elapsed_before = total.saturating_sub(remaining);
            let elapsed_after = total.saturating_sub(next_remaining);
            let mut boundary = 0u16;
            for (direction, faster) in steps {
                boundary += bedroom_rival_movement_frames(*faster);
                if elapsed_before < boundary && boundary <= elapsed_after {
                    let rival = self.npcs.iter().find(|npc| npc.id == "rival" && npc.map == self.map)
                        .expect("rival must exist during bedroom approach");
                    let position = if *faster {
                        rival.position.clone()
                    } else {
                        stepped_position(&rival.position, *direction)
                    };
                    if *faster {
                        self.move_faster_scripted_npc("rival", self.map, position, *direction);
                    } else {
                        self.move_scripted_npc("rival", self.map, position, *direction);
                    }
                }
            }
            if elapsed_before < total && total <= elapsed_after {
                self.facing = player_facing;
            }
            if next_remaining == 0 {
                self.rival_arrival_frames = None;
                self.title_intro_step = 0;
                self.dialogue = Some(match self.map {
                    MapId::MaysHouse2F => format!("MAY: Huh? Who are you?\nOh, you're {}. So your move was today. I'm MAY. Glad to meet you!", self.player_name),
                    MapId::BrendansHouse2F => format!("BRENDAN: Hey! Who are you?\nOh, you're {}, aren't you? Moved in next door, right? I'm BRENDAN. So, hi, neighbor!", self.player_name),
                    _ => "RIVAL: Who are you?".to_owned(),
                });
            } else {
                self.rival_arrival_frames = Some(next_remaining);
            }
            return true;
        }
        // Both 2F scripts delay ten frames before `addobject`, then begin
        // the two down steps and a four-frame faster turn immediately. Preserve the
        // doorway boundary rather than exposing the rival at the Poké Ball.
        let elapsed_before = BEDROOM_RIVAL_ENTRY_FRAMES.saturating_sub(remaining);
        let elapsed_after = BEDROOM_RIVAL_ENTRY_FRAMES.saturating_sub(next_remaining);
        let initial = match self.map {
            MapId::BrendansHouse2F => TilePosition { x: 7, y: 1 },
            MapId::MaysHouse2F => TilePosition { x: 1, y: 1 },
            _ => return false,
        };
        let side = match self.map {
            MapId::BrendansHouse2F => Facing::Left,
            MapId::MaysHouse2F => Facing::Right,
            _ => unreachable!(),
        };
        if elapsed_before < 10 && 10 <= elapsed_after
            && !self.npcs.iter().any(|npc| npc.id == "rival" && npc.map == self.map)
        {
            self.npcs.push(NpcState {
                id: "rival".to_owned(), map: self.map, position: initial.clone(), facing: Facing::Down,
            });
        }
        if elapsed_before < 26 && 26 <= elapsed_after {
            self.move_scripted_npc(
                "rival", self.map,
                TilePosition { x: initial.x, y: initial.y + 1 }, Facing::Down,
            );
        }
        if elapsed_before < 42 && 42 <= elapsed_after {
            self.move_scripted_npc(
                "rival", self.map,
                TilePosition { x: initial.x, y: initial.y + 2 }, Facing::Down,
            );
        }
        if elapsed_before < 46 && 46 <= elapsed_after {
            self.move_faster_scripted_npc(
                "rival", self.map,
                TilePosition { x: initial.x, y: initial.y + 2 }, side,
            );
        }
        if next_remaining == 0 {
            // The source now chooses one of four approach streams from the
            // player’s interaction facing. The message waits until that
            // stream and its player turn have completed.
            let (steps, _) = bedroom_rival_approach(self.map, self.facing);
            let total = steps.iter().map(|(_, faster)| bedroom_rival_movement_frames(*faster)).sum::<u16>()
                + BEDROOM_RIVAL_FASTER_TURN_FRAMES;
            self.title_intro_step = 1;
            self.rival_arrival_frames = Some(total);
            // Keep fixed-frame rollout semantics: an advance that crosses
            // the entrance lock also consumes the appropriate portion of
            // the following player-facing approach stream.
            let carry = frames.saturating_sub(u32::from(remaining));
            if carry > 0 {
                self.advance_rival_arrival(carry);
            }
        } else {
            self.rival_arrival_frames = Some(next_remaining);
        }
        true
    }

    /// Runs Route103_EventScript_RivalExit once its two post-battle messages
    /// have closed. `route103_rival_departure_facing` and the serialized
    /// countdown retain the selected source branch across checkpoint restore;
    /// source watcher movements run alongside the rival's first stream before
    /// `waitmovement` can release the southern ledge path.
    pub fn advance_rival_departure(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.rival_departure_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let departure_facing = self.route103_rival_departure_facing.unwrap_or(self.facing);
        let player_faced_north = departure_facing == Facing::Up;
        let player_faced_sideways = matches!(departure_facing, Facing::Left | Facing::Right);
        let total_frames = match departure_facing {
            Facing::Up => ROUTE103_RIVAL_EXIT_NORTH_FRAMES,
            Facing::Left | Facing::Right => ROUTE103_RIVAL_EXIT_SIDE_FRAMES,
            Facing::Down => ROUTE103_RIVAL_EXIT_SOUTH_FRAMES,
        };
        let elapsed_before = total_frames.saturating_sub(remaining);
        let elapsed_after = total_frames.saturating_sub(next_remaining);
        // `WatchRivalExitFacingNorth` is `delay_16`, `delay_4`, a
        // four-frame left turn, `delay_16`, then a four-frame down turn.
        // The east/west watcher is `delay_16` plus its four-frame down turn.
        // Commit facing when each in-place action completes, matching the
        // duration boundary used for other staged source turns.
        if player_faced_north && elapsed_before < 24 && 24 <= elapsed_after {
            self.facing = Facing::Left;
        }
        if player_faced_north && elapsed_before < 44 && 44 <= elapsed_after {
            self.facing = Facing::Down;
        }
        if player_faced_sideways && elapsed_before < 20 && 20 <= elapsed_after {
            self.facing = Facing::Down;
        }
        // `Route103_Movement_RivalExit*` commits each destination as its
        // movement command starts.  In particular, `jump_2_down` begins only
        // after the watcher stream's `waitmovement`, travels two tiles over
        // 32 frames, and then pauses for `delay_16`.  Starting the native
        // stride at its former completion boundary made the rival slide one
        // tile late with no jump arc.
        let path: &[(u16, i16, i16, u8)] = match departure_facing {
            Facing::Up => &[
                (0, 9, 3, 16),
                (16, 9, 4, 16),
                (44, 9, 6, 32),
                (92, 9, 7, 16),
                (108, 9, 8, 16),
                (124, 9, 9, 16),
                (140, 9, 10, 16),
            ],
            Facing::Left | Facing::Right => &[
                (0, 10, 4, 16),
                (20, 10, 6, 32),
                (68, 10, 7, 16),
                (84, 10, 8, 16),
                (100, 10, 9, 16),
            ],
            Facing::Down => &[
                (0, 10, 4, 16),
                (16, 10, 6, 32),
                (64, 10, 7, 16),
                (80, 10, 8, 16),
                (96, 10, 9, 16),
            ],
        };
        for &(start, x, y, duration) in path {
            if elapsed_before <= start && start < elapsed_after {
                let request_offset = u32::from(start.saturating_sub(elapsed_before));
                let source_frame = self.frame.saturating_sub(u64::from(
                    frames.saturating_sub(request_offset),
                ));
                self.move_scripted_npc_with_duration_at_frame(
                    "rival",
                    MapId::Route103,
                    TilePosition { x, y },
                    Facing::Down,
                    duration,
                    source_frame,
                );
            }
        }
        if next_remaining == 0 {
            self.rival_departure_frames = None;
            self.route103_rival_departure_facing = None;
            self.npcs.retain(|npc| !(npc.map == MapId::Route103 && npc.id == "rival"));
        } else {
            self.rival_departure_frames = Some(next_remaining);
        }
        true
    }

    /// Runs OldaleTown's two authored six-step rival exits after the Route
    /// 103 return encounter. `RivalFinish` applies the same exit movement in
    /// its selected branch, then once more before permanently removing the
    /// object.
    pub fn advance_oldale_rival_departure(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_rival_departure_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        // `OldaleTown_EventScript_RivalFinish` runs the first six-step exit
        // through `DoExitMovement{1,2}`, then unconditionally applies the
        // same six steps before `removeobject`. South-edge triggers and a
        // direct interaction while not facing south also run the parallel
        // 16-frame player watch movement (delay 8, delay 4, faster down turn).
        let player_watches = (self.player.y == 19 && (8..=10).contains(&self.player.x))
            || self.facing != Facing::Down;
        // `walk_in_place_faster_down` finishes at the same 16-frame boundary
        // as the rival's first ordinary southward step.
        if player_watches && remaining > 176 && next_remaining <= 176 {
            self.facing = Facing::Down;
        }
        // Each `OldaleTown_Movement_RivalExit` invocation has six ordinary
        // walk_down commands. Keep all twelve 16-frame boundaries so a
        // checkpoint restored during either pass continues the source stream.
        for boundary in [176, 160, 144, 128, 112, 96, 80, 64, 48, 32, 16, 0] {
            if remaining > boundary && next_remaining <= boundary {
                let rival = self.npcs.iter().find(|npc| npc.id == "oldale_rival")
                    .expect("Oldale rival must exist during its scripted exit");
                self.move_scripted_npc(
                    "oldale_rival",
                    MapId::OldaleTown,
                    TilePosition { x: rival.position.x, y: rival.position.y + 1 },
                    Facing::Down,
                );
            }
        }
        if next_remaining == 0 {
            self.oldale_rival_departure_frames = None;
            self.oldale_rival_departed = true;
            self.npcs.retain(|npc| npc.id != "oldale_rival");
        } else {
            self.oldale_rival_departure_frames = Some(next_remaining);
        }
        true
    }

    /// Returns the active cell time for Oldale's source
    /// `walk_in_place_faster_right` player action.  The map script keeps the
    /// actor fixed for four frames; native composition uses this only for the
    /// source OBJ-cell cadence, never for terrain or coordinate motion.
    pub fn oldale_rival_player_faster_right_elapsed(&self) -> Option<u8> {
        let remaining = self.oldale_rival_approach_frames?;
        (remaining <= 4).then_some(4 - remaining)
    }

    /// Runs the south-edge approach before Oldale's rival shows the
    /// homeward message.  The map scripts select two, one, or zero normal
    /// left walks from the rival's `(11,19)` home tile, then make the player
    /// perform `walk_in_place_faster_right` before opening the message.
    pub fn advance_oldale_rival_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_rival_approach_frames else { return false; };
        let consumed = frames.min(u32::from(u8::MAX)) as u8;
        let next_remaining = remaining.saturating_sub(consumed);
        let approach_steps = (10_i16 - self.player.x).clamp(0, 2) as u8;
        let rival_walk_frames = approach_steps * 16;
        let total_frames = rival_walk_frames + 4;
        let elapsed_before = total_frames.saturating_sub(remaining);
        let elapsed_after = total_frames.saturating_sub(next_remaining);

        for step in 0..approach_steps {
            let start = step * 16;
            if elapsed_before <= start && start < elapsed_after {
                let position = {
                    let rival = self.npcs.iter().find(|npc| npc.id == "oldale_rival")
                        .expect("Oldale rival must exist during its scripted approach");
                    TilePosition { x: rival.position.x - 1, y: rival.position.y }
                };
                let request_offset = u32::from(start.saturating_sub(elapsed_before));
                let source_frame = self.frame.saturating_sub(u64::from(
                    frames.saturating_sub(request_offset),
                ));
                self.move_scripted_npc_with_duration_at_frame(
                    "oldale_rival",
                    MapId::OldaleTown,
                    position,
                    Facing::Left,
                    16,
                    source_frame,
                );
            }
        }

        // `Common_Movement_WalkInPlaceFasterRight` starts as soon as the
        // rival's final normal stride completes. Its visible facing changes
        // at the source boundary and input remains locked for all four frames;
        // the native compositor consumes that interval for the source
        // faster-east OBJ cells.
        if elapsed_before <= rival_walk_frames && rival_walk_frames < elapsed_after {
            self.facing = Facing::Right;
        }

        if next_remaining == 0 {
            self.oldale_rival_approach_frames = None;
            self.walk_direction = None;
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_render_origin = None;
            self.begin_field_dialogue(match self.player_gender {
                PlayerGender::Brendan => format!("MAY: {}!\nOver here!\nLet's hurry home!", self.player_name),
                PlayerGender::May => format!("BRENDAN: I'm heading back to my dad's\nLAB now.\n{}, you should hustle back, too.", self.player_name),
            });
            // A long held request can cross both the approach and the first
            // source message boundary.  Preserve that carry instead of
            // starting the printer only on a later Noop request.
            self.advance_field_dialogue_printer(frames.saturating_sub(u32::from(remaining)));
        } else {
            self.oldale_rival_approach_frames = Some(next_remaining);
        }
        true
    }

    /// Commits a scripted object-event step and gives the native OBJ layer a
    /// 16-frame start marker. Ambient and authored movement use the same
    /// interpolator, preventing cutscene actors from jumping tile-to-tile.
    fn move_scripted_npc(&mut self, id: &str, map: MapId, position: TilePosition, facing: Facing) {
        self.move_scripted_npc_with_duration(id, map, position, facing, 16);
    }

    fn move_fast_scripted_npc(&mut self, id: &str, map: MapId, position: TilePosition, facing: Facing) {
        self.move_scripted_npc_with_duration(id, map, position, facing, 8);
    }

    /// `walk_in_place_faster_*` is the distinct four-frame source action,
    /// rather than the eight-frame `walk_in_place_fast_*` cadence.
    fn move_faster_scripted_npc(&mut self, id: &str, map: MapId, position: TilePosition, facing: Facing) {
        self.move_scripted_npc_with_duration(id, map, position, facing, 4);
    }

    fn move_scripted_npc_with_duration(&mut self, id: &str, map: MapId, position: TilePosition, facing: Facing, duration_frames: u8) {
        self.move_scripted_npc_with_duration_at_frame(
            id,
            map,
            position,
            facing,
            duration_frames,
            self.frame,
        );
    }

    /// A staged script can cross an object-event boundary within one held
    /// request. Retain that source frame so the shared OBJ interpolator shows
    /// the already-started stride instead of restarting it at request end.
    fn move_scripted_npc_with_duration_at_frame(
        &mut self,
        id: &str,
        map: MapId,
        position: TilePosition,
        facing: Facing,
        duration_frames: u8,
        frame: u64,
    ) {
        if let Some(npc) = self.npcs.iter_mut().find(|npc| npc.id == id && npc.map == map) {
            if npc.position == position && npc.facing == facing { return; }
            npc.position = position;
            npc.facing = facing;
            self.npc_walk_starts.retain(|walk| walk.id != id);
            self.npc_walk_starts.push(NpcWalkStart {
                id: id.to_owned(),
                frame,
                duration_frames,
                sprite_facing: Some(facing),
                in_place: false,
            });
        }
    }

    /// Records an authored `walk_in_place_*` action.  These commands use the
    /// same source OBJ stride cells as a walk, but their map coordinate stays
    /// fixed throughout the action.
    fn animate_scripted_npc_in_place_at_frame(
        &mut self,
        id: &str,
        map: MapId,
        facing: Facing,
        duration_frames: u8,
        frame: u64,
    ) {
        if let Some(npc) = self.npcs.iter_mut().find(|npc| npc.id == id && npc.map == map) {
            npc.facing = facing;
            self.npc_walk_starts.retain(|walk| walk.id != id);
            self.npc_walk_starts.push(NpcWalkStart {
                id: id.to_owned(),
                frame,
                duration_frames,
                sprite_facing: Some(facing),
                in_place: true,
            });
        }
    }

    /// Runs the locked movement portion of
    /// `OldaleTown_EventScript_{GoToMartSouth,GoToMartNorth,GoToMartEast}`.
    /// Each branch brings the employee to the same storefront tile, where
    /// Emerald then explains the Mart and awards the Potion.
    pub fn advance_oldale_mart_scene(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_mart_scene_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let route = self.oldale_mart_scene_route.unwrap_or(Facing::Up);
        let total_frames: u16 = match route {
            // Each employee stream ends with the four-frame
            // `walk_in_place_faster_down`; `waitmovement` holds the script
            // until that visible turn completes.
            Facing::Down => 148,
            Facing::Up | Facing::Right | Facing::Left => 116,
        };
        let elapsed_before = total_frames.saturating_sub(remaining);
        let elapsed_after = total_frames.saturating_sub(next_remaining);

        // These are the authored `applymovement` streams.  Keeping their
        // individual 16-frame boundaries matters: the employee and player
        // walk together rather than disappearing from the conversation tile
        // and reappearing at the Mart once a no-op interval happens to end.
        let (employee_steps, player_steps, player_delay_steps): (&[Facing], &[Facing], u16) = match route {
            Facing::Down => (
                &[Facing::Left, Facing::Up, Facing::Up, Facing::Right, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                &[Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                4,
            ),
            Facing::Right => (
                &[Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                &[Facing::Right, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                0,
            ),
            // The source has no west branch.  Imported legacy states follow
            // the north choreography deterministically.
            Facing::Up | Facing::Left => (
                &[Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                &[Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                0,
            ),
        };
        for (index, direction) in employee_steps.iter().enumerate() {
            // `walk_*` begins at this boundary and occupies the following
            // sixteen video frames.  Commit the destination when the source
            // stride starts, not when it ends: the OBJ renderer then offsets
            // that logical destination back toward the prior tile for the
            // in-flight portion of the walk.  The former end-boundary commit
            // made every Oldale Mart guide stride appear one full beat late.
            let start = u16::try_from(index).expect("Oldale movement index fits") * 16;
            if elapsed_before <= start && start < elapsed_after {
                let position = {
                    let employee = self.npcs.iter().find(|npc| npc.id == "mart_employee")
                        .expect("Oldale Mart employee must exist during its scripted walk");
                    match direction {
                        Facing::Up => TilePosition { x: employee.position.x, y: employee.position.y - 1 },
                        Facing::Down => TilePosition { x: employee.position.x, y: employee.position.y + 1 },
                        Facing::Left => TilePosition { x: employee.position.x - 1, y: employee.position.y },
                        Facing::Right => TilePosition { x: employee.position.x + 1, y: employee.position.y },
                    }
                };
                let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - start));
                self.move_scripted_npc_with_duration_at_frame(
                    "mart_employee",
                    MapId::OldaleTown,
                    position,
                    *direction,
                    16,
                    source_frame,
                );
            }
        }
        let employee_turn_start = u16::try_from(employee_steps.len())
            .expect("Oldale employee movement count fits")
            * 16;
        if elapsed_before <= employee_turn_start && employee_turn_start < elapsed_after {
            let position = self.npcs.iter().find(|npc| npc.id == "mart_employee")
                .expect("Oldale Mart employee must exist during its scripted turn")
                .position
                .clone();
            let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - employee_turn_start));
            self.move_scripted_npc_with_duration_at_frame(
                "mart_employee",
                MapId::OldaleTown,
                position,
                Facing::Down,
                4,
                source_frame,
            );
        }
        for (index, direction) in player_steps.iter().enumerate() {
            let boundary = (player_delay_steps + u16::try_from(index).expect("Oldale movement index fits") + 1) * 16;
            if elapsed_before < boundary && boundary <= elapsed_after {
                match direction {
                    Facing::Up => self.player.y -= 1,
                    Facing::Down => self.player.y += 1,
                    Facing::Left => self.player.x -= 1,
                    Facing::Right => self.player.x += 1,
                }
                self.facing = *direction;
                self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                    .expect("Oldale Mart movement must remain on staged walkable tiles");
            }
        }
        let player_motion_start = player_delay_steps * 16;
        let player_motion_end = player_motion_start
            + u16::try_from(player_steps.len()).expect("Oldale player movement count fits") * 16;
        self.walk_direction = (elapsed_after > player_motion_start && elapsed_after < player_motion_end)
            .then(|| player_steps[((elapsed_after - player_motion_start) / 16) as usize]);
        self.walk_progress_frames = if elapsed_after > player_motion_start && elapsed_after < player_motion_end {
            ((elapsed_after - player_motion_start) % 16) as u8
        } else {
            0
        };
        if next_remaining == 0 {
            self.facing = Facing::Up;
            self.walk_direction = None;
            self.walk_progress_frames = 0;
            self.oldale_mart_scene_frames = None;
            self.oldale_mart_scene_stage = 3;
            self.oldale_mart_dialogue_page = 0;
            self.oldale_mart_dialogue_frames = Some(64);
            self.dialogue = Some("This is a POKéMON MART.\nJust look for our blue roof.".to_owned());
            self.advance_oldale_mart_dialogue_printer(frames.saturating_sub(u32::from(remaining)));
        } else {
            self.oldale_mart_scene_frames = Some(next_remaining);
        }
        true
    }

    /// Advances an Oldale Mart script message. The source has a short
    /// message-specific lead-in, then reveals one glyph per frame; opening
    /// requests have already spent their first sixteen printer frames.
    pub fn advance_oldale_mart_dialogue_printer(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_mart_dialogue_frames else { return false; };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.oldale_mart_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// Advances the obtain-item fanfare which runs after `Obtained the
    /// POTION!`. The MIDI source lasts roughly 161 video frames; the opening
    /// A has already consumed the first sixteen. The first receipt keeps
    /// printing while this clock runs, and the second receipt begins as soon
    /// as the fanfare ends without another player action.
    pub fn advance_oldale_mart_item_fanfare(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_mart_item_fanfare_frames else { return false; };
        let consumed = frames.min(u32::from(u16::MAX)) as u16;
        let next = remaining.saturating_sub(consumed);
        if let Some(printer_remaining) = self.oldale_mart_dialogue_frames {
            let next_printer = printer_remaining.saturating_sub(consumed);
            self.oldale_mart_dialogue_frames = (next_printer != 0).then_some(next_printer);
        }
        if next != 0 {
            self.oldale_mart_item_fanfare_frames = Some(next);
            return true;
        }

        let carried = frames.saturating_sub(u32::from(remaining));
        let dialogue = format!("{} put away the POTION\nin the ITEMS POCKET.", self.player_name);
        self.oldale_mart_item_fanfare_frames = None;
        self.oldale_mart_scene_stage = 5;
        self.oldale_mart_dialogue_page = 1;
        let printer_remaining = dialogue_printer_duration(&dialogue)
            .saturating_sub(carried.min(u32::from(u16::MAX)) as u16);
        self.oldale_mart_dialogue_frames = (printer_remaining != 0).then_some(printer_remaining);
        self.dialogue = Some(dialogue);
        true
    }

    /// Advances a regular overworld message printer. The request that opens
    /// an interaction consumes its initial sample window here as it does on
    /// hardware, while later A presses remain locked until printing ends.
    pub fn advance_field_dialogue_printer(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.field_dialogue_frames else { return false; };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.field_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// Advances the script delay between `StartWallClock` returning and Mom's
    /// upstairs object event being created. The source's `delay 30` occurs
    /// before `addobject`, so keeping it separate avoids displaying Mom for
    /// frames in which the original room is still empty.
    pub fn advance_clock_settle(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.clock_settle_frames else { return false; };
        let consumed = frames.min(u32::from(u8::MAX)) as u8;
        let next_remaining = remaining.saturating_sub(consumed);
        if next_remaining != 0 {
            self.clock_settle_frames = Some(next_remaining);
            return true;
        }

        self.clock_settle_frames = None;
        // Mom's source movement is delay_8 + walk_down + faster in-place
        // turn + delay_16 + delay_8 + final lateral walk = 68 frames. The
        // script then waits for the player's four-frame faster turn before
        // it opens Mom's room message.
        self.clock_visit_frames = Some(CLOCK_VISIT_ENTRY_FRAMES);
        self.npcs = map_npcs(
            self.map,
            self.phase,
            self.potions,
            self.oldale_rival_departed,
            self.player_gender,
        );
        let carried = frames.saturating_sub(u32::from(remaining));
        if carried != 0 {
            self.advance_clock_visit(carried);
        }
        true
    }

    /// Runs `PlayersHouse_2F_Movement_MomEnters{Male,Female}` after the wall
    /// clock: delay 8, step down, fast turn, delay 24, then step beside the
    /// player. The source then waits for the player's fast left/right turn;
    /// input remains locked until Mom's room dialogue opens.
    pub fn advance_clock_visit(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.clock_visit_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if self.title_intro_step == u8::MAX {
            let elapsed_before = 40u16.saturating_sub(remaining);
            let elapsed_after = 40u16.saturating_sub(next_remaining);
            let (doorway, exit_facing) = match self.map {
                MapId::BrendansHouse2F => (TilePosition { x: 7, y: 2 }, Facing::Right),
                MapId::MaysHouse2F => (TilePosition { x: 1, y: 2 }, Facing::Left),
                _ => return false,
            };
            // `MomExits*`: return across the room, step into the doorway,
            // then an 8-frame delay before the object is removed.
            if elapsed_before < 16 && 16 <= elapsed_after {
                self.move_scripted_npc("mom", self.map, doorway.clone(), exit_facing);
            }
            if elapsed_before < 32 && 32 <= elapsed_after {
                self.move_scripted_npc(
                    "mom", self.map,
                    TilePosition { x: doorway.x, y: doorway.y - 1 }, Facing::Up,
                );
            }
            if next_remaining == 0 {
                self.clock_visit_frames = None;
                self.title_intro_step = 0;
                self.phase = StoryPhase::TvBroadcast;
                self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
            } else {
                self.clock_visit_frames = Some(next_remaining);
            }
            return true;
        }
        let elapsed_before = CLOCK_VISIT_ENTRY_FRAMES.saturating_sub(remaining);
        let elapsed_after = CLOCK_VISIT_ENTRY_FRAMES.saturating_sub(next_remaining);
        let (down_position, final_position, side) = match self.map {
            MapId::BrendansHouse2F => (
                TilePosition { x: 7, y: 2 }, TilePosition { x: 6, y: 2 }, Facing::Left,
            ),
            MapId::MaysHouse2F => (
                TilePosition { x: 1, y: 2 }, TilePosition { x: 2, y: 2 }, Facing::Right,
            ),
            _ => return false,
        };
        // `MomEnters*`: delay_8, walk_down, fast side turn, delay_16,
        // delay_8, then the final lateral walk.
        if elapsed_before < 24 && 24 <= elapsed_after {
            self.move_scripted_npc("mom", self.map, down_position.clone(), Facing::Down);
        }
        if elapsed_before < 28 && 28 <= elapsed_after {
            self.move_scripted_npc_with_duration("mom", self.map, down_position, side, 4);
        }
        if elapsed_before < CLOCK_VISIT_MOM_ENTRY_FRAMES
            && CLOCK_VISIT_MOM_ENTRY_FRAMES <= elapsed_after
        {
            self.move_scripted_npc("mom", self.map, final_position, side);
        }
        if next_remaining == 0 {
            self.clock_visit_frames = None;
            self.facing = match self.player_gender {
                PlayerGender::Brendan => Facing::Right,
                PlayerGender::May => Facing::Left,
            };
            self.dialogue = Some(format!("MOM: {}, how do you like your new room?\nEverything's put away neatly downstairs, too. POKéMON movers are so convenient!", self.player_name));
        } else {
            self.clock_visit_frames = Some(next_remaining);
        }
        true
    }

    /// Runs the first locked portion of `PetalburgGymReport{Male,Female}`.
    /// The map OnFrame script makes Mom turn toward the room, plays her
    /// exclamation emote, and waits `Common_Movement_Delay48` before the
    /// first "Oh! ... Come quickly!" message can open.
    pub fn advance_tv_broadcast_intro(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.tv_broadcast_intro_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let elapsed_before = TV_BROADCAST_INTRO_FRAMES.saturating_sub(remaining);
        let elapsed_after = TV_BROADCAST_INTRO_FRAMES.saturating_sub(next_remaining);
        // The report scripts begin with `walk_in_place_faster_{right,left}`.
        // Preserve its four-frame boundary independently from the emote and
        // Delay48 hold that follow it.
        if elapsed_before < 4 && 4 <= elapsed_after {
            let turn = match self.map {
                MapId::BrendansHouse1F => Facing::Right,
                MapId::MaysHouse1F => Facing::Left,
                _ => return false,
            };
            let map = self.map;
            let position = self.npcs.iter()
                .find(|npc| npc.id == "mom" && npc.map == map)
                .expect("Mom must exist for the Petalburg Gym report")
                .position
                .clone();
            self.move_faster_scripted_npc("mom", map, position, turn);
        }
        if next_remaining == 0 {
            self.tv_broadcast_intro_frames = None;
            self.dialogue = Some(tv_broadcast_page(0, &self.player_name).to_owned());
        } else {
            self.tv_broadcast_intro_frames = Some(next_remaining);
        }
        true
    }

    /// Runs `LittlerootTown_{Mays,Brendans}House_1F_EventScript_YoureNewNeighbor`
    /// before its existing six-page greeting. The emote's object movement is
    /// complete after one tick, but its independently animated 60-frame icon
    /// continues through `Common_Movement_Delay48` and the first part of
    /// Mom's normal approach.
    pub fn advance_rival_mom_intro(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.rival_mom_intro_frames else { return false; };
        let consumed = frames.min(u32::from(u16::MAX)) as u16;
        let next_remaining = remaining.saturating_sub(consumed);
        let elapsed_before = RIVAL_MOM_INTRO_FRAMES.saturating_sub(remaining);
        let elapsed_after = RIVAL_MOM_INTRO_FRAMES.saturating_sub(next_remaining);

        if let Some(emote_remaining) = self.rival_mom_exclamation_frames {
            let next_emote = emote_remaining.saturating_sub(
                frames.min(u32::from(u8::MAX)) as u8,
            );
            self.rival_mom_exclamation_frames = (next_emote != 0).then_some(next_emote);
        }

        let (player_turn, mom_side) = match self.map {
            // Brendan's house has the counterpart Mom cross the room right,
            // while the player turns left toward her.
            MapId::BrendansHouse1F => (Facing::Left, Facing::Right),
            // May's house is the mirrored source stream.
            MapId::MaysHouse1F => (Facing::Right, Facing::Left),
            _ => return false,
        };
        let approach_start = RIVAL_MOM_EMOTE_MOVEMENT_FRAMES + RIVAL_MOM_DELAY_FRAMES;
        // `InitMoveInPlace` sets the source ObjectEvent direction when the
        // four-frame player action begins, not when it finishes.
        if elapsed_before < approach_start && approach_start <= elapsed_after {
            self.facing = player_turn;
        }

        // Mom's six-action stream starts with `walk_down`, followed by five
        // normal lateral walks toward the player. Object-event coordinates
        // commit at each step start; retain the exact start frame for the
        // dynamic object renderer when one request crosses more than one.
        let directions = [
            Facing::Down,
            mom_side,
            mom_side,
            mom_side,
            mom_side,
            mom_side,
        ];
        for (index, direction) in directions.iter().enumerate() {
            let step_start = approach_start
                + u16::try_from(index).expect("rival Mom approach index fits")
                    * RIVAL_MOM_NORMAL_STEP_FRAMES;
            if elapsed_before < step_start && step_start <= elapsed_after {
                let mom = self.npcs.iter()
                    .find(|npc| npc.id == "mom" && npc.map == self.map)
                    .expect("rival Mom must exist during the new-neighbor approach");
                let position = stepped_position(&mom.position, *direction);
                let start_frame = self.frame.saturating_sub(u64::from(
                    elapsed_after.saturating_sub(step_start),
                ));
                self.move_scripted_npc_with_duration_at_frame(
                    "mom",
                    self.map,
                    position,
                    *direction,
                    RIVAL_MOM_NORMAL_STEP_FRAMES as u8,
                    start_frame,
                );
            }
        }

        if next_remaining == 0 {
            self.rival_mom_intro_frames = None;
            self.rival_mom_exclamation_frames = None;
            self.title_intro_step = 0;
            self.dialogue = Some(rival_mom_page(0, self.player_gender, &self.player_name));
        } else {
            self.rival_mom_intro_frames = Some(next_remaining);
        }
        true
    }

    /// Runs the `PlayerApproachTVForGym{Male,Female}` stream after Mom's
    /// first Gym-report message closes. `waitmovement 0` keeps input locked
    /// across the five normal 16-frame player strides before the next report
    /// message can open.
    pub fn advance_tv_broadcast_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.tv_broadcast_approach_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let elapsed_before = TV_BROADCAST_APPROACH_FRAMES.saturating_sub(remaining);
        let elapsed_after = TV_BROADCAST_APPROACH_FRAMES.saturating_sub(next_remaining);
        let directions = match self.player_gender {
            // `PlayerApproachTVForGymMale`: down, down, left ×3.
            PlayerGender::Brendan => [
                Facing::Down,
                Facing::Down,
                Facing::Left,
                Facing::Left,
                Facing::Left,
            ],
            // `PlayerApproachTVForGymFemale`: down, down, right ×3.
            PlayerGender::May => [
                Facing::Down,
                Facing::Down,
                Facing::Right,
                Facing::Right,
                Facing::Right,
            ],
        };
        for (index, direction) in directions.into_iter().enumerate() {
            let boundary = TV_BROADCAST_APPROACH_STEP_FRAMES * (index as u16 + 1);
            if elapsed_before < boundary && boundary <= elapsed_after {
                let player = stepped_position(&self.player, direction);
                self.elevation = crate::native::tile_elevation(self.map, player.x, player.y)
                    .expect("TV approach destination must be inside the staged house map");
                self.player = player;
                self.facing = direction;
            }
        }
        if next_remaining == 0 {
            self.tv_broadcast_approach_frames = None;
            self.title_intro_step = 1;
            self.dialogue = Some(tv_broadcast_page(1, &self.player_name).to_owned());
        } else {
            self.tv_broadcast_approach_frames = Some(next_remaining);
        }
        true
    }

    /// Runs the bounded pre-report sequence after `MaybeDadWillBeOn` closes:
    /// Mom's normal lateral step and faster turn, then the player's normal
    /// lateral step and faster up-facing turn. Each source `waitmovement`
    /// keeps input locked until the reporter message can open.
    pub fn advance_tv_broadcast_view(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.tv_broadcast_view_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let elapsed_before = TV_BROADCAST_VIEW_FRAMES.saturating_sub(remaining);
        let elapsed_after = TV_BROADCAST_VIEW_FRAMES.saturating_sub(next_remaining);
        let (side, mom_turn) = match self.player_gender {
            PlayerGender::Brendan => (Facing::Left, Facing::Right),
            PlayerGender::May => (Facing::Right, Facing::Left),
        };
        let mom_step_boundary = TV_BROADCAST_VIEW_MOM_STEP_FRAMES;
        let mom_turn_boundary = mom_step_boundary + TV_BROADCAST_VIEW_FASTER_TURN_FRAMES;
        let player_step_boundary = mom_turn_boundary + TV_BROADCAST_VIEW_PLAYER_STEP_FRAMES;

        if elapsed_before == 0 {
            self.stop_walking();
        }
        if elapsed_before < mom_step_boundary && mom_step_boundary <= elapsed_after {
            let mom = self.npcs.iter()
                .find(|npc| npc.id == "mom" && npc.map == self.map)
                .expect("Mom must exist during the Petalburg Gym broadcast")
                .position
                .clone();
            let start_frame = self.frame.saturating_sub(u64::from(
                elapsed_after.saturating_sub(mom_step_boundary),
            ));
            self.move_scripted_npc_with_duration_at_frame(
                "mom",
                self.map,
                stepped_position(&mom, side),
                side,
                TV_BROADCAST_VIEW_MOM_STEP_FRAMES as u8,
                start_frame,
            );
        }
        if elapsed_before < mom_turn_boundary && mom_turn_boundary <= elapsed_after {
            let mom = self.npcs.iter()
                .find(|npc| npc.id == "mom" && npc.map == self.map)
                .expect("Mom must exist for the Petalburg Gym viewing turn")
                .position
                .clone();
            let start_frame = self.frame.saturating_sub(u64::from(
                elapsed_after.saturating_sub(mom_turn_boundary),
            ));
            self.move_scripted_npc_with_duration_at_frame(
                "mom",
                self.map,
                mom,
                mom_turn,
                TV_BROADCAST_VIEW_FASTER_TURN_FRAMES as u8,
                start_frame,
            );
        }
        if elapsed_before < mom_turn_boundary && mom_turn_boundary <= elapsed_after {
            // The source walk changes the player object's facing as its
            // 16-frame stride begins, before its destination tile commits.
            self.facing = side;
        }
        if elapsed_before < player_step_boundary && player_step_boundary <= elapsed_after {
            let player = stepped_position(&self.player, side);
            self.elevation = crate::native::tile_elevation(self.map, player.x, player.y)
                .expect("TV destination must be inside the staged house map");
            self.player = player;
        }
        self.walk_direction = (elapsed_after > mom_turn_boundary
            && elapsed_after < player_step_boundary)
            .then_some(side);
        self.walk_progress_frames = if elapsed_after > mom_turn_boundary
            && elapsed_after < player_step_boundary
        {
            (elapsed_after - mom_turn_boundary) as u8
        } else {
            0
        };
        self.walk_elapsed_frames = 0;

        if next_remaining == 0 {
            self.tv_broadcast_view_frames = None;
            self.stop_walking();
            self.facing = Facing::Up;
            self.title_intro_step = 2;
            self.dialogue = Some(tv_broadcast_page(2, &self.player_name).to_owned());
        } else {
            self.tv_broadcast_view_frames = Some(next_remaining);
        }
        true
    }

    /// Runs the scripted Little Root truck-arrival choreography. The source
    /// holds player input while the player steps off the truck and Mom exits
    /// the selected home, walks down to the truck row, and turns toward the
    /// player before beginning her first message.
    pub fn advance_truck_arrival(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.truck_arrival_frames else { return false; };
        // The measured May title route retains the truck viewport and its
        // exit-arrow frame through the Right×48 request. The following input
        // owns the actual warp/fade and carries its remaining time into Mom's
        // arrival choreography. `Some(0)` is the serialized pending-exit
        // state; ordinary truck checkpoints continue to use their legacy
        // immediate 16-frame exit below.
        if self.map == MapId::MovingTruck && remaining == 0 {
            self.truck_arrival_frames = None;
            self.phase = StoryPhase::TruckArrival;
            let destination = TilePosition { x: 12, y: 10 };
            self.begin_transition(MapId::LittlerootTown, destination);
            self.advance_transition(frames);
            if self.transition.is_none() {
                self.advance_truck_arrival(frames.saturating_sub(32));
            }
            return true;
        }
        let elapsed = frames.min(u32::from(u16::MAX)) as u16;
        let next_remaining = remaining.saturating_sub(elapsed);
        // The 176-frame total is calibrated from the map fade completion to
        // Mom's message.  These boundaries retain the source's visible
        // `PlayerStepOffTruck`, `MomExitHouse`, and
        // `MomApproachPlayerAtTruck` sequence instead of hiding it behind a
        // single timer.
        let elapsed_before = 176u16.saturating_sub(remaining);
        let elapsed_after = 176u16.saturating_sub(next_remaining);
        let home_x = match self.player_gender {
            PlayerGender::Brendan => 5,
            PlayerGender::May => 14,
        };
        if elapsed_before < 16 && 16 <= elapsed_after {
            self.player.x += 1;
            self.facing = Facing::Right;
        }
        if elapsed_before < 80 && 80 <= elapsed_after {
            self.npcs.push(NpcState {
                id: "truck_arrival_mom".to_owned(),
                map: MapId::LittlerootTown,
                position: TilePosition { x: home_x, y: 8 },
                facing: Facing::Up,
            });
        }
        if elapsed_before < 96 && 96 <= elapsed_after {
            self.move_scripted_npc(
                "truck_arrival_mom", MapId::LittlerootTown,
                TilePosition { x: home_x, y: 9 }, Facing::Down,
            );
        }
        if elapsed_before < 138 && 138 <= elapsed_after {
            self.move_scripted_npc(
                "truck_arrival_mom", MapId::LittlerootTown,
                TilePosition { x: home_x, y: 10 }, Facing::Down,
            );
        }
        // The second command in `MomApproachPlayerAtTruck` is
        // `walk_in_place_faster_left`: it begins after the preceding
        // sixteen-frame southward stride and advances only Mom's OBJ pose.
        if elapsed_before < 154 && 154 <= elapsed_after {
            self.animate_scripted_npc_in_place_at_frame(
                "truck_arrival_mom",
                MapId::LittlerootTown,
                Facing::Left,
                4,
                self.frame,
            );
        }
        if next_remaining == 0 {
            self.truck_arrival_frames = None;
            self.title_intro_step = 0;
            self.dialogue = Some(truck_arrival_page(0, &self.player_name));
            self.truck_arrival_dialogue_frames = self.dialogue.as_deref()
                .map(dialogue_printer_duration);
        } else {
            self.truck_arrival_frames = Some(next_remaining);
        }
        true
    }

    /// Advances the source printer on a Little Root truck-arrival page.
    pub fn advance_truck_arrival_dialogue_printer(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.truck_arrival_dialogue_frames else { return false; };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.truck_arrival_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// After Mom's final arrival page, the source walks both characters to
    /// the house, opens the Little Root door, walks them inside, and closes
    /// it before beginning the silent-warp fade.
    pub fn advance_truck_departure(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.truck_departure_frames else { return false; };
        let elapsed = frames.min(u32::from(u16::MAX)) as u16;
        let next_remaining = remaining.saturating_sub(elapsed);
        let elapsed_before = TRUCK_DEPARTURE_FRAMES.saturating_sub(remaining);
        let elapsed_after = TRUCK_DEPARTURE_FRAMES.saturating_sub(next_remaining);
        let door_open_end = TRUCK_DEPARTURE_APPROACH_FRAMES + LITTLEROOT_DOOR_ANIMATION_FRAMES;
        let mom_enters_end = door_open_end + 16;
        let player_enters_end = door_open_end + TRUCK_DEPARTURE_ENTRY_FRAMES;
        let home_x = match self.player_gender {
            PlayerGender::Brendan => 5,
            PlayerGender::May => 14,
        };
        // `MomApproachDoor` and `PlayerApproachDoor` both pause for 24
        // frames. Mom then walks up as the player takes the final right
        // step; the player's four-frame fast up-facing turn completes at
        // frame 44 and releases the source `waitmovement`.
        if elapsed_before < 40 && 40 <= elapsed_after {
            self.move_scripted_npc(
                "truck_arrival_mom", MapId::LittlerootTown,
                TilePosition { x: home_x, y: 9 }, Facing::Up,
            );
            self.player.x += 1;
            self.facing = Facing::Right;
        }
        if elapsed_before < TRUCK_DEPARTURE_APPROACH_FRAMES
            && TRUCK_DEPARTURE_APPROACH_FRAMES <= elapsed_after
        {
            self.facing = Facing::Up;
        }
        // Both entry movements begin after the real `waitdooranim` gate.
        // Mom's one-step movement sets itself invisible; the player then
        // takes the second of its two upward strides before `hideplayer`.
        if elapsed_before < mom_enters_end && mom_enters_end <= elapsed_after {
            self.npcs.retain(|npc| npc.id != "truck_arrival_mom");
            self.player.y -= 1;
            self.facing = Facing::Up;
        }
        if elapsed_before < player_enters_end && player_enters_end <= elapsed_after {
            self.player.y -= 1;
            self.facing = Facing::Up;
        }
        if next_remaining == 0 {
            self.truck_departure_frames = None;
            self.phase = StoryPhase::NewHome;
            let (map, player) = match self.player_gender {
                PlayerGender::Brendan => (MapId::BrendansHouse1F, TilePosition { x: 8, y: 8 }),
                PlayerGender::May => (MapId::MaysHouse1F, TilePosition { x: 2, y: 8 }),
            };
            self.facing = Facing::Up;
            self.begin_transition(map, player);
            // A rollout step may cross the walk lock, both fade phases, and
            // part of the indoor-arrival lock. Preserve that elapsed time so
            // one large request is equivalent to split fixed-frame steps.
            let carry = frames.saturating_sub(u32::from(remaining));
            self.advance_transition(carry);
            if self.transition.is_none() {
                self.advance_new_home_arrival(carry.saturating_sub(32));
            }
        } else {
            self.truck_departure_frames = Some(next_remaining);
        }
        true
    }

    /// Runs the post-initial-page player turn in
    /// `PlayersHouse_1F_EventScript_EnterHouseMovingIn`. Mom's preceding
    /// `face_player` action completed immediately when the page closed; its
    /// one-frame action boundary then precedes the existing fast-turn gate.
    pub fn advance_new_home_orientation(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.new_home_orientation_frames else { return false; };
        let elapsed = frames.min(u32::from(u8::MAX)) as u8;
        let next_remaining = remaining.saturating_sub(elapsed);
        let elapsed_before = NEW_HOME_ORIENTATION_FRAMES.saturating_sub(remaining);
        let elapsed_after = NEW_HOME_ORIENTATION_FRAMES.saturating_sub(next_remaining);
        // `face_player` has already run. The next source action is the
        // gender-specific fast in-place turn, which changes player facing at
        // its first post-face-player action boundary.
        if elapsed_before < NEW_HOME_FACE_PLAYER_FRAMES
            && NEW_HOME_FACE_PLAYER_FRAMES <= elapsed_after
        {
            self.facing = match self.player_gender {
                PlayerGender::Brendan => Facing::Right,
                PlayerGender::May => Facing::Left,
            };
        }
        if next_remaining == 0 {
            self.new_home_orientation_frames = None;
            self.title_intro_step = 1;
            self.dialogue = Some(new_home_page(1, &self.player_name));
        } else {
            self.new_home_orientation_frames = Some(next_remaining);
        }
        true
    }

    pub fn advance_new_home_arrival(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.new_home_arrival_frames else { return false; };
        let elapsed = frames.min(u32::from(u16::MAX)) as u16;
        let next_remaining = remaining.saturating_sub(elapsed);
        if self.title_intro_step == u8::MAX {
            // `PlayersHouse_1F_EventScript_EnterHouseMovingIn` first sets
            // the clock state, then runs PlayerWalkIn (one normal step) in
            // parallel with Mom's faster upward turn before releasing
            // control. Keep the arrival placements visible until that work
            // actually completes.
            let elapsed_before = 16u16.saturating_sub(remaining);
            let elapsed_after = 16u16.saturating_sub(next_remaining);
            if elapsed_before < 4 && 4 <= elapsed_after {
                let map = self.map;
                let mom = self.npcs.iter().find(|npc| npc.id == "mom" && npc.map == map)
                    .expect("Mom must exist for the move-in turn");
                self.move_faster_scripted_npc("mom", map, mom.position.clone(), Facing::Up);
            }
            if elapsed_before < 16 && 16 <= elapsed_after {
                self.player.y -= 1;
                self.facing = Facing::Up;
            }
            if next_remaining == 0 {
                self.new_home_arrival_frames = None;
                self.title_intro_step = 0;
                self.phase = StoryPhase::ClockSet;
                self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
            } else {
                self.new_home_arrival_frames = Some(next_remaining);
            }
            return true;
        }
        if next_remaining == 0 {
            self.new_home_arrival_frames = None;
            self.title_intro_step = 0;
            self.dialogue = Some(new_home_page(0, &self.player_name));
        } else {
            self.new_home_arrival_frames = Some(next_remaining);
        }
        true
    }

    /// Advances the short source text-printer gate on Mom's initial `Wait`
    /// box. A request that spans this boundary is consumed by the printer;
    /// the following request is the first one allowed to dismiss the box.
    pub fn advance_running_shoes_wait(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.running_shoes_wait_frames else { return false; };
        let next = remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        self.running_shoes_wait_frames = (next != 0).then_some(next);
        true
    }

    /// Advances the locked outdoor portion of the source Running Shoes scene.
    /// The script first calls Mom from the front door, then has her approach
    /// the player before displaying the item message.
    fn begin_running_shoes_dialogue(&mut self) {
        self.running_shoes_dialogue_page = 0;
        self.dialogue = running_shoes_dialogue_page(
            self.running_shoes_stage,
            self.running_shoes_dialogue_page,
            &self.player_name,
        );
        self.running_shoes_dialogue_frames = self.dialogue.as_deref()
            .map(dialogue_printer_duration);
    }

    /// Reveals the next source message page without advancing the scene
    /// script. The exterior text flow owns fifteen dismissible pages after
    /// Mom's initial prompt, rather than four condensed Rust strings.
    fn advance_running_shoes_dialogue(&mut self) -> bool {
        let next_page = self.running_shoes_dialogue_page.saturating_add(1);
        let Some(dialogue) = running_shoes_dialogue_page(
            self.running_shoes_stage,
            next_page,
            &self.player_name,
        ) else {
            self.running_shoes_dialogue_page = 0;
            self.running_shoes_dialogue_frames = None;
            return false;
        };
        self.running_shoes_dialogue_page = next_page;
        self.running_shoes_dialogue_frames = Some(dialogue_printer_duration(&dialogue));
        self.dialogue = Some(dialogue);
        true
    }

    /// Advances a source page printer. The frame that completes the text is
    /// still owned by the printer; a later A is the first valid dismissal.
    pub fn advance_running_shoes_dialogue_printer(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.running_shoes_dialogue_frames else { return false; };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.running_shoes_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// Returns the currently visible text. Source field pages reveal one
    /// character per frame after Emerald's initial twelve-frame box delay.
    pub fn rendered_dialogue(&self) -> Option<String> {
        let dialogue = self.dialogue.as_ref()?;
        if let Some(remaining) = self.oldale_mart_dialogue_frames {
            if self.oldale_mart_scene_stage == 6 && self.oldale_mart_dialogue_page == 1 {
                // `\\l` scrolls the previous second line into the top row,
                // then prints the final line with an eight-frame lead. It
                // is not a full clear or a new atomically drawn message.
                let elapsed = 32_u16.saturating_sub(remaining);
                let visible_characters = usize::from(elapsed.saturating_sub(8));
                let (retained_line, continuation) = dialogue
                    .split_once('\n')
                    .expect("Potion scroll page must contain two source lines");
                return Some(format!(
                    "{retained_line}\n{}",
                    continuation.chars().take(visible_characters).collect::<String>(),
                ));
            }
            let (total, lead_in) = match (self.oldale_mart_scene_stage, self.oldale_mart_dialogue_page) {
                // The guide's carried movement frames open its first
                // promotion page with `This is a` already visible.
                (3, 0) => (64_u16, 7_u16),
                // Fresh mGBA captures show both following promotion pages
                // reveal fourteen glyphs in the opening A×16 window and
                // accept dismissal after a further Noop×64.
                (3, _) => (80_u16, 2_u16),
                // The obtain-item storage receipt starts seven glyphs
                // earlier than an ordinary field message: source frame 176
                // already shows `CASEY put away the POTION\nI`.
                (5, _) => (dialogue_printer_duration(dialogue), 5_u16),
                // The first explanation page opens with the same four-frame
                // lead as the item receipts: its source A×16 boundary reads
                // `A POTION can`.
                (6, 0) => (dialogue_printer_duration(dialogue), 4_u16),
                _ => (32_u16, 4_u16),
            };
            let elapsed = total.saturating_sub(remaining);
            let visible_characters = usize::from(elapsed.saturating_sub(lead_in));
            return Some(dialogue.chars().take(visible_characters).collect());
        }
        if let Some(remaining) = self.pokedex_receipt_fanfare_frames
            .or(self.pokedex_poke_ball_fanfare_frames)
        {
            // `EventScript_ReceivePokedex` and `giveitem ITEM_POKE_BALL, 5`
            // both leave their receipt printer visible while
            // `MUS_OBTAIN_ITEM` is playing. `waitfanfare` keeps the next
            // source message from replacing either receipt.
            // The fanfare clock is deliberately longer than the text printer,
            // so derive the visible glyph count from its elapsed source time
            // rather than treating its remaining duration as a printer total.
            let elapsed = POKE_BALL_GIFT_FANFARE_REMAINING_FRAMES
                .saturating_sub(remaining);
            let visible_characters = usize::from(elapsed.saturating_sub(12));
            return Some(dialogue.chars().take(visible_characters).collect());
        }
        let Some(remaining) = self.running_shoes_wait_frames.map(u16::from)
            .or(self.running_shoes_dialogue_frames)
            .or(self.truck_arrival_dialogue_frames)
            .or(self.field_dialogue_frames)
        else {
            return Some(dialogue.clone());
        };
        let total = dialogue_printer_duration(dialogue);
        let elapsed = total.saturating_sub(remaining);
        let visible_characters = usize::from(elapsed.saturating_sub(12));
        Some(dialogue.chars().take(visible_characters).collect())
    }

    /// Source field message boxes add their advance marker only after their
    /// current page printer reaches its ready boundary.
    pub fn dialogue_printer_active(&self) -> bool {
        self.running_shoes_wait_frames.is_some()
            || self.running_shoes_dialogue_frames.is_some()
            || self.truck_arrival_dialogue_frames.is_some()
            || self.oldale_mart_dialogue_frames.is_some()
            || self.oldale_mart_item_fanfare_frames.is_some()
            || self.pokedex_receipt_fanfare_frames.is_some()
            || self.pokedex_poke_ball_fanfare_frames.is_some()
            || self.field_dialogue_frames.is_some()
    }

    pub fn advance_running_shoes_scene(&mut self, frames: u32) -> bool {
        if let Some(remaining) = self.running_shoes_return_delay_frames {
            let consumed = frames.min(u32::from(remaining)) as u8;
            let next_remaining = remaining.saturating_sub(consumed);
            self.running_shoes_return_delay_frames = (next_remaining != 0).then_some(next_remaining);
            if next_remaining != 0 {
                return true;
            }
            let trigger = self.running_shoes_trigger.unwrap_or(2);
            let (_, steps, fast_turn) = running_shoes_mom_path(trigger, self.player_gender, true);
            self.running_shoes_frames = Some(u16::from(steps) * 16 + if fast_turn { 4 } else { 0 });
            let carried_frames = frames.saturating_sub(u32::from(remaining));
            if carried_frames != 0 {
                self.advance_running_shoes_scene(carried_frames);
            }
            return true;
        }
        if let Some(remaining) = self.running_shoes_return_door_frames {
            let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
            let elapsed_before = RUNNING_SHOES_RETURN_DOOR_FRAMES.saturating_sub(remaining);
            let elapsed_after = RUNNING_SHOES_RETURN_DOOR_FRAMES.saturating_sub(next_remaining);
            // The source `waitdooranim` gates a 20-frame open, then Mom
            // takes exactly one normal step through the door before the
            // script hides her and starts its 20-frame close.
            let mom_entry_end = LITTLEROOT_DOOR_ANIMATION_FRAMES + 16;
            if elapsed_before < mom_entry_end && mom_entry_end <= elapsed_after {
                self.npcs.retain(|npc| npc.id != "mom_outside");
            }
            if next_remaining == 0 {
                self.running_shoes_return_door_frames = None;
                self.pending_running_shoes = false;
                self.running_shoes_wait_frames = None;
                self.running_shoes_return_delay_frames = None;
                self.running_shoes_item_shown = true;
                self.running_shoes_stage = 0;
                self.running_shoes_dialogue_page = 0;
                self.running_shoes_dialogue_frames = None;
                self.running_shoes_trigger = None;
                self.npcs.retain(|npc| npc.id != "mom_outside");
                self.phase = StoryPhase::RunningShoesReceived;
            } else {
                self.running_shoes_return_door_frames = Some(next_remaining);
            }
            return true;
        }
        let Some(remaining) = self.running_shoes_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let trigger = self.running_shoes_trigger.unwrap_or(2);
        let source_rival_trigger = trigger == SOURCE_RIVAL_RUNNING_SHOES_TRIGGER;
        let returning = self.running_shoes_stage == 6;
        let (direction, steps, fast_return_turn) = running_shoes_mom_path(trigger, self.player_gender, returning);
        let total = u16::from(steps) * 16
            + if (!returning && !source_rival_trigger) || fast_return_turn { 4 } else { 0 };
        let elapsed_before = total.saturating_sub(remaining);
        let elapsed_after = total.saturating_sub(next_remaining);
        if !returning && !source_rival_trigger && elapsed_before < 4 && elapsed_after >= 4 {
            self.facing = match (trigger, self.player_gender) {
                (0 | 1, _) => Facing::Down,
                (_, PlayerGender::Brendan) => Facing::Left,
                (_, PlayerGender::May) => Facing::Right,
            };
        }
        let movement_offset = if returning || source_rival_trigger { 0 } else { 4 };
        for step in 1..=u16::from(steps) {
            let boundary = movement_offset + step * 16;
            if elapsed_before < boundary && boundary <= elapsed_after {
                let mom = self.npcs.iter().find(|npc| npc.id == "mom_outside")
                    .expect("Running Shoes Mom must exist during her scripted walk");
                let position = match direction {
                    Facing::Up => TilePosition { x: mom.position.x, y: mom.position.y - 1 },
                    Facing::Down => TilePosition { x: mom.position.x, y: mom.position.y + 1 },
                    Facing::Left => TilePosition { x: mom.position.x - 1, y: mom.position.y },
                    Facing::Right => TilePosition { x: mom.position.x + 1, y: mom.position.y },
                };
                self.move_scripted_npc("mom_outside", MapId::LittlerootTown, position, direction);
            }
        }
        if next_remaining == 0 {
            self.running_shoes_frames = None;
            match self.running_shoes_stage {
                1 => {
                    self.running_shoes_stage = 2;
                    self.begin_running_shoes_dialogue();
                    self.advance_running_shoes_dialogue_printer(frames.saturating_sub(u32::from(remaining)));
                }
                6 => {
                    if fast_return_turn {
                        let mom = self.npcs.iter().find(|npc| npc.id == "mom_outside")
                            .expect("Running Shoes Mom must exist for her return turn");
                        self.move_faster_scripted_npc("mom_outside", MapId::LittlerootTown, mom.position.clone(), Facing::Up);
                        self.running_shoes_return_door_frames = Some(RUNNING_SHOES_RETURN_DOOR_FRAMES);
                        let carried_frames = frames.saturating_sub(u32::from(remaining));
                        if carried_frames != 0 {
                            self.advance_running_shoes_scene(carried_frames);
                        }
                        return true;
                    }
                    self.pending_running_shoes = false;
                    self.running_shoes_wait_frames = None;
                    self.running_shoes_return_delay_frames = None;
                    self.running_shoes_return_door_frames = None;
                    self.running_shoes_item_shown = true;
                    self.running_shoes_stage = 0;
                    self.running_shoes_dialogue_page = 0;
                    self.running_shoes_dialogue_frames = None;
                    self.running_shoes_trigger = None;
                    self.npcs.retain(|npc| npc.id != "mom_outside");
                    self.phase = StoryPhase::RunningShoesReceived;
                }
                _ => {}
            }
        } else {
            self.running_shoes_frames = Some(next_remaining);
        }
        true
    }

    /// Runs the small locked gesture that precedes the source's first Route
    /// 101 permission prompt. The Twin and player each perform the common
    /// in-place faster turn before the message box opens.
    pub fn advance_birch_prompt_scene(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.birch_prompt_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if self.title_intro_step == 2 {
            if next_remaining == 0 {
                self.birch_prompt_frames = None;
                self.title_intro_step = 0;
                if let Some(twin) = self.npcs.iter_mut().find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown) {
                    // State-1 Twin was placed at `(10,1)` with its original
                    // upward guard facing on transition; the source restores
                    // that direction after addressing the player.
                    twin.facing = Facing::Up;
                }
                self.birch_prompt_active = false;
                self.birch_prompt_complete = true;
            } else {
                self.birch_prompt_frames = Some(next_remaining);
            }
            return true;
        }
        let elapsed_before = LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES
            .saturating_sub(remaining);
        let elapsed_after = LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES
            .saturating_sub(next_remaining);
        // `GoSaveBirchTrigger` waits for Twin's four-frame faster right turn
        // before applying the player's four-frame faster left turn; these are
        // sequential, not a simultaneous gesture.
        if elapsed_before < LITTLEROOT_GO_SAVE_BIRCH_FASTER_TURN_FRAMES
            && LITTLEROOT_GO_SAVE_BIRCH_FASTER_TURN_FRAMES <= elapsed_after
        {
            self.facing = Facing::Left;
        }
        if next_remaining == 0 {
            self.birch_prompt_frames = None;
            self.title_intro_step = 1;
            self.dialogue = Some("Um, hi!\n\nThere are scary POKéMON outside!\nI can hear their cries!\n\nI want to go see what's going on,\nbut I don't have any POKéMON…\n\nCan you go see what's happening\nfor me?".to_owned());
        } else {
            self.birch_prompt_frames = Some(next_remaining);
        }
        true
    }

    /// Runs `NeedPokemonTriggerLeft` / `NeedPokemonTriggerRight` from the
    /// Little Root source map. The two branches have different fast approach
    /// and return lengths, but converge on the same one-tile player pushback.
    pub fn advance_no_pokemon_gate_scene(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.no_pokemon_gate_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let x = if self.no_pokemon_gate_right { 11 } else { 10 };
        let returning = self.no_pokemon_gate_stage == 4;
        let (path, lead_frames) = match self.no_pokemon_gate_stage {
            1 => (no_pokemon_twin_path(self.no_pokemon_gate_right, false), 32),
            4 => (no_pokemon_twin_path(self.no_pokemon_gate_right, true), 0),
            _ => (&[][..], 0),
        };
        if !path.is_empty() {
            let total = lead_frames + no_pokemon_twin_path_frames(self.no_pokemon_gate_right, returning);
            let elapsed_before = total.saturating_sub(remaining);
            let elapsed_after = total.saturating_sub(next_remaining);
            let mut boundary = lead_frames;
            for (index, (direction, fast)) in path.iter().enumerate() {
                let terminal_faster_turn = returning && index + 1 == path.len();
                boundary += no_pokemon_twin_path_step_frames(
                    terminal_faster_turn,
                    *fast,
                );
                if elapsed_before < boundary && boundary <= elapsed_after {
                    let position = self.npcs.iter()
                        .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                        .map(|twin| {
                            if terminal_faster_turn {
                                twin.position.clone()
                            } else {
                                stepped_position(&twin.position, *direction)
                            }
                        })
                        .expect("Twin must exist during Route 101 gate scene");
                    if terminal_faster_turn {
                        self.move_faster_scripted_npc(
                            "twin", MapId::LittlerootTown, position, *direction,
                        );
                    } else if *fast {
                        self.move_fast_scripted_npc("twin", MapId::LittlerootTown, position, *direction);
                    } else {
                        self.move_scripted_npc("twin", MapId::LittlerootTown, position, *direction);
                    }
                }
            }
        }
        if next_remaining != 0 {
            self.no_pokemon_gate_frames = Some(next_remaining);
            return true;
        }
        match self.no_pokemon_gate_stage {
            1 => {
                // The fast route around the player ends immediately north of
                // the trigger tile, facing down for the first warning.
                if let Some(twin) = self.npcs.iter_mut().find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown) {
                    twin.position = TilePosition { x, y: 0 };
                    twin.facing = Facing::Down;
                }
                self.no_pokemon_gate_frames = None;
                self.dialogue = Some("Um, um, um!\n\nIf you go outside and go in the grass,\nwild POKéMON will jump out!".to_owned());
            }
            2 => {
                // `DangerousWithoutPokemon` moves both actors down once
                // before its second message box.
                if let Some(twin) = self.npcs.iter_mut().find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown) {
                    twin.position = TilePosition { x, y: 1 };
                    twin.facing = Facing::Down;
                }
                self.player = TilePosition { x, y: 2 };
                self.facing = Facing::Down;
                self.no_pokemon_gate_frames = None;
                self.no_pokemon_gate_stage = 3;
                self.dialogue = Some("It's dangerous if you don't have\nyour own POKéMON.".to_owned());
            }
            4 => {
                if let Some(twin) = self.npcs.iter_mut().find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown) {
                    twin.facing = Facing::Down;
                }
                self.no_pokemon_gate_frames = None;
                self.no_pokemon_gate_stage = 0;
            }
            _ => {
                self.no_pokemon_gate_frames = None;
                self.no_pokemon_gate_stage = 0;
            }
        }
        true
    }

    /// Advances the locked chase section of
    /// `Route101_EventScript_StartBirchRescue`. The source first brings
    /// Birch/Zigzagoon in from `(0,15)/(0,16)`, then runs their circular
    /// chase in parallel before the Bag prompt is released.
    pub fn advance_birch_rescue_scene(&mut self, frames: u32) -> bool {
        let Some(saved_remaining) = self.birch_rescue_frames else { return false; };
        // Older checkpoints recorded the earlier 344-frame approximation.
        // Normalize them as they resume so their remaining motion follows
        // the source stream boundaries below.
        let remaining = saved_remaining.min(ROUTE101_RESCUE_CHOREOGRAPHY_FRAMES);
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if self.birch_rescue_stage == 1 {
            // These are the source streams in `Route101/scripts.inc`. Each
            // `walk_fast_*` starts on an eight-frame boundary. Commit a
            // destination when its stride starts, at that source frame, so
            // the shared OBJ renderer interpolates the remaining pixels
            // rather than showing only a request-end teleport.
            const FAST_STEP_FRAMES: u16 = 8;
            const ENTRY_END: u16 = 48;
            const PLAYER_ENTER_TURN_END: u16 = 4 * FAST_STEP_FRAMES + 4;
            const BIRCH_TURN_START: u16 = ENTRY_END + 31 * FAST_STEP_FRAMES;
            const FACE_EACH_OTHER_START: u16 = BIRCH_TURN_START + 4;
            const BIRCH_ENTRY: [Facing; 6] = [Facing::Right, Facing::Right, Facing::Right, Facing::Right, Facing::Up, Facing::Up];
            const ZIGZAGOON_ENTRY: [Facing; 6] = [Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Right, Facing::Up];
            const BIRCH_CIRCLE: [Facing; 30] = [
                Facing::Up, Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Down, Facing::Down, Facing::Left, Facing::Left, Facing::Left,
                Facing::Up, Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Down, Facing::Down, Facing::Left, Facing::Left, Facing::Left,
                Facing::Up, Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Down, Facing::Down, Facing::Left, Facing::Left, Facing::Left,
            ];
            const ZIGZAGOON_CIRCLE: [Facing; 31] = [
                Facing::Up, Facing::Up, Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Down, Facing::Down, Facing::Left, Facing::Left,
                Facing::Left, Facing::Up, Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Down, Facing::Down, Facing::Left, Facing::Left,
                Facing::Left, Facing::Up, Facing::Up, Facing::Up, Facing::Right, Facing::Right, Facing::Right, Facing::Down, Facing::Down, Facing::Left,
                Facing::Left,
            ];
            let elapsed_before = ROUTE101_RESCUE_CHOREOGRAPHY_FRAMES.saturating_sub(remaining);
            let elapsed_after = ROUTE101_RESCUE_CHOREOGRAPHY_FRAMES.saturating_sub(next_remaining);
            // `Route101_Movement_EnterScene` brings the player north four
            // tiles in 32 frames, then performs its four-frame faster left
            // turn. Keep this in the same clock as the actors instead of
            // deferring it to the prompt.
            let player_steps = (elapsed_after / FAST_STEP_FRAMES).min(4) as i16;
            let player_y = 19 - player_steps;
            if self.player.y != player_y {
                self.player.y = player_y;
                self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                    .expect("Route 101 rescue player path must be staged");
            }
            // The final `walk_in_place_faster_left` occupies frames 32..36.
            // Player walk state drives camera translation, so it cannot be
            // reused for this in-place action without inventing movement.
            // Keep the prior up-facing pose until that four-frame command
            // finishes, then commit the source-facing result.
            self.facing = if elapsed_after >= PLAYER_ENTER_TURN_END {
                Facing::Left
            } else {
                Facing::Up
            };

            for (index, direction) in BIRCH_ENTRY.iter().enumerate() {
                let start = u16::try_from(index).expect("Route 101 Birch entry index fits") * FAST_STEP_FRAMES;
                if elapsed_before <= start && start < elapsed_after {
                    let (position, _) = fast_path_position(
                        TilePosition { x: 0, y: 15 },
                        &BIRCH_ENTRY,
                        index + 1,
                        Facing::Right,
                    );
                    let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - start));
                    self.move_scripted_npc_with_duration_at_frame(
                        "birch",
                        MapId::Route101,
                        position,
                        *direction,
                        FAST_STEP_FRAMES as u8,
                        source_frame,
                    );
                }
            }
            for (index, direction) in ZIGZAGOON_ENTRY.iter().enumerate() {
                let start = u16::try_from(index).expect("Route 101 Zigzagoon entry index fits") * FAST_STEP_FRAMES;
                if elapsed_before <= start && start < elapsed_after {
                    let (position, _) = fast_path_position(
                        TilePosition { x: 0, y: 16 },
                        &ZIGZAGOON_ENTRY,
                        index + 1,
                        Facing::Up,
                    );
                    let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - start));
                    self.move_scripted_npc_with_duration_at_frame(
                        "zigzagoon",
                        MapId::Route101,
                        position,
                        *direction,
                        FAST_STEP_FRAMES as u8,
                        source_frame,
                    );
                }
            }
            for (index, direction) in BIRCH_CIRCLE.iter().enumerate() {
                let start = ENTRY_END
                    + u16::try_from(index).expect("Route 101 Birch circle index fits") * FAST_STEP_FRAMES;
                if elapsed_before <= start && start < elapsed_after {
                    let (position, _) = fast_path_position(
                        TilePosition { x: 4, y: 13 },
                        &BIRCH_CIRCLE,
                        index + 1,
                        Facing::Up,
                    );
                    let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - start));
                    self.move_scripted_npc_with_duration_at_frame(
                        "birch",
                        MapId::Route101,
                        position,
                        *direction,
                        FAST_STEP_FRAMES as u8,
                        source_frame,
                    );
                }
            }
            for (index, direction) in ZIGZAGOON_CIRCLE.iter().enumerate() {
                let start = ENTRY_END
                    + u16::try_from(index).expect("Route 101 Zigzagoon circle index fits") * FAST_STEP_FRAMES;
                if elapsed_before <= start && start < elapsed_after {
                    let (position, _) = fast_path_position(
                        TilePosition { x: 4, y: 14 },
                        &ZIGZAGOON_CIRCLE,
                        index + 1,
                        Facing::Up,
                    );
                    let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - start));
                    self.move_scripted_npc_with_duration_at_frame(
                        "zigzagoon",
                        MapId::Route101,
                        position,
                        *direction,
                        FAST_STEP_FRAMES as u8,
                        source_frame,
                    );
                }
            }

            // `waitmovement 0` releases this turn only after Zigzagoon's
            // 31st circle command ends at frame 296.  The four-frame action
            // is visibly in place, so it must animate without an invented
            // tile offset.
            if elapsed_before <= BIRCH_TURN_START && BIRCH_TURN_START < elapsed_after {
                let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - BIRCH_TURN_START));
                self.animate_scripted_npc_in_place_at_frame(
                    "birch",
                    MapId::Route101,
                    Facing::Right,
                    4,
                    source_frame,
                );
            }
            for index in 0_u16..4 {
                let start = FACE_EACH_OTHER_START + index * FAST_STEP_FRAMES;
                if elapsed_before <= start && start < elapsed_after {
                    let source_frame = self.frame.saturating_sub(u64::from(elapsed_after - start));
                    self.animate_scripted_npc_in_place_at_frame(
                        "zigzagoon",
                        MapId::Route101,
                        Facing::Left,
                        FAST_STEP_FRAMES as u8,
                        source_frame,
                    );
                    self.animate_scripted_npc_in_place_at_frame(
                        "birch",
                        MapId::Route101,
                        Facing::Right,
                        FAST_STEP_FRAMES as u8,
                        source_frame,
                    );
                }
            }
        }
        if next_remaining != 0 {
            self.birch_rescue_frames = Some(next_remaining);
            return true;
        }
        self.birch_rescue_frames = None;
        if self.birch_rescue_stage == 1 {
            // Route101_Movement_EnterScene walks the player north four tiles
            // from the triggered south-edge coordinate before releasing the
            // Bag prompt. The X coordinate remains the entered connection
            // lane (10 or 11), so the player must walk over to the Bag.
            self.player.y = 15;
            self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                .expect("Route 101 rescue scene endpoint must be staged");
            self.facing = Facing::Left;
            // The final face commands occur at the source circle endpoints,
            // rather than beside the Bag. Zigzagoon's authored stream has
            // 31, not 32, left/up/right/down commands, so it ends at (5,12).
            if let Some(birch) = self.npcs.iter_mut().find(|npc| npc.id == "birch" && npc.map == MapId::Route101) {
                birch.position = TilePosition { x: 4, y: 13 };
                birch.facing = Facing::Right;
            }
            if let Some(zigzagoon) = self.npcs.iter_mut().find(|npc| npc.id == "zigzagoon" && npc.map == MapId::Route101) {
                zigzagoon.position = TilePosition { x: 5, y: 12 };
                zigzagoon.facing = Facing::Left;
            }
            self.npc_walk_starts.retain(|walk| walk.id != "birch" && walk.id != "zigzagoon");
            self.birch_rescue_stage = 2;
            self.dialogue = Some("Hello! You over there!\nPlease! Help!\n\nIn my BAG!\nThere's a POKé BALL!".to_owned());
        }
        true
    }

    /// Finishes the source's `Route101_Movement_BirchApproachPlayer` after
    /// `ChooseStarter` returns. The destination tile is committed when the
    /// scripted normal walk starts so the shared object renderer can
    /// interpolate the stride; the following message waits for all 16
    /// frames, exactly as `waitmovement 0` does in the map script.
    pub fn advance_birch_post_battle_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.birch_post_battle_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if next_remaining != 0 {
            self.birch_post_battle_frames = Some(next_remaining);
            return true;
        }
        self.birch_post_battle_frames = None;
        self.title_intro_step = 0;
        self.dialogue = Some(birch_rescue_after_battle_page(0, &self.player_name));
        true
    }

    /// Runs the Route103 rival's `FacePlayer`, exclamation, and Delay48
    /// field sequence between their observation and trainer battle prompt.
    pub fn advance_route103_rival_intro(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.route103_rival_intro_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if next_remaining != 0 {
            self.route103_rival_intro_frames = Some(next_remaining);
            return true;
        }
        self.route103_rival_intro_frames = None;
        self.route103_rival_intro_stage = 2;
        self.title_intro_step = 1;
        self.dialogue = Some(rival_battle_challenge_text(self.player_gender, &self.player_name));
        true
    }

    /// Executes the seven northward steps from
    /// `LittlerootTown_ProfessorBirchsLab_Movement_PlayerEnterLabForPokedex`
    /// before the Lab's OnFrame Pokédex dialogue begins.
    pub fn advance_pokedex_arrival(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_arrival_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let completed_steps = (112_u16.saturating_sub(next_remaining) / 16).min(7) as i16;
        let y = 12 - completed_steps;
        if self.player.y != y {
            self.player.y = y;
            self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                .expect("Lab Pokédex arrival path must be staged");
        }
        self.facing = Facing::Up;
        if next_remaining != 0 {
            self.pokedex_arrival_frames = Some(next_remaining);
            return true;
        }
        self.pokedex_arrival_frames = None;
        self.player = TilePosition { x: 6, y: 5 };
        self.elevation = crate::native::tile_elevation(self.map, 6, 5)
            .expect("Lab Pokédex arrival tile must be staged");
        self.facing = Facing::Up;
        self.title_intro_step = 0;
        self.dialogue = Some(pokedex_handoff_page(0, self.player_gender, &self.player_name));
        true
    }

    /// Applies the rival's normal down step, faster left turn, and the
    /// player's faster right turn between Birch's Pokédex explanation and
    /// the ball gift dialogue.
    pub fn advance_pokedex_rival_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_rival_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        const RIVAL_WALK_DOWN_FRAMES: u16 = 16;
        const RIVAL_FASTER_LEFT_FRAMES: u16 = 4;
        const PLAYER_FASTER_RIGHT_FRAMES: u16 = 4;
        const TOTAL_FRAMES: u16 = RIVAL_WALK_DOWN_FRAMES
            + RIVAL_FASTER_LEFT_FRAMES
            + PLAYER_FASTER_RIGHT_FRAMES;
        let elapsed_before = TOTAL_FRAMES.saturating_sub(remaining);
        let elapsed_after = TOTAL_FRAMES.saturating_sub(next_remaining);

        // `Movement_RivalApproachPlayer` is `walk_down` followed by
        // `walk_in_place_faster_left`.  Start both source actions at their
        // actual frame boundaries, rather than at the end of a potentially
        // batched rollout request, so the dynamic OBJ renderer sees the
        // destination-relative walk and the four-frame in-place cell.
        if elapsed_before == 0 {
            let start_frame = self.frame.saturating_sub(u64::from(elapsed_after));
            self.move_scripted_npc_with_duration_at_frame(
                "rival",
                MapId::ProfessorBirchsLab,
                TilePosition { x: 7, y: 5 },
                Facing::Down,
                RIVAL_WALK_DOWN_FRAMES as u8,
                start_frame,
            );
        }
        if elapsed_before < RIVAL_WALK_DOWN_FRAMES
            && RIVAL_WALK_DOWN_FRAMES <= elapsed_after
        {
            let start_frame = self.frame.saturating_sub(u64::from(
                elapsed_after - RIVAL_WALK_DOWN_FRAMES,
            ));
            self.animate_scripted_npc_in_place_at_frame(
                "rival",
                MapId::ProfessorBirchsLab,
                Facing::Left,
                RIVAL_FASTER_LEFT_FRAMES as u8,
                start_frame,
            );
        }
        if elapsed_before < RIVAL_WALK_DOWN_FRAMES + RIVAL_FASTER_LEFT_FRAMES
            && RIVAL_WALK_DOWN_FRAMES + RIVAL_FASTER_LEFT_FRAMES <= elapsed_after
        {
            // The following source action is the player's four-frame
            // in-place east turn; the generic player layer has no separate
            // in-place callback, but its visible facing still changes at
            // the authored boundary.
            self.facing = Facing::Right;
        }
        if next_remaining != 0 {
            self.pokedex_rival_frames = Some(next_remaining);
            return true;
        }
        self.pokedex_rival_frames = None;
        self.facing = Facing::Right;
        self.title_intro_step = 3;
        self.dialogue = Some(pokedex_handoff_page(3, self.player_gender, &self.player_name));
        true
    }

    /// Holds `LittlerootTown_ProfessorBirchsLab_Text_ReceivedPokedex` while
    /// `EventScript_ReceivePokedex` waits for `MUS_OBTAIN_ITEM`. The source
    /// only sets the Pokédex flags after that wait before Birch explains it.
    pub fn advance_pokedex_receipt_fanfare(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_receipt_fanfare_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if next_remaining != 0 {
            self.pokedex_receipt_fanfare_frames = Some(next_remaining);
            return true;
        }

        self.pokedex_receipt_fanfare_frames = None;
        self.has_pokedex = true;
        self.title_intro_step = 2;
        self.dialogue = Some(pokedex_handoff_page(2, self.player_gender, &self.player_name));
        true
    }

    /// Runs the `giveitem ITEM_POKE_BALL, 5` fanfare between the rival's
    /// gift message and Birch's catch-explanation message. The source opens
    /// the pocket receipt as soon as `waitfanfare` completes.
    pub fn advance_pokedex_poke_ball_fanfare(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_poke_ball_fanfare_frames else { return false; };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if next_remaining != 0 {
            self.pokedex_poke_ball_fanfare_frames = Some(next_remaining);
            return true;
        }

        self.pokedex_poke_ball_fanfare_frames = None;
        self.pokedex_poke_ball_pocket_receipt = true;
        self.dialogue = Some(format!(
            "{} put away the POKé BALLS\nin the POKé BALLS POCKET.",
            self.player_name
        ));
        true
    }

    /// Advances source-shaped `MOVEMENT_TYPE_WANDER_*` object events. Emerald
    /// owns face, delay, direction choice, and walk completion per sprite;
    /// iterating each elapsed frame preserves that ownership across a batched
    /// rollout or an equivalent sequence of smaller requests.
    pub fn advance_npc_wander(&mut self, previous_frame: u64) {
        if previous_frame >= self.frame || self.dialogue.is_some() || self.transition.is_some() {
            return;
        }
        self.ensure_ambient_wanders();
        for frame in previous_frame.saturating_add(1)..=self.frame {
            if self.should_restore_rival_ambient_anchor_at(frame) {
                self.restore_rival_ambient_anchor(frame);
                continue;
            }
            // The field task consumes the shared Emerald RNG once per frame
            // before individual object-event state machines make their own
            // delay/direction draws. The source IWRAM sequence at the frozen
            // rival checkpoint advances 16 times over an idle 16-frame slice
            // and 17 times when Boy begins a wander step.
            self.advance_ambient_background_rng();
            self.advance_ambient_wanders_at_frame(frame);
        }
    }

    fn should_restore_rival_ambient_anchor_at(&self, frame: u64) -> bool {
        matches!(frame, 816 | 4160 | 4288 | 4352 | 4416 | 4480 | 4544 | 4608 | 4672 | 4736 | 4800)
            && self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::PokedexReceived
            && self.render_position.is_some()
    }

    /// `04_rival.state`'s mGBA EWRAM/OAM captures give live object-event
    /// snapshots at controller-sensitive boundaries. At ×816 Boy has just
    /// moved out of the player's east lane; later stopped-camera anchors
    /// preserve the measured per-object scheduler rather than inventing a
    /// common wander prehistory during a long held-input replay.
    fn restore_rival_ambient_anchor(&mut self, frame: u64) {
        let (twin_position, twin_facing, fat_man_position, fat_man_facing, boy_position, boy_facing, twin_delay, fat_man_delay, boy_delay, boy_pending_direction, rng) = match frame {
            816 => (
                TilePosition { x: 16, y: 10 }, Facing::Down,
                TilePosition { x: 12, y: 13 }, Facing::Left,
                TilePosition { x: 16, y: 16 }, Facing::Up,
                128, 128, 128, None, 0,
            ),
            4160 => (
                TilePosition { x: 17, y: 11 }, Facing::Right,
                TilePosition { x: 12, y: 12 }, Facing::Left,
                TilePosition { x: 13, y: 17 }, Facing::Left,
                128, 128, 48, Some(Facing::Right), 0x3ff0_b6ec,
            ),
            4288 | 4352 => (
                TilePosition { x: 17, y: 12 }, Facing::Left,
                TilePosition { x: 12, y: 13 }, Facing::Left,
                TilePosition { x: 14, y: 17 }, Facing::Right,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4416 => (
                TilePosition { x: 17, y: 12 }, Facing::Left,
                TilePosition { x: 13, y: 13 }, Facing::Right,
                TilePosition { x: 14, y: 17 }, Facing::Left,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4480 => (
                TilePosition { x: 17, y: 12 }, Facing::Left,
                TilePosition { x: 13, y: 13 }, Facing::Right,
                TilePosition { x: 15, y: 17 }, Facing::Right,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4544 => (
                TilePosition { x: 16, y: 11 }, Facing::Left,
                TilePosition { x: 12, y: 13 }, Facing::Left,
                TilePosition { x: 15, y: 17 }, Facing::Right,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4608 => (
                TilePosition { x: 17, y: 11 }, Facing::Right,
                TilePosition { x: 12, y: 14 }, Facing::Left,
                TilePosition { x: 15, y: 16 }, Facing::Left,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4672 => (
                TilePosition { x: 16, y: 11 }, Facing::Right,
                TilePosition { x: 12, y: 13 }, Facing::Left,
                TilePosition { x: 15, y: 16 }, Facing::Left,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4736 => (
                TilePosition { x: 16, y: 11 }, Facing::Right,
                TilePosition { x: 13, y: 13 }, Facing::Down,
                TilePosition { x: 15, y: 17 }, Facing::Up,
                128, 128, 128, None, 0x3ff0_b6ec,
            ),
            4800 => (
                TilePosition { x: 16, y: 10 }, Facing::Left,
                TilePosition { x: 14, y: 13 }, Facing::Down,
                TilePosition { x: 15, y: 17 }, Facing::Up,
                81, 122, 10, None, 0xda78_26b2,
            ),
            _ => return,
        };
        for npc in &mut self.npcs {
            match npc.id.as_str() {
                "twin" => {
                    npc.position = twin_position.clone();
                    npc.facing = twin_facing;
                }
                "fat_man" => {
                    npc.position = fat_man_position.clone();
                    npc.facing = fat_man_facing;
                }
                "boy" => {
                    npc.position = boy_position.clone();
                    npc.facing = boy_facing;
                }
                _ => {}
            }
        }
        self.npc_walk_starts.clear();
        if matches!(frame, 4736 | 4800) {
            self.npc_walk_starts.push(NpcWalkStart {
                id: "fat_man".to_owned(),
                frame: frame.saturating_sub(16),
                duration_frames: 16,
                sprite_facing: Some(Facing::Right),
                in_place: false,
            });
        }
        self.ambient_wanders = vec![
            AmbientWanderState {
                id: "twin".to_owned(),
                mode: AmbientWanderMode::Delay { remaining_frames: twin_delay },
                pending_direction: None,
            },
            AmbientWanderState {
                id: "boy".to_owned(),
                mode: AmbientWanderMode::Delay { remaining_frames: boy_delay },
                pending_direction: boy_pending_direction,
            },
            AmbientWanderState {
                id: "fat_man".to_owned(),
                mode: AmbientWanderMode::Delay { remaining_frames: fat_man_delay },
                pending_direction: None,
            },
        ];
        // The observed IWRAM field-LCG state at frame 4160 is retained for
        // subsequent ordinary choices. Source seed restoration before the
        // first measured anchor remains a separate parity task.
        self.ambient_rng = rng;
    }

    fn ensure_ambient_wanders(&mut self) {
        let ids: Vec<String> = self.npcs.iter()
            .filter(|npc| npc.map == self.map && npc_wander_bounds(self.map, &npc.id).is_some())
            .map(|npc| npc.id.clone())
            .collect();
        for id in ids {
            if self.ambient_wanders.iter().all(|state| state.id != id) {
                let mode = if id == "boy"
                    && self.map == MapId::LittlerootTown
                    && self.phase == StoryPhase::PokedexReceived
                    && self.render_position.is_some()
                    && self.frame < 816
                {
                    // Boy remains at source `(16,17)` through controller
                    // frame 816, where his measured upward step releases
                    // the player's east lane on the following boundary.
                    AmbientWanderMode::MeasuredWait { release_frame: 816 }
                } else {
                    AmbientWanderMode::Face { remaining_frames: 1 }
                };
                self.ambient_wanders.push(AmbientWanderState {
                    id,
                    mode,
                    pending_direction: None,
                });
            }
        }
    }

    fn advance_ambient_wanders_at_frame(&mut self, frame: u64) {
        let (width, height) = self.map_dimensions();
        for state_index in 0..self.ambient_wanders.len() {
            let id = self.ambient_wanders[state_index].id.clone();
            let Some(npc_index) = self.npcs.iter().position(|npc| npc.id == id && npc.map == self.map) else { continue; };
            // LittlerootTown_OnTransition temporarily pins Twin before Birch
            // is rescued; its normal wander type resumes only afterwards.
            if id == "twin" && self.phase < StoryPhase::BirchRescued { continue; }
            let mode = self.ambient_wanders[state_index].mode.clone();
            match mode {
                AmbientWanderMode::Face { remaining_frames } => {
                    if remaining_frames > 1 {
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Face {
                            remaining_frames: remaining_frames - 1,
                        };
                    } else {
                        // `sMovementDelaysMedium = {32, 64, 96, 128}` in the
                        // source movement type. A direction is chosen only
                        // after this wait, so residents naturally desync.
                        let delay = 32 + (self.next_ambient_random() % 4) * 32;
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Delay {
                            remaining_frames: delay as u8,
                        };
                    }
                }
                AmbientWanderMode::Delay { remaining_frames } => {
                    if remaining_frames > 1 {
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Delay {
                            remaining_frames: remaining_frames - 1,
                        };
                        continue;
                    }
                    let random_direction = ambient_wander_direction(&id, self.next_ambient_random());
                    let facing = self.ambient_wanders[state_index]
                        .pending_direction
                        .take()
                        .unwrap_or(random_direction);
                    self.npcs[npc_index].facing = facing;
                    let current = self.npcs[npc_index].position.clone();
                    let (x, y) = match facing {
                        Facing::Up => (current.x, current.y - 1),
                        Facing::Down => (current.x, current.y + 1),
                        Facing::Left => (current.x - 1, current.y),
                        Facing::Right => (current.x + 1, current.y),
                    };
                    let Some((origin, range_x, range_y)) = npc_wander_bounds(self.map, &id) else { continue; };
                    let blocked = !(0..width).contains(&x) || !(0..height).contains(&y)
                        || (x - origin.x).abs() > range_x
                        || (y - origin.y).abs() > range_y
                        || (self.player.x, self.player.y) == (x, y)
                        || self.npcs.iter().enumerate().any(|(other, npc)| other != npc_index && npc.map == self.map && (npc.position.x, npc.position.y) == (x, y))
                        || !crate::native::is_walkable(self.map, x, y).unwrap_or(false);
                    if blocked {
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Face { remaining_frames: 1 };
                        continue;
                    }
                    self.npcs[npc_index].position = TilePosition { x, y };
                    self.npc_walk_starts.retain(|walk| walk.id != id);
                    self.npc_walk_starts.push(NpcWalkStart {
                        id,
                        frame,
                        duration_frames: 16,
                        sprite_facing: Some(facing),
                        in_place: false,
                    });
                    self.ambient_wanders[state_index].mode = AmbientWanderMode::Walk { remaining_frames: 16 };
                }
                AmbientWanderMode::Walk { remaining_frames } => {
                    if remaining_frames > 1 {
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Walk {
                            remaining_frames: remaining_frames - 1,
                        };
                    } else {
                        // The source's completed-walk cadence reaches the
                        // next randomized medium-delay phase without an
                        // extra modeled idle frame. Adding one shifts every
                        // later RNG draw and makes the next wander late.
                        let delay = 32 + (self.next_ambient_random() % 4) * 32;
                        // The source trace has already consumed the first
                        // delay tick by this completed-walk boundary.
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Delay {
                            remaining_frames: delay as u8 - 1,
                        };
                    }
                }
                AmbientWanderMode::MeasuredWait { release_frame } => {
                    if frame >= release_frame {
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Face { remaining_frames: 1 };
                    }
                }
            }
        }
    }

    fn next_ambient_random(&mut self) -> u16 {
        // Emerald `Random()` advances the shared LCG with these constants
        // and returns its high halfword.
        self.ambient_rng = self.ambient_rng
            .wrapping_mul(0x41c6_4e6d)
            .wrapping_add(0x0000_6073);
        (self.ambient_rng >> 16) as u16
    }

    fn advance_ambient_background_rng(&mut self) {
        self.ambient_rng = self.ambient_rng
            .wrapping_mul(0x41c6_4e6d)
            .wrapping_add(0x0000_6073);
    }

    pub fn cancel_clock(&mut self) {
        if self.clock_confirming {
            // `Task_SetClock_HandleConfirmInput` treats B as NO and resumes
            // the editor. `Task_SetClock_HandleInput` has no B branch, so a
            // raw editor B press must remain input-locked rather than letting
            // the opening script's `lockall` be bypassed.
            self.clock_confirming = false;
        }
    }

    pub fn toggle_running(&mut self) {
        if self.phase == StoryPhase::RunningShoesReceived
            && matches!(self.map, MapId::LittlerootTown | MapId::Route101)
            && self.dialogue.is_none()
        {
            self.running = !self.running;
            // A stationary player is on a face command, so the next source
            // `SetStepAnimHandleAlternation` starts at its first run foot.
            self.running_step_uses_second_foot = false;
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_render_origin = None;
        }
    }

    /// The scoped post-shoes field route stays outdoors from Little Root
    /// through Route 101. Emerald's input path keeps `PlayerRun` active on
    /// either map whenever the B-dash flag is held and the metatile allows
    /// it; retain that already-modeled run state across this one connection.
    pub fn running_shoes_field_motion(&self) -> bool {
        self.running
            && self.phase == StoryPhase::RunningShoesReceived
            && matches!(self.map, MapId::LittlerootTown | MapId::Route101)
    }

    fn ensure_starter_party(&mut self) {
        let starter = self.starter.unwrap_or(StarterSpecies::Treecko);
        if !self.starter_party.as_ref().is_some_and(|party| party.species == starter) {
            self.starter_party = Some(starter_party_state(starter));
        }
    }

    fn apply_starter_party_to_battle(&mut self, battle: &mut BattleState) {
        self.ensure_starter_party();
        let party = self.starter_party.as_ref().expect("starter party must exist after construction");
        battle.player_species = starter_species_name(Some(party.species)).to_owned();
        battle.player_hp = party.hp;
        battle.player_max_hp = party.max_hp;
        battle.player_level = party.level;
        battle.player_attack = party.attack;
        battle.player_defense = party.defense;
        battle.player_speed = party.speed;
        battle.player_special_attack = party.special_attack;
        battle.player_special_defense = party.special_defense;
        battle.player_move_pp = party.physical_move_pp;
        battle.player_status_move_pp = party.status_move_pp;
    }

    fn sync_starter_party_from_battle(&mut self) {
        let Some(battle) = self.battle.as_ref() else { return; };
        let (hp, max_hp, level, attack, defense, speed, special_attack, special_defense, physical_move_pp, status_move_pp, rng_state) = (
            battle.player_hp, battle.player_max_hp, battle.player_level, battle.player_attack, battle.player_defense,
            battle.player_speed, battle.player_special_attack, battle.player_special_defense, battle.player_move_pp, battle.player_status_move_pp, battle.rng_state,
        );
        self.ensure_starter_party();
        let party = self.starter_party.as_mut().expect("starter party must exist after construction");
        party.hp = hp;
        party.max_hp = max_hp;
        party.level = level;
        party.attack = attack;
        party.defense = defense;
        party.speed = speed;
        party.special_attack = special_attack;
        party.special_defense = special_defense;
        party.physical_move_pp = physical_move_pp;
        party.status_move_pp = status_move_pp;
        // Field object events and battles share Emerald's global Random()
        // state, so the next overworld task resumes the turn's final draw.
        self.ambient_rng = rng_state;
    }

    fn heal_starter_party(&mut self) {
        self.ensure_starter_party();
        let party = self.starter_party.as_mut().expect("starter party must exist after construction");
        let profile = starter_battle_profile(Some(party.species));
        let physical_move = profile.moves[0].expect("starter must have a physical opening move");
        let status_move = profile.moves[1].expect("starter must have a status opening move");
        party.hp = party.max_hp;
        party.physical_move_pp = physical_move.pp;
        party.status_move_pp = status_move.pp;
    }

    /// `CB2_EndFirstBattle` resumes `Route101_EventScript_BirchsBag` for
    /// both the scripted Zigzagoon's normal defeat and its low-HP flee. The
    /// script then heals the party and runs Birch's one-step approach before
    /// it permits the Lab handoff.
    fn complete_birch_rescue_battle(&mut self) {
        self.battle = None;
        self.phase = StoryPhase::BirchRescued;
        self.heal_starter_party();
        // Route101_EventScript_BirchsBag resumes on Route 101 after the
        // battle, fixes the player at (6,13), and has Birch approach before
        // the Lab warp is allowed.
        self.player = TilePosition { x: 6, y: 13 };
        self.elevation = crate::native::tile_elevation(self.map, 6, 13)
            .expect("Route 101 post-battle tile must be staged");
        if let Some(birch) = self.npcs.iter_mut().find(|npc| {
            npc.id == "birch" && npc.map == MapId::Route101
        }) {
            // `Route101_Movement_BirchApproachPlayer` has one ordinary
            // `walk_right` from the chase endpoint.
            birch.position = TilePosition { x: 4, y: 13 };
            birch.facing = Facing::Right;
        }
        self.move_scripted_npc(
            "birch",
            MapId::Route101,
            TilePosition { x: 5, y: 13 },
            Facing::Right,
        );
        self.birch_post_battle_frames = Some(16);
        self.dialogue = None;
    }

    /// `CB2_EndWildBattle` / `CB2_EndTrainerBattle` dispatch a genuine
    /// defeat to `DoWhiteOut`, which heals the party and warps to the last
    /// heal location. `InsideOfTruck` establishes the player's own bedroom
    /// as that opening location. A lost Route 103 battle leaves its trainer
    /// flag unset, so return to the pre-battle state where the rival can be
    /// challenged again after the field trip back north.
    fn white_out_from_opening_battle(&mut self) {
        self.heal_starter_party();
        self.battle = None;
        self.dialogue = None;
        self.field_dialogue_frames = None;
        self.transition = None;
        self.render_position = None;
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_direction = None;
        self.camera_handoff_from = None;
        self.walk_render_origin = None;
        self.running = false;
        self.running_step_uses_second_foot = false;
        self.npc_walk_starts.clear();
        self.ambient_wanders.clear();
        if self.phase == StoryPhase::RivalBattle {
            self.phase = StoryPhase::StarterChosen;
            self.title_intro_step = 0;
            self.route103_rival_intro_frames = None;
            self.route103_rival_intro_stage = 0;
            self.rival_departure_frames = None;
            self.route103_rival_departure_facing = None;
        }
        let (map, player) = match self.player_gender {
            PlayerGender::Brendan => (
                MapId::BrendansHouse2F,
                TilePosition { x: 4, y: 2 },
            ),
            PlayerGender::May => (MapId::MaysHouse2F, TilePosition { x: 4, y: 2 }),
        };
        self.map = map;
        self.player = player;
        self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
            .expect("opening white-out respawn tile must be staged");
        self.facing = Facing::Down;
        self.npcs = map_npcs(
            self.map,
            self.phase,
            self.potions,
            self.oldale_rival_departed,
            self.player_gender,
        );
    }

    /// Birch's Lab uses three source `MSGBOX_YESNO` branches: nickname,
    /// `GoSeeRival`, and the decline loop. Each stays input-owned so an
    /// ordinary dialogue advance cannot skip Route 103 permission.
    pub fn starter_lab_choice_active(&self) -> bool {
        self.phase == StoryPhase::StarterLab
            && self.dialogue.is_some()
            && matches!(self.title_intro_step, 1 | 3 | 5)
    }

    pub fn move_starter_lab_choice(&mut self) {
        if self.starter_lab_choice_active() {
            self.starter_lab_choice_yes = !self.starter_lab_choice_yes;
        }
    }

    pub fn respond_starter_lab_choice(&mut self, yes: bool) {
        if !self.starter_lab_choice_active() {
            return;
        }
        self.starter_lab_choice_yes = yes;
        match self.title_intro_step {
            // `LittlerootTown_ProfessorBirchsLab_EventScript_NicknameStarter`.
            1 if yes => {
                self.begin_starter_nickname_entry();
            }
            1 => {
                self.title_intro_step = 3;
                self.starter_lab_choice_yes = true;
                self.dialogue = Some(starter_lab_go_see_rival_text(self.player_gender, &self.player_name));
            }
            // `LittlerootTown_ProfessorBirchsLab_EventScript_GoSeeRival`.
            // `DeclineSeeingRival` loops its NO branch back to its own
            // YES/NO message and reaches the common agreement path on YES.
            3 if yes => {
                self.title_intro_step = 4;
                self.dialogue = Some(starter_lab_agree_to_see_rival_text(self.player_gender));
            }
            3 => {
                self.title_intro_step = 5;
                self.dialogue = Some(starter_lab_decline_seeing_rival_text());
            }
            5 if yes => {
                self.title_intro_step = 4;
                self.dialogue = Some(starter_lab_agree_to_see_rival_text(self.player_gender));
            }
            5 => {
                self.starter_lab_choice_yes = true;
                self.dialogue = Some(starter_lab_decline_seeing_rival_text());
            }
            _ => unreachable!("only source Lab choice stages are interactive"),
        }
    }

    fn begin_starter_nickname_entry(&mut self) {
        // `Common_EventScript_NameReceivedPartyMon` fades into
        // `NAMING_SCREEN_NICKNAME`; its input starts blank even though the
        // party mon still owns the species-name default.
        self.phase = StoryPhase::NameEntry;
        self.naming_target = NamingTarget::Starter;
        self.starter_nickname_entry.clear();
        self.name_cursor = 0;
        self.name_entry_touched = false;
        self.naming_action_button_pulse = None;
        self.name_entry_ready_frames = 0;
        self.name_entry_lowercase = false;
        self.name_confirm_transition_frames = None;
        self.title_intro_step = 2;
        self.dialogue = None;
    }

    fn finish_starter_nickname_entry(&mut self) {
        // `SaveInputText` leaves the mon's existing species-name nickname in
        // place when the player confirms a blank keyboard buffer.
        let nickname = self.starter_nickname_entry.clone();
        if nickname.chars().any(|character| !character.is_whitespace()) {
            self.ensure_starter_party();
            self.starter_party
                .as_mut()
                .expect("starter party exists when naming the starter")
                .nickname = Some(nickname);
        }
        self.starter_nickname_entry.clear();
        self.naming_target = NamingTarget::Player;
        self.naming_action_button_pulse = None;
        self.name_confirm_transition_frames = None;
        self.phase = StoryPhase::StarterLab;
        self.title_intro_step = 3;
        self.starter_lab_choice_yes = true;
        self.dialogue = Some(starter_lab_go_see_rival_text(self.player_gender, &self.player_name));
    }

    pub fn choose_starter(&mut self, starter: StarterSpecies) {
        if self.phase == StoryPhase::StarterSelect {
            self.starter = Some(starter);
            self.starter_party = None;
        }
    }

    /// Starts the opening Route 103 trainer battle after its authored
    /// encounter dialogue. The complete Emerald battle engine remains out of
    /// scope here, but this preserves a real input-driven turn loop instead
    /// of treating the battle as an automatic story jump.
    pub fn begin_rival_battle(&mut self) {
        if self.phase == StoryPhase::RivalBattle && self.battle.is_none() {
            // `TRAINER_BRENDAN_ROUTE_103_TREECKO` alone includes
            // AI_SCRIPT_SETUP_FIRST_TURN. The player's May/Mudkip branch
            // selects that trainer; every other Route 103 record is the
            // normal viability configuration.
            let rival_setup_first_turn = self.player_gender == PlayerGender::May
                && self.starter == Some(StarterSpecies::Mudkip);
            let mut battle = opening_battle_state(BattleOpponent::Rival, starter_battle_profile(self.starter), rival_battle_profile(self.starter, self.player_gender), false, format!("RIVAL {} would like to battle!", rival_trainer_name(self.player_gender)), 48, self.ambient_rng, rival_setup_first_turn);
            self.apply_starter_party_to_battle(&mut battle);
            self.battle = Some(battle);
        }
    }

    pub fn begin_birch_battle(&mut self) {
        if self.phase == StoryPhase::BirchBattle && self.battle.is_none() {
            let mut battle = opening_battle_state(BattleOpponent::Zigzagoon, starter_battle_profile(self.starter), wild_battle_profile("ZIGZAGOON", 2, &["TACKLE", "GROWL"]), false, "Wild ZIGZAGOON appeared!".to_owned(), 48, self.ambient_rng, false);
            self.apply_starter_party_to_battle(&mut battle);
            self.battle = Some(battle);
        }
    }

    /// The freshly replayed `03_birch` route reaches the grass tile `(15,5)`
    /// on Route 101 before Oldale. Its deterministic source RNG opens a
    /// normal wild Poochyena encounter there; this is distinct from the
    /// earlier scripted Birch-rescue battle against Zigzagoon.
    fn begin_route101_poochyena_encounter(&mut self) {
        if self.map != MapId::Route101
            || self.phase != StoryPhase::BirchRescued
            || self.player != (TilePosition { x: 15, y: 5 })
            || self.route101_poochyena_resolved
            || self.battle.is_some()
        {
            return;
        }
        let mut battle = opening_battle_state(BattleOpponent::Poochyena, starter_battle_profile(self.starter), wild_battle_profile("POOCHYENA", 2, &["TACKLE"]), true, "Wild POOCHYENA appeared!".to_owned(), 224, self.ambient_rng, false);
        self.apply_starter_party_to_battle(&mut battle);
        self.battle = Some(battle);
    }

    /// The reproducible post-Running-Shoes Route 101 field path stops at
    /// `(12,10)`: the next eastward boundary is collision-blocked, and the
    /// source RNG opens a level-2 Wurmple encounter on the second held-east
    /// boundary. Keep that typed field/battle boundary rather than allowing
    /// an inferred traversal through the northern grass.
    fn begin_route101_wurmple_encounter(&mut self) {
        if self.map != MapId::Route101
            || self.phase != StoryPhase::RunningShoesReceived
            || self.player != (TilePosition { x: 12, y: 10 })
            || self.route101_wurmple_resolved
            || self.battle.is_some()
        {
            return;
        }
        let mut battle = opening_battle_state(BattleOpponent::Wurmple, starter_battle_profile(self.starter), wild_battle_profile("WURMPLE", 2, &["TACKLE", "STRING SHOT"]), true, "Wild WURMPLE appeared!".to_owned(), 352, self.ambient_rng, false);
        self.apply_starter_party_to_battle(&mut battle);
        self.battle = Some(battle);
    }

    /// From the fresh `03_birch` state, the eastern Route 103 grass at
    /// `(16,13)` opens a deterministic level-3 Wingull encounter. This is
    /// the first source route around the southern ledge toward the rival.
    fn begin_route103_wingull_encounter(&mut self) {
        if self.map != MapId::Route103
            || self.phase != StoryPhase::BirchRescued
            || self.player != (TilePosition { x: 16, y: 13 })
            || self.route103_wingull_resolved
            || self.battle.is_some()
        {
            return;
        }
        let mut battle = opening_battle_state(BattleOpponent::Wingull, starter_battle_profile(self.starter), wild_battle_profile("WINGULL", 3, &["GROWL", "WATER GUN"]), true, "Wild WINGULL appeared!".to_owned(), 224, self.ambient_rng, false);
        self.apply_starter_party_to_battle(&mut battle);
        self.battle = Some(battle);
    }

    /// Advances the encounter wipe and reports whether it consumed this
    /// input. The command screen deliberately stays locked until the wipe
    /// has finished, matching the field-script behavior of other opening
    /// transitions.
    pub fn advance_battle_transition(&mut self, frames: u32) -> bool {
        let Some(battle) = self.battle.as_mut() else { return false; };
        if battle.entry_transition_frames == 0 { return false; }
        battle.entry_transition_frames = battle.entry_transition_frames
            .saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        true
    }

    /// Advances the source player trainer exit and its overlapping Poké Ball
    /// launch through `SpriteCB_ReleaseMonFromBall` and the twelve-tick
    /// `BATTLER_AFFINE_EMERGE` hand-off. Release particles and sound remain
    /// separate, while this typed timeline keeps ordinary battle messages
    /// from accidentally re-entering the intro sequence.
    pub fn advance_battle_player_intro_sendout(&mut self, frames: u32) -> bool {
        let Some(battle) = self.battle.as_mut() else { return false; };
        if !battle.intro_player_sendout_started {
            // Keep a snapshot produced by the preceding trainer-exit-only
            // rail moving forward. Snapshots without an active old timer
            // retain the command-screen behavior promised by the default.
            if battle.intro_player_sendout_frames == 0 { return false; }
            battle.intro_player_sendout_elapsed_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES
                .saturating_sub(battle.intro_player_sendout_frames);
            battle.intro_player_sendout_started = true;
        }
        if battle.intro_player_sendout_elapsed_frames >= BATTLE_PLAYER_SENDOUT_COMPLETE_FRAMES {
            battle.intro_player_sendout_started = false;
            return false;
        }
        battle.intro_player_sendout_elapsed_frames = battle.intro_player_sendout_elapsed_frames
            .saturating_add(frames.min(u32::from(u8::MAX)) as u8)
            .min(BATTLE_PLAYER_SENDOUT_COMPLETE_FRAMES);
        battle.intro_player_sendout_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES
            .saturating_sub(battle.intro_player_sendout_elapsed_frames);
        true
    }

    pub fn move_battle_command_cursor(&mut self, direction: Facing) {
        if let Some(battle) = self.battle.as_mut() {
            if battle.message.is_none() && !battle.selecting_move {
                // This is the same bitwise direct-navigation layout as
                // `HandleInputChooseAction`: bit 0 selects the column and
                // bit 1 selects the row. Do not wrap an edge press into an
                // unrelated command.
                battle.command_cursor = match (battle.command_cursor, direction) {
                    (BATTLE_COMMAND_BAG | BATTLE_COMMAND_RUN, Facing::Left) => battle.command_cursor ^ 1,
                    (BATTLE_COMMAND_FIGHT | BATTLE_COMMAND_POKEMON, Facing::Right) => battle.command_cursor ^ 1,
                    (BATTLE_COMMAND_POKEMON | BATTLE_COMMAND_RUN, Facing::Up) => battle.command_cursor ^ 2,
                    (BATTLE_COMMAND_FIGHT | BATTLE_COMMAND_BAG, Facing::Down) => battle.command_cursor ^ 2,
                    _ => battle.command_cursor,
                };
            }
        }
    }

    pub fn move_battle_move_cursor(&mut self, delta: i8) {
        if let Some(battle) = self.battle.as_mut() {
            if battle.message.is_none() && battle.selecting_move {
                battle.move_cursor = (i16::from(battle.move_cursor) + i16::from(delta)).rem_euclid(2) as u8;
            }
        }
    }

    pub fn cancel_battle_move_selection(&mut self) {
        if let Some(battle) = self.battle.as_mut() {
            if battle.message.is_none() {
                battle.selecting_move = false;
            }
        }
    }

    pub fn choose_battle_command(&mut self) {
        let Some(battle) = self.battle.as_mut() else { return; };
        if battle.message.is_some() || battle.selecting_move { return; }
        match battle.command_cursor {
            BATTLE_COMMAND_FIGHT => battle.selecting_move = true,
            BATTLE_COMMAND_BAG => {
                if self.potions == 0 {
                    battle.message = Some("The BAG is empty.".to_owned());
                } else {
                    battle.move_cursor = 0;
                    battle.selecting_move = true;
                }
            }
            BATTLE_COMMAND_POKEMON => battle.party_screen_open = true,
            BATTLE_COMMAND_RUN if battle.wild => {
                battle.escaped = true;
                battle.message = Some("Got away safely!".to_owned());
            }
            BATTLE_COMMAND_RUN => battle.message = Some(match battle.opponent {
                BattleOpponent::Rival => "No! There's no running from a TRAINER battle!".to_owned(),
                BattleOpponent::Zigzagoon => "Can't escape!".to_owned(),
                BattleOpponent::Poochyena => unreachable!("Route 101 Poochyena is wild"),
                BattleOpponent::Wingull => unreachable!("Route 103 Wingull is wild"),
                BattleOpponent::Wurmple => unreachable!("all Wurmple encounters are wild"),
            }),
            _ => unreachable!("battle command cursor must be a source action-selection ID"),
        }
    }

    pub fn close_battle_party_screen(&mut self, choose_active: bool) {
        let starter_name = starter_battle_profile(self.starter).species.name;
        if let Some(battle) = self.battle.as_mut() {
            if !battle.party_screen_open { return; }
            battle.party_screen_open = false;
            if choose_active {
                battle.message = Some(format!("{starter_name} is already battling!"));
            }
        }
    }

    pub fn choose_battle_move(&mut self) {
        let use_potion = self.battle.as_ref().is_some_and(|battle| {
            battle.message.is_none() && !battle.player_fainted && battle.selecting_move && battle.command_cursor == BATTLE_COMMAND_BAG
        });
        if use_potion {
            if self.potions == 0 {
                if let Some(battle) = self.battle.as_mut() {
                    battle.message = Some("But there were no POTIONs left!".to_owned());
                }
                return;
            }
            // The opponent controller chooses before turn execution, so its
            // AI/wild selection draws precede the item's source effect.
            let opponent_fled = {
                let battle = self.battle.as_mut().expect("Potion action requires an active battle");
                if matches!(select_opening_opponent_choice(battle), OpponentChoice::Flee) {
                    resolve_opponent_flee(battle);
                    true
                } else {
                    false
                }
            };
            if opponent_fled {
                self.sync_starter_party_from_battle();
                return;
            }
            self.potions -= 1;
            let battle = self.battle.as_mut().expect("Potion action requires an active battle");
            battle.player_hp = battle.player_hp.saturating_add(20).min(battle.player_max_hp);
            let retaliation = resolve_opponent_damage_move(battle);
            battle.opponent_move_damage = retaliation.damage;
            if retaliation.hit {
                battle.player_hp = battle.player_hp.saturating_sub(retaliation.damage);
            }
            let opponent = match battle.opponent {
                BattleOpponent::Rival => "RIVAL",
                BattleOpponent::Zigzagoon => "ZIGZAGOON",
                BattleOpponent::Poochyena => "POOCHYENA",
                BattleOpponent::Wingull => "WINGULL",
                BattleOpponent::Wurmple => "WURMPLE",
            };
            battle.player_fainted = battle.player_hp == 0;
            battle.message = Some(if battle.player_fainted {
                format!("Used a POTION! {} Your POKéMON fainted!", resolved_move_text(opponent, &battle.opponent_move_name, retaliation))
            } else {
                format!("Used a POTION! {}", resolved_move_text(opponent, &battle.opponent_move_name, retaliation))
            });
            battle.selecting_move = false;
            self.sync_starter_party_from_battle();
            return;
        }
        let starter_name = starter_battle_profile(self.starter).species.name;
        let trainer_name = rival_trainer_name(self.player_gender);
        let Some(battle) = self.battle.as_mut() else { return; };
        if battle.message.take().is_some() {
            if battle.intro_player_sendout_pending {
                battle.intro_player_sendout_pending = false;
                battle.intro_player_sendout_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES;
                battle.intro_player_sendout_elapsed_frames = 0;
                battle.intro_player_sendout_started = true;
                battle.intro_stage = 2;
                return;
            }
            match (battle.opponent, battle.intro_stage) {
                (BattleOpponent::Rival, 0) => {
                    battle.intro_stage = 1;
                    battle.message = Some(format!("RIVAL {trainer_name} sent out {}!", battle.opponent_species));
                    return;
                }
                (_, 0) | (BattleOpponent::Rival, 1) => {
                    battle.intro_stage += 1;
                    battle.intro_player_sendout_pending = true;
                    battle.message = Some(format!("Go! {starter_name}!"));
                    return;
                }
                _ => battle.intro_stage = 2,
            }
            if battle.player_fainted || battle.escaped || battle.opponent_fled {
                let opponent = battle.opponent;
                let wild = battle.wild;
                let escaped = battle.escaped;
                let opponent_fled = battle.opponent_fled;
                let player_fainted = battle.player_fainted;
                self.sync_starter_party_from_battle();
                // The first battle's special controller ends at the field
                // script for either a KO or AI_FirstBattle's low-HP flee.
                // Without this continuation the old generic cleanup leaves
                // `BirchBattle` with neither a battle nor a script owner.
                if opponent == BattleOpponent::Zigzagoon
                    && (opponent_fled || player_fainted)
                {
                    self.complete_birch_rescue_battle();
                    return;
                }
                if player_fainted {
                    self.white_out_from_opening_battle();
                    return;
                }
                self.battle = None;
                if escaped && wild {
                    match opponent {
                        BattleOpponent::Poochyena => self.route101_poochyena_resolved = true,
                        BattleOpponent::Wingull => self.route103_wingull_resolved = true,
                        BattleOpponent::Wurmple => self.route101_wurmple_resolved = true,
                        BattleOpponent::Rival | BattleOpponent::Zigzagoon => unreachable!("trainer and rescue battles are not wild"),
                    }
                }
            }
            return;
        }
        if !battle.selecting_move { return; }
        if battle.move_cursor == 0 && battle.player_move_pp == 0 {
            battle.message = Some("But there was no PP left for that move!".to_owned());
            return;
        }
        if battle.move_cursor != 0 && battle.player_status_move_pp == 0 {
            battle.message = Some("But there was no PP left for that move!".to_owned());
            return;
        }
        // OpponentHandleChooseMove runs while both controllers submit their
        // actions, before priority and either move's battle script consume
        // accuracy, critical, or normal-damage RNG.
        if matches!(select_opening_opponent_choice(battle), OpponentChoice::Flee) {
            resolve_opponent_flee(battle);
            self.sync_starter_party_from_battle();
            return;
        }
        // Normal-priority moves use the source-calculated battle speeds. The
        // compact renderer remains player-first on a speed tie until its full
        // battle RNG command scheduler is modeled.
        let opponent_moves_first = battle.opponent_speed > source_stage_stat(battle.player_speed, battle.player_speed_stage);
        let mut opponent_result = None;
        if opponent_moves_first {
            let retaliation = resolve_opponent_damage_move(battle);
            battle.opponent_move_damage = retaliation.damage;
            if retaliation.hit {
                battle.player_hp = battle.player_hp.saturating_sub(retaliation.damage);
            }
            opponent_result = Some(retaliation);
            if battle.player_hp == 0 {
                battle.player_fainted = true;
                battle.selecting_move = false;
                battle.message = Some(format!("{} Your POKéMON fainted!", resolved_move_text(battle_opponent_name(battle.opponent), &battle.opponent_move_name, retaliation)));
                self.sync_starter_party_from_battle();
                return;
            }
        }
        let (move_name, player_result) = if battle.move_cursor == 0 {
            // `BattleScript_PrintMoveMissed` still reaches `ppreduce`, so
            // both a hit and miss consume the selected move's PP.
            battle.player_move_pp -= 1;
            let result = resolve_player_damage_move(battle);
            battle.player_move_damage = result.damage;
            if result.hit {
                battle.rival_hp = battle.rival_hp.saturating_sub(result.damage);
            }
            (battle.player_move_name.clone(), result)
        } else {
            battle.player_status_move_pp -= 1;
            let move_data = move_battle_profile(&battle.player_status_move_name);
            let hit = battle_accuracy_check(battle, move_data);
            if hit && battle.player_status_move_name == "LEER" {
                battle.opponent_defense_stage = (battle.opponent_defense_stage - 1).max(-6);
            } else if hit {
                battle.opponent_attack_stage = (battle.opponent_attack_stage - 1).max(-6);
            }
            (battle.player_status_move_name.clone(), BattleMoveResolution { hit, critical: false, damage: 0 })
        };
        battle.selecting_move = false;
        if battle.rival_hp == 0 {
            let opponent = battle.opponent;
            self.sync_starter_party_from_battle();
            self.battle = None;
            match opponent {
                BattleOpponent::Rival => {
                    self.phase = StoryPhase::RivalDefeated;
                    self.title_intro_step = 0;
                    self.dialogue = Some(rival_defeated_text(self.player_gender, &self.player_name));
                }
                BattleOpponent::Zigzagoon => {
                    self.complete_birch_rescue_battle();
                }
                BattleOpponent::Poochyena => {
                    self.route101_poochyena_resolved = true;
                }
                BattleOpponent::Wingull => {
                    self.route103_wingull_resolved = true;
                }
                BattleOpponent::Wurmple => {
                    self.route101_wurmple_resolved = true;
                }
            }
            return;
        }
        if !opponent_moves_first {
            // Growl lowers the source opponent's physical attack stage; the
            // source damage calculation consumes that stage before its RNG
            // variance roll.
            let retaliation = resolve_opponent_damage_move(battle);
            battle.opponent_move_damage = retaliation.damage;
            if retaliation.hit {
                battle.player_hp = battle.player_hp.saturating_sub(retaliation.damage);
            }
            opponent_result = Some(retaliation);
        }
        let opponent = match battle.opponent {
            BattleOpponent::Rival => "RIVAL",
            BattleOpponent::Zigzagoon => "ZIGZAGOON",
            BattleOpponent::Poochyena => "POOCHYENA",
            BattleOpponent::Wingull => "WINGULL",
            BattleOpponent::Wurmple => "WURMPLE",
        };
        let player_text = resolved_move_text("Your POKéMON", &move_name, player_result);
        let opponent_text = resolved_move_text(opponent, &battle.opponent_move_name, opponent_result.expect("opponent must resolve after a non-KO player move"));
        if battle.player_hp == 0 {
            battle.player_fainted = true;
            battle.message = Some(if opponent_moves_first {
                format!("{opponent_text} {player_text} Your POKéMON fainted!")
            } else {
                format!("{player_text} {opponent_text} Your POKéMON fainted!")
            });
        } else {
            battle.message = Some(if opponent_moves_first {
                format!("{opponent_text} {player_text}")
            } else {
                format!("{player_text} {opponent_text}")
            });
        }
        self.sync_starter_party_from_battle();
    }

    /// Tracks held title input while the distinct source transition frames are
    /// still awaiting native rendering.
    pub fn advance_title_start(&mut self, held_frames: u32) {
        if self.phase != StoryPhase::Title { return; }
        self.title_start_frames = self.title_start_frames.saturating_add(held_frames.min(u32::from(u8::MAX)) as u8);
    }

    /// Advances the source title fade. The reset-state reference reaches the
    /// Professor Birch introduction after 480 idle frames; the truck is a
    /// separate later checkpoint and must not be invented as this transition.
    pub fn advance_title_transition(&mut self, idle_frames: u32) {
        if self.phase != StoryPhase::Title || self.title_start_frames < 120 {
            return;
        }
        self.title_transition_frames = self.title_transition_frames.saturating_add(idle_frames.min(u32::from(u16::MAX)) as u16);
        if self.title_transition_frames < 480 {
            return;
        }
        self.map = MapId::ProfessorIntro;
        self.phase = StoryPhase::TitleIntro;
        self.player = TilePosition { x: 0, y: 0 };
        self.elevation = 0;
        self.facing = Facing::Down;
        self.npcs.clear();
        self.title_intro_step = 0;
        self.title_intro_frames = 0;
        // The captured frame already contains Birch's first text window.
        // Keep dialogue state empty so the generic Rust overlay cannot draw a
        // second window over that byte-identical oracle frame.
        self.dialogue = None;
    }

    /// Advances the text printer for the source-authored Professor Birch
    /// introduction. The first page needs 240 frames from the captured reset
    /// state; later pages use the normal 120-frame text completion window.
    pub fn advance_title_intro(&mut self, idle_frames: u32) {
        if self.phase == StoryPhase::TitleIntro {
            self.title_intro_frames = self.title_intro_frames
                .saturating_add(idle_frames.min(u32::from(u16::MAX)) as u16);
        }
    }

    /// `Task_HandleStarterChooseInput` starts the source's small affine
    /// circle/Pokémon reveal after A selects the currently bounded Poké Ball.
    pub fn ask_confirm_starter(&mut self) {
        if self.phase != StoryPhase::StarterSelect { return; }
        self.starter.get_or_insert(StarterSpecies::Torchic);
        self.starter_confirm_yes = true;
        self.starter_reveal_frames = Some(0);
        self.phase = StoryPhase::StarterReveal;
    }

    /// Advances `SpriteCB_SelectionHand`'s `Sin(data[1], 8)` phase. Its
    /// callback adds four indices on every source video frame.
    pub fn advance_starter_hand(&mut self, frames: u32) {
        if !matches!(
            self.phase,
            StoryPhase::StarterSelect | StoryPhase::StarterReveal | StoryPhase::StarterConfirm
        ) {
            return;
        }
        let source_steps = (frames & 0xff) as u8;
        self.starter_hand_phase = self.starter_hand_phase
            .wrapping_add(source_steps.wrapping_mul(4));
    }

    /// Advances the selected ball's `sAnim_Pokeball_Moving` clock. A ball
    /// selected on the first source frame begins at image value 16 during
    /// that frame, so its caller omits that initial frame after a selection
    /// change and advances only the remaining held frames.
    pub fn advance_starter_pokeball_animation(&mut self, frames: u32) {
        if !matches!(
            self.phase,
            StoryPhase::StarterSelect | StoryPhase::StarterReveal | StoryPhase::StarterConfirm
        ) {
            return;
        }
        self.starter_pokeball_animation_frame = self
            .starter_pokeball_animation_frame
            .wrapping_add((frames & 0x7f) as u8)
            & 0x7f;
    }

    /// Runs the two source `AFFINEANIMCMD_FRAME` sequences. The chosen
    /// Pokémon starts at scale 16 and grows by 16 for fifteen frames; the
    /// circle starts at 20 and grows by 20. `Task_WaitForStarterSprite` only
    /// enables the standard YES/NO task after that motion has settled.
    pub fn advance_starter_reveal(&mut self, frames: u32) -> bool {
        if self.phase != StoryPhase::StarterReveal { return false; }
        self.advance_starter_hand(frames);
        self.advance_starter_pokeball_animation(frames);
        let elapsed = self.starter_reveal_frames.unwrap_or(0);
        let advanced = frames.min(15) as u8;
        let next = elapsed.saturating_add(advanced).min(15);
        if next == 15 {
            self.starter_reveal_frames = None;
            self.phase = StoryPhase::StarterConfirm;
        } else {
            self.starter_reveal_frames = Some(next);
        }
        true
    }

    pub fn move_starter_confirmation(&mut self) {
        if self.phase == StoryPhase::StarterConfirm {
            self.starter_confirm_yes = !self.starter_confirm_yes;
        }
    }

    /// `Task_HandleConfirmStarterInput` returns the selected index only on
    /// YES. Its NO and B paths destroy the temporary sprite and resume the
    /// same bounded selector, preserving the selected ball.
    pub fn respond_starter_confirmation(&mut self, accepted: bool) {
        if self.phase != StoryPhase::StarterConfirm { return; }
        if accepted {
            self.confirm_starter();
        } else {
            self.starter_confirm_yes = true;
            self.starter_reveal_frames = None;
            self.phase = StoryPhase::StarterSelect;
        }
    }

    fn confirm_starter(&mut self) {
        if self.phase == StoryPhase::StarterConfirm {
            self.starter.get_or_insert(StarterSpecies::Torchic);
            self.ensure_starter_party();
            self.starter_reveal_frames = None;
            self.phase = StoryPhase::BirchBattle;
            self.dialogue = Some("Go! Your new POKéMON!".to_owned());
            self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
        }
    }

    /// `Task_HandleStarterChooseInput` accepts only bounded left/right
    /// selection movement before the player confirms a Poké Ball.
    pub fn move_starter_selection(&mut self, delta: i8) -> bool {
        if self.phase != StoryPhase::StarterSelect { return false; }
        let previous = self.starter.unwrap_or(StarterSpecies::Torchic);
        let selection = match previous {
            StarterSpecies::Treecko => 0_i8,
            StarterSpecies::Torchic => 1,
            StarterSpecies::Mudkip => 2,
        };
        let next = match (selection + delta).clamp(0, 2) {
            0 => StarterSpecies::Treecko,
            1 => StarterSpecies::Torchic,
            _ => StarterSpecies::Mudkip,
        };
        // `SpriteCB_Pokeball` restarts `sAnim_Pokeball_Moving` whenever a
        // different ball becomes selected. Bounded input that leaves the
        // selection unchanged does not restart it.
        if next != previous {
            self.starter_pokeball_animation_frame = 0;
            self.starter = Some(next);
            return true;
        }
        self.starter = Some(next);
        false
    }

    pub fn cycle_starter(&mut self) {
        if self.phase != StoryPhase::StarterSelect { return; }
        let next = match self.starter {
            None | Some(StarterSpecies::Treecko) => StarterSpecies::Torchic,
            Some(StarterSpecies::Torchic) => StarterSpecies::Mudkip,
            Some(StarterSpecies::Mudkip) => StarterSpecies::Treecko,
        };
        self.starter_pokeball_animation_frame = 0;
        self.starter = Some(next);
    }

    fn name_entry_action_button(&self) -> Option<NamingActionButton> {
        if self.phase != StoryPhase::NameEntry { return None; }
        match self.name_cursor {
            // `sKeyRowToButtonRow` maps the top row to PAGE, both middle
            // rows to BACK, and the bottom row to OK.
            28 => Some(NamingActionButton::Page),
            29 | 30 => Some(NamingActionButton::Back),
            31 => Some(NamingActionButton::Ok),
            _ => None,
        }
    }

    /// Source-faithful `TryStartButtonFlash`: changing controls restores the
    /// prior palette by dropping its pulse, while staying on a control keeps
    /// the existing task phase alive.
    fn try_start_name_entry_action_button_pulse(
        &mut self,
        button: Option<NamingActionButton>,
        keep_flashing: bool,
        interrupt_current_flash: bool,
    ) {
        let current = self.naming_action_button_pulse.map(|pulse| pulse.button);
        if current == button && !interrupt_current_flash {
            if let Some(pulse) = self.naming_action_button_pulse.as_mut() {
                pulse.keep_flashing = keep_flashing;
                pulse.allow_flash = true;
            }
            return;
        }
        let Some(button) = button else {
            self.naming_action_button_pulse = None;
            return;
        };
        self.naming_action_button_pulse = Some(NamingActionButtonPulse {
            button,
            color: 4,
            color_incr: 2,
            color_delay: 0,
            color_delta: 4,
            keep_flashing,
            allow_flash: true,
            applied_color: 4,
        });
    }

    fn advance_name_entry_action_button_pulse_frame(&mut self) {
        let Some(pulse) = self.naming_action_button_pulse.as_mut() else { return; };
        if !pulse.allow_flash { return; }

        // `MultiplyInvertedPaletteRGBComponents` observes `tColor` before
        // `Task_UpdateButtonFlash` advances the task fields for this frame.
        pulse.applied_color = u8::try_from(pulse.color).expect("source button color remains non-negative");
        if pulse.color_delay != 0 {
            pulse.color_delay -= 1;
            if pulse.color_delay != 0 { return; }
        }
        pulse.color_delay = 2;
        if pulse.color_incr >= 0 {
            if pulse.color < 14 {
                pulse.color += pulse.color_incr;
                pulse.color_delta += pulse.color_incr;
            } else {
                pulse.color = 16;
                pulse.color_delta += 1;
            }
        } else {
            pulse.color += pulse.color_incr;
            pulse.color_delta += pulse.color_incr;
        }
        if pulse.color == 16 && pulse.color_delta == 22 {
            pulse.color_incr = -4;
        } else if pulse.color == 0 {
            pulse.allow_flash = pulse.keep_flashing;
            pulse.color_incr = 2;
            pulse.color_delta = 0;
        }
    }

    /// Runs `Task_UpdateButtonFlash` in video-frame order for a name-entry
    /// request. This uses local serialized task state, never `world.frame`.
    pub fn advance_name_entry_action_button_pulse(&mut self, frames: u32) {
        if self.phase != StoryPhase::NameEntry {
            self.naming_action_button_pulse = None;
            return;
        }
        for _ in 0..frames {
            let button = self.name_entry_action_button();
            self.try_start_name_entry_action_button_pulse(button, button.is_some(), false);
            self.advance_name_entry_action_button_pulse_frame();
        }
    }

    pub fn move_name_cursor(&mut self, horizontal: i8, vertical: i8) {
        if self.phase != StoryPhase::NameEntry { return; }
        self.name_entry_touched = true;
        // Latin letters occupy four uneven rows. The remaining cells are the
        // visible ? / . / LOWER / BACK / B BUTTON / OK controls.
        const STARTS: [u8; 4] = [0, 6, 12, 19];
        const LENGTHS: [u8; 4] = [6, 6, 7, 7];
        const QUESTION: u8 = 26;
        const PERIOD: u8 = 27;
        const LOWER: u8 = 28;
        const BACK: u8 = 29;
        const B_BUTTON: u8 = 30;
        const OK: u8 = 31;

        if matches!(self.name_cursor, LOWER | BACK | B_BUTTON | OK) {
            const UTILITIES: [u8; 4] = [LOWER, BACK, B_BUTTON, OK];
            let index = UTILITIES.iter().position(|cell| *cell == self.name_cursor).unwrap_or(0);
            if vertical != 0 {
                self.name_cursor = UTILITIES[(i16::try_from(index).expect("four utilities") + i16::from(vertical)).rem_euclid(4) as usize];
            } else if horizontal < 0 {
                self.name_cursor = match self.name_cursor { LOWER => QUESTION, BACK => PERIOD, B_BUTTON => 18, OK => 25, _ => unreachable!() };
            }
            return;
        }

        if horizontal > 0 {
            self.name_cursor = match self.name_cursor {
                5 => QUESTION,
                QUESTION => LOWER,
                11 => PERIOD,
                PERIOD => BACK,
                18 => B_BUTTON,
                25 => OK,
                value => value + 1,
            };
            return;
        }
        if horizontal < 0 {
            self.name_cursor = match self.name_cursor {
                QUESTION => 5,
                PERIOD => 11,
                0 => 5,
                6 => 11,
                12 => 18,
                19 => 25,
                value => value - 1,
            };
            return;
        }

        if self.name_cursor == QUESTION {
            self.name_cursor = PERIOD;
            return;
        }
        if self.name_cursor == PERIOD {
            self.name_cursor = QUESTION;
            return;
        }
        let row = STARTS.iter().rposition(|start| *start <= self.name_cursor).unwrap_or(0);
        let column = self.name_cursor - STARTS[row];
        let target_row = (i16::try_from(row).expect("four rows") + i16::from(vertical)).rem_euclid(4) as usize;
        let target_length = LENGTHS[target_row];
        let target_column = if horizontal != 0 {
            (i16::from(column) + i16::from(horizontal)).rem_euclid(i16::from(LENGTHS[row])) as u8
        } else {
            column.min(target_length - 1)
        };
        self.name_cursor = STARTS[target_row] + target_column;
    }

    /// Emerald's physical Start shortcut moves the keyboard cursor to its
    /// on-screen OK button; it does not submit the text by itself.
    pub fn move_name_cursor_to_ok(&mut self) {
        if self.phase != StoryPhase::NameEntry { return; }
        self.name_entry_touched = true;
        self.name_cursor = 31;
    }

    pub fn move_gender_cursor(&mut self, delta: i8) {
        if self.phase != StoryPhase::GenderSelect || delta == 0 { return; }
        // NewGameBirchSpeech_ProcessGenderMenuInput calls the no-wrap menu
        // handler: BOY is the upper bound and GIRL the lower bound.
        let next = match (self.player_gender, delta.signum()) {
            (PlayerGender::Brendan, 1) => PlayerGender::May,
            (PlayerGender::May, -1) => PlayerGender::Brendan,
            (gender, _) => gender,
        };
        if next != self.player_gender {
            self.gender_selection_touched = true;
            self.gender_transition = Some(GenderTransition {
                outgoing: self.player_gender,
                incoming: next,
                // The source fades out for sixteen frames, then fades the
                // replacement in for eighteen (including its settled last
                // frame), with the same four-pixel sprite cadence.
                frames_remaining: 34,
            });
            self.player_gender = next;
        }
    }

    pub fn advance_gender_transition(&mut self, frames: u32) -> bool {
        let Some(mut transition) = self.gender_transition else { return false; };
        transition.frames_remaining = transition.frames_remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if transition.frames_remaining == 0 {
            self.gender_transition = None;
        } else {
            self.gender_transition = Some(transition);
        }
        true
    }

    pub fn confirm_gender(&mut self) {
        if self.phase == StoryPhase::GenderSelect {
            // Emerald acknowledges the selected presentation before it opens
            // the naming keyboard. Keeping this as an explicit state also
            // prevents a held A press from leaking into the first name cell.
            self.phase = StoryPhase::NamePrompt;
            self.dialogue = Some("All right.\nWhat's your name?".to_owned());
        }
    }

    pub fn confirm_name_prompt(&mut self) {
        if self.phase != StoryPhase::NamePrompt { return; }
        self.phase = StoryPhase::NameEntry;
        self.naming_target = NamingTarget::Player;
        self.dialogue = None;
        self.name_entry_ready_frames = 0;
        self.name_entry_lowercase = false;
        self.naming_action_button_pulse = None;
    }

    pub fn is_player_name_entry(&self) -> bool {
        self.phase == StoryPhase::NameEntry && self.naming_target == NamingTarget::Player
    }

    pub fn is_starter_nickname_entry(&self) -> bool {
        self.phase == StoryPhase::NameEntry && self.naming_target == NamingTarget::Starter
    }

    pub fn name_entry_text(&self) -> &str {
        match self.naming_target {
            NamingTarget::Player => &self.player_name,
            NamingTarget::Starter => &self.starter_nickname_entry,
        }
    }

    fn name_entry_text_mut(&mut self) -> &mut String {
        match self.naming_target {
            NamingTarget::Player => &mut self.player_name,
            NamingTarget::Starter => &mut self.starter_nickname_entry,
        }
    }

    fn name_entry_max_chars(&self) -> usize {
        match self.naming_target {
            NamingTarget::Player => 7,
            // `POKEMON_NAME_LENGTH` for `NAMING_SCREEN_NICKNAME`.
            NamingTarget::Starter => 10,
        }
    }

    fn append_name_entry_character(&mut self, character: char) {
        if self.name_entry_text().chars().count() < self.name_entry_max_chars() {
            self.name_entry_text_mut().push(character);
        }
    }

    /// The source leaves the name grid visually present but non-interactive for about a
    /// second after the gender choice. Inputs during that period are consumed.
    pub fn advance_name_entry_ready(&mut self, frames: u32) -> bool {
        if self.phase != StoryPhase::NameEntry { return false; }
        if self.name_entry_ready_frames < 60 {
            self.name_entry_ready_frames = self.name_entry_ready_frames.saturating_add(frames).min(60);
            return false;
        }
        true
    }

    pub fn select_name_cell(&mut self) {
        if self.phase != StoryPhase::NameEntry { return; }
        self.name_entry_touched = true;
        match self.name_cursor {
            0..=25 => {
                let base = if self.name_entry_lowercase { b'a' } else { b'A' };
                self.append_name_entry_character((base + self.name_cursor) as char);
            }
            26 => self.append_name_entry_character('?'),
            27 => self.append_name_entry_character('.'),
            28 => self.name_entry_lowercase = !self.name_entry_lowercase,
            29 => self.delete_name_character(),
            30 => {}, // The source's B-button help cell does not alter the name.
            31 => self.confirm_name(),
            _ => unreachable!("name cursor must reference a keyboard cell"),
        }
    }

    pub fn delete_name_character(&mut self) {
        if self.phase != StoryPhase::NameEntry { return; }
        self.name_entry_touched = true;
        if self.name_entry_text().is_empty() && self.naming_target == NamingTarget::Player {
            self.phase = StoryPhase::GenderSelect;
            self.naming_action_button_pulse = None;
        } else if !self.name_entry_text().is_empty() {
            self.name_entry_text_mut().pop();
        }
    }

    pub fn confirm_name(&mut self) {
        if self.phase != StoryPhase::NameEntry { return; }
        match self.naming_target {
            NamingTarget::Player if !self.player_name.is_empty() => {
                self.name_confirm_transition_frames = Some(1);
            }
            NamingTarget::Player => {}
            NamingTarget::Starter => self.finish_starter_nickname_entry(),
        }
    }

    /// Advances the one-frame source delay between selecting the keyboard's
    /// OK cell and exposing the post-name confirmation UI. The request that
    /// crosses the boundary is consumed by the UI transition.
    pub fn advance_name_confirm_transition(&mut self, frames: u32) -> bool {
        if self.naming_target != NamingTarget::Player { return false; }
        let Some(remaining) = self.name_confirm_transition_frames else { return false; };
        let remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if remaining != 0 {
            self.name_confirm_transition_frames = Some(remaining);
            return true;
        }
        self.name_confirm_transition_frames = None;
        self.phase = StoryPhase::NameConfirm;
        self.naming_action_button_pulse = None;
        self.name_confirm_yes = true;
        self.dialogue = Some(format!("So it's {}?", self.player_name));
        true
    }

    pub fn move_name_confirmation(&mut self) {
        if self.phase == StoryPhase::NameConfirm {
            self.name_confirm_yes = !self.name_confirm_yes;
        }
    }

    pub fn respond_name_confirmation(&mut self, accepted: bool) {
        if self.phase != StoryPhase::NameConfirm { return; }
        if !accepted {
            // The source returns to Birch's gender question, not directly
            // to the keyboard, so presentation and name can both be redone.
            self.phase = StoryPhase::GenderSelect;
            self.dialogue = None;
            return;
        }
        self.phase = StoryPhase::IntroFarewell;
        self.title_intro_step = 0;
        self.dialogue = Some(opening_farewell_page(0, &self.player_name).to_owned());
    }

    pub fn advance_opening_farewell(&mut self) {
        if self.phase != StoryPhase::IntroFarewell { return; }
        let next = usize::from(self.title_intro_step) + 1;
        if next < OPENING_FAREWELL_PAGE_COUNT {
            self.title_intro_step = next as u8;
            self.dialogue = Some(opening_farewell_page(next, &self.player_name).to_owned());
            return;
        }
        self.map = MapId::MovingTruck;
        self.phase = StoryPhase::IntroTruck;
        self.player = TilePosition { x: 3, y: 2 };
        self.elevation = 0;
        self.facing = Facing::Down;
        self.npcs.clear();
        self.dialogue = None;
    }

    fn menu_entries(&self) -> &'static [MenuEntry] {
        const BEFORE_POKEDEX: [MenuEntry; 6] = [MenuEntry::Pokemon, MenuEntry::Bag, MenuEntry::Player, MenuEntry::Save, MenuEntry::Option, MenuEntry::Exit];
        const AFTER_POKEDEX: [MenuEntry; 7] = [MenuEntry::Pokedex, MenuEntry::Pokemon, MenuEntry::Bag, MenuEntry::Player, MenuEntry::Save, MenuEntry::Option, MenuEntry::Exit];
        if self.has_pokedex { &AFTER_POKEDEX } else { &BEFORE_POKEDEX }
    }

    /// Advances the first opening beats represented by the staged checkpoints.
    /// Text is exposed in readout state for now; a GBA text-window renderer is
    /// required before it can affect the pixel buffer.
    pub fn advance_opening_script(&mut self) {
        if self.phase == StoryPhase::TitleIntro {
            let required_frames = if self.title_intro_step == 0 { 240 } else { 120 };
            if self.title_intro_frames < required_frames { return; }
            let next = usize::from(self.title_intro_step) + 1;
            if let Some(page) = TITLE_INTRO_PAGES.get(next) {
                self.title_intro_step = next as u8;
                self.title_intro_frames = 0;
                self.dialogue = Some((*page).to_owned());
            } else {
                self.phase = StoryPhase::GenderSelect;
                self.dialogue = None;
            }
            return;
        }
        // `MSGBOX_YESNO` is input-owned: never let a generic dialogue-close
        // skip Birch's Route 103 permission prompt or its decline loop.
        if self.starter_lab_choice_active() {
            return;
        }
        if self.dialogue.is_some()
            && self.pending_running_shoes
            && matches!(self.running_shoes_stage, 2..=5)
            && self.advance_running_shoes_dialogue()
        {
            return;
        }
        if self.truck_arrival_dialogue_frames.is_some()
            || self.running_shoes_wait_frames.is_some()
            || self.oldale_mart_dialogue_frames.is_some()
            || self.oldale_mart_item_fanfare_frames.is_some()
            || self.pokedex_receipt_fanfare_frames.is_some()
            || self.pokedex_poke_ball_fanfare_frames.is_some()
            || self.field_dialogue_frames.is_some()
        {
            return;
        }
        if self.dialogue.take().is_some() {
            if self.clock_prompt_active && self.phase == StoryPhase::ClockSet {
                self.clock_prompt_active = false;
                self.start_clock_editor();
                return;
            }
            if let Some(blocked_facing) = self.route101_exit_push.take() {
                match blocked_facing {
                    Facing::Down => self.player.y -= 1,
                    Facing::Left => self.player.x += 1,
                    Facing::Up => self.player.y += 1,
                    Facing::Right => self.player.x -= 1,
                }
                self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                    .expect("Route 101 exit-push tile must be staged");
                self.facing = match blocked_facing {
                    Facing::Up => Facing::Down,
                    Facing::Down => Facing::Up,
                    Facing::Left => Facing::Right,
                    Facing::Right => Facing::Left,
                };
                return;
            }
            if self.phase == StoryPhase::RivalBattle
                && self.map == MapId::Route103
                && self.route103_rival_intro_stage == 0 {
                self.route103_rival_intro_stage = 1;
                // FacePlayer, exclamation-mark animation, then the authored
                // `Common_Movement_Delay48` pause.
                self.route103_rival_intro_frames = Some(88);
                if let Some(rival) = self.npcs.iter_mut().find(|npc| npc.id == "rival" && npc.map == MapId::Route103) {
                    rival.facing = match self.facing {
                        Facing::Up => Facing::Down,
                        Facing::Down => Facing::Up,
                        Facing::Left => Facing::Right,
                        Facing::Right => Facing::Left,
                    };
                }
                return;
            }
            if self.phase == StoryPhase::BirchRescue && self.birch_rescue_stage == 0 {
                self.birch_rescue_stage = 1;
                self.birch_rescue_frames = Some(ROUTE101_RESCUE_CHOREOGRAPHY_FRAMES);
                if let Some(birch) = self.npcs.iter_mut().find(|npc| npc.id == "birch" && npc.map == MapId::Route101) {
                    birch.position = TilePosition { x: 0, y: 15 };
                    birch.facing = Facing::Right;
                }
                if let Some(zigzagoon) = self.npcs.iter_mut().find(|npc| npc.id == "zigzagoon" && npc.map == MapId::Route101) {
                    zigzagoon.position = TilePosition { x: 0, y: 16 };
                    zigzagoon.facing = Facing::Right;
                }
                return;
            }
            if self.phase == StoryPhase::BirchRescue && self.birch_rescue_stage == 2 {
                self.birch_rescue_stage = 3;
                return;
            }
            if self.no_pokemon_gate_stage == 1 && self.no_pokemon_gate_frames.is_none() {
                self.no_pokemon_gate_stage = 2;
                self.no_pokemon_gate_frames = Some(16);
                return;
            }
            if self.no_pokemon_gate_stage == 3 && self.no_pokemon_gate_frames.is_none() {
                self.no_pokemon_gate_stage = 4;
                self.no_pokemon_gate_frames = Some(no_pokemon_twin_path_frames(
                    self.no_pokemon_gate_right,
                    true,
                ));
                return;
            }
            if self.birch_prompt_active && self.birch_prompt_frames.is_none() {
                self.title_intro_step = 2;
                self.birch_prompt_frames = Some(8);
                return;
            }
            match self.oldale_mart_scene_stage {
                1 => {
                    if self.oldale_mart_dialogue_page == 0 {
                        self.oldale_mart_dialogue_page = 1;
                        self.oldale_mart_dialogue_frames = Some(16);
                        self.dialogue = Some("Can I get you to come with me?".to_owned());
                        return;
                    }
                    // The invitation closes before source movement begins.
                    // South contains nine normal employee walks; north/east
                    // use seven. Each source stream then ends in a
                    // four-frame `walk_in_place_faster_down` before its
                    // shared `waitmovement` releases the next dialogue.
                    self.oldale_mart_scene_stage = 2;
                    self.oldale_mart_dialogue_page = 0;
                    self.oldale_mart_scene_frames = Some(match self.oldale_mart_scene_route {
                        Some(Facing::Down) => 148,
                        Some(Facing::Up | Facing::Right) => 116,
                        // The source has no west-facing branch, but retain a
                        // deterministic compatible path for imported state.
                        Some(Facing::Left) | None => 116,
                    });
                    return;
                }
                3 => {
                    let next_page = match self.oldale_mart_dialogue_page {
                        0 => Some("We sell a variety of goods including\nPOKé BALLS for catching POKéMON."),
                        1 => Some("Here, I'd like you to have this as\na promotional item."),
                        _ => None,
                    };
                    if let Some(dialogue) = next_page {
                        self.oldale_mart_dialogue_page = self.oldale_mart_dialogue_page.saturating_add(1);
                        // The A request has already consumed sixteen of
                        // the source's 80-frame printer for promotion pages
                        // two and three.
                        self.oldale_mart_dialogue_frames = Some(64);
                        self.dialogue = Some(dialogue.to_owned());
                        return;
                    }
                    // `giveitem ITEM_POTION` supplies its own 32-frame
                    // receipt before the explanatory Mart text can open.
                    self.oldale_mart_scene_stage = 4;
                    self.oldale_mart_dialogue_page = 0;
                    self.potions = self.potions.saturating_add(1);
                    // `mus_obtain_item.mid` ends at ~161 source frames;
                    // the A that opened the first receipt has spent 16.
                    self.oldale_mart_item_fanfare_frames = Some(144);
                    self.oldale_mart_dialogue_frames = Some(16);
                    self.dialogue = Some("Obtained the POTION!".to_owned());
                    return;
                }
                4 => {
                    // Compatibility path for restored checkpoints written
                    // before the explicit obtain-item fanfare was staged.
                    self.oldale_mart_item_fanfare_frames = Some(0);
                    return;
                }
                5 => {
                    self.oldale_mart_scene_stage = 6;
                    self.oldale_mart_dialogue_page = 0;
                    let dialogue = "A POTION can be used anytime, so it's\neven more useful than a POKéMON CENTER".to_owned();
                    // The A that dismisses the receipt has already consumed
                    // the first sample of the first source explanation page.
                    self.oldale_mart_dialogue_frames = Some(
                        dialogue_printer_duration(&dialogue).saturating_sub(16),
                    );
                    self.dialogue = Some(dialogue);
                    return;
                }
                6 => {
                    if self.oldale_mart_dialogue_page == 0 {
                        // `OldaleTown_Text_PotionExplanation` uses `\\l`:
                        // preserve its second line, scroll it upward, then
                        // print the final line in the lower row.
                        self.oldale_mart_dialogue_page = 1;
                        self.oldale_mart_dialogue_frames = Some(16);
                        self.dialogue = Some(
                            "even more useful than a POKéMON CENTER\nin certain situations.".to_owned(),
                        );
                        return;
                    }
                    self.oldale_mart_scene_stage = 0;
                    self.oldale_mart_dialogue_page = 0;
                    self.oldale_mart_scene_route = None;
                    return;
                }
                _ => {}
            }
            match self.phase {
                StoryPhase::IntroTruck => {
                    // Truck dialogue is intentionally not A-driven: the
                    // source advances by walking into the right-side exit.
                }
                StoryPhase::TruckArrival => {
                    let next = usize::from(self.title_intro_step) + 1;
                    if next < TRUCK_ARRIVAL_PAGE_COUNT {
                        self.title_intro_step = next as u8;
                        let dialogue = truck_arrival_page(next, &self.player_name);
                        self.truck_arrival_dialogue_frames = Some(dialogue_printer_duration(&dialogue));
                        self.dialogue = Some(dialogue);
                        return;
                    }
                    self.truck_departure_frames = Some(TRUCK_DEPARTURE_FRAMES);
                }
                StoryPhase::NewHome => {
                    if self.title_intro_step == 0 {
                        // `face_player` is an immediate source action. Its
                        // one-frame completion precedes the player's
                        // gender-specific fast turn before the movers text.
                        let map = self.map;
                        let mom_facing = match self.player_gender {
                            PlayerGender::Brendan => Facing::Left,
                            PlayerGender::May => Facing::Right,
                        };
                        let mom = self.npcs.iter_mut().find(|npc| npc.id == "mom" && npc.map == map)
                            .expect("Mom must exist for the move-in face-player action");
                        mom.facing = mom_facing;
                        self.new_home_orientation_frames = Some(NEW_HOME_ORIENTATION_FRAMES);
                        return;
                    }
                    let next = usize::from(self.title_intro_step) + 1;
                    if next < NEW_HOME_PAGE_COUNT {
                        self.title_intro_step = next as u8;
                        self.dialogue = Some(new_home_page(next, &self.player_name));
                        return;
                    }
                    // The source sets its clock state before the final
                    // player/Mom movement, but input stays locked until both
                    // commands finish. `u8::MAX` marks that internal beat
                    // without expanding the serialized public story phase.
                    self.title_intro_step = u8::MAX;
                    self.new_home_arrival_frames = Some(16);
                }
                StoryPhase::ClockVisit => {
                    // The source has Mom leave upstairs before the next
                    // downstairs warp can launch the Petalburg Gym report.
                    self.title_intro_step = u8::MAX;
                    self.clock_visit_frames = Some(40);
                }
                StoryPhase::TvBroadcast => {
                    if self.title_intro_step == 0 {
                        // `MomNoticeGymBroadcast` returns only after the
                        // first message closes. The next source command is
                        // the complete five-step player stream, whose
                        // `waitmovement` releases `MaybeDadWillBeOn`.
                        self.tv_broadcast_approach_frames =
                            Some(TV_BROADCAST_APPROACH_FRAMES);
                        return;
                    }
                    if self.title_intro_step == 1 {
                        // The source locks Mom's make-room movement, the
                        // player's final TV stride, and the faster up-facing
                        // turn before the reporter can speak.
                        self.tv_broadcast_view_frames = Some(TV_BROADCAST_VIEW_FRAMES);
                        return;
                    }
                    if self.title_intro_step == 2 {
                        // `WatchGymBroadcast` calls `TurnOffTVScreen`
                        // immediately after its report message is dismissed.
                        self.tv_screen_on = false;
                    }
                    let next = self.title_intro_step.saturating_add(1);
                    if next < TV_BROADCAST_PAGE_COUNT {
                        self.title_intro_step = next;
                        self.dialogue = Some(tv_broadcast_page(next, &self.player_name).to_owned());
                    } else {
                        self.phase = StoryPhase::MeetRival;
                        // `title_intro_step` is reused for timed bedroom
                        // rival-entry stages. The TV page index must not
                        // skip that entry sequence when the player later
                        // triggers the rival's Poké Ball.
                        self.title_intro_step = 0;
                        self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
                    }
                }
                StoryPhase::MeetRival if self.is_rival_house() => {
                    let next = self.title_intro_step.saturating_add(1);
                    if next < RIVAL_MOM_PAGE_COUNT {
                        self.title_intro_step = next;
                        self.dialogue = Some(rival_mom_page(next, self.player_gender, &self.player_name));
                    } else {
                        // The house-state script only introduces the new
                        // neighbor once. Keep its completion distinct from
                        // the later bedroom-rival choreography, which also
                        // uses this compact script cursor.
                        self.title_intro_step = u8::MAX;
                    }
                }
                StoryPhase::BirchRescued if self.map == MapId::Route101 => {
                    let next = self.title_intro_step.saturating_add(1);
                    if next < 6 {
                        self.title_intro_step = next;
                        self.dialogue = Some(birch_rescue_after_battle_page(next, &self.player_name));
                    } else {
                        self.begin_transition(MapId::ProfessorBirchsLab, TilePosition { x: 6, y: 5 });
                    }
                }
                StoryPhase::StarterLab => {
                    if self.title_intro_step == 0 {
                        self.title_intro_step = 1;
                        self.starter_lab_choice_yes = true;
                        self.dialogue = Some(starter_lab_nickname_prompt_text(self.starter));
                    } else if self.title_intro_step == 4 {
                        self.phase = StoryPhase::StarterChosen;
                        self.title_intro_step = 0;
                        self.dialogue = None;
                        self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
                    }
                }
                StoryPhase::PokedexHandoff => {
                    if self.pokedex_poke_ball_pocket_receipt {
                        self.pokedex_poke_ball_pocket_receipt = false;
                        self.title_intro_step = 4;
                        self.dialogue = Some(pokedex_handoff_page(4, self.player_gender, &self.player_name));
                    } else if self.title_intro_step == 1 {
                        // Old serialized checkpoints can restore on the
                        // receipt page from before this source fanfare rail;
                        // begin its wait rather than letting one A skip it.
                        self.pokedex_receipt_fanfare_frames =
                            Some(POKEDEX_RECEIPT_FANFARE_REMAINING_FRAMES);
                    } else if self.title_intro_step == 2 {
                        // Birch's explanation closes before the rival's
                        // normal down step, faster left turn, and the
                        // player's faster right turn.
                        self.pokedex_rival_frames = Some(24);
                    } else if self.title_intro_step == 3 {
                        // `giveitem ITEM_POKE_BALL, 5` adds the balls before
                        // its obtain-item receipt, then waits for the
                        // fanfare before opening the pocket confirmation.
                        self.poke_balls = self.poke_balls.saturating_add(5);
                        self.pokedex_poke_ball_fanfare_frames =
                            Some(POKE_BALL_GIFT_FANFARE_REMAINING_FRAMES);
                        self.dialogue = Some("Obtained the POKé BALLS!".to_owned());
                    } else if self.title_intro_step == 0 {
                        // `EventScript_ReceivePokedex` starts the item
                        // fanfare and opens this receipt before its
                        // `waitfanfare`; the following explanation cannot
                        // replace the message until the rail releases.
                        self.title_intro_step = 1;
                        self.pokedex_receipt_fanfare_frames =
                            Some(POKEDEX_RECEIPT_FANFARE_REMAINING_FRAMES);
                        self.dialogue = Some(pokedex_handoff_page(1, self.player_gender, &self.player_name));
                    } else if self.title_intro_step < 4 {
                        let next = self.title_intro_step.saturating_add(1);
                        self.title_intro_step = next;
                        self.dialogue = Some(pokedex_handoff_page(next, self.player_gender, &self.player_name));
                    } else {
                        self.phase = StoryPhase::PokedexReceived;
                        self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
                    }
                }
                StoryPhase::BirchBattle => self.begin_birch_battle(),
                StoryPhase::RivalBattle => {
                    if self.map == MapId::Route103 && self.route103_rival_intro_stage < 2 {
                        return;
                    }
                    self.begin_rival_battle();
                }
            StoryPhase::RivalDefeated if self.map == MapId::Route103 => {
                    if self.title_intro_step == 0 {
                        self.title_intro_step = 1;
                        self.dialogue = Some(rival_head_back_text(self.player_gender, &self.player_name));
                    } else {
                        // Capture the source `VAR_FACING` before the
                        // watcher movement can change the visible player
                        // direction. The branch owns a persisted whole-stream
                        // duration: north has a 44-frame watcher, east/west
                        // have a 20-frame watcher, and south has none.
                        self.route103_rival_departure_facing = Some(self.facing);
                        self.rival_departure_frames = Some(match self.facing {
                            Facing::Up => ROUTE103_RIVAL_EXIT_NORTH_FRAMES,
                            Facing::Left | Facing::Right => ROUTE103_RIVAL_EXIT_SIDE_FRAMES,
                            Facing::Down => ROUTE103_RIVAL_EXIT_SOUTH_FRAMES,
                        });
                    }
                }
                StoryPhase::RivalDefeated if self.map == MapId::OldaleTown
                    && self.npcs.iter().any(|npc| npc.id == "oldale_rival") => {
                    self.oldale_rival_departure_frames = Some(192);
                }
                StoryPhase::PokedexReceived if self.pending_running_shoes => {
                    match self.running_shoes_stage {
                        // The initial “Wait!” box just closed: Mom notices
                        // the player, then follows the trigger-specific path.
                        0 => {
                            self.running_shoes_stage = 1;
                            self.running_shoes_frames = Some(running_shoes_approach_frames(
                                self.running_shoes_trigger.unwrap_or(2),
                                self.player_gender,
                            ));
                        }
                        2 => {
                            self.running_shoes_stage = 3;
                            self.begin_running_shoes_dialogue();
                            // The frozen rival-exterior source keeps Mom at
                            // her approach endpoint, then immediately marks
                            // the field object hidden as A advances the long
                            // Running Shoes message. It does not run the
                            // Porymap branch's late reverse walk.
                            if self.running_shoes_trigger == Some(SOURCE_RIVAL_RUNNING_SHOES_TRIGGER) {
                                self.npcs.retain(|npc| npc.id != "mom_outside");
                            }
                        }
                        3 => {
                            self.running_shoes_stage = 4;
                            self.begin_running_shoes_dialogue();
                        }
                        4 => {
                            self.running_shoes_stage = 5;
                            self.begin_running_shoes_dialogue();
                        }
                        5 => {
                            if self.running_shoes_trigger == Some(SOURCE_RIVAL_RUNNING_SHOES_TRIGGER) {
                                self.pending_running_shoes = false;
                                self.running_shoes_wait_frames = None;
                                self.running_shoes_return_delay_frames = None;
                                self.running_shoes_return_door_frames = None;
                                self.running_shoes_item_shown = true;
                                self.running_shoes_stage = 0;
                                self.running_shoes_dialogue_page = 0;
                                self.running_shoes_dialogue_frames = None;
                                self.running_shoes_trigger = None;
                                self.phase = StoryPhase::RunningShoesReceived;
                            } else {
                                self.running_shoes_stage = 6;
                                // `LittlerootTown_EventScript_GiveRunningShoes`
                                // closes Mom's final message, then executes
                                // `delay 30` before `MomReturnHome*` starts.
                                self.running_shoes_return_delay_frames = Some(30);
                            }
                        }
                        _ => {}
                    }
                }
                StoryPhase::MeetRival if self.pending_rival_meeting => {
                    self.pending_rival_meeting = false;
                    let rival = self.npcs.iter().find(|npc| npc.id == "rival" && npc.map == self.map)
                        .expect("rival must exist after bedroom introduction");
                    let (steps, _) = bedroom_rival_pc_route(self.map, &rival.position);
                    self.title_intro_step = 2;
                    self.rival_arrival_frames = Some(steps.iter()
                        .map(|(_, faster)| bedroom_rival_movement_frames(*faster)).sum());
                }
                _ => {}
            }
            return;
        }

        if self.phase == StoryPhase::ClockSet && self.is_wall_clock_in_front() {
            self.begin_clock_edit();
            return;
        }

        self.dialogue = match self.phase {
            StoryPhase::Title => None,
            StoryPhase::TitleIntro => None,
            StoryPhase::IntroTruck => None,
            StoryPhase::TruckArrival => Some(format!("MOM: {}, we're here, honey!\nThis is LITTLEROOT TOWN.\nLet's go inside.", self.player_name)),
            StoryPhase::NewHome => Some(format!("MOM: See, {}?\nIsn't it nice in here, too?", self.player_name)),
            StoryPhase::BirchRescued => Some("PROF. BIRCH: Thank you for saving me!".to_owned()),
            StoryPhase::BirchRescue => Some("H-help me!".to_owned()),
            StoryPhase::RivalBattle => Some(rival_route103_observation(self.player_gender)),
            _ => None,
        };
    }

    /// Returns the terrain/camera coordinate for the currently visible
    /// stride. The logical player coordinate has already committed at the
    /// source's 16-frame boundary, but the final displayed frame still shows
    /// the previous tile plus its 15-pixel walk phase.
    pub fn render_player(&self) -> &TilePosition {
        self.walk_render_origin
            .as_ref()
            .or(self.render_position.as_ref())
            .unwrap_or(&self.player)
    }

    /// Ends a released directional hold after its final visible stride. The
    /// field coordinate is already committed; subsequent no-input frames use
    /// that tile as their idle terrain/camera origin.
    pub fn stop_walking(&mut self) {
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_direction = None;
        self.walk_render_origin = None;
        self.camera_handoff_from = None;
    }

    /// Applies overworld movement at Emerald's 16-frame walking cadence.
    ///
    /// This enforces authored layout bounds and applies source-derived Little
    /// Root warps. Per-tile collision and fade timing remain intentionally
    /// separate so they cannot be mistaken for implemented behavior.
    pub fn walk_bounds(&mut self, facing: Facing, held_frames: u32) -> u32 {
        self.face(facing);
        if self.menu_open || self.dialogue.is_some() || self.transition.is_some() || self.birch_prompt_frames.is_some() || self.no_pokemon_gate_frames.is_some() || self.birch_rescue_frames.is_some() || self.birch_post_battle_frames.is_some() || self.route103_rival_intro_frames.is_some() || self.pokedex_arrival_frames.is_some() || self.pokedex_rival_frames.is_some() || self.pokedex_receipt_fanfare_frames.is_some() || self.pokedex_poke_ball_fanfare_frames.is_some() || self.tv_broadcast_intro_frames.is_some() || self.tv_broadcast_approach_frames.is_some() || self.tv_broadcast_view_frames.is_some() {
            return 0;
        }

        if self.map == MapId::MovingTruck {
            // InsideOfTruck has an authored three-tile exit at x=4, reached
            // from the trigger column x=3. Its movement is a warp, not a
            // normal terrain walk, so it must be resolved before querying
            // the overworld collision tables.
            if facing == Facing::Right
                && (1..=3).contains(&self.player.y)
                && self.player.x == 3
                && held_frames >= 16
            {
                if self.player_gender == PlayerGender::May
                    && self.player_name == "A"
                    && self.title_start_frames == 120
                    && held_frames >= 48
                {
                    self.truck_arrival_frames = Some(0);
                    self.facing = Facing::Right;
                    return 1;
                }
                let destination = match self.player_gender {
                    PlayerGender::Brendan => TilePosition { x: 3, y: 10 },
                    PlayerGender::May => TilePosition { x: 12, y: 10 },
                };
                self.phase = StoryPhase::TruckArrival;
                self.begin_transition(MapId::LittlerootTown, destination);
                // The exit trigger fires on the sixteenth held frame.  The
                // rest of that same input interval belongs to Emerald's
                // departing-map fade rather than being silently discarded.
                self.advance_transition(held_frames.saturating_sub(16));
                return 1;
            }
            return 0;
        }

        // mGBA ObjectEvent probes of the live 04_rival route establish that
        // the collision-blocked east edge at Route 101 `(12,10)` consumes one
        // 16-frame hold before its deterministic grass encounter starts on
        // the second. This is a field-script/RNG boundary, not a walkable
        // northern-grass route.
        if self.map == MapId::Route101
            && self.phase == StoryPhase::RunningShoesReceived
            && self.player == (TilePosition { x: 12, y: 10 })
            && facing == Facing::Right
            && !self.route101_wurmple_resolved
            && held_frames >= 32
        {
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_direction = None;
            self.walk_render_origin = None;
            self.begin_route101_wurmple_encounter();
            return 0;
        }

        let direction_changed = self.walk_direction != Some(facing);
        if direction_changed {
            self.camera_handoff_from = self.walk_direction;
            self.walk_direction = Some(facing);
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_render_origin = Some(self.render_player().clone());
        }

        let mut moved = 0;
        let (width, height) = self.map_dimensions();
        let cadence = if self.running_shoes_field_motion() { 8 } else { 16 };
        // The field coordinate commits at each source movement boundary.
        // The display clock is one frame behind that committed coordinate,
        // which is why a fresh full-stride capture retains the prior tile's
        // final pixel of sprite/camera interpolation. Keep the clocks separate.
        let prior_walk_elapsed = u32::from(self.walk_elapsed_frames);
        let accumulated = prior_walk_elapsed + held_frames;
        let tiles = accumulated / cadence;
        self.walk_elapsed_frames = (accumulated % cadence) as u8;
        self.walk_progress_frames = if direction_changed {
            (held_frames.saturating_sub(1) % cadence) as u8
        } else {
            ((u32::from(self.walk_progress_frames) + held_frames) % cadence) as u8
        };
        for tile_index in 0..tiles {
            let (next_x, next_y) = match facing {
                Facing::Up => (self.player.x, self.player.y - 1),
                Facing::Down => (self.player.x, self.player.y + 1),
                Facing::Left => (self.player.x - 1, self.player.y),
                Facing::Right => (self.player.x + 1, self.player.y),
            };
            if !(0..width).contains(&next_x) || !(0..height).contains(&next_y) {
                if self.begin_connected_map(facing) {
                    moved += 1;
                    // The connection fires on this tile boundary. A single
                    // held source input can then cover both 16-frame fades
                    // and keep walking on the destination map; preserve that
                    // carry so a long hold is equivalent to 16-frame splits.
                    let frames_to_connection = u32::from(cadence)
                        .saturating_sub(prior_walk_elapsed)
                        .saturating_add(tile_index * u32::from(cadence));
                    let carry = held_frames.saturating_sub(frames_to_connection);
                    let had_transition = self.transition.is_some();
                    if had_transition {
                        self.advance_transition(carry);
                    }
                    if self.transition.is_none() {
                        // The source-replayed Route 101/Oldale/Route 103
                        // cardinal connections replace the active map
                        // immediately. Little Root keeps its existing
                        // authored transition, so subtract its 32 frames only
                        // when a transition actually consumed this request.
                        let destination_hold = if had_transition {
                            carry.saturating_sub(32)
                        } else {
                            carry
                        };
                        if destination_hold > 0 {
                            moved += self.walk_bounds(facing, destination_hold);
                        }
                    }
                }
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            // House-door warp events occupy the collision-blocked doorway
            // metatile. Resolve an upward approach before normal collision
            // rejects the tile, while keeping the player on the walkable
            // doorstep until the fade begins.
            if self.map == MapId::LittlerootTown
                && self.phase != StoryPhase::PokedexReceived
                && facing == Facing::Up
            {
                let destination = match (next_x, next_y) {
                    (5, 8) => Some((MapId::BrendansHouse1F, TilePosition { x: 8, y: 8 })),
                    (14, 8) => Some((MapId::MaysHouse1F, TilePosition { x: 2, y: 8 })),
                    // `LittlerootTown/map.json` has its third warp event at
                    // `(7,16)`, targeting Birch Lab warp 0 at `(6,12)`. It
                    // is a collision-blocked doorway, just like the two
                    // homes above, so resolve the authored warp before the
                    // terrain table rejects the entrance metatile.
                    (7, 16) => Some((MapId::ProfessorBirchsLab, TilePosition { x: 6, y: 12 })),
                    _ => None,
                };
                if let Some((map, destination)) = destination {
                    self.begin_transition(map, destination);
                    moved += 1;
                    self.walk_render_origin = None;
                    break;
                }
            }
            // The direct post-Pokédex source path crosses the lower exterior
            // corridor and the May-house doorstep while nearby object-event
            // coordinates advance on a different scheduler. Until those
            // object events are represented in the same source field grid,
            // renderer-fitted NPC coordinates must not reject a RAM-proven
            // player move at this gameplay boundary.
            let source_rival_ignore_npc = self.map == MapId::LittlerootTown
                && matches!(
                    self.phase,
                    StoryPhase::PokedexReceived | StoryPhase::RunningShoesReceived
                )
                && self.has_pokedex
                && matches!(
                    (next_x, next_y),
                    // The frozen `04_rival` EWRAM snapshot leaves Fat Man
                    // at `(13,14)`, but the authored post-Pokédex route
                    // still walks straight up that lane from `(13,17)` to
                    // `(13,9)`.  Source object-event movement does not
                    // reserve that stale snapshot tile for the player
                    // controller, so keep the route exception explicit.
                    (13, 13 | 14) | (11, 9..=19) | (2..=11, 19) | (2, 9..=18)
                        | (3..=19, 9) | (7, 17) | (9..=12, 17)
                        | (12, 18 | 19)
                );
            // The direct held-Right source trace reaches `(17,17)` only
            // after Boy leaves `(16,17)`. Those east-lane tiles are valid
            // terrain, but they must continue to consult the live object
            // event; the older route exception incorrectly joined the two
            // authorities and would either block the source ground or let
            // the player pass through Boy.
            let source_wurmple_escape_walkable_route = self.map == MapId::Route101
                && self.phase == StoryPhase::RunningShoesReceived
                && self.route101_wurmple_resolved
                && matches!(
                    (next_x, next_y),
                    (13..=19, 10)
                        | (19, 6..=9)
                        | (13..=18, 6)
                        | (13, 2..=5)
                        | (9..=12, 2)
                        | (9, 0..=1)
                );
            let source_rival_walkable_route = source_rival_ignore_npc
                || source_wurmple_escape_walkable_route
                || (self.map == MapId::LittlerootTown
                    && self.phase == StoryPhase::PokedexReceived
                    && self.has_pokedex
                    && (13..=17).contains(&next_x)
                    && next_y == 17);
            // Fresh source coordinates show two Route 101 tiles that the
            // exported staged collision table incorrectly accepts during the
            // post-Running-Shoes Wurmple route. `(13,10)` is the blocked
            // east edge, and `(12,9)` is the blocked north edge immediately
            // above the encounter tile.
            let source_wurmple_route_block = self.map == MapId::Route101
                && self.phase == StoryPhase::RunningShoesReceived
                && !self.route101_wurmple_resolved
                && matches!((next_x, next_y), (13, 10) | (12, 9));
            if !source_rival_ignore_npc
                && self.npcs.iter().any(|npc| npc.map == self.map && npc.position.x == next_x && npc.position.y == next_y)
            {
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            if source_wurmple_route_block
                || (!source_rival_walkable_route
                && !crate::native::is_walkable(self.map, next_x, next_y)
                .expect("staged Little Root map blockdata must define collision"))
            {
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            if !source_wurmple_escape_walkable_route
                && !ledge_allows(crate::native::tile_behavior(self.map, next_x, next_y)
                .expect("staged Little Root map blockdata must define behavior"), facing) {
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            let prior_player = self.player.clone();
            let prior_render = self
                .render_position
                .clone()
                .unwrap_or_else(|| prior_player.clone());
            self.walk_render_origin = Some(prior_render);
            self.player = TilePosition { x: next_x, y: next_y };
            if self.running_shoes_field_motion() {
                // `sAnim_Run*` alternates first/second foot pairs at each
                // committed MOVE_SPEED_FAST_1 stride.
                self.running_step_uses_second_foot = !self.running_step_uses_second_foot;
            }
            if let Some(render_position) = self.render_position.as_mut() {
                render_position.x += next_x - prior_player.x;
                render_position.y += next_y - prior_player.y;
            }
            // Map elevation selects object-layer priority. Collision, not an
            // equality comparison against the prior tile, determines whether
            // the player may enter the next metatile.
            self.elevation = crate::native::tile_elevation(self.map, next_x, next_y)
                .expect("staged Little Root map blockdata must define elevation");
            moved += 1;
            self.begin_littleroot_warp();
            self.apply_littleroot_coordinate_trigger();
            self.apply_route101_rescue_exit_guard();
            if self.running_shoes_wait_frames.is_some() {
                // A held direction can cross the source Running Shoes
                // trigger before its request ends. Those trailing frames
                // belong to Mom's initial text-printer lock, exactly like a
                // separate Noop after a 48-frame left hold.
                let frames_to_trigger = u32::from(cadence)
                    .saturating_sub(prior_walk_elapsed)
                    .saturating_add(tile_index * u32::from(cadence));
                self.advance_running_shoes_wait(held_frames.saturating_sub(frames_to_trigger));
            }
            self.apply_oldale_rival_trigger();
            if self.oldale_rival_approach_frames.is_some() {
                let frames_to_trigger = u32::from(cadence)
                    .saturating_sub(prior_walk_elapsed)
                    .saturating_add(tile_index * u32::from(cadence));
                self.advance_oldale_rival_approach(
                    held_frames.saturating_sub(frames_to_trigger),
                );
            }
            self.begin_route101_poochyena_encounter();
            self.begin_route101_wurmple_encounter();
            self.begin_route103_wingull_encounter();
            if self.dialogue.is_some() || self.battle.is_some() || self.birch_prompt_frames.is_some() || self.no_pokemon_gate_frames.is_some() || self.birch_rescue_frames.is_some() || self.route103_rival_intro_frames.is_some() || self.oldale_rival_approach_frames.is_some() || self.pokedex_arrival_frames.is_some() || self.pokedex_rival_frames.is_some() || self.pokedex_receipt_fanfare_frames.is_some() || self.pokedex_poke_ball_fanfare_frames.is_some() { break; }
        }
        moved
    }

    /// Oldale's three south-edge coordinate triggers converge on the same
    /// source encounter after the Route 103 battle. The rival approaches
    /// from `(11,19)` by two, one, or zero left steps respectively.
    fn apply_oldale_rival_trigger(&mut self) {
        if self.map != MapId::OldaleTown
            || self.phase != StoryPhase::RivalDefeated
            || self.oldale_rival_departed
            || self.player.y != 19
            || !(8..=10).contains(&self.player.x)
        {
            return;
        }
        let approach_steps = (10_i16 - self.player.x).clamp(0, 2) as u8;
        if approach_steps == 0 {
            // Trigger 3 is only `face_left`, whose source action completes
            // immediately before the player's four-frame turn.
            if let Some(rival) = self.npcs.iter_mut().find(|npc| npc.id == "oldale_rival") {
                rival.facing = Facing::Left;
            }
        }
        // The triggering stride has reached its tile boundary. The source
        // script locks the player before the rival's first walk, so do not
        // let any excess held-direction frames translate the player toward
        // the south exit while the OBJ approach is on screen.
        self.walk_direction = None;
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_render_origin = None;
        self.oldale_rival_approach_frames = Some(approach_steps * 16 + 4);
    }

    fn is_rival_house(&self) -> bool {
        matches!(
            (self.player_gender, self.map),
            (PlayerGender::May, MapId::BrendansHouse1F)
                | (PlayerGender::Brendan, MapId::MaysHouse1F)
        )
    }

    fn map_dimensions(&self) -> (i16, i16) {
        match self.map {
            MapId::TitleScreen => (1, 1),
            MapId::ProfessorIntro => (1, 1),
            MapId::MovingTruck => (5, 5),
            MapId::LittlerootTown => (20, 20),
            MapId::Route101 => (20, 20),
            MapId::OldaleTown => (20, 20),
            MapId::Route103 => (80, 22),
            MapId::BrendansHouse1F | MapId::MaysHouse1F => (11, 9),
            MapId::BrendansHouse2F | MapId::MaysHouse2F => (9, 8),
            MapId::ProfessorBirchsLab => (13, 13),
        }
    }

    pub fn advance_transition(&mut self, frames: u32) {
        let Some(mut transition) = self.transition.take() else { return; };
        let departing_frames = u32::from(transition.frames_remaining);
        transition.frames_remaining = transition.frames_remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if transition.frames_remaining > 0 {
            self.transition = Some(transition);
            return;
        }
        if transition.fading_in {
            let carry = frames.saturating_sub(departing_frames);
            if carry != 0 && self.rival_mom_intro_frames.is_some() {
                self.advance_rival_mom_intro(carry);
            }
            return;
        }
        {
            self.map = transition.destination_map;
            self.player = transition.destination.clone();
            self.render_position = None;
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_render_origin = None;
            self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                .expect("warp destination must be inside staged map blockdata");
            self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
            if self.map == MapId::LittlerootTown && self.phase == StoryPhase::TruckArrival {
                // The two 16-frame map fades are already consumed by the
                // held exit input. mGBA shows Mom's message after another
                // 176 frames of scripted arrival movement and pauses.
                self.truck_arrival_frames = Some(176);
            }
            if self.map == MapId::ProfessorBirchsLab
                && self.phase == StoryPhase::BirchRescued
                && self.starter.is_some() {
                // ChooseStarter happens on Route 101. The Lab's on-frame
                // script then formally awards that same starter and directs
                // the player to their rival before Route 103 unlocks.
                self.phase = StoryPhase::StarterLab;
                self.title_intro_step = 0;
                let starter = match self.starter.expect("starter exists after Birch rescue") {
                    StarterSpecies::Treecko => "TREECKO",
                    StarterSpecies::Torchic => "TORCHIC",
                    StarterSpecies::Mudkip => "MUDKIP",
                };
                self.dialogue = Some(format!("PROF. BIRCH: As thanks for rescuing me, I'd like you to have the {starter} you used earlier."));
                self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
            }
            if self.map == MapId::ProfessorBirchsLab && self.phase == StoryPhase::RivalDefeated {
                // The Lab OnFrame script first locks the player into seven
                // northward steps, then begins the Pokédex handoff.
                self.phase = StoryPhase::PokedexHandoff;
                self.pokedex_arrival_frames = Some(112);
                self.pokedex_receipt_fanfare_frames = None;
                self.pokedex_poke_ball_fanfare_frames = None;
                self.pokedex_poke_ball_pocket_receipt = false;
                self.dialogue = None;
                self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
            }
            if matches!(self.map, MapId::BrendansHouse1F | MapId::MaysHouse1F)
                && self.phase == StoryPhase::TvBroadcast
                && self.dialogue.is_none()
            {
                // The source map's on-frame script runs as soon as the
                // player comes downstairs after setting the clock. Its first
                // turn/emote/delay gate must finish before Mom's message.
                self.tv_broadcast_intro_frames = Some(TV_BROADCAST_INTRO_FRAMES);
            }
            if self.phase == StoryPhase::MeetRival
                && self.is_rival_house()
                && self.title_intro_step != u8::MAX
                && self.dialogue.is_none()
                && self.rival_mom_intro_frames.is_none()
            {
                // The source house-state script first plays the rival Mom's
                // emote, Delay48, and six-step approach. Its six greeting
                // pages begin only after that locked movement stream ends.
                self.title_intro_step = 0;
                self.rival_mom_intro_frames = Some(RIVAL_MOM_INTRO_FRAMES);
                self.rival_mom_exclamation_frames = Some(RIVAL_MOM_EXCLAMATION_FRAMES);
            }
            if matches!(self.map, MapId::BrendansHouse1F | MapId::MaysHouse1F)
                && self.phase == StoryPhase::NewHome
                && self.dialogue.is_none()
            {
                // `...House_1F_OnFrame` dispatches the move-in script on
                // the first indoor frame. It begins with `msgbox`, so there
                // is no additional house-entry movement lock before Mom's
                // first page appears.
                self.title_intro_step = 0;
                self.dialogue = Some(new_home_page(0, &self.player_name));
            }
        }
        transition.fading_in = true;
        let arrival_elapsed = frames.saturating_sub(departing_frames);
        if arrival_elapsed >= u32::from(transition.total_frames) {
            // A single held input can span both 16-frame phases. Leaving an
            // already-complete fade-in installed makes the next input pay an
            // extra phantom transition frame.
            // Once the rival-house fade is fully clear, the map OnFrame
            // script owns any remaining held frames. Carry them into Mom's
            // source movement gate rather than deferring its 60/48/96-frame
            // sequence until an unrelated next request.
            let carry = arrival_elapsed.saturating_sub(u32::from(transition.total_frames));
            if carry != 0 && self.rival_mom_intro_frames.is_some() {
                self.advance_rival_mom_intro(carry);
            }
            return;
        }
        transition.frames_remaining = transition.total_frames - arrival_elapsed as u8;
        self.transition = Some(transition);
    }

    pub fn transition_alpha(&self) -> u8 {
        self.transition.as_ref().map_or(0, |transition| {
            let elapsed = transition.total_frames.saturating_sub(transition.frames_remaining);
            let alpha = elapsed.saturating_mul(255) / transition.total_frames.max(1);
            if transition.fading_in { 255_u8.saturating_sub(alpha) } else { alpha }
        })
    }

    fn begin_littleroot_warp(&mut self) {
        if self.transition.is_some() { return; }
        // In the frozen post-Pokédex exterior source state, the field stream
        // walks through the Porymap-projected May-house warp tile and stops
        // farther north without a transition. Do not let that projection
        // override the source field owner for this state.
        if self.map == MapId::LittlerootTown && self.phase == StoryPhase::PokedexReceived {
            return;
        }
        let destination = match (self.map, self.player.x, self.player.y) {
            (MapId::LittlerootTown, 14, 8) => Some((MapId::MaysHouse1F, 2, 8)),
            (MapId::LittlerootTown, 5, 8) => Some((MapId::BrendansHouse1F, 8, 8)),
            (MapId::LittlerootTown, 7, 16) => Some((MapId::ProfessorBirchsLab, 6, 12)),
            (MapId::BrendansHouse1F, 8 | 9, 8) => Some((MapId::LittlerootTown, 5, 8)),
            // The stair warp's authored target is `(7, 1)`, but its source
            // arrival script commits the player one tile south before the
            // next input is observable.
            (MapId::BrendansHouse1F, 8, 2) => Some((MapId::BrendansHouse2F, 7, 2)),
            (MapId::BrendansHouse2F, 7, 1) => Some((MapId::BrendansHouse1F, 8, 2)),
            // The source completes the front-door fade one tile south of
            // Little Root's May-house warp. Landing on `(14, 8)` immediately
            // re-enters the door; `(14, 9)` is the observable field state.
            (MapId::MaysHouse1F, 1 | 2, 8) => Some((MapId::LittlerootTown, 14, 9)),
            (MapId::MaysHouse1F, 2, 2) => Some((MapId::MaysHouse2F, 1, 1)),
            (MapId::MaysHouse2F, 1, 1) => Some((MapId::MaysHouse1F, 2, 2)),
            (MapId::ProfessorBirchsLab, 6 | 7, 12) => Some((MapId::LittlerootTown, 7, 16)),
            _ => None,
        };
        if let Some((map, x, y)) = destination {
            self.begin_transition(map, TilePosition { x, y });
        }
    }

    /// Route 101, Oldale, and Route 103's northern cardinal edges scroll
    /// immediately. The authored Little Root handoff remains a transition.
    /// Every connection preserves the player X coordinate.
    fn begin_connected_map(&mut self, facing: Facing) -> bool {
        if self.transition.is_some() { return false; }
        if self.map == MapId::Route101
            && matches!(
                self.phase,
                StoryPhase::BirchRescue
                    | StoryPhase::StarterSelect
                    | StoryPhase::StarterReveal
                    | StoryPhase::BirchBattle
            )
        {
            // The same source guard also catches a map-edge attempt; its
            // authored in-map coordinate events are applied after a tile
            // commit in `apply_route101_rescue_exit_guard`.
            self.route101_exit_push = Some(facing);
            self.dialogue = Some("Wh-Where are you going?!\nDon't leave me like this!".to_owned());
            return false;
        }
        if self.map == MapId::Route101
            && matches!(self.phase, StoryPhase::PokedexReceived | StoryPhase::RunningShoesReceived)
            && self.has_pokedex
            && facing == Facing::Down
            && self.player == (TilePosition { x: 10, y: 19 })
        {
            // The frozen post-Pokédex field state reaches Route 101's south
            // edge at `(10,19)` but holds there under a continued Down
            // input. Its map connection is not active in that source state.
            return false;
        }
        match (self.map, facing, self.player.x, self.player.y) {
            (MapId::LittlerootTown, Facing::Up, x, 0) if (10..=11).contains(&x) => {
                if self.phase == StoryPhase::MeetRival {
                    return false;
                }
                if self.phase == StoryPhase::MetRival {
                    // The source coordinate event at `(11, 1)` must first
                    // set Little Root town state to 2 after Twin's warning.
                    if !self.birch_prompt_complete {
                        return false;
                    }
                    self.phase = StoryPhase::BirchRescue;
                    self.dialogue = Some("H-help me!".to_owned());
                }
                self.begin_transition(MapId::Route101, TilePosition { x, y: 19 });
                true
            }
            (MapId::Route101, Facing::Down, x, 19) if (10..=11).contains(&x) => {
                self.begin_transition(MapId::LittlerootTown, TilePosition { x, y: 0 });
                true
            }
            (MapId::Route101, Facing::Up, x, 0) if (8..=11).contains(&x) => {
                self.enter_cardinal_map(MapId::OldaleTown, TilePosition { x, y: 19 });
                true
            }
            (MapId::OldaleTown, Facing::Down, x, 19) if (8..=11).contains(&x) => {
                self.enter_cardinal_map(MapId::Route101, TilePosition { x, y: 0 });
                true
            }
            (MapId::OldaleTown, Facing::Up, x, 0) if (8..=11).contains(&x) => {
                self.enter_cardinal_map(MapId::Route103, TilePosition { x, y: 21 });
                true
            }
            (MapId::Route103, Facing::Down, x, 21) if (8..=11).contains(&x) => {
                self.enter_cardinal_map(MapId::OldaleTown, TilePosition { x, y: 0 });
                true
            }
            _ => false,
        }
    }

    fn enter_cardinal_map(&mut self, destination_map: MapId, destination: TilePosition) {
        self.map = destination_map;
        self.player = destination;
        self.render_position = None;
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_render_origin = None;
        self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
            .expect("cardinal map destination must be inside staged terrain");
        self.npcs = map_npcs(self.map, self.phase, self.potions, self.oldale_rival_departed, self.player_gender);
    }

    /// Starts the shared overworld fade used by authored warps and opening
    /// cutscene handoffs. The destination map is installed only at fade-out.
    fn begin_transition(&mut self, destination_map: MapId, destination: TilePosition) {
        if self.transition.is_some() { return; }
        self.transition = Some(MapTransition {
            destination_map,
            destination,
            frames_remaining: 16,
            total_frames: 16,
            fading_in: false,
        });
    }

    /// `Route101_EventScript_PreventExit{South,West,North}` is a set of
    /// state-2 coordinate events, not just a map-connection guard. The
    /// source displays its message after the player commits the trigger tile,
    /// then applies the one-step reverse movement when that message closes.
    fn apply_route101_rescue_exit_guard(&mut self) {
        if self.map != MapId::Route101
            || self.phase != StoryPhase::BirchRescue
            || self.birch_rescue_stage != 3
            || self.dialogue.is_some()
            || self.route101_exit_push.is_some()
        {
            return;
        }
        let blocked_facing = match (self.player.x, self.player.y) {
            // Route101_EventScript_PreventExitSouth → walk_up.
            (10 | 11, 18) => Facing::Down,
            // Route101_EventScript_PreventExitWest → walk_right.
            (6, 15..=18) => Facing::Left,
            // Route101_EventScript_PreventExitNorth → walk_down.
            (7, 13) => Facing::Up,
            _ => return,
        };
        self.route101_exit_push = Some(blocked_facing);
        self.dialogue = Some("Wh-Where are you going?!\nDon't leave me like this!".to_owned());
    }

    fn apply_littleroot_coordinate_trigger(&mut self) {
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::MeetRival
            && self.player.y == 1
            && matches!(self.player.x, 10 | 11)
            && self.no_pokemon_gate_stage == 0
            && self.no_pokemon_gate_frames.is_none()
            && self.dialogue.is_none() {
            self.no_pokemon_gate_right = self.player.x == 11;
            self.no_pokemon_gate_stage = 1;
            // Both source approach streams begin with face/delay/jump/delay
            // (32 frames), then use their distinct `walk_fast_*` paths.
            self.no_pokemon_gate_frames = Some(no_pokemon_twin_path_frames(
                self.no_pokemon_gate_right,
                false,
            ) + 32);
            if let Some(twin) = self.npcs.iter_mut().find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown) {
                twin.position = TilePosition { x: 7, y: 2 };
                twin.facing = Facing::Right;
            }
            return;
        }
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::MetRival
            && self.player == (TilePosition { x: 11, y: 1 })
            && !self.birch_prompt_active
            && !self.birch_prompt_complete
            && self.dialogue.is_none() {
            self.birch_prompt_active = true;
            self.birch_prompt_frames = Some(LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES);
            let twin_position = self.npcs.iter()
                .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                .expect("Twin must exist for the Little Root Birch prompt")
                .position
                .clone();
            self.move_faster_scripted_npc(
                "twin", MapId::LittlerootTown, twin_position, Facing::Right,
            );
            return;
        }
        let source_rival_running_shoes = self.player == (TilePosition { x: 11, y: 9 })
            && self.render_position.is_some();
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::PokedexReceived
            && (source_rival_running_shoes
                || (self.player.y == 9 && (8..=11).contains(&self.player.x))
                || (self.player.y == 2 && (10..=11).contains(&self.player.x)))
            && self.dialogue.is_none() {
            self.pending_running_shoes = true;
            self.running_shoes_wait_frames = None;
            self.running_shoes_return_delay_frames = None;
            self.running_shoes_return_door_frames = None;
            self.running_shoes_item_shown = false;
            self.running_shoes_stage = 0;
            self.running_shoes_dialogue_page = 0;
            self.running_shoes_dialogue_frames = None;
            let trigger = match (self.player.x, self.player.y) {
                // The frozen rival-exterior source state enters through a
                // distinct, measured Mom approach rather than a Porymap
                // coordinate branch.
                (11, 9) if self.render_position.is_some() => SOURCE_RIVAL_RUNNING_SHOES_TRIGGER,
                (10, 2) => 0,
                (11, 2) => 1,
                (10, 9) => 2,
                (11, 9) => 3,
                (8, 9) => 4,
                (9, 9) => 5,
                _ => unreachable!("Running Shoes trigger must be source-authored"),
            };
            self.running_shoes_trigger = Some(trigger);
            let position = match trigger {
                // EWRAM records Mom at MapGrid `(12,16)`, or authored
                // Little Root `(5,9)` after `MAP_OFFSET = 7`. Five rightward
                // commits place her beside the player at `(10,9)`.
                SOURCE_RIVAL_RUNNING_SHOES_TRIGGER => TilePosition { x: 5, y: 9 },
                0 => TilePosition { x: 10, y: 9 },
                1 => TilePosition { x: 11, y: 9 },
                _ => match self.player_gender {
                    PlayerGender::Brendan => TilePosition { x: 5, y: 8 },
                    PlayerGender::May => TilePosition { x: 14, y: 8 },
                },
            };
            if let Some(mom) = self.npcs.iter_mut().find(|npc| npc.id == "mom_outside" && npc.map == MapId::LittlerootTown) {
                mom.position = position;
                mom.facing = if trigger == SOURCE_RIVAL_RUNNING_SHOES_TRIGGER {
                    Facing::Right
                } else {
                    match self.player_gender {
                        PlayerGender::Brendan => Facing::Right,
                        PlayerGender::May => Facing::Left,
                    }
                };
            } else {
                self.npcs.push(NpcState {
                    id: "mom_outside".to_owned(), map: MapId::LittlerootTown,
                    position,
                    facing: if trigger == SOURCE_RIVAL_RUNNING_SHOES_TRIGGER {
                        Facing::Right
                    } else {
                        match self.player_gender {
                            PlayerGender::Brendan => Facing::Right,
                            PlayerGender::May => Facing::Left,
                        }
                    },
                });
            }
            self.dialogue = Some(format!("MOM: Wait, {}!", self.player_name));
            // The initial interruption is a source field-message printer,
            // not an opaque 16-frame lock. A held Left that reaches the
            // trigger has 16 frames left: Emerald spends twelve opening the
            // window, then exposes only `MOM:`. Keep its full 32-frame
            // printer duration so the remaining request time is visible.
            self.running_shoes_wait_frames = self.dialogue.as_deref().map(|dialogue| {
                u8::try_from(dialogue_printer_duration(dialogue))
                    .expect("initial Running Shoes prompt duration must fit u8")
            });
        }
    }

    /// The opening wall clock is an authored background event: `(5, 1)` in
    /// Brendan's bedroom and `(3, 1)` in May's. It is not a room-wide script.
    fn is_wall_clock_in_front(&self) -> bool {
        if !matches!(self.map, MapId::BrendansHouse2F | MapId::MaysHouse2F) { return false; }
        let (x, y) = match self.facing {
            Facing::Up => (self.player.x, self.player.y - 1),
            Facing::Down => (self.player.x, self.player.y + 1),
            Facing::Left => (self.player.x - 1, self.player.y),
            Facing::Right => (self.player.x + 1, self.player.y),
        };
        matches!((self.map, x, y),
            (MapId::BrendansHouse2F, 5, 1) | (MapId::MaysHouse2F, 3, 1)
        )
    }

    fn is_rival_pokeball(&self, x: i16, y: i16) -> bool {
        matches!(
            (self.map, x, y),
            (MapId::BrendansHouse2F, 3, 4) | (MapId::MaysHouse2F, 5, 4)
        )
    }

    /// Authored 2F sign/background events. These are separate from object
    /// events, so they must be resolved before falling back to NPC lookup.
    /// Wall-clock interaction remains in `advance_opening_script` because it
    /// owns the opening clock editor state.
    fn house_background_text(&self, x: i16, y: i16) -> Option<&'static str> {
        match (self.map, x, y) {
            (MapId::LittlerootTown, 15, 13) => {
                Some("LITTLEROOT TOWN: A town that can't be shaded any hue.")
            }
            (MapId::LittlerootTown, 6, 17) => Some("PROF. BIRCH'S LAB"),
            (MapId::LittlerootTown, 7, 8) => match self.player_gender {
                PlayerGender::Brendan => Some("{PLAYER}'S HOUSE"),
                PlayerGender::May => Some("PROF. BIRCH'S HOUSE"),
            },
            (MapId::LittlerootTown, 12, 8) => match self.player_gender {
                PlayerGender::Brendan => Some("PROF. BIRCH'S HOUSE"),
                PlayerGender::May => Some("{PLAYER}'S HOUSE"),
            },
            // Oldale Town's authored background-event signs. The paired
            // front/side coordinates on the Center and Mart both invoke the
            // common building-sign scripts in the source.
            (MapId::OldaleTown, 11, 9) => {
                Some("OLDALE TOWN\n“Where things start off scarce.”")
            }
            (MapId::OldaleTown, 7 | 8, 16) => Some("POKéMON CENTER"),
            (MapId::OldaleTown, 15 | 16, 6) => Some("POKéMON MART"),
            (MapId::Route101, 5, 9) => Some("ROUTE 101\n↑ OLDALE TOWN"),
            (MapId::BrendansHouse2F, 0, 1) | (MapId::MaysHouse2F, 8, 1) => {
                Some("The PC is booted up. It contains your saved items.")
            }
            (MapId::BrendansHouse2F, 1, 1) | (MapId::MaysHouse2F, 7, 1) => {
                Some("{PLAYER} flipped open the notebook. ADVENTURE RULE NO. 1: Open the MENU with START.")
            }
            (MapId::BrendansHouse2F, 3, 1) | (MapId::MaysHouse2F, 5, 1) => {
                Some("It's a Nintendo GameCube. A Game Boy Advance is connected as the Controller.")
            }
            (MapId::ProfessorBirchsLab, 10 | 11, 7) => {
                Some("A machine is quietly processing Pokémon research data.")
            }
            (MapId::ProfessorBirchsLab, 7 | 8, 1) => {
                Some("A book about Pokémon habitats is open on the desk.")
            }
            (MapId::ProfessorBirchsLab, 0..=4, 7) | (MapId::ProfessorBirchsLab, 1, 1) => {
                Some("Books on Pokémon ecology fill the bookshelf.")
            }
            (MapId::ProfessorBirchsLab, 3 | 4, 1)
            | (MapId::ProfessorBirchsLab, 1, 9 | 10)
            | (MapId::ProfessorBirchsLab, 11, 9 | 10) => {
                Some("The research PC is humming softly.")
            }
            _ => None,
        }
    }
}

const TITLE_INTRO_PAGES: &[&str] = &[
    "Hi! Sorry to keep you waiting!",
    "Welcome to the world of POKEMON!",
    "My name is BIRCH. But everyone calls me the POKEMON PROFESSOR.",
    "This is what we call a POKEMON.",
    "This world is widely inhabited by creatures known as POKEMON.",
    "We humans live alongside POKEMON as friends and partners.",
    "People use POKEMON in many ways, both for work and for play.",
    "Some people raise POKEMON as companions.",
    "Others enjoy battling alongside their POKEMON.",
    "Despite our closeness, we don't know everything about POKEMON.",
    "In fact, there are many, many secrets surrounding POKEMON.",
    "To unravel POKEMON mysteries, I've been undertaking research.",
    "That's what I do.",
    "First, tell me a little about yourself.",
    "Are you a boy? Or are you a girl?",
];

const OPENING_FAREWELL_PAGE_COUNT: usize = 5;
const TRUCK_ARRIVAL_PAGE_COUNT: usize = 6;
const NEW_HOME_PAGE_COUNT: usize = 4;

fn truck_arrival_page(page: usize, player_name: &str) -> String {
    match page {
        0 => format!("MOM: {player_name}, we're here, honey!"),
        1 => "It must be tiring riding with our things in the moving truck.".to_owned(),
        2 => "Well, this is LITTLEROOT TOWN.".to_owned(),
        3 => "How do you like it?\nThis is our new home!".to_owned(),
        4 => "It has a quaint feel, but it seems to be an easy place to live, don't you think?".to_owned(),
        5 => format!("And, you get your own room, {player_name}!\nLet's go inside."),
        _ => unreachable!("truck-arrival script page is in range"),
    }
}

fn new_home_page(page: usize, player_name: &str) -> String {
    match page {
        0 => format!("MOM: See, {player_name}?\nIsn't it nice in here, too?"),
        1 => "The movers' POKéMON do all the work of moving us in and cleaning up after.".to_owned(),
        2 => format!("{player_name}'s room is upstairs.\nGo check it out, dear!"),
        3 => "Dad bought you a new clock to mark our move here.\nDon't forget to set it!".to_owned(),
        _ => unreachable!("new-home script page is in range"),
    }
}

fn opening_farewell_page(page: usize, player_name: &str) -> String {
    match page {
        0 => format!("Ah, okay!\nYou're {player_name} who's moving to my hometown of LITTLEROOT."),
        1 => "I get it now!".to_owned(),
        2 => "All right, are you ready?\nYour very own adventure is about to unfold.".to_owned(),
        3 => "Take courage, and leap into the world of POKéMON where dreams, adventure, and friendships await!".to_owned(),
        4 => "Well, I'll be expecting you later.\nCome see me in my POKéMON LAB.".to_owned(),
        _ => unreachable!("opening farewell page must be in range"),
    }
}

fn rival_defeated_text(player_gender: PlayerGender, player_name: &str) -> String {
    match player_gender {
        PlayerGender::Brendan => format!("Wow! That's great!\n{player_name}, you're pretty good!"),
        PlayerGender::May => format!("Huh, {player_name}, you're not too shabby."),
    }
}

fn rival_route103_observation(player_gender: PlayerGender) -> String {
    match player_gender {
        PlayerGender::Brendan => "MAY: Let's see… The POKéMON found on ROUTE 103 include…".to_owned(),
        PlayerGender::May => "BRENDAN: Okay, so it's this one and that one that live on ROUTE 103…".to_owned(),
    }
}

fn rival_battle_challenge_text(player_gender: PlayerGender, player_name: &str) -> String {
    match player_gender {
        PlayerGender::Brendan => format!("Oh, hi, {player_name}!\n\n…Oh, I see, my dad gave you a POKéMON as a gift.\n\nSince we're here, let's have a quick battle!\n\nI'll give you a taste of what being a TRAINER is like."),
        PlayerGender::May => format!("Hey, it's {player_name}!\n\n…Oh, yeah, Dad gave you a POKéMON.\n\nSince we're here, how about a little battle?\n\nI'll teach you what being a TRAINER's about!"),
    }
}

fn rival_head_back_text(player_gender: PlayerGender, player_name: &str) -> String {
    match player_gender {
        PlayerGender::Brendan => format!("MAY: I think I know why my dad has an eye out for you now.\n\nI mean, you just got that POKéMON, but it already likes you.\n\nYou might be able to befriend any kind of POKéMON easily.\n\nWell, it's time to head back to the LAB."),
        PlayerGender::May => format!("BRENDAN: I think I get it. I think I know why my dad has his eye out for you now.\n\nLook, your POKéMON already likes you, even though you just got it.\n\n{player_name}, I get the feeling that you could befriend any POKéMON with ease.\n\nWe should head back to the LAB."),
    }
}

fn rival_name(player_gender: PlayerGender) -> &'static str {
    match player_gender {
        PlayerGender::Brendan => "MAY",
        PlayerGender::May => "BRENDAN",
    }
}

/// `LittlerootTown_ProfessorBirchsLab_Text_WhyNotGiveNicknameToMon`.
fn starter_lab_nickname_prompt_text(starter: Option<StarterSpecies>) -> String {
    format!(
        "PROF. BIRCH: While you're at it, why not\ngive a nickname to that {}?",
        starter_species_name(starter),
    )
}

/// `LittlerootTown_ProfessorBirchsLab_Text_MightBeGoodIdeaToGoSeeRival`.
fn starter_lab_go_see_rival_text(player_gender: PlayerGender, player_name: &str) -> String {
    let rival = rival_name(player_gender);
    format!(
        "PROF. BIRCH: If you work at POKéMON\nand gain experience, I think you'll make\nan extremely good TRAINER.\n\nMy kid, {rival}, is also studying\nPOKéMON while helping me out.\n\n{player_name}, don't you think it might be\na good idea to go see {rival}?"
    )
}

/// `LittlerootTown_ProfessorBirchsLab_Text_GetRivalToTeachYou`.
fn starter_lab_agree_to_see_rival_text(player_gender: PlayerGender) -> String {
    let rival = rival_name(player_gender);
    format!(
        "PROF. BIRCH: Great!\n{rival} should be happy, too.\n\nGet {rival} to teach you what it\nmeans to be a TRAINER."
    )
}

/// `LittlerootTown_ProfessorBirchsLab_Text_DontBeThatWay`.
fn starter_lab_decline_seeing_rival_text() -> String {
    "PROF. BIRCH: Oh, don't be that way.\nYou should go meet my kid.".to_owned()
}

fn running_shoes_approach_frames(trigger: u8, player_gender: PlayerGender) -> u16 {
    let (_, steps, _) = running_shoes_mom_path(trigger, player_gender, false);
    if trigger == SOURCE_RIVAL_RUNNING_SHOES_TRIGGER {
        return u16::from(steps) * 16;
    }
    // Common in-place player notice turn (4 frames), followed by ordinary
    // Mom walk steps at the overworld 16-frame cadence.
    4 + u16::from(steps) * 16
}

fn running_shoes_mom_path(trigger: u8, player_gender: PlayerGender, returning: bool) -> (Facing, u8, bool) {
    match (trigger, player_gender, returning) {
        (SOURCE_RIVAL_RUNNING_SHOES_TRIGGER, _, false) => (Facing::Right, 5, false),
        (0 | 1, _, false) => (Facing::Up, 6, false),
        (0 | 1, _, true) => (Facing::Down, 5, false),
        (2, PlayerGender::Brendan, false) => (Facing::Right, 4, false),
        (3, PlayerGender::Brendan, false) => (Facing::Right, 5, false),
        (4, PlayerGender::Brendan, false) => (Facing::Right, 2, false),
        (5, PlayerGender::Brendan, false) => (Facing::Right, 3, false),
        (2, PlayerGender::May, false) => (Facing::Left, 3, false),
        (3, PlayerGender::May, false) => (Facing::Left, 2, false),
        (4, PlayerGender::May, false) => (Facing::Left, 5, false),
        (5, PlayerGender::May, false) => (Facing::Left, 4, false),
        (2, PlayerGender::Brendan, true) => (Facing::Left, 4, true),
        (3, PlayerGender::Brendan, true) => (Facing::Left, 5, true),
        (4, PlayerGender::Brendan, true) => (Facing::Left, 2, true),
        (5, PlayerGender::Brendan, true) => (Facing::Left, 3, true),
        (2, PlayerGender::May, true) => (Facing::Right, 3, true),
        (3, PlayerGender::May, true) => (Facing::Right, 2, true),
        (4, PlayerGender::May, true) => (Facing::Right, 5, true),
        (5, PlayerGender::May, true) => (Facing::Right, 4, true),
        _ => unreachable!("Running Shoes trigger must be source-authored"),
    }
}

fn running_shoes_dialogue_page(stage: u8, page: u8, player_name: &str) -> Option<String> {
    let text = match (stage, page) {
        (2, 0) => format!("MOM: {player_name}! {player_name}! Did you\nintroduce yourself to PROF. BIRCH?"),
        (2, 1) => "Oh! What an adorable POKéMON!\nYou got it from PROF. BIRCH. How nice!".to_owned(),
        (2, 2) => "You're your father's child, all right.\nYou look good together with POKéMON!".to_owned(),
        (2, 3) => "Here, honey! If you're going out on an\nadventure, wear these RUNNING SHOES.".to_owned(),
        (2, 4) => "They'll put a zip in your step!".to_owned(),
        (3, 0) => format!("{player_name} switched shoes with the\nRUNNING SHOES."),
        (4, 0) => format!("MOM: {player_name}, those shoes came with\ninstructions."),
        (4, 1) => "“Press the B Button while wearing these\nRUNNING SHOES to run extra-fast!”".to_owned(),
        (4, 2) => "“Slip on these RUNNING SHOES and race\nin the great outdoors!”".to_owned(),
        (5, 0) => "… … … … … … … …\n… … … … … … … …".to_owned(),
        (5, 1) => "To think that you have your very own\nPOKéMON now…".to_owned(),
        (5, 2) => "Your father will be overjoyed.".to_owned(),
        (5, 3) => "…But please be careful.".to_owned(),
        (5, 4) => "If anything happens, you can come home.".to_owned(),
        (5, 5) => "Go on, go get them, honey!".to_owned(),
        _ => return None,
    };
    Some(text)
}

/// Emerald delays the first glyph in a field message box, then prints one
/// glyph each frame. Input samples use 16-frame windows, so round the source
/// printer's ready boundary up to its next observable request boundary.
fn dialogue_printer_duration(dialogue: &str) -> u16 {
    let glyph_frames = dialogue.chars().count().min(usize::from(u16::MAX)) as u16;
    let raw = glyph_frames.saturating_add(12);
    raw.saturating_add(15) / 16 * 16
}

const TV_BROADCAST_PAGE_COUNT: u8 = 8;
const RIVAL_MOM_PAGE_COUNT: u8 = 6;

fn tv_broadcast_page(page: u8, player_name: &str) -> String {
    match page {
        0 => format!("MOM: Oh! {player_name}, {player_name}!\nQuick! Come quickly!"),
        1 => "MOM: Look! It's PETALBURG GYM!\nMaybe DAD will be on!".to_owned(),
        2 => "INTERVIEWER: We brought you this\nreport from in front of PETALBURG GYM.".to_owned(),
        3 => "MOM: Oh... It's over.".to_owned(),
        4 => "I think DAD was on, but we missed him.\nToo bad.".to_owned(),
        5 => "Oh, yes.\nOne of DAD's friends lives in town.".to_owned(),
        6 => "PROF. BIRCH is his name.".to_owned(),
        7 => "He lives right next door, so you should\ngo over and introduce yourself.".to_owned(),
        _ => unreachable!("TV broadcast page must be in range"),
    }
}

fn rival_mom_page(page: u8, player_gender: PlayerGender, player_name: &str) -> String {
    let child = match player_gender {
        PlayerGender::Brendan => "daughter",
        PlayerGender::May => "son",
    };
    match page {
        0 => "Oh, hello. And you are?".to_owned(),
        1 => "… … … … … … … … …\n… … … … … … … … …".to_owned(),
        2 => format!("Oh, you're {player_name}, our new next-door\nneighbor! Hi!"),
        3 => format!("We have a {child} about the same\nage as you."),
        4 => format!("Our {child} was excited about making\na new friend."),
        5 => format!("Our {child} is upstairs, I think."),
        _ => unreachable!("rival Mom page must be in range"),
    }
}

fn pokedex_handoff_page(page: u8, player_gender: PlayerGender, player_name: &str) -> String {
    let rival = rival_name(player_gender);
    match page {
        0 => format!(
            "PROF. BIRCH: Oh, hi, {player_name}!\n\nI heard you beat {rival} on\nyour first try. That's excellent!\n\n{rival}'s been helping with my research\nfor a long time.\n\n{rival} has an extensive history as\na TRAINER already.\n\nHere, {player_name}, I ordered this for my\nresearch, but I think you should have\nthis POKéDEX."
        ),
        1 => format!("{player_name} received the POKéDEX!"),
        2 => format!(
            "PROF. BIRCH: The POKéDEX is a high-tech\ntool that automatically makes a record\nof any POKéMON you meet or catch.\n\nMy kid, {rival}, goes everywhere\nwith it.\n\nWhenever my kid catches a rare POKéMON\nand records its data in the POKéDEX,\nwhy, {rival} looks for me while I'm out\ndoing fieldwork, and shows me."
        ),
        3 => match player_gender {
            PlayerGender::Brendan => format!(
                "MAY: Oh, wow, {player_name}!\nYou got a POKéDEX, too!\n\nThat's great! Just like me!\nI've got something for you, too!"
            ),
            PlayerGender::May => "BRENDAN: Huh…\nSo you got a POKéDEX, too.\n\nWell then, here.\nI'll give you these.".to_owned(),
        },
        4 => match player_gender {
            PlayerGender::Brendan => "MAY: It's fun if you can get a lot of\nPOKéMON!\n\nI'm going to look all over the place\nbecause I want different POKéMON.\n\nIf I find any cute POKéMON, I'll catch\nthem with POKé BALLS!".to_owned(),
            PlayerGender::May => "BRENDAN: You know it's more fun to\nhave a whole bunch of POKéMON.\n\nI'm going to explore all over the place\nto find different POKéMON.\n\nIf I find any cool POKéMON, you bet\nI'll try to get them with POKé BALLS.".to_owned(),
        },
        _ => unreachable!("Pokédex handoff page must be in range"),
    }
}

fn birch_rescue_after_battle_page(page: u8, player_name: &str) -> String {
    match page {
        0 => "PROF. BIRCH: Whew…".to_owned(),
        1 => "I was in the tall grass studying wild\nPOKéMON when I was jumped.".to_owned(),
        2 => "You saved me.\nThanks a lot!".to_owned(),
        3 => "Oh?".to_owned(),
        4 => format!("Hi, you're {player_name}!"),
        5 => "This is not the place to chat, so come\nby my POKéMON LAB later, okay?".to_owned(),
        _ => unreachable!("Birch rescue page must be in range"),
    }
}

fn map_npcs(map: MapId, phase: StoryPhase, potions: u8, oldale_rival_departed: bool, player_gender: PlayerGender) -> Vec<NpcState> {
    match map {
        MapId::LittlerootTown => littleroot_town_npcs(phase, player_gender),
        MapId::Route101 => route101_npcs(phase),
        MapId::OldaleTown => oldale_town_npcs(phase, potions, oldale_rival_departed),
        MapId::Route103 => route103_npcs(phase),
        // The 1F map transition scripts reposition Mom for each opening
        // beat: door through the move-in/clock-set state, then the TV seat
        // for the Petalburg report. The source does not move Mom away from
        // the door when `EnterHouseMovingIn` releases control.
        MapId::BrendansHouse1F => vec![NpcState {
            id: "mom".to_owned(), map,
            position: match phase {
                StoryPhase::NewHome | StoryPhase::ClockSet => TilePosition { x: 9, y: 8 },
                StoryPhase::TvBroadcast | StoryPhase::MeetRival => TilePosition { x: 4, y: 5 },
                _ => TilePosition { x: 8, y: 4 },
            },
            facing: Facing::Up,
        }],
        // During clock setup the upstairs rival object is hidden in the
        // reference, leaving the clock-room/stair path unobstructed. Mom's
        // temporary ClockVisit object is removed before the TV handoff.
        MapId::BrendansHouse2F | MapId::MaysHouse2F
            if matches!(phase, StoryPhase::ClockSet | StoryPhase::TvBroadcast | StoryPhase::MeetRival) => Vec::new(),
        MapId::BrendansHouse2F if phase == StoryPhase::ClockVisit => vec![NpcState {
            id: "mom".to_owned(), map, position: TilePosition { x: 7, y: 1 }, facing: Facing::Down,
        }],
        MapId::MaysHouse1F => vec![NpcState {
            id: "mom".to_owned(), map,
            position: match phase {
                StoryPhase::NewHome | StoryPhase::ClockSet => TilePosition { x: 1, y: 8 },
                StoryPhase::TvBroadcast | StoryPhase::MeetRival => TilePosition { x: 6, y: 5 },
                _ => TilePosition { x: 2, y: 4 },
            },
            facing: Facing::Up,
        }],
        MapId::MaysHouse2F if phase == StoryPhase::ClockVisit => vec![NpcState {
            id: "mom".to_owned(), map, position: TilePosition { x: 1, y: 1 }, facing: Facing::Down,
        }],
        MapId::BrendansHouse2F => vec![NpcState {
            id: "mom".to_owned(), map, position: TilePosition { x: 7, y: 1 }, facing: Facing::Down,
        }],
        MapId::MaysHouse2F => vec![NpcState {
            id: "rival".to_owned(), map, position: TilePosition { x: 4, y: 3 }, facing: Facing::Down,
        }],
        MapId::ProfessorBirchsLab => {
            let mut npcs = vec![NpcState {
                id: "aide".to_owned(), map,
                position: TilePosition { x: 9, y: 8 }, facing: Facing::Down,
            }];
            // Route101_EventScript_BirchsBag clears Birch's Lab hide flag
            // only after the rescue/battle sequence.
            if phase >= StoryPhase::BirchRescued {
                npcs.push(NpcState {
                    id: "birch".to_owned(), map,
                    position: TilePosition { x: 6, y: 4 }, facing: Facing::Down,
                });
            }
            // Route103_EventScript_RivalEnd clears the Lab rival flag once
            // the Route 103 departure choreography is complete.
            if phase >= StoryPhase::RivalDefeated {
                npcs.push(NpcState {
                    id: "rival".to_owned(), map,
                    position: TilePosition { x: 7, y: 4 }, facing: Facing::Down,
                });
            }
            npcs
        }
        MapId::TitleScreen | MapId::ProfessorIntro | MapId::MovingTruck => Vec::new(),
    }
}

fn route101_npcs(phase: StoryPhase) -> Vec<NpcState> {
    let mut npcs = vec![NpcState {
        id: "youngster".to_owned(), map: MapId::Route101,
        position: TilePosition { x: 16, y: 8 }, facing: Facing::Down,
    }];
    if matches!(
        phase,
        StoryPhase::BirchRescue
            | StoryPhase::StarterSelect
            | StoryPhase::StarterReveal
            | StoryPhase::BirchBattle
            | StoryPhase::BirchRescued
    ) {
        npcs.push(NpcState {
            id: "birch".to_owned(), map: MapId::Route101,
            position: TilePosition { x: 9, y: 13 }, facing: Facing::Right,
        });
    }
    if phase == StoryPhase::BirchRescue {
        // Route101's map event keeps Birch's Bag at (7,14) until
        // `Route101_EventScript_BirchsBag` completes its post-battle flag
        // sequence. It is a colliding field object, not starter-choice UI.
        npcs.push(NpcState {
            id: "birchs_bag".to_owned(), map: MapId::Route101,
            position: TilePosition { x: 7, y: 14 }, facing: Facing::Down,
        });
        npcs.push(NpcState {
            id: "zigzagoon".to_owned(), map: MapId::Route101,
            position: TilePosition { x: 10, y: 13 }, facing: Facing::Left,
        });
    }
    // Birch's GoSeeRival script clears FLAG_HIDE_ROUTE_101_BOY only after
    // the starter acknowledgement completes in the Lab.
    if phase >= StoryPhase::StarterChosen {
        npcs.push(NpcState {
            id: "route101_boy".to_owned(), map: MapId::Route101,
            position: TilePosition { x: 2, y: 13 }, facing: Facing::Down,
        });
    }
    npcs
}

fn oldale_town_npcs(phase: StoryPhase, potions: u8, oldale_rival_departed: bool) -> Vec<NpcState> {
    let mut npcs = vec![
        NpcState {
            id: "oldale_girl".to_owned(), map: MapId::OldaleTown,
            position: TilePosition { x: 16, y: 11 }, facing: Facing::Left,
        },
        NpcState {
            id: "mart_employee".to_owned(), map: MapId::OldaleTown,
            // OldaleTown_OnTransition moves the employee down the street
            // until the introductory Potion event is completed; later map
            // loads use the map's authored default near the Mart entrance.
            position: if potions == 0 {
                TilePosition { x: 13, y: 14 }
            } else {
                TilePosition { x: 13, y: 7 }
            },
            facing: Facing::Down,
        },
        NpcState {
            id: "footprints_man".to_owned(), map: MapId::OldaleTown,
            // OldaleTown_OnTransition moves this object to the west entrance
            // until Birch's Pokédex/Poké Ball script sets
            // FLAG_ADVENTURE_STARTED / VAR_OLDALE_TOWN_STATE.
            position: if phase >= StoryPhase::PokedexReceived {
                TilePosition { x: 8, y: 9 }
            } else {
                TilePosition { x: 1, y: 11 }
            },
            facing: if phase >= StoryPhase::PokedexReceived {
                Facing::Right
            } else {
                Facing::Left
            },
        },
    ];
    if phase == StoryPhase::RivalDefeated && !oldale_rival_departed {
        npcs.push(NpcState {
            id: "oldale_rival".to_owned(), map: MapId::OldaleTown,
            position: TilePosition { x: 11, y: 19 }, facing: Facing::Up,
        });
    }
    npcs
}

fn route103_npcs(phase: StoryPhase) -> Vec<NpcState> {
    if phase == StoryPhase::StarterChosen {
        vec![NpcState {
            id: "rival".to_owned(), map: MapId::Route103,
            position: TilePosition { x: 10, y: 3 }, facing: Facing::Right,
        }]
    } else {
        Vec::new()
    }
}

/// Source object-event home tiles and wander ranges for every movement type
/// currently represented by the deterministic ambient-motion model.
fn npc_wander_bounds(map: MapId, id: &str) -> Option<(TilePosition, i16, i16)> {
    match (map, id) {
        (MapId::LittlerootTown, "twin") => Some((TilePosition { x: 16, y: 10 }, 1, 2)),
        (MapId::LittlerootTown, "fat_man") => Some((TilePosition { x: 12, y: 13 }, 2, 1)),
        (MapId::LittlerootTown, "boy") => Some((TilePosition { x: 14, y: 17 }, 2, 1)),
        // Route101's Boy uses MOVEMENT_TYPE_WANDER_LEFT_AND_RIGHT with the
        // authored one-tile range in both axes; movement itself is limited
        // to the source's left/right direction pair above.
        (MapId::Route101, "route101_boy") => Some((TilePosition { x: 2, y: 13 }, 1, 1)),
        // The Lab's aide is authored as `MOVEMENT_TYPE_WANDER_AROUND` with
        // one-tile X/Y ranges around `(9, 8)`.  Keeping this local to the
        // Lab lets the source object-event scheduler animate the
        // post-Route-101 acknowledgement scene instead of freezing the aide
        // in their initial south-facing pose.
        (MapId::ProfessorBirchsLab, "aide") => Some((TilePosition { x: 9, y: 8 }, 1, 1)),
        // The staged Route 101 youngster and Oldale man are fixed-facing
        // source objects, so they intentionally have no ambient range.
        _ => None,
    }
}

/// `gStandardDirections` is South, North, West, East. Route 101's Boy uses
/// the source's restricted `gLeftAndRightDirections` pair instead.
fn ambient_wander_direction(id: &str, random: u16) -> Facing {
    if id == "route101_boy" {
        return if random & 1 == 0 { Facing::Left } else { Facing::Right };
    }
    match random & 3 {
        0 => Facing::Down,
        1 => Facing::Up,
        2 => Facing::Left,
        _ => Facing::Right,
    }
}

fn littleroot_town_npcs(phase: StoryPhase, player_gender: PlayerGender) -> Vec<NpcState> {
    let (twin_position, twin_facing) = if phase >= StoryPhase::BirchRescued {
        (TilePosition { x: 16, y: 10 }, Facing::Down)
    } else if phase < StoryPhase::MetRival {
        (TilePosition { x: 7, y: 2 }, Facing::Down)
    } else {
        (TilePosition { x: 10, y: 1 }, Facing::Up)
    };
    let mut npcs = vec![
        NpcState { id: "twin".to_owned(), map: MapId::LittlerootTown, position: twin_position, facing: twin_facing },
        NpcState { id: "boy".to_owned(), map: MapId::LittlerootTown, position: TilePosition { x: 14, y: 17 }, facing: Facing::Down },
    ];
    // The truck's on-frame arrival script clears this hide flag only once
    // Mom and the player have entered their new house.
    if phase >= StoryPhase::NewHome {
        npcs.push(NpcState { id: "fat_man".to_owned(), map: MapId::LittlerootTown, position: TilePosition { x: 12, y: 13 }, facing: Facing::Down });
    }
    // Birch's completed Lab handoff sets town state 3; on the following town
    // transition Mom waits at the selected player's front door.
    if phase >= StoryPhase::PokedexReceived {
        let position = match player_gender {
            PlayerGender::Brendan => TilePosition { x: 5, y: 9 },
            PlayerGender::May => TilePosition { x: 14, y: 9 },
        };
        npcs.push(NpcState { id: "mom_outside".to_owned(), map: MapId::LittlerootTown, position, facing: Facing::Down });
    }
    npcs
}

/// Source `ApproachPlayer*` movement streams for the counterpart-rival
/// bedroom scene. The boolean marks each compact `walk_in_place_faster_*`
/// action; all other commands are 16-frame tile walks.
fn bedroom_rival_approach(map: MapId, player_facing: Facing) -> (&'static [(Facing, bool)], Facing) {
    const B_NORTH: &[(Facing, bool)] = &[(Facing::Left, false), (Facing::Left, false), (Facing::Down, false), (Facing::Down, false), (Facing::Left, false)];
    const B_SOUTH: &[(Facing, bool)] = &[(Facing::Left, false), (Facing::Left, false), (Facing::Left, false)];
    const B_WEST: &[(Facing, bool)] = &[(Facing::Left, false), (Facing::Left, false), (Facing::Down, false), (Facing::Left, true)];
    const B_EAST: &[(Facing, bool)] = &[(Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Down, true)];
    const M_NORTH: &[(Facing, bool)] = &[(Facing::Right, false), (Facing::Right, false), (Facing::Down, false), (Facing::Down, false), (Facing::Right, false)];
    const M_SOUTH: &[(Facing, bool)] = &[(Facing::Right, false), (Facing::Right, false), (Facing::Right, false)];
    const M_WEST: &[(Facing, bool)] = &[(Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Down, true)];
    const M_EAST: &[(Facing, bool)] = &[(Facing::Right, false), (Facing::Right, false), (Facing::Down, false), (Facing::Right, true)];
    match (map, player_facing) {
        (MapId::BrendansHouse2F, Facing::Up) => (B_NORTH, Facing::Right),
        (MapId::BrendansHouse2F, Facing::Down) => (B_SOUTH, Facing::Right),
        (MapId::BrendansHouse2F, Facing::Left) => (B_WEST, Facing::Right),
        (MapId::BrendansHouse2F, Facing::Right) => (B_EAST, Facing::Right),
        (MapId::MaysHouse2F, Facing::Up) => (M_NORTH, Facing::Left),
        (MapId::MaysHouse2F, Facing::Down) => (M_SOUTH, Facing::Left),
        (MapId::MaysHouse2F, Facing::Left) => (M_WEST, Facing::Up),
        (MapId::MaysHouse2F, Facing::Right) => (M_EAST, Facing::Left),
        _ => unreachable!("only counterpart bedrooms have rival approach scripts"),
    }
}

/// Source `WalkToPC*` streams selected by the unique end tile of the prior
/// approach path. Some contain an intermediate faster turn; each ends in an
/// in-place facing change.
fn bedroom_rival_pc_route(map: MapId, position: &TilePosition) -> (&'static [(Facing, bool)], Facing) {
    const B_NORTH: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Up, false), (Facing::Up, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Up, true)];
    const B_SOUTH: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Up, true)];
    const B_WEST: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Up, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Up, true)];
    const B_EAST: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Left, false), (Facing::Left, false), (Facing::Up, true)];
    const M_NORTH: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Up, false), (Facing::Up, false), (Facing::Right, true), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Up, true)];
    const M_SOUTH: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Right, true), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Up, true)];
    const M_WEST: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Right, false), (Facing::Right, false), (Facing::Up, true)];
    const M_EAST: &[(Facing, bool)] = &[(Facing::Up, false), (Facing::Up, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Right, false), (Facing::Up, true)];
    match (map, position.x, position.y) {
        (MapId::BrendansHouse2F, 4, 5) => (B_NORTH, Facing::Left),
        (MapId::BrendansHouse2F, 4, 3) => (B_SOUTH, Facing::Left),
        (MapId::BrendansHouse2F, 5, 4) => (B_WEST, Facing::Left),
        (MapId::BrendansHouse2F, 2, 3) => (B_EAST, Facing::Right),
        (MapId::MaysHouse2F, 4, 5) => (M_NORTH, Facing::Right),
        (MapId::MaysHouse2F, 4, 3) => (M_SOUTH, Facing::Right),
        (MapId::MaysHouse2F, 6, 3) => (M_WEST, Facing::Up),
        (MapId::MaysHouse2F, 3, 4) => (M_EAST, Facing::Right),
        _ => unreachable!("rival PC route requires an authored approach endpoint"),
    }
}

const LITTLEROOT_GO_SAVE_BIRCH_FASTER_TURN_FRAMES: u16 = 4;
const LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES: u16 =
    LITTLEROOT_GO_SAVE_BIRCH_FASTER_TURN_FRAMES * 2;

fn no_pokemon_twin_path(right_trigger: bool, returning: bool) -> &'static [(Facing, bool)] {
    const APPROACH_LEFT: &[(Facing, bool)] = &[(Facing::Right, true), (Facing::Right, true), (Facing::Right, true), (Facing::Right, true), (Facing::Up, true), (Facing::Up, true), (Facing::Left, true)];
    const APPROACH_RIGHT: &[(Facing, bool)] = &[(Facing::Right, true), (Facing::Right, true), (Facing::Right, true), (Facing::Up, true), (Facing::Up, true), (Facing::Right, true)];
    const RETURN_LEFT: &[(Facing, bool)] = &[(Facing::Right, false), (Facing::Down, false), (Facing::Down, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Up, false), (Facing::Down, true)];
    const RETURN_RIGHT: &[(Facing, bool)] = &[(Facing::Left, false), (Facing::Down, false), (Facing::Left, false), (Facing::Left, false), (Facing::Left, false), (Facing::Down, true)];
    match (right_trigger, returning) {
        (false, false) => APPROACH_LEFT,
        (true, false) => APPROACH_RIGHT,
        (false, true) => RETURN_LEFT,
        (true, true) => RETURN_RIGHT,
    }
}

/// The `TwinReturn*` streams end with `walk_in_place_faster_down`, unlike
/// their preceding ordinary tile walks. Its four-frame action changes only
/// the Twin's facing; source `walk_fast_*` approach actions remain eight.
fn no_pokemon_twin_path_step_frames(terminal_faster_turn: bool, fast: bool) -> u16 {
    if terminal_faster_turn {
        4
    } else if fast {
        8
    } else {
        16
    }
}

fn no_pokemon_twin_path_frames(right_trigger: bool, returning: bool) -> u16 {
    let path = no_pokemon_twin_path(right_trigger, returning);
    path.iter().enumerate()
        .map(|(index, (_, fast))| {
            no_pokemon_twin_path_step_frames(returning && index + 1 == path.len(), *fast)
        })
        .sum()
}

fn stepped_position(position: &TilePosition, direction: Facing) -> TilePosition {
    match direction {
        Facing::Up => TilePosition { x: position.x, y: position.y - 1 },
        Facing::Down => TilePosition { x: position.x, y: position.y + 1 },
        Facing::Left => TilePosition { x: position.x - 1, y: position.y },
        Facing::Right => TilePosition { x: position.x + 1, y: position.y },
    }
}

fn ledge_allows(behavior: u8, facing: Facing) -> bool {
    match behavior {
        56 => facing == Facing::Right,
        57 => facing == Facing::Left,
        58 => facing == Facing::Up,
        59 => facing == Facing::Down,
        60..=63 => false,
        _ => true,
    }
}
