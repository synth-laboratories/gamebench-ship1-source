#!/usr/bin/env python3
"""Compare source-derived Rogue ring branches across C, Python, and Rust."""

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

from source_rings import source_rings_report


TRACE_KEYS = ["eat"]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LEFT 0
#define RIGHT 1

#define ISCURSED 0000001
#define ISKNOW 0000002

#define RING '='

#define R_PROTECT 0
#define R_ADDSTR 1
#define R_SUSTSTR 2
#define R_SEARCH 3
#define R_SEEINVIS 4
#define R_NOP 5
#define R_AGGR 6
#define R_ADDHIT 7
#define R_ADDDAM 8
#define R_REGEN 9
#define R_DIGEST 10
#define R_TELEPORT 11
#define R_STEALTH 12
#define R_SUSTARM 13

#define OP_RING_ON 1
#define OP_RING_OFF 2
#define OP_DROPCHECK 3
#define OP_RING_EAT 4
#define OP_RING_NUM 5

#define RESULT_NULL 0
#define RESULT_BOOL 1
#define RESULT_INT 2
#define RESULT_STRING 3

typedef struct ring_object {
    int present;
    const char *id;
    char type;
    int which;
    int arm;
    int flags;
    char packch;
} RingObject;

typedef struct world {
    int seed;
    int strength;
    RingObject left_ring;
    RingObject right_ring;
    int selected_hand;
    char markers[32][64];
    int marker_count;
    int has_eat;
    int eat;
} World;

typedef struct test_case {
    const char *name;
    int seed;
    int op;
    int strength;
    RingObject left_ring;
    RingObject right_ring;
    int selected_hand;
    int hand;
    RingObject obj;
} TestCase;

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }

RingObject no_ring(void)
{
    RingObject obj = {0, "", RING, R_NOP, 0, 0, 'a'};
    return obj;
}

RingObject ring_make(const char *id, char type, int which, int arm, int flags, char packch)
{
    RingObject obj = {1, id, type, which, arm, flags, packch};
    return obj;
}

void marker(World *world, const char *value)
{
    strncpy(world->markers[world->marker_count], value, sizeof(world->markers[world->marker_count]) - 1);
    world->markers[world->marker_count][sizeof(world->markers[world->marker_count]) - 1] = '\0';
    world->marker_count++;
}

int same_obj(RingObject *left, RingObject *right)
{
    return left->present && right->present && strcmp(left->id, right->id) == 0;
}

int is_current(World *world, RingObject *obj)
{
    return same_obj(&world->left_ring, obj) || same_obj(&world->right_ring, obj);
}

int current_hand(World *world, RingObject *obj)
{
    if (same_obj(&world->left_ring, obj))
        return LEFT;
    if (same_obj(&world->right_ring, obj))
        return RIGHT;
    return -1;
}

void add_ring_marker(World *world, const char *prefix, int ring)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "%s%d", prefix, ring);
    marker(world, buf);
}

void add_pack_marker(World *world, const char *prefix, char packch)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "%s%c", prefix, packch);
    marker(world, buf);
}

void ring_on(World *world, RingObject *obj)
{
    int ring;
    if (!obj->present)
        return;
    if (obj->type != RING)
    {
        marker(world, "not_ring");
        return;
    }
    if (is_current(world, obj))
    {
        marker(world, "in_use");
        return;
    }
    if (!world->left_ring.present && !world->right_ring.present)
    {
        ring = world->selected_hand;
        if (ring < 0)
        {
            marker(world, "gethand_cancelled");
            return;
        }
    }
    else if (!world->left_ring.present)
        ring = LEFT;
    else if (!world->right_ring.present)
        ring = RIGHT;
    else
    {
        marker(world, "wearing_two");
        return;
    }
    if (ring == LEFT)
        world->left_ring = *obj;
    else
        world->right_ring = *obj;
    if (obj->which == R_ADDSTR)
    {
        world->strength += obj->arm;
        marker(world, "chg_str");
    }
    else if (obj->which == R_SEEINVIS)
        marker(world, "invis_on");
    else if (obj->which == R_AGGR)
        marker(world, "aggravate");
    add_ring_marker(world, "wear:", ring);
}

int dropcheck(World *world, RingObject *obj)
{
    int hand;
    if (!obj->present)
        return 1;
    hand = current_hand(world, obj);
    if (hand < 0)
        return 1;
    if (obj->flags & ISCURSED)
    {
        marker(world, "cursed");
        return 0;
    }
    if (hand == LEFT)
        world->left_ring.present = 0;
    else
        world->right_ring.present = 0;
    if (obj->which == R_ADDSTR)
    {
        world->strength -= obj->arm;
        marker(world, "chg_str");
    }
    else if (obj->which == R_SEEINVIS)
    {
        marker(world, "unsee");
        marker(world, "extinguish_unsee");
    }
    return 1;
}

