"""
Unit tests for core convert: content_to_rows and rows_to_csv_string.
"""

import pytest

from src.core.convert import apply_description_style, content_to_rows, rows_to_csv_string
from src.core.domain import CSV_HEADERS


@pytest.mark.unit
class TestContentToRows:
    """content_to_rows(content) -> (rows, account)."""

    def test_sample_content_returns_at_least_one_row(
        self, sample_mt940_content: str
    ) -> None:
        rows, account = content_to_rows(sample_mt940_content)
        assert len(rows) >= 1
        assert account == "NL00TEST0123456789EUR"

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

    def test_abn_profile_default_description_adds_omschrijving_for_sepa(self) -> None:
        content = """{4:
:20:REF001
:25:NL00ABNA0123456789EUR
:60F:C240101EUR100,00
:61:2401020102D10,00NTRFNONREF//1
:86:0001 SEPA Overboeking | (02-01) IBAN: NL98INGB0008565296 | BIC: INGBNL2A | Naam: Hr R van Balen | Omschrijving: factuur: 2021636 | Kenmerk: NOTPROVIDED
:62F:C240102EUR90,00
}
"""

        rows, account = content_to_rows(content, bank_profile="abn")

        assert account == "NL00ABNA0123456789EUR"
        assert rows[0]["bank_transaction_label"] == "SEPA Overboeking"
        assert rows[0]["description"] == "Hr R van Balen - factuur: 2021636"


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

    def test_description_style_counterparty_only(self) -> None:
        row = {
            "date": "02-01-2024",
            "description": "Hr R van Balen",
            "amount": "-10,00",
            "counterparty_name": "Hr R van Balen",
            "payment_description": "factuur: 2021636",
            "bank_transaction_label": "SEPA Overboeking",
        }

        rows = apply_description_style([row], "counterparty")

        assert rows[0]["description"] == "Hr R van Balen"

    def test_description_style_appends_description_for_all_rows_when_selected(self) -> None:
        row = {
            "date": "02-01-2024",
            "description": "ODIDO NETHERLANDS B.V.",
            "amount": "-10,00",
            "counterparty_name": "ODIDO NETHERLANDS B.V.",
            "payment_description": "Factuurnummer 901525297788",
            "bank_transaction_label": "SEPA Incasso",
        }

        rows = apply_description_style([row], "counterparty_with_description")

        assert rows[0]["description"] == "ODIDO NETHERLANDS B.V. - Factuurnummer 901525297788"

    def test_generic_counterparty_keeps_clean_existing_description(self) -> None:
        row = {
            "date": "02-01-2024",
            "description": "HP Inc Instant Ink NL",
            "amount": "-5,99",
            "counterparty_name": "WORLDPAY",
            "payment_description": "HP Inc Instant Ink NL",
        }

        rows = apply_description_style([row])

        assert rows[0]["description"] == "HP Inc Instant Ink NL"
