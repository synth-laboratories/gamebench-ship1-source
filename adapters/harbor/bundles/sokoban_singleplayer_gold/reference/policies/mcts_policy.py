"""Pure-Python MCTS code policy for Sokoban."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ChildStats:
    action: str
    visits: int = 0
    value_sum: float = 0.0

    @property
    def q(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "visits": self.visits, "q": round(self.q, 4), "prior": 0.25}


@dataclass
class RootStats:
    children: dict[str, ChildStats] = field(default_factory=dict)
    visits: int = 0


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    stream_callback: Callable[[dict[str, Any]], None] | None = None,
    seed: int = 0,
    num_simulations: int = 200,
    rollout_depth: int = 24,
    stream_every: int = 50,
    **_: Any,
) -> dict[str, Any]:
    if engine is None:
        action = valid_actions[0] if valid_actions else "up"
        return {"actions": [action], "policy_reason": "mcts unavailable: no engine", "mcts_debug": {"root_children": [], "chosen": action}}
    if not valid_actions:
        return {"actions": [], "policy_reason": "mcts: terminal", "mcts_debug": {"root_children": [], "chosen": None}}

    rng = random.Random(seed + int(session.get("ply", 0)))
    sim_engine = engine.clone_for_sim() if hasattr(engine, "clone_for_sim") else engine
    root_blob = engine.checkpoint_bytes()
    root = RootStats(children={action: ChildStats(action) for action in valid_actions})
    root_score = _score(engine)

    for sim in range(num_simulations):
        sim_engine.restore_checkpoint(root_blob)
        child = _select(root, rng)
        sim_engine.step(child.action)
        reward = _rollout(sim_engine, root_score=root_score, rng=rng, depth=rollout_depth)
        child.visits += 1
        child.value_sum += reward
        root.visits += 1
        if stream_callback and (sim + 1) % max(1, stream_every) == 0:
            stream_callback(
                {
                    "type": "mcts_stats",
                    "simulations_done": sim + 1,
                    "simulations_budget": num_simulations,
                    "root_children": _children_debug(root),
                }
            )

    sim_engine.restore_checkpoint(root_blob)
    best = max(root.children.values(), key=lambda child: (child.visits, child.q, child.action))
    debug = {"simulations": num_simulations, "root_children": _children_debug(root), "chosen": best.action}
    return {
        "actions": [best.action],
        "policy_reason": f"mcts: {best.action} N={num_simulations} Q={best.q:.3f}",
        "mcts_debug": debug,
    }


def _select(root: RootStats, rng: random.Random) -> ChildStats:
    unvisited = [child for child in root.children.values() if child.visits == 0]
    if unvisited:
        return rng.choice(unvisited)
    log_parent = math.log(max(root.visits, 1))
    return max(
        root.children.values(),
        key=lambda child: child.q + 1.414 * math.sqrt(log_parent / max(child.visits, 1)),
    )


def _rollout(engine: Any, *, root_score: float, rng: random.Random, depth: int) -> float:
    for step_count in range(depth):
        if getattr(engine.private, "terminated", False):
            return 10.0 + _score(engine) - step_count * 0.25 + float(getattr(engine.private, "total_reward", 0.0))
        if getattr(engine.private, "truncated", False):
            break
        actions = engine.valid_actions()
        if not actions:
            break
        engine.step(_heuristic_action(engine, actions, rng))
    return _score(engine) - root_score - depth * 0.05 + float(getattr(engine.private, "total_reward", 0.0))


def _heuristic_action(engine: Any, actions: list[str], rng: random.Random) -> str:
    best_action = rng.choice(actions)
    best_score = -1e9
    blob = engine.checkpoint_bytes()
    for action in actions:
        engine.restore_checkpoint(blob)
        engine.step(action)
        score = _score(engine)
        if score > best_score:
            best_action = action
            best_score = score
    engine.restore_checkpoint(blob)
    return best_action


def _score(engine: Any) -> float:
    readout = engine.symbolic_readout()
    public = readout["public"]
    boxes = [tuple(pos) for pos in public["boxes"]]
    player = tuple(public["player"])
    room_state = public["room_state"]
    goals = [(r, c) for r, row in enumerate(room_state) for c, cell in enumerate(row) if cell in (2, 3, 6)]
    on_target = int(public.get("boxes_on_target", 0))
    distance = 0
    for box in boxes:
        if goals:
            distance += min(abs(box[0] - g[0]) + abs(box[1] - g[1]) for g in goals)
        distance += abs(player[0] - box[0]) + abs(player[1] - box[1]) * 0.1
    return on_target * 5.0 - distance * 0.1


def _children_debug(root: RootStats) -> list[dict[str, Any]]:
    return [root.children[action].to_dict() for action in sorted(root.children)]
