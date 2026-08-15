# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Investor is a multi-agent value-investing analysis system for A-share stocks, built on AgentScope. The core philosophy is **data foundation first, agent collaboration second**: structured financial data is the reusable, verifiable asset that Agents reason over — Agents are an orchestration layer, not the source of truth. Don't bypass the data layer to invent logic in prompts.

When changing data/valuation/Agent behavior, CONTRIBUTING.md asks you to state: (1) where data comes from, (2) how it flows into analysis/valuation/Agent tools, (3) how missing data is surfaced rather than silently fabricated.

## Commands

### Setup & Run
```bash
uv sync                                  # Python deps (requires Python 3.12+, uv)
cd frontend && npm install               # Frontend deps (Node >= 18)

uv run python backend/server.py          # Backend: HTTP :8000 + WebSocket :8765
cd frontend && npm run dev               # Frontend: http://localhost:5173

uv run python main.py --tickers 600519,000858 --date 2026-01-28   # CLI mode
uv run python main.py --tickers 600519 --enable-memory            # with long-term memory
```

### Tests
```bash
# Backend: pure-logic unit tests, no DB/network/LLM
uv run python -m unittest discover -s tests -p "test_*.py" -v
uv run python -m unittest tests.test_valuation_v2 -v              # single module
uv run python -m unittest tests.test_valuation_v2.TestDCF.test_gordon_terminal -v  # single test

# Frontend
cd frontend && npm run test          # vitest run
cd frontend && npx vitest run src/stores/analysisStore.test.ts    # single file
cd frontend && npm run lint          # eslint
cd frontend && npm run build         # tsc -b && vite build (type-check gate)
```

### Reference Data Bootstrap (idempotent, required for fresh DB)
```bash
uv run python -m backend.scripts.bootstrap_reference_data --dry-run   # audit only
uv run python -m backend.scripts.bootstrap_reference_data              # writes
```
Creates standard accounts, data sources, exchanges, Sina subject mappings, and bank extended subjects in dependency order. Safe to re-run.

### Migration / repair scripts
`backend/scripts/` contains migration and repair scripts (e.g. `migrate_session_status_cancelled.py`, `repair_cancelled_sessions.py`, `init_financial_db.py`). Prefer extending existing scripts over ad-hoc SQL.

## Architecture

### Backend (`backend/`)

- **`core/pipeline.py` — `RatingPipeline`** is the heart of the analysis flow. Phases run in order:
  0. Clear short-term memory (prevents cross-day context contamination)
  1. Analyst evaluation (fundamentals + valuation analysts)
  2. Risk assessment
  3. Conference discussion (multi-round, bounded by `MAX_COMM_CYCLES`)
  4. Structured forecasts (direction + confidence)
  5. Investment recommendation (PM)
  6. Rating report generation
  7. Reflection & long-term memory (optional)

- **Agents** (`backend/agents/`): `AnalystAgent` extends `AgentScope.ReActAgent`. Four roles defined in `backend/config/constants.py`: fundamentals analyst, valuation analyst, risk manager, portfolio manager. Prompts are YAML in `backend/agents/prompts/` loaded by `PromptLoader` — do not hardcode role text in Python.
  - Agent tools live in `backend/agents/tools/` (`fundamentals_tools.py`, `valuation_tools.py`, `qualitative_tools.py`, `stock_code.py`). Tools must read the DB and compute; Agents should not "invent" numbers.

- **Valuation** (`backend/valuation/`): 6 methods — DCF, Residual Income, Relative, SOTP, WACC, and Triangulate (multi-method fusion weighted by industry profile). Bind stock codes as strings (see recent commits `c7a0a15`, `4b677ef`, `e87e964`) — indexed date ranges and string stock codes matter for query correctness.

- **Analysis** (`backend/analysis/`): four-dimensional financial analysis — solvency, profitability, growth, operating. Pure computation over repository-fetched data.

- **Persistence** (`backend/persistence/`): SQLAlchemy ORM models (`orm_models.py`) + repository pattern (`repository.py`). DB is async — `aiomysql` for MySQL (production), `aiosqlite` for dev fallback. `backend/persistence/compat.py` exposes `get_database` / `close_database` used by the server lifespan.

- **Crawler** (`backend/crawler/`): Sina financial statements, exchange listings, cninfo (年报 PDF) via MinerU, MD&A extraction, segment extractor, news sentiment. Outputs land in the structured DB and are reused by APIs and Agent tools.

- **WebSocket** (`backend/websocket/`): `gateway.py` accepts connections on `WS_PORT` (8765); `state_sync.py` (`WebSocketStateSync`) pushes pipeline progress to the frontend via callbacks (`on_agent_complete`, `on_conference_*`, etc.). WebSocket state is held in-process — **production must run a single worker** (no multi-worker Gunicorn).

- **API** (`backend/api/`): FastAPI routers for sessions, auth (JWT), users, crawler, analysis, valuation, companies, exchanges, segments. Swagger at `/docs`.

### Frontend (`frontend/`)

React 19 + TypeScript 5.9 + Vite 7 + Tailwind + Zustand. Key areas under `src/components/`:
- `AIMode/` — real-time multi-agent analysis view (subscribes to WebSocket)
- `ExpertMode/` — valuation lab (interactive DCF/RI/Relative/SOTP)
- `DataManagement/` — crawler task management
- `DataViewer/` — structured financial data browser (coverage, validation, annual reports, news)
- `Reports/`, `StockList/`, `Dashboard/`

State: `src/stores/` (Zustand) — `analysisStore.ts` (WebSocket-driven analysis state), `expertStore.ts`, `modeStore.ts`. WebSocket hook in `src/hooks/useWebSocket.ts`.

### Data Flow

```
Crawlers → structured DB (accounts, statements, MD&A, segments, news)
              ├─► 4-dim analysis API   ├─► Agent toolkit (reads real numbers)
              ├─► Valuation engines   └─► RatingPipeline conference
                                              └─► 5-level rating + report + frontend replay
```

Agent tools MUST read from the DB. Adding a new data field means updating crawler → persistence → repository → tool, not just prompting the Agent differently.

## Conventions

- **Python**: PEP8, type hints, async/await. Data access through repository/service layer — no business logic in prompts. Ruff is configured at repo level (`.ruff_cache` exists).
- **TypeScript/React**: functional components + hooks, strict mode. `npm run build` must pass after changes.
- **Commits**: `feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:` prefixes (see `CONTRIBUTING.md`).
- **Agent/data changes**: explain in the PR where data comes from, how it reaches Agent tools, and how missing data is reported. Prefer pure-logic tests for valuation/analysis changes.
- Stock codes are strings (e.g. `"600519"`, `"000001"`). Date ranges use indexed lookups — see `backend/valuation/*.py` and recent commits.
- When adding a new analyst/role: define type in `backend/config/constants.py`, add persona YAML in `backend/agents/prompts/analyst/personas.yaml`, add system prompt in `system.yaml`, optionally add tools.

## Key References

- Full design & features: `README.md` (Chinese). Detailed project context: `AGENTS.md`.
- Contribution flow & review focus: `CONTRIBUTING.md`.
- Valuation model notes: `docs/现金流折现估值模型-DCF.md`, `docs/剩余收益估值模型-RIM-N年后RE=0场景.md`.
- Production WebSocket proxy & AgentScope Studio setup: `docs/production-websocket-proxy.md`, `deploy/agentscope-studio/`.
- Plans under `docs/superpowers/plans/` track in-progress work.
- Swagger API docs: `http://localhost:8000/docs` when backend is running.
