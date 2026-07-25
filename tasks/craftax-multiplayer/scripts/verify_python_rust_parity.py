#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from gold_python.engine import CraftaxCoopEnv
from gold_python.state import Monster,Plant
from scenario_fixtures import alem_parity_projection, load_scenarios, run_scenario

def cargo_json(example: str, payload: str | None = None) -> dict:
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "gold_rust/Cargo.toml"), "--example", example],
        input=payload,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr.strip() or f"Rust {example} failed with status {completed.returncode}")
    return json.loads(completed.stdout)

def projection(env:CraftaxCoopEnv)->dict:
    state=env._require_state()
    return {"timestep":state.timestep,"players":[env._player_summary(p)|{"facing":p.facing} for p in state.players],"trade_count":state.trade_count,"achievements":sorted(k for k,v in state.achievements.items() if v),"boss_health":state.boss_health,"boss_progress":state.boss_progress,"terminated":state.terminated,"termination_reason":state.termination_reason,"map_samples":[state.maps[0][4][5],state.maps[0][10][10],state.maps[8][24][24]],"monster_count":len(state.monsters),"nev":state.nev,"legacy_nev":state.legacy_nev}

def main()->None:
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(101);env.state.players[2].inventory["iron"]=2
    env.step({"agent_0":"request_iron","agent_1":"cast_spell","agent_2":"give_iron_to_agent_0"})
    env.step({"agent_0":"right","agent_1":"down","agent_2":"left"})
    env.step({"agent_0":"rest","agent_1":"noop","agent_2":"make_iron_pickaxe"})
    rust=cargo_json("parity_fixture")
    python=projection(env)
    # Rust serialization is authoritative wire shape; normalize it to the Python dashboard projection.
    rust["players"]=[{"agent_id":p["agent_id"],"role":p["role"],"position":[p["x"],p["y"]],"level":p["level"],"health":p["health"],"food":p["food"],"drink":p["drink"],"energy":p["energy"],"mana":p["mana"],"alive":p["alive"],"sleeping":p["sleeping"],"resting":p["resting"],"inventory":p["inventory"],"equipment":{"pickaxe":p["pickaxe"],"sword":p["sword"],"armour":p["armour"],"armour_slots":p["armour_slots"],"bow":p["bow"],"arrows":p["arrows"],"torches":p["torches"],"books":p["books"],"saplings":p["saplings"],"potions":p["potions"],"learned_spell":p["learned_spell"],"enchantments":{"sword":p["sword_enchantment"],"armour":p["armour_enchantment"],"armour_slots":p["armour_enchantments"],"bow":p["bow_enchantment"]}},"attributes":{"dexterity":p["dexterity"],"strength":p["strength"],"intelligence":p["intelligence"],"xp":p["xp"],"level_points":p["level_points"]},"intrinsics":{"recover":p["recover"],"hunger":p["hunger"],"thirst":p["thirst"],"fatigue":p["fatigue"],"recover_mana":p["recover_mana"]},"request":{"resource":p["request_type"],"remaining":p["request_duration"]},"facing":p["facing"]} for p in rust["players"]]
    if python!=rust:
        print(json.dumps({"python":python,"rust":rust},indent=2,sort_keys=True));raise SystemExit("Python/Rust parity mismatch")
    scenarios=python_scenarios()
    rust_scenarios=cargo_json("parity_scenarios")
    if scenarios!=rust_scenarios:
        print(json.dumps({"python":scenarios,"rust":rust_scenarios},indent=2,sort_keys=True));raise SystemExit("Python/Rust scenario parity mismatch")
    assert scenarios["collect"]["iron"]==1 and scenarios["collect"]["tile"]=="path"
    assert not scenarios["combat"]["monsters"] and scenarios["combat"]["xp"]==0
    assert scenarios["boss"]["progress"]==1 and scenarios["boss"]["health"]==7
    assert scenarios["death"]["terminated"] and scenarios["death"]["reason"]=="death"
    assert scenarios["plant_light"]["tile"]=="ripe_plant"
    assert scenarios["full_transfer"]["trades"]==1 and scenarios["full_transfer"]["request"]=="wood"
    assert scenarios["level_point"]=={"xp":1,"points":2}
    cross_checkpoint = verify_cross_language_checkpoint(env)
    service_build = verify_rust_service_build()
    alem = verify_alem_profile_fixtures()
    alem_cross_checkpoint = verify_alem_cross_language_checkpoint()
    print(json.dumps({"status":"pass","projection":python,"scenarios":scenarios,"cross_checkpoint":cross_checkpoint,"rust_service":service_build,"alem":alem,"alem_cross_checkpoint":alem_cross_checkpoint},sort_keys=True))

