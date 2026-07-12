#!/usr/bin/env python3
"""Compare source-derived Rogue do_chase branches across C, Python, and Rust."""

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

from source_do_chase import source_do_chase_report


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DOOR '+'
#define FLOOR '.'
#define PASSAGE '#'
#define ISGONE 0000002
#define ISCANC 0000010
#define ISGREED 0000040
#define ISTARGET 0000200
#define ISRUN 0020000
#define BOLT_LENGTH 6
#define DRAGONSHOT 5

typedef struct coord { int y; int x; } Coord;
typedef struct room { int index; int goldval; int flags; Coord exits[4]; int exit_count; } Room;
typedef struct object { char type; Coord pos; } Object;
typedef struct monster { char type; Coord pos; int room; int flags; const char *dest; Coord dest_pos; Object pack[4]; int pack_count; } Monster;
typedef struct tile { Coord pos; char ch; } Tile;
typedef struct world {
    int seed;
    Coord hero;
    int proom;
    Room rooms[3];
    Room passage;
    Object objects[4];
    int object_count;
    Tile terrain[4];
    int terrain_count;
    int dest_room;
    int chase_keep;
    Coord chase_pos;
    int chase_room;
    int attack_return;
    const char *find_dest;
    Coord find_dest_pos;
    int running;
    int count;
    int quiet;
    int has_hit;
    int to_death;
    int kamikaze;
    const char *markers[8];
    int marker_count;
    int has_greed_reset;
    Coord target;
    int has_dragon_roll;
    int dragon_roll;
    int has_delta;
    Coord delta;
} World;
typedef struct test_case {
    const char *name;
    int seed;
    char type;
    Coord pos;
    int room;
    int flags;
    const char *dest;
    Coord dest_pos;
    Coord hero;
    int proom;
    int room_goldval;
    int room_flags;
    int dest_room;
    int has_tile;
    char tile;
    int chase_keep;
    Coord chase_pos;
    int chase_room;
    int attack_return;
    Object objects[4];
    int object_count;
    const char *find_dest;
    Coord find_dest_pos;
    int has_hit;
    int to_death;
    int kamikaze;
} TestCase;

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }
Coord coord(int y, int x) { Coord c = {y, x}; return c; }
int coord_eq(Coord a, Coord b) { return a.x == b.x && a.y == b.y; }
int dist(Coord a, Coord b) { return (b.x - a.x) * (b.x - a.x) + (b.y - a.y) * (b.y - a.y); }
int sign(int v) { return (v > 0) - (v < 0); }

Room room_make(int index, int goldval, int flags, Coord a, Coord b)
{
    Room r;
    r.index = index;
    r.goldval = goldval;
    r.flags = flags;
    r.exits[0] = a;
    r.exits[1] = b;
    r.exit_count = 2;
    return r;
}

Object object_make(char type, Coord pos) { Object o = {type, pos}; return o; }

void marker(World *world, const char *value) { world->markers[world->marker_count++] = value; }

char terrain_at(World *world, Coord pos)
{
    for (int i = 0; i < world->terrain_count; i++)
        if (coord_eq(world->terrain[i].pos, pos))
            return world->terrain[i].ch;
    return FLOOR;
}

void set_terrain(World *world, Coord pos, char ch)
{
    for (int i = 0; i < world->terrain_count; i++)
        if (coord_eq(world->terrain[i].pos, pos)) {
            world->terrain[i].ch = ch;
            return;
        }
    world->terrain[world->terrain_count].pos = pos;
    world->terrain[world->terrain_count].ch = ch;
    world->terrain_count++;
}

Room *room_by_index(World *world, int index)
{
    for (int i = 0; i < 3; i++)
        if (world->rooms[i].index == index)
            return &world->rooms[i];
    return &world->passage;
}

