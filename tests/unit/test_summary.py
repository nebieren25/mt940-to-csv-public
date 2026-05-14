"""
Unit tests for core summary: compute_financial_summary.
"""

import pytest

from src.core.summary import compute_financial_summary


@pytest.mark.unit
class TestComputeFinancialSummary:
    """compute_financial_summary(rows) -> dict | None."""

    def test_empty_rows_returns_none(self) -> None:
        assert compute_financial_summary([]) is None

    def test_single_row_positive_amount(self) -> None:
        rows = [
            {
                "value_date": "2024-01-15",
                "signed_amount": "100.50",
                "account": "NL00BANK",
            }
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 100.5
        assert s["total_expense"] == 0.0
        assert s["net_change"] == 100.5
        assert s["total_count"] == 1
        assert s["income_count"] == 1
        assert s["expense_count"] == 0
        assert s["date_range"]["from"] == "2024-01-15"
        assert s["date_range"]["to"] == "2024-01-15"

    def test_single_row_negative_amount(self) -> None:
        rows = [
            {
                "value_date": "2024-02-20",
                "signed_amount": "-50.25",
                "account": "NL00BANK",
            }
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 0.0
        assert s["total_expense"] == 50.25
        assert s["net_change"] == -50.25
        assert s["income_count"] == 0
        assert s["expense_count"] == 1

    def test_all_positive_amounts(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "10"},
            {"value_date": "2024-01-02", "signed_amount": "20"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 30.0
        assert s["total_expense"] == 0.0
        assert s["net_change"] == 30.0
        assert s["income_count"] == 2
        assert s["expense_count"] == 0
        assert s["date_range"]["from"] == "2024-01-01"
        assert s["date_range"]["to"] == "2024-01-02"

    def test_all_negative_amounts(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "-5.50"},
            {"value_date": "2024-01-02", "signed_amount": "-4.50"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 0.0
        assert s["total_expense"] == 10.0
        assert s["net_change"] == -10.0
        assert s["income_count"] == 0
        assert s["expense_count"] == 2

    def test_mixed_income_and_expense(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "100"},
            {"value_date": "2024-01-02", "signed_amount": "-30"},
            {"value_date": "2024-01-03", "signed_amount": "20"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 120.0
        assert s["total_expense"] == 30.0
        assert s["net_change"] == 90.0
        assert s["total_count"] == 3
        assert s["income_count"] == 2
        assert s["expense_count"] == 1

    def test_missing_amount_treated_as_zero(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "account": "X"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 0.0
        assert s["total_expense"] == 0.0
        assert s["net_change"] == 0.0
        assert s["total_count"] == 1
        assert s["income_count"] == 0
        assert s["expense_count"] == 0

    def test_uses_entry_date_when_no_value_date(self) -> None:
        rows = [
            {"entry_date": "2024-06-15", "signed_amount": "1"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["date_range"]["from"] == "2024-06-15"
        assert s["date_range"]["to"] == "2024-06-15"

    def test_decimal_no_float_errors(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "0.1"},
            {"value_date": "2024-01-02", "signed_amount": "0.2"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["net_change"] == pytest.approx(0.3)
        assert s["total_income"] == pytest.approx(0.3)

    def test_comma_decimal_in_amount(self) -> None:
        rows = [
            {"value_date": "2024-01-01", "signed_amount": "12,34"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert s["total_income"] == 12.34

    def test_yearly_breakdown(self) -> None:
        rows = [
            {"value_date": "2023-03-15", "signed_amount": "100"},
            {"value_date": "2023-06-20", "signed_amount": "-50"},
            {"value_date": "2024-01-10", "signed_amount": "200"},
        ]
        s = compute_financial_summary(rows)
        assert s is not None
        assert "yearly_breakdown" in s
        yb = s["yearly_breakdown"]
        assert len(yb) == 2
        y2023 = next(r for r in yb if r["year"] == "2023")
        y2024 = next(r for r in yb if r["year"] == "2024")
        assert y2023["income"] == 100.0
        assert y2023["expense"] == 50.0
        assert y2024["income"] == 200.0
        assert y2024["expense"] == 0.0
