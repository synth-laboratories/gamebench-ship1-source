#!/usr/bin/env python3
"""Compare source-derived Rogue player fight branches across C, Python, and Rust."""

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

from source_fight import source_fight_report


TRACE_KEYS = [
    "xeroc_hallu",
    "roll_hit",
    "roll_rng",
    "leprechaun_gold_saved",
    "magic_save_roll",
    "target_removed",
    "level_add",
]


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GOLD '*'
#define WEAPON ')'
#define CANHUH 0000001
#define ISBLIND 0000004
#define ISMISL 0000004
#define ISTARGET 0000200
#define ISHELD 0000400
#define ISHUH 0001000
#define ISHALU 0004000
#define ISRUN 0020000
#define NO_WEAPON -1
#define BOW 2
#define ARROW 3
#define VS_MAGIC 3

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

typedef struct weapon {
    char obj_type;
    int which;
    int hplus;
    int dplus;
    char damage[32];
    char hurl_damage[32];
    int launch;
    int flags;
    char name[32];
} Weapon;

typedef struct object {
    char obj_type;
    char name[32];
    int goldval;
} Object;

typedef struct monster {
    char type;
    Stats stats;
    int flags;
    char disguise;
    int has_disguise;
    Object pack[8];
    int pack_count;
    char oldch;
} Monster;

typedef struct world {
    int seed;
    Stats player;
    int player_flags;
    Weapon current_weapon;
    int has_current_weapon;
    int count;
    int quiet;
    int terse;
    int to_death;
    int has_hit;
    int fight_flush;
    int level;
    int max_level;
    int max_hp;
    int vf_hit;
    int fallpos_ok;
    int monster_present;
    char markers[32][48];
    int marker_count;
    Object dropped[8];
    int dropped_count;
    int has_xeroc_hallu;
    char xeroc_hallu;
    int has_roll_hit;
    int roll_hit;
    int has_roll_rng;
    int roll_rng;
    int has_leprechaun_gold_saved;
    int leprechaun_gold_saved;
    int has_magic_save_roll;
    int magic_save_roll;
    int has_target_removed;
    int has_level_add;
    int level_add;
} World;

typedef struct test_case {
    char name[64];
    int seed;
    char type;
    Stats monster_stats;
    int monster_flags;
    char disguise;
    int has_disguise;
    Object monster_pack[8];
    int monster_pack_count;
    char oldch;
    Stats player_stats;
    int player_flags;
    Weapon current_weapon;
    int has_current_weapon;
    Weapon weapon;
    int has_weapon;
    int thrown;
    int count;
    int quiet;
    int terse;
    int to_death;
    int has_hit;
    int fight_flush;
    int level;
    int max_level;
    int max_hp;
    int vf_hit;
    int fallpos_ok;
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

Weapon weapon_make(char obj_type, int which, int hplus, int dplus, const char *damage, const char *hurl_damage, int launch, int flags, const char *name)
{
    Weapon weapon;
    weapon.obj_type = obj_type;
    weapon.which = which;
    weapon.hplus = hplus;
    weapon.dplus = dplus;
    strncpy(weapon.damage, damage, sizeof(weapon.damage) - 1);
    weapon.damage[sizeof(weapon.damage) - 1] = '\0';
    strncpy(weapon.hurl_damage, hurl_damage, sizeof(weapon.hurl_damage) - 1);
    weapon.hurl_damage[sizeof(weapon.hurl_damage) - 1] = '\0';
    weapon.launch = launch;
    weapon.flags = flags;
    strncpy(weapon.name, name, sizeof(weapon.name) - 1);
    weapon.name[sizeof(weapon.name) - 1] = '\0';
    return weapon;
}

Object object_make(char obj_type, const char *name, int goldval)
{
    Object obj;
    obj.obj_type = obj_type;
    strncpy(obj.name, name, sizeof(obj.name) - 1);
    obj.name[sizeof(obj.name) - 1] = '\0';
    obj.goldval = goldval;
    return obj;
}

void marker(World *world, const char *value)
{
    strncpy(world->markers[world->marker_count], value, sizeof(world->markers[world->marker_count]) - 1);
    world->markers[world->marker_count][sizeof(world->markers[world->marker_count]) - 1] = '\0';
    world->marker_count++;
}

int roll_em(World *world, Stats *attacker, Stats *defender, Weapon *weapon, int hurl)
{
    char damage_expression[64];
    char *cp;
    int hplus = 0;
    int dplus = 0;
    int did_hit = 0;
    if (weapon == NULL)
        strncpy(damage_expression, attacker->damage, sizeof(damage_expression) - 1);
    else
    {
        hplus = weapon->hplus;
        dplus = weapon->dplus;
        strncpy(damage_expression, weapon->damage, sizeof(damage_expression) - 1);
        if (hurl)
        {
            if ((weapon->flags & ISMISL) && world->has_current_weapon && world->current_weapon.which == weapon->launch)
            {
                strncpy(damage_expression, weapon->hurl_damage, sizeof(damage_expression) - 1);
                hplus += world->current_weapon.hplus;
                dplus += world->current_weapon.dplus;
            }
            else if (weapon->launch < 0)
                strncpy(damage_expression, weapon->hurl_damage, sizeof(damage_expression) - 1);
        }
    }
    damage_expression[sizeof(damage_expression) - 1] = '\0';
    if (!(defender->flags & ISRUN))
        hplus += 4;
    cp = damage_expression;
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
        need = (20 - attacker->level) - defender->arm;
        if (swing_roll + hplus + str_plus[attacker->strength] >= need)
        {
            int damage_roll = roll(world, ndice, nsides);
            int damage = dplus + damage_roll + add_dam[attacker->strength];
            defender->hp -= damage > 0 ? damage : 0;
            did_hit = 1;
        }
        slash = strchr(cp, '/');
        if (slash == NULL)
            break;
        cp = slash + 1;
    }
    return did_hit;
}

