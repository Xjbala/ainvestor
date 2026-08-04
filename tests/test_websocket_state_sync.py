# -*- coding: utf-8 -*-
"""WebSocket 状态同步器单元测试。"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.websocket.message import EventType
from backend.websocket.state_sync import WebSocketStateSync


class TestWebSocketStateSync(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
