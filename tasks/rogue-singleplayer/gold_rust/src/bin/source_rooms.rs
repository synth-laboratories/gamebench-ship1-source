use rogue_gold::source_level::{
    generate_new_level_slice, generate_passage_slice, generate_room_slice,
};
use serde_json::json;

fn main() {
    let cases = [
        (1, 1),
        (7, 1),
        (12345, 1),
        (12345, 6),
        (-17, 12),
        (67, 6),
        (24680, 26),
        (31415, 30),
    ];
    let reports = cases
        .iter()
        .map(|(seed, level)| {
            let draft = generate_room_slice(*seed, *level, *level, false);
            json!({"seed": seed, "level": level, "draft": draft})
        })
        .collect::<Vec<_>>();
    let passage_reports = cases
        .iter()
        .map(|(seed, level)| {
            let mut draft =
                serde_json::to_value(generate_passage_slice(*seed, *level, *level, false)).unwrap();
            draft
                .as_object_mut()
                .unwrap()
                .entry("hidden_passages")
                .or_insert_with(|| json!([]));
            json!({"seed": seed, "level": level, "draft": draft})
        })
        .collect::<Vec<_>>();
    let level_reports = cases
        .iter()
        .map(|(seed, level)| {
            let mut draft =
                serde_json::to_value(generate_new_level_slice(*seed, *level, *level, false))
                    .unwrap();
            draft
                .as_object_mut()
                .unwrap()
                .entry("hidden_passages")
                .or_insert_with(|| json!([]));
            json!({"seed": seed, "level": level, "draft": draft})
        })
        .collect::<Vec<_>>();
    println!(
        "{}",
        serde_json::to_string(
            &json!({"rooms": reports, "passages": passage_reports, "levels": level_reports})
        )
        .unwrap()
    );
}
