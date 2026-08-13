use axum::extract::{Path, Query, State, WebSocketUpgrade};
use axum::extract::ws::{Message, WebSocket};
use axum::http::{header, StatusCode};
use axum::response::{sse::{Event, KeepAlive, Sse}, IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use craftax_gamebench_gold::render::{
    encode_gif_via_ffmpeg, encode_png_rgb, frame_sha256, render_rgb_frame_from_world,
    RenderMode, RgbFrame, DEFAULT_RENDER_TILE_SIZE,
};
use craftax_gamebench_gold::{run_entry, CraftaxRustSession};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;
use std::convert::Infallible;
use tokio::sync::broadcast;
use tokio_stream::{wrappers::BroadcastStream, StreamExt};
use tower_http::cors::{Any, CorsLayer};
use uuid::Uuid;

#[derive(Clone, Copy)]
struct ReplaySettings {
    enabled: bool,
}

#[derive(Clone)]
struct AppState {
    sessions: Arc<Mutex<HashMap<String, RolloutSession>>>,
    telemetry: Arc<Mutex<HashMap<String, broadcast::Sender<Value>>>>,
    telemetry_history: Arc<Mutex<HashMap<String, Vec<Value>>>>,
    replay: ReplaySettings,
}

const DEFAULT_TASK: &str = r#"{
  "schema": "gamebench.task.craftax.v1",
  "task_id": "manual",
  "scenario_id": "manual",
  "world": {"use_default": "craftax_default"},
  "rules": {"base": "symbolic_no_homeostasis"},
  "readouts": {"profile": "symbolic_compact"}
}"#;

struct RolloutSession {
    engine: CraftaxRustSession,
    started_at: Instant,
    checkpoints: HashMap<String, Vec<u8>>,
    frames: HashMap<u64, Vec<u8>>,
    gif_frames: HashMap<u64, RgbFrame>,
    /// GELO/GEPA terminal record when an optimizer rollout has finished.
    terminal_record: Option<Value>,
    status: String,
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

#[derive(Deserialize)]
struct RolloutRequest {
    task: Option<Value>,
    seed: Option<i64>,
    telemetry: Option<Value>,
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

#[derive(Deserialize)]
struct TaskInfoQuery {
    task_id: Option<String>,
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
        telemetry: Arc::new(Mutex::new(HashMap::new())),
        telemetry_history: Arc::new(Mutex::new(HashMap::new())),
        replay: ReplaySettings {
            enabled: replay_enabled,
        },
    };
    let app = Router::new()
        .route("/health", get(health))
        .route("/info", get(info))
        .route("/task_catalog", get(task_catalog))
        .route("/task_info", get(task_info))
        .route("/run_scenario", post(run_scenario_route))
        // GELO/GEPA optimizers post GELO-shaped bodies to /rollout; GameBench
        // scenario runners also use /rollout with `{task:...}`. Dispatch both.
        .route("/rollout", post(optimizer_or_scenario_rollout))
        .route("/rollouts", post(create_rollout))
        .route("/reset", post(create_rollout))
        .route("/rollouts/:rollout_id", get(get_rollout_record).delete(delete_rollout))
        .route("/rollouts/:rollout_id/step", post(step))
        .route("/rollouts/:rollout_id/readout", get(readout))
        .route("/rollouts/:rollout_id/state", get(rollout_state))
        .route("/rollouts/:rollout_id/terminate", post(terminate_rollout))
        .route("/dataset", get(gepa_dataset))
        .route("/dataset/rows", post(gepa_dataset_rows))
        .route("/program", get(gepa_program))
        .route("/metadata", get(optimizer_metadata))
        .route("/compatibility", get(compatibility))
        .route("/rollouts/:rollout_id/event_log", get(event_log))
        .route("/rollouts/:rollout_id/events", get(event_log))
        .route("/rollouts/:rollout_id/stream", get(rollout_stream))
        .route("/rollouts/:rollout_id/ws", get(rollout_ws))
        .route("/rollouts/:rollout_id/checkpoint", post(checkpoint))
        .route("/rollouts/:rollout_id/checkpoints", post(checkpoint))
        .route("/rollouts/:rollout_id/resume", post(resume_optimizer_rollout))
        .route("/rollouts/:rollout_id/restore", post(restore))
        .route("/rollouts/:rollout_id/simulate", post(simulate))
        .route("/rollouts/:rollout_id/render.svg", get(render_svg))
        .route("/rollouts/:rollout_id/render.png", get(render_png_route))
        .route("/rollouts/:rollout_id/frames/manifest", get(frame_manifest_route))
        .route("/rollouts/:rollout_id/frames/:step", get(frame_png_route))
        .route("/rollouts/:rollout_id/replay.gif", get(replay_gif_route))
        .layer(CorsLayer::new().allow_origin(Any).allow_methods(Any).allow_headers(Any))
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
        "task_catalog",
        "task_info",
        "rollout_stream_sse",
        "rollout_stream_ws",
    ];
    Json(json!({
        "env_family": "craftax-singleplayer",
        "lane": "rust",
        "capabilities": capabilities,
        "streaming": {
            "schema": "synth.rollout.event.v1",
            "transports": ["sse", "websocket"],
            "supports_resume": false,
            "frame_formats": ["png"]
        },
        "replay_enabled": app.replay.enabled,
        "action_names": craftax_gamebench_gold::action_names(),
        "glyph_legend": craftax_gamebench_gold::glyph_legend(),
    }))
}

async fn task_catalog() -> Json<Value> {
    Json(task_catalog_value())
}

fn task_catalog_value() -> Value {
	let instances = (1001_i64..=1032)
		.map(|seed| ("train", seed))
		.chain((2001_i64..=2008).map(|seed| ("test", seed)))
		.map(|(split, seed)| json!({
			"task_instance_id": format!("craftax:{split}:{seed}"),
			"task_id": "manual",
			"split": split,
			"tags": ["craftax", split, "craftax_default"],
			"metadata": {
				"seed": seed,
				"world_profile": "craftax_default",
				"rules": "symbolic_no_homeostasis",
				"readout_profile": "symbolic_compact"
			},
			"rollout": {
				"seed": seed,
				"task": {
					"schema": "gamebench.task.craftax.v1",
					"task_id": "manual",
					"scenario_id": format!("seed-{seed}"),
					"world": {"use_default": "craftax_default", "seed": seed},
					"rules": {"base": "symbolic_no_homeostasis"},
					"readouts": {"profile": "symbolic_compact"}
				}
			}
		}))
		.collect::<Vec<_>>();
	json!({
        "schema": "synth.container.task_catalog.v1",
        "tasks": [{
            "task_id": "manual",
            "name": "Craftax single-player",
            "description": "Explore, gather, craft, fight, and survive in a symbolic Craftax world.",
            "family": "craftax-singleplayer",
            "scenario_id": "manual",
            "default": true
        }],
		"instances": instances,
		"metadata": {
			"instance_count": 40,
			"seed_policy": "curated_fixed_v1",
			"filterable_fields": ["split", "metadata.seed", "metadata.world_profile", "metadata.rules"]
		}
	})
}

