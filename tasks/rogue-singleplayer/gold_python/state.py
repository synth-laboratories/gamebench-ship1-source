"""Rogue public and private state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Position = tuple[int, int]


@dataclass
class PublicState:
    terrain: list[str]
    hero: Position
    visible_items: dict[str, str] = field(default_factory=dict)
    visible_monsters: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "terrain": self.terrain,
            "hero": [self.hero[0], self.hero[1]],
            "visible_items": dict(sorted(self.visible_items.items())),
            "visible_monsters": dict(sorted(self.visible_monsters.items())),
        }


@dataclass
class PrivateState:
    step_index: int = 0
    total_reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    terminal_reason: str = ""
    dungeon_level: int = 1
    max_level: int = 1
    has_amulet: bool = False
    purse: int = 0
    food: int = 1
    hp: int = 12
    max_hp: int = 12
    rng_seed: int = 0
    item_values: dict[str, int] = field(default_factory=dict)
    source_inventory: list[dict[str, Any]] = field(default_factory=list)
    left_ring_id: str = ""
    right_ring_id: str = ""
    current_weapon_id: str = ""
    current_armor_id: str = ""
    player_flags: int = 0
    strength: int = 16
    max_strength: int = 16
    no_command: int = 0
    no_move: int = 0
    food_left: int = 1300
    hungry_state: int = 0
    quiet: int = 0
    daemon_between: int = 0
    pot_known: list[bool] = field(default_factory=lambda: [False] * 14)
    ring_known: list[bool] = field(default_factory=lambda: [False] * 14)
    scr_known: list[bool] = field(default_factory=lambda: [False] * 18)
    ws_known: list[bool] = field(default_factory=lambda: [False] * 14)
    seen_tiles: list[str] = field(default_factory=list)
    scout_score: int = 0
    scout_last: int = 0
    acquired_item_classes: list[str] = field(default_factory=list)
    killed_monster_types: list[str] = field(default_factory=list)
    synth_shaped_reward: float = 0.0
    synth_shaped_reward_last: float = 0.0
    source_effect_markers: list[str] = field(default_factory=list)
    source_monsters: list[dict[str, Any]] = field(default_factory=list)
    source_combat_markers: list[str] = field(default_factory=list)
    source_attack_markers: list[str] = field(default_factory=list)
    source_chase_markers: list[str] = field(default_factory=list)
    source_traps: list[dict[str, Any]] = field(default_factory=list)
    source_trap_markers: list[str] = field(default_factory=list)
    source_map_cells: list[dict[str, Any]] = field(default_factory=list)
    source_daemon_actions: list[dict[str, Any]] = field(default_factory=list)
    source_daemon_markers: list[str] = field(default_factory=list)
    source_level_objects: list[dict[str, Any]] = field(default_factory=list)
    source_rooms: list[dict[str, Any]] = field(default_factory=list)
    source_passages: list[dict[str, Any]] = field(default_factory=list)
    source_level_markers: list[str] = field(default_factory=list)
    player_exp: int = 0
    player_level: int = 1
    player_armor: int = 6
    player_damage: str = "1x4"
    vf_hit: int = 0
    max_hit: int = 0
    kamikaze: bool = False
    command_after: bool = True
    command_running: bool = False
    command_count: int = 0
    command_last: str = ""
    command_direction: str = ""
    command_runch: str = ""
    command_to_death: bool = False
    command_markers: list[str] = field(default_factory=list)
    config_hash: str = ""
    episode_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "total_reward": self.total_reward,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "terminal_reason": self.terminal_reason,
            "dungeon_level": self.dungeon_level,
            "max_level": self.max_level,
            "has_amulet": self.has_amulet,
            "purse": self.purse,
            "food": self.food,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "rng_seed": self.rng_seed,
            "item_values": dict(sorted(self.item_values.items())),
            "source_inventory": [dict(item) for item in self.source_inventory],
            "left_ring_id": self.left_ring_id,
            "right_ring_id": self.right_ring_id,
            "current_weapon_id": self.current_weapon_id,
            "current_armor_id": self.current_armor_id,
            "player_flags": self.player_flags,
            "strength": self.strength,
            "max_strength": self.max_strength,
            "no_command": self.no_command,
            "no_move": self.no_move,
            "food_left": self.food_left,
            "hungry_state": self.hungry_state,
            "quiet": self.quiet,
            "daemon_between": self.daemon_between,
            "pot_known": list(self.pot_known),
            "ring_known": list(self.ring_known),
            "scr_known": list(self.scr_known),
            "ws_known": list(self.ws_known),
            "seen_tiles": list(self.seen_tiles),
            "scout_score": self.scout_score,
            "scout_last": self.scout_last,
            "acquired_item_classes": list(self.acquired_item_classes),
            "killed_monster_types": list(self.killed_monster_types),
            "synth_shaped_reward": self.synth_shaped_reward,
            "synth_shaped_reward_last": self.synth_shaped_reward_last,
            "source_effect_markers": list(self.source_effect_markers),
            "source_monsters": [dict(monster) for monster in self.source_monsters],
            "source_combat_markers": list(self.source_combat_markers),
            "source_attack_markers": list(self.source_attack_markers),
            "source_chase_markers": list(self.source_chase_markers),
            "source_traps": [dict(trap) for trap in self.source_traps],
            "source_trap_markers": list(self.source_trap_markers),
            "source_map_cells": [dict(cell) for cell in self.source_map_cells],
            "source_daemon_actions": [dict(action) for action in self.source_daemon_actions],
            "source_daemon_markers": list(self.source_daemon_markers),
            "source_level_objects": [dict(obj) for obj in self.source_level_objects],
            "source_rooms": [dict(room) for room in self.source_rooms],
            "source_passages": [dict(passage) for passage in self.source_passages],
            "source_level_markers": list(self.source_level_markers),
            "player_exp": self.player_exp,
            "player_level": self.player_level,
            "player_armor": self.player_armor,
            "player_damage": self.player_damage,
            "vf_hit": self.vf_hit,
            "max_hit": self.max_hit,
            "kamikaze": self.kamikaze,
            "command_after": self.command_after,
            "command_running": self.command_running,
            "command_count": self.command_count,
            "command_last": self.command_last,
            "command_direction": self.command_direction,
            "command_runch": self.command_runch,
            "command_to_death": self.command_to_death,
            "command_markers": list(self.command_markers),
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }
