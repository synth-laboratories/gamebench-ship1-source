use axum::extract::{Path, Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, post};
use axum::{Json, Router};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use crafter_gamebench_gold::render::{
    encode_gif_via_ffmpeg, encode_png_rgb, frame_sha256, render_rgb_frame_from_readout,
    RenderMode, RgbFrame, DEFAULT_RENDER_TILE_SIZE,
};
use crafter_gamebench_gold::CrafterRustSession;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{Arc, Mutex};
use std::time::Instant;
use uuid::Uuid;

type Sessions = Arc<Mutex<HashMap<String, RolloutSession>>>;

#[derive(Clone, Copy)]
struct ReplaySettings {
    enabled: bool,
}

#[derive(Clone)]
struct AppState {
    sessions: Sessions,
    replay: ReplaySettings,
}

#[derive(Deserialize)]
struct ReplayGifQuery {
    through_step: Option<u64>,
}

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

struct RolloutSession {
    engine: CrafterRustSession,
    limits: Value,
    agent_progress: Value,
    started_at: Instant,
    checkpoints: HashMap<String, Vec<u8>>,
    checkpoint_metadata: HashMap<String, Value>,
    frames: HashMap<u64, Vec<u8>>,
    gif_frames: HashMap<u64, RgbFrame>,
}

#[derive(Deserialize)]
struct RolloutRequest {
    task: Option<Value>,
    seed: Option<u64>,
    limits: Option<Value>,
}

#[derive(Deserialize, Default)]
struct ProgressUpdateRequest {
    llm_calls_completed: Option<u64>,
    llm_call_in_flight: Option<bool>,
    prompt_tokens: Option<u64>,
    completion_tokens: Option<u64>,
    total_tokens: Option<u64>,
    wall_clock_seconds: Option<f64>,
}

#[derive(Deserialize)]
struct BatchRolloutRequest {
    items: Option<Vec<RolloutRequest>>,
    tasks: Option<Vec<Value>>,
    seeds: Option<Vec<Option<u64>>>,
}

#[derive(Deserialize)]
struct ScenarioRequest {
    task: Value,
}

#[derive(Deserialize)]
struct StepRequest {
    action: String,
}

#[derive(Deserialize)]
struct RestoreRequest {
    blob: String,
}

#[derive(Deserialize)]
struct CheckpointExport {
    checkpoint_id: String,
    blob: String,
}

#[derive(Deserialize)]
struct SimulateRequest {
    blob: String,
    sequences: Vec<Vec<String>>,
}