async fn task_info(Query(query): Query<TaskInfoQuery>) -> Result<Json<Value>, ApiError> {
    let task_id = query.task_id.as_deref().unwrap_or("manual");
    if task_id != "manual" {
        return Err(ApiError {
            status: StatusCode::NOT_FOUND,
            code: "task_not_found",
            message: format!("unknown task_id: {task_id}"),
        });
    }
    Ok(Json(json!({
        "schema": "synth.container.task_info.v1",
        "task": {
            "task_id": "manual",
            "name": "Craftax single-player",
            "description": "Explore, gather resources, craft equipment, fight creatures, and survive in a symbolic Craftax world.",
            "family": "craftax-singleplayer",
            "scenario_id": "manual"
        },
        "objective": "Select valid actions that make progress through the Craftax technology tree while keeping the player alive.",
        "output_space": {
            "kind": "interactive_action",
            "contract": "Choose exactly one action name per environment step.",
            "valid_actions": craftax_gamebench_gold::action_names()
        },
        "metrics": {
            "primary": "achievements_unlocked",
            "secondary": ["survival", "inventory_progress", "depth_reached"]
        },
        "constraints": {
            "state_observation": "symbolic",
            "default_world": "craftax_default",
            "rules": "symbolic_no_homeostasis"
        },
        "metadata": {
            "readout_profile": "symbolic_compact",
            "supports_seed": true,
            "supports_checkpointing": true
        }
    })))
}

async fn run_scenario_route(Json(body): Json<ScenarioRequest>) -> Result<Json<Value>, ApiError> {
    Ok(Json(run_entry(&body.task).map_err(bad_request)?))
}

fn is_optimizer_rollout_body(body: &Value) -> bool {
    body.get("arms").is_some()
        || body.get("candidate").is_some()
        || body.get("schema_version")
            .and_then(Value::as_str)
            .is_some_and(|s| s.contains("goex") || s.contains("gepa") || s.contains("rollout_request"))
        || body.get("submission_mode").is_some()
        || body.get("policy").is_some()
}

async fn optimizer_or_scenario_rollout(
    State(app): State<AppState>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    if is_optimizer_rollout_body(&body) {
        return run_optimizer_rollout(app, body).await;
    }
    if let Some(task) = body.get("task") {
        return Ok(Json(run_entry(task).map_err(bad_request)?));
    }
    // Fall through to interactive create_rollout shape.
    let seed = body.get("seed").and_then(Value::as_i64);
    let task = body.get("task").cloned().unwrap_or_else(default_task);
    create_rollout_from_parts(app, task, seed, body.get("telemetry").cloned()).await
}

async fn create_rollout(
    State(app): State<AppState>,
    Json(body): Json<RolloutRequest>,
) -> Result<Json<Value>, ApiError> {
    let task = body.task.unwrap_or_else(default_task);
    create_rollout_from_parts(app, task, body.seed, body.telemetry).await
}

