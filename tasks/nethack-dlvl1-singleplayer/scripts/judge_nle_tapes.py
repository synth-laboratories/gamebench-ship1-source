#!/usr/bin/env python3
"""Harsh, non-vacuous, layered replay judge for frozen NLE oracle tapes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.compare_nle_discrepancies import (
    compare_lane,
    expected_public,
    first_difference,
    fixture_task,
    is_dlvl1_descend,
    python_step_projections,
    python_step_semantic_snapshots,
    rust_step_projections,
    rust_step_semantic_snapshots,
)
from scripts.oracle_tape import sha256_json, validate_manifest


LAYERS = ("lifecycle", "semantic_message", "mechanics_state", "screen_planes", "specials", "terminal_ui")


def _decode_tty_rows(rows: Any, *, start: int, stop: int, width: int) -> list[str]:
    result: list[str] = []
    if not isinstance(rows, list):
        return result
    for row in rows[start:stop]:
        cells = row if isinstance(row, list) else []
        result.append("".join(chr(int(cell)) for cell in cells[:width]).ljust(width))
    return result


def _message_row(projection: dict[str, Any]) -> str:
    raw = projection.get("message_raw", [])
    data = bytes(int(cell) for cell in raw if isinstance(cell, int))
    return data.split(b"\0", 1)[0].decode("latin1", errors="replace")[:80].ljust(80)


def _strength(blstats: list[Any]) -> str:
    strength = int(blstats[2])
    if strength <= 18:
        return str(strength)
    return f"18/{max(0, int(blstats[3]) - 18):02d}"


def _status_rows(blstats: list[Any]) -> list[str]:
    if len(blstats) < 27:
        return []
    alignment = {-1: "Chaotic", 0: "Neutral", 1: "Lawful"}.get(int(blstats[26]), "Unaligned")
    first = (
        f"{'Agent the Stripling':<31}"
        f"St:{_strength(blstats)} Dx:{int(blstats[4])} Co:{int(blstats[5])} "
        f"In:{int(blstats[6])} Wi:{int(blstats[7])} Ch:{int(blstats[8])} "
        f"{alignment} S:{int(blstats[9])}"
    )
    second = (
        f"Dlvl:{int(blstats[12])} $:{int(blstats[13])} "
        f"HP:{int(blstats[10])}({int(blstats[11])}) "
        f"Pw:{int(blstats[14])}({int(blstats[15])}) AC:{int(blstats[16])} "
        f"Xp:{int(blstats[18])}/{int(blstats[19])} T:{int(blstats[20])}"
    )
    return [first[:80].ljust(80), second[:80].ljust(80)]


def _text_colors(row: str) -> list[int]:
    return [7 if character != " " else 0 for character in row[:80].ljust(80)]


_INVENTORY_DISPLAY_HEADINGS = ((2, "Weapons"), (3, "Armor"), (7, "Comestibles"), (6, "Tools"))


def _inventory_display_lines(projection: dict[str, Any]) -> list[tuple[str, int]]:
    """Return the observed NLE `(end)` inventory page, or no overlay.

    This is deliberately bounded to the object classes recovered from the
    pinned Valkyrie tapes.  The raw NLE inventory strings omit their letter,
    which the terminal listing supplies as ``a - ...``.
    """

    inventory = projection.get("inventory", {})
    if not isinstance(inventory, dict):
        return []
    letters = inventory.get("inv_letters", [])
    classes = inventory.get("inv_oclasses", [])
    strings = inventory.get("inv_strs", [])
    if not all(isinstance(values, list) for values in (letters, classes, strings)):
        return []
    grouped: dict[int, list[str]] = {object_class: [] for object_class, _ in _INVENTORY_DISPLAY_HEADINGS}
    for letter, object_class, raw in zip(letters, classes, strings, strict=False):
        if not isinstance(letter, int) or letter == 0:
            continue
        if not isinstance(object_class, int) or object_class not in grouped:
            return []
        if not isinstance(raw, str) or not raw:
            return []
        grouped[object_class].append(f"{chr(letter)} - {raw}")
    lines: list[tuple[str, int]] = []
    for object_class, heading in _INVENTORY_DISPLAY_HEADINGS:
        entries = grouped[object_class]
        if not entries:
            continue
        lines.append((heading, 23))
        lines.extend((entry, 7) for entry in entries)
    if not lines:
        return []
    lines.append(("(end)", 7))
    # Longer displays page in NLE; no unobserved pagination policy is claimed.
    if len(lines) > 21 or max(len(text) for text, _ in lines) > 78:
        return []
    return lines


def _overlay_inventory_display(char_rows: list[str], color_rows: list[list[int]], projection: dict[str, Any]) -> tuple[list[str], list[list[int]], list[int] | None]:
    lines = _inventory_display_lines(projection)
    if not lines:
        return char_rows, color_rows, None
    x = 80 - max(len(text) for text, _ in lines) - 2
    if x < 0:
        return char_rows, color_rows, None
    chars = [list(row[:80].ljust(80)) for row in char_rows]
    colors = [(list(row[:80]) + [0] * 80)[:80] for row in color_rows]
    for y, (text, color) in enumerate(lines):
        # NLE clears the complete terminal row before putting an inventory
        # line, including any map cells underneath the list.
        chars[y] = [" "] * 80
        colors[y] = [0] * 80
        chars[y][x : x + len(text)] = list(text)
        colors[y][x : x + len(text)] = [color if character != " " else 0 for character in text]
    return ["".join(row) for row in chars], colors, [len(lines) - 1, x + len("(end)") + 1]


def _terminal_ui_from_oracle(snapshot: dict[str, Any]) -> dict[str, Any]:
    projection = snapshot.get("projection", {})
    return {
        "char_rows": _decode_tty_rows(projection.get("tty_chars", []), start=0, stop=24, width=80),
        "color_rows": projection.get("tty_colors", []),
        "cursor_yx": projection.get("tty_cursor_yx", []),
    }


def _terminal_ui_from_gold(projection: dict[str, Any]) -> dict[str, Any]:
    terminal_tty = projection.get("terminal_tty")
    if isinstance(terminal_tty, dict):
        return {
            "char_rows": terminal_tty.get("char_rows", []),
            "color_rows": terminal_tty.get("color_rows", []),
            "cursor_yx": terminal_tty.get("cursor_yx", []),
        }
    blstats = projection.get("blstats", [])
    mode = projection.get("input_mode", {})
    pager_suffix = "--More--" if projection.get("terminal_ui_pager") else ""
    if pager_suffix:
        cursor = [0, min(79, len(str(projection.get("message", ""))) + len(pager_suffix))]
    elif isinstance(mode, dict) and mode.get("kind") == "normal":
        cursor = [int(blstats[1]) + 1, int(blstats[0])] if len(blstats) >= 2 else []
    else:
        cursor = [0, min(79, len(str(projection.get("message", ""))) + len(pager_suffix) + 1)]
    message_row = _message_row(projection)
    if pager_suffix:
        row = list(message_row)
        start = min(80, len(str(projection.get("message", ""))))
        row[start : start + len(pager_suffix)] = list(pager_suffix)
        message_row = "".join(row[:80]).ljust(80)
    map_rows = [str(row)[:79].ljust(80) for row in projection.get("chars", [])]
    status_rows = _status_rows(blstats)
    map_colors = [
        list(row[:79]) + [0]
        for row in projection.get("colors", [])
    ]
    char_rows = [message_row, *map_rows, *status_rows]
    color_rows = [_text_colors(message_row), *map_colors, *(_text_colors(row) for row in status_rows)]
    if isinstance(mode, dict) and mode.get("kind") == "inventory_display":
        char_rows, color_rows, display_cursor = _overlay_inventory_display(char_rows, color_rows, projection)
        if display_cursor is not None:
            cursor = display_cursor
    return {
        "char_rows": char_rows,
        "color_rows": color_rows,
        "cursor_yx": cursor,
    }


def layers(expected_snapshot: dict[str, Any], actual: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    expected = expected_public(expected_snapshot)
    actual_inventory = actual.get("inventory", {})
    inventory = {
        key: actual_inventory.get(key)
        for key in ("inv_letters", "inv_glyphs", "inv_oclasses", "inv_strs")
    } if isinstance(actual_inventory, dict) else actual_inventory
    return {
        "lifecycle": (
            {"done": expected["done"], "terminal_reason": expected["terminal_reason"]},
            {"done": actual.get("done"), "terminal_reason": actual.get("terminal_reason")},
        ),
        "semantic_message": (
            {"message": expected["message"], "message_raw": expected["message_raw"]},
            {"message": actual.get("message"), "message_raw": actual.get("message_raw")},
        ),
        "mechanics_state": (
            {"blstats": expected["blstats"], "inventory": expected["inventory"]},
            {"blstats": actual.get("blstats"), "inventory": inventory},
        ),
        "screen_planes": (
            {
                "chars": expected["chars"],
                "colors": expected["colors"],
                "glyphs": expected["glyphs"],
            },
            {
                "chars": actual.get("chars"),
                "colors": actual.get("colors"),
                "glyphs": actual.get("glyphs"),
            },
        ),
        "specials": (
            {"specials": expected["specials"]} if "specials" in expected else {},
            {"specials": actual.get("specials")} if "specials" in expected else {},
        ),
        "terminal_ui": (
            _terminal_ui_from_oracle(expected_snapshot),
            _terminal_ui_from_gold(actual),
        ),
    }


def replay(lane: str, task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return python_step_projections(task, actions) if lane == "python" else rust_step_projections(task, actions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=TASK_DIR / "fixtures" / "nle_oracle")
    parser.add_argument("--lane", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--fixture", action="append", default=[])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    fixture_dirs = [root / name for name in args.fixture] if args.fixture else sorted(path.parent for path in root.rglob("meta.json"))
    if not fixture_dirs:
        raise SystemExit("NLE tape judge FAILED: zero oracle fixtures found")
    lanes = ("python", "rust") if args.lane == "both" else (args.lane,)
    failures: list[str] = []
    counts: Counter[str] = Counter()
    evidence: list[dict[str, Any]] = []
    legacy_fixtures: list[str] = []

    for fixture_dir in fixture_dirs:
        failures.extend(validate_manifest(fixture_dir))
        manifest_path = fixture_dir / "tape_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("capture_runtime", {}).get("status") == "legacy_version_only":
                legacy_fixtures.append(fixture_dir.name)
        task, actions, snapshots = fixture_task(fixture_dir)
        if not actions:
            failures.append(f"{fixture_dir.name}: zero recorded inputs")
            continue
        counts["fixtures"] += 1
        counts["inputs"] += len(actions)
        # Public oracle equality is necessary but not sufficient: two gold
        # lanes can render the same frame while carrying different hidden
        # scheduler/object/inventory state into the next action.  Compare the
        # complete private projection at every prefix as a gold-to-gold
        # validity layer.  This deliberately never hydrates native sidecars
        # or treats private state as an oracle claim.
        if lanes == ("python", "rust"):
            try:
                python_semantic = python_step_semantic_snapshots(task, actions)
                rust_semantic = rust_step_semantic_snapshots(task, actions)
            except Exception as exc:  # noqa: BLE001 - materialize fail-hard evidence
                failures.append(f"{fixture_dir.name} cross-lane semantic replay failed: {exc}")
            else:
                if len(python_semantic) != len(rust_semantic):
                    failures.append(
                        f"{fixture_dir.name} cross-lane semantic trace length: "
                        f"Python {len(python_semantic)} != Rust {len(rust_semantic)}"
                    )
                for step, (python_state, rust_state) in enumerate(zip(python_semantic, rust_semantic, strict=False)):
                    counts["cross_lane.semantic_state"] += 1
                    difference = first_difference(python_state, rust_state)
                    evidence.append(
                        {
                            "fixture_id": fixture_dir.name,
                            "lane": "python_vs_rust",
                            "step": step,
                            "layer": "semantic_state",
                            "oracle_sha256": sha256_json(python_state),
                            "gold_sha256": sha256_json(rust_state),
                            "status": "equal" if difference is None else "diverged",
                            "first_difference": difference,
                        }
                    )
                    if difference:
                        failures.append(f"{fixture_dir.name} cross-lane step {step} semantic_state: {difference}")
                        break
        for lane in lanes:
            first = replay(lane, task, actions)
            second = replay(lane, task, actions)
            deterministic_difference = first_difference(first, second)
            counts[f"{lane}.determinism_runs"] += 2
            if deterministic_difference:
                failures.append(f"{fixture_dir.name} {lane} nondeterministic replay: {deterministic_difference}")
                continue
            failures.extend(compare_lane(fixture_dir, lane, actions, snapshots, first))
            descent_steps = {
                int(record.get("step", -1))
                for record in actions
                if is_dlvl1_descend(record)
            }
            for step, snapshot in enumerate(snapshots):
                # A dlvl-1 descent snapshot is captured before DOWN, while
                # the gold trace includes the owned terminal transition at
                # the action's index. Layer the pre-action frame here; the
                # terminal contract itself is checked by compare_lane.
                actual_step = step - 1 if step in descent_steps else step
                if actual_step < 0 or actual_step >= len(first):
                    break
                layer_snapshot = snapshot
                if step in descent_steps:
                    layer_snapshot = {
                        **snapshot,
                        "done": False,
                        "terminal_reason": "",
                    }
                for layer_name, (expected, actual) in layers(layer_snapshot, first[actual_step]).items():
                    counts[f"{lane}.{layer_name}"] += 1
                    difference = first_difference(expected, actual)
                    evidence.append(
                        {
                            "fixture_id": fixture_dir.name,
                            "lane": lane,
                            "step": step,
                            "layer": layer_name,
                            "oracle_sha256": sha256_json(expected),
                            "gold_sha256": sha256_json(actual),
                            "status": "equal" if difference is None else "diverged",
                            "first_difference": difference,
                        }
                    )
                    if difference:
                        failures.append(f"{fixture_dir.name} {lane} step {step} {layer_name}: {difference}")
                        break

    for lane in lanes:
        if counts[f"{lane}.determinism_runs"] < 2:
            failures.append(f"{lane}: zero deterministic replay comparisons")
        for layer_name in LAYERS:
            if counts[f"{lane}.{layer_name}"] == 0:
                failures.append(f"{lane}: zero {layer_name} comparisons")
    if lanes == ("python", "rust") and counts["cross_lane.semantic_state"] == 0:
        failures.append("cross-lane: zero semantic_state comparisons")

    try:
        reported_root = str(root.relative_to(TASK_DIR))
    except ValueError:
        reported_root = str(root)
    report = {
        "schema": "gamebench.nethack.oracle_judge_report.v1",
        "status": "pass" if not failures else "failed",
        "oracle_root": reported_root,
        "lanes": list(lanes),
        "counts": dict(sorted(counts.items())),
        "legacy_runtime_provenance": sorted(set(legacy_fixtures)),
        "evidence": evidence,
        "failures": failures,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if failures:
        raise SystemExit("NLE tape judge FAILED\n" + "\n".join(failures))
    print(
        json.dumps(
            {
                "status": "pass",
                "fixtures": counts["fixtures"],
                "inputs": counts["inputs"],
                "lanes": list(lanes),
                "layer_comparisons": sum(counts[f"{lane}.{layer}"] for lane in lanes for layer in LAYERS),
                "legacy_runtime_provenance": len(set(legacy_fixtures)),
                "report": str(args.report.resolve()) if args.report else "",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
