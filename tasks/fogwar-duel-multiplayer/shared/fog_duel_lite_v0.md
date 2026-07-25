# Fog Duel Lite v0 contract

This is the implementation contract for `fogwar-duel-multiplayer`, distilled
from Age of LLM §2 and Appendices A–B. It preserves published decision mechanics
while making the announced Lite deltas: pinned maps, finite non-respawning
deposits, and structured-only diplomacy. There is no upstream runtime or
free-text channel in this contract.

## Board and round contract

- Coordinates are integer `[x, y]`, with `0 <= x < 13` and `0 <= y < 7`.
- Bases begin at `agent_0: [1,3]` and `agent_1: [11,3]`. Column 6 is a mountain
  barrier with one or two passable cells per pinned layout. Layouts must be
  symmetric and expose a central uranium deposit only on a passable barrier cell.
- Every full round consists of two half-turns in the fixed order
  `[agent_0, agent_1]`. A half-turn is the only public engine `step`, so callers
  supply an action object for the active actor only.
- A half-turn applies up to three actions in array order. Each rejected action
  consumes its own slot; it does not reject siblings or the whole half-turn.
- Queued launches resolve only after both half-turns. A base reaching zero HP
  ends the match immediately and skips any remaining half-turn.
- V0 has at most 80 full rounds. A non-terminal match at that limit is a draw.

The seed is an immutable scenario identity, not input to a procedural map
generator. The three v0 layouts are therefore deterministic now:

| Scenario | Seed | Passable cells in column 6 | Central uranium deposit |
|---|---:|---|---|
| `fogwar_military_win_v0` | 1307 | `[6,1]`, `[6,3]` | `[6,3]` |
| `fogwar_nuclear_win_v0` | 2718 | `[6,3]` | `[6,3]` |
| `fogwar_illegal_reliability_v0` | 4242 | `[6,3]`, `[6,5]` | `[6,3]` |

Every other cell in column 6 is a mountain. Scenario data will also pin exact
side deposits, finite reserves, and scripted opening state. Reserve values are
always finite and are never respawned by the engine.

## Authoritative state and private observation

The authoritative `gamebench.fog_duel_lite.state.v0` state is canonical JSON:

```json
{
  "schema_version": "gamebench.fog_duel_lite.state.v0",
  "scenario_id": "fogwar_military_win_v0",
  "seed": 1307,
  "round": 1,
  "half_turn": {"active_agent": "agent_0", "actions_used": 0},
  "board": {"size": [13, 7], "mountains": [], "passages": [], "deposits": []},
  "players": {"agent_0": {}, "agent_1": {}},
  "units": [],
  "buildings": [],
  "diplomacy": {},
  "queued_launches": [],
  "terminal": null,
  "rng_state": ""
}
```

`players[agent]` contains `credits`, private `uranium`, `enemy_base_discovered`,
`known_enemy_base_pos`, per-half-turn unit use flags, and terminal score.
`units[]` has `{id, owner, kind, pos}`. `buildings[]` has
`{id, owner, kind, pos, hp, under_construction}`. `deposits[]` has
`{kind, pos, reserve}`. `diplomacy` holds pending proposal IDs and remaining
ceasefire rounds. No state field exposes the opponent's uranium.

An actor receives `gamebench.fog_duel_lite.observation.v0`, not that whole state:

```json
{
  "schema_version": "gamebench.fog_duel_lite.observation.v0",
  "you": "agent_0",
  "round": 1,
  "you_play_first": true,
  "actions_remaining": 3,
  "visible_cells": [],
  "visible_units": [],
  "visible_buildings": [],
  "remembered_enemy_buildings": [],
  "remembered_enemy_deposits": [],
  "own_resources": {"credits": 5, "uranium": 0},
  "enemy_base_discovered": false,
  "diplomacy": {},
  "last_turn_results": [],
  "terminal": null
}
```

Every remembered object carries `kind`, `pos`, and `last_seen_turn`. Enemy units
are current-visibility only. A destroyed building is removed from memory when
the engine observes its destruction. Visibility is the union of Chebyshev-radius
detection from the actor's units and buildings.

## Actions and rules

Each step submits the following shape. `diplomacy` is optional and does not count
against the three action slots; no text-bearing field exists.