#[tokio::main]
async fn main() {
    let mut host = "127.0.0.1".to_string();
    let mut port = 8095_u16;
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
        .route("/pool", get(pool))
        .route("/pool/evict_idle", post(evict_idle))
        .route("/run_scenario", post(run_scenario_route))
        .route("/rollout", post(run_scenario_route))
        .route("/rollouts", post(create_rollout))
        .route("/rollouts/batch", post(create_rollout_batch))
        .route("/reset", post(create_rollout))
        .route("/step", post(step_legacy))
        .route("/rollouts/:rollout_id/step", post(step))
        .route("/rollouts/:rollout_id/state", get(state_route))
        .route("/rollouts/:rollout_id/progress", post(update_progress))
        .route("/rollouts/:rollout_id/readout", get(readout))
        .route("/rollouts/:rollout_id/events", get(events))
        .route("/rollouts/:rollout_id/event_log", get(events))
        .route(
            "/rollouts/:rollout_id/checkpoint",
            post(checkpoint_with_blob),
        )
        .route(
            "/rollouts/:rollout_id/checkpoints",
            post(checkpoint_without_blob).get(list_checkpoints),
        )
        .route("/checkpoint/:rollout_id", post(checkpoint_with_blob))
        .route("/checkpoints/:checkpoint_id/export", get(export_checkpoint))
        .route("/checkpoints/import", post(import_checkpoint))
        .route("/restore", post(restore_new))
        .route("/rollouts/:rollout_id/restore", post(restore_in_place))
        .route("/rollouts/:rollout_id/simulate", post(simulate))
        .route("/rollouts/:rollout_id/render.svg", get(render_svg_route))
        .route("/rollouts/:rollout_id/render.png", get(render_png_route))
        .route("/rollouts/:rollout_id/frames/manifest", get(frame_manifest_route))
        .route("/rollouts/:rollout_id/frames/:step.png", get(frame_png_route))
        .route("/rollouts/:rollout_id/replay.gif", get(replay_gif_route))
        .route("/rollouts/:rollout_id", delete(close_rollout))
        .route("/state/:rollout_id", get(state_route))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind(format!("{}:{}", host, port))
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health(State(app): State<AppState>) -> Json<Value> {
    Json(json!({
        "ok": true,
        "engine": "crafter-singleplayer-rust-gold",
        "lane": "rust",
        "env_family": "crafter-singleplayer",
        "replay_enabled": app.replay.enabled,
        "pool": pool_stats(&app.sessions.lock().unwrap())
    }))
}

async fn info(State(app): State<AppState>) -> Json<Value> {
    let capabilities = vec![
        "rollout",
        "checkpoint",
        "checkpoint_list",
        "nev_log",
        "symbolic_readout",
        "render_svg",
        "render_png",
        "frame_manifest",
        "frame_png",
        "replay_gif",
        "session_pool",
        "batch_rollout",
        "simulate_from_checkpoint",
    ];
    Json(json!({
        "env_family": "crafter-singleplayer",
        "lane": "rust",
        "replay_enabled": app.replay.enabled,
        "capabilities": capabilities,
        "pool": pool_stats(&app.sessions.lock().unwrap())
    }))
}

async fn pool(State(app): State<AppState>) -> Json<Value> {
    Json(pool_stats(&app.sessions.lock().unwrap()))
}

async fn evict_idle(State(app): State<AppState>) -> Json<Value> {
    Json(json!({
        "evicted": 0,
        "pool": pool_stats(&app.sessions.lock().unwrap())
    }))
}

async fn create_rollout(
    State(app): State<AppState>,
    Json(body): Json<RolloutRequest>,
) -> Result<Json<Value>, ApiError> {
    let rollout_id = Uuid::new_v4().to_string();
    let mut session = session_from_rollout_request_checked(body)?;
    capture_frame_if_enabled(&mut session, app.replay, false);
    let payload = rollout_payload(&rollout_id, &session);
    app.sessions.lock().unwrap().insert(rollout_id, session);
    Ok(Json(payload))
}

async fn create_rollout_batch(
    State(app): State<AppState>,
    Json(body): Json<BatchRolloutRequest>,
) -> Result<Json<Value>, ApiError> {
    let items = batch_rollout_items(body);
    let mut rollouts = Vec::with_capacity(items.len());
    let mut pending = Vec::with_capacity(items.len());
    for item in items {
        let rollout_id = Uuid::new_v4().to_string();
        let mut session = session_from_rollout_request_checked(item)?;
        capture_frame_if_enabled(&mut session, app.replay, false);
        let item_payload = rollout_payload(&rollout_id, &session);
        rollouts.push(item_payload);
        pending.push((rollout_id, session));
    }
    let mut guard = app.sessions.lock().unwrap();
    for (rollout_id, session) in pending {
        guard.insert(rollout_id, session);
    }
    Ok(Json(json!({
        "count": rollouts.len(),
        "rollouts": rollouts,
        "pool": pool_stats(&guard)
    })))
}

async fn run_scenario_route(Json(body): Json<ScenarioRequest>) -> Result<Json<Value>, ApiError> {
    let session = reset_from_entry_checked(&body.task)?;
    Ok(Json(scenario_result(&body.task, &session)))
}

async fn step_legacy(
    State(app): State<AppState>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    let rollout_id = body
        .get("rollout_id")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let action = body.get("action").and_then(Value::as_str).unwrap_or("noop");
    let mut guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get_mut(&rollout_id) else {
        return Err(rollout_not_found());
    };
    step_session_checked(session, action, &rollout_id, app.replay)?;
    Ok(Json(rollout_payload(&rollout_id, session)))
}

async fn step(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<StepRequest>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get_mut(&rollout_id) else {
        return Err(rollout_not_found());
    };
    step_session_checked(session, &body.action, &rollout_id, app.replay)?;
    Ok(Json(rollout_payload(&rollout_id, session)))
}

async fn state_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get(&rollout_id) else {
        return Err(StatusCode::NOT_FOUND);
    };
    Ok(Json(rollout_payload(&rollout_id, session)))
}

async fn update_progress(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<ProgressUpdateRequest>,
) -> Result<Json<Value>, StatusCode> {
    let mut guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get_mut(&rollout_id) else {
        return Err(StatusCode::NOT_FOUND);
    };
    merge_agent_progress(session, &body);
    Ok(Json(rollout_payload(&rollout_id, session)))
}

async fn readout(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get(&rollout_id) else {
        return Err(StatusCode::NOT_FOUND);
    };
    Ok(Json(session.engine.readout()))
}

async fn events(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get(&rollout_id) else {
        return Err(StatusCode::NOT_FOUND);
    };
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "events": session.engine.events.clone(),
        "legacy": session.engine.legacy_strings(),
        "nev_cursor": session.engine.event_cursor()
    })))
}

async fn close_rollout(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let released = app.sessions.lock().unwrap().remove(&rollout_id).is_some();
    if !released {
        return Err(StatusCode::NOT_FOUND);
    }
    let guard = app.sessions.lock().unwrap();
    Ok(Json(
        json!({"rollout_id": rollout_id, "released": true, "pool": pool_stats(&guard)}),
    ))
}

async fn checkpoint_with_blob(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    save_checkpoint(app.sessions.clone(), rollout_id, true)
}

async fn checkpoint_without_blob(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    save_checkpoint(app.sessions.clone(), rollout_id, false)
}

