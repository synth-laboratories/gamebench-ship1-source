#!/usr/bin/env python3
"""Compare source-derived Rogue trap consequences across C, Python, and Rust."""

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

from source_traps import source_traps_report


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>

#define F_SEEN 0x40
#define F_REAL 0x10
#define F_TMASK 0x07

#define T_DOOR 0
#define T_ARROW 1
#define T_SLEEP 2
#define T_BEAR 3
#define T_TELEP 4
#define T_DART 5
#define T_RUST 6
#define T_MYST 7

#define VS_POISON 0

#define ISBLIND 0000004
#define ISLEVIT 0000010
#define ISRUN 0020000
#define ISHALU 0004000
#define ISMISL 0000004
#define ISMANY 0000010
#define ISPROT 0000040

#define LEATHER 0

#define R_ADDSTR 1
#define R_SUSTSTR 2
#define R_SUSTARM 13

#define TRAP '^'
#define DOOR '+'
#define PASSAGE '#'
#define WEAPON ')'
#define ARMOR ']'

#define ARROW 3
#define DAGGER 4

typedef struct stats {
    int strength;
    int max_strength;
    int level;
    int arm;
    int hp;
    int max_hp;
} Stats;

typedef struct ring {
    int present;
    int which;
    int arm;
} Ring;

typedef struct armor {
    int present;
    char type;
    int which;
    int arm;
    int flags;
} Armor;

typedef struct object {
    int present;
    char type;
    int which;
    int count;
    int group;
    int flags;
    int y;
    int x;
    int init_count;
} Object;

typedef struct swing_payload {
    int present;
    int roll;
    int need;
    int hit;
    int rng_seed;
} SwingPayload;

typedef struct save_payload {
    int present;
    int which;
    int level;
    int need;
    int roll;
    int saved;
    int rng_seed;
} SavePayload;

typedef struct state {
    int seed;
    int level;
    int no_move;
    int no_command;
    int player_flags;
    Stats stats;
    char cell_ch;
    int cell_flags;
    int running;
    int count;
    int weapon_group;
    int hero_y;
    int hero_x;
    Ring left_ring;
    Ring right_ring;
    Armor armor;
    Object arrow;
    const char *markers[16];
    int marker_count;
    int terminal;
    int has_mystery_roll;
    int mystery_roll;
    int has_color;
    int color_index;
    const char *color;
    SwingPayload arrow_swing;
    int has_arrow_damage;
    int arrow_damage;
    SwingPayload dart_swing;
    int has_dart_damage;
    int dart_damage;
    SavePayload poison_save;
} State;

typedef struct trap_case {
    const char *name;
    int seed;
    int trap_kind;
    int level;
    int no_move;
    int no_command;
    int player_flags;
    Stats stats;
    int weapon_group;
    Ring left_ring;
    Ring right_ring;
    Armor armor;
} TrapCase;

typedef struct trap_return {
    int present;
    int value;
} TrapReturn;

typedef struct search_trap {
    const char *id;
    int row;
    int col;
    int kind;
    int flags;
    char ch;
    int weapon_group;
} SearchTrap;

typedef struct search_cell {
    const char *id;
    int row;
    int col;
    char ch;
    int flags;
} SearchCell;

typedef struct search_case {
    const char *name;
    int seed;
    int hero_y;
    int hero_x;
    int player_flags;
    SearchTrap traps[4];
    int trap_count;
    SearchCell map_cells[4];
    int map_cell_count;
} SearchCase;

typedef struct search_result {
    int seed;
    int found;
    SearchTrap traps[4];
    int trap_count;
    SearchCell map_cells[4];
    int map_cell_count;
    char markers[16][96];
    int marker_count;
} SearchResult;

static int init_weapon_flags[9] = {0, 0, 0, ISMANY|ISMISL, ISMISL|ISMISL, 0, ISMANY|ISMISL, ISMANY|ISMISL, ISMISL};
static const char *rainbow[27] = {
    "amber", "aquamarine", "black", "blue", "brown", "clear", "crimson", "cyan", "ecru",
    "gold", "green", "grey", "magenta", "orange", "pink", "plaid", "purple", "red",
    "silver", "tan", "tangerine", "topaz", "turquoise", "vermilion", "violet", "white", "yellow"
};

