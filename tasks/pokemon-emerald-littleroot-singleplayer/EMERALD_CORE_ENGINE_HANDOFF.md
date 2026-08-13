# Emerald Rust Core Engine + Content Packs Refactor Handoff

Status: implementation plan and regression contract  
Audience: the next agent working on the Emerald Rust buildout  
Task root: `tasks/pokemon-emerald-littleroot-singleplayer`  
Primary crate: `tasks/pokemon-emerald-littleroot-singleplayer/gold_rust`

## Executive mandate

Continue the Pokémon Emerald Rust implementation by changing its organizing
architecture from route-by-route special cases into a reusable core engine plus
declarative map/content packs.

The refactor is successful when adding another map or route normally requires:

1. declaring map geometry, collision, connections, and warps;
2. registering actors, encounters, scripts, scenes, and render assets;
3. implementing only genuinely new mechanics behind a core interface; and
4. running the same generic engine, scheduler, movement, script, battle, render,
   checkpoint, and evidence paths already used by earlier maps.

It is not successful if route-specific branches are merely moved into files
with generic names.

Preserve source behavior continuously. Before changing architecture, commit the
current Emerald work as a baseline, create a dedicated refactor branch, and run
the Rust and authenticated mGBA differential suites. Run the same immutable
corpus after every meaningful extraction and again before merge. A source
comparison that did not authenticate the ROM, state, adapter, emulator image,
and nonzero VBlank count is not evidence.

## Non-negotiable working rules

- Do not weaken, rewrite, replace, or recapture an oracle fixture to make a
  regression green.
- Do not use Rust-vs-Rust self-consistency as evidence of Emerald correctness.
  It is useful, but it is a separate lane from source equivalence.
- Exit status `2` from an oracle tool is an infrastructure/authentication
  failure. Stop and fix the oracle environment; never count it as a skipped or
  passing test.
- Exit status `1` is a measured divergence. Preserve the report, minimize it if
  useful, and fix or explicitly account for it.
- Keep the baseline reports outside the repository and never overwrite them.
- Use the same seed, checkpoint identity, savestate, random-case count, step
  count, and source image before and after a refactor.
- No content module may own a VBlank loop or mutate arbitrary engine fields.
- No renderer may infer a scene from checkpoint names or exact request/input-log
  history.
- No core module may import a particular route or map pack.
- Return typed errors for invalid external/content/checkpoint state. Do not
  silently fall back, silently ignore invalid transitions, or panic on data that
  can be rejected at a boundary.
- Keep checkpoint/readout compatibility while internal state is migrated.
- Delete a legacy path when its replacement has passed equivalence. Do not leave
  two schedulers permanently active.
- Do not mix unrelated repository changes into the Emerald baseline commit.

## Why this refactor is needed now

The Rust buildout has accumulated enough real behavior that repeated local
patching has become the main risk. The current crate is roughly 61,000 lines:

- `src/lib.rs`: about 7,900 lines;
- `src/world.rs`: about 18,300 lines;
- `src/native.rs`: about 34,000 lines.

The pressure is structural rather than merely cosmetic:

- `WorldState` has roughly 177 fields, including approximately 87 `Option`
  fields, 42 booleans, and many timer/stage fields.
- `BattleState` has roughly 75 fields, with many timing fields.
- There are dozens of `advance_*` methods and over one hundred route-named
  world functions.
- `step()` mixes input transport, held-input replay, VBlank scheduling,
  request-history predicates, and route-specific controller selection.
- Input ownership can be inferred by scanning optional timers instead of being
  represented by one explicit controller state.
- Rendering sometimes selects captured/profile paths from checkpoints or input
  history rather than durable semantic scene state.
- The whole internal `WorldState` is coupled directly to checkpoint/readout
  compatibility.

These patterns make every new route capable of regressing old routes and make
the next patch more likely to add another timer, boolean, checkpoint predicate,
or rendering exception. The architecture below is intended to make shared
patterns mandatory rather than optional.

## Rust interpretation of the requested class-oriented style

Rust does not have implementation inheritance. Do not imitate it with a deep
trait-object hierarchy. Translate the useful intent as follows:

| Desired style | Rust mechanism | Use it for |
|---|---|---|
| classes with public methods | structs with focused `impl` blocks | owning subsystem state and invariants |
| abstract/base classes | small traits at package seams | content registration, behavior policies, render backends |
| subclasses | trait implementations or enum variants | open plugins or closed runtime alternatives |
| shared base implementation | composition and helper structs | outdoor/interior defaults, common actor movement |
| closed class family | enums with exhaustive `match` | controller tasks, map kinds, motion, scene operations, errors |
| strict constructors | `try_new`, builders, `TryFrom` | validation before runtime |
| exceptions | `Result<T, EngineError>` | contextual, recoverable failure paths |
| namespaces/facades | modules plus a small owning facade | `EmeraldEngine`, `ContentRegistry`, `Renderer` |

Use traits only where there is a real extension seam. Prefer an enum when the
engine owns the complete set of variants and benefits from exhaustive matches.
Prefer composition when variants share data or implementation. Avoid trait
explosion and avoid dynamic dispatch inside per-VBlank hot paths unless it is
measured and justified.

This matches the useful observed Synth style: strict contracts separate from
runtimes, small namespace-like public facades, closed enums for operation/state
sets, custom error hierarchies, validation at construction boundaries, and
inheritance only where it clarifies an interface or error family.

## Target dependency architecture

```text
content packs
    |
    v
ContentRegistryBuilder --validate--> immutable ContentRegistry
    |                                      |
    +--------------------------------------+
                                           v
                                      EmeraldEngine
                              +------------+-------------+
                              |            |             |
                           field         script        battle
                              |            |             |
                              +------------+-------------+
                                           |
                                           v
                                  semantic WorldSnapshot
                                     /             \
                                    v               v
                                Renderer      Evidence/Oracle
                                    |
                                    v
                             framebuffer/PPU state

Checkpoint v1/readout v1 <--> compatibility DTOs <--> internal runtime state
```

Dependency rules:

```text
engine          -> contracts and subsystem interfaces
field           -> engine contracts, content registry contracts
script          -> engine commands/events, typed content IDs
battle          -> engine contracts, battle data contracts
render          -> read-only semantic snapshots and render assets
evidence        -> snapshots and completed render output
content::<area> -> registry builder and declarative specs only
compatibility   -> internal state plus stable public DTOs

engine          -X-> content::littleroot
engine          -X-> content::route101
render          -X-> request history/checkpoint names
content         -X-> raw WorldState mutation
content         -X-> frame scheduler implementation
```

## Target module tree

Migrate toward this shape incrementally. The exact number of files can vary,
but dependency direction and ownership should not.

