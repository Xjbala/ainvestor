# Financial Query Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every financial AgentScope tool's stock code as a six-character string and replace valuation `EXTRACT(YEAR...)` predicates with indexable annual date ranges.

**Architecture:** Continue using SQLAlchemy exclusively. A tool-layer normalizer converts LLM-supplied integers or strings before a service is called. A valuation helper returns half-open `date` boundaries; the five affected statements retain their existing sort order and `LIMIT 1` semantics.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async ORM, AgentScope, `unittest`, `unittest.mock`.

---

## File Structure

- Create: `backend/agents/tools/stock_code.py` — normalize LLM tool inputs to six-digit A-share code strings.
- Create: `backend/valuation/query_helpers.py` — generate validated annual date boundaries.
- Modify: `backend/agents/tools/fundamentals_tools.py` — normalize four fundamental tool inputs.
- Modify: `backend/agents/tools/valuation_tools.py` — normalize six valuation tool inputs.
- Modify: `backend/valuation/wacc.py`, `backend/valuation/dcf.py`, `backend/valuation/residual_income.py`, `backend/valuation/relative.py` — replace five `func.extract` conditions.
- Create: `tests/test_financial_query_normalization.py` — regression tests for helpers, all public tool boundaries, and query shape.

### Task 1: Add Pure Normalization and Date Helpers

**Files:**
- Create: `backend/agents/tools/stock_code.py`
- Create: `backend/valuation/query_helpers.py`
- Test: `tests/test_financial_query_normalization.py`

- [ ] **Step 1: Write the failing helper tests**

```python
def test_normalize_stock_code_pads_numeric_inputs(self):
    self.assertEqual("000001", normalize_stock_code(1))
    self.assertEqual("603137", normalize_stock_code(603137))
    self.assertEqual("000001", normalize_stock_code("000001"))

def test_normalize_stock_code_rejects_invalid_inputs(self):
    for value in (True, "60313", "600519.SH", "abc123", ""):
        with self.assertRaises(ValueError):
            normalize_stock_code(value)

def test_calendar_year_bounds_are_half_open(self):
    self.assertEqual(
        (date(2026, 1, 1), date(2027, 1, 1)),
        calendar_year_bounds(2026),
    )
```

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_financial_query_normalization -v`

Expected: `ModuleNotFoundError` because neither helper exists.

- [ ] **Step 3: Implement the minimal helpers**

```python
# backend/agents/tools/stock_code.py
def normalize_stock_code(stock_code: str | int) -> str:
    if isinstance(stock_code, bool):
        raise ValueError("stock_code must be a six-digit A-share code")
    if isinstance(stock_code, int):
        candidate = str(stock_code).zfill(6)
    elif isinstance(stock_code, str):
        candidate = stock_code.strip()
    else:
        raise ValueError("stock_code must be a string or integer")
    if not re.fullmatch(r"\d{6}", candidate):
        raise ValueError("stock_code must be a six-digit A-share code")
    return candidate

# backend/valuation/query_helpers.py
def calendar_year_bounds(year: int) -> tuple[date, date]:
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("year must be an integer")
    return date(year, 1, 1), date(year + 1, 1, 1)
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run python -m unittest tests.test_financial_query_normalization -v`

Expected: all helper tests pass.

- [ ] **Step 5: Commit**

Run: `git add backend/agents/tools/stock_code.py backend/valuation/query_helpers.py tests/test_financial_query_normalization.py && git commit -m "feat: normalize financial query inputs"`

### Task 2: Normalize Every Financial Tool Boundary

**Files:**
- Modify: `backend/agents/tools/fundamentals_tools.py:21-166`
- Modify: `backend/agents/tools/valuation_tools.py:29-214`
- Test: `tests/test_financial_query_normalization.py`

- [ ] **Step 1: Write failing public-tool tests**

Use a fake asynchronous session context manager and patch the service class at its source module. Its `analyze`, `valuate`, and `calculate` methods append their first positional argument or `stock_code` keyword argument to a shared list. Invoke each public tool with `stock_code=1`, then assert the recorded value is `"000001"`. Cover all ten tools:

```python
FINANCIAL_TOOL_CASES = (
    analyze_profitability, analyze_growth, analyze_solvency, analyze_operating,
    dcf_valuation_analysis, residual_income_valuation_analysis,
    relative_valuation_analysis, get_wacc_breakdown,
    comprehensive_valuation_analysis, sotp_valuation_analysis,
)
```

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_financial_query_normalization.TestFinancialToolBoundaries -v`

