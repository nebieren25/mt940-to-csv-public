"""
Unit tests for core parsing: parse_mt940_custom and pure helpers.
"""

import pytest

from src.core.parsing import (
    _cleared_description,
    _extract_description_fields,
    _format_signed_amount,
    _parse_mmdd,
    _parse_yyymmdd,
    parse_mt940_custom,
)


@pytest.mark.unit
class TestParseMt940Custom:
    """parse_mt940_custom returns (rows, account)."""

    def test_minimal_mt940_returns_one_row_and_account(
        self, minimal_mt940_with_one_tx: str
    ) -> None:
        rows, account = parse_mt940_custom(minimal_mt940_with_one_tx)
        assert len(rows) == 1
        assert account == "NL00TEST0123456789EUR"

    def test_sample_mt940_returns_one_row(self, sample_mt940_content: str) -> None:
        rows, account = parse_mt940_custom(sample_mt940_content)
        assert len(rows) >= 1
        assert account == "NL00TEST0123456789EUR"

    def test_first_row_has_required_fields(
        self, minimal_mt940_with_one_tx: str
    ) -> None:
        rows, _ = parse_mt940_custom(minimal_mt940_with_one_tx)
        r = rows[0]
        assert "entry_date" in r
        assert "amount" in r
        assert "value_date" in r
        assert "signed_amount" in r
        assert r["debit_credit"] == "D"
        assert r["value_date"] == "31-01-2025"
        assert r["entry_date"] == "01-31"


@pytest.mark.unit
class TestClearedDescription:
    """_cleared_description strips tags and normalizes."""

    def test_strips_remi_tag(self) -> None:
        out = _cleared_description("/REMI/USTD//Some text")
        assert "/REMI/" not in out
        assert "Some text" in out

    def test_strips_iban_like(self) -> None:
        out = _cleared_description("Pay NL00TEST9876543210 recipient")
        assert "NL00TEST9876543210" not in out
        assert "recipient" in out

    def test_strips_bic(self) -> None:
        out = _cleared_description("Bank INGBNL2A here")
        assert "INGBNL2A" not in out

    def test_empty_returns_empty(self) -> None:
        assert _cleared_description("") == ""

    def test_structured_cleared_description_prefers_counterparty_name(self) -> None:
        raw = (
            "/EREF/501829643239//MARF/1.21881344//CSID/NL93ZZZ332656790051"
            "//CNTP/NL12COBA0733959555/COBANL2XXXX/ODIDO NETHERLANDS B.V."
            "///REMI/USTD//Factuurnummer 901525297788//PURP/OTHR/"
        )

        assert _cleared_description(raw) == "ODIDO NETHERLANDS B.V."

    def test_structured_fields_keep_reference_details_separate(self) -> None:
        raw = (
            "/EREF/501829643239//MARF/1.21881344//CSID/NL93ZZZ332656790051"
            "//CNTP/NL12COBA0733959555/COBANL2XXXX/ODIDO NETHERLANDS B.V."
            "///REMI/USTD//Factuurnummer 901525297788//PURP/OTHR/"
        )

        fields = _extract_description_fields(raw)

        assert fields["description"] == "ODIDO NETHERLANDS B.V."
        assert fields["counterparty_iban"] == "NL12COBA0733959555"
        assert fields["counterparty_bic"] == "COBANL2XXXX"
        assert fields["payment_reference"] == "501829643239"
        assert fields["payment_description"] == "Factuurnummer 901525297788"
        assert fields["card_terminal"] == ""

    def test_generic_payment_processor_prefers_payment_description(self) -> None:
        raw = (
            "/EREF/32064405337//MARF/M-100286980-2903926815042522"
            "//CSID/NL23ZZZ611047600000"
            "//CNTP/NL48ABNA0122691407/ABNANL2A/WORLDPAY"
            "///REMI/USTD//HP Inc Instant Ink NL//ULTC/HP Inc Instant Ink NL//"
        )

        assert _cleared_description(raw) == "HP Inc Instant Ink NL"

    def test_card_terminal_metadata_moves_to_fields(self) -> None:
        raw = (
            "/REMI/USTD//BP CHARLOIS ZUIDZIJDE ROTTERDAM 01-10-2022 "
            "18:19TERMINALID: 09298211 PASVOLGNR: 001 TRANSACTIENR: G1B6T6/"
        )

        fields = _extract_description_fields(raw)

        assert fields["description"] == "BP CHARLOIS ZUIDZIJDE ROTTERDAM"
        assert fields["payment_description"] == "BP CHARLOIS ZUIDZIJDE ROTTERDAM"
        assert fields["card_terminal_id"] == "09298211"
        assert fields["card_sequence_number"] == "001"
        assert fields["card_transaction_number"] == "G1B6T6"

    def test_abn_sepa_description_fields(self) -> None:
        raw = (
            "0001 SEPA Overboeking | (02-01) IBAN: NL98INGB0008565296 | BIC:"
            "?20INGBNL2A | Naam: Hr R van Balen | Omschrijving: factuur: 2021636"
            "?21| Kenmerk: NOTPROVIDED"
        )

        fields = _extract_description_fields(raw)

        assert fields["description_format"] == "abn"
        assert fields["supplementary"] == "0001"
        assert fields["bank_transaction_label"] == "SEPA Overboeking"
        assert fields["description"] == "Hr R van Balen"
        assert fields["counterparty_name"] == "Hr R van Balen"
        assert fields["counterparty_iban"] == "NL98INGB0008565296"
        assert fields["counterparty_bic"] == "INGBNL2A"
        assert fields["payment_description"] == "factuur: 2021636"
        assert fields["payment_reference"] == ""

    def test_abn_bea_card_fields(self) -> None:
        raw = (
            "0057 BEA, Betaalpas | (08-04) Action 1354,PAS224 | "
            "NR:72131213?2008.04.22/11.21 | Spijkenisse"
        )

        fields = _extract_description_fields(raw)

        assert fields["description_format"] == "abn"
        assert fields["supplementary"] == "0057"
        assert fields["bank_transaction_label"] == "BEA, Betaalpas"
        assert fields["description"] == "Action 1354 Spijkenisse"
        assert fields["card_terminal"] == "Action 1354 Spijkenisse"
        assert fields["card_terminal_id"] == "72131213"
        assert fields["card_sequence_number"] == "224"


@pytest.mark.unit
class TestParseYyymmdd:
    def test_250131_to_2025_01_31(self) -> None:
        assert _parse_yyymmdd("250131") == "31-01-2025"

    def test_short_returns_empty(self) -> None:
        assert _parse_yyymmdd("2501") == ""


@pytest.mark.unit
class TestParseMmdd:
    def test_0131_to_01_31(self) -> None:
        assert _parse_mmdd("0131") == "01-31"

    def test_short_returns_empty(self) -> None:
        assert _parse_mmdd("01") == ""


@pytest.mark.unit
class TestFormatSignedAmount:
    def test_debit_negative(self) -> None:
        assert _format_signed_amount("22,85", "D") == "-22,85"

    def test_credit_positive(self) -> None:
        assert _format_signed_amount("75,00", "C") == "75,00"

    def test_empty_returns_empty(self) -> None:
        assert _format_signed_amount("", "C") == ""
