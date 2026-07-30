#!/usr/bin/env python3
"""Compare source-derived Rogue save-state bytes across C, Python, and Rust."""

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

from source_state import source_state_report


C_SOURCE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RSID_STATS 0xABCD0001u
#define RSID_THING 0xABCD0002u
#define RSID_OBJECT 0xABCD0003u
#define RSID_MAGICITEMS 0xABCD0004u
#define RSID_OBJECTLIST 0xABCD0007u
#define RSID_MONSTERLIST 0xABCD0009u
#define RSID_MONSTERS 0xABCD000Bu
#define RSID_WINDOW 0xABCD000Du
#define RSID_DAEMONS 0xABCD000Eu
#define RSID_ROOMS 0xABCD0017u
#define MAXROOMS 9

static const unsigned char source_encstr[] = {
    0300, 'k', '|', '|', '`', 0251, 'Y', '.', '\'', 0305, 0321, 0201, '+',
    0277, '~', 'r', '"', ']', 0240, '_', 0223, '=', '1', 0341, ')', 0222,
    0212, 0241, 't', ';', '\t', '$', 0270, 0314, '/', '<', '#', 0201, 0254
};
static const unsigned char source_statlist[] = {
    0355, 'k', 'l', '{', '+', 0204, 0255, 0313, 'i', 'd', 'J', 0361, 0214,
    '=', '4', ':', 0311, 0271, 0341, 'w', 'K', '<', 0312, 0321, 0213, ',',
    ',', '7', 0271, '/', 'R', 'k', '%', '\b', 0312, '\f', 0246
};

typedef struct writer {
    unsigned char data[16384];
    int len;
} Writer;

typedef struct coord {
    int y;
    int x;
} Coord;

typedef struct stats {
    unsigned int strength;
    int exp;
    int level;
    int armor;
    int hp;
    const char *damage;
    int max_hp;
} SourceStats;

typedef struct obj_info {
    const char *name;
    int prob;
    int worth;
    const char *guess;
    int know;
} SourceObjInfo;

typedef struct object {
    const char *object_id;
    char obj_type;
    Coord pos;
    int launch;
    char packch;
    const char *damage;
    const char *hurldmg;
    int count;
    int which;
    int hplus;
    int dplus;
    int arm;
    int flags;
    int group;
    const char *label;
} SourceObject;

typedef struct room {
    Coord pos;
    Coord max;
    Coord gold;
    int goldval;
    int flags;
    Coord exits[12];
    int nexits;
} SourceRoom;

typedef struct thing {
    const char *thing_id;
    Coord pos;
    int turn;
    char thing_type;
    char disguise;
    char oldch;
    const char *dest_kind;
    int dest_index;
    int flags;
    SourceStats stats;
    int room_index;
    SourceObject pack[3];
    int pack_count;
} SourceThing;

typedef struct place {
    char ch;
    int flags;
    int monster_index;
} SourcePlace;

typedef struct daemon {
    int d_type;
    int func;
    int arg;
    int time;
} SourceDaemon;

static void write_byte(Writer *w, unsigned char value)
{
    w->data[w->len++] = value;
}

static void write_int(Writer *w, int value)
{
    uint32_t raw = (uint32_t) value;
    write_byte(w, raw & 0xff);
    write_byte(w, (raw >> 8) & 0xff);
    write_byte(w, (raw >> 16) & 0xff);
    write_byte(w, (raw >> 24) & 0xff);
}

static void write_uint(Writer *w, unsigned int value)
{
    write_byte(w, value & 0xff);
    write_byte(w, (value >> 8) & 0xff);
    write_byte(w, (value >> 16) & 0xff);
    write_byte(w, (value >> 24) & 0xff);
}

static void write_short(Writer *w, int value)
{
    uint16_t raw = (uint16_t) value;
    write_byte(w, raw & 0xff);
    write_byte(w, (raw >> 8) & 0xff);
}

static void write_char(Writer *w, char value)
{
    write_byte(w, (unsigned char) value);
}

static void write_boolean(Writer *w, int value)
{
    write_byte(w, value ? 1 : 0);
}

static void write_booleans(Writer *w, int *values, int count)
{
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_boolean(w, values[i]);
}

static void write_ints(Writer *w, int *values, int count)
{
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_int(w, values[i]);
}

static void write_chars_raw(Writer *w, const unsigned char *value, int count)
{
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_byte(w, value[i]);
}

static void write_fixed_chars(Writer *w, const char *value, int count)
{
    unsigned char buf[2048];
    memset(buf, 0, sizeof(buf));
    if (value != NULL)
    {
        int len = (int) strlen(value);
        if (len > count)
            len = count;
        memcpy(buf, value, len);
    }
    write_chars_raw(w, buf, count);
}

