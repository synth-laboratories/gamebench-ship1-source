#!/usr/bin/env python3
"""GameBench code-policy panel: Harbor Codex×2 + Pi×2 + Cursor×2 + SMR×2.

Compares harnesses on a single task (rogue-singleplayer or craftax-singleplayer)
and surfaces baseline / best / uplift from Harbor verifier receipts.

Usage:
  ./scripts/run_codepolicy_harbor2_smr2_panel.py --task rogue-singleplayer
  SLOT=slot2 ./scripts/run_codepolicy_harbor2_smr2_panel.py --task craftax-singleplayer
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SPINNER = "⠋⠙⠹⠼⠴⠦⠧⠇⠏"
SUPPORTED_TASKS = ("rogue-singleplayer", "craftax-singleplayer")
_SMR_STARTED_MARKERS = (
    "PASS: run started",
)
_SMR_START_HARD_FAIL_MARKERS = (
    "slot_manager_start_in_progress",
    "slot_manager_start_timeout",
    "storage preflight failed",
    "noncanonical_manager_root_refused",
)
_ERROR_CODE_DENYLIST = {"", "none", "unknown", "null", "—", "-"}


def _term_cols() -> int:
    try:
        return max(72, int(shutil.get_terminal_size(fallback=(120, 40)).columns))
    except OSError:
        return 120


def _fit(line: str, cols: int) -> str:
    if cols <= 1 or len(line) <= cols:
        return line
    return line[: max(1, cols - 1)] + "…"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fmt_dur(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}m{s % 60:02d}s"


def _bar(frac: float, width: int = 14) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def _short(text: str, n: int = 48) -> str:
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def _fmt_num(v: Any, digits: int = 4) -> str:
    if v is None or v == "":
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return _short(str(v), 12)


def _fmt_uplift(v: Any) -> str:
    if v is None or v == "":
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return _short(str(v), 12)
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.4f}"


def _normalize_error(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, Mapping):
        code = str(raw.get("error_code") or raw.get("code") or "").strip()
        msg = str(
            raw.get("message") or raw.get("error") or raw.get("reason") or ""
        ).strip()
        nested = ""
        detail = raw.get("detail")
        if isinstance(detail, Mapping):
            nested = _normalize_error(detail)
        elif isinstance(detail, str) and detail.strip() and detail.strip() != msg:
            nested = detail.strip()
        if nested:
            if not msg or msg in nested or nested in msg:
                msg = nested
            elif code and nested.startswith(f"{code}:"):
                msg = nested
            else:
                msg = f"{msg}; {nested}"
        if code and msg:
            if msg.startswith(f"{code}:"):
                return msg
            return f"{code}: {msg}"
        return msg or code or str(raw)
    text = str(raw).strip()
    if not text:
        return ""
    dict_match = re.search(r"(\{.*\})\s*$", text, flags=re.DOTALL)
    if dict_match:
        blob = dict_match.group(1)
        try:
            parsed = ast.literal_eval(blob)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, Mapping):
            nested = _normalize_error(parsed)
            prefix = text[: dict_match.start()].strip().rstrip(":")
            if nested and (
                "preflight denied" in prefix.lower()
                or "runtimeerror" in prefix.lower()
                or not prefix
            ):
                return nested
            if nested and prefix:
                return f"{prefix}: {nested}"
            return nested or text
    return " ".join(text.split())


def _error_pair(raw: Any, *, live_n: int = 72) -> tuple[str, str]:
    full = _normalize_error(raw)
    if not full:
        return "failed", "failed"
    return _short(full, live_n), full


_TYPED_FAILURE_CODE_RE = re.compile(
    r"(?:reason|failure_class|primary_failure_code|backend_blocker|error_code)"
    r"[\"']?\s*[:=]\s*[\"']?"
    r"([A-Za-z][A-Za-z0-9_]{2,80})"
)
_KNOWN_INFRA_FAILURE_CODES = (
    "artifact_layout_incomplete",
    "verifier_inputs_missing",
    "verifier_zero_review_rejected",
    "lifecycle_public_state_lag",
    "environment_local_docker_capacity_exhausted",
    "codex_app_server_external_sigkill",
    "sigkill_external_unknown",
    "sigkilled_not_oom",
    "worker_stopped_without_artifacts",
    "control_plane_snapshot_missing",
    "control_plane_control_snapshot_corrupt",
    "participant_turns_not_recorded",
    "inference_provider_quota_exhausted",
    "codex_auth_failed",
    "codex_auth_refresh_revoked",
    "codex_container_oom",
)


def _extract_typed_failure_code(*texts: Any) -> str | None:
    """Compatibility reader for logs until all producers emit lane receipts."""
    blob = "\n".join(str(t) for t in texts if t)
    if not blob.strip():
        return None
    # Explicit known codes win even when buried in detail prose.
    lowered = blob.lower()
    for code in _KNOWN_INFRA_FAILURE_CODES:
        if code in lowered:
            return code
    matches = _TYPED_FAILURE_CODE_RE.findall(blob)
    for raw in reversed(matches):
        code = str(raw).strip()
        if code.lower() in _ERROR_CODE_DENYLIST | {
            "failed",
            "blocked",
            "stopped",
            "error",
        }:
            continue
        if code.startswith("backend_blocker"):
            continue
        return code
    return None


def _best_error_from_log(log_path: Path) -> str:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    ranked: list[tuple[int, str]] = []
    for ln in lines:
        low = ln.lower()
        score = 0
        if "error_code" in low or "model_unavailable" in low:
            score += 5
        if "preflight denied" in low or "runtimeerror" in low:
            score += 4
        if "traceback" in low or low.startswith("error"):
            score += 2
        if score:
            ranked.append((score, ln))
    if ranked:
        ranked.sort(key=lambda item: item[0])
        return _normalize_error(ranked[-1][1])
    for ln in reversed(lines):
        if ln.lower().startswith("warning:"):
            continue
        return _normalize_error(ln)
    return _normalize_error(lines[-1])


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class Job:
    key: str
    kind: str  # harbor | smr
    label: str
    cmd: list[str]
    cwd: Path
    env: dict[str, str]
    log_path: Path
    out_dir: Path
    timeout_s: float
    task_id: str = ""
    harness: str = ""
    model: str = ""
    effort: str = ""
    index: int = 1
    proc: subprocess.Popen[str] | None = None
    started_at: float = 0.0
    ended_at: float | None = None
    exit_code: int | None = None
    phase: str = "queued"
    detail: str = "waiting to start"
    run_id: str = "—"
    baseline: str = "—"
    best: str = "—"
    uplift: str = "—"
    scout_baseline: str = "—"
    scout_best: str = "—"
    scout_uplift: str = "—"
    reward: str = "—"
    ok: bool | None = None
    notes: str = ""
    error_code: str = "—"
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def run_metadata(self) -> str:
        return f"{self.harness}/{self.model}/{self.effort}#{self.index}"

    def set(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "key": self.key,
                "kind": self.kind,
                "label": self.label or self.run_metadata,
                "run_metadata": self.run_metadata,
                "harness": self.harness,
                "model": self.model,
                "effort": self.effort,
                "index": self.index,
                "task_id": self.task_id,
                "phase": self.phase,
                "detail": self.detail,
                "run_id": self.run_id,
                "baseline": self.baseline,
                "best": self.best,
                "uplift": self.uplift,
                "scout_baseline": self.scout_baseline,
                "scout_best": self.scout_best,
                "scout_uplift": self.scout_uplift,
                "reward": self.reward,
                "ok": self.ok,
                "notes": self.notes,
                "error_code": self.error_code,
                "exit_code": self.exit_code,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "timeout_s": self.timeout_s,
                "out_dir": str(self.out_dir),
                "log_path": str(self.log_path),
            }


class Panel:
    def __init__(self, jobs: list[Job], *, enabled: bool) -> None:
        self.jobs = jobs
        self.enabled = enabled and sys.stdout.isatty()
        self._drawn_lines = 0
        self._i = 0
        self._lock = threading.Lock()
        self._last_nontty_fingerprint = ""
        self._meta_w = max((len(j.run_metadata) for j in jobs), default=12)
        self._meta_w = max(self._meta_w, len("run_metadata"))

    def _row(self, job: Job, *, spin: str, now: float) -> str:
        snap = job.snapshot()
        started = snap["started_at"] or now
        ended = snap["ended_at"]
        elapsed = (ended or now) - started if started else 0.0
        frac = elapsed / max(1.0, float(snap["timeout_s"]))
        if snap["phase"] in {"done", "failed", "error"}:
            mark = "✓" if snap["ok"] else "✗"
        else:
            mark = spin
        rid = str(snap["run_id"] or "—")
        if len(rid) > 10:
            rid = rid[:8]
        uplift = str(snap.get("uplift") or "—")
        if len(uplift) > 10:
            uplift = uplift[:9] + "…"
        detail_src = str(snap.get("detail") or "")
        if snap["phase"] in {"failed", "error"}:
            notes = str(snap.get("notes") or "").strip()
            err_code = str(snap.get("error_code") or "").strip()
            if err_code and err_code != "—":
                detail_src = err_code if not notes else f"{err_code}: {notes}"
            elif notes:
                detail_src = notes
            detail_budget = 100
        else:
            detail_budget = 36
        return (
            f"{mark} {snap['run_metadata']:<{self._meta_w}} │ {snap['phase']:<8} │ "
            f"{_bar(frac)} {_fmt_dur(elapsed):>6} │ "
            f"Δ={uplift:<10} │ id={rid:<8} │ {_short(detail_src, detail_budget)}"
        )

    def render(self) -> None:
        with self._lock:
            self._i += 1
            spin = SPINNER[self._i % len(SPINNER)]
            now = time.time()
            cols = _term_cols()
            lines = [_fit(self._row(job, spin=spin, now=now), cols) for job in self.jobs]
            block = "\n".join(lines)
            if not self.enabled:
                fingerprint = "|".join(
                    f"{j.snapshot()['phase']}:{j.snapshot().get('uplift')}:"
                    f"{j.snapshot().get('detail')}:{j.snapshot().get('ok')}"
                    for j in self.jobs
                )
                if fingerprint == self._last_nontty_fingerprint and self._i != 1:
                    return
                self._last_nontty_fingerprint = fingerprint
                stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"--- panel {stamp}Z ---", flush=True)
                print(block, flush=True)
                return
            if self._drawn_lines:
                sys.stdout.write(f"\033[{self._drawn_lines}A")
            sys.stdout.write("\033[J")
            sys.stdout.write(block + "\n")
            sys.stdout.flush()
            self._drawn_lines = len(lines)

    def finalize(self) -> None:
        if self.enabled and self._drawn_lines:
            # Leave final frame in place.
            pass


def _apply_uplift_fields(job: Job, payload: Mapping[str, Any]) -> None:
    data: dict[str, Any] = dict(payload)
    nested = payload.get("verifier")
    if isinstance(nested, Mapping):
        # Nested verifier wins for score fields when top-level is missing.
        for key in (
            "baseline_score",
            "best_score",
            "delta_vs_baseline",
            "best_candidate_id",
            "harbor_reward",
            "reward",
            "baseline_mean_scout_score",
            "best_mean_scout_score",
            "delta_mean_scout_score",
            "best_scout_candidate_id",
            "score_metric",
        ):
            if data.get(key) is None and nested.get(key) is not None:
                data[key] = nested.get(key)
    baseline = data.get("baseline_score")
    best = data.get("best_score")
    delta = data.get("delta_vs_baseline")
    if delta is None and baseline is not None and best is not None:
        try:
            delta = float(best) - float(baseline)
        except (TypeError, ValueError):
            delta = None
    reward = data.get("reward")
    if reward is None:
        reward = data.get("harbor_reward")
    updates: dict[str, Any] = {}
    if baseline is not None:
        updates["baseline"] = _fmt_num(baseline)
    if best is not None:
        updates["best"] = _fmt_num(best)
    if delta is not None:
        updates["uplift"] = _fmt_uplift(delta)
        updates["detail"] = f"Δ={_fmt_uplift(delta)} best={_fmt_num(best)}"
    if reward is not None:
        updates["reward"] = _fmt_num(reward)
    scout_base = data.get("baseline_mean_scout_score")
    scout_best = data.get("best_mean_scout_score")
    scout_delta = data.get("delta_mean_scout_score")
    if scout_delta is None and scout_base is not None and scout_best is not None:
        try:
            scout_delta = float(scout_best) - float(scout_base)
        except (TypeError, ValueError):
            scout_delta = None
    if scout_base is not None:
        updates["scout_baseline"] = _fmt_num(scout_base)
    if scout_best is not None:
        updates["scout_best"] = _fmt_num(scout_best)
    if scout_delta is not None:
        updates["scout_uplift"] = _fmt_uplift(scout_delta)
        # When headline score is saturated, live detail should show scout signal.
        try:
            headline_flat = delta is not None and abs(float(delta)) < 1e-9
        except (TypeError, ValueError):
            headline_flat = False
        if headline_flat:
            updates["detail"] = (
                f"scoutΔ={_fmt_uplift(scout_delta)} "
                f"scout={_fmt_num(scout_best)}"
            )
    cand = data.get("best_scout_candidate_id") or data.get("best_candidate_id")
    if cand:
        updates["run_id"] = str(cand)[:10]
    if updates:
        job.set(**updates)


def _poll_harbor(job: Job) -> None:
    receipt = _load_json(job.out_dir / "lane-receipt.json")
    if receipt:
        _apply_uplift_fields(job, receipt)
        if job.exit_code is not None:
            ok = job.exit_code == 0
            if receipt.get("verify_rc") not in (None, 0):
                ok = False
                live, full = _error_pair(
                    receipt.get("verifier_error")
                    or receipt.get("error")
                    or f"verify_rc={receipt.get('verify_rc')}"
                )
                job.set(phase="failed", detail=live, notes=full or job.notes, ok=False)
                return
            job.set(phase=("done" if ok else "failed"), ok=ok)
        else:
            job.set(phase="scoring", detail=job.detail or "verifier ready")
        return

    result = _load_json(job.out_dir / "logs" / "verifier" / "result.json")
    if result:
        _apply_uplift_fields(job, result)
        if job.exit_code is None:
            job.set(phase="scoring")
        return

    if job.exit_code is None and job.phase in {"queued", "starting"}:
        job.set(phase="running", detail="harbor agent")


def _parse_smr_log_metrics(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, pat in (
        ("baseline_score", r"baseline_score[\"']?\s*[:=]\s*([0-9.]+)"),
        ("best_score", r"best_score[\"']?\s*[:=]\s*([0-9.]+)"),
        ("delta_vs_baseline", r"delta_vs_baseline[\"']?\s*[:=]\s*([-+0-9.]+)"),
        ("reward", r"\breward[\"']?\s*[:=]\s*([0-9.]+)"),
        ("run_id", r"\brun_id[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)"),
    ):
        m = re.search(pat, text)
        if m:
            out[key] = m.group(1)
    return out


def _extract_smr_evidence_path(text: str) -> Path | None:
    # Prefer the last evidence path; ReportBench may print staging then final.
    matches = re.findall(r"(?m)^\s*evidence:\s+(\S+)\s*$", text)
    if not matches:
        matches = re.findall(r"\bevidence:\s+(\S+)", text)
    for raw in reversed(matches):
        path = Path(raw.strip().rstrip(",;"))
        if path.is_dir():
            return path
    return None


def _normalized_failure_code(raw: Any) -> str | None:
    code = str(raw or "").strip().lower()
    if code in _ERROR_CODE_DENYLIST:
        return None
    if not code[0].isalpha() or not code.replace("_", "").isalnum():
        return None
    return code


def _manifest_artifact_path(evidence: Path, relative_path: str) -> Path | None:
    canonical = evidence / relative_path
    if canonical.is_file():
        return canonical
    manifest = _load_json(evidence / "evidence_manifest.json") or {}
    bundle = manifest.get("artifact_bundle")
    rows = bundle.get("manifest") if isinstance(bundle, Mapping) else None
    resolved: list[Path] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            raw_path = str(row.get("path") or "").strip()
            if raw_path == relative_path or raw_path.endswith(f"/{relative_path}"):
                candidate = evidence / raw_path
                if candidate.is_file():
                    resolved.append(candidate)
    if len(resolved) == 1:
        return resolved[0]

    # COMPAT: pre-manifest evidence roots. Remove after all lane receipts carry
    # reportbench.smr_benchmark_outcome.v1 and an artifact bundle manifest.
    basename = Path(relative_path).name
    suffix = Path(relative_path).as_posix()
    matches = sorted(
        path
        for path in evidence.rglob(basename)
        if path.is_file() and path.as_posix().endswith(suffix)
    )
    return matches[0] if len(matches) == 1 else None


def _leaderboard_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    baseline = payload.get("baseline_score")
    best = payload.get("best_score")
    candidate_id = payload.get("best_candidate_id")
    delta = None
    rankings = payload.get("rankings")
    if isinstance(rankings, list):
        accepted_rows = [
            row
            for row in rankings
            if isinstance(row, Mapping) and row.get("accepted") is True
        ]
        if candidate_id is not None:
            selected = next(
                (
                    row
                    for row in rankings
                    if isinstance(row, Mapping)
                    and str(row.get("candidate_id") or "") == str(candidate_id)
                ),
                None,
            )
        else:
            selected = accepted_rows[0] if accepted_rows else None
        if isinstance(selected, Mapping):
            best = best if best is not None else selected.get("score")
            delta = selected.get("delta_vs_baseline")
            candidate_id = candidate_id or selected.get("candidate_id")
    if delta is None and baseline is not None and best is not None:
        try:
            delta = float(best) - float(baseline)
        except (TypeError, ValueError):
            delta = None
    return {
        "baseline_score": baseline,
        "best_score": best,
        "delta_vs_baseline": delta,
        "best_candidate_id": candidate_id,
    }


def _structured_evidence_receipt(evidence: Path) -> dict[str, Any]:
    report = _load_json(evidence / "artifacts" / "reportbench_output.json") or {}
    failure = (
        _load_json(evidence / "reportbench_run_failure.json")
        or _load_json(evidence / "artifacts" / "run_failure.json")
        or {}
    )
    summary = _load_json(evidence / "evals_summary.json") or {}
    outcome_raw = report.get("smr_benchmark_outcome")
    if not isinstance(outcome_raw, Mapping):
        outcome_raw = failure.get("smr_benchmark_outcome")
    outcome = outcome_raw if isinstance(outcome_raw, Mapping) else {}
    decision = str(outcome.get("panel_decision") or "").strip().lower()
    if decision == "pass":
        error_code = None
    else:
        error_code = _normalized_failure_code(outcome.get("code"))
        if error_code is None:
            error_code = _normalized_failure_code(
                failure.get("primary_failure_code") or failure.get("reason")
            )
        if error_code is None:
            error_code = _normalized_failure_code(summary.get("failure_code"))
    summary_verdict = summary.get("verdict")
    summary_reason = (
        summary_verdict.get("reason")
        if isinstance(summary_verdict, Mapping)
        else None
    )
    detail = str(
        outcome.get("detail")
        or failure.get("detail")
        or summary_reason
        or ""
    ).strip()
    reward = report.get("primary_score")
    if reward is None:
        reward_payload = report.get("reward")
        if isinstance(reward_payload, Mapping):
            reward = reward_payload.get("value")
    return {
        "panel_decision": decision or None,
        "error_code": error_code,
        "error_detail": detail or None,
        "reward": reward,
        "best_candidate_id": report.get("best_candidate_id"),
        "run_id": report.get("run_id") or failure.get("run_id") or summary.get("run_id"),
    }


def _hydrate_smr_metrics_from_evidence(evidence: Path) -> dict[str, Any]:
    """Project typed receipts and manifest-addressed score evidence."""
    out = _structured_evidence_receipt(evidence)
    scout_path = _manifest_artifact_path(
        evidence,
        "artifacts/gamebench_hillclimb/leaderboard.json",
    )
    heldout_path = _manifest_artifact_path(
        evidence,
        "artifacts/gamebench_hillclimb_heldout/leaderboard.json",
    )
    scout = _load_json(scout_path) if scout_path is not None else None
    heldout = _load_json(heldout_path) if heldout_path is not None else None
    if isinstance(scout, Mapping):
        scout_metrics = _leaderboard_metrics(scout)
        out["baseline_mean_scout_score"] = scout_metrics.get("baseline_score")
        out["best_mean_scout_score"] = scout_metrics.get("best_score")
        out["delta_mean_scout_score"] = scout_metrics.get("delta_vs_baseline")
        out["best_scout_candidate_id"] = scout_metrics.get("best_candidate_id")
    if isinstance(heldout, Mapping):
        out.update(_leaderboard_metrics(heldout))
    elif isinstance(scout, Mapping):
        out.update(_leaderboard_metrics(scout))
    out["evidence_path"] = str(evidence)
    return out


def _collect_smr_metrics(*, log_text: str = "", receipt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Project receipts first; log scraping is a temporary compatibility layer."""
    metrics: dict[str, Any] = {}
    if receipt:
        for key, value in receipt.items():
            if value is not None and key != "error":
                metrics[key] = value
    evidence: Path | None = None
    receipt_evidence = str(metrics.get("evidence_path") or "").strip()
    if receipt_evidence:
        candidate = Path(receipt_evidence)
        if candidate.is_dir():
            evidence = candidate
    if log_text:
        for key, value in _parse_smr_log_metrics(log_text).items():
            metrics.setdefault(key, value)
        if evidence is None:
            evidence = _extract_smr_evidence_path(log_text)
    if evidence is not None:
        hydrated = _hydrate_smr_metrics_from_evidence(evidence)
        for key, value in hydrated.items():
            if value is not None:
                metrics[key] = value
    return metrics