#define RN (((st->seed = st->seed*11109+13849) >> 16) & 0xffff)

int rnd(State *st, int range)
{
    return range == 0 ? 0 : abs((int) RN) % range;
}

int roll(State *st, int number, int sides)
{
    int total = 0;
    while (number--)
        total += rnd(st, sides) + 1;
    return total;
}

int spread(State *st, int nm)
{
    return nm - nm / 20 + rnd(st, nm / 10);
}

Stats stats_make(int strength, int max_strength, int level, int arm, int hp, int max_hp)
{
    Stats stats = {strength, max_strength, level, arm, hp, max_hp};
    return stats;
}

Ring ring_none(void)
{
    Ring ring = {0, 0, 0};
    return ring;
}

Ring ring_make(int which, int arm)
{
    Ring ring = {1, which, arm};
    return ring;
}

Armor armor_none(void)
{
    Armor armor = {0, 0, 0, 0, 0};
    return armor;
}

Armor armor_make(char type, int which, int arm, int flags)
{
    Armor armor = {1, type, which, arm, flags};
    return armor;
}

TrapCase case_make(const char *name, int seed, int trap_kind)
{
    TrapCase tc;
    tc.name = name;
    tc.seed = seed;
    tc.trap_kind = trap_kind;
    tc.level = 1;
    tc.no_move = 0;
    tc.no_command = 0;
    tc.player_flags = ISRUN;
    tc.stats = stats_make(16, 16, 1, 6, 12, 12);
    tc.weapon_group = 1;
    tc.left_ring = ring_none();
    tc.right_ring = ring_none();
    tc.armor = armor_none();
    return tc;
}

void append_marker(State *st, const char *marker)
{
    st->markers[st->marker_count++] = marker;
}

int is_wearing(State *st, int ring_kind)
{
    return (st->left_ring.present && st->left_ring.which == ring_kind) || (st->right_ring.present && st->right_ring.which == ring_kind);
}

SwingPayload swing(State *st, int at_lvl, int op_arm, int wplus)
{
    SwingPayload payload;
    int result = rnd(st, 20);
    int need = (20 - at_lvl) - op_arm;
    payload.present = 1;
    payload.roll = result;
    payload.need = need;
    payload.hit = result + wplus >= need;
    payload.rng_seed = st->seed;
    return payload;
}

SavePayload save_throw(State *st, int which, int level)
{
    SavePayload payload;
    int need = 14 + which - level / 2;
    int save_roll = roll(st, 1, 20);
    payload.present = 1;
    payload.which = which;
    payload.level = level;
    payload.need = need;
    payload.roll = save_roll;
    payload.saved = save_roll >= need;
    payload.rng_seed = st->seed;
    return payload;
}

Object init_weapon(State *st, int which)
{
    Object obj;
    obj.present = 1;
    obj.type = WEAPON;
    obj.which = which;
    obj.flags = init_weapon_flags[which];
    obj.count = 1;
    obj.group = 0;
    obj.y = 0;
    obj.x = 0;
    if (which == DAGGER)
    {
        obj.count = rnd(st, 4) + 2;
        obj.group = st->weapon_group++;
    }
    else if (obj.flags & ISMANY)
    {
        obj.count = rnd(st, 8) + 8;
        obj.group = st->weapon_group++;
    }
    obj.init_count = obj.count;
    return obj;
}

void add_str(int *strength, int amount)
{
    *strength += amount;
    if (*strength < 3)
        *strength = 3;
    else if (*strength > 31)
        *strength = 31;
}

void chg_str(State *st, int amount)
{
    int comparable;
    add_str(&st->stats.strength, amount);
    comparable = st->stats.strength;
    if (st->left_ring.present && st->left_ring.which == R_ADDSTR)
        add_str(&comparable, -st->left_ring.arm);
    if (st->right_ring.present && st->right_ring.which == R_ADDSTR)
        add_str(&comparable, -st->right_ring.arm);
    if (comparable > st->stats.max_strength)
        st->stats.max_strength = comparable;
}

