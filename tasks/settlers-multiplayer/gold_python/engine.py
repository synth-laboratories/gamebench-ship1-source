"""Deterministic, brand-safe four-player settlers-rules emulator.

This is deliberately a compact symbolic board rather than a renderer or a
wrapper around an upstream game.  It preserves the decision pressure relevant
to the paper: production, network expansion, robber disruption, negotiated
trades, development cards, and the two public achievement races.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any

AGENTS = ("agent_0", "agent_1", "agent_2", "agent_3")
RESOURCES = ("wood", "brick", "sheep", "wheat", "ore")
DEV_DECK = ("knight", "knight", "knight", "victory_point", "road_building", "monopoly", "year_of_plenty")
DICE = (5, 8, 6, 9, 7, 10, 4, 11, 3, 12)
# 24 vertices form a modular ring.  Tiles deliberately overlap so every
# settlement participates in several production opportunities.
TILES = (
    ("wood", 5, (0, 1, 2, 3)), ("brick", 8, (3, 4, 5, 6)),
    ("sheep", 6, (6, 7, 8, 9)), ("wheat", 9, (9, 10, 11, 12)),
    ("ore", 4, (12, 13, 14, 15)), ("wood", 10, (15, 16, 17, 18)),
    ("wheat", 3, (18, 19, 20, 21)), ("sheep", 11, (21, 22, 23, 0)),
    ("ore", 5, (1, 7, 13, 19)), ("brick", 6, (2, 8, 14, 20)),
    ("wood", 9, (4, 10, 16, 22)), ("wheat", 8, (5, 11, 17, 23)),
)
EDGES = tuple((index, (index + 1) % 24) for index in range(24))
STARTING_SETTLEMENTS = ((0, 3), (6, 9), (12, 15), (18, 21))


@dataclass
class Player:
    agent_id: str
    resources: dict[str, int] = field(default_factory=lambda: {resource: 4 for resource in RESOURCES})
    settlements: list[int] = field(default_factory=list)
    cities: list[int] = field(default_factory=list)
    roads: list[int] = field(default_factory=list)
    dev_cards: list[str] = field(default_factory=list)
    played_knights: int = 0


@dataclass
class GameState:
    seed: int
    turn: int = 0
    current_player: int = 0
    robber_tile: int = 0
    robber_pending: bool = False
    pending_trade: dict[str, Any] | None = None
    dev_cursor: int = 0
    longest_road_owner: str | None = None
    largest_army_owner: str | None = None
    terminated: bool = False
    winner: str | None = None
    termination_reason: str | None = None
    players: list[Player] = field(default_factory=list)
    nev: list[dict[str, Any]] = field(default_factory=list)
    legacy_nev: list[str] = field(default_factory=list)


class SettlersEnv:
    """Alternating-turn owned emulator of settlers rules to ten VP."""

    env_family = "settlers-multiplayer"

    def __init__(self, max_turns: int = 240):
        self.max_turns = max_turns
        self.state: GameState | None = None

    def reset(self, seed: int = 0) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        players = [Player(agent_id=agent, settlements=list(STARTING_SETTLEMENTS[index]), roads=[STARTING_SETTLEMENTS[index][0], STARTING_SETTLEMENTS[index][1]]) for index, agent in enumerate(AGENTS)]
        self.state = GameState(seed=seed, players=players)
        self._event("game_started", seed=seed, players=list(AGENTS), victory_points_to_win=10)
        return self.observations(), {"seed": seed, "state_hash": self.state_hash(), "turn_model": "alternating"}

    def _require_state(self) -> GameState:
        if self.state is None:
            raise RuntimeError("reset must be called before use")
        return self.state

    def _event(self, kind: str, **payload: Any) -> None:
        state = self._require_state()
        event = {"turn": state.turn, "kind": kind, **payload}
        state.nev.append(event)
        state.legacy_nev.append(f"{''.join(piece.title() for piece in kind.split('_'))}({','.join(map(str, payload.values()))})")

    def current_agent(self) -> str:
        return AGENTS[self._require_state().current_player]

    def legal_actions(self, agent_id: str | None = None) -> list[str]:
        state = self._require_state()
        actor = agent_id or self.current_agent()
        if actor != self.current_agent() or state.terminated:
            return []
        if state.robber_pending:
            return ["move_robber"]
        kinds = ["end_turn", "build_road", "build_settlement", "build_city", "bank_trade", "trade_propose", "trade_accept", "trade_reject", "buy_dev", "play_dev"]
        return kinds

    @staticmethod
    def _normalise_action(action: Any) -> dict[str, Any]:
        if isinstance(action, str):
            return {"kind": action}
        if not isinstance(action, dict) or not isinstance(action.get("kind"), str):
            raise ValueError("action must be a kind string or object")
        return dict(action)

    def step(self, action: Any) -> tuple[dict[str, dict[str, Any]], dict[str, float], dict[str, bool], dict[str, Any]]:
        state = self._require_state()
        if state.terminated:
            raise RuntimeError("step called after a terminal state")
        command = self._normalise_action(action)
        actor = self.current_agent()
        before = {player.agent_id: self.victory_points(player.agent_id) for player in state.players}
        die = DICE[(state.seed + state.turn) % len(DICE)]
        self._event("dice", agent_id=actor, value=die)
        if die == 7:
            self._discard_for_robber()
            state.robber_pending = True
            self._event("robber", agent_id=actor, phase="required")
        else:
            self._produce(die)
        valid = command["kind"] in self.legal_actions(actor)
        if not valid:
            self._event("illegal_action", agent_id=actor, action=command["kind"], reason="not_legal_in_current_phase")
        else:
            self._apply(actor, command)
        if not state.robber_pending:
            self._update_awards()
            self._check_terminal()
            if not state.terminated:
                state.current_player = (state.current_player + 1) % len(AGENTS)
                state.turn += 1
        rewards = {player.agent_id: float(self.victory_points(player.agent_id) - before[player.agent_id]) for player in state.players}
        dones = {agent: state.terminated for agent in AGENTS} | {"__all__": state.terminated}
        return self.observations(), rewards, dones, {"events": deepcopy(state.nev[-12:]), "state_hash": self.state_hash(), "current_agent": self.current_agent() if not state.terminated else None, "termination_reason": state.termination_reason}

    def _apply(self, actor: str, action: dict[str, Any]) -> None:
        kind = action["kind"]
        if kind == "end_turn":
            self._event("turn_end", agent_id=actor)
        elif kind == "move_robber":
            self._move_robber(actor, action)
        elif kind == "build_road":
            self._build_road(actor, action)
        elif kind == "build_settlement":
            self._build_settlement(actor, action)
        elif kind == "build_city":
            self._build_city(actor, action)
        elif kind == "bank_trade":
            self._bank_trade(actor, action)
        elif kind == "trade_propose":
            self._trade_propose(actor, action)
        elif kind == "trade_accept":
            self._trade_accept(actor)
        elif kind == "trade_reject":
            self._trade_reject(actor)
        elif kind == "buy_dev":
            self._buy_dev(actor)
        elif kind == "play_dev":
            self._play_dev(actor, action)

    def _player(self, agent_id: str) -> Player:
        return next(player for player in self._require_state().players if player.agent_id == agent_id)

    @staticmethod
    def _can_pay(player: Player, cost: dict[str, int]) -> bool:
        return all(player.resources[resource] >= amount for resource, amount in cost.items())

    def _pay(self, player: Player, cost: dict[str, int]) -> bool:
        if not self._can_pay(player, cost):
            return False
        for resource, amount in cost.items():
            player.resources[resource] -= amount
        return True

    def _owned_edges(self, agent_id: str) -> set[int]:
        return set(self._player(agent_id).roads)

    @staticmethod
    def _edge_index(value: Any) -> int | None:
        return value if isinstance(value, int) and 0 <= value < len(EDGES) else None

    def _build_road(self, actor: str, action: dict[str, Any]) -> None:
        player = self._player(actor); edge = self._edge_index(action.get("edge"))
        free = bool(action.get("_from_dev", False))
        if edge is None or edge in {road for p in self._require_state().players for road in p.roads}:
            return self._illegal(actor, "road_unavailable")
        endpoints = set(EDGES[edge]); connected = bool(endpoints & set(player.settlements + player.cities))
        connected = connected or any(endpoints & set(EDGES[road]) for road in player.roads)
        if not connected or (not free and not self._can_pay(player, {"wood": 1, "brick": 1})):
            return self._illegal(actor, "road_cost_or_network")
        if not free:
            self._pay(player, {"wood": 1, "brick": 1})
        player.roads.append(edge)
        self._event("build", agent_id=actor, piece="road", edge=edge, free=free)

    def _build_settlement(self, actor: str, action: dict[str, Any]) -> None:
        player = self._player(actor); vertex = action.get("vertex")
        occupied = {vertex for p in self._require_state().players for vertex in p.settlements + p.cities}
        adjacent = {(vertex - 1) % 24, (vertex + 1) % 24}
        connected = any(vertex in EDGES[road] for road in player.roads)
        cost = {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1}
        if not isinstance(vertex, int) or not 0 <= vertex < 24 or vertex in occupied or occupied & adjacent or not connected or not self._pay(player, cost):
            return self._illegal(actor, "settlement_cost_network_or_distance")
        player.settlements.append(vertex)
        self._event("build", agent_id=actor, piece="settlement", vertex=vertex)
        self._event("vp", agent_id=actor, total=self.victory_points(actor), reason="settlement")

    def _build_city(self, actor: str, action: dict[str, Any]) -> None:
        player = self._player(actor); vertex = action.get("vertex")
        if vertex not in player.settlements or not self._pay(player, {"ore": 3, "wheat": 2}):
            return self._illegal(actor, "city_cost_or_ownership")
        player.settlements.remove(vertex); player.cities.append(vertex)
        self._event("build", agent_id=actor, piece="city", vertex=vertex)
        self._event("vp", agent_id=actor, total=self.victory_points(actor), reason="city")

    def _bank_trade(self, actor: str, action: dict[str, Any]) -> None:
        player = self._player(actor); give, want = action.get("give"), action.get("want")
        if give not in RESOURCES or want not in RESOURCES or give == want or player.resources[give] < 4:
            return self._illegal(actor, "bank_trade_ratio_or_resource")
        player.resources[give] -= 4; player.resources[want] += 1
        self._event("trade_bank", agent_id=actor, give={give: 4}, want={want: 1})

    def _trade_propose(self, actor: str, action: dict[str, Any]) -> None:
        state = self._require_state(); target, give, want = action.get("to"), action.get("give"), action.get("want")
        if target not in AGENTS or target == actor or give not in RESOURCES or want not in RESOURCES or self._player(actor).resources[give] < 1:
            return self._illegal(actor, "trade_proposal_invalid")
        state.pending_trade = {"from": actor, "to": target, "give": give, "want": want}
        self._event("trade_proposed", agent_id=actor, to=target, give={give: 1}, want={want: 1})

    def _trade_accept(self, actor: str) -> None:
        state = self._require_state(); offer = state.pending_trade
        if not offer or offer["to"] != actor or self._player(actor).resources[offer["want"]] < 1:
            return self._illegal(actor, "trade_accept_unavailable")
        source, target = self._player(offer["from"]), self._player(actor)
        if source.resources[offer["give"]] < 1:
            return self._illegal(actor, "trade_offer_expired")
        source.resources[offer["give"]] -= 1; target.resources[offer["give"]] += 1
        target.resources[offer["want"]] -= 1; source.resources[offer["want"]] += 1
        state.pending_trade = None
        self._event("trade_accepted", agent_id=actor, from_agent=source.agent_id)

    def _trade_reject(self, actor: str) -> None:
        state = self._require_state(); offer = state.pending_trade
        if not offer or offer["to"] != actor:
            return self._illegal(actor, "trade_reject_unavailable")
        state.pending_trade = None; self._event("trade_rejected", agent_id=actor, from_agent=offer["from"])

    def _buy_dev(self, actor: str) -> None:
        player = self._player(actor); state = self._require_state()
        if not self._pay(player, {"ore": 1, "sheep": 1, "wheat": 1}) or state.dev_cursor >= len(DEV_DECK):
            return self._illegal(actor, "dev_card_cost_or_empty_deck")
        card = DEV_DECK[state.dev_cursor]; state.dev_cursor += 1; player.dev_cards.append(card)
        self._event("dev_card", agent_id=actor, phase="bought", card=card)

    def _play_dev(self, actor: str, action: dict[str, Any]) -> None:
        player = self._player(actor); card = action.get("card")
        if card not in player.dev_cards:
            return self._illegal(actor, "dev_card_unowned")
        player.dev_cards.remove(card)
        if card == "knight":
            player.played_knights += 1; self._event("dev_card", agent_id=actor, phase="played", card=card)
            self._move_robber(actor, {"tile": action.get("tile", 0), "victim": action.get("victim")})
        elif card == "victory_point":
            self._event("vp", agent_id=actor, total=self.victory_points(actor), reason="development")
        elif card == "road_building":
            self._build_road(actor, {"edge": action.get("edge"), "_from_dev": True})
        elif card == "monopoly":
            resource = action.get("resource")
            if resource not in RESOURCES: return self._illegal(actor, "monopoly_resource")
            gained = 0
            for opponent in self._require_state().players:
                if opponent != player: gained += opponent.resources[resource]; opponent.resources[resource] = 0
            player.resources[resource] += gained; self._event("dev_card", agent_id=actor, phase="played", card=card, resource=resource, gained=gained)
        else:
            resource = action.get("resource")
            if resource not in RESOURCES: return self._illegal(actor, "year_of_plenty_resource")
            player.resources[resource] += 2; self._event("dev_card", agent_id=actor, phase="played", card=card, resource=resource)

    def _move_robber(self, actor: str, action: dict[str, Any]) -> None:
        state = self._require_state(); tile = action.get("tile"); victim = action.get("victim")
        if not isinstance(tile, int) or not 0 <= tile < len(TILES) or tile == state.robber_tile:
            return self._illegal(actor, "robber_tile_invalid")
        state.robber_tile = tile; state.robber_pending = False
        stolen = None
        if victim in AGENTS and victim != actor:
            target = self._player(victim); resource = next((r for r in RESOURCES if target.resources[r] > 0), None)
            if resource:
                target.resources[resource] -= 1; self._player(actor).resources[resource] += 1; stolen = resource
        self._event("robber", agent_id=actor, phase="moved", tile=tile, victim=victim, stolen=stolen)

    def _discard_for_robber(self) -> None:
        for player in self._require_state().players:
            total = sum(player.resources.values())
            if total > 7:
                drop = total // 2
                # The symbolic engine uses a stable discard priority.  It
                # preserves basic construction materials, so a robber does
                # not turn the network race into a deterministic dead end.
                for resource in ("ore", "wheat", "sheep", "brick", "wood"):
                    amount = min(player.resources[resource], drop); player.resources[resource] -= amount; drop -= amount
                    if not drop: break
                self._event("robber", agent_id=player.agent_id, phase="discarded")

    def _produce(self, die: int) -> None:
        state = self._require_state()
        for tile_index, (resource, number, vertices) in enumerate(TILES):
            if number != die or tile_index == state.robber_tile: continue
            for player in state.players:
                amount = sum(2 if vertex in player.cities else 1 for vertex in vertices if vertex in player.settlements or vertex in player.cities)
                if amount:
                    player.resources[resource] += amount; self._event("produce", agent_id=player.agent_id, resource=resource, amount=amount, tile=tile_index)

    def _road_length(self, player: Player) -> int:
        if not player.roads: return 0
        remaining = set(player.roads); longest = 0
        while remaining:
            stack = [remaining.pop()]; size = 0
            while stack:
                edge = stack.pop(); size += 1; endpoints = set(EDGES[edge])
                linked = [candidate for candidate in remaining if endpoints & set(EDGES[candidate])]
                for candidate in linked: remaining.remove(candidate); stack.append(candidate)
            longest = max(longest, size)
        return longest

    def _update_awards(self) -> None:
        state = self._require_state()
        roads = sorted(((self._road_length(player), player.agent_id) for player in state.players), reverse=True)
        if roads[0][0] >= 5 and (state.longest_road_owner is None or roads[0][0] > self._road_length(self._player(state.longest_road_owner))):
            state.longest_road_owner = roads[0][1]; self._event("longest_road", agent_id=roads[0][1], length=roads[0][0])
        armies = sorted(((player.played_knights, player.agent_id) for player in state.players), reverse=True)
        if armies[0][0] >= 3 and (state.largest_army_owner is None or armies[0][0] > self._player(state.largest_army_owner).played_knights):
            state.largest_army_owner = armies[0][1]; self._event("largest_army", agent_id=armies[0][1], knights=armies[0][0])

    def victory_points(self, agent_id: str) -> int:
        state = self._require_state(); player = self._player(agent_id)
        dev_vp = player.dev_cards.count("victory_point")
        return len(player.settlements) + 2 * len(player.cities) + dev_vp + (2 if state.longest_road_owner == agent_id else 0) + (2 if state.largest_army_owner == agent_id else 0)

    def _check_terminal(self) -> None:
        state = self._require_state(); winner = next((player.agent_id for player in state.players if self.victory_points(player.agent_id) >= 10), None)
        if winner:
            state.terminated = True; state.winner = winner; state.termination_reason = "victory_points"; self._event("terminal", winner=winner, reason="victory_points")
        elif state.turn + 1 >= self.max_turns:
            state.terminated = True; state.termination_reason = "turn_limit"; self._event("terminal", winner=None, reason="turn_limit")

    def _illegal(self, actor: str, reason: str) -> None:
        self._event("illegal_action", agent_id=actor, reason=reason)

    def observations(self) -> dict[str, dict[str, Any]]:
        state = self._require_state(); public = {player.agent_id: {"vp": self.victory_points(player.agent_id), "settlements": sorted(player.settlements), "cities": sorted(player.cities), "roads": sorted(player.roads), "played_knights": player.played_knights} for player in state.players}
        return {agent: {"agent_id": agent, "turn_model": "alternating", "current_agent": self.current_agent() if not state.terminated else None, "legal_actions": self.legal_actions(agent), "self": asdict(self._player(agent)), "public": public, "robber_tile": state.robber_tile, "pending_trade": state.pending_trade, "victory_points_to_win": 10, "last_nev": state.nev[-8:]} for agent in AGENTS}

    def state_dict(self) -> dict[str, Any]:
        return asdict(self._require_state()) | {"max_turns": self.max_turns}

    def state_hash(self) -> str:
        return sha256(json.dumps(self.state_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def checkpoint(self) -> dict[str, Any]:
        return {"schema_version": "gamebench.checkpoint.v1", "env_family": self.env_family, "sim": self.state_dict()}

    def restore(self, checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if checkpoint.get("schema_version") != "gamebench.checkpoint.v1" or checkpoint.get("env_family") != self.env_family:
            raise ValueError("unsupported settlers checkpoint")
        data = deepcopy(checkpoint["sim"]); self.max_turns = int(data.pop("max_turns", self.max_turns))
        data["players"] = [Player(**player) for player in data["players"]]
        self.state = GameState(**data)
        return self.observations()