async fn create_rollout_from_parts(
    app: AppState,
    task: Value,
    seed: Option<i64>,
    telemetry: Option<Value>,
) -> Result<Json<Value>, ApiError> {
    let engine = CraftaxRustSession::reset_from_task(&task, seed).map_err(bad_request)?;
    let rollout_id = Uuid::new_v4().to_string();
    let mut session = RolloutSession {
        engine,
        started_at: Instant::now(),
        checkpoints: HashMap::new(),
        frames: HashMap::new(),
        gif_frames: HashMap::new(),
        terminal_record: None,
        status: "running".into(),
    };
    capture_frame_if_enabled(&mut session, app.replay, false);
    let mut payload = rollout_payload(&rollout_id, &session);
    if telemetry
        .as_ref()
        .and_then(|value| value.get("enabled"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        capture_frame_if_enabled(&mut session, app.replay, true);
        let (sender, _) = broadcast::channel(256);
        app.telemetry.lock().unwrap().insert(rollout_id.clone(), sender.clone());
        payload["stream"] = json!({
            "schema": "synth.rollout.stream.v1",
            "sse_url": format!("/rollouts/{rollout_id}/stream"),
            "websocket_url": format!("/rollouts/{rollout_id}/ws"),
            "cursor": 0
        });
        let event = rollout_event(&rollout_id, &payload);
        app.telemetry_history.lock().unwrap().insert(rollout_id.clone(), vec![event.clone()]);
        let _ = sender.send(event);
    }
    app.sessions.lock().unwrap().insert(rollout_id, session);
    Ok(Json(payload))
}

async fn run_optimizer_rollout(app: AppState, body: Value) -> Result<Json<Value>, ApiError> {
    let seed = body
        .pointer("/env/seed")
        .or_else(|| body.get("seed"))
        .and_then(Value::as_i64)
        .unwrap_or(101);
    let policy_cfg = body
        .pointer("/policy/config")
        .cloned()
        .unwrap_or_else(|| json!({}));
    let max_steps = body
        .pointer("/env/config/max_steps")
        .or_else(|| policy_cfg.get("max_steps"))
        .or_else(|| body.get("segment_steps"))
        .and_then(Value::as_u64)
        .unwrap_or(32)
        // The reference world runs to 5000 steps. A 512 ceiling silently
        // truncated every real-world run; the default stays small so no
        // existing caller changes behaviour by accident.
        .clamp(1, 5000) as usize;
    let max_llm_turns = policy_cfg
        .get("max_llm_turns")
        .or_else(|| body.pointer("/go_ex/max_llm_turns"))
        .and_then(Value::as_u64)
        .unwrap_or(16)
        .clamp(1, 128) as usize;
    let use_lm = policy_cfg
        .get("use_lm")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let rollout_id = body
        .get("rollout_id")
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    // The world used to be hardcoded to `policy_dev_small` here: a 16x16, 3-level
    // board with 16% of vanilla tree density and a 120-step budget. Every
    // optimizer, GEPA, GELO and SFT rollout went through this function, so all
    // of them scored a toy arena and reported it as a Craftax result — the
    // early tech tree (wood -> table -> pickaxe -> stone) is not reachable
    // there. The world is now caller-configurable and defaults to the reference
    // world; a caller that wants the fast dev board has to ask for it by name.
    let mut world = body
        .pointer("/env/config/world")
        .or_else(|| body.pointer("/env/world"))
        .or_else(|| body.pointer("/task/world"))
        .or_else(|| policy_cfg.get("world"))
        .cloned()
        .unwrap_or_else(|| json!({"use_default": "craftax_default"}));
    if let Some(obj) = world.as_object_mut() {
        obj.insert("seed".into(), json!(seed));
    }
    let world_preset = world
        .get("use_default")
        .and_then(Value::as_str)
        .unwrap_or("inline")
        .to_string();
    // A score is only comparable to a real Craftax run when the board is the
    // reference board and no resource density has been scaled.
    let scaled_resources: Vec<String> = world
        .get("densities")
        .and_then(Value::as_object)
        .map(|o| o.keys().cloned().collect())
        .unwrap_or_default();
    let is_reference_world = world_preset == "craftax_default" && scaled_resources.is_empty();
    let mut task = default_task();
    if let Some(obj) = task.as_object_mut() {
        obj.insert("world".into(), world.clone());
        obj.insert("scenario_id".into(), json!(format!("seed-{seed}")));
    }
    let mut engine = CraftaxRustSession::reset_from_task(&task, Some(seed)).map_err(bad_request)?;
    let actions = craftax_gamebench_gold::action_names();
    let valid: Vec<String> = actions.iter().map(|s| (*s).to_string()).collect();

    let system_prompt = body
        .pointer("/policy/config/system_prompt")
        .or_else(|| body.pointer("/policy/config/react_system_prompt"))
        .or_else(|| body.pointer("/candidate/react_system_prompt"))
        .or_else(|| body.pointer("/arms/0/react_system_prompt"))
        .and_then(Value::as_str)
        .unwrap_or(
            "You are playing GameBench Craftax. Reply with JSON only, for example \
             {\"actions\":[\"do\",\"right\",\"do\"]}. Prioritize survival, wood, stone, tools, \
             and achievement progress.",
        )
        .to_string();
    let provider = body
        .pointer("/policy/config/provider")
        .or_else(|| body.pointer("/policy/provider"))
        .and_then(Value::as_str)
        .unwrap_or("groq")
        .to_ascii_lowercase();
    let model = body
        .pointer("/policy/config/model")
        .or_else(|| body.pointer("/policy/model"))
        .and_then(Value::as_str)
        .unwrap_or(match provider.as_str() {
            "deepseek" => "deepseek-v4-flash",
            "openai" => "gpt-4.1-mini",
            "gemini" => "gemini-3.1-flash-lite",
            _ => "openai/gpt-oss-120b",
        })
        .to_string();
    let inference_url = body
        .pointer("/policy/config/inference_url")
        .or_else(|| body.pointer("/policy/inference_url"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| default_inference_url(&provider));
    // Reasoning effort is part of the policy identity — "Luna medium" is a
    // different policy from "Luna high" — so it has to be configurable and
    // recorded, not inferred from the provider name.
    let reasoning_effort = body
        .pointer("/policy/config/reasoning_effort")
        .or_else(|| body.pointer("/policy/reasoning_effort"))
        .and_then(Value::as_str)
        .map(str::to_string);
    let api_key_env = body
        .pointer("/policy/config/api_key_env")
        .or_else(|| body.pointer("/policy/api_key_env"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| default_api_key_env(&provider));
    let api_key = std::env::var(&api_key_env)
        .ok()
        .filter(|s| !s.trim().is_empty())
        .or_else(|| std::env::var("GROQ_API_KEY").ok().filter(|s| !s.trim().is_empty()))
        .or_else(|| std::env::var("DEEPSEEK_API_KEY").ok().filter(|s| !s.trim().is_empty()))
        .or_else(|| std::env::var("OPENAI_API_KEY").ok().filter(|s| !s.trim().is_empty()))
        .or_else(|| std::env::var("GEMINI_API_KEY").ok().filter(|s| !s.trim().is_empty()))
        .unwrap_or_default();
    let temperature = policy_cfg
        .get("temperature")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let max_tokens = body
        .pointer("/policy/config/max_tokens")
        .or_else(|| body.pointer("/policy/max_tokens"))
        .and_then(Value::as_u64)
        .unwrap_or(512)
        .clamp(64, 4096) as u32;
    let min_actions = policy_cfg
        .get("min_actions_per_call")
        .and_then(Value::as_u64)
        .unwrap_or(3)
        .clamp(1, 32) as usize;
    let max_actions = policy_cfg
        .get("max_actions_per_call")
        .and_then(Value::as_u64)
        .unwrap_or(12)
        .clamp(1, 32) as usize;
    let objective = "Make measurable Craftax achievement progress while staying alive.".to_string();

    // ReAct shape. `conversation` is the classic loop: an accumulating
    // system/user/assistant-tool_call/tool-result transcript that is compacted
    // by a model-written summary when the context crosses a threshold.
    // `stateless` is the older single-turn prompt kept for A/B comparison — it
    // carries only a 16-action tail window and forgets everything else.
    let react_mode = policy_cfg
        .get("react_mode")
        .and_then(Value::as_str)
        .unwrap_or("conversation")
        .to_string();
    let context_token_budget = policy_cfg
        .get("context_token_budget")
        .and_then(Value::as_u64)
        .unwrap_or(16000)
        .clamp(2000, 400_000) as u64;
    let compact_at = policy_cfg
        .get("compact_at")
        .and_then(Value::as_f64)
        .unwrap_or(0.7)
        .clamp(0.1, 0.95);
    let compact_threshold = (context_token_budget as f64 * compact_at) as u64;
    let keep_recent_messages = policy_cfg
        .get("keep_recent_messages")
        .and_then(Value::as_u64)
        .unwrap_or(8)
        .clamp(2, 64) as usize;
    // Optional durable scratchpad. The compaction summary is model-written and
    // lossy; a scratchpad is agent-authored and pinned, so a plan survives
    // verbatim no matter how many times the middle is summarized away.
    let scratchpad_enabled = policy_cfg
        .get("enable_scratchpad")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let mut scratchpad = String::new();
    let mut scratchpad_writes: usize = 0;
    let mut compactions: Vec<Value> = Vec::new();
    let mut last_prompt_tokens: u64 = 0;

    let mut action_history: Vec<String> = Vec::new();
    let mut turns: Vec<Value> = Vec::new();
    let mut usage_total = json!({"prompt_tokens": 0u64, "completion_tokens": 0u64, "total_tokens": 0u64});
    let mut llm_calls: usize = 0;
    let mut policy_label = "craftax_react_lm".to_string();

    if use_lm {
        if api_key.is_empty() {
            return Err(ApiError {
                status: StatusCode::BAD_REQUEST,
                code: "missing_api_key",
                message: format!(
                    "Craftax LM rollout requires {api_key_env} (provider={provider})"
                ),
            });
        }
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(120))
            .build()
            .map_err(|err| ApiError {
                status: StatusCode::INTERNAL_SERVER_ERROR,
                code: "http_client",
                message: err.to_string(),
            })?;
        if react_mode == "conversation" {
            // ── Classic ReAct: one accumulating transcript ──────────────────
            // system + user(task) + assistant(tool_calls) + tool(result) + ...
            // The environment is a tool the model calls; observations come back
            // as tool results. Nothing is re-templated per turn, so the model
            // sees the whole episode until compaction summarizes the middle.
            let tools = json!([{
                "type": "function",
                "function": {
                    "name": "interact",
                    "description": "Act in the world: execute Craftax actions in order, then return the resulting observation. Plan a short coherent batch.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {"type": "string", "enum": valid.clone()},
                                "description": "Actions to execute sequentially."
                            }
                        },
                        "required": ["actions"],
                        "additionalProperties": false
                    }
                }
            }]);
            // Compaction is infrastructure, not a policy decision: it fires
            // automatically at a fixed context threshold. Exposing it as a tool
            // makes context management part of what is under test, which is a
            // different experiment.
            let tools = if scratchpad_enabled {
                let mut t = tools.as_array().cloned().unwrap_or_default();
                t.push(json!({
                    "type": "function",
                    "function": {
                        "name": "scratchpad",
                        "description": "Record or revise your long-term plan and map knowledge. This text is pinned to your context and survives context compaction verbatim, so put anything here you must not forget: where resources are, what the current goal is, what has already been tried. Rewrite it in full each time.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string", "description": "The complete new scratchpad contents, replacing whatever was there."}
                            },
                            "required": ["content"],
                            "additionalProperties": false
                        }
                    }
                }));
                json!(t)
            } else {
                tools
            };

            let opening = format!(
                "{objective}\n\nYou are playing Craftax. Call the `interact` tool to act; you will get the new observation back as the tool result. Plan {min_actions}-{max_actions} coherent actions per call.\n\nvalid_actions={}\n\nInitial observation:\n{}",
                valid.join(", "),
                engine
                    .readout()
                    .get("observation_text")
                    .and_then(Value::as_str)
                    .unwrap_or("")
            );
            let mut messages: Vec<Value> = vec![
                json!({"role": "system", "content": system_prompt}),
                json!({"role": "user", "content": opening}),
            ];
            // Index 2 is the pinned scratchpad when enabled. Compaction keeps
            // the head intact, so this slot is never summarized away.
            let head_len = if scratchpad_enabled { 3 } else { 2 };
            if scratchpad_enabled {
                messages.push(json!({
                    "role": "user",
                    "content": "[scratchpad] empty — call the `scratchpad` tool to record your plan."
                }));
            }

            while !engine.is_done()
                && (engine
                    .private
                    .get("step_index")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as usize)
                    < max_steps
                && llm_calls < max_llm_turns
            {
                let steps_done = engine
                    .private
                    .get("step_index")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as usize;
                let steps_remaining = max_steps.saturating_sub(steps_done);
                let llm_remaining = max_llm_turns.saturating_sub(llm_calls);

                let mut request_body = json!({
                    "model": model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                });
                if let Some(effort) = reasoning_effort.as_deref() {
                    request_body.as_object_mut().unwrap()
                        .insert("reasoning_effort".into(), json!(effort));
                }
                let response = client
                    .post(&inference_url)
                    .header("Authorization", format!("Bearer {api_key}"))
                    .header("Content-Type", "application/json")
                    .json(&request_body)
                    .send()
                    .await
                    .map_err(|err| ApiError {
                        status: StatusCode::BAD_GATEWAY,
                        code: "policy_http",
                        message: format!("policy LM request failed: {err}"),
                    })?;
                let status = response.status();
                let payload: Value = response.json().await.map_err(|err| ApiError {
                    status: StatusCode::BAD_GATEWAY,
                    code: "policy_http",
                    message: format!("policy LM response decode failed: {err}"),
                })?;
                if !status.is_success() {
                    return Err(ApiError {
                        status: StatusCode::BAD_GATEWAY,
                        code: "policy_http",
                        message: format!("policy LM HTTP {}: {}", status.as_u16(), payload),
                    });
                }
                accumulate_usage(&mut usage_total, payload.get("usage"));
                last_prompt_tokens = payload
                    .pointer("/usage/prompt_tokens")
                    .and_then(Value::as_u64)
                    .unwrap_or(last_prompt_tokens);

                let msg = payload.pointer("/choices/0/message").cloned().unwrap_or(json!({}));
                let assistant_text = extract_assistant_text(&payload);
                let tool_calls = msg.get("tool_calls").and_then(Value::as_array).cloned();

                // Keep the assistant turn verbatim so tool_call_ids stay valid.
                messages.push(msg.clone());

                let mut executed: Vec<String> = Vec::new();
                let mut planned: Vec<String> = Vec::new();
                let used_tool_call = tool_calls.as_ref().is_some_and(|c| !c.is_empty());
                match tool_calls {
                    Some(calls) if !calls.is_empty() => {
                        for call in calls {
                            let args_raw = call
                                .pointer("/function/arguments")
                                .and_then(Value::as_str)
                                .unwrap_or("{}");
                            let fn_name = call
                                .pointer("/function/name")
                                .and_then(Value::as_str)
                                .unwrap_or("step");
                            if fn_name == "scratchpad" {
                                let content = serde_json::from_str::<Value>(args_raw)
                                    .ok()
                                    .and_then(|v| v.get("content").and_then(Value::as_str).map(str::to_string))
                                    .unwrap_or_default();
                                if !content.trim().is_empty() {
                                    scratchpad = content;
                                    scratchpad_writes += 1;
                                    if messages.len() > 2 {
                                        messages[2] = json!({
                                            "role": "user",
                                            "content": format!("[scratchpad — pinned, survives compaction]\n{scratchpad}")
                                        });
                                    }
                                }
                                messages.push(json!({
                                    "role": "tool",
                                    "tool_call_id": call.get("id").and_then(Value::as_str).unwrap_or(""),
                                    "content": format!("scratchpad saved ({} chars). It is pinned to your context.", scratchpad.len())
                                }));
                                continue;
                            }
                            let batch_cap = max_actions.min(steps_remaining).max(1);
                            let batch = parse_actions_batch(args_raw, &valid, batch_cap);
                            planned.extend(batch.iter().cloned());
                            for action in &batch {
                                if engine.is_done() {
                                    break;
                                }
                                let now = engine.private.get("step_index")
                                    .and_then(Value::as_u64).unwrap_or(0) as usize;
                                if now >= max_steps {
                                    break;
                                }
                                engine.step(&json!(action)).map_err(|err| ApiError {
                                    status: StatusCode::BAD_REQUEST,
                                    code: "step_failed",
                                    message: err.to_string(),
                                })?;
                                executed.push(action.clone());
                                action_history.push(action.clone());
                            }
                            let readout = engine.readout();
                            let obs = readout.get("observation_text")
                                .and_then(Value::as_str).unwrap_or("");
                            let result = format!(
                                "executed={}\nsteps_remaining={}\nllm_calls_remaining={}\n\n{}",
                                serde_json::to_string(&executed).unwrap_or_else(|_| "[]".into()),
                                max_steps.saturating_sub(
                                    engine.private.get("step_index")
                                        .and_then(Value::as_u64).unwrap_or(0) as usize),
                                llm_remaining.saturating_sub(1),
                                obs
                            );
                            messages.push(json!({
                                "role": "tool",
                                "tool_call_id": call.get("id").and_then(Value::as_str).unwrap_or(""),
                                "content": result
                            }));
                        }
                    }
                    _ => {
                        // No tool call. Accept a plain JSON action batch so a
                        // model that ignores the tool schema still advances,
                        // and tell it plainly what it should have done.
                        let batch_cap = max_actions.min(steps_remaining).max(1);
                        let batch = parse_actions_batch(&assistant_text, &valid, batch_cap);
                        planned.extend(batch.iter().cloned());
                        for action in &batch {
                            if engine.is_done() {
                                break;
                            }
                            let now = engine.private.get("step_index")
                                .and_then(Value::as_u64).unwrap_or(0) as usize;
                            if now >= max_steps {
                                break;
                            }
                            engine.step(&json!(action)).map_err(|err| ApiError {
                                status: StatusCode::BAD_REQUEST,
                                code: "step_failed",
                                message: err.to_string(),
                            })?;
                            executed.push(action.clone());
                            action_history.push(action.clone());
                        }
                        let readout = engine.readout();
                        let obs = readout.get("observation_text")
                            .and_then(Value::as_str).unwrap_or("");
                        messages.push(json!({
                            "role": "user",
                            "content": format!(
                                "Use the `interact` tool next time. executed={}\n\n{}",
                                serde_json::to_string(&executed).unwrap_or_else(|_| "[]".into()),
                                obs
                            )
                        }));
                    }
                }

                llm_calls += 1;
                turns.push(json!({
                    "llm_call": llm_calls,
                    "assistant": assistant_text,
                    "actions": executed,
                    "planned": planned,
                    "prompt_tokens": last_prompt_tokens,
                    "message_count": messages.len(),
                    // Distinguishes a real tool call from the text fallback.
                    // Without it you cannot tell whether the loop is actually
                    // running on tool calls or quietly limping on JSON parsing.
                    "used_tool_call": used_tool_call,
                }));

                // ── Compaction ─────────────────────────────────────────────
                // Fixed context window: compact when the real prompt token
                // count crosses the threshold. Not agent-decided.
                if last_prompt_tokens > compact_threshold
                    && messages.len() > keep_recent_messages + head_len
                {
                    // Never split an assistant(tool_calls)/tool(result) pair:
                    // an orphaned tool message is a hard API error.
                    let mut start = messages.len().saturating_sub(keep_recent_messages);
                    while start > head_len
                        && messages[start].get("role").and_then(Value::as_str) == Some("tool")
                    {
                        start -= 1;
                    }
                    if start > head_len {
                        let middle: Vec<Value> = messages[head_len..start].to_vec();
                        let transcript = serde_json::to_string(&middle)
                            .unwrap_or_else(|_| "[]".into());
                        let summary_req = json!({
                            "model": model,
                            "messages": [
                                {"role": "system", "content": "You compact an agent's episode transcript. Write a dense factual brief the agent will rely on as its only memory of these turns."},
                                {"role": "user", "content": format!(
                                    "Summarize this Craftax episode segment for the agent that will keep playing. Cover: terrain and resources seen and roughly where relative to the player; inventory and achievements gained; what was attempted and failed; the current goal. Be concrete and brief. No preamble.\n\n{transcript}"
                                )}
                            ],
                            "temperature": 0.0,
                            "max_tokens": 700,
                        });
                        let summary_resp = client
                            .post(&inference_url)
                            .header("Authorization", format!("Bearer {api_key}"))
                            .header("Content-Type", "application/json")
                            .json(&summary_req)
                            .send()
                            .await;
                        if let Ok(resp) = summary_resp {
                            if let Ok(sp) = resp.json::<Value>().await {
                                accumulate_usage(&mut usage_total, sp.get("usage"));
                                let summary = extract_assistant_text(&sp);
                                if !summary.trim().is_empty() {
                                    let before = messages.len();
                                    let mut next: Vec<Value> = messages[0..head_len].to_vec();
                                    next.push(json!({
                                        "role": "user",
                                        "content": format!("[context compacted — the turns below are summarized, not verbatim]\n{summary}")
                                    }));
                                    next.extend_from_slice(&messages[start..]);
                                    messages = next;
                                    compactions.push(json!({
                                        "trigger": "fixed_threshold",
                                        "at_llm_call": llm_calls,
                                        "prompt_tokens_before": last_prompt_tokens,
                                        "messages_before": before,
                                        "messages_after": messages.len(),
                                        "summarized_messages": middle.len(),
                                        "summary_chars": summary.len(),
                                    }));
                                }
                            }
                        }
                    }
                }
            }
            policy_label = format!("craftax_react_conversation_{provider}");
        } else {
        while !engine.is_done()
            && (engine
                .private
                .get("step_index")
                .and_then(Value::as_u64)
                .unwrap_or(0) as usize)
                < max_steps
            && llm_calls < max_llm_turns
        {
            let steps_done = engine
                .private
                .get("step_index")
                .and_then(Value::as_u64)
                .unwrap_or(0) as usize;
            let steps_remaining = max_steps.saturating_sub(steps_done);
            let llm_remaining = max_llm_turns.saturating_sub(llm_calls);
            let batch_cap = max_actions.min(steps_remaining).max(1);
            let batch_floor = min_actions.min(batch_cap).max(1);
            let readout = engine.readout();
            let observation_text = readout
                .get("observation_text")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            // Keep the user prompt compact: full ASCII maps blow the gpt-oss
            // reasoning budget and leave `content` empty under max_tokens=512.
            let prompt = format!(
                "{objective}\n\n{observation_text}\n\nlast_actions={}\nsteps_remaining={steps_remaining}\nllm_calls_remaining={llm_remaining}\nvalid_actions={}\nPlan {batch_floor}-{batch_cap} valid actions to execute sequentially before the next observation.\nReply with JSON only, for example {{\"actions\":[\"do\",\"right\",\"do\",\"left\",\"do\"]}}.",
                serde_json::to_string(&action_history[action_history.len().saturating_sub(16)..])
                    .unwrap_or_else(|_| "[]".into()),
                valid.join(", ")
            );
            // Keep the exact decision context: a turn that reports only the
            // assistant text is not reconstructible, and an SFT example built
            // from it would train on a prompt the teacher never saw.
            let prompt_for_turn = prompt.clone();
            let observation_for_turn = observation_text.clone();
            let valid_for_turn = valid.clone();
            let mut request_body = json!({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            });
            if provider == "deepseek" {
                request_body
                    .as_object_mut()
                    .unwrap()
                    .insert("thinking".into(), json!({"type": "disabled"}));
            }
            if let Some(effort) = reasoning_effort.as_deref() {
                request_body
                    .as_object_mut()
                    .unwrap()
                    .insert("reasoning_effort".into(), json!(effort));
            }
            if provider == "groq" && model.contains("gpt-oss") {
                let obj = request_body.as_object_mut().unwrap();
                obj.insert("reasoning_effort".into(), json!("low"));
                // Prefer leaving room for the JSON answer after CoT.
                if max_tokens < 768 {
                    obj.insert("max_tokens".into(), json!(1024));
                }
            }
            let response = client
                .post(&inference_url)
                .header("Authorization", format!("Bearer {api_key}"))
                .header("Content-Type", "application/json")
                .json(&request_body)
                .send()
                .await
                .map_err(|err| ApiError {
                    status: StatusCode::BAD_GATEWAY,
                    code: "policy_http",
                    message: format!("policy LM request failed: {err}"),
                })?;
            let status = response.status();
            let payload: Value = response.json().await.map_err(|err| ApiError {
                status: StatusCode::BAD_GATEWAY,
                code: "policy_http",
                message: format!("policy LM response decode failed: {err}"),
            })?;
            if !status.is_success() {
                return Err(ApiError {
                    status: StatusCode::BAD_GATEWAY,
                    code: "policy_http",
                    message: format!(
                        "policy LM HTTP {}: {}",
                        status.as_u16(),
                        payload
                    ),
                });
            }
            let assistant = extract_assistant_text(&payload);
            accumulate_usage(&mut usage_total, payload.get("usage"));
            let planned = parse_actions_batch(&assistant, &valid, batch_cap);
            let mut executed = Vec::new();
            for action in &planned {
                if engine.is_done() {
                    break;
                }
                let steps_now = engine
                    .private
                    .get("step_index")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as usize;
                if steps_now >= max_steps {
                    break;
                }
                engine
                    .step(&json!(action))
                    .map_err(|err| ApiError {
                        status: StatusCode::BAD_REQUEST,
                        code: "step_failed",
                        message: err.to_string(),
                    })?;
                executed.push(action.clone());
                action_history.push(action.clone());
            }
            if executed.is_empty() {
                // Avoid infinite loops if the model returns nothing usable.
                let fallback = valid
                    .iter()
                    .find(|a| a.as_str() == "do" || a.as_str() == "noop")
                    .cloned()
                    .unwrap_or_else(|| valid[0].clone());
                if !engine.is_done() {
                    let _ = engine.step(&json!(fallback));
                    executed.push(fallback.clone());
                    action_history.push(fallback);
                }
            }
            llm_calls += 1;
            turns.push(json!({
                "llm_call": llm_calls,
                "assistant": assistant,
                "actions": executed,
                // The user message verbatim, so a training example can reuse
                // the teacher's exact inference representation.
                "prompt": prompt_for_turn,
                "system_prompt": system_prompt,
                "observation_text": observation_for_turn,
                "valid_actions": valid_for_turn,
            }));
        }
        policy_label = format!("craftax_react_{provider}");
        }
    } else {
        // Explicit smoke path when use_lm=false.
        let noop = valid
            .iter()
            .find(|name| name.eq_ignore_ascii_case("noop") || name.eq_ignore_ascii_case("do"))
            .cloned()
            .unwrap_or_else(|| valid.first().cloned().unwrap_or_else(|| "noop".into()));
        for _ in 0..max_steps {
            if engine.is_done() {
                break;
            }
            let _ = engine.step(&json!(noop));
        }
        policy_label = "craftax_heuristic_noop_smoke".into();
    }

    let reward = engine
        .private
        .get("total_reward")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let steps = engine
        .private
        .get("step_index")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let record = json!({
        "status": "completed",
        "rollout_id": rollout_id,
        "outcome_reward": reward,
        "reward": reward,
        "reward_info": {"outcome_reward": reward, "score": reward},
        "summary": {
            "outcome_reward": reward,
            "env_steps": steps,
            "seed": seed,
            "policy": policy_label,
            "policy_llm_turns": llm_calls,
            "model": model,
            "provider": provider,
            "reasoning_effort": reasoning_effort,
            // The ReAct loop is stateless: each call is [system, user] and the
            // only carried state is a 16-action tail window. Nothing is
            // summarized — everything older is dropped. The Python container
            // emits `agent.context_compacted` for this; the Rust path was
            // silent, so an episode could drop 150+ actions with no record.
            "context": if react_mode == "conversation" {
                json!({
                    "mode": "conversation",
                    "strategy": "summarize_and_keep_recent",
                    "conversation_carried": true,
                    "summarized": !compactions.is_empty(),
                    "compaction_count": compactions.len(),
                    "scratchpad_enabled": scratchpad_enabled,
                    "scratchpad_writes": scratchpad_writes,
                    "scratchpad_chars": scratchpad.len(),
                    "scratchpad_final": scratchpad,
                    "compactions": compactions,
                    "final_prompt_tokens": last_prompt_tokens,
                    "context_token_budget": context_token_budget,
                    "compact_threshold": compact_threshold,
                    "keep_recent_messages": keep_recent_messages,
                })
            } else {
                json!({
                    "mode": "stateless",
                    "strategy": "tail_window",
                    "conversation_carried": false,
                    "summarized": false,
                    "retained_actions": action_history.len().min(16),
                    "dropped_actions": action_history.len().saturating_sub(16),
                })
            },
            "world": {
                "preset": world_preset,
                "max_steps": max_steps,
                "scaled_resources": scaled_resources,
                "is_reference_world": is_reference_world,
                "requested": world,
            },
        },
        "usage": usage_total,
        "turns": turns,
        "events": [],
        "scheduled_checkpoints": [],
        "final_achievements": engine.private.get("achievements").cloned().unwrap_or(json!([])),
        "metadata": {
            "env": "craftax-singleplayer",
            "seed": seed,
            "task": "craftax",
            "backend": "gamebench_gold_rust",
            "optimizer_compatible": true
        },
        "terminated": true,
        "truncated": engine.private.get("truncated").and_then(Value::as_bool).unwrap_or(false),
    });
    let session = RolloutSession {
        engine,
        started_at: Instant::now(),
        checkpoints: HashMap::new(),
        frames: HashMap::new(),
        gif_frames: HashMap::new(),
        terminal_record: Some(record.clone()),
        status: "completed".into(),
    };
    app.sessions.lock().unwrap().insert(rollout_id.clone(), session);
    Ok(Json(record))
}

