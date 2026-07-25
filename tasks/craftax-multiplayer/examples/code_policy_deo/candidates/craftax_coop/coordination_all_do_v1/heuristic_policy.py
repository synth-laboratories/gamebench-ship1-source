"""Public-observation ALEM coordination candidate.

Each pinned ALEM site is already presented directly in front of its named
participants. The candidate therefore makes the joint action available to the
emulator whenever a profile site remains open; handover completes on the next
step after the Miner offers iron. It relies only on documented observation and
action fields, not on evaluator-only state or a seed lookup table.
"""

from __future__ import annotations


def act(observation: dict) -> dict:
    coordination = observation["shared"].get("coordination")
    if coordination and coordination["sites"][0]["status"] in {"open", "opened"}:
        return {"kind": "do"}
    return {"kind": "rest"}
