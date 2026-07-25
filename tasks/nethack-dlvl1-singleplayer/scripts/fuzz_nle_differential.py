#!/usr/bin/env python3
"""Live NLE differential fuzzer for the own dlvl-1 gold engines.

This is deliberately an oracle-development tool.  It imports NLE only while
the command is running, starts both own lanes from an NLE-derived level dump,
and writes candidate captures only to a caller-selected output directory.
Results are diagnostics, never evidence for the 33-tape conformance corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.capture_nle_fixture import (
    OBSERVATION_KEYS,
    action_table,
    canonical_json,
    deterministic_nle_seeds,
    dungeon_identity,
    hero_position,
    level_dump,
    normalise_reset,
    project,
    read_actions,
    visible_down_stairs,
)
from scripts.compare_nle_discrepancies import expected_public
from shared.task_resolve import resolve_task


PASSABLE = {ord("."), ord("#"), ord("<"), ord(">"), ord("_"), ord("{"), ord("}"), ord("~")}
DIRECTIONS = (
    ("CompassDirection.N", 0, -1),
    ("CompassDirection.E", 1, 0),
    ("CompassDirection.S", 0, 1),
    ("CompassDirection.W", -1, 0),
    ("CompassDirection.NE", 1, -1),
    ("CompassDirection.SE", 1, 1),
    ("CompassDirection.SW", -1, 1),
    ("CompassDirection.NW", -1, -1),
)
PROMPT_PROBE_ACTIONS = (
    "Command.SEARCH",
    "Command.PICKUP",
    "Command.OPEN",
    "Command.CLOSE",
    "Command.KICK",
    "Command.INVENTORY",
    "Command.APPLY",
    "Command.EAT",
)


def compact(value: Any, *, limit: int = 240) -> Any:
    """Keep report values inspectable without embedding a 21×79 plane twice."""

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def difference_paths(expected: Any, actual: Any, *, path: str = "$") -> Iterable[str]:
    """Yield every mismatched expected leaf, with `chars` compared cellwise."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            yield path
            return
        for key, value in expected.items():
            if key not in actual:
                yield f"{path}.{key}"
            else:
                yield from difference_paths(value, actual[key], path=f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            yield path
            return
        for index, value in enumerate(expected):
            yield from difference_paths(value, actual[index], path=f"{path}[{index}]")
        return
    if path.startswith("$.chars[") and isinstance(expected, str) and isinstance(actual, str):
        if len(expected) != len(actual):
            yield path
            return
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left != right:
                yield f"{path}[{index}]"
        return
    if expected != actual:
        yield path


def first_difference(expected: Any, actual: Any, *, ignored: set[str] | None = None, path: str = "$") -> dict[str, Any] | None:
    """Return one structured expected-subset difference, honoring a baseline mask."""

    if ignored and path in ignored:
        return None
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return {"path": path, "expected": compact(expected), "actual": compact(actual)}
        for key, value in expected.items():
            child = f"{path}.{key}"
            if key not in actual:
                if not ignored or child not in ignored:
                    return {"path": child, "expected": compact(value), "actual": "<missing>"}
                continue
            difference = first_difference(value, actual[key], ignored=ignored, path=child)
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return {"path": path, "expected": compact(expected), "actual": compact(actual)}
        for index, value in enumerate(expected):
            difference = first_difference(value, actual[index], ignored=ignored, path=f"{path}[{index}]")
            if difference:
                return difference
        return None
    if path.startswith("$.chars[") and isinstance(expected, str) and isinstance(actual, str):
        if len(expected) != len(actual):
            return {"path": path, "expected": compact(expected), "actual": compact(actual)}
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            child = f"{path}[{index}]"
            if left != right and (not ignored or child not in ignored):
                return {"path": child, "expected": left, "actual": right}
        return None
    if expected != actual:
        return {"path": path, "expected": compact(expected), "actual": compact(actual)}
    return None


def first_transition_difference(expected_base: Any, actual_base: Any, expected: Any, actual: Any, *, path: str = "$") -> dict[str, Any] | None:
    """Compare a step while masking only subtrees still unchanged from both resets."""

    if expected_base != actual_base and expected == expected_base and actual == actual_base:
        return None
    if isinstance(expected_base, dict) and isinstance(actual_base, dict) and isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            child = f"{path}.{key}"
            if key not in actual or key not in expected_base or key not in actual_base:
                return first_difference(value, actual.get(key, "<missing>"), path=child)
            difference = first_transition_difference(expected_base[key], actual_base[key], value, actual[key], path=child)
            if difference:
                return difference
        return None
    if isinstance(expected_base, list) and isinstance(actual_base, list) and isinstance(expected, list) and isinstance(actual, list):
        if len(expected_base) != len(actual_base) or len(expected) != len(actual):
            return first_difference(expected, actual, path=path)
        for index, value in enumerate(expected):
            difference = first_transition_difference(expected_base[index], actual_base[index], value, actual[index], path=f"{path}[{index}]")
            if difference:
                return difference
        return None
    if path.startswith("$.chars[") and all(isinstance(value, str) for value in (expected_base, actual_base, expected, actual)):
        if len(expected_base) != len(actual_base) or len(expected) != len(actual):
            return first_difference(expected, actual, path=path)
        for index, (expected_base_cell, actual_base_cell, expected_cell, actual_cell) in enumerate(zip(expected_base, actual_base, expected, actual, strict=True)):
            child = f"{path}[{index}]"
            if expected_base_cell != actual_base_cell and expected_cell == expected_base_cell and actual_cell == actual_base_cell:
                continue
            if expected_cell != actual_cell:
                return {"path": child, "expected": expected_cell, "actual": actual_cell}
        return None
    if expected_base != actual_base and expected == expected_base and actual == actual_base:
        return None
    return first_difference(expected, actual, path=path)


def nle_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    return expected_public(snapshot)


def action_id_by_name(table: list[list[Any]], name: str) -> int:
    for action_id, canonical, _ in table:
        if canonical == name:
            return int(action_id)
    raise ValueError(f"pinned NLE action {name!r} is unavailable")


def tty_text(observation: dict[str, Any]) -> str:
    rows = observation.get("tty_chars", [])
    if not hasattr(rows, "tolist"):
        return ""
    values = rows.tolist()
    if not isinstance(values, list):
        return ""
    return "\n".join("".join(chr(int(cell)) for cell in row if isinstance(cell, int)) for row in values)


def inferred_input_mode(observation: dict[str, Any]) -> str:
    """Classify the raw NLE screen for campaign recovery and coverage metrics."""

    tty = tty_text(observation).lower()
    message = str(project(observation).get("message", "")).lower()
    text = f"{tty}\n{message}"
    if "--more--" in text:
        return "more"
    if "in what direction" in text or "what direction" in text:
        return "direction"
    if "(y/n" in text or "[yn" in text or "[y/n" in text:
        return "ynq"
    if "what do you want to use" in text or "what do you want to eat" in text or "what do you want to wield" in text:
        return "inventory_letter"
    if "pick an object" in text or "pick a category" in text:
        return "menu"
    if "what do you want to call" in text or "what do you want to name" in text:
        return "string"
    return "normal"


def choose_navigation_action(observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    """Choose a safe movement/MORE action using only the visible NLE plane."""

    if "--More--" in tty_text(observation):
        return action_id_by_name(table, "MiscAction.MORE"), "tty_more", [action_id_by_name(table, "MiscAction.MORE")]

    blstats = observation.get("blstats")
    chars = observation.get("chars")
    if not hasattr(blstats, "tolist") or not hasattr(chars, "tolist"):
        return action_id_by_name(table, "MiscDirection.WAIT"), "missing_visible_plane", [action_id_by_name(table, "MiscDirection.WAIT")]
    stats = blstats.tolist()
    plane = chars.tolist()
    if len(stats) < 2 or not isinstance(plane, list):
        return action_id_by_name(table, "MiscDirection.WAIT"), "missing_hero_position", [action_id_by_name(table, "MiscDirection.WAIT")]
    x, y = int(stats[0]), int(stats[1])
    candidates: list[int] = []
    for name, dx, dy in DIRECTIONS:
        target_x, target_y = x + dx, y + dy
        if not (0 <= target_y < len(plane) and isinstance(plane[target_y], list) and 0 <= target_x < len(plane[target_y])):
            continue
        if int(plane[target_y][target_x]) in PASSABLE:
            candidates.append(action_id_by_name(table, name))
    if not candidates:
        wait = action_id_by_name(table, "MiscDirection.WAIT")
        return wait, "no_visible_navigation_target", [wait]
    return rng.choice(candidates), "visible_navigation", candidates


def choose_prompt_probe_action(observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    """Probe safe commands and recover raw NLE prompts with representable input."""

    mode = inferred_input_mode(observation)
    if mode == "more":
        action_id = action_id_by_name(table, "MiscAction.MORE")
        return action_id, "prompt_recovery_more", [action_id]
    if mode == "direction":
        candidates = [action_id_by_name(table, name) for name, _, _ in DIRECTIONS]
        return rng.choice(candidates), "prompt_recovery_direction", candidates
    if mode != "normal":
        action_id = action_id_by_name(table, "Command.ESC")
        return action_id, f"prompt_recovery_{mode}", [action_id]
    candidates = [action_id_by_name(table, name) for name in PROMPT_PROBE_ACTIONS]
    return rng.choice(candidates), "safe_prompt_probe", candidates


def choose_campaign_action(campaign: str, observation: dict[str, Any], table: list[list[Any]], rng: random.Random) -> tuple[int, str, list[int]]:
    if campaign == "navigation-v0":
        return choose_navigation_action(observation, table, rng)
    if campaign == "prompt-probe-v0":
        return choose_prompt_probe_action(observation, table, rng)
    raise ValueError(f"unsupported live NLE campaign {campaign!r}")


def normalise_step(result: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(result, tuple) and len(result) >= 3:
        return dict(result[0]), bool(result[2])
    return dict(result), False


def python_trace(task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    projections = [engine.public_projection()]
    for record in actions:
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        engine.step(int(record["action_id"]))
        projections.append(engine.public_projection())
    return projections


def rust_trace(task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entry = {**task, "actions": [int(record["action_id"]) for record in actions]}
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--trace-stdin"],
        input=json.dumps(entry),
        text=True,
        capture_output=True,
        check=True,
    )
    return list(json.loads(completed.stdout)["snapshots"])


def lane_report(lane: str, expected: list[dict[str, Any]], actual: list[dict[str, Any]], actions: list[dict[str, Any]], *, strict_baseline: bool) -> dict[str, Any]:
    baseline_mask = set() if strict_baseline else set(difference_paths(expected[0], actual[0]))

    strict_difference: dict[str, Any] | None = None
    transition_difference: dict[str, Any] | None = None
    for step, expected_snapshot in enumerate(expected):
        action = actions[step - 1] if step > 0 and step - 1 < len(actions) else None
        if step >= len(actual):
            difference = {"path": "$.trace", "expected": f"snapshot at step {step}", "actual": "trace ended early"}
        else:
            difference = first_difference(expected_snapshot, actual[step])
        if difference and strict_difference is None:
            strict_difference = {"step": step, "action": action, **difference}
        if step >= len(actual):
            masked = difference
        elif strict_baseline:
            masked = first_difference(expected_snapshot, actual[step])
        else:
            masked = first_transition_difference(expected[0], actual[0], expected_snapshot, actual[step])
        if masked and transition_difference is None:
            transition_difference = {"step": step, "action": action, **masked}

    return {
        "lane": lane,
        "strict_snapshot_v1": {"status": "equal" if strict_difference is None else "diverged", "first_difference": strict_difference},
        "bootstrap_masked_transition_v0": {
            "status": "equal" if transition_difference is None else "diverged",
            "first_difference": transition_difference,
            "baseline_masked_path_count": len(baseline_mask),
            "strict_baseline": strict_baseline,
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def action_family(action_name: str) -> str:
    return action_name.partition(".")[0] or "unknown"


def changed_blstats_slots(snapshots: list[dict[str, Any]]) -> list[int]:
    if not snapshots:
        return []
    initial = list(dict(snapshots[0].get("projection", {})).get("blstats", []))
    changed: set[int] = set()
    for snapshot in snapshots[1:]:
        current = list(dict(snapshot.get("projection", {})).get("blstats", []))
        for index, (before, after) in enumerate(zip(initial, current, strict=False)):
            if before != after:
                changed.add(index)
    return sorted(changed)


def coverage_report(table: list[list[Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize selected and NLE-stepped inputs, not a parity claim."""

    actions = [record for case in cases for record in case["actions"]]
    selected_action_ids = sorted({int(record["action_id"]) for record in actions})
    nle_stepped_actions = [record for record in actions if record.get("nle_stepped") is True]
    nle_stepped_action_ids = sorted({int(record["action_id"]) for record in nle_stepped_actions})
    contexts = sorted(
        {
            (
                int(record["action_id"]),
                str(record["action_name"]),
                str(record.get("input_mode", "unknown")),
                record.get("nle_stepped") is True,
            )
            for record in actions
        }
    )
    family_counts = Counter(action_family(str(record["action_name"])) for record in actions)
    mode_counts = Counter(str(record.get("input_mode", "unknown")) for record in actions)
    selection_counts = Counter(str(record.get("selection", "unknown")) for record in actions)
    terminal_counts = Counter(
        str(snapshot.get("terminal_reason", ""))
        for case in cases
        for snapshot in case["snapshots"]
        if snapshot.get("terminal_reason")
    )
    mutable_blstats = sorted({slot for case in cases for slot in changed_blstats_slots(case["snapshots"])})
    observation_delta_counts = Counter()
    for case in cases:
        snapshots = case["snapshots"]
        if not snapshots:
            continue
        baseline = dict(snapshots[0].get("projection", {}))
        for snapshot in snapshots[1:]:
            current = dict(snapshot.get("projection", {}))
            for key in ("chars", "colors", "glyphs", "message_raw", "inventory"):
                if baseline.get(key) != current.get(key):
                    observation_delta_counts[key] += 1
    differential_counts = Counter()
    first_paths = Counter()
    signatures: list[dict[str, Any]] = []
    for case in cases:
        report = case["report"]
        for lane in report["lanes"]:
            status = str(lane["bootstrap_masked_transition_v0"]["status"])
            differential_counts[f"transition_{status}"] += 1
            difference = lane["bootstrap_masked_transition_v0"].get("first_difference")
            if difference:
                first_paths[str(difference.get("path", "unknown"))] += 1
        initial = dict(case["snapshots"][0].get("projection", {})) if case["snapshots"] else {}
        signature_payload = {
            "initial_chars": initial.get("chars", []),
            "contexts": [
                (record["action_id"], record.get("input_mode", "unknown"), record.get("nle_stepped") is True)
                for record in case["actions"]
            ],
            "terminal_reasons": [snapshot.get("terminal_reason", "") for snapshot in case["snapshots"] if snapshot.get("terminal_reason")],
        }
        signatures.append(
            {
                "fixture_id": case["meta"]["fixture_id"],
                "sha256": hashlib.sha256(canonical_json(signature_payload).encode("utf-8")).hexdigest(),
            }
        )
    return {
        "schema": "gamebench.nethack.live_fuzz_coverage.v1",
        "diagnostic_fuzz": True,
        "not_a_conformance_pass": True,
        "cases": len(cases),
        "action_ids": {
            "selected": selected_action_ids,
            "selected_count": len(selected_action_ids),
            "nle_stepped": nle_stepped_action_ids,
            "nle_stepped_count": len(nle_stepped_action_ids),
            "pinned_count": len(table),
            "selected_fraction": len(selected_action_ids) / len(table) if table else 0.0,
            "nle_stepped_fraction": len(nle_stepped_action_ids) / len(table) if table else 0.0,
        },
        "action_contexts": [
            {"action_id": action_id, "action_name": action_name, "input_mode": input_mode, "nle_stepped": nle_stepped}
            for action_id, action_name, input_mode, nle_stepped in contexts
        ],
        "enum_family_step_counts": dict(sorted(family_counts.items())),
        "input_mode_step_counts": dict(sorted(mode_counts.items())),
        "selection_step_counts": dict(sorted(selection_counts.items())),
        "terminal_reason_counts": dict(sorted(terminal_counts.items())),
        "observation": {
            "changed_blstats_slots": mutable_blstats,
            "changed_blstats_slot_count": len(mutable_blstats),
            "snapshot_delta_counts": dict(sorted(observation_delta_counts.items())),
        },
        "differential": {
            "transition_lane_counts": dict(sorted(differential_counts.items())),
            "first_difference_paths": dict(sorted(first_paths.items())),
        },
        "novelty_signatures": signatures,
    }


def capture_case(*, case_index: int, seed: int, character: str, steps: int, campaign: str, table: list[list[Any]], tape: list[int], output: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:
        raise SystemExit("Live NLE fuzzing requires the optional nle==0.9.0 oracle environment. Create the CPython 3.10 dev venv documented in README.md.") from error

    case_seed = seed + case_index
    rng = random.Random(case_seed)
    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        max_episode_steps=max(steps + 1, 100),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        live_table = action_table(env)
        if live_table != table:
            raise RuntimeError("NLE action table drifted from shared/nle_action_map.json; refuse to fuzz against mismatched action ids")
        core_seed, display_seed = deterministic_nle_seeds(case_seed)
        if hasattr(env, "seed"):
            nle_seeds = env.seed(core=core_seed, disp=display_seed, reseed=False)
        else:
            nle_seeds = (core_seed, display_seed, False)
        observation = normalise_reset(env.reset())
        initial_observation = deepcopy(observation)
        known_down_stairs = visible_down_stairs(observation)
        snapshots = [{"step": 0, "projection": project(observation), "done": False, "terminal_reason": ""}]
        action_records: list[dict[str, Any]] = []
        stop_reason = "step_budget"
        for step in range(1, steps + 1):
            input_mode = inferred_input_mode(observation)
            if step <= len(tape):
                action_id = int(tape[step - 1])
                selection = "provided_tape"
                candidates = [action_id]
            else:
                action_id, selection, candidates = choose_campaign_action(campaign, observation, table, rng)
            if not 0 <= action_id < len(table):
                raise ValueError(f"fuzz action {action_id} is outside pinned NLE action table length {len(table)}")
            action_name = str(table[action_id][1])
            known_down_stairs.update(visible_down_stairs(observation))
            pre_action_projection = project(observation)
            if action_name == "MiscDirection.DOWN":
                if hero_position(observation) not in known_down_stairs:
                    pre_action_dungeon = dungeon_identity(observation)
                else:
                    action_records.append({"step": step, "action_id": action_id, "action_name": action_name, "input_mode": input_mode, "selection": selection, "candidates": candidates, "boundary": "dlvl1_descend", "nle_stepped": False})
                    snapshots.append({"step": step, "projection": pre_action_projection, "done": True, "terminal_reason": "descended", "oracle_boundary": "pre_dlvl2"})
                    stop_reason = "dlvl1_descend"
                    break
            else:
                pre_action_dungeon = dungeon_identity(observation)
            result = env.step(action_id)
            next_observation, done = normalise_step(result)
            if action_name == "MiscDirection.DOWN" and dungeon_identity(next_observation) != pre_action_dungeon:
                action_records.append({"step": step, "action_id": action_id, "action_name": action_name, "input_mode": input_mode, "selection": selection, "candidates": candidates, "boundary": "dlvl1_descend", "nle_stepped": True})
                snapshots.append({"step": step, "projection": pre_action_projection, "done": True, "terminal_reason": "descended", "oracle_boundary": "pre_dlvl2"})
                stop_reason = "dlvl1_descend"
                break
            observation = next_observation
            known_down_stairs.update(visible_down_stairs(observation))
            action_records.append({"step": step, "action_id": action_id, "action_name": action_name, "input_mode": input_mode, "selection": selection, "candidates": candidates, "nle_stepped": True})
            snapshots.append({"step": step, "projection": project(observation), "done": done, "terminal_reason": "nle_done_unknown" if done else ""})
            if done:
                stop_reason = "nle_done"
                break
        fixture_id = f"fuzz-case-{case_index:04d}-seed-{case_seed}"
        meta = {
            "schema": "gamebench.nethack.nle_capture.v1",
            "fixture_id": fixture_id,
            "nle_version": getattr(nle, "__version__", "unknown"),
            "nethack_version": "3.6.6",
            "character": {"nle_character": character},
            "seed": case_seed,
            "nle_seeds": {"core": int(nle_seeds[0]), "display": int(nle_seeds[1]), "reseed": bool(nle_seeds[2])},
            "observation_keys": OBSERVATION_KEYS,
            "auto_more": "raw_explicit",
            "action_table": table,
            "action_table_sha256": hashlib.sha256(canonical_json(table).encode("utf-8")).hexdigest(),
            "fuzz": {"diagnostic_fuzz": True, "not_a_conformance_pass": True, "campaign": campaign, "requested_steps": steps, "stop_reason": stop_reason},
        }
        task = {
            "task_id": fixture_id,
            "seed": case_seed,
            "character": {"nle_character": character},
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
            "level_dump": level_dump(initial_observation, {}),
        }
        case_dir = output / "cases" / fixture_id
        write_json(case_dir / "meta.json", meta)
        write_json(case_dir / "level_dump.json", task["level_dump"])
        write_jsonl(case_dir / "actions.jsonl", action_records)
        write_jsonl(case_dir / "snapshots.jsonl", snapshots)
        return meta, task, action_records, snapshots
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=1)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--lane", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--campaign", choices=("navigation-v0", "prompt-probe-v0"), default="navigation-v0", help="State-aware action family; supplied --actions always takes priority.")
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--actions", type=Path, default=None, help="Optional JSONL action tape; remaining steps use the selected campaign.")
    parser.add_argument("--output", type=Path, required=True, help="Explicit out-of-tree artifact root; candidate captures are never written to fixtures/nle_oracle.")
    parser.add_argument("--strict-baseline", action="store_true", help="Treat reset mismatches as transition discrepancies instead of masking them.")
    parser.add_argument("--allow-divergences", action="store_true", help="Report diagnostic discrepancies but exit zero after writing artifacts.")
    args = parser.parse_args()
    if args.cases < 1 or args.steps < 1:
        raise SystemExit("--cases and --steps must both be positive")
    output = args.output.resolve()
    if TASK_DIR.resolve() in output.parents or output == TASK_DIR.resolve():
        raise SystemExit("--output must be outside the task directory so fuzz artifacts cannot accidentally enter the canonical corpus")
    tape = read_actions(args.actions) if args.actions else []
    pinned_table = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())["actions"]
    reports: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for case_index in range(args.cases):
        meta, task, actions, snapshots = capture_case(case_index=case_index, seed=args.seed, character=args.character, steps=args.steps, campaign=args.campaign, table=pinned_table, tape=tape, output=output)
        expected = [nle_projection(snapshot) for snapshot in snapshots]
        lanes = ("python", "rust") if args.lane == "both" else (args.lane,)
        case_reports: list[dict[str, Any]] = []
        for lane in lanes:
            actual = python_trace(task, actions) if lane == "python" else rust_trace(task, actions)
            case_reports.append(lane_report(lane, expected, actual, actions, strict_baseline=args.strict_baseline))
        report = {
            "schema": "gamebench.nethack.live_fuzz_result.v1",
            "diagnostic_fuzz": True,
            "not_a_conformance_pass": True,
            "fixture_id": meta["fixture_id"],
            "artifact": str(output / "cases" / meta["fixture_id"]),
            "lanes": case_reports,
        }
        write_json(output / "results" / f"{meta['fixture_id']}.json", report)
        reports.append(report)
        cases.append({"meta": meta, "actions": actions, "snapshots": snapshots, "report": report})
    coverage = coverage_report(pinned_table, cases)
    write_json(output / "coverage.json", coverage)
    summary = {
        "schema": "gamebench.nethack.live_fuzz_run.v1",
        "diagnostic_fuzz": True,
        "not_a_conformance_pass": True,
        "cases": args.cases,
        "steps": args.steps,
        "seed": args.seed,
        "lane": args.lane,
        "campaign": args.campaign,
        "strict_baseline": args.strict_baseline,
        "coverage": coverage,
        "reports": reports,
    }
    write_json(output / "run.json", summary)
    diverged = any(
        lane["bootstrap_masked_transition_v0"]["status"] == "diverged"
        for report in reports
        for lane in report["lanes"]
    )
    print(json.dumps({"status": "diverged" if diverged else "no_new_transition_divergence", "artifact_root": str(output), "cases": args.cases, "lanes": args.lane, "campaign": args.campaign, "distinct_selected_action_ids": coverage["action_ids"]["selected_count"], "distinct_nle_stepped_action_ids": coverage["action_ids"]["nle_stepped_count"], "diagnostic_fuzz": True}, sort_keys=True))
    if diverged and not args.allow_divergences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
