#!/usr/bin/env python3
"""Compare source-derived Rogue scroll branches across C, Python, and Rust."""

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

from source_scrolls import source_scrolls_report


TRACE_KEYS = ["sleep_time", "sleep_roll", "create_selected", "map_draw", "map_oldch", "enchanted"]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define R_OR_S -2

#define PASSAGE '#'
#define DOOR '+'
#define FLOOR '.'
#define TRAP '^'
#define STAIRS '%'
#define POTION '!'
#define SCROLL '?'
#define WEAPON ')'
#define ARMOR ']'

#define F_PASS 0x80
#define F_SEEN 0x40
#define F_REAL 0x10

#define ISCURSED 0000001
#define ISPROT 0000040

#define CANHUH 0000001
#define ISHELD 0000400
#define ISRUN 0020000
#define SEEMONST 040000

#define S_CONFUSE 0
#define S_MAP 1
#define S_HOLD 2
#define S_SLEEP 3
#define S_ARMOR 4
#define S_ID_POTION 5
#define S_ID_SCROLL 6
#define S_ID_WEAPON 7
#define S_ID_ARMOR 8
#define S_ID_R_OR_S 9
#define S_SCARE 10
#define S_FDET 11
#define S_TELEP 12
#define S_ENCH 13
#define S_CREATE 14
#define S_REMOVE 15
#define S_AGGR 16
#define S_PROTECT 17
#define MAXSCROLLS 18

typedef struct scroll_object {
    char type;
    int which;
    int count;
} ScrollObject;

typedef struct scroll_item {
    char type;
    int which;
    int flags;
    int arm;
    int hplus;
    int dplus;
} ScrollItem;

typedef struct scroll_monster {
    char type;
    int flags;
    char oldch;
} ScrollMonster;

typedef struct map_cell {
    char ch;
    int flags;
    int has_monster;
    ScrollMonster monster;
} MapCell;

typedef struct world {
    int seed;
    int player_flags;
    int no_command;
    int current_weapon_is_obj;
    int has_current_weapon;
    ScrollItem current_weapon;
    int has_current_armor;
    ScrollItem current_armor;
    int has_left_ring;
    ScrollItem left_ring;
    int has_right_ring;
    ScrollItem right_ring;
    ScrollMonster nearby_monsters[8];
    int nearby_count;
    int create_candidates;
    int food_count;
    int teleport_room_changed;
    MapCell map_cells[12];
    int map_count;
    int scr_known[MAXSCROLLS];
    char markers[80][80];
    int marker_count;
    int has_sleep_time;
    int sleep_time;
    int has_sleep_roll;
    int sleep_roll;
    int has_create_selected;
    int create_selected;
    int has_map_draw;
    int map_draw;
    int has_map_oldch;
    int map_oldch;
    char enchanted[16];
    int has_enchanted;
} World;

typedef struct test_case {
    const char *name;
    int seed;
    ScrollObject obj;
    int player_flags;
    int no_command;
    int current_weapon_is_obj;
    int has_current_weapon;
    ScrollItem current_weapon;
    int has_current_armor;
    ScrollItem current_armor;
    int has_left_ring;
    ScrollItem left_ring;
    int has_right_ring;
    ScrollItem right_ring;
    ScrollMonster nearby_monsters[8];
    int nearby_count;
    int create_candidates;
    int food_count;
    int teleport_room_changed;
    MapCell map_cells[12];
    int map_count;
} TestCase;

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }
int c_spread(World *world, int nm) { return nm - nm / 20 + rnd(world, nm / 10); }

ScrollObject scroll_object(char type, int which, int count)
{
    ScrollObject obj = {type, which, count};
    return obj;
}
ScrollObject scroll_make(int which, int count) { return scroll_object(SCROLL, which, count); }
ScrollItem item_make(char type)
{
    ScrollItem item = {type, 0, 0, 0, 0, 0};
    return item;
}
ScrollMonster monster_make(char type)
{
    ScrollMonster monster = {type, 0, ' '};
    return monster;
}
MapCell map_cell_make(char ch, int flags, int has_monster, ScrollMonster monster)
{
    MapCell cell = {ch, flags, has_monster, monster};
    return cell;
}

