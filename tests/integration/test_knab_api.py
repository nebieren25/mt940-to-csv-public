"""Knab uploads and exports use the existing API and CSV schema."""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from src.core.domain import CSV_HEADERS


CONTENT = """:20:SYNTHETIC001
:25:NL00KNAB0000000000
:28C:00001/001
:60F:C240101EUR100,00
:61:2401020102D10,00N100NONREF//BANK001
:86:/TRTP/SEPA OVERBOEKING/IBAN/NL00TEST0000000000/BIC/TESTNL2A/NAME/SAMPLE SUPPLIER/REMI/Invoice 42
:62M:C240102EUR90,00
:20:SYNTHETIC002
:25:NL00KNAB0000000000
:28C:00001/002
:60M:C240102EUR90,00
:61:2401020102D5,00N300NONREF//BANK002
:86:/TRTP/BETAALAUTOMAAT/NAME/SAMPLE SHOP/REMI/Payment at 12
:34 in Rotterdam
:62F:C240102EUR85,00
"""


@pytest.mark.integration
class TestKnabAPI:
    def test_auto_and_knab_uploads_match_and_keep_page_balances(self, app):
        with TestClient(app) as client:
            results = []
            for profile in ("auto", "knab"):
                response = client.post(
                    "/api/convert",
                    files={"file": ("synthetic-knab.txt", CONTENT.encode(), "text/plain")},
                    data={"bank_profile": profile, "delimiter": ";"},
                )
                assert response.status_code == 200
                results.append(response.json())
            assert results[0] == results[1]
            result = results[0]
            assert result["success"] is True
            assert result["row_count"] == 2
            assert result["summary"]["total_expense"] == 15.0
            rows = result["rows"]
            assert [r["opening_balance"] for r in rows] == ["100,00", "90,00"]
            assert [r["closing_balance"] for r in rows] == ["90,00", "85,00"]
            assert rows[1]["payment_description"] == "Payment at 12:34 in Rotterdam"
            assert ":34 in Rotterdam" in rows[1]["raw_86"]
            exported = list(csv.DictReader(io.StringIO(result["csv"]), delimiter=";"))
            assert list(exported[0]) == CSV_HEADERS
            assert exported[1]["counterparty_name"] == "SAMPLE SHOP"

    @pytest.mark.parametrize("delimiter,decimal", [(";", ","), (",", "."), ("\t", ",")])
    def test_direct_csv_and_reexport_keep_details(self, app, delimiter, decimal):
        with TestClient(app) as client:
            options = {"bank_profile": "knab", "delimiter": delimiter, "decimal_sep": decimal}
            response = client.post(
                "/api/convert?format=csv",
                files={"file": ("synthetic-knab.txt", CONTENT.encode(), "text/plain")},
                data=options,
            )
            assert response.status_code == 200
            assert "text/csv" in response.headers["content-type"]
            rows = list(csv.DictReader(io.StringIO(response.text), delimiter=delimiter))
            assert len(rows) == 2
            assert rows[0]["amount"] == "-10" + decimal + "00"
            assert rows[1]["closing_balance"] == "85" + decimal + "00"
            assert rows[0]["counterparty_iban"] == "NL00TEST0000000000"
            parsed = client.post(
                "/api/convert",
                files={"file": ("synthetic-knab.txt", CONTENT.encode(), "text/plain")},
                data=options,
            ).json()
            exported = client.post("/api/export", json={
                "rows": parsed["rows"], "delimiter": delimiter, "decimal_sep": decimal,
                "description_style": "counterparty_with_description",
            })
            assert exported.status_code == 200
            rows = list(csv.DictReader(io.StringIO(exported.json()["csv"]), delimiter=delimiter))
            assert rows[1]["description"] == "SAMPLE SHOP - Payment at 12:34 in Rotterdam"
            assert ":34 in Rotterdam" in rows[1]["raw_86"]

    def test_exported_csv_can_be_uploaded_again(self, app):
        with TestClient(app) as client:
            result = client.post(
                "/api/convert",
                files={"file": ("synthetic-knab.txt", CONTENT.encode(), "text/plain")},
                data={"bank_profile": "knab", "delimiter": ";"},
            ).json()
            response = client.post(
                "/api/convert",
                files={"file": ("synthetic-knab.csv", result["csv"].encode(), "text/csv")},
                data={"delimiter": ";"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["row_count"] == 2
            assert data["summary"] == result["summary"]
            assert data["rows"][0]["counterparty_name"] == "SAMPLE SUPPLIER"
            assert data["rows"][1]["closing_balance"] == "85,00"
