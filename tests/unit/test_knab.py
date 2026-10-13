"""Knab dialect regressions using synthetic, non-customer statement data."""

from decimal import Decimal

import pytest

from src.core.domain import CSV_HEADERS
from src.core.knab import looks_like_knab_content, parse_knab_mt940


ACCOUNT = "NL00KNAB0123456789"
COUNTERPARTY_IBAN = "NL00TEST9876543210"


def _page(
    transactions: str,
    *,
    reference: str = "STMT-A",
    number: str = "00001/1",
    opening: str = ":60F:C240101EUR100,00",
    closing: str = ":62F:C240102EUR88,01",
    account: str = ACCOUNT,
) -> str:
    return (
        f":20:{reference}\n:25:{account}\n:28C:{number}\n"
        f"{opening}\n{transactions.rstrip()}\n{closing}\n"
    )


@pytest.fixture
def knab_transaction_kinds() -> str:
    """Cover the different :86: layouts without reusing private bank data."""
    return _page(
        f""":61:2401020102D10,N100CLIENT-1//BANK-1
:86:/TRTP/SEPA OVERBOEKING/IBAN/{COUNTERPARTY_IBAN}/BIC/TESTNL2A/NAME/Example Supplier/EREF/PAYMENT-1/REMI/Invoice /STORE/ branch 7
:61:2401020102D1,2N300NONREF//BANK-2
:86:/TRTP/BETAALAUTOMAAT/NAME/Corner Shop/REMI/Testtown 02-01-2024 11:00 PAS: 001
:61:2401020102D2,34N302NONREF//BANK-3
:86:/TRTP/GELDAUTOMAAT/NAME/Cashpoint Testtown/REMI/Testtown 02-01-2024 12:00 PAS: 001
:61:2401020102D3,45N401NONREF//BANK-4
:86:/TRTP/PAKKETKOSTEN/BBAN/0000000123/NAME/Example Bank/REMI/Monthly account fee
:61:2401020102D4,00N132NONREF//BANK-5
:86:/TRTP/SEPA INCASSO DOORLOPEND/IBAN/{COUNTERPARTY_IBAN}/BIC/TESTNL2A/NAME/Example Utility/CSID/NL00ZZZ000000000000/MARF/MANDATE-1/EREF/DEBIT-1/REMI/Subscription January
:61:2401020102C4,00N125NONREF//BANK-6
:86:/RTRN/AM04/TRTP/SEPA TERUGBOEKING INCASSO/IBAN/{COUNTERPARTY_IBAN}/NAME/Example Utility/CSID/NL00ZZZ000000000000/MARF/MANDATE-1/EREF/RETURN-1/REMI/Returned subscription
:61:2401020102C5,00NTRFNONREF//BANK-7
:86:/BBAN/0000000456/NAME/Example Internal/REMI/Bank internal credit
"""
    )


