# Analysis Timing Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add timestamped access logs and session-correlated timing events that identify whether an AI analysis is slow in a pipeline phase, Agent reply, or tool call.

**Architecture:** `backend.server` supplies the Uvicorn access-log configuration and logs whole-session elapsed time. `RatingPipeline` measures each phase and `agent.reply()` invocation; its existing tool-progress scope measures individual tool calls. Every timing line uses the dedicated `analysis_timing` logger and carries the session ID without logging prompts, response content, arguments, or secrets.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, AgentScope, standard-library `logging` and `time.perf_counter`, `unittest`.

---

## File Structure

- Modify: `backend/server.py` — configure timestamped Uvicorn access logs and log the lifetime of each WebSocket analysis session.
- Modify: `backend/core/pipeline.py` — time pipeline phases, Agent replies, and existing tool-progress events.
- Modify: `tests/test_server_logging.py` — assert the custom Uvicorn formatter keeps timestamps.
- Modify: `tests/test_pipeline_realtime_lifecycle.py` — assert lifecycle timing events are emitted without changing WebSocket progress behavior.
- Modify: `tests/test_server_analysis_cancellation.py` — assert completed and cancelled analysis sessions emit duration events.
- Modify: `README.md` — document the timing log format and Baota investigation command.

### Task 1: Timestamp Uvicorn Access Logs

**Files:**
- Modify: `backend/server.py:8-55,337-349`
- Modify: `tests/test_server_logging.py:1-19`

- [ ] **Step 1: Write the failing test**

```python
from backend.server import UVICORN_LOG_CONFIG


class TestServerLogging(unittest.TestCase):
    def test_uvicorn_access_log_format_includes_timestamp_with_milliseconds(self):
        formatter = UVICORN_LOG_CONFIG["formatters"]["access"]

        self.assertIn("%(asctime)s", formatter["fmt"])
        self.assertIn("%(msecs)03d", formatter["fmt"])
        self.assertEqual("%Y-%m-%d %H:%M:%S", formatter["datefmt"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m unittest tests.test_server_logging.TestServerLogging.test_uvicorn_access_log_format_includes_timestamp_with_milliseconds -v`

Expected: FAIL because `UVICORN_LOG_CONFIG` is not exported by `backend.server`.

- [ ] **Step 3: Add the application-owned Uvicorn configuration**

```python
from copy import deepcopy

from uvicorn.config import LOGGING_CONFIG

LOG_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

UVICORN_LOG_CONFIG = deepcopy(LOGGING_CONFIG)
for formatter_name in ("default", "access"):
    UVICORN_LOG_CONFIG["formatters"][formatter_name]["fmt"] = LOG_FORMAT
    UVICORN_LOG_CONFIG["formatters"][formatter_name]["datefmt"] = LOG_DATE_FORMAT
    UVICORN_LOG_CONFIG["formatters"][formatter_name]["use_colors"] = False
```

Use `LOG_FORMAT` and `LOG_DATE_FORMAT` in `logging.basicConfig`, then pass `log_config=UVICORN_LOG_CONFIG` to `uvicorn.run`. Keep the existing host, port, access-log behavior, and standard stream redirection unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_server_logging.TestServerLogging.test_uvicorn_access_log_format_includes_timestamp_with_milliseconds -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py tests/test_server_logging.py
git commit -m "feat: timestamp uvicorn access logs"
```

### Task 2: Record Agent, Tool, and Phase Durations

**Files:**
- Modify: `backend/core/pipeline.py:1-223,261-376`
- Modify: `tests/test_pipeline_realtime_lifecycle.py:1-123`

- [ ] **Step 1: Write the failing test**

Extend the successful lifecycle test to capture the dedicated logger while keeping its existing WebSocket assertions:

```python
with self.assertLogs("analysis_timing", level="INFO") as captured:
    result = await pipeline._reply_with_lifecycle(
        FakeAgent(),
        Msg(name="system", content="分析", role="user"),
        phase="analysis",
    )

self.assertEqual("分析完成", result.content)
self.assertTrue(any("event=tool_call" in line and "tool=analyze_profitability" in line for line in captured.output))
self.assertTrue(any("event=agent_reply" in line and "agent=fundamentals_analyst" in line for line in captured.output))
self.assertTrue(all("duration_ms=" in line for line in captured.output))
```

Add a second test whose `reply()` raises `RuntimeError("model unavailable")` and assert it emits `event=agent_reply`, `status=failed`, and `error_type=RuntimeError` before retaining the existing failure behavior.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m unittest tests.test_pipeline_realtime_lifecycle -v`