void marker(World *world, const char *value)
{
    strncpy(world->markers[world->marker_count], value, sizeof(world->markers[world->marker_count]) - 1);
    world->markers[world->marker_count][sizeof(world->markers[world->marker_count]) - 1] = '\0';
    world->marker_count++;
}
void marker_i(World *world, const char *prefix, int value)
{
    char buf[80];
    snprintf(buf, sizeof(buf), "%s%d", prefix, value);
    marker(world, buf);
}
void marker_whatis(World *world, int value)
{
    char buf[80];
    if (value == R_OR_S)
        snprintf(buf, sizeof(buf), "whatis:%d", value);
    else
        snprintf(buf, sizeof(buf), "whatis:%c", (char)value);
    marker(world, buf);
}

void uncurse_item(int has_item, ScrollItem *item)
{
    if (has_item)
        item->flags &= ~ISCURSED;
}

void create_monster(World *world)
{
    int selected = -1;
    for (int index = 0; index < world->create_candidates; index++)
        if (rnd(world, index + 1) == 0)
            selected = index;
    if (selected < 0)
        marker(world, "faint_cry");
    else
    {
        world->create_selected = selected;
        world->has_create_selected = 1;
        marker(world, "new_monster");
    }
}

char map_default(MapCell *cell)
{
    if (cell->flags & F_PASS)
    {
        if (!(cell->flags & F_REAL))
            cell->ch = PASSAGE;
        cell->flags |= F_SEEN | F_REAL;
        return PASSAGE;
    }
    return ' ';
}

char map_cell_apply(MapCell *cell)
{
    char ch = cell->ch;
    if (ch == DOOR || ch == STAIRS)
        return ch;
    if (ch == '-' || ch == '|')
    {
        if (!(cell->flags & F_REAL))
        {
            cell->ch = DOOR;
            cell->flags |= F_REAL;
            return DOOR;
        }
        return ch;
    }
    if (ch == ' ')
    {
        if (cell->flags & F_REAL)
            return map_default(cell);
        cell->flags |= F_REAL;
        cell->ch = PASSAGE;
        ch = PASSAGE;
    }
    if (ch == PASSAGE)
    {
        if (!(cell->flags & F_REAL))
            cell->ch = PASSAGE;
        cell->flags |= F_SEEN | F_REAL;
        return PASSAGE;
    }
    if (ch == FLOOR)
    {
        if (cell->flags & F_REAL)
            return ' ';
        cell->ch = TRAP;
        cell->flags |= F_SEEN | F_REAL;
        return TRAP;
    }
    return map_default(cell);
}

void magic_map(World *world)
{
    int draw_count = 0;
    int oldch_count = 0;
    for (int i = 0; i < world->map_count; i++)
    {
        char display = map_cell_apply(&world->map_cells[i]);
        if (display != ' ')
        {
            if (world->map_cells[i].has_monster)
            {
                world->map_cells[i].monster.oldch = display;
                oldch_count++;
            }
            if (!world->map_cells[i].has_monster || !(world->player_flags & SEEMONST))
                draw_count++;
        }
    }
    world->map_draw = draw_count;
    world->has_map_draw = 1;
    world->map_oldch = oldch_count;
    world->has_map_oldch = 1;
}

