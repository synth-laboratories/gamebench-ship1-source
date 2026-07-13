from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .constants import BASE_ACTIONS, BOSS_HEALTH, DAY_LENGTH, GLYPHS, MAP_SIZE, MAX_TIMESTEPS, MOB_STATS, NUM_LEVELS, POTION_COLOURS, REQUEST_ACTIONS, REQUEST_DURATION, RESOURCES, ROLES
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
            rng = (seed + 1) * 1_000_003 + level * 97
            grid = [["grass" for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
            for i in range(MAP_SIZE):
                grid[0][i] = grid[-1][i] = grid[i][0] = grid[i][-1] = "stone"
            for y in range(1, MAP_SIZE - 1):
                for x in range(1, MAP_SIZE - 1):
                    rng = (rng * 6_364_136_223_846_793_005 + 1) & ((1 << 64) - 1)
                    roll = ((rng >> 32) % 1000) / 1000
                    if roll < .055: grid[y][x] = "water" if level < 6 else ("lava" if level == 6 else "ice_grass")
                    elif roll < .18: grid[y][x] = resources[((rng >> 16) + level // 2) % len(resources)]
                    elif roll < .19: grid[y][x] = "chest"
                    elif roll < .20 and level == 0: grid[y][x] = "plant"
            if level < NUM_LEVELS - 1: grid[MAP_SIZE - 3][MAP_SIZE - 3] = "stairs_down"
            if level > 0: grid[2][2] = "stairs_up"
            if level == NUM_LEVELS - 1: grid[MAP_SIZE // 2][MAP_SIZE // 2] = "boss"
            maps.append(grid)
        return maps

    def reset(self, seed: int = 0) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        players = [Player(a, ROLES[i % len(ROLES)], 3 + i, 3) for i, a in enumerate(self.agent_ids)]
        maps = self._generate_maps(seed)
        monsters = self._spawn_initial_monsters(seed, maps)
        self.state = WorldState(seed, 0, self.max_timesteps, players, maps, monsters, boss_health=BOSS_HEALTH)
        self._event("game_started", task_id=self.env_family, seed=seed)
        return self.observations(), {"seed": seed, "state_hash": self.state_hash()}

    @staticmethod
    def _spawn_initial_monsters(seed: int, maps: list[list[list[str]]]) -> list[dict[str, Any]]:
        monsters = []
        kinds = tuple(MOB_STATS)
        for level in range(NUM_LEVELS - 1):
            for index in range(3 + level):
                value = ((seed + 17) * 1_103_515_245 + level * 7919 + index * 104729) & 0xFFFFFFFF
                x, y = 6 + value % 36, 6 + (value // 37) % 36
                if maps[level][y][x] in ("grass", "path", "sand", "gravel"):
                    kind = kinds[min(len(kinds) - 1, level + index % 2)]
                    health, damage = MOB_STATS[kind]
                    monsters.append({"id": f"mob_{level}_{index}", "kind": kind, "level": level, "x": x, "y": y, "health": health, "damage": damage})
        return monsters

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
        self._update_projectiles()
        self._update_monsters()
        self._update_plants()
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
        elif kind == "sleep": p.sleeping = True
        elif kind == "shoot_arrow": self._shoot_arrow(p)
        elif kind == "cast_spell" and p.role == "forager" and p.mana >= 2:
            p.mana -= 2
            for ally in self._require_state().players: ally.health = min(9, ally.health + 2)
            self._require_state().achievements["cast_spell"] = True
            self._event("role_ability", agent_id=p.agent_id, ability="team_heal")
        elif kind.startswith("make_"): self._craft(p, kind)
        elif kind.startswith("place_"): self._place(p, kind)
        elif kind.startswith("drink_potion_"): self._drink_potion(p, kind.removeprefix("drink_potion_"))
        elif kind == "read_book": self._read_book(p)
        elif kind.startswith("enchant_"): self._enchant(p, kind.removeprefix("enchant_"))
        elif kind.startswith("level_up_"): self._level_up(p, kind.removeprefix("level_up_"))

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
        elif tile == "ripe_plant" and p.role == "forager":
            p.food = min(9 + 2 * p.dexterity, p.food + 4); state.maps[p.level][y][x] = "plant"
            state.achievements["eat_plant"] = True; self._event("plant_eaten", agent_id=p.agent_id)
        elif tile == "fountain":
            p.drink = min(9 + 2 * p.dexterity, p.drink + 5); self._event("fountain_used", agent_id=p.agent_id)
        elif tile == "chest":
            state.maps[p.level][y][x] = "grass"; p.books += 1; p.arrows += 2
            colour = POTION_COLOURS[(state.seed + state.timestep + p.level) % len(POTION_COLOURS)]; p.potions[colour] += 1
            if p.role == "miner": p.inventory[("coal", "iron", "diamond")[min(2, p.level // 3)]] += 2
            state.achievements["open_chest"] = True; self._event("chest_opened", agent_id=p.agent_id)
        else:
            mob = next((m for m in state.monsters if m["level"] == p.level and m["x"] == x and m["y"] == y), None)
            if mob:
                damage = 1 + p.strength + p.sword * 2
                if p.role == "warrior": damage *= 2
                mob["health"] -= damage; self._event("mob_damaged", agent_id=p.agent_id, mob_id=mob["id"], damage=damage)
                if mob["health"] <= 0:
                    state.monsters.remove(mob); p.xp += 1; p.level_points += int(p.xp in (3, 7, 12, 18))
                    state.achievements["defeat_monster"] = True; self._event("mob_defeated", agent_id=p.agent_id, mob_id=mob["id"])
        if tile == "boss" and p.level == NUM_LEVELS - 1:
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

    def _place(self, p: Player, kind: str) -> None:
        state = self._require_state(); dx, dy = {"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}[p.facing]; x,y=p.x+dx,p.y+dy
        recipes = {"place_stone":("stone",1,"stone"),"place_table":("wood",2,"crafting_table"),"place_furnace":("stone",4,"furnace"),"place_plant":("saplings",1,"plant"),"place_torch":("torches",1,"path")}
        recipe=recipes.get(kind)
        if not recipe or state.maps[p.level][y][x] not in ("grass","path","sand","gravel"): return
        resource,cost,tile=recipe; stock=p.saplings if resource=="saplings" else p.torches if resource=="torches" else p.inventory[resource]
        if stock<cost:return
        if resource=="saplings":p.saplings-=cost
        elif resource=="torches":p.torches-=cost
        else:p.inventory[resource]-=cost
        state.maps[p.level][y][x]=tile
        key={"place_table":"place_table","place_furnace":"place_furnace","place_plant":"place_plant"}.get(kind)
        if key:state.achievements[key]=True
        self._event("block_placed",agent_id=p.agent_id,tile=tile,x=x,y=y)

    def _shoot_arrow(self,p:Player)->None:
        if p.arrows<=0:return
        p.arrows-=1; dx,dy={"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}[p.facing]
        self._require_state().projectiles.append({"owner":p.agent_id,"level":p.level,"x":p.x,"y":p.y,"dx":dx,"dy":dy,"damage":2+p.dexterity+(2 if p.role=="warrior" else 0),"ttl":8})
        self._require_state().achievements["shoot_arrow"]=True;self._event("arrow_shot",agent_id=p.agent_id)

    def _drink_potion(self,p:Player,colour:str)->None:
        if colour not in p.potions or p.potions[colour]<=0:return
        p.potions[colour]-=1
        if colour=="red":p.health=min(9+2*p.strength,p.health+5)
        elif colour=="green":p.food=min(9+2*p.dexterity,p.food+5)
        elif colour=="blue":p.drink=min(9+2*p.dexterity,p.drink+5)
        elif colour=="pink":p.mana=min(9+2*p.intelligence,p.mana+5)
        elif colour=="cyan":p.energy=min(9,p.energy+5)
        else:p.level_points+=1
        self._require_state().achievements["drink_potion"]=True;self._event("potion_drunk",agent_id=p.agent_id,colour=colour)

    def _read_book(self,p:Player)->None:
        if p.books<=0:return
        p.books-=1;p.intelligence+=1;p.mana=min(9+2*p.intelligence,p.mana+2)
        self._require_state().achievements["read_book"]=True;self._event("book_read",agent_id=p.agent_id)

    def _enchant(self,p:Player,item:str)->None:
        if p.inventory["ruby"]<1 or p.inventory["sapphire"]<1 or item not in ("sword","armour","bow"):return
        p.inventory["ruby"]-=1;p.inventory["sapphire"]-=1;setattr(p,f"{item}_enchantment","fire" if (self._require_state().seed+self._require_state().timestep)%2==0 else "ice")
        self._require_state().achievements["enchant_item"]=True;self._event("item_enchanted",agent_id=p.agent_id,item=item)

    def _level_up(self,p:Player,attribute:str)->None:
        if p.level_points<=0 or attribute not in ("dexterity","strength","intelligence"):return
        p.level_points-=1;setattr(p,attribute,getattr(p,attribute)+1);self._require_state().achievements["level_up"]=True;self._event("attribute_leveled",agent_id=p.agent_id,attribute=attribute)

    def _world_tick(self) -> None:
        state = self._require_state()
        state.light_level = max(0.1, (1.0 + __import__("math").cos(2 * __import__("math").pi * (state.timestep % DAY_LENGTH) / DAY_LENGTH)) / 2)
        for p in state.players:
            if not p.alive: continue
            if p.sleeping:
                p.energy = min(9, p.energy + 2)
                if p.energy >= 9: p.sleeping = False; state.achievements["wake_up"] = True
                continue
            p.energy = max(0, p.energy - 1)
            if state.timestep % 25 == 24: p.food = max(0, p.food - 1); p.drink = max(0, p.drink - 1)
            if p.food == 0 or p.drink == 0: p.health -= 1
            if p.level == NUM_LEVELS - 1 and state.boss_health > 0: p.health -= max(0, 2 - p.armour)
            if p.health <= 0: p.health = 0; p.alive = False; self._event("player_died", agent_id=p.agent_id)

    def _update_projectiles(self) -> None:
        state=self._require_state();remaining=[]
        for projectile in state.projectiles:
            projectile["x"]+=projectile["dx"];projectile["y"]+=projectile["dy"];projectile["ttl"]-=1
            if projectile["ttl"]<=0 or state.maps[projectile["level"]][projectile["y"]][projectile["x"]] in ("stone","wall","water"):continue
            mob=next((m for m in state.monsters if m["level"]==projectile["level"] and m["x"]==projectile["x"] and m["y"]==projectile["y"]),None)
            if mob:
                mob["health"]-=projectile["damage"]
                if mob["health"]<=0:state.monsters.remove(mob);state.achievements["defeat_monster"]=True
                continue
            remaining.append(projectile)
        state.projectiles=remaining

    def _update_monsters(self) -> None:
        state=self._require_state()
        for mob in list(state.monsters):
            targets=[p for p in state.players if p.alive and p.level==mob["level"]]
            if not targets:continue
            target=min(targets,key=lambda p:abs(p.x-mob["x"])+abs(p.y-mob["y"]));distance=abs(target.x-mob["x"])+abs(target.y-mob["y"])
            if distance<=1:
                damage=max(0,mob["damage"]-(target.armour+target.strength//2));target.health-=damage
                if damage:self._event("player_damaged",agent_id=target.agent_id,mob_id=mob["id"],damage=damage)
            elif distance<=8:
                dx=0 if target.x==mob["x"] else (1 if target.x>mob["x"] else -1);dy=0 if target.y==mob["y"] else (1 if target.y>mob["y"] else -1)
                if abs(target.x-mob["x"])>=abs(target.y-mob["y"]):dy=0
                else:dx=0
                nx,ny=mob["x"]+dx,mob["y"]+dy
                if state.maps[mob["level"]][ny][nx] not in ("stone","wall","water","lava") and not any(p.level==mob["level"] and p.x==nx and p.y==ny for p in state.players):mob["x"],mob["y"]=nx,ny

    def _update_plants(self) -> None:
        state=self._require_state()
        if state.timestep and state.timestep%50==0:
            for level in range(NUM_LEVELS):
                for y in range(MAP_SIZE):
                    for x in range(MAP_SIZE):
                        if state.maps[level][y][x]=="plant":state.maps[level][y][x]="ripe_plant"

    def _terminate(self, reason: str) -> None:
        state = self._require_state(); state.terminated = True; state.termination_reason = reason
        self._event("game_ended", outcome=reason)

    def observations(self) -> dict[str, dict[str, Any]]:
        state = self._require_state(); dashboard = [self._player_summary(p) for p in state.players]
        return {p.agent_id: {"agent_id":p.agent_id,"agent_index":i,"role":p.role,"legal_agent_ids":list(self.agent_ids),"legal_actions":self.legal_actions(p.agent_id),"self":self._player_summary(p),"teammate_dashboard":deepcopy(dashboard),"level":p.level,"map_size":[MAP_SIZE,MAP_SIZE],"num_levels":NUM_LEVELS,"local_view":self._local_view(p),"ascii":self.render_ascii(p.agent_id),"visible_monsters":[deepcopy(m) for m in state.monsters if m["level"]==p.level and abs(m["x"]-p.x)<=self.view_radius and abs(m["y"]-p.y)<=self.view_radius],"shared":{"timestep":state.timestep,"light_level":state.light_level,"boss_health":state.boss_health,"boss_progress":state.boss_progress,"trade_count":state.trade_count,"achievements":deepcopy(state.achievements)},"last_joint_event":deepcopy(state.last_joint_event)} for i,p in enumerate(state.players)}

    @staticmethod
    def _player_summary(p: Player) -> dict[str, Any]:
        return {"agent_id":p.agent_id,"role":p.role,"position":[p.x,p.y],"level":p.level,"health":p.health,"food":p.food,"drink":p.drink,"energy":p.energy,"mana":p.mana,"alive":p.alive,"sleeping":p.sleeping,"inventory":deepcopy(p.inventory),"equipment":{"pickaxe":p.pickaxe,"sword":p.sword,"armour":p.armour,"arrows":p.arrows,"torches":p.torches,"books":p.books,"saplings":p.saplings,"potions":deepcopy(p.potions),"enchantments":{"sword":p.sword_enchantment,"armour":p.armour_enchantment,"bow":p.bow_enchantment}},"attributes":{"dexterity":p.dexterity,"strength":p.strength,"intelligence":p.intelligence,"xp":p.xp,"level_points":p.level_points},"request":{"resource":p.request_type,"remaining":p.request_duration}}

    def _local_view(self, p: Player) -> list[list[dict[str, Any]]]:
        state=self._require_state(); out=[]
        for y in range(p.y-self.view_radius,p.y+self.view_radius+1):
            row=[]
            for x in range(p.x-self.view_radius,p.x+self.view_radius+1):
                terrain = "out_of_bounds" if not (0<=x<MAP_SIZE and 0<=y<MAP_SIZE) else state.maps[p.level][y][x]
                agents=[q.agent_id for q in state.players if q.alive and q.level==p.level and q.x==x and q.y==y]
                mobs=[m["id"] for m in state.monsters if m["level"]==p.level and m["x"]==x and m["y"]==y]
                row.append({"x":x,"y":y,"terrain":terrain,"agents":agents,"mobs":mobs})
            out.append(row)
        return out

    def render_ascii(self, agent_id: str) -> str:
        p=next(p for p in self._require_state().players if p.agent_id==agent_id); rows=[]
        for row in self._local_view(p):
            rows.append("".join((cell["agents"][0][-1] if cell["agents"] else "M" if cell["mobs"] else GLYPHS.get(cell["terrain"],"#")) for cell in row))
        return "\n".join(rows)

    def checkpoint(self) -> dict[str, Any]: return {"schema_version":"craftax-coop.checkpoint.v1","state":deepcopy(self._require_state().to_dict())}
    def restore(self, checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if checkpoint.get("schema_version") != "craftax-coop.checkpoint.v1": raise ValueError("unsupported checkpoint schema")
        self.state=WorldState.from_dict(deepcopy(checkpoint["state"])); self.agent_ids=tuple(p.agent_id for p in self.state.players); return self.observations()
    def state_hash(self) -> str: return hashlib.sha256(json.dumps(self._require_state().to_dict(),sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    def _require_state(self) -> WorldState:
        if self.state is None: raise RuntimeError("reset or restore required")
        return self.state