def _smr_receipt_payload(job: Job, *, exit_code: int, error: str | None = None) -> dict[str, Any]:
    try:
        text = job.log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    metrics = _collect_smr_metrics(log_text=text)
    error_code = _normalized_failure_code(metrics.get("error_code"))
    if error_code is None:
        error_code = _extract_typed_failure_code(
            error,
            job.snapshot().get("error_code"),
            job.snapshot().get("notes"),
            text,
        )
    error_detail = str(metrics.get("error_detail") or error or "").strip() or None
    payload: dict[str, Any] = {
        "schema_version": "gamebench.smr.lane_receipt.v1",
        "task_id": job.task_id,
        "exit_code": exit_code,
        "baseline_score": metrics.get("baseline_score"),
        "best_score": metrics.get("best_score"),
        "delta_vs_baseline": metrics.get("delta_vs_baseline"),
        "reward": metrics.get("reward"),
        "best_candidate_id": metrics.get("best_candidate_id"),
        "baseline_mean_scout_score": metrics.get("baseline_mean_scout_score"),
        "best_mean_scout_score": metrics.get("best_mean_scout_score"),
        "delta_mean_scout_score": metrics.get("delta_mean_scout_score"),
        "evidence_path": metrics.get("evidence_path"),
        "run_id": metrics.get("run_id") or (job.run_id if job.run_id != "—" else None),
        "panel_decision": metrics.get("panel_decision"),
        "error_code": error_code,
    }
    if error_detail and (exit_code != 0 or metrics.get("panel_decision") != "pass"):
        # Keep typed code at the front of durable error text for panel/grep.
        if error_code and not error_detail.startswith(f"{error_code}:"):
            payload["error"] = f"{error_code}: {error_detail}"
        else:
            payload["error"] = error_detail
    return payload