fn default_inference_url(provider: &str) -> String {
    match provider {
        "openrouter" => "https://openrouter.ai/api/v1/chat/completions".into(),
        "deepseek" => "https://api.deepseek.com/chat/completions".into(),
        "openai" => "https://api.openai.com/v1/chat/completions".into(),
        "gemini" => {
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions".into()
        }
        _ => "https://api.groq.com/openai/v1/chat/completions".into(),
    }
}

fn default_api_key_env(provider: &str) -> String {
    match provider {
        "openrouter" => "OPENROUTER_API_KEY".into(),
        "deepseek" => "DEEPSEEK_API_KEY".into(),
        "openai" => "OPENAI_API_KEY".into(),
        "gemini" => "GEMINI_API_KEY".into(),
        _ => "GROQ_API_KEY".into(),
    }
}

fn extract_assistant_text(payload: &Value) -> String {
    let message = payload.pointer("/choices/0/message");
    let content = message
        .and_then(|m| m.get("content"))
        .cloned()
        .unwrap_or(Value::Null);
    let mut text = match content {
        Value::String(s) => s,
        Value::Array(parts) => parts
            .iter()
            .filter_map(|part| part.get("text").and_then(Value::as_str))
            .collect::<Vec<_>>()
            .join(""),
        _ => String::new(),
    };
    if text.trim().is_empty() {
        // gpt-oss on Groq often puts the entire reply in `reasoning` when the
        // completion budget is consumed by chain-of-thought.
        if let Some(reasoning) = message
            .and_then(|m| m.get("reasoning").or_else(|| m.get("reasoning_content")))
            .and_then(Value::as_str)
        {
            text = reasoning.to_string();
        }
    }
    if let Some(json_blob) = extract_embedded_json_object(&text) {
        return json_blob;
    }
    text
}

