# -*- coding: utf-8 -*-
"""Optional AgentScope Studio run registration and trace exporting."""

import logging
import os
from datetime import datetime, timezone
from threading import Lock

import httpx
from agentscope import _config as _agentscope_config

logger = logging.getLogger(__name__)

_tracing_lock = Lock()
_configured_trace_endpoint: str | None = None


def _enabled() -> bool:
    return os.getenv("AGENTSCOPE_STUDIO_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _studio_endpoint() -> str | None:
    """Return the Studio endpoint, accepting the previous URL name as a fallback."""
    value = os.getenv(
        "AGENTSCOPE_STUDIO_ENDPOINT",
        os.getenv("AGENTSCOPE_STUDIO_URL", ""),
    ).strip().rstrip("/")
    return value or None


def _configure_tracing(endpoint: str) -> None:
    """Configure the AgentScope OpenTelemetry exporter only once per endpoint."""
    global _configured_trace_endpoint

    with _tracing_lock:
        if _configured_trace_endpoint == endpoint:
            return

        from agentscope.tracing import setup_tracing

        setup_tracing(endpoint=endpoint)
        _configured_trace_endpoint = endpoint


async def initialize(session_id: str) -> bool:
    """Register an analysis session in Studio and enable its trace exporter.

    Studio is an optional diagnostics service. A missing or unavailable Studio
    must not prevent investment analysis from starting.
    """
    if not _enabled():
        return False

    studio_endpoint = _studio_endpoint()
    if not studio_endpoint:
        logger.warning(
            "AgentScope Studio is enabled but AGENTSCOPE_STUDIO_ENDPOINT is empty; "
            "observability is disabled for session=%s",
            session_id,
        )
        return False

    payload = {
        "id": session_id,
        "project": os.getenv("AGENTSCOPE_STUDIO_PROJECT", "AI Investor"),
        "name": f"analysis-{session_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "pid": os.getpid(),
        # This trace-only adapter does not install AgentScope's global Studio
        # hooks or Socket.IO lifecycle client, so Studio has no completion
        # callback. Registering as done avoids stale "running" runs.
        "status": "done",
        "run_dir": "",
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{studio_endpoint}/trpc/registerRun",
                json=payload,
            )
            response.raise_for_status()
        _configure_tracing(f"{studio_endpoint}/v1/traces")
    except Exception as exc:  # Studio must never block the analysis path.
        logger.warning(
            "AgentScope Studio initialization failed for session=%s: %s",
            session_id,
            exc,
        )
        return False

    _agentscope_config.run_id = session_id
    _agentscope_config.trace_enabled = True
    logger.info("AgentScope Studio enabled for analysis session=%s", session_id)
    return True
