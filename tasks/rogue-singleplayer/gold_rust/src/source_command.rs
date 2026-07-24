use serde_json::{json, Value};

const ESCAPE: char = '\x1b';
const CTRL_B: char = '\x02';
const CTRL_H: char = '\x08';
const CTRL_J: char = '\x0a';
const CTRL_K: char = '\x0b';
const CTRL_L: char = '\x0c';
const CTRL_N: char = '\x0e';
const CTRL_P: char = '\x10';
const CTRL_R: char = '\x12';
const CTRL_U: char = '\x15';
const CTRL_Y: char = '\x19';

#[derive(Clone)]
struct CommandState {
    running: bool,
    count: i32,
    countch: char,
    direction: char,
    runch: char,
    door_stop: bool,
    firstmove: bool,
    move_on: bool,
    after: bool,
    again: bool,
    to_death: bool,
    kamikaze: bool,
    q_comm: bool,
    no_command: i32,
    last_comm: char,
    last_dir: char,
    last_pick: String,
    l_last_comm: char,
    l_last_dir: char,
    l_last_pick: String,
    player_blind: bool,
    get_dir_success: bool,
    dir_ch: char,
    item_here: bool,
    levitating: bool,
    monster_visible: bool,
    diag_ok: bool,
    take: char,
    markers: Vec<String>,
}

#[derive(Clone)]
struct CommandCase {
    name: &'static str,
    chars: Vec<char>,
    state: CommandState,
}

impl Default for CommandState {
    fn default() -> Self {
        Self {
            running: false,
            count: 0,
            countch: '\0',
            direction: '\0',
            runch: '\0',
            door_stop: false,
            firstmove: false,
            move_on: false,
            after: true,
            again: false,
            to_death: false,
            kamikaze: false,
            q_comm: false,
            no_command: 0,
            last_comm: '\0',
            last_dir: '\0',
            last_pick: String::new(),
            l_last_comm: '\0',
            l_last_dir: '\0',
            l_last_pick: String::new(),
            player_blind: false,
            get_dir_success: true,
            dir_ch: 'h',
            item_here: false,
            levitating: false,
            monster_visible: false,
            diag_ok: true,
            take: '\0',
            markers: Vec::new(),
        }
    }
}

impl CommandState {
    fn to_json(&self) -> Value {
        json!({
            "running": self.running,
            "count": self.count,
            "countch": label(self.countch),
            "direction": label(self.direction),
            "runch": label(self.runch),
            "door_stop": self.door_stop,
            "firstmove": self.firstmove,
            "move_on": self.move_on,
            "after": self.after,
            "again": self.again,
            "to_death": self.to_death,
            "kamikaze": self.kamikaze,
            "q_comm": self.q_comm,
            "no_command": self.no_command,
            "last_comm": label(self.last_comm),
            "last_dir": label(self.last_dir),
            "last_pick": self.last_pick,
            "l_last_comm": label(self.l_last_comm),
            "l_last_dir": label(self.l_last_dir),
            "l_last_pick": self.l_last_pick,
            "take": label(self.take),
            "markers": self.markers,
        })
    }
}

pub fn source_command_report() -> Value {
    json!({
        "schema": "gamebench.rogue.source_command.v1",
        "repeatable": tracked_repeat_commands()
            .into_iter()
            .map(|ch| json!({"command": label(ch), "repeatable": is_repeatable(ch)}))
            .collect::<Vec<_>>(),
        "cases": cases().into_iter().map(run_case).collect::<Vec<_>>(),
    })
}

pub fn runtime_command_projection(
    action: &str,
    running: bool,
    count: i32,
    last_comm: char,
    direction: char,
    item_here: bool,
    no_command: i32,
    dir_ch: char,
    get_dir_success: bool,
) -> Value {
    let mut state = CommandState {
        running,
        count,
        last_comm,
        direction,
        item_here,
        no_command,
        dir_ch,
        get_dir_success,
        ..CommandState::default()
    };
    let initial = state.to_json();
    let chars = if action.is_empty() {
        vec!['.']
    } else {
        action.chars().collect()
    };
    apply_command(chars, &mut state);
    let command = effective_command(action);
    json!({
        "schema": "gamebench.rogue.command_dispatch.v1",
        "input": action,
        "command": label(command),
        "known": is_known_command(command),
        "repeatable": is_repeatable(command),
        "initial": initial,
        "final": state.to_json(),
    })
}

