#!/usr/bin/env python3
"""Compare source-derived Rogue pack semantics across C, Python, and Rust."""

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

from source_pack import source_pack_report


C_SOURCE = r'''
#include <stdio.h>
#include <string.h>

#define MAXPACK 23
#define ISFOUND 0000020
#define AMULET ','
#define ARMOR ']'
#define FOOD ':'
#define POTION '!'
#define SCROLL '?'
#define WEAPON ')'
#define S_SCARE 10

typedef struct object {
    int id;
    char type;
    int which;
    int count;
    int group;
    int flags;
    char packch;
    int y;
    int x;
} Object;

typedef struct state {
    Object objects[512];
    int next_id;
    int pack[256];
    int pack_count;
    int level_objects[256];
    int level_count;
    int discarded[256];
    int discarded_count;
    Object returned[256];
    int returned_count;
    int inpack;
    int pack_used[26];
    int amulet;
    int last_pick;
} State;

static State st;

void init_state(void)
{
    memset(&st, 0, sizeof(st));
    st.next_id = 1;
    st.last_pick = -1;
}

Object *obj_by_id(int id)
{
    for (int i = 0; i < st.next_id; i++)
        if (st.objects[i].id == id)
            return &st.objects[i];
    return NULL;
}

int make_obj(char type, int which, int count, int group, int flags, int y, int x)
{
    Object *obj = &st.objects[st.next_id];
    obj->id = st.next_id;
    obj->type = type;
    obj->which = which;
    obj->count = count;
    obj->group = group;
    obj->flags = flags;
    obj->packch = 0;
    obj->y = y;
    obj->x = x;
    st.next_id++;
    return obj->id;
}

void add_floor(int id)
{
    for (int i = st.level_count; i > 0; i--)
        st.level_objects[i] = st.level_objects[i - 1];
    st.level_objects[0] = id;
    st.level_count++;
}

void detach_level_object(int id)
{
    int index = -1;
    for (int i = 0; i < st.level_count; i++)
        if (st.level_objects[i] == id)
            index = i;
    if (index < 0)
        return;
    for (int i = index; i + 1 < st.level_count; i++)
        st.level_objects[i] = st.level_objects[i + 1];
    st.level_count--;
}

void insert_pack_after(int index, int id)
{
    for (int i = st.pack_count; i > index + 1; i--)
        st.pack[i] = st.pack[i - 1];
    st.pack[index + 1] = id;
    st.pack_count++;
}

void append_pack(int id)
{
    st.pack[st.pack_count++] = id;
}

void remove_pack_index(int index)
{
    for (int i = index; i + 1 < st.pack_count; i++)
        st.pack[i] = st.pack[i + 1];
    st.pack_count--;
}

int pack_index_by_id(int id)
{
    for (int i = 0; i < st.pack_count; i++)
        if (st.pack[i] == id)
            return i;
    return -1;
}

int is_mult(char type)
{
    return type == POTION || type == SCROLL || type == FOOD;
}

char pack_char(void)
{
    for (int i = 0; i < 26; i++)
        if (!st.pack_used[i])
        {
            st.pack_used[i] = 1;
            return (char)('a' + i);
        }
    return '?';
}

int pack_room(int from_floor, int id)
{
    st.inpack++;
    if (st.inpack > MAXPACK)
    {
        st.inpack = MAXPACK;
        return 0;
    }
    if (from_floor)
        detach_level_object(id);
    return 1;
}

const char *add_pack(int id, int from_floor)
{
    Object *obj = obj_by_id(id);
    int final_id = id;

    if (obj->type == SCROLL && obj->which == S_SCARE && (obj->flags & ISFOUND))
    {
        if (from_floor)
            detach_level_object(id);
        st.discarded[st.discarded_count++] = id;
        return "scare_dust";
    }

    if (st.pack_count == 0)
    {
        obj->packch = pack_char();
        st.inpack++;
        append_pack(id);
    }
    else
    {
        int lp_index = -1;
        int op_index = 0;
        while (op_index < st.pack_count)
        {
            Object *op = obj_by_id(st.pack[op_index]);
            if (op->type != obj->type)
            {
                lp_index = op_index;
                op_index++;
                continue;
            }
            while (op->type == obj->type && op->which != obj->which)
            {
                lp_index = op_index;
                if (op_index + 1 == st.pack_count)
                    break;
                op_index++;
                op = obj_by_id(st.pack[op_index]);
            }
            if (op->type == obj->type && op->which == obj->which)
            {
                if (is_mult(op->type))
                {
                    if (!pack_room(from_floor, id))
                        return "no_room";
                    op->count++;
                    st.discarded[st.discarded_count++] = id;
                    final_id = op->id;
                    lp_index = -1;
                    break;
                }
                else if (obj->group)
                {
                    lp_index = op_index;
                    while (op->type == obj->type && op->which == obj->which && op->group != obj->group)
                    {
                        lp_index = op_index;
                        if (op_index + 1 == st.pack_count)
                            break;
                        op_index++;
                        op = obj_by_id(st.pack[op_index]);
                    }
                    if (op->type == obj->type && op->which == obj->which && op->group == obj->group)
                    {
                        op->count += obj->count;
                        st.inpack--;
                        if (!pack_room(from_floor, id))
                            return "no_room";
                        st.discarded[st.discarded_count++] = id;
                        final_id = op->id;
                        lp_index = -1;
                        break;
                    }
                }
                else
                    lp_index = op_index;
            }
            break;
        }
        if (lp_index >= 0)
        {
            if (!pack_room(from_floor, id))
                return "no_room";
            obj->packch = pack_char();
            insert_pack_after(lp_index, id);
        }
    }

    obj_by_id(final_id)->flags |= ISFOUND;
    if (obj_by_id(final_id)->type == AMULET)
        st.amulet = 1;
    return "added";
}

Object leave_pack(int id, int newobj, int all_items)
{
    int index = pack_index_by_id(id);
    Object *obj = obj_by_id(id);
    Object returned;
    st.inpack--;
    if (obj->count > 1 && !all_items)
    {
        st.last_pick = obj->id;
        obj->count--;
        if (obj->group)
            st.inpack++;
        if (newobj)
        {
            returned = *obj;
            returned.id = st.next_id;
            returned.count = 1;
            st.objects[st.next_id] = returned;
            st.next_id++;
        }
        else
            returned = *obj;
    }
    else
    {
        st.last_pick = -1;
        if (obj->packch)
            st.pack_used[obj->packch - 'a'] = 0;
        returned = *obj;
        remove_pack_index(index);
    }
    st.returned[st.returned_count++] = returned;
    return returned;
}

void print_object(Object *obj)
{
    printf("{\"id\":%d,\"type\":\"%c\",\"which\":%d,\"count\":%d,\"group\":%d,\"flags\":%d,\"packch\":", obj->id, obj->type, obj->which, obj->count, obj->group, obj->flags);
    if (obj->packch)
        printf("\"%c\"", obj->packch);
    else
        printf("\"\"");
    printf(",\"pos\":[%d,%d]}", obj->y, obj->x);
}

void print_object_by_id(int id)
{
    print_object(obj_by_id(id));
}

void print_state(void)
{
    printf("{\"pack\":[");
    for (int i = 0; i < st.pack_count; i++)
    {
        if (i)
            printf(",");
        print_object_by_id(st.pack[i]);
    }
    printf("],\"level_objects\":[");
    for (int i = 0; i < st.level_count; i++)
    {
        if (i)
            printf(",");
        print_object_by_id(st.level_objects[i]);
    }
    printf("],\"discarded\":[");
    for (int i = 0; i < st.discarded_count; i++)
    {
        if (i)
            printf(",");
        printf("%d", st.discarded[i]);
    }
    printf("],\"returned\":[");
    for (int i = 0; i < st.returned_count; i++)
    {
        if (i)
            printf(",");
        print_object(&st.returned[i]);
    }
    printf("],\"inpack\":%d,\"pack_used\":\"", st.inpack);
    for (int i = 0; i < 26; i++)
        if (st.pack_used[i])
            putchar((char)('a' + i));
    printf("\",\"amulet\":%s,\"last_pick\":", st.amulet ? "true" : "false");
    if (st.last_pick < 0)
        printf("null");
    else
        printf("%d", st.last_pick);
    printf("}");
}

void print_case_initial_order(void)
{
    init_state();
    add_pack(make_obj(FOOD, 0, 1, 0, 0, 0, 0), 0);
    add_pack(make_obj(ARMOR, 1, 1, 0, 0, 0, 0), 0);
    add_pack(make_obj(WEAPON, 0, 1, 0, 0, 0, 0), 0);
    add_pack(make_obj(WEAPON, 2, 1, 0, 0, 0, 0), 0);
    add_pack(make_obj(WEAPON, 3, 31, 2, 0, 0, 0), 0);
    printf("{\"name\":\"initial_order\",\"state\":");
    print_state();
    printf("}");
}

void print_case_multi_merge(void)
{
    init_state();
    int first = make_obj(FOOD, 0, 1, 0, 0, 0, 0);
    int second = make_obj(FOOD, 0, 1, 0, 0, 0, 0);
    add_pack(first, 0);
    add_pack(second, 0);
    leave_pack(first, 1, 0);
    printf("{\"name\":\"multi_merge_leave_one\",\"state\":");
    print_state();
    printf("}");
}

void print_case_group_merge_split(void)
{
    init_state();
    int arrows = make_obj(WEAPON, 3, 10, 7, 0, 0, 0);
    int same_group = make_obj(WEAPON, 3, 5, 7, 0, 0, 0);
    int other_group = make_obj(WEAPON, 3, 4, 8, 0, 0, 0);
    add_pack(arrows, 0);
    add_pack(same_group, 0);
    add_pack(other_group, 0);
    leave_pack(arrows, 1, 0);
    printf("{\"name\":\"group_merge_split\",\"state\":");
    print_state();
    printf("}");
}

void print_case_pack_overflow(void)
{
    init_state();
    for (int i = 0; i < MAXPACK; i++)
        add_pack(make_obj(ARMOR, i, 1, 0, 0, 0, 0), 0);
    int extra = make_obj(ARMOR, 99, 1, 0, 0, 0, 0);
    const char *result = add_pack(extra, 0);
    printf("{\"name\":\"pack_overflow\",\"result\":\"%s\",\"state\":", result);
    print_state();
    printf(",\"extra\":");
    print_object_by_id(extra);
    printf("}");
}

void print_case_scare_scroll_dust(void)
{
    init_state();
    int scroll = make_obj(SCROLL, S_SCARE, 1, 0, ISFOUND, 3, 4);
    add_floor(scroll);
    const char *result = add_pack(scroll, 1);
    printf("{\"name\":\"scare_scroll_dust\",\"result\":\"%s\",\"state\":", result);
    print_state();
    printf("}");
}

void print_case_leave_all(void)
{
    init_state();
    int food = make_obj(FOOD, 0, 3, 0, 0, 0, 0);
    add_pack(food, 0);
    leave_pack(food, 0, 1);
    add_pack(make_obj(POTION, 2, 1, 0, 0, 0, 0), 0);
    printf("{\"name\":\"leave_all_reuses_packch\",\"state\":");
    print_state();
    printf("}");
}

void print_case_amulet(void)
{
    init_state();
    add_pack(make_obj(AMULET, 0, 1, 0, 0, 0, 0), 0);
    printf("{\"name\":\"amulet_flag\",\"state\":");
    print_state();
    printf("}");
}

int main(void)
{
    printf("{\"cases\":[");
    print_case_initial_order();
    printf(",");
    print_case_multi_merge();
    printf(",");
    print_case_group_merge_split();
    printf(",");
    print_case_pack_overflow();
    printf(",");
    print_case_scare_scroll_dust();
    printf(",");
    print_case_leave_all();
    printf(",");
    print_case_amulet();
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_pack_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_pack",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-pack-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_pack.c"
        binary = temp / "source_pack"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_pack.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source pack mismatch")


if __name__ == "__main__":
    main()