int save_magic(World *world)
{
    int need = 14 + VS_MAGIC - world->player.level / 2;
    int save_roll = roll(world, 1, 20);
    world->has_magic_save_roll = 1;
    world->magic_save_roll = save_roll;
    return save_roll >= need;
}

void check_level(World *world)
{
    int next_level = 1;
    int old_level;
    for (int i = 0; e_levels[i] != 0; i++)
    {
        if (e_levels[i] > world->player.exp)
            break;
        next_level++;
    }
    old_level = world->player.level;
    world->player.level = next_level;
    if (next_level > old_level)
    {
        int add = roll(world, next_level - old_level, 10);
        world->max_hp += add;
        world->player.hp += add;
        char value[32];
        snprintf(value, sizeof(value), "welcome:%d", next_level);
        marker(world, value);
        world->has_level_add = 1;
        world->level_add = add;
    }
}

void remove_mon(World *world, Monster *monster, int waskill)
{
    for (int i = 0; i < monster->pack_count; i++)
    {
        char value[64];
        if (waskill)
        {
            snprintf(value, sizeof(value), "fall:%s", monster->pack[i].name);
            marker(world, value);
            world->dropped[world->dropped_count++] = monster->pack[i];
        }
        else
        {
            snprintf(value, sizeof(value), "discard:%s", monster->pack[i].name);
            marker(world, value);
        }
    }
    monster->pack_count = 0;
    world->monster_present = 0;
    char mv[32];
    snprintf(mv, sizeof(mv), "mvaddch:%c", monster->oldch);
    marker(world, mv);
    marker(world, "detach_monster");
    if (monster->flags & ISTARGET)
    {
        world->has_target_removed = 1;
        world->to_death = 0;
        if (world->fight_flush)
            marker(world, "flush_type");
    }
    marker(world, "discard_monster");
}