fn apply_command(chars: Vec<char>, state: &mut CommandState) {
    state.after = true;
    state.take = '\0';
    state.markers.push("do_daemons_before".to_string());
    state.markers.push("do_fuses_before".to_string());
    if state.no_command != 0 {
        state.no_command -= 1;
        state.markers.push("no_command_wait".to_string());
        if state.no_command == 0 {
            state.markers.push("you_can_move_again".to_string());
        }
        finish_command(state);
        return;
    }

    let mut index = 0usize;
    let mut ch = chars.get(index).copied().unwrap_or('.');
    index += 1;
    let mut newcount = false;
    if ch.is_ascii_digit() {
        state.count = 0;
        newcount = true;
        while ch.is_ascii_digit() {
            state.count = state.count * 10 + (ch as i32 - '0' as i32);
            if state.count > 255 {
                state.count = 255;
            }
            ch = chars.get(index).copied().unwrap_or('.');
            index += 1;
        }
        state.countch = ch;
        if !is_repeatable(ch) {
            state.count = 0;
        }
    }
    if state.count != 0 && !state.running {
        state.count -= 1;
    }
    if ch != 'a' && ch != ESCAPE && !(state.running || state.count != 0 || state.to_death) {
        state.l_last_comm = state.last_comm;
        state.l_last_dir = state.last_dir;
        state.l_last_pick = state.last_pick.clone();
        state.last_comm = ch;
        state.last_dir = '\0';
        state.last_pick.clear();
    }
    dispatch(ch, state, newcount);
    finish_command(state);
}

fn dispatch(mut ch: char, state: &mut CommandState, newcount: bool) {
    loop {
        if ch == ',' {
            if state.item_here {
                if state.levitating {
                    state.markers.push("levit_check".to_string());
                } else {
                    state.markers.push("pick_up".to_string());
                }
            } else {
                state.markers.push("nothing_here".to_string());
            }
            return;
        }
        if let Some((dy, dx)) = direction_delta(ch) {
            state.markers.push(format!("do_move:{ch}:{dy}:{dx}"));
            return;
        }
        if let Some(run_ch) = run_command(ch) {
            state.running = true;
            state.runch = run_ch;
            state.markers.push(format!("do_run:{run_ch}"));
            return;
        }
        if let Some(run_ch) = control_run_command(ch) {
            if !state.player_blind {
                state.door_stop = true;
                state.firstmove = true;
            }
            if state.count != 0 && !newcount {
                ch = state.direction;
            } else {
                ch = run_ch;
                state.direction = ch;
            }
            continue;
        }
        if ch == 'F' {
            state.kamikaze = true;
            ch = 'f';
            continue;
        }
        if ch == 'f' {
            if !state.get_dir_success {
                state.after = false;
                state.markers.push("fight_no_direction".to_string());
                return;
            }
            if !state.monster_visible {
                state.after = false;
                state.markers.push("no_monster_there".to_string());
                return;
            }
            if state.diag_ok {
                state.to_death = true;
                state.runch = state.dir_ch;
                state.markers.push("fight_to_death".to_string());
                ch = state.dir_ch;
                continue;
            }
            state.markers.push("fight_bad_diagonal".to_string());
            return;
        }
        if ch == 't' {
            if state.get_dir_success {
                state.markers.push(format!("missile:{}", state.dir_ch));
            } else {
                state.after = false;
                state.markers.push("throw_no_direction".to_string());
            }
            return;
        }
        if ch == 'a' {
            if state.last_comm == '\0' {
                state.after = false;
                state.markers.push("again_empty".to_string());
                return;
            }
            state.again = true;
            state
                .markers
                .push(format!("again:{}", label(state.last_comm)));
            ch = state.last_comm;
            continue;
        }
        if let Some(action) = item_action(ch) {
            state.markers.push(action.to_string());
            return;
        }
        if let Some(action) = no_turn_action(ch) {
            if ch == 'Q' {
                state.q_comm = true;
            }
            state.after = false;
            state.markers.push(action.to_string());
            if ch == 'Q' {
                state.q_comm = false;
            }
            return;
        }
        if ch == 's' {
            state.markers.push("search".to_string());
            return;
        }
        if ch == 'z' {
            if state.get_dir_success {
                state.markers.push(format!("do_zap:{}", state.dir_ch));
            } else {
                state.after = false;
                state.markers.push("zap_no_direction".to_string());
            }
            return;
        }
        if ch == '.' {
            state.markers.push("rest".to_string());
            return;
        }
        if ch == ' ' {
            state.after = false;
            state.markers.push("legal_illegal".to_string());
            return;
        }
        if ch == '^' {
            state.after = false;
            if state.get_dir_success {
                state
                    .markers
                    .push(format!("identify_trap:{}", state.dir_ch));
            } else {
                state.markers.push("identify_trap_no_direction".to_string());
            }
            return;
        }
        if ch == ESCAPE {
            state.door_stop = false;
            state.count = 0;
            state.after = false;
            state.again = false;
            state.markers.push("escape".to_string());
            return;
        }
        if ch == 'm' {
            state.move_on = true;
            if !state.get_dir_success {
                state.after = false;
                state.markers.push("move_on_no_direction".to_string());
                return;
            }
            ch = state.dir_ch;
            state.countch = state.dir_ch;
            continue;
        }
        if let Some(action) = current_action(ch) {
            state.markers.push(action.to_string());
            return;
        }
        state.after = false;
        state.count = 0;
        state.markers.push(format!("illegal:{}", label(ch)));
        return;
    }
}