def _poll_smr(job: Job) -> None:
    receipt = _load_json(job.out_dir / "smr-receipt.json")
    try:
        text = job.log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    if receipt:
        metrics = _collect_smr_metrics(log_text=text, receipt=receipt)
        # If the on-disk receipt is missing scores but evidence exists, rewrite it.
        if (
            metrics.get("baseline_score") is not None
            and receipt.get("baseline_score") is None
            and job.exit_code is not None
        ):
            try:
                refreshed = _smr_receipt_payload(
                    job,
                    exit_code=int(job.exit_code),
                    error=str(receipt.get("error") or "") or None,
                )
                (job.out_dir / "smr-receipt.json").write_text(
                    json.dumps(refreshed, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                metrics = refreshed
            except OSError:
                pass
        _apply_uplift_fields(job, metrics)
        if metrics.get("run_id"):
            job.set(run_id=str(metrics["run_id"])[:10])
        err_code = _normalized_failure_code(metrics.get("error_code"))
        if err_code is None:
            err_code = _extract_typed_failure_code(
                receipt.get("error_code"),
                receipt.get("error"),
                receipt.get("primary_failure_code"),
                receipt.get("reason"),
                text,
            )
        if err_code:
            job.set(error_code=err_code)
        if receipt.get("error"):
            live, full = _error_pair(receipt["error"])
            if err_code and not full.startswith(f"{err_code}:"):
                full = f"{err_code}: {full}"
                live = _short(full, 72)
            job.set(phase="failed", detail=live, notes=full, ok=False)
            return
        if job.exit_code is not None:
            ok = job.exit_code == 0
            job.set(phase=("done" if ok else "failed"), ok=ok)
        return

    if text:
        metrics = _collect_smr_metrics(log_text=text)
        if metrics:
            _apply_uplift_fields(job, metrics)
            if metrics.get("run_id"):
                job.set(run_id=str(metrics["run_id"])[:10])
        err_code = _extract_typed_failure_code(text)
        if err_code:
            job.set(error_code=err_code)
    if job.exit_code is None and job.phase in {"queued", "starting"}:
        job.set(phase="running", detail="smr launch")


def _supervise(job: Job, poller) -> None:
    assert job.proc is not None
    log_fh = job.log_path.open("a", encoding="utf-8")
    try:
        assert job.proc.stdout is not None
        for line in job.proc.stdout:
            log_fh.write(line)
            log_fh.flush()
            text = line.strip()
            if text:
                job.set(detail=_short(text, 48))
                poller()
        rc = job.proc.wait()
        job.set(exit_code=rc, ended_at=time.time())
        poller()
        snap = job.snapshot()
        if snap["ok"] is None:
            job.set(ok=(rc == 0), phase=("done" if rc == 0 else "failed"))
        if rc != 0:
            notes = str(snap.get("notes") or "").strip()
            if not notes or notes.startswith("exit ") or len(notes) < 12:
                log_err = _best_error_from_log(job.log_path)
                if log_err:
                    live, full = _error_pair(log_err)
                    job.set(detail=live, notes=full)
                elif not notes:
                    job.set(notes=f"exit {rc}")
            else:
                live, full = _error_pair(notes)
                job.set(detail=live, notes=full)
            # Write SMR receipt on failure for durable panel notes.
            if job.kind == "smr":
                payload = _smr_receipt_payload(
                    job,
                    exit_code=rc,
                    error=str(job.snapshot().get("notes") or f"exit {rc}"),
                )
                (job.out_dir / "smr-receipt.json").write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _apply_uplift_fields(job, payload)
                if payload.get("error_code"):
                    job.set(error_code=str(payload["error_code"]))
                if payload.get("error"):
                    live, full = _error_pair(payload["error"])
                    job.set(detail=live, notes=full, ok=False, phase="failed")
        else:
            if job.kind == "smr":
                payload = _smr_receipt_payload(job, exit_code=0)
                (job.out_dir / "smr-receipt.json").write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _apply_uplift_fields(job, payload)
                if payload.get("error_code"):
                    job.set(error_code=str(payload["error_code"]))
        if snap["phase"] not in {"done", "failed", "error"}:
            job.set(phase=("done" if rc == 0 else "failed"))
    finally:
        log_fh.close()


def _poll_job_safe(job: Job, poller) -> None:
    try:
        poller()
    except Exception as exc:  # noqa: BLE001
        live, full = _error_pair(f"poll_err:{type(exc).__name__}: {exc}")
        job.set(detail=live, notes=full)


def _print_failures(jobs: list[Job]) -> None:
    fails = [
        job
        for job in jobs
        if job.snapshot()["ok"] is False or (job.exit_code or 0) != 0
    ]
    if not fails:
        return
    print("\nfailures:")
    width = max(60, _term_cols() - 4)
    for job in fails:
        snap = job.snapshot()
        msg = str(snap.get("notes") or snap.get("detail") or "unknown error").strip()
        print(f"  {snap.get('run_metadata') or snap['label']}")
        wrapped = " ".join(msg.split())
        while wrapped:
            chunk = wrapped[:width]
            if len(wrapped) > width:
                split_at = chunk.rfind(" ")
                if split_at > width // 2:
                    chunk = chunk[:split_at]
            print(f"    {chunk}")
            wrapped = wrapped[len(chunk) :].lstrip()


def _print_table(jobs: list[Job], *, task_id: str) -> None:
    rows: list[dict[str, str]] = []
    for job in jobs:
        snap = job.snapshot()
        status = "ok" if snap["ok"] is True else ("fail" if snap["ok"] is False else snap["phase"])
        wall = "—"
        if snap.get("started_at"):
            ended = snap.get("ended_at") or time.time()
            wall = _fmt_dur(float(ended) - float(snap["started_at"]))
        rows.append(
            {
                "run_metadata": str(snap.get("run_metadata") or snap["label"]),
                "task": task_id.replace("-singleplayer", ""),
                "status": status,
                "baseline": str(snap.get("baseline") or "—"),
                "best": str(snap.get("best") or "—"),
                "uplift": str(snap.get("uplift") or "—"),
                "scout_b": str(snap.get("scout_baseline") or "—"),
                "scout_best": str(snap.get("scout_best") or "—"),
                "scout_Δ": str(snap.get("scout_uplift") or "—"),
                "reward": str(snap.get("reward") or "—"),
                "error": (
                    f"{snap.get('error_code')}: {_short(str(snap.get('notes') or ''), 36)}"
                    if str(snap.get("error_code") or "") not in _ERROR_CODE_DENYLIST
                    and str(snap.get("notes") or "").strip()
                    else str(snap.get("error_code") or "—")
                ),
                "wall": wall,
                "run": str(snap.get("run_id") or "—"),
            }
        )
    headers = (
        "run_metadata",
        "task",
        "status",
        "baseline",
        "best",
        "uplift",
        "scout_b",
        "scout_best",
        "scout_Δ",
        "reward",
        "error",
        "wall",
        "run",
    )
    widths = [len(h) for h in headers]
    for row in rows:
        for i, key in enumerate(headers):
            widths[i] = max(widths[i], len(str(row[key])))
    fmt = "  ".join(f"{{:{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*[str(row[h]) for h in headers]))


def _default_timeout(task_id: str) -> float:
    if task_id.startswith("craftax"):
        return 5400.0
    return 3600.0


def _discover_slotctl_bin() -> Path | None:
    runtime = str(os.environ.get("SYNTH_SLOT_MANAGER_RUNTIME_DIR") or "").strip()
    if runtime:
        cand = Path(runtime) / "synth-local-slotctl"
        if cand.is_file():
            return cand
    which = shutil.which("synth-local-slotctl")
    if which:
        return Path(which)
    # Fall back to the binary next to the live managerd process.
    try:
        out = subprocess.check_output(
            ["ps", "-ax", "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        if "synth-local-slot-managerd" not in line:
            continue
        if "--internal-" in line:
            continue
        token = line.strip().split()[0]
        managerd = Path(token)
        cand = managerd.with_name("synth-local-slotctl")
        if cand.is_file():
            return cand
    runtime_root = Path.home() / ".synth-dev" / "runtime"
    if runtime_root.is_dir():
        matches = sorted(runtime_root.glob("*/synth-local-slotctl"))
        if matches:
            return matches[-1]
    return None


def _slotctl_status_payload(
    *,
    slot: str,
    synth_dev_root: Path,
    slotctl: Path,
) -> dict[str, Any] | None:
    env = os.environ.copy()
    env["SYNTH_DEV_ROOT"] = str(synth_dev_root)
    env["SYNTH_SLOT_MANAGER_CANONICAL_ROOT"] = str(synth_dev_root)
    try:
        proc = subprocess.run(
            [str(slotctl), "status", slot],
            env=env,
            cwd=str(synth_dev_root),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}
    text = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {"_error": text or f"slotctl_status_rc={proc.returncode}"}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Some builds emit trailing logs; take the last JSON object.
        start = text.rfind("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {"_error": text[:400]}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {"_error": text[:400]}
    return payload if isinstance(payload, dict) else {"_error": "status_not_object"}


def _resolve_live_slot_manager_root(
    *,
    slot: str,
    candidates: list[Path],
    slotctl: Path,
) -> tuple[Path, dict[str, Any]]:
    """Pick the synth-dev root that owns the live slot-manager slot state."""

    errors: list[str] = []
    for root in candidates:
        if not root.is_dir():
            continue
        payload = _slotctl_status_payload(
            slot=slot, synth_dev_root=root, slotctl=slotctl
        )
        if payload is None:
            errors.append(f"{root}: empty_status")
            continue
        if payload.get("_error"):
            errors.append(f"{root}: {payload['_error']}")
            continue
        state_dir = str(payload.get("state_dir") or "").strip()
        if state_dir:
            observed = Path(state_dir).resolve()
            # .../temp/slotN → synth-dev root
            if observed.name.startswith("slot") and observed.parent.name == "temp":
                return observed.parent.parent, payload
        return root.resolve(), payload
    detail = "; ".join(errors) if errors else "no_candidates"
    raise RuntimeError(f"slot_manager_root_unresolved:{detail}")


def _slot_services_ready(payload: Mapping[str, Any]) -> tuple[bool, str]:
    services = payload.get("services")
    if not isinstance(services, list):
        return False, "services_missing"
    by_name = {
        str(item.get("service") or "").strip(): item
        for item in services
        if isinstance(item, Mapping)
    }
    missing: list[str] = []
    for name in ("backend-api", "smr-runtime"):
        item = by_name.get(name)
        if not isinstance(item, Mapping):
            missing.append(f"{name}=absent")
            continue
        if not item.get("ready") or str(item.get("health") or "") != "healthy":
            missing.append(
                f"{name}=ready={item.get('ready')} health={item.get('health')}"
            )
    if missing:
        return False, ",".join(missing)
    return True, "ok"


def _preflight_slot_for_smr(
    *,
    slot: str,
    synth_dev_root: Path,
    slotctl: Path,
    timeout_s: float = 90.0,
) -> dict[str, Any]:
    """Block until slotctl status is healthy; fail loudly on start-in-progress stall."""

    deadline = time.time() + max(5.0, timeout_s)
    last_err = "not_checked"
    while time.time() < deadline:
        payload = _slotctl_status_payload(
            slot=slot, synth_dev_root=synth_dev_root, slotctl=slotctl
        ) or {"_error": "empty_status"}
        if payload.get("_error"):
            last_err = str(payload["_error"])
            if "slot_manager_start_in_progress" in last_err:
                time.sleep(2.0)
                continue
            time.sleep(1.0)
            continue
        ready, detail = _slot_services_ready(payload)
        if ready:
            return payload
        last_err = detail
        time.sleep(2.0)
    raise RuntimeError(
        f"smr_slot_preflight_failed:slot={slot}:root={synth_dev_root}:detail={last_err}"
    )


def _smr_log_indicates_started(text: str) -> bool:
    return any(marker in text for marker in _SMR_STARTED_MARKERS)


def _smr_log_indicates_hard_start_failure(text: str) -> str | None:
    for marker in _SMR_START_HARD_FAIL_MARKERS:
        if marker in text:
            return marker
    return None


def _kill_job_tree(job: Job, *, reason: str) -> None:
    proc = job.proc
    if proc is None or proc.poll() is not None:
        if job.exit_code is None:
            job.set(
                phase="failed",
                ok=False,
                exit_code=job.exit_code if job.exit_code is not None else 130,
                ended_at=time.time(),
                detail=_short(reason, 48),
                notes=reason,
            )
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    deadline = time.time() + 5.0
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.1)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
    job.set(
        phase="failed",
        ok=False,
        exit_code=proc.poll() if proc.poll() is not None else 130,
        ended_at=time.time(),
        detail=_short(reason, 48),
        notes=reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        required=True,
        choices=SUPPORTED_TASKS,
        help="GameBench code-policy task id",
    )
    parser.add_argument("--slot", default=os.environ.get("SLOT", "slot2"))
    parser.add_argument(
        "--gamebench",
        default=os.environ.get("GAMEBENCH_ROOT", ""),
        help="GameBench checkout root",
    )
    parser.add_argument(
        "--evals",
        default=os.environ.get("GAMEBENCH_EVALS_ROOT", os.environ.get("EVALS_ROOT", "")),
    )
    parser.add_argument("--harbor-model", default="gpt-5.6-luna")
    parser.add_argument("--harbor-effort", default="high")
    parser.add_argument("--pi-model", default="gpt-5.6-luna")
    parser.add_argument("--pi-effort", default="high")
    parser.add_argument("--cursor-model", default="gpt-5.6-luna")
    parser.add_argument("--cursor-effort", default="medium")
    parser.add_argument("--smr-model", default="gpt-5.6-luna")
    parser.add_argument("--smr-effort", default="medium")
    parser.add_argument(
        "--lanes",
        choices=("all", "smr"),
        default=os.environ.get("GAMEBENCH_PANEL_LANES", "all"),
        help="Lane set: all (Harbor×6 + SMR) or smr (SMR only)",
    )
    parser.add_argument(
        "--smr-count",
        type=int,
        default=int(os.environ.get("GAMEBENCH_SMR_COUNT", "1")),
        help="Number of parallel SMR lanes (default 1; lean Docker hosts cannot fit 2×2GiB env reservations)",
    )
    parser.add_argument("--smr-stagger-seconds", type=float, default=8.0)
    parser.add_argument(
        "--smr-start-timeout-seconds",
        type=float,
        default=float(os.environ.get("GAMEBENCH_SMR_START_TIMEOUT_S", "180")),
        help="Abort entire panel if SMR lanes do not PASS: run started within this window",
    )
    args = parser.parse_args(argv)

    task_id = str(args.task)
    gb_root = Path(args.gamebench or Path(__file__).resolve().parents[1]).resolve()
    preferred_evals = gb_root.parent / "evals-execution-target-20260719"
    preferred_synth_ai = gb_root.parent / "synth-ai-execution-target-20260719"
    evals_arg = str(args.evals or "").strip()
    if evals_arg:
        evals_root = Path(evals_arg).expanduser().resolve()
    elif preferred_evals.is_dir() and (preferred_evals / "reportbench").is_dir():
        evals_root = preferred_evals.resolve()
    else:
        evals_root = (gb_root.parent / "evals").resolve()
    synth_ai_env = str(os.environ.get("SYNTH_AI") or "").strip()
    if synth_ai_env:
        synth_ai_root = Path(synth_ai_env).expanduser().resolve()
    elif preferred_synth_ai.is_dir() and (preferred_synth_ai / "synth_ai").is_dir():
        synth_ai_root = preferred_synth_ai.resolve()
    else:
        synth_ai_root = (evals_root.parent / "synth-ai").resolve()
    synth_dev = Path(os.environ.get("SYNTH_DEV", gb_root.parent / "synth-dev")).resolve()
    slot = str(args.slot)
    harbor_run = gb_root / "adapters" / "harbor" / "run.sh"
    mr_run = gb_root / "adapters" / "managedresearch" / "run.sh"

    launch_context = evals_root / "reportbench" / "launch_context.py"
    for path, label in (
        (harbor_run, "harbor adapter"),
        (mr_run, "managedresearch adapter"),
        (evals_root / "reportbench", "evals reportbench"),
        (launch_context, "reportbench launch_context.py"),
        (synth_ai_root / "synth_ai" / "managed_research" / "models" / "run_launch.py", "synth-ai run_launch.py"),
    ):
        if not path.exists():
            print(f"missing {label}: {path}", file=sys.stderr)
            return 2
    if "platform_resolved" not in launch_context.read_text(encoding="utf-8", errors="replace"):
        print(
            f"evals at {evals_root} cannot project execution_target "
            "(missing platform_resolved in launch_context.py)",
            file=sys.stderr,
        )
        print(
            "Set GAMEBENCH_EVALS_ROOT=~/Documents/GitHub/evals-execution-target-20260719",
            file=sys.stderr,
        )
        return 2
    run_launch = (
        synth_ai_root
        / "synth_ai"
        / "managed_research"
        / "models"
        / "run_launch.py"
    )
    if "execution_target" not in run_launch.read_text(encoding="utf-8", errors="replace"):
        print(
            f"synth-ai at {synth_ai_root} cannot serialize execution_target",
            file=sys.stderr,
        )
        print(
            "Set SYNTH_AI=~/Documents/GitHub/synth-ai-execution-target-20260719",
            file=sys.stderr,
        )
        return 2

    slotctl = _discover_slotctl_bin()
    if slotctl is None:
        print("missing synth-local-slotctl (slot-manager runtime not found)", file=sys.stderr)
        return 2

    jwt_slot_root = gb_root.parent / "synth-dev-jwt-admission-dev-20260717"
    projection_root = gb_root.parent / "synth-dev-projection-validation-20260719"
    candidates = []
    for root in (
        Path(os.environ.get("SYNTH_SLOT_MANAGER_CANONICAL_ROOT") or ""),
        Path(os.environ.get("SYNTH_DEV_ROOT") or ""),
        projection_root,
        jwt_slot_root,
        synth_dev,
    ):
        if not str(root):
            continue
        resolved = root.expanduser().resolve()
        if resolved not in candidates:
            candidates.append(resolved)

    try:
        slot_manager_root, status_payload = _resolve_live_slot_manager_root(
            slot=slot,
            candidates=candidates,
            slotctl=slotctl,
        )
    except RuntimeError as exc:
        print(f"slot manager root resolve failed: {exc}", file=sys.stderr)
        return 2

    slot_contract = slot_manager_root / "temp" / slot / "local-eval-contract.json"
    if not slot_contract.exists():
        # Fall back to sibling synth-dev contract if the live root has none.
        alt = synth_dev / "temp" / slot / "local-eval-contract.json"
        if alt.exists():
            slot_contract = alt
        else:
            print(f"missing {slot} local-eval-contract.json under {slot_manager_root}", file=sys.stderr)
            return 2

    lanes = str(args.lanes).strip().lower()
    smr_only = lanes == "smr"
    stamp = _utc_stamp()
    short_task = task_id.replace("-singleplayer", "")
    panel_tag = f"smr{max(1, int(args.smr_count))}" if smr_only else "harbor2-pi2-cursor2-smr2"
    work = (
        gb_root
        / "submissions"
        / "_panel"
        / f"codepolicy-{short_task}-{panel_tag}-{stamp}"
    )
    work.mkdir(parents=True, exist_ok=True)

    timeout_s = _default_timeout(task_id)
    harbor_image = f"gamebench-harbor-code_policy_deo_hillclimb-{task_id}:latest"

    try:
        status_payload = _preflight_slot_for_smr(
            slot=slot,
            synth_dev_root=slot_manager_root,
            slotctl=slotctl,
            timeout_s=float(os.environ.get("GAMEBENCH_SMR_SLOT_PREFLIGHT_TIMEOUT_S", "90")),
        )
    except RuntimeError as exc:
        print(f"SMR slot preflight failed: {exc}", file=sys.stderr)
        print(
            "refusing to start harbor lanes — fix slot-manager / slot2 first",
            file=sys.stderr,
        )
        return 2

    base_env = os.environ.copy()
    # Prefer Homebrew / local Python (>=3.10). System /usr/bin/python3 is 3.9 and
    # breaks craftax gold_python (zip(..., strict=True)).
    preferred_path = "/opt/homebrew/bin:/usr/local/bin:/Users/joshpurtell/.local/bin"
    existing_path = str(base_env.get("PATH") or os.defpath)
    base_env["PATH"] = f"{preferred_path}:{existing_path}"
    base_env["PYTHONUNBUFFERED"] = "1"
    base_env["GAMEBENCH_EVALS_ROOT"] = str(evals_root)
    base_env["GAMEBENCH_ROOT"] = str(gb_root)
    base_env["SYNTH_AI"] = str(synth_ai_root)
    # Ensure managedresearch SMR child inherits PYTHONPATH authority for synth-ai.
    existing_pythonpath = str(base_env.get("PYTHONPATH") or "").strip()
    base_env["PYTHONPATH"] = (
        f"{synth_ai_root}:{existing_pythonpath}"
        if existing_pythonpath
        else str(synth_ai_root)
    )
    base_env["UV_NO_SYNC"] = "1"
    base_env["SYNTH_EVAL_LOCAL_CONTRACT_PATH"] = str(slot_contract)
    base_env["SYNTH_DEV_LOCAL_EVAL_CONTRACT_PATH"] = str(slot_contract)
    base_env["SLOT"] = slot
    base_env["GAMEBENCH_HARBOR_TIMEOUT_SEC"] = str(int(timeout_s))
    base_env["GAMEBENCH_HARBOR_IMAGE"] = harbor_image
    base_env["SMR_AUTO_MANAGE_LOCAL_RUNTIME"] = "0"
    base_env["SYNTH_SLOT_MANAGER_CANONICAL_ROOT"] = str(slot_manager_root)
    base_env["SYNTH_DEV_ROOT"] = str(slot_manager_root)
    base_env["REPORTBENCH_BATCH_LAUNCH_ID"] = (
        base_env.get("REPORTBENCH_BATCH_LAUNCH_ID")
        or f"gamebench-codepolicy-panel-{task_id}"
    )
    base_env["REPORTBENCH_BATCH_LAUNCH_SLOT_ID"] = slot

    print(f"harbor image: {harbor_image}", flush=True)
    print(f"evals: {evals_root}", flush=True)
    print(f"synth-ai: {synth_ai_root}", flush=True)
    print(f"slot-manager / SYNTH_DEV_ROOT: {slot_manager_root}", flush=True)
    print(f"slotctl: {slotctl}", flush=True)
    print(
        f"slot2 preflight: state={status_payload.get('state')} "
        f"services=backend-api+smr-runtime healthy",
        flush=True,
    )
    print(
        f"reportbench batch lock: id={base_env['REPORTBENCH_BATCH_LAUNCH_ID']} "
        f"slot={slot}",
        flush=True,
    )
    def _meta(harness: str, model: str, effort: str, index: int) -> str:
        return f"{harness}/{model}/{effort}#{index}"

    jobs: list[Job] = []

    def _add_harbor(agent: str, model: str, effort: str, idx: int) -> None:
        out = work / f"{agent}-{idx}"
        out.mkdir(parents=True, exist_ok=True)
        env = base_env.copy()
        env["GAMEBENCH_HARBOR_AGENT"] = agent
        env["GAMEBENCH_HARBOR_MODEL"] = model
        env["GAMEBENCH_HARBOR_EFFORT"] = effort
        env["GAMEBENCH_HARBOR_OUT"] = str(out)
        env["GAMEBENCH_HARBOR_WORKSPACE"] = str(out / "workspace")
        env["GAMEBENCH_HARBOR_IMAGE"] = harbor_image
        env["GAMEBENCH_HARBOR_SKIP_BUILD"] = "1"
        meta = _meta(agent, model, effort, idx)
        jobs.append(
            Job(
                key=f"{agent}-{idx}",
                kind="harbor",
                label=meta,
                harness=agent,
                model=model,
                effort=effort,
                index=idx,
                task_id=task_id,
                cmd=[
                    "bash",
                    str(harbor_run),
                    "code-policy",
                    agent,
                    task_id,
                ],
                cwd=gb_root,
                env=env,
                log_path=work / f"{agent}-{idx}.log",
                out_dir=out,
                timeout_s=timeout_s,
            )
        )

    if not smr_only:
        # Prebuild once so parallel lanes can safely SKIP_BUILD for this task only.
        prebuild_log = work / "harbor-prebuild.log"
        print(f"prebuilding harbor image (log={prebuild_log})", flush=True)
        pre_env = base_env.copy()
        pre_env["GAMEBENCH_HARBOR_SKIP_BUILD"] = "0"
        pre_env["GAMEBENCH_HARBOR_AGENT"] = "codex"
        pre_env["GAMEBENCH_HARBOR_OUT"] = str(work / "_prebuild")
        pre_env["GAMEBENCH_HARBOR_WORKSPACE"] = str(work / "_prebuild" / "workspace")
        (work / "_prebuild").mkdir(parents=True, exist_ok=True)
        dockerfile = (
            gb_root
            / "adapters"
            / "harbor"
            / "bundles"
            / "code_policy_deo_hillclimb"
            / "environment"
            / "Dockerfile"
        )
        candidate_subdir = (
            "craftax"
            if task_id.startswith("craftax")
            else "rogue"
            if task_id.startswith("rogue")
            else task_id.removesuffix("-singleplayer").removesuffix("-multiplayer")
        )
        build_cmd = [
            "docker",
            "build",
            "-t",
            harbor_image,
            "-f",
            str(dockerfile),
            "--build-arg",
            f"GAMEBENCH_TASK={task_id}",
            "--build-arg",
            f"CANDIDATE_SUBDIR={candidate_subdir}",
            str(gb_root),
        ]
        with prebuild_log.open("w", encoding="utf-8") as fh:
            build_rc = subprocess.run(
                build_cmd,
                cwd=str(gb_root),
                env=pre_env,
                stdout=fh,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
        if build_rc != 0:
            print(f"harbor prebuild failed rc={build_rc}; see {prebuild_log}", file=sys.stderr)
            return 2
        print(f"harbor prebuild ok: {harbor_image}", flush=True)

        for idx in (1, 2):
            _add_harbor("codex", str(args.harbor_model), str(args.harbor_effort), idx)
        for idx in (1, 2):
            _add_harbor("pi", str(args.pi_model), str(args.pi_effort), idx)
        for idx in (1, 2):
            _add_harbor("cursor", str(args.cursor_model), str(args.cursor_effort), idx)

    for idx in range(1, max(1, int(args.smr_count)) + 1):
        out = work / f"smr-{idx}"
        out.mkdir(parents=True, exist_ok=True)
        meta = _meta("smr", str(args.smr_model), str(args.smr_effort), idx)
        env = base_env.copy()
        jobs.append(
            Job(
                key=f"smr-{idx}",
                kind="smr",
                label=meta,
                harness="smr",
                model=str(args.smr_model),
                effort=str(args.smr_effort),
                index=idx,
                task_id=task_id,
                cmd=[
                    "bash",
                    str(mr_run),
                    "code-policy",
                    "smr",
                    task_id,
                ],
                cwd=gb_root,
                env=env,
                log_path=work / f"smr-{idx}.log",
                out_dir=out,
                timeout_s=timeout_s + 600.0,
            )
        )

    if smr_only:
        lane_desc = f"smr×{max(1, int(args.smr_count))}"
    else:
        lane_desc = (
            f"harbor_codex×2 + harbor_pi×2 + harbor_cursor×2 + "
            f"smr×{max(1, int(args.smr_count))}"
        )
    print(
        f"panel lanes: {lane_desc}  task={task_id} slot={slot}",
        flush=True,
    )
    print(f"panel workdir: {work}", flush=True)
    print(
        "runs: " + " ".join(job.run_metadata for job in jobs) + " (parallel)",
        flush=True,
    )

    panel = Panel(jobs, enabled=True)
    children: list[threading.Thread] = []
    stop = threading.Event()
    harbor_started = False

    def _poll_job(job: Job) -> None:
        if job.kind == "harbor":
            _poll_harbor(job)
        else:
            _poll_smr(job)

    def _start(job: Job) -> None:
        job.set(phase="starting", detail="spawning", started_at=time.time())
        job.proc = subprocess.Popen(
            job.cmd,
            cwd=str(job.cwd),
            env=job.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        job.set(phase="running", detail=f"pid={job.proc.pid}")
        t = threading.Thread(
            target=_supervise, args=(job, lambda: _poll_job(job)), daemon=True
        )
        children.append(t)
        t.start()

    def _abort_all(reason: str) -> None:
        stop.set()
        print(f"ABORT panel: {reason}", file=sys.stderr, flush=True)
        for job in jobs:
            _kill_job_tree(job, reason=reason)

    # SMR first: do not burn Harbor tokens if slot/storage preflight cannot launch.
    print("starting SMR lanes first (harbor waits for PASS: run started)", flush=True)
    for job in jobs:
        if job.kind == "smr":
            _start(job)
            time.sleep(max(0.0, float(args.smr_stagger_seconds)))

    smr_jobs = [job for job in jobs if job.kind == "smr"]
    start_deadline = time.time() + max(30.0, float(args.smr_start_timeout_seconds))
    smr_ready = False
    while time.time() < start_deadline and not stop.is_set():
        started = 0
        hard_fail: str | None = None
        for job in smr_jobs:
            try:
                text = job.log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if _smr_log_indicates_started(text):
                started += 1
                continue
            marker = _smr_log_indicates_hard_start_failure(text)
            if marker:
                hard_fail = f"{job.key}:{marker}"
                break
            if job.exit_code is not None and job.exit_code != 0:
                hard_fail = (
                    f"{job.key}:exit={job.exit_code}:"
                    f"{job.snapshot().get('notes') or 'smr_exited_before_start'}"
                )
                break
        if hard_fail:
            _abort_all(f"smr_start_failed:{hard_fail}")
            break
        if started >= len(smr_jobs):
            smr_ready = True
            break
        try:
            panel.render()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.0)

    if not stop.is_set() and not smr_ready:
        _abort_all(
            "smr_start_timeout:"
            f"waited={args.smr_start_timeout_seconds}s "
            "without PASS: run started on all SMR lanes"
        )

    if not stop.is_set() and smr_ready:
        harbor_jobs = [job for job in jobs if job.kind == "harbor"]
        if harbor_jobs:
            print("SMR started — launching harbor lanes", flush=True)
            for job in harbor_jobs:
                _start(job)
            harbor_started = True
        else:
            print("SMR started — smr-only panel (no harbor lanes)", flush=True)

    def _on_signal(signum: int, _frame: Any) -> None:
        _abort_all(f"signal_{signum}")

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        while not stop.is_set():
            # Late SMR collapse after harbor started — still abort siblings.
            if harbor_started:
                for job in smr_jobs:
                    try:
                        text = job.log_path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        text = ""
                    marker = _smr_log_indicates_hard_start_failure(text)
                    if marker and job.exit_code is not None and job.exit_code != 0:
                        _abort_all(f"smr_collapsed:{job.key}:{marker}")
                        break
            for job in jobs:
                _poll_job_safe(job, lambda j=job: _poll_job(j))
            try:
                panel.render()
            except Exception:  # noqa: BLE001
                pass
            if all(job.exit_code is not None for job in jobs):
                break
            time.sleep(1.0)
    finally:
        for t in children:
            t.join(timeout=2.0)
        for job in jobs:
            _poll_job_safe(job, lambda j=job: _poll_job(j))
        try:
            panel.render()
            panel.finalize()
        except Exception:  # noqa: BLE001
            pass

    summary = {
        "schema_version": "gamebench.panel.codepolicy_harbor2_pi2_cursor2_smr2.v1",
        "task_id": task_id,
        "workdir": str(work),
        "created_at": stamp,
        "slot": slot,
        "slot_manager_root": str(slot_manager_root),
        "smr_ready": smr_ready,
        "harbor_started": harbor_started,
        "jobs": [job.snapshot() for job in jobs],
    }
    (work / "panel-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print()
    _print_table(jobs, task_id=task_id)
    _print_failures(jobs)
    print(f"\nsummary: {work / 'panel-summary.json'}")

    if not smr_ready or any(
        job.snapshot()["ok"] is False or (job.exit_code or 0) != 0 for job in jobs
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