fn extract_embedded_json_object(text: &str) -> Option<String> {
    let trimmed = text.trim();
    if trimmed.starts_with('{') && serde_json::from_str::<Value>(trimmed).is_ok() {
        return Some(trimmed.to_string());
    }
    // Prefer fenced ```json ... ``` blocks, then the last {...} slice.
    if let Some(start) = trimmed.find("```json") {
        let after = &trimmed[start + 7..];
        if let Some(end) = after.find("```") {
            let inner = after[..end].trim();
            if serde_json::from_str::<Value>(inner).is_ok() {
                return Some(inner.to_string());
            }
        }
    }
    let mut last = None;
    let bytes = trimmed.as_bytes();
    for i in 0..bytes.len() {
        if bytes[i] != b'{' {
            continue;
        }
        let mut depth = 0i32;
        for j in i..bytes.len() {
            match bytes[j] {
                b'{' => depth += 1,
                b'}' => {
                    depth -= 1;
                    if depth == 0 {
                        let slice = &trimmed[i..=j];
                        if let Ok(v) = serde_json::from_str::<Value>(slice) {
                            if v.get("actions").is_some() || v.get("action").is_some() {
                                last = Some(slice.to_string());
                            }
                        }
                        break;
                    }
                }
                _ => {}
            }
        }
    }
    last
}

