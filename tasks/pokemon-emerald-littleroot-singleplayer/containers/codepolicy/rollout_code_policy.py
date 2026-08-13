"""Roll out Emerald code policies against the Rust gold HTTP service."""

from __future__ import annotations

import atexit
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


TASK_ROOT = Path(__file__).resolve().parents[2]
VALID_ACTIONS = ("up", "down", "left", "right", "a", "b", "start", "select", "noop")
PolicyFn = Callable[..., dict[str, Any]]
_POLICY_CACHE: dict[str, PolicyFn] = {}
_SERVICE_PROC: subprocess.Popen[str] | None = None
_SERVICE_PORT: int | None = None


def shutdown_service() -> None:
    """Stop the helper service that this process started, if it is still live."""
    global _SERVICE_PROC, _SERVICE_PORT
    proc = _SERVICE_PROC
    _SERVICE_PROC = None
    _SERVICE_PORT = None
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


atexit.register(shutdown_service)


def task_root() -> Path:
    return TASK_ROOT


def _scenario_bin() -> Path:
    # Prefer cargo metadata target (sandbox/workspace), then local target/.
    try:
        meta = subprocess.check_output(
            [
                "cargo",
                "metadata",
                "--manifest-path",
                str(TASK_ROOT / "gold_rust" / "Cargo.toml"),
                "--format-version",
                "1",
                "--no-deps",
            ],
            text=True,
        )
        target = Path(json.loads(meta)["target_directory"])
        candidate = target / "release" / "emerald_gold"
        if candidate.is_file():
            return candidate
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        pass
    local = TASK_ROOT / "gold_rust" / "target" / "release" / "emerald_gold"
    if local.is_file():
        return local
    raise FileNotFoundError(
        "emerald_gold release binary missing; build with "
        "`cargo build --release --manifest-path gold_rust/Cargo.toml --bin emerald_gold`"
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def ensure_service(*, port: int | None = None, base_url: str | None = None) -> str:
    """Return a live base URL, starting emerald_gold if needed."""
    global _SERVICE_PROC, _SERVICE_PORT
    if base_url:
        _wait_health(base_url, timeout_s=2.0)
        return base_url.rstrip("/")
    if _SERVICE_PROC is not None and _SERVICE_PORT is not None and _SERVICE_PROC.poll() is None:
        url = f"http://127.0.0.1:{_SERVICE_PORT}"
        try:
            _wait_health(url, timeout_s=0.5)
            return url
        except TimeoutError:
            pass
    chosen = int(port or os.environ.get("GAMEBENCH_POKEMON_EMERALD_PORT") or _free_port())
    binary = _scenario_bin()
    _SERVICE_PROC = subprocess.Popen(
        [str(binary), "--port", str(chosen)],
        cwd=str(TASK_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    _SERVICE_PORT = chosen
    url = f"http://127.0.0.1:{chosen}"
    try:
        _wait_health(url, timeout_s=30.0)
    except Exception:
        proc = _SERVICE_PROC
        _SERVICE_PROC = None
        if proc is not None:
            proc.kill()
            err = (proc.stderr.read() if proc.stderr else "")[-1000:]
            raise RuntimeError(f"failed to start emerald_gold on {chosen}: {err}") from None
        raise
    return url


def _wait_health(base_url: str, *, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    url = base_url.rstrip("/") + "/health"
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.05)
    raise TimeoutError(f"emerald gold not healthy at {url}: {last}")


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def load_policy_module(policy_path: Path, *, entry: str = "choose_actions") -> PolicyFn:
    resolved = policy_path.expanduser().resolve()
    key = f"{resolved}::{entry}"
    if key in _POLICY_CACHE:
        return _POLICY_CACHE[key]
    if not resolved.is_file():
        raise ValueError(f"policy file not found: {resolved}")
    name = f"emerald_codepolicy_{resolved.stem}_{abs(hash(str(resolved))) % 10_000_000}"
    spec = importlib.util.spec_from_file_location(name, resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fn = getattr(module, entry, None)
    if not callable(fn):
        raise ValueError(f"policy {resolved} missing callable {entry}")
    _POLICY_CACHE[key] = fn
    return fn


def compile_check_policy(policy_path: Path, *, base_url: str | None = None) -> dict[str, Any]:
    fn = load_policy_module(policy_path)
    url = ensure_service(base_url=base_url)
    created = _http_json("POST", f"{url}/rollouts", {"checkpoint": "bedroom_idle"})
    readout = created.get("readout") or _http_json("GET", f"{url}/rollouts/{created['rollout_id']}/readout")
    result = fn(
        observation_text=_observation_text(readout),
        session={"rollout_id": created["rollout_id"], "ply": 0},
        valid_actions=list(VALID_ACTIONS),
        engine=None,
        seed=0,
        ply=0,
        readout=readout,
    )
    actions = _normalize_actions(result)
    return {"policy_path": str(policy_path.resolve()), "sample_actions": actions}


def _observation_text(readout: dict[str, Any]) -> str:
    world = readout.get("world") or {}
    player = world.get("player") or {}
    bits = [
        f"checkpoint={readout.get('checkpoint')}",
        f"phase={world.get('phase')}",
        f"map={world.get('map')}",
        f"player=({player.get('x')},{player.get('y')})",
        f"facing={world.get('facing')}",
        f"frame={readout.get('frame_index')}",
    ]
    if world.get("dialogue"):
        bits.append("dialogue=1")
    if world.get("clock_prompt_active"):
        bits.append("clock_prompt=1")
    if world.get("clock_minutes") is not None:
        bits.append(f"clock_minutes={world.get('clock_minutes')}")
    if world.get("running_shoes_stage"):
        bits.append(f"shoes_stage={world.get('running_shoes_stage')}")
    if world.get("running_shoes_trigger") is not None:
        bits.append(f"shoes_trigger={world.get('running_shoes_trigger')}")
    if world.get("starter"):
        bits.append(f"starter={world.get('starter')}")
    return " ".join(bits)


def _normalize_actions(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict) or "actions" not in result:
        raise ValueError("choose_actions must return {'actions': [...]}")
    raw = result["actions"]
    if not isinstance(raw, list) or not raw:
        raise ValueError("actions must be a non-empty list")
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            action = item.strip().lower()
            frames = 1
        elif isinstance(item, dict):
            action = str(item.get("action") or item.get("kind") or "").strip().lower()
            frames = int(item.get("frames", 1))
        else:
            raise ValueError(f"unsupported action item: {item!r}")
        if action not in VALID_ACTIONS:
            raise ValueError(f"invalid action {action!r}; expected one of {VALID_ACTIONS}")
        if frames < 0:
            raise ValueError("frames must be >= 0")
        out.append({"action": action, "frames": frames})
    return out


def _manhattan(a: dict[str, Any], b: dict[str, Any]) -> int:
    return abs(int(a.get("x", 0)) - int(b.get("x", 0))) + abs(int(a.get("y", 0)) - int(b.get("y", 0)))


def _score_episode(
    *,
    start_readout: dict[str, Any],
    final_readout: dict[str, Any],
    scenario: dict[str, Any],
    invalid_action_count: int,
) -> dict[str, Any]:
    start_world = start_readout.get("world") or {}
    final_world = final_readout.get("world") or {}
    start_player = start_world.get("player") or {}
    final_player = final_world.get("player") or {}
    moved = _manhattan(start_player, final_player)
    phase_changed = start_world.get("phase") != final_world.get("phase")
    map_changed = start_world.get("map") != final_world.get("map")
    target = scenario.get("target_player") or {}
    reached_target = False
    if target:
        reached_target = int(final_player.get("x", -1)) == int(target.get("x", -2)) and int(
            final_player.get("y", -1)
        ) == int(target.get("y", -2))
    clock_prompt = bool(final_world.get("clock_prompt_active") or final_world.get("clock_editing"))
    clock_minutes_set = final_world.get("clock_minutes") is not None
    require_phase = scenario.get("require_phase")
    require_map = scenario.get("require_map")
    require_battle = dict(scenario.get("require_battle") or {})
    require_world = dict(scenario.get("require_world") or {})
    min_world = dict(scenario.get("min_world") or {})
    phase_matched = require_phase is None or final_world.get("phase") == require_phase
    map_matched = require_map is None or final_world.get("map") == require_map
    battle = final_world.get("battle") if isinstance(final_world.get("battle"), dict) else {}
    battle_ok = True
    battle_details: dict[str, Any] = {}
    for key, expected in require_battle.items():
        actual = battle.get(key)
        ok = actual == expected
        battle_details[key] = {"actual": actual, "expected": expected, "ok": ok}
        battle_ok = battle_ok and ok
    world_ok = True
    world_details: dict[str, Any] = {}
    for key, expected in require_world.items():
        actual = final_world.get(key)
        ok = actual == expected
        world_details[key] = {"actual": actual, "expected": expected, "ok": ok}
        world_ok = world_ok and ok
    min_world_ok = True
    min_world_details: dict[str, Any] = {}
    for key, minimum in min_world.items():
        actual = final_world.get(key)
        try:
            ok = float(actual) >= float(minimum)
        except (TypeError, ValueError):
            ok = False
        min_world_details[key] = {"actual": actual, "minimum": minimum, "ok": ok}
        min_world_ok = min_world_ok and ok
    min_move = int(scenario.get("min_manhattan_from_start", 1))
    require_phase_change = bool(scenario.get("require_phase_change", False))
    require_map_change = bool(scenario.get("require_map_change", False))
    require_target = bool(target) or bool(scenario.get("require_target", False))
    require_clock_prompt = bool(scenario.get("require_clock_prompt", False))

    reward = 0.0
    if moved >= min_move:
        reward += 1.0
    if phase_changed:
        reward += 1.0
    if map_changed:
        reward += 1.0
    if reached_target:
        reward += 2.0
    if clock_prompt:
        reward += 0.5
    if clock_minutes_set:
        reward += 1.5
    if require_phase is not None and phase_matched:
        reward += 2.0
    if require_map is not None and map_matched:
        reward += 2.0
    if min_world and min_world_ok:
        reward += 2.0
    if require_battle and battle_ok:
        reward += 2.0
    if require_world and world_ok:
        reward += 2.0
    if invalid_action_count:
        reward -= 0.25 * invalid_action_count

    success = moved >= min_move
    if require_phase_change:
        success = success and phase_changed
    if require_map_change:
        success = success and map_changed
    if require_target:
        success = success and reached_target
    if require_clock_prompt:
        success = success and clock_prompt
    if require_phase is not None:
        success = success and phase_matched
    if require_map is not None:
        success = success and map_matched
    if min_world:
        success = success and min_world_ok
    if require_battle:
        success = success and battle_ok
    if require_world:
        success = success and world_ok

    return {
        "outcome": "success" if success else "failed",
        "outcome_reward": 1.0 if success else 0.0,
        "total_reward": round(reward, 4),
        "details": {
            "moved_manhattan": moved,
            "phase_changed": phase_changed,
            "map_changed": map_changed,
            "reached_target": reached_target,
            "clock_prompt": clock_prompt,
            "clock_minutes_set": clock_minutes_set,
            "phase_matched": phase_matched,
            "map_matched": map_matched,
            "min_world": min_world_details,
            "require_world": world_details,
            "battle": battle_details,
            "start_phase": start_world.get("phase"),
            "final_phase": final_world.get("phase"),
            "start_map": start_world.get("map"),
            "final_map": final_world.get("map"),
            "start_player": start_player,
            "final_player": final_player,
            "invalid_action_count": invalid_action_count,
            "scenario_id": scenario.get("scenario_id"),
            "checkpoint": scenario.get("checkpoint"),
            "seed": scenario.get("seed"),
        },
    }


def rollout_code_policy(
    *,
    policy_path: Path,
    scenario: dict[str, Any],
    max_steps: int = 16,
    include_trace: bool = False,
    candidate_fn: PolicyFn | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    url = ensure_service(base_url=base_url)
    checkpoint = str(scenario.get("checkpoint") or "bedroom_idle")
    seed = int(scenario.get("seed", 0))
    created = _http_json("POST", f"{url}/rollouts", {"checkpoint": checkpoint})
    rollout_id = created["rollout_id"]
    start_readout = created.get("readout") or _http_json("GET", f"{url}/rollouts/{rollout_id}/readout")
    candidate = candidate_fn or load_policy_module(policy_path)
    invalid = 0
    turns: list[dict[str, Any]] = []
    readout = start_readout
    # Persist policy memory across plies (stuck recovery, open-loop cursors, etc.).
    session: dict[str, Any] = {"rollout_id": rollout_id, "seed": seed}
    for ply in range(max_steps):
        session["ply"] = ply
        try:
            decision = candidate(
                observation_text=_observation_text(readout),
                session=session,
                valid_actions=list(VALID_ACTIONS),
                engine=None,
                seed=seed,
                ply=ply,
                readout=readout,
            )
            actions = _normalize_actions(decision)
        except Exception as exc:  # noqa: BLE001
            invalid += 1
            actions = [{"action": "noop", "frames": 1}]
            decision = {"actions": actions, "policy_error": f"{type(exc).__name__}: {exc}"}
        stop = False
        for step in actions:
            stepped = _http_json("POST", f"{url}/rollouts/{rollout_id}/step", step)
            # emerald_gold returns the readout object directly from /step.
            if isinstance(stepped, dict) and "world" in stepped:
                readout = stepped
            else:
                readout = stepped.get("readout") or _http_json(
                    "GET", f"{url}/rollouts/{rollout_id}/readout"
                )
            # Score after each engine step so chunked tapes don't overshoot goals.
            if scenario.get("stop_on_success", True):
                probe = _score_episode(
                    start_readout=start_readout,
                    final_readout=readout,
                    scenario=scenario,
                    invalid_action_count=invalid,
                )
                if probe["outcome"] == "success":
                    stop = True
                    break
        if include_trace:
            turns.append({"ply": ply, "decision": decision, "actions": actions, "readout": readout})
        if stop:
            break

    reward_info = _score_episode(
        start_readout=start_readout,
        final_readout=readout,
        scenario=scenario,
        invalid_action_count=invalid,
    )
    return {
        "schema": "gamebench.pokemon_emerald.policy_episode.v1",
        "rollout_id": rollout_id,
        "scenario_id": scenario.get("scenario_id"),
        "checkpoint": checkpoint,
        "seed": seed,
        "success_status": reward_info["outcome"],
        "reward_info": reward_info,
        "final_readout": {
            "frame_index": readout.get("frame_index"),
            "world": {
                "phase": (readout.get("world") or {}).get("phase"),
                "map": (readout.get("world") or {}).get("map"),
                "player": (readout.get("world") or {}).get("player"),
                "facing": (readout.get("world") or {}).get("facing"),
            },
        },
        "turns": turns if include_trace else None,
    }
