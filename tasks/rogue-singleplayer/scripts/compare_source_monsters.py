#!/usr/bin/env python3
"""Compare source-derived Rogue monster behavior across C, Python, and Rust."""

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

from source_monsters import source_monsters_report


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define AMULETLEVEL 26
#define LAMPDIST 3
#define VS_MAGIC 3
#define S_SCARE 10

#define CANSEE 0000002
#define ISBLIND 0000004
#define ISCANC 0000010
#define ISLEVIT 0000010
#define ISFOUND 0000020
#define ISGREED 0000040
#define ISHASTE 0000100
#define ISHELD 0000400
#define ISHUH 0001000
#define ISINVIS 0002000
#define ISMEAN 0004000
#define ISHALU 0004000
#define ISREGEN 0010000
#define ISRUN 0020000
#define ISFLY 0040000

#define R_PROTECT 0
#define R_STEALTH 12
#define R_AGGR 6

#define POTION '!'
#define SCROLL '?'
#define RING '='
#define STICK '/'
#define FOOD ':'
#define WEAPON ')'
#define ARMOR ']'
#define STAIRS '%'
#define GOLD '*'
#define AMULET ','

typedef struct coord {
    int y;
    int x;
} Coord;

typedef struct stats {
    int strength;
    int exp;
    int level;
    int arm;
    int hp;
    const char *damage;
    int max_hp;
} Stats;

typedef struct monster {
    char type;
    char disguise;
    Coord pos;
    char oldch;
    int room;
    const char *dest;
    int has_dest_pos;
    Coord dest_pos;
    int flags;
    int turn;
    Stats stats;
    int pack_count;
} Monster;

typedef struct object {
    char type;
    int which;
    Coord pos;
    int room;
} Object;

typedef struct ring {
    int present;
    int which;
    int arm;
} Ring;

typedef struct save_payload {
    int present;
    int which;
    int original_which;
    int level;
    int need;
    int roll;
    int saved;
    int rng_seed;
} SavePayload;

typedef struct find_roll {
    Coord pos;
    int roll;
    int prob;
} FindRoll;

typedef struct world {
    int seed;
    int level;
    int max_level;
    Coord hero;
    int proom;
    Coord proom_gold;
    int proom_goldval;
    int room_dark_index[8];
    int room_dark_value[8];
    int room_dark_count;
    int player_flags;
    Ring left_ring;
    Ring right_ring;
    Object objects[8];
    int object_count;
    Coord claimed[8];
    int claimed_count;
    const char *markers[8];
    int marker_count;
    int has_wake_roll;
    int wake_roll;
    int has_medusa_visible;
    int medusa_visible;
    SavePayload medusa_save;
    FindRoll find_rolls[8];
    int find_roll_count;
} World;

static char lvl_mons[26] = {'K','E','B','S','H','I','R','O','Z','L','C','Q','A','N','Y','F','T','W','P','X','U','M','V','G','J','D'};
static char wand_mons[26] = {'K','E','B','S','H',0,'R','O','Z',0,'C','Q','A',0,'Y',0,'T','W','P',0,'U','M','V','G','J',0};
static char rnd_thing_list[10] = {POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS, GOLD, AMULET};
static int monster_carry[26] = {0, 0, 15, 100, 0, 0, 20, 0, 0, 70, 0, 0, 40, 100, 15, 0, 0, 0, 0, 50, 0, 20, 0, 30, 30, 0};
static int monster_exp[26] = {20, 1, 17, 5000, 2, 80, 2000, 3, 5, 3000, 1, 10, 200, 37, 5, 120, 15, 9, 2, 120, 190, 350, 55, 100, 50, 6};
static int monster_levels[26] = {5, 1, 4, 10, 1, 8, 13, 1, 1, 15, 1, 3, 8, 3, 1, 8, 3, 2, 1, 6, 7, 8, 5, 7, 4, 2};
static int monster_armor[26] = {2, 3, 4, -1, 7, 3, 2, 5, 9, 6, 7, 8, 2, 9, 6, 3, 3, 3, 5, 4, -2, 1, 4, 7, 6, 8};
static const char *monster_damage[26] = {
    "0x0/0x0", "1x2", "1x2/1x5/1x5", "1x8/1x8/3x10", "1x2", "%%%x0",
    "4x3/3x5", "1x8", "0x0", "2x12/2x4", "1x4", "1x1", "3x4/3x4/2x5",
    "0x0", "1x8", "4x4", "1x5/1x5", "1x6", "1x3", "1x8/1x8/2x6",
    "1x9/1x9/2x9", "1x10", "1x6", "4x4", "1x6/1x6", "1x8"
};
static int monster_flags[26] = {
    ISMEAN, ISFLY, 0, ISMEAN, ISMEAN, ISMEAN, ISMEAN|ISFLY|ISREGEN, ISMEAN, 0, 0,
    ISMEAN|ISFLY, 0, ISMEAN, 0, ISGREED, ISINVIS, ISMEAN, ISMEAN, ISMEAN,
    ISREGEN|ISMEAN, ISMEAN, ISREGEN|ISMEAN, 0, 0, 0, ISMEAN
};

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range)
{
    return range == 0 ? 0 : abs((int) RN(world)) % range;
}

