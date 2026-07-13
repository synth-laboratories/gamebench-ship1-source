use std::collections::BTreeMap;

use serde::Serialize;
use serde_json::Value;

use crate::protocol::ParsedProtocol;

pub const ROW_SCHEMA: &str = "gamebench.marl_promptopt_task.v1";
pub const TRACE_SCHEMA: &str = "gamebench.marl_promptopt_trace.v1";

pub fn public_split(dataset_split: &str) -> Option<&'static str> {
    match dataset_split {
        "train" | "selection" => Some("train"),
        "heldout" => Some("heldout"),
        _ => None,
    }
}

pub fn validate_public_split(split: &str) -> Result<(), String> {
    if matches!(split, "train" | "heldout") {
        Ok(())
    } else {
        Err(format!(
            "unsupported public split {split:?}; expected train or heldout"
        ))
    }
}

#[derive(Clone, Debug)]
pub struct DiagnosticArm {
    pub id: String,
    pub channel_masked: bool,
    pub role_permuted: bool,
    pub ablated_role: Option<String>,
}

impl DiagnosticArm {
    pub fn primary() -> Self {
        Self {
            id: "primary".to_string(),
            channel_masked: false,
            role_permuted: false,
            ablated_role: None,
        }
    }

    pub fn primary_metric_eligible(&self) -> bool {
        self.id == "primary"
    }
}

#[derive(Clone, Debug)]
pub struct ExecutionSpec {
    pub protocol: ParsedProtocol,
    pub arm: DiagnosticArm,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct AgentContribution {
    pub generated_actions: usize,
    pub applied_actions: usize,
    pub messages_sent: usize,
    pub engine_events: usize,
    pub successful_contributions: usize,
    pub reward: f64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct EpisodeMetrics {
    pub outcome_success: f64,
    pub coordination_success: f64,
    pub message_action_alignment: f64,
    pub role_consistency: f64,
    pub role_duplication_count: usize,
    pub invalid_action_count: usize,
    pub idle_action_count: usize,
    pub interference_action_count: usize,
    pub message_count: usize,
    pub message_chars: usize,
    pub per_agent_contribution_coverage: f64,
    pub engine_reward: f64,
}

impl EpisodeMetrics {
    pub fn outcome_reward(&self) -> f64 {
        let base = 0.45 * self.outcome_success
            + 0.20 * self.coordination_success
            + 0.10 * self.message_action_alignment
            + 0.10 * self.role_consistency
            + 0.05 * self.per_agent_contribution_coverage
            + 0.10;
        let penalty = 0.03 * self.invalid_action_count as f64
            + 0.02 * self.interference_action_count as f64
            + 0.01 * self.role_duplication_count as f64
            + 0.002 * self.idle_action_count as f64
            + 0.000_25 * self.message_chars as f64;
        (base - penalty).clamp(-1.0, 1.0)
    }
}

#[derive(Clone, Debug)]
pub struct EpisodeEvidence {
    pub task_id: String,
    pub split: String,
    pub environment: String,
    pub checkpoint_digest: String,
    pub final_state_digest: String,
    pub metrics: EpisodeMetrics,
    pub per_agent: BTreeMap<String, AgentContribution>,
    pub engine_events: Vec<Value>,
    pub action_trace: Vec<Value>,
    pub failure_signals: Vec<String>,
    pub summary_fields: BTreeMap<String, Value>,
}

pub fn contribution_coverage(contributions: &BTreeMap<String, AgentContribution>) -> f64 {
    if contributions.is_empty() {
        return 0.0;
    }
    let active = contributions
        .values()
        .filter(|entry| entry.successful_contributions > 0)
        .count();
    active as f64 / contributions.len() as f64
}