fn finish_command(state: &mut CommandState) {
    if state.take != '\0' {
        state
            .markers
            .push(format!("pick_up_take:{}", label(state.take)));
    }
    if !state.running {
        state.door_stop = false;
    }
    if state.after {
        state.markers.push("consume_turn".to_string());
    } else {
        state.markers.push("refund_ntimes".to_string());
    }
    state.markers.push("do_daemons_after".to_string());
    state.markers.push("do_fuses_after".to_string());
}

fn run_case(case: CommandCase) -> Value {
    let mut state = case.state.clone();
    let initial = state.to_json();
    apply_command(case.chars.clone(), &mut state);
    json!({
        "name": case.name,
        "input": case.chars.into_iter().map(label).collect::<Vec<_>>(),
        "initial": initial,
        "final": state.to_json(),
    })
}

fn cases() -> Vec<CommandCase> {
    vec![
        case(
            "count_caps_repeatable_move",
            "300h".chars().collect(),
            CommandState::default(),
        ),
        case(
            "count_clears_nonrepeatable_inventory",
            "12i".chars().collect(),
            CommandState::default(),
        ),
        case("plain_move", vec!['l'], CommandState::default()),
        case("uppercase_run", vec!['N'], CommandState::default()),
        case(
            "control_run_sets_door_stop",
            vec![CTRL_H],
            CommandState::default(),
        ),
        case(
            "continued_count_reuses_direction",
            vec![CTRL_H],
            state_with(|s| {
                s.count = 3;
                s.direction = 'J';
            }),
        ),
        case(
            "pickup_nothing",
            vec![','],
            state_with(|s| s.item_here = false),
        ),
        case("pickup_item", vec![','], state_with(|s| s.item_here = true)),
        case(
            "fight_no_direction",
            vec!['f'],
            state_with(|s| s.get_dir_success = false),
        ),
        case(
            "fight_visible_target",
            vec!['f'],
            state_with(|s| {
                s.get_dir_success = true;
                s.dir_ch = 'u';
                s.monster_visible = true;
            }),
        ),
        case(
            "fight_no_monster",
            vec!['f'],
            state_with(|s| {
                s.get_dir_success = true;
                s.monster_visible = false;
            }),
        ),
        case(
            "kamikaze_visible_target",
            vec!['F'],
            state_with(|s| {
                s.dir_ch = 'y';
                s.monster_visible = true;
            }),
        ),
        case(
            "throw_no_direction",
            vec!['t'],
            state_with(|s| s.get_dir_success = false),
        ),
        case(
            "throw_with_direction",
            vec!['t'],
            state_with(|s| {
                s.get_dir_success = true;
                s.dir_ch = 'n';
            }),
        ),
        case("again_empty", vec!['a'], CommandState::default()),
        case(
            "again_replays_quaff",
            vec!['a'],
            state_with(|s| s.last_comm = 'q'),
        ),
        case(
            "zap_no_direction",
            vec!['z'],
            state_with(|s| s.get_dir_success = false),
        ),
        case(
            "zap_with_direction",
            vec!['z'],
            state_with(|s| {
                s.get_dir_success = true;
                s.dir_ch = 'k';
            }),
        ),
        case(
            "move_on_with_direction",
            vec!['m'],
            state_with(|s| {
                s.get_dir_success = true;
                s.dir_ch = 'h';
            }),
        ),
        case(
            "move_on_no_direction",
            vec!['m'],
            state_with(|s| s.get_dir_success = false),
        ),
        case("inventory_no_turn", vec!['i'], CommandState::default()),
        case("descend_no_turn", vec!['>'], CommandState::default()),
        case("search_consumes_turn", vec!['s'], CommandState::default()),
        case("rest_consumes_turn", vec!['.'], CommandState::default()),
        case("space_refunds_turn", vec![' '], CommandState::default()),
        case(
            "escape_resets_count",
            vec![ESCAPE],
            state_with(|s| {
                s.count = 9;
                s.door_stop = true;
                s.again = true;
            }),
        ),
        case(
            "current_weapon_consumes_turn",
            vec![')'],
            CommandState::default(),
        ),
        case("illegal_command", vec!['x'], state_with(|s| s.count = 4)),
        case(
            "no_command_wait_finishes",
            Vec::new(),
            state_with(|s| s.no_command = 1),
        ),
        case(
            "read_scroll_item_dispatch",
            vec!['r'],
            CommandState::default(),
        ),
        case("ring_on_item_dispatch", vec!['P'], CommandState::default()),
        case("save_no_turn", vec!['S'], CommandState::default()),
        case(
            "trap_identify_with_direction",
            vec!['^'],
            state_with(|s| {
                s.get_dir_success = true;
                s.dir_ch = 'j';
            }),
        ),
    ]
}

