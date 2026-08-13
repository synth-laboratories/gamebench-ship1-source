use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::STANDARD, Engine};
use nethack_dlvl1_gold::{resolve_task, run_scenario_entry, NethackSession, ENV_FAMILY};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::{Arc, Mutex},
};
use uuid::Uuid;

type Sessions = Arc<Mutex<HashMap<String, NethackSession>>>;

#[derive(Deserialize)]
struct ScenarioRequest {
    task: Value,
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
    sequences: Vec<Vec<Value>>,
}

#[tokio::main]
async fn main() {
    let mut host = "127.0.0.1".to_string();
    let mut port = 8121u16;
    let args = std::env::args().collect::<Vec<_>>();
    let mut index = 1;
    while index < args.len() {
        if args[index] == "--host" && index + 1 < args.len() {
            host = args[index + 1].clone();
            index += 2;
        } else if args[index] == "--port" && index + 1 < args.len() {
            port = args[index + 1].parse().expect("numeric port");
            index += 2;
        } else {
            index += 1;
        }
    }
    let sessions: Sessions = Arc::new(Mutex::new(HashMap::new()));
    let app = Router::new()
        .route("/health", get(health))
        .route("/run_scenario", post(run_scenario))
        .route("/rollouts", post(create_rollout))
        .route("/rollouts/:id/step", post(step))
        .route("/rollouts/:id/checkpoint", post(checkpoint))
        .route("/rollouts/:id/restore", post(restore))
        .route("/rollouts/:id/simulate", post(simulate))
        .route("/rollouts/:id/readout", get(readout))
        .route("/rollouts/:id/event_log", get(event_log))
        .with_state(sessions);
    let listener = tokio::net::TcpListener::bind(
        format!("{host}:{port}")
            .parse::<SocketAddr>()
            .expect("socket address"),
    )
    .await
    .expect("bind service socket");
    axum::serve(listener, app).await.expect("serve gold HTTP");
}

async fn health(State(sessions): State<Sessions>) -> Json<Value> {
    Json(
        json!({"ok": true, "lane": "rust", "env_family": ENV_FAMILY, "sessions": sessions.lock().expect("session lock").len()}),
    )
}

async fn run_scenario(
    Json(body): Json<ScenarioRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    run_scenario_entry(&body.task)
        .map(Json)
        .map_err(bad_request)
}

async fn create_rollout(
    State(sessions): State<Sessions>,
    Json(body): Json<RolloutRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let task = body.task.unwrap_or_else(default_task);
    let resolved = resolve_task(&task, body.seed).map_err(bad_request)?;
    let session = NethackSession::reset(resolved).map_err(bad_request)?;
    let id = Uuid::new_v4().to_string();
    sessions
        .lock()
        .expect("session lock")
        .insert(id.clone(), session);
    let guard = sessions.lock().expect("session lock");
    Ok(Json(payload(&id, guard.get(&id).expect("stored rollout"))))
}

async fn step(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<StepRequest>,
) -> Result<Json<Value>, StatusCode> {
    let mut guard = sessions.lock().expect("session lock");
    let session = guard.get_mut(&id).ok_or(StatusCode::NOT_FOUND)?;
    session.step(body.action);
    Ok(Json(payload(&id, session)))
}

async fn checkpoint(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().expect("session lock");
    let session = guard.get(&id).ok_or(StatusCode::NOT_FOUND)?;
    let blob = session.checkpoint_bytes();
    Ok(Json(
        json!({"rollout_id": id, "checkpoint_id": Uuid::new_v4().to_string(), "blob": STANDARD.encode(&blob), "bytes": blob.len(), "nev_cursor": session.events.len(), "readout": session.readout()}),
    ))
}

async fn restore(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<RestoreRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let bytes = STANDARD.decode(body.blob.as_bytes()).map_err(|error| {
        (
            StatusCode::BAD_REQUEST,
            format!("invalid checkpoint: {error}"),
        )
    })?;
    let mut guard = sessions.lock().expect("session lock");
    let session = guard
        .get_mut(&id)
        .ok_or((StatusCode::NOT_FOUND, "rollout not found".to_string()))?;
    let restored = session.restore_checkpoint(&bytes).map_err(bad_request)?;
    Ok(Json(
        json!({"rollout_id": id, "restore_report": {"bytes": bytes.len(), "wall_ms": 0.0, "nev_events_restored": restored}, "readout": session.readout()}),
    ))
}

async fn simulate(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<SimulateRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let bytes = STANDARD.decode(body.blob.as_bytes()).map_err(|error| {
        (
            StatusCode::BAD_REQUEST,
            format!("invalid checkpoint: {error}"),
        )
    })?;
    let guard = sessions.lock().expect("session lock");
    let root = guard
        .get(&id)
        .ok_or((StatusCode::NOT_FOUND, "rollout not found".to_string()))?;
    let mut results = Vec::new();
    for (index, sequence) in body.sequences.iter().enumerate() {
        let mut sim = root.clone();
        sim.restore_checkpoint(&bytes).map_err(bad_request)?;
        for action in sequence {
            if sim.state.terminated || sim.state.truncated {
                break;
            }
            sim.step(action.clone());
        }
        results.push(json!({"index": index, "actions": sequence, "reward": sim.state.reward, "terminated": sim.state.terminated, "truncated": sim.state.truncated, "readout": sim.readout(), "nev_cursor": sim.events.len()}));
    }
    Ok(Json(
        json!({"rollout_id": id, "root_nev_cursor": root.events.len(), "results": results}),
    ))
}

async fn readout(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().expect("session lock");
    Ok(Json(guard.get(&id).ok_or(StatusCode::NOT_FOUND)?.readout()))
}

async fn event_log(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().expect("session lock");
    let session = guard.get(&id).ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(
        json!({"events": session.events, "legacy": session.legacy_strings(), "nev_cursor": session.events.len()}),
    ))
}

fn payload(id: &str, session: &NethackSession) -> Value {
    json!({"rollout_id": id, "readout": session.readout(), "reward": session.state.reward, "terminated": session.state.terminated, "truncated": session.state.truncated, "nev_cursor": session.events.len()})
}

fn default_task() -> Value {
    serde_json::from_str(include_str!(
        "../../../fixtures/gold/scenarios/bootstrap_descend.json"
    ))
    .expect("valid default task")
}

fn bad_request(error: String) -> (StatusCode, String) {
    (StatusCode::BAD_REQUEST, error)
}
