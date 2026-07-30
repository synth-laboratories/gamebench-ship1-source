#!/usr/bin/env python3
"""Compare source-derived Rogue primitives across C, Python, and Rust."""

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

from source_rogue import RogueRng, command_move_delta, direction_delta, step_ok


SEEDS = [0, 1, 7, 12345, -17]
STEP_CHARS = [" ", "|", "-", ".", "#", "+", "%", "*", ":", "A", "z"]
DIRECTION_CHARS = ["h", "H", "j", "K", "x"]

C_SOURCE = r'''
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>

int seed;
#define RN (((seed = seed*11109+13849) >> 16) & 0xffff)

int rnd(int range)
{
    return range == 0 ? 0 : abs((int) RN) % range;
}

int roll(int number, int sides)
{
    int dtotal = 0;
    while (number--)
        dtotal += rnd(sides)+1;
    return dtotal;
}

int spread(int nm)
{
    return nm - nm / 20 + rnd(nm / 10);
}

int gold_calc(int level)
{
    return rnd(50 + 10 * level) + 2;
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

int prompt_dir(char ch, int *dy, int *dx)
{
    switch (ch)
    {
        case 'h': case 'H': *dy = 0; *dx = -1; return 1;
        case 'j': case 'J': *dy = 1; *dx = 0; return 1;
        case 'k': case 'K': *dy = -1; *dx = 0; return 1;
        case 'l': case 'L': *dy = 0; *dx = 1; return 1;
        case 'y': case 'Y': *dy = -1; *dx = -1; return 1;
        case 'u': case 'U': *dy = -1; *dx = 1; return 1;
        case 'b': case 'B': *dy = 1; *dx = -1; return 1;
        case 'n': case 'N': *dy = 1; *dx = 1; return 1;
        default: return 0;
    }
}

int command_dir(char ch, int *dy, int *dx)
{
    switch (ch)
    {
        case 'h': *dy = 0; *dx = -1; return 1;
        case 'j': *dy = 1; *dx = 0; return 1;
        case 'k': *dy = -1; *dx = 0; return 1;
        case 'l': *dy = 0; *dx = 1; return 1;
        case 'y': *dy = -1; *dx = -1; return 1;
        case 'u': *dy = -1; *dx = 1; return 1;
        case 'b': *dy = 1; *dx = -1; return 1;
        case 'n': *dy = 1; *dx = 1; return 1;
        default: return 0;
    }
}

void print_delta(int ok, int dy, int dx)
{
    if (ok)
        printf("[%d,%d]", dy, dx);
    else
        printf("null");
}

void print_rng(int initial)
{
    seed = initial;
    int values[9];
    values[0] = rnd(60);
    values[1] = rnd(100);
    values[2] = rnd(3);
    values[3] = rnd(0);
    values[4] = rnd(17);
    values[5] = roll(3, 6);
    values[6] = spread(70);
    values[7] = gold_calc(1);
    values[8] = gold_calc(13);
    printf("{\"seed\":%d,\"values\":[", initial);
    for (int i = 0; i < 9; i++)
    {
        if (i)
            printf(",");
        printf("%d", values[i]);
    }
    printf("],\"final_seed\":%d}", seed);
}

int main(void)
{
    int seeds[] = {0, 1, 7, 12345, -17};
    char step_chars[] = {' ', '|', '-', '.', '#', '+', '%', '*', ':', 'A', 'z'};
    char dir_chars[] = {'h', 'H', 'j', 'K', 'x'};
    printf("{\"rng\":[");
    for (int i = 0; i < 5; i++)
    {
        if (i)
            printf(",");
        print_rng(seeds[i]);
    }
    printf("],\"step_ok\":[");
    for (int i = 0; i < 11; i++)
    {
        if (i)
            printf(",");
        printf("{\"ch\":\"%c\",\"ok\":%s}", step_chars[i], step_ok(step_chars[i]) ? "true" : "false");
    }
    printf("],\"directions\":[");
    for (int i = 0; i < 5; i++)
    {
        int pdy = 0, pdx = 0, cdy = 0, cdx = 0;
        int pok = prompt_dir(dir_chars[i], &pdy, &pdx);
        int cok = command_dir(dir_chars[i], &cdy, &cdx);
        if (i)
            printf(",");
        printf("{\"ch\":\"%c\",\"prompt\":", dir_chars[i]);
        print_delta(pok, pdy, pdx);
        printf(",\"command\":");
        print_delta(cok, cdy, cdx);
        printf("}");
    }
    printf("]}");
    return 0;
}
'''


def python_report() -> dict[str, Any]:
    rng_reports = []
    for seed in SEEDS:
        rng = RogueRng(seed)
        values = [
            rng.rnd(60),
            rng.rnd(100),
            rng.rnd(3),
            rng.rnd(0),
            rng.rnd(17),
            rng.roll(3, 6),
            rng.spread(70),
            rng.gold_calc(1),
            rng.gold_calc(13),
        ]
        rng_reports.append({"seed": seed, "values": values, "final_seed": rng.seed})
    return {
        "rng": rng_reports,
        "step_ok": [{"ch": ch, "ok": step_ok(ch)} for ch in STEP_CHARS],
        "directions": [
            {
                "ch": ch,
                "prompt": _as_list(direction_delta(ch)),
                "command": _as_list(command_move_delta(ch)),
            }
            for ch in DIRECTION_CHARS
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
            "source_primitives",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def c_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rogue-source-primitives-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source_primitives.c"
        binary = temp / "source_primitives"
        source.write_text(C_SOURCE)
        subprocess.run(["cc", "-O0", "-fwrapv", str(source), "-o", str(binary)], check=True)
        proc = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)


def _as_list(value: tuple[int, int] | None) -> list[int] | None:
    return None if value is None else [value[0], value[1]]


def main() -> None:
    reports = {"c": c_report(), "python": python_report(), "rust": rust_report()}
    print(json.dumps({"schema": "gamebench.rogue.source_primitives.v1", "reports": reports}, indent=2, sort_keys=True))
    if reports["c"] != reports["python"]:
        raise SystemExit("Python source primitive mismatch")
    if reports["c"] != reports["rust"]:
        raise SystemExit("Rust source primitive mismatch")


if __name__ == "__main__":
    main()