int roll(World *world, int number, int sides)
{
    int total = 0;
    while (number--)
        total += rnd(world, sides) + 1;
    return total;
}

Coord coord(int y, int x)
{
    Coord c = {y, x};
    return c;
}

Ring no_ring(void)
{
    Ring ring = {0, 0, 0};
    return ring;
}

Ring ring_make(int which, int arm)
{
    Ring ring = {1, which, arm};
    return ring;
}

Object object_make(char type, int which, Coord pos, int room)
{
    Object obj = {type, which, pos, room};
    return obj;
}

void world_init(World *world, int seed, int level, Coord hero, int proom)
{
    memset(world, 0, sizeof(*world));
    world->seed = seed;
    world->level = level;
    world->max_level = level;
    world->hero = hero;
    world->proom = proom;
    world->proom_gold = coord(2, 2);
    world->proom_goldval = 0;
    world->left_ring = no_ring();
    world->right_ring = no_ring();
}

void set_room_dark(World *world, int room, int dark)
{
    world->room_dark_index[world->room_dark_count] = room;
    world->room_dark_value[world->room_dark_count] = dark;
    world->room_dark_count++;
}

int room_dark(World *world, int room)
{
    for (int i = 0; i < world->room_dark_count; i++)
        if (world->room_dark_index[i] == room)
            return world->room_dark_value[i];
    return 0;
}

void append_marker(World *world, const char *marker)
{
    world->markers[world->marker_count++] = marker;
}

int coord_eq(Coord first, Coord second)
{
    return first.x == second.x && first.y == second.y;
}

int dist(Coord first, Coord second)
{
    return (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y);
}

int is_wearing(World *world, int ring_kind)
{
    return (world->left_ring.present && world->left_ring.which == ring_kind) || (world->right_ring.present && world->right_ring.which == ring_kind);
}

int exp_add(int level, int max_hp)
{
    int mod = (level == 1) ? max_hp / 8 : max_hp / 6;
    if (level > 9)
        mod *= 20;
    else if (level > 6)
        mod *= 4;
    return mod;
}

char rnd_thing(World *world)
{
    int index;
    if (world->level >= AMULETLEVEL)
        index = rnd(world, 10);
    else
        index = rnd(world, 9);
    return rnd_thing_list[index];
}

Stats base_stats(char monster_type)
{
    int index = monster_type - 'A';
    Stats stats = {10, monster_exp[index], monster_levels[index], monster_armor[index], 1, monster_damage[index], 1};
    return stats;
}

int see_monst(World *world, Monster *monster)
{
    if (world->player_flags & ISBLIND)
        return 0;
    if ((monster->flags & ISINVIS) && !(world->player_flags & CANSEE))
        return 0;
    if (dist(monster->pos, world->hero) < LAMPDIST)
        return 1;
    if (monster->room != world->proom)
        return 0;
    return !room_dark(world, monster->room);
}

SavePayload save_magic(World *world, int which, int player_level)
{
    SavePayload payload;
    int adjusted = which;
    if (which == VS_MAGIC)
    {
        if (world->left_ring.present && world->left_ring.which == R_PROTECT)
            adjusted -= world->left_ring.arm;
        if (world->right_ring.present && world->right_ring.which == R_PROTECT)
            adjusted -= world->right_ring.arm;
    }
    payload.present = 1;
    payload.which = adjusted;
    payload.original_which = which;
    payload.level = player_level;
    payload.need = 14 + adjusted - player_level / 2;
    payload.roll = roll(world, 1, 20);
    payload.saved = payload.roll >= payload.need;
    payload.rng_seed = world->seed;
    return payload;
}

