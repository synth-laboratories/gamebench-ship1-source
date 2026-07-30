//! Independent Rust authority for the symbolic Fog Duel Lite contract.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{self, Read};
use std::path::PathBuf;

const AGENTS: [&str; 2] = ["agent_0", "agent_1"];

#[derive(Clone, Debug, Deserialize)]
struct Scenario {
    id: String,
    seed: i64,
    #[serde(default = "default_max_rounds")]
    max_rounds: i64,
    passages: Vec<Vec<i64>>,
    deposits: Vec<Deposit>,
    #[serde(default)]
    initial: Initial,
}

fn default_max_rounds() -> i64 { 80 }

#[derive(Clone, Debug, Default, Deserialize)]
struct Initial {
    #[serde(default)] players: BTreeMap<String, InitialPlayer>,
    #[serde(default)] units: Vec<Unit>,
    #[serde(default)] buildings: Vec<InitialBuilding>,
}

#[derive(Clone, Debug, Default, Deserialize)]
struct InitialPlayer {
    credits: Option<i64>, uranium: Option<i64>, enemy_base_discovered: Option<bool>, known_enemy_base_pos: Option<Vec<i64>>,
}

#[derive(Clone, Debug, Deserialize)]
struct InitialBuilding {
    id: String,
    owner: Option<String>,
    kind: Option<String>,
    pos: Option<Vec<i64>>,
    hp: Option<i64>,
    under_construction: Option<bool>,
    ready_round: Option<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Deposit {
    kind: String,
    pos: Vec<i64>,
    reserve: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    central: Option<bool>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Unit { id: String, owner: String, kind: String, pos: Vec<i64> }

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Building {
    id: String, owner: String, kind: String, pos: Vec<i64>, hp: i64, under_construction: bool, ready_round: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Board { size: Vec<i64>, mountains: Vec<Vec<i64>>, passages: Vec<Vec<i64>>, deposits: Vec<Deposit> }

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Player {
    credits: i64,
    uranium: i64,
    enemy_base_discovered: bool,
    known_enemy_base_pos: Option<Vec<i64>>,
    remembered_enemy_buildings: Vec<Value>,
    remembered_enemy_deposits: Vec<Value>,
    last_turn_results: Vec<Value>,
    score: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Diplomacy { ceasefire_remaining: i64, pending: Vec<Value>, next_proposal_id: i64 }

#[derive(Clone, Debug, Serialize, Deserialize)]
struct State {
    schema_version: String,
    scenario_id: String,
    seed: i64,
    max_rounds: i64,
    round: i64,
    active_agent: String,
    half_turn: i64,
    board: Board,
    players: BTreeMap<String, Player>,
    units: Vec<Unit>,
    buildings: Vec<Building>,
    diplomacy: Diplomacy,
    queued_launches: Vec<String>,
    action_flags: BTreeMap<String, Vec<String>>,
    next_entity_id: i64,
    terminal: Option<Value>,
    rng_state: i64,
}

struct Engine { state: State, events: Vec<Value>, next_seq: i64 }

fn base_pos(agent: &str) -> Vec<i64> { if agent == "agent_0" { vec![1, 3] } else { vec![11, 3] } }
fn other(agent: &str) -> String { if agent == "agent_0" { "agent_1".to_string() } else { "agent_0".to_string() } }
fn dist(a: &[i64], b: &[i64]) -> i64 { (a[0]-b[0]).abs().max((a[1]-b[1]).abs()) }
fn valid_pos(pos: &Value) -> Option<Vec<i64>> { let xs = pos.as_array()?; if xs.len()!=2 { return None; } let x=xs[0].as_i64()?; let y=xs[1].as_i64()?; if (0..13).contains(&x) && (0..7).contains(&y) { Some(vec![x,y]) } else { None } }
fn unit_spec(kind: &str) -> Option<(i64,i64,i64,i64,&'static str)> { match kind { "drone"=>Some((2,3,3,0,"air")), "sam"=>Some((3,2,2,2,"ground")), "tank"=>Some((4,2,1,2,"ground")), "fighter"=>Some((4,3,2,2,"air")), _=>None } }
fn building_spec(kind: &str) -> Option<(i64,i64,i64)> { match kind { "base"=>Some((4,2,0)), "credit_mine"=>Some((2,1,2)), "uranium_mine"=>Some((2,1,2)), "silo"=>Some((3,1,5)), _=>None } }

impl Engine {
    fn reset(scenario: Scenario) -> Self {
        let mut players = BTreeMap::new();
        for agent in AGENTS { let override_ = scenario.initial.players.get(agent); players.insert(agent.to_string(), Player { credits: override_.and_then(|p|p.credits).unwrap_or(5), uranium: override_.and_then(|p|p.uranium).unwrap_or(0), enemy_base_discovered: override_.and_then(|p|p.enemy_base_discovered).unwrap_or(false), known_enemy_base_pos: override_.and_then(|p|p.known_enemy_base_pos.clone()), remembered_enemy_buildings: vec![], remembered_enemy_deposits: vec![], last_turn_results: vec![], score: 0.0 }); }
        let mut buildings: Vec<Building> = AGENTS.iter().map(|agent| Building { id: format!("{}_base", agent), owner: agent.to_string(), kind: "base".to_string(), pos: base_pos(agent), hp: 4, under_construction: false, ready_round: 1 }).collect();
        for item in scenario.initial.buildings {
            if let Some(existing) = buildings.iter_mut().find(|b| b.id == item.id) { if let Some(hp)=item.hp { existing.hp=hp; } if let Some(owner)=item.owner { existing.owner=owner; } if let Some(kind)=item.kind { existing.kind=kind; } if let Some(pos)=item.pos { existing.pos=pos; } if let Some(construction)=item.under_construction { existing.under_construction=construction; } if let Some(round)=item.ready_round { existing.ready_round=round; } } else { let kind=item.kind.unwrap_or_else(||"silo".to_string()); let (hp,_,_)=building_spec(&kind).unwrap(); buildings.push(Building { id:item.id, owner:item.owner.unwrap_or_else(||"agent_0".to_string()), kind, pos:item.pos.unwrap_or_else(||vec![3,3]), hp:item.hp.unwrap_or(hp), under_construction:item.under_construction.unwrap_or(false), ready_round:item.ready_round.unwrap_or(1) }); }
        }
        let mountains=(0..7).filter(|row| !scenario.passages.contains(&vec![6,*row])).map(|row|vec![6,row]).collect();
        let state=State { schema_version:"gamebench.fog_duel_lite.state.v0".to_string(), scenario_id:scenario.id.clone(), seed:scenario.seed, max_rounds:scenario.max_rounds, round:1, active_agent:"agent_0".to_string(), half_turn:0, board:Board{size:vec![13,7],mountains,passages:scenario.passages,deposits:scenario.deposits}, players, units:scenario.initial.units, buildings, diplomacy:Diplomacy{ceasefire_remaining:0,pending:vec![],next_proposal_id:1}, queued_launches:vec![], action_flags:BTreeMap::new(), next_entity_id:1, terminal:None, rng_state:scenario.seed };
        let mut engine=Self{state,events:vec![],next_seq:0}; engine.emit("match_started",None,json!({"scenario_id":scenario.id,"seed":scenario.seed})); engine.begin_half_turn("agent_0"); engine
    }

    fn emit(&mut self, kind:&str, actor:Option<&str>, payload:Value) { self.events.push(json!({"schema_version":"gamebench.nev.v1","seq":self.next_seq,"round":self.state.round,"half_turn":self.state.half_turn,"actor":actor,"kind":kind,"payload":payload})); self.next_seq+=1; }
    fn begin_half_turn(&mut self, actor:&str) { self.state.active_agent=actor.to_string(); self.state.action_flags.clear(); let complete:Vec<String>=self.state.buildings.iter().filter(|b|b.owner==actor && b.under_construction && b.ready_round<=self.state.round).map(|b|b.id.clone()).collect(); for id in complete { if let Some(b)=self.state.buildings.iter_mut().find(|b|b.id==id) { b.under_construction=false; } self.emit("building_completed",Some(actor),json!({"building_id":id})); } self.emit("half_turn_started",Some(actor),json!({"order":self.state.half_turn})); }
    fn illegal(&mut self, actor:&str, index:Option<usize>, action:&Value, reason:&str) { let kind=action.get("kind").and_then(Value::as_str).unwrap_or("invalid"); self.emit("illegal_action",Some(actor),json!({"action_index":index,"submitted_kind":kind,"reason_code":reason})); self.state.players.get_mut(actor).unwrap().last_turn_results.push(json!({"action_index":index,"ok":false,"reason_code":reason})); }
    fn accepted(&mut self, actor:&str, index:usize, action:&Value, transition:&str, extra:Value) { let mut payload=json!({"action_index":index,"action":action,"transition":transition}); if let (Some(a),Some(b))=(payload.as_object_mut(),extra.as_object()) { for (k,v) in b { a.insert(k.clone(),v.clone()); } } self.emit("action_applied",Some(actor),payload); self.state.players.get_mut(actor).unwrap().last_turn_results.push(json!({"action_index":index,"ok":true,"transition":transition})); }
    fn visible(&self, agent:&str) -> BTreeSet<(i64,i64)> { let mut out=BTreeSet::new(); let mut sources:Vec<(Vec<i64>,i64)>=vec![]; for u in &self.state.units { if u.owner==agent { sources.push((u.pos.clone(),unit_spec(&u.kind).unwrap().2)); } } for b in &self.state.buildings { if b.owner==agent { sources.push((b.pos.clone(),building_spec(&b.kind).unwrap().1)); } } for (pos,radius) in sources { for x in (pos[0]-radius).max(0)..=(pos[0]+radius).min(12) { for y in (pos[1]-radius).max(0)..=(pos[1]+radius).min(6) { out.insert((x,y)); } } } out }
    fn open(&self,pos:&[i64],layer:&str,ignored:Option<&str>)->bool { if layer=="ground" && self.state.board.mountains.contains(&pos.to_vec()) { return false; } if layer=="ground" && self.state.buildings.iter().any(|b|b.pos==pos) {return false;} !self.state.units.iter().any(|u|Some(u.id.as_str())!=ignored && u.pos==pos && unit_spec(&u.kind).unwrap().4==layer) }
    fn line_clear(&self,start:&[i64],end:&[i64],buildings:bool)->bool { let steps=(start[0]-end[0]).abs().max((start[1]-end[1]).abs()); if steps<=1{return true;} for n in 1..steps { let pos=vec![((start[0] as f64+(end[0]-start[0]) as f64*n as f64/steps as f64).round()) as i64,((start[1] as f64+(end[1]-start[1]) as f64*n as f64/steps as f64).round()) as i64]; if self.state.board.mountains.contains(&pos) || (buildings && self.state.buildings.iter().any(|b|b.pos==pos)) {return false;} } true }
    fn owned_unit_index(&self,actor:&str,id:&str)->Option<usize>{self.state.units.iter().position(|u|u.owner==actor&&u.id==id)}
    fn in_own(&self,actor:&str,pos:&[i64])->bool{if actor=="agent_0"{pos[0]<=5}else{pos[0]>=7}}
    fn bomb_cost(&self)->i64{let reduction=if self.state.round<40{0}else{2*(1+(self.state.round-40)/10)}; let mut cost=(25-reduction).max(13);if self.state.diplomacy.ceasefire_remaining>0{cost+=6;}cost}

    fn apply_action(&mut self, actor:&str,index:usize,action:&Value){let kind=match action.get("kind").and_then(Value::as_str){Some(k)=>k,None=>{self.illegal(actor,Some(index),action,"invalid_schema");return;}};match kind{"wait"=>self.accepted(actor,index,action,"wait",json!({})),"produce"=>self.produce(actor,index,action),"move"=>self.move_unit(actor,index,action),"attack"=>self.attack(actor,index,action),"build"=>self.build(actor,index,action),"launch"=>self.launch(actor,index,action),_=>self.illegal(actor,Some(index),action,"unknown_action")}}
    fn produce(&mut self,actor:&str,index:usize,action:&Value){let kind=match action.get("unit").and_then(Value::as_str).and_then(unit_spec){Some(s)=>s,None=>{self.illegal(actor,Some(index),action,"unknown_unit");return;}};if self.state.players[actor].credits<kind.0{self.illegal(actor,Some(index),action,"insufficient_credits");return;}let base=base_pos(actor);let mut cells=vec![];for dx in -1..=1{for dy in -1..=1{if dx!=0||dy!=0{let p=vec![base[0]+dx,base[1]+dy];if p[0]>=0&&p[0]<13&&p[1]>=0&&p[1]<7&&self.open(&p,kind.4,None){cells.push(p);}}}}cells.sort();if cells.is_empty(){self.illegal(actor,Some(index),action,"base_spawn_blocked");return;}self.state.players.get_mut(actor).unwrap().credits-=kind.0;let name=action["unit"].as_str().unwrap();let unit=Unit{id:format!("{}_{}_{}",actor,name,self.state.next_entity_id),owner:actor.to_string(),kind:name.to_string(),pos:cells[0].clone()};self.state.next_entity_id+=1;self.state.units.push(unit.clone());self.accepted(actor,index,action,"produce",json!({"unit":unit}));self.emit("unit_produced",Some(actor),json!({"unit":unit}));}
    fn move_unit(&mut self,actor:&str,index:usize,action:&Value){let id=match action.get("unit_id").and_then(Value::as_str){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"unit_not_found");return;}};let dest=match action.get("to").and_then(valid_pos){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"move_out_of_range");return;}};let ix=match self.owned_unit_index(actor,id){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"unit_not_found");return;}};let unit=self.state.units[ix].clone();let spec=unit_spec(&unit.kind).unwrap();if self.state.action_flags.get("moved").map(|v|v.contains(&unit.id)).unwrap_or(false){self.illegal(actor,Some(index),action,"unit_already_moved");return;}if dist(&unit.pos,&dest)>spec.1{self.illegal(actor,Some(index),action,"move_out_of_range");return;}if !self.open(&dest,spec.4,Some(&unit.id))||(spec.4=="ground"&&!self.line_clear(&unit.pos,&dest,true)){self.illegal(actor,Some(index),action,"move_blocked");return;}self.state.units[ix].pos=dest.clone();self.state.action_flags.entry("moved".to_string()).or_default().push(unit.id.clone());self.accepted(actor,index,action,"move",json!({"unit_id":unit.id,"from":unit.pos,"to":dest}));self.emit("unit_moved",Some(actor),json!({"unit_id":unit.id,"from":unit.pos,"to":dest}));}
    fn attack(&mut self,actor:&str,index:usize,action:&Value){let id=match action.get("unit_id").and_then(Value::as_str){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"unit_not_found");return;}};let target=match action.get("target_pos").and_then(valid_pos){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"attack_out_of_range");return;}};let ix=match self.owned_unit_index(actor,id){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"unit_not_found");return;}};let unit=self.state.units[ix].clone();let spec=unit_spec(&unit.kind).unwrap();if self.state.action_flags.get("attacked").map(|v|v.contains(&unit.id)).unwrap_or(false){self.illegal(actor,Some(index),action,"unit_already_attacked");return;}if self.state.diplomacy.ceasefire_remaining>0{self.illegal(actor,Some(index),action,"ceasefire_active");return;}if unit.kind=="drone"||dist(&unit.pos,&target)>spec.3{self.illegal(actor,Some(index),action,"attack_out_of_range");return;}if !self.visible(actor).contains(&(target[0],target[1])){self.illegal(actor,Some(index),action,"target_not_visible");return;}if unit.kind!="fighter"&&!self.line_clear(&unit.pos,&target,true){self.illegal(actor,Some(index),action,"line_of_sight_blocked");return;}let enemy_unit=self.state.units.iter().position(|u|u.owner!=actor&&u.pos==target);let enemy_building=self.state.buildings.iter().position(|b|b.owner!=actor&&b.pos==target);let mut combat=Value::Null;let mut destroyed:Option<Building>=None;if let Some(uix)=enemy_unit{let victim=self.state.units[uix].clone();let legal=match unit.kind.as_str(){"fighter"=>matches!(victim.kind.as_str(),"tank"|"drone"|"fighter"),"sam"=>matches!(victim.kind.as_str(),"drone"|"fighter"),"tank"=>matches!(victim.kind.as_str(),"tank"|"sam"),_=>false};if legal{self.state.units.remove(uix);combat=json!({"attacker":unit.id,"target":victim.id,"target_kind":victim.kind,"outcome":"destroyed"});}}else if let Some(bix)=enemy_building{if unit.kind=="tank"{self.state.buildings[bix].hp-=2;let victim=self.state.buildings[bix].clone();let dead=victim.hp<=0;combat=json!({"attacker":unit.id,"target":victim.id,"target_kind":victim.kind,"damage":2,"destroyed":dead});if dead{destroyed=Some(victim);}}}if combat.is_null(){self.illegal(actor,Some(index),action,"no_legal_target");return;}self.state.action_flags.entry("attacked".to_string()).or_default().push(unit.id.clone());self.accepted(actor,index,action,"attack",combat.clone());self.emit("combat_resolved",Some(actor),combat);if let Some(b)=destroyed{self.destroy_building(&b,actor);}}
    fn build(&mut self,actor:&str,index:usize,action:&Value){let kind=match action.get("building").and_then(Value::as_str){Some(v @ ("credit_mine"|"uranium_mine"|"silo"))=>v,_=>{self.illegal(actor,Some(index),action,"invalid_build");return;}};let pos=match action.get("pos").and_then(valid_pos){Some(v)=>v,None=>{self.illegal(actor,Some(index),action,"invalid_build");return;}};if !self.visible(actor).contains(&(pos[0],pos[1])){self.illegal(actor,Some(index),action,"cell_not_visible");return;}if self.state.buildings.iter().any(|b|b.pos==pos)||self.state.units.iter().any(|u|u.pos==pos&&unit_spec(&u.kind).unwrap().4=="ground"){self.illegal(actor,Some(index),action,"cell_occupied");return;}if self.state.board.mountains.contains(&pos)||AGENTS.iter().any(|a|dist(&pos,&base_pos(a))<=1){self.illegal(actor,Some(index),action,"invalid_build_cell");return;}let deposit=self.state.board.deposits.iter().find(|d|d.pos==pos&&d.reserve>0);if kind=="credit_mine"&&deposit.map(|d|d.kind.as_str())!=Some("credit"){self.illegal(actor,Some(index),action,"credit_deposit_required");return;}if kind=="uranium_mine"&&deposit.map(|d|d.kind.as_str())!=Some("uranium"){self.illegal(actor,Some(index),action,"uranium_deposit_required");return;}if kind=="silo"&&(deposit.is_some()||!self.in_own(actor,&pos)){self.illegal(actor,Some(index),action,"invalid_silo_position");return;}let (_,_,cost)=building_spec(kind).unwrap();if self.state.players[actor].credits<cost{self.illegal(actor,Some(index),action,"insufficient_credits");return;}self.state.players.get_mut(actor).unwrap().credits-=cost;let (hp,_,_)=building_spec(kind).unwrap();let building=Building{id:format!("{}_{}_{}",actor,kind,self.state.next_entity_id),owner:actor.to_string(),kind:kind.to_string(),pos,hp,under_construction:true,ready_round:self.state.round+1};self.state.next_entity_id+=1;self.state.buildings.push(building.clone());self.accepted(actor,index,action,"build",json!({"building":building}));self.emit("building_built",Some(actor),json!({"building":building}));}
    fn launch(&mut self,actor:&str,index:usize,action:&Value){let player=&self.state.players[actor];if !self.state.buildings.iter().any(|b|b.owner==actor&&b.kind=="silo"&&!b.under_construction){self.illegal(actor,Some(index),action,"no_operational_silo");return;}if !player.enemy_base_discovered{self.illegal(actor,Some(index),action,"enemy_base_unknown");return;}let cost=self.bomb_cost();if player.uranium<cost{self.illegal(actor,Some(index),action,"insufficient_uranium");return;}if self.state.queued_launches.contains(&actor.to_string()){self.illegal(actor,Some(index),action,"already_launched");return;}self.state.players.get_mut(actor).unwrap().uranium-=cost;self.state.queued_launches.push(actor.to_string());self.accepted(actor,index,action,"launch",json!({"bomb_cost":cost}));self.emit("launch_queued",Some(actor),json!({"bomb_cost":cost}));}
    fn apply_diplomacy(&mut self,actor:&str,diplomacy:&Value){
        let Some(object)=diplomacy.as_object() else { self.illegal(actor,None,&json!({"kind":"diplomacy"}),"invalid_diplomacy_schema"); return; };
        if let Some(proposal)=object.get("proposal") {
            if !proposal.is_null() {
                let kind=proposal.get("kind").and_then(Value::as_str);
                if !matches!(kind,Some("ceasefire"|"peace"|"ultimatum")) { self.illegal(actor,None,&json!({"kind":"diplomacy"}),"unknown_proposal"); }
                else {
                    let kind=kind.unwrap(); let minimum=if kind=="peace" {15} else {10}; let target=proposal.get("target_round").and_then(Value::as_i64);
                    if self.state.round<minimum || (kind=="ultimatum" && !target.map(|turn|turn>=self.state.round+1&&turn<=self.state.round+3).unwrap_or(false)) { self.illegal(actor,None,&json!({"kind":"diplomacy"}),"proposal_unavailable"); }
                    else { let id=format!("p_{}",self.state.diplomacy.next_proposal_id); self.state.diplomacy.next_proposal_id+=1; let item=json!({"proposal_id":id,"from":actor,"to":other(actor),"kind":kind,"target_round":target}); self.state.diplomacy.pending.push(item.clone()); self.emit("diplomacy_proposed",Some(actor),item); }
                }
            }
        }
        for response in object.get("responses").and_then(Value::as_array).cloned().unwrap_or_default() {
            let proposal_id=response.get("proposal_id").and_then(Value::as_str); let accept=response.get("accept").and_then(Value::as_bool);
            let found=proposal_id.and_then(|id|self.state.diplomacy.pending.iter().position(|item|item.get("proposal_id").and_then(Value::as_str)==Some(id)&&item.get("to").and_then(Value::as_str)==Some(actor)));
            if found.is_none() || accept.is_none() { self.illegal(actor,None,&json!({"kind":"diplomacy"}),"proposal_not_pending"); continue; }
            let pending=self.state.diplomacy.pending.remove(found.unwrap()); let accepted=accept.unwrap(); self.emit("diplomacy_resolved",Some(actor),json!({"proposal_id":proposal_id,"accepted":accepted}));
            if !accepted { continue; }
            match pending.get("kind").and_then(Value::as_str) { Some("ceasefire")=>self.state.diplomacy.ceasefire_remaining=3, Some("peace")=>self.terminal("peace",None,json!({"agent_0":1.0,"agent_1":1.0})), Some("ultimatum")=>{let proposer=pending["from"].as_str().unwrap();let scores=if proposer=="agent_0"{json!({"agent_0":3.0,"agent_1":0.5})}else{json!({"agent_0":0.5,"agent_1":3.0})};self.terminal("ultimatum",Some(proposer),scores);}, _=>{} }
        }
    }
    fn destroy_building(&mut self,building:&Building,actor:&str){if let Some(ix)=self.state.buildings.iter().position(|b|b.id==building.id){self.state.buildings.remove(ix);}for agent in AGENTS{self.state.players.get_mut(agent).unwrap().remembered_enemy_buildings.retain(|v|v.get("pos")!=Some(&json!(building.pos)));}self.emit("building_destroyed",Some(actor),json!({"building_id":building.id,"kind":building.kind}));if building.kind=="base"{self.terminal("military",Some(actor),json!({actor:3.0,other(actor):0.0}));}}
    fn terminal(&mut self,reason:&str,winner:Option<&str>,scores:Value){if self.state.terminal.is_some(){return;}let a=scores.get("agent_0").and_then(Value::as_f64).unwrap_or(0.0);let b=scores.get("agent_1").and_then(Value::as_f64).unwrap_or(0.0);self.state.players.get_mut("agent_0").unwrap().score=a;self.state.players.get_mut("agent_1").unwrap().score=b;let term=json!({"reason":reason,"winner":winner,"scores":{"agent_0":a,"agent_1":b}});self.state.terminal=Some(term.clone());self.emit("terminal",winner,term);}
    fn resolve_round(&mut self){
        let launches=self.state.queued_launches.clone();
        if launches.len()==2 { let mut ordered=launches; ordered.sort(); self.emit("launch_resolved",None,json!({"launchers":ordered,"outcome":"mutual_destruction"})); self.terminal("mutual_destruction",None,json!({"agent_0":0.0,"agent_1":0.0})); return; }
        if launches.len()==1 {
            let winner=launches[0].clone();
            self.emit("launch_resolved",Some(&winner),json!({"launchers":[winner.clone()],"outcome":"nuclear"}));
            let scores=if winner=="agent_0" { json!({"agent_0":3.0,"agent_1":0.0}) } else { json!({"agent_0":0.0,"agent_1":3.0}) };
            self.terminal("nuclear",Some(&winner),scores);
            return;
        }
        self.update_memory(); self.collect_income();
        if self.state.diplomacy.ceasefire_remaining>0 { self.state.diplomacy.ceasefire_remaining-=1; }
        if self.state.round>=self.state.max_rounds { self.terminal("timeout",None,json!({"agent_0":1.0,"agent_1":1.0})); return; }
        self.state.round+=1; self.state.half_turn=0; self.begin_half_turn("agent_0");
    }
    fn update_memory(&mut self){for agent in AGENTS{let enemy=other(agent);let visible=self.visible(agent);let mut memories:BTreeMap<(i64,i64),Value>=self.state.players[agent].remembered_enemy_buildings.iter().filter_map(|v|{let p=v.get("pos")?.as_array()?;Some(((p[0].as_i64()?,p[1].as_i64()?),v.clone()))}).collect();for b in self.state.buildings.iter().filter(|b|b.owner==enemy&&visible.contains(&(b.pos[0],b.pos[1]))){memories.insert((b.pos[0],b.pos[1]),json!({"kind":b.kind,"pos":b.pos,"last_seen_turn":self.state.round}));if b.kind=="base"{let p=self.state.players.get_mut(agent).unwrap();p.enemy_base_discovered=true;p.known_enemy_base_pos=Some(b.pos.clone());}}let count=memories.len();self.state.players.get_mut(agent).unwrap().remembered_enemy_buildings=memories.into_values().collect();self.emit("fog_memory_updated",Some(agent),json!({"visible_cell_count":visible.len(),"remembered_buildings":count}));}}
    fn collect_income(&mut self){let mut c:BTreeMap<String,(i64,i64)>=BTreeMap::new();for agent in AGENTS{c.insert(agent.to_string(),(1,0));}for building in &self.state.buildings{if building.under_construction||!(building.kind=="credit_mine"||building.kind=="uranium_mine"){continue;}if let Some(dep)=self.state.board.deposits.iter_mut().find(|d|d.pos==building.pos&&d.reserve>0){dep.reserve-=1;let entry=c.get_mut(&building.owner).unwrap();if building.kind=="credit_mine"{entry.0+=3}else{entry.1+=1};}}for agent in AGENTS{let delta=c[agent];let p=self.state.players.get_mut(agent).unwrap();p.credits+=delta.0;p.uranium+=delta.1;self.emit("income_collected",Some(agent),json!({"credits":delta.0,"uranium":delta.1}));}}
    fn step(&mut self,request:&Value){if self.state.terminal.is_some(){let actor=self.state.active_agent.clone();self.illegal(&actor,None,&json!({"kind":"step"}),"terminal");return;}let actor=self.state.active_agent.clone();let actions=request.get("actions").and_then(Value::as_array).cloned().unwrap_or_default();for (index,action) in actions.iter().enumerate(){if index>=3{self.illegal(&actor,Some(index),action,"action_limit");continue;}if self.state.terminal.is_some(){break;}self.apply_action(&actor,index,action);}if self.state.terminal.is_none(){if let Some(diplomacy)=request.get("diplomacy"){self.apply_diplomacy(&actor,diplomacy);}}self.emit("half_turn_completed",Some(&actor),json!({"actions_submitted":actions.len()}));if self.state.terminal.is_none(){if actor=="agent_0"{self.state.half_turn=1;self.begin_half_turn("agent_1");}else{self.resolve_round();}}}
    fn observation(&self)->Value{let agent=&self.state.active_agent;let visible=self.visible(agent);let units:Vec<Unit>=self.state.units.iter().filter(|u|u.owner==*agent||visible.contains(&(u.pos[0],u.pos[1]))).cloned().collect();let buildings:Vec<Building>=self.state.buildings.iter().filter(|b|b.owner==*agent||visible.contains(&(b.pos[0],b.pos[1]))).cloned().collect();let pending:Vec<Value>=self.state.diplomacy.pending.iter().filter(|p|p.get("to").and_then(Value::as_str)==Some(agent)).cloned().collect();json!({"schema_version":"gamebench.fog_duel_lite.observation.v0","you":agent,"round":self.state.round,"you_play_first":agent=="agent_0","active_agent":agent,"actions_remaining":3,"visible_cells":visible.iter().map(|p|vec![p.0,p.1]).collect::<Vec<_>>(),"visible_units":units,"visible_buildings":buildings,"remembered_enemy_buildings":self.state.players[agent].remembered_enemy_buildings,"remembered_enemy_deposits":self.state.players[agent].remembered_enemy_deposits,"own_resources":{"credits":self.state.players[agent].credits,"uranium":self.state.players[agent].uranium},"enemy_base_discovered":self.state.players[agent].enemy_base_discovered,"enemy_base_position":self.state.players[agent].known_enemy_base_pos,"diplomacy":{"ceasefire_remaining":self.state.diplomacy.ceasefire_remaining,"pending":pending},"last_turn_results":self.state.players[agent].last_turn_results,"terminal":self.state.terminal,"enemy_uranium":Value::Null,"enemy":other(agent)})}
    fn checkpoint(&self)->Value{json!({"schema_version":"gamebench.fog_duel_lite.checkpoint.v0","state":self.state,"events":self.events,"next_event_sequence":self.next_seq})}
}