```text
gold_rust/src/
├── lib.rs                         # narrow crate facade and compatibility exports
├── engine/
│   ├── mod.rs
│   ├── facade.rs                  # EmeraldEngine
│   ├── runtime.rs                 # private internal Runtime
│   ├── scheduler.rs               # exactly one VBlank scheduler
│   ├── input.rs                   # physical input and edge/hold normalization
│   ├── commands.rs                # typed state-change requests
│   ├── events.rs                  # typed semantic completions/observations
│   ├── ids.rs                     # MapId, ActorId, ScriptId, etc.
│   ├── errors.rs                  # EngineError hierarchy
│   ├── validation.rs              # cross-subsystem invariant checks
│   └── checkpoint.rs              # internal checkpoint orchestration
├── field/
│   ├── mod.rs
│   ├── map.rs                     # map contracts and active-map state
│   ├── movement.rs                # universal motion timing
│   ├── collision.rs               # terrain/object/trigger collision
│   ├── actors.rs                  # actor runtime and behaviors
│   ├── camera.rs                  # camera tracking and rails
│   └── transitions.rs             # door, warp, connection, fade tasks
├── script/
│   ├── mod.rs
│   ├── spec.rs                    # declarative SceneSpec/ScriptSpec
│   ├── operations.rs              # closed SceneOp enum
│   ├── conditions.rs              # typed predicates
│   └── runtime.rs                 # PC, locals, waits, command/event bridge
├── battle/
│   ├── mod.rs
│   ├── model.rs                   # mechanics and durable battle facts
│   ├── controller.rs              # phase/task progression
│   ├── presentation.rs            # dialogue/animation schedule
│   └── data.rs                    # species, moves, encounters, trainers
├── render/
│   ├── mod.rs
│   ├── scene.rs                   # snapshot -> RenderPlan
│   ├── ppu.rs                     # GBA Mode 0/PPU implementation
│   ├── assets.rs                  # typed immutable asset registry
│   ├── field.rs
│   ├── battle.rs
│   ├── ui.rs
│   └── evidence.rs                # receipts/diffs, not scene selection
├── content/
│   ├── mod.rs
│   ├── registry.rs                # builder, validation, immutable registry
│   ├── common/
│   │   ├── maps.rs
│   │   ├── actors.rs
│   │   └── scenes.rs
│   ├── littleroot/
│   │   ├── mod.rs                 # LittlerootPack registration
│   │   ├── maps/
│   │   │   ├── town.rs
│   │   │   ├── mays_house_1f.rs
│   │   │   ├── mays_house_2f.rs
│   │   │   ├── brendans_house_1f.rs
│   │   │   ├── brendans_house_2f.rs
│   │   │   └── birch_lab.rs
│   │   ├── actors.rs
│   │   ├── scenes.rs
│   │   └── encounters.rs
│   ├── route101/
│   ├── oldale/
│   └── route103/
└── compatibility/
    ├── mod.rs
    ├── checkpoint_v1.rs
    └── readout_v1.rs
```

Do not begin by mechanically splitting three huge files into dozens of huge
files. Establish contracts and dependency tests first, then move one vertical
slice through them.

## Core facade and lifecycle

The public engine should be small and should own subsystem lifecycle:

```rust
pub struct EmeraldEngine {
    runtime: Runtime,
    content: Arc<ContentRegistry>,
    renderer: Renderer,
}

impl EmeraldEngine {
    pub fn new(content: ContentRegistry) -> Result<Self, EngineError>;

    pub fn step(
        &mut self,
        request: StepRequest,
    ) -> Result<StepOutcome, EngineError>;

    pub fn snapshot(&self) -> WorldSnapshot;

    pub fn render(&self) -> Result<Frame, EngineError>;

    pub fn checkpoint(&self) -> Result<Vec<u8>, EngineError>;

    pub fn restore(&mut self, bytes: &[u8]) -> Result<(), EngineError>;
}
```

Keep existing service/scenario signatures alive through compatibility adapters
while callers migrate. Internal methods should return `Result` immediately;
the old wrapper may convert an error into the existing service error shape at
the outermost boundary.

The facade should not know individual route IDs beyond what is present in an
initial configuration or checkpoint DTO.

## Typed identities

Introduce domain-specific identifiers rather than passing unrelated strings or
integers through the engine:

```rust
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq, Serialize, Deserialize)]
pub struct MapId(pub &'static str);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq, Serialize, Deserialize)]
pub struct ActorId(pub &'static str);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq, Serialize, Deserialize)]
pub struct ScriptId(pub &'static str);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq, Serialize, Deserialize)]
pub struct SceneId(pub &'static str);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq, Serialize, Deserialize)]
pub struct AssetId(pub &'static str);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq, Serialize, Deserialize)]
pub struct EncounterTableId(pub &'static str);
```

If deserialized IDs need owned storage, use an interned numeric/newtype key in
the runtime and keep stable strings in DTO/content layers. Do not leak raw
registry indices into checkpoints.

## Content packs and registry

Use one extension seam for area registration:

```rust
pub trait ContentPack {
    fn register(
        &self,
        builder: &mut ContentRegistryBuilder,
    ) -> Result<(), ContentError>;
}
```

Example:

```rust
pub struct LittlerootPack;

impl ContentPack for LittlerootPack {
    fn register(
        &self,
        builder: &mut ContentRegistryBuilder,
    ) -> Result<(), ContentError> {
        maps::register(builder)?;
        actors::register(builder)?;
        scenes::register(builder)?;
        encounters::register(builder)?;
        Ok(())
    }
}
```

The builder is mutable only during startup. `finish()` performs full graph
validation and returns an immutable registry:

```rust
let content = ContentRegistryBuilder::new()
    .with_pack(LittlerootPack)?
    .with_pack(Route101Pack)?
    .with_pack(OldalePack)?
    .with_pack(Route103Pack)?
    .finish()?;
```

Validate at least:

- duplicate map, actor, scene, script, asset, trainer, and encounter IDs;
- missing warp destinations and invalid destination coordinates;
- one-way map connections that were declared bidirectional;
- out-of-bounds warps, triggers, collision overrides, actor spawns, and camera
  anchors;
- invalid trigger rectangles or conflicting trigger priority;
- missing render profiles and assets;
- scripts referencing unknown maps, actors, flags, dialogue, assets, or scenes;
- scripts with invalid jump targets or terminal/wait states;
- encounter tables with invalid level ranges, weights, species, or methods;
- actor behavior that cannot exist on the actor's map;
- map entries that place the player in a blocked or unrenderable location;
- checkpoint IDs that cannot be converted to a valid internal runtime state.

Runtime lookups may then assume the registry is structurally valid, while
still returning typed errors for unavailable dynamic state.

## Map contracts

Maps describe facts. They do not schedule frames.

```rust
pub struct MapSpec {
    pub id: MapId,
    pub kind: MapKind,
    pub dimensions: TileDimensions,
    pub collision: CollisionGrid,
    pub connections: Vec<MapConnection>,
    pub warps: Vec<WarpSpec>,
    pub triggers: Vec<TriggerSpec>,
    pub actors: Vec<ActorSpawn>,
    pub encounter_table: Option<EncounterTableId>,
    pub render_profile: RenderProfileId,
}

pub enum MapKind {
    Outdoor(OutdoorMapSpec),
    Interior(InteriorMapSpec),
    Cave(CaveMapSpec),
    Special(SpecialMapSpec),
}
```

Do not create `BaseMap -> OutdoorMap -> LittlerootMap` inheritance. Put common
data in composed structs and common construction policy in builders:

```rust
MapSpecBuilder::outdoor(MapId::LITTLEROOT_TOWN, 20, 20)
    .render_profile(RenderProfileId::LITTLEROOT)
    .connection(...)
    .warp(...)
    .actor(...)
    .finish()?
```