int dragon_flame(World *world, Monster *monster)
{
    int aligned = monster->pos.y == world->hero.y || monster->pos.x == world->hero.x ||
        abs(monster->pos.y - world->hero.y) == abs(monster->pos.x - world->hero.x);
    if (monster->type != 'D' || !aligned || dist(monster->pos, world->hero) > BOLT_LENGTH * BOLT_LENGTH || (monster->flags & ISCANC))
        return 0;
    world->has_dragon_roll = 1;
    world->dragon_roll = rnd(world, DRAGONSHOT);
    if (world->dragon_roll != 0)
        return 0;
    world->has_delta = 1;
    world->delta = coord(sign(world->hero.y - monster->pos.y), sign(world->hero.x - monster->pos.x));
    if (world->has_hit)
        marker(world, "endmsg");
    marker(world, "fire_bolt_flame");
    world->running = 0;
    world->count = 0;
    world->quiet = 0;
    if (world->to_death && !(monster->flags & ISTARGET)) {
        world->to_death = 0;
        world->kamikaze = 0;
    }
    return 1;
}

int do_chase(World *world, Monster *monster)
{
    Room *rer = room_by_index(world, monster->room);
    int ree_index;
    int door;
    int mindist = 32767;
    int stoprun = 0;
    if ((monster->flags & ISGREED) && rer->goldval == 0) {
        monster->dest = "hero";
        monster->dest_pos = world->hero;
        world->has_greed_reset = 1;
    }
    ree_index = strcmp(monster->dest, "hero") == 0 ? world->proom : world->dest_room;
    door = terrain_at(world, monster->pos) == DOOR;
    world->target = monster->dest_pos;
    while (rer->index != ree_index) {
        for (int i = 0; i < rer->exit_count; i++) {
            int curdist = dist(monster->dest_pos, rer->exits[i]);
            if (curdist < mindist) {
                world->target = rer->exits[i];
                mindist = curdist;
            }
        }
        if (door) {
            rer = &world->passage;
            door = 0;
            continue;
        }
        break;
    }
    if (rer->index == ree_index) {
        world->target = monster->dest_pos;
        if (dragon_flame(world, monster))
            return 0;
    }
    if (!world->chase_keep) {
        if (coord_eq(world->target, world->hero)) {
            marker(world, "attack");
            return world->attack_return;
        }
        if (coord_eq(world->target, monster->dest_pos)) {
            for (int i = 0; i < world->object_count; i++) {
                if (coord_eq(world->objects[i].pos, monster->dest_pos)) {
                    Object obj = world->objects[i];
                    for (int j = i; j + 1 < world->object_count; j++)
                        world->objects[j] = world->objects[j + 1];
                    world->object_count--;
                    for (int j = monster->pack_count; j > 0; j--)
                        monster->pack[j] = monster->pack[j - 1];
                    monster->pack[0] = obj;
                    monster->pack_count++;
                    set_terrain(world, obj.pos, (room_by_index(world, monster->room)->flags & ISGONE) ? PASSAGE : FLOOR);
                    monster->dest = world->find_dest;
                    monster->dest_pos = world->find_dest_pos;
                    marker(world, "pickup_object");
                    break;
                }
            }
            stoprun = monster->type != 'F';
        }
    }
    else if (monster->type == 'F')
        return 0;
    if (!coord_eq(world->chase_pos, monster->pos)) {
        monster->pos = world->chase_pos;
        monster->room = world->chase_room;
        marker(world, "relocate");
    }
    if (stoprun && coord_eq(monster->pos, monster->dest_pos))
        monster->flags &= ~ISRUN;
    return 0;
}

