# -*- coding: utf-8 -*-
"""Tests for cancelled-session repair script helpers."""

import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.scripts import repair_cancelled_sessions as repair


class TestRepairCancelledSessions(unittest.TestCase):
    def test_normalize_status_accepts_legacy_uppercase_values(self):
        self.assertEqual("running", repair.normalize_status("RUNNING"))
        self.assertEqual("cancelled", repair.normalize_status("Cancelled"))
        self.assertEqual("CANCELLED", repair.cancelled_status_for("RUNNING"))
        self.assertEqual("cancelled", repair.cancelled_status_for("running"))

    def test_main_disposes_engine_after_repair(self):
        asyncio.run(self._test_main_disposes_engine_after_repair())

    async def _test_main_disposes_engine_after_repair(self):
        fake_engine = SimpleNamespace(dispose=AsyncMock())
        with (
            patch.object(repair, "repair_sessions", new_callable=AsyncMock) as repair_sessions,
            patch.object(repair, "engine", fake_engine),
        ):
            await repair.main(["session-1"])

        repair_sessions.assert_awaited_once_with(["session-1"])
        fake_engine.dispose.assert_awaited_once()

    def test_main_disposes_engine_when_repair_fails(self):
        asyncio.run(self._test_main_disposes_engine_when_repair_fails())

    async def _test_main_disposes_engine_when_repair_fails(self):
        fake_engine = SimpleNamespace(dispose=AsyncMock())
        with (
            patch.object(
                repair,
                "repair_sessions",
                new_callable=AsyncMock,
                side_effect=RuntimeError("database unavailable"),
            ),
            patch.object(repair, "engine", fake_engine),
        ):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                await repair.main(["session-1"])

        fake_engine.dispose.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
