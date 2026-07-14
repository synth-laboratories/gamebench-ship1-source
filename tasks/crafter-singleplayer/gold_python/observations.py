"""Crafter symbolic readouts and policy-facing observation text."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any


def grid_hash(observation: dict[str, Any]) -> str:
    world = observation.get("world", {})
    if world.get("tiles"):
        tiles = sorted(world["tiles"], key=lambda item: (item["pos"][1], item["pos"][0]))
    else:
        tiles = sorted(observation.get("view", {}).get("tiles", []), key=lambda item: (item["pos"][1], item["pos"][0]))
    payload = "|".join(f"{tile['pos'][0]},{tile['pos'][1]}:{tile['kind']}" for tile in tiles)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def local_tile_counts(observation: dict[str, Any]) -> dict[str, int]:
    return dict(Counter(str(tile.get("kind", "unknown")) for tile in observation.get("view", {}).get("tiles", [])))


def front_tile(observation: dict[str, Any]) -> dict[str, Any] | None:
    player = observation.get("player", {})
    pos = player.get("pos", [0, 0])
    facing = player.get("facing", [0, 1])
    target = [int(pos[0]) + int(facing[0]), int(pos[1]) + int(facing[1])]
    for tile in observation.get("view", {}).get("tiles", []):
        if tile.get("pos") == target:
            return tile
    return None


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_kind_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    reward_source_totals: Counter[str] = Counter()
    reward_component_totals: Counter[str] = Counter()
    terminal: dict[str, Any] | None = None

    for event in events:
        kind = str(event.get("kind", "unknown"))
        event_kind_counts[kind] += 1
        severity_counts[str(event.get("severity", "unknown"))] += 1
        action = event.get("action")
        if action:
            action_counts[str(action)] += 1
        transition = event.get("transition")
        if isinstance(transition, dict):
            for key in transition:
                transition_counts[str(key)] += 1
        payload = event.get("payload")
        if kind == "reward_delta" and isinstance(payload, dict):
            delta = float(payload.get("delta", 0.0))
            source = str(payload.get("source", "unknown"))
            component = str(payload.get("component", source))
            reward_source_totals[source] += delta
            reward_component_totals[component] += delta
        if kind == "terminal" or kind == "death":
            payload_dict = payload if isinstance(payload, dict) else {}
            reason = payload_dict.get("reason")
            record = {
                "step_index": int(event.get("step_index", 0)),
                "reason": reason,
            }
            cause = payload_dict.get("cause")
            if cause is not None:
                record["cause"] = cause
            terminal = record

    return {
        "schema": "gamebench.crafter.event_summary.v1",
        "event_count": len(events),
        "nev_cursor": len(events),
        "first_step_index": int(events[0]["step_index"]) if events else None,
        "last_step_index": int(events[-1]["step_index"]) if events else None,
        "event_kind_counts": dict(sorted(event_kind_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "transition_counts": dict(sorted(transition_counts.items())),
        "reward_source_totals": {key: float(value) for key, value in sorted(reward_source_totals.items())},
        "reward_component_totals": {key: float(value) for key, value in sorted(reward_component_totals.items())},
        "terminal": terminal,
    }


def termination_from_state(
    *,
    private: dict[str, Any],
    event_summary: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    embedded = private.get("termination")
    if isinstance(embedded, dict) and embedded.get("reason"):
        return dict(embedded)
    done_reason = private.get("done_reason")
    if not done_reason:
        return None
    summary = event_summary or {}
    terminal = summary.get("terminal") if isinstance(summary.get("terminal"), dict) else {}
    record: dict[str, Any] = {
        "reason": str(done_reason),
        "step_index": int(terminal.get("step_index") or private.get("step_index") or 0),
    }
    cause = terminal.get("cause") or private.get("termination_cause")
    if cause is not None and str(done_reason) == "death":
        record["cause"] = str(cause)
    return record


def project_readout(engine: Any) -> dict[str, Any]:
    observation = engine.observation
    private = engine.private.to_dict()
    if engine.resolved is not None:
        private["max_steps"] = engine.resolved.max_steps
        private["unsupported_rules"] = list(engine.resolved.unsupported_rules)
        resolved_json = engine.resolved.resolved_json or {}
        private["reward_mode"] = resolved_json.get("reward_mode", "standard")
        private["objective"] = resolved_json.get("objective")
    event_summary = engine.nev.summarize()
    readout = {
        "schema": "gamebench.crafter.readout.v1",
        "valid_actions": engine.valid_actions(),
        "grid_hash": grid_hash(observation),
        "local_tile_counts": local_tile_counts(observation),
        "front_tile": front_tile(observation),
        "public": engine.public.to_dict(),
        "private": private,
        "observation": observation,
        "event_summary": event_summary,
        "nev_tail": engine.nev.legacy_tail(8),
    }
    readout["observation_text"] = observation_text(readout)
    return readout


def observation_text(readout: dict[str, Any]) -> str:
    obs = readout.get("observation", {})
    player = obs.get("player", {})
    inventory = dict(player.get("inventory", {}))
    nonzero_inventory = {key: value for key, value in inventory.items() if value}
    achievements = obs.get("achievements", {})
    unlocked = sorted(name for name, value in achievements.items() if int(value) > 0)
    front = readout.get("front_tile") or {}
    counts = readout.get("local_tile_counts", {})
    stats = obs.get("stats", {})
    reward_breakdown = readout.get("private", {}).get("reward_breakdown", {})
    event_summary = readout.get("event_summary", {})
    parts: list[str] = []
    objective = readout.get("private", {}).get("objective")
    reward_mode = readout.get("private", {}).get("reward_mode")
    if objective:
        parts.append(
            f"goal=Unlock achievement '{objective}'. "
            f"Terminal reward is 1.0 only if '{objective}' is unlocked, else 0.0."
        )
    elif reward_mode == "goal_binary":
        parts.append("goal=Unlock the configured objective achievement for reward 1.0.")
    parts.extend(
        [
        f"step={obs.get('step', 0)} max_steps={readout.get('private', {}).get('max_steps')}",
        f"pos={player.get('pos')} facing={player.get('facing')} sleeping={player.get('sleeping', False)}",
        "vitals="
        f"health:{player.get('health')} food:{player.get('food')} drink:{player.get('drink')} energy:{player.get('energy')}",
        f"front_tile={front.get('kind')} at {front.get('pos')}",
        f"inventory={nonzero_inventory}",
        f"achievements={unlocked}",
        f"score={stats.get('score', 0)} daylight={stats.get('daylight')}",
        "reward="
        f"last:{readout.get('private', {}).get('reward_last', 0)} total:{readout.get('private', {}).get('total_reward', 0)} "
        f"breakdown:{reward_breakdown}",
        f"events={event_summary.get('event_kind_counts', {})}",
        f"transitions={event_summary.get('transition_counts', {})}",
        f"nearby_tiles={counts}",
        f"valid_actions={readout.get('valid_actions', [])}",
        ]
    )
    return "\n".join(parts)
