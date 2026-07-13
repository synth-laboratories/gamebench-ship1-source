mod backend;
mod craftax;
mod dungeongrid;
mod model;
mod protocol;

use std::net::IpAddr;
use std::path::PathBuf;
use std::sync::Arc;

use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use backend::Backend;
use clap::{Parser, ValueEnum};
use model::{DiagnosticArm, EpisodeEvidence, TRACE_SCHEMA};
use protocol::{
    execution_spec, CandidateProgram, COMMUNICATION_POLICY, PROGRAM_FIELDS, ROLE_PROMPTS,
    SEMANTICS_VERSION, SHARED_INSTRUCTION,
};
use serde::Deserialize;
use serde_json::{json, Map, Value};
use uuid::Uuid;

const GEPA_CONTRACT_VERSION: &str = "gepa_optimizer_contract.v1";

#[derive(Clone, Copy, Debug, ValueEnum)]
enum Environment {
    Craftax,
    Dungeongrid,
}

#[derive(Debug, Parser)]
#[command(about = "Pure-Rust GameBench MARL prompt optimization eval service")]
struct Args {
    #[arg(long, value_enum)]
    environment: Environment,
    #[arg(long, default_value = "127.0.0.1")]
    host: IpAddr,
    #[arg(long, default_value_t = 8788)]
    port: u16,
}

#[derive(Clone)]
struct AppState {
    backend: Arc<Backend>,
}

#[derive(Clone, Debug, Deserialize)]
struct TasksetTasksRequest {
    split: String,
    #[serde(default)]
    task_ids: Vec<String>,
    #[serde(default)]
    filters: Value,
}

#[derive(Clone, Debug, Default, Deserialize)]
struct RolloutRequest {
    #[serde(default)]
    rollout_id: Option<String>,
    #[serde(default)]
    trace_correlation_id: Option<String>,
    #[serde(default)]
    candidate: Map<String, Value>,
    #[serde(default)]
    candidate_overlay: Map<String, Value>,
    #[serde(default)]
    task: Map<String, Value>,
    #[serde(default)]
    task_id: Option<String>,
    #[serde(default)]
    metadata: Map<String, Value>,
}

#[derive(Debug)]
struct ApiError {
    status: StatusCode,
    message: String,
}

impl ApiError {
    fn bad_request(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::BAD_REQUEST,
            message: message.into(),
        }
    }

    fn internal(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            message: message.into(),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (
            self.status,
            Json(json!({
                "error": {
                    "kind": if self.status == StatusCode::BAD_REQUEST { "invalid_request" } else { "internal_error" },
                    "message": self.message,
                }
            })),
        )
            .into_response()
    }
}

#[tokio::main]
async fn main() -> Result<(), String> {
    let args = Args::parse();
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let tasks_root = manifest_dir
        .parent()
        .ok_or_else(|| "marl-promptopt-rust must have the tasks directory as parent".to_string())?;
    let backend = match args.environment {
        Environment::Craftax => Backend::craftax(tasks_root)?,
        Environment::Dungeongrid => Backend::dungeongrid(tasks_root)?,
    };
    let environment = backend.environment_id();
    let state = AppState {
        backend: Arc::new(backend),
    };
    let app = Router::new()
        .route("/health", get(health))
        .route("/metadata", get(metadata))
        .route("/info", get(metadata))
        .route("/task_info", get(task_info))
        .route("/program", get(program))
        .route("/taskset", get(taskset))
        .route("/taskset/tasks", post(taskset_tasks))
        .route("/rollout", post(rollout))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind((args.host, args.port))
        .await
        .map_err(|error| format!("bind {}:{}: {error}", args.host, args.port))?;
    eprintln!(
        "gamebench MARL promptopt service environment={environment} listening=http://{}:{}",
        args.host, args.port
    );
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .map_err(|error| format!("serve HTTP: {error}"))
}

