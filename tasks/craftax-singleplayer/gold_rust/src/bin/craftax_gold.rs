use axum::extract::{Path, Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, post};
use axum::{Json, Router};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use craftax_gamebench_gold::render::{
    encode_gif_via_ffmpeg, encode_png_rgb, frame_sha256, render_rgb_frame_from_world, RenderMode,
    RgbFrame, DEFAULT_RENDER_TILE_SIZE,
};
use craftax_gamebench_gold::{run_entry, CraftaxRustSession};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;
use uuid::Uuid;

#[derive(Clone, Copy)]
struct ReplaySettings {
    enabled: bool,
}

#[derive(Clone)]
struct AppState {
    sessions: Arc<Mutex<HashMap<String, RolloutSession>>>,
    replay: ReplaySettings,
}

/// Matches the `env_family` reported by `/health` and `/info`.
const TASK_FAMILY: &str = "craftax-singleplayer";

const DEFAULT_TASK: &str = r#"{
  "schema": "gamebench.task.craftax.v1",
  "task_id": "manual",
  "scenario_id": "manual",
  "world": {"use_default": "policy_dev_small"},
  "rules": {"base": "symbolic_no_homeostasis"},
  "readouts": {"profile": "symbolic_compact"}
}"#;

struct RolloutSession {
    engine: CraftaxRustSession,
    started_at: Instant,
    checkpoints: HashMap<String, Vec<u8>>,
    frames: HashMap<u64, Vec<u8>>,
    gif_frames: HashMap<u64, RgbFrame>,
}

#[derive(Debug)]
struct ApiError {
    status: StatusCode,
    code: &'static str,
    message: String,
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (
            self.status,
            Json(json!({
                "error": {
                    "code": self.code,
                    "message": self.message
                }
            })),
        )
            .into_response()
    }
}

#[derive(Deserialize)]
struct ScenarioRequest {
    task: Value,
}

/// The pool-facing shape of `POST /rollout`.
///
/// Two callers post here with two different bodies. The native lane sends
/// `{"task": {...}}`. The container pool sends its own rollout request, in
/// which the scenario lives at `env.config.task` and the seed at `env.seed` —
/// the same convention the Python `react` container already reads. Accepting
/// both here means neither the pool nor the engine needs a translation shim.
#[derive(Deserialize)]
struct RolloutEntryRequest {
    #[serde(default)]
    task: Option<Value>,
    #[serde(default)]
    env: Option<Value>,
    #[serde(default)]
    seed: Option<i64>,
}

impl RolloutEntryRequest {
    fn resolve_entry(&self) -> Value {
        let env_config = self.env.as_ref().and_then(|env| env.get("config"));
        let mut entry = self
            .task
            .clone()
            .or_else(|| env_config.and_then(|config| config.get("task").cloned()))
            .unwrap_or_else(default_task);
        let seed = self
            .seed
            .or_else(|| {
                self.env
                    .as_ref()
                    .and_then(|env| env.get("seed"))
                    .and_then(Value::as_i64)
            })
            .or_else(|| {
                env_config
                    .and_then(|config| config.get("seed"))
                    .and_then(Value::as_i64)
            });
        // `reset_from_entry` takes its seed override from `entry.seed`. Only
        // fill it when the entry does not already carry one, so an explicit
        // scenario always wins over an ambient pool seed.
        if let (Some(seed), Some(object)) = (seed, entry.as_object_mut()) {
            object.entry("seed").or_insert(json!(seed));
        }
        entry
    }
}

#[derive(Deserialize)]
struct RolloutRequest {
    task: Option<Value>,
    seed: Option<i64>,
}

#[derive(Deserialize)]
struct StepRequest {
    action: Value,
}

#[derive(Deserialize)]
struct RestoreRequest {
    blob: String,
}

#[derive(Deserialize)]
struct SimulateRequest {
    blob: String,
    sequences: Vec<Vec<String>>,
}

#[derive(Deserialize)]
struct ReplayGifQuery {
    through_step: Option<u64>,
}

