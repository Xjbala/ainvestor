# -*- coding: utf-8 -*-
"""Regression coverage for Uvicorn startup with redirected AgentScope output."""

import unittest

import uvicorn

from backend.server import app


class TestServerLogging(unittest.TestCase):
    def test_uvicorn_configures_logging_with_redirected_standard_streams(self):
        config = uvicorn.Config(app)

        self.assertIsNotNone(config)


if __name__ == "__main__":
    unittest.main()
