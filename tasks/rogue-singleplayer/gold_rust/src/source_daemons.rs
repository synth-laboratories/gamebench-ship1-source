use crate::RogueRng;
use serde_json::{json, Value};

pub const EMPTY: i32 = 0;
pub const DAEMON: i32 = -1;
pub const BEFORE: i32 = 1;
pub const AFTER: i32 = 2;
pub const MAXDAEMONS: usize = 20;

pub const CANSEE: i32 = 0o000002;
pub const ISBLIND: i32 = 0o000004;
pub const ISLEVIT: i32 = 0o000010;
pub const ISHASTE: i32 = 0o000100;
pub const ISHUH: i32 = 0o001000;
pub const ISRUN: i32 = 0o020000;

pub const R_REGEN: i32 = 9;
pub const R_DIGEST: i32 = 10;

const MORETIME: i32 = 150;
const STARVETIME: i32 = 850;

#[derive(Clone)]
pub struct SourceStats {
    pub level: i32,
    pub hp: i32,
}

#[derive(Clone)]
pub struct SourceRing {
    pub which: i32,
}

#[derive(Clone)]
pub struct DelayedAction {
    pub action: &'static str,
    pub action_type: i32,
    pub arg: i32,
    pub time: i32,
}

pub struct DaemonWorld {
    pub rng: RogueRng,
    pub stats: SourceStats,
    pub max_hp: i32,
    pub quiet: i32,
    pub player_flags: i32,
    pub left_ring: Option<SourceRing>,
    pub right_ring: Option<SourceRing>,
    pub food_left: i32,
    pub hungry_state: i32,
    pub no_command: i32,
    pub amulet: i32,
    pub running: bool,
    pub to_death: bool,
    pub count: i32,
    pub proom_gone: bool,
    pub visible_invisible: i32,
    pub between: i32,
    pub actions: Vec<DelayedAction>,
    pub markers: Vec<String>,
    pub trace: serde_json::Map<String, Value>,
}

pub fn source_daemons_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_daemons.v1",
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn doctor(world: &mut DaemonWorld) {
    let level = world.stats.level;
    let old_hp = world.stats.hp;
    world.quiet += 1;
    if level < 8 {
        if world.quiet + (level << 1) > 20 {
            world.stats.hp += 1;
        }
    } else if world.quiet >= 3 {
        world.stats.hp += world.rng.rnd(level - 7) + 1;
    }
    if is_ring(&world.left_ring, R_REGEN) {
        world.stats.hp += 1;
    }
    if is_ring(&world.right_ring, R_REGEN) {
        world.stats.hp += 1;
    }
    if old_hp != world.stats.hp {
        if world.stats.hp > world.max_hp {
            world.stats.hp = world.max_hp;
        }
        world.quiet = 0;
    }
}

pub fn swander(world: &mut DaemonWorld) {
    start_daemon(world, "rollwand", 0, BEFORE);
}

pub fn rollwand(world: &mut DaemonWorld) {
    world.between += 1;
    if world.between >= 4 {
        let roll = world.rng.roll(1, 6);
        world.trace.insert("wander_roll".to_string(), json!(roll));
        if roll == 4 {
            world.markers.push("wanderer".to_string());
            kill_daemon(world, "rollwand");
            let time = wandertime(world);
            fuse(world, "swander", 0, time, BEFORE);
        }
        world.between = 0;
    }
}

pub fn unconfuse(world: &mut DaemonWorld) {
    world.player_flags &= !ISHUH;
    world.markers.push("msg_unconfuse".to_string());
}

pub fn unsee(world: &mut DaemonWorld) {
    for _ in 0..world.visible_invisible {
        world.markers.push("restore_invisible".to_string());
    }
    world.player_flags &= !CANSEE;
}

pub fn sight(world: &mut DaemonWorld) {
    if world.player_flags & ISBLIND != 0 {
        extinguish(world, "sight");
        world.player_flags &= !ISBLIND;
        if !world.proom_gone {
            world.markers.push("enter_room".to_string());
        }
        world.markers.push("msg_sight".to_string());
    }
}

