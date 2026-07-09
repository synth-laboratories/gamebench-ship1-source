#!/usr/bin/env python3
"""Draft hillclimb harness for the sandboxed dev-port porter prompt.

The script never asks a model to write prompt tokens.  A human/operator-authored
proposal file is appended verbatim to the current incumbent prompt to form each
candidate spec.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


HERE = Path(__file__).resolve().parent
GAMEBENCH = Path(__file__).resolve().parents[2]
BASE_SPEC = HERE / "dev_port_to_rust.sandboxed.json"
CANDIDATES = HERE / "candidates"
LEDGER = HERE / "optimize_porter_ledger.jsonl"
DEFAULT_ENVS = "sokoban-singleplayer,minihack-singleplayer"


@dataclass(frozen=True)
class AttemptScore:
    env: str
    path: Path
    attempt: str
    order: tuple[int, str]
    passed: int
    total: int
    score: float


def die(message: str) -> None:
    raise SystemExit(f"error: {message}")


def positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        die(f"expected a positive integer, got {raw!r}")
    if value < 1:
        die(f"expected a positive integer, got {raw!r}")
    return value


def parse_envs(raw: str) -> list[str]:
    envs = [part.strip() for part in raw.split(",") if part.strip()]
    if not envs:
        die("--envs must name at least one source task")
    return envs


def model_slug(model: str) -> str:
    return model.replace("/", "_")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(GAMEBENCH))
    except ValueError:
        return str(path)


def git_ls_files(pattern: str) -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "--", pattern],
        cwd=GAMEBENCH,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit status {proc.returncode}"
        die(f"git ls-files failed for {pattern!r}: {detail}")
    return [GAMEBENCH / line for line in proc.stdout.splitlines() if line.strip()]


def attempt_from_name(path: Path, slug: str, env: str) -> tuple[str, tuple[int, str]]:
    base = f"score.sandbox.{slug}.{env}"
    name = path.name
    if name == f"{base}.json":
        return "base", (1, "base")
    prefix = f"{base}.r"
    if name.startswith(prefix) and name.endswith(".json"):
        attempt = name[len(base) + 1 : -len(".json")]
        raw_order = attempt[1:]
        if raw_order.isdigit():
            return attempt, (int(raw_order), attempt)
        return attempt, (1_000_000, attempt)
    die(f"score filename does not match expected model/env pattern: {rel(path)}")


def load_score(path: Path, slug: str, env: str) -> AttemptScore:
    attempt, order = attempt_from_name(path, slug, env)
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        die(f"could not parse {rel(path)} as JSON: {exc}")
    if doc.get("source_task") != env:
        die(f"{rel(path)} source_task={doc.get('source_task')!r}, expected {env!r}")
    passed = doc.get("passed")
    total = doc.get("total")
    if not isinstance(passed, int) or not isinstance(total, int) or total <= 0:
        die(f"{rel(path)} must contain integer passed and positive integer total")
    return AttemptScore(
        env=env,
        path=path,
        attempt=attempt,
        order=order,
        passed=passed,
        total=total,
        score=passed / total,
    )


def load_committed_baseline(model: str, envs: list[str]) -> dict[str, list[AttemptScore]]:
    slug = model_slug(model)
    baseline: dict[str, list[AttemptScore]] = {}
    for env in envs:
        pattern = f"tasks/dev-port-singleplayer/score.sandbox.{slug}.{env}*.json"
        paths = git_ls_files(pattern)
        if not paths:
            die(f"no committed baseline scores found for model={model!r} env={env!r}")
        scores = [load_score(path, slug, env) for path in paths]
        baseline[env] = sorted(scores, key=lambda item: item.order)
    return baseline


def score_summary(scores: list[AttemptScore]) -> dict:
    values = [item.score for item in scores]
    return {
        "n": len(scores),
        "mean": mean(values),
        "min": min(values),
        "max": max(values),
        "attempts": scores,
    }


def comparison_incumbent(
    baseline: dict[str, list[AttemptScore]],
    envs: list[str],
    attempts_per_cell: int,
) -> tuple[float, dict[str, dict]]:
    per_env = {}
    for env in envs:
        scores = baseline[env]
        if len(scores) < attempts_per_cell:
            die(
                f"baseline for {env!r} has {len(scores)} committed attempts, "
                f"but --attempts-per-cell={attempts_per_cell}"
            )
        per_env[env] = score_summary(scores[:attempts_per_cell])
    return mean(item["mean"] for item in per_env.values()), per_env


def format_attempt(score: AttemptScore) -> str:
    return f"{score.attempt}:{score.passed}/{score.total}={score.score:.4f}"


def print_baseline(
    model: str,
    envs: list[str],
    baseline: dict[str, list[AttemptScore]],
    incumbent_mean: float,
    attempts_per_cell: int,
) -> None:
    print(f"Baseline committed scores (model={model})")
    print(f"{'env':32} {'n':>3} {'mean':>8} {'spread':>17} attempts")
    for env in envs:
        summary = score_summary(baseline[env])
        spread = f"{summary['min']:.4f}..{summary['max']:.4f}"
        attempts = ", ".join(format_attempt(score) for score in summary["attempts"])
        print(f"{env:32} {summary['n']:>3} {summary['mean']:>8.4f} {spread:>17} {attempts}")
    print(f"Incumbent comparison mean ({attempts_per_cell} attempt/cell): {incumbent_mean:.4f}")


def plan_command(spec_path: Path, model: str, env: str, attempt_tag: str) -> str:
    env_parts = {
        "SPEC": str(spec_path),
        "SOURCE_TASK": env,
        "MODEL": model,
        "ATTEMPT": attempt_tag,
    }
    prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env_parts.items())
    return f"{prefix} ./run_sandboxed.sh"


def candidate_attempt_tag(gen: int, attempt: int) -> str:
    return f"opt-g{gen}-a{attempt}"


def candidate_score_path(model: str, env: str, attempt_tag: str) -> Path:
    return HERE / f"score.sandbox.{model_slug(model)}.{env}.r{attempt_tag}.json"


def print_plan(args: argparse.Namespace, envs: list[str]) -> None:
    proposal = resolve_proposal_path(args.proposal)
    print()
    print("Plan mode: no candidate specs, ledger rows, or bench commands will be executed.")
    print(f"Candidate proposal source: {rel(proposal)}")
    print(f"Ledger target: {rel(LEDGER)}")
    print(f"Command cwd: {rel(HERE)}")
    print()
    print("Planned run matrix")
    for gen in range(1, args.generations + 1):
        spec_path = CANDIDATES / f"gen{gen}.spec.json"
        print(f"gen {gen}: would write {rel(spec_path)}")
        for env in envs:
            for attempt in range(1, args.attempts_per_cell + 1):
                tag = candidate_attempt_tag(gen, attempt)
                print(f"  {plan_command(spec_path, args.model, env, tag)}")


def load_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text())
    except FileNotFoundError:
        die(f"missing required file: {rel(path)}")
    except json.JSONDecodeError as exc:
        die(f"could not parse {rel(path)} as JSON: {exc}")
    if not isinstance(doc, dict):
        die(f"{rel(path)} must contain a JSON object")
    return doc


def porter_prompt(spec: dict) -> str:
    try:
        prompt = spec["host"]["roles"]["rust_porter"]["prompt"]
    except KeyError as exc:
        die(f"{rel(BASE_SPEC)} missing expected host.roles.rust_porter.prompt: {exc}")
    if not isinstance(prompt, str) or not prompt.strip():
        die(f"{rel(BASE_SPEC)} host.roles.rust_porter.prompt must be a non-empty string")
    return prompt


def set_porter_prompt(spec: dict, prompt: str) -> None:
    spec["host"]["roles"]["rust_porter"]["prompt"] = prompt


def resolve_proposal_path(raw: str | None) -> Path:
    if raw is None:
        return HERE / "PROPOSAL.md"
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def proposal_path_for_gen(root: Path, gen: int) -> Path:
    if root.is_dir():
        return root / f"gen{gen}.md"
    return root


def load_proposal(root: Path, gen: int) -> str:
    path = proposal_path_for_gen(root, gen)
    try:
        text = path.read_text().strip()
    except FileNotFoundError:
        die(f"missing proposal file for gen {gen}: {rel(path)}")
    if not text:
        die(f"proposal file for gen {gen} is empty: {rel(path)}")
    return text


def candidate_prompt(incumbent_prompt: str, proposal: str) -> str:
    return f"{incumbent_prompt.rstrip()}\n\n{proposal.strip()}"


def write_candidate_spec(path: Path, spec: dict) -> None:
    if path.exists():
        die(f"candidate spec already exists: {rel(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2) + "\n")


def run_bench(spec_path: Path, model: str, env: str, attempt_tag: str) -> AttemptScore:
    score_path = candidate_score_path(model, env, attempt_tag)
    if score_path.exists():
        die(f"candidate score already exists: {rel(score_path)}")
    run_env = os.environ.copy()
    run_env.update(
        {
            "SPEC": str(spec_path),
            "SOURCE_TASK": env,
            "MODEL": model,
            "ATTEMPT": attempt_tag,
        }
    )
    cmd = ["./run_sandboxed.sh"]
    try:
        subprocess.run(cmd, cwd=HERE, env=run_env, check=True)
    except subprocess.CalledProcessError as exc:
        rendered = plan_command(spec_path, model, env, attempt_tag)
        die(f"bench command failed with exit status {exc.returncode}: {rendered}")
    if not score_path.is_file():
        rendered = plan_command(spec_path, model, env, attempt_tag)
        die(f"bench command did not produce expected score {rel(score_path)}: {rendered}")
    return load_score(score_path, model_slug(model), env)


def aggregate_candidate(scores_by_env: dict[str, list[AttemptScore]]) -> tuple[float, dict]:
    per_env = {}
    for env, scores in scores_by_env.items():
        summary = score_summary(scores)
        per_env[env] = {
            "mean": summary["mean"],
            "spread": [summary["min"], summary["max"]],
            "attempts": [
                {
                    "attempt": score.attempt,
                    "score_path": rel(score.path),
                    "passed": score.passed,
                    "total": score.total,
                    "score": score.score,
                }
                for score in scores
            ],
        }
    return mean(item["mean"] for item in per_env.values()), per_env


def append_ledger(row: dict) -> None:
    with LEDGER.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def run(args: argparse.Namespace, envs: list[str], incumbent_mean: float) -> None:
    proposal_root = resolve_proposal_path(args.proposal)
    incumbent_spec = load_json(BASE_SPEC)
    incumbent_prompt = porter_prompt(incumbent_spec)

    for gen in range(1, args.generations + 1):
        proposal = load_proposal(proposal_root, gen)
        candidate_spec = json.loads(json.dumps(incumbent_spec))
        set_porter_prompt(candidate_spec, candidate_prompt(incumbent_prompt, proposal))
        spec_path = CANDIDATES / f"gen{gen}.spec.json"
        write_candidate_spec(spec_path, candidate_spec)

        scores_by_env: dict[str, list[AttemptScore]] = {}
        for env in envs:
            env_scores = []
            for attempt in range(1, args.attempts_per_cell + 1):
                tag = candidate_attempt_tag(gen, attempt)
                env_scores.append(run_bench(spec_path, args.model, env, tag))
            scores_by_env[env] = env_scores

        candidate_mean, per_env = aggregate_candidate(scores_by_env)
        verdict = "accepted" if candidate_mean > incumbent_mean else "rejected"
        append_ledger(
            {
                "gen": gen,
                "spec_path": rel(spec_path),
                "envs": envs,
                "attempts": args.attempts_per_cell,
                "mean": candidate_mean,
                "per_env": per_env,
                "verdict": verdict,
            }
        )
        print(f"gen {gen}: mean={candidate_mean:.4f} incumbent={incumbent_mean:.4f} {verdict}")
        if verdict == "accepted":
            incumbent_mean = candidate_mean
            incumbent_spec = candidate_spec
            incumbent_prompt = porter_prompt(incumbent_spec)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=positive_int, required=True)
    parser.add_argument("--envs", default=DEFAULT_ENVS, help="comma-separated source tasks")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--attempts-per-cell", type=positive_int, default=1)
    parser.add_argument("--proposal", help="PROPOSAL.md file, or a dir containing gen<N>.md files")
    parser.add_argument("--plan", action="store_true", help="print matrix and commands; execute nothing")
    args = parser.parse_args()

    envs = parse_envs(args.envs)
    baseline = load_committed_baseline(args.model, envs)
    incumbent_mean, _ = comparison_incumbent(baseline, envs, args.attempts_per_cell)
    print_baseline(args.model, envs, baseline, incumbent_mean, args.attempts_per_cell)
    if args.plan:
        print_plan(args, envs)
        return
    run(args, envs, incumbent_mean)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
