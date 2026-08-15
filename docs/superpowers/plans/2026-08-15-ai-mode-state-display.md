# AI Mode State Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep AI mode timestamps and agent cards consistent and render the report area only while it is preparing or explicitly opened.

**Architecture:** The backend owns a timezone-aware event timestamp. The analysis store carries each agent's latest event timestamp and finalizes active agents when a successful session ends. The AI layout derives cards and report-area visibility from that canonical state rather than the browser clock.

**Tech Stack:** Python 3.12, unittest, React 19, TypeScript, Vite, Vitest.

---

### Task 1: Cover timezone-aware WebSocket events

**Files:**
- Modify: `tests/test_websocket_state_sync.py`
- Modify: `backend/websocket/message.py:8-94`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta
from backend.websocket.message import EventType, MessageType, WebSocketMessage

def test_message_timestamp_has_an_explicit_utc_offset(self):
    message = WebSocketMessage(
        type=MessageType.SYSTEM,
        event=EventType.PING,
    )

    timestamp = datetime.fromisoformat(message.timestamp)

    self.assertEqual(timedelta(0), timestamp.utcoffset())
```

- [ ] **Step 2: Run the focused test and confirm it fails because the timestamp is naive**

Run: `uv run python -m unittest tests.test_websocket_state_sync.TestWebSocketStateSync.test_message_timestamp_has_an_explicit_utc_offset`

Expected: `AssertionError` because `utcoffset()` is `None`.

- [ ] **Step 3: Emit UTC RFC 3339 timestamps**

```python
def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

timestamp: str = field(default_factory=_utc_timestamp)
```

Use `_utc_timestamp` for the `from_json` fallback as well.

- [ ] **Step 4: Run the focused test and confirm it passes**

Run: `uv run python -m unittest tests.test_websocket_state_sync.TestWebSocketStateSync.test_message_timestamp_has_an_explicit_utc_offset`

Expected: `OK`.

### Task 2: Establish frontend state-display regression tests

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/stores/analysisStore.test.ts`
- Create: `frontend/src/components/AIMode/AnalystCard.test.tsx`
- Create: `frontend/src/components/AIMode/reportVisibility.test.ts`

- [ ] **Step 1: Add Vitest as a development dependency and a `test` command**

```json
"scripts": {
  "test": "vitest run"
},
"devDependencies": {
  "vitest": "^4.1.10"
}
```

- [ ] **Step 2: Write failing frontend tests**

```ts
it('finalizes active agents when a session completes', () => {
  const next = analysisReducer(runningState, {
    type: 'SESSION_END',
    payload: { success: true, status: 'completed' },
  });
  expect(next.agents.fundamentals_analyst).toMatchObject({
    status: 'complete', progress: 100,
  });
});

it('renders the supplied event timestamp', () => {
  const markup = renderToStaticMarkup(<AnalystCard timestamp={eventTimestamp} {...props} />);
  expect(markup).toContain(`[${formatTimeShort(eventTimestamp)}]`);
});

it('shows the report area only while running or explicitly opened with a report', () => {
  expect(shouldShowReportArea('running', false, '')).toBe(true);
  expect(shouldShowReportArea('completed', false, 'report')).toBe(false);
  expect(shouldShowReportArea('completed', true, 'report')).toBe(true);
});
```

- [ ] **Step 3: Run the frontend tests and confirm they fail from missing exports or props**

Run: `npm test`

Expected: a module/export failure for the new report predicate and the unexported reducer, or a TypeScript failure because `AnalystCard` has no `timestamp` prop.

### Task 3: Preserve event times and settle successful sessions

**Files:**
- Modify: `frontend/src/types/message.ts:40-78`
- Modify: `frontend/src/stores/analysisStore.ts:37-218`
- Modify: `frontend/src/App.tsx:175-213`
- Modify: `frontend/src/components/AIMode/AnalystCard.tsx:5-81`

- [ ] **Step 1: Persist each event timestamp in `AgentState`**

Add `updatedAt?: string` to `AgentState`, carry the WebSocket message timestamp through start, progress, completion, and failure actions, and write it to the agent state.

- [ ] **Step 2: Finalize only active agents for completed sessions**

In the `SESSION_END` reducer branch, map `analyzing` agents to `complete` with progress `100` only when the terminal session status is `completed`.

- [ ] **Step 3: Render event timestamps instead of render-time clocks**

Add `timestamp?: string` to `AnalystCardProps`; render it when present. Pass `agent.updatedAt` from the layout and use the same field for analysis-output entries in `App.tsx`.

- [ ] **Step 4: Run the frontend unit suite and confirm it passes**

Run: `npm test`

Expected: all three regression tests pass.

### Task 4: Make the report carrier conditional

**Files:**
- Create: `frontend/src/components/AIMode/reportVisibility.ts`
- Modify: `frontend/src/components/AIMode/AIModeLayout.tsx:18-495`
- Modify: `frontend/src/components/AIMode/AIMode.css:1243-1570`

- [ ] **Step 1: Add the pure visibility predicate**

```ts
export function shouldShowReportArea(
  analysisStatus: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled' | undefined,
  showReport: boolean,
  report: string | undefined,
): boolean {
  return analysisStatus === 'running' || (showReport && Boolean(report?.trim()));
}
```

- [ ] **Step 2: Move the lower report section inside `.ai-mode-content`**

Render a full-width grid child only when `shouldShowReportArea(...)` returns true. For a running session show an investment-report preparation placeholder. For an explicitly opened report render the existing Markdown and close control. Keep the compact right-side `DecisionFooter` as the report-open control.

- [ ] **Step 3: Run frontend tests and the production build**

Run: `npm test && npm run build`

Expected: tests pass and Vite emits the production bundle without TypeScript errors.

### Task 5: Validate the integrated state flow

**Files:**
- Verify: `tests/test_websocket_state_sync.py`
- Verify: `frontend/src/components/AIMode/AIModeLayout.tsx`

- [ ] **Step 1: Run focused Python regression tests**

Run: `uv run python -m unittest tests.test_websocket_state_sync -v`

Expected: all tests pass.

- [ ] **Step 2: Inspect the local AI mode in the browser**

Verify that the default/closed completed state has no lower report carrier, a running state has the preparation placeholder, and the layout still renders the cards and right-side controls.

- [ ] **Step 3: Inspect the final diff for scope and whitespace**

Run: `git diff --check HEAD~1..HEAD && git status --short`

Expected: no whitespace errors; only the planned implementation and test files remain changed.