pub fn nohaste(world: &mut DaemonWorld) {
    world.player_flags &= !ISHASTE;
    world.markers.push("msg_nohaste".to_string());
}

pub fn land(world: &mut DaemonWorld) {
    world.player_flags &= !ISLEVIT;
    world.markers.push("msg_land".to_string());
}

pub fn stomach(world: &mut DaemonWorld) {
    let original_hungry = world.hungry_state;
    if world.food_left <= 0 {
        if world.food_left < -STARVETIME {
            world.markers.push("death:s".to_string());
        }
        world.food_left -= 1;
        if world.no_command != 0 || world.rng.rnd(5) != 0 {
            return;
        }
        let faint = world.rng.rnd(8) + 4;
        world.trace.insert("faint_roll".to_string(), json!(faint));
        world.no_command += faint;
        world.hungry_state = 3;
        world.markers.push("msg_faint".to_string());
    } else {
        let oldfood = world.food_left;
        let left_ring = world.left_ring.clone();
        let right_ring = world.right_ring.clone();
        world.food_left -=
            ring_eat(world, left_ring.as_ref()) + ring_eat(world, right_ring.as_ref()) + 1
                - world.amulet;
        if world.food_left < MORETIME && oldfood >= MORETIME {
            world.hungry_state = 2;
            world.markers.push("msg_weak".to_string());
        } else if world.food_left < 2 * MORETIME && oldfood >= 2 * MORETIME {
            world.hungry_state = 1;
            world.markers.push("msg_hungry".to_string());
        }
    }
    if world.hungry_state != original_hungry {
        world.player_flags &= !ISRUN;
        world.running = false;
        world.to_death = false;
        world.count = 0;
    }
}

pub fn start_daemon(world: &mut DaemonWorld, action: &'static str, arg: i32, action_type: i32) {
    let index = d_slot(world);
    world.actions[index].action_type = action_type;
    world.actions[index].action = action;
    world.actions[index].arg = arg;
    world.actions[index].time = DAEMON;
}

pub fn kill_daemon(world: &mut DaemonWorld, action: &'static str) {
    if let Some(index) = find_slot(world, action) {
        world.actions[index].action_type = EMPTY;
    }
}

pub fn do_daemons(world: &mut DaemonWorld, flag: i32) {
    let actions = world.actions.clone();
    for action in actions {
        if action.action_type == flag && action.time == DAEMON {
            run_action(world, action.action);
        }
    }
}

pub fn fuse(world: &mut DaemonWorld, action: &'static str, arg: i32, time: i32, action_type: i32) {
    let index = d_slot(world);
    world.actions[index].action_type = action_type;
    world.actions[index].action = action;
    world.actions[index].arg = arg;
    world.actions[index].time = time;
}

pub fn lengthen(world: &mut DaemonWorld, action: &'static str, xtime: i32) {
    if let Some(index) = find_slot(world, action) {
        world.actions[index].time += xtime;
    }
}

pub fn extinguish(world: &mut DaemonWorld, action: &'static str) {
    if let Some(index) = find_slot(world, action) {
        world.actions[index].action_type = EMPTY;
    }
}

pub fn do_fuses(world: &mut DaemonWorld, flag: i32) {
    let len = world.actions.len();
    for index in 0..len {
        if world.actions[index].action_type == flag && world.actions[index].time > 0 {
            world.actions[index].time -= 1;
            if world.actions[index].time == 0 {
                let action = world.actions[index].action;
                world.actions[index].action_type = EMPTY;
                run_action(world, action);
            }
        }
    }
}