Expected: FAIL because no `analysis_timing` records exist.

- [ ] **Step 3: Implement focused pipeline telemetry**

Add a module-level `timing_logger = logging.getLogger("analysis_timing")` and a helper that resolves `self._session_id`, then falls back to `state_sync._session_id`, then `"unknown"` for isolated tests.

Add a timed phase helper:

```python
async def _run_timed_phase(
    self,
    phase: str,
    operation: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    started_at = time.perf_counter()
    try:
        result = await operation(*args, **kwargs)
    except asyncio.CancelledError:
        timing_logger.info(
            "event=phase_completed session=%s phase=%s status=cancelled duration_ms=%d",
            self._timing_session_id(), phase,
            (time.perf_counter() - started_at) * 1000,
        )
        raise
    except Exception as exc:
        timing_logger.info(
            "event=phase_completed session=%s phase=%s status=failed error_type=%s duration_ms=%d",
            self._timing_session_id(), phase, type(exc).__name__,
            (time.perf_counter() - started_at) * 1000,
        )
        raise
    timing_logger.info(
        "event=phase_completed session=%s phase=%s status=completed duration_ms=%d",
        self._timing_session_id(), phase,
        (time.perf_counter() - started_at) * 1000,
    )
    return result
```

Wrap the Phase 1, 2, 3, 4, 5, and 7 calls in `run_cycle` with this helper. In `_reply_with_lifecycle`, use `time.perf_counter()` around the existing retry wrapper and emit `event=agent_reply` for completed, failed, and cancelled responses. In `_on_tool_progress`, maintain start timestamps by tool name and emit `event=tool_call` on `completed` or `failed`; preserve the existing `state_sync` callbacks and progress percentages.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m unittest tests.test_pipeline_realtime_lifecycle -v`

Expected: PASS, including the existing cancellation and WebSocket lifecycle assertions.

- [ ] **Step 5: Commit**

```bash
git add backend/core/pipeline.py tests/test_pipeline_realtime_lifecycle.py
git commit -m "feat: trace pipeline and tool durations"
```

### Task 3: Record Whole-Session Duration

**Files:**
- Modify: `backend/server.py:119-232`
- Modify: `tests/test_server_analysis_cancellation.py:1-116`

- [ ] **Step 1: Write the failing tests**

Add a completed-session test that wraps `run_analysis()` in `self.assertLogs("analysis_timing", level="INFO")` and checks for both `event=analysis_started session=session-completed` and `event=analysis_completed session=session-completed status=completed duration_ms=`.

Extend the existing cancellation test similarly and assert `event=analysis_completed session=session-cancelled status=cancelled duration_ms=` appears before `asyncio.CancelledError` is re-raised.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m unittest tests.test_server_analysis_cancellation -v`

Expected: FAIL because `run_analysis` does not emit `analysis_timing` records.

- [ ] **Step 3: Implement session timing**

At the beginning of `run_analysis`, store `started_at = time.perf_counter()` and write:

```python
timing_logger.info(
    "event=analysis_started session=%s tickers=%s date=%s",
    session_id, ",".join(tickers), date,
)
```

In the completed, failed, and cancelled paths, emit exactly one terminal `event=analysis_completed` line with `session`, `status`, `duration_ms`, and `error_type` for failures. Preserve the existing session persistence and exception propagation behavior.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m unittest tests.test_server_analysis_cancellation -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py tests/test_server_analysis_cancellation.py
git commit -m "feat: log analysis session durations"
```

### Task 4: Document Baota Investigation Workflow

**Files:**
- Modify: `README.md:260-317`

- [ ] **Step 1: Add the operational documentation**

Add an “分析耗时定位” subsection after the backend startup instructions. State that the existing Baota command remains unchanged:

```bash
/root/.local/bin/uv run python backend/server.py > app.log 2>&1
```

Document these investigation commands, replacing the sample session ID with the value from the WebSocket request:

```bash
grep 'session=bba6b336-2782-45c2-bfb2-49de2518e7f7' app.log
grep 'event=tool_call.*tool=analyze_profitability' app.log
```

Explain that `agent_reply` includes model and tool latency, while `tool_call` isolates tool latency; do not add prompt or response-body logging.

- [ ] **Step 2: Verify documentation and the full test suite**

Run: `git diff --check && uv run python -m unittest discover -s tests -p "test_*.py" -v`

Expected: no whitespace errors and all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: explain analysis timing logs"
```