#[tokio::main]
async fn main() {
    let mut host = "127.0.0.1".to_string();
    let mut port = 8098_u16;
    let mut replay_enabled = replay_enabled_from_env();
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--host" => host = args.next().unwrap_or(host),
            "--port" => {
                port = args
                    .next()
                    .and_then(|value| value.parse().ok())
                    .unwrap_or(port)
            }
            "--replay" => replay_enabled = true,
            "--no-replay" => replay_enabled = false,
            _ => {}
        }
    }

    let state = AppState {
        sessions: Arc::new(Mutex::new(HashMap::new())),
        replay: ReplaySettings {
            enabled: replay_enabled,
        },
    };
    let app = Router::new()
        .route("/health", get(health))
        .route("/info", get(info))
        .route("/metadata", get(metadata))
        .route("/task_info", get(task_info))
        .route("/run_scenario", post(run_scenario_route))
        .route("/rollout", post(rollout_entry_route))
        .route("/rollouts", post(create_rollout))
        .route("/reset", post(create_rollout))
        .route("/rollouts/:rollout_id/step", post(step))
        .route("/rollouts/:rollout_id", delete(delete_rollout))
        .route("/rollouts/:rollout_id/readout", get(readout))
        .route("/rollouts/:rollout_id/state", get(readout))
        .route("/rollouts/:rollout_id/event_log", get(event_log))
        .route("/rollouts/:rollout_id/events", get(event_log))
        .route("/rollouts/:rollout_id/checkpoint", post(checkpoint))
        .route("/rollouts/:rollout_id/checkpoints", post(checkpoint))
        .route("/rollouts/:rollout_id/restore", post(restore))
        .route("/rollouts/:rollout_id/simulate", post(simulate))
        .route("/rollouts/:rollout_id/render.svg", get(render_svg))
        .route("/rollouts/:rollout_id/render.png", get(render_png_route))
        .route(
            "/rollouts/:rollout_id/frames/manifest",
            get(frame_manifest_route),
        )
        .route("/rollouts/:rollout_id/frames/:step", get(frame_png_route))
        .route("/rollouts/:rollout_id/replay.gif", get(replay_gif_route))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind(format!("{host}:{port}"))
        .await
        .expect("bind Craftax Rust gold service");
    axum::serve(listener, app)
        .await
        .expect("serve Craftax Rust gold service");
}

async fn health(State(app): State<AppState>) -> Json<Value> {
    Json(json!({
        "ok": true,
        "lane": "rust",
        "env_family": "craftax-singleplayer",
        "sessions": app.sessions.lock().unwrap().len(),
        "replay_enabled": app.replay.enabled,
    }))
}

async fn info(State(app): State<AppState>) -> Json<Value> {
    let capabilities = vec![
        "rollout",
        "checkpoint",
        "nev_log",
        "symbolic_readout",
        "render_svg",
        "render_png",
        "frames_manifest",
        "frame_png",
        "replay_gif",
        "simulate_from_checkpoint",
    ];
    Json(json!({
        "env_family": "craftax-singleplayer",
        "lane": "rust",
        "capabilities": capabilities,
        "replay_enabled": app.replay.enabled,
    }))
}

/// Container-pool probe. The pool fetches `/metadata` once per task
/// materialization to learn what the runtime is and what it can do; it is the
/// companion to `/info`, which reports live service state.
async fn metadata(State(app): State<AppState>) -> Json<Value> {
    Json(json!({
        "status": "ok",
        "runtime_id": "gamebench.craftax_singleplayer.gold_rust",
        "name": "GameBench Craftax single-player Rust gold service",
        "task_family": TASK_FAMILY,
        "lane": "rust",
        "schema": "gamebench.task.craftax.v1",
        // The engine is a sealed binary: no model, no egress, and no
        // synth-containers wheel. Trace emission is the caller's job.
        "emits_trace_v5": false,
        "capabilities": {
            "async_rollout": false,
            "checkpoint_resume": true,
            "scheduled_checkpoints": false,
            "replay": app.replay.enabled,
        },
        "features": ["checkpoint_resume", "one_shot_rollout", "stepwise_rollout"],
    }))
}

#[derive(Deserialize)]
struct TaskInfoQuery {
    seed: Option<i64>,
}

