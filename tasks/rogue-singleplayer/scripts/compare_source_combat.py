#!/usr/bin/env python3
"""Compare source-derived Rogue combat math across C, Python, and Rust."""

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

from source_combat import source_combat_report


C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define VS_POISON 0
#define VS_MAGIC 3
#define ISRUN 0020000
#define ISMISL 0000004
#define R_PROTECT 0
#define R_ADDHIT 7
#define R_ADDDAM 8
#define BOW 2
#define ARROW 3
#define NO_WEAPON -1

typedef struct stats {
    int strength;
    int exp;
    int level;
    int arm;
    int hp;
    const char *damage;
    int max_hp;
    int flags;
} Stats;

typedef struct weapon {
    int which;
    int hplus;
    int dplus;
    const char *damage;
    const char *hurl_damage;
    int launch;
    int flags;
} Weapon;

typedef struct ring {
    int which;
    int arm;
} Ring;

static int seed;

static int str_plus[32] = {-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3};
static int add_dam[32] = {-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6};

#define RN (((seed = seed*11109+13849) >> 16) & 0xffff)

int rnd(int range)
{
    return range == 0 ? 0 : abs((int) RN) % range;
}

int roll(int number, int sides)
{
    int total = 0;
    while (number--)
        total += rnd(sides) + 1;
    return total;
}

int swing_raw(int at_lvl, int op_arm, int wplus, int *roll_out, int *need_out)
{
    int res = rnd(20);
    int need = (20 - at_lvl) - op_arm;
    *roll_out = res;
    *need_out = need;
    return (res + wplus >= need);
}

int save_throw_raw(int which, int level, int *need_out, int *roll_out)
{
    int need = 14 + which - level / 2;
    int save_roll = roll(1, 20);
    *need_out = need;
    *roll_out = save_roll;
    return save_roll >= need;
}

int save_adjusted(int which, Stats player, Ring *left, Ring *right, int *adjusted_out, int *need_out, int *roll_out)
{
    int adjusted = which;
    if (which == VS_MAGIC)
    {
        if (left != NULL && left->which == R_PROTECT)
            adjusted -= left->arm;
        if (right != NULL && right->which == R_PROTECT)
            adjusted -= right->arm;
    }
    *adjusted_out = adjusted;
    return save_throw_raw(adjusted, player.level, need_out, roll_out);
}

int exp_add(int level, int max_hp)
{
    int mod;
    if (level == 1)
        mod = max_hp / 8;
    else
        mod = max_hp / 6;
    if (level > 9)
        mod *= 20;
    else if (level > 6)
        mod *= 4;
    return mod;
}

void print_stats(Stats stats)
{
    printf("{\"strength\":%d,\"exp\":%d,\"level\":%d,\"arm\":%d,\"hp\":%d,\"damage\":\"%s\",\"max_hp\":%d,\"flags\":%d}",
        stats.strength, stats.exp, stats.level, stats.arm, stats.hp, stats.damage, stats.max_hp, stats.flags);
}

void print_swing_case(int initial_seed, int at_lvl, int op_arm, int wplus)
{
    int roll_value;
    int need;
    seed = initial_seed;
    int hit = swing_raw(at_lvl, op_arm, wplus, &roll_value, &need);
    printf("{\"seed\":%d,\"roll\":%d,\"need\":%d,\"hit\":%s,\"rng_seed\":%d}", initial_seed, roll_value, need, hit ? "true" : "false", seed);
}

void print_save_throw_case(int initial_seed, int which, int level)
{
    int need;
    int save_roll;
    seed = initial_seed;
    int saved = save_throw_raw(which, level, &need, &save_roll);
    printf("{\"seed\":%d,\"which\":%d,\"level\":%d,\"need\":%d,\"roll\":%d,\"saved\":%s,\"rng_seed\":%d}",
        initial_seed, which, level, need, save_roll, saved ? "true" : "false", seed);
}

void print_save_case(int initial_seed, int which, Stats player, Ring *left, Ring *right)
{
    int adjusted;
    int need;
    int save_roll;
    seed = initial_seed;
    int saved = save_adjusted(which, player, left, right, &adjusted, &need, &save_roll);
    printf("{\"seed\":%d,\"which\":%d,\"original_which\":%d,\"level\":%d,\"need\":%d,\"roll\":%d,\"saved\":%s,\"rng_seed\":%d}",
        initial_seed, adjusted, which, player.level, need, save_roll, saved ? "true" : "false", seed);
}