void read_scroll(World *world, ScrollObject *obj)
{
    int discardit;
    if (obj->type != SCROLL)
    {
        marker(world, "nothing_to_read");
        return;
    }
    if (world->current_weapon_is_obj)
    {
        world->current_weapon_is_obj = 0;
        marker(world, "unwield_scroll");
    }
    discardit = obj->count == 1;
    marker(world, "leave_pack");
    if (obj->which == S_CONFUSE)
    {
        world->player_flags |= CANHUH;
        marker(world, "hands_glow");
    }
    else if (obj->which == S_ARMOR)
    {
        if (world->has_current_armor)
        {
            world->current_armor.arm--;
            world->current_armor.flags &= ~ISCURSED;
            marker(world, "armor_glows");
        }
    }
    else if (obj->which == S_HOLD)
    {
        int held = 0;
        for (int i = 0; i < world->nearby_count; i++)
            if (world->nearby_monsters[i].flags & ISRUN)
            {
                world->nearby_monsters[i].flags &= ~ISRUN;
                world->nearby_monsters[i].flags |= ISHELD;
                held++;
            }
        if (held)
        {
            world->scr_known[S_HOLD] = 1;
            marker_i(world, "monsters_freeze:", held);
        }
        else
            marker(world, "loss");
    }
    else if (obj->which == S_SLEEP)
    {
        int sleep_time = c_spread(world, 5);
        int sleep_roll = rnd(world, sleep_time);
        world->scr_known[S_SLEEP] = 1;
        world->sleep_time = sleep_time;
        world->has_sleep_time = 1;
        world->sleep_roll = sleep_roll;
        world->has_sleep_roll = 1;
        world->no_command += sleep_roll + 4;
        world->player_flags &= ~ISRUN;
        marker(world, "fall_asleep");
    }
    else if (obj->which == S_CREATE)
        create_monster(world);
    else if (obj->which == S_ID_POTION || obj->which == S_ID_SCROLL || obj->which == S_ID_WEAPON || obj->which == S_ID_ARMOR || obj->which == S_ID_R_OR_S)
    {
        int id_type = obj->which == S_ID_POTION ? POTION : obj->which == S_ID_SCROLL ? SCROLL : obj->which == S_ID_WEAPON ? WEAPON : obj->which == S_ID_ARMOR ? ARMOR : R_OR_S;
        world->scr_known[obj->which] = 1;
        marker_i(world, "id_scroll:", obj->which);
        marker_whatis(world, id_type);
    }
    else if (obj->which == S_MAP)
    {
        world->scr_known[S_MAP] = 1;
        marker(world, "map_msg");
        magic_map(world);
    }
    else if (obj->which == S_FDET)
    {
        if (world->food_count > 0)
        {
            world->scr_known[S_FDET] = 1;
            marker_i(world, "show_food:", world->food_count);
        }
        else
            marker(world, "nose_tingles");
    }
    else if (obj->which == S_TELEP)
    {
        marker(world, "teleport");
        if (world->teleport_room_changed)
            world->scr_known[S_TELEP] = 1;
    }
    else if (obj->which == S_ENCH)
    {
        if (!world->has_current_weapon || world->current_weapon.type != WEAPON)
            marker(world, "loss");
        else
        {
            world->current_weapon.flags &= ~ISCURSED;
            if (rnd(world, 2) == 0)
            {
                world->current_weapon.hplus++;
                strncpy(world->enchanted, "hplus", sizeof(world->enchanted));
            }
            else
            {
                world->current_weapon.dplus++;
                strncpy(world->enchanted, "dplus", sizeof(world->enchanted));
            }
            world->has_enchanted = 1;
            marker(world, "weapon_glows");
        }
    }
    else if (obj->which == S_SCARE)
        marker(world, "laughter");
    else if (obj->which == S_REMOVE)
    {
        uncurse_item(world->has_current_armor, &world->current_armor);
        uncurse_item(world->has_current_weapon, &world->current_weapon);
        uncurse_item(world->has_left_ring, &world->left_ring);
        uncurse_item(world->has_right_ring, &world->right_ring);
        marker(world, "remove_curse");
    }
    else if (obj->which == S_AGGR)
    {
        marker(world, "aggravate");
        marker(world, "hum");
    }
    else if (obj->which == S_PROTECT)
    {
        if (world->has_current_armor)
        {
            world->current_armor.flags |= ISPROT;
            marker(world, "protect_armor");
        }
        else
            marker(world, "loss");
    }
    else
    {
        marker(world, "puzzling");
        return;
    }
    marker(world, "look:true");
    marker(world, "status");
    marker_i(world, "call_it:", obj->which);
    if (discardit)
        marker(world, "discard");
}

