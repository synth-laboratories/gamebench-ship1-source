#!/usr/bin/env python3
"""Compare source-derived Rogue monster attack branches across C, Python, and Rust."""

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

from source_attack import source_attack_report


TRACE_KEYS = [
    "target_cancelled",
    "xeroc_hallu",
    "roll_hit",
    "roll_rng",
    "ice_roll",
    "poison_saved",
    "poison_roll",
    "drain_roll",
    "drain_fewer",
    "gold_saved",
    "gold_save_roll",
    "stolen",
]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define VS_POISON 0
#define VS_MAGIC 3
#define ISBLIND 0000004
#define ISCANC 0000010
#define ISTARGET 0000200
#define ISHELD 0000400
#define ISHALU 0004000
#define ISRUN 0020000
#define R_PROTECT 0
#define BORE_LEVEL 50
#define AMULET ','
#define ARMOR ']'
#define POTION '!'
#define RING '='
#define SCROLL '?'
#define STICK '/'
#define WEAPON ')'

typedef struct stats {
    int strength;
    int exp;
    int level;
    int arm;
    int hp;
    char damage[32];
    int max_hp;
    int flags;
} Stats;

typedef struct ring_obj {
    int present;
    int which;
    int arm;
} RingObj;

typedef struct item {
    char name[32];
    char type;
    int magic;
    int equipped;
} Item;

typedef struct monster {
    char type;
    Stats stats;
    int flags;
    char disguise;
    int has_disguise;
} Monster;

typedef struct world {
    int seed;
    Stats player;
    int player_flags;
    int has_armor;
    int armor_arm;
    RingObj left_ring;
    RingObj right_ring;
    int sustain_strength;
    int running;
    int count;
    int quiet;
    int to_death;
    int kamikaze;
    int has_hit;
    int max_hit;
    int no_command;
    int purse;
    int level;
    int max_hp;
    int vf_hit;
    int fight_flush;
    Item pack[8];
    int pack_count;
    char markers[24][32];
    int marker_count;
    int has_target_cancelled;
    int has_roll_hit;
    int roll_hit;
    int has_roll_rng;
    int roll_rng;
    int has_ice_roll;
    int ice_roll;
    int has_poison_saved;
    int poison_saved;
    int poison_roll;
    int has_drain_roll;
    int drain_roll;
    int has_drain_fewer;
    int drain_fewer;
    int has_gold_saved;
    int gold_saved;
    int gold_save_roll;
    int has_xeroc_hallu;
    char xeroc_hallu;
    int has_stolen;
    char stolen[32];
} World;

typedef struct test_case {
    char name[64];
    int seed;
    char type;
    Stats monster_stats;
    Stats player_stats;
    int monster_flags;
    char disguise;
    int has_disguise;
    int player_flags;
    int has_armor;
    int armor_arm;
    RingObj left_ring;
    RingObj right_ring;
    int sustain_strength;
    int running;
    int count;
    int quiet;
    int to_death;
    int kamikaze;
    int has_hit;
    int max_hit;
    int no_command;
    int purse;
    int level;
    int max_hp;
    int vf_hit;
    int fight_flush;
    Item pack[8];
    int pack_count;
} TestCase;

static int str_plus[32] = {-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3};
static int add_dam[32] = {-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6};
static int e_levels[21] = {10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000, 800000, 2000000, 4000000, 8000000, 0};

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }
int roll(World *world, int number, int sides)
{
    int total = 0;
    while (number-- > 0)
        total += rnd(world, sides) + 1;
    return total;
}
int gold_calc(World *world) { return rnd(world, 50 + 10 * world->level) + 2; }

Stats stats_make(int strength, int exp, int level, int arm, int hp, const char *damage, int max_hp, int flags)
{
    Stats st;
    st.strength = strength;
    st.exp = exp;
    st.level = level;
    st.arm = arm;
    st.hp = hp;
    strncpy(st.damage, damage, sizeof(st.damage) - 1);
    st.damage[sizeof(st.damage) - 1] = '\0';
    st.max_hp = max_hp;
    st.flags = flags;
    return st;
}

