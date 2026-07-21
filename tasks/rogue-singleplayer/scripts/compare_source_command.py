#!/usr/bin/env python3
"""Compare source-derived Rogue command dispatch across C, Python, and Rust."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from source_command import source_command_report


C_SOURCE = r'''
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ESCAPE 27
#define CTRL_B 2
#define CTRL_H 8
#define CTRL_J 10
#define CTRL_K 11
#define CTRL_L 12
#define CTRL_N 14
#define CTRL_P 16
#define CTRL_R 18
#define CTRL_U 21
#define CTRL_Y 25

typedef struct command_state {
    int running;
    int count;
    char countch;
    char direction;
    char runch;
    int door_stop;
    int firstmove;
    int move_on;
    int after;
    int again;
    int to_death;
    int kamikaze;
    int q_comm;
    int no_command;
    char last_comm;
    char last_dir;
    char last_pick[16];
    char l_last_comm;
    char l_last_dir;
    char l_last_pick[16];
    int player_blind;
    int get_dir_success;
    char dir_ch;
    int item_here;
    int levitating;
    int monster_visible;
    int diag_ok;
    char take;
    char markers[96][64];
    int marker_count;
} CommandState;

typedef struct command_case {
    const char *name;
    char chars[8];
    int len;
    CommandState state;
} CommandCase;

static void label(char ch, char *out)
{
    switch ((unsigned char) ch)
    {
        case 0: strcpy(out, ""); break;
        case ESCAPE: strcpy(out, "ESCAPE"); break;
        case CTRL_B: strcpy(out, "CTRL_B"); break;
        case CTRL_H: strcpy(out, "CTRL_H"); break;
        case CTRL_J: strcpy(out, "CTRL_J"); break;
        case CTRL_K: strcpy(out, "CTRL_K"); break;
        case CTRL_L: strcpy(out, "CTRL_L"); break;
        case CTRL_N: strcpy(out, "CTRL_N"); break;
        case CTRL_P: strcpy(out, "CTRL_P"); break;
        case CTRL_R: strcpy(out, "CTRL_R"); break;
        case CTRL_U: strcpy(out, "CTRL_U"); break;
        case CTRL_Y: strcpy(out, "CTRL_Y"); break;
        case ' ': strcpy(out, "SPACE"); break;
        default:
            out[0] = ch;
            out[1] = '\0';
            break;
    }
}

static void print_bool(int value)
{
    printf(value ? "true" : "false");
}

static void print_string(const char *value)
{
    putchar('"');
    for (const char *p = value; *p; p++)
    {
        if (*p == '"' || *p == '\\')
            putchar('\\');
        putchar(*p);
    }
    putchar('"');
}

static void push_marker(CommandState *state, const char *marker)
{
    strcpy(state->markers[state->marker_count++], marker);
}

static void push_markerf(CommandState *state, const char *prefix, char ch)
{
    char lab[16];
    label(ch, lab);
    snprintf(state->markers[state->marker_count++], 64, "%s%s", prefix, lab);
}

static CommandState base_state(void)
{
    CommandState state;
    memset(&state, 0, sizeof(state));
    state.after = 1;
    state.get_dir_success = 1;
    state.dir_ch = 'h';
    state.diag_ok = 1;
    return state;
}

static int is_repeatable(char ch)
{
    switch ((unsigned char) ch)
    {
        case CTRL_B: case CTRL_H: case CTRL_J: case CTRL_K:
        case CTRL_L: case CTRL_N: case CTRL_U: case CTRL_Y:
        case '.': case 'a': case 'b': case 'h': case 'j':
        case 'k': case 'l': case 'm': case 'n': case 'q':
        case 'r': case 's': case 't': case 'u': case 'y':
        case 'z': case 'B': case 'C': case 'H': case 'I':
        case 'J': case 'K': case 'L': case 'N': case 'U':
        case 'Y':
            return 1;
        default:
            return 0;
    }
}

static int direction_delta(char ch, int *dy, int *dx)
{
    switch (ch)
    {
        case 'h': *dy = 0; *dx = -1; return 1;
        case 'j': *dy = 1; *dx = 0; return 1;
        case 'k': *dy = -1; *dx = 0; return 1;
        case 'l': *dy = 0; *dx = 1; return 1;
        case 'y': *dy = -1; *dx = -1; return 1;
        case 'u': *dy = -1; *dx = 1; return 1;
        case 'b': *dy = 1; *dx = -1; return 1;
        case 'n': *dy = 1; *dx = 1; return 1;
        default: return 0;
    }
}

static int run_command(char ch, char *run_ch)
{
    switch (ch)
    {
        case 'H': *run_ch = 'h'; return 1;
        case 'J': *run_ch = 'j'; return 1;
        case 'K': *run_ch = 'k'; return 1;
        case 'L': *run_ch = 'l'; return 1;
        case 'Y': *run_ch = 'y'; return 1;
        case 'U': *run_ch = 'u'; return 1;
        case 'B': *run_ch = 'b'; return 1;
        case 'N': *run_ch = 'n'; return 1;
        default: return 0;
    }
}

static int control_run_command(char ch, char *run_ch)
{
    switch ((unsigned char) ch)
    {
        case CTRL_H: *run_ch = 'H'; return 1;
        case CTRL_J: *run_ch = 'J'; return 1;
        case CTRL_K: *run_ch = 'K'; return 1;
        case CTRL_L: *run_ch = 'L'; return 1;
        case CTRL_Y: *run_ch = 'Y'; return 1;
        case CTRL_U: *run_ch = 'U'; return 1;
        case CTRL_B: *run_ch = 'B'; return 1;
        case CTRL_N: *run_ch = 'N'; return 1;
        default: return 0;
    }
}

static const char *item_action(char ch)
{
    switch (ch)
    {
        case 'q': return "quaff";
        case 'd': return "drop";
        case 'r': return "read_scroll";
        case 'e': return "eat";
        case 'w': return "wield";
        case 'W': return "wear";
        case 'T': return "take_off";
        case 'P': return "ring_on";
        case 'R': return "ring_off";
        default: return NULL;
    }
}

static const char *no_turn_action(char ch)
{
    switch ((unsigned char) ch)
    {
        case '!': return "shell";
        case 'Q': return "quit";
        case 'i': return "inventory";
        case 'I': return "picky_inventory";
        case 'o': return "option";
        case 'c': return "call";
        case '>': return "down_level";
        case '<': return "up_level";
        case '?': return "help";
        case '/': return "identify";
        case 'D': return "discovered";
        case CTRL_P: return "huh";
        case CTRL_R: return "redraw";
        case 'v': return "version";
        case 'S': return "save_game";
        case '@': return "status";
        default: return NULL;
    }
}

static const char *current_action(char ch)
{
    switch (ch)
    {
        case ')': return "current_weapon";
        case ']': return "current_armor";
        case '=': return "current_rings";
        default: return NULL;
    }
}

static void finish_command(CommandState *state)
{
    if (state->take)
        push_markerf(state, "pick_up_take:", state->take);
    if (!state->running)
        state->door_stop = 0;
    push_marker(state, state->after ? "consume_turn" : "refund_ntimes");
    push_marker(state, "do_daemons_after");
    push_marker(state, "do_fuses_after");
}

static void dispatch(char ch, CommandState *state, int newcount)
{
    for (;;)
    {
        int dy = 0, dx = 0;
        char run_ch = 0;
        const char *action = NULL;
        if (ch == ',')
        {
            if (state->item_here)
                push_marker(state, state->levitating ? "levit_check" : "pick_up");
            else
                push_marker(state, "nothing_here");
            return;
        }
        if (direction_delta(ch, &dy, &dx))
        {
            snprintf(state->markers[state->marker_count++], 64, "do_move:%c:%d:%d", ch, dy, dx);
            return;
        }
        if (run_command(ch, &run_ch))
        {
            state->running = 1;
            state->runch = run_ch;
            snprintf(state->markers[state->marker_count++], 64, "do_run:%c", run_ch);
            return;
        }
        if (control_run_command(ch, &run_ch))
        {
            if (!state->player_blind)
            {
                state->door_stop = 1;
                state->firstmove = 1;
            }
            if (state->count && !newcount)
                ch = state->direction;
            else
            {
                ch = run_ch;
                state->direction = ch;
            }
            continue;
        }
        if (ch == 'F')
        {
            state->kamikaze = 1;
            ch = 'f';
            continue;
        }
        if (ch == 'f')
        {
            if (!state->get_dir_success)
            {
                state->after = 0;
                push_marker(state, "fight_no_direction");
                return;
            }
            if (!state->monster_visible)
            {
                state->after = 0;
                push_marker(state, "no_monster_there");
                return;
            }
            if (state->diag_ok)
            {
                state->to_death = 1;
                state->runch = state->dir_ch;
                push_marker(state, "fight_to_death");
                ch = state->dir_ch;
                continue;
            }
            push_marker(state, "fight_bad_diagonal");
            return;
        }
        if (ch == 't')
        {
            if (state->get_dir_success)
                push_markerf(state, "missile:", state->dir_ch);
            else
            {
                state->after = 0;
                push_marker(state, "throw_no_direction");
            }
            return;
        }
        if (ch == 'a')
        {
            if (!state->last_comm)
            {
                state->after = 0;
                push_marker(state, "again_empty");
                return;
            }
            state->again = 1;
            push_markerf(state, "again:", state->last_comm);
            ch = state->last_comm;
            continue;
        }
        action = item_action(ch);
        if (action)
        {
            push_marker(state, action);
            return;
        }
        action = no_turn_action(ch);
        if (action)
        {
            if (ch == 'Q')
                state->q_comm = 1;
            state->after = 0;
            push_marker(state, action);
            if (ch == 'Q')
                state->q_comm = 0;
            return;
        }
        if (ch == 's')
        {
            push_marker(state, "search");
            return;
        }
        if (ch == 'z')
        {
            if (state->get_dir_success)
                push_markerf(state, "do_zap:", state->dir_ch);
            else
            {
                state->after = 0;
                push_marker(state, "zap_no_direction");
            }
            return;
        }
        if (ch == '.')
        {
            push_marker(state, "rest");
            return;
        }
        if (ch == ' ')
        {
            state->after = 0;
            push_marker(state, "legal_illegal");
            return;
        }
        if (ch == '^')
        {
            state->after = 0;
            if (state->get_dir_success)
                push_markerf(state, "identify_trap:", state->dir_ch);
            else
                push_marker(state, "identify_trap_no_direction");
            return;
        }
        if ((unsigned char) ch == ESCAPE)
        {
            state->door_stop = 0;
            state->count = 0;
            state->after = 0;
            state->again = 0;
            push_marker(state, "escape");
            return;
        }
        if (ch == 'm')
        {
            state->move_on = 1;
            if (!state->get_dir_success)
            {
                state->after = 0;
                push_marker(state, "move_on_no_direction");
                return;
            }
            ch = state->dir_ch;
            state->countch = state->dir_ch;
            continue;
        }
        action = current_action(ch);
        if (action)
        {
            push_marker(state, action);
            return;
        }
        state->after = 0;
        state->count = 0;
        push_markerf(state, "illegal:", ch);
        return;
    }
}

static void apply_command(char *chars, int len, CommandState *state)
{
    int index = 0;
    char ch;
    int newcount = 0;
    state->after = 1;
    state->take = 0;
    push_marker(state, "do_daemons_before");
    push_marker(state, "do_fuses_before");
    if (state->no_command)
    {
        state->no_command--;
        push_marker(state, "no_command_wait");
        if (state->no_command == 0)
            push_marker(state, "you_can_move_again");
        finish_command(state);
        return;
    }
    ch = index < len ? chars[index++] : '.';
    if (isdigit((unsigned char) ch))
    {
        state->count = 0;
        newcount = 1;
        while (isdigit((unsigned char) ch))
        {
            state->count = state->count * 10 + (ch - '0');
            if (state->count > 255)
                state->count = 255;
            ch = index < len ? chars[index++] : '.';
        }
        state->countch = ch;
        if (!is_repeatable(ch))
            state->count = 0;
    }
    if (state->count && !state->running)
        state->count--;
    if (ch != 'a' && (unsigned char) ch != ESCAPE && !(state->running || state->count || state->to_death))
    {
        state->l_last_comm = state->last_comm;
        state->l_last_dir = state->last_dir;
        strcpy(state->l_last_pick, state->last_pick);
        state->last_comm = ch;
        state->last_dir = 0;
        state->last_pick[0] = '\0';
    }
    dispatch(ch, state, newcount);
    finish_command(state);
}

static void print_state(CommandState *state)
{
    char buf[16];
    printf("{");
    printf("\"running\":"); print_bool(state->running);
    printf(",\"count\":%d", state->count);
    label(state->countch, buf); printf(",\"countch\":"); print_string(buf);
    label(state->direction, buf); printf(",\"direction\":"); print_string(buf);
    label(state->runch, buf); printf(",\"runch\":"); print_string(buf);
    printf(",\"door_stop\":"); print_bool(state->door_stop);
    printf(",\"firstmove\":"); print_bool(state->firstmove);
    printf(",\"move_on\":"); print_bool(state->move_on);
    printf(",\"after\":"); print_bool(state->after);
    printf(",\"again\":"); print_bool(state->again);
    printf(",\"to_death\":"); print_bool(state->to_death);
    printf(",\"kamikaze\":"); print_bool(state->kamikaze);
    printf(",\"q_comm\":"); print_bool(state->q_comm);
    printf(",\"no_command\":%d", state->no_command);
    label(state->last_comm, buf); printf(",\"last_comm\":"); print_string(buf);
    label(state->last_dir, buf); printf(",\"last_dir\":"); print_string(buf);
    printf(",\"last_pick\":"); print_string(state->last_pick);
    label(state->l_last_comm, buf); printf(",\"l_last_comm\":"); print_string(buf);
    label(state->l_last_dir, buf); printf(",\"l_last_dir\":"); print_string(buf);
    printf(",\"l_last_pick\":"); print_string(state->l_last_pick);
    label(state->take, buf); printf(",\"take\":"); print_string(buf);
    printf(",\"markers\":[");
    for (int i = 0; i < state->marker_count; i++)
    {
        if (i) printf(",");
        print_string(state->markers[i]);
    }
    printf("]}");
}

static void print_input(char *chars, int len)
{
    char buf[16];
    printf("[");
    for (int i = 0; i < len; i++)
    {
        if (i) printf(",");
        label(chars[i], buf);
        print_string(buf);
    }
    printf("]");
}

static CommandCase make_case(const char *name, const char *chars, int len, CommandState state)
{
    CommandCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    memcpy(c.chars, chars, len);
    c.len = len;
    c.state = state;
    return c;
}

static void print_case(CommandCase *c)
{
    CommandState state = c->state;
    CommandState initial = state;
    printf("{\"name\":"); print_string(c->name);
    printf(",\"input\":"); print_input(c->chars, c->len);
    printf(",\"initial\":"); print_state(&initial);
    apply_command(c->chars, c->len, &state);
    printf(",\"final\":"); print_state(&state);
    printf("}");
}

int main(void)
{
    char tracked[] = {CTRL_B, CTRL_H, CTRL_J, CTRL_K, CTRL_L, CTRL_N, CTRL_U, CTRL_Y, '.', ',', 'a', 'd', 'h', 'i', 'm', 'q', 'r', 's', 't', 'z', '>', 'B', 'C', 'H', 'I', 'N', ESCAPE};
    CommandCase cases[40];
    int count = 0;
    CommandState state;
    state = base_state(); cases[count++] = make_case("count_caps_repeatable_move", "300h", 4, state);
    state = base_state(); cases[count++] = make_case("count_clears_nonrepeatable_inventory", "12i", 3, state);
    state = base_state(); cases[count++] = make_case("plain_move", "l", 1, state);
    state = base_state(); cases[count++] = make_case("uppercase_run", "N", 1, state);
    state = base_state(); { char chars[] = {CTRL_H}; cases[count++] = make_case("control_run_sets_door_stop", chars, 1, state); }
    state = base_state(); state.count = 3; state.direction = 'J'; { char chars[] = {CTRL_H}; cases[count++] = make_case("continued_count_reuses_direction", chars, 1, state); }
    state = base_state(); state.item_here = 0; cases[count++] = make_case("pickup_nothing", ",", 1, state);
    state = base_state(); state.item_here = 1; cases[count++] = make_case("pickup_item", ",", 1, state);
    state = base_state(); state.get_dir_success = 0; cases[count++] = make_case("fight_no_direction", "f", 1, state);
    state = base_state(); state.get_dir_success = 1; state.dir_ch = 'u'; state.monster_visible = 1; cases[count++] = make_case("fight_visible_target", "f", 1, state);
    state = base_state(); state.get_dir_success = 1; state.monster_visible = 0; cases[count++] = make_case("fight_no_monster", "f", 1, state);
    state = base_state(); state.dir_ch = 'y'; state.monster_visible = 1; cases[count++] = make_case("kamikaze_visible_target", "F", 1, state);
    state = base_state(); state.get_dir_success = 0; cases[count++] = make_case("throw_no_direction", "t", 1, state);
    state = base_state(); state.get_dir_success = 1; state.dir_ch = 'n'; cases[count++] = make_case("throw_with_direction", "t", 1, state);
    state = base_state(); cases[count++] = make_case("again_empty", "a", 1, state);
    state = base_state(); state.last_comm = 'q'; cases[count++] = make_case("again_replays_quaff", "a", 1, state);
    state = base_state(); state.get_dir_success = 0; cases[count++] = make_case("zap_no_direction", "z", 1, state);
    state = base_state(); state.get_dir_success = 1; state.dir_ch = 'k'; cases[count++] = make_case("zap_with_direction", "z", 1, state);
    state = base_state(); state.get_dir_success = 1; state.dir_ch = 'h'; cases[count++] = make_case("move_on_with_direction", "m", 1, state);
    state = base_state(); state.get_dir_success = 0; cases[count++] = make_case("move_on_no_direction", "m", 1, state);
    state = base_state(); cases[count++] = make_case("inventory_no_turn", "i", 1, state);
    state = base_state(); cases[count++] = make_case("descend_no_turn", ">", 1, state);
    state = base_state(); cases[count++] = make_case("search_consumes_turn", "s", 1, state);
    state = base_state(); cases[count++] = make_case("rest_consumes_turn", ".", 1, state);
    state = base_state(); cases[count++] = make_case("space_refunds_turn", " ", 1, state);
    state = base_state(); state.count = 9; state.door_stop = 1; state.again = 1; { char chars[] = {ESCAPE}; cases[count++] = make_case("escape_resets_count", chars, 1, state); }
    state = base_state(); cases[count++] = make_case("current_weapon_consumes_turn", ")", 1, state);
    state = base_state(); state.count = 4; cases[count++] = make_case("illegal_command", "x", 1, state);
    state = base_state(); state.no_command = 1; cases[count++] = make_case("no_command_wait_finishes", "", 0, state);
    state = base_state(); cases[count++] = make_case("read_scroll_item_dispatch", "r", 1, state);
    state = base_state(); cases[count++] = make_case("ring_on_item_dispatch", "P", 1, state);
    state = base_state(); cases[count++] = make_case("save_no_turn", "S", 1, state);
    state = base_state(); state.get_dir_success = 1; state.dir_ch = 'j'; cases[count++] = make_case("trap_identify_with_direction", "^", 1, state);

    printf("{\"schema\":\"gamebench.rogue.source_command.v1\",\"repeatable\":[");
    for (int i = 0; i < (int) sizeof(tracked); i++)
    {
        char buf[16];
        if (i) printf(",");
        label(tracked[i], buf);
        printf("{\"command\":"); print_string(buf);
        printf(",\"repeatable\":"); print_bool(is_repeatable(tracked[i]));
        printf("}");
    }
    printf("],\"cases\":[");
    for (int i = 0; i < count; i++)
    {
        if (i) printf(",");
        print_case(&cases[i]);
    }
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_command_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_command",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-command-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_command.c"
        binary = temp / "source_command"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_command.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source command mismatch")


if __name__ == "__main__":
    main()
