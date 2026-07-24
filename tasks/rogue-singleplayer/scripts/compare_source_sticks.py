#!/usr/bin/env python3
"""Compare source-derived Rogue stick and wand branches across C, Python, and Rust."""

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

from source_sticks import source_sticks_report


TRACE_KEYS = ["charges", "drain_amount", "missile_launch", "polymorph_type"]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STICK '/'
#define ISGONE 0000002
#define CANHUH 0000001
#define ISCANC 0000010
#define ISHASTE 0000100
#define ISHELD 0000400
#define ISINVIS 0002000
#define ISRUN 0020000
#define ISSLOW 0100000
#define ISKNOW 0000002

#define WS_LIGHT 0
#define WS_INVIS 1
#define WS_ELECT 2
#define WS_FIRE 3
#define WS_COLD 4
#define WS_POLYMORPH 5
#define WS_MISSILE 6
#define WS_HASTE_M 7
#define WS_SLOW_M 8
#define WS_DRAIN 9
#define WS_NOP 10
#define WS_TELAWAY 11
#define WS_TELTO 12
#define WS_CANCEL 13
#define MAXSTICKS 14

#define OP_FIX_STICK 1
#define OP_DO_ZAP 2
#define OP_CHARGE_STR 3

typedef struct stick_object {
    char type;
    int which;
    int charges;
    int flags;
    char damage[16];
    char hurldmg[16];
    int hplus;
    int dplus;
    int launch;
    int is_staff;
} StickObject;

typedef struct stick_monster {
    char type;
    int hp;
    int flags;
    char disguise;
    int has_disguise;
    char oldch;
    int pack_count;
    int turn;
    int dest_hero;
    int visible;
    int cansee;
} StickMonster;

typedef struct world {
    int seed;
    int after;
    int player_flags;
    int hero_hp;
    int proom_flags;
    int has_current_weapon;
    int current_weapon_which;
    int has_target;
    StickMonster target;
    StickMonster drain_monsters[8];
    int drain_count;
    int save_throw_success;
    int ws_known[MAXSTICKS];
    char markers[64][80];
    int marker_count;
    int has_trace_charges;
    int trace_charges;
    int has_trace_drain_amount;
    int trace_drain_amount;
    int has_trace_missile_launch;
    int trace_missile_launch;
    char trace_polymorph_type[2];
    int has_trace_polymorph_type;
} World;

typedef struct test_case {
    const char *name;
    int seed;
    int op;
    int after;
    int player_flags;
    int hero_hp;
    int proom_flags;
    int has_current_weapon;
    int current_weapon_which;
    int has_target;
    StickMonster target;
    StickMonster drain_monsters[8];
    int drain_count;
    int save_throw_success;
    int terse;
    StickObject obj;
} TestCase;

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }

void marker(World *world, const char *value)
{
    strncpy(world->markers[world->marker_count], value, sizeof(world->markers[world->marker_count]) - 1);
    world->markers[world->marker_count][sizeof(world->markers[world->marker_count]) - 1] = '\0';
    world->marker_count++;
}

void marker_ch(World *world, const char *prefix, char value)
{
    char buf[80];
    snprintf(buf, sizeof(buf), "%s%c", prefix, value);
    marker(world, buf);
}

StickObject object_make(char type, int which, int charges)
{
    StickObject obj;
    memset(&obj, 0, sizeof(obj));
    obj.type = type;
    obj.which = which;
    obj.charges = charges;
    obj.launch = -1;
    return obj;
}

StickObject stick_make(int which, int charges) { return object_make(STICK, which, charges); }

StickMonster monster_make(char type, int hp)
{
    StickMonster monster;
    memset(&monster, 0, sizeof(monster));
    monster.type = type;
    monster.hp = hp;
    monster.oldch = '.';
    monster.visible = 1;
    monster.cansee = 1;
    return monster;
}

