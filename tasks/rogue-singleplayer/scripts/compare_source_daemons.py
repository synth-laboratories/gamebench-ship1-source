#!/usr/bin/env python3
"""Compare source-derived Rogue daemon and fuse branches across C, Python, and Rust."""

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

from source_daemons import source_daemons_report


TRACE_KEYS = ["wander_roll", "faint_roll"]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EMPTY 0
#define DAEMON -1
#define BEFORE 1
#define AFTER 2
#define MAXDAEMONS 20

#define CANSEE 0000002
#define ISBLIND 0000004
#define ISLEVIT 0000010
#define ISHASTE 0000100
#define ISHUH 0001000
#define ISRUN 0020000

#define R_REGEN 9
#define R_DIGEST 10
#define MORETIME 150
#define STARVETIME 850

#define OP_DOCTOR 1
#define OP_STOMACH 2
#define OP_SWANDER 3
#define OP_ROLLWAND 4
#define OP_DO_DAEMONS 5
#define OP_DO_FUSES 6
#define OP_UNCONFUSE 7
#define OP_UNSEE 8
#define OP_SIGHT 9
#define OP_NOHASTE 10
#define OP_LAND 11

#define SETUP_START 1
#define SETUP_FUSE 2
#define SETUP_LENGTHEN 3
#define SETUP_EXTINGUISH 4

typedef struct stats {
    int level;
    int hp;
} Stats;

typedef struct ring {
    int present;
    int which;
} Ring;

typedef struct delayed_action {
    const char *action;
    int type;
    int arg;
    int time;
} DelayedAction;

typedef struct world {
    int seed;
    Stats stats;
    int max_hp;
    int quiet;
    int player_flags;
    Ring left_ring;
    Ring right_ring;
    int food_left;
    int hungry_state;
    int no_command;
    int amulet;
    int running;
    int to_death;
    int count;
    int proom_gone;
    int visible_invisible;
    int between;
    DelayedAction actions[MAXDAEMONS];
    char markers[32][48];
    int marker_count;
    int has_wander_roll;
    int wander_roll;
    int has_faint_roll;
    int faint_roll;
} World;

typedef struct setup_action {
    int op;
    const char *action;
    int type;
    int arg;
    int time;
} SetupAction;

typedef struct test_case {
    const char *name;
    int seed;
    int op;
    int flag;
    int level;
    int hp;
    int max_hp;
    int quiet;
    int player_flags;
    Ring left_ring;
    Ring right_ring;
    int food_left;
    int hungry_state;
    int no_command;
    int amulet;
    int running;
    int to_death;
    int count;
    int proom_gone;
    int visible_invisible;
    int between;
    SetupAction setup[4];
    int setup_count;
} TestCase;

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }
int roll(World *world, int number, int sides)
{
    int total = 0;
    while (number-- > 0)
        total += rnd(world, sides) + 1;
    return total;
}
int wandertime(World *world) { return 70 - 70 / 20 + rnd(world, 70 / 10); }
Ring ring_make(int which) { Ring ring = {1, which}; return ring; }

void marker(World *world, const char *value)
{
    strncpy(world->markers[world->marker_count], value, sizeof(world->markers[world->marker_count]) - 1);
    world->markers[world->marker_count][sizeof(world->markers[world->marker_count]) - 1] = '\0';
    world->marker_count++;
}

int is_ring(Ring *ring, int which) { return ring->present && ring->which == which; }

int d_slot(World *world)
{
    for (int i = 0; i < MAXDAEMONS; i++)
        if (world->actions[i].type == EMPTY)
            return i;
    return -1;
}

int find_slot(World *world, const char *action)
{
    for (int i = 0; i < MAXDAEMONS; i++)
        if (world->actions[i].type != EMPTY && strcmp(world->actions[i].action, action) == 0)
            return i;
    return -1;
}