void rust_armor(State *st)
{
    if (!st->armor.present || st->armor.type != ARMOR || st->armor.which == LEATHER || st->armor.arm >= 9)
        return;
    if ((st->armor.flags & ISPROT) || is_wearing(st, R_SUSTARM))
    {
        append_marker(st, "rust_vanishes");
        return;
    }
    st->armor.arm++;
    append_marker(st, "armor_weakened");
}

TrapReturn return_value(int value)
{
    TrapReturn ret = {1, value};
    return ret;
}

TrapReturn no_return(void)
{
    TrapReturn ret = {0, 0};
    return ret;
}

TrapReturn be_trapped(State *st)
{
    int trap_kind;
    if (st->player_flags & ISLEVIT)
        return return_value(T_RUST);

    st->running = 0;
    st->count = 0;
    st->cell_ch = TRAP;
    trap_kind = st->cell_flags & F_TMASK;
    st->cell_flags |= F_SEEN;

    switch (trap_kind)
    {
        case T_DOOR:
            st->level++;
            append_marker(st, "new_level");
            break;
        case T_BEAR:
            st->no_move += spread(st, 3);
            break;
        case T_MYST:
            st->has_mystery_roll = 1;
            st->mystery_roll = rnd(st, 11);
            if (st->mystery_roll == 1 || st->mystery_roll == 4 || st->mystery_roll == 6 || st->mystery_roll == 10)
            {
                st->has_color = 1;
                st->color_index = rnd(st, 27);
                st->color = rainbow[st->color_index];
            }
            break;
        case T_SLEEP:
            st->no_command += spread(st, 5);
            st->player_flags &= ~ISRUN;
            break;
        case T_ARROW:
            st->arrow_swing = swing(st, st->stats.level - 1, st->stats.arm, 1);
            if (st->arrow_swing.hit)
            {
                st->has_arrow_damage = 1;
                st->arrow_damage = roll(st, 1, 6);
                st->stats.hp -= st->arrow_damage;
                if (st->stats.hp <= 0)
                {
                    append_marker(st, "death_a");
                    st->terminal = 1;
                    return no_return();
                }
            }
            else
            {
                st->arrow = init_weapon(st, ARROW);
                st->arrow.count = 1;
                st->arrow.y = st->hero_y;
                st->arrow.x = st->hero_x;
                append_marker(st, "fall_arrow");
            }
            break;
        case T_TELEP:
            append_marker(st, "teleport");
            break;
        case T_DART:
            st->dart_swing = swing(st, st->stats.level + 1, st->stats.arm, 1);
            if (st->dart_swing.hit)
            {
                st->has_dart_damage = 1;
                st->dart_damage = roll(st, 1, 4);
                st->stats.hp -= st->dart_damage;
                if (st->stats.hp <= 0)
                {
                    append_marker(st, "death_d");
                    st->terminal = 1;
                    return no_return();
                }
                if (!is_wearing(st, R_SUSTSTR))
                {
                    st->poison_save = save_throw(st, VS_POISON, st->stats.level);
                    if (!st->poison_save.saved)
                    {
                        chg_str(st, -1);
                        append_marker(st, "poison_strength");
                    }
                }
            }
            break;
        case T_RUST:
            append_marker(st, "rust_armor");
            rust_armor(st);
            break;
    }

    append_marker(st, "flush_type");
    return return_value(trap_kind);
}

SearchTrap search_trap_make(const char *id, int kind, int row, int col, int flags)
{
    SearchTrap trap;
    trap.id = id;
    trap.row = row;
    trap.col = col;
    trap.kind = kind;
    trap.flags = flags;
    trap.ch = TRAP;
    trap.weapon_group = 1;
    return trap;
}

SearchCell search_cell_make(const char *id, char ch, int row, int col, int flags)
{
    SearchCell cell;
    cell.id = id;
    cell.row = row;
    cell.col = col;
    cell.ch = ch;
    cell.flags = flags;
    return cell;
}

SearchCase search_case_make(const char *name, int seed)
{
    SearchCase sc;
    sc.name = name;
    sc.seed = seed;
    sc.hero_y = 2;
    sc.hero_x = 3;
    sc.player_flags = 0;
    sc.trap_count = 0;
    sc.map_cell_count = 0;
    return sc;
}