Expected: spies receive integer `1`, showing that tool input is not normalized.

- [ ] **Step 3: Implement normalization at each entry**

Import `normalize_stock_code` in both modules and add this before each `async_session_factory()` call:

```python
stock_code = normalize_stock_code(stock_code)
```

Apply it to the four fundamentals tools and six valuation tools named in the test case. Preserve each existing `try`/error response flow.

- [ ] **Step 4: Verify GREEN**

Run: `uv run python -m unittest tests.test_financial_query_normalization.TestFinancialToolBoundaries -v`

Expected: every service records `"000001"`; invalid codes return the existing localized error `ToolResponse` without opening a session.

- [ ] **Step 5: Commit**

Run: `git add backend/agents/tools/fundamentals_tools.py backend/agents/tools/valuation_tools.py tests/test_financial_query_normalization.py && git commit -m "fix: bind financial tool stock codes as strings"`

### Task 3: Make Valuation Year Lookups Indexable

**Files:**
- Modify: `backend/valuation/wacc.py:204-228`
- Modify: `backend/valuation/dcf.py:548-567`
- Modify: `backend/valuation/dcf.py:680-730`
- Modify: `backend/valuation/residual_income.py:605-656`
- Modify: `backend/valuation/relative.py:247-271`
- Test: `tests/test_financial_query_normalization.py`

- [ ] **Step 1: Write failing statement-shape tests**

Use a capturing asynchronous session and compile captured statements using the MySQL dialect. Exercise the affected lookup methods, then assert each statement uses two date bounds and has no `EXTRACT` text:

```python
compiled = str(statement.compile(dialect=mysql.dialect())).upper()
self.assertNotIn("EXTRACT", compiled)
self.assertIn("FINANCIAL_DATA.REPORT_DATE >=", compiled)
self.assertIn("FINANCIAL_DATA.REPORT_DATE <", compiled)
```

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_financial_query_normalization.TestValuationYearPredicates -v`

Expected: assertions fail because current statements contain `EXTRACT(year FROM financial_data.report_date)`.

- [ ] **Step 3: Replace the five non-sargable predicates**

Import `calendar_year_bounds` in each affected valuation module. For the local `year` or `base_year`, build the bounds once and replace:

```python
func.extract("year", FinancialData.report_date) == year
```

with:

```python
year_start, next_year_start = calendar_year_bounds(year)
FinancialData.report_date >= year_start,
FinancialData.report_date < next_year_start,
```

Use `base_year` in the two DCF and one residual-income locations. Keep annual report filtering, `ORDER BY report_date DESC`, and `LIMIT 1` exactly as they are.

- [ ] **Step 4: Verify GREEN**

Run: `uv run python -m unittest tests.test_financial_query_normalization.TestValuationYearPredicates -v`

Expected: all captured statements have range predicates and no `EXTRACT`.

- [ ] **Step 5: Commit**

Run: `git add backend/valuation/wacc.py backend/valuation/dcf.py backend/valuation/residual_income.py backend/valuation/relative.py tests/test_financial_query_normalization.py && git commit -m "fix: use indexed date ranges for valuation queries"`

### Task 4: Verify the Complete Change

**Files:**
- Verify: all files listed above.

- [ ] **Step 1: Search for missed predicates**

Run: `rg -n "func\\.extract\\(" backend/valuation --glob '*.py'`

Expected: no matches.

- [ ] **Step 2: Run focused tests**

Run: `uv run python -m unittest tests.test_financial_query_normalization tests.test_valuation_logic tests.test_valuation_v2 -v`

Expected: all focused tests pass.

- [ ] **Step 3: Run the entire unit suite**

Run: `uv run python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all tests pass.

- [ ] **Step 4: Check final diff**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and no uncommitted changes.
