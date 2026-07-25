# Pinned NLE action map

The authoritative machine-readable map is [`nle_action_map.json`](nle_action_map.json).
It is the ordered `nle.nethack.ACTIONS` tuple from NLE `0.9.0` / NetHack `3.6.6`.
The public GameBench action **id** is the tuple index; it is deliberately not the
ASCII/Meta/control keycode in the third column.  A capture records all three
fields and its action-map SHA-256, because a changed action order changes an id.

| IDs | NLE enum family | Semantics |
| --- | --- | --- |
| 0–7 | `CompassDirection` | One-square compass movement (`k,l,j,h,u,n,b,y`). |
| 8–15 | `CompassDirectionLonger` | Uppercase run/far movement. |
| 16–18 | `MiscDirection` | `<`, `>`, `.`. |
| 19 | `MiscAction.MORE` | Raw carriage-return / `--More--` acknowledgement. |
| 20–104 | `Command` | Full NetHack command surface, including Meta and control commands. |
| 105–120 | `TextCharacters` | Text/menu prompt characters supplied by NLE. |

The accepted command names, by contiguous order in the `Command` range, are:

```text
EXTCMD EXTLIST ADJUST ANNOTATE APPLY ATTRIBUTES AUTOPICKUP CALL CAST CHAT
CLOSE CONDUCT DIP DROP DROPTYPE EAT ENGRAVE ENHANCE ESC FIGHT FIRE FORCE
GLANCE HISTORY INVENTORY INVENTTYPE INVOKE JUMP KICK KNOWN KNOWNCLASS LOOK
LOOT MONSTER MOVE MOVEFAR OFFER OPEN OPTIONS OVERVIEW PAY PICKUP PRAY PUTON
QUAFF QUIT QUIVER READ REDRAW REMOVE RIDE RUB RUSH RUSH2 SAVE SEARCH SEEALL
SEEAMULET SEEARMOR SEEGOLD SEERINGS SEESPELLS SEETOOLS SEETRAP SEEWEAPON
SHELL SIT SWAP TAKEOFF TAKEOFFALL TELEPORT THROW TIP TRAVEL TURN TWOWEAPON
UNTRAP VERSION VERSIONSHORT WEAR WHATDOES WHATIS WIELD WIPE ZAP
```

`UnsafeActions.HELP` and `UnsafeActions.PREVMSG` are not members of the pinned
`ACTIONS` tuple, so they have no public tuple id.  Gold accepts their keycodes as
diagnostic aliases.  Gold also accepts canonical names (for legible scenarios)
and raw key values as an adapter convenience, but captures and HTTP clients should
send the tuple id.

Prompt handling is contextual.  For example, id 24 is `Command.APPLY` outside a
prompt, while the same keycode can select inventory letter `a` in an
`inventory_letter` prompt.  Each step consumes exactly one action and publishes
the resulting input mode.

The capture utility emits an action table directly from its installed NLE before
recording a fixture.  It refuses to write a capture when that table does not hash
to this pinned map unless `--accept-action-map-drift` is explicitly supplied.
