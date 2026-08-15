# -*- coding: utf-8 -*-
"""WebSocket 状态同步器单元测试。"""

import asyncio
from datetime import datetime, timedelta
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.websocket.message import EventType, MessageType, WebSocketMessage
from backend.websocket.state_sync import WebSocketStateSync


class TestWebSocketStateSync(unittest.TestCase):
    def test_message_timestamp_has_an_explicit_utc_offset(self):
        message = WebSocketMessage(
            type=MessageType.SYSTEM,
            event=EventType.PING,
        )

        timestamp = datetime.fromisoformat(message.timestamp)

        self.assertEqual(timedelta(0), timestamp.utcoffset())

    def test_agent_complete_only_broadcasts(self):
        async def run_test():
            state_sync = WebSocketStateSync()
            state_sync.set_session_id("session-001")
            state_sync.broadcast = AsyncMock()

            with patch(
                "backend.websocket.state_sync.get_database",
                new_callable=AsyncMock,
            ) as get_database:
                await state_sync.on_agent_complete(
                    agent_id="portfolio_manager",
                    content='{"recommendations": []}',
                )

            get_database.assert_not_awaited()
            state_sync.broadcast.assert_awaited_once()
            message = state_sync.broadcast.await_args.args[0]
            self.assertEqual(message.event, EventType.ANALYSIS_COMPLETE)
            self.assertEqual(message.session_id, "session-001")
            self.assertEqual(message.data["agent_id"], "portfolio_manager")
            self.assertEqual(message.data["content"], '{"recommendations": []}')

        asyncio.run(run_test())

    def test_agent_failed_broadcasts_session_bound_event(self):
        async def run_test():
            state_sync = WebSocketStateSync(session_id="session-002")
            state_sync.broadcast = AsyncMock(return_value=1)

            await state_sync.on_agent_failed(
                agent_id="risk_manager",
                error="risk_assessment失败：RuntimeError: model unavailable",
                phase="risk_assessment",
            )

            message = state_sync.broadcast.await_args.args[0]
            self.assertEqual(message.event, EventType.ANALYSIS_FAILED)
            self.assertEqual(message.session_id, "session-002")
            self.assertEqual(message.data["agent_id"], "risk_manager")
            self.assertEqual(message.data["phase"], "risk_assessment")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
