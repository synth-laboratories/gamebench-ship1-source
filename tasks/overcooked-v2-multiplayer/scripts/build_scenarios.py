#!/usr/bin/env python3
"""Build Overcooked v2 gold scenario fixtures from validated action scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scenarios import run_scenario
from layout_catalog import LAYOUT_SPECS


W = {"kind": "wait"}
I = {"kind": "interact"}
N = {"kind": "move", "direction": "north"}
S = {"kind": "move", "direction": "south"}
E = {"kind": "move", "direction": "east"}
WEST = {"kind": "move", "direction": "west"}


def ja(agent_0: dict[str, Any], agent_1: dict[str, Any]) -> dict[str, Any]:
    return {"agent_0": agent_0, "agent_1": agent_1}


def ja3(agent_0: dict[str, Any], agent_1: dict[str, Any], agent_2: dict[str, Any]) -> dict[str, Any]:
    return {"agent_0": agent_0, "agent_1": agent_1, "agent_2": agent_2}


FULL_DELIVERY = [
    ja(N, W),
    ja(I, W),
    ja(E, W),
    ja(E, W),
    ja(E, W),
    ja(E, W),
    ja(N, W),
    ja(I, W),
    ja(W, W),
    ja(W, W),
    ja(I, W),
    ja(E, W),
    ja(N, W),
    ja(E, W),
    ja(I, W),
]

TRIO_DELIVERY = [
    ja(N, WEST),
    ja(I, WEST),
    ja(E, WEST),
    ja(E, WEST),
    ja(E, WEST),
    ja(E, WEST),
    ja(E, WEST),
    ja(E, WEST),
    ja(N, W),
    ja(I, W),
    ja(N, W),
    ja(I, W),
    ja(E, W),
    ja(E, W),
    ja(E, W),
    ja(E, W),
    ja(N, W),
    ja(I, W),
    ja(W, W),
    ja(W, W),
    ja(W, W),
    ja(I, W),
    ja(E, W),
    ja(N, W),
    ja(E, W),
    ja(I, W),
]

MIXED_SOUP_DELIVERY = [
    ja(N, W),
    ja(E, W),
    ja(I, W),
    ja(WEST, W),
    ja(I, W),
    ja(E, W),
    ja(I, W),
    ja(WEST, W),
    ja(I, W),
    ja(N, W),
    ja(WEST, W),
    ja(I, W),
    ja(S, W),
    ja(WEST, W),
    ja(I, W),
    ja(W, W),
    ja(W, W),
    ja(W, W),
    ja(WEST, W),
    ja(I, W),
    ja(N, W),
    ja(E, W),
    ja(E, W),
    ja(I, W),
]


def scenarios() -> list[dict[str, Any]]:
    base_rules = {"base": "cooperative_full_obs", "overrides": {"max_steps": 64, "cook_time": 2}}
    trio_rules = {
        "base": "cooperative_full_obs",
        "overrides": {"max_steps": 96, "cook_time": 3, "required_onions": 3},
        "recipe_id": "trio_soup",
    }
    return [
        {
            "scenario_id": "smoke_reset",
            "seed": 1,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": [],
        },
        {
            "scenario_id": "face_onion_north",
            "seed": 2,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": [ja(N, W)],
        },
        {
            "scenario_id": "pick_onion_agent0",
            "seed": 3,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": [ja(N, W), ja(I, W)],
        },
        {
            "scenario_id": "agent0_move_east",
            "seed": 4,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": [ja(E, W), ja(E, W)],
        },
        {
            "scenario_id": "add_onion_start_cook",
            "seed": 5,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": FULL_DELIVERY[:8],
        },
        {
            "scenario_id": "cook_complete_wait",
            "seed": 6,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": FULL_DELIVERY[:10],
        },
        {
            "scenario_id": "pick_soup_after_cook",
            "seed": 7,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": FULL_DELIVERY[:11],
        },
        {
            "scenario_id": "full_delivery_simple_soup",
            "seed": 8,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": FULL_DELIVERY,
        },
        {
            "scenario_id": "agent1_move_west",
            "seed": 9,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": [ja(W, WEST), ja(W, WEST), ja(W, WEST)],
        },
        {
            "scenario_id": "truncation_timeout",
            "seed": 10,
            "layout_id": "demo_tiny",
            "rules": {"base": "cooperative_full_obs", "overrides": {"max_steps": 4, "cook_time": 2}},
            "joint_actions": [ja(W, W), ja(W, W), ja(W, W), ja(W, W), ja(W, W)],
        },
        {
            "scenario_id": "counter_row_delivery",
            "seed": 11,
            "layout_id": "counter_row",
            "rules": base_rules,
            "joint_actions": [
                ja(N, W),
                ja(I, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(N, W),
                ja(I, W),
                ja(W, W),
                ja(W, W),
                ja(I, W),
                ja(E, W),
                ja(N, W),
                ja(E, W),
                ja(I, W),
            ],
        },
        {
            "scenario_id": "trio_soup_delivery",
            "seed": 12,
            "layout_id": "demo_tiny",
            "rules": trio_rules,
            "joint_actions": TRIO_DELIVERY,
        },
        {
            "scenario_id": "checkpoint_restore_delivery",
            "seed": 13,
            "layout_id": "demo_tiny",
            "rules": base_rules,
            "joint_actions": FULL_DELIVERY[:11],
            "checkpoint_after": 11,
            "restore_then_actions": FULL_DELIVERY[11:],
        },
        {
            "scenario_id": "partial_obs_move_smoke",
            "seed": 14,
            "layout_id": "demo_tiny",
            "rules": {"base": "partial_obs_v1"},
            "joint_actions": [ja(E, W), ja(E, W)],
        },
        {
            "scenario_id": "hidden_recipe_indicator_smoke",
            "seed": 15,
            "layout_id": "indicator_split",
            "rules": {"base": "hidden_recipe_indicator"},
            "joint_actions": [ja(N, W), ja(E, W), ja(E, W)],
        },
        {
            "scenario_id": "stochastic_spawn_smoke",
            "seed": 16,
            "layout_id": "demo_tiny",
            "rules": {"base": "stochastic_spawn"},
            "joint_actions": [ja(W, W)],
        },
        {
            "scenario_id": "counter_place_pick",
            "seed": 17,
            "layout_id": "plated_kitchen",
            "rules": base_rules,
            "joint_actions": [
                ja(W, E),
                ja(W, E),
                ja(N, W),
                ja(I, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(S, W),
                ja(S, W),
                ja(E, W),
                ja(I, W),
                ja(W, W),
                ja(I, W),
            ],
        },
        {
            "scenario_id": "plated_soup_delivery",
            "seed": 18,
            "layout_id": "plated_kitchen",
            "rules": base_rules,
            "joint_actions": [
                ja(W, E),
                ja(W, E),
                ja(N, W),
                ja(I, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(E, W),
                ja(N, W),
                ja(I, W),
                ja(W, W),
                ja(W, W),
                ja(WEST, W),
                ja(WEST, W),
                ja(N, W),
                ja(I, W),
                ja(E, W),
                ja(E, W),
                ja(N, W),
                ja(I, W),
                ja(E, W),
                ja(E, W),
                ja(N, W),
                ja(I, W),
            ],
        },
        {
            "scenario_id": "three_agent_move_smoke",
            "seed": 19,
            "layout_id": "three_chefs",
            "rules": base_rules,
            "joint_actions": [ja3(E, W, W), ja3(E, W, W)],
        },
        {
            "scenario_id": "zsc_coop_smoke",
            "seed": 20,
            "layout_id": "indicator_split",
            "rules": {"base": "zsc_coop"},
            "joint_actions": [ja(W, W), ja(W, W), ja(W, W), ja(W, W)],
        },
        {
            "scenario_id": "mixed_soup_delivery",
            "seed": 21,
            "layout_id": "dual_ingredient",
            "rules": {
                "recipe_id": "mixed_soup",
                "overrides": {"max_steps": 96, "cook_time": 2},
            },
            "joint_actions": MIXED_SOUP_DELIVERY,
        },
        {
            "scenario_id": "button_activation_smoke",
            "seed": 22,
            "layout_id": "overcookedv2_demo",
            "rules": {"base": "grounded_communication"},
            "joint_actions": [ja(S, W), ja(WEST, W), ja(I, W)],
        },
        {
            "scenario_id": "featurized_obs_smoke",
            "seed": 23,
            "layout_id": "demo_tiny",
            "rules": {"base": "featurized_obs"},
            "readouts": {"profile": "featurized"},
            "joint_actions": [ja(E, W)],
        },
        {
            "scenario_id": "random_reset_smoke",
            "seed": 26,
            "layout_id": "demo_tiny",
            "rules": {"base": "random_reset"},
            "joint_actions": [ja(W, W)],
        },
        {
            "scenario_id": "urgency_layer_smoke",
            "seed": 27,
            "layout_id": "demo_tiny",
            "rules": {
                "base": "cooperative_full_obs",
                "overrides": {"max_steps": 50, "urgency_cutoff": 40},
            },
            "readouts": {"profile": "spatial_tensor"},
            "joint_actions": [ja(W, W) for _ in range(11)],
        },
        {
            "scenario_id": "pixel_obs_smoke",
            "seed": 24,
            "layout_id": "demo_tiny",
            "rules": {"base": "pixel_obs"},
            "readouts": {"profile": "pixel_rgb"},
            "joint_actions": [ja(E, W)],
        },
        {
            "scenario_id": "grounded_coord_button_smoke",
            "seed": 25,
            "layout_id": "grounded_coord_simple",
            "rules": {"base": "grounded_communication", "recipe_id": "tomato_trio"},
            "joint_actions": [ja(N, W), ja(WEST, W), ja(I, W)],
        },
        {
            "scenario_id": "featurized_vector_exact_smoke",
            "seed": 28,
            "layout_id": "demo_tiny",
            "rules": {"base": "featurized_obs"},
            "joint_actions": [],
        },
        {
            "scenario_id": "layout_catalog_cramped_room",
            "seed": 29,
            "layout_id": "cramped_room",
            "rules": {"recipe_id": "trio_soup", "overrides": {"max_steps": 32}},
            "joint_actions": [ja(W, W)],
        },
    ]


def validate_layout_catalog() -> None:
    from task_resolve import resolve_task

    for layout_id in sorted(LAYOUT_SPECS):
        resolved = resolve_task({"scenario_id": f"layout_{layout_id}", "seed": 1, "layout_id": layout_id})
        if not resolved.agent_ids:
            raise SystemExit(f"layout {layout_id}: no agents parsed")


def main() -> None:
    validate_layout_catalog()
    output = TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json"
    entries = scenarios()
    for entry in entries:
        result = run_scenario(entry)
        if entry["scenario_id"] == "featurized_vector_exact_smoke":
            obs = result["readout"]["observations"]["agent_0"]
            from featurized_obs import featurized_vector_length

            expected_len = featurized_vector_length(len(result["readout"]["observations"]))
            actual_len = len(obs.get("features", []))
            if actual_len != expected_len:
                raise SystemExit(f"featurized_vector_exact_smoke: expected {expected_len}, got {actual_len}")
        if entry["scenario_id"] == "urgency_layer_smoke":
            obs = result["readout"]["observations"]["agent_0"]
            if not obs.get("urgency_active"):
                raise SystemExit("urgency_layer_smoke: expected urgency_active true")
            tensor = obs.get("tensor") or []
            if not tensor or tensor[-1][0][0] != 1.0:
                raise SystemExit("urgency_layer_smoke: expected urgency tensor layer on")
        if entry["scenario_id"] == "random_reset_smoke":
            events = result["events"]
            if "RandomResetApplied" not in events:
                raise SystemExit("random_reset_smoke: missing RandomResetApplied")
        if entry["scenario_id"] in {
            "full_delivery_simple_soup",
            "plated_soup_delivery",
            "mixed_soup_delivery",
        }:
            if not result["state"]["private"]["terminated"]:
                raise SystemExit(f"{entry['scenario_id']}: expected terminal success")
        if entry["scenario_id"] == "truncation_timeout":
            if not result["state"]["private"]["truncated"]:
                raise SystemExit(f"{entry['scenario_id']}: expected truncated")
    doc = {"schema": "gamebench.overcooked_v2.gold_scenarios.v1", "scenarios": entries}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(entries)} scenarios to {output}")


if __name__ == "__main__":
    main()