RingObj ring_make(int which, int arm)
{
    RingObj ring;
    ring.present = 1;
    ring.which = which;
    ring.arm = arm;
    return ring;
}

Item item_make(const char *name, char type, int magic, int equipped)
{
    Item item;
    strncpy(item.name, name, sizeof(item.name) - 1);
    item.name[sizeof(item.name) - 1] = '\0';
    item.type = type;
    item.magic = magic;
    item.equipped = equipped;
    return item;
}

void marker(World *world, const char *value)
{
    strncpy(world->markers[world->marker_count], value, sizeof(world->markers[world->marker_count]) - 1);
    world->markers[world->marker_count][sizeof(world->markers[world->marker_count]) - 1] = '\0';
    world->marker_count++;
}

int save_world(World *world, int which, int *roll_out)
{
    int adjusted = which;
    int need;
    int save_roll;
    if (which == VS_MAGIC)
    {
        if (world->left_ring.present && world->left_ring.which == R_PROTECT)
            adjusted -= world->left_ring.arm;
        if (world->right_ring.present && world->right_ring.which == R_PROTECT)
            adjusted -= world->right_ring.arm;
    }
    need = 14 + adjusted - world->player.level / 2;
    save_roll = roll(world, 1, 20);
    *roll_out = save_roll;
    return save_roll >= need;
}

void roll_em(World *world, Stats *attacker, Stats *defender, int *did_hit)
{
    char damage_expr[64];
    char *cp;
    int hplus = 0;
    int dplus = 0;
    int defender_arm = defender->arm;
    *did_hit = 0;
    if (!(defender->flags & ISRUN))
        hplus += 4;
    if (world->has_armor)
        defender_arm = world->armor_arm;
    if (world->left_ring.present && world->left_ring.which == R_PROTECT)
        defender_arm -= world->left_ring.arm;
    if (world->right_ring.present && world->right_ring.which == R_PROTECT)
        defender_arm -= world->right_ring.arm;
    strncpy(damage_expr, attacker->damage, sizeof(damage_expr) - 1);
    damage_expr[sizeof(damage_expr) - 1] = '\0';
    cp = damage_expr;
    while (cp != NULL && *cp != '\0')
    {
        int ndice = atoi(cp);
        int nsides;
        int swing_roll;
        int need;
        char *slash;
        cp = strchr(cp, 'x');
        if (cp == NULL)
            break;
        nsides = atoi(++cp);
        swing_roll = rnd(world, 20);
        need = (20 - attacker->level) - defender_arm;
        if (swing_roll + hplus + str_plus[attacker->strength] >= need)
        {
            int damage_roll = roll(world, ndice, nsides);
            int damage = dplus + damage_roll + add_dam[attacker->strength];
            defender->hp -= damage > 0 ? damage : 0;
            *did_hit = 1;
        }
        slash = strchr(cp, '/');
        if (slash == NULL)
            break;
        cp = slash + 1;
    }
}

int is_magic(Item *item)
{
    if (item->type == POTION || item->type == SCROLL || item->type == STICK || item->type == RING || item->type == AMULET)
        return 1;
    if ((item->type == ARMOR || item->type == WEAPON) && item->magic)
        return 1;
    return 0;
}

int pick_nymph_steal(World *world)
{
    int steal_index = -1;
    int nobj = 0;
    for (int i = 0; i < world->pack_count; i++)
    {
        if (world->pack[i].equipped || !is_magic(&world->pack[i]))
            continue;
        nobj++;
        if (rnd(world, nobj) == 0)
            steal_index = i;
    }
    return steal_index;
}