void fix_stick(World *world, StickObject *obj)
{
    if (obj->is_staff)
        strncpy(obj->damage, "2x3", sizeof(obj->damage));
    else
        strncpy(obj->damage, "1x1", sizeof(obj->damage));
    strncpy(obj->hurldmg, "1x1", sizeof(obj->hurldmg));
    if (obj->which == WS_LIGHT)
        obj->charges = rnd(world, 10) + 10;
    else
        obj->charges = rnd(world, 5) + 3;
    world->trace_charges = obj->charges;
    world->has_trace_charges = 1;
}

void drain(World *world)
{
    int amount;
    if (world->drain_count == 0)
    {
        marker(world, "tingling");
        return;
    }
    world->hero_hp /= 2;
    amount = world->hero_hp / world->drain_count;
    world->trace_drain_amount = amount;
    world->has_trace_drain_amount = 1;
    for (int i = 0; i < world->drain_count; i++)
    {
        world->drain_monsters[i].hp -= amount;
        if (world->drain_monsters[i].hp <= 0)
            marker_ch(world, "killed:", world->drain_monsters[i].type);
        else
            marker_ch(world, "runto:", world->drain_monsters[i].type);
    }
}

void fire_bolt(World *world, const char *name)
{
    char buf[80];
    snprintf(buf, sizeof(buf), "fire_bolt:%s", name);
    marker(world, buf);
}

void zap_target_effect(World *world, int which)
{
    StickMonster *monster;
    if (!world->has_target)
        return;
    monster = &world->target;
    if (monster->type == 'F')
        world->player_flags &= ~ISHELD;
    if (which == WS_INVIS)
    {
        monster->flags |= ISINVIS;
        if (monster->cansee)
            marker(world, "draw_oldch");
    }
    else if (which == WS_POLYMORPH)
    {
        char oldch = monster->oldch;
        int pack_count = monster->pack_count;
        if (monster->visible)
            marker(world, "erase_monster");
        monster->type = (char)(rnd(world, 26) + 'A');
        monster->oldch = oldch;
        monster->pack_count = pack_count;
        world->trace_polymorph_type[0] = monster->type;
        world->trace_polymorph_type[1] = '\0';
        world->has_trace_polymorph_type = 1;
        if (monster->visible)
        {
            marker(world, "draw_new_monster");
            world->ws_known[WS_POLYMORPH] = 1;
        }
    }
    else if (which == WS_CANCEL)
    {
        monster->flags |= ISCANC;
        monster->flags &= ~(ISINVIS | CANHUH);
        monster->disguise = monster->type;
        monster->has_disguise = 1;
        if (monster->visible)
            marker(world, "draw_disguise");
    }
    else if (which == WS_TELAWAY || which == WS_TELTO)
    {
        monster->dest_hero = 1;
        monster->flags |= ISRUN;
        if (which == WS_TELAWAY)
            marker(world, "relocate:random_floor");
        else
            marker(world, "relocate:adjacent");
    }
}

