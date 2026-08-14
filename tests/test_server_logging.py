# -*- coding: utf-8 -*-
"""Regression coverage for Uvicorn startup with redirected AgentScope output."""

import unittest

import uvicorn

from backend import server
from backend.server import app


class TestServerLogging(unittest.TestCase):
    def test_uvicorn_configures_logging_with_redirected_standard_streams(self):
        config = uvicorn.Config(app)

        self.assertIsNotNone(config)

    def test_uvicorn_access_log_format_includes_timestamp_with_milliseconds(self):
        formatter = server.UVICORN_LOG_CONFIG["formatters"]["access"]

        self.assertIn("%(asctime)s", formatter["fmt"])
        self.assertIn("%(msecs)03d", formatter["fmt"])
        self.assertEqual("%Y-%m-%d %H:%M:%S", formatter["datefmt"])

    def test_uvicorn_handlers_keep_original_standard_streams(self):
        handlers = server.UVICORN_LOG_CONFIG["handlers"]

        self.assertIs(handlers["access"]["stream"], server.ORIGINAL_STDOUT)
        self.assertIs(handlers["default"]["stream"], server.ORIGINAL_STDERR)


if __name__ == "__main__":
    unittest.main()
