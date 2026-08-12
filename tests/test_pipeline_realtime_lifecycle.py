# -*- coding: utf-8 -*-
"""Pipeline 实时 Agent 生命周期测试。"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentscope.message import Msg

from backend.agents.tool_progress import report_tool_progress
from backend.core.pipeline import RatingPipeline


class FakeSync:
    def __init__(self):
        self.events = []

    async def on_agent_start(self, agent_id, phase=""):
        self.events.append(("start", agent_id, phase))

    async def on_agent_progress(self, agent_id, progress, content="", phase=""):
        self.events.append(("progress", agent_id, progress, content, phase))

    async def on_agent_failed(self, agent_id, error, phase=""):
        self.events.append(("failed", agent_id, error, phase))


class FakeAgent:
    name = "fundamentals_analyst"

    async def reply(self, message):
        await report_tool_progress("analyze_profitability", "started")
        await report_tool_progress("analyze_profitability", "completed")
        return Msg(name=self.name, content="分析完成", role="assistant")


class FailingAgent:
    name = "risk_manager"

    async def reply(self, message):
        raise RuntimeError("model unavailable")


class CancelledAgent:
    name = "valuation_analyst"

    async def reply(self, message):
        raise asyncio.CancelledError()


class TestPipelineRealtimeLifecycle(unittest.TestCase):
    def test_reply_emits_start_tool_progress_and_completion_progress(self):
        asyncio.run(self._test_reply_emits_start_tool_progress_and_completion_progress())

    async def _test_reply_emits_start_tool_progress_and_completion_progress(self):
        sync = FakeSync()
        pipeline = RatingPipeline(
            analysts=[],
            risk_manager=None,
            portfolio_manager=None,
            state_sync=sync,
        )

        result = await pipeline._reply_with_lifecycle(
            FakeAgent(),
            Msg(name="system", content="分析", role="user"),
            phase="analysis",
        )

        self.assertEqual("分析完成", result.content)
        self.assertEqual(("start", "fundamentals_analyst", "analysis"), sync.events[0])
        self.assertEqual("progress", sync.events[1][0])
        self.assertIn("等待模型", sync.events[1][3])
        self.assertEqual(("progress", "fundamentals_analyst", 35, "正在调用工具：analyze_profitability", "analysis"), sync.events[2])
        self.assertEqual(("progress", "fundamentals_analyst", 65, "工具已返回，正在整理分析结果：analyze_profitability", "analysis"), sync.events[3])
        self.assertEqual(("progress", "fundamentals_analyst", 90, "模型回复已完成，正在生成结构化结果", "analysis"), sync.events[4])

    def test_reply_failure_emits_agent_failed(self):
        asyncio.run(self._test_reply_failure_emits_agent_failed())

    async def _test_reply_failure_emits_agent_failed(self):
        sync = FakeSync()
        pipeline = RatingPipeline(
            analysts=[],
            risk_manager=None,
            portfolio_manager=None,
            state_sync=sync,
        )

        with self.assertRaisesRegex(RuntimeError, "model unavailable"):
            await pipeline._reply_with_lifecycle(
                FailingAgent(),
                Msg(name="system", content="分析", role="user"),
                phase="risk_assessment",
            )

        self.assertEqual("failed", sync.events[-1][0])
        self.assertEqual("risk_manager", sync.events[-1][1])
        self.assertEqual("risk_assessment", sync.events[-1][3])

    def test_reply_cancellation_is_not_reported_as_agent_failure(self):
        asyncio.run(self._test_reply_cancellation_is_not_reported_as_agent_failure())

    async def _test_reply_cancellation_is_not_reported_as_agent_failure(self):
        sync = FakeSync()
        pipeline = RatingPipeline(
            analysts=[],
            risk_manager=None,
            portfolio_manager=None,
            state_sync=sync,
        )

        with self.assertRaises(asyncio.CancelledError):
            await pipeline._reply_with_lifecycle(
                CancelledAgent(),
                Msg(name="system", content="分析", role="user"),
                phase="analysis",
            )

        self.assertNotIn("failed", [event[0] for event in sync.events])


if __name__ == "__main__":
    unittest.main()