fn ring_eat(world: &mut DaemonWorld, ring: Option<&SourceRing>) -> i32 {
    let uses = [1, 1, 1, -3, -5, 0, 0, -3, -3, 2, -2, 0, 1, 1];
    let Some(ring) = ring else {
        return 0;
    };
    let mut eat = uses[ring.which as usize];
    if eat < 0 {
        eat = if world.rng.rnd(-eat) == 0 { 1 } else { 0 };
    }
    if ring.which == R_DIGEST {
        eat = -eat;
    }
    eat
}

fn run_action(world: &mut DaemonWorld, action: &'static str) {
    match action {
        "doctor" => doctor(world),
        "stomach" => stomach(world),
        "swander" => swander(world),
        "rollwand" => rollwand(world),
        "sight" => sight(world),
        "unconfuse" => unconfuse(world),
        "unsee" => unsee(world),
        "nohaste" => nohaste(world),
        "land" => land(world),
        other => world.markers.push(format!("run:{}", other)),
    }
}

fn d_slot(world: &DaemonWorld) -> usize {
    world
        .actions
        .iter()
        .position(|action| action.action_type == EMPTY)
        .unwrap()
}

fn find_slot(world: &DaemonWorld, action: &'static str) -> Option<usize> {
    world
        .actions
        .iter()
        .position(|slot| slot.action_type != EMPTY && slot.action == action)
}

fn wandertime(world: &mut DaemonWorld) -> i32 {
    70 - 70 / 20 + world.rng.rnd(70 / 10)
}

fn is_ring(ring: &Option<SourceRing>, which: i32) -> bool {
    ring.as_ref().is_some_and(|ring| ring.which == which)
}

fn run_case(case: Case) -> Value {
    let mut world = world_for(&case);
    for action in &case.setup_actions {
        match action.op {
            SetupOp::Start => {
                start_daemon(&mut world, action.action, action.arg, action.action_type)
            }
            SetupOp::Fuse => fuse(
                &mut world,
                action.action,
                action.arg,
                action.time,
                action.action_type,
            ),
            SetupOp::Lengthen => lengthen(&mut world, action.action, action.time),
            SetupOp::Extinguish => extinguish(&mut world, action.action),
        }
    }
    match case.op {
        CaseOp::Doctor => doctor(&mut world),
        CaseOp::Stomach => stomach(&mut world),
        CaseOp::Swander => swander(&mut world),
        CaseOp::Rollwand => rollwand(&mut world),
        CaseOp::DoDaemons => do_daemons(&mut world, case.flag),
        CaseOp::DoFuses => do_fuses(&mut world, case.flag),
        CaseOp::Unconfuse => unconfuse(&mut world),
        CaseOp::Unsee => unsee(&mut world),
        CaseOp::Sight => sight(&mut world),
        CaseOp::Nohaste => nohaste(&mut world),
        CaseOp::Land => land(&mut world),
    }
    json!({"name": case.name, "seed": case.seed, "world": world_json(&world)})
}

#[derive(Clone, Copy)]
enum CaseOp {
    Doctor,
    Stomach,
    Swander,
    Rollwand,
    DoDaemons,
    DoFuses,
    Unconfuse,
    Unsee,
    Sight,
    Nohaste,
    Land,
}

#[derive(Clone, Copy)]
enum SetupOp {
    Start,
    Fuse,
    Lengthen,
    Extinguish,
}

#[derive(Clone)]
struct SetupAction {
    op: SetupOp,
    action: &'static str,
    action_type: i32,
    arg: i32,
    time: i32,
}

#[derive(Clone)]
struct Case {
    name: &'static str,
    seed: i32,
    op: CaseOp,
    flag: i32,
    level: i32,
    hp: i32,
    max_hp: i32,
    quiet: i32,
    player_flags: i32,
    left_ring: Option<SourceRing>,
    right_ring: Option<SourceRing>,
    food_left: i32,
    hungry_state: i32,
    no_command: i32,
    amulet: i32,
    running: bool,
    to_death: bool,
    count: i32,
    proom_gone: bool,
    visible_invisible: i32,
    between: i32,
    setup_actions: Vec<SetupAction>,
}

