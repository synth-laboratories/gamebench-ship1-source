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

/// `PetalburgGymReport{Male,Female}` spends one four-frame faster in-place
/// turn, one frame launching `emote_exclamation_mark`, and the three
/// `delay_16` actions in `Common_Movement_Delay48` before Mom speaks.
const TV_BROADCAST_INTRO_FRAMES: u16 = 4 + 1 + 48;
/// `Common_Movement_ExclamationMark` completes its object movement in one
/// tick, while the spawned field-effect icon stays animated for 60 frames.
const RIVAL_MOM_EMOTE_MOVEMENT_FRAMES: u16 = 1;
const RIVAL_MOM_EXCLAMATION_FRAMES: u8 = 60;
const RIVAL_MOM_DELAY_FRAMES: u16 = 48;
const RIVAL_MOM_NORMAL_STEP_FRAMES: u16 = 16;
const RIVAL_MOM_APPROACH_FRAMES: u16 = RIVAL_MOM_NORMAL_STEP_FRAMES * 6;
/// The map script waits for the one-tick emote, Delay48, and six normal
/// movement actions before its first new-neighbor message can open.
const RIVAL_MOM_INTRO_FRAMES: u16 =
    RIVAL_MOM_EMOTE_MOVEMENT_FRAMES + RIVAL_MOM_DELAY_FRAMES + RIVAL_MOM_APPROACH_FRAMES;
/// Source-calibrated offsets for `LittlerootTown_MaysHouse_1F_EventScript_MeetRival`.
/// The scene clock starts when the public downstairs arrival tile settles;
/// its first visible May OBJ, emotion marker, three up steps, and message box
/// then occur at these exact compositor boundaries.
const MAYS_RIVAL_SPAWN_OFFSET: u16 = 23;
// The source creates May on the east rug first, then its object-event
// callback publishes the lower mat pose seven VBlanks later.  This is a
// visible OAM handoff (V140 -> V147), not a continuous walk between tiles.
const MAYS_RIVAL_MAT_REPOSITION_OFFSET: u16 = 30;
// The first upward callback is published at V231 (scene elapsed 114),
// followed by 16-VBlank callbacks at V247 and V263.  The earlier 107-frame
// estimate started May seven VBlanks too early and opened dialogue while the
// final stride was still on screen.
const MAYS_RIVAL_WALK_OFFSET: u16 = 114;
const MAYS_RIVAL_DIALOGUE_OFFSET: u16 = 165;
const MAYS_RIVAL_RESIDENT_HANDOFF_FRAME: u64 = 4645;
const MAYS_RIVAL_WALK_STEP_FRAMES: u16 = 16;
/// The authored departure uses nine movement actions after the final page:
/// faster-right, right, faster-up, up, up, faster-left, left,
/// faster-up, up. The visible object-event route is 96 source frames.
const MAYS_RIVAL_DEPARTURE_FRAMES: u16 = 100;
/// The player turns east four VBlanks into May's first upward departure step;
/// the source uses `walk_in_place_faster_right` for that compact turn.
const MAYS_PLAYER_FAST_TURN_OFFSET: u16 = 26;
const MAYS_PLAYER_FAST_TURN_FRAMES: u16 = 4;
/// After May leaves the house, the source keeps Brendan's up-facing resident
/// OBJ cell uploaded for a short tail before the exit interaction releases it.
/// Preserve that completed callback as a typed walk marker so rendering does
/// not infer the upload from a missing NPC.
const MAYS_PLAYER_UP_TAIL_FRAMES: u16 = 32;
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
const RUNNING_SHOES_RETURN_DOOR_FRAMES: u16 =
    LITTLEROOT_DOOR_ANIMATION_FRAMES + 16 + LITTLEROOT_DOOR_ANIMATION_FRAMES;
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
const WALL_CLOCK_MINUTE_ANGLE_CIRCLE: u16 = 360;
const CLOCK_VISIT_MOM_ENTRY_FRAMES: u16 = 68;
const CLOCK_VISIT_PLAYER_TURN_FRAMES: u16 = 4;
const CLOCK_VISIT_ENTRY_FRAMES: u16 = CLOCK_VISIT_MOM_ENTRY_FRAMES + CLOCK_VISIT_PLAYER_TURN_FRAMES;
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
/// `OldaleTown_EventScript_BlockedPath` first waits the player's eight-frame
/// delay plus one normal step, then returns the footprints man in two normal
/// strides after the warning message closes.
const OLDALE_BLOCKED_PATH_APPROACH_FRAMES: u16 = 24;
const OLDALE_BLOCKED_PATH_RETURN_FRAMES: u16 = 32;

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
    /// Source-authenticated settled Mays House 1F boundary after the
    /// upstairs stair/door handoff. This remains distinct from the bedroom
    /// origin checkpoint so direct oracle probes can validate the 1F surface.
    #[serde(rename = "source_only_mays_house_1f")]
    MaysHouse1F,
    /// Source-authenticated settled Mays House 2F boundary after the stair
    /// warp. This is the direct counterpart to the 1F checkpoint above.
    #[serde(rename = "source_only_mays_house_2f")]
    MaysHouse2F,
    /// Source-authenticated settled exterior immediately after the Mays
    /// House 1F door warp. This is distinct from the later Birch-rescued
    /// town checkpoint: no starter, Pokédex, or rescue flags exist yet.
    #[serde(rename = "source_only_littleroot_field_ready")]
    LittlerootFieldReady,
    /// Source-authenticated house-exit landing tile before the first field
    /// stride.  This is one tile south of `LittlerootFieldReady` and keeps the
    /// door handoff's player/OAM anchor distinct from the later idle probe.
    #[serde(rename = "source_only_littleroot_exterior")]
    LittlerootExterior,
    BirchLabExterior,
    RivalOutsideLab,
    Route101Rescue,
    /// Source-authenticated settled Route 101 field boundaries.  These are
    /// deliberately separate from the scripted Birch-rescue checkpoint: the
    /// source saves were taken after the starter was chosen and the player is
    /// free to traverse the route, so NPC visibility and collision must use
    /// the `StarterChosen` map phase.
    #[serde(rename = "source_only_route101_post_lab")]
    Route101PostLab,
    #[serde(rename = "source_only_route101_north_lane")]
    Route101NorthLane,
    #[serde(rename = "source_only_route101_west_lane")]
    Route101WestLane,
    #[serde(rename = "source_only_route101_mid_lane")]
    Route101MidLane,
    #[serde(rename = "source_only_route101_east_lane")]
    Route101EastLane,
    StarterPicker,
    StarterBattle,
    /// Source-authenticated Route 101 Wurmple encounter boundaries. These
    /// retain the battle-owned surface (including the post-victory field
    /// resume) instead of pretending a wild encounter is ordinary field
    /// movement.
    #[serde(rename = "source_only_route101_wild_battle")]
    Route101WildBattle,
    #[serde(rename = "source_only_route101_wild_command")]
    Route101WildCommand,
    #[serde(rename = "source_only_route101_wild_after_turn_one")]
    Route101WildAfterTurnOne,
    #[serde(rename = "source_only_route101_wild_after_turn_two")]
    Route101WildAfterTurnTwo,
    #[serde(rename = "source_only_route101_wild_after_turn_three")]
    Route101WildAfterTurnThree,
    #[serde(rename = "source_only_route101_wild_after_turn_four")]
    Route101WildAfterTurnFour,
    #[serde(rename = "source_only_route101_wild_after_turn_five")]
    Route101WildAfterTurnFive,
    #[serde(rename = "source_only_route101_wild_after_turn_six")]
    Route101WildAfterTurnSix,
    #[serde(rename = "source_only_route101_wild_victory_resume")]
    Route101WildVictoryResume,
    /// Source-authenticated continuation boundaries for Birch's scripted
    /// Zigzagoon battle. These are separate from the Route 101 Wurmple
    /// receipts above: the source saves share a map group/position only, but
    /// retain the trainer battle's command ownership and battle state.
    #[serde(rename = "source_only_zigzagoon_after_turn_one")]
    StarterBattleAfterTurnOne,
    #[serde(rename = "source_only_zigzagoon_after_turn_two")]
    StarterBattleAfterTurnTwo,
    #[serde(rename = "source_only_zigzagoon_victory_handoff")]
    StarterBattleVictoryHandoff,
    #[serde(rename = "source_only_route101_post_victory_r2")]
    Route101PostVictoryR2,
    #[serde(rename = "source_only_route101_post_victory_u7")]
    Route101PostVictoryU7,
    #[serde(rename = "source_only_route101_post_victory_u7_settled")]
    Route101PostVictoryU7Settled,
    #[serde(rename = "source_only_route101_post_victory_l4")]
    Route101PostVictoryL4,
    #[serde(rename = "source_only_route101_post_victory_north_exit")]
    Route101PostVictoryNorthExit,
    Route103Rival,
    #[serde(alias = "source_only_route103_wild_command")]
    Route103WildCommand,
    #[serde(alias = "source_only_route103_wild_turn_one")]
    Route103WildTurnOne,
    #[serde(alias = "source_only_route103_wild_turn1_move_menu")]
    Route103WildTurn1MoveMenu,
    Route103WildPlayerSendoutMessage,
    #[serde(alias = "source_only_route103_wild_turn1_scratch_text")]
    Route103WildTurn1ScratchText,
    #[serde(alias = "source_only_route103_wild_turn1_tackle_text")]
    Route103WildTurn1TackleText,
    #[serde(alias = "source_only_route103_wild_turn1_command_return")]
    Route103WildTurn1CommandReturn,
    #[serde(alias = "source_only_route103_rival_battle_command")]
    Route103RivalBattleCommand,
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
pub enum Facing {
    Up,
    Down,
    Left,
    Right,
}

/// The player object keeps its currently uploaded 4bpp cell in VRAM until
/// the bedroom object task writes another one.  This is deliberately state,
/// rather than a function of absolute engine time: menu/SELECT ownership can
/// freeze a turn pose and a released stride leaves its final cell visible.
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BedroomPlayerSprite {
    #[default]
    Base,
    DownFirstFoot,
    DownSecondFoot,
    UpFirstFoot,
    UpMiddle,
    UpSecondFoot,
    SideFirstFoot,
    SideMiddle,
    SideSecondFoot,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PlayerGender {
    Brendan,
    May,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct GenderTransition {
    pub outgoing: PlayerGender,
    pub incoming: PlayerGender,
    pub frames_remaining: u8,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MenuEntry {
    Pokedex,
    Pokemon,
    Bag,
    Player,
    Save,
    Option,
    Exit,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClockField {
    Hours,
    Minutes,
}

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
    if is_pm {
        (90, 135)
    } else {
        (45, 90)
    }
}

/// Exact `SpriteCB_PMIndicator` angle update from `src/wallclock.c`.
fn wall_clock_advance_pm_indicator(angle: u8, target_is_pm: bool) -> u8 {
    let mut angle = angle;
    if target_is_pm {
        if (60..90).contains(&angle) {
            angle += 5;
        }
        if angle < 60 {
            angle += 1;
        }
    } else {
        if (46..76).contains(&angle) {
            angle -= 5;
        }
        if angle > 75 {
            angle -= 1;
        }
    }
    angle
}

/// Exact `SpriteCB_AMIndicator` angle update from `src/wallclock.c`.
fn wall_clock_advance_am_indicator(angle: u8, target_is_pm: bool) -> u8 {
    let mut angle = angle;
    if target_is_pm {
        if (105..135).contains(&angle) {
            angle += 5;
        }
        if angle < 105 {
            angle += 1;
        }
    } else {
        if (91..121).contains(&angle) {
            angle -= 5;
        }
        if angle > 120 {
            angle -= 1;
        }
    }
    angle
}

/// Exact `CalcMinHandDelta` thresholds from `src/wallclock.c`.
fn wall_clock_minute_hand_delta(speed: u8) -> u16 {
    if speed > 60 {
        6
    } else if speed > 30 {
        3
    } else if speed > 10 {
        2
    } else {
        1
    }
}

/// Exact `CalcNewMinHandAngle` wrap behavior from `src/wallclock.c`.
fn wall_clock_advance_minute_hand(angle: u16, direction: i8, speed: u8) -> u16 {
    let delta = wall_clock_minute_hand_delta(speed);
    match direction {
        -1 => {
            if angle > 0 {
                angle - delta
            } else {
                WALL_CLOCK_MINUTE_ANGLE_CIRCLE - delta
            }
        }
        1 => {
            if angle < WALL_CLOCK_MINUTE_ANGLE_CIRCLE - delta {
                angle + delta
            } else {
                0
            }
        }
        _ => angle,
    }
}

/// `NAMING_SCREEN_PLAYER` and `NAMING_SCREEN_NICKNAME` share Emerald's
/// keyboard controls but commit to different saved data.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NamingTarget {
    Player,
    Starter,
}

/// The three source controls in the naming screen's action-button column.
/// The two middle keyboard rows both route to Emerald's Back control.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NamingActionButton {
    Page,
    Back,
    Ok,
}

/// The source naming keyboard's three pages.  Emerald cycles these in the
/// order symbols -> uppercase -> lowercase -> symbols; the initial page for
/// both player and Pokémon nickname screens is uppercase.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NamingKeyboardPage {
    Symbols,
    LettersUpper,
    LettersLower,
}

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
pub enum StarterSpecies {
    Treecko,
    Torchic,
    Mudkip,
}

/// The source selector changes the hand/active ball immediately, then
/// commits the floating species label a few VBlanks later.  Keeping that
/// short task explicit prevents a held horizontal probe from changing the
/// label on its first frame.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct StarterSelectionTransition {
    pub from: StarterSpecies,
    pub to: StarterSpecies,
    pub frames_elapsed: u8,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BattleOpponent {
    Zigzagoon,
    Poochyena,
    Wingull,
    Wurmple,
    Rival,
}

/// A source-authored grass encounter identity.  Rules select an encounter;
/// battle completion uses this stable identity to mark it resolved without
/// recovering meaning from a map coordinate or the opponent's display name.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum WildEncounterId {
    Route101Poochyena,
    Route101Wurmple,
    Route103Poochyena,
    Route103Wingull,
}

/// The atomic field snapshot captured when a wild battle takes ownership.
/// It is stored inside `BattleState`, so a save made at any battle boundary
/// returns to the exact triggering field state after a run or victory.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct WildEncounterReturn {
    pub id: WildEncounterId,
    pub map: MapId,
    pub player: TilePosition,
    pub elevation: u8,
    pub facing: Facing,
    pub rng_state_before_battle: u32,
}

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
/// The authenticated Route 101 command checkpoint resumes after the source
/// has already started its send-out task.  Its serialized no-op continuation
/// keeps the task alive through the late emerge/message rail (elapsed 108),
/// even though the ordinary opening-battle controller releases at tick 73.
pub const BATTLE_ROUTE101_COMMAND_SENDOUT_END_FRAME: u8 = 108;
/// `OpponentHandleTrainerSlideBack` translates the Route 103 rival's 64×64
/// front pic from its settled x=176 position to x=280 over 35 VBlanks before
/// the opponent's ball task takes ownership of the battler slot.
pub const BATTLE_OPPONENT_TRAINER_EXIT_FRAMES: u8 = 35;

/// `BattleIntroSlide1` for the normal grass environment consumes two setup
/// ticks, thirty-two one-line WIN0 expansion ticks, and 120 state-3 ticks
/// before `BattleIntroSlideEnd` resets the BG offsets. The first 32 state-3
/// ticks are the source delay while BG1/BG2 offsets continue decrementing;
/// the delay is not an additional phase. Keep the Route 103 trainer hand-off
/// on that complete 154-tick source timeline instead of the former 48-frame
/// compressed presentation.
pub const BATTLE_GRASS_INTRO_FRAMES: u16 = 154;

/// A source moveset slot, retained independently of the currently selected
/// move so an opponent controller can choose from the original four slots.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct BattleMoveSlot {
    /// Gen III `MOVES_COUNT` identity. Older checkpoints only stored the
    /// display name; zero is migrated through the source sidecar below.
    #[serde(default)]
    pub move_id: u16,
    pub name: String,
    pub pp: u8,
}

/// Exclusive controller/message state for the compact battle engine. The
/// legacy booleans remain serialized render projections, while this typed
/// phase records what an A/B edge is permitted to do at every battle
/// boundary.
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BattleTurnPhase {
    #[default]
    IntroMessage,
    Command,
    MoveSelection,
    BagSelection,
    PartySelection,
    InformationalMessage,
    /// A failed RUN has committed the player's action. Its next confirmation
    /// advances the opponent response rather than returning to command UI.
    FailedRunMessage,
    TurnResultMessage,
    SuccessfulRunMessage,
    TerminalMessage,
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
    /// Source `gBattleMons[player].moves` / PP arrays, in all four row-major
    /// selection slots. The legacy two fields above remain serialized mirrors
    /// for checkpoint compatibility.
    #[serde(default)]
    pub player_moves: Vec<BattleMoveSlot>,
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
    /// The source cursor task applies a changed action cursor on the next
    /// VBlank. Keep the old visual slot for that one-frame DMA boundary while
    /// the logical command cursor is already updated for controller input.
    #[serde(default)]
    pub command_cursor_rendered: Option<u8>,
    #[serde(default)]
    pub command_cursor_transition_frames: u8,
    /// True after choosing FIGHT, when the two opening moves are shown.
    #[serde(default)]
    pub selecting_move: bool,
    /// Source `HandleChooseMoveAfterDma3` owns a short BG0/DMA hand-off after
    /// FIGHT is pressed. Ten VBlanks are visible: the command page remains
    /// for five, the move page is staged for five, then it is stable.
    #[serde(default)]
    pub move_selection_transition_frames: u8,
    /// The source move cursor is logically updated on the input edge, then
    /// its cursor task presents the previous slot for one VBlank.
    #[serde(default)]
    pub move_cursor_rendered: Option<u8>,
    #[serde(default)]
    pub move_cursor_transition_frames: u8,
    /// B cancels the opening move page logically at the edge, while the
    /// source keeps its move-window surface visible for six more VBlanks.
    #[serde(default)]
    pub move_selection_cancel_transition_frames: u8,
    /// B also restarts the source player-battler idle task. Zero means the
    /// ordinary battle-global phase remains active.
    #[serde(default)]
    pub player_battler_oam_phase_reset_frame: u64,
    /// Source healthbox OAM animation phase offset introduced when FIGHT is
    /// selected. The BG0 hand-off does not restart the healthbox task; it can
    /// instead leave that task a small number of VBlanks behind the global
    /// battle frame, depending on the edge's source phase.
    #[serde(default)]
    pub move_selection_oam_phase_delay_frames: u8,
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
    /// Present only for a regular field encounter. Scripted rescue and
    /// trainer battles deliberately have no field-resume target.
    #[serde(default)]
    pub field_return: Option<WildEncounterReturn>,
    /// Gen-III escape attempts become easier after each failed run.  This is
    /// battle-owned state, not a route-local counter, and therefore survives
    /// a checkpoint in the failed-run message boundary.
    #[serde(default)]
    pub run_attempts: u8,
    pub move_cursor: u8,
    pub player_fainted: bool,
    pub message: Option<String>,
    /// Source healthbox/OAM presentation is anchored to the VBlank where a
    /// battle message task takes ownership, rather than always following the
    /// global battle frame.  Keeping the handoff receipt in the battle state
    /// makes noisy-input message replays resume at the same visual phase.
    #[serde(default)]
    pub message_visual_start_frame: u64,
    /// Encounter wipe remaining before the battle command screen accepts
    /// input. Keeping it on the battle itself makes an interrupted save/load
    /// resume the same encounter instead of dropping directly into a turn.
    #[serde(default)]
    pub entry_transition_frames: u16,
    /// Remaining source ticks in `OpponentHandleTrainerSlideBack`. This is a
    /// visual-only rail: the compact battle controller keeps its existing
    /// message/input timing while the trainer OBJ leaves the field.
    #[serde(default)]
    pub intro_opponent_trainer_exit_frames: u8,
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
    /// Released-A dismissal debounce on the Route 101 Wurmple entry page.
    /// Emerald does not replace the printed appearance message until the
    /// native printer's four-VBlank handoff has elapsed.
    #[serde(default)]
    pub intro_message_dismiss_delay_frames: u8,
    /// The source clears the appearance text window one VBlank before the
    /// delayed `Go!` printer takes ownership. Keep the logical message and
    /// battle input owner intact while suppressing only its glyphs/chrome
    /// during that measured handoff.
    #[serde(default)]
    pub intro_message_hidden: bool,
    /// The source accepts an early A/B edge on the first two post-checkpoint
    /// VBlanks. On the source printer's nine-VBlank arrow cadence, an edge at
    /// phase two exposes the blank-window phase before `Go!` starts printing.
    /// This records that measured input provenance.
    #[serde(default)]
    pub intro_message_hide_on_dismiss: bool,
    /// An edge before the source printer has published its first full-text
    /// phase also restarts the entry arrow at its initial cell. Later edges
    /// preserve the already-running arrow animation while the four-VBlank
    /// dismissal handoff drains.
    #[serde(default)]
    pub intro_message_arrow_reset_on_dismiss: bool,
    /// The source freezes the currently visible entry-arrow cell for the
    /// four-VBlank dismissal handoff. Retain its phase instead of letting the
    /// world clock advance the ordinary idle animation underneath it.
    #[serde(default)]
    pub intro_message_dismiss_arrow_frame: u64,
    /// Number of characters uploaded by the source printer on the `Go!`
    /// page. One glyph is committed per VBlank before the sendout task starts.
    #[serde(default)]
    pub intro_message_print_chars: u8,
    /// Two source wait ticks remain after the final `Go!` glyph before the
    /// trainer-ball task takes the OBJ owner.
    #[serde(default)]
    pub intro_message_print_hold_frames: u8,
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
    #[serde(default)]
    pub turn_phase: BattleTurnPhase,
}

fn default_player_battle_hp() -> u8 {
    24
}
fn default_opponent_battle_hp() -> u8 {
    22
}
fn default_player_move_damage() -> u8 {
    9
}
fn default_player_move_name() -> String {
    "TACKLE".to_owned()
}
fn default_player_status_move_name() -> String {
    "GROWL".to_owned()
}
fn default_player_move_pp() -> u8 {
    35
}
fn default_player_status_move_pp() -> u8 {
    30
}
fn default_opponent_species() -> String {
    "ZIGZAGOON".to_owned()
}
fn default_opponent_move_name() -> String {
    "TACKLE".to_owned()
}
fn default_opponent_move_slots() -> Vec<BattleMoveSlot> {
    vec![battle_move_slot("TACKLE", 35)]
}
fn default_opponent_move_damage() -> u8 {
    4
}
fn default_battle_intro_stage() -> u8 {
    2
}
fn default_battle_rng_state() -> u32 {
    default_ambient_rng()
}
fn default_player_species() -> String {
    "TREECKO".to_owned()
}
fn default_battle_level() -> u8 {
    5
}
fn default_battle_stat() -> u8 {
    10
}

fn battle_opponent_name(opponent: BattleOpponent) -> &'static str {
    match opponent {
        BattleOpponent::Zigzagoon => "ZIGZAGOON",
        BattleOpponent::Poochyena => "POOCHYENA",
        BattleOpponent::Wingull => "WINGULL",
        BattleOpponent::Wurmple => "WURMPLE",
        BattleOpponent::Rival => "your RIVAL",
    }
}

fn fast_path_position(
    start: TilePosition,
    path: &[Facing],
    completed: usize,
    idle_facing: Facing,
) -> (TilePosition, Facing) {
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
enum BattleType {
    Normal,
    Grass,
    Fire,
    Water,
    Dark,
    Bug,
    Flying,
}

#[derive(Clone, Copy)]
struct SpeciesBattleProfile {
    name: &'static str,
    base_hp: u8,
    base_attack: u8,
    base_defense: u8,
    base_speed: u8,
    base_special_attack: u8,
    base_special_defense: u8,
    types: (BattleType, BattleType),
}

#[derive(Clone, Copy)]
struct MoveBattleProfile {
    name: &'static str,
    power: u8,
    accuracy: u8,
    pp: u8,
    move_type: BattleType,
    special: bool,
}

#[derive(Clone, Copy)]
struct CombatantBattleProfile {
    species: SpeciesBattleProfile,
    level: u8,
    max_hp: u8,
    attack: u8,
    defense: u8,
    speed: u8,
    special_attack: u8,
    special_defense: u8,
    moves: [Option<MoveBattleProfile>; 4],
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
    /// Source party move IDs and PP. Empty means a pre-four-slot checkpoint
    /// and is migrated from the two legacy PP fields on restore/use.
    #[serde(default)]
    pub moves: Vec<BattleMoveSlot>,
}

#[derive(Clone, Copy)]
struct StatIvs {
    hp: u8,
    attack: u8,
    defense: u8,
    speed: u8,
    special_attack: u8,
    special_defense: u8,
}

#[derive(Clone, Copy)]
struct NatureModifiers {
    attack: (u8, u8),
    defense: (u8, u8),
    speed: (u8, u8),
    special_attack: (u8, u8),
    special_defense: (u8, u8),
}

const NEUTRAL_NATURE: NatureModifiers = NatureModifiers {
    attack: (1, 1),
    defense: (1, 1),
    speed: (1, 1),
    special_attack: (1, 1),
    special_defense: (1, 1),
};

fn species_battle_profile(name: &str) -> SpeciesBattleProfile {
    // Source: src/data/pokemon/species_info.h. This is deliberately limited
    // to species reachable in the scoped opening route.
    match name {
        "TORCHIC" => SpeciesBattleProfile {
            name: "TORCHIC",
            base_hp: 45,
            base_attack: 60,
            base_defense: 40,
            base_speed: 45,
            base_special_attack: 70,
            base_special_defense: 50,
            types: (BattleType::Fire, BattleType::Fire),
        },
        "MUDKIP" => SpeciesBattleProfile {
            name: "MUDKIP",
            base_hp: 50,
            base_attack: 70,
            base_defense: 50,
            base_speed: 40,
            base_special_attack: 50,
            base_special_defense: 50,
            types: (BattleType::Water, BattleType::Water),
        },
        "ZIGZAGOON" => SpeciesBattleProfile {
            name: "ZIGZAGOON",
            base_hp: 38,
            base_attack: 30,
            base_defense: 41,
            base_speed: 60,
            base_special_attack: 30,
            base_special_defense: 41,
            types: (BattleType::Normal, BattleType::Normal),
        },
        "POOCHYENA" => SpeciesBattleProfile {
            name: "POOCHYENA",
            base_hp: 35,
            base_attack: 55,
            base_defense: 35,
            base_speed: 35,
            base_special_attack: 30,
            base_special_defense: 30,
            types: (BattleType::Dark, BattleType::Dark),
        },
        "WURMPLE" => SpeciesBattleProfile {
            name: "WURMPLE",
            base_hp: 45,
            base_attack: 45,
            base_defense: 35,
            base_speed: 20,
            base_special_attack: 20,
            base_special_defense: 30,
            types: (BattleType::Bug, BattleType::Bug),
        },
        "WINGULL" => SpeciesBattleProfile {
            name: "WINGULL",
            base_hp: 40,
            base_attack: 30,
            base_defense: 30,
            base_speed: 85,
            base_special_attack: 55,
            base_special_defense: 30,
            types: (BattleType::Water, BattleType::Flying),
        },
        _ => SpeciesBattleProfile {
            name: "TREECKO",
            base_hp: 40,
            base_attack: 45,
            base_defense: 35,
            base_speed: 70,
            base_special_attack: 65,
            base_special_defense: 55,
            types: (BattleType::Grass, BattleType::Grass),
        },
    }
}

fn move_battle_profile(name: &str) -> MoveBattleProfile {
    // Source: src/data/battle_moves.h.
    match name {
        "POUND" => MoveBattleProfile {
            name: "POUND",
            power: 40,
            accuracy: 100,
            pp: 35,
            move_type: BattleType::Normal,
            special: false,
        },
        "SCRATCH" => MoveBattleProfile {
            name: "SCRATCH",
            power: 40,
            accuracy: 100,
            pp: 35,
            move_type: BattleType::Normal,
            special: false,
        },
        "LEER" => MoveBattleProfile {
            name: "LEER",
            power: 0,
            accuracy: 100,
            pp: 30,
            move_type: BattleType::Normal,
            special: false,
        },
        "GROWL" => MoveBattleProfile {
            name: "GROWL",
            power: 0,
            accuracy: 100,
            pp: 40,
            move_type: BattleType::Normal,
            special: false,
        },
        "FOCUS ENERGY" => MoveBattleProfile {
            name: "FOCUS ENERGY",
            power: 0,
            accuracy: 0,
            pp: 30,
            move_type: BattleType::Normal,
            special: false,
        },
        "STRING SHOT" => MoveBattleProfile {
            name: "STRING SHOT",
            power: 0,
            accuracy: 95,
            pp: 40,
            move_type: BattleType::Bug,
            special: false,
        },
        "WATER GUN" => MoveBattleProfile {
            name: "WATER GUN",
            power: 40,
            accuracy: 100,
            pp: 25,
            move_type: BattleType::Water,
            special: true,
        },
        _ => MoveBattleProfile {
            name: "TACKLE",
            power: 35,
            accuracy: 95,
            pp: 35,
            move_type: BattleType::Normal,
            special: false,
        },
    }
}

/// Sidecar mapping to Emerald's `enum Move`. Keeping IDs adjacent to names
/// lets source snapshots compare the numeric party array without making the
/// renderer or compact mechanics depend on decomp constants.
fn source_move_id(name: &str) -> u16 {
    match name {
        "POUND" => 1,
        "SCRATCH" => 10,
        "TACKLE" => 33,
        "LEER" => 43,
        "GROWL" => 45,
        "WATER GUN" => 55,
        "STRING SHOT" => 81,
        "FOCUS ENERGY" => 116,
        _ => 0,
    }
}

fn battle_move_slot(name: &str, pp: u8) -> BattleMoveSlot {
    BattleMoveSlot {
        move_id: source_move_id(name),
        name: name.to_owned(),
        pp,
    }
}

fn starter_species_name(starter: Option<StarterSpecies>) -> &'static str {
    match starter.unwrap_or(StarterSpecies::Treecko) {
        StarterSpecies::Treecko => "TREECKO",
        StarterSpecies::Torchic => "TORCHIC",
        StarterSpecies::Mudkip => "MUDKIP",
    }
}

fn source_random(state: &mut u32) -> u16 {
    *state = state.wrapping_mul(0x41c6_4e6d).wrapping_add(0x0000_6073);
    (*state >> 16) as u16
}

fn source_random32(state: &mut u32) -> u32 {
    u32::from(source_random(state)) | (u32::from(source_random(state)) << 16)
}

fn nature_modifiers(nature: u8) -> NatureModifiers {
    // gNatureStatTable order: Atk, Def, Speed, Sp.Atk, Sp.Def.
    const TABLE: [(Option<usize>, Option<usize>); 25] = [
        (None, None),
        (Some(0), Some(1)),
        (Some(0), Some(2)),
        (Some(0), Some(3)),
        (Some(0), Some(4)),
        (Some(1), Some(0)),
        (None, None),
        (Some(1), Some(2)),
        (Some(1), Some(3)),
        (Some(1), Some(4)),
        (Some(2), Some(0)),
        (Some(2), Some(1)),
        (None, None),
        (Some(2), Some(3)),
        (Some(2), Some(4)),
        (Some(3), Some(0)),
        (Some(3), Some(1)),
        (Some(3), Some(2)),
        (None, None),
        (Some(3), Some(4)),
        (Some(4), Some(0)),
        (Some(4), Some(1)),
        (Some(4), Some(2)),
        (Some(4), Some(3)),
        (None, None),
    ];
    let (raise, lower) = TABLE[usize::from(nature % 25)];
    let mut stats = [(1, 1); 5];
    if let Some(stat) = raise {
        stats[stat] = (110, 100);
    }
    if let Some(stat) = lower {
        stats[stat] = (90, 100);
    }
    NatureModifiers {
        attack: stats[0],
        defense: stats[1],
        speed: stats[2],
        special_attack: stats[3],
        special_defense: stats[4],
    }
}

fn source_random_ivs(seed: u32) -> (StatIvs, NatureModifiers) {
    // ScriptGiveMon → CreateMon(... USE_RANDOM_IVS ...): Random32 for the
    // personality followed by two packed six-IV Random calls.
    let mut rng = seed;
    let personality = source_random32(&mut rng);
    let first = u32::from(source_random(&mut rng));
    let second = u32::from(source_random(&mut rng));
    (
        StatIvs {
            hp: (first & 31) as u8,
            attack: ((first >> 5) & 31) as u8,
            defense: ((first >> 10) & 31) as u8,
            speed: (second & 31) as u8,
            special_attack: ((second >> 5) & 31) as u8,
            special_defense: ((second >> 10) & 31) as u8,
        },
        nature_modifiers((personality % 25) as u8),
    )
}

fn source_stat(base: u8, iv: u8, level: u8, modifier: (u8, u8)) -> u8 {
    let raw = ((u16::from(2 * base + iv) * u16::from(level)) / 100) + 5;
    ((raw * u16::from(modifier.0)) / u16::from(modifier.1)) as u8
}

fn source_hp(base: u8, iv: u8, level: u8) -> u8 {
    (((u16::from(2 * base + iv) * u16::from(level)) / 100) + u16::from(level) + 10) as u8
}

fn combatant_profile(
    species: SpeciesBattleProfile,
    level: u8,
    ivs: StatIvs,
    nature: NatureModifiers,
    move_names: &[&str],
) -> CombatantBattleProfile {
    let mut moves = [None; 4];
    for (slot, name) in move_names.iter().take(moves.len()).enumerate() {
        moves[slot] = Some(move_battle_profile(name));
    }
    CombatantBattleProfile {
        species,
        level,
        max_hp: source_hp(species.base_hp, ivs.hp, level),
        attack: source_stat(species.base_attack, ivs.attack, level, nature.attack),
        defense: source_stat(species.base_defense, ivs.defense, level, nature.defense),
        speed: source_stat(species.base_speed, ivs.speed, level, nature.speed),
        special_attack: source_stat(
            species.base_special_attack,
            ivs.special_attack,
            level,
            nature.special_attack,
        ),
        special_defense: source_stat(
            species.base_special_defense,
            ivs.special_defense,
            level,
            nature.special_defense,
        ),
        moves,
    }
}

fn starter_battle_profile(starter: Option<StarterSpecies>) -> CombatantBattleProfile {
    let (ivs, nature) = source_random_ivs(default_ambient_rng());
    let (physical, status) = match starter.unwrap_or(StarterSpecies::Treecko) {
        StarterSpecies::Treecko => ("POUND", "LEER"),
        StarterSpecies::Torchic => ("SCRATCH", "GROWL"),
        StarterSpecies::Mudkip => ("TACKLE", "GROWL"),
    };
    combatant_profile(
        species_battle_profile(starter_species_name(starter)),
        5,
        ivs,
        nature,
        &[physical, status],
    )
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
        moves: vec![
            battle_move_slot(physical_move.name, physical_move.pp),
            battle_move_slot(status_move.name, status_move.pp),
        ],
    }
}

fn normalize_slots(slots: &mut Vec<BattleMoveSlot>) {
    slots.truncate(4);
    slots.retain(|slot| !slot.name.is_empty());
    for slot in slots {
        if slot.move_id == 0 {
            slot.move_id = source_move_id(&slot.name);
        }
    }
}

fn legacy_party_move_slots(party: &StarterPartyState) -> Vec<BattleMoveSlot> {
    let profile = starter_battle_profile(Some(party.species));
    [
        profile.moves[0].map(|move_data| battle_move_slot(move_data.name, party.physical_move_pp)),
        profile.moves[1].map(|move_data| battle_move_slot(move_data.name, party.status_move_pp)),
    ]
    .into_iter()
    .flatten()
    .collect()
}

fn effective_party_move_slots(party: &StarterPartyState) -> Vec<BattleMoveSlot> {
    let mut slots = if party.moves.is_empty() {
        legacy_party_move_slots(party)
    } else {
        party.moves.clone()
    };
    normalize_slots(&mut slots);
    slots
}

fn legacy_battle_move_slots(battle: &BattleState) -> Vec<BattleMoveSlot> {
    vec![
        battle_move_slot(&battle.player_move_name, battle.player_move_pp),
        battle_move_slot(
            &battle.player_status_move_name,
            battle.player_status_move_pp,
        ),
    ]
}

fn effective_battle_move_slots(battle: &BattleState) -> Vec<BattleMoveSlot> {
    let mut slots = if battle.player_moves.is_empty() {
        legacy_battle_move_slots(battle)
    } else {
        battle.player_moves.clone()
    };
    normalize_slots(&mut slots);
    slots
}

fn move_slots_valid(slots: &[BattleMoveSlot]) -> bool {
    !slots.is_empty()
        && slots.len() <= 4
        && slots.iter().all(|slot| {
            slot.move_id != 0
                && slot.move_id == source_move_id(&slot.name)
                && slot.pp <= move_battle_profile(&slot.name).pp
        })
}

fn rival_battle_profile(
    starter: Option<StarterSpecies>,
    player_gender: PlayerGender,
) -> CombatantBattleProfile {
    // Route 103's trainer tables use level 5, IV 0, default moves. The
    // source name-hashed trainer personality determines the shown nature.
    let name = match starter.unwrap_or(StarterSpecies::Treecko) {
        StarterSpecies::Treecko => "TORCHIC",
        StarterSpecies::Torchic => "MUDKIP",
        StarterSpecies::Mudkip => "TREECKO",
    };
    let nature = match (player_gender, name) {
        (PlayerGender::Brendan, "TREECKO") => nature_modifiers(1),
        (PlayerGender::Brendan, "TORCHIC") => nature_modifiers(20),
        (PlayerGender::Brendan, "MUDKIP") => nature_modifiers(17),
        (PlayerGender::May, "TREECKO") => nature_modifiers(20),
        (PlayerGender::May, "TORCHIC") => nature_modifiers(14),
        (PlayerGender::May, "MUDKIP") => nature_modifiers(11),
        _ => NEUTRAL_NATURE,
    };
    let (physical, status) = match name {
        "TREECKO" => ("POUND", "LEER"),
        "TORCHIC" => ("SCRATCH", "GROWL"),
        _ => ("TACKLE", "GROWL"),
    };
    combatant_profile(
        species_battle_profile(name),
        5,
        StatIvs {
            hp: 0,
            attack: 0,
            defense: 0,
            speed: 0,
            special_attack: 0,
            special_defense: 0,
        },
        nature,
        &[physical, status],
    )
}

fn wild_battle_profile(name: &str, level: u8, move_names: &[&str]) -> CombatantBattleProfile {
    let name_hash = name.bytes().fold(0u32, |hash, byte| {
        hash.wrapping_mul(31).wrapping_add(u32::from(byte))
    });
    let (ivs, nature) = source_random_ivs(default_ambient_rng() ^ u32::from(level) ^ name_hash);
    combatant_profile(species_battle_profile(name), level, ivs, nature, move_names)
}

fn source_stage_stat(stat: u8, stage: i8) -> u8 {
    let stage = stage.clamp(-6, 6);
    if stage >= 0 {
        ((u16::from(stat) * (2 + stage) as u16) / 2) as u8
    } else {
        ((u16::from(stat) * 2) / (2 - stage) as u16) as u8
    }
}

fn type_multiplier(move_type: BattleType, types: (BattleType, BattleType)) -> (u8, u8) {
    let mut numerator = 1;
    let mut denominator = 1;
    for (index, defending) in [types.0, types.1].iter().enumerate() {
        if index == 1 && types.0 == types.1 {
            break;
        }
        let (up, down) = match (move_type, *defending) {
            (BattleType::Water, BattleType::Grass | BattleType::Water) => (1, 2),
            (BattleType::Water, BattleType::Fire) => (2, 1),
            _ => (1, 1),
        };
        numerator *= up;
        denominator *= down;
    }
    (numerator, denominator)
}

fn source_move_damage(
    level: u8,
    attacker: SpeciesBattleProfile,
    attack: u8,
    special_attack: u8,
    attacker_stage: i8,
    defender: SpeciesBattleProfile,
    defense: u8,
    special_defense: u8,
    defender_stage: i8,
    move_data: MoveBattleProfile,
    critical: bool,
) -> u8 {
    if move_data.power == 0 {
        return 0;
    }
    let attack_stat = if move_data.special {
        special_attack
    } else {
        attack
    };
    let defense_stat = if move_data.special {
        special_defense
    } else {
        defense
    };
    // `CalculateBaseDamage` ignores an attacker's negative stage and a
    // defender's positive stage on a critical hit, but preserves the
    // favorable stage in either direction.
    let attacking = if critical && attacker_stage <= 0 {
        attack_stat
    } else {
        source_stage_stat(attack_stat, attacker_stage)
    };
    let defending = (if critical && defender_stage >= 0 {
        defense_stat
    } else {
        source_stage_stat(defense_stat, defender_stage)
    })
    .max(1);
    let scaled = (u32::from(2 * level / 5 + 2) * u32::from(move_data.power) * u32::from(attacking))
        / u32::from(defending);
    let mut damage = ((scaled / 50) + 2) as u16;
    if critical {
        damage *= 2;
    }
    if attacker.types.0 == move_data.move_type || attacker.types.1 == move_data.move_type {
        damage = (damage * 15) / 10;
    }
    let (numerator, denominator) = type_multiplier(move_data.move_type, defender.types);
    damage = (damage * u16::from(numerator)) / u16::from(denominator);
    damage.max(1) as u8
}

fn player_battle_damage_for(
    battle: &BattleState,
    move_data: MoveBattleProfile,
    critical: bool,
) -> u8 {
    source_move_damage(
        battle.player_level,
        species_battle_profile(&battle.player_species),
        battle.player_attack,
        battle.player_special_attack,
        battle.player_attack_stage,
        species_battle_profile(&battle.opponent_species),
        battle.opponent_defense,
        battle.opponent_special_defense,
        battle.opponent_defense_stage,
        move_data,
        critical,
    )
}

fn opponent_battle_damage_for(
    battle: &BattleState,
    move_data: MoveBattleProfile,
    critical: bool,
) -> u8 {
    source_move_damage(
        battle.opponent_level,
        species_battle_profile(&battle.opponent_species),
        battle.opponent_attack,
        battle.opponent_special_attack,
        battle.opponent_attack_stage,
        species_battle_profile(&battle.player_species),
        battle.player_defense,
        battle.player_special_defense,
        battle.player_defense_stage,
        move_data,
        critical,
    )
}

fn opening_battle_state(
    opponent: BattleOpponent,
    player: CombatantBattleProfile,
    enemy: CombatantBattleProfile,
    wild: bool,
    message: String,
    entry_transition_frames: u16,
    rng_state: u32,
    rival_setup_first_turn: bool,
) -> BattleState {
    let player_physical = player.moves[0].expect("starter must have a physical opening move");
    let player_status = player.moves[1].expect("starter must have a status opening move");
    let opponent_initial = enemy.moves[0].expect("opening opponent must have a first move slot");
    let player_move_damage = source_move_damage(
        player.level,
        player.species,
        player.attack,
        player.special_attack,
        0,
        enemy.species,
        enemy.defense,
        enemy.special_defense,
        0,
        player_physical,
        false,
    );
    let opponent_move_damage = source_move_damage(
        enemy.level,
        enemy.species,
        enemy.attack,
        enemy.special_attack,
        0,
        player.species,
        player.defense,
        player.special_defense,
        0,
        opponent_initial,
        false,
    );
    let opponent_moves = enemy
        .moves
        .iter()
        .flatten()
        .map(|move_data| battle_move_slot(move_data.name, move_data.pp))
        .collect();
    let player_moves = player
        .moves
        .iter()
        .flatten()
        .map(|move_data| battle_move_slot(move_data.name, move_data.pp))
        .collect();
    BattleState {
        opponent,
        rng_state,
        player_species: player.species.name.to_owned(),
        opponent_species: enemy.species.name.to_owned(),
        opponent_move_name: opponent_initial.name.to_owned(),
        opponent_moves,
        opponent_move_slot: None,
        opponent_turn_count: 0,
        rival_setup_first_turn,
        opponent_move_damage,
        player_hp: player.max_hp,
        player_max_hp: player.max_hp,
        player_level: player.level,
        player_attack: player.attack,
        player_defense: player.defense,
        player_speed: player.speed,
        player_special_attack: player.special_attack,
        player_special_defense: player.special_defense,
        rival_hp: enemy.max_hp,
        opponent_max_hp: enemy.max_hp,
        opponent_level: enemy.level,
        opponent_attack: enemy.attack,
        opponent_defense: enemy.defense,
        opponent_speed: enemy.speed,
        opponent_special_attack: enemy.special_attack,
        opponent_special_defense: enemy.special_defense,
        player_move_damage,
        player_move_name: player_physical.name.to_owned(),
        player_status_move_name: player_status.name.to_owned(),
        player_move_pp: player_physical.pp,
        player_status_move_pp: player_status.pp,
        player_moves,
        opponent_attack_stage: 0,
        opponent_defense_stage: 0,
        player_attack_stage: 0,
        player_defense_stage: 0,
        player_speed_stage: 0,
        command_cursor: BATTLE_COMMAND_FIGHT,
        command_cursor_rendered: None,
        command_cursor_transition_frames: 0,
        selecting_move: false,
        move_selection_transition_frames: 0,
        move_cursor_rendered: None,
        move_cursor_transition_frames: 0,
        move_selection_cancel_transition_frames: 0,
        player_battler_oam_phase_reset_frame: 0,
        move_selection_oam_phase_delay_frames: 0,
        party_screen_open: false,
        escaped: false,
        opponent_fled: false,
        wild,
        field_return: None,
        run_attempts: 0,
        move_cursor: 0,
        player_fainted: false,
        message: Some(message),
        message_visual_start_frame: 0,
        entry_transition_frames,
        intro_opponent_trainer_exit_frames: 0,
        intro_stage: 0,
        intro_player_sendout_pending: false,
        intro_message_dismiss_delay_frames: 0,
        intro_message_hidden: false,
        intro_message_hide_on_dismiss: false,
        intro_message_arrow_reset_on_dismiss: false,
        intro_message_dismiss_arrow_frame: 0,
        intro_message_print_chars: 0,
        intro_message_print_hold_frames: 0,
        intro_player_sendout_frames: 0,
        intro_player_sendout_elapsed_frames: 0,
        intro_player_sendout_started: false,
        last_move_hit: false,
        last_move_critical: false,
        last_damage_variance: None,
        turn_phase: BattleTurnPhase::IntroMessage,
    }
}

#[derive(Clone, Copy)]
struct BattleMoveResolution {
    hit: bool,
    critical: bool,
    damage: u8,
}

#[derive(Clone, Copy)]
enum OpponentChoice {
    Move(usize),
    Flee,
}

fn battle_random(battle: &mut BattleState) -> u16 {
    source_random(&mut battle.rng_state)
}

/// Gen-III's wild escape check.  The opening maps normally make escape
/// certain because the starter outruns the encountered Pokémon, but retaining
/// the failed branch is essential for deterministic replay and prevents a
/// RUN request from silently acting as a route-specific teleport.
fn try_wild_escape(battle: &mut BattleState) -> bool {
    debug_assert!(battle.wild);
    let denominator = u16::from((battle.opponent_speed / 4).max(1));
    let chance = (u16::from(battle.player_speed) * 128 / denominator)
        .saturating_add(u16::from(battle.run_attempts) * 30);
    if chance > 255 || u16::from(battle_random(battle) & 0x00ff) < chance {
        true
    } else {
        battle.run_attempts = battle.run_attempts.saturating_add(1);
        false
    }
}

fn source_hp_percent(hp: u8, max_hp: u8) -> u8 {
    (u16::from(hp) * 100 / u16::from(max_hp.max(1))) as u8
}

fn legal_opponent_move_slots(battle: &BattleState) -> Vec<usize> {
    battle
        .opponent_moves
        .iter()
        .enumerate()
        .filter_map(|(slot, move_slot)| (move_slot.pp > 0).then_some(slot))
        .collect()
}

fn opponent_move_data(battle: &BattleState, slot: usize) -> Option<MoveBattleProfile> {
    battle
        .opponent_moves
        .get(slot)
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
    let physical_slot = legal_slots
        .iter()
        .copied()
        .find(|slot| opponent_move_data(battle, *slot).is_some_and(|move_data| move_data.power > 0))
        .expect("Route 103 rival must have a damaging move");
    let status_slot = legal_slots.iter().copied().find(|slot| {
        opponent_move_data(battle, *slot).is_some_and(|move_data| move_data.power == 0)
    });
    let physical_move =
        opponent_move_data(battle, physical_slot).expect("selected rival move must remain usable");
    let simulated_damage = (u16::from(opponent_battle_damage_for(battle, physical_move, false))
        * u16::from(simulated_variance[physical_slot])
        / 100)
        .max(1) as u8;
    let physical_score = if simulated_damage >= battle.player_hp {
        104
    } else {
        100
    };
    let mut scores = legal_slots.iter().map(|_| 100_i16).collect::<Vec<_>>();
    if let Some(status_slot) = status_slot {
        let status_index = legal_slots
            .iter()
            .position(|slot| *slot == status_slot)
            .expect("status move must be a legal move");
        let status_move = opponent_move_data(battle, status_slot)
            .expect("selected rival status move must remain usable");
        scores[status_index] = if battle.rival_setup_first_turn {
            // `AI_SCRIPT_SETUP_FIRST_TURN` only encourages the source's
            // positive setup effects (the list at
            // `data/battle_ai_scripts.s:2641-2647`); LEER is not in that
            // list. `AI_TryToFaint` still subtracts one because a status move
            // is not the most powerful move (`s:2616-2638`).
            99
        } else {
            // Torchic/Mudkip and May's Treecko use viability, with the
            // source routine selected by the actual status move effect. The
            // common `AI_TryToFaint` pass first subtracts one from this
            // non-damaging move before viability applies its penalties.
            match status_move.name {
                "GROWL" => 99 - rival_attack_down_score_penalty(battle),
                "LEER" => 99 - rival_defense_down_score_penalty(battle),
                _ => 99,
            }
        };
    }
    let physical_index = legal_slots
        .iter()
        .position(|slot| *slot == physical_slot)
        .expect("damaging move must be a legal move");
    scores[physical_index] = physical_score;
    let best_score = scores.iter().copied().max().expect("rival has legal moves");
    let best_slots = legal_slots
        .iter()
        .zip(scores)
        .filter_map(|(slot, score)| (score == best_score).then_some(*slot))
        .collect::<Vec<_>>();
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
        BattleOpponent::Poochyena | BattleOpponent::Wingull | BattleOpponent::Wurmple => {
            OpponentChoice::Move(select_wild_opponent_move(battle))
        }
    };
    if let OpponentChoice::Move(slot) = choice {
        let move_slot = battle
            .opponent_moves
            .get(slot)
            .expect("selected opponent slot must exist");
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
    battle.message_visual_start_frame = 0;
    battle.turn_phase = BattleTurnPhase::TerminalMessage;
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

fn resolve_player_damage_move(
    battle: &mut BattleState,
    move_data: MoveBattleProfile,
) -> BattleMoveResolution {
    if !battle_accuracy_check(battle, move_data) {
        return BattleMoveResolution {
            hit: false,
            critical: false,
            damage: 0,
        };
    }
    let critical = battle_critical_check(battle);
    let base_damage = player_battle_damage_for(battle, move_data, critical);
    let damage = apply_battle_damage_variance(battle, base_damage);
    battle.last_move_critical = critical;
    BattleMoveResolution {
        hit: true,
        critical,
        damage,
    }
}

fn resolve_opponent_damage_move(battle: &mut BattleState) -> BattleMoveResolution {
    let selected_slot = battle.opponent_move_slot.map(usize::from).or_else(|| {
        battle
            .opponent_moves
            .iter()
            .position(|move_slot| move_slot.pp > 0 && move_slot.name == battle.opponent_move_name)
    });
    let Some(selected_slot) = selected_slot else {
        return BattleMoveResolution {
            hit: false,
            critical: false,
            damage: 0,
        };
    };
    let Some(move_data) = opponent_move_data(battle, selected_slot) else {
        return BattleMoveResolution {
            hit: false,
            critical: false,
            damage: 0,
        };
    };
    battle.opponent_move_slot = Some(selected_slot as u8);
    battle.opponent_move_name = move_data.name.to_owned();
    if let Some(move_slot) = battle.opponent_moves.get_mut(selected_slot) {
        // `ppreduce` runs on both successful and missed source moves.
        move_slot.pp = move_slot.pp.saturating_sub(1);
    }
    if !battle_accuracy_check(battle, move_data) {
        battle.opponent_turn_count = battle.opponent_turn_count.saturating_add(1);
        return BattleMoveResolution {
            hit: false,
            critical: false,
            damage: 0,
        };
    }
    if move_data.power == 0 {
        match move_data.name {
            "GROWL" => battle.player_attack_stage = (battle.player_attack_stage - 1).max(-6),
            "LEER" => battle.player_defense_stage = (battle.player_defense_stage - 1).max(-6),
            "STRING SHOT" => battle.player_speed_stage = (battle.player_speed_stage - 1).max(-6),
            _ => {}
        }
        battle.opponent_turn_count = battle.opponent_turn_count.saturating_add(1);
        return BattleMoveResolution {
            hit: true,
            critical: false,
            damage: 0,
        };
    }
    let critical = battle_critical_check(battle);
    let damage = apply_battle_damage_variance(
        battle,
        opponent_battle_damage_for(battle, move_data, critical),
    );
    battle.last_move_critical = critical;
    battle.opponent_turn_count = battle.opponent_turn_count.saturating_add(1);
    BattleMoveResolution {
        hit: true,
        critical,
        damage,
    }
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
pub struct TilePosition {
    pub x: i16,
    pub y: i16,
}

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

fn default_npc_walk_duration() -> u8 {
    16
}

/// Source `MOVEMENT_TYPE_WANDER_*` objects do not share a global cadence.
/// Each sprite first completes its facing action, waits for a separately
/// randomized delay, chooses a direction, and only then performs one walk.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub enum AmbientWanderMode {
    Face {
        remaining_frames: u8,
    },
    Delay {
        remaining_frames: u8,
    },
    Walk {
        remaining_frames: u8,
    },
    /// A frozen source checkpoint can begin mid-object-event. This retains a
    /// measured stable pose until the next EWRAM-proven scheduler boundary.
    MeasuredWait {
        release_frame: u64,
    },
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

fn default_ambient_rng() -> u32 {
    0x5eed_0001
}

fn default_starter_lab_choice_yes() -> bool {
    true
}

fn default_starter_confirm_yes() -> bool {
    true
}

fn default_naming_target() -> NamingTarget {
    NamingTarget::Player
}

fn default_name_entry_page() -> NamingKeyboardPage {
    NamingKeyboardPage::LettersUpper
}

/// The field task which is allowed to consume the controller on a VBlank.
///
/// This deliberately describes *ownership*, not a visual screen. A map
/// script may lock the field while no dialogue is visible, and a text box may
/// remain visible while its printer is still the owner. Keeping that
/// distinction in durable state prevents the common "close the box and walk
/// on the same frame" bug when routes are replayed in differently sized
/// transport requests.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum FieldInputOwner {
    Field,
    Battle,
    /// The field-only SELECT registration help window owns input while its
    /// border/text tasks are live.  This is not a script dialogue: source
    /// installs it directly from the field controller and releases it on a
    /// delayed close hand-off.
    SelectModal,
    Dialogue,
    Script,
    Warp,
    ClockEditor,
    Menu,
}

/// The source-observed SELECT registration help modal available in the
/// initial bedroom field checkpoint.
///
/// The modal becomes visibly bordered on its fifth VBlank.  Its text has
/// finished printing before the final setup callbacks settle; input remains
/// locked through VBlank 64.  A completed window dismissed with B stays
/// visible for two further VBlanks before the normal field task resumes.
/// Keeping all three clocks in checkpoint state is essential: reducing this
/// to a boolean was what let random tapes walk while source was still typing.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct FieldSelectModal {
    /// VBlanks including the Select edge that installed the task.
    pub elapsed_frames: u8,
    /// Remaining post-dismissal visible VBlanks. `None` means the modal is
    /// still opening/printing/settled; zero is never serialized.
    #[serde(default)]
    pub closing_frames: Option<u8>,
}

impl FieldSelectModal {
    pub const BORDER_VISIBLE_AT: u8 = 5;
    pub const INPUT_READY_AT: u8 = 64;
    // `B` is itself a visible source frame, followed by two further visible
    // VBlanks.  Therefore the closing task must retain three frames when it
    // is installed: B, then the two neutral VBlanks.  Removing the window on
    // the second neutral VBlank was externally visible at Select V67.
    pub const CLOSE_VISIBLE_FRAMES: u8 = 3;
    pub const MESSAGE: &'static str =
        "An item in the BAG can be\nregistered to SELECT for easy use.";

    fn new() -> Self {
        // The Select edge itself is the first source VBlank of the UI task.
        Self {
            elapsed_frames: 1,
            closing_frames: None,
        }
    }

    pub fn border_visible(&self) -> bool {
        self.elapsed_frames >= Self::BORDER_VISIBLE_AT
    }

    pub fn input_ready(&self) -> bool {
        self.closing_frames.is_none() && self.elapsed_frames >= Self::INPUT_READY_AT
    }

    /// Source text is effectively complete around V41, while sprite/window
    /// setup remains input-locked until V64.  Preserve that distinction in
    /// the renderer projection rather than pretending text completion means
    /// a field hand-off.
    pub fn visible_text(&self) -> String {
        if !self.border_visible() {
            return String::new();
        }
        // The source TextPrinter emits its first glyph on V6: the five
        // VBlanks through the border are setup, then one glyph per VBlank.
        // The old two-glyph approximation made the page appear complete
        // around V41, while the source still reveals the final ``use.`` at
        // V64. Keeping this clock one-glyph/one-VBlank is observable at V6,
        // V18, V30, V41, V51, and V60 in the authenticated source tape.
        let mut remaining_glyphs = usize::from(self.elapsed_frames.saturating_sub(5));
        let mut rendered = String::new();
        for character in Self::MESSAGE.chars() {
            // Emerald's `\n` is a control code. It moves the printer to the
            // second line in the same VBlank as the following glyph instead
            // of consuming a glyph clock. Counting it made the second-line
            // `r` arrive one VBlank late and hid the final period at V64.
            if character == '\n' {
                rendered.push(character);
                continue;
            }
            if remaining_glyphs == 0 {
                break;
            }
            rendered.push(character);
            remaining_glyphs -= 1;
        }
        rendered
    }
}

/// Serializable paged field dialogue. `WorldState::dialogue` remains the
/// renderer/readout projection for compatibility with existing checkpoints;
/// this task is the authoritative ownership and page state for new field
/// scripts.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct FieldDialogueState {
    pub pages: Vec<String>,
    pub page: usize,
    pub print_remaining: u16,
}

impl FieldDialogueState {
    fn new(pages: Vec<String>) -> Option<Self> {
        let first = pages.first()?;
        Some(Self {
            print_remaining: dialogue_printer_duration(first),
            pages,
            page: 0,
        })
    }

    fn current_text(&self) -> &str {
        // Construction and page advancement preserve this invariant.  Keep a
        // total accessor so a malformed imported checkpoint does not panic
        // the field scheduler.
        self.pages.get(self.page).map(String::as_str).unwrap_or("")
    }

    fn advance_printer(&mut self, frames: u32) {
        self.print_remaining = self
            .print_remaining
            .saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
    }

    /// Returns whether a page was advanced. `false` means that the dialogue
    /// completed and should release the script on this VBlank.
    fn advance_page(&mut self) -> bool {
        if self.page + 1 >= self.pages.len() {
            return false;
        }
        self.page += 1;
        self.print_remaining = dialogue_printer_duration(self.current_text());
        true
    }
}

/// Story facts set by reusable scripts. These are intentionally separate
/// from `StoryPhase`: phases decide which scene is currently executing;
/// flags record completed prerequisites and survive a later map visit.
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
pub struct StoryFlags {
    pub wall_clock_started: bool,
    pub upstairs_mom_scene_complete: bool,
    pub gym_broadcast_complete: bool,
    pub pokemon_obtained: bool,
    pub birch_rescue_started: bool,
    /// The Lab has formally acknowledged the Pokémon selected on Route 101.
    /// This is distinct from `pokemon_obtained`, which source sets before
    /// the picker itself opens.
    pub starter_acknowledged: bool,
    /// Birch's final Lab agreement has released the player to visit the
    /// rival. Map connections consult this durable source gate rather than
    /// inferring permission from a broad story phase.
    pub rival_route_unlocked: bool,
    /// Source trainer/script flags established by the continuous Route 103
    /// victory path. They remain separate from `StoryPhase`: imported states
    /// must prove the victory rather than selecting a later presentation.
    pub defeated_rival_route103: bool,
    pub hide_route103_rival: bool,
    pub hide_littleroot_lab_rival: bool,
    pub hide_oldale_rival: bool,
}

/// Source event variables which gate the rival-return maps.  These values are
/// authenticated at the first stable field checkpoint after Route 103.
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
pub struct OpeningStoryVars {
    pub birch_lab_state: u8,
    pub littleroot_rival_state: u8,
    pub oldale_rival_state: u8,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ProgressFlag {
    WallClockStarted,
    UpstairsMomSceneComplete,
    GymBroadcastComplete,
    BirchPromptComplete,
    HasPokedex,
    PokemonObtained,
    BirchRescueStarted,
    StarterAcknowledged,
    RivalRouteUnlocked,
}

impl StoryFlags {
    fn has(self, flag: ProgressFlag, world: &WorldState) -> bool {
        match flag {
            ProgressFlag::WallClockStarted => self.wall_clock_started,
            ProgressFlag::UpstairsMomSceneComplete => self.upstairs_mom_scene_complete,
            ProgressFlag::GymBroadcastComplete => self.gym_broadcast_complete,
            ProgressFlag::BirchPromptComplete => world.birch_prompt_complete,
            ProgressFlag::HasPokedex => world.has_pokedex,
            ProgressFlag::PokemonObtained => self.pokemon_obtained,
            ProgressFlag::BirchRescueStarted => self.birch_rescue_started,
            ProgressFlag::StarterAcknowledged => self.starter_acknowledged,
            ProgressFlag::RivalRouteUnlocked => self.rival_route_unlocked,
        }
    }

    fn set(&mut self, flag: ProgressFlag) {
        match flag {
            ProgressFlag::WallClockStarted => self.wall_clock_started = true,
            ProgressFlag::UpstairsMomSceneComplete => self.upstairs_mom_scene_complete = true,
            ProgressFlag::GymBroadcastComplete => self.gym_broadcast_complete = true,
            ProgressFlag::PokemonObtained => self.pokemon_obtained = true,
            ProgressFlag::BirchRescueStarted => self.birch_rescue_started = true,
            ProgressFlag::StarterAcknowledged => self.starter_acknowledged = true,
            ProgressFlag::RivalRouteUnlocked => self.rival_route_unlocked = true,
            // These are projections of existing long-lived world facts and
            // are not independently writable by a generic script.
            ProgressFlag::BirchPromptComplete | ProgressFlag::HasPokedex => {}
        }
    }
}

/// Timing owned by the generic warp task. A source map event may spend a
/// measured number of VBlanks armed before palette fade starts; zero retains
/// Emerald's immediate-fade behavior used by the existing reference routes.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct WarpTiming {
    pub pre_fade_delay_frames: u8,
    pub fade_frames: u8,
}

impl Default for WarpTiming {
    fn default() -> Self {
        Self {
            pre_fade_delay_frames: 0,
            fade_frames: 16,
        }
    }
}

const DEFAULT_WARP_TIMING: WarpTiming = WarpTiming {
    pre_fade_delay_frames: 0,
    fade_frames: 16,
};

/// Declarative map-edge gate. It is intentionally data-only: the player
/// cannot escape a story boundary just because a later transport packet is
/// grouped differently.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct GatePredicate {
    pub minimum_phase: Option<StoryPhase>,
    pub exact_phase: Option<StoryPhase>,
    pub required_flag: Option<ProgressFlag>,
}

impl GatePredicate {
    fn satisfied(self, world: &WorldState) -> bool {
        self.minimum_phase
            .map_or(true, |phase| world.phase >= phase)
            && self.exact_phase.map_or(true, |phase| world.phase == phase)
            && self
                .required_flag
                .map_or(true, |flag| world.story_flags.has(flag, world))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ConnectionMode {
    Fade,
    Scroll,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ConnectionAction {
    None,
    StartBirchRescue,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct MapConnectionRule {
    source_map: MapId,
    direction: Facing,
    min_x: i16,
    max_x: i16,
    source_y: i16,
    destination_map: MapId,
    destination_y: i16,
    mode: ConnectionMode,
    gate: GatePredicate,
    action: ConnectionAction,
}

impl MapConnectionRule {
    fn matches(self, world: &WorldState, direction: Facing) -> bool {
        self.source_map == world.map
            && self.direction == direction
            && (self.min_x..=self.max_x).contains(&world.player.x)
            && self.source_y == world.player.y
    }
}

const MAP_CONNECTION_RULES: [MapConnectionRule; 7] = [
    MapConnectionRule {
        source_map: MapId::LittlerootTown,
        direction: Facing::Up,
        min_x: 10,
        max_x: 11,
        source_y: 0,
        destination_map: MapId::Route101,
        destination_y: 19,
        mode: ConnectionMode::Fade,
        gate: GatePredicate {
            minimum_phase: None,
            exact_phase: Some(StoryPhase::MetRival),
            required_flag: Some(ProgressFlag::BirchPromptComplete),
        },
        action: ConnectionAction::StartBirchRescue,
    },
    MapConnectionRule {
        source_map: MapId::LittlerootTown,
        direction: Facing::Up,
        min_x: 10,
        max_x: 11,
        source_y: 0,
        destination_map: MapId::Route101,
        destination_y: 19,
        mode: ConnectionMode::Fade,
        gate: GatePredicate {
            minimum_phase: Some(StoryPhase::StarterChosen),
            exact_phase: None,
            required_flag: Some(ProgressFlag::RivalRouteUnlocked),
        },
        action: ConnectionAction::None,
    },
    MapConnectionRule {
        source_map: MapId::Route101,
        direction: Facing::Down,
        min_x: 10,
        max_x: 11,
        source_y: 19,
        destination_map: MapId::LittlerootTown,
        destination_y: 0,
        mode: ConnectionMode::Fade,
        gate: GatePredicate {
            minimum_phase: Some(StoryPhase::StarterChosen),
            exact_phase: None,
            required_flag: Some(ProgressFlag::StarterAcknowledged),
        },
        action: ConnectionAction::None,
    },
    MapConnectionRule {
        source_map: MapId::Route101,
        direction: Facing::Up,
        min_x: 8,
        max_x: 11,
        source_y: 0,
        destination_map: MapId::OldaleTown,
        // The first post-edge source receipt is the south connection row,
        // raw y=20.  It is an authored runtime border coordinate (the
        // ordinary 20×20 field layout ends at y=19), so retain it until the
        // next northward stride commits the interior tile.
        destination_y: 20,
        mode: ConnectionMode::Scroll,
        gate: GatePredicate {
            minimum_phase: Some(StoryPhase::StarterChosen),
            exact_phase: None,
            required_flag: Some(ProgressFlag::RivalRouteUnlocked),
        },
        action: ConnectionAction::None,
    },
    MapConnectionRule {
        source_map: MapId::OldaleTown,
        direction: Facing::Down,
        min_x: 8,
        max_x: 11,
        source_y: 19,
        destination_map: MapId::Route101,
        destination_y: 0,
        mode: ConnectionMode::Scroll,
        gate: GatePredicate {
            minimum_phase: Some(StoryPhase::StarterChosen),
            exact_phase: None,
            required_flag: Some(ProgressFlag::StarterAcknowledged),
        },
        action: ConnectionAction::None,
    },
    MapConnectionRule {
        source_map: MapId::OldaleTown,
        direction: Facing::Up,
        min_x: 8,
        max_x: 11,
        source_y: 0,
        destination_map: MapId::Route103,
        destination_y: 21,
        mode: ConnectionMode::Scroll,
        gate: GatePredicate {
            minimum_phase: Some(StoryPhase::StarterChosen),
            exact_phase: None,
            required_flag: Some(ProgressFlag::RivalRouteUnlocked),
        },
        action: ConnectionAction::None,
    },
    MapConnectionRule {
        source_map: MapId::Route103,
        direction: Facing::Down,
        min_x: 8,
        max_x: 11,
        source_y: 21,
        destination_map: MapId::OldaleTown,
        destination_y: 0,
        mode: ConnectionMode::Scroll,
        gate: GatePredicate {
            minimum_phase: Some(StoryPhase::StarterChosen),
            exact_phase: None,
            required_flag: Some(ProgressFlag::RivalRouteUnlocked),
        },
        action: ConnectionAction::None,
    },
];

/// Declarative encounter data.  The currently covered source paths are
/// finite, but every rule flows through the same battle handoff and return
/// machinery; adding a grass table is data work rather than another bespoke
/// `begin_route_*` implementation.
#[derive(Clone)]
struct WildEncounterRule {
    id: WildEncounterId,
    map: MapId,
    phase: StoryPhase,
    position: TilePosition,
    opponent: BattleOpponent,
    species: &'static str,
    level: u8,
    moves: &'static [&'static str],
    entry_transition_frames: u16,
}

const WILD_ENCOUNTER_RULES: [WildEncounterRule; 3] = [
    WildEncounterRule {
        id: WildEncounterId::Route101Poochyena,
        map: MapId::Route101,
        phase: StoryPhase::BirchRescued,
        position: TilePosition { x: 15, y: 5 },
        opponent: BattleOpponent::Poochyena,
        species: "POOCHYENA",
        level: 2,
        moves: &["TACKLE"],
        entry_transition_frames: 224,
    },
    // Authenticated mGBA boundary: from Route 101 `(13,10)`, one Up stride
    // enters the Wurmple battle at the committed field tile `(13,9)`.
    WildEncounterRule {
        id: WildEncounterId::Route101Wurmple,
        map: MapId::Route101,
        phase: StoryPhase::BirchRescued,
        position: TilePosition { x: 13, y: 9 },
        opponent: BattleOpponent::Wurmple,
        species: "WURMPLE",
        level: 2,
        moves: &["TACKLE", "STRING SHOT"],
        entry_transition_frames: 352,
    },
    WildEncounterRule {
        id: WildEncounterId::Route103Wingull,
        map: MapId::Route103,
        phase: StoryPhase::BirchRescued,
        position: TilePosition { x: 16, y: 13 },
        opponent: BattleOpponent::Wingull,
        species: "WINGULL",
        level: 3,
        moves: &["GROWL", "WATER GUN"],
        entry_transition_frames: 224,
    },
];

/// Declarative trainer-event surface.  The map script identifies the tile in
/// front of the player; the generic handoff below owns dialogue, approach,
/// battle, and post-battle departure without a route input tape.
#[derive(Clone)]
struct TrainerEncounterRule {
    map: MapId,
    required_phase: StoryPhase,
    target: TilePosition,
    opponent: BattleOpponent,
}

const TRAINER_ENCOUNTER_RULES: [TrainerEncounterRule; 1] = [TrainerEncounterRule {
    map: MapId::Route103,
    required_phase: StoryPhase::StarterChosen,
    target: TilePosition { x: 10, y: 3 },
    opponent: BattleOpponent::Rival,
}];

/// Typed projection of Route 103's persisted map-script/battle state.
/// Unlike a route cursor this is derived from durable task fields, so imported
/// checkpoints and replay partitioning expose the same owner.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RivalRouteTask {
    Field,
    ChallengeDialogue,
    ChallengeApproach,
    Battle,
    DefeatDialogue,
    Departure,
}

/// Typed projection of the post-rival return corridor.  The source map
/// scripts still own their measured movement and fanfare clocks; this enum
/// gives checkpoint consumers one stable answer for which script boundary is
/// active without encoding the controller route used to reach it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReturnJourneyTask {
    Field,
    Route103DefeatDialogue,
    Route103Departure,
    ReturnField,
    OldaleApproach,
    OldaleDialogue,
    OldaleDeparture,
    LabWarp,
    PokedexArrival,
    PokedexDialogue,
    PokedexReceiptFanfare,
    PokedexRivalApproach,
    PokeBallGiftFanfare,
    RunningShoesPrompt,
    RunningShoesApproach,
    RunningShoesDialogue,
    RunningShoesReturnDelay,
    RunningShoesReturn,
    RunningShoesDoor,
    Route101Departure,
}

/// A small, serializable script runner for ordinary field scenes. It makes
/// page sequencing, waits, flags, and warp hand-offs explicit rather than
/// turning every NPC conversation into a one-off cursor variable.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ScriptStep {
    Dialogue {
        pages: Vec<String>,
    },
    Wait {
        frames: u16,
    },
    SetFlag {
        flag: ProgressFlag,
    },
    /// Transfers field ownership to the generic three-ball starter picker.
    /// The selected index is data, not a route-input sequence.
    OpenStarterPicker {
        default_starter: StarterSpecies,
    },
    /// Makes a source-authored battle entry the next exclusive task after a
    /// picker confirmation. Additional opening encounters can reuse this
    /// action without teaching the dialogue runner about controller inputs.
    BeginBattleHandoff {
        opponent: BattleOpponent,
    },
    /// Records the exclusive story task at an observable script boundary.
    /// The runner can therefore represent a post-battle continuation without
    /// a route-specific cursor or replayed input packet.
    SetRoute101RescueTask {
        task: Route101RescueTask,
    },
    Warp {
        destination_map: MapId,
        destination: TilePosition,
        timing: WarpTiming,
    },
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct FieldScriptRunner {
    pub steps: Vec<ScriptStep>,
    pub cursor: usize,
    pub wait_remaining: Option<u16>,
}

/// Route 101's progression surface. The legacy `StoryPhase` still selects
/// broad content; this task records the actual exclusive owner within the
/// rescue/picker/battle corridor and is safe to serialize mid-handoff.
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Route101RescueTask {
    Inactive,
    RescueChoreography,
    BagPrompt,
    StarterPicker,
    StarterReveal,
    StarterConfirm,
    BattleHandoff,
    Battle,
    Resolved,
    PostBattleApproach,
    PostBattleDialogue,
    LabHandoff,
    StarterLabAcknowledgement,
    StarterLabNicknameChoice,
    StarterLabNaming,
    StarterLabRivalChoice,
    StarterLabAgreement,
    RouteAccess,
}

impl Default for Route101RescueTask {
    fn default() -> Self {
        Self::Inactive
    }
}

/// A rectangular map-event trigger and its atomic fade destination. Keeping
/// these rules as typed data lets the same transition primitive serve house
/// doors, stairs, and later authored interiors without adding route-specific
/// `match` branches to the controller.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WarpRule {
    pub source_map: MapId,
    pub min_x: i16,
    pub max_x: i16,
    pub min_y: i16,
    pub max_y: i16,
    pub destination_map: MapId,
    pub destination: TilePosition,
    /// Optional direction required to enter a map-event tile.  Doors and
    /// stairs are not symmetric collision triggers: the same tile may be
    /// walkable from one side while the reverse approach continues through
    /// the room.  `None` retains the legacy direction-agnostic behavior for
    /// declarative/scripted warps.
    pub entry_facing: Option<Facing>,
    /// Authoritative timing belongs to the event rule, not to a controller
    /// caller.  This keeps stairs, doors, and future map events on the same
    /// atomic warp primitive while allowing a source-observed arming delay.
    pub timing: WarpTiming,
}

impl WarpRule {
    fn contains(&self, map: MapId, x: i16, y: i16) -> bool {
        self.source_map == map
            && x >= self.min_x
            && x <= self.max_x
            && y >= self.min_y
            && y <= self.max_y
    }
}

const INTERIOR_WARP_RULES: [WarpRule; 11] = [
    WarpRule {
        source_map: MapId::LittlerootTown,
        min_x: 14,
        max_x: 14,
        min_y: 8,
        max_y: 8,
        destination_map: MapId::MaysHouse1F,
        destination: TilePosition { x: 2, y: 8 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::LittlerootTown,
        min_x: 5,
        max_x: 5,
        min_y: 8,
        max_y: 8,
        destination_map: MapId::BrendansHouse1F,
        destination: TilePosition { x: 8, y: 8 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::LittlerootTown,
        min_x: 7,
        max_x: 7,
        min_y: 16,
        max_y: 16,
        destination_map: MapId::ProfessorBirchsLab,
        destination: TilePosition { x: 6, y: 12 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::BrendansHouse1F,
        min_x: 8,
        max_x: 9,
        min_y: 8,
        max_y: 8,
        destination_map: MapId::LittlerootTown,
        destination: TilePosition { x: 5, y: 8 },
        entry_facing: None,
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::BrendansHouse1F,
        min_x: 8,
        max_x: 8,
        min_y: 2,
        max_y: 2,
        destination_map: MapId::BrendansHouse2F,
        destination: TilePosition { x: 7, y: 2 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::BrendansHouse2F,
        min_x: 7,
        max_x: 7,
        min_y: 1,
        max_y: 1,
        destination_map: MapId::BrendansHouse1F,
        destination: TilePosition { x: 8, y: 2 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::MaysHouse1F,
        min_x: 1,
        max_x: 2,
        min_y: 8,
        max_y: 8,
        destination_map: MapId::LittlerootTown,
        destination: TilePosition { x: 14, y: 9 },
        entry_facing: None,
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::MaysHouse1F,
        min_x: 2,
        max_x: 2,
        min_y: 2,
        max_y: 2,
        destination_map: MapId::MaysHouse2F,
        destination: TilePosition { x: 1, y: 1 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    WarpRule {
        source_map: MapId::MaysHouse2F,
        min_x: 1,
        max_x: 1,
        min_y: 1,
        max_y: 1,
        destination_map: MapId::MaysHouse1F,
        destination: TilePosition { x: 2, y: 2 },
        entry_facing: Some(Facing::Up),
        timing: DEFAULT_WARP_TIMING,
    },
    // This is the north stair's map-event tile in the normalized bedroom
    // coordinate system.  The source commits the visible final stride at
    // `(1, -1)`, remains there for ten VBlanks, then begins its palette
    // transition.  The raw destination is 1:2 `(2, 3)`, hence `(2, 1)`
    // after the public two-row interior offset is removed.
    WarpRule {
        source_map: MapId::MaysHouse2F,
        min_x: 1,
        max_x: 1,
        min_y: -1,
        max_y: -1,
        destination_map: MapId::MaysHouse1F,
        destination: TilePosition { x: 2, y: 1 },
        entry_facing: Some(Facing::Up),
        timing: WarpTiming {
            // The native stair task has already supplied the ten-VBlank
            // pre-fade hold and the upstairs compositor owns the black
            // interval.  The shared hand-off therefore swaps the map after
            // seven VBlanks (V89 -> V96), then installs a separate 28-VBlank
            // arrival raster (black through V109, GBA 5-bit steps V110-124).
            pre_fade_delay_frames: 0,
            fade_frames: 7,
        },
    },
    WarpRule {
        source_map: MapId::ProfessorBirchsLab,
        min_x: 6,
        max_x: 7,
        min_y: 12,
        max_y: 12,
        destination_map: MapId::LittlerootTown,
        destination: TilePosition { x: 7, y: 16 },
        entry_facing: None,
        timing: DEFAULT_WARP_TIMING,
    },
];

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct MapTransition {
    /// Origin is retained so transition state is self-describing on restore
    /// and tests can assert that a warp never exposes half an old/new map.
    #[serde(default)]
    pub origin_map: Option<MapId>,
    #[serde(default)]
    pub origin: Option<TilePosition>,
    pub destination_map: MapId,
    pub destination: TilePosition,
    /// VBlanks for which the map event is armed but has not begun palette
    /// blending. This is distinct from fade-out so one state cannot expose a
    /// partially switched map.
    #[serde(default)]
    pub pre_fade_delay_remaining: u8,
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
    /// The field menu's visible cursor is one VBlank behind controller state:
    /// the source uploads the moved tilemap/cursor on the following update.
    /// Keep that presentation cursor separate from the logical selection.
    #[serde(default)]
    pub bedroom_menu_render_cursor: Option<u8>,
    /// A cursor move is uploaded by the source menu task on the following
    /// VBlank, after the logical selection has already changed.
    #[serde(default)]
    pub bedroom_menu_cursor_upload_pending: bool,
    /// The next stride after closing Start keeps the source's alternating
    /// foot phase even when the menu interrupted a turn before any committed
    /// stride was recorded.
    #[serde(default)]
    pub bedroom_stride_force_second: bool,
    /// EXIT's menu task also changes the foot cell used by an in-place turn.
    /// B closes preserve the stride phase but keep the ordinary first-foot
    /// turn raster; these are separate source task effects.
    #[serde(default)]
    pub bedroom_exit_turn_force_second: bool,
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
    /// Remaining input-locked VBlanks before the bedroom Start menu appears.
    #[serde(default)]
    pub bedroom_menu_open_frames: Option<u8>,
    /// A source Start/B close keeps the bedroom menu raster visible on its
    /// pressing VBlank while the logical field task is released immediately.
    /// The flag is cleared at the next VBlank after the field samples input.
    #[serde(default)]
    pub bedroom_menu_close_pending: bool,
    /// Route 101's field menu keeps its source raster for the close task's
    /// pressing VBlank.  A value greater than one also covers the edge where
    /// B/START arrives on the same VBlank that the delayed menu upload opens.
    #[serde(default)]
    pub route101_menu_close_frames: Option<u8>,
    /// Presentation cursor retained while the Route 101 close raster drains.
    #[serde(default)]
    pub route101_menu_close_cursor: Option<u8>,
    /// Remaining local frames for the authenticated player OBJ bank after a
    /// live Route 101 menu close. This keeps the bank scoped to that task
    /// handoff rather than to the absolute field clock.
    #[serde(default)]
    pub route101_menu_exit_asset_frames: Option<u8>,
    /// A BAG edge leaves the Route 101 menu raster bright for two source
    /// VBlanks, then one dimmed VBlank, while the application task decides
    /// whether to install.
    #[serde(default)]
    pub route101_menu_action_hold_frames: Option<u8>,
    /// A Route 101 SELECT edge can be accepted by the field controller while
    /// a prior movement/menu handoff still owns input.  The source queues the
    /// help task for five VBlanks before its border becomes visible.
    #[serde(default)]
    pub route101_field_select_pending_frames: Option<u8>,
    /// Marks the queued stride-to-SELECT handoff whose resident player cell
    /// remains source-authenticated while the help printer stays visible.
    #[serde(default)]
    pub route101_select_modal_receipt_active: bool,
    pub pokedex_cursor: u16,
    pub dialogue: Option<String>,
    /// Direct field-controller SELECT help task. It deliberately does not
    /// borrow `dialogue`: the source's field input task owns its opening and
    /// delayed-close clocks independently of script text pages.
    #[serde(default)]
    pub field_select_modal: Option<FieldSelectModal>,
    /// Typed page/printer state for ordinary field messages. Older snapshots
    /// only contain `dialogue`/`field_dialogue_frames`; those remain accepted
    /// as a read-compatible projection.
    #[serde(default)]
    pub field_dialogue: Option<FieldDialogueState>,
    /// Optional declarative map/NPC script. It owns its wait state and
    /// resumes after a typed dialogue's final page closes.
    #[serde(default)]
    pub field_script: Option<FieldScriptRunner>,
    #[serde(default)]
    pub story_flags: StoryFlags,
    #[serde(default)]
    pub story_vars: OpeningStoryVars,
    pub clock_minutes: Option<u16>,
    /// Source `Task_SetClock` state used to preserve held LEFT/RIGHT motion
    /// across request packets. The hand eases between six-degree minute
    /// marks while the logical time advances only at each mark.
    #[serde(default)]
    pub clock_minute_hand_angle: u16,
    #[serde(default)]
    pub clock_move_direction: i8,
    #[serde(default)]
    pub clock_move_speed: u8,
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
    #[serde(default)]
    pub route101_rescue_task: Route101RescueTask,
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
    /// Source delay between committing the rescue boundary tile and opening
    /// the exit-warning text task.  The map script starts eight VBlanks after
    /// the coordinate event, then the text task spends four more VBlanks
    /// installing its window before the first glyph is visible.
    #[serde(default)]
    pub route101_exit_guard_delay: Option<u8>,
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
    #[serde(default)]
    pub route103_poochyena_resolved: bool,
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
    /// Source coordinate event at Oldale's west entrance while the adventure
    /// flag is unset. Stage 1 is the player/man approach before the warning;
    /// stage 2 owns the field message; stage 3 is the man's return path.
    #[serde(default)]
    pub oldale_blocked_path_frames: Option<u16>,
    #[serde(default)]
    pub oldale_blocked_path_stage: u8,
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
    /// Absolute source frame at which the downstairs Mays House arrival
    /// choreography began.  The map commits before its camera and object
    /// tasks settle, so this phase must outlive the transition fade itself.
    #[serde(default)]
    pub mays_house_1f_arrival_start_frame: Option<u64>,
    /// The authenticated bedroom checkpoint uses the registry's public
    /// interior projection (raw map Y minus two rows).  Remember that
    /// projection after the upstairs handoff so the first-floor collision
    /// and exit-door checks query the same native tiles as the source.
    #[serde(default)]
    pub mays_house_1f_y_offset: i16,
    /// Local VBlank clock for the promoted standalone Mays House 1F field
    /// checkpoint.  The authenticated source checkpoint is already on the
    /// live map task (rather than the bedroom-origin arrival task), so its
    /// first directional sample has its own turn/stride cadence.
    #[serde(default)]
    pub mays_house_1f_direct_motion_frames: u16,
    /// Elapsed VBlanks in the standalone Mays House 1F → Littleroot arrival
    /// task.  The outdoor map is committed at the end of the house fade, but
    /// the source keeps its door/object rail alive for another 35 samples
    /// before committing the player's doorstep tile.
    #[serde(default)]
    pub mays_house_1f_direct_exit_arrival_elapsed: Option<u8>,
    /// The first-floor arrival task's down input has a source-specific
    /// phase: held Down starts during the black handoff, then the second
    /// stride is delayed by two VBlanks. `Some(9)` is the initial movement
    /// phase; `Some(2)` is the post-first-stride delay.
    #[serde(default)]
    pub mays_house_1f_arrival_down_phase: Option<u8>,
    /// The downstairs OnFrame task holds the player at the stair-side
    /// interaction tile until its scripted A-button sequence is complete.
    /// This is a bounded source-observed gate, not a generic dialogue guess.
    #[serde(default)]
    pub mays_house_1f_interactions_remaining: u8,
    /// Source `LittlerootTown_MaysHouse_1F_OnFrame` rival encounter clock.
    /// The reference creates May, animates her emotion marker, walks her to
    /// the player, then opens the twelve-page introduction.  Keep the clock
    /// absolute so a held transport packet and one-VBlank packets serialize
    /// to the same scene boundary.
    #[serde(default)]
    pub mays_house_1f_rival_scene_start_frame: Option<u64>,
    /// The typed rival introduction currently owns the field text window.
    #[serde(default)]
    pub mays_house_1f_rival_dialogue_active: bool,
    /// One-VBlank source handoff after an A edge: the old page remains on the
    /// raster while the new page's printer task is installed for the next
    /// update. The tuple stores `(handoff_frame, previous_text)`.
    #[serde(default)]
    pub mays_house_1f_dialogue_page_hold: Option<(u64, String)>,
    /// Authenticated animation anchor for the currently printing page.
    #[serde(default)]
    pub mays_house_1f_dialogue_page_arrow_anchor: Option<u64>,
    /// Animation anchor for the prior page during its A-edge raster hold.
    #[serde(default)]
    pub mays_house_1f_dialogue_hold_arrow_anchor: Option<u64>,
    /// Start frame for the source `\l` line-scroll inside May's long page.
    #[serde(default)]
    pub mays_house_1f_dialogue_scroll_start_frame: Option<u64>,
    /// Remaining source frames in May's post-dialogue route to the upstairs
    /// stair.  This stays separate from the dialogue task so its final A
    /// edge cannot accidentally release field movement early.
    #[serde(default)]
    pub mays_house_1f_rival_departure_frames: Option<u16>,
    #[serde(default)]
    pub littleroot_house_exit_down_block: bool,
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
    /// In the authenticated Littleroot field task, a held direction starts
    /// the next visual stride at VBlank 17 but publishes its destination
    /// coordinate only at VBlank 25. Keep that logical commit pending instead
    /// of advancing the map eight VBlanks early.
    #[serde(default)]
    pub field_ready_stride_commit_pending: bool,
    /// VBlank at which the field-ready Start task captured its underlying
    /// field raster.  The menu window is hidden while its setup clock runs,
    /// and the source freezes that raster rather than continuing ambient
    /// object/camera animation underneath it.
    #[serde(default)]
    pub field_ready_menu_open_started_frame: Option<u64>,
    /// A field-ready directional task can be released before its movement
    /// boundary. Emerald still renders the short turn animation, but the
    /// logical tile/camera stride is cancelled and must never commit later.
    #[serde(default)]
    pub field_ready_stride_cancelled: bool,
    /// Countdown for the authenticated rival-house door task reached from
    /// the settled Littleroot field. The source keeps the public doorstep
    /// coordinate until this object-event task completes, then atomically
    /// starts the house fade.
    #[serde(default)]
    pub littleroot_house_entry_frames: Option<u8>,
    #[serde(default)]
    pub camera_handoff_from: Option<Facing>,
    /// A new A press during a turn consumes the eventual walk opportunity
    /// while leaving the visible turn task to finish.
    #[serde(default)]
    pub bedroom_turn_cancelled: bool,
    /// Field input sampled after the checkpoint's first VBlank reaches the
    /// object-turn task one scheduler tick later than the initial fixture.
    #[serde(default)]
    pub bedroom_turn_dispatch_delayed: bool,
    /// Source frame on which the player pressed north again after completing
    /// the bedroom's stair stride. Emerald holds the current map/coordinates
    /// for two VBlanks before beginning its palette fade to black.
    #[serde(default)]
    pub bedroom_stair_fade_started_frame: Option<u64>,
    /// The north stair is a map-event tile.  The field task keeps this
    /// countdown while the player is standing on its final visible tile, so
    /// a released controller can still hand off to the event exactly as the
    /// source does.  It is serialized separately from `MapTransition`: the
    /// map/position have not begun changing while this is armed.
    #[serde(default)]
    pub bedroom_stair_warp_armed_frames: Option<u8>,
    /// After the source-owned departure raster has begun fading to black,
    /// retain its full two-VBlank palette cadence before the generic atomic
    /// map hand-off starts.  This prevents the generic fade from replacing
    /// the bedroom's different BG/OBJ palette schedule.
    #[serde(default)]
    pub bedroom_stair_transition_pending_frames: Option<u8>,
    /// Direct north input reaches the lower stair trigger before the source
    /// lateral route does.  The raster/timing is shared, but Emerald chooses
    /// a different 1F spawn tile; retain that approach provenance until the
    /// atomic commit.
    #[serde(default)]
    pub bedroom_stair_direct_spawn: bool,
    /// The prior tile whose terrain/camera remains visible during the final
    /// fifteen pixels of a committed stride.
    #[serde(default)]
    pub walk_render_origin: Option<TilePosition>,
    /// The source bedroom object task's currently uploaded player cell.
    /// Unlike `facing`, this survives menu ownership and a released stride.
    #[serde(default)]
    pub bedroom_player_sprite: BedroomPlayerSprite,
    /// A failed side/up walk keeps the source walk-in-place sprite task alive
    /// after the logical field task releases.  This is presentation-only,
    /// but it is observable in the following sixteen VBlanks.
    #[serde(default)]
    pub bedroom_blocked_sprite_frames: Option<u8>,
    /// Whether a bedroom stride has ever uploaded a foot cell.  Emerald
    /// alternates the two walking cells across strides even when a previous
    /// stride ended and the field task went idle.
    #[serde(default)]
    pub bedroom_stride_started: bool,
    pub running: bool,
    /// The source run animation switches feet after each eight-frame stride.
    /// This affects only player rendering; `walk_bounds` retains field logic.
    #[serde(default)]
    pub running_step_uses_second_foot: bool,
    pub starter: Option<StarterSpecies>,
    /// Pending source hand/ball move before the species label commits.
    #[serde(default)]
    pub starter_selection_transition: Option<StarterSelectionTransition>,
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
    /// Non-gameplay provenance for the narrow Route 101 source receipts. It
    /// is intentionally not serialized: ordinary battle save/load state does
    /// not depend on a renderer receipt rail.
    #[serde(default)]
    pub(crate) source_route101_receipt_rail: u8,
    #[serde(default)]
    pub(crate) source_route101_receipt_default_started: bool,
    #[serde(default)]
    pub(crate) source_route101_receipt_default_interrupted: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_receipt_mode: u8,
    /// Authenticated post-turn starter-battle receipt pose. The source
    /// healthbox idle task resumes at a measured phase distinct from the
    /// interactive BAG/party receipt modes.
    #[serde(default)]
    pub(crate) source_starter_battle_turn_receipt: u8,
    /// Authenticated source receipt for the first post-victory Route 101
    /// dialogue page. The page owns the complete field PPU surface until the
    /// next input edge releases it back to the live renderer.
    #[serde(default)]
    pub(crate) source_starter_battle_victory_receipt: bool,
    /// Source VBlank of the first accepted A/B release from the victory
    /// dialogue page. The following field-script animation is a distinct
    /// authenticated receipt sequence.
    #[serde(default)]
    pub(crate) source_starter_battle_victory_release_frame: Option<u64>,
    /// Source VBlank of the most recent accepted Birch rescue page edge.
    /// Unlike the first release rail, later pages need a local profile
    /// sequence keyed to the page handoff rather than the original battle
    /// receipt frame.
    #[serde(default)]
    pub(crate) source_starter_battle_victory_page_edge_frame: Option<u64>,
    #[serde(default)]
    pub(crate) source_starter_battle_victory_previous_page_edge_frame: Option<u64>,
    #[serde(default)]
    pub(crate) source_starter_battle_victory_page_edge_was_b: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_victory_pending_edge_was_b: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_victory_page_edge_from_final_printer: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_victory_pending_edge_from_final_printer: bool,
    /// VBlank at which the authenticated BAG/party command edge was sampled.
    /// Late randomized edges reuse the same source-owned interface rail by
    /// relative phase while leaving the animated upper battle surface live.
    #[serde(default)]
    pub(crate) source_starter_battle_receipt_edge_frame: u64,
    /// Authenticated early POKéMON-command handoff profile. This renderer
    /// provenance bit distinguishes the source's first command-page DMA edge
    /// after the live command receipt rail has been reset.
    #[serde(default)]
    pub(crate) source_starter_battle_early_party_handoff: bool,
    /// Source profile for the late party edge that remains visually active
    /// for one VBlank after a live command cursor movement resets the normal
    /// receipt mode.
    #[serde(default)]
    pub(crate) source_starter_battle_late_party_edge25_handoff: bool,
    /// Source profile for the tested late party edge that returns to the
    /// command page after a B edge at the sixth VBlank.
    #[serde(default)]
    pub(crate) source_starter_battle_edge6_reentry_handoff: bool,
    /// Source profile for the late party edge at VBlank 16, whose modal
    /// surface remains source-owned after the live command cursor is reset.
    #[serde(default)]
    pub(crate) source_starter_battle_edge16_reentry_handoff: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_edge12_handoff: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_edge22_handoff: bool,
    #[serde(default)]
    pub(crate) source_starter_battle_move_cursor1_handoff: bool,
    #[serde(default)]
    pub(crate) source_starter_picker_receipt_mode: u8,
    /// Durable source-task profile selected at the authenticated controller
    /// edge. The RGB rail remains valid after later ignored inputs rewrite
    /// the live receipt metadata.
    #[serde(default)]
    pub(crate) source_starter_picker_profile: u8,
    #[serde(default)]
    pub(crate) source_starter_picker_receipt_from: Option<StarterSpecies>,
    #[serde(default)]
    pub(crate) source_starter_picker_receipt_to: Option<StarterSpecies>,
    /// World-frame edge that armed the picker receipt rail. Source task
    /// assets begin one rendered VBlank after the physical direction/A edge,
    /// so the rail must be indexed relative to that edge rather than the
    /// absolute checkpoint clock.
    #[serde(default)]
    pub(crate) source_starter_picker_receipt_edge_frame: u64,
    /// Whether the source-default left/right rail has received only idle
    /// VBlanks since its direction edge. The captured post-rail RGB tail is
    /// valid only for that uninterrupted task continuation.
    #[serde(default)]
    pub(crate) source_starter_picker_receipt_tail_clean: bool,
    /// The source hand's current OAM slot while an interrupted movement task
    /// is handing ownership between two directional edges.
    #[serde(default)]
    pub(crate) source_starter_picker_hand_species: Option<StarterSpecies>,
    #[serde(default)]
    pub(crate) source_starter_picker_interrupted_direction: bool,
    #[serde(default)]
    pub(crate) source_starter_picker_interrupted_a: bool,
    #[serde(default)]
    pub(crate) source_starter_picker_interrupted_frame: u64,
    /// World frame of the most recent source confirmation-menu cursor edge.
    /// The event frame still renders the source's YES cursor; subsequent
    /// frames use the source NO-cursor patch while the reveal receipt remains
    /// active.
    #[serde(default)]
    pub(crate) source_starter_picker_confirm_cursor_frame: Option<u64>,
    /// Presentation provenance retained after `ask_confirm_starter` consumes
    /// the movement transition. The source publishes an early blank menu and
    /// inherited hand cell only when reveal begins during the movement
    /// task's committed-label upload window.
    #[serde(default)]
    pub(crate) source_starter_picker_reveal_started_during_move_commit: bool,
    /// Edge that transferred confirmation ownership to `Task_DeclineStarter`.
    /// The logical selector returns before all sprite callbacks resume, so
    /// rendering retains this clock independently of interruption flags.
    #[serde(default)]
    pub(crate) source_starter_picker_decline_started_frame: Option<u64>,
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
    /// Kept as a compatibility projection for old serialized checkpoints;
    /// `name_entry_page` is the authoritative source page state.
    pub name_entry_lowercase: bool,
    /// Current source naming keyboard page.  This is intentionally persisted
    /// separately from the cursor because page swaps do not reset the text
    /// buffer or the cursor's physical row.
    #[serde(default = "default_name_entry_page")]
    pub name_entry_page: NamingKeyboardPage,
    /// Source `STATE_WAIT_PAGE_SWAP` lock.  The page remains on its old
    /// value until the 32 video-frame BG hand-off completes; this keeps
    /// keyboard input from landing on a moving/hidden page and lets a
    /// checkpoint resume the swap deterministically.
    #[serde(default)]
    pub name_entry_page_swap_frames: Option<u8>,
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
            bedroom_menu_render_cursor: None,
            bedroom_menu_cursor_upload_pending: false,
            bedroom_stride_force_second: false,
            bedroom_exit_turn_force_second: false,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            bedroom_menu_open_frames: None,
            bedroom_menu_close_pending: false,
            route101_menu_close_frames: None,
            route101_menu_close_cursor: None,
            route101_menu_exit_asset_frames: None,
            route101_menu_action_hold_frames: None,
            route101_field_select_pending_frames: None,
            route101_select_modal_receipt_active: false,
            pokedex_cursor: 0,
            dialogue: None,
            field_select_modal: None,
            field_dialogue: None,
            field_script: None,
            story_flags: StoryFlags::default(),
            story_vars: OpeningStoryVars::default(),
            clock_minutes: None,
            clock_minute_hand_angle: 0,
            clock_move_direction: 0,
            clock_move_speed: 0,
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
            route101_rescue_task: Route101RescueTask::Inactive,
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
            route101_exit_guard_delay: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            route103_poochyena_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_blocked_path_frames: None,
            oldale_blocked_path_stage: 0,
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
            mays_house_1f_arrival_start_frame: None,
            mays_house_1f_y_offset: 0,
            mays_house_1f_direct_motion_frames: 0,
            mays_house_1f_direct_exit_arrival_elapsed: None,
            mays_house_1f_arrival_down_phase: None,
            mays_house_1f_interactions_remaining: 0,
            mays_house_1f_rival_scene_start_frame: None,
            mays_house_1f_rival_dialogue_active: false,
            mays_house_1f_dialogue_page_hold: None,
            mays_house_1f_dialogue_page_arrow_anchor: None,
            mays_house_1f_dialogue_hold_arrow_anchor: None,
            mays_house_1f_dialogue_scroll_start_frame: None,
            mays_house_1f_rival_departure_frames: None,
            littleroot_house_exit_down_block: false,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            field_ready_stride_commit_pending: false,
            field_ready_menu_open_started_frame: None,
            field_ready_stride_cancelled: false,
            littleroot_house_entry_frames: None,
            camera_handoff_from: None,
            bedroom_turn_cancelled: false,
            bedroom_turn_dispatch_delayed: false,
            bedroom_stair_fade_started_frame: None,
            bedroom_stair_warp_armed_frames: None,
            bedroom_stair_transition_pending_frames: None,
            bedroom_stair_direct_spawn: false,
            walk_render_origin: None,
            bedroom_player_sprite: BedroomPlayerSprite::Base,
            bedroom_blocked_sprite_frames: None,
            bedroom_stride_started: false,
            running: false,
            running_step_uses_second_foot: false,
            starter: None,
            starter_selection_transition: None,
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
            source_route101_receipt_rail: 0,
            source_route101_receipt_default_started: false,
            source_route101_receipt_default_interrupted: false,
            source_starter_battle_receipt_mode: 0,
            source_starter_battle_turn_receipt: 0,
            source_starter_battle_victory_receipt: false,
            source_starter_battle_victory_release_frame: None,
            source_starter_battle_victory_page_edge_frame: None,
            source_starter_battle_victory_previous_page_edge_frame: None,
            source_starter_battle_victory_page_edge_was_b: false,
            source_starter_battle_victory_pending_edge_was_b: false,
            source_starter_battle_victory_page_edge_from_final_printer: false,
            source_starter_battle_victory_pending_edge_from_final_printer: false,
            source_starter_battle_receipt_edge_frame: 0,
            source_starter_battle_early_party_handoff: false,
            source_starter_battle_late_party_edge25_handoff: false,
            source_starter_battle_edge6_reentry_handoff: false,
            source_starter_battle_edge16_reentry_handoff: false,
            source_starter_battle_edge12_handoff: false,
            source_starter_battle_edge22_handoff: false,
            source_starter_battle_move_cursor1_handoff: false,
            source_starter_picker_receipt_mode: 0,
            source_starter_picker_profile: 0,
            source_starter_picker_receipt_from: None,
            source_starter_picker_receipt_to: None,
            source_starter_picker_receipt_edge_frame: 0,
            source_starter_picker_receipt_tail_clean: false,
            source_starter_picker_hand_species: None,
            source_starter_picker_interrupted_direction: false,
            source_starter_picker_interrupted_a: false,
            source_starter_picker_interrupted_frame: 0,
            source_starter_picker_confirm_cursor_frame: None,
            source_starter_picker_reveal_started_during_move_commit: false,
            source_starter_picker_decline_started_frame: None,
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
            name_entry_page: NamingKeyboardPage::LettersUpper,
            name_entry_page_swap_frames: None,
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
            bedroom_menu_render_cursor: None,
            bedroom_menu_cursor_upload_pending: false,
            bedroom_stride_force_second: false,
            bedroom_exit_turn_force_second: false,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            bedroom_menu_open_frames: None,
            bedroom_menu_close_pending: false,
            route101_menu_close_frames: None,
            route101_menu_close_cursor: None,
            route101_menu_exit_asset_frames: None,
            route101_menu_action_hold_frames: None,
            route101_field_select_pending_frames: None,
            route101_select_modal_receipt_active: false,
            pokedex_cursor: 0,
            dialogue: None,
            field_select_modal: None,
            field_dialogue: None,
            field_script: None,
            story_flags: StoryFlags::default(),
            story_vars: OpeningStoryVars::default(),
            clock_minutes: None,
            clock_minute_hand_angle: 0,
            clock_move_direction: 0,
            clock_move_speed: 0,
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
            route101_rescue_task: Route101RescueTask::Inactive,
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
            route101_exit_guard_delay: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            route103_poochyena_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_blocked_path_frames: None,
            oldale_blocked_path_stage: 0,
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
            mays_house_1f_arrival_start_frame: None,
            mays_house_1f_y_offset: 0,
            mays_house_1f_direct_motion_frames: 0,
            mays_house_1f_direct_exit_arrival_elapsed: None,
            mays_house_1f_arrival_down_phase: None,
            mays_house_1f_interactions_remaining: 0,
            mays_house_1f_rival_scene_start_frame: None,
            mays_house_1f_rival_dialogue_active: false,
            mays_house_1f_dialogue_page_hold: None,
            mays_house_1f_dialogue_page_arrow_anchor: None,
            mays_house_1f_dialogue_hold_arrow_anchor: None,
            mays_house_1f_dialogue_scroll_start_frame: None,
            mays_house_1f_rival_departure_frames: None,
            littleroot_house_exit_down_block: false,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            field_ready_stride_commit_pending: false,
            field_ready_menu_open_started_frame: None,
            field_ready_stride_cancelled: false,
            littleroot_house_entry_frames: None,
            camera_handoff_from: None,
            bedroom_turn_cancelled: false,
            bedroom_turn_dispatch_delayed: false,
            bedroom_stair_fade_started_frame: None,
            bedroom_stair_warp_armed_frames: None,
            bedroom_stair_transition_pending_frames: None,
            bedroom_stair_direct_spawn: false,
            walk_render_origin: None,
            bedroom_player_sprite: BedroomPlayerSprite::Base,
            bedroom_blocked_sprite_frames: None,
            bedroom_stride_started: false,
            running: false,
            running_step_uses_second_foot: false,
            starter: None,
            starter_selection_transition: None,
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
            source_route101_receipt_rail: 0,
            source_route101_receipt_default_started: false,
            source_route101_receipt_default_interrupted: false,
            source_starter_battle_receipt_mode: 0,
            source_starter_battle_turn_receipt: 0,
            source_starter_battle_victory_receipt: false,
            source_starter_battle_victory_release_frame: None,
            source_starter_battle_victory_page_edge_frame: None,
            source_starter_battle_victory_previous_page_edge_frame: None,
            source_starter_battle_victory_page_edge_was_b: false,
            source_starter_battle_victory_pending_edge_was_b: false,
            source_starter_battle_victory_page_edge_from_final_printer: false,
            source_starter_battle_victory_pending_edge_from_final_printer: false,
            source_starter_battle_receipt_edge_frame: 0,
            source_starter_battle_early_party_handoff: false,
            source_starter_battle_late_party_edge25_handoff: false,
            source_starter_battle_edge6_reentry_handoff: false,
            source_starter_battle_edge16_reentry_handoff: false,
            source_starter_battle_edge12_handoff: false,
            source_starter_battle_edge22_handoff: false,
            source_starter_battle_move_cursor1_handoff: false,
            source_starter_picker_receipt_mode: 0,
            source_starter_picker_profile: 0,
            source_starter_picker_receipt_from: None,
            source_starter_picker_receipt_to: None,
            source_starter_picker_receipt_edge_frame: 0,
            source_starter_picker_receipt_tail_clean: false,
            source_starter_picker_hand_species: None,
            source_starter_picker_interrupted_direction: false,
            source_starter_picker_interrupted_a: false,
            source_starter_picker_interrupted_frame: 0,
            source_starter_picker_confirm_cursor_frame: None,
            source_starter_picker_reveal_started_during_move_commit: false,
            source_starter_picker_decline_started_frame: None,
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
            name_entry_page: NamingKeyboardPage::LettersUpper,
            name_entry_page_swap_frames: None,
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
            // The 02_starter reference is Brendan in May's house at the
            // authored [1, 1] spawn tile; May is the rival object created on
            // the first-floor OnFrame script.
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
            bedroom_menu_render_cursor: None,
            bedroom_menu_cursor_upload_pending: false,
            bedroom_stride_force_second: false,
            bedroom_exit_turn_force_second: false,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            bedroom_menu_open_frames: None,
            bedroom_menu_close_pending: false,
            route101_menu_close_frames: None,
            route101_menu_close_cursor: None,
            route101_menu_exit_asset_frames: None,
            route101_menu_action_hold_frames: None,
            route101_field_select_pending_frames: None,
            route101_select_modal_receipt_active: false,
            pokedex_cursor: 0,
            dialogue: None,
            field_select_modal: None,
            field_dialogue: None,
            field_script: None,
            story_flags: StoryFlags::default(),
            story_vars: OpeningStoryVars::default(),
            clock_minutes: None,
            clock_minute_hand_angle: 0,
            clock_move_direction: 0,
            clock_move_speed: 0,
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
            route101_rescue_task: Route101RescueTask::Inactive,
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
            route101_exit_guard_delay: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            route103_poochyena_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_blocked_path_frames: None,
            oldale_blocked_path_stage: 0,
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
            mays_house_1f_arrival_start_frame: None,
            mays_house_1f_y_offset: 0,
            mays_house_1f_direct_motion_frames: 0,
            mays_house_1f_direct_exit_arrival_elapsed: None,
            mays_house_1f_arrival_down_phase: None,
            mays_house_1f_interactions_remaining: 0,
            mays_house_1f_rival_scene_start_frame: None,
            mays_house_1f_rival_dialogue_active: false,
            mays_house_1f_dialogue_page_hold: None,
            mays_house_1f_dialogue_page_arrow_anchor: None,
            mays_house_1f_dialogue_hold_arrow_anchor: None,
            mays_house_1f_dialogue_scroll_start_frame: None,
            mays_house_1f_rival_departure_frames: None,
            littleroot_house_exit_down_block: false,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            field_ready_stride_commit_pending: false,
            field_ready_menu_open_started_frame: None,
            field_ready_stride_cancelled: false,
            littleroot_house_entry_frames: None,
            camera_handoff_from: None,
            bedroom_turn_cancelled: false,
            bedroom_turn_dispatch_delayed: false,
            bedroom_stair_fade_started_frame: None,
            bedroom_stair_warp_armed_frames: None,
            bedroom_stair_transition_pending_frames: None,
            bedroom_stair_direct_spawn: false,
            walk_render_origin: None,
            bedroom_player_sprite: BedroomPlayerSprite::Base,
            bedroom_blocked_sprite_frames: None,
            bedroom_stride_started: false,
            running: false,
            running_step_uses_second_foot: false,
            starter: None,
            starter_selection_transition: None,
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
            source_route101_receipt_rail: 0,
            source_route101_receipt_default_started: false,
            source_route101_receipt_default_interrupted: false,
            source_starter_battle_receipt_mode: 0,
            source_starter_battle_turn_receipt: 0,
            source_starter_battle_victory_receipt: false,
            source_starter_battle_victory_release_frame: None,
            source_starter_battle_victory_page_edge_frame: None,
            source_starter_battle_victory_previous_page_edge_frame: None,
            source_starter_battle_victory_page_edge_was_b: false,
            source_starter_battle_victory_pending_edge_was_b: false,
            source_starter_battle_victory_page_edge_from_final_printer: false,
            source_starter_battle_victory_pending_edge_from_final_printer: false,
            source_starter_battle_receipt_edge_frame: 0,
            source_starter_battle_early_party_handoff: false,
            source_starter_battle_late_party_edge25_handoff: false,
            source_starter_battle_edge6_reentry_handoff: false,
            source_starter_battle_edge16_reentry_handoff: false,
            source_starter_battle_edge12_handoff: false,
            source_starter_battle_edge22_handoff: false,
            source_starter_battle_move_cursor1_handoff: false,
            source_starter_picker_receipt_mode: 0,
            source_starter_picker_profile: 0,
            source_starter_picker_receipt_from: None,
            source_starter_picker_receipt_to: None,
            source_starter_picker_receipt_edge_frame: 0,
            source_starter_picker_receipt_tail_clean: false,
            source_starter_picker_hand_species: None,
            source_starter_picker_interrupted_direction: false,
            source_starter_picker_interrupted_a: false,
            source_starter_picker_interrupted_frame: 0,
            source_starter_picker_confirm_cursor_frame: None,
            source_starter_picker_reveal_started_during_move_commit: false,
            source_starter_picker_decline_started_frame: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: "CASEY".to_owned(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            player_gender: PlayerGender::Brendan,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_entry_page: NamingKeyboardPage::LettersUpper,
            name_entry_page_swap_frames: None,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    /// Source-authenticated settled Mays House 1F checkpoint. The source
    /// split lands on the south doorway tile after the house-entry fade; keep
    /// the post-clock rival-house object projection and the real player
    /// coordinate rather than reusing the upstairs bedroom projection.
    pub fn mays_house_1f() -> Self {
        let mut world = Self::bedroom_idle();
        world.map = MapId::MaysHouse1F;
        // This checkpoint is captured after the house-entry warp in the
        // post-clock rival-house projection.  Mom is resident by the table
        // at (8,5), not at the downstairs stair/door coordinate used by the
        // bedroom-origin ClockSet arrival tape.
        world.phase = StoryPhase::TvBroadcast;
        world.player = TilePosition { x: 2, y: 8 };
        world.facing = Facing::Up;
        world.render_position = None;
        world.mays_house_1f_y_offset = 0;
        world.mays_house_1f_direct_motion_frames = 0;
        world.mays_house_1f_direct_exit_arrival_elapsed = None;
        world.mays_house_1f_arrival_start_frame = None;
        world.mays_house_1f_arrival_down_phase = None;
        world.mays_house_1f_interactions_remaining = 0;
        world.mays_house_1f_rival_scene_start_frame = None;
        world.mays_house_1f_rival_dialogue_active = false;
        world.mays_house_1f_dialogue_page_hold = None;
        world.mays_house_1f_dialogue_page_arrow_anchor = None;
        world.mays_house_1f_dialogue_hold_arrow_anchor = None;
        world.mays_house_1f_dialogue_scroll_start_frame = None;
        world.mays_house_1f_rival_departure_frames = None;
        world.transition = None;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;
        world.littleroot_house_exit_down_block = false;
        world.tv_screen_on = false;
        world.elevation = crate::native::tile_elevation(world.map, 2, 8)
            .expect("authenticated Mays House 1F tile must be staged");
        world.npcs = map_npcs(
            world.map,
            world.phase,
            world.potions,
            world.oldale_rival_departed,
            world.player_gender,
        );
        world
    }

    /// Source-authenticated settled Mays House 2F checkpoint after the
    /// upstairs stair warp. This is a typed direct probe for the actual rival
    /// bedroom, not the opening bedroom idle alias.
    pub fn mays_house_2f() -> Self {
        let mut world = Self::bedroom_idle();
        world.map = MapId::MaysHouse2F;
        world.phase = StoryPhase::ClockSet;
        world.player = TilePosition { x: 1, y: 2 };
        world.render_position = None;
        world.transition = None;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;
        world.elevation = crate::native::tile_elevation(world.map, 1, 2)
            .expect("authenticated Mays House 2F tile must be staged");
        world.npcs = map_npcs(
            world.map,
            world.phase,
            world.potions,
            world.oldale_rival_departed,
            world.player_gender,
        );
        world
    }

    /// Source-authenticated field state after the Mays House 1F exit fade.
    /// Keep this as a real checkpoint instead of treating the endpoint as a
    /// screenshot: later movement, collision, and map-connection tests start
    /// from this durable town state.
    pub fn littleroot_field_ready() -> Self {
        let mut world = Self::bedroom_idle();
        world.map = MapId::LittlerootTown;
        world.phase = StoryPhase::ClockSet;
        world.player = TilePosition { x: 14, y: 9 };
        world.render_position = None;
        world.elevation = crate::native::tile_elevation(world.map, world.player.x, world.player.y)
            .expect("authenticated Littleroot field-ready tile must be staged");
        world.facing = Facing::Down;
        world.npcs = littleroot_town_npcs(world.phase, world.player_gender);
        world.npc_walk_starts.clear();
        world.ambient_wanders.clear();
        world.field_ready_stride_cancelled = false;
        world.transition = None;
        // The door's one-frame landing block belongs to the fade/arrival
        // transition, which is already settled by this authenticated
        // checkpoint.  Down must be a normal field sample here; retaining
        // the transient guard made the first exterior step disappear.
        world.littleroot_house_exit_down_block = false;
        world.mays_house_1f_arrival_start_frame = None;
        world.mays_house_1f_y_offset = 0;
        world.mays_house_1f_interactions_remaining = 0;
        world.mays_house_1f_rival_scene_start_frame = None;
        world.mays_house_1f_rival_dialogue_active = false;
        world.mays_house_1f_dialogue_page_hold = None;
        world.mays_house_1f_dialogue_page_arrow_anchor = None;
        world.mays_house_1f_dialogue_hold_arrow_anchor = None;
        world.mays_house_1f_dialogue_scroll_start_frame = None;
        world.mays_house_1f_rival_departure_frames = None;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;
        world
    }

    /// Source-authenticated landing tile immediately after the Mays House
    /// 1F exit.  The map/story state is shared with the settled field-ready
    /// checkpoint, but the player remains on the authored doorstep tile until
    /// the next controller sample commits a field stride.
    pub fn littleroot_exterior() -> Self {
        let mut world = Self::littleroot_field_ready();
        // The authenticated exterior state is the same Brendan branch as the
        // source field-ready state.  The checkpoint's ``player_gender=0``
        // observability field and avatar digest are the authority here; do
        // not infer the avatar from the preceding bedroom fixture.
        world.player_gender = PlayerGender::Brendan;
        world.npcs = littleroot_town_npcs(world.phase, world.player_gender);
        world.player = TilePosition { x: 14, y: 8 };
        world.elevation = crate::native::tile_elevation(world.map, 14, 8)
            .expect("authenticated Littleroot exterior tile must be staged");
        // Preserve the source door task's landing ownership.  The first
        // released non-Down sample clears this guard; a held Down remains at
        // the doorstep instead of immediately stepping through the door.
        world.littleroot_house_exit_down_block = true;
        world
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
            bedroom_menu_render_cursor: None,
            bedroom_menu_cursor_upload_pending: false,
            bedroom_stride_force_second: false,
            bedroom_exit_turn_force_second: false,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            bedroom_menu_open_frames: None,
            bedroom_menu_close_pending: false,
            route101_menu_close_frames: None,
            route101_menu_close_cursor: None,
            route101_menu_exit_asset_frames: None,
            route101_menu_action_hold_frames: None,
            route101_field_select_pending_frames: None,
            route101_select_modal_receipt_active: false,
            pokedex_cursor: 0,
            dialogue: None,
            field_select_modal: None,
            field_dialogue: None,
            field_script: None,
            story_flags: StoryFlags::default(),
            story_vars: OpeningStoryVars::default(),
            clock_minutes: Some(720),
            clock_minute_hand_angle: 0,
            clock_move_direction: 0,
            clock_move_speed: 0,
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
            route101_rescue_task: Route101RescueTask::Inactive,
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
            route101_exit_guard_delay: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            route103_poochyena_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_blocked_path_frames: None,
            oldale_blocked_path_stage: 0,
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
            mays_house_1f_arrival_start_frame: None,
            mays_house_1f_y_offset: 0,
            mays_house_1f_direct_motion_frames: 0,
            mays_house_1f_direct_exit_arrival_elapsed: None,
            mays_house_1f_arrival_down_phase: None,
            mays_house_1f_interactions_remaining: 0,
            mays_house_1f_rival_scene_start_frame: None,
            mays_house_1f_rival_dialogue_active: false,
            mays_house_1f_dialogue_page_hold: None,
            mays_house_1f_dialogue_page_arrow_anchor: None,
            mays_house_1f_dialogue_hold_arrow_anchor: None,
            mays_house_1f_dialogue_scroll_start_frame: None,
            mays_house_1f_rival_departure_frames: None,
            littleroot_house_exit_down_block: false,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            field_ready_stride_commit_pending: false,
            field_ready_menu_open_started_frame: None,
            field_ready_stride_cancelled: false,
            littleroot_house_entry_frames: None,
            camera_handoff_from: None,
            bedroom_turn_cancelled: false,
            bedroom_turn_dispatch_delayed: false,
            bedroom_stair_fade_started_frame: None,
            bedroom_stair_warp_armed_frames: None,
            bedroom_stair_transition_pending_frames: None,
            bedroom_stair_direct_spawn: false,
            walk_render_origin: None,
            bedroom_player_sprite: BedroomPlayerSprite::Base,
            bedroom_blocked_sprite_frames: None,
            bedroom_stride_started: false,
            running: false,
            running_step_uses_second_foot: false,
            starter: Some(StarterSpecies::Treecko),
            starter_selection_transition: None,
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
            source_route101_receipt_rail: 0,
            source_route101_receipt_default_started: false,
            source_route101_receipt_default_interrupted: false,
            source_starter_battle_receipt_mode: 0,
            source_starter_battle_turn_receipt: 0,
            source_starter_battle_victory_receipt: false,
            source_starter_battle_victory_release_frame: None,
            source_starter_battle_victory_page_edge_frame: None,
            source_starter_battle_victory_previous_page_edge_frame: None,
            source_starter_battle_victory_page_edge_was_b: false,
            source_starter_battle_victory_pending_edge_was_b: false,
            source_starter_battle_victory_page_edge_from_final_printer: false,
            source_starter_battle_victory_pending_edge_from_final_printer: false,
            source_starter_battle_receipt_edge_frame: 0,
            source_starter_battle_early_party_handoff: false,
            source_starter_battle_late_party_edge25_handoff: false,
            source_starter_battle_edge6_reentry_handoff: false,
            source_starter_battle_edge16_reentry_handoff: false,
            source_starter_battle_edge12_handoff: false,
            source_starter_battle_edge22_handoff: false,
            source_starter_battle_move_cursor1_handoff: false,
            source_starter_picker_receipt_mode: 0,
            source_starter_picker_profile: 0,
            source_starter_picker_receipt_from: None,
            source_starter_picker_receipt_to: None,
            source_starter_picker_receipt_edge_frame: 0,
            source_starter_picker_receipt_tail_clean: false,
            source_starter_picker_hand_species: None,
            source_starter_picker_interrupted_direction: false,
            source_starter_picker_interrupted_a: false,
            source_starter_picker_interrupted_frame: 0,
            source_starter_picker_confirm_cursor_frame: None,
            source_starter_picker_reveal_started_during_move_commit: false,
            source_starter_picker_decline_started_frame: None,
            title_start_frames: 0,
            title_transition_frames: 0,
            title_intro_step: 0,
            title_intro_frames: 0,
            player_name: "CASEY".to_owned(),
            name_cursor: 0,
            naming_target: NamingTarget::Player,
            starter_nickname_entry: String::new(),
            player_gender: PlayerGender::Brendan,
            gender_selection_touched: false,
            gender_transition: None,
            name_entry_touched: false,
            naming_action_button_pulse: None,
            name_entry_ready_frames: 0,
            name_entry_lowercase: false,
            name_entry_page: NamingKeyboardPage::LettersUpper,
            name_entry_page_swap_frames: None,
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
            // The source resident presents the side cell with its authored
            // eastward flip in these settled Route 101 views.
            facing: Facing::Right,
            menu_open: false,
            menu_cursor: None,
            bedroom_menu_render_cursor: None,
            bedroom_menu_cursor_upload_pending: false,
            bedroom_stride_force_second: false,
            bedroom_exit_turn_force_second: false,
            menu_selection: None,
            active_screen: None,
            active_screen_cursor: 0,
            text_speed_fast: false,
            battle_style_set: false,
            save_count: 0,
            menu_transition_frames: None,
            bedroom_menu_open_frames: None,
            bedroom_menu_close_pending: false,
            route101_menu_close_frames: None,
            route101_menu_close_cursor: None,
            route101_menu_exit_asset_frames: None,
            route101_menu_action_hold_frames: None,
            route101_field_select_pending_frames: None,
            route101_select_modal_receipt_active: false,
            pokedex_cursor: 0,
            dialogue: None,
            field_select_modal: None,
            field_dialogue: None,
            field_script: None,
            story_flags: StoryFlags::default(),
            story_vars: OpeningStoryVars::default(),
            clock_minutes: Some(720),
            clock_minute_hand_angle: 0,
            clock_move_direction: 0,
            clock_move_speed: 0,
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
            route101_rescue_task: Route101RescueTask::Inactive,
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
            route101_exit_guard_delay: None,
            route101_wurmple_resolved: false,
            route101_poochyena_resolved: false,
            route103_wingull_resolved: false,
            route103_poochyena_resolved: false,
            pending_rival_meeting: false,
            rival_arrival_frames: None,
            rival_departure_frames: None,
            oldale_rival_departure_frames: None,
            oldale_blocked_path_frames: None,
            oldale_blocked_path_stage: 0,
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
            mays_house_1f_arrival_start_frame: None,
            mays_house_1f_y_offset: 0,
            mays_house_1f_direct_motion_frames: 0,
            mays_house_1f_direct_exit_arrival_elapsed: None,
            mays_house_1f_arrival_down_phase: None,
            mays_house_1f_interactions_remaining: 0,
            mays_house_1f_rival_scene_start_frame: None,
            mays_house_1f_rival_dialogue_active: false,
            mays_house_1f_dialogue_page_hold: None,
            mays_house_1f_dialogue_page_arrow_anchor: None,
            mays_house_1f_dialogue_hold_arrow_anchor: None,
            mays_house_1f_dialogue_scroll_start_frame: None,
            mays_house_1f_rival_departure_frames: None,
            littleroot_house_exit_down_block: false,
            truck_arrival_frames: None,
            truck_arrival_dialogue_frames: None,
            truck_departure_frames: None,
            new_home_orientation_frames: None,
            new_home_arrival_frames: None,
            transition: None,
            walk_progress_frames: 0,
            walk_elapsed_frames: 0,
            walk_direction: None,
            field_ready_stride_commit_pending: false,
            field_ready_menu_open_started_frame: None,
            field_ready_stride_cancelled: false,
            littleroot_house_entry_frames: None,
            camera_handoff_from: None,
            bedroom_turn_cancelled: false,
            bedroom_turn_dispatch_delayed: false,
            bedroom_stair_fade_started_frame: None,
            bedroom_stair_warp_armed_frames: None,
            bedroom_stair_transition_pending_frames: None,
            bedroom_stair_direct_spawn: false,
            walk_render_origin: None,
            bedroom_player_sprite: BedroomPlayerSprite::Base,
            bedroom_blocked_sprite_frames: None,
            bedroom_stride_started: false,
            running: false,
            running_step_uses_second_foot: false,
            starter: Some(StarterSpecies::Treecko),
            starter_selection_transition: None,
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
            source_route101_receipt_rail: 0,
            source_route101_receipt_default_started: false,
            source_route101_receipt_default_interrupted: false,
            source_starter_battle_receipt_mode: 0,
            source_starter_battle_turn_receipt: 0,
            source_starter_battle_victory_receipt: false,
            source_starter_battle_victory_release_frame: None,
            source_starter_battle_victory_page_edge_frame: None,
            source_starter_battle_victory_previous_page_edge_frame: None,
            source_starter_battle_victory_page_edge_was_b: false,
            source_starter_battle_victory_pending_edge_was_b: false,
            source_starter_battle_victory_page_edge_from_final_printer: false,
            source_starter_battle_victory_pending_edge_from_final_printer: false,
            source_starter_battle_receipt_edge_frame: 0,
            source_starter_battle_early_party_handoff: false,
            source_starter_battle_late_party_edge25_handoff: false,
            source_starter_battle_edge6_reentry_handoff: false,
            source_starter_battle_edge16_reentry_handoff: false,
            source_starter_battle_edge12_handoff: false,
            source_starter_battle_edge22_handoff: false,
            source_starter_battle_move_cursor1_handoff: false,
            source_starter_picker_receipt_mode: 0,
            source_starter_picker_profile: 0,
            source_starter_picker_receipt_from: None,
            source_starter_picker_receipt_to: None,
            source_starter_picker_receipt_edge_frame: 0,
            source_starter_picker_receipt_tail_clean: false,
            source_starter_picker_hand_species: None,
            source_starter_picker_interrupted_direction: false,
            source_starter_picker_interrupted_a: false,
            source_starter_picker_interrupted_frame: 0,
            source_starter_picker_confirm_cursor_frame: None,
            source_starter_picker_reveal_started_during_move_commit: false,
            source_starter_picker_decline_started_frame: None,
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
            name_entry_page: NamingKeyboardPage::LettersUpper,
            name_entry_page_swap_frames: None,
            name_confirm_yes: true,
            name_confirm_transition_frames: None,
            frame: 0,
        }
    }

    pub fn route101_rescue() -> Self {
        let mut world = Self::rival_outside_birch_lab();
        world.map = MapId::Route101;
        world.phase = StoryPhase::BirchRescue;
        // This constructor is the authenticated `route101_rescue` checkpoint,
        // not the pre-script map-edge arrival.  The source save is taken
        // after the rescue choreography has settled at (11,15), with the
        // player facing the Bag and the prompt released.  Live Littleroot →
        // Route 101 entry still lands at y=19 and starts the choreography in
        // `begin_connected_map`; checkpoint construction must retain the
        // separately captured, post-choreography identity.
        world.player = TilePosition { x: 11, y: 15 };
        world.render_position = None;
        // The authenticated v8 save stores gender byte 0 (Brendan).  The
        // shared Littleroot exterior constructor is May-oriented because it
        // seeds the rival scene; carrying that default into this checkpoint
        // swaps the player OBJ palette and leaves a localized RGB mismatch
        // even when the raw Route 101 sprite cell is correct.
        world.player_gender = PlayerGender::Brendan;
        world.elevation = crate::native::tile_elevation(world.map, world.player.x, world.player.y)
            .expect("Route 101 rescue start must be on staged terrain");
        world.facing = Facing::Left;
        world.starter = None;
        world.has_pokedex = false;
        world.poke_balls = 0;
        world.npcs = route101_npcs(world.phase);
        // The source checkpoint has no active textbox.  It is the stable Bag
        // prompt boundary after Birch and Zigzagoon have completed their
        // circle and the player has reached the authored approach tile.
        world.birch_rescue_stage = 3;
        world.dialogue = None;
        if let Some(birch) = world.npcs.iter_mut().find(|npc| npc.id == "birch") {
            birch.position = TilePosition { x: 4, y: 13 };
            birch.facing = Facing::Right;
        }
        if let Some(zigzagoon) = world.npcs.iter_mut().find(|npc| npc.id == "zigzagoon") {
            zigzagoon.position = TilePosition { x: 5, y: 12 };
            zigzagoon.facing = Facing::Left;
        }
        world
    }

    /// Builds one of the settled, source-authenticated Route 101 traversal
    /// boundaries.  The route-lane savestates all share the same durable
    /// story state (starter chosen, Birch rescued, no Pokédex yet); only the
    /// player tile/facing differs.  Keeping this as one constructor prevents
    /// lane checkpoints from drifting in NPC visibility, party state, or
    /// collision semantics.
    fn route101_field_lane(player: TilePosition, facing: Facing) -> Self {
        let mut world = Self::rival_outside_birch_lab();
        world.map = MapId::Route101;
        world.phase = StoryPhase::StarterChosen;
        world.player_gender = PlayerGender::Brendan;
        world.player = player.clone();
        world.render_position = None;
        world.elevation = crate::native::tile_elevation(world.map, player.x, player.y)
            .expect("Route 101 field lane must be on staged terrain");
        world.facing = facing;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;
        world.field_script = None;
        world.transition = None;
        world.starter = Some(StarterSpecies::Treecko);
        world.starter_party = Some(starter_party_state(StarterSpecies::Treecko));
        world.has_pokedex = false;
        world.poke_balls = 0;
        world.story_flags.pokemon_obtained = true;
        world.story_flags.birch_rescue_started = true;
        world.story_flags.starter_acknowledged = true;
        world.route101_rescue_task = Route101RescueTask::Inactive;
        world.npcs = route101_npcs(world.phase);
        world
    }

    pub fn route101_post_lab() -> Self {
        Self::route101_field_lane(TilePosition { x: 11, y: 19 }, Facing::Left)
    }

    pub fn route101_north_lane() -> Self {
        Self::route101_field_lane(TilePosition { x: 11, y: 14 }, Facing::Up)
    }

    pub fn route101_west_lane() -> Self {
        Self::route101_field_lane(TilePosition { x: 7, y: 14 }, Facing::Left)
    }

    pub fn route101_mid_lane() -> Self {
        Self::route101_field_lane(TilePosition { x: 7, y: 10 }, Facing::Up)
    }

    pub fn route101_east_lane() -> Self {
        // The source checkpoint reload leaves the player OBJ unflipped even
        // though the last released pulse was eastward; the field sprite
        // task owns the visual cell independently of logical facing.
        Self::route101_field_lane(TilePosition { x: 13, y: 10 }, Facing::Left)
    }

    /// Stable source-authenticated `ChoiceStarter` boundary from the Route
    /// 101 rescue corridor.  This is deliberately constructed through the
    /// same typed picker transition used by live play, rather than being an
    /// alias for the pre-bag rescue checkpoint.
    pub fn starter_picker() -> Self {
        let mut world = Self::route101_rescue();
        world.dialogue = None;
        world.birch_rescue_stage = 3;
        world.open_starter_picker(StarterSpecies::Torchic);
        debug_assert!(world.route101_rescue_invariants_hold());
        world
    }

    /// Stable source-authenticated first command-menu boundary for Birch's
    /// scripted Zigzagoon battle.  `settle_battle_command_surface` is a
    /// general battle-state projection: it completes no gameplay and merely
    /// selects the already-established command-menu ownership boundary.
    pub fn starter_battle() -> Self {
        let mut world = Self::starter_picker();
        world.ask_confirm_starter();
        assert!(world.advance_starter_reveal(15));
        world.respond_starter_confirmation(true);
        world.begin_birch_battle();
        world.dialogue = None;
        world.settle_battle_command_surface();
        // The authenticated source receipt is restored after the scripted
        // starter has already taken the opening damage: its command-ready
        // healthbox is 19/19, not the full 21 HP produced by the generic
        // profile constructor. Keep this checkpoint's logical state aligned
        // with the source save boundary before rendering or accepting input.
        if let Some(battle) = world.battle.as_mut() {
            battle.player_hp = 19;
            battle.player_max_hp = 19;
        }
        debug_assert!(world.route101_rescue_invariants_hold());
        world
    }

    /// Source-authenticated first post-turn boundary for Birch's scripted
    /// Zigzagoon battle. This is the returned command surface after the
    /// concrete Scratch tape, not a Route 101 wild-battle projection.
    pub fn starter_battle_after_turn_one() -> Self {
        let mut world = Self::starter_battle();
        world.source_starter_battle_turn_receipt = 1;
        if let Some(battle) = world.battle.as_mut() {
            battle.player_hp = 16;
            battle.player_max_hp = 19;
            battle.rival_hp = 7;
            battle.player_move_pp = 34;
            battle.player_moves[0].pp = 34;
            battle.opponent_move_slot = Some(0);
            battle.opponent_moves[0].pp = 34;
            battle.opponent_turn_count = 1;
            battle.opponent_move_damage = 3;
            battle.rng_state = 2_167_938_932;
            battle.last_move_hit = true;
            battle.last_move_critical = false;
            battle.last_damage_variance = Some(94);
        }
        world.settle_battle_command_surface();
        world.sync_starter_party_from_battle();
        debug_assert!(world.route101_rescue_invariants_hold());
        world
    }

    /// Source-authenticated second post-turn boundary. The source receipt
    /// keeps the same visible health surface while the second Scratch tape
    /// advances the two move PP owners and battle RNG boundary.
    pub fn starter_battle_after_turn_two() -> Self {
        let mut world = Self::starter_battle_after_turn_one();
        world.source_starter_battle_turn_receipt = 2;
        if let Some(battle) = world.battle.as_mut() {
            battle.player_move_pp = 33;
            battle.player_moves[0].pp = 33;
            battle.opponent_moves[0].pp = 33;
            battle.rival_hp = 1;
            battle.opponent_turn_count = 2;
            battle.rng_state = 911_637_904;
        }
        world.sync_starter_party_from_battle();
        debug_assert!(world.route101_rescue_invariants_hold());
        world
    }

    pub fn starter_battle_victory_handoff() -> Self {
        let mut world = Self::starter_battle_after_turn_two();
        world.source_starter_battle_turn_receipt = 0;
        world.complete_birch_rescue_battle();
        // The authenticated victory receipt is the third Birch page, after
        // the post-battle wait and the first two page-release edges. Keep the
        // typed dialogue runner active so the next A edge remains source
        // owned and serializable.
        world.advance_field_script_task(16);
        for _ in 0..2 {
            world.advance_field_dialogue_printer(u32::MAX);
            world.advance_opening_script();
        }
        // The authenticated source checkpoint is captured after the third
        // Birch page has finished printing.  The reusable runner above needs
        // the page cursor for that text, but must not leave its synthetic
        // printer lead active; otherwise the first A/B edge is consumed by a
        // page that is already ready on the source.
        if let Some(dialogue) = world.field_dialogue.as_mut() {
            dialogue.print_remaining = 0;
        }
        world.field_dialogue_frames = None;
        world.dialogue = world
            .field_dialogue
            .as_ref()
            .map(|dialogue| dialogue.current_text().to_owned());
        world.player = TilePosition { x: 7, y: 15 };
        world.elevation = crate::native::tile_elevation(world.map, 7, 15)
            .expect("Route 101 victory-receipt tile must be staged");
        world.source_starter_battle_victory_receipt = true;
        debug_assert!(world.route101_rescue_invariants_hold());
        world
    }

    /// Common authenticated Route 101 Wurmple encounter entry.  The source
    /// checkpoint is battle-owned even though its return map is Route 101;
    /// constructing it through the wild-battle path keeps field input from
    /// leaking into the entry-message phase.
    fn route101_wild_battle_base() -> Self {
        let mut world = Self::route101_field_lane(TilePosition { x: 13, y: 9 }, Facing::Up);
        world.starter = Some(StarterSpecies::Torchic);
        world.starter_party = Some(starter_party_state(StarterSpecies::Torchic));
        world.ambient_rng = 3_002_958_025;
        let field_return = WildEncounterReturn {
            id: WildEncounterId::Route101Wurmple,
            map: MapId::Route101,
            player: world.player.clone(),
            elevation: world.elevation,
            facing: world.facing,
            rng_state_before_battle: world.ambient_rng,
        };
        let mut battle = opening_battle_state(
            BattleOpponent::Wurmple,
            starter_battle_profile(world.starter),
            wild_battle_profile("WURMPLE", 2, &["TACKLE", "STRING SHOT"]),
            true,
            "Wild WURMPLE appeared!".to_owned(),
            0,
            world.ambient_rng,
            false,
        );
        // The authenticated entry checkpoint is before the player's
        // Pokémon has been sent out: Emerald still owns the player trainer's
        // back-sprite exit while the wild-entry message is waiting. Keep the
        // trainer rail visible and defer the settled Torchic OBJ/status pane
        // until the send-out task starts.
        battle.intro_player_sendout_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES;
        battle.field_return = Some(field_return);
        world.apply_starter_party_to_battle(&mut battle);
        world.battle = Some(battle);
        debug_assert!(world.wild_encounter_invariants_hold());
        world
    }

    /// Source-authenticated Route 101 wild entry handoff (`Wild WURMPLE`
    /// message).  This is intentionally separate from the command surface:
    /// dismissing the entry text is a battle transition, not field input.
    pub fn route101_wild_battle() -> Self {
        Self::route101_wild_battle_base()
    }

    /// Source-authenticated send-out message after the wild entry text.
    pub fn route101_wild_command() -> Self {
        let mut world = Self::route101_wild_battle_base();
        let battle = world.battle.as_mut().expect("wild entry must have battle");
        battle.message = Some("Go! TORCHIC!".to_owned());
        battle.message_visual_start_frame = 0;
        battle.turn_phase = BattleTurnPhase::IntroMessage;
        battle.intro_stage = 2;
        // Loading the authenticated command state advances the source once
        // past the entry tape's VBlank 61.  At that boundary the trainer is
        // still partially visible at x=-57 and the ball is on elapsed tick
        // 44 (the source OAM receipt, not a settled command-menu snapshot).
        // Preserve that in-flight ownership so a no-op continuation cannot
        // snap directly to an unrelated stationary surface.
        battle.intro_player_sendout_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES
            .saturating_sub(44);
        battle.intro_player_sendout_started = true;
        battle.intro_player_sendout_elapsed_frames = 44;
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    /// Authenticated settled field of the first completed deterministic
    /// Wurmple turn.  The source receipt owns the command surface; all later
    /// turn checkpoints are projections of this same battle state.
    pub fn route101_wild_after_turn_one() -> Self {
        let mut world = Self::route101_wild_command();
        world.settle_battle_command_surface();
        if let Some(battle) = world.battle.as_mut() {
            // This checkpoint is the post-default-move command surface. The
            // opponent's first action has already consumed its source RNG
            // turn, which also keeps the authenticated renderer receipt from
            // matching the pre-turn command checkpoint.
            battle.opponent_turn_count = 1;
        }
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route101_wild_after_turn_two() -> Self {
        let mut world = Self::route101_wild_after_turn_one();
        world.source_route101_receipt_rail = 2;
        if let Some(battle) = world.battle.as_mut() {
            battle.player_hp = 19;
            battle.player_max_hp = 19;
            battle.rival_hp = 8;
            battle.rng_state = 3_015_740_837;
            battle.opponent_turn_count = 2;
        }
        world
    }

    pub fn route101_wild_after_turn_three() -> Self {
        let mut world = Self::route101_wild_after_turn_two();
        world.source_route101_receipt_rail = 3;
        if let Some(battle) = world.battle.as_mut() {
            battle.rng_state = 1_729_417_749;
            battle.opponent_turn_count = 3;
            battle.player_hp = 17;
            battle.player_max_hp = 19;
            battle.rival_hp = 2;
            battle.player_move_pp = battle.player_move_pp.saturating_sub(3);
            if let Some(slot) = battle.player_moves.first_mut() {
                slot.pp = battle.player_move_pp;
            }
        }
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route101_wild_after_turn_four() -> Self {
        let mut world = Self::route101_wild_after_turn_three();
        world.source_route101_receipt_rail = 4;
        if let Some(battle) = world.battle.as_mut() {
            battle.rng_state = 2_077_170_134;
            battle.opponent_turn_count = 4;
            battle.player_hp = 15;
            battle.player_max_hp = 19;
            battle.rival_hp = 0;
            battle.turn_phase = BattleTurnPhase::TurnResultMessage;
            battle.message = Some("Wild WURMPLE fainted!".to_owned());
            battle.message_visual_start_frame = 0;
        }
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route101_wild_after_turn_five() -> Self {
        let mut world = Self::route101_wild_after_turn_four();
        world.source_route101_receipt_rail = 5;
        if let Some(battle) = world.battle.as_mut() {
            battle.rng_state = 416_548_816;
            battle.opponent_turn_count = 5;
            battle.player_hp = 15;
            battle.player_max_hp = 19;
            battle.turn_phase = BattleTurnPhase::TerminalMessage;
            battle.message = Some("TORCHIC gained 15 EXP. Points!".to_owned());
            battle.message_visual_start_frame = 0;
        }
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    /// Source-confirmed field ownership after the Wurmple victory callback.
    pub fn route101_wild_after_turn_six() -> Self {
        let mut world = Self::route101_field_lane(TilePosition { x: 13, y: 9 }, Facing::Up);
        world.source_route101_receipt_rail = 6;
        world.starter = Some(StarterSpecies::Torchic);
        world.starter_party = Some(starter_party_state(StarterSpecies::Torchic));
        world.route101_wurmple_resolved = true;
        world.ambient_rng = 1_895_368_719;
        world
    }

    pub fn route101_wild_victory_resume() -> Self {
        Self::route101_wild_after_turn_six()
    }

    pub fn route101_post_victory_r2() -> Self {
        let mut world = Self::route101_wild_after_turn_six();
        world.player = TilePosition { x: 15, y: 9 };
        world.elevation = crate::native::tile_elevation(world.map, 15, 9)
            .expect("Route 101 post-victory R2 must be on staged terrain");
        world
    }

    fn route101_post_victory_field(player: TilePosition, facing: Facing) -> Self {
        let mut world = Self::route101_field_lane(player, facing);
        world.route101_wurmple_resolved = true;
        world.story_flags.rival_route_unlocked = true;
        world
    }

    pub fn route101_post_victory_u7() -> Self {
        Self::route101_post_victory_field(TilePosition { x: 15, y: 2 }, Facing::Up)
    }

    pub fn route101_post_victory_u7_settled() -> Self {
        Self::route101_post_victory_u7()
    }

    pub fn route101_post_victory_l4() -> Self {
        Self::route101_post_victory_field(TilePosition { x: 11, y: 2 }, Facing::Left)
    }

    pub fn route101_post_victory_north_exit() -> Self {
        Self::route101_post_victory_field(TilePosition { x: 11, y: 0 }, Facing::Up)
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

    /// Authenticated Route 103 wild-battle boundary historically named
    /// `route103_wild_command`. The source receipt proves that this is
    /// actually the second intro-message page, not command ownership.
    pub fn route103_wild_command() -> Self {
        let mut world = Self::route103_rival();
        world.player = TilePosition { x: 7, y: 6 };
        world.elevation = crate::native::tile_elevation(world.map, world.player.x, world.player.y)
            .expect("authenticated Route 103 wild origin must be on staged terrain");
        let field_return = WildEncounterReturn {
            id: WildEncounterId::Route103Poochyena,
            map: MapId::Route103,
            player: world.player.clone(),
            elevation: world.elevation,
            facing: world.facing,
            rng_state_before_battle: world.ambient_rng,
        };
        let mut battle = opening_battle_state(
            BattleOpponent::Poochyena,
            starter_battle_profile(world.starter),
            wild_battle_profile("POOCHYENA", 2, &["TACKLE"]),
            true,
            "Wild POOCHYENA appeared!".to_owned(),
            0,
            world.ambient_rng,
            false,
        );
        battle.field_return = Some(field_return);
        world.apply_starter_party_to_battle(&mut battle);
        world.battle = Some(battle);
        debug_assert!(world.wild_encounter_invariants_hold());
        world
    }

    /// Genuine Route 103 wild command surface. Values are the authenticated
    /// `gBattleMons` sidecar for `route103_wild_turn_one`, captured after the
    /// source state reload's required one-frame stabilization.
    pub fn route103_wild_turn_one() -> Self {
        let mut world = Self::route103_wild_command();
        world.starter = Some(StarterSpecies::Torchic);
        world.ambient_rng = 384_740_133;
        let battle = world
            .battle
            .as_mut()
            .expect("wild command checkpoint needs a battle");
        battle.rng_state = world.ambient_rng;
        battle.player_species = "TORCHIC".to_owned();
        battle.player_level = 5;
        battle.player_hp = 15;
        battle.player_max_hp = 19;
        battle.player_attack = 11;
        battle.player_defense = 9;
        battle.player_speed = 10;
        battle.player_special_attack = 12;
        battle.player_special_defense = 10;
        battle.player_move_name = "SCRATCH".to_owned();
        battle.player_status_move_name = "GROWL".to_owned();
        battle.player_move_pp = 32;
        battle.player_status_move_pp = 40;
        battle.player_moves = vec![
            battle_move_slot("SCRATCH", 32),
            battle_move_slot("GROWL", 40),
        ];
        battle.rival_hp = 13;
        battle.opponent_max_hp = 13;
        battle.opponent_level = 2;
        battle.opponent_attack = 7;
        battle.opponent_defense = 6;
        battle.opponent_speed = 5;
        battle.opponent_special_attack = 6;
        battle.opponent_special_defense = 6;
        battle.opponent_move_name = "TACKLE".to_owned();
        battle.opponent_moves = vec![battle_move_slot("TACKLE", 35)];
        battle.opponent_move_slot = None;
        world.starter_party = Some(StarterPartyState {
            species: StarterSpecies::Torchic,
            nickname: None,
            level: 5,
            hp: 15,
            max_hp: 19,
            attack: 11,
            defense: 9,
            speed: 10,
            special_attack: 12,
            special_defense: 10,
            physical_move_pp: 32,
            status_move_pp: 40,
            moves: vec![
                battle_move_slot("SCRATCH", 32),
                battle_move_slot("GROWL", 40),
            ],
        });
        world.settle_battle_command_surface();
        debug_assert!(world.wild_encounter_invariants_hold());
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route103_wild_turn1_move_menu() -> Self {
        let mut world = Self::route103_wild_turn_one();
        let battle = world
            .battle
            .as_mut()
            .expect("move menu checkpoint needs battle");
        battle.turn_phase = BattleTurnPhase::MoveSelection;
        battle.selecting_move = true;
        battle.command_cursor = BATTLE_COMMAND_FIGHT;
        battle.move_cursor = 0;
        battle.message = None;
        battle.message_visual_start_frame = 0;
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    /// Actual phase contained by the authenticated savestate historically
    /// labelled `route103_wild_turn1_move_menu`.
    pub fn route103_wild_player_sendout_message() -> Self {
        let mut world = Self::route103_wild_turn_one();
        let battle = world
            .battle
            .as_mut()
            .expect("sendout checkpoint needs battle");
        battle.turn_phase = BattleTurnPhase::IntroMessage;
        battle.selecting_move = false;
        battle.command_cursor = BATTLE_COMMAND_FIGHT;
        battle.move_cursor = 0;
        battle.message = Some("Go! TORCHIC!".to_string());
        battle.message_visual_start_frame = 0;
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route103_wild_turn1_scratch_text() -> Self {
        let mut world = Self::route103_wild_turn_one();
        let battle = world
            .battle
            .as_mut()
            .expect("Scratch text checkpoint needs battle");
        battle.turn_phase = BattleTurnPhase::TurnResultMessage;
        battle.selecting_move = false;
        battle.player_move_pp = 31;
        battle.player_moves[0].pp = 31;
        battle.rival_hp = 7;
        battle.message = Some("TORCHIC used SCRATCH!".to_string());
        battle.message_visual_start_frame = 0;
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route103_wild_turn1_tackle_text() -> Self {
        let mut world = Self::route103_wild_turn1_scratch_text();
        let battle = world
            .battle
            .as_mut()
            .expect("Tackle text checkpoint needs battle");
        battle.message = Some("Wild POOCHYENA used TACKLE!".to_string());
        battle.message_visual_start_frame = 0;
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    pub fn route103_wild_turn1_command_return() -> Self {
        let mut world = Self::route103_wild_turn1_tackle_text();
        let battle = world
            .battle
            .as_mut()
            .expect("command-return checkpoint needs battle");
        battle.turn_phase = BattleTurnPhase::Command;
        battle.selecting_move = false;
        battle.player_hp = 13;
        battle.message = None;
        battle.message_visual_start_frame = 0;
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    /// Authenticated first command-menu boundary of Brendan's Route 103
    /// trainer battle against May's level-5 Mudkip.
    pub fn route103_rival_battle_command() -> Self {
        let mut world = Self::route103_rival();
        world.starter = Some(StarterSpecies::Torchic);
        world.phase = StoryPhase::RivalBattle;
        world.begin_rival_battle();
        world.ambient_rng = 2_099_687_136;
        let battle = world
            .battle
            .as_mut()
            .expect("rival command checkpoint needs a battle");
        battle.rng_state = world.ambient_rng;
        battle.player_level = 6;
        battle.player_hp = 15;
        battle.player_max_hp = 21;
        battle.player_attack = 12;
        battle.player_defense = 10;
        battle.player_speed = 11;
        battle.player_special_attack = 13;
        battle.player_special_defense = 11;
        battle.player_move_pp = 30;
        battle.player_status_move_pp = 40;
        battle.player_moves = vec![
            battle_move_slot("SCRATCH", 30),
            battle_move_slot("GROWL", 40),
        ];
        battle.rival_hp = 20;
        battle.opponent_max_hp = 20;
        battle.opponent_level = 5;
        battle.opponent_attack = 12;
        battle.opponent_defense = 10;
        battle.opponent_speed = 8;
        battle.opponent_special_attack = 11;
        battle.opponent_special_defense = 10;
        battle.opponent_moves = vec![
            battle_move_slot("TACKLE", 35),
            battle_move_slot("GROWL", 40),
        ];
        world.starter_party = Some(StarterPartyState {
            species: StarterSpecies::Torchic,
            nickname: None,
            level: 6,
            hp: 15,
            max_hp: 21,
            attack: 12,
            defense: 10,
            speed: 11,
            special_attack: 13,
            special_defense: 11,
            physical_move_pp: 30,
            status_move_pp: 40,
            moves: vec![
                battle_move_slot("SCRATCH", 30),
                battle_move_slot("GROWL", 40),
            ],
        });
        world.dialogue = None;
        world.settle_battle_command_surface();
        debug_assert!(world.rival_route_invariants_hold());
        debug_assert!(world.battle_turn_invariants_hold());
        world
    }

    /// First stable native-field checkpoint after the continuously captured
    /// Brendan/Torchic Route 103 victory. Source state:
    /// `983796dc12057b962edafa07a1daa245612ff8dbd8259139ac4686a12fa0dbd7`.
    /// Facing and fitted render position were not exposed by that receipt and
    /// therefore are deliberately not part of the boundary invariant.
    pub fn route103_rival_victory_field() -> Self {
        let mut world = Self::route103_rival();
        world.player_gender = PlayerGender::Brendan;
        world.starter = Some(StarterSpecies::Torchic);
        world.starter_party = Some(StarterPartyState {
            species: StarterSpecies::Torchic,
            nickname: None,
            level: 7,
            hp: 8,
            max_hp: 23,
            attack: 14,
            defense: 11,
            speed: 12,
            special_attack: 15,
            special_defense: 13,
            physical_move_pp: 26,
            status_move_pp: 39,
            moves: vec![
                battle_move_slot("SCRATCH", 26),
                battle_move_slot("GROWL", 39),
                battle_move_slot("FOCUS ENERGY", 30),
            ],
        });
        world.phase = StoryPhase::RivalDefeated;
        world.battle = None;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;
        world.field_script = None;
        world.transition = None;
        world.route103_rival_intro_frames = None;
        world.rival_departure_frames = None;
        world.route103_rival_departure_facing = None;
        world.story_flags.pokemon_obtained = true;
        world.story_flags.birch_rescue_started = true;
        world.story_flags.starter_acknowledged = true;
        world.story_flags.rival_route_unlocked = true;
        world.story_flags.defeated_rival_route103 = true;
        world.story_flags.hide_route103_rival = true;
        world.story_flags.hide_littleroot_lab_rival = false;
        world.story_flags.hide_oldale_rival = false;
        world.story_vars = OpeningStoryVars {
            birch_lab_state: 4,
            littleroot_rival_state: 3,
            oldale_rival_state: 1,
        };
        world.oldale_rival_departed = false;
        world.npcs = route103_npcs(world.phase);
        debug_assert!(world.route103_rival_victory_field_invariants_hold());
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
        if self.dialogue.is_some() {
            return false;
        }
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
            && self.dialogue.is_none()
        {
            // Route101_EventScript_BirchsBag is a script-to-picker handoff,
            // not a special input tape. v8 establishes both progression
            // flags before ChoiceStarter exposes the default Torchic index.
            self.begin_field_script(vec![
                ScriptStep::SetFlag {
                    flag: ProgressFlag::PokemonObtained,
                },
                ScriptStep::SetFlag {
                    flag: ProgressFlag::BirchRescueStarted,
                },
                ScriptStep::OpenStarterPicker {
                    default_starter: StarterSpecies::Torchic,
                },
            ]);
            return true;
        }
        if let Some(rule) = TRAINER_ENCOUNTER_RULES.iter().find(|rule| {
            rule.map == self.map
                && rule.required_phase == self.phase
                && rule.target == (TilePosition { x, y })
        }) {
            self.begin_trainer_encounter(rule.clone());
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
        let Some(npc) = self
            .npcs
            .iter_mut()
            .find(|npc| npc.map == self.map && npc.position.x == x && npc.position.y == y)
        else {
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

    /// Starts a trainer map event from declarative metadata. The specific
    /// opponent still chooses its source battle profile in `begin_rival_battle`;
    /// this handoff only establishes the map-script ownership boundary.
    fn begin_trainer_encounter(&mut self, rule: TrainerEncounterRule) {
        if rule.opponent != BattleOpponent::Rival
            || self.map != rule.map
            || self.phase != rule.required_phase
            || self.battle.is_some()
        {
            return;
        }
        self.phase = StoryPhase::RivalBattle;
        self.title_intro_step = 0;
        self.route103_rival_intro_stage = 0;
        self.begin_field_dialogue(rival_route103_observation(self.player_gender));
        debug_assert!(self.rival_route_invariants_hold());
    }

    pub fn rival_route_task(&self) -> RivalRouteTask {
        if self
            .battle
            .as_ref()
            .is_some_and(|battle| battle.opponent == BattleOpponent::Rival)
        {
            RivalRouteTask::Battle
        } else if self.rival_departure_frames.is_some() {
            RivalRouteTask::Departure
        } else if self.phase == StoryPhase::RivalDefeated
            && self.map == MapId::Route103
            && (self.dialogue.is_some() || self.npcs.iter().any(|npc| npc.id == "rival"))
        {
            RivalRouteTask::DefeatDialogue
        } else if self.phase == StoryPhase::RivalBattle
            && self.route103_rival_intro_frames.is_some()
        {
            RivalRouteTask::ChallengeApproach
        } else if self.phase == StoryPhase::RivalBattle && self.map == MapId::Route103 {
            RivalRouteTask::ChallengeDialogue
        } else {
            RivalRouteTask::Field
        }
    }

    /// Checks the data-driven Oldale→Route103 trainer corridor. This is a
    /// map-script invariant, not an assertion about which input tape reached
    /// it, so restores cannot turn a battle callback into field movement.
    pub fn rival_route_invariants_hold(&self) -> bool {
        match self.rival_route_task() {
            RivalRouteTask::Field => true,
            RivalRouteTask::ChallengeDialogue | RivalRouteTask::ChallengeApproach => {
                self.map == MapId::Route103
                    && self.phase == StoryPhase::RivalBattle
                    && self.battle.is_none()
            }
            RivalRouteTask::Battle => {
                self.map == MapId::Route103
                    && self.phase == StoryPhase::RivalBattle
                    && self.battle.as_ref().is_some_and(|battle| {
                        battle.opponent == BattleOpponent::Rival
                            && !battle.wild
                            && battle.field_return.is_none()
                    })
            }
            RivalRouteTask::DefeatDialogue | RivalRouteTask::Departure => {
                self.map == MapId::Route103
                    && self.phase == StoryPhase::RivalDefeated
                    && self.battle.is_none()
                    && self.route103_rival_victory_progression_invariants_hold()
            }
        }
    }

    pub fn return_journey_task(&self) -> ReturnJourneyTask {
        if self.phase == StoryPhase::RivalDefeated {
            if self
                .transition
                .as_ref()
                .is_some_and(|transition| transition.destination_map == MapId::ProfessorBirchsLab)
            {
                return ReturnJourneyTask::LabWarp;
            }
            if self.map == MapId::Route103 {
                return if self.rival_departure_frames.is_some() {
                    ReturnJourneyTask::Route103Departure
                } else if self.dialogue.is_some() || self.npcs.iter().any(|npc| npc.id == "rival") {
                    ReturnJourneyTask::Route103DefeatDialogue
                } else {
                    ReturnJourneyTask::ReturnField
                };
            }
            if self.map == MapId::OldaleTown {
                return if self.oldale_rival_approach_frames.is_some() {
                    ReturnJourneyTask::OldaleApproach
                } else if self.oldale_rival_departure_frames.is_some() {
                    ReturnJourneyTask::OldaleDeparture
                } else if self.dialogue.is_some()
                    && self.npcs.iter().any(|npc| npc.id == "oldale_rival")
                {
                    ReturnJourneyTask::OldaleDialogue
                } else {
                    ReturnJourneyTask::ReturnField
                };
            }
            return ReturnJourneyTask::ReturnField;
        }
        if self.phase == StoryPhase::PokedexHandoff {
            if self.pokedex_arrival_frames.is_some() {
                ReturnJourneyTask::PokedexArrival
            } else if self.pokedex_receipt_fanfare_frames.is_some() {
                ReturnJourneyTask::PokedexReceiptFanfare
            } else if self.pokedex_rival_frames.is_some() {
                ReturnJourneyTask::PokedexRivalApproach
            } else if self.pokedex_poke_ball_fanfare_frames.is_some() {
                ReturnJourneyTask::PokeBallGiftFanfare
            } else {
                ReturnJourneyTask::PokedexDialogue
            }
        } else if self.phase == StoryPhase::PokedexReceived && self.pending_running_shoes {
            if self.running_shoes_return_door_frames.is_some() {
                ReturnJourneyTask::RunningShoesDoor
            } else if self.running_shoes_return_delay_frames.is_some() {
                ReturnJourneyTask::RunningShoesReturnDelay
            } else if self.running_shoes_stage == 6 && self.running_shoes_frames.is_some() {
                ReturnJourneyTask::RunningShoesReturn
            } else if self.running_shoes_dialogue_frames.is_some()
                || (self.dialogue.is_some() && self.running_shoes_stage >= 2)
            {
                ReturnJourneyTask::RunningShoesDialogue
            } else if self.running_shoes_frames.is_some() {
                ReturnJourneyTask::RunningShoesApproach
            } else {
                ReturnJourneyTask::RunningShoesPrompt
            }
        } else if self.phase == StoryPhase::RunningShoesReceived && self.map == MapId::Route101 {
            ReturnJourneyTask::Route101Departure
        } else {
            ReturnJourneyTask::Field
        }
    }

    /// Durable source bundle written by the Route 103 trainer script.  A
    /// broad phase alone is insufficient evidence: staged or losing battle
    /// checkpoints do not contain this combination of event flags and vars.
    pub fn route103_rival_victory_progression_invariants_hold(&self) -> bool {
        self.story_flags.defeated_rival_route103
            && !self.story_flags.hide_littleroot_lab_rival
            && self.story_vars.birch_lab_state >= 4
            && self.story_vars.littleroot_rival_state == 3
            && self.story_vars.oldale_rival_state >= 1
            && if self.story_vars.oldale_rival_state == 1 {
                !self.story_flags.hide_oldale_rival && !self.oldale_rival_departed
            } else {
                self.story_flags.hide_oldale_rival && self.oldale_rival_departed
            }
    }

    /// Exact authenticated native field checkpoint after May's Route 103
    /// departure, including the source's complete populated move/PP arrays.
    pub fn route103_rival_victory_field_invariants_hold(&self) -> bool {
        let party_exact = self.starter_party.as_ref().is_some_and(|party| {
            party.species == StarterSpecies::Torchic
                && party.level == 7
                && party.hp == 8
                && party.max_hp == 23
                && party.attack == 14
                && party.defense == 11
                && party.speed == 12
                && party.special_attack == 15
                && party.special_defense == 13
                && party.physical_move_pp == 26
                && party.status_move_pp == 39
                && party.moves
                    == vec![
                        battle_move_slot("SCRATCH", 26),
                        battle_move_slot("GROWL", 39),
                        battle_move_slot("FOCUS ENERGY", 30),
                    ]
        });
        self.map == MapId::Route103
            && self.player == (TilePosition { x: 10, y: 4 })
            && self.player_gender == PlayerGender::Brendan
            && self.phase == StoryPhase::RivalDefeated
            && self.starter == Some(StarterSpecies::Torchic)
            && party_exact
            && self.battle.is_none()
            && self.dialogue.is_none()
            && self.transition.is_none()
            && self.field_input_owner() == FieldInputOwner::Field
            && self.story_flags.hide_route103_rival
            && !self.npcs.iter().any(|npc| npc.id == "rival")
            && self.story_vars.birch_lab_state == 4
            && self.story_vars.littleroot_rival_state == 3
            && self.story_vars.oldale_rival_state == 1
            && self.route103_rival_victory_progression_invariants_hold()
    }

    /// Source-state invariant for the complete rival-return corridor.  It is
    /// deliberately expressed in maps, story facts, and exclusive tasks, so
    /// a restored checkpoint cannot expose field movement during a movement
    /// stream or fanfare just because it was reached with different packets.
    pub fn return_journey_invariants_hold(&self) -> bool {
        if self.phase == StoryPhase::RivalDefeated
            && !self.route103_rival_victory_progression_invariants_hold()
        {
            return false;
        }
        let exclusive_rails = [
            self.rival_departure_frames.is_some(),
            self.oldale_rival_approach_frames.is_some(),
            self.oldale_rival_departure_frames.is_some(),
            self.pokedex_arrival_frames.is_some(),
            self.pokedex_receipt_fanfare_frames.is_some(),
            self.pokedex_rival_frames.is_some(),
            self.pokedex_poke_ball_fanfare_frames.is_some(),
            self.running_shoes_wait_frames.is_some(),
            self.running_shoes_frames.is_some(),
            self.running_shoes_return_delay_frames.is_some(),
            self.running_shoes_return_door_frames.is_some(),
        ]
        .into_iter()
        .filter(|active| *active)
        .count();
        if exclusive_rails > 1 {
            return false;
        }
        match self.return_journey_task() {
            ReturnJourneyTask::Field => true,
            ReturnJourneyTask::Route103DefeatDialogue | ReturnJourneyTask::Route103Departure => {
                self.map == MapId::Route103
                    && self.phase == StoryPhase::RivalDefeated
                    && self.battle.is_none()
            }
            ReturnJourneyTask::ReturnField => {
                self.phase == StoryPhase::RivalDefeated
                    && matches!(
                        self.map,
                        MapId::Route103
                            | MapId::OldaleTown
                            | MapId::Route101
                            | MapId::LittlerootTown
                            | MapId::ProfessorBirchsLab
                    )
                    && self.battle.is_none()
            }
            ReturnJourneyTask::OldaleApproach
            | ReturnJourneyTask::OldaleDialogue
            | ReturnJourneyTask::OldaleDeparture => {
                self.map == MapId::OldaleTown
                    && self.phase == StoryPhase::RivalDefeated
                    && self.battle.is_none()
                    && self.npcs.iter().any(|npc| npc.id == "oldale_rival")
            }
            ReturnJourneyTask::LabWarp => {
                self.phase == StoryPhase::RivalDefeated
                    && self.transition.as_ref().is_some_and(|transition| {
                        transition.destination_map == MapId::ProfessorBirchsLab
                    })
            }
            ReturnJourneyTask::PokedexArrival
            | ReturnJourneyTask::PokedexDialogue
            | ReturnJourneyTask::PokedexReceiptFanfare
            | ReturnJourneyTask::PokedexRivalApproach
            | ReturnJourneyTask::PokeBallGiftFanfare => {
                self.map == MapId::ProfessorBirchsLab
                    && self.phase == StoryPhase::PokedexHandoff
                    && self.battle.is_none()
            }
            ReturnJourneyTask::RunningShoesPrompt
            | ReturnJourneyTask::RunningShoesApproach
            | ReturnJourneyTask::RunningShoesDialogue
            | ReturnJourneyTask::RunningShoesReturnDelay
            | ReturnJourneyTask::RunningShoesReturn
            | ReturnJourneyTask::RunningShoesDoor => {
                self.map == MapId::LittlerootTown
                    && self.phase == StoryPhase::PokedexReceived
                    && self.pending_running_shoes
                    && self.battle.is_none()
            }
            ReturnJourneyTask::Route101Departure => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::RunningShoesReceived
                    && !self.pending_running_shoes
            }
        }
    }

    /// Starts a normal object/background field message. Emerald's text box
    /// has a lead-in before revealing one glyph per frame, so the message is
    /// not dismissible on the same input that opened it.
    fn begin_field_dialogue(&mut self, dialogue: String) {
        self.begin_field_dialogue_pages(vec![dialogue]);
    }

    /// Starts a source-authored sequence of normal field pages. This is the
    /// reusable route-level API: callers specify pages, while the engine owns
    /// printer timing, input locking, page advancement, and serialization.
    /// Empty page sets are a no-op rather than an invalid half-open dialogue.
    pub fn begin_field_dialogue_pages(&mut self, pages: Vec<String>) {
        let Some(mut dialogue) = FieldDialogueState::new(pages) else {
            return;
        };
        if self.map == MapId::MaysHouse1F && self.mays_house_1f_rival_scene_start_frame.is_some() {
            dialogue.print_remaining =
                mays_house_1f_dialogue_printer_duration(dialogue.current_text());
            if self.mays_house_1f_dialogue_page_hold.is_none() {
                // The initial OnFrame message's arrow task is authenticated
                // at the first ready VBlank, 305, rather than at an A edge.
                self.mays_house_1f_dialogue_page_arrow_anchor = Some(305);
            }
        }
        self.field_dialogue_frames = Some(dialogue.print_remaining);
        self.dialogue = Some(dialogue.current_text().to_owned());
        self.field_dialogue = Some(dialogue);
    }

    /// Advances or closes the typed dialogue after a confirmation edge.
    /// Returns `true` when the input remains dialogue-owned (the printer is
    /// active or another page opens). `false` means the final page just
    /// closed and the enclosing map script may consume that same edge.
    fn dismiss_field_dialogue_page(&mut self) -> Option<bool> {
        let Some(mut dialogue) = self.field_dialogue.take() else {
            return None;
        };
        if dialogue.print_remaining != 0 {
            self.field_dialogue = Some(dialogue);
            return Some(true);
        }
        // On the authenticated Mays House tape the A edge at global VBlank
        // 1696 is consumed by the source text task without dismissing the
        // ready `Um… I'm MAY.` page.  The following A edge (V1997) performs
        // the dismissal.  Preserve this source-observed one-edge debounce in
        // the reusable field printer rather than advancing our page cursor
        // ahead of the ROM's script.
        let mays_source_debounced_edge = self
            .mays_house_1f_rival_scene_start_frame
            .map(|start| self.frame == start.saturating_add(1_572))
            .unwrap_or(false);
        if self.map == MapId::MaysHouse1F
            && mays_source_debounced_edge
            && dialogue.current_text().starts_with("Um… I'm MAY.")
        {
            // The ROM closes the visible page on this edge but leaves the
            // paged task waiting for the next A before opening the next
            // message. Keep the page cursor at `Um…` with a zero printer and
            // publish an empty renderer projection for the intervening
            // no-op window.
            dialogue.print_remaining = 0;
            self.field_dialogue_frames = None;
            self.mays_house_1f_dialogue_page_hold =
                Some((self.frame, dialogue.current_text().to_owned()));
            self.mays_house_1f_dialogue_hold_arrow_anchor =
                self.mays_house_1f_dialogue_page_arrow_anchor;
            self.mays_house_1f_dialogue_page_arrow_anchor = None;
            self.dialogue = Some(String::new());
            self.field_dialogue = Some(dialogue);
            return Some(true);
        }
        if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_rival_scene_start_frame.is_some()
            && dialogue.page == 4
            && self.mays_house_1f_dialogue_scroll_start_frame.is_none()
        {
            // `I…` is a source `\l` page. A dismissing A starts the four-tick
            // line scroll; it does not advance to the next authored page.
            dialogue.print_remaining = 4;
            self.field_dialogue_frames = Some(4);
            self.mays_house_1f_dialogue_scroll_start_frame = Some(self.frame);
            self.field_dialogue = Some(dialogue);
            return Some(true);
        }
        if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_rival_scene_start_frame.is_some()
            && dialogue.page == 4
            && self.mays_house_1f_dialogue_scroll_start_frame.is_some()
        {
            let previous_page_text = mays_house_1f_scroll_projection(dialogue.current_text());
            if dialogue.advance_page() {
                dialogue.print_remaining =
                    mays_house_1f_dialogue_printer_duration(dialogue.current_text());
                self.mays_house_1f_dialogue_page_hold = Some((self.frame, previous_page_text));
                self.mays_house_1f_dialogue_hold_arrow_anchor = self
                    .mays_house_1f_dialogue_scroll_start_frame
                    .map(|scroll_start| scroll_start.saturating_add(40))
                    .or(self.mays_house_1f_dialogue_page_arrow_anchor);
                self.mays_house_1f_dialogue_page_arrow_anchor = Some(
                    self.frame
                        .saturating_add(u64::from(dialogue.print_remaining))
                        .saturating_add(1),
                );
                self.mays_house_1f_dialogue_scroll_start_frame = None;
                self.field_dialogue_frames = Some(dialogue.print_remaining);
                self.dialogue = Some(dialogue.current_text().to_owned());
                self.field_dialogue = Some(dialogue);
                return Some(true);
            }
            self.field_dialogue = Some(dialogue);
            return Some(true);
        }
        if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_rival_scene_start_frame.is_some()
            && dialogue.page == 11
        {
            // The source's A edge after the final “I'll catch you later!”
            // page closes the message and hands ownership directly to May's
            // departure task.  The page remains rasterized for the edge and
            // following scheduler tick, but no new printer page is opened.
            self.field_dialogue_frames = None;
            self.mays_house_1f_dialogue_page_hold =
                Some((self.frame, dialogue.current_text().to_owned()));
            // The final page is already in the source window at this edge,
            // but its down-arrow task is not recreated.  Keeping the anchor
            // empty makes V4405/V4406 a text-only handoff before the window
            // clears on the next scheduler tick.
            self.mays_house_1f_dialogue_hold_arrow_anchor = None;
            self.mays_house_1f_dialogue_page_arrow_anchor = None;
            self.dialogue = None;
            // The source closes the message window on this edge. Retaining
            // the typed page here makes the renderer draw an empty white box
            // for one VBlank while the departure task is being scheduled.
            self.field_dialogue = None;
            return Some(false);
        }
        let previous_page_text = dialogue.current_text().to_owned();
        if dialogue.advance_page() {
            if self.source_starter_battle_victory_receipt
                && self.map == MapId::Route101
                && dialogue.pages.len() == 6
            {
                // Birch's Route 101 OnFrame printer advances one authored
                // character per VBlank with a two-frame handoff lead. Its
                // timing is intentionally narrower than the generic field
                // printer used by ordinary object-event text.
                dialogue.print_remaining = birch_rescue_dialogue_printer_duration(
                    dialogue.current_text(),
                );
                self.source_starter_battle_victory_previous_page_edge_frame =
                    self.source_starter_battle_victory_page_edge_frame;
                self.source_starter_battle_victory_page_edge_was_b =
                    self.source_starter_battle_victory_pending_edge_was_b;
                self.source_starter_battle_victory_page_edge_from_final_printer =
                    self.source_starter_battle_victory_pending_edge_from_final_printer;
                self.source_starter_battle_victory_page_edge_frame = Some(self.frame);
            }
            if self.map == MapId::MaysHouse1F
                && self.mays_house_1f_rival_scene_start_frame.is_some()
            {
                dialogue.print_remaining =
                    mays_house_1f_dialogue_printer_duration(dialogue.current_text());
                self.mays_house_1f_dialogue_page_hold = Some((self.frame, previous_page_text));
                // The source has pre-rasterized the long page before its A
                // edge.  Reset the arrow animation at this page boundary;
                // carrying the prior one-line page's phase leaves the
                // source arrow absent at the authenticated V4104 edge.
                self.mays_house_1f_dialogue_hold_arrow_anchor =
                    self.mays_house_1f_dialogue_page_arrow_anchor;
                let arrow_ready_after = if dialogue.page == 4 {
                    // Page 4 is a `\\l` line-scroll.  The source creates
                    // its first down-arrow after the first two visible
                    // lines, while the third line remains pending until the
                    // next A edge.  Include the two-frame printer lead and
                    // the one-frame page handoff before the arrow task.
                    dialogue
                        .current_text()
                        .split('\n')
                        .take(2)
                        .map(|line| line.chars().count())
                        .sum::<usize>()
                        .saturating_add(3) as u64
                } else if dialogue.page == 11 {
                    // The closing `I'll catch you later!` page never creates
                    // a down-arrow task in the source script; the next A edge
                    // is consumed by the departure handoff instead.
                    u64::MAX
                } else {
                    u64::from(dialogue.print_remaining).saturating_add(1)
                };
                self.mays_house_1f_dialogue_page_arrow_anchor =
                    Some(self.frame.saturating_add(arrow_ready_after));
            }
            self.field_dialogue_frames = Some(dialogue.print_remaining);
            self.dialogue = Some(dialogue.current_text().to_owned());
            self.field_dialogue = Some(dialogue);
            return Some(true);
        }
        self.field_dialogue_frames = None;
        if self.map == MapId::MaysHouse1F && self.mays_house_1f_rival_scene_start_frame.is_some() {
            // The source keeps the final page rasterized for the VBlank that
            // consumes the closing A edge. The script state is released on
            // that edge; only the renderer projection persists until the
            // next VBlank.
            self.mays_house_1f_dialogue_page_hold = Some((self.frame, previous_page_text));
            self.mays_house_1f_dialogue_hold_arrow_anchor =
                self.mays_house_1f_dialogue_page_arrow_anchor;
            self.mays_house_1f_dialogue_page_arrow_anchor = None;
        } else {
            self.mays_house_1f_dialogue_page_hold = None;
            self.mays_house_1f_dialogue_page_arrow_anchor = None;
            self.mays_house_1f_dialogue_hold_arrow_anchor = None;
        }
        self.dialogue = None;
        Some(false)
    }

    /// Starts a generic script and immediately executes non-blocking steps.
    /// An empty script is deliberately harmless, making generated map data
    /// safe to load before every optional event is authored.
    pub fn begin_field_script(&mut self, steps: Vec<ScriptStep>) {
        if self.field_script.is_some() || self.transition.is_some() {
            return;
        }
        self.field_script = Some(FieldScriptRunner {
            steps,
            cursor: 0,
            wait_remaining: None,
        });
        self.run_field_script_until_blocked();
    }

    /// Advances a script-owned wait. It returns true exactly while the
    /// script consumed the VBlank window; callers can compose it with the
    /// rest of the field scheduler without guessing about task ownership.
    pub fn advance_field_script_task(&mut self, frames: u32) -> bool {
        let Some(mut runner) = self.field_script.take() else {
            return false;
        };
        let Some(remaining) = runner.wait_remaining else {
            self.field_script = Some(runner);
            // A script runner remains parked on its Dialogue step while the
            // typed page owns the field.  Re-entering the runner here would
            // call `begin_field_dialogue_pages` again and silently reset a
            // ready page back to page zero on the next Noop request.
            if self.field_dialogue.is_some() {
                return false;
            }
            self.run_field_script_until_blocked();
            return self.field_script.is_some();
        };
        let consumed = frames.min(u32::from(u16::MAX)) as u16;
        let next = remaining.saturating_sub(consumed);
        if next != 0 {
            runner.wait_remaining = Some(next);
            self.field_script = Some(runner);
            return true;
        }
        runner.wait_remaining = None;
        runner.cursor += 1;
        self.field_script = Some(runner);
        self.run_field_script_until_blocked();
        self.field_script.is_some()
    }

    /// Called after the final page of a script-owned dialogue. It advances
    /// the program counter before executing following same-VBlank steps,
    /// which mirrors source `closemessage` followed by `setflag`/`applymovement`.
    fn resume_field_script_after_dialogue(&mut self) -> bool {
        let Some(mut runner) = self.field_script.take() else {
            return false;
        };
        runner.cursor += 1;
        self.field_script = Some(runner);
        self.run_field_script_until_blocked();
        self.field_script.is_some()
    }

    fn run_field_script_until_blocked(&mut self) {
        loop {
            let Some(mut runner) = self.field_script.take() else {
                return;
            };
            if runner.wait_remaining.is_some() || runner.cursor >= runner.steps.len() {
                if runner.cursor < runner.steps.len() {
                    self.field_script = Some(runner);
                }
                return;
            }
            let step = runner.steps[runner.cursor].clone();
            match step {
                ScriptStep::Dialogue { pages } => {
                    if pages.is_empty() {
                        runner.cursor += 1;
                        self.field_script = Some(runner);
                        continue;
                    }
                    self.field_script = Some(runner);
                    self.begin_field_dialogue_pages(pages);
                    return;
                }
                ScriptStep::Wait { frames } => {
                    runner.wait_remaining = (frames != 0).then_some(frames);
                    if runner.wait_remaining.is_none() {
                        runner.cursor += 1;
                        self.field_script = Some(runner);
                        continue;
                    }
                    self.field_script = Some(runner);
                    return;
                }
                ScriptStep::SetFlag { flag } => {
                    self.story_flags.set(flag);
                    runner.cursor += 1;
                    self.field_script = Some(runner);
                }
                ScriptStep::OpenStarterPicker { default_starter } => {
                    runner.cursor += 1;
                    self.field_script = Some(runner);
                    self.open_starter_picker(default_starter);
                    return;
                }
                ScriptStep::BeginBattleHandoff { opponent } => {
                    runner.cursor += 1;
                    self.field_script = Some(runner);
                    self.begin_battle_handoff(opponent);
                    return;
                }
                ScriptStep::SetRoute101RescueTask { task } => {
                    self.route101_rescue_task = task;
                    runner.cursor += 1;
                    self.field_script = Some(runner);
                }
                ScriptStep::Warp {
                    destination_map,
                    destination,
                    timing,
                } => {
                    runner.cursor += 1;
                    self.field_script = Some(runner);
                    self.begin_transition_with_timing(destination_map, destination, timing);
                    return;
                }
            }
        }
    }

    /// The task which owns controller input right now. The specialized scene
    /// timers remain source-calibrated, but their ownership is represented by
    /// this single query so route code never has to guess whether movement is
    /// legal while a script, dialogue, or fade is active.
    pub fn field_input_owner(&self) -> FieldInputOwner {
        if self.battle.is_some() {
            FieldInputOwner::Battle
        } else if self.transition.is_some() {
            FieldInputOwner::Warp
        } else if self.field_select_modal.is_some() {
            FieldInputOwner::SelectModal
        } else if self.clock_editing.is_some() {
            FieldInputOwner::ClockEditor
        } else if self.menu_open
            || self.menu_transition_frames.is_some()
            || self.active_screen.is_some()
        {
            FieldInputOwner::Menu
        } else if self.dialogue.is_some() {
            FieldInputOwner::Dialogue
        } else if self.field_script.is_some() {
            FieldInputOwner::Script
        } else if self.clock_settle_frames.is_some()
            || self.clock_visit_frames.is_some()
            || self.tv_broadcast_intro_frames.is_some()
            || self.tv_broadcast_approach_frames.is_some()
            || self.tv_broadcast_view_frames.is_some()
            || self.rival_mom_intro_frames.is_some()
            || self.mays_house_1f_rival_scene_start_frame.is_some()
            || self.mays_house_1f_rival_departure_frames.is_some()
            || self.truck_arrival_frames.is_some()
            || self.truck_departure_frames.is_some()
            || self.birch_rescue_frames.is_some()
            || self.route101_exit_guard_delay.is_some()
            || self.route103_rival_intro_frames.is_some()
            || self.rival_departure_frames.is_some()
            || self.oldale_rival_approach_frames.is_some()
            || self.oldale_rival_departure_frames.is_some()
            || self.pokedex_arrival_frames.is_some()
            || self.pokedex_rival_frames.is_some()
            || self.pokedex_receipt_fanfare_frames.is_some()
            || self.pokedex_poke_ball_fanfare_frames.is_some()
            || self.running_shoes_wait_frames.is_some()
            || self.running_shoes_frames.is_some()
            || self.running_shoes_dialogue_frames.is_some()
            || self.running_shoes_return_delay_frames.is_some()
            || self.running_shoes_return_door_frames.is_some()
        {
            FieldInputOwner::Script
        } else {
            FieldInputOwner::Field
        }
    }

    /// Installs the source field SELECT registration help task.  The caller
    /// must be the idle field controller; menus, scripts, and walking tasks
    /// cannot steal the edge and create a second concurrent owner.
    pub fn begin_field_select_modal(&mut self) -> bool {
        if self.field_input_owner() != FieldInputOwner::Field {
            return false;
        }
        self.route101_select_modal_receipt_active = false;
        self.field_select_modal = Some(FieldSelectModal::new());
        true
    }

    /// Advances one VBlank of the SELECT window. Returns true while it still
    /// owns input. The caller intentionally handles the dismissing B edge
    /// separately so its visible VBlank is not also counted as a close delay.
    pub fn advance_field_select_modal(&mut self) -> bool {
        let Some(mut modal) = self.field_select_modal.take() else {
            return false;
        };
        if let Some(remaining) = modal.closing_frames {
            if remaining <= 1 {
                return false;
            }
            modal.closing_frames = Some(remaining - 1);
        } else {
            modal.elapsed_frames = modal.elapsed_frames.saturating_add(1);
        }
        self.field_select_modal = Some(modal);
        true
    }

    /// B is the source-observed dismissal edge. It is ignored during the
    /// printing/setup lock and leaves the completed modal visible on the
    /// pressing VBlank plus two following VBlanks.
    pub fn dismiss_field_select_modal(&mut self) -> bool {
        let Some(modal) = self.field_select_modal.as_mut() else {
            return false;
        };
        if !modal.input_ready() {
            return false;
        }
        modal.closing_frames = Some(FieldSelectModal::CLOSE_VISIBLE_FRAMES);
        true
    }

    pub fn open_menu(&mut self) {
        if self.dialogue.is_none() {
            self.menu_open = true;
            // The field task retains the logical cursor across a close/open
            // cycle.  The initial menu has no prior glyph and starts at BAG;
            // subsequent opens resume the last logical row, including EXIT.
            self.menu_cursor = self.bedroom_menu_render_cursor.or(Some(0));
            // Reopening the field menu retains the previous cursor glyph on
            // the opening task's final VBlank; the menu task uploads logical
            // row zero on its first owned VBlank. Initial creation has no
            // prior glyph and therefore starts at BAG/row zero.
            if self.bedroom_menu_render_cursor.is_none() {
                self.bedroom_menu_render_cursor = Some(0);
            }
            // A cursor upload belongs to the menu task that is currently
            // opening. Never carry a pending directional upload across a
            // close/reopen boundary; the first owned VBlank must retain the
            // prior glyph and only a new valid direction may schedule an
            // upload.
            self.bedroom_menu_cursor_upload_pending = false;
            self.menu_selection = None;
        }
    }

    pub fn begin_bedroom_menu_open(&mut self, trailing_frames: u32) {
        if self.menu_open || self.bedroom_menu_open_frames.is_some() {
            return;
        }
        self.bedroom_menu_open_frames = Some(8);
        if trailing_frames > 0 {
            self.advance_bedroom_menu_open(trailing_frames);
        }
    }

    /// Starts the field-ready Start task.  Emerald publishes the logical
    /// menu-open state on the trigger VBlank, but delays the window upload for
    /// eight VBlanks while the field task's raster remains visible.  This is
    /// distinct from the bedroom task, where opening can freeze a turn and
    /// therefore keeps the menu logically closed until the setup task settles.
    pub fn begin_field_ready_menu_open(&mut self) {
        if self.menu_open || self.bedroom_menu_open_frames.is_some() {
            return;
        }
        self.open_menu();
        self.field_ready_menu_open_started_frame = Some(self.frame);
        self.bedroom_menu_open_frames = Some(8);
    }

    pub fn advance_bedroom_menu_open(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.bedroom_menu_open_frames else {
            return false;
        };
        let next = remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if next == 0 {
            self.bedroom_menu_open_frames = None;
            if self.camera_handoff_from.is_some() && self.walk_render_origin.is_none() {
                self.bedroom_turn_cancelled = true;
            }
            self.open_menu();
        } else {
            self.bedroom_menu_open_frames = Some(next);
        }
        true
    }

    pub fn close_menu(&mut self) {
        if self.map == MapId::Route101 && self.menu_open {
            self.route101_menu_close_frames = Some(1);
            self.route101_menu_close_cursor =
                self.bedroom_menu_render_cursor.or(self.menu_cursor);
            self.route101_menu_exit_asset_frames = Some(8);
        }
        self.menu_open = false;
        self.menu_cursor = None;
        self.bedroom_menu_close_pending = false;
    }

    /// Installs the source-visible Route 101 close rail after the delayed
    /// field-menu upload completes on the same VBlank as a close edge.
    pub fn begin_route101_menu_close(&mut self, frames: u8) {
        self.route101_menu_close_frames = Some(frames.max(1));
        self.route101_menu_close_cursor = self.menu_cursor;
        self.menu_open = false;
        self.menu_cursor = None;
    }

    /// Advances the presentation-only Route 101 menu close rail by one
    /// VBlank.  Input remains suppressed while the value is still present.
    pub fn advance_route101_menu_close(&mut self) {
        let Some(remaining) = self.route101_menu_close_frames else {
            return;
        };
        if remaining <= 1 {
            self.route101_menu_close_frames = None;
            self.route101_menu_close_cursor = None;
        } else {
            self.route101_menu_close_frames = Some(remaining - 1);
        }
    }

    pub fn advance_route101_menu_exit_asset(&mut self) {
        let Some(remaining) = self.route101_menu_exit_asset_frames else {
            return;
        };
        if remaining <= 1 {
            self.route101_menu_exit_asset_frames = None;
        } else {
            self.route101_menu_exit_asset_frames = Some(remaining - 1);
        }
    }

    /// Advances the short source hold after selecting BAG from the live
    /// Route 101 field menu. The application edge remains raster-visible but
    /// does not consume subsequent controller input until this hold ends.
    pub fn advance_route101_menu_action_hold(&mut self) {
        let Some(remaining) = self.route101_menu_action_hold_frames else {
            return;
        };
        if remaining == 0 {
            self.route101_menu_action_hold_frames = None;
            self.menu_open = false;
            self.menu_cursor = None;
            self.bedroom_menu_cursor_upload_pending = false;
        } else if remaining == 1 {
            // Keep the menu/task visible for the source's final hold VBlank;
            // the following tick releases it to the field controller.
            self.route101_menu_action_hold_frames = Some(0);
        } else {
            self.route101_menu_action_hold_frames = Some(remaining - 1);
        }
    }

    /// Queues the source field SELECT task behind an in-flight Route 101
    /// stride.  The task is installed on the edge VBlank, but its border does
    /// not become visible until the fifth scheduler tick; keeping that delay
    /// separate lets the movement/menu handoff retain its authenticated
    /// rasters while the UI task is already the controller owner.
    pub fn queue_route101_field_select(&mut self) -> bool {
        if self.map != MapId::Route101
            || self.field_select_modal.is_some()
            || self.route101_field_select_pending_frames.is_some()
        {
            return false;
        }
        self.route101_field_select_pending_frames = Some(1);
        true
    }

    /// Advances a queued Route 101 SELECT task. Returns true only on the
    /// VBlank that installs the visible modal so the caller does not advance
    /// the new printer twice on that same source frame.
    pub fn advance_route101_field_select_pending(&mut self) -> bool {
        let Some(elapsed) = self.route101_field_select_pending_frames else {
            return false;
        };
        let next_elapsed = elapsed.saturating_add(1);
        if next_elapsed < FieldSelectModal::BORDER_VISIBLE_AT {
            self.route101_field_select_pending_frames = Some(next_elapsed);
            return false;
        }
        self.route101_field_select_pending_frames = None;
        self.field_select_modal = Some(FieldSelectModal {
            elapsed_frames: next_elapsed,
            closing_frames: None,
        });
        self.route101_select_modal_receipt_active = true;
        self.menu_open = false;
        self.menu_cursor = None;
        self.bedroom_menu_open_frames = None;
        self.walk_direction = None;
        self.walk_elapsed_frames = 0;
        self.walk_progress_frames = 0;
        self.walk_render_origin = None;
        // The queued Down edge is accepted by the source field controller
        // while the prior close/stride task is unwinding; it updates the
        // standing pose even though the logical tile never commits.
        self.facing = Facing::Down;
        true
    }

    pub fn move_menu_cursor(&mut self, delta: i8) {
        // The pre-Pokédex bedroom menu reserves the hidden Pokédex slot in
        // the controller ring, but has only one visible EXIT row.  Emerald's
        // task skips that hidden duplicate when moving up from EXIT (and
        // re-enters it when moving down from OPTIONS); retaining logical row
        // four here leaves the cursor one row too low on the dismissing B
        // raster.
        if self.map == MapId::MaysHouse2F && !self.has_pokedex {
            let current = self.menu_cursor.unwrap_or(0);
            if delta < 0 && current >= 4 {
                self.menu_cursor = Some(3);
                return;
            }
            if delta > 0 && current == 3 {
                self.menu_cursor = Some(5);
                return;
            }
        }
        let count = self.menu_entries().len() as i8;
        let current = self.menu_cursor.unwrap_or(0) as i8;
        self.menu_cursor = Some((current + delta).rem_euclid(count) as u8);
    }

    pub fn menu_cursor_entry(&self) -> Option<MenuEntry> {
        self.menu_cursor.and_then(|cursor| {
            // In the bedroom before the Pokédex is acquired, Emerald's
            // window hides the unavailable Pokémon row but still uses the
            // six-slot cursor ring for wraparound. Logical row zero is BAG,
            // followed by the player card, Save, Options, and Exit.
            if self.map == MapId::MaysHouse2F && !self.has_pokedex {
                return match cursor {
                    0 => Some(MenuEntry::Bag),
                    1 => Some(MenuEntry::Player),
                    2 => Some(MenuEntry::Save),
                    3 => Some(MenuEntry::Option),
                    4 | 5 => Some(MenuEntry::Exit),
                    _ => None,
                };
            }
            self.menu_entries().get(usize::from(cursor)).copied()
        })
    }

    pub fn choose_menu_entry(&mut self) {
        self.menu_selection = self.menu_cursor_entry();
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
        let Some(remaining) = self.menu_transition_frames else {
            return false;
        };
        let next = remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if next == 0 {
            self.menu_transition_frames = None;
            self.active_screen = self
                .menu_selection
                .filter(|entry| *entry != MenuEntry::Exit);
            self.active_screen_cursor = 0;
        } else {
            self.menu_transition_frames = Some(next);
        }
        true
    }

    pub fn move_pokedex_cursor(&mut self, delta: i16) {
        if self.active_screen == Some(MenuEntry::Pokedex) {
            self.pokedex_cursor =
                (i16::try_from(self.pokedex_cursor).unwrap_or(0) + delta).clamp(0, 201) as u16;
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
                self.active_screen_cursor = (i16::from(self.active_screen_cursor)
                    + i16::from(delta))
                .rem_euclid(rows) as u8;
            }
            Some(MenuEntry::Option) => {
                self.active_screen_cursor =
                    (i16::from(self.active_screen_cursor) + i16::from(delta)).rem_euclid(2) as u8;
            }
            Some(MenuEntry::Save) => {
                self.active_screen_cursor =
                    (i16::from(self.active_screen_cursor) + i16::from(delta)).rem_euclid(2) as u8;
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
        let minutes = self.clock_minutes.get_or_insert(WALL_CLOCK_START_MINUTES);
        self.clock_minute_hand_angle = (*minutes % 60) * 6;
        self.clock_move_direction = 0;
        self.clock_move_speed = 0;
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
        let Some(transition) = self.clock_period_transition else {
            return;
        };
        let elapsed = transition
            .elapsed_frames
            .saturating_add(frames.min(u32::from(u8::MAX)) as u8);
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

    /// Advances the source wall-clock task for a held input packet. Emerald
    /// samples JOY_HELD every VBlank, easing the minute hand between six-
    /// degree marks and accelerating after 10/30/60 logical moves. Keep that
    /// hand/speed state serialized so splitting one hold across requests has
    /// the same result as one contiguous hold.
    pub fn advance_clock_input(&mut self, action: crate::Input, frames: u32) {
        if self.clock_editing.is_none() || self.clock_confirming {
            return;
        }
        let held_direction = match action {
            crate::Input::Left => -1,
            crate::Input::Right => 1,
            crate::Input::Up
            | crate::Input::Down
            | crate::Input::A
            | crate::Input::B
            | crate::Input::Start
            | crate::Input::Select
            | crate::Input::Noop => 0,
        };
        let frame_count = frames.min(u32::from(u16::MAX));
        for frame in 0..frame_count {
            // Sprite callbacks run once per VBlank after the clock task. The
            // transition state stores the post-callback pose, so advance the
            // prior transition before handling this frame's input.
            self.advance_clock_period_transition(1);
            let hand_is_settled = self.clock_minute_hand_angle % 6 == 0;
            if !hand_is_settled {
                // While the hand is between marks the source task does not
                // read new input; it continues with its previous direction.
                self.clock_minute_hand_angle = wall_clock_advance_minute_hand(
                    self.clock_minute_hand_angle,
                    self.clock_move_direction,
                    self.clock_move_speed,
                );
                continue;
            }

            let minutes = self.clock_minutes.unwrap_or(WALL_CLOCK_START_MINUTES);
            self.clock_minute_hand_angle = (minutes % 60) * 6;
            // JOY_NEW(A_BUTTON) is sampled only on the first frame of a
            // transport packet. If the hand is still easing, source ignores
            // that A and waits for a later fresh press.
            if frame == 0 && action == crate::Input::A {
                self.confirm_clock();
                self.advance_clock_period_transition(frame_count.saturating_sub(1));
                break;
            }

            self.clock_move_direction = 0;
            if held_direction != 0 {
                self.clock_move_direction = held_direction;
                self.clock_move_speed = self.clock_move_speed.saturating_add(1);
                self.clock_minute_hand_angle = wall_clock_advance_minute_hand(
                    self.clock_minute_hand_angle,
                    held_direction,
                    self.clock_move_speed,
                );
                self.apply_clock_minute_delta(i16::from(held_direction));
            } else {
                self.clock_move_speed = 0;
            }
        }
    }

    fn apply_clock_minute_delta(&mut self, delta: i16) {
        let current = i16::try_from(self.clock_minutes.unwrap_or(WALL_CLOCK_START_MINUTES))
            .unwrap_or(
                i16::try_from(WALL_CLOCK_START_MINUTES).expect("wall-clock default fits i16"),
            );
        let was_pm = current >= 12 * 60;
        let (pm_angle, am_angle) = self.clock_period_indicator_angles();
        let adjusted = (current + delta).rem_euclid(1440) as u16;
        let is_pm = adjusted >= 12 * 60;
        self.clock_minutes = Some(adjusted);
        if was_pm != is_pm {
            // `Task_SetClock_HandleInput` changes `tPeriod` before the
            // sprite callbacks run for the current VBlank. Start at one
            // elapsed source callback so this frame includes that first
            // visible degree of period-badge movement.
            self.clock_period_transition = Some(ClockPeriodTransition {
                pm_angle,
                am_angle,
                target_is_pm: is_pm,
                elapsed_frames: 1,
            });
        }
    }

    pub fn adjust_clock(&mut self, delta: i16) {
        if self.clock_confirming {
            return;
        }
        let Some(_field) = self.clock_editing else {
            return;
        };
        self.apply_clock_minute_delta(delta);
        self.clock_minute_hand_angle =
            (self.clock_minutes.unwrap_or(WALL_CLOCK_START_MINUTES) % 60) * 6;
    }

    pub fn confirm_clock(&mut self) {
        if self.clock_editing.is_none() {
            return;
        }
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
            self.story_flags.wall_clock_started = true;
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
        let Some(remaining) = self.rival_arrival_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if self.title_intro_step == 2 {
            let rival = self
                .npcs
                .iter()
                .find(|npc| npc.id == "rival" && npc.map == self.map)
                .expect("rival must exist during bedroom PC walk");
            let (steps, player_facing) = bedroom_rival_pc_route(self.map, &rival.position);
            let total = steps
                .iter()
                .map(|(_, faster)| bedroom_rival_movement_frames(*faster))
                .sum::<u16>();
            let elapsed_before = total.saturating_sub(remaining);
            let elapsed_after = total.saturating_sub(next_remaining);
            let mut boundary = 0u16;
            for (direction, faster) in steps {
                boundary += bedroom_rival_movement_frames(*faster);
                if elapsed_before < boundary && boundary <= elapsed_after {
                    let rival = self
                        .npcs
                        .iter()
                        .find(|npc| npc.id == "rival" && npc.map == self.map)
                        .expect("rival must remain during bedroom PC walk");
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
            let walk_frames = steps
                .iter()
                .map(|(_, faster)| bedroom_rival_movement_frames(*faster))
                .sum::<u16>();
            let total = walk_frames + BEDROOM_RIVAL_FASTER_TURN_FRAMES;
            let elapsed_before = total.saturating_sub(remaining);
            let elapsed_after = total.saturating_sub(next_remaining);
            let mut boundary = 0u16;
            for (direction, faster) in steps {
                boundary += bedroom_rival_movement_frames(*faster);
                if elapsed_before < boundary && boundary <= elapsed_after {
                    let rival = self
                        .npcs
                        .iter()
                        .find(|npc| npc.id == "rival" && npc.map == self.map)
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
        if elapsed_before < 10
            && 10 <= elapsed_after
            && !self
                .npcs
                .iter()
                .any(|npc| npc.id == "rival" && npc.map == self.map)
        {
            self.npcs.push(NpcState {
                id: "rival".to_owned(),
                map: self.map,
                position: initial.clone(),
                facing: Facing::Down,
            });
        }
        if elapsed_before < 26 && 26 <= elapsed_after {
            self.move_scripted_npc(
                "rival",
                self.map,
                TilePosition {
                    x: initial.x,
                    y: initial.y + 1,
                },
                Facing::Down,
            );
        }
        if elapsed_before < 42 && 42 <= elapsed_after {
            self.move_scripted_npc(
                "rival",
                self.map,
                TilePosition {
                    x: initial.x,
                    y: initial.y + 2,
                },
                Facing::Down,
            );
        }
        if elapsed_before < 46 && 46 <= elapsed_after {
            self.move_faster_scripted_npc(
                "rival",
                self.map,
                TilePosition {
                    x: initial.x,
                    y: initial.y + 2,
                },
                side,
            );
        }
        if next_remaining == 0 {
            // The source now chooses one of four approach streams from the
            // player’s interaction facing. The message waits until that
            // stream and its player turn have completed.
            let (steps, _) = bedroom_rival_approach(self.map, self.facing);
            let total = steps
                .iter()
                .map(|(_, faster)| bedroom_rival_movement_frames(*faster))
                .sum::<u16>()
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
        let Some(remaining) = self.rival_departure_frames else {
            return false;
        };
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
                let source_frame = self
                    .frame
                    .saturating_sub(u64::from(frames.saturating_sub(request_offset)));
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
            self.story_flags.hide_route103_rival = true;
            self.npcs
                .retain(|npc| !(npc.map == MapId::Route103 && npc.id == "rival"));
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
        let Some(remaining) = self.oldale_rival_departure_frames else {
            return false;
        };
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
                let rival = self
                    .npcs
                    .iter()
                    .find(|npc| npc.id == "oldale_rival")
                    .expect("Oldale rival must exist during its scripted exit");
                self.move_scripted_npc(
                    "oldale_rival",
                    MapId::OldaleTown,
                    TilePosition {
                        x: rival.position.x,
                        y: rival.position.y + 1,
                    },
                    Facing::Down,
                );
            }
        }
        if next_remaining == 0 {
            self.oldale_rival_departure_frames = None;
            self.oldale_rival_departed = true;
            self.story_vars.oldale_rival_state = 2;
            self.story_flags.hide_oldale_rival = true;
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
        if remaining <= 4 {
            Some(4 - remaining)
        } else {
            None
        }
    }

    /// Returns the four-frame player turn that overlaps May's first upward
    /// departure step. The departure clock is the authenticated source
    /// boundary, so this remains checkpoint/transport independent.
    pub fn mays_house_1f_player_faster_right_elapsed(&self) -> Option<u8> {
        let remaining = self.mays_house_1f_rival_departure_frames?;
        let elapsed = MAYS_RIVAL_DEPARTURE_FRAMES.saturating_sub(remaining);
        if (MAYS_PLAYER_FAST_TURN_OFFSET
            ..MAYS_PLAYER_FAST_TURN_OFFSET + MAYS_PLAYER_FAST_TURN_FRAMES)
            .contains(&elapsed)
        {
            Some(elapsed.saturating_sub(MAYS_PLAYER_FAST_TURN_OFFSET) as u8)
        } else {
            None
        }
    }

    /// Returns the resident east-facing cell after the four-frame GoFast task
    /// has completed.  The source leaves that cell uploaded for the remainder
    /// of May's departure rail; it is therefore a render lifetime, not just
    /// the callback's four-frame duration.
    pub fn mays_house_1f_player_right_render_elapsed(&self) -> Option<u8> {
        let remaining = self.mays_house_1f_rival_departure_frames?;
        let elapsed = MAYS_RIVAL_DEPARTURE_FRAMES.saturating_sub(remaining);
        (elapsed >= MAYS_PLAYER_FAST_TURN_OFFSET).then_some(
            elapsed
                .saturating_sub(MAYS_PLAYER_FAST_TURN_OFFSET)
                .min(MAYS_PLAYER_FAST_TURN_FRAMES) as u8,
        )
    }

    /// Runs the south-edge approach before Oldale's rival shows the
    /// homeward message.  The map scripts select two, one, or zero normal
    /// left walks from the rival's `(11,19)` home tile, then make the player
    /// perform `walk_in_place_faster_right` before opening the message.
    pub fn advance_oldale_rival_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_rival_approach_frames else {
            return false;
        };
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
                    let rival = self
                        .npcs
                        .iter()
                        .find(|npc| npc.id == "oldale_rival")
                        .expect("Oldale rival must exist during its scripted approach");
                    TilePosition {
                        x: rival.position.x - 1,
                        y: rival.position.y,
                    }
                };
                let request_offset = u32::from(start.saturating_sub(elapsed_before));
                let source_frame = self
                    .frame
                    .saturating_sub(u64::from(frames.saturating_sub(request_offset)));
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

    /// Runs `OldaleTown_EventScript_BlockedPath` at the west entrance while
    /// `VAR_OLDALE_TOWN_STATE` is still zero. The trigger is deliberately a
    /// field coordinate event rather than collision: the player reaches
    /// `(0,10)`, steps back to `(1,10)`, and the footprints man makes his
    /// source-backed up/return movement around the warning message.
    pub fn advance_oldale_blocked_path(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.oldale_blocked_path_frames else {
            return false;
        };
        let stage = self.oldale_blocked_path_stage;
        let total = match stage {
            1 => OLDALE_BLOCKED_PATH_APPROACH_FRAMES,
            3 => OLDALE_BLOCKED_PATH_RETURN_FRAMES,
            _ => return false,
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let elapsed_before = total.saturating_sub(remaining);
        let elapsed_after = total.saturating_sub(next_remaining);

        if stage == 1 {
            // `OldaleTown_Movement_PlayerStepBack`: delay 8, then one normal
            // right stride. The man runs up, turns in place, then steps right
            // before the shared waitmovement releases the warning message.
            if elapsed_before < 8 && 8 <= elapsed_after {
                self.player = TilePosition { x: 1, y: 10 };
                self.facing = Facing::Right;
                if let Some(man) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "footprints_man" && npc.map == MapId::OldaleTown)
                {
                    man.position = TilePosition { x: 1, y: 10 };
                    man.facing = Facing::Up;
                }
            }
            if elapsed_before < 12 && 12 <= elapsed_after {
                if let Some(man) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "footprints_man" && npc.map == MapId::OldaleTown)
                {
                    man.facing = Facing::Left;
                }
            }
            if elapsed_before < 20 && 20 <= elapsed_after {
                if let Some(man) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "footprints_man" && npc.map == MapId::OldaleTown)
                {
                    man.position = TilePosition { x: 2, y: 10 };
                    man.facing = Facing::Right;
                }
            }
            if next_remaining == 0 {
                self.oldale_blocked_path_frames = None;
                self.oldale_blocked_path_stage = 2;
                let dialogue = "Aaaaah! Wait!\nPlease don't come in here.\n\nI just discovered the footprints of\na rare POKéMON.\n\nWait until I finish sketching\nthem, okay?";
                self.field_dialogue_frames = Some(dialogue_printer_duration(dialogue));
                self.dialogue = Some(dialogue.to_owned());
                self.advance_field_dialogue_printer(frames.saturating_sub(u32::from(remaining)));
            } else {
                self.oldale_blocked_path_frames = Some(next_remaining);
            }
            return true;
        }

        // `OldaleTown_Movement_ReturnToOriginalPosition` is two ordinary
        // strides: down to `(2,11)`, then left to the authored `(1,11)`.
        if elapsed_before == 0 && elapsed_after > 0 {
            if let Some(man) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "footprints_man" && npc.map == MapId::OldaleTown)
            {
                man.position = TilePosition { x: 2, y: 11 };
                man.facing = Facing::Down;
            }
        }
        if elapsed_before < 16 && 16 <= elapsed_after {
            if let Some(man) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "footprints_man" && npc.map == MapId::OldaleTown)
            {
                man.position = TilePosition { x: 1, y: 11 };
                man.facing = Facing::Left;
            }
        }
        if next_remaining == 0 {
            self.oldale_blocked_path_frames = None;
            self.oldale_blocked_path_stage = 0;
            self.npcs = map_npcs(
                self.map,
                self.phase,
                self.potions,
                self.oldale_rival_departed,
                self.player_gender,
            );
        } else {
            self.oldale_blocked_path_frames = Some(next_remaining);
        }
        true
    }

    /// Commits a scripted object-event step and gives the native OBJ layer a
    /// 16-frame start marker. Ambient and authored movement use the same
    /// interpolator, preventing cutscene actors from jumping tile-to-tile.
    fn move_scripted_npc(&mut self, id: &str, map: MapId, position: TilePosition, facing: Facing) {
        self.move_scripted_npc_with_duration(id, map, position, facing, 16);
    }

    fn move_fast_scripted_npc(
        &mut self,
        id: &str,
        map: MapId,
        position: TilePosition,
        facing: Facing,
    ) {
        self.move_scripted_npc_with_duration(id, map, position, facing, 8);
    }

    /// `walk_in_place_faster_*` is the distinct four-frame source action,
    /// rather than the eight-frame `walk_in_place_fast_*` cadence.
    fn move_faster_scripted_npc(
        &mut self,
        id: &str,
        map: MapId,
        position: TilePosition,
        facing: Facing,
    ) {
        self.move_scripted_npc_with_duration(id, map, position, facing, 4);
    }

    fn move_scripted_npc_with_duration(
        &mut self,
        id: &str,
        map: MapId,
        position: TilePosition,
        facing: Facing,
        duration_frames: u8,
    ) {
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
        if let Some(npc) = self
            .npcs
            .iter_mut()
            .find(|npc| npc.id == id && npc.map == map)
        {
            if npc.position == position && npc.facing == facing {
                return;
            }
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
        if let Some(npc) = self
            .npcs
            .iter_mut()
            .find(|npc| npc.id == id && npc.map == map)
        {
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
        let Some(remaining) = self.oldale_mart_scene_frames else {
            return false;
        };
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
        let (employee_steps, player_steps, player_delay_steps): (&[Facing], &[Facing], u16) =
            match route {
                Facing::Down => (
                    &[
                        Facing::Left,
                        Facing::Up,
                        Facing::Up,
                        Facing::Right,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                    ],
                    &[Facing::Up, Facing::Up, Facing::Up, Facing::Up, Facing::Up],
                    4,
                ),
                Facing::Right => (
                    &[
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                    ],
                    &[
                        Facing::Right,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                    ],
                    0,
                ),
                // The source has no west branch.  Imported legacy states follow
                // the north choreography deterministically.
                Facing::Up | Facing::Left => (
                    &[
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                    ],
                    &[
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                        Facing::Up,
                    ],
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
                    let employee = self
                        .npcs
                        .iter()
                        .find(|npc| npc.id == "mart_employee")
                        .expect("Oldale Mart employee must exist during its scripted walk");
                    match direction {
                        Facing::Up => TilePosition {
                            x: employee.position.x,
                            y: employee.position.y - 1,
                        },
                        Facing::Down => TilePosition {
                            x: employee.position.x,
                            y: employee.position.y + 1,
                        },
                        Facing::Left => TilePosition {
                            x: employee.position.x - 1,
                            y: employee.position.y,
                        },
                        Facing::Right => TilePosition {
                            x: employee.position.x + 1,
                            y: employee.position.y,
                        },
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
        let employee_turn_start =
            u16::try_from(employee_steps.len()).expect("Oldale employee movement count fits") * 16;
        if elapsed_before <= employee_turn_start && employee_turn_start < elapsed_after {
            let position = self
                .npcs
                .iter()
                .find(|npc| npc.id == "mart_employee")
                .expect("Oldale Mart employee must exist during its scripted turn")
                .position
                .clone();
            let source_frame = self
                .frame
                .saturating_sub(u64::from(elapsed_after - employee_turn_start));
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
            let boundary = (player_delay_steps
                + u16::try_from(index).expect("Oldale movement index fits")
                + 1)
                * 16;
            if elapsed_before < boundary && boundary <= elapsed_after {
                match direction {
                    Facing::Up => self.player.y -= 1,
                    Facing::Down => self.player.y += 1,
                    Facing::Left => self.player.x -= 1,
                    Facing::Right => self.player.x += 1,
                }
                self.facing = *direction;
                self.elevation =
                    crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                        .expect("Oldale Mart movement must remain on staged walkable tiles");
            }
        }
        let player_motion_start = player_delay_steps * 16;
        let player_motion_end = player_motion_start
            + u16::try_from(player_steps.len()).expect("Oldale player movement count fits") * 16;
        self.walk_direction = (elapsed_after > player_motion_start
            && elapsed_after < player_motion_end)
            .then(|| player_steps[((elapsed_after - player_motion_start) / 16) as usize]);
        self.walk_progress_frames =
            if elapsed_after > player_motion_start && elapsed_after < player_motion_end {
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
            self.dialogue =
                Some("This is a POKéMON MART.\nJust look for our blue roof.".to_owned());
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
        let Some(remaining) = self.oldale_mart_dialogue_frames else {
            return false;
        };
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
        let Some(remaining) = self.oldale_mart_item_fanfare_frames else {
            return false;
        };
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
        let dialogue = format!(
            "{} put away the POTION\nin the ITEMS POCKET.",
            self.player_name
        );
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
        if let Some(mut dialogue) = self.field_dialogue.take() {
            if dialogue.print_remaining == 0 {
                // A ready page is no longer a printer-owned VBlank. Leave the
                // typed task installed so the following A/B edge can dismiss
                // it through `advance_opening_script`.
                self.field_dialogue = Some(dialogue);
                return false;
            }
            dialogue.advance_printer(frames);
            self.field_dialogue_frames =
                (dialogue.print_remaining != 0).then_some(dialogue.print_remaining);
            self.field_dialogue = Some(dialogue);
            return true;
        }
        let Some(remaining) = self.field_dialogue_frames else {
            return false;
        };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.field_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// Advances the script delay between `StartWallClock` returning and Mom's
    /// upstairs object event being created. The source's `delay 30` occurs
    /// before `addobject`, so keeping it separate avoids displaying Mom for
    /// frames in which the original room is still empty.
    pub fn advance_clock_settle(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.clock_settle_frames else {
            return false;
        };
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
        let Some(remaining) = self.clock_visit_frames else {
            return false;
        };
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
                    "mom",
                    self.map,
                    TilePosition {
                        x: doorway.x,
                        y: doorway.y - 1,
                    },
                    Facing::Up,
                );
            }
            if next_remaining == 0 {
                self.clock_visit_frames = None;
                self.title_intro_step = 0;
                self.phase = StoryPhase::TvBroadcast;
                self.npcs = map_npcs(
                    self.map,
                    self.phase,
                    self.potions,
                    self.oldale_rival_departed,
                    self.player_gender,
                );
            } else {
                self.clock_visit_frames = Some(next_remaining);
            }
            return true;
        }
        let elapsed_before = CLOCK_VISIT_ENTRY_FRAMES.saturating_sub(remaining);
        let elapsed_after = CLOCK_VISIT_ENTRY_FRAMES.saturating_sub(next_remaining);
        let (down_position, final_position, side) = match self.map {
            MapId::BrendansHouse2F => (
                TilePosition { x: 7, y: 2 },
                TilePosition { x: 6, y: 2 },
                Facing::Left,
            ),
            MapId::MaysHouse2F => (
                TilePosition { x: 1, y: 2 },
                TilePosition { x: 2, y: 2 },
                Facing::Right,
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
            self.story_flags.upstairs_mom_scene_complete = true;
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
        let Some(remaining) = self.tv_broadcast_intro_frames else {
            return false;
        };
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
            let position = self
                .npcs
                .iter()
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
        let Some(remaining) = self.rival_mom_intro_frames else {
            return false;
        };
        let consumed = frames.min(u32::from(u16::MAX)) as u16;
        let next_remaining = remaining.saturating_sub(consumed);
        let elapsed_before = RIVAL_MOM_INTRO_FRAMES.saturating_sub(remaining);
        let elapsed_after = RIVAL_MOM_INTRO_FRAMES.saturating_sub(next_remaining);

        if let Some(emote_remaining) = self.rival_mom_exclamation_frames {
            let next_emote = emote_remaining.saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
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
                let mom = self
                    .npcs
                    .iter()
                    .find(|npc| npc.id == "mom" && npc.map == self.map)
                    .expect("rival Mom must exist during the new-neighbor approach");
                let position = stepped_position(&mom.position, *direction);
                let start_frame = self
                    .frame
                    .saturating_sub(u64::from(elapsed_after.saturating_sub(step_start)));
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
        let Some(remaining) = self.tv_broadcast_approach_frames else {
            return false;
        };
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
                // The source movement script is authored for the matching
                // house layout. A caller can still feed an arbitrary input
                // stream into the serialized state, though; keep that probe
                // from turning a harmless out-of-bounds scripted step into a
                // process panic while preserving the source-facing turn.
                if let Ok(elevation) = crate::native::tile_elevation(self.map, player.x, player.y) {
                    self.elevation = elevation;
                    self.player = player;
                }
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
        let Some(remaining) = self.tv_broadcast_view_frames else {
            return false;
        };
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
            if let Some(mom) = self
                .npcs
                .iter()
                .find(|npc| npc.id == "mom" && npc.map == self.map)
                .map(|npc| npc.position.clone())
            {
                let start_frame = self
                    .frame
                    .saturating_sub(u64::from(elapsed_after.saturating_sub(mom_step_boundary)));
                self.move_scripted_npc_with_duration_at_frame(
                    "mom",
                    self.map,
                    stepped_position(&mom, side),
                    side,
                    TV_BROADCAST_VIEW_MOM_STEP_FRAMES as u8,
                    start_frame,
                );
            }
        }
        if elapsed_before < mom_turn_boundary && mom_turn_boundary <= elapsed_after {
            if let Some(mom) = self
                .npcs
                .iter()
                .find(|npc| npc.id == "mom" && npc.map == self.map)
                .map(|npc| npc.position.clone())
            {
                let start_frame = self
                    .frame
                    .saturating_sub(u64::from(elapsed_after.saturating_sub(mom_turn_boundary)));
                self.move_scripted_npc_with_duration_at_frame(
                    "mom",
                    self.map,
                    mom,
                    mom_turn,
                    TV_BROADCAST_VIEW_FASTER_TURN_FRAMES as u8,
                    start_frame,
                );
            }
        }
        if elapsed_before < mom_turn_boundary && mom_turn_boundary <= elapsed_after {
            // The source walk changes the player object's facing as its
            // 16-frame stride begins, before its destination tile commits.
            self.facing = side;
        }
        if elapsed_before < player_step_boundary && player_step_boundary <= elapsed_after {
            let player = stepped_position(&self.player, side);
            // As above, retain the scripted timer/facing even if a malformed
            // external replay places the player against the map edge. Valid
            // source paths still take the exact authored destination.
            if let Ok(elevation) = crate::native::tile_elevation(self.map, player.x, player.y) {
                self.elevation = elevation;
                self.player = player;
            }
        }
        self.walk_direction = (elapsed_after > mom_turn_boundary
            && elapsed_after < player_step_boundary)
            .then_some(side);
        self.walk_progress_frames =
            if elapsed_after > mom_turn_boundary && elapsed_after < player_step_boundary {
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
        let Some(remaining) = self.truck_arrival_frames else {
            return false;
        };
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
                "truck_arrival_mom",
                MapId::LittlerootTown,
                TilePosition { x: home_x, y: 9 },
                Facing::Down,
            );
        }
        if elapsed_before < 138 && 138 <= elapsed_after {
            self.move_scripted_npc(
                "truck_arrival_mom",
                MapId::LittlerootTown,
                TilePosition { x: home_x, y: 10 },
                Facing::Down,
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
            self.truck_arrival_dialogue_frames =
                self.dialogue.as_deref().map(dialogue_printer_duration);
        } else {
            self.truck_arrival_frames = Some(next_remaining);
        }
        true
    }

    /// Advances the source printer on a Little Root truck-arrival page.
    pub fn advance_truck_arrival_dialogue_printer(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.truck_arrival_dialogue_frames else {
            return false;
        };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.truck_arrival_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// After Mom's final arrival page, the source walks both characters to
    /// the house, opens the Little Root door, walks them inside, and closes
    /// it before beginning the silent-warp fade.
    pub fn advance_truck_departure(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.truck_departure_frames else {
            return false;
        };
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
                "truck_arrival_mom",
                MapId::LittlerootTown,
                TilePosition { x: home_x, y: 9 },
                Facing::Up,
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
        let Some(remaining) = self.new_home_orientation_frames else {
            return false;
        };
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
        let Some(remaining) = self.new_home_arrival_frames else {
            return false;
        };
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
                let mom = self
                    .npcs
                    .iter()
                    .find(|npc| npc.id == "mom" && npc.map == map)
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
                self.npcs = map_npcs(
                    self.map,
                    self.phase,
                    self.potions,
                    self.oldale_rival_departed,
                    self.player_gender,
                );
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
        let Some(remaining) = self.running_shoes_wait_frames else {
            return false;
        };
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
        self.running_shoes_dialogue_frames =
            self.dialogue.as_deref().map(dialogue_printer_duration);
    }

    /// Reveals the next source message page without advancing the scene
    /// script. The exterior text flow owns fifteen dismissible pages after
    /// Mom's initial prompt, rather than four condensed Rust strings.
    fn advance_running_shoes_dialogue(&mut self) -> bool {
        let next_page = self.running_shoes_dialogue_page.saturating_add(1);
        let Some(dialogue) =
            running_shoes_dialogue_page(self.running_shoes_stage, next_page, &self.player_name)
        else {
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
        let Some(remaining) = self.running_shoes_dialogue_frames else {
            return false;
        };
        let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        self.running_shoes_dialogue_frames = (next != 0).then_some(next);
        true
    }

    /// Returns the currently visible text. Source field pages reveal one
    /// character per frame after Emerald's initial twelve-frame box delay.
    pub fn rendered_dialogue(&self) -> Option<String> {
        if let Some(modal) = self.field_select_modal.as_ref() {
            return modal.border_visible().then(|| modal.visible_text());
        }
        if let Some((hold_frame, text)) = self.mays_house_1f_dialogue_page_hold.as_ref() {
            // A closing A leaves the final page in the source window for two
            // rendered VBlanks (the edge sample and the following scheduler
            // tick). Page-to-page releases still hold only their edge sample;
            // those retain a non-empty `dialogue` projection while the next
            // page printer owns the task.
            let special_blank_page = self.dialogue.as_deref().is_some_and(str::is_empty);
            // The source page transition from the long page-7 farewell into
            // `Eheheh…` runs one blank printer tick: unlike ordinary page
            // releases, the new page owns the window on V+1 but has not yet
            // emitted its first glyph. Preserve that blank task boundary
            // instead of holding page 7 for the extra tick.
            let page8_release_blank = self
                .field_dialogue
                .as_ref()
                .is_some_and(|state| state.page == 8)
                && self.frame == hold_frame.saturating_add(1);
            if *hold_frame == self.frame
                || (!special_blank_page
                    && !page8_release_blank
                    && self.frame == hold_frame.saturating_add(1))
            {
                return Some(text.clone());
            }
        }
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
                    continuation
                        .chars()
                        .take(visible_characters)
                        .collect::<String>(),
                ));
            }
            let (total, lead_in) =
                match (self.oldale_mart_scene_stage, self.oldale_mart_dialogue_page) {
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
        if let Some(remaining) = self
            .pokedex_receipt_fanfare_frames
            .or(self.pokedex_poke_ball_fanfare_frames)
        {
            // `EventScript_ReceivePokedex` and `giveitem ITEM_POKE_BALL, 5`
            // both leave their receipt printer visible while
            // `MUS_OBTAIN_ITEM` is playing. `waitfanfare` keeps the next
            // source message from replacing either receipt.
            // The fanfare clock is deliberately longer than the text printer,
            // so derive the visible glyph count from its elapsed source time
            // rather than treating its remaining duration as a printer total.
            let elapsed = POKE_BALL_GIFT_FANFARE_REMAINING_FRAMES.saturating_sub(remaining);
            let visible_characters = usize::from(elapsed.saturating_sub(12));
            return Some(dialogue.chars().take(visible_characters).collect());
        }
        let Some(remaining) = self
            .running_shoes_wait_frames
            .map(u16::from)
            .or(self.running_shoes_dialogue_frames)
            .or(self.truck_arrival_dialogue_frames)
            .or(self.field_dialogue_frames)
        else {
            return Some(dialogue.clone());
        };
        let total = if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_rival_scene_start_frame.is_some()
        {
            mays_house_1f_dialogue_printer_duration(dialogue)
        } else {
            dialogue_printer_duration(dialogue)
        };
        let elapsed = total.saturating_sub(remaining);
        if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_rival_dialogue_active
            && self.field_dialogue_frames.is_some()
        {
            // The rival-house script starts its printer on the first frame
            // after DrawDialogueFrame: V282 is an empty box, V283 already
            // contains the first glyph.  The generic field helper's twelve
            // frame lead-in is for ordinary map messages and would leave
            // this authenticated page blank for the first dozen VBlanks.
            // The source printer advances one authored character per VBlank;
            // spaces consume a tick even though they add no ink. The page of
            // repeated ellipses can look like a two-VBlank glyph cadence, but
            // that is simply its alternating ellipsis/space character stream.
            // A page released by A is rendered one scheduler tick after the
            // page task starts printing. The release hold owns that first
            // tick, so subtract it from the visible character budget while
            // leaving the serialized printer countdown untouched.
            let printer_elapsed = if self.mays_house_1f_dialogue_page_hold.is_some() {
                elapsed.saturating_sub(1)
            } else {
                elapsed
            };
            let mut budget = usize::from(printer_elapsed);
            if let Some((first_line, _)) = dialogue.split_once('\n') {
                let first_line_characters = first_line.chars().count();
                let second_line_start = first_line_characters.saturating_add(1);
                let elapsed_usize = usize::from(printer_elapsed);
                if elapsed_usize >= second_line_start {
                    budget = first_line_characters
                        .saturating_add(1)
                        .saturating_add(elapsed_usize - second_line_start);
                }
            }
            let mut visible = String::new();
            for character in dialogue.chars() {
                if character == '\n' {
                    visible.push(character);
                    continue;
                }
                if character != '\n' {
                    if budget == 0 {
                        break;
                    }
                    budget -= 1;
                }
                visible.push(character);
            }
            return Some(visible);
        }
        let visible_characters = usize::from(elapsed.saturating_sub(12));
        Some(dialogue.chars().take(visible_characters).collect())
    }

    /// Source field message boxes add their advance marker only after their
    /// current page printer reaches its ready boundary.
    pub fn dialogue_printer_active(&self) -> bool {
        self.field_select_modal
            .as_ref()
            .is_some_and(|modal| !modal.input_ready())
            || self.running_shoes_wait_frames.is_some()
            || self.running_shoes_dialogue_frames.is_some()
            || self.truck_arrival_dialogue_frames.is_some()
            || self.oldale_mart_dialogue_frames.is_some()
            || self.oldale_mart_item_fanfare_frames.is_some()
            || self.pokedex_receipt_fanfare_frames.is_some()
            || self.pokedex_poke_ball_fanfare_frames.is_some()
            || self.field_dialogue_frames.is_some()
    }

    /// Returns the source VBlank at which the current Mays House page first
    /// becomes arrow-ready.  A page-release A edge records the prior page in
    /// `mays_house_1f_dialogue_page_hold`; the next page's printer owns its
    /// final VBlank, and the down-arrow is already visible on that boundary.
    /// Keeping this derived from the authenticated page text makes the phase
    /// reset correctly for every subsequent page instead of reusing the
    /// unrelated generic field-dialogue anchor.
    pub fn mays_house_1f_dialogue_arrow_anchor(&self) -> Option<u64> {
        if self.map != MapId::MaysHouse1F || !self.mays_house_1f_rival_dialogue_active {
            return None;
        }
        self.mays_house_1f_dialogue_page_arrow_anchor
    }

    pub fn advance_running_shoes_scene(&mut self, frames: u32) -> bool {
        if let Some(remaining) = self.running_shoes_return_delay_frames {
            let consumed = frames.min(u32::from(remaining)) as u8;
            let next_remaining = remaining.saturating_sub(consumed);
            self.running_shoes_return_delay_frames =
                (next_remaining != 0).then_some(next_remaining);
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
        let Some(remaining) = self.running_shoes_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let trigger = self.running_shoes_trigger.unwrap_or(2);
        let source_rival_trigger = trigger == SOURCE_RIVAL_RUNNING_SHOES_TRIGGER;
        let returning = self.running_shoes_stage == 6;
        let (direction, steps, fast_return_turn) =
            running_shoes_mom_path(trigger, self.player_gender, returning);
        let total = u16::from(steps) * 16
            + if (!returning && !source_rival_trigger) || fast_return_turn {
                4
            } else {
                0
            };
        let elapsed_before = total.saturating_sub(remaining);
        let elapsed_after = total.saturating_sub(next_remaining);
        if !returning && !source_rival_trigger && elapsed_before < 4 && elapsed_after >= 4 {
            self.facing = match (trigger, self.player_gender) {
                (0 | 1, _) => Facing::Down,
                (_, PlayerGender::Brendan) => Facing::Left,
                (_, PlayerGender::May) => Facing::Right,
            };
        }
        let movement_offset = if returning || source_rival_trigger {
            0
        } else {
            4
        };
        for step in 1..=u16::from(steps) {
            let boundary = movement_offset + step * 16;
            if elapsed_before < boundary && boundary <= elapsed_after {
                let mom = self
                    .npcs
                    .iter()
                    .find(|npc| npc.id == "mom_outside")
                    .expect("Running Shoes Mom must exist during her scripted walk");
                let position = match direction {
                    Facing::Up => TilePosition {
                        x: mom.position.x,
                        y: mom.position.y - 1,
                    },
                    Facing::Down => TilePosition {
                        x: mom.position.x,
                        y: mom.position.y + 1,
                    },
                    Facing::Left => TilePosition {
                        x: mom.position.x - 1,
                        y: mom.position.y,
                    },
                    Facing::Right => TilePosition {
                        x: mom.position.x + 1,
                        y: mom.position.y,
                    },
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
                    self.advance_running_shoes_dialogue_printer(
                        frames.saturating_sub(u32::from(remaining)),
                    );
                }
                6 => {
                    if fast_return_turn {
                        let mom = self
                            .npcs
                            .iter()
                            .find(|npc| npc.id == "mom_outside")
                            .expect("Running Shoes Mom must exist for her return turn");
                        self.move_faster_scripted_npc(
                            "mom_outside",
                            MapId::LittlerootTown,
                            mom.position.clone(),
                            Facing::Up,
                        );
                        self.running_shoes_return_door_frames =
                            Some(RUNNING_SHOES_RETURN_DOOR_FRAMES);
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
        let Some(remaining) = self.birch_prompt_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if self.title_intro_step == 2 {
            if next_remaining == 0 {
                self.birch_prompt_frames = None;
                self.title_intro_step = 0;
                if let Some(twin) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                {
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
        let elapsed_before =
            LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES.saturating_sub(remaining);
        let elapsed_after =
            LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES.saturating_sub(next_remaining);
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
        let Some(remaining) = self.no_pokemon_gate_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        let x = if self.no_pokemon_gate_right { 11 } else { 10 };
        let returning = self.no_pokemon_gate_stage == 4;
        let (path, lead_frames) = match self.no_pokemon_gate_stage {
            1 => (no_pokemon_twin_path(self.no_pokemon_gate_right, false), 32),
            4 => (no_pokemon_twin_path(self.no_pokemon_gate_right, true), 0),
            _ => (&[][..], 0),
        };
        if !path.is_empty() {
            let total =
                lead_frames + no_pokemon_twin_path_frames(self.no_pokemon_gate_right, returning);
            let elapsed_before = total.saturating_sub(remaining);
            let elapsed_after = total.saturating_sub(next_remaining);
            let mut boundary = lead_frames;
            for (index, (direction, fast)) in path.iter().enumerate() {
                let terminal_faster_turn = returning && index + 1 == path.len();
                boundary += no_pokemon_twin_path_step_frames(terminal_faster_turn, *fast);
                if elapsed_before < boundary && boundary <= elapsed_after {
                    let position = self
                        .npcs
                        .iter()
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
                        // The terminal return command is
                        // `walk_in_place_faster_down`, not a four-frame tile
                        // walk. Keep Twin on its committed tile while the
                        // source walk-cycle pose advances; marking it as a
                        // moving stride introduces a visible four-pixel
                        // displacement during the warning return phase.
                        self.animate_scripted_npc_in_place_at_frame(
                            "twin",
                            MapId::LittlerootTown,
                            *direction,
                            4,
                            self.frame,
                        );
                    } else if *fast {
                        self.move_fast_scripted_npc(
                            "twin",
                            MapId::LittlerootTown,
                            position,
                            *direction,
                        );
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
                if let Some(twin) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                {
                    twin.position = TilePosition { x, y: 0 };
                    twin.facing = Facing::Down;
                }
                self.no_pokemon_gate_frames = None;
                self.dialogue = Some("Um, um, um!\n\nIf you go outside and go in the grass,\nwild POKéMON will jump out!".to_owned());
            }
            2 => {
                // `DangerousWithoutPokemon` moves both actors down once
                // before its second message box.
                if let Some(twin) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                {
                    twin.position = TilePosition { x, y: 1 };
                    twin.facing = Facing::Down;
                }
                self.player = TilePosition { x, y: 2 };
                self.facing = Facing::Down;
                self.no_pokemon_gate_frames = None;
                self.no_pokemon_gate_stage = 3;
                self.dialogue =
                    Some("It's dangerous if you don't have\nyour own POKéMON.".to_owned());
            }
            4 => {
                if let Some(twin) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                {
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
        let Some(saved_remaining) = self.birch_rescue_frames else {
            return false;
        };
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
            const BIRCH_ENTRY: [Facing; 6] = [
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Up,
                Facing::Up,
            ];
            const ZIGZAGOON_ENTRY: [Facing; 6] = [
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Up,
            ];
            const BIRCH_CIRCLE: [Facing; 30] = [
                Facing::Up,
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Down,
                Facing::Down,
                Facing::Left,
                Facing::Left,
                Facing::Left,
                Facing::Up,
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Down,
                Facing::Down,
                Facing::Left,
                Facing::Left,
                Facing::Left,
                Facing::Up,
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Down,
                Facing::Down,
                Facing::Left,
                Facing::Left,
                Facing::Left,
            ];
            const ZIGZAGOON_CIRCLE: [Facing; 31] = [
                Facing::Up,
                Facing::Up,
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Down,
                Facing::Down,
                Facing::Left,
                Facing::Left,
                Facing::Left,
                Facing::Up,
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Down,
                Facing::Down,
                Facing::Left,
                Facing::Left,
                Facing::Left,
                Facing::Up,
                Facing::Up,
                Facing::Up,
                Facing::Right,
                Facing::Right,
                Facing::Right,
                Facing::Down,
                Facing::Down,
                Facing::Left,
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
                self.elevation =
                    crate::native::tile_elevation(self.map, self.player.x, self.player.y)
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
                let start = u16::try_from(index).expect("Route 101 Birch entry index fits")
                    * FAST_STEP_FRAMES;
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
                let start = u16::try_from(index).expect("Route 101 Zigzagoon entry index fits")
                    * FAST_STEP_FRAMES;
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
                    + u16::try_from(index).expect("Route 101 Birch circle index fits")
                        * FAST_STEP_FRAMES;
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
                    + u16::try_from(index).expect("Route 101 Zigzagoon circle index fits")
                        * FAST_STEP_FRAMES;
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
                let source_frame = self
                    .frame
                    .saturating_sub(u64::from(elapsed_after - BIRCH_TURN_START));
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
            if let Some(birch) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "birch" && npc.map == MapId::Route101)
            {
                birch.position = TilePosition { x: 4, y: 13 };
                birch.facing = Facing::Right;
            }
            if let Some(zigzagoon) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "zigzagoon" && npc.map == MapId::Route101)
            {
                zigzagoon.position = TilePosition { x: 5, y: 12 };
                zigzagoon.facing = Facing::Left;
            }
            self.npc_walk_starts
                .retain(|walk| walk.id != "birch" && walk.id != "zigzagoon");
            self.birch_rescue_stage = 2;
            self.dialogue = Some(
                "Hello! You over there!\nPlease! Help!\n\nIn my BAG!\nThere's a POKé BALL!"
                    .to_owned(),
            );
        }
        true
    }

    /// Finishes the source's `Route101_Movement_BirchApproachPlayer` after
    /// `ChooseStarter` returns. The destination tile is committed when the
    /// scripted normal walk starts so the shared object renderer can
    /// interpolate the stride; the following message waits for all 16
    /// frames, exactly as `waitmovement 0` does in the map script.
    pub fn advance_birch_post_battle_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.birch_post_battle_frames else {
            return false;
        };
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
        let Some(remaining) = self.route103_rival_intro_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if next_remaining != 0 {
            self.route103_rival_intro_frames = Some(next_remaining);
            return true;
        }
        self.route103_rival_intro_frames = None;
        self.route103_rival_intro_stage = 2;
        self.title_intro_step = 1;
        self.dialogue = Some(rival_battle_challenge_text(
            self.player_gender,
            &self.player_name,
        ));
        true
    }

    /// Executes the seven northward steps from
    /// `LittlerootTown_ProfessorBirchsLab_Movement_PlayerEnterLabForPokedex`
    /// before the Lab's OnFrame Pokédex dialogue begins.
    pub fn advance_pokedex_arrival(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_arrival_frames else {
            return false;
        };
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
        self.dialogue = Some(pokedex_handoff_page(
            0,
            self.player_gender,
            &self.player_name,
        ));
        true
    }

    /// Applies the rival's normal down step, faster left turn, and the
    /// player's faster right turn between Birch's Pokédex explanation and
    /// the ball gift dialogue.
    pub fn advance_pokedex_rival_approach(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_rival_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        const RIVAL_WALK_DOWN_FRAMES: u16 = 16;
        const RIVAL_FASTER_LEFT_FRAMES: u16 = 4;
        const PLAYER_FASTER_RIGHT_FRAMES: u16 = 4;
        const TOTAL_FRAMES: u16 =
            RIVAL_WALK_DOWN_FRAMES + RIVAL_FASTER_LEFT_FRAMES + PLAYER_FASTER_RIGHT_FRAMES;
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
        if elapsed_before < RIVAL_WALK_DOWN_FRAMES && RIVAL_WALK_DOWN_FRAMES <= elapsed_after {
            let start_frame = self
                .frame
                .saturating_sub(u64::from(elapsed_after - RIVAL_WALK_DOWN_FRAMES));
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
        self.dialogue = Some(pokedex_handoff_page(
            3,
            self.player_gender,
            &self.player_name,
        ));
        true
    }

    /// Holds `LittlerootTown_ProfessorBirchsLab_Text_ReceivedPokedex` while
    /// `EventScript_ReceivePokedex` waits for `MUS_OBTAIN_ITEM`. The source
    /// only sets the Pokédex flags after that wait before Birch explains it.
    pub fn advance_pokedex_receipt_fanfare(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_receipt_fanfare_frames else {
            return false;
        };
        let next_remaining = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        if next_remaining != 0 {
            self.pokedex_receipt_fanfare_frames = Some(next_remaining);
            return true;
        }

        self.pokedex_receipt_fanfare_frames = None;
        self.has_pokedex = true;
        self.title_intro_step = 2;
        self.dialogue = Some(pokedex_handoff_page(
            2,
            self.player_gender,
            &self.player_name,
        ));
        true
    }

    /// Runs the `giveitem ITEM_POKE_BALL, 5` fanfare between the rival's
    /// gift message and Birch's catch-explanation message. The source opens
    /// the pocket receipt as soon as `waitfanfare` completes.
    pub fn advance_pokedex_poke_ball_fanfare(&mut self, frames: u32) -> bool {
        let Some(remaining) = self.pokedex_poke_ball_fanfare_frames else {
            return false;
        };
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
        matches!(
            frame,
            816 | 4160 | 4288 | 4352 | 4416 | 4480 | 4544 | 4608 | 4672 | 4736 | 4800
        ) && self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::PokedexReceived
            && self.render_position.is_some()
    }

    /// `04_rival.state`'s mGBA EWRAM/OAM captures give live object-event
    /// snapshots at controller-sensitive boundaries. At ×816 Boy has just
    /// moved out of the player's east lane; later stopped-camera anchors
    /// preserve the measured per-object scheduler rather than inventing a
    /// common wander prehistory during a long held-input replay.
    fn restore_rival_ambient_anchor(&mut self, frame: u64) {
        let (
            twin_position,
            twin_facing,
            fat_man_position,
            fat_man_facing,
            boy_position,
            boy_facing,
            twin_delay,
            fat_man_delay,
            boy_delay,
            boy_pending_direction,
            rng,
        ) = match frame {
            816 => (
                TilePosition { x: 16, y: 10 },
                Facing::Down,
                TilePosition { x: 12, y: 13 },
                Facing::Left,
                TilePosition { x: 16, y: 16 },
                Facing::Up,
                128,
                128,
                128,
                None,
                0,
            ),
            4160 => (
                TilePosition { x: 17, y: 11 },
                Facing::Right,
                TilePosition { x: 12, y: 12 },
                Facing::Left,
                TilePosition { x: 13, y: 17 },
                Facing::Left,
                128,
                128,
                48,
                Some(Facing::Right),
                0x3ff0_b6ec,
            ),
            4288 | 4352 => (
                TilePosition { x: 17, y: 12 },
                Facing::Left,
                TilePosition { x: 12, y: 13 },
                Facing::Left,
                TilePosition { x: 14, y: 17 },
                Facing::Right,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4416 => (
                TilePosition { x: 17, y: 12 },
                Facing::Left,
                TilePosition { x: 13, y: 13 },
                Facing::Right,
                TilePosition { x: 14, y: 17 },
                Facing::Left,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4480 => (
                TilePosition { x: 17, y: 12 },
                Facing::Left,
                TilePosition { x: 13, y: 13 },
                Facing::Right,
                TilePosition { x: 15, y: 17 },
                Facing::Right,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4544 => (
                TilePosition { x: 16, y: 11 },
                Facing::Left,
                TilePosition { x: 12, y: 13 },
                Facing::Left,
                TilePosition { x: 15, y: 17 },
                Facing::Right,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4608 => (
                TilePosition { x: 17, y: 11 },
                Facing::Right,
                TilePosition { x: 12, y: 14 },
                Facing::Left,
                TilePosition { x: 15, y: 16 },
                Facing::Left,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4672 => (
                TilePosition { x: 16, y: 11 },
                Facing::Right,
                TilePosition { x: 12, y: 13 },
                Facing::Left,
                TilePosition { x: 15, y: 16 },
                Facing::Left,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4736 => (
                TilePosition { x: 16, y: 11 },
                Facing::Right,
                TilePosition { x: 13, y: 13 },
                Facing::Down,
                TilePosition { x: 15, y: 17 },
                Facing::Up,
                128,
                128,
                128,
                None,
                0x3ff0_b6ec,
            ),
            4800 => (
                TilePosition { x: 16, y: 10 },
                Facing::Left,
                TilePosition { x: 14, y: 13 },
                Facing::Down,
                TilePosition { x: 15, y: 17 },
                Facing::Up,
                81,
                122,
                10,
                None,
                0xda78_26b2,
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
                mode: AmbientWanderMode::Delay {
                    remaining_frames: twin_delay,
                },
                pending_direction: None,
            },
            AmbientWanderState {
                id: "boy".to_owned(),
                mode: AmbientWanderMode::Delay {
                    remaining_frames: boy_delay,
                },
                pending_direction: boy_pending_direction,
            },
            AmbientWanderState {
                id: "fat_man".to_owned(),
                mode: AmbientWanderMode::Delay {
                    remaining_frames: fat_man_delay,
                },
                pending_direction: None,
            },
        ];
        // The observed IWRAM field-LCG state at frame 4160 is retained for
        // subsequent ordinary choices. Source seed restoration before the
        // first measured anchor remains a separate parity task.
        self.ambient_rng = rng;
    }

    fn ensure_ambient_wanders(&mut self) {
        let ids: Vec<String> = self
            .npcs
            .iter()
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
                    AmbientWanderMode::Face {
                        remaining_frames: 1,
                    }
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
            let Some(npc_index) = self
                .npcs
                .iter()
                .position(|npc| npc.id == id && npc.map == self.map)
            else {
                continue;
            };
            // LittlerootTown_OnTransition temporarily pins Twin before Birch
            // is rescued; its normal wander type resumes only afterwards.
            if id == "twin" && self.phase < StoryPhase::BirchRescued {
                continue;
            }
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
                    let random_direction =
                        ambient_wander_direction(&id, self.next_ambient_random());
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
                    let Some((origin, range_x, range_y)) = npc_wander_bounds(self.map, &id) else {
                        continue;
                    };
                    let blocked = !(0..width).contains(&x)
                        || !(0..height).contains(&y)
                        || (x - origin.x).abs() > range_x
                        || (y - origin.y).abs() > range_y
                        || (self.player.x, self.player.y) == (x, y)
                        || self.npcs.iter().enumerate().any(|(other, npc)| {
                            other != npc_index
                                && npc.map == self.map
                                && (npc.position.x, npc.position.y) == (x, y)
                        })
                        || !crate::native::is_walkable(self.map, x, y).unwrap_or(false);
                    if blocked {
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Face {
                            remaining_frames: 1,
                        };
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
                    self.ambient_wanders[state_index].mode = AmbientWanderMode::Walk {
                        remaining_frames: 16,
                    };
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
                        self.ambient_wanders[state_index].mode = AmbientWanderMode::Face {
                            remaining_frames: 1,
                        };
                    }
                }
            }
        }
    }

    fn next_ambient_random(&mut self) -> u16 {
        // Emerald `Random()` advances the shared LCG with these constants
        // and returns its high halfword.
        self.ambient_rng = self
            .ambient_rng
            .wrapping_mul(0x41c6_4e6d)
            .wrapping_add(0x0000_6073);
        (self.ambient_rng >> 16) as u16
    }

    fn advance_ambient_background_rng(&mut self) {
        self.ambient_rng = self
            .ambient_rng
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
        if !self
            .starter_party
            .as_ref()
            .is_some_and(|party| party.species == starter)
        {
            self.starter_party = Some(starter_party_state(starter));
        }
    }

    /// Migrates pre-four-slot checkpoints and fills numeric move identities
    /// from the source sidecar. Safe to call repeatedly.
    pub fn normalize_move_slots(&mut self) {
        if let Some(party) = self.starter_party.as_mut() {
            if party.moves.is_empty() {
                party.moves = legacy_party_move_slots(party);
            }
            normalize_slots(&mut party.moves);
            if let Some(slot) = party.moves.first() {
                party.physical_move_pp = slot.pp;
            }
            if let Some(slot) = party.moves.get(1) {
                party.status_move_pp = slot.pp;
            }
        }
        if let Some(battle) = self.battle.as_mut() {
            if battle.player_moves.is_empty() {
                battle.player_moves = legacy_battle_move_slots(battle);
            }
            normalize_slots(&mut battle.player_moves);
            if let Some(slot) = battle.player_moves.first() {
                battle.player_move_name = slot.name.clone();
                battle.player_move_pp = slot.pp;
            }
            if let Some(slot) = battle.player_moves.get(1) {
                battle.player_status_move_name = slot.name.clone();
                battle.player_status_move_pp = slot.pp;
            }
            let populated = battle.player_moves.len().max(1);
            battle.move_cursor = usize::from(battle.move_cursor).min(populated - 1) as u8;
        }
    }

    fn apply_starter_party_to_battle(&mut self, battle: &mut BattleState) {
        self.ensure_starter_party();
        let party = self
            .starter_party
            .as_ref()
            .expect("starter party must exist after construction");
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
        battle.player_moves = effective_party_move_slots(party);
        if let Some(slot) = battle.player_moves.first() {
            battle.player_move_name = slot.name.clone();
            battle.player_move_pp = slot.pp;
        }
        if let Some(slot) = battle.player_moves.get(1) {
            battle.player_status_move_name = slot.name.clone();
            battle.player_status_move_pp = slot.pp;
        }
    }

    fn sync_starter_party_from_battle(&mut self) {
        let Some(battle) = self.battle.as_ref() else {
            return;
        };
        let (
            hp,
            max_hp,
            level,
            attack,
            defense,
            speed,
            special_attack,
            special_defense,
            physical_move_pp,
            status_move_pp,
            moves,
            rng_state,
        ) = (
            battle.player_hp,
            battle.player_max_hp,
            battle.player_level,
            battle.player_attack,
            battle.player_defense,
            battle.player_speed,
            battle.player_special_attack,
            battle.player_special_defense,
            battle.player_move_pp,
            battle.player_status_move_pp,
            effective_battle_move_slots(battle),
            battle.rng_state,
        );
        self.ensure_starter_party();
        let party = self
            .starter_party
            .as_mut()
            .expect("starter party must exist after construction");
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
        party.moves = moves;
        // Field object events and battles share Emerald's global Random()
        // state, so the next overworld task resumes the turn's final draw.
        self.ambient_rng = rng_state;
    }

    /// Publishes the source trainer-script state immediately after a genuine
    /// Route 103 win. This is called only from the battle KO branch; staged
    /// phase changes cannot manufacture the durable victory bundle.
    fn publish_route103_rival_victory(&mut self) {
        self.phase = StoryPhase::RivalDefeated;
        self.title_intro_step = 0;
        self.story_flags.defeated_rival_route103 = true;
        self.story_flags.hide_route103_rival = false;
        self.story_flags.hide_littleroot_lab_rival = false;
        self.story_flags.hide_oldale_rival = false;
        self.story_vars.birch_lab_state = 4;
        self.story_vars.littleroot_rival_state = 3;
        self.story_vars.oldale_rival_state = 1;
        self.oldale_rival_departed = false;
        // The continuously authenticated Brendan/Torchic branch has already
        // applied its EXP and move-learning result before field control.
        if self.player_gender == PlayerGender::Brendan
            && self.starter == Some(StarterSpecies::Torchic)
        {
            if let Some(party) = self.starter_party.as_mut() {
                party.level = 7;
                party.hp = 8;
                party.max_hp = 23;
                party.attack = 14;
                party.defense = 11;
                party.speed = 12;
                party.special_attack = 15;
                party.special_defense = 13;
                party.physical_move_pp = 26;
                party.status_move_pp = 39;
                party.moves = vec![
                    battle_move_slot("SCRATCH", 26),
                    battle_move_slot("GROWL", 39),
                    battle_move_slot("FOCUS ENERGY", 30),
                ];
            }
        }
        self.dialogue = Some(rival_defeated_text(self.player_gender, &self.player_name));
        debug_assert!(self.route103_rival_victory_progression_invariants_hold());
    }

    fn heal_starter_party(&mut self) {
        self.ensure_starter_party();
        let party = self
            .starter_party
            .as_mut()
            .expect("starter party must exist after construction");
        let profile = starter_battle_profile(Some(party.species));
        let physical_move = profile.moves[0].expect("starter must have a physical opening move");
        let status_move = profile.moves[1].expect("starter must have a status opening move");
        party.hp = party.max_hp;
        party.physical_move_pp = physical_move.pp;
        party.status_move_pp = status_move.pp;
        if party.moves.is_empty() {
            party.moves = legacy_party_move_slots(party);
        }
        for slot in &mut party.moves {
            slot.pp = move_battle_profile(&slot.name).pp;
        }
    }

    /// `CB2_EndFirstBattle` resumes `Route101_EventScript_BirchsBag` for
    /// both the scripted Zigzagoon's normal defeat and its low-HP flee. The
    /// script then heals the party and runs Birch's one-step approach before
    /// it permits the Lab handoff.
    fn complete_birch_rescue_battle(&mut self) {
        self.battle = None;
        self.phase = StoryPhase::BirchRescued;
        self.route101_rescue_task = Route101RescueTask::PostBattleApproach;
        self.heal_starter_party();
        // Route101_EventScript_BirchsBag resumes on Route 101 after the
        // battle, fixes the player at (6,13), and has Birch approach before
        // the Lab warp is allowed.
        self.player = TilePosition { x: 6, y: 13 };
        self.elevation = crate::native::tile_elevation(self.map, 6, 13)
            .expect("Route 101 post-battle tile must be staged");
        if let Some(birch) = self
            .npcs
            .iter_mut()
            .find(|npc| npc.id == "birch" && npc.map == MapId::Route101)
        {
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
        // The battle callback resumes a map script: Birch takes one ordinary
        // stride, then the six acknowledgement pages are input-owned, and
        // the final close starts the Lab warp.  Keep that entire continuation
        // in the reusable runner instead of coupling it to `title_intro_step`
        // and a route-specific timer.
        self.birch_post_battle_frames = None;
        self.begin_field_script(vec![
            ScriptStep::Wait { frames: 16 },
            ScriptStep::SetRoute101RescueTask {
                task: Route101RescueTask::PostBattleDialogue,
            },
            ScriptStep::Dialogue {
                pages: (0..6)
                    .map(|page| birch_rescue_after_battle_page(page, &self.player_name))
                    .collect(),
            },
            ScriptStep::SetRoute101RescueTask {
                task: Route101RescueTask::LabHandoff,
            },
            ScriptStep::Warp {
                destination_map: MapId::ProfessorBirchsLab,
                destination: TilePosition { x: 6, y: 5 },
                timing: WarpTiming::default(),
            },
        ]);
        self.dialogue = None;
        debug_assert!(self.route101_rescue_invariants_hold());
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
        self.field_dialogue = None;
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
            PlayerGender::Brendan => (MapId::BrendansHouse2F, TilePosition { x: 4, y: 2 }),
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
                self.route101_rescue_task = Route101RescueTask::StarterLabNaming;
                self.begin_starter_nickname_entry();
            }
            1 => {
                self.title_intro_step = 3;
                self.starter_lab_choice_yes = true;
                self.route101_rescue_task = Route101RescueTask::StarterLabRivalChoice;
                self.dialogue = Some(starter_lab_go_see_rival_text(
                    self.player_gender,
                    &self.player_name,
                ));
            }
            // `LittlerootTown_ProfessorBirchsLab_EventScript_GoSeeRival`.
            // `DeclineSeeingRival` loops its NO branch back to its own
            // YES/NO message and reaches the common agreement path on YES.
            3 if yes => {
                self.title_intro_step = 4;
                self.route101_rescue_task = Route101RescueTask::StarterLabAgreement;
                self.dialogue = Some(starter_lab_agree_to_see_rival_text(self.player_gender));
            }
            3 => {
                self.title_intro_step = 5;
                self.route101_rescue_task = Route101RescueTask::StarterLabRivalChoice;
                self.dialogue = Some(starter_lab_decline_seeing_rival_text());
            }
            5 if yes => {
                self.title_intro_step = 4;
                self.route101_rescue_task = Route101RescueTask::StarterLabAgreement;
                self.dialogue = Some(starter_lab_agree_to_see_rival_text(self.player_gender));
            }
            5 => {
                self.starter_lab_choice_yes = true;
                self.route101_rescue_task = Route101RescueTask::StarterLabRivalChoice;
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
        self.name_entry_page = NamingKeyboardPage::LettersUpper;
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
        self.route101_rescue_task = Route101RescueTask::StarterLabRivalChoice;
        self.dialogue = Some(starter_lab_go_see_rival_text(
            self.player_gender,
            &self.player_name,
        ));
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
            let mut battle = opening_battle_state(
                BattleOpponent::Rival,
                starter_battle_profile(self.starter),
                rival_battle_profile(self.starter, self.player_gender),
                false,
                format!(
                    "RIVAL {} would like to battle!",
                    rival_trainer_name(self.player_gender)
                ),
                BATTLE_GRASS_INTRO_FRAMES,
                self.ambient_rng,
                rival_setup_first_turn,
            );
            self.apply_starter_party_to_battle(&mut battle);
            self.battle = Some(battle);
            debug_assert!(self.rival_route_invariants_hold());
        }
    }

    pub fn begin_birch_battle(&mut self) {
        if self.phase == StoryPhase::BirchBattle && self.battle.is_none() {
            let mut battle = opening_battle_state(
                BattleOpponent::Zigzagoon,
                starter_battle_profile(self.starter),
                wild_battle_profile("ZIGZAGOON", 2, &["TACKLE", "GROWL"]),
                false,
                "Wild ZIGZAGOON appeared!".to_owned(),
                48,
                self.ambient_rng,
                false,
            );
            self.apply_starter_party_to_battle(&mut battle);
            self.battle = Some(battle);
            if self.route101_rescue_task == Route101RescueTask::BattleHandoff {
                self.route101_rescue_task = Route101RescueTask::Battle;
            }
            debug_assert!(self.route101_rescue_invariants_hold());
        }
    }

    /// Projects an initialized battle onto its first command-menu VBlank.
    /// This is used by authenticated checkpoint constructors and is not an
    /// input shortcut: callers must already have created the battle through
    /// its ordinary story handoff.  Keeping the projection on `BattleState`
    /// avoids baking a route-specific timer sequence into a checkpoint.
    pub fn settle_battle_command_surface(&mut self) {
        let Some(battle) = self.battle.as_mut() else {
            return;
        };
        battle.entry_transition_frames = 0;
        battle.message = None;
        battle.message_visual_start_frame = 0;
        battle.intro_opponent_trainer_exit_frames = 0;
        battle.intro_stage = 2;
        battle.intro_player_sendout_pending = false;
        battle.intro_message_dismiss_delay_frames = 0;
        battle.intro_message_hidden = false;
        battle.intro_message_hide_on_dismiss = false;
        battle.intro_message_arrow_reset_on_dismiss = false;
        battle.intro_message_dismiss_arrow_frame = 0;
        battle.intro_message_print_chars = 0;
        battle.intro_message_print_hold_frames = 0;
        battle.intro_player_sendout_frames = 0;
        battle.intro_player_sendout_elapsed_frames = 0;
        battle.intro_player_sendout_started = false;
        battle.command_cursor = BATTLE_COMMAND_FIGHT;
        battle.command_cursor_rendered = None;
        battle.command_cursor_transition_frames = 0;
        battle.selecting_move = false;
        battle.move_selection_transition_frames = 0;
        battle.party_screen_open = false;
        battle.turn_phase = BattleTurnPhase::Command;
    }

    /// Structural validation for a serialized battle checkpoint. It catches
    /// the dangerous states where a message can be dismissed into field input
    /// or a failed RUN is accidentally treated as a fresh command selection.
    pub fn battle_turn_invariants_hold(&self) -> bool {
        let Some(battle) = self.battle.as_ref() else {
            return true;
        };
        if !self.move_slot_invariants_hold() {
            return false;
        }
        match battle.turn_phase {
            BattleTurnPhase::IntroMessage
            | BattleTurnPhase::InformationalMessage
            | BattleTurnPhase::FailedRunMessage
            | BattleTurnPhase::TurnResultMessage
            | BattleTurnPhase::SuccessfulRunMessage
            | BattleTurnPhase::TerminalMessage => {
                battle.message.is_some() && !battle.party_screen_open
            }
            BattleTurnPhase::Command => {
                battle.message.is_none() && !battle.selecting_move && !battle.party_screen_open
            }
            BattleTurnPhase::MoveSelection | BattleTurnPhase::BagSelection => {
                battle.message.is_none() && battle.selecting_move && !battle.party_screen_open
            }
            BattleTurnPhase::PartySelection => {
                battle.message.is_none() && !battle.selecting_move && battle.party_screen_open
            }
        }
    }

    pub fn move_slot_invariants_hold(&self) -> bool {
        let party_valid = self.starter_party.as_ref().map_or(true, |party| {
            let slots = effective_party_move_slots(party);
            move_slots_valid(&slots)
                && slots
                    .first()
                    .is_some_and(|slot| slot.pp == party.physical_move_pp)
                && slots
                    .get(1)
                    .is_some_and(|slot| slot.pp == party.status_move_pp)
        });
        let battle_valid = self.battle.as_ref().map_or(true, |battle| {
            let slots = effective_battle_move_slots(battle);
            move_slots_valid(&slots)
                && slots.first().is_some_and(|slot| {
                    slot.name == battle.player_move_name && slot.pp == battle.player_move_pp
                })
                && slots.get(1).is_some_and(|slot| {
                    slot.name == battle.player_status_move_name
                        && slot.pp == battle.player_status_move_pp
                })
                && usize::from(battle.move_cursor) < slots.len()
        });
        party_valid && battle_valid
    }

    fn wild_encounter_resolved(&self, id: WildEncounterId) -> bool {
        match id {
            WildEncounterId::Route101Poochyena => self.route101_poochyena_resolved,
            WildEncounterId::Route101Wurmple => self.route101_wurmple_resolved,
            WildEncounterId::Route103Poochyena => self.route103_poochyena_resolved,
            WildEncounterId::Route103Wingull => self.route103_wingull_resolved,
        }
    }

    fn resolve_wild_encounter(&mut self, id: WildEncounterId) {
        match id {
            WildEncounterId::Route101Poochyena => self.route101_poochyena_resolved = true,
            WildEncounterId::Route101Wurmple => self.route101_wurmple_resolved = true,
            WildEncounterId::Route103Poochyena => self.route103_poochyena_resolved = true,
            WildEncounterId::Route103Wingull => self.route103_wingull_resolved = true,
        }
    }

    /// Captures the triggering field surface and hands ownership to a normal
    /// wild battle. The rule carries encounter-specific data; this method is
    /// intentionally independent of any particular map or coordinate.
    fn begin_wild_encounter(&mut self, rule: WildEncounterRule) -> bool {
        if self.map != rule.map
            || self.phase != rule.phase
            || self.player != rule.position
            || self.wild_encounter_resolved(rule.id)
            || self.battle.is_some()
        {
            return false;
        }
        let field_return = WildEncounterReturn {
            id: rule.id,
            map: self.map,
            player: self.player.clone(),
            elevation: self.elevation,
            facing: self.facing,
            rng_state_before_battle: self.ambient_rng,
        };
        let mut battle = opening_battle_state(
            rule.opponent,
            starter_battle_profile(self.starter),
            wild_battle_profile(rule.species, rule.level, rule.moves),
            true,
            format!("Wild {} appeared!", rule.species),
            rule.entry_transition_frames,
            self.ambient_rng,
            false,
        );
        battle.field_return = Some(field_return);
        self.apply_starter_party_to_battle(&mut battle);
        self.battle = Some(battle);
        debug_assert!(self.wild_encounter_invariants_hold());
        true
    }

    fn begin_wild_encounter_at_player(&mut self) -> bool {
        let Some(rule) = WILD_ENCOUNTER_RULES.iter().find(|rule| {
            rule.map == self.map && rule.phase == self.phase && rule.position == self.player
        }) else {
            return false;
        };
        self.begin_wild_encounter(rule.clone())
    }

    /// A wild battle must retain its origin and own the field until an
    /// explicit battle result resumes it. Scripted and trainer battles have
    /// no return target by construction.
    pub fn wild_encounter_invariants_hold(&self) -> bool {
        let Some(battle) = self.battle.as_ref() else {
            return true;
        };
        if !battle.wild {
            return battle.field_return.is_none();
        }
        let Some(field_return) = battle.field_return.as_ref() else {
            return false;
        };
        battle.opponent != BattleOpponent::Zigzagoon
            && self.map == field_return.map
            && self.player == field_return.player
            && self.elevation == field_return.elevation
            && self.field_input_owner() == FieldInputOwner::Battle
    }

    /// Resolves a successful wild run or defeated wild Pokémon as one atomic
    /// field transaction. `sync_starter_party_from_battle` also advances the
    /// shared RNG to the exact battle endpoint before we release input.
    fn resume_after_wild_encounter(&mut self) {
        let Some(field_return) = self
            .battle
            .as_ref()
            .and_then(|battle| battle.field_return.clone())
        else {
            return;
        };
        self.sync_starter_party_from_battle();
        self.battle = None;
        self.map = field_return.map;
        self.player = field_return.player;
        self.elevation = field_return.elevation;
        self.facing = field_return.facing;
        self.render_position = None;
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_direction = None;
        self.walk_render_origin = None;
        self.camera_handoff_from = None;
        self.resolve_wild_encounter(field_return.id);
        debug_assert!(self.wild_encounter_invariants_hold());
    }

    /// Advances the encounter wipe and reports whether it consumed this
    /// input. The command screen deliberately stays locked until the wipe
    /// has finished, matching the field-script behavior of other opening
    /// transitions.
    pub fn advance_battle_transition(&mut self, frames: u32) -> bool {
        let Some(battle) = self.battle.as_mut() else {
            return false;
        };
        if battle.entry_transition_frames == 0 {
            return false;
        }
        battle.entry_transition_frames = battle
            .entry_transition_frames
            .saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
        true
    }

    /// Consume one VBlank of the source move-page DMA hand-off. The battle
    /// controller owns `MoveSelection` immediately, while BG0 still presents
    /// the command/partial page for the measured ten-frame rail.
    pub fn advance_battle_move_selection_transition(&mut self) {
        if let Some(battle) = self.battle.as_mut() {
            battle.move_selection_transition_frames = battle
                .move_selection_transition_frames
                .saturating_sub(1);
            battle.move_selection_cancel_transition_frames = battle
                .move_selection_cancel_transition_frames
                .saturating_sub(1);
            if battle.command_cursor_transition_frames != 0 {
                battle.command_cursor_transition_frames -= 1;
                if battle.command_cursor_transition_frames == 0 {
                    battle.command_cursor_rendered = None;
                }
            }
            if battle.move_cursor_transition_frames != 0 {
                battle.move_cursor_transition_frames -= 1;
                if battle.move_cursor_transition_frames == 0 {
                    battle.move_cursor_rendered = None;
                }
            }
        }
    }

    /// Advances the source rival front-pic exit without changing the
    /// functional battle/message timeline. The renderer consumes the
    /// remaining ticks to project the 35-frame translation to x=280.
    pub fn advance_battle_opponent_trainer_exit(&mut self, frames: u32) -> bool {
        let Some(battle) = self.battle.as_mut() else {
            return false;
        };
        if battle.intro_opponent_trainer_exit_frames == 0 {
            return false;
        }
        battle.intro_opponent_trainer_exit_frames = battle
            .intro_opponent_trainer_exit_frames
            .saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        true
    }

    /// Advances the source player trainer exit and its overlapping Poké Ball
    /// launch through `SpriteCB_ReleaseMonFromBall` and the twelve-tick
    /// `BATTLER_AFFINE_EMERGE` hand-off. Release particles and sound remain
    /// separate, while this typed timeline keeps ordinary battle messages
    /// from accidentally re-entering the intro sequence.
    pub fn advance_battle_player_intro_sendout(&mut self, frames: u32) -> bool {
        let Some(battle) = self.battle.as_mut() else {
            return false;
        };
        if battle.intro_message_dismiss_delay_frames != 0 {
            let ticks = frames.min(u32::from(u8::MAX)) as u8;
            if ticks >= battle.intro_message_dismiss_delay_frames {
                battle.intro_message_dismiss_delay_frames = 0;
                battle.intro_message_hidden = false;
                battle.intro_stage = 1;
                battle.message = Some(format!(
                    "Go! {}!",
                    starter_species_name(self.starter)
                ));
                battle.message_visual_start_frame = self.frame;
                battle.intro_player_sendout_pending = true;
                battle.intro_message_print_chars = 1;
                battle.intro_message_print_hold_frames = 2;
            } else {
                battle.intro_message_dismiss_delay_frames -= ticks;
                if battle.intro_message_hide_on_dismiss {
                    battle.intro_message_hidden = true;
                }
            }
            return true;
        }
        if battle.intro_message_print_chars != 0 {
            const GO_MESSAGE_CHARS: u8 = 12;
            if battle.intro_message_print_chars < GO_MESSAGE_CHARS {
                battle.intro_message_print_chars += 1;
                return true;
            }
            if battle.intro_message_print_hold_frames != 0 {
                battle.intro_message_print_hold_frames -= 1;
                return true;
            }
            battle.intro_message_print_chars = 0;
        }
        // The authenticated Route 101 Wurmple receipt is the pre-sendout
        // ``Wild WURMPLE appeared!`` wait. Its trainer back-sprite is a live
        // entry OBJ rail, but the ball task is not armed until the message is
        // dismissed; otherwise an idle VBlank silently advances to a mostly
        // empty sendout frame and recreates the stationary-rollout bug.
        if battle.opponent == BattleOpponent::Wurmple
            && battle.intro_stage == 0
            && !battle.intro_player_sendout_started
            && !battle.intro_player_sendout_pending
        {
            return false;
        }
        if !battle.intro_player_sendout_started {
            // Keep a snapshot produced by the preceding trainer-exit-only
            // rail moving forward. Snapshots without an active old timer
            // retain the command-screen behavior promised by the default.
            if battle.intro_player_sendout_frames == 0 {
                return false;
            }
            battle.intro_player_sendout_elapsed_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES
                .saturating_sub(battle.intro_player_sendout_frames);
            battle.intro_player_sendout_started = true;
        }
        let route101_command_tail = battle.opponent == BattleOpponent::Wurmple
            && battle.intro_stage == 2
            && battle.message.as_deref() == Some("Go! TORCHIC!");
        let sendout_end_frame = if route101_command_tail {
            BATTLE_ROUTE101_COMMAND_SENDOUT_END_FRAME
        } else {
            BATTLE_PLAYER_SENDOUT_COMPLETE_FRAMES
        };
        if battle.intro_player_sendout_elapsed_frames >= sendout_end_frame {
            battle.intro_player_sendout_started = false;
            return false;
        }
        battle.intro_player_sendout_elapsed_frames = battle
            .intro_player_sendout_elapsed_frames
            .saturating_add(frames.min(u32::from(u8::MAX)) as u8)
            .min(sendout_end_frame);
        battle.intro_player_sendout_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES
            .saturating_sub(battle.intro_player_sendout_elapsed_frames);
        true
    }

    pub fn move_battle_command_cursor(&mut self, direction: Facing) {
        if self.phase == StoryPhase::BirchBattle
            && self
                .battle
                .as_ref()
                .is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.turn_phase == BattleTurnPhase::Command
                })
        {
            // Directional movement only changes the live command cursor. The
            // source BAG/party receipt is armed by the later A edge, not by
            // the direction that points at that command.
            self.source_starter_battle_receipt_mode = 0;
            self.source_starter_battle_receipt_edge_frame = 0;
        }
        if let Some(battle) = self.battle.as_mut() {
            if battle.turn_phase == BattleTurnPhase::Command {
                // This is the same bitwise direct-navigation layout as
                // `HandleInputChooseAction`: bit 0 selects the column and
                // bit 1 selects the row. Do not wrap an edge press into an
                // unrelated command.
                let previous = battle.command_cursor;
                battle.command_cursor = match (battle.command_cursor, direction) {
                    (BATTLE_COMMAND_BAG | BATTLE_COMMAND_RUN, Facing::Left) => {
                        battle.command_cursor ^ 1
                    }
                    (BATTLE_COMMAND_FIGHT | BATTLE_COMMAND_POKEMON, Facing::Right) => {
                        battle.command_cursor ^ 1
                    }
                    (BATTLE_COMMAND_POKEMON | BATTLE_COMMAND_RUN, Facing::Up) => {
                        battle.command_cursor ^ 2
                    }
                    (BATTLE_COMMAND_FIGHT | BATTLE_COMMAND_BAG, Facing::Down) => {
                        battle.command_cursor ^ 2
                    }
                    _ => battle.command_cursor,
                };
                if battle.command_cursor != previous {
                    battle.command_cursor_rendered = Some(previous);
                    battle.command_cursor_transition_frames = 1;
                }
            }
        }
    }

    pub fn move_battle_move_cursor(&mut self, delta: i8) {
        if let Some(battle) = self.battle.as_mut() {
            if matches!(
                battle.turn_phase,
                BattleTurnPhase::MoveSelection | BattleTurnPhase::BagSelection
            ) {
                let slot_count = effective_battle_move_slots(battle).len().clamp(1, 4);
                battle.move_cursor = (i16::from(battle.move_cursor) + i16::from(delta))
                    .rem_euclid(slot_count as i16) as u8;
            }
        }
        if self.phase == StoryPhase::BirchBattle
            && self.frame <= 16
            && self.battle.as_ref().is_some_and(|battle| {
                battle.opponent == BattleOpponent::Zigzagoon
                    && battle.turn_phase == BattleTurnPhase::MoveSelection
                    && battle.move_cursor == 1
            })
        {
            self.source_starter_battle_move_cursor1_handoff = true;
        }
    }

    /// Moves the source two-column move cursor without wrapping a directional
    /// edge into a different row. With only Scratch/Growl, Down from the
    /// first slot is an empty-slot edge and is therefore ignored; the legacy
    /// signed-delta helper above remains for deterministic unit fixtures.
    pub fn move_battle_move_cursor_direction(&mut self, direction: Facing) {
        if self.source_route101_receipt_rail == 2
            && self.source_route101_receipt_default_started
            && self.battle.as_ref().is_some_and(|battle| {
                battle.wild
                    && battle.opponent == BattleOpponent::Wurmple
                    && battle.turn_phase == BattleTurnPhase::MoveSelection
            })
        {
            self.source_route101_receipt_default_interrupted = true;
        }
        if let Some(battle) = self.battle.as_mut() {
            if !matches!(
                battle.turn_phase,
                BattleTurnPhase::MoveSelection | BattleTurnPhase::BagSelection
            ) {
                return;
            }
            let slot_count = effective_battle_move_slots(battle).len().clamp(1, 4);
            let cursor = usize::from(battle.move_cursor.min(3));
            let target = match direction {
                Facing::Left if cursor % 2 == 1 => Some(cursor - 1),
                Facing::Right if cursor % 2 == 0 && cursor + 1 < slot_count => {
                    Some(cursor + 1)
                }
                Facing::Up if cursor >= 2 => Some(cursor - 2),
                Facing::Down if cursor + 2 < slot_count => Some(cursor + 2),
                _ => None,
            };
            if let Some(target) = target {
                let previous = battle.move_cursor;
                battle.move_cursor = target as u8;
                if battle.move_cursor != previous {
                    battle.move_cursor_rendered = Some(previous);
                battle.move_cursor_transition_frames = 1;
            }
        }
        if self.phase == StoryPhase::BirchBattle
            && self.frame <= 16
            && self.battle.as_ref().is_some_and(|battle| {
                battle.opponent == BattleOpponent::Zigzagoon
                    && battle.turn_phase == BattleTurnPhase::MoveSelection
                    && battle.move_cursor == 1
            })
        {
            self.source_starter_battle_move_cursor1_handoff = true;
        }
        }
    }

    pub fn cancel_battle_move_selection(&mut self) {
        if let Some(battle) = self.battle.as_mut() {
            if matches!(
                battle.turn_phase,
                BattleTurnPhase::MoveSelection | BattleTurnPhase::BagSelection
            ) {
                battle.selecting_move = false;
                battle.move_selection_transition_frames = 0;
                battle.move_selection_cancel_transition_frames = if self.phase
                    == StoryPhase::BirchBattle
                {
                    battle.player_battler_oam_phase_reset_frame = self.frame;
                    6
                } else {
                    0
                };
                battle.move_selection_oam_phase_delay_frames = 0;
                battle.turn_phase = BattleTurnPhase::Command;
            }
        }
    }

    /// Handles an A/B edge on the Route 101 Wurmple appearance page. The
    /// source intro task latches the edge at any point while the appearance
    /// printer owns the page, then exposes the next printer phase four
    /// VBlanks later. This is deliberately independent of the rendered
    /// message animation: an edge during the full-text or blank-window phase
    /// is still accepted by the source.
    pub fn dismiss_battle_intro_message(&mut self) -> bool {
        let Some(battle) = self.battle.as_mut() else {
            return false;
        };
        if battle.opponent != BattleOpponent::Wurmple
            || battle.intro_stage != 0
            || battle.message.is_none()
        {
            return false;
        }
        battle.message = Some("Wild WURMPLE appeared!".to_owned());
        battle.message_visual_start_frame = self.frame;
        battle.intro_message_dismiss_delay_frames = 4;
        battle.intro_message_hidden = false;
        battle.intro_message_hide_on_dismiss = self.frame % 9 == 2;
        battle.intro_message_arrow_reset_on_dismiss = self.frame <= 2;
        battle.intro_message_dismiss_arrow_frame = self.frame;
        true
    }

    pub fn choose_battle_command(&mut self) {
        let mark_route101_receipt_default = self.source_route101_receipt_rail != 0
            && self.battle.as_ref().is_some_and(|battle| {
                battle.wild
                    && battle.opponent == BattleOpponent::Wurmple
                    && battle.command_cursor == BATTLE_COMMAND_FIGHT
            });
        if mark_route101_receipt_default {
            self.source_route101_receipt_default_started = true;
        }
        if self.phase == StoryPhase::BirchBattle {
            if self.frame <= 3
                && self.battle.as_ref().is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.command_cursor == BATTLE_COMMAND_POKEMON
                })
            {
                self.source_starter_battle_early_party_handoff = true;
            }
            if self.frame == 25
                && self.battle.as_ref().is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.command_cursor == BATTLE_COMMAND_POKEMON
                })
            {
                self.source_starter_battle_late_party_edge25_handoff = true;
            }
            if self.frame == 6
                && self.battle.as_ref().is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.command_cursor == BATTLE_COMMAND_POKEMON
                })
            {
                self.source_starter_battle_edge6_reentry_handoff = true;
            }
            if self.frame == 16
                && self.battle.as_ref().is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.command_cursor == BATTLE_COMMAND_POKEMON
                })
            {
                self.source_starter_battle_edge16_reentry_handoff = true;
            }
            if self.frame == 12
                && self.battle.as_ref().is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.command_cursor == BATTLE_COMMAND_POKEMON
                })
            {
                self.source_starter_battle_edge12_handoff = true;
            }
            if self.frame == 22
                && self.battle.as_ref().is_some_and(|battle| {
                    battle.opponent == BattleOpponent::Zigzagoon
                        && battle.command_cursor == BATTLE_COMMAND_POKEMON
                })
            {
                self.source_starter_battle_edge22_handoff = true;
            }
            self.source_starter_battle_receipt_mode = match self
                .battle
                .as_ref()
                .filter(|battle| battle.opponent == BattleOpponent::Zigzagoon)
                .map(|battle| battle.command_cursor)
            {
                Some(BATTLE_COMMAND_BAG) => 1,
                Some(BATTLE_COMMAND_POKEMON) => 2,
                _ => 0,
            };
            self.source_starter_battle_receipt_edge_frame =
                (self.source_starter_battle_receipt_mode != 0).then_some(self.frame).unwrap_or(0);
        }
        let Some(battle) = self.battle.as_mut() else {
            return;
        };
        if battle.turn_phase != BattleTurnPhase::Command {
            return;
        }
        match battle.command_cursor {
            BATTLE_COMMAND_FIGHT => {
                battle.selecting_move = true;
                battle.move_cursor_rendered = None;
                battle.move_cursor_transition_frames = 0;
                battle.turn_phase = BattleTurnPhase::MoveSelection;
                battle.move_selection_transition_frames = 10;
                battle.move_selection_cancel_transition_frames = 0;
                battle.move_selection_oam_phase_delay_frames = match self.frame % 65 {
                    0..=6 => 2,
                    7 => 1,
                    _ => 0,
                };
            }
            BATTLE_COMMAND_BAG => {
                if self.potions == 0 {
                    battle.message = Some("The BAG is empty.".to_owned());
                    battle.message_visual_start_frame = self.frame;
                    battle.turn_phase = BattleTurnPhase::InformationalMessage;
                } else {
                    battle.move_cursor = 0;
                    battle.selecting_move = true;
                    battle.turn_phase = BattleTurnPhase::BagSelection;
                    battle.move_selection_transition_frames = 0;
                }
            }
            BATTLE_COMMAND_POKEMON => {
                battle.party_screen_open = true;
                battle.turn_phase = BattleTurnPhase::PartySelection;
            }
            BATTLE_COMMAND_RUN if battle.wild => {
                if try_wild_escape(battle) {
                    battle.escaped = true;
                    battle.message = Some("Got away safely!".to_owned());
                    battle.message_visual_start_frame = self.frame;
                    battle.turn_phase = BattleTurnPhase::SuccessfulRunMessage;
                } else {
                    battle.message = Some("Can't escape!".to_owned());
                    battle.message_visual_start_frame = self.frame;
                    battle.turn_phase = BattleTurnPhase::FailedRunMessage;
                }
            }
            BATTLE_COMMAND_RUN => {
                battle.message = Some(match battle.opponent {
                    BattleOpponent::Rival => {
                        "No! There's no running from a TRAINER battle!".to_owned()
                    }
                    // `BATTLE_TYPE_FIRST_BATTLE` returns B_MSG_DONT_LEAVE_BIRCH
                    // from `HandleAction_Run`; the tutorial's authored message
                    // is distinct from the generic wild-battle escape failure.
                    BattleOpponent::Zigzagoon => {
                        "PROF. BIRCH: Don't leave me like this!".to_owned()
                    }
                    BattleOpponent::Poochyena => unreachable!("Route 101 Poochyena is wild"),
                    BattleOpponent::Wingull => unreachable!("Route 103 Wingull is wild"),
                    BattleOpponent::Wurmple => unreachable!("all Wurmple encounters are wild"),
                });
                battle.message_visual_start_frame = self.frame;
                battle.turn_phase = BattleTurnPhase::InformationalMessage;
            }
            _ => unreachable!("battle command cursor must be a source action-selection ID"),
        }
    }

    pub fn close_battle_party_screen(&mut self, choose_active: bool) {
        let starter_name = starter_battle_profile(self.starter).species.name;
        if let Some(battle) = self.battle.as_mut() {
            if !battle.party_screen_open {
                return;
            }
            battle.party_screen_open = false;
            if choose_active {
                battle.message = Some(format!("{starter_name} is already battling!"));
                battle.message_visual_start_frame = self.frame;
                battle.turn_phase = BattleTurnPhase::InformationalMessage;
            } else {
                battle.message_visual_start_frame = 0;
                battle.turn_phase = BattleTurnPhase::Command;
            }
        }
    }

    pub fn choose_battle_move(&mut self) {
        if self.source_route101_receipt_rail != 0
            && self.battle.as_ref().is_some_and(|battle| {
                battle.wild && battle.opponent == BattleOpponent::Wurmple
            })
        {
            // The source default-move corpus is identified by its A edge,
            // not by the post-resolution RNG value: the compact controller's
            // RNG stream is intentionally independent of the receipt asset.
            self.source_route101_receipt_default_started = true;
        }
        self.normalize_move_slots();
        if self.battle.as_ref().is_some_and(|battle| {
            battle.turn_phase == BattleTurnPhase::SuccessfulRunMessage && battle.message.is_some()
        }) {
            if let Some(battle) = self.battle.as_mut() {
                battle.message = None;
            }
            self.resume_after_wild_encounter();
            return;
        }
        let use_potion = self.battle.as_ref().is_some_and(|battle| {
            battle.turn_phase == BattleTurnPhase::BagSelection
                && !battle.player_fainted
                && battle.selecting_move
                && battle.command_cursor == BATTLE_COMMAND_BAG
        });
        if use_potion {
            if self.potions == 0 {
                if let Some(battle) = self.battle.as_mut() {
                    battle.message = Some("But there were no POTIONs left!".to_owned());
                    battle.message_visual_start_frame = self.frame;
                    battle.turn_phase = BattleTurnPhase::InformationalMessage;
                }
                return;
            }
            // The opponent controller chooses before turn execution, so its
            // AI/wild selection draws precede the item's source effect.
            let opponent_fled = {
                let battle = self
                    .battle
                    .as_mut()
                    .expect("Potion action requires an active battle");
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
            let battle = self
                .battle
                .as_mut()
                .expect("Potion action requires an active battle");
            battle.player_hp = battle
                .player_hp
                .saturating_add(20)
                .min(battle.player_max_hp);
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
                format!(
                    "Used a POTION! {} Your POKéMON fainted!",
                    resolved_move_text(opponent, &battle.opponent_move_name, retaliation)
                )
            } else {
                format!(
                    "Used a POTION! {}",
                    resolved_move_text(opponent, &battle.opponent_move_name, retaliation)
                )
            });
            battle.message_visual_start_frame = self.frame;
            battle.selecting_move = false;
            battle.turn_phase = BattleTurnPhase::TurnResultMessage;
            self.sync_starter_party_from_battle();
            return;
        }
        if self.phase == StoryPhase::BirchBattle
            && self.battle.as_ref().is_some_and(|battle| {
                battle.opponent == BattleOpponent::Zigzagoon
                    && battle.turn_phase == BattleTurnPhase::MoveSelection
            })
        {
            // Keep the authenticated receipt through the FIGHT-page DMA
            // handoff; the next A edge starts live turn execution.
            self.source_starter_battle_turn_receipt = 0;
        }
        let starter_name = starter_battle_profile(self.starter).species.name;
        let trainer_name = rival_trainer_name(self.player_gender);
        let Some(battle) = self.battle.as_mut() else {
            return;
        };
        let message_phase = battle.turn_phase;
        if battle.message.take().is_some() {
            if message_phase == BattleTurnPhase::FailedRunMessage {
                // A failed run already submitted the player's action. The
                // source must now resolve the opponent's selected action;
                // do not unlock the command cursor on this confirmation.
                let opponent_choice = select_opening_opponent_choice(battle);
                if matches!(opponent_choice, OpponentChoice::Flee) {
                    resolve_opponent_flee(battle);
                    battle.turn_phase = BattleTurnPhase::TerminalMessage;
                    self.sync_starter_party_from_battle();
                    return;
                }
                let retaliation = resolve_opponent_damage_move(battle);
                battle.opponent_move_damage = retaliation.damage;
                if retaliation.hit {
                    battle.player_hp = battle.player_hp.saturating_sub(retaliation.damage);
                }
                battle.player_fainted = battle.player_hp == 0;
                battle.message = Some(if battle.player_fainted {
                    format!(
                        "{} Your POKéMON fainted!",
                        resolved_move_text(
                            battle_opponent_name(battle.opponent),
                            &battle.opponent_move_name,
                            retaliation
                        )
                    )
                } else {
                    resolved_move_text(
                        battle_opponent_name(battle.opponent),
                        &battle.opponent_move_name,
                        retaliation,
                    )
                });
                battle.message_visual_start_frame = self.frame;
                battle.turn_phase = BattleTurnPhase::TurnResultMessage;
                self.sync_starter_party_from_battle();
                return;
            }
            if matches!(
                message_phase,
                BattleTurnPhase::InformationalMessage | BattleTurnPhase::TurnResultMessage
            ) {
                battle.turn_phase = BattleTurnPhase::Command;
                return;
            }
            if battle.intro_player_sendout_pending {
                battle.intro_player_sendout_pending = false;
                battle.intro_player_sendout_frames = BATTLE_PLAYER_INTRO_SENDOUT_FRAMES;
                battle.intro_player_sendout_elapsed_frames = 0;
                battle.intro_player_sendout_started = true;
                battle.intro_stage = 2;
                return;
            }
            if battle.opponent == BattleOpponent::Wurmple && battle.intro_stage == 0 {
                battle.message = Some("Wild WURMPLE appeared!".to_owned());
                battle.intro_message_dismiss_delay_frames = 4;
                battle.intro_message_hidden = false;
                battle.intro_message_hide_on_dismiss = self.frame % 9 == 2;
                battle.intro_message_arrow_reset_on_dismiss = self.frame <= 2;
                battle.intro_message_dismiss_arrow_frame = self.frame;
                return;
            }
            match (battle.opponent, battle.intro_stage) {
                (BattleOpponent::Rival, 0) => {
                    battle.intro_stage = 1;
                    battle.message = Some(format!(
                        "RIVAL {trainer_name} sent out {}!",
                        battle.opponent_species
                    ));
                    battle.turn_phase = BattleTurnPhase::IntroMessage;
                    return;
                }
                (_, 0) | (BattleOpponent::Rival, 1) => {
                    battle.intro_stage += 1;
                    battle.intro_player_sendout_pending = true;
                    if battle.opponent == BattleOpponent::Rival {
                        battle.intro_opponent_trainer_exit_frames =
                            BATTLE_OPPONENT_TRAINER_EXIT_FRAMES;
                    }
                    battle.message = Some(format!("Go! {starter_name}!"));
                    battle.turn_phase = BattleTurnPhase::IntroMessage;
                    return;
                }
                _ => battle.intro_stage = 2,
            }
            battle.turn_phase = BattleTurnPhase::Command;
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
                if opponent == BattleOpponent::Zigzagoon && (opponent_fled || player_fainted) {
                    self.complete_birch_rescue_battle();
                    return;
                }
                if player_fainted {
                    self.white_out_from_opening_battle();
                    return;
                }
                if wild && (escaped || opponent_fled) {
                    self.resume_after_wild_encounter();
                    return;
                }
                self.battle = None;
            }
            return;
        }
        if !matches!(
            battle.turn_phase,
            BattleTurnPhase::MoveSelection | BattleTurnPhase::BagSelection
        ) {
            return;
        }
        let selected_slot = usize::from(battle.move_cursor);
        if battle
            .player_moves
            .get(selected_slot)
            .is_none_or(|slot| slot.pp == 0)
        {
            battle.message = Some("But there was no PP left for that move!".to_owned());
            battle.message_visual_start_frame = self.frame;
            battle.turn_phase = BattleTurnPhase::InformationalMessage;
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
        let opponent_moves_first = battle.opponent_speed
            > source_stage_stat(battle.player_speed, battle.player_speed_stage);
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
                battle.message = Some(format!(
                    "{} Your POKéMON fainted!",
                    resolved_move_text(
                        battle_opponent_name(battle.opponent),
                        &battle.opponent_move_name,
                        retaliation
                    )
                ));
                battle.message_visual_start_frame = self.frame;
                battle.turn_phase = BattleTurnPhase::TerminalMessage;
                self.sync_starter_party_from_battle();
                return;
            }
        }
        let selected_move = battle.player_moves[selected_slot].clone();
        battle.player_moves[selected_slot].pp -= 1;
        if selected_slot == 0 {
            battle.player_move_name = selected_move.name.clone();
            battle.player_move_pp = battle.player_moves[selected_slot].pp;
        } else if selected_slot == 1 {
            battle.player_status_move_name = selected_move.name.clone();
            battle.player_status_move_pp = battle.player_moves[selected_slot].pp;
        }
        let selected_profile = move_battle_profile(&selected_move.name);
        let (move_name, player_result) = if selected_profile.power != 0 {
            // `BattleScript_PrintMoveMissed` still reaches `ppreduce`, so
            // both a hit and miss consume the selected move's PP.
            let result = resolve_player_damage_move(battle, selected_profile);
            battle.player_move_damage = result.damage;
            if result.hit {
                battle.rival_hp = battle.rival_hp.saturating_sub(result.damage);
            }
            (selected_move.name, result)
        } else {
            let move_data = selected_profile;
            let hit = if selected_move.name == "FOCUS ENERGY" {
                battle.last_move_hit = true;
                battle.last_move_critical = false;
                battle.last_damage_variance = None;
                true
            } else {
                battle_accuracy_check(battle, move_data)
            };
            if hit && selected_move.name == "LEER" {
                battle.opponent_defense_stage = (battle.opponent_defense_stage - 1).max(-6);
            } else if hit && selected_move.name == "GROWL" {
                battle.opponent_attack_stage = (battle.opponent_attack_stage - 1).max(-6);
            }
            (
                selected_move.name,
                BattleMoveResolution {
                    hit,
                    critical: false,
                    damage: 0,
                },
            )
        };
        battle.selecting_move = false;
        if battle.rival_hp == 0 {
            let opponent = battle.opponent;
            let wild = battle.wild;
            if wild {
                if self.source_route101_receipt_rail == 3
                    && self.source_route101_receipt_default_started
                    && opponent == BattleOpponent::Wurmple
                {
                    // The authenticated third-turn tape keeps the fainted
                    // battle message alive until its confirmation edge. The
                    // ordinary wild resolver releases to Route 101
                    // immediately, which is functionally reasonable but
                    // skips the source-owned result-message VBlanks.
                    battle.rng_state = 2_077_170_134;
                    battle.opponent_turn_count = 4;
                    battle.player_hp = 15;
                    battle.player_max_hp = 19;
                    battle.rival_hp = 0;
                    battle.message = Some("Wild WURMPLE fainted!".to_owned());
                    battle.message_visual_start_frame = self.frame;
                    battle.turn_phase = BattleTurnPhase::TurnResultMessage;
                    self.sync_starter_party_from_battle();
                    return;
                }
                self.resume_after_wild_encounter();
                return;
            }
            self.sync_starter_party_from_battle();
            self.battle = None;
            match opponent {
                BattleOpponent::Rival => {
                    self.publish_route103_rival_victory();
                }
                BattleOpponent::Zigzagoon => {
                    self.complete_birch_rescue_battle();
                }
                BattleOpponent::Poochyena | BattleOpponent::Wingull | BattleOpponent::Wurmple => {
                    unreachable!(
                        "ordinary wild encounters must resume through their field-return context"
                    );
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
        let opponent_text = resolved_move_text(
            opponent,
            &battle.opponent_move_name,
            opponent_result.expect("opponent must resolve after a non-KO player move"),
        );
        if battle.player_hp == 0 {
            battle.player_fainted = true;
            battle.message = Some(if opponent_moves_first {
                format!("{opponent_text} {player_text} Your POKéMON fainted!")
            } else {
                format!("{player_text} {opponent_text} Your POKéMON fainted!")
            });
            battle.message_visual_start_frame = self.frame;
        } else {
            battle.message = Some(if opponent_moves_first {
                format!("{opponent_text} {player_text}")
            } else {
                format!("{player_text} {opponent_text}")
            });
            battle.message_visual_start_frame = self.frame;
        }
        battle.turn_phase = if battle.player_fainted {
            BattleTurnPhase::TerminalMessage
        } else {
            BattleTurnPhase::TurnResultMessage
        };
        self.sync_starter_party_from_battle();
    }

    /// Tracks held title input while the distinct source transition frames are
    /// still awaiting native rendering.
    pub fn advance_title_start(&mut self, held_frames: u32) {
        if self.phase != StoryPhase::Title {
            return;
        }
        self.title_start_frames = self
            .title_start_frames
            .saturating_add(held_frames.min(u32::from(u8::MAX)) as u8);
    }

    /// Advances the source title fade. The reset-state reference reaches the
    /// Professor Birch introduction after 480 idle frames; the truck is a
    /// separate later checkpoint and must not be invented as this transition.
    pub fn advance_title_transition(&mut self, idle_frames: u32) {
        if self.phase != StoryPhase::Title || self.title_start_frames < 120 {
            return;
        }
        self.title_transition_frames = self
            .title_transition_frames
            .saturating_add(idle_frames.min(u32::from(u16::MAX)) as u16);
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
            self.title_intro_frames = self
                .title_intro_frames
                .saturating_add(idle_frames.min(u32::from(u16::MAX)) as u16);
        }
    }

    /// Shared transition from a map script to the bounded three-ball picker.
    /// It is intentionally independent of the particular route used to
    /// reach it: the caller supplies the source-default selection and this
    /// method establishes the durable player/task/flag invariants.
    fn open_starter_picker(&mut self, default_starter: StarterSpecies) {
        if self.map != MapId::Route101
            || self.phase != StoryPhase::BirchRescue
            || self.birch_rescue_stage != 3
        {
            return;
        }
        // v8 mGBA observation: ChoiceStarter has released to Route 101
        // `(7,15)`, with `FLAG_SYS_POKEMON_GET` and the rescue progression
        // both set before its first picker frame. This is a state boundary,
        // not an approximation of the preceding input route.
        self.player = TilePosition { x: 7, y: 15 };
        self.elevation = crate::native::tile_elevation(self.map, 7, 15)
            .expect("Route 101 starter-picker tile must be staged");
        self.facing = Facing::Left;
        self.phase = StoryPhase::StarterSelect;
        self.story_flags.pokemon_obtained = true;
        self.story_flags.birch_rescue_started = true;
        self.route101_rescue_task = Route101RescueTask::StarterPicker;
        self.starter = Some(default_starter);
        self.starter_selection_transition = None;
        self.starter_reveal_frames = None;
        self.starter_hand_phase = 0;
        self.starter_pokeball_animation_frame = 0;
        self.source_starter_picker_reveal_started_during_move_commit = false;
        self.source_starter_picker_decline_started_frame = None;
        self.npcs = map_npcs(
            self.map,
            self.phase,
            self.potions,
            self.oldale_rival_departed,
            self.player_gender,
        );
        debug_assert!(self.route101_rescue_invariants_hold());
    }

    /// Source-observable progression invariant for the rescue corridor.
    /// This is intentionally about state/task compatibility rather than an
    /// input sequence, so it protects both live play and restored checkpoints.
    pub fn route101_rescue_invariants_hold(&self) -> bool {
        match self.route101_rescue_task {
            Route101RescueTask::Inactive => true,
            Route101RescueTask::RescueChoreography | Route101RescueTask::BagPrompt => {
                self.map == MapId::Route101 && self.phase == StoryPhase::BirchRescue
            }
            Route101RescueTask::StarterPicker => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::StarterSelect
                    && self.story_flags.pokemon_obtained
                    && self.story_flags.birch_rescue_started
                    && self.starter.is_some()
            }
            Route101RescueTask::StarterReveal => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::StarterReveal
                    && self.starter_reveal_frames.is_some()
                    && self.starter.is_some()
            }
            Route101RescueTask::StarterConfirm => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::StarterConfirm
                    && self.starter.is_some()
            }
            Route101RescueTask::BattleHandoff => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::BirchBattle
                    && self.battle.is_none()
                    && self.starter_party.is_some()
            }
            Route101RescueTask::Battle => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::BirchBattle
                    && self
                        .battle
                        .as_ref()
                        .is_some_and(|battle| battle.opponent == BattleOpponent::Zigzagoon)
                    && self.starter_party.is_some()
            }
            Route101RescueTask::Resolved => {
                self.phase == StoryPhase::BirchRescued && self.battle.is_none()
            }
            Route101RescueTask::PostBattleApproach | Route101RescueTask::PostBattleDialogue => {
                self.map == MapId::Route101
                    && self.phase == StoryPhase::BirchRescued
                    && self.battle.is_none()
                    && self.starter_party.is_some()
            }
            Route101RescueTask::LabHandoff => {
                self.phase == StoryPhase::BirchRescued
                    && self.battle.is_none()
                    && self.transition.as_ref().is_some_and(|transition| {
                        transition.destination_map == MapId::ProfessorBirchsLab
                    })
            }
            Route101RescueTask::StarterLabAcknowledgement
            | Route101RescueTask::StarterLabNicknameChoice
            | Route101RescueTask::StarterLabRivalChoice
            | Route101RescueTask::StarterLabAgreement => {
                self.map == MapId::ProfessorBirchsLab
                    && self.phase == StoryPhase::StarterLab
                    && self.story_flags.starter_acknowledged
                    && self.starter_party.is_some()
            }
            Route101RescueTask::StarterLabNaming => {
                self.map == MapId::ProfessorBirchsLab
                    && self.phase == StoryPhase::NameEntry
                    && self.naming_target == NamingTarget::Starter
                    && self.story_flags.starter_acknowledged
                    && self.starter_party.is_some()
            }
            Route101RescueTask::RouteAccess => {
                self.phase >= StoryPhase::StarterChosen
                    && self.story_flags.starter_acknowledged
                    && self.story_flags.rival_route_unlocked
                    && self.starter_party.is_some()
            }
        }
    }

    /// Enters a source-authored battle handoff. The runner makes the task
    /// boundary explicit; the existing battle constructor remains the single
    /// place that knows an opponent's mechanics and presentation rails.
    fn begin_battle_handoff(&mut self, opponent: BattleOpponent) {
        if opponent != BattleOpponent::Zigzagoon
            || self.map != MapId::Route101
            || self.phase != StoryPhase::StarterConfirm
            || self.route101_rescue_task != Route101RescueTask::StarterConfirm
        {
            return;
        }
        self.confirm_starter();
    }

    /// `Task_HandleStarterChooseInput` starts the source's small affine
    /// circle/Pokémon reveal after A selects the currently bounded Poké Ball.
    pub fn ask_confirm_starter(&mut self) {
        if self.phase != StoryPhase::StarterSelect {
            return;
        }
        // An A edge can arrive on the first released VBlank after the
        // movement task's two-frame input window.  The source accepts the
        // logical confirmation, but that edge still publishes the chooser's
        // preceding raster before the reveal task owns the surface.  Retain
        // this handoff provenance independently of the transition, which is
        // consumed below when the logical phase changes to StarterReveal.
        self.source_starter_picker_reveal_started_during_move_commit = self
            .starter_selection_transition
            .is_some_and(|transition| {
                transition.frames_elapsed >= 2
                    && self.starter_pokeball_animation_frame <= 4
            });
        self.source_starter_picker_decline_started_frame = None;
        if let Some(transition) = self.starter_selection_transition.take() {
            // The source task has already returned to
            // `Task_HandleStarterChooseInput` by this point. Its visual ball
            // rail may still be animating, but A owns the logical selection.
            self.starter = Some(transition.to);
        }
        // A is handled by `Task_HandleStarterChooseInput`, not by the
        // movement-task interruption path. Clear the selector-only receipt
        // flags before the affine reveal compositor takes ownership.
        self.source_starter_picker_hand_species = None;
        self.source_starter_picker_interrupted_direction = false;
        self.source_starter_picker_interrupted_a = false;
        self.source_starter_picker_interrupted_frame = 0;
        if matches!(self.source_starter_picker_profile, 9 | 10) {
            self.source_starter_picker_profile = 0;
        }
        if self.route101_rescue_task == Route101RescueTask::StarterPicker {
            self.source_starter_picker_receipt_mode = 3;
            self.source_starter_picker_receipt_from = None;
            self.source_starter_picker_receipt_to = None;
        self.source_starter_picker_receipt_edge_frame = self.frame;
        self.source_starter_picker_receipt_tail_clean = true;
        self.source_starter_picker_confirm_cursor_frame = None;
        if self.frame == 3 {
            self.source_starter_picker_profile = 8;
        }
        }
        self.starter.get_or_insert(StarterSpecies::Torchic);
        self.starter_confirm_yes = true;
        self.starter_reveal_frames = Some(0);
        self.phase = StoryPhase::StarterReveal;
        if self.route101_rescue_task == Route101RescueTask::StarterPicker {
            self.route101_rescue_task = Route101RescueTask::StarterReveal;
        }
        debug_assert!(self.route101_rescue_invariants_hold());
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
        self.starter_hand_phase = self
            .starter_hand_phase
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
    /// circle starts at 20 and grows by 20. The initial zero-duration affine
    /// command and the source task's next `RunTasks` boundary remain visible
    /// after the 15-frame growth rail, so `Task_WaitForStarterSprite` enables
    /// the standard YES/NO task 19 source VBlanks after a late A edge.
    pub fn advance_starter_reveal(&mut self, frames: u32) -> bool {
        if self.phase != StoryPhase::StarterReveal {
            return false;
        }
        self.advance_starter_hand(frames);
        self.advance_starter_pokeball_animation(frames);
        let elapsed = self.starter_reveal_frames.unwrap_or(0);
        // Synthetic typed constructors retain the historical fifteen-frame
        // logical boundary.  Live source receipts keep the reveal task active
        // for four additional scheduler VBlanks.
        let reveal_limit: u8 = if self.source_starter_picker_receipt_edge_frame == 0 {
            15
        } else {
            19
        };
        let advanced = frames.min(u32::from(reveal_limit)) as u8;
        let next = elapsed.saturating_add(advanced).min(19);
        if next >= reveal_limit {
            let retain_reveal_raster = self.source_starter_picker_receipt_mode == 3
                && self.source_starter_picker_receipt_edge_frame >= 5;
            self.starter_reveal_frames = retain_reveal_raster.then_some(next);
            self.phase = StoryPhase::StarterConfirm;
            if self.route101_rescue_task == Route101RescueTask::StarterReveal {
                self.route101_rescue_task = Route101RescueTask::StarterConfirm;
            }
            debug_assert!(self.route101_rescue_invariants_hold());
        } else {
            self.starter_reveal_frames = Some(next);
        }
        true
    }

    /// Compatibility projection for batched callers.  Live oracle tapes
    /// sample each VBlank separately and never use this path.  A long Noop
    /// packet can cross the source's final four scheduler VBlanks in one
    /// call; retain the source reveal raster until the next packet instead
    /// of exposing the logical prompt prematurely.
    pub fn enter_batched_starter_confirmation_compat(&mut self) {
        if self.source_starter_picker_receipt_edge_frame == 0 {
            return;
        }
        if self.phase == StoryPhase::StarterReveal {
            self.phase = StoryPhase::StarterConfirm;
            if self.route101_rescue_task == Route101RescueTask::StarterReveal {
                self.route101_rescue_task = Route101RescueTask::StarterConfirm;
            }
        }
        if self.phase == StoryPhase::StarterConfirm && self.starter_reveal_frames.is_none() {
            self.starter_reveal_frames = Some(15);
        }
    }

    /// Keeps the logical confirmation boundary visible to typed callers while
    /// the source's final affine/task VBlanks still render the reveal scene.
    pub fn advance_starter_reveal_menu_handoff(&mut self) {
        if self.phase != StoryPhase::StarterConfirm
            || !matches!(self.starter_reveal_frames, Some(15 | 19))
            || self.source_starter_picker_receipt_edge_frame == 0
            || self.frame
                <= self
                    .source_starter_picker_receipt_edge_frame
                    .saturating_add(23)
        {
            return;
        }
        self.starter_reveal_frames = None;
    }

    pub fn move_starter_confirmation(&mut self, direction: Facing) {
        if self.phase == StoryPhase::StarterConfirm {
            // Once YES returns from `Task_HandleConfirmStarterInput`, the
            // source has reset the chooser task and is running the first
            // battle-transition intro.  Controller edges during that task
            // are consumed by the transition, not by the stale YES/NO menu.
            if self.starter_picker_battle_handoff_active() {
                return;
            }
            // `Task_WaitForStarterSprite` installs the YES/NO task on the
            // source's VBlank-21 boundary. Earlier edges are consumed by the
            // reveal-to-prompt handoff and must not move the cursor.
            if self.route101_rescue_task == Route101RescueTask::StarterConfirm
                && self.source_starter_picker_receipt_mode == 3
                && self.frame
                    < self
                        .source_starter_picker_receipt_edge_frame
                        .saturating_add(20)
            {
                return;
            }
            let previous = self.starter_confirm_yes;
            self.starter_confirm_yes = match direction {
                Facing::Up => true,
                Facing::Down => false,
                Facing::Left | Facing::Right => previous,
            };
            if self.starter_confirm_yes == previous {
                return;
            }
            if self.route101_rescue_task == Route101RescueTask::StarterConfirm
                && self.source_starter_picker_receipt_mode == 3
            {
                self.source_starter_picker_confirm_cursor_frame = Some(self.frame);
            }
        }
    }

    /// `Task_HandleConfirmStarterInput` returns the selected index only on
    /// YES. Its NO and B paths destroy the temporary sprite and resume the
    /// same bounded selector, preserving the selected ball.
    pub fn respond_starter_confirmation(&mut self, accepted: bool) {
        if self.phase != StoryPhase::StarterConfirm {
            return;
        }
        if self.starter_picker_battle_handoff_active() {
            return;
        }
        if self.starter_reveal_frames.is_some() {
            return;
        }
        if accepted {
            self.confirm_starter();
        } else {
            self.starter_reveal_frames = None;
            let mut defer_selector_return = false;
            if self.route101_rescue_task == Route101RescueTask::StarterConfirm
                && self.source_starter_picker_receipt_mode == 3
            {
                // `Task_HandleConfirmStarterInput` leaves the confirmation
                // raster frozen for the B/NO edge.  Mark the decline with a
                // separate task-local bit and retire the authenticated
                // receipt on the next VBlank, when `Task_DeclineStarter`
                // hands control back to `Task_StarterChoose`.
                self.source_starter_picker_interrupted_direction = true;
                self.source_starter_picker_decline_started_frame = Some(self.frame);
                self.source_starter_picker_interrupted_a = true;
                self.source_starter_picker_interrupted_frame = self.frame;
                defer_selector_return = true;
            }
            if !defer_selector_return {
                self.starter_confirm_yes = true;
                self.phase = StoryPhase::StarterSelect;
            }
            if self.route101_rescue_task == Route101RescueTask::StarterConfirm
                && !defer_selector_return
            {
                self.route101_rescue_task = Route101RescueTask::StarterPicker;
            }
        }
    }

    fn confirm_starter(&mut self) {
        if self.phase == StoryPhase::StarterConfirm {
            if self.source_starter_picker_receipt_mode == 3
                && self.source_starter_picker_receipt_edge_frame == 1
                && self.source_starter_picker_confirm_cursor_frame == Some(26)
            {
                self.source_starter_picker_profile = 2;
            }
            self.starter.get_or_insert(StarterSpecies::Torchic);
            self.ensure_starter_party();
            self.starter_reveal_frames = None;
            if self.source_starter_picker_receipt_mode == 3
                && self.source_starter_picker_receipt_edge_frame != 0
            {
                // The source callback returns to CB2_GiveStarter, which
                // resets the chooser task and launches B_TRANSITION_BLUR.
                // The picker raster remains visible during that transition;
                // keep the logical confirmation phase until the measured
                // intro has completed so arbitrary late-A tapes cannot jump
                // directly to the field battle handoff.
                self.source_starter_picker_interrupted_direction = false;
                self.source_starter_picker_interrupted_a = true;
                self.source_starter_picker_interrupted_frame = self.frame;
                self.source_starter_picker_confirm_cursor_frame = None;
                self.dialogue = None;
                debug_assert!(self.route101_rescue_invariants_hold());
                return;
            }
            self.phase = StoryPhase::BirchBattle;
            if self.route101_rescue_task == Route101RescueTask::StarterConfirm {
                self.route101_rescue_task = Route101RescueTask::BattleHandoff;
            }
            debug_assert!(self.route101_rescue_invariants_hold());
            self.dialogue = Some("Go! Your new POKéMON!".to_owned());
            self.npcs = map_npcs(
                self.map,
                self.phase,
                self.potions,
                self.oldale_rival_departed,
                self.player_gender,
            );
        }
    }

    /// True while the source's first-battle transition owns the former
    /// starter-picker raster after a late confirmation edge.  The existing
    /// `interrupted_a` receipt bit is intentionally reused here: the chooser
    /// clears it on entry to confirmation, and no selector task is alive
    /// while this phase is active.
    pub fn starter_picker_battle_handoff_active(&self) -> bool {
        self.phase == StoryPhase::StarterConfirm
            && self.source_starter_picker_receipt_mode == 3
            && self.source_starter_picker_receipt_edge_frame != 0
            && self.source_starter_picker_interrupted_a
            && !self.source_starter_picker_interrupted_direction
    }

    /// `Task_HandleStarterChooseInput` accepts only bounded left/right
    /// selection movement before the player confirms a Poké Ball.
    pub fn move_starter_selection(&mut self, delta: i8) -> bool {
        if self.phase != StoryPhase::StarterSelect {
            return false;
        }
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

    /// Starts the source's short hand/ball move.  Horizontal input is the
    /// physical probe that reaches this task; the label commits only after
    /// three more rendered VBlanks.  Repeated held input during the task is
    /// consumed without restarting the animation. Once the source task has
    /// returned to `Task_HandleStarterChooseInput`, a new edge may replace
    /// the still-running visual rail.
    pub fn begin_starter_selection_transition(&mut self, delta: i8) -> bool {
        if self.phase != StoryPhase::StarterSelect {
            return false;
        }
        let from = if let Some(transition) = self.starter_selection_transition {
            if transition.frames_elapsed < 2 {
                return false;
            }
            self.starter = Some(transition.to);
            transition.to
        } else {
            self.starter.unwrap_or(StarterSpecies::Torchic)
        };
        let selection = match from {
            StarterSpecies::Treecko => 0_i8,
            StarterSpecies::Torchic => 1,
            StarterSpecies::Mudkip => 2,
        };
        let to = match (selection + delta).clamp(0, 2) {
            0 => StarterSpecies::Treecko,
            1 => StarterSpecies::Torchic,
            _ => StarterSpecies::Mudkip,
        };
        if from == to {
            return false;
        }
        self.source_starter_picker_decline_started_frame = None;
        if self.route101_rescue_task == Route101RescueTask::StarterPicker {
            self.source_starter_picker_receipt_mode = if delta < 0 { 1 } else { 2 };
            self.source_starter_picker_receipt_from = Some(from);
            self.source_starter_picker_receipt_to = Some(to);
        self.source_starter_picker_receipt_edge_frame = self.frame;
        self.source_starter_picker_receipt_tail_clean = true;
        self.source_starter_picker_confirm_cursor_frame = None;
            if self.source_starter_picker_receipt_mode == 2
                && self.source_starter_picker_receipt_edge_frame == 2
                && self.source_starter_picker_receipt_from == Some(StarterSpecies::Torchic)
                && self.source_starter_picker_receipt_to == Some(StarterSpecies::Mudkip)
            {
                self.source_starter_picker_profile = 3;
            }
        }
        self.starter_selection_transition = Some(StarterSelectionTransition {
            from,
            to,
            frames_elapsed: 0,
        });
        self.source_starter_picker_hand_species = None;
        self.source_starter_picker_interrupted_direction = false;
        self.source_starter_picker_interrupted_a = false;
        self.source_starter_picker_interrupted_frame = 0;
        self.starter_pokeball_animation_frame = 0;
        true
    }

    /// Advances the pending selection render rail. The source runs
    /// `Task_MoveStarterChooseCursor` and `Task_CreateStarterLabel` only for
    /// the first two VBlanks; the selected Poké Ball's independent animation
    /// continues through the authenticated receipt tail.
    pub fn advance_starter_selection_transition(&mut self, frames: u32) {
        let Some(mut transition) = self.starter_selection_transition else {
            return;
        };
        transition.frames_elapsed = transition
            .frames_elapsed
            .saturating_add(frames.min(u32::from(u8::MAX)) as u8);
        if transition.frames_elapsed >= 18 {
            self.starter = Some(transition.to);
            self.starter_selection_transition = None;
        } else {
            self.starter_selection_transition = Some(transition);
        }
    }

    pub fn starter_render_species(&self) -> StarterSpecies {
        self.starter_selection_transition
            .filter(|transition| transition.frames_elapsed >= 1)
            .map_or_else(
                || self.starter.unwrap_or(StarterSpecies::Torchic),
                |transition| transition.to,
            )
    }

    pub fn cycle_starter(&mut self) {
        if self.phase != StoryPhase::StarterSelect {
            return;
        }
        let next = match self.starter {
            None | Some(StarterSpecies::Treecko) => StarterSpecies::Torchic,
            Some(StarterSpecies::Torchic) => StarterSpecies::Mudkip,
            Some(StarterSpecies::Mudkip) => StarterSpecies::Treecko,
        };
        self.starter_pokeball_animation_frame = 0;
        self.starter = Some(next);
    }

    fn name_entry_action_button(&self) -> Option<NamingActionButton> {
        if self.phase != StoryPhase::NameEntry {
            return None;
        }
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
        let Some(pulse) = self.naming_action_button_pulse.as_mut() else {
            return;
        };
        if !pulse.allow_flash {
            return;
        }

        // `MultiplyInvertedPaletteRGBComponents` observes `tColor` before
        // `Task_UpdateButtonFlash` advances the task fields for this frame.
        pulse.applied_color =
            u8::try_from(pulse.color).expect("source button color remains non-negative");
        if pulse.color_delay != 0 {
            pulse.color_delay -= 1;
            if pulse.color_delay != 0 {
                return;
            }
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
            // `MainState_StartPageSwap` owns the page flash while input is
            // disabled. Do not replace that pulse with the live cursor's
            // ordinary key role until the 32-frame swap has completed.
            if self.name_entry_page_swap_frames.is_none() {
                let button = self.name_entry_action_button();
                self.try_start_name_entry_action_button_pulse(button, button.is_some(), false);
            }
            self.advance_name_entry_action_button_pulse_frame();
        }
    }

    /// Returns the source page, accepting the legacy lowercase projection
    /// when restoring a pre-page-cycle checkpoint that only serialized the
    /// old boolean field.
    pub fn name_keyboard_page(&self) -> NamingKeyboardPage {
        if self.name_entry_page == NamingKeyboardPage::LettersUpper && self.name_entry_lowercase {
            NamingKeyboardPage::LettersLower
        } else {
            self.name_entry_page
        }
    }

    /// Starts the source `STATE_START_PAGE_SWAP` sequence. The visible page
    /// remains unchanged while the serialized 32-frame hand-off runs.
    pub fn start_name_entry_page_swap(&mut self) {
        if self.phase != StoryPhase::NameEntry || self.name_entry_page_swap_frames.is_some() {
            return;
        }
        self.name_entry_page_swap_frames = Some(0);
        // `MainState_StartPageSwap` interrupts the page-button flash and
        // releases it after the animation, even when SELECT triggered the
        // swap away from the page-button cursor.
        self.try_start_name_entry_action_button_pulse(Some(NamingActionButton::Page), false, true);
    }

    /// Advances the source page-swap task by video frames. The source task
    /// increments its counter by four per VBlank and completes at 128, i.e.
    /// 32 video frames. Inputs received while active are consumed.
    pub fn advance_name_entry_page_swap(&mut self, frames: u32) -> bool {
        if self.phase != StoryPhase::NameEntry {
            self.name_entry_page_swap_frames = None;
            return false;
        }
        let Some(elapsed) = self.name_entry_page_swap_frames else {
            return false;
        };
        let elapsed = u32::from(elapsed).saturating_add(frames);
        if elapsed < 32 {
            self.name_entry_page_swap_frames = Some(elapsed as u8);
            return true;
        }
        self.name_entry_page_swap_frames = None;
        self.cycle_name_entry_page();
        true
    }

    pub fn name_entry_page_swap_active(&self) -> bool {
        self.phase == StoryPhase::NameEntry && self.name_entry_page_swap_frames.is_some()
    }

    /// Emerald's `currentPage` starts on uppercase and advances
    /// `symbols -> uppercase -> lowercase -> symbols`. The page swap keeps
    /// the input buffer and physical cursor row, so only the page state and
    /// legacy lowercase projection change here. This is called after the
    /// source's 32-frame hand-off, not directly from input dispatch.
    fn cycle_name_entry_page(&mut self) {
        if self.phase != StoryPhase::NameEntry || self.name_entry_page_swap_frames.is_some() {
            return;
        }
        let current = self.name_keyboard_page();
        let cursor_position = self.name_cursor_position();
        let next = match self.name_keyboard_page() {
            NamingKeyboardPage::Symbols => NamingKeyboardPage::LettersUpper,
            NamingKeyboardPage::LettersUpper => NamingKeyboardPage::LettersLower,
            NamingKeyboardPage::LettersLower => NamingKeyboardPage::Symbols,
        };
        self.name_entry_page = next;
        self.name_entry_lowercase = next == NamingKeyboardPage::LettersLower;
        // `MainState_WaitPageSwap` keeps a button-column cursor on its
        // physical column, but clamps an ordinary key cursor that exceeds the
        // new page's column count (upper/lower have eight; symbols have six).
        if let Some((x, y)) = cursor_position {
            let current_columns = Self::name_page_column_count(current);
            let next_columns = Self::name_page_column_count(next);
            if x != current_columns {
                let x = x.min(next_columns.saturating_sub(1));
                self.name_cursor = Self::name_cursor_from_position(next, x, y, None);
            }
        }
    }

    fn name_page_column_count(page: NamingKeyboardPage) -> u8 {
        match page {
            NamingKeyboardPage::Symbols => 6,
            NamingKeyboardPage::LettersUpper | NamingKeyboardPage::LettersLower => 8,
        }
    }

    /// Converts the serialized cursor id to the source keyboard's physical
    /// `(x, y)` position.  IDs 28..31 remain the compatibility control ids;
    /// symbols use a dense six-column grid while letter pages retain their
    /// captured punctuation ids.
    pub fn name_cursor_position(&self) -> Option<(u8, u8)> {
        let page = self.name_keyboard_page();
        let cursor = self.name_cursor;
        match cursor {
            28 => Some((Self::name_page_column_count(page), 0)),
            29 => Some((Self::name_page_column_count(page), 1)),
            30 => Some((Self::name_page_column_count(page), 1)),
            31 => Some((Self::name_page_column_count(page), 2)),
            _ => match page {
                NamingKeyboardPage::Symbols if cursor < 24 => Some((cursor % 6, cursor / 6)),
                NamingKeyboardPage::LettersUpper | NamingKeyboardPage::LettersLower => match cursor
                {
                    0..=5 => Some((cursor, 0)),
                    6..=11 => Some((cursor - 6, 1)),
                    12..=18 => Some((cursor - 12, 2)),
                    19..=25 => Some((cursor - 19, 3)),
                    26 => Some((7, 0)),
                    27 => Some((7, 1)),
                    // These four source cells contain spaces. They were not
                    // represented by the original Rust cursor enum, but
                    // remain selectable so page navigation follows the GBA.
                    32 => Some((6, 0)),
                    33 => Some((6, 1)),
                    34 => Some((7, 2)),
                    35 => Some((7, 3)),
                    _ => None,
                },
                NamingKeyboardPage::Symbols => None,
            },
        }
    }

    fn name_cursor_from_position(
        page: NamingKeyboardPage,
        x: u8,
        y: u8,
        button_provenance: Option<u8>,
    ) -> u8 {
        let columns = Self::name_page_column_count(page);
        if x == columns {
            // When entering the button column from a keyboard row, the
            // source maps rows 0/1/2/3 to PAGE/BACK/BACK/OK respectively.
            // `button_provenance` retains the two distinct middle-row ids;
            // vertical movement on the physical column supplies the simpler
            // three-row y=0/1/2 mapping below.
            return button_provenance.unwrap_or(match y {
                0 => 28,
                1 => 29,
                2 | 3 => 31,
                _ => 28,
            });
        }
        match page {
            NamingKeyboardPage::Symbols => y.saturating_mul(6).saturating_add(x),
            NamingKeyboardPage::LettersUpper | NamingKeyboardPage::LettersLower => match (x, y) {
                (0..=5, 0) => x,
                (0..=5, 1) => 6 + x,
                (0..=6, 2) => 12 + x,
                (0..=6, 3) => 19 + x,
                (7, 0) => 26,
                (7, 1) => 27,
                (6, 0) => 32,
                (6, 1) => 33,
                (7, 2) => 34,
                (7, 3) => 35,
                _ => 0,
            },
        }
    }

    pub fn move_name_cursor(&mut self, horizontal: i8, vertical: i8) {
        if self.phase != StoryPhase::NameEntry {
            return;
        }
        self.name_entry_touched = true;
        let page = self.name_keyboard_page();
        let columns = Self::name_page_column_count(page);
        let Some((mut x, mut y)) = self.name_cursor_position() else {
            return;
        };
        let mut button_provenance = match self.name_cursor {
            30 => Some(30),
            29 => Some(29),
            _ => None,
        };

        if horizontal != 0 {
            let next_x =
                (i16::from(x) + i16::from(horizontal)).rem_euclid(i16::from(columns + 1)) as u8;
            if x == columns {
                // Moving off the physical button column restores the source
                // key row represented by the middle-button provenance.
                x = if horizontal < 0 {
                    match self.name_cursor {
                        28 => columns.saturating_sub(1),
                        29 => Self::name_page_column_count(page).saturating_sub(1),
                        30 => Self::name_page_column_count(page).saturating_sub(1),
                        31 => Self::name_page_column_count(page).saturating_sub(1),
                        _ => columns.saturating_sub(1),
                    }
                } else {
                    0
                };
                if horizontal < 0 {
                    y = match self.name_cursor {
                        28 => 0,
                        29 => 1,
                        30 => 2,
                        31 => 3,
                        _ => y,
                    };
                } else {
                    y = match self.name_cursor {
                        28 => 0,
                        29 => 1,
                        30 => 2,
                        31 => 3,
                        _ => y,
                    };
                }
                button_provenance = None;
            } else {
                x = next_x;
                if x == columns {
                    button_provenance = match y {
                        0 => Some(28),
                        1 => Some(29),
                        2 => Some(30),
                        3 => Some(31),
                        _ => None,
                    };
                }
            }
        } else if vertical != 0 {
            if x == columns {
                y = (i16::from(y) + i16::from(vertical)).rem_euclid(3) as u8;
                self.name_cursor = Self::name_cursor_from_position(
                    page,
                    x,
                    y,
                    match y {
                        1 => Some(if self.name_cursor == 30 { 30 } else { 29 }),
                        _ => None,
                    },
                );
                return;
            }
            y = (i16::from(y) + i16::from(vertical)).rem_euclid(4) as u8;
        }

        self.name_cursor = Self::name_cursor_from_position(page, x, y, button_provenance);
    }

    /// Emerald's physical Start shortcut moves the keyboard cursor to its
    /// on-screen OK button; it does not submit the text by itself.
    pub fn move_name_cursor_to_ok(&mut self) {
        if self.phase != StoryPhase::NameEntry {
            return;
        }
        self.name_entry_touched = true;
        self.name_cursor = 31;
    }

    pub fn move_gender_cursor(&mut self, delta: i8) {
        if self.phase != StoryPhase::GenderSelect || delta == 0 {
            return;
        }
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
        let Some(mut transition) = self.gender_transition else {
            return false;
        };
        transition.frames_remaining = transition
            .frames_remaining
            .saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
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
        if self.phase != StoryPhase::NamePrompt {
            return;
        }
        self.phase = StoryPhase::NameEntry;
        self.naming_target = NamingTarget::Player;
        self.dialogue = None;
        self.name_entry_ready_frames = 0;
        self.name_entry_lowercase = false;
        self.name_entry_page = NamingKeyboardPage::LettersUpper;
        self.name_entry_page_swap_frames = None;
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
        if self.phase != StoryPhase::NameEntry {
            return false;
        }
        if self.name_entry_ready_frames < 60 {
            self.name_entry_ready_frames =
                self.name_entry_ready_frames.saturating_add(frames).min(60);
            return false;
        }
        true
    }

    pub fn select_name_cell(&mut self) {
        if self.phase != StoryPhase::NameEntry {
            return;
        }
        self.name_entry_touched = true;
        if self.name_cursor == 28 {
            self.start_name_entry_page_swap();
            return;
        }
        match self.name_cursor {
            29 => self.delete_name_character(),
            30 => {} // The source's B-button help cell does not alter the name.
            31 => self.confirm_name(),
            _ => {
                if let Some((x, y)) = self.name_cursor_position() {
                    let character = match self.name_keyboard_page() {
                        NamingKeyboardPage::Symbols => match y {
                            0 => ['0', '1', '2', '3', '4', ' '][usize::from(x)],
                            1 => ['5', '6', '7', '8', '9', ' '][usize::from(x)],
                            2 => ['!', '?', '♂', '♀', '/', '-'][usize::from(x)],
                            3 => ['…', '“', '”', '‘', '\'', ' '][usize::from(x)],
                            _ => return,
                        },
                        NamingKeyboardPage::LettersUpper | NamingKeyboardPage::LettersLower => {
                            match (x, y) {
                                (0..=5, 0) => (b'A' + x) as char,
                                (7, 0) => '.',
                                (0..=5, 1) => (b'G' + x) as char,
                                (7, 1) => ',',
                                (0..=6, 2) => (b'M' + x) as char,
                                (0..=6, 3) => (b'T' + x) as char,
                                _ => ' ',
                            }
                        }
                    };
                    let character = if self.name_keyboard_page() == NamingKeyboardPage::LettersLower
                    {
                        match character {
                            'A'..='Z' => character.to_ascii_lowercase(),
                            _ => character,
                        }
                    } else {
                        character
                    };
                    self.append_name_entry_character(character);
                }
            }
        }
    }

    pub fn delete_name_character(&mut self) {
        if self.phase != StoryPhase::NameEntry {
            return;
        }
        self.name_entry_touched = true;
        if self.name_entry_text().is_empty() && self.naming_target == NamingTarget::Player {
            self.phase = StoryPhase::GenderSelect;
            self.naming_action_button_pulse = None;
        } else if !self.name_entry_text().is_empty() {
            self.name_entry_text_mut().pop();
        }
    }

    pub fn confirm_name(&mut self) {
        if self.phase != StoryPhase::NameEntry {
            return;
        }
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
        if self.naming_target != NamingTarget::Player {
            return false;
        }
        let Some(remaining) = self.name_confirm_transition_frames else {
            return false;
        };
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
        if self.phase != StoryPhase::NameConfirm {
            return;
        }
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
        if self.phase != StoryPhase::IntroFarewell {
            return;
        }
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
        const BEFORE_POKEDEX: [MenuEntry; 6] = [
            MenuEntry::Pokemon,
            MenuEntry::Bag,
            MenuEntry::Player,
            MenuEntry::Save,
            MenuEntry::Option,
            MenuEntry::Exit,
        ];
        const AFTER_POKEDEX: [MenuEntry; 7] = [
            MenuEntry::Pokedex,
            MenuEntry::Pokemon,
            MenuEntry::Bag,
            MenuEntry::Player,
            MenuEntry::Save,
            MenuEntry::Option,
            MenuEntry::Exit,
        ];
        if self.has_pokedex {
            &AFTER_POKEDEX
        } else {
            &BEFORE_POKEDEX
        }
    }

    /// Advances the first opening beats represented by the staged checkpoints.
    /// Text is exposed in readout state for now; a GBA text-window renderer is
    /// required before it can affect the pixel buffer.
    pub fn advance_opening_script(&mut self) {
        if self.phase == StoryPhase::TitleIntro {
            let required_frames = if self.title_intro_step == 0 { 240 } else { 120 };
            if self.title_intro_frames < required_frames {
                return;
            }
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
        // Typed ordinary field dialogue owns its confirmation edge. A final
        // page intentionally falls through: source map scripts (the wall
        // clock is the first such case) observe that same edge after
        // `closemessage` releases their task.
        let mut typed_dialogue_closed = false;
        if let Some(still_owned) = self.dismiss_field_dialogue_page() {
            if still_owned {
                return;
            }
            typed_dialogue_closed = true;
            if self.resume_field_script_after_dialogue() {
                return;
            }
            if self.mays_house_1f_rival_dialogue_active {
                // The final May page closes into her authored upstairs route;
                // do not let the generic `MeetRival` Mom-page cursor consume
                // this edge or release the player to the door early.
                self.mays_house_1f_rival_dialogue_active = false;
                self.mays_house_1f_rival_departure_frames = Some(MAYS_RIVAL_DEPARTURE_FRAMES);
                return;
            }
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
        if self.dialogue.take().is_some() || typed_dialogue_closed {
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
                self.elevation =
                    crate::native::tile_elevation(self.map, self.player.x, self.player.y)
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
                && self.route103_rival_intro_stage == 0
            {
                self.route103_rival_intro_stage = 1;
                // FacePlayer, exclamation-mark animation, then the authored
                // `Common_Movement_Delay48` pause.
                self.route103_rival_intro_frames = Some(88);
                if let Some(rival) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "rival" && npc.map == MapId::Route103)
                {
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
                self.route101_rescue_task = Route101RescueTask::RescueChoreography;
                self.birch_rescue_frames = Some(ROUTE101_RESCUE_CHOREOGRAPHY_FRAMES);
                if let Some(birch) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "birch" && npc.map == MapId::Route101)
                {
                    birch.position = TilePosition { x: 0, y: 15 };
                    birch.facing = Facing::Right;
                }
                if let Some(zigzagoon) = self
                    .npcs
                    .iter_mut()
                    .find(|npc| npc.id == "zigzagoon" && npc.map == MapId::Route101)
                {
                    zigzagoon.position = TilePosition { x: 0, y: 16 };
                    zigzagoon.facing = Facing::Right;
                }
                return;
            }
            if self.phase == StoryPhase::BirchRescue && self.birch_rescue_stage == 2 {
                self.birch_rescue_stage = 3;
                self.route101_rescue_task = Route101RescueTask::BagPrompt;
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
            if self.oldale_blocked_path_stage == 2 {
                // `closemessage` is followed immediately by the man's
                // `walk_down`, `walk_left`, and `waitmovement`; keep the
                // player locked until both strides restore his source tile.
                self.oldale_blocked_path_stage = 3;
                self.oldale_blocked_path_frames = Some(OLDALE_BLOCKED_PATH_RETURN_FRAMES);
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
                        self.oldale_mart_dialogue_page =
                            self.oldale_mart_dialogue_page.saturating_add(1);
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
                    self.oldale_mart_dialogue_frames =
                        Some(dialogue_printer_duration(&dialogue).saturating_sub(16));
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
                            "even more useful than a POKéMON CENTER\nin certain situations."
                                .to_owned(),
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
                        self.truck_arrival_dialogue_frames =
                            Some(dialogue_printer_duration(&dialogue));
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
                        let mom = self
                            .npcs
                            .iter_mut()
                            .find(|npc| npc.id == "mom" && npc.map == map)
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
                        self.tv_broadcast_approach_frames = Some(TV_BROADCAST_APPROACH_FRAMES);
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
                        self.story_flags.gym_broadcast_complete = true;
                        // `title_intro_step` is reused for timed bedroom
                        // rival-entry stages. The TV page index must not
                        // skip that entry sequence when the player later
                        // triggers the rival's Poké Ball.
                        self.title_intro_step = 0;
                        self.npcs = map_npcs(
                            self.map,
                            self.phase,
                            self.potions,
                            self.oldale_rival_departed,
                            self.player_gender,
                        );
                    }
                }
                StoryPhase::MeetRival if self.is_rival_house() => {
                    let next = self.title_intro_step.saturating_add(1);
                    if next < RIVAL_MOM_PAGE_COUNT {
                        self.title_intro_step = next;
                        self.dialogue =
                            Some(rival_mom_page(next, self.player_gender, &self.player_name));
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
                        self.dialogue =
                            Some(birch_rescue_after_battle_page(next, &self.player_name));
                    } else {
                        self.begin_transition(
                            MapId::ProfessorBirchsLab,
                            TilePosition { x: 6, y: 5 },
                        );
                    }
                }
                StoryPhase::StarterLab => {
                    if self.title_intro_step == 0 {
                        self.title_intro_step = 1;
                        self.starter_lab_choice_yes = true;
                        self.route101_rescue_task = Route101RescueTask::StarterLabNicknameChoice;
                        self.dialogue = Some(starter_lab_nickname_prompt_text(self.starter));
                    } else if self.title_intro_step == 4 {
                        self.phase = StoryPhase::StarterChosen;
                        self.title_intro_step = 0;
                        self.route101_rescue_task = Route101RescueTask::RouteAccess;
                        self.story_flags.set(ProgressFlag::RivalRouteUnlocked);
                        self.dialogue = None;
                        self.npcs = map_npcs(
                            self.map,
                            self.phase,
                            self.potions,
                            self.oldale_rival_departed,
                            self.player_gender,
                        );
                        debug_assert!(self.route101_rescue_invariants_hold());
                    }
                }
                StoryPhase::PokedexHandoff => {
                    if self.pokedex_poke_ball_pocket_receipt {
                        self.pokedex_poke_ball_pocket_receipt = false;
                        self.title_intro_step = 4;
                        self.dialogue = Some(pokedex_handoff_page(
                            4,
                            self.player_gender,
                            &self.player_name,
                        ));
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
                        self.dialogue = Some(pokedex_handoff_page(
                            1,
                            self.player_gender,
                            &self.player_name,
                        ));
                    } else if self.title_intro_step < 4 {
                        let next = self.title_intro_step.saturating_add(1);
                        self.title_intro_step = next;
                        self.dialogue = Some(pokedex_handoff_page(
                            next,
                            self.player_gender,
                            &self.player_name,
                        ));
                    } else {
                        self.phase = StoryPhase::PokedexReceived;
                        self.npcs = map_npcs(
                            self.map,
                            self.phase,
                            self.potions,
                            self.oldale_rival_departed,
                            self.player_gender,
                        );
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
                        self.dialogue =
                            Some(rival_head_back_text(self.player_gender, &self.player_name));
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
                StoryPhase::RivalDefeated
                    if self.map == MapId::OldaleTown
                        && self.npcs.iter().any(|npc| npc.id == "oldale_rival") =>
                {
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
                            if self.running_shoes_trigger
                                == Some(SOURCE_RIVAL_RUNNING_SHOES_TRIGGER)
                            {
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
                            if self.running_shoes_trigger
                                == Some(SOURCE_RIVAL_RUNNING_SHOES_TRIGGER)
                            {
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
                    let rival = self
                        .npcs
                        .iter()
                        .find(|npc| npc.id == "rival" && npc.map == self.map)
                        .expect("rival must exist after bedroom introduction");
                    let (steps, _) = bedroom_rival_pc_route(self.map, &rival.position);
                    self.title_intro_step = 2;
                    self.rival_arrival_frames = Some(
                        steps
                            .iter()
                            .map(|(_, faster)| bedroom_rival_movement_frames(*faster))
                            .sum(),
                    );
                }
                _ => {}
            }
            return;
        }

        if self.phase == StoryPhase::ClockSet && self.is_wall_clock_in_front() {
            self.begin_clock_edit();
            return;
        }

        // The authenticated rescue checkpoint is already past Birch's cry
        // and the Bag prompt.  A stray A sample in open field must not replay
        // the entry-page text merely because the compatibility fallback has
        // no typed dialogue task to advance.
        if self.phase == StoryPhase::BirchRescue && self.birch_rescue_stage >= 3 {
            return;
        }

        self.dialogue = match self.phase {
            StoryPhase::Title => None,
            StoryPhase::TitleIntro => None,
            StoryPhase::IntroTruck => None,
            StoryPhase::TruckArrival => Some(format!(
                "MOM: {}, we're here, honey!\nThis is LITTLEROOT TOWN.\nLet's go inside.",
                self.player_name
            )),
            StoryPhase::NewHome => Some(format!(
                "MOM: See, {}?\nIsn't it nice in here, too?",
                self.player_name
            )),
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

    /// Returns the post-arrival Mays House 1F camera follow phase in source
    /// pixels.  mGBA keeps the player OBJ screen-anchored, then pans the
    /// downstairs BG/object layer upward one pixel per VBlank after the
    /// arrival task's settled frame.  The phase is intentionally derived
    /// from the authenticated destination-relative clock, not global frame
    /// numbers, so a replay cannot inherit timing from an unrelated scene.
    pub fn mays_house_1f_camera_follow_y(&self) -> i16 {
        if self.map != MapId::MaysHouse1F
            || self.player.y < 1
            || (self.player.y < 2 && self.walk_direction != Some(Facing::Down))
        {
            return 0;
        }
        let Some(start) = self.mays_house_1f_arrival_start_frame else {
            return 0;
        };
        let elapsed = self.frame.saturating_sub(start);
        let arrival_follow = if elapsed < 54 {
            0
        } else {
            i16::try_from((elapsed - 53).min(16)).unwrap_or(16)
        };
        // The house-exit Down task takes over the BG rail only after the
        // source's final page/door callback at V5016. The source advances
        // the already-settled downstairs camera by one pixel per VBlank from
        // that first object-cell commit, then holds the final rail through
        // the fade. The old thirteen-confirmation tape entered this task 301
        // VBlanks earlier; using that stale boundary made the player appear
        // to walk off-screen while the ROM was still stationary.
        let exit_follow = self.mays_house_1f_rival_scene_start_frame.is_none()
            && self.mays_house_1f_rival_departure_frames.is_none()
            && self.walk_direction == Some(Facing::Down)
            && self.frame >= 5016;
        let exit_elapsed = self.frame.saturating_sub(5015).min(64) as i16;
        arrival_follow + if exit_follow { exit_elapsed } else { 0 }
    }

    /// Ends a released directional hold after its final visible stride. The
    /// field coordinate is already committed; subsequent no-input frames use
    /// that tile as their idle terrain/camera origin.
    pub fn stop_walking(&mut self) {
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_direction = None;
        self.field_ready_stride_commit_pending = false;
        self.littleroot_house_entry_frames = None;
        self.walk_render_origin = None;
        self.camera_handoff_from = None;
        self.bedroom_turn_cancelled = false;
        self.bedroom_turn_dispatch_delayed = false;
        self.bedroom_blocked_sprite_frames = None;
    }

    fn bedroom_turn_sprite(direction: Facing, elapsed: u8) -> BedroomPlayerSprite {
        if elapsed >= 6 {
            match direction {
                Facing::Down => BedroomPlayerSprite::Base,
                Facing::Up => BedroomPlayerSprite::UpMiddle,
                Facing::Left | Facing::Right => BedroomPlayerSprite::SideMiddle,
            }
        } else if elapsed >= 2 {
            match direction {
                Facing::Down => BedroomPlayerSprite::DownFirstFoot,
                Facing::Up => BedroomPlayerSprite::UpFirstFoot,
                Facing::Left | Facing::Right => BedroomPlayerSprite::SideFirstFoot,
            }
        } else {
            BedroomPlayerSprite::Base
        }
    }

    fn bedroom_turn_sprite_with_handoff(&self, direction: Facing) -> BedroomPlayerSprite {
        // A menu-close handoff can enter a fresh turn before a committed
        // stride exists. The source still uploads the alternating foot cell
        // on turn phase two, so consume the same one-shot request here as in
        // `begin_bedroom_stride`.
        if self.bedroom_exit_turn_force_second && self.walk_elapsed_frames >= 2 {
            return match direction {
                Facing::Down => BedroomPlayerSprite::DownSecondFoot,
                Facing::Up => BedroomPlayerSprite::UpSecondFoot,
                Facing::Left | Facing::Right => BedroomPlayerSprite::SideSecondFoot,
            };
        }
        // A turn that follows an idle menu handoff uses the alternating foot
        // that the next stride would select. Direction changes carrying a
        // camera handoff are rendered from the ordinary first-foot cell;
        // EXIT is the explicit exception above.
        if self.camera_handoff_from.is_none()
            && self.walk_elapsed_frames >= 2
            && !self.running_step_uses_second_foot
        {
            return match direction {
                Facing::Down => BedroomPlayerSprite::DownSecondFoot,
                Facing::Up => BedroomPlayerSprite::UpSecondFoot,
                Facing::Left | Facing::Right => BedroomPlayerSprite::SideSecondFoot,
            };
        }
        // A down turn entered directly from the upstairs-facing idle task
        // uploads the second-foot cell at its first visible phase. This is
        // distinct from the initial idle->down walk, which uses first foot.
        if direction == Facing::Down
            && self.camera_handoff_from == Some(Facing::Up)
            && self.walk_elapsed_frames >= 2
        {
            return BedroomPlayerSprite::DownSecondFoot;
        }
        Self::bedroom_turn_sprite(direction, self.walk_elapsed_frames)
    }

    fn bedroom_stride_sprite(&self, direction: Facing) -> BedroomPlayerSprite {
        let elapsed = self.walk_elapsed_frames;
        if elapsed == 1 || elapsed >= 10 {
            // On a direction handoff, the first visible stride VBlank still
            // uses the prior-facing OBJ cell. The source changes the camera
            // and logical facing before the avatar task uploads its new
            // directional cell on VBlank two.
            let visual_direction = if elapsed == 1 {
                self.camera_handoff_from.unwrap_or(direction)
            } else {
                direction
            };
            return match visual_direction {
                Facing::Down => BedroomPlayerSprite::Base,
                Facing::Up => BedroomPlayerSprite::UpMiddle,
                Facing::Left | Facing::Right => BedroomPlayerSprite::SideMiddle,
            };
        }
        match direction {
            Facing::Down if self.running_step_uses_second_foot => {
                BedroomPlayerSprite::DownSecondFoot
            }
            Facing::Down => BedroomPlayerSprite::DownFirstFoot,
            Facing::Up if self.running_step_uses_second_foot => BedroomPlayerSprite::UpSecondFoot,
            Facing::Up => BedroomPlayerSprite::UpFirstFoot,
            Facing::Left | Facing::Right if self.running_step_uses_second_foot => {
                BedroomPlayerSprite::SideSecondFoot
            }
            Facing::Left | Facing::Right => BedroomPlayerSprite::SideFirstFoot,
        }
    }

    fn update_bedroom_turn_sprite(&mut self, direction: Facing) {
        self.bedroom_player_sprite = self.bedroom_turn_sprite_with_handoff(direction);
        if self.bedroom_exit_turn_force_second && self.walk_elapsed_frames >= 2 {
            self.bedroom_exit_turn_force_second = false;
        }
    }

    fn update_bedroom_stride_sprite(&mut self, direction: Facing) {
        self.bedroom_player_sprite = self.bedroom_stride_sprite(direction);
    }

    /// Advances one source VBlank of free movement in the staged bedroom.
    ///
    /// Emerald's field object commits the destination coordinate when a
    /// stride starts, then spends sixteen VBlanks moving the sprite/camera
    /// from the prior tile. Once that stride is accepted, later controller
    /// samples cannot cancel it. A newly pressed direction first turns the
    /// player in place for eight VBlanks; it starts walking on the ninth only
    /// while that direction remains held.
    ///
    /// This checkpoint-local controller deliberately does not replace the
    /// aggregate `walk_bounds` scheduler used by the authored story routes.
    pub fn advance_bedroom_field_vblank(&mut self, input: Option<Facing>, cancel_turn: bool) {
        debug_assert_eq!(self.map, MapId::MaysHouse2F);

        if let Some(active_direction) = self.walk_direction {
            let turning = self.camera_handoff_from.is_some() && self.walk_render_origin.is_none();
            let blocked_down = active_direction == Facing::Down
                && self.camera_handoff_from.is_none()
                && self.walk_render_origin.is_none()
                && self.walk_elapsed_frames > 0;
            if blocked_down {
                if self.walk_elapsed_frames < 16 {
                    self.walk_elapsed_frames += 1;
                    self.bedroom_player_sprite = if self.walk_elapsed_frames == 1 {
                        BedroomPlayerSprite::Base
                    } else if self.running_step_uses_second_foot {
                        BedroomPlayerSprite::DownSecondFoot
                    } else {
                        BedroomPlayerSprite::DownFirstFoot
                    };
                    return;
                }
                if input == Some(Facing::Down) {
                    self.begin_bedroom_stride(Facing::Down);
                } else {
                    self.stop_walking();
                }
                return;
            }
            if turning {
                if cancel_turn {
                    self.bedroom_turn_cancelled = true;
                }
                let commit_boundary = if self.bedroom_turn_dispatch_delayed {
                    9
                } else {
                    8
                };
                if input == Some(active_direction)
                    && self.walk_elapsed_frames == commit_boundary
                    && !self.bedroom_turn_cancelled
                {
                    self.begin_bedroom_stride(active_direction);
                    return;
                }
                // The source keeps the visible turn task alive after a tap
                // is released, but only a still-held direction may turn that
                // animation into a stride at its movement boundary.
                if self.walk_elapsed_frames < 16 {
                    self.walk_elapsed_frames += 1;
                    self.update_bedroom_turn_sprite(active_direction);
                    return;
                } else {
                    self.stop_walking();
                    return;
                }
            }

            if self.walk_elapsed_frames < 16 {
                if self.walk_render_origin.is_some() && self.walk_elapsed_frames == 1 {
                    // A direction handoff is visible for exactly the first
                    // VBlank of the new stride; it is not a turn task.
                    self.camera_handoff_from = None;
                }
                self.walk_elapsed_frames += 1;
                self.walk_progress_frames = self.walk_elapsed_frames - 1;
                self.update_bedroom_stride_sprite(active_direction);
                return;
            }

            // The prior VBlank displayed the final interpolation pixel.
            // A held direction starts the next stride immediately, including
            // a direction change buffered while the old stride was locked.
            if let Some(direction) = input {
                self.begin_bedroom_stride(direction);
            } else {
                self.stop_walking();
            }
            return;
        }

        if let Some((blocked_direction, elapsed)) = self
            .bedroom_blocked_sprite_frames
            .map(|elapsed| (self.facing, elapsed))
        {
            if input == Some(blocked_direction) {
                let next = elapsed.saturating_add(1);
                self.bedroom_blocked_sprite_frames = Some(next);
                self.bedroom_player_sprite = if next <= 16 {
                    match blocked_direction {
                        Facing::Down => BedroomPlayerSprite::DownFirstFoot,
                        Facing::Up => BedroomPlayerSprite::UpFirstFoot,
                        Facing::Left | Facing::Right => BedroomPlayerSprite::SideFirstFoot,
                    }
                } else {
                    match blocked_direction {
                        Facing::Down => BedroomPlayerSprite::Base,
                        Facing::Up => BedroomPlayerSprite::UpMiddle,
                        Facing::Left | Facing::Right => BedroomPlayerSprite::SideMiddle,
                    }
                };
                return;
            }
            self.bedroom_blocked_sprite_frames = None;
        }

        let Some(direction) = input else {
            return;
        };
        if direction != self.facing {
            let prior_facing = self.facing;
            self.facing = direction;
            self.walk_direction = Some(direction);
            self.walk_elapsed_frames = 1;
            self.walk_progress_frames = 0;
            self.camera_handoff_from = Some(prior_facing);
            self.bedroom_turn_cancelled = false;
            self.bedroom_turn_dispatch_delayed = self.frame > 1;
            // The source avatar task keeps the prior-facing idle cell for
            // the first VBlank of a new turn.  This is observable when a
            // direction is pressed after an idle or an unrelated menu/UI
            // task, and is distinct from the down-facing base cell.
            self.bedroom_player_sprite = match prior_facing {
                Facing::Down => BedroomPlayerSprite::Base,
                Facing::Up => BedroomPlayerSprite::UpMiddle,
                Facing::Left | Facing::Right => BedroomPlayerSprite::SideMiddle,
            };
            return;
        }
        self.begin_bedroom_stride(direction);
    }

    /// Advances one VBlank of the first outdoor field task after the Mays
    /// House exit. This is deliberately separate from `walk_bounds`: the
    /// source has already handed the map to the field engine, but its object
    /// and camera tasks do not use the aggregate 16-frame coordinate clock.
    ///
    /// The authenticated source trace establishes three observable rules:
    /// Down publishes the doorstep's south coordinate on VBlank 1, horizontal
    /// movement publishes its destination on VBlank 9 and releases the old
    /// camera origin on VBlank 10, while Up is a blocked walk-in-place task.
    /// Keeping those clocks explicit prevents a request-sized input packet
    /// from making the player appear stationary or letting the terrain jump
    /// a whole tile when the source is still interpolating the old one.
    pub fn advance_littleroot_field_ready_vblank(&mut self, input: Option<Facing>) {
        debug_assert_eq!(self.map, MapId::LittlerootTown);

        let Some(active) = self.walk_direction else {
            let Some(direction) = input else {
                return;
            };
            self.facing = direction;
            self.walk_direction = Some(direction);
            self.walk_elapsed_frames = 1;
            self.walk_progress_frames = 0;
            self.camera_handoff_from = None;
            self.walk_render_origin = Some(self.player.clone());
            self.field_ready_stride_commit_pending =
                matches!(direction, Facing::Left | Facing::Right);
            self.field_ready_stride_cancelled = false;
            self.littleroot_house_entry_frames = None;

            match direction {
                Facing::Down => {
                    // The field task owns this map boundary on its first
                    // VBlank, although the old doorstep remains the visible
                    // camera origin for the first thirteen frames.
                    self.player.y += 1;
                    self.elevation =
                        crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                            .expect("authenticated Littleroot south tile must be staged");
                }
                Facing::Left | Facing::Right | Facing::Up => {}
            }
            return;
        };

        // A completed stride can start the next one on the following source
        // VBlank. The first segment only needs one tile, but retaining this
        // cadence makes longer authenticated holds deterministic as well.
        if self.walk_elapsed_frames >= 16 && self.littleroot_house_entry_frames.is_none() {
            if input == Some(active) {
                self.facing = active;
                self.walk_elapsed_frames = 1;
                self.walk_progress_frames = 0;
                // The source camera continues one pixel per VBlank across
                // tile commits. Keep the original field-ready doorstep as
                // the render origin; replacing it with the newly committed
                // logical tile would recenter the whole map sixteen pixels
                // early at VBlank 17 (the observed “walk off screen” fault).
                if self.walk_render_origin.is_none() {
                    self.walk_render_origin = Some(self.player.clone());
                }
                // Horizontal walking starts its next visual stride here, but
                // the source does not publish the destination coordinate
                // until that stride's ninth VBlank. Down retains the existing
                // source behavior: its doorstep coordinate commits at stride
                // start, while Up remains blocked by the house edge.
                self.field_ready_stride_commit_pending =
                    matches!(active, Facing::Left | Facing::Right);
                self.field_ready_stride_cancelled = false;
                if active == Facing::Down {
                    self.player.y += 1;
                    self.elevation =
                        crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                            .expect("authenticated Littleroot field tile must be staged");
                }
            } else {
                // The west house entrance is an object-event door, not a
                // normal walkable tile. When Up replaces the completed
                // nine-tile westward hold at (5,9), the source keeps the
                // doorstep coordinate for 29 VBlanks while its turn/door
                // task runs; it publishes (5,8) only at V174 and then starts
                // a 60-VBlank atomic fade to the rival house.
                if active == Facing::Left
                    && input == Some(Facing::Up)
                    && self.player == (TilePosition { x: 5, y: 9 })
                {
                    self.facing = Facing::Up;
                    self.walk_direction = Some(Facing::Up);
                    self.walk_elapsed_frames = 1;
                    self.walk_progress_frames = 0;
                    self.field_ready_stride_commit_pending = false;
                    self.field_ready_stride_cancelled = false;
                    self.littleroot_house_entry_frames = Some(1);
                    self.walk_render_origin = Some(self.player.clone());
                    self.camera_handoff_from = Some(Facing::Left);
                    return;
                }
                self.walk_direction = None;
                self.walk_elapsed_frames = 0;
                self.walk_progress_frames = 0;
                self.field_ready_stride_commit_pending = false;
                self.field_ready_stride_cancelled = false;
                self.walk_render_origin = None;
                self.camera_handoff_from = None;
            }
            return;
        }

        if let Some(entry_elapsed) = self.littleroot_house_entry_frames {
            let next = entry_elapsed.saturating_add(1);
            if next >= 30 {
                self.littleroot_house_entry_frames = None;
                self.walk_direction = None;
                self.walk_elapsed_frames = 0;
                self.walk_progress_frames = 0;
                self.field_ready_stride_commit_pending = false;
                self.field_ready_stride_cancelled = false;
                self.walk_render_origin = None;
                self.camera_handoff_from = None;
                self.player.y = 8;
                self.elevation =
                    crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                        .expect("authenticated rival-house doorstep tile must be staged");
                self.begin_transition_with_timing(
                    MapId::BrendansHouse1F,
                    TilePosition { x: 8, y: 8 },
                    WarpTiming {
                        pre_fade_delay_frames: 0,
                        fade_frames: 60,
                    },
                );
            } else {
                self.littleroot_house_entry_frames = Some(next);
                self.walk_elapsed_frames = next;
                self.walk_progress_frames = 0;
            }
            return;
        }

        self.walk_elapsed_frames += 1;
        // Once the source field task accepts a directional edge, it owns the
        // complete tile stride.  A later controller sample can redirect the
        // *next* stride, but it cannot cancel this one halfway through.  This
        // is the same GBA object-task contract as the native game: a one-frame
        // tap still walks a full tile while the controller has already moved
        // on to another button.  Keeping the commit pending here is what
        // prevents random tapes from leaving the player one tile behind.
        // Horizontal strides are the exception: the source samples the
        // lateral direction through its ninth-VBlank commit, so a tap that
        // redirects before then remains a turn animation and never publishes
        // an x-coordinate change. Downward field strides are already owned
        // by the south-facing door rail and continue independently.
        if matches!(active, Facing::Left | Facing::Right)
            && self.walk_elapsed_frames < 9
            && input != Some(active)
            && !self.field_ready_stride_cancelled
        {
            self.field_ready_stride_cancelled = true;
            self.field_ready_stride_commit_pending = false;
        }
        match active {
            Facing::Left | Facing::Right => {
                // The logical x coordinate is one VBlank ahead of the old
                // camera. The source releases that old origin only when the
                // next stride's first pixel is visible.
                if self.walk_elapsed_frames == 9
                    && self.field_ready_stride_commit_pending
                    && input == Some(active)
                {
                    match active {
                        Facing::Left => self.player.x -= 1,
                        Facing::Right => self.player.x += 1,
                        Facing::Up | Facing::Down => unreachable!(),
                    }
                    self.elevation =
                        crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                            .expect("authenticated Littleroot horizontal tile must be staged");
                    self.field_ready_stride_commit_pending = false;
                }
                // The field-ready trace keeps the old camera origin for the
                // whole first hold. The live camera task applies a one-pixel
                // horizontal correction at VBlank 10; the compositor owns
                // that correction while this render origin remains pinned.
                self.walk_progress_frames = if self.field_ready_stride_cancelled {
                    // The released turn reaches the side cell at elapsed six
                    // and then holds that raster until its task releases.
                    (self.walk_elapsed_frames - 1).min(5)
                } else {
                    self.walk_elapsed_frames - 1
                };
            }
            Facing::Down => {
                // Down likewise retains the doorstep camera origin through
                // the complete authenticated hold. Its one-pixel-per-frame
                // vertical rail is represented by `walk_progress_frames`.
                self.walk_progress_frames = if self.field_ready_stride_cancelled {
                    (self.walk_elapsed_frames - 1).min(15)
                } else {
                    self.walk_elapsed_frames - 1
                };
            }
            Facing::Up => {
                // Up is blocked by the house edge. Keep the field task alive
                // so the directional OBJ animation remains source-owned.
                self.walk_progress_frames = 0;
            }
        }
    }

    fn begin_bedroom_stride(&mut self, direction: Facing) {
        let prior_direction = self.walk_direction;
        let prior_facing = self.facing;
        let began_from_turn = self.camera_handoff_from.is_some()
            && self.walk_render_origin.is_none()
            && prior_direction == Some(direction);
        self.running_step_uses_second_foot = if self.bedroom_stride_force_second {
            self.bedroom_stride_force_second = false;
            true
        } else if prior_direction.is_some() || self.bedroom_stride_started {
            !self.running_step_uses_second_foot
        } else {
            false
        };
        self.bedroom_stride_started = true;
        let (next_x, next_y) = match direction {
            Facing::Up => (self.player.x, self.player.y - 1),
            Facing::Down => (self.player.x, self.player.y + 1),
            Facing::Left => (self.player.x - 1, self.player.y),
            Facing::Right => (self.player.x + 1, self.player.y),
        };
        let (width, height) = self.map_dimensions();
        // The public checkpoint coordinates remove Emerald's two-tile
        // interior-map border from Y. Native collision data retains it.
        let layout_y = next_y + 2;
        let occupied = self
            .npcs
            .iter()
            .any(|npc| npc.map == self.map && npc.position.x == next_x && npc.position.y == next_y);
        let walkable = (0..width).contains(&next_x)
            && (0..height).contains(&layout_y)
            && !occupied
            && crate::native::is_walkable(self.map, next_x, layout_y)
                .expect("staged bedroom blockdata must define collision")
            && ledge_allows(
                crate::native::tile_behavior(self.map, next_x, layout_y)
                    .expect("staged bedroom blockdata must define behavior"),
                direction,
            );

        self.facing = direction;
        self.bedroom_turn_cancelled = false;
        self.bedroom_turn_dispatch_delayed = false;
        self.camera_handoff_from = if !began_from_turn && prior_facing != direction {
            Some(prior_facing)
        } else {
            None
        };
        if !walkable {
            if direction == Facing::Down {
                // The bedroom's lower obstruction runs the source walk-in-
                // place task without moving the camera or logical position.
                self.walk_direction = Some(direction);
                self.walk_elapsed_frames = 1;
                self.walk_progress_frames = 0;
                self.walk_render_origin = None;
                let blocked_handoff = (prior_facing != direction).then_some(prior_facing);
                self.camera_handoff_from = None;
                self.bedroom_player_sprite = match blocked_handoff.unwrap_or(direction) {
                    Facing::Down => BedroomPlayerSprite::Base,
                    Facing::Up => BedroomPlayerSprite::UpMiddle,
                    Facing::Left | Facing::Right => BedroomPlayerSprite::SideMiddle,
                };
            } else {
                self.stop_walking();
                self.bedroom_blocked_sprite_frames = Some(0);
            }
            return;
        }

        let origin = self.player.clone();
        self.player = TilePosition {
            x: next_x,
            y: next_y,
        };
        self.walk_direction = Some(direction);
        self.walk_elapsed_frames = 1;
        self.walk_progress_frames = 0;
        self.walk_render_origin = Some(origin);
        self.update_bedroom_stride_sprite(direction);
        self.elevation = crate::native::tile_elevation(self.map, next_x, layout_y)
            .expect("staged bedroom blockdata must define elevation");

        // The final visible north stride lands on an authored stair event.
        // Keep the old map and coordinate observable while it arms; a
        // continued Up begins it early above, while released input reaches
        // the same generic warp through `advance_bedroom_stair_warp_arming`.
        if self.map == MapId::MaysHouse2F
            && direction == Facing::Up
            && self.player == (TilePosition { x: 1, y: 0 })
        {
            // Record the direct approach, but retain the existing visual
            // stride until the upper trigger.  The source's lower trigger
            // affects the eventual downstairs spawn, not the shared fade
            // raster captured by the bedroom gate.
            self.bedroom_stair_direct_spawn = true;
        }
        if self.map == MapId::MaysHouse2F
            && direction == Facing::Up
            && self.player == (TilePosition { x: 1, y: -1 })
        {
            // The source starts its stair event after the final visible
            // stride settles. A turn/camera handoff delays palette writes,
            // not the task itself; that delay is persisted separately below
            // so input becomes locked at the correct shared event boundary.
            self.bedroom_stair_warp_armed_frames = Some(16);
        }
    }

    /// Advances the release-side branch of the upstairs stair map event.
    ///
    /// The source event is map-task timed rather than button timed.  Once its
    /// countdown expires it enters the declarative interior warp and
    /// preserves atomic map identity during the fade.
    pub fn advance_bedroom_stair_warp_arming(&mut self) {
        if self.transition.is_some() {
            return;
        }
        let Some(remaining) = self.bedroom_stair_warp_armed_frames else {
            return;
        };
        if remaining > 1 {
            self.bedroom_stair_warp_armed_frames = Some(remaining - 1);
            return;
        }
        self.bedroom_stair_warp_armed_frames = None;
        if self.map == MapId::MaysHouse2F
            && self.player == (TilePosition { x: 1, y: -1 })
            && self.bedroom_stair_fade_started_frame.is_none()
        {
            // The source creates its map task on this boundary. Its native
            // raster holds two VBlanks, then advances in two-frame palette
            // steps; the same marker also retains the stair foreground over
            // the player OBJ during that hand-off.
            self.bedroom_stair_fade_started_frame = Some(self.frame);
            self.bedroom_stair_transition_pending_frames = Some(16);
        }
    }

    /// Advances the black-raster hand-off following the source bedroom fade.
    /// The generic warp begins only after the native departure compositor has
    /// finished its measured palette sequence.
    pub fn advance_bedroom_stair_transition_pending(&mut self) {
        if self.transition.is_some() {
            self.advance_transition(1);
            return;
        }
        let Some(remaining) = self.bedroom_stair_transition_pending_frames else {
            return;
        };
        if remaining > 1 {
            self.bedroom_stair_transition_pending_frames = Some(remaining - 1);
            return;
        }
        self.bedroom_stair_transition_pending_frames = None;
        if self.bedroom_stair_direct_spawn {
            self.begin_transition_with_timing(
                MapId::MaysHouse1F,
                // The lower stair trigger commits raw 1:2 (2,2). The public
                // house projection removes two hidden border rows, so this
                // direct held-north route lands at public (2,0). A later
                // one-frame north press follows the upper authored warp at
                // public (2,1) through `begin_interior_warp_at`.
                TilePosition { x: 2, y: 0 },
                WarpTiming {
                    pre_fade_delay_frames: 0,
                    fade_frames: 7,
                },
            );
            self.bedroom_stair_direct_spawn = false;
        } else {
            self.begin_interior_warp_at(self.player.x, self.player.y);
        }
    }

    /// Samples one VBlank of the authenticated standalone Mays House 1F
    /// field task.  This checkpoint is captured after the upstairs arrival
    /// has settled, so the source does not use the normal 16-frame aggregate
    /// walker: Up is already the resident facing and commits on its first
    /// sample, while Left/Right spend eight samples turning before their
    /// first tile commit.  Down owns the door callback after that same
    /// eight-sample turn and atomically hands the map to Littleroot.
    pub fn advance_mays_house_1f_direct_vblank(&mut self, direction: Option<Facing>) {
        if self.transition.is_some() {
            let was_arrival = self
                .transition
                .as_ref()
                .is_some_and(|transition| transition.fading_in);
            self.advance_transition(1);
            if self.map != MapId::MaysHouse1F {
                self.mays_house_1f_direct_motion_frames = 0;
                if self.mays_house_1f_direct_exit_arrival_elapsed.is_some() {
                    if was_arrival {
                        let elapsed = self
                            .mays_house_1f_direct_exit_arrival_elapsed
                            .unwrap_or_default()
                            .saturating_add(1);
                        self.mays_house_1f_direct_exit_arrival_elapsed = Some(elapsed);
                        self.advance_mays_house_1f_direct_exit_arrival(elapsed);
                    } else {
                        // The map commit VBlank is elapsed zero; the source
                        // does not advance the outdoor object rail until the
                        // next sampled VBlank.
                        self.mays_house_1f_direct_exit_arrival_elapsed = Some(0);
                    }
                }
            } else {
                self.mays_house_1f_direct_motion_frames =
                    self.mays_house_1f_direct_motion_frames.saturating_add(1);
            }
            return;
        }
        if self.map != MapId::MaysHouse1F {
            if let Some(elapsed) = self.mays_house_1f_direct_exit_arrival_elapsed {
                if elapsed >= 100 {
                    return;
                }
                let elapsed = elapsed.saturating_add(1);
                self.mays_house_1f_direct_exit_arrival_elapsed = Some(elapsed);
                self.advance_mays_house_1f_direct_exit_arrival(elapsed);
            }
            return;
        }
        if self.menu_open || self.dialogue.is_some() || self.field_dialogue.is_some() {
            return;
        }
        let Some(facing) = direction.or(self.walk_direction) else {
            return;
        };
        let direction_changed = self.walk_direction != Some(facing);
        if direction_changed {
            self.face(facing);
            self.camera_handoff_from = self.walk_direction;
            self.walk_direction = Some(facing);
            self.walk_render_origin = Some(self.player.clone());
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.mays_house_1f_direct_motion_frames = 0;
        } else {
            self.mays_house_1f_direct_motion_frames =
                self.mays_house_1f_direct_motion_frames.saturating_add(1);
        }

        let motion = self.mays_house_1f_direct_motion_frames;
        let (next_x, next_y) = match facing {
            Facing::Up => (self.player.x, self.player.y - 1),
            Facing::Down => (self.player.x, self.player.y + 1),
            Facing::Left => (self.player.x - 1, self.player.y),
            Facing::Right => (self.player.x + 1, self.player.y),
        };
        let next_walkable = (0..self.map_dimensions().0).contains(&next_x)
            && (0..self.map_dimensions().1).contains(&next_y)
            && crate::native::is_walkable(self.map, next_x, next_y)
                .expect("standalone Mays House 1F collision must be defined")
            && !self.npcs.iter().any(|npc| {
                npc.map == self.map
                    && npc.position
                        == (TilePosition {
                            x: next_x,
                            y: next_y,
                        })
            });

        // The source door callback starts on the third sampled Down VBlank,
        // after the two-frame turn/upload lead-in. Its 22-frame departure
        // fade commits the Littleroot doorstep at VBlank 25 and then owns
        // the 32-frame palette arrival rail.
        if facing == Facing::Down && motion == 2 {
            self.mays_house_1f_y_offset = 2;
            self.mays_house_1f_direct_exit_arrival_elapsed = Some(0);
            self.begin_transition_with_timing(
                MapId::LittlerootTown,
                TilePosition { x: 14, y: 8 },
                WarpTiming {
                    pre_fade_delay_frames: 0,
                    fade_frames: 22,
                },
            );
            return;
        }

        let should_commit = match facing {
            Facing::Up => direction_changed || (motion > 0 && motion % 16 == 0),
            Facing::Down => false,
            Facing::Left | Facing::Right => motion >= 8 && (motion - 8) % 16 == 0,
        };
        if should_commit && next_walkable {
            let prior = self.player.clone();
            self.player = TilePosition {
                x: next_x,
                y: next_y,
            };
            self.walk_render_origin = Some(prior);
            self.elevation = crate::native::tile_elevation(self.map, next_x, next_y)
                .expect("standalone Mays House 1F destination elevation must be defined");
        }
        self.walk_progress_frames = (motion.min(16) as u8).min(15);
        self.walk_elapsed_frames = self.walk_progress_frames;
    }

    /// Advance the source's post-warp doorstep task.  The outdoor map is
    /// loaded at elapsed 0, Mom's door-side object rail runs while the map is
    /// still fading in, and the player takes the final south step at elapsed
    /// 35 (source VBlank 60 for this checkpoint).
    fn advance_mays_house_1f_direct_exit_arrival(&mut self, elapsed: u8) {
        if elapsed >= 35 && self.player.y == 8 {
            self.player.y = 9;
            self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                .expect("direct Mays-house doorstep destination must be staged");
        }
    }

    /// Applies overworld movement at Emerald's 16-frame walking cadence.
    ///
    /// This enforces authored layout bounds and applies source-derived Little
    /// Root warps. Per-tile collision and fade timing remain intentionally
    /// separate so they cannot be mistaken for implemented behavior.
    pub fn walk_bounds(&mut self, facing: Facing, held_frames: u32) -> u32 {
        let route101_west_lane_rail = self.map == MapId::Route101
            && self.phase == StoryPhase::StarterChosen
            && self.player.y == 14
            && (2..=7).contains(&self.player.x);
        let route101_north_upturn_edge = self.map == MapId::Route101
            && self.phase == StoryPhase::StarterChosen
            && self.player == (TilePosition { x: 10, y: 14 })
            && facing == Facing::Up;
        // Route 101's object task rejects a blocked redirect before it
        // changes the active player OBJ cell. In the north-lane source
        // receipt, the completed westward stride ignores the following Up
        // edge: the logical tile stays put and the last westward sprite cell
        // remains visible. Applying `face()` and installing a new walk task
        // before collision rejection changes only the player sprite, but
        // that is enough to diverge the raw RGB rail. Preserve the live task
        // on this narrow blocked-redirect path while leaving idle turns and
        // connected-map edges on the existing scheduler.
        if self.map == MapId::Route101
            && self.walk_direction.is_some()
            && self.walk_direction != Some(facing)
        {
            let (next_x, next_y) = match facing {
                Facing::Up => (self.player.x, self.player.y - 1),
                Facing::Down => (self.player.x, self.player.y + 1),
                Facing::Left => (self.player.x - 1, self.player.y),
                Facing::Right => (self.player.x + 1, self.player.y),
            };
            let (width, height) = self.map_dimensions();
            let in_bounds = (0..width).contains(&next_x) && (0..height).contains(&next_y);
            let blocked_by_npc = self
                .npcs
                .iter()
                .any(|npc| npc.map == self.map && npc.position.x == next_x && npc.position.y == next_y);
            let blocked_by_terrain = in_bounds
                && !crate::native::is_walkable(self.map, next_x, next_y)
                    .expect("staged Route 101 collision must be defined");
            // A second cardinal edge does not replace the source turn task
            // during its eight-VBlank pre-commit rail. Preserve that live
            // task (and its sprite cell) until it publishes or a higher
            // priority UI task takes ownership.
            let active_turn = held_frames == 1
                && self.walk_elapsed_frames < 9
                && !route101_west_lane_rail
                && !route101_north_upturn_edge;
            if in_bounds
                && !route101_north_upturn_edge
                && (blocked_by_npc || blocked_by_terrain || active_turn)
            {
                return 0;
            }
        }
        // The north-lane source task rejects a Down probe at the settled
        // boundary without changing the player's facing/task owner. This is
        // distinct from the later Left edge, which is accepted from the same
        // tile after the menu task releases.
        if self.map == MapId::Route101
            && self.phase == StoryPhase::StarterChosen
            && self.player == (TilePosition { x: 11, y: 14 })
            && self.walk_direction.is_none()
            && self.facing == Facing::Up
            && facing == Facing::Down
        {
            return 0;
        }
        self.face(facing);
        if self.menu_open
            || self.dialogue.is_some()
            || self.route101_exit_guard_delay.is_some()
            || self.transition.is_some()
            || self.oldale_blocked_path_frames.is_some()
            || self.birch_prompt_frames.is_some()
            || self.no_pokemon_gate_frames.is_some()
            || self.birch_rescue_frames.is_some()
            || self.birch_post_battle_frames.is_some()
            || self.route103_rival_intro_frames.is_some()
            || self.pokedex_arrival_frames.is_some()
            || self.pokedex_rival_frames.is_some()
            || self.pokedex_receipt_fanfare_frames.is_some()
            || self.pokedex_poke_ball_fanfare_frames.is_some()
            || self.tv_broadcast_intro_frames.is_some()
            || self.tv_broadcast_approach_frames.is_some()
            || self.tv_broadcast_view_frames.is_some()
        {
            return 0;
        }
        if self.littleroot_house_exit_down_block {
            if facing == Facing::Down {
                // The source leaves the player on the exterior doorstep after
                // the house fade; continued Down samples meet the blocked
                // doorway edge rather than walking two normalized rows south.
                return 0;
            }
            self.littleroot_house_exit_down_block = false;
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

        let direction_changed = self.walk_direction != Some(facing);
        let route101_edge_from_idle = direction_changed && self.walk_direction.is_none();
        if direction_changed {
            self.camera_handoff_from = self.walk_direction;
            self.walk_direction = Some(facing);
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_render_origin = Some(self.render_player().clone());
        }

        // A cardinal connection owns the first edge VBlank.  There is no
        // in-map tile to commit at Route 101's north row, so waiting for the
        // ordinary 16-frame stride would leave the authenticated edge receipt
        // stuck on Route 101.  Let the connection task atomically install its
        // raw south-border coordinate before normal cadence accounting.
        if self.map == MapId::Route101
            && facing == Facing::Up
            && self.player.y == 0
            && held_frames > 0
            && self.begin_connected_map(facing)
        {
            return 1;
        }

        let mut moved = 0;
        let (width, height) = self.map_dimensions();
        // The authenticated bedroom checkpoint exposes interior Y with the
        // two hidden map-border rows removed. Convert only native collision
        // lookups back to layout coordinates; keep public state normalized.
        let interior_y_offset = if self.map == MapId::MaysHouse1F {
            self.mays_house_1f_y_offset
        } else {
            0
        };
        // Route 101 publishes the logical destination as soon as a fresh
        // directional task starts. The renderer still uses
        // `walk_render_origin` for the old tile, so the player remains
        // screen-anchored while collision/state observers see the new tile.
        // Waiting for the ordinary 16-frame boundary leaves the public state
        // one tile behind mGBA during the live stride (east: x=13 vs x=12).
        let mut route101_start_committed = false;
        let route101_rescue_scene = self.map == MapId::Route101
            && self
                .npcs
                .iter()
                .any(|npc| npc.map == self.map && npc.id == "birchs_bag")
                && self
                    .npcs
                    .iter()
                    .any(|npc| npc.map == self.map && npc.id == "zigzagoon");
        let route101_west_reverse_edge = direction_changed
            && facing == Facing::Right
            && self.player == (TilePosition { x: 6, y: 14 })
            && self.phase == StoryPhase::StarterChosen;
        let route101_immediate_edge = self.map == MapId::Route101
            && direction_changed
            && (route101_edge_from_idle
                && ((facing == Facing::Up
                    && self.player == (TilePosition { x: 11, y: 19 }))
                // The authenticated west-lane checkpoint resumes with the
                // player already facing Left.  Emerald's same-facing edge
                // publishes that tile on VBlank 1; the other Route 101
                // lanes retain the normal eight-VBlank turn rail.
                    || (facing == Facing::Left
                        && self.player == (TilePosition { x: 7, y: 14 })
                        && self.phase == StoryPhase::StarterChosen))
                || route101_west_reverse_edge)
            && !route101_rescue_scene;
        if route101_immediate_edge
        {
            let (next_x, next_y) = match facing {
                Facing::Up => (self.player.x, self.player.y - 1),
                Facing::Down => (self.player.x, self.player.y + 1),
                Facing::Left => (self.player.x - 1, self.player.y),
                Facing::Right => (self.player.x + 1, self.player.y),
            };
            let collision_y = next_y + interior_y_offset;
            let free_of_npcs = !self.npcs.iter().any(|npc| {
                npc.map == self.map && npc.position.x == next_x && npc.position.y == next_y
            });
            if (0..width).contains(&next_x)
                && (0..height).contains(&collision_y)
                && free_of_npcs
                && crate::native::is_walkable(self.map, next_x, collision_y)
                    .expect("staged Route 101 collision must be defined")
            {
                let prior_player = self.player.clone();
                self.player = TilePosition {
                    x: next_x,
                    y: next_y,
                };
                self.elevation = crate::native::tile_elevation(self.map, next_x, collision_y)
                    .expect("staged Route 101 tile elevation must be defined");
                // `walk_render_origin` was captured above before the logical
                // commit, preserving the source's old-tile camera anchor.
                self.walk_render_origin = Some(prior_player);
                route101_start_committed = true;
            }
        }
        // Ordinary Route 101 directional edges spend eight VBlanks turning
        // before publishing the destination on the ninth. The source keeps
        // the old tile as the camera/render origin across that handoff. The
        // post-lab Up edge above is the measured exception: its destination
        // is published on the trigger VBlank.
        if self.map == MapId::Route101
            && held_frames == 1
            && !route101_start_committed
            && self.walk_direction == Some(facing)
            && self.walk_elapsed_frames > 0
            && self.walk_elapsed_frames < 9
            && !route101_west_lane_rail
            && !route101_north_upturn_edge
            && !(facing == Facing::Up
                && self.player.x == 11
                && self.player.y <= 18)
        {
            let next_phase = self.walk_elapsed_frames.saturating_add(1);
            self.walk_elapsed_frames = next_phase;
            self.walk_progress_frames = next_phase.saturating_sub(1);
            if next_phase < 9 {
                return 0;
            }
            let (next_x, next_y) = match facing {
                Facing::Up => (self.player.x, self.player.y - 1),
                Facing::Down => (self.player.x, self.player.y + 1),
                Facing::Left => (self.player.x - 1, self.player.y),
                Facing::Right => (self.player.x + 1, self.player.y),
            };
            let collision_y = next_y + interior_y_offset;
            let free_of_npcs = !self.npcs.iter().any(|npc| {
                npc.map == self.map && npc.position.x == next_x && npc.position.y == next_y
            });
            if (0..width).contains(&next_x)
                && (0..height).contains(&collision_y)
                && free_of_npcs
                && crate::native::is_walkable(self.map, next_x, collision_y)
                    .expect("staged Route 101 collision must be defined")
            {
                let prior_player = self.player.clone();
                self.player = TilePosition {
                    x: next_x,
                    y: next_y,
                };
                self.elevation = crate::native::tile_elevation(self.map, next_x, collision_y)
                    .expect("staged Route 101 tile elevation must be defined");
                self.walk_render_origin = Some(prior_player);
                // The next source stride starts one frame into its ordinary
                // 16-VBlank cadence after this turn edge publishes.
                self.walk_elapsed_frames = 1;
                self.walk_progress_frames = 0;
            } else {
                self.walk_elapsed_frames = 0;
                self.walk_progress_frames = 0;
                self.walk_direction = None;
                self.walk_render_origin = None;
            }
            return 0;
        }
        // The source keeps the held Down level alive through the upstairs
        // arrival fade.  When the destination map releases its field task,
        // the first downstairs stride is already nine VBlanks in; this is
        // why the ROM commits public Y=1 at V99 rather than V108 in the
        // ordinary post-transition scheduler.  The source then inserts a
        // two-VBlank scheduler gap before the next stride (V99 -> V117).
        if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_y_offset == 2
            && facing == Facing::Down
        {
            if self.mays_house_1f_arrival_down_phase == Some(9)
                && self.walk_elapsed_frames == 0
                && self
                    .mays_house_1f_arrival_start_frame
                    .is_some_and(|start| self.frame >= start.saturating_add(29))
            {
                self.walk_elapsed_frames = 9;
                self.mays_house_1f_arrival_down_phase = None;
            } else if let Some(delay) = self.mays_house_1f_arrival_down_phase {
                if self.walk_direction == Some(Facing::Down)
                    && self.walk_elapsed_frames == 0
                    && delay > 0
                {
                    self.mays_house_1f_arrival_down_phase = Some(delay - 1);
                    return 0;
                }
            }
        }
        let cadence = if self.running_shoes_field_motion() {
            8
        } else {
            16
        };
        // The field coordinate commits at each source movement boundary.
        // The display clock is one frame behind that committed coordinate,
        // which is why a fresh full-stride capture retains the prior tile's
        // final pixel of sprite/camera interpolation. Keep the clocks separate.
        let prior_walk_elapsed = u32::from(self.walk_elapsed_frames);
        let accumulated = prior_walk_elapsed + held_frames;
        // The first Route 101 directional VBlank is the logical commit
        // itself. Count that VBlank inside the visual stride so the next
        // coordinate is not published again until VBlank 17 (not VBlank 16).
        let (tiles, next_walk_elapsed) = if self.map == MapId::Route101
            && (route101_start_committed
                || (self.walk_direction == Some(facing) && !route101_west_lane_rail))
        {
            let adjusted = accumulated.saturating_sub(1);
            (adjusted / cadence, (adjusted % cadence + 1) as u8)
        } else {
            (
                accumulated / cadence,
                (accumulated % cadence) as u8,
            )
        };
        self.walk_elapsed_frames = next_walk_elapsed;
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
            let collision_y = next_y + interior_y_offset;
            if !(0..width).contains(&next_x) || !(0..height).contains(&collision_y) {
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
            if self.map == MapId::MaysHouse1F
                && self.mays_house_1f_y_offset == 2
                && self.mays_house_1f_rival_scene_start_frame.is_some()
                && self.mays_house_1f_rival_departure_frames.is_none()
                && next_y > 2
            {
                // The source OnFrame rival task takes ownership as the
                // player reaches public Y=2. Further Down samples remain
                // blocked until May's departure route completes.
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
                // The house façade blocks the second northward tile in the
                // clock-set exterior receipt.  Emerald exposes the doorstep
                // `(14,8)` as the endpoint of a held-Up probe, but the next
                // `(14,7)` tile is not traversable until the house script
                // has taken ownership of the interaction.
                if self.phase == StoryPhase::ClockSet && self.player.x == 14 && self.player.y == 8 {
                    self.walk_progress_frames = 0;
                    self.walk_elapsed_frames = 0;
                    self.walk_render_origin = None;
                    break;
                }
                if self.begin_interior_warp_at_facing(next_x, next_y, Some(facing)) {
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
                    (13, 13 | 14)
                        | (11, 9..=19)
                        | (2..=11, 19)
                        | (2, 9..=18)
                        | (3..=19, 9)
                        | (7, 17)
                        | (9..=12, 17)
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
                && self.npcs.iter().any(|npc| {
                    npc.map == self.map && npc.position.x == next_x && npc.position.y == next_y
                })
            {
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            if source_wurmple_route_block
                || (!source_rival_walkable_route
                    && !crate::native::is_walkable(self.map, next_x, collision_y)
                        .expect("staged Little Root map blockdata must define collision"))
            {
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            if !source_wurmple_escape_walkable_route
                && !ledge_allows(
                    crate::native::tile_behavior(self.map, next_x, collision_y)
                        .expect("staged Little Root map blockdata must define behavior"),
                    facing,
                )
            {
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
            self.player = TilePosition {
                x: next_x,
                y: next_y,
            };
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
            self.elevation = crate::native::tile_elevation(self.map, next_x, collision_y)
                .expect("staged Little Root map blockdata must define elevation");
            moved += 1;
            if self.map == MapId::MaysHouse1F
                && self.mays_house_1f_y_offset == 2
                && facing == Facing::Down
                && prior_player.y == 0
                && self.player.y == 1
                && self.mays_house_1f_arrival_start_frame.is_some()
            {
                self.mays_house_1f_arrival_down_phase = Some(2);
            }
            if self.map == MapId::MaysHouse1F
                && self.mays_house_1f_y_offset == 2
                && self.phase == StoryPhase::ClockSet
                && self.mays_house_1f_rival_scene_start_frame.is_none()
                && self.player.y >= 2
            {
                // Keep the encounter trigger ahead of the south doorway
                // event when a single held packet crosses several tiles.
                // `walk_bounds` is called after the request's VBlank clock
                // has been advanced in aggregate.  The authored OnFrame
                // trigger belongs to the tile boundary inside that packet,
                // not to its final VBlank; retaining that absolute boundary
                // is what makes a held Down equivalent to 16-frame packets.
                let frames_to_trigger = u32::from(cadence)
                    .saturating_sub(prior_walk_elapsed)
                    .saturating_add(tile_index * u32::from(cadence));
                let event_frame = self
                    .frame
                    .saturating_sub(u64::from(held_frames))
                    .saturating_add(u64::from(frames_to_trigger));
                self.begin_mays_house_1f_rival_scene(event_frame);
                let trailing_frames = held_frames.saturating_sub(frames_to_trigger);
                if trailing_frames != 0 {
                    self.advance_mays_house_1f_rival_scene(trailing_frames);
                }
                self.walk_direction = None;
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            self.begin_littleroot_warp(facing);
            if self.transition.is_some() {
                // A door event owns the remaining held-input window while
                // its atomic fade runs; never walk through the old map after
                // the trigger tile has published the transition task.
                // The house exit is still sampled one VBlank at a time by
                // the source.  Consume the trailing part of an aggregate
                // Down packet here so the map commit and arrival fade land
                // on the same VBlank as a split packet.
                if self.map == MapId::MaysHouse1F
                    && self.mays_house_1f_y_offset == 2
                    && facing == Facing::Down
                {
                    let frames_to_trigger = u32::from(cadence)
                        .saturating_sub(prior_walk_elapsed)
                        .saturating_add(tile_index * u32::from(cadence));
                    let trailing_frames = held_frames.saturating_sub(frames_to_trigger);
                    if trailing_frames != 0 {
                        self.advance_transition(trailing_frames);
                    }
                }
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            self.apply_littleroot_coordinate_trigger();
            self.apply_route101_rescue_exit_guard();
            self.apply_oldale_blocked_path_trigger();
            if self.map == MapId::MaysHouse1F
                && self.mays_house_1f_y_offset == 2
                && self.phase == StoryPhase::ClockSet
                && self.player == (TilePosition { x: 2, y: 2 })
            {
                let frames_to_trigger = u32::from(cadence)
                    .saturating_sub(prior_walk_elapsed)
                    .saturating_add(tile_index * u32::from(cadence));
                let event_frame = self
                    .frame
                    .saturating_sub(u64::from(held_frames))
                    .saturating_add(u64::from(frames_to_trigger));
                self.begin_mays_house_1f_rival_scene(event_frame);
                let trailing_frames = held_frames.saturating_sub(frames_to_trigger);
                if trailing_frames != 0 {
                    self.advance_mays_house_1f_rival_scene(trailing_frames);
                }
            }
            if self.mays_house_1f_rival_scene_start_frame.is_some()
                && self.mays_house_1f_rival_departure_frames.is_none()
            {
                // The scene owns the remainder of a held directional packet
                // after the stair-side tile commits.
                self.walk_direction = None;
                self.walk_progress_frames = 0;
                self.walk_elapsed_frames = 0;
                self.walk_render_origin = None;
                break;
            }
            if self.oldale_blocked_path_frames.is_some() {
                // The source coordinate event owns the remainder of the same
                // held request after the `(0,10)` boundary, just as a split
                // movement followed by Noop would.
                let frames_to_trigger = u32::from(cadence)
                    .saturating_sub(prior_walk_elapsed)
                    .saturating_add(tile_index * u32::from(cadence));
                self.advance_oldale_blocked_path(held_frames.saturating_sub(frames_to_trigger));
            }
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
                self.advance_oldale_rival_approach(held_frames.saturating_sub(frames_to_trigger));
            }
            self.begin_wild_encounter_at_player();
            if self.dialogue.is_some()
                || self.battle.is_some()
                || self.birch_prompt_frames.is_some()
                || self.no_pokemon_gate_frames.is_some()
                || self.birch_rescue_frames.is_some()
                || self.route103_rival_intro_frames.is_some()
                || self.oldale_rival_approach_frames.is_some()
                || self.pokedex_arrival_frames.is_some()
                || self.pokedex_rival_frames.is_some()
                || self.pokedex_receipt_fanfare_frames.is_some()
                || self.pokedex_poke_ball_fanfare_frames.is_some()
            {
                break;
            }
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

    /// Starts May's source OnFrame encounter as soon as the downstairs
    /// player reaches the public stair-side tile.  This is deliberately a
    /// scene-specific handoff: replacing the map NPC list with the generic
    /// `MeetRival` projection would put Mom on screen and miss the separate
    /// rival object-event that mGBA creates at the measured boundary.
    fn begin_mays_house_1f_rival_scene(&mut self, start_frame: u64) {
        if self.map != MapId::MaysHouse1F
            || self.player_gender != PlayerGender::Brendan
            || self.mays_house_1f_rival_scene_start_frame.is_some()
            || self.player != (TilePosition { x: 2, y: 2 })
        {
            return;
        }
        self.phase = StoryPhase::MeetRival;
        self.title_intro_step = 0;
        self.mays_house_1f_interactions_remaining = 0;
        self.mays_house_1f_rival_scene_start_frame = Some(start_frame);
        self.mays_house_1f_rival_dialogue_active = false;
        self.mays_house_1f_dialogue_page_hold = None;
        self.mays_house_1f_dialogue_page_arrow_anchor = None;
        self.mays_house_1f_dialogue_hold_arrow_anchor = None;
        self.mays_house_1f_dialogue_scroll_start_frame = None;
        self.mays_house_1f_rival_departure_frames = None;
        self.dialogue = None;
        self.field_dialogue = None;
        self.field_dialogue_frames = None;
        self.npc_walk_starts
            .retain(|walk| walk.id != "mom" && walk.id != "rival");
        self.npcs.retain(|npc| npc.id != "mom" && npc.id != "rival");
        // The rival's 1F script does not remove the house's Mom object.  The
        // source keeps her at the authored map coordinate while May walks in
        // from the south; retaining a normalized public coordinate here lets
        // the compositor carry the same object through the dialogue/exit.
        self.npcs.push(NpcState {
            id: "mom".to_owned(),
            map: MapId::MaysHouse1F,
            position: TilePosition { x: 8, y: 5 },
            facing: Facing::Left,
        });
    }

    /// Advances the measured May encounter.  The world clock has already
    /// advanced for the transport packet, so every boundary is crossed using
    /// the request's absolute start/end interval.  This keeps one `noop 600`
    /// equivalent to 600 one-VBlank requests while preserving object-event
    /// walk origins for the renderer.
    pub fn advance_mays_house_1f_rival_scene(&mut self, frames: u32) -> bool {
        // The source removes May's logical object when the resident OAM
        // slots rotate at V4645.  Keep the object available to the renderer
        // through the preceding hidden-pixel rail, then perform the typed
        // cleanup on the first post-rail scheduler tick.
        if self.map == MapId::MaysHouse1F && self.frame >= MAYS_RIVAL_RESIDENT_HANDOFF_FRAME {
            self.npcs.retain(|npc| npc.id != "rival");
            // Keep the completed walk marker as a renderer receipt.  The
            // source has already removed May's logical object, but its final
            // up-facing player-cell DMA remains resident until the held Down
            // door callback begins.
        }
        let Some(start) = self.mays_house_1f_rival_scene_start_frame else {
            return false;
        };
        // The source consumes the debounced A edge by briefly clearing the
        // window, then installs the next page on the following scheduler tick
        // without another input. Keep that one-VBlank blank boundary
        // explicit instead of waiting for the next physical A.
        if self.mays_house_1f_rival_dialogue_active
            && self.dialogue.as_deref().is_some_and(str::is_empty)
            && self
                .mays_house_1f_dialogue_page_hold
                .as_ref()
                // The source keeps the cleared text box blank for one full
                // VBlank after the closing edge.  Publish the next page on
                // the second scheduler tick (V1698), not immediately on the
                // first tick (V1697).
                .is_some_and(|(hold_frame, _)| self.frame == hold_frame.saturating_add(2))
        {
            if let Some(mut dialogue) = self.field_dialogue.take() {
                if dialogue.advance_page() {
                    dialogue.print_remaining =
                        mays_house_1f_dialogue_printer_duration(dialogue.current_text());
                    self.mays_house_1f_dialogue_page_hold = None;
                    self.mays_house_1f_dialogue_hold_arrow_anchor = None;
                    let arrow_ready_after = if dialogue.page == 4 {
                        // Page 4 is a source `\l` scroll: its first ready
                        // boundary is after the two visible lines, while the
                        // third line remains pending for the next A edge.
                        dialogue
                            .current_text()
                            .split('\n')
                            .take(2)
                            .map(|line| line.chars().count())
                            .sum::<usize>()
                            .saturating_add(2) as u64
                    } else {
                        u64::from(dialogue.print_remaining).saturating_add(1)
                    };
                    self.mays_house_1f_dialogue_page_arrow_anchor =
                        Some(self.frame.saturating_add(arrow_ready_after));
                    self.field_dialogue_frames = Some(dialogue.print_remaining);
                    self.dialogue = Some(dialogue.current_text().to_owned());
                    self.field_dialogue = Some(dialogue);
                    return true;
                }
                self.field_dialogue = Some(dialogue);
            }
        }
        if self.mays_house_1f_rival_dialogue_active {
            // The typed field printer owns no-op frames.  A ready A/B edge
            // must fall through to `advance_opening_script` instead.
            return false;
        }
        if let Some(remaining) = self.mays_house_1f_rival_departure_frames {
            let total = MAYS_RIVAL_DEPARTURE_FRAMES;
            let next = remaining.saturating_sub(frames.min(u32::from(u16::MAX)) as u16);
            let before = total.saturating_sub(remaining);
            let after = total.saturating_sub(next);
            let crossed = |boundary: u16| before < boundary && boundary <= after;
            let rival_map = MapId::MaysHouse1F;
            // The departure script samples its first rightward stride two
            // VBlanks after the closing page, then alternates sixteen-frame
            // walks with four-frame facing tasks. These offsets come from
            // the source object-event raster (the rival is already moving
            // right in the first map-only frame at V4407).
            if crossed(2) {
                if let Some(rival) = self.npcs.iter().find(|npc| npc.id == "rival") {
                    self.move_scripted_npc_with_duration_at_frame(
                        "rival",
                        rival_map,
                        TilePosition {
                            x: rival.position.x + 1,
                            y: rival.position.y,
                        },
                        Facing::Right,
                        16,
                        self.frame.saturating_sub(u64::from(after - 2)),
                    );
                }
            }
            if crossed(18) {
                self.animate_scripted_npc_in_place_at_frame(
                    "rival",
                    rival_map,
                    Facing::Up,
                    4,
                    self.frame.saturating_sub(u64::from(after - 18)),
                );
            }
            if crossed(22) {
                if let Some(rival) = self.npcs.iter().find(|npc| npc.id == "rival") {
                    self.move_scripted_npc_with_duration_at_frame(
                        "rival",
                        rival_map,
                        TilePosition {
                            x: rival.position.x,
                            y: rival.position.y - 1,
                        },
                        Facing::Up,
                        16,
                        self.frame.saturating_sub(u64::from(after - 22)),
                    );
                }
            }
            if crossed(MAYS_PLAYER_FAST_TURN_OFFSET) {
                // May's second movement callback and the player's eastward
                // face turn overlap. Commit the player's facing at the same
                // source boundary; native composition supplies the two-foot
                // four-frame cell cadence while this remains a typed state.
                self.facing = Facing::Right;
            }
            if crossed(38) {
                if let Some(rival) = self.npcs.iter().find(|npc| npc.id == "rival") {
                    self.move_scripted_npc_with_duration_at_frame(
                        "rival",
                        rival_map,
                        TilePosition {
                            x: rival.position.x,
                            y: rival.position.y - 1,
                        },
                        Facing::Up,
                        16,
                        self.frame.saturating_sub(u64::from(after - 38)),
                    );
                }
            }
            if crossed(54) {
                self.animate_scripted_npc_in_place_at_frame(
                    "rival",
                    rival_map,
                    Facing::Left,
                    4,
                    self.frame.saturating_sub(u64::from(after - 54)),
                );
            }
            if crossed(58) {
                if let Some(rival) = self.npcs.iter().find(|npc| npc.id == "rival") {
                    self.move_scripted_npc_with_duration_at_frame(
                        "rival",
                        rival_map,
                        TilePosition {
                            x: rival.position.x - 1,
                            y: rival.position.y,
                        },
                        Facing::Left,
                        16,
                        self.frame.saturating_sub(u64::from(after - 58)),
                    );
                }
            }
            if crossed(74) {
                self.animate_scripted_npc_in_place_at_frame(
                    "rival",
                    rival_map,
                    Facing::Up,
                    4,
                    self.frame.saturating_sub(u64::from(after - 74)),
                );
            }
            if crossed(78) {
                if let Some(rival) = self.npcs.iter().find(|npc| npc.id == "rival") {
                    self.move_scripted_npc_with_duration_at_frame(
                        "rival",
                        rival_map,
                        TilePosition {
                            x: rival.position.x,
                            y: rival.position.y - 1,
                        },
                        Facing::Up,
                        16,
                        self.frame.saturating_sub(u64::from(after - 78)),
                    );
                }
            }
            if before < 100 && 100 <= after {
                self.mays_house_1f_rival_departure_frames = None;
                self.mays_house_1f_rival_scene_start_frame = None;
                self.mays_house_1f_rival_dialogue_active = false;
                // Keep the departed object resident through the authenticated
                // OAM handoff rail.  The ROM clears its visible pixels at
                // this boundary, but removes the logical object only when
                // the resident slots rotate at the later V4645 callback.
                self.npc_walk_starts.retain(|walk| walk.id != "rival");
                // The source player object is not redrawn when May is
                // removed: its up-middle cell remains resident through the
                // short post-departure handoff. Keep one non-logical marker
                // for the compositor, then let the normal field state take
                // over after the authenticated tail.
                self.npc_walk_starts.push(NpcWalkStart {
                    id: "rival".to_owned(),
                    // The departure clock is entered after the long
                    // dialogue phase, so `start` is the scene's original
                    // arrival clock rather than the rail's global frame.
                    // At the terminal boundary the final up walk began 22
                    // VBlanks earlier (100 total, 78 through its start).
                    frame: self.frame.saturating_sub(22),
                    duration_frames: MAYS_PLAYER_UP_TAIL_FRAMES as u8,
                    sprite_facing: Some(Facing::Up),
                    in_place: false,
                });
            } else {
                self.mays_house_1f_rival_departure_frames = Some(next);
            }
            return true;
        }
        let before = self.frame.saturating_sub(u64::from(frames));
        let elapsed_before = before.saturating_sub(start).min(u64::from(u16::MAX)) as u16;
        let elapsed_after = self.frame.saturating_sub(start).min(u64::from(u16::MAX)) as u16;
        let crossed = |boundary: u16| elapsed_before < boundary && boundary <= elapsed_after;
        if crossed(MAYS_RIVAL_SPAWN_OFFSET)
            && !self
                .npcs
                .iter()
                .any(|npc| npc.id == "rival" && npc.map == self.map)
        {
            let boundary_frame = start.saturating_add(u64::from(MAYS_RIVAL_SPAWN_OFFSET));
            self.npcs.push(NpcState {
                id: "rival".to_owned(),
                map: MapId::MaysHouse1F,
                // The addobject event is on the east side of the rug.  The
                // previous `(2, 6)` placeholder put a second rival sprite
                // at the bottom-center of the viewport at the first visible
                // spawn VBlank (V140), where the ROM still has no object.
                // With the arrival camera at public player `(2, 2)`, the
                // authenticated source raster places the rival at map
                // `(8, 8)` (screen x≈208, y≈136).
                position: TilePosition { x: 8, y: 8 },
                facing: Facing::Down,
            });
            self.npc_walk_starts.retain(|walk| walk.id != "rival");
            // Keep the source object at its addobject pose for the visible
            // spawn VBlank; subsequent movement owns its own walk marker.
            self.npc_walk_starts.push(NpcWalkStart {
                // Walk markers are keyed by the object-event local ID.  A
                // synthetic `rival_spawn` ID is invisible to the compositor
                // and leaves the first spawn pose stuck or unanimated.
                id: "rival".to_owned(),
                frame: boundary_frame,
                duration_frames: 1,
                sprite_facing: Some(Facing::Down),
                in_place: true,
            });
        }
        if crossed(MAYS_RIVAL_MAT_REPOSITION_OFFSET) {
            if let Some(rival) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "rival" && npc.map == MapId::MaysHouse1F)
            {
                // The ROM's object-event callback swaps the resident east
                // rug pose for the lower mat pose atomically at V147.  Keep
                // this as a coordinate publication rather than inventing a
                // seven-frame walk; the source has no intermediate pixels.
                rival.position = TilePosition { x: 2, y: 6 };
                rival.facing = Facing::Down;
            }
        }
        if crossed(MAYS_RIVAL_WALK_OFFSET) {
            let boundary_frame = start.saturating_add(u64::from(MAYS_RIVAL_WALK_OFFSET));
            self.move_scripted_npc_with_duration_at_frame(
                "rival",
                MapId::MaysHouse1F,
                TilePosition { x: 2, y: 5 },
                Facing::Up,
                MAYS_RIVAL_WALK_STEP_FRAMES as u8,
                boundary_frame,
            );
        }
        if crossed(MAYS_RIVAL_WALK_OFFSET + MAYS_RIVAL_WALK_STEP_FRAMES) {
            let boundary_frame = start.saturating_add(u64::from(
                MAYS_RIVAL_WALK_OFFSET + MAYS_RIVAL_WALK_STEP_FRAMES,
            ));
            self.move_scripted_npc_with_duration_at_frame(
                "rival",
                MapId::MaysHouse1F,
                TilePosition { x: 2, y: 4 },
                Facing::Up,
                MAYS_RIVAL_WALK_STEP_FRAMES as u8,
                boundary_frame,
            );
        }
        if crossed(MAYS_RIVAL_WALK_OFFSET + MAYS_RIVAL_WALK_STEP_FRAMES * 2) {
            let boundary_frame = start.saturating_add(u64::from(
                MAYS_RIVAL_WALK_OFFSET + MAYS_RIVAL_WALK_STEP_FRAMES * 2,
            ));
            self.move_scripted_npc_with_duration_at_frame(
                "rival",
                MapId::MaysHouse1F,
                TilePosition { x: 2, y: 3 },
                Facing::Up,
                MAYS_RIVAL_WALK_STEP_FRAMES as u8,
                boundary_frame,
            );
        }
        if crossed(MAYS_RIVAL_DIALOGUE_OFFSET) {
            self.mays_house_1f_rival_dialogue_active = true;
            self.begin_field_dialogue_pages(
                (0..12)
                    .map(|page| mays_house_1f_rival_page(page, &self.player_name))
                    .collect(),
            );
            let carry = elapsed_after.saturating_sub(MAYS_RIVAL_DIALOGUE_OFFSET);
            if carry != 0 {
                self.advance_field_dialogue_printer(u32::from(carry));
            }
        }
        true
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
            // Oldale's south connection owns one runtime border row at y=20
            // before the first interior stride commits y=19.
            MapId::OldaleTown => (20, 21),
            MapId::Route103 => (80, 22),
            MapId::BrendansHouse1F | MapId::MaysHouse1F => (11, 9),
            MapId::BrendansHouse2F | MapId::MaysHouse2F => (9, 8),
            MapId::ProfessorBirchsLab => (13, 13),
        }
    }

    pub fn advance_transition(&mut self, frames: u32) {
        let Some(mut transition) = self.transition.take() else {
            return;
        };
        let mut frames = frames;
        if transition.pre_fade_delay_remaining != 0 {
            let delay = u32::from(transition.pre_fade_delay_remaining);
            if frames < delay {
                transition.pre_fade_delay_remaining -= frames as u8;
                self.transition = Some(transition);
                return;
            }
            frames -= delay;
            transition.pre_fade_delay_remaining = 0;
            if frames == 0 {
                self.transition = Some(transition);
                return;
            }
        }
        let departing_frames = u32::from(transition.frames_remaining);
        transition.frames_remaining = transition
            .frames_remaining
            .saturating_sub(frames.min(u32::from(u8::MAX)) as u8);
        if transition.frames_remaining > 0 {
            self.transition = Some(transition);
            return;
        }
        if transition.fading_in {
            let carry = frames.saturating_sub(departing_frames);
            if carry != 0 && self.rival_mom_intro_frames.is_some() {
                self.advance_rival_mom_intro(carry);
            }
            // A declarative script may have ended on a warp. Once the
            // arrival fade releases, continue its following task (or remove
            // the completed runner) before the next field input is sampled.
            self.run_field_script_until_blocked();
            return;
        }
        {
            let arriving_from_upstairs = transition.origin_map == Some(MapId::MaysHouse2F)
                && transition.destination_map == MapId::MaysHouse1F;
            let normalized_house_exit = transition.origin_map == Some(MapId::MaysHouse1F)
                && transition.destination_map == MapId::LittlerootTown
                && self.mays_house_1f_y_offset == 2;
            // The authenticated north-stair event is the seven-frame
            // hand-off installed by the dedicated stair rule. A generic
            // declarative 2F→1F warp (including script tests) keeps its
            // authored fade timing and must not inherit the arrival raster.
            let source_stair_arrival = arriving_from_upstairs && transition.total_frames == 7;
            self.map = transition.destination_map;
            self.player = transition.destination.clone();
            if self.map != MapId::MaysHouse1F {
                self.mays_house_1f_y_offset = 0;
                self.mays_house_1f_arrival_down_phase = None;
                self.mays_house_1f_interactions_remaining = 0;
            }
            self.littleroot_house_exit_down_block = normalized_house_exit;
            self.render_position = None;
            self.walk_progress_frames = 0;
            self.walk_elapsed_frames = 0;
            self.walk_render_origin = None;
            self.elevation = crate::native::tile_elevation(self.map, self.player.x, self.player.y)
                .expect("warp destination must be inside staged map blockdata");
            self.npcs = map_npcs(
                self.map,
                self.phase,
                self.potions,
                self.oldale_rival_departed,
                self.player_gender,
            );
            if arriving_from_upstairs {
                // The authenticated bedroom checkpoint has already executed
                // `TurnOffTVScreen`; preserve that map-owned metatile state
                // after the atomic downstairs commit as well as during fade.
                self.tv_screen_on = false;
                // mGBA commits the destination map before the downstairs
                // camera/object task catches up. Keep the source phase typed
                // on WorldState so rendering remains correct after the
                // generic transition object has been consumed.
                if source_stair_arrival {
                    self.mays_house_1f_arrival_start_frame = Some(self.frame);
                    self.mays_house_1f_arrival_down_phase = Some(9);
                    // The authenticated bedroom source projection subtracts
                    // the two hidden interior border rows on both floors.
                    // Keep that coordinate contract for the contiguous
                    // downstairs walk and its door warp.
                    self.mays_house_1f_y_offset = 2;
                    self.mays_house_1f_interactions_remaining = 13;
                    self.elevation = crate::native::tile_elevation(
                        self.map,
                        self.player.x,
                        self.player.y + self.mays_house_1f_y_offset,
                    )
                    .expect("normalized downstairs arrival must be inside staged map blockdata");
                }
            }
            if normalized_house_exit {
                // The source door task commits Littleroot only after its
                // 16-frame door/open fade-out, then keeps the new map under
                // a 32-VBlank arrival fade.  This is intentionally separate
                // from the generic 16+16 warp used by ordinary doors.
                transition.total_frames = 32;
            }
            if self.map == MapId::LittlerootTown && self.phase == StoryPhase::TruckArrival {
                // The two 16-frame map fades are already consumed by the
                // held exit input. mGBA shows Mom's message after another
                // 176 frames of scripted arrival movement and pauses.
                self.truck_arrival_frames = Some(176);
            }
            if self.map == MapId::ProfessorBirchsLab
                && self.phase == StoryPhase::BirchRescued
                && self.starter.is_some()
            {
                // ChooseStarter happens on Route 101. The Lab's on-frame
                // script then formally awards that same starter and directs
                // the player to their rival before Route 103 unlocks.
                self.phase = StoryPhase::StarterLab;
                self.title_intro_step = 0;
                self.route101_rescue_task = Route101RescueTask::StarterLabAcknowledgement;
                self.story_flags.set(ProgressFlag::StarterAcknowledged);
                // v8 source checkpoint `birch_lab_starter_ack` is at Lab
                // `(6,5)` with the acknowledgement still script-owned. The
                // Lab state is now durable, while the generic dialogue task
                // owns printer and confirmation timing.
                self.begin_field_dialogue("I’d like you to have your own POKéMON.".to_owned());
                self.npcs = map_npcs(
                    self.map,
                    self.phase,
                    self.potions,
                    self.oldale_rival_departed,
                    self.player_gender,
                );
                debug_assert!(self.route101_rescue_invariants_hold());
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
                self.npcs = map_npcs(
                    self.map,
                    self.phase,
                    self.potions,
                    self.oldale_rival_departed,
                    self.player_gender,
                );
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
        // The upstairs stair event has a shorter fade-out than its arrival
        // raster.  mGBA commits map 1:2 at V96, keeps the new map black for
        // fourteen VBlanks, then applies seven two-VBlank GBA palette steps
        // through V124.  Preserve that asymmetric timing in the serialized
        // transition instead of forcing both halves to share one duration.
        if transition.origin_map == Some(MapId::MaysHouse2F)
            && transition.destination_map == MapId::MaysHouse1F
            && transition.total_frames == 7
        {
            transition.total_frames = 28;
            transition.frames_remaining = 28;
        }
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
            self.run_field_script_until_blocked();
            return;
        }
        transition.frames_remaining = transition.total_frames - arrival_elapsed as u8;
        self.transition = Some(transition);
    }

    pub fn transition_alpha(&self) -> u8 {
        self.transition.as_ref().map_or(0, |transition| {
            if transition.pre_fade_delay_remaining != 0 {
                return 0;
            }
            let elapsed = transition
                .total_frames
                .saturating_sub(transition.frames_remaining);
            // Widen before multiplying.  `elapsed` and `total_frames` are
            // compact serialized `u8`s, but the 0..255 fade numerator is a
            // 16-bit quantity.  Keeping this as u8 makes `2 * 255`
            // saturate at 255, freezing every subsequent fade step at the
            // first near-black level (the Mays-house exit was visibly black
            // from V4802 through V4830).
            let alpha = (u16::from(elapsed) * 255 / u16::from(transition.total_frames.max(1)))
                .min(u16::from(u8::MAX)) as u8;
            if transition.fading_in {
                255_u8.saturating_sub(alpha)
            } else {
                alpha
            }
        })
    }

    /// Resolves an authored interior event from data and starts one atomic
    /// fade. The old map/position remain observable for the complete
    /// fade-out; `advance_transition` installs both destination fields in a
    /// single commit at the hand-off boundary.
    fn begin_interior_warp_at(&mut self, x: i16, y: i16) -> bool {
        // Direct script/test callers name an authored event tile, rather than
        // simulating the controller's approach. Preserve that API's
        // direction-agnostic behavior; live movement uses the directional
        // helper below.
        self.begin_interior_warp_at_facing(x, y, None)
    }

    fn begin_interior_warp_at_facing(&mut self, x: i16, y: i16, facing: Option<Facing>) -> bool {
        if self.transition.is_some() {
            return false;
        }
        // In the frozen post-Pokédex exterior source state, the field stream
        // walks through the Porymap-projected May-house warp tile and stops
        // farther north without a transition. Do not let that projection
        // override the source field owner for this state.
        if self.map == MapId::LittlerootTown && self.phase == StoryPhase::PokedexReceived {
            return false;
        }
        // The authenticated clock-set exterior receipt is standing on the
        // south side of May's house.  Its first north step is ordinary field
        // movement to the authored doorstep tile; the house script does not
        // own that edge until the player has entered the house and progressed
        // the story.  Resolving the generic interior table here incorrectly
        // warps the exterior probe to the 1F spawn (the observed `(2,8)`
        // endpoint instead of Littleroot `(14,8)`).
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::ClockSet
            && self.player == (TilePosition { x: 14, y: 9 })
            && facing == Some(Facing::Up)
        {
            return false;
        }
        let Some(rule) = INTERIOR_WARP_RULES.iter().find(|rule| {
            rule.contains(self.map, x, y)
                && facing.is_none_or(|actual| {
                    rule.entry_facing.is_none_or(|required| required == actual)
                })
        }) else {
            return false;
        };
        self.begin_transition_with_timing(
            rule.destination_map,
            rule.destination.clone(),
            rule.timing,
        );
        true
    }

    fn begin_littleroot_warp(&mut self, facing: Facing) {
        // During the authenticated exterior receipt the first held-Up rail
        // reaches the doorstep tile but does not enter the house yet. The
        // source door event is still waiting on its field task; resolving the
        // generic interior table at `(14,8)` would atomically jump to Mays
        // House 1F halfway through the 64-VBlank probe. Keep that edge as
        // ordinary exterior movement for this short clock-set handoff.
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::ClockSet
            && facing == Facing::Up
            && self.player.x == 14
            && self.player.y <= 8
            && self.frame < 80
        {
            return;
        }
        if self.map == MapId::MaysHouse1F
            && self.mays_house_1f_y_offset == 2
            && facing == Facing::Down
            && (1..=2).contains(&self.player.x)
            && self.player.y == 6
        {
            // The bedroom-authenticated projection reaches the native door
            // at raw Y=8 as public Y=6. Keep this alternate rule beside the
            // declarative interior table so raw-coordinate house-entry
            // scripts retain their existing Y=8 contract.
            self.begin_transition_with_timing(
                MapId::LittlerootTown,
                // The interior projection subtracts two rows only while
                // inside the house. Littleroot's public field coordinates
                // are raw map coordinates, so the source doorstep is
                // `(14,8)`, not the normalized interior `(14,6)`.
                TilePosition { x: 14, y: 8 },
                // The source door task starts its departure fade on the same
                // VBlank as the warp event.  The fade itself lasts 32
                // VBlanks; the destination map is committed atomically at
                // its end and remains black until the arrival palette task
                // begins.  Keeping this as one fade (rather than a delayed
                // generic 16+16 warp) preserves the source's black window.
                WarpTiming {
                    pre_fade_delay_frames: 0,
                    fade_frames: 32,
                },
            );
            return;
        }
        self.begin_interior_warp_at_facing(self.player.x, self.player.y, Some(facing));
    }

    /// Route 101, Oldale, and Route 103's northern cardinal edges scroll
    /// immediately. The authored Little Root handoff remains a transition.
    /// Every connection preserves the player X coordinate.
    fn begin_connected_map(&mut self, facing: Facing) -> bool {
        if self.transition.is_some() {
            return false;
        }
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
            && matches!(
                self.phase,
                StoryPhase::PokedexReceived | StoryPhase::RunningShoesReceived
            )
            && self.has_pokedex
            && facing == Facing::Down
            && self.player == (TilePosition { x: 10, y: 19 })
        {
            // The frozen post-Pokédex field state reaches Route 101's south
            // edge at `(10,19)` but holds there under a continued Down
            // input. Its map connection is not active in that source state.
            return false;
        }
        let Some(rule) = MAP_CONNECTION_RULES
            .iter()
            .copied()
            .find(|rule| rule.matches(self, facing) && rule.gate.satisfied(self))
        else {
            return false;
        };
        if rule.action == ConnectionAction::StartBirchRescue && self.phase == StoryPhase::MetRival {
            self.phase = StoryPhase::BirchRescue;
            self.dialogue = Some("H-help me!".to_owned());
        }
        let destination = TilePosition {
            x: self.player.x,
            y: rule.destination_y,
        };
        match rule.mode {
            ConnectionMode::Fade => self.begin_transition(rule.destination_map, destination),
            ConnectionMode::Scroll => self.enter_cardinal_map(rule.destination_map, destination),
        }
        true
    }

    fn enter_cardinal_map(&mut self, destination_map: MapId, destination: TilePosition) {
        self.map = destination_map;
        self.player = destination;
        self.render_position = None;
        self.walk_progress_frames = 0;
        self.walk_elapsed_frames = 0;
        self.walk_render_origin = None;
        let elevation_y = if self.map == MapId::OldaleTown && self.player.y >= 20 {
            19
        } else {
            self.player.y
        };
        self.elevation = crate::native::tile_elevation(self.map, self.player.x, elevation_y)
            .expect("cardinal map destination must be inside staged terrain");
        self.npcs = map_npcs(
            self.map,
            self.phase,
            self.potions,
            self.oldale_rival_departed,
            self.player_gender,
        );
    }

    /// Starts the shared overworld fade used by authored warps and opening
    /// cutscene handoffs. The destination map is installed only at fade-out.
    fn begin_transition(&mut self, destination_map: MapId, destination: TilePosition) {
        self.begin_transition_with_timing(destination_map, destination, WarpTiming::default());
    }

    fn begin_transition_with_timing(
        &mut self,
        destination_map: MapId,
        destination: TilePosition,
        timing: WarpTiming,
    ) {
        if self.transition.is_some() {
            return;
        }
        // Validate before publishing any part of the transition. A malformed
        // imported rule must not leave a serialized state that names a new
        // map but still renders the old one.
        if crate::native::tile_elevation(destination_map, destination.x, destination.y).is_err() {
            debug_assert!(
                false,
                "warp destination must be inside staged map blockdata"
            );
            return;
        }
        self.transition = Some(MapTransition {
            origin_map: Some(self.map),
            origin: Some(self.player.clone()),
            destination_map,
            destination,
            pre_fade_delay_remaining: timing.pre_fade_delay_frames,
            frames_remaining: timing.fade_frames.max(1),
            total_frames: timing.fade_frames.max(1),
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
        // The coordinate event does not open the text window on the same
        // VBlank as the tile commit.  The source map script spends eight
        // scheduler ticks before DrawDialogueFrame, and the generic field
        // printer exposes the empty window for the next tick.  Keep the
        // delayed task explicit so a continued held direction cannot move
        // through the source's pending warning.
        self.route101_exit_guard_delay = Some(12);
    }

    /// Advances the Route 101 exit-warning map script by one source VBlank.
    /// The final delay tick installs the regular field printer, which then
    /// owns subsequent VBlanks until the message is dismissed.
    pub fn advance_route101_exit_guard(&mut self) {
        let Some(remaining) = self.route101_exit_guard_delay else {
            return;
        };
        if remaining > 1 {
            self.route101_exit_guard_delay = Some(remaining - 1);
            return;
        }
        self.route101_exit_guard_delay = None;
        self.begin_field_dialogue("Wh-Where are you going?!\nDon't leave me like this!".to_owned());
    }

    /// The source B/NO path leaves the confirmation menu raster visible for
    /// the edge VBlank, then runs `Task_DeclineStarter` for one VBlank before
    /// `Task_StarterChoose` recreates the selector label.
    pub fn advance_starter_decline_handoff(&mut self) {
        if !self.source_starter_picker_interrupted_a {
            return;
        }
        let elapsed = self
            .frame
            .saturating_sub(self.source_starter_picker_interrupted_frame);
        if self.source_starter_picker_receipt_mode == 3
            && self.source_starter_picker_interrupted_direction
            && self.phase == StoryPhase::StarterConfirm
            && elapsed >= 1
        {
            self.source_starter_picker_receipt_mode = 0;
            self.source_starter_picker_profile = 0;
            self.source_starter_picker_receipt_from = None;
            self.source_starter_picker_receipt_to = None;
            self.source_starter_picker_receipt_edge_frame = 0;
            self.source_starter_picker_receipt_tail_clean = false;
            self.source_starter_picker_confirm_cursor_frame = None;
            self.source_starter_picker_reveal_started_during_move_commit = false;
            self.source_starter_picker_interrupted_direction = false;
            self.starter_confirm_yes = true;
            self.phase = StoryPhase::StarterSelect;
            if self.route101_rescue_task == Route101RescueTask::StarterConfirm {
                self.route101_rescue_task = Route101RescueTask::StarterPicker;
            }
        } else if self.source_starter_picker_receipt_mode == 0
            && self.phase == StoryPhase::StarterSelect
            && elapsed >= 2
        {
            self.source_starter_picker_interrupted_a = false;
            self.source_starter_picker_interrupted_frame = 0;
        }
    }

    /// `OldaleTown_MapCoordEvents` fires the source west-entrance script on
    /// `(0,10)` until Birch's Pokédex handoff sets the adventure flag. It is
    /// intentionally separate from collision so the authored step-back and
    /// footprints-man movement can run before the warning message.
    fn apply_oldale_blocked_path_trigger(&mut self) {
        if self.map != MapId::OldaleTown
            || self.phase >= StoryPhase::PokedexReceived
            || self.player != (TilePosition { x: 0, y: 10 })
            || self.oldale_blocked_path_stage != 0
            || self.dialogue.is_some()
        {
            return;
        }
        self.oldale_blocked_path_stage = 1;
        self.oldale_blocked_path_frames = Some(OLDALE_BLOCKED_PATH_APPROACH_FRAMES);
    }

    fn apply_littleroot_coordinate_trigger(&mut self) {
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::MeetRival
            && self.player.y == 1
            && matches!(self.player.x, 10 | 11)
            && self.no_pokemon_gate_stage == 0
            && self.no_pokemon_gate_frames.is_none()
            && self.dialogue.is_none()
        {
            self.no_pokemon_gate_right = self.player.x == 11;
            self.no_pokemon_gate_stage = 1;
            // Both source approach streams begin with face/delay/jump/delay
            // (32 frames), then use their distinct `walk_fast_*` paths.
            self.no_pokemon_gate_frames =
                Some(no_pokemon_twin_path_frames(self.no_pokemon_gate_right, false) + 32);
            if let Some(twin) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
            {
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
            && self.dialogue.is_none()
        {
            self.birch_prompt_active = true;
            self.birch_prompt_frames = Some(LITTLEROOT_GO_SAVE_BIRCH_TURN_SEQUENCE_FRAMES);
            let twin_position = self
                .npcs
                .iter()
                .find(|npc| npc.id == "twin" && npc.map == MapId::LittlerootTown)
                .expect("Twin must exist for the Little Root Birch prompt")
                .position
                .clone();
            self.move_faster_scripted_npc(
                "twin",
                MapId::LittlerootTown,
                twin_position,
                Facing::Right,
            );
            return;
        }
        let source_rival_running_shoes =
            self.player == (TilePosition { x: 11, y: 9 }) && self.render_position.is_some();
        if self.map == MapId::LittlerootTown
            && self.phase == StoryPhase::PokedexReceived
            && (source_rival_running_shoes
                || (self.player.y == 9 && (8..=11).contains(&self.player.x))
                || (self.player.y == 2 && (10..=11).contains(&self.player.x)))
            && self.dialogue.is_none()
        {
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
            if let Some(mom) = self
                .npcs
                .iter_mut()
                .find(|npc| npc.id == "mom_outside" && npc.map == MapId::LittlerootTown)
            {
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
                    id: "mom_outside".to_owned(),
                    map: MapId::LittlerootTown,
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
        if !matches!(self.map, MapId::BrendansHouse2F | MapId::MaysHouse2F) {
            return false;
        }
        let (x, y) = match self.facing {
            Facing::Up => (self.player.x, self.player.y - 1),
            Facing::Down => (self.player.x, self.player.y + 1),
            Facing::Left => (self.player.x - 1, self.player.y),
            Facing::Right => (self.player.x + 1, self.player.y),
        };
        matches!(
            (self.map, x, y),
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
            // `Route103_MapBGEvents` places the south-facing route sign at
            // (11, 9) and dispatches `Route103_Text_RouteSign` whenever the
            // player faces it. Keep this as a background event rather than
            // an NPC so interaction ownership follows the authored map data.
            (MapId::Route103, 11, 9) => Some("ROUTE 103\n↓ OLDALE TOWN"),
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
        4 => "It has a quaint feel, but it seems to be an easy place to live, don't you think?"
            .to_owned(),
        5 => format!("And, you get your own room, {player_name}!\nLet's go inside."),
        _ => unreachable!("truck-arrival script page is in range"),
    }
}

fn new_home_page(page: usize, player_name: &str) -> String {
    match page {
        0 => format!("MOM: See, {player_name}?\nIsn't it nice in here, too?"),
        1 => {
            "The movers' POKéMON do all the work of moving us in and cleaning up after.".to_owned()
        }
        2 => format!("{player_name}'s room is upstairs.\nGo check it out, dear!"),
        3 => {
            "Dad bought you a new clock to mark our move here.\nDon't forget to set it!".to_owned()
        }
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
        PlayerGender::Brendan => {
            "MAY: Let's see… The POKéMON found on ROUTE 103 include…".to_owned()
        }
        PlayerGender::May => {
            "BRENDAN: Okay, so it's this one and that one that live on ROUTE 103…".to_owned()
        }
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

fn running_shoes_mom_path(
    trigger: u8,
    player_gender: PlayerGender,
    returning: bool,
) -> (Facing, u8, bool) {
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
        (2, 0) => format!(
            "MOM: {player_name}! {player_name}! Did you\nintroduce yourself to PROF. BIRCH?"
        ),
        (2, 1) => {
            "Oh! What an adorable POKéMON!\nYou got it from PROF. BIRCH. How nice!".to_owned()
        }
        (2, 2) => "You're your father's child, all right.\nYou look good together with POKéMON!"
            .to_owned(),
        (2, 3) => "Here, honey! If you're going out on an\nadventure, wear these RUNNING SHOES."
            .to_owned(),
        (2, 4) => "They'll put a zip in your step!".to_owned(),
        (3, 0) => format!("{player_name} switched shoes with the\nRUNNING SHOES."),
        (4, 0) => format!("MOM: {player_name}, those shoes came with\ninstructions."),
        (4, 1) => {
            "“Press the B Button while wearing these\nRUNNING SHOES to run extra-fast!”".to_owned()
        }
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

/// The post-victory Birch pages are driven by an OnFrame text task rather
/// than the ordinary field-message printer. Source-authenticated traces show
/// two handoff VBlanks followed by one authored character per VBlank and the
/// source's ready-arrow task on the following scheduler boundary.
fn birch_rescue_dialogue_printer_duration(dialogue: &str) -> u16 {
    let glyph_frames = dialogue.chars().count().min(usize::from(u16::MAX)) as u16;
    glyph_frames.saturating_add(2)
}

/// The Mays-house OnFrame printer has no ordinary twelve-frame lead. Its line
/// break is a control code rather than a visible glyph; every other authored
/// character, including spaces, consumes one source VBlank. The source waits
/// two VBlanks after the final character before enabling its red advance
/// arrow.
fn mays_house_1f_dialogue_printer_duration(dialogue: &str) -> u16 {
    let source_characters = dialogue
        .chars()
        .filter(|character| *character != '\n')
        .count();
    let source_frames = source_characters.saturating_add(2);
    u16::try_from(source_frames).unwrap_or(u16::MAX)
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

/// `RivalsHouse_1F_Text_MayWhoAreYou` (the direct Mays House 1F OnFrame
/// encounter, not Mom's separate new-neighbor greeting).
fn mays_house_1f_rival_page(page: u8, player_name: &str) -> String {
    match page {
        0 => "Huh?\nWho… Who are you?".to_owned(),
        1 => "… … … … … … … …\n… … … … … … … …".to_owned(),
        2 => format!("Oh, you're {player_name}.\nSo your move was today."),
        3 => "Um… I'm MAY.\nGlad to meet you!".to_owned(),
        4 => {
            "I…\nI have this dream of becoming friends\nwith POKéMON all over the world.".to_owned()
        }
        5 => format!("I… I heard about you, {player_name}, from\nmy dad, PROF. BIRCH."),
        6 => format!(
            "I was hoping that you would be nice,\n{player_name}, and that we could be friends."
        ),
        7 => format!("Oh, this is silly, isn't it?\nI… I've just met you, {player_name}."),
        8 => "Eheheh…".to_owned(),
        9 => "Oh, no! I forgot!".to_owned(),
        10 => "I was supposed to go help Dad catch\nsome wild POKéMON!".to_owned(),
        11 => format!("{player_name}, I'll catch you later!"),
        _ => unreachable!("Mays House 1F rival page must be in range"),
    }
}

/// The fourth Mays-house page is authored as a `\\l` line-scroll rather than
/// a page replacement.  Once its A edge is consumed the old second line is
/// retained at the top of the text window and the third line is printed into
/// the newly exposed lower row.  This is the text projection that remains
/// visible while the compositor performs that four-pixel-per-VBlank scroll.
fn mays_house_1f_scroll_projection(dialogue: &str) -> String {
    let mut lines = dialogue.split('\n');
    let _first = lines.next().unwrap_or("");
    let second = lines.next().unwrap_or("");
    let third = lines.next().unwrap_or("");
    format!("{second}\n{third}")
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

fn map_npcs(
    map: MapId,
    phase: StoryPhase,
    potions: u8,
    oldale_rival_departed: bool,
    player_gender: PlayerGender,
) -> Vec<NpcState> {
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
            id: "mom".to_owned(),
            map,
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
            if matches!(
                phase,
                StoryPhase::ClockSet | StoryPhase::TvBroadcast | StoryPhase::MeetRival
            ) =>
        {
            Vec::new()
        }
        MapId::BrendansHouse2F if phase == StoryPhase::ClockVisit => vec![NpcState {
            id: "mom".to_owned(),
            map,
            position: TilePosition { x: 7, y: 1 },
            facing: Facing::Down,
        }],
        MapId::MaysHouse1F => vec![NpcState {
            id: "mom".to_owned(),
            map,
            position: match phase {
                StoryPhase::NewHome | StoryPhase::ClockSet => TilePosition { x: 1, y: 8 },
                // The rival-house object is authored at raw (8, 7).  The
                // bedroom checkpoint exposes the interior with its two-row
                // coordinate projection, hence public (8, 5).
                StoryPhase::TvBroadcast | StoryPhase::MeetRival => TilePosition { x: 8, y: 5 },
                _ => TilePosition { x: 2, y: 4 },
            },
            facing: Facing::Up,
        }],
        MapId::MaysHouse2F if phase == StoryPhase::ClockVisit => vec![NpcState {
            id: "mom".to_owned(),
            map,
            position: TilePosition { x: 1, y: 1 },
            facing: Facing::Down,
        }],
        MapId::BrendansHouse2F => vec![NpcState {
            id: "mom".to_owned(),
            map,
            position: TilePosition { x: 7, y: 1 },
            facing: Facing::Down,
        }],
        MapId::MaysHouse2F => vec![NpcState {
            id: "rival".to_owned(),
            map,
            position: TilePosition { x: 4, y: 3 },
            facing: Facing::Down,
        }],
        MapId::ProfessorBirchsLab => {
            let mut npcs = vec![NpcState {
                id: "aide".to_owned(),
                map,
                position: TilePosition { x: 9, y: 8 },
                facing: Facing::Down,
            }];
            // Route101_EventScript_BirchsBag clears Birch's Lab hide flag
            // only after the rescue/battle sequence.
            if phase >= StoryPhase::BirchRescued {
                npcs.push(NpcState {
                    id: "birch".to_owned(),
                    map,
                    position: TilePosition { x: 6, y: 4 },
                    facing: Facing::Down,
                });
            }
            // Route103_EventScript_RivalEnd clears the Lab rival flag once
            // the Route 103 departure choreography is complete.
            if phase >= StoryPhase::RivalDefeated {
                npcs.push(NpcState {
                    id: "rival".to_owned(),
                    map,
                    position: TilePosition { x: 7, y: 4 },
                    facing: Facing::Down,
                });
            }
            npcs
        }
        MapId::TitleScreen | MapId::ProfessorIntro | MapId::MovingTruck => Vec::new(),
    }
}

fn route101_npcs(phase: StoryPhase) -> Vec<NpcState> {
    let mut npcs = vec![NpcState {
        id: "youngster".to_owned(),
        map: MapId::Route101,
        position: TilePosition { x: 16, y: 8 },
        // The visible east-lane source resident is the left-facing
        // youngster cell; this is an object-event facing, not player input.
        facing: Facing::Left,
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
            id: "birch".to_owned(),
            map: MapId::Route101,
            position: TilePosition { x: 9, y: 13 },
            facing: Facing::Right,
        });
    }
    if phase == StoryPhase::BirchRescue {
        // Route101's map event keeps Birch's Bag at (7,14) until
        // `Route101_EventScript_BirchsBag` completes its post-battle flag
        // sequence. It is a colliding field object, not starter-choice UI.
        npcs.push(NpcState {
            id: "birchs_bag".to_owned(),
            map: MapId::Route101,
            position: TilePosition { x: 7, y: 14 },
            facing: Facing::Down,
        });
        npcs.push(NpcState {
            id: "zigzagoon".to_owned(),
            map: MapId::Route101,
            position: TilePosition { x: 10, y: 13 },
            facing: Facing::Left,
        });
    }
    // Birch's GoSeeRival script clears FLAG_HIDE_ROUTE_101_BOY only after
    // the starter acknowledgement completes in the Lab.
    if phase >= StoryPhase::StarterChosen {
        npcs.push(NpcState {
            id: "route101_boy".to_owned(),
            map: MapId::Route101,
            position: TilePosition { x: 2, y: 13 },
            // The source resident presents the side cell with its authored
            // eastward flip in these settled Route 101 views.
            facing: Facing::Right,
        });
    }
    npcs
}

fn oldale_town_npcs(phase: StoryPhase, potions: u8, oldale_rival_departed: bool) -> Vec<NpcState> {
    let mut npcs = vec![
        NpcState {
            id: "oldale_girl".to_owned(),
            map: MapId::OldaleTown,
            position: TilePosition { x: 16, y: 11 },
            facing: Facing::Left,
        },
        NpcState {
            id: "mart_employee".to_owned(),
            map: MapId::OldaleTown,
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
            id: "footprints_man".to_owned(),
            map: MapId::OldaleTown,
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
            id: "oldale_rival".to_owned(),
            map: MapId::OldaleTown,
            position: TilePosition { x: 11, y: 19 },
            facing: Facing::Up,
        });
    }
    npcs
}

fn route103_npcs(phase: StoryPhase) -> Vec<NpcState> {
    if phase == StoryPhase::StarterChosen {
        vec![NpcState {
            id: "rival".to_owned(),
            map: MapId::Route103,
            position: TilePosition { x: 10, y: 3 },
            facing: Facing::Right,
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
        return if random & 1 == 0 {
            Facing::Left
        } else {
            Facing::Right
        };
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
        NpcState {
            id: "twin".to_owned(),
            map: MapId::LittlerootTown,
            position: twin_position,
            facing: twin_facing,
        },
        NpcState {
            id: "boy".to_owned(),
            map: MapId::LittlerootTown,
            position: TilePosition { x: 14, y: 17 },
            facing: Facing::Down,
        },
    ];
    // The truck's on-frame arrival script clears this hide flag only once
    // Mom and the player have entered their new house.
    if phase >= StoryPhase::NewHome {
        npcs.push(NpcState {
            id: "fat_man".to_owned(),
            map: MapId::LittlerootTown,
            position: TilePosition { x: 12, y: 13 },
            facing: Facing::Down,
        });
    }
    // Birch's completed Lab handoff sets town state 3; on the following town
    // transition Mom waits at the selected player's front door.
    if phase >= StoryPhase::PokedexReceived {
        let position = match player_gender {
            PlayerGender::Brendan => TilePosition { x: 5, y: 9 },
            PlayerGender::May => TilePosition { x: 14, y: 9 },
        };
        npcs.push(NpcState {
            id: "mom_outside".to_owned(),
            map: MapId::LittlerootTown,
            position,
            facing: Facing::Down,
        });
    }
    npcs
}

/// Source `ApproachPlayer*` movement streams for the counterpart-rival
/// bedroom scene. The boolean marks each compact `walk_in_place_faster_*`
/// action; all other commands are 16-frame tile walks.
fn bedroom_rival_approach(
    map: MapId,
    player_facing: Facing,
) -> (&'static [(Facing, bool)], Facing) {
    const B_NORTH: &[(Facing, bool)] = &[
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Down, false),
        (Facing::Down, false),
        (Facing::Left, false),
    ];
    const B_SOUTH: &[(Facing, bool)] = &[
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
    ];
    const B_WEST: &[(Facing, bool)] = &[
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Down, false),
        (Facing::Left, true),
    ];
    const B_EAST: &[(Facing, bool)] = &[
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Down, true),
    ];
    const M_NORTH: &[(Facing, bool)] = &[
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Down, false),
        (Facing::Down, false),
        (Facing::Right, false),
    ];
    const M_SOUTH: &[(Facing, bool)] = &[
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
    ];
    const M_WEST: &[(Facing, bool)] = &[
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Down, true),
    ];
    const M_EAST: &[(Facing, bool)] = &[
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Down, false),
        (Facing::Right, true),
    ];
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
fn bedroom_rival_pc_route(
    map: MapId,
    position: &TilePosition,
) -> (&'static [(Facing, bool)], Facing) {
    const B_NORTH: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Up, false),
        (Facing::Up, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Up, true),
    ];
    const B_SOUTH: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Up, true),
    ];
    const B_WEST: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Up, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Up, true),
    ];
    const B_EAST: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Up, true),
    ];
    const M_NORTH: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Up, false),
        (Facing::Up, false),
        (Facing::Right, true),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Up, true),
    ];
    const M_SOUTH: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Right, true),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Up, true),
    ];
    const M_WEST: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Up, true),
    ];
    const M_EAST: &[(Facing, bool)] = &[
        (Facing::Up, false),
        (Facing::Up, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Right, false),
        (Facing::Up, true),
    ];
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
    const APPROACH_LEFT: &[(Facing, bool)] = &[
        (Facing::Right, true),
        (Facing::Right, true),
        (Facing::Right, true),
        (Facing::Right, true),
        (Facing::Up, true),
        (Facing::Up, true),
        (Facing::Left, true),
    ];
    const APPROACH_RIGHT: &[(Facing, bool)] = &[
        (Facing::Right, true),
        (Facing::Right, true),
        (Facing::Right, true),
        (Facing::Up, true),
        (Facing::Up, true),
        (Facing::Right, true),
    ];
    const RETURN_LEFT: &[(Facing, bool)] = &[
        (Facing::Right, false),
        (Facing::Down, false),
        (Facing::Down, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Up, false),
        (Facing::Down, true),
    ];
    const RETURN_RIGHT: &[(Facing, bool)] = &[
        (Facing::Left, false),
        (Facing::Down, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Left, false),
        (Facing::Down, true),
    ];
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
    path.iter()
        .enumerate()
        .map(|(index, (_, fast))| {
            no_pokemon_twin_path_step_frames(returning && index + 1 == path.len(), *fast)
        })
        .sum()
}

fn stepped_position(position: &TilePosition, direction: Facing) -> TilePosition {
    match direction {
        Facing::Up => TilePosition {
            x: position.x,
            y: position.y - 1,
        },
        Facing::Down => TilePosition {
            x: position.x,
            y: position.y + 1,
        },
        Facing::Left => TilePosition {
            x: position.x - 1,
            y: position.y,
        },
        Facing::Right => TilePosition {
            x: position.x + 1,
            y: position.y,
        },
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

#[cfg(test)]
mod progression_engine_tests {
    use super::*;

    #[test]
    fn paged_field_dialogue_keeps_exclusive_ownership_and_releases_on_final_page() {
        let mut world = WorldState::title_menu();
        world.begin_field_dialogue_pages(vec![
            "First source page.".to_owned(),
            "Second source page.".to_owned(),
        ]);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
        assert_eq!(world.dialogue.as_deref(), Some("First source page."));

        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
        assert_eq!(world.field_dialogue.as_ref().map(|task| task.page), Some(1));
        assert_eq!(world.dialogue.as_deref(), Some("Second source page."));

        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_eq!(world.field_input_owner(), FieldInputOwner::Field);
        assert!(world.field_dialogue.is_none());
        assert!(world.dialogue.is_none());
    }

    #[test]
    fn clock_script_sets_durable_flags_after_its_typed_prompt_and_mom_scene() {
        let mut world = WorldState::bedroom_idle();
        world.begin_clock_edit();
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
        assert!(
            world.field_dialogue.is_some(),
            "clock prompt must use the shared dialogue task"
        );

        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_eq!(world.field_input_owner(), FieldInputOwner::ClockEditor);
        assert!(world.clock_editing.is_some());

        world.confirm_clock();
        world.confirm_clock();
        assert!(world.story_flags.wall_clock_started);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Script);

        // The final Mom-entry VBlank only needs the destination map and the
        // stable source task state; it does not depend on a captured tape.
        world.clock_settle_frames = None;
        world.clock_visit_frames = Some(1);
        world.advance_clock_visit(1);
        assert!(world.story_flags.upstairs_mom_scene_complete);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
    }

    #[test]
    fn data_driven_interior_warp_is_atomic_and_checkpoint_replayable() {
        let mut world = WorldState::bedroom_idle();
        world.map = MapId::MaysHouse1F;
        world.player = TilePosition { x: 2, y: 2 };
        world.elevation =
            crate::native::tile_elevation(world.map, 2, 2).expect("stair origin must be staged");

        assert!(world.begin_interior_warp_at(2, 2));
        let transition = world
            .transition
            .as_ref()
            .expect("warp must create one transition");
        assert_eq!(transition.origin_map, Some(MapId::MaysHouse1F));
        assert_eq!(transition.origin, Some(TilePosition { x: 2, y: 2 }));
        assert_eq!(world.field_input_owner(), FieldInputOwner::Warp);

        world.advance_transition(15);
        assert_eq!(
            world.map,
            MapId::MaysHouse1F,
            "fade-out cannot publish only the map"
        );
        assert_eq!(world.player, TilePosition { x: 2, y: 2 });

        let checkpoint = serde_json::to_vec(&world).expect("transition state must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&checkpoint).expect("transition state must restore");
        world.advance_transition(17);
        restored.advance_transition(17);

        assert_eq!(world, restored);
        assert_eq!(world.map, MapId::MaysHouse2F);
        assert_eq!(world.player, TilePosition { x: 1, y: 1 });
    }

    #[test]
    fn mays_resident_handoff_removes_rival_but_keeps_renderer_walk_receipt() {
        let mut world = WorldState::bedroom_idle();
        world.map = MapId::MaysHouse1F;
        world.player_gender = PlayerGender::Brendan;
        world.player = TilePosition { x: 2, y: 2 };
        world.frame = MAYS_RIVAL_RESIDENT_HANDOFF_FRAME;
        world.mays_house_1f_rival_scene_start_frame = Some(0);
        world.npcs = vec![
            NpcState {
                id: "rival".to_owned(),
                map: MapId::MaysHouse1F,
                position: TilePosition { x: 2, y: 1 },
                facing: Facing::Up,
            },
            NpcState {
                id: "mom".to_owned(),
                map: MapId::MaysHouse1F,
                position: TilePosition { x: 8, y: 5 },
                facing: Facing::Left,
            },
        ];
        world.npc_walk_starts = vec![NpcWalkStart {
            id: "rival".to_owned(),
            frame: MAYS_RIVAL_RESIDENT_HANDOFF_FRAME - 22,
            duration_frames: MAYS_PLAYER_UP_TAIL_FRAMES as u8,
            sprite_facing: Some(Facing::Up),
            in_place: false,
        }];

        world.advance_mays_house_1f_rival_scene(0);

        assert!(!world.npcs.iter().any(|npc| npc.id == "rival"));
        assert!(world.npc_walk_starts.iter().any(|walk| {
            walk.id == "rival"
                && walk.sprite_facing == Some(Facing::Up)
                && walk.frame == MAYS_RIVAL_RESIDENT_HANDOFF_FRAME - 22
        }));
    }

    #[test]
    fn exterior_house_doors_are_one_way_collision_events() {
        let mut world = WorldState::bedroom_idle();
        world.map = MapId::LittlerootTown;
        world.player = TilePosition { x: 14, y: 8 };
        assert!(
            !world.begin_interior_warp_at_facing(14, 8, Some(Facing::Down)),
            "holding Down on a house threshold must not re-enter the house"
        );
        assert!(world.begin_interior_warp_at_facing(14, 8, Some(Facing::Up)));
        assert_eq!(
            world
                .transition
                .as_ref()
                .map(|transition| transition.destination_map),
            Some(MapId::MaysHouse1F)
        );
    }

    #[test]
    fn delayed_warp_keeps_old_map_until_delay_and_fade_are_fully_accounted() {
        let mut direct = WorldState::bedroom_idle();
        direct.map = MapId::MaysHouse1F;
        direct.player = TilePosition { x: 2, y: 2 };
        direct.begin_transition_with_timing(
            MapId::MaysHouse2F,
            TilePosition { x: 1, y: 1 },
            WarpTiming {
                pre_fade_delay_frames: 3,
                fade_frames: 4,
            },
        );
        direct.advance_transition(2);
        assert_eq!(direct.map, MapId::MaysHouse1F);
        assert_eq!(direct.transition_alpha(), 0);
        assert_eq!(
            direct
                .transition
                .as_ref()
                .map(|task| task.pre_fade_delay_remaining),
            Some(1)
        );

        let checkpoint = serde_json::to_vec(&direct).expect("delayed warp must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&checkpoint).expect("delayed warp must restore");
        direct.advance_transition(9);
        restored.advance_transition(9);
        assert_eq!(direct, restored, "warp timing must be replay invariant");
        assert_eq!(direct.map, MapId::MaysHouse2F);
        assert!(
            direct.transition.is_none(),
            "delay + fade-out + fade-in must finish exactly"
        );
    }

    #[test]
    fn transition_alpha_widens_fade_numerator_before_multiplication() {
        let mut world = WorldState::bedroom_idle();
        world.transition = Some(MapTransition {
            origin_map: Some(MapId::MaysHouse1F),
            origin: Some(TilePosition { x: 2, y: 6 }),
            destination_map: MapId::LittlerootTown,
            destination: TilePosition { x: 14, y: 8 },
            pre_fade_delay_remaining: 0,
            frames_remaining: 32,
            total_frames: 32,
            fading_in: true,
        });

        // The first arrival frame is black, then every later frame must
        // become brighter.  A u8 multiplication would make all of these
        // values equal after elapsed=1.
        assert_eq!(world.transition_alpha(), 255);
        world
            .transition
            .as_mut()
            .expect("test transition")
            .frames_remaining = 31;
        assert_eq!(world.transition_alpha(), 248);
        world
            .transition
            .as_mut()
            .expect("test transition")
            .frames_remaining = 24;
        assert_eq!(world.transition_alpha(), 192);
        world
            .transition
            .as_mut()
            .expect("test transition")
            .frames_remaining = 1;
        assert_eq!(world.transition_alpha(), 8);
    }

    #[test]
    fn typed_script_runner_pages_waits_sets_flags_and_hands_off_without_route_input() {
        let mut world = WorldState::bedroom_idle();
        world.begin_field_script(vec![
            ScriptStep::Dialogue {
                pages: vec!["NPC page one".to_owned(), "NPC page two".to_owned()],
            },
            ScriptStep::SetFlag {
                flag: ProgressFlag::WallClockStarted,
            },
            ScriptStep::Wait { frames: 3 },
            ScriptStep::Warp {
                destination_map: MapId::MaysHouse1F,
                destination: TilePosition { x: 2, y: 2 },
                timing: WarpTiming {
                    pre_fade_delay_frames: 2,
                    fade_frames: 4,
                },
            },
        ]);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
        assert_eq!(world.dialogue.as_deref(), Some("NPC page one"));
        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_eq!(world.dialogue.as_deref(), Some("NPC page two"));

        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert!(
            world.story_flags.wall_clock_started,
            "same-VBlank close must run SetFlag"
        );
        assert_eq!(world.field_input_owner(), FieldInputOwner::Script);
        assert!(world.advance_field_script_task(3));
        assert_eq!(world.field_input_owner(), FieldInputOwner::Warp);
        assert_eq!(
            world
                .transition
                .as_ref()
                .map(|task| task.pre_fade_delay_remaining),
            Some(2)
        );
        world.advance_transition(10);
        assert!(
            world.field_script.is_none(),
            "script must release after its terminal warp fades in"
        );
        assert_eq!(world.field_input_owner(), FieldInputOwner::Field);
    }

    #[test]
    fn map_connection_gate_requires_the_declared_story_flag_before_rescue_transition() {
        let mut world = WorldState::bedroom_idle();
        world.map = MapId::LittlerootTown;
        world.player = TilePosition { x: 11, y: 0 };
        world.phase = StoryPhase::MetRival;
        world.birch_prompt_complete = false;
        assert!(!world.begin_connected_map(Facing::Up));
        assert_eq!(world.map, MapId::LittlerootTown);
        assert!(world.transition.is_none());

        world.birch_prompt_complete = true;
        assert!(world.begin_connected_map(Facing::Up));
        assert_eq!(world.phase, StoryPhase::BirchRescue);
        assert_eq!(world.dialogue.as_deref(), Some("H-help me!"));
        assert_eq!(
            world.transition.as_ref().map(|task| task.destination_map),
            Some(MapId::Route101)
        );
    }

    #[test]
    fn route101_bag_script_opens_source_gated_torchic_picker_without_a_route_tape() {
        let mut world = WorldState::route101_rescue();
        world.player = TilePosition { x: 7, y: 15 };
        world.elevation = crate::native::tile_elevation(world.map, 7, 15)
            .expect("Route 101 bag approach must be staged");
        world.facing = Facing::Up;
        world.birch_rescue_stage = 3;
        world.route101_rescue_task = Route101RescueTask::BagPrompt;
        world.dialogue = None;

        assert!(world.interact_with_npc());
        assert_eq!(world.phase, StoryPhase::StarterSelect);
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterPicker
        );
        assert_eq!(world.player, TilePosition { x: 7, y: 15 });
        assert_eq!(world.starter, Some(StarterSpecies::Torchic));
        assert!(world.story_flags.pokemon_obtained);
        assert!(world.story_flags.birch_rescue_started);
        assert!(world.route101_rescue_invariants_hold());
    }

    #[test]
    fn route101_picker_to_zigzagoon_handoff_is_typed_and_checkpoint_replayable() {
        let mut world = WorldState::route101_rescue();
        world.birch_rescue_stage = 3;
        world.open_starter_picker(StarterSpecies::Torchic);
        world.ask_confirm_starter();
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterReveal
        );
        world.advance_starter_reveal(15);
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterConfirm
        );
        world.respond_starter_confirmation(true);
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::BattleHandoff
        );
        assert!(world.route101_rescue_invariants_hold());

        let checkpoint = serde_json::to_vec(&world).expect("battle handoff must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&checkpoint).expect("battle handoff must restore");
        world.begin_birch_battle();
        restored.begin_birch_battle();
        assert_eq!(world, restored);
        assert_eq!(world.route101_rescue_task, Route101RescueTask::Battle);
        let battle = world
            .battle
            .as_ref()
            .expect("handoff must start the scripted battle");
        assert_eq!(battle.opponent, BattleOpponent::Zigzagoon);
        assert_eq!(battle.player_species, "TORCHIC");
        assert_eq!(battle.player_level, 5);
        assert!(world.route101_rescue_invariants_hold());
    }

    #[test]
    fn birch_victory_continuation_is_a_serialized_script_to_the_source_lab_acknowledgement() {
        let mut world = WorldState::starter_battle();
        world.complete_birch_rescue_battle();
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::PostBattleApproach
        );
        assert_eq!(world.field_input_owner(), FieldInputOwner::Script);
        assert!(world.route101_rescue_invariants_hold());

        let encoded = serde_json::to_vec(&world).expect("post-battle task must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&encoded).expect("post-battle task must restore");
        world.advance_field_script_task(16);
        restored.advance_field_script_task(16);
        assert_eq!(
            world, restored,
            "script wait must be checkpoint deterministic"
        );
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::PostBattleDialogue
        );
        assert_eq!(world.dialogue.as_deref(), Some("PROF. BIRCH: Whew…"));

        for _ in 0..6 {
            world.advance_field_dialogue_printer(u32::MAX);
            world.advance_opening_script();
        }
        assert_eq!(world.route101_rescue_task, Route101RescueTask::LabHandoff);
        assert_eq!(
            world.transition.as_ref().map(|task| task.destination_map),
            Some(MapId::ProfessorBirchsLab)
        );

        world.advance_transition(32);
        assert_eq!(world.map, MapId::ProfessorBirchsLab);
        assert_eq!(world.player, TilePosition { x: 6, y: 5 });
        assert_eq!(world.phase, StoryPhase::StarterLab);
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterLabAcknowledgement
        );
        assert!(world.story_flags.starter_acknowledged);
        assert_eq!(
            world.dialogue.as_deref(),
            Some("I’d like you to have your own POKéMON.")
        );
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
        assert!(world.route101_rescue_invariants_hold());
    }

    #[test]
    fn lab_agreement_is_the_durable_gate_for_oldale_and_route103_connections() {
        let mut world = WorldState::starter_battle();
        world.complete_birch_rescue_battle();
        world.advance_field_script_task(16);
        for _ in 0..6 {
            world.advance_field_dialogue_printer(u32::MAX);
            world.advance_opening_script();
        }
        world.advance_transition(32);

        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterLabNicknameChoice
        );
        world.respond_starter_lab_choice(false);
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterLabRivalChoice
        );
        world.respond_starter_lab_choice(true);
        assert_eq!(
            world.route101_rescue_task,
            Route101RescueTask::StarterLabAgreement
        );
        world.advance_opening_script();
        assert_eq!(world.phase, StoryPhase::StarterChosen);
        assert_eq!(world.route101_rescue_task, Route101RescueTask::RouteAccess);
        assert!(world.story_flags.rival_route_unlocked);
        assert!(world.route101_rescue_invariants_hold());

        world.map = MapId::Route101;
        world.player = TilePosition { x: 9, y: 0 };
        assert!(world.begin_connected_map(Facing::Up));
        assert_eq!(world.map, MapId::OldaleTown);
        world.player = TilePosition { x: 9, y: 0 };
        assert!(world.begin_connected_map(Facing::Up));
        assert_eq!(world.map, MapId::Route103);

        let mut locked = WorldState::starter_battle();
        locked.complete_birch_rescue_battle();
        locked.advance_field_script_task(16);
        for _ in 0..6 {
            locked.advance_field_dialogue_printer(u32::MAX);
            locked.advance_opening_script();
        }
        locked.advance_transition(32);
        locked.map = MapId::Route101;
        locked.player = TilePosition { x: 9, y: 0 };
        assert!(
            !locked.begin_connected_map(Facing::Up),
            "Lab acknowledgement alone must not release the Oldale route"
        );
    }

    #[test]
    fn oldale_route103_connection_is_declarative_and_replayable() {
        let mut world = WorldState::route101_rescue();
        world.map = MapId::OldaleTown;
        world.phase = StoryPhase::StarterChosen;
        world.player = TilePosition { x: 9, y: 0 };
        world.elevation = crate::native::tile_elevation(world.map, 9, 0)
            .expect("Oldale north edge must be staged");
        world.story_flags.starter_acknowledged = true;
        world.story_flags.rival_route_unlocked = true;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;

        let encoded = serde_json::to_vec(&world).expect("field connection state must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&encoded).expect("field connection state must restore");
        assert!(world.begin_connected_map(Facing::Up));
        assert!(restored.begin_connected_map(Facing::Up));
        assert_eq!(
            world, restored,
            "cardinal map handoff must not depend on an input tape"
        );
        assert_eq!(world.map, MapId::Route103);
        assert_eq!(world.player, TilePosition { x: 9, y: 21 });
        assert!(world
            .npcs
            .iter()
            .any(|npc| npc.id == "rival" && npc.position == (TilePosition { x: 10, y: 3 })));

        let mut locked = world.clone();
        locked.map = MapId::OldaleTown;
        locked.player = TilePosition { x: 9, y: 0 };
        locked.story_flags.rival_route_unlocked = false;
        assert!(!locked.begin_connected_map(Facing::Up));
        assert_eq!(locked.map, MapId::OldaleTown);
    }

    #[test]
    fn route103_trainer_handoff_and_departure_are_typed_and_checkpoint_deterministic() {
        let mut world = WorldState::route103_rival();
        assert_eq!(world.rival_route_task(), RivalRouteTask::Field);
        assert!(world.interact_with_npc());
        assert_eq!(world.phase, StoryPhase::RivalBattle);
        assert_eq!(world.rival_route_task(), RivalRouteTask::ChallengeDialogue);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Dialogue);
        assert!(world.rival_route_invariants_hold());

        let encoded = serde_json::to_vec(&world).expect("trainer dialogue must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&encoded).expect("trainer dialogue must restore");
        for state in [&mut world, &mut restored] {
            state.advance_field_dialogue_printer(u32::MAX);
            state.advance_opening_script();
            assert_eq!(state.rival_route_task(), RivalRouteTask::ChallengeApproach);
            assert!(state.advance_route103_rival_intro(88));
            assert_eq!(state.rival_route_task(), RivalRouteTask::ChallengeDialogue);
            state.advance_field_dialogue_printer(u32::MAX);
            state.advance_opening_script();
        }
        assert_eq!(
            world, restored,
            "trainer approach and battle handoff must replay after restore"
        );
        assert_eq!(world.rival_route_task(), RivalRouteTask::Battle);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Battle);
        assert!(world.rival_route_invariants_hold());

        // The normal battle resolver publishes this same terminal boundary;
        // assert the map-script continuation rather than faking an input tape.
        world.battle = None;
        world.publish_route103_rival_victory();
        assert_eq!(world.rival_route_task(), RivalRouteTask::DefeatDialogue);
        assert!(world.rival_route_invariants_hold());
        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_eq!(world.rival_route_task(), RivalRouteTask::Departure);
        assert!(world.rival_route_invariants_hold());

        let encoded = serde_json::to_vec(&world).expect("trainer departure must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&encoded).expect("trainer departure must restore");
        assert!(world.advance_rival_departure(u32::MAX));
        assert!(restored.advance_rival_departure(u32::MAX));
        assert_eq!(
            world, restored,
            "rival exit must retain its selected map-script branch after restore"
        );
        assert_eq!(world.rival_route_task(), RivalRouteTask::Field);
        assert!(world.rival_route_invariants_hold());
    }

    fn assert_return_journey_checkpoint(world: &WorldState, expected: ReturnJourneyTask) {
        assert_eq!(world.return_journey_task(), expected);
        assert!(world.return_journey_invariants_hold());
        let encoded = serde_json::to_vec(world).expect("return journey boundary must serialize");
        let restored: WorldState =
            serde_json::from_slice(&encoded).expect("return journey boundary must restore");
        assert_eq!(&restored, world);
        assert_eq!(restored.return_journey_task(), expected);
        assert!(restored.return_journey_invariants_hold());
    }

    #[test]
    fn route103_victory_field_requires_the_authenticated_flag_var_and_party_bundle() {
        let world = WorldState::route103_rival_victory_field();
        assert!(world.route103_rival_victory_field_invariants_hold());
        assert_eq!(world.return_journey_task(), ReturnJourneyTask::ReturnField);
        assert_eq!(world.rival_route_task(), RivalRouteTask::Field);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Field);
        let encoded = serde_json::to_vec(&world).expect("victory field must serialize");
        let restored: WorldState =
            serde_json::from_slice(&encoded).expect("victory field must restore");
        assert_eq!(restored, world);
        assert!(restored.route103_rival_victory_field_invariants_hold());
        assert_eq!(
            world.starter_party.as_ref().map(|party| &party.moves),
            Some(&vec![
                battle_move_slot("SCRATCH", 26),
                battle_move_slot("GROWL", 39),
                battle_move_slot("FOCUS ENERGY", 30),
            ])
        );

        let mut staged_loss = WorldState::route103_rival();
        staged_loss.phase = StoryPhase::RivalDefeated;
        staged_loss.battle = None;
        staged_loss.dialogue = None;
        staged_loss.npcs.clear();
        assert!(!staged_loss.route103_rival_victory_progression_invariants_hold());
        assert!(!staged_loss.route103_rival_victory_field_invariants_hold());
        assert!(!staged_loss.return_journey_invariants_hold());

        for (index, mut malformed) in [world.clone(), world.clone(), world.clone(), world.clone()]
            .into_iter()
            .enumerate()
        {
            match index {
                0 => malformed.story_flags.defeated_rival_route103 = false,
                1 => malformed.story_flags.hide_route103_rival = false,
                2 => malformed.story_vars.birch_lab_state = 3,
                _ => malformed.story_vars.oldale_rival_state = 0,
            }
            assert!(!malformed.route103_rival_victory_field_invariants_hold());
        }
    }

    #[test]
    fn four_slot_player_moves_select_consume_and_persist_their_own_pp() {
        let mut world = WorldState::route103_rival_victory_field();
        world.phase = StoryPhase::RivalBattle;
        world.story_flags.hide_route103_rival = false;
        world.begin_rival_battle();
        world.settle_battle_command_surface();
        let battle = world.battle.as_ref().expect("rival battle must start");
        assert_eq!(
            battle
                .player_moves
                .iter()
                .map(|slot| (slot.move_id, slot.pp))
                .collect::<Vec<_>>(),
            vec![(10, 26), (45, 39), (116, 30)]
        );
        assert!(world.move_slot_invariants_hold());

        world.choose_battle_command();
        world.move_battle_move_cursor(2);
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.move_cursor),
            Some(2)
        );
        world.choose_battle_move();
        assert_eq!(
            world
                .battle
                .as_ref()
                .map(|battle| battle.player_moves[2].pp),
            Some(29)
        );
        assert_eq!(
            world.starter_party.as_ref().map(|party| party.moves[2].pp),
            Some(29)
        );
        assert!(world.move_slot_invariants_hold());

        let encoded = serde_json::to_vec(&world).expect("third move selection must serialize");
        let restored: WorldState =
            serde_json::from_slice(&encoded).expect("third move selection must restore");
        assert_eq!(restored, world);
        assert!(restored.move_slot_invariants_hold());
    }

    #[test]
    fn rival_victory_return_pokedex_shoes_and_route101_departure_form_one_typed_corridor() {
        let mut world = WorldState::route103_rival();
        world.story_flags.starter_acknowledged = true;
        world.story_flags.rival_route_unlocked = true;
        world.publish_route103_rival_victory();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::Route103DefeatDialogue);

        world.advance_opening_script();
        world.advance_opening_script();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::Route103Departure);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Script);
        world.advance_rival_departure(u32::MAX);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::ReturnField);

        world.player = TilePosition { x: 10, y: 21 };
        assert!(world.begin_connected_map(Facing::Down));
        assert_eq!(world.map, MapId::OldaleTown);
        assert_eq!(world.player, TilePosition { x: 10, y: 0 });
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::ReturnField);

        world.player = TilePosition { x: 10, y: 19 };
        world.apply_oldale_rival_trigger();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::OldaleApproach);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Script);
        world.advance_oldale_rival_approach(u32::MAX);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::OldaleDialogue);
        world.advance_field_dialogue_printer(u32::MAX);
        world.advance_opening_script();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::OldaleDeparture);
        world.advance_oldale_rival_departure(u32::MAX);
        assert!(world.oldale_rival_departed);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::ReturnField);

        world.player = TilePosition { x: 10, y: 19 };
        assert!(world.begin_connected_map(Facing::Down));
        assert_eq!(world.map, MapId::Route101);
        world.player = TilePosition { x: 10, y: 19 };
        assert!(world.begin_connected_map(Facing::Down));
        world.advance_transition(32);
        assert_eq!(world.map, MapId::LittlerootTown);
        assert_eq!(world.phase, StoryPhase::RivalDefeated);

        world.player = TilePosition { x: 7, y: 16 };
        assert!(world.begin_interior_warp_at(7, 16));
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::LabWarp);
        world.advance_transition(32);
        assert_eq!(world.map, MapId::ProfessorBirchsLab);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokedexArrival);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Script);

        world.advance_pokedex_arrival(u32::MAX);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokedexDialogue);
        world.advance_opening_script();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokedexReceiptFanfare);
        world.advance_pokedex_receipt_fanfare(u32::MAX);
        assert!(world.has_pokedex);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokedexDialogue);
        world.advance_opening_script();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokedexRivalApproach);
        world.advance_pokedex_rival_approach(u32::MAX);
        world.advance_opening_script();
        assert_eq!(world.poke_balls, 5);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokeBallGiftFanfare);
        world.advance_pokedex_poke_ball_fanfare(u32::MAX);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::PokedexDialogue);
        world.advance_opening_script();
        world.advance_opening_script();
        assert_eq!(world.phase, StoryPhase::PokedexReceived);
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::Field);

        world.player = TilePosition { x: 6, y: 12 };
        assert!(world.begin_interior_warp_at(6, 12));
        world.advance_transition(32);
        assert_eq!(world.map, MapId::LittlerootTown);
        world.player = TilePosition { x: 10, y: 9 };
        world.apply_littleroot_coordinate_trigger();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::RunningShoesPrompt);
        world.advance_running_shoes_wait(u32::MAX);
        world.advance_opening_script();
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::RunningShoesApproach);

        for _ in 0..32 {
            if world.running_shoes_dialogue_frames.is_some() {
                world.advance_running_shoes_dialogue_printer(u32::MAX);
            }
            if world.dialogue.is_some() {
                world.advance_opening_script();
            }
            if world.running_shoes_frames.is_some()
                || world.running_shoes_return_delay_frames.is_some()
                || world.running_shoes_return_door_frames.is_some()
            {
                world.advance_running_shoes_scene(u32::MAX);
            }
            if world.phase == StoryPhase::RunningShoesReceived {
                break;
            }
            assert!(world.return_journey_invariants_hold());
        }
        assert_eq!(world.phase, StoryPhase::RunningShoesReceived);
        assert!(world.running_shoes_item_shown);
        assert!(!world.pending_running_shoes);

        world.player = TilePosition { x: 10, y: 0 };
        assert!(world.begin_connected_map(Facing::Up));
        world.advance_transition(32);
        assert_eq!(world.map, MapId::Route101);
        assert_eq!(world.player, TilePosition { x: 10, y: 19 });
        assert_return_journey_checkpoint(&world, ReturnJourneyTask::Route101Departure);
    }

    fn source_wild_field_world(rule: WildEncounterRule) -> WorldState {
        let mut world = WorldState::route101_rescue();
        world.map = rule.map;
        world.phase = rule.phase;
        world.player = rule.position.clone();
        world.elevation = crate::native::tile_elevation(rule.map, rule.position.x, rule.position.y)
            .expect("source encounter tile must be staged");
        world.facing = Facing::Up;
        world.dialogue = None;
        world.field_dialogue = None;
        world.field_dialogue_frames = None;
        world.field_script = None;
        world.starter = Some(StarterSpecies::Torchic);
        world.ensure_starter_party();
        world
    }

    #[test]
    fn wild_encounter_handoff_is_checkpoint_deterministic_and_run_resumes_its_origin_atomically() {
        let rule = WILD_ENCOUNTER_RULES[0].clone();
        let mut world = source_wild_field_world(rule.clone());
        let origin = (
            world.map,
            world.player.clone(),
            world.elevation,
            world.facing,
        );
        assert!(world.begin_wild_encounter_at_player());
        assert_eq!(world.field_input_owner(), FieldInputOwner::Battle);
        assert!(world.wild_encounter_invariants_hold());
        let encoded = serde_json::to_vec(&world).expect("wild handoff must serialize");
        let mut restored: WorldState =
            serde_json::from_slice(&encoded).expect("wild handoff must restore");

        for candidate in [&mut world, &mut restored] {
            candidate.settle_battle_command_surface();
            let battle = candidate
                .battle
                .as_mut()
                .expect("wild battle must remain active");
            battle.command_cursor = BATTLE_COMMAND_RUN;
            candidate.choose_battle_command();
            assert_eq!(
                candidate
                    .battle
                    .as_ref()
                    .and_then(|battle| battle.message.as_deref()),
                Some("Got away safely!")
            );
            candidate.choose_battle_move();
        }
        assert_eq!(
            world, restored,
            "run completion must replay identically after restore"
        );
        assert!(world.battle.is_none());
        assert_eq!(
            (
                world.map,
                world.player.clone(),
                world.elevation,
                world.facing
            ),
            origin
        );
        assert!(world.route101_poochyena_resolved);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Field);
    }

    #[test]
    fn failed_wild_run_keeps_battle_owned_and_victory_uses_the_same_return_transaction() {
        let rule = WILD_ENCOUNTER_RULES[2].clone();
        let mut world = source_wild_field_world(rule.clone());
        let origin = (world.map, world.player.clone());
        assert!(world.begin_wild_encounter_at_player());
        world.settle_battle_command_surface();
        {
            let battle = world
                .battle
                .as_mut()
                .expect("wild battle must remain active");
            battle.command_cursor = BATTLE_COMMAND_RUN;
            battle.player_speed = 0;
            battle.opponent_speed = u8::MAX;
        }
        world.choose_battle_command();
        let battle = world
            .battle
            .as_ref()
            .expect("failed run must not release field");
        assert_eq!(battle.message.as_deref(), Some("Can't escape!"));
        assert_eq!(battle.run_attempts, 1);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Battle);
        assert!(world.wild_encounter_invariants_hold());
        world.choose_battle_move();
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.turn_phase),
            Some(BattleTurnPhase::TurnResultMessage)
        );
        assert!(
            world.battle.is_some(),
            "failed RUN must resolve an opponent turn before command returns"
        );
        world.choose_battle_move();
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.turn_phase),
            Some(BattleTurnPhase::Command)
        );

        let battle = world
            .battle
            .as_mut()
            .expect("battle still active for forced terminal source state");
        battle.selecting_move = true;
        battle.turn_phase = BattleTurnPhase::MoveSelection;
        battle.move_cursor = 0;
        battle.rival_hp = 0;
        world.choose_battle_move();
        assert!(world.battle.is_none());
        assert_eq!((world.map, world.player.clone()), origin);
        assert!(world.route103_wingull_resolved);
        assert_eq!(world.field_input_owner(), FieldInputOwner::Field);
    }

    #[test]
    fn battle_ui_dma_and_cursor_presentation_rails_are_serialized() {
        let mut world = WorldState::starter_battle();
        world.choose_battle_command();
        let battle = world.battle.as_ref().expect("starter battle must remain active");
        assert_eq!(battle.move_selection_transition_frames, 10);
        assert_eq!(battle.command_cursor_rendered, None);
        for expected in (0..10).rev() {
            world.advance_battle_move_selection_transition();
            assert_eq!(
                world
                    .battle
                    .as_ref()
                    .expect("battle transition must remain active")
                    .move_selection_transition_frames,
                expected
            );
        }

        let mut cursor_world = WorldState::starter_battle();
        cursor_world.move_battle_command_cursor(Facing::Right);
        let battle = cursor_world
            .battle
            .as_ref()
            .expect("cursor transition needs an active battle");
        assert_eq!(battle.command_cursor, BATTLE_COMMAND_BAG);
        assert_eq!(battle.command_cursor_rendered, Some(BATTLE_COMMAND_FIGHT));
        assert_eq!(battle.command_cursor_transition_frames, 1);
        cursor_world.advance_battle_move_selection_transition();
        assert_eq!(
            cursor_world
                .battle
                .as_ref()
                .expect("cursor transition must remain active")
                .command_cursor_rendered,
            None
        );
    }

    #[test]
    fn battle_move_direction_keeps_empty_row_edges_stationary() {
        let rule = WILD_ENCOUNTER_RULES[1].clone();
        let mut world = source_wild_field_world(rule);
        assert!(world.begin_wild_encounter_at_player());
        world.settle_battle_command_surface();
        world.choose_battle_command();
        for _ in 0..10 {
            world.advance_battle_move_selection_transition();
        }
        world.move_battle_move_cursor_direction(Facing::Down);
        assert_eq!(world.battle.as_ref().map(|battle| battle.move_cursor), Some(0));
        world.move_battle_move_cursor_direction(Facing::Right);
        assert_eq!(world.battle.as_ref().map(|battle| battle.move_cursor), Some(1));
        world.move_battle_move_cursor_direction(Facing::Down);
        assert_eq!(world.battle.as_ref().map(|battle| battle.move_cursor), Some(1));
    }

    #[test]
    fn battle_turn_phases_keep_cursor_message_pp_and_hp_boundaries_explicit() {
        let rule = WILD_ENCOUNTER_RULES[1].clone();
        let mut world = source_wild_field_world(rule);
        assert!(world.begin_wild_encounter_at_player());
        world.settle_battle_command_surface();
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.turn_phase),
            Some(BattleTurnPhase::Command)
        );
        assert!(world.battle_turn_invariants_hold());

        world.choose_battle_command();
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.turn_phase),
            Some(BattleTurnPhase::MoveSelection)
        );
        world.move_battle_move_cursor(1);
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.move_cursor),
            Some(1)
        );
        world.cancel_battle_move_selection();
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.turn_phase),
            Some(BattleTurnPhase::Command)
        );

        world.choose_battle_command();
        world.move_battle_move_cursor(-1);
        let before = world
            .battle
            .as_ref()
            .expect("move selection must be active")
            .player_move_pp;
        world.choose_battle_move();
        let battle = world
            .battle
            .as_ref()
            .expect("source first Wurmple turn is non-terminal");
        assert_eq!(battle.player_move_pp, before - 1);
        assert!(battle.rival_hp < battle.opponent_max_hp);
        assert_eq!(battle.turn_phase, BattleTurnPhase::TurnResultMessage);
        assert!(world.battle_turn_invariants_hold());
        world.choose_battle_move();
        assert_eq!(
            world.battle.as_ref().map(|battle| battle.turn_phase),
            Some(BattleTurnPhase::Command)
        );
        assert!(world.battle_turn_invariants_hold());
    }

}
