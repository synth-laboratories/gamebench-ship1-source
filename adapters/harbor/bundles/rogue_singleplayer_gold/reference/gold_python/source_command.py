"""Source-faithful Rogue command dispatch slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ESCAPE = "\x1b"
CTRL_B = "\x02"
CTRL_H = "\x08"
CTRL_J = "\x0a"
CTRL_K = "\x0b"
CTRL_L = "\x0c"
CTRL_N = "\x0e"
CTRL_P = "\x10"
CTRL_R = "\x12"
CTRL_U = "\x15"
CTRL_Y = "\x19"

DIRECTION_DELTAS = {
    "h": (0, -1),
    "j": (1, 0),
    "k": (-1, 0),
    "l": (0, 1),
    "y": (-1, -1),
    "u": (-1, 1),
    "b": (1, -1),
    "n": (1, 1),
}

RUN_COMMANDS = {
    "H": "h",
    "J": "j",
    "K": "k",
    "L": "l",
    "Y": "y",
    "U": "u",
    "B": "b",
    "N": "n",
}

CTRL_RUN_COMMANDS = {
    CTRL_H: "H",
    CTRL_J: "J",
    CTRL_K: "K",
    CTRL_L: "L",
    CTRL_Y: "Y",
    CTRL_U: "U",
    CTRL_B: "B",
    CTRL_N: "N",
}

REPEATABLE_COMMANDS = {
    CTRL_B,
    CTRL_H,
    CTRL_J,
    CTRL_K,
    CTRL_L,
    CTRL_N,
    CTRL_U,
    CTRL_Y,
    ".",
    "a",
    "b",
    "h",
    "j",
    "k",
    "l",
    "m",
    "n",
    "q",
    "r",
    "s",
    "t",
    "u",
    "y",
    "z",
    "B",
    "C",
    "H",
    "I",
    "J",
    "K",
    "L",
    "N",
    "U",
    "Y",
}

TRACKED_REPEAT_COMMANDS = [
    CTRL_B,
    CTRL_H,
    CTRL_J,
    CTRL_K,
    CTRL_L,
    CTRL_N,
    CTRL_U,
    CTRL_Y,
    ".",
    ",",
    "a",
    "d",
    "h",
    "i",
    "m",
    "q",
    "r",
    "s",
    "t",
    "z",
    ">",
    "B",
    "C",
    "H",
    "I",
    "N",
    ESCAPE,
]

ITEM_ACTIONS = {
    "q": "quaff",
    "d": "drop",
    "r": "read_scroll",
    "e": "eat",
    "w": "wield",
    "W": "wear",
    "T": "take_off",
    "P": "ring_on",
    "R": "ring_off",
}

NO_TURN_ACTIONS = {
    "!": "shell",
    "Q": "quit",
    "i": "inventory",
    "I": "picky_inventory",
    "o": "option",
    "c": "call",
    ">": "down_level",
    "<": "up_level",
    "?": "help",
    "/": "identify",
    "D": "discovered",
    CTRL_P: "huh",
    CTRL_R: "redraw",
    "v": "version",
    "S": "save_game",
    "@": "status",
}

CURRENT_ACTIONS = {
    ")": "current_weapon",
    "]": "current_armor",
    "=": "current_rings",
}


@dataclass
class CommandState:
    running: bool = False
    count: int = 0
    countch: str = ""
    direction: str = ""
    runch: str = ""
    door_stop: bool = False
    firstmove: bool = False
    move_on: bool = False
    after: bool = True
    again: bool = False
    to_death: bool = False
    kamikaze: bool = False
    q_comm: bool = False
    no_command: int = 0
    last_comm: str = ""
    last_dir: str = ""
    last_pick: str = ""
    l_last_comm: str = ""
    l_last_dir: str = ""
    l_last_pick: str = ""
    player_blind: bool = False
    get_dir_success: bool = True
    dir_ch: str = "h"
    item_here: bool = False
    levitating: bool = False
    monster_visible: bool = False
    diag_ok: bool = True
    take: str = ""
    markers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "count": self.count,
            "countch": _label(self.countch),
            "direction": _label(self.direction),
            "runch": _label(self.runch),
            "door_stop": self.door_stop,
            "firstmove": self.firstmove,
            "move_on": self.move_on,
            "after": self.after,
            "again": self.again,
            "to_death": self.to_death,
            "kamikaze": self.kamikaze,
            "q_comm": self.q_comm,
            "no_command": self.no_command,
            "last_comm": _label(self.last_comm),
            "last_dir": _label(self.last_dir),
            "last_pick": self.last_pick,
            "l_last_comm": _label(self.l_last_comm),
            "l_last_dir": _label(self.l_last_dir),
            "l_last_pick": self.l_last_pick,
            "take": _label(self.take),
            "markers": self.markers[:],
        }


@dataclass
class CommandCase:
    name: str
    chars: list[str]
    state: CommandState = field(default_factory=CommandState)


def source_command_report() -> dict[str, Any]:
    return {
        "schema": "gamebench.rogue.source_command.v1",
        "repeatable": [
            {"command": _label(ch), "repeatable": ch in REPEATABLE_COMMANDS}
            for ch in TRACKED_REPEAT_COMMANDS
        ],
        "cases": [_run_case(case) for case in _cases()],
    }


def runtime_command_projection(
    action: str,
    *,
    running: bool = False,
    count: int = 0,
    last_comm: str = "",
    direction: str = "",
    item_here: bool = False,
    no_command: int = 0,
    dir_ch: str = "h",
    get_dir_success: bool = True,
) -> dict[str, Any]:
    state = CommandState(
        running=running,
        count=count,
        last_comm=last_comm[:1],
        direction=direction[:1],
        item_here=item_here,
        no_command=no_command,
        dir_ch=dir_ch[:1] if dir_ch else "h",
        get_dir_success=get_dir_success,
    )
    initial = state.to_dict()
    apply_command(list(action) if action else ["."], state)
    final = state.to_dict()
    command = _effective_command(action)
    return {
        "schema": "gamebench.rogue.command_dispatch.v1",
        "input": action,
        "command": _label(command),
        "known": _is_known_command(command),
        "repeatable": command in REPEATABLE_COMMANDS,
        "initial": initial,
        "final": final,
    }


def apply_command(chars: list[str], state: CommandState) -> CommandState:
    state.after = True
    state.take = ""
    state.markers.append("do_daemons_before")
    state.markers.append("do_fuses_before")
    if state.no_command:
        state.no_command -= 1
        state.markers.append("no_command_wait")
        if state.no_command == 0:
            state.markers.append("you_can_move_again")
        _finish_command(state)
        return state

    index = 0
    ch = chars[index] if chars else "."
    index += 1
    newcount = False
    if ch.isdigit():
        state.count = 0
        newcount = True
        while ch.isdigit():
            state.count = state.count * 10 + ord(ch) - ord("0")
            if state.count > 255:
                state.count = 255
            ch = chars[index] if index < len(chars) else "."
            index += 1
        state.countch = ch
        if ch not in REPEATABLE_COMMANDS:
            state.count = 0
    if state.count and not state.running:
        state.count -= 1
    if ch != "a" and ch != ESCAPE and not (state.running or state.count or state.to_death):
        state.l_last_comm = state.last_comm
        state.l_last_dir = state.last_dir
        state.l_last_pick = state.last_pick
        state.last_comm = ch
        state.last_dir = ""
        state.last_pick = ""
    _dispatch(ch, state, newcount)
    _finish_command(state)
    return state


def _dispatch(ch: str, state: CommandState, newcount: bool) -> None:
    while True:
        if ch == ",":
            if state.item_here:
                if state.levitating:
                    state.markers.append("levit_check")
                else:
                    state.markers.append("pick_up")
            else:
                state.markers.append("nothing_here")
            return
        if ch in DIRECTION_DELTAS:
            dy, dx = DIRECTION_DELTAS[ch]
            state.markers.append(f"do_move:{ch}:{dy}:{dx}")
            return
        if ch in RUN_COMMANDS:
            state.running = True
            state.runch = RUN_COMMANDS[ch]
            state.markers.append(f"do_run:{RUN_COMMANDS[ch]}")
            return
        if ch in CTRL_RUN_COMMANDS:
            if not state.player_blind:
                state.door_stop = True
                state.firstmove = True
            if state.count and not newcount:
                ch = state.direction
            else:
                ch = CTRL_RUN_COMMANDS[ch]
                state.direction = ch
            continue
        if ch == "F":
            state.kamikaze = True
            ch = "f"
            continue
        if ch == "f":
            if not state.get_dir_success:
                state.after = False
                state.markers.append("fight_no_direction")
                return
            if not state.monster_visible:
                state.after = False
                state.markers.append("no_monster_there")
                return
            if state.diag_ok:
                state.to_death = True
                state.runch = state.dir_ch
                state.markers.append("fight_to_death")
                ch = state.dir_ch
                continue
            state.markers.append("fight_bad_diagonal")
            return
        if ch == "t":
            if state.get_dir_success:
                state.markers.append(f"missile:{state.dir_ch}")
            else:
                state.after = False
                state.markers.append("throw_no_direction")
            return
        if ch == "a":
            if not state.last_comm:
                state.after = False
                state.markers.append("again_empty")
                return
            state.again = True
            state.markers.append(f"again:{_label(state.last_comm)}")
            ch = state.last_comm
            continue
        if ch in ITEM_ACTIONS:
            state.markers.append(ITEM_ACTIONS[ch])
            return
        if ch in NO_TURN_ACTIONS:
            if ch == "Q":
                state.q_comm = True
            state.after = False
            state.markers.append(NO_TURN_ACTIONS[ch])
            if ch == "Q":
                state.q_comm = False
            return
        if ch == "s":
            state.markers.append("search")
            return
        if ch == "z":
            if state.get_dir_success:
                state.markers.append(f"do_zap:{state.dir_ch}")
            else:
                state.after = False
                state.markers.append("zap_no_direction")
            return
        if ch == ".":
            state.markers.append("rest")
            return
        if ch == " ":
            state.after = False
            state.markers.append("legal_illegal")
            return
        if ch == "^":
            state.after = False
            if state.get_dir_success:
                state.markers.append(f"identify_trap:{state.dir_ch}")
            else:
                state.markers.append("identify_trap_no_direction")
            return
        if ch == ESCAPE:
            state.door_stop = False
            state.count = 0
            state.after = False
            state.again = False
            state.markers.append("escape")
            return
        if ch == "m":
            state.move_on = True
            if not state.get_dir_success:
                state.after = False
                state.markers.append("move_on_no_direction")
                return
            ch = state.dir_ch
            state.countch = state.dir_ch
            continue
        if ch in CURRENT_ACTIONS:
            state.markers.append(CURRENT_ACTIONS[ch])
            return
        state.after = False
        state.count = 0
        state.markers.append(f"illegal:{_label(ch)}")
        return


def _finish_command(state: CommandState) -> None:
    if state.take:
        state.markers.append(f"pick_up_take:{_label(state.take)}")
    if not state.running:
        state.door_stop = False
    state.markers.append("refund_ntimes" if not state.after else "consume_turn")
    state.markers.append("do_daemons_after")
    state.markers.append("do_fuses_after")


def _run_case(case: CommandCase) -> dict[str, Any]:
    initial = case.state.to_dict()
    final = apply_command(case.chars[:], case.state).to_dict()
    return {
        "name": case.name,
        "input": [_label(ch) for ch in case.chars],
        "initial": initial,
        "final": final,
    }


def _cases() -> list[CommandCase]:
    return [
        CommandCase("count_caps_repeatable_move", list("300h")),
        CommandCase("count_clears_nonrepeatable_inventory", list("12i")),
        CommandCase("plain_move", ["l"]),
        CommandCase("uppercase_run", ["N"]),
        CommandCase("control_run_sets_door_stop", [CTRL_H]),
        CommandCase(
            "continued_count_reuses_direction",
            [CTRL_H],
            CommandState(count=3, direction="J"),
        ),
        CommandCase("pickup_nothing", [","], CommandState(item_here=False)),
        CommandCase("pickup_item", [","], CommandState(item_here=True)),
        CommandCase("fight_no_direction", ["f"], CommandState(get_dir_success=False)),
        CommandCase(
            "fight_visible_target",
            ["f"],
            CommandState(get_dir_success=True, dir_ch="u", monster_visible=True),
        ),
        CommandCase("fight_no_monster", ["f"], CommandState(get_dir_success=True, monster_visible=False)),
        CommandCase("kamikaze_visible_target", ["F"], CommandState(dir_ch="y", monster_visible=True)),
        CommandCase("throw_no_direction", ["t"], CommandState(get_dir_success=False)),
        CommandCase("throw_with_direction", ["t"], CommandState(get_dir_success=True, dir_ch="n")),
        CommandCase("again_empty", ["a"]),
        CommandCase("again_replays_quaff", ["a"], CommandState(last_comm="q")),
        CommandCase("zap_no_direction", ["z"], CommandState(get_dir_success=False)),
        CommandCase("zap_with_direction", ["z"], CommandState(get_dir_success=True, dir_ch="k")),
        CommandCase("move_on_with_direction", ["m"], CommandState(get_dir_success=True, dir_ch="h")),
        CommandCase("move_on_no_direction", ["m"], CommandState(get_dir_success=False)),
        CommandCase("inventory_no_turn", ["i"]),
        CommandCase("descend_no_turn", [">"]),
        CommandCase("search_consumes_turn", ["s"]),
        CommandCase("rest_consumes_turn", ["."]),
        CommandCase("space_refunds_turn", [" "]),
        CommandCase("escape_resets_count", [ESCAPE], CommandState(count=9, door_stop=True, again=True)),
        CommandCase("current_weapon_consumes_turn", [")"]),
        CommandCase("illegal_command", ["x"], CommandState(count=4)),
        CommandCase("no_command_wait_finishes", [], CommandState(no_command=1)),
        CommandCase("read_scroll_item_dispatch", ["r"]),
        CommandCase("ring_on_item_dispatch", ["P"]),
        CommandCase("save_no_turn", ["S"]),
        CommandCase("trap_identify_with_direction", ["^"], CommandState(get_dir_success=True, dir_ch="j")),
    ]


def _label(ch: str) -> str:
    if not ch:
        return ""
    labels = {
        ESCAPE: "ESCAPE",
        CTRL_B: "CTRL_B",
        CTRL_H: "CTRL_H",
        CTRL_J: "CTRL_J",
        CTRL_K: "CTRL_K",
        CTRL_L: "CTRL_L",
        CTRL_N: "CTRL_N",
        CTRL_P: "CTRL_P",
        CTRL_R: "CTRL_R",
        CTRL_U: "CTRL_U",
        CTRL_Y: "CTRL_Y",
        " ": "SPACE",
    }
    return labels.get(ch, ch)


def _effective_command(action: str) -> str:
    if not action:
        return "."
    index = 0
    while index < len(action) and action[index].isdigit():
        index += 1
    return action[index] if index < len(action) else "."


def _is_known_command(ch: str) -> bool:
    return (
        ch in DIRECTION_DELTAS
        or ch in RUN_COMMANDS
        or ch in CTRL_RUN_COMMANDS
        or ch in ITEM_ACTIONS
        or ch in NO_TURN_ACTIONS
        or ch in CURRENT_ACTIONS
        or ch in {",", "F", "f", "t", "a", "s", "z", ".", " ", "^", ESCAPE, "m"}
    )
