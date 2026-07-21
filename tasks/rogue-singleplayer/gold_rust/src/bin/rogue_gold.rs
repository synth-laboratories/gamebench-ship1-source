use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::STANDARD, Engine};
use rogue_gold::{resolve_task, RogueSession};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::{Arc, Mutex},
};
use uuid::Uuid;

type Sessions = Arc<Mutex<HashMap<String, RogueSession>>>;

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
    action: String,
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

#[tokio::main]
async fn main() {
    let mut host = "127.0.0.1".to_string();
    let mut port = 8101u16;
    let args: Vec<String> = std::env::args().collect();
    let mut i = 1;
    while i < args.len() {
        if args[i] == "--host" && i + 1 < args.len() {
            host = args[i + 1].clone();
            i += 2;
        } else if args[i] == "--port" && i + 1 < args.len() {
            port = args[i + 1].parse().unwrap();
            i += 2;
        } else {
            i += 1;
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
    let listener =
        tokio::net::TcpListener::bind(format!("{}:{}", host, port).parse::<SocketAddr>().unwrap())
            .await
            .unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health(State(sessions): State<Sessions>) -> Json<Value> {
    Json(
        json!({"ok": true, "lane": "rust", "env_family": RogueSession::ENV_FAMILY, "sessions": sessions.lock().unwrap().len()}),
    )
}

async fn run_scenario(Json(body): Json<ScenarioRequest>) -> Json<Value> {
    let session = RogueSession::reset_from_entry(&body.task);
    let scenario_id = body
        .task
        .get("scenario_id")
        .or_else(|| body.task.get("task_id"))
        .and_then(Value::as_str)
        .unwrap_or("manual");
    Json(
        json!({"scenario_id": scenario_id, "events": session.legacy_strings(), "nev": session.events, "state": {"public": session.readout()["public"], "private": session.readout()["private"]}, "readout": session.readout()}),
    )
}

async fn create_rollout(
    State(sessions): State<Sessions>,
    Json(body): Json<RolloutRequest>,
) -> Json<Value> {
    let task = body.task.unwrap_or_else(default_task);
    let mut session = RogueSession::default();
    session.reset(resolve_task(&task, body.seed));
    let id = Uuid::new_v4().to_string();
    sessions.lock().unwrap().insert(id.clone(), session);
    Json(payload(&id, sessions.lock().unwrap().get(&id).unwrap()))
}

async fn step(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<StepRequest>,
) -> Result<Json<Value>, StatusCode> {
    let mut guard = sessions.lock().unwrap();
    let session = guard.get_mut(&id).ok_or(StatusCode::NOT_FOUND)?;
    session.step(&body.action);
    Ok(Json(payload(&id, session)))
}

async fn checkpoint(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().unwrap();
    let session = guard.get(&id).ok_or(StatusCode::NOT_FOUND)?;
    let blob = session.checkpoint_bytes();
    Ok(Json(json!({
        "rollout_id": id,
        "checkpoint_id": Uuid::new_v4().to_string(),
        "blob": STANDARD.encode(&blob),
        "bytes": blob.len(),
        "nev_cursor": session.events.len(),
        "source_state_projection": session.source_state_projection()
    })))
}

async fn restore(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<RestoreRequest>,
) -> Result<Json<Value>, StatusCode> {
    let mut guard = sessions.lock().unwrap();
    let session = guard.get_mut(&id).ok_or(StatusCode::NOT_FOUND)?;
    let blob = STANDARD
        .decode(body.blob.as_bytes())
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    let restored = session.restore_checkpoint(&blob);
    Ok(Json(
        json!({"rollout_id": id, "restore_report": {"bytes": blob.len(), "wall_ms": 0.0, "nev_events_restored": restored}, "readout": session.readout()}),
    ))
}

async fn simulate(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<SimulateRequest>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().unwrap();
    let session = guard.get(&id).ok_or(StatusCode::NOT_FOUND)?;
    let blob = STANDARD
        .decode(body.blob.as_bytes())
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    let mut results = Vec::new();
    for (index, sequence) in body.sequences.iter().enumerate() {
        let mut sim = session.clone();
        sim.restore_checkpoint(&blob);
        for action in sequence {
            if sim.private.terminated || sim.private.truncated {
                break;
            }
            sim.step(action);
        }
        results.push(json!({"index": index, "actions": sequence, "reward": sim.private.total_reward, "terminated": sim.private.terminated, "truncated": sim.private.truncated, "readout": sim.readout(), "nev_cursor": sim.events.len()}));
    }
    Ok(Json(
        json!({"rollout_id": id, "root_nev_cursor": session.events.len(), "results": results}),
    ))
}

async fn readout(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().unwrap();
    Ok(Json(guard.get(&id).ok_or(StatusCode::NOT_FOUND)?.readout()))
}

async fn event_log(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, StatusCode> {
    let guard = sessions.lock().unwrap();
    let session = guard.get(&id).ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(
        json!({"events": session.events, "legacy": session.legacy_strings(), "nev_cursor": session.events.len()}),
    ))
}

fn payload(id: &str, session: &RogueSession) -> Value {
    json!({"rollout_id": id, "readout": session.readout(), "reward": session.private.total_reward, "terminated": session.private.terminated, "truncated": session.private.truncated, "nev_cursor": session.events.len()})
}

fn default_task() -> Value {
    json!({"task_id": "manual", "seed": 1, "grid": ["                    ","  ------------      ","  |@...*....%|      ","  |....:.....|      ","  ------------      ","                    "], "rules": {"base": "modern_rogue_core", "overrides": {"max_steps": 40}}, "objective": "descend"})
}
