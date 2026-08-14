# Financial Query Normalization Design

## Goal

Ensure every AgentScope financial-analysis tool binds stock codes to MySQL as
six-character strings, and remove non-sargable year extraction predicates from
valuation queries that read `financial_data`.

## Evidence

- `financial_data.company_code` is `VARCHAR(10)`.
- AgentScope traces show the four fundamentals tools spend over 20 minutes in
  aggregate while local calls finish in milliseconds.
- A live MySQL process entry showed an estimate/WACC query running for more
  than two minutes with `EXTRACT(YEAR FROM report_date) = 2026`.
- `EXPLAIN` for that query chose a backward scan of `ix_financial_data_report_date`.
  The equivalent half-open date range used
  `ix_financial_data_coverage_lookup` and estimated one row.

## Design

### Stock code normalization

Add one small shared helper for financial AgentScope tools. It accepts a
string or integer, rejects booleans and invalid values, and returns a six-digit
string using zero-padding. Tool functions call it immediately before opening
their database session.

This keeps existing SQLAlchemy comparisons such as
`FinancialData.company_code == stock_code`. SQLAlchemy then binds a string
parameter instead of allowing an integer tool argument to reach a `VARCHAR`
comparison. No SQL is assembled manually.

The helper is applied to every fundamentals and valuation tool that accepts
`stock_code`. Existing REST API path parameters already arrive as strings and
are out of scope.

### Year predicates

Add a shared helper that builds a half-open annual date range:

```python
FinancialData.report_date >= date(year, 1, 1)
FinancialData.report_date < date(year + 1, 1, 1)
```

Replace each `func.extract("year", FinancialData.report_date) == year` in
WACC, DCF, residual-income, and relative-valuation services with this helper.
The query semantics remain "the latest available report in that calendar year"
because the existing descending `report_date` ordering and `LIMIT 1` remain
unchanged.

## Error Handling

Invalid stock codes return the existing tool error `ToolResponse`; valid
zero-padded codes preserve current behavior for inputs such as `"603137"` and
`"000001"`.

## Tests

- Unit-test normalizing numeric and string A-share codes, including leading
  zeroes and invalid values.
- Unit-test the annual range helper at ordinary and year-boundary inputs.
- Exercise all registered financial tool functions with a numeric stock code
  using lightweight service fakes, proving the normalized string reaches each
  service.
- Assert valuation statements compile to date-range predicates and do not
  contain `EXTRACT`.

## Scope Limits

This change does not introduce manual SQL, alter existing financial data, or
change MySQL schema. It addresses known non-sargable predicates and tool input
typing; a subsequent live slow-query capture remains necessary if the
fundamentals tools stay slow after deployment.