fn accumulate_usage(total: &mut Value, usage: Option<&Value>) {
    let Some(usage) = usage.and_then(Value::as_object) else {
        return;
    };
    let Some(obj) = total.as_object_mut() else {
        return;
    };
    for key in ["prompt_tokens", "completion_tokens", "total_tokens"] {
        let add = usage.get(key).and_then(Value::as_u64).unwrap_or(0);
        let cur = obj.get(key).and_then(Value::as_u64).unwrap_or(0);
        obj.insert(key.into(), json!(cur + add));
    }
}

fn parse_actions_batch(raw: &str, valid: &[String], batch_cap: usize) -> Vec<String> {
    let text = raw.trim();
    let mut out = Vec::new();
    if let Ok(parsed) = serde_json::from_str::<Value>(text) {
        if let Some(arr) = parsed.get("actions").and_then(Value::as_array) {
            for item in arr {
                if let Some(action) = resolve_action(item.as_str().unwrap_or(""), valid) {
                    out.push(action);
                }
            }
        } else if let Some(arr) = parsed.as_array() {
            for item in arr {
                if let Some(action) = resolve_action(item.as_str().unwrap_or(""), valid) {
                    out.push(action);
                }
            }
        } else if let Some(single) = parsed
            .get("action")
            .or_else(|| parsed.get("move"))
            .or_else(|| parsed.get("command"))
            .and_then(Value::as_str)
        {
            if let Some(action) = resolve_action(single, valid) {
                out.push(action);
            }
        }
    }
    if out.is_empty() {
        // Last resort: prefer a productive default over scanning free-form CoT,
        // which casually mentions many valid action names.
        if let Some(action) = resolve_action("do", valid).or_else(|| valid.first().cloned()) {
            out.push(action);
        }
    }
    if out.len() > batch_cap {
        out.truncate(batch_cap);
    }
    out
}

