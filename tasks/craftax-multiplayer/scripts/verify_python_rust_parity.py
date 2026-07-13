#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from gold_python.engine import CraftaxCoopEnv

def projection(env:CraftaxCoopEnv)->dict:
    state=env._require_state()
    return {"timestep":state.timestep,"players":[env._player_summary(p)|{"facing":p.facing} for p in state.players],"trade_count":state.trade_count,"achievements":sorted(k for k,v in state.achievements.items() if v),"boss_health":state.boss_health,"boss_progress":state.boss_progress,"terminated":state.terminated,"termination_reason":state.termination_reason,"map_samples":[state.maps[0][4][5],state.maps[0][10][10],state.maps[8][24][24]],"monster_count":len(state.monsters)}

def main()->None:
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(101);env.state.players[2].inventory["iron"]=2
    env.step({"agent_0":"request_iron","agent_1":"cast_spell","agent_2":"give_iron_to_agent_0"})
    env.step({"agent_0":"right","agent_1":"down","agent_2":"left"})
    env.step({"agent_0":"rest","agent_1":"noop","agent_2":"make_iron_pickaxe"})
    rust=json.loads(subprocess.run(["cargo","run","--quiet","--manifest-path",str(ROOT/"gold_rust/Cargo.toml"),"--example","parity_fixture"],check=True,text=True,capture_output=True).stdout)
    python=projection(env)
    # Rust serialization is authoritative wire shape; normalize it to the Python dashboard projection.
    rust["players"]=[{"agent_id":p["agent_id"],"role":p["role"],"position":[p["x"],p["y"]],"level":p["level"],"health":p["health"],"food":p["food"],"drink":p["drink"],"energy":p["energy"],"mana":p["mana"],"alive":p["alive"],"sleeping":p["sleeping"],"inventory":p["inventory"],"equipment":{"pickaxe":p["pickaxe"],"sword":p["sword"],"armour":p["armour"],"arrows":p["arrows"],"torches":p["torches"],"books":p["books"],"saplings":p["saplings"],"potions":p["potions"],"enchantments":{"sword":p["sword_enchantment"],"armour":p["armour_enchantment"],"bow":p["bow_enchantment"]}},"attributes":{"dexterity":p["dexterity"],"strength":p["strength"],"intelligence":p["intelligence"],"xp":p["xp"],"level_points":p["level_points"]},"request":{"resource":p["request_type"],"remaining":p["request_duration"]},"facing":p["facing"]} for p in rust["players"]]
    if python!=rust:
        print(json.dumps({"python":python,"rust":rust},indent=2,sort_keys=True));raise SystemExit("Python/Rust parity mismatch")
    print(json.dumps({"status":"pass","projection":python},sort_keys=True))

if __name__=="__main__":main()