int search_trap_at(SearchResult *result, int row, int col)
{
    int i;
    for (i = 0; i < result->trap_count; i++)
        if (result->traps[i].row == row && result->traps[i].col == col)
            return i;
    return -1;
}

int search_cell_at(SearchResult *result, int row, int col)
{
    int i;
    for (i = 0; i < result->map_cell_count; i++)
        if (result->map_cells[i].row == row && result->map_cells[i].col == col)
            return i;
    return -1;
}

void append_search_marker(SearchResult *result, const char *text)
{
    snprintf(result->markers[result->marker_count++], 96, "%s", text);
}

SearchResult search_hidden_traps(SearchCase *sc)
{
    SearchResult result;
    State st;
    int probinc = 0;
    int y, x, i;
    st.seed = sc->seed;
    result.seed = sc->seed;
    result.found = 0;
    result.trap_count = sc->trap_count;
    result.map_cell_count = sc->map_cell_count;
    result.marker_count = 0;
    for (i = 0; i < sc->trap_count; i++)
        result.traps[i] = sc->traps[i];
    for (i = 0; i < sc->map_cell_count; i++)
        result.map_cells[i] = sc->map_cells[i];
    if (sc->player_flags & ISHALU)
        probinc += 3;
    if (sc->player_flags & ISBLIND)
        probinc += 2;
    for (y = sc->hero_y - 1; y <= sc->hero_y + 1; y++)
    {
        for (x = sc->hero_x - 1; x <= sc->hero_x + 1; x++)
        {
            int trap_index, cell_index, roll;
            char marker[96];
            if (y == sc->hero_y && x == sc->hero_x)
                continue;
            cell_index = search_cell_at(&result, y, x);
            if (cell_index >= 0 && !(result.map_cells[cell_index].flags & F_REAL))
            {
                switch (result.map_cells[cell_index].ch)
                {
                    case '|':
                    case '-':
                        roll = rnd(&st, 5 + probinc);
                        snprintf(marker, sizeof(marker), "search_cell_roll:%s:%d", result.map_cells[cell_index].id, roll);
                        append_search_marker(&result, marker);
                        if (roll != 0)
                            continue;
                        result.map_cells[cell_index].flags |= F_REAL;
                        result.map_cells[cell_index].ch = DOOR;
                        snprintf(marker, sizeof(marker), "search_found_door:%s", result.map_cells[cell_index].id);
                        append_search_marker(&result, marker);
                        result.found = 1;
                        continue;
                    case ' ':
                        roll = rnd(&st, 3 + probinc);
                        snprintf(marker, sizeof(marker), "search_cell_roll:%s:%d", result.map_cells[cell_index].id, roll);
                        append_search_marker(&result, marker);
                        if (roll != 0)
                            continue;
                        result.map_cells[cell_index].flags |= F_REAL;
                        result.map_cells[cell_index].ch = PASSAGE;
                        snprintf(marker, sizeof(marker), "search_found_passage:%s", result.map_cells[cell_index].id);
                        append_search_marker(&result, marker);
                        result.found = 1;
                        continue;
                }
            }
            trap_index = search_trap_at(&result, y, x);
            if (trap_index < 0 || (result.traps[trap_index].flags & F_REAL))
                continue;
            roll = rnd(&st, 2 + probinc);
            snprintf(marker, sizeof(marker), "search_trap_roll:%s:%d", result.traps[trap_index].id, roll);
            append_search_marker(&result, marker);
            if (roll != 0)
                continue;
            result.traps[trap_index].flags |= F_REAL | F_SEEN;
            result.traps[trap_index].ch = TRAP;
            snprintf(marker, sizeof(marker), "search_found_trap:%s", result.traps[trap_index].id);
            append_search_marker(&result, marker);
            result.found = 1;
        }
    }
    result.seed = st.seed;
    return result;
}

void print_bool(int value)
{
    printf(value ? "true" : "false");
}

void print_char_string(char ch)
{
    printf("\"%c\"", ch);
}

void print_stats(Stats *stats)
{
    printf("{\"strength\":%d,\"max_strength\":%d,\"level\":%d,\"arm\":%d,\"hp\":%d,\"max_hp\":%d}",
        stats->strength, stats->max_strength, stats->level, stats->arm, stats->hp, stats->max_hp);
}