static void write_string(Writer *w, const char *value)
{
    unsigned char buf[256];
    int len = 0;
    if (value != NULL)
    {
        len = (int) strlen(value) + 1;
        memcpy(buf, value, len - 1);
        buf[len - 1] = 0;
    }
    write_int(w, len);
    write_chars_raw(w, buf, len);
}

static void write_strings(Writer *w, const char **values, int count)
{
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_string(w, values[i]);
}

static void write_marker(Writer *w, unsigned int marker)
{
    write_uint(w, marker);
}

static void write_coord(Writer *w, Coord coord)
{
    write_int(w, coord.x);
    write_int(w, coord.y);
}

static void write_stats(Writer *w, SourceStats stats)
{
    write_marker(w, RSID_STATS);
    write_uint(w, stats.strength);
    write_int(w, stats.exp);
    write_int(w, stats.level);
    write_int(w, stats.armor);
    write_int(w, stats.hp);
    write_fixed_chars(w, stats.damage, 13);
    write_int(w, stats.max_hp);
}

static void write_monsters(Writer *w, SourceStats *stats, int count)
{
    write_marker(w, RSID_MONSTERS);
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_stats(w, stats[i]);
}

static void write_obj_info(Writer *w, SourceObjInfo *items, int count)
{
    write_marker(w, RSID_MAGICITEMS);
    write_int(w, count);
    for (int i = 0; i < count; i++)
    {
        write_int(w, items[i].prob);
        write_int(w, items[i].worth);
        write_string(w, items[i].guess);
        write_boolean(w, items[i].know);
    }
}

static void write_room(Writer *w, SourceRoom room)
{
    write_coord(w, room.pos);
    write_coord(w, room.max);
    write_coord(w, room.gold);
    write_int(w, room.goldval);
    write_short(w, room.flags);
    write_int(w, room.nexits);
    for (int i = 0; i < 12; i++)
        write_coord(w, room.exits[i]);
}

static void write_rooms(Writer *w, SourceRoom *rooms, int count)
{
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_room(w, rooms[i]);
}

static void write_room_reference(Writer *w, int room_index)
{
    write_int(w, room_index >= 0 && room_index < MAXROOMS ? room_index : -1);
}

static void write_object(Writer *w, SourceObject obj)
{
    write_marker(w, RSID_OBJECT);
    write_int(w, obj.obj_type);
    write_coord(w, obj.pos);
    write_int(w, obj.launch);
    write_char(w, obj.packch);
    write_fixed_chars(w, obj.damage, 8);
    write_fixed_chars(w, obj.hurldmg, 8);
    write_int(w, obj.count);
    write_int(w, obj.which);
    write_int(w, obj.hplus);
    write_int(w, obj.dplus);
    write_int(w, obj.arm);
    write_int(w, obj.flags);
    write_int(w, obj.group);
    write_string(w, obj.label);
}

static void write_object_list(Writer *w, SourceObject *objects, int count)
{
    write_marker(w, RSID_OBJECTLIST);
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_object(w, objects[i]);
}

static void write_object_reference(Writer *w, SourceObject *objects, int count, const char *item_id)
{
    int index = -1;
    if (item_id != NULL)
        for (int i = 0; i < count; i++)
            if (strcmp(objects[i].object_id, item_id) == 0)
            {
                index = i;
                break;
            }
    write_int(w, index);
}

static void dest_pair(SourceThing thing, int monster_count, int object_count, int *dest_list, int *dest_index)
{
    if (strcmp(thing.dest_kind, "hero") == 0)
    {
        *dest_list = 0;
        *dest_index = 1;
    }
    else if (strcmp(thing.dest_kind, "monster") == 0)
    {
        *dest_list = 1;
        *dest_index = thing.dest_index >= 0 && thing.dest_index < monster_count ? thing.dest_index : -1;
    }
    else if (strcmp(thing.dest_kind, "object") == 0)
    {
        *dest_list = 2;
        *dest_index = thing.dest_index >= 0 && thing.dest_index < object_count ? thing.dest_index : -1;
    }
    else if (strcmp(thing.dest_kind, "room_gold") == 0)
    {
        *dest_list = 3;
        *dest_index = thing.dest_index >= 0 && thing.dest_index < MAXROOMS ? thing.dest_index : -1;
    }
    else
    {
        *dest_list = 0;
        *dest_index = 0;
    }
}