async fn list_checkpoints(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get(&rollout_id) else {
        return Err(StatusCode::NOT_FOUND);
    };
    let mut checkpoints = session
        .checkpoint_metadata
        .values()
        .cloned()
        .collect::<Vec<_>>();
    checkpoints.sort_by(|left, right| {
        let left_index = left.get("saved_index").and_then(Value::as_u64).unwrap_or(0);
        let right_index = right
            .get("saved_index")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        left_index.cmp(&right_index).then_with(|| {
            left.get("checkpoint_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .cmp(
                    right
                        .get("checkpoint_id")
                        .and_then(Value::as_str)
                        .unwrap_or(""),
                )
        })
    });
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "checkpoint_count": checkpoints.len(),
        "checkpoints": checkpoints
    })))
}

async fn export_checkpoint(
    State(app): State<AppState>,
    Path(checkpoint_id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = app.sessions.lock().unwrap();
    for session in guard.values() {
        if let Some(blob) = session.checkpoints.get(&checkpoint_id) {
            return Ok(Json(json!({
                "checkpoint_id": checkpoint_id,
                "blob": BASE64.encode(blob)
            })));
        }
    }
    Err(StatusCode::NOT_FOUND)
}

async fn import_checkpoint(
    State(app): State<AppState>,
    Json(body): Json<CheckpointExport>,
) -> Result<Json<Value>, ApiError> {
    restore_new_payload(app.sessions.clone(), &body.blob, Some(body.checkpoint_id))
}

async fn restore_new(
    State(app): State<AppState>,
    Json(body): Json<RestoreRequest>,
) -> Result<Json<Value>, ApiError> {
    restore_new_payload(app.sessions.clone(), &body.blob, None)
}

async fn restore_in_place(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<RestoreRequest>,
) -> Result<Json<Value>, ApiError> {
    let blob = decode_checkpoint_blob(&body.blob)?;
    let checkpoint_hash = checkpoint_config_hash(&blob)?;
    let mut guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get_mut(&rollout_id) else {
        return Err(error_response(
            StatusCode::NOT_FOUND,
            "rollout_not_found",
            "rollout not found",
        ));
    };
    if checkpoint_hash != session.engine.config_hash {
        return Err(error_response(
            StatusCode::CONFLICT,
            "checkpoint_config_mismatch",
            "checkpoint config_hash does not match rollout config_hash",
        ));
    }
    let mut restored_engine = session.engine.clone();
    let restored = restore_checkpoint_checked(&mut restored_engine, &blob)?;
    session.engine = restored_engine;
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "restore_report": {"bytes": blob.len(), "wall_ms": 0.0, "nev_events_restored": restored},
        "state": rollout_payload(&rollout_id, session)
    })))
}

async fn simulate(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(body): Json<SimulateRequest>,
) -> Result<Json<Value>, ApiError> {
    let blob = decode_checkpoint_blob(&body.blob)?;
    let checkpoint_hash = checkpoint_config_hash(&blob)?;
    let root_nev_cursor = {
        let guard = app.sessions.lock().unwrap();
        let Some(session) = guard.get(&rollout_id) else {
            return Err(error_response(
                StatusCode::NOT_FOUND,
                "rollout_not_found",
                "rollout not found",
            ));
        };
        if checkpoint_hash != session.engine.config_hash {
            return Err(error_response(
                StatusCode::CONFLICT,
                "checkpoint_config_mismatch",
                "checkpoint config_hash does not match rollout config_hash",
            ));
        }
        session.engine.event_cursor()
    };
    let mut results = Vec::with_capacity(body.sequences.len());
    for (index, sequence) in body.sequences.into_iter().enumerate() {
        let mut sim = CrafterRustSession::reset_from_task(&default_restore_task());
        restore_checkpoint_checked(&mut sim, &blob)?;
        // Per-step reward trace + first-unlock step per achievement, so callers
        // can compute properly discounted returns (scientifically-valid Q).
        let mut reward_trace: Vec<f32> = Vec::with_capacity(sequence.len());
        let mut unlock_steps = serde_json::Map::new();
        let mut prev: std::collections::HashSet<String> =
            sim.achievements_unlocked().into_iter().collect();
        let mut steps = 0usize;
        for action in &sequence {
            if sim.terminated || sim.truncated {
                break;
            }
            step_simulation_checked(&mut sim, action)?;
            steps += 1;
            reward_trace.push(sim.reward_last);
            for name in sim.achievements_unlocked() {
                if !prev.contains(&name) {
                    unlock_steps
                        .entry(name.clone())
                        .or_insert_with(|| json!(steps));
                    prev.insert(name);
                }
            }
        }
        results.push(json!({
            "index": index,
            "actions": sequence,
            "reward": sim.total_reward,
            "reward_trace": reward_trace,
            "achievement_unlock_steps": unlock_steps,
            "steps": steps,
            "terminated": sim.terminated,
            "truncated": sim.truncated,
            "readout": sim.readout(),
            "nev_cursor": sim.event_cursor()
        }));
    }
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "root_nev_cursor": root_nev_cursor,
        "results": results
    })))
}