void start_daemon(World *world, const char *action, int arg, int type)
{
    int index = d_slot(world);
    world->actions[index].type = type;
    world->actions[index].action = action;
    world->actions[index].arg = arg;
    world->actions[index].time = DAEMON;
}

void kill_daemon(World *world, const char *action)
{
    int index = find_slot(world, action);
    if (index >= 0)
        world->actions[index].type = EMPTY;
}

void fuse_action(World *world, const char *action, int arg, int time, int type)
{
    int index = d_slot(world);
    world->actions[index].type = type;
    world->actions[index].action = action;
    world->actions[index].arg = arg;
    world->actions[index].time = time;
}

void lengthen(World *world, const char *action, int xtime)
{
    int index = find_slot(world, action);
    if (index >= 0)
        world->actions[index].time += xtime;
}

void extinguish(World *world, const char *action)
{
    int index = find_slot(world, action);
    if (index >= 0)
        world->actions[index].type = EMPTY;
}

int ring_eat(World *world, Ring *ring)
{
    int uses[] = {1, 1, 1, -3, -5, 0, 0, -3, -3, 2, -2, 0, 1, 1};
    int eat;
    if (!ring->present)
        return 0;
    eat = uses[ring->which];
    if (eat < 0)
        eat = rnd(world, -eat) == 0;
    if (ring->which == R_DIGEST)
        eat = -eat;
    return eat;
}

void doctor(World *world)
{
    int level = world->stats.level;
    int old_hp = world->stats.hp;
    world->quiet++;
    if (level < 8)
    {
        if (world->quiet + (level << 1) > 20)
            world->stats.hp++;
    }
    else if (world->quiet >= 3)
        world->stats.hp += rnd(world, level - 7) + 1;
    if (is_ring(&world->left_ring, R_REGEN))
        world->stats.hp++;
    if (is_ring(&world->right_ring, R_REGEN))
        world->stats.hp++;
    if (old_hp != world->stats.hp)
    {
        if (world->stats.hp > world->max_hp)
            world->stats.hp = world->max_hp;
        world->quiet = 0;
    }
}

void swander(World *world) { start_daemon(world, "rollwand", 0, BEFORE); }

void rollwand(World *world)
{
    if (++world->between >= 4)
    {
        world->wander_roll = roll(world, 1, 6);
        world->has_wander_roll = 1;
        if (world->wander_roll == 4)
        {
            marker(world, "wanderer");
            kill_daemon(world, "rollwand");
            fuse_action(world, "swander", 0, wandertime(world), BEFORE);
        }
        world->between = 0;
    }
}

void unconfuse(World *world)
{
    world->player_flags &= ~ISHUH;
    marker(world, "msg_unconfuse");
}

void unsee(World *world)
{
    for (int i = 0; i < world->visible_invisible; i++)
        marker(world, "restore_invisible");
    world->player_flags &= ~CANSEE;
}

void sight(World *world)
{
    if (world->player_flags & ISBLIND)
    {
        extinguish(world, "sight");
        world->player_flags &= ~ISBLIND;
        if (!world->proom_gone)
            marker(world, "enter_room");
        marker(world, "msg_sight");
    }
}

void nohaste(World *world)
{
    world->player_flags &= ~ISHASTE;
    marker(world, "msg_nohaste");
}

void land(World *world)
{
    world->player_flags &= ~ISLEVIT;
    marker(world, "msg_land");
}

void stomach(World *world)
{
    int original_hungry = world->hungry_state;
    if (world->food_left <= 0)
    {
        if (world->food_left < -STARVETIME)
            marker(world, "death:s");
        world->food_left--;
        if (world->no_command || rnd(world, 5) != 0)
            return;
        world->faint_roll = rnd(world, 8) + 4;
        world->has_faint_roll = 1;
        world->no_command += world->faint_roll;
        world->hungry_state = 3;
        marker(world, "msg_faint");
    }
    else
    {
        int oldfood = world->food_left;
        world->food_left -= ring_eat(world, &world->left_ring) + ring_eat(world, &world->right_ring) + 1 - world->amulet;
        if (world->food_left < MORETIME && oldfood >= MORETIME)
        {
            world->hungry_state = 2;
            marker(world, "msg_weak");
        }
        else if (world->food_left < 2 * MORETIME && oldfood >= 2 * MORETIME)
        {
            world->hungry_state = 1;
            marker(world, "msg_hungry");
        }
    }
    if (world->hungry_state != original_hungry)
    {
        world->player_flags &= ~ISRUN;
        world->running = 0;
        world->to_death = 0;
        world->count = 0;
    }
}

