# What a Craftax rollout must provide for SFT curation

The curator (`optimizers-beta-sft/scripts/lib/craftax_curation.py`) is
**fail-closed**: it rejects a trajectory rather than infer a fact the container
did not state. That is deliberate — paid training on unverifiable demonstrations
is worse than not training — but it means the container owes three facts that it
did not originally emit. All three were found by running a real captured rollout
through curation and watching it get rejected.

| field | on | why the curator needs it |
|---|---|---|
| `invalid_actions` | rollout record | A policy that mostly emits unrecognized action names is not a demonstration. `resolve_action` silently dropped them, so the count existed and was thrown away. Now `parse_actions_batch_counted` reports it, per turn and per rollout. |
| `observation_text` | each turn | Without the observation an example teaches an action prior, not a policy. In `observation_mode: image`/`both` the symbolic text is not in the tool result either, so the turn record is the only place it can come from. |
| `target` | each turn | The exact string an SFT example must reproduce. |

## `target` is not `assistant`

This is the subtle one and it is easy to regress.

In tool-call mode the action lives in `tool_calls`, and `assistant` holds
whatever the model put in `content`:

| model class | `content` | `tool_calls` |
|---|---|---|
| thinking (e.g. `gpt-5.6-luna`) | reasoning text | the action |
| non-thinking (e.g. `gpt-4.1`) | **`null`** | the action |

Deriving the training target from `assistant` therefore yields an **empty target
for every turn of a non-thinking model**, and curation rejects all of them with
`turn N: empty target`. It also trains the thinking models on their own reasoning
prose rather than on an action.

`target` is emitted separately as canonical `{"actions":[...]}` JSON, built from
the parsed batch, independent of whether the model thinks. Verified on both
classes: Luna produced 448 chars of thinking and a valid target; GPT-4.1 produced
0 chars of thinking and an identical target shape. Both curate to the same
`[system, user, assistant]` example structure.

## Regression check

`acceptance/craftax_curation_dry_test.py` in `optimizers-beta-sft` covers the
rejection rules on fixtures. The end-to-end path — real rollout → sealed Trace V5
→ curation → dataset — is proven by running a live capture and asserting
`hard_rejection_reason(...) is None`. Anything that changes the turn record
should re-run that, not just the fixture suite: all three defects above passed
the fixture tests and still rejected 100% of real trajectories.