void add_find_dest_roll(World *world, Coord pos, int value, int prob)
{
    FindRoll *roll_out = &world->find_rolls[world->find_roll_count++];
    roll_out->pos = pos;
    roll_out->roll = value;
    roll_out->prob = prob;
}

int is_claimed(World *world, Coord pos)
{
    for (int i = 0; i < world->claimed_count; i++)
        if (coord_eq(pos, world->claimed[i]))
            return 1;
    return 0;
}

void set_dest(Monster *monster, const char *dest, Coord pos)
{
    monster->dest = dest;
    monster->dest_pos = pos;
    monster->has_dest_pos = 1;
}

void find_dest(World *world, Monster *monster, const char **dest, Coord *dest_pos)
{
    int carry_prob = monster_carry[monster->type - 'A'];
    *dest = "hero";
    *dest_pos = world->hero;
    if (carry_prob <= 0 || monster->room == world->proom || see_monst(world, monster))
        return;
    for (int i = 0; i < world->object_count; i++)
    {
        Object *obj = &world->objects[i];
        if (obj->type == SCROLL && obj->which == S_SCARE)
            continue;
        if (obj->room == monster->room)
        {
            int value = rnd(world, 100);
            add_find_dest_roll(world, obj->pos, value, carry_prob);
            if (value < carry_prob && !is_claimed(world, obj->pos))
            {
                *dest = "object";
                *dest_pos = obj->pos;
                return;
            }
        }
    }
}

void runto(World *world, Monster *monster)
{
    const char *dest;
    Coord dest_pos;
    monster->flags |= ISRUN;
    monster->flags &= ~ISHELD;
    find_dest(world, monster, &dest, &dest_pos);
    set_dest(monster, dest, dest_pos);
}

Monster new_monster(World *world, char monster_type, Coord pos, int room)
{
    int index = monster_type - 'A';
    int lev_add = world->level - AMULETLEVEL;
    int monster_level, hp, max_hp;
    Monster monster;
    if (lev_add < 0)
        lev_add = 0;
    monster_level = monster_levels[index] + lev_add;
    hp = roll(world, monster_level, 8);
    max_hp = hp;
    monster.type = monster_type;
    monster.disguise = monster_type == 'X' ? rnd_thing(world) : monster_type;
    monster.pos = pos;
    monster.oldch = '.';
    monster.room = room;
    monster.dest = "none";
    monster.has_dest_pos = 0;
    monster.dest_pos = coord(0, 0);
    monster.flags = monster_flags[index];
    if (world->level > 29)
        monster.flags |= ISHASTE;
    monster.turn = 1;
    monster.stats.strength = 10;
    monster.stats.exp = monster_exp[index] + lev_add * 10 + exp_add(monster_level, max_hp);
    monster.stats.level = monster_level;
    monster.stats.arm = monster_armor[index] - lev_add;
    monster.stats.hp = hp;
    monster.stats.damage = monster_damage[index];
    monster.stats.max_hp = max_hp;
    monster.pack_count = 0;
    if (is_wearing(world, R_AGGR))
        runto(world, &monster);
    return monster;
}

void wake_monster(World *world, Monster *monster)
{
    if (!(monster->flags & ISRUN))
    {
        int wake_roll = rnd(world, 3);
        world->has_wake_roll = 1;
        world->wake_roll = wake_roll;
        if (wake_roll != 0 && (monster->flags & ISMEAN) && !(monster->flags & ISHELD) && !is_wearing(world, R_STEALTH) && !(world->player_flags & ISLEVIT))
        {
            set_dest(monster, "hero", world->hero);
            monster->flags |= ISRUN;
            append_marker(world, "monster_runs");
        }
    }

    if (monster->type == 'M' && !(world->player_flags & ISBLIND) && !(world->player_flags & ISHALU)
        && !(monster->flags & ISFOUND) && !(monster->flags & ISCANC) && (monster->flags & ISRUN))
    {
        int visible = (monster->room == world->proom && !room_dark(world, world->proom)) || dist(monster->pos, world->hero) < LAMPDIST;
        world->has_medusa_visible = 1;
        world->medusa_visible = visible;
        if (visible)
        {
            monster->flags |= ISFOUND;
            world->medusa_save = save_magic(world, VS_MAGIC, 1);
            if (!world->medusa_save.saved)
            {
                world->player_flags |= ISHUH;
                append_marker(world, "confuse_player");
                append_marker(world, "fuse_unconfuse");
            }
        }
    }

    if ((monster->flags & ISGREED) && !(monster->flags & ISRUN))
    {
        monster->flags |= ISRUN;
        if (world->proom_goldval)
            set_dest(monster, "gold", world->proom_gold);
        else
            set_dest(monster, "hero", world->hero);
        append_marker(world, "greed_runs");
    }
}