int special_hit(World *world, Monster *monster)
{
    if (monster->type == 'A')
        marker(world, "rust_armor");
    else if (monster->type == 'I')
    {
        world->player_flags &= ~ISRUN;
        if (!world->no_command)
            marker(world, "freeze_msg");
        world->ice_roll = rnd(world, 2) + 2;
        world->has_ice_roll = 1;
        world->no_command += world->ice_roll;
        if (world->no_command > BORE_LEVEL)
            marker(world, "death:h");
    }
    else if (monster->type == 'R')
    {
        int save_roll;
        int saved = save_world(world, VS_POISON, &save_roll);
        world->has_poison_saved = 1;
        world->poison_saved = saved;
        world->poison_roll = save_roll;
        if (!saved)
        {
            if (!world->sustain_strength)
            {
                world->player.strength--;
                marker(world, "chg_str:-1");
            }
            else if (!world->to_death)
                marker(world, "sustain_strength");
        }
    }
    else if (monster->type == 'W' || monster->type == 'V')
    {
        int threshold = monster->type == 'W' ? 15 : 30;
        world->drain_roll = rnd(world, 100);
        world->has_drain_roll = 1;
        if (world->drain_roll < threshold)
        {
            int fewer;
            if (monster->type == 'W')
            {
                if (world->player.exp == 0)
                    marker(world, "death:W");
                world->player.level--;
                if (world->player.level == 0)
                {
                    world->player.exp = 0;
                    world->player.level = 1;
                }
                else
                    world->player.exp = e_levels[world->player.level - 1] + 1;
                fewer = roll(world, 1, 10);
            }
            else
                fewer = roll(world, 1, 3);
            world->drain_fewer = fewer;
            world->has_drain_fewer = 1;
            world->player.hp -= fewer;
            world->max_hp -= fewer;
            if (world->player.hp <= 0)
                world->player.hp = 1;
            if (world->max_hp <= 0)
            {
                char death[16];
                snprintf(death, sizeof(death), "death:%c", monster->type);
                marker(world, death);
            }
            marker(world, "drain");
        }
    }
    else if (monster->type == 'F')
    {
        world->player_flags |= ISHELD;
        world->vf_hit++;
        snprintf(monster->stats.damage, sizeof(monster->stats.damage), "%dx1", world->vf_hit);
        world->player.hp--;
        if (world->player.hp <= 0)
            marker(world, "death:F");
    }
    else if (monster->type == 'L')
    {
        int lastpurse = world->purse;
        int save_roll;
        int saved;
        world->purse -= gold_calc(world);
        saved = save_world(world, VS_MAGIC, &save_roll);
        world->has_gold_saved = 1;
        world->gold_saved = saved;
        world->gold_save_roll = save_roll;
        if (!saved)
            for (int i = 0; i < 4; i++)
                world->purse -= gold_calc(world);
        if (world->purse < 0)
            world->purse = 0;
        marker(world, "remove_mon");
        if (world->purse != lastpurse)
            marker(world, "purse_lighter");
        return 1;
    }
    else if (monster->type == 'N')
    {
        int stolen_index = pick_nymph_steal(world);
        if (stolen_index >= 0)
        {
            strncpy(world->stolen, world->pack[stolen_index].name, sizeof(world->stolen) - 1);
            world->stolen[sizeof(world->stolen) - 1] = '\0';
            world->has_stolen = 1;
            for (int j = stolen_index; j + 1 < world->pack_count; j++)
                world->pack[j] = world->pack[j + 1];
            world->pack_count--;
            marker(world, "remove_mon");
            marker(world, "leave_pack");
            marker(world, "discard");
            return 1;
        }
    }
    return 0;
}