fn base_case(name: &'static str, seed: i32, op: CaseOp) -> Case {
    Case {
        name,
        seed,
        op,
        flag: 0,
        level: 5,
        hp: 10,
        max_hp: 20,
        quiet: 0,
        player_flags: ISRUN,
        left_ring: None,
        right_ring: None,
        food_left: 1300,
        hungry_state: 0,
        no_command: 0,
        amulet: 0,
        running: true,
        to_death: true,
        count: 3,
        proom_gone: false,
        visible_invisible: 0,
        between: 0,
        setup_actions: Vec::new(),
    }
}

impl Case {
    fn level(mut self, level: i32, hp: i32, max_hp: i32) -> Self {
        self.level = level;
        self.hp = hp;
        self.max_hp = max_hp;
        self
    }
    fn quiet(mut self, quiet: i32) -> Self {
        self.quiet = quiet;
        self
    }
    fn player_flags(mut self, flags: i32) -> Self {
        self.player_flags = flags;
        self
    }
    fn left_ring(mut self, which: i32) -> Self {
        self.left_ring = Some(SourceRing { which });
        self
    }
    fn right_ring(mut self, which: i32) -> Self {
        self.right_ring = Some(SourceRing { which });
        self
    }
    fn food_left(mut self, food_left: i32) -> Self {
        self.food_left = food_left;
        self
    }
    fn hungry_state(mut self, hungry_state: i32) -> Self {
        self.hungry_state = hungry_state;
        self
    }
    fn no_command(mut self, no_command: i32) -> Self {
        self.no_command = no_command;
        self
    }
    fn running_state(mut self, running: bool, to_death: bool, count: i32) -> Self {
        self.running = running;
        self.to_death = to_death;
        self.count = count;
        self
    }
    fn visible_invisible(mut self, count: i32) -> Self {
        self.visible_invisible = count;
        self
    }
    fn between(mut self, between: i32) -> Self {
        self.between = between;
        self
    }
    fn flag(mut self, flag: i32) -> Self {
        self.flag = flag;
        self
    }
    fn setup(mut self, action: SetupAction) -> Self {
        self.setup_actions.push(action);
        self
    }
}

fn cases() -> Vec<Case> {
    vec![
        base_case("doctor_low_level_waits", 1, CaseOp::Doctor)
            .level(3, 10, 20)
            .quiet(13),
        base_case("doctor_low_level_heals", 1, CaseOp::Doctor)
            .level(3, 10, 20)
            .quiet(14),
        base_case("doctor_high_regen_caps", 7, CaseOp::Doctor)
            .level(10, 19, 20)
            .quiet(2)
            .left_ring(R_REGEN)
            .right_ring(R_REGEN),
        base_case("stomach_gets_hungry", 1, CaseOp::Stomach)
            .food_left(300)
            .left_ring(R_REGEN),
        base_case("stomach_gets_weak", 1, CaseOp::Stomach).food_left(150),
        base_case("stomach_faints", 1, CaseOp::Stomach)
            .food_left(0)
            .hungry_state(2)
            .player_flags(ISRUN)
            .running_state(true, true, 3),
        base_case("stomach_starves", 1, CaseOp::Stomach)
            .food_left(-851)
            .no_command(1),
        base_case("swander_starts_rollwand", 1, CaseOp::Swander),
        base_case("rollwand_wanderer", 17, CaseOp::Rollwand)
            .between(3)
            .setup(setup_start("rollwand", BEFORE)),
        base_case("do_daemons_runs_doctor", 1, CaseOp::DoDaemons)
            .flag(AFTER)
            .level(3, 10, 20)
            .quiet(14)
            .setup(setup_start("doctor", AFTER)),
        base_case("do_fuses_runs_sight", 1, CaseOp::DoFuses)
            .flag(AFTER)
            .player_flags(ISRUN | ISBLIND)
            .setup(setup_fuse("sight", AFTER, 1)),
        base_case("lengthen_fuse_waits", 1, CaseOp::DoFuses)
            .flag(AFTER)
            .player_flags(ISRUN | ISBLIND)
            .setup(setup_fuse("sight", AFTER, 1))
            .setup(setup_lengthen("sight", 2)),
        base_case("extinguish_fuse_removes", 1, CaseOp::DoFuses)
            .flag(AFTER)
            .player_flags(ISRUN | ISBLIND)
            .setup(setup_fuse("sight", AFTER, 1))
            .setup(setup_extinguish("sight")),
        base_case("unconfuse_clears_flag", 1, CaseOp::Unconfuse).player_flags(ISRUN | ISHUH),
        base_case("unsee_restores_invisible", 1, CaseOp::Unsee)
            .player_flags(ISRUN | CANSEE)
            .visible_invisible(2),
        base_case("sight_clears_blind", 1, CaseOp::Sight)
            .player_flags(ISRUN | ISBLIND)
            .setup(setup_fuse("sight", AFTER, 5)),
        base_case("nohaste_clears_haste", 1, CaseOp::Nohaste).player_flags(ISRUN | ISHASTE),
        base_case("land_clears_levitation", 1, CaseOp::Land).player_flags(ISRUN | ISLEVIT),
    ]
}

