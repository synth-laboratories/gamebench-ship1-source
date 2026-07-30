#!/usr/bin/env python3
"""Compare source-derived Rogue potion branches across C, Python, and Rust."""

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

from source_potions import source_potions_report


TRACE_KEYS = [
    "duration_0",
    "duration_1",
    "duration_4",
    "duration_12",
    "duration_13",
    "poison_loss",
    "heal_roll",
    "turn_see_hallu",
    "level_add",
    "xheal_roll",
    "haste_duration",
    "haste_faint",
]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BEFORE 1
#define AFTER 2
#define DAEMON -1

#define HEALTIME 30
#define HUHDURATION 20
#define SEEDURATION 850

#define ARMOR ']'
#define POTION '!'
#define SCROLL '?'
#define WEAPON ')'
#define AMULET ','
#define RING '='
#define STICK '/'

#define ISPROT 0000040

#define CANSEE 0000002
#define ISBLIND 0000004
#define ISLEVIT 0000010
#define ISHASTE 0000100
#define ISHUH 0001000
#define ISHALU 0004000
#define ISRUN 0020000
#define SEEMONST 040000

#define P_CONFUSE 0
#define P_LSD 1
#define P_POISON 2
#define P_STRENGTH 3
#define P_SEEINVIS 4
#define P_HEALING 5
#define P_MFIND 6
#define P_TFIND 7
#define P_RAISE 8
#define P_XHEAL 9
#define P_HASTE 10
#define P_RESTORE 11
#define P_BLIND 12
#define P_LEVIT 13
#define MAXPOTIONS 14

#define R_ADDSTR 1
#define R_SUSTSTR 2

#define OP_QUAFF 1
#define OP_IS_MAGIC 2

typedef struct potion_object {
    int present;
    char type;
    int which;
    int count;
    int flags;
    int arm;
    int hplus;
    int dplus;
} PotionObject;

typedef struct source_ring {
    int present;
    int which;
    int arm;
} SourceRing;

typedef struct delayed_action {
    const char *action;
    int type;
    int arg;
    int time;
} DelayedAction;

typedef struct world {
    int seed;
    int player_flags;
    int strength;
    int max_strength;
    int level;
    int exp;
    int hp;
    int max_hp;
    int no_command;
    int after;
    int current_weapon_is_obj;
    SourceRing left_ring;
    SourceRing right_ring;
    int pot_known[MAXPOTIONS];
    DelayedAction actions[24];
    int action_count;
    int magic_count;
    int new_monsters;
    int invisible_visible;
    int stairs_visible;
    int seenstairs;
    int proom_gone;
    char markers[64][80];
    int marker_count;
    int has_duration[14];
    int duration[14];
    int has_poison_loss;
    int poison_loss;
    int has_heal_roll;
    int heal_roll;
    int has_level_add;
    int level_add;
    int has_xheal_roll;
    int xheal_roll;
    int has_haste_duration;
    int haste_duration;
    int has_haste_faint;
    int haste_faint;
    char turn_see_hallu[8][2];
    int turn_see_hallu_count;
} World;

typedef struct test_case {
    const char *name;
    int seed;
    int op;
    int player_flags;
    int strength;
    int max_strength;
    int level;
    int exp;
    int hp;
    int max_hp;
    int no_command;
    int after;
    int current_weapon_is_obj;
    SourceRing left_ring;
    SourceRing right_ring;
    DelayedAction actions[8];
    int action_count;
    int magic_count;
    int new_monsters;
    int invisible_visible;
    int stairs_visible;
    int seenstairs;
    int proom_gone;
    PotionObject obj;
} TestCase;

typedef struct potion_action {
    int flag;
    const char *daemon;
    int time;
} PotionAction;

int e_levels[] = {10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000, 800000, 2000000, 4000000, 8000000, 0};
int a_class[] = {8, 7, 7, 6, 5, 4, 4, 3};

