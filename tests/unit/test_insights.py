"""
Unit tests for core insights: filter_rows_by_scope, compute_metrics, compute_breakdown, check_currencies.
"""

import pytest

from src.core.insights import (
    check_currencies,
    compute_breakdown,
    compute_metrics,
    filter_rows_by_scope,
)


@pytest.mark.unit
class TestFilterRowsByScope:
    """filter_rows_by_scope(rows, scope) -> filtered rows."""

    def test_empty_rows(self) -> None:
        assert filter_rows_by_scope([], {"year": None, "quarter": None, "month": None}) == []

    def test_all_time_returns_all(self) -> None:
        rows = [
            {"value_date": "2024-01-15", "signed_amount": "100"},
            {"value_date": "2025-06-20", "signed_amount": "-50"},
        ]
        got = filter_rows_by_scope(rows, {"year": None, "quarter": None, "month": None})
        assert len(got) == 2

    def test_single_year(self) -> None:
        rows = [
            {"value_date": "2024-01-15", "signed_amount": "100"},
            {"value_date": "2025-06-20", "signed_amount": "-50"},
        ]
        got = filter_rows_by_scope(rows, {"year": 2024, "quarter": None, "month": None})
        assert len(got) == 1
        assert got[0]["value_date"] == "2024-01-15"

    def test_year_plus_quarter(self) -> None:
        rows = [
            {"value_date": "2024-01-15", "signed_amount": "100"},   # Q1
            {"value_date": "2024-05-10", "signed_amount": "50"},    # Q2
        ]
        got = filter_rows_by_scope(rows, {"year": 2024, "quarter": 2, "month": None})
        assert len(got) == 1
        assert got[0]["value_date"] == "2024-05-10"

    def test_year_quarter_month(self) -> None:
        rows = [
            {"value_date": "2024-05-01", "signed_amount": "10"},
            {"value_date": "2024-05-15", "signed_amount": "20"},
            {"value_date": "2024-06-01", "signed_amount": "30"},
        ]
        got = filter_rows_by_scope(rows, {"year": 2024, "quarter": 2, "month": 5})
        assert len(got) == 2
        assert all(r["value_date"].startswith("2024-05") for r in got)

    def test_skips_rows_without_date(self) -> None:
        rows = [
            {"value_date": "2024-01-15", "signed_amount": "100"},
            {"signed_amount": "50"},
        ]
        got = filter_rows_by_scope(rows, {"year": None, "quarter": None, "month": None})
        assert len(got) == 1


@pytest.mark.unit
class TestComputeMetrics:
    """compute_metrics(rows) -> dict."""

    def test_empty_rows(self) -> None:
        m = compute_metrics([])
        assert m["total_count"] == 0
        assert m["total_income"] == 0.0
        assert m["total_expense"] == 0.0
        assert m["min_date"] is None
        assert m["avg_income_txn"] == 0.0
        assert m["avg_expense_txn"] == 0.0

    def test_single_income(self) -> None:
        rows = [{"value_date": "2024-01-15", "signed_amount": "100.50"}]
        m = compute_metrics(rows)
        assert m["total_income"] == 100.5
        assert m["total_expense"] == 0.0
        assert m["net"] == 100.5
        assert m["income_count"] == 1
        assert m["expense_count"] == 0
        assert m["min_date"] == m["max_date"] == "2024-01-15"
        assert m["avg_income_txn"] == 100.5

    def test_mixed_income_expense(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "100"},
            {"value_date": "2024-01-02", "signed_amount": "-30"},
            {"value_date": "2024-01-03", "signed_amount": "20"},
        ]
        m = compute_metrics(rows)
        assert m["total_income"] == 120.0
        assert m["total_expense"] == 30.0
        assert m["net"] == 90.0
        assert m["total_count"] == 3
        assert m["income_count"] == 2
        assert m["expense_count"] == 1
        assert m["min_date"] == "2024-01-01"
        assert m["max_date"] == "2024-01-03"
        assert m["avg_income_txn"] == 60.0
        assert m["avg_expense_txn"] == 30.0

    def test_most_frequent_description(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "1", "description": "  Foo  Bar  "},
            {"value_date": "2024-01-02", "signed_amount": "1", "description": "foo bar"},
            {"value_date": "2024-01-03", "signed_amount": "1", "description": "Other"},
        ]
        m = compute_metrics(rows)
        assert m["most_frequent_description"] == "foo bar"