void print_ring(Ring *ring)
{
    if (!ring->present)
    {
        printf("null");
        return;
    }
    printf("{\"which\":%d,\"arm\":%d}", ring->which, ring->arm);
}

void print_armor(Armor *armor)
{
    if (!armor->present)
    {
        printf("null");
        return;
    }
    printf("{\"type\":\"%c\",\"which\":%d,\"arm\":%d,\"flags\":%d}", armor->type, armor->which, armor->arm, armor->flags);
}

void print_object(Object *obj)
{
    if (!obj->present)
    {
        printf("null");
        return;
    }
    printf("{\"type\":\"%c\",\"which\":%d,\"count\":%d,\"group\":%d,\"flags\":%d,\"y\":%d,\"x\":%d,\"init_count\":%d}",
        obj->type, obj->which, obj->count, obj->group, obj->flags, obj->y, obj->x, obj->init_count);
}

void print_swing(SwingPayload *payload)
{
    printf("{\"roll\":%d,\"need\":%d,\"hit\":", payload->roll, payload->need);
    print_bool(payload->hit);
    printf(",\"rng_seed\":%d}", payload->rng_seed);
}

void print_save(SavePayload *payload)
{
    printf("{\"which\":%d,\"level\":%d,\"need\":%d,\"roll\":%d,\"saved\":", payload->which, payload->level, payload->need, payload->roll);
    print_bool(payload->saved);
    printf(",\"rng_seed\":%d}", payload->rng_seed);
}

void print_trace_field_prefix(int *first, const char *name)
{
    if (!*first)
        printf(",");
    printf("\"%s\":", name);
    *first = 0;
}

void print_trace(State *st)
{
    int first = 1;
    printf("{");
    if (st->has_mystery_roll)
    {
        print_trace_field_prefix(&first, "mystery_roll");
        printf("%d", st->mystery_roll);
        if (st->has_color)
        {
            print_trace_field_prefix(&first, "color_index");
            printf("%d", st->color_index);
            print_trace_field_prefix(&first, "color");
            printf("\"%s\"", st->color);
        }
    }
    if (st->arrow_swing.present)
    {
        print_trace_field_prefix(&first, "arrow_swing");
        print_swing(&st->arrow_swing);
    }
    if (st->has_arrow_damage)
    {
        print_trace_field_prefix(&first, "arrow_damage");
        printf("%d", st->arrow_damage);
    }
    if (st->dart_swing.present)
    {
        print_trace_field_prefix(&first, "dart_swing");
        print_swing(&st->dart_swing);
    }
    if (st->has_dart_damage)
    {
        print_trace_field_prefix(&first, "dart_damage");
        printf("%d", st->dart_damage);
    }
    if (st->poison_save.present)
    {
        print_trace_field_prefix(&first, "poison_save");
        print_save(&st->poison_save);
    }
    printf("}");
}

void print_markers(State *st)
{
    printf("[");
    for (int i = 0; i < st->marker_count; i++)
    {
        if (i)
            printf(",");
        printf("\"%s\"", st->markers[i]);
    }
    printf("]");
}

void print_state(State *st)
{
    printf("{\"rng_seed\":%d,\"level\":%d,\"no_move\":%d,\"no_command\":%d,\"player_flags\":%d,",
        st->seed, st->level, st->no_move, st->no_command, st->player_flags);
    printf("\"stats\":");
    print_stats(&st->stats);
    printf(",\"cell\":{\"ch\":");
    print_char_string(st->cell_ch);
    printf(",\"flags\":%d},\"running\":", st->cell_flags);
    print_bool(st->running);
    printf(",\"count\":");
    print_bool(st->count);
    printf(",\"weapon_group\":%d,\"hero\":{\"y\":%d,\"x\":%d},\"left_ring\":", st->weapon_group, st->hero_y, st->hero_x);
    print_ring(&st->left_ring);
    printf(",\"right_ring\":");
    print_ring(&st->right_ring);
    printf(",\"armor\":");
    print_armor(&st->armor);
    printf(",\"arrow\":");
    print_object(&st->arrow);
    printf(",\"markers\":");
    print_markers(st);
    printf(",\"trace\":");
    print_trace(st);
    printf(",\"terminal\":");
    print_bool(st->terminal);
    printf("}");
}