void ring_off(World *world)
{
    int ring;
    RingObject obj;
    if (!world->left_ring.present && !world->right_ring.present)
    {
        marker(world, "no_rings");
        return;
    }
    else if (!world->left_ring.present)
        ring = RIGHT;
    else if (!world->right_ring.present)
        ring = LEFT;
    else
    {
        ring = world->selected_hand;
        if (ring < 0)
        {
            marker(world, "gethand_cancelled");
            return;
        }
    }
    obj = ring == LEFT ? world->left_ring : world->right_ring;
    if (!obj.present)
    {
        marker(world, "not_wearing");
        return;
    }
    if (dropcheck(world, &obj))
        add_pack_marker(world, "was_wearing:", obj.packch);
}

int ring_eat(World *world, int hand)
{
    int uses[] = {1, 1, 1, -3, -5, 0, 0, -3, -3, 2, -2, 0, 1, 1};
    int eat;
    RingObject *ring = hand == LEFT ? &world->left_ring : &world->right_ring;
    if (!ring->present)
        return 0;
    eat = uses[ring->which];
    if (eat < 0)
        eat = rnd(world, -eat) == 0;
    if (ring->which == R_DIGEST)
        eat = -eat;
    world->eat = eat;
    world->has_eat = 1;
    return eat;
}

const char *num(int value)
{
    static char buf[16];
    if (value < 0)
        snprintf(buf, sizeof(buf), "%d", value);
    else
        snprintf(buf, sizeof(buf), "+%d", value);
    return buf;
}

const char *ring_num(RingObject *obj)
{
    static char buf[32];
    if (!(obj->flags & ISKNOW))
        return "";
    switch (obj->which)
    {
        case R_PROTECT:
        case R_ADDSTR:
        case R_ADDDAM:
        case R_ADDHIT:
            snprintf(buf, sizeof(buf), " [%s]", num(obj->arm));
            return buf;
        default:
            return "";
    }
}

TestCase base_case(const char *name, int seed, int op)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = seed;
    c.op = op;
    c.strength = 16;
    c.selected_hand = LEFT;
    c.hand = LEFT;
    c.left_ring = no_ring();
    c.right_ring = no_ring();
    c.obj = no_ring();
    return c;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->strength = c->strength;
    world->left_ring = c->left_ring;
    world->right_ring = c->right_ring;
    world->selected_hand = c->selected_hand;
}

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

void print_ring(RingObject *ring)
{
    if (!ring->present)
    {
        printf("null");
        return;
    }
    printf("{\"id\":");
    print_string(ring->id);
    printf(",\"type\":\"%c\",\"which\":%d,\"arm\":%d,\"flags\":%d,\"packch\":\"%c\"}", ring->type, ring->which, ring->arm, ring->flags, ring->packch);
}

void print_result(int type, int int_value, const char *str_value)
{
    if (type == RESULT_NULL)
        printf("null");
    else if (type == RESULT_BOOL)
        printf(int_value ? "true" : "false");
    else if (type == RESULT_INT)
        printf("%d", int_value);
    else
        print_string(str_value);
}

void print_case(TestCase *c)
{
    World world;
    int result_type = RESULT_NULL;
    int int_result = 0;
    const char *str_result = "";
    world_init(&world, c);
    if (c->op == OP_RING_ON)
        ring_on(&world, &c->obj);
    else if (c->op == OP_RING_OFF)
        ring_off(&world);
    else if (c->op == OP_DROPCHECK)
    {
        int_result = dropcheck(&world, &c->obj);
        result_type = RESULT_BOOL;
    }
    else if (c->op == OP_RING_EAT)
    {
        int_result = ring_eat(&world, c->hand);
        result_type = RESULT_INT;
    }
    else if (c->op == OP_RING_NUM)
    {
        str_result = ring_num(&c->obj);
        result_type = RESULT_STRING;
    }
    printf("{\"name\":");
    print_string(c->name);
    printf(",\"seed\":%d,\"result\":", c->seed);
    print_result(result_type, int_result, str_result);
    printf(",\"world\":{\"rng_seed\":%d,\"strength\":%d,\"left_ring\":", world.seed, world.strength);
    print_ring(&world.left_ring);
    printf(",\"right_ring\":");
    print_ring(&world.right_ring);
    printf(",\"markers\":[");
    for (int i = 0; i < world.marker_count; i++)
    {
        if (i)
            printf(",");
        print_string(world.markers[i]);
    }
    printf("],\"trace\":{\"eat\":");
    if (world.has_eat)
        printf("%d", world.eat);
    else
        printf("null");
    printf("}}}");
}