Existing `WarpTiming`, `GatePredicate`, `MapConnectionRule`, `WarpRule`,
`WildEncounterRule`, and `TrainerEncounterRule` are seeds for these contracts.
Move and normalize them rather than inventing a parallel second rule system.

## Explicit runtime state machines

Replace clouds of optional timers and booleans with enums that make impossible
combinations unrepresentable:

```rust
pub enum ControllerTask {
    Field(FieldTask),
    Transition(TransitionTask),
    Script(ScriptTask),
    Battle(BattleTask),
    Menu(MenuTask),
}

pub enum FieldTask {
    Idle,
    Walking(WalkState),
    Turning(TurnState),
    Interacting(InteractionState),
}

pub enum TransitionTask {
    Door(DoorTransition),
    Warp(WarpTransition),
    Connection(ConnectionTransition),
    Fade(FadeTransition),
}
```

One controller task owns input at a time. `InputOwner` and `FieldInputOwner`
should become explicit views of that state, not deductions made by scanning a
long list of optional timers.

Each task owns its local timing and transitions through explicit methods:

```rust
impl TransitionTask {
    fn advance(
        &mut self,
        frame: &mut FrameContext<'_>,
    ) -> Result<TaskStatus, EngineError>;
}

pub enum TaskStatus {
    Running,
    Completed(Vec<EngineEvent>),
    Replaced(ControllerTask),
}
```

Avoid a universal `stage: u32` when the stages have names. Use an enum such as
`DoorPhase::{Open, Enter, FadeOut, LoadMap, FadeIn, Settle}` and store elapsed
frames only where timing is truly continuous.

## Exactly one VBlank scheduler

There must be one canonical per-VBlank path:

```rust
fn advance_vblank(
    runtime: &mut Runtime,
    input: PhysicalInput,
    content: &ContentRegistry,
) -> Result<StepOutcome, EngineError> {
    let normalized = runtime.input.advance(input);
    let events = runtime.controller.advance(normalized, content)?;
    runtime.apply_events(events, content)?;
    runtime.validate_frame_invariants(content)?;
    Ok(runtime.outcome())
}
```

A multi-frame request loops over this exact function. Held-input chunking must
not select a different scheduler or replay a special route snapshot. This is
why the Rust transport fuzz lane is a permanent test.

Remove route-specific early-return chains from `step()` incrementally. During
migration, a compatibility controller variant may wrap a legacy path, but:

- it must still be advanced through the universal VBlank scheduler;
- it must have a named removal issue/phase;
- no new content may be implemented on the legacy path; and
- it is deleted immediately after its replacement passes the same oracle tape.

## Commands and events instead of raw mutation

Content and scripts request changes through typed commands:

```rust
pub enum EngineCommand {
    MoveActor { actor: ActorId, motion: MotionSpec },
    FaceActor { actor: ActorId, direction: Direction },
    SetFlag(FlagId),
    ClearFlag(FlagId),
    StartDialogue(DialogueId),
    BeginTransition(TransitionSpec),
    StartBattle(BattleRequest),
    ChangeMap(MapEntry),
    PlayAnimation(AnimationId),
}
```

The engine emits semantic events:

```rust
pub enum EngineEvent {
    MotionCompleted(ActorId),
    DialogueAdvanced(DialogueId),
    DialogueCompleted(DialogueId),
    TransitionCompleted(MapId),
    BattleStarted(BattleId),
    BattleEnded(BattleResult),
    FlagChanged(FlagId),
    AnimationCompleted(AnimationId),
}
```

The command application layer is the only place that mutates corresponding
runtime structures. It checks preconditions and returns a typed error for an
invalid command. Scripts wait for events or typed conditions rather than
guessing how many frames another subsystem needs.

## Movement, collision, camera, and actors

Build one motion engine for player movement, NPC movement, scripted movement,
and ambient wandering. Behavior decides intent; motion owns cadence,
interpolation, collision, animation phase, and completion events.

```rust
pub enum MotionIntent {
    Step(Direction),
    Turn(Direction),
    FollowPath(PathId),
    Approach(ActorId),
    Wander(WanderPolicyId),
    Wait(u16),
}

pub struct MotionState {
    pub kind: MotionKind,
    pub origin: TilePosition,
    pub destination: TilePosition,
    pub elapsed_vblanks: u16,
    pub duration_vblanks: u16,
}

pub enum MotionKind {
    Walk,
    Run,
    Turn,
    Bump,
    Scripted,
}
```

`NpcState`, `NpcWalkStart`, and `AmbientWanderState` should be folded into this
system where their semantics overlap. Keep separate data only for genuinely
different behavior policy.

Collision should be a query interface over map terrain, dynamic actors,
directional permissions, and triggers. It should return a reason rather than a
bare boolean:

```rust
pub enum CollisionResult {
    Open,
    BlockedByTerrain(TilePosition),
    BlockedByActor(ActorId),
    BlockedByRule(CollisionRuleId),
    ActivatesTrigger(TriggerId),
    CrossesConnection(MapConnectionId),
}
```

This allows source-measured collision exceptions to be authored as data with
provenance instead of hidden coordinate branches.

## Script and scene runtime

The existing `ScriptStep` and `FieldScriptRunner` are the starting point. Grow
them into one typed scene runtime instead of adding more scene-specific timers.

```rust
pub struct SceneSpec {
    pub id: SceneId,
    pub operations: Vec<SceneOp>,
}

pub enum SceneOp {
    Command(EngineCommand),
    WaitFrames(u16),
    WaitFor(SceneCondition),
    Dialogue(DialogueId),
    Branch {
        condition: SceneCondition,
        then_pc: ScenePc,
        else_pc: ScenePc,
    },
    Jump(ScenePc),
    Complete,
}

pub struct SceneRuntime {
    pub scene: SceneId,
    pub pc: ScenePc,
    pub wait: SceneWait,
    pub locals: SceneLocals,
}
```

Validate all PCs, referenced IDs, and terminal paths at registry build time.
Keep VBlank-sensitive presentation explicit in operations or animation specs;
do not conceal it in checkpoint-name patches.

## Battle decomposition

Split the current large battle state into three responsibilities:

1. `BattleModel`: combatants, stats, moves, RNG, damage, statuses, inventory,
   and durable outcomes.
2. `BattleController`: command ownership, phase state machine, turn ordering,
   action resolution, and transition to/from field state.
3. `BattlePresentation`: source-timed text printing, sprite/OAM/affine changes,
   health-bar animation, sound-less timing, fades, and render-facing events.

Use closed enums for controller state:

```rust
pub enum BattlePhase {
    Intro(BattleIntroState),
    Command(CommandState),
    MoveMenu(MoveMenuState),
    Resolving(ActionResolutionState),
    Fainting(FaintState),
    Victory(VictoryState),
    Escape(EscapeState),
    ReturnToField(ReturnToFieldState),
}
```

An encounter table and trainer definition belong to content/data. Turn
resolution belongs to the battle engine. The affine ball path or exact message
printer phase belongs to presentation. Do not encode all three in one timer
family.

## Semantic rendering boundary

Rendering consumes a read-only semantic snapshot:

