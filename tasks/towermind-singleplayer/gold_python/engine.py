"""Own discrete TowerMind-like tower-defense emulator.

This lane deliberately models the paper's decision pressure, rather than Unity
frames or ML-Agents APIs: spatial build slots, a pickup-only gold economy,
three asymmetric towers, hero/knight micro, fog-disabled friendlies, leaks, and
rejected hallucinated actions are all authoritative here.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[1]
LEVEL_DIR = TASK_ROOT / "defaults" / "levels"
TOWER_RULES = {
    "archer": {"cost": 3, "range": 3, "damage": 2},
    "magician": {"cost": 4, "range": 3, "damage": 1},
    "knight": {"cost": 5, "range": 0, "damage": 0},
}


class TowerMindEnv:
    """Deterministic single-agent environment with JSON-native actions/state."""

    ENV_FAMILY = "towermind-singleplayer"

    def __init__(self) -> None:
        self.state: dict[str, Any] | None = None
        self.events: list[dict[str, Any]] = []
        self._level: dict[str, Any] = {}

    def reset(self, level_id: str = "L1", *, seed: int = 0, initial_gold: int = 0) -> dict[str, Any]:
        level = self._load_level(level_id)
        self._level = level
        self.events = []
        if level["availability"] == "stub":
            self.state = {
                "level": level_id,
                "seed": seed,
                "availability": "stub",
                "tick": 0,
                "base_hp": None,
                "gold": initial_gold,
                "hero": None,
                "knights": [],
                "towers": [],
                "enemies": [],
                "coins": [],
                "total_reward": 0.0,
                "illegal_actions": 0,
                "terminated": False,
                "termination_reason": None,
            }
            self._event("level_stub", "preview", f"LevelStub({level_id})", {"note": level["progression_note"]})
            return self.observation()
        self.state = {
            "level": level_id,
            "seed": seed,
            "availability": "implemented",
            "tick": 0,
            "base_hp": int(level["base_hp"]),
            "gold": initial_gold,
            "hero": {"id": "hero", "pos": list(level["hero_start"]), "hp": 5},
            "knights": [],
            "towers": [],
            "enemies": [],
            "coins": [],
            "total_reward": 0.0,
            "illegal_actions": 0,
            "terminated": False,
            "termination_reason": None,
        }
        self._event("state_transition", "reset", f"Reset(level={level_id},seed={seed})", {"level": level_id, "seed": seed})
        self._spawn_due()
        return self.observation()

    def step(self, action: dict[str, Any] | str) -> dict[str, Any]:
        state = self._require_state()
        parsed = {"kind": action} if isinstance(action, str) else copy.deepcopy(action)
        if not isinstance(parsed, dict):
            parsed = {"kind": "invalid", "raw": repr(action)}
        if state["availability"] == "stub":
            self._illegal(parsed, "level_stub", "L3-L5 are declared progression stubs in v0")
            return self.transition_result()
        if state["terminated"]:
            self._illegal(parsed, "terminal", "episode has already ended")
            return self.transition_result()
        kind = parsed.get("kind")
        if kind == "build":
            self._build(parsed)
        elif kind == "move":
            self._move(parsed)
        elif kind == "collect":
            self._collect(parsed)
        elif kind == "attack":
            self._attack(parsed)
        elif kind == "wait":
            self._event("action_applied", "wait", "Wait()", {"action": parsed})
        else:
            self._illegal(parsed, "unknown_action", f"unknown action kind {kind!r}")
        self._advance_world()
        return self.transition_result()

    def transition_result(self) -> dict[str, Any]:
        state = self._require_state()
        return {
            "observation": self.observation(),
            "reward": state["total_reward"],
            "terminated": state["terminated"],
            "info": {"illegal_actions": state["illegal_actions"], "nev_cursor": len(self.events)},
        }

    def observation(self) -> dict[str, Any]:
        state = self._require_state()
        structured = {
            "level": state["level"],
            "availability": state["availability"],
            "tick": state["tick"],
            "base_hp": state["base_hp"],
            "gold": state["gold"],
            "friendlies": self._visible_friendlies(),
            "towers": self._visible_towers(),
            "enemies": [self._enemy_view(enemy) for enemy in state["enemies"]],
            "coins": [copy.deepcopy(coin) for coin in state["coins"]],
            "build_slots": copy.deepcopy(self._level.get("build_slots", {})),
            "fog_cells": copy.deepcopy(self._level.get("fog_cells", [])),
            "illegal_actions": state["illegal_actions"],
            "terminated": state["terminated"],
            "termination_reason": state["termination_reason"],
        }
        return {"structured": structured, "text": json.dumps(structured, sort_keys=True, separators=(",", ":"))}

    def projection(self) -> dict[str, Any]:
        state = self._require_state()
        return {
            "state": copy.deepcopy(state),
            "events": copy.deepcopy(self.events),
            "observation": self.observation(),
        }

    def checkpoint(self) -> str:
        return json.dumps({"version": 1, "state": self._require_state(), "events": self.events}, sort_keys=True, separators=(",", ":"))

    def restore(self, checkpoint: str | dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(checkpoint) if isinstance(checkpoint, str) else copy.deepcopy(checkpoint)
        if payload.get("version") != 1:
            raise ValueError("unsupported checkpoint version")
        state = payload.get("state")
        if not isinstance(state, dict) or "level" not in state:
            raise ValueError("invalid checkpoint state")
        self._level = self._load_level(str(state["level"]))
        self.state = state
        self.events = list(payload.get("events", []))
        return self.observation()

    def _build(self, action: dict[str, Any]) -> None:
        state = self._require_state()
        tower = action.get("tower")
        slot = action.get("target")
        if tower not in TOWER_RULES:
            self._illegal(action, "unknown_tower", f"unknown tower {tower}")
            return
        if not isinstance(slot, str) or slot not in self._level["build_slots"]:
            self._illegal(action, "unknown_slot", f"unknown build slot {slot}")
            return
        if any(existing["slot"] == slot for existing in state["towers"]):
            self._illegal(action, "occupied_slot", f"build slot {slot!r} is occupied")
            return
        cost = TOWER_RULES[tower]["cost"]
        if state["gold"] < cost:
            self._illegal(action, "insufficient_gold", f"{tower} costs {cost} pickup gold")
            return
        state["gold"] -= cost
        tower_id = f"tower_{len(state['towers'])}"
        position = list(self._level["build_slots"][slot])
        state["towers"].append({"id": tower_id, "kind": tower, "slot": slot, "pos": position})
        self._event("tower_built", "build", f"TowerBuilt({tower},{slot})", {"tower": tower, "slot": slot, "gold": state["gold"]})
        if tower == "knight":
            knight_id = f"knight_{len(state['knights'])}"
            state["knights"].append({"id": knight_id, "source": tower_id, "pos": position, "hp": 3})
            self._event("knight_summoned", "summon", f"KnightSummoned({knight_id})", {"knight": knight_id, "source": tower_id, "at": position})

    def _move(self, action: dict[str, Any]) -> None:
        actor = self._actor(str(action.get("actor", "")))
        target = action.get("target")
        if actor is None:
            self._illegal(action, "unknown_actor", f"unknown friendly {action.get('actor')}")
            return
        if self._in_fog(actor["pos"]):
            self._illegal(action, "friendly_disabled_by_fog", f"{actor['id']} is disabled in fog")
            return
        if not self._valid_cell(target):
            self._illegal(action, "out_of_bounds", "move target is outside the discrete map")
            return
        if self._distance(actor["pos"], target) != 1:
            self._illegal(action, "non_adjacent_move", "friendly movement is one Manhattan cell per step")
            return
        actor["pos"] = list(target)
        self._event("friendly_moved", "move", f"FriendlyMoved({actor['id']})", {"actor": actor["id"], "to": list(target)})

    def _collect(self, action: dict[str, Any]) -> None:
        state = self._require_state()
        actor = self._actor(str(action.get("actor", "")))
        target = action.get("target")
        if actor is None:
            self._illegal(action, "unknown_actor", f"unknown friendly {action.get('actor')}")
            return
        if self._in_fog(actor["pos"]):
            self._illegal(action, "friendly_disabled_by_fog", f"{actor['id']} is disabled in fog")
            return
        if not isinstance(target, list) or actor["pos"] != target:
            self._illegal(action, "collect_not_at_target", "collect requires the friendly to stand on target")
            return
        coin = next((coin for coin in state["coins"] if coin["at"] == target), None)
        if coin is None:
            self._illegal(action, "missing_coin", "no spawned coin is present at target")
            return
        state["coins"].remove(coin)
        state["gold"] += int(coin["value"])
        self._event("coin_collected", "collect", f"CoinCollected({coin['id']})", {"coin": coin["id"], "actor": actor["id"], "value": coin["value"], "gold": state["gold"]})

    def _attack(self, action: dict[str, Any]) -> None:
        actor = self._actor(str(action.get("actor", "")))
        target_id = action.get("target")
        if actor is None:
            self._illegal(action, "unknown_actor", f"unknown friendly {action.get('actor')}")
            return
        if self._in_fog(actor["pos"]):
            self._illegal(action, "friendly_disabled_by_fog", f"{actor['id']} is disabled in fog")
            return
        enemy = next((item for item in self._require_state()["enemies"] if item["id"] == target_id), None)
        if enemy is None:
            self._illegal(action, "unknown_enemy", f"unknown enemy {target_id}")
            return
        if self._distance(actor["pos"], enemy["pos"]) > 1:
            self._illegal(action, "out_of_range", "hero and knights attack adjacent enemies only")
            return
        self._damage(enemy, 2 if actor["id"].startswith("knight_") else 1, actor["id"], "friendly_attack")

    def _advance_world(self) -> None:
        state = self._require_state()
        state["tick"] += 1
        self._spawn_due()
        for enemy in list(state["enemies"]):
            enemy["path_index"] += 1
            path = self._level["road"]
            if enemy["path_index"] >= len(path) - 1:
                state["enemies"].remove(enemy)
                state["base_hp"] -= 1
                state["total_reward"] -= 1.0
                self._event("enemy_leaked", "leak", f"EnemyLeaked({enemy['id']})", {"enemy": enemy["id"], "base_hp": state["base_hp"], "reward_delta": -1.0})
            else:
                enemy["pos"] = list(path[enemy["path_index"]])
        self._tower_phase()
        if state["base_hp"] <= 0:
            state["terminated"] = True
            state["termination_reason"] = "base_destroyed"
            self._event("terminal", "base_destroyed", "Terminal(base_destroyed)", {"base_hp": state["base_hp"]})
        elif self._waves_finished() and not state["enemies"]:
            state["terminated"] = True
            state["termination_reason"] = "waves_cleared"
            self._event("terminal", "waves_cleared", "Terminal(waves_cleared)", {"base_hp": state["base_hp"]})

    def _spawn_due(self) -> None:
        state = self._require_state()
        tick = state["tick"]
        for spec in self._level.get("coin_spawns", []):
            if spec["tick"] == tick and not any(coin["id"] == spec["id"] for coin in state["coins"]):
                state["coins"].append({"id": spec["id"], "at": list(spec["at"]), "value": spec["value"]})
                self._event("coin_spawned", "spawn", f"CoinSpawned({spec['id']})", {"coin": spec["id"], "at": spec["at"], "value": spec["value"]})
        for wave in self._level.get("waves", []):
            offset = tick - wave["spawn_tick"]
            if offset < 0 or offset % wave["spawn_every"] != 0:
                continue
            ordinal = offset // wave["spawn_every"]
            if ordinal >= wave["count"]:
                continue
            enemy_id = f"enemy_{self._spawn_sequence(wave['id'], ordinal)}"
            state["enemies"].append({"id": enemy_id, "kind": wave["kind"], "hp": wave["hp"], "path_index": 0, "pos": list(self._level["road"][0])})
            self._event("enemy_spawned", "spawn", f"EnemySpawned({enemy_id})", {"enemy": enemy_id, "kind": wave["kind"]})

    def _spawn_sequence(self, wave_id: str, ordinal: int) -> int:
        sequence = 0
        for wave in self._level.get("waves", []):
            if wave["id"] == wave_id:
                return sequence + ordinal
            sequence += int(wave["count"])
        raise ValueError(f"unknown wave {wave_id}")

    def _tower_phase(self) -> None:
        state = self._require_state()
        for tower in list(state["towers"]):
            if tower["kind"] == "knight":
                continue
            if self._in_fog(tower["pos"]):
                self._event("friendly_disabled_by_fog", "tower_disabled", f"TowerDisabledByFog({tower['id']})", {"tower": tower["id"]})
                continue
            targets = [enemy for enemy in state["enemies"] if self._distance(tower["pos"], enemy["pos"]) <= TOWER_RULES[tower["kind"]]["range"]]
            if not targets:
                continue
            targets.sort(key=lambda enemy: (enemy["path_index"], enemy["id"]), reverse=True)
            first = targets[0]
            if tower["kind"] == "archer":
                self._damage(first, TOWER_RULES["archer"]["damage"], tower["id"], "archer_attack")
            else:
                splash = [enemy for enemy in list(state["enemies"]) if self._distance(first["pos"], enemy["pos"]) <= 1]
                for enemy in splash:
                    self._damage(enemy, TOWER_RULES["magician"]["damage"], tower["id"], "magician_aoe")

    def _damage(self, enemy: dict[str, Any], damage: int, source: str, transition: str) -> None:
        state = self._require_state()
        if enemy not in state["enemies"]:
            return
        enemy["hp"] -= damage
        self._event("enemy_damaged", transition, f"EnemyDamaged({enemy['id']},{damage})", {"enemy": enemy["id"], "damage": damage, "source": source, "hp": enemy["hp"]})
        if enemy["hp"] <= 0:
            state["enemies"].remove(enemy)
            self._event("enemy_defeated", "defeat", f"EnemyDefeated({enemy['id']})", {"enemy": enemy["id"], "source": source, "gold_awarded": 0})

    def _waves_finished(self) -> bool:
        state = self._require_state()
        latest = 0
        for wave in self._level.get("waves", []):
            latest = max(latest, int(wave["spawn_tick"]) + (int(wave["count"]) - 1) * int(wave["spawn_every"]))
        return state["tick"] >= latest

    def _visible_friendlies(self) -> list[dict[str, Any]]:
        state = self._require_state()
        friendlies = [state["hero"], *state["knights"]] if state["hero"] is not None else []
        return [self._friendly_view(item) for item in friendlies]

    def _visible_towers(self) -> list[dict[str, Any]]:
        return [self._tower_view(tower) for tower in self._require_state()["towers"]]

    def _friendly_view(self, friendly: dict[str, Any]) -> dict[str, Any]:
        disabled = self._in_fog(friendly["pos"])
        return {"id": friendly["id"], "hp": friendly["hp"], "pos": None if disabled else list(friendly["pos"]), "occluded": disabled, "disabled": disabled}

    def _tower_view(self, tower: dict[str, Any]) -> dict[str, Any]:
        disabled = self._in_fog(tower["pos"])
        return {"id": tower["id"], "kind": tower["kind"], "slot": tower["slot"], "pos": None if disabled else list(tower["pos"]), "occluded": disabled, "disabled": disabled}

    @staticmethod
    def _enemy_view(enemy: dict[str, Any]) -> dict[str, Any]:
        return {"id": enemy["id"], "kind": enemy["kind"], "hp": enemy["hp"], "pos": list(enemy["pos"]), "path_index": enemy["path_index"]}

    def _actor(self, actor_id: str) -> dict[str, Any] | None:
        state = self._require_state()
        if state["hero"] is not None and actor_id == "hero":
            return state["hero"]
        return next((knight for knight in state["knights"] if knight["id"] == actor_id), None)

    def _valid_cell(self, value: Any) -> bool:
        return isinstance(value, list) and len(value) == 2 and all(isinstance(item, int) for item in value) and 0 <= value[0] < self._level["width"] and 0 <= value[1] < self._level["height"]

    def _in_fog(self, position: list[int]) -> bool:
        return position in self._level.get("fog_cells", [])

    @staticmethod
    def _distance(left: list[int], right: list[int]) -> int:
        return abs(left[0] - right[0]) + abs(left[1] - right[1])

    def _illegal(self, action: dict[str, Any], code: str, message: str) -> None:
        state = self._require_state()
        state["illegal_actions"] += 1
        self._event("illegal_action", "rejected", f"IllegalAction({code})", {"action": action, "code": code, "hallucination": True, "message": message}, severity="warning")

    def _event(self, kind: str, transition: str, message: str, payload: dict[str, Any], severity: str = "info") -> None:
        state = self.state
        tick = 0 if state is None else state["tick"]
        self.events.append({"step_index": tick, "tick": tick, "kind": kind, "transition": transition, "severity": severity, "message": message, "payload": payload})

    @staticmethod
    def _load_level(level_id: str) -> dict[str, Any]:
        filename = f"{level_id.lower()}.json" if level_id in {"L1", "L2"} else f"{level_id.lower()}_stub.json"
        path = LEVEL_DIR / filename
        if not path.exists():
            raise ValueError(f"unknown TowerMind level {level_id!r}")
        return json.loads(path.read_text())

    def _require_state(self) -> dict[str, Any]:
        if self.state is None:
            raise RuntimeError("reset must be called before using TowerMindEnv")
        return self.state


def run_scenario(document: dict[str, Any]) -> dict[str, Any]:
    """Run a pinned action tape and return the canonical fixture projection."""

    env = TowerMindEnv()
    env.reset(str(document["level"]), seed=int(document.get("seed", 0)), initial_gold=int(document.get("initial_gold", 0)))
    for action in document.get("actions", []):
        if env._require_state()["terminated"]:
            break
        env.step(action)
    return {"scenario": document["id"], "projection": env.projection(), "checkpoint": env.checkpoint()}