def verify_rust_service_build() -> str:
    completed = subprocess.run(
        ["cargo", "check", "--quiet", "--manifest-path", str(ROOT / "gold_rust/Cargo.toml"), "--bin", "service"],
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr.strip() or "Rust service build failed")
    return "pass"

def verify_alem_profile_fixtures() -> dict:
    fixtures = [entry for entry in load_scenarios() if entry.get("rules_profile") == "alem_coord_v0"]
    if len(fixtures) < 6:
        raise SystemExit("ALEM parity requires at least six profile fixtures")
    for entry in fixtures:
        python = alem_parity_projection(run_scenario(entry))
        rust = cargo_json("alem_fixture", json.dumps(entry))
        if python != rust:
            print(json.dumps({"scenario_id":entry["scenario_id"],"python":python,"rust":rust},indent=2,sort_keys=True))
            raise SystemExit("Python/Rust ALEM fixture parity mismatch")
    return {"fixtures":len(fixtures),"status":"pass"}

def alem_observation_surface(environment: CraftaxCoopEnv) -> dict:
    return {
        agent_id: {
            "legal_action_count": len(observation["legal_actions"]),
            "shared": observation["shared"],
            "last_joint_event": observation["last_joint_event"],
        }
        for agent_id, observation in environment.observations().items()
    }

def alem_coordination_state(environment: CraftaxCoopEnv) -> dict:
    state = environment._require_state()
    return {
        "alem_coord": state.to_dict()["alem_coord"],
        "players": [
            {
                "agent_id": player.agent_id,
                "level": player.level,
                "position": [player.x, player.y],
                "facing": player.facing,
                "iron": player.inventory["iron"],
            }
            for player in state.players
        ],
    }

def verify_alem_cross_language_checkpoint() -> str:
    environment = CraftaxCoopEnv(
        max_timesteps=16,
        rules_profile="alem_coord_v0",
        coordination={"scenario": "handover", "alpha": 0.3},
    )
    environment.reset(7)
    environment.step({"agent_0": "noop", "agent_1": "noop", "agent_2": "do"})
    checkpoint = environment.checkpoint()
    restored = {
        "state": deepcopy(alem_coordination_state(environment)),
        "observations": deepcopy(alem_observation_surface(environment)),
        "nev": deepcopy(environment._require_state().nev),
    }
    cursor = len(environment._require_state().nev)
    _, _, _, info = environment.step({"agent_0": "noop", "agent_1": "do", "agent_2": "noop"})
    expected = {
        "restored": restored,
        "after": {
            "state": alem_coordination_state(environment),
            "observations": alem_observation_surface(environment),
            "nev_suffix": environment._require_state().nev[cursor:],
            "step_events": info["events"],
        },
    }
    actual = cargo_json(
        "alem_checkpoint_bridge",
        json.dumps({"checkpoint": checkpoint, "joint_action": {"agent_0": "noop", "agent_1": "do", "agent_2": "noop"}}),
    )
    if expected != actual:
        print(json.dumps({"python": expected, "rust": actual}, indent=2, sort_keys=True))
        raise SystemExit("Python -> Rust ALEM checkpoint bridge mismatch")
    return "pass"

