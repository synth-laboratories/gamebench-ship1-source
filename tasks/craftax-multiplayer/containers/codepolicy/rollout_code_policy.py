"""Run a joint code policy through either Craftax-Coop HTTP runtime."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

TASK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TASK_ROOT))

from containers.http_rollout import read_action_tape, run_http_rollout, write_action_tape, write_report


def load_policy(path: Path) -> Callable[[dict[str, Any]], Any]:
    spec = importlib.util.spec_from_file_location("craftax_coop_candidate", path.resolve())
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, "act", None)
    if not callable(function):
        raise ValueError("policy must export act(observation)")
    return function


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run or replay a Craftax-Coop code policy through Python or Rust HTTP."
    )
    parser.add_argument("--base-url", required=True, help="Craftax-Coop service URL")
    parser.add_argument("--runtime", choices=("python", "rust"), required=True)
    parser.add_argument("--policy", type=Path, help="Python file exporting act(observation)")
    parser.add_argument("--seed", type=int, help="Defaults to tape seed when replaying, otherwise 101")
    parser.add_argument("--steps", type=int, help="Defaults to tape length when replaying, otherwise 100")
    parser.add_argument("--capture-actions", type=Path, help="Write the executed joint-action tape")
    parser.add_argument("--replay-actions", type=Path, help="Replay a previously captured joint-action tape")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.replay_actions and args.policy:
        parser.error("--policy and --replay-actions are mutually exclusive")
    if not args.replay_actions and not args.policy:
        parser.error("--policy is required unless --replay-actions is used")

    tape = read_action_tape(args.replay_actions) if args.replay_actions else None
    seed = args.seed if args.seed is not None else int(tape["seed"]) if tape else 101
    max_steps = args.steps if args.steps is not None else len(tape["actions"]) if tape else 100
    policy = load_policy(args.policy) if args.policy else None
    policy_metadata = (
        {"policy_path": str(args.policy.resolve())}
        if args.policy
        else dict(tape.get("policy_metadata", {}))
    )

    def choose(observations: dict[str, Any], _: int) -> tuple[dict[str, Any], dict[str, Any]]:
        assert policy is not None
        return {agent: policy(observation) for agent, observation in observations.items()}, {}

    report, actions = run_http_rollout(
        base_url=args.base_url,
        runtime=args.runtime,
        seed=seed,
        max_steps=max_steps,
        policy_kind="code",
        choose_action=choose if policy else None,
        replay_tape=tape,
        policy_metadata=policy_metadata,
    )
    if args.capture_actions:
        write_action_tape(
            args.capture_actions,
            seed=seed,
            agent_ids=report["agent_ids"],
            actions=actions,
            policy_kind="code",
            policy_metadata=policy_metadata,
        )
        report["action_tape"] = str(args.capture_actions)
    print(write_report(args.output, report))


if __name__ == "__main__":
    main()
