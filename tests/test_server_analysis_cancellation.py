# -*- coding: utf-8 -*-
"""分析任务取消时的会话持久化测试。"""

import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.server import run_analysis


class FakePipeline:
    def __init__(self, *args, **kwargs):
        self._session_id = None

    async def run_cycle(self, *args, **kwargs):
        raise asyncio.CancelledError()


class FakeSessionSync:
    def set_session_id(self, session_id):
        self.session_id = session_id


class TestRunAnalysisCancellation(unittest.TestCase):
    def test_cancellation_persists_cancelled_status(self):
        asyncio.run(self._test_cancellation_persists_cancelled_status())

    async def _test_cancellation_persists_cancelled_status(self):
        database = MagicMock()
        database.create_session = AsyncMock(
            return_value=SimpleNamespace(id="session-cancelled"),
        )
        database.update_session_status = AsyncMock()

        with (
            patch("backend.server.get_database", new_callable=AsyncMock, return_value=database),
            patch("backend.agents.RiskAgent", MagicMock()),
            patch("backend.agents.PMAgent", MagicMock()),
            patch("backend.config.constants.ANALYST_TYPES", {}),
            patch("backend.config.env_config.get_env_int", return_value=2),
            patch("backend.llm.models.get_agent_model", return_value=MagicMock()),
            patch("backend.llm.models.get_agent_formatter", return_value=MagicMock()),
            patch("backend.core.pipeline.RatingPipeline", FakePipeline),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_analysis(
                    tickers=["603137"],
                    date="2026-08-11",
                    session_id="session-cancelled",
                    session_sync=FakeSessionSync(),
                )

        self.assertEqual(
            [
                (("session-cancelled", "running"),),
                (("session-cancelled", "cancelled"),),
            ],
            database.update_session_status.await_args_list,
        )

    def test_console_output_is_disabled_before_agent_construction(self):
        asyncio.run(self._test_console_output_is_disabled_before_agent_construction())

    async def _test_console_output_is_disabled_before_agent_construction(self):
        database = MagicMock()
        database.create_session = AsyncMock(
            return_value=SimpleNamespace(id="session-completed"),
        )
        database.update_session_status = AsyncMock()

        created_agents = []

        class CompletedPipeline:
            def __init__(self, analysts, risk_manager, portfolio_manager, **kwargs):
                self._session_id = None
                created_agents.extend([*analysts, risk_manager, portfolio_manager])

            async def run_cycle(self, *args, **kwargs):
                return {}

        class RecordingAgent:
            def __init__(self, *args, **kwargs):
                self.console_output_disabled = (
                    os.environ.get("AGENTSCOPE_DISABLE_CONSOLE_OUTPUT") == "true"
                )

        with (
            patch("backend.server.get_database", new_callable=AsyncMock, return_value=database),
            patch("backend.agents.AnalystAgent", RecordingAgent),
            patch("backend.agents.RiskAgent", RecordingAgent),
            patch("backend.agents.PMAgent", RecordingAgent),
            patch("backend.config.constants.ANALYST_TYPES", {"fundamentals_analyst": {}}),
            patch("backend.config.env_config.get_env_int", return_value=2),
            patch("backend.llm.models.get_agent_model", return_value=MagicMock()),
            patch("backend.llm.models.get_agent_formatter", return_value=MagicMock()),
            patch("backend.core.pipeline.RatingPipeline", CompletedPipeline),
        ):
            await run_analysis(
                tickers=["603137"],
                date="2026-08-11",
                session_id="session-completed",
                session_sync=FakeSessionSync(),
            )

        self.assertTrue(all(agent.console_output_disabled for agent in created_agents))


if __name__ == "__main__":
    unittest.main()
