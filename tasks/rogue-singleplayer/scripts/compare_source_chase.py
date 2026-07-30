#!/usr/bin/env python3
"""Compare source-derived Rogue chase decisions across C, Python, and Rust."""

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

from source_chase import source_chase_report


C_SOURCE = r'''
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NUMCOLS 80
#define NUMLINES 24
#define SCROLL '?'
#define ISHUH 0001000
#define ISHASTE 0000100
#define ISSLOW 0100000
#define S_SCARE 10

typedef struct coord {
    int y;
    int x;
} Coord;

typedef struct thing {
    char type;
    Coord pos;
    int flags;
    int turn;
    char disguise;
} Thing;

typedef struct object {
    char type;
    int which;
    Coord pos;
} Object;

typedef struct tile {
    Coord pos;
    char ch;
} Tile;

typedef struct map {
    Tile tiles[16];
    int tile_count;
    Object objects[16];
    int object_count;
    Thing monsters[16];
    int monster_count;
} Map;

typedef struct chase_result {
    Coord chosen;
    int curdist;
    int keep_chasing;
    int flags;
    int rng_seed;
    const char *branch;
} ChaseResult;

typedef struct move_result {
    int calls;
    int returned;
    int flags;
    int turn;
} MoveResult;

typedef struct chase_case {
    const char *name;
    int seed;
    char type;
    int flags;
    Coord pos;
    Coord target;
    Coord hero;
    Map map;
} ChaseCase;

static int seed;

#define RN (((seed = seed*11109+13849) >> 16) & 0xffff)

int rnd(int range)
{
    return range == 0 ? 0 : abs((int) RN) % range;
}

Coord coord(int y, int x)
{
    Coord c = {y, x};
    return c;
}

int coord_eq(Coord first, Coord second)
{
    return first.x == second.x && first.y == second.y;
}

int dist(Coord first, Coord second)
{
    return (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y);
}

int step_ok(char ch)
{
    return ch != ' ' && ch != '|' && ch != '-' && !isalpha((unsigned char) ch);
}

char chat(Map *map, Coord pos)
{
    for (int i = 0; i < map->tile_count; i++)
        if (coord_eq(map->tiles[i].pos, pos))
            return map->tiles[i].ch;
    return '.';
}

Thing *moat(Map *map, Coord pos)
{
    for (int i = 0; i < map->monster_count; i++)
        if (coord_eq(map->monsters[i].pos, pos))
            return &map->monsters[i];
    return NULL;
}

char winat(Map *map, Coord pos)
{
    Thing *monster = moat(map, pos);
    return monster == NULL ? chat(map, pos) : monster->disguise;
}

Object *object_at(Map *map, Coord pos)
{
    for (int i = 0; i < map->object_count; i++)
        if (coord_eq(map->objects[i].pos, pos))
            return &map->objects[i];
    return NULL;
}

int diag_ok(Map *map, Coord start, Coord end)
{
    if (end.x < 0 || end.x >= NUMCOLS || end.y <= 0 || end.y >= NUMLINES - 1)
        return 0;
    if (end.x == start.x || end.y == start.y)
        return 1;
    return step_ok(chat(map, coord(end.y, start.x))) && step_ok(chat(map, coord(start.y, end.x)));
}

Coord rndmove(Thing *thing)
{
    Coord ret;
    ret.y = thing->pos.y + rnd(3) - 1;
    ret.x = thing->pos.x + rnd(3) - 1;
    return ret;
}

ChaseResult chase(Map *map, Thing *thing, Coord target, Coord hero)
{
    int random_branch = 0;
    int curdist;
    int plcnt = 1;
    Coord chosen;
    ChaseResult result;
    const char *branch = "direct";

    if (thing->flags & ISHUH)
        random_branch = rnd(5) != 0;
    if (!random_branch && thing->type == 'P')
        random_branch = rnd(5) == 0;
    if (!random_branch && thing->type == 'B')
        random_branch = rnd(2) == 0;

    if (random_branch)
    {
        branch = "random";
        chosen = rndmove(thing);
        curdist = dist(chosen, target);
        if (rnd(20) == 0)
            thing->flags &= ~ISHUH;
    }
    else
    {
        int ey, ex;
        curdist = dist(thing->pos, target);
        chosen = thing->pos;
        ey = thing->pos.y + 1;
        if (ey >= NUMLINES - 1)
            ey = NUMLINES - 2;
        ex = thing->pos.x + 1;
        if (ex >= NUMCOLS)
            ex = NUMCOLS - 1;
        for (int x = thing->pos.x - 1; x <= ex; x++)
        {
            if (x < 0)
                continue;
            for (int y = thing->pos.y - 1; y <= ey; y++)
            {
                Coord tryp = coord(y, x);
                char ch;
                Object *obj;
                Thing *blocker;
                int thisdist;
                if (!diag_ok(map, thing->pos, tryp))
                    continue;
                ch = winat(map, tryp);
                if (!step_ok(ch))
                    continue;
                obj = object_at(map, tryp);
                if (ch == SCROLL && obj != NULL && obj->type == SCROLL && obj->which == S_SCARE)
                    continue;
                blocker = moat(map, tryp);
                if (blocker != NULL && blocker->type == 'X')
                    continue;
                thisdist = dist(tryp, target);
                if (thisdist < curdist)
                {
                    plcnt = 1;
                    chosen = tryp;
                    curdist = thisdist;
                }
                else if (thisdist == curdist && rnd(++plcnt) == 0)
                {
                    chosen = tryp;
                    curdist = thisdist;
                }
            }
        }
    }
    result.chosen = chosen;
    result.curdist = curdist;
    result.keep_chasing = curdist != 0 && !coord_eq(chosen, hero);
    result.flags = thing->flags;
    result.rng_seed = seed;
    result.branch = branch;
    return result;
}

MoveResult move_monst_schedule(Thing *thing, int *results, int result_count)
{
    MoveResult result = {0, 0, thing->flags, thing->turn};
    if (!(thing->flags & ISSLOW) || thing->turn)
    {
        result.calls++;
        if (result_count > 0 && results[0] == -1)
        {
            result.returned = -1;
            result.flags = thing->flags;
            result.turn = thing->turn;
            return result;
        }
    }
    if (thing->flags & ISHASTE)
    {
        result.calls++;
        if (result_count > 1 && results[1] == -1)
        {
            result.returned = -1;
            result.flags = thing->flags;
            result.turn = thing->turn;
            return result;
        }
    }
    thing->turn = !thing->turn;
    result.flags = thing->flags;
    result.turn = thing->turn;
    return result;
}

ChaseCase chase_case(const char *name, int initial_seed, char type, int flags, Coord pos, Coord target, Coord hero)
{
    ChaseCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = initial_seed;
    c.type = type;
    c.flags = flags;
    c.pos = pos;
    c.target = target;
    c.hero = hero;
    return c;
}

void add_tile(ChaseCase *c, Coord pos, char ch)
{
    c->map.tiles[c->map.tile_count].pos = pos;
    c->map.tiles[c->map.tile_count].ch = ch;
    c->map.tile_count++;
}

void add_object(ChaseCase *c, char type, int which, Coord pos)
{
    c->map.objects[c->map.object_count].type = type;
    c->map.objects[c->map.object_count].which = which;
    c->map.objects[c->map.object_count].pos = pos;
    c->map.object_count++;
}

void add_monster(ChaseCase *c, char type, Coord pos, int flags, char disguise)
{
    c->map.monsters[c->map.monster_count].type = type;
    c->map.monsters[c->map.monster_count].pos = pos;
    c->map.monsters[c->map.monster_count].flags = flags;
    c->map.monsters[c->map.monster_count].turn = 1;
    c->map.monsters[c->map.monster_count].disguise = disguise;
    c->map.monster_count++;
}

void print_bool(int value)
{
    printf(value ? "true" : "false");
}

void print_coord(Coord c)
{
    printf("{\"y\":%d,\"x\":%d}", c.y, c.x);
}

void print_chase_case(ChaseCase *c)
{
    Thing thing;
    ChaseResult result;
    seed = c->seed;
    thing.type = c->type;
    thing.pos = c->pos;
    thing.flags = c->flags;
    thing.turn = 1;
    thing.disguise = c->type;
    result = chase(&c->map, &thing, c->target, c->hero);
    printf("{\"name\":\"%s\",\"chosen\":", c->name);
    print_coord(result.chosen);
    printf(",\"curdist\":%d,\"keep_chasing\":", result.curdist);
    print_bool(result.keep_chasing);
    printf(",\"flags\":%d,\"rng_seed\":%d,\"branch\":\"%s\"}", result.flags, result.rng_seed, result.branch);
}

void print_move_case(const char *name, char type, int flags, int turn, int *results, int result_count)
{
    Thing thing;
    MoveResult result;
    thing.type = type;
    thing.pos = coord(5, 5);
    thing.flags = flags;
    thing.turn = turn;
    thing.disguise = type;
    result = move_monst_schedule(&thing, results, result_count);
    printf("{\"name\":\"%s\",\"calls\":%d,\"returned\":%d,\"flags\":%d,\"turn\":", name, result.calls, result.returned, result.flags);
    print_bool(result.turn);
    printf("}");
}

int main(void)
{
    ChaseCase cases[9];
    int no_results[1] = {0};
    int normal_results[1] = {0};
    int haste_results[2] = {0, 0};
    int first_stop[2] = {-1, 0};
    int second_stop[2] = {0, -1};

    cases[0] = chase_case("direct_east", 1, 'K', 0, coord(5, 5), coord(5, 7), coord(5, 7));
    cases[1] = chase_case("tie_break", 7, 'K', 0, coord(5, 5), coord(7, 7), coord(9, 9));
    cases[2] = chase_case("wall_blocks_diagonal", 7, 'K', 0, coord(5, 5), coord(4, 4), coord(4, 4));
    add_tile(&cases[2], coord(4, 5), '|');
    add_tile(&cases[2], coord(5, 4), '-');
    cases[3] = chase_case("scare_scroll_skip", 7, 'K', 0, coord(5, 5), coord(5, 4), coord(5, 4));
    add_tile(&cases[3], coord(5, 4), SCROLL);
    add_object(&cases[3], SCROLL, S_SCARE, coord(5, 4));
    cases[4] = chase_case("ordinary_scroll_allowed", 7, 'K', 0, coord(5, 5), coord(5, 4), coord(5, 4));
    add_tile(&cases[4], coord(5, 4), SCROLL);
    add_object(&cases[4], SCROLL, 1, coord(5, 4));
    cases[5] = chase_case("xeroc_skip", 7, 'K', 0, coord(5, 5), coord(5, 4), coord(5, 4));
    add_monster(&cases[5], 'X', coord(5, 4), 0, ':');
    cases[6] = chase_case("confused_random", 5, 'K', ISHUH, coord(5, 5), coord(7, 7), coord(7, 7));
    cases[7] = chase_case("phantom_random", 1, 'P', 0, coord(5, 5), coord(7, 7), coord(7, 7));
    cases[8] = chase_case("bat_random", 1, 'B', 0, coord(5, 5), coord(7, 7), coord(7, 7));

    printf("{\"schema\":\"gamebench.rogue.source_chase.v1\",\"chase_cases\":[");
    for (int i = 0; i < 9; i++)
    {
        if (i)
            printf(",");
        print_chase_case(&cases[i]);
    }
    printf("],\"move_monst\":[");
    print_move_case("normal_one_chase", 'K', 0, 1, normal_results, 1);
    printf(",");
    print_move_case("slow_turn_skips", 'K', ISSLOW, 0, no_results, 0);
    printf(",");
    print_move_case("slow_turn_moves", 'K', ISSLOW, 1, normal_results, 1);
    printf(",");
    print_move_case("haste_two_chases", 'K', ISHASTE, 1, haste_results, 2);
    printf(",");
    print_move_case("first_chase_stops", 'K', ISHASTE, 1, first_stop, 2);
    printf(",");
    print_move_case("second_chase_stops", 'K', ISHASTE, 1, second_stop, 2);
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return _project(source_chase_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_chase",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-chase-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_chase.c"
        binary = temp / "source_chase"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def _project(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": report["schema"],
        "chase_cases": [
            {
                "name": case["name"],
                "chosen": case["outcome"]["chosen"],
                "curdist": case["outcome"]["curdist"],
                "keep_chasing": case["outcome"]["keep_chasing"],
                "flags": case["outcome"]["thing"]["flags"],
                "rng_seed": case["outcome"]["rng_seed"],
                "branch": case["outcome"]["trace"]["branch"],
            }
            for case in report["chase_cases"]
        ],
        "move_monst": [
            {
                "name": case["name"],
                "calls": case["outcome"]["calls"],
                "returned": case["outcome"]["returned"],
                "flags": case["outcome"]["thing"]["flags"],
                "turn": case["outcome"]["thing"]["turn"],
            }
            for case in report["move_monst"]
        ],
    }


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_chase.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "chase_cases": [case["name"] for case in reports["c"]["chase_cases"]],
        "move_cases": [case["name"] for case in reports["c"]["move_monst"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source chase mismatch")


if __name__ == "__main__":
    main()
