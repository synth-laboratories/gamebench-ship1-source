from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


DIRS = {
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
}


def load_scenario(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _episode_id(scenario: dict[str, Any]) -> str:
    hasher = hashlib.sha256()
    for key in ("task_id", "scenario_id", "quest_id", "seed"):
        hasher.update(str(scenario[key]).encode("utf-8"))
    return f"dg-{hasher.hexdigest()[:16]}"


class DungeonGridSession:
    def __init__(self, scenario: dict[str, Any]):
        self.scenario = copy.deepcopy(scenario)
        self.episode_id = _episode_id(self.scenario)
        self.width = 0
        self.height = 0
        self.terrain: dict[tuple[int, int], str] = {}
        self.doors: dict[str, dict[str, Any]] = {}
        self.traps: dict[str, dict[str, Any]] = {}
        self.chests: dict[str, dict[str, Any]] = {}
        self.monsters: dict[str, dict[str, Any]] = {}
        self.heroes: dict[str, dict[str, Any]] = {}
        self.message_inboxes: dict[str, list[dict[str, Any]]] = {}
        self.turn_order: list[str] = []
        self.turn_cursor = 0
        self.active_agent = "agent_0"
        self.step_index = 0
        self.turn_index = 1
        self.reward_last = 0.0
        self.total_reward = 0.0
        self.done = False
        self.success = False
        self.terminal_reason: str | None = None
        self.achievements: set[str] = set()
        self.event_log: list[dict[str, Any]] = []
        self._reset_from_scenario()

    @classmethod
    def reset(cls, scenario: dict[str, Any]) -> "DungeonGridSession":
        return cls(scenario)

    def reset_to_initial(self) -> None:
        scenario = copy.deepcopy(self.scenario)
        self.__init__(scenario)

    @classmethod
    def restore_from_checkpoint(cls, checkpoint: dict[str, Any]) -> "DungeonGridSession":
        if checkpoint.get("schema") != "gamebench.dungeongrid.checkpoint.v1":
            raise ValueError("checkpoint schema must be gamebench.dungeongrid.checkpoint.v1")
        session = cls(checkpoint["scenario"])
        dynamic = checkpoint["dynamic"]
        for name in (
            "heroes",
            "doors",
            "traps",
            "chests",
            "monsters",
            "active_agent",
            "turn_order",
            "turn_cursor",
            "reward_last",
            "total_reward",
            "done",
            "success",
            "terminal_reason",
            "event_log",
        ):
            setattr(session, name, copy.deepcopy(dynamic[name]))
        session.message_inboxes = copy.deepcopy(
            dynamic.get("message_inboxes", {agent_id: [] for agent_id in session.heroes})
        )
        session.step_index = int(checkpoint["step_index"])
        session.turn_index = int(checkpoint["turn_index"])
        session.achievements = set(dynamic["achievements"])
        session._event("checkpoint_restored", "info", f"CheckpointRestored(step={session.step_index})")
        return session

    def _reset_from_scenario(self) -> None:
        lines = self.scenario["map_ascii"].splitlines()
        self.height = len(lines)
        self.width = len(lines[0])
        entry: tuple[int, int] | None = None
        counts = {"door": 0, "trap": 0, "chest": 0, "monster": 0}
        for y, line in enumerate(lines):
            if len(line) != self.width:
                raise ValueError("map_ascii must be rectangular")
            for x, glyph in enumerate(line):
                pos = (x, y)
                if glyph == "#":
                    self.terrain[pos] = "wall"
                elif glyph == "E":
                    self.terrain[pos] = "escape"
                    entry = pos
                elif glyph == "I":
                    self.terrain[pos] = "objective"
                elif glyph == "D":
                    self.terrain[pos] = "floor"
                    counts["door"] += 1
                    door_id = f"door_{counts['door']}"
                    self.doors[door_id] = {
                        "id": door_id,
                        "pos": {"x": x, "y": y},
                        "open": False,
                        "secret": False,
                        "discovered": True,
                    }
                elif glyph == "T":
                    self.terrain[pos] = "floor"
                    counts["trap"] += 1
                    trap_id = f"trap_{counts['trap']}"
                    self.traps[trap_id] = {
                        "id": trap_id,
                        "pos": {"x": x, "y": y},
                        "revealed": False,
                        "armed": True,
                        "damage": 1,
                    }
                elif glyph == "C":
                    self.terrain[pos] = "floor"
                    counts["chest"] += 1
                    chest_id = f"chest_{counts['chest']}"
                    self.chests[chest_id] = {
                        "id": chest_id,
                        "pos": {"x": x, "y": y},
                        "opened": False,
                        "contents": ["coin_cache", "healing_draught"],
                    }
                elif glyph == "R":
                    self.terrain[pos] = "floor"
                    counts["monster"] += 1
                    monster_id = f"crypt_brute_{counts['monster']}"
                    self.monsters[monster_id] = {
                        "id": monster_id,
                        "role": "crypt_brute",
                        "pos": {"x": x, "y": y},
                        "hp": 4,
                        "max_hp": 4,
                        "attack": 2,
                        "guard": 1,
                        "awake": False,
                        "statuses": [],
                    }
                elif glyph == ".":
                    self.terrain[pos] = "floor"
                else:
                    raise ValueError(f"unsupported map glyph {glyph!r} at {x},{y}")
        if entry is None:
            raise ValueError("map must include E entry/escape tile")
        for idx, role in enumerate(self.scenario["hero_roles"]):
            agent_id = f"agent_{idx}"
            self.turn_order.append(agent_id)
            self.heroes[agent_id] = {
                "agent_id": agent_id,
                "role": role,
                "pos": {"x": entry[0], "y": entry[1]},
                "hp": 6,
                "max_hp": 6,
                "ap": 2,
                "max_ap": 2,
                "inventory": _starting_inventory(role),
                "guarded": False,
                "messages_sent": 0,
            }
            self.message_inboxes[agent_id] = []
        self.active_agent = self.turn_order[0]
        self._event("episode_reset", "info", f"EpisodeReset({self.scenario['quest_id']},{self.episode_id})")
        self._event("turn_started", "info", f"TurnStarted({self.active_agent})")

    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        if self.done:
            self._reject(action, "terminal", {})
            return self._result(False)
        before = self._transition_snapshot()
        self.reward_last = 0.0
        cost = _action_cost(action)
        hero = self.heroes[self.active_agent]
        if hero["ap"] < cost:
            self._reject(action, "insufficient_ap", {"required": cost, "available": hero["ap"]})
            return self._result(False)
        applied = self._apply(action)
        if applied and cost:
            hero["ap"] = max(0, hero["ap"] - cost)
        if applied and action["type"] != "end_turn":
            self.step_index += 1
            self._check_trap()
            self._check_terminal()
        if applied and self.reward_last:
            self.total_reward += self.reward_last
            self._event("reward", "info", f"Reward({self.reward_last:.2f},total={self.total_reward:.2f})")
        if applied:
            self._event(
                "state_updated",
                "debug",
                f"StateUpdated(step={self.step_index})",
                action=action,
                transition={"before": before, "after": self._transition_snapshot()},
            )
        return self._result(applied)

    def rich_state(self) -> dict[str, Any]:
        return {
            "schema": "gamebench.dungeongrid.state.v1",
            "episode_id": self.episode_id,
            "task_id": self.scenario["task_id"],
            "scenario_id": self.scenario["scenario_id"],
            "quest_id": self.scenario["quest_id"],
            "title": self.scenario["title"],
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "active_agent": self.active_agent,
            "turn_order": self.turn_order,
            "done": self.done,
            "success": self.success,
            "terminal_reason": self.terminal_reason,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "achievements": sorted(self.achievements),
            "metadata": self.scenario.get("metadata", {}),
            "map": {
                "width": self.width,
                "height": self.height,
                "ascii": self._render_ascii(),
                "terrain": [
                    {"x": x, "y": y, "terrain": terrain}
                    for (x, y), terrain in sorted(self.terrain.items())
                ],
            },
            "heroes": self.heroes,
            "message_inboxes": self.message_inboxes,
            "doors": self.doors,
            "traps": self.traps,
            "chests": self.chests,
            "monsters": self.monsters,
            "objective": self._objective_state(),
            "legal_actions": self._legal_actions(),
            "coordination": self._coordination_state(),
            "event_log_tail": self.event_log[-12:],
        }

    def state_digest(self) -> str:
        state = copy.deepcopy(self.rich_state())
        state.pop("event_log_tail", None)
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def checkpoint_json(self) -> dict[str, Any]:
        return {
            "schema": "gamebench.dungeongrid.checkpoint.v1",
            "episode_id": self.episode_id,
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "scenario": copy.deepcopy(self.scenario),
            "dynamic": {
                "heroes": copy.deepcopy(self.heroes),
                "message_inboxes": copy.deepcopy(self.message_inboxes),
                "doors": copy.deepcopy(self.doors),
                "traps": copy.deepcopy(self.traps),
                "chests": copy.deepcopy(self.chests),
                "monsters": copy.deepcopy(self.monsters),
                "active_agent": self.active_agent,
                "turn_order": copy.deepcopy(self.turn_order),
                "turn_cursor": self.turn_cursor,
                "reward_last": self.reward_last,
                "total_reward": self.total_reward,
                "done": self.done,
                "success": self.success,
                "terminal_reason": self.terminal_reason,
                "achievements": sorted(self.achievements),
                "event_log": copy.deepcopy(self.event_log),
            },
        }

    def _apply(self, action: dict[str, Any]) -> bool:
        kind = action["type"]
        if kind == "message":
            if not self._observation_config()["communication_enabled"]:
                self._reject(action, "communication_disabled", {"target": action.get("target")})
                return False
            text = action.get("payload", {}).get("text", "").strip()
            if not text:
                self._reject(action, "empty_message", {})
                return False
            target = action.get("target")
            if target == "party":
                recipients = [agent_id for agent_id in self.heroes if agent_id != self.active_agent]
            elif target in self.heroes:
                recipients = [target]
            else:
                self._reject(action, "unknown_message_target", {"target": target})
                return False
            delivered = {
                "from": self.active_agent,
                "target": target,
                "text": text,
                "step_index": self.step_index,
                "turn_index": self.turn_index,
            }
            for recipient in recipients:
                self.message_inboxes[recipient].append(copy.deepcopy(delivered))
            self.heroes[self.active_agent]["messages_sent"] += 1
            self.reward_last += 0.15
            self._event(
                "message_sent",
                "info",
                f"MessageSent({self.active_agent}->{target})",
                action=action,
                payload={"from": self.active_agent, "target": target, "recipients": recipients, "text": text},
            )
            self._unlock("coordination.message_sent")
            return True
        if kind == "move":
            return self._move(action)
        if kind == "open_door":
            return self._open_door(action)
        if kind == "cast":
            return self._cast(action)
        if kind == "search_traps":
            return self._search_traps(action)
        if kind == "inspect_tile":
            return self._inspect_tile(action)
        if kind == "interact":
            return self._interact(action)
        if kind == "attack_melee":
            return self._attack_melee(action)
        if kind == "use_item":
            return self._use_item(action)
        if kind == "give_item":
            return self._give_item(action)
        if kind == "guard":
            self.heroes[self.active_agent]["guarded"] = True
            self.reward_last += 0.05
            self._event("guarded", "info", f"Guarded({self.active_agent})", action=action)
            self._unlock("coordination.guard_used")
            return True
        if kind == "end_turn":
            self._event("end_turn", "info", f"EndTurn({self.active_agent})", action=action)
            self._advance_turn()
            return True
        self._reject(action, "unknown_action", {"type": kind})
        return False

    def _move(self, action: dict[str, Any]) -> bool:
        dx, dy = DIRS[action["direction"]]
        hero = self.heroes[self.active_agent]
        start = (hero["pos"]["x"], hero["pos"]["y"])
        end = (start[0] + dx, start[1] + dy)
        if not self._passable(end):
            self._reject(action, "blocked_move", {"from": _pos(start), "to": _pos(end)})
            return False
        hero["pos"] = _pos(end)
        hero["guarded"] = False
        self.reward_last += 0.05
        self._event("move_applied", "info", f"MoveApplied({self.active_agent},{action['direction']})", action=action)
        self._unlock("movement.first_step")
        return True

    def _open_door(self, action: dict[str, Any]) -> bool:
        door = self.doors.get(action["target"])
        if door is None:
            self._reject(action, "unknown_door", {"target": action["target"]})
            return False
        if _dist(self.heroes[self.active_agent]["pos"], door["pos"]) > 1:
            self._reject(action, "door_not_adjacent", {"target": action["target"]})
            return False
        door["open"] = True
        self.reward_last += 0.3
        self._event("door_opened", "info", f"DoorOpened({action['target']})", action=action)
        self._unlock("routing.opened_door")
        return True

    def _cast(self, action: dict[str, Any]) -> bool:
        spell = action.get("payload", {}).get("spell")
        hero = self.heroes[self.active_agent]
        if spell not in hero["inventory"]:
            self._reject(action, "spell_not_available", {"spell": spell})
            return False
        if spell == "ward_circle":
            target = self.active_agent if action["target"] == "self" else action["target"]
            if target not in self.heroes:
                self._reject(action, "unknown_hero", {"target": action["target"]})
                return False
            self.heroes[target]["guarded"] = True
            self.reward_last += 0.35
            self._event("spell_cast", "info", f"SpellCast({self.active_agent},ward_circle->{target})", action=action)
            self._unlock("coordination.guard_used")
            return True
        if spell == "reveal_glyph":
            target = action["target"]
            if target in {"objective", self.scenario["objective_item"]}:
                revealed = []
                for trap in self.traps.values():
                    if not trap["revealed"]:
                        trap["revealed"] = True
                        revealed.append(trap["id"])
                self.reward_last += 0.7
                self._event(
                    "counterplay_revealed",
                    "info",
                    "CounterplayRevealed(objective)",
                    action=action,
                    payload={"target": target, "revealed_traps": revealed},
                )
                self._unlock("support.counterplay_revealed")
                return True
            monster = self.monsters.get(target)
            if monster is None:
                self._reject(action, "unknown_reveal_target", {"target": target})
                return False
            monster["statuses"] = sorted(set(monster["statuses"]) | {"counterplay_revealed"})
            monster["guard"] = 0
            self.reward_last += 0.8
            self._event(
                "counterplay_revealed",
                "info",
                f"CounterplayRevealed({target})",
                action=action,
                payload={"target": target, "effect": "monster_guard_removed"},
            )
            self._unlock("support.counterplay_revealed")
            return True
        if spell == "spark_lance":
            return self._spark_lance(action)
        self._reject(action, "unknown_spell", {"spell": spell})
        return False

    def _search_traps(self, action: dict[str, Any]) -> bool:
        hero_pos = self.heroes[self.active_agent]["pos"]
        revealed = []
        for trap in self.traps.values():
            if _dist(hero_pos, trap["pos"]) <= 2 and not trap["revealed"]:
                trap["revealed"] = True
                revealed.append(trap["id"])
        if revealed:
            self.reward_last += 0.4
            self._unlock("support.revealed_trap")
        else:
            self.reward_last += 0.02
        self._event("traps_searched", "info", f"TrapsSearched({len(revealed)})", action=action, payload={"revealed": revealed})
        return True

    def _inspect_tile(self, action: dict[str, Any]) -> bool:
        target = action["target"]
        pos = (int(target["x"]), int(target["y"]))
        terrain = self.terrain.get(pos)
        door = next((door for door in self.doors.values() if _tuple_pos(door["pos"]) == pos), None)
        trap = next((trap for trap in self.traps.values() if _tuple_pos(trap["pos"]) == pos), None)
        self.reward_last += 0.1
        self._event(
            "tile_inspected",
            "info",
            f"TileInspected({pos[0]}, {pos[1]})",
            action=action,
            payload={"target": target, "terrain": terrain, "door": door, "trap": trap},
        )
        return True

    def _interact(self, action: dict[str, Any]) -> bool:
        target = action["target"]
        if target in {"objective", self.scenario["objective_item"]}:
            return self._interact_objective(action)
        if target == "escape":
            return self._interact_escape(action)
        if target in self.chests:
            return self._interact_chest(action)
        self._reject(action, "unknown_interaction_target", {"target": target})
        return False

    def _interact_objective(self, action: dict[str, Any]) -> bool:
        agent_id = self.active_agent
        objective = self._objective_state()
        if _dist(self.heroes[agent_id]["pos"], objective["pos"]) > 1:
            self._reject(action, "objective_not_adjacent", {"objective": objective})
            return False
        if any(self.scenario["objective_item"] in hero["inventory"] for hero in self.heroes.values()):
            self._reject(action, "objective_already_taken", {})
            return False
        self.heroes[agent_id]["inventory"].append(self.scenario["objective_item"])
        self.reward_last += 3.0
        self._event(
            "objective_taken",
            "info",
            f"ObjectiveTaken({agent_id},{self.scenario['objective_item']})",
            action=action,
            payload={"agent_id": agent_id, "item_id": self.scenario["objective_item"]},
        )
        self._unlock("objective.secured")
        return True

    def _interact_escape(self, action: dict[str, Any]) -> bool:
        agent_id = self.active_agent
        escape = self._objective_state()["escape_tile"]
        hero = self.heroes[agent_id]
        if hero["pos"] != escape:
            self._reject(action, "not_on_escape_tile", {"escape_tile": escape})
            return False
        if self.scenario["objective_item"] not in hero["inventory"]:
            self._reject(action, "missing_objective_item", {"agent_id": agent_id})
            return False
        self.reward_last += 5.0
        self.done = True
        self.success = True
        self.terminal_reason = "escaped_with_objective"
        self._event("objective_escaped", "info", f"ObjectiveEscaped({agent_id})", action=action, payload={"agent_id": agent_id})
        self._unlock("objective.extracted")
        self._event("terminal", "info", "Terminal(success)", payload={"reason": "escaped_with_objective"})
        return True

    def _interact_chest(self, action: dict[str, Any]) -> bool:
        target = action["target"]
        chest = self.chests[target]
        agent_id = self.active_agent
        if _dist(self.heroes[agent_id]["pos"], chest["pos"]) > 1:
            self._reject(action, "chest_not_adjacent", {"target": target})
            return False
        if chest["opened"]:
            self._reject(action, "chest_already_open", {"target": target})
            return False
        chest["opened"] = True
        contents = list(chest["contents"])
        self.heroes[agent_id]["inventory"].extend(contents)
        self.reward_last += 0.8
        self._event("chest_opened", "info", f"ChestOpened({target})", action=action, payload={"target": target, "contents": contents, "agent_id": agent_id})
        self._unlock("optional.opened_chest")
        return True

    def _attack_melee(self, action: dict[str, Any]) -> bool:
        target = action["target"]
        monster = self.monsters.get(target)
        agent_id = self.active_agent
        if monster is None:
            self._reject(action, "unknown_monster", {"target": target})
            return False
        if monster["hp"] <= 0:
            self._reject(action, "monster_already_defeated", {"target": target})
            return False
        if _dist(self.heroes[agent_id]["pos"], monster["pos"]) > 1:
            self._reject(action, "monster_not_adjacent", {"target": target, "monster": monster})
            return False
        guard = 0 if "counterplay_revealed" in monster["statuses"] else monster["guard"]
        damage = max(1, _hero_attack(self.heroes[agent_id]["role"]) - guard)
        monster["awake"] = True
        monster["hp"] = max(0, monster["hp"] - damage)
        defeated = monster["hp"] == 0
        self.reward_last += 2.0 if defeated else 0.5
        self._event("melee_attack", "info", f"MeleeAttack({agent_id}->{target},damage={damage})", action=action, payload={"agent_id": agent_id, "target": target, "damage": damage, "defeated": defeated})
        self._unlock("combat.first_hit")
        if defeated:
            self._event("monster_defeated", "info", f"MonsterDefeated({target})", payload={"target": target})
            self._unlock("combat.monster_defeated")
        return True

    def _spark_lance(self, action: dict[str, Any]) -> bool:
        target = action["target"]
        monster = self.monsters.get(target)
        agent_id = self.active_agent
        if monster is None:
            self._reject(action, "unknown_monster", {"target": target})
            return False
        if _dist(self.heroes[agent_id]["pos"], monster["pos"]) > 4:
            self._reject(action, "spell_target_out_of_range", {"target": target})
            return False
        damage = 2
        monster["awake"] = True
        monster["hp"] = max(0, monster["hp"] - damage)
        defeated = monster["hp"] == 0
        self.reward_last += 2.0 if defeated else 0.6
        self._event("spell_cast", "info", f"SpellCast({agent_id},spark_lance->{target},damage={damage})", action=action, payload={"spell": "spark_lance", "target": target, "damage": damage, "defeated": defeated})
        self._unlock("caster.spell_cast")
        if defeated:
            self._event("monster_defeated", "info", f"MonsterDefeated({target})", payload={"target": target})
            self._unlock("combat.monster_defeated")
        return True

    def _use_item(self, action: dict[str, Any]) -> bool:
        item = action["target"]
        hero = self.heroes[self.active_agent]
        if item not in hero["inventory"]:
            self._reject(action, "item_not_carried", {"item": item})
            return False
        hero["inventory"].remove(item)
        effect = "consumed"
        if item in {"healing_draught", "iron_ration"}:
            amount = 3 if item == "healing_draught" else 1
            hero["hp"] = min(hero["max_hp"], hero["hp"] + amount)
            effect = "healed"
            self.reward_last += 0.25
        else:
            self.reward_last += 0.05
        self._event("item_used", "info", f"ItemUsed({self.active_agent},{item})", action=action, payload={"agent_id": self.active_agent, "item": item, "effect": effect})
        self._unlock("inventory.item_used")
        return True

    def _give_item(self, action: dict[str, Any]) -> bool:
        target = action["target"]
        item = action.get("payload", {}).get("item")
        if target not in self.heroes:
            self._reject(action, "unknown_hero", {"target": target})
            return False
        giver = self.heroes[self.active_agent]
        receiver = self.heroes[target]
        if _dist(giver["pos"], receiver["pos"]) > 1:
            self._reject(action, "hero_not_adjacent", {"target": target, "item": item})
            return False
        if item not in giver["inventory"]:
            self._reject(action, "item_not_carried", {"target": target, "item": item})
            return False
        giver["inventory"].remove(item)
        receiver["inventory"].append(item)
        self.reward_last += 0.2
        self._event("item_given", "info", f"ItemGiven({self.active_agent}->{target},{item})", action=action, payload={"from": self.active_agent, "target": target, "item": item})
        self._unlock("coordination.item_handoff")
        return True

    def _advance_turn(self) -> None:
        self.turn_cursor = (self.turn_cursor + 1) % len(self.turn_order)
        if self.turn_cursor == 0:
            self.turn_index += 1
        self.active_agent = self.turn_order[self.turn_cursor]
        self.heroes[self.active_agent]["ap"] = self.heroes[self.active_agent]["max_ap"]
        self._event("turn_started", "info", f"TurnStarted({self.active_agent})")

    def _passable(self, pos: tuple[int, int]) -> bool:
        if self.terrain.get(pos) not in {"floor", "escape", "objective"}:
            return False
        for door in self.doors.values():
            if _tuple_pos(door["pos"]) == pos and not door["open"]:
                return False
        for monster in self.monsters.values():
            if _tuple_pos(monster["pos"]) == pos and monster["hp"] > 0:
                return False
        return True

    def _check_trap(self) -> None:
        agent_id = self.active_agent
        pos = _tuple_pos(self.heroes[agent_id]["pos"])
        trap = next((trap for trap in self.traps.values() if _tuple_pos(trap["pos"]) == pos and trap["armed"]), None)
        if trap is None:
            return
        trap["revealed"] = True
        trap["armed"] = False
        damage = int(trap["damage"])
        self.heroes[agent_id]["hp"] = max(0, self.heroes[agent_id]["hp"] - damage)
        self.reward_last -= 0.2
        self._event("trap_triggered", "warning", f"TrapTriggered({trap['id']},{agent_id})", payload={"trap_id": trap["id"], "agent_id": agent_id, "damage": damage})

    def _check_terminal(self) -> None:
        if all(hero["hp"] <= 0 for hero in self.heroes.values()):
            self.done = True
            self.success = False
            self.terminal_reason = "party_defeated"
            self._event("terminal", "info", "Terminal(party_defeated)", payload={"reason": "party_defeated"})

    def _observation_config(self) -> dict[str, Any]:
        return {
            "mode": "global",
            "visibility_radius": 3,
            "communication_enabled": True,
            **self.scenario.get("observation", {}),
        }

    def _visible(self, agent_id: str | None, pos: dict[str, int] | tuple[int, int]) -> bool:
        if agent_id is None or self._observation_config()["mode"] == "global":
            return True
        point = _pos(pos) if isinstance(pos, tuple) else pos
        return _dist(self.heroes[agent_id]["pos"], point) <= int(
            self._observation_config()["visibility_radius"]
        )

    def _render_ascii(self, viewer: str | None = None) -> str:
        rows = [[" " for _ in range(self.width)] for _ in range(self.height)]
        for (x, y), terrain in self.terrain.items():
            if not self._visible(viewer, (x, y)):
                rows[y][x] = "?"
                continue
            rows[y][x] = {"wall": "#", "floor": ".", "escape": "E", "objective": "I"}[terrain]
        for door in self.doors.values():
            if not self._visible(viewer, door["pos"]):
                continue
            rows[door["pos"]["y"]][door["pos"]["x"]] = "/" if door["open"] else "D"
        for trap in self.traps.values():
            if not self._visible(viewer, trap["pos"]):
                continue
            rows[trap["pos"]["y"]][trap["pos"]["x"]] = "^" if trap["revealed"] else "."
        for chest in self.chests.values():
            if not self._visible(viewer, chest["pos"]):
                continue
            rows[chest["pos"]["y"]][chest["pos"]["x"]] = "c" if chest["opened"] else "C"
        for monster in self.monsters.values():
            if monster["hp"] > 0 and self._visible(viewer, monster["pos"]):
                rows[monster["pos"]["y"]][monster["pos"]["x"]] = "R"
        for hero in self.heroes.values():
            if self._visible(viewer, hero["pos"]):
                rows[hero["pos"]["y"]][hero["pos"]["x"]] = hero["agent_id"][-1]
        return "\n".join("".join(row) for row in rows)

    def _objective_state(self) -> dict[str, Any]:
        holder = next(
            (
                hero["agent_id"]
                for hero in self.heroes.values()
                if self.scenario["objective_item"] in hero["inventory"]
            ),
            None,
        )
        objective_pos = next(pos for pos, terrain in self.terrain.items() if terrain == "objective")
        escape_pos = next(pos for pos, terrain in self.terrain.items() if terrain == "escape")
        return {
            "item_id": self.scenario["objective_item"],
            "pos": _pos(objective_pos),
            "holder": holder,
            "escape_tile": _pos(escape_pos),
            "secured": holder is not None,
        }

    def _legal_actions(self) -> dict[str, Any]:
        hero = self.heroes[self.active_agent]
        base = ["move", "inspect_tile", "search_traps", "guard", "cast", "use_item", "give_item", "end_turn"]
        if self._observation_config()["communication_enabled"]:
            base.insert(3, "message")
        return {
            "agent_id": self.active_agent,
            "ap": hero["ap"],
            "base": base,
            "directions": sorted(DIRS),
            "adjacent_doors": [
                door_id
                for door_id, door in self.doors.items()
                if _dist(hero["pos"], door["pos"]) <= 1 and not door["open"]
            ],
            "adjacent_chests": [
                chest_id
                for chest_id, chest in self.chests.items()
                if _dist(hero["pos"], chest["pos"]) <= 1 and not chest["opened"]
            ],
            "adjacent_monsters": [
                monster_id
                for monster_id, monster in self.monsters.items()
                if _dist(hero["pos"], monster["pos"]) <= 1 and monster["hp"] > 0
            ],
            "ranged_monsters": [
                monster_id
                for monster_id, monster in self.monsters.items()
                if _dist(hero["pos"], monster["pos"]) <= 4
                and monster["hp"] > 0
                and self._visible(self.active_agent, monster["pos"])
            ],
            "adjacent_heroes": [
                agent_id
                for agent_id, other in self.heroes.items()
                if agent_id != self.active_agent and _dist(hero["pos"], other["pos"]) <= 1
            ],
            "carried_items": hero["inventory"],
            "spells": [item for item in hero["inventory"] if item in {"spark_lance", "reveal_glyph", "ward_circle"}],
            "can_interact_objective": _dist(hero["pos"], self._objective_state()["pos"]) <= 1,
            "can_escape": hero["pos"] == self._objective_state()["escape_tile"]
            and self.scenario["objective_item"] in hero["inventory"],
        }

    def _coordination_state(self) -> dict[str, Any]:
        return {
            "message_count": sum(hero["messages_sent"] for hero in self.heroes.values()),
            "guarded_agents": [hero["agent_id"] for hero in self.heroes.values() if hero["guarded"]],
            "objective_holder": self._objective_state()["holder"],
            "active_role": self.heroes[self.active_agent]["role"],
            "axis": self.scenario.get("metadata", {}).get("marl_axis"),
            "skills": self.scenario.get("metadata", {}).get("coordination_skills"),
        }

    def _transition_snapshot(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "active_agent": self.active_agent,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "done": self.done,
            "success": self.success,
            "heroes": [
                {"agent_id": agent_id, "pos": hero["pos"], "hp": hero["hp"], "ap": hero["ap"]}
                for agent_id, hero in self.heroes.items()
            ],
            "objective": self._objective_state(),
            "achievements": sorted(self.achievements),
        }

    def observation_for(self, agent_id: str) -> dict[str, Any]:
        config = self._observation_config()
        local_mode = config["mode"] == "local"
        return {
            "agent_id": agent_id,
            "active_agent": self.active_agent,
            "round": self.turn_index,
            "phase": "terminal" if self.done else "hero_turn",
            "observation_mode": config["mode"],
            "visibility_radius": config["visibility_radius"] if local_mode else None,
            "communication_enabled": config["communication_enabled"],
            "visible_map": self._render_ascii(agent_id if local_mode else None),
            "inbox": copy.deepcopy(self.message_inboxes.get(agent_id, [])),
            "symbolic": self._local_state(agent_id) if local_mode else self.rich_state(),
        }

    def _local_state(self, agent_id: str) -> dict[str, Any]:
        objective = self._objective_state()
        objective_visible = (
            self._visible(agent_id, objective["pos"])
            or objective["holder"] == agent_id
            or (
                objective["holder"] in self.heroes
                and self._visible(agent_id, self.heroes[objective["holder"]]["pos"])
            )
        )
        return {
            "schema": "gamebench.dungeongrid.local_observation.v1",
            "episode_id": self.episode_id,
            "step_index": self.step_index,
            "turn_index": self.turn_index,
            "active_agent": self.active_agent,
            "self": copy.deepcopy(self.heroes[agent_id]),
            "map": {
                "width": self.width,
                "height": self.height,
                "ascii": self._render_ascii(agent_id),
                "visible_terrain": [
                    {"x": x, "y": y, "terrain": terrain}
                    for (x, y), terrain in sorted(self.terrain.items())
                    if self._visible(agent_id, (x, y))
                ],
            },
            "visible_heroes": {
                other_id: copy.deepcopy(hero)
                for other_id, hero in self.heroes.items()
                if other_id == agent_id or self._visible(agent_id, hero["pos"])
            },
            "visible_doors": {
                entity_id: copy.deepcopy(entity)
                for entity_id, entity in self.doors.items()
                if self._visible(agent_id, entity["pos"])
            },
            "visible_traps": {
                entity_id: copy.deepcopy(entity)
                for entity_id, entity in self.traps.items()
                if entity["revealed"] and self._visible(agent_id, entity["pos"])
            },
            "visible_chests": {
                entity_id: copy.deepcopy(entity)
                for entity_id, entity in self.chests.items()
                if self._visible(agent_id, entity["pos"])
            },
            "visible_monsters": {
                entity_id: copy.deepcopy(entity)
                for entity_id, entity in self.monsters.items()
                if entity["hp"] > 0 and self._visible(agent_id, entity["pos"])
            },
            "objective": objective if objective_visible else None,
            "legal_actions": self._legal_actions() if agent_id == self.active_agent else None,
            "inbox": copy.deepcopy(self.message_inboxes.get(agent_id, [])),
            "done": self.done,
            "success": self.success,
            "terminal_reason": self.terminal_reason,
        }

    def _result(self, applied: bool) -> dict[str, Any]:
        local_mode = self._observation_config()["mode"] == "local"
        return {
            "applied": applied,
            "observation": self.observation_for(self.active_agent),
            "reward": self.reward_last,
            "done": self.done,
            "info": {
                "recent_events": [] if local_mode else self.event_log[-8:],
                "rich_state": self._local_state(self.active_agent) if local_mode else self.rich_state(),
            },
        }

    def _unlock(self, achievement: str) -> None:
        if achievement not in self.achievements:
            self.achievements.add(achievement)
            self._event("achievement_unlocked", "info", f"AchievementUnlocked({achievement})")

    def _reject(self, action: dict[str, Any], reason: str, details: dict[str, Any]) -> None:
        self.reward_last = 0.0
        self._event(
            "action_rejected",
            "warning",
            f"ActionRejected({reason})",
            action=action,
            payload={"reason": reason, "details": details},
        )

    def _event(
        self,
        kind: str,
        severity: str,
        message: str,
        *,
        action: dict[str, Any] | None = None,
        transition: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.event_log.append(
            {
                "step_index": self.step_index,
                "turn_index": self.turn_index,
                "episode_id": self.episode_id,
                "agent_id": self.active_agent,
                "kind": kind,
                "severity": severity,
                "message": message,
                "action": action,
                "transition": transition,
                "payload": payload or {},
            }
        )


def _starting_inventory(role: str) -> list[str]:
    if role == "wizard":
        return ["ash_staff", "spark_lance", "reveal_glyph", "ward_circle"]
    if role == "barbarian":
        return ["broad_sword", "iron_ration"]
    return []


def _action_cost(action: dict[str, Any]) -> int:
    if action["type"] == "end_turn":
        return 0
    if action["type"] in {"move", "open_door", "message", "guard", "interact", "use_item", "give_item"}:
        return 1
    return 2


def _hero_attack(role: str) -> int:
    if role == "barbarian":
        return 3
    if role == "wizard":
        return 1
    return 2


def _pos(pos: tuple[int, int]) -> dict[str, int]:
    return {"x": pos[0], "y": pos[1]}


def _tuple_pos(pos: dict[str, int]) -> tuple[int, int]:
    return (int(pos["x"]), int(pos["y"]))


def _dist(left: dict[str, int], right: dict[str, int]) -> int:
    return abs(left["x"] - right["x"]) + abs(left["y"] - right["y"])
