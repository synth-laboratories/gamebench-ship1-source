use rogue_gold::{command_move_delta, direction_delta, step_ok, RogueRng};
use serde_json::json;

fn main() {
    let seeds = [0, 1, 7, 12345, -17];
    let mut reports = Vec::new();
    for seed in seeds {
        let mut rng = RogueRng::new(seed);
        let values = vec![
            rng.rnd(60),
            rng.rnd(100),
            rng.rnd(3),
            rng.rnd(0),
            rng.rnd(17),
            rng.roll(3, 6),
            rng.spread(70),
            rng.gold_calc(1),
            rng.gold_calc(13),
        ];
        reports.push(json!({"seed": seed, "values": values, "final_seed": rng.seed}));
    }
    let chars = [" ", "|", "-", ".", "#", "+", "%", "*", ":", "A", "z"];
    let step = chars
        .iter()
        .map(|value| {
            let ch = value.chars().next().unwrap();
            json!({"ch": value, "ok": step_ok(ch)})
        })
        .collect::<Vec<_>>();
    let directions = ["h", "H", "j", "K", "x"];
    let dir = directions
        .iter()
        .map(|value| {
            let ch = value.chars().next().unwrap();
            json!({
                "ch": value,
                "prompt": direction_delta(ch).map(|(dy, dx)| vec![dy, dx]),
                "command": command_move_delta(ch).map(|(dy, dx)| vec![dy, dx]),
            })
        })
        .collect::<Vec<_>>();
    println!(
        "{}",
        serde_json::to_string(&json!({"rng": reports, "step_ok": step, "directions": dir}))
            .unwrap()
    );
}