void killed(World *world, Monster *monster, int pr)
{
    world->player.exp += monster->stats.exp;
    if (monster->type == 'F')
    {
        world->player_flags &= ~ISHELD;
        world->vf_hit = 0;
        strncpy(monster->stats.damage, "000x0", sizeof(monster->stats.damage) - 1);
        monster->stats.damage[sizeof(monster->stats.damage) - 1] = '\0';
    }
    if (monster->type == 'L' && world->fallpos_ok && world->level >= world->max_level)
    {
        int goldval = gold_calc(world);
        int saved = save_magic(world);
        world->has_leprechaun_gold_saved = 1;
        world->leprechaun_gold_saved = saved;
        if (saved)
            for (int i = 0; i < 4; i++)
                goldval += gold_calc(world);
        for (int i = monster->pack_count; i > 0; i--)
            monster->pack[i] = monster->pack[i - 1];
        monster->pack[0] = object_make(GOLD, "gold", goldval);
        monster->pack_count++;
    }
    remove_mon(world, monster, 1);
    if (pr)
    {
        if (world->has_hit)
        {
            marker(world, "defeated_join");
            world->has_hit = 0;
        }
        else
            marker(world, "defeated");
    }
    check_level(world);
    if (world->fight_flush)
        marker(world, "flush_type");
}

int fight(World *world, Monster *monster, Weapon *weapon, int thrown)
{
    int did_hit;
    world->count = 0;
    world->quiet = 0;
    marker(world, "runto");
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
        if (!thrown)
            return 0;
    }
    world->has_hit = world->terse && !world->to_death;
    did_hit = roll_em(world, &world->player, &monster->stats, weapon, thrown);
    world->has_roll_hit = 1;
    world->roll_hit = did_hit;
    world->has_roll_rng = 1;
    world->roll_rng = world->seed;
    if (did_hit)
    {
        if (thrown)
            marker(world, "thunk");
        else
            marker(world, "hit");
        int did_confuse = 0;
        if (world->player_flags & CANHUH)
        {
            did_confuse = 1;
            monster->flags |= ISHUH;
            world->player_flags &= ~CANHUH;
            marker(world, "endmsg");
            marker(world, "hands_stop_glowing");
            world->has_hit = 0;
        }
        if (monster->stats.hp <= 0)
            killed(world, monster, 1);
        else if (did_confuse && !(world->player_flags & ISBLIND))
            marker(world, "appears_confused");
        return 1;
    }
    if (thrown)
        marker(world, "bounce");
    else
        marker(world, "miss");
    return 0;
}

TestCase base_case(const char *name, int seed, char type)
{
    TestCase c;
    memset(&c, 0, sizeof(c));
    strncpy(c.name, name, sizeof(c.name) - 1);
    c.seed = seed;
    c.type = type;
    c.monster_stats = stats_make(16, 0, 5, 6, 30, "1x1", 30, ISRUN);
    c.monster_flags = ISRUN;
    c.disguise = type;
    c.has_disguise = 1;
    c.oldch = '.';
    c.player_stats = stats_make(16, 0, 5, 6, 30, "1x1", 30, ISRUN);
    c.player_flags = ISRUN;
    c.count = 4;
    c.quiet = 7;
    c.fight_flush = 1;
    c.level = 1;
    c.max_level = 1;
    c.max_hp = 30;
    return c;
}

void world_init(World *world, TestCase *c)
{
    memset(world, 0, sizeof(*world));
    world->seed = c->seed;
    world->player = c->player_stats;
    world->player_flags = c->player_flags;
    world->current_weapon = c->current_weapon;
    world->has_current_weapon = c->has_current_weapon;
    world->count = c->count;
    world->quiet = c->quiet;
    world->terse = c->terse;
    world->to_death = c->to_death;
    world->has_hit = c->has_hit;
    world->fight_flush = c->fight_flush;
    world->level = c->level;
    world->max_level = c->max_level;
    world->max_hp = c->max_hp;
    world->vf_hit = c->vf_hit;
    world->fallpos_ok = c->fallpos_ok;
    world->monster_present = 1;
}

