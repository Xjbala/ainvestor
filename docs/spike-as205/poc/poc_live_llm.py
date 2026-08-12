#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optional live LLM PoC for AgentScope 2.0.5.

Loads repo .env if present. Requires OPENAI_API_KEY (OpenAI-compatible OK).

  source .venv-as205-spike/bin/activate
  python docs/spike-as205/poc/poc_live_llm.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict


def load_dotenv() -> None:
    root = Path(__file__).resolve().parents[3]
    env_path = root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def extract_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if hasattr(obj, "content"):
        return extract_text(getattr(obj, "content"))
    if isinstance(obj, list):
        parts = []
        for item in obj:
            t = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
            if t in {"thinking", "tool_call", "tool_use"}:
                continue
            if hasattr(item, "text"):
                parts.append(str(item.text))
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            else:
                piece = extract_text(item)
                if piece:
                    parts.append(piece)
        return "\n".join(parts).strip()
    if hasattr(obj, "text"):
        return str(obj.text or "")
    return str(obj)


async def run() -> Dict[str, Any]:
    from agentscope.agent import Agent
    from agentscope.credential import OpenAICredential
    from agentscope.message import TextBlock, UserMsg
    from agentscope.model import OpenAIChatModel
    from agentscope.permission import (
        PermissionBehavior,
        PermissionContext,
        PermissionMode,
        PermissionRule,
    )
    from agentscope.state import AgentState
    from agentscope.tool import FunctionTool, Toolkit, ToolResponse

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY missing"}

    base_url = os.getenv("OPENAI_BASE_URL") or None
    model_name = os.getenv("MODEL_NAME") or "gpt-4o-mini"

    try:
        cred = OpenAICredential(api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"credential: {exc}"}

    client_kwargs = {}
    if base_url:
        client_kwargs["base_url"] = base_url

    model = OpenAIChatModel(
        credential=cred,
        model=model_name,
        stream=False,
        client_kwargs=client_kwargs or None,
    )

    def spike_add(a: int, b: int) -> ToolResponse:
        """Add two integers and return sum=N text."""
        return ToolResponse(content=[TextBlock(type="text", text=f"sum={a + b}")])

    toolkit = Toolkit()
    await toolkit.add_tool(FunctionTool(spike_add))

    # 2.0 defaults to permission ASK for custom tools; spike needs unattended run.
    state = AgentState(
        permission_context=PermissionContext(
            mode=PermissionMode.BYPASS,
            allow_rules={
                "spike_add": [
                    PermissionRule(
                        tool_name="spike_add",
                        rule_content=None,
                        behavior=PermissionBehavior.ALLOW,
                        source="spike",
                    )
                ]
            },
        )
    )

    agent = Agent(
        name="spike_live",
        system_prompt=(
            "You are a test agent. When asked to add numbers, you MUST call the "
            "spike_add tool. After the tool returns, reply with the numeric sum only."
        ),
        model=model,
        toolkit=toolkit,
        state=state,
    )

    user = UserMsg(
        name="tester",
        content="Use spike_add to compute 17+25. Final answer should contain 42.",
    )
    result = await asyncio.wait_for(agent.reply(user), timeout=120)
    text = extract_text(result)
    ok = "42" in text or "sum=42" in text
    return {
        "ok": ok,
        "model": model_name,
        "base_url": base_url,
        "text": text[:1000],
        "result_type": type(result).__name__,
        "result_role": getattr(result, "role", None),
    }


def main() -> int:
    load_dotenv()
    print("=== Live LLM PoC ===")
    try:
        out = asyncio.run(run())
    except Exception as exc:  # noqa: BLE001
        out = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-2000:],
        }
    path = Path(__file__).with_name("poc_live_report.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {path}")
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