```json
{
  "actions": [{"kind": "wait"}],
  "diplomacy": {
    "proposal": {"kind": "ceasefire"},
    "responses": [{"proposal_id": "p_12", "accept": false}]
  }
}
```

| `kind` | Required fields | Core legality predicate |
|---|---|---|
| `produce` | `unit` | `unit` is Drone, SAM, Tank, or Fighter; the actor can pay and its base has a valid spawn cell. |
| `move` | `unit_id`, `to` | Owned live unit has not moved this half-turn; destination is in range and legal for its layer. Ground movement needs a clear path and cannot cross mountains/buildings; air ignores them. |
| `attack` | `unit_id`, `target_pos` | Owned live unit has not attacked this half-turn; target is legal, visible, in range, and satisfies its unit matchup and line-of-sight rule. |
| `build` | `building`, `pos` | Actor can pay; visible cell is free and valid for the building. Mines require the matching deposit; a silo is in own territory and not on a deposit. No construction is adjacent to either base. |
| `launch` | none | Actor has an operational silo, enough private uranium for the current bomb cost, and has discovered the enemy base. It queues a launch; it does not resolve it yet. |
| `wait` | none | Always legal and consumes one slot. |

`produce` unit constants are: Drone `2C`, move/detect `3/3`; SAM `3C`,
`2/2`, attacks air only; Tank `4C`, `2/1`, attacks Tank/SAM and buildings;
Fighter `4C`, `3/2`, attacks Tank/Drone/Fighter. Attack range is 2 for the
three combat units. Unit combat is lethal; an attacker survives mirror matches.
Only a Tank damages buildings (2 HP per legal hit). Bases have 4 HP, mines 2 HP,
and silos 3 HP. Ground line of sight is blocked by mountains and buildings;
Fighters ignore those blockers.

Actors start with `5C, 0U`. They receive `+1C` per full round, credit mines add
`+3C`, and uranium mines add `+1U` while their finite deposit remains. Mines cost
`2C`; silos cost `5C`. New buildings provide vision but are under construction
until their owner's next half-turn; before then mines do not produce, silos cannot
launch, and one Tank hit destroys them. The normal bomb cost is `25U`, dropping
by `2U` each ten rounds from round 40 to a floor of `13U`; an active ceasefire
adds `6U`.

Diplomacy is typed: `ceasefire` (available round 10+, blocks attacks for three
rounds), `peace` (round 15+, immediate draw), or `ultimatum` (round 10+, target
round one through three rounds ahead). An accepted ultimatum is an immediate
win for its proposer and a `0.5` consolation score for its accepter. Nuclear
launches remain allowed during a ceasefire at the increased cost. At round end,
one queued launch is nuclear victory; two are mutual destruction.

Any schema, ownership, fog/visibility, range, occupancy, resource, or timing
violation is rejected. The engine must leave authoritative state unchanged for
that operation and emit `illegal_action` with a stable reason code.

## NEV contract

Every event has this envelope, serialized in ascending `seq` order:

```json
{
  "schema_version": "gamebench.nev.v1",
  "seq": 17,
  "round": 4,
  "half_turn": 1,
  "actor": "agent_1",
  "kind": "illegal_action",
  "payload": {}
}
```

Required kinds are `match_started`, `half_turn_started`, `action_applied`,
`illegal_action`, `unit_produced`, `unit_moved`, `combat_resolved`,
`building_built`, `building_destroyed`, `income_collected`, `fog_memory_updated`,
`diplomacy_proposed`, `diplomacy_resolved`, `launch_queued`, `launch_resolved`,
`half_turn_completed`, and `terminal`. `illegal_action.payload` must include
`{action_index, submitted_kind, reason_code}`. `terminal.payload` must include
`{reason, winner, scores}` where `reason` is one of `military`, `nuclear`,
`mutual_destruction`, `peace`, `ultimatum`, or `timeout`.

## Checkpoint contract

`gamebench.fog_duel_lite.checkpoint.v0` is canonical UTF-8 JSON at every action
boundary. It stores `scenario_id`, seed/layout identity, complete authoritative
state, current round and active actor, action-use flags, pending diplomacy,
queued launches, fog memories for both players, terminal status, PRNG state, and
the next NEV sequence number. Restoring one must yield the same active actor,
observation, state digest, and subsequent NEV suffix for the same future actions.