int attack(World *world, Monster *monster)
{
    int oldhp;
    int did_hit;
    int monster_removed = 0;
    world->running = 0;
    world->count = 0;
    world->quiet = 0;
    if (world->to_death && !(monster->flags & ISTARGET))
    {
        world->to_death = 0;
        world->kamikaze = 0;
        world->has_target_cancelled = 1;
    }
    if (monster->type == 'X' && monster->disguise != 'X' && !(world->player_flags & ISBLIND))
    {
        monster->disguise = 'X';
        monster->has_disguise = 1;
        marker(world, "xeroc_reveal");
        if (world->player_flags & ISHALU)
        {
            world->xeroc_hallu = (char)(rnd(world, 26) + 'A');
            world->has_xeroc_hallu = 1;
        }
    }
    oldhp = world->player.hp;
    roll_em(world, &monster->stats, &world->player, &did_hit);
    world->has_roll_hit = 1;
    world->roll_hit = did_hit;
    world->has_roll_rng = 1;
    world->roll_rng = world->seed;
    if (did_hit)
    {
        if (monster->type != 'I')
        {
            if (world->has_hit)
                marker(world, "addmsg_join");
            marker(world, "hit");
        }
        else if (world->has_hit)
            marker(world, "endmsg");
        world->has_hit = 0;
        if (world->player.hp <= 0)
        {
            char death[16];
            snprintf(death, sizeof(death), "death:%c", monster->type);
            marker(world, death);
        }
        else if (!world->kamikaze)
        {
            int damage = oldhp - world->player.hp;
            if (damage > world->max_hit)
                world->max_hit = damage;
            if (world->player.hp <= world->max_hit)
                world->to_death = 0;
        }
        if (!(monster->flags & ISCANC))
            monster_removed = special_hit(world, monster);
    }
    else if (monster->type != 'I')
    {
        if (world->has_hit)
        {
            marker(world, "addmsg_join");
            world->has_hit = 0;
        }
        if (monster->type == 'F')
        {
            world->player.hp -= world->vf_hit;
            if (world->player.hp <= 0)
                marker(world, "death:F");
        }
        marker(world, "miss");
    }
    if (world->fight_flush && !world->to_death)
        marker(world, "flush_type");
    world->count = 0;
    marker(world, "status");
    return monster_removed ? -1 : 0;
}

TestCase base_case(const char *name, int seed, char type)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    strncpy(c.name, name, sizeof(c.name) - 1);
    c.seed = seed;
    c.type = type;
    c.monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN);
    c.player_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN);
    c.monster_flags = ISRUN;
    c.disguise = type;
    c.has_disguise = 1;
    c.player_flags = ISRUN;
    c.has_armor = 1;
    c.armor_arm = 6;
    c.running = 1;
    c.count = 4;
    c.quiet = 7;
    c.purse = 200;
    c.level = 1;
    c.max_hp = 30;
    c.fight_flush = 1;
    return c;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->player = c->player_stats;
    world->player_flags = c->player_flags;
    world->has_armor = c->has_armor;
    world->armor_arm = c->armor_arm;
    world->left_ring = c->left_ring;
    world->right_ring = c->right_ring;
    world->sustain_strength = c->sustain_strength;
    world->running = c->running;
    world->count = c->count;
    world->quiet = c->quiet;
    world->to_death = c->to_death;
    world->kamikaze = c->kamikaze;
    world->has_hit = c->has_hit;
    world->max_hit = c->max_hit;
    world->no_command = c->no_command;
    world->purse = c->purse;
    world->level = c->level;
    world->max_hp = c->max_hp;
    world->vf_hit = c->vf_hit;
    world->fight_flush = c->fight_flush;
    for (int i = 0; i < c->pack_count; i++)
        world->pack[world->pack_count++] = c->pack[i];
}

