mod catalog;
mod env;
mod model;

pub use env::OvercookedV2Env;
pub use model::{
    Action, AgentState, Direction, EventRecord, JointAction, LayoutDocument, ParsedLayout,
    Position, PrivateState, PublicState, Readout, ResolvedTask, RuntimeMetrics, TerminalMetrics,
};

pub fn sha256_digest(bytes: &[u8]) -> String {
    catalog::sha256_hex(bytes)
}
