use dungeongrid_gold::{
    Direction, DungeonGridAction, DungeonGridSession, MessagePayload, Scenario, SpellPayload,
};

fn main() {
    let scenario = Scenario::from_json_str(include_str!(
        "../../defaults/scenarios/lantern_crypt_lite.json"
    ))
    .expect("lantern crypt lite scenario JSON should parse");
    let mut session =
        DungeonGridSession::reset(scenario).expect("lantern crypt lite scenario should reset");
    let actions = [
        DungeonGridAction::Message {
            target: "party".to_string(),
            payload: MessagePayload {
                text: "Barbarian will open the east door; wizard should inspect the idol room."
                    .to_string(),
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
        DungeonGridAction::Move {
            direction: Direction::East,
        },
        DungeonGridAction::OpenDoor {
            target: "door_1".to_string(),
        },
    ];
    for action in actions {
        let _ = session.step(action);
    }
    let checkpoint = session.checkpoint_json();
    let restored = DungeonGridSession::restore_from_checkpoint_value(checkpoint)
        .expect("checkpoint should restore");
    let state = session.rich_state();
    let restored_state = restored.rich_state();
    let event_kinds = session
        .event_log
        .iter()
        .map(|event| event.kind.as_str())
        .collect::<Vec<_>>();
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "episode_id": state["episode_id"],
            "active_agent": state["active_agent"],
            "step_index": state["step_index"],
            "total_reward": state["total_reward"],
            "achievements": state["achievements"],
            "restored_step_index": restored_state["step_index"],
            "restored_total_reward": restored_state["total_reward"],
            "map_ascii": state["map"]["ascii"],
            "event_kinds": event_kinds,
            "rich_state_keys": state.as_object().map(|object| object.keys().cloned().collect::<Vec<_>>()),
        }))
        .expect("summary serializes")
    );
}