TestCase base_case(const char *name, int seed)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = seed;
    c.type = 'K';
    c.pos = coord(5, 5);
    c.room = 0;
    c.flags = ISRUN;
    c.dest = "hero";
    c.dest_pos = coord(10, 10);
    c.hero = coord(10, 10);
    c.proom = 1;
    c.room_goldval = 1;
    c.dest_room = 1;
    c.chase_keep = 1;
    c.chase_pos = coord(6, 6);
    c.chase_room = 0;
    c.find_dest = "hero";
    c.find_dest_pos = coord(10, 10);
    return c;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->hero = c->hero;
    world->proom = c->proom;
    world->rooms[0] = room_make(0, c->room_goldval, c->room_flags, coord(2, 2), coord(6, 6));
    world->rooms[1] = room_make(1, 0, 0, coord(10, 10), coord(10, 10));
    world->rooms[2] = room_make(2, 0, 0, coord(4, 4), coord(4, 4));
    world->passage = room_make(9, 0, ISGONE, coord(3, 8), coord(8, 3));
    for (int i = 0; i < c->object_count; i++)
        world->objects[world->object_count++] = c->objects[i];
    if (c->has_tile) {
        world->terrain[0].pos = c->pos;
        world->terrain[0].ch = c->tile;
        world->terrain_count = 1;
    }
    world->dest_room = c->dest_room;
    world->chase_keep = c->chase_keep;
    world->chase_pos = c->chase_pos;
    world->chase_room = c->chase_room;
    world->attack_return = c->attack_return;
    world->find_dest = c->find_dest;
    world->find_dest_pos = c->find_dest_pos;
    world->running = 1;
    world->count = 1;
    world->quiet = 3;
    world->has_hit = c->has_hit;
    world->to_death = c->to_death;
    world->kamikaze = c->kamikaze;
}

void print_bool(int value) { printf(value ? "true" : "false"); }
void print_coord(Coord c) { printf("{\"y\":%d,\"x\":%d}", c.y, c.x); }

void print_case(TestCase *c)
{
    World world;
    Monster monster;
    int returned;
    world_init(&world, c);
    monster.type = c->type;
    monster.pos = c->pos;
    monster.room = c->room;
    monster.flags = c->flags;
    monster.dest = c->dest;
    monster.dest_pos = c->dest_pos;
    monster.pack_count = 0;
    returned = do_chase(&world, &monster);
    printf("{\"name\":\"%s\",\"returned\":%d,\"monster\":{\"type\":\"%c\",\"pos\":", c->name, returned, monster.type);
    print_coord(monster.pos);
    printf(",\"room\":%d,\"flags\":%d,\"dest\":\"%s\",\"dest_pos\":", monster.room, monster.flags, monster.dest);
    print_coord(monster.dest_pos);
    printf(",\"pack_count\":%d},\"world\":{\"rng_seed\":%d,\"running\":", monster.pack_count, world.seed);
    print_bool(world.running);
    printf(",\"count\":%d,\"quiet\":%d,\"to_death\":", world.count, world.quiet);
    print_bool(world.to_death);
    printf(",\"kamikaze\":");
    print_bool(world.kamikaze);
    printf(",\"object_count\":%d,\"terrain_count\":%d,\"markers\":[", world.object_count, world.terrain_count);
    for (int i = 0; i < world.marker_count; i++) {
        if (i) printf(",");
        printf("\"%s\"", world.markers[i]);
    }
    printf("],\"target\":");
    print_coord(world.target);
    printf(",\"greed_reset\":");
    print_bool(world.has_greed_reset);
    printf(",\"dragon_roll\":");
    if (world.has_dragon_roll) printf("%d", world.dragon_roll); else printf("null");
    printf(",\"delta\":");
    if (world.has_delta) print_coord(world.delta); else printf("null");
    printf("}}");
}

