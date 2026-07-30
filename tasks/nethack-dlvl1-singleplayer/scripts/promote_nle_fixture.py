#!/usr/bin/env python3
"""Promote a reviewed staged NLE capture only after strict dual-lane replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.compare_nle_discrepancies import compare_fixture
from shared.task_resolve import resolve_task


REQUIRED_FILES = ("meta.json", "level_dump.json", "actions.jsonl", "snapshots.jsonl")
FIXTURE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid JSON in {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"invalid JSON in {path.name}:{number}: {error}") from error
        if not isinstance(value, dict):
            raise SystemExit(f"{path.name}:{number} must contain a JSON object")
        records.append(value)
    return records


def projection_shows_down_stair(snapshot: dict[str, object], *, x: int, y: int) -> bool:
    projection = snapshot.get("projection")
    if not isinstance(projection, dict):
        return False
    chars = projection.get("chars")
    if not isinstance(chars, list) or not (0 <= y < len(chars)):
        return False
    row = chars[y]
    return isinstance(row, list) and 0 <= x < len(row) and row[x] == ord(">")


def validate_descend_boundary(actions: list[dict[str, object]], snapshots: list[dict[str, object]]) -> None:
    boundaries = [(index, action) for index, action in enumerate(actions, start=1) if "boundary" in action]
    if not boundaries:
        if any("observed_down_stair" in action for action in actions):
            raise SystemExit("observed_down_stair is valid only on a dlvl1 descent boundary")
        if any(snapshot.get("oracle_boundary") for snapshot in snapshots):
            raise SystemExit("oracle boundary snapshot has no matching action boundary")
        return
    if len(boundaries) != 1:
        raise SystemExit("canonical fixture may contain only one terminal boundary")
    index, action = boundaries[0]
    if action.get("boundary") != "dlvl1_descend" or index != len(actions) or action.get("action_name") != "MiscDirection.DOWN":
        raise SystemExit("dlvl1 descent boundary must be the final MiscDirection.DOWN action")
    snapshot = snapshots[index]
    if not (
        snapshot.get("done") is True
        and snapshot.get("terminal_reason") == "descended"
        and snapshot.get("oracle_boundary") == "pre_dlvl2"
    ):
        raise SystemExit("dlvl1 descent boundary requires a pre-dlvl2 terminal snapshot")
    evidence = action.get("observed_down_stair")
    if not isinstance(evidence, dict) or type(evidence.get("x")) is not int or type(evidence.get("y")) is not int:
        raise SystemExit("dlvl1 descent boundary requires an observed_down_stair coordinate")
    x, y = evidence["x"], evidence["y"]
    projection = snapshot.get("projection")
    blstats = projection.get("blstats") if isinstance(projection, dict) else None
    if not isinstance(blstats, list) or len(blstats) < 2 or blstats[:2] != [x, y]:
        raise SystemExit("observed_down_stair must match the hero coordinate in the pre-dlvl2 snapshot")
    if not any(projection_shows_down_stair(prior, x=x, y=y) for prior in snapshots[:index]):
        raise SystemExit("dlvl1 descent boundary lacks an auditable raw NLE down-stair observation")


def validate_capture(source: Path, fixture_id: str) -> None:
    """Fail closed before a diagnostic artifact can enter the canonical corpus."""

    meta = read_json(source / "meta.json")
    level_dump = read_json(source / "level_dump.json")
    actions = read_jsonl(source / "actions.jsonl")
    snapshots = read_jsonl(source / "snapshots.jsonl")
    if meta.get("schema") != "gamebench.nethack.nle_capture.v1":
        raise SystemExit("staged capture has an unsupported meta schema")
    if meta.get("fixture_id") != fixture_id:
        raise SystemExit("--fixture-id must exactly match meta.json fixture_id")
    if meta.get("nle_version") != "0.9.0" or meta.get("nethack_version") != "3.6.6":
        raise SystemExit("canonical fixtures must pin NLE 0.9.0 and NetHack 3.6.6")
    if "fuzz" in meta or meta.get("diagnostic_fuzz") or meta.get("not_a_conformance_pass"):
        raise SystemExit("diagnostic fuzz artifacts may not be promoted into fixtures/nle_oracle")
    pinned_actions = read_json(TASK_DIR / "shared" / "nle_action_map.json").get("actions")
    if not isinstance(pinned_actions, list) or meta.get("action_table") != pinned_actions:
        raise SystemExit("staged capture action table does not match the pinned action map")
    if meta.get("action_table_sha256") != hashlib.sha256(canonical_json(pinned_actions).encode("utf-8")).hexdigest():
        raise SystemExit("staged capture action table hash is invalid")
    if level_dump.get("schema") != "gamebench.nethack.level_dump.v1":
        raise SystemExit("staged capture has an unsupported level_dump schema")
    if "visibility_schedule" in level_dump:
        raise SystemExit("level_dump may not encode future action-indexed visibility")
    if not actions:
        raise SystemExit("canonical fixture must contain at least one action")
    for expected_step, action in enumerate(actions, start=1):
        action_id = action.get("action_id")
        if type(action_id) is not int or not 0 <= action_id < len(pinned_actions):
            raise SystemExit(f"invalid action_id at actions.jsonl step {expected_step}")
        expected_name = pinned_actions[action_id][1]
        if action.get("step") != expected_step or action.get("action_name") != expected_name:
            raise SystemExit(f"action record {expected_step} does not match the pinned action table")
    if [snapshot.get("step") for snapshot in snapshots] != list(range(len(actions) + 1)):
        raise SystemExit("snapshots.jsonl must contain contiguous step-zero through final-action snapshots")
    if not snapshots or bool(snapshots[0].get("done", False)):
        raise SystemExit("canonical fixture must contain a nonterminal step-zero snapshot")
    if any(not isinstance(snapshot.get("projection"), dict) for snapshot in snapshots):
        raise SystemExit("each snapshot must contain an NLE projection object")
    if any(bool(snapshot.get("done", False)) for snapshot in snapshots[:-1]):
        raise SystemExit("canonical fixture contains actions after an NLE-terminal snapshot")
    for snapshot in snapshots:
        projection = snapshot["projection"]
        blstats = projection.get("blstats") if isinstance(projection, dict) else None
        if not isinstance(blstats, list) or len(blstats) < 25 or blstats[23:25] != [0, 1]:
            raise SystemExit("canonical fixture must remain on Main Dungeon dlvl 1 in every raw NLE snapshot")
    validate_descend_boundary(actions, snapshots)
    resolve_task(
        {
            "task_id": fixture_id,
            "seed": int(meta.get("seed", 0)),
            "character": dict(meta.get("character", {})),
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": str(meta.get("auto_more", "raw_explicit")), "vision_radius": 5},
            "level_dump": level_dump,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Verified staged capture directory outside the task tree.")
    parser.add_argument("--fixture-id", required=True, help="Destination fixture id under fixtures/nle_oracle/.")
    args = parser.parse_args()

    source = args.source.resolve()
    if source == TASK_DIR.resolve() or TASK_DIR.resolve() in source.parents:
        raise SystemExit("--source must be an out-of-tree staged capture, never an existing task artifact")
    if not FIXTURE_ID.fullmatch(args.fixture_id):
        raise SystemExit("--fixture-id may contain only letters, digits, '.', '_', and '-'")
    missing = [name for name in REQUIRED_FILES if not (source / name).is_file()]
    if missing:
        raise SystemExit(f"staged capture is missing required files: {', '.join(missing)}")
    validate_capture(source, args.fixture_id)

    failures = [
        *compare_fixture(source, "python"),
        *compare_fixture(source, "rust"),
    ]
    if failures:
        raise SystemExit("refuse promotion: staged NLE capture is not strict-green\n" + "\n".join(failures))

    destination = TASK_DIR / "fixtures" / "nle_oracle" / args.fixture_id
    if destination.exists():
        raise SystemExit(f"refuse overwrite of existing canonical fixture: {destination}")
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=f".{args.fixture_id}.promote-") as temporary:
        staged = Path(temporary) / args.fixture_id
        staged.mkdir()
        for name in REQUIRED_FILES:
            shutil.copy2(source / name, staged / name)
        staged.replace(destination)
    print(json.dumps({"status": "promoted", "fixture": str(destination), "lanes": ["python", "rust"]}, sort_keys=True))


if __name__ == "__main__":
    main()
