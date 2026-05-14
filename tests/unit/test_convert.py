"""
Unit tests for core convert: content_to_rows and rows_to_csv_string.
"""

import pytest

from src.core.convert import content_to_rows, rows_to_csv_string
from src.core.domain import CSV_HEADERS


@pytest.mark.unit
class TestContentToRows:
    """content_to_rows(content) -> (rows, account)."""

    def test_sample_content_returns_at_least_one_row(
        self, sample_mt940_content: str
    ) -> None:
        rows, account = content_to_rows(sample_mt940_content)
        assert len(rows) >= 1
        assert account == "NL85INGB0398076014EUR"

    def test_first_row_has_expected_fields(self, sample_mt940_content: str) -> None:
        rows, _ = content_to_rows(sample_mt940_content)
        r = rows[0]
        assert "entry_date" in r
        assert "amount" in r
        assert "value_date" in r
        assert "signed_amount" in r

    def test_empty_content_returns_empty_list(self) -> None:
        rows, account = content_to_rows("")
        assert rows == []
        assert account == ""


@pytest.mark.unit
class TestRowsToCsvString:
    """rows_to_csv_string(rows, delimiter, decimal_sep) -> str."""

    def test_output_has_header_line(self, sample_mt940_content: str) -> None:
        rows, _ = content_to_rows(sample_mt940_content)
        csv_str = rows_to_csv_string(rows)
        assert "entry_date" in csv_str
        first_line = csv_str.splitlines()[0]
        assert "entry_date" in first_line

    def test_delimiter_semicolon_used(self, sample_mt940_content: str) -> None:
        rows, _ = content_to_rows(sample_mt940_content)
        csv_str = rows_to_csv_string(rows, delimiter=";")
        lines = csv_str.strip().splitlines()
        assert len(lines) >= 2  # header + at least one data row
        assert ";" in lines[0]

    def test_line_count_is_header_plus_rows(self, sample_mt940_content: str) -> None:
        rows, _ = content_to_rows(sample_mt940_content)
        csv_str = rows_to_csv_string(rows)
        line_count = len(csv_str.strip().splitlines())
        assert line_count == 1 + len(rows)

    def test_uses_csv_headers(self) -> None:
        row = {h: "" for h in CSV_HEADERS}
        row["entry_date"] = "01-31"
        row["amount"] = "10,50"
        csv_str = rows_to_csv_string([row])
        for h in CSV_HEADERS:
            assert h in csv_str
