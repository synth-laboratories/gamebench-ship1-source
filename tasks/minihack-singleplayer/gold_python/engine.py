"""Symbolic MiniHack gold engine — full BALROG challenge subset."""

from __future__ import annotations

import json
from typing import Any

from core.nev import NevLog
from state import PublicState, PrivateState
from task_resolve import ResolvedTask, resolve_task
from worldgen import cardinal_directions, direction_delta


class MiniHackEngine:
    ENV_FAMILY = "minihack-singleplayer"

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.walls: set[tuple[int, int]] = set()
        self.goals: set[tuple[int, int]] = set()
        self.targets: set[tuple[int, int]] = set()
        self.player = (0, 0)
        self.boulders: set[tuple[int, int]] = set()
        self.monsters: set[tuple[int, int]] = set()
        self.lava: set[tuple[int, int]] = set()
        self.frozen: set[tuple[int, int]] = set()
        self.items_on_ground: dict[tuple[int, int], str] = {}
        self.inventory: set[str] = set()
        self.public = PublicState(player=(0, 0))
        self.private = PrivateState()
        self.nev = NevLog()

    def reset(self, resolved: ResolvedTask) -> None:
        self.resolved = resolved
        self.walls = set(resolved.walls)
        self.goals = set(resolved.goals)
        self.targets = set(resolved.targets)
        self.player = resolved.player_start
        self.boulders = set(resolved.boulders_start)
        self.monsters = set(resolved.monsters_start)
        self.lava = set(resolved.lava_start)
        self.frozen = set(resolved.frozen_start)
        self.items_on_ground = {pos: item_id for pos, item_id in resolved.items_start}
        self.inventory = set()
        self.public = PublicState(player=self.player)
        self.private = PrivateState(
            config_hash=resolved.config_hash,
            episode_id=resolved.episode_id,
        )
        self.nev = NevLog()
        self._sync_public()
        self.nev.append(
            step_index=0,
            episode_id=resolved.episode_id,
            kind="task_resolved",
            message=f"TaskResolved({resolved.task_id},{resolved.config_hash})",
            payload={"task": resolved.to_dict()},
        )

    def reset_from_task(self, task: dict[str, Any], seed_override: int | None = None) -> None:
        self.reset(resolve_task(task, seed_override=seed_override))

    def step(self, action: dict[str, Any] | str) -> dict[str, Any]:
        if self.resolved is None:
            raise RuntimeError("engine must be reset before step")
        parsed = parse_action(action)
        self.private.step_index += 1
        if self.private.terminated or self.private.truncated:
            self._blocked(parsed, "terminal", "episode already ended")
            return self.symbolic_readout()

        kind = parsed["kind"]
        if kind == "wait":
            self._apply_reward(self._step_reward(), parsed)
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="action_applied",
                action=parsed,
                transition="wait",
                message=f"ActionApplied(wait,step={self.private.step_index})",
            )
            self._finalize_step(parsed)
            return self.symbolic_readout()
        if kind == "pickup":
            return self._step_pickup(parsed)
        if kind == "attack":
            return self._step_attack(parsed)
        if kind == "move":
            return self._step_move(parsed)
        self._blocked(parsed, "unknown_action", f"unknown action {kind}")
        return self.symbolic_readout()

    def _step_pickup(self, parsed: dict[str, Any]) -> dict[str, Any]:
        assert self.resolved is not None
        reward = self._step_reward()
        item_id = self.items_on_ground.get(self.player)
        if item_id is None:
            self._blocked(parsed, "no_item", "no item at player position", reward=reward)
            return self.symbolic_readout()
        del self.items_on_ground[self.player]
        self.inventory.add(item_id)
        if item_id == "freeze":
            self._freeze_all_lava(parsed)
        self._sync_public()
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="action_applied",
            action=parsed,
            transition="pickup",
            message=f"ItemPicked({item_id})",
            payload={"item_id": item_id, "inventory": sorted(self.inventory)},
        )
        self._apply_reward(reward + 0.05, parsed)
        self._finalize_step(parsed)
        return self.symbolic_readout()

    def _freeze_all_lava(self, parsed: dict[str, Any]) -> None:
        assert self.resolved is not None
        if not self.lava:
            return
        self.frozen.update(self.lava)
        self.lava.clear()
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            action=parsed,
            transition="lava_frozen",
            message="LavaFrozen(all)",
            payload={"frozen": [list(pos) for pos in sorted(self.frozen)]},
        )

    def _step_attack(self, parsed: dict[str, Any]) -> dict[str, Any]:
        assert self.resolved is not None
        direction = str(parsed.get("direction", ""))
        try:
            dr, dc = direction_delta(direction)
        except ValueError:
            self._blocked(parsed, "unknown_direction", f"unknown direction {direction}")
            return self.symbolic_readout()
        reward = self._step_reward()
        pr, pc = self.player
        target = (pr + dr, pc + dc)
        if target not in self.monsters:
            self._blocked(parsed, "no_monster", "no monster to attack", reward=reward)
            return self.symbolic_readout()
        self.monsters.remove(target)
        self._sync_public()
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="action_applied",
            action=parsed,
            transition="attack",
            message=f"MonsterDefeated({list(target)})",
            payload={"monster": list(target), "direction": direction},
        )
        self._apply_reward(reward + 0.2, parsed)
        self._finalize_step(parsed)
        return self.symbolic_readout()

    def _step_move(self, parsed: dict[str, Any]) -> dict[str, Any]:
        assert self.resolved is not None
        direction = str(parsed.get("direction", ""))
        try:
            dr, dc = direction_delta(direction)
        except ValueError:
            self._blocked(parsed, "unknown_direction", f"unknown direction {direction}")
            return self.symbolic_readout()

        reward = self._step_reward()
        pr, pc = self.player
        nr, nc = pr + dr, pc + dc
        if self._is_wall(nr, nc):
            self._blocked(parsed, "wall", "move blocked by wall", reward=reward)
            return self.symbolic_readout()
        if (nr, nc) in self.monsters:
            self._blocked(parsed, "monster", "move blocked by monster", reward=reward)
            return self.symbolic_readout()
        if self._is_lava_blocked(nr, nc):
            self._blocked(parsed, "lava", "move blocked by lava", reward=reward)
            return self.symbolic_readout()

        pushed = False
        if (nr, nc) in self.boulders:
            br, bc = nr + dr, nc + dc
            if self._is_wall(br, bc) or (br, bc) in self.boulders or (br, bc) in self.monsters:
                self._blocked(parsed, "box_blocked", "push blocked", reward=reward)
                return self.symbolic_readout()
            if self._is_lava_blocked(br, bc):
                self._blocked(parsed, "box_blocked", "push blocked by lava", reward=reward)
                return self.symbolic_readout()
            self.boulders.remove((nr, nc))
            self.boulders.add((br, bc))
            pushed = True
            reward += 0.1

        self.player = (nr, nc)
        self._sync_public()
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="action_applied",
            action=parsed,
            transition="move",
            message=f"ActionApplied({direction},step={self.private.step_index})",
            payload={"direction": direction, "player": list(self.player), "pushed": pushed},
        )
        if pushed:
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="push_applied",
                action=parsed,
                transition="push",
                message=f"PushApplied({direction},boulders_on_target={self.public.boulders_on_target})",
                payload={"boulders": [list(pos) for pos in sorted(self.boulders)]},
            )
            if self.public.boulders_on_target > 0:
                self.nev.append(
                    step_index=self.private.step_index,
                    episode_id=self.resolved.episode_id,
                    kind="boulder_on_target",
                    action=parsed,
                    message=f"BoulderOnTarget(count={self.public.boulders_on_target})",
                    payload={"count": self.public.boulders_on_target},
                )

        self._apply_reward(reward, parsed)
        self._finalize_step(parsed)
        return self.symbolic_readout()

    def _finalize_step(self, parsed: dict[str, Any]) -> None:
        if self._check_win(parsed):
            return
        self._maybe_truncated(parsed)

    def _step_reward(self) -> float:
        overrides = self.resolved.rules.get("overrides", {}) if self.resolved else {}
        return float(overrides.get("step_penalty", -0.01))

    def _apply_reward(self, reward: float, action: dict[str, Any]) -> None:
        assert self.resolved is not None
        self.private.total_reward += reward
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="resource_delta",
            action=action,
            transition="reward",
            message=f"RewardDelta({reward:.2f},total={self.private.total_reward:.2f})",
            payload={"reward": reward, "total_reward": self.private.total_reward},
        )

    def _check_win(self, action: dict[str, Any]) -> bool:
        assert self.resolved is not None
        if self.resolved.win_mode == "reach_goal":
            if self.player not in self.goals:
                return False
            return self._terminate_success(action, "goal_reached", "GoalReached", float(
                self.resolved.rules.get("overrides", {}).get("goal_reward", 1.0)
            ), f"GoalReached(player={list(self.player)})", {"player": list(self.player)})

        if self.resolved.win_mode == "all_boulders_on_targets":
            if not self.targets or self.public.boulders_on_target != len(self.targets):
                return False
            return self._terminate_success(
                action,
                "level_complete",
                "LevelComplete",
                float(self.resolved.rules.get("overrides", {}).get("complete_reward", 1.0)),
                f"LevelComplete(boxoban,count={self.public.boulders_on_target})",
                {"boulders_on_target": self.public.boulders_on_target},
            )
        return False

    def _terminate_success(
        self,
        action: dict[str, Any],
        event_kind: str,
        _label: str,
        win_reward: float,
        message: str,
        payload: dict[str, Any],
    ) -> bool:
        assert self.resolved is not None
        self.private.terminated = True
        self.private.total_reward += win_reward
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind=event_kind,
            action=action,
            message=message,
            payload=payload,
        )
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="resource_delta",
            action=action,
            transition="win_reward",
            message=f"RewardDelta({win_reward:.2f},total={self.private.total_reward:.2f})",
            payload={"reward": win_reward, "total_reward": self.private.total_reward},
        )
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="terminal",
            action=action,
            transition="success",
            message="Terminal(success)",
        )
        return True

    def _maybe_truncated(self, action: dict[str, Any]) -> None:
        assert self.resolved is not None
        if self.private.step_index >= self.resolved.max_steps and not self.private.terminated:
            self.private.truncated = True
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="terminal",
                action=action,
                transition="truncated",
                message="Terminal(truncated)",
                payload={"max_steps": self.resolved.max_steps},
            )

    def _blocked(
        self,
        action: dict[str, Any],
        code: str,
        message: str,
        reward: float | None = None,
    ) -> None:
        assert self.resolved is not None
        if reward is not None:
            self._apply_reward(reward, action)
        kind = "push_blocked" if code in {"box_blocked"} else "move_blocked"
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind=kind,
            action=action,
            transition="blocked",
            severity="warn",
            message=f"{kind}({code})",
            payload={"code": code, "message": message},
        )

    def _is_wall(self, row: int, col: int) -> bool:
        return (row, col) in self.walls

    def _is_lava_blocked(self, row: int, col: int) -> bool:
        pos = (row, col)
        if pos in self.frozen:
            return False
        if pos not in self.lava:
            return False
        return "levitation" not in self.inventory

    def _sync_public(self) -> None:
        self.public.player = self.player
        self.public.boulders = sorted(self.boulders)
        self.public.monsters = sorted(self.monsters)
        self.public.lava = sorted(self.lava)
        self.public.frozen = sorted(self.frozen)
        self.public.items_on_ground = [
            {"position": [row, col], "item_id": item_id}
            for (row, col), item_id in sorted(self.items_on_ground.items())
        ]
        self.public.inventory = sorted(self.inventory)
        self.public.boulders_on_target = sum(1 for pos in self.boulders if pos in self.targets)

    def _render_char(self, pos: tuple[int, int]) -> str:
        if pos in self.walls:
            return "#"
        if pos in self.boulders:
            return "$"
        if pos in self.monsters:
            return "M"
        if pos in self.lava:
            return "~"
        if pos in self.frozen:
            return "="
        if pos in self.items_on_ground:
            item = self.items_on_ground[pos]
            return "L" if item == "levitation" else "F"
        if pos in self.targets and pos not in self.boulders:
            return "%"
        if pos in self.goals:
            return ">"
        if pos == self.player:
            return "@"
        return "."

    def symbolic_readout(self) -> dict[str, Any]:
        assert self.resolved is not None
        ascii_rows = []
        for row_index in range(self.resolved.height):
            chars = [self._render_char((row_index, col_index)) for col_index in range(self.resolved.width)]
            ascii_rows.append("".join(chars))
        return {
            "schema": "gamebench.minihack.readout.v1",
            "env_family": self.ENV_FAMILY,
            "task_id": self.resolved.task_id,
            "profile": self.resolved.profile,
            "public": self.public.to_dict(),
            "private": self.private.to_dict(),
            "ascii": "\n".join(ascii_rows),
            "grid_hash": self.resolved.config_hash,
            "nev_cursor": self.nev.cursor(),
            "valid_actions": self.valid_actions(),
        }

    def valid_actions(self) -> list[dict[str, Any]]:
        if self.private.terminated or self.private.truncated:
            return []
        actions: list[dict[str, Any]] = [{"kind": "wait"}]
        if self.player in self.items_on_ground:
            actions.append({"kind": "pickup"})
        for direction in cardinal_directions():
            dr, dc = direction_delta(direction)
            pr, pc = self.player
            target = (pr + dr, pc + dc)
            if target in self.monsters:
                actions.append({"kind": "attack", "direction": direction})
            nr, nc = pr + dr, pc + dc
            if self._is_wall(nr, nc) or (nr, nc) in self.monsters:
                continue
            if self._is_lava_blocked(nr, nc):
                continue
            if (nr, nc) in self.boulders:
                br, bc = nr + dr, nc + dc
                if self._is_wall(br, bc) or (br, bc) in self.boulders or (br, bc) in self.monsters:
                    continue
                if self._is_lava_blocked(br, bc):
                    continue
            actions.append({"kind": "move", "direction": direction})
        return actions

    def checkpoint_bytes(self) -> bytes:
        assert self.resolved is not None
        payload = {
            "schema_version": "gamebench.checkpoint.v1",
            "env_family": self.ENV_FAMILY,
            "episode_id": self.resolved.episode_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.nev.cursor(),
            "config_hash": self.resolved.config_hash,
            "sim": {
                "resolved": self.resolved.to_dict(),
                "player": list(self.player),
                "boulders": [list(pos) for pos in sorted(self.boulders)],
                "monsters": [list(pos) for pos in sorted(self.monsters)],
                "lava": [list(pos) for pos in sorted(self.lava)],
                "frozen": [list(pos) for pos in sorted(self.frozen)],
                "items_on_ground": [[list(pos), item_id] for pos, item_id in sorted(self.items_on_ground.items())],
                "inventory": sorted(self.inventory),
                "public": self.public.to_dict(),
                "private": self.private.to_dict(),
                "events": self.nev.export(),
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = json.loads(blob.decode("utf-8"))
        sim = payload["sim"]
        resolved_data = sim["resolved"]
        self.resolved = ResolvedTask(
            task_id=str(resolved_data["task_id"]),
            seed=int(resolved_data["seed"]),
            profile=str(resolved_data["profile"]),
            width=int(resolved_data["width"]),
            height=int(resolved_data["height"]),
            walls=frozenset((int(r), int(c)) for r, c in resolved_data["walls"]),
            goals=frozenset((int(r), int(c)) for r, c in resolved_data["goals"]),
            targets=frozenset((int(r), int(c)) for r, c in resolved_data["targets"]),
            player_start=(int(resolved_data["player_start"][0]), int(resolved_data["player_start"][1])),
            boulders_start=frozenset((int(r), int(c)) for r, c in resolved_data["boulders_start"]),
            monsters_start=frozenset((int(r), int(c)) for r, c in resolved_data.get("monsters_start", [])),
            lava_start=frozenset((int(r), int(c)) for r, c in resolved_data.get("lava_start", [])),
            frozen_start=frozenset((int(r), int(c)) for r, c in resolved_data.get("frozen_start", [])),
            items_start=frozenset(
                ((int(entry[0][0]), int(entry[0][1])), str(entry[1])) for entry in resolved_data.get("items_start", [])
            ),
            rules=dict(resolved_data["rules"]),
            max_steps=int(resolved_data["max_steps"]),
            win_mode=str(resolved_data["win_mode"]),
            config_hash=str(resolved_data["config_hash"]),
            episode_id=str(resolved_data["episode_id"]),
        )
        self.walls = set(self.resolved.walls)
        self.goals = set(self.resolved.goals)
        self.targets = set(self.resolved.targets)
        self.player = (int(sim["player"][0]), int(sim["player"][1]))
        self.boulders = {(int(r), int(c)) for r, c in sim["boulders"]}
        self.monsters = {(int(r), int(c)) for r, c in sim.get("monsters", [])}
        self.lava = {(int(r), int(c)) for r, c in sim.get("lava", [])}
        self.frozen = {(int(r), int(c)) for r, c in sim.get("frozen", [])}
        self.items_on_ground = {
            (int(entry[0][0]), int(entry[0][1])): str(entry[1]) for entry in sim.get("items_on_ground", [])
        }
        self.inventory = set(sim.get("inventory", []))
        self.public = PublicState(
            player=self.player,
            boulders=[(int(r), int(c)) for r, c in sim["public"]["boulders"]],
            monsters=[(int(r), int(c)) for r, c in sim["public"].get("monsters", [])],
            lava=[(int(r), int(c)) for r, c in sim["public"].get("lava", [])],
            frozen=[(int(r), int(c)) for r, c in sim["public"].get("frozen", [])],
            items_on_ground=list(sim["public"].get("items_on_ground", [])),
            inventory=list(sim["public"].get("inventory", [])),
            boulders_on_target=int(sim["public"]["boulders_on_target"]),
        )
        private = sim["private"]
        self.private = PrivateState(
            step_index=int(private["step_index"]),
            total_reward=float(private["total_reward"]),
            terminated=bool(private["terminated"]),
            truncated=bool(private["truncated"]),
            config_hash=str(private["config_hash"]),
            episode_id=str(private["episode_id"]),
        )
        self.nev = NevLog.from_export(sim["events"])
        return self.nev.cursor()

    def clone_for_sim(self) -> "MiniHackEngine":
        clone = MiniHackEngine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone


def parse_action(action: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(action, dict):
        parsed = dict(action)
    elif isinstance(action, str):
        if action.strip().startswith("{"):
            parsed = json.loads(action)
        else:
            parsed = {"kind": "move", "direction": action}
    else:
        raise ValueError("invalid action")
    if "kind" not in parsed and "direction" in parsed:
        parsed["kind"] = "move"
    if "kind" not in parsed:
        raise ValueError("minihack action requires kind")
    return parsed