void print_search_trap(SearchTrap *trap)
{
    printf("{\"id\":\"%s\",\"row\":%d,\"col\":%d,\"kind\":%d,\"flags\":%d,\"ch\":\"%c\",\"weapon_group\":%d}",
        trap->id, trap->row, trap->col, trap->kind, trap->flags, trap->ch, trap->weapon_group);
}

void print_search_cell(SearchCell *cell)
{
    printf("{\"id\":\"%s\",\"row\":%d,\"col\":%d,\"ch\":\"%c\",\"flags\":%d}",
        cell->id, cell->row, cell->col, cell->ch, cell->flags);
}

void print_search_result(SearchResult *result)
{
    int i;
    printf("{\"rng_seed\":%d,\"found\":", result->seed);
    print_bool(result->found);
    printf(",\"traps\":[");
    for (i = 0; i < result->trap_count; i++)
    {
        if (i)
            printf(",");
        print_search_trap(&result->traps[i]);
    }
    printf("],\"map_cells\":[");
    for (i = 0; i < result->map_cell_count; i++)
    {
        if (i)
            printf(",");
        print_search_cell(&result->map_cells[i]);
    }
    printf("],\"markers\":[");
    for (i = 0; i < result->marker_count; i++)
    {
        if (i)
            printf(",");
        printf("\"%s\"", result->markers[i]);
    }
    printf("]}");
}

void init_state(State *st, TrapCase *tc)
{
    st->seed = tc->seed;
    st->level = tc->level;
    st->no_move = tc->no_move;
    st->no_command = tc->no_command;
    st->player_flags = tc->player_flags;
    st->stats = tc->stats;
    st->cell_ch = TRAP;
    st->cell_flags = F_REAL | tc->trap_kind;
    st->running = 1;
    st->count = 1;
    st->weapon_group = tc->weapon_group;
    st->hero_y = 10;
    st->hero_x = 20;
    st->left_ring = tc->left_ring;
    st->right_ring = tc->right_ring;
    st->armor = tc->armor;
    st->arrow.present = 0;
    st->marker_count = 0;
    st->terminal = 0;
    st->has_mystery_roll = 0;
    st->has_color = 0;
    st->color_index = 0;
    st->color = "";
    st->arrow_swing.present = 0;
    st->has_arrow_damage = 0;
    st->dart_swing.present = 0;
    st->has_dart_damage = 0;
    st->poison_save.present = 0;
}

void print_case(TrapCase *tc)
{
    State st;
    TrapReturn ret;
    init_state(&st, tc);
    ret = be_trapped(&st);
    printf("{\"name\":\"%s\",\"seed\":%d,\"trap_kind\":%d,\"returned\":", tc->name, tc->seed, tc->trap_kind);
    if (ret.present)
        printf("%d", ret.value);
    else
        printf("null");
    printf(",\"state\":");
    print_state(&st);
    printf("}");
}

void print_search_case(SearchCase *sc)
{
    SearchResult result = search_hidden_traps(sc);
    printf("{\"name\":\"%s\",\"seed\":%d,\"result\":", sc->name, sc->seed);
    print_search_result(&result);
    printf("}");
}

