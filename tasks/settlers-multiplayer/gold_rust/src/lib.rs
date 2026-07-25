//! Owned Rust authority for the symbolic settlers-rules emulator.
//!
//! This crate deliberately models rules and event semantics only.  It has no
//! upstream engine, renderer, or brand-specific runtime dependency.
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

pub const AGENTS: [&str; 4] = ["agent_0", "agent_1", "agent_2", "agent_3"];
const RESOURCES: [&str; 5] = ["wood", "brick", "sheep", "wheat", "ore"];
const DICE: [i32; 10] = [5, 8, 6, 9, 7, 10, 4, 11, 3, 12];
const DEV_DECK: [&str; 7] = ["knight", "knight", "knight", "victory_point", "road_building", "monopoly", "year_of_plenty"];
const TILES: [(&str, i32, [usize; 4]); 12] = [
    ("wood", 5, [0, 1, 2, 3]), ("brick", 8, [3, 4, 5, 6]),
    ("sheep", 6, [6, 7, 8, 9]), ("wheat", 9, [9, 10, 11, 12]),
    ("ore", 4, [12, 13, 14, 15]), ("wood", 10, [15, 16, 17, 18]),
    ("wheat", 3, [18, 19, 20, 21]), ("sheep", 11, [21, 22, 23, 0]),
    ("ore", 5, [1, 7, 13, 19]), ("brick", 6, [2, 8, 14, 20]),
    ("wood", 9, [4, 10, 16, 22]), ("wheat", 8, [5, 11, 17, 23]),
];