fn case(name: &'static str, chars: Vec<char>, state: CommandState) -> CommandCase {
    CommandCase { name, chars, state }
}

fn state_with(update: impl FnOnce(&mut CommandState)) -> CommandState {
    let mut state = CommandState::default();
    update(&mut state);
    state
}

fn tracked_repeat_commands() -> Vec<char> {
    vec![
        CTRL_B, CTRL_H, CTRL_J, CTRL_K, CTRL_L, CTRL_N, CTRL_U, CTRL_Y, '.', ',', 'a', 'd', 'h',
        'i', 'm', 'q', 'r', 's', 't', 'z', '>', 'B', 'C', 'H', 'I', 'N', ESCAPE,
    ]
}

fn is_repeatable(ch: char) -> bool {
    matches!(
        ch,
        CTRL_B
            | CTRL_H
            | CTRL_J
            | CTRL_K
            | CTRL_L
            | CTRL_N
            | CTRL_U
            | CTRL_Y
            | '.'
            | 'a'
            | 'b'
            | 'h'
            | 'j'
            | 'k'
            | 'l'
            | 'm'
            | 'n'
            | 'q'
            | 'r'
            | 's'
            | 't'
            | 'u'
            | 'y'
            | 'z'
            | 'B'
            | 'C'
            | 'H'
            | 'I'
            | 'J'
            | 'K'
            | 'L'
            | 'N'
            | 'U'
            | 'Y'
    )
}