#define RN(world) ((((world)->seed = (world)->seed * 11109 + 13849) >> 16) & 0xffff)

int rnd(World *world, int range) { return range == 0 ? 0 : abs((int) RN(world)) % range; }
int roll(World *world, int number, int sides)
{
    int total = 0;
    while (number-- > 0)
        total += rnd(world, sides) + 1;
    return total;
}
int spread(World *world, int nm) { return nm - nm / 20 + rnd(world, nm / 10); }

PotionObject no_object(void)
{
    PotionObject obj = {0, ' ', 0, 1, 0, 0, 0, 0};
    return obj;
}
PotionObject object_make(char type, int which, int count, int flags, int arm, int hplus, int dplus)
{
    PotionObject obj = {1, type, which, count, flags, arm, hplus, dplus};
    return obj;
}
PotionObject potion_make(int which, int count) { return object_make(POTION, which, count, 0, 0, 0, 0); }
SourceRing no_ring(void)
{
    SourceRing ring = {0, 0, 0};
    return ring;
}
SourceRing ring_make(int which, int arm)
{
    SourceRing ring = {1, which, arm};
    return ring;
}
DelayedAction action_make(const char *action, int type, int arg, int time)
{
    DelayedAction delayed = {action, type, arg, time};
    return delayed;
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

void fuse(World *world, const char *action, int arg, int time, int type)
{
    world->actions[world->action_count++] = action_make(action, type, arg, time);
}
void start_daemon(World *world, const char *action, int arg, int type)
{
    world->actions[world->action_count++] = action_make(action, type, arg, DAEMON);
}
void remove_action(World *world, int index)
{
    for (int i = index; i + 1 < world->action_count; i++)
        world->actions[i] = world->actions[i + 1];
    world->action_count--;
}
void kill_daemon(World *world, const char *action)
{
    for (int i = 0; i < world->action_count; i++)
        if (strcmp(world->actions[i].action, action) == 0)
        {
            remove_action(world, i);
            return;
        }
}
void extinguish(World *world, const char *action) { kill_daemon(world, action); }
void lengthen(World *world, const char *action, int extra_time)
{
    for (int i = 0; i < world->action_count; i++)
        if (strcmp(world->actions[i].action, action) == 0)
        {
            world->actions[i].time += extra_time;
            return;
        }
}

int add_str(int value, int amount)
{
    value += amount;
    if (value < 3)
        return 3;
    if (value > 31)
        return 31;
    return value;
}
int is_ring(SourceRing *ring, int which) { return ring->present && ring->which == which; }
int is_wearing(World *world, int which) { return is_ring(&world->left_ring, which) || is_ring(&world->right_ring, which); }
void chg_str(World *world, int amount)
{
    int comp;
    if (amount == 0)
        return;
    world->strength = add_str(world->strength, amount);
    comp = world->strength;
    if (is_ring(&world->left_ring, R_ADDSTR))
        comp = add_str(comp, -world->left_ring.arm);
    if (is_ring(&world->right_ring, R_ADDSTR))
        comp = add_str(comp, -world->right_ring.arm);
    if (comp > world->max_strength)
        world->max_strength = comp;
}
void restore_strength(World *world)
{
    if (is_ring(&world->left_ring, R_ADDSTR))
        world->strength = add_str(world->strength, -world->left_ring.arm);
    if (is_ring(&world->right_ring, R_ADDSTR))
        world->strength = add_str(world->strength, -world->right_ring.arm);
    if (world->strength < world->max_strength)
        world->strength = world->max_strength;
    if (is_ring(&world->left_ring, R_ADDSTR))
        world->strength = add_str(world->strength, world->left_ring.arm);
    if (is_ring(&world->right_ring, R_ADDSTR))
        world->strength = add_str(world->strength, world->right_ring.arm);
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
void come_down(World *world)
{
    if (!(world->player_flags & ISHALU))
        return;
    kill_daemon(world, "visuals");
    world->player_flags &= ~ISHALU;
    marker(world, "come_down");
    if (world->player_flags & ISBLIND)
        return;
    marker(world, "redraw_after_hallu");
}
void invis_on(World *world)
{
    world->player_flags |= CANSEE;
    for (int i = 0; i < world->invisible_visible; i++)
        marker(world, "draw_invisible");
}
int turn_see(World *world, int turn_off)
{
    if (turn_off)
    {
        world->player_flags &= ~SEEMONST;
        marker(world, "turn_see:off");
        return 0;
    }
    for (int i = 0; i < world->new_monsters; i++)
        if (world->player_flags & ISHALU)
        {
            world->turn_see_hallu[world->turn_see_hallu_count][0] = (char)(rnd(world, 26) + 'A');
            world->turn_see_hallu[world->turn_see_hallu_count][1] = '\0';
            world->turn_see_hallu_count++;
        }
    world->player_flags |= SEEMONST;
    marker_i(world, "turn_see:on:", world->new_monsters);
    return world->new_monsters != 0;
}

void check_level(World *world)
{
    int next_level = 1;
    int old_level;
    for (int i = 0; e_levels[i] != 0; i++)
    {
        if (e_levels[i] > world->exp)
            break;
        next_level++;
    }
    old_level = world->level;
    world->level = next_level;
    if (next_level > old_level)
    {
        int add = roll(world, next_level - old_level, 10);
        world->max_hp += add;
        world->hp += add;
        world->level_add = add;
        world->has_level_add = 1;
        marker_i(world, "welcome:", next_level);
    }
}
void raise_level(World *world)
{
    world->exp = e_levels[world->level - 1] + 1;
    check_level(world);
}
int add_haste(World *world, int potion)
{
    if (world->player_flags & ISHASTE)
    {
        int faint = rnd(world, 8);
        world->haste_faint = faint;
        world->has_haste_faint = 1;
        world->no_command += faint;
        world->player_flags &= ~(ISRUN | ISHASTE);
        extinguish(world, "nohaste");
        marker(world, "msg_faint_exhaustion");
        return 0;
    }
    world->player_flags |= ISHASTE;
    if (potion)
    {
        int duration = rnd(world, 4) + 4;
        world->haste_duration = duration;
        world->has_haste_duration = 1;
        fuse(world, "nohaste", 0, duration, AFTER);
    }
    return 1;
}

PotionAction potion_action(int type)
{
    PotionAction action = {0, "", 0};
    if (type == P_CONFUSE) { action.flag = ISHUH; action.daemon = "unconfuse"; action.time = HUHDURATION; }
    else if (type == P_LSD) { action.flag = ISHALU; action.daemon = "come_down"; action.time = SEEDURATION; }
    else if (type == P_SEEINVIS) { action.flag = CANSEE; action.daemon = "unsee"; action.time = SEEDURATION; }
    else if (type == P_BLIND) { action.flag = ISBLIND; action.daemon = "sight"; action.time = SEEDURATION; }
    else if (type == P_LEVIT) { action.flag = ISLEVIT; action.daemon = "land"; action.time = HEALTIME; }
    return action;
}
void do_pot(World *world, int type, int knowit)
{
    PotionAction action = potion_action(type);
    int duration;
    if (!world->pot_known[type])
        world->pot_known[type] = knowit;
    duration = spread(world, action.time);
    world->duration[type] = duration;
    world->has_duration[type] = 1;
    if (!(world->player_flags & action.flag))
    {
        world->player_flags |= action.flag;
        fuse(world, action.daemon, 0, duration, AFTER);
        marker(world, "look:false");
    }
    else
        lengthen(world, action.daemon, duration);
    marker_i(world, "msg_pot:", type);
}
int is_magic(PotionObject *obj)
{
    if (obj->type == ARMOR)
        return (obj->flags & ISPROT) || obj->arm != a_class[obj->which];
    if (obj->type == WEAPON)
        return obj->hplus != 0 || obj->dplus != 0;
    return obj->type == POTION || obj->type == SCROLL || obj->type == STICK || obj->type == RING || obj->type == AMULET;
}

void quaff(World *world, PotionObject *obj)
{
    int trip, discardit;
    if (!obj->present)
        return;
    if (obj->type != POTION)
    {
        marker(world, "undrinkable");
        return;
    }
    if (world->current_weapon_is_obj)
    {
        world->current_weapon_is_obj = 0;
        marker(world, "unwield_potion");
    }
    trip = (world->player_flags & ISHALU) != 0;
    discardit = obj->count == 1;
    marker(world, "leave_pack");
    if (obj->which == P_CONFUSE)
        do_pot(world, P_CONFUSE, !trip);
    else if (obj->which == P_POISON)
    {
        world->pot_known[P_POISON] = 1;
        if (is_wearing(world, R_SUSTSTR))
            marker(world, "msg_momentarily_sick");
        else
        {
            int loss = rnd(world, 3) + 1;
            world->poison_loss = loss;
            world->has_poison_loss = 1;
            chg_str(world, -loss);
            marker(world, "msg_very_sick");
            come_down(world);
        }
    }
    else if (obj->which == P_HEALING)
    {
        int heal;
        world->pot_known[P_HEALING] = 1;
        heal = roll(world, world->level, 4);
        world->heal_roll = heal;
        world->has_heal_roll = 1;
        world->hp += heal;
        if (world->hp > world->max_hp)
        {
            world->max_hp++;
            world->hp = world->max_hp;
        }
        sight(world);
        marker(world, "msg_better");
    }
    else if (obj->which == P_STRENGTH)
    {
        world->pot_known[P_STRENGTH] = 1;
        chg_str(world, 1);
        marker(world, "msg_stronger");
    }
    else if (obj->which == P_MFIND)
    {
        world->player_flags |= SEEMONST;
        fuse(world, "turn_see", 1, HUHDURATION, AFTER);
        if (!turn_see(world, 0))
            marker(world, "msg_monster_fleeting");
    }
    else if (obj->which == P_TFIND)
    {
        if (world->magic_count > 0)
        {
            world->pot_known[P_TFIND] = 1;
            marker_i(world, "show_magic:", world->magic_count);
            marker(world, "show_win_magic");
        }
        else
            marker(world, "msg_magic_fleeting");
    }
    else if (obj->which == P_LSD)
    {
        if (!trip)
        {
            if (world->player_flags & SEEMONST)
                turn_see(world, 0);
            start_daemon(world, "visuals", 0, BEFORE);
            world->seenstairs = world->stairs_visible;
        }
        do_pot(world, P_LSD, 1);
    }
    else if (obj->which == P_SEEINVIS)
    {
        int show = (world->player_flags & CANSEE) != 0;
        do_pot(world, P_SEEINVIS, 0);
        if (!show)
            invis_on(world);
        sight(world);
    }
    else if (obj->which == P_RAISE)
    {
        world->pot_known[P_RAISE] = 1;
        marker(world, "msg_raise");
        raise_level(world);
    }
    else if (obj->which == P_XHEAL)
    {
        int heal;
        world->pot_known[P_XHEAL] = 1;
        heal = roll(world, world->level, 8);
        world->xheal_roll = heal;
        world->has_xheal_roll = 1;
        world->hp += heal;
        if (world->hp > world->max_hp)
        {
            if (world->hp > world->max_hp + world->level + 1)
                world->max_hp++;
            world->max_hp++;
            world->hp = world->max_hp;
        }
        sight(world);
        come_down(world);
        marker(world, "msg_much_better");
    }
    else if (obj->which == P_HASTE)
    {
        world->pot_known[P_HASTE] = 1;
        world->after = 0;
        if (add_haste(world, 1))
            marker(world, "msg_much_faster");
    }
    else if (obj->which == P_RESTORE)
    {
        restore_strength(world);
        marker(world, "msg_restore");
    }
    else if (obj->which == P_BLIND)
        do_pot(world, P_BLIND, 1);
    else if (obj->which == P_LEVIT)
        do_pot(world, P_LEVIT, 1);
    else
    {
        marker(world, "odd_tasting");
        return;
    }
    marker(world, "status");
    marker_i(world, "call_it:", obj->which);
    if (discardit)
        marker(world, "discard");
}

TestCase base_case(const char *name, int seed, int op)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    c.name = name;
    c.seed = seed;
    c.op = op;
    c.strength = 16;
    c.max_strength = 16;
    c.level = 5;
    c.exp = 100;
    c.hp = 12;
    c.max_hp = 20;
    c.after = 1;
    c.left_ring = no_ring();
    c.right_ring = no_ring();
    c.obj = no_object();
    return c;
}
void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->player_flags = c->player_flags;
    world->strength = c->strength;
    world->max_strength = c->max_strength;
    world->level = c->level;
    world->exp = c->exp;
    world->hp = c->hp;
    world->max_hp = c->max_hp;
    world->no_command = c->no_command;
    world->after = c->after;
    world->current_weapon_is_obj = c->current_weapon_is_obj;
    world->left_ring = c->left_ring;
    world->right_ring = c->right_ring;
    world->action_count = c->action_count;
    for (int i = 0; i < c->action_count; i++)
        world->actions[i] = c->actions[i];
    world->magic_count = c->magic_count;
    world->new_monsters = c->new_monsters;
    world->invisible_visible = c->invisible_visible;
    world->stairs_visible = c->stairs_visible;
    world->seenstairs = c->seenstairs;
    world->proom_gone = c->proom_gone;
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
void print_action(DelayedAction *action)
{
    printf("{\"action\":");
    print_string(action->action);
    printf(",\"type\":%d,\"arg\":%d,\"time\":%d}", action->type, action->arg, action->time);
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
    print_trace_int("duration_0", world->has_duration[0], world->duration[0], 0);
    print_trace_int("duration_1", world->has_duration[1], world->duration[1], 1);
    print_trace_int("duration_4", world->has_duration[4], world->duration[4], 1);
    print_trace_int("duration_12", world->has_duration[12], world->duration[12], 1);
    print_trace_int("duration_13", world->has_duration[13], world->duration[13], 1);
    print_trace_int("poison_loss", world->has_poison_loss, world->poison_loss, 1);
    print_trace_int("heal_roll", world->has_heal_roll, world->heal_roll, 1);
    printf(",");
    print_string("turn_see_hallu");
    printf(":");
    if (world->turn_see_hallu_count)
    {
        printf("[");
        for (int i = 0; i < world->turn_see_hallu_count; i++)
        {
            if (i) printf(",");
            print_string(world->turn_see_hallu[i]);
        }
        printf("]");
    }
    else
        printf("null");
    print_trace_int("level_add", world->has_level_add, world->level_add, 1);
    print_trace_int("xheal_roll", world->has_xheal_roll, world->xheal_roll, 1);
    print_trace_int("haste_duration", world->has_haste_duration, world->haste_duration, 1);
    print_trace_int("haste_faint", world->has_haste_faint, world->haste_faint, 1);
    printf("}");
}
void print_case(TestCase *c)
{
    World world;
    int bool_result = 0;
    int has_result = 0;
    world_init(&world, c);
    if (c->op == OP_QUAFF)
        quaff(&world, &c->obj);
    else if (c->op == OP_IS_MAGIC)
    {
        bool_result = is_magic(&c->obj);
        has_result = 1;
    }
    printf("{\"name\":");
    print_string(c->name);
    printf(",\"seed\":%d,\"result\":", c->seed);
    if (has_result) print_bool(bool_result); else printf("null");
    printf(",\"world\":{\"rng_seed\":%d,\"player_flags\":%d,\"strength\":%d,\"max_strength\":%d,\"level\":%d,\"exp\":%d,\"hp\":%d,\"max_hp\":%d,\"no_command\":%d,\"after\":",
        world.seed, world.player_flags, world.strength, world.max_strength, world.level, world.exp, world.hp, world.max_hp, world.no_command);
    print_bool(world.after);
    printf(",\"current_weapon_is_obj\":");
    print_bool(world.current_weapon_is_obj);
    printf(",\"pot_known\":[");
    for (int i = 0; i < MAXPOTIONS; i++)
    {
        if (i) printf(",");
        print_bool(world.pot_known[i]);
    }
    printf("],\"actions\":[");
    for (int i = 0; i < world.action_count; i++)
    {
        if (i) printf(",");
        print_action(&world.actions[i]);
    }
    printf("],\"seenstairs\":");
    print_bool(world.seenstairs);
    printf(",\"markers\":[");
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
    TestCase cases[25];
    int count = 0;
    cases[count] = base_case("quaff_non_potion_rejected", 1, OP_QUAFF); cases[count].obj = object_make(':', 0, 1, 0, 0, 0, 0); count++;
    cases[count] = base_case("confuse_new", 1, OP_QUAFF); cases[count].obj = potion_make(P_CONFUSE, 1); count++;
    cases[count] = base_case("confuse_lengthens", 1, OP_QUAFF); cases[count].player_flags = ISHUH; cases[count].actions[cases[count].action_count++] = action_make("unconfuse", AFTER, 0, 5); cases[count].obj = potion_make(P_CONFUSE, 1); count++;
    cases[count] = base_case("poison_sustained", 1, OP_QUAFF); cases[count].left_ring = ring_make(R_SUSTSTR, 0); cases[count].obj = potion_make(P_POISON, 1); count++;
    cases[count] = base_case("poison_strength_loss_come_down", 1, OP_QUAFF); cases[count].player_flags = ISHALU; cases[count].strength = 16; cases[count].actions[cases[count].action_count++] = action_make("visuals", BEFORE, 0, DAEMON); cases[count].obj = potion_make(P_POISON, 1); count++;
    cases[count] = base_case("healing_caps_hp", 1, OP_QUAFF); cases[count].level = 4; cases[count].hp = 19; cases[count].max_hp = 20; cases[count].obj = potion_make(P_HEALING, 1); count++;
    cases[count] = base_case("strength_updates_max", 1, OP_QUAFF); cases[count].strength = 16; cases[count].max_strength = 16; cases[count].obj = potion_make(P_STRENGTH, 1); count++;
    cases[count] = base_case("mfind_fleeting", 1, OP_QUAFF); cases[count].new_monsters = 0; cases[count].obj = potion_make(P_MFIND, 1); count++;
    cases[count] = base_case("mfind_reveals", 1, OP_QUAFF); cases[count].new_monsters = 2; cases[count].obj = potion_make(P_MFIND, 1); count++;
    cases[count] = base_case("tfind_shows_magic", 1, OP_QUAFF); cases[count].magic_count = 3; cases[count].obj = potion_make(P_TFIND, 1); count++;
    cases[count] = base_case("tfind_fleeting", 1, OP_QUAFF); cases[count].magic_count = 0; cases[count].obj = potion_make(P_TFIND, 1); count++;
    cases[count] = base_case("lsd_starts_visuals", 1, OP_QUAFF); cases[count].player_flags = SEEMONST; cases[count].new_monsters = 1; cases[count].stairs_visible = 1; cases[count].obj = potion_make(P_LSD, 1); count++;
    cases[count] = base_case("seeinvis_new", 1, OP_QUAFF); cases[count].invisible_visible = 2; cases[count].obj = potion_make(P_SEEINVIS, 1); count++;
    cases[count] = base_case("seeinvis_existing_blind", 1, OP_QUAFF); cases[count].player_flags = CANSEE | ISBLIND; cases[count].actions[cases[count].action_count++] = action_make("unsee", AFTER, 0, 5); cases[count].actions[cases[count].action_count++] = action_make("sight", AFTER, 0, 5); cases[count].obj = potion_make(P_SEEINVIS, 1); count++;
    cases[count] = base_case("raise_level", 1, OP_QUAFF); cases[count].level = 5; cases[count].exp = 100; cases[count].hp = 12; cases[count].max_hp = 20; cases[count].obj = potion_make(P_RAISE, 1); count++;
    cases[count] = base_case("xheal_big_come_down_blind", 1, OP_QUAFF); cases[count].player_flags = ISHALU | ISBLIND; cases[count].level = 5; cases[count].hp = 19; cases[count].max_hp = 20; cases[count].obj = potion_make(P_XHEAL, 1); count++;
    cases[count] = base_case("haste_new", 1, OP_QUAFF); cases[count].after = 1; cases[count].obj = potion_make(P_HASTE, 1); count++;
    cases[count] = base_case("haste_exhaustion", 1, OP_QUAFF); cases[count].player_flags = ISHASTE | ISRUN; cases[count].actions[cases[count].action_count++] = action_make("nohaste", AFTER, 0, 5); cases[count].obj = potion_make(P_HASTE, 1); count++;
    cases[count] = base_case("restore_with_addstr", 1, OP_QUAFF); cases[count].strength = 10; cases[count].max_strength = 16; cases[count].left_ring = ring_make(R_ADDSTR, 2); cases[count].obj = potion_make(P_RESTORE, 1); count++;
    cases[count] = base_case("blind_new", 1, OP_QUAFF); cases[count].obj = potion_make(P_BLIND, 1); count++;
    cases[count] = base_case("levit_new_unwields", 1, OP_QUAFF); cases[count].current_weapon_is_obj = 1; cases[count].obj = potion_make(P_LEVIT, 1); count++;
    cases[count] = base_case("is_magic_protected_armor", 1, OP_IS_MAGIC); cases[count].obj = object_make(ARMOR, 0, 1, ISPROT, 8, 0, 0); count++;
    cases[count] = base_case("is_magic_plain_weapon", 1, OP_IS_MAGIC); cases[count].obj = object_make(WEAPON, 0, 1, 0, 0, 0, 0); count++;
    cases[count] = base_case("is_magic_enchanted_weapon", 1, OP_IS_MAGIC); cases[count].obj = object_make(WEAPON, 0, 1, 0, 0, 1, 0); count++;
    cases[count] = base_case("is_magic_ring", 1, OP_IS_MAGIC); cases[count].obj = object_make(RING, 0, 1, 0, 0, 0, 0); count++;
    printf("{\"schema\":\"gamebench.rogue.source_potions.v1\",\"cases\":[");
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
    return _project(source_potions_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_potions",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-potions-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_potions.c"
        binary = temp / "source_potions"
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
                    "player_flags": case["world"]["player_flags"],
                    "strength": case["world"]["strength"],
                    "max_strength": case["world"]["max_strength"],
                    "level": case["world"]["level"],
                    "exp": case["world"]["exp"],
                    "hp": case["world"]["hp"],
                    "max_hp": case["world"]["max_hp"],
                    "no_command": case["world"]["no_command"],
                    "after": case["world"]["after"],
                    "current_weapon_is_obj": case["world"]["current_weapon_is_obj"],
                    "pot_known": case["world"]["pot_known"],
                    "actions": case["world"]["actions"],
                    "seenstairs": case["world"]["seenstairs"],
                    "markers": case["world"]["markers"],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_potions.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source potions mismatch")


if __name__ == "__main__":
    main()