int main(void)
{
    TrapCase cases[20];
    SearchCase search_cases[6];
    int count = 0;
    int search_count = 0;

    cases[count] = case_make("levitating_arrow_returns_rust", 1, T_ARROW);
    cases[count].player_flags = ISRUN | ISLEVIT;
    count++;

    cases[count] = case_make("trapdoor_new_level", 1, T_DOOR);
    cases[count].level = 4;
    count++;

    cases[count] = case_make("bear_trap_holds", -17, T_BEAR);
    cases[count].no_move = 1;
    count++;

    cases[count++] = case_make("mystery_plain", -184, T_MYST);
    cases[count++] = case_make("mystery_color_1", -178, T_MYST);
    cases[count++] = case_make("mystery_color_4", -160, T_MYST);
    cases[count++] = case_make("mystery_color_6", -148, T_MYST);
    cases[count++] = case_make("mystery_color_10", -190, T_MYST);

    cases[count] = case_make("sleep_trap_stops_run", 7, T_SLEEP);
    cases[count].no_command = 2;
    count++;

    cases[count] = case_make("arrow_hit", 76, T_ARROW);
    cases[count].stats = stats_make(16, 16, 1, 6, 12, 12);
    count++;

    cases[count] = case_make("arrow_miss_falls", 1, T_ARROW);
    cases[count].stats = stats_make(16, 16, 1, 6, 12, 12);
    cases[count].weapon_group = 9;
    count++;

    cases[count] = case_make("arrow_death", 76, T_ARROW);
    cases[count].stats = stats_make(16, 16, 1, 6, 1, 12);
    count++;

    cases[count++] = case_make("teleport_marker", 7, T_TELEP);

    cases[count] = case_make("dart_miss", 1, T_DART);
    cases[count].stats = stats_make(16, 16, 1, 6, 12, 12);
    count++;

    cases[count] = case_make("dart_poison_strength", 64, T_DART);
    cases[count].stats = stats_make(10, 10, 1, 6, 12, 12);
    count++;

    cases[count] = case_make("dart_poison_saved", 68, T_DART);
    cases[count].stats = stats_make(10, 10, 1, 6, 12, 12);
    count++;

    cases[count] = case_make("dart_sustain_strength", 64, T_DART);
    cases[count].stats = stats_make(10, 10, 1, 6, 12, 12);
    cases[count].left_ring = ring_make(R_SUSTSTR, 0);
    count++;

    cases[count] = case_make("rust_armor", 5, T_RUST);
    cases[count].armor = armor_make(ARMOR, 1, 4, 0);
    count++;

    cases[count] = case_make("rust_protected_armor", 5, T_RUST);
    cases[count].armor = armor_make(ARMOR, 1, 4, ISPROT);
    count++;

    cases[count] = case_make("rust_sustain_armor", 5, T_RUST);
    cases[count].armor = armor_make(ARMOR, 1, 4, 0);
    cases[count].right_ring = ring_make(R_SUSTARM, 0);
    count++;

    search_cases[search_count] = search_case_make("search_hidden_trap_found", 1);
    search_cases[search_count].traps[search_cases[search_count].trap_count++] = search_trap_make("hidden_arrow", T_ARROW, 2, 4, T_ARROW);
    search_count++;

    search_cases[search_count] = search_case_make("search_hidden_trap_missed", 5);
    search_cases[search_count].traps[search_cases[search_count].trap_count++] = search_trap_make("hidden_bear", T_BEAR, 2, 4, T_BEAR);
    search_count++;

    search_cases[search_count] = search_case_make("search_ignores_real_trap", 1);
    search_cases[search_count].traps[search_cases[search_count].trap_count++] = search_trap_make("real_arrow", T_ARROW, 2, 4, F_REAL | T_ARROW);
    search_count++;

    search_cases[search_count] = search_case_make("search_secret_door_found", 1);
    search_cases[search_count].map_cells[search_cases[search_count].map_cell_count++] = search_cell_make("secret_door", '|', 2, 4, 0);
    search_count++;

    search_cases[search_count] = search_case_make("search_hidden_passage_found", 1);
    search_cases[search_count].map_cells[search_cases[search_count].map_cell_count++] = search_cell_make("hidden_passage", ' ', 2, 4, 0);
    search_count++;

    search_cases[search_count] = search_case_make("search_secret_door_missed", 5);
    search_cases[search_count].map_cells[search_cases[search_count].map_cell_count++] = search_cell_make("missed_door", '-', 2, 4, 0);
    search_count++;

    printf("{\"schema\":\"gamebench.rogue.source_traps.v1\",\"trap_cases\":[");
    for (int i = 0; i < count; i++)
    {
        if (i)
            printf(",");
        print_case(&cases[i]);
    }
    printf("],\"search_cases\":[");
    for (int i = 0; i < search_count; i++)
    {
        if (i)
            printf(",");
        print_search_case(&search_cases[i]);
    }
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_traps_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_traps",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-traps-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_traps.c"
        binary = temp / "source_traps"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_traps.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "trap_cases": [case["name"] for case in reports["c"]["trap_cases"]],
        "search_cases": [case["name"] for case in reports["c"]["search_cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source traps mismatch")


if __name__ == "__main__":
    main()