fn resolve_action(raw: &str, valid: &[String]) -> Option<String> {
    let cleaned = raw
        .trim()
        .trim_matches(|c: char| c == '"' || c == '\'' || c == '`' || c == ',' || c == ';')
        .to_ascii_lowercase();
    if cleaned.is_empty() {
        return None;
    }
    valid
        .iter()
        .find(|a| a.eq_ignore_ascii_case(&cleaned))
        .cloned()
}

async fn get_rollout_record(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    if let Some(record) = &session.terminal_record {
        return Ok(Json(record.clone()));
    }
    let mut payload = rollout_payload(&rollout_id, session);
    payload["status"] = json!(&session.status);
    Ok(Json(payload))
}

async fn rollout_state(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let guard = app.sessions.lock().unwrap();
    let session = guard.get(&rollout_id).ok_or_else(rollout_not_found)?;
    Ok(Json(json!({
        "rollout_id": rollout_id,
        "status": session.status,
        "terminated": session.status == "completed" || session.status == "failed" || session.status == "cancelled",
    })))
}

async fn terminate_rollout(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    let session = guard.get_mut(&rollout_id).ok_or_else(rollout_not_found)?;
    session.status = "cancelled".into();
    Ok(Json(json!({"rollout_id": rollout_id, "status": "cancelled"})))
}

/// GELO resume: parent may be missing after heuristic sync completion; fall back
/// to a fresh optimizer episode using request overrides (smoke-compatible).
async fn resume_optimizer_rollout(
    State(app): State<AppState>,
    Path(_parent_rollout_id): Path<String>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    let mut overrides = body
        .get("overrides")
        .cloned()
        .unwrap_or_else(|| body.clone());
    if let Some(object) = overrides.as_object_mut() {
        if let Some(target) = body
            .get("target_rollout_id")
            .and_then(Value::as_str)
            .map(str::to_string)
            .filter(|value| !value.is_empty())
        {
            object.insert("rollout_id".into(), json!(target));
        }
        object
            .entry("submission_mode".to_string())
            .or_insert(json!("sync"));
    }
    run_optimizer_rollout(app, overrides).await
}

async fn gepa_dataset() -> Json<Value> {
    Json(json!({
        "schema": "synth.container.dataset.v1",
        "task_family": "craftax-singleplayer",
        "splits": {
            "train": {"count": 8},
            "validation": {"count": 4},
            "test": {"count": 4}
        },
        "rows": (101_i64..=108).map(|seed| json!({
            "example_id": format!("craftax:train:{seed}"),
            "seed": seed,
            "split": "train",
            "input": {"seed": seed, "task": "craftax"},
            "label": null
        })).collect::<Vec<_>>()
    }))
}

