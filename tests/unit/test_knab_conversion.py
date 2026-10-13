"""Knab profile dispatch, display styles, and default CLI conversion."""

import csv
import io
from unittest.mock import patch

import pytest

from src.adapters.file_io import convert_one_file
from src.core.convert import content_to_rows, rows_to_csv_string
from src.core.domain import CSV_HEADERS
from src.core.parsing import parse_mt940_custom


KNAB_CONTENT = """:20:SYNTHETIC001
:25:NL00KNAB0000000000
:28C:00001/001
:60F:C240101EUR100,00
:61:2401020102D10,50N100NONREF//BANK001
:86:/TRTP/SEPA OVERBOEKING/IBAN/NL00TEST0000000000/BIC/TESTNL2A/NAME/SAMPLE SUPPLIER/REMI/Invoice 42/EREF/PAY001
:61:2401020102D2,00N300NONREF//BANK002
:86:/TRTP/BETAALAUTOMAAT/NAME/SAMPLE SHOP/REMI/ROTTERDAM
:62F:C240102EUR87,50
"""


@pytest.mark.unit
class TestKnabConversion:
    def test_auto_and_explicit_knab_produce_the_same_rows(self):
        auto = content_to_rows(KNAB_CONTENT)
        knab = content_to_rows(KNAB_CONTENT, bank_profile="knab")
        assert auto == knab
        rows, account = auto
        assert account == "NL00KNAB0000000000"
        assert [r["amount"] for r in rows] == ["-10,50", "-2,00"]
        assert rows[0]["counterparty_name"] == "SAMPLE SUPPLIER"
        assert rows[0]["closing_balance"] == "87,50"

    @pytest.mark.parametrize(
        "style,expected",
        [
            ("counterparty", ["SAMPLE SUPPLIER", "SAMPLE SHOP"]),
            (
                "sepa_overboeking_with_description",
                ["SAMPLE SUPPLIER - Invoice 42", "SAMPLE SHOP"],
            ),
            (
                "counterparty_with_description",
                ["SAMPLE SUPPLIER - Invoice 42", "SAMPLE SHOP - ROTTERDAM"],
            ),
        ],
    )
    def test_existing_description_styles_apply_to_knab(self, style, expected):
        rows, _ = content_to_rows(KNAB_CONTENT, description_style=style)
        assert [r["description"] for r in rows] == expected
        exported = list(csv.DictReader(io.StringIO(rows_to_csv_string(
            rows, delimiter=";", description_style=style
        )), delimiter=";"))
        assert [r["description"] for r in exported] == expected
        assert list(exported[0]) == CSV_HEADERS

    @pytest.mark.parametrize("profile", ["ing", "rabo", "raw", "abn"])
    def test_explicit_other_profiles_keep_the_existing_parser(self, profile):
        expected, expected_account = parse_mt940_custom(KNAB_CONTENT)
        with patch("src.core.convert.parse_knab_mt940", side_effect=AssertionError(
            "A different explicit profile must not use the Knab parser"
        )):
            rows, account = content_to_rows(KNAB_CONTENT, bank_profile=profile)
        assert account == expected_account
        assert [r["amount"] for r in rows] == [r["amount"] for r in expected]
        assert rows[0]["counterparty_name"] == ""
        assert rows[0]["description_format"] == expected[0]["description_format"]

    def test_generic_name_tag_does_not_override_auto_bank_identity(self):
        content = KNAB_CONTENT.replace("NL00KNAB0000000000", "NL00TEST0000000000")
        with patch("src.core.convert.parse_knab_mt940", side_effect=AssertionError(
            "NAME/TRTP tags alone are not evidence of a Knab account"
        )):
            rows, account = content_to_rows(content)
        assert account == "NL00TEST0000000000"
        assert len(rows) == 2

    def test_file_adapter_uses_auto_knab_without_new_cli_flags(self, tmp_path):
        source = tmp_path / "synthetic-knab.txt"
        output = tmp_path / "synthetic-knab.csv"
        source.write_text(KNAB_CONTENT, encoding="utf-8")
        assert convert_one_file(source, output, delimiter=";", decimal_sep=".") == (True, 2)
        with output.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
        assert rows[0]["counterparty_name"] == "SAMPLE SUPPLIER"
        assert rows[0]["amount"] == "-10.50"
        assert rows[0]["closing_balance"] == "87.50"
