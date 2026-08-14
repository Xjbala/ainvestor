# Analysis Timing Observability Design

## Goal

Make each AI analysis session diagnosable from the existing Baota `app.log` by adding timestamps to Uvicorn access logs and correlated duration events for the full analysis, pipeline phases, Agent replies, and tool calls.

## Scope

- Keep the existing `/root/.local/bin/uv run python backend/server.py > app.log 2>&1` startup command.
- Configure Uvicorn's access logger in the application so every access line includes local date and millisecond precision.
- Emit structured, single-line timing logs with the analysis session ID as the correlation key.
- Record only identifiers, event names, duration, and failure type. Do not log prompts, model responses, tool arguments, API keys, or financial content.

## Design

`backend.server` owns server-level configuration and total analysis duration. Its Uvicorn configuration overrides the default `uvicorn.access` formatter with an `asctime`-aware formatter while retaining the current stdout/stderr routing.

`RatingPipeline` owns pipeline-level telemetry. It records elapsed time for each business phase and for each `agent.reply()` call. The reply event captures total agent latency, including any model and tool work. The existing tool-progress callback records elapsed time from a tool's `started` event through `completed` or `failed`, enabling agent-level latency to be separated from direct tool latency.

All timing events use the `analysis_timing` logger and include `event=`, `session=`, `phase=`, `agent=`, `tool=`, and `duration_ms=` where applicable. Events are logged on success, failure, cancellation, and completion so an interrupted session remains diagnosable.

## Expected Output

```text
2026-08-14 10:00:00.123 | INFO | uvicorn.access | 203.0.113.1:0 - "GET /api/sessions?limit=5 HTTP/1.1" 200
2026-08-14 10:01:02.004 | INFO | analysis_timing | event=analysis_started session=... tickers=603137
2026-08-14 10:01:05.220 | INFO | analysis_timing | event=tool_call session=... phase=analysis agent=fundamentals_analyst tool=analyze_profitability status=completed duration_ms=287
2026-08-14 10:01:08.002 | INFO | analysis_timing | event=agent_reply session=... phase=analysis agent=fundamentals_analyst status=completed duration_ms=5998
2026-08-14 10:02:14.908 | INFO | analysis_timing | event=phase_completed session=... phase=conference duration_ms=66802
2026-08-14 10:02:22.101 | INFO | analysis_timing | event=analysis_completed session=... duration_ms=80100
```

## Error Handling

- A failed Agent reply emits an `agent_reply` event with `status=failed` and the exception type before preserving existing failure propagation.
- A cancelled analysis emits its elapsed duration before preserving cancellation propagation.
- Tool timing events report failure but do not alter the current tool-progress or WebSocket behavior.

## Verification

- Unit-test that Uvicorn's configured access formatter contains `%(asctime)s` and millisecond-capable date formatting.
- Unit-test that a successful Agent reply emits a correlated duration event.
- Unit-test that a tool lifecycle emits duration on completion and preserves the existing progress events.
- Run focused tests, then the full `unittest` suite.