void run_action(World *world, const char *action)
{
    if (strcmp(action, "doctor") == 0)
        doctor(world);
    else if (strcmp(action, "stomach") == 0)
        stomach(world);
    else if (strcmp(action, "swander") == 0)
        swander(world);
    else if (strcmp(action, "rollwand") == 0)
        rollwand(world);
    else if (strcmp(action, "sight") == 0)
        sight(world);
    else if (strcmp(action, "unconfuse") == 0)
        unconfuse(world);
    else if (strcmp(action, "unsee") == 0)
        unsee(world);
    else if (strcmp(action, "nohaste") == 0)
        nohaste(world);
    else if (strcmp(action, "land") == 0)
        land(world);
}

void do_daemons(World *world, int flag)
{
    DelayedAction snapshot[MAXDAEMONS];
    memcpy(snapshot, world->actions, sizeof(snapshot));
    for (int i = 0; i < MAXDAEMONS; i++)
        if (snapshot[i].type == flag && snapshot[i].time == DAEMON)
            run_action(world, snapshot[i].action);
}

void do_fuses(World *world, int flag)
{
    for (int i = 0; i < MAXDAEMONS; i++)
    {
        if (world->actions[i].type == flag && world->actions[i].time > 0 && --world->actions[i].time == 0)
        {
            const char *action = world->actions[i].action;
            world->actions[i].type = EMPTY;
            run_action(world, action);
        }
    }
}

TestCase base_case(const char *name, int seed, int op)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = seed;
    c.op = op;
    c.level = 5;
    c.hp = 10;
    c.max_hp = 20;
    c.player_flags = ISRUN;
    c.food_left = 1300;
    c.running = 1;
    c.to_death = 1;
    c.count = 3;
    return c;
}

SetupAction setup_start(const char *action, int type)
{
    SetupAction setup = {SETUP_START, action, type, 0, 0};
    return setup;
}

SetupAction setup_fuse(const char *action, int type, int time)
{
    SetupAction setup = {SETUP_FUSE, action, type, 0, time};
    return setup;
}

SetupAction setup_lengthen(const char *action, int time)
{
    SetupAction setup = {SETUP_LENGTHEN, action, 0, 0, time};
    return setup;
}

SetupAction setup_extinguish(const char *action)
{
    SetupAction setup = {SETUP_EXTINGUISH, action, 0, 0, 0};
    return setup;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->stats.level = c->level;
    world->stats.hp = c->hp;
    world->max_hp = c->max_hp;
    world->quiet = c->quiet;
    world->player_flags = c->player_flags;
    world->left_ring = c->left_ring;
    world->right_ring = c->right_ring;
    world->food_left = c->food_left;
    world->hungry_state = c->hungry_state;
    world->no_command = c->no_command;
    world->amulet = c->amulet;
    world->running = c->running;
    world->to_death = c->to_death;
    world->count = c->count;
    world->proom_gone = c->proom_gone;
    world->visible_invisible = c->visible_invisible;
    world->between = c->between;
}

void apply_setup(World *world, SetupAction *setup)
{
    if (setup->op == SETUP_START)
        start_daemon(world, setup->action, setup->arg, setup->type);
    else if (setup->op == SETUP_FUSE)
        fuse_action(world, setup->action, setup->arg, setup->time, setup->type);
    else if (setup->op == SETUP_LENGTHEN)
        lengthen(world, setup->action, setup->time);
    else if (setup->op == SETUP_EXTINGUISH)
        extinguish(world, setup->action);
}

