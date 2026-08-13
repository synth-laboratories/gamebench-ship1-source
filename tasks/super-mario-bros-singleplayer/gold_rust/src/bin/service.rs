use axum::extract::{Path, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, post};
use axum::{Json, Router};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use gamebench_platformer_gold::{Action, Env, Input, LevelId, ODYSSEUS_LEVELS};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

type Sessions = Arc<Mutex<HashMap<String, Env>>>;

#[derive(Deserialize)]
struct RolloutRequest {
    task: Option<Value>,
    seed: Option<u64>,
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

#[derive(Debug)]
struct ApiError(StatusCode, &'static str, String);

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (
            self.0,
            Json(json!({"error": {"code": self.1, "message": self.2}})),
        )
            .into_response()
    }
}

#[tokio::main]
async fn main() {
    let mut host = "127.0.0.1".to_string();
    let mut port = 8099_u16;
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
            _ => {}
        }
    }
    let sessions: Sessions = Arc::new(Mutex::new(HashMap::new()));
    let app = Router::new()
        .route("/health", get(health))
        .route("/info", get(info))
        .route("/run_scenario", post(run_scenario))
        .route("/rollout", post(run_scenario))
        .route("/rollouts", post(create_rollout))
        .route("/reset", post(create_rollout))
        .route("/rollouts/:id", delete(delete_rollout))
        .route("/rollouts/:id/step", post(step))
        .route("/rollouts/:id/checkpoint", post(checkpoint))
        .route("/rollouts/:id/restore", post(restore))
        .route("/rollouts/:id/simulate", post(simulate))
        .route("/rollouts/:id/readout", get(readout))
        .route("/rollouts/:id/state", get(readout))
        .route("/rollouts/:id/event_log", get(event_log))
        .route("/rollouts/:id/events", get(event_log))
        .route("/rollouts/:id/render.png", get(render_png))
        .route("/rollouts/:id/render.rgb", get(render_rgb))
        .with_state(sessions);
    let listener = tokio::net::TcpListener::bind(format!("{host}:{port}"))
        .await
        .expect("bind SMB research service");
    axum::serve(listener, app)
        .await
        .expect("serve SMB research service");
}

async fn health(State(sessions): State<Sessions>) -> Json<Value> {
    Json(json!({
        "ok": true,
        "lane": "rust",
        "env_family": "super-mario-bros-singleplayer",
        "catalog_levels": ODYSSEUS_LEVELS.len(),
        "sessions": sessions.lock().expect("session mutex").len()
    }))
}

async fn info() -> Json<Value> {
    Json(json!({
        "env_family": "super-mario-bros-singleplayer",
        "lane": "rust",
        "contract": "gamebench.platformer.v1",
        "capabilities": [
            "32_authored_levels", "fixed_point", "rgb", "semantic_events", "checkpoint",
            "restore", "batched_simulate", "route_progress", "terminal_semantics"
        ],
        "observation": {"width": 256, "height": 240, "channels": 3, "format": "rgb8"}
    }))
}

