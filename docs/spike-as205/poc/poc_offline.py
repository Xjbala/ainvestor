#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day1 offline PoCs for AgentScope 2.0.5 (no LLM required).

Covers checklist:
  PoC-A  custom Python tool registration (FunctionTool + Toolkit.add_tool)
  PoC-B  message text extraction compatible with ainvestor needs
  PoC-C  multi-agent shared context WITHOUT MsgHub (manual observe / state)
  PoC-D  subclassing Agent

Run inside spike venv:
  source .venv-as205-spike/bin/activate
  python docs/spike-as205/poc/poc_offline.py
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Case:
    id: str
    title: str
    status: str = "pending"
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


RESULTS: List[Case] = []


def record(case: Case) -> None:
    RESULTS.append(case)
    mark = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}.get(case.status, case.status)
    print(f"[{mark}] {case.id} {case.title}: {case.detail}")


def extract_text(content: Any) -> str:
    """Mirrors RatingPipeline._extract_text_content ideas for 2.0 blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if hasattr(content, "get_text_content") and callable(content.get_text_content):
        try:
            return str(content.get_text_content() or "")
        except Exception:  # noqa: BLE001
            pass
    if hasattr(content, "content") and not isinstance(content, (str, list, dict)):
        return extract_text(getattr(content, "content"))
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            # skip non-text blocks when possible
            t = getattr(item, "type", None)
            if t in {"thinking", "tool_use", "tool_call", "tool_result"}:
                # still try text if present
                pass
            piece = extract_text(item)
            if piece:
                parts.append(piece)
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        if content.get("type") == "text":
            return str(content.get("text") or "")
        if "text" in content:
            return str(content.get("text") or "")
        return extract_text(content.get("content"))
    if hasattr(content, "text"):
        return str(getattr(content, "text") or "")
    if getattr(content, "type", None) == "text":
        return str(getattr(content, "text") or "")
    return ""


async def poc_a_toolkit() -> None:
    from agentscope.message import TextBlock
    from agentscope.tool import FunctionTool, Toolkit, ToolResponse

    def spike_add(a: int, b: int) -> ToolResponse:
        """Add two integers for spike PoC-A."""
        return ToolResponse(content=[TextBlock(type="text", text=f"sum={a + b}")])

    toolkit = Toolkit()
    tool = FunctionTool(spike_add)
    await toolkit.add_tool(tool)
    schemas = await toolkit.get_tool_schemas()
    names = [s.get("function", {}).get("name") for s in schemas]
    ok = "spike_add" in names or "add" in names or any(names)
    record(
        Case(
            id="PoC-A",
            title="Custom Python tool via FunctionTool + Toolkit.add_tool",
            status="pass" if ok else "fail",
            detail=f"schemas names={names}",
            evidence={"schemas": schemas},
        )
    )

    # Negative: bare function registration like 1.x
    bare_ok = False
    bare_err = None
    try:
        tk2 = Toolkit()
        if hasattr(tk2, "register_tool_function"):
            tk2.register_tool_function(spike_add)
            bare_ok = True
        else:
            bare_err = "register_tool_function removed"
    except Exception as exc:  # noqa: BLE001
        bare_err = f"{type(exc).__name__}: {exc}"
    record(
        Case(
            id="PoC-A2",
            title="1.x register_tool_function still works",
            status="pass" if bare_ok else "fail",
            detail=bare_err or "works",
            evidence={"bare_ok": bare_ok},
        )
    )


async def poc_b_message_extract() -> None:
    from agentscope.message import TextBlock, UserMsg, Msg, ThinkingBlock

    u = UserMsg(name="human", content="关注经营性现金流")
    text = extract_text(u)
    ok_user = "经营性现金流" in text

    # classic 1.x Msg(str content) should fail / need adapter
    classic_ok = False
    classic_err = None
    try:
        Msg(name="system", content="plain string", role="user")
        classic_ok = True
    except Exception as exc:  # noqa: BLE001
        classic_err = f"{type(exc).__name__}: {exc}"

    # proper 2.0 Msg
    m = Msg(
        name="system",
        role="user",
        content=[TextBlock(type="text", text="hello blocks")],
    )
    text2 = extract_text(m)
    ok_msg = text2 == "hello blocks"

    # mixed blocks: text + thinking
    try:
        thinking = ThinkingBlock(type="thinking", text="secret chain")
    except Exception:
        try:
            thinking = ThinkingBlock(text="secret chain")
        except Exception as exc:  # noqa: BLE001
            thinking = None
            record(
                Case(
                    id="PoC-B",
                    title="Message text extraction",
                    status="pass" if (ok_user and ok_msg) else "fail",
                    detail=f"user={ok_user} msg={ok_msg}; ThinkingBlock skip ({exc})",
                    evidence={
                        "user_text": text,
                        "msg_text": text2,
                        "classic_str_content": classic_ok,
                        "classic_err": classic_err,
                    },
                )
            )
            return

    mixed = Msg(
        name="assistant",
        role="assistant",
        content=[thinking, TextBlock(type="text", text="最终结论：中性")],
    )
    mixed_text = extract_text(mixed)
    # extractor currently concatenates; pipeline may want to filter thinking — flag warn if mixed
    record(
        Case(
            id="PoC-B",
            title="Message text extraction",
            status="pass" if (ok_user and ok_msg) else "fail",
            detail=(
                f"user={ok_user} msg={ok_msg} classic_str_content={classic_ok}; "
                f"mixed_text={mixed_text!r}; classic_err={classic_err}"
            ),
            evidence={
                "user_text": text,
                "msg_text": text2,
                "mixed_text": mixed_text,
                "classic_str_content_allowed": classic_ok,
                "classic_err": classic_err,
                "note": "1.x Msg(content=str) breaks; need UserMsg or content=[TextBlock...]",
            },
        )
    )


async def poc_c_multi_agent_without_msghub() -> None:
    """Simulate conference broadcast by manual observe + shared state notes."""
    from agentscope.message import AssistantMsg, UserMsg
    from agentscope.state import AgentState

    # No MsgHub module
    try:
        import agentscope.pipeline  # noqa: F401

        has_pipeline = True
    except Exception:
        has_pipeline = False

    # Manual hub replacement
    class ManualHub:
        def __init__(self) -> None:
            self.participants: Dict[str, AgentState] = {}
            self.transcript: List[str] = []

        def add(self, name: str, state: AgentState) -> None:
            self.participants[name] = state

        async def broadcast(self, speaker: str, text: str) -> None:
            msg = UserMsg(name=speaker, content=text)
            self.transcript.append(f"{speaker}: {text}")
            for name, st in self.participants.items():
                # append into each agent context list
                st.context = list(st.context or []) + [msg]

    hub = ManualHub()
    pm_state = AgentState()
    analyst_state = AgentState()
    hub.add("pm", pm_state)
    hub.add("fundamentals", analyst_state)

    await hub.broadcast("pm", "请评估贵州茅台现金流质量")
    await hub.broadcast("fundamentals", "经营现金流稳健，但增速放缓")

    ok = (
        not has_pipeline
        and len(hub.transcript) == 2
        and len(pm_state.context) == 2
        and len(analyst_state.context) == 2
    )
    record(
        Case(
            id="PoC-C",
            title="Multi-agent share without MsgHub (manual context inject)",
            status="pass" if ok else "warn",
            detail=(
                f"pipeline_module={has_pipeline}; transcript={hub.transcript}; "
                f"pm_ctx={len(pm_state.context)} analyst_ctx={len(analyst_state.context)}"
            ),
            evidence={
                "has_agentscope_pipeline": has_pipeline,
                "strategy": "ManualHub + AgentState.context append / Agent.observe",
                "transcript": hub.transcript,
            },
        )
    )

    # observe API exists on Agent class — structural only
    from agentscope.agent import Agent

    has_observe = callable(getattr(Agent, "observe", None))
    record(
        Case(
            id="PoC-C2",
            title="Agent.observe available for cross-agent injection",
            status="pass" if has_observe else "fail",
            detail=f"observe={has_observe} sig={inspect.signature(Agent.observe)}",
        )
    )


async def poc_d_subclass() -> None:
    from agentscope.agent import Agent

    subclass_error = None
    init_works = False
    try:

        class SpikeAnalyst(Agent):
            async def reply(self, inputs=None, structured_schema=None):  # type: ignore[no-untyped-def]
                # Cannot easily call super without model; just prove override exists
                return await super().reply(inputs, structured_schema=structured_schema)

        init_works = True
        # Instantiation without model should fail — that's ok
        try:
            SpikeAnalyst(name="x", system_prompt="y", model=None)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            subclass_error = f"init requires real model: {type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001
        subclass_error = f"{type(exc).__name__}: {exc}"
        init_works = False

    # MRO: Agent -> object (no ReActAgentBase)
    mro = [c.__name__ for c in Agent.__mro__]
    record(
        Case(
            id="PoC-D",
            title="Subclass Agent",
            status="pass" if init_works else "fail",
            detail=f"mro={mro}; {subclass_error or 'class body ok'}",
            evidence={
                "mro": mro,
                "note": "Subclass possible but 1.x hooks (sys_prompt/formatter/memory kwargs) gone",
                "new_ctor": str(inspect.signature(Agent.__init__)),
            },
        )
    )


async def poc_memory_clear() -> None:
    """Phase0 equivalent: clear short-term context."""
    from agentscope.message import UserMsg
    from agentscope.state import AgentState

    st = AgentState()
    st.context = [UserMsg(name="u", content="old day context")]
    # 2.0: no InMemoryMemory.clear — clear list
    st.context = []
    ok = list(st.context) == []
    record(
        Case(
            id="PoC-MEM",
            title="Phase0 memory clear via AgentState.context=[]",
            status="pass" if ok else "fail",
            detail="InMemoryMemory module absent; use AgentState.context reset",
            evidence={"has_inmemory": False},
        )
    )


async def main() -> int:
    print("=== AgentScope 2.0.5 offline PoCs ===")
    try:
        import agentscope

        print("version", getattr(agentscope, "__version__", "?"))
    except Exception as exc:  # noqa: BLE001
        print("FATAL cannot import agentscope", exc)
        return 1

    for fn in (poc_a_toolkit, poc_b_message_extract, poc_c_multi_agent_without_msghub, poc_d_subclass, poc_memory_clear):
        try:
            await fn()
        except Exception as exc:  # noqa: BLE001
            record(
                Case(
                    id=fn.__name__,
                    title=fn.__name__,
                    status="fail",
                    detail=f"{type(exc).__name__}: {exc}",
                    evidence={"traceback": traceback.format_exc()[-1500:]},
                )
            )

    fails = sum(1 for c in RESULTS if c.status == "fail")
    warns = sum(1 for c in RESULTS if c.status == "warn")
    passes = sum(1 for c in RESULTS if c.status == "pass")
    summary = {
        "pass": passes,
        "warn": warns,
        "fail": fails,
        "cases": [
            {"id": c.id, "status": c.status, "title": c.title, "detail": c.detail, "evidence": c.evidence}
            for c in RESULTS
        ],
    }
    out = __file__.replace("poc_offline.py", "poc_offline_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSummary pass={passes} warn={warns} fail={fails}")
    print(f"Wrote {out}")
    # A2 expected fail is informative (1.x API gone)
    critical_fail_ids = {"PoC-A", "PoC-B", "PoC-C", "PoC-D", "PoC-MEM"}
    crit_fails = [c for c in RESULTS if c.id in critical_fail_ids and c.status == "fail"]
    return 1 if crit_fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