void do_zap(World *world, StickObject *obj)
{
    if (obj->type != STICK)
    {
        world->after = 0;
        marker(world, "cant_zap");
        return;
    }
    if (obj->charges == 0)
    {
        marker(world, "nothing_happens");
        return;
    }
    if (obj->which == WS_LIGHT)
    {
        world->ws_known[WS_LIGHT] = 1;
        if (world->proom_flags & ISGONE)
            marker(world, "corridor_glows");
        else
        {
            world->proom_flags &= ~ISGONE;
            marker(world, "enter_room");
            marker(world, "room_lit");
        }
    }
    else if (obj->which == WS_DRAIN)
    {
        if (world->hero_hp < 2)
        {
            marker(world, "too_weak");
            return;
        }
        drain(world);
    }
    else if (obj->which == WS_INVIS || obj->which == WS_POLYMORPH || obj->which == WS_TELAWAY || obj->which == WS_TELTO || obj->which == WS_CANCEL)
        zap_target_effect(world, obj->which);
    else if (obj->which == WS_MISSILE)
    {
        world->ws_known[WS_MISSILE] = 1;
        if (world->has_current_weapon)
        {
            world->trace_missile_launch = world->current_weapon_which;
            world->has_trace_missile_launch = 1;
        }
        if (world->has_target && !world->save_throw_success)
            marker(world, "hit_monster:missile");
        else if (world->has_target)
            marker(world, "missile_misses");
        else
            marker(world, "missile_vanishes");
    }
    else if (obj->which == WS_HASTE_M || obj->which == WS_SLOW_M)
    {
        if (world->has_target)
        {
            if (obj->which == WS_HASTE_M)
            {
                if (world->target.flags & ISSLOW)
                    world->target.flags &= ~ISSLOW;
                else
                    world->target.flags |= ISHASTE;
            }
            else
            {
                if (world->target.flags & ISHASTE)
                    world->target.flags &= ~ISHASTE;
                else
                    world->target.flags |= ISSLOW;
                world->target.turn = 1;
            }
            marker(world, "runto");
        }
    }
    else if (obj->which == WS_ELECT || obj->which == WS_FIRE || obj->which == WS_COLD)
    {
        const char *name = obj->which == WS_ELECT ? "bolt" : obj->which == WS_FIRE ? "flame" : "ice";
        fire_bolt(world, name);
        world->ws_known[obj->which] = 1;
    }
    else if (obj->which == WS_NOP)
    {
    }
    else
        marker(world, "bizarre_schtick");
    obj->charges--;
}

const char *charge_str(StickObject *obj, int terse)
{
    static char buf[32];
    if (!(obj->flags & ISKNOW))
        return "";
    if (terse)
        snprintf(buf, sizeof(buf), " [%d]", obj->charges);
    else
        snprintf(buf, sizeof(buf), " [%d charges]", obj->charges);
    return buf;
}

