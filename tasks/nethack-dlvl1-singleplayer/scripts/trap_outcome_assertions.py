"""Exact authored-trap transition checks for the dlvl-1 gold scenarios.

The native NLE fixture set currently contains no trap-bearing reset level, so
this contract is intentionally scoped to the explicit ``bootstrap_trap_death``
scenario. It checks the complete observable lifecycle without claiming a
native trap-damage or trap-RNG model.
"""

from __future__ import annotations

from typing import Any


SCHEMA = "gamebench.nethack.authored_trap_outcome.v1"


def authored_trap_death_report(result: dict[str, Any], *, trap_id: str, damage: int) -> dict[str, Any]:
    """Return a fail-closed report for one explicit fatal-trap scenario."""

    readout = result.get("readout") if isinstance(result, dict) else None
    if not isinstance(readout, dict):
        return {"schema": SCHEMA, "status": "rejected", "errors": ["missing readout"]}
    public, private = readout.get("public"), readout.get("private")
    if not isinstance(public, dict) or not isinstance(private, dict):
        return {"schema": SCHEMA, "status": "rejected", "errors": ["missing public/private readout"]}
    traps = private.get("traps")
    trap = next((entry for entry in traps if isinstance(entry, dict) and entry.get("id") == trap_id), None) if isinstance(traps, list) else None
    hero, stats = private.get("hero"), public.get("blstats_named")
    if not isinstance(trap, dict) or not isinstance(hero, dict) or not isinstance(stats, dict):
        return {"schema": SCHEMA, "status": "rejected", "errors": ["missing trap/hero/stats state"]}
    events = result.get("nev", [])
    trap_event = next((event for event in events if isinstance(event, dict) and event.get("kind") == "action_applied" and event.get("transition") == "trap"), None) if isinstance(events, list) else None
    terminal_event = next((event for event in events if isinstance(event, dict) and event.get("kind") == "death"), None) if isinstance(events, list) else None
    position = trap.get("position", {})
    payload = trap_event.get("payload", {}) if isinstance(trap_event, dict) and isinstance(trap_event.get("payload"), dict) else {}
    terminal_payload = terminal_event.get("payload", {}) if isinstance(terminal_event, dict) and isinstance(terminal_event.get("payload"), dict) else {}
    checks = {
        "movement_consumed": stats.get("time") == 1,
        "hero_on_trap": hero.get("x") == position.get("x") and hero.get("y") == position.get("y"),
        "trap_seen": trap.get("seen") is True,
        "trap_triggered": trap.get("triggered") is True,
        "damage_bound": trap.get("damage") == int(damage),
        "hp_zero": private.get("hp") == 0 and stats.get("hp") == 0,
        "done": public.get("done") is True and public.get("terminated") is True,
        "death_reason": public.get("terminal_reason") == "death",
        "trap_event": payload.get("trap") == trap_id and payload.get("damage") == int(damage),
        "terminal_event": terminal_payload.get("terminal_reason") == "death",
    }
    return {
        "schema": SCHEMA,
        "status": "pass" if all(checks.values()) else "errors_found",
        "source_scope": "explicit_authored_scenario_only",
        "native_trap_rng_claim": False,
        "checks": checks,
    }