async fn render_svg_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Response, StatusCode> {
    let readout = {
        let guard = app.sessions.lock().unwrap();
        let Some(session) = guard.get(&rollout_id) else {
            return Err(StatusCode::NOT_FOUND);
        };
        session.engine.readout()
    };
    Ok((
        [("content-type", "image/svg+xml")],
        render_svg_from_readout(&readout),
    )
        .into_response())
}

async fn render_png_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Response, ApiError> {
    let png = {
        let guard = app.sessions.lock().unwrap();
        let Some(session) = guard.get(&rollout_id) else {
            return Err(rollout_not_found());
        };
        let readout = session.engine.readout();
        let frame = render_rgb_frame_from_readout(&readout, DEFAULT_RENDER_TILE_SIZE, RenderMode::Auto);
        encode_png_rgb(frame.0, frame.1, &frame.2)
    };
    Ok((
        [(header::CONTENT_TYPE, "image/png")],
        png,
    )
        .into_response())
}

async fn frame_manifest_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let Some(session) = guard.get(&rollout_id) else {
        return Err(rollout_not_found());
    };
    Ok(Json(frame_manifest(&rollout_id, session)))
}

async fn frame_png_route(
    State(app): State<AppState>,
    Path((rollout_id, step_raw)): Path<(String, String)>,
) -> Result<Response, ApiError> {
    let step = parse_frame_step(&step_raw).ok_or_else(|| {
        error_response(
            StatusCode::BAD_REQUEST,
            "frame_step_invalid",
            "frame step must be a non-negative integer",
        )
    })?;
    let png = {
        let mut guard = app.sessions.lock().unwrap();
        let Some(session) = guard.get_mut(&rollout_id) else {
            return Err(rollout_not_found());
        };
        let current_step = session.engine.step_index();
        if step == current_step && !session.frames.contains_key(&step) {
            store_frame(session, step);
        }
        session.frames.get(&step).cloned()
    };
    let Some(png) = png else {
        return Err(error_response(
            StatusCode::NOT_FOUND,
            "frame_not_found",
            "frame not found",
        ));
    };
    Ok((
        [(header::CONTENT_TYPE, "image/png")],
        png,
    )
        .into_response())
}

async fn replay_gif_route(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
    Query(query): Query<ReplayGifQuery>,
) -> Result<Response, ApiError> {
    let gif = {
        let mut guard = app.sessions.lock().unwrap();
        let Some(session) = guard.get_mut(&rollout_id) else {
            return Err(rollout_not_found());
        };
        if session.gif_frames.is_empty() {
            store_frame(session, session.engine.step_index());
        }
        let mut steps: Vec<u64> = session
            .gif_frames
            .keys()
            .copied()
            .filter(|step| query.through_step.is_none_or(|limit| *step <= limit))
            .collect();
        steps.sort_unstable();
        if steps.is_empty() {
            store_frame(session, session.engine.step_index());
            steps.push(session.engine.step_index());
        }
        let frames: Vec<RgbFrame> = steps
            .iter()
            .filter_map(|step| session.gif_frames.get(step).cloned())
            .collect();
        encode_gif_via_ffmpeg(&frames, 10).map_err(|err| {
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "gif_encode_failed",
                &err,
            )
        })?
    };
    Ok((
        [(header::CONTENT_TYPE, "image/gif")],
        gif,
    )
        .into_response())
}

fn parse_frame_step(raw: &str) -> Option<u64> {
    raw.strip_suffix(".png")
        .or(Some(raw))
        .and_then(|value| value.parse().ok())
}

fn replay_enabled_from_env() -> bool {
    match std::env::var("GAMEBENCH_CRAFTER_REPLAY_ENABLED")
        .ok()
        .map(|value| value.trim().to_ascii_lowercase())
        .as_deref()
    {
        Some("1") | Some("true") | Some("yes") | Some("on") => true,
        Some("0") | Some("false") | Some("no") | Some("off") => false,
        _ => false,
    }
}

