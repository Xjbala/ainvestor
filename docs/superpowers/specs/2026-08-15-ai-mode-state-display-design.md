# AI Mode State Display Design

## Goal

Make AI analysis timestamps consistent, make every agent card reach a terminal display state when a successful session ends, and use the report area only while a report is being prepared or explicitly opened.

## Time Model

Every WebSocket event will carry an RFC 3339 UTC timestamp with an explicit
`+00:00` offset. The frontend will retain that event timestamp in each agent
state and use it for the card, activity feed, and stock-header update time.
No component may create a replacement current timestamp while rendering an
analysis event.

## Agent Completion Model

On `session_end` with `completed` status, the analysis store will turn any
remaining `analyzing` agent into `complete` with progress `100`. This covers a
dropped individual completion event without changing failed or cancelled
sessions. A completed card with no extractable summary will show a concise
completion message instead of an in-progress message.

## Report Area

The lower, full-width report area is conditional:

- While `analysisStatus === 'running'`, it renders an investment-report
  preparation placeholder.
- After completion, it is hidden until `showReport && report` is true.
- When opened, it renders the existing full report and its close control.

The compact right-side decision footer remains the control surface for opening
the report. The report area is a grid child so it occupies the intended
full-width row rather than an unrelated page region.

## Verification

Regression coverage will prove that generated WebSocket timestamps are
timezone-aware, a successful session finalizes active agents, agent cards use
their supplied event timestamp, and the report-area visibility condition
matches the three states above. The frontend build, focused Python tests, and
local browser checks will verify integration.