static void write_thing(Writer *w, SourceThing *thing, SourceThing *monsters, int monster_count, SourceObject *objects, int object_count)
{
    int dest_list = 0;
    int dest_index = 0;
    write_marker(w, RSID_THING);
    if (thing == NULL)
    {
        write_int(w, 0);
        return;
    }
    write_int(w, 1);
    write_coord(w, thing->pos);
    write_boolean(w, thing->turn);
    write_char(w, thing->thing_type);
    write_char(w, thing->disguise);
    write_char(w, thing->oldch);
    dest_pair(*thing, monster_count, object_count, &dest_list, &dest_index);
    write_int(w, dest_list);
    write_int(w, dest_index);
    write_short(w, thing->flags);
    write_stats(w, thing->stats);
    write_room_reference(w, thing->room_index);
    write_object_list(w, thing->pack, thing->pack_count);
}

static void write_thing_list(Writer *w, SourceThing *things, int count, SourceObject *objects, int object_count)
{
    write_marker(w, RSID_MONSTERLIST);
    write_int(w, count);
    for (int i = 0; i < count; i++)
        write_thing(w, &things[i], things, count, objects, object_count);
}

static void write_thing_reference(Writer *w, int count, int index)
{
    write_int(w, index >= 0 && index < count ? index : -1);
}

static void write_places(Writer *w, SourcePlace *places, int count, int monster_count)
{
    for (int i = 0; i < count; i++)
    {
        write_char(w, places[i].ch);
        write_char(w, (char) (places[i].flags & 0xff));
        write_thing_reference(w, monster_count, places[i].monster_index);
    }
}

static void write_daemons(Writer *w, SourceDaemon *daemons, int daemon_count, int count)
{
    write_marker(w, RSID_DAEMONS);
    write_int(w, count);
    for (int i = 0; i < count; i++)
    {
        SourceDaemon daemon = {0, 0, 0, 0};
        if (i < daemon_count)
            daemon = daemons[i];
        write_int(w, daemon.d_type);
        write_int(w, daemon.func);
        write_int(w, daemon.arg);
        write_int(w, daemon.time);
    }
}

static void write_window(Writer *w, const char **rows, int height, int width)
{
    write_marker(w, RSID_WINDOW);
    write_int(w, height);
    write_int(w, width);
    for (int row = 0; row < height; row++)
        for (int col = 0; col < width; col++)
            write_int(w, rows[row][col]);
}

static void write_save_header_projection(Writer *w, const char *version, int lines, int cols)
{
    char geometry[80];
    int len = (int) strlen(version) + 1;
    for (int i = 0; i < len; i++)
        write_char(w, version[i]);
    memset(geometry, 0, sizeof(geometry));
    snprintf(geometry, sizeof(geometry), "%d x %d\n", lines, cols);
    for (int i = 0; i < 80; i++)
        write_char(w, geometry[i]);
}

static Writer source_encwrite_bytes(const unsigned char *data, int size)
{
    Writer w = {{0}, 0};
    int e1 = 0;
    int e2 = 0;
    unsigned char fb = 0;
    int enc_len = (int) sizeof(source_encstr);
    int stat_len = (int) sizeof(source_statlist);
    for (int i = 0; i < size; i++)
    {
        write_byte(&w, data[i] ^ source_encstr[e1] ^ source_statlist[e2] ^ fb);
        fb = (unsigned char) (fb + (unsigned char) (source_encstr[e1] * source_statlist[e2]));
        e1 = (e1 + 1) % enc_len;
        e2 = (e2 + 1) % stat_len;
    }
    return w;
}

static Writer source_save_file_envelope(Writer body, int lines, int cols)
{
    Writer w = {{0}, 0};
    Writer part;
    const char version[] = "rogue (rogueforge) 09/05/07";
    char geometry[80];
    part = source_encwrite_bytes((const unsigned char *) version, (int) sizeof(version));
    for (int i = 0; i < part.len; i++)
        write_byte(&w, part.data[i]);
    memset(geometry, 0, sizeof(geometry));
    snprintf(geometry, sizeof(geometry), "%d x %d\n", lines, cols);
    part = source_encwrite_bytes((const unsigned char *) geometry, 80);
    for (int i = 0; i < part.len; i++)
        write_byte(&w, part.data[i]);
    part = source_encwrite_bytes(body.data, body.len);
    for (int i = 0; i < part.len; i++)
        write_byte(&w, part.data[i]);
    return w;
}