fn rollout_capture_enabled(session: &RolloutSession) -> bool {
    let resolved = &session.engine.resolved_json;
    let visual_enabled = resolved
        .get("readouts")
        .and_then(|readouts| readouts.get("visual"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let stream = resolved.get("stream").and_then(Value::as_object);
    let stream_enabled = stream
        .and_then(|stream| stream.get("enabled"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let persist_frames = stream
        .and_then(|stream| stream.get("persist_frames"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    visual_enabled || stream_enabled || persist_frames
}

fn capture_frame_if_enabled(session: &mut RolloutSession, replay: ReplaySettings, force: bool) {
    if !replay.enabled {
        return;
    }
    if !force && !rollout_capture_enabled(session) {
        return;
    }
    store_frame(session, session.engine.step_index());
}

fn store_frame(session: &mut RolloutSession, step: u64) {
    let readout = session.engine.readout();
    let frame = render_rgb_frame_from_readout(&readout, DEFAULT_RENDER_TILE_SIZE, RenderMode::Auto);
    let png = encode_png_rgb(frame.0, frame.1, &frame.2);
    session.frames.insert(step, png);
    session.gif_frames.insert(step, frame);
}

fn frame_manifest(rollout_id: &str, session: &RolloutSession) -> Value {
    let mut frames = Vec::new();
    for step in session.frames.keys().copied().collect::<Vec<_>>().into_iter() {
        let blob = session.frames.get(&step).expect("frame step");
        frames.push(json!({
            "step": step,
            "bytes": blob.len(),
            "sha256": frame_sha256(blob),
            "url": format!("/rollouts/{}/frames/{}.png", rollout_id, step),
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
    let engine = &session.engine;
    let readout = engine.readout();
    json!({
        "rollout_id": rollout_id,
        "public": readout.get("public").cloned().unwrap_or(Value::Null),
        "private": engine.private_json(),
        "readout": readout,
        "reward": engine.total_reward,
        "terminated": engine.terminated,
        "truncated": engine.truncated,
        "limits": session.limits.clone(),
        "progress": rollout_progress(session),
        "nev_tail": engine.events.iter().rev().take(5).cloned().collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>(),
        "nev_cursor": engine.event_cursor()
    })
}

fn rollout_progress(session: &RolloutSession) -> Value {
    let agent = &session.agent_progress;
    let prompt_tokens = agent
        .get("prompt_tokens")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let completion_tokens = agent
        .get("completion_tokens")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let total_tokens = agent
        .get("total_tokens")
        .and_then(Value::as_u64)
        .unwrap_or(prompt_tokens + completion_tokens);
    let wall_clock_seconds = agent
        .get("wall_clock_seconds")
        .and_then(Value::as_f64)
        .unwrap_or_else(|| session.started_at.elapsed().as_secs_f64());
    json!({
        "env_steps": session.engine.step_index(),
        "llm_calls_completed": agent.get("llm_calls_completed").and_then(Value::as_u64).unwrap_or(0),
        "llm_call_in_flight": agent.get("llm_call_in_flight").and_then(Value::as_bool).unwrap_or(false),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "wall_clock_seconds": wall_clock_seconds,
    })
}

fn merge_agent_progress(session: &mut RolloutSession, patch: &ProgressUpdateRequest) {
    let map = session
        .agent_progress
        .as_object_mut()
        .expect("agent_progress must be an object");
    if let Some(value) = patch.llm_calls_completed {
        map.insert("llm_calls_completed".to_string(), json!(value));
    }
    if let Some(value) = patch.llm_call_in_flight {
        map.insert("llm_call_in_flight".to_string(), json!(value));
    }
    if let Some(value) = patch.prompt_tokens {
        map.insert("prompt_tokens".to_string(), json!(value));
    }
    if let Some(value) = patch.completion_tokens {
        map.insert("completion_tokens".to_string(), json!(value));
    }
    if let Some(value) = patch.total_tokens {
        map.insert("total_tokens".to_string(), json!(value));
    }
    if let Some(value) = patch.wall_clock_seconds {
        map.insert("wall_clock_seconds".to_string(), json!(value));
    }
}

fn scenario_result(task: &Value, session: &CrafterRustSession) -> Value {
    json!({
        "scenario_id": task.get("scenario_id").and_then(Value::as_str).unwrap_or(&session.scenario_id),
        "events": session.legacy_strings(),
        "nev": session.events.clone(),
        "checkpoint_cursor": Value::Null,
        "state": {
            "public": session.readout().get("public").cloned().unwrap_or(Value::Null),
            "private": session.private_json()
        },
        "readout": session.readout()
    })
}

fn save_checkpoint(
    sessions: Sessions,
    rollout_id: String,
    include_blob: bool,
) -> Result<Json<Value>, ApiError> {
    let mut guard = sessions.lock().unwrap();
    let Some(session) = guard.get_mut(&rollout_id) else {
        return Err(rollout_not_found());
    };
    let payload = store_checkpoint_checked(session, &rollout_id, "manual", include_blob)?;
    Ok(Json(payload))
}

fn store_checkpoint(
    session: &mut RolloutSession,
    rollout_id: &str,
    source: &str,
    include_blob: bool,
) -> Value {
    let blob = session.engine.checkpoint_bytes();
    let checkpoint_id = Uuid::new_v4().to_string();
    session
        .checkpoints
        .insert(checkpoint_id.clone(), blob.clone());
    let mut payload = checkpoint_metadata(
        rollout_id,
        &checkpoint_id,
        &session.engine,
        blob.len(),
        session.checkpoints.len(),
        source,
    );
    session
        .checkpoint_metadata
        .insert(checkpoint_id, payload.clone());
    if include_blob {
        payload["blob"] = Value::String(BASE64.encode(blob));
    }
    payload
}

fn maybe_save_cadence_checkpoint(session: &mut RolloutSession, rollout_id: &str) {
    let interval = session
        .engine
        .resolved_json
        .get("checkpoint_every_n_steps")
        .and_then(Value::as_u64)
        .unwrap_or(10);
    let step = session.engine.step_index();
    if interval == 0 || step == 0 || !step.is_multiple_of(interval) {
        return;
    }
    let already_saved = session.checkpoint_metadata.values().any(|metadata| {
        metadata.get("source").and_then(Value::as_str) == Some("cadence")
            && metadata.get("step_index").and_then(Value::as_u64) == Some(step)
    });
    if already_saved {
        return;
    }
    store_checkpoint(session, rollout_id, "cadence", false);
}

fn step_session_checked(
    session: &mut RolloutSession,
    action: &str,
    rollout_id: &str,
    replay: ReplaySettings,
) -> Result<(), ApiError> {
    catch_unwind(AssertUnwindSafe(|| {
        session.engine.step(action);
        maybe_save_cadence_checkpoint(session, rollout_id);
        capture_frame_if_enabled(session, replay, false);
    }))
    .map_err(|panic| {
        error_response(
            StatusCode::BAD_REQUEST,
            "runtime_step_failed",
            panic_message(&panic),
        )
    })
}

fn step_simulation_checked(engine: &mut CrafterRustSession, action: &str) -> Result<(), ApiError> {
    catch_unwind(AssertUnwindSafe(|| engine.step(action))).map_err(|panic| {
        error_response(
            StatusCode::BAD_REQUEST,
            "simulation_step_failed",
            panic_message(&panic),
        )
    })
}

fn store_checkpoint_checked(
    session: &mut RolloutSession,
    rollout_id: &str,
    source: &str,
    include_blob: bool,
) -> Result<Value, ApiError> {
    catch_unwind(AssertUnwindSafe(|| {
        store_checkpoint(session, rollout_id, source, include_blob)
    }))
    .map_err(|panic| {
        error_response(
            StatusCode::BAD_REQUEST,
            "checkpoint_save_failed",
            panic_message(&panic),
        )
    })
}

fn checkpoint_metadata(
    rollout_id: &str,
    checkpoint_id: &str,
    engine: &CrafterRustSession,
    blob_len: usize,
    saved_index: usize,
    source: &str,
) -> Value {
    json!({
        "rollout_id": rollout_id,
        "checkpoint_id": checkpoint_id,
        "saved_index": saved_index,
        "source": source,
        "auto": source == "cadence",
        "bytes": blob_len,
        "step_index": engine.step_index(),
        "nev_cursor": engine.event_cursor(),
        "config_hash": engine.config_hash,
        "export_url": format!("/checkpoints/{}/export", checkpoint_id)
    })
}

fn restore_new_payload(
    sessions: Sessions,
    blob_b64: &str,
    checkpoint_id: Option<String>,
) -> Result<Json<Value>, ApiError> {
    let blob = decode_checkpoint_blob(blob_b64)?;
    let mut engine = CrafterRustSession::reset_from_task(&default_restore_task());
    let restored = restore_checkpoint_checked(&mut engine, &blob)?;
    let rollout_id = Uuid::new_v4().to_string();
    let session = RolloutSession {
        engine,
        limits: json!({}),
        agent_progress: json!({}),
        started_at: Instant::now(),
        checkpoints: HashMap::new(),
        checkpoint_metadata: HashMap::new(),
        frames: HashMap::new(),
        gif_frames: HashMap::new(),
    };
    let mut payload = rollout_payload(&rollout_id, &session);
    payload["restore_report"] =
        json!({"bytes": blob.len(), "wall_ms": 0.0, "nev_events_restored": restored});
    if let Some(checkpoint_id) = checkpoint_id {
        payload["checkpoint_id"] = Value::String(checkpoint_id);
    }
    sessions.lock().unwrap().insert(rollout_id, session);
    Ok(Json(payload))
}

fn decode_checkpoint_blob(blob_b64: &str) -> Result<Vec<u8>, ApiError> {
    BASE64.decode(blob_b64.as_bytes()).map_err(|_| {
        error_response(
            StatusCode::BAD_REQUEST,
            "checkpoint_blob_invalid_base64",
            "checkpoint blob must be valid base64",
        )
    })
}

fn checkpoint_config_hash(blob: &[u8]) -> Result<String, ApiError> {
    let payload: Value = serde_json::from_slice(blob).map_err(|_| {
        error_response(
            StatusCode::BAD_REQUEST,
            "checkpoint_blob_invalid_json",
            "checkpoint blob must be supported checkpoint JSON",
        )
    })?;
    if payload.get("schema_version").and_then(Value::as_str) != Some("gamebench.checkpoint.v1") {
        return Err(error_response(
            StatusCode::BAD_REQUEST,
            "checkpoint_schema_unsupported",
            "checkpoint blob schema_version is unsupported",
        ));
    }
    payload
        .get("config_hash")
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| {
            error_response(
                StatusCode::BAD_REQUEST,
                "checkpoint_config_hash_missing",
                "checkpoint blob missing config_hash",
            )
        })
}

fn restore_checkpoint_checked(
    engine: &mut CrafterRustSession,
    blob: &[u8],
) -> Result<usize, ApiError> {
    catch_unwind(AssertUnwindSafe(|| engine.restore_checkpoint_bytes(blob))).map_err(|panic| {
        error_response(
            StatusCode::BAD_REQUEST,
            "checkpoint_restore_failed",
            panic_message(&panic),
        )
    })
}

fn reset_from_entry_checked(task: &Value) -> Result<CrafterRustSession, ApiError> {
    catch_unwind(AssertUnwindSafe(|| {
        CrafterRustSession::reset_from_entry(task)
    }))
    .map_err(|panic| {
        error_response(
            StatusCode::BAD_REQUEST,
            "task_reset_failed",
            panic_message(&panic),
        )
    })
}

fn session_from_rollout_request_checked(body: RolloutRequest) -> Result<RolloutSession, ApiError> {
    catch_unwind(AssertUnwindSafe(|| session_from_rollout_request(body))).map_err(|panic| {
        error_response(
            StatusCode::BAD_REQUEST,
            "task_reset_failed",
            panic_message(&panic),
        )
    })
}

fn panic_message(panic: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(message) = panic.downcast_ref::<&str>() {
        return (*message).to_string();
    }
    if let Some(message) = panic.downcast_ref::<String>() {
        return message.clone();
    }
    "runtime operation failed".to_string()
}

fn error_response(status: StatusCode, code: &'static str, message: impl Into<String>) -> ApiError {
    ApiError {
        status,
        code,
        message: message.into(),
    }
}

fn rollout_not_found() -> ApiError {
    error_response(
        StatusCode::NOT_FOUND,
        "rollout_not_found",
        "rollout not found",
    )
}

fn default_restore_task() -> Value {
    json!({
        "schema": "gamebench.task.crafter.v1",
        "task_id": "restored",
        "world": {"use_default": "policy_dev_small"},
        "rules": {"base": "no_homeostasis"}
    })
}

fn session_from_rollout_request(body: RolloutRequest) -> RolloutSession {
    let mut task = body.task.unwrap_or_else(|| {
        json!({
            "schema": "gamebench.task.crafter.v1",
            "task_id": "manual",
            "world": {"use_default": "policy_dev_small"},
            "rules": {"base": "no_homeostasis"}
        })
    });
    if let Some(seed) = body.seed {
        task["world"]["seed"] = Value::from(seed);
    }
    RolloutSession {
        engine: CrafterRustSession::reset_from_task(&task),
        limits: body.limits.unwrap_or_else(|| json!({})),
        agent_progress: json!({}),
        started_at: Instant::now(),
        checkpoints: HashMap::new(),
        checkpoint_metadata: HashMap::new(),
        frames: HashMap::new(),
        gif_frames: HashMap::new(),
    }
}

fn batch_rollout_items(body: BatchRolloutRequest) -> Vec<RolloutRequest> {
    if let Some(items) = body.items {
        return items;
    }
    let tasks = body.tasks.unwrap_or_default();
    let seeds = body.seeds.unwrap_or_default();
    tasks
        .into_iter()
        .enumerate()
        .map(|(index, task)| RolloutRequest {
            task: Some(task),
            seed: seeds.get(index).copied().flatten(),
            limits: None,
        })
        .collect()
}

fn render_svg_from_readout(readout: &Value) -> String {
    let observation = readout
        .get("public")
        .and_then(|public| public.get("observation"))
        .unwrap_or(&Value::Null);
    let Some(view) = observation.get("view") else {
        return empty_svg();
    };
    let radius = view.get("radius").and_then(Value::as_u64).unwrap_or(0) as usize;
    let size = radius.saturating_mul(2).saturating_add(1);
    if size == 0 {
        return empty_svg();
    }
    if view.get("tiles").and_then(Value::as_array).is_some() {
        return render_native_view_svg(view, radius, size);
    }
    render_legacy_view_svg(view, radius, size)
}

fn render_native_view_svg(view: &Value, radius: usize, size: usize) -> String {
    let Some(tiles) = view.get("tiles").and_then(Value::as_array) else {
        return empty_svg();
    };
    let Some(center) = view.get("center").and_then(value_pair_i64) else {
        return empty_svg();
    };
    let radius_i64 = radius as i64;
    let mut grid = vec![vec!['?'; size]; size];

    for tile in tiles {
        let Some(pos) = tile.get("pos").and_then(value_pair_i64) else {
            continue;
        };
        let Some((x, y)) = view_grid_pos(pos, center, radius_i64, size) else {
            continue;
        };
        let ch = if tile
            .get("in_bounds")
            .and_then(Value::as_bool)
            .unwrap_or(true)
        {
            material_char(tile.get("kind"))
        } else {
            '?'
        };
        grid[y][x] = ch;
    }

    if let Some(entities) = view.get("entities").and_then(Value::as_array) {
        for entity in entities {
            let Some(pos) = entity.get("pos").and_then(value_pair_i64) else {
                continue;
            };
            let Some((x, y)) = view_grid_pos(pos, center, radius_i64, size) else {
                continue;
            };
            grid[y][x] = object_char(entity.get("kind").unwrap_or(entity));
        }
    }

    grid[radius][radius] = '@';
    let lines = grid
        .into_iter()
        .map(|row| row.into_iter().collect::<String>())
        .collect::<Vec<_>>();
    ascii_lines_to_svg(&lines)
}

fn render_legacy_view_svg(view: &Value, radius: usize, size: usize) -> String {
    let materials = view
        .get("materials")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let in_bounds = view.get("in_bounds").and_then(Value::as_array);
    let mut object_chars: HashMap<(usize, usize), char> = HashMap::new();
    if let Some(objects) = view.get("objects").and_then(Value::as_array) {
        for object in objects {
            let Some(items) = object.as_array() else {
                continue;
            };
            if items.len() < 3 {
                continue;
            }
            let Some(x) = items[0].as_u64().map(|value| value as usize) else {
                continue;
            };
            let Some(y) = items[1].as_u64().map(|value| value as usize) else {
                continue;
            };
            object_chars.insert((x, y), object_char(&items[2]));
        }
    }

    let mut lines = Vec::with_capacity(size);
    for y in 0..size {
        let mut line = String::with_capacity(size);
        for x in 0..size {
            let idx = y * size + x;
            let ch = if x == radius && y == radius {
                '@'
            } else if let Some(ch) = object_chars.get(&(x, y)) {
                *ch
            } else if !in_bounds
                .and_then(|items| items.get(idx))
                .and_then(Value::as_bool)
                .unwrap_or(true)
            {
                '?'
            } else {
                material_char(materials.get(idx))
            };
            line.push(ch);
        }
        lines.push(line);
    }
    ascii_lines_to_svg(&lines)
}

fn value_pair_i64(value: &Value) -> Option<(i64, i64)> {
    let items = value.as_array()?;
    if items.len() < 2 {
        return None;
    }
    Some((items[0].as_i64()?, items[1].as_i64()?))
}

fn view_grid_pos(
    pos: (i64, i64),
    center: (i64, i64),
    radius: i64,
    size: usize,
) -> Option<(usize, usize)> {
    let x = pos.0 - center.0 + radius;
    let y = pos.1 - center.1 + radius;
    if x < 0 || y < 0 || x >= size as i64 || y >= size as i64 {
        return None;
    }
    Some((x as usize, y as usize))
}

fn ascii_lines_to_svg(lines: &[String]) -> String {
    let tile_size = 14usize;
    let width = lines.iter().map(String::len).max().unwrap_or(1) * tile_size;
    let height = lines.len().max(1) * tile_size;
    let text = lines
        .iter()
        .enumerate()
        .map(|(idx, line)| {
            format!(
                r#"<text x="4" y="{}" font-family="monospace" font-size="12">{}</text>"#,
                (idx + 1) * tile_size - 3,
                escape_xml(line)
            )
        })
        .collect::<Vec<_>>()
        .join("");
    format!(
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}"><rect width="100%" height="100%" fill="white"/>{}</svg>"#,
        width, height, text
    )
}

fn empty_svg() -> String {
    ascii_lines_to_svg(&[String::new()])
}

fn material_char(value: Option<&Value>) -> char {
    let kind = value
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_ascii_lowercase();
    match kind.as_str() {
        "water" => '~',
        "grass" => '.',
        "stone" => '^',
        "path" => ':',
        "sand" => ',',
        "tree" => 'T',
        "lava" => 'L',
        "coal" => 'c',
        "iron" => 'i',
        "diamond" => 'd',
        "table" => '#',
        "furnace" => 'F',
        "sapphire" => 's',
        "ruby" => 'r',
        "chest" => 'C',
        _ => '?',
    }
}

fn object_char(value: &Value) -> char {
    let kind = value
        .as_object()
        .and_then(|object| object.keys().next())
        .map(|key| key.to_ascii_lowercase())
        .or_else(|| value.as_str().map(str::to_ascii_lowercase))
        .unwrap_or_else(|| "object".to_string());
    match kind.as_str() {
        "player" => '@',
        "cow" => 'C',
        "zombie" => 'Z',
        "skeleton" => 'S',
        "plant" => 'P',
        "arrow" => '*',
        "fireball" => '*',
        "orc_soldier" => 'O',
        "orc_mage" => 'M',
        "knight" => 'K',
        "knight_archer" => 'A',
        "troll" => 'T',
        "bat" => 'B',
        "snail" => 'N',
        _ => 'E',
    }
}

fn escape_xml(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn pool_stats(sessions: &HashMap<String, RolloutSession>) -> Value {
    json!({
        "active_sessions": sessions.len(),
        "terminated_sessions": sessions
            .values()
            .filter(|session| session.engine.terminated || session.engine.truncated)
            .count(),
        "max_active_sessions": Value::Null,
        "idle_ttl_seconds": Value::Null,
        "auto_release_on_terminal": false,
        "supports_many_live_seeds": true
    })
}
