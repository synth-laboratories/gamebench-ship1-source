"""Safe communication-only baseline for the ALEM coordination DEO suite.

This baseline uses the public structured-message channel, but deliberately never
commits the required joint ``do`` action. It gives policy authors a legal,
reliable starting point whose coordination score can be improved honestly.
"""

from __future__ import annotations


def act(observation: dict) -> dict:
    coordination = observation["shared"].get("coordination")
    if coordination:
        site = coordination["sites"][0]
        code = "NEED_IRON" if site["kind"] == "handover" else "MEET_AT"
        return {
            "kind": "say",
            "to": "all",
            "code": code,
            "site_id": site["site_id"],
        }
    return {"kind": "rest"}