async fn shutdown_signal() {
    let _ = tokio::signal::ctrl_c().await;
}

async fn health(State(state): State<AppState>) -> Json<Value> {
    Json(json!({
        "status": "ok",
        "contract_version": GEPA_CONTRACT_VERSION,
        "environment": state.backend.environment_id(),
    }))
}

async fn metadata(State(state): State<AppState>) -> Json<Value> {
    Json(json!({
        "runtime": {
            "runtime_id": format!("gamebench_marl_promptopt_rust_{}", state.backend.environment_id()),
            "name": "GameBench MARL prompt-to-protocol Rust eval",
            "environment": state.backend.environment_id(),
            "implementation": "pure_rust",
        },
        "capabilities": {
            "contract_version": "container_contract.v1",
            "rollout_modes": ["blocking"],
            "deterministic_frozen_checkpoints": true,
            "diagnostic_arms": ["primary", "channel_masked", "role_permuted", "role_ablation::<role>"],
        },
        "metadata": {
            "optimizer_contracts": {
                "gepa": {
                    "version": GEPA_CONTRACT_VERSION,
                    "program_route": "/program",
                    "taskset_route": "/taskset",
                    "taskset_tasks_route": "/taskset/tasks",
                    "rollout_route": "/rollout",
                }
            },
            "privacy": {
                "heldout_rows_in_metadata": false,
                "heldout_labels_in_metadata": false,
            }
        }
    }))
}

async fn task_info(State(state): State<AppState>) -> Json<Value> {
    Json(state.backend.task_info())
}

async fn program() -> Json<Value> {
    let modules = [
        (
            "shared_instruction",
            "system",
            SHARED_INSTRUCTION,
            "Select only the bounded environment priority semantic.",
        ),
        (
            "communication_policy",
            "developer",
            COMMUNICATION_POLICY,
            "Select bounded speaking, message length, request, handoff, and reply semantics.",
        ),
        (
            "role_prompts",
            "developer",
            ROLE_PROMPTS,
            "Select global and optional role-specific assignment behavior in one string field.",
        ),
    ]
    .into_iter()
    .map(|(field, role, content, objective)| {
        json!({
            "module_id": field,
            "role": role,
            "content": content,
            "mutable": true,
            "candidate_field": field,
            "template_variables": [],
            "metadata": {"semantic_objective": objective},
        })
    })
    .collect::<Vec<_>>();
    let target_modules = PROGRAM_FIELDS
        .into_iter()
        .map(|field| {
            json!({
                "module_id": field,
                "candidate_field": field,
                "objective": "outcome_reward",
            })
        })
        .collect::<Vec<_>>();
    Json(json!({
        "version": "prompt_program.v1",
        "program_id": "gamebench_marl_prompt_protocol_v1",
        "modules": modules,
        "target_modules": target_modules,
        "seed_candidate": {
            "shared_instruction": SHARED_INSTRUCTION,
            "communication_policy": COMMUNICATION_POLICY,
            "role_prompts": ROLE_PROMPTS,
        },
        "rollout_overlay_schema": {
            "candidate_fields": PROGRAM_FIELDS,
            "value_type": "string",
        },
        "metadata": {
            "semantics_version": SEMANTICS_VERSION,
            "same_program_across_environments": true,
            "unknown_directives_use_seed_behavior": true,
        }
    }))
}

async fn taskset(State(state): State<AppState>) -> Json<Value> {
    Json(state.backend.taskset())
}

async fn taskset_tasks(
    State(state): State<AppState>,
    Json(request): Json<TasksetTasksRequest>,
) -> Result<Json<Value>, ApiError> {
    if !matches!(&request.filters, Value::Null)
        && !request.filters.as_object().is_some_and(Map::is_empty)
    {
        return Err(ApiError::bad_request(
            "this fixed taskset does not accept task filters",
        ));
    }
    let tasks = state
        .backend
        .task_rows(&request.split, &request.task_ids)
        .map_err(ApiError::bad_request)?;
    Ok(Json(json!({
        "tasks": tasks,
        "metadata": {
            "split": request.split,
            "count": request.task_ids.len(),
            "dataset_id": state.backend.dataset_id(),
            "heldout_labels_returned": false,
        }
    })))
}

