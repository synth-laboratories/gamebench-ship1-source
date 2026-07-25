"""Python gold engine for FrogsGame."""

from __future__ import annotations

import copy
import json
from typing import Any

from core.nev import NevLog
from scoring import binary_success_score, validate_frogs
from state import Position, PrivateState, PublicState
from task_resolve import ResolvedTask


class FrogsEngine:
    ENV_FAMILY = "frogs-singleplayer"

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.public = PublicState(board=[])
        self.private = PrivateState()
        self.nev = NevLog()

    def reset(self, resolved: ResolvedTask) -> None:
        self.resolved = resolved
        self.public = PublicState(board=copy.deepcopy(resolved.board))
        max_tool_calls = int(resolved.rules.get("overrides", {}).get("max_tool_calls", 200))
        self.private = PrivateState(config_hash=resolved.config_hash, episode_id=resolved.episode_id, max_tool_calls=max_tool_calls)
        self.nev = NevLog()
        self.nev.append(
            step_index=0,
            episode_id=resolved.episode_id,
            kind="state_transition",
            transition="reset",
            message=f"TaskResolved({resolved.task_id},{resolved.config_hash})",
            payload={"task": resolved.to_dict()},
        )

    def step(self, action: dict[str, Any] | str) -> dict[str, Any]:
        if self.resolved is None:
            raise RuntimeError("engine must be reset before step")
        parsed = parse_action(action)
        self.private.step_index += 1
        if self.private.terminated or self.private.truncated:
            self._violation("terminal", "episode already ended", parsed)
            return self.symbolic_readout()
        kind = parsed["kind"]
        if kind == "place_frog":
            self._place(int(parsed["row"]), int(parsed["col"]), parsed)
        elif kind == "remove_frog":
            self._remove(int(parsed["row"]), int(parsed["col"]), parsed)
        elif kind == "submit":
            self._submit(parsed)
        elif kind == "reset":
            self._soft_reset(parsed)
        else:
            self._violation("unknown_action", f"unknown action {kind}", parsed)

        if self.private.step_index >= self.resolved.max_steps and not self.private.terminated:
            self.private.truncated = True
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="terminal",
                action=parsed,
                transition="truncate",
                message="Terminal(truncated)",
                payload={"max_steps": self.resolved.max_steps},
            )
        return self.symbolic_readout()

    def execute_tool_call(self, tool_name: str, args: dict[str, Any] | None = None) -> Any:
        args = args or {}
        if tool_name == "place_frog":
            return self.tool_place_frog(int(args.get("row", -1)), int(args.get("col", -1)))
        if tool_name == "remove_frog":
            return self.tool_remove_frog(int(args.get("row", -1)), int(args.get("col", -1)))
        if tool_name == "get_state":
            return self.tool_get_state()
        if tool_name == "check_violations":
            return self.tool_check_violations()
        if tool_name == "submit":
            return self.tool_submit()
        if tool_name == "reset":
            return self.tool_reset()
        return {"error": f"Unknown tool: '{tool_name}'. Available: ['place_frog', 'remove_frog', 'get_state', 'check_violations', 'submit', 'reset']"}

    def tool_place_frog(self, row: int, col: int) -> str:
        assert self.resolved is not None
        self.private.tool_call_count += 1
        if not (0 <= row < self.resolved.n and 0 <= col < self.resolved.n):
            return f"Error: ({row},{col}) is out of bounds for {self.resolved.n}x{self.resolved.n} board."
        if (row, col) in self.public.frogs:
            return f"Error: A frog is already at ({row},{col})."
        candidate = [*self.public.frogs, (row, col)]
        violations = self._original_violation_strings(candidate)
        if violations:
            return f"Error: Placement at ({row},{col}) violates rules: " + "; ".join(violations)
        self.public.frogs = sorted(candidate)
        self.public.violations = []
        return "OK"

    def tool_remove_frog(self, row: int, col: int) -> str:
        self.private.tool_call_count += 1
        if (row, col) not in self.public.frogs:
            return f"Error: No frog at ({row},{col})."
        self.public.frogs = [cell for cell in self.public.frogs if cell != (row, col)]
        return "OK"

    def tool_get_state(self) -> dict[str, Any]:
        assert self.resolved is not None
        self.private.tool_call_count += 1
        return {
            "board": [row[:] for row in self.resolved.board],
            "frogs": sorted(self.public.frogs),
            "n": self.resolved.n,
            "colors": self.resolved.colors[:],
        }

    def tool_check_violations(self) -> dict[str, Any]:
        self.private.tool_call_count += 1
        violations = self._original_violation_strings(self.public.frogs)
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "n_frogs_placed": len(self.public.frogs),
        }

    def tool_submit(self) -> dict[str, Any]:
        assert self.resolved is not None
        self.private.tool_call_count += 1
        self.public.submitted = True
        violations = self._original_violation_strings(self.public.frogs)
        if len(self.public.frogs) != self.resolved.n:
            violations.append(f"Completeness: expected {self.resolved.n} frogs, placed {len(self.public.frogs)}.")
        correct = len(violations) == 0
        self.private.total_reward = 1.0 if correct else 0.0
        self.private.terminated = True
        return {
            "correct": correct,
            "violations": violations,
            "reward": 1.0 if correct else 0.0,
        }

    def tool_reset(self) -> None:
        self.private.tool_call_count += 1
        self.public.frogs = []
        self.public.submitted = False
        self.public.violations = []
        self.private.terminated = False
        self.private.truncated = False
        self.private.total_reward = 0.0
        return None

    def exceeded_tool_calls(self) -> bool:
        return self.private.tool_call_count >= self.private.max_tool_calls

    def _original_violation_strings(self, frogs: list[Position]) -> list[str]:
        assert self.resolved is not None
        violations: list[str] = []
        frog_list = sorted(frogs)
        rows = [row for row, _ in frog_list]
        for row in sorted(set(rows)):
            if rows.count(row) > 1:
                violations.append(f"Row uniqueness: multiple frogs in row {row}.")
        cols = [col for _, col in frog_list]
        for col in sorted(set(cols)):
            if cols.count(col) > 1:
                violations.append(f"Column uniqueness: multiple frogs in column {col}.")
        for index, first in enumerate(frog_list):
            for second in frog_list[index + 1 :]:
                if abs(first[0] - second[0]) <= 1 and abs(first[1] - second[1]) <= 1:
                    violations.append(f"Adjacency: frogs at ({first[0]},{first[1]}) and ({second[0]},{second[1]}) are adjacent.")
        color_frogs: dict[str, list[Position]] = {}
        for row, col in frog_list:
            color = self.resolved.board[row][col]
            color_frogs.setdefault(color, []).append((row, col))
        for color in sorted(color_frogs):
            if len(color_frogs[color]) > 1:
                violations.append(f"Color uniqueness: multiple frogs in color '{color}' at {color_frogs[color]}.")
        return violations

    def _place(self, row: int, col: int, action: dict[str, Any]) -> None:
        assert self.resolved is not None
        if not 0 <= row < self.resolved.n or not 0 <= col < self.resolved.n:
            self._violation("out_of_bounds", f"cannot place frog outside board at ({row},{col})", action)
            return
        if (row, col) in self.public.frogs:
            self._violation("duplicate_cell", f"frog already placed at ({row},{col})", action)
            return
        candidate = [*self.public.frogs, (row, col)]
        violations = validate_frogs(self.resolved.board, candidate, require_complete=False)
        if violations:
            self.public.violations = violations
            self._violation(violations[0].code, violations[0].message, action, [violation.to_dict() for violation in violations])
            return
        self.public.frogs = sorted(candidate)
        self.public.violations = []
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="action_applied",
            action=action,
            transition="place",
            message=f"FrogPlaced({row},{col})",
            payload={"cell": [row, col], "color": self.resolved.board[row][col]},
        )

    def _remove(self, row: int, col: int, action: dict[str, Any]) -> None:
        assert self.resolved is not None
        if (row, col) not in self.public.frogs:
            self._violation("missing_frog", f"no frog at ({row},{col})", action)
            return
        self.public.frogs = [cell for cell in self.public.frogs if cell != (row, col)]
        self.public.violations = validate_frogs(self.resolved.board, self.public.frogs, require_complete=False)
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="action_applied",
            action=action,
            transition="remove",
            message=f"FrogRemoved({row},{col})",
            payload={"cell": [row, col]},
        )

    def _submit(self, action: dict[str, Any]) -> None:
        assert self.resolved is not None
        self.public.submitted = True
        self.public.violations = validate_frogs(self.resolved.board, self.public.frogs, require_complete=True)
        reward = binary_success_score(self.resolved.board, self.public.frogs)
        self.private.total_reward += reward
        self.private.terminated = True
        correct = reward == 1.0
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            action=action,
            transition="submit",
            message=f"SubmissionChecked(correct={str(correct).lower()},reward={reward:.1f})",
            payload={"violations": [violation.to_dict() for violation in self.public.violations]},
        )
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="resource_delta",
            action=action,
            transition="reward",
            message=f"RewardDelta({reward:.2f},total={self.private.total_reward:.2f})",
            payload={"reward": reward, "total_reward": self.private.total_reward},
        )
        terminal = "success" if correct else "failure"
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="terminal",
            action=action,
            transition=terminal,
            message=f"Terminal({terminal})",
            payload={"correct": correct},
        )

    def _soft_reset(self, action: dict[str, Any]) -> None:
        assert self.resolved is not None
        self.public.frogs = []
        self.public.submitted = False
        self.public.violations = []
        self.private.total_reward = 0.0
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            action=action,
            transition="reset_board",
            message="BoardReset()",
        )

    def _violation(
        self,
        code: str,
        message: str,
        action: dict[str, Any],
        violations: list[dict[str, Any]] | None = None,
    ) -> None:
        assert self.resolved is not None
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="rule_violation",
            action=action,
            transition="reject",
            severity="warn",
            message=f"RuleViolation({code})",
            payload={"code": code, "message": message, "violations": violations or []},
        )

    def symbolic_readout(self) -> dict[str, Any]:
        assert self.resolved is not None
        rows = []
        frogs = set(self.public.frogs)
        for row_index, row in enumerate(self.resolved.board):
            cells = []
            for col_index, color in enumerate(row):
                marker = "F" if (row_index, col_index) in frogs else "."
                cells.append(f"{color}:{marker}")
            rows.append(" ".join(cells))
        payload = {
            "schema": "gamebench.frogs.readout.v1",
            "env_family": self.ENV_FAMILY,
            "task_id": self.resolved.task_id,
            "public": self.public.to_dict(),
            "private": self.private.to_dict(),
            "ascii": "\n".join(rows),
            "grid_hash": self.resolved.config_hash,
            "nev_cursor": self.nev.cursor(),
        }
        return payload

    def valid_actions(self) -> list[dict[str, Any]]:
        assert self.resolved is not None
        if self.private.terminated or self.private.truncated:
            return []
        actions: list[dict[str, Any]] = [{"kind": "submit"}, {"kind": "reset"}]
        frogs = set(self.public.frogs)
        for row in range(self.resolved.n):
            for col in range(self.resolved.n):
                if (row, col) in frogs:
                    actions.append({"kind": "remove_frog", "row": row, "col": col})
                else:
                    candidate = [*self.public.frogs, (row, col)]
                    if not validate_frogs(self.resolved.board, candidate, require_complete=False):
                        actions.append({"kind": "place_frog", "row": row, "col": col})
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
                "public": self.public.to_dict(),
                "private": self.private.to_dict(),
                "events": self.nev.export(),
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def restore_checkpoint(self, blob: bytes) -> int:
        from task_resolve import ResolvedTask

        payload = json.loads(blob.decode("utf-8"))
        sim = payload["sim"]
        resolved_data = sim["resolved"]
        self.resolved = ResolvedTask(
            task_id=resolved_data["task_id"],
            seed=int(resolved_data["seed"]),
            board=[[str(cell) for cell in row] for row in resolved_data["board"]],
            rules=dict(resolved_data["rules"]),
            max_steps=int(resolved_data["max_steps"]),
            config_hash=str(resolved_data["config_hash"]),
            episode_id=str(resolved_data["episode_id"]),
        )
        public = sim["public"]
        private = sim["private"]
        self.public = PublicState(
            board=[[str(cell) for cell in row] for row in public["board"]],
            frogs=[(int(row), int(col)) for row, col in public["frogs"]],
            submitted=bool(public["submitted"]),
            violations=validate_frogs(self.resolved.board, [(int(row), int(col)) for row, col in public["frogs"]], require_complete=bool(public["submitted"])),
        )
        self.private = PrivateState(
            step_index=int(private["step_index"]),
            tool_call_count=int(private.get("tool_call_count", 0)),
            max_tool_calls=int(private.get("max_tool_calls", 200)),
            total_reward=float(private["total_reward"]),
            terminated=bool(private["terminated"]),
            truncated=bool(private["truncated"]),
            config_hash=str(private["config_hash"]),
            episode_id=str(private["episode_id"]),
        )
        self.nev = NevLog.from_export(sim["events"])
        return self.nev.cursor()

    def clone_for_sim(self) -> "FrogsEngine":
        clone = FrogsEngine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone


def parse_action(action: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(action, dict):
        parsed = dict(action)
    else:
        parsed = json.loads(action) if action.strip().startswith("{") else {"kind": action}
    if "kind" not in parsed and "type" in parsed:
        parsed["kind"] = parsed["type"]
    if "kind" not in parsed:
        raise ValueError("frogs action requires kind")
    return parsed
