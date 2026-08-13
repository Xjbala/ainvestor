# -*- coding: utf-8 -*-
"""Studio tracing coverage for the command-line analysis entry point."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import main


class TestCliAgentScopeStudio(unittest.TestCase):
    def test_cli_rating_cycle_initializes_a_studio_run(self):
        asyncio.run(self._test_cli_rating_cycle_initializes_a_studio_run())

    async def _test_cli_rating_cycle_initializes_a_studio_run(self):
        class Pipeline:
            async def run_cycle(self, **kwargs):
                self.kwargs = kwargs
                return {"rating_report": "ok"}

        pipeline = Pipeline()
        with (
            patch("main.initialize_studio", new_callable=AsyncMock) as initialize_studio,
            patch("main.uuid4", return_value="cli-session-id"),
        ):
            result = await main.run_rating_cycle(
                pipeline=pipeline,
                tickers=["600519"],
                date="2026-08-13",
            )

        initialize_studio.assert_awaited_once_with("cli-session-id")
        self.assertEqual({"rating_report": "ok"}, result)


if __name__ == "__main__":
    unittest.main()
