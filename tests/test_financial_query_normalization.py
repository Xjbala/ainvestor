"""Tests for financial query input normalization helpers."""

from datetime import date
import unittest

from backend.agents.tools.stock_code import normalize_stock_code
from backend.valuation.query_helpers import calendar_year_bounds


class TestNormalizeStockCode(unittest.TestCase):
    def test_normalizes_integer_codes_to_six_digits(self) -> None:
        self.assertEqual(normalize_stock_code(1), "000001")
        self.assertEqual(normalize_stock_code(603137), "603137")

    def test_preserves_valid_six_digit_string(self) -> None:
        self.assertEqual(normalize_stock_code("000001"), "000001")

    def test_rejects_invalid_codes(self) -> None:
        invalid_codes = (True, "60313", "600519.SH", "abc123", "", 1.5)

        for code in invalid_codes:
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    normalize_stock_code(code)  # type: ignore[arg-type]


class TestCalendarYearBounds(unittest.TestCase):
    def test_returns_half_open_calendar_year_bounds(self) -> None:
        self.assertEqual(
            calendar_year_bounds(2026),
            (date(2026, 1, 1), date(2027, 1, 1)),
        )

    def test_rejects_non_integer_years(self) -> None:
        for year in (True, "2026"):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    calendar_year_bounds(year)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
