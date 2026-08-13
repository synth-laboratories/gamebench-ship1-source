"""Strong Emerald code-policy baseline (Rust gold).

Finishes the committed Little Root opening (title → ``met_rival``) via the
verified May replay tape, and clears the hard checkpoint suite.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SHARED = Path(__file__).resolve().parents[1] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from opening_tape import BEDROOM_CLOCK_TAPE_INDEX, may_opening_steps  # noqa: E402

CLOCK_TILE = (3, 2)
RIVAL_TARGET = (11, 11)
BIRCH_DOOR = (6, 12)
ROUTE101_BAG = (10, 15)
TAPE_CHUNK = 24

_OPENING_PHASES = {
    "clock_set",
    "clock_visit",
    "tv_broadcast",
    "meet_rival",
    "new_home",
    "met_rival",
}


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    world = readout.get("world") or {}
    memory = session.setdefault("emerald_baseline", {})
    checkpoint = str(readout.get("checkpoint") or "")
    map_id = str(world.get("map") or "")
    phase = str(world.get("phase") or "")
    player = world.get("player") or {}
    px, py = int(player.get("x", 0)), int(player.get("y", 0))
    facing = str(world.get("facing") or "down")

    if phase == "met_rival":
        return _act([("noop", 1)], "met_rival done")

    if checkpoint == "truck_arrival":
        return _act([("right", 48)], "truck held-right exit")

    if checkpoint == "title_menu" or memory.get("opening_tape") == "title":
        return _play_tape(memory, tape_id="title", start=0, reason="title→met_rival tape")

    if checkpoint == "route103_rival" or map_id == "route103" or phase in {
        "rival_battle",
        "rival_defeated",
    }:
        return _route103(world, phase, memory)

    if checkpoint == "route101_rescue" or map_id == "route101":
        return _route101(world, px, py, memory, ply)

    if checkpoint == "birch_lab_exterior" or map_id == "professor_birchs_lab" or phase in {
        "starter_lab",
        "starter_chosen",
        "starter_select",
        "starter_confirm",
        "birch_battle",
        "birch_rescued",
    }:
        if checkpoint == "birch_lab_exterior" and map_id == "littleroot_town":
            action = _step_toward(px, py, BIRCH_DOOR[0], BIRCH_DOOR[1], memory, ply)
            return _act([(action, 16)], f"to Birch door via {action}")
        return _birch_lab(world, phase, memory)

    if checkpoint == "running_shoes" or phase == "running_shoes_received":
        return _running_shoes(world, px, py, map_id, phase, memory, ply)

    if checkpoint == "rival_outside_lab":
        action = _step_toward(px, py, RIVAL_TARGET[0], RIVAL_TARGET[1], memory, ply)
        return _act([(action, 16)], f"rival tile via {action}")

    # Bedroom / continuous Little Root opening (May).
    if checkpoint == "bedroom_idle" or memory.get("opening_tape") == "bedroom" or phase in _OPENING_PHASES:
        return _bedroom_opening(world, px, py, facing, phase, memory)

    if _ui_blocking(world):
        return _act([("a", 1), ("noop", 8)], "clear UI")

    cycle = ("down", "right", "up", "left")
    return _act([(cycle[ply % 4], 16)], "explore")


def _bedroom_opening(
    world: dict[str, Any],
    px: int,
    py: int,
    facing: str,
    phase: str,
    memory: dict[str, Any],
) -> dict[str, Any]:
    if phase == "met_rival":
        return _act([("noop", 1)], "met_rival done")

    if memory.get("opening_tape") == "bedroom":
        return _play_tape(
            memory,
            tape_id="bedroom",
            start=BEDROOM_CLOCK_TAPE_INDEX,
            reason="bedroom→met_rival tape",
        )

    if (px, py) == CLOCK_TILE:
        if facing != "up":
            return _act([("up", 1)], "face clock for tape")
        memory["opening_tape"] = "bedroom"
        memory["tape_cursor"] = BEDROOM_CLOCK_TAPE_INDEX
        return _play_tape(
            memory,
            tape_id="bedroom",
            start=BEDROOM_CLOCK_TAPE_INDEX,
            reason="bedroom→met_rival tape",
        )

    action = _step_toward(px, py, CLOCK_TILE[0], CLOCK_TILE[1], memory, 0)
    return _act([(action, 16)], f"to clock via {action}")


def _play_tape(
    memory: dict[str, Any],
    *,
    tape_id: str,
    start: int,
    reason: str,
) -> dict[str, Any]:
    memory["opening_tape"] = tape_id
    cursor = int(memory.get("tape_cursor", start))
    steps = may_opening_steps()
    if cursor >= len(steps):
        return _act([("noop", 1)], f"{reason} exhausted")
    chunk = [dict(step) for step in steps[cursor : cursor + TAPE_CHUNK]]
    memory["tape_cursor"] = cursor + len(chunk)
    return {"actions": chunk, "policy_reason": f"{reason} @{cursor}"}


def _route101(
    world: dict[str, Any],
    px: int,
    py: int,
    memory: dict[str, Any],
    ply: int,
) -> dict[str, Any]:
    if world.get("dialogue") or world.get("birch_prompt_active"):
        return _act([("a", 1)], "route101 dialogue")
    if (px, py) == ROUTE101_BAG:
        return _act([("noop", 1)], "bag lane")
    action = _step_toward(px, py, ROUTE101_BAG[0], ROUTE101_BAG[1], memory, ply)
    return _act([(action, 16)], f"route101 {action}")


def _route103(world: dict[str, Any], phase: str, memory: dict[str, Any]) -> dict[str, Any]:
    if phase == "rival_defeated":
        if world.get("dialogue"):
            return _act([("a", 1), ("noop", 16)], "post-rival dialogue")
        return _act([("noop", 1)], "rival defeated")

    battle = world.get("battle") if isinstance(world.get("battle"), dict) else {}
    if battle.get("selecting_move"):
        return _act([("a", 1)], "battle fight/move")
    if battle.get("message") or phase == "rival_battle" or world.get("dialogue"):
        return _act([("a", 1), ("noop", 16)], "rival battle advance")
    return _act([("a", 1), ("noop", 16)], "route103 engage")


def _birch_lab(world: dict[str, Any], phase: str, memory: dict[str, Any]) -> dict[str, Any]:
    if phase == "starter_chosen":
        return _act([("noop", 1)], "starter_chosen")

    if phase == "name_entry":
        ready = int(world.get("name_entry_ready_frames") or 0)
        if ready < 60:
            return _act([("noop", 16)], f"name ready {ready}/60")
        if not memory.get("name_ok_focused"):
            memory["name_ok_focused"] = True
            return _act([("start", 1)], "name focus OK")
        return _act([("a", 1), ("noop", 8)], "name confirm")

    n = int(memory.get("lab_up_a") or 0) + 1
    memory["lab_up_a"] = n
    return _act([("up", 16), ("a", 1)], f"lab up/A #{n}")


def _running_shoes(
    world: dict[str, Any],
    px: int,
    py: int,
    map_id: str,
    phase: str,
    memory: dict[str, Any],
    ply: int,
) -> dict[str, Any]:
    if map_id.endswith("house1_f"):
        return _act([("noop", 1)], "home entered")

    if phase == "running_shoes_received" or world.get("running_shoes_item_shown"):
        if (px, py) == (8, 9) and not memory.get("home_route"):
            memory["home_route"] = True
            return _act(
                [("left", 16), ("left", 16), ("left", 16), ("up", 16), ("up", 16)],
                "home door sequence",
            )
        action = _step_toward(px, py, 5, 8, memory, ply)
        return _act([(action, 16)], f"to home via {action}")

    if world.get("running_shoes_trigger") is None and not world.get("pending_running_shoes"):
        return _act([("right", 16)], "shoes trigger east")

    n = int(memory.get("shoes_pages") or 0) + 1
    memory["shoes_pages"] = n
    stage = int(world.get("running_shoes_stage") or 0)
    return _act([("a", 1), ("noop", 16)], f"shoes script #{n} (stage {stage})")


def _ui_blocking(world: dict[str, Any]) -> bool:
    if world.get("clock_prompt_active"):
        return False
    for flag in (
        "dialogue",
        "menu_open",
        "birch_prompt_active",
        "clock_editing",
        "clock_confirming",
        "name_entry_touched",
        "starter_nickname_entry",
    ):
        if world.get(flag):
            return True
    screen = str(world.get("active_screen") or "")
    if screen and screen not in {"field", "overworld"}:
        return True
    battle = world.get("battle")
    return bool(isinstance(battle, dict) and battle.get("message"))


def _step_toward(
    px: int,
    py: int,
    tx: int,
    ty: int,
    memory: dict[str, Any],
    ply: int,
) -> str:
    preferred: list[str] = []
    if py < ty:
        preferred.append("down")
    elif py > ty:
        preferred.append("up")
    if px < tx:
        preferred.append("right")
    elif px > tx:
        preferred.append("left")
    if not preferred:
        preferred = ["up", "right", "down", "left"]

    last_pos = memory.get("last_pos")
    last_action = memory.get("last_action")
    stuck = last_pos == (px, py) and last_action is not None
    failed = list(memory.get("failed_actions") or [])
    if stuck and last_action not in failed:
        failed.append(last_action)
    if not stuck:
        failed = []
    memory["failed_actions"] = failed
    memory["last_pos"] = (px, py)

    order = preferred + [d for d in ("down", "right", "up", "left") if d not in preferred]
    order = [d for d in order if d not in failed] or order
    action = order[0]
    memory["last_action"] = action
    return action


def _act(steps: list[tuple[str, int]], reason: str) -> dict[str, Any]:
    return {
        "actions": [{"action": action, "frames": frames} for action, frames in steps],
        "policy_reason": reason,
    }