static SourceStats source_monster_stats[26] = {
    {10, 20, 5, 2, 1, "0x0/0x0", 1},
    {10, 1, 1, 3, 1, "1x2", 1},
    {10, 17, 4, 4, 1, "1x2/1x5/1x5", 1},
    {10, 5000, 10, -1, 1, "1x8/1x8/3x10", 1},
    {10, 2, 1, 7, 1, "1x2", 1},
    {10, 80, 8, 3, 1, "%%%x0", 1},
    {10, 2000, 13, 2, 1, "4x3/3x5", 1},
    {10, 3, 1, 5, 1, "1x8", 1},
    {10, 5, 1, 9, 1, "0x0", 1},
    {10, 3000, 15, 6, 1, "2x12/2x4", 1},
    {10, 1, 1, 7, 1, "1x4", 1},
    {10, 10, 3, 8, 1, "1x1", 1},
    {10, 200, 8, 2, 1, "3x4/3x4/2x5", 1},
    {10, 37, 3, 9, 1, "0x0", 1},
    {10, 5, 1, 6, 1, "1x8", 1},
    {10, 120, 8, 3, 1, "4x4", 1},
    {10, 15, 3, 3, 1, "1x5/1x5", 1},
    {10, 9, 2, 3, 1, "1x6", 1},
    {10, 2, 1, 5, 1, "1x3", 1},
    {10, 120, 6, 4, 1, "1x8/1x8/2x6", 1},
    {10, 190, 7, -2, 1, "1x9/1x9/2x9", 1},
    {10, 350, 8, 1, 1, "1x10", 1},
    {10, 55, 5, 4, 1, "1x6", 1},
    {10, 100, 7, 7, 1, "4x4", 1},
    {10, 50, 4, 6, 1, "1x6/1x6", 1},
    {10, 6, 2, 8, 1, "1x8", 1},
};

static SourceObjInfo source_things_info[7] = {
    {NULL, 26, 0, NULL, 0},
    {NULL, 36, 0, NULL, 0},
    {NULL, 16, 0, NULL, 0},
    {NULL, 7, 0, NULL, 0},
    {NULL, 7, 0, NULL, 0},
    {NULL, 4, 0, NULL, 0},
    {NULL, 4, 0, NULL, 0},
};

static SourceObjInfo source_arm_info[8] = {
    {"leather armor", 20, 20, NULL, 0},
    {"ring mail", 15, 25, NULL, 0},
    {"studded leather armor", 15, 20, NULL, 0},
    {"scale mail", 13, 30, NULL, 0},
    {"chain mail", 12, 75, NULL, 0},
    {"splint mail", 10, 80, NULL, 0},
    {"banded mail", 10, 90, NULL, 0},
    {"plate mail", 5, 150, NULL, 0},
};

static SourceObjInfo source_pot_info[14] = {
    {"confusion", 7, 5, NULL, 1},
    {"hallucination", 8, 5, NULL, 0},
    {"poison", 8, 5, NULL, 0},
    {"gain strength", 13, 150, NULL, 0},
    {"see invisible", 3, 100, NULL, 0},
    {"healing", 13, 130, NULL, 0},
    {"monster detection", 6, 130, NULL, 0},
    {"magic detection", 6, 105, NULL, 0},
    {"raise level", 2, 250, NULL, 0},
    {"extra healing", 5, 200, NULL, 0},
    {"haste self", 5, 190, NULL, 0},
    {"restore strength", 13, 130, NULL, 0},
    {"blindness", 5, 5, NULL, 0},
    {"levitation", 6, 75, NULL, 0},
};

static SourceObjInfo source_ring_info[14] = {
    {"protection", 9, 400, NULL, 0},
    {"add strength", 9, 400, NULL, 1},
    {"sustain strength", 5, 280, NULL, 0},
    {"searching", 10, 420, NULL, 0},
    {"see invisible", 10, 310, NULL, 0},
    {"adornment", 1, 10, NULL, 0},
    {"aggravate monster", 10, 10, NULL, 0},
    {"dexterity", 8, 440, NULL, 0},
    {"increase damage", 8, 400, NULL, 0},
    {"regeneration", 4, 460, NULL, 0},
    {"slow digestion", 9, 240, NULL, 0},
    {"teleportation", 5, 30, NULL, 0},
    {"stealth", 7, 470, NULL, 0},
    {"maintain armor", 5, 380, NULL, 0},
};

static SourceObjInfo source_scr_info[18] = {
    {"monster confusion", 7, 140, NULL, 0},
    {"magic mapping", 4, 150, NULL, 1},
    {"hold monster", 2, 180, NULL, 0},
    {"sleep", 3, 5, NULL, 0},
    {"enchant armor", 7, 160, NULL, 0},
    {"identify potion", 10, 80, NULL, 0},
    {"identify scroll", 10, 80, NULL, 0},
    {"identify weapon", 6, 80, NULL, 0},
    {"identify armor", 7, 100, NULL, 0},
    {"identify ring, wand or staff", 10, 115, NULL, 0},
    {"scare monster", 3, 200, NULL, 0},
    {"food detection", 2, 60, NULL, 0},
    {"teleportation", 5, 165, NULL, 0},
    {"enchant weapon", 8, 150, NULL, 0},
    {"create monster", 4, 75, NULL, 0},
    {"remove curse", 7, 105, NULL, 0},
    {"aggravate monsters", 3, 20, NULL, 0},
    {"protect armor", 2, 250, NULL, 0},
};

