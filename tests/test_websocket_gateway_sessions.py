# -*- coding: utf-8 -*-
"""WebSocket 网关会话隔离和生命周期测试。"""

import asyncio
import json
import os
import sys
import types
import unittest

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
    def __init__(self, remote_address=None):
        self.remote_address = remote_address
        self.sent = []

    async def send(self, message):
        self.sent.append(json.loads(message))


class TestWebSocketGatewaySessions(unittest.TestCase):
    def test_each_start_request_uses_its_own_sync_and_client(self):
        asyncio.run(self._test_each_start_request_uses_its_own_sync_and_client())

    async def _test_each_start_request_uses_its_own_sync_and_client(self):
        gateway = WebSocketGateway()
        gateway.set_analysis_handler(object())
        release = asyncio.Event()

        async def blocking_run_analysis(*args):
            await release.wait()

        gateway._run_analysis = blocking_run_analysis
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

    def test_immediate_stop_emits_cancelled_terminal_event(self):
        asyncio.run(self._test_immediate_stop_emits_cancelled_terminal_event())

    async def _test_immediate_stop_emits_cancelled_terminal_event(self):
        gateway = WebSocketGateway()
        handler_started = asyncio.Event()

        async def handler(tickers, date, session_id, session_sync):
            handler_started.set()

        gateway.set_analysis_handler(handler)
        client = FakeWebSocket()
        request = {
            "type": "command",
            "event": "start_analysis",
            "data": {"tickers": ["603137"], "date": "2026-08-11"},
        }

        await gateway._handle_start_analysis(client, request)
        session_id = gateway._client_sessions[client]
        await gateway._handle_stop_analysis(client, {"type": "command", "event": "stop_analysis"})

        self.assertFalse(handler_started.is_set())
        self.assertNotIn(session_id, gateway._current_tasks)
        terminal_events = [
            message for message in client.sent if message["event"] == "session_end"
        ]
        self.assertEqual(1, len(terminal_events))
        self.assertEqual("cancelled", terminal_events[0]["data"]["status"])

    def test_explicit_stop_cancels_task_and_emits_one_cancelled_terminal_event(self):
        asyncio.run(self._test_explicit_stop_cancels_task_and_emits_one_cancelled_terminal_event())

    async def _test_explicit_stop_cancels_task_and_emits_one_cancelled_terminal_event(self):
        gateway = WebSocketGateway()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def blocking_handler(tickers, date, session_id, session_sync):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        gateway.set_analysis_handler(blocking_handler)
        client = FakeWebSocket(("127.0.0.1", 54321))
        request = {
            "type": "command",
            "event": "start_analysis",
            "data": {"tickers": ["603137"], "date": "2026-08-11"},
        }

        await gateway._handle_start_analysis(client, request)
        await started.wait()
        session_id = gateway._client_sessions[client]

        await gateway._handle_stop_analysis(client, {"type": "command", "event": "stop_analysis"})

        self.assertTrue(cancelled.is_set())
        self.assertNotIn(session_id, gateway._current_tasks)
        self.assertNotIn(session_id, gateway._session_syncs)
        self.assertNotIn(session_id, gateway._session_metadata)
        terminal_events = [
            message for message in client.sent if message["event"] == "session_end"
        ]
        self.assertEqual(1, len(terminal_events))
        self.assertEqual("cancelled", terminal_events[0]["data"]["status"])
        self.assertFalse(terminal_events[0]["data"]["success"])

    def test_resume_rebinds_disconnected_client_without_cancelling_task(self):
        asyncio.run(self._test_resume_rebinds_disconnected_client_without_cancelling_task())

    async def _test_resume_rebinds_disconnected_client_without_cancelling_task(self):
        gateway = WebSocketGateway()
        started = asyncio.Event()
        release = asyncio.Event()
        cancelled = asyncio.Event()

        async def blocking_handler(tickers, date, session_id, session_sync):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        gateway.set_analysis_handler(blocking_handler)
        original_client = FakeWebSocket()
        replacement_client = FakeWebSocket()
        request = {
            "type": "command",
            "event": "start_analysis",
            "data": {"tickers": ["603137"], "date": "2026-08-11"},
        }

        await gateway._handle_start_analysis(original_client, request)
        await started.wait()
        session_id = gateway._client_sessions[original_client]
        session_sync = gateway._session_syncs[session_id]

        await session_sync.unregister(original_client)
        gateway._client_sessions.pop(original_client)
        self.assertFalse(gateway._current_tasks[session_id].done())
        self.assertFalse(cancelled.is_set())

        await gateway._handle_resume_analysis(
            replacement_client,
            {
                "type": "command",
                "event": "resume_analysis",
                "data": {"session_id": session_id},
            },
        )

        self.assertEqual(session_id, gateway._client_sessions[replacement_client])
        self.assertIn(replacement_client, session_sync._clients)
        self.assertEqual("session_start", replacement_client.sent[-1]["event"])
        self.assertEqual(session_id, replacement_client.sent[-1]["session_id"])

        release.set()
        await asyncio.gather(*gateway._current_tasks.values())
        self.assertFalse(cancelled.is_set())

    def test_missing_handler_cleans_session_registrations(self):
        asyncio.run(self._test_missing_handler_cleans_session_registrations())

    async def _test_missing_handler_cleans_session_registrations(self):
        gateway = WebSocketGateway()
        client = FakeWebSocket()
        request = {
            "type": "command",
            "event": "start_analysis",
            "data": {"tickers": ["603137"], "date": "2026-08-11"},
        }

        await gateway._handle_start_analysis(client, request)

        self.assertEqual({}, gateway._current_tasks)
        self.assertEqual({}, gateway._session_syncs)
        self.assertEqual({}, gateway._session_metadata)
        self.assertEqual({}, gateway._client_sessions)
        self.assertEqual("error", client.sent[-1]["event"])


if __name__ == "__main__":
    unittest.main()