async fn run_scenario(Json(body): Json<Value>) -> Result<Json<Value>, ApiError> {
    let task = body.get("task").unwrap_or(&body);
    let mut env = reset_from_task(task, body.get("seed").and_then(Value::as_u64))?;
    let actions = task
        .get("actions")
        .or_else(|| body.get("actions"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut steps = Vec::new();
    for action in actions {
        if env.readout().terminal {
            break;
        }
        let step = env.step(parse_action(&action)?);
        steps.push(step);
    }
    Ok(Json(json!({
        "scenario_id": task.get("scenario_id").or_else(|| task.get("task_id")).cloned().unwrap_or_else(|| json!("manual")),
        "readout": env.readout(),
        "steps": steps,
        "events": env.events(),
        "legacy": env.legacy_strings()
    })))
}

async fn create_rollout(
    State(sessions): State<Sessions>,
    Json(body): Json<RolloutRequest>,
) -> Result<Json<Value>, ApiError> {
    let task = body.task.unwrap_or_else(|| json!({"level_id": "1-1"}));
    let env = reset_from_task(&task, body.seed)?;
    let id = Uuid::new_v4().to_string();
    let payload = payload(&id, &env);
    sessions.lock().expect("session mutex").insert(id, env);
    Ok(Json(payload))
}

async fn step(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<StepRequest>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = sessions.lock().expect("session mutex");
    let env = guard.get_mut(&id).ok_or_else(|| not_found("rollout"))?;
    let step = env.step(parse_action(&body.action)?);
    Ok(Json(
        json!({"rollout_id": id, "step": step, "readout": env.readout(), "nev_cursor": env.events().len()}),
    ))
}

async fn delete_rollout(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    if sessions
        .lock()
        .expect("session mutex")
        .remove(&id)
        .is_none()
    {
        return Err(not_found("rollout"));
    }
    Ok(Json(json!({"rollout_id": id, "deleted": true})))
}

async fn checkpoint(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = sessions.lock().expect("session mutex");
    let env = guard.get(&id).ok_or_else(|| not_found("rollout"))?;
    let blob = env
        .checkpoint_bytes()
        .map_err(|error| bad_request(error.to_string()))?;
    Ok(Json(json!({
        "rollout_id": id,
        "checkpoint_id": Uuid::new_v4().to_string(),
        "blob": BASE64.encode(&blob),
        "bytes": blob.len(),
        "nev_cursor": env.events().len(),
        "readout": env.readout()
    })))
}

async fn restore(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<RestoreRequest>,
) -> Result<Json<Value>, ApiError> {
    let blob = BASE64
        .decode(body.blob.as_bytes())
        .map_err(|_| bad_request("blob is not base64".to_string()))?;
    let restored =
        Env::from_checkpoint_bytes(&blob).map_err(|error| bad_request(error.to_string()))?;
    let mut guard = sessions.lock().expect("session mutex");
    let env = guard.get_mut(&id).ok_or_else(|| not_found("rollout"))?;
    *env = restored;
    Ok(Json(json!({
        "rollout_id": id,
        "restore_report": {"bytes": blob.len(), "nev_events_restored": env.events().len()},
        "readout": env.readout()
    })))
}

async fn simulate(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
    Json(body): Json<SimulateRequest>,
) -> Result<Json<Value>, ApiError> {
    let guard = sessions.lock().expect("session mutex");
    let root = guard.get(&id).ok_or_else(|| not_found("rollout"))?;
    let blob = BASE64
        .decode(body.blob.as_bytes())
        .map_err(|_| bad_request("blob is not base64".to_string()))?;
    let mut results = Vec::new();
    for (index, sequence) in body.sequences.iter().enumerate() {
        let mut env =
            Env::from_checkpoint_bytes(&blob).map_err(|error| bad_request(error.to_string()))?;
        for action in sequence {
            if env.readout().terminal {
                break;
            }
            env.step(parse_action(action)?);
        }
        results.push(json!({
            "index": index,
            "actions": sequence,
            "readout": env.readout(),
            "events": env.events(),
            "nev_cursor": env.events().len()
        }));
    }
    Ok(Json(
        json!({"rollout_id": id, "root_nev_cursor": root.events().len(), "results": results}),
    ))
}

async fn readout(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = sessions.lock().expect("session mutex");
    Ok(Json(
        serde_json::to_value(
            guard
                .get(&id)
                .ok_or_else(|| not_found("rollout"))?
                .readout(),
        )
        .expect("readout JSON"),
    ))
}

async fn event_log(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = sessions.lock().expect("session mutex");
    let env = guard.get(&id).ok_or_else(|| not_found("rollout"))?;
    Ok(Json(
        json!({"rollout_id": id, "events": env.events(), "legacy": env.legacy_strings(), "nev_cursor": env.events().len()}),
    ))
}

async fn render_png(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Response, ApiError> {
    let guard = sessions.lock().expect("session mutex");
    let env = guard.get(&id).ok_or_else(|| not_found("rollout"))?;
    let rgb = env.render_rgb();
    let mut bytes = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut bytes, 256, 240);
        encoder.set_color(png::ColorType::Rgb);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder
            .write_header()
            .map_err(|e| bad_request(e.to_string()))?;
        writer
            .write_image_data(&rgb)
            .map_err(|e| bad_request(e.to_string()))?;
    }
    Ok(([(header::CONTENT_TYPE, "image/png")], bytes).into_response())
}

async fn render_rgb(
    State(sessions): State<Sessions>,
    Path(id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = sessions.lock().expect("session mutex");
    let env = guard.get(&id).ok_or_else(|| not_found("rollout"))?;
    let rgb = env.render_rgb();
    Ok(Json(
        json!({"width": 256, "height": 240, "format": "rgb8", "data": BASE64.encode(rgb)}),
    ))
}

fn payload(id: &str, env: &Env) -> Value {
    json!({
        "rollout_id": id,
        "readout": env.readout(),
        "reward": 0,
        "terminated": env.readout().terminal,
        "truncated": false,
        "nev_cursor": env.events().len()
    })
}

fn reset_from_task(task: &Value, seed: Option<u64>) -> Result<Env, ApiError> {
    let level = task
        .get("level_id")
        .or_else(|| task.get("scenario_id"))
        .and_then(Value::as_str)
        .and_then(LevelId::parse)
        .or_else(|| {
            let object = task.get("level")?;
            Some(LevelId::new(
                object.get("world")?.as_u64()? as u8,
                object.get("level")?.as_u64()? as u8,
            ))
        })
        .unwrap_or(ODYSSEUS_LEVELS[0]);
    Env::reset(level, seed.unwrap_or(0)).map_err(|error| bad_request(error.to_string()))
}

fn parse_action(value: &Value) -> Result<Input, ApiError> {
    if let Some(name) = value.as_str() {
        return Action::parse(name)
            .map(Into::into)
            .ok_or_else(|| bad_request("unsupported action".to_string()));
    }
    if let Some(nested) = value.get("action") {
        return parse_action(nested);
    }
    serde_json::from_value::<Input>(value.clone())
        .map_err(|_| bad_request("action must be a discrete name or input object".to_string()))
}

fn not_found(resource: &'static str) -> ApiError {
    ApiError(
        StatusCode::NOT_FOUND,
        "not_found",
        format!("{resource} not found"),
    )
}

fn bad_request(message: String) -> ApiError {
    ApiError(StatusCode::BAD_REQUEST, "bad_request", message)
}