static SourceObjInfo source_weap_info[10] = {
    {"mace", 11, 8, NULL, 0},
    {"long sword", 11, 15, NULL, 0},
    {"short bow", 12, 15, NULL, 0},
    {"arrow", 12, 1, NULL, 0},
    {"dagger", 8, 3, NULL, 0},
    {"two handed sword", 10, 75, NULL, 0},
    {"dart", 12, 2, NULL, 0},
    {"shuriken", 12, 5, NULL, 0},
    {"spear", 12, 5, NULL, 0},
    {NULL, 0, 0, NULL, 0},
};

static SourceObjInfo source_ws_info[14] = {
    {"light", 12, 250, NULL, 1},
    {"invisibility", 6, 5, NULL, 0},
    {"lightning", 3, 330, NULL, 0},
    {"fire", 3, 330, NULL, 0},
    {"cold", 3, 330, NULL, 0},
    {"polymorph", 15, 310, NULL, 0},
    {"magic missile", 10, 170, NULL, 0},
    {"haste monster", 10, 5, NULL, 0},
    {"slow monster", 11, 350, NULL, 0},
    {"drain life", 9, 300, NULL, 0},
    {"nothing", 1, 5, NULL, 0},
    {"teleport away", 6, 340, NULL, 0},
    {"teleport to", 6, 50, NULL, 0},
    {"cancellation", 5, 280, NULL, 0},
};

static void init_objects(SourceObject objects[2])
{
    objects[0] = (SourceObject) {"weapon", ')', {4, 5}, 2, 'a', "1d8", "1d6", 1, 1, 2, -1, 0, 0000006, 3, "etched"};
    objects[1] = (SourceObject) {"food", ':', {8, 9}, -1, 'b', "", "", 2, 0, 0, 0, 0, 0, 0, NULL};
}

static SourceThing make_player(SourceObject objects[2])
{
    SourceThing player;
    memset(&player, 0, sizeof(player));
    player.thing_id = "player";
    player.pos = (Coord) {10, 11};
    player.turn = 0;
    player.thing_type = '@';
    player.disguise = '@';
    player.oldch = '.';
    player.dest_kind = "null";
    player.dest_index = 0;
    player.flags = 0020000;
    player.stats = (SourceStats) {0x1010, 220, 5, 3, 31, "1d4", 36};
    player.room_index = 0;
    player.pack[0] = objects[0];
    player.pack[1] = objects[1];
    player.pack_count = 2;
    return player;
}

static void init_monsters(SourceThing monsters[3], SourceObject objects[2])
{
    memset(monsters, 0, sizeof(SourceThing) * 3);
    monsters[0].thing_id = "kestrel";
    monsters[0].pos = (Coord) {3, 30};
    monsters[0].turn = 1;
    monsters[0].thing_type = 'K';
    monsters[0].disguise = 'K';
    monsters[0].oldch = '.';
    monsters[0].dest_kind = "hero";
    monsters[0].dest_index = 1;
    monsters[0].flags = 0020040;
    monsters[0].stats = (SourceStats) {0x0909, 12, 1, 8, 4, "1d4", 4};
    monsters[0].room_index = 1;

    monsters[1].thing_id = "nymph";
    monsters[1].pos = (Coord) {7, 35};
    monsters[1].turn = 0;
    monsters[1].thing_type = 'N';
    monsters[1].disguise = 'N';
    monsters[1].oldch = '.';
    monsters[1].dest_kind = "object";
    monsters[1].dest_index = 0;
    monsters[1].flags = 0020000;
    monsters[1].stats = (SourceStats) {0x0808, 50, 3, 9, 12, "0d0", 12};
    monsters[1].room_index = 1;
    monsters[1].pack[0] = objects[1];
    monsters[1].pack_count = 1;

    monsters[2].thing_id = "dragon";
    monsters[2].pos = (Coord) {11, 40};
    monsters[2].turn = 0;
    monsters[2].thing_type = 'D';
    monsters[2].disguise = 'D';
    monsters[2].oldch = '.';
    monsters[2].dest_kind = "monster";
    monsters[2].dest_index = 0;
    monsters[2].flags = 0020000;
    monsters[2].stats = (SourceStats) {0x1515, 5000, 10, -1, 80, "1d8/1d8/3d10", 80};
    monsters[2].room_index = 2;
}