TestCase base_case(const char *name, int seed, int op)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = seed;
    c.op = op;
    c.after = 1;
    c.hero_hp = 12;
    c.obj = stick_make(WS_NOP, 0);
    return c;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->after = c->after;
    world->player_flags = c->player_flags;
    world->hero_hp = c->hero_hp;
    world->proom_flags = c->proom_flags;
    world->has_current_weapon = c->has_current_weapon;
    world->current_weapon_which = c->current_weapon_which;
    world->has_target = c->has_target;
    world->target = c->target;
    world->drain_count = c->drain_count;
    for (int i = 0; i < c->drain_count; i++)
        world->drain_monsters[i] = c->drain_monsters[i];
    world->save_throw_success = c->save_throw_success;
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
void print_nullable_int(int has_value, int value)
{
    if (has_value)
        printf("%d", value);
    else
        printf("null");
}
void print_object(StickObject *obj)
{
    printf("{\"type\":\"%c\",\"which\":%d,\"charges\":%d,\"flags\":%d,\"damage\":", obj->type, obj->which, obj->charges, obj->flags);
    print_string(obj->damage);
    printf(",\"hurldmg\":");
    print_string(obj->hurldmg);
    printf(",\"hplus\":%d,\"dplus\":%d,\"launch\":%d,\"is_staff\":", obj->hplus, obj->dplus, obj->launch);
    print_bool(obj->is_staff);
    printf("}");
}
void print_monster(StickMonster *monster)
{
    printf("{\"type\":\"%c\",\"hp\":%d,\"flags\":%d,\"disguise\":", monster->type, monster->hp, monster->flags);
    if (monster->has_disguise)
        printf("\"%c\"", monster->disguise);
    else
        printf("null");
    printf(",\"oldch\":\"%c\",\"pack_count\":%d,\"turn\":", monster->oldch, monster->pack_count);
    print_bool(monster->turn);
    printf(",\"dest_hero\":");
    print_bool(monster->dest_hero);
    printf(",\"visible\":");
    print_bool(monster->visible);
    printf(",\"cansee\":");
    print_bool(monster->cansee);
    printf("}");
}
void print_trace(World *world)
{
    printf("{\"charges\":");
    print_nullable_int(world->has_trace_charges, world->trace_charges);
    printf(",\"drain_amount\":");
    print_nullable_int(world->has_trace_drain_amount, world->trace_drain_amount);
    printf(",\"missile_launch\":");
    print_nullable_int(world->has_trace_missile_launch, world->trace_missile_launch);
    printf(",\"polymorph_type\":");
    if (world->has_trace_polymorph_type)
        print_string(world->trace_polymorph_type);
    else
        printf("null");
    printf("}");
}
void print_case(TestCase *c)
{
    World world;
    StickObject obj = c->obj;
    const char *result = NULL;
    world_init(&world, c);
    if (c->op == OP_FIX_STICK)
        fix_stick(&world, &obj);
    else if (c->op == OP_DO_ZAP)
        do_zap(&world, &obj);
    else if (c->op == OP_CHARGE_STR)
        result = charge_str(&obj, c->terse);
    printf("{\"name\":");
    print_string(c->name);
    printf(",\"seed\":%d,\"result\":", c->seed);
    if (result)
        print_string(result);
    else
        printf("null");
    printf(",\"world\":{\"rng_seed\":%d,\"after\":", world.seed);
    print_bool(world.after);
    printf(",\"player_flags\":%d,\"hero_hp\":%d,\"proom_flags\":%d,\"current_weapon_which\":", world.player_flags, world.hero_hp, world.proom_flags);
    print_nullable_int(world.has_current_weapon, world.current_weapon_which);
    printf(",\"object\":");
    print_object(&obj);
    printf(",\"target\":");
    if (world.has_target)
        print_monster(&world.target);
    else
        printf("null");
    printf(",\"drain_monsters\":[");
    for (int i = 0; i < world.drain_count; i++)
    {
        if (i) printf(",");
        print_monster(&world.drain_monsters[i]);
    }
    printf("],\"ws_known\":[");
    for (int i = 0; i < MAXSTICKS; i++)
    {
        if (i) printf(",");
        print_bool(world.ws_known[i]);
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
    TestCase cases[26];
    int count = 0;
    cases[count] = base_case("fix_light_wand", 1, OP_FIX_STICK); cases[count].obj = stick_make(WS_LIGHT, 0); cases[count].obj.is_staff = 0; count++;
    cases[count] = base_case("fix_staff_nonlight", 1, OP_FIX_STICK); cases[count].obj = stick_make(WS_FIRE, 0); cases[count].obj.is_staff = 1; count++;
    cases[count] = base_case("zap_non_stick", 1, OP_DO_ZAP); cases[count].obj = object_make('!', WS_LIGHT, 1); count++;
    cases[count] = base_case("zap_empty", 1, OP_DO_ZAP); cases[count].obj = stick_make(WS_LIGHT, 0); count++;
    cases[count] = base_case("light_room", 1, OP_DO_ZAP); cases[count].proom_flags = 0; cases[count].obj = stick_make(WS_LIGHT, 2); count++;
    cases[count] = base_case("light_corridor", 1, OP_DO_ZAP); cases[count].proom_flags = ISGONE; cases[count].obj = stick_make(WS_LIGHT, 2); count++;
    cases[count] = base_case("drain_too_weak", 1, OP_DO_ZAP); cases[count].hero_hp = 1; cases[count].obj = stick_make(WS_DRAIN, 2); count++;
    cases[count] = base_case("drain_no_monsters", 1, OP_DO_ZAP); cases[count].hero_hp = 12; cases[count].obj = stick_make(WS_DRAIN, 2); count++;
    cases[count] = base_case("drain_hits_monsters", 1, OP_DO_ZAP); cases[count].hero_hp = 20; cases[count].drain_monsters[cases[count].drain_count++] = monster_make('K', 4); cases[count].drain_monsters[cases[count].drain_count++] = monster_make('O', 10); cases[count].obj = stick_make(WS_DRAIN, 2); count++;
    cases[count] = base_case("invis_flytrap_unholds", 1, OP_DO_ZAP); cases[count].player_flags = ISHELD; cases[count].has_target = 1; cases[count].target = monster_make('F', 8); cases[count].obj = stick_make(WS_INVIS, 2); count++;
    cases[count] = base_case("polymorph_visible", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].target.oldch = '.'; cases[count].target.pack_count = 2; cases[count].target.visible = 1; cases[count].obj = stick_make(WS_POLYMORPH, 2); count++;
    cases[count] = base_case("cancel_invisible_confuser", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('M', 8); cases[count].target.flags = ISINVIS | CANHUH; cases[count].obj = stick_make(WS_CANCEL, 2); count++;
    cases[count] = base_case("telaway_sets_run", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].obj = stick_make(WS_TELAWAY, 2); count++;
    cases[count] = base_case("telto_sets_run", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].obj = stick_make(WS_TELTO, 2); count++;
    cases[count] = base_case("missile_hits", 1, OP_DO_ZAP); cases[count].has_current_weapon = 1; cases[count].current_weapon_which = 3; cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].save_throw_success = 0; cases[count].obj = stick_make(WS_MISSILE, 2); count++;
    cases[count] = base_case("missile_misses", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].save_throw_success = 1; cases[count].obj = stick_make(WS_MISSILE, 2); count++;
    cases[count] = base_case("haste_clears_slow", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].target.flags = ISSLOW; cases[count].obj = stick_make(WS_HASTE_M, 2); count++;
    cases[count] = base_case("haste_sets_haste", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].obj = stick_make(WS_HASTE_M, 2); count++;
    cases[count] = base_case("slow_clears_haste", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].target.flags = ISHASTE; cases[count].obj = stick_make(WS_SLOW_M, 2); count++;
    cases[count] = base_case("slow_sets_slow_turn", 1, OP_DO_ZAP); cases[count].has_target = 1; cases[count].target = monster_make('K', 8); cases[count].obj = stick_make(WS_SLOW_M, 2); count++;
    cases[count] = base_case("fire_bolt", 1, OP_DO_ZAP); cases[count].obj = stick_make(WS_FIRE, 2); count++;
    cases[count] = base_case("cold_bolt", 1, OP_DO_ZAP); cases[count].obj = stick_make(WS_COLD, 2); count++;
    cases[count] = base_case("nop_consumes_charge", 1, OP_DO_ZAP); cases[count].obj = stick_make(WS_NOP, 2); count++;
    cases[count] = base_case("charge_unknown", 1, OP_CHARGE_STR); cases[count].obj = stick_make(WS_LIGHT, 7); cases[count].obj.flags = 0; count++;
    cases[count] = base_case("charge_known_verbose", 1, OP_CHARGE_STR); cases[count].obj = stick_make(WS_LIGHT, 7); cases[count].obj.flags = ISKNOW; cases[count].terse = 0; count++;
    cases[count] = base_case("charge_known_terse", 1, OP_CHARGE_STR); cases[count].obj = stick_make(WS_LIGHT, 7); cases[count].obj.flags = ISKNOW; cases[count].terse = 1; count++;
    printf("{\"schema\":\"gamebench.rogue.source_sticks.v1\",\"cases\":[");
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
    return _project(source_sticks_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_sticks",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-sticks-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_sticks.c"
        binary = temp / "source_sticks"
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
                "result": case["result"],
                "world": {
                    "rng_seed": case["world"]["rng_seed"],
                    "after": case["world"]["after"],
                    "player_flags": case["world"]["player_flags"],
                    "hero_hp": case["world"]["hero_hp"],
                    "proom_flags": case["world"]["proom_flags"],
                    "current_weapon_which": case["world"]["current_weapon_which"],
                    "object": case["world"]["object"],
                    "target": case["world"]["target"],
                    "drain_monsters": case["world"]["drain_monsters"],
                    "ws_known": case["world"]["ws_known"],
                    "markers": case["world"]["markers"],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_sticks.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source sticks mismatch")


if __name__ == "__main__":
    main()
