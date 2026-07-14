"""Authoritative Python engine for synthetic Earthborne Rangers."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from core.checkpoint import decode_checkpoint, encode_checkpoint
from core.nev import EventKind, EventRecord, EventSeverity, NevLog
from parity import EBR_ACHIEVEMENTS, INTERMEDIATE_ACHIEVEMENTS, VERY_ADVANCED_ACHIEVEMENTS
from state import PrivateState, PublicState, SimSnapshot
from task_resolve import ResolvedTask, resolve_task, resolved_from_dict


def episode_id_for_task(task_id: str, seed: int, config_hash: str) -> str:
    raw = f"gamebench.earthborne-rangers-singleplayer.episode:{task_id}:{seed}:{config_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class EarthborneRangersEngine:
    ENV_FAMILY = "earthborne-rangers-singleplayer"
    ACTION_TYPES = (
        "start_day",
        "choose_ranger",
        "choose_role",
        "record_campaign_entry",
        "select_deck",
        "draw",
        "discard",
        "fatigue",
        "soothe",
        "take_injury",
        "add_malady",
        "spend_energy",
        "commit_card",
        "resolve_test",
        "resolve_challenge",
        "exhaust",
        "ready",
        "build_path_deck",
        "draw_path_card",
        "place_path_card",
        "check_range",
        "play_card",
        "attach_card",
        "add_progress",
        "add_harm",
        "change_presence",
        "clear_card",
        "travel",
        "test",
        "interact",
        "rest",
        "end_round",
        "refresh",
        "choose_travel",
        "end_day",
        "resolve_trigger",
        "choose_option",
        "apply_effect",
        "set_active_ranger",
        "assist_test",
        "move_ranger_area",
        "write_note",
        "expose_reflection",
        "complete_attempt",
    )
    STATE_FIELDS = (
        "ranger_identity",
        "ranger_deck",
        "hand",
        "discard",
        "fatigue_stack",
        "current_location",
        "day",
        "campaign_log",
        "mission_states",
        "strategy_notes",
        "reflection_exposures",
        "score_components",
        "event_log_hash",
        "session",
        "role",
        "aspect_card",
        "reward_pool",
        "injuries",
        "maladies",
        "setup_cards",
        "aspect_energy",
        "ready_state",
        "committed_cards",
        "active_test",
        "challenge_discard",
        "path_deck",
        "path_discard",
        "within_reach",
        "along_the_way",
        "nearby",
        "obstacles",
        "terrain_sets",
        "world_cards",
        "attachments",
        "progress_tokens",
        "harm_tokens",
        "presence_tokens",
        "traits",
        "keywords",
        "round",
        "rested_rangers",
        "travel_progress",
        "ready_queue",
        "refresh_queue",
        "trigger_queue",
        "replacement_effects",
        "persistent_effects",
        "delayed_effects",
        "choice_prompts",
        "rangers",
        "turn_order",
        "within_reach_by_ranger",
        "shared_location",
        "ranger_local_areas",
        "attempt_index",
    )

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.public = PublicState("", None, "trailhead", 1, 0, 0, [], [], [], [], {})
        self.private = PrivateState("", "", "", 0, "")
        self.full_state: dict[str, Any] = _default_full_state()
        self.nev = NevLog()

    def reset(self, resolved_task: ResolvedTask) -> SimSnapshot:
        self.resolved = resolved_task
        episode_id = episode_id_for_task(resolved_task.task_id, resolved_task.seed, resolved_task.config_hash)
        objective_targets = {obj.objective_id: obj.target for obj in resolved_task.objectives}
        objective_locations = {obj.objective_id: obj.location_id for obj in resolved_task.objectives}
        self.public = PublicState(
            ranger_id=resolved_task.ranger_id,
            archetype=None,
            location_id=resolved_task.starting_location,
            day=1,
            time=0,
            fatigue=0,
            hand=[],
            play_area=[],
            discard=[],
            objectives_completed=[],
            objective_progress={obj.objective_id: 0 for obj in resolved_task.objectives},
        )
        self.private = PrivateState(
            episode_id=episode_id,
            task_id=resolved_task.task_id,
            scenario_id=resolved_task.scenario_id,
            seed=resolved_task.seed,
            config_hash=resolved_task.config_hash,
            objective_targets=objective_targets,
            objective_locations=objective_locations,
            objective_count=len(resolved_task.objectives),
        )
        self.full_state = _default_full_state()
        self.full_state["ranger_identity"] = resolved_task.ranger_id
        self.full_state["ranger_deck"] = list(resolved_task.decks.get(resolved_task.default_archetype, []))
        self.full_state["current_location"] = resolved_task.starting_location
        self.full_state["shared_location"] = resolved_task.starting_location
        self.full_state["day"] = 1
        self.full_state["mission_states"] = {obj.objective_id: "active" for obj in resolved_task.objectives}
        self.full_state["score_components"] = {"objective_count": len(resolved_task.objectives)}
        self.nev = NevLog()
        self._append_nev(
            kind=EventKind.TASK_RESOLVED,
            message=f"TaskResolved({resolved_task.scenario_id},{resolved_task.config_hash})",
            payload={"resolved": resolved_task.to_dict()},
        )
        self._expose_reflections(resolved_task.reflexion)
        if resolved_task.default_archetype:
            self._select_deck(resolved_task.default_archetype, count_step=False)
        return self.snapshot()

    def reset_from_task(self, task: dict[str, Any], seed_override: int | None = None) -> SimSnapshot:
        return self.reset(resolve_task(task, seed_override=seed_override))

    def step(self, action: str | dict[str, Any]) -> tuple[SimSnapshot, EventRecord | None]:
        parsed = self._parse_action(action)
        if self.private.terminated or self.private.truncated:
            return self._rule_violation(parsed, "terminal")
        self.private.step_index += 1
        self.private.reward_last = 0.0
        action_type = parsed["type"]
        if action_type == "start_day":
            record = self._start_day(parsed)
        elif action_type == "choose_ranger":
            record = self._choose_ranger(parsed)
        elif action_type == "choose_role":
            record = self._choose_role(parsed)
        elif action_type == "record_campaign_entry":
            record = self._record_campaign_entry(parsed)
        elif action_type == "select_deck":
            record = self._select_deck(str(parsed.get("archetype", "")), count_step=True)
        elif action_type == "draw":
            record = self._draw_card(parsed)
        elif action_type == "discard":
            record = self._discard_card(parsed)
        elif action_type == "fatigue":
            record = self._fatigue_action(parsed)
        elif action_type == "soothe":
            record = self._soothe_action(parsed)
        elif action_type == "take_injury":
            record = self._take_injury(parsed)
        elif action_type == "add_malady":
            record = self._add_malady(parsed)
        elif action_type == "play":
            record = self._play_card(str(parsed.get("card_id", "")), parsed)
        elif action_type == "play_card":
            record = self._play_card(str(parsed.get("card_id", "")), parsed)
        elif action_type == "spend_energy":
            record = self._spend_energy(parsed)
        elif action_type == "commit_card":
            record = self._commit_card(parsed)
        elif action_type == "resolve_test":
            record = self._resolve_test_action(parsed)
        elif action_type == "resolve_challenge":
            record = self._resolve_challenge(parsed)
        elif action_type == "exhaust":
            record = self._set_ready_state(parsed, ready=False)
        elif action_type == "ready":
            record = self._set_ready_state(parsed, ready=True)
        elif action_type == "build_path_deck":
            record = self._build_path_deck(parsed)
        elif action_type == "draw_path_card":
            record = self._draw_path_card(parsed)
        elif action_type == "place_path_card":
            record = self._place_path_card(parsed)
        elif action_type == "check_range":
            record = self._check_range(parsed)
        elif action_type == "travel":
            record = self._travel(str(parsed.get("location_id", "")), parsed)
        elif action_type == "test":
            record = self._test_objective(str(parsed.get("objective_id", "")), parsed)
        elif action_type == "interact":
            record = self._interact(str(parsed.get("objective_id", "")), parsed)
        elif action_type == "attach_card":
            record = self._attach_card(parsed)
        elif action_type == "add_progress":
            record = self._token_action(parsed, "progress_tokens", EventKind.PROGRESS_ADDED, "ProgressAdded")
        elif action_type == "add_harm":
            record = self._token_action(parsed, "harm_tokens", EventKind.HARM_ADDED, "HarmAdded")
        elif action_type == "change_presence":
            record = self._token_action(parsed, "presence_tokens", EventKind.PRESENCE_CHANGED, "PresenceChanged")
        elif action_type == "clear_card":
            record = self._clear_card(parsed)
        elif action_type == "rest":
            record = self._rest(parsed)
        elif action_type == "end_round":
            record = self._round_event(parsed, EventKind.ROUND_ENDED, "RoundEnded")
        elif action_type == "refresh":
            record = self._refresh(parsed)
        elif action_type == "choose_travel":
            record = self._choose_travel(parsed)
        elif action_type == "end_day":
            record = self._end_day(parsed)
        elif action_type == "resolve_trigger":
            record = self._resolve_trigger(parsed)
        elif action_type == "choose_option":
            record = self._choose_option(parsed)
        elif action_type == "apply_effect":
            record = self._apply_effect(parsed)
        elif action_type == "set_active_ranger":
            record = self._set_active_ranger(parsed)
        elif action_type == "assist_test":
            record = self._assist_test(parsed)
        elif action_type == "move_ranger_area":
            record = self._move_ranger_area(parsed)
        elif action_type == "write_note":
            record = self._write_note(str(parsed.get("text", "")), parsed)
        elif action_type == "expose_reflection":
            record = self._expose_reflection_action(parsed)
        elif action_type == "complete_attempt":
            record = self._complete_attempt(parsed)
        else:
            record = self._rule_violation(parsed, f"unknown_action:{action_type}")
        self._check_limits()
        return self.snapshot(), record

    def checkpoint_bytes(self) -> bytes:
        return encode_checkpoint(
            env_family=self.ENV_FAMILY,
            episode_id=self.private.episode_id,
            step_index=self.private.step_index,
            nev_cursor=self.nev.cursor(),
            config_hash=self.private.config_hash,
            sim={
                "resolved": self.resolved.to_dict() if self.resolved else None,
                "public": self.public.to_dict(),
                "private": self.private.to_dict(),
                "full_state": self.full_state,
            },
            nev_events=self.nev.export(),
        )

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = decode_checkpoint(blob)
        if payload["env_family"] != self.ENV_FAMILY:
            raise ValueError(f"wrong env_family: {payload['env_family']}")
        sim = payload["sim"]
        self.resolved = resolved_from_dict(sim["resolved"]) if sim.get("resolved") else None
        self.public = _public_from_dict(sim["public"])
        self.private = _private_from_dict(sim["private"])
        self.full_state = copy.deepcopy(sim.get("full_state") or _default_full_state())
        self.nev = NevLog()
        self.nev.import_events(payload.get("nev_events", []))
        if self.nev.cursor() != int(payload.get("nev_cursor", self.nev.cursor())):
            raise ValueError("checkpoint nev_cursor does not match restored events")
        self._validate_achievement_state()
        return self.nev.cursor()

    def valid_actions(self) -> list[str]:
        if self.private.terminated or self.private.truncated:
            return []
        actions = ["draw", "rest", "end_day"]
        if self.public.archetype is None and self.resolved:
            actions.extend(f"select_deck:{name}" for name in sorted(self.resolved.decks))
        actions.extend(f"play:{card_id}" for card_id in self.public.hand)
        if self.resolved:
            actions.extend(f"travel:{location_id}" for location_id in sorted(self.resolved.locations) if location_id != self.public.location_id)
            for objective_id in self.private.objective_targets:
                if objective_id not in self.public.objectives_completed:
                    actions.append(f"test:{objective_id}")
                    if self.private.objective_locations.get(objective_id) == self.public.location_id:
                        actions.append(f"interact:{objective_id}")
        return actions

    def symbolic_readout(self) -> dict[str, Any]:
        return {
            "env_family": self.ENV_FAMILY,
            "scenario_id": self.private.scenario_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.nev.cursor(),
            "public": self.public.to_dict(),
            "full_state": copy.deepcopy(self.full_state),
            "private_summary": {
                "fatigue_taken": self.private.fatigue_taken,
                "fatigue_recovered": self.private.fatigue_recovered,
                "illegal_action_count": self.private.illegal_action_count,
                "cards_played": list(self.private.cards_played),
                "strategy_notes": list(self.private.strategy_notes),
                "exposed_reflections": list(self.private.exposed_reflections),
                "achievements": sorted(self.private.achievements),
                "total_reward": self.private.total_reward,
                "terminated": self.private.terminated,
                "truncated": self.private.truncated,
            },
        }

    def snapshot(self) -> SimSnapshot:
        return SimSnapshot(self.public, self.private, self.nev.export())

    def clone_for_sim(self) -> "EarthborneRangersEngine":
        clone = EarthborneRangersEngine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone

    def _parse_action(self, action: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(action, dict):
            return dict(action)
        raw = str(action).strip()
        if ":" in raw:
            action_type, value = raw.split(":", 1)
            if action_type == "select_deck":
                return {"type": action_type, "archetype": value}
            if action_type == "play":
                return {"type": action_type, "card_id": value}
            if action_type == "travel":
                return {"type": action_type, "location_id": value}
            if action_type in ("test", "interact"):
                return {"type": action_type, "objective_id": value}
            if action_type == "write_note":
                return {"type": action_type, "text": value}
        return {"type": raw}

    def _start_day(self, action: dict[str, Any]) -> EventRecord:
        day = int(action.get("day", self.full_state.get("day", self.public.day)))
        self.public.day = day
        self.private.day_start_illegal_count = self.private.illegal_action_count
        self.full_state["day"] = day
        self.full_state["session"] = action.get("session", self.full_state.get("session", "synthetic_session"))
        self._append_nev(kind=EventKind.DAY_STARTED, message=f"DayStarted({day})", action=action, payload={"day": day})
        return self._append_nev(
            kind=EventKind.ROUND_STARTED,
            message=f"RoundStarted({self.full_state['round']})",
            action=action,
            payload={"round": self.full_state["round"]},
        )

    def _choose_ranger(self, action: dict[str, Any]) -> EventRecord:
        ranger_id = str(action.get("ranger_id", self.public.ranger_id))
        self.public.ranger_id = ranger_id
        self.full_state["ranger_identity"] = ranger_id
        if ranger_id not in self.full_state["rangers"]:
            self.full_state["rangers"].append(ranger_id)
        return self._append_nev(kind=EventKind.CAMPAIGN_SETUP, message=f"CampaignSetup(ranger={ranger_id})", action=action, payload={"ranger_id": ranger_id})

    def _choose_role(self, action: dict[str, Any]) -> EventRecord:
        role = str(action.get("role", "synthetic_role"))
        aspect_card = str(action.get("aspect_card", "synthetic_aspect"))
        self.full_state["role"] = role
        self.full_state["aspect_card"] = aspect_card
        return self._append_nev(kind=EventKind.CAMPAIGN_SETUP, message=f"CampaignSetup(role={role})", action=action, payload={"role": role, "aspect_card": aspect_card})

    def _record_campaign_entry(self, action: dict[str, Any]) -> EventRecord:
        entry_id = str(action.get("entry_id", f"entry_{len(self.full_state['campaign_log'])}"))
        state = str(action.get("state", "recorded"))
        self.full_state["campaign_log"].append({"entry_id": entry_id, "state": state})
        if "mission_id" in action:
            self.full_state["mission_states"][str(action["mission_id"])] = state
        return self._append_nev(kind=EventKind.MISSION_STATE_CHANGED, message=f"MissionStateChanged({entry_id},{state})", action=action, payload={"entry_id": entry_id, "state": state})

    def _discard_card(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        if card_id in self.public.hand:
            self.public.hand.remove(card_id)
        self.public.discard.append(card_id)
        self.full_state["hand"] = list(self.public.hand)
        self.full_state["discard"] = list(self.public.discard)
        return self._append_nev(kind=EventKind.CARD_DISCARDED, message=f"CardDiscarded({card_id})", action=action, payload={"card_id": card_id})

    def _fatigue_action(self, action: dict[str, Any]) -> EventRecord:
        amount = int(action.get("amount", 1))
        moved: list[str] = []
        for _ in range(max(0, amount)):
            if self.private.deck_index < len(self.private.deck):
                card_id = self.private.deck[self.private.deck_index]
                self.private.deck_index += 1
                moved.append(card_id)
        self.full_state["fatigue_stack"].extend(moved)
        if len(moved) < amount:
            self._append_nev(kind=EventKind.DECK_EXHAUSTED, message="DeckExhausted(ranger)", action=action, payload={"requested": amount, "moved": len(moved)})
        return self._take_fatigue(amount, action, f"FatigueTaken({amount})")

    def _soothe_action(self, action: dict[str, Any]) -> EventRecord:
        amount = int(action.get("amount", 1))
        soothed = self.full_state["fatigue_stack"][-amount:] if amount > 0 else []
        if soothed:
            del self.full_state["fatigue_stack"][-len(soothed):]
            self.public.hand.extend(soothed)
            self.full_state["hand"] = list(self.public.hand)
        recovered = min(amount, self.public.fatigue)
        self.public.fatigue -= recovered
        self.private.fatigue_recovered += recovered
        return self._append_nev(kind=EventKind.FATIGUE_SOOTHED, message=f"FatigueSoothed({recovered})", action=action, payload={"amount": recovered, "cards": soothed})

    def _take_injury(self, action: dict[str, Any]) -> EventRecord:
        injury_id = str(action.get("injury_id", f"injury_{len(self.full_state['injuries'])}"))
        self.full_state["injuries"].append(injury_id)
        return self._append_nev(kind=EventKind.INJURY_TAKEN, message=f"InjuryTaken({injury_id})", action=action, payload={"injury_id": injury_id})

    def _add_malady(self, action: dict[str, Any]) -> EventRecord:
        malady_id = str(action.get("malady_id", f"malady_{len(self.full_state['maladies'])}"))
        self.full_state["maladies"].append(malady_id)
        self.private.deck.append(malady_id)
        return self._append_nev(kind=EventKind.MALADY_ADDED, message=f"MaladyAdded({malady_id})", action=action, payload={"malady_id": malady_id})

    def _select_deck(self, archetype: str, *, count_step: bool) -> EventRecord:
        if not self.resolved or archetype not in self.resolved.decks:
            return self._rule_violation({"type": "select_deck", "archetype": archetype}, f"unknown_archetype:{archetype}")
        previous = _public_from_dict(self.public.to_dict())
        self.public.archetype = archetype
        self.private.deck = list(self.resolved.decks[archetype])
        self.private.deck_index = 0
        self.public.hand = []
        self.public.play_area = []
        self.public.discard = []
        if count_step:
            self._unlock("select_deck")
        return self._append_nev(
            kind=EventKind.DECK_SELECTED,
            message=f"DeckSelected({archetype})",
            action={"type": "select_deck", "archetype": archetype} if count_step else None,
            transition=self.public.diff(previous),
            payload={"archetype": archetype, "deck_size": len(self.private.deck)},
        )

    def _draw_card(self, action: dict[str, Any]) -> EventRecord:
        if not self.private.deck:
            return self._rule_violation(action, "deck_not_selected")
        card_id = self.private.deck[self.private.deck_index % len(self.private.deck)]
        self.private.deck_index += 1
        self.public.hand.append(card_id)
        self.full_state["hand"] = list(self.public.hand)
        self._unlock("first_card_drawn")
        return self._append_nev(
            kind=EventKind.CARD_DRAWN,
            message=f"CardDrawn({card_id})",
            action=action,
            payload={"card_id": card_id, "hand_size": len(self.public.hand)},
        )

    def _play_card(self, card_id: str, action: dict[str, Any]) -> EventRecord:
        if not self.resolved or card_id not in self.resolved.cards:
            return self._rule_violation(action, f"unknown_card:{card_id}")
        if card_id not in self.public.hand:
            return self._rule_violation(action, f"card_not_in_hand:{card_id}")
        card = self.resolved.cards[card_id]
        self.public.hand.remove(card_id)
        self.public.play_area.append(card_id)
        self.full_state["hand"] = list(self.public.hand)
        self.private.cards_played.append(card_id)
        self._unlock("first_card_played")
        if len(set(self.private.cards_played)) >= 5:
            self._unlock("card_diversity_5")
        record = self._append_nev(
            kind=EventKind.CARD_PLAYED,
            message=f"CardPlayed({card_id})",
            action=action,
            payload={"card_id": card_id, "tags": list(card.get("tags", []))},
        )
        effects = list(card.get("effects") or [])
        if effects:
            self._apply_effect_list(effects, action, source=f"card:{card_id}", label=f"CardEffect({card_id})")
        else:
            fatigue_cost = int(card.get("fatigue_cost", 0))
            if fatigue_cost:
                self._take_fatigue(fatigue_cost, action, f"CardFatigue({card_id},{fatigue_cost})")
            recover = int(card.get("recover", 0))
            if recover:
                self._recover_fatigue(recover, action, f"CardRecovered({card_id},{recover})")
            progress = int(card.get("progress", 0))
            if progress:
                self._apply_progress(self._nearest_incomplete_objective(), progress, action, source=f"card:{card_id}")
        return record

    def _spend_energy(self, action: dict[str, Any]) -> EventRecord:
        aspect = str(action.get("aspect", "any"))
        amount = int(action.get("amount", 1))
        current = int(self.full_state["aspect_energy"].get(aspect, 0))
        self.full_state["aspect_energy"][aspect] = current - amount
        return self._append_nev(kind=EventKind.ENERGY_SPENT, message=f"EnergySpent({aspect},{amount})", action=action, payload={"aspect": aspect, "amount": amount, "remaining": self.full_state["aspect_energy"][aspect]})

    def _commit_card(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        test_id = str(action.get("test_id", "active_test"))
        self.full_state["committed_cards"].append({"card_id": card_id, "test_id": test_id})
        return self._append_nev(kind=EventKind.CARD_COMMITTED, message=f"CardCommitted({card_id},{test_id})", action=action, payload={"card_id": card_id, "test_id": test_id})

    def _resolve_test_action(self, action: dict[str, Any]) -> EventRecord:
        test_id = str(action.get("test_id", action.get("objective_id", "test")))
        result = str(action.get("result", "success"))
        self.full_state["active_test"] = {"test_id": test_id, "result": result, "difficulty": action.get("difficulty")}
        self._unlock("first_test_resolved")
        if result == "success":
            self._unlock("pass_test")
        return self._append_nev(kind=EventKind.TEST_RESOLVED, message=f"TestResolved({test_id},{result})", action=action, payload={"test_id": test_id, "result": result})

    def _resolve_challenge(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", "synthetic_challenge"))
        challenge = self._challenge_card(card_id)
        modifier = int(action.get("modifier", challenge.get("modifier", 0)))
        effects = list(action.get("effects") if "effects" in action else challenge.get("effects", []))
        self.full_state["challenge_discard"].append({"card_id": card_id, "modifier": modifier})
        self._append_nev(kind=EventKind.CHALLENGE_REVEALED, message=f"ChallengeRevealed({card_id},{modifier})", action=action, payload={"card_id": card_id, "modifier": modifier})
        self._apply_effect_list(effects, action, source=f"challenge:{card_id}", label=f"ChallengeEffect({card_id})")
        return self._append_nev(kind=EventKind.CHALLENGE_EFFECT_RESOLVED, message=f"ChallengeEffectResolved({card_id})", action=action, payload={"card_id": card_id, "effects": effects})

    def _set_ready_state(self, action: dict[str, Any], *, ready: bool) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        self.full_state["ready_state"][card_id] = ready
        kind = EventKind.CARD_READIED if ready else EventKind.CARD_EXHAUSTED
        label = "CardReadied" if ready else "CardExhausted"
        return self._append_nev(kind=kind, message=f"{label}({card_id})", action=action, payload={"card_id": card_id, "ready": ready})

    def _build_path_deck(self, action: dict[str, Any]) -> EventRecord:
        path_set = self._path_set_for_action(action)
        cards = list(action.get("cards") if "cards" in action else path_set.get("cards", []))
        terrain_sets = list(action.get("terrain_sets") if "terrain_sets" in action else path_set.get("terrain_sets", path_set.get("terrain", [])))
        self.full_state["path_deck"] = cards
        self.full_state["terrain_sets"] = terrain_sets
        return self._append_nev(kind=EventKind.PATH_DECK_BUILT, message=f"PathDeckBuilt({len(cards)})", action=action, payload={"cards": cards, "terrain_sets": terrain_sets})

    def _draw_path_card(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id") or (self.full_state["path_deck"].pop(0) if self.full_state["path_deck"] else ""))
        if card_id:
            self.full_state["path_discard"].append(card_id)
        return self._append_nev(kind=EventKind.PATH_CARD_REVEALED, message=f"PathCardRevealed({card_id})", action=action, payload={"card_id": card_id})

    def _place_path_card(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        zone = str(action.get("zone", "within_reach"))
        kind = str(action.get("kind", "path"))
        self.full_state.setdefault(zone, []).append(card_id)
        self.full_state["world_cards"][card_id] = {"zone": zone, "kind": kind}
        traits = []
        if self.resolved and card_id in self.resolved.cards:
            card = self.resolved.cards[card_id]
            traits = list(card.get("traits") or card.get("tags") or [])
        if not traits:
            traits = list(action.get("traits") or [])
        if traits:
            self.full_state["traits"][card_id] = traits
        if kind == "obstacle" or "obstacle" in traits or bool(action.get("obstacle", False)):
            if card_id not in self.full_state["obstacles"]:
                self.full_state["obstacles"].append(card_id)
        self._append_nev(kind=EventKind.PATH_CARD_PLACED, message=f"PathCardPlaced({card_id},{zone})", action=action, payload={"card_id": card_id, "zone": zone})
        record = self._append_nev(kind=EventKind.WORLD_CARD_ENTERED, message=f"WorldCardEntered({card_id},{zone})", action=action, payload={"card_id": card_id, "zone": zone})
        if self.resolved and card_id in self.resolved.cards:
            effects = list(self.resolved.cards[card_id].get("effects") or [])
            self._apply_effect_list(effects, action, source=f"world:{card_id}", label=f"WorldCardEffect({card_id})")
        return record

    def _check_range(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        reachable = bool(action.get("reachable", card_id in self.full_state["within_reach"]))
        if not reachable and bool(action.get("blocked_by_obstacle", False)):
            self.private.obstacle_blocked_seen = True
            self._append_nev(kind=EventKind.OBSTACLE_BLOCKED, message=f"ObstacleBlocked({card_id})", action=action, payload={"card_id": card_id})
        return self._append_nev(kind=EventKind.RANGE_CHECKED, message=f"RangeChecked({card_id},{reachable})", action=action, payload={"card_id": card_id, "reachable": reachable})

    def _travel(self, location_id: str, action: dict[str, Any]) -> EventRecord:
        if not self.resolved or location_id not in self.resolved.locations:
            return self._rule_violation(action, f"unknown_location:{location_id}")
        previous = _public_from_dict(self.public.to_dict())
        self.public.location_id = location_id
        fatigue = int(self.resolved.locations[location_id].get("travel_fatigue", 0))
        if fatigue:
            self._take_fatigue(fatigue, action, f"TravelFatigue({location_id},{fatigue})")
        self._unlock("first_travel")
        if self.private.obstacle_blocked_seen:
            self._unlock("clear_obstacle")
        record = self._append_nev(
            kind=EventKind.LOCATION_CHANGED,
            message=f"LocationChanged({location_id})",
            action=action,
            transition=self.public.diff(previous),
            payload={"location_id": location_id, "travel_fatigue": fatigue},
        )
        effects = list(self.resolved.locations[location_id].get("effects") or [])
        self._apply_effect_list(effects, action, source=f"location:{location_id}", label=f"LocationEffect({location_id})")
        return record

    def _attach_card(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        target_id = str(action.get("target_id", ""))
        self.full_state["attachments"].append({"card_id": card_id, "target_id": target_id})
        return self._append_nev(kind=EventKind.ATTACHMENT_ADDED, message=f"AttachmentAdded({card_id},{target_id})", action=action, payload={"card_id": card_id, "target_id": target_id})

    def _token_action(self, action: dict[str, Any], bucket: str, kind: EventKind, label: str) -> EventRecord:
        card_id = str(action.get("card_id", action.get("objective_id", "")))
        amount = int(action.get("amount", 1))
        current = int(self.full_state[bucket].get(card_id, 0))
        self.full_state[bucket][card_id] = current + amount
        return self._append_nev(kind=kind, message=f"{label}({card_id},{amount})", action=action, payload={"card_id": card_id, "amount": amount, "total": self.full_state[bucket][card_id]})

    def _clear_card(self, action: dict[str, Any]) -> EventRecord:
        card_id = str(action.get("card_id", ""))
        self.full_state["world_cards"].pop(card_id, None)
        if card_id not in self.full_state["path_discard"]:
            self.full_state["path_discard"].append(card_id)
        for zone in ("within_reach", "along_the_way", "nearby"):
            if card_id in self.full_state[zone]:
                self.full_state[zone].remove(card_id)
        self._unlock("clear_path_card")
        return self._append_nev(kind=EventKind.CARD_CLEARED, message=f"CardCleared({card_id})", action=action, payload={"card_id": card_id})

    def _test_objective(self, objective_id: str, action: dict[str, Any]) -> EventRecord:
        if objective_id not in self.private.objective_targets:
            return self._rule_violation(action, f"unknown_objective:{objective_id}")
        fatigue = 1 if self.public.fatigue >= 3 else 0
        if fatigue:
            self._take_fatigue(fatigue, action, f"TestFatigue({objective_id},{fatigue})")
        record = self._append_nev(
            kind=EventKind.TEST_RESOLVED,
            message=f"TestResolved({objective_id},success)",
            action=action,
            payload={"objective_id": objective_id, "success": True, "fatigue_penalty": fatigue},
        )
        self._unlock("first_test_resolved")
        self._unlock("pass_test")
        self._apply_progress(objective_id, 1, action, source="test")
        return record

    def _interact(self, objective_id: str, action: dict[str, Any]) -> EventRecord:
        expected = self.private.objective_locations.get(objective_id)
        if expected is None:
            return self._rule_violation(action, f"unknown_objective:{objective_id}")
        if expected != self.public.location_id:
            return self._rule_violation(action, f"wrong_location:{objective_id}:{self.public.location_id}")
        record = self._append_nev(
            kind=EventKind.TEST_RESOLVED,
            message=f"TestResolved({objective_id},interact)",
            action=action,
            payload={"objective_id": objective_id, "success": True, "mode": "interact"},
        )
        self._unlock("first_test_resolved")
        self._unlock("pass_test")
        self._apply_progress(objective_id, 1, action, source="interact")
        return record

    def _write_note(self, text: str, action: dict[str, Any]) -> EventRecord:
        enabled = bool(self.resolved and self.resolved.reflexion.get("enabled"))
        if not enabled:
            return self._rule_violation(action, "strategy_notes_disabled")
        note = text[:240]
        self.private.strategy_notes.append(note)
        self.full_state["strategy_notes"].append(note)
        self._unlock("write_reflection")
        return self._append_nev(
            kind=EventKind.STRATEGY_NOTE_WRITTEN,
            message=f"StrategyNoteWritten({len(self.private.strategy_notes)})",
            action=action,
            payload={"note_index": len(self.private.strategy_notes) - 1, "text": note},
        )

    def _expose_reflection_action(self, action: dict[str, Any]) -> EventRecord:
        record = {
            "index": len(self.private.exposed_reflections),
            "kind": str(action.get("kind", "reflection")),
            "text": str(action.get("text", ""))[:500],
        }
        self.private.exposed_reflections.append(record)
        self.full_state["reflection_exposures"].append(record)
        return self._append_nev(
            kind=EventKind.REFLECTION_EXPOSED,
            message=f"ReflectionExposed({record['kind']},{record['index']})",
            action=action,
            payload=record,
        )

    def _end_day(self, action: dict[str, Any]) -> EventRecord:
        ended_day = self.public.day
        self.public.day += 1
        self.public.time = 0
        self.public.play_area.clear()
        if self.public.day > (self.resolved.max_days if self.resolved else 5):
            self.private.truncated = True
            self.public.done = True
        self._unlock("complete_day")
        if ended_day >= 3:
            self._unlock("complete_day_three")
        if self.public.fatigue == 0:
            self._unlock("zero_fatigue_day")
        if self.private.illegal_action_count == self.private.day_start_illegal_count:
            self._unlock("day_no_violation")
        return self._append_nev(
            kind=EventKind.DAY_ENDED,
            message=f"DayEnded({self.public.day - 1})",
            action=action,
            payload={"day": self.public.day - 1, "next_day": self.public.day},
        )

    def _round_event(self, action: dict[str, Any], kind: EventKind, label: str) -> EventRecord:
        self.full_state["round"] = int(self.full_state.get("round", 1))
        return self._append_nev(kind=kind, message=f"{label}({self.full_state['round']})", action=action, payload={"round": self.full_state["round"]})

    def _rest(self, action: dict[str, Any]) -> EventRecord:
        ranger_id = str(action.get("ranger_id", self.full_state.get("active_ranger") or self.public.ranger_id))
        if ranger_id not in self.full_state["rested_rangers"]:
            self.full_state["rested_rangers"].append(ranger_id)
        self._append_nev(kind=EventKind.RANGER_RESTED, message=f"RangerRested({ranger_id})", action=action, payload={"ranger_id": ranger_id})
        return self._recover_fatigue(2, action, "Rest")

    def _refresh(self, action: dict[str, Any]) -> EventRecord:
        self.full_state["round"] = int(self.full_state.get("round", 1)) + 1
        self.full_state["ready_queue"] = []
        self.full_state["refresh_queue"] = []
        return self._append_nev(kind=EventKind.REFRESH_COMPLETED, message=f"RefreshCompleted({self.full_state['round']})", action=action, payload={"round": self.full_state["round"]})

    def _choose_travel(self, action: dict[str, Any]) -> EventRecord:
        location_id = str(action.get("location_id", self.public.location_id))
        self.full_state["travel_progress"][location_id] = int(action.get("progress", self.full_state["travel_progress"].get(location_id, 0)))
        self._append_nev(kind=EventKind.TRAVEL_AVAILABLE, message=f"TravelAvailable({location_id})", action=action, payload={"location_id": location_id})
        self.full_state["current_location"] = location_id
        self.full_state["shared_location"] = location_id
        self.public.location_id = location_id
        return self._append_nev(kind=EventKind.TRAVEL_COMPLETED, message=f"TravelCompleted({location_id})", action=action, payload={"location_id": location_id})

    def _resolve_trigger(self, action: dict[str, Any]) -> EventRecord:
        trigger_id = str(action.get("trigger_id", f"trigger_{len(self.full_state['trigger_queue'])}"))
        self.full_state["trigger_queue"].append({"trigger_id": trigger_id, "source": action.get("source")})
        return self._append_nev(kind=EventKind.TRIGGER_QUEUED, message=f"TriggerQueued({trigger_id})", action=action, payload={"trigger_id": trigger_id})

    def _choose_option(self, action: dict[str, Any]) -> EventRecord:
        choice_id = str(action.get("choice_id", "choice"))
        option_id = str(action.get("option_id", "option"))
        self.full_state["choice_prompts"].append({"choice_id": choice_id, "option_id": option_id})
        self._append_nev(kind=EventKind.CHOICE_PRESENTED, message=f"ChoicePresented({choice_id})", action=action, payload={"choice_id": choice_id})
        return self._append_nev(kind=EventKind.CHOICE_RESOLVED, message=f"ChoiceResolved({choice_id},{option_id})", action=action, payload={"choice_id": choice_id, "option_id": option_id})

    def _apply_effect(self, action: dict[str, Any]) -> EventRecord:
        effect_id = str(action.get("effect_id", "effect"))
        bucket = str(action.get("bucket", "persistent_effects"))
        if bucket not in self.full_state:
            bucket = "persistent_effects"
        payload = dict(action.get("payload", {}) or {})
        self.full_state[bucket].append({"effect_id": effect_id, "payload": payload})
        if bucket == "replacement_effects":
            self._append_nev(kind=EventKind.REPLACEMENT_APPLIED, message=f"ReplacementApplied({effect_id})", action=action, payload={"effect_id": effect_id})
        if "keyword" in payload:
            keyword = str(payload["keyword"])
            self.full_state["keywords"][keyword] = payload
            self._append_nev(kind=EventKind.KEYWORD_RESOLVED, message=f"KeywordResolved({keyword})", action=action, payload={"keyword": keyword, "effect_id": effect_id})
        if "reward_id" in payload:
            reward_id = str(payload["reward_id"])
            self.full_state["reward_pool"].append(reward_id)
            self._append_nev(kind=EventKind.REWARD_ADDED, message=f"RewardAdded({reward_id})", action=action, payload={"reward_id": reward_id, "effect_id": effect_id})
        return self._append_nev(kind=EventKind.EFFECT_RESOLVED, message=f"EffectResolved({effect_id})", action=action, payload={"effect_id": effect_id, "bucket": bucket})

    def _apply_effect_list(self, effects: list[Any], action: dict[str, Any], *, source: str, label: str) -> None:
        for index, effect in enumerate(effects):
            if not isinstance(effect, dict):
                self._append_nev(
                    kind=EventKind.EFFECT_RESOLVED,
                    message=f"EffectResolved({label}:{index})",
                    action=action,
                    payload={"source": source, "index": index, "raw": effect},
                )
                continue
            kind = str(effect.get("kind", "effect"))
            amount = int(effect.get("amount", 1))
            if kind == "fatigue":
                self._take_fatigue(amount, action, f"{label}:Fatigue({amount})")
            elif kind == "recover":
                self._recover_fatigue(amount, action, f"{label}:Recovered({amount})")
            elif kind == "progress":
                objective_id = str(effect.get("objective_id") or self._nearest_incomplete_objective())
                self._apply_progress(objective_id, amount, action, source=source)
            elif kind in ("add_progress", "progress_token"):
                self._effect_token(action, effect, "progress_tokens", EventKind.PROGRESS_ADDED, "ProgressAdded")
            elif kind in ("harm", "add_harm"):
                self._effect_token(action, effect, "harm_tokens", EventKind.HARM_ADDED, "HarmAdded")
            elif kind in ("presence", "change_presence"):
                self._effect_token(action, effect, "presence_tokens", EventKind.PRESENCE_CHANGED, "PresenceChanged")
            elif kind in ("energy", "spend_energy"):
                self._spend_energy({"type": "spend_energy", "aspect": effect.get("aspect", "any"), "amount": amount})
            elif kind in ("gain_energy", "set_energy"):
                aspect = str(effect.get("aspect", "any"))
                current = int(self.full_state["aspect_energy"].get(aspect, 0))
                total = amount if kind == "set_energy" else current + amount
                self.full_state["aspect_energy"][aspect] = total
                label_kind = "EnergySet" if kind == "set_energy" else "EnergyGained"
                self._append_nev(kind=EventKind.EFFECT_RESOLVED, message=f"{label_kind}({aspect},{amount})", action=action, payload={"kind": kind, "aspect": aspect, "amount": amount, "total": total, "source": source})
            elif kind == "draw":
                for _ in range(max(0, amount)):
                    self._draw_card({"type": "draw", "source": source})
            elif kind == "discard":
                self._discard_card({"type": "discard", "card_id": effect.get("card_id", ""), "source": source})
            elif kind in ("remove_progress", "remove_progress_token"):
                reversed_effect = dict(effect)
                reversed_effect["amount"] = -amount
                self._effect_token(action, reversed_effect, "progress_tokens", EventKind.PROGRESS_ADDED, "ProgressAdded")
            elif kind in ("remove_harm", "heal_harm"):
                reversed_effect = dict(effect)
                reversed_effect["amount"] = -amount
                self._effect_token(action, reversed_effect, "harm_tokens", EventKind.HARM_ADDED, "HarmAdded")
            elif kind in ("remove_presence", "reduce_presence"):
                reversed_effect = dict(effect)
                reversed_effect["amount"] = -amount
                self._effect_token(action, reversed_effect, "presence_tokens", EventKind.PRESENCE_CHANGED, "PresenceChanged")
            elif kind == "exhaust":
                self._set_ready_state({"type": "exhaust", "card_id": effect.get("card_id", ""), "source": source}, ready=False)
            elif kind == "ready":
                self._set_ready_state({"type": "ready", "card_id": effect.get("card_id", ""), "source": source}, ready=True)
            elif kind == "attach":
                self._attach_card({"type": "attach_card", "card_id": effect.get("card_id", ""), "target_id": effect.get("target_id", ""), "source": source})
            elif kind in ("place_card", "place_path", "place_world"):
                self._place_path_card(
                    {
                        "type": "place_path_card",
                        "card_id": effect.get("card_id", effect.get("target_id", "")),
                        "zone": effect.get("zone", "within_reach"),
                        "kind": effect.get("card_kind", effect.get("kind_name", "path")),
                        "source": source,
                    }
                )
            elif kind in ("clear", "clear_card"):
                self._clear_card({"type": "clear_card", "card_id": effect.get("card_id", effect.get("target_id", "")), "source": source})
            elif kind == "move_card":
                card_id = str(effect.get("card_id", effect.get("target_id", "")))
                to_zone = str(effect.get("to_zone", effect.get("zone", "within_reach")))
                for zone in ("within_reach", "along_the_way", "nearby"):
                    while card_id in self.full_state[zone]:
                        self.full_state[zone].remove(card_id)
                self.full_state.setdefault(to_zone, []).append(card_id)
                self.full_state["world_cards"].setdefault(card_id, {})["zone"] = to_zone
                self._append_nev(kind=EventKind.EFFECT_RESOLVED, message=f"CardMoved({card_id},{to_zone})", action=action, payload={"kind": kind, "card_id": card_id, "to_zone": to_zone, "source": source})
            elif kind == "travel_progress":
                location_id = str(effect.get("location_id", effect.get("target_id", self.public.location_id)))
                current = int(self.full_state["travel_progress"].get(location_id, 0))
                total = current + amount
                self.full_state["travel_progress"][location_id] = total
                self._append_nev(kind=EventKind.EFFECT_RESOLVED, message=f"TravelProgress({location_id},{amount})", action=action, payload={"kind": kind, "location_id": location_id, "amount": amount, "total": total, "source": source})
            elif kind == "keyword":
                keyword = str(effect.get("keyword", effect.get("value", "")))
                self.full_state["keywords"][keyword] = dict(effect)
                self._append_nev(kind=EventKind.KEYWORD_RESOLVED, message=f"KeywordResolved({keyword})", action=action, payload={"keyword": keyword, "source": source})
            elif kind == "reward":
                reward_id = str(effect.get("reward_id", effect.get("id", "")))
                self.full_state["reward_pool"].append(reward_id)
                self._append_nev(kind=EventKind.REWARD_ADDED, message=f"RewardAdded({reward_id})", action=action, payload={"reward_id": reward_id, "source": source})
            elif kind == "trigger":
                trigger_id = str(effect.get("trigger_id", effect.get("id", f"{source}:{index}")))
                self.full_state["trigger_queue"].append({"trigger_id": trigger_id, "source": source})
                self._append_nev(kind=EventKind.TRIGGER_QUEUED, message=f"TriggerQueued({trigger_id})", action=action, payload={"trigger_id": trigger_id})
            elif kind == "replacement":
                replacement_id = str(effect.get("replacement_id", effect.get("id", f"{source}:{index}")))
                self.full_state["replacement_effects"].append({"effect_id": replacement_id, "payload": dict(effect)})
                self._append_nev(kind=EventKind.REPLACEMENT_APPLIED, message=f"ReplacementApplied({replacement_id})", action=action, payload={"effect_id": replacement_id})
            elif kind in ("delayed", "delay"):
                effect_id = str(effect.get("effect_id", effect.get("id", f"{source}:{index}")))
                self.full_state["delayed_effects"].append({"effect_id": effect_id, "payload": dict(effect)})
                self._append_nev(kind=EventKind.EFFECT_RESOLVED, message=f"DelayedEffect({effect_id})", action=action, payload={"kind": kind, "effect_id": effect_id, "source": source})
            elif kind == "choice":
                choice_id = str(effect.get("choice_id", effect.get("id", f"{source}:{index}")))
                options = list(effect.get("options", []))
                self.full_state["choice_prompts"].append({"choice_id": choice_id, "options": options, "source": source})
                self._append_nev(kind=EventKind.CHOICE_PRESENTED, message=f"ChoicePresented({choice_id})", action=action, payload={"choice_id": choice_id, "options": options})
            elif kind in ("mission_state", "campaign_state"):
                mission_id = str(effect.get("mission_id", effect.get("id", f"{source}:{index}")))
                state = str(effect.get("state", "active"))
                self.full_state["mission_states"][mission_id] = state
                self._append_nev(kind=EventKind.MISSION_STATE_CHANGED, message=f"MissionStateChanged({mission_id},{state})", action=action, payload={"mission_id": mission_id, "state": state})
            else:
                self.full_state["persistent_effects"].append({"effect_id": f"{source}:{index}", "payload": dict(effect)})
                self._append_nev(kind=EventKind.EFFECT_RESOLVED, message=f"EffectResolved({kind})", action=action, payload={"kind": kind, "source": source, "effect": dict(effect)})

    def _effect_token(self, action: dict[str, Any], effect: dict[str, Any], bucket: str, kind: EventKind, label: str) -> None:
        card_id = str(effect.get("card_id", effect.get("target_id", effect.get("objective_id", ""))))
        amount = int(effect.get("amount", 1))
        current = int(self.full_state[bucket].get(card_id, 0))
        self.full_state[bucket][card_id] = current + amount
        self._append_nev(kind=kind, message=f"{label}({card_id},{amount})", action=action, payload={"card_id": card_id, "amount": amount, "total": self.full_state[bucket][card_id]})

    def _set_active_ranger(self, action: dict[str, Any]) -> EventRecord:
        ranger_id = str(action.get("ranger_id", self.public.ranger_id))
        self.full_state["active_ranger"] = ranger_id
        if ranger_id not in self.full_state["turn_order"]:
            self.full_state["turn_order"].append(ranger_id)
        return self._append_nev(kind=EventKind.ACTIVE_RANGER_CHANGED, message=f"ActiveRangerChanged({ranger_id})", action=action, payload={"ranger_id": ranger_id})

    def _assist_test(self, action: dict[str, Any]) -> EventRecord:
        ranger_id = str(action.get("ranger_id", self.full_state.get("active_ranger", self.public.ranger_id)))
        card_id = str(action.get("card_id", ""))
        return self._append_nev(kind=EventKind.ASSIST_COMMITTED, message=f"AssistCommitted({ranger_id},{card_id})", action=action, payload={"ranger_id": ranger_id, "card_id": card_id})

    def _move_ranger_area(self, action: dict[str, Any]) -> EventRecord:
        ranger_id = str(action.get("ranger_id", self.public.ranger_id))
        area = str(action.get("area", "within_reach"))
        self.full_state["ranger_local_areas"][ranger_id] = area
        self.full_state["within_reach_by_ranger"].setdefault(ranger_id, [])
        return self._append_nev(kind=EventKind.RANGER_AREA_CHANGED, message=f"RangerAreaChanged({ranger_id},{area})", action=action, payload={"ranger_id": ranger_id, "area": area})

    def _complete_attempt(self, action: dict[str, Any]) -> EventRecord:
        self.full_state["attempt_index"] = int(action.get("attempt_index", self.full_state.get("attempt_index", 0)))
        self.full_state["event_log_hash"] = "sha256:" + hashlib.sha256("|".join(self.nev.legacy_strings()).encode("utf-8")).hexdigest()
        self._append_nev(kind=EventKind.SCORE_SUMMARY_EMITTED, message=f"ScoreSummaryEmitted({self.full_state['attempt_index']})", action=action, payload={"score_components": self.full_state.get("score_components", {})})
        return self._append_nev(kind=EventKind.ATTEMPT_COMPLETED, message=f"AttemptCompleted({self.full_state['attempt_index']})", action=action, payload={"attempt_index": self.full_state["attempt_index"]})

    def _apply_progress(self, objective_id: str, amount: int, action: dict[str, Any], *, source: str) -> None:
        if not objective_id or objective_id in self.public.objectives_completed:
            return
        before = self.public.objective_progress.get(objective_id, 0)
        target = self.private.objective_targets[objective_id]
        after = min(target, before + amount)
        self.public.objective_progress[objective_id] = after
        self.private.reward_last += amount
        self.private.total_reward += amount
        self._append_nev(
            kind=EventKind.OBJECTIVE_PROGRESS,
            message=f"ObjectiveProgress({objective_id},{after}/{target})",
            action=action,
            payload={"objective_id": objective_id, "from": before, "to": after, "target": target, "source": source},
        )
        if after > before:
            self._unlock("first_objective_progress")
        if after >= target and objective_id not in self.public.objectives_completed:
            self.public.objectives_completed.append(objective_id)
            self.private.reward_last += 5.0
            self.private.total_reward += 5.0
            self._append_nev(
                kind=EventKind.OBJECTIVE_COMPLETED,
                message=f"ObjectiveCompleted({objective_id})",
                action=action,
                payload={"objective_id": objective_id},
            )
            self._unlock("complete_objective")
            if len(self.public.objectives_completed) >= 3:
                self._unlock("complete_three_objectives")
            if len(self.public.objectives_completed) == len(self.private.objective_targets):
                self.private.terminated = True
                self.public.done = True
                self._unlock("all_objectives")
                if self.private.illegal_action_count == 0:
                    self._unlock("flawless_episode")
                self._append_nev(
                    kind=EventKind.CAMPAIGN_SEGMENT_COMPLETED,
                    message=f"CampaignSegmentCompleted({len(self.public.objectives_completed)})",
                    payload={"objectives_completed": list(self.public.objectives_completed)},
                )
                self._append_nev(kind=EventKind.TERMINAL, message="Terminal(success)", payload={"reason": "success"})

    def _take_fatigue(self, amount: int, action: dict[str, Any], message: str) -> EventRecord:
        self.public.fatigue += amount
        self.private.fatigue_taken += amount
        self.private.reward_last -= amount * 0.25
        self.private.total_reward -= amount * 0.25
        return self._append_nev(
            kind=EventKind.FATIGUE_TAKEN,
            message=message,
            action=action,
            payload={"amount": amount, "fatigue": self.public.fatigue},
        )

    def _recover_fatigue(self, amount: int, action: dict[str, Any], prefix: str) -> EventRecord:
        recovered = min(amount, self.public.fatigue)
        self.public.fatigue -= recovered
        self.private.fatigue_recovered += recovered
        self.private.reward_last += recovered * 0.15
        self.private.total_reward += recovered * 0.15
        if recovered > 0:
            self._unlock("recover_fatigue")
        message = prefix if "(" in prefix else f"{prefix}Recovered({recovered})"
        return self._append_nev(
            kind=EventKind.FATIGUE_RECOVERED,
            message=message,
            action=action,
            payload={"amount": recovered, "fatigue": self.public.fatigue},
        )

    def _rule_violation(self, action: dict[str, Any], reason: str) -> EventRecord:
        self.private.illegal_action_count += 1
        self.private.reward_last = -1.0
        self.private.total_reward -= 1.0
        return self._append_nev(
            kind=EventKind.RULE_VIOLATION,
            severity=EventSeverity.ERROR,
            message=f"RuleViolation({reason})",
            action=action,
            payload={"reason": reason},
        )

    def _check_limits(self) -> None:
        if self.private.terminated or self.private.truncated:
            return
        if self.resolved and self.private.step_index >= self.resolved.max_steps:
            self.private.truncated = True
            self.public.done = True
            self._append_nev(
                kind=EventKind.TERMINAL,
                message="Terminal(truncated)",
                payload={"reason": "max_steps", "max_steps": self.resolved.max_steps},
            )

    def _nearest_incomplete_objective(self) -> str:
        for objective_id in self.private.objective_targets:
            if objective_id not in self.public.objectives_completed:
                return objective_id
        return next(iter(self.private.objective_targets))

    def _expose_reflections(self, reflexion: dict[str, Any]) -> None:
        exposures = list(reflexion.get("exposures") or [])
        for index, exposure in enumerate(exposures):
            record = {"index": index, "kind": str(exposure.get("kind", "reflection")), "text": str(exposure.get("text", ""))[:500]}
            self.private.exposed_reflections.append(record)
            self.full_state["reflection_exposures"].append(record)
            self._append_nev(
                kind=EventKind.REFLECTION_EXPOSED,
                message=f"ReflectionExposed({record['kind']},{index})",
                payload=record,
            )

    def _challenge_card(self, card_id: str) -> dict[str, Any]:
        if not self.resolved:
            return {}
        for card in _rows_from_table(self.resolved.resolved_json.get("challenge_deck")):
            if str(card.get("id")) == card_id:
                return card
        return {}

    def _unlock(self, name: str) -> None:
        if name not in EBR_ACHIEVEMENTS:
            raise ValueError(f"unknown achievement: {name!r}")
        if self.public.achievements.get(name, 0) > 0:
            return
        self.public.achievements[name] = 1
        self.private.achievements.add(name)
        delta = self._achievement_reward(name)
        self.private.reward_last += delta
        self.private.total_reward += delta
        self._append_achievement(name)

    def _achievement_reward(self, name: str) -> float:
        scale = 1.0
        if self.resolved:
            scale = float(self.resolved.rules.get("achievement_reward", 1.0))
        if name in VERY_ADVANCED_ACHIEVEMENTS:
            return 8.0 * scale
        if name in INTERMEDIATE_ACHIEVEMENTS:
            return 3.0 * scale
        return 1.0 * scale

    def _append_achievement(self, name: str) -> None:
        self._append_nev(
            kind=EventKind.ACHIEVEMENT_UNLOCKED,
            message=f"AchievementUnlocked({name})",
            transition={"achievement": name},
            payload={"achievement": name},
        )

    def _validate_achievement_state(self) -> None:
        public_unlocked = {
            name
            for name, count in self.public.achievements.items()
            if int(count) > 0
        }
        unknown_public = sorted(public_unlocked - set(EBR_ACHIEVEMENTS))
        if unknown_public:
            raise ValueError(f"unknown public achievement: {unknown_public[0]!r}")
        unknown_private = sorted(set(self.private.achievements) - set(EBR_ACHIEVEMENTS))
        if unknown_private:
            raise ValueError(f"unknown private achievement: {unknown_private[0]!r}")
        if public_unlocked != self.private.achievements:
            raise ValueError("public/private achievement sets do not match")
        for event in self.nev.export():
            if event.get("kind") != EventKind.ACHIEVEMENT_UNLOCKED.value:
                continue
            payload_name = (event.get("payload") or {}).get("achievement")
            transition_name = (event.get("transition") or {}).get("achievement")
            if payload_name not in EBR_ACHIEVEMENTS:
                raise ValueError(f"unknown achievement event: {payload_name!r}")
            if payload_name != transition_name:
                raise ValueError("achievement transition does not match payload")

    def _path_set_for_action(self, action: dict[str, Any]) -> dict[str, Any]:
        if not self.resolved:
            return {}
        path_sets = _rows_from_table(self.resolved.resolved_json.get("path_sets"))
        path_set_id = action.get("path_set_id")
        if path_set_id is None:
            location_id = str(action.get("location_id", self.public.location_id))
            location = self.resolved.locations.get(location_id, {})
            refs = list(location.get("path_set_refs", []))
            path_set_id = refs[0] if refs else None
        if path_set_id is not None:
            for path_set in path_sets:
                if str(path_set.get("id")) == str(path_set_id):
                    return path_set
        return {}

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


def _rows_from_table(table: Any) -> list[dict[str, Any]]:
    if isinstance(table, dict):
        return [dict(value, id=key) if isinstance(value, dict) and "id" not in value else dict(value) for key, value in table.items() if isinstance(value, dict)]
    if isinstance(table, list):
        return [dict(value) for value in table if isinstance(value, dict)]
    return []


def _public_from_dict(data: dict[str, Any]) -> PublicState:
    achievements = {str(key): int(value) for key, value in dict(data.get("achievements", {})).items()}
    for name in achievements:
        if name not in EBR_ACHIEVEMENTS:
            raise ValueError(f"unknown public achievement: {name!r}")
    return PublicState(
        ranger_id=str(data["ranger_id"]),
        archetype=data.get("archetype"),
        location_id=str(data["location_id"]),
        day=int(data["day"]),
        time=int(data["time"]),
        fatigue=int(data["fatigue"]),
        hand=list(data["hand"]),
        play_area=list(data["play_area"]),
        discard=list(data["discard"]),
        objectives_completed=list(data["objectives_completed"]),
        objective_progress={key: int(value) for key, value in data["objective_progress"].items()},
        achievements=achievements,
        done=bool(data.get("done", False)),
    )


def _default_full_state() -> dict[str, Any]:
    return {
        "active_ranger": None,
        "active_test": None,
        "along_the_way": [],
        "aspect_card": None,
        "aspect_energy": {},
        "attachments": [],
        "attempt_index": 0,
        "campaign_log": [],
        "challenge_discard": [],
        "choice_prompts": [],
        "committed_cards": [],
        "current_location": "trailhead",
        "day": 1,
        "delayed_effects": [],
        "discard": [],
        "event_log_hash": None,
        "fatigue_stack": [],
        "hand": [],
        "harm_tokens": {},
        "injuries": [],
        "keywords": {},
        "maladies": [],
        "mission_states": {},
        "nearby": [],
        "obstacles": [],
        "path_deck": [],
        "path_discard": [],
        "persistent_effects": [],
        "presence_tokens": {},
        "progress_tokens": {},
        "ranger_deck": [],
        "ranger_identity": None,
        "ranger_local_areas": {},
        "rangers": [],
        "ready_queue": [],
        "ready_state": {},
        "reflection_exposures": [],
        "refresh_queue": [],
        "replacement_effects": [],
        "rested_rangers": [],
        "reward_pool": [],
        "role": None,
        "round": 1,
        "score_components": {},
        "session": None,
        "setup_cards": [],
        "shared_location": "trailhead",
        "strategy_notes": [],
        "terrain_sets": [],
        "traits": {},
        "travel_progress": {},
        "trigger_queue": [],
        "turn_order": [],
        "within_reach": [],
        "within_reach_by_ranger": {},
        "world_cards": {},
    }


def _private_from_dict(data: dict[str, Any]) -> PrivateState:
    achievements = {str(name) for name in data.get("achievements", [])}
    for name in achievements:
        if name not in EBR_ACHIEVEMENTS:
            raise ValueError(f"unknown private achievement: {name!r}")
    return PrivateState(
        episode_id=str(data["episode_id"]),
        task_id=str(data["task_id"]),
        scenario_id=str(data["scenario_id"]),
        seed=int(data["seed"]),
        config_hash=str(data["config_hash"]),
        step_index=int(data["step_index"]),
        deck=list(data.get("deck", [])),
        deck_index=int(data.get("deck_index", 0)),
        objective_targets={key: int(value) for key, value in data.get("objective_targets", {}).items()},
        objective_locations={key: str(value) for key, value in data.get("objective_locations", {}).items()},
        fatigue_taken=int(data.get("fatigue_taken", 0)),
        fatigue_recovered=int(data.get("fatigue_recovered", 0)),
        illegal_action_count=int(data.get("illegal_action_count", 0)),
        cards_played=list(data.get("cards_played", [])),
        strategy_notes=list(data.get("strategy_notes", [])),
        exposed_reflections=list(data.get("exposed_reflections", [])),
        achievements=achievements,
        obstacle_blocked_seen=bool(data.get("obstacle_blocked_seen", False)),
        day_start_illegal_count=int(data.get("day_start_illegal_count", 0)),
        reward_last=float(data.get("reward_last", 0.0)),
        total_reward=float(data.get("total_reward", 0.0)),
        objective_count=int(data.get("objective_count", 0)),
        terminated=bool(data.get("terminated", False)),
        truncated=bool(data.get("truncated", False)),
    )