static void init_rooms(SourceRoom rooms[2])
{
    memset(rooms, 0, sizeof(SourceRoom) * 2);
    rooms[0].pos = (Coord) {2, 4};
    rooms[0].max = (Coord) {6, 10};
    rooms[0].gold = (Coord) {5, 9};
    rooms[0].goldval = 73;
    rooms[0].flags = 0000005;
    rooms[0].exits[0] = (Coord) {2, 7};
    rooms[0].exits[1] = (Coord) {6, 8};
    rooms[0].nexits = 2;
    rooms[1].pos = (Coord) {12, 20};
    rooms[1].max = (Coord) {4, 8};
    rooms[1].gold = (Coord) {0, 0};
    rooms[1].goldval = 0;
    rooms[1].flags = 0;
    rooms[1].nexits = 0;
}

static void init_passages(SourceRoom passages[2])
{
    memset(passages, 0, sizeof(SourceRoom) * 2);
    passages[0].flags = 0000003;
    passages[0].exits[0] = (Coord) {3, 8};
    passages[0].exits[1] = (Coord) {8, 3};
    passages[0].exits[2] = (Coord) {8, 9};
    passages[0].nexits = 3;
    passages[1].flags = 0000003;
    passages[1].nexits = 0;
}

static Writer primitive_block(void)
{
    Writer w = {{0}, 0};
    const unsigned char abc[] = {'a', 'b', 'c'};
    write_int(&w, 0x12345678);
    write_int(&w, -2);
    write_uint(&w, 0x89ABCDEFu);
    write_short(&w, -1234);
    write_boolean(&w, 1);
    write_boolean(&w, 0);
    write_char(&w, 'A');
    write_chars_raw(&w, abc, 3);
    write_string(&w, "hello");
    write_string(&w, NULL);
    write_coord(&w, (Coord) {7, 3});
    return w;
}

static Writer stats_and_rooms(void)
{
    Writer w = {{0}, 0};
    SourceRoom rooms[2];
    init_rooms(rooms);
    write_stats(&w, (SourceStats) {0x1234, 55, 4, -2, 17, "1d8/1d3", 25});
    write_marker(&w, RSID_ROOMS);
    write_rooms(&w, rooms, 2);
    write_room_reference(&w, 1);
    write_room_reference(&w, 12);
    return w;
}

static Writer object_list_and_refs(void)
{
    Writer w = {{0}, 0};
    SourceObject objects[2];
    init_objects(objects);
    write_object_list(&w, objects, 2);
    write_object_reference(&w, objects, 2, "weapon");
    write_object_reference(&w, objects, 2, "missing");
    return w;
}

static Writer thing_list_and_places(void)
{
    Writer w = {{0}, 0};
    SourceObject objects[2];
    SourceThing monsters[3];
    SourceThing player;
    SourcePlace places[3] = {{'.', 0x10, -1}, {'A', 0x50, 0}, {'B', 0x40, 1}};
    init_objects(objects);
    player = make_player(objects);
    init_monsters(monsters, objects);
    write_thing(&w, &player, monsters, 3, objects, 2);
    write_object_reference(&w, player.pack, player.pack_count, "food");
    write_thing_list(&w, monsters, 3, objects, 2);
    write_places(&w, places, 3, 3);
    return w;
}

static Writer daemons_and_save_header_projection(void)
{
    Writer w = {{0}, 0};
    SourceDaemon daemons[2] = {{1, 2, 0, 30}, {2, 5, 7, 80}};
    write_daemons(&w, daemons, 2, 4);
    write_save_header_projection(&w, "rogue-5.4.4", 24, 80);
    return w;
}

static Writer save_file_prefix_block(void)
{
    Writer w = {{0}, 0};
    int pack_used[26];
    for (int i = 0; i < 26; i++)
        pack_used[i] = i == 0 || i == 2 || i == 25;
    write_boolean(&w, 1);   /* after */
    write_boolean(&w, 0);   /* again */
    write_int(&w, 7);       /* noscore */
    write_boolean(&w, 1);   /* seenstairs */
    write_boolean(&w, 1);   /* amulet */
    write_boolean(&w, 0);   /* door_stop */
    write_boolean(&w, 1);   /* fight_flush */
    write_boolean(&w, 0);   /* firstmove */
    write_boolean(&w, 0);   /* got_ltc */
    write_boolean(&w, 1);   /* has_hit */
    write_boolean(&w, 0);   /* in_shell */
    write_boolean(&w, 1);   /* inv_describe */
    write_boolean(&w, 1);   /* jump */
    write_boolean(&w, 1);   /* kamikaze */
    write_boolean(&w, 0);   /* lower_msg */
    write_boolean(&w, 1);   /* move_on */
    write_boolean(&w, 0);   /* msg_esc */
    write_boolean(&w, 1);   /* passgo */
    write_boolean(&w, 1);   /* playing */
    write_boolean(&w, 0);   /* q_comm */
    write_boolean(&w, 1);   /* running */
    write_boolean(&w, 1);   /* save_msg */
    write_boolean(&w, 1);   /* see_floor */
    write_boolean(&w, 0);   /* stat_msg */
    write_boolean(&w, 1);   /* terse */
    write_boolean(&w, 1);   /* to_death */
    write_boolean(&w, 1);   /* tombstone */
    write_int(&w, 0);       /* wizard is zero in non-MASTER builds */
    write_booleans(&w, pack_used, 26);
    return w;
}

