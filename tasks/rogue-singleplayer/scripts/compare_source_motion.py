#!/usr/bin/env python3
"""Compare source-derived Rogue motion decisions across C, Python, and Rust."""

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

from source_motion import source_motion_report


C_SOURCE = r'''
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NUMCOLS 80
#define NUMLINES 24
#define DOOR '+'
#define FLOOR '.'
#define PASSAGE '#'
#define STAIRS '%'
#define TRAP '^'
#define F_PASS 0x80
#define F_SEEN 0x40
#define F_REAL 0x10
#define F_PNUM 0x0f
#define F_TMASK 0x07
#define ISDARK 0000001
#define LAMPDIST 3
#define T_DOOR 0
#define T_BEAR 3
#define T_TELEP 4
#define T_RUST 6

typedef struct coord {
    int y;
    int x;
} Coord;

typedef struct room {
    Coord pos;
    Coord max;
    int flags;
} Room;

typedef struct room_ref {
    int exists;
    const char *kind;
    int index;
} RoomRef;

typedef struct tile {
    Coord coord;
    char ch;
    unsigned char flags;
    int monst;
} Tile;

typedef struct outcome {
    const char *transition;
    Coord from;
    Coord to;
    Coord hero_after;
    int moved;
    const char *reason;
    char tile;
    int trap_kind_exists;
    int trap_kind;
    int revealed_hidden_trap;
    int seenstairs;
    int fight;
    char take;
    int cell_after_exists;
    char cell_after_ch;
    int cell_after_flags;
} Outcome;

static char rows[NUMLINES][NUMCOLS];
static unsigned char flags_map[NUMLINES][NUMCOLS];
static int monsters[NUMLINES][NUMCOLS];
static Room rooms[9];

int step_ok_c(char ch)
{
    if (ch == ' ' || ch == '|' || ch == '-')
        return 0;
    return !isalpha((unsigned char) ch);
}

void init_base(void)
{
    for (int y = 0; y < NUMLINES; y++)
        for (int x = 0; x < NUMCOLS; x++)
        {
            rows[y][x] = ' ';
            flags_map[y][x] = F_REAL;
            monsters[y][x] = 0;
        }
    for (int i = 0; i < 9; i++)
    {
        rooms[i].pos.y = 0;
        rooms[i].pos.x = 0;
        rooms[i].max.y = 0;
        rooms[i].max.x = 0;
        rooms[i].flags = 0;
    }
    rooms[0].pos.y = 1;
    rooms[0].pos.x = 1;
    rooms[0].max.y = 5;
    rooms[0].max.x = 10;
    rooms[1].pos.y = 1;
    rooms[1].pos.x = 20;
    rooms[1].max.y = 5;
    rooms[1].max.x = 10;
    rooms[1].flags = ISDARK;
    for (int y = 1; y < 6; y++)
        for (int x = 1; x < 11; x++)
            rows[y][x] = FLOOR;
    for (int x = 1; x < 11; x++)
    {
        rows[1][x] = '-';
        rows[5][x] = '-';
    }
    for (int y = 1; y < 6; y++)
    {
        rows[y][1] = '|';
        rows[y][10] = '|';
    }
    for (int y = 1; y < 6; y++)
        for (int x = 20; x < 30; x++)
            rows[y][x] = FLOOR;
}

void set_tile(int y, int x, char ch, int flags, int monst)
{
    rows[y][x] = ch;
    flags_map[y][x] = (unsigned char) flags;
    monsters[y][x] = monst;
}

int dist_c(int y1, int x1, int y2, int x2)
{
    return ((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
}

int diag_ok(Coord start, Coord end)
{
    if (end.x < 0 || end.x >= NUMCOLS || end.y <= 0 || end.y >= NUMLINES - 1)
        return 0;
    if (end.x == start.x || end.y == start.y)
        return 1;
    return step_ok_c(rows[end.y][start.x]) && step_ok_c(rows[start.y][end.x]);
}

int turn_ok(Coord coord)
{
    int flags = flags_map[coord.y][coord.x];
    return rows[coord.y][coord.x] == DOOR || ((flags & (F_REAL | F_PASS)) == (F_REAL | F_PASS));
}

RoomRef roomin(Coord coord)
{
    RoomRef ref = {0, "", 0};
    int flags = flags_map[coord.y][coord.x];
    if (flags & F_PASS)
    {
        ref.exists = 1;
        ref.kind = "passage";
        ref.index = flags & F_PNUM;
        return ref;
    }
    for (int i = 0; i < 9; i++)
        if (coord.x <= rooms[i].pos.x + rooms[i].max.x && rooms[i].pos.x <= coord.x
            && coord.y <= rooms[i].pos.y + rooms[i].max.y && rooms[i].pos.y <= coord.y)
        {
            ref.exists = 1;
            ref.kind = "room";
            ref.index = i;
            return ref;
        }
    return ref;
}

int cansee(Coord hero, Coord target, int is_blind)
{
    if (is_blind)
        return 0;
    if (dist_c(target.y, target.x, hero.y, hero.x) < LAMPDIST)
    {
        if (flags_map[target.y][target.x] & F_PASS)
            if (target.y != hero.y && target.x != hero.x
                && !step_ok_c(rows[target.y][hero.x]) && !step_ok_c(rows[hero.y][target.x]))
                return 0;
        return 1;
    }
    RoomRef target_room = roomin(target);
    RoomRef hero_room = roomin(hero);
    if (!target_room.exists || !hero_room.exists)
        return 0;
    if (strcmp(target_room.kind, hero_room.kind) != 0 || target_room.index != hero_room.index)
        return 0;
    if (strcmp(target_room.kind, "room") != 0)
        return 1;
    return !(rooms[target_room.index].flags & ISDARK);
}

int be_trapped(Coord coord)
{
    rows[coord.y][coord.x] = TRAP;
    int trap_kind = flags_map[coord.y][coord.x] & F_TMASK;
    flags_map[coord.y][coord.x] |= F_SEEN;
    return trap_kind;
}

Outcome make_outcome(const char *transition, Coord hero, Coord target, int moved)
{
    Outcome outcome;
    outcome.transition = transition;
    outcome.from = hero;
    outcome.to = target;
    outcome.hero_after = moved ? target : hero;
    outcome.moved = moved;
    outcome.reason = "";
    outcome.tile = 0;
    outcome.trap_kind_exists = 0;
    outcome.trap_kind = 0;
    outcome.revealed_hidden_trap = 0;
    outcome.seenstairs = 0;
    outcome.fight = 0;
    outcome.take = 0;
    outcome.cell_after_exists = 0;
    outcome.cell_after_ch = 0;
    outcome.cell_after_flags = 0;
    return outcome;
}

Outcome classify_move(Coord hero, int dy, int dx)
{
    Coord target = {hero.y + dy, hero.x + dx};
    if (target.x < 0 || target.x >= NUMCOLS || target.y <= 0 || target.y >= NUMLINES - 1)
    {
        Outcome outcome = make_outcome("blocked", hero, target, 0);
        outcome.reason = "boundary";
        return outcome;
    }
    if (!diag_ok(hero, target))
    {
        Outcome outcome = make_outcome("blocked", hero, target, 0);
        outcome.reason = "diagonal";
        return outcome;
    }
    int fl = flags_map[target.y][target.x];
    char ch = rows[target.y][target.x];
    int revealed_hidden_trap = 0;
    if (!(fl & F_REAL) && ch == FLOOR)
    {
        ch = TRAP;
        rows[target.y][target.x] = TRAP;
        fl |= F_REAL;
        flags_map[target.y][target.x] = (unsigned char) fl;
        revealed_hidden_trap = 1;
    }
    if (ch == ' ' || ch == '|' || ch == '-')
    {
        Outcome outcome = make_outcome("blocked", hero, target, 0);
        outcome.reason = "wall";
        outcome.tile = ch;
        return outcome;
    }
    if (ch == DOOR)
    {
        Outcome outcome = make_outcome("door", hero, target, 1);
        outcome.tile = ch;
        return outcome;
    }
    if (ch == TRAP)
    {
        int trap_kind = be_trapped(target);
        int moved = !(trap_kind == T_DOOR || trap_kind == T_TELEP);
        Outcome outcome = make_outcome(moved ? "trap_move" : "trap_no_move", hero, target, moved);
        outcome.tile = ch;
        outcome.trap_kind_exists = 1;
        outcome.trap_kind = trap_kind;
        outcome.revealed_hidden_trap = revealed_hidden_trap;
        outcome.cell_after_exists = 1;
        outcome.cell_after_ch = rows[target.y][target.x];
        outcome.cell_after_flags = flags_map[target.y][target.x];
        return outcome;
    }
    if (ch == PASSAGE)
    {
        Outcome outcome = make_outcome("passage", hero, target, 1);
        outcome.tile = ch;
        return outcome;
    }
    if (ch == FLOOR)
    {
        if (!(fl & F_REAL))
            be_trapped(hero);
        Outcome outcome = make_outcome("floor", hero, target, 1);
        outcome.tile = ch;
        return outcome;
    }
    if (ch == STAIRS)
    {
        Outcome outcome = make_outcome("stairs", hero, target, 1);
        outcome.tile = ch;
        outcome.seenstairs = 1;
        return outcome;
    }
    if (isupper((unsigned char) ch) || monsters[target.y][target.x])
    {
        Outcome outcome = make_outcome("fight", hero, target, 0);
        outcome.tile = ch;
        outcome.fight = 1;
        return outcome;
    }
    Outcome outcome = make_outcome("item", hero, target, 1);
    outcome.tile = ch;
    outcome.take = ch;
    return outcome;
}

void print_coord(Coord coord)
{
    printf("{\"y\":%d,\"x\":%d}", coord.y, coord.x);
}

void print_room_ref(RoomRef ref)
{
    if (!ref.exists)
    {
        printf("null");
        return;
    }
    printf("{\"kind\":\"%s\",\"index\":%d}", ref.kind, ref.index);
}

void print_json_char(char ch)
{
    if (ch == 0)
        printf("\"\"");
    else
        printf("\"%c\"", ch);
}

void print_outcome(Outcome outcome)
{
    printf("{\"transition\":\"%s\",\"from\":", outcome.transition);
    print_coord(outcome.from);
    printf(",\"to\":");
    print_coord(outcome.to);
    printf(",\"hero_after\":");
    print_coord(outcome.hero_after);
    printf(",\"moved\":%s", outcome.moved ? "true" : "false");
    printf(",\"reason\":\"%s\"", outcome.reason);
    printf(",\"tile\":");
    print_json_char(outcome.tile);
    printf(",\"trap_kind\":");
    if (outcome.trap_kind_exists)
        printf("%d", outcome.trap_kind);
    else
        printf("null");
    printf(",\"revealed_hidden_trap\":%s", outcome.revealed_hidden_trap ? "true" : "false");
    printf(",\"seenstairs\":%s", outcome.seenstairs ? "true" : "false");
    printf(",\"fight\":%s", outcome.fight ? "true" : "false");
    printf(",\"take\":");
    print_json_char(outcome.take);
    printf(",\"cell_after\":");
    if (outcome.cell_after_exists)
    {
        printf("{\"ch\":");
        print_json_char(outcome.cell_after_ch);
        printf(",\"flags\":%d}", outcome.cell_after_flags);
    }
    else
        printf("null");
    printf("}");
}

Tile tile(int y, int x, char ch, int flags)
{
    Tile result;
    result.coord.y = y;
    result.coord.x = x;
    result.ch = ch;
    result.flags = (unsigned char) flags;
    result.monst = 0;
    return result;
}

void apply_tiles(Tile *tiles, int count)
{
    for (int i = 0; i < count; i++)
        set_tile(tiles[i].coord.y, tiles[i].coord.x, tiles[i].ch, tiles[i].flags, tiles[i].monst);
}

void print_move_case(const char *name, Coord hero, Coord delta, Tile *tiles, int tile_count)
{
    init_base();
    apply_tiles(tiles, tile_count);
    Coord target = {hero.y + delta.y, hero.x + delta.x};
    Outcome outcome = classify_move(hero, delta.y, delta.x);
    printf("{\"name\":\"%s\",\"diag_ok\":%s,\"room_before\":", name, diag_ok(hero, target) ? "true" : "false");
    print_room_ref(roomin(hero));
    printf(",\"room_target\":");
    if (target.y >= 0 && target.y < NUMLINES && target.x >= 0 && target.x < NUMCOLS)
        print_room_ref(roomin(target));
    else
        printf("null");
    printf(",\"outcome\":");
    print_outcome(outcome);
    printf("}");
}

void print_spatial_payload(const char *name, Coord hero, Coord target)
{
    printf("{\"name\":\"%s\",\"hero_room\":", name);
    print_room_ref(roomin(hero));
    printf(",\"target_room\":");
    print_room_ref(roomin(target));
    printf(",\"diag_ok\":%s,\"cansee\":%s}", diag_ok(hero, target) ? "true" : "false", cansee(hero, target, 0) ? "true" : "false");
}

void print_move_cases(void)
{
    Coord hero;
    Coord delta;
    Tile tiles[4];
    printf("[");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, FLOOR, F_REAL);
    print_move_case("floor_east", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 2}; delta = (Coord){0, -1}; tiles[0] = tile(3, 1, '|', F_REAL);
    print_move_case("wall_west", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){1, 4}; delta = (Coord){-1, 0};
    print_move_case("boundary_top", hero, delta, tiles, 0);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){-1, 1}; tiles[0] = tile(2, 4, FLOOR, F_REAL); tiles[1] = tile(2, 3, '|', F_REAL); tiles[2] = tile(3, 4, FLOOR, F_REAL);
    print_move_case("diagonal_blocked", hero, delta, tiles, 3);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){-1, 1}; tiles[0] = tile(2, 4, FLOOR, F_REAL); tiles[1] = tile(2, 3, FLOOR, F_REAL); tiles[2] = tile(3, 4, FLOOR, F_REAL);
    print_move_case("diagonal_open", hero, delta, tiles, 3);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, DOOR, F_REAL);
    print_move_case("door_east", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, PASSAGE, F_REAL | F_PASS | 1);
    print_move_case("passage_east", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, STAIRS, F_REAL);
    print_move_case("stairs_east", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, ':', F_REAL);
    print_move_case("item_food_east", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, 'A', F_REAL);
    print_move_case("monster_fight_east", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, FLOOR, T_BEAR);
    print_move_case("hidden_bear_trap", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, TRAP, F_REAL | T_DOOR);
    print_move_case("visible_trapdoor", hero, delta, tiles, 1);
    printf(",");
    hero = (Coord){3, 3}; delta = (Coord){0, 1}; tiles[0] = tile(3, 4, TRAP, F_REAL | T_RUST);
    print_move_case("visible_rust_trap", hero, delta, tiles, 1);
    printf("]");
}

void print_spatial_cases(void)
{
    printf("[");
    init_base();
    print_spatial_payload("lit_same_room_far", (Coord){3, 3}, (Coord){4, 8});
    printf(",");
    init_base();
    print_spatial_payload("dark_same_room_far", (Coord){3, 22}, (Coord){4, 28});
    printf(",");
    init_base();
    set_tile(4, 4, PASSAGE, F_REAL | F_PASS | 1, 0);
    set_tile(4, 3, '|', F_REAL, 0);
    set_tile(3, 4, '|', F_REAL, 0);
    print_spatial_payload("near_passage_blocked_diagonal", (Coord){3, 3}, (Coord){4, 4});
    printf(",");
    init_base();
    set_tile(4, 4, PASSAGE, F_REAL | F_PASS | 1, 0);
    set_tile(4, 3, FLOOR, F_REAL, 0);
    set_tile(3, 4, '|', F_REAL, 0);
    print_spatial_payload("near_passage_clear_diagonal", (Coord){3, 3}, (Coord){4, 4});
    printf(",");
    init_base();
    set_tile(3, 4, DOOR, F_REAL, 0);
    set_tile(3, 5, PASSAGE, F_REAL | F_PASS | 2, 0);
    set_tile(3, 6, PASSAGE, F_PASS | 2, 0);
    printf("{\"name\":\"turn_ok\",\"door\":%s,\"real_passage\":%s,\"hidden_passage\":%s}",
        turn_ok((Coord){3, 4}) ? "true" : "false",
        turn_ok((Coord){3, 5}) ? "true" : "false",
        turn_ok((Coord){3, 6}) ? "true" : "false");
    printf("]");
}

int main(void)
{
    printf("{\"move_cases\":");
    print_move_cases();
    printf(",\"spatial_cases\":");
    print_spatial_cases();
    printf("}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_motion_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_motion",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-motion-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_motion.c"
        binary = temp / "source_motion"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_motion.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "move_cases": [case["name"] for case in reports["c"]["move_cases"]],
        "spatial_cases": [case["name"] for case in reports["c"]["spatial_cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source motion mismatch")


if __name__ == "__main__":
    main()