@pytest.mark.unit
class TestKnabDescriptionFields:
    def test_transaction_kinds_keep_names_and_payment_details_separate(
        self, knab_transaction_kinds: str
    ) -> None:
        rows, account = parse_knab_mt940(knab_transaction_kinds)

        assert account == ACCOUNT
        assert len(rows) == 7
        assert [r["description"] for r in rows] == [
            "Example Supplier",
            "Corner Shop",
            "Cashpoint Testtown",
            "Example Bank",
            "Example Utility",
            "Example Utility",
            "Example Internal",
        ]
        assert [r["counterparty_name"] for r in rows] == [
            r["description"] for r in rows
        ]
        assert [r["amount"] for r in rows] == [
            "-10,00", "-1,20", "-2,34", "-3,45", "-4,00", "4,00", "5,00"
        ]
        assert all(set(CSV_HEADERS) <= set(row) for row in rows)
        assert all(row["description_format"] == "knab" for row in rows)
        assert all(row["account"] == ACCOUNT for row in rows)
        assert all(row["currency"] == "EUR" for row in rows)
        assert all(row["date"] == "02-01-2024" for row in rows)
        assert all(row["value_date"] == "02-01-2024" for row in rows)
        assert all(row["entry_date"] == "01-02" for row in rows)
        assert all(row["statement_number"] == "00001/1" for row in rows)
        assert all(row["transaction_reference"] == "STMT-A" for row in rows)
        assert all(row["opening_balance"] == "100,00" for row in rows)
        assert all(row["closing_balance"] == "88,01" for row in rows)

        transfer, card, atm, fee, debit, returned, internal = rows
        assert transfer["counterparty_account"] == COUNTERPARTY_IBAN
        assert transfer["counterparty_iban"] == COUNTERPARTY_IBAN
        assert transfer["counterparty_bic"] == "TESTNL2A"
        assert transfer["bank_transaction_label"] == "SEPA OVERBOEKING"
        assert transfer["payment_reference"] == "PAYMENT-1"
        assert transfer["payment_description"] == "Invoice /STORE/ branch 7"
        assert transfer["customer_ref"] == "CLIENT-1"
        assert transfer["bank_ref"] == "BANK-1"
        assert transfer["reference"] == "BANK-1"
        assert transfer["transaction_type"] == "N100"

        assert card["card_terminal"] == "Corner Shop"
        assert card["payment_description"].startswith("Testtown ")
        assert atm["card_terminal"] == "Cashpoint Testtown"
        assert atm["transaction_type"] == "N302"
        assert fee["counterparty_account"] == "0000000123"
        assert fee["counterparty_iban"] == ""
        assert fee["bank_transaction_label"] == "PAKKETKOSTEN"
        assert fee["transaction_type"] == "N401"
        assert debit["mandate_reference"] == "MANDATE-1"
        assert debit["creditor_id"] == "NL00ZZZ000000000000"
        assert debit["payment_reference"] == "DEBIT-1"
        assert returned["return_reason"] == "AM04"
        assert returned["mandate_reference"] == "MANDATE-1"
        assert returned["payment_reference"] == "RETURN-1"
        assert internal["counterparty_account"] == "0000000456"
        assert internal["bank_transaction_label"] == ""
        assert internal["transaction_type"] == "NTRF"

    def test_wrapped_fields_and_colon_continuations_preserve_source_text(self) -> None:
        raw_61 = ":61:2401020102D10,00N100CLIENT-1//BANK-1\n/TRCD/12345/"
        fragments = [
            f"/TRTP/SEPA OVERBOEKING/IBAN/{COUNTERPARTY_IBAN}/BIC/TESTN",
            "L2A/NAME/International Mar",
            "ket/EREF/PAYMENT-1/REMI/Invoice /STORE/ branch 7 ",
            ": continuation time 12:30",
        ]
        content = _page(
            raw_61 + "\n:86:" + "\n".join(fragments),
            closing=":62F:C240102EUR90,00",
        )

        rows, _ = parse_knab_mt940(content)

        assert len(rows) == 1
        row = rows[0]
        assert row["counterparty_name"] == "International Market"
        assert row["counterparty_bic"] == "TESTNL2A"
        assert row["payment_reference"] == "PAYMENT-1"
        assert row["payment_description"] == (
            "Invoice /STORE/ branch 7 : continuation time 12:30"
        )
        assert row["raw_61"] == raw_61
        assert row["raw_86"] == "".join(fragments)
        assert row["raw_all_together"] == raw_61 + " " + "".join(fragments)
        assert ":62F:" not in row["raw_86"]

    def test_unmapped_slash_labels_remain_remittance_content(self) -> None:
        remittance = "Invoice /AB/ branch /CNTP/ external text"
        content = _page(
            ":61:2401020102D10,00N100NONREF//BANK-1\n"
            f":86:/NAME/Example Supplier/REMI/{remittance}"
        )

        rows, _ = parse_knab_mt940(content)

        assert rows[0]["payment_description"] == remittance
        assert rows[0]["description"] == "Example Supplier"
        assert rows[0]["raw_86"].endswith(remittance)

    def test_brace_prefixed_remittance_is_not_a_swift_envelope(self) -> None:
        fragments = ["/NAME/Example Supplier/REMI/Invoice ", "{1: memo text}"]
        content = _page(
            ":61:2401020102D10,00N100NONREF//BANK-1\n"
            ":86:" + "\n".join(fragments)
        )

        rows, _ = parse_knab_mt940(content)

        assert rows[0]["payment_description"] == "Invoice {1: memo text}"
        assert rows[0]["raw_86"] == "".join(fragments)


