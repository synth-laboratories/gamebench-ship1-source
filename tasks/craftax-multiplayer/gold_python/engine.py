from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .constants import ACHIEVEMENT_REWARDS, BASE_ACTIONS, BOSS_HEALTH, DAY_LENGTH, FLOOR_MOBS, GLYPHS, KILL_ACHIEVEMENTS, LEVEL_ACHIEVEMENTS, MAP_SIZE, MAX_TIMESTEPS, MOB_DAMAGE, MOB_HEALTH, NUM_LEVELS, POTION_COLOURS, PROJECTILE_KIND, REQUEST_ACTIONS, REQUEST_DURATION, RESOURCES, ROLES
from .state import AlemCoordState, CoordSite, Monster, Plant, Player, Projectile, WorldState


class CraftaxCoopEnv:
    """Deterministic, simultaneous, shared-reward Craftax-Coop model."""

    env_family = "craftax-multiplayer"

    def __init__(
        self,
        agent_count: int = 3,
        max_timesteps: int = MAX_TIMESTEPS,
        view_radius: int = 5,
        rules_profile: str | None = None,
        coordination: dict[str, Any] | None = None,
    ):
        if agent_count < 2:
            raise ValueError("Craftax-Coop requires at least two agents")
        if rules_profile not in (None, "alem_coord_v0"):
            raise ValueError(f"unsupported rules profile: {rules_profile}")
        if rules_profile == "alem_coord_v0" and agent_count != 3:
            raise ValueError("alem_coord_v0 requires exactly three agents")
        self.agent_ids = tuple(f"agent_{i}" for i in range(agent_count))
        self.max_timesteps = max_timesteps
        self.view_radius = view_radius
        self.rules_profile = rules_profile
        self.coordination = dict(coordination or {})
        self.state: WorldState | None = None

    @staticmethod
    def _generate_maps(seed: int) -> list[list[list[str]]]:
        maps = []
        floor_resources=((),("coal","iron"),("coal","iron"),("iron",),("diamond",),("diamond","ruby","sapphire"),("ruby",),("sapphire",),())
        biomes = (
            ("grass","water","stone","tree"), ("path","water","stone","stalagmite"),
            ("path","water","stone","stalagmite"), ("path","water","stone","stalagmite"),
            ("path","water","stone","stalagmite"), ("path","water","stone","stalagmite"),
            ("fire_grass","lava","stone","fire_tree"), ("ice_grass","water","stone","ice_shrub"),
            ("path","wall","wall","grave"),
        )
        for level in range(NUM_LEVELS):
            rng = (seed + 1) * 1_000_003 + level * 97
            base,liquid,mountain,vegetation=biomes[level]
            grid = [[base for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
            for i in range(MAP_SIZE):
                grid[0][i] = grid[-1][i] = grid[i][0] = grid[i][-1] = mountain
            for y in range(1, MAP_SIZE - 1):
                for x in range(1, MAP_SIZE - 1):
                    rng = (rng * 6_364_136_223_846_793_005 + 1) & ((1 << 64) - 1)
                    roll = ((rng >> 32) % 1000) / 1000
                    if roll < .055: grid[y][x] = liquid
                    elif roll < .11: grid[y][x] = mountain
                    elif roll < .15: grid[y][x] = vegetation
                    elif roll < .18:
                        choices=floor_resources[level];grid[y][x]=choices[((rng>>16)+level)%len(choices)] if choices else vegetation
                    elif roll < .19: grid[y][x] = "chest"
                    elif roll < .20 and level == 0: grid[y][x] = "plant"
            if level in (1,3,4):
                grid=[["wall" for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
                rooms=[]
                for row in range(2):
                    for column in range(4):
                        x0=2+column*11;y0=3+row*22;width=9;height=17;rooms.append((x0,y0,width,height))
                        for yy in range(y0,y0+height):
                            for xx in range(x0,x0+width):grid[yy][xx]="path"
                for left,right in zip(rooms[:3],rooms[1:4]):
                    y=left[1]+left[3]//2
                    for xx in range(left[0]+left[2],right[0]+1):grid[y][xx]="path"
                for left,right in zip(rooms[4:7],rooms[5:8]):
                    y=left[1]+left[3]//2
                    for xx in range(left[0]+left[2],right[0]+1):grid[y][xx]="path"
                for column in range(4):
                    x=rooms[column][0]+rooms[column][2]//2
                    for yy in range(rooms[column][1]+rooms[column][3],rooms[column+4][1]+1):grid[yy][x]="path"
                for index,(x0,y0,width,height) in enumerate(rooms):
                    cx,cy=x0+width//2,y0+height//2
                    if index%2==0:grid[cy][cx]="chest"
                    if level==3 and index in (1,6):grid[cy][cx]="fountain"
                    choices=floor_resources[level]
                    if choices:grid[y0+2][x0+2]=choices[index%len(choices)]
            if level < NUM_LEVELS - 1: grid[MAP_SIZE - 3][MAP_SIZE - 3] = "stairs_down"
            if level > 0: grid[2][2] = "stairs_up"
            if level == 6:grid[10][10]="enchantment_table_fire"
            if level == 7:grid[10][10]="enchantment_table_ice"
            if level == NUM_LEVELS - 1:
                grid[MAP_SIZE//2][MAP_SIZE//2]="necromancer"
                for offset,tile in zip(range(-3,4),("grave","grave2","grave3","grave","grave3","grave2","grave")):grid[MAP_SIZE//2+3][MAP_SIZE//2+offset]=tile
            maps.append(grid)
        return maps

    def _alem_state(self) -> AlemCoordState:
        scenario = str(self.coordination.get("scenario", "sync_2"))
        alpha = self.coordination.get("alpha", 0.3)
        try:
            alpha_milli = int(round(float(alpha) * 1000))
        except (TypeError, ValueError) as exc:
            raise ValueError("alem_coord_v0 alpha must be one of 0.3, 0.6, 0.9") from exc
        if alpha_milli not in (300, 600, 900):
            raise ValueError("alem_coord_v0 alpha must be one of 0.3, 0.6, 0.9")
        sites = {
            "sync_2": [CoordSite("sync_2_site", 0, "sync_2", 0, 4, 4, ["agent_0", "agent_1"], "warrior")],
            "sync_all": [CoordSite("sync_all_site", 1, "sync_all", 0, 4, 4, ["agent_0", "agent_1", "agent_2"], "warrior")],
            "handover": [CoordSite("handover_site", 2, "handover", 0, 4, 4, ["agent_2", "agent_1"], "miner", "forager", "iron", 2)],
        }
        if scenario not in sites:
            raise ValueError("alem_coord_v0 scenario must be sync_2, sync_all, or handover")
        return AlemCoordState(scenario=scenario, alpha_milli=alpha_milli, sites=sites[scenario])

    def _configure_alem_map(self, players: list[Player], maps: list[list[list[str]]], coord: AlemCoordState) -> None:
        positions = {
            "sync_2": ((4, 3, "down"), (3, 4, "right"), (5, 3, "down")),
            "sync_all": ((4, 3, "down"), (3, 4, "right"), (5, 4, "left")),
            "handover": ((5, 3, "down"), (3, 4, "right"), (4, 3, "down")),
        }[coord.scenario]
        for player, (x, y, facing) in zip(players, positions, strict=True):
            player.x, player.y, player.facing = x, y, facing
        maps[0][4][4] = "coord_site"
        if coord.scenario == "handover":
            players[2].inventory["iron"] = 1

    def reset(self, seed: int = 0) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        players = [Player(a, ROLES[i % len(ROLES)], 3 + i, 3) for i, a in enumerate(self.agent_ids)]
        maps = self._generate_maps(seed)
        ladders_up=[[[2+i,2] for i in range(len(players))] for _ in range(NUM_LEVELS)]
        ladders_down=[[[MAP_SIZE-3-i,MAP_SIZE-3] for i in range(len(players))] for _ in range(NUM_LEVELS)]
        for index in range(len(players)):
            maps[0][3][3 + index] = "grass"
        maps[0][5][5] = "fountain"
        monsters: list[Monster] = []
        items=[[[None for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)] for _ in range(NUM_LEVELS)]
        lights=[[[1.0 if level==0 else .15 if level in (6,7) else 0.0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)] for level in range(NUM_LEVELS)]
        for level in range(NUM_LEVELS):
            if level<NUM_LEVELS-1:
                for x,y in ladders_down[level]:maps[level][y][x]="stairs_down";items[level][y][x]="ladder_down"
            if level>0:
                for x,y in ladders_up[level]:maps[level][y][x]="stairs_up";items[level][y][x]="ladder_up"
            if level in (1,3,4):
                for x,y in ((8,11),(19,33),(30,11),(41,33)):
                    if maps[level][y][x]=="path":
                        items[level][y][x]="torch"
                        for yy in range(max(0,y-4),min(MAP_SIZE,y+5)):
                            for xx in range(max(0,x-4),min(MAP_SIZE,x+5)):lights[level][yy][xx]=max(lights[level][yy][xx],max(0,1-(abs(xx-x)+abs(yy-y))/6))
        effects = ["health", "harm", "mana", "drain_mana", "energy", "exhaustion"]
        effects.sort(key=lambda effect: self._mix64(seed + sum(map(ord, effect))))
        self.state = WorldState(seed, 0, self.max_timesteps, players, maps, monsters, item_maps=items, light_maps=lights, ladders_up=ladders_up, ladders_down=ladders_down, boss_health=BOSS_HEALTH, potion_mapping=effects, chests_opened=[[False] * len(players) for _ in range(NUM_LEVELS)], achievements_by_agent={p.agent_id:{name:False for name in ACHIEVEMENT_REWARDS} for p in players})
        self._event("game_started", task_id=self.env_family, seed=seed)
        if self.rules_profile == "alem_coord_v0":
            coord = self._alem_state()
            self._configure_alem_map(players, maps, coord)
            self.state.alem_coord = coord
            for site in coord.sites:
                self._event(
                    "coord_site_spawned",
                    alpha_milli=coord.alpha_milli,
                    participants=list(site.participants),
                    site_id=site.site_id,
                    site_kind=site.kind,
                    target=[site.level, site.x, site.y],
                )
        return self.observations(), {"seed": seed, "state_hash": self.state_hash()}

    @staticmethod
    def _spawn_initial_monsters(seed: int, maps: list[list[list[str]]]) -> list[Monster]:
        monsters = []
        for level in range(NUM_LEVELS - 1):
            for index in range(3 + level):
                value = ((seed + 17) * 1_103_515_245 + level * 7919 + index * 104729) & 0xFFFFFFFF
                x, y = 6 + value % 36, 6 + (value // 37) % 36
                if maps[level][y][x] in ("grass", "path", "sand", "gravel"):
                    category_index = index % 3
                    kind = FLOOR_MOBS[level][category_index]
                    if kind is None:
                        continue
                    health = MOB_HEALTH[level][category_index]
                    damage = sum(MOB_DAMAGE.get(kind, (0, 0, 0)))
                    category = ("passive", "melee", "ranged")[category_index]
                    monsters.append(Monster(f"mob_{level}_{index}", kind, level, x, y, health, damage, category))
        return monsters

    def _event(self, kind: str, **payload: Any) -> None:
        assert self.state is not None
        payload=dict(sorted(payload.items()));event = {"timestep": self.state.timestep, "kind": kind, **payload}
        self.state.nev.append(event)
        self.state.last_joint_event.append(event)
        args = ",".join(v if isinstance(v, str) else json.dumps(v, separators=(",", ":")) for v in payload.values())
        label = "".join(part.title() for part in kind.split("_"))
        self.state.legacy_nev.append(f"{label}({args})")

    def _award(self,name:str,*players:Player)->None:
        state=self._require_state()
        state.achievements[name]=True
        recipients=players or tuple(state.players)
        for player in recipients:state.achievements_by_agent[player.agent_id][name]=True

    def legal_actions(self, agent_id: str) -> list[str]:
        actions = list(BASE_ACTIONS + REQUEST_ACTIONS)
        actions.extend(f"give_{resource}_to_{other}" for resource in RESOURCES for other in self.agent_ids if other != agent_id)
        if self.rules_profile == "alem_coord_v0":
            actions.append("say")
        return actions

    def step(self, joint_action: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, float], dict[str, bool], dict[str, Any]]:
        state = self._require_state()
        if state.terminated: raise RuntimeError("step called after terminal state")
        if set(joint_action) != set(self.agent_ids): raise ValueError("joint_action must contain every agent exactly once")
        state.last_joint_event = []
        before={agent:{name for name,earned in flags.items() if earned} for agent,flags in state.achievements_by_agent.items()};before_health=sum(p.health for p in state.players)
        normalized = {a: self._normalize_action(joint_action[a]) for a in self.agent_ids}
        for agent_id, action in normalized.items():
            if action["kind"] not in self.legal_actions(agent_id):
                raise ValueError(f"illegal action for {agent_id}: {action['kind']}")
            if action["kind"] == "say":
                self._validate_message(agent_id, action)
        for agent_id in self.agent_ids:self._event("joint_action",agent_id=agent_id,action=normalized[agent_id]["kind"])
        for agent_id, action in normalized.items():
            if action["kind"] == "say":
                self._event("message", sender=agent_id, to=action["to"], code=action["code"], **({"site_id": action["site_id"]} if "site_id" in action else {}))
                self._award("coord_message", next(player for player in state.players if player.agent_id == agent_id))
        effective={agent_id:({"kind":"noop"} if not state.players[i].alive or state.players[i].sleeping or state.players[i].resting or normalized[agent_id]["kind"] == "say" else normalized[agent_id]) for i,agent_id in enumerate(self.agent_ids)}
        self._resolve_floor_actions(effective)
        coord_step_reward = self._resolve_coord_sites(effective)
        self._resolve_joint_do(effective)
        for i, agent_id in enumerate(self.agent_ids):
            if effective[agent_id]["kind"] not in ("do","attack"):self._apply_nonmovement(state.players[i], effective[agent_id])
        self._expire_requests()
        for i, agent_id in enumerate(self.agent_ids): self._apply_request(state.players[i], effective[agent_id])
        self._resolve_movement(effective)
        self._update_projectiles()
        self._update_monsters()
        self._spawn_mobs()
        self._update_boss()
        self._update_plants()
        self._world_tick()
        self._calculate_inventory_achievements()
        state.timestep += 1
        if all(p.alive for p in state.players):self._award("all_roles_alive")
        if not any(p.alive for p in state.players): self._terminate("death")
        elif state.boss_progress >= NUM_LEVELS - 1: self._terminate("boss")
        elif state.timestep >= state.max_timesteps: self._terminate("timestep")
        for player in state.players:
            player.health = float(player.health)
            player.recover = float(player.recover)
        for monster in state.monsters:
            monster.health = float(monster.health)
        base_reward=float(sum(ACHIEVEMENT_REWARDS.get(name,1) for agent,flags in state.achievements_by_agent.items() for name,earned in flags.items() if earned and name not in before[agent])+.1*(sum(p.health for p in state.players)-before_health))
        if state.alem_coord is not None:
            state.alem_coord.base_reward += base_reward
        reward = base_reward + coord_step_reward
        rewards = {a: reward for a in self.agent_ids}
        dones = {a: state.terminated for a in self.agent_ids} | {"__all__": state.terminated}
        info = {"events": deepcopy(state.last_joint_event), "state_hash": self.state_hash(), "termination_reason": state.termination_reason}
        if state.alem_coord is not None:
            info["metrics"] = self.alem_metrics()
        return self.observations(), rewards, dones, info

    def _resolve_joint_do(self,actions:dict[str,dict[str,Any]])->None:
        state=self._require_state();groups:dict[tuple[int,int,int],list[Player]]={};delta={"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}
        for player in state.players:
            if actions[player.agent_id]["kind"] in ("do","attack"):
                dx,dy=delta[player.facing];groups.setdefault((player.level,player.x+dx,player.y+dy),[]).append(player)
        for (level,x,y),players in groups.items():
            if len(players)==1:self._do(players[0]);continue
            tile=state.maps[level][y][x]
            target=next((p for p in state.players if p not in players and p.level==level and (p.x,p.y)==(x,y)),None)
            if target:
                if not target.alive:target.health=1;target.alive=True;state.revives+=1
                else:
                    damage=sum(self._player_attack_damage(p,target)*(3.5 if target.sleeping else 1) for p in players);target.health-=damage;state.ff_damage_dealt+=damage
                continue
            mob=next((m for m in state.monsters if m.level==level and (m.x,m.y)==(x,y)),None)
            if mob:
                mob.health-=sum(self._mob_attack_damage(p,mob) for p in players)
                if mob.health<=0:
                    state.monsters.remove(mob)
                    if mob.category!="passive":state.monsters_killed[level]+=1
                    for player in players:
                        if mob.category=="passive" and player.role=="forager":player.food=min(self._max_food(player),player.food+6);player.hunger=0
                        if mob.category!="passive" or player.role=="forager":
                            achievement=KILL_ACHIEVEMENTS.get(mob.kind)
                            if achievement:self._award(achievement,player)
                continue
            mapping={"tree":("wood",0,"grass"),"fire_tree":("wood",0,"fire_grass"),"ice_shrub":("wood",0,"ice_grass"),"stone":("stone",1,"path"),"stalagmite":("stone",1,"path"),"coal":("coal",1,"path"),"iron":("iron",2,"path"),"diamond":("diamond",3,"path"),"ruby":("ruby",4,"path"),"sapphire":("sapphire",4,"path")}
            if tile in mapping:
                resource,tier,replacement=mapping[tile]
                for player in players:
                    if player.pickaxe>=tier:player.inventory[resource]=min(99,player.inventory[resource]+1);self._award(f"collect_{resource}",player)
                state.maps[level][y][x]=replacement;continue
            if tile=="chest":
                for player in players:self._loot_chest(player);state.chests_opened[level][state.players.index(player)]=True;self._award("open_chest",player)
                state.maps[level][y][x]="path";continue
            if tile=="ripe_plant":
                for player in players:player.food=min(self._max_food(player),player.food+4);player.hunger=0;self._award("eat_plant",player)
                state.maps[level][y][x]="plant";continue
            for player in players:self._do(player)

    @staticmethod
    def _normalize_action(action: Any) -> dict[str, Any]:
        if isinstance(action, str): return {"kind": action}
        if not isinstance(action, dict) or not isinstance(action.get("kind"), str): raise ValueError("actions must be strings or objects with kind")
        return action

    def _validate_message(self, sender: str, action: dict[str, Any]) -> None:
        if self.rules_profile != "alem_coord_v0":
            raise ValueError("say is only available under alem_coord_v0")
        allowed = {"kind", "to", "code", "site_id"}
        if set(action).difference(allowed):
            raise ValueError("ALEM messages permit only kind, to, code, and optional site_id")
        if action.get("to") not in (*self.agent_ids, "all") or action.get("to") == sender:
            raise ValueError("ALEM message recipient must be another agent or all")
        if action.get("code") not in {"NEED_IRON", "MEET_AT", "ATTACK_MOB", "BUILD_HERE"}:
            raise ValueError("invalid ALEM message code")
        if "site_id" in action and not isinstance(action["site_id"], str):
            raise ValueError("ALEM message site_id must be a string")

    def _resolve_coord_sites(self, actions: dict[str, dict[str, Any]]) -> float:
        state = self._require_state()
        coord = state.alem_coord
        if coord is None:
            return 0.0
        reward = 0.0
        for site in coord.sites:
            if site.kind in ("sync_2", "sync_all") and site.status == "open":
                actors = [
                    player for player in state.players
                    if player.agent_id in site.participants
                    and actions[player.agent_id]["kind"] in ("do", "attack")
                    and self._front(player) == (site.level, site.x, site.y)
                ]
                if actors:
                    if {player.agent_id for player in actors} != set(site.participants):
                        reward += self._resolve_coord_site(site, False, "coord_sync_fail", reason="missing_participant")
                    elif all([self._soft_role_allowed(site, player, site.required_role) for player in actors]):
                        reward += self._resolve_coord_site(site, True, "coord_sync_success")
                    else:
                        reward += self._resolve_coord_site(site, False, "coord_sync_fail", reason="soft_role_denied")
            elif site.kind == "handover":
                provider = next(player for player in state.players if player.agent_id == site.participants[0])
                receiver = next(player for player in state.players if player.agent_id == site.participants[1])
                provider_acts = actions[provider.agent_id]["kind"] in ("do", "attack") and self._front(provider) == (site.level, site.x, site.y)
                receiver_acts = actions[receiver.agent_id]["kind"] in ("do", "attack") and self._front(receiver) == (site.level, site.x, site.y)
                if site.status == "open" and provider_acts and self._soft_role_allowed(site, provider, site.required_role):
                    assert site.resource is not None
                    if provider.inventory[site.resource] > 0:
                        provider.inventory[site.resource] -= 1
                        site.status, site.opened_at = "opened", state.timestep
                        self._award("coord_handover_offer", provider)
                        self._event("handover_opened", giver=provider.agent_id, receiver=receiver.agent_id, resource=site.resource, site_id=site.site_id, window=site.window)
                if site.status == "opened" and receiver_acts and self._soft_role_allowed(site, receiver, site.receiver_role):
                    assert site.resource is not None
                    receiver.inventory[site.resource] = min(99, receiver.inventory[site.resource] + 1)
                    reward += self._resolve_coord_site(site, True, "handover_completed", giver=provider.agent_id, receiver=receiver.agent_id, resource=site.resource)
                elif site.status == "opened" and site.opened_at is not None and state.timestep - site.opened_at >= site.window:
                    reward += self._resolve_coord_site(site, False, "handover_expired", giver=provider.agent_id, receiver=receiver.agent_id, resource=site.resource)
        return reward

    @staticmethod
    def _front(player: Player) -> tuple[int, int, int]:
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[player.facing]
        return player.level, player.x + dx, player.y + dy

    def _soft_role_allowed(self, site: CoordSite, player: Player, required_role: str | None) -> bool:
        if required_role is None:
            return True
        state = self._require_state()
        player_index = state.players.index(player)
        roll = self._mix64(state.seed ^ state.timestep ^ (site.site_index << 16) ^ player_index) % 10_000
        success = player.role == required_role or roll < 10_000 - state.alem_coord.alpha_milli * 10
        self._event("soft_role_roll", agent_id=player.agent_id, alpha_milli=state.alem_coord.alpha_milli, required_role=required_role, roll=roll, site_id=site.site_id, success=success)
        if success and player.role != required_role:
            self._award("coord_soft_role", player)
        return success

    def _resolve_coord_site(self, site: CoordSite, success: bool, event_kind: str, **payload: Any) -> float:
        state = self._require_state()
        assert state.alem_coord is not None
        site.status = "completed" if success else "failed"
        metrics = state.alem_coord.site_metrics[site.kind]
        metrics["resolved"] += 1
        if success:
            metrics["success"] += 1
        event_payload = {"site_id": site.site_id, "site_kind": site.kind, "success": success, **payload}
        self._event(event_kind, **event_payload)
        if not success:
            return 0.0
        achievement = {"sync_2": "coord_sync_2", "sync_all": "coord_sync_all", "handover": "coord_handover"}[site.kind]
        self._award(achievement, *self._require_state().players)
        reward = {"sync_2": 2.0, "sync_all": 3.0, "handover": 2.0}[site.kind]
        state.alem_coord.coord_reward += reward
        return reward

    def alem_metrics(self) -> dict[str, Any]:
        coord = self._require_state().alem_coord
        if coord is None:
            return {}
        return {
            "base_reward": coord.base_reward,
            "coord_reward": coord.coord_reward,
            "coord_success_rate": {
                kind: {**values, "rate": values["success"] / values["resolved"] if values["resolved"] else 0.0}
                for kind, values in coord.site_metrics.items()
            },
        }

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
                if state.maps[p.level][ny][nx] in ("grass", "path", "sand", "gravel", "fire_grass", "ice_grass", "stairs_down", "stairs_up", "crafting_table", "furnace", "enchantment_table_fire", "enchantment_table_ice"): desired[p.agent_id] = (nx, ny)
        counts = {pos: list(desired.values()).count(pos) for pos in desired.values()}
        for p in state.players:
            pos = desired.get(p.agent_id)
            occupied = any(
                other.level == p.level and (other.x, other.y) == pos
                for other in state.players
            ) or any(
                monster.level == p.level and (monster.x, monster.y) == pos
                for monster in state.monsters
            )
            if pos and counts[pos] == 1 and not occupied:
                p.x, p.y = pos; self._event("move_applied", agent_id=p.agent_id, x=p.x, y=p.y, level=p.level)

    def _apply_nonmovement(self, p: Player, action: dict[str, Any]) -> None:
        if not p.alive: return
        kind = action["kind"]
        if kind.startswith("give_"): self._give(p, kind)
        elif kind in ("do", "attack"): self._do(p)
        elif kind in ("descend","ascend"): pass
        elif kind == "rest": p.resting = p.health < self._max_health(p)
        elif kind == "sleep": p.sleeping = p.energy < self._max_energy(p)
        elif kind == "shoot_arrow": self._shoot_arrow(p)
        elif kind == "cast_spell": self._cast_spell(p)
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
            cap = self._max_food(target) if resource == "food" else self._max_drink(target)
            if stock <= 0 or getattr(target, resource) >= cap: return
            setattr(giver, resource, stock - 1); setattr(target, resource, min(cap, getattr(target, resource) + 1))
            if resource=="food":target.hunger=0
            else:target.thirst=0
        else:
            if giver.inventory[resource] <= 0 or target.inventory[resource] >= 99: return
            giver.inventory[resource] -= 1; target.inventory[resource] += 1
        state = self._require_state(); state.trade_count += 1; self._award("trade",giver,target)
        if resource == "food": state.food_trade_count += 1
        if resource == "drink": state.drink_trade_count += 1
        if resource=="food":self._award("collect_food",target)
        if resource=="drink":self._award("collect_drink",target)
        self._event("trade_applied", giver=giver.agent_id, receiver=target.agent_id, resource=resource)

    def _do(self, p: Player) -> None:
        state = self._require_state(); dx, dy = {"left": (-1,0), "right": (1,0), "up": (0,-1), "down": (0,1)}[p.facing]
        x, y = p.x + dx, p.y + dy; tile = state.maps[p.level][y][x]
        mapping = {"tree":("wood","grass"),"fire_tree":("wood","fire_grass"),"ice_shrub":("wood","ice_grass"),"stone":("stone","path"),"stalagmite":("stone","path"),"coal":("coal","path"),"iron":("iron","path"),"diamond":("diamond","path"),"ruby":("ruby","path"),"sapphire":("sapphire","path")}
        teammate = next((other for other in state.players if other is not p and other.level == p.level and other.x == x and other.y == y), None)
        if teammate is not None:
            if not teammate.alive:
                teammate.health = 1; teammate.alive = True; state.revives += 1
                self._event("player_revived", agent_id=teammate.agent_id, by=p.agent_id)
            else:
                damage = self._player_attack_damage(p,teammate)*(3.5 if teammate.sleeping else 1)
                teammate.health -= damage; state.ff_damage_dealt += damage
                self._event("friendly_fire", attacker=p.agent_id, target=teammate.agent_id, damage=damage)
            return
        if tile in mapping:
            resource,replacement = mapping[tile]
            required_pickaxe = {"stone": 1, "coal": 1, "iron": 2, "diamond": 3, "ruby": 4, "sapphire": 4}.get(resource, 0)
            if p.pickaxe < required_pickaxe: return
            amount = 1
            p.inventory[resource] = min(99,p.inventory[resource]+amount); state.maps[p.level][y][x] = replacement
            key = f"collect_{resource}"; self._award(key,p)
            self._event("resource_collected", agent_id=p.agent_id, resource=resource, amount=amount)
        elif tile in ("crafting_table","furnace"):
            state.maps[p.level][y][x]="path"
        elif tile == "grass" and p.role == "forager" and self._mix64(state.seed ^ state.timestep ^ state.players.index(p)) % 5 == 0:
            p.saplings += 1; self._award("collect_sapling",p)
        elif tile == "ripe_plant":
            p.food = min(self._max_food(p), p.food + 4); p.hunger=0; state.maps[p.level][y][x] = "plant"
            for plant in state.plants:
                if (plant.level,plant.x,plant.y)==(p.level,x,y):plant.age=0;break
            self._award("eat_plant",p); self._event("plant_eaten", agent_id=p.agent_id)
        elif tile == "fountain":
            if p.role != "forager": return
            p.drink = min(self._max_drink(p), p.drink + 4); self._event("fountain_used", agent_id=p.agent_id)
            self._award("collect_drink",p)
        elif tile == "water":
            if p.role != "forager": return
            p.drink = min(self._max_drink(p), p.drink + 4)
            self._award("collect_drink",p); self._event("water_drunk", agent_id=p.agent_id)
        elif tile == "chest":
            state.maps[p.level][y][x] = "path"; self._loot_chest(p)
            state.chests_opened[p.level][state.players.index(p)] = True
            self._award("open_chest",p); self._event("chest_opened", agent_id=p.agent_id)
        else:
            mob = next((m for m in state.monsters if m.level == p.level and m.x == x and m.y == y), None)
            if mob:
                damage = self._mob_attack_damage(p,mob)
                mob.health -= damage; self._event("mob_damaged", agent_id=p.agent_id, mob_id=mob.id, damage=damage)
                if mob.health <= 0:
                    state.monsters.remove(mob)
                    if mob.category != "passive":state.monsters_killed[p.level] += 1
                    if mob.category == "passive" and p.role == "forager":
                        p.food=min(self._max_food(p),p.food+6);p.hunger=0
                        achievement=KILL_ACHIEVEMENTS.get(mob.kind)
                        if achievement:self._award(achievement,p)
                    elif mob.category != "passive":
                        achievement=KILL_ACHIEVEMENTS.get(mob.kind)
                        if achievement:self._award(achievement,p)
                    self._event("mob_defeated", agent_id=p.agent_id, mob_id=mob.id)
        if tile in ("boss","necromancer","necromancer_vulnerable") and p.level == NUM_LEVELS - 1 and state.boss_wave_timer <= 0 and not any(m.level==p.level for m in state.monsters):
            state.boss_progress+=1;state.boss_health=max(0,NUM_LEVELS-1-state.boss_progress);state.boss_wave_timer=7
            state.maps[p.level][y][x]="necromancer";self._award("damage_necromancer",p)
            self._event("boss_damaged",agent_id=p.agent_id,damage=1,remaining=state.boss_health)
            if state.boss_progress>=NUM_LEVELS-1:self._award("defeat_necromancer",p)

    def _change_level(self, p: Player, direction: int) -> None:
        state=self._require_state();tile = state.maps[p.level][p.y][p.x]
        required = "stairs_down" if direction > 0 else "stairs_up"
        if tile != required or not 0 <= p.level + direction < NUM_LEVELS or (direction > 0 and state.monsters_killed[p.level] < 8): return
        next_level=p.level+direction;first_entry=direction>0 and LEVEL_ACHIEVEMENTS[next_level] and not state.achievements[LEVEL_ACHIEVEMENTS[next_level]]
        destinations=state.ladders_down[next_level] if direction<0 else state.ladders_up[next_level]
        for index,player in enumerate(state.players):
            player.level=next_level;player.x,player.y=destinations[index]
            if first_entry:player.xp+=1
        achievement=LEVEL_ACHIEVEMENTS[next_level]
        if direction>0 and achievement:self._award(achievement,*state.players)
        self._event("level_changed", agent_id=p.agent_id, level=next_level)

    def _resolve_floor_actions(self,actions:dict[str,dict[str,Any]])->None:
        for p in self._require_state().players:
            if actions[p.agent_id]["kind"]=="descend":self._change_level(p,1);return
        for p in self._require_state().players:
            if actions[p.agent_id]["kind"]=="ascend":self._change_level(p,-1);return

    def _craft(self, p: Player, kind: str) -> None:
        near_table=self._near(p,"crafting_table");near_furnace=self._near(p,"furnace")
        specs={
            "make_wood_pickaxe":({"wood":1},"pickaxe",1,"miner",False),
            "make_stone_pickaxe":({"wood":1,"stone":1},"pickaxe",2,"miner",False),
            "make_iron_pickaxe":({"wood":1,"stone":1,"iron":1,"coal":1},"pickaxe",3,"miner",True),
            "make_diamond_pickaxe":({"wood":1,"diamond":3},"pickaxe",4,"miner",False),
            "make_wood_sword":({"wood":1},"sword",1,None,False),
            "make_stone_sword":({"wood":1,"stone":1},"sword",2,"warrior",False),
            "make_iron_sword":({"wood":1,"stone":1,"iron":1,"coal":1},"sword",3,"warrior",True),
            "make_diamond_sword":({"wood":1,"diamond":2},"sword",4,"warrior",False),
        }
        if kind=="make_arrow":
            if p.role!="warrior" or not near_table or p.inventory["wood"]<1 or p.inventory["stone"]<1:return
            p.inventory["wood"]-=1;p.inventory["stone"]-=1;p.arrows+=2
        elif kind=="make_torch":
            if p.role!="miner" or not near_table or p.inventory["wood"]<1 or p.inventory["coal"]<1:return
            p.inventory["wood"]-=1;p.inventory["coal"]-=1;p.torches+=4
        elif kind in ("make_iron_armour","make_diamond_armour"):
            tier=1 if kind=="make_iron_armour" else 2;cost={"iron":3,"coal":3} if tier==1 else {"diamond":3}
            if not near_table or (tier==1 and not near_furnace) or not any(slot<tier for slot in p.armour_slots) or any(p.inventory[r]<n for r,n in cost.items()):return
            for resource,amount in cost.items():p.inventory[resource]-=amount
            slot=next(i for i,value in enumerate(p.armour_slots) if value<tier);p.armour_slots[slot]=tier;p.armour=max(p.armour_slots)
        else:
            spec=specs.get(kind)
            if not spec:return
            cost,item,tier,role,needs_furnace=spec
            if not near_table or (needs_furnace and not near_furnace) or (role and p.role!=role) or getattr(p,item)>=tier or any(p.inventory[r]<n for r,n in cost.items()):return
            for resource,amount in cost.items():p.inventory[resource]-=amount
            setattr(p,item,tier)
        if kind in self._require_state().achievements:self._award(kind,p)
        self._event("item_crafted",agent_id=p.agent_id,item=kind.removeprefix("make_"))

    def _near(self,p:Player,tile:str)->bool:
        state=self._require_state()
        return any(0<=p.x+dx<MAP_SIZE and 0<=p.y+dy<MAP_SIZE and state.maps[p.level][p.y+dy][p.x+dx]==tile for dx in (-1,0,1) for dy in (-1,0,1) if (dx,dy)!=(0,0))

    def _place(self, p: Player, kind: str) -> None:
        state = self._require_state(); dx, dy = {"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}[p.facing]; x,y=p.x+dx,p.y+dy
        recipes = {"place_stone":("stone",1,"stone"),"place_table":("wood",2,"crafting_table"),"place_furnace":("stone",1,"furnace"),"place_plant":("saplings",1,"plant"),"place_torch":("torches",1,state.maps[p.level][y][x])}
        recipe=recipes.get(kind)
        valid=("grass","path","sand","gravel","fire_grass","ice_grass")
        if kind=="place_stone":valid+= ("water",)
        if kind=="place_plant":valid=("grass",)
        if not recipe or state.maps[p.level][y][x] not in valid or state.item_maps[p.level][y][x] is not None or any(q.alive and q.level==p.level and q.x==x and q.y==y for q in state.players) or any(m.level==p.level and m.x==x and m.y==y for m in state.monsters) or (kind=="place_stone" and p.role!="miner"): return
        resource,cost,tile=recipe; stock=p.saplings if resource=="saplings" else p.torches if resource=="torches" else p.inventory[resource]
        if stock<cost:return
        if resource=="saplings":
            p.saplings-=cost
            state.plants.append(Plant(p.level,x,y,0))
        elif resource=="torches":p.torches-=cost
        else:p.inventory[resource]-=cost
        state.maps[p.level][y][x]=tile
        if kind=="place_torch":
            state.item_maps[p.level][y][x]="torch"
            for yy in range(max(0,y-4),min(MAP_SIZE,y+5)):
                for xx in range(max(0,x-4),min(MAP_SIZE,x+5)):state.light_maps[p.level][yy][xx]=max(state.light_maps[p.level][yy][xx],max(0,1-(abs(xx-x)+abs(yy-y))/6))
        if kind in state.achievements:self._award(kind,p)
        self._event("block_placed",agent_id=p.agent_id,tile=tile,x=x,y=y)

    def _shoot_arrow(self,p:Player)->None:
        if p.arrows<=0 or p.bow<=0 or sum(not projectile.hostile for projectile in self._require_state().projectiles)>=len(self.agent_ids)*3:return
        p.arrows-=1; dx,dy={"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}[p.facing]
        self._require_state().projectiles.append(Projectile(p.agent_id, p.level, p.x, p.y, dx, dy, 5+p.dexterity, MAP_SIZE, "arrow2", False))
        self._award("fire_bow",p);self._event("arrow_shot",agent_id=p.agent_id)

    def _drink_potion(self,p:Player,colour:str)->None:
        if colour not in p.potions or p.potions[colour]<=0:return
        p.potions[colour]-=1
        effect=self._require_state().potion_mapping[POTION_COLOURS.index(colour)]
        if effect=="health":p.health=min(self._max_health(p),p.health+8)
        elif effect=="harm":p.health-=3
        elif effect=="mana":p.mana=min(self._max_mana(p),p.mana+8)
        elif effect=="drain_mana":p.mana=max(0,p.mana-3)
        elif effect=="energy":p.energy=min(9,p.energy+8)
        else:p.energy=max(0,p.energy-3)
        self._award("drink_potion",p);self._event("potion_drunk",agent_id=p.agent_id,colour=colour)

    def _read_book(self,p:Player)->None:
        if p.books<=0:return
        p.books-=1;p.learned_spell=True
        self._award("learn_spell",p);self._event("book_read",agent_id=p.agent_id)

    def _enchant(self,p:Player,item:str)->None:
        state=self._require_state();dx,dy={"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}[p.facing];table=state.maps[p.level][p.y+dy][p.x+dx]
        if table not in ("enchantment_table_fire","enchantment_table_ice") or p.mana<9 or item not in ("sword","armour","bow"):return
        element="fire" if table.endswith("fire") else "ice";gem="ruby" if element=="fire" else "sapphire"
        if p.inventory[gem]<1 or (item in ("sword","bow") and p.role!="warrior") or getattr(p,item)<=0:return
        p.inventory[gem]-=1;p.mana-=9
        if item=="armour":
            candidates=[i for i,value in enumerate(p.armour_enchantments) if value is None] or [i for i,value in enumerate(p.armour_enchantments) if value!=element]
            if not candidates:return
            p.armour_enchantments[candidates[0]]=element;p.armour_enchantment=element
        else:setattr(p,f"{item}_enchantment",element)
        key="enchant_sword" if item=="sword" else "enchant_armour" if item=="armour" else None
        if key:self._award(key,p)
        self._event("item_enchanted",agent_id=p.agent_id,item=item,element=element)

    def _level_up(self,p:Player,attribute:str)->None:
        if p.xp<=0 or attribute not in ("dexterity","strength","intelligence") or getattr(p,attribute)>=5:return
        p.xp-=1;setattr(p,attribute,getattr(p,attribute)+1);self._award("level_up",p);self._event("attribute_leveled",agent_id=p.agent_id,attribute=attribute)

    @staticmethod
    def _melee_damage(player: Player, armour: int) -> int:
        base = (1, 2, 3, 5, 8)[player.sword] * (2 if player.role == "warrior" else 1)
        coefficient = 1 + 0.25 * (player.strength - 1)
        return max(0, round(base * coefficient) - armour)

    def _player_damage_vector(self,player:Player)->tuple[float,float,float]:
        base=(1,2,3,5,8)[player.sword]*(2 if player.role=="warrior" else 1)
        physical=base*(1+.25*(player.strength-1));element=base*.5*(1+.05*(player.intelligence-1))
        return physical,element if player.sword_enchantment=="fire" else 0,element if player.sword_enchantment=="ice" else 0
    @staticmethod
    def _defense_vector(player:Player)->tuple[float,float,float]:
        return sum(player.armour_slots)*.1,sum(value=="fire" for value in player.armour_enchantments)*.2,sum(value=="ice" for value in player.armour_enchantments)*.2
    def _player_attack_damage(self,attacker:Player,target:Player)->float:
        return sum((1-defense)*damage for damage,defense in zip(self._player_damage_vector(attacker),self._defense_vector(target)))
    def _mob_attack_damage(self,player:Player,mob:Monster)->int:
        return self._vector_damage_to_mob(self._player_damage_vector(player),mob)
    @staticmethod
    def _vector_damage_to_mob(vector:tuple[float,float,float],mob:Monster)->float:
        physical=0
        if mob.level==4:physical=.5
        elif mob.level==5 and mob.category=="melee":physical=.2
        elif mob.level in (6,7):physical=.9
        defenses=(physical,1.0 if mob.level==6 else 0,1.0 if mob.level==7 else 0)
        return max(0,sum((1-defense)*damage for damage,defense in zip(vector,defenses)))
    def _incoming_damage(self,vector:tuple[int,int,int],target:Player,boss:bool=False)->float:
        amount=sum((1-defense)*damage for damage,defense in zip(vector,self._defense_vector(target)))
        return max(0,amount*(1.5 if boss else 1))
    @staticmethod
    def _projectile_vector(kind:str)->tuple[int,int,int]:
        return {"arrow":(2,0,0),"dagger":(4,0,0),"fireball":(0,3,0),"iceball":(0,0,3),"arrow2":(5,0,0),"slimeball":(4,3,3),"fireball2":(3,5,0),"iceball2":(4,0,5)}.get(kind,(1,0,0))
    def _player_projectile_vector(self,projectile:Projectile)->tuple[float,float,float]:
        owner=next((p for p in self._require_state().players if p.agent_id==projectile.owner),None)
        if owner is None:return self._projectile_vector(projectile.kind)
        if projectile.kind=="arrow2":
            physical=5*(1+.2*(owner.dexterity-1));element=2.5
            return physical,element if owner.bow_enchantment=="fire" else 0,element if owner.bow_enchantment=="ice" else 0
        if projectile.kind=="fireball":return 0,3*(1+.5*(owner.intelligence-1)),0
        return self._projectile_vector(projectile.kind)

    @staticmethod
    def _max_health(player: Player) -> int: return 8 + player.strength
    @staticmethod
    def _max_food(player: Player) -> int: return (7 + 2 * player.dexterity) * (3 if player.role == "forager" else 1)
    @staticmethod
    def _max_drink(player: Player) -> int: return (7 + 2 * player.dexterity) * (3 if player.role == "forager" else 1)
    @staticmethod
    def _max_energy(player: Player) -> int: return 7 + 2 * player.dexterity
    @staticmethod
    def _max_mana(player: Player) -> int: return 6 + 3 * player.intelligence

    def _loot_chest(self, player: Player) -> None:
        state = self._require_state()
        value = self._mix64(state.seed ^ (state.timestep << 17) ^ (player.level << 9) ^ sum(map(ord, player.agent_id)))
        if player.role == "miner" and value % 10 < 6:
            player.inventory["wood"] += 1 + value % 5
            player.torches += 4 + (value // 7) % 4
            ore = ("coal", "iron", "diamond", "sapphire", "ruby")[(value // 11) % 5]
            player.inventory[ore] += 1 + (value // 13) % (3 if ore == "coal" else 2)
            player.pickaxe = max(player.pickaxe, 1 + (value // 17) % 4)
        colour = POTION_COLOURS[(value // 19) % 6]
        if (value // 23) % 2 == 0:
            player.potions[colour] += 1 + (value // 29) % 2
        player_index=state.players.index(player);opened=state.chests_opened[player.level][player_index]
        if player.role == "warrior":
            if (value // 31) % 2 == 0: player.arrows += 4 + (value // 37) % 5
            if player.level == 1 and not opened:
                player.bow = max(1, player.bow); self._award("find_bow",player)
        if player.level in (3, 4) and not opened:
            player.books += 1

    @staticmethod
    def _mix64(value: int) -> int:
        value = (value + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & ((1 << 64) - 1)
        return value ^ (value >> 31)

    def _cast_spell(self, player: Player) -> None:
        if not player.learned_spell:
            return
        state = self._require_state()
        if player.role == "forager" and player.mana >= 6:
            player.mana -= 6
            for ally in state.players:
                if ally.alive: ally.health = min(self._max_health(ally), ally.health + 2)
            self._award("cast_spell",player)
            self._event("spell_cast", agent_id=player.agent_id, spell="heal")
        elif player.role in ("warrior", "miner") and player.mana >= 2:
            player.mana -= 2
            dx,dy={"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}[player.facing]
            damage = max(1, round(3 * (1 + .5 * (player.intelligence - 1))))
            if sum(not projectile.hostile for projectile in state.projectiles)<len(self.agent_ids)*3:state.projectiles.append(Projectile(player.agent_id, player.level, player.x, player.y, dx, dy, damage, MAP_SIZE, "fireball", False))
            self._award("cast_spell",player)
            self._event("spell_cast", agent_id=player.agent_id, spell="fireball")

    def _world_tick(self) -> None:
        state = self._require_state()
        state.light_level = round(max(0.1, (1.0 + __import__("math").cos(2 * __import__("math").pi * (state.timestep % DAY_LENGTH) / DAY_LENGTH)) / 2), 14)
        for p in state.players:
            if not p.alive: continue
            decay = 1.0 - .125 * (p.dexterity - 1)
            p.hunger += (.5 if p.sleeping else 1.0) * decay
            p.thirst += (.5 if p.sleeping else 1.0) * decay
            if p.hunger > 25: p.food = max(0, p.food - (0 if p.level==NUM_LEVELS-1 else 1)); p.hunger = 0
            if p.thirst > 20: p.drink = max(0, p.drink - (0 if p.level==NUM_LEVELS-1 else 1)); p.thirst = 0
            p.fatigue += -1 if p.sleeping else decay
            if p.fatigue > 30: p.energy = max(0, p.energy - 1); p.fatigue = 0
            if p.fatigue < -10: p.energy = min(self._max_energy(p), p.energy + 1); p.fatigue = 0
            necessities = p.food > 0 and p.drink > 0 and (p.energy > 0 or p.sleeping)
            p.recover += (2 if p.sleeping else 1) if necessities else (-.5 if p.sleeping else -1)
            if p.recover > 25: p.health = min(self._max_health(p), p.health + 2); p.recover = 0
            if p.recover < -15: p.health -= 0 if p.level==NUM_LEVELS-1 else 1; p.recover = 0
            p.recover_mana = (p.recover_mana + (2 if p.sleeping else 1)) * (1 + .25 * (p.intelligence - 1))
            if p.recover_mana > 30: p.mana = min(self._max_mana(p), p.mana + 1); p.recover_mana = 0
            if p.sleeping and p.energy >= self._max_energy(p): p.sleeping = False; self._award("wake_up",p)
            if p.resting and (p.health >= self._max_health(p) or p.food <= 0 or p.drink <= 0): p.resting = False
            if p.health <= 0: p.health = 0; p.alive = False; self._event("player_died", agent_id=p.agent_id)

    def _update_projectiles(self) -> None:
        state=self._require_state();remaining=[]
        for projectile in state.projectiles:
            projectile.x+=projectile.dx;projectile.y+=projectile.dy;projectile.ttl-=1
            if projectile.ttl<=0 or not (0<=projectile.x<MAP_SIZE and 0<=projectile.y<MAP_SIZE):continue
            tile=state.maps[projectile.level][projectile.y][projectile.x]
            if tile in ("crafting_table","furnace") and projectile.hostile:state.maps[projectile.level][projectile.y][projectile.x]="path";continue
            if tile in ("stone","wall","water","tree","coal","iron","diamond","ruby","sapphire","stalagmite","fire_tree","ice_shrub"):continue
            if projectile.hostile:
                target=next((p for p in state.players if p.alive and p.level==projectile.level and p.x==projectile.x and p.y==projectile.y),None)
                if target:
                    target.health-=self._incoming_damage(self._projectile_vector(projectile.kind),target,target.level==NUM_LEVELS-1);target.sleeping=False;target.resting=False
                    continue
            else:
                target=next((p for p in state.players if p.agent_id!=projectile.owner and p.alive and p.level==projectile.level and p.x==projectile.x and p.y==projectile.y),None)
                if target:
                    damage=self._incoming_damage(self._player_projectile_vector(projectile),target);target.health-=damage;state.ff_damage_dealt+=damage
                    continue
            mob=next((m for m in state.monsters if not projectile.hostile and m.level==projectile.level and m.x==projectile.x and m.y==projectile.y),None)
            if mob:
                mob.health-=self._vector_damage_to_mob(self._player_projectile_vector(projectile),mob)
                if mob.health<=0:
                    state.monsters.remove(mob)
                    if mob.category!="passive":state.monsters_killed[mob.level]+=1
                    achievement=KILL_ACHIEVEMENTS.get(mob.kind)
                    owner=next((p for p in state.players if p.agent_id==projectile.owner),None)
                    if achievement and owner:self._award(achievement,owner)
                continue
            remaining.append(projectile)
        state.projectiles=remaining

    def _update_monsters(self) -> None:
        state=self._require_state()
        for mob in list(state.monsters):
            targets=[p for p in state.players if p.alive and p.level==mob.level]
            if not targets:continue
            target=min(targets,key=lambda p:abs(p.x-mob.x)+abs(p.y-mob.y));distance=abs(target.x-mob.x)+abs(target.y-mob.y)
            if mob.category=="passive":
                dx=0 if target.x==mob.x else (-1 if target.x>mob.x else 1);dy=0 if target.y==mob.y else (-1 if target.y>mob.y else 1)
                if abs(target.x-mob.x)>=abs(target.y-mob.y):dy=0
                else:dx=0
                self._move_mob(mob,dx,dy)
            elif mob.category=="ranged" and distance<=6 and mob.attack_cooldown<=0 and sum(projectile.hostile for projectile in state.projectiles)<len(self.agent_ids)*3:
                dx=0 if target.x==mob.x else (1 if target.x>mob.x else -1);dy=0 if target.y==mob.y else (1 if target.y>mob.y else -1)
                if abs(target.x-mob.x)>=abs(target.y-mob.y):dy=0
                else:dx=0
                kind=PROJECTILE_KIND[mob.kind];damage=sum(MOB_DAMAGE.get(mob.kind,(1,0,0)))
                state.projectiles.append(Projectile(mob.id,mob.level,mob.x,mob.y,dx,dy,damage,MAP_SIZE,kind,True));mob.attack_cooldown=5
            elif mob.category=="ranged":
                toward_x=0 if target.x==mob.x else (1 if target.x>mob.x else -1);toward_y=0 if target.y==mob.y else (1 if target.y>mob.y else -1)
                if abs(target.x-mob.x)>=abs(target.y-mob.y):toward_y=0
                else:toward_x=0
                if distance<=3:self._move_mob(mob,-toward_x,-toward_y)
                elif distance>=6:self._move_mob(mob,toward_x,toward_y)
                else:
                    directions=((-1,0),(1,0),(0,-1),(0,1));self._move_mob(mob,*directions[self._mix64(state.seed^state.timestep^sum(map(ord,mob.id)))%4])
            elif distance<=1 and mob.attack_cooldown<=0:
                was_sleeping=target.sleeping;damage=self._incoming_damage(MOB_DAMAGE.get(mob.kind,(mob.damage,0,0)),target,target.level==NUM_LEVELS-1)*(3.5 if was_sleeping else 1);target.health-=damage
                target.sleeping=False;target.resting=False
                if was_sleeping:self._award("wake_up",target)
                mob.attack_cooldown=5
                if damage:self._event("player_damaged",agent_id=target.agent_id,mob_id=mob.id,damage=damage)
            elif distance<=8:
                dx=0 if target.x==mob.x else (1 if target.x>mob.x else -1);dy=0 if target.y==mob.y else (1 if target.y>mob.y else -1)
                if abs(target.x-mob.x)>=abs(target.y-mob.y):dy=0
                else:dx=0
                self._move_mob(mob,dx,dy)
            mob.attack_cooldown=max(0,mob.attack_cooldown-1)

    def _move_mob(self,mob:Monster,dx:int,dy:int)->None:
        state=self._require_state();nx,ny=mob.x+dx,mob.y+dy
        if not (0<=nx<MAP_SIZE and 0<=ny<MAP_SIZE):return
        tile=state.maps[mob.level][ny][nx];flying=mob.kind in ("bat","fire_elemental","ice_elemental");aquatic=mob.kind=="deep_thing";amphibious=mob.kind=="lizard"
        open_tile=flying or (tile=="water" if aquatic else tile not in ("stone","wall","lava") if amphibious else tile not in ("stone","wall","water","lava"))
        if open_tile and not any(p.level==mob.level and p.x==nx and p.y==ny for p in state.players) and not any(m is not mob and m.level==mob.level and m.x==nx and m.y==ny for m in state.monsters):mob.x,mob.y=nx,ny

    def _update_plants(self) -> None:
        state=self._require_state()
        for plant in state.plants:
            plant.age=min(500,plant.age+1)
            if plant.age>=500 and state.maps[plant.level][plant.y][plant.x]=="plant":
                state.maps[plant.level][plant.y][plant.x]="ripe_plant"

    def _calculate_inventory_achievements(self)->None:
        state=self._require_state()
        for p in state.players:
            for resource in ("wood","stone","coal","iron","diamond","ruby","sapphire"):
                if p.inventory[resource]>0:self._award(f"collect_{resource}",p)
            if p.saplings>0:self._award("collect_sapling",p)
            if p.bow>0:self._award("find_bow",p)
            if p.arrows>0:self._award("make_arrow",p)
            if p.torches>0:self._award("make_torch",p)
            for item in ("pickaxe","sword"):
                value=getattr(p,item)
                for tier,name in enumerate(("wood","stone","iron","diamond"),1):
                    if value>=tier:self._award(f"make_{name}_{item}",p)

    def _spawn_mobs(self)->None:
        state=self._require_state();alive=[p for p in state.players if p.alive]
        if not alive:return
        level=alive[0].level
        if level==NUM_LEVELS-1:return
        state.monsters[:]=[m for m in state.monsters if m.level!=level or min((abs(m.x-p.x)+abs(m.y-p.y) for p in alive),default=0)<14]
        caps=(len(state.players)*3,len(state.players)*3,len(state.players)*2)
        if level in (1,3,4):caps=(3,3,2)
        chances=(.1,.02+.1*(1-state.light_level)**2,.05) if level==0 else ((0 if level==7 else .1),.06,.05)
        if state.monsters_killed[level]<8:chances=tuple(min(1,chance*3) for chance in chances)
        for category,(kind,health,chance,cap) in enumerate(zip(FLOOR_MOBS[level],MOB_HEALTH[level],chances,caps)):
            if kind is None or sum(m.level==level and m.category==("passive","melee","ranged")[category] for m in state.monsters)>=cap:continue
            roll=(self._mix64(state.seed^state.timestep^(level<<8)^(category<<16))%10_000)/10_000
            if roll>=chance:continue
            start=self._mix64(state.seed^(state.timestep<<11)^(category<<25))%(MAP_SIZE*MAP_SIZE)
            for offset in range(MAP_SIZE*MAP_SIZE):
                cell=(start+offset)%(MAP_SIZE*MAP_SIZE);x,y=cell%MAP_SIZE,cell//MAP_SIZE
                distances=[abs(x-p.x)+abs(y-p.y) for p in alive]
                valid=("water",) if kind=="deep_thing" else ("grass","path","sand","gravel","fire_grass","ice_grass")
                if min(distances)<=9 or min(distances)>=14 or state.maps[level][y][x] not in valid or any(m.level==level and m.x==x and m.y==y for m in state.monsters):continue
                state.monsters.append(Monster(f"spawn_{level}_{state.timestep}_{category}",kind,level,x,y,health,sum(MOB_DAMAGE.get(kind,(0,0,0))),("passive","melee","ranged")[category]));break

    def _update_boss(self)->None:
        state=self._require_state()
        if not any(p.alive and p.level==NUM_LEVELS-1 for p in state.players):return
        if state.boss_wave_timer>0:
            state.boss_wave_timer-=1
            category=1+(state.boss_wave_timer%2);kind=FLOOR_MOBS[min(7,state.boss_progress)][category]
            if kind and sum(m.level==NUM_LEVELS-1 for m in state.monsters)<6:
                graves=[(x,y) for y,row in enumerate(state.maps[-1]) for x,tile in enumerate(row) if tile in ("grave","grave2","grave3")]
                if graves:
                    x,y=graves[self._mix64(state.seed^state.timestep^state.boss_progress)%len(graves)]
                    state.monsters.append(Monster(f"boss_{state.boss_progress}_{state.timestep}_{category}",kind,NUM_LEVELS-1,x,y,MOB_HEALTH[min(7,state.boss_progress)][category],sum(MOB_DAMAGE.get(kind,(0,0,0))),("passive","melee","ranged")[category]))
        if state.boss_wave_timer<=0 and not any(m.level==NUM_LEVELS-1 for m in state.monsters):
            for y,row in enumerate(state.maps[-1]):
                for x,tile in enumerate(row):
                    if tile=="necromancer":state.maps[-1][y][x]="necromancer_vulnerable"

    def _terminate(self, reason: str) -> None:
        state = self._require_state(); state.terminated = True; state.termination_reason = reason
        self._event("game_ended", outcome=reason)

    def observations(self) -> dict[str, dict[str, Any]]:
        state = self._require_state()
        dashboard = [self._player_summary(p) for p in state.players]
        shared = {
            "timestep": state.timestep,
            "light_level": state.light_level,
            "boss_health": state.boss_health,
            "boss_progress": state.boss_progress,
            "trade_count": state.trade_count,
            "food_trade_count": state.food_trade_count,
            "drink_trade_count": state.drink_trade_count,
            "revives": state.revives,
            "friendly_fire_damage": state.ff_damage_dealt,
            "chests_opened": deepcopy(state.chests_opened),
            "monsters_killed": deepcopy(state.monsters_killed),
            "achievements": {name: True for name, earned in state.achievements.items() if earned},
        }
        if state.alem_coord is not None:
            shared["rules_profile"] = "alem_coord_v0"
            shared["coordination"] = {
                "scenario": state.alem_coord.scenario,
                "alpha_milli": state.alem_coord.alpha_milli,
                "sites": [
                    {"site_id": site.site_id, "kind": site.kind, "status": site.status, "target": [site.level, site.x, site.y]}
                    for site in state.alem_coord.sites
                ],
                "metrics": self.alem_metrics(),
            }
        return {
            p.agent_id: {
                "agent_id": p.agent_id,
                "agent_index": i,
                "role": p.role,
                "legal_agent_ids": list(self.agent_ids),
                "legal_actions": self.legal_actions(p.agent_id),
                "self": self._player_summary(p),
                "achievements": {name: True for name, earned in state.achievements_by_agent[p.agent_id].items() if earned},
                "teammate_dashboard": deepcopy(dashboard),
                "level": p.level,
                "map_size": [MAP_SIZE, MAP_SIZE],
                "num_levels": NUM_LEVELS,
                "local_view": self._local_view(p),
                "ascii": self.render_ascii(p.agent_id),
                "visible_monsters": [deepcopy(m.__dict__) for m in state.monsters if m.level == p.level and abs(m.x - p.x) <= self.view_radius and abs(m.y - p.y) <= self.view_radius],
                "shared": deepcopy(shared),
                "last_joint_event": deepcopy(state.last_joint_event),
            }
            for i, p in enumerate(state.players)
        }

    @staticmethod
    def _player_summary(p: Player) -> dict[str, Any]:
        return {"agent_id":p.agent_id,"role":p.role,"position":[p.x,p.y],"level":p.level,"facing":p.facing,"health":p.health,"food":p.food,"drink":p.drink,"energy":p.energy,"mana":p.mana,"alive":p.alive,"sleeping":p.sleeping,"resting":p.resting,"inventory":deepcopy(p.inventory),"equipment":{"pickaxe":p.pickaxe,"sword":p.sword,"armour":p.armour,"armour_slots":deepcopy(p.armour_slots),"bow":p.bow,"arrows":p.arrows,"torches":p.torches,"books":p.books,"saplings":p.saplings,"potions":deepcopy(p.potions),"learned_spell":p.learned_spell,"enchantments":{"sword":p.sword_enchantment,"armour":p.armour_enchantment,"armour_slots":deepcopy(p.armour_enchantments),"bow":p.bow_enchantment}},"attributes":{"dexterity":p.dexterity,"strength":p.strength,"intelligence":p.intelligence,"xp":p.xp,"level_points":p.level_points},"intrinsics":{"recover":p.recover,"hunger":p.hunger,"thirst":p.thirst,"fatigue":p.fatigue,"recover_mana":p.recover_mana},"request":{"resource":p.request_type,"remaining":p.request_duration}}

    def _local_view(self, p: Player) -> list[list[dict[str, Any]]]:
        state=self._require_state(); out=[]
        for y in range(p.y-self.view_radius,p.y+self.view_radius+1):
            row=[]
            for x in range(p.x-self.view_radius,p.x+self.view_radius+1):
                terrain = "out_of_bounds" if not (0<=x<MAP_SIZE and 0<=y<MAP_SIZE) else state.maps[p.level][y][x]
                agents=[q.agent_id for q in state.players if q.alive and q.level==p.level and q.x==x and q.y==y]
                mobs=[m.id for m in state.monsters if m.level==p.level and m.x==x and m.y==y]
                item=None if not (0<=x<MAP_SIZE and 0<=y<MAP_SIZE) else state.item_maps[p.level][y][x]
                light=0.0 if terrain=="out_of_bounds" else state.light_maps[p.level][y][x]*(state.light_level if p.level==0 else 1.0)
                row.append({"x":x,"y":y,"terrain":terrain,"item":item,"light":light,"agents":agents,"mobs":mobs})
            out.append(row)
        return out

    def render_ascii(self, agent_id: str) -> str:
        p=next(p for p in self._require_state().players if p.agent_id==agent_id); rows=[]
        for row in self._local_view(p):
            rows.append("".join((cell["agents"][0][-1] if cell["agents"] else "M" if cell["mobs"] else GLYPHS.get(cell["terrain"],"#")) for cell in row))
        return "\n".join(rows)

    def checkpoint(self) -> dict[str, Any]:
        state=deepcopy(self._require_state().to_dict());state["achievements"]={name:True for name,earned in state["achievements"].items() if earned};state["achievements_by_agent"]={agent:{name:True for name,earned in flags.items() if earned} for agent,flags in state["achievements_by_agent"].items()}
        return {"schema_version":"craftax-coop.checkpoint.v2","state":state}
    def restore(self, checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if checkpoint.get("schema_version") != "craftax-coop.checkpoint.v2": raise ValueError("unsupported checkpoint schema")
        self.state=WorldState.from_dict(deepcopy(checkpoint["state"])); self.agent_ids=tuple(p.agent_id for p in self.state.players); self.rules_profile="alem_coord_v0" if self.state.alem_coord is not None else None; self.coordination={}; return self.observations()
    def state_hash(self) -> str: return hashlib.sha256(json.dumps(self._require_state().to_dict(),sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    def _require_state(self) -> WorldState:
        if self.state is None: raise RuntimeError("reset or restore required")
        return self.state
