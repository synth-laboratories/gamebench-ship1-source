"""Authoritative native Python Crafter gold engine."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from core.checkpoint import decode_checkpoint, encode_checkpoint
from core.nev import EventKind, EventRecord, EventSeverity, NevLog
from state import PrivateState, PublicState, SimSnapshot
from task_resolve import ResolvedTask, resolve_task
from worldgen import ChaCha8Rng, generate_world


ACTIONS = [
    "noop",
    "move_left",
    "move_right",
    "move_up",
    "move_down",
    "do",
    "sleep",
    "place_stone",
    "place_table",
    "place_furnace",
    "place_plant",
    "make_wood_pickaxe",
    "make_stone_pickaxe",
    "make_iron_pickaxe",
    "make_wood_sword",
    "make_stone_sword",
    "make_iron_sword",
    "make_diamond_pickaxe",
    "make_diamond_sword",
    "make_iron_armor",
    "make_diamond_armor",
    "make_bow",
    "make_arrow",
    "shoot_arrow",
    "drink_potion_red",
    "drink_potion_green",
    "drink_potion_blue",
    "drink_potion_pink",
    "drink_potion_cyan",
    "drink_potion_yellow",
]
ACTION_ALIASES = {
    "up": "move_up",
    "down": "move_down",
    "left": "move_left",
    "right": "move_right",
    "wait": "noop",
    "noop": "noop",
}
DIRS = {
    "move_left": (-1, 0),
    "move_right": (1, 0),
    "move_up": (0, -1),
    "move_down": (0, 1),
}
MATERIALS = {
    "water",
    "grass",
    "stone",
    "path",
    "sand",
    "tree",
    "lava",
    "coal",
    "iron",
    "diamond",
    "table",
    "furnace",
    "sapphire",
    "ruby",
    "chest",
}
WALKABLE = {"grass", "path", "sand", "lava"}
VITAL_KEYS = {"health", "food", "drink", "energy"}
INVENTORY_KEYS = [
    "health",
    "food",
    "drink",
    "energy",
    "sapling",
    "wood",
    "stone",
    "coal",
    "iron",
    "diamond",
    "sapphire",
    "ruby",
    "wood_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "diamond_pickaxe",
    "wood_sword",
    "stone_sword",
    "iron_sword",
    "diamond_sword",
    "bow",
    "arrows",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
    "xp",
    "level",
    "stat_points",
]
ACHIEVEMENTS = [
    "collect_coal",
    "collect_diamond",
    "collect_drink",
    "collect_iron",
    "collect_sapling",
    "collect_stone",
    "collect_wood",
    "defeat_skeleton",
    "defeat_zombie",
    "eat_cow",
    "eat_plant",
    "make_iron_pickaxe",
    "make_iron_sword",
    "make_stone_pickaxe",
    "make_stone_sword",
    "make_wood_pickaxe",
    "make_wood_sword",
    "place_furnace",
    "place_plant",
    "place_stone",
    "place_table",
    "wake_up",
    "collect_sapphire",
    "collect_ruby",
    "open_chest",
    "make_diamond_pickaxe",
    "make_diamond_sword",
    "make_bow",
    "make_arrow",
    "make_iron_armor",
    "make_diamond_armor",
    "defeat_orc_soldier",
    "defeat_orc_mage",
    "defeat_knight",
    "defeat_knight_archer",
    "defeat_troll",
    "drink_potion",
    "gain_xp",
    "reach_level",
]
ENTITY_HEALTH = {
    "cow": 3,
    "zombie": 5,
    "skeleton": 3,
    "orc_soldier": 5,
    "orc_mage": 3,
    "knight": 9,
    "knight_archer": 8,
    "troll": 12,
    "bat": 2,
    "snail": 3,
}
DEFEAT_ACHIEVEMENT = {
    "zombie": "defeat_zombie",
    "skeleton": "defeat_skeleton",
    "orc_soldier": "defeat_orc_soldier",
    "orc_mage": "defeat_orc_mage",
    "knight": "defeat_knight",
    "knight_archer": "defeat_knight_archer",
    "troll": "defeat_troll",
}
RULE_REWARD_DEFAULTS = {
    "achievement": 1.0,
    "invalid_action": 0.0,
    "death": 0.0,
    "step": 0.0,
}
DEFAULT_MONTY_REWARDS: dict[str, dict[str, Any]] = {
    "collect_wood_shaped_v1": {
        "achievement_rewards": {
            "collect_wood": 0.25,
            "place_table": 0.40,
            "make_wood_pickaxe": 0.50,
            "collect_stone": 0.25,
        },
        "resource_rewards": {"wood": 0.02, "stone": 0.02},
        "action_penalties": {"unknown_action": -0.50},
    },
    "achievement_ladder_v1": {
        "achievement_default": 0.25,
        "action_penalties": {"unknown_action": -0.50},
    },
    "sparse_classic": {"achievement_default": 1.0},
    "goal_binary_v1": {"achievement_default": 0.0},
}
SNAPSHOT_NEV_TAIL = 8


@dataclass
class Entity:
    id: str
    kind: str
    pos: tuple[int, int]
    health: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "pos": [self.pos[0], self.pos[1]],
            "health": self.health,
            "facing": None,
            "metadata": dict(self.metadata),
        }


@dataclass
class NativeWorld:
    width: int
    height: int
    view_radius: int
    max_steps: int
    seed: int
    tiles: list[list[str]]
    player_pos: tuple[int, int]
    player_facing: tuple[int, int] = (0, 1)
    player_sleeping: bool = False
    daylight: float = 1.0
    episode: int = 0
    step: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    achievements: dict[str, int] = field(default_factory=dict)
    entities: list[Entity] = field(default_factory=list)
    rng_state: object | None = None

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "view_radius": self.view_radius,
            "max_steps": self.max_steps,
            "seed": self.seed,
            "tiles": self.tiles,
            "player_pos": list(self.player_pos),
            "player_facing": list(self.player_facing),
            "player_sleeping": self.player_sleeping,
            "daylight": self.daylight,
            "episode": self.episode,
            "step": self.step,
            "inventory": dict(self.inventory),
            "achievements": dict(self.achievements),
            "entities": [entity.to_dict() for entity in self.entities],
            "rng_state": self.rng_state,
        }

    @classmethod
    def from_checkpoint(cls, payload: dict[str, Any]) -> "NativeWorld":
        return cls(
            width=int(payload["width"]),
            height=int(payload["height"]),
            view_radius=int(payload["view_radius"]),
            max_steps=int(payload["max_steps"]),
            seed=int(payload["seed"]),
            tiles=[list(row) for row in payload["tiles"]],
            player_pos=tuple(payload["player_pos"]),
            player_facing=tuple(payload["player_facing"]),
            player_sleeping=bool(payload["player_sleeping"]),
            daylight=float(payload["daylight"]),
            episode=int(payload["episode"]),
            step=int(payload["step"]),
            inventory={key: int(value) for key, value in payload["inventory"].items()},
            achievements={key: int(value) for key, value in payload["achievements"].items()},
            entities=[
                Entity(
                    id=str(entity["id"]),
                    kind=str(entity["kind"]),
                    pos=tuple(entity["pos"]),
                    health=int(entity.get("health") or 0),
                    metadata=dict(entity.get("metadata", {})),
                )
                for entity in payload.get("entities", [])
            ],
            rng_state=payload.get("rng_state"),
        )


def episode_id_for_task(task_id: str, seed: int, config_hash: str) -> str:
    digest = hashlib.sha256(f"gamebench.crafter-singleplayer.episode:{task_id}:{seed}:{config_hash}".encode()).hexdigest()
    return digest[:32]


class CrafterEngine:
    ENV_FAMILY = "crafter-singleplayer"

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.world: NativeWorld | None = None
        self.observation: dict[str, Any] = {}
        self.public = PublicState({}, (0, 0), {}, {}, False)
        self.private = PrivateState("", "", "", 0, "")
        self.nev = NevLog()
        self._rng = ChaCha8Rng(0)
        self._debug_events: list[str] = []

    def reset(self, resolved_task: ResolvedTask) -> SimSnapshot:
        self.resolved = resolved_task
        self.world = self._make_world(resolved_task)
        self._rng = ChaCha8Rng(resolved_task.seed)
        self.world.rng_state = self._rng
        self.observation = self._current_observation()
        episode_id = episode_id_for_task(resolved_task.task_id, resolved_task.seed, resolved_task.config_hash)
        seeded_achievements = {
            name for name, count in self.world.achievements.items() if int(count) > 0
        }
        self.private = PrivateState(
            episode_id=episode_id,
            task_id=resolved_task.task_id,
            scenario_id=resolved_task.scenario_id,
            seed=resolved_task.seed,
            config_hash=resolved_task.config_hash,
            achievements=seeded_achievements,
            reward_breakdown=self._initial_reward_breakdown(resolved_task),
        )
        self.private.reward_breakdown["achievement_count"] = len(seeded_achievements)
        self.public = self._public_state(done=False)
        self.nev = NevLog()
        self._append_nev(
            kind=EventKind.TASK_RESOLVED,
            message=f"TaskResolved({resolved_task.scenario_id},{resolved_task.config_hash})",
            payload={"resolved": resolved_task.to_dict()},
        )
        return self.snapshot(include_nev=False)

    def reset_from_task(self, task: dict[str, Any], seed_override: int | None = None) -> SimSnapshot:
        return self.reset(resolve_task(task, seed_override=seed_override))

    def step(self, action: str | dict[str, Any]) -> tuple[SimSnapshot, EventRecord | None]:
        action_name = normalize_action(action)
        if action_name not in ACTIONS:
            return self._reject(action_name, "unknown_action")
        if self.private.terminated or self.private.truncated:
            return self._reject(action_name, "terminal")
        if self.world is None:
            raise RuntimeError("engine has not been reset")

        before_inventory = dict(self.world.inventory)
        before_achievements = dict(self.world.achievements)
        before_pos = self.world.player_pos
        before_facing = self.world.player_facing
        before_player = self._player_observation(before_inventory)
        before_step = self.world.step
        self._debug_events = []

        self._process_action(action_name)
        self.world.step += 1
        done_reason = self._done_reason()
        if done_reason == "death":
            self._debug_events.append("Death cause: unknown")
        done = done_reason is not None
        self.private.step_index = self.world.step
        self.private.terminated = done_reason == "death"
        self.private.truncated = done_reason == "max_steps"
        self.private.done_reason = done_reason
        self.observation = self._current_observation()
        self.public = self._public_state(done=done)
        newly_unlocked = self._newly_unlocked(before_achievements, self.public.achievements)
        env_components = self._env_reward_components(newly_unlocked=newly_unlocked, done_reason=done_reason)
        monty_reward = self._monty_transition_reward(
            before_inventory=before_inventory,
            after_inventory=self.public.inventory,
            newly_unlocked=newly_unlocked,
        )
        self._apply_reward_deltas(env_components=env_components, monty_delta=monty_reward)

        action_event = self._append_nev(
            kind=EventKind.ACTION_APPLIED,
            message=f"ActionApplied({display_action(action_name)},step={self.private.step_index})",
            action=action_name,
            transition={
                "player_pos": {"from": [before_pos[0], before_pos[1]], "to": [self.world.player_pos[0], self.world.player_pos[1]]},
                "step": {"from": before_step, "to": self.world.step},
            },
            payload={"action": action_name, "done": done, "done_reason": done_reason},
        )
        self._append_inventory_deltas(action_name, before_inventory, self.public.inventory)
        if before_pos != self.public.player_pos or self.world.player_facing != before_facing:
            self._append_nev(
                kind=EventKind.STATE_TRANSITION,
                message=f"StateTransition(pos={self.observation['player']['pos']},facing={self.observation['player']['facing']})",
                action=action_name,
                payload={
                    "player_before": before_player,
                    "player_after": self.observation.get("player", {}),
                },
            )
        for achievement in newly_unlocked:
            self.private.achievements.add(achievement)
            self._append_nev(
                kind=EventKind.ACHIEVEMENT_UNLOCKED,
                message=f"AchievementUnlocked({achievement})",
                action=action_name,
                payload={"achievement": achievement},
            )
        for debug in self._debug_events:
            self._append_nev(
                kind=EventKind.ENTITY_TRANSITION,
                message=f"Debug({debug})",
                action=action_name,
                payload={"substrate_event": debug},
            )
        self._append_reward_delta_events(action_name, env_components, monty_reward)
        if done:
            terminal_kind = EventKind.DEATH if done_reason == "death" else EventKind.EPISODE_TRUNCATED
            self._append_nev(
                kind=terminal_kind,
                message=f"{title_event(terminal_kind.value)}({done_reason})",
                action=action_name,
                payload={"reason": done_reason},
            )
            self._append_nev(
                kind=EventKind.TERMINAL,
                message=f"Terminal({done_reason})",
                action=action_name,
                payload={"reason": done_reason},
            )
        self._append_checkpoint_cadence_event()
        return self.snapshot(include_nev=False), action_event

    def checkpoint_bytes(self) -> bytes:
        if self.world is None or self.resolved is None:
            raise RuntimeError("engine has not been reset")
        self.world.rng_state = self._rng.to_checkpoint()
        return encode_checkpoint(
            env_family=self.ENV_FAMILY,
            episode_id=self.private.episode_id,
            step_index=self.private.step_index,
            nev_cursor=self.nev.cursor(),
            config_hash=self.private.config_hash,
            sim={
                "resolved": self.resolved.to_dict(),
                "world": self.world.to_checkpoint(),
                "observation": self.observation,
                "private": self.private.to_dict(),
            },
            nev_events=self.nev.export(),
        )

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = decode_checkpoint(blob)
        if payload["env_family"] != self.ENV_FAMILY:
            raise ValueError(f"wrong env_family: {payload['env_family']}")
        previous_events = self.nev.export()
        sim = payload["sim"]
        self.resolved = _resolved_from_dict(sim["resolved"])
        self.world = NativeWorld.from_checkpoint(sim["world"])
        self._rng = ChaCha8Rng.from_checkpoint(self.world.rng_state) if isinstance(self.world.rng_state, dict) else ChaCha8Rng(self.world.seed)
        priv = sim["private"]
        self.private = PrivateState(
            episode_id=payload["episode_id"],
            task_id=priv["task_id"],
            scenario_id=priv.get("scenario_id", priv["task_id"]),
            seed=int(priv["seed"]),
            config_hash=payload["config_hash"],
            step_index=int(payload["step_index"]),
            reward_last=float(priv.get("reward_last", 0.0)),
            total_reward=float(priv.get("total_reward", 0.0)),
            reward_breakdown=dict(priv.get("reward_breakdown", {})),
            terminated=bool(priv.get("terminated", False)),
            truncated=bool(priv.get("truncated", False)),
            achievements=set(priv.get("achievements", [])),
            done_reason=priv.get("done_reason"),
        )
        self.observation = self._current_observation()
        self.public = self._public_state(done=self.private.terminated or self.private.truncated)
        self.nev = NevLog()
        if isinstance(payload.get("nev_events"), list):
            self.nev.import_events(payload["nev_events"])
        else:
            cursor = int(payload.get("nev_cursor", 0))
            if previous_events and len(previous_events) >= cursor:
                self.nev.import_events(previous_events[:cursor])
            else:
                tail_events = payload.get("nev_tail_events", [])
                offset = int(payload.get("nev_tail_cursor_offset", 0))
                self.nev.import_events(tail_events if isinstance(tail_events, list) else [], cursor_offset=offset)
        return self.nev.cursor()

    def clone_for_sim(self) -> "CrafterEngine":
        clone = CrafterEngine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone

    def simulate(self, sequences: list[list[str]]) -> list[dict[str, Any]]:
        """Batch-evaluate open-loop action sequences from the current state.

        Each sequence is replayed from a snapshot of the current state on a
        throwaway clone (this engine is left unmodified). Returns one record per
        sequence with the final achievement set and reward — the leaf-evaluation
        primitive used by search / MCTS code policies. Mirrors the rust
        ``/rollouts/:id/simulate`` endpoint so policies are lane-agnostic.
        """
        root_blob = self.checkpoint_bytes()
        results: list[dict[str, Any]] = []
        for index, sequence in enumerate(sequences):
            sim = self.clone_for_sim()
            reward_trace: list[float] = []
            unlock_steps: dict[str, int] = {}
            prev_achievements = set(sim.private.achievements)
            steps = 0
            for action in sequence:
                if sim.private.terminated or sim.private.truncated:
                    break
                sim.step(str(action))
                steps += 1
                reward_trace.append(float(sim.private.reward_last))
                for name in set(sim.private.achievements) - prev_achievements:
                    unlock_steps.setdefault(name, steps)
                prev_achievements = set(sim.private.achievements)
            results.append(
                {
                    "index": index,
                    "actions": list(sequence),
                    "achievements": sorted(sim.private.achievements),
                    "achievement_unlock_steps": dict(unlock_steps),
                    "reward": float(sim.private.total_reward),
                    "reward_trace": reward_trace,
                    "terminated": bool(sim.private.terminated),
                    "truncated": bool(sim.private.truncated),
                    "steps": steps,
                }
            )
        del root_blob
        return results

    def symbolic_readout(self) -> dict[str, Any]:
        from observations import project_readout

        return project_readout(self)

    def observation_text(self) -> str:
        from observations import observation_text

        return observation_text(self.symbolic_readout())

    def valid_actions(self) -> list[str]:
        if self.private.terminated or self.private.truncated:
            return []
        return list(ACTIONS)

    def snapshot(self, *, include_nev: bool = True, nev_tail: int = SNAPSHOT_NEV_TAIL) -> SimSnapshot:
        cursor = self.nev.cursor()
        if include_nev:
            events = self.nev.export()
            tail_events = events[-max(0, int(nev_tail)) :] if nev_tail > 0 else []
            return SimSnapshot(
                public=self.public,
                private=self.private,
                nev_events=events,
                nev_cursor=cursor,
                nev_tail_events=tail_events,
                nev_events_truncated=False,
            )
        return SimSnapshot(
            public=self.public,
            private=self.private,
            nev_events=[],
            nev_cursor=cursor,
            nev_tail_events=self.nev.export_tail(nev_tail),
            nev_events_truncated=cursor > 0,
        )

    def _make_world(self, resolved: ResolvedTask) -> NativeWorld:
        generated = generate_world(resolved)
        tiles = [list(row) for row in generated.tiles]
        player_pos = (resolved.width // 2, resolved.height // 2)
        world = NativeWorld(
            width=resolved.width,
            height=resolved.height,
            view_radius=resolved.view_radius,
            max_steps=resolved.max_steps,
            seed=resolved.seed,
            tiles=tiles,
            player_pos=player_pos,
            inventory=_default_inventory(),
            achievements={name: 0 for name in ACHIEVEMENTS},
            entities=[
                Entity(
                    id=str(entity["id"]),
                    kind=str(entity["kind"]),
                    pos=(int(entity["pos"][0]), int(entity["pos"][1])),
                    health=int(entity["health"]),
                    metadata=dict(entity.get("metadata", {})),
                )
                for entity in generated.entities
            ],
            rng_state=ChaCha8Rng(resolved.seed),
        )
        self._apply_initial_state(world, resolved.world.get("initial_state"))
        hooks = resolved.adapter_hooks
        if hooks.get("freeze_hunger"):
            world.inventory["food"] = 9
        if hooks.get("freeze_thirst"):
            world.inventory["drink"] = 9
        if hooks.get("freeze_fatigue"):
            world.inventory["energy"] = 9
        if hooks.get("freeze_daylight"):
            world.daylight = 1.0
        if hooks.get("suppress_mobs"):
            world.entities = [
                entity for entity in world.entities if entity.metadata.get("source") == "initial_state"
            ]
        return world

    def _apply_initial_state(self, world: NativeWorld, initial: dict[str, Any] | None) -> None:
        if not initial:
            return
        for patch in initial.get("tiles", []):
            x, y = int(patch["pos"][0]), int(patch["pos"][1])
            kind = str(patch["kind"])
            if kind not in MATERIALS:
                raise ValueError(f"unsupported material in world.initial_state.tiles: {kind}")
            world.tiles[y][x] = kind
        player = dict(initial.get("player", {}))
        if "pos" in player:
            world.player_pos = (int(player["pos"][0]), int(player["pos"][1]))
        if "facing" in player:
            world.player_facing = (int(player["facing"][0]), int(player["facing"][1]))
        for key, value in dict(initial.get("inventory", {})).items():
            if key not in world.inventory:
                raise ValueError(f"unsupported inventory key in world.initial_state: {key}")
            world.inventory[key] = _clamp_inventory(key, int(value))
        for key, value in dict(initial.get("achievements", {})).items():
            if key not in world.achievements:
                raise ValueError(f"unsupported achievement in world.initial_state: {key}")
            world.achievements[key] = int(value)
        occupied = {entity.pos for entity in world.entities}
        for idx, raw in enumerate(initial.get("entities", [])):
            kind = str(raw["kind"])
            if kind not in ENTITY_HEALTH:
                raise ValueError(f"unsupported entity kind in world.initial_state: {kind}")
            pos = (int(raw["pos"][0]), int(raw["pos"][1]))
            if pos == world.player_pos:
                raise ValueError(f"world.initial_state.entities[{idx}].pos is occupied by the player: {list(pos)}")
            if pos in occupied:
                raise ValueError(f"world.initial_state.entities[{idx}].pos is occupied by another entity: {list(pos)}")
            occupied.add(pos)
            world.entities.append(
                Entity(
                    id=f"initial_{kind}_{idx}",
                    kind=kind,
                    pos=pos,
                    health=int(raw.get("health", ENTITY_HEALTH[kind])),
                    metadata={"source": "initial_state"},
                )
            )

    def _process_action(self, action: str) -> None:
        assert self.world is not None
        if self.world.player_sleeping and action not in {"noop", "sleep"}:
            self.world.player_sleeping = False
            return
        if action in DIRS:
            self._move(action)
        elif action == "do":
            self._do()
        elif action == "sleep":
            self.world.player_sleeping = True
        elif action.startswith("place_"):
            self._place(action)
        elif action.startswith("make_"):
            self._craft(action)
        elif action.startswith("drink_potion_"):
            self._drink_potion(action.removeprefix("drink_potion_"))

    def _move(self, action: str) -> None:
        assert self.world is not None
        dx, dy = DIRS[action]
        self.world.player_facing = (dx, dy)
        target = (self.world.player_pos[0] + dx, self.world.player_pos[1] + dy)
        if not self._in_bounds(target):
            return
        if self._tile(target) not in WALKABLE:
            return
        if self._entity_at(target) is not None:
            return
        self.world.player_pos = target
        if self._tile(target) == "lava":
            self.world.inventory["health"] = 0
        self._debug_events.append(f"ACTION: {display_action(action)}")

    def _do(self) -> None:
        assert self.world is not None
        target = self._front_pos()
        entity = self._entity_at(target)
        if entity is not None:
            self._interact_entity(entity)
            self._debug_events.append(f"ACTION: Do on {entity.kind} at ({target[0]}, {target[1]})")
            return
        tile = self._tile(target)
        if tile == "tree":
            self._set_tile(target, "grass")
            self._add_inventory("wood", 1)
            self._add_achievement("collect_wood")
        elif tile == "stone" and self._best_pickaxe_tier() >= 1:
            self._set_tile(target, "path")
            self._add_inventory("stone", 1)
            self._add_achievement("collect_stone")
        elif tile == "coal" and self._best_pickaxe_tier() >= 1:
            self._set_tile(target, "path")
            self._add_inventory("coal", 1)
            self._add_achievement("collect_coal")
        elif tile == "iron" and self._best_pickaxe_tier() >= 2:
            self._set_tile(target, "path")
            self._add_inventory("iron", 1)
            self._add_achievement("collect_iron")
        elif tile == "diamond" and self._best_pickaxe_tier() >= 3:
            self._set_tile(target, "path")
            self._add_inventory("diamond", 1)
            self._add_achievement("collect_diamond")
        elif tile == "sapphire" and self._best_pickaxe_tier() >= 4:
            self._set_tile(target, "path")
            self._add_inventory("sapphire", 1)
            self._add_achievement("collect_sapphire")
        elif tile == "ruby" and self._best_pickaxe_tier() >= 4:
            self._set_tile(target, "path")
            self._add_inventory("ruby", 1)
            self._add_achievement("collect_ruby")
        elif tile == "water":
            self._add_inventory("drink", 1)
            self._add_achievement("collect_drink")
        elif tile == "grass" and self._rng.random_f32() < 0.1:
            self._add_inventory("sapling", 1)
            self._add_achievement("collect_sapling")
        elif tile == "chest":
            self._set_tile(target, "path")
            self._add_achievement("open_chest")
            self._open_chest()
        self._debug_events.append(f"ACTION: Do on {tile} at ({target[0]}, {target[1]})")

    def _interact_entity(self, entity: Entity) -> None:
        assert self.world is not None
        damage = self._attack_damage()
        entity.health -= damage
        if entity.health > 0:
            return
        self.world.entities = [candidate for candidate in self.world.entities if candidate.id != entity.id]
        if entity.kind == "cow":
            self._add_inventory("food", 6)
            self._add_achievement("eat_cow")
        elif entity.kind in DEFEAT_ACHIEVEMENT:
            self._add_achievement(DEFEAT_ACHIEVEMENT[entity.kind])
            if self.resolved and self.resolved.substrate_profile == "craftax_partial":
                self._grant_xp(3)
            elif entity.kind not in {"zombie", "skeleton"}:
                self._grant_xp(2)

    def _place(self, action: str) -> None:
        assert self.world is not None
        material_by_action = {
            "place_stone": "stone",
            "place_table": "table",
            "place_furnace": "furnace",
        }
        target = self._front_pos()
        if not self._in_bounds(target) or self._tile(target) != "grass" or self._entity_at(target) is not None:
            return
        if action == "place_plant":
            if self._use_inventory("sapling", 1):
                self._add_achievement("place_plant")
                world = self.world
                world.entities.append(
                    Entity(
                        id=f"world_{len(world.entities) + 1}",
                        kind="plant",
                        pos=target,
                        health=3,
                    )
                )
            return
        material = material_by_action.get(action)
        if material is None:
            return
        if material == "stone" and not self._use_inventory("stone", 1):
            return
        if material == "table" and not self._use_inventory("wood", 2):
            return
        if material == "furnace" and not self._use_inventory("stone", 4):
            return
        self._set_tile(target, material)
        self._add_achievement(action)
        self._debug_events.append(f"ACTION: {display_action(action)}")

    def _craft(self, action: str) -> None:
        if not self._has_adjacent("table"):
            return
        recipes = {
            "make_wood_pickaxe": {"wood": 1},
            "make_stone_pickaxe": {"wood": 1, "stone": 1},
            "make_wood_sword": {"wood": 1},
            "make_stone_sword": {"wood": 1, "stone": 1},
            "make_diamond_pickaxe": {"wood": 1, "diamond": 1},
            "make_diamond_sword": {"wood": 1, "diamond": 2},
            "make_bow": {"wood": 2},
            "make_arrow": {"wood": 1, "stone": 1},
        }
        furnace_recipes = {
            "make_iron_pickaxe": {"wood": 1, "coal": 1, "iron": 1},
            "make_iron_sword": {"wood": 1, "coal": 1, "iron": 1},
            "make_iron_armor": {"coal": 3, "iron": 3},
        }
        if action in furnace_recipes:
            if not self._has_adjacent("furnace"):
                return
            recipe = furnace_recipes[action]
        elif action == "make_diamond_armor":
            recipe = {"diamond": 3}
        else:
            recipe = recipes.get(action)
        if recipe is None or not self._has_resources(recipe):
            return
        for key, amount in recipe.items():
            self._use_inventory(key, amount)
        if action == "make_arrow":
            self._add_inventory("arrows", 3)
        elif action == "make_iron_armor":
            for key in ("armor_helmet", "armor_chestplate", "armor_leggings", "armor_boots"):
                self.world.inventory[key] = max(self.world.inventory[key], 1)
        elif action == "make_diamond_armor":
            for key in ("armor_helmet", "armor_chestplate", "armor_leggings", "armor_boots"):
                self.world.inventory[key] = max(self.world.inventory[key], 2)
        else:
            item = action.removeprefix("make_")
            self._add_inventory(item, 1)
        self._add_achievement(action)
        self._debug_events.append(f"ACTION: {display_action(action)}")

    def _drink_potion(self, color: str) -> None:
        key = f"potion_{color}"
        if not self._use_inventory(key, 1):
            return
        if color == "red":
            self._add_inventory("health", 2)
        elif color == "green":
            self._add_inventory("food", 2)
        elif color == "blue":
            self._add_inventory("drink", 2)
        elif color == "yellow":
            self._add_inventory("energy", 2)
        self._add_achievement("drink_potion")
        self._debug_events.append(f"ACTION: {display_action('drink_potion_' + color)}")

    def _open_chest(self) -> None:
        if self._rng.random_f32() < 0.5:
            self._add_inventory("arrows", self._rng.gen_range_u32_inclusive(2, 6))
        if self._rng.random_f32() < 0.35:
            potion_idx = self._rng.gen_range_u32_inclusive(0, 5)
            potion = ["red", "green", "blue", "pink", "cyan", "yellow"][potion_idx]
            self._add_inventory(f"potion_{potion}", 1)
        if self._rng.random_f32() < 0.2:
            if self._rng.random_f32() < 0.5:
                self._add_inventory("sapphire", 1)
                self._add_achievement("collect_sapphire")
            else:
                self._add_inventory("ruby", 1)
                self._add_achievement("collect_ruby")
        if self._rng.random_f32() < 0.6:
            self._add_inventory("coal", self._rng.gen_range_u32_inclusive(1, 2))
            self._add_achievement("collect_coal")
        if self._rng.random_f32() < 0.4:
            self._add_inventory("iron", self._rng.gen_range_u32_inclusive(1, 2))
            self._add_achievement("collect_iron")
        if self._rng.random_f32() < 0.2:
            self._add_inventory("diamond", 1)
            self._add_achievement("collect_diamond")

    def _done_reason(self) -> str | None:
        assert self.world is not None
        if self.world.inventory.get("health", 0) <= 0:
            return "death"
        if self.world.step >= self.world.max_steps:
            return "max_steps"
        return None

    def _current_observation(self) -> dict[str, Any]:
        assert self.world is not None
        inventory = dict(self.world.inventory)
        achievements = dict(self.world.achievements)
        return {
            "step": self.world.step,
            "episode": self.world.episode,
            "world": self._symbolic_world(),
            "player": self._player_observation(inventory),
            "achievements": achievements,
            "stats": {
                "score": sum(1 for value in achievements.values() if int(value) > 0),
                "daylight": self.world.daylight,
            },
            "view": self._symbolic_view(),
        }

    def _player_observation(self, inventory: dict[str, int]) -> dict[str, Any]:
        assert self.world is not None
        return {
            "pos": [self.world.player_pos[0], self.world.player_pos[1]],
            "facing": [self.world.player_facing[0], self.world.player_facing[1]],
            "sleeping": self.world.player_sleeping,
            "health": inventory["health"],
            "food": inventory["food"],
            "drink": inventory["drink"],
            "energy": inventory["energy"],
            "inventory": dict(inventory),
        }

    def _symbolic_world(self) -> dict[str, Any]:
        assert self.world is not None
        if not self.resolved or not self.resolved.readouts.get("full_world_state", False):
            return {"width": self.world.width, "height": self.world.height, "tiles": [], "entities": []}
        tiles = [
            {"pos": [x, y], "kind": self.world.tiles[y][x], "in_bounds": True}
            for y in range(self.world.height)
            for x in range(self.world.width)
        ]
        return {
            "width": self.world.width,
            "height": self.world.height,
            "tiles": tiles,
            "entities": [entity.to_dict() for entity in self.world.entities],
        }

    def _symbolic_view(self) -> dict[str, Any]:
        assert self.world is not None
        radius = self.world.view_radius
        px, py = self.world.player_pos
        tiles = []
        world_tiles = self.world.tiles
        width = self.world.width
        height = self.world.height
        for y in range(py - radius, py + radius + 1):
            for x in range(px - radius, px + radius + 1):
                in_bounds = 0 <= x < width and 0 <= y < height
                tiles.append({"pos": [x, y], "kind": world_tiles[y][x] if in_bounds else "water", "in_bounds": in_bounds})
        entities = [
            entity.to_dict()
            for entity in self.world.entities
            if abs(entity.pos[0] - px) <= radius and abs(entity.pos[1] - py) <= radius
        ]
        return {"center": [px, py], "radius": radius, "tiles": tiles, "entities": entities}

    def _public_state(self, *, done: bool) -> PublicState:
        player = self.observation.get("player", {})
        pos = player.get("pos", [0, 0])
        achievements = {key: int(value) for key, value in self.observation.get("achievements", {}).items()}
        inventory = {key: int(value) for key, value in player.get("inventory", {}).items()}
        return PublicState(
            observation=self.observation,
            player_pos=(int(pos[0]), int(pos[1])),
            inventory=inventory,
            achievements=achievements,
            done=done,
        )

    def _append_inventory_deltas(self, action: str, before: dict[str, int], after: dict[str, int]) -> None:
        for key in sorted(set(before) | set(after)):
            if key in VITAL_KEYS:
                continue
            before_value = int(before.get(key, 0))
            after_value = int(after.get(key, 0))
            if before_value == after_value:
                continue
            self._append_nev(
                kind=EventKind.RESOURCE_DELTA,
                message=f"ResourceDelta({key},{before_value}->{after_value})",
                action=action,
                payload={"resource": key, "before": before_value, "after": after_value, "delta": after_value - before_value},
            )

    def _reject(self, action: str, reason: str) -> tuple[SimSnapshot, EventRecord | None]:
        record = self._append_nev(
            kind=EventKind.ACTION_REJECTED,
            severity=EventSeverity.WARN,
            message=f"ActionRejected({action},{reason},step={self.private.step_index})",
            action=action,
            payload={"reason": reason},
        )
        if reason != "terminal":
            self._append_nev(
                kind=EventKind.RULE_VIOLATION,
                severity=EventSeverity.WARN,
                message=f"RuleViolation({reason})",
                action=action,
                payload={"reason": reason},
            )
        env_components = self._rejection_reward_components(reason)
        monty_reward = self._monty_rejection_reward(reason)
        self._apply_reward_deltas(env_components=env_components, monty_delta=monty_reward)
        self._append_reward_delta_events(action, env_components, monty_reward)
        return self.snapshot(include_nev=False), record

    def _initial_reward_breakdown(self, resolved_task: ResolvedTask) -> dict[str, Any]:
        return {
            "schema": "gamebench.crafter.reward_breakdown.v1",
            "env_total": 0.0,
            "monty_total": 0.0,
            "penalty_total": 0.0,
            "last_env": 0.0,
            "last_monty": 0.0,
            "last_env_components": [],
            "achievement_count": 0,
            "rule_rewards": self._rule_reward_config(resolved_task),
            "monty": copy.deepcopy(resolved_task.monty_reward),
        }

    def _apply_reward_deltas(self, *, env_components: list[dict[str, Any]], monty_delta: float) -> None:
        env_delta = self._reward_component_total(env_components)
        breakdown = dict(self.private.reward_breakdown or {})
        breakdown.setdefault("schema", "gamebench.crafter.reward_breakdown.v1")
        breakdown.setdefault("env_total", 0.0)
        breakdown.setdefault("monty_total", 0.0)
        breakdown.setdefault("penalty_total", 0.0)
        breakdown["last_env"] = env_delta
        breakdown["last_monty"] = monty_delta
        breakdown["last_env_components"] = copy.deepcopy(env_components)
        if self.resolved is not None:
            breakdown["rule_rewards"] = self._rule_reward_config(self.resolved)
        breakdown["env_total"] = float(breakdown.get("env_total", 0.0)) + env_delta
        breakdown["monty_total"] = float(breakdown.get("monty_total", 0.0)) + monty_delta
        for component in env_components:
            component_delta = float(component["delta"])
            if component_delta < 0:
                breakdown["penalty_total"] = float(breakdown.get("penalty_total", 0.0)) + component_delta
        if monty_delta < 0:
            breakdown["penalty_total"] = float(breakdown.get("penalty_total", 0.0)) + monty_delta
        breakdown["achievement_count"] = sum(1 for value in self.public.achievements.values() if int(value) > 0)
        self.private.reward_breakdown = breakdown
        self.private.reward_last = env_delta + monty_delta
        self.private.total_reward += self.private.reward_last

    def _append_reward_delta_events(self, action: str, env_components: list[dict[str, Any]], monty_delta: float) -> None:
        env_delta = self._reward_component_total(env_components)
        running_total = self.private.total_reward - env_delta - monty_delta
        for component in env_components:
            delta = float(component["delta"])
            if not delta:
                continue
            running_total += delta
            source = str(component["source"])
            kind = str(component["component"])
            payload = {"delta": delta, "total": running_total, "source": source, "component": kind}
            if "count" in component:
                payload["count"] = component["count"]
            if "achievements" in component:
                payload["achievements"] = list(component["achievements"])
            if source == "achievement" and kind == "achievement":
                message = f"RewardDelta({delta:.2f},total={running_total:.2f})"
            else:
                message = f"RewardDelta({delta:.2f},total={running_total:.2f},source={source},component={kind})"
            self._append_nev(kind=EventKind.REWARD_DELTA, message=message, action=action, payload=payload)
        if monty_delta:
            running_total += monty_delta
            self._append_nev(
                kind=EventKind.REWARD_DELTA,
                message=f"RewardDelta({monty_delta:.2f},total={running_total:.2f},source=monty)",
                action=action,
                payload={"delta": monty_delta, "total": running_total, "source": "monty"},
            )

    def _append_checkpoint_cadence_event(self) -> None:
        if self.resolved is None:
            return
        interval = int(self.resolved.checkpoint_every_n_steps)
        step_index = int(self.private.step_index)
        if interval <= 0 or step_index <= 0 or step_index % interval != 0:
            return
        self._append_nev(
            kind=EventKind.CHECKPOINT,
            message=f"Checkpoint(step={step_index},interval={interval})",
            payload={"source": "cadence", "step_index": step_index, "interval": interval, "nev_cursor_before": self.nev.cursor()},
        )

    def _env_reward_components(self, *, newly_unlocked: list[str], done_reason: str | None) -> list[dict[str, Any]]:
        rewards = self._rule_reward_config(self.resolved)
        components: list[dict[str, Any]] = []
        achievement_delta = rewards["achievement"] * len(newly_unlocked)
        if achievement_delta:
            components.append(
                {
                    "source": "achievement",
                    "component": "achievement",
                    "delta": achievement_delta,
                    "count": len(newly_unlocked),
                    "achievements": newly_unlocked,
                }
            )
        if rewards["step"]:
            components.append({"source": "env", "component": "step", "delta": rewards["step"]})
        if done_reason == "death" and rewards["death"]:
            components.append({"source": "env", "component": "death", "delta": rewards["death"]})
        return components

    def _rejection_reward_components(self, reason: str) -> list[dict[str, Any]]:
        rewards = self._rule_reward_config(self.resolved)
        if reason == "unknown_action" and rewards["invalid_action"]:
            return [{"source": "env", "component": "invalid_action", "delta": rewards["invalid_action"]}]
        return []

    def _rule_reward_config(self, resolved_task: ResolvedTask | None) -> dict[str, float]:
        rewards = dict(resolved_task.rules.get("rewards", {})) if resolved_task is not None else {}
        return {key: float(rewards.get(key, default)) for key, default in RULE_REWARD_DEFAULTS.items()}

    def _reward_component_total(self, components: list[dict[str, Any]]) -> float:
        return sum(float(component["delta"]) for component in components)

    def _monty_transition_reward(
        self,
        *,
        before_inventory: dict[str, int],
        after_inventory: dict[str, int],
        newly_unlocked: list[str],
    ) -> float:
        spec = self.resolved.monty_reward if self.resolved is not None else None
        config = _monty_config(spec)
        if config is None:
            return 0.0
        total = 0.0
        achievement_rewards = dict(config.get("achievement_rewards", {}))
        achievement_default = float(config.get("achievement_default", 0.0))
        for name in newly_unlocked:
            total += float(achievement_rewards.get(name, achievement_default))
        resource_rewards = dict(config.get("resource_rewards", {}))
        for name, weight in resource_rewards.items():
            delta = int(after_inventory.get(name, 0)) - int(before_inventory.get(name, 0))
            if delta > 0:
                total += float(weight) * delta
        return total

    def _monty_rejection_reward(self, reason: str) -> float:
        spec = self.resolved.monty_reward if self.resolved is not None else None
        config = _monty_config(spec)
        if config is None:
            return 0.0
        return float(dict(config.get("action_penalties", {})).get(reason, 0.0))

    def _append_nev(
        self,
        *,
        kind: EventKind,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        action: str | None = None,
        transition: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> EventRecord:
        return self.nev.append(
            EventRecord(
                step_index=self.private.step_index,
                sim_tick=self.private.step_index,
                episode_id=self.private.episode_id,
                kind=kind,
                severity=severity,
                message=message,
                action=action,
                transition=transition,
                payload=payload or {},
            )
        )

    def _front_pos(self) -> tuple[int, int]:
        assert self.world is not None
        return (
            self.world.player_pos[0] + self.world.player_facing[0],
            self.world.player_pos[1] + self.world.player_facing[1],
        )

    def _tile(self, pos: tuple[int, int]) -> str:
        assert self.world is not None
        x, y = pos
        if not self._in_bounds(pos):
            return "water"
        return self.world.tiles[y][x]

    def _set_tile(self, pos: tuple[int, int], value: str) -> None:
        assert self.world is not None
        x, y = pos
        self.world.tiles[y][x] = value

    def _in_bounds(self, pos: tuple[int, int]) -> bool:
        assert self.world is not None
        x, y = pos
        return 0 <= x < self.world.width and 0 <= y < self.world.height

    def _entity_at(self, pos: tuple[int, int]) -> Entity | None:
        assert self.world is not None
        for entity in self.world.entities:
            if entity.pos == pos:
                return entity
        return None

    def _add_inventory(self, key: str, amount: int) -> None:
        assert self.world is not None
        self.world.inventory[key] = _clamp_inventory(key, int(self.world.inventory.get(key, 0)) + amount)

    def _use_inventory(self, key: str, amount: int) -> bool:
        assert self.world is not None
        if int(self.world.inventory.get(key, 0)) < amount:
            return False
        self.world.inventory[key] = int(self.world.inventory.get(key, 0)) - amount
        return True

    def _has_resources(self, recipe: dict[str, int]) -> bool:
        assert self.world is not None
        return all(int(self.world.inventory.get(key, 0)) >= amount for key, amount in recipe.items())

    def _add_achievement(self, key: str, amount: int = 1) -> None:
        assert self.world is not None
        if key in self.world.achievements:
            self.world.achievements[key] = int(self.world.achievements.get(key, 0)) + amount

    def _newly_unlocked(self, before: dict[str, int], after: dict[str, int]) -> list[str]:
        return [
            name
            for name in sorted(after)
            if int(after.get(name, 0)) > 0 and int(before.get(name, 0)) <= 0
        ]

    def _best_pickaxe_tier(self) -> int:
        assert self.world is not None
        inv = self.world.inventory
        if inv.get("diamond_pickaxe", 0) > 0:
            return 4
        if inv.get("iron_pickaxe", 0) > 0:
            return 3
        if inv.get("stone_pickaxe", 0) > 0:
            return 2
        if inv.get("wood_pickaxe", 0) > 0:
            return 1
        return 0

    def _attack_damage(self) -> int:
        assert self.world is not None
        inv = self.world.inventory
        if inv.get("diamond_sword", 0) > 0:
            return 9
        if inv.get("iron_sword", 0) > 0:
            return 5
        if inv.get("stone_sword", 0) > 0:
            return 3
        if inv.get("wood_sword", 0) > 0:
            return 2
        return 1

    def _has_adjacent(self, material: str) -> bool:
        assert self.world is not None
        x, y = self.world.player_pos
        return any(self._tile((x + dx, y + dy)) == material for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    def _grant_xp(self, amount: int) -> None:
        assert self.world is not None
        self.world.inventory["xp"] = int(self.world.inventory.get("xp", 0)) + amount
        self._add_achievement("gain_xp", amount)
        while self.world.inventory["xp"] >= 10 * (self.world.inventory["level"] + 1):
            self.world.inventory["level"] += 1
            self.world.inventory["stat_points"] += 1
            self._add_achievement("reach_level")


def normalize_action(action: str | dict[str, Any]) -> str:
    if isinstance(action, dict):
        raw = action.get("action", action.get("name", action.get("id", "")))
    else:
        raw = action
    value = str(raw).strip().lower().replace(" ", "_")
    return ACTION_ALIASES.get(value, value)


def display_action(action: str) -> str:
    return "".join(part.capitalize() for part in action.split("_"))


def title_event(kind: str) -> str:
    return "".join(display_action(part) for part in kind.split("_"))


def _default_inventory() -> dict[str, int]:
    inventory = {key: 0 for key in INVENTORY_KEYS}
    inventory.update({"health": 9, "food": 9, "drink": 9, "energy": 9})
    return inventory


def _copy_observation(observation: dict[str, Any]) -> dict[str, Any]:
    copied = dict(observation)
    player = dict(observation.get("player", {}))
    if isinstance(player.get("pos"), list):
        player["pos"] = list(player["pos"])
    if isinstance(player.get("facing"), list):
        player["facing"] = list(player["facing"])
    if isinstance(player.get("inventory"), dict):
        player["inventory"] = dict(player["inventory"])
    copied["player"] = player
    copied["achievements"] = dict(observation.get("achievements", {}))
    copied["stats"] = dict(observation.get("stats", {}))
    copied["world"] = _copy_symbolic_region(observation.get("world", {}))
    copied["view"] = _copy_symbolic_region(observation.get("view", {}))
    return copied


def _copy_symbolic_region(region: Any) -> dict[str, Any]:
    if not isinstance(region, dict):
        return {}
    copied = dict(region)
    if isinstance(region.get("center"), list):
        copied["center"] = list(region["center"])
    copied["tiles"] = [_copy_nested_dict(item) for item in region.get("tiles", [])]
    copied["entities"] = [_copy_nested_dict(item) for item in region.get("entities", [])]
    return copied


def _copy_nested_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    copied = dict(value)
    for key in ("pos", "facing"):
        if isinstance(copied.get(key), list):
            copied[key] = list(copied[key])
    if isinstance(copied.get("metadata"), dict):
        copied["metadata"] = dict(copied["metadata"])
    return copied


def _clamp_inventory(key: str, value: int) -> int:
    if key in {"xp"}:
        return max(0, int(value))
    return max(0, min(9, int(value)))


def _monty_config(spec: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(spec, dict):
        return None
    if spec.get("kind") not in {None, "monty_python"}:
        return None
    if spec.get("entry") not in {None, "score_transition"}:
        return None
    module = str(spec.get("module", ""))
    config = copy.deepcopy(DEFAULT_MONTY_REWARDS.get(module, {}))
    for key in ("achievement_rewards", "resource_rewards", "action_penalties"):
        if isinstance(spec.get(key), dict):
            merged = dict(config.get(key, {}))
            merged.update({str(name): float(value) for name, value in spec[key].items()})
            config[key] = merged
    if "achievement_default" in spec:
        config["achievement_default"] = float(spec["achievement_default"])
    if not config:
        return None
    config["module"] = module
    return config


def _json_to_rng_state(value: Any) -> object:
    if isinstance(value, list):
        return tuple(_json_to_rng_state(item) for item in value)
    return value


def _resolved_from_dict(doc: dict[str, Any]) -> ResolvedTask:
    return ResolvedTask(
        task_id=doc["task_id"],
        scenario_id=doc["scenario_id"],
        seed=int(doc["seed"]),
        width=int(doc["width"]),
        height=int(doc["height"]),
        view_radius=int(doc["view_radius"]),
        max_steps=int(doc["max_steps"]),
        world=dict(doc["world"]),
        rules=dict(doc["rules"]),
        readouts=dict(doc["readouts"]),
        stream=dict(doc["stream"]),
        monty_reward=copy.deepcopy(doc.get("monty_reward")),
        checkpoint_every_n_steps=int(doc["checkpoint_every_n_steps"]),
        substrate_profile=str(doc["substrate_profile"]),
        substrate_config=dict(doc["substrate_config"]),
        adapter_hooks=dict(doc.get("adapter_hooks", {})),
        unsupported_rules=list(doc.get("unsupported_rules", [])),
        config_hash=doc["config_hash"],
        resolved_json=dict(doc.get("resolved_json", {})),
    )