TestCase base_case(const char *name, int seed)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = seed;
    c.obj = scroll_make(S_CONFUSE, 1);
    return c;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->player_flags = c->player_flags;
    world->no_command = c->no_command;
    world->current_weapon_is_obj = c->current_weapon_is_obj;
    world->has_current_weapon = c->has_current_weapon;
    world->current_weapon = c->current_weapon;
    world->has_current_armor = c->has_current_armor;
    world->current_armor = c->current_armor;
    world->has_left_ring = c->has_left_ring;
    world->left_ring = c->left_ring;
    world->has_right_ring = c->has_right_ring;
    world->right_ring = c->right_ring;
    world->nearby_count = c->nearby_count;
    for (int i = 0; i < c->nearby_count; i++)
        world->nearby_monsters[i] = c->nearby_monsters[i];
    world->create_candidates = c->create_candidates;
    world->food_count = c->food_count;
    world->teleport_room_changed = c->teleport_room_changed;
    world->map_count = c->map_count;
    for (int i = 0; i < c->map_count; i++)
        world->map_cells[i] = c->map_cells[i];
}

void print_bool(int value) { printf(value ? "true" : "false"); }
void print_string(const char *value)
{
    printf("\"");
    for (const char *p = value; *p; p++)
    {
        if (*p == '"' || *p == '\\')
            printf("\\%c", *p);
        else
            printf("%c", *p);
    }
    printf("\"");
}
void print_item(int has_item, ScrollItem *item)
{
    if (!has_item)
    {
        printf("null");
        return;
    }
    printf("{\"type\":\"%c\",\"which\":%d,\"flags\":%d,\"arm\":%d,\"hplus\":%d,\"dplus\":%d}", item->type, item->which, item->flags, item->arm, item->hplus, item->dplus);
}
void print_monster(ScrollMonster *monster)
{
    printf("{\"type\":\"%c\",\"flags\":%d,\"oldch\":\"%c\"}", monster->type, monster->flags, monster->oldch);
}
void print_map_cell(MapCell *cell)
{
    printf("{\"ch\":\"%c\",\"flags\":%d,\"monster\":", cell->ch, cell->flags);
    if (cell->has_monster)
        print_monster(&cell->monster);
    else
        printf("null");
    printf("}");
}
void print_trace_int(const char *key, int has_value, int value, int comma)
{
    if (comma) printf(",");
    print_string(key);
    printf(":");
    if (has_value) printf("%d", value); else printf("null");
}
void print_trace(World *world)
{
    printf("{");
    print_trace_int("sleep_time", world->has_sleep_time, world->sleep_time, 0);
    print_trace_int("sleep_roll", world->has_sleep_roll, world->sleep_roll, 1);
    print_trace_int("create_selected", world->has_create_selected, world->create_selected, 1);
    print_trace_int("map_draw", world->has_map_draw, world->map_draw, 1);
    print_trace_int("map_oldch", world->has_map_oldch, world->map_oldch, 1);
    printf(",");
    print_string("enchanted");
    printf(":");
    if (world->has_enchanted) print_string(world->enchanted); else printf("null");
    printf("}");
}
void print_case(TestCase *c)
{
    World world;
    world_init(&world, c);
    read_scroll(&world, &c->obj);
    printf("{\"name\":");
    print_string(c->name);
    printf(",\"seed\":%d,\"world\":{\"rng_seed\":%d,\"player_flags\":%d,\"no_command\":%d,\"current_weapon_is_obj\":",
        c->seed, world.seed, world.player_flags, world.no_command);
    print_bool(world.current_weapon_is_obj);
    printf(",\"current_weapon\":");
    print_item(world.has_current_weapon, &world.current_weapon);
    printf(",\"current_armor\":");
    print_item(world.has_current_armor, &world.current_armor);
    printf(",\"left_ring\":");
    print_item(world.has_left_ring, &world.left_ring);
    printf(",\"right_ring\":");
    print_item(world.has_right_ring, &world.right_ring);
    printf(",\"nearby_monsters\":[");
    for (int i = 0; i < world.nearby_count; i++)
    {
        if (i) printf(",");
        print_monster(&world.nearby_monsters[i]);
    }
    printf("],\"map_cells\":[");
    for (int i = 0; i < world.map_count; i++)
    {
        if (i) printf(",");
        print_map_cell(&world.map_cells[i]);
    }
    printf("],\"scr_known\":[");
    for (int i = 0; i < MAXSCROLLS; i++)
    {
        if (i) printf(",");
        print_bool(world.scr_known[i]);
    }
    printf("],\"markers\":[");
    for (int i = 0; i < world.marker_count; i++)
    {
        if (i) printf(",");
        print_string(world.markers[i]);
    }
    printf("],\"trace\":");
    print_trace(&world);
    printf("}}");
}