async fn gepa_dataset_rows(Json(body): Json<Value>) -> Json<Value> {
    let split = body
        .get("split")
        .and_then(Value::as_str)
        .unwrap_or("train");
    let seeds: Vec<i64> = body
        .get("seeds")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(Value::as_i64)
                .collect::<Vec<_>>()
        })
        .unwrap_or_else(|| match split {
            "validation" => (201..=204).collect(),
            "test" => (301..=304).collect(),
            _ => (101..=108).collect(),
        });
    Json(json!({
        "schema": "synth.container.dataset_rows.v1",
        "split": split,
        "rows": seeds.into_iter().map(|seed| json!({
            "example_id": format!("craftax:{split}:{seed}"),
            "task_id": format!("craftax:{split}:{seed}"),
            "seed": seed,
            "split": split,
            "input": {"seed": seed, "task": "craftax"},
            "label": null
        })).collect::<Vec<_>>()
    }))
}

async fn gepa_program() -> Json<Value> {
    let seed_prompt =
        "You are playing Craftax. Prefer survival and crafting progress.";
    Json(json!({
        "schema_version": "prompt_program.v1",
        "modules": [{
            "module_id": "react_system_prompt",
            "role": "system",
            "content": seed_prompt,
            "mutable": true,
            "candidate_field": "react_system_prompt"
        }],
        "target_modules": [{
            "module_id": "react_system_prompt",
            "candidate_field": "react_system_prompt",
            "objective": "outcome_reward"
        }],
        "seed_candidate": {
            "react_system_prompt": seed_prompt
        },
        "mutable_keys": ["react_system_prompt"],
        "metadata": {
            "task_family": "craftax-singleplayer",
            "task": "craftax"
        }
    }))
}

async fn optimizer_metadata() -> Json<Value> {
    Json(json!({
        "env_family": "craftax-singleplayer",
        "optimizer_targets": ["go_ex", "gepa"],
        "gelo_tier": "A",
        "gepa_tier": "smoke",
        "optimizer_contracts": {
            "gepa": "synth_optimizers.gepa.v2",
            "go_ex": "synth_optimizers.go_ex.v1"
        }
    }))
}

async fn compatibility(Query(query): Query<HashMap<String, String>>) -> Json<Value> {
    let target = query.get("target").map(String::as_str).unwrap_or("");
    Json(json!({
        "target": target,
        "compatible": matches!(target, "go_ex" | "go-ex" | "gelo" | "gepa" | ""),
        "env_family": "craftax-singleplayer"
    }))
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
        let telemetry_enabled = app.telemetry.lock().unwrap().contains_key(&rollout_id);
        capture_frame_if_enabled(session, app.replay, telemetry_enabled);
    }
    let payload = rollout_payload(&rollout_id, session);
    if let Some(sender) = app.telemetry.lock().unwrap().get(&rollout_id) {
        let event = rollout_event(&rollout_id, &payload);
        let mut histories = app.telemetry_history.lock().unwrap();
        let history = histories.entry(rollout_id.clone()).or_default();
        history.push(event.clone());
        if history.len() > 2048 { history.remove(0); }
        let _ = sender.send(event);
    }
    Ok(Json(payload))
}

fn rollout_event(rollout_id: &str, payload: &Value) -> Value {
    let mut streamed_payload = payload.clone();
    let step = payload.pointer("/progress/env_steps").and_then(Value::as_u64).unwrap_or(0);
    streamed_payload["frame_url"] = json!(format!("/rollouts/{rollout_id}/frames/{step}.png"));
    json!({
        "schema": "synth.rollout.event.v1",
        "rollout_id": rollout_id,
        "run_id": rollout_id,
        "lane": rollout_id,
        "kind": if payload.get("terminated").and_then(Value::as_bool).unwrap_or(false) || payload.get("truncated").and_then(Value::as_bool).unwrap_or(false) { "eval.run.terminal" } else { "snapshot" },
        "event_id": payload.pointer("/progress/env_steps").cloned().unwrap_or(json!(0)),
        "ts": chrono::Utc::now().to_rfc3339(),
        "payload": streamed_payload
    })
}

async fn rollout_stream(State(app): State<AppState>, Path(rollout_id): Path<String>) -> Result<Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>>, ApiError> {
    let receiver = app.telemetry.lock().unwrap().get(&rollout_id).map(broadcast::Sender::subscribe).ok_or_else(|| ApiError { status: StatusCode::NOT_FOUND, code: "telemetry_not_enabled", message: format!("telemetry not enabled for rollout: {rollout_id}") })?;
    let history = app.telemetry_history.lock().unwrap().get(&rollout_id).cloned().unwrap_or_default();
    let historical = tokio_stream::iter(history).map(|event| Ok(sse_event(event)));
    let live = BroadcastStream::new(receiver).filter_map(|message| message.ok().map(|event| Ok(sse_event(event))));
    Ok(Sse::new(historical.chain(live)).keep_alive(KeepAlive::default()))
}

fn sse_event(event: Value) -> Event {
        let event_id = event["event_id"].to_string();
        Event::default().id(event_id).event(event["kind"].as_str().unwrap_or("snapshot")).json_data(event).expect("event JSON")
}

async fn rollout_ws(ws: WebSocketUpgrade, State(app): State<AppState>, Path(rollout_id): Path<String>) -> Result<Response, ApiError> {
    let receiver = app.telemetry.lock().unwrap().get(&rollout_id).map(broadcast::Sender::subscribe).ok_or_else(|| ApiError { status: StatusCode::NOT_FOUND, code: "telemetry_not_enabled", message: format!("telemetry not enabled for rollout: {rollout_id}") })?;
    let history = app.telemetry_history.lock().unwrap().get(&rollout_id).cloned().unwrap_or_default();
    Ok(ws.on_upgrade(move |socket| stream_websocket(socket, receiver, history)).into_response())
}

async fn stream_websocket(mut socket: WebSocket, mut receiver: broadcast::Receiver<Value>, history: Vec<Value>) {
    for event in history {
        if socket.send(Message::Text(event.to_string())).await.is_err() { return; }
    }
    while let Ok(event) = receiver.recv().await {
        if socket.send(Message::Text(event.to_string())).await.is_err() { break; }
    }
}

async fn delete_rollout(
    State(app): State<AppState>,
    Path(rollout_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let mut guard = app.sessions.lock().unwrap();
    if guard.remove(&rollout_id).is_none() {
        return Err(rollout_not_found());
    }
    drop(guard);
    app.telemetry.lock().unwrap().remove(&rollout_id);
    app.telemetry_history.lock().unwrap().remove(&rollout_id);
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

#[cfg(test)]
mod catalog_tests {
	use super::*;

	#[test]
	fn fixed_seed_catalog_has_stable_train_and_test_instances() {
		let catalog = task_catalog_value();
		let instances = catalog["instances"].as_array().expect("instances");
		assert_eq!(instances.len(), 40);
		assert_eq!(instances[0]["task_instance_id"], "craftax:train:1001");
		assert_eq!(instances[31]["task_instance_id"], "craftax:train:1032");
		assert_eq!(instances[32]["task_instance_id"], "craftax:test:2001");
		assert_eq!(instances[39]["metadata"]["seed"], 2008);
	}
}