static Writer save_file_identity_text_block(void)
{
    Writer w = {{0}, 0};
    const char *inv_t_name[3] = {"Overwrite", "Slow", "Clear"};
    const char *tr_name[8] = {
        "a trapdoor",
        "an arrow trap",
        "a sleeping gas trap",
        "a beartrap",
        "a teleport trap",
        "a poison dart trap",
        "a rust trap",
        "a mysterious trap"
    };
    write_char(&w, 'h');
    write_fixed_chars(&w, "save.dat", 1024);
    write_fixed_chars(&w, "last message", 1024);
    for (int i = 0; i < 14; i++)
        write_int(&w, i);
    write_fixed_chars(&w, "scratch", 2048);
    for (int i = 13; i >= 0; i--)
        write_int(&w, i);
    write_string(&w, "5.4.4");
    write_char(&w, 'l');
    for (int i = 0; i < 18; i++)
    {
        char scroll_name[32];
        snprintf(scroll_name, sizeof(scroll_name), "scroll %d", i);
        write_string(&w, scroll_name);
    }
    write_char(&w, '!');
    write_fixed_chars(&w, "player", 1024);
    for (int i = 0; i < 14; i++)
    {
        write_int(&w, i % 2 == 0 ? 0 : 1);
        write_int(&w, i);
    }
    write_int(&w, 26);
    write_fixed_chars(&w, "slime-mold", 1024);
    write_fixed_chars(&w, "/tmp/rogue", 1024);
    write_strings(&w, inv_t_name, 3);
    write_char(&w, 's');
    write_char(&w, 'h');
    write_char(&w, 'f');
    write_char(&w, 'l');
    write_strings(&w, tr_name, 8);
    return w;
}

static Writer save_file_scalar_block(void)
{
    Writer w = {{0}, 0};
    int a_class[8] = {8, 7, 7, 6, 5, 4, 4, 3};
    int e_levels[21] = {
        10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000,
        50000, 100000, 200000, 400000, 800000, 2000000, 4000000, 8000000, 0
    };
    write_int(&w, 3);       /* n_objs */
    write_int(&w, 5);       /* ntraps */
    write_int(&w, 2);       /* hungry_state */
    write_int(&w, 7);       /* inpack */
    write_int(&w, 1);       /* inv_type */
    write_int(&w, 9);       /* level */
    write_int(&w, 11);      /* max_level */
    write_int(&w, 13);      /* mpos */
    write_int(&w, 17);      /* no_food */
    write_ints(&w, a_class, 8);
    write_int(&w, 19);      /* count */
    write_int(&w, 1200);    /* food_left */
    write_int(&w, -1);      /* lastscore */
    write_int(&w, 4);       /* no_command */
    write_int(&w, 6);       /* no_move */
    write_int(&w, 777);     /* purse */
    write_int(&w, 8);       /* quiet */
    write_int(&w, 10);      /* vf_hit */
    write_int(&w, 12);      /* dnum */
    write_int(&w, 12345);   /* seed */
    write_ints(&w, e_levels, 21);
    write_coord(&w, (Coord) {-1, 1});
    write_coord(&w, (Coord) {2, 3});
    write_coord(&w, (Coord) {4, 5});
    return w;
}

static Writer save_file_player_refs_block(void)
{
    Writer w = {{0}, 0};
    SourceObject objects[2];
    SourceThing player;
    init_objects(objects);
    player = make_player(objects);
    write_thing(&w, &player, NULL, 0, objects, 2);
    write_object_reference(&w, player.pack, player.pack_count, "food");
    write_object_reference(&w, player.pack, player.pack_count, "weapon");
    write_object_reference(&w, player.pack, player.pack_count, NULL);
    write_object_reference(&w, player.pack, player.pack_count, "weapon");
    write_object_reference(&w, player.pack, player.pack_count, "food");
    write_object_reference(&w, player.pack, player.pack_count, "missing");
    return w;
}

