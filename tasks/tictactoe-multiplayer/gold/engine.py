"""Multiplayer Tic-Tac-Toe engine — JaxMARL/Overcooked joint-step MARL contract."""

from __future__ import annotations

import hashlib
from typing import Any

from gold.board import AGENT_IDS, AGENT_MARKS, MARK_TO_AGENT, winner_for
from gold.core.checkpoint import CHECKPOINT_SCHEMA, decode_checkpoint, encode_checkpoint
from gold.core.nev import EventKind, EventRecord, EventSeverity, NevLog
from gold.state import PrivateState, PublicState, SimSnapshot

WAIT_ACTION = {"kind": "wait"}


def config_hash(scenario_id: str, seed: int) -> str:
    digest = hashlib.sha256(f"tictactoe-multiplayer:{scenario_id}:{seed}".encode()).hexdigest()
    return f"sha256:{digest}"


def episode_id_for_task(scenario_id: str, seed: int, task_id: str | None = None) -> str:
    key = task_id or scenario_id
    digest = hashlib.sha256(f"gamebench.tictactoe-multiplayer.episode:{key}:{seed}".encode()).hexdigest()
    return digest[:32]


def episode_id_from_task(task: dict[str, Any]) -> str:
    if task.get("episode_id"):
        return str(task["episode_id"])
    scenario_id = str(task["scenario_id"])
    seed = int(task.get("seed", 0))
    task_id = str(task.get("task_id", scenario_id))
    return episode_id_for_task(scenario_id, seed, task_id)


def _zero_rewards() -> dict[str, float]:
    return {"agent_0": 0.0, "agent_1": 0.0}


