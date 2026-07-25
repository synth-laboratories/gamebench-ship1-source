# Frozen NLE oracle corpus

Each authentic capture lives in its own directory:

```text
<fixture-id>/
  meta.json
  actions.jsonl
  snapshots.jsonl
  level_dump.json
```

`meta.json` pins NLE/NetHack versions, full ordered action mapping hash,
character options, seed data, observation-key order, and raw/auto-MORE policy.
`actions.jsonl` records one wire action index per line.  `snapshots.jsonl`
contains the projected observation after each action plus an initial step-zero
snapshot.  The down-stair boundary is captured without stepping live NLE into
dlvl 2.

No synthetic gold output may be put in this directory.  Until NLE captures are
materialized, it intentionally contains only this format note.