```rust
pub struct WorldSnapshot {
    pub frame: u64,
    pub map: MapId,
    pub player: PlayerSnapshot,
    pub actors: Vec<ActorSnapshot>,
    pub controller: ControllerSnapshot,
    pub camera: CameraSnapshot,
    pub dialogue: Option<DialogueSnapshot>,
    pub menu: Option<MenuSnapshot>,
    pub battle: Option<BattleSnapshot>,
    pub transition: Option<TransitionSnapshot>,
}
```

Pipeline:

```text
Runtime -> WorldSnapshot -> SceneBuilder -> RenderPlan -> PPU/Renderer -> Frame
```

Keep `GbaPpuRegisters` and `GbaMode0PpuMemory` as low-level foundations. Move
source-derived assets and profiles into typed asset registries/content packs.
The renderer may choose a profile from `MapSpec`, `BattleSnapshot`, or an
explicit presentation state; it may not examine request count, exact input-log
shape, fuzz case name, or checkpoint name.

Evidence collection occurs after rendering:

```text
WorldSnapshot + RenderPlan + rendered Frame -> EvidenceCollector
```

The authenticated source oracle remains independent. Do not make the Rust
renderer and oracle comparator share scene-identification shortcuts.

## Error model and fail-fast policy

Adopt one contextual error family. `thiserror` is recommended to keep this
cheap, but a manual `Display + Error` implementation is acceptable if adding a
dependency is undesirable.

```rust
#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("invalid content: {0}")]
    Content(#[from] ContentError),

    #[error("invalid transition: {0}")]
    Transition(#[from] TransitionError),

    #[error("runtime invariant failed: {0}")]
    Invariant(#[from] InvariantError),

    #[error("checkpoint failure: {0}")]
    Checkpoint(#[from] CheckpointError),

    #[error("render failure: {0}")]
    Render(#[from] RenderError),

    #[error("evidence failure: {0}")]
    Evidence(#[from] EvidenceError),
}
```

Attach context without relying on formatted prose alone:

```rust
pub struct ErrorContext {
    pub frame: Option<u64>,
    pub map: Option<MapId>,
    pub actor: Option<ActorId>,
    pub scene: Option<SceneId>,
    pub script_pc: Option<ScenePc>,
    pub controller: Option<ControllerKind>,
}
```

Policy:

- malformed content fails during `ContentRegistryBuilder::finish()`;
- malformed checkpoints fail before mutating the active runtime;
- invalid map entry fails before changing maps;
- invalid commands fail before partial application;
- unavailable render assets fail with map/scene/asset context;
- authenticated-oracle identity mismatch fails closed before comparison;
- `debug_assert!` is for already-validated internal facts only;
- `expect`/`unwrap` are not acceptable for content, request, checkpoint, or
  asset data;
- an intentional idempotent no-op should have a named return variant such as
  `AlreadyActive`, not be indistinguishable from ignored invalid input.

## Checkpoint and readout compatibility

Do not serialize the private runtime directly after the refactor. Introduce
versioned DTOs:

```rust
pub enum CheckpointEnvelope {
    V1(CheckpointV1),
    V2(CheckpointV2),
}

impl TryFrom<CheckpointV1> for Runtime { /* validate and migrate */ }
impl From<&Runtime> for CheckpointV1 { /* compatibility until retired */ }
```

Required tests:

- every committed v1 checkpoint loads into the new runtime;
- load -> save -> load preserves public semantics;
- a checkpoint made before each controller handoff resumes at the exact next
  source VBlank;
- corrupt enum tags, unknown IDs, missing content, and impossible phase data
  fail without changing the current session;
- public readout v1 remains stable while internal enums replace fields;
- future checkpoint versions use explicit migration functions rather than
  serde defaults that conceal missing state.

## Build on existing abstractions

Do not discard already useful types. Audit and migrate these first:

- `InputOwner` and `FieldInputOwner`;
- `WarpTiming`, `GatePredicate`, and `MapConnectionRule`;
- `WildEncounterRule` and `TrainerEncounterRule`;
- `ScriptStep` and `FieldScriptRunner`;
- `WarpRule`;
- `GbaPpuRegisters` and `GbaMode0PpuMemory`;
- `NpcState`, `NpcWalkStart`, and `AmbientWanderState`.

For each, choose exactly one outcome:

1. promote it into a core contract largely intact;
2. absorb it into a stronger enum/composed structure with a conversion test; or
3. delete it after all consumers migrate.

Do not create `NewWarpRule`, `NewScriptRunner`, or another parallel state model
and leave both indefinitely.

## Git safety: commit the current Emerald baseline first

The repository currently contains unrelated work. Never run `git add -A` or
commit the whole worktree.

From the repository root:

```bash
cd /Users/joshuapurtell/Documents/GitHub/gamebench

TASK=tasks/pokemon-emerald-littleroot-singleplayer

git status --short --branch
git diff -- "$TASK"
git ls-files --others --exclude-standard -- "$TASK" | sed -n '1,240p'
```

Stage only the Emerald task, explicitly excluding generated evidence and build
output:

```bash
git add -- "$TASK" \
  ":(exclude)$TASK/outputs" \
  ":(exclude)$TASK/outputs/**" \
  ":(exclude)$TASK/gold_rust/target" \
  ":(exclude)$TASK/gold_rust/target/**"

git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Review the name list. Every staged path must begin with
`tasks/pokemon-emerald-littleroot-singleplayer/`. If it does not, unstage that
path. Confirm that task-local generated `outputs/` files are not staged. Confirm
that intended source-derived assets, scripts, fixtures, Rust sources, README,
progress notes, and this handoff are staged.

Commit the current implementation as a behavior baseline:

```bash
git commit -m "feat(emerald): checkpoint current Rust buildout"
BASELINE_SHA=$(git rev-parse HEAD)
printf 'Emerald baseline: %s\n' "$BASELINE_SHA"
```

Do not amend unrelated work into this commit. Then create the dedicated branch:

```bash
git switch -c refactor/emerald-shared-core
test "$(git branch --show-current)" = "refactor/emerald-shared-core"
```

Unrelated unstaged changes may still be present because they belong to other
work. Leave them untouched and keep every refactor commit path-scoped to
`$TASK`.

## Authenticated oracle preflight

The source lane is pinned to:

- ROM SHA-256:
  `a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af`;
- mGBA image:
  `gamebench-mgba-oracle:0.10.5-9`;
- image ID:
  `sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed`;
- registry:
  `fixtures/gold/oracle_registry.json`;
- adapter/config identity embedded in that registry.

Set absolute paths. Do not use `{rom}` or another unresolved placeholder:

```bash
cd /Users/joshuapurtell/Documents/GitHub/gamebench/tasks/pokemon-emerald-littleroot-singleplayer

export EMERALD_ORACLE_ROM='/Users/joshuapurtell/Downloads/Pokemon - Emerald Version (USA, Europe).gba'
export EMERALD_ORACLE_ROOT='/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/work/emerald_oracle'

