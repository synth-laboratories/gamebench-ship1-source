"""LLDB callbacks for read-only ``mfndpos``/selector branch tracing.

This module is loaded *by LLDB*, never by the NLE process.  It places
breakpoints in the exact hash-pinned wheel image and reads registers/process
memory through LLDB; it neither calls a NetHack function nor writes to target
memory.  The runner writes a preselected action token before ``env.step``;
callbacks reject every stop without that token so a later result cannot choose
which branch call to retain.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any


MAX_MFNDPOS_CANDIDATES = 9
# Pinned Darwin/arm64 ``struct level`` layout.  These values are deliberately
# duplicated from the independently ABI-checked native reader rather than
# inferred from a renderer or a Python ctypes object inside the tracee.
COLNO = 80
ROWNO = 21
RM_SIZE = 8
LEVEL_LOCATIONS_OFFSET = 0
LEVEL_OBJECTS_OFFSET = COLNO * ROWNO * RM_SIZE
LEVEL_MONSTERS_OFFSET = LEVEL_OBJECTS_OFFSET + COLNO * ROWNO * 8
OBJ_SIZE = 96
MAX_CELL_OBJECTS = 8192
_RETURN_CONTEXTS: dict[int, dict[str, Any]] = {}
# A dog_move invocation is bound in debugger host memory from its own function
# entry through its own x30 return.  This avoids pretending that the caller
# frame visible from a nested mfndpos call is necessarily the selector's final
# return path (notably, code-1 no-displacement pet turns have an alternate
# epilogue).
_ACTIVE_DOGMOVE: dict[tuple[int, int], list[int]] = {}
_NEXT_EVENT_ID = 0
_RETURN_QUEUES: dict[tuple[int, int, int], list[int]] = {}
_RETURN_STOP_CONSUMED: set[tuple[int, int, int]] = set()


def _state() -> dict[str, Any] | None:
    path = os.environ.get("NLE_BRANCH_TRACE_STATE")
    if not path:
        return None
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return None
    if (
        isinstance(value, dict)
        and value.get("phase") == "action"
        and type(value.get("step")) is int
        and value["step"] > 0
        and isinstance(value.get("action"), dict)
    ):
        return value
    return None


def _write(event: dict[str, Any]) -> None:
    path = os.environ.get("NLE_BRANCH_TRACE_EVENTS")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def _function_name(frame: Any) -> str:
    name = frame.GetFunctionName() if frame and frame.IsValid() else None
    if not name and frame and frame.IsValid():
        symbol = frame.GetSymbol()
        name = symbol.GetName() if symbol and symbol.IsValid() else None
    return str(name or "").lstrip("_")


def _frame_location(frame: Any) -> dict[str, Any]:
    """Return a portable source location, never an ASLR address."""

    entry = frame.GetLineEntry() if frame and frame.IsValid() else None
    file_spec = entry.GetFileSpec() if entry and entry.IsValid() else None
    filename = file_spec.GetFilename() if file_spec and file_spec.IsValid() else None
    line = entry.GetLine() if entry and entry.IsValid() else None
    return {
        "function": _function_name(frame),
        "source_file": str(filename or ""),
        "source_line": int(line) if type(line) is int and line > 0 else None,
    }


def _register(frame: Any, name: str) -> int:
    register = frame.FindRegister(name)
    if not register or not register.IsValid():
        raise RuntimeError(f"missing arm64 register {name}")
    return int(register.GetValueAsUnsigned())


def _read(process: Any, address: int, byte_length: int) -> bytes:
    import lldb

    if address <= 0 or byte_length <= 0:
        raise RuntimeError("invalid target read address/length")
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_length, error)
    if not error.Success() or len(payload) != byte_length:
        raise RuntimeError(f"target memory read failed at 0x{address:x}: {error.GetCString()}")
    return bytes(payload)


def _actor(process: Any, address: int) -> dict[str, int]:
    # These are only the ABI offsets already asserted by
    # scripts/nle_native_entities.py.  Copy a prefix rather than attempting
    # to dereference a source-side ctypes object from the debugger host.
    raw = _read(process, address, 96)
    return {
        "entity_id": int(struct.unpack_from("<I", raw, 16)[0]),
        "movement_points": int(struct.unpack_from("<h", raw, 24)[0]),
        "native_x": int(struct.unpack_from("<b", raw, 28)[0]),
        "native_y": int(struct.unpack_from("<b", raw, 29)[0]),
        "mux": int(struct.unpack_from("<b", raw, 30)[0]),
        "muy": int(struct.unpack_from("<b", raw, 31)[0]),
        "strategy": int(struct.unpack_from("<Q", raw, 72)[0]),
    }


def _level_address(frame: Any) -> int:
    """Resolve the pinned wheel's ``level`` global without emitting ASLR data.

    The tracee binary is already hash-pinned by the runner.  Still, require a
    debugger-visible symbol and one unambiguous load address instead of using
    an address calculated from an unverified slide in the callback host.
    """

    import lldb

    target = frame.GetThread().GetProcess().GetTarget()
    addresses: set[int] = set()
    for name in ("level", "_level"):
        value = target.FindFirstGlobalVariable(name)
        if value and value.IsValid():
            address = value.GetAddress()
            if address and address.IsValid():
                load_address = int(address.GetLoadAddress(target))
                if load_address > 0:
                    addresses.add(load_address)
        # ``level`` is a local Mach-O data symbol in the pinned wheel, so it
        # is normally absent from SBTarget globals.  Resolve precisely from
        # the module containing the currently executing mfndpos frame.
        module = frame.GetModule()
        if module and module.IsValid():
            symbol = module.FindSymbol(name, lldb.eSymbolTypeData)
            if symbol and symbol.IsValid():
                address = symbol.GetStartAddress()
                if address and address.IsValid():
                    load_address = int(address.GetLoadAddress(target))
                    if load_address > 0:
                        addresses.add(load_address)
    if len(addresses) != 1:
        raise RuntimeError(f"pinned level global resolution is not unique: {len(addresses)} addresses")
    return next(iter(addresses))


def _cell_address(level_address: int, offset: int, x: int, y: int) -> int:
    if not (1 <= x < COLNO and 0 <= y < ROWNO):
        raise RuntimeError(f"source cell outside pinned playable level: ({x},{y})")
    return level_address + offset + (x * ROWNO + y) * 8


def _object_stack(process: Any, address: int, x: int, y: int) -> list[dict[str, int]]:
    """Copy one complete floor stack as portable raw source fields.

    Addresses are used only to walk the native ``nexthere`` chain.  They do
    not enter a tape; object identity/type/quantity and coordinates do.
    """

    objects: list[dict[str, int]] = []
    seen: set[int] = set()
    for _ in range(MAX_CELL_OBJECTS):
        if address == 0:
            return objects
        if address <= 0 or address % 8:
            raise RuntimeError("unaligned source floor-object pointer")
        if address in seen:
            raise RuntimeError("cycle in source floor-object stack")
        seen.add(address)
        raw = _read(process, address, OBJ_SIZE)
        object_id = int(struct.unpack_from("<I", raw, 24)[0])
        object_x = int(struct.unpack_from("<b", raw, 28)[0])
        object_y = int(struct.unpack_from("<b", raw, 29)[0])
        object_type = int(struct.unpack_from("<h", raw, 30)[0])
        quantity = int(struct.unpack_from("<q", raw, 40)[0])
        if object_id <= 0 or (object_x, object_y) != (x, y):
            raise RuntimeError("source floor-object stack has invalid identity or coordinate")
        objects.append(
            {
                "object_id": object_id,
                "object_type": object_type,
                "quantity": quantity,
            }
        )
        address = int(struct.unpack_from("<Q", raw, 8)[0])
    raise RuntimeError("source floor-object stack exceeded bounded traversal limit")


def _source_cell(process: Any, frame: Any, x: int, y: int) -> dict[str, Any]:
    """Capture one exact selector-boundary underlay and occupancy cell."""

    level_address = _level_address(frame)
    rm = _read(process, _cell_address(level_address, LEVEL_LOCATIONS_OFFSET, x, y), RM_SIZE)
    glyph, terrain_type, seen_vector, flags = struct.unpack("<ibBH", rm)
    object_address = int(struct.unpack("<Q", _read(process, _cell_address(level_address, LEVEL_OBJECTS_OFFSET, x, y), 8))[0])
    monster_address = int(struct.unpack("<Q", _read(process, _cell_address(level_address, LEVEL_MONSTERS_OFFSET, x, y), 8))[0])
    occupancy: dict[str, int | None]
    if monster_address:
        if monster_address % 8:
            raise RuntimeError("unaligned source cell monster pointer")
        occupancy = {"entity_id": _actor(process, monster_address)["entity_id"]}
    else:
        occupancy = {"entity_id": None}
    return {
        "coordinate": {"native_x": x, "native_y": y},
        # This deliberately excludes occupancy: terrain/object stacks are
        # the underlay whose conservation is compared across the exact
        # selector boundary.  Occupancy is captured separately below.
        "state": {
            "terrain": {
                "glyph": int(glyph),
                "type": int(terrain_type),
                "seen_vector": int(seen_vector),
                "flags": int(flags),
            },
            "object_stack": _object_stack(process, object_address, x, y),
            "object_stack_complete": True,
            "source_abi": "nethack_3_6_6_darwin_arm64_level_rm_obj_v1",
        },
        "occupancy": occupancy,
    }


def _selector_entry_boundary(process: Any, frame: Any, actor: dict[str, int]) -> dict[str, Any]:
    """Snapshot source + all legal adjacent destinations before selection."""

    source_x, source_y = actor["native_x"], actor["native_y"]
    source = _source_cell(process, frame, source_x, source_y)
    if source["occupancy"].get("entity_id") != actor["entity_id"]:
        raise RuntimeError("selector entry source occupancy does not name traced actor")
    neighborhood: dict[tuple[int, int], dict[str, Any]] = {}
    for x in range(max(1, source_x - 1), min(COLNO - 1, source_x + 1) + 1):
        for y in range(max(0, source_y - 1), min(ROWNO - 1, source_y + 1) + 1):
            neighborhood[(x, y)] = _source_cell(process, frame, x, y)
    if neighborhood.get((source_x, source_y)) != source:
        raise RuntimeError("selector entry source cell was not captured exactly once")
    return {"source": source, "neighborhood": neighborhood}


def _return_breakpoint_at(frame: Any, address: int, context: dict[str, Any]) -> int:
    """Stop once at an already-unwound caller return address.

    ``x30`` at a leaf entry is convenient, but it is not a durable way to
    bind a nested ``mfndpos`` call to *that particular* ``dog_move`` or
    ``m_move`` invocation.  The immediate caller's parent frame exposes the
    selector return PC before the leaf runs.  Keep that address in debugger
    host memory only; emitting ASLR addresses would make the source evidence
    non-portable and needlessly leak an implementation detail into a tape.
    """

    if address <= 0:
        raise RuntimeError("invalid selector return address")
    caller = frame.GetThread().GetFrameAtIndex(1)
    if not caller or not caller.IsValid():
        raise RuntimeError("selector return caller frame is unavailable")
    caller_sp = int(caller.GetSP())
    if caller_sp <= 0:
        raise RuntimeError("selector return caller stack pointer is invalid")
    target = frame.GetThread().GetProcess().GetTarget()
    breakpoint = target.BreakpointCreateByAddress(address)
    breakpoint.SetThreadID(frame.GetThread().GetThreadID())
    breakpoint.SetScriptCallbackFunction(f"{__name__}.on_return")
    breakpoint_id = int(breakpoint.GetID())
    # Many invocations share one return PC.  An address-only one-shot would
    # let the first matching PC consume a later invocation's context.  The
    # originating caller's stack frame makes this a PC+frame identity check;
    # mismatch hits are ignored and the breakpoint remains armed.
    context["expected_caller_sp"] = caller_sp
    queue_key = (int(frame.GetThread().GetThreadID()), address, caller_sp)
    # A separate completion callback is fired for every breakpoint at an
    # address.  Sequential dog_move calls share PC and stack frame, so only
    # the first queued context may consume one physical return stop.
    _RETURN_STOP_CONSUMED.discard(queue_key)
    context["return_queue_key"] = queue_key
    _RETURN_QUEUES.setdefault(queue_key, []).append(breakpoint_id)
    _RETURN_CONTEXTS[breakpoint_id] = context
    return breakpoint_id


def _return_breakpoint(frame: Any, context: dict[str, Any]) -> int:
    """Stop once at the current function's normal return address."""

    return _return_breakpoint_at(frame, _register(frame, "x30"), context)