void print_bool(int value) { printf(value ? "true" : "false"); }
void print_stats(Stats *st)
{
    printf("{\"strength\":%d,\"exp\":%d,\"level\":%d,\"arm\":%d,\"hp\":%d,\"damage\":\"%s\",\"max_hp\":%d,\"flags\":%d}",
        st->strength, st->exp, st->level, st->arm, st->hp, st->damage, st->max_hp, st->flags);
}
void print_trace_value_bool(int present, int value)
{
    if (present) print_bool(value); else printf("null");
}
void print_trace_value_int(int present, int value)
{
    if (present) printf("%d", value); else printf("null");
}
void print_case(TestCase *c)
{
    World world;
    Monster monster;
    int returned;
    world_init(&world, c);
    monster.type = c->type;
    monster.stats = c->monster_stats;
    monster.flags = c->monster_flags;
    monster.disguise = c->disguise;
    monster.has_disguise = c->has_disguise;
    returned = attack(&world, &monster);
    printf("{\"name\":\"%s\",\"seed\":%d,\"returned\":%d,\"monster\":{\"type\":\"%c\",\"flags\":%d,\"disguise\":", c->name, c->seed, returned, monster.type, monster.flags);
    if (monster.has_disguise) printf("\"%c\"", monster.disguise); else printf("null");
    printf(",\"stats\":");
    print_stats(&monster.stats);
    printf("},\"world\":{\"rng_seed\":%d,\"player\":", world.seed);
    print_stats(&world.player);
    printf(",\"player_flags\":%d,\"running\":", world.player_flags);
    print_bool(world.running);
    printf(",\"count\":%d,\"quiet\":%d,\"to_death\":", world.count, world.quiet);
    print_bool(world.to_death);
    printf(",\"kamikaze\":");
    print_bool(world.kamikaze);
    printf(",\"has_hit\":");
    print_bool(world.has_hit);
    printf(",\"max_hit\":%d,\"no_command\":%d,\"purse\":%d,\"level\":%d,\"max_hp\":%d,\"vf_hit\":%d,\"pack\":[", world.max_hit, world.no_command, world.purse, world.level, world.max_hp, world.vf_hit);
    for (int i = 0; i < world.pack_count; i++)
    {
        if (i) printf(",");
        printf("{\"name\":\"%s\",\"type\":\"%c\",\"magic\":", world.pack[i].name, world.pack[i].type);
        print_bool(world.pack[i].magic);
        printf(",\"equipped\":");
        print_bool(world.pack[i].equipped);
        printf("}");
    }
    printf("],\"markers\":[");
    for (int i = 0; i < world.marker_count; i++)
    {
        if (i) printf(",");
        printf("\"%s\"", world.markers[i]);
    }
    printf("],\"trace\":{\"target_cancelled\":");
    print_trace_value_bool(world.has_target_cancelled, 1);
    printf(",\"xeroc_hallu\":");
    if (world.has_xeroc_hallu) printf("\"%c\"", world.xeroc_hallu); else printf("null");
    printf(",\"roll_hit\":");
    print_trace_value_bool(world.has_roll_hit, world.roll_hit);
    printf(",\"roll_rng\":");
    print_trace_value_int(world.has_roll_rng, world.roll_rng);
    printf(",\"ice_roll\":");
    print_trace_value_int(world.has_ice_roll, world.ice_roll);
    printf(",\"poison_saved\":");
    print_trace_value_bool(world.has_poison_saved, world.poison_saved);
    printf(",\"poison_roll\":");
    print_trace_value_int(world.has_poison_saved, world.poison_roll);
    printf(",\"drain_roll\":");
    print_trace_value_int(world.has_drain_roll, world.drain_roll);
    printf(",\"drain_fewer\":");
    print_trace_value_int(world.has_drain_fewer, world.drain_fewer);
    printf(",\"gold_saved\":");
    print_trace_value_bool(world.has_gold_saved, world.gold_saved);
    printf(",\"gold_save_roll\":");
    print_trace_value_int(world.has_gold_saved, world.gold_save_roll);
    printf(",\"stolen\":");
    if (world.has_stolen) printf("\"%s\"", world.stolen); else printf("null");
    printf("}}}");
}