@pytest.mark.unit
class TestKnabStatementScope:
    def test_multipart_and_next_day_balances_are_signed_and_page_scoped(self) -> None:
        pages = [
            ("STMT-A", "00001/1", ":60F:C240101EUR100,00", "D10,00", ":62M:C240102EUR90,00"),
            ("STMT-A", "00001/2", ":60M:C240102EUR90,00", "D100,00", ":62M:D240102EUR10,00"),
            ("STMT-A", "00001/3", ":60M:D240102EUR10,00", "C5,00", ":62F:D240102EUR5,00"),
            ("STMT-B", "00002/1", ":60F:D240102EUR5,00", "C10,00", ":62F:C240103EUR5,00"),
            ("STMT-C", "00003/1", ":60F:C240103USD5,00", "D1,00", ":62F:C240104USD4,00"),
        ]
        content = "".join(
            _page(
                f":61:{'2401020102' if index < 3 else '2401030103' if index == 3 else '2401040104'}{amount}N100NONREF//BANK-{index}\n"
                f":86:/NAME/Example Supplier {index}/REMI/Invoice {index}",
                reference=reference,
                number=number,
                opening=opening,
                closing=closing,
            )
            for index, (reference, number, opening, amount, closing) in enumerate(pages)
        )

        rows, _ = parse_knab_mt940(content)

        assert len(rows) == 5
        assert [r["opening_balance"] for r in rows] == ["100,00", "90,00", "-10,00", "-5,00", "5,00"]
        assert [r["closing_balance"] for r in rows] == ["90,00", "-10,00", "-5,00", "5,00", "4,00"]
        assert [r["currency"] for r in rows] == ["EUR", "EUR", "EUR", "EUR", "USD"]
        assert [r["transaction_reference"] for r in rows] == ["STMT-A", "STMT-A", "STMT-A", "STMT-B", "STMT-C"]
        assert [r["statement_number"] for r in rows] == ["00001/1", "00001/2", "00001/3", "00002/1", "00003/1"]
        assert [r["date"] for r in rows] == ["02-01-2024", "02-01-2024", "02-01-2024", "03-01-2024", "04-01-2024"]
        for row in rows:
            opening = Decimal(row["opening_balance"].replace(",", "."))
            amount = Decimal(row["amount"].replace(",", "."))
            closing = Decimal(row["closing_balance"].replace(",", "."))
            assert opening + amount == closing

    def test_incomplete_next_page_does_not_borrow_previous_metadata(self) -> None:
        first = _page(
            ":61:2401020102D10,00N100NONREF//BANK-1\n:86:/NAME/First Merchant",
            closing=":62F:C240102EUR90,00",
        )
        second_account = "NL00KNAB1111111111"
        second = (
            f":20:STMT-B\n:25:{second_account}\n"
            ":61:2401030103C3,00N110NONREF//BANK-2\n"
            ":86:/NAME/Second Merchant\n"
        )

        rows, account = parse_knab_mt940(first + second)

        assert len(rows) == 2
        assert account == second_account
        assert rows[0]["account"] == ACCOUNT
        assert rows[1]["account"] == second_account
        assert rows[1]["transaction_reference"] == "STMT-B"
        assert rows[1]["statement_number"] == ""
        assert rows[1]["opening_balance"] == ""
        assert rows[1]["closing_balance"] == ""
        assert rows[1]["currency"] == ""

    def test_closing_balance_supplies_currency_when_opening_is_absent(self) -> None:
        content = _page(
            ":61:2401020102C3,00N110NONREF//BANK-1\n:86:/NAME/Example Supplier",
            opening="",
            closing=":62F:C240102GBP3,00",
        )

        rows, _ = parse_knab_mt940(content)

        assert rows[0]["currency"] == "GBP"
        assert rows[0]["opening_balance"] == ""
        assert rows[0]["closing_balance"] == "3,00"

    def test_swift_trailers_do_not_become_balance_or_description_text(self) -> None:
        header = "{1:F01KNABNL2HXXX0000000000}{2:I940TESTNL2AXXXN}{4:\n"
        first = _page(
            ":61:2401020102D10,00N100NONREF//BANK-1\n"
            ":86:/NAME/First Merchant/REMI/Invoice one",
            closing=":62F:C240102EUR90,00",
        )
        second = _page(
            ":61:2401030103C5,00N110NONREF//BANK-2\n"
            ":86:/NAME/Second Merchant/REMI/Invoice two",
            reference="STMT-B",
            number="00002/1",
            opening=":60F:C240102EUR90,00",
            closing=":62F:C240103EUR95,00",
        )
        content = (
            header + first + "-}{5:{CHK:000000000000}}\n"
            + header + second + "-}{5:{CHK:111111111111}}\n"
        )

        rows, _ = parse_knab_mt940(content)

        assert len(rows) == 2
        assert [r["opening_balance"] for r in rows] == ["100,00", "90,00"]
        assert [r["closing_balance"] for r in rows] == ["90,00", "95,00"]
        assert [r["payment_description"] for r in rows] == ["Invoice one", "Invoice two"]
        assert all("{CHK:" not in r["raw_86"] for r in rows)

    @pytest.mark.parametrize(
        ("next_number_tag", "expected_number"),
        [(":28C:00001/2\n", "00001/2"), ("", "00001/1")],
    )
    def test_next_page_without_repeated_reference_keeps_its_own_balances(
        self, next_number_tag: str, expected_number: str
    ) -> None:
        first = _page(
            ":61:2401020102D10,00N100NONREF//BANK-1\n:86:/NAME/First Merchant",
            closing=":62M:C240102EUR90,00",
        )
        second = (
            next_number_tag + ":60M:C240102EUR90,00\n"
            ":61:2401020102D20,00N100NONREF//BANK-2\n"
            ":86:/NAME/Second Merchant\n:62F:C240102EUR70,00\n"
        )

        rows, account = parse_knab_mt940(first + second)

        assert account == ACCOUNT
        assert len(rows) == 2
        assert [r["opening_balance"] for r in rows] == ["100,00", "90,00"]
        assert [r["closing_balance"] for r in rows] == ["90,00", "70,00"]
        assert [r["statement_number"] for r in rows] == ["00001/1", expected_number]
        assert all(r["account"] == ACCOUNT for r in rows)
        assert all(r["transaction_reference"] == "STMT-A" for r in rows)
        assert all(r["currency"] == "EUR" for r in rows)


