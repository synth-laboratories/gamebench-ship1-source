"""Python gold engine for the Rogue singleplayer lane."""

from __future__ import annotations

import json
from typing import Any

from core.nev import NevLog
from scoring import binary_success_score
from source_attack import AttackItem, AttackMonster, AttackWorld, SourceRing as AttackRing, SourceStats as AttackStats, attack as source_attack
from source_chase import ChaseMap, ChaseObject as SourceChaseObject, ChaseThing, Coord as ChaseCoord, chase as source_chase, move_monst_schedule
from source_command import CURRENT_ACTIONS, NO_TURN_ACTIONS, runtime_command_projection
from source_daemons import AFTER as DAEMON_AFTER
from source_daemons import BEFORE as DAEMON_BEFORE
from source_daemons import DAEMON, EMPTY, DaemonWorld, DelayedAction, SourceRing as DaemonRing, SourceStats as DaemonStats, do_daemons, do_fuses
from source_do_chase import ChaseMonster as DoChaseMonster, ChaseObject as DoChaseObject, ChaseRoom as DoChaseRoom, Coord as DoChaseCoord, DoChaseWorld, do_chase as source_do_chase
from source_fight import E_LEVELS
from source_fight import ISRUN as FIGHT_ISRUN
from source_fight import FightMonster, FightObject, FightStats, FightWeapon, FightWorld, fight as source_fight
from source_level import SourceLevelDraft, generate_new_level_slice
from source_monsters import MONSTER_NAMES
from source_rogue import AMULET, ARMOR, DOOR, FLOOR, FOOD, GOLD, MAXPACK, NUMCOLS, NUMLINES, PASSAGE, POTION, RING, SCROLL, STICK, RogueRng, WEAPON, command_move_delta, step_ok
from source_potions import PotionObject, PotionWorld, SourceRing, quaff
from source_rings import LEFT, RING, RingObject, RingWorld, dropcheck as ring_dropcheck, ring_off, ring_on
from source_scrolls import R_OR_S, S_ID_ARMOR, S_ID_POTION, S_ID_R_OR_S, S_ID_SCROLL, S_ID_WEAPON, S_TELEP, ScrollItem, ScrollObject, ScrollWorld, read_scroll
from source_sticks import ISHELD, WS_COLD, WS_ELECT, WS_FIRE, StickMonster, StickObject, StickWorld, do_zap
from source_state import SOURCE_POT_INFO, SOURCE_RING_INFO, SOURCE_SCR_INFO, SOURCE_WS_INFO, runtime_source_checkpoint_projection, runtime_source_identity_display, runtime_source_save_file_projection
from source_traps import F_REAL as TRAP_F_REAL
from source_traps import F_SEEN as TRAP_F_SEEN
from source_traps import F_TMASK as TRAP_F_TMASK
from source_traps import T_DOOR, T_MYST, T_TELEP
from source_traps import SourceTrapArmor, SourceTrapCell, SourceTrapRing, SourceTrapState, SourceTrapStats, be_trapped as source_be_trapped, search_hidden_traps
from state import Position, PrivateState, PublicState
from task_resolve import ResolvedTask


ISFOUND = 0o000020
ISCURSED = 0o000001
ISKNOW = 0o000002
SOURCE_ROOM_ISGONE = 0o000002
SOURCE_ROOM_ISMAZE = 0o000004
VS_MAGIC = 3
R_PROTECT = 0
BOLT_LENGTH = 6
FLAME_WEAPON = 9
S_SCARE = 10
HUNGERTIME = 1300
STOMACHSIZE = 2000
PICKUP_ITEMS = {GOLD, FOOD}
SOURCE_WEAPON_NAMES = (
    "mace",
    "long sword",
    "short bow",
    "arrow",
    "dagger",
    "two handed sword",
    "dart",
    "shuriken",
    "spear",
    "flame",
)
SOURCE_ARMOR_NAMES = (
    "leather armor",
    "ring mail",
    "studded leather armor",
    "scale mail",
    "chain mail",
    "splint mail",
    "banded mail",
    "plate mail",
)
SOURCE_A_CLASS = (8, 7, 7, 6, 5, 4, 4, 3)
SOURCE_RING_NAMES = (
    "protection",
    "add strength",
    "sustain strength",
    "searching",
    "see invisible",
    "adornment",
    "aggravate monster",
    "dexterity",
    "increase damage",
    "regeneration",
    "slow digestion",
    "teleportation",
    "stealth",
    "maintain armor",
)
SOURCE_HELP_ENTRIES = (
    ("?", "\tprints help", True),
    ("/", "\tidentify object", True),
    ("h", "\tleft", True),
    ("j", "\tdown", True),
    ("k", "\tup", True),
    ("l", "\tright", True),
    ("y", "\tup & left", True),
    ("u", "\tup & right", True),
    ("b", "\tdown & left", True),
    ("n", "\tdown & right", True),
    ("H", "\trun left", False),
    ("J", "\trun down", False),
    ("K", "\trun up", False),
    ("L", "\trun right", False),
    ("Y", "\trun up & left", False),
    ("U", "\trun up & right", False),
    ("B", "\trun down & left", False),
    ("N", "\trun down & right", False),
    ("\x08", "\trun left until adjacent", False),
    ("\x0a", "\trun down until adjacent", False),
    ("\x0b", "\trun up until adjacent", False),
    ("\x0c", "\trun right until adjacent", False),
    ("\x19", "\trun up & left until adjacent", False),
    ("\x15", "\trun up & right until adjacent", False),
    ("\x02", "\trun down & left until adjacent", False),
    ("\x0e", "\trun down & right until adjacent", False),
    ("", "\t<SHIFT><dir>: run that way", True),
    ("", "\t<CTRL><dir>: run till adjacent", True),
    ("f", "<dir>\tfight till death or near death", True),
    ("t", "<dir>\tthrow something", True),
    ("m", "<dir>\tmove onto without picking up", True),
    ("z", "<dir>\tzap a wand in a direction", True),
    ("^", "<dir>\tidentify trap type", True),
    ("s", "\tsearch for trap/secret door", True),
    (">", "\tgo down a staircase", True),
    ("<", "\tgo up a staircase", True),
    (".", "\trest for a turn", True),
    (",", "\tpick something up", True),
    ("i", "\tinventory", True),
    ("I", "\tinventory single item", True),
    ("q", "\tquaff potion", True),
    ("r", "\tread scroll", True),
    ("e", "\teat food", True),
    ("w", "\twield a weapon", True),
    ("W", "\twear armor", True),
    ("T", "\ttake armor off", True),
    ("P", "\tput on ring", True),
    ("R", "\tremove ring", True),
    ("d", "\tdrop object", True),
    ("c", "\tcall object", True),
    ("a", "\trepeat last command", True),
    (")", "\tprint current weapon", True),
    ("]", "\tprint current armor", True),
    ("=", "\tprint current rings", True),
    ("@", "\tprint current stats", True),
    ("D", "\trecall what's been discovered", True),
    ("o", "\texamine/set options", True),
    ("\x12", "\tredraw screen", True),
    ("\x10", "\trepeat last message", True),
    ("\x1b", "\tcancel command", True),
    ("S", "\tsave game", True),
    ("Q", "\tquit", True),
    ("!", "\tshell escape", True),
    ("F", "<dir>\tfight till either of you dies", True),
    ("v", "\tprint version number", True),
)
SOURCE_HUNGER_NAMES = ("", "Hungry", "Weak", "Faint")