/// Container-pool probe. The pool issues one request per seed and expects a
/// single object back each time, so this deliberately does not accept a seed
/// list — `fetch_service_task_info` fans out on the caller's side.
async fn task_info(Query(query): Query<TaskInfoQuery>) -> Json<Value> {
    let task = default_task();
    let seed = query.seed.unwrap_or(0);
    Json(json!({
        "seed": seed,
        "task_family": TASK_FAMILY,
        "task_id": task.get("task_id").cloned().unwrap_or(Value::Null),
        "scenario_id": task.get("scenario_id").cloned().unwrap_or(Value::Null),
        "schema": task.get("schema").cloned().unwrap_or(Value::Null),
        "reward_mode": "progress",
        "lane": "rust",
    }))
}

/// The native scenario lane. Deliberately strict: a missing `task` is an error
/// here, not a silent default, because fixture parity runs post this route.
async fn run_scenario_route(Json(body): Json<ScenarioRequest>) -> Result<Json<Value>, ApiError> {
    Ok(Json(run_entry(&body.task).map_err(bad_request)?))
}

/// The container-pool lane. Tolerant of the pool's rollout-request shape.
async fn rollout_entry_route(
    Json(body): Json<RolloutEntryRequest>,
) -> Result<Json<Value>, ApiError> {
    Ok(Json(run_entry(&body.resolve_entry()).map_err(bad_request)?))
}

async fn create_rollout(
    State(app): State<AppState>,
    Json(body): Json<RolloutRequest>,
) -> Result<Json<Value>, ApiError> {
    let task = body.task.unwrap_or_else(default_task);
    let engine = CraftaxRustSession::reset_from_task(&task, body.seed).map_err(bad_request)?;
    let rollout_id = Uuid::new_v4().to_string();
    let mut session = RolloutSession {
        engine,
        started_at: Instant::now(),
        checkpoints: HashMap::new(),
        frames: HashMap::new(),
        gif_frames: HashMap::new(),
    };
    capture_frame_if_enabled(&mut session, app.replay, false);
    let payload = rollout_payload(&rollout_id, &session);
    app.sessions.lock().unwrap().insert(rollout_id, session);
    Ok(Json(payload))
}

async fn step(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<StepRequest>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    let session = guard.get_mut(&rollout_id).ok_or_else(rollout_not_found)?;
    if !session.engine.is_done() {
        session.engine.step(&body.action).map_err(bad_request)?;
        capture_frame_if_enabled(session, app.replay, false);
    }
    Ok(Json(rollout_payload(&rollout_id, session)))
}

async fn delete_rollout(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    if guard.remove(&rollout_id).is_none() {
        return Err(rollout_not_found());
    }
    Ok(Json(json!({"rollout_id": rollout_id, "deleted": true})))
}

async fn readout(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    Ok(Json(session.engine.readout()))
}

async fn event_log(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "events": session.engine.events,
        "legacy": session.engine.legacy_strings(),
        "nev_cursor": session.engine.events.len()
    })))
}

async fn checkpoint(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    let session = guard.get_mut(&rollout_id).ok_or_else(rollout_not_found)?;
    let blob = session.engine.checkpoint_bytes().map_err(bad_request)?;
    let checkpoint_id = Uuid::new_v4().to_string();
    session
        .checkpoints
        .insert(checkpoint_id.clone(), blob.clone());
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "checkpoint_id": checkpoint_id,
        "blob": BASE64.encode(&blob),
        "bytes": blob.len(),
        "step_index": session.engine.private.get("step_index").cloned().unwrap_or(Value::Null),
        "nev_cursor": session.engine.events.len(),
        "config_hash": session.engine.resolved.config_hash
    })))
}

async fn restore(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<RestoreRequest>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    let session = guard.get_mut(&rollout_id).ok_or_else(rollout_not_found)?;
    let blob = BASE64.decode(body.blob).map_err(bad_request)?;
    let restored = session
        .engine
        .restore_checkpoint_bytes(&blob)
        .map_err(bad_request)?;
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "restore_report": {
            "bytes": blob.len(),
            "wall_ms": 0.0,
            "nev_events_restored": restored
        },
        "state": rollout_payload(&rollout_id, session)
    })))
}