void print_roll_em_result(
    int initial_seed,
    Stats attacker,
    Stats defender,
    Weapon *weap,
    int hurl,
    int weapon_is_current,
    Weapon *current_weapon,
    int has_current_armor,
    int current_armor_arm,
    Ring *left_ring,
    Ring *right_ring,
    int defender_is_player)
{
    seed = initial_seed;
    const char *damage_expression;
    int hplus;
    int dplus;
    if (weap == NULL)
    {
        damage_expression = attacker.damage;
        hplus = 0;
        dplus = 0;
    }
    else
    {
        hplus = weap->hplus;
        dplus = weap->dplus;
        if (weapon_is_current)
        {
            if (left_ring != NULL && left_ring->which == R_ADDDAM)
                dplus += left_ring->arm;
            else if (left_ring != NULL && left_ring->which == R_ADDHIT)
                hplus += left_ring->arm;
            if (right_ring != NULL && right_ring->which == R_ADDDAM)
                dplus += right_ring->arm;
            else if (right_ring != NULL && right_ring->which == R_ADDHIT)
                hplus += right_ring->arm;
        }
        damage_expression = weap->damage;
        if (hurl)
        {
            if ((weap->flags & ISMISL) && current_weapon != NULL && current_weapon->which == weap->launch)
            {
                damage_expression = weap->hurl_damage;
                hplus += current_weapon->hplus;
                dplus += current_weapon->dplus;
            }
            else if (weap->launch < 0)
                damage_expression = weap->hurl_damage;
        }
    }
    if (!(defender.flags & ISRUN))
        hplus += 4;
    int defender_arm = defender.arm;
    if (defender_is_player)
    {
        if (has_current_armor)
            defender_arm = current_armor_arm;
        if (left_ring != NULL && left_ring->which == R_PROTECT)
            defender_arm -= left_ring->arm;
        if (right_ring != NULL && right_ring->which == R_PROTECT)
            defender_arm -= right_ring->arm;
    }

    int did_hit = 0;
    printf("{\"did_hit\":");
    int did_hit_position = 0;
    (void)did_hit_position;
    char attack_buffer[8192];
    int attack_len = 0;
    attack_buffer[attack_len++] = '[';
    const char *cp = damage_expression;
    int first_attack = 1;
    while (cp != NULL && *cp != '\0')
    {
        int ndice = atoi(cp);
        cp = strchr(cp, 'x');
        if (cp == NULL)
            break;
        int nsides = atoi(++cp);
        int roll_value;
        int need;
        int hit = swing_raw(attacker.level, defender_arm, hplus + str_plus[attacker.strength], &roll_value, &need);
        int swing_seed = seed;
        int damage_roll = 0;
        int damage = 0;
        int applied = 0;
        if (hit)
        {
            damage_roll = roll(ndice, nsides);
            damage = dplus + damage_roll + add_dam[attacker.strength];
            applied = damage > 0 ? damage : 0;
            defender.hp -= applied;
            did_hit = 1;
        }
        if (!first_attack)
            attack_buffer[attack_len++] = ',';
        first_attack = 0;
        attack_len += sprintf(
            &attack_buffer[attack_len],
            "{\"ndice\":%d,\"nsides\":%d,\"swing\":{\"roll\":%d,\"need\":%d,\"hit\":%s,\"rng_seed\":%d},\"damage_roll\":%d,\"damage\":%d",
            ndice, nsides, roll_value, need, hit ? "true" : "false", swing_seed, damage_roll, damage);
        if (hit)
            attack_len += sprintf(&attack_buffer[attack_len], ",\"applied\":%d", applied);
        attack_buffer[attack_len++] = '}';
        cp = strchr(cp, '/');
        if (cp == NULL)
            break;
        cp++;
    }
    attack_buffer[attack_len++] = ']';
    attack_buffer[attack_len] = '\0';

    printf("%s", did_hit ? "true" : "false");
    printf(",\"attacker\":");
    print_stats(attacker);
    printf(",\"defender\":");
    print_stats(defender);
    printf(",\"rng_seed\":%d,\"attacks\":%s,\"damage_expression\":\"%s\",\"hplus\":%d,\"dplus\":%d,\"defender_arm\":%d}",
        seed, attack_buffer, damage_expression, hplus, dplus, defender_arm);
}

