"""
Unit tests for core csv_parse: csv_content_to_rows.
"""

import pytest

from src.core.csv_parse import CSVColumnError, csv_content_to_rows
from src.core.domain import CSV_HEADERS


@pytest.mark.unit
class TestCsvContentToRows:
    """csv_content_to_rows(content, delimiter?) -> list[dict]."""

    def test_valid_csv_returns_rows(self) -> None:
        content = "value_date,account,signed_amount,currency,reference,description\n2024-01-15,NL00BANK,100.50,EUR,ref1,Pay"
        rows = csv_content_to_rows(content)
        assert len(rows) == 1
        assert rows[0]["value_date"] == "2024-01-15"
        assert rows[0]["account"] == "NL00BANK"
        assert rows[0]["signed_amount"] == "100.50"
        assert rows[0]["currency"] == "EUR"

    def test_valid_csv_with_semicolon_delimiter(self) -> None:
        content = "value_date;account;signed_amount\n2024-01-15;NL00BANK;-50.25"
        rows = csv_content_to_rows(content, delimiter=";")
        assert len(rows) == 1
        assert rows[0]["value_date"] == "2024-01-15"
        assert rows[0]["signed_amount"] == "-50.25"

    def test_detect_delimiter_comma(self) -> None:
        content = "value_date,amount,account\n2024-01-01,10,NL"
        rows = csv_content_to_rows(content)
        assert len(rows) == 1
        assert rows[0]["value_date"] == "2024-01-01"
        assert rows[0]["amount"] == "10"

    def test_detect_delimiter_semicolon(self) -> None:
        content = "value_date;amount;account\n2024-01-01;20;NL"
        rows = csv_content_to_rows(content)
        assert len(rows) == 1
        assert rows[0]["amount"] == "20"

    def test_empty_content_returns_empty_list(self) -> None:
        assert csv_content_to_rows("") == []
        assert csv_content_to_rows("   \n  ") == []

    def test_header_only_returns_empty_list(self) -> None:
        content = "value_date,account,signed_amount"
        rows = csv_content_to_rows(content)
        assert rows == []

    def test_missing_date_column_raises(self) -> None:
        content = "account,signed_amount\nNL,100"
        with pytest.raises(CSVColumnError) as exc_info:
            csv_content_to_rows(content)
        assert "value_date" in str(exc_info.value) or "entry_date" in str(exc_info.value)

    def test_missing_amount_column_raises(self) -> None:
        content = "value_date,account\n2024-01-01,NL"
        with pytest.raises(CSVColumnError) as exc_info:
            csv_content_to_rows(content)
        assert "signed_amount" in str(exc_info.value) or "amount" in str(exc_info.value)

    def test_row_has_all_csv_header_keys(self) -> None:
        content = "value_date,signed_amount,account\n2024-01-01,10,NL"
        rows = csv_content_to_rows(content)
        assert len(rows) == 1
        for h in CSV_HEADERS:
            assert h in rows[0]
        assert rows[0]["value_date"] == "2024-01-01"
        assert rows[0]["signed_amount"] == "10"
        assert rows[0]["account"] == "NL"

    def test_multiple_rows(self) -> None:
        content = "value_date,signed_amount,account\n2024-01-01,1,NL\n2024-01-02,2,NL"
        rows = csv_content_to_rows(content)
        assert len(rows) == 2
        assert rows[0]["signed_amount"] == "1"
        assert rows[1]["signed_amount"] == "2"

    def test_entry_date_accepted(self) -> None:
        content = "entry_date,amount,account\n2024-03-15,5.50,NL"
        rows = csv_content_to_rows(content)
        assert len(rows) == 1
        assert rows[0]["entry_date"] == "2024-03-15"
        assert rows[0]["amount"] == "5.50"

    def test_card_terminal_metadata_is_split_from_description(self) -> None:
        content = (
            "value_date;signed_amount;description;payment_description\n"
            "2022-10-01;-25,00;BP CHARLOIS ZUIDZIJDE ROTTERDAM 01-10-2022 "
            "18:19TERMINALID: 09298211 PASVOLGNR: 001 TRANSACTIENR: G1B6T6;"
            "BP CHARLOIS ZUIDZIJDE ROTTERDAM 01-10-2022 "
            "18:19TERMINALID: 09298211 PASVOLGNR: 001 TRANSACTIENR: G1B6T6"
        )

        rows = csv_content_to_rows(content, delimiter=";")

        assert rows[0]["description"] == "BP CHARLOIS ZUIDZIJDE ROTTERDAM"
        assert rows[0]["payment_description"] == "BP CHARLOIS ZUIDZIJDE ROTTERDAM"
        assert rows[0]["card_terminal_id"] == "09298211"
        assert rows[0]["card_sequence_number"] == "001"
        assert rows[0]["card_transaction_number"] == "G1B6T6"