fn load_scenario(id:&str)->Scenario{let path=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../defaults/scenarios").join(format!("{}.json",id));serde_json::from_str(&std::fs::read_to_string(path).expect("scenario file")).expect("scenario JSON")}
fn run_document(document:Value)->Value{let id=document.get("scenario_id").and_then(Value::as_str).expect("scenario_id");let mut engine=if let Some(checkpoint)=document.get("checkpoint"){Engine{state:serde_json::from_value(checkpoint["state"].clone()).expect("checkpoint state"),events:checkpoint["events"].as_array().expect("checkpoint events").clone(),next_seq:checkpoint["next_event_sequence"].as_i64().expect("checkpoint sequence")}}else{Engine::reset(load_scenario(id))};let mut checkpoints=vec![engine.checkpoint()];for action in document.get("tape").and_then(Value::as_array).cloned().unwrap_or_default(){engine.step(&action);checkpoints.push(engine.checkpoint());if engine.state.terminal.is_some(){break;}}json!({"scenario_id":id,"state":engine.state,"events":engine.events,"checkpoints":checkpoints,"observation":engine.observation()})}
fn main(){let mut raw=String::new();io::stdin().read_to_string(&mut raw).expect("read stdin");let document:Value=serde_json::from_str(&raw).expect("JSON request");println!("{}",serde_json::to_string(&run_document(document)).unwrap());}