fn direction_delta(ch: char) -> Option<(i32, i32)> {
    match ch {
        'h' => Some((0, -1)),
        'j' => Some((1, 0)),
        'k' => Some((-1, 0)),
        'l' => Some((0, 1)),
        'y' => Some((-1, -1)),
        'u' => Some((-1, 1)),
        'b' => Some((1, -1)),
        'n' => Some((1, 1)),
        _ => None,
    }
}

fn run_command(ch: char) -> Option<char> {
    match ch {
        'H' => Some('h'),
        'J' => Some('j'),
        'K' => Some('k'),
        'L' => Some('l'),
        'Y' => Some('y'),
        'U' => Some('u'),
        'B' => Some('b'),
        'N' => Some('n'),
        _ => None,
    }
}

fn control_run_command(ch: char) -> Option<char> {
    match ch {
        CTRL_H => Some('H'),
        CTRL_J => Some('J'),
        CTRL_K => Some('K'),
        CTRL_L => Some('L'),
        CTRL_Y => Some('Y'),
        CTRL_U => Some('U'),
        CTRL_B => Some('B'),
        CTRL_N => Some('N'),
        _ => None,
    }
}

fn item_action(ch: char) -> Option<&'static str> {
    match ch {
        'q' => Some("quaff"),
        'd' => Some("drop"),
        'r' => Some("read_scroll"),
        'e' => Some("eat"),
        'w' => Some("wield"),
        'W' => Some("wear"),
        'T' => Some("take_off"),
        'P' => Some("ring_on"),
        'R' => Some("ring_off"),
        _ => None,
    }
}

fn no_turn_action(ch: char) -> Option<&'static str> {
    match ch {
        '!' => Some("shell"),
        'Q' => Some("quit"),
        'i' => Some("inventory"),
        'I' => Some("picky_inventory"),
        'o' => Some("option"),
        'c' => Some("call"),
        '>' => Some("down_level"),
        '<' => Some("up_level"),
        '?' => Some("help"),
        '/' => Some("identify"),
        'D' => Some("discovered"),
        CTRL_P => Some("huh"),
        CTRL_R => Some("redraw"),
        'v' => Some("version"),
        'S' => Some("save_game"),
        '@' => Some("status"),
        _ => None,
    }
}

fn current_action(ch: char) -> Option<&'static str> {
    match ch {
        ')' => Some("current_weapon"),
        ']' => Some("current_armor"),
        '=' => Some("current_rings"),
        _ => None,
    }
}

fn label(ch: char) -> String {
    match ch {
        '\0' => String::new(),
        ESCAPE => "ESCAPE".to_string(),
        CTRL_B => "CTRL_B".to_string(),
        CTRL_H => "CTRL_H".to_string(),
        CTRL_J => "CTRL_J".to_string(),
        CTRL_K => "CTRL_K".to_string(),
        CTRL_L => "CTRL_L".to_string(),
        CTRL_N => "CTRL_N".to_string(),
        CTRL_P => "CTRL_P".to_string(),
        CTRL_R => "CTRL_R".to_string(),
        CTRL_U => "CTRL_U".to_string(),
        CTRL_Y => "CTRL_Y".to_string(),
        ' ' => "SPACE".to_string(),
        _ => ch.to_string(),
    }
}

fn effective_command(action: &str) -> char {
    let mut chars = action.chars().peekable();
    while matches!(chars.peek(), Some(ch) if ch.is_ascii_digit()) {
        chars.next();
    }
    chars.next().unwrap_or('.')
}

fn is_known_command(ch: char) -> bool {
    direction_delta(ch).is_some()
        || run_command(ch).is_some()
        || control_run_command(ch).is_some()
        || item_action(ch).is_some()
        || no_turn_action(ch).is_some()
        || current_action(ch).is_some()
        || matches!(
            ch,
            ',' | 'F' | 'f' | 't' | 'a' | 's' | 'z' | '.' | ' ' | '^' | ESCAPE | 'm'
        )
}