fn setup_start(action: &'static str, action_type: i32) -> SetupAction {
    SetupAction {
        op: SetupOp::Start,
        action,
        action_type,
        arg: 0,
        time: 0,
    }
}

fn setup_fuse(action: &'static str, action_type: i32, time: i32) -> SetupAction {
    SetupAction {
        op: SetupOp::Fuse,
        action,
        action_type,
        arg: 0,
        time,
    }
}

fn setup_lengthen(action: &'static str, time: i32) -> SetupAction {
    SetupAction {
        op: SetupOp::Lengthen,
        action,
        action_type: 0,
        arg: 0,
        time,
    }
}

fn setup_extinguish(action: &'static str) -> SetupAction {
    SetupAction {
        op: SetupOp::Extinguish,
        action,
        action_type: 0,
        arg: 0,
        time: 0,
    }
}

fn world_for(case: &Case) -> DaemonWorld {
    DaemonWorld {
        rng: RogueRng::new(case.seed),
        stats: SourceStats {
            level: case.level,
            hp: case.hp,
        },
        max_hp: case.max_hp,
        quiet: case.quiet,
        player_flags: case.player_flags,
        left_ring: case.left_ring.clone(),
        right_ring: case.right_ring.clone(),
        food_left: case.food_left,
        hungry_state: case.hungry_state,
        no_command: case.no_command,
        amulet: case.amulet,
        running: case.running,
        to_death: case.to_death,
        count: case.count,
        proom_gone: case.proom_gone,
        visible_invisible: case.visible_invisible,
        between: case.between,
        actions: vec![
            DelayedAction {
                action: "",
                action_type: EMPTY,
                arg: 0,
                time: 0
            };
            MAXDAEMONS
        ],
        markers: Vec::new(),
        trace: serde_json::Map::new(),
    }
}

fn action_json(action: &DelayedAction) -> Value {
    json!({"action": action.action, "type": action.action_type, "arg": action.arg, "time": action.time})
}

pub fn world_json(world: &DaemonWorld) -> Value {
    json!({
        "rng_seed": world.rng.seed,
        "stats": {"level": world.stats.level, "hp": world.stats.hp},
        "max_hp": world.max_hp,
        "quiet": world.quiet,
        "player_flags": world.player_flags,
        "food_left": world.food_left,
        "hungry_state": world.hungry_state,
        "no_command": world.no_command,
        "running": world.running,
        "to_death": world.to_death,
        "count": world.count,
        "between": world.between,
        "actions": world.actions.iter().filter(|action| action.action_type != EMPTY).map(action_json).collect::<Vec<_>>(),
        "markers": world.markers,
        "trace": world.trace,
    })
}