export EMERALD_BEDROOM_STATE="$EMERALD_ORACLE_ROOT/02_starter.state"
export EMERALD_EXTERIOR_STATE="$EMERALD_ORACLE_ROOT/v8_littleroot_exterior/littleroot_exterior.state"
export EMERALD_FIELD_STATE="$EMERALD_ORACLE_ROOT/v8_littleroot_field_ready/littleroot_field_ready.state"
export EMERALD_RESCUE_STATE="$EMERALD_ORACLE_ROOT/v8_route101_rescue/route101_rescue.state"
export EMERALD_WILD_STATE="$EMERALD_ORACLE_ROOT/v8_route101_wild_battle/route101_wild_battle.state"
export EMERALD_PICKER_STATE="$EMERALD_ORACLE_ROOT/v8_starter_picker/starter_picker.state"
export EMERALD_STARTER_BATTLE_STATE="$EMERALD_ORACLE_ROOT/v8_starter_battle/starter_battle.state"
```

Important: do not substitute
`v8_observability_baseline/bedroom_idle.state`. Its local SHA is not the
promoted `bedroom_idle` registry identity. The authenticated bedroom state is
`02_starter.state`.

Verify identities before any refactor work:

```bash
test "$(shasum -a 256 "$EMERALD_ORACLE_ROM" | awk '{print $1}')" = \
  'a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af'

test "$(shasum -a 256 "$EMERALD_BEDROOM_STATE" | awk '{print $1}')" = \
  '34ae4afe4285efbc61c2345a2927b66097ea97b40636f42e32226f5a586e6e6e'
test "$(shasum -a 256 "$EMERALD_EXTERIOR_STATE" | awk '{print $1}')" = \
  '7fb3b7299cb7089b12865dfcd127288292d7b4ba892c46ea66d9c383cf95c1d3'
test "$(shasum -a 256 "$EMERALD_FIELD_STATE" | awk '{print $1}')" = \
  'ba6f0caf85584713da6f91646d27496a5a66e1460ac8c852c2e7b64c9a2394c9'
test "$(shasum -a 256 "$EMERALD_RESCUE_STATE" | awk '{print $1}')" = \
  '15f611c846623e6ee5608b73dedb7f001ef16e778fa9053d59922eb70b4726dd'
test "$(shasum -a 256 "$EMERALD_WILD_STATE" | awk '{print $1}')" = \
  '10ce0fe1d07bec8876dac98ef192dd2157641df0b273f6939d25a3e158a39ece'
test "$(shasum -a 256 "$EMERALD_PICKER_STATE" | awk '{print $1}')" = \
  '4df9d688e7f7e6cba1ce61f13372b2e607e4310eaeaf4aa7fd683701283216c2'
test "$(shasum -a 256 "$EMERALD_STARTER_BATTLE_STATE" | awk '{print $1}')" = \
  'd6f7d29591dfe91fc005718c410e2f86d1b201266491c5575c4652ec572bc9ac'

test "$(docker image inspect --format '{{.Id}}' gamebench-mgba-oracle:0.10.5-9)" = \
  'sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed'
```

If the image is absent, `scripts/run_mgba_jsonl_oracle.sh` may build it and will
still reject an unexpected image ID. Do not override the expected image ID to
accept an unreviewed image.

Run the harness/registry unit checks:

```bash
python3 scripts/test_emerald_oracle_registry.py
python3 scripts/test_fuzz_emerald_differential.py
python3 scripts/test_mgba_jsonl_input_encoding.py
python3 scripts/test_emerald_coverage_orchestrator.py
```

## Freeze the before-refactor baseline

Use a new external evidence directory named by the baseline commit. Reports are
write-once.

```bash
BASELINE_SHA=${BASELINE_SHA:-$(git rev-parse HEAD)}
export EMERALD_EVIDENCE_ROOT='/Users/joshuapurtell/Documents/Codex/2026-08-13/emerald-core-refactor-evidence'
export EMERALD_BASELINE_DIR="$EMERALD_EVIDENCE_ROOT/baseline-$BASELINE_SHA"

mkdir -p "$EMERALD_BASELINE_DIR"
test -z "$(find "$EMERALD_BASELINE_DIR" -mindepth 1 -maxdepth 1 -print -quit)"
git status --short --branch > "$EMERALD_BASELINE_DIR/git-status-before.txt"
git rev-parse HEAD > "$EMERALD_BASELINE_DIR/revision.txt"
```

### Baseline build and deterministic tests

```bash
cargo fmt --manifest-path gold_rust/Cargo.toml -- --check
cargo test --manifest-path gold_rust/Cargo.toml
cargo build --release --manifest-path gold_rust/Cargo.toml
cargo run --release --manifest-path gold_rust/Cargo.toml \
  --bin scenario -- --verify-manifest
cargo run --release --manifest-path gold_rust/Cargo.toml \
  --bin scenario < fixtures/gold/replays/title_to_met_rival_may.json
```

Capture command output with `tee` if desired, but do not redirect reports into
the repository.

### Baseline Rust transport fuzz

This lane checks one held request against equivalent chunked transport. Run a
larger cheap corpus in addition to the source lanes:

```bash
python3 scripts/fuzz_emerald_differential.py \
  --mode rust \
  --seed 20260730 \
  --random-cases 512 \
  --output "$EMERALD_BASELINE_DIR/rust-transport-512.json"
```

This must exit `0`. A transport violation is an engine regression even if a
particular source endpoint still happens to match.

### Baseline closed regression gates

Run all currently frozen wrappers with their output directed to the baseline
directory:

```bash
export EMERALD_FUZZ_OUTPUT_DIR="$EMERALD_BASELINE_DIR/closed-gates"
mkdir -p "$EMERALD_FUZZ_OUTPUT_DIR"

scripts/run_emerald_fuzz_progress.sh
scripts/run_emerald_mays_house_progress.sh

export EMERALD_ROUTE101_WILD_STATE="$EMERALD_WILD_STATE"
scripts/run_emerald_route101_wild_gate.sh
```

The bedroom gate must preserve its frozen exact corpus, the May's House gate
must preserve its full transition/dialogue/exit corpus, and the Route 101 wild
gate must preserve its exact entry/command handoff. These are hard gates, not
“no worse than baseline” metrics.

### Baseline canonical source-equivalence matrix

Define one runner and use it unchanged before and after:

```bash
run_emerald_equiv() {
  label=$1
  segment=$2
  checkpoint=$3
  state=$4
  random_cases=$5
  steps=$6
  output_dir=$7

  python3 scripts/fuzz_emerald_differential.py \
    --mode both \
    --seed 20260730 \
    --segment "$segment" \
    --oracle-checkpoint "$checkpoint" \
    --oracle-rom "$EMERALD_ORACLE_ROM" \
    --oracle-state "$state" \
    --oracle-command "scripts/run_mgba_jsonl_oracle.sh '$EMERALD_ORACLE_ROM' '$state' '$checkpoint'" \
    --random-cases "$random_cases" \
    --steps "$steps" \
    --output "$output_dir/$label.json"
}

run_emerald_equiv bedroom bedroom bedroom_idle \
  "$EMERALD_BEDROOM_STATE" 16 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv mays-house mays_house_exit bedroom_idle \
  "$EMERALD_BEDROOM_STATE" 16 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv littleroot-exterior littleroot_exterior littleroot_exterior \
  "$EMERALD_EXTERIOR_STATE" 0 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv littleroot-field littleroot_field littleroot_field_ready \
  "$EMERALD_FIELD_STATE" 16 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv route101-rescue littleroot_exterior route101_rescue \
  "$EMERALD_RESCUE_STATE" 0 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv route101-wild route101_wild_battle route101_wild_battle \
  "$EMERALD_WILD_STATE" 0 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv starter-picker starter_picker starter_picker \
  "$EMERALD_PICKER_STATE" 0 64 "$EMERALD_BASELINE_DIR"

