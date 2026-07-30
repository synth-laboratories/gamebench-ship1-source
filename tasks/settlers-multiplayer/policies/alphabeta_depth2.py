"""A small, deterministic AlphaBeta-depth-2 spirit baseline for DEO."""
from __future__ import annotations

from math import inf
from typing import Any

from gold_python.engine import DICE


class AlphaBetaDepth2Baseline:
    """Pruned depth-2 score search, intentionally cheap enough for local CI.

    The reported DEO policy uses two alternating plies.  Candidate pruning is
    an implementation descope only; it does not depend on any external game
    runtime or training loop.
    """
    name = "alphabeta_depth2_spirit"

    def actions(self, env: Any) -> list[dict[str, Any]]:
        state = env._require_state(); actor = env.current_agent(); player = env._player(actor)
        if state.robber_pending or DICE[(state.seed + state.turn) % len(DICE)] == 7:
            return [{"kind": "move_robber", "tile": next(tile for tile in range(12) if tile != state.robber_tile)}]
        candidates: list[dict[str, Any]] = [{"kind": "end_turn"}]
        occupied = {road for other in state.players for road in other.roads}
        endpoints = lambda edge: {edge, (edge + 1) % 24}
        own_vertices = set(player.settlements + player.cities)
        if player.resources["wood"] >= 1 and player.resources["brick"] >= 1:
            for edge in range(24):
                if edge in occupied:
                    continue
                edge_vertices = endpoints(edge)
                connected = bool(edge_vertices & own_vertices)
                connected = connected or any(edge_vertices & endpoints(road) for road in player.roads)
                if connected:
                    candidates.append({"kind": "build_road", "edge": edge})
        # Keep depth two but use a compact, legal, deterministic road frontier.
        return candidates[:6]

    def evaluate(self, env: Any, root: str) -> float:
        state = env._require_state(); own = env.victory_points(root)
        rivals = max(env.victory_points(player.agent_id) for player in state.players if player.agent_id != root)
        player = env._player(root)
        return 100.0 * (own - rivals) + 2.0 * len(player.roads) + sum(player.resources.values()) * 0.05

    def choose_action(self, env: Any) -> dict[str, Any]:
        root = env.current_agent(); best_action = {"kind": "end_turn"}; best_score = -inf
        for action in self.actions(env):
            child = env.__class__(max_turns=env.max_turns); child.restore(env.checkpoint()); child.step(action)
            if child._require_state().terminated:
                score = self.evaluate(child, root)
            else:
                reply_actions = self.actions(child)
                score = min(self._after(child, reply, root) for reply in reply_actions) if reply_actions else self.evaluate(child, root)
            if score > best_score: best_score, best_action = score, action
        return best_action

    def _after(self, env: Any, action: dict[str, Any], root: str) -> float:
        child = env.__class__(max_turns=env.max_turns); child.restore(env.checkpoint()); child.step(action)
        return self.evaluate(child, root)
