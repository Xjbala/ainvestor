"""Helpers for index-friendly financial data queries."""

from datetime import date


def calendar_year_bounds(year: int) -> tuple[date, date]:
    """Return inclusive lower and exclusive upper bounds for a calendar year."""
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("year must be an integer")

    return date(year, 1, 1), date(year + 1, 1, 1)