run_emerald_equiv starter-battle starter_battle starter_battle \
  "$EMERALD_STARTER_BATTLE_STATE" 0 64 "$EMERALD_BASELINE_DIR"
```

The `route101-rescue` call intentionally uses the generic physical-input probe
corpus selected by the harness fallback. The registry checkpoint and savestate
still authenticate the actual rescue boundary.

Preserve every report even when a currently open lane diverges. For an open
lane, the baseline report is the exact before-state: the refactor must not add
divergent tapes, pixel-mismatch VBlanks, or semantic-boundary mismatches.

### Baseline coverage/oracle smoke

Run the orchestrator for at least the promoted bedroom identity. This separately
proves load/load determinism and registry/emulator/config identity:

```bash
python3 scripts/emerald_coverage_orchestrator.py \
  --rom "$EMERALD_ORACLE_ROM" \
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh '$EMERALD_ORACLE_ROM' '$EMERALD_BEDROOM_STATE' bedroom_idle" \
  --state "bedroom_idle=$EMERALD_BEDROOM_STATE" \
  --random-cases 16 \
  --steps 64 \
  --output-dir "$EMERALD_BASELINE_DIR/coverage-bedroom"
```

Do not read “unexecuted missing state” rows as passes. The orchestrator reports
only supplied authenticated states as executed.

## Refactor implementation phases

Each phase should be a reviewable commit or short commit series. Run the cheap
Rust gate after every commit and the relevant authenticated source tape after
every behavior-owning change.

### Phase 0: lock evidence and architecture constraints

Deliverables:

- all baseline reports above exist outside the repository;
- oracle identity preflight is green;
- current exact gates are recorded;
- architecture dependency rules are documented in code/module comments;
- add a test or lint script that rejects forbidden imports/patterns.

Recommended initial enforcement searches:

```bash
rg -n 'content::(littleroot|route101|oldale|route103)' gold_rust/src/engine gold_rust/src/field
rg -n 'checkpoint|input_log|request_history' gold_rust/src/render
rg -n 'advance_vblank|for .*frame|while .*frame' gold_rust/src/content
```

Acceptance: the searches are encoded as intentional tests with narrow
allowlists where compatibility code still needs temporary access.

### Phase 1: module skeleton, IDs, errors, and registry contracts

Deliverables:

- create `engine`, `field`, `script`, `battle`, `render`, `content`, and
  `compatibility` module boundaries;
- add typed IDs and error hierarchy;
- add `ContentRegistryBuilder`, immutable `ContentRegistry`, and strict
  validation;
- adapt existing map/rule data into registry entries without changing runtime
  behavior;
- retain old `step()` and rendering behavior behind the facade temporarily.

Tests:

- duplicate/missing/out-of-bounds content rejects early;
- all current content builds into one registry;
- all existing Rust tests and manifest verification pass;
- Rust transport 512 report remains green;
- canonical source matrix is byte/metric equivalent.

This phase should move definitions and add contracts, not change timing.

### Phase 2: checkpoint/readout compatibility layer

Deliverables:

- separate internal runtime state from checkpoint/readout v1 DTOs;
- add explicit conversion and validation;
- stop serializing newly private subsystem objects directly;
- add atomic restore: parse/validate into a candidate runtime, then swap only
  after success.

Tests:

- every exposed checkpoint creates a rollout;
- checkpoint/restore during held input, transition, script, menu, and battle;
- malformed checkpoints fail without mutation;
- source continuation is unchanged at each migrated boundary.

### Phase 3: universal VBlank scheduler and input ownership

Deliverables:

- one `advance_vblank` path for one-frame and multi-frame requests;
- explicit `ControllerTask`/owner enum;
- held input normalized once, with no route-specific replay scheduler;
- legacy routes wrapped as temporary controller variants;
- delete ownership inference over optional timers as each owner migrates.

Required gate order:

1. Rust transport fuzz after each scheduler change;
2. bedroom authenticated gate;
3. May's House authenticated gate;
4. Littleroot field authenticated matrix;
5. battle entry gates if battle ownership code was touched.

Do not continue to content migration while transport equivalence is red.

### Phase 4: Littleroot content pack as the reference implementation

Migrate in vertical slices:

1. bedroom map and player movement;
2. upstairs-to-downstairs transition;
3. May's House 1F actors/dialogue/exit;
4. Littleroot exterior collision/camera/actors;
5. both rival houses;
6. Birch Lab map and actors.

For each slice:

- map geometry, warps, actors, and render profile move to content;
- scheduler/timing remains generic;
- scripts issue commands and wait for events;
- source-derived exceptions become named data with provenance;
- remove the old route/map branch after the same tape passes.

The bedroom, May's House, and Littleroot field form the first three-consumer
proof for shared map/transition/movement abstractions.

### Phase 5: unified movement, actor behavior, collision, and camera

Deliverables:

- player, NPC, ambient wander, and scripted walk share motion timing;
- collision returns typed reasons;
- actor occupancy and trigger ordering are centralized;
- camera projection follows one field system;
- source-measured directional collision overrides are map data;
- no content module updates pixel interpolation or animation phase directly.

Test the same motion abstraction against:

- bedroom interior;
- May's House stairs/door;
- Littleroot exterior blocked and open movement;
- Route 101 long directional lanes;
- an ambient NPC rail;
- checkpoint/restore mid-stride.

### Phase 6: typed scene runtime

Deliverables:

- migrate clock/TV, Mom, house dialogue, Birch rescue, starter choice, and Lab
  scenes into `SceneSpec`/`SceneRuntime`;
- use named operations and waits rather than root booleans/timers;
- validate script references and control flow at registry construction;
- expose semantic scene state to rendering.

Run the full contiguous May's House tape, rescue probes, starter picker, and
checkpoint/restore at operation boundaries.

### Phase 7: Route 101, Oldale, and Route 103 content packs

Deliverables:

- route geometry/connections/warps/encounters live in map packs;
- the engine has no route-name branches;
- wild encounter initiation is a generic field event;
- trainer/rival triggers use generic trigger/script/battle commands;
- connection transitions use the same scheduler as Littleroot.

Use the three-consumer rule again: the shared connection/encounter abstraction
is not complete until Route 101, Oldale, and Route 103 all use it.

### Phase 8: battle model/controller/presentation split

Migrate narrow authenticated seams first:

1. Route 101 wild entry and command handoff;
2. starter battle command-ready states;
3. one complete turn;
4. repeated turns;
5. victory/run return-to-field;
6. Route 103 wild and rival battle variants.

Keep mechanics, controller ownership, and visual timing separate. After each
seam, run its exact authenticated tape and a checkpoint/restore continuation.
Do not declare battle generalized from idle frames alone.

### Phase 9: semantic renderer and evidence separation

Deliverables:

- every renderer entry accepts `WorldSnapshot`/`RenderPlan`, not raw request
  history;
- typed asset/profile lookup;
- field, UI, and battle rendering share low-level PPU primitives;
- evidence collection is a separate observer;
- exact source-derived overlays are selected by explicit semantic presentation
  state and documented provenance, not fuzz/checkpoint identity.

For each converted renderer path, require exact RGB at all already exact
VBlanks. Rendering-only changes may use `--minimize-mismatches pixel` and an
external PPU capture directory to isolate the first source discrepancy.

### Phase 10: remove compatibility scaffolding and enforce the future pattern

Delete:

- route-specific scheduler branches;
- duplicate movement paths;
- input-owner inference from timer scans;
- migrated root booleans/options/timers;
- checkpoint/request-history scene dispatch;
- parallel legacy script and battle controllers;
- unused exact-patch functions made obsolete by semantic rendering.

Add permanent tests proving a small synthetic map/content pack can be
registered and traversed without editing the scheduler or renderer dispatch.

## Per-commit test ladder

Use the smallest sufficient gate while iterating, then escalate.

### Tier 1: every commit

```bash
cargo fmt --manifest-path gold_rust/Cargo.toml -- --check
cargo test --manifest-path gold_rust/Cargo.toml
python3 scripts/fuzz_emerald_differential.py \
  --mode rust --seed 20260730 --random-cases 128 \
  --output "/tmp/emerald-rust-$(git rev-parse --short HEAD)-$$.json"
