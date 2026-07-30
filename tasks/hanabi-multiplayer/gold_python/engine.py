"""Deterministic two-player Hanabi authority with private observations."""

from __future__ import annotations

import copy
import json
import random
from typing import Any

AGENTS = ("agent_0", "agent_1")
COLORS = ("red", "yellow", "green", "blue", "white")
RANK_COUNTS = {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}
HAND_SIZE = 5
MAX_INFORMATION_TOKENS = 8


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


class HanabiEnv:
    """A standard, alternating-turn, cooperative two-player Hanabi game."""

    ENV_FAMILY = "hanabi"

    def __init__(self) -> None:
        self.state: dict[str, Any] | None = None
        self.events: list[dict[str, Any]] = []
        self.next_event_sequence = 0

    def reset(self, seed: int = 0) -> dict[str, Any]:
        deck = [
            {"color": color, "rank": rank}
            for color in COLORS
            for rank, count in RANK_COUNTS.items()
            for _ in range(count)
        ]
        random.Random(seed).shuffle(deck)
        hands = {agent: [] for agent in AGENTS}
        knowledge = {agent: [] for agent in AGENTS}
        for _ in range(HAND_SIZE):
            for agent in AGENTS:
                hands[agent].append(deck.pop())
                knowledge[agent].append(self._blank_knowledge())
        self.state = {
            "schema_version": "gamebench.hanabi.state.v1",
            "seed": seed,
            "turn": 0,
            "active_agent": "agent_0",
            "deck": deck,
            "hands": hands,
            "knowledge": knowledge,
            "fireworks": {color: 0 for color in COLORS},
            "discard_pile": [],
            "information_tokens": MAX_INFORMATION_TOKENS,
            "life_tokens": 3,
            "final_turns_remaining": None,
            "terminal": None,
        }
        self.events = []
        self.next_event_sequence = 0
        self._emit("game_started", None, {"seed": seed, "deck_size": len(deck)})
        self._emit("turn_started", "agent_0", {})
        return self.observe()

    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        state = self._require_state()
        if state["terminal"] is not None:
            self._emit("illegal_action", state["active_agent"], {"reason": "terminal"})
            return self.snapshot()
        actor = state["active_agent"]
        if not isinstance(action, dict):
            self._illegal(actor, "action_not_object")
            return self.snapshot()
        kind = action.get("kind")
        if kind == "play":
            self._play_or_discard(actor, action, play=True)
        elif kind == "discard":
            self._play_or_discard(actor, action, play=False)
        elif kind == "hint":
            self._hint(actor, action)
        else:
            self._illegal(actor, "unknown_action", action)
        if state["terminal"] is None:
            self._finish_turn(actor)
        return self.snapshot()

    def observe(self, agent: str | None = None) -> dict[str, Any]:
        state = self._require_state()
        agent = agent or state["active_agent"]
        if agent not in AGENTS:
            raise ValueError(f"unknown Hanabi agent: {agent}")
        partner = self._other(agent)
        return _canonical({
            "schema_version": "gamebench.hanabi.observation.v1",
            "you": agent,
            "partner": partner,
            "active_agent": state["active_agent"],
            "turn": state["turn"],
            "own_hand": [
                {"slot": index, "color": None, "rank": None, "knowledge": copy.deepcopy(known)}
                for index, known in enumerate(state["knowledge"][agent])
            ],
            "partner_hand": [
                {"slot": index, **copy.deepcopy(card), "knowledge": copy.deepcopy(state["knowledge"][partner][index])}
                for index, card in enumerate(state["hands"][partner])
            ],
            "fireworks": state["fireworks"],
            "discard_pile": state["discard_pile"],
            "information_tokens": state["information_tokens"],
            "life_tokens": state["life_tokens"],
            "deck_size": len(state["deck"]),
            "final_turns_remaining": state["final_turns_remaining"],
            "terminal": state["terminal"],
        })

    def snapshot(self) -> dict[str, Any]:
        return _canonical({"observation": self.observe(), "state": self.state_projection(), "nev": copy.deepcopy(self.events)})

    def state_projection(self) -> dict[str, Any]:
        return _canonical(self._require_state())

    def checkpoint(self) -> dict[str, Any]:
        return _canonical({"schema_version": "gamebench.hanabi.checkpoint.v1", "state": self._require_state(), "events": self.events, "next_event_sequence": self.next_event_sequence})

    def restore(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if checkpoint.get("schema_version") != "gamebench.hanabi.checkpoint.v1":
            raise ValueError("unsupported Hanabi checkpoint")
        self.state = copy.deepcopy(checkpoint["state"])
        self.events = copy.deepcopy(checkpoint["events"])
        self.next_event_sequence = int(checkpoint["next_event_sequence"])
        return self.observe()

    def _play_or_discard(self, actor: str, action: dict[str, Any], *, play: bool) -> bool:
        state = self._require_state()
        slot = action.get("slot")
        hand = state["hands"][actor]
        if not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot < len(hand):
            self._illegal(actor, "invalid_slot", action)
            return False
        if not play and state["information_tokens"] >= MAX_INFORMATION_TOKENS:
            self._illegal(actor, "information_tokens_full", action)
            return False
        card = hand.pop(slot)
        state["knowledge"][actor].pop(slot)
        if play:
            if state["fireworks"][card["color"]] + 1 == card["rank"]:
                state["fireworks"][card["color"]] = card["rank"]
                if card["rank"] == 5:
                    state["information_tokens"] = min(MAX_INFORMATION_TOKENS, state["information_tokens"] + 1)
                self._emit("card_played", actor, {"slot": slot, "card": card})
            else:
                state["life_tokens"] -= 1
                state["discard_pile"].append(card)
                self._emit("card_misplayed", actor, {"slot": slot, "card": card, "life_tokens": state["life_tokens"]})
        else:
            state["discard_pile"].append(card)
            state["information_tokens"] += 1
            self._emit("card_discarded", actor, {"slot": slot, "card": card, "information_tokens": state["information_tokens"]})
        self._draw(actor)
        if state["life_tokens"] <= 0:
            self._terminate("lives_exhausted")
        elif sum(state["fireworks"].values()) == 25:
            self._terminate("perfect_score")
        return True

    def _hint(self, actor: str, action: dict[str, Any]) -> bool:
        state = self._require_state()
        if state["information_tokens"] <= 0:
            self._illegal(actor, "no_information_tokens", action)
            return False
        color, rank = action.get("color"), action.get("rank")
        if (color is None) == (rank is None):
            self._illegal(actor, "hint_requires_exactly_one_attribute", action)
            return False
        if color is not None and color not in COLORS:
            self._illegal(actor, "invalid_color", action)
            return False
        if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool) or rank not in RANK_COUNTS):
            self._illegal(actor, "invalid_rank", action)
            return False
        partner = self._other(actor)
        matches = [
            index for index, card in enumerate(state["hands"][partner])
            if (card["color"] == color if color is not None else card["rank"] == rank)
        ]
        if not matches:
            self._illegal(actor, "hint_matches_no_cards", action)
            return False
        state["information_tokens"] -= 1
        for index, card in enumerate(state["hands"][partner]):
            known = state["knowledge"][partner][index]
            if color is not None:
                if index in matches:
                    known["color"] = color
                else:
                    known["not_colors"] = sorted(set(known["not_colors"]) | {color})
            elif index in matches:
                known["rank"] = rank
            else:
                known["not_ranks"] = sorted(set(known["not_ranks"]) | {rank})
        self._emit("hint_given", actor, {"target": partner, "color": color, "rank": rank, "matching_slots": matches})
        return True

    def _draw(self, actor: str) -> None:
        state = self._require_state()
        if not state["deck"]:
            return
        state["hands"][actor].append(state["deck"].pop())
        state["knowledge"][actor].append(self._blank_knowledge())
        self._emit("card_drawn", actor, {"remaining_deck": len(state["deck"])})
        if not state["deck"] and state["final_turns_remaining"] is None:
            state["final_turns_remaining"] = len(AGENTS) + 1
            self._emit("final_round_started", None, {"turns_remaining_after_current": len(AGENTS)})

    def _finish_turn(self, actor: str) -> None:
        state = self._require_state()
        if state["final_turns_remaining"] is not None:
            state["final_turns_remaining"] -= 1
            if state["final_turns_remaining"] == 0:
                self._terminate("deck_exhausted")
                return
        state["turn"] += 1
        state["active_agent"] = self._other(actor)
        self._emit("turn_started", state["active_agent"], {})

    def _terminate(self, reason: str) -> None:
        state = self._require_state()
        state["terminal"] = {"reason": reason, "score": sum(state["fireworks"].values())}
        self._emit("game_ended", None, state["terminal"])

    def _illegal(self, actor: str, reason: str, action: Any | None = None) -> None:
        self._emit("illegal_action", actor, {"reason": reason, "action": action})

    def _emit(self, kind: str, actor: str | None, payload: dict[str, Any]) -> None:
        state = self._require_state()
        self.events.append({"schema_version": "gamebench.nev.v1", "seq": self.next_event_sequence, "turn": state["turn"], "actor": actor, "kind": kind, "payload": _canonical(payload)})
        self.next_event_sequence += 1

    def _require_state(self) -> dict[str, Any]:
        if self.state is None:
            raise RuntimeError("reset must be called before using HanabiEnv")
        return self.state

    @staticmethod
    def _other(agent: str) -> str:
        return "agent_1" if agent == "agent_0" else "agent_0"

    @staticmethod
    def _blank_knowledge() -> dict[str, Any]:
        return {"color": None, "rank": None, "not_colors": [], "not_ranks": []}
