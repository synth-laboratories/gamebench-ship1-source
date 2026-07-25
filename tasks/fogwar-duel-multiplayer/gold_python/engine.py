"""Independent, symbolic Fog Duel Lite authority.

The engine intentionally owns its board, fog, combat, NEV, and checkpoint
semantics.  It does not import or execute the private Age of LLM engine.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from .scenarios import load_scenario

AGENTS = ("agent_0", "agent_1")
BASE_POSITIONS = {"agent_0": [1, 3], "agent_1": [11, 3]}
UNIT_SPECS = {
    "drone": {"cost": 2, "move": 3, "detect": 3, "range": 0, "layer": "air"},
    "sam": {"cost": 3, "move": 2, "detect": 2, "range": 2, "layer": "ground"},
    "tank": {"cost": 4, "move": 2, "detect": 1, "range": 2, "layer": "ground"},
    "fighter": {"cost": 4, "move": 3, "detect": 2, "range": 2, "layer": "air"},
}
BUILDING_SPECS = {
    "base": {"hp": 4, "detect": 2},
    "credit_mine": {"hp": 2, "detect": 1, "cost": 2},
    "uranium_mine": {"hp": 2, "detect": 1, "cost": 2},
    "silo": {"hp": 3, "detect": 1, "cost": 5},
}
ATTACKS = {
    "fighter": {"tank", "drone", "fighter"},
    "sam": {"drone", "fighter"},
    "tank": {"tank", "sam"},
}


def _distance(left: list[int], right: list[int]) -> int:
    return max(abs(left[0] - right[0]), abs(left[1] - right[1]))


def _line_between(start: list[int], end: list[int]) -> list[list[int]]:
    """Inclusive grid line whose interior cells are enough for short-range LOS."""
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    if steps <= 1:
        return []
    return [[round(start[0] + (end[0] - start[0]) * index / steps), round(start[1] + (end[1] - start[1]) * index / steps)] for index in range(1, steps)]


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


class FogDuelEnv:
    """One-active-agent-at-a-time environment with fixed agent_0 -> agent_1 rounds."""

    ENV_FAMILY = "fogwar-duel"

    def __init__(self) -> None:
        self.state: dict[str, Any] | None = None
        self.events: list[dict[str, Any]] = []
        self.next_event_sequence = 0

    def reset(self, scenario_id: str) -> dict[str, Any]:
        scenario = load_scenario(scenario_id)
        passages = scenario["passages"]
        mountains = [[6, row] for row in range(7) if [6, row] not in passages]
        players = {
            agent: {
                "credits": 5,
                "uranium": 0,
                "enemy_base_discovered": False,
                "known_enemy_base_pos": None,
                "remembered_enemy_buildings": [],
                "remembered_enemy_deposits": [],
                "last_turn_results": [],
                "score": 0.0,
            }
            for agent in AGENTS
        }
        for agent, override in scenario.get("initial", {}).get("players", {}).items():
            players[agent].update(copy.deepcopy(override))
        buildings = [
            {"id": f"{agent}_base", "owner": agent, "kind": "base", "pos": BASE_POSITIONS[agent][:], "hp": 4, "under_construction": False, "ready_round": 1}
            for agent in AGENTS
        ]
        for supplied in scenario.get("initial", {}).get("buildings", []):
            building = copy.deepcopy(supplied)
            existing = next((item for item in buildings if item["id"] == building["id"]), None)
            if existing is not None:
                existing.update(building)
                continue
            building.setdefault("owner", "agent_0")
            building.setdefault("kind", "silo")
            building.setdefault("pos", [3, 3])
            building.setdefault("hp", BUILDING_SPECS[building["kind"]]["hp"])
            building.setdefault("under_construction", False)
            building.setdefault("ready_round", 1)
            buildings.append(building)
        self.state = {
            "schema_version": "gamebench.fog_duel_lite.state.v0",
            "scenario_id": scenario["id"],
            "seed": scenario["seed"],
            "max_rounds": scenario.get("max_rounds", 80),
            "round": 1,
            "active_agent": "agent_0",
            "half_turn": 0,
            "board": {"size": [13, 7], "mountains": mountains, "passages": copy.deepcopy(passages), "deposits": copy.deepcopy(scenario["deposits"])},
            "players": players,
            "units": copy.deepcopy(scenario.get("initial", {}).get("units", [])),
            "buildings": buildings,
            "diplomacy": {"ceasefire_remaining": 0, "pending": [], "next_proposal_id": 1},
            "queued_launches": [],
            "action_flags": {},
            "next_entity_id": 1,
            "terminal": None,
            "rng_state": scenario["seed"],
        }
        self.events = []
        self.next_event_sequence = 0
        self._emit("match_started", None, {"scenario_id": scenario_id, "seed": scenario["seed"]})
        self._begin_half_turn("agent_0")
        return self.observe()

    def step(self, request: dict[str, Any]) -> dict[str, Any]:
        state = self._require_state()
        if state["terminal"] is not None:
            self._emit("illegal_action", state["active_agent"], {"action_index": None, "submitted_kind": "step", "reason_code": "terminal"})
            return self.snapshot()
        actor = state["active_agent"]
        actions = request.get("actions", []) if isinstance(request, dict) else []
        if not isinstance(actions, list):
            self._illegal(actor, None, {"kind": "invalid"}, "actions_not_array")
            actions = []
        for index, action in enumerate(actions):
            if index >= 3:
                self._illegal(actor, index, action, "action_limit")
                continue
            if state["terminal"] is not None:
                break
            self._apply_action(actor, index, action)
        if state["terminal"] is None and isinstance(request, dict) and request.get("diplomacy") is not None:
            self._apply_diplomacy(actor, request["diplomacy"])
        self._emit("half_turn_completed", actor, {"actions_submitted": len(actions)})
        if state["terminal"] is None:
            if actor == "agent_0":
                state["half_turn"] = 1
                self._begin_half_turn("agent_1")
            else:
                self._resolve_round()
        return self.snapshot()

    def observe(self, agent: str | None = None) -> dict[str, Any]:
        state = self._require_state()
        agent = agent or state["active_agent"]
        visible = self._visible_cells(agent)
        enemy = self._other(agent)
        units = [copy.deepcopy(item) for item in state["units"] if item["owner"] == agent or tuple(item["pos"]) in visible]
        buildings = [copy.deepcopy(item) for item in state["buildings"] if item["owner"] == agent or tuple(item["pos"]) in visible]
        return _canonical({
            "schema_version": "gamebench.fog_duel_lite.observation.v0",
            "you": agent,
            "round": state["round"],
            "you_play_first": agent == "agent_0",
            "active_agent": state["active_agent"],
            "actions_remaining": 3,
            "visible_cells": [list(cell) for cell in sorted(visible)],
            "visible_units": sorted(units, key=lambda item: item["id"]),
            "visible_buildings": sorted(buildings, key=lambda item: item["id"]),
            "remembered_enemy_buildings": copy.deepcopy(state["players"][agent]["remembered_enemy_buildings"]),
            "remembered_enemy_deposits": copy.deepcopy(state["players"][agent]["remembered_enemy_deposits"]),
            "own_resources": {"credits": state["players"][agent]["credits"], "uranium": state["players"][agent]["uranium"]},
            "enemy_base_discovered": state["players"][agent]["enemy_base_discovered"],
            "enemy_base_position": state["players"][agent]["known_enemy_base_pos"],
            "diplomacy": self._diplomacy_for(agent),
            "last_turn_results": copy.deepcopy(state["players"][agent]["last_turn_results"]),
            "terminal": copy.deepcopy(state["terminal"]),
            "enemy_uranium": None,
            "enemy": enemy,
        })

    def snapshot(self) -> dict[str, Any]:
        return _canonical({"observation": self.observe(), "state": self.state_projection(), "nev": copy.deepcopy(self.events)})

    def state_projection(self) -> dict[str, Any]:
        return _canonical(self._require_state())

    def checkpoint(self) -> dict[str, Any]:
        return _canonical({
            "schema_version": "gamebench.fog_duel_lite.checkpoint.v0",
            "state": self._require_state(),
            "events": self.events,
            "next_event_sequence": self.next_event_sequence,
        })

    def restore(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if checkpoint.get("schema_version") != "gamebench.fog_duel_lite.checkpoint.v0":
            raise ValueError("unsupported Fog Duel checkpoint")
        self.state = copy.deepcopy(checkpoint["state"])
        self.events = copy.deepcopy(checkpoint["events"])
        self.next_event_sequence = int(checkpoint["next_event_sequence"])
        return self.observe()

    def _require_state(self) -> dict[str, Any]:
        if self.state is None:
            raise RuntimeError("reset must be called before using FogDuelEnv")
        return self.state

    def _other(self, agent: str) -> str:
        return "agent_1" if agent == "agent_0" else "agent_0"

    def _emit(self, kind: str, actor: str | None, payload: dict[str, Any]) -> None:
        state = self._require_state()
        self.events.append({"schema_version": "gamebench.nev.v1", "seq": self.next_event_sequence, "round": state["round"], "half_turn": state["half_turn"], "actor": actor, "kind": kind, "payload": _canonical(payload)})
        self.next_event_sequence += 1

    def _begin_half_turn(self, actor: str) -> None:
        state = self._require_state()
        state["active_agent"] = actor
        state["action_flags"] = {}
        for building in state["buildings"]:
            if building["owner"] == actor and building["under_construction"] and building["ready_round"] <= state["round"]:
                building["under_construction"] = False
                self._emit("building_completed", actor, {"building_id": building["id"]})
        self._emit("half_turn_started", actor, {"order": state["half_turn"]})

    def _apply_action(self, actor: str, index: int, action: Any) -> None:
        if not isinstance(action, dict) or not isinstance(action.get("kind"), str):
            self._illegal(actor, index, action, "invalid_schema")
            return
        kind = action["kind"]
        handlers = {
            "produce": self._produce,
            "move": self._move,
            "attack": self._attack,
            "build": self._build,
            "launch": self._launch,
            "wait": self._wait,
        }
        handler = handlers.get(kind)
        if handler is None:
            self._illegal(actor, index, action, "unknown_action")
            return
        handler(actor, index, action)

    def _wait(self, actor: str, index: int, action: dict[str, Any]) -> None:
        self._accepted(actor, index, action, "wait", {})

    def _produce(self, actor: str, index: int, action: dict[str, Any]) -> None:
        state = self._require_state()
        unit_kind = action.get("unit")
        if unit_kind not in UNIT_SPECS:
            self._illegal(actor, index, action, "unknown_unit")
            return
        cost = UNIT_SPECS[unit_kind]["cost"]
        if state["players"][actor]["credits"] < cost:
            self._illegal(actor, index, action, "insufficient_credits")
            return
        candidates = self._spawn_cells(actor, UNIT_SPECS[unit_kind]["layer"])
        if not candidates:
            self._illegal(actor, index, action, "base_spawn_blocked")
            return
        state["players"][actor]["credits"] -= cost
        entity_id = f"{actor}_{unit_kind}_{state['next_entity_id']}"
        state["next_entity_id"] += 1
        unit = {"id": entity_id, "owner": actor, "kind": unit_kind, "pos": candidates[0]}
        state["units"].append(unit)
        self._accepted(actor, index, action, "produce", {"unit": unit})
        self._emit("unit_produced", actor, {"unit": unit})

    def _move(self, actor: str, index: int, action: dict[str, Any]) -> None:
        state = self._require_state()
        unit = self._owned_unit(actor, action.get("unit_id"))
        destination = action.get("to")
        if unit is None:
            self._illegal(actor, index, action, "unit_not_found")
            return
        if unit["id"] in state["action_flags"].get("moved", []):
            self._illegal(actor, index, action, "unit_already_moved")
            return
        if not self._valid_position(destination) or _distance(unit["pos"], destination) > UNIT_SPECS[unit["kind"]]["move"]:
            self._illegal(actor, index, action, "move_out_of_range")
            return
        layer = UNIT_SPECS[unit["kind"]]["layer"]
        if not self._cell_open(destination, layer, unit["id"]) or (layer == "ground" and not self._ground_path_clear(unit["pos"], destination)):
            self._illegal(actor, index, action, "move_blocked")
            return
        before = unit["pos"][:]
        unit["pos"] = destination[:]
        state["action_flags"].setdefault("moved", []).append(unit["id"])
        self._accepted(actor, index, action, "move", {"unit_id": unit["id"], "from": before, "to": destination})
        self._emit("unit_moved", actor, {"unit_id": unit["id"], "from": before, "to": destination})

    def _attack(self, actor: str, index: int, action: dict[str, Any]) -> None:
        state = self._require_state()
        unit = self._owned_unit(actor, action.get("unit_id"))
        target_pos = action.get("target_pos")
        if unit is None:
            self._illegal(actor, index, action, "unit_not_found")
            return
        if unit["id"] in state["action_flags"].get("attacked", []):
            self._illegal(actor, index, action, "unit_already_attacked")
            return
        if state["diplomacy"]["ceasefire_remaining"] > 0:
            self._illegal(actor, index, action, "ceasefire_active")
            return
        if unit["kind"] == "drone" or not self._valid_position(target_pos) or _distance(unit["pos"], target_pos) > UNIT_SPECS[unit["kind"]]["range"]:
            self._illegal(actor, index, action, "attack_out_of_range")
            return
        if tuple(target_pos) not in self._visible_cells(actor):
            self._illegal(actor, index, action, "target_not_visible")
            return
        if unit["kind"] != "fighter" and not self._ground_path_clear(unit["pos"], target_pos, include_buildings=True):
            self._illegal(actor, index, action, "line_of_sight_blocked")
            return
        target_unit = next((item for item in state["units"] if item["owner"] != actor and item["pos"] == target_pos), None)
        target_building = next((item for item in state["buildings"] if item["owner"] != actor and item["pos"] == target_pos), None)
        destroyed_building: dict[str, Any] | None = None
        if target_unit is not None and target_unit["kind"] in ATTACKS.get(unit["kind"], set()):
            state["units"].remove(target_unit)
            payload = {"attacker": unit["id"], "target": target_unit["id"], "target_kind": target_unit["kind"], "outcome": "destroyed"}
        elif target_building is not None and unit["kind"] == "tank":
            target_building["hp"] -= 2
            destroyed = target_building["hp"] <= 0
            payload = {"attacker": unit["id"], "target": target_building["id"], "target_kind": target_building["kind"], "damage": 2, "destroyed": destroyed}
            if destroyed:
                destroyed_building = target_building
        else:
            self._illegal(actor, index, action, "no_legal_target")
            return
        state["action_flags"].setdefault("attacked", []).append(unit["id"])
        self._accepted(actor, index, action, "attack", payload)
        self._emit("combat_resolved", actor, payload)
        if destroyed_building is not None:
            self._destroy_building(destroyed_building, actor)

    def _build(self, actor: str, index: int, action: dict[str, Any]) -> None:
        state = self._require_state()
        building_kind = action.get("building")
        position = action.get("pos")
        if building_kind not in {"credit_mine", "uranium_mine", "silo"} or not self._valid_position(position):
            self._illegal(actor, index, action, "invalid_build")
            return
        if tuple(position) not in self._visible_cells(actor):
            self._illegal(actor, index, action, "cell_not_visible")
            return
        if any(item["pos"] == position for item in state["buildings"]) or any(item["pos"] == position and UNIT_SPECS[item["kind"]]["layer"] == "ground" for item in state["units"]):
            self._illegal(actor, index, action, "cell_occupied")
            return
        if position in state["board"]["mountains"] or any(_distance(position, base) <= 1 for base in BASE_POSITIONS.values()):
            self._illegal(actor, index, action, "invalid_build_cell")
            return
        deposit = next((item for item in state["board"]["deposits"] if item["pos"] == position and item["reserve"] > 0), None)
        if building_kind == "credit_mine" and (deposit is None or deposit["kind"] != "credit"):
            self._illegal(actor, index, action, "credit_deposit_required")
            return
        if building_kind == "uranium_mine" and (deposit is None or deposit["kind"] != "uranium"):
            self._illegal(actor, index, action, "uranium_deposit_required")
            return
        if building_kind == "silo" and (deposit is not None or not self._in_own_territory(actor, position)):
            self._illegal(actor, index, action, "invalid_silo_position")
            return
        cost = BUILDING_SPECS[building_kind]["cost"]
        if state["players"][actor]["credits"] < cost:
            self._illegal(actor, index, action, "insufficient_credits")
            return
        state["players"][actor]["credits"] -= cost
        building = {"id": f"{actor}_{building_kind}_{state['next_entity_id']}", "owner": actor, "kind": building_kind, "pos": position[:], "hp": BUILDING_SPECS[building_kind]["hp"], "under_construction": True, "ready_round": state["round"] + 1}
        state["next_entity_id"] += 1
        state["buildings"].append(building)
        self._accepted(actor, index, action, "build", {"building": building})
        self._emit("building_built", actor, {"building": building})

    def _launch(self, actor: str, index: int, action: dict[str, Any]) -> None:
        state = self._require_state()
        player = state["players"][actor]
        silo = next((item for item in state["buildings"] if item["owner"] == actor and item["kind"] == "silo" and not item["under_construction"]), None)
        if silo is None:
            self._illegal(actor, index, action, "no_operational_silo")
            return
        if not player["enemy_base_discovered"]:
            self._illegal(actor, index, action, "enemy_base_unknown")
            return
        cost = self._bomb_cost()
        if player["uranium"] < cost:
            self._illegal(actor, index, action, "insufficient_uranium")
            return
        if actor in state["queued_launches"]:
            self._illegal(actor, index, action, "already_launched")
            return
        player["uranium"] -= cost
        state["queued_launches"].append(actor)
        self._accepted(actor, index, action, "launch", {"bomb_cost": cost})
        self._emit("launch_queued", actor, {"bomb_cost": cost})

    def _accepted(self, actor: str, index: int, action: dict[str, Any], transition: str, payload: dict[str, Any]) -> None:
        self._emit("action_applied", actor, {"action_index": index, "action": action, "transition": transition, **payload})
        self._require_state()["players"][actor]["last_turn_results"].append({"action_index": index, "ok": True, "transition": transition})

    def _illegal(self, actor: str, index: int | None, action: Any, reason_code: str) -> None:
        kind = action.get("kind") if isinstance(action, dict) else "invalid"
        self._emit("illegal_action", actor, {"action_index": index, "submitted_kind": kind, "reason_code": reason_code})
        self._require_state()["players"][actor]["last_turn_results"].append({"action_index": index, "ok": False, "reason_code": reason_code})

    def _apply_diplomacy(self, actor: str, diplomacy: Any) -> None:
        state = self._require_state()
        if not isinstance(diplomacy, dict):
            self._illegal(actor, None, {"kind": "diplomacy"}, "invalid_diplomacy_schema")
            return
        proposal = diplomacy.get("proposal")
        if proposal is not None:
            if not isinstance(proposal, dict) or proposal.get("kind") not in {"ceasefire", "peace", "ultimatum"}:
                self._illegal(actor, None, {"kind": "diplomacy"}, "unknown_proposal")
            else:
                kind = proposal["kind"]
                min_round = 15 if kind == "peace" else 10
                target_round = proposal.get("target_round")
                if state["round"] < min_round or (kind == "ultimatum" and (not isinstance(target_round, int) or not state["round"] + 1 <= target_round <= state["round"] + 3)):
                    self._illegal(actor, None, {"kind": "diplomacy"}, "proposal_unavailable")
                else:
                    proposal_id = f"p_{state['diplomacy']['next_proposal_id']}"
                    state["diplomacy"]["next_proposal_id"] += 1
                    item = {"proposal_id": proposal_id, "from": actor, "to": self._other(actor), "kind": kind, "target_round": target_round}
                    state["diplomacy"]["pending"].append(item)
                    self._emit("diplomacy_proposed", actor, item)
        for response in diplomacy.get("responses", []):
            proposal_id = response.get("proposal_id") if isinstance(response, dict) else None
            pending = next((item for item in state["diplomacy"]["pending"] if item["proposal_id"] == proposal_id and item["to"] == actor), None)
            if pending is None or not isinstance(response.get("accept") if isinstance(response, dict) else None, bool):
                self._illegal(actor, None, {"kind": "diplomacy"}, "proposal_not_pending")
                continue
            state["diplomacy"]["pending"].remove(pending)
            accepted = response["accept"]
            self._emit("diplomacy_resolved", actor, {"proposal_id": proposal_id, "accepted": accepted})
            if not accepted:
                continue
            if pending["kind"] == "ceasefire":
                state["diplomacy"]["ceasefire_remaining"] = 3
            elif pending["kind"] == "peace":
                self._terminal("peace", None, {"agent_0": 1.0, "agent_1": 1.0})
            else:
                self._terminal("ultimatum", pending["from"], {pending["from"]: 3.0, actor: 0.5})

    def _resolve_round(self) -> None:
        state = self._require_state()
        queued = set(state["queued_launches"])
        if len(queued) == 2:
            self._emit("launch_resolved", None, {"launchers": sorted(queued), "outcome": "mutual_destruction"})
            self._terminal("mutual_destruction", None, {"agent_0": 0.0, "agent_1": 0.0})
            return
        if len(queued) == 1:
            winner = next(iter(queued))
            self._emit("launch_resolved", winner, {"launchers": [winner], "outcome": "nuclear"})
            self._terminal("nuclear", winner, {winner: 3.0, self._other(winner): 0.0})
            return
        state["queued_launches"] = []
        self._update_memories()
        self._collect_income()
        if state["diplomacy"]["ceasefire_remaining"] > 0:
            state["diplomacy"]["ceasefire_remaining"] -= 1
        if state["round"] >= state["max_rounds"]:
            self._terminal("timeout", None, {"agent_0": 1.0, "agent_1": 1.0})
            return
        state["round"] += 1
        state["half_turn"] = 0
        self._begin_half_turn("agent_0")

    def _collect_income(self) -> None:
        state = self._require_state()
        deltas = {agent: {"credits": 1, "uranium": 0} for agent in AGENTS}
        for building in state["buildings"]:
            if building["under_construction"] or building["kind"] not in {"credit_mine", "uranium_mine"}:
                continue
            deposit = next((item for item in state["board"]["deposits"] if item["pos"] == building["pos"] and item["reserve"] > 0), None)
            if deposit is None:
                continue
            deposit["reserve"] -= 1
            resource = "credits" if building["kind"] == "credit_mine" else "uranium"
            deltas[building["owner"]][resource] += 3 if resource == "credits" else 1
        for agent, delta in deltas.items():
            state["players"][agent]["credits"] += delta["credits"]
            state["players"][agent]["uranium"] += delta["uranium"]
            self._emit("income_collected", agent, delta)

    def _update_memories(self) -> None:
        state = self._require_state()
        for agent in AGENTS:
            enemy = self._other(agent)
            visible = self._visible_cells(agent)
            buildings = {tuple(item["pos"]): {"kind": item["kind"], "pos": item["pos"][:], "last_seen_turn": state["round"]} for item in state["buildings"] if item["owner"] == enemy and tuple(item["pos"]) in visible}
            previous = {tuple(item["pos"]): item for item in state["players"][agent]["remembered_enemy_buildings"]}
            previous.update(buildings)
            state["players"][agent]["remembered_enemy_buildings"] = [previous[key] for key in sorted(previous)]
            deposits = {tuple(item["pos"]): {"kind": item["kind"], "pos": item["pos"][:], "reserve": item["reserve"], "last_seen_turn": state["round"]} for item in state["board"]["deposits"] if tuple(item["pos"]) in visible and self._in_own_territory(enemy, item["pos"])}
            prior_deposits = {tuple(item["pos"]): item for item in state["players"][agent]["remembered_enemy_deposits"]}
            prior_deposits.update(deposits)
            state["players"][agent]["remembered_enemy_deposits"] = [prior_deposits[key] for key in sorted(prior_deposits)]
            enemy_base = next(item for item in state["buildings"] if item["owner"] == enemy and item["kind"] == "base")
            if tuple(enemy_base["pos"]) in visible:
                state["players"][agent]["enemy_base_discovered"] = True
                state["players"][agent]["known_enemy_base_pos"] = enemy_base["pos"][:]
            self._emit("fog_memory_updated", agent, {"visible_cell_count": len(visible), "remembered_buildings": len(previous)})

    def _terminal(self, reason: str, winner: str | None, scores: dict[str, float]) -> None:
        state = self._require_state()
        if state["terminal"] is not None:
            return
        normalized = {agent: float(scores.get(agent, 0.0)) for agent in AGENTS}
        for agent, score in normalized.items():
            state["players"][agent]["score"] = score
        state["terminal"] = {"reason": reason, "winner": winner, "scores": normalized}
        self._emit("terminal", winner, state["terminal"])

    def _destroy_building(self, building: dict[str, Any], actor: str) -> None:
        state = self._require_state()
        state["buildings"].remove(building)
        for agent in AGENTS:
            state["players"][agent]["remembered_enemy_buildings"] = [item for item in state["players"][agent]["remembered_enemy_buildings"] if item["pos"] != building["pos"]]
        self._emit("building_destroyed", actor, {"building_id": building["id"], "kind": building["kind"]})
        if building["kind"] == "base":
            self._terminal("military", actor, {actor: 3.0, self._other(actor): 0.0})

    def _visible_cells(self, agent: str) -> set[tuple[int, int]]:
        state = self._require_state()
        sources: list[tuple[list[int], int]] = []
        for unit in state["units"]:
            if unit["owner"] == agent:
                sources.append((unit["pos"], UNIT_SPECS[unit["kind"]]["detect"]))
        for building in state["buildings"]:
            if building["owner"] == agent:
                sources.append((building["pos"], BUILDING_SPECS[building["kind"]]["detect"]))
        visible: set[tuple[int, int]] = set()
        for source, radius in sources:
            for x in range(max(0, source[0] - radius), min(13, source[0] + radius + 1)):
                for y in range(max(0, source[1] - radius), min(7, source[1] + radius + 1)):
                    visible.add((x, y))
        return visible

    def _owned_unit(self, actor: str, unit_id: Any) -> dict[str, Any] | None:
        return next((item for item in self._require_state()["units"] if item["owner"] == actor and item["id"] == unit_id), None)

    def _valid_position(self, value: Any) -> bool:
        return isinstance(value, list) and len(value) == 2 and all(isinstance(item, int) for item in value) and 0 <= value[0] < 13 and 0 <= value[1] < 7

    def _in_own_territory(self, agent: str, position: list[int]) -> bool:
        return position[0] <= 5 if agent == "agent_0" else position[0] >= 7

    def _cell_open(self, position: list[int], layer: str, ignored_id: str | None = None) -> bool:
        state = self._require_state()
        if layer == "ground" and position in state["board"]["mountains"]:
            return False
        if layer == "ground" and any(item["pos"] == position for item in state["buildings"]):
            return False
        return not any(item["id"] != ignored_id and item["pos"] == position and UNIT_SPECS[item["kind"]]["layer"] == layer for item in state["units"])

    def _ground_path_clear(self, start: list[int], end: list[int], include_buildings: bool = True) -> bool:
        state = self._require_state()
        for cell in _line_between(start, end):
            if cell in state["board"]["mountains"]:
                return False
            if include_buildings and any(item["pos"] == cell for item in state["buildings"]):
                return False
        return True

    def _spawn_cells(self, actor: str, layer: str) -> list[list[int]]:
        base = BASE_POSITIONS[actor]
        candidates = [[base[0] + dx, base[1] + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
        return [item for item in sorted(candidates) if self._valid_position(item) and self._cell_open(item, layer)]

    def _bomb_cost(self) -> int:
        state = self._require_state()
        reduction = 0 if state["round"] < 40 else 2 * (1 + (state["round"] - 40) // 10)
        cost = max(13, 25 - reduction)
        return cost + (6 if state["diplomacy"]["ceasefire_remaining"] > 0 else 0)

    def _diplomacy_for(self, agent: str) -> dict[str, Any]:
        state = self._require_state()
        return {"ceasefire_remaining": state["diplomacy"]["ceasefire_remaining"], "pending": [copy.deepcopy(item) for item in state["diplomacy"]["pending"] if item["to"] == agent]}


def execute_tape(scenario_id: str, tape: list[dict[str, Any]]) -> dict[str, Any]:
    env = FogDuelEnv()
    env.reset(scenario_id)
    checkpoints: list[dict[str, Any]] = [env.checkpoint()]
    for request in tape:
        env.step(request)
        checkpoints.append(env.checkpoint())
        if env.state_projection()["terminal"] is not None:
            break
    return _canonical({"scenario_id": scenario_id, "state": env.state_projection(), "events": env.events, "checkpoints": checkpoints, "observation": env.observe()})