```

### Tier 2: every behavior-owning subsystem change

Run the authenticated checkpoint(s) touched by the change:

- input/scheduler/movement: bedroom + May's House + Littleroot field;
- map/transition: source and destination map boundaries;
- scene runtime: full contiguous scene tape, not only endpoint;
- battle: wild gate + picker/battle boundary involved;
- renderer: every checkpoint/profile that consumes the changed path;
- checkpoint: at least one field, transition, script, menu, and battle state.

### Tier 3: every phase completion

Run:

- release build;
- all Rust tests;
- manifest verification;
- 512-case Rust transport fuzz;
- all three closed wrappers;
- canonical eight-row source-equivalence matrix;
- coverage orchestrator smoke.

### Tier 4: before merge

Run the entire post-refactor protocol below in a new evidence directory and
compare it programmatically with the frozen baseline.

## Post-refactor regression protocol

Create a new write-once directory:

```bash
AFTER_SHA=$(git rev-parse HEAD)
export EMERALD_AFTER_DIR="$EMERALD_EVIDENCE_ROOT/after-$AFTER_SHA"
mkdir -p "$EMERALD_AFTER_DIR"
test -z "$(find "$EMERALD_AFTER_DIR" -mindepth 1 -maxdepth 1 -print -quit)"
git status --short --branch > "$EMERALD_AFTER_DIR/git-status-after.txt"
git rev-parse HEAD > "$EMERALD_AFTER_DIR/revision.txt"
```

Repeat, without changing arguments:

1. format/build/unit tests;
2. manifest verification and continuous scenario replay;
3. 512-case Rust transport fuzz into
   `$EMERALD_AFTER_DIR/rust-transport-512.json`;
4. all closed wrappers into `$EMERALD_AFTER_DIR/closed-gates`;
5. the canonical matrix using `$EMERALD_AFTER_DIR` as the final function
   argument;
6. the coverage orchestrator into `$EMERALD_AFTER_DIR/coverage-bedroom`.

Example matrix repetition:

```bash
run_emerald_equiv bedroom bedroom bedroom_idle \
  "$EMERALD_BEDROOM_STATE" 16 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv mays-house mays_house_exit bedroom_idle \
  "$EMERALD_BEDROOM_STATE" 16 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv littleroot-exterior littleroot_exterior littleroot_exterior \
  "$EMERALD_EXTERIOR_STATE" 0 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv littleroot-field littleroot_field littleroot_field_ready \
  "$EMERALD_FIELD_STATE" 16 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv route101-rescue littleroot_exterior route101_rescue \
  "$EMERALD_RESCUE_STATE" 0 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv route101-wild route101_wild_battle route101_wild_battle \
  "$EMERALD_WILD_STATE" 0 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv starter-picker starter_picker starter_picker \
  "$EMERALD_PICKER_STATE" 0 64 "$EMERALD_AFTER_DIR"
run_emerald_equiv starter-battle starter_battle starter_battle \
  "$EMERALD_STARTER_BATTLE_STATE" 0 64 "$EMERALD_AFTER_DIR"
```

## Programmatic before/after comparison

Do not compare only a headline percentage. Require equal corpus identity and no
worse per-case results. The following read-only comparator can be run directly
from the shell; it does not alter the repository:

```bash
python3 - "$EMERALD_BASELINE_DIR" "$EMERALD_AFTER_DIR" <<'PY'
import json
import pathlib
import sys

before_dir = pathlib.Path(sys.argv[1])
after_dir = pathlib.Path(sys.argv[2])
names = [
    "bedroom.json",
    "mays-house.json",
    "littleroot-exterior.json",
    "littleroot-field.json",
    "route101-rescue.json",
    "route101-wild.json",
    "starter-picker.json",
    "starter-battle.json",
]

def load(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)

def lane(report, name):
    return next(item for item in report["lanes"] if item["lane"] == name)

errors = []
for name in names:
    before = load(before_dir / name)
    after = load(after_dir / name)
    if before.get("seed") != after.get("seed"):
        errors.append(f"{name}: seed changed")

    before_rust = lane(before, "rust_transport_contract")
    after_rust = lane(after, "rust_transport_contract")
    if before_rust["case_count"] != after_rust["case_count"]:
        errors.append(f"{name}: transport corpus size changed")
    if after_rust["violation_count"] > before_rust["violation_count"]:
        errors.append(f"{name}: transport violations regressed")
    if before_rust["violation_count"] == 0 and after_rust["violation_count"] != 0:
        errors.append(f"{name}: previously exact transport lane is no longer exact")

    before_source = lane(before, "source_behavior_oracle")
    after_source = lane(after, "source_behavior_oracle")
    identity_fields = ["rom_sha256", "state_sha256", "oracle_checkpoint"]
    for field in identity_fields:
        if before_source.get(field) != after_source.get(field):
            errors.append(f"{name}: source identity field changed: {field}")
    if before_source["case_count"] != after_source["case_count"]:
        errors.append(f"{name}: source corpus size changed")
    if before_source["compared_source_frames"] != after_source["compared_source_frames"]:
        errors.append(f"{name}: compared VBlank count changed")
    for metric in (
        "divergence_count",
        "pixel_mismatch_frames",
        "semantic_boundary_mismatches",
    ):
        if after_source[metric] > before_source[metric]:
            errors.append(
                f"{name}: {metric} regressed "
                f"{before_source[metric]} -> {after_source[metric]}"
            )

    before_cases = {case["name"]: case for case in before_source["cases"]}
    after_cases = {case["name"]: case for case in after_source["cases"]}
    if before_cases.keys() != after_cases.keys():
        errors.append(f"{name}: source case names changed")
        continue
    for case_name, old in before_cases.items():
        new = after_cases[case_name]
        if old["compared_source_frames"] != new["compared_source_frames"]:
            errors.append(f"{name}/{case_name}: VBlank count changed")
        if old["result"] == "exact" and new["result"] != "exact":
            errors.append(f"{name}/{case_name}: previously exact case regressed")
        if new["pixel_mismatch_frames"] > old["pixel_mismatch_frames"]:
            errors.append(f"{name}/{case_name}: pixel mismatches increased")
        if new["semantic_boundary_mismatches"] > old["semantic_boundary_mismatches"]:
            errors.append(f"{name}/{case_name}: semantic mismatches increased")