async fn simulate(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<SimulateRequest>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    let root = BASE64.decode(body.blob).map_err(bad_request)?;
    let mut results = Vec::new();
    for (index, sequence) in body.sequences.iter().enumerate() {
        let mut sim = session.engine.clone();
        sim.restore_checkpoint_bytes(&root).map_err(bad_request)?;
        let root_invalid_action_count = sim
            .private
            .get("invalid_action_count")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let mut reward_trace = Vec::new();
        for action in sequence {
            if sim.is_done() {
                break;
            }
            sim.step(&Value::String(action.clone()))
                .map_err(bad_request)?;
            reward_trace.push(
                sim.private
                    .get("reward_last")
                    .cloned()
                    .unwrap_or(json!(0.0)),
            );
        }
        results.push(json!({
            "index": index,
            "actions": sequence,
            "reward": sim.private.get("total_reward").cloned().unwrap_or(json!(0.0)),
            "reward_trace": reward_trace,
            "invalid_action_delta": sim
                .private
                .get("invalid_action_count")
                .and_then(Value::as_i64)
                .unwrap_or(0)
                - root_invalid_action_count,
            "achievements": sim.private.get("achievements").cloned().unwrap_or_else(|| json!([])),
            "terminated": sim.private.get("terminated").and_then(Value::as_bool).unwrap_or(false),
            "truncated": sim.private.get("truncated").and_then(Value::as_bool).unwrap_or(false),
            "steps": sim.private.get("step_index").cloned().unwrap_or(json!(0)),
            "readout": sim.readout()
        }));
    }
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "root_nev_cursor": session.engine.events.len(),
        "results": results
    })))
}

async fn render_svg(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Response, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    let ascii = session
        .engine
        .readout()
        .get("ascii")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    Ok((
        [(header::CONTENT_TYPE, "image/svg+xml")],
        svg_for_ascii(&ascii),
    )
        .into_response())
}

async fn render_png_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Response, ApiError> {
    let png = {
        let guard = app.sessions.lock().unwrap();
        let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
        let frame = render_rgb_frame_from_world(
            &session.engine.world,
            DEFAULT_RENDER_TILE_SIZE,
            RenderMode::Auto,
        );
        encode_png_rgb(frame.0, frame.1, &frame.2)
    };
    Ok(([(header::CONTENT_TYPE, "image/png")], png).into_response())
}

async fn frame_manifest_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    Ok(Json(frame_manifest(&rollout_id, session)))
}

async fn frame_png_route(
    State(app): State<AppState>,
    Path((rollout_id, step_raw)): Path<(String, String)>,
) -> Result<Response, ApiError> {
    let step = parse_frame_step(&step_raw).ok_or_else(|| ApiError {
        status: StatusCode::BAD_REQUEST,
        code: "frame_step_invalid",
        message: "frame step must be a non-negative integer".into(),
    })?;
    let png = {
        let mut guard = app.sessions.lock().unwrap();
        let session = guard.get_mut(&rollout_id).ok_or_else(rollout_not_found)?;
        let current_step = session_step_index(session);
        if step == current_step && !session.frames.contains_key(&step) {
            store_frame(session, step);
        }
        session.frames.get(&step).cloned()
    };
    let Some(png) = png else {
        return Err(ApiError {
            status: StatusCode::NOT_FOUND,
            code: "frame_not_found",
            message: "frame not found".into(),
        });
    };
    Ok(([(header::CONTENT_TYPE, "image/png")], png).into_response())
}

async fn replay_gif_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Query(query): Query<ReplayGifQuery>,
) -> Result<Response, ApiError> {
    let gif = {
        let mut guard = app.sessions.lock().unwrap();
        let session = guard.get_mut(&rollout_id).ok_or_else(rollout_not_found)?;
        if session.gif_frames.is_empty() {
            store_frame(session, session_step_index(session));
        }
        let mut steps: Vec<u64> = session
            .gif_frames
            .keys()
            .copied()
            .filter(|step| query.through_step.is_none_or(|limit| *step <= limit))
            .collect();
        steps.sort_unstable();
        if steps.is_empty() {
            store_frame(session, session_step_index(session));
            steps.push(session_step_index(session));
        }
        let frames: Vec<RgbFrame> = steps
            .iter()
            .filter_map(|step| session.gif_frames.get(step).cloned())
            .collect();
        encode_gif_via_ffmpeg(&frames, 10).map_err(|err| ApiError {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            code: "gif_encode_failed",
            message: err,
        })?
    };
    Ok(([(header::CONTENT_TYPE, "image/gif")], gif).into_response())
}

