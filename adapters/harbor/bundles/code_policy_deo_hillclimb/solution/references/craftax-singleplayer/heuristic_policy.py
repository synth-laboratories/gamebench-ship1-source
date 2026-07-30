"""Craftax heuristic with compact-map marker normalization."""

from __future__ import annotations

from typing import Any

from policies.heuristic_baseline import choose_actions as _reference_choose_actions


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    # The symbolic compact readout uses `a` for a nearby crafting table, while
    # the reference policy's routing vocabulary expects `A`.
    observation = dict(readout.get("observation", {}))
    local_map = list(observation.get("local_map", []))
    observation["local_map"] = [row.replace("a", "A") for row in local_map]
    normalized = dict(readout)
    normalized["observation"] = observation
    return _reference_choose_actions(
        observation_text=observation_text,
        session=session,
        valid_actions=valid_actions,
        engine=engine,
        readout=normalized,
        seed=seed,
        ply=ply,
    )