if errors:
    print("REGRESSION")
    print("\n".join(f"- {error}" for error in errors))
    raise SystemExit(1)
print("PASS: corpus identities match and no measured metric regressed")
PY
```

For a mature workflow, promote this comparator into a tracked script with unit
tests. It should eventually also compare emulator/config identity, case button
programs, semantic boundaries, and exact proof-tape hashes for every
previously exact case.

## What counts as a regression

Any of the following blocks the refactor:

- a previously exact tape becomes divergent;
- source or Rust RGB changes at a previously exact VBlank;
- a public semantic boundary changes unexpectedly;
- transport chunking differs from a continuous hold;
- fewer source VBlanks or semantic boundaries are compared;
- a mandatory case disappears or is shortened;
- checkpoint restoration changes the next source-visible frame;
- the oracle ROM, state, image, adapter, config, or observability identity
  changes without separate review;
- a harness exits `2` or omits a report;
- the renderer still reaches into checkpoint/input history after migration;
- a map pack introduces a scheduler or direct runtime mutation;
- an invalid content/checkpoint state is silently accepted.

An intended source-correctness fix may improve an open baseline divergence. In
that case preserve both reports and the minimized proof. Improvement in one
metric does not authorize regression in another unrelated tape.

## Diagnosing a differential failure

1. Preserve the original report and artifact directory.
2. Classify the first mismatch as transport, semantic, pixel, or both.
3. Re-run only the failing checkpoint/tape with the same identity.
4. Use minimization for open/random failures:

   ```bash
   python3 scripts/fuzz_emerald_differential.py \
     --mode oracle \
     --seed 20260730 \
     --segment bedroom \
     --oracle-checkpoint bedroom_idle \
     --oracle-rom "$EMERALD_ORACLE_ROM" \
     --oracle-state "$EMERALD_BEDROOM_STATE" \
     --oracle-command "scripts/run_mgba_jsonl_oracle.sh '$EMERALD_ORACLE_ROM' '$EMERALD_BEDROOM_STATE' bedroom_idle" \
     --random-cases 16 \
     --steps 64 \
     --minimize-mismatches semantic \
     --minimize-limit 3 \
     --minimize-max-replays 64 \
     --output "$EMERALD_AFTER_DIR/bedroom-minimized.json"
   ```

5. For pixel failures, use `--minimize-mismatches pixel`. Capture full PPU
   receipts only into a new explicit external directory.
6. Find the first ownership/state divergence, not merely the final bad frame.
7. Add a focused regression test for the generalized invariant.
8. Re-run the touched checkpoint, then its neighboring seam, then the full
   phase ladder.

Do not add a frame-specific patch until the semantic owner, map, scene,
controller phase, and source evidence are understood. If a source-derived
pixel exception is truly required, encode it behind a semantic render state
and document the authenticated receipt.

## Architectural enforcement tests

Add permanent checks for:

- core modules cannot import individual content packs;
- content modules cannot access private `Runtime`/`WorldState` fields;
- content modules cannot implement VBlank loops;
- render modules cannot inspect request history, fuzz labels, or checkpoint
  names;
- only compatibility modules know checkpoint/readout v1 layout;
- every content pack validates independently and in the full registry;
- every ID reference is resolved before runtime;
- every closed state machine is exhaustively matched;
- one synthetic map can be registered without editing engine dispatch;
- all invalid registrations return a contextual `ContentError`;
- all exposed checkpoints round-trip through compatibility conversion;
- a continuous hold equals every tested transport partition.

Prefer structural tests over comments. A future agent should have to fight a
failing test before reintroducing route-specific scheduler logic.

## Three-consumer abstraction rule

Do not declare a core abstraction complete after using it on one route. Require
at least three meaningfully different consumers:

- map/movement: bedroom interior, Littleroot exterior, Route 101;
- transitions: interior stairs, exterior door warp, map connection;
- actors: player, scripted NPC, ambient NPC;
- scenes: Mom/TV, Birch rescue, rival trigger;
- battles: starter battle, wild battle, trainer/rival battle;
- rendering: interior field, outdoor field, battle/UI;
- checkpoints: idle field, active transition/script, active battle.

If an abstraction needs flags named after all three consumers, it is probably
not the common pattern yet.

## Recommended commit sequence on the refactor branch

Use small, behavior-preserving commits where possible:

1. `refactor(emerald): add core module boundaries and typed errors`
2. `refactor(emerald): add validated content registry and typed ids`
3. `refactor(emerald): isolate checkpoint and readout v1 adapters`
4. `refactor(emerald): route input through universal vblank scheduler`
5. `refactor(emerald): migrate littleroot maps into content pack`
6. `refactor(emerald): unify field movement collision and actors`
7. `refactor(emerald): migrate field scenes to typed runtime`
8. `refactor(emerald): register route101 oldale and route103 content`
9. `refactor(emerald): split battle model controller and presentation`
10. `refactor(emerald): render from semantic world snapshots`
11. `test(emerald): enforce architecture and equivalence contracts`
12. `refactor(emerald): remove legacy route-specific paths`

Each commit message should note the exact oracle reports run. Do not squash away
the point at which a large migration first became source-equivalent until the
review is complete.

## Definition of done

The core-engine refactor is done only when:

- there is one VBlank scheduler;
- input ownership is one explicit enum/state machine;
- map packs contain data and scripts, not scheduler branches;
- Littleroot, Route 101, Oldale, and Route 103 use the same map/connection
  interfaces;
- player, NPC, ambient, and scripted movement share one motion engine;
- scenes run through typed operations/commands/events;
- battle mechanics, controller phases, and presentation are separated;
- rendering is selected from semantic snapshots;
- authenticated oracle/evidence code is independent of rendering selection;
- checkpoint/readout compatibility is versioned and tested;
- invalid content and invalid restores fail early with contextual errors;
- architecture tests prevent the old dependency patterns;
- all previously exact authenticated tapes remain exact;
- no open lane has worse divergence metrics under the identical corpus;
- Rust held-input transport fuzz remains clean;
- baseline and post-refactor evidence directories, revisions, and comparator
  output are retained for review;
- adding a small map requires no edit to scheduler or renderer dispatch.

## Final agent handoff checklist

- [ ] Read this document and `PROGRESS.md` before editing.
- [ ] Inspect the dirty worktree and preserve unrelated changes.
- [ ] Stage only the Emerald task, excluding `outputs/` and `target/`.
- [ ] Commit the current Emerald baseline.
- [ ] Create `refactor/emerald-shared-core` from that commit.
- [ ] Authenticate ROM, states, registry, and mGBA image.
- [ ] Run and retain all before-refactor reports.
- [ ] Implement phases incrementally, using existing abstractions where sound.
- [ ] Run Rust transport fuzz after every scheduler/state change.
- [ ] Run the nearest authenticated source tape after every behavior change.
- [ ] Remove each legacy path as soon as its replacement proves equivalent.
- [ ] Run the complete post-refactor matrix with identical arguments.
- [ ] Run the programmatic before/after comparator.
- [ ] Retain minimized proofs for every intentional correctness change.
- [ ] Do not claim completion from unit tests or endpoint screenshots alone.
- [ ] Update `PROGRESS.md` with architecture status and exact evidence counts.

