use std::collections::BTreeMap;
use std::path::Path;

use serde_json::{json, Map, Value};

use crate::craftax::CraftaxBackend;
use crate::dungeongrid::DungeonGridBackend;
use crate::model::{public_split, EpisodeEvidence, ExecutionSpec};
use crate::overcooked::OvercookedBackend;
use crate::protocol::SEMANTICS_VERSION;

pub enum Backend {
    Craftax(CraftaxBackend),
    DungeonGrid(DungeonGridBackend),
    Overcooked(OvercookedBackend),
}

impl Backend {
    pub fn craftax(tasks_root: &Path) -> Result<Self, String> {
        Ok(Self::Craftax(CraftaxBackend::load(tasks_root)?))
    }

    pub fn dungeongrid(tasks_root: &Path) -> Result<Self, String> {
        Ok(Self::DungeonGrid(DungeonGridBackend::load(tasks_root)?))
    }

    pub fn overcooked(tasks_root: &Path) -> Result<Self, String> {
        Ok(Self::Overcooked(OvercookedBackend::load(tasks_root)?))
    }

    pub fn environment_id(&self) -> &'static str {
        match self {
            Self::Craftax(backend) => backend.environment_id(),
            Self::DungeonGrid(backend) => backend.environment_id(),
            Self::Overcooked(backend) => backend.environment_id(),
        }
    }

    pub fn dataset_id(&self) -> &str {
        match self {
            Self::Craftax(backend) => backend.dataset_id(),
            Self::DungeonGrid(backend) => backend.dataset_id(),
            Self::Overcooked(backend) => backend.dataset_id(),
        }
    }

    pub fn valid_roles(&self) -> Vec<String> {
        match self {
            Self::Craftax(backend) => backend.valid_roles(),
            Self::DungeonGrid(backend) => backend.valid_roles(),
            Self::Overcooked(backend) => backend.valid_roles(),
        }
    }

    pub fn task_roles(&self, task_id: &str) -> Option<Vec<String>> {
        match self {
            Self::Craftax(backend) => backend.task_roles(task_id),
            Self::DungeonGrid(backend) => backend.task_roles(task_id),
            Self::Overcooked(backend) => backend.task_roles(task_id),
        }
    }

    pub fn split_counts(&self) -> &BTreeMap<String, usize> {
        match self {
            Self::Craftax(backend) => backend.split_counts(),
            Self::DungeonGrid(backend) => backend.split_counts(),
            Self::Overcooked(backend) => backend.split_counts(),
        }
    }

    pub fn task_rows(&self, split: &str, task_ids: &[String]) -> Result<Vec<Value>, String> {
        match self {
            Self::Craftax(backend) => backend.task_rows(split, task_ids),
            Self::DungeonGrid(backend) => backend.task_rows(split, task_ids),
            Self::Overcooked(backend) => backend.task_rows(split, task_ids),
        }
    }

    pub fn task_split(&self, task_id: &str) -> Option<&'static str> {
        let mut parts = task_id.split(':');
        let prefix = parts.next()?;
        let dataset_split = parts.next()?;
        let expected = match self {
            Self::Craftax(_) => "craftax_coordination_v1",
            Self::DungeonGrid(_) => "dungeongrid_coordination_v1",
            Self::Overcooked(_) => "overcooked_v2_coordination_v1",
        };
        (prefix == expected)
            .then(|| public_split(dataset_split))
            .flatten()
    }

    pub fn has_task(&self, task_id: &str) -> bool {
        match self {
            Self::Craftax(backend) => backend.has_task(task_id),
            Self::DungeonGrid(backend) => backend.has_task(task_id),
            Self::Overcooked(backend) => backend.has_task(task_id),
        }
    }

    pub fn rollout(
        &self,
        task_id: &str,
        execution: &ExecutionSpec,
    ) -> Result<EpisodeEvidence, String> {
        match self {
            Self::Craftax(backend) => backend.rollout(task_id, execution),
            Self::DungeonGrid(backend) => backend.rollout(task_id, execution),
            Self::Overcooked(backend) => backend.rollout(task_id, execution),
        }
    }

    pub fn taskset(&self) -> Value {
        let counts = self.split_counts();
        let train_count = counts.get("train").copied().unwrap_or_default()
            + counts.get("selection").copied().unwrap_or_default();
        let heldout_count = counts.get("heldout").copied().unwrap_or_default();
        let splits = Map::from_iter([
            ("train".to_string(), json!({"num_tasks": train_count})),
            ("heldout".to_string(), json!({"num_tasks": heldout_count})),
        ]);
        json!({
            "taskset_id": self.dataset_id(),
            "splits": splits,
            "labels": [],
            "source": "committed GameBench MAPO coordination dataset v1",
            "metadata": {
                "environment": self.environment_id(),
                "row_version": "v1",
                "public_split_mapping": "Internal train and selection rows are both fetched through public split=train; internal heldout rows require public split=heldout.",
                "split_isolation": "Task ids are resolved only within the matching public split. This response never exposes heldout rows, ids, checkpoints, or labels through train.",
            },
        })
    }

    pub fn task_info(&self) -> Value {
        let environment_guidance = match self {
            Self::Craftax(_) => json!({
                "authority": "craftax-coop-gamebench",
                "actors": self.valid_roles(),
                "communication_surface": "Grounded request_<resource> engine actions followed by engine-validated give_<resource>_to_<agent> actions.",
                "load_bearing_events": ["request_made", "trade_applied", "craft completion"],
                "priority_value": "DELIVERY",
            }),
            Self::DungeonGrid(_) => json!({
                "authority": "dungeongrid_gold",
                "actors": self.valid_roles(),
                "communication_surface": "Engine Message actions deliver bounded text to party inboxes before role-specialized actions.",
                "load_bearing_events": ["counterplay_revealed", "door_opened", "objective_taken", "item_given", "objective_escaped"],
                "priority_value": "EXTRACTION",
            }),
            Self::Overcooked(_) => json!({
                "authority": "overcooked-v2-gold",
                "actors": self.valid_roles(),
                "communication_surface": "Grounded button activation, visible pot-state changes, and counter handoffs are the only communication signals. The adapter emits no free-text engine messages.",
                "load_bearing_events": ["ButtonActivated", "PotIngredientAdded", "CookStart", "ItemPicked(...,counter)", "Delivery"],
                "priority_value": "DELIVERY",
                "row_roles": "Use each task row's roles array for exact role_ablation::<role> arms; roles are restricted by probe and active agent count.",
            }),
        };
        json!({
            "task": {
                "task_id": "gamebench_marl_prompt_protocol",
                "name": "Frozen-checkpoint multi-agent prompt protocol control",
                "description": "Optimize three shared string prompt fields. A strict Rust semantic layer maps only explicit bounded directives to deterministic actions in the selected Rust authority.",
                "objective": "Maximize numeric outcome_reward from real engine actions/events while improving coordination, alignment, role consistency, and efficiency.",
                "environment": self.environment_id(),
            },
            "prompt_program": {
                "semantics_version": SEMANTICS_VERSION,
                "mutable_string_fields": ["shared_instruction", "communication_policy", "role_prompts"],
                "unknown_directive_behavior": "Unknown, vague, malformed, misplaced, or out-of-range text leaves that semantic at seed behavior. It never selects an oracle continuation.",
                "directives": {
                    "shared_instruction": {
                        "PRIORITY": ["SAFETY", "DELIVERY", "EXTRACTION"],
                    },
                    "communication_policy": {
                        "SPEAK": ["ALWAYS", "EVENT_TRIGGERED", "SILENT"],
                        "MAX_CHARS": "integer 8..240",
                        "REQUEST": ["ACTION_ONLY", "REQUEST_THEN_ACT", "REQUEST_ONLY"],
                        "HANDOFF": ["DIRECT", "REQUIRED", "NONE"],
                        "FOLLOWER_REPLY": ["ACK", "ON_REQUEST", "SILENT"],
                    },
                    "role_prompts": {
                        "ROLE_ASSIGNMENT": ["FLEXIBLE", "SPECIALISTS", "DUPLICATED"],
                        "ROLE[<role>]": ["FLEXIBLE", "SPECIALIST", "DUPLICATED", "SILENT"],
                    },
                },
            },
            "environment_contract": environment_guidance,
            "evaluation": {
                "primary_metric": "outcome_reward",
                "metrics": [
                    "outcome_success",
                    "coordination_success",
                    "message_action_alignment",
                    "role_consistency",
                    "role_duplication_count",
                    "invalid_action_count",
                    "idle_action_count",
                    "interference_action_count",
                    "message_count",
                    "message_chars",
                    "per_agent_contribution_coverage",
                    "engine_reward"
                ],
                "trace_evidence": "Every rollout returns generated/applied actions, real Rust-engine events, per-agent contribution signals, protocol parse diagnostics, and checkpoint/final-state digests.",
                "reward_formula": "0.45 outcome + 0.20 coordination + 0.10 alignment + 0.10 role consistency + 0.05 contribution coverage + 0.10 baseline, minus bounded invalid/interference/duplication/idle/message-character penalties; clamped to [-1,1].",
            },
            "diagnostic_interventions": {
                "required_metadata": "metadata.evaluation_arm is mandatory for every rollout, including primary.",
                "arm_ids": ["primary", "channel_masked", "role_permuted", "role_ablation::<role>"],
                "channel_masked": "Preserves real send or grounded-signal actions/events and counters, then suppresses only the recipient/request/inbox delivery or the executor's downstream use of that information on the same checkpoint.",
                "role_permuted": "Changes only which frozen-checkpoint actor receives each specialist assignment.",
                "role_ablation": {
                    "baseline_key": "metadata.ablation_baseline",
                    "accepted_aliases": ["parent_candidate", "seed_candidate", "parent_behavior", "seed_behavior"],
                    "behavior": "Only the arm suffix role's parsed role prompt is replaced; all shared and communication semantics remain the candidate's.",
                },
                "evidence": "Every non-primary response fails closed unless it can return intervention_applied=true, checkpoint_digest, and its arm-specific applied field.",
                "primary_metric_policy": "IMAC comparisons use primary-arm metrics only. Other arms are diagnostic matched evidence for COMA, IC3Net, and RODE.",
            },
            "data_isolation": {
                "proposer_visible": "Internal train and selection task rows are available only through public split=train; train-side rollout evidence never crosses into heldout.",
                "heldout_policy": "Heldout rows, task ids, checkpoints, labels, and answers are absent from task_info, program, metadata, and train task requests.",
                "overfitting_warning": "Propose general protocol directives, never task-id tables or exact continuation answers.",
            },
        })
    }
}