int main(void)
{
    TestCase cases[13];
    int count = 0;
    Stats hard_to_hit = stats_make(16, 100, 1, -10, 30, "1x1", 30, ISRUN);
    cases[count] = base_case("basic_hit_updates_max_hit", 1, 'K'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x4", 30, ISRUN); cases[count].player_stats = stats_make(16, 100, 20, 6, 20, "1x1", 20, ISRUN); cases[count].max_hp = 20; cases[count].max_hit = 1; count++;
    cases[count] = base_case("basic_miss_message", 7, 'K'); cases[count].monster_stats = stats_make(16, 100, 1, 6, 30, "1x1", 30, ISRUN); cases[count].player_stats = hard_to_hit; cases[count].armor_arm = -10; cases[count].has_hit = 1; count++;
    cases[count] = base_case("target_keeps_to_death", 1, 'K'); cases[count].monster_flags = ISRUN | ISTARGET; cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].to_death = 1; cases[count].kamikaze = 1; count++;
    cases[count] = base_case("xeroc_hallu_reveals", 7, 'X'); cases[count].disguise = 'A'; cases[count].player_flags = ISRUN | ISHALU; cases[count].monster_stats = stats_make(16, 100, 1, 6, 30, "1x1", 30, ISRUN); cases[count].player_stats = hard_to_hit; cases[count].armor_arm = -10; count++;
    cases[count] = base_case("aquator_rusts_armor", 1, 'A'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); count++;
    cases[count] = base_case("ice_freezes_player", 1, 'I'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].no_command = 49; count++;
    cases[count] = base_case("rattlesnake_poison_strength", 2, 'R'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].player_stats = stats_make(16, 100, 1, 6, 30, "1x1", 30, ISRUN); count++;
    cases[count] = base_case("rattlesnake_sustain_strength", 2, 'R'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].player_stats = stats_make(16, 100, 1, 6, 30, "1x1", 30, ISRUN); cases[count].sustain_strength = 1; count++;
    cases[count] = base_case("wraith_energy_drain", 3, 'W'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].player_stats = stats_make(16, 200, 5, 6, 30, "1x1", 30, ISRUN); cases[count].max_hp = 30; count++;
    cases[count] = base_case("venus_flytrap_hit_holds", 1, 'F'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].vf_hit = 1; count++;
    cases[count] = base_case("venus_flytrap_miss_crushes", 7, 'F'); cases[count].monster_stats = stats_make(16, 100, 1, 6, 30, "1x1", 30, ISRUN); cases[count].player_stats = hard_to_hit; cases[count].armor_arm = -10; cases[count].vf_hit = 3; count++;
    cases[count] = base_case("leprechaun_steals_gold", 1, 'L'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].purse = 200; cases[count].level = 4; cases[count].left_ring = ring_make(R_PROTECT, 2); count++;
    cases[count] = base_case("nymph_steals_magic_item", 1, 'N'); cases[count].monster_stats = stats_make(16, 100, 20, 6, 30, "1x1", 30, ISRUN); cases[count].pack[cases[count].pack_count++] = item_make("plain-food", ':', 0, 0); cases[count].pack[cases[count].pack_count++] = item_make("worn-armor", ARMOR, 1, 1); cases[count].pack[cases[count].pack_count++] = item_make("wand", STICK, 1, 0); cases[count].pack[cases[count].pack_count++] = item_make("plus-mace", WEAPON, 1, 0); count++;
    printf("{\"schema\":\"gamebench.rogue.source_attack.v1\",\"cases\":[");
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
    return _project(source_attack_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_attack",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-attack-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_attack.c"
        binary = temp / "source_attack"
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
                "returned": case["returned"],
                "monster": {
                    "type": case["monster"]["type"],
                    "flags": case["monster"]["flags"],
                    "disguise": case["monster"]["disguise"],
                    "damage": case["monster"]["stats"]["damage"],
                },
                "world": {
                    "rng_seed": case["world"]["rng_seed"],
                    "player": {
                        "strength": case["world"]["player"]["strength"],
                        "exp": case["world"]["player"]["exp"],
                        "level": case["world"]["player"]["level"],
                        "hp": case["world"]["player"]["hp"],
                        "max_hp": case["world"]["player"]["max_hp"],
                        "flags": case["world"]["player"]["flags"],
                    },
                    "player_flags": case["world"]["player_flags"],
                    "running": case["world"]["running"],
                    "count": case["world"]["count"],
                    "quiet": case["world"]["quiet"],
                    "to_death": case["world"]["to_death"],
                    "kamikaze": case["world"]["kamikaze"],
                    "has_hit": case["world"]["has_hit"],
                    "max_hit": case["world"]["max_hit"],
                    "no_command": case["world"]["no_command"],
                    "purse": case["world"]["purse"],
                    "level": case["world"]["level"],
                    "max_hp": case["world"]["max_hp"],
                    "vf_hit": case["world"]["vf_hit"],
                    "pack": [item["name"] for item in case["world"]["pack"]],
                    "markers": case["world"]["markers"],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_attack.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source attack mismatch")


if __name__ == "__main__":
    main()
