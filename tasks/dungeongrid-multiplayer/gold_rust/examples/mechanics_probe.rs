use dungeongrid_gold::{
    Direction, DungeonGridAction, DungeonGridSession, GiveItemPayload, MessagePayload,
    ObservationConfig, Pos, Scenario, SpellPayload,
};
use serde_json::json;
use std::collections::BTreeMap;

fn main() {
    let scenario = Scenario {
        task_id: "dg_mechanics_probe".to_string(),
        scenario_id: "mechanics_probe".to_string(),
        quest_id: "gamebench:mechanics_probe:rust".to_string(),
        title: "Mechanics Probe".to_string(),
        seed: 99,
        max_steps: 80,
        map_ascii: "########\n#E.DCI.#\n#.TR...#\n########".to_string(),
        hero_roles: vec!["barbarian".to_string(), "wizard".to_string()],
        objective_item: "probe_idol".to_string(),
        observation: ObservationConfig::default(),
        metadata: BTreeMap::from([
            (
                "marl_axis".to_string(),
                json!("mechanics coverage for event-rich state snapshots"),
            ),
            (
                "coordination_skills".to_string(),
                json!([
                    "communicate before route commitment",
                    "support reveals counterplay before the frontline attacks",
                    "handoff and consume inventory while maintaining turn order"
                ]),
            ),
        ]),
    };
    let mut session =
        DungeonGridSession::reset(scenario).expect("mechanics probe scenario should reset");
    let actions = [
        DungeonGridAction::Message {
            target: "party".to_string(),
            payload: MessagePayload {
                text: "Probe route: reveal, hand off ration, open chest, defeat brute.".to_string(),
            },
        },
        DungeonGridAction::Move {
            direction: Direction::East,
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::Cast {
            target: "self".to_string(),
            payload: SpellPayload {
                spell: "ward_circle".to_string(),
            },
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::SearchTraps,
        DungeonGridAction::EndTurn,
        DungeonGridAction::Cast {
            target: "crypt_brute_1".to_string(),
            payload: SpellPayload {
                spell: "reveal_glyph".to_string(),
            },
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::OpenDoor {
            target: "door_1".to_string(),
        },
        DungeonGridAction::GiveItem {
            target: "agent_1".to_string(),
            payload: GiveItemPayload {
                item: "iron_ration".to_string(),
            },
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::UseItem {
            target: "iron_ration".to_string(),
        },
        DungeonGridAction::Guard,
        DungeonGridAction::EndTurn,
        DungeonGridAction::Move {
            direction: Direction::East,
        },
        DungeonGridAction::Interact {
            target: "chest_1".to_string(),
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::Move {
            direction: Direction::East,
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::AttackMelee {
            target: "crypt_brute_1".to_string(),
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::Cast {
            target: "crypt_brute_1".to_string(),
            payload: SpellPayload {
                spell: "spark_lance".to_string(),
            },
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::Move {
            direction: Direction::East,
        },
        DungeonGridAction::Interact {
            target: "objective".to_string(),
        },
        DungeonGridAction::EndTurn,
        DungeonGridAction::InspectTile {
            target: Pos { x: 5, y: 1 },
        },
    ];
    for action in actions {
        let result = session.step(action);
        assert!(
            result.applied,
            "mechanics probe action should apply; recent events: {}",
            serde_json::to_string_pretty(&result.info["recent_events"])
                .expect("recent events serialize")
        );
    }

    let state = session.rich_state();
    let state_digest = session
        .state_digest()
        .expect("state digest should serialize");
    let restored = DungeonGridSession::restore_from_checkpoint_value(session.checkpoint_json())
        .expect("mechanics checkpoint should restore");
    let restored_state_digest = restored
        .state_digest()
        .expect("restored state digest should serialize");
    let event_kinds = session
        .event_log
        .iter()
        .map(|event| event.kind.as_str())
        .collect::<Vec<_>>();
    let rich_state_keys = state
        .as_object()
        .map(|object| object.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    let legal_action_keys = state["legal_actions"]
        .as_object()
        .map(|object| object.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();

    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "status": "passed",
            "scenario_id": state["scenario_id"],
            "step_index": state["step_index"],
            "turn_index": state["turn_index"],
            "active_agent": state["active_agent"],
            "total_reward": state["total_reward"],
            "done": state["done"],
            "success": state["success"],
            "state_digest": state_digest,
            "restored_state_digest": restored_state_digest,
            "event_count": event_kinds.len(),
            "event_kinds": event_kinds,
            "achievements": state["achievements"],
            "rich_state_keys": rich_state_keys,
            "legal_action_keys": legal_action_keys,
            "coordination": state["coordination"],
            "objective": state["objective"],
            "heroes": state["heroes"],
            "traps": state["traps"],
            "chests": state["chests"],
            "monsters": state["monsters"],
            "map_ascii": state["map"]["ascii"],
        }))
        .expect("summary serializes")
    );
}