class RogueEngine:
    ENV_FAMILY = "rogue-singleplayer"

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.public = PublicState(terrain=[], hero=(0, 0))
        self.private = PrivateState()
        self.nev = NevLog()

    def reset(self, resolved: ResolvedTask) -> None:
        terrain: list[str] = []
        items: dict[str, str] = {}
        item_values: dict[str, int] = {}
        hero = (0, 0)
        rng = RogueRng(resolved.seed)
        for row_index, row in enumerate(resolved.grid):
            cells = list(row)
            for col_index, char in enumerate(cells):
                key = f"{row_index},{col_index}"
                if char == "@":
                    hero = (row_index, col_index)
                    cells[col_index] = "."
                elif char in PICKUP_ITEMS:
                    items[key] = char
                    if char == GOLD:
                        item_values[key] = rng.gold_calc(level=1)
                    cells[col_index] = "."
            terrain.append("".join(cells))
        self.resolved = resolved
        source_monsters = self._normalize_monsters(resolved.monsters)
        source_traps = self._normalize_traps(resolved.traps, terrain)
        source_map_cells = self._normalize_source_map_cells(resolved.source_map_cells)
        self._apply_source_map_cell_display(terrain, source_map_cells)
        source_level_objects = self._normalize_level_objects(resolved.level_objects)
        for obj in source_level_objects:
            pos = dict(obj.get("pos", {}))
            row = int(pos.get("y", 0))
            col = int(pos.get("x", 0))
            key = f"{row},{col}"
            obj_type = str(obj.get("type", "?"))[:1] or "?"
            items[key] = obj_type
            if obj_type == GOLD:
                item_values[key] = int(obj.get("goldval", item_values.get(key, 0)))
            if 0 <= row < len(terrain):
                cells = list(terrain[row])
                if 0 <= col < len(cells) and cells[col] == obj_type:
                    cells[col] = "."
                    terrain[row] = "".join(cells)
        self.public = PublicState(terrain=terrain, hero=hero, visible_items=items, visible_monsters=self._visible_monsters(source_monsters))
        self.private = PrivateState(
            rng_seed=rng.seed,
            item_values=item_values,
            source_inventory=self._normalize_inventory(resolved.inventory),
            source_monsters=source_monsters,
            source_traps=source_traps,
            source_map_cells=source_map_cells,
            source_level_objects=source_level_objects,
            source_daemon_actions=self._default_daemon_actions(),
            config_hash=resolved.config_hash,
            episode_id=resolved.episode_id,
        )
        self.nev = NevLog()
        self._refresh_progress_metrics(None, emit=False)
        self._event("state_transition", f"TaskResolved({resolved.task_id},{resolved.config_hash})", transition="reset", payload={"task": resolved.to_dict()})

    def step(self, action: str) -> dict[str, Any]:
        if self.resolved is None:
            raise RuntimeError("engine must be reset before step")
        if self.private.terminated or self.private.truncated:
            self._event("rule_violation", "RuleViolation(terminal)", action=action, transition="reject", severity="warn")
            return self.symbolic_readout()
        self.private.step_index += 1
        self._run_source_daemon_phase(action, DAEMON_BEFORE, "before")
        if self.private.terminated or self.private.truncated:
            return self.symbolic_readout()
        command = self._effective_command(action)
        projection = self._apply_command_projection(action)
        self._event("command_dispatch", f"CommandDispatch({projection['command']})", action=action, transition="command", payload=projection)
        if "no_command_wait" in projection["final"]["markers"]:
            self._event("action_applied", "NoCommandWait()", action=action, transition="no_command_wait", payload={"markers": projection["final"]["markers"], "no_command": self.private.no_command})
        else:
            delta = command_move_delta(command)
            if delta is not None:
                self._move(command, delta)
            elif command == ".":
                self._event("action_applied", "Rest()", action=action, transition="rest")
            elif command == ",":
                self._pickup(action)
            elif command == ">":
                self._descend(action)
            elif command == "<":
                self._ascend(action)
            elif command == "s":
                self._search(action)
            elif command in {"f", "F"}:
                if not self._apply_source_fight_command(command, action):
                    self._event("action_applied", f"SourceCommandPending({projection['command']})", action=action, transition="source_pending", payload={"command": projection["command"], "markers": projection["final"]["markers"]})
            elif command in {"q", "r", "z", "P", "R", "d", "e", "w", "W", "T", "t"}:
                if not self._apply_source_item_command(command, action):
                    self._event("action_applied", f"SourceCommandPending({projection['command']})", action=action, transition="source_pending", payload={"command": projection["command"], "markers": projection["final"]["markers"]})
            elif self._apply_source_no_turn_command(command, action, projection):
                pass
            elif projection["known"]:
                transition = "source_no_turn" if not self.private.command_after else "source_pending"
                self._event("action_applied", f"SourceCommandPending({projection['command']})", action=action, transition=transition, payload={"command": projection["command"], "markers": projection["final"]["markers"]})
            else:
                self._event("rule_violation", f"RuleViolation(illegal_command:{action})", action=action, transition="illegal", severity="warn", payload={"command": projection["command"]})
        if self.private.command_after and not (self.private.terminated or self.private.truncated):
            self._run_source_daemon_phase(action, DAEMON_AFTER, "after")
        if self.private.command_after and not (self.private.terminated or self.private.truncated):
            self._run_source_monster_turns(action)
        self._refresh_progress_metrics(action, emit=True)
        if self.private.step_index >= self.resolved.max_steps and not self.private.terminated:
            self.private.truncated = True
            self.private.terminal_reason = "truncated"
            self._event("terminal", "Terminal(truncated)", action=action, transition="truncate")
        return self.symbolic_readout()

    def _move(self, action: str, delta: Position) -> None:
        if self.private.no_move > 0:
            self.private.no_move -= 1
            self._event("action_applied", f"NoMoveWait(remaining={self.private.no_move})", action=action, transition="no_move_wait", payload={"no_move": self.private.no_move})
            return
        dy, dx = delta
        row, col = self.public.hero
        nr, nc = row + dy, col + dx
        if not self._in_bounds(nr, nc) or not step_ok(self._terrain(nr, nc)) or not self._diag_ok(row, col, nr, nc):
            self._event("rule_violation", "Bump(wall)", action=action, transition="blocked", severity="warn", payload={"from": [row, col], "to": [nr, nc]})
            return
        monster = self._monster_at(nr, nc)
        if monster is not None:
            self._fight_monster(action, monster, thrown=False)
            return
        self.public.hero = (nr, nc)
        self._event("action_applied", f"Move({action},{nr},{nc})", action=action, transition="move", payload={"hero": [nr, nc]})
        trap_kind = self._apply_source_trap(action, previous=(row, col))
        if self.private.terminated or trap_kind in {T_DOOR, T_TELEP}:
            return
        self._pickup(action)

    def _pickup(self, action: str) -> None:
        row, col = self.public.hero
        key = f"{row},{col}"
        item = self.public.visible_items.pop(key, None)
        if item is None:
            if action == ",":
                self._event("state_transition", "NothingHere()", action=action, transition="pickup_empty")
            return
        level_object_index = self._source_level_object_index_at(row, col)
        if item == GOLD:
            gold = self.private.item_values.pop(key)
            self.private.purse += gold
            self._record_acquired_item_class(GOLD)
            if level_object_index is not None:
                self.private.source_level_objects.pop(level_object_index)
            self._event("resource_delta", f"GoldPicked({gold},total={self.private.purse})", action=action, transition="pickup", payload={"gold": gold, "purse": self.private.purse})
        elif item == FOOD and level_object_index is None:
            self.private.food += 1
            self._record_acquired_item_class(FOOD)
            self._event("resource_delta", f"FoodPicked(total={self.private.food})", action=action, transition="pickup", payload={"food": self.private.food})
        elif level_object_index is not None:
            picked = self.private.source_level_objects.pop(level_object_index)
            result = self._add_source_inventory_object(picked)
            if result == "no_room":
                self.private.source_level_objects.insert(level_object_index, picked)
                self.public.visible_items[key] = item
                self._event("rule_violation", "RuleViolation(pack_full)", action=action, transition="pickup_blocked", severity="warn", payload={"item": dict(picked)})
                return
            self._event(
                "resource_delta",
                f"SourceItemPicked({picked['id']},{result})",
                action=action,
                transition="pickup",
                payload={"item": dict(picked), "result": result, "inventory": [dict(entry) for entry in self.private.source_inventory]},
            )
            self._record_acquired_item_class(str(picked.get("type", item))[:1] or item)
        else:
            self.public.visible_items[key] = item

    def _descend(self, action: str) -> None:
        if self._terrain(*self.public.hero) != "%":
            self._event("rule_violation", "RuleViolation(no_stairs)", action=action, transition="reject", severity="warn")
            return
        self._apply_source_new_level(action, reason="descend", level=self.private.dungeon_level + 1)
        reward = binary_success_score(self.private.to_dict(), self.resolved.objective if self.resolved else "descend")
        self.private.total_reward += reward
        self._event("state_transition", f"Descend(level={self.private.dungeon_level})", action=action, transition="descend")
        self._event("resource_delta", f"RewardDelta({reward:.2f},total={self.private.total_reward:.2f})", action=action, transition="reward", payload={"reward": reward, "total_reward": self.private.total_reward})
        if reward > 0:
            self.private.terminated = True
            self.private.terminal_reason = "success"
            self._event("terminal", "Terminal(success)", action=action, transition="success")

    def _search(self, action: str) -> None:
        row, col = self.public.hero
        rng = RogueRng(self.private.rng_seed)
        result = search_hidden_traps(rng, self.private.source_traps, row, col, self.private.player_flags, self.private.source_map_cells)
        self.private.rng_seed = rng.seed
        self.private.source_trap_markers = list(result["markers"])
        if result["found"]:
            self.private.command_running = False
            self.private.command_count = 0
        for trap in self.private.source_traps:
            if int(trap.get("flags", 0)) & TRAP_F_REAL and int(trap.get("flags", 0)) & TRAP_F_SEEN and str(trap.get("ch", ""))[:1] == "^":
                self.public.visible_items[f"{int(trap['row'])},{int(trap['col'])}"] = "^"
        for cell in self.private.source_map_cells:
            if int(cell.get("flags", 0)) & TRAP_F_REAL:
                self._set_terrain(int(cell["row"]), int(cell["col"]), str(cell.get("ch", " "))[:1] or " ")
        self._event("action_applied", "SourceSearch()", action=action, transition="search", payload=result)

    def _ascend(self, action: str) -> None:
        if self._terrain(*self.public.hero) != "%":
            self._event("rule_violation", "RuleViolation(no_stairs_up)", action=action, transition="reject", severity="warn")
            return
        if not self.private.has_amulet:
            self._event("rule_violation", "RuleViolation(up_blocked_no_amulet)", action=action, transition="reject", severity="warn")
            return
        next_level = self.private.dungeon_level - 1
        if next_level <= 0:
            self.private.dungeon_level = 0
            self.private.terminated = True
            self.private.terminal_reason = "success"
            reward = binary_success_score(self.private.to_dict(), self.resolved.objective if self.resolved else "escape")
            self.private.total_reward += reward
            self._event("state_transition", "SourceWinner()", action=action, transition="ascend_win", payload={"level": 0, "has_amulet": self.private.has_amulet})
            self._event("resource_delta", f"RewardDelta({reward:.2f},total={self.private.total_reward:.2f})", action=action, transition="reward", payload={"reward": reward, "total_reward": self.private.total_reward})
            self._event("terminal", "Terminal(success)", action=action, transition="success")
            return
        self._apply_source_new_level(action, reason="ascend", level=next_level)
        self._event("state_transition", f"Ascend(level={self.private.dungeon_level})", action=action, transition="ascend", payload={"level": self.private.dungeon_level, "has_amulet": self.private.has_amulet})

    def _apply_source_new_level(self, action: str, *, reason: str, level: int) -> None:
        max_level = max(self.private.max_level, level)
        draft = generate_new_level_slice(self.private.rng_seed, level=level, max_level=max_level, amulet=self.private.has_amulet)
        self._sync_source_level_draft(draft)
        self._event(
            "state_transition",
            f"SourceNewLevel({reason},level={level})",
            action=action,
            transition="source_new_level",
            payload={"reason": reason, "level": level, "hero": draft.hero.to_dict(), "rng_seed": draft.rng_seed},
        )

    def _sync_source_level_draft(self, draft: SourceLevelDraft) -> None:
        terrain_rows = [list(row) for row in draft.rows()]
        visible_items: dict[str, str] = {}
        item_values: dict[str, int] = {}
        source_level_objects: list[dict[str, Any]] = []
        for index, obj in enumerate(draft.level_objects):
            obj_payload = obj.to_dict()
            obj_payload["id"] = f"level{draft.level}_object{index}"
            source_level_objects.append(obj_payload)
            row = int(obj.pos.y)
            col = int(obj.pos.x)
            key = f"{row},{col}"
            visible_items[key] = obj.obj_type
            if obj.obj_type == GOLD:
                item_values[key] = int(obj.goldval)
            if 0 <= row < len(terrain_rows) and 0 <= col < len(terrain_rows[row]) and terrain_rows[row][col] == obj.obj_type:
                terrain_rows[row][col] = "."
        self.public.terrain = ["".join(row) for row in terrain_rows]
        self.public.hero = (int(draft.hero.y), int(draft.hero.x))
        self.public.visible_items = visible_items
        self.private.item_values = item_values
        self.private.source_level_objects = source_level_objects
        self.private.source_monsters = [self._source_level_monster_payload(draft.level, index, monster) for index, monster in enumerate(draft.monsters)]
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)
        self.private.source_traps = [
            {
                "id": f"level{draft.level}_trap{index}",
                "row": int(trap.pos.y),
                "col": int(trap.pos.x),
                "kind": int(trap.kind),
                "flags": int(trap.kind),
                "ch": "^",
                "weapon_group": 1,
            }
            for index, trap in enumerate(draft.traps)
        ]
        self.private.source_rooms = [room.to_dict() for room in draft.rooms]
        self.private.source_passages = [passage.to_dict() for passage in draft.passages]
        self.private.source_map_cells = [dict(cell) for cell in draft.source_map_cells]
        self.private.source_level_markers = [
            f"new_level:{draft.level}",
            f"objects:{len(source_level_objects)}",
            f"monsters:{len(self.private.source_monsters)}",
            f"traps:{len(self.private.source_traps)}",
            f"map_cells:{len(self.private.source_map_cells)}",
        ]
        self.private.dungeon_level = int(draft.level)
        self.private.max_level = int(draft.max_level)
        self.private.has_amulet = bool(draft.amulet)
        self.private.rng_seed = int(draft.rng_seed)

    def _source_level_object_index_at(self, row: int, col: int) -> int | None:
        for index, obj in enumerate(self.private.source_level_objects):
            pos = dict(obj.get("pos", {}))
            if int(pos.get("y", -1)) == row and int(pos.get("x", -1)) == col:
                return index
        return None

    def _add_source_inventory_object(self, obj: dict[str, Any]) -> str:
        obj_type = str(obj.get("type", "?"))[:1] or "?"
        which = int(obj.get("which", 0))
        group = int(obj.get("group", 0))
        flags = int(obj.get("flags", 0))
        if obj_type == SCROLL and which == S_SCARE and flags & ISFOUND:
            return "scare_dust"
        if not self.private.source_inventory:
            if not self._pack_room():
                return "no_room"
            item = self._inventory_item_from_level_object(obj)
            item["packch"] = self._next_packch()
            item["flags"] = int(item.get("flags", 0)) | ISFOUND
            self.private.source_inventory.append(item)
            if obj_type == AMULET:
                self.private.has_amulet = True
            return "added"
        insert_after: int | None = None
        index = 0
        while index < len(self.private.source_inventory):
            entry = self.private.source_inventory[index]
            if str(entry.get("type", "?"))[:1] != obj_type:
                insert_after = index
                index += 1
                continue
            while str(entry.get("type", "?"))[:1] == obj_type and int(entry.get("which", 0)) != which:
                insert_after = index
                if index + 1 == len(self.private.source_inventory):
                    break
                index += 1
                entry = self.private.source_inventory[index]
            if str(entry.get("type", "?"))[:1] == obj_type and int(entry.get("which", 0)) == which:
                if self._is_mult(obj_type):
                    if not self._pack_room():
                        return "no_room"
                    entry["count"] = int(entry.get("count", 1)) + 1
                    entry["flags"] = int(entry.get("flags", 0)) | ISFOUND
                    if obj_type == AMULET:
                        self.private.has_amulet = True
                    return "added"
                if group:
                    insert_after = index
                    while str(entry.get("type", "?"))[:1] == obj_type and int(entry.get("which", 0)) == which and int(entry.get("group", 0)) != group:
                        insert_after = index
                        if index + 1 == len(self.private.source_inventory):
                            break
                        index += 1
                        entry = self.private.source_inventory[index]
                    if str(entry.get("type", "?"))[:1] == obj_type and int(entry.get("which", 0)) == which and int(entry.get("group", 0)) == group:
                        if not self._pack_room(adjust=-1):
                            return "no_room"
                        entry["count"] = int(entry.get("count", 1)) + int(obj.get("count", 1))
                        entry["flags"] = int(entry.get("flags", 0)) | ISFOUND
                        return "added"
                else:
                    insert_after = index
            break
        if insert_after is None:
            return "added"
        if not self._pack_room():
            return "no_room"
        item = self._inventory_item_from_level_object(obj)
        item["packch"] = self._next_packch()
        item["flags"] = int(item.get("flags", 0)) | ISFOUND
        self.private.source_inventory.insert(insert_after + 1, item)
        if obj_type == AMULET:
            self.private.has_amulet = True
        return "added"

    def _inventory_item_from_level_object(self, obj: dict[str, Any]) -> dict[str, Any]:
        obj_type = str(obj.get("type", "?"))[:1] or "?"
        arm = int(obj.get("arm", 0))
        charges = int(obj.get("charges", arm if obj_type == STICK else 0))
        return {
            "id": str(obj.get("id", "object")),
            "type": obj_type,
            "which": int(obj.get("which", 0)),
            "count": int(obj.get("count", 1)),
            "flags": int(obj.get("flags", 0)),
            "arm": arm,
            "hplus": int(obj.get("hplus", 0)),
            "dplus": int(obj.get("dplus", 0)),
            "charges": charges,
            "packch": str(obj.get("packch", ""))[:1],
            "damage": str(obj.get("damage", "")),
            "hurldmg": str(obj.get("hurldmg", "")),
            "launch": int(obj.get("launch", -1)),
            "is_staff": bool(obj.get("is_staff", False)),
            "group": int(obj.get("group", 0)),
        }

    def _pack_room(self, *, adjust: int = 0) -> bool:
        inpack = self._current_inpack() + 1 + adjust
        return inpack <= MAXPACK

    def _current_inpack(self) -> int:
        total = 0
        for item in self.private.source_inventory:
            obj_type = str(item.get("type", "?"))[:1]
            if self._is_mult(obj_type):
                total += max(0, int(item.get("count", 1)))
            elif int(item.get("count", 1)) > 0:
                total += 1
        return total

    def _next_packch(self) -> str:
        used = {str(item.get("packch", ""))[:1] for item in self.private.source_inventory if str(item.get("packch", ""))}
        for offset in range(26):
            candidate = chr(ord("a") + offset)
            if candidate not in used:
                return candidate
        raise RuntimeError("Rogue pack_char exhausted")

    def _is_mult(self, obj_type: str) -> bool:
        return obj_type in {POTION, SCROLL, FOOD}

    def _source_level_monster_payload(self, level: int, index: int, monster: Any) -> dict[str, Any]:
        hp = int(monster.hp)
        return {
            "id": f"level{level}_monster{index}",
            "type": str(monster.monster_type)[:1],
            "row": int(monster.pos.y),
            "col": int(monster.pos.x),
            "level": int(monster.level),
            "hp": hp,
            "max_hp": hp,
            "flags": int(monster.flags),
            "disguise": str(monster.disguise)[:1],
            "pack": [item.to_dict() for item in monster.pack],
        }

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < len(self.public.terrain) and 0 <= col < len(self.public.terrain[0])

    def _terrain(self, row: int, col: int) -> str:
        return self.public.terrain[row][col]

    def _set_terrain(self, row: int, col: int, ch: str) -> None:
        if not self._in_bounds(row, col):
            return
        chars = list(self.public.terrain[row])
        chars[col] = ch[:1] or " "
        self.public.terrain[row] = "".join(chars)

    def _diag_ok(self, row: int, col: int, nr: int, nc: int) -> bool:
        if abs(nr - row) != 1 or abs(nc - col) != 1:
            return True
        return step_ok(self._terrain(row, nc)) and step_ok(self._terrain(nr, col))

    def _source_room_index_at(self, row: int, col: int) -> int | None:
        for index, room in enumerate(self.private.source_rooms):
            if int(room.get("flags", 0)) & SOURCE_ROOM_ISGONE:
                continue
            pos = dict(room.get("pos", {}))
            max_size = dict(room.get("max", {}))
            top = int(pos.get("y", 0))
            left = int(pos.get("x", 0))
            height = int(max_size.get("y", 0))
            width = int(max_size.get("x", 0))
            if top <= row < top + height and left <= col < left + width:
                return index
        return None

    def _source_floor_candidate_ok(self, row: int, col: int, *, monst: bool, compchar: str | None = None, avoid_hero: bool = False) -> bool:
        if not self._in_bounds(row, col):
            return False
        if avoid_hero and (row, col) == self.public.hero:
            return False
        terrain = self._terrain(row, col)
        if monst:
            return self._monster_at(row, col) is None and step_ok(terrain)
        return terrain == compchar

    def _find_source_floor(self, *, monst: bool = True, avoid_hero: bool = False) -> Position | None:
        rng = RogueRng(self.private.rng_seed)
        rooms = self.private.source_rooms
        if rooms:
            for _ in range(4096):
                room = rooms[rng.rnd(len(rooms))]
                if int(room.get("flags", 0)) & SOURCE_ROOM_ISGONE:
                    continue
                pos = dict(room.get("pos", {}))
                max_size = dict(room.get("max", {}))
                width = int(max_size.get("x", 0))
                height = int(max_size.get("y", 0))
                if width <= 2 or height <= 2:
                    continue
                col = int(pos.get("x", 0)) + rng.rnd(width - 2) + 1
                row = int(pos.get("y", 0)) + rng.rnd(height - 2) + 1
                compchar = PASSAGE if int(room.get("flags", 0)) & SOURCE_ROOM_ISMAZE else FLOOR
                if self._source_floor_candidate_ok(row, col, monst=monst, compchar=compchar, avoid_hero=avoid_hero):
                    self.private.rng_seed = rng.seed
                    return (row, col)
        candidates = [
            (row, col)
            for row, line in enumerate(self.public.terrain)
            for col, _ in enumerate(line)
            if self._source_floor_candidate_ok(row, col, monst=monst, compchar=FLOOR, avoid_hero=avoid_hero)
        ]
        if not candidates:
            self.private.rng_seed = rng.seed
            return None
        selected = candidates[rng.rnd(len(candidates))]
        self.private.rng_seed = rng.seed
        return selected

    def _apply_source_teleport(self, action: str, reason: str) -> bool:
        previous = self.public.hero
        previous_room = self._source_room_index_at(*previous)
        destination = self._find_source_floor(monst=True)
        if destination is None:
            return False
        self.public.hero = destination
        self.private.player_flags &= ~ISHELD
        self.private.vf_hit = 0
        self.private.no_move = 0
        self.private.command_count = 0
        self.private.command_running = False
        changed_room = self._source_room_index_at(*destination) != previous_room if previous_room is not None else destination != previous
        self._event(
            "action_applied",
            f"SourceTeleport({reason},{destination[0]},{destination[1]})",
            action=action,
            transition="source_teleport",
            payload={"reason": reason, "from": [previous[0], previous[1]], "to": [destination[0], destination[1]], "changed_room": changed_room},
        )
        return changed_room

    def _event(self, kind: str, message: str, *, action: str | None = None, transition: str | None = None, severity: str = "info", payload: dict[str, Any] | None = None) -> None:
        assert self.resolved is not None
        self.nev.append(step_index=self.private.step_index, episode_id=self.resolved.episode_id, kind=kind, action=action, transition=transition, severity=severity, message=message, payload=payload)

    def valid_actions(self) -> list[str]:
        return [
            "h",
            "j",
            "k",
            "l",
            "y",
            "u",
            "b",
            "n",
            ".",
            ",",
            ">",
            "s",
            "H",
            "J",
            "K",
            "L",
            "Y",
            "U",
            "B",
            "N",
            "q",
            "r",
            "e",
            "w",
            "W",
            "T",
            "P",
            "R",
            "d",
            "i",
            "I",
            "z",
            "t",
            "f",
            "F",
            "m",
            "<",
            "?",
            "/",
            "c",
            "o",
            "D",
            "S",
            ")",
            "]",
            "=",
            "@",
            "^",
            " ",
        ] if not (self.private.terminated or self.private.truncated) else []

    def symbolic_readout(self) -> dict[str, Any]:
        rows = [list(row) for row in self.public.terrain]
        for key, item in self.public.visible_items.items():
            row, col = [int(part) for part in key.split(",")]
            rows[row][col] = item
        for key, monster in self.public.visible_monsters.items():
            row, col = [int(part) for part in key.split(",")]
            rows[row][col] = monster
        row, col = self.public.hero
        rows[row][col] = "@"
        return {
            "schema": "gamebench.rogue.readout.v1",
            "env_family": self.ENV_FAMILY,
            "task_id": self.resolved.task_id if self.resolved else "",
            "public": self.public.to_dict(),
            "private": self.private.to_dict(),
            "progress_metrics": self._progress_metrics_payload(),
            "ascii": "\n".join("".join(row) for row in rows),
            "valid_actions": self.valid_actions(),
            "command_dispatch": self.command_dispatch_readout(),
            "grid_hash": self.private.config_hash,
            "nev_cursor": self.nev.cursor(),
        }

    def checkpoint_bytes(self) -> bytes:
        assert self.resolved is not None
        payload = {
            "schema_version": "gamebench.checkpoint.v1",
            "env_family": self.ENV_FAMILY,
            "episode_id": self.resolved.episode_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.nev.cursor(),
            "config_hash": self.resolved.config_hash,
            "source_state_projection": self.source_state_projection(),
            "sim": {
                "resolved": self.resolved.to_dict(),
                "public": self.public.to_dict(),
                "private": self.private.to_dict(),
                "events": self.nev.export(),
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def source_state_projection(self) -> dict[str, Any]:
        assert self.resolved is not None
        return runtime_source_checkpoint_projection(self.resolved, self.public, self.private, self.nev.cursor())

    def restore_checkpoint(self, blob: bytes) -> int:
        from task_resolve import ResolvedTask

        payload = json.loads(blob.decode("utf-8"))
        sim = payload["sim"]
        resolved = sim["resolved"]
        self.resolved = ResolvedTask(
            task_id=resolved["task_id"],
            seed=int(resolved["seed"]),
            grid=list(resolved["grid"]),
            max_steps=int(resolved["max_steps"]),
            objective=str(resolved["objective"]),
            inventory=[dict(item) for item in list(resolved.get("inventory", []))],
            monsters=[dict(monster) for monster in list(resolved.get("monsters", []))],
            traps=[dict(trap) for trap in list(resolved.get("traps", []))],
            source_map_cells=[dict(cell) for cell in list(resolved.get("source_map_cells", []))],
            level_objects=[dict(obj) for obj in list(resolved.get("level_objects", []))],
            config_hash=str(resolved["config_hash"]),
            episode_id=str(resolved["episode_id"]),
        )
        public = sim["public"]
        private = sim["private"]
        self.public = PublicState(terrain=list(public["terrain"]), hero=(int(public["hero"][0]), int(public["hero"][1])), visible_items=dict(public.get("visible_items", {})), visible_monsters=dict(public.get("visible_monsters", {})))
        self.private = PrivateState(
            step_index=int(private["step_index"]),
            total_reward=float(private["total_reward"]),
            terminated=bool(private["terminated"]),
            truncated=bool(private["truncated"]),
            terminal_reason=str(private.get("terminal_reason", "")),
            dungeon_level=int(private["dungeon_level"]),
            max_level=int(private.get("max_level", private.get("dungeon_level", 1))),
            has_amulet=bool(private.get("has_amulet", False)),
            purse=int(private["purse"]),
            food=int(private["food"]),
            hp=int(private["hp"]),
            max_hp=int(private["max_hp"]),
            rng_seed=int(private.get("rng_seed", 0)),
            item_values={str(key): int(value) for key, value in dict(private.get("item_values", {})).items()},
            source_inventory=[dict(item) for item in list(private.get("source_inventory", []))],
            left_ring_id=str(private.get("left_ring_id", "")),
            right_ring_id=str(private.get("right_ring_id", "")),
            current_weapon_id=str(private.get("current_weapon_id", "")),
            current_armor_id=str(private.get("current_armor_id", "")),
            player_flags=int(private.get("player_flags", 0)),
            strength=int(private.get("strength", 16)),
            max_strength=int(private.get("max_strength", 16)),
            no_command=int(private.get("no_command", 0)),
            no_move=int(private.get("no_move", 0)),
            food_left=int(private.get("food_left", 1300)),
            hungry_state=int(private.get("hungry_state", 0)),
            quiet=int(private.get("quiet", 0)),
            daemon_between=int(private.get("daemon_between", 0)),
            pot_known=[bool(value) for value in list(private.get("pot_known", [False] * 14))],
            ring_known=[bool(value) for value in list(private.get("ring_known", [False] * 14))],
            scr_known=[bool(value) for value in list(private.get("scr_known", [False] * 18))],
            ws_known=[bool(value) for value in list(private.get("ws_known", [False] * 14))],
            seen_tiles=[str(value) for value in list(private.get("seen_tiles", []))],
            scout_score=int(private.get("scout_score", len(list(private.get("seen_tiles", []))))),
            scout_last=int(private.get("scout_last", 0)),
            acquired_item_classes=[str(value) for value in list(private.get("acquired_item_classes", []))],
            killed_monster_types=[str(value) for value in list(private.get("killed_monster_types", []))],
            synth_shaped_reward=float(private.get("synth_shaped_reward", 0.0)),
            synth_shaped_reward_last=float(private.get("synth_shaped_reward_last", 0.0)),
            source_effect_markers=[str(value) for value in list(private.get("source_effect_markers", []))],
            source_monsters=[dict(monster) for monster in list(private.get("source_monsters", []))],
            source_combat_markers=[str(value) for value in list(private.get("source_combat_markers", []))],
            source_attack_markers=[str(value) for value in list(private.get("source_attack_markers", []))],
            source_chase_markers=[str(value) for value in list(private.get("source_chase_markers", []))],
            source_traps=[dict(trap) for trap in list(private.get("source_traps", []))],
            source_trap_markers=[str(value) for value in list(private.get("source_trap_markers", []))],
            source_map_cells=[dict(cell) for cell in list(private.get("source_map_cells", []))],
            source_daemon_actions=[dict(action) for action in list(private.get("source_daemon_actions", []))],
            source_daemon_markers=[str(value) for value in list(private.get("source_daemon_markers", []))],
            source_level_objects=[dict(obj) for obj in list(private.get("source_level_objects", []))],
            source_rooms=[dict(room) for room in list(private.get("source_rooms", []))],
            source_passages=[dict(passage) for passage in list(private.get("source_passages", []))],
            source_level_markers=[str(value) for value in list(private.get("source_level_markers", []))],
            player_exp=int(private.get("player_exp", 0)),
            player_level=int(private.get("player_level", 1)),
            player_armor=int(private.get("player_armor", 6)),
            player_damage=str(private.get("player_damage", "1x4")),
            vf_hit=int(private.get("vf_hit", 0)),
            max_hit=int(private.get("max_hit", 0)),
            kamikaze=bool(private.get("kamikaze", False)),
            command_after=bool(private.get("command_after", True)),
            command_running=bool(private.get("command_running", False)),
            command_count=int(private.get("command_count", 0)),
            command_last=str(private.get("command_last", "")),
            command_direction=str(private.get("command_direction", "")),
            command_runch=str(private.get("command_runch", "")),
            command_to_death=bool(private.get("command_to_death", False)),
            command_markers=[str(value) for value in list(private.get("command_markers", []))],
            config_hash=str(private["config_hash"]),
            episode_id=str(private["episode_id"]),
        )
        self.nev = NevLog.from_export(sim["events"])
        return self.nev.cursor()

    def clone_for_sim(self) -> "RogueEngine":
        clone = RogueEngine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone

    def command_dispatch_readout(self) -> dict[str, Any]:
        return {
            "schema": "gamebench.rogue.command_state.v1",
            "after": self.private.command_after,
            "running": self.private.command_running,
            "count": self.private.command_count,
            "last_comm": self.private.command_last,
            "direction": self.private.command_direction,
            "runch": self.private.command_runch,
            "to_death": self.private.command_to_death,
            "markers": list(self.private.command_markers),
        }

    def _apply_command_projection(self, action: str) -> dict[str, Any]:
        item_here = self._item_at_hero() is not None
        projection = runtime_command_projection(
            action,
            running=self.private.command_running,
            count=self.private.command_count,
            last_comm=self.private.command_last,
            direction=self.private.command_direction,
            item_here=item_here,
            no_command=self.private.no_command,
            dir_ch=self._direction_input(action, default="h"),
        )
        final = projection["final"]
        self.private.command_after = bool(final["after"])
        self.private.command_running = bool(final["running"])
        self.private.command_count = int(final["count"])
        self.private.command_last = str(final["last_comm"])
        self.private.command_direction = str(final["direction"])
        self.private.command_runch = str(final["runch"])
        self.private.command_to_death = bool(final["to_death"])
        self.private.command_markers = [str(marker) for marker in final["markers"]]
        self.private.no_command = int(final.get("no_command", self.private.no_command))
        return projection

    def _effective_command(self, action: str) -> str:
        index = 0
        while index < len(action) and action[index].isdigit():
            index += 1
        return action[index] if index < len(action) else "."

    def _direction_input(self, action: str, *, default: str = "h") -> str:
        index = 0
        while index < len(action) and action[index].isdigit():
            index += 1
        command = action[index] if index < len(action) else "."
        if command in {"t", "z"}:
            tail = action[index + 1 :]
            if len(tail) >= 2 and command_move_delta(tail[1]) is not None:
                return tail[1]
            if len(tail) >= 1 and command_move_delta(tail[0]) is not None:
                return tail[0]
            return default
        if index + 1 < len(action) and command_move_delta(action[index + 1]) is not None:
            return action[index + 1]
        return default

    def _item_at_hero(self) -> str | None:
        row, col = self.public.hero
        return self.public.visible_items.get(f"{row},{col}")

    def _run_source_daemon_phase(self, action: str, flag: int, phase: str) -> None:
        world = self._daemon_world()
        before = world.to_dict()
        do_daemons(world, flag)
        do_fuses(world, flag)
        after = world.to_dict()
        self._sync_daemon_world(world)
        if before != after or world.markers:
            self._event("action_applied", f"SourceDaemons({phase})", action=action, transition=f"source_daemons_{phase}", payload={"flag": flag, "world": after})
        if "death:s" in world.markers:
            self.private.hp = 0
            self.private.terminated = True
            self.private.terminal_reason = "death"
            self._event("terminal", "Terminal(death:s)", action=action, transition="death")

    def _daemon_world(self) -> DaemonWorld:
        actions = [DelayedAction(action=str(item.get("action", "")), action_type=int(item.get("type", EMPTY)), arg=int(item.get("arg", 0)), time=int(item.get("time", 0))) for item in self.private.source_daemon_actions]
        actions.extend(DelayedAction() for _ in range(max(0, 20 - len(actions))))
        return DaemonWorld(
            rng=RogueRng(self.private.rng_seed),
            stats=DaemonStats(level=self.private.player_level, hp=self.private.hp),
            max_hp=self.private.max_hp,
            quiet=self.private.quiet,
            player_flags=self.private.player_flags,
            left_ring=self._daemon_ring(self.private.left_ring_id),
            right_ring=self._daemon_ring(self.private.right_ring_id),
            food_left=self.private.food_left,
            hungry_state=self.private.hungry_state,
            no_command=self.private.no_command,
            running=self.private.command_running,
            to_death=self.private.command_to_death,
            count=self.private.command_count,
            between=self.private.daemon_between,
            actions=actions[:20],
        )

    def _sync_daemon_world(self, world: DaemonWorld) -> None:
        self.private.rng_seed = world.rng.seed
        self.private.player_level = world.stats.level
        self.private.hp = max(0, world.stats.hp)
        self.private.max_hp = max(0, world.max_hp)
        self.private.quiet = world.quiet
        self.private.player_flags = world.player_flags
        self.private.food_left = world.food_left
        self.private.hungry_state = world.hungry_state
        self.private.no_command = world.no_command
        self.private.command_running = world.running
        self.private.command_to_death = world.to_death
        self.private.command_count = world.count
        self.private.daemon_between = world.between
        self.private.source_daemon_actions = [action.to_dict() for action in world.actions if action.action_type != EMPTY]
        self.private.source_daemon_markers = list(world.markers)

    def _daemon_ring(self, item_id: str) -> DaemonRing | None:
        item = self._ring_item_by_id(item_id)
        if item is None:
            return None
        return DaemonRing(which=int(item["which"]))

    def _apply_source_fight_command(self, command: str, action: str) -> bool:
        direction = self.private.command_direction
        if not direction or direction == "\0":
            self.private.source_combat_markers = [f"no_direction:{command}"]
            self._event("action_applied", f"SourceFightNoDirection({command})", action=action, transition="source_no_direction", payload={"command": command})
            return True
        delta = command_move_delta(direction.lower())
        if delta is None:
            return False
        row, col = self.public.hero
        dy, dx = delta
        monster = self._monster_at(row + dy, col + dx)
        if monster is None:
            self.private.source_combat_markers = [f"no_monster:{command}"]
            self._event("action_applied", f"SourceFightNoMonster({command})", action=action, transition="source_no_monster", payload={"command": command, "direction": direction})
            return True
        self._fight_monster(action, monster, thrown=False)
        return True

    def _fight_monster(self, action: str, monster: dict[str, Any], *, thrown: bool, weapon: FightWeapon | None = None) -> bool:
        selected = dict(monster)
        world = FightWorld(
            rng=RogueRng(self.private.rng_seed),
            player=self._fight_player_stats(),
            player_flags=self.private.player_flags | FIGHT_ISRUN,
            current_weapon=self._current_fight_weapon(),
            count=self.private.command_count,
            to_death=self.private.command_to_death,
            level=self.private.dungeon_level,
            max_level=self.private.dungeon_level,
            max_hp=self.private.max_hp,
            vf_hit=self.private.vf_hit,
            fallpos_ok=True,
        )
        source_monster = self._fight_monster_object(monster)
        returned = source_fight(world, source_monster, weapon, thrown)
        self.private.rng_seed = world.rng.seed
        self.private.player_flags = world.player_flags
        self.private.strength = world.player.strength
        self.private.player_exp = world.player.exp
        self.private.player_level = world.player.level
        self.private.player_armor = world.player.arm
        self.private.hp = max(0, world.player.hp)
        self.private.max_hp = max(0, world.max_hp)
        self.private.command_count = world.count
        self.private.command_to_death = world.to_death
        self.private.vf_hit = world.vf_hit
        self.private.source_combat_markers = list(world.markers)
        if world.monster_present and source_monster.stats.hp > 0:
            self._sync_monster(monster["id"], source_monster)
        else:
            self._remove_monster(monster["id"])
        self._event(
            "action_applied",
            f"SourceFight({selected['id']})",
            action=action,
            transition="source_fight",
            payload={"monster": selected, "returned": returned, "world": world.to_dict(), "result_monster": source_monster.to_dict(), "monsters": [dict(entry) for entry in self.private.source_monsters]},
        )
        return returned

    def _fight_player_stats(self) -> FightStats:
        return FightStats(
            strength=self.private.strength,
            exp=self.private.player_exp,
            level=self.private.player_level,
            arm=self.private.player_armor,
            hp=self.private.hp,
            damage=self._current_player_damage(),
            max_hp=self.private.max_hp,
            flags=FIGHT_ISRUN,
        )

    def _fight_monster_object(self, monster: dict[str, Any]) -> FightMonster:
        return FightMonster(
            monster_type=str(monster["type"])[:1],
            stats=FightStats(
                strength=int(monster.get("strength", 16)),
                exp=int(monster.get("exp", 1)),
                level=int(monster.get("level", 1)),
                arm=int(monster.get("arm", 6)),
                hp=int(monster.get("hp", 1)),
                damage=str(monster.get("damage", "1x1")),
                max_hp=int(monster.get("max_hp", monster.get("hp", 1))),
                flags=int(monster.get("stats_flags", FIGHT_ISRUN)),
            ),
            flags=int(monster.get("flags", FIGHT_ISRUN)),
            disguise=str(monster.get("disguise", monster.get("type", "K")))[:1],
            pack=[FightObject(obj_type=str(obj.get("type", obj.get("obj_type", GOLD)))[:1], name=str(obj.get("name", obj.get("id", "object"))), goldval=int(obj.get("goldval", 0))) for obj in list(monster.get("pack", []))],
            oldch=str(monster.get("oldch", "."))[:1],
        )

    def _sync_monster(self, monster_id: str, monster: FightMonster) -> None:
        for entry in self.private.source_monsters:
            if entry["id"] == monster_id:
                entry["type"] = monster.monster_type
                entry["hp"] = monster.stats.hp
                entry["max_hp"] = monster.stats.max_hp
                entry["strength"] = monster.stats.strength
                entry["exp"] = monster.stats.exp
                entry["level"] = monster.stats.level
                entry["arm"] = monster.stats.arm
                entry["damage"] = monster.stats.damage
                entry["stats_flags"] = monster.stats.flags
                entry["flags"] = monster.flags
                entry["disguise"] = monster.disguise or monster.monster_type
                entry["oldch"] = monster.oldch
                entry["pack"] = [obj.to_dict() for obj in monster.pack]
                break
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)

    def _remove_monster(self, monster_id: str) -> None:
        for entry in self.private.source_monsters:
            if entry["id"] == monster_id:
                self._record_killed_monster_type(str(entry.get("type", ""))[:1])
                break
        self.private.source_monsters = [entry for entry in self.private.source_monsters if entry["id"] != monster_id]
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)

    def _monster_at(self, row: int, col: int) -> dict[str, Any] | None:
        key = f"{row},{col}"
        for monster in self.private.source_monsters:
            if f"{monster['row']},{monster['col']}" == key:
                return monster
        return None

    def _trap_at(self, row: int, col: int) -> dict[str, Any] | None:
        for trap in self.private.source_traps:
            if int(trap["row"]) == row and int(trap["col"]) == col:
                return trap
        return None

    def _apply_source_trap(self, action: str, *, previous: Position) -> int | None:
        row, col = self.public.hero
        trap = self._trap_at(row, col)
        if trap is None and self._terrain(row, col) != "^":
            return None
        if trap is None:
            trap = {"id": f"trap{len(self.private.source_traps)}", "row": row, "col": col, "kind": T_MYST, "flags": TRAP_F_REAL | T_MYST}
            self.private.source_traps.append(trap)
        state = SourceTrapState(
            rng=RogueRng(self.private.rng_seed),
            level=self.private.dungeon_level,
            no_move=self.private.no_move,
            no_command=self.private.no_command,
            player_flags=self.private.player_flags,
            stats=SourceTrapStats(
                strength=self.private.strength,
                max_strength=self.private.max_strength,
                level=self.private.player_level,
                arm=self.private.player_armor,
                hp=self.private.hp,
                max_hp=self.private.max_hp,
            ),
            cell=SourceTrapCell("^", int(trap.get("flags", TRAP_F_REAL | int(trap.get("kind", T_MYST))))),
            running=self.private.command_running,
            count=self.private.command_count != 0,
            weapon_group=int(trap.get("weapon_group", 1)),
            hero_y=row,
            hero_x=col,
            left_ring=self._trap_ring(self.private.left_ring_id),
            right_ring=self._trap_ring(self.private.right_ring_id),
            armor=self._trap_armor(),
        )
        returned = source_be_trapped(state)
        trap["flags"] = state.cell.flags
        trap["ch"] = state.cell.ch
        trap["weapon_group"] = state.weapon_group
        self._sync_source_trap_state(state)
        if returned == T_DOOR:
            self.public.hero = previous
        elif returned == T_TELEP:
            self._apply_source_teleport(action, "trap")
        self._event(
            "action_applied",
            f"SourceTrap({returned})",
            action=action,
            transition="source_trap",
            payload={"trap": dict(trap), "returned": returned, "state": state.to_dict()},
        )
        if returned == T_DOOR:
            self._apply_source_new_level(action, reason="trapdoor", level=self.private.dungeon_level)
        if state.terminal:
            self.private.terminated = True
            self.private.terminal_reason = "death"
            self._event("terminal", "Terminal(death)", action=action, transition="death")
        return returned

    def _sync_source_trap_state(self, state: SourceTrapState) -> None:
        self.private.rng_seed = state.rng.seed
        self.private.dungeon_level = state.level
        self.private.no_move = state.no_move
        self.private.no_command = state.no_command
        self.private.player_flags = state.player_flags
        self.private.strength = state.stats.strength
        self.private.max_strength = state.stats.max_strength
        self.private.player_level = state.stats.level
        self.private.player_armor = state.stats.arm
        self.private.hp = max(0, state.stats.hp)
        self.private.max_hp = max(0, state.stats.max_hp)
        self.private.command_running = state.running
        if not state.count:
            self.private.command_count = 0
        self.private.source_trap_markers = list(state.markers or [])
        if state.arrow is not None:
            self.public.visible_items[f"{state.arrow.y},{state.arrow.x}"] = state.arrow.obj_type or WEAPON
        if state.armor is not None:
            armor_item = self._inventory_item_by_id(self.private.current_armor_id)
            if armor_item is not None:
                armor_item["which"] = state.armor.which
                armor_item["arm"] = state.armor.arm
                armor_item["flags"] = state.armor.flags
                self.private.player_armor = state.armor.arm

    def _trap_ring(self, item_id: str) -> SourceTrapRing | None:
        item = self._ring_item_by_id(item_id)
        if item is None:
            return None
        return SourceTrapRing(which=int(item["which"]), arm=int(item["arm"]))

    def _trap_armor(self) -> SourceTrapArmor | None:
        item = self._inventory_item_by_id(self.private.current_armor_id)
        if item is None:
            return None
        return SourceTrapArmor(obj_type=ARMOR, which=int(item["which"]), arm=int(item["arm"]), flags=int(item["flags"]))

    def _visible_monsters(self, monsters: list[dict[str, Any]]) -> dict[str, str]:
        return {f"{monster['row']},{monster['col']}": str(monster["type"])[:1] for monster in monsters if int(monster.get("hp", 1)) > 0}

    def _run_source_monster_turns(self, action: str) -> None:
        skip_attack_ids = self._run_source_chase_turns(action)
        if not (self.private.terminated or self.private.truncated):
            self._run_adjacent_monster_attacks(action, skip_attack_ids=skip_attack_ids)

    def _run_source_chase_turns(self, action: str) -> set[str]:
        markers: list[str] = []
        moved_adjacent_ids: set[str] = set()
        attack_ready_ids: set[str] = set()
        for stale_monster in list(self.private.source_monsters):
            monster_id = str(stale_monster["id"])
            monster = self._monster_by_id(monster_id)
            if monster is None or int(monster.get("hp", 1)) <= 0 or self._is_adjacent_to_hero(monster):
                continue
            thing = self._chase_thing_object(monster)
            schedule = move_monst_schedule(thing, [0, 0])
            outcomes: list[dict[str, Any]] = []
            for _ in range(int(schedule["calls"])):
                current = self._monster_by_id(monster_id)
                if current is None:
                    break
                if self._is_adjacent_to_hero(current):
                    attack_ready_ids.add(monster_id)
                    break
                thing.pos = ChaseCoord(int(current["row"]), int(current["col"]))
                hero = ChaseCoord(*self.public.hero)
                target = self._do_chase_target(current)
                rng = RogueRng(self.private.rng_seed)
                outcome = source_chase(rng, self._chase_map(monster_id), thing, target, hero)
                self.private.rng_seed = int(outcome["rng_seed"])
                old_row = int(current["row"])
                old_col = int(current["col"])
                do_world, do_monster = self._do_chase_runtime_state(current, outcome)
                returned = source_do_chase(do_world, do_monster)
                self._sync_do_chase_state(monster_id, do_monster, do_world)
                thing = self._chase_thing_object(self._monster_by_id(monster_id) or current)
                do_markers = [str(marker) for marker in do_world.markers]
                if "attack" in do_markers:
                    attack_ready_ids.add(monster_id)
                final_after_do = self._monster_by_id(monster_id) or current
                if "relocate" in do_markers and self._is_adjacent_to_hero(final_after_do):
                    moved_adjacent_ids.add(monster_id)
                outcomes.append({"chase": outcome, "do_chase": do_world.to_dict(), "result_monster": do_monster.to_dict(), "returned": returned})
                final = self._monster_by_id(monster_id) or current
                keep = str(bool(outcome["keep_chasing"])).lower()
                markers.append(f"{monster_id}:{old_row},{old_col}->{final['row']},{final['col']}:keep={keep}:do={','.join(do_markers)}")
            self._sync_chase_monster(monster_id, thing)
            if int(schedule["calls"]) == 0:
                markers.append(f"{monster_id}:schedule:0")
            if outcomes or int(schedule["calls"]) == 0:
                self._event("action_applied", f"SourceChase({monster_id})", action=action, transition="source_chase", payload={"monster": dict(stale_monster), "schedule": schedule, "outcomes": outcomes, "monsters": [dict(entry) for entry in self.private.source_monsters]})
        self.private.source_chase_markers = markers
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)
        return moved_adjacent_ids - attack_ready_ids

    def _monster_by_id(self, monster_id: str) -> dict[str, Any] | None:
        for monster in self.private.source_monsters:
            if str(monster["id"]) == monster_id:
                return monster
        return None

    def _chase_thing_object(self, monster: dict[str, Any]) -> ChaseThing:
        return ChaseThing(
            monster_type=str(monster["type"])[:1],
            pos=ChaseCoord(int(monster["row"]), int(monster["col"])),
            flags=int(monster.get("flags", FIGHT_ISRUN)),
            turn=bool(monster.get("turn", True)),
            disguise=str(monster.get("disguise", monster["type"]))[:1],
        )

    def _sync_chase_monster(self, monster_id: str, thing: ChaseThing) -> None:
        monster = self._monster_by_id(monster_id)
        if monster is None:
            return
        monster["flags"] = thing.flags
        monster["turn"] = thing.turn
        monster["disguise"] = thing.disguise or monster["type"]
        monster["row"] = thing.pos.y
        monster["col"] = thing.pos.x

    def _do_chase_target(self, monster: dict[str, Any]) -> ChaseCoord:
        dest = self._monster_dest_coord(monster)
        monster_room = int(monster.get("room", 0))
        dest_kind = str(monster.get("dest_kind", monster.get("dest", "hero")))
        ree_index = int(monster.get("proom", monster_room)) if dest_kind == "hero" else int(monster.get("dest_room", monster_room))
        if monster_room == ree_index:
            return ChaseCoord(dest.y, dest.x)
        exits = self._monster_room_exits(monster)
        if not exits:
            return ChaseCoord(dest.y, dest.x)
        return min(exits, key=lambda coord: (dest.x - coord.x) * (dest.x - coord.x) + (dest.y - coord.y) * (dest.y - coord.y))

    def _do_chase_runtime_state(self, monster: dict[str, Any], chase_outcome: dict[str, Any]) -> tuple[DoChaseWorld, DoChaseMonster]:
        hero = DoChaseCoord(*self.public.hero)
        monster_room = int(monster.get("room", 0))
        dest_kind = str(monster.get("dest_kind", monster.get("dest", "hero")))
        dest = self._monster_dest_coord(monster, coord_type=DoChaseCoord)
        dest_room = int(monster.get("dest_room", monster_room))
        proom = int(monster.get("proom", monster_room))
        rooms = {monster_room: DoChaseRoom(monster_room, int(monster.get("room_goldval", 1)), int(monster.get("room_flags", 0)), [DoChaseCoord(coord.y, coord.x) for coord in self._monster_room_exits(monster)])}
        rooms.setdefault(dest_room, DoChaseRoom(dest_room, int(monster.get("dest_room_goldval", 0)), int(monster.get("dest_room_flags", 0)), [DoChaseCoord(dest.y, dest.x)]))
        rooms.setdefault(proom, DoChaseRoom(proom, 0, 0, [hero]))
        passage_index = int(monster.get("passage_index", 9))
        passages = {passage_index: DoChaseRoom(passage_index, 0, int(monster.get("passage_flags", 0o000002)), [])}
        objects = [DoChaseObject(item, DoChaseCoord(*[int(part) for part in key.split(",")])) for key, item in self.public.visible_items.items()]
        chosen = chase_outcome["chosen"]
        world = DoChaseWorld(
            rng=RogueRng(self.private.rng_seed),
            hero=hero,
            proom=proom,
            rooms=rooms,
            passages=passages,
            objects=objects,
            terrain={(int(monster["row"]), int(monster["col"])): self._terrain(int(monster["row"]), int(monster["col"]))},
            dest_room=dest_room,
            passage_index=passage_index,
            chase_keep=bool(chase_outcome["keep_chasing"]),
            chase_pos=DoChaseCoord(int(chosen["y"]), int(chosen["x"])),
            chase_room=int(monster.get("chase_room", monster_room)),
            attack_return=0,
            find_dest_kind=str(monster.get("find_dest_kind", "hero")),
            find_dest_pos=self._monster_find_dest_coord(monster),
            running=self.private.command_running,
            count=self.private.command_count,
            quiet=0,
            has_hit=bool(monster.get("has_hit", False)),
            to_death=self.private.command_to_death,
            kamikaze=self.private.kamikaze,
        )
        source_monster = DoChaseMonster(
            monster_type=str(monster["type"])[:1],
            pos=DoChaseCoord(int(monster["row"]), int(monster["col"])),
            room=monster_room,
            flags=int(monster.get("flags", FIGHT_ISRUN)),
            dest_kind=dest_kind,
            dest_pos=dest,
            pack=[DoChaseObject(str(obj.get("type", obj.get("obj_type", GOLD)))[:1], self._pack_object_coord(obj)) for obj in list(monster.get("pack", []))],
        )
        return world, source_monster

    def _sync_do_chase_state(self, monster_id: str, source_monster: DoChaseMonster, world: DoChaseWorld) -> None:
        self.private.rng_seed = world.rng.seed
        self.private.command_running = world.running
        self.private.command_count = world.count
        self.private.command_to_death = world.to_death
        self.private.kamikaze = world.kamikaze
        remaining_objects = {f"{obj.pos.y},{obj.pos.x}" for obj in world.objects}
        for key in list(self.public.visible_items):
            if key not in remaining_objects:
                self.public.visible_items.pop(key, None)
                self.private.item_values.pop(key, None)
        monster = self._monster_by_id(monster_id)
        if monster is None:
            return
        monster["type"] = source_monster.monster_type
        monster["row"] = source_monster.pos.y
        monster["col"] = source_monster.pos.x
        monster["room"] = source_monster.room
        monster["flags"] = source_monster.flags
        monster["dest_kind"] = source_monster.dest_kind
        monster["dest_row"] = source_monster.dest_pos.y
        monster["dest_col"] = source_monster.dest_pos.x
        monster["pack"] = [obj.to_dict() for obj in source_monster.pack]

    def _monster_dest_coord(self, monster: dict[str, Any], coord_type: type[ChaseCoord] | type[DoChaseCoord] = ChaseCoord) -> ChaseCoord | DoChaseCoord:
        if str(monster.get("dest_kind", monster.get("dest", "hero"))) == "hero":
            return coord_type(*self.public.hero)
        if "dest_pos" in monster:
            return coord_type(int(monster["dest_pos"][0]), int(monster["dest_pos"][1]))
        return coord_type(int(monster.get("dest_row", self.public.hero[0])), int(monster.get("dest_col", self.public.hero[1])))

    def _monster_find_dest_coord(self, monster: dict[str, Any]) -> DoChaseCoord:
        if "find_dest_pos" in monster:
            return DoChaseCoord(int(monster["find_dest_pos"][0]), int(monster["find_dest_pos"][1]))
        return DoChaseCoord(int(monster.get("find_dest_row", self.public.hero[0])), int(monster.get("find_dest_col", self.public.hero[1])))

    def _monster_room_exits(self, monster: dict[str, Any]) -> list[ChaseCoord]:
        return [ChaseCoord(int(coord[0]), int(coord[1])) for coord in list(monster.get("room_exits", []))]

    def _pack_object_coord(self, obj: dict[str, Any]) -> DoChaseCoord:
        pos = obj.get("pos", {})
        if isinstance(pos, dict):
            return DoChaseCoord(int(pos.get("y", 0)), int(pos.get("x", 0)))
        if isinstance(pos, list) and len(pos) >= 2:
            return DoChaseCoord(int(pos[0]), int(pos[1]))
        return DoChaseCoord(0, 0)

    def _chase_map(self, selected_id: str) -> ChaseMap:
        terrain: dict[tuple[int, int], str] = {}
        for row in range(NUMLINES):
            source_row = self.public.terrain[row] if row < len(self.public.terrain) else ""
            for col in range(NUMCOLS):
                terrain[(row, col)] = source_row[col] if col < len(source_row) else " "
        objects = []
        for key, item in self.public.visible_items.items():
            row, col = [int(part) for part in key.split(",")]
            objects.append(SourceChaseObject(item, 0, ChaseCoord(row, col)))
        monsters = [
            self._chase_thing_object(monster)
            for monster in self.private.source_monsters
            if int(monster.get("hp", 1)) > 0 and str(monster["id"]) != selected_id
        ]
        return ChaseMap(terrain=terrain, objects=objects, monsters=monsters)

    def _run_adjacent_monster_attacks(self, action: str, *, skip_attack_ids: set[str] | None = None) -> None:
        skip_attack_ids = skip_attack_ids or set()
        attacks: list[dict[str, Any]] = []
        for monster in list(self.private.source_monsters):
            if str(monster["id"]) in skip_attack_ids:
                continue
            if not self._is_adjacent_to_hero(monster):
                continue
            selected = dict(monster)
            source_monster = self._attack_monster_object(monster)
            world = self._attack_world()
            returned = source_attack(world, source_monster)
            self._sync_attack_world(world)
            if returned < 0:
                self._remove_monster(monster["id"])
            else:
                self._sync_attack_monster(monster["id"], source_monster)
            attack_payload = {"monster": selected, "returned": returned, "world": world.to_dict(), "result_monster": source_monster.to_dict()}
            attacks.append(attack_payload)
            self._event("action_applied", f"SourceAttack({selected['id']})", action=action, transition="source_attack", payload=attack_payload)
            if self.private.hp <= 0:
                self.private.terminated = True
                self.private.terminal_reason = "death"
                self._event("terminal", "Terminal(death)", action=action, transition="death")
                break
        if attacks:
            self.private.source_attack_markers = [marker for attack in attacks for marker in attack["world"]["markers"]]

    def _is_adjacent_to_hero(self, monster: dict[str, Any]) -> bool:
        row, col = self.public.hero
        return max(abs(int(monster["row"]) - row), abs(int(monster["col"]) - col)) == 1

    def _attack_world(self) -> AttackWorld:
        return AttackWorld(
            rng=RogueRng(self.private.rng_seed),
            player=AttackStats(
                strength=self.private.strength,
                exp=self.private.player_exp,
                level=self.private.player_level,
                arm=self.private.player_armor,
                hp=self.private.hp,
                damage=self.private.player_damage,
                max_hp=self.private.max_hp,
                flags=FIGHT_ISRUN,
            ),
            player_flags=self.private.player_flags | FIGHT_ISRUN,
            current_armor_arm=self.private.player_armor if self.private.current_armor_id else None,
            left_ring=self._attack_ring(self.private.left_ring_id),
            right_ring=self._attack_ring(self.private.right_ring_id),
            sustain_strength=self._wearing_ring(2),
            running=self.private.command_running,
            count=self.private.command_count,
            quiet=0,
            to_death=self.private.command_to_death,
            kamikaze=self.private.kamikaze,
            max_hit=self.private.max_hit,
            no_command=self.private.no_command,
            purse=self.private.purse,
            level=self.private.dungeon_level,
            max_hp=self.private.max_hp,
            vf_hit=self.private.vf_hit,
            pack=self._attack_pack(),
        )

    def _sync_attack_world(self, world: AttackWorld) -> None:
        self.private.rng_seed = world.rng.seed
        self.private.player_flags = world.player_flags
        self.private.strength = world.player.strength
        self.private.player_exp = world.player.exp
        self.private.player_level = world.player.level
        self.private.player_armor = world.player.arm
        self.private.hp = max(0, world.player.hp)
        self.private.max_hp = max(0, world.max_hp)
        self.private.command_running = world.running
        self.private.command_count = world.count
        self.private.command_to_death = world.to_death
        self.private.kamikaze = world.kamikaze
        self.private.max_hit = world.max_hit
        self.private.no_command = world.no_command
        self.private.purse = max(0, world.purse)
        self.private.vf_hit = world.vf_hit
        self._sync_attack_inventory(world.pack)

    def _attack_monster_object(self, monster: dict[str, Any]) -> AttackMonster:
        return AttackMonster(
            monster_type=str(monster["type"])[:1],
            stats=AttackStats(
                strength=int(monster.get("strength", 16)),
                exp=int(monster.get("exp", 1)),
                level=int(monster.get("level", 1)),
                arm=int(monster.get("arm", 6)),
                hp=int(monster.get("hp", 1)),
                damage=str(monster.get("damage", "1x1")),
                max_hp=int(monster.get("max_hp", monster.get("hp", 1))),
                flags=int(monster.get("stats_flags", FIGHT_ISRUN)),
            ),
            flags=int(monster.get("flags", FIGHT_ISRUN)),
            disguise=str(monster.get("disguise", monster.get("type", "K")))[:1],
        )

    def _sync_attack_monster(self, monster_id: str, monster: AttackMonster) -> None:
        for entry in self.private.source_monsters:
            if entry["id"] == monster_id:
                entry["type"] = monster.monster_type
                entry["hp"] = monster.stats.hp
                entry["max_hp"] = monster.stats.max_hp
                entry["strength"] = monster.stats.strength
                entry["exp"] = monster.stats.exp
                entry["level"] = monster.stats.level
                entry["arm"] = monster.stats.arm
                entry["damage"] = monster.stats.damage
                entry["stats_flags"] = monster.stats.flags
                entry["flags"] = monster.flags
                entry["disguise"] = monster.disguise or monster.monster_type
                break
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)

    def _attack_ring(self, item_id: str) -> AttackRing | None:
        item = self._ring_item_by_id(item_id)
        if item is None:
            return None
        return AttackRing(which=int(item["which"]), arm=int(item["arm"]))

    def _wearing_ring(self, which: int) -> bool:
        return any(item is not None and int(item["which"]) == which for item in (self._ring_item_by_id(self.private.left_ring_id), self._ring_item_by_id(self.private.right_ring_id)))

    def _attack_pack(self) -> list[AttackItem]:
        return [
            AttackItem(name=str(item["id"]), obj_type=str(item["type"])[:1], magic=self._is_magic_attack_item(item), equipped=item["id"] in {self.private.left_ring_id, self.private.right_ring_id, self.private.current_weapon_id, self.private.current_armor_id})
            for item in self.private.source_inventory
        ]

    def _sync_attack_inventory(self, pack: list[AttackItem]) -> None:
        remaining_names = {item.name for item in pack}
        equipped = {self.private.left_ring_id, self.private.right_ring_id, self.private.current_weapon_id, self.private.current_armor_id}
        self.private.source_inventory = [item for item in self.private.source_inventory if str(item["id"]) in remaining_names or item["id"] in equipped]

    def _is_magic_attack_item(self, item: dict[str, Any]) -> bool:
        if item["type"] in {"!", "?", "/", "=", ","}:
            return True
        if item["type"] in {")", "]"}:
            return bool(item.get("hplus", 0) or item.get("dplus", 0) or item.get("arm", 0) or item.get("flags", 0))
        return False

    def _apply_source_item_command(self, command: str, action: str) -> bool:
        if command == "w":
            current = self._inventory_item_by_id(self.private.current_weapon_id)
            if current is not None and int(current.get("flags", 0)) & ISCURSED:
                self.private.source_effect_markers = ["cursed"]
                self._event("action_applied", f"SourceWieldBlocked({current['id']})", action=action, transition="source_wield_blocked", payload={"item": dict(current), "markers": list(self.private.source_effect_markers)})
                return True
            item = self._inventory_item_for_action(action, WEAPON)
            if item is None:
                return self._source_no_item(command, action)
            if item["id"] == self.private.current_weapon_id:
                self.private.command_after = False
                self.private.source_effect_markers = ["in_use"]
                self._event("action_applied", f"SourceWieldCurrent({item['id']})", action=action, transition="source_wield_current", payload={"item": dict(item), "markers": list(self.private.source_effect_markers)})
                return True
            self.private.current_weapon_id = str(item["id"])
            self.private.source_effect_markers = ["wield"]
            self._event("action_applied", f"SourceWield({item['id']})", action=action, transition="source_wield", payload={"item": dict(item), "current_weapon_id": self.private.current_weapon_id})
            return True
        if command == "W":
            if self.private.current_armor_id:
                self.private.command_after = False
                current = self._inventory_item_by_id(self.private.current_armor_id)
                self.private.source_effect_markers = ["already_wearing"]
                self._event("action_applied", f"SourceWearBlocked({self.private.current_armor_id})", action=action, transition="source_wear_blocked", payload={"item": dict(current) if current is not None else None, "markers": list(self.private.source_effect_markers)})
                return True
            item = self._inventory_item_for_action(action, ARMOR)
            if item is None:
                return self._source_no_item(command, action)
            item["flags"] = int(item.get("flags", 0)) | ISKNOW
            self.private.current_armor_id = str(item["id"])
            self.private.player_armor = int(item.get("arm", self.private.player_armor))
            self.private.source_effect_markers = ["wear"]
            self._event("action_applied", f"SourceWear({item['id']})", action=action, transition="source_wear", payload={"item": dict(item), "current_armor_id": self.private.current_armor_id})
            return True
        if command == "T":
            item = self._inventory_item_by_id(self.private.current_armor_id)
            if item is None:
                self.private.command_after = False
                return self._source_no_item(command, action)
            if int(item.get("flags", 0)) & ISCURSED:
                self.private.source_effect_markers = ["cursed"]
                self._event("action_applied", f"SourceTakeOffBlocked({item['id']})", action=action, transition="source_takeoff_blocked", payload={"item": dict(item), "markers": list(self.private.source_effect_markers)})
                return True
            self.private.current_armor_id = ""
            self.private.player_armor = 6
            self.private.source_effect_markers = ["take_off"]
            self._event("action_applied", f"SourceTakeOff({item['id']})", action=action, transition="source_takeoff", payload={"item": dict(item), "current_armor_id": ""})
            return True
        if command == "t":
            item = self._directional_inventory_item_for_action(action, WEAPON)
            if item is None:
                return self._source_no_item(command, action)
            selected = dict(item)
            if not self._dropcheck_item(item):
                self._event("action_applied", f"SourceThrowBlocked({item['id']})", action=action, transition="source_throw_blocked", payload={"item": dict(item), "markers": list(self.private.source_effect_markers)})
                return True
            thrown = self._leave_inventory_for_throw(item)
            direction = self._missile_direction()
            impact_row, impact_col, monster = self._projectile_impact(direction)
            hit = False
            if monster is not None:
                hit = self._fight_monster(action, monster, thrown=True, weapon=self._fight_weapon(thrown))
            fall_result = None
            if not hit:
                fall_result = self._fall_projectile(thrown, impact_row, impact_col)
            markers = ["leave_pack", f"missile:{direction}", "hit" if hit else str(fall_result)]
            self.private.source_effect_markers = markers
            self._event(
                "action_applied",
                f"SourceThrow({thrown['id']})",
                action=action,
                transition="source_throw",
                payload={
                    "item": selected,
                    "thrown": dict(thrown),
                    "direction": direction,
                    "impact": [impact_row, impact_col],
                    "hit": hit,
                    "fall_result": fall_result,
                    "inventory": [dict(entry) for entry in self.private.source_inventory],
                    "level_objects": [dict(obj) for obj in self.private.source_level_objects],
                    "markers": markers,
                },
            )
            return True
        if command == "d":
            item = self._inventory_item_for_action(action)
            if item is None:
                return self._source_no_item(command, action)
            row, col = self.public.hero
            key = f"{row},{col}"
            if self._terrain(row, col) not in {FLOOR, PASSAGE} or key in self.public.visible_items:
                self.private.command_after = False
                self._event("rule_violation", "RuleViolation(drop_occupied)", action=action, transition="drop_blocked", severity="warn", payload={"hero": [row, col], "terrain": self._terrain(row, col)})
                return True
            if not self._dropcheck_item(item):
                self._event("action_applied", f"SourceDropBlocked({item['id']})", action=action, transition="source_drop_blocked", payload={"item": dict(item), "markers": list(self.private.source_effect_markers)})
                return True
            dropped = self._leave_inventory_for_drop(item)
            dropped["pos"] = {"y": row, "x": col}
            self.private.source_level_objects.insert(0, dropped)
            self.public.visible_items[key] = str(dropped["type"])[:1]
            if dropped["type"] == AMULET:
                self.private.has_amulet = False
            self.private.source_effect_markers = ["leave_pack", "drop"]
            self._event(
                "action_applied",
                f"SourceDrop({dropped['id']})",
                action=action,
                transition="source_drop",
                payload={"item": dict(dropped), "inventory": [dict(entry) for entry in self.private.source_inventory], "level_objects": [dict(obj) for obj in self.private.source_level_objects]},
            )
            return True
        if command == "e":
            item = self._inventory_item_for_action(action, FOOD)
            if item is None:
                return self._source_no_item(command, action)
            selected = dict(item)
            rng = RogueRng(self.private.rng_seed)
            if self.private.food_left < 0:
                self.private.food_left = 0
            food_add = HUNGERTIME - 200 + rng.rnd(400)
            self.private.food_left = min(self.private.food_left + food_add, STOMACHSIZE)
            self.private.hungry_state = 0
            markers = ["eat_fruit" if int(item.get("which", 0)) == 1 else "eat_food"]
            trace: dict[str, Any] = {"food_add": food_add}
            if int(item.get("which", 0)) != 1:
                taste_roll = rng.rnd(100)
                trace["taste_roll"] = taste_roll
                if taste_roll > 70:
                    self.private.player_exp += 1
                    markers.append("awful")
                    level_add = self._check_player_level(rng)
                    if level_add:
                        markers.append(f"welcome:{self.private.player_level}")
                        trace["level_add"] = level_add
                else:
                    markers.append("good")
            self.private.rng_seed = rng.seed
            self.private.source_effect_markers = markers
            self._decrement_or_remove_item(item)
            self._event(
                "action_applied",
                f"SourceEat({selected['id']})",
                action=action,
                transition="source_eat",
                payload={"item": selected, "markers": markers, "trace": trace, "inventory": [dict(entry) for entry in self.private.source_inventory], "food_left": self.private.food_left},
            )
            return True
        if command == "q":
            item = self._inventory_item_for_action(action, "!")
            if item is None:
                return self._source_no_item(command, action)
            selected = dict(item)
            world = PotionWorld(
                rng=RogueRng(self.private.rng_seed),
                player_flags=self.private.player_flags,
                strength=self.private.strength,
                max_strength=self.private.max_strength,
                level=self.private.dungeon_level,
                exp=self.private.purse,
                hp=self.private.hp,
                max_hp=self.private.max_hp,
                no_command=self.private.no_command,
                after=self.private.command_after,
                current_weapon_is_obj=self.private.current_weapon_id == item["id"],
                left_ring=self._potion_source_ring(self.private.left_ring_id),
                right_ring=self._potion_source_ring(self.private.right_ring_id),
                pot_known=list(self.private.pot_known),
            )
            quaff(world, self._potion_object(item))
            self.private.rng_seed = world.rng.seed
            self.private.player_flags = world.player_flags
            self.private.strength = world.strength
            self.private.max_strength = world.max_strength
            self.private.hp = world.hp
            self.private.max_hp = world.max_hp
            self.private.no_command = world.no_command
            self.private.command_after = world.after
            self.private.pot_known = list(world.pot_known)
            self.private.source_effect_markers = list(world.markers)
            if world.current_weapon_is_obj is False and "unwield_potion" in world.markers:
                self.private.current_weapon_id = ""
            self._decrement_or_remove_item(item)
            self._source_effect_event(command, selected, world.to_dict(), action)
            return True
        if command == "r":
            item = self._inventory_item_for_action(action, "?")
            if item is None:
                return self._source_no_item(command, action)
            selected = dict(item)
            world = ScrollWorld(
                rng=RogueRng(self.private.rng_seed),
                player_flags=self.private.player_flags,
                no_command=self.private.no_command,
                current_weapon_is_obj=self.private.current_weapon_id == item["id"],
                current_weapon=self._scroll_item_from_inventory(self._inventory_item_by_id(self.private.current_weapon_id)),
                current_armor=self._scroll_item_from_inventory(self._inventory_item_by_id(self.private.current_armor_id)),
                left_ring=self._scroll_ring_item(self.private.left_ring_id),
                right_ring=self._scroll_ring_item(self.private.right_ring_id),
                food_count=self._food_count_for_scrolls(),
                scr_known=list(self.private.scr_known),
            )
            read_scroll(world, self._scroll_object(item))
            self.private.rng_seed = world.rng.seed
            self.private.player_flags = world.player_flags
            self.private.no_command = world.no_command
            self.private.scr_known = list(world.scr_known)
            if "teleport" in world.markers:
                changed_room = self._apply_source_teleport(action, "scroll")
                world.teleport_room_changed = changed_room
                if changed_room and len(self.private.scr_known) > S_TELEP:
                    self.private.scr_known[S_TELEP] = True
                    world.scr_known = list(self.private.scr_known)
            if world.current_weapon_is_obj is False and "unwield_scroll" in world.markers:
                self.private.current_weapon_id = ""
            self._sync_scroll_equipment(world)
            self._apply_source_whatis_for_scroll(selected, action, world)
            self.private.source_effect_markers = list(world.markers)
            self._decrement_or_remove_item(item)
            self._source_effect_event(command, selected, world.to_dict(), action)
            return True
        if command == "z":
            item = self._directional_inventory_item_for_action(action, STICK)
            if item is None:
                return self._source_no_item(command, action)
            selected = dict(item)
            obj = self._stick_object(item)
            target_id = self._zap_target_id()
            drain_ids = [str(monster["id"]) for monster in self.private.source_monsters if int(monster.get("hp", 1)) > 0]
            rng = RogueRng(self.private.rng_seed)
            save_throw_success = False
            if target_id is not None and int(item.get("which", 0)) == 6:
                save_payload = self._source_save_throw(rng, 3, self.private.player_level)
                save_throw_success = bool(save_payload["saved"])
            world = StickWorld(
                rng=rng,
                after=self.private.command_after,
                player_flags=self.private.player_flags,
                hero_hp=self.private.hp,
                current_weapon_which=self._current_weapon_which(),
                target=self._stick_monster(self._monster_by_id(target_id)) if target_id is not None else None,
                drain_monsters=[self._stick_monster(monster) for monster in self.private.source_monsters if int(monster.get("hp", 1)) > 0],
                save_throw_success=save_throw_success,
                ws_known=list(self.private.ws_known),
            )
            do_zap(world, obj)
            item["charges"] = obj.charges
            self.private.rng_seed = world.rng.seed
            self.private.command_after = world.after
            self.private.player_flags = world.player_flags
            self.private.hp = world.hero_hp
            self.private.ws_known = list(world.ws_known)
            self.private.source_effect_markers = list(world.markers)
            self._sync_stick_world(target_id, drain_ids, world)
            self._apply_stick_relocation(target_id, world)
            self._apply_stick_bolt(action, target_id, item, world)
            self._source_effect_event(command, selected, world.to_dict(obj), action)
            if self.private.hp <= 0 and "bolt_death:b" in self.private.source_effect_markers:
                self.private.terminated = True
                self.private.terminal_reason = "death"
                self._event("terminal", "Terminal(death:b)", action=action, transition="death")
            return True
        if command == "P":
            item = self._unworn_ring_for_action(action)
            if item is None:
                return self._source_no_item(command, action)
            selected = dict(item)
            world = self._ring_world()
            ring_on(world, self._ring_object(item))
            self._sync_ring_world(world)
            self.private.source_effect_markers = list(world.markers)
            self._source_effect_event(command, selected, world.to_dict(), action)
            return True
        if command == "R":
            selected = self._ring_item_by_id(self.private.left_ring_id or self.private.right_ring_id)
            if selected is None:
                return self._source_no_item(command, action)
            world = self._ring_world()
            ring_off(world)
            self._sync_ring_world(world)
            self.private.source_effect_markers = list(world.markers)
            self._source_effect_event(command, dict(selected), world.to_dict(), action)
            return True
        return False

    def _source_no_item(self, command: str, action: str) -> bool:
        self.private.source_effect_markers = [f"no_item:{command}"]
        self._event("action_applied", f"SourceCommandNoItem({command})", action=action, transition="source_no_item", payload={"command": command, "inventory": [dict(item) for item in self.private.source_inventory]})
        return True

    def _source_effect_event(self, command: str, item: dict[str, Any], world: dict[str, Any], action: str) -> None:
        self._event(
            "action_applied",
            f"SourceEffect({command},{item['id']})",
            action=action,
            transition="source_effect",
            payload={"command": command, "item": dict(item), "world": world, "inventory": [dict(entry) for entry in self.private.source_inventory]},
        )

    def _apply_source_no_turn_command(self, command: str, action: str, projection: dict[str, Any]) -> bool:
        markers = [str(marker) for marker in projection["final"]["markers"]]
        if command in {"i", "I"}:
            payload = self._source_inventory_payload(command, action, markers)
            self._event("action_applied", f"SourceInventory({command})", action=action, transition="source_inventory", payload=payload)
            return True
        if command in CURRENT_ACTIONS:
            payload = {"slot": CURRENT_ACTIONS[command], "markers": markers}
            if command == ")":
                item = self._current_item_payload(self.private.current_weapon_id)
                payload["item"] = item
                payload["message"] = self._source_current_message(item, "wielding")
            elif command == "]":
                item = self._current_item_payload(self.private.current_armor_id)
                payload["item"] = item
                payload["message"] = self._source_current_message(item, "wearing")
            else:
                left = self._current_item_payload(self.private.left_ring_id)
                right = self._current_item_payload(self.private.right_ring_id)
                left_message = self._source_current_message(left, "wearing", "on left hand")
                right_message = self._source_current_message(right, "wearing", "on right hand")
                payload["left"] = left
                payload["right"] = right
                payload["messages"] = [left_message, right_message]
            self._event("action_applied", f"SourceCurrent({CURRENT_ACTIONS[command]})", action=action, transition="source_current", payload=payload)
            return True
        if command == "?":
            topic = self._source_command_tail(action)[:1] or "*"
            payload = self._source_help_payload(topic, markers)
            self._event("action_applied", f"SourceHelp({topic})", action=action, transition="source_help", payload=payload)
            return True
        if command == "/":
            target = self._source_command_tail(action)[:1] or ""
            payload = {"target": target, "description": self._identify_description(target), "prompt": "what do you want identified? ", "markers": markers}
            if target == "\x1b":
                payload["cancelled"] = True
                payload["message"] = ""
            else:
                payload["message"] = f"'{self._source_unctrl(target)}': {payload['description']}"
            self._event("action_applied", f"SourceIdentify({target})", action=action, transition="source_identify", payload=payload)
            return True
        if command == "^":
            payload = self._trap_query_payload(action)
            payload["markers"] = markers
            self._event("action_applied", f"SourceTrapQuery({payload['direction']})", action=action, transition="source_trap_query", payload=payload)
            return True
        if command == "D":
            payload = self._source_discovered_payload(action, markers)
            self._event("action_applied", "SourceDiscovered()", action=action, transition="source_discovered", payload=payload)
            return True
        if command == "@":
            self._event("action_applied", "SourceStatus()", action=action, transition="source_status", payload=self._source_status_payload(markers))
            return True
        if command == "S":
            filename = self._source_command_tail(action).strip()
            if not filename or filename == "\x1b":
                self._event("action_applied", "SourceSavePrompt()", action=action, transition="source_save_prompt", payload={"markers": markers, "requires_file_name": True, "cancelled": filename == "\x1b"})
                return True
            save_file = runtime_source_save_file_projection(self.resolved, self.public, self.private, self.nev.cursor(), filename)
            self._event("action_applied", f"SourceSaveGame({filename})", action=action, transition="source_save", payload={"file_name": filename, "markers": markers, "save_file": save_file, "exit": True})
            self.private.terminated = True
            self.private.terminal_reason = "save"
            self._event("terminal", "Terminal(save)", action=action, transition="save")
            return True
        if command == "Q":
            self._event("action_applied", "SourceQuit()", action=action, transition="source_quit", payload={"markers": markers})
            self.private.terminated = True
            self.private.terminal_reason = "quit"
            self._event("terminal", "Terminal(quit)", action=action, transition="quit")
            return True
        if command == " ":
            self._event("action_applied", "SourceLegalIllegal()", action=action, transition="source_no_turn", payload={"markers": markers})
            return True
        if command == "\x1b":
            self._event("action_applied", "SourceEscape()", action=action, transition="source_no_turn", payload={"markers": markers})
            return True
        if command in NO_TURN_ACTIONS:
            action_name = NO_TURN_ACTIONS[command]
            self._event("action_applied", f"SourceNoTurn({action_name})", action=action, transition=f"source_{action_name}", payload={"command": command, "action": action_name, "markers": markers})
            return True
        return False

    def _current_item_payload(self, item_id: str) -> dict[str, Any] | None:
        item = self._inventory_item_by_id(item_id)
        return dict(item) if item is not None else None

    def _source_help_payload(self, topic: str, markers: list[str]) -> dict[str, Any]:
        payload: dict[str, Any] = {"topic": topic, "prompt": "character you want help for (* for all): ", "markers": markers}
        if topic == "*":
            payload["known"] = True
            payload["lines"] = [self._source_help_line(ch, desc) for ch, desc, printable in SOURCE_HELP_ENTRIES if printable]
            payload["continue_prompt"] = "--Press space to continue--"
            return payload

        entry = next((entry for entry in SOURCE_HELP_ENTRIES if entry[0] == topic), None)
        payload["known"] = entry is not None
        if entry is None:
            payload["message"] = f"unknown character '{self._source_unctrl(topic)}'"
            return payload
        payload["message"] = self._source_help_line(entry[0], entry[1])
        return payload

    def _source_help_line(self, ch: str, desc: str) -> str:
        return f"{self._source_unctrl(ch)}{desc}" if ch else desc

    def _source_status_payload(self, markers: list[str]) -> dict[str, Any]:
        hunger_index = max(0, min(self.private.hungry_state, len(SOURCE_HUNGER_NAMES) - 1))
        display_armor = 10 - self.private.player_armor
        return {
            "level": self.private.dungeon_level,
            "gold": self.private.purse,
            "hp": self.private.hp,
            "max_hp": self.private.max_hp,
            "strength": self.private.strength,
            "max_strength": self.private.max_strength,
            "armor": self.private.player_armor,
            "display_armor": display_armor,
            "exp": self.private.player_exp,
            "player_level": self.private.player_level,
            "hunger": self.private.hungry_state,
            "message": self._source_status_message(display_armor, SOURCE_HUNGER_NAMES[hunger_index]),
            "markers": markers,
        }

    def _source_status_message(self, display_armor: int, hunger: str) -> str:
        hp_width = len(str(max(1, self.private.max_hp)))
        return (
            f"Level: {self.private.dungeon_level:d}  "
            f"Gold: {self.private.purse:<5d}  "
            f"Hp: {self.private.hp:{hp_width}d}({self.private.max_hp:{hp_width}d})  "
            f"Str: {self.private.strength:2d}({self.private.max_strength:d})  "
            f"Arm: {display_armor:<2d}  "
            f"Exp: {self.private.player_level:d}/{self.private.player_exp:d}  "
            f"{hunger}"
        )

    def _source_discovered_payload(self, action: str, markers: list[str]) -> dict[str, Any]:
        assert self.resolved is not None
        topic = self._source_command_tail(action)[:1] or "*"
        payload: dict[str, Any] = {
            "type": topic,
            "prompt": "for what type of object do you want a list? (* for all)",
            "pot_known": list(self.private.pot_known),
            "ring_known": list(self.private.ring_known),
            "scr_known": list(self.private.scr_known),
            "ws_known": list(self.private.ws_known),
            "markers": markers,
        }
        if topic == "\x1b":
            payload["cancelled"] = True
            payload["message"] = ""
            return payload
        if topic not in {POTION, SCROLL, RING, STICK, "*"}:
            payload["valid"] = False
            payload["message"] = f"Please type one of {POTION}{SCROLL}{RING}{STICK} (ESCAPE to quit)"
            return payload

        rng = RogueRng(self.private.rng_seed)
        identity = runtime_source_identity_display(self.resolved, self.private)
        section_types = [POTION, SCROLL, RING, STICK] if topic == "*" else [topic]
        sections = []
        lines: list[str] = []
        for index, section_type in enumerate(section_types):
            section_lines = self._source_discovery_lines(section_type, identity, rng)
            sections.append({"type": section_type, "lines": section_lines})
            if index:
                lines.append("")
            lines.extend(section_lines)
        self.private.rng_seed = rng.seed
        payload["valid"] = True
        payload["sections"] = sections
        payload["lines"] = lines
        payload["continue_prompt"] = "--Press space to continue--"
        return payload

    def _source_discovery_lines(self, obj_type: str, identity: dict[str, Any], rng: RogueRng) -> list[str]:
        count = {POTION: 14, SCROLL: 18, RING: 14, STICK: 14}[obj_type]
        order = self._source_discovery_order(count, rng)
        lines = [self._source_discovery_name(obj_type, which, identity) for which in order if self._source_discovery_known(obj_type, which)]
        return lines or [self._source_discovery_nothing(obj_type)]

    def _source_discovery_order(self, count: int, rng: RogueRng) -> list[int]:
        order = list(range(count))
        for index in range(count, 0, -1):
            chosen = rng.rnd(index)
            order[index - 1], order[chosen] = order[chosen], order[index - 1]
        return order

    def _source_discovery_known(self, obj_type: str, which: int) -> bool:
        if obj_type == POTION:
            return which < len(self.private.pot_known) and self.private.pot_known[which]
        if obj_type == SCROLL:
            return which < len(self.private.scr_known) and self.private.scr_known[which]
        if obj_type == RING:
            return which < len(self.private.ring_known) and self.private.ring_known[which]
        return which < len(self.private.ws_known) and self.private.ws_known[which]

    def _source_discovery_name(self, obj_type: str, which: int, identity: dict[str, Any]) -> str:
        if obj_type == POTION:
            name = SOURCE_POT_INFO[which][0]
            color = identity["potions"][which]
            return f"A potion of {name}({color})"
        if obj_type == SCROLL:
            name = SOURCE_SCR_INFO[which][0]
            return f"A scroll of {name}"
        if obj_type == RING:
            name = SOURCE_RING_INFO[which][0]
            stone = identity["rings"][which]
            return f"A ring of {name}({stone})"
        name = SOURCE_WS_INFO[which][0]
        stick = identity["sticks"][which]
        return f"A {stick['type']} of {name}({stick['material']})"

    def _source_discovery_nothing(self, obj_type: str) -> str:
        type_name = {POTION: "potion", SCROLL: "scroll", RING: "ring", STICK: "stick"}[obj_type]
        return f"Haven't discovered anything about any {type_name}s"

    def _refresh_progress_metrics(self, action: str | None, *, emit: bool) -> None:
        seen = set(self.private.seen_tiles)
        old_shaped = float(self.private.synth_shaped_reward)
        newly_seen = sorted(key for key in self._currently_observed_tile_keys() if key not in seen)
        if newly_seen:
            seen.update(newly_seen)
            self.private.seen_tiles = sorted(seen, key=self._tile_key_sort)
        self.private.scout_score = len(self.private.seen_tiles)
        self.private.scout_last = len(newly_seen) if emit else 0
        shaped = self._compute_synth_shaped_reward()
        shaped_delta = shaped - old_shaped if emit else 0.0
        self.private.synth_shaped_reward = shaped
        self.private.synth_shaped_reward_last = shaped_delta
        if emit and newly_seen:
            self._event(
                "resource_delta",
                f"ScoutDelta({len(newly_seen)},total={self.private.scout_score})",
                action=action,
                transition="scout",
                payload={"new_tiles": newly_seen, "scout_delta": len(newly_seen), "scout_score": self.private.scout_score},
            )
        if emit and abs(shaped_delta) > 1e-9:
            self._event(
                "resource_delta",
                f"SynthShapedRewardDelta({shaped_delta:.2f},total={shaped:.2f})",
                action=action,
                transition="synth_shaped_reward",
                payload=self._progress_metrics_payload(),
            )

    def _currently_observed_tile_keys(self) -> list[str]:
        row, col = self.public.hero
        keys = []
        for seen_row in range(row - 1, row + 2):
            for seen_col in range(col - 1, col + 2):
                if self._in_bounds(seen_row, seen_col) and self._terrain(seen_row, seen_col) != " ":
                    keys.append(f"{self.private.dungeon_level},{seen_row},{seen_col}")
        return keys

    def _tile_key_sort(self, key: str) -> tuple[int, int, int]:
        level, row, col = [int(part) for part in key.split(",")]
        return level, row, col

    def _record_acquired_item_class(self, obj_type: str) -> None:
        item_class = str(obj_type)[:1]
        if not item_class:
            return
        classes = set(self.private.acquired_item_classes)
        classes.add(item_class)
        self.private.acquired_item_classes = sorted(classes)

    def _record_killed_monster_type(self, monster_type: str) -> None:
        kind = str(monster_type)[:1]
        if not kind:
            return
        killed = set(self.private.killed_monster_types)
        killed.add(kind)
        self.private.killed_monster_types = sorted(killed)

    def _compute_synth_shaped_reward(self) -> float:
        return (
            float(self.private.scout_score)
            + 100.0 * float(max(0, self.private.max_level - 1))
            + float(self.private.purse) / 10.0
            + float(max(0, self.private.player_exp)) / 20.0
            + 5.0 * float(self._known_identity_count())
            + 5.0 * float(len(self.private.acquired_item_classes))
            + 10.0 * float(len(self.private.killed_monster_types))
        )

    def _known_identity_count(self) -> int:
        return sum(1 for value in self.private.pot_known if value) + sum(1 for value in self.private.scr_known if value) + sum(1 for value in self.private.ring_known if value) + sum(1 for value in self.private.ws_known if value)

    def _achievement_names(self) -> list[str]:
        names = [f"scout.tile_seen:{tile_key}" for tile_key in self.private.seen_tiles]
        names.extend(f"depth.reached_level:{level}" for level in range(2, self.private.max_level + 1))
        if self.private.purse > 0:
            names.append("treasure.gold_collected")
        if self.private.player_exp > 0:
            names.append("combat.experience_gained")
        for family, known_values in (
            ("potion", self.private.pot_known),
            ("scroll", self.private.scr_known),
            ("ring", self.private.ring_known),
            ("wand", self.private.ws_known),
        ):
            names.extend(f"identify.known:{family}:{index}" for index, known in enumerate(known_values) if known)
        names.extend(f"inventory.acquired_class:{item_class}" for item_class in self.private.acquired_item_classes)
        names.extend(f"combat.killed_monster_type:{monster_type}" for monster_type in self.private.killed_monster_types)
        return names

    def _progress_metrics_payload(self) -> dict[str, Any]:
        return {
            "scout_score": self.private.scout_score,
            "scout_last": self.private.scout_last,
            "synth_shaped_reward": self.private.synth_shaped_reward,
            "synth_shaped_reward_last": self.private.synth_shaped_reward_last,
            "achievement_names": self._achievement_names(),
            "acquired_item_classes": list(self.private.acquired_item_classes),
            "killed_monster_types": list(self.private.killed_monster_types),
            "known_identity_count": self._known_identity_count(),
            "max_level": self.private.max_level,
            "purse": self.private.purse,
            "player_exp": self.private.player_exp,
        }

    def _source_inventory_payload(self, command: str, action: str, markers: list[str]) -> dict[str, Any]:
        inventory = [dict(item) for item in self.private.source_inventory]
        mode = "picky" if command == "I" else "full"
        payload: dict[str, Any] = {"mode": mode, "inventory": inventory, "markers": markers}
        if command == "i":
            lines = self._source_inventory_lines(inventory)
            payload["lines"] = lines
            if not lines:
                payload["message"] = "you are empty handed"
            return payload

        if not inventory:
            payload["lines"] = []
            payload["message"] = "you aren't carrying anything"
            return payload
        if len(inventory) == 1:
            payload["lines"] = [self._source_inventory_line(inventory[0])]
            return payload

        payload["prompt"] = "which item do you wish to inventory: "
        selected = self._source_command_tail(action)[:1]
        if not selected:
            payload["lines"] = []
            return payload

        payload["selected"] = selected
        selected_item = next((item for item in inventory if str(item.get("packch", ""))[:1] == selected), None)
        if selected_item is None:
            payload["lines"] = []
            payload["message"] = f"'{selected}' not in pack"
            return payload
        payload["lines"] = [self._source_inventory_line(selected_item)]
        return payload

    def _source_inventory_lines(self, inventory: list[dict[str, Any]]) -> list[str]:
        return [self._source_inventory_line(item) for item in inventory if int(item.get("count", 1)) > 0]

    def _source_inventory_line(self, item: dict[str, Any]) -> str:
        packch = str(item.get("packch", ""))[:1] or "?"
        return f"{packch}) {self._source_inv_name(item, drop=False)}"

    def _source_current_message(self, item: dict[str, Any] | None, how: str, where: str | None = None) -> str:
        suffix = f" {where}" if where else ""
        if item is None:
            return f"you are {how} nothing{suffix}"
        packch = str(item.get("packch", ""))[:1] or "?"
        return f"you are {how} ({packch}) {self._source_inv_name(item, drop=True)}{suffix}"

    def _source_inv_name(self, item: dict[str, Any], *, drop: bool) -> str:
        obj_type = str(item.get("type", "?"))[:1] or "?"
        which = int(item.get("which", 0))
        count = max(1, int(item.get("count", 1)))
        flags = int(item.get("flags", 0))
        label = item.get("label")
        if obj_type == WEAPON:
            name = SOURCE_WEAPON_NAMES[which] if 0 <= which < len(SOURCE_WEAPON_NAMES) else "weapon"
            if count > 1:
                text = f"{count} "
            else:
                text = f"A{self._vowel_suffix(name)} "
            if flags & ISKNOW:
                text += f"{self._source_num(int(item.get('hplus', 0)), int(item.get('dplus', 0)), WEAPON)} {name}"
            else:
                text += name
            if count > 1:
                text += "s"
            if label:
                text += f" called {label}"
            return self._source_drop_case(text, drop)
        if obj_type == ARMOR:
            name = SOURCE_ARMOR_NAMES[which] if 0 <= which < len(SOURCE_ARMOR_NAMES) else "armor"
            if flags & ISKNOW:
                arm = int(item.get("arm", 0))
                source_class = SOURCE_A_CLASS[which] if 0 <= which < len(SOURCE_A_CLASS) else 10
                text = f"{self._source_num(source_class - arm, 0, ARMOR)} {name} [protection {10 - arm}]"
            else:
                text = name
            if label:
                text += f" called {label}"
            return self._source_drop_case(text, drop)
        if obj_type == FOOD:
            text = "Some food" if count == 1 else f"{count} rations of food"
            return self._source_drop_case(text, drop)
        if obj_type == AMULET:
            return self._source_drop_case("The Amulet of Yendor", drop)
        if obj_type == GOLD:
            return f"{int(item.get('arm', item.get('gold', 0)))} Gold pieces"
        if obj_type == RING:
            if flags & ISKNOW:
                name = SOURCE_RING_NAMES[which] if 0 <= which < len(SOURCE_RING_NAMES) else "ring"
                text = f"A ring of {name}{self._source_ring_num(item)}"
            else:
                text = "A ring"
            return self._source_drop_case(text, drop)
        if obj_type == STICK:
            text = "A staff" if bool(item.get("is_staff", False)) else "A wand"
            return self._source_drop_case(text, drop)
        if obj_type == POTION:
            return self._source_drop_case("A potion", drop)
        if obj_type == SCROLL:
            text = "A scroll" if count == 1 else f"{count} scrolls"
            return self._source_drop_case(text, drop)
        return self._source_drop_case(str(item.get("name", item.get("id", "something"))), drop)

    def _source_drop_case(self, text: str, drop: bool) -> str:
        if drop and text and text[0].isupper():
            return text[0].lower() + text[1:]
        if not drop and text and text[0].islower():
            return text[0].upper() + text[1:]
        return text

    def _vowel_suffix(self, text: str) -> str:
        return "n" if text[:1].lower() in {"a", "e", "i", "o", "u"} else ""

    def _source_num(self, n1: int, n2: int, obj_type: str) -> str:
        text = f"{n1:+d}"
        if obj_type == WEAPON:
            text += f",{n2:+d}"
        return text

    def _source_ring_num(self, item: dict[str, Any]) -> str:
        which = int(item.get("which", 0))
        if which in {1, 7, 8}:
            return f" {int(item.get('arm', 0)):+d}"
        return ""

    def _source_command_tail(self, action: str) -> str:
        index = 0
        while index < len(action) and action[index].isdigit():
            index += 1
        return action[index + 1 :] if index < len(action) else ""

    def _source_unctrl(self, ch: str) -> str:
        if not ch:
            return ""
        code = ord(ch[:1])
        if code < 32:
            return f"^{chr(code + 64)}"
        if code == 127:
            return "^?"
        return ch[:1]

    def _identify_description(self, target: str) -> str:
        if not target:
            return "unknown character"
        if len(target) == 1 and "A" <= target <= "Z":
            return MONSTER_NAMES[ord(target) - ord("A")]
        return {
            "|": "wall of a room",
            "-": "wall of a room",
            GOLD: "gold",
            "%": "a staircase",
            DOOR: "door",
            FLOOR: "room floor",
            "@": "you",
            PASSAGE: "passage",
            "^": "trap",
            POTION: "potion",
            SCROLL: "scroll",
            FOOD: "food",
            WEAPON: "weapon",
            " ": "solid rock",
            ARMOR: "armor",
            AMULET: "the Amulet of Yendor",
            RING: "ring",
            STICK: "wand or staff",
        }.get(target, "unknown character")

    def _trap_query_payload(self, action: str) -> dict[str, Any]:
        direction = self._direction_input(action, default="h")
        delta = command_move_delta(direction)
        if delta is None:
            return {"direction": direction, "found": False, "trap": None}
        row, col = self.public.hero
        target = (row + delta[0], col + delta[1])
        for trap in self.private.source_traps:
            if (int(trap.get("row", -1)), int(trap.get("col", -1))) == target:
                trap["flags"] = int(trap.get("flags", 0)) | TRAP_F_SEEN
                return {"direction": direction, "found": True, "trap": dict(trap), "kind": int(trap["flags"]) & TRAP_F_TMASK}
        return {"direction": direction, "found": False, "trap": None}

    def _dropcheck_item(self, item: dict[str, Any]) -> bool:
        if item["id"] == self.private.current_weapon_id:
            if int(item.get("flags", 0)) & ISCURSED:
                self.private.source_effect_markers = ["cursed"]
                return False
            self.private.current_weapon_id = ""
            return True
        if item["id"] == self.private.current_armor_id:
            if int(item.get("flags", 0)) & ISCURSED:
                self.private.source_effect_markers = ["cursed"]
                return False
            self.private.current_armor_id = ""
            self.private.player_armor = 6
            return True
        if item["id"] not in {self.private.left_ring_id, self.private.right_ring_id}:
            return True
        world = self._ring_world()
        ok = ring_dropcheck(world, self._ring_object(item))
        self._sync_ring_world(world)
        self.private.source_effect_markers = list(world.markers)
        return ok

    def _leave_inventory_for_drop(self, item: dict[str, Any]) -> dict[str, Any]:
        obj_type = str(item.get("type", "?"))[:1]
        all_items = not self._is_mult(obj_type)
        if int(item.get("count", 1)) > 1 and not all_items:
            item["count"] = int(item["count"]) - 1
            dropped = dict(item)
            dropped["count"] = 1
            dropped["id"] = f"{item['id']}_drop{self.private.step_index}"
            return dropped
        dropped = dict(item)
        self.private.source_inventory = [entry for entry in self.private.source_inventory if entry["id"] != item["id"]]
        return dropped

    def _leave_inventory_for_throw(self, item: dict[str, Any]) -> dict[str, Any]:
        if int(item.get("count", 1)) > 1:
            item["count"] = int(item["count"]) - 1
            thrown = dict(item)
            thrown["count"] = 1
            thrown["id"] = f"{item['id']}_throw{self.private.step_index}"
            return thrown
        thrown = dict(item)
        self.private.source_inventory = [entry for entry in self.private.source_inventory if entry["id"] != item["id"]]
        return thrown

    def _missile_direction(self) -> str:
        for marker in self.private.command_markers:
            if marker.startswith("missile:") and len(marker) >= len("missile:h"):
                return marker.split(":", 1)[1][:1]
        return (self.private.command_direction or "h")[:1]

    def _projectile_impact(self, direction: str) -> tuple[int, int, dict[str, Any] | None]:
        delta = command_move_delta(direction)
        if delta is None:
            row, col = self.public.hero
            return row, col, None
        row, col = self.public.hero
        dy, dx = delta
        nr, nc = row, col
        while True:
            nr += dy
            nc += dx
            if not self._in_bounds(nr, nc):
                return nr, nc, None
            terrain = self._terrain(nr, nc)
            if not step_ok(terrain) or terrain == DOOR:
                return nr, nc, self._monster_at(nr, nc)
            monster = self._monster_at(nr, nc)
            if monster is not None:
                return nr, nc, monster

    def _fall_projectile(self, item: dict[str, Any], impact_row: int, impact_col: int) -> str:
        rng = RogueRng(self.private.rng_seed)
        count = 0
        chosen: tuple[int, int] | None = None
        hero = self.public.hero
        for row in range(impact_row - 1, impact_row + 2):
            for col in range(impact_col - 1, impact_col + 2):
                if (row, col) == hero or not self._in_bounds(row, col):
                    continue
                key = f"{row},{col}"
                if self._terrain(row, col) not in {FLOOR, PASSAGE} or key in self.public.visible_items or self._monster_at(row, col) is not None:
                    continue
                count += 1
                if rng.rnd(count) == 0:
                    chosen = (row, col)
        self.private.rng_seed = rng.seed
        if chosen is None:
            return "vanish"
        row, col = chosen
        item["pos"] = {"y": row, "x": col}
        self.private.source_level_objects.insert(0, item)
        self.public.visible_items[f"{row},{col}"] = str(item["type"])[:1]
        return "fall"

    def _check_player_level(self, rng: RogueRng) -> int:
        next_level = 1
        for threshold in E_LEVELS:
            if threshold == 0 or threshold > self.private.player_exp:
                break
            next_level += 1
        old_level = self.private.player_level
        self.private.player_level = next_level
        if next_level <= old_level:
            return 0
        level_add = rng.roll(next_level - old_level, 10)
        self.private.max_hp += level_add
        self.private.hp += level_add
        return level_add

    def _current_player_damage(self) -> str:
        weapon = self._inventory_item_by_id(self.private.current_weapon_id)
        if weapon is None:
            return self.private.player_damage
        return str(weapon.get("damage", self.private.player_damage))

    def _current_fight_weapon(self) -> FightWeapon | None:
        return self._fight_weapon(self._inventory_item_by_id(self.private.current_weapon_id))

    def _fight_weapon(self, item: dict[str, Any] | None) -> FightWeapon | None:
        if item is None or str(item.get("type", ""))[:1] != WEAPON:
            return None
        return FightWeapon(
            obj_type=WEAPON,
            which=int(item.get("which", 0)),
            hplus=int(item.get("hplus", 0)),
            dplus=int(item.get("dplus", 0)),
            damage=str(item.get("damage", "1x1")),
            hurl_damage=str(item.get("hurldmg", item.get("hurl_damage", "1x1"))),
            launch=int(item.get("launch", -1)),
            flags=int(item.get("flags", 0)),
            name=str(item.get("id", "weapon")),
        )

    def _scroll_item_from_inventory(self, item: dict[str, Any] | None) -> ScrollItem | None:
        if item is None:
            return None
        return ScrollItem(obj_type=str(item.get("type", "?"))[:1], which=int(item.get("which", 0)), flags=int(item.get("flags", 0)), arm=int(item.get("arm", 0)), hplus=int(item.get("hplus", 0)), dplus=int(item.get("dplus", 0)))

    def _sync_scroll_equipment(self, world: ScrollWorld) -> None:
        armor = self._inventory_item_by_id(self.private.current_armor_id)
        if armor is not None and world.current_armor is not None:
            armor["arm"] = world.current_armor.arm
            armor["flags"] = world.current_armor.flags
            self.private.player_armor = world.current_armor.arm
        weapon = self._inventory_item_by_id(self.private.current_weapon_id)
        if weapon is not None and world.current_weapon is not None:
            weapon["hplus"] = world.current_weapon.hplus
            weapon["dplus"] = world.current_weapon.dplus
            weapon["flags"] = world.current_weapon.flags

    def _normalize_traps(self, traps: list[dict[str, Any]], terrain: list[str]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        occupied: set[tuple[int, int]] = set()
        for index, raw in enumerate(traps):
            row = int(raw.get("row", raw.get("y", 0)))
            col = int(raw.get("col", raw.get("x", 0)))
            kind = int(raw.get("kind", raw.get("trap_kind", T_MYST)))
            flags = int(raw.get("flags", TRAP_F_REAL | kind))
            normalized.append(
                {
                    "id": str(raw.get("id", raw.get("trap_id", f"trap{index}"))),
                    "row": row,
                    "col": col,
                    "kind": kind,
                    "flags": flags,
                    "ch": str(raw.get("ch", "^"))[:1] or "^",
                    "weapon_group": int(raw.get("weapon_group", 1)),
                }
            )
            occupied.add((row, col))
        next_index = len(normalized)
        for row, text in enumerate(terrain):
            for col, ch in enumerate(text):
                if ch == "^" and (row, col) not in occupied:
                    normalized.append(
                        {
                            "id": f"trap{next_index}",
                            "row": row,
                            "col": col,
                            "kind": T_MYST,
                            "flags": TRAP_F_REAL | T_MYST,
                            "ch": "^",
                            "weapon_group": 1,
                        }
                    )
                    next_index += 1
        return normalized

    def _normalize_source_map_cells(self, cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": str(raw.get("id", raw.get("cell_id", f"cell{index}"))),
                "row": int(raw.get("row", raw.get("y", 0))),
                "col": int(raw.get("col", raw.get("x", 0))),
                "ch": str(raw.get("ch", " "))[:1] or " ",
                "flags": int(raw.get("flags", 0)),
            }
            for index, raw in enumerate(cells)
        ]

    def _apply_source_map_cell_display(self, terrain: list[str], cells: list[dict[str, Any]]) -> None:
        for cell in cells:
            row = int(cell.get("row", -1))
            col = int(cell.get("col", -1))
            if 0 <= row < len(terrain):
                chars = list(terrain[row])
                if 0 <= col < len(chars):
                    chars[col] = str(cell.get("ch", " "))[:1] or " "
                    terrain[row] = "".join(chars)

    def _default_daemon_actions(self) -> list[dict[str, Any]]:
        return [
            {"action": "doctor", "type": DAEMON_AFTER, "arg": 0, "time": DAEMON},
            {"action": "stomach", "type": DAEMON_AFTER, "arg": 0, "time": DAEMON},
        ]

    def _normalize_inventory(self, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(inventory):
            obj_type = str(raw.get("type", raw.get("obj_type", "?")))[:1] or "?"
            normalized.append(
                {
                    "id": str(raw.get("id", raw.get("obj_id", f"item{index}"))),
                    "type": obj_type,
                    "which": int(raw.get("which", 0)),
                    "count": int(raw.get("count", 1)),
                    "flags": int(raw.get("flags", 0)),
                    "arm": int(raw.get("arm", 0)),
                    "hplus": int(raw.get("hplus", 0)),
                    "dplus": int(raw.get("dplus", 0)),
                    "charges": int(raw.get("charges", 0)),
                    "group": int(raw.get("group", 0)),
                    "packch": str(raw.get("packch", chr(ord("a") + index)))[:1] or "a",
                    "damage": str(raw.get("damage", "")),
                    "hurldmg": str(raw.get("hurldmg", "")),
                    "launch": int(raw.get("launch", -1)),
                    "is_staff": bool(raw.get("is_staff", False)),
                }
            )
        return normalized

    def _normalize_level_objects(self, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(objects):
            obj_type = str(raw.get("type", raw.get("obj_type", "?")))[:1] or "?"
            pos = dict(raw.get("pos", {}))
            row = int(raw.get("row", raw.get("y", pos.get("y", 0))))
            col = int(raw.get("col", raw.get("x", pos.get("x", 0))))
            normalized.append(
                {
                    "id": str(raw.get("id", raw.get("obj_id", f"level_object{index}"))),
                    "type": obj_type,
                    "which": int(raw.get("which", 0)),
                    "pos": {"y": row, "x": col},
                    "count": int(raw.get("count", 1)),
                    "hplus": int(raw.get("hplus", 0)),
                    "dplus": int(raw.get("dplus", 0)),
                    "arm": int(raw.get("arm", raw.get("charges", 0) if obj_type == STICK else 0)),
                    "flags": int(raw.get("flags", 0)),
                    "group": int(raw.get("group", 0)),
                    "goldval": int(raw.get("goldval", 0)),
                    "charges": int(raw.get("charges", raw.get("arm", 0) if obj_type == STICK else 0)),
                    "damage": str(raw.get("damage", "")),
                    "hurldmg": str(raw.get("hurldmg", "")),
                    "launch": int(raw.get("launch", -1)),
                    "is_staff": bool(raw.get("is_staff", False)),
                }
            )
        return normalized

    def _normalize_monsters(self, monsters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(monsters):
            monster_type = str(raw.get("type", raw.get("monster_type", "K")))[:1] or "K"
            hp = int(raw.get("hp", raw.get("max_hp", 1)))
            normalized.append(
                {
                    "id": str(raw.get("id", raw.get("monster_id", f"monster{index}"))),
                    "type": monster_type,
                    "row": int(raw.get("row", raw.get("y", 0))),
                    "col": int(raw.get("col", raw.get("x", 0))),
                    "strength": int(raw.get("strength", 16)),
                    "exp": int(raw.get("exp", 1)),
                    "level": int(raw.get("level", 1)),
                    "arm": int(raw.get("arm", 6)),
                    "hp": hp,
                    "max_hp": int(raw.get("max_hp", hp)),
                    "damage": str(raw.get("damage", "1x1")),
                    "stats_flags": int(raw.get("stats_flags", FIGHT_ISRUN)),
                    "flags": int(raw.get("flags", FIGHT_ISRUN)),
                    "turn": bool(raw.get("turn", True)),
                    "room": int(raw.get("room", 0)),
                    "dest_kind": str(raw.get("dest_kind", raw.get("dest", "hero"))),
                    "dest_row": int(raw.get("dest_row", raw.get("dest_pos", [0, 0])[0] if isinstance(raw.get("dest_pos"), list) and raw.get("dest_pos") else 0)),
                    "dest_col": int(raw.get("dest_col", raw.get("dest_pos", [0, 0])[1] if isinstance(raw.get("dest_pos"), list) and len(raw.get("dest_pos", [])) > 1 else 0)),
                    "dest_room": int(raw.get("dest_room", raw.get("room", 0))),
                    "find_dest_kind": str(raw.get("find_dest_kind", "hero")),
                    "find_dest_row": int(raw.get("find_dest_row", raw.get("find_dest_pos", [0, 0])[0] if isinstance(raw.get("find_dest_pos"), list) and raw.get("find_dest_pos") else 0)),
                    "find_dest_col": int(raw.get("find_dest_col", raw.get("find_dest_pos", [0, 0])[1] if isinstance(raw.get("find_dest_pos"), list) and len(raw.get("find_dest_pos", [])) > 1 else 0)),
                    "room_goldval": int(raw.get("room_goldval", 1)),
                    "room_flags": int(raw.get("room_flags", 0)),
                    "dest_room_goldval": int(raw.get("dest_room_goldval", 0)),
                    "dest_room_flags": int(raw.get("dest_room_flags", 0)),
                    "passage_index": int(raw.get("passage_index", 9)),
                    "passage_flags": int(raw.get("passage_flags", 0o000002)),
                    "chase_room": int(raw.get("chase_room", raw.get("room", 0))),
                    "room_exits": [list(coord) for coord in list(raw.get("room_exits", []))],
                    "disguise": str(raw.get("disguise", monster_type))[:1] or monster_type,
                    "oldch": str(raw.get("oldch", "."))[:1] or ".",
                    "pack": [dict(obj) for obj in list(raw.get("pack", []))],
                }
            )
        return normalized

    def _first_inventory_item(self, obj_type: str) -> dict[str, Any] | None:
        for item in self.private.source_inventory:
            if item["type"] == obj_type and int(item.get("count", 1)) > 0:
                return item
        return None

    def _inventory_item_for_action(self, action: str, obj_type: str | None = None) -> dict[str, Any] | None:
        packch = self._packch_from_action(action)
        if packch:
            for item in self.private.source_inventory:
                if str(item.get("packch", ""))[:1] == packch and int(item.get("count", 1)) > 0:
                    if obj_type is None or str(item.get("type", "?"))[:1] == obj_type:
                        return item
                    return None
            return None
        if obj_type is None:
            return self._first_any_inventory_item()
        return self._first_inventory_item(obj_type)

    def _apply_source_whatis_for_scroll(self, selected: dict[str, Any], action: str, world: ScrollWorld) -> None:
        id_type = self._source_whatis_type_for_scroll(int(selected.get("which", -1)))
        if id_type is None:
            return
        consumed_id = str(selected.get("id", ""))
        consumed_removed = int(selected.get("count", 1)) <= 1
        item = self._source_whatis_item_for_action(action, id_type, consumed_id, consumed_removed)
        if item is None:
            world.markers.append(f"whatis_no_item:{id_type}")
            world.trace["whatis_item"] = None
            world.trace["whatis_type"] = id_type
            return
        obj_type = str(item.get("type", "?"))[:1]
        which = int(item.get("which", 0))
        item["flags"] = int(item.get("flags", 0)) | ISKNOW
        self._source_identify_known_type(obj_type, which)
        if obj_type == SCROLL:
            world.scr_known = list(self.private.scr_known)
        world.markers.append(f"whatis_selected:{obj_type}:{which}")
        world.markers.append(f"identified:{obj_type}:{which}")
        world.trace["whatis_item"] = dict(item)
        world.trace["whatis_type"] = id_type

    def _source_whatis_type_for_scroll(self, which: int) -> str | int | None:
        return {
            S_ID_POTION: POTION,
            S_ID_SCROLL: SCROLL,
            S_ID_WEAPON: WEAPON,
            S_ID_ARMOR: ARMOR,
            S_ID_R_OR_S: R_OR_S,
        }.get(which)

    def _source_whatis_item_for_action(self, action: str, id_type: str | int, consumed_id: str, consumed_removed: bool) -> dict[str, Any] | None:
        packch = self._source_whatis_packch_from_action(action)
        if packch:
            for item in self.private.source_inventory:
                if not self._source_whatis_candidate(item, id_type, consumed_id, consumed_removed):
                    continue
                if str(item.get("packch", ""))[:1] == packch:
                    return item
            return None
        for item in self.private.source_inventory:
            if self._source_whatis_candidate(item, id_type, consumed_id, consumed_removed):
                return item
        return None

    def _source_whatis_candidate(self, item: dict[str, Any], id_type: str | int, consumed_id: str, consumed_removed: bool) -> bool:
        if int(item.get("count", 1)) <= 0:
            return False
        if consumed_removed and consumed_id and str(item.get("id", "")) == consumed_id:
            return False
        obj_type = str(item.get("type", "?"))[:1]
        if id_type == R_OR_S:
            return obj_type in {RING, STICK}
        return obj_type == id_type

    def _source_identify_known_type(self, obj_type: str, which: int) -> None:
        if obj_type == POTION and 0 <= which < len(self.private.pot_known):
            self.private.pot_known[which] = True
        elif obj_type == SCROLL and 0 <= which < len(self.private.scr_known):
            self.private.scr_known[which] = True
        elif obj_type == RING and 0 <= which < len(self.private.ring_known):
            self.private.ring_known[which] = True
        elif obj_type == STICK and 0 <= which < len(self.private.ws_known):
            self.private.ws_known[which] = True

    def _source_whatis_packch_from_action(self, action: str) -> str:
        index = 0
        while index < len(action) and action[index].isdigit():
            index += 1
        target_index = index + 2
        if target_index < len(action):
            return action[target_index]
        return ""

    def _directional_inventory_item_for_action(self, action: str, obj_type: str) -> dict[str, Any] | None:
        packch = self._directional_packch_from_action(action)
        if packch:
            for item in self.private.source_inventory:
                if str(item.get("packch", ""))[:1] == packch and int(item.get("count", 1)) > 0:
                    if str(item.get("type", "?"))[:1] == obj_type:
                        return item
                    return None
            return None
        return self._first_inventory_item(obj_type)

    def _packch_from_action(self, action: str) -> str:
        index = 0
        while index < len(action) and action[index].isdigit():
            index += 1
        if index + 1 < len(action):
            return action[index + 1]
        return ""

    def _directional_packch_from_action(self, action: str) -> str:
        index = 0
        while index < len(action) and action[index].isdigit():
            index += 1
        if index >= len(action) or action[index] not in {"t", "z"}:
            return self._packch_from_action(action)
        tail = action[index + 1 :]
        if not tail:
            return ""
        if len(tail) == 1 and command_move_delta(tail[0]) is not None:
            return ""
        return tail[0]

    def _first_any_inventory_item(self) -> dict[str, Any] | None:
        for item in self.private.source_inventory:
            if int(item.get("count", 1)) > 0:
                return item
        return None

    def _first_unworn_ring(self) -> dict[str, Any] | None:
        worn = {self.private.left_ring_id, self.private.right_ring_id}
        for item in self.private.source_inventory:
            if item["type"] == RING and item["id"] not in worn:
                return item
        return None

    def _unworn_ring_for_action(self, action: str) -> dict[str, Any] | None:
        worn = {self.private.left_ring_id, self.private.right_ring_id}
        selected = self._inventory_item_for_action(action, RING)
        if selected is not None:
            return selected if selected["id"] not in worn else None
        if self._packch_from_action(action):
            return None
        return self._first_unworn_ring()

    def _ring_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        return self._inventory_item_by_id(item_id)

    def _inventory_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        if not item_id:
            return None
        for item in self.private.source_inventory:
            if item["id"] == item_id:
                return item
        return None

    def _decrement_or_remove_item(self, item: dict[str, Any]) -> None:
        if int(item.get("count", 1)) > 1:
            item["count"] = int(item["count"]) - 1
            return
        self.private.source_inventory = [entry for entry in self.private.source_inventory if entry["id"] != item["id"]]

    def _potion_object(self, item: dict[str, Any]) -> PotionObject:
        return PotionObject(obj_id=item["id"], obj_type=item["type"], which=int(item["which"]), count=int(item["count"]), flags=int(item["flags"]), arm=int(item["arm"]), hplus=int(item["hplus"]), dplus=int(item["dplus"]))

    def _scroll_object(self, item: dict[str, Any]) -> ScrollObject:
        return ScrollObject(obj_type=item["type"], which=int(item["which"]), count=int(item["count"]))

    def _stick_object(self, item: dict[str, Any]) -> StickObject:
        return StickObject(obj_type=item["type"], which=int(item["which"]), charges=int(item["charges"]), flags=int(item["flags"]), damage=str(item["damage"]), hurldmg=str(item["hurldmg"]), hplus=int(item["hplus"]), dplus=int(item["dplus"]), launch=int(item["launch"]), is_staff=bool(item["is_staff"]))

    def _zap_direction(self) -> str:
        for marker in self.private.command_markers:
            if marker.startswith("do_zap:") and len(marker) >= len("do_zap:h"):
                return marker.split(":", 1)[1][:1]
        return (self.private.command_direction or "h")[:1]

    def _zap_target_id(self) -> str | None:
        delta = command_move_delta(self._zap_direction())
        if delta is None:
            return None
        row, col = self.public.hero
        dy, dx = delta
        nr, nc = row + dy, col + dx
        while self._in_bounds(nr, nc) and step_ok(self._terrain(nr, nc)):
            monster = self._monster_at(nr, nc)
            if monster is not None and int(monster.get("hp", 1)) > 0:
                return str(monster["id"])
            nr += dy
            nc += dx
        return None

    def _stick_monster(self, monster: dict[str, Any] | None) -> StickMonster:
        if monster is None:
            return StickMonster(monster_type="K", hp=0)
        return StickMonster(
            monster_type=str(monster.get("type", "K"))[:1],
            hp=int(monster.get("hp", 1)),
            flags=int(monster.get("flags", FIGHT_ISRUN)),
            disguise=str(monster.get("disguise", monster.get("type", "K")))[:1],
            oldch=str(monster.get("oldch", "."))[:1],
            pack_count=len(list(monster.get("pack", []))),
            turn=bool(monster.get("turn", True)),
            dest_hero=str(monster.get("dest_kind", monster.get("dest", "hero"))) == "hero",
            visible=int(monster.get("hp", 1)) > 0,
            cansee=int(monster.get("hp", 1)) > 0,
        )

    def _sync_stick_world(self, target_id: str | None, drain_ids: list[str], world: StickWorld) -> None:
        if target_id is not None and world.target is not None:
            self._sync_stick_monster(target_id, world.target)
        for monster_id, source_monster in zip(drain_ids, world.drain_monsters, strict=False):
            self._sync_stick_monster(monster_id, source_monster)
        self.private.source_monsters = [monster for monster in self.private.source_monsters if int(monster.get("hp", 1)) > 0]
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)

    def _apply_stick_relocation(self, target_id: str | None, world: StickWorld) -> None:
        if target_id is None:
            return
        destination: Position | None = None
        if "relocate:random_floor" in world.markers:
            destination = self._find_source_floor(monst=True, avoid_hero=True)
        elif "relocate:adjacent" in world.markers:
            delta = command_move_delta(self._zap_direction())
            if delta is not None:
                row, col = self.public.hero
                destination = (row + delta[0], col + delta[1])
        if destination is None or not self._in_bounds(*destination):
            return
        for monster in self.private.source_monsters:
            if str(monster["id"]) == target_id:
                monster["row"] = destination[0]
                monster["col"] = destination[1]
                break
        self.public.visible_monsters = self._visible_monsters(self.private.source_monsters)

    def _apply_stick_bolt(self, action: str, target_id: str | None, item: dict[str, Any], world: StickWorld) -> None:
        which = int(item.get("which", 0))
        if which not in {WS_ELECT, WS_FIRE, WS_COLD} or not any(str(marker).startswith("fire_bolt:") for marker in world.markers):
            return
        if target_id is None:
            if not self._apply_reflected_bolt_hero_hit():
                self.private.source_effect_markers.append("bolt_vanishes")
            return
        monster = self._monster_by_id(target_id)
        if monster is None:
            if not self._apply_reflected_bolt_hero_hit():
                self.private.source_effect_markers.append("bolt_vanishes")
            return
        bolt_name = "bolt" if which == WS_ELECT else "flame" if which == WS_FIRE else "ice"
        rng = RogueRng(self.private.rng_seed)
        saved = self._source_save_throw(rng, VS_MAGIC, int(monster.get("level", 1)))
        self.private.rng_seed = int(saved["rng_seed"])
        if bool(saved["saved"]):
            self.private.source_effect_markers.append(f"bolt_saved:{target_id}")
            return
        if bolt_name == "flame" and str(monster.get("type", ""))[:1] == "D":
            self.private.source_effect_markers.append(f"bolt_bounced:{target_id}")
            return
        hit = self._fight_monster(action, monster, thrown=True, weapon=self._bolt_fight_weapon(bolt_name))
        self.private.source_effect_markers.append(f"bolt_hit:{target_id}" if hit else f"bolt_missed:{target_id}")

    def _apply_reflected_bolt_hero_hit(self) -> bool:
        delta = command_move_delta(self._zap_direction())
        if delta is None:
            return False
        hero_row, hero_col = self.public.hero
        row, col = hero_row, hero_col
        dy, dx = delta
        hit_hero = False
        changed = False
        bounced = False
        steps = 0
        guard = 0
        while steps < BOLT_LENGTH and guard < BOLT_LENGTH * 6:
            guard += 1
            row += dy
            col += dx
            terrain = self._terrain(row, col) if self._in_bounds(row, col) else " "
            if terrain in {DOOR, "|", "-", " "}:
                if not changed:
                    hit_hero = not hit_hero
                changed = False
                dy = -dy
                dx = -dx
                bounced = True
                self.private.source_effect_markers.append("bolt_bounce")
                continue
            if hit_hero and (row, col) == (hero_row, hero_col):
                rng = RogueRng(self.private.rng_seed)
                saved = self._source_player_magic_save(rng)
                self.private.rng_seed = int(saved["rng_seed"])
                if bool(saved["saved"]):
                    self.private.source_effect_markers.append("bolt_hero_saved")
                    return True
                damage = rng.roll(6, 6)
                self.private.rng_seed = rng.seed
                self.private.hp = max(0, self.private.hp - damage)
                self.private.source_effect_markers.append(f"bolt_hero_hit:{damage}")
                if self.private.hp <= 0:
                    self.private.source_effect_markers.append("bolt_death:b")
                return True
            steps += 1
        return bounced

    def _source_player_magic_save(self, rng: RogueRng) -> dict[str, Any]:
        adjusted = VS_MAGIC
        for item in (self._ring_item_by_id(self.private.left_ring_id), self._ring_item_by_id(self.private.right_ring_id)):
            if item is not None and int(item.get("which", 0)) == R_PROTECT:
                adjusted -= int(item.get("arm", 0))
        saved = self._source_save_throw(rng, adjusted, self.private.player_level)
        saved["original_which"] = VS_MAGIC
        return saved

    def _bolt_fight_weapon(self, name: str) -> FightWeapon:
        return FightWeapon(
            obj_type=WEAPON,
            which=FLAME_WEAPON,
            hplus=100,
            dplus=0,
            damage="1x1",
            hurl_damage="6x6",
            launch=-1,
            flags=0,
            name=name,
        )

    def _sync_stick_monster(self, monster_id: str, monster: StickMonster) -> None:
        for entry in self.private.source_monsters:
            if str(entry["id"]) != monster_id:
                continue
            entry["type"] = monster.monster_type
            entry["hp"] = monster.hp
            entry["flags"] = monster.flags
            entry["turn"] = monster.turn
            entry["disguise"] = monster.disguise or monster.monster_type
            entry["oldch"] = monster.oldch
            if monster.dest_hero:
                entry["dest_kind"] = "hero"
                entry["dest_row"] = self.public.hero[0]
                entry["dest_col"] = self.public.hero[1]
            break

    def _current_weapon_which(self) -> int | None:
        weapon = self._inventory_item_by_id(self.private.current_weapon_id)
        if weapon is None:
            return None
        return int(weapon.get("which", 0))

    def _source_save_throw(self, rng: RogueRng, which: int, level: int) -> dict[str, Any]:
        need = 14 + which - level // 2
        roll = rng.roll(1, 20)
        return {"which": which, "level": level, "need": need, "roll": roll, "saved": roll >= need, "rng_seed": rng.seed}

    def _ring_object(self, item: dict[str, Any]) -> RingObject:
        return RingObject(obj_id=item["id"], obj_type=item["type"], which=int(item["which"]), arm=int(item["arm"]), flags=int(item["flags"]), packch=str(item["packch"]))

    def _potion_source_ring(self, item_id: str) -> SourceRing | None:
        item = self._ring_item_by_id(item_id)
        if item is None:
            return None
        return SourceRing(which=int(item["which"]), arm=int(item["arm"]))

    def _scroll_ring_item(self, item_id: str) -> ScrollItem | None:
        item = self._ring_item_by_id(item_id)
        if item is None:
            return None
        return ScrollItem(obj_type=RING, which=int(item["which"]), flags=int(item["flags"]), arm=int(item["arm"]), hplus=int(item["hplus"]), dplus=int(item["dplus"]))

    def _ring_world(self) -> RingWorld:
        return RingWorld(
            rng=RogueRng(self.private.rng_seed),
            strength=self.private.strength,
            left_ring=self._ring_object(self._ring_item_by_id(self.private.left_ring_id)) if self._ring_item_by_id(self.private.left_ring_id) else None,
            right_ring=self._ring_object(self._ring_item_by_id(self.private.right_ring_id)) if self._ring_item_by_id(self.private.right_ring_id) else None,
            selected_hand=LEFT,
        )

    def _sync_ring_world(self, world: RingWorld) -> None:
        self.private.rng_seed = world.rng.seed
        self.private.strength = world.strength
        self.private.left_ring_id = world.left_ring.obj_id if world.left_ring is not None else ""
        self.private.right_ring_id = world.right_ring.obj_id if world.right_ring is not None else ""

    def _food_count_for_scrolls(self) -> int:
        visible_food = sum(1 for item in self.public.visible_items.values() if item == FOOD)
        inventory_food = sum(int(item.get("count", 1)) for item in self.private.source_inventory if item.get("type") == FOOD)
        return self.private.food + visible_food + inventory_food