void print_bool(int value) { printf(value ? "true" : "false"); }
void print_stats(Stats *st)
{
    printf("{\"strength\":%d,\"exp\":%d,\"level\":%d,\"arm\":%d,\"hp\":%d,\"damage\":\"%s\",\"max_hp\":%d,\"flags\":%d}",
        st->strength, st->exp, st->level, st->arm, st->hp, st->damage, st->max_hp, st->flags);
}
void print_object(Object *obj)
{
    printf("{\"type\":\"%c\",\"name\":\"%s\",\"goldval\":%d}", obj->obj_type, obj->name, obj->goldval);
}
void print_trace_bool(int present, int value)
{
    if (present) print_bool(value); else printf("null");
}
void print_trace_int(int present, int value)
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
    for (int i = 0; i < c->monster_pack_count; i++)
        monster.pack[monster.pack_count++] = c->monster_pack[i];
    monster.oldch = c->oldch;
    returned = fight(&world, &monster, c->has_weapon ? &c->weapon : NULL, c->thrown);
    printf("{\"name\":\"%s\",\"seed\":%d,\"returned\":", c->name, c->seed);
    print_bool(returned);
    printf(",\"monster\":{\"type\":\"%c\",\"stats\":", monster.type);
    print_stats(&monster.stats);
    printf(",\"flags\":%d,\"disguise\":", monster.flags);
    if (monster.has_disguise) printf("\"%c\"", monster.disguise); else printf("null");
    printf(",\"pack\":[");
    for (int i = 0; i < monster.pack_count; i++)
    {
        if (i) printf(",");
        print_object(&monster.pack[i]);
    }
    printf("],\"oldch\":\"%c\"},\"world\":{\"rng_seed\":%d,\"player\":", monster.oldch, world.seed);
    print_stats(&world.player);
    printf(",\"player_flags\":%d,\"count\":%d,\"quiet\":%d,\"terse\":", world.player_flags, world.count, world.quiet);
    print_bool(world.terse);
    printf(",\"to_death\":");
    print_bool(world.to_death);
    printf(",\"has_hit\":");
    print_bool(world.has_hit);
    printf(",\"level\":%d,\"max_level\":%d,\"max_hp\":%d,\"vf_hit\":%d,\"monster_present\":", world.level, world.max_level, world.max_hp, world.vf_hit);
    print_bool(world.monster_present);
    printf(",\"markers\":[");
    for (int i = 0; i < world.marker_count; i++)
    {
        if (i) printf(",");
        printf("\"%s\"", world.markers[i]);
    }
    printf("],\"dropped\":[");
    for (int i = 0; i < world.dropped_count; i++)
    {
        if (i) printf(",");
        print_object(&world.dropped[i]);
    }
    printf("],\"trace\":{\"xeroc_hallu\":");
    if (world.has_xeroc_hallu) printf("\"%c\"", world.xeroc_hallu); else printf("null");
    printf(",\"roll_hit\":");
    print_trace_bool(world.has_roll_hit, world.roll_hit);
    printf(",\"roll_rng\":");
    print_trace_int(world.has_roll_rng, world.roll_rng);
    printf(",\"leprechaun_gold_saved\":");
    print_trace_bool(world.has_leprechaun_gold_saved, world.leprechaun_gold_saved);
    printf(",\"magic_save_roll\":");
    print_trace_int(world.has_magic_save_roll, world.magic_save_roll);
    printf(",\"target_removed\":");
    print_trace_bool(world.has_target_removed, 1);
    printf(",\"level_add\":");
    print_trace_int(world.has_level_add, world.level_add);
    printf("}}}");
}

