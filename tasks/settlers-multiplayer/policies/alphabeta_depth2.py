"""A small, deterministic AlphaBeta-depth-2 spirit baseline for DEO."""
from __future__ import annotations

from math import inf
from typing import Any


class AlphaBetaDepth2Baseline:
    """Pruned depth-2 score search, intentionally cheap enough for local CI.

    The reported DEO policy uses two alternating plies.  Candidate pruning is
    an implementation descope only; it does not depend on any external game
    runtime or training loop.
    """
    name = "alphabeta_depth2_spirit"

    def actions(self, env: Any) -> list[dict[str, Any]]:
        state = env._require_state(); actor = env.current_agent(); player = env._player(actor)
        if state.robber_pending:
            return [{"kind": "move_robber", "tile": next(tile for tile in range(12) if tile != state.robber_tile)}]
        candidates: list[dict[str, Any]] = [{"kind": "end_turn"}]
        for edge in range(24):
            if edge not in {road for other in state.players for road in other.roads}:
                candidates.append({"kind": "build_road", "edge": edge})
        for vertex in player.settlements:
            candidates.append({"kind": "build_city", "vertex": vertex})
        for vertex in range(24): candidates.append({"kind": "build_settlement", "vertex": vertex})
        candidates.append({"kind": "buy_dev"})
        for card in player.dev_cards:
            command = {"kind": "play_dev", "card": card}
            if card == "knight": command["tile"] = next(tile for tile in range(12) if tile != state.robber_tile)
            if card in ("monopoly", "year_of_plenty"): command["resource"] = "ore"
            candidates.append(command)
        # Retain a stable, short search frontier while keeping each action kind.
        return candidates[:18]

    def evaluate(self, env: Any, root: str) -> float:
        state = env._require_state(); own = env.victory_points(root)
        rivals = max(env.victory_points(player.agent_id) for player in state.players if player.agent_id != root)
        player = env._player(root)
        return 100.0 * (own - rivals) + 2.0 * len(player.roads) + sum(player.resources.values()) * 0.05

    def choose_action(self, env: Any) -> dict[str, Any]:
        root = env.current_agent(); best_action = {"kind": "end_turn"}; best_score = -inf
        for action in self.actions(env):
            child = env.__class__(max_turns=env.max_turns); child.restore(env.checkpoint()); child.step(action)
            reply_actions = self.actions(child)
            score = min(self._after(child, reply, root) for reply in reply_actions) if reply_actions else self.evaluate(child, root)
            if score > best_score: best_score, best_action = score, action
        return best_action

    def _after(self, env: Any, action: dict[str, Any], root: str) -> float:
        child = env.__class__(max_turns=env.max_turns); child.restore(env.checkpoint()); child.step(action)
        return self.evaluate(child, root)