async fn rollout(
    State(state): State<AppState>,
    Json(request): Json<RolloutRequest>,
) -> Result<Json<Value>, ApiError> {
    let backend = state.backend.clone();
    let result = tokio::task::spawn_blocking(move || run_rollout(&backend, request))
        .await
        .map_err(|error| ApiError::internal(format!("rollout worker failed: {error}")))??;
    Ok(Json(result))
}

fn run_rollout(backend: &Backend, request: RolloutRequest) -> Result<Value, ApiError> {
    let row_task_id = request
        .task
        .get("task_id")
        .or_else(|| request.task.get("task_instance_id"))
        .or_else(|| request.task.get("example_id"))
        .and_then(Value::as_str)
        .or(request.task_id.as_deref())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| ApiError::bad_request("rollout requires task.task_id"))?;
    let expected_split = backend
        .task_split(row_task_id)
        .ok_or_else(|| ApiError::bad_request(format!("unknown task id {row_task_id:?}")))?;
    if !backend.has_task(row_task_id) {
        return Err(ApiError::bad_request(format!(
            "unknown task id {row_task_id:?}"
        )));
    }
    let supplied_split = request
        .task
        .get("split")
        .and_then(Value::as_str)
        .ok_or_else(|| ApiError::bad_request("rollout requires task.split"))?;
    if supplied_split != expected_split {
        return Err(ApiError::bad_request(
            "task id is not available in the supplied task split",
        ));
    }
    let candidate =
        CandidateProgram::from_candidate_maps(&request.candidate, &request.candidate_overlay)
            .map_err(ApiError::bad_request)?;
    let execution = execution_spec(&candidate, &request.metadata, &backend.valid_roles())
        .map_err(ApiError::bad_request)?;
    let evidence = backend
        .rollout(row_task_id, &execution)
        .map_err(ApiError::internal)?;
    if evidence.checkpoint_digest.trim().is_empty() {
        return Err(ApiError::internal(
            "rollout authority did not return a checkpoint digest",
        ));
    }
    let intervention = intervention_evidence(&execution.arm, &evidence)?;
    let rollout_id = request
        .rollout_id
        .unwrap_or_else(|| format!("rollout_{}", Uuid::new_v4().simple()));
    Ok(rollout_response(
        rollout_id,
        request.trace_correlation_id,
        candidate,
        execution,
        evidence,
        intervention,
    ))
}

fn intervention_evidence(
    arm: &DiagnosticArm,
    evidence: &EpisodeEvidence,
) -> Result<Value, ApiError> {
    let mut receipt = Map::from_iter([
        ("arm_id".to_string(), json!(arm.id)),
        (
            "intervention_applied".to_string(),
            json!(!arm.primary_metric_eligible()),
        ),
        (
            "checkpoint_digest".to_string(),
            json!(evidence.checkpoint_digest),
        ),
    ]);
    match arm.id.as_str() {
        "primary" => {}
        "channel_masked" if arm.channel_masked => {
            receipt.insert("channel_mask_applied".to_string(), json!(true));
        }
        "role_permuted" if arm.role_permuted => {
            receipt.insert("role_permutation_applied".to_string(), json!(true));
        }
        value if value.starts_with("role_ablation::") => {
            let role = arm.ablated_role.as_deref().ok_or_else(|| {
                ApiError::internal("role ablation completed without an ablated role receipt")
            })?;
            receipt.insert("ablate_role".to_string(), json!(role));
        }
        _ => {
            return Err(ApiError::internal(format!(
                "diagnostic arm {:?} did not produce its required applied receipt",
                arm.id
            )))
        }
    }
    if !arm.primary_metric_eligible()
        && receipt.get("intervention_applied").and_then(Value::as_bool) != Some(true)
    {
        return Err(ApiError::internal(
            "non-primary rollout did not apply its requested intervention",
        ));
    }
    Ok(Value::Object(receipt))
}