void print_bool(int value)
{
    printf(value ? "true" : "false");
}

void print_char(char ch)
{
    if (ch == 0)
        printf("\"\\u0000\"");
    else
        printf("\"%c\"", ch);
}

void print_coord(Coord coord)
{
    printf("{\"y\":%d,\"x\":%d}", coord.y, coord.x);
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

void print_stats(Stats *stats)
{
    printf("{\"strength\":%d,\"exp\":%d,\"level\":%d,\"arm\":%d,\"hp\":%d,\"damage\":\"%s\",\"max_hp\":%d}",
        stats->strength, stats->exp, stats->level, stats->arm, stats->hp, stats->damage, stats->max_hp);
}

void print_markers(World *world)
{
    printf("[");
    for (int i = 0; i < world->marker_count; i++)
    {
        if (i)
            printf(",");
        printf("\"%s\"", world->markers[i]);
    }
    printf("]");
}

void print_trace(World *world)
{
    int first = 1;
    printf("{");
    if (world->find_roll_count)
    {
        printf("\"find_dest_rolls\":[");
        first = 0;
        for (int i = 0; i < world->find_roll_count; i++)
        {
            if (i)
                printf(",");
            printf("{\"pos\":");
            print_coord(world->find_rolls[i].pos);
            printf(",\"roll\":%d,\"prob\":%d}", world->find_rolls[i].roll, world->find_rolls[i].prob);
        }
        printf("]");
    }
    if (world->has_wake_roll)
    {
        if (!first)
            printf(",");
        printf("\"wake_roll\":%d", world->wake_roll);
        first = 0;
    }
    if (world->has_medusa_visible)
    {
        if (!first)
            printf(",");
        printf("\"medusa_visible\":");
        print_bool(world->medusa_visible);
        first = 0;
    }
    if (world->medusa_save.present)
    {
        if (!first)
            printf(",");
        printf("\"medusa_save\":{\"which\":%d,\"original_which\":%d,\"level\":%d,\"need\":%d,\"roll\":%d,\"saved\":",
            world->medusa_save.which, world->medusa_save.original_which, world->medusa_save.level,
            world->medusa_save.need, world->medusa_save.roll);
        print_bool(world->medusa_save.saved);
        printf(",\"rng_seed\":%d}", world->medusa_save.rng_seed);
    }
    printf("}");
}

void print_world(World *world)
{
    printf("{\"rng_seed\":%d,\"level\":%d,\"max_level\":%d,\"hero\":", world->seed, world->level, world->max_level);
    print_coord(world->hero);
    printf(",\"proom\":%d,\"proom_gold\":", world->proom);
    print_coord(world->proom_gold);
    printf(",\"proom_goldval\":%d,\"player_flags\":%d,\"left_ring\":", world->proom_goldval, world->player_flags);
    print_ring(&world->left_ring);
    printf(",\"right_ring\":");
    print_ring(&world->right_ring);
    printf(",\"markers\":");
    print_markers(world);
    printf(",\"trace\":");
    print_trace(world);
    printf("}");
}

void print_monster(Monster *monster)
{
    printf("{\"type\":");
    print_char(monster->type);
    printf(",\"disguise\":");
    print_char(monster->disguise);
    printf(",\"pos\":");
    print_coord(monster->pos);
    printf(",\"oldch\":");
    print_char(monster->oldch);
    printf(",\"room\":%d,\"dest\":\"%s\",\"dest_pos\":", monster->room, monster->dest);
    if (monster->has_dest_pos)
        print_coord(monster->dest_pos);
    else
        printf("null");
    printf(",\"flags\":%d,\"turn\":", monster->flags);
    print_bool(monster->turn);
    printf(",\"stats\":");
    print_stats(&monster->stats);
    printf(",\"pack_count\":%d}", monster->pack_count);
}

void print_randmonster_case(int seed, int level, int wander)
{
    World world;
    char *mons = wander ? wand_mons : lvl_mons;
    int first = 1;
    char chosen = 0;
    world_init(&world, seed, level, coord(0, 0), 0);
    printf("{\"seed\":%d,\"level\":%d,\"wander\":", seed, level);
    print_bool(wander);
    printf(",\"monster\":");
    printf("PLACEHOLDER");
    printf(",\"attempts\":[");
    while (chosen == 0)
    {
        int raw = level + (rnd(&world, 10) - 6);
        int index = raw;
        if (index < 0)
            index = rnd(&world, 5);
        if (index > 25)
            index = rnd(&world, 5) + 21;
        chosen = mons[index];
        if (!first)
            printf(",");
        first = 0;
        printf("{\"raw\":%d,\"index\":%d,\"monster\":", raw, index);
        print_char(chosen);
        printf("}");
    }
    printf("],\"rng_seed\":%d}", world.seed);
}

void print_randmonster_case_fixed(int seed, int level, int wander)
{
    World world;
    char *mons = wander ? wand_mons : lvl_mons;
    int raws[16], indexes[16];
    char monsters[16];
    int count = 0;
    char chosen = 0;
    world_init(&world, seed, level, coord(0, 0), 0);
    while (chosen == 0)
    {
        int raw = level + (rnd(&world, 10) - 6);
        int index = raw;
        if (index < 0)
            index = rnd(&world, 5);
        if (index > 25)
            index = rnd(&world, 5) + 21;
        chosen = mons[index];
        raws[count] = raw;
        indexes[count] = index;
        monsters[count] = chosen;
        count++;
    }
    printf("{\"seed\":%d,\"level\":%d,\"wander\":", seed, level);
    print_bool(wander);
    printf(",\"monster\":");
    print_char(chosen);
    printf(",\"attempts\":[");
    for (int i = 0; i < count; i++)
    {
        if (i)
            printf(",");
        printf("{\"raw\":%d,\"index\":%d,\"monster\":", raws[i], indexes[i]);
        print_char(monsters[i]);
        printf("}");
    }
    printf("],\"rng_seed\":%d}", world.seed);
}

void print_new_monster_case(const char *name, int seed, int level, char monster_type, Coord pos, int room, Ring left_ring)
{
    World world;
    Monster monster;
    world_init(&world, seed, level, coord(1, 1), 0);
    world.left_ring = left_ring;
    monster = new_monster(&world, monster_type, pos, room);
    printf("{\"name\":\"%s\",\"seed\":%d,\"world\":", name, seed);
    print_world(&world);
    printf(",\"monster\":");
    print_monster(&monster);
    printf("}");
}

void print_runto_case(const char *name, int seed, char monster_type, int room, int proom, Object *objects, int object_count, Coord *claimed, int claimed_count, Coord hero)
{
    World world;
    Monster monster;
    world_init(&world, seed, 12, hero, proom);
    for (int i = 0; i < object_count; i++)
        world.objects[world.object_count++] = objects[i];
    for (int i = 0; i < claimed_count; i++)
        world.claimed[world.claimed_count++] = claimed[i];
    set_room_dark(&world, proom, 0);
    set_room_dark(&world, room, 0);
    monster.type = monster_type;
    monster.disguise = monster_type;
    monster.pos = coord(5, 5);
    monster.oldch = '.';
    monster.room = room;
    monster.dest = "none";
    monster.has_dest_pos = 0;
    monster.dest_pos = coord(0, 0);
    monster.flags = monster_flags[monster_type - 'A'];
    monster.turn = 1;
    monster.stats = base_stats(monster_type);
    monster.pack_count = 0;
    runto(&world, &monster);
    printf("{\"name\":\"%s\",\"seed\":%d,\"world\":", name, seed);
    print_world(&world);
    printf(",\"monster\":");
    print_monster(&monster);
    printf("}");
}

void print_wake_case(const char *name, int seed, char monster_type, int flags, Ring left_ring, int player_flags, int is_room_dark, Coord pos, int proom_goldval)
{
    World world;
    Monster monster;
    world_init(&world, seed, 12, coord(5, 5), 0);
    world.proom_goldval = proom_goldval;
    set_room_dark(&world, 0, is_room_dark);
    world.player_flags = player_flags;
    world.left_ring = left_ring;
    monster.type = monster_type;
    monster.disguise = monster_type;
    monster.pos = pos;
    monster.oldch = '.';
    monster.room = 0;
    monster.dest = "none";
    monster.has_dest_pos = 0;
    monster.dest_pos = coord(0, 0);
    monster.flags = flags;
    monster.turn = 1;
    monster.stats = base_stats(monster_type);
    monster.pack_count = 0;
    wake_monster(&world, &monster);
    printf("{\"name\":\"%s\",\"seed\":%d,\"world\":", name, seed);
    print_world(&world);
    printf(",\"monster\":");
    print_monster(&monster);
    printf("}");
}

int main(void)
{
    Object objects[2];
    Coord claimed[1];
    printf("{\"schema\":\"gamebench.rogue.source_monsters.v1\",\"randmonster\":[");
    print_randmonster_case_fixed(1, 1, 0);
    printf(",");
    print_randmonster_case_fixed(7, 12, 0);
    printf(",");
    print_randmonster_case_fixed(-17, 30, 0);
    printf(",");
    print_randmonster_case_fixed(5, 6, 1);
    printf(",");
    print_randmonster_case_fixed(10, 18, 1);
    printf("],\"new_monster\":[");
    print_new_monster_case("kestrel_level_1", 1, 1, 'K', coord(4, 5), 0, no_ring());
    printf(",");
    print_new_monster_case("dragon_level_30", 7, 30, 'D', coord(7, 8), 1, no_ring());
    printf(",");
    print_new_monster_case("xeroc_disguise", -17, 26, 'X', coord(10, 20), 2, no_ring());
    printf(",");
    print_new_monster_case("aggravate_ring_sets_dest", 3, 12, 'C', coord(3, 4), 1, ring_make(R_AGGR, 0));
    printf("],\"runto_find_dest\":[");
    print_runto_case("same_room_goes_hero", 1, 'C', 0, 0, objects, 0, claimed, 0, coord(1, 1));
    printf(",");
    objects[0] = object_make(FOOD, 0, coord(6, 7), 1);
    print_runto_case("carry_object_dest", 7, 'C', 1, 0, objects, 1, claimed, 0, coord(1, 1));
    printf(",");
    objects[0] = object_make(SCROLL, S_SCARE, coord(6, 7), 1);
    objects[1] = object_make(FOOD, 0, coord(6, 8), 1);
    print_runto_case("scare_scroll_skipped", 7, 'C', 1, 0, objects, 2, claimed, 0, coord(1, 1));
    printf(",");
    objects[0] = object_make(FOOD, 0, coord(6, 7), 1);
    claimed[0] = coord(6, 7);
    print_runto_case("claimed_object_goes_hero", 7, 'C', 1, 0, objects, 1, claimed, 1, coord(1, 1));
    printf(",");
    objects[0] = object_make(FOOD, 0, coord(6, 7), 1);
    print_runto_case("visible_goes_hero", 7, 'C', 1, 0, objects, 1, claimed, 0, coord(5, 6));
    printf("],\"wake_monster\":[");
    print_wake_case("mean_starts_running", 5, 'K', monster_flags['K' - 'A'], no_ring(), 0, 0, coord(5, 6), 0);
    printf(",");
    print_wake_case("mean_roll_zero_stays", 1, 'K', monster_flags['K' - 'A'], no_ring(), 0, 0, coord(5, 6), 0);
    printf(",");
    print_wake_case("stealth_prevents_running", 5, 'K', monster_flags['K' - 'A'], ring_make(R_STEALTH, 0), 0, 0, coord(5, 6), 0);
    printf(",");
    print_wake_case("levitation_prevents_running", 5, 'K', monster_flags['K' - 'A'], no_ring(), ISLEVIT, 0, coord(5, 6), 0);
    printf(",");
    print_wake_case("medusa_confuses", 5, 'M', monster_flags['M' - 'A'], no_ring(), 0, 0, coord(5, 6), 0);
    printf(",");
    print_wake_case("medusa_save", 10, 'M', monster_flags['M' - 'A'], no_ring(), 0, 0, coord(5, 6), 0);
    printf(",");
    print_wake_case("medusa_dark_room_no_gaze", 5, 'M', monster_flags['M' - 'A'], no_ring(), 0, 1, coord(8, 8), 0);
    printf(",");
    print_wake_case("greed_guards_gold", 1, 'O', monster_flags['O' - 'A'], no_ring(), 0, 0, coord(5, 6), 25);
    printf(",");
    print_wake_case("greed_runs_hero_without_gold", 1, 'O', monster_flags['O' - 'A'], no_ring(), 0, 0, coord(5, 6), 0);
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_monsters_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_monsters",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-monsters-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_monsters.c"
        binary = temp / "source_monsters"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_monsters.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "randmonster_cases": len(reports["c"]["randmonster"]),
        "new_monster_cases": [case["name"] for case in reports["c"]["new_monster"]],
        "runto_cases": [case["name"] for case in reports["c"]["runto_find_dest"]],
        "wake_cases": [case["name"] for case in reports["c"]["wake_monster"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source monsters mismatch")


if __name__ == "__main__":
    main()
