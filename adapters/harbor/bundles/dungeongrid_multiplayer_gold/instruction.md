# GameBench — DungeonGrid multiplayer gold

You are in a Harbor workspace for the GameBench DungeonGrid multiplayer gold
contract.

This task currently verifies the authoritative GameBench task bundle rather
than asking for a cleanroom rebuild. The verifier runs the same checks used by
the ReportBench/SMR contract-smoke lane:

- Python/Rust scenario-suite reset and checkpoint determinism
- Lantern Crypt Python/Rust lane comparison
- Rust event-rich mechanics probe
- Python/Rust event-rich mechanics parity probe

## Reference Surface

The mounted reference task lives at:

```text
/task/reference/dungeongrid-multiplayer
```

Useful local commands:

```bash
cd /task/reference/dungeongrid-multiplayer
python3 scripts/run_scenario_suite.py
python3 scripts/compare_gold_lanes.py
python3 scripts/run_rust_mechanics_probe.py
python3 scripts/compare_mechanics_probes.py
```

## Verifier

The Harbor verifier executes `/task/tests/test.sh`. It writes:

- `/logs/verifier/result.json`
- `/logs/verifier/reward.txt`

Reward is `1.0` only when all three contract checks pass.

## Scope Note

This is a Harbor-facing contract bundle for the current DungeonGrid gold
implementation. A future cleanroom engine-rebuild Harbor task should add hidden
fixtures and candidate-service scoring once the DungeonGrid HTTP/service
contract is finalized.
