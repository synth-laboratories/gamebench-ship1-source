use dungeongrid_gold::{DungeonGridSession, Scenario};
use serde_json::json;
use std::{fs, path::PathBuf};

fn main() {
    let scenario_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../defaults/scenarios");
    let mut paths = fs::read_dir(&scenario_dir)
        .expect("scenario directory should be readable")
        .map(|entry| entry.expect("scenario entry should be readable").path())
        .filter(|path| {
            path.extension()
                .is_some_and(|extension| extension == "json")
        })
        .collect::<Vec<_>>();
    paths.sort();

    let mut scenarios = Vec::new();
    for path in paths {
        let scenario_text = fs::read_to_string(&path).expect("scenario file should be readable");
        let scenario = Scenario::from_json_str(&scenario_text).expect("scenario should parse");
        let mut session =
            DungeonGridSession::reset(scenario).expect("scenario should reset into a session");
        let initial_state_digest = session
            .state_digest()
            .expect("state digest should serialize");
        let checkpoint = session.checkpoint_json();
        let restored = DungeonGridSession::restore_from_checkpoint_value(checkpoint)
            .expect("checkpoint should restore");
        let restored_state_digest = restored
            .state_digest()
            .expect("state digest should serialize");
        assert_eq!(
            initial_state_digest, restored_state_digest,
            "checkpoint restore changed deterministic state for {}",
            session.scenario.scenario_id
        );
        session
            .reset_to_initial()
            .expect("reset_to_initial should rebuild scenario state");
        let reset_state_digest = session
            .state_digest()
            .expect("state digest should serialize");
        assert_eq!(
            initial_state_digest, reset_state_digest,
            "reset_to_initial changed deterministic state for {}",
            session.scenario.scenario_id
        );
        let state = session.rich_state();
        let event_kinds = session
            .event_log
            .iter()
            .map(|event| event.kind.as_str())
            .collect::<Vec<_>>();
        assert_eq!(
            event_kinds,
            vec!["episode_reset", "turn_started"],
            "reset events should be deterministic for {}",
            session.scenario.scenario_id
        );
        scenarios.push(json!({
            "scenario_id": state["scenario_id"],
            "title": state["title"],
            "active_agent": state["active_agent"],
            "event_kinds": event_kinds,
            "state_digest": initial_state_digest,
            "restored_state_digest": restored_state_digest,
            "reset_state_digest": reset_state_digest,
            "entity_counts": {
                "heroes": session.heroes.len(),
                "doors": session.doors.len(),
                "traps": session.traps.len(),
                "chests": session.chests.len(),
                "monsters": session.monsters.len(),
            },
        }));
    }

    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "status": "passed",
            "lane": "rust",
            "scenario_count": scenarios.len(),
            "scenarios": scenarios,
        }))
        .expect("summary serializes")
    );
}
