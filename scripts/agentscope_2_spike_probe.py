#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentScope 2.x spike probe for ainvestor.

Isolated API survival checks against whatever `agentscope` is importable in the
current interpreter. Run inside a dedicated spike venv with agentscope==2.0.5:

    python3 -m venv .venv-as205-spike
    source .venv-as205-spike/bin/activate
    pip install "agentscope==2.0.5"
    python scripts/agentscope_2_spike_probe.py --out docs/spike-as205 --fail-on critical

Exit codes:
    0  ok (no failures at the selected fail-on level)
    1  probe runner error
    2  critical check failed (--fail-on critical|high|all)
    3  high check failed (--fail-on high|all)
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import importlib
import inspect
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_INFO = "info"

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_WARN = "warn"
STATUS_SKIP = "skip"
STATUS_INFO = "info"


@dataclasses.dataclass
class CheckResult:
    id: str
    title: str
    severity: str
    status: str
    detail: str = ""
    evidence: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class ProbeContext:
    def __init__(self) -> None:
        self.results: List[CheckResult] = []
        self.exports: Dict[str, List[str]] = {}
        self.meta: Dict[str, Any] = {}

    def add(self, result: CheckResult) -> CheckResult:
        self.results.append(result)
        return result

    def record(
        self,
        id: str,
        title: str,
        severity: str,
        status: str,
        detail: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> CheckResult:
        return self.add(
            CheckResult(
                id=id,
                title=title,
                severity=severity,
                status=status,
                detail=detail,
                evidence=evidence or {},
                error=error,
            )
        )


def _safe_dir(mod: Any) -> List[str]:
    return sorted(x for x in dir(mod) if not x.startswith("_"))


def _import(path: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        return importlib.import_module(path), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _call_optional(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Tuple[Any, Optional[str]]:
    try:
        return fn(*args, **kwargs), None
    except TypeError:
        # retry with no kwargs if signature differs
        try:
            return fn(*args), None
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def check_version(ctx: ProbeContext, expected: Optional[str]) -> None:
    mod, err = _import("agentscope")
    if err or mod is None:
        ctx.record(
            "P0-01",
            "Import agentscope",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="Cannot import agentscope in this interpreter",
            error=err,
        )
        return

    version = getattr(mod, "__version__", None) or getattr(mod, "version", None)
    ctx.meta["agentscope_version"] = version
    ctx.meta["agentscope_file"] = getattr(mod, "__file__", None)
    ctx.exports["agentscope"] = _safe_dir(mod)

    if expected and version and str(version) != str(expected):
        # Allow post releases like 2.0.5.post1 only if expected is prefix? keep strict.
        ctx.record(
            "P0-01",
            f"Version is {expected}",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail=f"Installed version is {version!r}, expected {expected!r}",
            evidence={"version": version, "expected": expected},
        )
    elif expected and not version:
        ctx.record(
            "P0-01",
            f"Version is {expected}",
            SEVERITY_HIGH,
            STATUS_WARN,
            detail="agentscope has no __version__; import ok but cannot verify pin",
            evidence={"expected": expected},
        )
    else:
        ctx.record(
            "P0-01",
            "Import agentscope / version",
            SEVERITY_CRITICAL,
            STATUS_PASS,
            detail=f"version={version}",
            evidence={"version": version, "file": ctx.meta.get("agentscope_file")},
        )


def check_module_exports(ctx: ProbeContext) -> None:
    modules = [
        ("agent", "P0-02"),
        ("message", "P0-03"),
        ("tool", "P0-04"),
        ("pipeline", "P0-06"),
        ("memory", "P0-08"),
        ("model", "P1-01"),
        ("formatter", "P1-03"),
        ("event", "P1-06"),
    ]
    for name, _hint in modules:
        mod, err = _import(f"agentscope.{name}")
        if err or mod is None:
            ctx.exports[name] = []
            # event may be 2.0-only; missing on accident still useful signal
            severity = SEVERITY_CRITICAL if name in {"agent", "message", "tool", "memory"} else SEVERITY_HIGH
            if name == "pipeline":
                severity = SEVERITY_CRITICAL
            if name == "event":
                severity = SEVERITY_MEDIUM
            ctx.record(
                f"EXP-{name}",
                f"Import agentscope.{name}",
                severity,
                STATUS_FAIL if name != "event" else STATUS_WARN,
                detail=f"agentscope.{name} not importable",
                error=err,
            )
        else:
            pubs = _safe_dir(mod)
            ctx.exports[name] = pubs
            ctx.record(
                f"EXP-{name}",
                f"Import agentscope.{name}",
                SEVERITY_INFO,
                STATUS_PASS,
                detail=f"{len(pubs)} public names",
                evidence={"exports_sample": pubs[:40]},
            )


def check_react_agent(ctx: ProbeContext) -> None:
    mod, err = _import("agentscope.agent")
    if err or mod is None:
        ctx.record(
            "P0-02",
            "ReActAgent (or equivalent) available",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            error=err,
        )
        return

    candidates = []
    for name in ("ReActAgent", "Agent", "ReActAgentBase", "AgentBase"):
        if hasattr(mod, name):
            candidates.append(name)

    react = getattr(mod, "ReActAgent", None)
    agent = getattr(mod, "Agent", None)
    base = getattr(mod, "AgentBase", None) or getattr(mod, "ReActAgentBase", None)

    evidence: Dict[str, Any] = {
        "candidates": candidates,
        "has_ReActAgent": react is not None,
        "has_Agent": agent is not None,
    }

    target = react or agent
    if target is None:
        ctx.record(
            "P0-02",
            "ReActAgent (or equivalent) available",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="Neither ReActAgent nor Agent found in agentscope.agent",
            evidence=evidence,
        )
        return

    # Subclass probe
    subclass_ok = False
    subclass_error = None
    try:
        class _SpikeAgent(target):  # type: ignore[misc,valid-type]
            pass

        subclass_ok = True
        evidence["subclass_of"] = target.__name__
    except Exception as exc:  # noqa: BLE001
        subclass_error = f"{type(exc).__name__}: {exc}"

    # reply / reply_stream presence on class
    methods = []
    for m in ("reply", "reply_stream", "__call__", "observe"):
        if hasattr(target, m):
            methods.append(m)
    evidence["methods"] = methods
    evidence["init_sig"] = str(inspect.signature(target.__init__)) if hasattr(target, "__init__") else None

    if "reply" not in methods and "reply_stream" not in methods and "__call__" not in methods:
        ctx.record(
            "P0-02",
            "ReActAgent (or equivalent) available",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail=f"Found {target.__name__} but no reply/reply_stream/__call__",
            evidence=evidence,
            error=subclass_error,
        )
        return

    status = STATUS_PASS
    detail_parts = [f"using {target.__name__}", f"methods={methods}"]
    if not subclass_ok:
        status = STATUS_WARN
        detail_parts.append(f"subclass failed: {subclass_error}")
    if react is None and agent is not None:
        detail_parts.append("ReActAgent missing; Agent present (migration to new primary API likely)")

    ctx.record(
        "P0-02",
        "ReActAgent (or equivalent) available",
        SEVERITY_CRITICAL,
        status if status != STATUS_WARN else STATUS_WARN,
        detail="; ".join(detail_parts),
        evidence=evidence,
        error=subclass_error,
    )

    # P0-07 reply shape
    if "reply" in methods:
        ctx.record(
            "P0-07",
            "reply() available for full-answer style calls",
            SEVERITY_CRITICAL,
            STATUS_PASS,
            detail="Class exposes reply(); runtime return type still needs PoC",
            evidence={"method": "reply"},
        )
    elif "reply_stream" in methods:
        ctx.record(
            "P0-07",
            "reply() available for full-answer style calls",
            SEVERITY_CRITICAL,
            STATUS_WARN,
            detail="Only reply_stream found — pipeline must drain events to text",
            evidence={"method": "reply_stream"},
        )
    else:
        ctx.record(
            "P0-07",
            "reply() available for full-answer style calls",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="No reply/reply_stream on agent class",
            evidence=evidence,
        )

    if base is not None:
        ctx.record(
            "P1-SUB",
            "Agent base class present",
            SEVERITY_LOW,
            STATUS_INFO,
            detail=getattr(base, "__name__", str(base)),
        )


def check_message_api(ctx: ProbeContext) -> None:
    mod, err = _import("agentscope.message")
    if err or mod is None:
        ctx.record(
            "P0-03",
            "Message construction (Msg / UserMsg)",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            error=err,
        )
        return

    evidence: Dict[str, Any] = {"exports_hit": []}
    constructed = None
    construct_path = None
    text_out = None

    # Prefer classic Msg(name, content, role) — ainvestor style
    Msg = getattr(mod, "Msg", None)
    if Msg is not None:
        evidence["exports_hit"].append("Msg")
        for kwargs in (
            {"name": "system", "content": "hello spike", "role": "user"},
            {},
        ):
            if kwargs:
                obj, e = _call_optional(Msg, **kwargs)
            else:
                # positional classic
                try:
                    obj = Msg("system", "hello spike", "user")
                    e = None
                except Exception as exc:  # noqa: BLE001
                    obj, e = None, f"{type(exc).__name__}: {exc}"
            if obj is not None:
                constructed = obj
                construct_path = f"Msg({kwargs or 'name,content,role'})"
                break
            evidence.setdefault("Msg_errors", []).append(e)

    # 2.0-style UserMsg
    if constructed is None:
        for alt in ("UserMsg", "AssistantMsg", "SystemMsg", "TextMsg"):
            cls = getattr(mod, alt, None)
            if cls is None:
                continue
            evidence["exports_hit"].append(alt)
            # try common patterns
            trials = [
                lambda c=cls: c("hello spike"),
                lambda c=cls: c(name="user", content="hello spike"),
                lambda c=cls: c("user", "hello spike"),
                lambda c=cls: c(content="hello spike"),
            ]
            for trial in trials:
                try:
                    constructed = trial()
                    construct_path = alt
                    break
                except Exception as exc:  # noqa: BLE001
                    evidence.setdefault(f"{alt}_errors", []).append(str(exc))
            if constructed is not None:
                break

    TextBlock = getattr(mod, "TextBlock", None)
    if TextBlock is not None:
        evidence["exports_hit"].append("TextBlock")
        try:
            # 1.x style
            try:
                tb = TextBlock(type="text", text="block")
            except TypeError:
                tb = TextBlock(text="block")
            evidence["TextBlock_sample"] = repr(tb)[:200]
        except Exception as exc:  # noqa: BLE001
            evidence["TextBlock_error"] = f"{type(exc).__name__}: {exc}"

    if constructed is not None:
        text_out = _extract_text_generic(constructed)
        evidence["construct_path"] = construct_path
        evidence["extracted_text"] = text_out
        evidence["constructed_type"] = type(constructed).__name__
        ok = bool(text_out) or hasattr(constructed, "content")
        ctx.record(
            "P0-03",
            "Message construction (Msg / UserMsg)",
            SEVERITY_CRITICAL,
            STATUS_PASS if ok else STATUS_WARN,
            detail=f"constructed via {construct_path}; extracted={text_out!r}",
            evidence=evidence,
        )
    else:
        ctx.record(
            "P0-03",
            "Message construction (Msg / UserMsg)",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="Could not construct Msg/UserMsg with known signatures",
            evidence=evidence,
        )


def _extract_text_generic(content: Any) -> str:
    """Best-effort text extraction compatible with ainvestor pipeline ideas."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # Msg-like
    if hasattr(content, "get_text_content") and callable(content.get_text_content):
        try:
            return str(content.get_text_content() or "")
        except Exception:  # noqa: BLE001
            pass
    if hasattr(content, "content"):
        return _extract_text_generic(getattr(content, "content"))
    if isinstance(content, list):
        parts = []
        for item in content:
            piece = _extract_text_generic(item)
            if piece:
                parts.append(piece)
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        if content.get("type") == "text" and "text" in content:
            return str(content.get("text") or "")
        if "text" in content:
            return str(content.get("text") or "")
        if "content" in content:
            return _extract_text_generic(content.get("content"))
    if hasattr(content, "text"):
        return str(getattr(content, "text") or "")
    return str(content)


def check_toolkit(ctx: ProbeContext) -> None:
    mod, err = _import("agentscope.tool")
    if err or mod is None:
        ctx.record(
            "P0-04",
            "Toolkit custom function registration",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            error=err,
        )
        ctx.record(
            "P0-05",
            "ToolResponse / text return path",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            error=err,
        )
        return

    Toolkit = getattr(mod, "Toolkit", None)
    ToolResponse = getattr(mod, "ToolResponse", None)
    evidence: Dict[str, Any] = {
        "has_Toolkit": Toolkit is not None,
        "has_ToolResponse": ToolResponse is not None,
        "toolkit_methods": _safe_dir(Toolkit) if Toolkit else [],
        "toolresponse_methods": _safe_dir(ToolResponse) if ToolResponse else [],
    }

    if Toolkit is None:
        ctx.record(
            "P0-04",
            "Toolkit custom function registration",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="Toolkit class missing",
            evidence=evidence,
        )
    else:
        register_names = [
            n
            for n in (
                "register_tool_function",
                "register",
                "register_tool",
                "add_tool",
                "add",
                "extend",
            )
            if hasattr(Toolkit, n)
        ]
        evidence["register_methods"] = register_names

        toolkit = None
        init_error = None
        try:
            # 1.x: Toolkit()
            toolkit = Toolkit()
        except TypeError as exc:
            init_error = str(exc)
            # 2.0 README: Toolkit(tools=[...])
            try:
                toolkit = Toolkit(tools=[])
            except Exception as exc2:  # noqa: BLE001
                init_error = f"{init_error}; fallback: {type(exc2).__name__}: {exc2}"
                toolkit = None
        except Exception as exc:  # noqa: BLE001
            init_error = f"{type(exc).__name__}: {exc}"

        def _sample_tool(x: int = 1, y: int = 2) -> Any:
            """Add two integers for spike probe."""
            return x + y

        registered = False
        reg_error = None
        if toolkit is not None and register_names:
            for method_name in register_names:
                method = getattr(toolkit, method_name)
                for trial in (
                    lambda m=method: m(_sample_tool),
                    lambda m=method: m(func=_sample_tool),
                    lambda m=method: m(tool=_sample_tool),
                    lambda m=method: m(_sample_tool, name="sample_tool"),
                ):
                    try:
                        trial()
                        registered = True
                        evidence["register_used"] = method_name
                        break
                    except Exception as exc:  # noqa: BLE001
                        reg_error = f"{type(exc).__name__}: {exc}"
                if registered:
                    break
        elif toolkit is not None and not register_names:
            # Maybe constructor-only tools=[Tool objects]
            evidence["note"] = "No register_* method; may require Tool class instances in constructor"
            reg_error = "no register method on Toolkit"

        if registered:
            ctx.record(
                "P0-04",
                "Toolkit custom function registration",
                SEVERITY_CRITICAL,
                STATUS_PASS,
                detail=f"Registered via {evidence.get('register_used')}",
                evidence=evidence,
            )
        elif toolkit is not None:
            ctx.record(
                "P0-04",
                "Toolkit custom function registration",
                SEVERITY_CRITICAL,
                STATUS_FAIL if not register_names else STATUS_WARN,
                detail="Toolkit created but custom function registration failed or API changed",
                evidence=evidence,
                error=reg_error or init_error,
            )
        else:
            ctx.record(
                "P0-04",
                "Toolkit custom function registration",
                SEVERITY_CRITICAL,
                STATUS_FAIL,
                detail="Could not instantiate Toolkit",
                evidence=evidence,
                error=init_error,
            )

    # ToolResponse
    msg_mod, _ = _import("agentscope.message")
    TextBlock = getattr(msg_mod, "TextBlock", None) if msg_mod else None
    if ToolResponse is None:
        ctx.record(
            "P0-05",
            "ToolResponse / text return path",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="ToolResponse missing",
            evidence=evidence,
        )
        return

    tr = None
    tr_error = None
    paths_tried = []
    # ainvestor style
    if TextBlock is not None:
        try:
            try:
                block = TextBlock(type="text", text="ok")
            except TypeError:
                block = TextBlock(text="ok")
            tr = ToolResponse(content=[block])
            paths_tried.append("ToolResponse(content=[TextBlock...])")
        except Exception as exc:  # noqa: BLE001
            tr_error = f"{type(exc).__name__}: {exc}"
            paths_tried.append(f"TextBlock path failed: {tr_error}")

    if tr is None and hasattr(ToolResponse, "text"):
        try:
            tr = ToolResponse.text("ok")  # type: ignore[attr-defined]
            paths_tried.append("ToolResponse.text")
        except Exception as exc:  # noqa: BLE001
            paths_tried.append(f"ToolResponse.text failed: {exc}")

    if tr is None:
        for trial in (
            lambda: ToolResponse(content="ok"),
            lambda: ToolResponse("ok"),
            lambda: ToolResponse(text="ok"),
            lambda: ToolResponse(content=[{"type": "text", "text": "ok"}]),
        ):
            try:
                tr = trial()
                paths_tried.append(trial.__name__ if hasattr(trial, "__name__") else "alt")
                break
            except Exception as exc:  # noqa: BLE001
                paths_tried.append(str(exc))

    evidence["toolresponse_paths"] = paths_tried
    if tr is not None:
        ctx.record(
            "P0-05",
            "ToolResponse / text return path",
            SEVERITY_CRITICAL,
            STATUS_PASS,
            detail=f"Constructed ToolResponse; paths={paths_tried}",
            evidence=evidence,
        )
    else:
        ctx.record(
            "P0-05",
            "ToolResponse / text return path",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="Could not construct ToolResponse in known forms",
            evidence=evidence,
            error=tr_error,
        )


def check_msghub(ctx: ProbeContext) -> None:
    mod, err = _import("agentscope.pipeline")
    team_note = None
    # Also peek agent team helpers if any
    for extra in ("agentscope.pipeline", "agentscope.agent", "agentscope.team"):
        m, e = _import(extra)
        if m and any(n for n in _safe_dir(m) if "Team" in n or "MsgHub" in n or "ChatRoom" in n):
            team_note = {
                "module": extra,
                "hits": [n for n in _safe_dir(m) if "Team" in n or "MsgHub" in n or "ChatRoom" in n],
            }
            break

    if err or mod is None:
        ctx.record(
            "P0-06",
            "MsgHub or multi-agent broadcast primitive",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="agentscope.pipeline missing",
            error=err,
            evidence={"team_note": team_note},
        )
        return

    MsgHub = getattr(mod, "MsgHub", None)
    ChatRoom = getattr(mod, "ChatRoom", None)
    evidence: Dict[str, Any] = {
        "has_MsgHub": MsgHub is not None,
        "has_ChatRoom": ChatRoom is not None,
        "pipeline_exports": ctx.exports.get("pipeline") or _safe_dir(mod),
        "team_note": team_note,
    }

    if MsgHub is None and ChatRoom is None:
        ctx.record(
            "P0-06",
            "MsgHub or multi-agent broadcast primitive",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="No MsgHub/ChatRoom — conference Phase3 needs redesign",
            evidence=evidence,
        )
        return

    # Structural check: async context manager?
    target = MsgHub or ChatRoom
    is_async_cm = (
        hasattr(target, "__aenter__")
        or hasattr(target, "__aexit__")
        or inspect.isasyncgenfunction(getattr(target, "__call__", None))
    )
    # class itself may implement on instances; check source-ish via annotations
    evidence["target"] = getattr(target, "__name__", str(target))
    try:
        evidence["sig"] = str(inspect.signature(target))
    except Exception:  # noqa: BLE001
        evidence["sig"] = None

    # Try instantiating with empty participants if possible (no agent run)
    inst = None
    inst_err = None
    try:
        inst = target(participants=[])  # type: ignore[misc]
    except TypeError:
        try:
            inst = target([])  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            inst_err = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001
        inst_err = f"{type(exc).__name__}: {exc}"

    if inst is not None:
        evidence["instance_type"] = type(inst).__name__
        evidence["is_async_context"] = hasattr(inst, "__aenter__") and hasattr(inst, "__aexit__")
        ctx.record(
            "P0-06",
            "MsgHub or multi-agent broadcast primitive",
            SEVERITY_CRITICAL,
            STATUS_PASS,
            detail=f"{evidence['target']} instantiable; async_cm={evidence.get('is_async_context')}",
            evidence=evidence,
        )
    else:
        # Still pass-with-warn if class exists — PoC must validate semantics
        ctx.record(
            "P0-06",
            "MsgHub or multi-agent broadcast primitive",
            SEVERITY_CRITICAL,
            STATUS_WARN,
            detail=f"{evidence['target']} exists but default construct failed — manual PoC-C required",
            evidence=evidence,
            error=inst_err,
        )


def check_memory(ctx: ProbeContext) -> None:
    mod, err = _import("agentscope.memory")
    if err or mod is None:
        ctx.record(
            "P0-08",
            "InMemoryMemory + clear",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            error=err,
        )
        return

    InMemoryMemory = getattr(mod, "InMemoryMemory", None)
    evidence: Dict[str, Any] = {
        "has_InMemoryMemory": InMemoryMemory is not None,
        "memory_exports": ctx.exports.get("memory") or _safe_dir(mod),
        "has_ReMeTaskLongTermMemory": hasattr(mod, "ReMeTaskLongTermMemory"),
        "has_LongTermMemoryBase": hasattr(mod, "LongTermMemoryBase"),
        "has_Mem0LongTermMemory": hasattr(mod, "Mem0LongTermMemory"),
    }

    if InMemoryMemory is None:
        ctx.record(
            "P0-08",
            "InMemoryMemory + clear",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="InMemoryMemory missing",
            evidence=evidence,
        )
        return

    try:
        mem = InMemoryMemory()
    except Exception as exc:  # noqa: BLE001
        ctx.record(
            "P0-08",
            "InMemoryMemory + clear",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="Cannot instantiate InMemoryMemory",
            evidence=evidence,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    clear_fn = getattr(mem, "clear", None)
    if clear_fn is None:
        ctx.record(
            "P0-08",
            "InMemoryMemory + clear",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="memory.clear missing — Phase0 needs alternative",
            evidence=evidence,
        )
        return

    async def _do_clear() -> None:
        res = clear_fn()
        if inspect.isawaitable(res):
            await res

    try:
        asyncio.run(_do_clear())
        ctx.record(
            "P0-08",
            "InMemoryMemory + clear",
            SEVERITY_CRITICAL,
            STATUS_PASS,
            detail="InMemoryMemory.clear() callable",
            evidence=evidence,
        )
    except Exception as exc:  # noqa: BLE001
        ctx.record(
            "P0-08",
            "InMemoryMemory + clear",
            SEVERITY_CRITICAL,
            STATUS_FAIL,
            detail="clear() raised",
            evidence=evidence,
            error=f"{type(exc).__name__}: {exc}",
        )

    # P1 ReMe
    if evidence["has_ReMeTaskLongTermMemory"]:
        ctx.record(
            "P1-04",
            "ReMeTaskLongTermMemory export present",
            SEVERITY_MEDIUM,
            STATUS_PASS,
            detail="Symbol exists; constructor/live wiring needs PoC",
            evidence=evidence,
        )
    else:
        ctx.record(
            "P1-04",
            "ReMeTaskLongTermMemory export present",
            SEVERITY_MEDIUM,
            STATUS_WARN,
            detail="ReMeTaskLongTermMemory missing — enable-memory path may break",
            evidence=evidence,
        )


def check_models_formatters(ctx: ProbeContext) -> None:
    model_mod, err_m = _import("agentscope.model")
    fmt_mod, err_f = _import("agentscope.formatter")
    cred_mod, err_c = _import("agentscope.credential")

    model_names = [
        "OpenAIChatModel",
        "DashScopeChatModel",
        "AnthropicChatModel",
        "GeminiChatModel",
        "OllamaChatModel",
    ]
    fmt_names = [
        "OpenAIChatFormatter",
        "DashScopeChatFormatter",
        "AnthropicChatFormatter",
        "GeminiChatFormatter",
        "OllamaChatFormatter",
        "OpenAIMultiAgentFormatter",
        "DashScopeMultiAgentFormatter",
    ]

    found_models = {}
    if model_mod:
        for n in model_names:
            found_models[n] = hasattr(model_mod, n)
        # init sig for OpenAI
        oai = getattr(model_mod, "OpenAIChatModel", None)
        if oai is not None:
            try:
                found_models["OpenAIChatModel_sig"] = str(inspect.signature(oai.__init__))
            except Exception:  # noqa: BLE001
                pass
    else:
        ctx.record(
            "P1-01",
            "OpenAIChatModel / provider models",
            SEVERITY_HIGH,
            STATUS_FAIL,
            error=err_m,
        )

    if model_mod:
        if found_models.get("OpenAIChatModel"):
            sig = str(found_models.get("OpenAIChatModel_sig", ""))
            base_url_hint = "base_url" in sig or "client_args" in sig or "api_key" in sig
            ctx.record(
                "P1-01",
                "OpenAIChatModel present (base_url compatibility manual)",
                SEVERITY_HIGH,
                STATUS_PASS if base_url_hint else STATUS_WARN,
                detail=f"sig={found_models.get('OpenAIChatModel_sig')}",
                evidence=found_models,
            )
        else:
            ctx.record(
                "P1-01",
                "OpenAIChatModel present",
                SEVERITY_HIGH,
                STATUS_FAIL,
                detail="OpenAIChatModel missing",
                evidence=found_models,
            )

        if found_models.get("DashScopeChatModel"):
            ctx.record(
                "P1-02",
                "DashScopeChatModel present",
                SEVERITY_HIGH,
                STATUS_PASS,
                evidence=found_models,
            )
        else:
            ctx.record(
                "P1-02",
                "DashScopeChatModel present",
                SEVERITY_HIGH,
                STATUS_WARN,
                detail="DashScopeChatModel missing",
                evidence=found_models,
            )

    found_fmt = {}
    if fmt_mod:
        for n in fmt_names:
            found_fmt[n] = hasattr(fmt_mod, n)
        ok = found_fmt.get("OpenAIChatFormatter") or found_fmt.get("DashScopeChatFormatter")
        ctx.record(
            "P1-03",
            "Chat formatters present",
            SEVERITY_HIGH,
            STATUS_PASS if ok else STATUS_FAIL,
            evidence=found_fmt,
            error=None if ok else err_f,
        )
    else:
        ctx.record(
            "P1-03",
            "Chat formatters present",
            SEVERITY_HIGH,
            STATUS_WARN,
            detail="formatter module missing — 2.0 may fold formatting elsewhere",
            error=err_f,
        )

    if cred_mod:
        ctx.record(
            "P1-CRED",
            "agentscope.credential module present",
            SEVERITY_MEDIUM,
            STATUS_INFO,
            detail="2.0-style credentials may be required",
            evidence={"exports": _safe_dir(cred_mod)},
        )
    else:
        ctx.record(
            "P1-CRED",
            "agentscope.credential module present",
            SEVERITY_LOW,
            STATUS_SKIP,
            detail="No credential module (may still use api_key kwargs)",
            error=err_c,
        )


def check_hitl_interrupt_symbols(ctx: ProbeContext) -> None:
    # Symbols may live in event / agent / message
    search_mods = []
    for name in ("event", "agent", "message", "tool", "types"):
        mod, err = _import(f"agentscope.{name}")
        if mod:
            search_mods.append((name, mod))

    want_hitl = [
        "RequireUserConfirmEvent",
        "UserConfirmResultEvent",
        "RequireExternalExecutionEvent",
        "ExternalExecutionResultEvent",
        "ConfirmResult",
        "UserInterruptEvent",
    ]
    found: Dict[str, str] = {}
    for sym in want_hitl:
        for name, mod in search_mods:
            if hasattr(mod, sym):
                found[sym] = f"agentscope.{name}"
                break

    evidence = {"found": found, "missing": [s for s in want_hitl if s not in found]}
    if found:
        ctx.record(
            "P1-06",
            "HITL / interrupt event symbols",
            SEVERITY_MEDIUM,
            STATUS_PASS,
            detail=f"found {sorted(found)}",
            evidence=evidence,
        )
    else:
        ctx.record(
            "P1-06",
            "HITL / interrupt event symbols",
            SEVERITY_MEDIUM,
            STATUS_WARN,
            detail="No documented HITL event symbols found in common modules",
            evidence=evidence,
        )

    # UserAgent
    agent_mod, _ = _import("agentscope.agent")
    if agent_mod and hasattr(agent_mod, "UserAgent"):
        ctx.record(
            "P1-08",
            "UserAgent present",
            SEVERITY_MEDIUM,
            STATUS_PASS,
            detail="UserAgent export exists",
        )
    else:
        ctx.record(
            "P1-08",
            "UserAgent present",
            SEVERITY_MEDIUM,
            STATUS_WARN,
            detail="UserAgent missing — human-as-participant needs alternate path",
        )


async def _live_llm_smoke(timeout: float) -> Dict[str, Any]:
    """Optional live call; best-effort across 1.x/2.0 APIs."""
    out: Dict[str, Any] = {"steps": []}

    def step(name: str, **kwargs: Any) -> None:
        out["steps"].append({"name": name, **kwargs})

    model_mod, err = _import("agentscope.model")
    agent_mod, err_a = _import("agentscope.agent")
    msg_mod, err_m = _import("agentscope.message")
    tool_mod, err_t = _import("agentscope.tool")
    fmt_mod, _ = _import("agentscope.formatter")
    mem_mod, _ = _import("agentscope.memory")

    if err or agent_mod is None or msg_mod is None:
        raise RuntimeError(f"Missing core modules: model={err} agent={err_a} message={err_m}")

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("No OPENAI_API_KEY or DASHSCOPE_API_KEY in environment")

    use_dashscope = bool(os.getenv("DASHSCOPE_API_KEY")) and not os.getenv("OPENAI_API_KEY")
    model = None
    formatter = None

    if use_dashscope and hasattr(model_mod, "DashScopeChatModel"):
        Model = model_mod.DashScopeChatModel
        model_name = os.getenv("MODEL_NAME", "qwen-plus")
        # try credential style then api_key style
        try:
            cred_mod, _ = _import("agentscope.credential")
            if cred_mod and hasattr(cred_mod, "DashScopeCredential"):
                cred = cred_mod.DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"])
                model = Model(model_name=model_name, credential=cred)
            else:
                model = Model(model_name=model_name, api_key=os.environ["DASHSCOPE_API_KEY"], stream=False)
        except Exception:
            model = Model(model_name=model_name, api_key=os.environ["DASHSCOPE_API_KEY"], stream=False)
        if fmt_mod and hasattr(fmt_mod, "DashScopeChatFormatter"):
            formatter = fmt_mod.DashScopeChatFormatter()
        step("model", provider="dashscope", model_name=model_name)
    else:
        Model = getattr(model_mod, "OpenAIChatModel", None)
        if Model is None:
            raise RuntimeError("OpenAIChatModel not available")
        model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        kwargs: Dict[str, Any] = {
            "model_name": model_name,
            "api_key": os.environ.get("OPENAI_API_KEY", api_key),
            "stream": False,
        }
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            # different versions accept base_url or client_kwargs
            try:
                model = Model(**kwargs, base_url=base_url)
            except TypeError:
                try:
                    model = Model(**kwargs, client_args={"base_url": base_url})
                except TypeError:
                    model = Model(**kwargs)
        else:
            model = Model(**kwargs)
        if fmt_mod and hasattr(fmt_mod, "OpenAIChatFormatter"):
            formatter = fmt_mod.OpenAIChatFormatter()
        step("model", provider="openai_compat", model_name=model_name, base_url=base_url)

    # toolkit with custom function
    def spike_add(a: int, b: int) -> Any:
        """Return the sum of a and b. Args: a, b integers."""
        ToolResponse = getattr(tool_mod, "ToolResponse", None) if tool_mod else None
        TextBlock = getattr(msg_mod, "TextBlock", None)
        total = a + b
        text = f"sum={total}"
        if ToolResponse is None:
            return text
        if TextBlock is not None:
            try:
                try:
                    block = TextBlock(type="text", text=text)
                except TypeError:
                    block = TextBlock(text=text)
                return ToolResponse(content=[block])
            except Exception:  # noqa: BLE001
                pass
        try:
            return ToolResponse(content=[{"type": "text", "text": text}])
        except Exception:  # noqa: BLE001
            return text

    toolkit = None
    if tool_mod and hasattr(tool_mod, "Toolkit"):
        Toolkit = tool_mod.Toolkit
        try:
            toolkit = Toolkit()
        except TypeError:
            toolkit = Toolkit(tools=[])
        if hasattr(toolkit, "register_tool_function"):
            toolkit.register_tool_function(spike_add)
        step("toolkit", ok=True)

    AgentCls = getattr(agent_mod, "ReActAgent", None) or getattr(agent_mod, "Agent", None)
    if AgentCls is None:
        raise RuntimeError("No Agent/ReActAgent")

    memory = None
    if mem_mod and hasattr(mem_mod, "InMemoryMemory"):
        memory = mem_mod.InMemoryMemory()

    agent_kwargs: Dict[str, Any] = {
        "name": "spike_agent",
        "model": model,
    }
    # sys_prompt vs system_prompt
    for key, val in (
        ("sys_prompt", "You are a spike test agent. Use tools when asked to add numbers."),
        ("system_prompt", "You are a spike test agent. Use tools when asked to add numbers."),
    ):
        try:
            inspect.signature(AgentCls.__init__).bind_partial(self=None, **{key: val})
            agent_kwargs[key] = val
            break
        except Exception:  # noqa: BLE001
            agent_kwargs.setdefault("sys_prompt", val)

    if formatter is not None:
        agent_kwargs["formatter"] = formatter
    if toolkit is not None:
        agent_kwargs["toolkit"] = toolkit
    if memory is not None:
        agent_kwargs["memory"] = memory
    agent_kwargs.setdefault("max_iters", 5)

    try:
        agent = AgentCls(**agent_kwargs)
    except TypeError:
        # drop unknown keys progressively
        agent = None
        last_exc = None
        keys = list(agent_kwargs.keys())
        for drop in ([], ["formatter"], ["memory"], ["toolkit", "formatter"], ["max_iters"]):
            trial = {k: v for k, v in agent_kwargs.items() if k not in drop}
            try:
                agent = AgentCls(**trial)
                step("agent_init", kwargs=list(trial.keys()))
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if agent is None:
            raise RuntimeError(f"Agent init failed: {last_exc}")
    else:
        step("agent_init", kwargs=list(agent_kwargs.keys()))

    # Build message
    Msg = getattr(msg_mod, "Msg", None)
    UserMsg = getattr(msg_mod, "UserMsg", None)
    prompt = "Use the tool to compute 17+25. Then reply with the sum only."
    if Msg is not None:
        try:
            user_msg = Msg(name="user", content=prompt, role="user")
        except TypeError:
            user_msg = Msg("user", prompt, "user")
    elif UserMsg is not None:
        try:
            user_msg = UserMsg(prompt)
        except TypeError:
            user_msg = UserMsg(name="user", content=prompt)
    else:
        raise RuntimeError("No Msg/UserMsg")

    async def _run() -> Any:
        if hasattr(agent, "reply"):
            res = agent.reply(user_msg)
            if inspect.isawaitable(res):
                return await res
            return res
        if hasattr(agent, "reply_stream"):
            chunks = []
            gen = agent.reply_stream(user_msg)
            if inspect.isasyncgen(gen):
                async for ev in gen:
                    chunks.append(ev)
            elif inspect.isawaitable(gen):
                async for ev in await gen:  # type: ignore[misc]
                    chunks.append(ev)
            return chunks
        if callable(agent):
            res = agent(user_msg)
            if inspect.isawaitable(res):
                return await res
            return res
        raise RuntimeError("Agent has no reply/reply_stream/__call__")

    result = await asyncio.wait_for(_run(), timeout=timeout)
    text = _extract_text_generic(result)
    out["result_type"] = type(result).__name__
    out["text"] = text[:1000]
    out["ok"] = "42" in text or "sum=42" in text.lower() or "42" in str(result)
    step("reply", text_preview=text[:200], ok=out["ok"])
    return out


def check_live_llm(ctx: ProbeContext, enabled: bool, timeout: float) -> None:
    if not enabled:
        ctx.record(
            "L-01",
            "Live LLM smoke",
            SEVERITY_HIGH,
            STATUS_SKIP,
            detail="Pass --live-llm to enable (needs API key)",
        )
        return

    try:
        result = asyncio.run(_live_llm_smoke(timeout))
        status = STATUS_PASS if result.get("ok") else STATUS_WARN
        ctx.record(
            "L-01",
            "Live LLM + optional tool smoke",
            SEVERITY_HIGH,
            status,
            detail=f"text_preview={result.get('text', '')[:160]!r}",
            evidence=result,
        )
        if result.get("ok"):
            ctx.record(
                "L-02",
                "Tool calling appeared successful (sum 17+25)",
                SEVERITY_HIGH,
                STATUS_PASS,
                detail="Result contained 42",
                evidence={"text": result.get("text")},
            )
        else:
            ctx.record(
                "L-02",
                "Tool calling appeared successful (sum 17+25)",
                SEVERITY_HIGH,
                STATUS_WARN,
                detail="Model replied but 42 not detected — check tool schema / prompting",
                evidence=result,
            )
    except Exception as exc:  # noqa: BLE001
        ctx.record(
            "L-01",
            "Live LLM smoke",
            SEVERITY_HIGH,
            STATUS_FAIL,
            detail="Live smoke raised",
            error=f"{type(exc).__name__}: {exc}",
            evidence={"traceback": traceback.format_exc()[-2000:]},
        )


def score_decision(results: Sequence[CheckResult]) -> Dict[str, Any]:
    p0_ids = {f"P0-0{i}" for i in range(1, 9)}
    # also accept ids exactly P0-01..08
    p0 = [r for r in results if r.id in p0_ids or r.id.startswith("P0-0")]
    # unique by id prefer last
    by_id: Dict[str, CheckResult] = {}
    for r in results:
        if r.id.startswith("P0-"):
            by_id[r.id] = r
    p0_list = [by_id[k] for k in sorted(by_id) if k.startswith("P0-0")]
    p0_pass = sum(1 for r in p0_list if r.status == STATUS_PASS)
    p0_warn = sum(1 for r in p0_list if r.status == STATUS_WARN)
    p0_fail = sum(1 for r in p0_list if r.status == STATUS_FAIL)
    p0_total = len(p0_list) or 8

    critical_fails = [r for r in results if r.severity == SEVERITY_CRITICAL and r.status == STATUS_FAIL]
    high_fails = [r for r in results if r.severity == SEVERITY_HIGH and r.status == STATUS_FAIL]

    # Decision heuristic aligned with checklist
    if p0_fail >= 2 or len(critical_fails) >= 2:
        decision = "NO-GO"
        rationale = [
            f"P0 fail={p0_fail}, warn={p0_warn}, pass={p0_pass}/{p0_total}",
            "Multiple critical API gaps — prefer stay on 1.x + self-built HITL",
        ]
    elif p0_fail == 0 and p0_warn <= 2 and not critical_fails:
        decision = "GO"
        rationale = [
            f"P0 pass={p0_pass}/{p0_total} (warn={p0_warn})",
            "Core symbols look adaptable; still run Day1 PoC-A/B/C before committing calendar time",
        ]
    else:
        decision = "CONDITIONAL"
        rationale = [
            f"P0 pass={p0_pass}/{p0_total}, fail={p0_fail}, warn={p0_warn}",
            "Migration possible only with rewrite on failed areas; compare to 8–14d HITL-on-1.x",
        ]

    # Highlight conference/tool specifically
    for r in results:
        if r.id == "P0-06" and r.status in {STATUS_FAIL, STATUS_WARN}:
            rationale.append("MsgHub/conference primitive weak — Phase3 cost dominates")
        if r.id == "P0-04" and r.status == STATUS_FAIL:
            rationale.append("Custom Toolkit registration failed — tools layer rewrite")
        if r.id == "P0-07" and r.status in {STATUS_FAIL, STATUS_WARN}:
            rationale.append("Full reply path weak — pipeline text extraction must change")

    return {
        "decision": decision,
        "p0_pass": p0_pass,
        "p0_warn": p0_warn,
        "p0_fail": p0_fail,
        "p0_total": p0_total,
        "critical_fails": [r.id for r in critical_fails],
        "high_fails": [r.id for r in high_fails],
        "rationale": rationale,
    }


def render_markdown(ctx: ProbeContext, decision: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# AgentScope Spike Probe Report")
    lines.append("")
    lines.append(f"- Generated (UTC): `{ctx.meta.get('generated_at')}`")
    lines.append(f"- Python: `{ctx.meta.get('python')}`")
    lines.append(f"- agentscope: `{ctx.meta.get('agentscope_version')}`")
    lines.append(f"- file: `{ctx.meta.get('agentscope_file')}`")
    lines.append("")
    lines.append("## Decision (heuristic)")
    lines.append("")
    lines.append(f"**{decision['decision']}** — P0 pass {decision['p0_pass']}/{decision['p0_total']} "
                 f"(warn {decision['p0_warn']}, fail {decision['p0_fail']})")
    lines.append("")
    for r in decision.get("rationale", []):
        lines.append(f"- {r}")
    lines.append("")
    lines.append("> Automated decision is advisory. Day1 PoC-A/B/C and human checklist override this.")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| ID | Sev | Status | Title | Detail |")
    lines.append("|----|-----|--------|-------|--------|")
    for r in ctx.results:
        detail = (r.detail or r.error or "").replace("|", "\\|").replace("\n", " ")
        if len(detail) > 120:
            detail = detail[:117] + "..."
        lines.append(f"| {r.id} | {r.severity} | **{r.status}** | {r.title} | {detail} |")
    lines.append("")
    lines.append("## Next actions")
    lines.append("")
    if decision["decision"] == "NO-GO":
        lines.append("1. Keep `agentscope>=1.0.x,<2` pin")
        lines.append("2. Build HITL on current pipeline/WebSocket")
        lines.append("3. Archive this report under docs/spike-as205/")
    elif decision["decision"] == "GO":
        lines.append("1. Finish manual PoC-A/B/C in checklist")
        lines.append("2. Recalibrate person-days (expect still 2+ weeks if MsgHub semantics shifted)")
        lines.append("3. Only then open migration branch")
    else:
        lines.append("1. List Rewrite modules from failed P0s")
        lines.append("2. Compare rewrite cost vs HITL-on-1.x (8–14d)")
        lines.append("3. CONDITIONAL go only if sandbox/multi-tenant service is a hard requirement")
    lines.append("")
    lines.append("## Export snapshot")
    lines.append("")
    for mod, names in sorted(ctx.exports.items()):
        lines.append(f"- `{mod}`: {', '.join(names[:25])}{' ...' if len(names) > 25 else ''}")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe AgentScope APIs for ainvestor 2.0 spike")
    p.add_argument("--expected-version", default="2.0.5", help="Expected agentscope version (empty to skip)")
    p.add_argument("--out", type=Path, default=Path("docs/spike-as205"), help="Output directory")
    p.add_argument(
        "--fail-on",
        choices=("none", "critical", "high", "all"),
        default="none",
        help="Exit non-zero when checks at this severity fail",
    )
    p.add_argument("--live-llm", action="store_true", help="Run live model+tool smoke test")
    p.add_argument("--live-timeout", type=float, default=90.0, help="Live smoke timeout seconds")
    p.add_argument("--json-only", action="store_true", help="Print JSON to stdout only")
    return p.parse_args(argv)


def run_probe(args: argparse.Namespace) -> Tuple[ProbeContext, Dict[str, Any]]:
    ctx = ProbeContext()
    ctx.meta["generated_at"] = datetime.now(timezone.utc).isoformat()
    ctx.meta["python"] = sys.version
    ctx.meta["executable"] = sys.executable
    ctx.meta["cwd"] = os.getcwd()
    ctx.meta["live_llm"] = bool(args.live_llm)

    expected = args.expected_version.strip() if args.expected_version else None
    if expected == "":
        expected = None

    check_version(ctx, expected)
    # Stop only when agentscope itself cannot be imported.
    import_failed = any(
        r.id == "P0-01"
        and r.status == STATUS_FAIL
        and "Cannot import agentscope" in (r.detail or "")
        for r in ctx.results
    )
    if import_failed:
        decision = score_decision(ctx.results)
        return ctx, decision

    check_module_exports(ctx)
    check_react_agent(ctx)
    check_message_api(ctx)
    check_toolkit(ctx)
    check_msghub(ctx)
    check_memory(ctx)
    check_models_formatters(ctx)
    check_hitl_interrupt_symbols(ctx)
    check_live_llm(ctx, enabled=args.live_llm, timeout=args.live_timeout)

    decision = score_decision(ctx.results)
    ctx.meta["decision"] = decision
    return ctx, decision


def persist(ctx: ProbeContext, decision: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": ctx.meta,
        "decision": decision,
        "results": [r.to_dict() for r in ctx.results],
    }
    (out_dir / "spike-report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "spike-raw-exports.json").write_text(
        json.dumps(ctx.exports, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "spike-report.md").write_text(
        render_markdown(ctx, decision),
        encoding="utf-8",
    )


def exit_code(results: Sequence[CheckResult], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    critical_failed = any(r.severity == SEVERITY_CRITICAL and r.status == STATUS_FAIL for r in results)
    high_failed = any(r.severity == SEVERITY_HIGH and r.status == STATUS_FAIL for r in results)
    any_failed = any(r.status == STATUS_FAIL for r in results)
    if fail_on == "critical" and critical_failed:
        return 2
    if fail_on == "high" and (critical_failed or high_failed):
        return 3 if not critical_failed else 2
    if fail_on == "all" and any_failed:
        return 2 if critical_failed else 3
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        ctx, decision = run_probe(args)
        if not args.json_only:
            persist(ctx, decision, args.out)
            print(render_markdown(ctx, decision))
            print(f"\nWrote reports under: {args.out.resolve()}")
        else:
            print(json.dumps({"meta": ctx.meta, "decision": decision, "results": [r.to_dict() for r in ctx.results]}, ensure_ascii=False, indent=2))
        return exit_code(ctx.results, args.fail_on)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Probe runner error: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
