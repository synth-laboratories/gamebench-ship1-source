"""Authoritative Python Sokoban gold engine."""

from __future__ import annotations

import hashlib
from typing import Any

from core.checkpoint import decode_checkpoint, encode_checkpoint
from core.nev import EventKind, EventRecord, EventSeverity, NevLog
from state import PrivateState, PublicState, SimSnapshot
from monty_loader import load_monty_scorer
from task_resolve import BOX, BOX_ON_TARGET, FLOOR, PLAYER, PLAYER_ON_TARGET, TARGET, WALL, ResolvedTask, resolve_task


DIRS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}


def episode_id_for_task(task_id: str, seed: int, config_hash: str) -> str:
    digest = hashlib.sha256(f"gamebench.sokoban-singleplayer.episode:{task_id}:{seed}:{config_hash}".encode()).hexdigest()
    return digest[:32]


class SokobanEngine:
    ENV_FAMILY = "sokoban-singleplayer"

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.room_fixed: list[list[int]] = []
        self.room_state: list[list[int]] = []
        self.player = (0, 0)
        self.boxes: set[tuple[int, int]] = set()
        self.goals: set[tuple[int, int]] = set()
        self.public = PublicState([], (0, 0), [], 0)
        self.private = PrivateState("", "", "", 0, "")
        self.nev = NevLog()
        self._monty_scorer = None

    def reset(self, resolved_task: ResolvedTask) -> SimSnapshot:
        self.resolved = resolved_task
        self.room_fixed = [list(row) for row in resolved_task.room_fixed]
        self.player = resolved_task.player
        self.boxes = set(resolved_task.boxes)
        self.goals = set(resolved_task.goals)
        self.room_state = self._compose_room_state()
        self.public = self._public_state()
        episode_id = episode_id_for_task(resolved_task.task_id, resolved_task.seed, resolved_task.config_hash)
        self.private = PrivateState(
            episode_id=episode_id,
            task_id=resolved_task.task_id,
            puzzle_id=resolved_task.puzzle_id,
            seed=resolved_task.seed,
            config_hash=resolved_task.config_hash,
        )
        self.nev = NevLog()
        self._monty_scorer = load_monty_scorer(resolved_task.monty_reward or None)
        self._append_nev(
            kind=EventKind.TASK_RESOLVED,
            message=f"TaskResolved({resolved_task.puzzle_id},{resolved_task.config_hash})",
            payload={"resolved": resolved_task.to_dict()},
        )
        return self.snapshot()

    def reset_from_task(self, task: dict[str, Any], seed_override: int | None = None) -> SimSnapshot:
        return self.reset(resolve_task(task, seed_override=seed_override))

    def step(self, action: str) -> tuple[SimSnapshot, EventRecord | None]:
        action = str(action).lower().strip()
        if action not in DIRS:
            return self._blocked(action, "unknown_action")
        if self.private.terminated or self.private.truncated:
            return self._blocked(action, "terminal")

        prev_public = self._public_state()
        prev_on_targets = prev_public.boxes_on_target
        dr, dc = DIRS[action]
        pr, pc = self.player
        nr, nc = pr + dr, pc + dc
        reward = self._reward("step")

        if self._is_wall(nr, nc):
            return self._blocked(action, "wall", reward)

        pushed = False
        if (nr, nc) in self.boxes:
            br, bc = nr + dr, nc + dc
            if self._is_wall(br, bc) or (br, bc) in self.boxes:
                return self._blocked(action, "box_blocked", reward)
            self.boxes.remove((nr, nc))
            self.boxes.add((br, bc))
            pushed = True
            reward += self._reward("push")

        self.player = (nr, nc)
        self.private.step_index += 1
        self.room_state = self._compose_room_state()
        self.public = self._public_state()
        self.private.reward_last = reward
        self.private.total_reward += reward

        action_event = self._append_nev(
            kind=EventKind.ACTION_APPLIED,
            message=f"ActionApplied({action},step={self.private.step_index})",
            action=action,
            transition=self.public.diff(prev_public),
            payload={"action": action, "pushed": pushed},
        )
        if pushed:
            self._append_nev(
                kind=EventKind.PUSH_APPLIED,
                message=f"PushApplied({action},boxes_on_target={self.public.boxes_on_target})",
                action=action,
                payload={"boxes": [list(pos) for pos in sorted(self.boxes)]},
            )
            self._unlock("first_push")

        if self.public.boxes_on_target > prev_on_targets:
            reward = self._reward("box_on_target")
            self.private.reward_last += reward
            self.private.total_reward += reward
            self._append_nev(
                kind=EventKind.BOX_ON_TARGET,
                message=f"BoxOnTarget({self.public.boxes_on_target}/{len(self.goals)})",
                payload={"boxes_on_target": self.public.boxes_on_target, "goals": len(self.goals)},
            )
            self._unlock("first_box_on_target")

        if self.private.reward_last:
            self._append_nev(
                kind=EventKind.REWARD_DELTA,
                message=f"RewardDelta({self.private.reward_last:.2f},total={self.private.total_reward:.2f})",
                payload={"delta": self.private.reward_last, "total": self.private.total_reward},
            )

        monty_delta = self._monty_transition_reward(
            before_public=prev_public,
            after_public=self.public,
            pushed=pushed,
            event="level_complete" if self._is_solved() else "step",
        )
        if monty_delta:
            self.private.reward_last = monty_delta
            self.private.total_reward += monty_delta
            self._append_nev(
                kind=EventKind.REWARD_DELTA,
                message=f"RewardDelta({monty_delta:.2f},total={self.private.total_reward:.2f},source=monty)",
                payload={"delta": monty_delta, "total": self.private.total_reward, "source": "monty"},
            )

        if self._is_solved():
            reward = self._reward("goal")
            self.private.reward_last += reward
            self.private.total_reward += reward
            self.private.terminated = True
            self.public.done = True
            self._append_nev(
                kind=EventKind.LEVEL_COMPLETE,
                message=f"LevelComplete({self.private.step_index})",
                payload={"steps": self.private.step_index},
            )
            self._unlock("level_complete")
            self._append_nev(
                kind=EventKind.TERMINAL,
                message="Terminal(success)",
                payload={"reason": "success"},
            )
        elif self.resolved and self.private.step_index >= self.resolved.max_steps:
            self.private.truncated = True
            self.public.done = True
            self._append_nev(
                kind=EventKind.EPISODE_TRUNCATED,
                message=f"EpisodeTruncated(max_steps={self.resolved.max_steps})",
                payload={"max_steps": self.resolved.max_steps},
            )
            self._append_nev(
                kind=EventKind.TERMINAL,
                message="Terminal(truncated)",
                payload={"reason": "truncated"},
            )

        return self.snapshot(), action_event

    def checkpoint_bytes(self) -> bytes:
        return encode_checkpoint(
            env_family=self.ENV_FAMILY,
            episode_id=self.private.episode_id,
            step_index=self.private.step_index,
            nev_cursor=self.nev.cursor(),
            config_hash=self.private.config_hash,
            sim={
                "resolved": self.resolved.to_dict() if self.resolved else None,
                "room_fixed": self.room_fixed,
                "player": list(self.player),
                "boxes": [list(pos) for pos in sorted(self.boxes)],
                "goals": [list(pos) for pos in sorted(self.goals)],
                "private": self.private.to_dict(),
            },
            nev_events=self.nev.export(),
        )

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = decode_checkpoint(blob)
        if payload["env_family"] != self.ENV_FAMILY:
            raise ValueError(f"wrong env_family: {payload['env_family']}")
        sim = payload["sim"]
        resolved_doc = sim.get("resolved")
        self.resolved = _resolved_from_dict(resolved_doc) if resolved_doc else None
        self.room_fixed = [list(row) for row in sim["room_fixed"]]
        self.player = tuple(sim["player"])
        self.boxes = {tuple(pos) for pos in sim["boxes"]}
        self.goals = {tuple(pos) for pos in sim["goals"]}
        priv = sim["private"]
        self.private = PrivateState(
            episode_id=payload["episode_id"],
            task_id=priv["task_id"],
            puzzle_id=priv["puzzle_id"],
            seed=int(priv["seed"]),
            config_hash=payload["config_hash"],
            step_index=int(payload["step_index"]),
            reward_last=float(priv.get("reward_last", 0.0)),
            total_reward=float(priv.get("total_reward", 0.0)),
            terminated=bool(priv.get("terminated", False)),
            truncated=bool(priv.get("truncated", False)),
            achievements=set(priv.get("achievements", [])),
        )
        self.room_state = self._compose_room_state()
        self.public = self._public_state()
        self.nev = NevLog()
        self.nev.import_events(payload.get("nev_events", []))
        return self.nev.cursor()

    def symbolic_readout(self) -> dict[str, Any]:
        from observations import project_readout

        return project_readout(self)

    def valid_actions(self) -> list[str]:
        if self.private.terminated or self.private.truncated:
            return []
        return list(DIRS)

    def snapshot(self) -> SimSnapshot:
        return SimSnapshot(public=self._public_state(), private=self.private, nev_events=self.nev.export())

    def clone_for_sim(self) -> "SokobanEngine":
        clone = SokobanEngine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone

    def _blocked(self, action: str, reason: str, base_reward: float = 0.0) -> tuple[SimSnapshot, EventRecord | None]:
        self.private.step_index += 1
        severity = EventSeverity.ERROR if self.resolved and self.resolved.errors.get("mode") == "strict" else EventSeverity.WARN
        self.private.reward_last = base_reward + self._reward("blocked")
        self.private.total_reward += self.private.reward_last
        record = self._append_nev(
            kind=EventKind.PUSH_BLOCKED,
            severity=severity,
            message=f"PushBlocked({action},{reason},step={self.private.step_index})",
            action=action,
            payload={"reason": reason},
        )
        if severity == EventSeverity.ERROR:
            self._append_nev(
                kind=EventKind.RULE_VIOLATION,
                severity=severity,
                message=f"RuleViolation({reason})",
                action=action,
                payload={"reason": reason},
            )
        if self.private.reward_last:
            self._append_nev(
                kind=EventKind.REWARD_DELTA,
                message=f"RewardDelta({self.private.reward_last:.2f},total={self.private.total_reward:.2f})",
                payload={"delta": self.private.reward_last, "total": self.private.total_reward},
            )
        if self.resolved and self.private.step_index >= self.resolved.max_steps:
            self.private.truncated = True
            self.public.done = True
            self._append_nev(
                kind=EventKind.EPISODE_TRUNCATED,
                message=f"EpisodeTruncated(max_steps={self.resolved.max_steps})",
                payload={"max_steps": self.resolved.max_steps},
            )
            self._append_nev(kind=EventKind.TERMINAL, message="Terminal(truncated)", payload={"reason": "truncated"})
        return self.snapshot(), record

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

    def _public_state(self) -> PublicState:
        return PublicState(
            room_state=[list(row) for row in self.room_state],
            player=self.player,
            boxes=sorted(self.boxes),
            boxes_on_target=sum(1 for box in self.boxes if box in self.goals),
            done=self.private.terminated or self.private.truncated,
        )

    def _compose_room_state(self) -> list[list[int]]:
        state: list[list[int]] = []
        for r, fixed_row in enumerate(self.room_fixed):
            row: list[int] = []
            for c, fixed in enumerate(fixed_row):
                pos = (r, c)
                if fixed == WALL:
                    row.append(WALL)
                elif pos == self.player:
                    row.append(PLAYER_ON_TARGET if fixed == TARGET else PLAYER)
                elif pos in self.boxes:
                    row.append(BOX_ON_TARGET if fixed == TARGET else BOX)
                else:
                    row.append(TARGET if fixed == TARGET else FLOOR)
            state.append(row)
        return state

    def _is_wall(self, r: int, c: int) -> bool:
        return r < 0 or c < 0 or r >= len(self.room_fixed) or c >= len(self.room_fixed[0]) or self.room_fixed[r][c] == WALL

    def _is_solved(self) -> bool:
        return all(goal in self.boxes for goal in self.goals)

    def _reward(self, key: str) -> float:
        if not self.resolved:
            return 0.0
        return float(self.resolved.rewards.get(key, 0.0))

    def _monty_transition_reward(
        self,
        *,
        before_public: PublicState,
        after_public: PublicState,
        pushed: bool,
        event: str,
    ) -> float:
        if self._monty_scorer is None or self.resolved is None:
            return 0.0
        return float(
            self._monty_scorer(
                spec=self.resolved.monty_reward,
                before_public=before_public.to_dict(),
                after_public=after_public.to_dict(),
                pushed=pushed,
                event=event,
            )
        )

    def _unlock(self, name: str) -> None:
        if name in self.private.achievements:
            return
        self.private.achievements.add(name)
        self._append_nev(
            kind=EventKind.ACHIEVEMENT_UNLOCKED,
            message=f"AchievementUnlocked({name})",
            payload={"achievement": name},
        )


def _resolved_from_dict(doc: dict[str, Any]) -> ResolvedTask:
    return ResolvedTask(
        task_id=doc["task_id"],
        puzzle_id=doc["puzzle_id"],
        seed=int(doc["seed"]),
        config_hash=doc["config_hash"],
        room_fixed=[list(row) for row in doc["room_fixed"]],
        room_state=[list(row) for row in doc["room_state"]],
        goals=[tuple(pos) for pos in doc["goals"]],
        boxes=[tuple(pos) for pos in doc["boxes"]],
        player=tuple(doc["player"]),
        max_steps=int(doc["max_steps"]),
        rewards={key: float(value) for key, value in doc["rewards"].items()},
        errors=dict(doc["errors"]),
        curriculum=dict(doc.get("curriculum", {})),
        monty_reward=dict(doc.get("monty_reward", {})),
        resolved_json=dict(doc.get("resolved_json", {})),
    )
