#!/usr/bin/env python3
"""Compare source-derived Rogue room generation across Python and Rust."""

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

from source_level import generate_new_level_slice, generate_passage_slice, generate_room_slice


CASES = [(1, 1), (7, 1), (12345, 1), (12345, 6), (-17, 12), (67, 6), (24680, 26), (31415, 30)]

C_SOURCE = r'''
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>

#define MAXROOMS 9
#define MAXPASS 13
#define MAXOBJ 9
#define MAXTRAPS 10
#define AMULETLEVEL 26
#define NUMLINES 24
#define NUMCOLS 80
#define DOOR '+'
#define FLOOR '.'
#define GOLD '*'
#define POTION '!'
#define SCROLL '?'
#define FOOD ':'
#define WEAPON ')'
#define ARMOR ']'
#define RING '='
#define STICK '/'
#define STAIRS '%'
#define AMULET ','
#define PASSAGE '#'
#define ISDARK 0000001
#define ISGONE 0000002
#define ISMAZE 0000004
#define ISCURSED 000001
#define ISMISL 0000004
#define ISMANY 0000010
#define F_PASS 0x80
#define F_REAL 0x10
#define F_PNUM 0x0f
#define R_PROTECT 0
#define R_ADDSTR 1
#define R_AGGR 6
#define R_ADDHIT 7
#define R_ADDDAM 8
#define R_TELEPORT 11
#define WS_LIGHT 0
#define DAGGER 4
#define GOLDGRP 1
#define TREAS_ROOM 20
#define MAXTREAS 10
#define MINTREAS 2
#define MAXTRIES 10
#define NTRAPS 8
#define ISGREED 0000040
#define ISHASTE 0000100
#define ISINVIS 0002000
#define ISMEAN 0004000
#define ISREGEN 0010000
#define ISFLY 0040000

typedef struct coord {
    int y;
    int x;
} Coord;

typedef struct room {
    Coord pos;
    Coord max;
    Coord gold;
    int goldval;
    short flags;
    int nexits;
    Coord exits[12];
} Room;

typedef struct place {
    char ch;
    unsigned char flags;
    int monst;
} Place;

typedef struct source_object {
    char type;
    int which;
    Coord pos;
    int count;
    int hplus;
    int dplus;
    int arm;
    int flags;
    int group;
    int goldval;
} SourceObject;

typedef struct source_monster {
    char type;
    Coord pos;
    int level;
    int hp;
    char disguise;
    int flags;
    int pack_count;
    SourceObject pack[16];
} SourceMonster;

typedef struct source_trap {
    Coord pos;
    int kind;
} SourceTrap;

static int seed;
static int level;
static int max_level;
static int amulet;
static Room rooms[MAXROOMS];
static Room passages[MAXPASS];
static Place places[NUMLINES][NUMCOLS];
static Coord monster_slots[64];
static SourceMonster monsters_out[128];
static SourceObject level_objects[256];
static SourceTrap traps_out[32];
static Coord stairs;
static Coord hero;
static int monster_count;
static int monsters_out_count;
static int level_object_count;
static int trap_count;
static int ntraps;
static int maze_maxy;
static int maze_maxx;
static int maze_starty;
static int maze_startx;
static int pnum;
static int newpnum;
static int no_food;
static int weapon_group;

static char lvl_mons[26] = {
    'K', 'E', 'B', 'S', 'H', 'I', 'R', 'O', 'Z', 'L', 'C', 'Q', 'A',
    'N', 'Y', 'F', 'T', 'W', 'P', 'X', 'U', 'M', 'V', 'G', 'J', 'D'
};
static int monster_carry[26] = {0, 0, 15, 100, 0, 0, 20, 0, 0, 70, 0, 0, 40, 100, 15, 0, 0, 0, 0, 50, 0, 20, 0, 30, 30, 0};
static int monster_levels[26] = {5, 1, 4, 10, 1, 8, 13, 1, 1, 15, 1, 3, 8, 3, 1, 8, 3, 2, 1, 6, 7, 8, 5, 7, 4, 2};
static int monster_flags[26] = {
    ISMEAN, ISFLY, 0, ISMEAN, ISMEAN, ISMEAN, ISMEAN|ISFLY|ISREGEN, ISMEAN, 0, 0,
    ISMEAN|ISFLY, 0, ISMEAN, 0, ISGREED, ISINVIS, ISMEAN, ISMEAN, ISMEAN,
    ISREGEN|ISMEAN, ISMEAN, ISREGEN|ISMEAN, 0, 0, 0, ISMEAN
};
static int thing_probs[7] = {26, 36, 16, 7, 7, 4, 4};
static int armor_probs[8] = {20, 15, 15, 13, 12, 10, 10, 5};
static int potion_probs[14] = {7, 8, 8, 13, 3, 13, 6, 6, 2, 5, 5, 13, 5, 6};
static int ring_probs[14] = {9, 9, 5, 10, 10, 1, 10, 8, 8, 4, 9, 5, 7, 5};
static int scroll_probs[18] = {7, 4, 2, 3, 7, 10, 10, 6, 7, 10, 3, 2, 5, 8, 4, 7, 3, 2};
static int weapon_probs[9] = {11, 11, 12, 12, 8, 10, 12, 12, 12};
static int stick_probs[14] = {12, 6, 3, 3, 3, 15, 10, 10, 11, 9, 1, 6, 6, 5};
static int a_class[8] = {8, 7, 7, 6, 5, 4, 4, 3};
static int init_weapon_flags[9] = {0, 0, 0, ISMANY|ISMISL, ISMISL|ISMISL, 0, ISMANY|ISMISL, ISMANY|ISMISL, ISMISL};
static char rnd_thing_list[10] = {POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS, GOLD, AMULET};

#define RN (((seed = seed*11109+13849) >> 16) & 0xffff)

int rnd(int range)
{
    return range == 0 ? 0 : abs((int) RN) % range;
}

int gold_calc(void)
{
    return rnd(50 + 10 * level) + 2;
}

int roll(int number, int sides)
{
    int total = 0;
    while (number--)
        total += rnd(sides) + 1;
    return total;
}

int step_ok(int ch)
{
    switch (ch)
    {
        case ' ':
        case '|':
        case '-':
            return 0;
        default:
            return (!isalpha(ch));
    }
}

int pick_one(int *info, int nitems)
{
    int i = rnd(100);
    for (int index = 0; index < nitems; index++)
        if (i < info[index])
            return index;
    return 0;
}

char rnd_thing(void)
{
    if (level >= 26)
        return rnd_thing_list[rnd(10)];
    return rnd_thing_list[rnd(9)];
}

SourceObject new_item_object(void)
{
    SourceObject obj;
    obj.type = 0;
    obj.which = 0;
    obj.pos.y = 0;
    obj.pos.x = 0;
    obj.count = 0;
    obj.hplus = 0;
    obj.dplus = 0;
    obj.arm = 0;
    obj.flags = 0;
    obj.group = 0;
    obj.goldval = 0;
    return obj;
}

void init_weapon(SourceObject *obj, int which)
{
    obj->type = WEAPON;
    obj->which = which;
    obj->flags = init_weapon_flags[which];
    obj->hplus = 0;
    obj->dplus = 0;
    if (which == DAGGER)
    {
        obj->count = rnd(4) + 2;
        obj->group = weapon_group++;
    }
    else if (obj->flags & ISMANY)
    {
        obj->count = rnd(8) + 8;
        obj->group = weapon_group++;
    }
    else
    {
        obj->count = 1;
        obj->group = 0;
    }
}

SourceObject new_thing(void)
{
    SourceObject obj;
    int r;
    obj = new_item_object();
    obj.count = 1;
    obj.hplus = 0;
    obj.dplus = 0;
    obj.arm = 11;
    obj.flags = 0;
    obj.group = 0;
    switch (no_food > 3 ? 2 : pick_one(thing_probs, 7))
    {
        case 0:
            obj.type = POTION;
            obj.which = pick_one(potion_probs, 14);
            break;
        case 1:
            obj.type = SCROLL;
            obj.which = pick_one(scroll_probs, 18);
            break;
        case 2:
            obj.type = FOOD;
            no_food = 0;
            if (rnd(10) != 0)
                obj.which = 0;
            else
                obj.which = 1;
            break;
        case 3:
            init_weapon(&obj, pick_one(weapon_probs, 9));
            if ((r = rnd(100)) < 10)
            {
                obj.flags |= ISCURSED;
                obj.hplus -= rnd(3) + 1;
            }
            else if (r < 15)
                obj.hplus += rnd(3) + 1;
            break;
        case 4:
            obj.type = ARMOR;
            obj.which = pick_one(armor_probs, 8);
            obj.arm = a_class[obj.which];
            if ((r = rnd(100)) < 20)
            {
                obj.flags |= ISCURSED;
                obj.arm += rnd(3) + 1;
            }
            else if (r < 28)
                obj.arm -= rnd(3) + 1;
            break;
        case 5:
            obj.type = RING;
            obj.which = pick_one(ring_probs, 14);
            switch (obj.which)
            {
                case R_ADDSTR:
                case R_PROTECT:
                case R_ADDHIT:
                case R_ADDDAM:
                    if ((obj.arm = rnd(3)) == 0)
                    {
                        obj.arm = -1;
                        obj.flags |= ISCURSED;
                    }
                    break;
                case R_AGGR:
                case R_TELEPORT:
                    obj.flags |= ISCURSED;
                    break;
            }
            break;
        case 6:
            obj.type = STICK;
            obj.which = pick_one(stick_probs, 14);
            if (obj.which == WS_LIGHT)
                obj.arm = rnd(10) + 10;
            else
                obj.arm = rnd(5) + 3;
            break;
    }
    return obj;
}

char randmonster(void)
{
    int d;
    do
    {
        d = level + (rnd(10) - 6);
        if (d < 0)
            d = rnd(5);
        if (d > 25)
            d = rnd(5) + 21;
    } while (lvl_mons[d] == 0);
    return lvl_mons[d];
}

SourceMonster new_monster(char type, Coord pos)
{
    SourceMonster monster;
    int lev_add = level - 26;
    int index = type - 'A';
    if (lev_add < 0)
        lev_add = 0;
    monster.type = type;
    monster.pos = pos;
    monster.level = monster_levels[index] + lev_add;
    monster.hp = roll(monster.level, 8);
    monster.disguise = (type == 'X') ? rnd_thing() : type;
    monster.flags = monster_flags[index];
    if (level > 29)
        monster.flags |= ISHASTE;
    monster.pack_count = 0;
    return monster;
}

void give_pack(SourceMonster *monster)
{
    int index = monster->type - 'A';
    if (level >= max_level && rnd(100) < monster_carry[index])
    {
        for (int i = monster->pack_count; i > 0; i--)
            monster->pack[i] = monster->pack[i - 1];
        monster->pack[0] = new_thing();
        monster->pack_count++;
    }
}

void attach_monster(SourceMonster monster)
{
    for (int i = monsters_out_count; i > 0; i--)
        monsters_out[i] = monsters_out[i - 1];
    monsters_out[0] = monster;
    monsters_out_count++;
}

void attach_object(SourceObject obj)
{
    for (int i = level_object_count; i > 0; i--)
        level_objects[i] = level_objects[i - 1];
    level_objects[0] = obj;
    level_object_count++;
}

int rnd_room(void)
{
    int rm;
    do
    {
        rm = rnd(MAXROOMS);
    } while (rooms[rm].flags & ISGONE);
    return rm;
}

void set_ch(int y, int x, char ch)
{
    places[y][x].ch = ch;
}

unsigned char flags_at(int y, int x)
{
    return places[y][x].flags;
}

void vert(int room_index, int startx)
{
    Room *rp = &rooms[room_index];
    for (int y = rp->pos.y + 1; y <= rp->max.y + rp->pos.y - 1; y++)
        set_ch(y, startx, '|');
}

void horiz(int room_index, int starty)
{
    Room *rp = &rooms[room_index];
    for (int x = rp->pos.x; x <= rp->pos.x + rp->max.x - 1; x++)
        set_ch(starty, x, '-');
}

void putpass(Coord cp)
{
    Place *pp = &places[cp.y][cp.x];
    pp->flags |= F_PASS;
    if (rnd(10) + 1 < level && rnd(40) == 0)
        pp->flags &= ~F_REAL;
    else
        pp->ch = PASSAGE;
}

void dig(int y, int x)
{
    Coord del[4] = {{2, 0}, {-2, 0}, {0, 2}, {0, -2}};
    for (;;)
    {
        int cnt = 0;
        int nexty = 0;
        int nextx = 0;
        for (int i = 0; i < 4; i++)
        {
            int newy = y + del[i].y;
            int newx = x + del[i].x;
            if (newy < 0 || newy > maze_maxy || newx < 0 || newx > maze_maxx)
                continue;
            if (flags_at(newy + maze_starty, newx + maze_startx) & F_PASS)
                continue;
            if (rnd(++cnt) == 0)
            {
                nexty = newy;
                nextx = newx;
            }
        }
        if (cnt == 0)
            return;
        Coord pos;
        if (nexty == y)
        {
            pos.y = y + maze_starty;
            if (nextx - x < 0)
                pos.x = nextx + maze_startx + 1;
            else
                pos.x = nextx + maze_startx - 1;
        }
        else
        {
            pos.x = x + maze_startx;
            if (nexty - y < 0)
                pos.y = nexty + maze_starty + 1;
            else
                pos.y = nexty + maze_starty - 1;
        }
        putpass(pos);
        pos.y = nexty + maze_starty;
        pos.x = nextx + maze_startx;
        putpass(pos);
        dig(nexty, nextx);
    }
}

void do_maze(int room_index)
{
    Room *rp = &rooms[room_index];
    maze_maxy = rp->max.y;
    maze_maxx = rp->max.x;
    maze_starty = rp->pos.y;
    maze_startx = rp->pos.x;
    int starty = (rnd(rp->max.y) / 2) * 2;
    int startx = (rnd(rp->max.x) / 2) * 2;
    Coord pos = {starty + maze_starty, startx + maze_startx};
    putpass(pos);
    dig(starty, startx);
}

void draw_room(int room_index)
{
    Room *rp = &rooms[room_index];
    if (rp->flags & ISMAZE)
    {
        do_maze(room_index);
        return;
    }
    vert(room_index, rp->pos.x);
    vert(room_index, rp->pos.x + rp->max.x - 1);
    horiz(room_index, rp->pos.y);
    horiz(room_index, rp->pos.y + rp->max.y - 1);
    for (int y = rp->pos.y + 1; y < rp->pos.y + rp->max.y - 1; y++)
        for (int x = rp->pos.x + 1; x < rp->pos.x + rp->max.x - 1; x++)
            set_ch(y, x, FLOOR);
}

Coord rnd_pos(int room_index)
{
    Room *rp = &rooms[room_index];
    Coord cp;
    cp.x = rp->pos.x + rnd(rp->max.x - 2) + 1;
    cp.y = rp->pos.y + rnd(rp->max.y - 2) + 1;
    return cp;
}

int try_find_floor(int room_index, int pickroom, int limit, int monst, Coord *out)
{
    int cnt = limit;
    char compchar = 0;
    if (!pickroom)
        compchar = (rooms[room_index].flags & ISMAZE) ? PASSAGE : FLOOR;
    for (;;)
    {
        if (limit && cnt-- == 0)
            return 0;
        if (pickroom)
        {
            room_index = rnd_room();
            compchar = (rooms[room_index].flags & ISMAZE) ? PASSAGE : FLOOR;
        }
        Coord cp = rnd_pos(room_index);
        Place *pp = &places[cp.y][cp.x];
        if (monst)
        {
            if (!pp->monst && step_ok(pp->ch))
            {
                *out = cp;
                return 1;
            }
        }
        else if (pp->ch == compchar)
        {
            *out = cp;
            return 1;
        }
    }
}

Coord find_floor(int room_index, int pickroom, int limit, int monst)
{
    Coord cp = {0, 0};
    if (!try_find_floor(room_index, pickroom, limit, monst, &cp))
        exit(17);
    return cp;
}

void conn(int r1, int r2);
void door(int room_index, Coord cp);
void do_passages(void);
void passnum(void);
void numpass(int y, int x);

void init_state(int initial_seed, int dungeon_level)
{
    seed = initial_seed;
    level = dungeon_level;
    max_level = dungeon_level;
    amulet = 0;
    monster_count = 0;
    monsters_out_count = 0;
    level_object_count = 0;
    trap_count = 0;
    ntraps = 0;
    stairs.y = 0;
    stairs.x = 0;
    hero.y = 0;
    hero.x = 0;
    no_food = 0;
    weapon_group = 2;
    for (int y = 0; y < NUMLINES; y++)
        for (int x = 0; x < NUMCOLS; x++)
        {
            places[y][x].ch = ' ';
            places[y][x].flags = F_REAL;
            places[y][x].monst = 0;
        }
    for (int i = 0; i < MAXROOMS; i++)
    {
        rooms[i].pos.y = 0;
        rooms[i].pos.x = 0;
        rooms[i].max.y = 0;
        rooms[i].max.x = 0;
        rooms[i].gold.y = 0;
        rooms[i].gold.x = 0;
        rooms[i].goldval = 0;
        rooms[i].flags = 0;
        rooms[i].nexits = 0;
        for (int j = 0; j < 12; j++)
        {
            rooms[i].exits[j].y = 0;
            rooms[i].exits[j].x = 0;
        }
    }
    for (int i = 0; i < MAXPASS; i++)
    {
        passages[i].pos.y = 0;
        passages[i].pos.x = 0;
        passages[i].max.y = 0;
        passages[i].max.x = 0;
        passages[i].gold.y = 0;
        passages[i].gold.x = 0;
        passages[i].goldval = 0;
        passages[i].flags = 0;
        passages[i].nexits = 0;
        for (int j = 0; j < 12; j++)
        {
            passages[i].exits[j].y = 0;
            passages[i].exits[j].x = 0;
        }
    }
}

void do_rooms(void)
{
    Coord bsze = {NUMLINES / 3, NUMCOLS / 3};
    int left_out = rnd(4);
    for (int i = 0; i < left_out; i++)
        rooms[rnd_room()].flags |= ISGONE;
    for (int i = 0; i < MAXROOMS; i++)
    {
        Room *rp = &rooms[i];
        Coord top = {(i / 3) * bsze.y, (i % 3) * bsze.x + 1};
        if (rp->flags & ISGONE)
        {
            do
            {
                rp->pos.x = top.x + rnd(bsze.x - 2) + 1;
                rp->pos.y = top.y + rnd(bsze.y - 2) + 1;
                rp->max.x = -NUMCOLS;
                rp->max.y = -NUMLINES;
            } while (!(rp->pos.y > 0 && rp->pos.y < NUMLINES - 1));
            continue;
        }
        if (rnd(10) < level - 1)
        {
            rp->flags |= ISDARK;
            if (rnd(15) == 0)
                rp->flags = ISMAZE;
        }
        if (rp->flags & ISMAZE)
        {
            rp->max.x = bsze.x - 1;
            rp->max.y = bsze.y - 1;
            rp->pos.x = top.x;
            if (rp->pos.x == 1)
                rp->pos.x = 0;
            rp->pos.y = top.y;
            if (rp->pos.y == 0)
            {
                rp->pos.y++;
                rp->max.y--;
            }
        }
        else
        {
            do
            {
                rp->max.x = rnd(bsze.x - 4) + 4;
                rp->max.y = rnd(bsze.y - 4) + 4;
                rp->pos.x = top.x + rnd(bsze.x - rp->max.x);
                rp->pos.y = top.y + rnd(bsze.y - rp->max.y);
            } while (rp->pos.y == 0);
        }
        draw_room(i);
        if (rnd(2) == 0 && (!amulet || level >= max_level))
        {
            SourceObject gold = new_item_object();
            rp->goldval = gold_calc();
            rp->gold = find_floor(i, 0, 0, 0);
            set_ch(rp->gold.y, rp->gold.x, GOLD);
            gold.goldval = rp->goldval;
            gold.pos = rp->gold;
            gold.flags = ISMANY;
            gold.group = GOLDGRP;
            gold.type = GOLD;
            attach_object(gold);
        }
        if (rnd(100) < (rp->goldval > 0 ? 80 : 25))
        {
            Coord mp = find_floor(i, 0, 0, 1);
            SourceMonster monster;
            places[mp.y][mp.x].monst = 1;
            monster_slots[monster_count++] = mp;
            monster = new_monster(randmonster(), mp);
            give_pack(&monster);
            attach_monster(monster);
        }
    }
}

void do_passages(void)
{
    int conn_table[MAXROOMS][MAXROOMS] = {
        { 0, 1, 0, 1, 0, 0, 0, 0, 0 },
        { 1, 0, 1, 0, 1, 0, 0, 0, 0 },
        { 0, 1, 0, 0, 0, 1, 0, 0, 0 },
        { 1, 0, 0, 0, 1, 0, 1, 0, 0 },
        { 0, 1, 0, 1, 0, 1, 0, 1, 0 },
        { 0, 0, 1, 0, 1, 0, 0, 0, 1 },
        { 0, 0, 0, 1, 0, 0, 0, 1, 0 },
        { 0, 0, 0, 0, 1, 0, 1, 0, 1 },
        { 0, 0, 0, 0, 0, 1, 0, 1, 0 },
    };
    int isconn[MAXROOMS][MAXROOMS] = {{0}};
    int ingraph[MAXROOMS] = {0};
    int roomcount = 1;
    int r1 = rnd(MAXROOMS);
    int r2 = 0;
    ingraph[r1] = 1;
    do
    {
        int j = 0;
        for (int i = 0; i < MAXROOMS; i++)
            if (conn_table[r1][i] && !ingraph[i] && rnd(++j) == 0)
                r2 = i;
        if (j == 0)
        {
            do
                r1 = rnd(MAXROOMS);
            while (!ingraph[r1]);
        }
        else
        {
            ingraph[r2] = 1;
            conn(r1, r2);
            isconn[r1][r2] = 1;
            isconn[r2][r1] = 1;
            roomcount++;
        }
    } while (roomcount < MAXROOMS);

    for (roomcount = rnd(5); roomcount > 0; roomcount--)
    {
        r1 = rnd(MAXROOMS);
        int j = 0;
        for (int i = 0; i < MAXROOMS; i++)
            if (conn_table[r1][i] && !isconn[r1][i] && rnd(++j) == 0)
                r2 = i;
        if (j != 0)
        {
            conn(r1, r2);
            isconn[r1][r2] = 1;
            isconn[r2][r1] = 1;
        }
    }
    passnum();
}

void conn(int r1, int r2)
{
    Room *rpf, *rpt;
    int rmt;
    int distance = 0;
    int turn_spot;
    int turn_distance = 0;
    int rm;
    char direc;
    Coord del = {0, 0};
    Coord curr = {0, 0};
    Coord turn_delta = {0, 0};
    Coord spos = {0, 0};
    Coord epos = {0, 0};

    if (r1 < r2)
    {
        rm = r1;
        if (r1 + 1 == r2)
            direc = 'r';
        else
            direc = 'd';
    }
    else
    {
        rm = r2;
        if (r2 + 1 == r1)
            direc = 'r';
        else
            direc = 'd';
    }
    rpf = &rooms[rm];
    if (direc == 'd')
    {
        rmt = rm + 3;
        rpt = &rooms[rmt];
        del.x = 0;
        del.y = 1;
        spos.x = rpf->pos.x;
        spos.y = rpf->pos.y;
        epos.x = rpt->pos.x;
        epos.y = rpt->pos.y;
        if (!(rpf->flags & ISGONE))
            do
            {
                spos.x = rpf->pos.x + rnd(rpf->max.x - 2) + 1;
                spos.y = rpf->pos.y + rpf->max.y - 1;
            } while ((rpf->flags & ISMAZE) && !(flags_at(spos.y, spos.x) & F_PASS));
        if (!(rpt->flags & ISGONE))
            do
            {
                epos.x = rpt->pos.x + rnd(rpt->max.x - 2) + 1;
            } while ((rpt->flags & ISMAZE) && !(flags_at(epos.y, epos.x) & F_PASS));
        distance = abs(spos.y - epos.y) - 1;
        turn_delta.y = 0;
        turn_delta.x = (spos.x < epos.x ? 1 : -1);
        turn_distance = abs(spos.x - epos.x);
    }
    else
    {
        rmt = rm + 1;
        rpt = &rooms[rmt];
        del.x = 1;
        del.y = 0;
        spos.x = rpf->pos.x;
        spos.y = rpf->pos.y;
        epos.x = rpt->pos.x;
        epos.y = rpt->pos.y;
        if (!(rpf->flags & ISGONE))
            do
            {
                spos.x = rpf->pos.x + rpf->max.x - 1;
                spos.y = rpf->pos.y + rnd(rpf->max.y - 2) + 1;
            } while ((rpf->flags & ISMAZE) && !(flags_at(spos.y, spos.x) & F_PASS));
        if (!(rpt->flags & ISGONE))
            do
            {
                epos.y = rpt->pos.y + rnd(rpt->max.y - 2) + 1;
            } while ((rpt->flags & ISMAZE) && !(flags_at(epos.y, epos.x) & F_PASS));
        distance = abs(spos.x - epos.x) - 1;
        turn_delta.y = (spos.y < epos.y ? 1 : -1);
        turn_delta.x = 0;
        turn_distance = abs(spos.y - epos.y);
    }

    turn_spot = rnd(distance - 1) + 1;
    if (!(rpf->flags & ISGONE))
        door(rm, spos);
    else
        putpass(spos);
    if (!(rpt->flags & ISGONE))
        door(rmt, epos);
    else
        putpass(epos);

    curr = spos;
    while (distance > 0)
    {
        curr.x += del.x;
        curr.y += del.y;
        if (distance == turn_spot)
            while (turn_distance--)
            {
                putpass(curr);
                curr.x += turn_delta.x;
                curr.y += turn_delta.y;
            }
        putpass(curr);
        distance--;
    }
}

void door(int room_index, Coord cp)
{
    Room *rm = &rooms[room_index];
    Place *pp;
    rm->exits[rm->nexits++] = cp;
    if (rm->flags & ISMAZE)
        return;
    pp = &places[cp.y][cp.x];
    if (rnd(10) + 1 < level && rnd(5) == 0)
    {
        if (cp.y == rm->pos.y || cp.y == rm->pos.y + rm->max.y - 1)
            pp->ch = '-';
        else
            pp->ch = '|';
        pp->flags &= ~F_REAL;
    }
    else
        pp->ch = DOOR;
}

void passnum(void)
{
    pnum = 0;
    newpnum = 0;
    for (int i = 0; i < MAXPASS; i++)
        passages[i].nexits = 0;
    for (int r = 0; r < MAXROOMS; r++)
        for (int i = 0; i < rooms[r].nexits; i++)
        {
            newpnum++;
            numpass(rooms[r].exits[i].y, rooms[r].exits[i].x);
        }
}

void numpass(int y, int x)
{
    Place *pp;
    char ch;
    if (x >= NUMCOLS || x < 0 || y >= NUMLINES || y <= 0)
        return;
    pp = &places[y][x];
    if (pp->flags & F_PNUM)
        return;
    if (newpnum)
    {
        pnum++;
        newpnum = 0;
    }
    ch = pp->ch;
    if (ch == DOOR || (!(pp->flags & F_REAL) && (ch == '|' || ch == '-')))
        passages[pnum].exits[passages[pnum].nexits++] = (Coord){y, x};
    else if (!(pp->flags & F_PASS))
        return;
    pp->flags |= pnum;
    numpass(y + 1, x);
    numpass(y - 1, x);
    numpass(y, x + 1);
    numpass(y, x - 1);
}

void treas_room(void)
{
    int nm;
    int spots;
    int num_monst;
    int room_index = rnd_room();
    Room *rp = &rooms[room_index];

    spots = (rp->max.y - 2) * (rp->max.x - 2) - MINTREAS;
    if (spots > (MAXTREAS - MINTREAS))
        spots = MAXTREAS - MINTREAS;
    num_monst = nm = rnd(spots) + MINTREAS;
    while (nm--)
    {
        Coord mp = find_floor(room_index, 0, 2 * MAXTRIES, 0);
        SourceObject obj = new_thing();
        obj.pos = mp;
        attach_object(obj);
        set_ch(mp.y, mp.x, obj.type);
    }

    if ((nm = rnd(spots) + MINTREAS) < num_monst + 2)
        nm = num_monst + 2;
    spots = (rp->max.y - 2) * (rp->max.x - 2);
    if (nm > spots)
        nm = spots;
    level++;
    while (nm--)
    {
        Coord mp = {0, 0};
        if (try_find_floor(room_index, 0, MAXTRIES, 1, &mp))
        {
            SourceMonster monster;
            places[mp.y][mp.x].monst = 1;
            monster_slots[monster_count++] = mp;
            monster = new_monster(randmonster(), mp);
            monster.flags |= ISMEAN;
            give_pack(&monster);
            attach_monster(monster);
        }
    }
    level--;
}

void put_things(void)
{
    if (amulet && level < max_level)
        return;
    if (rnd(TREAS_ROOM) == 0)
        treas_room();
    for (int i = 0; i < MAXOBJ; i++)
        if (rnd(100) < 36)
        {
            SourceObject obj = new_thing();
            obj.pos = find_floor(0, 1, 0, 0);
            set_ch(obj.pos.y, obj.pos.x, obj.type);
            attach_object(obj);
        }
    if (level >= AMULETLEVEL && !amulet)
    {
        SourceObject obj = new_item_object();
        obj.hplus = 0;
        obj.dplus = 0;
        obj.arm = 11;
        obj.type = AMULET;
        obj.pos = find_floor(0, 1, 0, 0);
        set_ch(obj.pos.y, obj.pos.x, AMULET);
        attach_object(obj);
    }
}

void place_traps(void)
{
    if (rnd(10) >= level)
        return;
    ntraps = rnd(level / 4) + 1;
    if (ntraps > MAXTRAPS)
        ntraps = MAXTRAPS;
    for (int i = 0; i < ntraps; i++)
    {
        Coord spot;
        do
        {
            spot = find_floor(0, 1, 0, 0);
        } while (places[spot.y][spot.x].ch != FLOOR);
        places[spot.y][spot.x].flags &= ~F_REAL;
        int trap_kind = rnd(NTRAPS);
        places[spot.y][spot.x].flags |= trap_kind;
        traps_out[trap_count].pos = spot;
        traps_out[trap_count].kind = trap_kind;
        trap_count++;
    }
}

void new_level_slice(void)
{
    do_rooms();
    do_passages();
    no_food++;
    put_things();
    place_traps();
    stairs = find_floor(0, 1, 0, 0);
    set_ch(stairs.y, stairs.x, STAIRS);
    hero = find_floor(0, 1, 0, 1);
}

void print_coord(Coord cp)
{
    printf("{\"y\":%d,\"x\":%d}", cp.y, cp.x);
}

void print_object(SourceObject *obj)
{
    printf("{\"type\":\"%c\",\"which\":%d,\"pos\":", obj->type, obj->which);
    print_coord(obj->pos);
    printf(",\"count\":%d,\"hplus\":%d,\"dplus\":%d,\"arm\":%d,\"flags\":%d,\"group\":%d,\"goldval\":%d}", obj->count, obj->hplus, obj->dplus, obj->arm, obj->flags, obj->group, obj->goldval);
}

void print_monster(SourceMonster *monster)
{
    printf("{\"type\":\"%c\",\"pos\":", monster->type);
    print_coord(monster->pos);
    printf(",\"level\":%d,\"hp\":%d,\"disguise\":\"%c\",\"flags\":%d,\"pack\":[", monster->level, monster->hp, monster->disguise, monster->flags);
    for (int i = 0; i < monster->pack_count; i++)
    {
        if (i)
            printf(",");
        print_object(&monster->pack[i]);
    }
    printf("]}");
}

void print_trap(SourceTrap *trap)
{
    printf("{\"pos\":");
    print_coord(trap->pos);
    printf(",\"kind\":%d}", trap->kind);
}

void print_room(Room *rp)
{
    printf("{\"pos\":");
    print_coord(rp->pos);
    printf(",\"max\":");
    print_coord(rp->max);
    printf(",\"gold\":");
    print_coord(rp->gold);
    printf(",\"goldval\":%d,\"flags\":%d,\"nexits\":%d,\"exits\":[", rp->goldval, rp->flags, rp->nexits);
    for (int i = 0; i < rp->nexits; i++)
    {
        if (i)
            printf(",");
        print_coord(rp->exits[i]);
    }
    printf("]}");
}

void print_case(int initial_seed, int dungeon_level, int mode)
{
    init_state(initial_seed, dungeon_level);
    if (mode == 2)
        new_level_slice();
    else
    {
        do_rooms();
        if (mode == 1)
            do_passages();
    }
    printf("{\"seed\":%d,\"level\":%d,\"draft\":{", initial_seed, dungeon_level);
    printf("\"level\":%d,\"max_level\":%d,\"amulet\":false,", dungeon_level, dungeon_level);
    printf("\"rooms\":[");
    for (int i = 0; i < MAXROOMS; i++)
    {
        if (i)
            printf(",");
        print_room(&rooms[i]);
    }
    printf("],\"rows\":[");
    for (int y = 0; y < NUMLINES; y++)
    {
        if (y)
            printf(",");
        printf("\"");
        for (int x = 0; x < NUMCOLS; x++)
            putchar(places[y][x].ch);
        printf("\"");
    }
    printf("],\"gold_positions\":{");
    int first = 1;
    for (int y = 0; y < NUMLINES; y++)
        for (int x = 0; x < NUMCOLS; x++)
            if (places[y][x].ch == GOLD)
            {
                int value = 0;
                for (int i = 0; i < MAXROOMS; i++)
                    if (rooms[i].gold.y == y && rooms[i].gold.x == x)
                        value = rooms[i].goldval;
                if (!first)
                    printf(",");
                first = 0;
                printf("\"%d,%d\":%d", y, x, value);
            }
    printf("},\"monster_slots\":[");
    for (int i = 0; i < monster_count; i++)
    {
        if (i)
            printf(",");
        print_coord(monster_slots[i]);
    }
    printf("],\"monsters\":[");
    for (int i = 0; i < monsters_out_count; i++)
    {
        if (i)
            printf(",");
        print_monster(&monsters_out[i]);
    }
    printf("],\"level_objects\":[");
    for (int i = 0; i < level_object_count; i++)
    {
        if (i)
            printf(",");
        print_object(&level_objects[i]);
    }
    printf("],\"traps\":[");
    for (int i = 0; i < trap_count; i++)
    {
        if (i)
            printf(",");
        print_trap(&traps_out[i]);
    }
    printf("],\"stairs\":");
    print_coord(stairs);
    printf(",\"hero\":");
    print_coord(hero);
    printf(",\"ntraps\":%d,\"no_food\":%d,\"rng_seed\":%d", ntraps, no_food, seed);
    if (mode != 0)
    {
        printf(",\"passages\":[");
        for (int i = 0; i < MAXPASS; i++)
        {
            if (i)
                printf(",");
            print_room(&passages[i]);
        }
        printf("],\"hidden_passages\":[");
        int first_hidden = 1;
        for (int y = 0; y < NUMLINES; y++)
            for (int x = 0; x < NUMCOLS; x++)
                if ((places[y][x].flags & F_PASS) && places[y][x].ch != PASSAGE)
                {
                    if (!first_hidden)
                        printf(",");
                    first_hidden = 0;
                    print_coord((Coord){y, x});
                }
        printf("],\"passage_numbers\":{");
        int first_number = 1;
        for (int y = 0; y < NUMLINES; y++)
            for (int x = 0; x < NUMCOLS; x++)
                if (places[y][x].flags & F_PNUM)
                {
                    if (!first_number)
                        printf(",");
                    first_number = 0;
                    printf("\"%d,%d\":%d", y, x, places[y][x].flags & F_PNUM);
                }
        printf("}");
    }
    printf("}}");
}

int main(void)
{
    int seeds[8] = {1, 7, 12345, 12345, -17, 67, 24680, 31415};
    int levels[8] = {1, 1, 1, 6, 12, 6, 26, 30};
    printf("{\"rooms\":[");
    for (int i = 0; i < 8; i++)
    {
        if (i)
            printf(",");
        print_case(seeds[i], levels[i], 0);
    }
    printf("],\"passages\":[");
    for (int i = 0; i < 8; i++)
    {
        if (i)
            printf(",");
        print_case(seeds[i], levels[i], 1);
    }
    printf("],\"levels\":[");
    for (int i = 0; i < 8; i++)
    {
        if (i)
            printf(",");
        print_case(seeds[i], levels[i], 2);
    }
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return {
        "rooms": [
            {"seed": seed, "level": level, "draft": generate_room_slice(seed, level=level, max_level=level, amulet=False).to_dict()}
            for seed, level in CASES
        ],
        "passages": [
            {"seed": seed, "level": level, "draft": generate_passage_slice(seed, level=level, max_level=level, amulet=False).to_dict()}
            for seed, level in CASES
        ],
        "levels": [
            {"seed": seed, "level": level, "draft": generate_new_level_slice(seed, level=level, max_level=level, amulet=False).to_dict()}
            for seed, level in CASES
        ],
    }


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_rooms",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-rooms-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_rooms.c"
        binary = temp / "source_rooms"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_rooms.v2",
        "cases": [{"seed": seed, "level": level} for seed, level in CASES],
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source room generation mismatch")


if __name__ == "__main__":
    main()
