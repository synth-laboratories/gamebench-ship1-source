use axum::extract::{Path, State};
use axum::http::{header, StatusCode};
use axum::response::Response;
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use pokemon_emerald_littleroot_gold::{encode_png_rgb, frame_sha256, LittlerootSession, OpeningCheckpoint, StepRequest, ENV_FAMILY, FRAME_HEIGHT, FRAME_WIDTH};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

#[derive(Clone, Default)]
struct AppState {
    sessions: Arc<Mutex<HashMap<String, LittlerootSession>>>,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
struct CreateRolloutRequest {
    checkpoint: Option<OpeningCheckpoint>,
}

#[derive(Clone, Debug, Deserialize)]
struct RestoreRequest { blob: String }

#[derive(Clone, Debug, Deserialize)]
struct SimulateRequest {
    blob: String,
    sequences: Vec<Vec<StepRequest>>,
}

#[tokio::main]
async fn main() {
    let port = std::env::args()
        .skip_while(|arg| arg != "--port")
        .nth(1)
        .and_then(|arg| arg.parse().ok())
        .unwrap_or(8103_u16);
    let app = Router::new()
        .route("/health", get(health))
        .route("/info", get(info))
        .route("/rollouts", post(create_rollout))
        .route("/rollouts/:rollout_id/step", post(step))
        .route("/rollouts/:rollout_id/checkpoint", post(checkpoint))
        .route("/rollouts/:rollout_id/restore", post(restore))
        .route("/rollouts/:rollout_id/simulate", post(simulate))
        .route("/rollouts/:rollout_id/readout", get(readout))
        .route("/rollouts/:rollout_id/frame", get(frame))
        .route("/rollouts/:rollout_id/render.png", get(render_png))
        .with_state(AppState::default());
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port))
        .await
        .expect("bind Pokémon Emerald Littleroot gold service");
    axum::serve(listener, app).await.expect("serve gold service");
}

async fn health(State(state): State<AppState>) -> Json<Value> {
    Json(json!({ "ok": true, "lane": "rust", "env_family": ENV_FAMILY, "sessions": state.sessions.lock().unwrap().len() }))
}

async fn info() -> Json<Value> {
    Json(json!({
        "lane": "rust",
        "env_family": ENV_FAMILY,
        "frame": { "width": FRAME_WIDTH, "height": FRAME_HEIGHT, "pixel_format": "rgb8" },
        "parity_status": "partial_exact_trace_corpus",
        "exact_reference_frames": 61,
        "native_fallback": true,
    }))
}

async fn create_rollout(State(state): State<AppState>, request: Option<Json<CreateRolloutRequest>>) -> Json<Value> {
    let rollout_id = Uuid::new_v4().to_string();
    let checkpoint = request.and_then(|request| request.0.checkpoint).unwrap_or(OpeningCheckpoint::RivalOutsideLab);
    let session = LittlerootSession::from_checkpoint(checkpoint);
    let readout = session.readout();
    state.sessions.lock().unwrap().insert(rollout_id.clone(), session);
    Json(json!({ "rollout_id": rollout_id, "readout": readout }))
}

async fn step(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(request): Json<StepRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let mut sessions = state.sessions.lock().unwrap();
    let session = sessions.get_mut(&rollout_id).ok_or_else(not_found)?;
    session.step(request);
    Ok(Json(session.readout()))
}

async fn readout(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let sessions = state.sessions.lock().unwrap();
    let session = sessions.get(&rollout_id).ok_or_else(not_found)?;
    Ok(Json(session.readout()))
}

async fn checkpoint(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let sessions = state.sessions.lock().unwrap();
    let session = sessions.get(&rollout_id).ok_or_else(not_found)?;
    let blob = session.checkpoint_bytes().map_err(internal_error)?;
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "checkpoint_id": Uuid::new_v4().to_string(),
        "blob": STANDARD.encode(&blob),
        "bytes": blob.len(),
        "frame_index": session.frame_index,
    })))
}

async fn restore(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(request): Json<RestoreRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let bytes = STANDARD.decode(request.blob.as_bytes()).map_err(|_| bad_request("invalid base64 checkpoint"))?;
    let mut sessions = state.sessions.lock().unwrap();
    let session = sessions.get_mut(&rollout_id).ok_or_else(not_found)?;
    session.restore_checkpoint(&bytes).map_err(bad_request)?;
    Ok(Json(json!({ "rollout_id": rollout_id, "restore_report": { "bytes": bytes.len() }, "readout": session.readout() })))
}

async fn simulate(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
    Json(request): Json<SimulateRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let bytes = STANDARD.decode(request.blob.as_bytes()).map_err(|_| bad_request("invalid base64 checkpoint"))?;
    let sessions = state.sessions.lock().unwrap();
    let session = sessions.get(&rollout_id).ok_or_else(not_found)?;
    let mut results = Vec::with_capacity(request.sequences.len());
    for (index, sequence) in request.sequences.into_iter().enumerate() {
        let mut branch = session.clone();
        branch.restore_checkpoint(&bytes).map_err(bad_request)?;
        for step in &sequence { branch.step(step.clone()); }
        results.push(json!({ "index": index, "inputs": sequence, "readout": branch.readout() }));
    }
    Ok(Json(json!({ "rollout_id": rollout_id, "root_frame_index": session.frame_index, "results": results })))
}

async fn frame(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Response, (StatusCode, Json<Value>)> {
    let sessions = state.sessions.lock().unwrap();
    let session = sessions.get(&rollout_id).ok_or_else(not_found)?;
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "application/octet-stream")
        .header("x-gamebench-frame-width", FRAME_WIDTH)
        .header("x-gamebench-frame-height", FRAME_HEIGHT)
        .header("x-gamebench-frame-sha256", frame_sha256(session.frame_rgb()))
        .body(session.frame_rgb().to_vec().into())
        .map_err(|error| internal_error(error.to_string()))
}

async fn render_png(
    State(state): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Response, (StatusCode, Json<Value>)> {
    let sessions = state.sessions.lock().unwrap();
    let session = sessions.get(&rollout_id).ok_or_else(not_found)?;
    let png = encode_png_rgb(session.frame_rgb()).map_err(internal_error)?;
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "image/png")
        .header("x-gamebench-frame-sha256", frame_sha256(session.frame_rgb()))
        .body(png.into())
        .map_err(|error| internal_error(error.to_string()))
}

fn not_found() -> (StatusCode, Json<Value>) {
    (StatusCode::NOT_FOUND, Json(json!({ "error": { "code": "rollout_not_found" } })))
}

fn internal_error(message: String) -> (StatusCode, Json<Value>) {
    (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "error": { "code": "response_build_failed", "message": message } })))
}

fn bad_request(message: impl Into<String>) -> (StatusCode, Json<Value>) {
    (StatusCode::BAD_REQUEST, Json(json!({ "error": { "code": "invalid_checkpoint", "message": message.into() } })))
}