class TicTacToeMultiplayerEngine:
    """Layer 1 engine — joint dict step, per-agent rewards/dones."""

    ENV_FAMILY = "tictactoe-multiplayer"
    AGENT_IDS = AGENT_IDS

    def __init__(self) -> None:
        self.public = PublicState(board=[""] * 9, current_agent="agent_0", winner=None)
        self.private = PrivateState(
            episode_id="",
            scenario_id="",
            seed=0,
            step_index=0,
            ply=0,
        )
        self.nev = NevLog()

    def reset(
        self,
        scenario_id: str,
        seed: int = 0,
        episode_id: str | None = None,
        task_id: str | None = None,
    ) -> SimSnapshot:
        self.public = PublicState(board=[""] * 9, current_agent="agent_0", winner=None)
        resolved_episode_id = episode_id or episode_id_for_task(scenario_id, seed, task_id)
        self.private = PrivateState(
            episode_id=resolved_episode_id,
            scenario_id=scenario_id,
            seed=seed,
            step_index=0,
            ply=0,
        )
        self.nev = NevLog()
        self._append_nev(
            kind=EventKind.STATE_TRANSITION,
            message=f"GameStarted({scenario_id})",
            payload={"scenario_id": scenario_id, "seed": seed},
        )
        self._append_nev(
            kind=EventKind.STATE_TRANSITION,
            message=f"JointTurn({self.public.current_agent})",
            payload={"current_agent": self.public.current_agent},
        )
        return self.snapshot()

    def step(self, joint_action: dict[str, Any]) -> tuple[SimSnapshot, EventRecord | None]:
        if self.private.terminated or self.private.truncated:
            violation = self._append_nev(
                kind=EventKind.RULE_VIOLATION,
                severity=EventSeverity.ERROR,
                message="game is already over",
                action=joint_action,
                payload={"reason": "terminal"},
            )
            return self.snapshot(), violation

        current = self.public.current_agent
        acting_action = dict(joint_action.get(current, WAIT_ACTION))
        for agent_id in AGENT_IDS:
            other_action = dict(joint_action.get(agent_id, WAIT_ACTION))
            if agent_id != current and other_action.get("kind") != "wait":
                violation = self._append_nev(
                    kind=EventKind.RULE_VIOLATION,
                    severity=EventSeverity.ERROR,
                    message=f"only {current} may act on this joint step",
                    action=joint_action,
                    payload={"current_agent": current, "offending_agent": agent_id},
                )
                return self.snapshot(), violation

        if acting_action.get("kind") == "wait":
            violation = self._append_nev(
                kind=EventKind.RULE_VIOLATION,
                severity=EventSeverity.ERROR,
                message=f"expected {current} to place",
                action=joint_action,
                payload={"current_agent": current},
            )
            return self.snapshot(), violation

        mark = AGENT_MARKS[current]
        position = int(acting_action.get("position", acting_action.get("cell", -1)))
        if position < 0 or position >= 9:
            violation = self._append_nev(
                kind=EventKind.RULE_VIOLATION,
                severity=EventSeverity.ERROR,
                message="position out of range",
                action=joint_action,
                payload={"position": position},
            )
            return self.snapshot(), violation
        if self.public.board[position]:
            violation = self._append_nev(
                kind=EventKind.RULE_VIOLATION,
                severity=EventSeverity.ERROR,
                message="position already occupied",
                action=joint_action,
                payload={"position": position, "cell": self.public.board[position]},
            )
            return self.snapshot(), violation

        prev_public = PublicState(
            board=list(self.public.board),
            current_agent=self.public.current_agent,
            winner=self.public.winner,
        )
        self.public.board[position] = mark
        self.private.ply += 1
        self.private.step_index += 1

        record = self._append_nev(
            kind=EventKind.ACTION_APPLIED,
            message=f"MoveApplied({current},{position})",
            action={current: acting_action},
            payload={"agent_id": current, "mark": mark, "position": position},
            transition=self.public.diff(prev_public),
        )

        winner_mark = winner_for(self.public.board)
        if winner_mark:
            winner_agent = MARK_TO_AGENT[winner_mark]
            self.public.winner = winner_agent
            self.private.terminated = True
            rewards = _zero_rewards()
            rewards[winner_agent] = 1.0
            self.private.reward_last = dict(rewards)
            for agent_id in AGENT_IDS:
                self.private.total_reward[agent_id] += rewards[agent_id]
            self._append_nev(
                kind=EventKind.TERMINAL,
                message=f"GameEnded({winner_agent},win)",
                payload={"winner": winner_agent, "reason": "win"},
            )
        elif all(cell for cell in self.public.board):
            self.public.winner = "draw"
            self.private.terminated = True
            self.private.reward_last = _zero_rewards()
            self._append_nev(
                kind=EventKind.TERMINAL,
                message="GameEnded(draw,draw)",
                payload={"winner": "draw", "reason": "draw"},
            )
        else:
            next_agent = AGENT_IDS[1] if current == AGENT_IDS[0] else AGENT_IDS[0]
            self.public.current_agent = next_agent
            self.private.reward_last = _zero_rewards()
            self._append_nev(
                kind=EventKind.STATE_TRANSITION,
                message=f"JointTurn({next_agent})",
                payload={"current_agent": next_agent},
            )

        return self.snapshot(), record

    def marl_step_return(self) -> tuple[dict[str, float], dict[str, bool], dict[str, Any]]:
        """JaxMARL-style per-agent rewards and dones after the latest step."""
        rewards = dict(self.private.reward_last)
        dones = {agent_id: self.private.terminated for agent_id in AGENT_IDS}
        dones["__all__"] = self.private.terminated
        info: dict[str, Any] = {"last_joint_event": self.nev.legacy_strings()[-1] if self.nev.cursor() else None}
        return rewards, dones, info

    def snapshot(self) -> SimSnapshot:
        return SimSnapshot(
            public=PublicState(
                board=list(self.public.board),
                current_agent=self.public.current_agent,
                winner=self.public.winner,
            ),
            private=PrivateState(
                episode_id=self.private.episode_id,
                scenario_id=self.private.scenario_id,
                seed=self.private.seed,
                step_index=self.private.step_index,
                ply=self.private.ply,
                reward_last=dict(self.private.reward_last),
                total_reward=dict(self.private.total_reward),
                terminated=self.private.terminated,
                truncated=self.private.truncated,
            ),
            nev_events=self.nev.export(),
        )

    def checkpoint_bytes(self) -> bytes:
        return encode_checkpoint(
            env_family=self.ENV_FAMILY,
            episode_id=self.private.episode_id,
            step_index=self.private.step_index,
            nev_cursor=self.nev.cursor(),
            config_hash=config_hash(self.private.scenario_id, self.private.seed),
            sim={
                "board": list(self.public.board),
                "current_agent": self.public.current_agent,
                "winner": self.public.winner,
                "scenario_id": self.private.scenario_id,
                "seed": self.private.seed,
                "ply": self.private.ply,
                "reward_last": dict(self.private.reward_last),
                "total_reward": dict(self.private.total_reward),
                "terminated": self.private.terminated,
                "truncated": self.private.truncated,
            },
            nev_events=self.nev.export(),
        )

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = decode_checkpoint(blob)
        if payload["env_family"] != self.ENV_FAMILY:
            raise ValueError(f"wrong env_family: {payload['env_family']}")
        sim = payload["sim"]
        self.public = PublicState(
            board=list(sim["board"]),
            current_agent=sim["current_agent"],
            winner=sim.get("winner"),
        )
        self.private = PrivateState(
            episode_id=payload["episode_id"],
            scenario_id=sim["scenario_id"],
            seed=int(sim["seed"]),
            step_index=int(payload["step_index"]),
            ply=int(sim["ply"]),
            reward_last=dict(sim.get("reward_last", _zero_rewards())),
            total_reward=dict(sim.get("total_reward", _zero_rewards())),
            terminated=bool(sim.get("terminated", False)),
            truncated=bool(sim.get("truncated", False)),
        )
        self.nev = NevLog()
        for event_dict in payload.get("nev_events", []):
            self.nev.append(
                EventRecord(
                    step_index=int(event_dict["step_index"]),
                    sim_tick=int(event_dict["sim_tick"]),
                    episode_id=str(event_dict["episode_id"]),
                    kind=EventKind(str(event_dict["kind"])),
                    severity=EventSeverity(str(event_dict["severity"])),
                    message=str(event_dict["message"]),
                    action=event_dict.get("action"),
                    transition=event_dict.get("transition"),
                    payload=dict(event_dict.get("payload") or {}),
                )
            )
        if self.nev.cursor() != int(payload["nev_cursor"]):
            raise ValueError(
                f"nev cursor mismatch: blob={payload['nev_cursor']} restored={self.nev.cursor()}"
            )
        return self.nev.cursor()

    def _append_nev(
        self,
        *,
        kind: EventKind,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        action: dict[str, Any] | None = None,
        transition: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> EventRecord:
        record = EventRecord(
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
        self.nev.append(record)
        return record