void run_case_action(World *world, TestCase *c)
{
    if (c->op == OP_DOCTOR)
        doctor(world);
    else if (c->op == OP_STOMACH)
        stomach(world);
    else if (c->op == OP_SWANDER)
        swander(world);
    else if (c->op == OP_ROLLWAND)
        rollwand(world);
    else if (c->op == OP_DO_DAEMONS)
        do_daemons(world, c->flag);
    else if (c->op == OP_DO_FUSES)
        do_fuses(world, c->flag);
    else if (c->op == OP_UNCONFUSE)
        unconfuse(world);
    else if (c->op == OP_UNSEE)
        unsee(world);
    else if (c->op == OP_SIGHT)
        sight(world);
    else if (c->op == OP_NOHASTE)
        nohaste(world);
    else if (c->op == OP_LAND)
        land(world);
}

void print_bool(int value) { printf(value ? "true" : "false"); }
void print_action(DelayedAction *action)
{
    printf("{\"action\":\"%s\",\"type\":%d,\"arg\":%d,\"time\":%d}", action->action, action->type, action->arg, action->time);
}
void print_case(TestCase *c)
{
    World world;
    world_init(&world, c);
    for (int i = 0; i < c->setup_count; i++)
        apply_setup(&world, &c->setup[i]);
    run_case_action(&world, c);
    printf("{\"name\":\"%s\",\"seed\":%d,\"world\":{\"rng_seed\":%d,\"stats\":{\"level\":%d,\"hp\":%d},\"max_hp\":%d,\"quiet\":%d,\"player_flags\":%d,\"food_left\":%d,\"hungry_state\":%d,\"no_command\":%d,\"running\":",
        c->name, c->seed, world.seed, world.stats.level, world.stats.hp, world.max_hp, world.quiet, world.player_flags, world.food_left, world.hungry_state, world.no_command);
    print_bool(world.running);
    printf(",\"to_death\":");
    print_bool(world.to_death);
    printf(",\"count\":%d,\"between\":%d,\"actions\":[", world.count, world.between);
    int first = 1;
    for (int i = 0; i < MAXDAEMONS; i++)
        if (world.actions[i].type != EMPTY)
        {
            if (!first) printf(",");
            first = 0;
            print_action(&world.actions[i]);
        }
    printf("],\"markers\":[");
    for (int i = 0; i < world.marker_count; i++)
    {
        if (i) printf(",");
        printf("\"%s\"", world.markers[i]);
    }
    printf("],\"trace\":{\"wander_roll\":");
    if (world.has_wander_roll) printf("%d", world.wander_roll); else printf("null");
    printf(",\"faint_roll\":");
    if (world.has_faint_roll) printf("%d", world.faint_roll); else printf("null");
    printf("}}}");
}

