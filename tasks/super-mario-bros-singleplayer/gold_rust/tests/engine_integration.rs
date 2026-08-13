use gamebench_platformer_gold::{
    Action, Env, Event, LevelId, PowerState, TerminalReason, ODYSSEUS_LEVELS,
};

#[test]
fn public_catalog_and_capability_contract_cover_all_levels() {
    for id in ODYSSEUS_LEVELS {
        let env = Env::reset(id, 0xfeed_face).expect("catalog level resets");
        let readout = env.readout();
        assert_eq!(readout.level_id, id.to_string());
        assert!(!readout.capability_tags.is_empty());
        assert_eq!(readout.allowed_actions.len(), 15);
        assert_eq!(env.level_spec().id, id);
    }
}

#[test]
fn two_instances_follow_the_same_replay_tape() {
    let mut left = Env::reset(LevelId::new(6, 2), 44).unwrap();
    let mut right = Env::reset(LevelId::new(6, 2), 44).unwrap();
    let tape = [
        Action::RightRun,
        Action::RightRun,
        Action::RightJumpRun,
        Action::Neutral,
        Action::LeftJump,
        Action::Down,
    ];
    for i in 0..500 {
        let action = tape[i % tape.len()];
        assert_eq!(left.step_action(action), right.step_action(action));
        assert_eq!(left.snapshot(), right.snapshot());
        if left.readout().terminal {
            break;
        }
    }
}

#[test]
fn checkpoint_branching_does_not_mutate_the_root() {
    let mut root = Env::reset(LevelId::new(8, 4), 9).unwrap();
    for _ in 0..30 {
        root.step_action(Action::RightRun);
    }
    let checkpoint = root.checkpoint_bytes().unwrap();
    let root_before = root.snapshot();
    let mut branch_a = Env::from_checkpoint_bytes(&checkpoint).unwrap();
    let mut branch_b = Env::from_checkpoint_bytes(&checkpoint).unwrap();
    for _ in 0..20 {
        branch_a.step_action(Action::RightJumpRun);
        branch_b.step_action(Action::RightJumpRun);
    }
    assert_eq!(branch_a.snapshot(), branch_b.snapshot());
    assert_eq!(root.snapshot(), root_before);
}

#[test]
fn observations_and_semantic_events_are_stable_and_asset_free() {
    let mut env = Env::reset(LevelId::new(2, 2), 1).unwrap();
    let first = env.render_rgb();
    assert_eq!(first.len(), 256 * 240 * 3);
    let episode = env.drain_events();
    assert!(matches!(
        episode.first(),
        Some(Event::EpisodeStarted { .. })
    ));
    for _ in 0..120 {
        env.step_action(Action::RightJumpRun);
        if env.readout().terminal {
            break;
        }
    }
    let second = env.render_rgb();
    assert_eq!(second.len(), first.len());
    assert_ne!(
        first, second,
        "the RGB observation should reflect simulation state"
    );
    let _ = env.drain_events();
    assert!(matches!(
        env.readout().power,
        PowerState::Small | PowerState::Big | PowerState::Fire | PowerState::Star
    ));
}

#[test]
fn terminal_semantics_are_explicit() {
    let mut env = Env::reset(LevelId::new(1, 1), 7).unwrap();
    for _ in 0..5000 {
        env.step_action(Action::RightRun);
        if env.readout().terminal {
            break;
        }
    }
    let readout = env.readout();
    assert!(readout.terminal);
    assert!(matches!(
        readout.terminal_reason,
        Some(TerminalReason::Completed | TerminalReason::Death | TerminalReason::Timeout)
    ));
    let after = env.snapshot();
    env.step_action(Action::LeftJumpRun);
    assert_eq!(env.snapshot(), after);
}
