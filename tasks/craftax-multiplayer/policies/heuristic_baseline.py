"""Deterministic role-aware policy used by the policy runner."""

def act(observation: dict) -> dict:
    me = observation["self"]
    if me["health"] <= 3 and observation["role"] == "forager": return {"kind": "cast_spell"}
    if me["drink"] <= 2: return {"kind": "request_drink"}
    if me["food"] <= 2: return {"kind": "request_food"}
    for mate in observation["teammate_dashboard"]:
        request = mate["request"]["resource"]
        if request and request not in ("food", "drink") and me["inventory"].get(request, 0):
            return {"kind": f"give_{request}_to_{mate['agent_id']}"}
    return {"kind": ("right", "down", "do", "left", "up")[observation["shared"]["timestep"] % 5]}