static Writer save_file_level_state_block(void)
{
    Writer w = {{0}, 0};
    SourceObject objects[2];
    SourceThing monsters[3];
    SourcePlace places[3] = {{'.', 0x10, -1}, {'A', 0x50, 0}, {'B', 0x40, 1}};
    init_objects(objects);
    init_monsters(monsters, objects);
    write_object_list(&w, objects, 2);
    write_thing_list(&w, monsters, 3, objects, 2);
    write_places(&w, places, 3, 3);
    return w;
}

static Writer save_file_room_state_block(void)
{
    Writer w = {{0}, 0};
    SourceRoom rooms[2];
    SourceRoom passages[2];
    init_rooms(rooms);
    init_passages(passages);
    write_stats(&w, (SourceStats) {0x1010, 220, 5, 3, 36, "1d4", 40});
    write_rooms(&w, rooms, 2);
    write_room_reference(&w, 1);
    write_rooms(&w, passages, 2);
    return w;
}

static Writer save_file_info_state_block(void)
{
    Writer w = {{0}, 0};
    write_monsters(&w, source_monster_stats, 26);
    write_obj_info(&w, source_things_info, 7);
    write_obj_info(&w, source_arm_info, 8);
    write_obj_info(&w, source_pot_info, 14);
    write_obj_info(&w, source_ring_info, 14);
    write_obj_info(&w, source_scr_info, 18);
    write_obj_info(&w, source_weap_info, 10);
    write_obj_info(&w, source_ws_info, 14);
    return w;
}

static Writer save_file_tail_state_block(void)
{
    Writer w = {{0}, 0};
    SourceDaemon daemons[2] = {
        {2, 2, 0, -1},
        {1, 9, 0, 5},
    };
    const char *rows[2] = {"@.%", "  #"};
    write_daemons(&w, daemons, 2, 20);
    write_int(&w, 0);
    write_int(&w, 3);
    write_coord(&w, (Coord) {4, 5});
    write_int(&w, 7);
    write_window(&w, rows, 2, 3);
    return w;
}

static Writer encwrite_known_bytes(void)
{
    const unsigned char data[] = {'a', 'b', 'c', 'd', 'e', 'f', '\0'};
    return source_encwrite_bytes(data, (int) sizeof(data));
}

static Writer save_file_envelope_projection(void)
{
    return source_save_file_envelope(primitive_block(), 24, 80);
}

static void print_string(const char *value)
{
    putchar('"');
    for (const char *p = value; *p; p++)
    {
        if (*p == '"' || *p == '\\')
            putchar('\\');
        putchar(*p);
    }
    putchar('"');
}

static void print_hex(Writer *w)
{
    static const char *digits = "0123456789abcdef";
    putchar('"');
    for (int i = 0; i < w->len; i++)
    {
        putchar(digits[w->data[i] >> 4]);
        putchar(digits[w->data[i] & 0x0f]);
    }
    putchar('"');
}

static void print_case(const char *name, Writer w)
{
    printf("{\"name\":");
    print_string(name);
    printf(",\"len\":%d,\"hex\":", w.len);
    print_hex(&w);
    printf("}");
}

int main(void)
{
    printf("{\"schema\":\"gamebench.rogue.source_state.v1\",\"cases\":[");
    print_case("primitive_block", primitive_block());
    printf(",");
    print_case("stats_and_rooms", stats_and_rooms());
    printf(",");
    print_case("object_list_and_refs", object_list_and_refs());
    printf(",");
    print_case("thing_list_and_places", thing_list_and_places());
    printf(",");
    print_case("daemons_and_save_header_projection", daemons_and_save_header_projection());
    printf(",");
    print_case("save_file_prefix_block", save_file_prefix_block());
    printf(",");
    print_case("save_file_identity_text_block", save_file_identity_text_block());
    printf(",");
    print_case("save_file_scalar_block", save_file_scalar_block());
    printf(",");
    print_case("save_file_player_refs_block", save_file_player_refs_block());
    printf(",");
    print_case("save_file_level_state_block", save_file_level_state_block());
    printf(",");
    print_case("save_file_room_state_block", save_file_room_state_block());
    printf(",");
    print_case("save_file_info_state_block", save_file_info_state_block());
    printf(",");
    print_case("save_file_tail_state_block", save_file_tail_state_block());
    printf(",");
    print_case("encwrite_known_bytes", encwrite_known_bytes());
    printf(",");
    print_case("save_file_envelope_projection", save_file_envelope_projection());
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_state_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_state",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-state-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_state.c"
        binary = temp / "source_state"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_state.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [{"name": case["name"], "len": case["len"]} for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source state mismatch")


if __name__ == "__main__":
    main()