int main(void)
{
    TestCase cases[18];
    int count = 0;
    cases[count] = base_case("wear_addstr_chosen_left", 1, OP_RING_ON); cases[count].selected_hand = LEFT; cases[count].obj = ring_make("addstr", RING, R_ADDSTR, 2, 0, 'a'); count++;
    cases[count] = base_case("wear_seeinvis_auto_right", 1, OP_RING_ON); cases[count].left_ring = ring_make("left", RING, R_PROTECT, 1, 0, 'l'); cases[count].obj = ring_make("see", RING, R_SEEINVIS, 0, 0, 'b'); count++;
    cases[count] = base_case("wear_aggravate_auto_left", 1, OP_RING_ON); cases[count].right_ring = ring_make("right", RING, R_PROTECT, 1, 0, 'r'); cases[count].obj = ring_make("aggr", RING, R_AGGR, 0, 0, 'c'); count++;
    cases[count] = base_case("wear_non_ring_rejected", 1, OP_RING_ON); cases[count].obj = ring_make("food", ':', R_NOP, 0, 0, 'a'); count++;
    cases[count] = base_case("wear_current_rejected", 1, OP_RING_ON); cases[count].left_ring = ring_make("same", RING, R_PROTECT, 1, 0, 'a'); cases[count].obj = ring_make("same", RING, R_PROTECT, 1, 0, 'a'); count++;
    cases[count] = base_case("wear_two_rejected", 1, OP_RING_ON); cases[count].left_ring = ring_make("left", RING, R_PROTECT, 1, 0, 'a'); cases[count].right_ring = ring_make("right", RING, R_ADDHIT, 1, 0, 'a'); cases[count].obj = ring_make("third", RING, R_REGEN, 0, 0, 'a'); count++;
    cases[count] = base_case("off_no_rings", 1, OP_RING_OFF); count++;
    cases[count] = base_case("off_addstr_uncursed", 1, OP_RING_OFF); cases[count].strength = 18; cases[count].left_ring = ring_make("addstr", RING, R_ADDSTR, 2, 0, 'a'); count++;
    cases[count] = base_case("off_cursed_keeps_ring", 1, OP_RING_OFF); cases[count].left_ring = ring_make("bad", RING, R_ADDSTR, 2, ISCURSED, 'b'); count++;
    cases[count] = base_case("off_seeinvis_unsee", 1, OP_RING_OFF); cases[count].right_ring = ring_make("see", RING, R_SEEINVIS, 0, 0, 'c'); count++;
    cases[count] = base_case("eat_none", 1, OP_RING_EAT); cases[count].hand = LEFT; count++;
    cases[count] = base_case("eat_regen", 1, OP_RING_EAT); cases[count].hand = LEFT; cases[count].left_ring = ring_make("regen", RING, R_REGEN, 0, 0, 'a'); count++;
    cases[count] = base_case("eat_search_random", 1, OP_RING_EAT); cases[count].hand = LEFT; cases[count].left_ring = ring_make("search", RING, R_SEARCH, 0, 0, 'a'); count++;
    cases[count] = base_case("eat_digest_negative", 1, OP_RING_EAT); cases[count].hand = LEFT; cases[count].left_ring = ring_make("digest", RING, R_DIGEST, 0, 0, 'a'); count++;
    cases[count] = base_case("num_unknown", 1, OP_RING_NUM); cases[count].obj = ring_make("unk", RING, R_ADDSTR, 2, 0, 'a'); count++;
    cases[count] = base_case("num_addhit_positive", 1, OP_RING_NUM); cases[count].obj = ring_make("hit", RING, R_ADDHIT, 3, ISKNOW, 'a'); count++;
    cases[count] = base_case("num_adddam_negative", 1, OP_RING_NUM); cases[count].obj = ring_make("dam", RING, R_ADDDAM, -1, ISKNOW, 'a'); count++;
    cases[count] = base_case("num_regen_empty", 1, OP_RING_NUM); cases[count].obj = ring_make("regen", RING, R_REGEN, 0, ISKNOW, 'a'); count++;
    printf("{\"schema\":\"gamebench.rogue.source_rings.v1\",\"cases\":[");
    for (int i = 0; i < count; i++)
    {
        if (i)
            printf(",");
        print_case(&cases[i]);
    }
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return _project(source_rings_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_rings",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-rings-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_rings.c"
        binary = temp / "source_rings"
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
                    "strength": case["world"]["strength"],
                    "left_ring": case["world"]["left_ring"],
                    "right_ring": case["world"]["right_ring"],
                    "markers": case["world"]["markers"],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_rings.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source rings mismatch")


if __name__ == "__main__":
    main()