void print_roll_case_monster_claw(void)
{
    printf("{\"name\":\"monster_claw\",\"result\":");
    print_roll_em_result(1, (Stats){10, 0, 3, 5, 12, "1x3/1x3", 12, 0}, (Stats){10, 0, 1, 7, 10, "1x4", 10, 0}, NULL, 0, 0, NULL, 0, 0, NULL, NULL, 0);
    printf("}");
}

void print_roll_case_current_mace(void)
{
    Weapon mace = {0, 1, 1, "2x4", "1x3", NO_WEAPON, 0};
    Ring left = {R_ADDHIT, 2};
    Ring right = {R_ADDDAM, 3};
    printf("{\"name\":\"current_mace_with_rings\",\"result\":");
    print_roll_em_result(7, (Stats){18, 0, 4, 5, 20, "1x4", 20, 0}, (Stats){10, 0, 5, 4, 30, "1x6", 30, 0}, &mace, 0, 1, NULL, 0, 0, &left, &right, 0);
    printf("}");
}

void print_roll_case_hurled_arrow(void)
{
    Weapon arrow = {ARROW, 0, 0, "1x1", "2x3", BOW, ISMISL};
    Weapon bow = {BOW, 1, 2, "1x1", "1x1", NO_WEAPON, 0};
    printf("{\"name\":\"hurled_arrow_with_bow\",\"result\":");
    print_roll_em_result(12345, (Stats){16, 0, 6, 5, 22, "1x4", 22, 0}, (Stats){10, 0, 8, 2, 45, "2x6", 45, 0}, &arrow, 1, 0, &bow, 0, 0, NULL, NULL, 0);
    printf("}");
}

void print_roll_case_defender_player(void)
{
    Ring left = {R_PROTECT, 1};
    Ring right = {R_PROTECT, 2};
    printf("{\"name\":\"defender_player_protection\",\"result\":");
    print_roll_em_result(-17, (Stats){20, 0, 9, 2, 50, "3x4/2x5", 50, 0}, (Stats){16, 0, 7, 8, 35, "1x4", 35, 0}, NULL, 0, 0, NULL, 1, 4, &left, &right, 1);
    printf("}");
}

int main(void)
{
    Ring protect2 = {R_PROTECT, 2};
    Ring protect1 = {R_PROTECT, 1};
    Ring protect3 = {R_PROTECT, 3};
    printf("{\"swing\":[");
    print_swing_case(1, 1, 6, 0);
    printf(",");
    print_swing_case(7, 5, 2, 3);
    printf(",");
    print_swing_case(-17, 12, -1, 5);
    printf("],\"save\":[");
    print_save_throw_case(1, VS_POISON, 1);
    printf(",");
    print_save_case(7, VS_MAGIC, (Stats){16, 0, 5, 6, 12, "1x4", 12, 0}, &protect2, NULL);
    printf(",");
    print_save_case(-17, VS_MAGIC, (Stats){16, 0, 10, 6, 20, "1x4", 20, 0}, &protect1, &protect3);
    printf("],\"roll_em\":[");
    print_roll_case_monster_claw();
    printf(",");
    print_roll_case_current_mace();
    printf(",");
    print_roll_case_hurled_arrow();
    printf(",");
    print_roll_case_defender_player();
    printf("],\"exp_add\":[");
    printf("{\"level\":1,\"max_hp\":7,\"value\":%d}", exp_add(1, 7));
    printf(",");
    printf("{\"level\":5,\"max_hp\":30,\"value\":%d}", exp_add(5, 30));
    printf(",");
    printf("{\"level\":8,\"max_hp\":48,\"value\":%d}", exp_add(8, 48));
    printf(",");
    printf("{\"level\":12,\"max_hp\":90,\"value\":%d}", exp_add(12, 90));
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    return source_combat_report()


def rust_report() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "source_combat",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-combat-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_combat.c"
        binary = temp / "source_combat"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    summary = {
        "schema": "gamebench.rogue.source_combat.v1",
        "c_python_match": reports["c"] == reports["python"],
        "c_rust_match": reports["c"] == reports["rust"],
        "roll_em_cases": [case["name"] for case in reports["c"]["roll_em"]],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if reports["c"] != reports["python"] or reports["c"] != reports["rust"]:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        raise SystemExit("C/Python/Rust source combat mismatch")


if __name__ == "__main__":
    main()
