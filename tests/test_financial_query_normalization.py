"""Tests for financial query input normalization helpers and tool boundaries."""

import json
from contextlib import ExitStack
from datetime import date
import unittest
from unittest.mock import Mock, patch

from backend.agents.tools import fundamentals_tools, valuation_tools
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


class _FakeAsyncSessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class TestFinancialToolStockCodeBoundaries(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _service_patch(
        target: str,
        method_name: str,
        calls: list[tuple[tuple[object, ...], dict[str, object]]],
        result: dict[str, object],
    ):
        class FakeService:
            def __init__(self, session: object) -> None:
                self.session = session

        async def record_call(
            self: FakeService,
            *args: object,
            **kwargs: object,
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return result

        setattr(FakeService, method_name, record_call)
        return patch(target, FakeService)

    @staticmethod
    def _raising_service_patch(target: str, method_name: str):
        class RaisingService:
            def __init__(self, session: object) -> None:
                self.session = session

        async def fail_if_called(
            self: RaisingService,
            *args: object,
            **kwargs: object,
        ) -> dict[str, object]:
            raise AssertionError("service should not be called for an invalid stock code")

        setattr(RaisingService, method_name, fail_if_called)
        return patch(target, RaisingService)

    @staticmethod
    def _stock_code_from_call(
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> object:
        return kwargs.get("stock_code", args[0] if args else None)

    @staticmethod
    def _response_error(response: object) -> str:
        content = response.content[0]
        text = content["text"] if isinstance(content, dict) else content.text
        return json.loads(text)["error"]

    @staticmethod
    def _tool_specs() -> list[dict[str, object]]:
        return [
            {
                "name": "analyze_profitability",
                "tool": fundamentals_tools.analyze_profitability,
                "factory": "backend.agents.tools.fundamentals_tools.async_session_factory",
                "services": [
                    ("backend.analysis.profitability.ProfitabilityAnalysisService", "analyze", {}),
                ],
                "error": "盈利能力分析失败",
            },
            {
                "name": "analyze_growth",
                "tool": fundamentals_tools.analyze_growth,
                "factory": "backend.agents.tools.fundamentals_tools.async_session_factory",
                "services": [
                    ("backend.analysis.growth.GrowthAnalysisService", "analyze", {}),
                ],
                "error": "发展能力分析失败",
            },
            {
                "name": "analyze_solvency",
                "tool": fundamentals_tools.analyze_solvency,
                "factory": "backend.agents.tools.fundamentals_tools.async_session_factory",
                "services": [
                    ("backend.analysis.solvency.SolvencyAnalysisService", "analyze", {}),
                ],
                "error": "偿债能力分析失败",
            },
            {
                "name": "analyze_operating",
                "tool": fundamentals_tools.analyze_operating,
                "factory": "backend.agents.tools.fundamentals_tools.async_session_factory",
                "services": [
                    ("backend.analysis.operating.OperatingAnalysisService", "analyze", {}),
                ],
                "error": "营运能力分析失败",
            },
            {
                "name": "dcf_valuation_analysis",
                "tool": valuation_tools.dcf_valuation_analysis,
                "factory": "backend.agents.tools.valuation_tools.async_session_factory",
                "services": [
                    ("backend.valuation.dcf.DCFValuationService", "valuate", {}),
                ],
                "error": "DCF估值分析失败",
            },
            {
                "name": "residual_income_valuation_analysis",
                "tool": valuation_tools.residual_income_valuation_analysis,
                "factory": "backend.agents.tools.valuation_tools.async_session_factory",
                "services": [
                    ("backend.valuation.wacc.WACCService", "calculate", {"ke": 0.09}),
                    ("backend.valuation.residual_income.ResidualIncomeService", "valuate", {}),
                ],
                "error": "剩余收益估值分析失败",
            },
            {
                "name": "relative_valuation_analysis",
                "tool": valuation_tools.relative_valuation_analysis,
                "factory": "backend.agents.tools.valuation_tools.async_session_factory",
                "services": [
                    ("backend.valuation.relative.RelativeValuationService", "valuate", {}),
                ],
                "error": "相对估值分析失败",
            },
            {
                "name": "get_wacc_breakdown",
                "tool": valuation_tools.get_wacc_breakdown,
                "factory": "backend.agents.tools.valuation_tools.async_session_factory",
                "services": [
                    ("backend.valuation.wacc.WACCService", "calculate", {"ke": 0.09}),
                ],
                "error": "WACC计算失败",
            },
            {
                "name": "comprehensive_valuation_analysis",
                "tool": valuation_tools.comprehensive_valuation_analysis,
                "factory": "backend.agents.tools.valuation_tools.async_session_factory",
                "services": [
                    ("backend.valuation.triangulate.TriangulationService", "valuate", {}),
                ],
                "error": "综合估值分析失败",
            },
            {
                "name": "sotp_valuation_analysis",
                "tool": valuation_tools.sotp_valuation_analysis,
                "factory": "backend.agents.tools.valuation_tools.async_session_factory",
                "services": [
                    ("backend.valuation.sotp.SOTPValuationService", "valuate", {}),
                ],
                "error": "SOTP估值分析失败",
            },
        ]

    async def test_each_financial_tool_normalizes_stock_code_before_service(self) -> None:
        for spec in self._tool_specs():
            calls_by_service: list[list[tuple[tuple[object, ...], dict[str, object]]]] = []
            session = object()
            factory = Mock(return_value=_FakeAsyncSessionContext(session))

            with self.subTest(tool=spec["name"]), ExitStack() as stack:
                stack.enter_context(patch(spec["factory"], factory))
                for target, method_name, result in spec["services"]:
                    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
                    calls_by_service.append(calls)
                    stack.enter_context(
                        self._service_patch(target, method_name, calls, result),
                    )

                await spec["tool"](1)

            factory.assert_called_once_with()
            for calls in calls_by_service:
                self.assertEqual(len(calls), 1)
                args, kwargs = calls[0]
                self.assertEqual(self._stock_code_from_call(args, kwargs), "000001")

    async def test_invalid_stock_code_returns_localized_error_before_opening_session(self) -> None:
        for spec in self._tool_specs():
            factory = Mock(return_value=_FakeAsyncSessionContext(object()))

            with self.subTest(tool=spec["name"]), ExitStack() as stack:
                stack.enter_context(patch(spec["factory"], factory))
                for target, method_name, _result in spec["services"]:
                    stack.enter_context(self._raising_service_patch(target, method_name))

                response = await spec["tool"]("invalid")

            self.assertIn(spec["error"], self._response_error(response))
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
