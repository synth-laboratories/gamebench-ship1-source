use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::{Map, Value};

use crate::model::{DiagnosticArm, ExecutionSpec};

pub const SEMANTICS_VERSION: &str = "gamebench.prompt_to_protocol.v1";
pub const SHARED_INSTRUCTION: &str = "PRIORITY=SAFETY";
pub const COMMUNICATION_POLICY: &str =
    "SPEAK=ALWAYS; MAX_CHARS=120; REQUEST=ACTION_ONLY; HANDOFF=DIRECT; FOLLOWER_REPLY=ACK";
pub const ROLE_PROMPTS: &str = "ROLE_ASSIGNMENT=FLEXIBLE";

pub const PROGRAM_FIELDS: [&str; 3] =
    ["shared_instruction", "communication_policy", "role_prompts"];

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SpeakPolicy {
    Always,
    EventTriggered,
    Silent,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Priority {
    Safety,
    Delivery,
    Extraction,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RequestPolicy {
    ActionOnly,
    RequestThenAct,
    RequestOnly,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HandoffPolicy {
    Direct,
    Required,
    None,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FollowerReply {
    Ack,
    OnRequest,
    Silent,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RoleMode {
    Flexible,
    Specialist,
    Duplicated,
    Silent,
}

#[derive(Clone, Debug, Serialize)]
pub struct ParsedProtocol {
    pub speak: SpeakPolicy,
    pub max_chars: usize,
    pub priority: Priority,
    pub request: RequestPolicy,
    pub handoff: HandoffPolicy,
    pub follower_reply: FollowerReply,
    pub role_assignment: RoleMode,
    pub role_overrides: BTreeMap<String, RoleMode>,
    pub recognized_directives: BTreeMap<String, String>,
    pub ignored_directives: Vec<String>,
}

impl Default for ParsedProtocol {
    fn default() -> Self {
        Self {
            speak: SpeakPolicy::Always,
            max_chars: 120,
            priority: Priority::Safety,
            request: RequestPolicy::ActionOnly,
            handoff: HandoffPolicy::Direct,
            follower_reply: FollowerReply::Ack,
            role_assignment: RoleMode::Flexible,
            role_overrides: BTreeMap::new(),
            recognized_directives: BTreeMap::new(),
            ignored_directives: Vec::new(),
        }
    }
}

impl ParsedProtocol {
    pub fn from_program(program: &CandidateProgram) -> Self {
        let mut parsed = Self::default();
        parsed.parse_shared(&program.shared_instruction);
        parsed.parse_communication(&program.communication_policy);
        parsed.parse_roles(&program.role_prompts);
        parsed
    }

    pub fn role_mode(&self, role: &str) -> RoleMode {
        self.role_overrides
            .get(&role.to_ascii_lowercase())
            .copied()
            .unwrap_or(self.role_assignment)
    }

    pub fn ablate_role_from(&mut self, role: &str, baseline: &ParsedProtocol) {
        self.role_overrides
            .insert(role.to_ascii_lowercase(), baseline.role_mode(role));
        self.recognized_directives.insert(
            format!("ROLE[{role}]"),
            format!("{:?}", baseline.role_mode(role)).to_ascii_uppercase(),
        );
    }

    fn parse_shared(&mut self, text: &str) {
        for token in tokens(text) {
            let Some((key, value)) = directive(&token) else {
                self.ignore(token);
                continue;
            };
            if key != "PRIORITY" {
                self.ignore(token);
                continue;
            }
            let parsed = match value.as_str() {
                "SAFETY" => Some(Priority::Safety),
                "DELIVERY" => Some(Priority::Delivery),
                "EXTRACTION" => Some(Priority::Extraction),
                _ => None,
            };
            if let Some(value) = parsed {
                self.priority = value;
                self.record(key, format!("{value:?}").to_ascii_uppercase());
            } else {
                self.ignore(token);
            }
        }
    }

    fn parse_communication(&mut self, text: &str) {
        for token in tokens(text) {
            let Some((key, value)) = directive(&token) else {
                self.ignore(token);
                continue;
            };
            let accepted = match key.as_str() {
                "SPEAK" => match value.as_str() {
                    "ALWAYS" => {
                        self.speak = SpeakPolicy::Always;
                        true
                    }
                    "EVENT_TRIGGERED" => {
                        self.speak = SpeakPolicy::EventTriggered;
                        true
                    }
                    "SILENT" => {
                        self.speak = SpeakPolicy::Silent;
                        true
                    }
                    _ => false,
                },
                "MAX_CHARS" => value
                    .parse::<usize>()
                    .ok()
                    .filter(|value| (8..=240).contains(value))
                    .map(|value| self.max_chars = value)
                    .is_some(),
                "REQUEST" => match value.as_str() {
                    "ACTION_ONLY" => {
                        self.request = RequestPolicy::ActionOnly;
                        true
                    }
                    "REQUEST_THEN_ACT" => {
                        self.request = RequestPolicy::RequestThenAct;
                        true
                    }
                    "REQUEST_ONLY" => {
                        self.request = RequestPolicy::RequestOnly;
                        true
                    }
                    _ => false,
                },
                "HANDOFF" => match value.as_str() {
                    "DIRECT" => {
                        self.handoff = HandoffPolicy::Direct;
                        true
                    }
                    "REQUIRED" => {
                        self.handoff = HandoffPolicy::Required;
                        true
                    }
                    "NONE" => {
                        self.handoff = HandoffPolicy::None;
                        true
                    }
                    _ => false,
                },
                "FOLLOWER_REPLY" => match value.as_str() {
                    "ACK" => {
                        self.follower_reply = FollowerReply::Ack;
                        true
                    }
                    "ON_REQUEST" => {
                        self.follower_reply = FollowerReply::OnRequest;
                        true
                    }
                    "SILENT" => {
                        self.follower_reply = FollowerReply::Silent;
                        true
                    }
                    _ => false,
                },
                _ => false,
            };
            if accepted {
                self.record(key, value);
            } else {
                self.ignore(token);
            }
        }
    }

    fn parse_roles(&mut self, text: &str) {
        for token in tokens(text) {
            let Some((key, value)) = directive(&token) else {
                self.ignore(token);
                continue;
            };
            let Some(mode) = parse_role_mode(&value, key == "ROLE_ASSIGNMENT") else {
                self.ignore(token);
                continue;
            };
            if key == "ROLE_ASSIGNMENT" {
                self.role_assignment = mode;
                self.record(key, value);
                continue;
            }
            let Some(role) = key
                .strip_prefix("ROLE[")
                .and_then(|rest| rest.strip_suffix(']'))
                .map(str::to_ascii_lowercase)
                .filter(|role| valid_role_name(role))
            else {
                self.ignore(token);
                continue;
            };
            self.role_overrides.insert(role.clone(), mode);
            self.record(format!("ROLE[{role}]"), value);
        }
    }

    fn record(&mut self, key: impl Into<String>, value: String) {
        self.recognized_directives.insert(key.into(), value);
    }

    fn ignore(&mut self, token: String) {
        let token = token.trim();
        if !token.is_empty() && !self.ignored_directives.iter().any(|item| item == token) {
            self.ignored_directives.push(token.to_string());
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct CandidateProgram {
    pub shared_instruction: String,
    pub communication_policy: String,
    pub role_prompts: String,
}

impl CandidateProgram {
    pub fn seed() -> Self {
        Self {
            shared_instruction: SHARED_INSTRUCTION.to_string(),
            communication_policy: COMMUNICATION_POLICY.to_string(),
            role_prompts: ROLE_PROMPTS.to_string(),
        }
    }

    pub fn from_candidate_maps(
        candidate: &Map<String, Value>,
        candidate_overlay: &Map<String, Value>,
    ) -> Result<Self, String> {
        let overlay_candidate = candidate_overlay
            .get("candidate")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default();
        let source = if candidate.is_empty() {
            &overlay_candidate
        } else {
            candidate
        };
        Self::from_object(source)
    }

    pub fn from_value(value: &Value) -> Result<Self, String> {
        match value {
            Value::String(role_prompts) => Ok(Self {
                role_prompts: role_prompts.clone(),
                ..Self::seed()
            }),
            Value::Object(object) => {
                if let Some(candidate) = object.get("candidate").and_then(Value::as_object) {
                    return Self::from_object(candidate);
                }
                Self::from_object(object)
            }
            _ => Err("ablation baseline must be a prompt string or candidate object".to_string()),
        }
    }

    fn from_object(object: &Map<String, Value>) -> Result<Self, String> {
        let mut program = Self::seed();
        for field in PROGRAM_FIELDS {
            let Some(value) = object.get(field) else {
                continue;
            };
            let text = value
                .as_str()
                .ok_or_else(|| format!("candidate field {field:?} must be a string"))?;
            match field {
                "shared_instruction" => program.shared_instruction = text.to_string(),
                "communication_policy" => program.communication_policy = text.to_string(),
                "role_prompts" => program.role_prompts = text.to_string(),
                _ => unreachable!(),
            }
        }
        Ok(program)
    }

    pub fn as_map(&self) -> Map<String, Value> {
        Map::from_iter([
            (
                "shared_instruction".to_string(),
                Value::String(self.shared_instruction.clone()),
            ),
            (
                "communication_policy".to_string(),
                Value::String(self.communication_policy.clone()),
            ),
            (
                "role_prompts".to_string(),
                Value::String(self.role_prompts.clone()),
            ),
        ])
    }
}

pub fn execution_spec(
    program: &CandidateProgram,
    metadata: &Map<String, Value>,
    valid_roles: &[String],
) -> Result<ExecutionSpec, String> {
    let arm_id = metadata
        .get("evaluation_arm")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            "metadata.evaluation_arm is required; use primary, channel_masked, role_permuted, or role_ablation::<role>"
                .to_string()
        })?
        .to_ascii_lowercase();
    let mut protocol = ParsedProtocol::from_program(program);
    let mut arm = DiagnosticArm::primary();
    match arm_id.as_str() {
        "primary" => {}
        "channel_masked" => {
            arm.id = arm_id;
            arm.channel_masked = true;
        }
        "role_permuted" => {
            arm.id = arm_id;
            arm.role_permuted = true;
        }
        value if value.starts_with("role_ablation::") => {
            let normalized_role = value
                .strip_prefix("role_ablation::")
                .map(str::trim)
                .filter(|role| !role.is_empty())
                .ok_or_else(|| {
                    "role ablation arm must be role_ablation::<role>".to_string()
                })?
                .to_ascii_lowercase();
            if let Some(declared_role) = metadata
                .get("ablate_role")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|role| !role.is_empty())
            {
                if !declared_role.eq_ignore_ascii_case(&normalized_role) {
                    return Err(format!(
                        "metadata.ablate_role {declared_role:?} does not match evaluation arm role {normalized_role:?}"
                    ));
                }
            }
            let valid = valid_roles
                .iter()
                .map(|role| role.to_ascii_lowercase())
                .collect::<BTreeSet<_>>();
            if !valid.contains(&normalized_role) {
                return Err(format!(
                    "role ablation requested missing role {normalized_role:?} in this environment"
                ));
            }
            let baseline = [
                "ablation_baseline",
                "parent_candidate",
                "seed_candidate",
                "parent_behavior",
                "seed_behavior",
            ]
            .into_iter()
            .find_map(|key| metadata.get(key))
            .ok_or_else(|| {
                "role_ablation requires metadata.ablation_baseline (or parent/seed candidate behavior)"
                    .to_string()
            })?;
            let baseline_program = CandidateProgram::from_value(baseline)?;
            let baseline_protocol = ParsedProtocol::from_program(&baseline_program);
            protocol.ablate_role_from(&normalized_role, &baseline_protocol);
            arm.id = format!("role_ablation::{normalized_role}");
            arm.ablated_role = Some(normalized_role);
        }
        other => {
            return Err(format!(
                "unsupported metadata.evaluation_arm {other:?}; expected primary, channel_masked, role_permuted, or role_ablation::<role>"
            ))
        }
    }
    Ok(ExecutionSpec { protocol, arm })
}

fn tokens(text: &str) -> impl Iterator<Item = String> + '_ {
    text.split([';', '\n'])
        .map(str::trim)
        .filter(|token| !token.is_empty())
        .map(str::to_string)
}

fn directive(token: &str) -> Option<(String, String)> {
    let (key, value) = token.split_once('=')?;
    let key = key.trim().to_ascii_uppercase();
    let value = value
        .trim()
        .trim_matches(|character: char| character == '.' || character == ',')
        .to_ascii_uppercase();
    if key.is_empty() || value.is_empty() {
        return None;
    }
    Some((key, value))
}

fn parse_role_mode(value: &str, global: bool) -> Option<RoleMode> {
    match value {
        "FLEXIBLE" => Some(RoleMode::Flexible),
        "SPECIALIST" if !global => Some(RoleMode::Specialist),
        "SPECIALISTS" if global => Some(RoleMode::Specialist),
        "DUPLICATED" => Some(RoleMode::Duplicated),
        "SILENT" if !global => Some(RoleMode::Silent),
        _ => None,
    }
}

fn valid_role_name(role: &str) -> bool {
    !role.is_empty()
        && role.len() <= 32
        && role
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '_' | '-'))
}