int main(void)
{
    TestCase cases[18];
    int count = 0;
    cases[count] = base_case("doctor_low_level_waits", 1, OP_DOCTOR); cases[count].level = 3; cases[count].hp = 10; cases[count].max_hp = 20; cases[count].quiet = 13; count++;
    cases[count] = base_case("doctor_low_level_heals", 1, OP_DOCTOR); cases[count].level = 3; cases[count].hp = 10; cases[count].max_hp = 20; cases[count].quiet = 14; count++;
    cases[count] = base_case("doctor_high_regen_caps", 7, OP_DOCTOR); cases[count].level = 10; cases[count].hp = 19; cases[count].max_hp = 20; cases[count].quiet = 2; cases[count].left_ring = ring_make(R_REGEN); cases[count].right_ring = ring_make(R_REGEN); count++;
    cases[count] = base_case("stomach_gets_hungry", 1, OP_STOMACH); cases[count].food_left = 300; cases[count].left_ring = ring_make(R_REGEN); count++;
    cases[count] = base_case("stomach_gets_weak", 1, OP_STOMACH); cases[count].food_left = 150; count++;
    cases[count] = base_case("stomach_faints", 1, OP_STOMACH); cases[count].food_left = 0; cases[count].hungry_state = 2; cases[count].player_flags = ISRUN; cases[count].running = 1; cases[count].to_death = 1; cases[count].count = 3; count++;
    cases[count] = base_case("stomach_starves", 1, OP_STOMACH); cases[count].food_left = -851; cases[count].no_command = 1; count++;
    cases[count] = base_case("swander_starts_rollwand", 1, OP_SWANDER); count++;
    cases[count] = base_case("rollwand_wanderer", 17, OP_ROLLWAND); cases[count].between = 3; cases[count].setup[cases[count].setup_count++] = setup_start("rollwand", BEFORE); count++;
    cases[count] = base_case("do_daemons_runs_doctor", 1, OP_DO_DAEMONS); cases[count].flag = AFTER; cases[count].level = 3; cases[count].hp = 10; cases[count].max_hp = 20; cases[count].quiet = 14; cases[count].setup[cases[count].setup_count++] = setup_start("doctor", AFTER); count++;
    cases[count] = base_case("do_fuses_runs_sight", 1, OP_DO_FUSES); cases[count].flag = AFTER; cases[count].player_flags = ISRUN | ISBLIND; cases[count].setup[cases[count].setup_count++] = setup_fuse("sight", AFTER, 1); count++;
    cases[count] = base_case("lengthen_fuse_waits", 1, OP_DO_FUSES); cases[count].flag = AFTER; cases[count].player_flags = ISRUN | ISBLIND; cases[count].setup[cases[count].setup_count++] = setup_fuse("sight", AFTER, 1); cases[count].setup[cases[count].setup_count++] = setup_lengthen("sight", 2); count++;
    cases[count] = base_case("extinguish_fuse_removes", 1, OP_DO_FUSES); cases[count].flag = AFTER; cases[count].player_flags = ISRUN | ISBLIND; cases[count].setup[cases[count].setup_count++] = setup_fuse("sight", AFTER, 1); cases[count].setup[cases[count].setup_count++] = setup_extinguish("sight"); count++;
    cases[count] = base_case("unconfuse_clears_flag", 1, OP_UNCONFUSE); cases[count].player_flags = ISRUN | ISHUH; count++;
    cases[count] = base_case("unsee_restores_invisible", 1, OP_UNSEE); cases[count].player_flags = ISRUN | CANSEE; cases[count].visible_invisible = 2; count++;
    cases[count] = base_case("sight_clears_blind", 1, OP_SIGHT); cases[count].player_flags = ISRUN | ISBLIND; cases[count].setup[cases[count].setup_count++] = setup_fuse("sight", AFTER, 5); count++;
    cases[count] = base_case("nohaste_clears_haste", 1, OP_NOHASTE); cases[count].player_flags = ISRUN | ISHASTE; count++;
    cases[count] = base_case("land_clears_levitation", 1, OP_LAND); cases[count].player_flags = ISRUN | ISLEVIT; count++;
    printf("{\"schema\":\"gamebench.rogue.source_daemons.v1\",\"cases\":[");
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
    return _project(source_daemons_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_daemons",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-daemons-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_daemons.c"
        binary = temp / "source_daemons"
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
                    "stats": case["world"]["stats"],
                    "max_hp": case["world"]["max_hp"],
                    "quiet": case["world"]["quiet"],
                    "player_flags": case["world"]["player_flags"],
                    "food_left": case["world"]["food_left"],
                    "hungry_state": case["world"]["hungry_state"],
                    "no_command": case["world"]["no_command"],
                    "running": case["world"]["running"],
                    "to_death": case["world"]["to_death"],
                    "count": case["world"]["count"],
                    "between": case["world"]["between"],
                    "actions": case["world"]["actions"],
                    "markers": case["world"]["markers"],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_daemons.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source daemons mismatch")


if __name__ == "__main__":
    main()