def _trace_error(state: dict[str, Any], function: str, error: Exception) -> None:
    _write(
        {
            "kind": "trace_error",
            "step": state["step"],
            "action": state["action"],
            "function": function,
            "error": str(error),
        }
    )


def _dogmove_key(frame: Any, actor_address: int) -> tuple[int, int]:
    return int(frame.GetThread().GetThreadID()), actor_address


def on_dog_move_entry(frame: Any, breakpoint_location: Any, _internal_dict: dict[str, Any]) -> bool:
    """Bind one dog_move invocation to its own x30 return before it runs."""

    del breakpoint_location
    state = _state()
    if state is None:
        return False
    try:
        process = frame.GetThread().GetProcess()
        actor_address = _register(frame, "x0")
        actor = _actor(process, actor_address)
        key = _dogmove_key(frame, actor_address)
        # Recursive same-actor dog_move would make a later candidate
        # ambiguous.  Keep the nested stack explicitly; mfndpos must bind to
        # the currently active top invocation, never an actor/order heuristic.
        entry = {
            "kind": "dog_move_return",
            "step": state["step"],
            "action": state["action"],
            "selector": "dog_move",
            "actor": actor,
            "actor_address": actor_address,
            "selector_entry_boundary": _selector_entry_boundary(process, frame, actor),
            "candidate_event_ids": [],
        }
        breakpoint_id = _return_breakpoint(frame, entry)
        _ACTIVE_DOGMOVE.setdefault(key, []).append(breakpoint_id)
    except Exception as error:  # pragma: no cover - exercised only under LLDB
        _trace_error(state, "dog_move", error)
    return False