fn rollout_response(
    rollout_id: String,
    trace_correlation_id: Option<String>,
    candidate: CandidateProgram,
    execution: model::ExecutionSpec,
    evidence: EpisodeEvidence,
    intervention: Value,
) -> Value {
    let outcome_reward = evidence.metrics.outcome_reward();
    let metrics = serde_json::to_value(&evidence.metrics).unwrap_or_else(|_| json!({}));
    let per_agent = serde_json::to_value(&evidence.per_agent).unwrap_or_else(|_| json!({}));
    let protocol = serde_json::to_value(&execution.protocol).unwrap_or_else(|_| json!({}));
    let mut summary = Map::new();
    summary.insert("outcome_reward".to_string(), json!(outcome_reward));
    summary.insert("evaluation_arm".to_string(), json!(execution.arm.id));
    summary.insert(
        "primary_metric_eligible".to_string(),
        json!(execution.arm.primary_metric_eligible()),
    );
    summary.insert(
        "checkpoint_digest".to_string(),
        json!(evidence.checkpoint_digest),
    );
    summary.insert(
        "final_state_digest".to_string(),
        json!(evidence.final_state_digest),
    );
    summary.insert("metrics".to_string(), metrics.clone());
    summary.insert("intervention".to_string(), intervention.clone());
    summary.extend(evidence.summary_fields.clone());
    let success = evidence.metrics.outcome_success == 1.0;
    json!({
        "rollout_id": rollout_id,
        "trace_correlation_id": trace_correlation_id,
        "status": "completed",
        "success_status": if success { "succeeded" } else { "failed" },
        "task_id": evidence.task_id,
        "reward_info": {
            "outcome_reward": outcome_reward,
            "score": outcome_reward,
            "event_rewards": [{"kind": "authority_engine_reward", "value": evidence.metrics.engine_reward}],
            "metrics": metrics,
            "details": {
                "objective": "outcome_reward",
                "environment": evidence.environment,
                "split": evidence.split,
                "checkpoint_digest": evidence.checkpoint_digest,
                "final_state_digest": evidence.final_state_digest,
                "evaluation_arm": execution.arm.id,
                "intervention": intervention,
                "per_agent_contributions": per_agent,
            }
        },
        "summary": summary,
        "intervention_evidence": intervention,
        "trace": {
            "schema_version": TRACE_SCHEMA,
            "semantics_version": SEMANTICS_VERSION,
            "evaluation_arm": execution.arm.id,
            "checkpoint_digest": evidence.checkpoint_digest,
            "final_state_digest": evidence.final_state_digest,
            "intervention": intervention,
            "protocol": protocol,
            "event_history": evidence.engine_events,
            "action_trace": evidence.action_trace,
            "per_agent_contributions": per_agent,
        },
        "turns": evidence.action_trace,
        "events": evidence.engine_events,
        "usage": {
            "model_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "executor": "deterministic_rust_prompt_to_protocol",
        },
        "actionable_side_info": {
            "failure_signals": evidence.failure_signals,
            "recognized_directives": execution.protocol.recognized_directives,
            "ignored_directives": execution.protocol.ignored_directives,
            "next_prompt_action": "Use only the documented bounded directives; inspect failed engine actions, delivery receipts, role consistency, and message/action alignment before changing one semantic at a time.",
        },
        "metadata": {
            "candidate": candidate.as_map(),
            "evaluation_arm": execution.arm.id,
            "diagnostic_only": !execution.arm.primary_metric_eligible(),
            "intervention": intervention,
        }
    })
}
