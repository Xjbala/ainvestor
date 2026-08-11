# -*- coding: utf-8 -*-
"""WebSocket 网关会话隔离测试。"""

import asyncio
import json
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock

try:
    import websockets  # noqa: F401
except ModuleNotFoundError:
    websockets_module = types.ModuleType("websockets")
    websockets_server_module = types.ModuleType("websockets.server")

    class ConnectionClosed(Exception):
        pass

    async def serve(*args, **kwargs):
        raise RuntimeError("WebSocket server is not started in this unit test")

    websockets_module.exceptions = types.SimpleNamespace(ConnectionClosed=ConnectionClosed)
    websockets_server_module.WebSocketServerProtocol = object
    websockets_server_module.serve = serve
    sys.modules["websockets"] = websockets_module
    sys.modules["websockets.server"] = websockets_server_module

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.websocket.gateway import WebSocketGateway


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(json.loads(message))


class TestWebSocketGatewaySessions(unittest.TestCase):
    def test_each_start_request_uses_its_own_sync_and_client(self):
        asyncio.run(self._test_each_start_request_uses_its_own_sync_and_client())

    async def _test_each_start_request_uses_its_own_sync_and_client(self):
        gateway = WebSocketGateway()
        gateway._run_analysis = AsyncMock()
        first_client = FakeWebSocket()
        second_client = FakeWebSocket()
        request = {
            "type": "command",
            "event": "start_analysis",
            "data": {"tickers": ["603137"], "date": "2026-08-11"},
        }

        await gateway._handle_start_analysis(first_client, request)
        await gateway._handle_start_analysis(second_client, request)

        self.assertEqual(2, len(gateway._session_syncs))
        self.assertEqual(2, len(gateway._client_sessions))
        first_session = gateway._client_sessions[first_client]
        second_session = gateway._client_sessions[second_client]
        self.assertNotEqual(first_session, second_session)
        self.assertIn(first_client, gateway._session_syncs[first_session]._clients)
        self.assertNotIn(second_client, gateway._session_syncs[first_session]._clients)
        self.assertIn(second_client, gateway._session_syncs[second_session]._clients)
        self.assertNotIn(first_client, gateway._session_syncs[second_session]._clients)

        for task in gateway._current_tasks.values():
            task.cancel()
        await asyncio.gather(*gateway._current_tasks.values(), return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
