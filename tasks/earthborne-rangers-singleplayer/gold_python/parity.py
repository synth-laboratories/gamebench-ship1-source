"""Shared parity constants for the synthetic EBR lane.

These names and tiers are mirrored in ``gold_rust/src/lib.rs``.
"""

EBR_ACHIEVEMENTS = [
    "select_deck",
    "first_card_played",
    "first_card_drawn",
    "first_travel",
    "first_test_resolved",
    "recover_fatigue",
    "write_reflection",
    "first_objective_progress",
    "clear_path_card",
    "complete_objective",
    "complete_day",
    "pass_test",
    "clear_obstacle",
    "zero_fatigue_day",
    "card_diversity_5",
    "day_no_violation",
    "complete_three_objectives",
    "complete_day_three",
    "all_objectives",
    "flawless_episode",
]

INTERMEDIATE_ACHIEVEMENTS = {
    "complete_objective",
    "complete_day",
    "pass_test",
    "clear_obstacle",
    "zero_fatigue_day",
    "card_diversity_5",
    "day_no_violation",
}

VERY_ADVANCED_ACHIEVEMENTS = {
    "complete_three_objectives",
    "complete_day_three",
    "all_objectives",
    "flawless_episode",
}
