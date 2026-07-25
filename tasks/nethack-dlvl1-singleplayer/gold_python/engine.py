"""Own capture-backed symbolic NetHack Main Dungeon dlvl-1 engine.

The implementation intentionally owns its state transitions.  It reads frozen
level dumps only; it never imports or delegates to NLE at runtime.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from shared.task_resolve import BLSTATS_FIELDS, VIEW_HEIGHT, VIEW_WIDTH

from .action_map import NleAction, action_payload, coerce_action, direction_for
from .core.checkpoint import decode_checkpoint, encode_checkpoint
from .core.nev import NevLog


PASSABLE = {".", "#", ">", "<", "_", "{", "}", "\\", "~", "^"}
WALLS = {" ", "|", "-", "+"}
ITEM_COMMANDS = {
    "APPLY",
    "DIP",
    "DROP",
    "EAT",
    "FIRE",
    "INVOKE",
    "PUTON",
    "QUAFF",
    "QUIVER",
    "READ",
    "REMOVE",
    "RUB",
    "TAKEOFF",
    "THROW",
    "TIP",
    "WEAR",
    "WIELD",
    "ZAP",
}
DIRECTION_COMMANDS = {"CLOSE", "FIGHT", "FORCE", "KICK", "MOVE", "MOVEFAR", "RUSH", "RUSH2", "SEETRAP", "UNTRAP"}
INFO_COMMANDS = {
    "ADJUST",
    "ANNOTATE",
    "ATTRIBUTES",
    "AUTOPICKUP",
    "CALL",
    "CONDUCT",
    "ENHANCE",
    "EXTLIST",
    "GLANCE",
    "HISTORY",
    "INVENTTYPE",
    "KNOWN",
    "KNOWNCLASS",
    "LOOK",
    "MONSTER",
    "OPTIONS",
    "OVERVIEW",
    "PAY",
    "REDRAW",
    "SEEALL",
    "SEEAMULET",
    "SEEARMOR",
    "SEEGOLD",
    "SEERINGS",
    "SEESPELLS",
    "SEETOOLS",
    "SEEWEAPON",
    "SHELL",
    "SIT",
    "SWAP",
    "TELEPORT",
    "TRAVEL",
    "TURN",
    "TWOWEAPON",
    "VERSION",
    "VERSIONSHORT",
    "WHATDOES",
    "WHATIS",
    "WIPE",
}


class NethackDlvl1Engine:
    ENV_FAMILY = "nethack-dlvl1-singleplayer"

    def __init__(self) -> None:
        self.resolved: dict[str, Any] | None = None
        self.state: dict[str, Any] = {}
        self.nev = NevLog()

    def reset(self, resolved: dict[str, Any]) -> None:
        level = deepcopy(resolved["level_dump"])
        hero = dict(level["hero"])
        inventory = deepcopy(level["inventory"])
        self._assign_inventory_letters(inventory)
        initial_hp = int(dict(level.get("metadata", {})).get("hp", 14))
        initial_energy = int(dict(level.get("metadata", {})).get("energy", 0))
        self.resolved = deepcopy(resolved)
        self.state = {
            "terrain": [list(row) for row in level["terrain"]],
            "base_glyphs": deepcopy(level["glyphs"]),
            "base_colors": deepcopy(level["colors"]),
            "seen": deepcopy(level["seen"]),
            "hero": hero,
            "floor_items": deepcopy(level["objects"]),
            "inventory": inventory,
            "monsters": deepcopy(level["monsters"]),
            "traps": deepcopy(level["traps"]),
            "step_index": 0,
            "time": 0,
            "rng": int(resolved["seed"]) & 0xFFFFFFFF,
            "message": "",
            "message_raw": [],
            "message_history": [],
            "input_mode": self._normal_mode(),
            "terminated": False,
            "truncated": False,
            "terminal_reason": "",
            "reward": 0.0,
            "hp": initial_hp,
            "hp_max": max(1, int(dict(level.get("metadata", {})).get("hp_max", initial_hp))),
            "energy": initial_energy,
            "energy_max": max(0, int(dict(level.get("metadata", {})).get("energy_max", initial_energy))),
            "gold": int(dict(level.get("metadata", {})).get("gold", 0)),
            "experience": int(dict(level.get("metadata", {})).get("experience", 0)),
            "experience_level": max(1, int(dict(level.get("metadata", {})).get("experience_level", 1))),
            "ac": int(dict(level.get("metadata", {})).get("ac", 10)),
            "hunger": int(dict(level.get("metadata", {})).get("hunger", 900)),
            "hunger_state": "Not Hungry",
            "strength": int(dict(level.get("metadata", {})).get("strength", 18)),
            "dexterity": int(dict(level.get("metadata", {})).get("dexterity", 10)),
            "constitution": int(dict(level.get("metadata", {})).get("constitution", 10)),
            "intelligence": int(dict(level.get("metadata", {})).get("intelligence", 8)),
            "wisdom": int(dict(level.get("metadata", {})).get("wisdom", 8)),
            "charisma": int(dict(level.get("metadata", {})).get("charisma", 8)),
            "wielded": "",
            "worn": "",
            "accessories": [],
            "quiver": "",
            "last_command": "",
            "engraving": "",
        }
        self.nev = NevLog()
        self._reveal()
        self._event("task_resolved", "TaskResolved(dlvl1 capture-backed)", transition="reset", payload={"task_id": resolved["task_id"], "config_hash": resolved["config_hash"], "fixture_id": resolved.get("fixture_id", "")})
        self._message("You enter the dungeon.")

    def step(self, action_input: int | str) -> dict[str, Any]:
        if self.resolved is None:
            raise RuntimeError("engine must be reset before step")
        action = coerce_action(action_input)
        if self.state["terminated"] or self.state["truncated"]:
            self._event("rule_violation", "RuleViolation(terminal)", action=str(action_input), transition="reject", severity="warn")
            return self.symbolic_readout()
        if action is None:
            self._message("Unknown NLE action id.")
            self._event("rule_violation", "RuleViolation(unknown_action)", action=str(action_input), transition="reject", severity="warn")
            return self.symbolic_readout()
        self.state["step_index"] += 1
        self._event("action_applied", f"Action({action.canonical})", action=action.canonical, transition="dispatch", payload=action_payload(action))
        if self.state["input_mode"]["kind"] == "normal":
            spent_turn = self._dispatch_normal(action)
        else:
            spent_turn = self._consume_prompt(action)
        if spent_turn and not self.state["terminated"]:
            self._advance_turn()
        self._reveal()
        self._check_truncation()
        return self.symbolic_readout()

    def symbolic_readout(self) -> dict[str, Any]:
        return {"public": self.public_projection(), "private": self.private_projection(), "reward": self.state.get("reward", 0.0), "terminated": self.state.get("terminated", False), "truncated": self.state.get("truncated", False), "nev_cursor": self.nev.cursor()}

    def public_projection(self) -> dict[str, Any]:
        chars, colors, glyphs = self._render_planes()
        inventory = self._inventory_projection()
        blstats = self._blstats()
        return {
            "schema": "gamebench.nethack.dlvl1.public.v1",
            "chars": chars,
            "colors": colors,
            "glyphs": glyphs,
            "blstats": blstats,
            "blstats_fields": list(BLSTATS_FIELDS),
            "blstats_named": dict(zip(BLSTATS_FIELDS, blstats, strict=True)),
            "message": self._normalise_message(self.state["message"]),
            "message_raw": list(self.state["message_raw"]),
            "inventory": inventory,
            "input_mode": deepcopy(self.state["input_mode"]),
            "done": bool(self.state["terminated"] or self.state["truncated"]),
            "terminated": bool(self.state["terminated"]),
            "truncated": bool(self.state["truncated"]),
            "terminal_reason": self.state["terminal_reason"],
        }

    def private_projection(self) -> dict[str, Any]:
        if not self.resolved:
            return {}
        return {
            "task_id": self.resolved["task_id"],
            "fixture_id": self.resolved.get("fixture_id", ""),
            "episode_id": self.resolved["episode_id"],
            "config_hash": self.resolved["config_hash"],
            "step_index": self.state["step_index"],
            "time": self.state["time"],
            "rng": self.state["rng"],
            "hero": deepcopy(self.state["hero"]),
            "hp": self.state["hp"],
            "hp_max": self.state["hp_max"],
            "gold": self.state["gold"],
            "experience": self.state["experience"],
            "experience_level": self.state["experience_level"],
            "hunger": self.state["hunger"],
            "hunger_state": self.state["hunger_state"],
            "ac": self.state["ac"],
            "wielded": self.state["wielded"],
            "worn": self.state["worn"],
            "accessories": list(self.state["accessories"]),
            "quiver": self.state["quiver"],
            "inventory": deepcopy(self.state["inventory"]),
            "floor_items": deepcopy(self.state["floor_items"]),
            "monsters": deepcopy(self.state["monsters"]),
            "traps": deepcopy(self.state["traps"]),
            "seen": deepcopy(self.state["seen"]),
            "input_mode": deepcopy(self.state["input_mode"]),
            "terminated": self.state["terminated"],
            "truncated": self.state["truncated"],
            "terminal_reason": self.state["terminal_reason"],
            "reward": self.state["reward"],
        }

    def checkpoint_bytes(self) -> bytes:
        if self.resolved is None:
            raise RuntimeError("engine must be reset before checkpoint")
        return encode_checkpoint(env_family=self.ENV_FAMILY, resolved=self.resolved, state=self.state, nev_events=self.nev.export())

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = decode_checkpoint(blob)
        if payload.get("env_family") != self.ENV_FAMILY:
            raise ValueError(f"checkpoint belongs to {payload.get('env_family')!r}")
        self.resolved = deepcopy(payload["resolved"])
        self.state = deepcopy(payload["sim"])
        self.nev = NevLog.from_export(payload["nev_events"])
        return self.nev.cursor()

    def clone_for_sim(self) -> "NethackDlvl1Engine":
        clone = NethackDlvl1Engine()
        clone.resolved = deepcopy(self.resolved)
        clone.state = deepcopy(self.state)
        clone.nev = NevLog.from_export(self.nev.export())
        return clone

    def _dispatch_normal(self, action: NleAction) -> bool:
        self.state["last_command"] = action.canonical
        direction = direction_for(action)
        if direction is not None:
            return self._move(direction, running=action.enum_class == "CompassDirectionLonger")
        if action.canonical == "MiscDirection.DOWN":
            return self._descend()
        if action.canonical == "MiscDirection.UP":
            self._message("You can't go up here.")
            return False
        if action.canonical == "MiscDirection.WAIT":
            self._message("You wait.")
            return True
        if action.canonical == "MiscAction.MORE":
            self._message("Nothing more to display.")
            return False
        name = action.name
        if name == "ESC":
            self._message("Never mind.")
            return False
        if name == "OPEN":
            self._enter_mode("direction", action, "In what direction?", {"operation": "open"})
            return False
        if name in DIRECTION_COMMANDS:
            operation = {"MOVEFAR": "move", "RUSH": "move", "RUSH2": "move"}.get(name, name.lower())
            self._enter_mode("direction", action, "In what direction?", {"operation": operation, "running": name in {"MOVEFAR", "RUSH", "RUSH2"}, "force_move": name == "MOVE"})
            return False
        if name in ITEM_COMMANDS:
            after = "direction" if name in {"FIRE", "THROW", "ZAP"} else "normal"
            self._enter_mode("inventory_letter", action, "What do you want to use?", {"operation": name.lower(), "after": after})
            return False
        if name == "PICKUP":
            return self._pickup()
        if name == "SEARCH":
            return self._search()
        if name in {"PRAY", "QUIT", "SAVE"}:
            self._enter_mode("ynq", action, "Really do that? [ynq]", {"operation": name.lower()})
            return False
        if name in {"EXTCMD", "ENGRAVE"}:
            self._enter_mode("string", action, "What do you want to type?", {"operation": name.lower(), "buffer": ""})
            return False
        if name == "LOOT":
            self._enter_mode("menu", action, "Loot which item?", {"operation": "loot", "choices": []})
            return False
        if name == "EXTLIST":
            self._enter_mode("more", action, "--More--", {})
            return False
        if action.canonical == "UnsafeActions.HELP" or name == "HELP":
            self._message("Use the action map for the full NLE command surface.")
            return False
        if action.canonical == "UnsafeActions.PREVMSG" or name == "PREVMSG":
            self._message(self.state["message_history"][-2] if len(self.state["message_history"]) >= 2 else "No previous message.")
            return False
        if name in INFO_COMMANDS or action.enum_class == "TextCharacters":
            self._message(f"{action.canonical} is accepted in normal mode.")
            return False
        self._message(f"{action.canonical} is accepted but has no fixture effect.")
        return False

    def _consume_prompt(self, action: NleAction) -> bool:
        mode = dict(self.state["input_mode"])
        kind = mode["kind"]
        if action.name == "ESC":
            self._exit_mode("Never mind.")
            return False
        if kind == "more":
            if action.canonical == "MiscAction.MORE" or action.key in {"\r", "\n", " "}:
                self._exit_mode("")
            else:
                self._message("--More--")
            return False
        if kind == "direction":
            direction = direction_for(action)
            if direction is None:
                self._message("Specify a direction.")
                return False
            self._exit_mode("")
            operation = str(mode.get("operation", "move"))
            if operation == "open":
                return self._open(direction)
            if operation == "close":
                return self._close(direction)
            if operation == "kick":
                return self._kick(direction)
            if operation in {"fight", "force"}:
                return self._fight_direction(direction, force=True)
            if operation == "seetrap":
                return self._inspect_trap(direction)
            if operation == "untrap":
                return self._untrap(direction)
            if operation in {"fire", "throw", "zap"}:
                return self._projectile(direction, str(mode.get("item_id", "")), operation)
            return self._move(direction, running=bool(mode.get("running", False)), force_move=bool(mode.get("force_move", False)))
        if kind == "inventory_letter":
            letter = action.key
            if not letter or not letter.isprintable():
                self._message("Choose an inventory letter.")
                return False
            item = next((candidate for candidate in self.state["inventory"] if candidate["letter"] == letter), None)
            if item is None:
                self._message("You don't have that object.")
                return False
            operation = str(mode.get("operation", "apply"))
            after = str(mode.get("after", "normal"))
            self._exit_mode("")
            if after == "direction":
                self._enter_mode("direction", action, "In what direction?", {"operation": operation, "item_id": item["id"]})
                return False
            return self._use_item(operation, item)
        if kind == "ynq":
            answer = action.key.lower()
            if answer not in {"y", "n", "q"}:
                self._message("Please answer y, n, or q.")
                return False
            operation = str(mode.get("operation", ""))
            self._exit_mode("")
            if answer != "y":
                self._message("Never mind.")
                return False
            if operation == "quit":
                self._terminal("quit", "You quit the dungeon.", kind="terminal")
                return False
            if operation == "save":
                self._terminal("saved", "Saving is terminal in this single-episode service.", kind="terminal")
                return False
            if operation == "pray":
                self._message("You begin praying.")
                self._event("action_applied", "Pray()", transition="pray")
                return True
            self._message("That answer is accepted.")
            return False
        if kind == "string":
            if action.canonical == "MiscAction.MORE":
                operation = str(mode.get("operation", "command"))
                text = str(mode.get("buffer", ""))
                self._exit_mode("")
                if operation == "engrave":
                    self.state["engraving"] = text
                    self._message("You engrave on the floor.")
                    self._event("action_applied", "Engrave()", transition="engrave", payload={"text": text})
                    return True
                self._message(f"#{text or 'command'} is accepted by the capture adapter.")
                return False
            key = action.key
            if not key or not key.isprintable():
                self._message("Enter printable prompt text or MORE to finish.")
                return False
            mode["buffer"] = str(mode.get("buffer", "")) + key
            self.state["input_mode"] = mode
            self._message(mode["prompt"])
            return False
        if kind == "menu":
            self._exit_mode("Never mind.")
            return False
        self._message("Unknown input mode.")
        return False

    def _move(self, direction: tuple[int, int], *, running: bool = False, force_move: bool = False) -> bool:
        moves = 8 if running else 1
        moved = False
        for _ in range(moves):
            hero = self.state["hero"]
            x, y = int(hero["x"]) + direction[0], int(hero["y"]) + direction[1]
            if not self._in_bounds(x, y):
                if not moved:
                    self._message("You bump into the edge of the known level.")
                break
            monster = self._monster_at(x, y)
            if monster is not None and not force_move:
                self._fight(monster)
                return True
            terrain = self._terrain_at(x, y)
            if terrain in WALLS:
                if not moved:
                    self._message("You bump into a wall.")
                break
            if terrain not in PASSABLE:
                if not moved:
                    self._message("You cannot move there.")
                break
            if monster is not None:
                self._message("There is a monster in the way.")
                break
            hero["x"], hero["y"] = x, y
            moved = True
            self._event("move", f"Move({x},{y})", transition="move", payload={"x": x, "y": y, "running": running})
            if bool(self.resolved["rules"].get("autopickup", False)):
                self._pickup(silent=True)
            self._trigger_trap(x, y)
            if self.state["terminated"]:
                return True
            if not running:
                break
        if moved:
            self._message("You move.")
        return True

    def _open(self, direction: tuple[int, int]) -> bool:
        x, y = self._target(direction)
        if self._in_bounds(x, y) and self._terrain_at(x, y) == "+":
            self.state["terrain"][y][x] = "."
            self._message("The door opens.")
            self._event("action_applied", "OpenDoor()", transition="open", payload={"x": x, "y": y})
        else:
            self._message("You see no door there.")
        return True

    def _close(self, direction: tuple[int, int]) -> bool:
        x, y = self._target(direction)
        if self._in_bounds(x, y) and self._terrain_at(x, y) == ".":
            self.state["terrain"][y][x] = "+"
            self._message("The door closes.")
        else:
            self._message("You see no open door there.")
        return True

    def _kick(self, direction: tuple[int, int]) -> bool:
        x, y = self._target(direction)
        if not self._in_bounds(x, y) or self._terrain_at(x, y) != "+":
            self._message("You kick at empty space.")
            return True
        if self._roll(2) == 0:
            self.state["terrain"][y][x] = "."
            self._message("The door crashes open!")
        else:
            self._message("WHAMMM!!!")
        return True

    def _fight_direction(self, direction: tuple[int, int], *, force: bool) -> bool:
        x, y = self._target(direction)
        monster = self._monster_at(x, y)
        if monster:
            self._fight(monster)
        elif force:
            self._message("You attack thin air.")
        else:
            self._message("There is nothing to fight.")
        return True

    def _fight(self, monster: dict[str, Any]) -> None:
        weapon = self._item_by_id(self.state["wielded"])
        damage = 1 + self._roll(4) + (int(weapon["damage"]) if weapon else 0)
        monster["hp"] -= damage
        self._event("fight", f"Fight({monster['name']})", transition="attack", payload={"monster": monster["id"], "damage": damage})
        if monster["hp"] <= 0:
            self.state["monsters"] = [candidate for candidate in self.state["monsters"] if candidate["id"] != monster["id"]]
            self.state["experience"] += int(monster["experience"])
            self.state["reward"] += 0.1
            self._message(f"You kill the {monster['name']}!")
            self._event("kill", f"Kill({monster['name']})", transition="kill", payload={"monster": monster["id"], "experience": monster["experience"]})
        else:
            self._message(f"You hit the {monster['name']}.")

    def _pickup(self, *, silent: bool = False) -> bool:
        hero = self.state["hero"]
        items = [item for item in self.state["floor_items"] if item["position"]["x"] == hero["x"] and item["position"]["y"] == hero["y"]]
        if not items:
            if not silent:
                self._message("There is nothing here to pick up.")
            return False
        for item in items:
            if item["kind"] == "$":
                self.state["gold"] += item["quantity"]
                self._message(f"You pick up {item['quantity']} gold piece(s).")
            else:
                self.state["inventory"].append(item)
                self._assign_inventory_letters(self.state["inventory"])
                self._message(f"You pick up {item['name']}.")
            self._event("pickup", f"Pickup({item['name']})", transition="pickup", payload={"item": item["id"], "kind": item["kind"]})
            self.state["reward"] += 0.02
        picked = {item["id"] for item in items}
        self.state["floor_items"] = [item for item in self.state["floor_items"] if item["id"] not in picked]
        return True

    def _use_item(self, operation: str, item: dict[str, Any]) -> bool:
        if operation == "eat":
            self._remove_inventory_item(item["id"])
            self.state["hunger"] = min(2000, self.state["hunger"] + int(item["nutrition"]))
            self._message(f"You eat {item['name']}.")
            self._event("eat", f"Eat({item['name']})", transition="eat", payload={"item": item["id"], "nutrition": item["nutrition"]})
            return True
        if operation == "quaff":
            self._remove_inventory_item(item["id"])
            effect = item["effect"] or "healing"
            if effect == "healing":
                self.state["hp"] = min(self.state["hp_max"], self.state["hp"] + 6)
            self._message(f"You quaff {item['name']}.")
            self._event("action_applied", f"Quaff({item['name']})", transition="quaff", payload={"item": item["id"], "effect": effect})
            return True
        if operation == "read":
            self._remove_inventory_item(item["id"])
            self._message(f"You read {item['name']}.")
            self._event("action_applied", f"Read({item['name']})", transition="read", payload={"item": item["id"], "effect": item["effect"]})
            return True
        if operation == "wield":
            self.state["wielded"] = item["id"]
            self._message(f"You are now wielding {item['name']}.")
            self._event("wear", f"Wield({item['name']})", transition="wield", payload={"item": item["id"]})
            return True
        if operation == "wear":
            self.state["worn"] = item["id"]
            self.state["ac"] = max(-10, 10 - int(item["armor"]))
            self._message(f"You are now wearing {item['name']}.")
            self._event("wear", f"Wear({item['name']})", transition="wear", payload={"item": item["id"]})
            return True
        if operation == "takeoff":
            if self.state["worn"] == item["id"]:
                self.state["worn"] = ""
                self.state["ac"] = 10
            self._message(f"You take off {item['name']}.")
            return True
        if operation == "puton":
            if item["id"] not in self.state["accessories"]:
                self.state["accessories"].append(item["id"])
            self._message(f"You put on {item['name']}.")
            self._event("wear", f"PutOn({item['name']})", transition="puton", payload={"item": item["id"]})
            return True
        if operation == "remove":
            self.state["accessories"] = [entry for entry in self.state["accessories"] if entry != item["id"]]
            self._message(f"You remove {item['name']}.")
            return True
        if operation == "quiver":
            self.state["quiver"] = item["id"]
            self._message(f"You ready {item['name']} in your quiver.")
            return True
        if operation == "drop":
            self._remove_inventory_item(item["id"])
            item["position"] = {"x": self.state["hero"]["x"], "y": self.state["hero"]["y"]}
            self.state["floor_items"].append(item)
            self._message(f"You drop {item['name']}.")
            return True
        if operation in {"fire", "throw", "zap"}:
            self._message("Specify a direction.")
            return False
        self._message(f"You apply {item['name']}.")
        self._event("action_applied", f"Use({item['name']})", transition=operation, payload={"item": item["id"]})
        return True

    def _projectile(self, direction: tuple[int, int], item_id: str, operation: str) -> bool:
        item = self._item_by_id(item_id)
        if not item:
            self._message("That item is no longer available.")
            return False
        x, y = self._target(direction)
        monster = self._monster_at(x, y)
        if monster:
            damage = max(1, int(item["damage"]) + self._roll(3))
            monster["hp"] -= damage
            if monster["hp"] <= 0:
                self.state["monsters"] = [candidate for candidate in self.state["monsters"] if candidate["id"] != monster["id"]]
                self._message(f"The {operation} kills the {monster['name']}!")
                self._event("kill", f"Kill({monster['name']})", transition=operation, payload={"monster": monster["id"], "damage": damage})
            else:
                self._message(f"The {operation} hits the {monster['name']}.")
        else:
            self._message(f"The {operation} flies harmlessly.")
        return True

    def _search(self) -> bool:
        hero = self.state["hero"]
        found = False
        for trap in self.state["traps"]:
            if not trap["seen"] and max(abs(trap["position"]["x"] - hero["x"]), abs(trap["position"]["y"] - hero["y"])) <= 1:
                trap["seen"] = True
                found = True
        self._message("You find a trap." if found else "You search.")
        return True

    def _inspect_trap(self, direction: tuple[int, int]) -> bool:
        x, y = self._target(direction)
        trap = next((entry for entry in self.state["traps"] if entry["position"]["x"] == x and entry["position"]["y"] == y and entry["seen"]), None)
        self._message(f"That is a {trap['kind']} trap." if trap else "You see no trap there.")
        return False

    def _untrap(self, direction: tuple[int, int]) -> bool:
        x, y = self._target(direction)
        trap = next((entry for entry in self.state["traps"] if entry["position"]["x"] == x and entry["position"]["y"] == y), None)
        if trap:
            self.state["traps"] = [entry for entry in self.state["traps"] if entry["id"] != trap["id"]]
            self._message("You disarm the trap.")
        else:
            self._message("You find no trap to disarm.")
        return True

    def _descend(self) -> bool:
        hero = self.state["hero"]
        tile = self._terrain_at(int(hero["x"]), int(hero["y"]))
        if tile != ">":
            self._message("You can't go down here.")
            return False
        self._event("stairs_descend", "StairsDescend(dlvl1)", transition="descend", payload={"dungeon_level": 1})
        self._terminal("descended", "You descend from dlvl 1.", kind="terminal", reward_delta=1.0)
        return False

    def _advance_turn(self) -> None:
        self.state["time"] += 1
        self.state["hunger"] = max(0, int(self.state["hunger"]) - 1)
        self._update_hunger_state()
        if self.state["hunger"] == 0:
            self.state["hp"] -= 1
            if self.state["hp"] <= 0:
                self._terminal("death", "You die of hunger.", kind="death", reward_delta=-1.0)
                return
        hero = self.state["hero"]
        for monster in list(self.state["monsters"]):
            if monster["peaceful"] or monster["pet"]:
                continue
            distance = max(abs(monster["position"]["x"] - hero["x"]), abs(monster["position"]["y"] - hero["y"]))
            if distance <= 1:
                damage = max(1, int(monster["attack"]) + self._roll(2) - 1)
                self.state["hp"] -= damage
                self._event("fight", f"MonsterAttack({monster['name']})", transition="monster_attack", payload={"monster": monster["id"], "damage": damage})
                if self.state["hp"] <= 0:
                    self._terminal("death", f"You die from the {monster['name']}'s attack.", kind="death", reward_delta=-1.0)
                    return
                self._message(f"The {monster['name']} bites!")
            elif distance <= 6:
                self._move_monster_toward(monster, hero)

    def _move_monster_toward(self, monster: dict[str, Any], hero: dict[str, Any]) -> None:
        dx = 0 if monster["position"]["x"] == hero["x"] else (1 if hero["x"] > monster["position"]["x"] else -1)
        dy = 0 if monster["position"]["y"] == hero["y"] else (1 if hero["y"] > monster["position"]["y"] else -1)
        x, y = monster["position"]["x"] + dx, monster["position"]["y"] + dy
        if self._in_bounds(x, y) and self._terrain_at(x, y) in PASSABLE and not self._monster_at(x, y) and (x, y) != (hero["x"], hero["y"]):
            monster["position"] = {"x": x, "y": y}

    def _trigger_trap(self, x: int, y: int) -> None:
        for trap in self.state["traps"]:
            if trap["triggered"] or trap["position"]["x"] != x or trap["position"]["y"] != y:
                continue
            trap["triggered"] = True
            trap["seen"] = True
            self.state["hp"] -= int(trap["damage"])
            self._message(f"You trigger a {trap['kind']} trap!")
            self._event("action_applied", f"Trap({trap['kind']})", transition="trap", payload={"trap": trap["id"], "damage": trap["damage"]})
            if self.state["hp"] <= 0:
                self._terminal("death", "You die from a trap.", kind="death", reward_delta=-1.0)

    def _terminal(self, reason: str, message: str, *, kind: str, reward_delta: float = 0.0) -> None:
        self.state["terminated"] = True
        self.state["terminal_reason"] = reason
        self.state["reward"] += reward_delta
        self._message(message)
        self._event(kind, f"Terminal({reason})", transition=reason, payload={"terminal_reason": reason, "reward_delta": reward_delta})

    def _check_truncation(self) -> None:
        max_steps = int(self.resolved["rules"].get("max_steps", 0)) if self.resolved else 0
        if max_steps > 0 and self.state["step_index"] >= max_steps and not self.state["terminated"]:
            self.state["truncated"] = True
            self.state["terminal_reason"] = "max_steps"
            self._message("Episode truncated at max_steps.")
            self._event("episode_truncated", "Terminal(max_steps)", transition="max_steps", payload={"max_steps": max_steps})

    def _render_planes(self) -> tuple[list[str], list[list[int]], list[list[int]]]:
        chars = [[" "] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
        colors = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
        glyphs = [[0] * VIEW_WIDTH for _ in range(VIEW_HEIGHT)]
        for y in range(VIEW_HEIGHT):
            for x in range(VIEW_WIDTH):
                if not self.state["seen"][y][x]:
                    continue
                chars[y][x] = self.state["terrain"][y][x]
                colors[y][x] = int(self.state["base_colors"][y][x])
                glyphs[y][x] = int(self.state["base_glyphs"][y][x])
        for item in self.state["floor_items"]:
            x, y = item["position"]["x"], item["position"]["y"]
            if self._in_bounds(x, y) and self.state["seen"][y][x]:
                chars[y][x], colors[y][x], glyphs[y][x] = item["kind"], int(item["color"]), int(item["glyph"])
        for monster in self.state["monsters"]:
            x, y = monster["position"]["x"], monster["position"]["y"]
            if self._in_bounds(x, y) and self.state["seen"][y][x]:
                chars[y][x], colors[y][x], glyphs[y][x] = monster["char"], int(monster["color"]), int(monster["glyph"])
        hero = self.state["hero"]
        chars[hero["y"]][hero["x"]] = "@"
        colors[hero["y"]][hero["x"]] = int(hero["color"])
        glyphs[hero["y"]][hero["x"]] = int(hero["glyph"])
        return ["".join(row) for row in chars], colors, glyphs

    def _inventory_projection(self) -> dict[str, Any]:
        letters = [0] * 55
        glyphs = [0] * 55
        oclasses = [0] * 55
        strings = [""] * 55
        for index, item in enumerate(self.state["inventory"][:55]):
            letters[index] = ord(item["letter"]) if item["letter"] else 0
            glyphs[index] = int(item["glyph"])
            oclasses[index] = int(item["oclass"])
            strings[index] = f"{item['letter']} - {item['name']}"
        return {"inv_letters": letters, "inv_glyphs": glyphs, "inv_oclasses": oclasses, "inv_strs": strings, "items": deepcopy(self.state["inventory"])}

    def _blstats(self) -> list[int]:
        hero = self.state["hero"]
        return [
            int(hero["x"]), int(hero["y"]), self.state["strength"], 0, self.state["dexterity"], self.state["constitution"], self.state["intelligence"], self.state["wisdom"], self.state["charisma"], self.state["experience"],
            self.state["hp"], self.state["hp_max"], 1, self.state["gold"], self.state["energy"], self.state["energy_max"], self.state["ac"], 1, self.state["experience_level"], self.state["experience"],
            self.state["time"], self._hunger_code(), 0, 0, 1,
        ]

    def _normal_mode(self) -> dict[str, Any]:
        return {"kind": "normal", "command": "", "prompt": "", "operation": ""}

    def _enter_mode(self, kind: str, action: NleAction, prompt: str, extra: dict[str, Any]) -> None:
        self.state["input_mode"] = {"kind": kind, "command": action.canonical, "prompt": prompt, **deepcopy(extra)}
        self._message(prompt)
        self._event("mode_enter", f"ModeEnter({kind})", action=action.canonical, transition=kind, payload=deepcopy(self.state["input_mode"]))

    def _exit_mode(self, message: str) -> None:
        prior = deepcopy(self.state["input_mode"])
        self.state["input_mode"] = self._normal_mode()
        self._event("mode_exit", f"ModeExit({prior['kind']})", transition=prior["kind"], payload={"prior": prior})
        if message:
            self._message(message)

    def _message(self, text: str) -> None:
        self.state["message"] = text
        self.state["message_raw"] = list(text.encode("utf-8"))
        self.state["message_history"].append(text)
        self._event("message", f"Message({text})", transition="message", payload={"raw": list(self.state["message_raw"])})

    def _event(self, kind: str, message: str, *, action: str | None = None, transition: str | None = None, severity: str = "info", payload: dict[str, Any] | None = None) -> None:
        episode_id = self.resolved["episode_id"] if self.resolved else "unresolved"
        self.nev.append(step_index=int(self.state.get("step_index", 0)), episode_id=episode_id, kind=kind, message=message, action=action, transition=transition, severity=severity, payload=payload)

    def _reveal(self) -> None:
        hero = self.state["hero"]
        radius = int(self.resolved["rules"].get("vision_radius", 4)) if self.resolved else 4
        for y in range(max(0, hero["y"] - radius), min(VIEW_HEIGHT, hero["y"] + radius + 1)):
            for x in range(max(0, hero["x"] - radius), min(VIEW_WIDTH, hero["x"] + radius + 1)):
                self.state["seen"][y][x] = True

    def _update_hunger_state(self) -> None:
        hunger = self.state["hunger"]
        self.state["hunger_state"] = "Satiated" if hunger > 1400 else "Not Hungry" if hunger > 500 else "Hungry" if hunger > 200 else "Weak" if hunger > 0 else "Fainting"

    def _hunger_code(self) -> int:
        return {"Satiated": 0, "Not Hungry": 1, "Hungry": 2, "Weak": 3, "Fainting": 4}.get(self.state["hunger_state"], 1)

    def _roll(self, upper: int) -> int:
        self.state["rng"] = (1664525 * int(self.state["rng"]) + 1013904223) & 0xFFFFFFFF
        return int(self.state["rng"]) % max(1, upper)

    def _target(self, direction: tuple[int, int]) -> tuple[int, int]:
        hero = self.state["hero"]
        return int(hero["x"]) + direction[0], int(hero["y"]) + direction[1]

    def _terrain_at(self, x: int, y: int) -> str:
        return self.state["terrain"][y][x]

    def _monster_at(self, x: int, y: int) -> dict[str, Any] | None:
        return next((monster for monster in self.state["monsters"] if monster["position"]["x"] == x and monster["position"]["y"] == y), None)

    def _item_by_id(self, item_id: str) -> dict[str, Any] | None:
        return next((item for item in self.state["inventory"] if item["id"] == item_id), None)

    def _remove_inventory_item(self, item_id: str) -> None:
        self.state["inventory"] = [item for item in self.state["inventory"] if item["id"] != item_id]
        self._assign_inventory_letters(self.state["inventory"])
        if self.state["wielded"] == item_id:
            self.state["wielded"] = ""
        if self.state["worn"] == item_id:
            self.state["worn"] = ""
            self.state["ac"] = 10
        self.state["accessories"] = [entry for entry in self.state["accessories"] if entry != item_id]

    @staticmethod
    def _assign_inventory_letters(inventory: list[dict[str, Any]]) -> None:
        used = {item["letter"] for item in inventory if item.get("letter")}
        next_letters = (chr(code) for code in range(ord("a"), ord("z") + 1))
        for item in inventory:
            if item.get("letter"):
                continue
            item["letter"] = next(letter for letter in next_letters if letter not in used)
            used.add(item["letter"])

    @staticmethod
    def _normalise_message(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _in_bounds(x: int, y: int) -> bool:
        return 0 <= x < VIEW_WIDTH and 0 <= y < VIEW_HEIGHT