def on_mfndpos_entry(frame: Any, breakpoint_location: Any, _internal_dict: dict[str, Any]) -> bool:
    """Remember a candidate-array call and stop again exactly at its return."""

    del breakpoint_location
    state = _state()
    if state is None:
        return False
    try:
        thread = frame.GetThread()
        caller_frame = thread.GetFrameAtIndex(1)
        caller = _function_name(caller_frame)
        if caller not in {"dog_move", "m_move"}:
            return False
        process = frame.GetThread().GetProcess()
        actor_address = _register(frame, "x0")
        actor = _actor(process, actor_address)
        dogmove_breakpoint_id: int | None = None
        selector_entry_boundary: dict[str, Any] | None = None
        selector_return_address: int | None = None
        selector_return_location: dict[str, Any] | None = None
        if caller == "dog_move":
            active = _ACTIVE_DOGMOVE.get(_dogmove_key(frame, actor_address), [])
            if len(active) != 1:
                raise RuntimeError("mfndpos dog_move invocation has no unique entry-to-x30-return binding")
            dogmove_breakpoint_id = active[-1]
            dogmove_context = _RETURN_CONTEXTS.get(dogmove_breakpoint_id)
            if not isinstance(dogmove_context, dict) or dogmove_context.get("actor", {}).get("entity_id") != actor["entity_id"]:
                raise RuntimeError("mfndpos dog_move binding lost stable actor identity")
        else:
            # m_move keeps the existing exact caller-return binding.  The
            # alternate dog_move path is handled above by its own x30.
            selector_parent = thread.GetFrameAtIndex(2)
            if not selector_parent or not selector_parent.IsValid():
                raise RuntimeError("mfndpos selector caller frame is unavailable")
            selector_return_address = int(selector_parent.GetPC())
            if selector_return_address <= 0:
                raise RuntimeError("mfndpos selector caller has invalid return PC")
            selector_return_location = _frame_location(selector_parent)
            selector_entry_boundary = _selector_entry_boundary(process, frame, actor)
        _return_breakpoint(
            frame,
            {
                "kind": "mfndpos_return",
                "step": state["step"],
                "action": state["action"],
                "caller": caller,
                "actor": actor,
                "poss_address": _register(frame, "x1"),
                "info_address": _register(frame, "x2"),
                "allowflags": _register(frame, "x3"),
                # Host-only pointer, removed before the candidate event is
                # written.  It is required to check that the selector return
                # remains the same stable native actor.
                "actor_address": actor_address,
                # Host-only ASLR address.  It is consumed to create a
                # one-shot breakpoint after mfndpos returns and is removed
                # before any event is written.
                "selector_return_address": selector_return_address,
                "selector_return_location": selector_return_location,
                # Semantic raw source data only.  This is retained in LLDB
                # host memory until the unique selector-return breakpoint;
                # it is not written with the mfndpos event and cannot be
                # matched later by seed, coordinates, or call order.
                "selector_entry_boundary": selector_entry_boundary,
                "dogmove_breakpoint_id": dogmove_breakpoint_id,
            },
        )
    except Exception as error:  # pragma: no cover - exercised only under LLDB
        _trace_error(state, "mfndpos", error)
    return False