fn edge(edge: usize) -> (usize, usize) { (edge, (edge + 1) % 24) }
fn agent(index: usize) -> String { AGENTS[index].to_string() }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Player {
    pub agent_id: String,
    pub resources: BTreeMap<String, i32>,
    pub settlements: Vec<usize>,
    pub cities: Vec<usize>,
    pub roads: Vec<usize>,
    pub dev_cards: Vec<String>,
    pub played_knights: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct State {
    pub seed: i32,
    pub turn: usize,
    pub current_player: usize,
    pub robber_tile: usize,
    pub robber_pending: bool,
    pub pending_trade: Option<Trade>,
    pub dev_cursor: usize,
    pub longest_road_owner: Option<String>,
    pub largest_army_owner: Option<String>,
    pub terminated: bool,
    pub winner: Option<String>,
    pub termination_reason: Option<String>,
    pub players: Vec<Player>,
    pub nev: Vec<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trade { pub from: String, pub to: String, pub give: String, pub want: String }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlersEnv { pub state: State, pub max_turns: usize }

impl SettlersEnv {
    pub fn reset(seed: i32, max_turns: usize) -> Self {
        let starts = [[0, 3], [6, 9], [12, 15], [18, 21]];
        let players = (0..4).map(|index| Player {
            agent_id: agent(index), resources: resources(), settlements: starts[index].to_vec(),
            cities: vec![], roads: starts[index].to_vec(), dev_cards: vec![], played_knights: 0,
        }).collect();
        let mut env = Self { state: State { seed, turn: 0, current_player: 0, robber_tile: 0, robber_pending: false, pending_trade: None, dev_cursor: 0, longest_road_owner: None, largest_army_owner: None, terminated: false, winner: None, termination_reason: None, players, nev: vec![] }, max_turns };
        env.event("game_started", json!({"seed": seed, "players": AGENTS, "victory_points_to_win": 10})); env
    }

    pub fn current_agent(&self) -> String { agent(self.state.current_player) }
    fn player_index(&self, agent_id: &str) -> usize { self.state.players.iter().position(|p| p.agent_id == agent_id).expect("known player") }
    fn player(&self, agent_id: &str) -> &Player { &self.state.players[self.player_index(agent_id)] }
    fn player_mut(&mut self, agent_id: &str) -> &mut Player { let index = self.player_index(agent_id); &mut self.state.players[index] }
    fn event(&mut self, kind: &str, payload: Value) { self.state.nev.push(json!({"turn": self.state.turn, "kind": kind, "payload": payload})); }
    fn illegal(&mut self, actor: &str, reason: &str) { self.event("illegal_action", json!({"agent_id": actor, "reason": reason})); }
    fn action_kind(action: &Value) -> Option<&str> { action.as_str().or_else(|| action.get("kind").and_then(Value::as_str)) }
    fn action_str<'a>(action: &'a Value, key: &str) -> Option<&'a str> { action.get(key).and_then(Value::as_str) }
    fn action_index(action: &Value, key: &str) -> Option<usize> { action.get(key).and_then(Value::as_u64).map(|v| v as usize) }
    fn legal(&self, kind: &str) -> bool {
        if self.state.robber_pending { return kind == "move_robber"; }
        matches!(kind, "end_turn" | "build_road" | "build_settlement" | "build_city" | "bank_trade" | "trade_propose" | "trade_accept" | "trade_reject" | "buy_dev" | "play_dev")
    }

    pub fn step(&mut self, action: Value) {
        if self.state.terminated { return; }
        let actor = self.current_agent();
        let die = DICE[((self.state.seed as usize) + self.state.turn) % DICE.len()];
        self.event("dice", json!({"agent_id": actor, "value": die}));
        if die == 7 { self.discard_for_robber(); self.state.robber_pending = true; self.event("robber", json!({"agent_id": actor, "phase": "required"})); } else { self.produce(die); }
        let Some(kind) = Self::action_kind(&action) else { self.illegal(&actor, "malformed_action"); return; };
        if !self.legal(kind) { self.illegal(&actor, "not_legal_in_current_phase"); return; }
        match kind {
            "end_turn" => self.event("turn_end", json!({"agent_id": actor})),
            "move_robber" => self.move_robber(&actor, &action),
            "build_road" => self.build_road(&actor, &action),
            "build_settlement" => self.build_settlement(&actor, &action),
            "build_city" => self.build_city(&actor, &action),
            "bank_trade" => self.bank_trade(&actor, &action),
            "trade_propose" => self.trade_propose(&actor, &action),
            "trade_accept" => self.trade_accept(&actor),
            "trade_reject" => self.trade_reject(&actor),
            "buy_dev" => self.buy_dev(&actor),
            "play_dev" => self.play_dev(&actor, &action),
            _ => self.illegal(&actor, "unknown_action"),
        }
        if !self.state.robber_pending {
            self.update_awards(); self.check_terminal();
            if !self.state.terminated { self.state.current_player = (self.state.current_player + 1) % 4; self.state.turn += 1; }
        }
    }

    fn can_pay(&self, actor: &str, cost: &[(&str, i32)]) -> bool { cost.iter().all(|(r, n)| self.player(actor).resources.get(*r).copied().unwrap_or(0) >= *n) }
    fn pay(&mut self, actor: &str, cost: &[(&str, i32)]) -> bool {
        if !self.can_pay(actor, cost) { return false; }
        let player = self.player_mut(actor); for (r, n) in cost { *player.resources.get_mut(*r).unwrap() -= *n; } true
    }
    fn all_roads(&self) -> BTreeSet<usize> { self.state.players.iter().flat_map(|p| p.roads.iter().copied()).collect() }

    fn build_road(&mut self, actor: &str, action: &Value) {
        let Some(road) = Self::action_index(action, "edge") else { self.illegal(actor, "road_unavailable"); return; };
        let free = action.get("_from_dev").and_then(Value::as_bool).unwrap_or(false);
        if road >= 24 || self.all_roads().contains(&road) { self.illegal(actor, "road_unavailable"); return; }
        let (a, b) = edge(road); let player = self.player(actor);
        let connected = player.settlements.iter().chain(player.cities.iter()).any(|v| *v == a || *v == b) || player.roads.iter().any(|r| { let (x, y) = edge(*r); x == a || x == b || y == a || y == b });
        if !connected || (!free && !self.can_pay(actor, &[("wood", 1), ("brick", 1)])) { self.illegal(actor, "road_cost_or_network"); return; }
        if !free { self.pay(actor, &[("wood", 1), ("brick", 1)]); }
        self.player_mut(actor).roads.push(road); self.event("build", json!({"agent_id": actor, "piece": "road", "edge": road, "free": free}));
    }
    fn build_settlement(&mut self, actor: &str, action: &Value) {
        let Some(vertex) = Self::action_index(action, "vertex") else { self.illegal(actor, "settlement_cost_network_or_distance"); return; };
        let occupied: BTreeSet<usize> = self.state.players.iter().flat_map(|p| p.settlements.iter().chain(p.cities.iter()).copied()).collect();
        let player = self.player(actor); let connected = player.roads.iter().any(|r| { let (a, b) = edge(*r); a == vertex || b == vertex });
        if vertex >= 24 || occupied.contains(&vertex) || occupied.contains(&((vertex + 23) % 24)) || occupied.contains(&((vertex + 1) % 24)) || !connected || !self.pay(actor, &[("wood", 1), ("brick", 1), ("sheep", 1), ("wheat", 1)]) { self.illegal(actor, "settlement_cost_network_or_distance"); return; }
        self.player_mut(actor).settlements.push(vertex); self.event("build", json!({"agent_id": actor, "piece": "settlement", "vertex": vertex})); let total = self.victory_points(actor); self.event("vp", json!({"agent_id": actor, "total": total, "reason": "settlement"}));
    }
    fn build_city(&mut self, actor: &str, action: &Value) {
        let Some(vertex) = Self::action_index(action, "vertex") else { self.illegal(actor, "city_cost_or_ownership"); return; };
        if !self.player(actor).settlements.contains(&vertex) || !self.pay(actor, &[("ore", 3), ("wheat", 2)]) { self.illegal(actor, "city_cost_or_ownership"); return; }
        let player = self.player_mut(actor); player.settlements.retain(|v| *v != vertex); player.cities.push(vertex); self.event("build", json!({"agent_id": actor, "piece": "city", "vertex": vertex})); let total = self.victory_points(actor); self.event("vp", json!({"agent_id": actor, "total": total, "reason": "city"}));
    }
    fn bank_trade(&mut self, actor: &str, action: &Value) {
        let (Some(give), Some(want)) = (Self::action_str(action, "give"), Self::action_str(action, "want")) else { self.illegal(actor, "bank_trade_ratio_or_resource"); return; };
        if !RESOURCES.contains(&give) || !RESOURCES.contains(&want) || give == want || self.player(actor).resources[give] < 4 { self.illegal(actor, "bank_trade_ratio_or_resource"); return; }
        let player = self.player_mut(actor); *player.resources.get_mut(give).unwrap() -= 4; *player.resources.get_mut(want).unwrap() += 1; self.event("trade_bank", json!({"agent_id": actor, "give": {give: 4}, "want": {want: 1}}));
    }
    fn trade_propose(&mut self, actor: &str, action: &Value) {
        let (Some(to), Some(give), Some(want)) = (Self::action_str(action, "to"), Self::action_str(action, "give"), Self::action_str(action, "want")) else { self.illegal(actor, "trade_proposal_invalid"); return; };
        if !AGENTS.contains(&to) || to == actor || !RESOURCES.contains(&give) || !RESOURCES.contains(&want) || self.player(actor).resources[give] < 1 { self.illegal(actor, "trade_proposal_invalid"); return; }
        self.state.pending_trade = Some(Trade { from: actor.into(), to: to.into(), give: give.into(), want: want.into() }); self.event("trade_proposed", json!({"agent_id": actor, "to": to, "give": {give: 1}, "want": {want: 1}}));
    }
    fn trade_accept(&mut self, actor: &str) {
        let Some(offer) = self.state.pending_trade.clone() else { self.illegal(actor, "trade_accept_unavailable"); return; };
        if offer.to != actor || self.player(actor).resources[&offer.want] < 1 || self.player(&offer.from).resources[&offer.give] < 1 { self.illegal(actor, "trade_accept_unavailable"); return; }
        *self.player_mut(&offer.from).resources.get_mut(&offer.give).unwrap() -= 1; *self.player_mut(actor).resources.get_mut(&offer.give).unwrap() += 1;
        *self.player_mut(actor).resources.get_mut(&offer.want).unwrap() -= 1; *self.player_mut(&offer.from).resources.get_mut(&offer.want).unwrap() += 1;
        self.state.pending_trade = None; self.event("trade_accepted", json!({"agent_id": actor, "from_agent": offer.from}));
    }
    fn trade_reject(&mut self, actor: &str) { let Some(offer) = self.state.pending_trade.clone() else { self.illegal(actor, "trade_reject_unavailable"); return; }; if offer.to != actor { self.illegal(actor, "trade_reject_unavailable"); return; } self.state.pending_trade = None; self.event("trade_rejected", json!({"agent_id": actor, "from_agent": offer.from})); }
    fn buy_dev(&mut self, actor: &str) {
        if self.state.dev_cursor >= DEV_DECK.len() || !self.pay(actor, &[("ore", 1), ("sheep", 1), ("wheat", 1)]) { self.illegal(actor, "dev_card_cost_or_empty_deck"); return; }
        let card = DEV_DECK[self.state.dev_cursor].to_string(); self.state.dev_cursor += 1; self.player_mut(actor).dev_cards.push(card.clone()); self.event("dev_card", json!({"agent_id": actor, "phase": "bought", "card": card}));
    }
    fn play_dev(&mut self, actor: &str, action: &Value) {
        let Some(card) = Self::action_str(action, "card") else { self.illegal(actor, "dev_card_unowned"); return; };
        let Some(position) = self.player(actor).dev_cards.iter().position(|c| c == card) else { self.illegal(actor, "dev_card_unowned"); return; };
        self.player_mut(actor).dev_cards.remove(position);
        match card {
            "knight" => { self.player_mut(actor).played_knights += 1; self.event("dev_card", json!({"agent_id": actor, "phase": "played", "card": card})); self.move_robber(actor, action); }
            "victory_point" => { let total = self.victory_points(actor); self.event("vp", json!({"agent_id": actor, "total": total, "reason": "development"})); }
            "road_building" => { let edge = action.get("edge").cloned().unwrap_or(Value::Null); self.build_road(actor, &json!({"edge": edge, "_from_dev": true})); }
            "monopoly" => { let Some(resource) = Self::action_str(action, "resource") else { self.illegal(actor, "monopoly_resource"); return; }; if !RESOURCES.contains(&resource) { self.illegal(actor, "monopoly_resource"); return; } let mut gained = 0; for opponent in AGENTS { if opponent != actor { let amount = self.player(opponent).resources[resource]; *self.player_mut(opponent).resources.get_mut(resource).unwrap() = 0; gained += amount; } } *self.player_mut(actor).resources.get_mut(resource).unwrap() += gained; self.event("dev_card", json!({"agent_id": actor, "phase": "played", "card": card, "resource": resource, "gained": gained})); }
            _ => { let Some(resource) = Self::action_str(action, "resource") else { self.illegal(actor, "year_of_plenty_resource"); return; }; if !RESOURCES.contains(&resource) { self.illegal(actor, "year_of_plenty_resource"); return; } *self.player_mut(actor).resources.get_mut(resource).unwrap() += 2; self.event("dev_card", json!({"agent_id": actor, "phase": "played", "card": card, "resource": resource})); }
        }
    }
    fn move_robber(&mut self, actor: &str, action: &Value) {
        let Some(tile) = Self::action_index(action, "tile") else { self.illegal(actor, "robber_tile_invalid"); return; };
        if tile >= TILES.len() || tile == self.state.robber_tile { self.illegal(actor, "robber_tile_invalid"); return; }
        self.state.robber_tile = tile; self.state.robber_pending = false; let victim = Self::action_str(action, "victim").map(String::from); let mut stolen: Option<String> = None;
        if let Some(target) = victim.as_deref() { if AGENTS.contains(&target) && target != actor { for resource in RESOURCES { if self.player(target).resources[resource] > 0 { *self.player_mut(target).resources.get_mut(resource).unwrap() -= 1; *self.player_mut(actor).resources.get_mut(resource).unwrap() += 1; stolen = Some(resource.to_string()); break; } } } }
        self.event("robber", json!({"agent_id": actor, "phase": "moved", "tile": tile, "victim": victim, "stolen": stolen}));
    }
    fn discard_for_robber(&mut self) { for actor in AGENTS { let total: i32 = self.player(actor).resources.values().sum(); if total > 7 { let mut drop = total / 2; for resource in ["ore", "wheat", "sheep", "brick", "wood"] { let amount = self.player(actor).resources[resource].min(drop); *self.player_mut(actor).resources.get_mut(resource).unwrap() -= amount; drop -= amount; if drop == 0 { break; } } self.event("robber", json!({"agent_id": actor, "phase": "discarded"})); } } }
    fn produce(&mut self, die: i32) { for (tile, (resource, number, vertices)) in TILES.iter().enumerate() { if *number != die || tile == self.state.robber_tile { continue; } for actor in AGENTS { let p = self.player(actor); let amount = vertices.iter().map(|v| if p.cities.contains(v) { 2 } else if p.settlements.contains(v) { 1 } else { 0 }).sum::<i32>(); if amount > 0 { *self.player_mut(actor).resources.get_mut(*resource).unwrap() += amount; self.event("produce", json!({"agent_id": actor, "resource": resource, "amount": amount, "tile": tile})); } } } }
    fn road_length(&self, player: &Player) -> usize { let mut remaining: BTreeSet<usize> = player.roads.iter().copied().collect(); let mut longest = 0; while let Some(first) = remaining.iter().next().copied() { remaining.remove(&first); let mut stack = vec![first]; let mut size = 0; while let Some(current) = stack.pop() { size += 1; let (a, b) = edge(current); let linked: Vec<usize> = remaining.iter().copied().filter(|other| { let (x, y) = edge(*other); a == x || a == y || b == x || b == y }).collect(); for candidate in linked { remaining.remove(&candidate); stack.push(candidate); } } longest = longest.max(size); } longest }
    fn update_awards(&mut self) { let mut road_scores: Vec<(usize, String)> = self.state.players.iter().map(|p| (self.road_length(p), p.agent_id.clone())).collect(); road_scores.sort(); if let Some((length, owner)) = road_scores.last().cloned() { let current = self.state.longest_road_owner.as_ref().map(|a| self.road_length(self.player(a))).unwrap_or(0); if length >= 5 && (self.state.longest_road_owner.is_none() || length > current) { self.state.longest_road_owner = Some(owner.clone()); self.event("longest_road", json!({"agent_id": owner, "length": length})); } } let mut armies: Vec<(i32, String)> = self.state.players.iter().map(|p| (p.played_knights, p.agent_id.clone())).collect(); armies.sort(); if let Some((knights, owner)) = armies.last().cloned() { let current = self.state.largest_army_owner.as_ref().map(|a| self.player(a).played_knights).unwrap_or(0); if knights >= 3 && (self.state.largest_army_owner.is_none() || knights > current) { self.state.largest_army_owner = Some(owner.clone()); self.event("largest_army", json!({"agent_id": owner, "knights": knights})); } } }
    fn check_terminal(&mut self) { let winner = AGENTS.iter().find(|a| self.victory_points(a) >= 10).map(|a| a.to_string()); if let Some(winner) = winner { self.state.terminated = true; self.state.winner = Some(winner.clone()); self.state.termination_reason = Some("victory_points".into()); self.event("terminal", json!({"winner": winner, "reason": "victory_points"})); } else if self.state.turn + 1 >= self.max_turns { self.state.terminated = true; self.state.termination_reason = Some("turn_limit".into()); self.event("terminal", json!({"winner": Value::Null, "reason": "turn_limit"})); } }
    pub fn victory_points(&self, actor: &str) -> i32 { let p = self.player(actor); p.settlements.len() as i32 + 2 * p.cities.len() as i32 + p.dev_cards.iter().filter(|c| c.as_str() == "victory_point").count() as i32 + if self.state.longest_road_owner.as_deref() == Some(actor) { 2 } else { 0 } + if self.state.largest_army_owner.as_deref() == Some(actor) { 2 } else { 0 } }
    pub fn checkpoint(&self) -> Value { json!({"schema_version": "gamebench.checkpoint.v1", "env_family": "settlers-multiplayer", "sim": self.state, "max_turns": self.max_turns}) }
    pub fn restore(checkpoint: Value) -> Result<Self, String> { if checkpoint["schema_version"] != "gamebench.checkpoint.v1" || checkpoint["env_family"] != "settlers-multiplayer" { return Err("unsupported settlers checkpoint".into()); } Ok(Self { state: serde_json::from_value(checkpoint["sim"].clone()).map_err(|e| e.to_string())?, max_turns: checkpoint["max_turns"].as_u64().unwrap_or(240) as usize }) }
    pub fn compact_projection(&self) -> Value { json!({"turn": self.state.turn, "current_agent": if self.state.terminated { Value::Null } else { json!(self.current_agent()) }, "robber_tile": self.state.robber_tile, "robber_pending": self.state.robber_pending, "pending_trade": self.state.pending_trade, "longest_road_owner": self.state.longest_road_owner, "largest_army_owner": self.state.largest_army_owner, "terminated": self.state.terminated, "winner": self.state.winner, "termination_reason": self.state.termination_reason, "players": self.state.players.iter().map(|p| json!({"agent_id": p.agent_id, "resources": p.resources, "settlements": sorted(&p.settlements), "cities": sorted(&p.cities), "roads": sorted(&p.roads), "dev_cards": p.dev_cards, "played_knights": p.played_knights, "victory_points": self.victory_points(&p.agent_id)})).collect::<Vec<_>>(), "event_kinds": self.state.nev.iter().map(|e| e["kind"].clone()).collect::<Vec<_>>()}) }
}

fn resources() -> BTreeMap<String, i32> { RESOURCES.into_iter().map(|resource| (resource.to_string(), 4)).collect() }
fn sorted(values: &[usize]) -> Vec<usize> { let mut out = values.to_vec(); out.sort(); out }