@pytest.mark.unit
class TestKnabTransactionLine:
    @pytest.mark.parametrize(
        ("body", "amount", "original_amount", "entry_date", "status", "transaction_type"),
        [
            ("2401020102D10,N100CLIENT//BANK", "-10,00", "10.00", "01-02", "D", "N100"),
            ("2401020102C1,2N110CLIENT//BANK", "1,20", "1.20", "01-02", "C", "N110"),
            ("2401020102DR1,23N300CLIENT//BANK", "-1,23", "1.23", "01-02", "D", "N300"),
            ("240102C2,00N110CLIENT//BANK", "2,00", "2.00", "", "C", "N110"),
            ("2401020102RD5,00N125CLIENT//BANK", "5,00", "5.00", "01-02", "RD", "N125"),
            ("2401020102RC5,00N125CLIENT//BANK", "-5,00", "5.00", "01-02", "RC", "N125"),
        ],
    )
    def test_decimal_forms_funds_code_optional_entry_and_reversals(
        self, body: str, amount: str, original_amount: str, entry_date: str, status: str,
        transaction_type: str,
    ) -> None:
        content = _page(f":61:{body}\n:86:/NAME/Example Supplier")

        rows, _ = parse_knab_mt940(content)

        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == amount
        assert row["signed_amount"] == amount
        assert Decimal(row["original_amount"].replace(",", ".")) == Decimal(original_amount)
        assert row["entry_date"] == entry_date
        assert row["value_date"] == "02-01-2024"
        assert row["debit_credit"] == status
        assert row["customer_ref"] == "CLIENT"
        assert row["bank_ref"] == "BANK"
        assert row["reference"] == "BANK"
        assert row["transaction_type"] == transaction_type

    def test_customer_reference_remains_available_without_bank_reference(self) -> None:
        content = _page(
            ":61:2401020102D10,00N100CUSTOMER-ONLY\n:86:/NAME/Example Supplier"
        )

        rows, _ = parse_knab_mt940(content)

        assert rows[0]["customer_ref"] == "CUSTOMER-ONLY"
        assert rows[0]["bank_ref"] == ""
        assert rows[0]["reference"] == "CUSTOMER-ONLY"


@pytest.mark.unit
class TestKnabDetection:
    @pytest.mark.parametrize(
        "content",
        [
            f":25:{ACCOUNT}\n",
            f":25:{ACCOUNT}EUR\n",
            "{1:F01KNABNL2HXXX0000000000}{2:I940TESTNL2AXXXN}{4:\n",
        ],
    )
    def test_bank_identity_selects_knab(self, content: str) -> None:
        assert looks_like_knab_content(content)

    @pytest.mark.parametrize(
        "content",
        [
            "",
            ":25:NL00INGB0123456789EUR\n:86:/TRTP/SEPA OVERBOEKING/NAME/Knab\n",
            ":86:/TRTP/SEPA OVERBOEKING/IBAN/NL00KNAB0123456789/NAME/Example Supplier\n",
            "Payment memo: KNABNL2H\n",
            "{1:F01INGBNL2AXXX0000000000}{2:I940KNABNL2HXXXN}{4:\n"
            ":25:NL00INGB0123456789EUR\n",
            "{1:F01KNABNL2HXXX0000000000}{4:\n:25:NL00INGB0123456789EUR\n",
            "{2:I940KNABNL2HXXXN}{4:\n",
            f":25:{ACCOUNT}\n:25:NL00INGB0123456789EUR\n",
        ],
    )
    def test_generic_tags_and_counterparty_identity_do_not_select_knab(self, content: str) -> None:
        assert not looks_like_knab_content(content)