def verify_cross_language_checkpoint(environment: CraftaxCoopEnv) -> str:
    python_checkpoint = environment.checkpoint()
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(ROOT / "gold_rust/Cargo.toml"), "--example", "checkpoint_bridge"],
        input=json.dumps(python_checkpoint),
        check=True,
        text=True,
        capture_output=True,
    )
    rust_checkpoint = json.loads(completed.stdout)
    restored = CraftaxCoopEnv()
    restored.restore(rust_checkpoint)
    source = environment._require_state().to_dict()
    returned = restored._require_state().to_dict()
    source["achievements"] = {key: value for key, value in source["achievements"].items() if value}
    returned["achievements"] = {key: value for key, value in returned["achievements"].items() if value}
    if source != returned:
        raise SystemExit("Python -> Rust -> Python checkpoint state mismatch")
    return "pass"

def python_scenarios()->dict:
    out={};env=CraftaxCoopEnv(max_timesteps=100);env.reset(17);out["reset"]={"maps":[env.state.maps[0][10][10],env.state.maps[6][10][10],env.state.maps[8][24][24]],"spawn":[env.state.maps[0][3][3],env.state.maps[0][3][4],env.state.maps[0][3][5]],"fountain":env.state.maps[0][5][5],"monsters":[asdict(monster) for monster in env.state.monsters[:5]]}
    try:env.step({"agent_0":"invalid_action","agent_1":"noop","agent_2":"noop"})
    except ValueError:out["strict_action"]=True
    else:out["strict_action"]=False
    env.step({a:("request_ruby" if a=="agent_0" else "noop") for a in env.agent_ids})
    for _ in range(10):env.step({a:"noop" for a in env.agent_ids})
    out["request_expiry"]=[env.state.players[0].request_type,env.state.players[0].request_duration]
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(17);env.state.monsters=[];p=env.state.players[2];p.pickaxe=2;env.state.maps[p.level][p.y+1][p.x]="iron";_,rewards,_,_=env.step({"agent_0":"noop","agent_1":"noop","agent_2":"do"});out["collect"]={"iron":env.state.players[2].inventory["iron"],"tile":env.state.maps[0][4][5],"reward":rewards["agent_0"],"achievements":sorted(k for k,v in env.state.achievements.items() if v),"nev":env.state.nev,"legacy_nev":env.state.legacy_nev}
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(17);env.state.monsters=[Monster("fixture","zombie",0,3,4,4,2)];env.step({"agent_0":"do","agent_1":"noop","agent_2":"noop"});env.step({"agent_0":"do","agent_1":"noop","agent_2":"noop"});out["combat"]={"monsters":[asdict(monster) for monster in env.state.monsters],"xp":env.state.players[0].xp,"achievements":sorted(k for k,v in env.state.achievements.items() if v)}
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(17);env.state.monsters=[]
    for p in env.state.players:p.level=8;p.x=24;p.y=23;p.facing="down"
    env.state.boss_wave_timer=0
    for _ in range(3):
        if not env.state.terminated:env.step({a:"do" for a in env.agent_ids})
    out["boss"]={"health":env.state.boss_health,"player_health":[player.health for player in env.state.players],"progress":env.state.boss_progress,"terminated":env.state.terminated,"reason":env.state.termination_reason,"achievements":sorted(k for k,v in env.state.achievements.items() if v)}
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(17);env.state.monsters=[]
    for p in env.state.players:p.health=1;p.food=0;p.drink=0;p.recover=-16
    _,death_rewards,_,_=env.step({a:"noop" for a in env.agent_ids});out["death"]={"health":[p.health for p in env.state.players],"reward":death_rewards["agent_0"],"terminated":env.state.terminated,"reason":env.state.termination_reason,"achievements":sorted(k for k,v in env.state.achievements.items() if v)}
    env=CraftaxCoopEnv(max_timesteps=1);env.reset(17);env.state.monsters=[];env.step({a:"noop" for a in env.agent_ids});out["timestep"]={"timestep":env.state.timestep,"terminated":env.state.terminated,"reason":env.state.termination_reason}
    env=CraftaxCoopEnv(max_timesteps=100);env.reset(17);env.state.monsters=[];env.state.maps[0][8][8]="plant";env.state.plants=[Plant(0,8,8,499)];env.step({a:"noop" for a in env.agent_ids});out["plant_light"]={"tile":env.state.maps[0][8][8],"timestep":env.state.timestep,"light":env.state.light_level}
    floor_env=CraftaxCoopEnv(max_timesteps=100);floor_env.reset(17);floor_env.state.monsters=[];floor_env.state.players[0].x=floor_env.state.players[0].y=45;floor_env.step({"agent_0":"descend","agent_1":"noop","agent_2":"noop"});descended=[floor_env.state.players[0].level,floor_env.state.players[0].x,floor_env.state.players[0].y];floor_env.step({"agent_0":"ascend","agent_1":"noop","agent_2":"noop"});out["floor_landing"]={"descended":descended,"ascended":[floor_env.state.players[0].level,floor_env.state.players[0].x,floor_env.state.players[0].y]}
    trade_env=CraftaxCoopEnv(max_timesteps=100);trade_env.reset(17);trade_env.state.monsters=[];trade_env.state.players[0].request_type="wood";trade_env.state.players[0].request_duration=10;trade_env.state.players[0].inventory["wood"]=98;trade_env.state.players[2].inventory["wood"]=1;trade_env.step({"agent_0":"noop","agent_1":"noop","agent_2":"give_wood_to_agent_0"});out["full_transfer"]={"giver":trade_env.state.players[2].inventory["wood"],"receiver":trade_env.state.players[0].inventory["wood"],"trades":trade_env.state.trade_count,"request":trade_env.state.players[0].request_type}
    survival_env=CraftaxCoopEnv(max_timesteps=100);survival_env.reset(18);survival_env.state.monsters=[];survival_env.state.maps[0][4][4]="tree";survival_env.step({"agent_0":"noop","agent_1":"do","agent_2":"noop"});survival_env.state.maps[0][4][4]="water";survival_env.state.players[1].drink=2;survival_env.step({"agent_0":"noop","agent_1":"do","agent_2":"noop"});survival_env.state.players[0].food=4;survival_env.state.monsters=[Monster("cow_fixture","cow",0,3,4,2,0,"passive")];survival_env.step({"agent_0":"do","agent_1":"noop","agent_2":"noop"});out["survival"]={"saplings":survival_env.state.players[1].saplings,"drink":survival_env.state.players[1].drink,"food":survival_env.state.players[0].food,"achievements":sorted(k for k,v in survival_env.state.achievements.items() if v)}
    projectile_env=CraftaxCoopEnv(max_timesteps=100);projectile_env.reset(17);projectile_env.state.monsters=[Monster("behind_wall","zombie",0,3,5,4,0)];projectile_env.state.maps[0][4][3]="stone";projectile_env.state.players[0].arrows=1;projectile_env.step({"agent_0":"shoot_arrow","agent_1":"noop","agent_2":"noop"});out["projectile_block"]={"projectiles":len(projectile_env.state.projectiles),"monster_health":projectile_env.state.monsters[0].health}
    progression_env=CraftaxCoopEnv(max_timesteps=100);progression_env.reset(17);progression_env.state.players[0].xp=2;progression_env.step({"agent_0":"level_up_strength","agent_1":"noop","agent_2":"noop"});out["level_point"]={"xp":progression_env.state.players[0].xp,"points":progression_env.state.players[0].strength}
    chest_env=CraftaxCoopEnv(max_timesteps=100);chest_env.reset(17);chest_env.state.monsters=[];chest_env.state.maps[0][4][5]="chest";chest_env.step({"agent_0":"noop","agent_1":"noop","agent_2":"do"});out["miner_chest"]={"coal":chest_env.state.players[2].inventory["coal"],"books":chest_env.state.players[2].books,"arrows":chest_env.state.players[2].arrows}
    restored=CraftaxCoopEnv();restored.restore(env.checkpoint());out["checkpoint"]=env.state.to_dict()==restored.state.to_dict();return out

if __name__=="__main__":main()
