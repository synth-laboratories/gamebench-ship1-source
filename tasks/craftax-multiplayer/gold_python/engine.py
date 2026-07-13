from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from typing import Any

from .constants import AGENT_IDS, BASE_ACTIONS, GLYPHS, MAP_SIZE, MAX_TIMESTEPS, NUM_LEVELS, REQUEST_ACTIONS, REQUEST_DURATION, RESOURCES, ROLES
from .state import Player, WorldState


class CraftaxCoopEnv:
    """Deterministic, simultaneous, shared-reward Craftax-Coop model."""

    env_family = "craftax-multiplayer"

    def __init__(self, agent_count: int = 3, max_timesteps: int = MAX_TIMESTEPS, view_radius: int = 5):
        if agent_count < 2:
            raise ValueError("Craftax-Coop requires at least two agents")
        self.agent_ids = tuple(f"agent_{i}" for i in range(agent_count))
        self.max_timesteps = max_timesteps
        self.view_radius = view_radius
        self.state: WorldState | None = None

    @staticmethod
    def _generate_maps(seed: int) -> list[list[list[str]]]:
        maps = []
        resources = ("tree", "stone", "coal", "iron", "diamond", "ruby", "sapphire")
        for level in range(NUM_LEVELS):
            rng = random.Random((seed + 1) * 1_000_003 + level * 97)
            grid = [["grass" for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
            for i in range(MAP_SIZE):
                grid[0][i] = grid[-1][i] = grid[i][0] = grid[i][-1] = "stone"
            for y in range(1, MAP_SIZE - 1):
                for x in range(1, MAP_SIZE - 1):
                    roll = rng.random()
                    if roll < .055: grid[y][x] = "water"
                    elif roll < .18: grid[y][x] = resources[min(6, level // 2 + rng.randrange(3))]
            if level < NUM_LEVELS - 1: grid[MAP_SIZE - 3][MAP_SIZE - 3] = "stairs_down"
            if level > 0: grid[2][2] = "stairs_up"
            if level == NUM_LEVELS - 1: grid[MAP_SIZE // 2][MAP_SIZE // 2] = "boss"
            maps.append(grid)
        return maps

    def reset(self, seed: int = 0) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        players = [Player(a, ROLES[i % len(ROLES)], 3 + i, 3) for i, a in enumerate(self.agent_ids)]
        self.state = WorldState(seed, 0, self.max_timesteps, players, self._generate_maps(seed), [])
        self._event("game_started", task_id=self.env_family, seed=seed)
        return self.observations(), {"seed": seed, "state_hash": self.state_hash()}

    def _event(self, kind: str, **payload: Any) -> None:
        assert self.state is not None
        event = {"timestep": self.state.timestep, "kind": kind, **payload}
        self.state.nev.append(event)
        self.state.last_joint_event.append(event)
        args = ",".join(str(v) for v in payload.values())
        label = "".join(part.title() for part in kind.split("_"))
        self.state.legacy_nev.append(f"{label}({args})")

    def legal_actions(self, agent_id: str) -> list[str]:
        actions = list(BASE_ACTIONS + REQUEST_ACTIONS)
        actions.extend(f"give_{resource}_to_{other}" for resource in RESOURCES for other in self.agent_ids if other != agent_id)
        return actions

    def step(self, joint_action: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, float], dict[str, bool], dict[str, Any]]:
        state = self._require_state()
        if state.terminated: raise RuntimeError("step called after terminal state")
        if set(joint_action) != set(self.agent_ids): raise ValueError("joint_action must contain every agent exactly once")
        state.last_joint_event = []
        before = sum(state.achievements.values())
        normalized = {a: self._normalize_action(joint_action[a]) for a in self.agent_ids}
        self._expire_requests()
        # Requests are visible before trades in the same simultaneous turn.
        for i, agent_id in enumerate(self.agent_ids): self._apply_request(state.players[i], normalized[agent_id])
        self._resolve_movement(normalized)
        for i, agent_id in enumerate(self.agent_ids): self._apply_nonmovement(state.players[i], normalized[agent_id])
        self._world_tick()
        state.timestep += 1
        state.achievements["all_roles_alive"] = all(p.alive for p in state.players)
        if not any(p.alive for p in state.players): self._terminate("death")
        elif state.boss_progress >= NUM_LEVELS - 1: self._terminate("boss")
        elif state.timestep >= state.max_timesteps: self._terminate("timestep")
        gained = sum(state.achievements.values()) - before
        reward = float(gained + (10 if state.termination_reason == "boss" else 0))
        rewards = {a: reward for a in self.agent_ids}
        dones = {a: state.terminated for a in self.agent_ids} | {"__all__": state.terminated}
        return self.observations(), rewards, dones, {"events": deepcopy(state.last_joint_event), "state_hash": self.state_hash(), "termination_reason": state.termination_reason}

    @staticmethod
    def _normalize_action(action: Any) -> dict[str, Any]:
        if isinstance(action, str): return {"kind": action}
        if not isinstance(action, dict) or not isinstance(action.get("kind"), str): raise ValueError("actions must be strings or objects with kind")
        return action

    def _expire_requests(self) -> None:
        for p in self._require_state().players:
            p.request_duration = max(0, p.request_duration - 1)
            if p.request_duration == 0: p.request_type = None

    def _apply_request(self, p: Player, action: dict[str, Any]) -> None:
        kind = action["kind"]
        if kind.startswith("request_") and kind[8:] in RESOURCES:
            p.request_type, p.request_duration = kind[8:], REQUEST_DURATION
            self._event("request_made", agent_id=p.agent_id, resource=p.request_type, duration=REQUEST_DURATION)

    def _resolve_movement(self, actions: dict[str, dict[str, Any]]) -> None:
        state = self._require_state(); desired: dict[str, tuple[int, int]] = {}
        delta = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
        for p in state.players:
            kind = actions[p.agent_id]["kind"]
            if kind in delta and p.alive:
                dx, dy = delta[kind]; p.facing = kind
                nx, ny = p.x + dx, p.y + dy
                if state.maps[p.level][ny][nx] not in ("stone", "water"): desired[p.agent_id] = (nx, ny)
        counts = {pos: list(desired.values()).count(pos) for pos in desired.values()}
        occupied = {(p.level, p.x, p.y) for p in state.players if p.alive}
        for p in state.players:
            pos = desired.get(p.agent_id)
            if pos and counts[pos] == 1 and (p.level, *pos) not in occupied:
                p.x, p.y = pos; self._event("move_applied", agent_id=p.agent_id, x=p.x, y=p.y, level=p.level)

    def _apply_nonmovement(self, p: Player, action: dict[str, Any]) -> None:
        if not p.alive: return
        kind = action["kind"]
        if kind.startswith("give_"): self._give(p, kind)
        elif kind in ("do", "attack"): self._do(p)
        elif kind == "descend": self._change_level(p, 1)
        elif kind == "ascend": self._change_level(p, -1)
        elif kind == "rest": p.energy = min(9, p.energy + (4 if p.role == "forager" else 2))
        elif kind == "cast_spell" and p.role == "forager":
            for ally in self._require_state().players: ally.health = min(9, ally.health + 2)
            self._event("role_ability", agent_id=p.agent_id, ability="team_heal")
        elif kind.startswith("make_"): self._craft(p, kind)

    def _give(self, giver: Player, kind: str) -> None:
        rest = kind[5:]
        try: resource, target_id = rest.split("_to_", 1)
        except ValueError: return
        target = next((p for p in self._require_state().players if p.agent_id == target_id), None)
        if target is None or target is giver or target.request_type != resource or target.request_duration <= 0: return
        if resource in ("food", "drink"):
            stock = getattr(giver, resource)
            if stock <= 0: return
            setattr(giver, resource, stock - 1); setattr(target, resource, min(9, getattr(target, resource) + 1))
        else:
            if giver.inventory[resource] <= 0: return
            giver.inventory[resource] -= 1; target.inventory[resource] += 1
        target.request_type, target.request_duration = None, 0
        state = self._require_state(); state.trade_count += 1; state.achievements["trade"] = True
        self._event("trade_applied", giver=giver.agent_id, receiver=target.agent_id, resource=resource)

    def _do(self, p: Player) -> None:
        state = self._require_state(); dx, dy = {"left": (-1,0), "right": (1,0), "up": (0,-1), "down": (0,1)}[p.facing]
        x, y = p.x + dx, p.y + dy; tile = state.maps[p.level][y][x]
        mapping = {"tree":"wood", "stone":"stone", "coal":"coal", "iron":"iron", "diamond":"diamond", "ruby":"ruby", "sapphire":"sapphire"}
        if tile in mapping:
            resource = mapping[tile]
            if resource in ("iron", "coal", "diamond", "ruby", "sapphire") and p.role != "miner": return
            amount = 2 if p.role == "miner" and resource not in ("wood",) else 1
            p.inventory[resource] += amount; state.maps[p.level][y][x] = "grass"
            key = f"collect_{resource}"; state.achievements[key] = key in state.achievements
            self._event("resource_collected", agent_id=p.agent_id, resource=resource, amount=amount)
        elif tile == "boss" and p.level == NUM_LEVELS - 1:
            damage = 2 * (2 if p.role == "warrior" else 1) + p.sword
            state.boss_health -= damage; state.achievements["damage_boss"] = True
            self._event("boss_damaged", agent_id=p.agent_id, damage=damage, remaining=max(0,state.boss_health))
            if state.boss_health <= 0:
                state.boss_progress = NUM_LEVELS - 1; state.achievements["defeat_boss"] = True

    def _change_level(self, p: Player, direction: int) -> None:
        tile = self._require_state().maps[p.level][p.y][p.x]
        required = "stairs_down" if direction > 0 else "stairs_up"
        if tile == required and 0 <= p.level + direction < NUM_LEVELS:
            p.level += direction; p.x = p.y = 2 if direction < 0 else 3
            self._require_state().achievements["descend"] |= direction > 0
            self._event("level_changed", agent_id=p.agent_id, level=p.level)

    def _craft(self, p: Player, kind: str) -> None:
        recipes = {"make_wood_pickaxe": ("wood",1,"pickaxe",1), "make_stone_pickaxe": ("stone",2,"pickaxe",2), "make_iron_pickaxe": ("iron",2,"pickaxe",3), "make_diamond_pickaxe": ("diamond",2,"pickaxe",4), "make_wood_sword": ("wood",1,"sword",1), "make_stone_sword": ("stone",2,"sword",2), "make_iron_sword": ("iron",2,"sword",3), "make_diamond_sword": ("diamond",2,"sword",4), "make_iron_armour": ("iron",3,"armour",1), "make_diamond_armour": ("diamond",3,"armour",2)}
        recipe = recipes.get(kind)
        if not recipe: return
        resource, cost, item, tier = recipe
        if p.inventory[resource] < cost: return
        if resource in ("iron", "diamond") and p.role != "miner": return
        p.inventory[resource] -= cost; setattr(p, item, max(getattr(p,item), tier))
        self._require_state().achievements[f"craft_{item}"] = True
        self._event("item_crafted", agent_id=p.agent_id, item=item, tier=tier)

    def _world_tick(self) -> None:
        state = self._require_state()
        for p in state.players:
            if not p.alive: continue
            p.energy = max(0, p.energy - 1)
            if state.timestep % 25 == 24: p.food = max(0, p.food - 1); p.drink = max(0, p.drink - 1)
            if p.food == 0 or p.drink == 0: p.health -= 1
            if p.level == NUM_LEVELS - 1 and state.boss_health > 0: p.health -= max(0, 2 - p.armour)
            if p.health <= 0: p.health = 0; p.alive = False; self._event("player_died", agent_id=p.agent_id)

    def _terminate(self, reason: str) -> None:
        state = self._require_state(); state.terminated = True; state.termination_reason = reason
        self._event("game_ended", outcome=reason)

    def observations(self) -> dict[str, dict[str, Any]]:
        state = self._require_state(); dashboard = [self._player_summary(p) for p in state.players]
        return {p.agent_id: {"agent_id":p.agent_id,"agent_index":i,"role":p.role,"legal_agent_ids":list(self.agent_ids),"legal_actions":self.legal_actions(p.agent_id),"self":self._player_summary(p),"teammate_dashboard":deepcopy(dashboard),"level":p.level,"map_size":[MAP_SIZE,MAP_SIZE],"num_levels":NUM_LEVELS,"local_view":self._local_view(p),"ascii":self.render_ascii(p.agent_id),"shared":{"timestep":state.timestep,"boss_health":state.boss_health,"boss_progress":state.boss_progress,"trade_count":state.trade_count,"achievements":deepcopy(state.achievements)},"last_joint_event":deepcopy(state.last_joint_event)} for i,p in enumerate(state.players)}

    @staticmethod
    def _player_summary(p: Player) -> dict[str, Any]:
        return {"agent_id":p.agent_id,"role":p.role,"position":[p.x,p.y],"level":p.level,"health":p.health,"food":p.food,"drink":p.drink,"energy":p.energy,"alive":p.alive,"inventory":deepcopy(p.inventory),"equipment":{"pickaxe":p.pickaxe,"sword":p.sword,"armour":p.armour,"arrows":p.arrows},"request":{"resource":p.request_type,"remaining":p.request_duration}}

    def _local_view(self, p: Player) -> list[list[dict[str, Any]]]:
        state=self._require_state(); out=[]
        for y in range(p.y-self.view_radius,p.y+self.view_radius+1):
            row=[]
            for x in range(p.x-self.view_radius,p.x+self.view_radius+1):
                terrain = "out_of_bounds" if not (0<=x<MAP_SIZE and 0<=y<MAP_SIZE) else state.maps[p.level][y][x]
                agents=[q.agent_id for q in state.players if q.alive and q.level==p.level and q.x==x and q.y==y]
                row.append({"x":x,"y":y,"terrain":terrain,"agents":agents})
            out.append(row)
        return out

    def render_ascii(self, agent_id: str) -> str:
        p=next(p for p in self._require_state().players if p.agent_id==agent_id); rows=[]
        for row in self._local_view(p):
            rows.append("".join((cell["agents"][0][-1] if cell["agents"] else GLYPHS.get(cell["terrain"],"#")) for cell in row))
        return "\n".join(rows)

    def checkpoint(self) -> dict[str, Any]: return {"schema_version":"craftax-coop.checkpoint.v1","state":deepcopy(self._require_state().to_dict())}
    def restore(self, checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if checkpoint.get("schema_version") != "craftax-coop.checkpoint.v1": raise ValueError("unsupported checkpoint schema")
        self.state=WorldState.from_dict(deepcopy(checkpoint["state"])); self.agent_ids=tuple(p.agent_id for p in self.state.players); return self.observations()
    def state_hash(self) -> str: return hashlib.sha256(json.dumps(self._require_state().to_dict(),sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    def _require_state(self) -> WorldState:
        if self.state is None: raise RuntimeError("reset or restore required")
        return self.state
