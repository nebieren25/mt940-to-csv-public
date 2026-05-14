"""
Golden tests for insights aggregation: compute_breakdown and compute_metrics.
Reference for UI client-side aggregation and future migration.
"""

import pytest

from src.core.insights import compute_breakdown, compute_metrics


@pytest.mark.unit
class TestInsightsAggregationGolden:
    """Golden results: fixed rows -> exact breakdown structure and values."""

    def test_breakdown_empty_returns_empty(self) -> None:
        assert compute_breakdown([]) == []

    def test_breakdown_single_year_golden(self) -> None:
        rows = [
            {"value_date": "2024-01-15", "signed_amount": "100"},
            {"value_date": "2024-06-20", "signed_amount": "-50"},
            {"value_date": "2024-12-01", "signed_amount": "25"},
        ]
        b = compute_breakdown(rows)
        year_rows = [r for r in b if r["level"] == 0]
        assert len(year_rows) == 1
        assert year_rows[0]["year"] == 2024
        assert year_rows[0]["period"] == "2024"
        assert year_rows[0]["income"] == 125.0
        assert year_rows[0]["expense"] == 50.0
        assert year_rows[0]["net"] == 75.0
        assert year_rows[0]["count"] == 3

    def test_breakdown_year_totals_and_quarter_labels_golden(self) -> None:
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
        assert y2023["income"] == 100.0 and y2023["expense"] == 50.0 and y2023["net"] == 50.0
        assert y2024["income"] == 200.0 and y2024["expense"] == 0.0 and y2024["net"] == 200.0
        quarter_rows = [r for r in b if r["level"] == 1]
        periods_q = [r["period"] for r in quarter_rows]
        assert "Q1 2023" in periods_q
        assert "Q2 2023" in periods_q
        assert "Q1 2024" in periods_q

    def test_breakdown_quarter_grouping_golden(self) -> None:
        rows = [
            {"value_date": "2024-01-05", "signed_amount": "10"},
            {"value_date": "2024-02-10", "signed_amount": "20"},
            {"value_date": "2024-05-15", "signed_amount": "-5"},
        ]
        b = compute_breakdown(rows)
        quarter_rows = [r for r in b if r["level"] == 1]
        q1 = next(r for r in quarter_rows if r["quarter"] == 1)
        q2 = next(r for r in quarter_rows if r["quarter"] == 2)
        assert q1["income"] == 30.0 and q1["expense"] == 0.0 and q1["count"] == 2
        assert q2["income"] == 0.0 and q2["expense"] == 5.0 and q2["count"] == 1
        assert q1["period"] == "Q1 2024"
        assert q2["period"] == "Q2 2024"

    def test_breakdown_month_grouping_and_labels_golden(self) -> None:
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
        assert apr["period"] == "Apr" and apr["income"] == 100.0 and apr["expense"] == 0.0
        assert may["period"] == "May" and may["income"] == 50.0
        assert jun["period"] == "Jun" and jun["expense"] == 25.0

    def test_breakdown_month_labels_oct_nov_jan_golden(self) -> None:
        rows = [
            {"value_date": "2024-10-01", "signed_amount": "10"},
            {"value_date": "2024-11-15", "signed_amount": "20"},
            {"value_date": "2024-01-10", "signed_amount": "5"},
        ]
        b = compute_breakdown(rows)
        month_rows = [r for r in b if r["level"] == 2]
        labels = {r["month"]: r["period"] for r in month_rows}
        assert labels.get(1) == "Jan"
        assert labels.get(10) == "Oct"
        assert labels.get(11) == "Nov"

    def test_metrics_date_range_and_totals_golden(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "100"},
            {"value_date": "2024-01-02", "signed_amount": "-30"},
            {"value_date": "2024-01-03", "signed_amount": "20"},
        ]
        m = compute_metrics(rows)
        assert m["min_date"] == "2024-01-01"
        assert m["max_date"] == "2024-01-03"
        assert m["total_income"] == 120.0
        assert m["total_expense"] == 30.0
        assert m["net"] == 90.0
        assert m["total_count"] == 3
        assert m["income_count"] == 2
        assert m["expense_count"] == 1