int main(void)
{
    TestCase cases[9];
    int count = 0;
    Stats hard_to_hit = stats_make(16, 0, 1, -10, 30, "1x1", 30, ISRUN);
    cases[count] = base_case("xeroc_melee_reveal_returns_false", 1, 'X'); cases[count].disguise = 'A'; cases[count].player_flags = ISRUN | ISHALU; cases[count].monster_stats = hard_to_hit; count++;
    cases[count] = base_case("thrown_xeroc_continues_hits", 1, 'X'); cases[count].disguise = 'A'; cases[count].monster_stats = stats_make(16, 0, 5, 20, 30, "1x1", 30, ISRUN); cases[count].thrown = 1; cases[count].weapon = weapon_make(WEAPON, ARROW, 0, 0, "1x1", "2x3", BOW, ISMISL, "arrow"); cases[count].has_weapon = 1; cases[count].current_weapon = weapon_make(WEAPON, BOW, 1, 2, "1x1", "1x1", NO_WEAPON, 0, "bow"); cases[count].has_current_weapon = 1; count++;
    cases[count] = base_case("melee_miss", 7, 'K'); cases[count].monster_stats = hard_to_hit; count++;
    cases[count] = base_case("canhuh_confuses_monster", 1, 'K'); cases[count].player_flags = ISRUN | CANHUH; cases[count].monster_stats = stats_make(16, 0, 5, 20, 30, "1x1", 30, ISRUN); count++;
    cases[count] = base_case("kill_regular_levels_up", 1, 'K'); cases[count].player_stats = stats_make(16, 9, 1, 6, 12, "1x1", 12, ISRUN); cases[count].monster_stats = stats_make(16, 20, 5, 20, 1, "1x1", 30, ISRUN); cases[count].max_hp = 12; count++;
    cases[count] = base_case("kill_flytrap_unholds", 1, 'F'); cases[count].player_flags = ISRUN | ISHELD; cases[count].monster_stats = stats_make(16, 5, 5, 20, 1, "1x1", 30, ISRUN); cases[count].vf_hit = 3; count++;
    cases[count] = base_case("kill_leprechaun_drops_gold", 1, 'L'); cases[count].player_stats = stats_make(16, 0, 10, 6, 30, "1x1", 30, ISRUN); cases[count].monster_stats = stats_make(16, 10, 5, 20, 1, "1x1", 30, ISRUN); cases[count].level = 8; cases[count].max_level = 8; cases[count].fallpos_ok = 1; count++;
    cases[count] = base_case("kill_target_clears_to_death", 1, 'K'); cases[count].monster_flags = ISRUN | ISTARGET; cases[count].monster_stats = stats_make(16, 1, 5, 20, 1, "1x1", 30, ISRUN); cases[count].to_death = 1; count++;
    cases[count] = base_case("remove_mon_drops_pack", 1, 'K'); cases[count].monster_stats = stats_make(16, 1, 5, 20, 1, "1x1", 30, ISRUN); cases[count].monster_pack[cases[count].monster_pack_count++] = object_make(WEAPON, "club", 0); cases[count].monster_pack[cases[count].monster_pack_count++] = object_make(GOLD, "gold", 12); count++;
    printf("{\"schema\":\"gamebench.rogue.source_fight.v1\",\"cases\":[");
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
    return _project(source_fight_report())


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_fight",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return _project(json.loads(proc.stdout))


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-fight-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_fight.c"
        binary = temp / "source_fight"
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
                    "hp": case["monster"]["stats"]["hp"],
                    "exp": case["monster"]["stats"]["exp"],
                    "damage": case["monster"]["stats"]["damage"],
                    "flags": case["monster"]["flags"],
                    "disguise": case["monster"]["disguise"],
                    "pack": [obj["name"] for obj in case["monster"]["pack"]],
                },
                "world": {
                    "rng_seed": case["world"]["rng_seed"],
                    "player": {
                        "exp": case["world"]["player"]["exp"],
                        "level": case["world"]["player"]["level"],
                        "hp": case["world"]["player"]["hp"],
                        "max_hp": case["world"]["player"]["max_hp"],
                        "flags": case["world"]["player"]["flags"],
                    },
                    "player_flags": case["world"]["player_flags"],
                    "count": case["world"]["count"],
                    "quiet": case["world"]["quiet"],
                    "to_death": case["world"]["to_death"],
                    "has_hit": case["world"]["has_hit"],
                    "max_hp": case["world"]["max_hp"],
                    "vf_hit": case["world"]["vf_hit"],
                    "monster_present": case["world"]["monster_present"],
                    "markers": case["world"]["markers"],
                    "dropped": [(obj["name"], obj["goldval"]) for obj in case["world"]["dropped"]],
                    "trace": {key: trace.get(key) for key in TRACE_KEYS},
                },
            }
        )
    return {"schema": report["schema"], "cases": cases}


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_fight.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "cases": [case["name"] for case in reports["c"]["cases"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source fight mismatch")


if __name__ == "__main__":
    main()