int main(void)
{
    TestCase cases[9];
    int count = 0;
    cases[count++] = base_case("different_room_routes_exit", 1);
    cases[count] = base_case("door_reroutes_passage", 1); cases[count].has_tile = 1; cases[count].tile = DOOR; cases[count].dest = "object"; cases[count].dest_pos = coord(12, 12); cases[count].dest_room = 2; cases[count].chase_pos = coord(8, 3); cases[count].chase_room = 9; count++;
    cases[count] = base_case("dragon_flame", 1); cases[count].type = 'D'; cases[count].room = 1; cases[count].pos = coord(5, 5); cases[count].dest_pos = coord(5, 10); cases[count].hero = coord(5, 10); cases[count].has_hit = 1; cases[count].to_death = 1; cases[count].kamikaze = 1; count++;
    cases[count] = base_case("dragon_cancelled_chases", 1); cases[count].type = 'D'; cases[count].flags = ISRUN | ISCANC; cases[count].room = 1; cases[count].pos = coord(5, 5); cases[count].dest_pos = coord(5, 10); cases[count].hero = coord(5, 10); cases[count].chase_pos = coord(5, 6); cases[count].chase_room = 1; count++;
    cases[count] = base_case("attack_hero_return", 7); cases[count].room = 1; cases[count].pos = coord(5, 5); cases[count].chase_keep = 0; cases[count].chase_pos = coord(5, 5); cases[count].attack_return = -1; count++;
    cases[count] = base_case("pickup_object_keeps_running_after_find_dest", 7); cases[count].room = 1; cases[count].pos = coord(5, 5); cases[count].dest = "object"; cases[count].dest_pos = coord(6, 6); cases[count].chase_keep = 0; cases[count].chase_pos = coord(6, 6); cases[count].chase_room = 1; cases[count].objects[0] = object_make('*', coord(6, 6)); cases[count].object_count = 1; count++;
    cases[count] = base_case("stoprun_at_destination", 7); cases[count].room = 1; cases[count].pos = coord(5, 5); cases[count].dest = "custom"; cases[count].dest_pos = coord(6, 6); cases[count].chase_keep = 0; cases[count].chase_pos = coord(6, 6); cases[count].chase_room = 1; count++;
    cases[count] = base_case("venus_flytrap_no_relocate", 7); cases[count].type = 'F'; cases[count].room = 1; cases[count].pos = coord(5, 5); cases[count].chase_pos = coord(6, 6); cases[count].chase_room = 1; count++;
    cases[count] = base_case("greed_gold_taken_resets_dest", 7); cases[count].type = 'O'; cases[count].flags = ISRUN | ISGREED; cases[count].room_goldval = 0; cases[count].dest = "object"; cases[count].dest_pos = coord(6, 6); cases[count].chase_pos = coord(5, 6); count++;
    printf("{\"schema\":\"gamebench.rogue.source_do_chase.v1\",\"cases\":[");
    for (int i = 0; i < count; i++) { if (i) printf(","); print_case(&cases[i]); }
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return _project(source_do_chase_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_do_chase",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-do-chase-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_do_chase.c"
        binary = temp / "source_do_chase"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def _project(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": report["schema"],
        "cases": [
            {
                "name": case["name"],
                "returned": case["returned"],
                "monster": {
                    "type": case["monster"]["type"],
                    "pos": case["monster"]["pos"],
                    "room": case["monster"]["room"],
                    "flags": case["monster"]["flags"],
                    "dest": case["monster"]["dest"],
                    "dest_pos": case["monster"]["dest_pos"],
                    "pack_count": len(case["monster"]["pack"]),
                },
                "world": {
                    "rng_seed": case["world"]["rng_seed"],
                    "running": case["world"]["running"],
                    "count": case["world"]["count"],
                    "quiet": case["world"]["quiet"],
                    "to_death": case["world"]["to_death"],
                    "kamikaze": case["world"]["kamikaze"],
                    "object_count": len(case["world"]["objects"]),
                    "terrain_count": len(case["world"]["terrain"]),
                    "markers": case["world"]["markers"],
                    "target": case["world"]["trace"].get("target"),
                    "greed_reset": case["world"]["trace"].get("greed_dest_reset", False),
                    "dragon_roll": case["world"]["trace"].get("dragon_roll"),
                    "delta": case["world"]["trace"].get("delta"),
                },
            }
            for case in report["cases"]
        ],
    }


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_do_chase.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source do_chase mismatch")


if __name__ == "__main__":
    main()
