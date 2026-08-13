# -*- coding: utf-8 -*-
"""Startup failure handling for the standalone WebSocket gateway."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.server import app, lifespan


class TestServerLifespan(unittest.TestCase):
    def test_websocket_bind_failure_aborts_application_startup(self):
        asyncio.run(self._test_websocket_bind_failure_aborts_application_startup())

    async def _test_websocket_bind_failure_aborts_application_startup(self):
        gateway = MagicMock()
        gateway.bind = AsyncMock(
            side_effect=OSError(48, "address already in use"),
        )

        with (
            patch("backend.server.get_database", new_callable=AsyncMock),
            patch("backend.server.close_database", new_callable=AsyncMock),
            patch("backend.server.WebSocketGateway", return_value=gateway),
        ):
            with self.assertRaisesRegex(OSError, "address already in use"):
                async with lifespan(app):
                    self.fail("Lifespan must not yield after WebSocket bind failure")

        gateway.bind.assert_awaited_once_with()

    def test_websocket_gateway_is_stopped_and_waited_for_on_shutdown(self):
        asyncio.run(
            self._test_websocket_gateway_is_stopped_and_waited_for_on_shutdown(),
        )

    async def _test_websocket_gateway_is_stopped_and_waited_for_on_shutdown(self):
        close_signal = asyncio.Event()
        gateway = MagicMock()
        gateway.bind = AsyncMock()
        gateway.stop = AsyncMock(side_effect=close_signal.set)
        gateway.wait_closed = AsyncMock(side_effect=close_signal.wait)

        with (
            patch("backend.server.get_database", new_callable=AsyncMock),
            patch("backend.server.close_database", new_callable=AsyncMock) as close_database,
            patch("backend.server.WebSocketGateway", return_value=gateway),
        ):
            async with lifespan(app):
                pass

        gateway.bind.assert_awaited_once_with()
        gateway.stop.assert_awaited_once_with()
        gateway.wait_closed.assert_awaited_once_with()
        close_database.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