def on_return(frame: Any, breakpoint_location: Any, _internal_dict: dict[str, Any]) -> bool:
    """Copy a full ``mfndpos`` result before its caller evaluates it."""

    global _NEXT_EVENT_ID
    breakpoint = breakpoint_location.GetBreakpoint()
    breakpoint_id = int(breakpoint.GetID())
    context = _RETURN_CONTEXTS.get(breakpoint_id)
    if context is None:
        return False
    try:
        if int(frame.GetSP()) != context.get("expected_caller_sp"):
            return False
        queue_key = context.get("return_queue_key")
        if not (isinstance(queue_key, tuple) and len(queue_key) == 3):
            raise RuntimeError("return context lacks queue identity")
        queue = _RETURN_QUEUES.get(queue_key)
        if not queue or queue[0] != breakpoint_id or queue_key in _RETURN_STOP_CONSUMED:
            return False
        queue.pop(0)
        if not queue:
            del _RETURN_QUEUES[queue_key]
        _RETURN_STOP_CONSUMED.add(queue_key)
        _RETURN_CONTEXTS.pop(breakpoint_id, None)
        frame.GetThread().GetProcess().GetTarget().BreakpointDelete(breakpoint_id)
        context.pop("expected_caller_sp", None)
        context.pop("return_queue_key", None)
        process = frame.GetThread().GetProcess()
        if context["kind"] == "mfndpos_return":
            count = int(_register(frame, "x0"))
            if not 0 <= count <= MAX_MFNDPOS_CANDIDATES:
                raise RuntimeError(f"mfndpos returned invalid candidate count {count}")
            poss = _read(process, int(context["poss_address"]), MAX_MFNDPOS_CANDIDATES * 2)
            info = _read(process, int(context["info_address"]), MAX_MFNDPOS_CANDIDATES * 8)
            context.update(
                {
                    "kind": "mfndpos_candidates",
                    "candidate_count": count,
                    "candidates": [
                        {
                            "native_x": int(struct.unpack_from("<b", poss, index * 2)[0]),
                            "native_y": int(struct.unpack_from("<b", poss, index * 2 + 1)[0]),
                            "mfndpos_flags": int(struct.unpack_from("<q", info, index * 8)[0]),
                        }
                        for index in range(count)
                    ],
                }
            )
            # Event ID is assigned before arming the selector return so the
            # return event can name one exact candidate.  This is a causal
            # binding, not a later actor/coordinate/order heuristic.
            actor_address = context.pop("actor_address", None)
            if type(actor_address) is not int or actor_address <= 0:
                raise RuntimeError("mfndpos candidate lacks actor address")
            # Candidate/result values are semantic source evidence.  The
            # three raw process pointers were necessary only to reach this
            # callback and must not enter a replay artifact.
            context.pop("poss_address", None)
            context.pop("info_address", None)
            dogmove_breakpoint_id = context.pop("dogmove_breakpoint_id", None)
            selector_return_address = context.pop("selector_return_address", None)
            selector_entry_boundary = context.pop("selector_entry_boundary", None)
            context["event_id"] = _NEXT_EVENT_ID
            _NEXT_EVENT_ID += 1
            _write(context)
            if dogmove_breakpoint_id is not None:
                if type(dogmove_breakpoint_id) is not int:
                    raise RuntimeError("mfndpos dog_move invocation ID is invalid")
                dogmove_context = _RETURN_CONTEXTS.get(dogmove_breakpoint_id)
                if not isinstance(dogmove_context, dict) or dogmove_context.get("kind") != "dog_move_return":
                    raise RuntimeError("mfndpos dog_move invocation no longer has an active x30 return")
                ids = dogmove_context.get("candidate_event_ids")
                if not isinstance(ids, list) or context["event_id"] in ids:
                    raise RuntimeError("mfndpos dog_move candidate binding is duplicate or malformed")
                ids.append(context["event_id"])
                return False
            if type(selector_return_address) is not int or selector_return_address <= 0:
                raise RuntimeError("mfndpos candidate lacks selector return address")
            if not isinstance(selector_entry_boundary, dict):
                raise RuntimeError("mfndpos candidate lacks exact selector-entry boundary")
            source_underlay_before = selector_entry_boundary.get("source")
            neighborhood = selector_entry_boundary.get("neighborhood")
            if not isinstance(source_underlay_before, dict) or not isinstance(neighborhood, dict):
                raise RuntimeError("mfndpos candidate selector-entry boundary is malformed")
            selector_context = {
                "kind": "selector_return",
                "step": context["step"],
                "action": context["action"],
                "selector": context["caller"],
                "actor": context["actor"],
                "actor_address": actor_address,
                "bound_candidate_event_id": context["event_id"],
                # Host-only until the one exact return breakpoint.  Its
                # cells contain no process pointers; they are nevertheless
                # withheld from the candidate event so an emitted record is
                # always causally complete (entry + same invocation return).
                "source_underlay_before": source_underlay_before,
                "entry_neighborhood": neighborhood,
            }
            _return_breakpoint_at(frame, selector_return_address, selector_context)
            return False
        if context["kind"] == "dog_move_return":
            actor_address = context.get("actor_address")
            if type(actor_address) is not int or actor_address <= 0:
                raise RuntimeError("dog_move x30 return lacks actor address")
            key = _dogmove_key(frame, actor_address)
            active = _ACTIVE_DOGMOVE.get(key)
            if not isinstance(active, list) or breakpoint_id not in active:
                raise RuntimeError("dog_move x30 return lost active invocation identity")
            active.remove(breakpoint_id)
            if not active:
                del _ACTIVE_DOGMOVE[key]
            candidate_ids = context.pop("candidate_event_ids", None)
            if not isinstance(candidate_ids, list):
                raise RuntimeError("dog_move x30 return lacks candidate invocation list")
            # A dog_move call with no mfndpos is not a candidate-selection
            # record.  It is intentionally not an unmatched candidate.
            if not candidate_ids:
                return False
            if len(candidate_ids) != 1 or type(candidate_ids[0]) is not int:
                raise RuntimeError("dog_move x30 return has non-unique mfndpos candidate binding")
            entry = context.pop("selector_entry_boundary", None)
            if not isinstance(entry, dict):
                raise RuntimeError("dog_move x30 return lacks selector-entry boundary")
            source_underlay_before = entry.get("source")
            neighborhood = entry.get("neighborhood")
            if not isinstance(source_underlay_before, dict) or not isinstance(neighborhood, dict):
                raise RuntimeError("dog_move x30 return selector-entry boundary is malformed")
            context.update(
                {
                    "kind": "selector_return",
                    "bound_candidate_event_id": candidate_ids[0],
                    "source_underlay_before": source_underlay_before,
                    "entry_neighborhood": neighborhood,
                }
            )
        if context["kind"] == "selector_return":
            context["return_code"] = int(_register(frame, "x0"))
            actor_address = context.pop("actor_address", None)
            if type(actor_address) is not int or actor_address <= 0:
                raise RuntimeError("selector return lacks actor address")
            actor_after = _actor(process, actor_address)
            if actor_after["entity_id"] != context["actor"]["entity_id"]:
                raise RuntimeError("selector actor identity changed before return")
            source_underlay_before = context.pop("source_underlay_before", None)
            entry_neighborhood = context.pop("entry_neighborhood", None)
            if not isinstance(source_underlay_before, dict) or not isinstance(entry_neighborhood, dict):
                raise RuntimeError("selector return lacks exact entry boundary")
            source_coordinate = source_underlay_before.get("coordinate")
            if not isinstance(source_coordinate, dict):
                raise RuntimeError("selector return entry source coordinate is malformed")
            source_x = source_coordinate.get("native_x")
            source_y = source_coordinate.get("native_y")
            destination_x, destination_y = actor_after["native_x"], actor_after["native_y"]
            if type(source_x) is not int or type(source_y) is not int:
                raise RuntimeError("selector return entry source coordinate is invalid")
            destination_before = entry_neighborhood.get((destination_x, destination_y))
            if not isinstance(destination_before, dict):
                raise RuntimeError("selector return destination was not in exact entry neighborhood")
            source_underlay_after = _source_cell(process, frame, source_x, source_y)
            destination_underlay_after = _source_cell(process, frame, destination_x, destination_y)
            if source_underlay_before.get("occupancy", {}).get("entity_id") != context["actor"]["entity_id"]:
                raise RuntimeError("selector return entry source occupancy no longer identifies actor")
            if destination_underlay_after.get("occupancy", {}).get("entity_id") != context["actor"]["entity_id"]:
                raise RuntimeError("selector return destination occupancy does not identify actor")
            # This is the exact return boundary selected when the candidate
            # was captured, not the action-end entity snapshot.
            context["actor_after"] = actor_after
            context["source_underlay_before"] = source_underlay_before
            context["source_underlay_after"] = source_underlay_after
            context["destination_underlay_before"] = destination_before
            context["destination_underlay_after"] = destination_underlay_after
        else:
            raise RuntimeError(f"unknown return context kind {context['kind']!r}")
        context["event_id"] = _NEXT_EVENT_ID
        _NEXT_EVENT_ID += 1
        _write(context)
    except Exception as error:  # pragma: no cover - exercised only under LLDB
        _trace_error({"step": context["step"], "action": context["action"]}, "return", error)
    return False


def __lldb_init_module(debugger: Any, _internal_dict: dict[str, Any]) -> None:
    """Install pending symbol breakpoints after ``target create python``."""

    target = debugger.GetSelectedTarget()
    for symbol, callback in (("mfndpos", "on_mfndpos_entry"), ("dog_move", "on_dog_move_entry")):
        breakpoint = target.BreakpointCreateByName(symbol)
        breakpoint.SetScriptCallbackFunction(f"{__name__}.{callback}")
