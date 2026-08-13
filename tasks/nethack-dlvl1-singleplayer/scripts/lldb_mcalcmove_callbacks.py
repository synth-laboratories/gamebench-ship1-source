"""Read-only LLDB tracing of exact ``mcalcmove`` allocation boundaries.

The action runner captures a public/source frame before input, but NetHack
may replenish monster movement between that frame and ``movemon``.  This
callback records the pinned source function's actor pointer, return allocation,
and exact return boundary without calling or mutating the target process.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any

_CONTEXTS: dict[int, dict[str, Any]] = {}
_NEXT = 0


def _state() -> dict[str, Any] | None:
    path = os.environ.get("NLE_BRANCH_TRACE_STATE")
    if not path:
        return None
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return None
    if isinstance(value, dict) and value.get("phase") == "action" and type(value.get("step")) is int and isinstance(value.get("action"), dict):
        return value
    return None


def _write(value: dict[str, Any]) -> None:
    path = os.environ.get("NLE_BRANCH_TRACE_EVENTS")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _read(process: Any, address: int, length: int) -> bytes:
    import lldb

    if address <= 0 or length <= 0:
        raise RuntimeError("invalid mcalcmove target read")
    error = lldb.SBError()
    payload = process.ReadMemory(address, length, error)
    if not error.Success() or len(payload) != length:
        raise RuntimeError(f"mcalcmove actor read failed: {error.GetCString()}")
    return bytes(payload)


def _reg(frame: Any, name: str) -> int:
    register = frame.FindRegister(name)
    if not register or not register.IsValid():
        raise RuntimeError(f"missing register {name}")
    return int(register.GetValueAsUnsigned())


def _actor(process: Any, address: int) -> dict[str, int]:
    # Pinned Darwin arm64 NativeMonst prefix, independently asserted by the
    # native entity reader: m_id=16, movement=24, mx/my=28/29.
    raw = _read(process, address, 96)
    return {
        "entity_id": int(struct.unpack_from("<I", raw, 16)[0]),
        "movement_points": int(struct.unpack_from("<h", raw, 24)[0]),
        "native_x": int(struct.unpack_from("<b", raw, 28)[0]),
        "native_y": int(struct.unpack_from("<b", raw, 29)[0]),
    }


def _line(frame: Any) -> dict[str, Any]:
    entry = frame.GetLineEntry()
    file_spec = entry.GetFileSpec() if entry and entry.IsValid() else None
    return {
        "function": str(frame.GetFunctionName() or "").lstrip("_"),
        "source_file": str(file_spec.GetFilename() or "") if file_spec else "",
        "source_line": int(entry.GetLine()) if entry and entry.IsValid() else None,
    }


def _arm_return(frame: Any, context: dict[str, Any]) -> None:
    address = _reg(frame, "x30")
    if address <= 0:
        raise RuntimeError("invalid mcalcmove return address")
    caller = frame.GetThread().GetFrameAtIndex(1)
    if not caller or not caller.IsValid() or int(caller.GetSP()) <= 0:
        raise RuntimeError("missing mcalcmove caller frame")
    target = frame.GetThread().GetProcess().GetTarget()
    breakpoint = target.BreakpointCreateByAddress(address)
    breakpoint.SetThreadID(frame.GetThread().GetThreadID())
    breakpoint.SetScriptCallbackFunction(f"{__name__}.on_return")
    context["expected_caller_sp"] = int(caller.GetSP())
    _CONTEXTS[int(breakpoint.GetID())] = context


def on_mcalcmove_entry(frame: Any, breakpoint_location: Any, _internal: dict[str, Any]) -> bool:
    del breakpoint_location, _internal
    state = _state()
    if state is None:
        return False
    try:
        address = _reg(frame, "x0")
        actor = _actor(frame.GetThread().GetProcess(), address)
        if actor["entity_id"] <= 0:
            raise RuntimeError("mcalcmove actor has invalid stable entity ID")
        context = {
            "kind": "mcalcmove_return",
            "step": state["step"],
            "action": state["action"],
            "actor": actor,
            "actor_address": address,
            "entry_location": _line(frame),
        }
        _arm_return(frame, context)
    except Exception as error:  # pragma: no cover - LLDB host only
        _write({"kind": "trace_error", "step": state["step"], "action": state["action"], "error": str(error)})
    return False


def on_return(frame: Any, breakpoint_location: Any, _internal: dict[str, Any]) -> bool:
    global _NEXT
    del _internal
    breakpoint = breakpoint_location.GetBreakpoint()
    breakpoint_id = int(breakpoint.GetID())
    context = _CONTEXTS.get(breakpoint_id)
    if context is None:
        return False
    try:
        if int(frame.GetSP()) != context["expected_caller_sp"]:
            return False
        _CONTEXTS.pop(breakpoint_id, None)
        frame.GetThread().GetProcess().GetTarget().BreakpointDelete(breakpoint_id)
        context.pop("expected_caller_sp", None)
        process = frame.GetThread().GetProcess()
        actor_address = context.pop("actor_address")
        after = _actor(process, actor_address)
        if after["entity_id"] != context["actor"]["entity_id"]:
            raise RuntimeError("mcalcmove actor identity changed before exact return")
        allocation = _reg(frame, "x0")
        if allocation < 0:
            raise RuntimeError("mcalcmove returned a negative allocation")
        context.update({
            "allocation": allocation,
            "actor_after": after,
            "return_location": _line(frame),
            "event_id": _NEXT,
        })
        _NEXT += 1
        _write(context)
    except Exception as error:  # pragma: no cover - LLDB host only
        _write({"kind": "trace_error", "step": context["step"], "action": context["action"], "error": str(error)})
    return False


def __lldb_init_module(debugger: Any, _internal: dict[str, Any]) -> None:
    del _internal
    breakpoint = debugger.GetSelectedTarget().BreakpointCreateByName("mcalcmove")
    breakpoint.SetScriptCallbackFunction(f"{__name__}.on_mcalcmove_entry")