fn replay_enabled_from_env() -> bool {
    matches!(
        std::env::var("GAMEBENCH_CRAFTAX_REPLAY_ENABLED")
            .unwrap_or_default()
            .as_str(),
        "1" | "true" | "TRUE" | "yes" | "YES"
    )
}

fn parse_frame_step(raw: &str) -> Option<u64> {
    raw.strip_suffix(".png")
        .or(Some(raw))
        .and_then(|value| value.parse().ok())
}

fn session_step_index(session: &RolloutSession) -> u64 {
    session
        .engine
        .private
        .get("step_index")
        .and_then(Value::as_u64)
        .unwrap_or(0)
}

fn rollout_capture_enabled(session: &RolloutSession) -> bool {
    let readouts = &session.engine.resolved.readouts;
    let visual = readouts
        .get("visual")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let stream = readouts.get("stream").and_then(Value::as_object);
    let stream_enabled = stream
        .and_then(|stream| stream.get("enabled"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let persist_frames = stream
        .and_then(|stream| stream.get("persist_frames"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    visual || stream_enabled || persist_frames
}

fn capture_frame_if_enabled(session: &mut RolloutSession, replay: ReplaySettings, force: bool) {
    if !replay.enabled {
        return;
    }
    if !force && !rollout_capture_enabled(session) {
        return;
    }
    store_frame(session, session_step_index(session));
}

fn store_frame(session: &mut RolloutSession, step: u64) {
    let frame = render_rgb_frame_from_world(
        &session.engine.world,
        DEFAULT_RENDER_TILE_SIZE,
        RenderMode::Auto,
    );
    let png = encode_png_rgb(frame.0, frame.1, &frame.2);
    session.frames.insert(step, png);
    session.gif_frames.insert(step, frame);
}

fn frame_manifest(rollout_id: &str, session: &RolloutSession) -> Value {
    let mut frames = Vec::new();
    for step in session.frames.keys().copied().collect::<Vec<_>>() {
        let blob = session.frames.get(&step).expect("frame step");
        frames.push(json!({
            "step": step,
            "bytes": blob.len(),
            "sha256": frame_sha256(blob),
            "url": format!("/rollouts/{rollout_id}/frames/{step}.png"),
        }));
    }
    frames.sort_by_key(|entry| entry.get("step").and_then(Value::as_u64).unwrap_or(0));
    json!({
        "rollout_id": rollout_id,
        "frame_count": frames.len(),
        "latest_step": frames.last().and_then(|entry| entry.get("step")).cloned(),
        "frames": frames,
    })
}

fn rollout_payload(rollout_id: &str, session: &RolloutSession) -> Value {
    json!({
        "rollout_id": rollout_id,
        "readout": session.engine.readout(),
        "reward": session.engine.private.get("total_reward").cloned().unwrap_or(json!(0.0)),
        "terminated": session.engine.private.get("terminated").and_then(Value::as_bool).unwrap_or(false),
        "truncated": session.engine.private.get("truncated").and_then(Value::as_bool).unwrap_or(false),
        "nev_cursor": session.engine.events.len(),
        "progress": {
            "env_steps": session.engine.private.get("step_index").cloned().unwrap_or(json!(0)),
            "wall_clock_seconds": session.started_at.elapsed().as_secs_f64()
        }
    })
}

fn default_task() -> Value {
    serde_json::from_str(DEFAULT_TASK).expect("default task JSON is valid")
}

fn bad_request(error: impl std::fmt::Display) -> ApiError {
    ApiError {
        status: StatusCode::BAD_REQUEST,
        code: "bad_request",
        message: error.to_string(),
    }
}

fn rollout_not_found() -> ApiError {
    ApiError {
        status: StatusCode::NOT_FOUND,
        code: "rollout_not_found",
        message: "rollout not found".into(),
    }
}

fn svg_for_ascii(ascii: &str) -> String {
    let escaped = ascii
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;");
    let lines = ascii.lines().count().max(1);
    let cols = ascii.lines().map(str::len).max().unwrap_or(1).max(1);
    format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}"><rect width="100%" height="100%" fill="#111"/><text x="12" y="20" fill="#e8e8e8" font-family="monospace" font-size="14"><tspan x="12" dy="0">{}</tspan></text></svg>"##,
        cols * 9 + 24,
        lines * 18 + 24,
        escaped.replace('\n', r#"</tspan><tspan x="12" dy="18">"#)
    )
}
