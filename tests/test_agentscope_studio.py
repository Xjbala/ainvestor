# -*- coding: utf-8 -*-
"""AgentScope Studio optional observability tests."""

import asyncio
import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAgentScopeStudio(unittest.TestCase):
    def setUp(self):
        self._environment = patch.dict(os.environ, {}, clear=True)
        self._environment.start()
        import backend.observability.studio as studio

        self.studio = importlib.reload(studio)

    def tearDown(self):
        self._environment.stop()

    def test_disabled_configuration_does_not_initialize_exporter(self):
        asyncio.run(self._test_disabled_configuration_does_not_initialize_exporter())

    async def _test_disabled_configuration_does_not_initialize_exporter(self):
        with patch.object(self.studio, "_configure_tracing") as configure:
            self.assertFalse(await self.studio.initialize("session-1"))

        configure.assert_not_called()

    def test_enabled_configuration_registers_run_and_initializes_exporter(self):
        asyncio.run(
            self._test_enabled_configuration_registers_run_and_initializes_exporter(),
        )

    async def _test_enabled_configuration_registers_run_and_initializes_exporter(self):
        os.environ.update(
            {
                "AGENTSCOPE_STUDIO_ENABLED": "true",
                "AGENTSCOPE_STUDIO_ENDPOINT": "http://studio.internal:3000/",
                "AGENTSCOPE_STUDIO_PROJECT": "AI Investor",
            },
        )
        request = MagicMock()
        post = MagicMock(return_value=request)

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def post(self, *args, **kwargs):
                return post(*args, **kwargs)

        with (
            patch.object(self.studio.httpx, "AsyncClient", FakeAsyncClient),
            patch.object(self.studio, "_configure_tracing") as configure,
        ):
            self.assertTrue(await self.studio.initialize("session-1"))

        post.assert_called_once_with(
            "http://studio.internal:3000/trpc/registerRun",
            json={
                "id": "session-1",
                "project": "AI Investor",
                "name": "analysis-session-1",
                "timestamp": unittest.mock.ANY,
                "pid": unittest.mock.ANY,
                "status": "done",
                "run_dir": "",
            },
        )
        request.raise_for_status.assert_called_once_with()
        configure.assert_called_once_with("http://studio.internal:3000/v1/traces")
        self.assertEqual("session-1", self.studio._agentscope_config.run_id)
        self.assertTrue(self.studio._agentscope_config.trace_enabled)

    def test_studio_connection_error_does_not_raise(self):
        asyncio.run(self._test_studio_connection_error_does_not_raise())

    async def _test_studio_connection_error_does_not_raise(self):
        os.environ.update(
            {
                "AGENTSCOPE_STUDIO_ENABLED": "true",
                "AGENTSCOPE_STUDIO_ENDPOINT": "http://studio.internal:3000",
            },
        )

        class OfflineAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def post(self, *args, **kwargs):
                raise OSError("offline")

        with patch.object(self.studio.httpx, "AsyncClient", OfflineAsyncClient):
            self.assertFalse(await self.studio.initialize("session-1"))

    def test_missing_url_keeps_integration_disabled(self):
        asyncio.run(self._test_missing_url_keeps_integration_disabled())

    async def _test_missing_url_keeps_integration_disabled(self):
        os.environ["AGENTSCOPE_STUDIO_ENABLED"] = "true"

        with patch.object(self.studio, "_configure_tracing") as configure:
            self.assertFalse(await self.studio.initialize("session-1"))

        configure.assert_not_called()

    def test_same_origin_proxy_protects_every_studio_endpoint(self):
        nginx_config = Path(__file__).parents[1] / "deploy" / "agentscope-studio" / "nginx.conf"
        config = nginx_config.read_text()

        self.assertEqual(3, config.count('auth_basic "AgentScope Studio";'))
        self.assertEqual(
            3,
            config.count('auth_basic_user_file /etc/nginx/.htpasswd-agent-studio;'),
        )


if __name__ == "__main__":
    unittest.main()
