#!/usr/bin/env python3
"""Spectrum correctness eval for Frogs gold candidates (python HTTP lane)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


TASK_DIR = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json"
EVENTLOGS_PATH = TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json"
DEFAULT_OUTPUT = TASK_DIR / "reports" / "spectrum_eval.json"
DEFAULT_CANDIDATE_PORT = 19096
ALMOST_THRESHOLD = 0.95

for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gold_python.scenarios import run_scenario, scenario_to_task


@dataclass
class ScenarioSpectrum:
    scenario_id: str
    seed: int
    nev_hit_rate: float
    public_hit_rate: float
    resolved: bool
    almost: bool
    gold_event_count: int
    candidate_event_count: int
    http_ok: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "nev_hit_rate": round(self.nev_hit_rate, 4),
            "public_hit_rate": round(self.public_hit_rate, 4),
            "resolved": self.resolved,
            "almost": self.almost,
            "gold_event_count": self.gold_event_count,
            "candidate_event_count": self.candidate_event_count,
            "http_ok": self.http_ok,
            "failures": list(self.failures),
        }


def nev_hit_rate(expected: list[str], actual: list[str]) -> float:
    if not expected:
        return 1.0 if not actual else 0.0
    matches = sum(1 for index, event in enumerate(expected) if index < len(actual) and actual[index] == event)
    return matches / len(expected)


def public_hit_rate(expected: dict[str, Any], actual: dict[str, Any]) -> float:
    keys = sorted(set(expected) | set(actual))
    if not keys:
        return 1.0
    matches = sum(1 for key in keys if expected.get(key) == actual.get(key))
    return matches / len(keys)


def canonical_public(public: dict[str, Any], grid_hash: str = "") -> dict[str, Any]:
    payload = _canonicalize(public)
    if grid_hash:
        payload["grid_hash"] = str(grid_hash)
    return payload


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    return value


def task_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    task = scenario_to_task(entry)
    task["actions"] = list(entry.get("actions", task.get("actions", [])))
    if "checkpoint_after" in entry:
        task["checkpoint_after"] = entry["checkpoint_after"]
    if "restore_then_actions" in entry:
        task["restore_then_actions"] = list(entry["restore_then_actions"])
    return task


def gold_public_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    result = run_scenario(entry)
    public = dict(result["state"]["public"])
    return canonical_public(public, str(result["readout"].get("grid_hash", "")))


def _http_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"content-type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def http_run_scenario(base_url: str, task: dict[str, Any]) -> tuple[list[str], dict[str, Any], bool]:
    try:
        payload = _http_json(base_url, "POST", "/run_scenario", {"task": task})
        events = list(payload.get("events") or [])
        public = dict((payload.get("state") or {}).get("public") or {})
        readout = dict(payload.get("readout") or {})
        return events, canonical_public(public, str(readout.get("grid_hash", ""))), True
    except (urllib.error.URLError, RuntimeError, json.JSONDecodeError, KeyError, TimeoutError):
        return [], {}, False


def wait_for_health(base_url: str, timeout_s: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            payload = _http_json(base_url, "GET", "/health")
            if payload.get("ok") or payload.get("status") == "ok":
                return True
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            time.sleep(0.15)
    return False


def spawn_candidate_service(candidate_root: Path, port: int, service_lane: str) -> subprocess.Popen[Any]:
    run_service = candidate_root / "scripts" / "run_service.py"
    if not run_service.is_file():
        raise FileNotFoundError(f"missing candidate run_service.py: {run_service}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(candidate_root)
    env["GAMEBENCH_FROGS_HOST"] = "127.0.0.1"
    env["GAMEBENCH_FROGS_PORT"] = str(port)
    command = [sys.executable, str(run_service), "--lane", service_lane, "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f"http://127.0.0.1:{port}"
    if not wait_for_health(base_url):
        proc.terminate()
        raise RuntimeError(f"candidate HTTP service did not become healthy on {base_url} (lane={service_lane})")
    return proc


def eval_scenario_spectrum_http(entry: dict[str, Any], gold_events: list[str], base_url: str) -> ScenarioSpectrum:
    task = task_from_entry(entry)
    scenario_id = str(task.get("scenario_id", task.get("task_id", entry.get("scenario_id", "manual"))))
    seed = int(task.get("seed", entry.get("seed", 0)))
    failures: list[str] = []
    gold_public = gold_public_from_entry(entry)
    candidate_events, candidate_public, http_ok = http_run_scenario(base_url, task)
    if not http_ok:
        failures.append("http run_scenario failed")
    nev_rate = nev_hit_rate(gold_events, candidate_events)
    public_rate = public_hit_rate(gold_public, candidate_public)
    return ScenarioSpectrum(
        scenario_id=scenario_id,
        seed=seed,
        nev_hit_rate=nev_rate,
        public_hit_rate=public_rate,
        resolved=nev_rate == 1.0 and public_rate == 1.0,
        almost=nev_rate >= ALMOST_THRESHOLD and public_rate >= ALMOST_THRESHOLD,
        gold_event_count=len(gold_events),
        candidate_event_count=len(candidate_events),
        http_ok=http_ok,
        failures=failures,
    )


def eval_scenario_spectrum_local(entry: dict[str, Any], gold_events: list[str]) -> ScenarioSpectrum:
    result = run_scenario(entry)
    scenario_id = str(result["scenario_id"])
    seed = int(entry.get("seed", scenario_to_task(entry).get("seed", 0)))
    candidate_events = list(result["events"])
    candidate_public = canonical_public(
        dict(result["state"]["public"]),
        str(result["readout"].get("grid_hash", "")),
    )
    gold_public = gold_public_from_entry(entry)
    nev_rate = nev_hit_rate(gold_events, candidate_events)
    public_rate = public_hit_rate(gold_public, candidate_public)
    return ScenarioSpectrum(
        scenario_id=scenario_id,
        seed=seed,
        nev_hit_rate=nev_rate,
        public_hit_rate=public_rate,
        resolved=nev_rate == 1.0 and public_rate == 1.0,
        almost=nev_rate >= ALMOST_THRESHOLD and public_rate >= ALMOST_THRESHOLD,
        gold_event_count=len(gold_events),
        candidate_event_count=len(candidate_events),
        http_ok=True,
        failures=[],
    )


def aggregate(rows: list[ScenarioSpectrum]) -> dict[str, Any]:
    count = len(rows)
    if count == 0:
        return {
            "scenario_count": 0,
            "resolved_count": 0,
            "almost_count": 0,
            "resolved_rate": 0.0,
            "almost_rate": 0.0,
            "mean_nev_hit_rate": 0.0,
            "mean_public_hit_rate": 0.0,
        }
    return {
        "scenario_count": count,
        "resolved_count": sum(1 for row in rows if row.resolved),
        "almost_count": sum(1 for row in rows if row.almost),
        "resolved_rate": round(sum(1 for row in rows if row.resolved) / count, 4),
        "almost_rate": round(sum(1 for row in rows if row.almost) / count, 4),
        "mean_nev_hit_rate": round(sum(row.nev_hit_rate for row in rows) / count, 4),
        "mean_public_hit_rate": round(sum(row.public_hit_rate for row in rows) / count, 4),
    }


def format_table(rows: list[ScenarioSpectrum], summary: dict[str, Any]) -> str:
    lines = [
        "GameBench Frogs spectrum correctness",
        (
            f"resolved={summary['resolved_count']}/{summary['scenario_count']} "
            f"({summary['resolved_rate']}) almost={summary['almost_count']} "
            f"mean_nev={summary['mean_nev_hit_rate']} mean_public={summary['mean_public_hit_rate']}"
        ),
        "",
        "scenario_id                         | seed | nev_hit | pub_hit | resolved | http",
        "------------------------------------|------|---------|---------|----------|-----",
    ]
    for row in rows:
        lines.append(
            f"{row.scenario_id:<35} | {row.seed:>4} | {row.nev_hit_rate:>7.3f} | "
            f"{row.public_hit_rate:>7.3f} | {str(row.resolved):<8} | {str(row.http_ok):<4}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="GameBench Frogs spectrum NEV/state eval")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scenario", help="single scenario_id filter")
    parser.add_argument("--lane", choices=["local", "http"], default="http")
    parser.add_argument("--candidate-root", type=Path, default=TASK_DIR)
    parser.add_argument("--candidate-url", help="existing HTTP base URL")
    parser.add_argument("--candidate-port", type=int, default=DEFAULT_CANDIDATE_PORT)
    parser.add_argument("--service-lane", choices=["python"], default="python")
    parser.add_argument("--reference-local", action="store_true", help="score in-process Python gold reference")
    args = parser.parse_args()

    scenarios_doc = json.loads(SCENARIOS_PATH.read_text())
    gold_doc = json.loads(EVENTLOGS_PATH.read_text())
    gold_by_id = {game["scenario_id"]: game["events"] for game in gold_doc["games"]}

    proc: subprocess.Popen[Any] | None = None
    base_url = args.candidate_url
    lane = "local" if args.reference_local else args.lane

    try:
        if lane == "http" and not base_url:
            proc = spawn_candidate_service(args.candidate_root.resolve(), args.candidate_port, args.service_lane)
            base_url = f"http://127.0.0.1:{args.candidate_port}"

        rows: list[ScenarioSpectrum] = []
        for entry in scenarios_doc["scenarios"]:
            scenario_id = str(entry["scenario_id"])
            if args.scenario and scenario_id != args.scenario:
                continue
            gold_events = gold_by_id.get(scenario_id)
            if gold_events is None:
                continue
            if lane == "local":
                rows.append(eval_scenario_spectrum_local(entry, gold_events))
            else:
                rows.append(eval_scenario_spectrum_http(entry, gold_events, base_url or ""))

        summary = aggregate(rows)
        report = {
            "schema_version": "gamebench.frogs.spectrum_correctness.v1",
            "lane": lane,
            "service_lane": args.service_lane if lane == "http" else "local",
            "candidate_url": base_url or "(local)",
            "almost_threshold": ALMOST_THRESHOLD,
            "public_projection": ["board", "frogs", "submitted", "violations", "grid_hash"],
            "summary": summary,
            "scenarios": [row.to_dict() for row in rows],
            "harbor_reward": summary["mean_nev_hit_rate"],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(format_table(rows, summary))
        print(f"\nwritten: {args.output}")
        print(f"harbor_reward (mean_nev_hit_rate): {report['harbor_reward']}")
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