@pytest.mark.unit
class TestComputeBreakdown:
    """compute_breakdown(rows) -> list of level/period/income/expense/net/count/avg_txn."""

    def test_empty_rows(self) -> None:
        assert compute_breakdown([]) == []

    def test_yearly_totals(self) -> None:
        rows = [
            {"value_date": "2023-03-15", "signed_amount": "100"},
            {"value_date": "2023-06-20", "signed_amount": "-50"},
            {"value_date": "2024-01-10", "signed_amount": "200"},
        ]
        b = compute_breakdown(rows)
        year_rows = [r for r in b if r["level"] == 0]
        assert len(year_rows) == 2
        y2023 = next(r for r in year_rows if r["year"] == 2023)
        y2024 = next(r for r in year_rows if r["year"] == 2024)
        assert y2023["income"] == 100.0
        assert y2023["expense"] == 50.0
        assert y2023["net"] == 50.0
        assert y2023["count"] == 2
        assert y2024["income"] == 200.0
        assert y2024["expense"] == 0.0
        assert y2024["count"] == 1

    def test_quarter_grouping(self) -> None:
        rows = [
            {"value_date": "2024-01-05", "signed_amount": "10"},   # Q1
            {"value_date": "2024-02-10", "signed_amount": "20"},   # Q1
            {"value_date": "2024-05-15", "signed_amount": "-5"},   # Q2
        ]
        b = compute_breakdown(rows)
        quarter_rows = [r for r in b if r["level"] == 1]
        q1 = next(r for r in quarter_rows if r["quarter"] == 1)
        q2 = next(r for r in quarter_rows if r["quarter"] == 2)
        assert q1["income"] == 30.0
        assert q1["expense"] == 0.0
        assert q1["count"] == 2
        assert q2["income"] == 0.0
        assert q2["expense"] == 5.0
        assert q2["count"] == 1

    def test_month_grouping(self) -> None:
        rows = [
            {"value_date": "2024-04-01", "signed_amount": "100"},
            {"value_date": "2024-05-01", "signed_amount": "50"},
            {"value_date": "2024-06-01", "signed_amount": "-25"},
        ]
        b = compute_breakdown(rows)
        month_rows = [r for r in b if r["level"] == 2]
        apr = next(r for r in month_rows if r["month"] == 4)
        may = next(r for r in month_rows if r["month"] == 5)
        jun = next(r for r in month_rows if r["month"] == 6)
        assert apr["income"] == 100.0 and apr["expense"] == 0.0 and apr["count"] == 1
        assert may["income"] == 50.0 and may["count"] == 1
        assert jun["expense"] == 25.0 and jun["count"] == 1
        assert apr["period"] == "Apr"
        assert may["period"] == "May"
        assert jun["period"] == "Jun"


@pytest.mark.unit
class TestCheckCurrencies:
    """check_currencies(rows) -> None or 'mixed'."""

    def test_empty(self) -> None:
        assert check_currencies([]) is None

    def test_single_currency(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "currency": "EUR"},
            {"value_date": "2024-01-02", "currency": "EUR"},
        ]
        assert check_currencies(rows) is None

    def test_mixed_currency(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "currency": "EUR"},
            {"value_date": "2024-01-02", "currency": "USD"},
        ]
        assert check_currencies(rows) == "mixed"

    def test_no_currency_treated_as_empty(self) -> None:
        rows = [{"value_date": "2024-01-01", "signed_amount": "1"}]
        assert check_currencies(rows) is None