int main(void)
{
    TestCase cases[23];
    int count = 0;
    ScrollMonster m;
    cases[count] = base_case("non_scroll_rejected", 1); cases[count].obj = scroll_object(POTION, 0, 1); count++;
    cases[count] = base_case("confuse_sets_canhuh", 1); cases[count].obj = scroll_make(S_CONFUSE, 1); count++;
    cases[count] = base_case("armor_enchants_uncurses", 1); cases[count].has_current_armor = 1; cases[count].current_armor = item_make(ARMOR); cases[count].current_armor.arm = 5; cases[count].current_armor.flags = ISCURSED; cases[count].obj = scroll_make(S_ARMOR, 1); count++;
    cases[count] = base_case("hold_two_monsters", 1); m = monster_make('K'); m.flags = ISRUN; cases[count].nearby_monsters[cases[count].nearby_count++] = m; m = monster_make('O'); m.flags = ISRUN; cases[count].nearby_monsters[cases[count].nearby_count++] = m; cases[count].nearby_monsters[cases[count].nearby_count++] = monster_make('B'); cases[count].obj = scroll_make(S_HOLD, 1); count++;
    cases[count] = base_case("hold_none", 1); cases[count].nearby_monsters[cases[count].nearby_count++] = monster_make('K'); cases[count].obj = scroll_make(S_HOLD, 1); count++;
    cases[count] = base_case("sleep_stops_running", 1); cases[count].player_flags = ISRUN; cases[count].no_command = 2; cases[count].obj = scroll_make(S_SLEEP, 1); count++;
    cases[count] = base_case("create_no_space", 1); cases[count].create_candidates = 0; cases[count].obj = scroll_make(S_CREATE, 1); count++;
    cases[count] = base_case("create_selects_space", 1); cases[count].create_candidates = 4; cases[count].obj = scroll_make(S_CREATE, 1); count++;
    cases[count] = base_case("id_potion", 1); cases[count].obj = scroll_make(S_ID_POTION, 1); count++;
    cases[count] = base_case("id_ring_or_stick", 1); cases[count].obj = scroll_make(S_ID_R_OR_S, 1); count++;
    cases[count] = base_case("magic_map_cells", 1); cases[count].map_cells[cases[count].map_count++] = map_cell_make(DOOR, 0, 0, monster_make('K')); cases[count].map_cells[cases[count].map_count++] = map_cell_make('-', 0, 0, monster_make('K')); cases[count].map_cells[cases[count].map_count++] = map_cell_make(' ', 0, 0, monster_make('K')); cases[count].map_cells[cases[count].map_count++] = map_cell_make(PASSAGE, 0, 0, monster_make('K')); cases[count].map_cells[cases[count].map_count++] = map_cell_make(FLOOR, 0, 1, monster_make('K')); cases[count].map_cells[cases[count].map_count++] = map_cell_make(FLOOR, F_REAL, 0, monster_make('K')); cases[count].map_cells[cases[count].map_count++] = map_cell_make('x', F_PASS, 0, monster_make('K')); cases[count].obj = scroll_make(S_MAP, 1); count++;
    cases[count] = base_case("food_detect_found", 1); cases[count].food_count = 2; cases[count].obj = scroll_make(S_FDET, 1); count++;
    cases[count] = base_case("food_detect_none", 1); cases[count].food_count = 0; cases[count].obj = scroll_make(S_FDET, 1); count++;
    cases[count] = base_case("teleport_changes_room", 1); cases[count].teleport_room_changed = 1; cases[count].obj = scroll_make(S_TELEP, 1); count++;
    cases[count] = base_case("teleport_same_room", 1); cases[count].teleport_room_changed = 0; cases[count].obj = scroll_make(S_TELEP, 1); count++;
    cases[count] = base_case("enchant_weapon_hplus", 1); cases[count].has_current_weapon = 1; cases[count].current_weapon = item_make(WEAPON); cases[count].current_weapon.flags = ISCURSED; cases[count].obj = scroll_make(S_ENCH, 1); count++;
    cases[count] = base_case("enchant_no_weapon", 1); cases[count].obj = scroll_make(S_ENCH, 1); count++;
    cases[count] = base_case("scare_laughter", 1); cases[count].obj = scroll_make(S_SCARE, 1); count++;
    cases[count] = base_case("remove_curse_all", 1); cases[count].has_current_armor = 1; cases[count].current_armor = item_make(ARMOR); cases[count].current_armor.flags = ISCURSED; cases[count].current_armor.arm = 5; cases[count].has_current_weapon = 1; cases[count].current_weapon = item_make(WEAPON); cases[count].current_weapon.flags = ISCURSED; cases[count].has_left_ring = 1; cases[count].left_ring = item_make('='); cases[count].left_ring.flags = ISCURSED; cases[count].has_right_ring = 1; cases[count].right_ring = item_make('='); cases[count].right_ring.flags = ISCURSED; cases[count].obj = scroll_make(S_REMOVE, 1); count++;
    cases[count] = base_case("aggravate", 1); cases[count].obj = scroll_make(S_AGGR, 1); count++;
    cases[count] = base_case("protect_armor", 1); cases[count].has_current_armor = 1; cases[count].current_armor = item_make(ARMOR); cases[count].current_armor.arm = 5; cases[count].obj = scroll_make(S_PROTECT, 1); count++;
    cases[count] = base_case("protect_no_armor", 1); cases[count].obj = scroll_make(S_PROTECT, 1); count++;
    cases[count] = base_case("unwield_scroll_multi_count", 1); cases[count].current_weapon_is_obj = 1; cases[count].obj = scroll_make(S_CONFUSE, 2); count++;
    printf("{\"schema\":\"gamebench.rogue.source_scrolls.v1\",\"cases\":[");
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
    return _project(source_scrolls_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_scrolls",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-scrolls-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_scrolls.c"
        binary = temp / "source_scrolls"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return _project(json.loads(proc.stdout))


def _project(report: dict[str, Any]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in report["cases"]:
        trace = case["world"].get("trace", {})
        cases.append(
            {
                "name": case["name"],
                "world": {
                    "rng_seed": case["world"]["rng_seed"],
                    "player_flags": case["world"]["player_flags"],
                    "no_command": case["world"]["no_command"],
                    "current_weapon_is_obj": case["world"]["current_weapon_is_obj"],
                    "current_weapon": case["world"]["current_weapon"],
                    "current_armor": case["world"]["current_armor"],
                    "left_ring": case["world"]["left_ring"],
                    "right_ring": case["world"]["right_ring"],
                    "nearby_monsters": case["world"]["nearby_monsters"],
                    "map_cells": case["world"]["map_cells"],
                    "scr_known": case["world"]["scr_known"],
                    "markers": case["world"]["markers"],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_scrolls.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source scrolls mismatch")


if __name__ == "__main__":
    main()
